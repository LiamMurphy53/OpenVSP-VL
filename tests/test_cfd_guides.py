"""Native CFD guide preserves engine inputs and real exports."""
import sys,unittest,json,time,os,signal,tempfile
from pathlib import Path
import test_native
from native_worker import analysis_schema,set_inputs
import native_cfd_guides as guide
import native_mesh
@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class CfdGuides(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    def test_actual_native_termination_retains_applied_setup_after_reload(self):
        import native_service as service
        before=self.model.read_bytes();previous=service.WORK,service.JOBS
        process=None
        try:
            with tempfile.TemporaryDirectory() as work:
                service.WORK=Path(work);service.JOBS={}
                job=service.start_job(dict(name=guide.NAME,inputs=[dict(name='BaseLen',values=[.05]),dict(name='MinLen',values=[.01])]),model_source=self.model,source_revision='native-setup-recovery')
                process=service.JOBS[job['id']]['_process'];folder=service.job_folder(job['id'])
                deadline=time.monotonic()+20
                while not (folder/'analysis-setup.json').exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue((folder/'analysis-setup.json').exists())
                setup=json.loads((folder/'analysis-setup.json').read_text())
                self.assertEqual(len(setup['inputs']),28)
                fields={e['name']:e['values'] for e in setup['inputs']}
                self.assertEqual(fields['BaseLen'],[.05]);self.assertEqual(fields['MinLen'],[.01])
                self.assertIsNone(process.poll(),'Native worker must still be live for termination test')
                os.killpg(process.pid,signal.SIGTERM)
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    state=service.job_state(job['id'])
                    if state.get('finished'):break
                    time.sleep(.01)
                self.assertEqual(state['status'],'failed');self.assertEqual(state['terminationSignal'],'SIGTERM')
                service.JOBS={};reloaded=service.job_state(job['id'])
                self.assertEqual(reloaded['analysisSetup'],setup);self.assertNotIn('result',reloaded)
                self.assertEqual((folder/'aircraft.vsp3').read_bytes(),before)
        finally:
            if process and process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=10)
            service.WORK,service.JOBS=previous
        self.assertEqual(self.model.read_bytes(),before)
    def test_all_original_inputs_defaults_limits_and_conditional_controls(self):
        v=self.v;n=guide.NAME;v.SetAnalysisInputDefaults(n)
        getters={v.INT_DATA:v.GetIntAnalysisInput,v.DOUBLE_DATA:v.GetDoubleAnalysisInput,v.STRING_DATA:v.GetStringAnalysisInput}
        raw={k:(v.GetAnalysisInputType(n,k),list(getters[v.GetAnalysisInputType(n,k)](n,k))) for k in v.GetAnalysisInputNames(n)}
        s=analysis_schema(v,n);fields={e['name']:e for e in s['inputs']}
        self.assertEqual({k:(e['type'],e['values']) for k,e in fields.items()},raw)
        self.assertEqual(set(fields),{k for section in s['guide']['sections'] for k in section['inputs']})
        for k,native in {'BaseLen':'BaseLen','MinLen':'MinLen','MaxGap':'MaxGap','NCircSeg':'NCircSeg','GrowthRatio':'GrowRatio','RelCurveTol':'RelCurveTol'}.items():
            p=guide.parameters(v)[native];self.assertEqual((fields[k]['min'],fields[k]['max']),(v.GetParmLowerLimit(p),v.GetParmUpperLimit(p)))
        self.assertEqual(fields['ModeID']['applicableWhen'],dict(input='UseMode',values=[1]))
        self.assertEqual(fields['STLFileName']['applicableWhen'],dict(input='STLFileFlag',values=[1]))
        self.assertFalse(fields['GMSHFileFlag']['editable'])
        live,_=self.worker(dict(action='schema',name=n));livefields={e['name']:e for e in live['inputs']}
        self.assertTrue(livefields['STLFileName']['editable']);self.assertFalse(livefields['GMSHFileName']['editable'])
    def test_bad_settings_modes_and_reserved_duplicate_names_stop_before_mesh(self):
        before=self.model.read_bytes()
        for values in [dict(GrowthRatio=[.5]),dict(RelCurveTol=[0]),dict(MinLen=[2],BaseLen=[1]),dict(UseMode=[1],ModeID=['missing']),dict(SelectedSetIndex=[999]),dict(SelectedSetIndex=[-1],SelectedDegenSetIndex=[-1]),dict(STLFileName=['aircraft.vsp3']),dict(STLFileName=['analysis-setup.json']),dict(STLFileName=['ANALYSIS-SETUP.JSON.TMP']),dict(STLFileName=['same.stl'],OBJFileName=['SAME.stl'])]:
            with self.subTest(values=values),self.assertRaises(ValueError):
                self.worker(dict(action='analysis',name=guide.NAME,inputs=[dict(name=k,values=x) for k,x in values.items()]))
            self.assertEqual(self.model.read_bytes(),before)
    def test_named_exports_and_full_mesh_equal_direct_original_sdk(self):
        v=self.v;before=self.model.read_bytes();values=dict(BaseLen=[1.],MinLen=[.2],MaxGap=[.02],GrowthRatio=[1.5],NCircSeg=[20.5],STLFileName=['/old/location/wing.stl'],OBJFileName=['wing.obj'],TRIFileFlag=[0],POLYFileFlag=[0],FACETFileFlag=[0],TaggedMultiSolid=[1])
        result,path=self.worker(dict(action='analysis',name=guide.NAME,inputs=[dict(name=k,values=x) for k,x in values.items()]))
        setup=json.loads((path.parent/'analysis-setup.json').read_text())
        self.assertEqual(setup['inputs'],result['inputs'])
        self.assertEqual(setup['nativeSettingOverrides'],result['nativeSettingOverrides'])
        self.assertEqual(setup['stage'],'before native execution')
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.SetAnalysisInputDefaults(guide.NAME)
        setters={v.INT_DATA:v.SetIntAnalysisInput,v.DOUBLE_DATA:v.SetDoubleAnalysisInput,v.STRING_DATA:v.SetStringAnalysisInput}
        for k,x in values.items():setters[v.GetAnalysisInputType(guide.NAME,k)](guide.NAME,k,x)
        p=v.FindParm(v.FindContainer('CFDGridDensity',0),'GrowRatio','CFDGridDensity')
        v.SetParmVal(p,1.5)
        direct=self.path/'direct';direct.mkdir()
        for prefix in ['GMSH','STL','OBJ']:
            k=prefix+'FileName';name='surface.msh' if prefix=='GMSH' else Path(v.GetStringAnalysisInput(guide.NAME,k)[0]).name
            v.SetStringAnalysisInput(guide.NAME,k,[str(direct/name)])
        v.ExecAnalysis(guide.NAME)
        self.assertEqual(native_mesh.read_gmsh(path.parent/'surface.msh'),native_mesh.read_gmsh(direct/'surface.msh'))
        for name in ['wing.stl','wing.obj']:self.assertEqual((path.parent/name).read_bytes(),(direct/name).read_bytes())
        self.assertFalse(list(path.parent.glob('*.tri')));self.assertFalse(list(path.parent.glob('*.poly')))
        self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
        fields={e['name']:e['values'] for e in result['inputs']}
        self.assertEqual(Path(fields['STLFileName'][0]).resolve(),(path.parent/'wing.stl').resolve());self.assertEqual(fields['GMSHFileFlag'],[1])
        self.assertEqual(result['nativeSettingOverrides']['GrowthRatio']['value'],1.5)

    def test_registered_name_mismatches_use_original_native_parameters(self):
        v=self.v;s=analysis_schema(v,guide.NAME)
        set_inputs(v,guide.NAME,[dict(name='GrowthRatio',values=[1.8]),dict(name='XYZIntCurveFlag',values=[1])])
        applied=native_mesh.configure_cfd(v,guide.NAME)
        for key,value in [('GrowthRatio',1.8),('XYZIntCurveFlag',1)]:
            self.assertEqual(applied[key]['value'],value);self.assertEqual(v.GetParmVal(applied[key]['parameter']),value)

    def compare_configuration(self,values):
        v=self.v;before=self.model.read_bytes()
        result,path=self.worker(dict(action='analysis',name=guide.NAME,inputs=[dict(name=k,values=x) for k,x in values.items()]))
        direct=self.path/('direct-'+path.parent.name);direct.mkdir()
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.SetAnalysisInputDefaults(guide.NAME)
        setters={v.INT_DATA:v.SetIntAnalysisInput,v.DOUBLE_DATA:v.SetDoubleAnalysisInput,v.STRING_DATA:v.SetStringAnalysisInput}
        for e in result['inputs']:
            x=e['values']
            if e['name'].endswith('FileName'):x=[str(direct/Path(x[0]).name)]
            setters[e['type']](guide.NAME,e['name'],x,e['index'])
        for entry in result['nativeSettingOverrides'].values():
            self.assertEqual(v.GetParmName(entry['parameter']),entry['nativeName'])
            v.SetParmVal(entry['parameter'],entry['value'])
        v.ExecAnalysis(guide.NAME)
        self.assertEqual(native_mesh.read_gmsh(path.parent/'surface.msh'),native_mesh.read_gmsh(direct/'surface.msh'))
        self.assertEqual((path.parent/'surface.msh').read_bytes(),(direct/'surface.msh').read_bytes())
        self.assertEqual(self.model.read_bytes(),before);self.assertEqual(path.read_bytes(),before)
        return result,native_mesh.read_gmsh(path.parent/'surface.msh')

    def test_positive_y_half_and_thin_surface_sets_match_complete_original_meshes(self):
        v=self.v;v.SetSetFlag(self.gid,3,True);v.SetSetName(3,'Thin verification wing');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        common=dict(BaseLen=[1.],MinLen=[.2],MaxGap=[.02],GrowthRatio=[1.5],XYZIntCurveFlag=[1],FACETFileFlag=[0],OBJFileFlag=[0],POLYFileFlag=[0],STLFileFlag=[0],TRIFileFlag=[0])
        for geometry in [dict(GenerateHalfMesh=[1]),dict(SelectedSetIndex=[-1],SelectedDegenSetIndex=[3])]:
            with self.subTest(geometry=geometry):
                result,mesh=self.compare_configuration(dict(common,**geometry))
                self.assertGreater(len(mesh['nodes']),0)
                if 'GenerateHalfMesh' in geometry:self.assertTrue(all(p[1]>=-1e-12 for p in mesh['nodes']))
                self.assertEqual(result['nativeSettingOverrides']['XYZIntCurveFlag']['value'],1)

    def test_mode_applied_geometry_matches_original_mesh_and_preserves_baseline(self):
        v=self.v;v.SetSetFlag(self.gid,3,True);m=v.CreateAndAddMode('Aft wing',3,v.SET_NONE)
        group=v.AddVarPresetGroup('Position');p=v.FindParm(self.gid,'X_Rel_Location','XForm');v.AddVarPresetParm(group,p);setting=v.AddVarPresetSetting(group,'Aft');v.SetVarPresetParmVal(group,setting,p,3.5);v.ModeAddGroupSetting(m,group,setting);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        result,mesh=self.compare_configuration(dict(UseMode=[1],ModeID=[m],BaseLen=[1.],MinLen=[.2],MaxGap=[.02],GrowthRatio=[1.5],FACETFileFlag=[0],OBJFileFlag=[0],POLYFileFlag=[0],STLFileFlag=[0],TRIFileFlag=[0]))
        self.assertTrue(all(point[0]>=3.5 for point in mesh['nodes']))
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();self.assertEqual(v.GetParmVal(p),0.)

if __name__=='__main__':unittest.main()
