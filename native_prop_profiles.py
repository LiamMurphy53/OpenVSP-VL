"""Propeller profiles must retain a nonzero base chord for native lofting."""
def is_prop(v,gid):return v.GetGeomTypeName(gid).upper() in ('PROP','PROPELLER')


def validate_shape(v,gid,shape):
    if is_prop(v,gid) and shape==v.XS_POINT:raise ValueError('OpenVSP cannot use Point profiles on propeller blades. Choose an airfoil or another nonzero-chord profile. The edit was not saved.')


def point_sections(v):
    return {(g,v.GetXSec(v.GetXSecSurf(g,s),i)) for g in v.FindGeoms() if is_prop(v,g) for s in range(v.GetNumXSecSurfs(g)) for i in range(v.GetNumXSec(v.GetXSecSurf(g,s))) if v.GetXSecShape(v.GetXSec(v.GetXSecSurf(g,s),i))==v.XS_POINT}


def validate_new_points(v,before):
    if point_sections(v)-before:raise ValueError('OpenVSP cannot use Point profiles on propeller blades. Choose an airfoil or another nonzero-chord profile. The edit was not saved.')
