"""Structural sizing driver metadata; native GridDensity owns all formulas."""
PAIRS={'BaseAbsRel':('BaseLen','BaseLenFrac'),'MinAbsRel':('MinLen','MinFrac'),'MaxGapAbsRel':('MaxGap','MaxGapFrac')}
LABELS={'BaseAbsRel':'Maximum edge length basis','BaseLen':'Maximum edge length (native units)','BaseLenFrac':'Maximum edge length fraction','MinAbsRel':'Minimum edge length basis','MinLen':'Minimum edge length (native units)','MinFrac':'Minimum edge length fraction','MaxGapAbsRel':'Surface gap basis','MaxGap':'Surface gap (native units)','MaxGapFrac':'Surface gap fraction','GrowRatio':'Mesh growth ratio','RigorLimit':'Rigorous growth limiting','NCircSeg':'Circle segmentation target'}


def reason(v,pid):
    if v.GetParmGroupName(pid)!='FEAGridDensity':return ''
    name=v.GetParmName(pid);owner=v.GetParmContainer(pid)
    for controller,(absolute,relative) in PAIRS.items():
        if name in (absolute,relative):
            basis=v.GetParmVal(v.FindParm(owner,controller,'FEAGridDensity'))
            if name==(relative if basis==v.ABS else absolute):return 'OpenVSP calculates this linked sizing value from the selected absolute or relative basis.'
    return ''


def annotate(v,p):
    if p['rawGroup']!='FEAGridDensity':return
    if p['name'] in LABELS:p['label']=LABELS[p['name']]
    if p['name'] in PAIRS:p['choices']=[dict(value=v.ABS,label='Absolute · native length'),dict(value=v.REL,label='Relative · fraction')]
    why=reason(v,p['id'])
    if why:p.update(active=False,editable=False,readOnly=True,readOnlyReason=why)


def validate_parameter(v,pid):
    why=reason(v,pid)
    if why:raise ValueError(why)


def refresh(v,pid):
    if v.GetParmGroupName(pid)!='FEAGridDensity':return
    sid=next((s for s in v.GetFeaStructIDVec() if pid in v.FindContainerParmIDs(s)),None)
    if sid:
        import native_part_controls
        native_part_controls.refresh(v,sid)


def study_metadata(v):
    out={}
    for sid in v.GetFeaStructIDVec():
        fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(sid) if v.GetParmGroupName(p)=='FEAGridDensity'}
        for controller,(absolute,relative) in PAIRS.items():
            for name,mode in ((absolute,v.ABS),(relative,v.REL)):
                out[fields[name]]=dict(conditions=[dict(parameter=fields[controller],values=[mode],label=LABELS[controller])],limitControllers=[])
    return out


def study_priority(v,pid):
    if v.GetParmGroupName(pid)!='FEAGridDensity':return None
    name=v.GetParmName(pid)
    return -12 if name in PAIRS else 20 if name in ('BaseLen','BaseLenFrac') else 30
