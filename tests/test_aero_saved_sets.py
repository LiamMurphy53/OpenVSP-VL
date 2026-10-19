"""Saved aero set selectors use actual current native sets, not guessed slots."""
import sys
import unittest
import test_native
from native_worker import parameter

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class SavedAeroSets(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_named_set_selection_edit_reopen_and_renaming(self):
        v=self.v;cid=v.FindContainer('VSPAEROSettings',0)
        v.SetSetName(3,'Main aircraft');v.SetSetFlag(self.gid,3,True)
        v.SetSetName(4,'Main aircraft') # Duplicate names still have distinct indices.
        v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        for name,value in [('GeomSet',3),('ThinGeomSet',4),('MassSet',3),('MassDegenSet',-1)]:
            with self.subTest(name=name):
                pid=v.FindParm(cid,name,'VSPAERO');field=parameter(v,pid)
                self.assertEqual([c['value'] for c in field['choices']],list(range(-1,v.GetNumSets())))
                self.assertEqual(field['choices'][0],dict(value=-1,label='None'))
                self.assertIn(dict(value=3,label='Main aircraft · 3'),field['choices'])
                self.assertIn(dict(value=4,label='Main aircraft · 4'),field['choices'])
                state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value))
                cold,_=self.worker(dict(action='state'),path)
                for data in (state,cold):
                    group=next(c for c in data['tools']['globalSettings'] if c['name']=='VSPAEROSettings')
                    actual=next(p for p in group['params'] if p['id']==pid)
                    self.assertEqual(actual['value'],value);self.assertEqual(actual['choices'],field['choices'])
        v.SetSetName(3,'Renamed airframe')
        self.assertIn(dict(value=3,label='Renamed airframe · 3'),parameter(v,v.FindParm(cid,'GeomSet','VSPAERO'))['choices'])
        self.assertEqual(self.model.read_bytes(),before)

    def test_missing_slots_reject_and_legacy_value_remains_visible_for_repair(self):
        v=self.v;pid=v.FindParm(v.FindContainer('VSPAEROSettings',0),'GeomSet','VSPAERO')
        before=self.model.read_bytes()
        for value in (v.GetNumSets(),1000,-2,3.5,True,None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='parameter',id=pid,value=value))
            self.assertEqual(self.model.read_bytes(),before)
        v.SetParmValUpdate(pid,1000);v.WriteVSPFile(str(self.model),v.SET_ALL)
        legacy=self.model.read_bytes();state,_=self.worker(dict(action='state'))
        group=next(c for c in state['tools']['globalSettings'] if c['name']=='VSPAEROSettings')
        field=next(p for p in group['params'] if p['id']==pid)
        self.assertIn(dict(value=1000.0,label='Unavailable native set · 1000.0'),field['choices'])
        state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=0))
        self.assertEqual(self.model.read_bytes(),legacy)
        user=v.AddUserParm(v.PARM_INT_TYPE,'GeomSet','VSPAERO')
        self.assertNotIn('choices',parameter(v,user))
