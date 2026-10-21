"""Pending UI set choices follow native contents and saved workspace history."""
import unittest
import test_session
import native_service as service

class SetIdentity(test_session.NativeSession):
    def setUp(self):
        super().setUp();self.old_ids=service.SET_IDENTITIES;service.SET_IDENTITIES={}
    def tearDown(self):
        service.SET_IDENTITIES=self.old_ids;super().tearDown()
    def test_empty_duplicate_sets_follow_moves_and_cold_undo_redo(self):
        v=self.v
        for i in (3,4):v.SetSetName(i,'Same')
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        before=self.model.read_bytes();initial=service.state();ids=[s['identity'] for s in initial['tools']['sets']]
        order=list(range(3,v.GetNumSets()));order[0],order[1]=order[1],order[0]
        moved=service.mutation(dict(operation='set-reorder',order=order,revision=service.REVISION))
        expected=[*ids[:3],*(ids[i] for i in order)]
        self.assertEqual([s['identity'] for s in moved['tools']['sets']],expected)
        after=self.model.read_bytes();service.SET_IDENTITIES={};self.assertTrue(service.restore_session())
        self.assertEqual([s['identity'] for s in service.state()['tools']['sets']],expected)
        undo=service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),before)
        self.assertEqual([s['identity'] for s in undo['tools']['sets']],ids)
        redo=service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),after)
        self.assertEqual([s['identity'] for s in redo['tools']['sets']],expected)
    def test_removed_and_recreated_slot_gets_new_identity(self):
        service.state()
        initial=service.mutation(dict(operation='set-count',count=21,revision=service.REVISION))
        old=initial['tools']['sets'][-1]['identity'];count=initial['tools']['setConfig']['count']
        service.mutation(dict(operation='set-count',count=count-1,revision=service.REVISION))
        grown=service.mutation(dict(operation='set-count',count=count,revision=service.REVISION))
        self.assertNotEqual(grown['tools']['sets'][-1]['identity'],old)
        service.undo(revision=service.REVISION);restored=service.undo(revision=service.REVISION)
        self.assertEqual(restored['tools']['sets'][-1]['identity'],old)

    def test_first_identity_save_preserves_recovery_warning(self):
        service.SESSION_WARNING='Preserved recovery record.'
        state=service.state()
        self.assertIn('Preserved recovery record.',state['warnings'])
        self.assertEqual(service.SESSION_WARNING,'Preserved recovery record.')
