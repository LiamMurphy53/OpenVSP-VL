"""Free target coordinates follow the original native optimizer exactly."""
import sys
import unittest
import test_native
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class FreeCoordinateFit(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_free_and_mixed_coordinate_fits_match_native_optimization_and_cold_geometry(self):
        v=self.v;v.ClearVSPModel();g=v.AddGeom('POD');v.Update()
        length=v.FindParm(g,'Length','Design');v.SetParmValUpdate(length,12)
        stations=[(.2,.1),(.4,.25),(.65,.45),(.85,.8)]
        points=[[p.x(),p.y(),p.z()] for p in (v.CompPnt01(g,0,u,w) for u,w in stations)]
        v.SetParmValUpdate(length,8);v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        for fixed_u,fixed_w in [(False,False),(False,True),(True,False)]:
            with self.subTest(fixedU=fixed_u,fixedW=fixed_w):
                seeds=[[u if fixed_u else u+.03,w if fixed_w else w+.04] for u,w in stations]
                state,path=self.worker(dict(action='mutate',operation='fit-targets-add',geom=g,surface=0,points=points,coordinates=seeds,fixedU=fixed_u,fixedW=fixed_w))
                state,path=self.worker(dict(action='mutate',operation='fit-variables',parameters=[length]),path)
                start=state['tools']['fit'];saved=path.read_bytes()
                v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();v.ResetFitModel()
                ut=v.FIT_MODEL_FIXED if fixed_u else v.FIT_MODEL_FREE;wt=v.FIT_MODEL_FIXED if fixed_w else v.FIT_MODEL_FREE
                for point,(u,w) in zip(points,seeds):
                    i=v.AddFitModelTargetPt(g,0,v.vec3d(*point),ut,wt,u,w);v.SetFitModelTargetPtUW(i,u,w)
                v.AddFitModelVar(length)
                self.assertEqual(v.GetNumFitModelOptVars(),start['degreesOfFreedom'])
                self.assertEqual(v.UpdateFitModelDist(),start['distance'])
                code=v.OptimizeFitModel();distance=v.UpdateFitModelDist();expected_length=v.GetParmVal(length)
                expected_uw=[[v.GetFitModelTargetPtU(i),v.GetFitModelTargetPtW(i)] for i in range(len(points))]
                self.assertIn(code,[1,2,3,4]);self.assertLess(distance,1e-7)
                self.assertAlmostEqual(expected_length,12,places=7)
                expected=[]
                for i in range(v.GetTotalNumSurfs(g)):
                    u,w=v.GetUWTess01(g,i%v.GetNumMainSurfs(g))
                    expected.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(g,i,[a for a in u for _ in w],[b for _ in u for b in w])])
                state,output=self.worker(dict(action='mutate',operation='fit-optimize'),path)
                cold,_=self.worker(dict(action='state'),output)
                for data in (state,cold):
                    fit=data['tools']['fit'];component=next(c for c in data['components'] if c['id']==g)
                    self.assertEqual(fit['report']['code'],code);self.assertEqual(fit['distance'],distance)
                    self.assertEqual([[t['u'],t['w']] for t in fit['targets']],expected_uw)
                    self.assertEqual(next(p['value'] for p in component['params'] if p['id']==length),expected_length)
                    self.assertEqual([s['points'] for s in component['surfaces']],expected)
                v.SaveFitModelFile(str(self.path/'direct.fit'))
                expected_file=(self.path/'direct.fit').read_bytes()
                exported,artifact=self.worker(dict(action='export-geometry',kind='fit'),output)
                content=(artifact.parent/exported['filename']).read_bytes()
                self.assertEqual(content,expected_file)
                imported,_=self.worker(dict(action='mutate',operation='fit-import',content=content.decode()),output)
                self.assertEqual(imported['tools']['fit']['targets'],state['tools']['fit']['targets'])
                self.assertEqual(imported['tools']['fit']['variables'],[length])
                self.assertEqual(path.read_bytes(),saved)
        self.assertEqual(self.model.read_bytes(),before)

    def test_search_and_refine_match_original_with_mixed_fixed_coordinates(self):
        v=self.v;v.ClearVSPModel();g=v.AddGeom('POD');v.Update()
        stations=[(.2,.1),(.4,.25),(.65,.45),(.85,.8)]
        points=[[p.x(),p.y(),p.z()] for p in (v.CompPnt01(g,0,u,w) for u,w in stations)]
        seeds=[[u,w+.04] for u,w in stations]
        v.WriteVSPFile(str(self.model),v.SET_ALL);original=self.model.read_bytes()
        state,path=self.worker(dict(action='mutate',operation='fit-targets-add',geom=g,surface=0,points=points,coordinates=seeds,fixedU=True,fixedW=False))
        geometry=[c['surfaces'] for c in state['components']]
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();v.ResetFitModel()
        for point,(u,w) in zip(points,seeds):
            i=v.AddFitModelTargetPt(g,0,v.vec3d(*point),v.FIT_MODEL_FIXED,v.FIT_MODEL_FREE,u,w);v.SetFitModelTargetPtUW(i,u,w)
        for operation,action in [('fit-search',v.SearchFitModelTargetUW),('fit-refine',v.RefineFitModelTargetUW)]:
            before=path.read_bytes();action()
            expected=[[v.GetFitModelTargetPtU(i),v.GetFitModelTargetPtW(i)] for i in range(len(points))]
            distance=v.UpdateFitModelDist()
            state,output=self.worker(dict(action='mutate',operation=operation),path)
            cold,_=self.worker(dict(action='state'),output)
            for data in (state,cold):
                fit=data['tools']['fit']
                self.assertEqual([[t['u'],t['w']] for t in fit['targets']],expected)
                self.assertEqual(fit['distance'],distance)
                self.assertTrue(all(t['utype']==v.FIT_MODEL_FIXED and t['wtype']==v.FIT_MODEL_FREE for t in fit['targets']))
                self.assertEqual([c['surfaces'] for c in data['components']],geometry)
            self.assertEqual(path.read_bytes(),before);path=output
        self.assertEqual(self.model.read_bytes(),original)

    def test_fresh_fixed_target_exports_match_original_surface_closure_initialization(self):
        v=self.v
        for kind in ('POD','WING','BODYOFREVOLUTION'):
            with self.subTest(kind=kind):
                v.ClearVSPModel();v.ResetFitModel();g=v.AddGeom(kind);v.Update()
                samples=[]
                for surface in range(v.GetTotalNumSurfs(g)):
                    point=v.CompPnt01(g,surface,.35,.4);samples.append((surface,[point.x(),point.y(),point.z()]))
                v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes();path=self.model
                for surface,point in samples:
                    _,path=self.worker(dict(action='mutate',operation='fit-targets-add',geom=g,surface=surface,points=[point],fixedU=True,fixedW=True,u=.35,w=.4),path)
                    i=v.AddFitModelTargetPt(g,surface,v.vec3d(*point),v.FIT_MODEL_FIXED,v.FIT_MODEL_FIXED,.35,.4);v.SetFitModelTargetPtUW(i,.35,.4)
                # Original refinement initializes per-surface closure while
                # fixed target coordinates and all geometry remain unchanged.
                v.RefineFitModelTargetUW();v.SaveFitModelFile(str(self.path/'fixed-direct.fit'))
                expected=(self.path/'fixed-direct.fit').read_bytes()
                exported,artifact=self.worker(dict(action='export-geometry',kind='fit'),path)
                actual=(artifact.parent/exported['filename']).read_bytes()
                self.assertEqual(actual,expected)
                self.assertEqual(self.model.read_bytes(),before)
