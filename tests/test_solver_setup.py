"""Saved native mixed/symmetric rotor setups remain exact and inspectable."""
import json,math,sys,unittest,shutil
import test_native
import native_worker,native_solver_setup
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class SolverSetup(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;blade=v.AddGeom('PROP');v.SetGeomName(blade,'Mirrored rotating blades');v.SetParmValUpdate(blade,'Diameter','Design',6);v.SetParmValUpdate(blade,'Beta34','Design',25);v.SetParmValUpdate(blade,'Y_Rel_Location','XForm',8);v.SetParmValUpdate(blade,'Sym_Planar_Flag','Sym',v.SYM_XZ)
        disk=v.AddGeom('PROP');v.SetGeomName(disk,'Native actuator disk');v.SetParmValUpdate(disk,'Diameter','Design',6);v.SetParmValUpdate(disk,'PropMode','Design',v.PROP_DISK);v.SetParmValUpdate(disk,'X_Rel_Location','XForm',-8);v.Update()
        group=v.AddVarPresetGroup('Disk geometry');parameter=v.FindParm(disk,'Diameter','Design');v.AddVarPresetParm(group,parameter);setting=v.AddVarPresetSetting(group,'Eight-unit disk');v.SetVarPresetParmVal(group,setting,parameter,8)
        mode=v.CreateAndAddMode('Mixed mirrored aircraft',v.SET_NONE,v.SET_ALL);v.ModeAddGroupSetting(mode,group,setting);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);return mode

    def test_native_mixed_symmetric_mode_setup_and_full_results_match_direct(self):
        mode=self.fixture();v=self.v;before=self.model.read_bytes();inputs={'UseModeFlag':1,'ModeID':mode,'RefFlag':0,'Sref':1.,'bref':6.,'cref':1.,'NCPU':1,'Vinf':30.,'Rho':1.225,'AlphaStart':0.,'AlphaNpts':1,'BetaNpts':1,'MachStart':.1,'MachNpts':1,'ReCrefNpts':1,'WakeNumIter':3,'PropBladesMode':v.VSPAERO_PROP_UNSTEADY,'AutoTimeStepFlag':1,'AutoTimeNumRevs':1}
        state,case=self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=[dict(name=k,values=[x]) for k,x in inputs.items()]))
        setup=state['solverSetup'];self.assertTrue(setup['available']);self.assertEqual(len(setup['disks']),1)
        self.assertEqual(next(f['value'] for f in setup['disks'][0]['fields'] if f['name']=='Radius'),'4')
        rotors=[g for g in setup['groups'] if next(f['value'] for f in g['fields'] if f['name']=='GeometryIsARotor')=='1'];self.assertEqual(len(rotors),2)
        self.assertEqual({next(f['value'] for f in g['fields'] if f['name']=='OVec') for g in rotors},{'0 8 0','0 -8 0'})
        self.assertEqual(setup,native_solver_setup.read(case.parent))
        import native_service as service
        old_work,old_jobs=service.WORK,service.JOBS
        legacy_id='a'*32
        legacy=self.path/'jobs'/legacy_id;legacy.mkdir(parents=True)
        for filename in (setup['source'],setup['groupSource']):shutil.copy2(case.parent/filename,legacy/filename)
        old_result={k:x for k,x in state.items() if k!='solverSetup'}
        response=legacy/'response.json';response.write_text(json.dumps(old_result));saved=response.read_bytes()
        try:
            service.WORK=self.path;service.JOBS={legacy_id:dict(name='VSPAEROSweep',status='complete',result=old_result)}
            restored=service.job_state(legacy_id);self.assertEqual(restored['result']['solverSetup'],setup)
            self.assertNotIn('solverSetup',service.JOBS[legacy_id]['result']);self.assertEqual(response.read_bytes(),saved)
        finally:service.WORK,service.JOBS=old_work,old_jobs
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();direct=self.path/'direct';direct.mkdir();v.SetVSP3FileName(str(direct/'aircraft.vsp3'))
        for name,entries in [('VSPAEROComputeGeometry',state['geometryInputs']),('VSPAEROSweep',state['inputs'])]:
            v.SetAnalysisInputDefaults(name)
            for e in entries:{v.INT_DATA:v.SetIntAnalysisInput,v.DOUBLE_DATA:v.SetDoubleAnalysisInput,v.STRING_DATA:v.SetStringAnalysisInput}[e['type']](name,e['name'],e['values'],e['index'])
            self.assertTrue(v.ExecAnalysis(name));native_worker.errors(v)
        self.assertEqual(setup,native_solver_setup.read(direct))
        for result in state['results']:
            rid=v.FindResultsID(result['name'],result['index']);self.assertTrue(rid)
            for e in result['entries']:
                if e['name'] in ('Analysis_Duration_Sec','WallTime') or e['type'] not in (v.INT_DATA,v.DOUBLE_DATA):continue
                values=list((v.GetIntResults if e['type']==v.INT_DATA else v.GetDoubleResults)(rid,e['name'],e['index']));values=[None if isinstance(x,float) and not math.isfinite(x) else x for x in values];self.assertEqual(values,e['values'],(result['name'],e['name']))
        self.assertEqual(self.model.read_bytes(),before)

    def test_missing_and_incomplete_setup_is_not_reconstructed(self):
        self.assertFalse(native_solver_setup.read(self.path)['available']);config=self.path/'saved.vspaero';config.write_text('NumberOfRotors = 1\nPropElement_1\n1\n0 0 0\n')
        with self.assertRaisesRegex(ValueError,'incomplete'):native_solver_setup.read(self.path)
        config.write_text('NumberOfRotors = 1\n')
        with self.assertRaisesRegex(ValueError,'count'):native_solver_setup.read(self.path)
