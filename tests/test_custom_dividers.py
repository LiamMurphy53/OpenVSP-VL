"""Native script divider context and order survive geometry edits/reopening."""
import base64
import unittest
import test_native
import test_custom_scripts
import test_custom_bindings

class CustomDividers(unittest.TestCase):
    setUpClass=classmethod(test_custom_scripts.CustomScripts.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template
    import_component=test_custom_scripts.CustomScripts.import_component
    fields=test_custom_scripts.CustomScripts.fields
    compare_box=test_custom_scripts.CustomScripts.compare_box

    def script(self):
        text=self.template().replace('GDEV_DIVIDER_BOX, "Design"','GDEV_DIVIDER_BOX, "Baseline dimensions"')
        text=text.replace('WidthSlider = AddGui','AddGui(GDEV_DIVIDER_BOX,"Section <width> & height");\n WidthSlider = AddGui')
        text=text.replace('SquareButton = AddGui','AddGui(GDEV_SCROLL_TAB,"Coupling");\n AddGui(GDEV_DIVIDER_BOX,"Dimension coupling");\n SquareButton = AddGui')
        return text

    def test_own_dividers_and_native_order_survive_edit_and_reopening(self):
        _,path,c=self.import_component(self.script());fields=self.fields(c);gid=c['id']
        self.assertEqual(fields['Length']['customDivider']['label'],'Baseline dimensions')
        self.assertEqual(fields['Width']['customDivider']['label'],'Section <width> & height')
        self.assertEqual(fields['Width']['customDivider'],fields['Height']['customDivider'])
        self.assertEqual(fields['SquareFlag']['customDivider']['label'],'Dimension coupling')
        self.assertEqual(fields['SquareFlag']['customTab'],'Coupling')
        order=[fields[n]['customControlOrder'] for n in ('Length','Width','Height','SquareFlag')];self.assertEqual(order,sorted(order));self.assertEqual(len(set(order)),4)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=fields['Length']['id'],value=9),path);actual=next(c for c in state['components'] if c['id']==gid);self.compare_box(actual,path,9)
        reopened,_=self.worker(dict(action='state'),path);cold=next(c for c in reopened['components'] if c['id']==gid)
        self.assertEqual(cold['surfaces'],actual['surfaces'])
        for name,p in self.fields(actual).items():
            q=self.fields(cold)[name];self.assertEqual((q['id'],q.get('customDivider'),q.get('customControlOrder'),q['rawGroup']),(p['id'],p.get('customDivider'),p.get('customControlOrder'),p['rawGroup']))

    def test_external_dividers_use_script_context_not_parent_context(self):
        parent,_,_,_,text=test_custom_bindings.ExternalCustomBindings.fixture(self)
        text=text.replace('ParentSelector=AddGui','AddGui(GDEV_TAB,"Parent setup");AddGui(GDEV_DIVIDER_BOX,"Array counts");ParentSelector=AddGui')
        text=text.replace('ParentLength=AddGui','AddGui(GDEV_DIVIDER_BOX,"Parent dimensions");ParentLength=AddGui')
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',name='Grouped external controls',parent=parent,content=base64.b64encode(text.encode()).decode()))
        child=next(c for c in state['components'] if c['name']=='Grouped external controls');gid=child['id'];row,length=child['customExternalControls']
        self.assertEqual(row['parameter']['customDivider']['label'],'Array counts');self.assertEqual(length['parameter']['customDivider']['label'],'Parent dimensions');self.assertEqual(row['tab'],length['tab']);self.assertEqual(row['tab'],'Parent setup');self.assertEqual(row['parameter']['customTab'],'Parent setup');self.assertEqual(length['parameter']['customTabIndex'],length['tabIndex'])
        state,path=self.worker(dict(action='mutate',operation='custom-control-parameter',geom=gid,index=length['index'],id=length['parameter']['id'],value=9),path)
        actual=next(c for c in state['components'] if c['id']==parent);v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();reference=v.AddGeom('BoxGroup');v.SetParmValUpdate(v.FindParm(reference,'Length','Design'),9);v.Update()
        for surface in actual['surfaces']:
            i=surface['index'];u,w=v.GetUWTess01(reference,i%v.GetNumMainSurfs(reference));points=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,i,[a for a in u for _ in w],[b for _ in u for b in w])];self.assertEqual(surface['points'],points)
        reopened,_=self.worker(dict(action='state'),path);self.assertEqual(next(c for c in reopened['components'] if c['id']==gid)['customExternalControls'],next(c for c in state['components'] if c['id']==gid)['customExternalControls'])

    def test_disconnected_inputs_retain_their_native_section_and_order(self):
        _,path,c=self.import_component(self.script());fields=self.fields(c);gid=c['id']
        state,path=self.worker(dict(action='mutate',operation='parameter',id=fields['SquareFlag']['id'],value=1),path)
        actual=next(c for c in state['components'] if c['id']==gid);current=self.fields(actual)
        for name in ('Width','Height'):
            self.assertTrue(current[name]['displayReadOnly'])
            self.assertEqual(current[name]['customDivider'],fields[name]['customDivider'])
            self.assertEqual(current[name]['customControlOrder'],fields[name]['customControlOrder'])
            self.assertEqual(current[name]['group'],fields[name]['group'])
        reopened,_=self.worker(dict(action='state'),path);cold=next(c for c in reopened['components'] if c['id']==gid)
        self.assertEqual(cold['params'],actual['params']);self.assertEqual(cold['surfaces'],actual['surfaces'])
