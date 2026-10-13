"""Saved-case study dependencies from the original GeometryAnalysisCase Update."""
import native_geometry_cases as cases


def metadata(v):
    out={}
    types=[c['value'] for c in cases.type_choices(v)]
    forced=[getattr(v,t) for t in ('PLANE_2PT_ANGLE_INTERFERENCE','PLANE_1PT_ANGLE_INTERFERENCE','GEAR_TURN_ANALYSIS','CCE_INTERFERENCE','RISK_ANGLE')]
    for cid in v.GetAllGeometryAnalysesIDVec():
        ids={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
        def condition(name,values):
            return dict(parameter=ids[name],values=values,label=cases.PARAM_LABELS.get(name,name))
        def add(name,branches):
            if name in ids:out[ids[name]]=dict(alternatives=branches,limitControllers=[])
        for axis in 'XYZ':
            add('Rot'+axis+'n',[[condition('SymmRot'+axis,[0])]])
            add('Disp'+axis,[[condition('IntererenceCheckType',[t for t in types if t!=v.PROJ_AREA])],
                             [condition('IntererenceCheckType',[v.PROJ_AREA]),condition('DirectionType',[v.VEC_PROJ])]])
        add('SecondaryType',[[condition('IntererenceCheckType',[t for t in types if t not in forced])]])
        for name in ('PlanarStartLocation','PlanarEndLocation'):
            add(name,[[condition('AutoBoundsFlag',[0])]])
    return out


def priority(v,pid):
    if v.GetParmContainer(pid) not in v.GetAllGeometryAnalysesIDVec():return None
    name=v.GetParmName(pid)
    if name=='IntererenceCheckType':return -12
    if name in ('DirectionType','AutoBoundsFlag','SymmRotX','SymmRotY','SymmRotZ'):return -10
    if name in ('PrimaryType','SecondaryType'):return -8
    return None


def validate(v,pid):
    cases.validate_parameter(v,pid)


def refresh(v,pid):
    if v.GetParmContainer(pid) in v.GetAllGeometryAnalysesIDVec():cases.update(v)
