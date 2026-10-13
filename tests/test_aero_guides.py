"""Native solver guidance and configuration recovery."""
import json
import math
import sys
import unittest
import test_native
import native_worker
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the native Python runtime.')
class AeroGuides(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_time_controls_match_original_written_solver_settings(self):
        v=self.v
        prop=v.AddGeom('PROP');v.SetParmValUpdate(prop,'Y_Rel_Location','XForm',8)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);baseline=self.model.read_bytes()
        for mode,automatic,expected in [(v.VSPAERO_PROP_STATIC,0,None),(v.VSPAERO_PROP_UNSTEADY,0,'4'),(v.VSPAERO_PROP_UNSTEADY,1,'-7')]:
            with self.subTest(mode=mode,automatic=automatic):
                settings={'GeomSet':-1,'ThinGeomSet':0,'StopBeforeRun':1,'NCPU':1,'AlphaNpts':1,'MachNpts':1,'PropBladesMode':mode,'AutoTimeStepFlag':automatic,'AutoTimeNumRevs':7,'NumTimeSteps':4,'TimeStepSize':.02,'StartAveragingTimeStep':2,'UnsteadyType':v.STABILITY_P_ANALYSIS}
                data,path=self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=[dict(name=k,values=[x]) for k,x in settings.items()]))
                self.assertEqual(data['executionMode'],'setup-only');self.assertFalse(data['solverExecuted'])
                self.assertFalse(list(path.parent.glob('*.adb')))
                self.assertFalse(list(path.parent.glob('*.history')))
                written={e['name']:e['value'] for e in data['solverSetup']['fields']}
                if expected is None:
                    for key in ('NumberOfTimeSteps','TimeStep','StartAveragingTimeStep'):self.assertNotIn(key,written)
                    self.assertEqual(written['VSP_StabilityType'],str(v.STABILITY_P_ANALYSIS))
                else:
                    self.assertEqual(written['NumberOfTimeSteps'],expected)
                    self.assertEqual(float(written['TimeStep']),-1. if automatic else .02)
                    self.assertEqual(written['StartAveragingTimeStep'],'2')
                spec=native_worker.analysis_schema(v,'VSPAEROSweep')
                fields={e['name']:e for e in spec['inputs']}
                values={n:settings.get(n,e['values'][0]) for n,e in fields.items()}
                def applies(rule):
                    if 'all' in rule:return all(applies(r) for r in rule['all'])
                    if 'any' in rule:return any(applies(r) for r in rule['any'])
                    return values[rule['input']] in rule['values']
                for key in ('NumTimeSteps','TimeStepSize'):
                    self.assertEqual(applies(fields[key]['applicableWhen']),expected is not None and not automatic)
                for key in ('AutoTimeStepFlag','StartAveragingTimeStep'):
                    self.assertEqual(applies(fields[key]['applicableWhen']),expected is not None)
                self.assertEqual(applies(fields['AutoTimeNumRevs']['applicableWhen']),expected is not None and bool(automatic))
                import native_solver_setup
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
                direct=self.path/('direct-'+str(mode)+'-'+str(automatic));direct.mkdir()
                v.SetVSP3FileName(str(direct/'aircraft.vsp3'))
                for analysis,entries in [('VSPAEROComputeGeometry',data['geometryInputs']),('VSPAEROSweep',data['inputs'])]:
                    v.SetAnalysisInputDefaults(analysis)
                    for e in entries:
                        {v.INT_DATA:v.SetIntAnalysisInput,v.DOUBLE_DATA:v.SetDoubleAnalysisInput,v.STRING_DATA:v.SetStringAnalysisInput}[e['type']](analysis,e['name'],e['values'],e['index'])
                    result=v.ExecAnalysis(analysis);native_worker.errors(v)
                    if analysis=='VSPAEROSweep':self.assertFalse(result)
                    else:self.assertTrue(result)
                self.assertEqual(data['solverSetup'],native_solver_setup.read(direct))
                self.assertEqual(self.model.read_bytes(),baseline)

    def test_schema_preserves_every_native_input_value_and_limit(self):
        v=self.v;v.SetAnalysisInputDefaults('VSPAEROSweep')
        before={n:list((v.GetIntAnalysisInput if v.GetAnalysisInputType('VSPAEROSweep',n)==v.INT_DATA else v.GetDoubleAnalysisInput if v.GetAnalysisInputType('VSPAEROSweep',n)==v.DOUBLE_DATA else v.GetStringAnalysisInput)('VSPAEROSweep',n)) for n in v.GetAnalysisInputNames('VSPAEROSweep')}
        spec=native_worker.analysis_schema(v,'VSPAEROSweep');self.assertEqual(before,{e['name']:e['values'] for e in spec['inputs']})
        grouped=[n for g in spec['guide']['sections'] for n in g['inputs']];self.assertEqual(len(grouped),len(set(grouped)));self.assertEqual(set(grouped),set(before))
        for e in spec['inputs']:
            if 'nativeParameter' in e:
                self.assertEqual(e['min'],v.GetParmLowerLimit(e['nativeParameter']));self.assertEqual(e['max'],v.GetParmUpperLimit(e['nativeParameter']))

    def test_invalid_active_solver_settings_preserve_native_aircraft(self):
        source=self.model.read_bytes()
        cases=[dict(NCPU=0),dict(AlphaNpts=0),dict(NoiseCalcFlag=1,NoiseUnits=9),dict(UnsteadyType=999),dict(GroundEffectToggle=1,GroundEffect=-1.),dict(FarDistToggle=1,FarDist=-1.),dict(RefFlag=1,WingID='missing'),dict(UseModeFlag=1,ModeID='missing'),dict(GeomSet=-1,ThinGeomSet=-1)]
        for values in cases:
            with self.subTest(values=values),self.assertRaises(ValueError):
                self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=[dict(name=n,values=[x]) for n,x in values.items()]))
            self.assertEqual(self.model.read_bytes(),source)

    def test_guidance_explains_native_effective_setting_restrictions(self):
        v=self.v;cid=v.FindContainer('VSPAEROSettings',0)
        parms={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
        def setting(name,x):v.SetParmVal(parms[name],x)
        self.assertEqual(v.GetNumUnsteadyRotorGroups(),0)
        setting('m_PropBladesMode',v.VSPAERO_PROP_UNSTEADY);v.Update()
        self.assertEqual(v.GetParmVal(parms['m_PropBladesMode']),v.VSPAERO_PROP_STATIC)
        for name in ('AlphaNpts','BetaNpts','MachNpts','ReCrefNpts'):setting(name,3)
        setting('UnsteadyType',v.STABILITY_DEFAULT)
        setting('GroundEffectToggle',1);setting('GroundEffect',1)
        setting('ManualVrefFlag',0);setting('Vinf',42);setting('Vref',17);v.Update()
        for name in ('AlphaNpts','BetaNpts','MachNpts','ReCrefNpts'):self.assertEqual(v.GetParmVal(parms[name]),1)
        self.assertEqual(v.GetParmVal(parms['UnsteadyType']),v.STABILITY_OFF)
        self.assertEqual(v.GetParmVal(parms['Vref']),42)
        note=native_worker.analysis_schema(v,'VSPAEROSweep')['guide']['note']
        for text in ('no rotating rotor groups','one alpha, beta, Mach and Reynolds condition','turn stability analysis off','freestream airspeed'):self.assertIn(text,note)

    def test_component_only_native_preparation_supports_wing_and_body(self):
        v=self.v;pod=v.AddGeom('POD');v.SetGeomName(pod,'Native body');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);source=self.model.read_bytes()
        for geom in (self.gid,pod):
            with self.subTest(geom=geom):
                data,model=self.worker(dict(action='analysis',name='VSPAEROComputeGeometry',inputs=[dict(name='GeomSet',values=[-1]),dict(name='ThinGeomSet',values=[-1]),dict(name='SingleGeomID',values=[geom])]))
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.SetVSP3FileName(str(self.path/'independent.vsp3'));v.SetAnalysisInputDefaults('VSPAEROComputeGeometry')
                v.SetIntAnalysisInput('VSPAEROComputeGeometry','GeomSet',[-1]);v.SetIntAnalysisInput('VSPAEROComputeGeometry','ThinGeomSet',[-1]);v.SetStringAnalysisInput('VSPAEROComputeGeometry','SingleGeomID',[geom]);rid=v.ExecAnalysis('VSPAEROComputeGeometry');self.assertTrue(rid)
                for r in data['results']:
                    native=v.FindResultsID(r['name'],r['index']);self.assertTrue(native)
                    for e in r['entries']:
                        if e['type'] in (v.INT_DATA,v.DOUBLE_DATA) and e['name']!='Analysis_Duration_Sec':
                            vals=list((v.GetIntResults if e['type']==v.INT_DATA else v.GetDoubleResults)(native,e['name'],e['index']));vals=[None if isinstance(x,float) and not math.isfinite(x) else x for x in vals];self.assertEqual(vals,e['values'],e['name'])
                self.assertEqual(self.model.read_bytes(),source)

    def test_geometry_alignment_and_saved_study_preparation_guide(self):
        import native_aero_guides
        import native_study_worker
        v=self.v;flight=native_worker.analysis_schema(v,'VSPAEROSweep');prep=native_worker.analysis_schema(v,'VSPAEROComputeGeometry')
        selection=[dict(name='GeomSet',values=[0]),dict(name='ThinGeomSet',values=[-1])]
        for side in ('inputs','geometryInputs'):
            aligned=native_aero_guides.align_geometry({side:selection},flight,prep)
            for key in ('inputs','geometryInputs'):
                self.assertEqual({e['name']:e['values'] for e in aligned[key]}, {e['name']:e['values'] for e in selection})
        with self.assertRaisesRegex(ValueError,'same selection'):
            self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=selection,geometryInputs=[dict(name='GeomSet',values=[-1]),dict(name='ThinGeomSet',values=[0])]))
        self.assertFalse(list(self.path.glob('*/aircraft.vspgeom')),'Conflicting selections must fail before native preparation.')
        stage=native_study_worker.stage_schema(v,dict(name='VSPAEROSweep',inputs=[],geometryInputs=[]),native_worker.analysis_schema,native_worker.set_inputs)
        geometry=stage['geometrySchema']
        self.assertEqual(geometry['name'],'VSPAEROComputeGeometry')
        self.assertEqual([g['title'] for g in geometry['guide']['sections']],['Geometry selection','Native mesh preparation'])
        self.assertEqual({e['name'] for e in geometry['inputs']},{n for g in geometry['guide']['sections'] for n in g['inputs']})

    def test_rotor_representation_choices_and_saved_rpm_are_native(self):
        v=self.v;prop=v.AddGeom('PROP');v.SetGeomName(prop,'Native rotor');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,_=self.worker(dict(action='state'))
        self.assertEqual(state['tools']['propModes'],{n:getattr(v,n) for n in ('PROP_BLADES','PROP_BOTH','PROP_DISK')})
        group=next(g for g in state['tools']['rotatingGroups'] if prop in g['components']);rpm=next(p['id'] for p in group['params'] if p['name']=='RPM')
        source=self.model.read_bytes();state,changed=self.worker(dict(action='mutate',operation='parameter',id=rpm,value=1350))
        v.SetParmValUpdate(rpm,1350);expected={v.GetParmName(p):v.GetParmVal(p) for p in v.FindContainerParmIDs(group['id'])}
        actual=next(g for g in state['tools']['rotatingGroups'] if g['id']==group['id'])
        self.assertEqual({p['name']:p['value'] for p in actual['params']},expected)
        reopened,_=self.worker(dict(action='state'),changed)
        self.assertEqual(next(p['value'] for g in reopened['tools']['rotatingGroups'] if g['id']==group['id'] for p in g['params'] if p['name']=='RPM'),1350)
        mode=v.FindParm(prop,'PropMode','Design');state,_=self.worker(dict(action='mutate',operation='parameter',id=mode,value=v.PROP_DISK),changed)
        v.SetParmValUpdate(mode,v.PROP_DISK)
        self.assertEqual(len(state['tools']['rotatingGroups']),v.GetNumUnsteadyGroups());self.assertEqual(len(state['tools']['disks']),v.GetNumActuatorDisks())
        self.assertEqual(self.model.read_bytes(),source)
