"""Cap workflows are compared with independent, unmodified native SDK edits."""
import sys
import json
import subprocess
import unittest
import test_native
import native_end_caps
import native_study_worker
import native_worker
from native_preview import parameter_activity


@unittest.skipUnless(sys.version_info[:2] == (3, 11), 'Use the matching native Python runtime.')
class EndCaps(unittest.TestCase):
    setUpClass = classmethod(lambda cls: setattr(cls, 'v', test_native.load()))
    setUp = test_native.NativeIntegration.setUp
    tearDown = test_native.NativeIntegration.tearDown
    worker = test_native.NativeIntegration.worker

    def fixture(self, kind):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom(kind);self.kind=kind
        if kind in ('FUSELAGE','STACK'):
            surf=v.GetXSecSurf(self.gid,0)
            # Point ends already close a body; use genuinely open sections.
            for i in (0,v.GetNumXSec(surf)-1):
                v.ChangeXSecShape(surf,i,v.XS_ELLIPSE)
                v.SetXSecWidthHeight(v.GetXSec(surf,i),2.,1.5)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        self.original={ (v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.GetGeomParmIDs(self.gid)}
        return self.model

    def fresh_bor(self,path,pid='',value=None):
        # BORGeom's official destructor leaves its profile container alive.
        # Reloading BOR repeatedly in one process remaps the leaked IDs. Use
        # the same fresh-process lifecycle as Studio, preserving exact IDs.
        script='''import json,sys
from vsp_runtime import load
v=load();v.ReadVSPFile(sys.argv[1]);v.Update();g=sys.argv[2]
original={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.GetGeomParmIDs(g)}
target=(v.GetParmGroupName(sys.argv[3]),v.GetParmName(sys.argv[3])) if sys.argv[3] else None
# Reconstruct native default circles so the independent SDK oracle has the
# correct parent; the installed DecodeXml path retains an obsolete ID.
if v.GetBORXSecShape(g)==v.XS_CIRCLE:
 v.ChangeBORXSecShape(g,v.XS_ELLIPSE)
 v.ChangeBORXSecShape(g,v.XS_CIRCLE)
ids={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.GetGeomParmIDs(g)}
assert set(original)==set(ids)
if target:v.SetParmValUpdate(ids[target],json.loads(sys.argv[4]));v.Update()
xyz=lambda p:[p.x(),p.y(),p.z()]
surfaces=[]
for i in range(v.GetTotalNumSurfs(g)):
 u,w=v.GetUWTess01(g,i%v.GetNumMainSurfs(g))
 surfaces.append(dict(index=i,rows=len(u),cols=len(w),points=[xyz(p) for p in v.CompVecPnt01(g,i,[a for a in u for _ in w],[b for _ in u for b in w])]))
print(json.dumps(dict(params={original[key]:v.GetParmVal(p) for key,p in ids.items()},surfaces=surfaces,profile=[xyz(v.ComputeBORXSecPnt(g,i/100)) for i in range(101)])))'''
        from vsp_runtime import interpreter
        output=subprocess.run([interpreter(),'-c',script,str(path),self.gid,pid,json.dumps(value)],cwd=test_native.ROOT,capture_output=True,text=True,check=True,timeout=20)
        return json.loads(output.stdout)

    def compare_bor(self,state,expected):
        c=state['components'][0]
        self.assertEqual({p['id']:p['value'] for p in c['params']},expected['params'])
        self.assertEqual(c['surfaces'],expected['surfaces'])
        self.assertEqual(state['tools']['bodiesOfRevolution'][0]['profile'],expected['profile'])

    def compare(self,state):
        v=self.v;c=state['components'][0]
        self.assertEqual({p['id']:p['value'] for p in c['params']},
                         {p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)})
        for s in c['surfaces']:
            u,w=v.GetUWTess01(self.gid,s['index']%v.GetNumMainSurfs(self.gid))
            pts=v.CompVecPnt01(self.gid,s['index'],[a for a in u for _ in w],[b for _ in u for b in w])
            self.assertEqual(s['points'],[[p.x(),p.y(),p.z()] for p in pts])
        for section in c['sections']:
            x=v.GetXSec(v.GetXSecSurf(self.gid,section['surface']),section['index'])
            pts=[v.ComputeXSecPnt(x,i/100) for i in range(101)]
            self.assertEqual(section['profile'],[[p.x(),p.y(),p.z()] for p in pts])

    def apply(self,path,pid,value):
        if self.kind=='BODYOFREVOLUTION':
            expected=self.fresh_bor(path,pid,value)
            state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
            self.compare_bor(state,expected)
            return state,saved
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        v.SetParmValUpdate(pid,value);v.Update();native_worker.errors(v)
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
        self.compare(state)
        return state,saved

    def test_all_surface_cap_modes_match_native_and_both_ends_shape_and_reopen(self):
        v=self.v
        for kind in ('WING','FUSELAGE','STACK','PROP','BODYOFREVOLUTION'):
            modes=[v.NO_END_CAP,v.FLAT_END_CAP,v.ROUND_END_CAP,v.EDGE_END_CAP,v.SHARP_END_CAP,v.POINT_END_CAP]
            if kind in ('WING','PROP'):modes += [v.ROUND_EXT_END_CAP_NONE,v.ROUND_EXT_END_CAP_LE,v.ROUND_EXT_END_CAP_TE,v.ROUND_EXT_END_CAP_BOTH]
            path=self.fixture(kind);pid=v.FindParm(self.gid,'CapUMaxOption','EndCap');shapes=[]
            for mode in modes:
                with self.subTest(kind=kind,mode=mode):
                    state,path=self.apply(path,pid,mode)
                    c=state['components'][0];shapes.append(c['surfaces'])
                    fields=c['endCaps']['ends'][1]['fields'];params={p['id']:p for p in c['params']}
                    self.assertEqual([choice[0] for choice in params[fields['mode']]['choices']],modes)
                    self.assertEqual(params[fields['strength']].get('displayReadOnly',False),mode!=v.SHARP_END_CAP)
                    self.assertEqual(params[fields['length']].get('displayReadOnly',False),mode in (0,1,5))
                    self.assertEqual({p:params[p]['active'] for p in fields.values()},parameter_activity(v,fields.values()))
            self.assertNotEqual(shapes[0],shapes[2],kind)
            for prefix in ('CapUMin','CapUMax'):
                for suffix,value in [('Option',v.SHARP_END_CAP),('Length',1.7),('Offset',.18),('Strength',.65),('SweepFlag',1)]:
                    with self.subTest(kind=kind,end=prefix,field=suffix):
                        state,path=self.apply(path,v.FindParm(self.gid,prefix+suffix,'EndCap'),value)
            state,path=self.apply(path,v.FindParm(self.gid,'CapUMinTess','EndCap'),7)
            reopened,_=self.worker(dict(action='state'),path)
            if kind=='BODYOFREVOLUTION':self.compare_bor(reopened,self.fresh_bor(path))
            else:v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.compare(reopened)

    def test_native_profile_edges_both_sides_and_all_four_modes(self):
        v=self.v
        for kind in ('WING','PROP','BODYOFREVOLUTION'):
            path=self.fixture(kind)
            def parm(name):
                return self.original[('Cap',name)] if kind=='BODYOFREVOLUTION' else v.GetXSecParm(v.GetXSec(v.GetXSecSurf(self.gid,0),1),name)
            for prefix in ('LE','TE'):
                for mode in (v.FLAT_END_CAP,v.ROUND_END_CAP,v.EDGE_END_CAP,v.SHARP_END_CAP):
                    with self.subTest(kind=kind,edge=prefix,mode=mode):state,path=self.apply(path,parm(prefix+'_Cap_Type'),mode)
                for suffix,value in [('Length',.7),('Offset',.2),('Strength',.6)]:
                    state,path=self.apply(path,parm(prefix+'_Cap_'+suffix),value)
            reopened,_=self.worker(dict(action='state'),path)
            if kind=='BODYOFREVOLUTION':self.compare_bor(reopened,self.fresh_bor(path))
            else:v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.compare(reopened)

    def test_native_point_caps_both_ends_complete_geometry_and_saved_study_guards(self):
        v=self.v
        for kind in ('WING','FUSELAGE','STACK','PROP','BODYOFREVOLUTION','POD'):
            with self.subTest(kind=kind):
                path=self.fixture(kind)
                for prefix,position in [('CapUMin',0.),('CapUMax',1.)]:
                    pid=v.FindParm(self.gid,prefix+'Option','EndCap')
                    state,path=self.apply(path,pid,v.POINT_END_CAP)
                    cap=state['components'][0]['endCaps']['ends'][int(position)]
                    self.assertIn('native cap point',cap['hint'])
                    params={p['id']:p for p in state['components'][0]['params']}
                    for key in ('length','offset','strength','sweep'):
                        self.assertTrue(params[cap['fields'][key]]['displayReadOnly'])
                    # Full independent geometry equality is asserted by apply.
                    # Explicitly inspect every physical copy's native endpoint
                    # to prove the Point result rather than only the enum value.
                    for surface in state['components'][0]['surfaces']:
                        boundary=surface['points'][:surface['cols']] if position==0 else surface['points'][-surface['cols']:]
                        for point in boundary:
                            for actual,expected in zip(point,boundary[0]):self.assertLessEqual(abs(actual-expected),1e-14)
                reopened,_=self.worker(dict(action='state'),path)
                if kind=='BODYOFREVOLUTION':self.compare_bor(reopened,self.fresh_bor(path))
                else:v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.compare(reopened)
                # Preparation must allow the actual native Point mode, while
                # rejecting a coupled request to change its unused factors.
                if kind!='BODYOFREVOLUTION':
                    option=v.FindParm(self.gid,'CapUMaxOption','EndCap');length=v.FindParm(self.gid,'CapUMaxLength','EndCap')
                    before=path.read_bytes();spec=native_study_worker.schema(v,native_worker.parameter)
                    self.assertTrue(next(p for p in spec['parameters'] if p['id']==option).get('editable',True))
                    self.assertFalse(next(p for p in spec['parameters'] if p['id']==length)['editable'])
                    native_study_worker.prepare(v,dict(parameters=[dict(id=option,value=v.POINT_END_CAP)]),self.path/'point-case.vsp3',native_worker.errors)
                    with self.assertRaisesRegex(ValueError,'Unused for this cap shape'):
                        native_study_worker.prepare(v,dict(parameters=[dict(id=length,value=2),dict(id=option,value=v.POINT_END_CAP)]),self.path/'unused-point-case.vsp3',native_worker.errors)
                    self.assertEqual(path.read_bytes(),before)

    def test_unused_modes_invalid_values_and_dormant_geometry_are_atomic(self):
        v=self.v;self.fixture('WING');before=self.model.read_bytes()
        for name,value in [('CapUMaxLength',2),('CapUMaxStrength',.2),('CapUMaxSweepFlag',1),
                           ('CapUMaxOption',1.5),('CapUMaxOption',10),('CapUMaxOption',True),
                           ('CapUMinTess',3.5),('CapUMinTess',52),('CapUMinTess',float('nan'))]:
            with self.subTest(name=name,value=value),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(self.gid,name,'EndCap'),value=value))
            self.assertEqual(self.model.read_bytes(),before)
        x=v.GetXSec(v.GetXSecSurf(self.gid,0),1)
        for value in (v.POINT_END_CAP,v.ROUND_EXT_END_CAP_LE):
            with self.assertRaisesRegex(ValueError,'Profile edges support'):
                self.worker(dict(action='mutate',operation='parameter',id=v.GetXSecParm(x,'LE_Cap_Type'),value=value))
        self.fixture('FUSELAGE')
        before=self.model.read_bytes()
        for value in (v.ROUND_EXT_END_CAP_NONE,v.ROUND_EXT_END_CAP_BOTH):
            with self.assertRaisesRegex(ValueError,'supported cap shape'):
                self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(self.gid,'CapUMaxOption','EndCap'),value=value))
            self.assertEqual(self.model.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'Profile edge caps apply'):
            self.worker(dict(action='mutate',operation='parameter',id=v.GetXSecParm(v.GetXSec(v.GetXSecSurf(self.gid,0),1),'LE_Cap_Type'),value=2))
        self.fixture('BLANK')
        with self.assertRaisesRegex(ValueError,'no native parametric surfaces'):
            self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(self.gid,'CapUMinOption','EndCap'),value=2))

    def test_studies_share_eligibility_and_apply_cap_modes_before_values(self):
        v=self.v;self.fixture('WING')
        option=v.FindParm(self.gid,'CapUMaxOption','EndCap');length=v.FindParm(self.gid,'CapUMaxLength','EndCap')
        spec=native_study_worker.schema(v,native_worker.parameter)
        self.assertFalse(next(p for p in spec['parameters'] if p['id']==length)['editable'])
        with self.assertRaises(ValueError):native_study_worker.prepare(v,dict(parameters=[dict(id=length,value=2.)]),self.path/'unused.vsp3',native_worker.errors)
        # A coupled prepared case must apply the cap controller first even
        # when axes arrive in the opposite order.
        result=native_study_worker.prepare(v,dict(parameters=[dict(id=length,value=1.8),dict(id=option,value=4)]),self.path/'case.vsp3',native_worker.errors)
        self.assertEqual(result['parameters'][0]['effective'],1.8)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        v.SetParmValUpdate(option,4);v.SetParmValUpdate(length,1.8);v.Update()
        expected={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)}
        v.ClearVSPModel();v.ReadVSPFile(str(self.path/'case.vsp3'));v.Update()
        self.assertEqual({p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)},expected)
        spec=native_study_worker.schema(v,native_worker.parameter)
        self.assertTrue(next(p for p in spec['parameters'] if p['id']==length).get('editable',True))

    def test_study_cap_choices_preserve_native_codes_and_reject_unsupported_family_modes(self):
        v=self.v
        ordinary=[v.NO_END_CAP,v.FLAT_END_CAP,v.ROUND_END_CAP,v.EDGE_END_CAP,v.SHARP_END_CAP,v.POINT_END_CAP]
        extended=[v.ROUND_EXT_END_CAP_NONE,v.ROUND_EXT_END_CAP_LE,v.ROUND_EXT_END_CAP_TE,v.ROUND_EXT_END_CAP_BOTH]
        for kind in ('WING','FUSELAGE','STACK','PROP','BODYOFREVOLUTION','POD'):
            with self.subTest(kind=kind):
                self.fixture(kind);before=self.model.read_bytes();pid=v.FindParm(self.gid,'CapUMaxOption','EndCap')
                params={p['id']:p for p in native_study_worker.schema(v,native_worker.parameter)['parameters']}
                choices=params[pid]['choices']
                self.assertEqual([c['value'] for c in choices],ordinary+(extended if kind in ('WING','PROP') else []))
                self.assertEqual(next(c['label'] for c in choices if c['value']==v.POINT_END_CAP),'Point')
                request=dict(axes=[dict(kind='parameter',id=pid,values=[v.FLAT_END_CAP,v.ROUND_END_CAP,v.POINT_END_CAP])],stages=[dict(name='CompGeom',inputs=[])])
                plan=native_study_worker.validate(v,request,native_worker.parameter,native_worker.analysis_schema,native_worker.set_inputs)
                self.assertEqual(plan['axes'][0]['choices'],choices)
                self.assertEqual(plan['axes'][0]['values'],[1,2,5])
                self.assertEqual(plan['axes'][0]['id'],pid)
                if kind not in ('WING','PROP'):
                    request['axes'][0]['values']=[v.ROUND_EXT_END_CAP_LE]
                    with self.assertRaisesRegex(ValueError,'supported native option'):
                        native_study_worker.validate(v,request,native_worker.parameter,native_worker.analysis_schema,native_worker.set_inputs)
                if kind in ('WING','PROP','BODYOFREVOLUTION'):
                    if kind=='BODYOFREVOLUTION':edge=v.FindParm(self.gid,'LE_Cap_Type','Cap')
                    else:edge=v.GetXSecParm(v.GetXSec(v.GetXSecSurf(self.gid,0),1),'LE_Cap_Type')
                    self.assertEqual([c['value'] for c in params[edge]['choices']],[1,2,3,4])
                self.assertEqual(self.model.read_bytes(),before)
