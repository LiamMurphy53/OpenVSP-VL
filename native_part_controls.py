"""Guided structural placement backed by original FeaStructure::Update."""
import ctypes,json

GROUPS=('FeaPart','FeaRib','FeaSpar','FeaSlice','FeaRibArray','FeaSliceArray','FeaDome','FeaSkin')
LABELS={'AbsRelParmFlag':'Placement units','RelCenterLocation':'Position fraction (0–1)','AbsCenterLocation':'Position (native model units)','OrientationPlane':'Slice plane','RotationAxis':'Slice rotation axis','XRot':'X rotation (degrees)','YRot':'Y rotation (degrees)','ZRot':'Z rotation (degrees)','Theta':'Part angle (degrees)','PerpendicularEdgeType':'Rib reference direction','UsePercentChord':'Place spar by chord fractions','PercentRootChord':'Root chord fraction','PercentTipChord':'Tip chord fraction','LimitRibToSectionFlag':'Limit to wing sections','LimitSparToSectionFlag':'Limit to wing sections','StartWingSection':'First wing section','EndWingSection':'Last wing section','BndBoxTrimFlag':'Trim to bounding box','MatchDihedralFlag':'Follow wing dihedral','PositiveDirectionFlag':'Array direction','RelStartLocation':'Array start fraction','RelEndLocation':'Array end fraction','AbsStartLocation':'Array start (native model units)','AbsEndLocation':'Array end (native model units)','RibRelSpacing':'Rib spacing fraction','RibAbsSpacing':'Rib spacing (native model units)','SliceRelSpacing':'Slice spacing fraction','SliceAbsSpacing':'Slice spacing (native model units)','RemoveSkinTrisFlag':'Remove skin triangles','RemoveRootCapFlag':'Remove root cap','RemoveTipCapFlag':'Remove tip cap','A_Radius':'Dome radius A','B_Radius':'Dome radius B','C_Radius':'Dome radius C','SpineAttachFlag':'Attach dome to parent spine','USpineLoc':'Spine position U (0–1)','X_Location':'Dome body X offset','Y_Location':'Dome body Y offset','Z_Location':'Dome body Z offset','X_Rotation':'Dome X rotation (degrees)','Y_Rotation':'Dome Y rotation (degrees)','Z_Rotation':'Dome Z rotation (degrees)','FlipDirectionFlag':'Reverse dome direction'}
PLANES=[('XY_BODY','Component XY'),('YZ_BODY','Component YZ'),('XZ_BODY','Component XZ'),('XY_ABS','Global XY'),('YZ_ABS','Global YZ'),('XZ_ABS','Global XZ'),('SPINE_NORMAL','Normal to parent spine')]


def owners(v):return {p:s for s in v.GetFeaStructIDVec() for p in v.GetFeaPartIDVec(s)}


def refresh(v,structure=None,pid=None):
    if pid is not None:
        if v.GetParmGroupName(pid) not in GROUPS:return
        structure=owners(v).get(v.GetParmContainer(pid))
        if structure is None:return
    selected=[structure] if structure is not None else list(v.GetFeaStructIDVec())
    if not selected:return
    from native_preview import adapter
    _,engine,bridge=adapter(v);fn=bridge.studio_structure_update
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];fn.restype=ctypes.c_char_p
    for sid in selected:
        if sid not in v.GetFeaStructIDVec():raise ValueError('This structure is unavailable.')
        result=json.loads(fn(engine,v.GetFeaStructParentGeomID(sid).encode(),v.GetFeaStructIndex(sid)))
        if result.get('error'):raise ValueError(result['error'])


def reason(v,pid):
    group=v.GetParmGroupName(pid)
    if group not in GROUPS:return ''
    name=v.GetParmName(pid);owner=v.GetParmContainer(pid);typ=v.GetFeaPartType(owner)
    get=lambda n,g='FeaPart':v.GetParmVal(v.FindParm(owner,n,g))
    if typ==v.FEA_SPAR and get('UsePercentChord','FeaSpar') and name in ('Theta','RelCenterLocation','AbsCenterLocation'):
        return 'OpenVSP calculates spar angle and position from root and tip chord fractions.'
    if typ in (v.FEA_RIB,v.FEA_SPAR,v.FEA_SLICE) and name in ('RelCenterLocation','AbsCenterLocation'):
        follower='AbsCenterLocation' if get('AbsRelParmFlag')==v.REL else 'RelCenterLocation'
        if name==follower:return 'OpenVSP calculates this linked position from the chosen placement units.'
    if typ in (v.FEA_RIB_ARRAY,v.FEA_SLICE_ARRAY) and name in ('AbsStartLocation','RelStartLocation','AbsEndLocation','RelEndLocation','RibAbsSpacing','RibRelSpacing','SliceAbsSpacing','SliceRelSpacing'):
        relative='Rel' in name
        if relative!=(get('AbsRelParmFlag')==v.REL):return 'OpenVSP calculates this linked array value from the chosen placement units.'
    if group in ('FeaSlice','FeaSliceArray') and name in ('XRot','YRot','ZRot'):
        active={v.X_DIR:'XRot',v.Y_DIR:'YRot',v.Z_DIR:'ZRot'}[get('RotationAxis',group)]
        if name!=active:return 'OpenVSP resets rotations outside the selected slice rotation axis to zero.'
    return ''


def annotate(v,p):
    if p['rawGroup'] not in GROUPS:return
    name=p['name'];p['label']=LABELS.get(name,p.get('label',name))
    if name=='AbsRelParmFlag':p['choices']=[dict(value=v.REL,label='Relative · fraction'),dict(value=v.ABS,label='Absolute · model units')]
    elif name=='OrientationPlane':p['choices']=[dict(value=getattr(v,n),label=l) for n,l in PLANES if p['min']<=getattr(v,n)<=p['max']]
    elif name=='RotationAxis':p['choices']=[dict(value=getattr(v,n+'_DIR'),label=n) for n in 'XYZ']
    elif name=='PerpendicularEdgeType':p['choices']=[dict(value=getattr(v,n),label=l) for n,l in [('NO_NORMAL','No reference edge'),('LE_NORMAL','Normal to leading edge'),('TE_NORMAL','Normal to trailing edge'),('SPAR_NORMAL','Normal to selected spar')]]
    elif name=='PositiveDirectionFlag':p['choices']=[dict(value=1,label='Increasing position'),dict(value=0,label='Decreasing position')]
    why=reason(v,p['id'])
    if why:p.update(active=False,editable=False,readOnly=True,readOnlyReason=why)


def validate_parameter(v,pid,value=None):
    why=reason(v,pid)
    if why:raise ValueError(why)
    if value is not None and v.GetParmGroupName(pid) in GROUPS and not v.GetParmLowerLimit(pid)<=value<=v.GetParmUpperLimit(pid):
        raise ValueError('The requested structural value is outside the native limits after this case’s placement and geometry controllers.')


def deferred_limits(v,pid,swept):
    return v.GetParmGroupName(pid) in GROUPS and v.GetParmName(pid) in ('AbsCenterLocation','RelCenterLocation','AbsStartLocation','AbsEndLocation','RelStartLocation','RelEndLocation','RibAbsSpacing','RibRelSpacing','SliceAbsSpacing','SliceRelSpacing','StartWingSection','EndWingSection') and bool(set(swept)-{pid})


def guide(v,owner):
    typ=v.GetFeaPartType(owner)
    fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(owner)}
    val=lambda name:v.GetParmVal(fields[name])
    names=[]
    if typ in (v.FEA_RIB,v.FEA_SPAR,v.FEA_SLICE,v.FEA_RIB_ARRAY,v.FEA_SLICE_ARRAY):
        names+=['AbsRelParmFlag']
        if typ in (v.FEA_RIB_ARRAY,v.FEA_SLICE_ARRAY):
            prefix='Rel' if val('AbsRelParmFlag')==v.REL else 'Abs'
            names+=['PositiveDirectionFlag',prefix+'StartLocation',prefix+'EndLocation',('Rib' if typ==v.FEA_RIB_ARRAY else 'Slice')+prefix+'Spacing']
        else:names+=['RelCenterLocation' if val('AbsRelParmFlag')==v.REL else 'AbsCenterLocation']
    if typ==v.FEA_SPAR:
        names+=['UsePercentChord']
        if val('UsePercentChord'):
            names=[n for n in names if n not in ('RelCenterLocation','AbsCenterLocation')];names+=['PercentRootChord','PercentTipChord']
        else:names+=['Theta']
        names+=['LimitSparToSectionFlag']
    if typ in (v.FEA_RIB,v.FEA_RIB_ARRAY):names+=['PerpendicularEdgeType','Theta','MatchDihedralFlag','LimitRibToSectionFlag']
    if typ in (v.FEA_RIB,v.FEA_SPAR,v.FEA_RIB_ARRAY):
        flag='LimitSparToSectionFlag' if typ==v.FEA_SPAR else 'LimitRibToSectionFlag'
        if val(flag):names+=['StartWingSection','EndWingSection']
        names+=['BndBoxTrimFlag']
    if typ in (v.FEA_SLICE,v.FEA_SLICE_ARRAY):names+=['OrientationPlane','RotationAxis',{v.X_DIR:'XRot',v.Y_DIR:'YRot',v.Z_DIR:'ZRot'}[val('RotationAxis')]]
    if typ==v.FEA_SKIN:names+=['RemoveSkinTrisFlag','RemoveRootCapFlag','RemoveTipCapFlag']
    if typ==v.FEA_DOME:
        names+=['A_Radius','B_Radius','C_Radius','SpineAttachFlag']
        if val('SpineAttachFlag'):names+=['USpineLoc']
        names+=['X_Location','Y_Location','Z_Location','X_Rotation','Y_Rotation','Z_Rotation','FlipDirectionFlag']
    note='Positions and offsets use native model units; fractions are dimensionless. OpenVSP evaluates linked positions, array spacing limits and construction surfaces.'
    if typ==v.FEA_DOME:note+=' Dome body offsets remain additive when spine attachment is enabled.'
    return dict(primary=[fields[n] for n in names if n in fields],note=note)


def study_metadata(v):
    out={}
    for owner in owners(v):
        typ=v.GetFeaPartType(owner);fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(owner)}
        condition=lambda n,values:dict(parameter=fields[n],values=values,label=LABELS.get(n,n))
        def add(name,conditions):
            if name in fields:out[fields[name]]=dict(conditions=conditions,limitControllers=[])
        if typ in (v.FEA_RIB,v.FEA_SPAR,v.FEA_SLICE):
            for name,basis in [('RelCenterLocation',v.REL),('AbsCenterLocation',v.ABS)]:
                extra=[condition('UsePercentChord',[0])] if typ==v.FEA_SPAR else []
                add(name,[condition('AbsRelParmFlag',[basis])]+extra)
        if typ==v.FEA_SPAR:
            add('Theta',[condition('UsePercentChord',[0])])
            for name in ('PercentRootChord','PercentTipChord'):add(name,[condition('UsePercentChord',[1])])
        if typ in (v.FEA_RIB_ARRAY,v.FEA_SLICE_ARRAY):
            for prefix,basis in [('Rel',v.REL),('Abs',v.ABS)]:
                for name in (prefix+'StartLocation',prefix+'EndLocation',('Rib' if typ==v.FEA_RIB_ARRAY else 'Slice')+prefix+'Spacing'):add(name,[condition('AbsRelParmFlag',[basis])])
        if typ in (v.FEA_SLICE,v.FEA_SLICE_ARRAY):
            for axis in 'XYZ':add(axis+'Rot',[condition('RotationAxis',[getattr(v,axis+'_DIR')])])
    return out


def study_priority(v,pid):
    if v.GetParmGroupName(pid) not in GROUPS:return None
    name=v.GetParmName(pid)
    if name=='AbsRelParmFlag':return -12
    if name in ('UsePercentChord','OrientationPlane','RotationAxis','LimitRibToSectionFlag','LimitSparToSectionFlag','PositiveDirectionFlag'):return -10
    if name in ('StartWingSection','EndWingSection'):return -8
    return 20
