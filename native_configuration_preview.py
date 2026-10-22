"""Read native values around an isolated, ordinary configuration transaction."""
def values(v,req):
    from native_study_worker import parameter_ids
    from native_worker import parameter
    from native_parameter_units import unit
    from native_tools import one
    if req.get('configuration')=='preset':
        group=one(req.get('group'),v.GetVarPresetGroups());one(req.get('setting'),v.GetVarPresetSettings(group));groups=[group]
    elif req.get('configuration')=='mode':groups=list(v.ModeGetAllGroups(one(req.get('id'),v.GetAllModes())))
    else:groups=[]
    selected={p for group in groups for p in v.GetVarPresetParmIDs(group)}
    out=[]
    for pid in sorted(parameter_ids(v)):
        if not v.ValidParm(pid):continue
        p=parameter(v,pid);owner=v.GetParmContainer(pid)
        identity='@native:user-parameters' if owner==v.GetUserParmContainer() else owner
        out.append(dict(owner=identity,group=p['rawGroup'],name=p['name'],id=pid,label=' / '.join([v.GetContainerName(owner),p['rawGroup'],p.get('label',p['name'])]),value=v.GetParmVal(pid),unit=unit(p),selected=pid in selected,computed=p['rawGroup']=='BBox' or p.get('displayReadOnly',False)))
    return out


def difference(before,after):
    key=lambda p:(p['owner'],p['group'],p['name'])
    old={key(p):p for p in before};new={key(p):p for p in after};changes=[]
    for identity in sorted(old.keys()|new.keys()):
        a,b=old.get(identity),new.get(identity)
        if a is not None and b is not None and a['value']==b['value']:continue
        p=b or a
        changes.append(dict(label=p['label'],owner=p['owner'],group=p['group'],name=p['name'],idBefore=a['id'] if a else None,idAfter=b['id'] if b else None,before=a['value'] if a else None,after=b['value'] if b else None,unit=p['unit'],selected=bool((a or {}).get('selected') or (b or {}).get('selected')),computed=p.get('computed',False),status='changed' if a and b else 'added' if b else 'removed'))
    return sorted(changes,key=lambda p:(not p['selected'],p['computed'],p['label'],p['owner'],p['name']))
