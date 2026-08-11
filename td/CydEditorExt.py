"""TouchDesigner Extension: bridge CYD_TD_Controller Editor pulses to editor_ctl.py."""

import json
import os
import subprocess
import sys


class CydEditorExt:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp

    def _set_setupstatus(self, msg: str) -> None:
        par = getattr(self.ownerComp.par, "Setupstatus", None)
        if par is not None:
            par.val = (msg or "")[:500]

    def _project_dir(self) -> str:
        par = getattr(self.ownerComp.par, "Projectdir", None)
        if par is None:
            self._set_setupstatus("error: Projectdir parameter missing")
            return ""

        raw = par.eval()
        if raw is None:
            self._set_setupstatus("error: set Projectdir to repo root (editor_ctl.py)")
            return ""

        path = str(raw).strip().strip('"').strip("'")
        if not path:
            self._set_setupstatus("error: set Projectdir to repo root (editor_ctl.py)")
            return ""

        ctl = os.path.join(path, "editor_ctl.py")
        if not os.path.isfile(ctl):
            self._set_setupstatus(f"error: editor_ctl.py not found in {path}")
            return ""

        return path

    def _format_status(self, cmd: str, stdout: str, stderr: str, returncode: int) -> str:
        stdout = (stdout or "").strip()
        stderr = (stderr or "").strip()

        if cmd in ("start", "stop", "status", "open"):
            try:
                data = json.loads(stdout)
            except (json.JSONDecodeError, TypeError):
                data = None
            if isinstance(data, dict):
                running = bool(data.get("running"))
                base = "running" if running else "stopped"
                url = data.get("url")
                if url:
                    return f"{base} ({url})"
                return base

        if returncode != 0:
            snippet = stderr or stdout or f"exit {returncode}"
            return f"error: {snippet[:200]}"

        if stdout:
            return stdout[:200]
        return "stopped" if cmd == "stop" else "ok"

    def _run_ctl(self, cmd: str) -> str:
        project_dir = self._project_dir()
        if not project_dir:
            par = getattr(self.ownerComp.par, "Setupstatus", None)
            return par.eval() if par is not None else "error"

        ctl_path = os.path.join(project_dir, "editor_ctl.py")
        self._set_setupstatus(f"running {cmd}...")

        try:
            result = subprocess.run(
                [sys.executable, ctl_path, cmd],
                capture_output=True,
                text=True,
                timeout=60,
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

        status = self._format_status(cmd, result.stdout, result.stderr, result.returncode)
        self._set_setupstatus(status)
        return status

    def StartSetup(self):
        return self._run_ctl("start")

    def StopSetup(self):
        return self._run_ctl("stop")

    def EditCyd(self):
        return self._run_ctl("open")

    def RefreshStatus(self):
        return self._run_ctl("status")
