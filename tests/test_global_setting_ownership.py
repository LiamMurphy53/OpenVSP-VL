"""Unrelated native parameter names cannot route edits to global managers."""
import sys
import unittest
import test_native
import native_parasite_controls as parasite
import native_wave_controls as wave
import native_export_controls as exports
from native_worker import parameter,errors

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class GlobalSettingOwnership(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_unrelated_unit_and_reference_edits_preserve_global_settings_and_geometry(self):
        v=self.v;users=[]
        cases=[('ParasiteDrag','VinfUnitType',4.5),('ParasiteDrag','TempUnit',4.5),('ParasiteDrag','RefFlag',1),('ParasiteDrag','ExcresVal',2.75),('WaveDrag','RefFlag',1),('WaveDrag','UseMode',1),('STEPSettings','LenUnit',4.5),('STEPSettings','ToCubicTol',2.75)]
        for group,name,value in cases:
            pid=v.AddUserParm(v.PARM_DOUBLE_TYPE,name,group);users.append((pid,value))
            field=parameter(v,pid)
            for key in ('label','choices','readOnlyReason'):self.assertNotIn(key,field)
            for module in (parasite,wave,exports):
                self.assertEqual(module.reason(v,pid),'');self.assertIsNone(module.study_priority(v,pid))
            self.assertFalse(parasite.set_parameter(v,pid,value));errors(v)
        v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        initial,_=self.worker(dict(action='state'));path=self.model
        def globals(data):return {c['id']:{p['id']:p['value'] for p in c['params']} for c in data['tools']['globalSettings']}
        original=globals(initial);geometry=[c['surfaces'] for c in initial['components']]
        for pid,value in users:
            state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
            cold,_=self.worker(dict(action='state'),path)
            for data in (state,cold):
                field=next(p for p in data['tools']['userParameters'] if p['id']==pid)
                self.assertEqual(field['value'],value)
                for key in ('label','choices','readOnlyReason'):self.assertNotIn(key,field)
                self.assertEqual(globals(data),original)
                self.assertEqual([c['surfaces'] for c in data['components']],geometry)
        self.assertEqual(self.model.read_bytes(),before)

    def test_original_manager_controls_keep_choices_and_reference_guards(self):
        v=self.v
        for container,group,name in [('ParasiteDragSettings','ParasiteDrag','VinfUnitType'),('WaveDragSettings','WaveDrag','RefFlag'),('Vehicle','STEPSettings','LenUnit')]:
            owner=v.GetVehicleID() if container=='Vehicle' else v.FindContainer(container,0)
            field=parameter(v,v.FindParm(owner,name,group));self.assertTrue(field['choices']);self.assertTrue(field['label'])
        for module,container,group in [(parasite,'ParasiteDragSettings','ParasiteDrag'),(wave,'WaveDragSettings','WaveDrag')]:
            pid=v.FindParm(v.FindContainer(container,0),'RefFlag',group)
            with self.assertRaisesRegex(ValueError,'reference wing'):module.validate_parameter(v,pid,1)
        errors(v)

    def test_custom_geometry_unit_name_edits_geometry_without_changing_global_units(self):
        import base64
        from vsp_runtime import distribution
        script=(distribution()/'CustomScripts/Box.vsppart').read_text().replace('"Length", "Design"','"VinfUnitType", "ParasiteDrag"')
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',name='Unit-name box',content=base64.b64encode(script.encode()).decode()))
        gid=state['changed'];custom=next(c for c in state['components'] if c['id']==gid)
        field=next(p for p in custom['params'] if p['name']=='VinfUnitType' and p['rawGroup']=='ParasiteDrag')
        self.assertNotIn('choices',field)
        def unit(data):
            group=next(c for c in data['tools']['globalSettings'] if c['name']=='ParasiteDragSettings')
            return next(p['value'] for p in group['params'] if p['name']=='VinfUnitType')
        before=unit(state)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=field['id'],value=8),path)
        cold,_=self.worker(dict(action='state'),path)
        v=self.v;v.ClearVSPModel();reference=v.AddGeom('Box');v.SetParmValUpdate(reference,'Length','Design',8)
        for data in (state,cold):
            self.assertEqual(unit(data),before)
            custom=next(c for c in data['components'] if c['id']==gid)
            self.assertEqual(next(p for p in custom['params'] if p['id']==field['id'])['value'],8)
            self.assertEqual(len(custom['surfaces']),v.GetTotalNumSurfs(reference))
            for surface in custom['surfaces']:
                i=surface['index'];u,w=v.GetUWTess01(reference,i%v.GetNumMainSurfs(reference))
                expected=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,i,[a for a in u for _ in w],[b for _ in u for b in w])]
                self.assertEqual(surface['points'],expected)
