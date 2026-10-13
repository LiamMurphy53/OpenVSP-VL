"""Original BOR editable-profile operations through the existing curve adapter."""
import ctypes,json


def edit(v,gid,operation=0,argument=0,u=0):
    from native_tools import one
    import native_preview
    one(gid,[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='BODYOFREVOLUTION'])
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_bor_edit_curve
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int,ctypes.c_double];fn.restype=ctypes.c_char_p
    data=json.loads(fn(engine,gid.encode(),operation,argument,u))
    if data.get('error'):raise ValueError(data['error'])
    return data


def container(v,gid):
    return v.GetParmContainer(next(p for p in v.GetGeomParmIDs(gid) if v.GetParmName(p)=='CurveType' and v.GetParmGroupName(p)=='XSecCurve'))


def details(v,gid,parameter):
    if v.GetBORXSecShape(gid)!=v.XS_EDIT_CURVE:return None
    from native_preview import editable_activity
    data=edit(v,gid);cid=container(v,gid);fields=[parameter(v,p) for p in v.FindContainerParmIDs(cid)]
    data.update(id=cid,type=v.XS_EDIT_CURVE,params=fields,curveType=int(v.GetParmVal(v.FindParm(cid,'CurveType','XSecCurve'))))
    data.update(editable_activity(v,fields,len(data['controlPoints'])))
    from native_editable_curves import initialization_shape
    data['initShape']=initialization_shape(v,fields)
    return data


def mutate(v,r):
    gid=r['geom']
    if r['operation']=='bor-curve-convert':edit(v,gid);v.Update();return True,gid
    if v.GetBORXSecShape(gid)!=v.XS_EDIT_CURVE:raise ValueError('Convert the revolution profile to an editable curve first.')
    from native_region_curves import mutate_edit_native
    from native_tools import finite
    from native_preview import parameter_activity
    cid=container(v,gid);fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)};before=edit(v,gid);op=r['operation'].replace('bor-curve-','region-curve-')
    if op in ('region-curve-point','region-curve-fixed','region-curve-smooth'):
        i=r.get('point')
        if type(i)!=int or not 0<=i<len(before['controlPoints']):raise ValueError('Choose an existing curve point.')
        if op=='region-curve-point':
            coords=r.get('xyz')
            if not isinstance(coords,list) or len(coords)!=3:raise ValueError('Enter three coordinates.')
            updates=[(fields[f'{a}_{i}'],finite(x)) for a,x in zip('XYZ',coords)]
        else:
            key='fixed' if op=='region-curve-fixed' else 'smooth'
            if type(r.get(key))!=bool:raise ValueError('Choose whether the curve constraint is enabled.')
            updates=[(fields[f'FixedU_{i}' if key=='fixed' else f'G1_{i}'],int(r[key]))]
        activity=parameter_activity(v,[p for p,_ in updates])
        for p,x in updates:
            if not activity[p] and x!=v.GetParmVal(p):raise ValueError('This profile coordinate or constraint is locked by OpenVSP.')
            if not v.GetParmLowerLimit(p)<=x<=v.GetParmUpperLimit(p):raise ValueError('Use a value within the native profile limits.')
    mutate_edit_native(v,{**r,'operation':op},cid,lambda operation=0,argument=0,u=0:edit(v,gid,operation,argument,u))
    return True,gid
