"""Human controls and presets delegate body and pose evaluation to OpenVSP."""
import ctypes,json

LENGTH=['mm','cm','m','in','ft','yd']
MASS=['g','kg','tonne','lbm','slug','lbf·s²/in']
LABELS={'LenUnit':'Human length units','MassUnit':'Human mass units','GenderFlag':'Body model','Stature_pct':'Stature percentile (0–1)','BMI_pct':'BMI percentile (0–1)','Age':'Age (years)','SitFrac':'Sitting height / stature','AutoDensity':'Calculate density from body mass','RLSym':'Match left pose to right','PresetPose':'Native pose preset','ShowSkelFlag':'Show native skeleton','Nod':'Head tilt','RotateHead':'Head turn','Back':'Back bend','Waist':'Waist bend'}
JOINTS={'Wrist':'Wrist bend','Forearm':'Forearm twist','Elbow':'Elbow bend','ShoulderABAD':'Shoulder sideways','ShoulderFE':'Shoulder forward/back','ShoulderIE':'Shoulder twist','HipABAD':'Hip sideways','HipFE':'Hip forward/back','Knee':'Knee bend','Ankle':'Ankle bend'}

def human(v,pid):
    return next((g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='HUMAN' and pid in v.GetGeomParmIDs(g)),None)

def reasons(v,gid,study=False):
    p={v.GetParmName(p):p for p in v.GetGeomParmIDs(gid)}
    result={p['Volume']:'Body volume is calculated by OpenVSP from its native mesh.'}
    if v.GetParmVal(p['AutoDensity']):result[p['Density']]='Density follows the native body mass and volume. Turn automatic density off to edit it.'
    if v.GetParmVal(p['RLSym']):
        result.update({p[n+'Lt']:'Left pose follows the right side. Turn off matching to edit it independently.' for n in JOINTS})
    if study:result[p['PresetPose']]='The preset selector requires Apply pose. Sweep the native joint angles instead.'
    return result

def read_only_reasons(v):
    return {p:reason for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='HUMAN' for p,reason in reasons(v,g,True).items()}

def validate_parameter(v,pid,study=False):
    g=human(v,pid)
    if g and pid in reasons(v,g,study):raise ValueError(reasons(v,g,study)[pid])

def native(v,gid,apply=False):
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='HUMAN':raise ValueError('Choose a native Human component.')
    import native_preview
    _,engine,bridge=native_preview.adapter(v);f=bridge.studio_human
    f.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_bool];f.restype=ctypes.c_char_p
    data=json.loads(f(engine,gid.encode(),apply))
    if 'error' in data:raise ValueError(data['error'])
    return data

def preset(v,req):
    gid=req['geom'];native(v,gid)
    if type(req.get('preset'))!=int or req['preset'] not in (0,1):raise ValueError('Choose standing or sitting.')
    v.SetParmVal(gid,'PresetPose','Pose',req['preset']);native(v,gid,True);v.Update()

def study_metadata(v,gid):
    """Describe native case dependencies without evaluating body math."""
    ids={v.GetParmName(p):p for p in v.GetGeomParmIDs(gid)}
    out={}
    for n,pid in ids.items():
        data={}
        if n.endswith('Lt') and n[:-2] in JOINTS:
            data['condition']=dict(parameter=ids['RLSym'],value=0,label=LABELS['RLSym']+' = Off')
        if n=='Density':data['condition']=dict(parameter=ids['AutoDensity'],value=0,label=LABELS['AutoDensity']+' = Off')
        if n=='Stature':data['limitControllers']=[ids['LenUnit']]
        units=[]
        if n in ('Stature','Volume','Density'):units.append(dict(parameter=ids['LenUnit'],label=LABELS['LenUnit']))
        if n in ('Mass','Density'):units.append(dict(parameter=ids['MassUnit'],label=LABELS['MassUnit']))
        if units:data['unitControllers']=units
        if data:out[pid]=data
    return out

def study_controlled(v,pid,axes):
    gid=human(v,pid)
    condition=study_metadata(v,gid).get(pid,{}).get('condition') if gid else None
    return bool(condition and any(isinstance(a,dict) and a.get('kind')=='parameter' and a.get('id')==condition['parameter'] and condition['value'] in a.get('values',[]) for a in axes))

def deferred_limits(v,pid,swept_ids):
    gid=human(v,pid)
    return bool(gid and set(study_metadata(v,gid).get(pid,{}).get('limitControllers',[])) & swept_ids)

def enrich(v,gid,params,eyes=True):
    p={p['name']:p for p in params};length=LENGTH[int(p['LenUnit']['value'])];mass=MASS[int(p['MassUnit']['value'])]
    choices={'LenUnit':list(enumerate(LENGTH)),'MassUnit':list(enumerate(MASS)),'GenderFlag':[(v.MALE,'Male'),(v.FEMALE,'Female')],'PresetPose':[(0,'Standing'),(1,'Sitting')]}
    locks=reasons(v,gid)
    for item in params:
        n=item['name']
        if n in LABELS:item['label']=LABELS[n]
        if n in choices:item['choices']=[dict(value=x,label=s) for x,s in choices[n]]
        if n in ('Stature','Mass','Volume'):item['label']={'Stature':f'Stature ({length})','Mass':f'Body mass ({mass})','Volume':f'Body volume ({length}³)'}[n]
        if n=='Density':item['label']=f'Body density ({mass}/{length}³)'
        if item['rawGroup']=='Pose' and n not in ('RLSym','PresetPose'):
            item['dimension']='angle'
            if n[-2:] in ('Lt','Rt'):item['label']=('Left ' if n.endswith('Lt') else 'Right ')+JOINTS[n[:-2]].lower()
        if item['id'] in locks:item.update(displayReadOnly=True,readOnlyReason=locks[item['id']])
    drawing=native(v,gid) if eyes else dict(eyes=[],skeleton=[])
    skeleton=[dict(o,label='Standing reference' if i==0 else 'Current pose') for i,o in enumerate(drawing['skeleton'])]
    return dict(lengthUnit=length,massUnit=mass,eyes=drawing['eyes'],skeleton=skeleton,skeletonFrame='Native body coordinates')
