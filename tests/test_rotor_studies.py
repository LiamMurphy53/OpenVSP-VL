"""Frozen rotor studies retain native drivers and reject calculated-value sweeps."""
import json
import math
from pathlib import Path
import shutil
import sys
import unittest
import test_studies
import native_service as service
import native_studies as studies
import native_worker
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class RotorStudies(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    worker=test_studies.NativeStudies.worker
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def fixture(self):
        v=self.v;prop=v.AddGeom('PROP');v.SetParmValUpdate(prop,'PropMode','Design',v.PROP_DISK);v.SetParmValUpdate(prop,'X_Rel_Location','XForm',-8);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        cid=v.FindActuatorDisk(0);state,saved=self.worker(dict(action='mutate',operation='rotor-disk-drivers',id=cid,choices=[0,3,6]));shutil.copy2(saved,self.model)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        return prop,cid,{v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}

    def test_schema_and_save_reject_derived_disk_dimensions(self):
        _,_,p=self.fixture();state,_=self.worker(dict(action='study-schema'));params={x['id']:x for x in state['parameters']}
        for name in ('RotorThrust','RotorPower','RotorRPM'):self.assertTrue(params[p[name]].get('editable',True))
        before=self.model.read_bytes()
        for name in ('RotorCP','RotorCT','RotorEta','RotorDiameter','RotorHubDiameter'):
            self.assertFalse(params[p[name]]['editable']);self.assertIn('Calculated by OpenVSP',params[p[name]]['readOnlyReason'])
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'Choose an editable driver'):
                self.save([dict(kind='parameter',id=p[name],values=[1.])])
        self.assertEqual(self.model.read_bytes(),before)

    def test_case_hub_dependency_is_checked_before_native_model_write(self):
        _,_,p=self.fixture();before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'derives'):
            self.worker(dict(action='study-model',parameters=[dict(id=p['RotorCP'],value=.5)]))
        state,manual=self.worker(dict(action='study-model',parameters=[dict(id=p['RotorHubDiameter'],value=.25),dict(id=p['AutoHubDiaFlag'],value=0)]))
        self.v.ClearVSPModel();self.v.ReadVSPFile(str(manual));self.v.Update();self.assertEqual(self.v.GetParmVal(p['RotorHubDiameter']),.25)
        with self.assertRaisesRegex(ValueError,'derives'):
            self.worker(dict(action='study-model',parameters=[dict(id=p['RotorHubDiameter'],value=.5),dict(id=p['AutoHubDiaFlag'],value=1)]),manual)
        self.assertEqual(self.model.read_bytes(),before)

    def test_rotating_group_sweeps_use_source_geometry_and_rotor_rpm(self):
        v=self.v;prop=v.AddGeom('PROP');v.SetParmValUpdate(prop,'PropMode','Design',v.PROP_BLADES);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        rotor=None;fixed=None
        for i in range(v.GetNumUnsteadyGroups()):
            cid=v.FindUnsteadyGroup(i);p={v.GetParmName(x):x for x in v.FindContainerParmIDs(cid)}
            if v.GetParmVal(p['GeomPropertyType'])==2:rotor=p
            else:fixed=p
        self.assertIsNotNone(rotor);self.assertIsNotNone(fixed)
        state,_=self.worker(dict(action='study-schema'));params={p['id']:p for p in state['parameters']};before=self.model.read_bytes()
        self.assertTrue(params[rotor['RPM']].get('editable',True))
        for p in [rotor[n] for n in ('RotorDia','Ox','Oy','Oz','Rx','Ry','Rz')]+[fixed['RPM']]:
            self.assertFalse(params[p]['editable'])
            with self.subTest(parameter=p),self.assertRaisesRegex(ValueError,'Choose an editable driver'):
                self.save([dict(kind='parameter',id=p,values=[1.])])
            with self.subTest(parameter=p),self.assertRaises(ValueError):
                self.worker(dict(action='study-model',parameters=[dict(id=p,value=1.)]))
        diameter=v.FindParm(prop,'Diameter','Design')
        state,case=self.worker(dict(action='study-model',parameters=[dict(id=diameter,value=6.),dict(id=rotor['RPM'],value=1350.)]))
        v.ClearVSPModel();v.ReadVSPFile(str(case));v.Update()
        self.assertEqual(v.GetParmVal(rotor['RotorDia']),6.)
        self.assertEqual(v.GetParmVal(rotor['RPM']),1350.)
        self.assertEqual(self.model.read_bytes(),before)

    def test_case_applies_native_speed_coupling_before_multiple_rotor_rpms(self):
        v=self.v
        for y in (-8,8):
            g=v.AddGeom('PROP');v.SetParmValUpdate(g,'PropMode','Design',v.PROP_BLADES);v.SetParmValUpdate(g,'Y_Rel_Location','XForm',y)
        c=v.FindContainer('VSPAEROSettings',0);p={v.GetParmName(x):x for x in v.FindContainerParmIDs(c)}
        v.SetParmValUpdate(p['m_PropBladesMode'],v.VSPAERO_PROP_UNSTEADY);v.SetParmValUpdate(p['UniformPropRPMFlag'],1);v.Update()
        rpms=[]
        for i in range(v.GetNumUnsteadyGroups()):
            q={v.GetParmName(x):x for x in v.FindContainerParmIDs(v.FindUnsteadyGroup(i))}
            if v.GetParmVal(q['GeomPropertyType'])==2:rpms.append(q['RPM'])
        self.assertEqual(len(rpms),2);v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        request=[dict(id=rpms[0],value=1200.),dict(id=rpms[1],value=1500.),dict(id=p['UniformPropRPMFlag'],value=0)]
        state,case=self.worker(dict(action='study-model',parameters=request))
        v.ClearVSPModel();v.ReadVSPFile(str(case));v.Update()
        self.assertEqual([v.GetParmVal(x) for x in rpms],[1200.,1500.])
        self.assertEqual([x['effective'] for x in state['parameters']],[1200.,1500.,0])
        self.assertEqual(self.model.read_bytes(),before)

    def test_representation_regeneration_rejects_stale_group_in_either_axis_order(self):
        v=self.v;prop=v.AddGeom('PROP');v.Update()
        mode=v.FindParm(prop,'PropMode','Design')
        rpm=v.FindParm(v.FindUnsteadyGroup(1),'RPM','UnsteadyGroup')
        self.assertTrue(v.ValidParm(rpm));v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        records=[dict(id=mode,value=v.PROP_DISK),dict(id=rpm,value=1350.)]
        for request in (records,list(reversed(records))):
            with self.subTest(order=[x['id'] for x in request]),self.assertRaisesRegex(ValueError,'regenerate rotor groups'):
                self.worker(dict(action='study-model',parameters=request))
            self.assertEqual(self.model.read_bytes(),before)
        state,case=self.worker(dict(action='study-model',parameters=[dict(id=rpm,value=1350.)]))
        v.ClearVSPModel();v.ReadVSPFile(str(case));v.Update()
        self.assertEqual(v.GetParmVal(rpm),1350.)
        self.assertEqual(state['parameters'][0]['effective'],1350.)
        self.assertEqual(self.model.read_bytes(),before)

    def test_saved_disk_thrust_sweep_runs_native_solver_and_keeps_baseline(self):
        v=self.v;_,cid,p=self.fixture();before=self.model.read_bytes()
        flight={'NCPU':1,'AlphaStart':4.,'AlphaNpts':1,'BetaNpts':1,'MachStart':.1,'MachNpts':1,'ReCrefNpts':1,'WakeNumIter':5,'PropBladesMode':v.VSPAERO_PROP_STATIC,'RefFlag':1,'WingID':self.gid,'GeomSet':-1,'ThinGeomSet':0}
        stage=dict(name='VSPAEROSweep',inputs=[dict(name=n,values=[x]) for n,x in flight.items()],geometryInputs=[dict(name='GeomSet',values=[-1]),dict(name='ThinGeomSet',values=[0])])
        plan=self.save([dict(kind='parameter',id=p['RotorThrust'],values=[1000.,1500.])],stages=[stage])
        frozen=studies.study_folder(plan['id'])/'aircraft.vsp3';frozen_before=frozen.read_bytes()
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id']);self.assertEqual(batch['status'],'complete',batch)
        for case in batch['cases']:
            model=studies.batch_folder(plan['id'],batch['id'])/'cases'/str(case['index'])/'aircraft.vsp3'
            v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update();self.assertEqual(v.GetParmVal(p['RotorThrust']),case['values'][0])
            from native_references import references
            self.assertEqual(references(v)[cid]['propDrivers'],[0,3,6])
            job=service.job_state(case['stages'][0]['job']);result=job['result']
            v.SetVSP3FileName(str(self.path/f'direct-{case["index"]}.vsp3'))
            for name,entries in [('VSPAEROComputeGeometry',result['geometryInputs']),('VSPAEROSweep',result['inputs'])]:
                v.SetAnalysisInputDefaults(name)
                for e in entries:
                    setters={v.INT_DATA:v.SetIntAnalysisInput,v.DOUBLE_DATA:v.SetDoubleAnalysisInput,v.STRING_DATA:v.SetStringAnalysisInput}
                    self.assertIn(e['type'],setters);setters[e['type']](name,e['name'],e['values'],e['index'])
                self.assertTrue(v.ExecAnalysis(name))
            for r in result['results']:
                rid=v.FindResultsID(r['name'],r['index']);self.assertTrue(rid)
                for e in r['entries']:
                    if e['name'] in ('Analysis_Duration_Sec','WallTime') or e['type'] not in (v.INT_DATA,v.DOUBLE_DATA):continue
                    native=list((v.GetIntResults if e['type']==v.INT_DATA else v.GetDoubleResults)(rid,e['name'],e['index']));native=[None if isinstance(x,float) and not math.isfinite(x) else x for x in native]
                    self.assertEqual(native,e['values'],(r['name'],e['name']))
        self.assertEqual(frozen.read_bytes(),frozen_before);self.assertEqual(self.model.read_bytes(),before)
