"""Native point-cloud transforms and safe directional projection.

The release exposes local points but no cloud transform matrix. Temporary
Blank children let OpenVSP evaluate the parent's origin and three axes,
including hierarchy and attachment. Matrix operations and ray/surface math
remain native. No temporary geometry is saved in the user's aircraft.
"""
import math
import os
import xml.etree.ElementTree as ET
from native_references import document,ReloadRequired


def transform(v,g):
    probes=[];axes=[]
    try:
        for point in [(0,0,0),(1,0,0),(0,1,0),(0,0,1)]:
            child=v.AddGeom('BLANK',g);probes.append(child)
            parms={v.GetParmName(p):p for p in v.GetGeomParmIDs(child)}
            for name,value in [('Trans_Attach_Flag',v.ATTACH_TRANS_COMP),('Rots_Attach_Flag',v.ATTACH_ROT_COMP),('X_Rel_Location',point[0]),('Y_Rel_Location',point[1]),('Z_Rel_Location',point[2])]:v.SetParmValUpdate(parms[name],value)
            axes.append(v.vec3d(*[v.GetParmVal(parms[n]) for n in ['X_Location','Y_Location','Z_Location']]))
        matrix=v.Matrix4d();matrix.loadIdentity();matrix.translatev(axes[0]);matrix.setBasis(*[p-axes[0] for p in axes[1:]])
        # Match PtCloudGeom::GetTotalTransMat's native multiplication order.
        scaled=v.Matrix4d();scaled.loadIdentity();scaled.scale(v.GetParmVal(g,'Scale_From_Original','XForm'));scaled.postMult(matrix)
        return scaled
    finally:
        for child in reversed(probes):v.DeleteGeom(child)
        v.Update()


def world_points(v,g):
    matrix=transform(v,g)
    return [matrix.xform(p) for p in v.GetPtCloudPnts(g)]


def project(v,g,target,surface,direction):
    matrix=transform(v,g);inverse=v.Matrix4d();inverse.initMat(matrix);inverse.affineInverse();points=[]
    for local in v.GetPtCloudPnts(g):
        distance,u,w=v.AxisProjPnt01(target,surface,direction,matrix.xform(local))
        # The release's ProjectPtCloudPts dereferences invalid UV on a ray miss.
        # Use the native ray query and keep misses untouched, as its API documents.
        if distance>=0 and all(math.isfinite(x) and 0<=x<=1 for x in [u,w]):points.append(inverse.xform(v.CompPnt01(target,surface,u,w)))
        else:points.append(local)
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
