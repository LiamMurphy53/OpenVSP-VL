"""Original point/tangent inspection for native profile owners."""
import ctypes,json,math
from native_tools import one,section


def query(v,r):
    from native_fit import coord
    source=r.get('source')
    if not isinstance(source,dict):raise ValueError('Choose a native profile.')
    kind=one(source.get('kind'),['section','bor','auxiliary','region']);fraction=coord(r['fraction'])
    if kind=='section':
        _,_,_,x=section(v,source);point=v.ComputeXSecPnt(x,fraction);tangent=v.ComputeXSecTan(x,fraction);operation='ComputeXSecPnt / ComputeXSecTan';units='Native profile model units'
    elif kind=='bor':
        g=one(source.get('geom'),[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='BODYOFREVOLUTION']);point=v.ComputeBORXSecPnt(g,fraction);tangent=v.ComputeBORXSecTan(g,fraction);operation='ComputeBORXSecPnt / ComputeBORXSecTan';units='Native profile model units'
    else:
        if kind=='auxiliary':
            import native_auxiliary_controls as a
            a.curve(v,source['geom']);cid=a.curve_container(v,source['geom']);units='Native cone profile angles in degrees'
        else:
            import native_region_curves,native_references
            native_region_curves.owner(v,source);cid=native_references.references(v)[source['id']]['curveID'];units='Native region profile coordinates'
        import native_preview
        _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_profile_query;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_double];fn.restype=ctypes.c_char_p
        data=json.loads(fn(engine,cid.encode(),fraction))
        if data.get('error'):raise ValueError(data['error'])
        operation='XSecCurve::GetCurve / VspCurve::CompPnt01 / CompTan01'
    if kind in ('section','bor'):
        def xyz(p):return [x if math.isfinite(x) else None for x in (p.x(),p.y(),p.z())]
        data=dict(point=xyz(point),tangent=xyz(tangent))
    result=dict(nativeOperation=operation,fraction=fraction,coordinateFrame='Native XSec curve XYZ with section placement' if kind=='section' else 'Native profile-local XYZ',coordinateConvention=units,**data)
    if any(x is None for values in data.values() for x in values):result['nativeWarning']='OpenVSP returned undefined profile coordinates at this position. Undefined values are preserved as null.'
    return result
