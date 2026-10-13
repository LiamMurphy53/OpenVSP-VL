"""Dependent CG ranges and saved gear calculations versus original native replay."""
import sys,json,unittest
import test_studies,test_gear_cases,test_gear_controls,test_geometry_cases
import native_studies as studies,native_service as service,native_worker,native_geometry_cases
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class NativeGearStudies(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    worker=test_studies.NativeStudies.worker
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait
    fixture=test_gear_cases.NativeGearCases.fixture
    assert_native_geometry=test_gear_controls.NativeGearControls.assert_native_geometry
    canonical=test_geometry_cases.NativeGeometryCases.canonical
    assertResults=test_geometry_cases.NativeGeometryCases.assertResults

    def ids(self):
        return {name:self.v.FindParm(self.gear,name,'GroundPlane') for name in ('XCGNominalLocal','XCGMinLocal','XCGMaxLocal')}

    def reread_baseline(self):
        v=self.v
        # Release original bogies before clearing their native parent.
        if self.gear in v.FindGeoms():
            for b in list(v.GetAllBogies(self.gear)):v.DelBogie(self.gear,b)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        v.SetAuxiliaryGeomContactPtID(self.aux,0,v.GetAuxiliaryGeomContactPtID(self.aux,0));v.Update()

    def assert_prepared(self,path,edits,native_lifecycle=False):
        v=self.v
        def refresh_original():
            import native_preview
            for g in v.FindGeoms():
                if v.GetGeomTypeName(g).upper()=='GEAR':
                    for b in v.GetAllBogies(g):native_preview.bogie_retraction(v,g,b,'refresh')
            v.Update();v.SetAuxiliaryGeomContactPtID(self.aux,0,v.GetAuxiliaryGeomContactPtID(self.aux,0));v.Update()
        if native_lifecycle:
            if self.gear in v.FindGeoms():
                for b in list(v.GetAllBogies(self.gear)):v.DelBogie(self.gear,b)
            v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();refresh_original()
        else:self.reread_baseline()
        for p,x in edits:v.SetParmValUpdate(p,x)
        v.Update()
        # Reevaluate the original gear after aircraft bounds have settled;
        # its automatic plane is also the auxiliary's attachment surface.
        if native_lifecycle:refresh_original()
        else:
            v.SetParmValUpdate(self.gear,'CGLocalFlag','GroundPlane',v.GetParmVal(self.gear,'CGLocalFlag','GroundPlane'))
            v.SetAuxiliaryGeomContactPtID(self.aux,0,v.GetAuxiliaryGeomContactPtID(self.aux,0));v.Update()
        # Match the saved/reopened lifecycle using an independently generated
        # SDK file, never the worker's prepared aircraft as the expected input.
        expected_file=self.path/'independent-cg-prepared.vsp3'
        v.WriteVSPFile(str(expected_file),v.SET_ALL)
        for b in list(v.GetAllBogies(self.gear)):v.DelBogie(self.gear,b)
        v.ClearVSPModel();v.ReadVSPFile(str(expected_file));v.Update()
        if native_lifecycle:refresh_original()
        else:v.SetAuxiliaryGeomContactPtID(self.aux,0,v.GetAuxiliaryGeomContactPtID(self.aux,0));v.Update()
        state,_=self.worker(dict(action='state'),path)
        for g in v.FindGeoms():
            self.assert_native_geometry(state,g,generated_groups=('Cap','Chevron','Close','Flap','Trim','XSecCurve','XSecCurve_Background') if g==self.aux else ())
            fields=next(c['params'] for c in state['components'] if c['id']==g)
            native={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.GetGeomParmIDs(g)}
            for p in fields:
                pid=native[(p['rawGroup'],p['name'])]
                self.assertEqual(p['min'],v.GetParmLowerLimit(pid),(g,p['rawGroup'],p['name'],'min'));self.assertEqual(p['max'],v.GetParmUpperLimit(pid),(g,p['rawGroup'],p['name'],'max'))

    def test_both_nominal_range_directions_ignore_axis_order_and_match_native(self):
        self.fixture();v=self.v;ids=self.ids();original=self.model.read_bytes()
        for nominal,minimum,maximum in [(3.5,3.2,4.2),(2.5,2.2,2.8)]:
            edits=[(ids['XCGNominalLocal'],nominal),(ids['XCGMinLocal'],minimum),(ids['XCGMaxLocal'],maximum)]
            for reverse in (False,True):
                requested=list(reversed(edits)) if reverse else edits
                data,path=self.worker(dict(action='study-model',parameters=[dict(id=p,value=x) for p,x in requested]))
                self.assertEqual([(p['id'],p['effective']) for p in data['parameters']],requested)
                self.assertEqual(data['warnings'],[]);self.assert_prepared(path,edits)
        self.assertEqual(self.model.read_bytes(),original)

    def test_native_current_limits_reject_invalid_range_atomically(self):
        self.fixture();ids=self.ids();before=self.model.read_bytes()
        # Range is baseline-valid, but becomes invalid after lowering nominal.
        with self.assertRaisesRegex(ValueError,'range limits after applying'):
            self.worker(dict(action='study-model',parameters=[dict(id=ids['XCGMinLocal'],value=2.9),dict(id=ids['XCGNominalLocal'],value=2.5)]))
        self.assertEqual(self.model.read_bytes(),before)
        for name,value in [('XCGMinLocal',3.2),('XCGMaxLocal',2.8)]:
            with self.assertRaisesRegex(ValueError,'native parameter limits'):
                self.save([dict(kind='parameter',id=ids[name],values=[value])])
        self.assertEqual(self.model.read_bytes(),before)

    def test_gear_transform_and_multiple_cg_coordinates_precede_ranges(self):
        self.fixture();v=self.v
        edits=[(v.FindParm(self.gear,n,g),x) for n,g,x in [
            ('X_Rel_Location','XForm',5),('Z_Rel_Rotation','XForm',20),
            ('XCGNominalLocal','GroundPlane',3.5),('YCGNominalLocal','GroundPlane',.4),
            ('ZCGNominalLocal','GroundPlane',4),('XCGMinLocal','GroundPlane',3.2),
            ('YCGMinLocal','GroundPlane',.2),('ZCGMaxLocal','GroundPlane',4.2)]]
        data,path=self.worker(dict(action='study-model',parameters=[dict(id=p,value=x) for p,x in reversed(edits)]))
        self.assertEqual(data['warnings'],[])
        self.assert_prepared(path,edits)

    def test_saved_two_axis_study_matches_original_geometry_and_weight_results(self):
        self.fixture();ids=self.ids();original=self.model.read_bytes()
        plan=self.save([dict(kind='parameter',id=ids['XCGMinLocal'],values=[3.2]),dict(kind='parameter',id=ids['XCGNominalLocal'],values=[3.5,4.])],stages=[dict(name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[self.cid])])])
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id'])
        self.assertEqual(batch['status'],'complete',batch)
        for case in batch['cases']:
            path=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
            self.assert_prepared(path,[(ids['XCGNominalLocal'],case['values'][1]),(ids['XCGMinLocal'],case['values'][0])])
            v=self.v;native_geometry_cases.update(v);v.SetAnalysisInputDefaults('GeometryAnalysis');v.SetStringAnalysisInput('GeometryAnalysis','CaseID',[self.cid]);v.ExecAnalysis('GeometryAnalysis');native_worker.errors(v)
            self.assertResults(native_worker.collect_results(v),service.job_state(case['stages'][0]['job'])['result']['results'])
        self.assertEqual(self.model.read_bytes(),original)
        field=next(f for f in studies.result_fields(plan['id'],batch['id']) if f['field']=='NominalReactions')
        rows=studies.comparison(plan['id'],batch['id'],field['key'])['rows']
        self.assertEqual([r['requested'] for r in rows],[r['effective'] for r in rows])

    def test_saved_frame_switch_exposes_original_driver_coordinates_both_directions(self):
        self.fixture();v=self.v
        for target in (0,1):
            self.reread_baseline()
            for name,value in [('X_Rel_Location',5),('Y_Rel_Location',2),('Z_Rel_Rotation',20)]:v.SetParmValUpdate(self.gear,name,'XForm',value)
            flag=v.FindParm(self.gear,'CGLocalFlag','GroundPlane');v.SetParmValUpdate(flag,1-target);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
            frame='Global' if target==0 else 'Local';coordinate=v.FindParm(self.gear,'XCGNominal'+frame,'GroundPlane')
            schema,_=self.worker(dict(action='study-schema'));p=next(p for p in schema['parameters'] if p['id']==coordinate)
            self.assertFalse(p['editable']);self.assertEqual(p['cgFrame'],dict(parameter=flag,value=target,label='World axes' if target==0 else 'Gear axes'))
            with self.assertRaisesRegex(ValueError,'Calculated'):
                self.save([dict(kind='parameter',id=coordinate,values=[3.5])])
            # Deliberately put the coordinate before its frame controller.
            plan=self.save([dict(kind='parameter',id=coordinate,values=[8.,8.5] if target==0 else [3.5,4.]),dict(kind='parameter',id=flag,values=[target])],stages=[dict(name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[self.cid])])])
            batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'complete',batch)
            for case in batch['cases']:
                path=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
                self.assert_prepared(path,[(flag,target),(coordinate,case['values'][0])],native_lifecycle=True)
                native_geometry_cases.update(v);v.SetAnalysisInputDefaults('GeometryAnalysis');v.SetStringAnalysisInput('GeometryAnalysis','CaseID',[self.cid]);v.ExecAnalysis('GeometryAnalysis');native_worker.errors(v)
                self.assertResults(native_worker.collect_results(v),service.job_state(case['stages'][0]['job'])['result']['results'])

    def test_mixed_frames_stop_calculated_coordinate_cases_and_preserve_valid_results(self):
        self.fixture();v=self.v;flag=v.FindParm(self.gear,'CGLocalFlag','GroundPlane');coordinate=v.FindParm(self.gear,'XCGNominalGlobal','GroundPlane');original=self.model.read_bytes()
        plan=self.save([dict(kind='parameter',id=coordinate,values=[3.5]),dict(kind='parameter',id=flag,values=[1,0])],stages=[dict(name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[self.cid])])])
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'partial')
        failed,valid=batch['cases'];self.assertEqual(failed['status'],'failed');self.assertIn('Calculated',failed['error']);self.assertIsNone(failed['stages'][0].get('job'));self.assertEqual(valid['status'],'complete')
        self.assertEqual(self.model.read_bytes(),original)

if __name__=='__main__':unittest.main()
