"""Real isolated subprocess groups release run locks after cancellation/timeouts."""
from pathlib import Path
import json,os,signal,sys,tempfile,time,unittest
from unittest.mock import patch
import native_service as service,native_processes

WORKER='''import json,os,pathlib,signal,subprocess,sys,time
request=json.loads(pathlib.Path(sys.argv[1]).read_text());scenario=request.get('scenario','quick')
if scenario in ('malformed','array'):pathlib.Path(sys.argv[3]).write_text('{' if scenario=='malformed' else '[]');sys.exit(0)
if scenario=='parent':signal.signal(signal.SIGTERM,signal.SIG_IGN)
if scenario=='child':
 subprocess.Popen([sys.executable,'-c',"import signal,time,pathlib;signal.signal(signal.SIGTERM,signal.SIG_IGN);pathlib.Path('child-ready').write_text('yes');time.sleep(60)"],close_fds=False)
 while not pathlib.Path('child-ready').exists():time.sleep(.01)
pathlib.Path('ready').write_text('yes')
if scenario in ('parent','child'):time.sleep(60)
pathlib.Path(sys.argv[3]).write_text(json.dumps(dict(version='process-control fixture',results=[])))
'''
class JobStopRecovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.model=self.root/'aircraft.vsp3';self.model.write_bytes(b'original aircraft')
        (self.root/'native_worker.py').write_text(WORKER)
        self.patches=[patch.multiple(service,ROOT=self.root,WORK=self.root,MODEL=self.model,REVISION='test',JOBS={},RUN_RESERVATION=None,ANALYSIS_TIMEOUT_SECONDS=1.),patch.object(service,'interpreter',return_value=sys.executable),patch.object(native_processes,'STOP_GRACE_SECONDS',.15)]
        for p in self.patches:p.start()
        self.processes=[]
    def tearDown(self):
        for jid,process,monitor in self.processes:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=5)
        for jid,process,monitor in self.processes:
            deadline=time.monotonic()+3
            while jid in service.JOBS and not service.JOBS[jid].get('finished') and time.monotonic()<deadline:time.sleep(.01)
        for jid,process,monitor in self.processes:monitor.join(timeout=5);self.assertFalse(monitor.is_alive())
        for p in reversed(self.patches):p.stop()
    def start(self,scenario):
        job=service.start_job(dict(name='CompGeom',scenario=scenario),model_source=self.model,set_identities=[]);self.processes.append((job['id'],service.JOBS[job['id']]['_process'],service.JOBS[job['id']]['_monitor']));return job
    def wait(self,jid,ready=False):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            job=service.job_state(jid)
            if ready and (service.job_folder(jid)/'ready').exists():return job
            if not ready and job.get('finished') and not job.get('stopping'):return job
            time.sleep(.01)
        self.fail('Verification process did not reach its expected state')
    def recovered(self,jid,status):
        job=self.wait(jid);self.assertEqual(job['status'],status);self.assertFalse(service.lock_is_held(self.root/'run.lock'));self.assertFalse(service.lock_is_held(service.job_folder(jid)/'.engine.lock'))
        service.JOBS.pop(jid);self.assertEqual(service.job_state(jid)['status'],status)
        next_job=self.start('quick');self.assertEqual(self.wait(next_job['id'])['status'],'complete');self.assertEqual(self.model.read_bytes(),b'original aircraft');return job
    def test_stubborn_parent_cancellation_releases_locks_and_allows_next_run(self):
        job=self.start('parent');self.wait(job['id'],ready=True);stopped=service.cancel_job(job['id']);self.assertFalse(stopped['stopping']);job=self.recovered(job['id'],'cancelled');self.assertTrue(job['forceStopped']);self.assertEqual(job['exitCode'],-signal.SIGKILL)
    def test_solver_child_is_stopped_even_after_worker_parent_exits(self):
        job=self.start('child');self.wait(job['id'],ready=True);service.cancel_job(job['id']);job=self.recovered(job['id'],'cancelled');self.assertTrue(job['forceStopped'])
    def test_timeout_stops_stubborn_group_and_releases_run_lock(self):
        job=self.start('parent');job=self.recovered(job['id'],'failed');self.assertTrue(job['timedOut']);self.assertTrue(job['forceStopped']);self.assertEqual(job['terminationSignal'],'SIGKILL')
    def test_malformed_receipt_is_failed_and_can_reopen_and_run_again(self):
        for scenario in ['malformed','array']:
            job=self.start(scenario);job=self.recovered(job['id'],'failed');self.assertIn('receipt could not be read',job['error'])

    def test_user_cancellation_is_preserved_when_timeout_overlaps_shutdown(self):
        with patch.object(service,'ANALYSIS_TIMEOUT_SECONDS',.1):
            job=self.start('parent');self.wait(job['id'],ready=True);service.cancel_job(job['id']);job=self.recovered(job['id'],'cancelled');self.assertTrue(job['forceStopped'])
