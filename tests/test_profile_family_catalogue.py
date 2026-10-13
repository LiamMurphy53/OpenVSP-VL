"""Every exposed native profile family retains original sampled geometry."""
import math,sys,unittest
import test_native
from native_special import SHAPES

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class ProfileCatalogue(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_all_profiles_on_all_ordinary_owner_families(self):
        v=self.v
        for kind in ('WING','FUSELAGE','STACK','PROP'):
            for name in SHAPES:
                with self.subTest(kind=kind,profile=name):
                    v.ClearVSPModel();g=v.AddGeom(kind);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                    if kind=='PROP' and name=='XS_POINT':
                        before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
                        with self.assertRaisesRegex(ValueError,'Point profiles on propeller blades'):
                            self.worker(dict(action='mutate',operation='shape',geom=g,surface=0,index=1,shape=v.XS_POINT))
                        candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)
                        continue
                    surf=v.GetXSecSurf(g,0);v.ChangeXSecShape(surf,1,getattr(v,name));v.Update();reference=self.path/'profile-reference.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
                    expected,_=self.worker(dict(action='state'),reference)
                    actual,path=self.worker(dict(action='mutate',operation='shape',geom=g,surface=0,index=1,shape=getattr(v,name)))
                    cold,_=self.worker(dict(action='state'),path)
                    for data in (actual,cold):
                        self.assertEqual(data['components'][0]['sections'][1]['shape'],getattr(v,name))
                        a=data['components'][0]['surfaces'];b=expected['components'][0]['surfaces']
                        self.assertEqual([(s['index'],s['rows'],s['cols'],len(s['points'])) for s in a],[(s['index'],s['rows'],s['cols'],len(s['points'])) for s in b])
                        for surface,other in zip(a,b):
                            for point,q in zip(surface['points'],other['points']):
                                for x,y in zip(point,q):
                                    self.assertTrue(math.isfinite(x) and math.isfinite(y))
                                    self.assertLessEqual(abs(x-y),64*sys.float_info.epsilon*max(1,abs(x),abs(y)))

    def test_propeller_point_insertion_and_profile_copy_preserve_candidate(self):
        v=self.v;v.ClearVSPModel();prop=v.AddGeom('PROP');source=v.AddGeom('STACK');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        requests=[dict(operation='insert-section',geom=prop,surface=0,index=1,shape=v.XS_POINT),dict(operation='section-copy-from',geom=prop,surface=0,index=1,curveOnly=True,source=dict(kind='section',geom=source,surface=0,index=0))]
        before=self.model.read_bytes()
        for request in requests:
            existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,'Point profiles on propeller blades'):self.worker(dict(action='mutate',**request))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)
        state,_=self.worker(dict(action='state'));row=next(c for c in state['components'] if c['id']==prop)
        self.assertNotIn('XS_POINT',row['profileShapes']);self.assertEqual(len(row['profileShapes']),19)

    def test_legacy_propeller_point_record_is_preserved_and_can_be_repaired(self):
        v=self.v;v.ClearVSPModel();prop=v.AddGeom('PROP');surf=v.GetXSecSurf(prop,0);v.ChangeXSecShape(surf,1,v.XS_POINT);v.Update();xid=v.GetXSec(surf,1);v.WriteVSPFile(str(self.model),v.SET_ALL)
        baseline,_=self.worker(dict(action='state'))
        self.assertEqual(baseline['components'][0]['sections'][1]['shape'],v.XS_POINT)
        renamed,path=self.worker(dict(action='mutate',operation='rename',geom=prop,name='Legacy propeller'))
        section=renamed['components'][0]['sections'][1];self.assertEqual(section['id'],xid);self.assertEqual(section['shape'],v.XS_POINT)
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(cold['components'][0]['sections'][1]['shape'],v.XS_POINT)
        repaired,path=self.worker(dict(action='mutate',operation='shape',geom=prop,surface=0,index=1,shape=v.XS_FOUR_SERIES),path)
        self.assertEqual(repaired['components'][0]['sections'][1]['shape'],v.XS_FOUR_SERIES)
        reopened,_=self.worker(dict(action='state'),path)
        self.assertEqual(reopened['components'][0]['surfaces'],repaired['components'][0]['surfaces'])

if __name__=='__main__':unittest.main()
