"""Profile modifiers must retain complete official native geometry and values."""
import sys
import unittest
import test_native
import test_end_caps as cap_tests
import native_profile_controls
import native_study_worker
import native_worker


@unittest.skipUnless(sys.version_info[:2] == (3, 11), 'Use the matching native Python runtime.')
class ProfileControls(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    compare=cap_tests.EndCaps.compare
    fresh_bor=cap_tests.EndCaps.fresh_bor
    compare_bor=cap_tests.EndCaps.compare_bor
    apply=cap_tests.EndCaps.apply

    def fixture(self,kind):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom(kind);self.kind=kind
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        self.original={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.GetGeomParmIDs(self.gid)}
        return self.model

    def parm(self,name,group=None):
        if self.kind=='BODYOFREVOLUTION':return self.original[(group,name)]
        v=self.v;x=v.GetXSec(v.GetXSecSurf(self.gid,0),1)
        matches=[p for p in v.GetXSecParmIDs(x) if v.GetParmName(p)==name and (group is None or v.GetParmGroupName(p)==group)]
        self.assertEqual(len(matches),1,(name,group))
        return matches[0]

    def step(self,path,name,value,group=None):
        return self.apply(path,self.parm(name,group),value)

    def reopened(self,path):
        state,_=self.worker(dict(action='state'),path)
        if self.kind=='BODYOFREVOLUTION':self.compare_bor(state,self.fresh_bor(path))
        else:self.v.ClearVSPModel();self.v.ReadVSPFile(str(path));self.v.Update();self.compare(state)
        return state

    def test_all_native_closure_methods_and_both_dimension_bases(self):
        for kind in ('WING','PROP','BODYOFREVOLUTION'):
            path=self.fixture(kind);v=self.v
            for edge,modes in [('LE',[1,2,3]),('TE',[1,2,3,4])]:
                for mode in modes:
                    with self.subTest(kind=kind,edge=edge,mode=mode):
                        state,path=self.step(path,edge+'_Close_Type',mode,'Close')
                        state,path=self.step(path,edge+'_Close_Thick',.015+mode*.001,'Close')
                state,path=self.step(path,edge+'_Close_AbsRel',1,'Close')
                state,path=self.step(path,edge+'_Close_Thick_Chord',.02,'Close')
                controls=state['components'][0].get('profileControls') if kind=='BODYOFREVOLUTION' else state['components'][0]['sections'][1]['profileControls']
                pids={p['id']:p for p in state['components'][0]['params']}
                fields=next(c for c in controls['close'] if c['edge']==edge)['fields']
                self.assertTrue(pids[fields['gap']]['displayReadOnly'])
                self.assertFalse(pids[fields['gapFraction']].get('displayReadOnly',False))
                self.assertEqual([c[0] for c in pids[fields['mode']]['choices']],list(range(4 if edge=='LE' else 5)))
            self.reopened(path)

    def test_trim_drivers_plain_flap_and_local_transforms(self):
        for kind in ('WING','PROP','BODYOFREVOLUTION'):
            path=self.fixture(kind);v=self.v
            if kind=='BODYOFREVOLUTION':
                v.ChangeBORXSecShape(self.gid,v.XS_FOUR_SERIES);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                self.original={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.GetGeomParmIDs(self.gid)}
            for edge in ('LE','TE'):
                for mode,name,value in [(1,'X',.025),(2,'Thick',.04)]:
                    state,path=self.step(path,edge+'_Trim_Type',mode,'Trim')
                    state,path=self.step(path,edge+'_Trim_'+name,value,'Trim')
                state,path=self.step(path,edge+'_Trim_AbsRel',1,'Trim')
                state,path=self.step(path,edge+'_Trim_Thick_Chord',.03,'Trim')
            before,_=self.worker(dict(action='state'),path)
            steps=[('TE_Flap_Type',1),('TE_Flap_X_Chord',.25),('TE_Flap_Y_Frc',.4)]
            if kind=='PROP':steps += [('TE_Flap_T',.25),('TE_Flap_DT',.004),('TE_Flap_Flag',1)]
            steps += [('TE_Flap_Deflection',12.),('TE_Trim_AbsRel',0),('TE_Flap_X',.1)]
            for name,value in steps:
                state,path=self.step(path,name,value,'Flap')
            profile=state['components'][0].get('profileControls') if kind=='BODYOFREVOLUTION' else state['components'][0]['sections'][1]['profileControls']
            params={p['id']:p for p in state['components'][0]['params']}
            self.assertEqual(params[profile['flap']['active']]['value'],1,kind)
            self.assertEqual(params[profile['flap']['active']].get('displayReadOnly',False),kind!='PROP')
            self.assertNotEqual(before['components'][0]['surfaces'],state['components'][0]['surfaces'])
            for name,value in [('Theta',7.),('Scale',1.08),('DeltaX',.03),('DeltaY',-.02),('ShiftLE',.08)]:
                state,path=self.step(path,name,value,'XSecCurve')
            self.reopened(path)
        for kind in ('FUSELAGE','STACK'):
            path=self.fixture(kind)
            for name,value in [('Theta',8.),('Scale',1.2),('DeltaX',.04),('DeltaY',-.03),('ShiftLE',.1)]:
                state,path=self.step(path,name,value)
            self.assertFalse(state['components'][0]['sections'][1]['profileControls']['edgeEditing'])
            self.reopened(path)

    def test_calculated_unused_and_invalid_edits_preserve_source(self):
        self.fixture('WING');v=self.v;before=self.model.read_bytes()
        for name,value,group in [('TE_Close_Thick',.02,'Close'),('TE_Close_AbsRel',1,'Close'),
                                 ('LE_Trim_X',.01,'Trim'),('TE_Flap_Deflection',10,'Flap'),
                                 ('TE_Flap_Flag',1,'Flap'),('TE_Flap_T',.3,'Flap'),('TE_Flap_DT',.1,'Flap'),
                                 ('LE_Close_Type',4,'Close'),('TE_Close_Type',1.5,'Close'),
                                 ('TE_Close_Type',True,'Close'),('Theta',181,'XSecCurve'),('Scale',float('nan'),'XSecCurve')]:
            with self.subTest(name=name,value=value),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='parameter',id=self.parm(name,group),value=value))
            self.assertEqual(self.model.read_bytes(),before)
        self.fixture('FUSELAGE')
        for name,group in [('LE_Close_Type','Close'),('TE_Trim_Type','Trim'),('TE_Flap_Type','Flap')]:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='parameter',id=self.parm(name,group),value=1))
        point=v.GetXSec(v.GetXSecSurf(self.gid,0),0)
        with self.assertRaisesRegex(ValueError,'Point profiles'):
            self.worker(dict(action='mutate',operation='parameter',id=v.GetXSecParm(point,'Theta'),value=10.))

    def test_prepared_studies_order_method_basis_and_values_and_share_locks(self):
        self.fixture('WING');v=self.v
        mode=self.parm('TE_Trim_Type');basis=self.parm('TE_Trim_AbsRel','Trim');distance=self.parm('TE_Trim_X_Chord')
        schema=native_study_worker.schema(v,native_worker.parameter)
        self.assertFalse(next(p for p in schema['parameters'] if p['id']==distance)['editable'])
        result=native_study_worker.prepare(v,dict(parameters=[dict(id=distance,value=.03),dict(id=basis,value=1),dict(id=mode,value=1)]),self.path/'case.vsp3',native_worker.errors)
        self.assertEqual(result['parameters'][0]['effective'],.03)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        v.SetParmValUpdate(mode,1);v.SetParmValUpdate(basis,1);v.SetParmValUpdate(distance,.03);v.Update()
        expected={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)}
        v.ClearVSPModel();v.ReadVSPFile(str(self.path/'case.vsp3'));v.Update()
        self.assertEqual({p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)},expected)
        schema=native_study_worker.schema(v,native_worker.parameter)
        self.assertTrue(next(p for p in schema['parameters'] if p['id']==distance).get('editable',True))
        for pid in (self.parm('TE_Trim_X'),self.parm('TE_Trim_Thick'),self.parm('TE_Flap_T')):
            with self.assertRaises(ValueError):native_study_worker.prepare(v,dict(parameters=[dict(id=pid,value=.01)]),self.path/'invalid.vsp3',native_worker.errors)

    def test_blade_flap_setup_guards_and_coupled_study_order(self):
        path=self.fixture('PROP');v=self.v
        state,path=self.step(path,'TE_Flap_Type',1,'Flap')
        before=path.read_bytes()
        for name,value in [('TE_Flap_Deflection',12),('TE_Flap_T',1),('TE_Flap_DT',.9)]:
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='parameter',id=self.parm(name,'Flap'),value=value),path)
            self.assertEqual(path.read_bytes(),before)
        # A saved case may supply controllers last. The engine must see a
        # valid transition and enabled geometry before nonzero deflection.
        settings=[('TE_Flap_Deflection',12),('TE_Flap_Flag',1),('TE_Flap_DT',.004),('TE_Flap_T',.25)]
        changes=[dict(id=self.parm(name,'Flap'),value=value) for name,value in settings]
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        native_study_worker.prepare(v,dict(parameters=changes),self.path/'blade-case.vsp3',native_worker.errors)
        state,_=self.worker(dict(action='state'),self.path/'blade-case.vsp3')
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        for name,value in reversed(settings):v.SetParmValUpdate(self.parm(name,'Flap'),value)
        self.compare(state)
        path=self.path/'blade-case.vsp3';before=path.read_bytes()
        for name,value in [('TE_Flap_DT',0),('TE_Flap_T',.998)]:
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='parameter',id=self.parm(name,'Flap'),value=value),path)
            self.assertEqual(path.read_bytes(),before)

    def test_circular_bor_flap_is_protected_before_native_evaluation(self):
        self.fixture('BODYOFREVOLUTION');before=self.model.read_bytes()
        state,_=self.worker(dict(action='state'))
        fields=state['components'][0]['profileControls']['flap']
        params={p['id']:p for p in state['components'][0]['params']}
        self.assertTrue(all(params[p]['displayReadOnly'] for p in fields.values()))
        with self.assertRaisesRegex(ValueError,'airfoil profile'):
            self.worker(dict(action='mutate',operation='parameter',id=fields['mode'],value=1))
        self.assertEqual(self.model.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'airfoil profile'):
            native_study_worker.prepare(self.v,dict(parameters=[dict(id=fields['mode'],value=1)]),self.path/'unsafe.vsp3',native_worker.errors)
