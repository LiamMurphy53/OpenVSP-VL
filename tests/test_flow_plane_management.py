"""Saved plane management preserves survivors and protects native references."""
import unittest
import test_native

class FlowPlaneManagement(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;v.DeleteAllCpSlices();ids=[]
        for i in range(5):
            cid=v.AddCpSlice(v.Y_DIR,i-2);v.SetContainerName(cid,'Station '+str(i));ids.append(cid)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return ids

    def test_rename_and_nonadjacent_batch_removal_preserve_native_survivors(self):
        v=self.v;ids=self.fixture();baseline,_=self.worker(dict(action='state'))
        state,renamed=self.worker(dict(action='mutate',operation='flow-plane-rename',id=ids[2],name='Midspan'))
        self.assertEqual(next(c['name'] for c in state['tools']['flowPlanes'] if c['id']==ids[2]),'Midspan')
        before=state['tools']['flowPlanes'];state,path=self.worker(dict(action='mutate',operation='flow-plane-delete-many',ids=[ids[4],ids[0],ids[2]]),renamed)
        expected=[c for c in before if c['id'] in [ids[1],ids[3]]]
        for result in [state,self.worker(dict(action='state'),path)[0]]:
            self.assertEqual(result['tools']['flowPlanes'],expected);self.assertEqual(result['components'],baseline['components'])
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual([v.GetCpSliceID(i) for i in range(v.GetNumCpSlices())],[ids[1],ids[3]])

    def test_single_and_batch_removal_reject_referenced_plane_atomically(self):
        v=self.v;ids=self.fixture();pid=v.FindParm(ids[2],'CutPosition','CpSlice')
        v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Required cut',pid);v.WriteVSPFile(str(self.model),v.SET_ALL)
        original=self.model.read_bytes()
        for request in [dict(operation='flow-plane-delete',id=ids[2]),dict(operation='flow-plane-delete-many',ids=[ids[0],ids[2]])]:
            with self.assertRaisesRegex(ValueError,'cutting-plane parameter IDs.*parameter reference'):
                self.worker(dict(action='mutate',**request))
            self.assertEqual(self.model.read_bytes(),original)
            self.assertTrue(all(p.read_bytes()==original for p in self.path.glob('*/aircraft.vsp3')))
        state,path=self.worker(dict(action='mutate',operation='flow-plane-delete-many',ids=[ids[0],ids[4]]))
        self.assertIn(ids[2],[p['id'] for p in state['tools']['flowPlanes']])
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.assertTrue(v.ValidParm(pid))

    def test_invalid_selection_and_names_do_not_save_partial_changes(self):
        ids=self.fixture();original=self.model.read_bytes()
        requests=[dict(operation='flow-plane-delete-many',ids=values) for values in [[],[ids[0],ids[0]],[ids[0],'stale'],None,[{}]]]
        requests += [dict(operation='flow-plane-rename',id=cid,name=name) for cid,name in [(ids[0],''),(ids[0],'x'*121),('stale','Cut')]]
        for request in requests:
            with self.subTest(request=request):
                with self.assertRaises(ValueError):self.worker(dict(action='mutate',**request))
                self.assertEqual(self.model.read_bytes(),original)
                self.assertTrue(all(p.read_bytes()==original for p in self.path.glob('*/aircraft.vsp3')))
