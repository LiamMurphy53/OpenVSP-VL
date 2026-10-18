"""Capture and restore live original native polygon graph data."""
import ctypes
import json
import math
import hashlib
import os
from pathlib import Path
import tempfile
import copy
import xml.etree.ElementTree as ET
from native_preview import adapter, _verified_private_layout
from vsp_runtime import distribution


def _target(v, gid):
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper() not in ('NGONMESH', 'NGON_MESH'):
        raise ValueError('Choose an existing native polygon mesh.')
    guard = v.FindParm(gid, 'Scale_From_Original', 'XForm')
    if not v.ValidParm(guard):
        raise ValueError('Native polygon scale parameter unavailable.')
    path = distribution()/'python/openvsp/openvsp/_vsp.so'
    stat = path.stat()
    _verified_private_layout(str(path), stat.st_size, stat.st_mtime_ns)
    _, engine, bridge = adapter(v)
    return engine, bridge, guard


def snapshot(v, gid):
    engine, bridge, guard = _target(v, gid)
    function = bridge.studio_ngon_snapshot
    function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    function.restype = ctypes.c_char_p
    result = json.loads(function(engine, gid.encode(), guard.encode()))
    if 'error' in result:
        raise ValueError(result['error'])
    return result


def triangulate(v,gid):
    """Use the same original native action as the polygon geometry screen."""
    graph=snapshot(v,gid)
    if not graph['faces']:raise ValueError('Choose a polygon mesh with geometry.')
    engine,bridge,guard=_target(v,gid);function=bridge.studio_ngon_triangulate
    function.argtypes=[ctypes.c_char_p]*3;function.restype=ctypes.c_char_p
    result=json.loads(function(engine,gid.encode(),guard.encode()))
    if 'error' in result:raise ValueError(result['error'])
    v.Update();validate(snapshot(v,gid))
    return result


def prepare_mesh(v,gid):
    """Restore original native tag-manager setup omitted by a saved triangle mesh."""
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='MESH':raise ValueError('Choose a native triangle mesh.')
    path=distribution()/'python/openvsp/openvsp/_vsp.so';stat=path.stat()
    _verified_private_layout(str(path),stat.st_size,stat.st_mtime_ns)
    guard=v.FindParm(gid,'Scale_From_Original','XForm')
    if not v.ValidParm(guard):raise ValueError('Native triangle mesh scale parameter unavailable.')
    registry=getattr(v,'_studio_mesh_tag_data',{})
    if gid in registry:
        mesh_metadata(v,gid)  # Invalidate archived tags if actual source metadata changed.
        if gid in registry:
            _,engine,bridge=adapter(v);function=bridge.studio_mesh_restore_tags
            function.argtypes=[ctypes.c_char_p]*4;function.restype=ctypes.c_char_p
            result=json.loads(function(engine,gid.encode(),guard.encode(),_payload(registry[gid]['data'])))
            if 'error' in result:raise ValueError(result['error'])
            return result
    _,engine,bridge=adapter(v);function=bridge.studio_mesh_prepare_polygon
    function.argtypes=[ctypes.c_char_p]*3;function.restype=ctypes.c_char_p
    result=json.loads(function(engine,gid.encode(),guard.encode()))
    if 'error' in result:raise ValueError(result['error'])
    return result


def mesh_metadata(v,gid):
    """Read live triangle conversion metadata without altering its native mesh."""
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='MESH':raise ValueError('Choose a native triangle mesh.')
    path=distribution()/'python/openvsp/openvsp/_vsp.so';stat=path.stat()
    _verified_private_layout(str(path),stat.st_size,stat.st_mtime_ns)
    v.GetAllSubSurfIDs()  # Original SDK initializes its singleton without changing tag tables.
    _,engine,bridge=adapter(v);function=bridge.studio_mesh_metadata
    function.argtypes=[ctypes.c_char_p]*3;function.restype=ctypes.c_char_p
    guard=v.FindParm(gid,'Scale_From_Original','XForm')
    if not v.ValidParm(guard):raise ValueError('Native triangle mesh scale parameter unavailable.')
    result=json.loads(function(engine,gid.encode(),guard.encode()))
    if 'error' in result:raise ValueError(result['error'])
    registry=getattr(v,'_studio_mesh_tag_data',{})
    if gid in registry:
        if registry[gid]['source']==_mesh_tag_signature(result):result['tagData']=copy.deepcopy(registry[gid]['data'])
        else:registry.pop(gid)
    return result


def capture_mesh(v,gid):
    """Archive tag context immediately after the original meshing operation."""
    data=mesh_metadata(v,gid)
    if not any(m['triangles'] for m in data['meshes']):return False
    validate_mesh_metadata(data)
    if not hasattr(v,'_studio_mesh_tag_data'):v._studio_mesh_tag_data={}
    v._studio_mesh_tag_data[gid]=dict(source=_mesh_tag_signature(data),data=copy.deepcopy(data['tagData']))
    return True


def mesh_project_data(v,gid):
    """Original native flattened geometry/XML plus its preserved metadata."""
    raw=mesh_metadata(v,gid)
    if gid not in getattr(v,'_studio_mesh_tag_data',{}):raise ValueError('The triangle source changed without an archived native tag context. Rebuild the source mesh before saving its metadata.')
    path=distribution()/'python/openvsp/openvsp/_vsp.so';stat=path.stat();_verified_private_layout(str(path),stat.st_size,stat.st_mtime_ns)
    _,engine,bridge=adapter(v);function=bridge.studio_mesh_project_data
    function.argtypes=[ctypes.c_char_p]*3;function.restype=ctypes.c_char_p
    result=json.loads(function(engine,gid.encode(),v.FindParm(gid,'Scale_From_Original','XForm').encode()))
    if 'error' in result:raise ValueError(result['error'])
    result['metadata']['tagData']=copy.deepcopy(raw['tagData']);validate_mesh_metadata(result['metadata'])
    kept=sum(sum(not child['ignore'] for child in t['split']) if t['split'] else not t['ignore'] for m in raw['meshes'] for t in m['triangles'])
    if sum(len(m['triangles']) for m in result['metadata']['meshes'])!=kept:raise ValueError('OpenVSP canonical mesh encoding dropped source triangles. The project was not replaced.')
    return result


def _mesh_tag_signature(data):
    # Native conversion renumbers scratch node/triangle IDs; uniform model
    # scaling changes only the separate scale matrix, not the tag definitions.
    def source(x):
        if isinstance(x,dict):return {k:source(v) for k,v in x.items() if k!='id'}
        if isinstance(x,list):return [source(v) for v in x]
        return x
    return hashlib.sha256(json.dumps(source(data['meshes']),allow_nan=False,separators=(',',':'),sort_keys=True).encode()).hexdigest()


def validate_mesh_metadata(data):
    def fail():raise ValueError('Invalid triangle metadata snapshot.')
    def fields(obj,names):
        if type(obj)!=dict or set(obj)!=set(names.split()):fail()
    def integer(x):
        if type(x)!=int or not -(2**31)<=x<2**31:fail()
    def number(x):
        if type(x) not in (int,float) or not math.isfinite(x):fail()
    def array(xs,check,count=None):
        if type(xs)!=list or count is not None and len(xs)!=count:fail()
        for x in xs:check(x)
    def boolean(x):
        if type(x)!=bool:fail()
    def text(x):
        if type(x)!=str:fail()
    def vector(xs):array(xs,number,3)
    def grid(xs):array(xs,lambda row:array(row,vector))
    total=0
    def triangle(t,depth=0):
        nonlocal total
        total+=1
        if depth>64 or total>10000000:fail()
        fields(t,'quad jref kref id ignore invalid geomID density tags inside normal corners split')
        for k in ('quad','jref','kref','id'):integer(t[k])
        for k in ('ignore','invalid'):boolean(t[k])
        text(t['geomID']);number(t['density']);array(t['tags'],integer);array(t['inside'],boolean);vector(t['normal'])
        def corner(n):
            fields(n,'xyz uw xyzFlag coordInfo intersection id');vector(n['xyz']);vector(n['uw']);boolean(n['xyzFlag'])
            for k in ('coordInfo','intersection','id'):integer(n[k])
            if not 0<=n['coordInfo']<=3:fail()
        array(t['corners'],corner,3);array(t['split'],lambda child:triangle(child,depth+1))
    try:
        fields(data,'format meshes scaleMatrix tagData');integer(data['format'])
        if data['format']!=2:fail()
        array(data['scaleMatrix'],number,16)
        def mesh(m):
            fields(m,'origin name surface plate copy material cfdType surfaceType thick flatPatch massPriority density shellAreaDensity shell wmin uscale wscale groups uwGrid xyzGrid triangles')
            for k in ('origin','name'):text(m[k])
            for k in ('surface','plate','copy','material','cfdType','surfaceType','thick','massPriority'):integer(m[k])
            for k in ('flatPatch','shell'):boolean(m[k])
            for k in ('density','shellAreaDensity','wmin','uscale','wscale'):number(m[k])
            array(m['groups'],integer);grid(m['uwGrid']);grid(m['xyzGrid'])
            if [len(row) for row in m['uwGrid']]!=[len(row) for row in m['xyzGrid']]:fail()
            array(m['triangles'],triangle)
        array(data['meshes'],mesh)
        tags=data['tagData']
        fields(tags,'names ids componentNames componentIDs types plates copies wmin uscale wscale thick currentSurface combinations keys single geometryIDs geometryCopies')
        for k in ('names','ids'):
            def pair(p):
                if type(p)!=list or len(p)!=2:fail()
                integer(p[0]);text(p[1])
            array(tags[k],pair)
            if len({p[0] for p in tags[k]})!=len(tags[k]):fail()
        for k in ('componentNames','componentIDs','geometryIDs'):array(tags[k],text)
        for k in ('types','plates','copies','thick'):array(tags[k],integer)
        for k in ('wmin','uscale','wscale'):array(tags[k],number)
        count=len(tags['componentNames'])
        if any(len(tags[k])!=count for k in ('componentIDs','types','plates','copies','thick','wmin','uscale','wscale')):fail()
        integer(tags['currentSurface'])
        for k in ('combinations','keys'):
            array(tags[k],lambda xs:array(xs,integer))
            if len({tuple(xs) for xs in tags[k]})!=len(tags[k]):fail()
        def single(p):
            if type(p)!=list or len(p)!=2:fail()
            array(p[0],integer);integer(p[1])
        array(tags['single'],single)
        lookup={tuple(xs):value for xs,value in tags['single']}
        if len(lookup)!=len(tags['single']):fail()
        def geometry_copy(p):
            if type(p)!=list or len(p)!=2:fail()
            text(p[0]);integer(p[1])
        array(tags['geometryCopies'],geometry_copy)
        if len(set(tags['geometryIDs']))!=len(tags['geometryIDs']) or len({tuple(p) for p in tags['geometryCopies']})!=len(tags['geometryCopies']):fail()
        def covered(t):
            if t['split']:
                for child in t['split']:covered(child)
            elif not t['ignore']:
                key=t['tags'];value=lookup.get(tuple(key),-1);index=value-1-(1000 if value>1000 else 0)
                if not key or not 1<=key[0]<=count or not 0<=index<len(tags['keys']) or tags['keys'][index]!=key:fail()
        for m in data['meshes']:
            for t in m['triangles']:covered(t)
    except (KeyError,TypeError,IndexError,ValueError,OverflowError,RecursionError):fail()
    return data


def restore_mesh_metadata(v,gid,data):
    validate_mesh_metadata(data)
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='MESH':raise ValueError('Choose a native triangle mesh.')
    path=distribution()/'python/openvsp/openvsp/_vsp.so';stat=path.stat();_verified_private_layout(str(path),stat.st_size,stat.st_mtime_ns)
    _,engine,bridge=adapter(v);function=bridge.studio_mesh_restore_metadata
    function.argtypes=[ctypes.c_char_p]*4;function.restype=ctypes.c_char_p
    guard=v.FindParm(gid,'Scale_From_Original','XForm')
    if not v.ValidParm(guard):raise ValueError('Native triangle mesh scale parameter unavailable.')
    result=json.loads(function(engine,gid.encode(),guard.encode(),_payload(data)))
    if 'error' in result:raise ValueError(result['error'])
    if not hasattr(v,'_studio_mesh_tag_data'):v._studio_mesh_tag_data={}
    v._studio_mesh_tag_data[gid]=dict(source=_mesh_tag_signature(data),data=copy.deepcopy(data['tagData']))
    return result


def validate(data):
    """Validate pointer-free graph ownership and reciprocal references before native allocation."""
    def fail():raise ValueError('Invalid polygon graph snapshot.')
    def integer(x):
        if type(x)!=int or not -(2**31)<=x<2**31:fail()
    def numbers(xs,count):
        if not isinstance(xs,list) or len(xs)!=count:fail()
        for x in xs:
            if type(x) not in (int,float) or not math.isfinite(x):fail()
    def refs(xs,n,nullable=False):
        if not isinstance(xs,list):fail()
        for x in xs:
            integer(x)
            if not (-1 if nullable else 0)<=x<n:fail()
    def fields(obj,names):
        if type(obj)!=dict or set(obj)!=set(names.split()):fail()
    def unique(xs):
        if len(set(xs))!=len(xs):fail()
    try:
        fields(data,'format activeMesh points nodes edges faces meshes tagNames tagIDs thick type plate copyIndex wmin uscale wscale tagKeys singleTagMap scaleMatrix')
        integer(data['format'])
        if data['format']!=1:fail()
        points,nodes,edges,faces,meshes=(data[k] for k in ('points','nodes','edges','faces','meshes'))
        if not all(isinstance(xs,list) for xs in (points,nodes,edges,faces,meshes)):fail()
        if sum(map(len,(points,nodes,edges,faces,meshes)))>10000000:fail()
        integer(data['activeMesh'])
        if not 0<=data['activeMesh']<len(meshes):fail()
        numbers(data['scaleMatrix'],16)
        for p in points:
            fields(p,'xyz id deleted nodes')
            numbers(p['xyz'],3);integer(p['id']);refs(p['nodes'],len(nodes))
            unique(p['nodes'])
        for n in nodes:
            fields(n,'point deleted edges tagUW')
            refs([n['point']],len(points));refs(n['edges'],len(edges))
            unique(n['edges'])
            if not isinstance(n['tagUW'],list):fail()
            for tag,uv in n['tagUW']:integer(tag);numbers(uv,2)
            if len({pair[0] for pair in n['tagUW']})!=len(n['tagUW']):fail()
        for e in edges:
            fields(e,'nodes id deleted inLoop inCurrentLoop faces')
            if len(e['nodes'])!=2 or e['nodes'][0]==e['nodes'][1]:fail()
            refs(e['nodes'],len(nodes));refs(e['faces'],len(faces));integer(e['id'])
            unique(e['faces'])
            for k in ('inLoop','inCurrentLoop'):
                if type(e[k])!=bool:fail()
        for f in faces:
            fields(f,'normal id quad tag jref kref region deleted parent edges triNodes children')
            numbers(f['normal'],3)
            for k in ('id','quad','tag','jref','kref','region'):integer(f[k])
            refs([f['parent']],len(faces),True);refs(f['edges'],len(edges));refs(f['triNodes'],len(nodes));refs(f['children'],len(faces))
            if len(f['edges'])<3 or len(f['triNodes'])%3:fail()
            unique(f['edges']);unique(f['children'])
        owners={k:{} for k in ('nodes','edges','faces')}
        for i,m in enumerate(meshes):
            fields(m,'deleted nodes edges faces doubleBackNodes edgeLoops wingWakes wingWakeParts bodyWakes bodyWakeParts bodyWakeNodes bodyWakeNodeParts regions')
            for k,xs in (('nodes',nodes),('edges',edges),('faces',faces)):
                refs(m[k],len(xs))
                for j in m[k]:
                    if j in owners[k]:fail()
                    owners[k][j]=i
            for k in ('edgeLoops','wingWakes','bodyWakes'):
                if not isinstance(m[k],list):fail()
                for loop in m[k]:refs(loop,len(edges))
            refs(m['doubleBackNodes'],len(nodes));refs(m['bodyWakeNodes'],len(nodes));refs(m['regions'],len(faces))
            for a,b in (('wingWakes','wingWakeParts'),('bodyWakes','bodyWakeParts'),('bodyWakeNodes','bodyWakeNodeParts')):
                if len(m[a])!=len(m[b]):fail()
                for x in m[b]:integer(x)
        for k,xs in (('nodes',nodes),('edges',edges),('faces',faces)):
            if set(owners[k])!=set(range(len(xs))):fail()
        for i,p in enumerate(points):
            for n in p['nodes']:
                if nodes[n]['point']!=i:fail()
        for i,n in enumerate(nodes):
            if i not in points[n['point']]['nodes']:fail()
            for e in n['edges']:
                if i not in edges[e]['nodes']:fail()
        for i,e in enumerate(edges):
            for n in e['nodes']:
                if i not in nodes[n]['edges'] or owners['nodes'][n]!=owners['edges'][i]:fail()
            for f in e['faces']:
                if i not in faces[f]['edges']:fail()
        for i,f in enumerate(faces):
            for e in f['edges']:
                if i not in edges[e]['faces'] or owners['faces'][i]!=owners['edges'][e]:fail()
        for xs in (points,nodes,edges,faces,meshes):
            for obj in xs:
                if type(obj['deleted'])!=bool or obj['deleted']:fail()
        for k in ('thick','type','plate','copyIndex'):
            if not isinstance(data[k],list):fail()
            for x in data[k]:integer(x)
        for k in ('wmin','uscale','wscale'):numbers(data[k],len(data[k]))
        for k in ('tagNames','tagIDs'):
            if not isinstance(data[k],list):fail()
            for i,text in data[k]:
                integer(i)
                if not isinstance(text,str):fail()
            if len({x[0] for x in data[k]})!=len(data[k]):fail()
        if not isinstance(data['tagKeys'],list) or not isinstance(data['singleTagMap'],list):fail()
        for xs in data['tagKeys']:
            if not isinstance(xs,list):fail()
            for x in xs:integer(x)
        for xs,i in data['singleTagMap']:
            if not isinstance(xs,list):fail()
            integer(i)
            for x in xs:integer(x)
        unique([tuple(xs) for xs,i in data['singleTagMap']])
    except (KeyError,TypeError,IndexError,OverflowError,ValueError):fail()
    return data


def _payload(data):
    root=ET.Element('snapshot')
    def put(node,value):
        if isinstance(value,dict):
            for key,val in value.items():put(ET.SubElement(node,key),val)
        elif isinstance(value,list):
            for val in value:put(ET.SubElement(node,'item'),val)
        elif isinstance(value,str):node.text=value.encode().hex()
        elif type(value)==bool:node.text='1' if value else '0'
        else:node.text=repr(value)
    put(root,data);payload=ET.tostring(root,encoding='utf-8')
    if len(payload)>128*1024*1024:raise ValueError('Polygon snapshot exceeds the restore limit.')
    return payload


def restore(v,gid,data):
    validate(data)
    payload=_payload(data)
    engine,bridge,guard=_target(v,gid);function=bridge.studio_ngon_restore
    function.argtypes=[ctypes.c_char_p]*4;function.restype=ctypes.c_char_p
    result=json.loads(function(engine,gid.encode(),guard.encode(),payload))
    if 'error' in result:raise ValueError(result['error'])
    # The native constructor exposes levels 0..10 even when only level 0
    # exists. GetActiveMesh indexes its vector without a bounds check.
    active=v.FindParm(gid,'ActiveMesh','RefMesh')
    v.SetParmUpperLimit(active,len(data['meshes'])-1)
    v.SetParmVal(active,data['activeMesh'])
    return result


def write(v,path):
    """Keep native VSP3 parameters and Studio's full polygon graph in one file."""
    path=Path(path)
    graphs={g:snapshot(v,g) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper() in ('NGONMESH','NGON_MESH')}
    triangles={g:mesh_project_data(v,g) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='MESH' and g in getattr(v,'_studio_mesh_tag_data',{})}
    if not graphs and not triangles:
        v.WriteVSPFile(str(path),v.SET_ALL)
        return
    for data in graphs.values():validate(data)
    filename=v.GetVSPFileName()
    fd,name=tempfile.mkstemp(prefix='.studio-polygons-',suffix='.vsp3',dir=path.parent)
    os.close(fd);temporary=Path(name)
    try:
        v.WriteVSPFile(str(temporary),v.SET_ALL)
        tree=ET.parse(temporary);found=set()
        for geom in tree.findall('./Vehicle/Geom'):
            gid=geom.findtext('./ParmContainer/ID')
            if gid not in graphs and gid not in triangles:continue
            if gid in found:raise ValueError('Native mesh file identity is inconsistent.')
            found.add(gid)
            if gid in graphs:
                if geom.find('NGonMeshGeom') is None:raise ValueError('Native polygon file identity is inconsistent.')
                data=graphs[gid];tag='StudioPolygonSnapshot';version='1'
            else:
                previous=geom.find('MeshGeom')
                if previous is None:raise ValueError('Native triangle file identity is inconsistent.')
                canonical=ET.fromstring(triangles[gid]['xml'])
                if canonical.tag!='MeshGeom':raise ValueError('OpenVSP did not encode the native triangle mesh.')
                index=list(geom).index(previous);geom.remove(previous);geom.insert(index,canonical)
                data=triangles[gid]['metadata'];tag='StudioTriangleMetadata';version='2'
            text=json.dumps(data,allow_nan=False,ensure_ascii=True,separators=(',',':'))
            if len(text)>128*1024*1024:raise ValueError('Polygon snapshot exceeds the project limit.')
            ET.SubElement(geom,tag,format=version,sha256=hashlib.sha256(text.encode()).hexdigest()).text=text
        if found!=(set(graphs)|set(triangles)):raise ValueError('OpenVSP did not save every mesh component.')
        tree.write(temporary,encoding='utf-8',xml_declaration=True)
        os.replace(temporary,path);v.SetVSP3FileName(str(path))
    except BaseException:
        v.SetVSP3FileName(filename)
        raise
    finally:temporary.unlink(missing_ok=True)


def restore_file(v,path):
    """Restore Studio extension data after an ordinary original-engine VSP3 read."""
    raw=Path(path).read_bytes()
    if b'<StudioPolygonSnapshot' not in raw and b'<StudioTriangleMetadata' not in raw:return []
    tree=ET.ElementTree(ET.fromstring(raw));pending={};triangle_pending={}
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate polygon snapshot field.')
            result[key]=value
        return result
    for geom in tree.findall('./Vehicle/Geom'):
        triangle_entries=geom.findall('StudioTriangleMetadata')
        if triangle_entries:
            gid=geom.findtext('./ParmContainer/ID');entry=triangle_entries[0];text=entry.text or ''
            if len(triangle_entries)!=1 or not gid or gid in triangle_pending or geom.find('MeshGeom') is None or geom.find('NGonMeshGeom') is not None:raise ValueError('Invalid saved triangle component identity.')
            if entry.get('format')!='2' or len(text)>128*1024*1024 or hashlib.sha256(text.encode()).hexdigest()!=entry.get('sha256'):raise ValueError('Saved triangle metadata is corrupt or unsupported.')
            data=json.loads(text,object_pairs_hook=pairs);validate_mesh_metadata(data)
            if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper()!='MESH':raise ValueError('Saved triangle metadata has no native mesh owner.')
            triangle_pending[gid]=data
        entries=geom.findall('StudioPolygonSnapshot')
        if not entries:continue
        gid=geom.findtext('./ParmContainer/ID');entry=entries[0];text=entry.text or ''
        if len(entries)!=1 or not gid or gid in pending or geom.find('NGonMeshGeom') is None:raise ValueError('Invalid saved polygon component identity.')
        if entry.get('format')!='1' or len(text)>128*1024*1024 or hashlib.sha256(text.encode()).hexdigest()!=entry.get('sha256'):raise ValueError('Saved polygon snapshot is corrupt or unsupported.')
        data=json.loads(text,object_pairs_hook=pairs);validate(data)
        _target(v,gid);pending[gid]=data
    # Validate every component before changing any native graph. Worker-level
    # rollback still protects the project if a later native restoration fails.
    for gid,data in pending.items():restore(v,gid,data)
    for gid,data in triangle_pending.items():restore_mesh_metadata(v,gid,data)
    if pending or triangle_pending:v.Update()
    return list(pending)+list(triangle_pending)
