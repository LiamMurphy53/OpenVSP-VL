"""Original parameter-link switches and native relationship reevaluation."""
import ctypes
import json

OPTIONS=('Scale','Offset','LowerLimit','UpperLimit')


def flags(v,lid):
    return {key:bool(getattr(v,'GetParmLink'+key+'Flag')(lid)) for key in OPTIONS}


def apply(v,r):
    from native_tools import one
    lid=one(r['id'],[v.GetParmLinkID(i) for i in range(v.GetNumParmLinks())])
    changes=r['flags']
    if not isinstance(changes,dict) or not changes or any(key not in OPTIONS or type(value)!=bool for key,value in changes.items()):
        raise ValueError('Choose native link switches with on/off values.')
    for key,value in changes.items():getattr(v,'SetParmLink'+key+'Flag')(lid,value)
    refresh(v,lid)


def refresh(v,lid):
    # Native setters store switches/endpoints. Notify the original manager,
    # to evaluate its stored source, without nudging a dimension or local math.
    from native_preview import adapter
    _,engine,bridge=adapter(v);refresh=bridge.studio_refresh_parameter_links
    refresh.argtypes=[ctypes.c_char_p,ctypes.c_char_p];refresh.restype=ctypes.c_char_p
    result=json.loads(refresh(engine,v.GetParmLinkAParm(lid).encode()))
    if 'error' in result:raise ValueError(result['error'])
    v.Update()


def rewire(v,r):
    from native_tools import one,parameter_ids
    lid=one(r['id'],[v.GetParmLinkID(i) for i in range(v.GetNumParmLinks())])
    allowed={p for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)}|parameter_ids(v)
    source=one(r['source'],allowed);target=one(r['target'],allowed);edges={}
    for i in range(v.GetNumParmLinks()):
        other=v.GetParmLinkID(i)
        if other==lid:continue
        a=v.GetParmLinkAParm(other);b=v.GetParmLinkBParm(other)
        if b==target:raise ValueError('This target already has a driver link.')
        edges.setdefault(a,[]).append(b)
    for i in range(len(v.GetAdvLinkNames())):
        outputs=list(v.GetAdvLinkOutputParms(i))
        if target in outputs:raise ValueError('This target already has a driver expression.')
        for a in v.GetAdvLinkInputParms(i):edges.setdefault(a,[]).extend(outputs)
    stack=[target];seen=set()
    while stack:
        current=stack.pop()
        if current==source:raise ValueError('This link would create a dependency cycle.')
        if current not in seen:seen.add(current);stack.extend(edges.get(current,[]))
    if (v.GetParmLinkAParm(lid),v.GetParmLinkBParm(lid))==(source,target):return
    v.SetParmLinkAParm(lid,source);v.SetParmLinkBParm(lid,target)
    if (v.GetParmLinkAParm(lid),v.GetParmLinkBParm(lid))!=(source,target):raise ValueError('OpenVSP rejected the link endpoints.')
    refresh(v,lid)
