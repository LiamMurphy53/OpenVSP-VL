"""Original measurement refresh, calculated fields and coordinate bases."""
import ctypes,json
OUTPUTS={'ruler':{'Distance','DeltaX','DeltaY','DeltaZ'},'probe':{'X','Y','Z','NX','NY','NZ','Kmax','Kmin','Kmean','KGaussian'},'rst-probe':{'X','Y','Z'},'protractor':{'Theta','ThetaX','ThetaY','ThetaZ'}}
LABELS={'MidU':'Middle U (0–1)','MidW':'Middle W (0–1)','MidIndx':'Middle surface index','OriginU':'Start U (0–1)','OriginW':'Start W (0–1)','OriginR':'Volume R (0–1)','OriginS':'Volume S (0–1)','OriginT':'Volume T (0–1)','OriginL':'Volume L (0–1)','OriginM':'Volume M (0–1)','OriginN':'Volume N (0–1)','EndU':'End U (0–1)','EndW':'End W (0–1)','OriginIndx':'Start surface index','EndIndx':'End surface index','LMNFlag':'Volume coordinate basis','Component':'Distance component','Precision':'Displayed decimal places','Visible':'Show measurement','Len':'Probe marker length (model units)','NX':'Normal X','NY':'Normal Y','NZ':'Normal Z','Kmax':'Maximum principal curvature','Kmin':'Minimum principal curvature','Kmean':'Mean curvature','KGaussian':'Gaussian curvature','Distance':'Native distance (model units)'}


def owners(v):return [('ruler',list(v.GetAllRulers())),('probe',list(v.GetAllProbes())),('rst-probe',list(v.GetAllRSTProbes())),('protractor',list(v.GetAllProtractors()))]


def refresh(v):
    if not any(ids for _,ids in owners(v)):return
    import native_preview
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_measurements_update;fn.argtypes=[ctypes.c_char_p];fn.restype=ctypes.c_char_p
    data=json.loads(fn(engine))
    if data.get('error'):raise ValueError(data['error'])


def reason(v,pid):
    if v.GetParmGroupName(pid)!='Measure':return ''
    owner=v.GetParmContainer(pid);kind=next((kind for kind,ids in owners(v) if owner in ids),None);name=v.GetParmName(pid)
    if kind is None:return ''
    if name in OUTPUTS[kind]:return 'Calculated by the original OpenVSP measurement manager.'
    if kind=='rst-probe' and name in ('OriginR','OriginS','OriginT','OriginL','OriginM','OriginN'):
        lmn=bool(v.GetParmVal(v.FindParm(owner,'LMNFlag','Measure')))
        if name in (('OriginR','OriginS','OriginT') if lmn else ('OriginL','OriginM','OriginN')):return 'Calculated by OpenVSP from the selected volume coordinate basis.'
    return ''


def annotate(v,p):
    if p['rawGroup']!='Measure':return
    if p['name'] in LABELS:p['label']=LABELS[p['name']]
    if p['name']=='LMNFlag':p['choices']=[dict(value=0,label='R / S / T'),dict(value=1,label='L / M / N')]
    if p['name'] in ('Theta','ThetaX','ThetaY','ThetaZ'):p['label']={'Theta':'Native angle (degrees)','ThetaX':'YZ projected angle (degrees)','ThetaY':'XZ projected angle (degrees)','ThetaZ':'XY projected angle (degrees)'}[p['name']]
    if p['name']=='Component' and v.GetParmContainer(p['id']) in v.GetAllProtractors():
        p['label']='Angle projection';p['choices']=[dict(value=getattr(v,n),label=l) for n,l in [('X_DIR','YZ plane'),('Y_DIR','XZ plane'),('Z_DIR','XY plane'),('ALL_DIR','Full 3D angle')]]
    elif p['name']=='Component':p['choices']=[dict(value=getattr(v,n),label=l) for n,l in [('X_DIR','X distance'),('Y_DIR','Y distance'),('Z_DIR','Z distance'),('ALL_DIR','Full 3D distance')]]
    why=reason(v,p['id'])
    if why:p.update(active=False,editable=False,readOnly=True,readOnlyReason=why)


def validate_parameter(v,pid):
    why=reason(v,pid)
    if why:raise ValueError(why)


def study_metadata(v):
    out={}
    for cid in v.GetAllRSTProbes():
        basis=v.FindParm(cid,'LMNFlag','Measure')
        for name,mode in [('OriginR',0),('OriginS',0),('OriginT',0),('OriginL',1),('OriginM',1),('OriginN',1)]:out[v.FindParm(cid,name,'Measure')]=dict(conditions=[dict(parameter=basis,values=[mode],label='Volume coordinate basis')],limitControllers=[])
    return out


def references(v):
    import native_references
    ids={cid for _,owners_ in owners(v) for cid in owners_}
    if not ids:return {}
    path,tree=native_references.document(v)
    try:
        return {cid:dict(originGeom=node.findtext('ParmContainer/OriginGeomID',''),endGeom=node.findtext('ParmContainer/EndGeomID',''),midGeom=node.findtext('ParmContainer/MidGeomID','')) for node in tree.iter() if (cid:=node.findtext('ParmContainer/ID')) in ids}
    finally:path.unlink(missing_ok=True)


def edit(v,r):
    from native_tools import one,name
    from native_fit import surface
    ids={cid:kind for kind,items in owners(v) for cid in items};cid=one(r.get('id'),ids,'Choose an existing saved measurement.')
    if r['operation']=='measurement-rename':v.SetContainerName(cid,name(r['name']));return
    side=one(r.get('side'),['start','mid','end'])
    if side=='end' and ids[cid] not in ('ruler','protractor'):raise ValueError('Only a ruler or protractor has an end surface.')
    if side=='mid' and ids[cid]!='protractor':raise ValueError('Only a protractor has a middle surface.')
    g,index=surface(v,r);pid=v.FindParm(cid,{'start':'OriginIndx','mid':'MidIndx','end':'EndIndx'}[side],'Measure');v.SetParmVal(pid,index)
    import native_references,os
    filename=v.GetVSPFileName();path,tree=native_references.document(v)
    try:
        nodes=[n.find('ParmContainer') for n in tree.iter() if n.findtext('ParmContainer/ID')==cid]
        if len(nodes)!=1:raise ValueError('The saved measurement reference is unavailable.')
        node=nodes[0].find({'start':'OriginGeomID','mid':'MidGeomID','end':'EndGeomID'}[side])
        if node is None:raise ValueError('The native measurement reference field is unavailable.')
        node.text=g;tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
    finally:path.unlink(missing_ok=True)
    raise native_references.ReloadRequired(dict(action='mutate',operation='measurement-refresh'))


def preview(v):
    refresh(v)
    import native_preview
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_measurement_drawing;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];fn.restype=ctypes.c_char_p
    parts=[]
    for code,(kind,ids) in enumerate(owners(v)):
        for cid in ids:
            objects=json.loads(fn(engine,cid.encode(),code))
            if isinstance(objects,dict):raise ValueError(objects.get('error','Native measurement drawing unavailable.'))
            parts.append(dict(id=cid,index=len(parts),name=v.GetContainerName(cid)+' · '+kind,objects=objects,kind=kind))
    return dict(parts=parts,warnings=[],showContext=True,filename='Native saved measurements',displayNote='Anchors and protractor arc points come from original OpenVSP drawing objects. Connecting lines show those native anchors; ruler label offsets and probe marker length are presentation settings. Measurement values remain original engine outputs.')


def guard_geometry_delete(v,gid):
    removed={gid};pending=[gid]
    while pending:
        for child in v.GetGeomChildren(pending.pop()):
            if child not in removed:removed.add(child);pending.append(child)
    refs=references(v);users=[]
    for kind,ids in owners(v):
        for cid in ids:
            used=[label for key,label in [('originGeom','start'),('midGeom','middle'),('endGeom','end')] if refs.get(cid,{}).get(key) in removed]
            if used:users.append(v.GetContainerName(cid)+' ('+kind+' · '+', '.join(used)+')')
    if users:raise ValueError('Reassign or remove these saved measurements before deleting this component and its children: '+ '; '.join(users))
