"""Native aircraft and undo/redo survive a cold server restart."""
import hashlib
import json
import sys
import unittest
import uuid
import test_native
import native_service as service
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeSession(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    def setUp(self):
        test_native.NativeIntegration.setUp(self)
        self.old=service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION,service.SESSION_WARNING
        service.WORK=self.path;service.MODEL=self.model;service.HISTORY=[];service.FUTURE=[];service.REVISION=uuid.uuid4().hex;service.SESSION_WARNING=None
    def tearDown(self):
        service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION,service.SESSION_WARNING=self.old
        test_native.NativeIntegration.tearDown(self)
    def edit(self,value):
        return service.mutation(dict(operation='parameter',id=self.v.FindParm(self.gid,'TotalSpan','WingGeom'),value=value,revision=service.REVISION))
    def test_cold_restart_preserves_native_aircraft_revision_and_both_history_directions(self):
        original=self.model.read_bytes();self.edit(12.);first=self.model.read_bytes();self.edit(18.);second=self.model.read_bytes()
        service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),first);revision=service.REVISION
        service.HISTORY=[];service.FUTURE=[];service.REVISION=uuid.uuid4().hex
        self.assertTrue(service.restore_session());self.assertEqual(service.REVISION,revision);self.assertEqual(len(service.HISTORY),1);self.assertEqual(len(service.FUTURE),1)
        service.undo(redo=True,revision=revision);self.assertEqual(self.model.read_bytes(),second)
        service.undo(revision=service.REVISION);service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),original)
        self.assertTrue(service.restore_session());self.assertFalse(service.HISTORY);self.assertEqual(len(service.FUTURE),2)
        service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),first)
    def test_changed_or_missing_native_snapshot_preserves_recovery_record(self):
        self.edit(12.);saved=(self.path/'session.json').read_bytes();self.model.write_bytes(self.model.read_bytes()+b'\n')
        self.assertFalse(service.restore_session());self.assertEqual(next(self.path.glob('session-recovery-*.json')).read_bytes(),saved);self.assertTrue(service.SESSION_WARNING);self.assertFalse(service.HISTORY)
        service.save_session();data=json.loads((self.path/'session.json').read_text());data['history']=['../../outside.vsp3'];(self.path/'session.json').write_text(json.dumps(data))
        self.assertFalse(service.restore_session());self.assertIn('outside',service.SESSION_WARNING);self.assertFalse(service.HISTORY)

if __name__=='__main__':unittest.main()
