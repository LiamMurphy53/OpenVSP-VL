"""Original point-cloud transforms and safe native directional projection."""
import math
import os
import xml.etree.ElementTree as ET
from native_references import document,ReloadRequired


def transform_points(v,g,points,inverse=False):
    import ctypes,json,native_preview
    if g not in v.FindGeoms() or v.GetGeomTypeName(g).upper() not in ('PTCLOUD','POINTCLOUD','POINT_CLOUD'):raise ValueError('Choose an existing native point cloud.')
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_cloud_transform
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.POINTER(ctypes.c_double),ctypes.c_int,ctypes.c_bool];fn.restype=ctypes.c_char_p
    coordinates=(ctypes.c_double*(3*len(points)))(*(x for p in points for x in (p.x(),p.y(),p.z())))
    result=json.loads(fn(engine,g.encode(),coordinates,len(points),inverse))
    if isinstance(result,dict):raise ValueError(result.get('error','Native point-cloud transform unavailable.'))
    return [v.vec3d(*p) for p in result]


def world_points(v,g):
    return transform_points(v,g,list(v.GetPtCloudPnts(g)))


def project(v,g,target,surface,direction):
    points=list(v.GetPtCloudPnts(g));world=transform_points(v,g,points);hits=[];positions=[]
    for i,point in enumerate(world):
        distance,u,w=v.AxisProjPnt01(target,surface,direction,point)
        # The release's ProjectPtCloudPts dereferences invalid UV on a ray miss.
        # Use the native ray query and keep misses untouched, as its API documents.
        if distance>=0 and all(math.isfinite(x) and 0<=x<=1 for x in [u,w]):
            hits.append(v.CompPnt01(target,surface,u,w));positions.append(i)
    for i,point in zip(positions,transform_points(v,g,hits,inverse=True)):points[i]=point
    filename=v.GetVSPFileName();path,tree=document(v)
    try:
        matches=[node for node in tree.findall('.//Vehicle/Geom') if node.findtext('ParmContainer/ID')==g]
        if len(matches)!=1:raise ValueError('The point cloud no longer exists.')
        cloud=matches[0].find('PtCloudGeom')
        if cloud is None:raise ValueError('The native point-cloud data is missing.')
        for node in list(cloud):cloud.remove(node)
        rows=ET.SubElement(cloud,'Pt_List')
        for p in points:ET.SubElement(rows,'Pt').text=', '.join(format(x,'.18e') for x in [p.x(),p.y(),p.z()])+', '
        tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
    finally:path.unlink(missing_ok=True)
    raise ReloadRequired()


def refresh(v):
    """Rebuild the native scale matrix omitted by PtCloudGeom::DecodeXml."""
    import ctypes,json,native_preview
    clouds=[g for g in v.FindGeoms() if v.GetGeomTypeName(g).upper() in ('PTCLOUD','POINTCLOUD','POINT_CLOUD')]
    if not clouds:return
    _,engine,bridge=native_preview.adapter(v);fn=bridge.studio_cloud_refresh
    fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p];fn.restype=ctypes.c_char_p
    for g in clouds:
        result=json.loads(fn(engine,g.encode()))
        if result.get('error'):raise ValueError(result['error'])
