"""Native saved CFD density modes; GridDensity performs every conversion."""
import ctypes,json
PAIRS={'BaseAbsRel':('BaseLen','BaseLenFrac'),'MinAbsRel':('MinLen','MinFrac'),'MaxGapAbsRel':('MaxGap','MaxGapFrac'),'FarAbsRel':('MaxFar','FarFrac'),'FarMaxGapAbsRel':('MaxFarGap','FarMaxGapFrac')}
LABELS={'BaseAbsRel':'Maximum edge length basis','BaseLen':'Maximum edge length (model units)','BaseLenFrac':'Maximum edge length fraction','MinAbsRel':'Minimum edge length basis','MinLen':'Minimum edge length (model units)','MinFrac':'Minimum edge length fraction','MaxGapAbsRel':'Surface gap basis','MaxGap':'Surface gap (model units)','MaxGapFrac':'Surface gap fraction','FarAbsRel':'Far-field maximum edge basis','MaxFar':'Far-field maximum edge (model units)','FarFrac':'Far-field edge fraction','FarMaxGapAbsRel':'Far-field gap basis','MaxFarGap':'Far-field gap (model units)','FarMaxGapFrac':'Far-field gap fraction','NCircSeg':'Circle segmentation target','FarNCircSeg':'Far-field circle target','GrowRatio':'Mesh growth ratio','RigorLimit':'Rigorous growth limiting'}


def refresh(v):
    if not v.FindGeoms():return
    from native_preview import adapter
    cid=v.FindContainer('CFDGridDensity',0)
    _,engine,bridge=adapter(v);fn=bridge.studio_cfd_density_update;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
    result=json.loads(fn(engine,cid.encode()))
    if result.get('error'):raise ValueError(result['error'])


def reason(v,pid):
    if v.GetParmGroupName(pid)!='CFDGridDensity' or v.GetParmContainer(pid)!=v.FindContainer('CFDGridDensity',0):return ''
    owner=v.GetParmContainer(pid);name=v.GetParmName(pid)
    for controller,(absolute,relative) in PAIRS.items():
        if name in (absolute,relative):
            mode=v.GetParmVal(v.FindParm(owner,controller,'CFDGridDensity'))
            if name==(relative if mode==v.ABS else absolute):return 'OpenVSP calculates this linked CFD density value from the saved sizing basis.'
    return ''


def annotate(v,p):
    if p['rawGroup']!='CFDGridDensity' or v.GetParmContainer(p['id'])!=v.FindContainer('CFDGridDensity',0):return
    if p['name'] in LABELS:p['label']=LABELS[p['name']]
    if p['name'] in PAIRS:p['choices']=[dict(value=v.ABS,label='Absolute · model units'),dict(value=v.REL,label='Relative · fraction')]
    why=reason(v,p['id'])
    if why:p.update(active=False,editable=False,readOnly=True,readOnlyReason=why)


def validate_parameter(v,pid):
    why=reason(v,pid)
    if why:raise ValueError(why)


def study_metadata(v):
    owner=v.FindContainer('CFDGridDensity',0);fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(owner)};out={}
    for controller,(absolute,relative) in PAIRS.items():
        for name,mode in ((absolute,v.ABS),(relative,v.REL)):out[fields[name]]=dict(conditions=[dict(parameter=fields[controller],values=[mode],label=LABELS[controller])],limitControllers=[])
    return out


def study_priority(v,pid):
    if v.GetParmGroupName(pid)!='CFDGridDensity' or v.GetParmContainer(pid)!=v.FindContainer('CFDGridDensity',0):return None
    name=v.GetParmName(pid)
    return -12 if name in PAIRS else 20 if name in ('BaseLen','BaseLenFrac','MaxFar','FarFrac') else 30
