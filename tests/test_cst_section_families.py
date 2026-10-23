"""CST editing follows the native profile family rather than its geometry owner."""
import base64,math,unittest
import test_native
from native_cst_validation import AIRFOIL_SHAPES,fitting_allowed


class CSTSectionFamilies(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self,kind,shape=None):
        v=self.v;v.ClearVSPModel();gid=v.AddGeom(kind);surf=v.GetXSecSurf(gid,0)
        v.ChangeXSecShape(surf,1,v.XS_FOUR_SERIES if shape is None else shape);v.Update()
        xid=v.GetXSec(surf,1)
        if fitting_allowed(v,v.GetXSecShape(xid)):
            v.SetParmVal(v.GetXSecParm(xid,'Chord'),2);v.SetParmVal(v.GetXSecParm(xid,'ThickChord'),.15);v.Update()
        v.WriteVSPFile(str(self.model),v.SET_ALL);return gid,surf,xid

    def original(self,gid):
        v=self.v;v.Update();surf=v.GetXSecSurf(gid,0);x=v.GetXSec(surf,1)
        parameters=sorted((v.GetParmGroupName(p),v.GetParmName(p),v.GetParmVal(p)) for p in v.GetGeomParmIDs(gid))
        profiles=[[[p.x(),p.y(),p.z()] for p in [v.ComputeXSecPnt(v.GetXSec(surf,j),i/100) for i in range(101)]] for j in range(v.GetNumXSec(surf))]
        surfaces=[]
        for i in range(v.GetTotalNumSurfs(gid)):
            u,w=v.GetUWTess01(gid,i%v.GetNumMainSurfs(gid));surfaces.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(gid,i,[a for a in u for _ in w],[b for _ in u for b in w])])
        return dict(params=parameters,profiles=profiles,surfaces=surfaces,upper=list(v.GetUpperCSTCoefs(x)),lower=list(v.GetLowerCSTCoefs(x)))

    def compare(self,state,gid,expected):
        c=next(c for c in state['components'] if c['id']==gid)
        self.assertEqual(sorted((p['rawGroup'],p['name'],p['value']) for p in c['params']),expected['params'])
        self.assertEqual([s['profile'] for s in c['sections']],expected['profiles'])
        self.assertEqual([s['points'] for s in c['surfaces']],expected['surfaces'])
        section=next(s for s in c['sections'] if s['surface']==0 and s['index']==1)
        self.assertTrue(section['cstFitAllowed']);self.assertEqual(section['cst']['upper'],expected['upper']);self.assertEqual(section['cst']['lower'],expected['lower'])

    def reopened_original(self,gid):
        path=self.path/'original-reference.vsp3';v=self.v
        v.WriteVSPFile(str(path),v.SET_ALL);v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        return self.original(gid)

    def test_fuselage_and_stack_fit_coefficients_and_degrees_match_original_after_reopening(self):
        for kind in ('FUSELAGE','STACK'):
            with self.subTest(kind=kind):
                v=self.v;gid,surf,_=self.fixture(kind)
                initial,_=self.worker(dict(action='state'));section=initial['components'][0]['sections'][1]
                self.assertTrue(section['cstFitAllowed']);self.assertNotIn('cst',section)
                v.FitCSTAirfoil(surf,1,3);expected=self.original(gid)
                state,path=self.worker(dict(action='mutate',operation='cst-fit',geom=gid,surface=0,index=1,degree=3));self.compare(state,gid,expected)
                cold,_=self.worker(dict(action='state'),path);self.compare(cold,gid,self.reopened_original(gid))
                x=v.GetXSec(surf,1);upper=list(expected['upper']);lower=list(expected['lower']);upper[1]*=1.07;lower[2]*=.94
                v.SetUpperCST(x,3,upper);v.SetLowerCST(x,3,lower);expected=self.original(gid)
                state,path=self.worker(dict(action='mutate',operation='cst-coefficients',geom=gid,surface=0,index=1,upper=upper,lower=lower),path);self.compare(state,gid,expected)
                cold,_=self.worker(dict(action='state'),path);self.compare(cold,gid,self.reopened_original(gid))
                for side,direction in [('upper','promote'),('lower','demote')]:
                    getattr(v,direction.title()+'CST'+side.title())(x);expected=self.original(gid)
                    state,path=self.worker(dict(action='mutate',operation='cst-degree',geom=gid,surface=0,index=1,side=side,direction=direction),path);self.compare(state,gid,expected)
                    cold,_=self.worker(dict(action='state'),path);self.compare(cold,gid,self.reopened_original(gid))

    def test_fitting_family_catalogue_matches_original_airfoil_dispatch(self):
        v=self.v
        for shape in AIRFOIL_SHAPES:
            with self.subTest(shape=shape):
                gid,surf,_=self.fixture('STACK',getattr(v,shape));self.assertTrue(fitting_allowed(v,getattr(v,shape)))
                v.FitCSTAirfoil(surf,1,3);v.Update();x=v.GetXSec(surf,1)
                self.assertEqual(v.GetXSecShape(x),v.XS_CST_AIRFOIL)
                self.assertTrue(all(math.isfinite(value) for value in [*v.GetUpperCSTCoefs(x),*v.GetLowerCSTCoefs(x)]))
                manager=v.ErrorMgrSingleton.getInstance();errors=[]
                while manager.GetNumTotalErrors():errors.append(manager.PopLastError().m_ErrorString)
                self.assertEqual(errors,[])

    def test_nonairfoil_fit_and_noncst_edits_reject_without_changing_aircraft(self):
        for kind,shape in [('FUSELAGE',self.v.XS_ELLIPSE),('STACK',self.v.XS_AC25_773),('WING',self.v.XS_EDIT_CURVE)]:
            with self.subTest(kind=kind,shape=shape):
                gid,_,_=self.fixture(kind,shape);before=self.model.read_bytes()
                state,_=self.worker(dict(action='state'));self.assertFalse(state['components'][0]['sections'][1]['cstFitAllowed'])
                requests=[dict(operation='cst-fit',degree=3),dict(operation='cst-degree',side='upper',direction='promote'),dict(operation='cst-coefficients',upper=[.1,.2],lower=[-.1,-.2])]
                for request in requests:
                    existing=set(self.path.glob('*/aircraft.vsp3'))
                    with self.assertRaises(ValueError):self.worker(dict(action='mutate',geom=gid,surface=0,index=1,**request))
                    candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)

    def test_generated_profiles_on_both_native_surfaces_remain_read_only(self):
        script='''void Init(){for(int i=0;i<2;i++){string surface=AddXSecSurf();AppendCustomXSec(surface,XS_CST_AIRFOIL);AppendCustomXSec(surface,XS_CST_AIRFOIL);}}
void InitGui(){}
void UpdateGui(){}
void UpdateSurf(){string geom=GetCurrCustomGeom();for(int i=0;i<2;i++){string surface=GetXSecSurf(geom,i);SetCustomXSecLoc(GetXSec(surface,0),vec3d(0,i*3,0));SetCustomXSecLoc(GetXSec(surface,1),vec3d(2,i*3,0));}SkinXSecSurf();}
'''
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',name='Generated CST surfaces',content=base64.b64encode(script.encode()).decode()))
        c=next(c for c in state['components'] if c['name']=='Generated CST surfaces')
        self.assertEqual({s['surface'] for s in c['sections']},{0,1})
        for section in c['sections']:
            self.assertTrue(section['generated']);self.assertFalse(section['cstFitAllowed']);self.assertIn('cst',section)
        for surface in (0,1):
            before=path.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,'generated|script'):
                self.worker(dict(action='mutate',operation='cst-degree',geom=c['id'],surface=surface,index=0,side='upper',direction='promote'),path)
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before);self.assertEqual(path.read_bytes(),before)

    def test_saved_body_coefficient_locks_still_reject_cst_edits(self):
        v=self.v;gid,surf,_=self.fixture('FUSELAGE');v.FitCSTAirfoil(surf,1,3);v.Update();x=v.GetXSec(surf,1)
        upper=list(v.GetUpperCSTCoefs(x));lower=list(v.GetLowerCSTCoefs(x));pid=v.GetXSecParm(x,'Au_1');v.WriteVSPFile(str(self.model),v.SET_ALL)
        _,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[pid],locked=True));before=path.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
        upper[1]*=1.1
        with self.assertRaisesRegex(ValueError,'locked'):
            self.worker(dict(action='mutate',operation='cst-coefficients',geom=gid,surface=0,index=1,upper=upper,lower=lower),path)
        candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before);self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
