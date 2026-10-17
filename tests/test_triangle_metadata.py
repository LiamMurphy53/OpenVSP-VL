"""Read original live triangle metadata that native VSP3 does not preserve."""
from collections import Counter
import ctypes
import json
import sys
import unittest
import native_files
import native_ngon
from native_preview import adapter
import test_native


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeTriangleMetadata(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown

    def fixture(self,kind):
        v=self.v;v.ClearVSPModel();v.AddGeom(kind);v.Update()
        return v.ComputeCompGeom(v.SET_ALL,False,0)

    def test_readonly_corners_match_original_native_display_and_live_conversion(self):
        v=self.v
        for kind,expected_faces in [('POD',144),('WING',448)]:
            with self.subTest(kind=kind):
                gid=self.fixture(kind);v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
                parameters={p:v.GetParmVal(p) for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)}
                data=native_ngon.mesh_metadata(v,gid)
                self.assertEqual(data,native_ngon.mesh_metadata(v,gid))
                self.assertEqual(json.loads(json.dumps(data,allow_nan=False)),data)
                self.assertEqual(self.model.read_bytes(),before)
                self.assertEqual({p:v.GetParmVal(p) for g in v.FindGeoms() for p in v.GetGeomParmIDs(g)},parameters)
                tris=[t for m in data['meshes'] for t in m['triangles']]
                self.assertTrue(tris);self.assertTrue(all(t['quad']>=0 for t in tris))
                self.assertTrue(all(not t['split'] for t in tris))
                display=native_files.mesh_geometry(v,gid)
                expected=Counter(tuple(display['points'][i]) for face in display['triangles'] for i in face)
                self.assertEqual(Counter(tuple(n['xyz']) for t in tris for n in t['corners']),expected)
                self.assertTrue(all(len(n['uw'])==3 for t in tris for n in t['corners']))
                self.assertTrue(all(m['origin'] in v.FindGeoms() for m in data['meshes']))
                ngon=v.CreateNGonMeshGeom(gid)
                self.assertEqual(len(native_ngon.snapshot(v,ngon)['faces']),expected_faces)

    def test_native_cold_file_loses_quad_uv_attributes_but_keeps_scale_matrix(self):
        v=self.v;gid=self.fixture('POD');v.SetParmValUpdate(gid,'Scale','XForm',1.7)
        live=native_ngon.mesh_metadata(v,gid);v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        cold=native_ngon.mesh_metadata(v,gid)
        a=[t for m in live['meshes'] for t in m['triangles']];b=[t for m in cold['meshes'] for t in m['triangles']]
        self.assertEqual(len(a),len(b));self.assertTrue(all(t['quad']>=0 for t in a));self.assertTrue(all(t['quad']==-1 for t in b))
        self.assertEqual([[c['xyz'] for c in t['corners']] for t in a],[[c['xyz'] for c in t['corners']] for t in b])
        self.assertNotEqual([[c['uw'] for c in t['corners']] for t in a],[[c['uw'] for c in t['corners']] for t in b])
        self.assertNotEqual(live['meshes'][0]['origin'],cold['meshes'][0]['origin'])
        self.assertEqual(live['scaleMatrix'],cold['scaleMatrix'])
        self.assertEqual(self.model.read_bytes(),before)

    def test_wrong_geometry_and_native_layout_guard_reject(self):
        v=self.v
        with self.assertRaisesRegex(ValueError,'triangle mesh'):native_ngon.mesh_metadata(v,self.gid)
        gid=self.fixture('POD');before=native_ngon.mesh_metadata(v,gid)
        _,engine,bridge=adapter(v);f=bridge.studio_mesh_metadata;f.argtypes=[ctypes.c_char_p]*3;f.restype=ctypes.c_char_p
        result=json.loads(f(engine,gid.encode(),v.FindParm(gid,'Scale','XForm').encode()))
        self.assertIn('layout does not match',result['error']);self.assertEqual(native_ngon.mesh_metadata(v,gid),before)
