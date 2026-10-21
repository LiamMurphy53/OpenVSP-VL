"""Named assembly connection inputs; points and constraint presets stay native."""
import ctypes,json,math


def copies(v,pid):
    from native_preview import adapter
    from native_tools import one
    one(pid,[p for s in v.GetFeaStructIDVec() for p in v.GetFeaPartIDVec(s) if v.GetFeaPartType(p)==v.FEA_FIX_POINT],'Choose an existing structural fixed point.')
    _,engine,bridge=adapter(v);fn=bridge.studio_fixedpoint_copies
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
    result=json.loads(fn(engine,pid.encode()))
    if isinstance(result,dict):raise ValueError(result.get('error','Native fixed-point copies unavailable.'))
    if any(len(p)!=3 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in p) for p in result):raise ValueError('OpenVSP returned undefined fixed-point coordinates.')
    return result


def annotate(v,p):
    if p['rawGroup']!='Connection':return
    labels={'ConMode':'Connection constraint mode','Constraints':'Custom constrained degrees of freedom','StartFixPtSurfIndex':'Start fixed-point copy','EndFixPtSurfIndex':'End fixed-point copy'}
    if p['name'] in labels:p['label']=labels[p['name']]
    if p['name']=='ConMode':p['choices']=[dict(value=getattr(v,n),label=l) for n,l in [('FEA_BCM_USER','Custom degrees of freedom'),('FEA_BCM_ALL','Rigid · all six degrees'),('FEA_BCM_PIN','Pinned · translations')]]
    if p['name']=='Constraints':
        labels=['Move X','Move Y','Move Z','Rotate X','Rotate Y','Rotate Z']
        p['choices']=[dict(value=mask,label=', '.join(label for i,label in enumerate(labels) if mask&(1<<i)) or 'No constrained degrees') for mask in range(64)]
    if p['name'] in ('StartFixPtSurfIndex','EndFixPtSurfIndex'):
        p['min']=0;p['studyNote']='Copy indices are checked against this case’s original native fixed-point copies after geometry changes. Geometry axes can change the available copy count.'
    if p['name']=='Constraints' and v.GetParmVal(v.FindParm(v.GetParmContainer(p['id']),'ConMode','Connection'))!=v.FEA_BCM_USER:
        p.update(active=False,readOnly=True,editable=False,readOnlyReason='OpenVSP calculates the constraint mask from the selected connection mode.')


def validate_parameter(v,pid,value=None):
    if v.GetParmGroupName(pid)=='Connection' and v.GetParmName(pid)=='Constraints' and v.GetParmVal(v.FindParm(v.GetParmContainer(pid),'ConMode','Connection'))!=v.FEA_BCM_USER:
        raise ValueError('Choose Custom degrees of freedom before editing the connection constraints.')
    if value is not None and v.GetParmGroupName(pid)=='Connection' and v.GetParmName(pid) in ('StartFixPtSurfIndex','EndFixPtSurfIndex'):
        from native_references import references
        side='Start' if v.GetParmName(pid).startswith('Start') else 'End'
        point=references(v).get(v.GetParmContainer(pid),{}).get(side+'FixPtID','')
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or int(value)!=value or value not in range(len(copies(v,point))):raise ValueError('Choose an available native '+side.lower()+' fixed-point copy for this case.')


def study_metadata(v):
    out={}
    for aid in v.GetFeaAssemblyIDVec():
        for i in range(v.NumFeaAssemblyConnections(aid)):
            cid=v.GetFeaAssemblyConnectionID(aid,i)
            pid=v.FindParm(cid,'Constraints','Connection');controller=v.FindParm(cid,'ConMode','Connection')
            out[pid]=dict(conditions=[dict(parameter=controller,values=[v.FEA_BCM_USER],label='Connection constraint mode · Custom degrees of freedom')],limitControllers=[])
    return out


def study_priority(v,pid):
    if v.GetParmGroupName(pid)!='Connection':return None
    return -10 if v.GetParmName(pid)=='ConMode' else 20


def owner_label(v,cid):
    for aid in v.GetFeaAssemblyIDVec():
        for i in range(v.NumFeaAssemblyConnections(aid)):
            if v.GetFeaAssemblyConnectionID(aid,i)==cid:return v.GetFeaAssemblyName(aid)+' / Connection '+str(i+1)
    return ''


def catalog(v,aid):
    out=[]
    for sid in v.GetFeaAssemblyStructureIDVec(aid):
        geom=v.GetFeaStructParentGeomID(sid);name=v.GetFeaStructName(geom,v.GetFeaStructIndex(sid))
        for pid in v.GetFeaPartIDVec(sid):
            if v.GetFeaPartType(pid)==v.FEA_FIX_POINT:out.append(dict(structure=sid,id=pid,label=name+' / '+v.GetFeaPartName(pid),copies=copies(v,pid)))
    return out


def edit(v,r):
    from native_tools import one
    import native_references,xml.etree.ElementTree as ET,os
    aid=one(r['assembly'],v.GetFeaAssemblyIDVec());cid=one(r['id'],[v.GetFeaAssemblyConnectionID(aid,i) for i in range(v.NumFeaAssemblyConnections(aid))])
    ends=[]
    for side in ('start','end'):
        sid=one(r[side+'Structure'],v.GetFeaAssemblyStructureIDVec(aid));pid=one(r[side+'Point'],[p for p in v.GetFeaPartIDVec(sid) if v.GetFeaPartType(p)==v.FEA_FIX_POINT]);index=one(r[side+'Index'],range(len(copies(v,pid))),'Choose an available native fixed-point copy.')
        ends.append((sid,pid,index))
    if ends[0]==ends[1]:raise ValueError('Choose two different fixed-point copies.')
    for side,(_,_,index) in zip(('Start','End'),ends):v.SetParmVal(v.FindParm(cid,side+'FixPtSurfIndex','Connection'),index)
    filename=v.GetVSPFileName();path,tree=native_references.document(v)
    try:
        node=next(n for n in tree.findall('.//Connection') if n.findtext('ParmContainer/ID')==cid)
        for side,(sid,pid,_) in zip(('Start','End'),ends):
            for key,value in ((side+'StructID',sid),(side+'FixPtID',pid)):
                child=node.find(key)
                if child is None:child=ET.SubElement(node,key)
                child.text=value
        tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
    finally:path.unlink(missing_ok=True)
    raise native_references.ReloadRequired()


def connection_issues(v,aid,refs=None,points=None):
    """Check saved endpoints against current native member/copy topology."""
    if refs is None:
        from native_references import references
        refs=references(v)
    if points is None:
        from native_part_controls import refresh
        for sid in v.GetFeaAssemblyStructureIDVec(aid):refresh(v,structure=sid)
        points=catalog(v,aid)
    available={(p['structure'],p['id']):p for p in points}
    issues=[]
    for i in range(v.NumFeaAssemblyConnections(aid)):
        cid=v.GetFeaAssemblyConnectionID(aid,i)
        for side in ('Start','End'):
            saved=refs.get(cid,{})
            point=available.get((saved.get(side+'StructID'),saved.get(side+'FixPtID')))
            index=v.GetParmVal(v.FindParm(cid,side+'FixPtSurfIndex','Connection'))
            if point is None:
                message=f'Connection {i+1}: {side.lower()} fixed point is unavailable in this assembly.'
            elif index not in range(len(point['copies'])):
                message=f'Connection {i+1}: {side.lower()} copy {int(index)} is unavailable for {point["label"]} ({len(point["copies"])} current copies).'
            else:continue
            issues.append(dict(connection=cid,index=i,side=side.lower(),message=message))
    return issues


def validate_assembly(v,aid):
    issues=inspect_assembly(v,aid)
    if issues:
        raise ValueError(' '.join(i['message'] for i in issues)+' Repair the endpoints in Modeling tools → Assemblies before meshing.')


def inspect_assembly(v,aid):
    # Structural refresh changes native follower values and meshing state.
    # Evaluate the saved endpoints in a separate original-engine process.
    from pathlib import Path
    import uuid,native_ngon
    from native_service import invoke
    folder=Path.cwd()/('connection-preflight-'+uuid.uuid4().hex);folder.mkdir()
    model=folder/'aircraft.vsp3';filename=v.GetVSPFileName()
    # Original serialization regenerates assembly output names. Keep caller
    # destinations intact; the child uses only the snapshot.
    outputs={(a,i):v.GetFeaAssemblyFileName(a,i) for a in v.GetFeaAssemblyIDVec() for i in range(v.FEA_NUM_FILE_NAMES)}
    try:native_ngon.write(v,model)
    finally:
        v.SetVSP3FileName(filename)
        for (a,i),name in outputs.items():v.SetFeaAssemblyFileName(a,i,name)
    return invoke(dict(action='assembly-connection-preflight',assembly=aid),model,folder)['issues']
