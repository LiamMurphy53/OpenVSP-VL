"""Exact original SDK volume search/conversion parity and input guards."""
import sys,unittest,math,json,tempfile
from pathlib import Path
from vsp_runtime import load
import native_volume

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class VolumeQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.v=load()
    def setUp(self):
        v=self.v;v.ClearVSPModel();self.g=v.AddGeom('POD');v.SetParmVal(v.FindParm(self.g,'X_Rel_Location','XForm'),4.);v.SetParmVal(v.FindParm(self.g,'Y_Rel_Location','XForm'),-2.);v.SetParmVal(v.FindParm(self.g,'Z_Rel_Rotation','XForm'),25.);v.Update()
    def test_both_original_conversion_directions_and_complete_native_point(self):
        v=self.v
        for kind in ['POD','FUSELAGE','WING']:
            g=v.AddGeom(kind);v.Update()
            for coords in [[.12,.68,.56],[.8,.2,.9],[0.,.5,1.]]:
                for basis in ['RST','LMN']:
                    with self.subTest(kind=kind,basis=basis,coordinates=coords):
                        q=native_volume.query(v,dict(operation='volume-convert',geom=g,basis=basis,coordinates=coords))
                        if basis=='RST':rst=coords;lmn=list(v.ConvertRSTtoLMN(g,0,*coords))
                        else:rst=list(v.ConvertLMNtoRST(g,0,*coords));lmn=coords
                        p=v.CompPntRST(g,0,*rst)
                        self.assertEqual(q['RST'],[x if math.isfinite(x) else None for x in rst]);self.assertEqual(q['LMN'],[x if math.isfinite(x) else None for x in lmn]);json.dumps(q,allow_nan=False);self.assertEqual(q['point'],[p.x(),p.y(),p.z()])
    def test_original_nearest_search_with_and_without_guess_preserves_complete_values(self):
        v=self.v;p=v.CompPntRST(self.g,0,.12,.68,.56)
        for xyz in [[p.x(),p.y(),p.z()],[2.,3.,1.]]:
            for guess in [None,[.2,.6,.5]]:
                req=dict(operation='volume-project',geom=self.g,point=xyz)
                if guess is not None:req['guess']=guess
                q=native_volume.query(v,req);pnt=v.vec3d(*xyz)
                expected=list(v.FindRST(self.g,0,pnt) if guess is None else v.FindRSTGuess(self.g,0,pnt,*guess))
                self.assertEqual([q['distance'],*q['RST']],expected)
                self.assertEqual(q['LMN'],list(v.ConvertRSTtoLMN(self.g,0,*expected[1:])))
                self.assertEqual(q['inside'],bool(v.InsideSurf(self.g,0,pnt)))
    def test_native_undefined_tip_conversion_preserves_null_and_valid_native_point(self):
        v=self.v;rst=[0.,.5,1.];raw=list(v.ConvertRSTtoLMN(self.g,0,*rst))
        self.assertTrue(any(not math.isfinite(x) for x in raw))
        q=native_volume.query(v,dict(operation='volume-convert',geom=self.g,basis='RST',coordinates=rst))
        self.assertEqual(q['LMN'],[x if math.isfinite(x) else None for x in raw]);self.assertEqual(q['RST'],rst)
        p=v.CompPntRST(self.g,0,*rst);self.assertEqual(q['point'],[p.x(),p.y(),p.z()])
        self.assertIn('undefined',q['nativeWarning']);json.dumps(q,allow_nan=False)

    def test_symmetry_surface_queries_keep_original_native_index_and_results(self):
        v=self.v;g=v.AddGeom('WING');v.Update();self.assertGreater(v.GetTotalNumSurfs(g),1)
        for s in range(v.GetTotalNumSurfs(g)):
            q=native_volume.query(v,dict(operation='volume-convert',geom=g,surface=s,basis='RST',coordinates=[.7,.4,.6]))
            self.assertEqual(q['surface'],s);self.assertEqual(q['LMN'],list(v.ConvertRSTtoLMN(g,s,.7,.4,.6)))
            p=v.CompPntRST(g,s,.7,.4,.6);self.assertEqual(q['point'],[p.x(),p.y(),p.z()])
            found=native_volume.query(v,dict(operation='volume-project',geom=g,surface=s,point=[p.x(),p.y(),p.z()]))
            self.assertEqual([found['distance'],*found['RST']],list(v.FindRST(g,s,p)))

    def test_saved_native_aircraft_reopens_with_exact_query_values_and_unchanged_file(self):
        v=self.v
        with tempfile.TemporaryDirectory() as temp:
            model=Path(temp)/'aircraft.vsp3';v.WriteVSPFile(str(model),v.SET_ALL);original=model.read_bytes()
            v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update()
            before={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.g)}
            rst=[.12,.68,.56];expected=list(v.ConvertRSTtoLMN(self.g,0,*rst))
            q=native_volume.query(v,dict(operation='volume-convert',geom=self.g,basis='RST',coordinates=rst))
            self.assertEqual(q['LMN'],expected)
            point=v.CompPntRST(self.g,0,*rst);xyz=[point.x(),point.y(),point.z()]
            q=native_volume.query(v,dict(operation='volume-project',geom=self.g,point=xyz,guess=[.2,.6,.5]))
            self.assertEqual([q['distance'],*q['RST']],list(v.FindRSTGuess(self.g,0,point,.2,.6,.5)))
            self.assertEqual(model.read_bytes(),original);self.assertEqual({p:v.GetParmVal(p) for p in before},before)

    def test_invalid_vectors_coordinates_references_and_guesses_leave_geometry_unchanged(self):
        v=self.v;before={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.g)}
        requests=[dict(operation='volume-convert',basis='RST',coordinates=x) for x in [[-1.,.2,.3],[.2,1.1,.3],[.2,.3],[float('nan'),.2,.3]]]
        requests += [dict(operation='volume-project',point=[1.,2.,3.],guess=[.1,.2,2.]),dict(operation='volume-project',point=[1.,float('inf'),3.]),dict(operation='volume-convert',basis='XYZ',coordinates=[.1,.2,.3]),dict(operation='volume-convert',basis='RST',coordinates=[.1,.2,.3],surface=99)]
        for r in requests:
            with self.subTest(request=r),self.assertRaises(ValueError):native_volume.query(v,dict(geom=self.g,**r))
            self.assertEqual({p:v.GetParmVal(p) for p in before},before)

import test_native
@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class VolumeWorkerQueries(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    def test_real_worker_dispatch_preserves_source_and_matches_original_saved_sdk(self):
        v=self.v;v.ClearVSPModel();g=v.AddGeom('POD');v.SetParmVal(v.FindParm(g,'X_Rel_Location','XForm'),4.);v.SetParmVal(v.FindParm(g,'Z_Rel_Rotation','XForm'),25.);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        before=self.model.read_bytes();v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();rst=[.12,.68,.56];p=v.CompPntRST(g,0,*rst)
        result,path=self.worker(dict(action='query',operation='volume-convert',geom=g,basis='RST',coordinates=rst))
        self.assertEqual(result['LMN'],list(v.ConvertRSTtoLMN(g,0,*rst)));self.assertEqual(result['point'],[p.x(),p.y(),p.z()]);self.assertEqual(result['engineVersion'],v.GetVSPVersion());self.assertEqual(path.read_bytes(),before)
        for guess in [None,[.2,.6,.5]]:
            req=dict(action='query',operation='volume-project',geom=g,point=[p.x(),p.y(),p.z()])
            if guess is not None:req['guess']=guess
            result,path=self.worker(req)
            direct=list(v.FindRST(g,0,p) if guess is None else v.FindRSTGuess(g,0,p,*guess))
            self.assertEqual([result['distance'],*result['RST']],direct);self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main()
