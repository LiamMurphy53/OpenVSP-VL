"""Original human presets, linked-pose guards and native solid equality."""
import sys,unittest
import test_native,native_files,native_human_controls as human
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class HumanControls(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;self.hid=v.AddGeom('HUMAN');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        self.ids={v.GetParmName(p):p for p in v.GetGeomParmIDs(self.hid)}

    def test_original_presets_match_complete_sdk_pose_and_solid(self):
        self.fixture();v=self.v;before=self.model.read_bytes()
        standing=dict(RLSym=1,Back=0,Waist=0,Nod=0,RotateHead=0,WristRt=0,ForearmRt=0,ElbowRt=15,ShoulderABADRt=0,ShoulderFERt=0,ShoulderIERt=0,HipABADRt=.5,HipFERt=2.5,KneeRt=0,AnkleRt=0)
        for preset in (0,1):
            actual,path=self.worker(dict(action='mutate',operation='human-preset',geom=self.hid,preset=preset))
            v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
            # Independent public SDK assignment of the original SetPreset
            # records from the matching official HumanGeom.cpp, no body math.
            values=dict(standing,PresetPose=preset)
            if preset:values.update(ElbowRt=80,ShoulderIERt=45,HipFERt=80,KneeRt=80)
            for n,x in values.items():v.SetParmVal(self.ids[n],x)
            v.Update();expected={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.hid)}
            component=next(c for c in actual['components'] if c['id']==self.hid)
            self.assertEqual({p['id']:p['value'] for p in component['params']},expected)
            self.assertEqual(component['mesh'],native_files.solid_preview(v,self.hid))
            cold,_=self.worker(dict(action='state'),path);self.assertEqual(next(c for c in cold['components'] if c['id']==self.hid),component)
        self.assertEqual(self.model.read_bytes(),before)

    def test_linked_pose_volume_and_density_reject_and_unlock(self):
        self.fixture();before=self.model.read_bytes()
        for n in ('KneeLt','Volume','Density'):
            with self.subTest(field=n),self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='parameter',id=self.ids[n],value=1.))
        state,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids['RLSym'],value=0))
        state,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids['KneeLt'],value=45.),path)
        c=next(c for c in state['components'] if c['id']==self.hid);p={p['name']:p for p in c['params']}
        self.assertEqual(p['KneeLt']['value'],45.);self.assertEqual(p['KneeRt']['value'],0.)
        schema,_=self.worker(dict(action='study-schema'),path);fields={p['id']:p for p in schema['parameters']}
        self.assertTrue(fields[self.ids['KneeLt']].get('editable',True));self.assertFalse(fields[self.ids['Volume']]['editable']);self.assertFalse(fields[self.ids['PresetPose']]['editable'])
        with self.assertRaisesRegex(ValueError,'Apply pose'):self.worker(dict(action='study-model',parameters=[dict(id=self.ids['PresetPose'],value=1)]),path)
        self.assertEqual(self.model.read_bytes(),before)

    def test_body_units_mass_and_percentiles_match_original_sdk(self):
        self.fixture();v=self.v;path=self.model
        for name,value in [('LenUnit',v.LEN_CM),('MassUnit',v.MASS_UNIT_KG),('GenderFlag',v.FEMALE),('Age',44.),('Stature_pct',.75),('BMI_pct',.35),('Mass',64.)]:
            original=path
            actual,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids[name],value=value),original)
            v.ClearVSPModel();v.ReadVSPFile(str(original));v.Update();v.SetParmValUpdate(self.ids[name],value);v.Update()
            c=next(c for c in actual['components'] if c['id']==self.hid)
            self.assertEqual({p['id']:p['value'] for p in c['params']},{p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.hid)})
            self.assertEqual(c['mesh'],native_files.solid_preview(v,self.hid))
        self.assertEqual(c['humanControls']['lengthUnit'],'cm');self.assertEqual(c['humanControls']['massUnit'],'kg')

    def test_solid_preview_preserves_all_native_sets_and_visibility(self):
        self.fixture();v=self.v;v.SetSetFlag(self.gid,v.SET_SHOWN,False);v.SetSetFlag(self.hid,7,True)
        before={g:[v.GetSetFlag(g,i) for i in range(v.GetNumSets())] for g in v.FindGeoms()}
        native_files.solid_preview(v,self.hid)
        self.assertEqual({g:[v.GetSetFlag(g,i) for i in range(v.GetNumSets())] for g in v.FindGeoms()},before)
        state,_=self.worker(dict(action='state'))
        self.assertTrue(next(c for c in state['components'] if c['id']==self.hid)['shown'])

    def test_skeleton_preserves_native_body_frame_pose_and_visibility(self):
        self.fixture();v=self.v;before=self.model.read_bytes()
        state,path=self.worker(dict(action='state'))
        original=next(c for c in state['components'] if c['id']==self.hid)
        self.assertEqual(len(original['humanControls']['skeleton']),2)
        self.assertTrue(all(len(o['points'])==48 and not o['visible'] for o in original['humanControls']['skeleton']))
        shown,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids['ShowSkelFlag'],value=1))
        shown=next(c for c in shown['components'] if c['id']==self.hid)
        self.assertEqual(shown['mesh'],original['mesh'])
        self.assertTrue(all(o['visible'] for o in shown['humanControls']['skeleton']))
        self.assertEqual([o['points'] for o in shown['humanControls']['skeleton']],[o['points'] for o in original['humanControls']['skeleton']])
        # Joint22 is DES_EYE in the original HumanGeom header. Its posed
        # native line endpoint agrees with the separate original eye getter.
        self.assertEqual(shown['humanControls']['skeleton'][1]['points'][43],shown['humanControls']['eyes'][0])
        pose,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids['ElbowRt'],value=80.),path)
        pose=next(c for c in pose['components'] if c['id']==self.hid)
        self.assertEqual(pose['humanControls']['skeleton'][0]['points'],shown['humanControls']['skeleton'][0]['points'])
        self.assertNotEqual(pose['humanControls']['skeleton'][1]['points'],shown['humanControls']['skeleton'][1]['points'])
        moved,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids['X_Rel_Location'],value=3.),path)
        moved=next(c for c in moved['components'] if c['id']==self.hid)
        self.assertEqual(moved['humanControls']['skeleton'],pose['humanControls']['skeleton'])
        self.assertEqual(moved['humanControls']['eyes'][0],[pose['humanControls']['eyes'][0][0]+3,*pose['humanControls']['eyes'][0][1:]])
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(next(c for c in cold['components'] if c['id']==self.hid),moved)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();v.SetSetFlag(self.hid,v.SET_SHOWN,False)
        flags=[v.GetSetFlag(self.hid,i) for i in range(v.GetNumSets())]
        drawing=human.native(v,self.hid)
        self.assertTrue(all(not o['visible'] for o in drawing['skeleton']))
        self.assertEqual([v.GetSetFlag(self.hid,i) for i in range(v.GetNumSets())],flags)
        self.assertEqual(self.model.read_bytes(),before)

if __name__=='__main__':unittest.main()
