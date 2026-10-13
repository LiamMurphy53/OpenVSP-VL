"""CST degree changes retain native coefficient IDs and use original engine math."""
import sys,unittest
import test_native

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class CSTIdentity(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self,bor,kind="WING"):
        v=self.v;v.ClearVSPModel();g=v.AddGeom('BODYOFREVOLUTION' if bor else kind)
        if bor:
            v.ChangeBORXSecShape(g,v.XS_FOUR_SERIES);v.FitBORAfCST(g,8);params=v.GetGeomParmIDs(g)
        else:
            v.FitCSTAirfoil(v.GetXSecSurf(g,0),1,8);params=v.GetXSecParmIDs(v.GetXSec(v.GetXSecSurf(g,0),1))
        v.Update();pid=next(p for p in params if v.GetParmName(p)=='Au_8' and v.GetParmGroupName(p)=='UpperCoeff')
        v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Retained coefficient',pid);v.WriteVSPFile(str(self.model),v.SET_ALL)
        return g,pid

    def test_degree_and_coefficient_changes_preserve_native_ids_and_saved_geometry(self):
        v=self.v
        for kind in ('WING','PROP','BODYOFREVOLUTION'):
            bor=kind=='BODYOFREVOLUTION'
            for mode in ('promote','demote','coefficients'):
                with self.subTest(kind=kind,mode=mode):
                    g,pid=self.fixture(bor,kind);prefix='bor-cst-' if bor else 'cst-';request=dict(action='mutate',geom=g)
                    if not bor:request['index']=1
                    x=g if bor else v.GetXSec(v.GetXSecSurf(g,0),1)
                    if mode=='coefficients':
                        upper=[.1,.2,.3,.2,.1];lower=[-.1,-.2,-.1,-.05]
                        request.update(operation=prefix+mode,upper=upper,lower=lower)
                        (v.SetBORUpperCST if bor else v.SetUpperCST)(x,4,upper);(v.SetBORLowerCST if bor else v.SetLowerCST)(x,3,lower)
                    else:
                        request.update(operation=prefix+'degree',side='upper',direction=mode)
                        getattr(v,mode.title()+('BORCST' if bor else 'CST')+'Upper')(x)
                    v.Update();reference=self.path/'reference.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
                    expected,_=self.worker(dict(action='state'),reference)
                    state,path=self.worker(request);cold,_=self.worker(dict(action='state'),path)
                    for result in (state,cold):
                        self.assertEqual(result['components'][0]['surfaces'],expected['components'][0]['surfaces'])
                        self.assertEqual(next(a['values'] for a in result['tools']['attributes'] if a['name']=='Retained coefficient'),[pid])
                        fields=result['components'][0]['params']
                        self.assertIn(pid,{p['id'] for p in fields})

    def test_invalid_coefficients_and_fitting_degrees_preserve_candidate(self):
        for kind in ('WING','PROP','BODYOFREVOLUTION'):
            bor=kind=='BODYOFREVOLUTION'
            g,pid=self.fixture(bor,kind);prefix='bor-cst-' if bor else 'cst-';owner=dict(geom=g,**({} if bor else dict(index=1)))
            requests=[dict(operation=prefix+'coefficients',upper=[1e12+1],lower=[0]),dict(operation=prefix+'coefficients',upper=[0],lower=[-1e12-1])]
            requests += [dict(operation=prefix+'fit',degree=d) for d in (True,False,1.5,0,21,None)]
            before=self.model.read_bytes()
            for request in requests:
                existing=set(self.path.glob('*/aircraft.vsp3'))
                with self.assertRaises(ValueError):self.worker(dict(action='mutate',**owner,**request))
                candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)

if __name__=='__main__':unittest.main()
