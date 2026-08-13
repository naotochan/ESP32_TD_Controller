# Parameter Execute DAT — parent COMP custom pars, ops='..'


def onPulse(par):
    comp = parent()
    ext = comp.ext.CydEditorExt
    name = par.name

    if name == "Setup":
        ext.Setup()
    elif name == "Editcyd":
        ext.EditCyd()
    elif name == "Refreshstatus":
        ext.RefreshStatus()


def onValueChange(par, prev):
    if par.name == "Run":
        parent().ext.CydEditorExt.OnRunChanged(bool(par.eval()))
