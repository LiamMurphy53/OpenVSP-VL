"""Protect native scaling bookkeeping; Geom::Scale owns all resize equations."""
REASONS={
    'Last_Scale':'Native scale bookkeeping is calculated. Use Scale to resize the component.',
    'Scale_From_Original':'Accumulated native scale is calculated. Use Scale to resize the component.',
}


def reason(v,pid):
    if v.GetParmGroupName(pid)!='XForm' or v.GetParmName(pid) not in REASONS:return None
    owner=v.GetParmContainer(pid)
    if owner not in v.FindGeoms() or pid not in v.GetGeomParmIDs(owner):return None
    return REASONS[v.GetParmName(pid)]


def annotate(v,field):
    message=reason(v,field['id'])
    if message:field.update(displayReadOnly=True,editable=False,readOnlyReason=message,description=message)


def validate_parameter(v,pid):
    message=reason(v,pid)
    if message:raise ValueError(message)
