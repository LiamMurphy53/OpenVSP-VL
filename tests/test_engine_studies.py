"""Dependent flowpath study axes must apply as one native specification."""
from collections import Counter
import unittest
import test_studies
import native_service as service
import native_studies as studies
import native_worker


class EngineStudies(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def fixture(self,kind='FUSELAGE'):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom(kind);v.Update()
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        names=['InletLipIndex','OutletLipIndex','GeomOutType','GeomInType','GeomIOType']
        self.ids={n:v.FindParm(self.gid,n,'EngineModel') for n in names}
        return [dict(kind='parameter',id=self.ids[n],values=values) for n,values in zip(names,
            [[1,2],[3],[v.ENGINE_GEOM_TO_LIP],[v.ENGINE_GEOM_TO_LIP],[v.ENGINE_GEOM_INLET_OUTLET]])]

    def capture(self):
        v=self.v;g=self.gid
        parameters=Counter((v.GetParmGroupName(p),v.GetParmName(p),v.GetParmVal(p)) for p in v.GetGeomParmIDs(g))
        surfaces=[]
        for i in range(v.GetTotalNumSurfs(g)):
            u,w=v.GetUWTess01(g,i%v.GetNumMainSurfs(g))
            surfaces.append([[q.x(),q.y(),q.z()] for q in v.CompVecPnt01(g,i,[a for a in u for _ in w],[b for _ in u for b in w])])
        return parameters,surfaces

    def test_reversed_axes_activate_and_build_original_flowpath_before_analysis(self):
        v=self.v
        for kind in ('FUSELAGE','STACK'):
            with self.subTest(kind=kind):
                axes=self.fixture(kind)
                if kind=='FUSELAGE':axes.insert(0,dict(kind='parameter',id=v.FindParm(self.gid,'Length','Design'),values=[18.,24.]))
                before=self.model.read_bytes()
                source=self.path/'independent-baseline.vsp3';source.write_bytes(before)
                plan=self.save(axes);frozen=studies.study_folder(plan['id'])/'aircraft.vsp3';frozen_before=frozen.read_bytes()
                batch=self.wait(plan['id'],studies.launch(plan['id'])['id'])
                self.assertEqual(batch['status'],'complete',batch)
                for case in batch['cases']:
                    model=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
                    v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update();actual=self.capture()
                    v.ClearVSPModel();v.ReadVSPFile(str(source));v.Update()
                    for axis,value in zip(axes,case['values']):v.SetParmVal(axis['id'],value)
                    v.Update();reference=self.path/'independent-final.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
                    v.ClearVSPModel();v.ReadVSPFile(str(reference));v.Update()
                    self.assertEqual(actual,self.capture())
                    v.SetVSP3FileName(str(self.path/'independent-analysis.vsp3'))
                    v.SetAnalysisInputDefaults('CompGeom');v.ExecAnalysis('CompGeom');native_worker.errors(v)
                    job=service.job_state(case['stages'][0]['job'])
                    for result in native_worker.collect_results(v):
                        saved=next(r for r in job['result']['results'] if r['name']==result['name'] and r['index']==result['index'])
                        for field in result['entries']:
                            if field['name']!='Analysis_Duration_Sec' and field['type'] in (v.INT_DATA,v.DOUBLE_DATA,v.VEC3D_DATA,v.DOUBLE_MATRIX_DATA):
                                self.assertEqual(next(e['values'] for e in saved['entries'] if e['name']==field['name'] and e['index']==field['index']),field['values'],field['name'])
                    self.assertEqual([p['value'] for p in job['result']['studyParameters']],case['values'])
                self.assertEqual(self.model.read_bytes(),before)
                self.assertEqual(frozen.read_bytes(),frozen_before)
                self.assertFalse(service.HISTORY)


    def test_inactive_station_requires_compatible_role_controller(self):
        axes=self.fixture()
        with self.assertRaisesRegex(ValueError,'compatible controller axes'):
            self.save(axes[:1])

    def test_collapsed_case_stops_before_analysis_and_corrected_study_recovers(self):
        axes=self.fixture()
        axes[0]['values']=[0];axes[1]['values']=[0]
        before=self.model.read_bytes();plan=self.save(axes)
        failed=self.wait(plan['id'],studies.launch(plan['id'])['id'])
        self.assertEqual(failed['status'],'failed',failed)
        case=failed['cases'][0];self.assertIn('stations coincide',case['error'])
        self.assertTrue(all(s['status']=='not-run' and not s.get('job') for s in case['stages']))
        model=studies.batch_folder(plan['id'],failed['id'])/'cases/0/aircraft.vsp3'
        self.assertEqual(model.read_bytes(),before)
        axes[0]['values']=[1];axes[1]['values']=[3]
        corrected=self.save(axes,id=plan['id'],definitionVersion=plan['version'],baseline='saved')
        completed=self.wait(plan['id'],studies.launch(plan['id'])['id'])
        self.assertEqual(completed['status'],'complete',completed)
        self.assertEqual(corrected['sourceHash'],plan['sourceHash'])
        self.assertEqual(self.model.read_bytes(),before)
        self.assertFalse(service.HISTORY)


    def test_unused_station_case_is_not_silently_assigned_or_analyzed(self):
        v=self.v;axes=self.fixture()
        axes[0]['values']=[1];axes[-1]['values']=[v.ENGINE_GEOM_NONE,v.ENGINE_GEOM_INLET_OUTLET]
        before=self.model.read_bytes();plan=self.save(axes)
        batch=self.wait(plan['id'],studies.launch(plan['id'])['id'])
        self.assertEqual(batch['status'],'partial',batch)
        bad,good=batch['cases'];self.assertEqual(bad['status'],'failed')
        self.assertIn('OpenVSP',bad['error']);self.assertIn('Inlet lip cross-section',bad['error'])
        self.assertTrue(all(s['status']=='not-run' and not s.get('job') for s in bad['stages']))
        self.assertEqual(good['status'],'complete')
        model=studies.batch_folder(plan['id'],batch['id'])/'cases/0/aircraft.vsp3'
        self.assertEqual(model.read_bytes(),before)
        self.assertEqual(self.model.read_bytes(),before)


    def test_late_link_driver_cannot_collapse_prepared_stations_before_analysis(self):
        v=self.v;axes=self.fixture();axes[0]['values']=[1]
        driver=v.AddUserParm(v.PARM_DOUBLE_TYPE,'Flowpath station driver','Study')
        v.SetParmVal(driver,0.)
        for name in ('InletLipIndex','InletFaceIndex','OutletLipIndex','OutletFaceIndex'):
            target=v.FindParm(self.gid,name,'EngineModel');link=v.AddParmLink(driver,target)
            v.SetParmLinkScaleFlag(link,True);v.SetParmLinkOffsetFlag(link,True)
            v.SetParmVal(v.FindParm(link,'Scale','Link'),1.);v.SetParmVal(v.FindParm(link,'Offset','Link'),0.)
        # The later case must change the source to trigger native link propagation.
        v.SetParmValUpdate(driver,1.);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        axes.insert(0,dict(kind='parameter',id=driver,values=[0.]))
        before=self.model.read_bytes();plan=self.save(axes)
        batch=self.wait(plan['id'],studies.launch(plan['id'])['id'])
        self.assertEqual(batch['status'],'failed',batch)
        case=batch['cases'][0];self.assertIn('stations coincide',case['error'])
        self.assertTrue(all(s['status']=='not-run' and not s.get('job') for s in case['stages']))
        self.assertEqual(self.model.read_bytes(),before)
