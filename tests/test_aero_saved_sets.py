"""Saved aero set selectors use actual current native sets, not guessed slots."""
import sys
import unittest
import test_native
from native_worker import parameter

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class SavedAeroSets(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_named_set_selection_edit_reopen_and_renaming(self):
        v=self.v;cid=v.FindContainer('VSPAEROSettings',0)
        v.SetSetName(3,'Main aircraft');v.SetSetFlag(self.gid,3,True)
        v.SetSetName(4,'Main aircraft') # Duplicate names still have distinct indices.
        v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        for name,value in [('GeomSet',3),('ThinGeomSet',4),('MassSet',3),('MassDegenSet',-1)]:
            with self.subTest(name=name):
                pid=v.FindParm(cid,name,'VSPAERO');field=parameter(v,pid)
                self.assertEqual([c['value'] for c in field['choices']],list(range(-1,v.GetNumSets())))
                self.assertEqual(field['choices'][0],dict(value=-1,label='None'))
                self.assertIn(dict(value=3,label='Main aircraft · 3'),field['choices'])
                self.assertIn(dict(value=4,label='Main aircraft · 4'),field['choices'])
                state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value))
                cold,_=self.worker(dict(action='state'),path)
                for data in (state,cold):
                    group=next(c for c in data['tools']['globalSettings'] if c['name']=='VSPAEROSettings')
                    actual=next(p for p in group['params'] if p['id']==pid)
                    self.assertEqual(actual['value'],value);self.assertEqual(actual['choices'],field['choices'])
        v.SetSetName(3,'Renamed airframe')
        self.assertIn(dict(value=3,label='Renamed airframe · 3'),parameter(v,v.FindParm(cid,'GeomSet','VSPAERO'))['choices'])
        self.assertEqual(self.model.read_bytes(),before)

    def test_missing_slots_reject_and_legacy_value_remains_visible_for_repair(self):
        v=self.v;pid=v.FindParm(v.FindContainer('VSPAEROSettings',0),'GeomSet','VSPAERO')
        before=self.model.read_bytes()
        for value in (v.GetNumSets(),1000,-2,3.5,True,None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='parameter',id=pid,value=value))
            self.assertEqual(self.model.read_bytes(),before)
        v.SetParmValUpdate(pid,1000);v.WriteVSPFile(str(self.model),v.SET_ALL)
        legacy=self.model.read_bytes();state,_=self.worker(dict(action='state'))
        group=next(c for c in state['tools']['globalSettings'] if c['name']=='VSPAEROSettings')
        field=next(p for p in group['params'] if p['id']==pid)
        self.assertIn(dict(value=1000.0,label='Unavailable native set · 1000.0'),field['choices'])
        state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=0))
        self.assertEqual(self.model.read_bytes(),legacy)
        user=v.AddUserParm(v.PARM_INT_TYPE,'GeomSet','VSPAERO')
        self.assertNotIn('choices',parameter(v,user))

    def test_saved_set_and_reference_edits_feed_original_native_solver_setup(self):
        import native_solver_setup
        v=self.v;cid=v.FindContainer('VSPAEROSettings',0)
        body=v.AddGeom('POD');v.SetParmValUpdate(body,'X_Rel_Location','XForm',100)
        v.SetSetName(3,'Wing only');v.SetSetFlag(self.gid,3,True);v.SetSetFlag(body,3,False)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        path=self.model
        # Use the same saved-setting mutation route as the modern controls.
        for name,value in [('GeomSet',-1),('ThinGeomSet',3),('RefFlag',v.MANUAL_REF),('Sref',77),('bref',19),('cref',4),('NoiseUnits',v.NOISE_ENGLISH),('AlphaStart',4),('AlphaEnd',4),('AlphaNpts',1),('MachStart',.1),('MachEnd',.1),('MachNpts',1)]:
            pid=v.FindParm(cid,name,'VSPAERO')
            _,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
        saved=path.read_bytes()
        request=dict(action='analysis',name='VSPAEROSweep',inputs=[dict(name='StopBeforeRun',values=[1]),dict(name='NCPU',values=[1])])
        actual,output=self.worker(request,path)
        self.assertEqual(actual['executionMode'],'setup-only');self.assertFalse(actual['solverExecuted'])
        flight={e['name']:e['values'] for e in actual['inputs']}
        geometry={e['name']:e['values'] for e in actual['geometryInputs']}
        for name,value in [('GeomSet',-1),('ThinGeomSet',3)]:
            self.assertEqual(flight[name],[value]);self.assertEqual(geometry[name],[value])
        for name,value in [('RefFlag',v.MANUAL_REF),('Sref',77),('bref',19),('cref',4),('NoiseUnits',v.NOISE_ENGLISH)]:self.assertEqual(flight[name],[value])
        # Independent official API replay reads saved defaults itself. It does
        # not copy effective inputs back from Studio's response.
        direct=self.path/'original-saved-defaults';direct.mkdir()
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();v.SetVSP3FileName(str(direct/'aircraft.vsp3'))
        v.SetAnalysisInputDefaults('VSPAEROComputeGeometry')
        self.assertTrue(v.ExecAnalysis('VSPAEROComputeGeometry'))
        v.SetAnalysisInputDefaults('VSPAEROSweep')
        v.SetIntAnalysisInput('VSPAEROSweep','StopBeforeRun',[1]);v.SetIntAnalysisInput('VSPAEROSweep','NCPU',[1])
        self.assertFalse(v.ExecAnalysis('VSPAEROSweep'))
        self.assertEqual(actual['solverSetup'],native_solver_setup.read(direct))
        expected=(direct/'aircraft.vspgeom').read_bytes();self.assertTrue(expected)
        self.assertEqual((output.parent/'aircraft.vspgeom').read_bytes(),expected)
        self.assertEqual(path.read_bytes(),saved);self.assertEqual(self.model.read_bytes(),before)
        # Complete a real one-case solve using the same saved defaults, then
        # compare every native floating-point polar column, not just setup.
        v.SetIntAnalysisInput('VSPAEROSweep','StopBeforeRun',[0])
        self.assertTrue(v.ExecAnalysis('VSPAEROSweep'))
        rid=v.FindLatestResultsID('VSPAERO_Polar')
        expected={n:list(v.GetDoubleResults(rid,n)) for n in v.GetAllDataNames(rid) if v.GetResultsType(rid,n)==v.DOUBLE_DATA}
        self.assertTrue(expected['CLtot']);self.assertTrue(expected['CDtot'])
        completed,run=self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=[dict(name='StopBeforeRun',values=[0]),dict(name='NCPU',values=[1])]),path)
        polar=next(r for r in completed['results'] if r['name']=='VSPAERO_Polar')
        actual={e['name']:e['values'] for e in polar['entries'] if e['type']==v.DOUBLE_DATA}
        self.assertEqual(actual,expected)
        self.assertTrue(list(run.parent.glob('*.adb')))
        self.assertEqual(path.read_bytes(),saved);self.assertEqual(self.model.read_bytes(),before)
