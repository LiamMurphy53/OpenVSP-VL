"""Section-curve region controls delegated to the official native engine."""
import ctypes
import json
import math
from pathlib import Path


def import_profile(v,r):
    from native_tools import one
    from native_worker import errors
    fmt=one(r.get('format'),('airfoil','section'),'Choose an airfoil or OpenVSP section file.')
    text=r.get('content')
    if not isinstance(text,str) or not text.strip() or len(text.encode())>5_000_000 or '\x00' in text:
        raise ValueError('Choose a nonempty coordinate file smaller than 5 MB.')
    lines=text.strip().splitlines()
    coordinates=[]
    for number,line in enumerate(lines[1:] if fmt=='section' else lines,2 if fmt=='section' else 1):
        fields=line.split()
        if fmt=='section' and len(fields)!=2:raise ValueError(f'Expected two section coordinates on line {number}.')
        if len(fields)!=2:continue
        try:pair=[float(x) for x in fields]
        except ValueError:
            if fmt=='section':raise ValueError(f'Invalid section coordinates on line {number}.')
            continue
        if not all(math.isfinite(x) and abs(x)<1e12 for x in pair):raise ValueError('File coordinates must be finite and smaller than 1e12 in magnitude.')
        coordinates.append(tuple(pair))
    if fmt=='section' and ('OPENVSP_XSEC_FILE_V1' not in lines[0] or len(set(coordinates))<3):
        raise ValueError('Choose an OPENVSP_XSEC_FILE_V1 section with at least three distinct coordinate points.')
    if fmt=='airfoil' and len(coordinates)<4:raise ValueError('No airfoil coordinate sequence was found.')
    path=Path.cwd()/('region-profile.fxs' if fmt=='section' else 'region-profile.dat');path.write_text(text)
    if fmt=='section':
        from native_section_file_validation import validate_profile_file
        validate_profile_file(path)
    geom=v.AddGeom('STACK')
    try:
        surf=v.GetXSecSurf(geom,0)
        v.ChangeXSecShape(surf,1,v.XS_FILE_FUSE if fmt=='section' else v.XS_FILE_AIRFOIL)
        section=v.GetXSec(surf,1)
        if fmt=='section':points=list(v.ReadFileXSec(section,str(path)))
        else:
            v.ReadFileAirfoil(section,str(path));errors(v)
            # Region curves use normalized surface coordinates. The temporary
            # Stack's default chord is 3, outside a region's native width limit.
            v.SetXSecWidth(section,1.0)
            points=list(v.GetAirfoilUpperPnts(section))+list(v.GetAirfoilLowerPnts(section))
        errors(v)
        if not points or any(not all(math.isfinite(x) for x in (p.x(),p.y(),p.z())) for p in points):
            raise ValueError('OpenVSP returned empty or undefined file coordinates.')
        v.Update();v.CopyXSecCurve(geom,1);errors(v)
    finally:
        v.DeleteGeom(geom);path.unlink(missing_ok=True)


def parameters(v,region,refs,parameter):
    curve=refs.get(region,{}).get('curveID')
    nested=set(v.FindContainerParmIDs(curve)) if curve else set()
    return [parameter(v,p) for p in v.FindContainerParmIDs(region) if p not in nested]


def edit(v,r,operation=0,argument=0,u=0):
    import native_preview
    geom,index,region_index=owner(v,r)
    _,engine,bridge=native_preview.adapter(v)
    function=bridge.studio_region_edit_curve
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_double]
    function.restype=ctypes.c_char_p
    result=json.loads(function(engine,geom.encode(),index,region_index,operation,argument,u))
    if result.get('error'):raise ValueError(result['error'])
    return result


def details(v,region,refs,parameter):
    curve=refs.get(region,{})
    if not curve.get('curveID'):return dict(sectionCurve=None)
    from native_special import SHAPES
    result=dict(id=curve['curveID'],type=curve['curveType'],
        shapes={n:getattr(v,n) for n in SHAPES if hasattr(v,n)},
        params=[parameter(v,p) for p in v.FindContainerParmIDs(curve['curveID'])])
    if curve['curveType']==v.XS_EDIT_CURVE and curve.get('regionType')==v.SS_XSEC_CURVE:
        request=dict(id=region)
        for g in v.FindGeoms():
            if region in v.GetSubSurfIDVec(g):request['geom']=g;break
        if 'geom' not in request:
            request['structure']=next(s for s in v.GetFeaStructIDVec() if region in v.GetFeaSubSurfIDVec(s))
        result.update(edit(v,request))
        # Structural evaluation can refresh derived native curve parameters.
        result['params']=[parameter(v,p) for p in v.FindContainerParmIDs(curve['curveID'])]
        result['curveType']=int(next(p['value'] for p in result['params'] if p['name']=='CurveType'))
        from native_editable_curves import initialization_shape
        result['initShape']=initialization_shape(v,result['params'])
        from native_preview import editable_activity
        result.update(editable_activity(v,result['params'],len(result['controlPoints'])))
    return dict(sectionCurve=result)


def mutate_edit(v,r):
    from native_tools import finite,one
    import native_references
    geom,_,_=owner(v,r)
    ref=native_references.references(v)[r['id']]
    if ref['curveType']!=v.XS_EDIT_CURVE:raise ValueError('Convert this region to an editable curve first.')
    mutate_edit_native(v,r,ref['curveID'],lambda operation=0,argument=0,u=0:edit(v,r,operation,argument,u))
    return True,geom

def mutate_edit_native(v,r,cid,invoke):
    from native_tools import finite,one
    before=invoke();op=r['operation']
    parms={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
    count=len(before['controlPoints'])
    def point():
        i=r.get('point')
        if isinstance(i,bool) or not isinstance(i,int):raise ValueError('Choose a native point index.')
        return one(i,range(count),'Choose an existing curve point.')
    if op=='region-curve-replace-points':
        from native_editable_curves import replace_container_points
        replace_container_points(v,cid,parms,r);invoke()
    elif op=='region-curve-point':
        i=point();p=r.get('xyz')
        if not isinstance(p,list) or len(p)!=3:raise ValueError('Enter three coordinates.')
        values=[finite(x) for x in p]
        side=one(r.get('tangentSide','outgoing'),('incoming','outgoing'),'Choose the incoming or outgoing tangent handle.')
        if int(v.GetParmVal(parms['CurveType']))==v.CEDIT and i%3==0:
            handle=i-1 if side=='incoming' else i+1
            if not 0<=handle<count:
                handle=(count-2 if side=='incoming' else 1) if v.GetParmVal(parms['CloseFlag']) else i
            invoke(6,handle)
        for axis,value in zip('XYZ',values):v.SetParmVal(parms[f'{axis}_{i}'],value)
        invoke(5)
    elif op=='region-curve-fixed':
        i=point()
        if not isinstance(r.get('fixed'),bool):raise ValueError('Choose whether the curve position is fixed.')
        v.SetParmVal(parms[f'FixedU_{i}'],int(r['fixed']))
    elif op=='region-curve-smooth':
        i=point()
        if int(v.GetParmVal(parms['CurveType']))!=v.CEDIT or i%3:
            raise ValueError('Smooth tangents apply to cubic Bezier anchors.')
        if not isinstance(r.get('smooth'),bool):raise ValueError('Choose whether the anchor has a smooth tangent.')
        v.SetParmValUpdate(parms[f'G1_{i}'],int(r['smooth']))
    elif op=='region-curve-init':
        from native_editable_curves import guard_rebuild
        guard_rebuild(v,[dict(id=pid,name=name) for name,pid in parms.items()])
        shape=one(r.get('shape'),('EDIT_XSEC_CIRCLE','EDIT_XSEC_ELLIPSE','EDIT_XSEC_RECTANGLE'))
        v.SetParmVal(parms['ShapeType'],getattr(v,shape));invoke(7)
    elif op=='region-curve-type':
        target=getattr(v,one(r.get('type'),('LINEAR','PCHIP','CEDIT')))
        if (int(v.GetParmVal(parms['CurveType']))==v.CEDIT)!=(target==v.CEDIT):
            from native_editable_curves import guard_rebuild
            guard_rebuild(v,[dict(id=pid,name=name) for name,pid in parms.items()])
        invoke(1,target)
    elif op=='region-curve-split':
        u=finite(r.get('u'))
        if not 0<u<1:raise ValueError('Split position must be strictly between 0 and 1.')
        from native_editable_curves import guard_rebuild
        guard_rebuild(v,[dict(id=pid,name=name) for name,pid in parms.items()])
        invoke(2,u=u);v.Update()
        if len(invoke()['controlPoints'])<=count:raise ValueError('OpenVSP did not add a point here. Choose a location between existing anchors.')
    elif op=='region-curve-delete':
        i=point();one(i,range(1,count-1),'The first and closing points cannot be removed.')
        if int(v.GetParmVal(parms['CurveType']))==v.CEDIT and i%3:raise ValueError('Remove a curve anchor, not a Bezier handle.')
        from native_editable_curves import guard_rebuild
        guard_rebuild(v,[dict(id=pid,name=name) for name,pid in parms.items()],{i-1,i,i+1} if int(v.GetParmVal(parms['CurveType']))==v.CEDIT else {i})
        invoke(3,i);v.Update()
        if len(invoke()['controlPoints'])>=count:raise ValueError('OpenVSP could not remove this point with the current curve constraints.')
    elif op=='region-curve-reparameterize':invoke(4)
    else:raise ValueError('Unknown editable region curve operation.')
    v.Update()


def owner(v,r):
    from native_tools import one
    import native_references
    if r.get('structure'):
        structure=one(r['structure'],v.GetFeaStructIDVec())
        geom=v.GetFeaStructParentGeomID(structure);index=v.GetFeaStructIndex(structure)
        regions=list(v.GetFeaSubSurfIDVec(structure))
        region=one(r.get('id'),regions,'Choose a region in this structure.')
        refs=native_references.references(v)
        typ=refs.get(region,{}).get('regionType')
    else:
        geom=one(r.get('geom'),v.FindGeoms());index=-1
        regions=list(v.GetSubSurfIDVec(geom))
        region=one(r.get('id'),regions,'Choose a region on this component.')
        typ=v.GetSubSurfType(region)
    if typ!=v.SS_XSEC_CURVE:raise ValueError('Choose a section-curve region; computed intersection curves retain their native shape.')
    return geom,index,regions.index(region)


def mutate(v,r):
    from native_tools import one,section
    from native_special import SHAPES
    import native_preview
    geom,index,region_index=owner(v,r)
    import native_references
    from native_editable_curves import guard_container_shape_replacement
    ref=native_references.references(v)[r['id']]
    def protect(target):guard_container_shape_replacement(v,ref['curveID'],ref['curveType'],target)
    _,engine,bridge=native_preview.adapter(v)
    change=bridge.studio_region_curve_shape if r['operation']=='region-curve-shape' else bridge.studio_region_curve_operation
    change.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int,ctypes.c_int];change.restype=ctypes.c_char_p
    def call(g,i,ri,operation):
        response=json.loads(change(engine,g.encode(),i,ri,operation))
        if response.get('error'):raise ValueError(response['error'])
    if r['operation']=='region-curve-shape':
        shape=one(r.get('shape'),[n for n in SHAPES if hasattr(v,n)],'Choose a native curve shape.')
        protect(getattr(v,shape));call(geom,index,region_index,getattr(v,shape))
    elif r['operation']=='region-curve-convert':
        protect(v.XS_EDIT_CURVE);call(geom,index,region_index,1)
    elif r['operation']=='region-curve-import':
        fmt=one(r.get('format'),('airfoil','section'))
        protect(v.XS_FILE_AIRFOIL if fmt=='airfoil' else v.XS_FILE_FUSE)
        import_profile(v,r);call(geom,index,region_index,3)
    elif r['operation']=='region-curve-copy-from':
        source=r.get('source')
        if not isinstance(source,dict):raise ValueError('Choose a curve to copy.')
        import native_bor_clipboard
        native_bor_clipboard.copy(v,source)
        call(geom,index,region_index,3)
    else:raise ValueError('Unknown section-curve operation.')
    v.Update()
    return True,geom
