"""Custom profile sliders persist through original script-declared driving inputs."""
from pathlib import Path
import unittest
import test_native
import test_studies
import test_custom_scripts
import native_service as service


class SavedCustomProfiles(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template
    import_component=test_custom_scripts.CustomScripts.import_component

    def fixture(self):
        text=self.template().replace('void Init()\n{','void Init()\n{\n string radius=AddParm(PARM_DOUBLE_TYPE,"CornerRadius","Design");SetParmValLimits(radius,.2,0,1);')
        text=text.replace('LengthSlider = AddGui','AddGui(GDEV_SLIDER_INPUT,"Profile corner radius","CornerRadius","Design",.1);\n LengthSlider = AddGui')
        for xsec in ('xsec1','xsec2'):
            old='SetParmVal( GetXSecParm( '+xsec+', "RoundRectXSec_Radius" ), 0.0 );'
            self.assertIn(old,text)
            text=text.replace(old,'SetParmVal( GetXSecParm( '+xsec+', "RoundRectXSec_Radius" ), GetParmVal(GetParm(geom_id,"CornerRadius","Design")) );')
        _,path,c=self.import_component(text);self.model.write_bytes(path.read_bytes());self.gid=c['id']
        return next(r for r in c['customOwnControls'] if r['parameter']['label']=='Profile corner radius')

    def edit(self,row,value):
        return service.mutation(dict(operation='custom-control-parameter',geom=self.gid,index=row['index'],id=row['parameter']['id'],value=value,editGesture='a'*32,revision=service.REVISION))

    def capture(self,path):
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();gid=self.gid
        fields=sorted((v.GetParmGroupName(p),v.GetParmName(p),v.GetParmVal(p)) for p in v.GetGeomParmIDs(gid));profiles=[];surfaces=[]
        for s in range(v.GetNumXSecSurfs(gid)):
            surf=v.GetXSecSurf(gid,s)
            for i in range(v.GetNumXSec(surf)):
                x=v.GetXSec(surf,i)
                profiles.append((s,i,v.GetXSecShape(x),sorted((v.GetParmGroupName(p),v.GetParmName(p),v.GetParmVal(p)) for p in v.GetXSecParmIDs(x))))
        for i in range(v.GetTotalNumSurfs(gid)):
            u,w=v.GetUWTess01(gid,i%v.GetNumMainSurfs(gid));surfaces.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(gid,i,[a for a in u for _ in w],[b for _ in u for b in w])])
        return fields,profiles,surfaces

    def test_saved_profile_driver_matches_original_geometry_history_and_cold_values(self):
        row=self.fixture();before=self.model.read_bytes();base=self.path/'native-before.vsp3';base.write_bytes(before);initial=self.capture(base)
        for value in (.3,.5):state=self.edit(row,value)
        self.assertEqual(len(service.HISTORY),1);final=self.model.read_bytes();actual=self.capture(self.model)
        self.assertNotEqual(actual[2],initial[2],'The driven slider must actually change native surfaces')
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(base));v.Update()
        for value in (.3,.5):v.SetParmValUpdate(row['parameter']['id'],value);v.Update()
        ref=self.path/'native-after.vsp3';v.WriteVSPFile(str(ref),v.SET_ALL)
        self.assertEqual(actual,self.capture(ref))
        for _,section,_,fields in actual[1]:
            if section in (1,2):self.assertIn(('XSecCurve','RoundRectXSec_Radius',.5),fields)
        cold=service.state();c=next(c for c in cold['components'] if c['id']==self.gid)
        current=next(r for r in c['customOwnControls'] if r['index']==row['index'])
        self.assertEqual(current['parameter']['value'],.5);self.assertEqual(current['parameter']['id'],row['parameter']['id']);self.assertFalse(current['parameter'].get('displayReadOnly',False))
        self.assertEqual([s['points'] for s in c['surfaces']],actual[2])
        service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),before);self.assertEqual(self.capture(self.model),initial)
        service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),final);self.assertEqual(self.capture(self.model),actual)

    def test_saved_profile_driver_lock_rejects_edit_and_survives_reopening(self):
        row=self.fixture();self.edit(row,.5);pid=row['parameter']['id']
        service.mutation(dict(operation='property-lock',parameters=[pid],locked=True,revision=service.REVISION))
        before=self.model.read_bytes();history=list(service.HISTORY);cold=service.state()
        self.assertTrue(next(r for c in cold['components'] if c['id']==self.gid for r in c['customOwnControls'] if r['index']==row['index'])['parameter']['userLocked'])
        with self.assertRaisesRegex(ValueError,'locked'):self.edit(row,.7)
        self.assertEqual(self.model.read_bytes(),before);self.assertEqual(service.HISTORY,history)
        service.mutation(dict(operation='property-lock',parameters=[pid],locked=False,revision=service.REVISION));self.edit(row,.7)
        cold=service.state();self.assertEqual(next(r for c in cold['components'] if c['id']==self.gid for r in c['customOwnControls'] if r['index']==row['index'])['parameter']['value'],.7)
