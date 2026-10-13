"""Native surface queries, measurement persistence, and fit recovery."""
import sys
import unittest
import test_native
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class FitNative(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def pod(self):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom('POD');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);return self.gid

    def test_queries_are_exact_native_samples_and_leave_model_unchanged(self):
        v=self.v;g=self.pod();before=self.model.read_bytes();u,w=.35,.21
        def xyz(p):return [p.x(),p.y(),p.z()]
        data,path=self.worker(dict(action='query',operation='surface-evaluate',geom=g,surface=0,u=u,w=w))
        for key,fn in [('point',v.CompPnt01),('normal',v.CompNorm01),('tangentU',v.CompTanU01),('tangentW',v.CompTanW01)]:self.assertEqual(data[key],xyz(fn(g,0,u,w)))
        self.assertEqual(data['curvature'],list(v.CompCurvature01(g,0,u,w)));self.assertEqual(path.read_bytes(),before)
        p=[4.,2.,1.];dist,pu,pw=v.ProjPnt01(g,0,v.vec3d(*p))
        data,path=self.worker(dict(action='query',operation='surface-project',geom=g,surface=0,point=p))
        for key,x in [('distance',dist),('u',pu),('w',pw)]:self.assertAlmostEqual(data[key],x,places=10)
        self.assertEqual(data['inside'],v.InsideSurf(g,0,v.vec3d(*p)))
        data,path=self.worker(dict(action='query',operation='volume-evaluate',geom=g,surface=0,r=.3,s=.4,t=.5))
        self.assertEqual(data['point'],xyz(v.CompPntRST(g,0,.3,.4,.5)))
        with self.assertRaises(ValueError):self.worker(dict(action='query',operation='surface-evaluate',geom=g,surface=0,u=-1,w=.5))

    def test_rulers_probes_survive_native_edits_and_deletion(self):
        v=self.v;g=self.pod();common=dict(action='mutate',operation='measurement-add',geom=g,surface=0,name='Saved measurement',u=.2,w=.25,r=.3,s=.4,t=.5,endgeom=g,endsurface=0,endu=.8,endw=.25)
        path=self.model
        for kind in ['ruler','probe','rst-probe']:state,path=self.worker(common|dict(kind=kind),path)
        self.assertEqual(len(state['tools']['measurements']),3)
        ruler=next(m for m in state['tools']['measurements'] if m['kind']=='ruler');distance=next(p['value'] for p in ruler['params'] if p['name']=='Distance')
        a=v.CompPnt01(g,0,.2,.25);b=v.CompPnt01(g,0,.8,.25);self.assertAlmostEqual(distance,v.dist(a,b),places=10)
        length=v.FindParm(g,'Length','Design')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=length,value=20),path)
        ruler=next(m for m in state['tools']['measurements'] if m['kind']=='ruler');self.assertGreater(next(p['value'] for p in ruler['params'] if p['name']=='Distance'),distance)
        state,path=self.worker(dict(action='mutate',operation='measurement-delete',kind='ruler',id=ruler['id']),path)
        self.assertEqual({m['kind'] for m in state['tools']['measurements']},{'probe','rst-probe'})

    def test_fit_recovers_known_native_geometry_and_persists_native_targets(self):
        v=self.v;g=self.pod();length=v.FindParm(g,'Length','Design');v.SetParmValUpdate(length,12)
        samples=[]
        for u,w in [(.2,.1),(.4,.25),(.65,.45),(.85,.8)]:
            p=v.CompPnt01(g,0,u,w);samples.append((u,w,[p.x(),p.y(),p.z()]))
        v.SetParmValUpdate(length,8);v.WriteVSPFile(str(self.model),v.SET_ALL)
        path=self.model
        for u,w,p in samples:state,path=self.worker(dict(action='mutate',operation='fit-targets-add',geom=g,surface=0,points=[p],fixedU=True,fixedW=True,u=u,w=w),path)
        state,path=self.worker(dict(action='mutate',operation='fit-variables',parameters=[length]),path)
        before=state['tools']['fit']['distance'];self.assertGreater(before,1)
        state,path=self.worker(dict(action='mutate',operation='fit-optimize'),path)
        fit=state['tools']['fit'];self.assertLess(fit['distance'],1e-7)
        self.assertAlmostEqual(next(p['value'] for p in state['components'][0]['params'] if p['id']==length),12,places=7)
        self.assertEqual(fit['variables'],[length]);self.assertEqual(len(fit['targets']),4);self.assertEqual(fit['degreesOfFreedom'],1)
        self.assertAlmostEqual(fit['report']['before'],before);self.assertLess(fit['report']['after'],1e-7);self.assertIn(fit['report']['code'],[1,2,3,4])
        reopened,path=self.worker(dict(action='state'),path)
        self.assertEqual(reopened['tools']['fit'],fit)
        export,out=self.worker(dict(action='export-geometry',kind='fit'),path)
        content=(out.parent/export['filename']).read_text();self.assertIn('<TargetPt',content)
        imported,importpath=self.worker(dict(action='mutate',operation='fit-import',content=content),path);self.assertEqual(imported['tools']['fit']['targets'],fit['targets']);self.assertEqual(imported['tools']['fit']['variables'],fit['variables'])
        state,path=self.worker(dict(action='mutate',operation='fit-target-delete',index=1),path);self.assertEqual(len(state['tools']['fit']['targets']),3)
        state,path=self.worker(dict(action='mutate',operation='fit-reset'),path);self.assertEqual(state['tools']['fit']['targets'],[]);self.assertEqual(state['tools']['fit']['variables'],[])

    def test_underconstrained_fit_is_rejected_without_changing_model(self):
        v=self.v;g=self.pod();p=v.CompPnt01(g,0,.5,.25)
        state,path=self.worker(dict(action='mutate',operation='fit-targets-add',geom=g,surface=0,points=[[p.x(),p.y(),p.z()]],fixedU=False,fixedW=False))
        variables=[v.FindParm(g,'Length','Design'),v.FindParm(g,'FineRatio','Design')]
        state,path=self.worker(dict(action='mutate',operation='fit-variables',parameters=variables),path)
        self.assertEqual(state['tools']['fit']['degreesOfFreedom'],4)
        before=path.read_bytes()
        with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='fit-optimize'),path)
        self.assertEqual(path.read_bytes(),before)

    def test_clearance_and_snap_match_native_engine(self):
        v=self.v;g=self.pod();other=v.AddGeom('POD');v.SetParmValUpdate(other,'Y_Rel_Location','XForm',5)
        setid=3;v.SetSetFlag(other,setid,True);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        expected=v.ComputeMinClearanceDistance(g,setid)
        data,path=self.worker(dict(action='query',operation='clearance',geom=g,set=setid));self.assertAlmostEqual(data['distance'],expected,places=10)
        parameter=v.FindParm(g,'Y_Rel_Location','XForm');v.SnapParm(parameter,1.,True,setid);target=v.GetParmVal(parameter)
        state,path=self.worker(dict(action='mutate',operation='clearance-snap',geom=g,parameter=parameter,distance=1.,increase=True,set=setid))
        self.assertAlmostEqual(next(p['value'] for p in state['components'][0]['params'] if p['id']==parameter),target,places=10)
