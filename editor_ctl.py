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
PID_FILE = os.path.join(REPO_ROOT, ".editor.pids")
LOG_DIR = os.path.join(REPO_ROOT, ".editor_logs")
SERVER_LOG = os.path.join(LOG_DIR, "server.log")
VITE_LOG = os.path.join(LOG_DIR, "vite.log")
SERVER_SCRIPT = os.path.join(REPO_ROOT, "server.py")
UI_EDITOR_DIR = os.path.join(REPO_ROOT, "ui-editor")
SERVER_PORT = 3737
VITE_PORT = 5173
EDITOR_URL = f"http://localhost:{VITE_PORT}"
START_POLL_TIMEOUT = 8.0
START_POLL_INTERVAL = 0.25


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


def status_dict() -> dict:
    srv = server_up()
    ed = editor_up()
    return {
        "running": srv and ed,
        "server": srv,
        "editor": ed,
        "url": EDITOR_URL,
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


def kill_port_listeners(port: int) -> None:
    lsof = shutil.which("lsof")
    if not lsof:
        return
    try:
        result = subprocess.run(
            [lsof, f"-ti:{port}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
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


def spawn_server() -> subprocess.Popen:
    ensure_log_dir()
    log = open(SERVER_LOG, "a", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, SERVER_SCRIPT],
        cwd=REPO_ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def spawn_vite() -> subprocess.Popen:
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm not found in PATH; install Node.js/npm to run the editor")

    ensure_log_dir()
    log = open(VITE_LOG, "a", encoding="utf-8")
    return subprocess.Popen(
        [npm, "run", "dev"],
        cwd=UI_EDITOR_DIR,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


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


def cmd_start(_args: argparse.Namespace) -> int:
    st = status_dict()
    if st["running"]:
        print_status()
        return 0

    server_proc = None
    vite_proc = None

    if not st["server"]:
        server_proc = spawn_server()
    if not st["editor"]:
        try:
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
        ("open", cmd_open),
    ):
        sub.add_parser(name, help=handler.__doc__ or name).set_defaults(func=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
