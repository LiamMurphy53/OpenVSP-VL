"""Controller-dependent wing blend studies use original native geometry/results."""
import unittest
import test_studies
import test_engine_studies
import native_service as service
import native_studies as studies
import native_worker

class WingBlendStudies(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait
    capture=test_engine_studies.EngineStudies.capture

    def fixture(self):
        v=self.v;v.InsertXSec(self.gid,1,v.XS_FOUR_SERIES);v.Update()
        self.x=v.GetXSec(v.GetXSecSurf(self.gid,0),1)
        self.ids={n:v.GetXSecParm(self.x,n) for n in ('InLEMode','OutLEMode','InTEMode','OutTEMode','InLESweep','InLEDihedral','OutTEStrength')}
        v.WriteVSPFile(str(self.model),v.SET_ALL)

    def axis(self,name,values):return dict(kind='parameter',id=self.ids[name],values=values)

    def compare(self,axes):
        v=self.v;before=self.model.read_bytes();source=self.path/'independent-baseline.vsp3';source.write_bytes(before)
        plan=self.save(axes);frozen=studies.study_folder(plan['id'])/'aircraft.vsp3';frozen_before=frozen.read_bytes()
        batch=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(batch['status'],'complete',batch)
        for case in batch['cases']:
            model=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
            v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update();actual=self.capture()
            v.ClearVSPModel();v.ReadVSPFile(str(source));v.Update()
            order={'InLEMode':-14,'InTEMode':-13,'OutLEMode':-12,'OutTEMode':-11}
            for axis,value in sorted(zip(axes,case['values']),key=lambda pair:order.get(v.GetParmName(pair[0]['id']),0)):
                v.SetParmValUpdate(axis['id'],value);v.Update()
            native_worker.errors(v);reference=self.path/'original-final.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
            v.ClearVSPModel();v.ReadVSPFile(str(reference));v.Update();self.assertEqual(actual,self.capture())
            v.SetVSP3FileName(str(self.path/'original-analysis.vsp3'));v.SetAnalysisInputDefaults('CompGeom');v.ExecAnalysis('CompGeom');native_worker.errors(v)
            job=service.job_state(case['stages'][0]['job'])
            for result in native_worker.collect_results(v):
                saved=next(r for r in job['result']['results'] if r['name']==result['name'] and r['index']==result['index'])
                for field in result['entries']:
                    if field['name']!='Analysis_Duration_Sec' and field['type'] in (v.INT_DATA,v.DOUBLE_DATA,v.VEC3D_DATA,v.DOUBLE_MATRIX_DATA):
                        self.assertEqual(next(e['values'] for e in saved['entries'] if e['name']==field['name'] and e['index']==field['index']),field['values'],field['name'])
            self.assertEqual([p['value'] for p in job['result']['studyParameters']],case['values'])
        self.assertEqual(self.model.read_bytes(),before);self.assertEqual(frozen.read_bytes(),frozen_before);self.assertFalse(service.HISTORY)

    def test_reversed_angle_and_strength_axes_activate_and_match_original(self):
        self.fixture();v=self.v
        self.compare([self.axis('OutTEStrength',[.4,.8]),self.axis('InLESweep',[15.,25.]),self.axis('OutTEMode',[v.BLEND_ANGLES]),self.axis('InLEMode',[v.BLEND_ANGLES])])

    def test_matching_mode_chain_is_independent_of_axis_declaration_order(self):
        self.fixture();v=self.v
        self.compare([self.axis('OutTEMode',[v.BLEND_MATCH_LE_ANGLES]),self.axis('OutLEMode',[v.BLEND_MATCH_IN_ANGLES]),self.axis('InTEMode',[v.BLEND_MATCH_LE_ANGLES]),self.axis('InLEDihedral',[7.]),self.axis('InLESweep',[18.]),self.axis('InLEMode',[v.BLEND_ANGLES])])

    def test_automatic_case_fails_before_analysis_compatible_case_continues(self):
        self.fixture();v=self.v;before=self.model.read_bytes()
        axes=[self.axis('InLESweep',[23.]),self.axis('InLEMode',[v.BLEND_FREE,v.BLEND_ANGLES])]
        plan=self.save(axes);batch=self.wait(plan['id'],studies.launch(plan['id'])['id'])
        self.assertEqual([c['status'] for c in batch['cases']],['failed','complete'])
        bad=batch['cases'][0];self.assertIn('Automatic',bad['error']);self.assertTrue(all(s['status']=='not-run' and not s.get('job') for s in bad['stages']))
        model=studies.batch_folder(plan['id'],batch['id'])/'cases/0/aircraft.vsp3';self.assertEqual(model.read_bytes(),before)
        self.assertEqual(self.model.read_bytes(),before)
        axes[1]['values']=[v.BLEND_ANGLES]
        corrected=self.save(axes,id=plan['id'],definitionVersion=plan['version'],baseline='saved')
        complete=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(complete['status'],'complete');self.assertEqual(corrected['sourceHash'],plan['sourceHash'])

    def test_missing_mode_controller_and_absent_neighbor_are_rejected(self):
        self.fixture();v=self.v
        with self.assertRaisesRegex(ValueError,'compatible controller axes'):self.save([self.axis('InLESweep',[23.])])
        root=v.GetXSec(v.GetXSecSurf(self.gid,0),0)
        with self.assertRaisesRegex(ValueError,'neighbor'):self.save([dict(kind='parameter',id=v.GetXSecParm(root,'InLESweep'),values=[12.]),dict(kind='parameter',id=v.GetXSecParm(root,'InLEMode'),values=[1])])

    def test_late_link_cannot_leave_swept_angle_calculated_before_analysis(self):
        self.fixture();v=self.v
        driver=v.AddUserParm(v.PARM_DOUBLE_TYPE,'Wing blend mode driver','Study');v.SetParmVal(driver,0.)
        link=v.AddParmLink(driver,self.ids['InLEMode']);v.SetParmLinkScaleFlag(link,True);v.SetParmLinkOffsetFlag(link,True)
        v.SetParmVal(v.FindParm(link,'Scale','Link'),1.);v.SetParmVal(v.FindParm(link,'Offset','Link'),0.)
        v.SetParmValUpdate(driver,1.);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        before=self.model.read_bytes();axes=[self.axis('InLEMode',[1]),self.axis('InLESweep',[23.]),dict(kind='parameter',id=driver,values=[0.])]
        plan=self.save(axes);batch=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(batch['status'],'failed',batch)
        case=batch['cases'][0];self.assertIn('Automatic',case['error']);self.assertTrue(all(s['status']=='not-run' and not s.get('job') for s in case['stages']))
        self.assertEqual(self.model.read_bytes(),before)
