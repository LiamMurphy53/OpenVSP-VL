"""Native Stack basis and loop controllers precede coordinate study values."""
import unittest
import test_studies
import test_engine_studies
import native_service as service
import native_studies as studies
import native_worker

class StackPositionStudies(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait
    capture=test_engine_studies.EngineStudies.capture

    def fixture(self,loop=False):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom('STACK');v.Update()
        surf=v.GetXSecSurf(self.gid,0);prior=v.GetXSec(surf,1)
        v.SetParmValUpdate(v.GetXSecParm(prior,'ZRotate'),17.);v.Update()
        self.x=v.GetXSec(surf,v.GetNumXSec(surf)-1 if loop else 2)
        self.basis=v.GetXSecParm(self.x,'XSAbsRelFlag');self.target=v.GetXSecParm(self.x,'XAbs')
        self.order=v.FindParm(self.gid,'OrderPolicy','Design')
        if loop:v.SetParmValUpdate(self.order,1);v.Update()
        v.WriteVSPFile(str(self.model),v.SET_ALL)

    def test_reversed_basis_and_loop_axes_match_original_geometry_and_results(self):
        v=self.v
        for loop in (False,True):
            self.fixture(loop);before=self.model.read_bytes();source=self.path/'original-source.vsp3';source.write_bytes(before)
            axes=[dict(kind='parameter',id=self.target,values=[2.,3.]),dict(kind='parameter',id=self.basis,values=[v.ABS])]
            if loop:axes.append(dict(kind='parameter',id=self.order,values=[0]))
            plan=self.save(axes);frozen=studies.study_folder(plan['id'])/'aircraft.vsp3';frozen_before=frozen.read_bytes()
            batch=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(batch['status'],'complete',batch)
            for case in batch['cases']:
                candidate=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
                v.ClearVSPModel();v.ReadVSPFile(str(candidate));v.Update();actual=self.capture()
                v.ClearVSPModel();v.ReadVSPFile(str(source));v.Update()
                if loop:v.SetParmValUpdate(self.order,0);v.Update()
                v.SetParmValUpdate(self.basis,v.ABS);v.Update();v.SetParmValUpdate(self.target,case['values'][0]);v.Update()
                original=self.path/'original-final.vsp3';v.WriteVSPFile(str(original),v.SET_ALL)
                v.ClearVSPModel();v.ReadVSPFile(str(original));v.Update();self.assertEqual(actual,self.capture())
                v.SetVSP3FileName(str(self.path/'original-analysis.vsp3'));v.SetAnalysisInputDefaults('CompGeom');v.ExecAnalysis('CompGeom');native_worker.errors(v)
                job=service.job_state(case['stages'][0]['job'])
                for result in native_worker.collect_results(v):
                    saved=next(r for r in job['result']['results'] if r['name']==result['name'] and r['index']==result['index'])
                    for field in result['entries']:
                        if field['name']!='Analysis_Duration_Sec' and field['type'] in (v.INT_DATA,v.DOUBLE_DATA,v.VEC3D_DATA,v.DOUBLE_MATRIX_DATA):self.assertEqual(next(e['values'] for e in saved['entries'] if e['name']==field['name'] and e['index']==field['index']),field['values'],field['name'])
                self.assertEqual([p['value'] for p in job['result']['studyParameters']],case['values'])
            self.assertEqual(self.model.read_bytes(),before);self.assertEqual(frozen.read_bytes(),frozen_before);self.assertFalse(service.HISTORY)

    def test_incompatible_basis_case_stops_and_missing_controller_is_rejected(self):
        self.fixture();v=self.v;before=self.model.read_bytes()
        axes=[dict(kind='parameter',id=self.target,values=[3.]),dict(kind='parameter',id=self.basis,values=[v.REL,v.ABS])]
        with self.assertRaisesRegex(ValueError,'compatible controller axes'):self.save(axes[:1])
        plan=self.save(axes);batch=self.wait(plan['id'],studies.launch(plan['id'])['id'])
        self.assertEqual([c['status'] for c in batch['cases']],['failed','complete'])
        case=batch['cases'][0];self.assertIn('coordinate basis',case['error']);self.assertTrue(all(s['status']=='not-run' and not s.get('job') for s in case['stages']))
        candidate=studies.batch_folder(plan['id'],batch['id'])/'cases/0/aircraft.vsp3';self.assertEqual(candidate.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)

    def test_late_link_cannot_recalculate_requested_absolute_coordinate(self):
        self.fixture();v=self.v
        driver=v.AddUserParm(v.PARM_DOUBLE_TYPE,'Stack coordinate basis driver','Study');v.SetParmVal(driver,1.)
        link=v.AddParmLink(driver,self.basis);v.SetParmLinkScaleFlag(link,True);v.SetParmLinkOffsetFlag(link,True)
        v.SetParmVal(v.FindParm(link,'Scale','Link'),1.);v.SetParmVal(v.FindParm(link,'Offset','Link'),0.)
        v.SetParmValUpdate(driver,0.);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        axes=[dict(kind='parameter',id=self.basis,values=[v.ABS]),dict(kind='parameter',id=self.target,values=[3.]),dict(kind='parameter',id=driver,values=[1.])]
        plan=self.save(axes);batch=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(batch['status'],'failed',batch)
        case=batch['cases'][0];self.assertIn('coordinate basis',case['error']);self.assertTrue(all(s['status']=='not-run' and not s.get('job') for s in case['stages']));self.assertEqual(self.model.read_bytes(),before)
