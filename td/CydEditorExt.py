"""TouchDesigner Extension: bridge CYD_TD_Controller Editor pulses to editor_ctl.py."""

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
