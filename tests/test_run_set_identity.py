"""Saved jobs retain the geometry-set identity of their own aircraft."""
import time,unittest
import test_studies
import native_service as service

class RunSetIdentity(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    def test_job_identity_survives_set_move_and_cold_job_loading(self):
        v=self.v;v.SetSetName(3,'Wing');v.SetSetFlag(self.gid,3,True);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state=service.state();identity=state['tools']['sets'][3]['identity'];before=self.model.read_bytes()
        job=service.start_job(dict(name='CompGeom',inputs=[dict(name='Set',index=0,values=[3])],revision=service.REVISION))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            saved=service.job_state(job['id'])
            if saved['status']!='running':break
            time.sleep(.03)
        self.assertEqual(saved['status'],'complete');self.assertEqual(saved['setIdentities'][3],identity);self.assertEqual(self.model.read_bytes(),before)
        order=list(range(3,v.GetNumSets()));order[0],order[1]=order[1],order[0]
        moved=service.mutation(dict(operation='set-reorder',order=order,revision=service.REVISION));self.assertEqual(moved['tools']['sets'][4]['identity'],identity)
        service.JOBS={};cold=service.job_state(job['id']);self.assertEqual(cold['setIdentities'][3],identity)
        self.assertEqual(next(e['values'] for e in cold['result']['results'][0]['entries'] if e['name']=='Comp_Name'),['Reference wing'])
