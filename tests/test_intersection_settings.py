"""Saved native preparation settings and whole-request validation."""
import sys,unittest,re
import test_native
import test_cfd_results as cfd_results
import test_intersection_guides as guides
from native_intersections import mutate_settings

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class IntersectionSettings(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def values(self):
        v=self.v;c=v.FindContainer('SurfaceIntersectSettings',0)
        return {v.GetParmName(p):v.GetParmVal(p) for p in v.FindContainerParmIDs(c)}

    def test_worker_settings_match_sdk_and_cold_native_file(self):
        v=self.v;values=dict(DemoteSurfsCubicFlag=1,CubicSurfTolerance=2e-5,HalfMesh=1,STEPMergePoints=1)
        before=self.model.read_bytes()
        state,path=self.worker(dict(action='mutate',operation='intersection-settings',values=values))
        group=next(g for g in state['tools']['globalSettings'] if g['name']=='SurfaceIntersectSettings')
        actual={p['name']:p['value'] for p in group['params']}
        c=v.FindContainer('SurfaceIntersectSettings',0)
        for p in v.FindContainerParmIDs(c):
            if v.GetParmName(p) in values:v.SetParmVal(p,values[v.GetParmName(p)])
        v.Update();self.assertEqual(actual,self.values())
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual({n:self.values()[n] for n in values},values)
        fresh,_=self.worker(dict(action='state'),path)
        cold=next(g for g in fresh['tools']['globalSettings'] if g['name']=='SurfaceIntersectSettings')
        self.assertEqual({p['name']:p['value'] for p in cold['params']},actual)
        self.assertEqual(self.model.read_bytes(),before)

    def test_invalid_request_changes_no_native_parameter(self):
        before=self.values()
        for bad in [dict(HalfMesh=.5),dict(CubicSurfTolerance=0),dict(CubicSurfTolerance=float('inf')),dict(STEPMergePoints=True),dict(SRF_XYZIntCurve=1),dict(NoSuchSetting=1),{},[],None]:
            values=dict(DemoteSurfsCubicFlag=1,**bad) if isinstance(bad,dict) and bad else bad
            with self.subTest(values=values),self.assertRaises(ValueError):mutate_settings(self.v,dict(values=values))
            self.assertEqual(self.values(),before)

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class PreparationExports(unittest.TestCase):
    setUpClass=classmethod(cfd_results.CfdResults.setUpClass.__func__)
    tearDownClass=classmethod(cfd_results.CfdResults.tearDownClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    drawings=staticmethod(cfd_results.CfdResults.drawings)
    direct=guides.IntersectionGuides.direct
    run_case=guides.IntersectionGuides.run_case

    def save_settings(self,values):
        _,path=self.worker(dict(action='mutate',operation='intersection-settings',values=values))
        self.model=path

    def curves(self):
        return self.run_case(dict(UseMode=[0],SelectedSetIndex=[self.v.SET_ALL],SelectedDegenSetIndex=[-1],IGESFileFlag=[0],STEPFileFlag=[0],SRFFileName=['native.srf'],CURVFileName=['native.curv'],P3DFileName=['native.p3d']))

    def test_higher_order_fuselage_is_demoted_and_tolerances_match_sdk(self):
        v=self.v;v.ClearVSPModel();g=v.AddGeom('FUSELAGE');s=v.GetXSecSurf(g,0)
        for i in range(v.GetNumXSec(s)):v.SetXSecContinuity(v.GetXSec(s,i),2)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        outputs=[];degrees=[]
        for flag,tol in [(0,1e-6),(1,1e-3),(1,1e-6)]:
            self.save_settings(dict(DemoteSurfsCubicFlag=flag,CubicSurfTolerance=tol))
            _,path,direct=self.curves()
            for suffix in ['srf','curv','p3d']:self.assertEqual((path.parent/f'native.{suffix}').read_bytes(),(direct/f'native.{suffix}').read_bytes())
            text=(path.parent/'native.srf').read_text();outputs.append(text)
            rows=re.findall(r'Num [UW] Patches, patch order:\n([^\n]+)',text)
            degrees.append(max(int(n) for row in rows for n in re.findall(r'\d+',row)))
        self.assertGreater(degrees[0],3);self.assertEqual(degrees[1:],[3,3])
        self.assertNotEqual(outputs[0],outputs[1]);self.assertNotEqual(outputs[1],outputs[2])

    def test_mirrored_wing_half_selection_changes_native_surfaces(self):
        outputs=[];counts=[]
        for half in [0,1]:
            self.save_settings(dict(HalfMesh=half))
            _,path,direct=self.curves()
            for suffix in ['srf','curv','p3d']:self.assertEqual((path.parent/f'native.{suffix}').read_bytes(),(direct/f'native.{suffix}').read_bytes())
            text=(path.parent/'native.srf').read_text();outputs.append(text)
            counts.append(int(re.search(r'(\d+)\s*// Number of Cubic Bezier Surfaces',text).group(1)))
        self.assertGreater(counts[0],counts[1]);self.assertGreater(counts[1],0);self.assertNotEqual(outputs[0],outputs[1])

    def test_step_point_merging_matches_every_native_step_record(self):
        v=self.v;v.ClearVSPModel();v.AddGeom('POD');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        exports=[]
        for merge in [0,1]:
            self.save_settings(dict(STEPMergePoints=merge))
            _,path,direct=self.run_case(dict(UseMode=[0],SelectedSetIndex=[v.SET_ALL],SelectedDegenSetIndex=[-1],SRFFileFlag=[0],CURVFileFlag=[0],P3DFileFlag=[0],IGESFileFlag=[0],STEPFileFlag=[1],STEPFileName=['native.stp']))
            normalize=lambda text:re.sub(r"(?m)^(FILE_NAME\('[^']*',')[^']*('.*)$",r'\1<NATIVE_TIMESTAMP>\2',text)
            actual=normalize((path.parent/'native.stp').read_text());expected=normalize((direct/'native.stp').read_text())
            self.assertEqual(actual,expected);self.assertIn('MANIFOLD_SOLID_BREP',actual);exports.append(actual)
        self.assertNotEqual(exports[0],exports[1])

    def test_saved_native_mode_defaults_apply_presets_and_match_all_curve_exports(self):
        guides.IntersectionGuides.fixture(self)
        _,path=self.worker(dict(action='mutate',operation='intersection-selection',values={'UseMode':1},mode=self.mode));self.model=path
        before=self.model.read_bytes()
        _,path,direct=self.run_case(dict(IGESFileFlag=[0],STEPFileFlag=[0],SRFFileName=['native.srf'],CURVFileName=['native.curv'],P3DFileName=['native.p3d']))
        for suffix in ['srf','curv','p3d']:self.assertEqual((path.parent/f'native.{suffix}').read_bytes(),(direct/f'native.{suffix}').read_bytes())
        self.assertEqual(self.v.GetParmVal(self.v.FindParm(self.gid,'X_Rel_Location','XForm')),3)
        self.assertEqual(self.model.read_bytes(),before)
