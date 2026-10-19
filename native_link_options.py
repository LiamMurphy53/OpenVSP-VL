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
    # Native flag setters only store the switches. Notify the original manager,
    # to evaluate its stored source, without nudging a dimension or local math.
    from native_preview import adapter
    _,engine,bridge=adapter(v);refresh=bridge.studio_refresh_parameter_links
    refresh.argtypes=[ctypes.c_char_p,ctypes.c_char_p];refresh.restype=ctypes.c_char_p
    result=json.loads(refresh(engine,v.GetParmLinkAParm(lid).encode()))
    if 'error' in result:raise ValueError(result['error'])
    v.Update()
