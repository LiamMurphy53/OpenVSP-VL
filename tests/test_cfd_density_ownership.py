"""CFD metadata must not break unrelated native parameters sharing its names."""
import sys
import unittest
import test_native
import native_cfd_density
from native_worker import parameter,errors

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class DensityOwnership(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_same_named_user_parameters_open_edit_and_reopen_without_native_errors(self):
        v=self.v;users=[]
        for name in ('BaseLen','BaseAbsRel','MaxFarGap'):
            pid=v.AddUserParm(v.PARM_DOUBLE_TYPE,name,'CFDGridDensity')
            v.SetParmValUpdate(pid,1.25);users.append(pid)
            field=parameter(v,pid)
            for key in ('label','choices','readOnlyReason'):self.assertNotIn(key,field)
            self.assertEqual(native_cfd_density.reason(v,pid),'')
            self.assertIsNone(native_cfd_density.study_priority(v,pid))
            errors(v)
        v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        original,_=self.worker(dict(action='state'))
        path=self.model
        for pid in users:
            state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=2.75),path)
            cold,_=self.worker(dict(action='state'),path)
            for data in (state,cold):
                field=next(p for p in data['tools']['userParameters'] if p['id']==pid)
                self.assertEqual(field['value'],2.75)
                for key in ('label','choices','readOnlyReason'):self.assertNotIn(key,field)
                self.assertEqual([c['surfaces'] for c in data['components']],[c['surfaces'] for c in original['components']])
        self.assertEqual(self.model.read_bytes(),before)

    def test_real_native_density_keeps_driver_choices_follower_guards_and_study_priority(self):
        v=self.v;cid=v.FindContainer('CFDGridDensity',0)
        basis=v.FindParm(cid,'BaseAbsRel','CFDGridDensity')
        v.SetParmValUpdate(basis,v.ABS)
        follower=v.FindParm(cid,'BaseLenFrac','CFDGridDensity')
        self.assertEqual([c['value'] for c in parameter(v,basis)['choices']],[v.ABS,v.REL])
        self.assertTrue(native_cfd_density.reason(v,follower))
        self.assertTrue(parameter(v,follower)['readOnly'])
        self.assertEqual(native_cfd_density.study_priority(v,basis),-12)
        errors(v)

    def test_custom_script_can_use_colliding_group_and_parameter_for_real_geometry(self):
        import base64
        from vsp_runtime import distribution
        script=(distribution()/'CustomScripts/Box.vsppart').read_text().replace('"Length", "Design"','"BaseLen", "CFDGridDensity"')
        state,path=self.worker(dict(action='mutate',operation='geometry-import',format='CUSTOM_SCRIPT',name='Custom density names',content=base64.b64encode(script.encode()).decode()))
        gid=state['changed'];component=next(c for c in state['components'] if c['id']==gid)
        field=next(p for p in component['params'] if p['name']=='BaseLen' and p['rawGroup']=='CFDGridDensity')
        self.assertFalse(field.get('readOnly',False));self.assertNotIn('choices',field)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=field['id'],value=8),path)
        cold,_=self.worker(dict(action='state'),path)
        v=self.v;v.ClearVSPModel();reference=v.AddGeom('Box')
        v.SetParmValUpdate(reference,'Length','Design',8)
        for data in (state,cold):
            custom=next(c for c in data['components'] if c['id']==gid)
            self.assertEqual(next(p for p in custom['params'] if p['id']==field['id'])['value'],8)
            self.assertEqual(len(custom['surfaces']),v.GetTotalNumSurfs(reference))
            for surface in custom['surfaces']:
                i=surface['index'];u,w=v.GetUWTess01(reference,i%v.GetNumMainSurfs(reference))
                expected=[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(reference,i,[a for a in u for _ in w],[b for _ in u for b in w])]
                self.assertEqual(surface['points'],expected)
