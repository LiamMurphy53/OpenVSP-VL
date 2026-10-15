"""Tool-menu section copies use the same original clipboard as Properties."""
import base64
import unittest
import test_native
import test_custom_scripts

class SectionCopyRoutes(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template

    def compare_routes(self,source,target,surface,model):
        common=dict(action='mutate',operation='section-copy-from',geom=target,surface=0,index=1)
        legacy,saved=self.worker(dict(**common,sourceGeom=source,sourceSurface=surface,sourceIndex=1),model)
        menu,path=self.worker(dict(**common,source=dict(kind='section',geom=source,surface=surface,index=1),curveOnly=False),model)
        cold_reference=self.worker(dict(action='state'),saved)[0]
        for state,reference in [(menu,legacy),(self.worker(dict(action='state'),path)[0],cold_reference)]:
            ref=next(c for c in reference['components'] if c['id']==target)
            actual=next(c for c in state['components'] if c['id']==target)
            self.assertEqual(actual['surfaces'],ref['surfaces'])
            self.assertEqual(actual['sections'][1]['profile'],ref['sections'][1]['profile'])
            values=lambda c:sorted((p['rawGroup'],p['name'],p['value'],p['min'],p['max']) for p in c['params'])
            self.assertEqual(values(actual),values(ref))
        return menu,path

    def test_cross_family_menu_copies_match_original_sdk(self):
        v=self.v
        for kind in ('FUSELAGE','WING','PROP'):
            with self.subTest(kind=kind):
                v.ClearVSPModel();source=v.AddGeom('STACK');target=v.AddGeom(kind)
                xs=v.GetXSecSurf(source,0);v.ChangeXSecShape(xs,1,v.XS_ELLIPSE)
                x=v.GetXSec(xs,1);v.SetParmVal(v.GetXSecParm(x,'Ellipse_Width'),2.5);v.SetParmVal(v.GetXSecParm(x,'Ellipse_Height'),1.25)
                v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                v.CopyXSec(source,1);v.PasteXSec(target,1);v.Update();reference=self.path/'reference.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
                expected,_=self.worker(dict(action='state'),reference)
                actual,_=self.compare_routes(source,target,0,self.model)
                self.assertEqual(next(c for c in actual['components'] if c['id']==target)['surfaces'],next(c for c in expected['components'] if c['id']==target)['surfaces'])

    def test_second_generated_surface_copies_match_properties_and_persist(self):
        v=self.v;text=self.template('BoxGroup')
        old='BuildBox( xsec_surf, length_val, width_val, height_val );'
        self.assertIn(old,text)
        text=text.replace(old,old+'\nstring second=AddXSecSurf();BuildBox(second,length_val,2.5*width_val,1.5*height_val);')
        state,model=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',name='Two native profiles',content=base64.b64encode(text.encode()).decode()))
        source=next(c for c in state['components'] if c['name']=='Two native profiles')
        self.assertEqual({s['surface'] for s in source['sections']},{0,1})
        first=next(s for s in source['sections'] if s['surface']==0 and s['index']==1)
        second=next(s for s in source['sections'] if s['surface']==1 and s['index']==1)
        self.assertNotEqual(first['profile'],second['profile'])
        actual,_=self.compare_routes(source['id'],self.gid,1,model)
        target=next(c for c in actual['components'] if c['id']==self.gid)
        self.assertEqual(target['sections'][1]['shape'],second['shape'])
        self.assertEqual(next(c for c in actual['components'] if c['id']==source['id'])['surfaces'],source['surfaces'])
