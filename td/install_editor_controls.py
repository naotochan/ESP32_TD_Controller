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
'''

_EMBEDDED_PAREXEC_EDITOR = r'''# Parameter Execute DAT callbacks (parent COMP custom pars, ops='..')


def onPulse(par):
    comp = parent()
    ext = comp.ext.CydEditorExt
    name = par.name

    if name == "Startsetup":
        ext.StartSetup()
    elif name == "Stopsetup":
        ext.StopSetup()
    elif name == "Editcyd":
        ext.EditCyd()
    elif name == "Refreshstatus":
        ext.RefreshStatus()
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
- Projectdir — git repo root (folder containing editor_ctl.py)
- Start Setup — editor_ctl start (server.py + Vite)
- Stop Setup — editor_ctl stop
- Edit CYD — editor_ctl open (browser)
- Refresh Status — editor_ctl status → Setupstatus
- Setupstatus — read-only status (running/stopped/error)

Internal operators (minimal build)
----------------------------------
oscin -> null_all -> out_all ; null_send -> oscout

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


def _ensure_editor_page(comp, repo_root):
    page = _find_custom_page(comp, "Editor")
    if page is None:
        page = comp.appendCustomPage("Editor")

    if not hasattr(comp.par, "Projectdir"):
        append_folder = getattr(page, "appendFolder", None)
        if append_folder:
            par = append_folder("Projectdir", label="Project Dir")
        else:
            par = page.appendFile("Projectdir", label="Project Dir")
        hint = repo_root or ""
        if hint:
            par.val = hint
            print(f"Set Projectdir default: {hint}")

    pulses = (
        ("Startsetup", "Start Setup"),
        ("Stopsetup", "Stop Setup"),
        ("Editcyd", "Edit CYD"),
        ("Refreshstatus", "Refresh Status"),
    )
    for name, label in pulses:
        if not hasattr(comp.par, name):
            page.appendPulse(name, label=label)

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
    dat.view = False
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
    if hasattr(parexec.par, "custom"):
        parexec.par.custom = True
    if hasattr(parexec.par, "pars"):
        parexec.par.pars = "*"
    if hasattr(parexec.par, "builtin"):
        parexec.par.builtin = False

    return parexec


def _bind_extension(comp, ext_dat):
    """Attach CydEditorExt Text DAT to COMP extensions (TD version tolerant)."""
    bound = False

    for par_name in ("ext0object", "Ext0object", "extension1object"):
        par = getattr(comp.par, par_name, None)
        if par is None:
            continue
        try:
            par.val = ext_dat
            bound = True
            print(f"Set {par_name} -> ext_CydEditorExt")
            break
        except Exception as exc:
            print(f"Note: {par_name} assignment failed: {exc}")

    if not bound:
        for par_name in ("ext0", "Ext0"):
            par = getattr(comp.par, par_name, None)
            if par is None:
                continue
            try:
                par.val = ext_dat
                bound = True
                print(f"Set {par_name} -> ext_CydEditorExt")
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
        print(
            "WARNING: could not auto-bind extension DAT. "
            "Manually set Extensions → Extension 0 Object to ext_CydEditorExt, "
            "then Re-Init Extensions."
        )


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

    try:
        comp.save(tox_path)
        print(f"SUCCESS: saved {tox_path}")
    except Exception as exc:
        print(f"FAIL: comp.save failed: {exc}")
        return False

    print("Done. Set Editor → Projectdir to repo root, then use Start Setup / Edit CYD.")
    return True


# When executed outside TouchDesigner (no `op` builtin), exit with message.
if "op" not in dir():
    print("install_editor_controls.py must be run inside TouchDesigner (Textport or Text DAT).")
    print("Example: exec(open('<repo>/td/install_editor_controls.py').read())")
    if __name__ == "__main__":
        sys.exit(1)
else:
    run()
