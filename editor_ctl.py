#!/usr/bin/env python3
"""CLI to start/stop/status/open the deploy server and Vite editor."""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_CLONE_URL = "https://github.com/naotochan/CYD_TD_Controller.git"
CLONE_DIRNAME = "CYD_TD_Controller"
PID_FILE = os.path.join(REPO_ROOT, ".editor.pids")
LOG_DIR = os.path.join(REPO_ROOT, ".editor_logs")
SERVER_LOG = os.path.join(LOG_DIR, "server.log")
VITE_LOG = os.path.join(LOG_DIR, "vite.log")
SERVER_SCRIPT = os.path.join(REPO_ROOT, "server.py")
UI_EDITOR_DIR = os.path.join(REPO_ROOT, "ui-editor")
SERVER_PORT = 3737
VITE_PORT = 5173
EDITOR_URL = f"http://localhost:{VITE_PORT}"
START_POLL_TIMEOUT = 12.0
START_POLL_INTERVAL = 0.25
NPM_INSTALL_TIMEOUT = 240.0
UV_SYNC_TIMEOUT = 300.0
ENV_FILE = os.path.join(REPO_ROOT, ".env")
FIRMWARE_BIN = os.path.join(REPO_ROOT, "micropython_esp32.bin")
UI_EDITOR_VITE_MARKER = os.path.join(UI_EDITOR_DIR, "node_modules", "vite")
ENV_TEMPLATE = """\
WIFI_SSID=your_wifi_ssid
WIFI_PASSWORD=your_wifi_password
OSC_HOST=127.0.0.1
OSC_PORT=24320
# OSC_LISTEN_PORT=24321
"""


def _extra_path_dirs() -> tuple[str, ...]:
    """Platform dirs often missing from TouchDesigner's minimal PATH."""
    home_local = os.path.join(os.path.expanduser("~"), ".local", "bin")
    if sys.platform == "darwin":
        return (home_local, "/opt/homebrew/bin", "/usr/local/bin")
    if sys.platform == "win32":
        dirs: list[str] = []
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        dirs.append(os.path.join(program_files, "nodejs"))
        appdata = os.environ.get("APPDATA")
        if appdata:
            dirs.append(os.path.join(appdata, "npm"))
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            dirs.append(os.path.join(localappdata, "Programs", "node"))
        return tuple(d for d in dirs if os.path.isdir(d))
    return (home_local, "/usr/local/bin")


def _npm_candidates() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return ("/opt/homebrew/bin/npm", "/usr/local/bin/npm")
    if sys.platform == "win32":
        candidates: list[str] = []
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        candidates.append(os.path.join(program_files, "nodejs", "npm.cmd"))
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(os.path.join(appdata, "npm", "npm.cmd"))
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            candidates.append(os.path.join(localappdata, "Programs", "node", "npm.cmd"))
        return tuple(candidates)
    return ()


def subprocess_env() -> dict:
    """Return os.environ copy with PATH extended for TD's minimal environment."""
    env = os.environ.copy()
    current = env.get("PATH", "")
    parts = [p for p in current.split(os.pathsep) if p]
    existing = set(parts)
    prepend = [p for p in _extra_path_dirs() if p not in existing and os.path.isdir(p)]
    if prepend:
        env["PATH"] = os.pathsep.join(prepend + parts)
    return env


def find_executable(name: str, *, extra_candidates: tuple[str, ...] = ()) -> str | None:
    """Resolve an executable using enriched PATH and optional absolute fallbacks."""
    env = subprocess_env()
    found = shutil.which(name, path=env.get("PATH", ""))
    if found:
        return found
    for candidate in extra_candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _uv_candidates() -> tuple[str, ...]:
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


def find_uv() -> str | None:
    return find_executable("uv", extra_candidates=_uv_candidates())


def _venv_bin_dir() -> str:
    if sys.platform == "win32":
        return os.path.join(REPO_ROOT, ".venv", "Scripts")
    return os.path.join(REPO_ROOT, ".venv", "bin")


def venv_python() -> str:
    path = os.path.join(_venv_bin_dir(), "python.exe" if sys.platform == "win32" else "python")
    if os.path.isfile(path):
        return path
    raise RuntimeError(".venv Python not found; run Setup to sync dependencies")


def _venv_executable(name: str) -> str | None:
    bindir = _venv_bin_dir()
    if sys.platform == "win32":
        candidates = (f"{name}.exe", name)
    else:
        candidates = (name, f"{name}.py")
    for candidate in candidates:
        path = os.path.join(bindir, candidate)
        if os.path.isfile(path):
            return path
    return None


def venv_has_python_deps() -> bool:
    if not os.path.isdir(os.path.join(REPO_ROOT, ".venv")):
        return False
    if _venv_executable("mpremote") is None:
        return False
    if _venv_executable("esptool") is not None:
        return True
    py = _venv_executable("python") or (
        os.path.join(_venv_bin_dir(), "python.exe" if sys.platform == "win32" else "python")
    )
    if not os.path.isfile(py):
        return False
    try:
        result = subprocess.run(
            [py, "-m", "esptool", "version"],
            capture_output=True,
            timeout=10,
            check=False,
            env=subprocess_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def ensure_python_deps() -> None:
    """Create .venv and install Python tools when missing or incomplete."""
    if venv_has_python_deps():
        return

    uv = find_uv()
    if not uv:
        raise RuntimeError(
            "uv not found in PATH; install with: "
            "curl -LsSf https://astral.sh/uv/install.sh | sh "
            "(Windows: winget install astral-sh.uv)"
        )

    print("Syncing Python deps (uv sync)...", file=sys.stderr)
    ensure_log_dir()
    try:
        result = subprocess.run(
            [uv, "sync"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=UV_SYNC_TIMEOUT,
            check=False,
            env=subprocess_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"uv sync timed out after {UV_SYNC_TIMEOUT:.0f}s") from exc

    combined = (result.stderr or "") + (result.stdout or "")
    if combined.strip():
        with open(SERVER_LOG, "a", encoding="utf-8") as fh:
            fh.write("\n--- uv sync ---\n")
            fh.write(combined)
            if not combined.endswith("\n"):
                fh.write("\n")

    if result.returncode != 0:
        snippet = combined.strip()[:500]
        raise RuntimeError(f"uv sync failed: {snippet or f'exit {result.returncode}'}")

    if not venv_has_python_deps():
        raise RuntimeError("uv sync finished but mpremote/esptool are still missing in .venv")


def ensure_env_file() -> None:
    """Create a .env template when missing (never overwrite)."""
    if os.path.isfile(ENV_FILE):
        return
    with open(ENV_FILE, "w", encoding="utf-8") as fh:
        fh.write(ENV_TEMPLATE)
    print("Created .env — edit WiFi/OSC settings before deploy", file=sys.stderr)


def find_npm() -> str | None:
    """Resolve npm (npm.cmd on Windows) using enriched PATH and known install locations."""
    candidates = _npm_candidates()
    found = find_executable("npm", extra_candidates=candidates)
    if found:
        return found
    if sys.platform == "win32":
        return find_executable("npm.cmd", extra_candidates=candidates)
    return None


def port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def port_listening(port: int, timeout: float = 0.3) -> bool:
    """Return True if something is accepting TCP connections on port."""
    if port_open("127.0.0.1", port, timeout):
        return True
    try:
        with socket.create_connection(("::1", port), timeout=timeout):
            return True
    except OSError:
        return False


def server_up() -> bool:
    return port_listening(SERVER_PORT)


def editor_up() -> bool:
    return port_listening(VITE_PORT)


def _npm_ready() -> bool:
    return os.path.isdir(UI_EDITOR_VITE_MARKER)


def _env_ready() -> bool:
    return os.path.isfile(ENV_FILE)


def status_dict() -> dict:
    srv = server_up()
    ed = editor_up()
    venv_ok = venv_has_python_deps()
    npm_ok = _npm_ready()
    env_ok = _env_ready()
    missing: list[str] = []
    if not venv_ok:
        missing.append("venv")
    if not npm_ok:
        missing.append("npm")
    if not env_ok:
        missing.append("env")
    setup_ready = not missing

    from server import list_ports, select_port

    ports = list_ports()
    port, _, ambiguous = select_port()
    flash_ok = bool(port) and not ambiguous

    return {
        "running": srv and ed,
        "server": srv,
        "editor": ed,
        "url": EDITOR_URL,
        "setup_ready": setup_ready,
        "venv": venv_ok,
        "npm": npm_ok,
        "env": env_ok,
        "missing": missing,
        "ports": ports,
        "port": port,
        "flash_ok": flash_ok,
    }


def print_status() -> None:
    print(json.dumps(status_dict()))


def read_pid_file() -> dict | None:
    if not os.path.isfile(PID_FILE):
        return None
    try:
        with open(PID_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return None
        return {
            "server_pid": int(data.get("server_pid", 0)),
            "vite_pid": int(data.get("vite_pid", 0)),
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def write_pid_file(server_pid: int, vite_pid: int) -> None:
    os.makedirs(os.path.dirname(PID_FILE) or ".", exist_ok=True)
    with open(PID_FILE, "w", encoding="utf-8") as fh:
        json.dump({"server_pid": server_pid, "vite_pid": vite_pid}, fh)
        fh.write("\n")


def remove_pid_file() -> None:
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def kill_pid(pid: int, sigterm_wait: float = 2.0) -> None:
    if pid <= 0 or not pid_alive(pid):
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        return

    deadline = time.monotonic() + sigterm_wait
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            return
        time.sleep(0.1)

    if pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def kill_process_group(pid: int, sigterm_wait: float = 2.0) -> None:
    if pid <= 0:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            kill_pid(pid, sigterm_wait)
        return
    try:
        pgid = os.getpgid(pid)
    except (ProcessLookupError, PermissionError):
        kill_pid(pid, sigterm_wait)
        return

    try:
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        kill_pid(pid, sigterm_wait)
        return

    deadline = time.monotonic() + sigterm_wait
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            return
        time.sleep(0.1)

    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        kill_pid(pid, sigterm_wait)


def kill_pids_from_file() -> None:
    pids = read_pid_file()
    if not pids:
        return
    kill_process_group(pids.get("server_pid", 0))
    kill_process_group(pids.get("vite_pid", 0))


def _netstat_local_port(addr: str) -> int | None:
    """Extract the local TCP/UDP port from a netstat address field."""
    if addr.startswith("["):
        idx = addr.rfind("]:")
        if idx == -1:
            return None
        port_str = addr[idx + 2 :]
    elif ":" in addr:
        port_str = addr.rsplit(":", 1)[1]
    else:
        return None
    try:
        return int(port_str)
    except ValueError:
        return None


def _kill_port_listeners_windows(port: int) -> None:
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        if _netstat_local_port(parts[1]) != port:
            continue
        try:
            pids.add(int(parts[-1]))
        except ValueError:
            continue
    for pid in pids:
        if pid <= 0:
            continue
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            kill_pid(pid)


def kill_port_listeners(port: int) -> None:
    if sys.platform == "win32":
        _kill_port_listeners_windows(port)
        return
    env = subprocess_env()
    lsof = shutil.which("lsof", path=env.get("PATH", ""))
    if not lsof:
        return
    try:
        result = subprocess.run(
            [lsof, f"-ti:{port}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pid = int(line)
        except ValueError:
            continue
        kill_pid(pid)


def ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def _spawn_process(args: list[str], cwd: str, log_path: str) -> subprocess.Popen:
    ensure_log_dir()
    log = open(log_path, "a", encoding="utf-8")
    common = {
        "args": args,
        "cwd": cwd,
        "stdout": log,
        "stderr": subprocess.STDOUT,
        "env": subprocess_env(),
    }
    try:
        return subprocess.Popen(**common, start_new_session=True)
    except (AttributeError, OSError, ValueError):
        return subprocess.Popen(**common)


def ensure_ui_editor_deps() -> None:
    """Run npm install when ui-editor dependencies are missing or incomplete."""
    if os.path.isdir(UI_EDITOR_VITE_MARKER):
        return

    npm = find_npm()
    if not npm:
        raise RuntimeError("npm not found in PATH; install Node.js/npm to run the editor")

    print("Installing ui-editor dependencies (npm install)...", file=sys.stderr)
    ensure_log_dir()
    try:
        result = subprocess.run(
            [npm, "install"],
            cwd=UI_EDITOR_DIR,
            capture_output=True,
            text=True,
            timeout=NPM_INSTALL_TIMEOUT,
            check=False,
            env=subprocess_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"npm install timed out after {NPM_INSTALL_TIMEOUT:.0f}s"
        ) from exc

    combined = (result.stderr or "") + (result.stdout or "")
    if combined.strip():
        with open(VITE_LOG, "a", encoding="utf-8") as fh:
            fh.write("\n--- npm install ---\n")
            fh.write(combined)
            if not combined.endswith("\n"):
                fh.write("\n")

    if result.returncode != 0:
        snippet = combined.strip()[:500]
        raise RuntimeError(f"npm install failed: {snippet or f'exit {result.returncode}'}")

    if not os.path.isdir(UI_EDITOR_VITE_MARKER):
        raise RuntimeError("npm install finished but node_modules/vite is still missing")


def spawn_server() -> subprocess.Popen:
    return _spawn_process([sys.executable, SERVER_SCRIPT], REPO_ROOT, SERVER_LOG)


def spawn_vite() -> subprocess.Popen:
    npm = find_npm()
    if not npm:
        raise RuntimeError("npm not found in PATH; install Node.js/npm to run the editor")

    return _spawn_process([npm, "run", "dev"], UI_EDITOR_DIR, VITE_LOG)


def wait_for_ports(timeout: float = START_POLL_TIMEOUT) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = status_dict()
        if st["server"] and st["editor"]:
            return st
        time.sleep(START_POLL_INTERVAL)
    return status_dict()


def cmd_status(_args: argparse.Namespace) -> int:
    print_status()
    return 0


def cmd_setup(_args: argparse.Namespace) -> int:
    """Ensure Python/UI deps and .env without starting servers."""
    try:
        ensure_python_deps()
        ensure_env_file()
        ensure_ui_editor_deps()
    except RuntimeError as exc:
        st = status_dict()
        st["ok"] = False
        st["error"] = str(exc)
        print(json.dumps(st))
        print(str(exc), file=sys.stderr)
        return 1

    st = status_dict()
    st["ok"] = True
    st["cloned"] = False
    print(json.dumps(st))
    return 0 if st.get("setup_ready") else 1


def cmd_start(_args: argparse.Namespace) -> int:
    st = status_dict()
    if st["running"]:
        print_status()
        return 0

    server_proc = None
    vite_proc = None

    try:
        ensure_python_deps()
        ensure_env_file()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        print_status()
        return 1

    if not st["server"]:
        server_proc = spawn_server()
    if not st["editor"]:
        try:
            ensure_ui_editor_deps()
            vite_proc = spawn_vite()
        except RuntimeError as exc:
            if server_proc is not None:
                kill_process_group(server_proc.pid)
            print(str(exc), file=sys.stderr)
            print_status()
            return 1

    server_pid = server_proc.pid if server_proc else (read_pid_file() or {}).get("server_pid", 0)
    vite_pid = vite_proc.pid if vite_proc else (read_pid_file() or {}).get("vite_pid", 0)

    if server_proc or vite_proc:
        if not server_pid and st["server"]:
            server_pid = 0
        if not vite_pid and st["editor"]:
            vite_pid = 0
        write_pid_file(server_pid or 0, vite_pid or 0)

    st = wait_for_ports()
    print_status()

    if st["running"]:
        return 0

    if server_proc is not None:
        kill_process_group(server_proc.pid)
    if vite_proc is not None:
        kill_process_group(vite_proc.pid)
    if server_up():
        kill_port_listeners(SERVER_PORT)
    if editor_up():
        kill_port_listeners(VITE_PORT)
    remove_pid_file()

    if not st["server"]:
        print("Server did not become ready on port 3737", file=sys.stderr)
    if not st["editor"]:
        print(f"Editor did not become ready on port {VITE_PORT}", file=sys.stderr)
    return 1


def cmd_stop(_args: argparse.Namespace) -> int:
    kill_pids_from_file()
    if server_up():
        kill_port_listeners(SERVER_PORT)
    if editor_up():
        kill_port_listeners(VITE_PORT)
    remove_pid_file()
    print_status()
    return 0


def open_url(url: str) -> None:
    if sys.platform == "darwin":
        opener = shutil.which("open")
        if opener:
            subprocess.run([opener, url], check=False)
            return
    if sys.platform.startswith("linux"):
        for cmd in ("xdg-open", "gio", "sensible-browser"):
            opener = shutil.which(cmd)
            if opener:
                subprocess.run([opener, url], check=False)
                return
    webbrowser.open(url)


def _run_esptool(args: list[str]) -> subprocess.CompletedProcess:
    py = venv_python()
    return subprocess.run(
        [py, "-m", "esptool", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=subprocess_env(),
    )


def cmd_flash(_args: argparse.Namespace) -> int:
    try:
        ensure_python_deps()
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        print(str(exc), file=sys.stderr)
        return 1

    if not os.path.isfile(FIRMWARE_BIN):
        msg = f"{os.path.basename(FIRMWARE_BIN)} not found in repo root"
        print(json.dumps({"ok": False, "error": msg}))
        print(msg, file=sys.stderr)
        return 1

    from server import select_port

    port, candidates, ambiguous = select_port()
    if not candidates:
        msg = "No serial port found; connect the ESP32 via USB"
        print(json.dumps({"ok": False, "error": msg, "ports": []}))
        print(msg, file=sys.stderr)
        return 1
    if ambiguous or port is None:
        msg = f"Ambiguous serial ports: {', '.join(candidates)}"
        print(json.dumps({"ok": False, "error": msg, "ports": candidates}))
        print(msg, file=sys.stderr)
        return 1

    erase = _run_esptool(["--port", port, "erase_flash"])
    if erase.returncode != 0:
        combined = ((erase.stderr or "") + (erase.stdout or "")).strip()
        msg = combined[:500] or f"erase_flash failed (exit {erase.returncode})"
        print(json.dumps({"ok": False, "error": msg, "port": port}))
        print(msg, file=sys.stderr)
        return 1

    write = _run_esptool(
        ["--port", port, "--baud", "460800", "write_flash", "0x1000", FIRMWARE_BIN]
    )
    if write.returncode != 0:
        combined = ((write.stderr or "") + (write.stdout or "")).strip()
        msg = combined[:500] or f"write_flash failed (exit {write.returncode})"
        print(json.dumps({"ok": False, "error": msg, "port": port}))
        print(msg, file=sys.stderr)
        return 1

    st = status_dict()
    print(
        json.dumps(
            {
                "ok": True,
                "flashed": True,
                "port": port,
                "running": st["running"],
                "url": st["url"],
            }
        )
    )
    return 0


def cmd_open(_args: argparse.Namespace) -> int:
    st = status_dict()
    if not st["running"]:
        rc = cmd_start(_args)
        if rc != 0:
            return rc
        st = status_dict()
    open_url(st["url"])
    print_status()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage the CYD TD deploy server and Vite editor.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, handler in (
        ("start", cmd_start),
        ("stop", cmd_stop),
        ("status", cmd_status),
        ("setup", cmd_setup),
        ("open", cmd_open),
        ("flash", cmd_flash),
    ):
        sub.add_parser(name, help=handler.__doc__ or name).set_defaults(func=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
