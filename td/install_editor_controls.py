# CYD_TD_Controller — Editor controls installer
# Run once inside TouchDesigner Textport or a Text DAT (td_execute).
#
# Textport example:
#   exec(open('/path/to/repo/td/install_editor_controls.py').read())
#
# Override repo root (folder containing editor_ctl.py) when auto-detect fails:
PROJECT_DIR = ""  # e.g. "/Users/you/cyd-td-controller"

import os
import sys

# --- Embedded sources (self-contained tox after install) -------------------
# Updated from sibling .py files when present next to this script.

_EMBEDDED_CYD_EDITOR_EXT = r'''"""TouchDesigner Extension: bridge CYD_TD_Controller Editor pulses to editor_ctl.py."""

import json
import os
import re
import shutil
import socket
import subprocess
import sys

SERVER_PORT = 3737
VITE_PORT = 5173
FALLBACK_VERSION = "0.11.0"
REPO_CLONE_URL = "https://github.com/naotochan/CYD_TD_Controller.git"
REPO_CLONE_REF = "cursor/td-editor-control-f789"  # switch to "main" after merge
CLONE_DIRNAME = "CYD_TD_Controller"
SETUP_TIMEOUT = 900
UV_SYNC_TIMEOUT = 300
NPM_INSTALL_TIMEOUT = 240
ENV_TEMPLATE = """\
WIFI_SSID=your_wifi_ssid
WIFI_PASSWORD=your_wifi_password
OSC_HOST=127.0.0.1
OSC_PORT=24320
# OSC_LISTEN_PORT=24321
"""


class CydEditorExt:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self._syncing_run = False
        self._last_ctl_data = None

    def _set_setupstatus(self, msg: str) -> None:
        par = getattr(self.ownerComp.par, "Setupstatus", None)
        if par is not None:
            par.val = (msg or "")[:500]

    def _set_par_str(self, name: str, value: str) -> None:
        par = getattr(self.ownerComp.par, name, None)
        if par is not None:
            par.val = (value or "")[:500]

    def _human_status_from_data(self, data: dict) -> str:
        running = bool(data.get("running"))
        base = "running" if running else "stopped"
        url = data.get("url")
        if url:
            return f"{base} ({url})"
        return base

    def _status_probe_dir(self, data: dict) -> str:
        """Repo root for setup probing when status JSON lacks setup_ready."""
        for key in ("project_dir", "repo_root", "path"):
            raw = data.get(key)
            if raw:
                path = str(raw).strip().strip('"').strip("'")
                if path and self._has_editor_ctl(path):
                    return path

        project_dir = self._project_dir()
        if project_dir:
            return project_dir

        return self._resolve_base_dir()

    def _probe_setup_status(self, repo_root: str) -> tuple[bool, list[str]]:
        """Filesystem probe for old editor_ctl status JSON without setup_ready."""
        if not repo_root:
            return False, []

        missing: list[str] = []
        venv_dir = os.path.join(repo_root, ".venv")
        venv_ok = False
        if os.path.isdir(venv_dir):
            bin_name = "Scripts" if sys.platform == "win32" else "bin"
            bin_dir = os.path.join(venv_dir, bin_name)
            ext = ".exe" if sys.platform == "win32" else ""
            if os.path.isfile(os.path.join(bin_dir, f"mpremote{ext}")):
                venv_ok = True
            elif os.path.isfile(os.path.join(bin_dir, f"python{ext}")):
                venv_ok = True
        if not venv_ok:
            missing.append("venv")

        vite_marker = os.path.join(repo_root, "ui-editor", "node_modules", "vite")
        if not os.path.isdir(vite_marker):
            missing.append("npm")

        if not os.path.isfile(os.path.join(repo_root, ".env")):
            missing.append("env")

        return (not missing), missing

    def _apply_status(self, data: dict, *, update_setupstatus: bool = True) -> str:
        if "setup_ready" not in data:
            probe_dir = self._status_probe_dir(data)
            if probe_dir:
                setup_ready, missing = self._probe_setup_status(probe_dir)
            else:
                setup_ready = False
                missing = []
        else:
            setup_ready = bool(data.get("setup_ready"))
            missing = data.get("missing") or []

        if setup_ready:
            setupready = "ready"
        elif missing:
            setupready = "incomplete: " + ", ".join(missing)
        else:
            setupready = "unknown"
        self._set_par_str("Setupready", setupready)

        port = data.get("port")
        ports = data.get("ports") or []
        if port:
            serialport = str(port)
        elif not ports:
            serialport = "none"
        elif data.get("flash_ok") is False and len(ports) > 1:
            shown = ", ".join(ports[:4])
            if len(ports) > 4:
                shown += ", ..."
            serialport = f"ambiguous: {shown}"
        else:
            serialport = "none"
        self._set_par_str("Serialport", serialport)

        status = self._human_status_from_data(data)
        if update_setupstatus:
            self._set_setupstatus(status)

        run_par = getattr(self.ownerComp.par, "Run", None)
        if run_par is not None:
            self._syncing_run = True
            try:
                run_par.val = bool(data.get("running"))
            finally:
                self._syncing_run = False

        flash_par = getattr(self.ownerComp.par, "Flashmicropython", None)
        if flash_par is not None and hasattr(flash_par, "enable"):
            flash_par.enable = False

        self.UpdateViewer(data)
        return status

    def _toe_folder_runtime(self) -> str:
        try:
            folder = project.folder  # noqa: F821
            if folder:
                return os.path.abspath(folder)
        except Exception:
            pass
        return ""

    def _extra_path_dirs(self) -> tuple:
        home_local = os.path.join(os.path.expanduser("~"), ".local", "bin")
        if sys.platform == "darwin":
            return (home_local, "/opt/homebrew/bin", "/usr/local/bin")
        if sys.platform == "win32":
            dirs = []
            program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
            dirs.append(os.path.join(program_files, "Git", "cmd"))
            dirs.append(os.path.join(program_files, "nodejs"))
            appdata = os.environ.get("APPDATA")
            if appdata:
                dirs.append(os.path.join(appdata, "npm"))
            return tuple(d for d in dirs if os.path.isdir(d))
        return (home_local, "/usr/local/bin")

    def _subprocess_env(self) -> dict:
        env = os.environ.copy()
        current = env.get("PATH", "")
        parts = [p for p in current.split(os.pathsep) if p]
        existing = set(parts)
        prepend = [
            p for p in self._extra_path_dirs() if p not in existing and os.path.isdir(p)
        ]
        if prepend:
            env["PATH"] = os.pathsep.join(prepend + parts)
        return env

    def _find_executable(self, name: str, *, extra_candidates: tuple = ()) -> str | None:
        env = self._subprocess_env()
        found = shutil.which(name, path=env.get("PATH", ""))
        if found:
            return found
        for candidate in extra_candidates:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return None

    def _find_git(self) -> str | None:
        if sys.platform == "win32":
            program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
            extras = (
                os.path.join(program_files, "Git", "bin", "git.exe"),
                os.path.join(program_files, "Git", "cmd", "git.exe"),
            )
        else:
            extras = ("/opt/homebrew/bin/git", "/usr/local/bin/git")
        return self._find_executable("git", extra_candidates=extras)

    def _uv_candidates(self) -> tuple:
        if sys.platform == "darwin":
            home = os.path.expanduser("~")
            return (
                os.path.join(home, ".local", "bin", "uv"),
                "/opt/homebrew/bin/uv",
                "/usr/local/bin/uv",
            )
        if sys.platform == "win32":
            home = os.environ.get("USERPROFILE", os.path.expanduser("~"))
            candidates = [
                os.path.join(home, ".local", "bin", "uv.exe"),
                os.path.join(home, ".cargo", "bin", "uv.exe"),
            ]
            program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
            candidates.append(os.path.join(program_files, "uv", "uv.exe"))
            return tuple(candidates)
        home = os.path.expanduser("~")
        return (os.path.join(home, ".local", "bin", "uv"), "/usr/local/bin/uv")

    def _npm_candidates(self) -> tuple:
        if sys.platform == "darwin":
            return ("/opt/homebrew/bin/npm", "/usr/local/bin/npm")
        if sys.platform == "win32":
            candidates = []
            program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
            candidates.append(os.path.join(program_files, "nodejs", "npm.cmd"))
            appdata = os.environ.get("APPDATA")
            if appdata:
                candidates.append(os.path.join(appdata, "npm", "npm.cmd"))
            localappdata = os.environ.get("LOCALAPPDATA")
            if localappdata:
                candidates.append(
                    os.path.join(localappdata, "Programs", "node", "npm.cmd")
                )
            return tuple(candidates)
        return ()

    def _find_uv(self) -> str | None:
        return self._find_executable("uv", extra_candidates=self._uv_candidates())

    def _find_npm(self) -> str | None:
        candidates = self._npm_candidates()
        found = self._find_executable("npm", extra_candidates=candidates)
        if found:
            return found
        if sys.platform == "win32":
            return self._find_executable("npm.cmd", extra_candidates=candidates)
        return None

    def _setup_subcommand_missing(self, msg: str) -> bool:
        lower = (msg or "").lower()
        return "invalid choice" in lower and "setup" in lower

    def _ensure_deps_fallback(self, repo_root: str) -> None:
        """Install deps when cloned editor_ctl lacks setup subcommand."""
        self._set_setupstatus("installing Python deps (uv sync)...")
        uv = self._find_uv()
        if not uv:
            raise RuntimeError(
                "uv not found in PATH; install uv to sync Python dependencies"
            )

        try:
            result = subprocess.run(
                [uv, "sync"],
                capture_output=True,
                text=True,
                timeout=UV_SYNC_TIMEOUT,
                cwd=repo_root,
                env=self._subprocess_env(),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"uv sync timed out after {UV_SYNC_TIMEOUT}s"
            ) from exc

        if result.returncode != 0:
            combined = ((result.stderr or "") + (result.stdout or "")).strip()
            snippet = combined[:500] or f"exit {result.returncode}"
            raise RuntimeError(f"uv sync failed: {snippet}")

        env_path = os.path.join(repo_root, ".env")
        if not os.path.isfile(env_path):
            self._set_setupstatus("creating .env template...")
            with open(env_path, "w", encoding="utf-8") as fh:
                fh.write(ENV_TEMPLATE)

        ui_editor = os.path.join(repo_root, "ui-editor")
        vite_marker = os.path.join(ui_editor, "node_modules", "vite")
        if os.path.isdir(ui_editor) and not os.path.isdir(vite_marker):
            self._set_setupstatus("installing ui-editor deps (npm install)...")
            npm = self._find_npm()
            if not npm:
                raise RuntimeError(
                    "npm not found in PATH; install Node.js/npm for the editor"
                )
            try:
                result = subprocess.run(
                    [npm, "install"],
                    capture_output=True,
                    text=True,
                    timeout=NPM_INSTALL_TIMEOUT,
                    cwd=ui_editor,
                    env=self._subprocess_env(),
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"npm install timed out after {NPM_INSTALL_TIMEOUT}s"
                ) from exc
            if result.returncode != 0:
                combined = ((result.stderr or "") + (result.stdout or "")).strip()
                snippet = combined[:500] or f"exit {result.returncode}"
                raise RuntimeError(f"npm install failed: {snippet}")
            if not os.path.isdir(vite_marker):
                raise RuntimeError(
                    "npm install finished but vite is still missing in ui-editor"
                )

        self._set_setupstatus("deps installed")

    def _resolve_base_dir(self) -> str:
        """Projectdir or .toe folder — does not require editor_ctl.py."""
        par = getattr(self.ownerComp.par, "Projectdir", None)
        path = ""
        if par is not None:
            raw = par.eval()
            if raw is not None:
                path = str(raw).strip().strip('"').strip("'")
        if not path:
            path = self._toe_folder_runtime()
        return path

    def _has_editor_ctl(self, directory: str) -> bool:
        return bool(directory) and os.path.isfile(os.path.join(directory, "editor_ctl.py"))

    def _clone_base_dir(self, base_dir: str) -> str:
        """Parent directory for CYD_TD_Controller/ — avoids nested clone."""
        norm = os.path.normpath(base_dir)
        if os.path.basename(norm) == CLONE_DIRNAME and not self._has_editor_ctl(norm):
            parent = os.path.dirname(norm)
            if parent:
                return parent
        return base_dir

    def _run_git(self, git: str, args: list, *, cwd: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [git, *args],
                capture_output=True,
                text=True,
                timeout=SETUP_TIMEOUT,
                cwd=cwd,
                env=self._subprocess_env(),
            )
        except subprocess.TimeoutExpired as exc:
            cmd = " ".join(args[:3])
            raise RuntimeError(f"git {cmd} timed out after {SETUP_TIMEOUT}s") from exc

    def _fresh_git_clone(self, git: str, base_dir: str) -> None:
        result = self._run_git(
            git,
            [
                "clone",
                "--depth",
                "1",
                "--branch",
                REPO_CLONE_REF,
                REPO_CLONE_URL,
                CLONE_DIRNAME,
            ],
            cwd=base_dir,
        )
        if result.returncode != 0:
            combined = ((result.stderr or "") + (result.stdout or "")).strip()
            snippet = combined[:300] or f"exit {result.returncode}"
            raise RuntimeError(f"git clone failed: {snippet}")

    def _try_repair_incomplete_clone(self, git: str, clone_path: str) -> bool:
        git_dir = os.path.join(clone_path, ".git")
        if not os.path.isdir(git_dir):
            return False

        self._set_setupstatus("repairing incomplete clone...")
        fetch = self._run_git(git, ["fetch", "origin", REPO_CLONE_REF], cwd=clone_path)
        if fetch.returncode != 0:
            return False

        checkout = self._run_git(git, ["checkout", REPO_CLONE_REF], cwd=clone_path)
        if checkout.returncode != 0:
            pull = self._run_git(git, ["pull", "origin", REPO_CLONE_REF], cwd=clone_path)
            if pull.returncode != 0:
                return False

        return self._has_editor_ctl(clone_path)

    def _clone_repo(self, base_dir: str) -> str:
        """Shallow-clone into base_dir/CLONE_DIRNAME; return repo root path."""
        git = self._find_git()
        if not git:
            raise RuntimeError(
                "git not found in PATH; install Git to clone CYD_TD_Controller"
            )

        clone_path = os.path.join(base_dir, CLONE_DIRNAME)
        if self._has_editor_ctl(clone_path):
            return clone_path

        if os.path.isdir(clone_path):
            if os.listdir(clone_path):
                if self._try_repair_incomplete_clone(git, clone_path):
                    return clone_path
                self._set_setupstatus("re-cloning...")
                shutil.rmtree(clone_path)
            else:
                try:
                    os.rmdir(clone_path)
                except OSError as exc:
                    raise RuntimeError(
                        f"cannot use empty {clone_path} for clone: {exc}"
                    ) from exc

        os.makedirs(base_dir, exist_ok=True)
        self._set_setupstatus(f"cloning {CLONE_DIRNAME}...")
        self._fresh_git_clone(git, base_dir)

        if not self._has_editor_ctl(clone_path):
            raise RuntimeError(
                f"clone finished but editor_ctl.py missing in {clone_path}"
            )
        return clone_path

    def _ensure_repo_root(self, base_dir: str) -> tuple[str, bool]:
        """Return (repo_root, cloned). Clone into subdir when needed."""
        if not base_dir:
            raise RuntimeError("Project Dir is empty; save the .toe or set Project Dir")

        if self._has_editor_ctl(base_dir):
            return base_dir, False

        clone_base = self._clone_base_dir(base_dir)
        clone_path = os.path.join(clone_base, CLONE_DIRNAME)
        if self._has_editor_ctl(clone_path):
            return clone_path, False

        return self._clone_repo(clone_base), True

    def _retarget_projectdir(self, repo_root: str, base_dir: str) -> None:
        """Point Projectdir at repo root when it differs from the resolved base."""
        if os.path.normpath(repo_root) == os.path.normpath(base_dir):
            return

        par = getattr(self.ownerComp.par, "Projectdir", None)
        if par is None:
            raise RuntimeError("Projectdir parameter missing; cannot retarget")

        toe = self._toe_folder_runtime()
        expected_subdir = os.path.join(toe, CLONE_DIRNAME) if toe else ""
        if toe and os.path.normpath(repo_root) == os.path.normpath(expected_subdir):
            try:
                par.mode = ParMode.EXPRESSION  # noqa: F821
                par.expr = f"project.folder+'/{CLONE_DIRNAME}'"
                return
            except Exception as exc:
                raise RuntimeError(
                    f"failed to set Projectdir expression: {exc}"
                ) from exc

        try:
            par.val = repo_root
        except Exception as exc:
            raise RuntimeError(
                f"failed to set Projectdir to {repo_root}: {exc}"
            ) from exc

    def _mark_project_dir_error(self, msg: str) -> None:
        self._set_setupstatus(msg)
        self._set_par_str("Setupready", "incomplete: project dir")
        self.UpdateViewer()

    def _port_open(self, host: str, port: int, timeout: float = 0.3) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def _port_listening(self, port: int, timeout: float = 0.3) -> bool:
        if self._port_open("127.0.0.1", port, timeout):
            return True
        return self._port_open("::1", port, timeout)

    def _probe_running(self) -> bool:
        return self._port_listening(SERVER_PORT) and self._port_listening(VITE_PORT)

    def _read_version(self) -> str:
        project_dir = ""
        par = getattr(self.ownerComp.par, "Projectdir", None)
        if par is not None:
            raw = par.eval()
            if raw is not None:
                project_dir = str(raw).strip().strip('"').strip("'")
        if not project_dir:
            project_dir = self._toe_folder_runtime()
        if project_dir:
            pyproject = os.path.join(project_dir, "pyproject.toml")
            if os.path.isfile(pyproject):
                try:
                    with open(pyproject, encoding="utf-8") as fh:
                        for line in fh:
                            match = re.match(
                                r'^\s*version\s*=\s*["\']([^"\']+)["\']', line
                            )
                            if match:
                                return match.group(1)
                except OSError:
                    pass
            main_py = os.path.join(project_dir, "main.py")
            if os.path.isfile(main_py):
                try:
                    with open(main_py, encoding="utf-8") as fh:
                        for line in fh:
                            match = re.match(
                                r'^__version__\s*=\s*["\']([^"\']+)["\']', line
                            )
                            if match:
                                return match.group(1)
                except OSError:
                    pass
        return FALLBACK_VERSION

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
        value = hex_color.lstrip("#")
        return (
            int(value[0:2], 16) / 255.0,
            int(value[2:4], 16) / 255.0,
            int(value[4:6], 16) / 255.0,
        )

    def _set_top_color(self, top, hex_color: str) -> None:
        r, g, b = self._hex_to_rgb(hex_color)
        if hasattr(top.par, "colorr"):
            top.par.colorr = r
            top.par.colorg = g
            top.par.colorb = b
        else:
            top.par.fontcolorr = r
            top.par.fontcolorg = g
            top.par.fontcolorb = b

    def UpdateViewer(self, data=None) -> None:
        comp = self.ownerComp
        bg_top = comp.op("viewer_bg")
        title_top = comp.op("viewer_title")
        state_top = comp.op("viewer_state")
        meta_top = comp.op("viewer_meta")
        if not any((bg_top, title_top, state_top, meta_top)):
            return

        if isinstance(data, dict) and "running" in data:
            running = bool(data.get("running"))
        else:
            running = self._probe_running()

        version = self._read_version()

        if running:
            bg_hex = "#101814"
            state_text = "RUNNING"
            state_hex = "#34d399"
            meta_text = f"v{version}  ·  :3737 :5173"
        else:
            bg_hex = "#141416"
            state_text = "STOPPED"
            state_hex = "#9ca3af"
            meta_text = f"v{version}  ·  offline"

        muted_hex = "#9ca3af"

        if bg_top is not None:
            self._set_top_color(bg_top, bg_hex)
        if title_top is not None:
            title_top.par.text = "CYD EDITOR"
            self._set_top_color(title_top, muted_hex)
        if state_top is not None:
            state_top.par.text = state_text
            self._set_top_color(state_top, state_hex)
        if meta_top is not None:
            meta_top.par.text = meta_text
            self._set_top_color(meta_top, muted_hex)

    def _fetch_status_data(self) -> dict | None:
        project_dir = self._project_dir()
        if not project_dir:
            return None
        ctl_path = os.path.join(project_dir, "editor_ctl.py")
        try:
            result = subprocess.run(
                [sys.executable, ctl_path, "status"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=project_dir,
            )
            data = json.loads((result.stdout or "").strip())
        except (subprocess.TimeoutExpired, json.JSONDecodeError, TypeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def _project_dir(self) -> str:
        par = getattr(self.ownerComp.par, "Projectdir", None)
        if par is None:
            self._mark_project_dir_error("error: Projectdir parameter missing")
            return ""

        raw = par.eval()
        path = ""
        if raw is not None:
            path = str(raw).strip().strip('"').strip("'")

        if not path:
            path = self._toe_folder_runtime()

        if not path:
            self._mark_project_dir_error(
                "error: set Projectdir to folder containing editor_ctl.py "
                "(defaults to .toe folder or CYD_TD_Controller clone)"
            )
            return ""

        ctl = os.path.join(path, "editor_ctl.py")
        if not os.path.isfile(ctl):
            self._mark_project_dir_error(
                f"error: editor_ctl.py not found in {path} "
                "(set Projectdir to CYD clone if .toe folder lacks it)"
            )
            return ""

        return path

    def _format_status(self, cmd: str, stdout: str, stderr: str, returncode: int) -> str:
        stdout = (stdout or "").strip()
        stderr = (stderr or "").strip()

        if cmd == "flash":
            try:
                data = json.loads(stdout)
            except (json.JSONDecodeError, TypeError):
                data = None
            if isinstance(data, dict):
                if data.get("ok") and data.get("flashed"):
                    port = data.get("port")
                    if port:
                        return f"flashed ({port})"
                    return "flashed"
                err = data.get("error") or stderr or stdout
                return f"error: {str(err)[:200]}"

        if cmd in ("start", "stop", "status", "open", "setup"):
            try:
                data = json.loads(stdout)
            except (json.JSONDecodeError, TypeError):
                data = None
            if isinstance(data, dict):
                return self._human_status_from_data(data)

        if returncode != 0:
            snippet = stderr or stdout or f"exit {returncode}"
            return f"error: {snippet[:200]}"

        if stdout:
            return stdout[:200]
        return "stopped" if cmd == "stop" else "ok"

    def _run_ctl(self, cmd: str, *, project_dir: str | None = None) -> str:
        if project_dir is None:
            project_dir = self._project_dir()
            if not project_dir:
                par = getattr(self.ownerComp.par, "Setupstatus", None)
                return par.eval() if par is not None else "error"
        else:
            ctl_check = os.path.join(project_dir, "editor_ctl.py")
            if not os.path.isfile(ctl_check):
                msg = f"error: editor_ctl.py not found in {project_dir}"
                self._set_setupstatus(msg)
                return msg

        ctl_path = os.path.join(project_dir, "editor_ctl.py")
        self._set_setupstatus(f"running {cmd}...")

        timeout = 600 if cmd in ("start", "open", "flash") else SETUP_TIMEOUT if cmd == "setup" else 60
        try:
            result = subprocess.run(
                [sys.executable, ctl_path, cmd],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=project_dir,
            )
        except subprocess.TimeoutExpired:
            msg = f"error: {cmd} timed out"
            self._set_setupstatus(msg)
            return msg
        except OSError as exc:
            msg = f"error: {cmd} failed: {exc}"
            self._set_setupstatus(msg)
            return msg

        stdout = (result.stdout or "").strip()
        self._last_ctl_data = None

        if cmd in ("start", "stop", "status", "open", "setup"):
            try:
                data = json.loads(stdout)
            except (json.JSONDecodeError, TypeError):
                data = None
            if isinstance(data, dict):
                self._last_ctl_data = data
                if cmd == "setup" and not data.get("ok", True):
                    err = data.get("error") or "setup failed"
                    error_msg = f"error: {str(err)[:200]}"
                    self._set_setupstatus(error_msg)
                    self._apply_status(data, update_setupstatus=False)
                    return error_msg
                status = self._apply_status(data)
                return status

        status = self._format_status(cmd, result.stdout, result.stderr, result.returncode)
        self._set_setupstatus(status)
        return status

    def OnRunChanged(self, on: bool):
        if self._syncing_run:
            return None
        if on:
            return self._run_ctl("start")
        return self._run_ctl("stop")

    def Setup(self):
        """Clone repo (if needed) and ensure deps without starting servers."""
        self._set_setupstatus("running setup...")
        repo_root = ""
        cloned = False
        try:
            base_dir = self._resolve_base_dir()
            repo_root, cloned = self._ensure_repo_root(base_dir)
            if os.path.normpath(repo_root) != os.path.normpath(base_dir):
                self._retarget_projectdir(repo_root, base_dir)
        except RuntimeError as exc:
            msg = f"error: {exc}"
            self._set_setupstatus(str(msg)[:500])
            self._set_par_str("Setupready", "incomplete: setup")
            self.UpdateViewer()
            return msg

        status = self._run_ctl("setup", project_dir=repo_root)
        data = self._last_ctl_data if isinstance(self._last_ctl_data, dict) else {}

        if self._setup_subcommand_missing(status):
            try:
                self._ensure_deps_fallback(repo_root)
            except RuntimeError as exc:
                msg = f"error: {exc}"
                self._set_setupstatus(str(msg)[:500])
                self._set_par_str("Setupready", "incomplete: setup")
                self.UpdateViewer()
                return msg
            status = self._run_ctl("status", project_dir=repo_root)
            data = self._last_ctl_data if isinstance(self._last_ctl_data, dict) else {}
        elif status.startswith("error") or not data.get("ok", True):
            return status

        if cloned and data.get("setup_ready"):
            self._set_setupstatus(f"setup complete ({CLONE_DIRNAME})")
        return status

    def StartSetup(self):
        return self.Setup()

    def StopSetup(self):
        return self._run_ctl("stop")

    def EditCyd(self):
        return self._run_ctl("open")

    def RefreshStatus(self):
        return self._run_ctl("status")

    def FlashMicropython(self):
        flash_par = getattr(self.ownerComp.par, "Flashmicropython", None)
        if flash_par is not None and hasattr(flash_par, "enable") and not flash_par.enable:
            msg = "error: no CYD serial port (connect USB)"
            self._set_setupstatus(msg)
            return msg

        data = self._fetch_status_data()
        if data is None:
            status = self._run_ctl("flash")
        else:
            self._apply_status(data, update_setupstatus=False)
            if not data.get("flash_ok"):
                ports = data.get("ports") or []
                if not ports:
                    msg = "error: no CYD serial port (connect USB)"
                else:
                    shown = ", ".join(ports[:5])
                    if len(ports) > 5:
                        shown += ", ..."
                    msg = f"error: ambiguous serial ports: {shown}"
                self._set_setupstatus(msg)
                return msg
            status = self._run_ctl("flash")

        refresh = self._fetch_status_data()
        if refresh is not None:
            self._apply_status(refresh, update_setupstatus=False)
        return status
'''

_EMBEDDED_PAREXEC_EDITOR = r'''# Parameter Execute DAT — parent COMP custom pars, ops='..'


def onPulse(par):
    comp = parent()
    ext = comp.ext.CydEditorExt
    name = par.name

    if name == "Setup":
        ext.Setup()
    elif name == "Startsetup":
        ext.Setup()
    elif name == "Stopsetup":
        ext.StopSetup()
    elif name == "Editcyd":
        ext.EditCyd()
    elif name == "Refreshstatus":
        ext.RefreshStatus()


def onValueChange(par, prev):
    if par.name == "Run":
        parent().ext.CydEditorExt.OnRunChanged(bool(par.eval()))
'''

_README_BODY = """CYD_TD_Controller
==================

OSC + Editor controls for the CYD TouchDesigner controller COMP.

CYD page (unchanged by Editor installer)
----------------------------------------
- Active / Listenport (24320) — OSC In from ESP32
- Esp32address / Sendport (24321) / Sendactive — OSC Out to ESP32
- Stripsegments — LED strip segment count

Editor page
-----------
- Projectdir — defaults to project.folder (.toe directory)
- Setup Ready — read-only: ready / incomplete: venv, npm, env
- Serial Port — read-only: selected port, none, or ambiguous list
- Setup — pulse: shallow-clone into CYD_TD_Controller/ when needed + uv sync + .env + npm install (no servers)
- Run — toggle deploy server + Vite on/off (after Setup)
- Edit CYD — editor_ctl open (browser)
- Refresh Status — editor_ctl status → updates Setup Ready, Serial Port, Run
- Flash MicroPython — Web editor (Deploy 横のボタン)。CLI: `editor_ctl flash`
- Setupstatus — read-only last action / running state

Legacy (existing tox only): Start Setup / Stop Setup pulses disabled — use Setup then Run.

Internal operators (minimal build)
----------------------------------
oscin -> null_all -> out_all ; null_send -> oscout

COMP node viewer (bg nullTOP)
-----------------------------
Dark 480x270 card: live Run status + version (ports 3737/5173 when running).
viewer_bg + viewer_title/state/meta -> viewer_layer1/2/3 -> bg ; exec_viewer polls UpdateViewer.

Regenerate this COMP: run td/install_editor_controls.py in TD Textport.
Cloud CI cannot run TouchDesigner; generate td/CYD_TD_Controller.tox locally.
"""


def _script_dir():
    """Best-effort td/ folder containing this installer."""
    if PROJECT_DIR:
        return os.path.join(PROJECT_DIR, "td")

    path = globals().get("__file__")
    if path:
        return os.path.dirname(os.path.abspath(path))

    try:
        me = op("install_editor_controls")  # noqa: F821
        folder = me.par.file.eval()
        if folder:
            return folder
    except Exception:
        pass

    return ""


def _load_text(filename, embedded):
    td_dir = _script_dir()
    if td_dir:
        path = os.path.join(td_dir, filename)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                return fh.read()
    return embedded


def _repo_root():
    if PROJECT_DIR:
        return os.path.abspath(PROJECT_DIR)

    td_dir = _script_dir()
    if td_dir:
        parent = os.path.dirname(td_dir)
        if os.path.isfile(os.path.join(parent, "editor_ctl.py")):
            return parent

    return ""


def _toe_folder():
    try:
        folder = project.folder  # noqa: F821
        if folder:
            return os.path.abspath(folder)
    except Exception:
        pass
    return ""


def _resolve_comp():
    """Return CYD_TD_Controller COMP, creating a minimal shell if needed."""
    created = False

    for path in ("/project1/CYD_TD_Controller", "CYD_TD_Controller"):
        try:
            comp = op(path)  # noqa: F821
            if comp is not None:
                return comp, created
        except Exception:
            pass

    try:
        project1 = op("/project1")  # noqa: F821
    except Exception:
        project1 = None
    parent_path = "/project1" if project1 is not None else "/"
    parent = op(parent_path)  # noqa: F821
    comp = parent.create(baseCOMP, "CYD_TD_Controller")
    created = True
    print(f"Created new baseCOMP at {comp.path}")
    return comp, created


def _find_custom_page(comp, name):
    for page in comp.customPages:
        if page.name == name:
            return page
    return None


def _set_par_readonly(par):
    for attr in ("readOnly", "readonly"):
        if hasattr(par, attr):
            try:
                setattr(par, attr, True)
                return
            except Exception:
                pass
    if hasattr(par, "enable"):
        try:
            par.enable = False
        except Exception:
            pass


def _ensure_cyd_page(comp):
    """Create CYD custom page + minimal OSC network when building from scratch."""
    if hasattr(comp.par, "Listenport"):
        print("CYD page parameters already present — leaving unchanged.")
        return

    page = _find_custom_page(comp, "CYD")
    if page is None:
        page = comp.appendCustomPage("CYD")

    specs = (
        ("Toggle", "Active", "Active", True),
        ("Int", "Listenport", "Listen Port", 24320),
        ("Str", "Esp32address", "ESP32 Address", "192.168.1.100"),
        ("Int", "Sendport", "Send Port", 24321),
        ("Int", "Stripsegments", "Strip Segments", 1),
        ("Toggle", "Sendactive", "Send Active", False),
    )
    for kind, name, label, default in specs:
        if hasattr(comp.par, name):
            continue
        append = getattr(page, f"append{kind}", None)
        if append is None:
            print(f"WARNING: cannot append {kind} parameter {name}")
            continue
        par = append(name, label=label)
        if kind == "Toggle":
            par.default = bool(default)
        elif kind == "Int":
            par.default = int(default)
        else:
            par.default = str(default)

    _ensure_osc_shell(comp)
    _bind_osc_expressions(comp)


def _ensure_osc_shell(comp):
    def _op(name, create_fn):
        existing = comp.op(name)
        if existing:
            return existing
        return create_fn()

    oscin = _op("oscin", lambda: comp.create(oscinCHOP, "oscin"))
    null_all = _op("null_all", lambda: comp.create(nullCHOP, "null_all"))
    out_all = _op("out_all", lambda: comp.create(outCHOP, "out_all"))
    oscout = _op("oscout", lambda: comp.create(oscoutCHOP, "oscout"))
    null_send = _op("null_send", lambda: comp.create(nullCHOP, "null_send"))

    if null_all.inputConnectors[0].connections == []:
        null_all.inputConnectors[0].connect(oscin)
    if out_all.inputConnectors[0].connections == []:
        out_all.inputConnectors[0].connect(null_all)
    if oscout.inputConnectors[0].connections == []:
        oscout.inputConnectors[0].connect(null_send)

    readme = comp.op("readme")
    if readme is None:
        readme = comp.create(textDAT, "readme")
    readme.text = _README_BODY

    print("OSC shell: oscin -> null_all -> out_all ; null_send -> oscout")


def _bind_osc_expressions(comp):
    """Bind oscin/oscout to CYD page custom pars when parameter names exist."""
    oscin = comp.op("oscin")
    oscout = comp.op("oscout")
    bindings = []

    if oscin:
        if hasattr(oscin.par, "port") and hasattr(comp.par, "Listenport"):
            oscin.par.port.expr = "parent().par.Listenport"
            bindings.append("oscin.port <- Listenport")
        if hasattr(oscin.par, "active") and hasattr(comp.par, "Active"):
            oscin.par.active.expr = "parent().par.Active"
            bindings.append("oscin.active <- Active")

    if oscout:
        if hasattr(oscout.par, "address") and hasattr(comp.par, "Esp32address"):
            oscout.par.address.expr = "parent().par.Esp32address"
            bindings.append("oscout.address <- Esp32address")
        if hasattr(oscout.par, "port") and hasattr(comp.par, "Sendport"):
            oscout.par.port.expr = "parent().par.Sendport"
            bindings.append("oscout.port <- Sendport")
        if hasattr(oscout.par, "active") and hasattr(comp.par, "Sendactive"):
            oscout.par.active.expr = "parent().par.Sendactive"
            bindings.append("oscout.active <- Sendactive")

    if bindings:
        print("OSC expressions: " + ", ".join(bindings))
    else:
        print("WARNING: could not bind OSC expressions; check operator parameter names.")


def _set_projectdir_portable(par):
    """Portable Projectdir: expression project.folder, else empty for runtime fallback."""
    try:
        par.mode = ParMode.EXPRESSION  # noqa: F821
        par.expr = "project.folder"
        return "expression project.folder"
    except Exception:
        pass
    try:
        par.val = ""
        return "empty (runtime uses project.folder)"
    except Exception:
        return None


def _ensure_editor_page(comp, repo_root):
    page = _find_custom_page(comp, "Editor")
    if page is None:
        page = comp.appendCustomPage("Editor")

    toe_hint = _toe_folder() or repo_root or ""

    if not hasattr(comp.par, "Projectdir"):
        append_folder = getattr(page, "appendFolder", None)
        if append_folder:
            par = append_folder("Projectdir", label="Project Dir")
        else:
            par = page.appendFile("Projectdir", label="Project Dir")
        mode = _set_projectdir_portable(par)
        if toe_hint:
            print(
                f"Projectdir portable ({mode}); current .toe folder: {toe_hint}"
            )
        elif mode:
            print(f"Projectdir portable: {mode}")
    else:
        par = comp.par.Projectdir
        current = str(par.eval() or "").strip().strip('"').strip("'")
        if not current:
            mode = _set_projectdir_portable(par)
            if toe_hint:
                print(
                    f"Projectdir portable ({mode}); current .toe folder: {toe_hint}"
                )
            elif mode:
                print(f"Projectdir portable: {mode}")

    if not hasattr(comp.par, "Setupready"):
        par = page.appendStr("Setupready", label="Setup Ready")
        par.default = "unknown"
        _set_par_readonly(par)

    if not hasattr(comp.par, "Serialport"):
        par = page.appendStr("Serialport", label="Serial Port")
        par.default = "none"
        _set_par_readonly(par)

    if not hasattr(comp.par, "Setup"):
        page.appendPulse("Setup", label="Setup")
    else:
        setup_par = comp.par.Setup
        if hasattr(setup_par, "enable"):
            try:
                setup_par.enable = True
            except Exception:
                pass
        if hasattr(setup_par, "label"):
            try:
                setup_par.label = "Setup"
            except Exception:
                pass

    if not hasattr(comp.par, "Run"):
        par = page.appendToggle("Run", label="Run")
        par.default = False

    pulses = (
        ("Editcyd", "Edit CYD"),
        ("Refreshstatus", "Refresh Status"),
    )
    for name, label in pulses:
        if not hasattr(comp.par, name):
            page.appendPulse(name, label=label)

    flash_par = getattr(comp.par, "Flashmicropython", None)
    if flash_par is not None and hasattr(flash_par, "enable"):
        try:
            flash_par.enable = False
        except Exception:
            pass

    for legacy in ("Startsetup", "Stopsetup"):
        if hasattr(comp.par, legacy):
            par = getattr(comp.par, legacy)
            if hasattr(par, "enable"):
                try:
                    par.enable = False
                except Exception:
                    pass

    if not hasattr(comp.par, "Setupstatus"):
        par = page.appendStr("Setupstatus", label="Setup Status")
        par.default = "stopped"
        _set_par_readonly(par)

    if hasattr(comp.par, "Setupstatus") and not str(comp.par.Setupstatus.eval() or "").strip():
        comp.par.Setupstatus.val = "stopped"


def _ensure_text_dat(comp, name, source):
    dat = comp.op(name)
    if dat is None:
        dat = comp.create(textDAT, name)
    dat.text = source
    if hasattr(dat, "viewer"):
        dat.viewer = False
    lang = getattr(dat.par, "language", None)
    if lang is not None:
        try:
            lang.val = "python"
        except Exception:
            pass
    return dat


def _ensure_parexec(comp, source):
    parexec = comp.op("parexec_editor")
    if parexec is None:
        parexec = comp.create(parameterexecuteDAT, "parexec_editor")
    parexec.text = source
    parexec.par.active = True

    # Watch parent COMP custom parameters (Editor pulses live on parent).
    if hasattr(parexec.par, "ops"):
        parexec.par.ops = ".."
    elif hasattr(parexec.par, "op"):
        parexec.par.op = ".."

    if hasattr(parexec.par, "onpulse"):
        parexec.par.onpulse = True
    if hasattr(parexec.par, "valuechange"):
        parexec.par.valuechange = True
    for par_name in (
        "valueschanged",
        "expressionchange",
        "exportchange",
        "enablechange",
        "modechange",
    ):
        if hasattr(parexec.par, par_name):
            try:
                setattr(parexec.par, par_name, False)
            except Exception:
                pass

    if hasattr(parexec.par, "fromop"):
        try:
            parexec.par.fromop = ""
        except Exception:
            try:
                parexec.par.fromop = None
            except Exception:
                pass

    if hasattr(parexec.par, "custom"):
        parexec.par.custom = True
    if hasattr(parexec.par, "pars"):
        parexec.par.pars = "Setup Run Editcyd Refreshstatus Startsetup Stopsetup"
    if hasattr(parexec.par, "builtin"):
        parexec.par.builtin = False

    lang = getattr(parexec.par, "language", None)
    if lang is not None:
        try:
            lang.val = "python"
        except Exception:
            pass

    return parexec


def _extension_object_expr(ext_dat):
    return f"op('./{ext_dat.name}').module.CydEditorExt(me)"


def _set_extension_object_par(par, ext_dat):
    """Bind extension object par (OP ref on legacy TD, Python expr on TD 2025+)."""
    is_str_style = getattr(par, "style", None) == "Str" or not getattr(par, "isOP", True)
    if is_str_style:
        expr = _extension_object_expr(ext_dat)
        par.val = expr
        return expr
    par.val = ext_dat
    return ext_dat


def _bind_extension(comp, ext_dat):
    """Attach CydEditorExt Text DAT to COMP extensions (TD version tolerant)."""
    bound = False

    for par_name in ("ext0object", "Ext0object", "extension1object"):
        par = getattr(comp.par, par_name, None)
        if par is None:
            continue
        try:
            value = _set_extension_object_par(par, ext_dat)
            bound = True
            print(f"Set {par_name} -> {value!r}")
            break
        except Exception as exc:
            print(f"Note: {par_name} assignment failed: {exc}")

    if not bound:
        for par_name in ("ext0", "Ext0"):
            par = getattr(comp.par, par_name, None)
            if par is None:
                continue
            try:
                value = _set_extension_object_par(par, ext_dat)
                bound = True
                print(f"Set {par_name} -> {value!r}")
                break
            except Exception as exc:
                print(f"Note: {par_name} assignment failed: {exc}")

    for par_name in ("ext0name", "Ext0name", "extension1name"):
        par = getattr(comp.par, par_name, None)
        if par is None:
            continue
        try:
            par.val = "CydEditorExt"
            print(f"Set {par_name} = CydEditorExt")
            break
        except Exception:
            pass

    for par_name in ("ext0promote", "Ext0promote"):
        par = getattr(comp.par, par_name, None)
        if par is None:
            continue
        try:
            par.val = True
            break
        except Exception:
            pass

    reinit_par = getattr(comp.par, "reinitextensions", None)
    if reinit_par is not None and hasattr(reinit_par, "pulse"):
        reinit_par.pulse()
        print("Pulsed comp.par.reinitextensions")
    else:
        reinit = getattr(comp, "initializeExtensions", None)
        if callable(reinit):
            reinit()
            print("Called comp.initializeExtensions()")
        else:
            reinit = getattr(comp, "extensionsReinit", None)
            if callable(reinit):
                reinit()
                print("Called comp.extensionsReinit()")

    if not bound:
        expr = _extension_object_expr(ext_dat)
        print(
            "WARNING: could not auto-bind extension DAT. "
            f"Manually set Extensions → Extension 0 Object to {expr!r} "
            "(TD 2025+ Str style) or ext_CydEditorExt (legacy OP style), "
            "Extension 0 Name to CydEditorExt, then Re-Init Extensions."
        )


_EMBEDDED_EXEC_VIEWER = r'''# Execute DAT — poll viewer status ~2x/sec

_frame = 0


def onFrameStart(frame):
    global _frame
    _frame += 1
    if _frame % 30 != 0:
        return
    try:
        parent().ext.CydEditorExt.UpdateViewer()
    except Exception:
        pass
'''

_VIEWER_W = 480
_VIEWER_H = 270
_VIEWER_FONT = "Avenir Next"


def _create_viewer_op(comp, op_type, name):
    existing = comp.op(name)
    if existing is not None:
        return existing
    try:
        tdapi = op.TDAPI  # noqa: F821
        new_op = tdapi.CreateOp(op_type, parent=comp, name=name)
    except Exception:
        new_op = comp.create(op_type, name)
    if hasattr(new_op, "viewer"):
        new_op.viewer = True
    return new_op


def _set_top_resolution(top):
    if hasattr(top.par, "outputresolution"):
        top.par.outputresolution = "custom"
    if hasattr(top.par, "resolutionw"):
        top.par.resolutionw = _VIEWER_W
    if hasattr(top.par, "resolutionh"):
        top.par.resolutionh = _VIEWER_H


def _configure_text_top(top, text, size, color_rgb, alignx, aligny, posy):
    top.par.text = text
    for attr in ("font", "fontface"):
        if hasattr(top.par, attr):
            try:
                setattr(top.par, attr, _VIEWER_FONT)
                break
            except Exception:
                pass
    for attr in ("fontsizex", "fontsize"):
        if hasattr(top.par, attr):
            setattr(top.par, attr, size)
    if hasattr(top.par, "fontsizey"):
        top.par.fontsizey = size
    r, g, b = color_rgb
    top.par.fontcolorr = r
    top.par.fontcolorg = g
    top.par.fontcolorb = b
    if hasattr(top.par, "alignx"):
        top.par.alignx = alignx
    if hasattr(top.par, "aligny"):
        top.par.aligny = aligny
    if hasattr(top.par, "positiony"):
        top.par.positiony = posy
    _set_top_resolution(top)


def _set_composite_operand_over(comp_op):
    if not hasattr(comp_op.par, "operand"):
        return
    for val in ("over", "Over"):
        try:
            comp_op.par.operand = val
            return
        except Exception:
            continue


def _wire_composite(comp, name, bottom, top_layer, node_x, node_y):
    comp_op = _create_viewer_op(comp, compositeTOP, name)
    comp_op.nodeX = node_x
    comp_op.nodeY = node_y
    _set_top_resolution(comp_op)
    _set_composite_operand_over(comp_op)
    if comp_op.inputConnectors[0].connections == []:
        comp_op.inputConnectors[0].connect(bottom)
    if len(comp_op.inputConnectors) > 1 and comp_op.inputConnectors[1].connections == []:
        comp_op.inputConnectors[1].connect(top_layer)
    return comp_op


def _ensure_exec_viewer(comp):
    exec_dat = comp.op("exec_viewer")
    if exec_dat is None:
        exec_dat = comp.create(executeDAT, "exec_viewer")
    exec_dat.text = _EMBEDDED_EXEC_VIEWER
    if hasattr(exec_dat, "viewer"):
        exec_dat.viewer = True
    if hasattr(exec_dat.par, "active"):
        exec_dat.par.active = True
    if hasattr(exec_dat.par, "framestart"):
        exec_dat.par.framestart = True
    lang = getattr(exec_dat.par, "language", None)
    if lang is not None:
        try:
            lang.val = "python"
        except Exception:
            pass
    exec_dat.nodeX = 0
    exec_dat.nodeY = 200
    return exec_dat


def _remove_legacy_viewer_ops(comp):
    for name in ("text1", "text2", "constant1", "constant2", "comp1", "comp2", "switch1"):
        old = comp.op(name)
        if old is None:
            continue
        try:
            old.destroy()
            print(f"Removed legacy viewer op: {name}")
        except Exception as exc:
            print(f"Note: could not remove {name}: {exc}")


def _set_comp_opviewer(comp, bg_null):
    for par_name in ("nodeview", "Nodeview"):
        par = getattr(comp.par, par_name, None)
        if par is None:
            continue
        for val in ("opviewer", "operatorviewer", "Operator Viewer", "opview"):
            try:
                par.val = val
                print(f"Set {par_name} = {val!r} (Operator Viewer)")
                break
            except Exception:
                continue
        break

    for par_name in ("opviewer", "Opviewer"):
        par = getattr(comp.par, par_name, None)
        if par is None:
            continue
        try:
            par.val = bg_null
            print(f"Set {par_name} -> bg")
            break
        except Exception:
            pass


def _ensure_status_viewer(comp):
    """Build live status card (viewer_* TOPs) feeding bg nullTOP."""
    _remove_legacy_viewer_ops(comp)

    muted = (156 / 255.0, 163 / 255.0, 175 / 255.0)
    stopped_bg = (20 / 255.0, 20 / 255.0, 22 / 255.0)

    viewer_bg = _create_viewer_op(comp, constantTOP, "viewer_bg")
    viewer_bg.nodeX = 0
    viewer_bg.nodeY = 0
    viewer_bg.par.colorr = stopped_bg[0]
    viewer_bg.par.colorg = stopped_bg[1]
    viewer_bg.par.colorb = stopped_bg[2]
    _set_top_resolution(viewer_bg)

    viewer_title = _create_viewer_op(comp, textTOP, "viewer_title")
    viewer_title.nodeX = 220
    viewer_title.nodeY = 0
    _configure_text_top(viewer_title, "CYD EDITOR", 14, muted, "center", "top", 0.38)

    viewer_state = _create_viewer_op(comp, textTOP, "viewer_state")
    viewer_state.nodeX = 440
    viewer_state.nodeY = 0
    _configure_text_top(viewer_state, "STOPPED", 28, muted, "center", "center", 0)

    viewer_meta = _create_viewer_op(comp, textTOP, "viewer_meta")
    viewer_meta.nodeX = 660
    viewer_meta.nodeY = 0
    _configure_text_top(viewer_meta, "v0.11.0  ·  offline", 12, muted, "center", "bottom", -0.38)

    layer1 = _wire_composite(comp, "viewer_layer1", viewer_bg, viewer_title, 0, -180)
    layer2 = _wire_composite(comp, "viewer_layer2", layer1, viewer_state, 220, -180)
    layer3 = _wire_composite(comp, "viewer_layer3", layer2, viewer_meta, 440, -180)

    bg = comp.op("bg")
    if bg is None:
        bg = _create_viewer_op(comp, nullTOP, "bg")
    bg.nodeX = 660
    bg.nodeY = -180
    try:
        bg.inputConnectors[0].disconnect()
    except Exception:
        pass
    if bg.inputConnectors[0].connections == []:
        bg.inputConnectors[0].connect(layer3)

    _ensure_exec_viewer(comp)
    _set_comp_opviewer(comp, bg)

    try:
        comp.ext.CydEditorExt.UpdateViewer()
    except Exception:
        pass

    print("Status viewer: viewer_bg + text layers -> viewer_layer3 -> bg")


def _update_readme_dat(comp):
    readme = comp.op("readme")
    if readme is None:
        readme = comp.create(textDAT, "readme")
    readme.text = _README_BODY


def run():
    ext_source = _load_text("CydEditorExt.py", _EMBEDDED_CYD_EDITOR_EXT)
    parexec_source = _load_text("parexec_editor.py", _EMBEDDED_PAREXEC_EDITOR)
    repo_root = _repo_root()

    comp, created = _resolve_comp()
    print(f"Target COMP: {comp.path}")

    if created:
        _ensure_cyd_page(comp)
    else:
        if not hasattr(comp.par, "Listenport"):
            print("Existing COMP has no CYD Listenport par — adding CYD page + OSC shell.")
            _ensure_cyd_page(comp)

    _ensure_editor_page(comp, repo_root)
    _ensure_text_dat(comp, "ext_CydEditorExt", ext_source)
    _ensure_parexec(comp, parexec_source)
    _bind_extension(comp, comp.op("ext_CydEditorExt"))
    _ensure_status_viewer(comp)
    _update_readme_dat(comp)

    td_dir = _script_dir() or os.path.join(repo_root, "td") if repo_root else ""
    if not td_dir and repo_root:
        td_dir = os.path.join(repo_root, "td")

    if not td_dir:
        print(
            "WARNING: could not resolve td/ output folder. "
            "Set PROJECT_DIR at top of install_editor_controls.py and re-run."
        )
        print("Editor controls installed; tox not saved.")
        return False

    os.makedirs(td_dir, exist_ok=True)
    tox_path = os.path.join(td_dir, "CYD_TD_Controller.tox")

    if hasattr(comp.par, "Projectdir"):
        mode = _set_projectdir_portable(comp.par.Projectdir)
        if mode:
            print(f"Projectdir for tox save: {mode}")

    try:
        comp.save(tox_path)
        print(f"SUCCESS: saved {tox_path}")
    except Exception as exc:
        print(f"FAIL: comp.save failed: {exc}")
        return False

    print(
        "Done. Projectdir uses project.folder at runtime; "
        "pulse Setup to clone into CYD_TD_Controller/ and install deps, then toggle Run."
    )
    return True


# When executed outside TouchDesigner (no `op` builtin), exit with message.
try:
    op  # noqa: F821
except NameError:
    print("install_editor_controls.py must be run inside TouchDesigner (Textport or Text DAT).")
    print("Example: exec(open('<repo>/td/install_editor_controls.py').read())")
    if __name__ == "__main__":
        sys.exit(1)
else:
    run()
