"""Viewer text/color helpers for CYD_TD_Controller COMP node viewer."""

VIEWER_FONT = "Arial"
TEXT_FORMAT = "rgba8fixed"


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.lstrip("#")
    return (
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
    )


def _set_top_color(top, hex_color: str) -> None:
    r, g, b = _hex_to_rgb(hex_color)
    if hasattr(top.par, "colorr"):
        top.par.colorr = r
        top.par.colorg = g
        top.par.colorb = b
    else:
        top.par.fontcolorr = r
        top.par.fontcolorg = g
        top.par.fontcolorb = b


def _par_eval_str(par) -> str:
    try:
        raw = par.eval() if hasattr(par, "eval") else par.val
        return str(raw) if raw is not None else ""
    except Exception:
        return ""


def _set_par_val_if_wrong(par, value) -> None:
    try:
        current = _par_eval_str(par)
        target = str(value)
        if current != target:
            par.val = value
    except Exception:
        pass


def heal(comp) -> None:
    """Ensure viewer_* text/composite TOPs have readable font/format/size (do NOT touch swaporder)."""
    for name in ("viewer_title", "viewer_state", "viewer_meta"):
        top = comp.op(name)
        if top is None:
            continue
        for attr in ("font", "fontface"):
            par = getattr(top.par, attr, None)
            if par is not None:
                _set_par_val_if_wrong(par, VIEWER_FONT)
                break
        fmt = getattr(top.par, "format", None)
        if fmt is not None:
            _set_par_val_if_wrong(fmt, TEXT_FORMAT)
    for name in ("viewer_layer1", "viewer_layer2", "viewer_layer3"):
        comp_op = comp.op(name)
        if comp_op is None:
            continue
        operand = getattr(comp_op.par, "operand", None)
        if operand is not None:
            for val in ("over", "Over"):
                try:
                    if _par_eval_str(operand).lower() != val.lower():
                        operand.val = val
                    break
                except Exception:
                    continue
        size = getattr(comp_op.par, "size", None)
        if size is not None:
            for val in ("input1", "Input1"):
                try:
                    if _par_eval_str(size).lower() != val.lower():
                        size.val = val
                    break
                except Exception:
                    continue
        fmt = getattr(comp_op.par, "format", None)
        if fmt is not None:
            _set_par_val_if_wrong(fmt, TEXT_FORMAT)


def apply(comp, *, running: bool, version: str) -> None:
    """Set CYD EDITOR / RUNNING|STOPPED / meta text and colors on viewer_* TOPs. Calls heal first."""
    bg_top = comp.op("viewer_bg")
    title_top = comp.op("viewer_title")
    state_top = comp.op("viewer_state")
    meta_top = comp.op("viewer_meta")
    if not any((bg_top, title_top, state_top, meta_top)):
        return

    heal(comp)

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
        _set_top_color(bg_top, bg_hex)
    if title_top is not None:
        title_top.par.text = "CYD EDITOR"
        _set_top_color(title_top, muted_hex)
    if state_top is not None:
        state_top.par.text = state_text
        _set_top_color(state_top, state_hex)
    if meta_top is not None:
        meta_top.par.text = meta_text
        _set_top_color(meta_top, muted_hex)
