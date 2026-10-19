"""Saved aerodynamic enum controls retain original native identities/values."""
import sys
import unittest
import test_native
from native_worker import parameter

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python runtime.')
class SavedAeroChoices(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_named_native_choices_survive_saved_edit_and_cold_reopen(self):
        v=self.v;cid=v.FindContainer('VSPAEROSettings',0)
        expected={
            'RefFlag':['MANUAL_REF','COMPONENT_REF'],
            'MassSliceDir':['X_DIR','Y_DIR','Z_DIR'],
            'm_PropBladesMode':['VSPAERO_PROP_STATIC','VSPAERO_PROP_UNSTEADY','VSPAERO_PROP_PSEUDO_STEADY'],
            'UnsteadyType':['STABILITY_OFF','STABILITY_DEFAULT','STABILITY_ADJOINT','STABILITY_PITCH','STABILITY_P_ANALYSIS','STABILITY_Q_ANALYSIS','STABILITY_R_ANALYSIS'],
            'StallModel':['STALL_OFF','STALL_ON'],
            'NoiseCalcType':['NOISE_FLYBY','NOISE_FOOTPRINT','NOISE_STEADY'],
            'NoiseUnits':['NOISE_SI','NOISE_ENGLISH']}
        prop=v.AddGeom('PROP');v.SetParmValUpdate(prop,'Y_Rel_Location','XForm',8)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        path=self.model;before=self.model.read_bytes()
        for name,constants in expected.items():
            with self.subTest(name=name):
                pid=v.FindParm(cid,name,'VSPAERO');field=parameter(v,pid)
                codes=[getattr(v,c) for c in constants]
                self.assertEqual([o['value'] for o in field['choices']],codes)
                self.assertTrue(all(o['label'] and o['label']!=str(o['value']) for o in field['choices']))
                state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=codes[-1]),self.model)
                cold,_=self.worker(dict(action='state'),path)
                for data in (state,cold):
                    group=next(c for c in data['tools']['globalSettings'] if c['name']=='VSPAEROSettings')
                    saved=next(p for p in group['params'] if p['id']==pid)
                    self.assertEqual(saved['value'],codes[-1])
                    self.assertEqual(saved['choices'],field['choices'])
                    self.assertEqual(saved['label'],field['label'])
        self.assertEqual(self.model.read_bytes(),before)

    def test_user_parameter_with_same_native_group_and_name_stays_numeric(self):
        v=self.v;pid=v.AddUserParm(v.PARM_INT_TYPE,'NoiseUnits','VSPAERO')
        field=parameter(v,pid)
        self.assertNotIn('choices',field)
        self.assertNotIn('label',field)
