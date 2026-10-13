"""Copy complete cross-sections using the original engine clipboard."""
def replace(v,request):
    from native_worker import errors
    target=request['geom'];source=request['sourceGeom']
    if target not in v.FindGeoms() or source not in v.FindGeoms():raise ValueError('Choose existing source and target components.')
    surface_indices=[request.get('surface',0),request.get('sourceSurface',0)]
    if any(type(i)!=int for i in surface_indices):raise ValueError('Choose valid section surfaces.')
    indices=[request['index'],request['sourceIndex']]
    if any(type(i)!=int for i in indices):raise ValueError('Choose valid section indices.')
    surfaces=[]
    for gid,index,si in zip((target,source),indices,surface_indices):
        if not 0<=si<v.GetNumXSecSurfs(gid):raise ValueError('This component has no editable cross-sections.')
        surf=v.GetXSecSurf(gid,si)
        if not 0<=index<v.GetNumXSec(surf):raise ValueError('The selected section no longer exists.')
        surfaces.append(surf)
    if target==source and indices[0]==indices[1] and surface_indices[0]==surface_indices[1]:raise ValueError('Choose a different source section.')
    count=v.GetNumXSec(surfaces[0])
    from native_custom_library import is_custom
    if surface_indices==[0,0] and not is_custom(v,source):
        v.CopyXSec(source,indices[1]);errors(v)
        v.PasteXSec(target,indices[0]);errors(v)
    else:
        import ctypes,json,native_preview
        _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_section_copy_surfaces
        fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int];fn.restype=ctypes.c_char_p
        result=json.loads(fn(engine,surfaces[1].encode(),surfaces[0].encode(),indices[1],indices[0]));errors(v)
        if 'error' in result:raise ValueError(result['error'])
    refresh_owner(v,target);errors(v)
    if v.GetNumXSec(surfaces[0])!=count:raise ValueError('OpenVSP changed the section count unexpectedly.')


def curve_clipboard(v,surface,index,operation):
    import ctypes,json,native_preview
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_section_curve_clipboard
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int];fn.restype=ctypes.c_char_p
    data=json.loads(fn(engine,surface.encode(),index,operation))
    if data.get('error'):raise ValueError(data['error'])


def refresh_owner(v,gid):
    import ctypes,json,native_preview
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_refresh_section_owner
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
    data=json.loads(fn(engine,gid.encode()))
    if data.get('error'):raise ValueError(data['error'])
    v.UpdateGeom(gid);v.Update()
