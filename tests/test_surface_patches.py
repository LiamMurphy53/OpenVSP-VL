"""Native structured patch grids, hierarchy and normals remain exact."""
import unittest,sys,json
import test_native,test_guides,test_degenerate
from vsp_runtime import load
import native_surface_patches

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeSurfacePatches(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    fixture=test_guides.NativeGuides.fixture
    direct=test_guides.NativeGuides.direct
    canonical=test_degenerate.NativeDegenerate.canonical
    assertResults=test_degenerate.NativeDegenerate.assertResults

    def test_hierarchy_coordinates_normals_and_empty_native_sets(self):
        self.fixture();v=self.v;v.SetParmValUpdate(v.FindParm(self.gid,'Z_Rel_Location','XForm'),2.);v.SetParmValUpdate(v.FindParm(self.gid,'X_Rel_Rotation','XForm'),17.);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);baseline=self.model.read_bytes()
        for selection in (0,3,4,-1,20):
            with self.subTest(selection=selection):
                expected=self.direct('SurfacePatches',dict(Set=[selection]));data,path=self.worker(dict(action='analysis',name='SurfacePatches',inputs=[dict(name='Set',values=[selection])]))
                self.assertResults(expected,data['results']);preview=json.loads((path.parent/data['guideFile']).read_text());self.assertEqual(self.canonical(expected,native_surface_patches.geometry(expected)),self.canonical(data['results'],preview))
                for record in (r for r in expected if r['name']=='SurfacePatch'):
                    saved_id=next(r['id'] for r in data['results'] if (r['name'],r['index'])==(record['name'],record['index']));group=next(g for g in preview['groups'] if g['nativeResultID']==saved_id);axes=[v.GetDoubleMatResults(record['id'],k) for k in ['x','y','z']];normals=[v.GetDoubleMatResults(record['id'],k) for k in ['nx','ny','nz']];points=[list(p) for rows in zip(*axes) for p in zip(*rows)];normal_points=[list(p) for rows in zip(*normals) for p in zip(*rows)];cells=[e for e in preview['elements'] if e['group']==group['id']];start=min(n for e in cells for n in e['nodes']);self.assertEqual(preview['nodes'][start:start+len(points)],points)
                    for cell in cells:self.assertEqual(cell['nativePointNormals'],[normal_points[n-start] for n in cell['nodes']])
                if selection in (-1,20):self.assertFalse(preview['nodes']);self.assertTrue(preview['warnings'])
                else:self.assertTrue(preview['nodes']);self.assertTrue(preview['elements'])
                self.assertEqual(path.read_bytes(),baseline);self.assertEqual(self.model.read_bytes(),baseline)

    def test_invalid_set_indices_reject_without_changing_source(self):
        self.fixture();baseline=self.model.read_bytes()
        for selection in (-2,999):
            with self.subTest(selection=selection),self.assertRaises(ValueError):self.worker(dict(action='analysis',name='SurfacePatches',inputs=[dict(name='Set',values=[selection])]))
            self.assertEqual(self.model.read_bytes(),baseline)
