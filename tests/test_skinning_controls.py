"""Guided skinning parameters must match full native geometry and saved state."""
import sys
import unittest
import test_native
import native_study_worker
import native_worker
from vsp_runtime import load
from native_preview import parameter_activity


@unittest.skipUnless(sys.version_info[:2] == (3, 11), 'Use the matching native Python runtime.')
class SkinningControls(unittest.TestCase):
    setUpClass = classmethod(lambda cls: setattr(cls, 'v', load()))
    setUp = test_native.NativeIntegration.setUp
    tearDown = test_native.NativeIntegration.tearDown
    worker = test_native.NativeIntegration.worker

    def fixture(self, kind='FUSELAGE'):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom(kind);v.Update()
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        return v.GetXSec(v.GetXSecSurf(self.gid,0),2)

    def compare(self,state):
        v=self.v;c=state['components'][0]
        self.assertEqual({p['id']:p['value'] for p in c['params']},{p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)})
        for s in c['surfaces']:
            u,w=v.GetUWTess01(self.gid,s['index']%v.GetNumMainSurfs(self.gid))
            points=v.CompVecPnt01(self.gid,s['index'],[x for x in u for _ in w],[y for _ in u for y in w])
            self.assertEqual(s['points'],[[p.x(),p.y(),p.z()] for p in points])
        by_id={p['id']:p for p in c['params']}
        for s in c['sections']:
            x=v.GetXSec(v.GetXSecSurf(self.gid,s['surface']),s['index'])
            self.assertEqual(s['skin']['continuity'],v.GetXSecContinuity(x))
            for side in ('XSEC_LEFT_SIDE','XSEC_RIGHT_SIDE'):
                for key,fn in [('angles',v.GetXSecTanAngles),('slews',v.GetXSecTanSlews),('strengths',v.GetXSecTanStrengths),('curvatures',v.GetXSecCurvatures)]:
                    self.assertEqual(s['skin']['sides'][side][key],list(fn(x,getattr(v,side))))
            active=parameter_activity(v,s['skinControls']['parameters'])
            for pid in s['skinControls']['parameters']:self.assertEqual(by_id[pid]['active'],active[pid])

    def apply(self,path,name,value,index=2):
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        x=v.GetXSec(v.GetXSecSurf(self.gid,0),index);pid=v.GetXSecParm(x,name)
        v.SetParmValUpdate(pid,value);v.Update()
        state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
        self.compare(state)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        reopened,_=self.worker(dict(action='state'),path);self.compare(reopened)
        return state,path

    def test_manual_continuity_symmetry_and_equality_match_native_on_bodies_and_stacks(self):
        for kind in ('FUSELAGE','STACK'):
            self.fixture(kind);path=self.model
            steps=[('TopLAngleSet',1),('TopLAngle',12.),('TopLStrength',.8),('TopLSlew',4.),
                   ('TopLCurveSet',1),('TopLCurve',.3),('ContinuityTop',1),
                   ('AllSym',0),('TBSym',0),('RLSym',0),('RightLAngle',-6.),
                   ('BottomLStrength',.9),('LeftLSlew',-3.),('ContinuityTop',2),
                   ('ContinuityTop',0),('TopLRAngleEq',0),('TopLRSlewEq',0),
                   ('TopLRStrengthEq',0),('TopLRCurveEq',0),('TopRAngle',-8.),
                   ('TopRStrength',1.3),('TopRSlew',3.),('TopRCurve',-.2),('AllSym',1)]
            for name,value in steps:
                with self.subTest(kind=kind,name=name,value=value):state,path=self.apply(path,name,value)
            v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
            x=v.GetXSec(v.GetXSecSurf(self.gid,0),2);v.ResetXSecSkinParms(x);v.Update()
            state,path=self.worker(dict(action='mutate',operation='section-skin-reset',geom=self.gid,index=2),path);self.compare(state)

    def test_endpoint_guidance_and_all_section_reset_preserve_native_math(self):
        v=self.v;self.fixture('STACK');surf=v.GetXSecSurf(self.gid,0);count=v.GetNumXSec(surf)
        path=self.model
        for index in (0,count-1):
            state,path=self.apply(path,'TopLAngleSet',1,index)
            state,path=self.apply(path,'TopLAngle',18. if index==0 else -12.,index)
            s=state['components'][0]['sections'][index];params={p['id']:p for p in state['components'][0]['params']}
            self.assertTrue(params[s['skinControls']['continuity']]['displayReadOnly'])
            self.assertIn('After constraints are unused',s['skinControls']['endpoint'])
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();surf=v.GetXSecSurf(self.gid,0)
        for i in range(v.GetNumXSec(surf)):v.ResetXSecSkinParms(v.GetXSec(surf,i))
        v.Update()
        state,saved=self.worker(dict(action='mutate',operation='body-skin-reset-all',geom=self.gid),path);self.compare(state)
        v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update()
        reopened,_=self.worker(dict(action='state'),saved);self.compare(reopened)

    def test_calculated_fields_and_invalid_values_are_atomic_and_studies_use_same_guidance(self):
        v=self.v;x=self.fixture();v.ResetXSecSkinParms(x);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        state,_=self.worker(dict(action='state'));c=state['components'][0];s=c['sections'][2];params={p['name']:p for p in c['params'] if p['id'] in s['skinControls']['parameters']}
        for name in ('TopLAngle','TopLStrength','TopLSlew','TopLCurve','TBSym','RLSym','RightLAngle','TopLStrengthSet','TopLSlewSet','ContinuityRight'):
            self.assertTrue(params[name]['displayReadOnly'],name)
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='parameter',id=params[name]['id'],value=1.))
            self.assertEqual(self.model.read_bytes(),before)
        angle=params['TopLAngle']['id']
        spec=native_study_worker.schema(v,native_worker.parameter)
        self.assertFalse(next(p for p in spec['parameters'] if p['id']==angle)['editable'])
        with self.assertRaises(ValueError):native_study_worker.prepare(v,dict(parameters=[dict(id=angle,value=12.)]),self.path/'case.vsp3',native_worker.errors)
        v.SetParmValUpdate(v.GetXSecParm(x,'TopLAngleSet'),1);v.WriteVSPFile(str(self.model),v.SET_ALL)
        spec=native_study_worker.schema(v,native_worker.parameter)
        self.assertTrue(next(p for p in spec['parameters'] if p['id']==angle).get('editable',True))
        before=self.model.read_bytes()
        for value in (float('nan'),400.,True):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='parameter',id=angle,value=value))
            self.assertEqual(self.model.read_bytes(),before)
        # A manual constraint remains available to real saved study cases.
        prepared=self.path/'manual-skin-study.vsp3'
        result=native_study_worker.prepare(v,dict(parameters=[dict(id=angle,value=12.)]),prepared,native_worker.errors)
        self.assertEqual(result['parameters'][0]['requested'],12.)
        self.assertEqual(result['parameters'][0]['effective'],12.)
        self.assertEqual(self.model.read_bytes(),before)
        state,_=self.worker(dict(action='state'),prepared)
        self.compare(state)
