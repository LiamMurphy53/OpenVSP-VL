"""The modern conversion action uses original native polygonization."""
import json
import sys
import unittest
import xml.etree.ElementTree as ET
import test_native
import native_files
import native_ngon


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativePolygonConversion(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    def worker(self,request,model=None):
        try:return test_native.NativeIntegration.worker(self,request,model)
        except FileNotFoundError:
            logs=[p.read_text() for p in self.path.glob('*/log.txt')]
            self.fail('Native worker exited without a response:\n'+'\n'.join(logs))

    def test_native_conversion_graph_preview_and_cold_project_match_original_sdk(self):
        v=self.v
        for kind in ('POD','WING'):
            with self.subTest(kind=kind):
                v.ClearVSPModel();source=v.AddGeom(kind);v.Update()
                mesh=v.ComputeCompGeom(v.SET_ALL,False,0)
                self.assertIn(mesh,v.FindGeoms());self.assertEqual(v.GetGeomTypeName(mesh).upper(),'MESH')
                for name,value in [('Scale',1.3),('X_Rel_Location',3.125),('Z_Rel_Rotation',17)]:v.SetParmValUpdate(mesh,name,'XForm',value)
                v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
                native_ngon.prepare_mesh(v,mesh)
                direct=v.CreateNGonMeshGeom(mesh);expected_graph=native_ngon.snapshot(v,direct)
                expected=native_files.mesh_geometry(v,direct)
                state,path=self.worker(dict(action='mutate',operation='mesh-to-polygon',geom=mesh))
                gid=state['changed'];self.assertNotIn(gid,[source,mesh])
                self.assertEqual(set(c['id'] for c in state['components']),{source,mesh,gid})
                component=next(c for c in state['components'] if c['id']==gid)
                self.assertEqual(component['mesh'],expected)
                node=next(g for g in ET.parse(path).findall('./Vehicle/Geom') if g.findtext('ParmContainer/ID')==gid)
                actual_graph=json.loads(node.findtext('StudioPolygonSnapshot'))
                # Native merge cleanup orders adjacency by pointer addresses;
                # normalize only those unordered neighbor lists across processes.
                for graph in (actual_graph,expected_graph):
                    for record in graph['points']:record['nodes'].sort()
                    for record in graph['nodes']:record['edges'].sort()
                    for record in graph['edges']:record['faces'].sort()
                for key in expected_graph:self.assertEqual(actual_graph[key],expected_graph[key],key)
                reopened,_=self.worker(dict(action='state'),path)
                self.assertEqual(next(c for c in reopened['components'] if c['id']==gid)['mesh'],expected)
                self.assertEqual(self.model.read_bytes(),before)

    def test_nonmesh_and_missing_mesh_reject_without_changing_source(self):
        v=self.v;before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'triangle mesh'):self.worker(dict(action='mutate',operation='mesh-to-polygon',geom=self.gid))
        self.assertEqual(self.model.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'component'):self.worker(dict(action='mutate',operation='mesh-to-polygon',geom='missing'))
        self.assertEqual(self.model.read_bytes(),before)

    def test_empty_saved_triangle_mesh_rejects_before_native_conversion(self):
        v=self.v;v.ClearVSPModel();v.AddGeom('POD');v.Update();gid=v.ComputeCompGeom(v.SET_ALL,False,0);v.WriteVSPFile(str(self.model),v.SET_ALL)
        tree=ET.parse(self.model)
        for mesh in tree.findall('./Vehicle/Geom/MeshGeom/TMesh'):
            mesh.find('Num_Tris').text='0';mesh.find('Tri_List').clear()
        tree.write(self.model);before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'mesh with geometry'):self.worker(dict(action='mutate',operation='mesh-to-polygon',geom=gid))
        self.assertEqual(self.model.read_bytes(),before)
