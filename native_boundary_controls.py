"""Native structural boundary labels, preset updates and study dependencies."""
import ctypes,json


def ids(v):return [b for s in v.GetFeaStructIDVec() for b in v.GetFeaBCIDVec(s)]


def refresh(v,boundary=None):
    selected=[boundary] if boundary is not None else ids(v)
    if not selected:return
    from native_preview import adapter
    _,engine,bridge=adapter(v);fn=bridge.studio_boundary_update
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
    for bid in selected:
        if bid not in ids(v):raise ValueError('This structural boundary no longer exists.')
        result=json.loads(fn(engine,bid.encode()))
        if result.get('error'):raise ValueError(result['error'])


def annotate(v,p):
    if p['rawGroup']!='FeaBC':return
    name=p['name']
    if name=='Type':p.update(label='Boundary scope',choices=[dict(value=getattr(v,n),label=l) for n,l in [('FEA_BC_STRUCTURE','Whole structure'),('FEA_BC_PART','Structural part'),('FEA_BC_SUBSURF','Structural region')]])
    elif name=='ConMode':p.update(label='Boundary constraint mode',choices=[dict(value=getattr(v,n),label=l) for n,l in [('FEA_BCM_USER','Custom degrees of freedom'),('FEA_BCM_ALL','Clamped · all six degrees'),('FEA_BCM_PIN','Pinned · translations'),('FEA_BCM_SYMM','Symmetric'),('FEA_BCM_ASYMM','Antisymmetric')]])
    elif name=='Constraints':
        labels=['Move X','Move Y','Move Z','Rotate X','Rotate Y','Rotate Z']
        p.update(label='Custom constrained degrees of freedom',choices=[dict(value=mask,label=', '.join(label for i,label in enumerate(labels) if mask&(1<<i)) or 'No constrained degrees') for mask in range(64)])
        if v.GetParmVal(v.FindParm(v.GetParmContainer(p['id']),'ConMode','FeaBC'))!=v.FEA_BCM_USER:p.update(active=False,readOnly=True,editable=False,readOnlyReason='OpenVSP calculates these constraints from the boundary preset.')
    else:
        for axis in 'XYZ':
            labels={axis+'LTFlag':'Enable '+axis+' upper coordinate limit',axis+'LGFlag':'Enable '+axis+' lower coordinate limit',axis+'LTVal':axis+' maximum coordinate ('+coordinate_unit(v)+')',axis+'GTVal':axis+' minimum coordinate ('+coordinate_unit(v)+')'}
            if name in labels:p['label']=labels[name]
            if name in (axis+'LTVal',axis+'GTVal'):p['nativeUnit']=coordinate_unit(v)


def validate_parameter(v,pid):
    if v.GetParmGroupName(pid)=='FeaBC' and v.GetParmName(pid)=='Constraints' and v.GetParmVal(v.FindParm(v.GetParmContainer(pid),'ConMode','FeaBC'))!=v.FEA_BCM_USER:raise ValueError('Choose Custom degrees of freedom before editing boundary constraints.')


def study_metadata(v):
    return {v.FindParm(b,'Constraints','FeaBC'):dict(conditions=[dict(parameter=v.FindParm(b,'ConMode','FeaBC'),values=[v.FEA_BCM_USER],label='Boundary constraint mode · Custom degrees of freedom')],limitControllers=[]) for b in ids(v)}


def study_priority(v,pid):
    if v.GetParmGroupName(pid)!='FeaBC':return None
    return -10 if v.GetParmName(pid) in ('ConMode','Type') or v.GetParmName(pid).endswith('Flag') else 20


def coordinate_unit(v):
    system=v.GetParmVal(v.FindParm(v.GetVehicleID(),'StructUnit','FeaStructure'))
    return {v.SI_UNIT:'m',v.CGS_UNIT:'cm',v.MPA_UNIT:'mm',v.BFT_UNIT:'ft',v.BIN_UNIT:'in'}.get(system,'structural solver length units')


def validate_targets(v,structures):
    """Reject unassigned/foreign saved targets before native tag-index lookup."""
    scoped=[]
    for sid in structures:
        for bid in v.GetFeaBCIDVec(sid):
            if v.GetParmVal(v.FindParm(bid,'ConMode','FeaBC'))==v.FEA_BCM_USER and v.GetParmVal(v.FindParm(bid,'Constraints','FeaBC'))==0:continue
            typ=v.GetParmVal(v.FindParm(bid,'Type','FeaBC'))
            if typ in (v.FEA_BC_PART,v.FEA_BC_SUBSURF):scoped.append((sid,bid,typ))
    if not scoped:return
    # Original serialization regenerates output names. Validation must retain
    # all structural output destinations, including other structures and assemblies.
    outputs={(s,i):v.GetFeaMeshFileName(v.GetFeaStructParentGeomID(s),v.GetFeaStructIndex(s),i) for s in v.GetFeaStructIDVec() for i in range(v.FEA_NUM_FILE_NAMES)}
    assembly_outputs={(a,i):v.GetFeaAssemblyFileName(a,i) for a in v.GetFeaAssemblyIDVec() for i in range(v.FEA_NUM_FILE_NAMES)}
    from native_references import references
    try:refs=references(v)
    finally:
        for (s,i),name in outputs.items():v.SetFeaMeshFileName(v.GetFeaStructParentGeomID(s),v.GetFeaStructIndex(s),i,name)
        for (a,i),name in assembly_outputs.items():v.SetFeaAssemblyFileName(a,i,name)
    for sid,bid,typ in scoped:
        part=typ==v.FEA_BC_PART;key='PartID' if part else 'SubSurfID'
        available=v.GetFeaPartIDVec(sid) if part else v.GetFeaSubSurfIDVec(sid)
        if refs.get(bid,{}).get(key,'') not in available:
            raise ValueError('Boundary "'+v.GetContainerName(bid)+'" needs an available '+('structural part' if part else 'structural region')+' in this structure. Choose its target in Modeling tools → Constraints & laminates before meshing.')
