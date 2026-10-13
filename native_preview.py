"""Read official engine structural drawing data, without meshing or geometry math."""
import ctypes
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import tempfile
from vsp_runtime import ROOT,distribution


def adapter(v):
    if platform.system()!='Darwin' or platform.machine()!='arm64' or v.GetVSPVersion()!='OpenVSP 3.52.2':
        raise ValueError('Native drawing and section-curve controls currently require the installed macOS arm64 OpenVSP 3.52.2 engine.')
    source=ROOT/'native_bridge/structural_preview.cpp';headers=ROOT/'native_bridge/vendor/openvsp-3.52.2'
    digest=hashlib.sha256(source.read_bytes()+b''.join(p.read_bytes() for p in sorted(headers.glob('*.h')))).hexdigest()[:20]
    folder=ROOT/'.runtime/native-preview';folder.mkdir(parents=True,exist_ok=True);library=folder/(digest+'.dylib')
    if not library.exists():
        with tempfile.TemporaryDirectory(dir=folder) as temp:
            target=Path(temp)/'preview.dylib'
            sdk=subprocess.run(['/usr/bin/xcrun','--show-sdk-path'],capture_output=True,text=True,timeout=30)
            if sdk.returncode:raise ValueError('Apple SDK headers are required to build the native drawing adapter.')
            xml_headers=Path(sdk.stdout.strip())/'usr/include/libxml2'
            result=subprocess.run(['/usr/bin/clang++','-std=c++17','-O2','-dynamiclib','-I',str(headers),'-I',str(xml_headers),str(source),'-o',str(target)],capture_output=True,text=True,timeout=60)
            if result.returncode:raise ValueError('Could not build the native drawing adapter: '+result.stderr[-3000:])
            target.replace(library)
    engine=distribution()/'python/openvsp/openvsp/_vsp.so'
    bridge=ctypes.CDLL(str(library));function=bridge.studio_structural_preview
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_int,ctypes.c_int];function.restype=ctypes.c_char_p
    return function,str(engine).encode(),bridge


def symmetry_count(v,gid):
    """Read Geom::GetNumSymmCopies from the installed engine, including ancestors."""
    if gid not in v.FindGeoms():raise ValueError('Choose an existing component.')
    _,engine,bridge=adapter(v);function=bridge.studio_symmetry_count
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p];function.restype=ctypes.c_char_p
    result=json.loads(function(engine,gid.encode()))
    if isinstance(result,dict):raise ValueError(result.get('error','Native symmetry copies unavailable.'))
    if type(result)!=int or result<1:raise ValueError('Native symmetry copy count is invalid.')
    return result

def export_fea_mesh(v,sid):
    """Original FeaMeshMgr exports of an existing native mesh/intersections."""
    if sid not in v.GetFeaStructIDVec():raise ValueError('Choose an existing native structure.')
    _,engine,bridge=adapter(v);function=bridge.studio_fea_mesh_export
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p];function.restype=ctypes.c_char_p
    result=json.loads(function(engine,sid.encode()))
    if 'error' in result:raise ValueError(result['error'])


def bogie_retraction(v,gid,bid,action='state',parent='',drawings=False):
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='GEAR':raise ValueError('Choose an existing landing gear.')
    if bid not in v.GetAllBogies(gid):raise ValueError('Choose a wheel group in this landing gear.')
    actions={'state':0,'stow':1,'mechanism':2,'refresh':3}
    if action not in actions:raise ValueError('Choose a supported retraction reference.')
    _,engine,bridge=adapter(v);function=bridge.studio_bogie_retraction
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_bool];function.restype=ctypes.c_char_p
    result=json.loads(function(engine,gid.encode(),bid.encode(),actions[action],parent.encode(),drawings))
    if 'error' in result:raise ValueError(result['error'])
    return result


def refresh_profile(v,pid,gid):
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='BODYOFREVOLUTION' or pid not in v.GetGeomParmIDs(gid):raise ValueError('Choose the original body-of-revolution profile.')
    anchor=v.FindParm(gid,'Theta','XSecCurve')
    if not v.ValidParm(pid) or not v.ValidParm(anchor) or v.GetParmContainer(pid)!=v.GetParmContainer(anchor):
        raise ValueError('Choose an original body-of-revolution curve parameter.')
    _,engine,bridge=adapter(v);function=bridge.studio_refresh_profile
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p];function.restype=ctypes.c_char_p
    result=json.loads(function(engine,v.GetParmContainer(pid).encode(),pid.encode(),gid.encode()))
    if 'error' in result:raise ValueError(result['error'])
    return result


def parameter_activity(v,ids):
    ids=list(ids)
    _,engine,bridge=adapter(v);function=bridge.studio_parameter_activity
    function.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_char_p),ctypes.c_int];function.restype=ctypes.c_char_p
    native_ids=(ctypes.c_char_p*len(ids))(*(p.encode() for p in ids))
    result=json.loads(function(engine,native_ids,len(ids)))
    if isinstance(result,dict):raise ValueError(result.get('error','Native parameter activity unavailable.'))
    if len(result)!=len(ids):raise ValueError('Native parameter activity is incomplete.')
    return dict(zip(ids,result))


def prop_driver_combinations(v):
    """Ask the installed native PropDriverGroup to validate all three-driver sets."""
    _,engine,bridge=adapter(v)
    function=bridge.studio_prop_driver_combinations
    function.argtypes=[ctypes.c_char_p];function.restype=ctypes.c_char_p
    result=json.loads(function(engine))
    if isinstance(result,dict):raise ValueError(result.get('error','Native propeller drivers unavailable.'))
    return result


def wing_driver_combinations(v):
    """Use official WingDriverGroup::ValidDrivers, not copied independence rules."""
    _,engine,bridge=adapter(v)
    function=bridge.studio_wing_driver_combinations
    function.argtypes=[ctypes.c_char_p];function.restype=ctypes.c_char_p
    result=json.loads(function(engine))
    if isinstance(result,dict):raise ValueError(result.get('error','Native wing drivers unavailable.'))
    return result


def wing_driver_parameters(v,gid,section):
    """Read the actual WingSect::GetDriverParms IDs in native enum order."""
    if v.GetGeomTypeName(gid).upper()!='WING':raise ValueError('Choose a wing for section driver controls.')
    surf=v.GetXSecSurf(gid,0)
    if type(section)!=int or not 0<=section<v.GetNumXSec(surf):raise ValueError('Choose an existing wing section.')
    _,engine,bridge=adapter(v);function=bridge.studio_wing_driver_parameters
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];function.restype=ctypes.c_char_p
    result=json.loads(function(engine,gid.encode(),section))
    if isinstance(result,dict):raise ValueError(result.get('error','Native wing section parameters unavailable.'))
    if len(result)!=11 or any(not v.ValidParm(pid) for pid in result):raise ValueError('Native wing section parameter list is incomplete.')
    return result


def body_driver_combinations(v,circle=False):
    """Read supported section driver choices from installed native validators."""
    _,engine,bridge=adapter(v);function=bridge.studio_body_driver_combinations
    function.argtypes=[ctypes.c_char_p,ctypes.c_bool];function.restype=ctypes.c_char_p
    result=json.loads(function(engine,circle))
    if isinstance(result,dict):raise ValueError(result.get('error','Native section drivers unavailable.'))
    return result


def body_driver_parameters(v,gid,surface,index):
    if v.GetGeomTypeName(gid).upper() not in ('FUSELAGE','STACK'):raise ValueError('Choose a fuselage or stack section.')
    if type(surface)!=int or not 0<=surface<v.GetNumXSecSurfs(gid):raise ValueError('Choose an existing section surface.')
    surf=v.GetXSecSurf(gid,surface)
    if type(index)!=int or not 0<=index<v.GetNumXSec(surf):raise ValueError('Choose an existing section.')
    xid=v.GetXSec(surf,index);shape=v.GetXSecShape(xid)
    if shape==v.XS_POINT:return []
    area=v.GetXSecParm(xid,'Area');container=v.GetParmContainer(area)
    # Container identity comes from an actual curve-owned native parameter.
    if not v.ValidParm(area) or v.GetParmGroupName(area)!='XSecCurve':raise ValueError('Native section curve unavailable.')
    _,engine,bridge=adapter(v);function=bridge.studio_body_driver_parameters
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_bool];function.restype=ctypes.c_char_p
    result=json.loads(function(engine,container.encode(),shape==v.XS_CIRCLE))
    if isinstance(result,dict):raise ValueError(result.get('error','Native section dimensions unavailable.'))
    if len(result)!=(2 if shape==v.XS_CIRCLE else 4) or any(not v.ValidParm(p) for p in result):raise ValueError('Native section dimension list is incomplete.')
    return result


def attachment_frame(v,gid):
    if gid not in v.FindGeoms():raise ValueError('Choose an existing component.')
    _,engine,bridge=adapter(v);function=bridge.studio_attachment_frame
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p];function.restype=ctypes.c_char_p
    result=json.loads(function(engine,gid.encode()))
    if 'error' in result:raise ValueError(result['error'])
    if len(result.get('matrix',[]))!=16 or len(result.get('points',[]))!=4:raise ValueError('Native attachment frame is incomplete.')
    return result


def prop_curve_values(v,gid,curve,stations):
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper() not in ('PROP','PROPELLER'):
        raise ValueError('Choose an existing propeller.')
    from native_advanced import PROP_CURVES
    if type(curve)!=int or curve not in [getattr(v,n) for n in PROP_CURVES]:raise ValueError('Choose a native blade curve.')
    stations=list(stations)
    if not 1<=len(stations)<=10000 or any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1 for x in stations):
        raise ValueError('Choose finite radius fractions between zero and one.')
    _,engine,bridge=adapter(v);function=bridge.studio_prop_curve_values
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(ctypes.c_double),ctypes.c_int];function.restype=ctypes.c_char_p
    result=json.loads(function(engine,gid.encode(),curve,(ctypes.c_double*len(stations))(*stations),len(stations)))
    if isinstance(result,dict):raise ValueError(result.get('error','Native blade curve unavailable.'))
    if len(result)!=len(stations) or any(not math.isfinite(x) for x in result):raise ValueError('Native blade curve samples are incomplete.')
    return result


def wire_geometry(v,gid):
    """Copy native wire grids and line connectivity into the aircraft canvas."""
    if v.GetGeomTypeName(gid).upper()!='WIREFRAME':
        raise ValueError('Choose native wire geometry to preview.')
    _,engine,bridge=adapter(v);function=bridge.studio_wire_drawings
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p];function.restype=ctypes.c_char_p
    drawings=json.loads(function(engine,gid.encode()))
    if isinstance(drawings,dict):raise ValueError(drawings.get('error','Native wire drawings unavailable.'))
    surfaces=[];paths=[];isolated=[]
    def check(points):
        if any(len(p)!=3 or not all(math.isfinite(x) for x in p) for p in points):
            raise ValueError('OpenVSP returned undefined wire geometry drawing points.')
    for drawing in drawings:
        if drawing['kind']=='lines':
            points=drawing['points'];check(points)
            if len(points)%2:raise ValueError('Native wire line connectivity is incomplete.')
            paths.extend(points[i:i+2] for i in range(0,len(points),2))
        else:
            if len(drawing['normals'])!=len(drawing['points']):raise ValueError('Native wire surface normals are incomplete.')
            for grid,normal_grid in zip(drawing['points'],drawing['normals']):
                if not grid:continue
                cols=len(grid[0])
                if any(len(row)!=cols for row in grid):raise ValueError('Native wire surface grid is incomplete.')
                points=[p for row in grid for p in row];check(points)
                if not points:continue
                if len(normal_grid)!=len(grid) or any(len(row)!=cols for row in normal_grid):raise ValueError('Native wire surface normals are incomplete.')
                normals=[p for row in normal_grid for p in row];check(normals)
                if len(points)==1:isolated.extend(points)
                surfaces.append(dict(index=len(surfaces),rows=len(grid),cols=cols,points=points,
                                     normals=normals,nativeID=drawing['nativeID'],flipNormals=drawing['flipNormals'],source='WireGeom::LoadDrawObjs'))
    return dict(surfaces=surfaces,paths=paths,points=isolated,source='WireGeom::LoadDrawObjs')


def editable_activity(v,parameters,count):
    """Serialize engine activity, shared by section and region curve editors."""
    activity=parameter_activity(v,[p['id'] for p in parameters])
    for p in parameters:p['active']=activity[p['id']]
    by_name={p['name']:p['active'] for p in parameters}
    ids={p['name']:p['id'] for p in parameters}
    return dict(rounding=[v.GetParmVal(ids[f'R_{i}']) for i in range(count)],pointActivity=[[by_name[f'{axis}_{i}'] for axis in 'XYZ'] for i in range(count)],
                smoothActivity=[by_name[f'G1_{i}'] for i in range(count)],
                fixedActivity=[by_name[f'FixedU_{i}'] for i in range(count)])


def cfd_sources(v,request):
    """Read each native refinement source and all of its physical surface copies."""
    from native_tools import one
    geom=one(request.get('geom'),v.FindGeoms(),'Choose an existing component to preview.')
    _,engine,library=adapter(v);function=library.studio_cfd_sources
    function.argtypes=[ctypes.c_char_p,ctypes.c_char_p];function.restype=ctypes.c_char_p
    drawings=json.loads(function(engine,geom.encode()))
    if isinstance(drawings,dict):raise ValueError(drawings.get('error','Native CFD source drawings unavailable.'))
    sources=[]
    for i in range(v.GetNumCFDSources(geom)):
        sid=v.GetCFDSourceID(geom,i)
        sources.append(dict(id=sid,geom=geom,index=i,name=v.GetCFDSourceName(geom,i),type=v.GetCFDSourceType(geom,i),copies=[],objects=[]))
    by_id={s['id']:s for s in sources};surface_count=v.GetTotalNumSurfs(geom)
    for row in drawings:
        source=by_id.get(row['source'])
        if source is None or not 0<=row['surface']<surface_count:raise ValueError('OpenVSP returned an unknown source or surface.')
        for obj in row['objects']:
            if any(len(p)!=3 or not all(math.isfinite(x) for x in p) for p in obj['points']):raise ValueError('OpenVSP returned undefined CFD source drawing points.')
            obj['surface']=row['surface']
        source['copies'].append(row);source['objects'].extend(row['objects'])
    warnings=[s['name']+': OpenVSP returned no drawing points for this source.' for s in sources if not s['objects']]
    return dict(version=v.GetVSPVersion(),geom=geom,parts=sources,warnings=warnings,showContext=True,
                engineOperation='Geom::UpdateSources / BaseSimpleSource::LoadDrawObjs',
                filename='CFD refinement source preview',
                displayNote='OpenVSP’s native refinement-source influence outlines, including mirrored and repeated surface copies. Aircraft surfaces provide context. Target edge lengths are evaluated when the CFD mesh is generated.')


def structure(v,request):
    from native_tools import one
    sid=one(request.get('structure'),v.GetFeaStructIDVec(),'Choose an existing structure to preview.')
    geom=v.GetFeaStructParentGeomID(sid);index=v.GetFeaStructIndex(sid);parts=list(v.GetFeaPartIDVec(sid))
    function,engine,library=adapter(v)
    regions=list(v.GetFeaSubSurfIDVec(sid))
    result=json.loads(function(engine,geom.encode(),index,len(parts),len(regions)))
    if result.get('error'):raise ValueError(result['error'])
    from native_references import references
    refs=references(v) if regions else {}
    for row,pid in zip(result['parts']+result['regions'],parts+regions):
        is_region=pid in regions
        row.update(id=pid,name=v.GetFeaSubSurfName(pid) if is_region else v.GetFeaPartName(pid),
                   type=refs.get(pid,{}).get('regionType') if is_region else v.GetFeaPartType(pid),
                   isSkin=not is_region and v.GetFeaPartType(pid)==v.FEA_SKIN,isRegion=is_region)
        for obj in row['objects']:
            if any(len(p)!=3 or not all(math.isfinite(x) for x in p) for p in obj['points']):raise ValueError('OpenVSP returned undefined structural drawing points.')
    result.update(version=v.GetVSPVersion(),structure=sid,geom=geom,engineOperation='FeaStructure::Update / FeaPart::LoadDrawObjs / SubSurface::LoadDrawObjs',warnings=[])
    for part in result['parts']+result['regions']:
        if not part['objects']:result['warnings'].append(part['name']+': OpenVSP returned no drawing points for this '+('region. Configure or compute its native boundary.' if part['isRegion'] else 'part.'))
    return result


def assembly(v,request):
    from native_tools import one
    aid=one(request.get('assembly'),v.GetFeaAssemblyIDVec(),'Choose an existing structural assembly.')
    members=list(v.GetFeaAssemblyStructureIDVec(aid));parts=[];regions=[];warnings=[];geoms=[]
    for sid in members:
        drawing=structure(v,dict(structure=sid))
        geom=drawing['geom'];name=v.GetFeaStructName(geom,v.GetFeaStructIndex(sid))
        if geom not in geoms:geoms.append(geom)
        for rows,target in ((drawing['parts'],parts),(drawing['regions'],regions)):
            for row in rows:
                row.update(nativeIndex=row['index'],index=len(target),structure=sid,geom=geom,name=name+' / '+row['name']);target.append(row)
        warnings.extend(name+' / '+w for w in drawing['warnings'])
    from native_references import references
    refs=references(v);_,engine,bridge=adapter(v);fn=bridge.studio_connection_preview
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
    connections=[]
    for index in range(v.NumFeaAssemblyConnections(aid)):
        cid=v.GetFeaAssemblyConnectionID(aid,index);objects=json.loads(fn(engine,cid.encode()))
        if isinstance(objects,dict):raise ValueError(objects.get('error','Native connection drawing unavailable.'))
        if any(len(p)!=3 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in p) for o in objects for p in o['points']):raise ValueError('OpenVSP returned undefined assembly connection coordinates.')
        row=dict(id=cid,index=len(parts),nativeIndex=index,name='Connection '+str(index+1),isConnection=True,isRegion=False,objects=objects,references=refs.get(cid,{}),params=[dict(name=v.GetParmName(p),value=v.GetParmVal(p)) for p in v.FindContainerParmIDs(cid)])
        connections.append(row);parts.append(row)
        if not objects:warnings.append(row['name']+': no native drawing points. Check member fixed-point references and copy indices.')
    return dict(version=v.GetVSPVersion(),assembly=aid,members=members,geoms=geoms,parts=parts,regions=regions,connections=connections,warnings=warnings,
                filename=v.GetFeaAssemblyName(aid)+' · native construction',showContext=False,
                engineOperation='FeaStructure::Update / FeaPart::LoadDrawObjs / SubSurface::LoadDrawObjs / FeaConnection::Update / FeaConnection::LoadDrawObjs',
                displayNote='Original native member part and region drawings, plus native connection lines and selected fixed-point copies. Aircraft surfaces provide optional context. This construction preview precedes meshing; final connection nodes and constraints are generated in the native solver exports.')


def geometry_features(v,gid):
    """Original Geom drawing segments; preserve independent line connectivity."""
    _,engine,bridge=adapter(v);fn=bridge.studio_geom_features
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
    result=json.loads(fn(engine,gid.encode()))
    if isinstance(result,dict):raise ValueError(result.get('error','Native feature lines unavailable.'))
    return result


def blank_drawings(v,gid):
    """Original reference origins, symmetry axes and point-mass CG records."""
    if v.GetGeomTypeName(gid).upper()!='BLANK':raise ValueError('Choose a reference component.')
    _,engine,bridge=adapter(v);fn=bridge.studio_blank_drawings
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
    data=json.loads(fn(engine,gid.encode()))
    if isinstance(data,dict):raise ValueError(data.get('error','Native reference drawing unavailable.'))
    return data
