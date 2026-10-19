"""Prevent saved mode configurations from losing their preset definitions."""


def users(v,group,setting=None):
    result=[]
    for mode in v.GetAllModes():
        groups=list(v.ModeGetAllGroups(mode));settings=list(v.ModeGetAllSettings(mode))
        if any(g==group and (setting is None or i<len(settings) and settings[i]==setting) for i,g in enumerate(groups)):
            result.append(dict(id=mode,name=v.GetModeName(mode)))
    return result


def guard_delete(v,group,setting=None):
    modes=users(v,group,setting)
    if modes:
        names=', '.join(m['name'] for m in modes)
        raise ValueError('This '+('setting' if setting is not None else 'preset')+' is used by modes: '+names+'. Remove the included setting from those modes in Configurations before deleting it.')
