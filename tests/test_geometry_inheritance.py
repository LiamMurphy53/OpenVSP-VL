"""Swept native geometry sets reach both aerodynamic input scopes and exports."""
import unittest,math
from aero_io import read_adb
import test_studies
import native_service as service,native_studies as studies,native_managers
from native_worker import errors,collect_results

class GeometryInheritance(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def test_both_scopes_follow_case_set_and_match_original_geometry_and_setup(self):
        self.check_inherited_sets(False)

    def test_both_scopes_match_original_solver_results_and_pressure(self):
        self.check_inherited_sets(True)

    def check_inherited_sets(self,solve):
        v=self.v;a=self.gid;v.SetGeomName(a,'Wing A');b=v.AddGeom('WING');v.SetGeomName(b,'Wing B');v.SetParmValUpdate(b,'TotalSpan','WingGeom',24);v.SetParmValUpdate(b,'X_Rel_Location','XForm',30)
        for index,g in [(3,a),(4,b)]:
            v.SetSetName(index,v.GetGeomName(g))
            for geom in v.FindGeoms():v.SetSetFlag(geom,index,geom==g)
        cid=native_managers.manager(v,'VSPAEROSettings');pid=v.FindParm(cid,'ThinGeomSet','VSPAERO');v.SetParmValUpdate(pid,3);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        inputs=[dict(name=k,values=[x]) for k,x in dict(UseModeFlag=0,GeomSet=-1,ThinGeomSet=3,StopBeforeRun=0 if solve else 1,AlphaStart=4,MachStart=.1,WakeNumIter=3,Sref=45,bref=18,cref=2.5,AlphaNpts=1,BetaNpts=1,MachNpts=1,ReCrefNpts=1,NCPU=1).items()]
        stage=dict(name='VSPAEROSweep',freezeInputs=True,inputs=inputs,geometryInputs=[dict(name='GeomSet',values=[-1]),dict(name='ThinGeomSet',values=[3])],followDefaults=[dict(scope=scope,name='ThinGeomSet',index=0) for scope in ['inputs','geometryInputs']])
        plan=self.save([dict(kind='parameter',id=pid,values=[3,4])],[stage]);batch=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(batch['status'],'complete',batch)
        geometry=[]
        for case in batch['cases']:
            job=service.job_state(case['stages'][0]['job']);folder=service.job_folder(job['id']);data=job['result'];selected=case['values'][0]
            for scope in ['inputs','geometryInputs']:self.assertEqual(next(e['values'] for e in data[scope] if e['name']=='ThinGeomSet'),[selected])
            if not solve:self.assertEqual(data['executionMode'],'setup-only')
            geometry.append((folder/'aircraft.vspgeom').read_bytes());direct=self.path/('original-'+str(case['index']));direct.mkdir()
            v.ClearVSPModel();v.ReadVSPFile(str(folder/'aircraft.vsp3'));v.Update();v.SetVSP3FileName(str(direct/'aircraft.vsp3'))
            for name,entries in [('VSPAEROComputeGeometry',data['geometryInputs']),('VSPAEROSweep',data['inputs'])]:
                v.SetAnalysisInputDefaults(name)
                for entry in entries:{v.INT_DATA:v.SetIntAnalysisInput,v.DOUBLE_DATA:v.SetDoubleAnalysisInput,v.STRING_DATA:v.SetStringAnalysisInput}[entry['type']](name,entry['name'],entry['values'],entry['index'])
                v.ExecAnalysis(name);errors(v)
            for name in ['aircraft.vspgeom','aircraft.vspaero']:self.assertEqual((folder/name).read_bytes(),(direct/name).read_bytes())
            if solve:
                def clean(x):
                    if isinstance(x,float) and not math.isfinite(x):return None
                    return [clean(y) for y in x] if isinstance(x,list) else x
                def fields(results):return {(r['name'],r['index'],x['name'],x['index']):clean(x['values']) for r in results for x in r['entries'] if x['type'] in (v.INT_DATA,v.DOUBLE_DATA,v.VEC3D_DATA,v.DOUBLE_MATRIX_DATA) and x['name'] not in ['Analysis_Duration_Sec','WallTime']}
                self.assertEqual(fields(collect_results(v)),fields(data['results']))
                self.assertEqual(read_adb(next(folder.glob('*.adb'))),read_adb(next(direct.glob('*.adb'))))
        self.assertNotEqual(*geometry);self.assertEqual(self.model.read_bytes(),before)
