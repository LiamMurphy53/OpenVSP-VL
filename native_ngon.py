"""Capture and restore live original native polygon graph data."""
import ctypes
import json
import math
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
    return result
