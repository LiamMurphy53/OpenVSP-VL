"""Native wing driver usability and dependency fidelity, including study guards."""
import itertools
import sys
import unittest
import test_native
import native_preview
import native_study_worker
import native_worker


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class WingControls(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_catalogue_matches_every_sdk_driver_combination(self):
        v=self.v;actual=[]
        for choices in itertools.combinations(range(v.NUM_WSECT_DRIVER),3):
            v.SetDriverGroup(self.gid,1,v.SPAN_WSECT_DRIVER,v.ROOTC_WSECT_DRIVER,v.TIPC_WSECT_DRIVER)
            native_worker.errors(v)
            v.SetDriverGroup(self.gid,1,*choices)
            manager=v.ErrorMgrSingleton.getInstance();errors=[]
            while manager.GetNumTotalErrors():errors.append(manager.PopLastError().m_ErrorString)
            if not errors and list(v.GetDriverGroup(self.gid,1))==list(choices):actual.append(list(choices))
        self.assertEqual(native_preview.wing_driver_combinations(v),actual)
        self.assertEqual(len(actual),39)

    def assert_geometry_matches(self,state):
        v=self.v;c=state['components'][0]
        expected={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)}
        for p in c['params']:self.assertAlmostEqual(p['value'],expected[p['id']],places=10,msg=p['name'])
        for surface in c['surfaces']:
            u,w=v.GetUWTess01(self.gid,0)
            points=v.CompVecPnt01(self.gid,surface['index'],[a for a in u for _ in w],[b for _ in u for b in w])
            self.assertEqual(len(surface['points']),len(points))
            for actual,p in zip(surface['points'],points):
                for a,b in zip(actual,[p.x(),p.y(),p.z()]):self.assertAlmostEqual(a,b,places=10)

    def test_driver_edits_persistence_and_every_native_parameter_surface(self):
        v=self.v;source=self.model.read_bytes()
        for choices,value in [([1,5,6],9.),([0,5,6],7.),([1,2,3],8.),([1,5,7],7.)]:
            with self.subTest(choices=choices):
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
                state,saved=self.worker(dict(action='mutate',operation='drivers',geom=self.gid,index=1,surface=0,drivers=choices))
                section=state['components'][0]['sections'][1]
                self.assertEqual(section['drivers'],choices)
                names=['Aspect','Span','Area','Taper','Avg_Chord','Root_Chord','Tip_Chord','Sec_Sweep','Sweep','Sweep_Location','Sec_Sweep_Location']
                independent=[v.FindParm(self.gid,name,'XSec_1') for name in names]
                self.assertEqual(section['driverParameterIDs'],independent)
                params={p['id']:p for p in state['components'][0]['params']}
                self.assertEqual({d['value'] for d in section['driverControls'] if not params[d['parameter']]['displayReadOnly']},set(choices))
                pid=independent[choices[0]]
                state,edited=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),saved)
                v.SetDriverGroup(self.gid,1,*choices);v.Update();v.SetParmValUpdate(pid,value);v.Update()
                self.assert_geometry_matches(state)
                reopened,_=self.worker(dict(action='state'),edited)
                self.assertEqual(reopened['components'][0]['sections'][1]['drivers'],choices)
                self.assert_geometry_matches(reopened)
        self.assertEqual(self.model.read_bytes(),source)

    def test_invalid_and_calculated_edits_are_atomic(self):
        v=self.v;before=self.model.read_bytes()
        for choices,index in [([0,1,2],1),([1,1,5],1),([True,5,6],1),(['1',5,6],1),([1,5],1),([1,5,8],1),([1,5,6],0)]:
            with self.subTest(choices=choices,index=index),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='drivers',geom=self.gid,index=index,drivers=choices))
        for name,group in [('Aspect','XSec_1'),('Area','XSec_1'),('Avg_Chord','XSec_1'),('Span','XSec_0'),('ProjectedSpan','XSec_1'),('TotalAR','WingGeom')]:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'calculates|follows'):
                self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(self.gid,name,group),value=2.))
        self.assertEqual(self.model.read_bytes(),before)

    def test_study_schema_save_and_prepare_guard_calculated_dimensions(self):
        v=self.v;spec=native_study_worker.schema(v,native_worker.parameter);params={p['id']:p for p in spec['parameters']}
        span=v.FindParm(self.gid,'Span','XSec_1');area=v.FindParm(self.gid,'Area','XSec_1')
        self.assertIs(params[area]['editable'],False);self.assertTrue(params[span].get('editable',True))
        req=dict(stages=[dict(name='CompGeom',inputs=[])],axes=[dict(kind='parameter',id=area,values=[3.])])
        with self.assertRaisesRegex(ValueError,'driver'):
            native_study_worker.validate(v,req,native_worker.parameter,native_worker.analysis_schema,native_worker.set_inputs)
        before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'drivers'):
            native_study_worker.prepare(v,dict(parameters=[dict(id=area,value=3.)]),self.model,native_worker.errors)
        self.assertEqual(self.model.read_bytes(),before)
        native_study_worker.prepare(v,dict(parameters=[dict(id=span,value=9.)]),self.path/'case.vsp3',native_worker.errors)
        self.assertEqual(v.GetParmVal(span),9.)
