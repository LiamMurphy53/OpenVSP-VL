"""Chevron editing must preserve complete official-engine geometry."""
import sys
import json
import subprocess
import unittest
import test_profile_controls as profile_tests
import native_preview
import native_study_worker
import native_worker


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class Chevrons(unittest.TestCase):
    setUpClass=classmethod(profile_tests.ProfileControls.setUpClass.__func__)
    setUp=profile_tests.ProfileControls.setUp
    tearDown=profile_tests.ProfileControls.tearDown
    worker=profile_tests.ProfileControls.worker
    apply=profile_tests.ProfileControls.apply
    fixture=profile_tests.ProfileControls.fixture
    parm=profile_tests.ProfileControls.parm
    reopened=profile_tests.ProfileControls.reopened

    def step(self,path,name,value):
        try:return self.apply(path,self.parm(name,'Chevron'),value)
        except AssertionError as error:
            raise AssertionError(f'{self.kind}: {name}={value}: {error}') from error

    def compare(self,state):
        if self.kind!='PROP':return profile_tests.ProfileControls.compare(self,state)
        v=self.v;c=state['components'][0]
        self.assertEqual({p['id']:p['value'] for p in c['params']},{p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)})
        def coordinates(actual,expected):
            self.assertEqual(len(actual),len(expected))
            for a,b in zip(actual,expected):
                self.assertEqual(len(a),3)
                for x,y in zip(a,b):self.assertLessEqual(abs(x-y),1e-14)
        # Eight independent unmodified native runs varied by 5.33e-15.
        # Retain every coordinate; allow only that floating-point scale.
        self.assertEqual(len(c['surfaces']),v.GetTotalNumSurfs(self.gid))
        for s in c['surfaces']:
            u,w=v.GetUWTess01(self.gid,s['index']%v.GetNumMainSurfs(self.gid))
            self.assertEqual((s['rows'],s['cols']),(len(u),len(w)))
            pts=v.CompVecPnt01(self.gid,s['index'],[a for a in u for _ in w],[b for _ in u for b in w])
            coordinates(s['points'],[[p.x(),p.y(),p.z()] for p in pts])
        for s in c['sections']:
            x=v.GetXSec(v.GetXSecSurf(self.gid,s['surface']),s['index'])
            pts=[v.ComputeXSecPnt(x,i/100) for i in range(101)]
            coordinates(s['profile'],[[p.x(),p.y(),p.z()] for p in pts])

    def fresh_bor(self,path,pid='',value=None):
        # Independent public SDK reference: a native constructor assigns the
        # curve's correct parent, unlike the installed circle DecodeXml path.
        # Native shape reconstruction copies the decoded profile parameters
        # without setting dependent fields in an artificial order. Its new
        # IDs are mapped by unique raw group/name to assert all original IDs
        # and values, with no fields or sampled coordinates omitted.
        script='''import json,sys
from vsp_runtime import load
v=load();v.ReadVSPFile(sys.argv[1]);v.Update();g=sys.argv[2]
original={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.GetGeomParmIDs(g)}
target=(v.GetParmGroupName(sys.argv[3]),v.GetParmName(sys.argv[3])) if sys.argv[3] else None
assert v.GetBORXSecShape(g)==v.XS_CIRCLE
v.ChangeBORXSecShape(g,v.XS_ELLIPSE)
v.ChangeBORXSecShape(g,v.XS_CIRCLE)
ids={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.GetGeomParmIDs(g)}
if target:v.SetParmValUpdate(ids[target],json.loads(sys.argv[4]))
v.Update()
assert set(original)==set(ids)
xyz=lambda p:[p.x(),p.y(),p.z()]
surfaces=[]
for i in range(v.GetTotalNumSurfs(g)):
 u,w=v.GetUWTess01(g,i%v.GetNumMainSurfs(g))
 surfaces.append(dict(index=i,rows=len(u),cols=len(w),points=[xyz(p) for p in v.CompVecPnt01(g,i,[a for a in u for _ in w],[b for _ in u for b in w])]))
print(json.dumps(dict(params={original[key]:v.GetParmVal(p) for key,p in ids.items()},surfaces=surfaces,profile=[xyz(v.ComputeBORXSecPnt(g,i/100)) for i in range(101)])))'''
        from vsp_runtime import interpreter
        output=subprocess.run([interpreter(),'-c',script,str(path),self.gid,pid,json.dumps(value)],cwd=profile_tests.test_native.ROOT,capture_output=True,text=True,check=True,timeout=20)
        return json.loads(output.stdout)

    def controls(self,state):
        c=state['components'][0]
        profile=c.get('profileControls') if self.kind=='BODYOFREVOLUTION' else c['sections'][1]['profileControls']
        return profile['chevrons'],{p['id']:p for p in c['params']}

    def compare_bor(self,state,expected):
        c=state['components'][0]
        actual={p['id']:p['value'] for p in c['params']}
        differences=[(p['rawGroup'],p['name'],p['value'],expected['params'].get(p['id']))
                     for p in c['params'] if p['value']!=expected['params'].get(p['id'])]
        self.assertEqual(actual,expected['params'],json.dumps(differences))
        self.assertEqual(c['surfaces'],expected['surfaces'])
        self.assertEqual(state['tools']['bodiesOfRevolution'][0]['profile'],expected['profile'])

    def test_full_and_partial_native_patterns_all_owner_families(self):
        for kind in ('WING','PROP','FUSELAGE','STACK','BODYOFREVOLUTION'):
            with self.subTest(kind=kind):
                path=self.fixture(kind);before,_=self.worker(dict(action='state'),path)
                for name,value in [('Chevron_Type',2),('Number',5),('TopAmplitude',.12),('Top_Angle',15.),
                                   ('Top_Slew',-8.),('On_Duty',.12),('Off_Duty',.18),
                                   ('Peak_Radius',.006),('Valley_Radius',.008),('W01_Start',.1),
                                   ('Chevron_Type',1),('W01_Start_Guide',self.v.W_FREE),
                                   ('W01_End_Guide',self.v.W_FREE),('W01_Start',.85),('W01_End',.25)]:
                    state,path=self.step(path,name,value)
                controls,params=self.controls(state)
                self.assertAlmostEqual(params[controls['extent'][7]]['value'],.4)
                self.assertTrue(params[controls['extent'][5]]['displayReadOnly'])
                self.assertTrue(params[controls['extent'][7]]['displayReadOnly'])
                self.assertNotEqual(before['components'][0]['surfaces'],state['components'][0]['surfaces'])
                state,path=self.step(path,'W01_End',.3)
                for guide in (self.v.W_RIGHT_0,self.v.W_BOTTOM,self.v.W_LEFT,self.v.W_TOP,self.v.W_RIGHT_1,self.v.W_FREE):
                    state,path=self.step(path,'W01_Start_Guide',guide)
                for name,value in [('W01_Mode',1),('W01_Center_Guide',self.v.W_FREE),
                                   ('W01_Center',.9),('W01_Width',.35)]:
                    state,path=self.step(path,name,value)
                controls,params=self.controls(state)
                self.assertTrue(params[controls['extent'][2]]['displayReadOnly'])
                self.assertFalse(params[controls['extent'][6]].get('displayReadOnly',False))
                self.reopened(path)

    def test_direction_symmetry_native_values_activity_and_saved_geometry(self):
        for kind in ('WING','PROP','FUSELAGE','STACK','BODYOFREVOLUTION'):
            with self.subTest(kind=kind):
                path=self.fixture(kind)
                for name,value in [('Chevron_Type',2),('TopAmplitude',.15),('AllSym',0),('TBSym',0),('RLSym',0),
                    ('BottomAmplitude',.1),('LeftAmplitude',.2),('RightAmplitude',.25),
                    ('Bottom_Angle',-12.),('Right_Angle',8.),('Left_Angle',-4.),
                    ('Bottom_Slew',6.),('Right_Slew',-5.),('Left_Slew',9.)]:
                    state,path=self.step(path,name,value)
                controls,params=self.controls(state)
                self.assertEqual(params[controls['directions'][1]['parameters'][0]]['name'],'LeftAmplitude')
                self.assertEqual(params[controls['directions'][3]['parameters'][0]]['name'],'RightAmplitude')
                self.assertTrue(all(params[p]['active'] and not params[p].get('displayReadOnly',False)
                                    for d in controls['directions'] for p in d['parameters']))
                for name,value in [('TBSym',1),('RLSym',1),('AllSym',1)]:
                    state,path=self.step(path,name,value)
                controls,params=self.controls(state)
                for d in controls['directions'][1:]:
                    self.assertEqual(params[d['parameters'][0]]['value'],.15)
                    self.assertTrue(all(params[p]['displayReadOnly'] for p in d['parameters']))
                self.reopened(path)

    def test_inactive_and_invalid_values_preserve_native_file(self):
        path=self.fixture('STACK');v=self.v;before=path.read_bytes()
        for name,value in [('Number',4),('TopAmplitude',.1),('W01_Start',.3)]:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='parameter',id=self.parm(name,'Chevron'),value=value),path)
            self.assertEqual(path.read_bytes(),before)
        state,path=self.step(path,'Chevron_Type',2);before=path.read_bytes()
        for name,value in [('Number',2.5),('Number',0),('Chevron_Type',True),('TopAmplitude',float('nan')),
                           ('BottomAmplitude',.2),('W01_Width',.4),('W01_Start_Guide',5),('On_Duty',1.)]:
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='parameter',id=self.parm(name,'Chevron'),value=value),path)
            self.assertEqual(path.read_bytes(),before)
        state,path=self.step(path,'Chevron_Type',1);before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'nonzero outline width'):
            self.worker(dict(action='mutate',operation='parameter',id=self.parm('W01_End_Guide','Chevron'),value=v.W_RIGHT_0),path)
        self.assertEqual(path.read_bytes(),before)
        state,path=self.step(path,'W01_Mode',1);before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'nonzero outline width'):
            self.worker(dict(action='mutate',operation='parameter',id=self.parm('W01_Width','Chevron'),value=0),path)
        self.assertEqual(path.read_bytes(),before)
        path=self.fixture('FUSELAGE')
        point=v.GetXSec(v.GetXSecSurf(self.gid,0),0)
        with self.assertRaisesRegex(ValueError,'Point profiles'):
            self.worker(dict(action='mutate',operation='parameter',id=v.GetXSecParm(point,'Chevron_Type'),value=2),path)

    def test_loaded_bor_parent_refresh_completes_surfaces_before_snapshot(self):
        path=self.fixture('BODYOFREVOLUTION')
        for name,value in [('Chevron_Type',2),('TopAmplitude',.12),('Number',5),
                           ('Chevron_Type',1),('W01_Start_Guide',self.v.W_FREE),
                           ('W01_End_Guide',self.v.W_FREE),('W01_Start',.85),
                           ('W01_End',.3),('W01_Mode',1),('W01_Center_Guide',self.v.W_FREE),
                           ('W01_Center',.9),('W01_Width',.35)]:
            _,path=self.step(path,name,value)
        state=self.reopened(path)
        controls,params=self.controls(state)
        self.assertTrue(params[controls['pattern'][0]]['active'])
        self.assertEqual(params[controls['extent'][7]]['value'],.35)

    def test_prepared_cases_order_native_coverage_guides_and_symmetry(self):
        self.fixture('FUSELAGE');v=self.v
        changes=[('W01_Width',.4),('W01_Center',.85),('BottomAmplitude',.1),('TopAmplitude',.2),
                 ('W01_Center_Guide',v.W_FREE),('TBSym',0),('AllSym',0),('W01_Mode',1),('Chevron_Type',1)]
        schema=native_study_worker.schema(v,native_worker.parameter)
        self.assertFalse(next(p for p in schema['parameters'] if p['id']==self.parm('W01_Width','Chevron'))['editable'])
        native_study_worker.prepare(v,dict(parameters=[dict(id=self.parm(n,'Chevron'),value=x) for n,x in changes]),self.path/'case.vsp3',native_worker.errors)
        state,_=self.worker(dict(action='state'),self.path/'case.vsp3')
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        for name,value in reversed(changes):v.SetParmValUpdate(self.parm(name,'Chevron'),value)
        self.compare(state)
        schema=native_study_worker.schema(v,native_worker.parameter)
        self.assertTrue(next(p for p in schema['parameters'] if p['id']==self.parm('W01_Width','Chevron')).get('editable',True))
        with self.assertRaises(ValueError):
            native_study_worker.prepare(v,dict(parameters=[dict(id=self.parm('W01_Start','Chevron'),value=.1)]),self.path/'unused.vsp3',native_worker.errors)
