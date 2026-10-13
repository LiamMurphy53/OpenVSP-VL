"""Guidance and reference validation for native Bogie retraction; no mechanism math."""
import native_preview

ATTACH_NAMES=(('NONE','Down-position pivot'),('COMP','Component axes'),('UV','Surface (U / W)'),('RST','Section volume (R / S / T)'),('LMN','Uniform volume (L / M / N)'),('EtaMN','Wing span (eta / M / N)'))
COORDINATES=((2,['U01','ULoc','U0NLoc','WLoc']),(3,['R01','RLoc','R0NLoc','SLoc','TLoc']),(4,['L01','LLoc','L0LenLoc']),(5,['EtaLoc']),((4,5),['MLoc','NLoc']))
MECHANISM=['MechKRetract','Mech_X_Axis','Mech_Y_Axis','Mech_Z_Axis','Mech_RetAngle','MechKneePos','MechKneeDownAngle','MechKneeAngle','MechKneeAzimuthAngle','MechKneeElevationAngle','Mech_TwistAngle','m_MechRollAngle','Mech_BogieAngle','Mech_StrutDL']
LABELS={'MechKRetract':'Retraction fraction (0–1)','Mech_X_Axis':'Retraction axis X','Mech_Y_Axis':'Retraction axis Y','Mech_Z_Axis':'Retraction axis Z','Mech_RetAngle':'Main retraction angle (degrees)',
 'MechKneePos':'Knee position fraction','MechKneeDownAngle':'Knee angle when down (degrees)','MechKneeAngle':'Knee retraction angle (degrees)',
 'MechKneeAzimuthAngle':'Knee azimuth (degrees)','MechKneeElevationAngle':'Knee elevation (degrees)','Mech_TwistAngle':'Retraction twist (degrees)',
 'm_MechRollAngle':'Retraction roll (degrees)','Mech_BogieAngle':'Bogie retraction angle (degrees)','Mech_StrutDL':'Strut length change (model units)'}


def names(v,bid):return {v.GetParmName(p):p for p in v.FindContainerParmIDs(bid)}


def reasons(v,bid,fields=None):
    fields=fields or names(v,bid);locked={};mode=int(v.GetParmVal(fields['RetMode']))
    prefix='Mech' if mode==v.GEAR_STOWED_POSITION else 'Stow'
    for name,pid in fields.items():
        if name.startswith(prefix) or (prefix=='Mech' and name=='m_MechRollAngle'):
            locked[pid]='Calculated by OpenVSP from the selected retraction driver.'
    for prefix in ('Stow','Mech'):
        selected={int(v.GetParmVal(fields[prefix+'TransAttachFlag']))}
        if prefix=='Stow':selected.add(int(v.GetParmVal(fields[prefix+'RotAttachFlag'])))
        for mode,suffixes in COORDINATES:
            if selected.intersection(mode if isinstance(mode,tuple) else [mode]):continue
            for suffix in suffixes:locked[fields[prefix+suffix]]='Choose this attachment reference before editing its coordinates.'
        if not selected.intersection((2,3,4,5)):locked[fields[prefix+'SurfIndx']]='Surface selection applies to a surface or volume attachment reference.'
    return locked


def labels(v):
    result=dict(LABELS)
    for prefix,title in [('Stow','Stowed'),('Mech','Mechanism')]:
        result[prefix+'AbsRelFlag']=title+' coordinate frame'
        result[prefix+'TransAttachFlag']=title+' position reference'
        if prefix=='Stow':result[prefix+'RotAttachFlag']='Stowed rotation reference'
        result[prefix+'SurfIndx']=title+' attachment surface'
        for suffix,label in [('U01','U basis'),('ULoc','U fraction'),('U0NLoc','U native coordinate'),('WLoc','W fraction'),('R01','R basis'),('RLoc','R fraction'),('R0NLoc','R native coordinate'),('SLoc','S fraction'),('TLoc','T fraction'),('L01','L basis'),('LLoc','L fraction'),('L0LenLoc','L distance (model units)'),('MLoc','M fraction'),('NLoc','N fraction'),('EtaLoc','Wing span fraction')]:
            result[prefix+suffix]=title+' · '+label
        for axis in 'XYZ':
            for suffix,description in [('Loc','position (model units)'),('RelLoc','offset (model units)')]:
                key=prefix+axis+suffix if prefix=='Stow' or suffix=='RelLoc' else 'Mech_'+axis+'Loc'
                result[key]=title+' '+axis+' '+description
            if prefix=='Stow':
                result[prefix+axis+'Rot']=title+' '+axis+' rotation (degrees)'
                result[prefix+axis+'RelRot']=title+' '+axis+' rotation offset (degrees)'
    return result


def choices(v):
    result={}
    for prefix in ('Stow','Mech'):
        result[prefix+'AbsRelFlag']=[(v.ABS,'Gear coordinates'),(v.REL,'Relative to attachment')]
        result[prefix+'TransAttachFlag']=[(getattr(v,'ATTACH_TRANS_'+n),s) for n,s in ATTACH_NAMES]
        if prefix=='Stow':result[prefix+'RotAttachFlag']=[(getattr(v,'ATTACH_ROT_'+n),'No attachment rotation' if n=='NONE' else s) for n,s in ATTACH_NAMES]
        for coord in ('U','R','L'):
            result[prefix+coord+'01']=[(1,'Normalized fraction (0–1)'),(0,'Distance along component' if coord=='L' else 'Native section coordinate')]
    return result


def metadata(v,gid,bid,drawings=False):
    data=native_preview.bogie_retraction(v,gid,bid,drawings=drawings)
    fields=names(v,bid)
    data['mode']=int(v.GetParmVal(fields['RetMode']))
    data['fields']=fields
    return data


def dependencies(v):
    geoms=list(v.FindGeoms());graph={g:{v.GetGeomParent(g)}&set(geoms) for g in geoms}
    for g in geoms:
        if v.GetGeomTypeName(g).upper()!='GEAR':continue
        for b in v.GetAllBogies(g):
            m=metadata(v,g,b)
            graph[g].update(p for p in (m['stowParent'],m['mechanismParent']) if p in graph)
    return graph


def refresh(v):
    """Evaluate forward references and restore native step-child registration.

    Gear DecodeXml may run before a referenced joint/component is decoded.
    Plain Vehicle.Update does not dirty that already evaluated gear afterward.
    Follow native dependencies, then request native Gear evaluation; no pose or
    mechanism formula, driver value, parent ID, or parameter ID is replaced.
    """
    gears={g:list(v.GetAllBogies(g)) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='GEAR'}
    if not gears:return
    graph=dependencies(v);done=set();visiting=set()
    def visit(g):
        if g in done:return
        if g in visiting:raise ValueError('The saved gear attachments contain a circular component or gear reference.')
        visiting.add(g)
        for parent in sorted(graph.get(g,())):visit(parent)
        if g in gears:
            for bid in gears[g]:native_preview.bogie_retraction(v,g,bid,'refresh')
        visiting.remove(g);done.add(g)
    for g in gears:visit(g)
    v.Update()


def require_dependency(v,owner,parent):
    if not parent:return
    graph=dependencies(v);pending=[parent];seen=set()
    while pending:
        current=pending.pop()
        if current==owner:raise ValueError('This attachment would create a circular component or gear reference.')
        if current in seen:continue
        seen.add(current);pending.extend(graph.get(current,()))


def set_parent(v,gid,bid,side,parent):
    from native_tools import one
    one(side,['stow','mechanism'],'Choose a stowed-position or mechanism attachment.')
    fields=names(v,bid);mode=int(v.GetParmVal(fields['RetMode']))
    expected=v.GEAR_STOWED_POSITION if side=='stow' else v.GEAR_MECHANISM
    if mode!=expected:raise ValueError('Choose this retraction driver before changing its attachment.')
    one(parent,['']+list(v.FindGeoms()),'Choose an existing attachment component or the down-position pivot.')
    require_dependency(v,gid,parent)
    native_preview.bogie_retraction(v,gid,bid,side,parent)
    v.Update()


def guard_geometry_delete(v,gid):
    removed={gid};pending=[gid]
    while pending:
        for g in v.GetGeomChildren(pending.pop()):
            if g not in removed:removed.add(g);pending.append(g)
    users=[]
    for g in v.FindGeoms():
        if g in removed or v.GetGeomTypeName(g).upper()!='GEAR':continue
        for b in v.GetAllBogies(g):
            m=metadata(v,g,b)
            if m['stowParent'] in removed or m['mechanismParent'] in removed:users.append(v.GetGeomName(g)+' / '+v.GetContainerName(b))
    if users:raise ValueError('Reassign the gear retraction attachment before removing this component: '+', '.join(users))


def validate_parameter(v,pid,value):
    name=v.GetParmName(pid)
    if name not in ('StowTransAttachFlag','StowRotAttachFlag','MechTransAttachFlag','StowSurfIndx','MechSurfIndx'):return
    bid=v.GetParmContainer(pid);gear=next((g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='GEAR' and bid in v.GetAllBogies(g)),None)
    if not gear:return
    data=metadata(v,gear,bid);parent=data['stowParent' if name.startswith('Stow') else 'mechanismParent']
    if name.endswith('SurfIndx'):
        if parent not in v.FindGeoms() or value not in range(v.GetTotalNumSurfs(parent)):raise ValueError('Choose an actual surface of the retraction attachment component.')
    elif value in (v.ATTACH_TRANS_UV,v.ATTACH_TRANS_RST,v.ATTACH_TRANS_LMN,v.ATTACH_TRANS_EtaMN):
        if parent not in v.FindGeoms() or v.GetNumMainSurfs(parent)==0:raise ValueError('Choose an attachment component with native surfaces first.')
        if value==v.ATTACH_TRANS_EtaMN and v.GetGeomTypeName(parent).upper()!='WING':raise ValueError('Wing-span attachment requires a wing component.')


def controller(v,pid):
    return v.GetParmName(pid) in {'RetMode','GearConfigMode','StowAbsRelFlag','StowTransAttachFlag','StowRotAttachFlag','MechAbsRelFlag','MechTransAttachFlag','StowU01','StowR01','StowL01','MechU01','MechR01','MechL01'}


def controller_priority(v,pid):
    name=v.GetParmName(pid)
    if name=='RetMode':return -3
    if name=='GearConfigMode':return -2
    if controller(v,pid):return -1
