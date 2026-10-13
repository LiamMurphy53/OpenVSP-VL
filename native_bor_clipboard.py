"""Original BOR profile clipboard interoperates with native section clipboard."""
import ctypes,json
from native_tools import one,section


def clipboard(v,g,operation):
    one(g,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='BODYOFREVOLUTION'])
    import native_preview
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_bor_profile_clipboard;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];fn.restype=ctypes.c_char_p
    data=json.loads(fn(engine,g.encode(),operation))
    if data.get('error'):raise ValueError(data['error'])


def copy(v,source):
    if not isinstance(source,dict):raise ValueError('Choose a profile to copy.')
    kind=one(source.get('kind'),['section','bor','auxiliary','region'])
    if kind=='bor':clipboard(v,source['geom'],0)
    elif kind=='auxiliary':
        import native_auxiliary_controls
        native_auxiliary_controls.curve(v,source['geom'],2)
    elif kind=='region':
        import native_region_curves,native_preview
        g,index,ri=native_region_curves.owner(v,source);_,engine,bridge=native_preview.adapter(v)
        fn=bridge.studio_region_curve_operation;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int,ctypes.c_int];fn.restype=ctypes.c_char_p
        data=json.loads(fn(engine,g.encode(),index,ri,2))
        if data.get('error'):raise ValueError(data['error'])
    else:
        g,surf,index,_=section(v,source)
        from native_section_copy import curve_clipboard
        curve_clipboard(v,surf,index,0)


def paste(v,target,source):
    one(target,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='BODYOFREVOLUTION']);copy(v,source);clipboard(v,target,1)
    return True,target
