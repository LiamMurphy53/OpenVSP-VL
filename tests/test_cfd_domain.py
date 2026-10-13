"""Native CFD domains/wakes, named references, mode presets and persistence."""
import itertools
import math
import sys
import unittest
import test_native
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class CfdDomain(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def settings(self,**values):
        v=self.v;c=v.FindContainersWithName('CFDMeshSettings')[0]
        parms={v.GetParmName(p):p for p in v.FindContainerParmIDs(c)}
        for n,x in values.items():v.SetParmVal(parms[n],x)
        v.Update()

    def save(self):self.v.WriteVSPFile(str(self.model),self.v.SET_ALL)

    def query(self,path=None):return self.worker(dict(action='query',operation='cfd-domain-preview'),path)

    def assert_box(self,data,low,high):
        part=next(p for p in data['parts'] if p['id']=='domain')
        points=[p for o in part['objects'] for p in o['points']]
        self.assertEqual(len(points),16)
        for axis in range(3):
            self.assertAlmostEqual(min(p[axis] for p in points),low[axis],places=10)
            self.assertAlmostEqual(max(p[axis] for p in points),high[axis],places=10)
        corners=list(itertools.product(*zip(low,high)))
        for p in points:self.assertTrue(any(math.dist(p,c)<1e-10 for c in corners),p)

    def test_absolute_manual_half_domain_and_native_symmetry_are_read_only(self):
        self.settings(Set=0,DegenSet=-1,UseMode=0,FarMesh=1,FarComp=0,FarAbsSize=1,
                      FarManualLoc=1,FarLength=20,FarWidth=30,FarHeight=40,
                      FarXLocation=-10,FarYLocation=5,FarZLocation=2,HalfMesh=1,SymmetrySplitting=1)
        self.save();before=self.model.read_bytes();data,path=self.query()
        self.assert_box(data,[-10,0,-18],[10,20,22])
        symmetry=next(p for p in data['parts'] if p['id']=='symmetry');self.assertTrue(symmetry['objects'])
        self.assertTrue(all(abs(p[1])<1e-12 for o in symmetry['objects'] for p in o['points']))
        self.assertEqual([c['id'] for c in data['context']],[self.gid])
        self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
        self.assertFalse(list(path.parent.glob('*.msh')))

    def test_relative_centered_domain_and_wake_angle_match_native_bbox_and_te_points(self):
        v=self.v;v.SetCFDWakeFlag(self.gid,True)
        v.SetParmVal(self.gid,'WakeScale','WakeSettings',2);v.SetParmVal(self.gid,'WakeAngle','WakeSettings',12)
        self.settings(Set=0,DegenSet=-1,UseMode=0,FarMesh=1,FarComp=0,FarAbsSize=0,
                      FarManualLoc=0,FarXScale=4,FarYScale=3,FarZScale=2,HalfMesh=0,SymmetrySplitting=0)
        self.save();box=list(v.GetBBoxSet(v.SET_ALL));low=box[1:4];size=box[4:7];scales=[4,3,2]
        expected_low=[x-.5*(s-1)*d for x,d,s in zip(low,size,scales)]
        expected_high=[x+.5*(s+1)*d for x,d,s in zip(low,size,scales)]
        data,_=self.query();self.assert_box(data,expected_low,expected_high)
        wake=next(p for p in data['parts'] if p['id']=='wake');points=[p for o in wake['objects'] for p in o['points']]
        self.assertEqual(len(points),12)
        te=[]
        for surf in range(v.GetTotalNumSurfs(self.gid)):
            for u in [0,1/3,2/3,1]:
                p=v.CompPnt01(self.gid,surf,u,0);te.append([p.x(),p.y(),p.z()])
        end_x=low[0]+size[0]+.99*max(size)
        for start,end in zip(points[::2],points[1::2]):
            self.assertTrue(any(math.dist(start,p)<1e-10 for p in te),start)
            self.assertAlmostEqual(end[0],end_x,places=10);self.assertAlmostEqual(end[1],start[1],places=10)
            # The official VspUtil DEG2RAD macro uses this rounded constant.
            self.assertAlmostEqual(end[2],start[2]+(end[0]-start[0])*math.tan(12*.017453293),places=10)

    def test_named_mode_applies_presets_to_preview_context_without_saving_aircraft(self):
        v=self.v;v.SetCFDWakeFlag(self.gid,True);v.SetSetFlag(self.gid,3,True)
        excluded=v.AddGeom('POD');v.SetGeomName(excluded,'Excluded component')
        mode=v.CreateAndAddMode('CFD flight configuration',3,v.SET_NONE)
        group=v.AddVarPresetGroup('Translated wing');pid=v.FindParm(self.gid,'X_Rel_Location','XForm')
        v.AddVarPresetParm(group,pid);setting=v.AddVarPresetSetting(group,'Forward');v.SetVarPresetParmVal(group,setting,pid,20)
        # Native GenerateMesh freezes CFD settings before mode presets run.
        cfd=v.FindContainersWithName('CFDMeshSettings')[0]
        length=next(p for p in v.FindContainerParmIDs(cfd) if v.GetParmName(p)=='FarLength')
        v.AddVarPresetParm(group,length);v.SetVarPresetParmVal(group,setting,length,9)
        v.ModeAddGroupSetting(mode,group,setting)
        self.settings(Set=0,DegenSet=-1,UseMode=0,FarMesh=1,FarComp=0,FarAbsSize=1,FarManualLoc=1,
                      FarLength=60,FarWidth=40,FarHeight=20,FarXLocation=-10,FarYLocation=0,FarZLocation=0,HalfMesh=0,SymmetrySplitting=0)
        self.save();state,path=self.worker(dict(action='mutate',operation='cfd-domain-settings',values={'UseMode':1},mode=mode,farGeom=''))
        config=state['tools']['cfdDomain'];self.assertEqual(config['mode'],mode)
        state,path=self.worker(dict(action='mutate',operation='cfd-domain-settings',values={'FarLength':60},mode=mode,farGeom=''),path)
        self.assertEqual(state['tools']['cfdDomain']['mode'],mode)
        self.assertEqual(next(p['value'] for p in state['tools']['cfdDomain']['params'] if p['name']=='FarLength'),60)
        before=path.read_bytes();data,_=self.query(path)
        self.assertEqual(data['normalSet'],3);self.assertEqual(data['degenSet'],v.SET_NONE)
        self.assertEqual(data['selectedGeoms'],[self.gid]);self.assertEqual([c['id'] for c in data['context']],[self.gid])
        actual=next(p['value'] for p in data['context'][0]['params'] if p['id']==pid);self.assertEqual(actual,20)
        self.assert_box(data,[-10,-20,-10],[50,20,10]);self.assertEqual(path.read_bytes(),before)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.assertEqual(v.GetParmVal(pid),0)
        v.SetAnalysisInputDefaults('CfdMeshAnalysis');self.assertEqual(list(v.GetStringAnalysisInput('CfdMeshAnalysis','ModeID')),[mode])
        v.ApplyModeSettings(mode)
        self.assertEqual(v.GetParmVal(length),9)
        # Context carries the actual engine's post-mode sampled surface, not a
        # translated approximation of the original browser surface.
        surfaces=data['context'][0]['surfaces'];self.assertTrue(surfaces)
        u,w=v.GetUWTess01(self.gid,0)
        for surface in surfaces:
            for i,j in [(0,0),(len(u)//2,len(w)//2),(len(u)-1,len(w)-1)]:
                point=v.CompPnt01(self.gid,surface['index'],u[i],w[j])
                for a,b in zip(surface['points'][i*len(w)+j],[point.x(),point.y(),point.z()]):self.assertAlmostEqual(a,b,places=11)
        with self.assertRaisesRegex(ValueError,'selected for CFD'):self.worker(dict(action='mutate',operation='mode-delete',id=mode),path)
        self.assertEqual(path.read_bytes(),before)

    def test_far_field_reference_guards_and_invalid_settings_preserve_model(self):
        v=self.v;far=v.AddGeom('POD');v.SetGeomName(far,'Outer boundary');v.Update();self.save()
        state,path=self.worker(dict(action='mutate',operation='cfd-domain-settings',values={'UseMode':0,'FarMesh':1,'FarComp':1},mode='',farGeom=far))
        self.assertEqual(state['tools']['cfdDomain']['farGeom'],far)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.assertEqual(v.GetCFDFarFieldGeomID(),far)
        data,_=self.query(path);self.assertTrue(any('component supplies' in w for w in data['warnings']))
        self.assertTrue(any(c['id']==far for c in data['context']))
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'active CFD far-field'):self.worker(dict(action='mutate',operation='delete',geom=far),path)
        for extra in [dict(values={'FarLength':-1}),dict(values={'Set':999}),dict(values={'HalfMesh':.5}),dict(values={'UseMode':1},mode=''),dict(values={'FarMesh':1,'FarComp':1},farGeom=''),dict(values={'FarMesh':1},farGeom='UNKNOWN'),dict(values={'FarMesh':1},mode=None)]:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='cfd-domain-settings',**extra),path)
            self.assertEqual(path.read_bytes(),before)

    def test_disabled_domain_and_wakes_report_native_empty_state(self):
        self.settings(Set=0,DegenSet=-1,UseMode=0,FarMesh=0,FarComp=0,HalfMesh=0,SymmetrySplitting=0)
        self.save();data,_=self.query();self.assertEqual(data['parts'],[])
        self.assertTrue(any('disabled' in w for w in data['warnings']));self.assertTrue(any('No native wake' in w for w in data['warnings']))
