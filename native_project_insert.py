"""Original project-geometry insertion with checked Studio mesh payloads."""
import copy
import hashlib
import json
from pathlib import Path
import re
import secrets
import string
import uuid
import xml.etree.ElementTree as ET
import native_ngon


def remap_mesh(data,mapping,triangle=False):
    data=copy.deepcopy(data)
    pattern=re.compile(r'(?<![A-Za-z0-9])(?:'+ '|'.join(re.escape(k) for k in sorted(mapping,key=len,reverse=True))+r')(?![A-Za-z0-9])') if mapping else None
    def reference(value):return pattern.sub(lambda m:mapping[m[0]],value) if pattern else value
    if triangle:
        for mesh in data['meshes']:
            mesh['origin']=mapping.get(mesh['origin'],mesh['origin'])
            def triangles(items):
                for t in items:
                    t['geomID']=mapping.get(t['geomID'],t['geomID']);triangles(t['split'])
            triangles(mesh['triangles'])
        tags=data['tagData']
        tags['ids']=[[k,reference(value)] for k,value in tags['ids']]
        tags['componentIDs']=[reference(value) for value in tags['componentIDs']]
        tags['geometryIDs']=[mapping.get(value,value) for value in tags['geometryIDs']]
        tags['geometryCopies']=[[mapping.get(value,value),index] for value,index in tags['geometryCopies']]
    else:data['tagIDs']=[[k,reference(value)] for k,value in data['tagIDs']]
    return data


def insert(v,raw,parent=''):
    tree=ET.ElementTree(ET.fromstring(raw));root=tree.getroot()
    if root.tag!='Vsp_Geometry':raise ValueError('Choose an OpenVSP .vsp3 project.')
    geoms=tree.findall('./Vehicle/Geom')
    if not geoms:raise ValueError('The project contains no geometry to insert.')
    ids=[g.findtext('ParmContainer/ID') for g in geoms]
    if not all(ids) or len(set(ids))!=len(ids):raise ValueError('The project has missing or duplicate geometry identities.')
    pending=[];marker='Studio.InsertMapping.'+uuid.uuid4().hex;expected=set(ids)
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('Duplicate saved mesh field.')
            out[key]=value
        return out
    def attribute_id():return ''.join(secrets.choice(string.ascii_uppercase) for _ in range(9))
    for geom,gid in zip(geoms,ids):
        for tag,version,validator in [('StudioPolygonSnapshot','1',native_ngon.validate),('StudioTriangleMetadata','2',native_ngon.validate_mesh_metadata)]:
            entries=geom.findall(tag)
            if not entries:continue
            entry=entries[0];text=entry.text or '';triangle=tag=='StudioTriangleMetadata'
            if len(entries)!=1 or entry.get('format')!=version or len(text)>128*1024*1024 or hashlib.sha256(text.encode()).hexdigest()!=entry.get('sha256'):raise ValueError('Saved mesh data is corrupt or unsupported.')
            if geom.find('MeshGeom' if triangle else 'NGonMeshGeom') is None:raise ValueError('Saved mesh has no matching native geometry owner.')
            data=json.loads(text,object_pairs_hook=pairs);validator(data);pending.append((gid,triangle,data))
            if not triangle:
                active=geom.find('.//RefMesh/ActiveMesh')
                if active is None:raise ValueError('Saved polygon has no active-level parameter.')
                active.set('Value','0')
        # Native attribute decoding supplies the engine's actual new object IDs.
        # Mark only references used by mesh source/tag records; user names stay
        # untouched and the native reader handles all other native references.
        owners=[(geom.find('ParmContainer'),v.ATTROBJ_GEOM)]
        owners += [(s.find('ParmContainer'),v.ATTROBJ_SUBSURF) for s in geom.iter('SubSurface')]
        for container,kind in owners:
            if container is None:continue
            old=container.findtext('ID')
            if not old:raise ValueError('Inserted native object is missing its identity.')
            collection=container.find('AttributeCollection')
            if collection is None:collection=ET.SubElement(container,'AttributeCollection',ID=attribute_id(),AttachID=old,AttachType=str(kind))
            ET.SubElement(collection,'Attribute',ID=attribute_id(),AttachID=collection.get('ID'),Name=marker,Type=str(v.STRING_DATA),EventGroup='0',StrData=old,Desc='',Protection='0')
    path=Path.cwd()/('insert-'+uuid.uuid4().hex+'.vsp3');tree.write(path,encoding='utf-8',xml_declaration=True)
    readable=path;markers=[]
    try:
        import native_custom_assets
        readable=native_custom_assets.prepare(v,path)
        before=set(v.FindGeoms());v.InsertVSPFile(str(readable),parent)
        added=set(v.FindGeoms())-before
        if not before<=set(v.FindGeoms()):raise ValueError('Native insertion removed existing geometry.')
        mapping={}
        markers=[a for a in v.FindAllAttributes() if v.GetAttributeName(a)==marker]
        owners=list(added)+[sid for gid in added for sid in v.GetSubSurfIDVec(gid)]
        for owner in owners:
            for attr in v.FindAttributesInCollection(v.GetChildCollection(owner)):
                if v.GetAttributeName(attr)!=marker:continue
                old=list(v.GetAttributeStringVal(attr))
                if len(old)!=1 or old[0] in mapping:raise ValueError('Native insertion produced ambiguous object identities.')
                mapping[old[0]]=owner
        if not expected<=set(mapping) or any(mapping[g] not in added for g in ids):raise ValueError('OpenVSP did not identify every inserted component.')
        for old,triangle,data in pending:
            target=mapping[old];data=remap_mesh(data,mapping,triangle)
            if triangle:native_ngon.restore_mesh_metadata(v,target,data)
            else:native_ngon.restore(v,target,data)
        for attr in markers:v.DeleteAttribute(attr)
        markers=[];v.Update()
        roots=[mapping[g] for g in ids if v.GetGeomParent(mapping[g]) not in added]
        if parent and any(v.GetGeomParent(g)!=parent for g in roots):raise ValueError('OpenVSP did not apply the requested insertion parent.')
        return roots[0] if roots else mapping[ids[0]]
    finally:
        for attr in markers:v.DeleteAttribute(attr)
        if readable!=path:readable.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
