"""Retain native editable point vectors across the original curve clipboard."""

def capture(v,source):
    kind=source['kind']
    if kind=='section':
        from native_tools import section
        _,_,_,x=section(v,source)
        if v.GetXSecShape(x)!=v.XS_EDIT_CURVE:return None
        cid=v.GetParmContainer(v.GetXSecParm(x,'Theta'))
    elif kind=='bor':
        if v.GetBORXSecShape(source['geom'])!=v.XS_EDIT_CURVE:return None
        from native_bor_curves import container
        cid=container(v,source['geom'])
    elif kind=='auxiliary':
        from native_auxiliary_controls import curve_container
        cid=curve_container(v,source['geom'])
    else:
        from native_references import references
        cid=references(v).get(source.get('id'),{}).get('curveID')
        if not cid:return None
    fields={v.GetParmName(p):v.GetParmVal(p) for p in v.FindContainerParmIDs(cid)}
    if 'CurveType' not in fields:return None
    count=sum(name.startswith('U_') and name[2:].isdigit() for name in fields)
    return dict(type=next(name for name in ('LINEAR','PCHIP','CEDIT') if getattr(v,name)==fields['CurveType']),rows=[[fields[f'{axis}_{i}'] for axis in ('U','X','Y','Z','R')] for i in range(count)],flags={name:value for name,value in fields.items() if name.startswith(('G1_','FixedU_'))})


def restore(v,cid,payload):
    if payload is None:return
    fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
    actual=[[v.GetParmVal(fields[f'{axis}_{i}']) for axis in ('U','X','Y','Z','R')] for i in range(sum(n.startswith('U_') and n[2:].isdigit() for n in fields))]
    if actual==payload['rows']:return
    # DecodeXml only grows arrays and can clamp U against old point limits.
    # The original SetPntVecs rebuilds all native arrays and their limits.
    from native_editable_curves import replace_container_points
    replace_container_points(v,cid,fields,payload)
    fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
    for name,value in payload['flags'].items():v.SetParmVal(fields[name],value)
    v.Update()


def copy_to_section(v,source,surface,index):
    import native_bor_clipboard
    from native_section_copy import curve_clipboard
    payload=capture(v,source)
    native_bor_clipboard.copy(v,source);curve_clipboard(v,surface,index,1)
    if payload is not None:
        x=v.GetXSec(surface,index)
        restore(v,v.GetParmContainer(v.GetXSecParm(x,'Theta')),payload)
