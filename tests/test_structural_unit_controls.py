"""Named structural model-unit controls retain original numeric geometry."""
import sys,unittest
import test_native

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class StructuralUnitControls(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_all_native_model_unit_choices_edit_and_reopen_without_geometry_changes(self):
        v=self.v;v.AddFeaStruct(self.gid);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        pid=v.FindParm(v.GetVehicleID(),'StructModelUnit','FeaStructure')
        initial,_=self.worker(dict(action='state'))
        def field(data):return next(p for g in data['tools']['globalSettings'] for p in g['params'] if p['id']==pid)
        choices=[(v.LEN_MM,'mm'),(v.LEN_CM,'cm'),(v.LEN_M,'m'),(v.LEN_IN,'in'),(v.LEN_FT,'ft'),(v.LEN_YD,'yd'),(v.LEN_UNITLESS,'Unitless')]
        self.assertEqual([(c['value'],c['label']) for c in field(initial)['choices']],choices)
        original=self.model.read_bytes()
        for value,label in choices:
            with self.subTest(unit=label):
                state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value))
                cold,_=self.worker(dict(action='state'),path)
                for data in [state,cold]:
                    self.assertEqual(field(data)['label'],'Structural model length units')
                    self.assertEqual(field(data)['value'],value)
                    self.assertEqual([c['params'] for c in data['components']],[c['params'] for c in initial['components']])
                    self.assertEqual([c['surfaces'] for c in data['components']],[c['surfaces'] for c in initial['components']])
                self.assertEqual(self.model.read_bytes(),original)

    def test_user_parameters_with_unit_names_keep_their_own_controls(self):
        v=self.v;vehicle=v.GetVehicleID()
        real={n:v.GetParmVal(v.FindParm(vehicle,n,'FeaStructure')) for n in ['StructModelUnit','StructUnit']}
        users=[]
        for name in real:
            pid=v.AddUserParm(v.PARM_DOUBLE_TYPE,name,'FeaStructure');v.SetParmValUpdate(pid,7.5);users.append(pid)
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        path=self.model
        for pid in users:
            state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=8.25),path)
            cold,_=self.worker(dict(action='state'),path)
            for data in [state,cold]:
                field=next(p for p in data['tools']['userParameters'] if p['id']==pid)
                self.assertEqual(field['value'],8.25)
                self.assertNotIn('choices',field);self.assertNotIn('label',field)
                global_fields={p['name']:p for g in data['tools']['globalSettings'] if g['name']=='Vehicle' for p in g['params'] if p['rawGroup']=='FeaStructure'}
                self.assertEqual({n:global_fields[n]['value'] for n in real},real)
