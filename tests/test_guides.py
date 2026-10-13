"""Guided analyses use exact native operations and saved result geometry."""
import json
import sys
import unittest
import test_native
import native_worker
import native_guides
from vsp_runtime import load


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeGuides(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;self.pod=v.AddGeom('POD');v.SetGeomName(self.pod,'Body')
        v.SetParmValUpdate(v.FindParm(self.pod,'X_Rel_Location','XForm'),3.)
        v.SetSetName(3,'Wing only');v.SetSetFlag(self.gid,3,True)
        v.SetSetName(4,'Body only');v.SetSetFlag(self.pod,4,True)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def direct(self,name,values,model=None):
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(model or self.model));v.Update();v.SetVSP3FileName(str(self.path/'direct.vsp3'));v.SetAnalysisInputDefaults(name)
        setters={v.INT_DATA:v.SetIntAnalysisInput,v.DOUBLE_DATA:v.SetDoubleAnalysisInput,v.STRING_DATA:v.SetStringAnalysisInput,v.VEC3D_DATA:v.SetVec3dAnalysisInput}
        for key,items in values.items():
            typ=v.GetAnalysisInputType(name,key)
            if typ==v.VEC3D_DATA:items=[v.vec3d(*p) for p in items]
            setters[typ](name,key,items)
        if name=='ParasiteDrag':v.SetStringAnalysisInput(name,'FileName',[str(self.path/'direct-parasite.csv')])
        rid=v.ExecAnalysis(name);native_worker.errors(v);self.assertTrue(rid)
        return native_worker.collect_results(v)

    def assertNative(self,expected,actual):
        rows={(r['name'],r['index']):r for r in actual}
        for r in expected:
            self.assertIn((r['name'],r['index']),rows)
            entries={(e['name'],e['index']):e for e in rows[r['name'],r['index']]['entries']}
            for e in r['entries']:
                if e['name'] in ('Analysis_Duration_Sec','Mesh_GeomID'):continue
                self.assertIn((e['name'],e['index']),entries);got=entries[e['name'],e['index']]
                self.assertEqual(got['type'],e['type']);self.assertEqual(got['values'],e['values'],msg=e['name'])

    def runCase(self,name,values,model=None):
        expected=self.direct(name,values,model)
        request=dict(action='analysis',name=name,inputs=[dict(name=n,index=0,values=x) for n,x in values.items()])
        data,path=self.worker(request,model);self.assertNative(expected,data['results'])
        self.assertEqual(path.read_bytes(),(model or self.model).read_bytes())
        return data,path

    def test_all_guided_calculations_equal_direct_native_and_preserve_aircraft(self):
        self.fixture()
        for name in sorted(native_guides.NAMES):
            with self.subTest(name=name):
                inputs={};baseline=self.model.read_bytes()
                if name=='BladeElement':
                    prop=self.v.AddGeom('PROP');self.v.Update();self.v.WriteVSPFile(str(self.model),self.v.SET_ALL);inputs={'PropID':[prop]}
                data,path=self.runCase(name,inputs)
                if name=='BladeElement':self.model.write_bytes(baseline)
                if name in ('MassProp','PlanarSlice','Projection'):
                    self.assertTrue(data['guideFile']);geometry=json.loads((path.parent/data['guideFile']).read_text())
                    self.assertTrue(geometry['nodes']);self.assertTrue(geometry['elements'])
                    self.assertEqual(len({e['id'] for e in geometry['elements']}),len(geometry['elements']))
                    self.assertEqual(geometry,native_guides.preview(data['results'],name))
                if name=='ParasiteDrag':
                    filename=next(e['values'][0] for e in data['inputs'] if e['name']=='FileName')
                    self.assertEqual(__import__('pathlib').Path(filename).parent.resolve(),path.parent.resolve());self.assertGreater(__import__('pathlib').Path(filename).stat().st_size,200)

    def test_oblique_manual_slices_and_transverse_degenerate_mass_match_native(self):
        self.fixture();v=self.v
        data,path=self.runCase('PlanarSlice',dict(Norm=[[.3,1.,0.]],NumSlices=[9],AutoBoundFlag=[0],StartVal=[-4.],EndVal=[4.]))
        r=next(r for r in data['results'] if r['name']=='Slice');centers=next(e['values'] for e in r['entries'] if e['name']=='Slice_Area_Center')
        self.assertEqual(json.loads((path.parent/data['guideFile']).read_text())['nodes'],centers)
        self.runCase('MassProp',dict(Set=[-1],DegenSet=[3],NumMassSlices=[30],MassSliceDir=[v.Y_DIR]))

    def test_eminton_lord_distributions_equal_native_and_invalid_samples_are_safe(self):
        for x,area in [([0,1,2],[0,1,0]),([0,.2,.7,1.5,3],[0,.4,1.2,.5,0]),([2,3,5,8],[.2,1,.7,.1])]:
            self.runCase('EmintonLord',dict(X_vec=x,Area_vec=area))
        schema=native_worker.analysis_schema(self.v,'EmintonLord')
        self.assertEqual(schema['guide']['sections'][0]['inputs'],['X_vec','Area_vec'])
        baseline=self.model.read_bytes()
        for x,area in [([],[]),([0,1],[0,1]),([0,1,2],[0,1]),([0,0,2],[0,1,0]),([2,1,0],[0,1,0]),([0,1,2],[0,-1,0])]:
            with self.subTest(x=x,area=area),self.assertRaises(ValueError):
                self.worker(dict(action='analysis',name='EmintonLord',inputs=[dict(name='X_vec',values=x),dict(name='Area_vec',values=area)]))
            self.assertEqual(self.model.read_bytes(),baseline)

    def test_projection_targets_boundaries_modes_and_custom_vectors_equal_native_paths(self):
        self.fixture();v=self.v;mode=v.CreateAndAddMode('Wing projection',3,-1);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        cases=[dict(TargetType=[v.GEOM_TARGET],TargetGeomID=[self.gid],DirectionType=[v.VEC_PROJ],Direction=[[1.,.4,.2]],TargetHullFlag=[1]),
               dict(TargetType=[v.SET_TARGET],TargetSet=[0],DirectionType=[v.Z_PROJ],BoundaryType=[v.GEOM_BOUNDARY],BoundaryGeomID=[self.pod]),
               dict(TargetType=[v.MODE_TARGET],TargetModeID=[mode],DirectionType=[v.Z_PROJ],BoundaryType=[v.SET_BOUNDARY],BoundarySet=[4],BoundaryHullFlag=[1])]
        for inputs in cases:
            with self.subTest(inputs=inputs):
                data,path=self.runCase('Projection',inputs)
                paths=[e['values'] for r in data['results'] if r['name']=='Projection' for e in r['entries'] if e['name']=='Path']
                if paths:
                    geometry=json.loads((path.parent/data['guideFile']).read_text());self.assertEqual(geometry['nodes'],[p for path in paths for p in path])
                    self.assertEqual(geometry['totalElements'],sum(max(0,len(path)-1) for path in paths))

    def test_wave_reference_edits_use_native_wing_area_and_persist(self):
        self.fixture();v=self.v;area=v.GetParmVal(v.FindParm(self.gid,'TotalArea','WingGeom'))
        state,path=self.worker(dict(action='mutate',operation='analysis-reference',analysis='WaveDrag',wing=self.gid))
        settings=next(c for c in state['tools']['globalSettings'] if c['name']=='WaveDragSettings')
        self.assertEqual(next(p['value'] for p in settings['params'] if p['name']=='Sref'),area)
        self.assertEqual(next(p['value'] for p in settings['params'] if p['name']=='RefFlag'),0)
        data,out=self.runCase('WaveDrag',dict(Mach=[1.8],NumSlices=[31],NumRotSects=[11]),path)
        self.assertEqual(data['guideSettings']['Sref'],area)
        state,path=self.worker(dict(action='mutate',operation='analysis-reference',analysis='WaveDrag',value=120.),path)
        data,out=self.runCase('WaveDrag',dict(Mach=[1.8],NumSlices=[31],NumRotSects=[11]),path);self.assertEqual(data['guideSettings']['Sref'],120.)

    def test_parasite_metric_and_manual_freestream_choices_equal_native_and_isolate_csv(self):
        self.fixture();v=self.v
        for inputs in [dict(LengthUnit=[v.LEN_M],VelocityUnit=[v.V_UNIT_M_S],AltLengthUnit=[v.PD_UNITS_METRIC],TempUnit=[v.TEMP_UNIT_K],PresUnit=[v.PRES_UNIT_PA],Altitude=[1500.],Vinf=[80.],Sref=[30.]),
                       dict(FreestreamPropChoice=[v.ATMOS_TYPE_MANUAL_RE_L],Re_L=[2000000.],Mach=[.4],LamCfEqnChoice=[v.CF_LAM_BLASIUS_W_HEAT],TurbCfEqnChoice=[v.CF_TURB_EXPLICIT_FIT_SPALDING])]:
            with self.subTest(inputs=inputs):self.runCase('ParasiteDrag',inputs)
        data,path=self.runCase('ParasiteDrag',dict(FileName=['../../outside-guide.csv']))
        self.assertTrue((path.parent/'outside-guide.csv').is_file());self.assertFalse((self.path.parent/'outside-guide.csv').exists())
        filename=next(e['values'][0] for e in data['inputs'] if e['name']=='FileName');self.assertEqual(filename,str((path.parent/'outside-guide.csv').resolve()))

    def test_invalid_guided_inputs_fail_before_calculation(self):
        self.fixture();v=self.v
        cases=[('PlanarSlice',dict(Norm=[[0,0,0]])),('PlanarSlice',dict(Norm=[[True,0,0]])),('PlanarSlice',dict(AutoBoundFlag=[0],StartVal=[2.],EndVal=[1.])),
               ('MassProp',dict(Set=[-1],DegenSet=[-1])),('MassProp',dict(NumMassSlices=[0])),('Projection',dict(TargetType=[v.GEOM_TARGET],TargetGeomID=['missing'])),
               ('Projection',dict(DirectionType=[v.VEC_PROJ],Direction=[[0,0,0]])),('Projection',dict(BoundaryType=[v.GEOM_BOUNDARY],BoundaryGeomID=[''])),
               ('WaveDrag',dict(Mach=[1.])),('WaveDrag',dict(NumRotSects=[0])),('WaveDrag',dict(SSFlow_vec=['missing'])),
               ('ParasiteDrag',dict(RefFlag=[1],WingID=[''])),('ParasiteDrag',dict(Sref=[0.])),('ParasiteDrag',dict(FreestreamPropChoice=[v.ATMOS_TYPE_MANUAL_RE_L],Re_L=[0.]))]
        for name,inputs in cases:
            with self.subTest(name=name,inputs=inputs),self.assertRaises(ValueError):self.worker(dict(action='analysis',name=name,inputs=[dict(name=n,values=x) for n,x in inputs.items()]))

    def test_native_guided_schema_retains_all_inputs_and_exposes_native_choices_and_mass_settings(self):
        self.fixture();v=self.v
        for name in native_guides.NAMES:
            spec,path=self.worker(dict(action='schema',name=name));self.assertEqual({e['name'] for e in spec['inputs']},set(v.GetAnalysisInputNames(name)))
            self.assertTrue(spec['guide']['sections']);self.assertTrue(all(e.get('label') for e in spec['inputs']))
            if name=='MassProp':self.assertTrue(any(p['name']=='Density' for c in spec['guide']['massComponents'] for p in c['settings']))
            if name=='Projection':self.assertEqual(next(e for e in spec['inputs'] if e['name']=='TargetType')['choices'][1]['value'],v.GEOM_TARGET)

    def test_parasite_atmosphere_dependencies_match_native_parameter_activity(self):
        import native_preview
        self.fixture();v=self.v
        mapping={'Altitude':'Alt','DeltaTemp':'DeltaTemp','Vinf':'Vinf','Temperature':'Temp','Pressure':'Pres','Density':'Density','Mach':'Mach','Re_L':'Re_L','SpecificHeatRatio':'SpecificHeatRatio'}
        schema=native_worker.analysis_schema(v,'ParasiteDrag');fields={e['name']:e for e in schema['inputs']}
        methods=[v.ATMOS_TYPE_US_STANDARD_1976,v.ATMOS_TYPE_HERRINGTON_1966,v.ATMOS_TYPE_MANUAL_P_R,v.ATMOS_TYPE_MANUAL_P_T,v.ATMOS_TYPE_MANUAL_R_T,v.ATMOS_TYPE_MANUAL_RE_L]
        friction=[v.CF_TURB_EXPLICIT_FIT_SPALDING,v.CF_TURB_ROUGHNESS_SCHLICHTING_AVG_FLOW_CORRECTION,v.CF_TURB_HEATTRANSFER_WHITE_CHRISTOPH]
        for atmosphere in methods:
            for method in friction:
                with self.subTest(atmosphere=atmosphere,friction=method):
                    self.direct('ParasiteDrag',dict(FreestreamPropChoice=[atmosphere],TurbCfEqnChoice=[method],Re_L=[2000000.],Mach=[.4]))
                    cid=v.FindContainer('ParasiteDragSettings',0);ids={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
                    activity=native_preview.parameter_activity(v,[ids[n] for n in mapping.values()])
                    settings={'FreestreamPropChoice':atmosphere,'TurbCfEqnChoice':method}
                    for key,pname in mapping.items():
                        rule=fields[key]['applicableWhen'];visible=any(settings[r['input']] in r['values'] for r in rule.get('any',[rule]))
                        self.assertEqual(visible,activity[ids[pname]],key)

if __name__=='__main__':unittest.main()
