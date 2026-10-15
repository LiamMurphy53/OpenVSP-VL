"""Original script slider declarations and native setters survive worker reloads."""
import sys
import unittest
import test_native
import test_custom_scripts
import test_custom_bindings


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use native Python 3.11.')
class CustomSliders(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    template=test_custom_scripts.CustomScripts.template
    import_component=test_custom_scripts.CustomScripts.import_component
    fields=test_custom_scripts.CustomScripts.fields
    compare_box=test_custom_scripts.CustomScripts.compare_box
    rejected_file_is_unchanged=test_custom_scripts.CustomScripts.rejected_file_is_unchanged

    def test_script_ranges_and_native_geometry_survive_reopening(self):
        text=self.template().replace('GDEV_SLIDER_ADJ_RANGE_INPUT, "Length"  ', 'GDEV_SLIDER_ADJ_RANGE_INPUT, "Length", "", "", 3.125 ')
        text=text.replace('GDEV_SLIDER_ADJ_RANGE_INPUT, "Width"  ', 'GDEV_SLIDER_INPUT, "Width", "", "", 2.0 ')
        state,path,c=self.import_component(text);fields=self.fields(c)
        self.assertEqual(fields['Length']['customSlider']['range'],3.125)
        self.assertTrue(fields['Length']['customSlider']['adjustable'])
        self.assertEqual(fields['Width']['customSlider']['range'],2.0)
        self.assertFalse(fields['Width']['customSlider']['adjustable'])
        key=fields['Length']['customSlider']['key']
        state,path=self.worker(dict(action='mutate',operation='parameter',id=fields['Length']['id'],value=7),path)
        c=next(c for c in state['components'] if c['name']=='Custom test')
        self.compare_box(c,path,7)
        cold,_=self.worker(dict(action='state'),path)
        reopened=next(row for row in cold['components'] if row['id']==c['id'])
        self.assertEqual(self.fields(reopened)['Length']['customSlider']['key'],key)
        self.assertEqual(c['surfaces'],reopened['surfaces'])

    def test_external_slider_uses_original_owner_and_default_range(self):
        parent,child,state,path,_=test_custom_bindings.ExternalCustomBindings.fixture(self)
        control=next(c for c in child['customExternalControls'] if c['parameter']['label']=='Parent length')
        p=control['parameter'];self.assertEqual(p['customSlider']['range'],10)
        self.assertFalse(p['customSlider']['adjustable'])
        self.assertEqual(p['customSlider']['key'],f'{child["id"]}:{control["index"]}:{p["id"]}')
        state,path=self.worker(dict(action='mutate',operation='custom-control-parameter',geom=child['id'],index=control['index'],id=p['id'],value=8),path)
        actual=next(c for c in state['components'] if c['id']==parent)
        self.assertEqual(next(x['value'] for x in actual['params'] if x['id']==p['id']),8)
        self.assertNotIn(p['id'],{x['id'] for x in next(c for c in state['components'] if c['id']==child['id'])['params']})
        state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[p['id']],locked=True),path)
        self.rejected_file_is_unchanged(dict(action='mutate',operation='custom-control-parameter',geom=child['id'],index=control['index'],id=p['id'],value=9),path)
