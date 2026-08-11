# Parameter Execute DAT callbacks (parent COMP custom pars, ops='..')


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
