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
    if field['rawGroup']=='XForm' and field['name']=='Scale':
        owner=v.GetParmContainer(field['id'])
        if owner in v.FindGeoms():field['scaleActions']=dict(geom=owner)
    message=reason(v,field['id'])
    if message:field.update(displayReadOnly=True,editable=False,readOnlyReason=message,description=message)


def validate_parameter(v,pid):
    message=reason(v,pid)
    if message:raise ValueError(message)


def mutate(v,request):
    from native_preview import parameter_activity
    gid=request.get('geom')
    if gid not in v.FindGeoms():raise ValueError('Choose an existing component to scale.')
    pid=v.FindParm(gid,'Scale','XForm')
    if not v.ValidParm(pid) or not parameter_activity(v,[pid])[pid]:raise ValueError('Scale is locked by OpenVSP for this component.')
    operation=request.get('operation')
    if operation=='scale-accept':v.AcceptGeomScale(gid)
    elif operation=='scale-reset':v.ResetGeomScale(gid)
    else:raise ValueError('Choose Accept scale or Reset scale.')
