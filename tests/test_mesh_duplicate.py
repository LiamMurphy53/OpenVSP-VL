"""Duplicate retains complete mesh payloads around native clipboard parameters."""
import json
import sys
import unittest
import xml.etree.ElementTree as ET
import native_ngon
import native_files
import test_native
import test_triangle_project


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeMeshDuplicate(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    @staticmethod
    def graph(path,gid,tag):
        geom=next(g for g in ET.parse(path).findall('./Vehicle/Geom') if g.findtext('ParmContainer/ID')==gid)
        return json.loads(geom.findtext(tag))

    def fixture(self,polygon=False):
        v=self.v;mesh=v.ComputeCompGeom(v.SET_ALL,False,0);native_ngon.capture_mesh(v,mesh)
        gid=native_ngon.convert(v,mesh,levels=2) if polygon else mesh
        if polygon:v.SetParmValUpdate(gid,'ActiveMesh','RefMesh',2)
        parent=v.AddGeom('BLANK');v.SetGeomParent(gid,parent)
        for name,value in [('X_Rel_Location',3.125),('Z_Rel_Rotation',17),('Scale',1.7)]:v.SetParmValUpdate(gid,name,'XForm',value)
        native_files.mesh_geometry(v,gid);native_ngon.write(v,self.model)
        return gid,parent

    def test_multilevel_polygon_duplicate_edit_and_reopen_preserve_source_and_graph(self):
        v=self.v;gid,parent=self.fixture(True);before=self.model.read_bytes();expected=self.graph(self.model,gid,'StudioPolygonSnapshot')
        state,path=self.worker(dict(action='mutate',operation='duplicate',geom=gid))
        clone=state['changed'];self.assertNotEqual(clone,gid)
        for g in [gid,clone]:self.assertEqual(self.graph(path,g,'StudioPolygonSnapshot'),expected)
        a,b=[next(c for c in state['components'] if c['id']==g) for g in [gid,clone]]
        self.assertEqual(a['mesh'],b['mesh']);self.assertEqual(b['parent'],parent)
        self.assertFalse(set(p['id'] for p in a['params'])&set(p['id'] for p in b['params']))
        pid=next(p['id'] for p in b['params'] if p['name']=='X_Rel_Location' and p['rawGroup']=='XForm')
        edited,output=self.worker(dict(action='mutate',operation='parameter',id=pid,value=8.75),path)
        self.assertEqual(self.graph(output,gid,'StudioPolygonSnapshot'),expected)
        reopened,_=self.worker(dict(action='state'),output)
        self.assertEqual(next(c for c in reopened['components'] if c['id']==clone)['mesh'],next(c for c in edited['components'] if c['id']==clone)['mesh'])
        self.assertEqual(self.model.read_bytes(),before)

    def test_triangle_duplicate_retains_conversion_context_and_original_geometry(self):
        v=self.v;gid,parent=self.fixture();before=self.model.read_bytes();expected=self.graph(self.model,gid,'StudioTriangleMetadata')
        state,path=self.worker(dict(action='mutate',operation='duplicate',geom=gid))
        clone=state['changed'];self.assertNotEqual(clone,gid)
        for g in [gid,clone]:self.assertEqual(self.graph(path,g,'StudioTriangleMetadata'),expected)
        a,b=[next(c for c in state['components'] if c['id']==g) for g in [gid,clone]]
        self.assertEqual(a['mesh'],b['mesh']);self.assertEqual(b['parent'],parent)
        converted,output=self.worker(dict(action='mutate',operation='mesh-to-polygon',geom=clone),path)
        actual=self.graph(output,converted['changed'],'StudioPolygonSnapshot')
        native_ngon.prepare_mesh(v,gid);reference=v.CreateNGonMeshGeom(gid);direct=native_ngon.snapshot(v,reference)
        canonical=test_triangle_project.NativeTriangleProject.canonical
        self.assertEqual(canonical(actual),canonical(direct));self.assertEqual(len(actual['faces']),448)
        self.worker(dict(action='state'),output)
        self.assertEqual(self.model.read_bytes(),before)
