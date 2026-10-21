"""Retry a persisted cancellation after the original service process dies."""
from pathlib import Path
import json,os,signal,subprocess,sys,tempfile,time,unittest
from unittest.mock import patch
import native_service as service,native_processes
from test_job_stop_recovery import WORKER

OWNER='''from pathlib import Path
import sys,time,uuid
sys.path.insert(0,sys.argv[1])
import native_service as service,native_processes
service.WORK=Path(sys.argv[2]);service.MODEL=service.WORK/'aircraft.vsp3';service.ROOT=Path(sys.argv[3]);service.REVISION=uuid.uuid4().hex
service.interpreter=lambda:sys.executable
native_processes.STOP_GRACE_SECONDS=60
job=service.start_job(dict(name='CompGeom',scenario='parent'),model_source=service.MODEL,set_identities=[])
while not (service.job_folder(job['id'])/'ready').exists():time.sleep(.01)
service.cancel_job(job['id'])
'''

def interrupted_owner(work,model_bytes=b'original aircraft'):
    work=Path(work);work.mkdir(parents=True,exist_ok=True);(work/'aircraft.vsp3').write_bytes(model_bytes)
    runtime=work/'test-worker-runtime';runtime.mkdir();(runtime/'native_worker.py').write_text(WORKER.replace('time.sleep(60)','time.sleep(600)'))
    script=work/'owner.py';script.write_text(OWNER);log=(work/'owner.log').open('w')
    owner=subprocess.Popen([sys.executable,'-I',str(script),str(Path(service.__file__).parent),str(work),str(runtime)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    pid=None
    try:
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            for p in (work/'jobs').glob('*/job.json'):
                meta=json.loads(p.read_text());pid=meta['processID']
                if meta.get('stopping'):
                    owner.kill();owner.wait(timeout=5);return meta,runtime
            if owner.poll() is not None:raise AssertionError('Owner stopped before cancellation: '+(work/'owner.log').read_text())
            time.sleep(.01)
        raise AssertionError('Owner did not persist the pending cancellation')
    except BaseException:
        if owner.poll() is None:owner.kill();owner.wait(timeout=5)
        if pid:
            try:os.killpg(pid,signal.SIGKILL)
            except ProcessLookupError:pass
        raise
    finally:log.close()

class RestartedJobStop(unittest.TestCase):
    def test_recovered_stop_has_no_popen_handle_and_allows_next_job(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory);meta,runtime=interrupted_owner(work);pid=meta['processID']
            try:
                with patch.multiple(service,ROOT=runtime,WORK=work,MODEL=work/'aircraft.vsp3',REVISION='restarted',JOBS={},RUN_RESERVATION=None),patch.object(service,'interpreter',return_value=sys.executable),patch.object(native_processes,'STOP_GRACE_SECONDS',.15):
                    job=service.job_state(meta['id']);self.assertTrue(job['stopping']);self.assertNotIn('_process',service.JOBS[meta['id']]);self.assertTrue(service.lock_is_held(work/'run.lock'))
                    service.cancel_job(meta['id'])
                    deadline=time.monotonic()+5
                    while service.job_state(meta['id']).get('stopping') and time.monotonic()<deadline:time.sleep(.01)
                    job=service.job_state(meta['id']);self.assertEqual(job['status'],'cancelled');self.assertFalse(job['stopping']);self.assertTrue(job['forceStopped']);self.assertFalse(service.lock_is_held(work/'run.lock'))
                    next_job=service.start_job(dict(name='CompGeom',scenario='quick'),model_source=work/'aircraft.vsp3',set_identities=[]);monitor=service.JOBS[next_job['id']]['_monitor'];monitor.join(timeout=5);self.assertFalse(monitor.is_alive());self.assertEqual(service.job_state(next_job['id'])['status'],'complete')
                    service.JOBS.pop(meta['id']);self.assertFalse(service.job_state(meta['id'])['stopping']);self.assertEqual((work/'aircraft.vsp3').read_bytes(),b'original aircraft')
            finally:
                try:os.killpg(pid,signal.SIGKILL)
                except ProcessLookupError:pass
