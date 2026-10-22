"""Named flowpath choices retain original parameter IDs and native geometry."""
import sys
import unittest
from collections import Counter
import test_native
from vsp_runtime import load
from native_preview import parameter_activity
from native_worker import parameter
import native_engine_controls as controls


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class EngineChoices(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self,kind):
        v=self.v;v.ClearVSPModel();g=v.AddGeom(kind);v.Update()
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        return g

    def test_all_named_choices_indices_and_native_activity_for_both_owners(self):
        v=self.v
        for kind in ('FUSELAGE','STACK'):
            g=self.fixture(kind);state,_=self.worker(dict(action='state'))
            c=state['components'][0];fields={p['name']:p for p in c['params'] if p['rawGroup']=='EngineModel'}
            for name,p in fields.items():
                if p['type']==1:
                    self.assertTrue(p.get('choices'),name)
                    self.assertTrue(all(p['min']<=a['value']<=p['max'] for a in p['choices']))
                    self.assertEqual(len({a['value'] for a in p['choices']}),len(p['choices']))
                    self.assertEqual(v.GetParmVal(p['id']),p['value'])
            self.assertEqual(fields['GeomIOType']['choices'][0]['label'],'No flowpath')
            self.assertEqual(fields['ExtensionDistance']['dimension'],'length')
            group=next(a for a in c['familyControls'] if a['title']=='Inlet & outlet flowpath')
            self.assertEqual(group['parameters'][0],fields['GeomIOType']['id'])
            self.assertEqual(set(group['parameters']),{p['id'] for p in fields.values()})
            activity=parameter_activity(v,[p['id'] for p in fields.values()])
            for p in fields.values():
                if not activity[p['id']]:self.assertFalse(p['active'])

    def test_all_four_component_roles_match_original_saved_parameters_and_surfaces(self):
        v=self.v
        for kind in ('FUSELAGE','STACK'):
            for value,u_basis in [(i,False) for i in range(v.ENGINE_GEOM_IO_NUM_TYPES)]+[(v.ENGINE_GEOM_INLET_OUTLET,True)]:
                with self.subTest(kind=kind,role=value,u_basis=u_basis):
                    g=self.fixture(kind);pid=v.FindParm(g,'GeomIOType','EngineModel')
                    settings=dict(GeomInType=v.ENGINE_GEOM_TO_LIP,GeomOutType=v.ENGINE_GEOM_TO_LIP,
                        InletLipIndex=1,OutletLipIndex=3,InletFaceIndex=2,OutletFaceIndex=2,GeomIOType=value)
                    if u_basis:
                        settings.pop('InletLipIndex');settings.pop('OutletLipIndex')
                        settings.update(InletLipMode=v.ENGINE_LOC_U,OutletLipMode=v.ENGINE_LOC_U,
                            InletLipU=.25,OutletLipU=.75)
                    for name,x in settings.items():v.SetParmVal(g,name,'EngineModel',x)
                    v.Update();v.Update();reference=self.path/'reference.vsp3'
                    v.WriteVSPFile(str(reference),v.SET_ALL)
                    v.ClearVSPModel();v.ReadVSPFile(str(reference));v.Update()
                    expected=Counter((v.GetParmGroupName(p),v.GetParmName(p),v.GetParmVal(p)) for p in v.GetGeomParmIDs(g))
                    grids=[]
                    for i in range(v.GetTotalNumSurfs(g)):
                        u,w=v.GetUWTess01(g,i%v.GetNumMainSurfs(g))
                        grids.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(g,i,[a for a in u for _ in w],[b for _ in u for b in w])])
                    state,path=self.worker(dict(action='mutate',operation='engine-configure',geom=g,settings=settings))
                    c=state['components'][0]
                    self.assertEqual(Counter((p['rawGroup'],p['name'],p['value']) for p in c['params']),expected)
                    self.assertEqual([s['points'] for s in c['surfaces']],grids)
                    cold,_=self.worker(dict(action='state'),path)
                    self.assertEqual(cold['components'][0]['params'],c['params'])

    def test_inactive_flowpath_inputs_stay_guarded(self):
        v=self.v;g=self.fixture('FUSELAGE');before=self.model.read_bytes()
        pid=v.FindParm(g,'GeomInType','EngineModel')
        with self.assertRaises(ValueError):
            self.worker(dict(action='mutate',operation='parameter',id=pid,value=v.ENGINE_GEOM_TO_FACE))
        self.assertEqual(before,self.model.read_bytes())

    def test_same_named_user_parameter_is_not_reinterpreted(self):
        v=self.v;self.fixture('STACK');pid=v.AddUserParm(v.PARM_INT_TYPE,'GeomIOType','EngineModel')
        p=parameter(v,pid)
        self.assertNotIn('choices',p)
        self.assertNotEqual(p.get('label'),'Flowpath component')


    def test_collapsed_default_is_rejected_before_native_update(self):
        v=self.v;g=self.fixture('FUSELAGE');before=self.model.read_bytes()
        for request in [dict(operation='engine-configure',geom=g,settings={'GeomIOType':v.ENGINE_GEOM_INLET_OUTLET}),
                        dict(operation='parameter',id=v.FindParm(g,'GeomIOType','EngineModel'),value=v.ENGINE_GEOM_INLET_OUTLET)]:
            with self.assertRaisesRegex(ValueError,'stations coincide'):self.worker(dict(action='mutate',**request))
            self.assertEqual(self.model.read_bytes(),before)


    def test_invalid_staged_inputs_preserve_aircraft(self):
        v=self.v;g=self.fixture('STACK');before=self.model.read_bytes()
        for settings in ({'BadName':1},{'GeomIOType':float('nan')},{'InletFaceIndex':1.5},
                         {'InletFaceIndex':999},{'InletFaceU':.4},{'InletFaceMode':1,'InletFaceIndex':1}):
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='engine-configure',geom=g,settings=settings))
                self.assertEqual(self.model.read_bytes(),before)

    def test_staged_setup_cannot_change_locked_role(self):
        v=self.v;g=self.fixture('FUSELAGE');pid=v.FindParm(g,'GeomIOType','EngineModel')
        _,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[pid],locked=True))
        before=path.read_bytes()
        settings=dict(GeomIOType=v.ENGINE_GEOM_INLET_OUTLET,GeomInType=v.ENGINE_GEOM_TO_LIP,
            GeomOutType=v.ENGINE_GEOM_TO_LIP,InletLipIndex=1,OutletLipIndex=3)
        with self.assertRaisesRegex(ValueError,'locked'):
            self.worker(dict(action='mutate',operation='engine-configure',geom=g,settings=settings),path)
        self.assertEqual(path.read_bytes(),before)


    def test_existing_collapsed_native_model_stays_readable_without_sampling(self):
        v=self.v;g=self.fixture('FUSELAGE')
        v.SetParmValUpdate(g,'GeomIOType','EngineModel',v.ENGINE_GEOM_INLET_OUTLET)
        v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        state,_=self.worker(dict(action='state'))
        self.assertEqual(state['components'][0]['surfaces'],[])
        self.assertTrue(any('degenerate' in warning for warning in state['warnings']))
        self.assertEqual(self.model.read_bytes(),before)
