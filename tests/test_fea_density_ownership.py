"""Structural mesh sizing metadata belongs only to native structures."""
import sys
import unittest
import test_native
import native_fea_sizing
from native_worker import parameter,errors

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class FeaDensityOwnership(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_user_names_open_edit_and_reopen_alongside_real_structure(self):
        v=self.v;v.AddFeaStruct(self.gid);users=[]
        for name,group in [('BaseLen','FEAGridDensity'),('BaseAbsRel','FEAGridDensity'),('MinFrac','FEAGridDensity'),('MaxGap','FEAGridDensity'),('ConvertToQuadsFlag','Global'),('CADLenUnit','ExportFEA')]:
            pid=v.AddUserParm(v.PARM_DOUBLE_TYPE,name,group);v.SetParmValUpdate(pid,1.25);users.append(pid)
            field=parameter(v,pid)
            for key in ('label','choices','readOnlyReason'):self.assertNotIn(key,field)
            self.assertEqual(native_fea_sizing.reason(v,pid),'')
            self.assertIsNone(native_fea_sizing.study_priority(v,pid));errors(v)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        state,_=self.worker(dict(action='state'));surfaces=[c['surfaces'] for c in state['components']]
        path=self.model
        for pid in users:
            state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=2.75),path)
            cold,_=self.worker(dict(action='state'),path)
            for data in (state,cold):
                actual=next(p for p in data['tools']['userParameters'] if p['id']==pid)
                self.assertEqual(actual['value'],2.75)
                for key in ('label','choices','readOnlyReason'):self.assertNotIn(key,actual)
                self.assertEqual([c['surfaces'] for c in data['components']],surfaces)
        self.assertEqual(self.model.read_bytes(),before)

    def test_every_real_structure_keeps_basis_and_follower_guards(self):
        v=self.v
        for geom in (self.gid,v.AddGeom('POD')):
            index=v.AddFeaStruct(geom);sid=v.GetFeaStructID(geom,index)
            basis=v.FindParm(sid,'BaseAbsRel','FEAGridDensity')
            for mode,follower in ((v.ABS,'BaseLenFrac'),(v.REL,'BaseLen')):
                v.SetParmValUpdate(basis,mode)
                field=parameter(v,basis)
                self.assertEqual([c['value'] for c in field['choices']],[v.ABS,v.REL])
                pid=v.FindParm(sid,follower,'FEAGridDensity')
                self.assertTrue(native_fea_sizing.reason(v,pid));self.assertTrue(parameter(v,pid)['readOnly'])
                with self.assertRaises(ValueError):native_fea_sizing.validate_parameter(v,pid)
                self.assertEqual(native_fea_sizing.study_priority(v,basis),-12)
                self.assertIn(pid,native_fea_sizing.study_metadata(v))
                errors(v)

    def test_nested_native_mesh_and_cad_settings_keep_named_choices(self):
        v=self.v;index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index)
        for name,group,label in [('ConvertToQuadsFlag','Global','Element shapes'),('CADLenUnit','ExportFEA','CAD file length units')]:
            pid=v.FindParm(sid,name,group);field=parameter(v,pid)
            self.assertTrue(native_fea_sizing.owns(v,pid))
            self.assertEqual(field['label'],label);self.assertTrue(field['choices'])
        errors(v)
