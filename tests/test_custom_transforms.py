"""Original section-global transforms regenerate through embedded custom scripts."""
import base64
import shutil
import sys
import unittest
import test_native
from native_custom_scripts import import_script

SCRIPT='''void Init(){
 string p=AddParm(PARM_DOUBLE_TYPE,"Offset","Design");SetParmValLimits(p,2,-20,20);
 p=AddParm(PARM_DOUBLE_TYPE,"Angle","Design");SetParmValLimits(p,25,-90,90);
 for(int i=0;i<2;i++){string s=AddXSecSurf();AppendCustomXSec(s,XS_POINT);string x=AppendCustomXSec(s,XS_CIRCLE);SetCustomXSecLoc(x,vec3d(2,0,0));SetParmVal(GetXSecParm(x,"Circle_Diameter"),1+i);x=AppendCustomXSec(s,XS_POINT);SetCustomXSecLoc(x,vec3d(5,0,0));}
}
void InitGui(){AddGui(GDEV_TAB,"Design");AddGui(GDEV_SLIDER_INPUT,"Offset","Offset","Design");AddGui(GDEV_SLIDER_INPUT,"Angle","Angle","Design");}
void UpdateGui(){}
void UpdateSurf(){string g=GetCurrCustomGeom();Matrix4d m;m.rotateZ(GetParmVal(GetParm(g,"Angle","Design")));m.translatef(GetParmVal(GetParm(g,"Offset","Design")),0,0);SetXSecSurfGlobalXForm(GetXSecSurf(g,0),m);Matrix4d n=GetXSecSurfGlobalXForm(GetXSecSurf(g,0));n.translatef(0,5,0);SetXSecSurfGlobalXForm(GetXSecSurf(g,1),n);SkinXSecSurf();}
'''


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class CustomSurfaceTransforms(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_embedded_surface_transforms_match_original_and_regenerate_after_relocation(self):
        v=self.v
        original=self.path/'original';original.mkdir();source=original/'transform.vsppart';source.write_text(SCRIPT)
        reference=import_script(v,source,'Original transform reference');v.Update()
        def samples(gid):
            out=[]
            for i in range(v.GetTotalNumSurfs(gid)):
                u,w=v.GetUWTess01(gid,i%v.GetNumMainSurfs(gid))
                out.append([[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(gid,i,[a for a in u for _ in w],[b for _ in u for b in w])])
            return out
        expected={}
        for offset,angle in [(2.,25.),(-3.,-35.)]:
            v.SetParmVal(reference,'Offset','Design',offset);v.SetParmValUpdate(reference,'Angle','Design',angle);expected[(offset,angle)]=samples(reference)
        self.assertNotEqual(expected[(2.,25.)],expected[(-3.,-35.)])
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',name='Transformed custom surfaces',content=base64.b64encode(SCRIPT.encode()).decode()))
        component=next(c for c in state['components'] if c['name']=='Transformed custom surfaces');gid=component['id']
        self.assertEqual(len(component['surfaces']),2)
        self.assertEqual([s['points'] for s in component['surfaces']],expected[(2.,25.)])
        source.unlink()
        for folder in self.path.rglob('component-package'):
            if folder.is_dir():shutil.rmtree(folder)
        fields={p['name']:p['id'] for p in component['params'] if p['rawGroup']=='Design'}
        state,path=self.worker(dict(action='mutate',operation='parameter',id=fields['Offset'],value=-3.),path)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=fields['Angle'],value=-35.),path)
        before=path.read_bytes()
        for request in [dict(action='state'),dict(action='state')]:
            state,_=self.worker(request,path);current=next(c for c in state['components'] if c['id']==gid)
            self.assertEqual([s['points'] for s in current['surfaces']],expected[(-3.,-35.)])
            self.assertEqual(len({s['surface'] for s in current['sections']}),2)
            self.assertTrue(all(s['generated'] for s in current['sections']))
        self.assertEqual(path.read_bytes(),before)
