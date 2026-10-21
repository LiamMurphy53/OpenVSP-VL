"""Real subprocess exits retain diagnostics even without a native response."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import native_service as service

class WorkerExit(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'transaction'
        self.model=self.root/'aircraft.vsp3';self.model.write_text('unchanged aircraft')
    def invoke(self,script,timeout=5):
        (self.root/'native_worker.py').write_text(script)
        with patch.object(service,'ROOT',self.root),patch.object(service,'interpreter',return_value=sys.executable):
            return service.invoke({'action':'state'},self.model,self.folder,timeout=timeout)
    def receipt(self):return json.loads((self.folder/'worker-exit.json').read_text())
    def test_signal_and_missing_response_are_distinguished(self):
        with self.assertRaisesRegex(RuntimeError,'SIGTERM'):
            self.invoke('import os,signal;os.kill(os.getpid(),signal.SIGTERM)')
        r=self.receipt();self.assertGreater(r['processID'],0);self.assertEqual(r['returncode'],-signal.SIGTERM);self.assertEqual(r['terminationSignal'],'SIGTERM');self.assertFalse(r['timedOut'])
        self.assertEqual(json.loads((self.folder/'request.json').read_text()),{'action':'state'})
        self.assertEqual(self.model.read_text(),'unchanged aircraft')
    def test_zero_exit_without_response_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError,'exit code 0'):self.invoke('pass')
        self.assertEqual(self.receipt()['returncode'],0)
    def test_timeout_reaps_child_and_records_exit(self):
        with self.assertRaises(subprocess.TimeoutExpired):self.invoke('import time;time.sleep(30)',timeout=.1)
        r=self.receipt();self.assertTrue(r['timedOut']);self.assertIsNotNone(r['returncode'])
    def test_native_response_and_error_contracts_are_preserved(self):
        script='import json,sys;open(sys.argv[3],"w").write(json.dumps(%s))'
        self.assertEqual(self.invoke(script % repr({'value':3})),{'value':3})
        with self.assertRaisesRegex(ValueError,'native validation failed'):
            self.invoke(script % repr({'error':'native validation failed'}))

    def test_native_helper_retains_failed_worker_before_temporary_cleanup(self):
        import test_native
        case=test_native.NativeIntegration('test_invalid_number_is_rejected')
        case.path=self.root/'temporary-test';case.path.mkdir();case.model=case.path/'source.vsp3';case.model.write_text('exact original input')
        (self.root/'native_worker.py').write_text('import os,signal;os.kill(os.getpid(),signal.SIGTERM)')
        with patch.object(service,'ROOT',self.root),patch.object(service,'interpreter',return_value=sys.executable),patch.object(test_native,'ROOT',self.root):
            with self.assertRaisesRegex(RuntimeError,'Retained worker input'):case.worker({'action':'state'})
        import shutil
        shutil.rmtree(case.path)
        saved=list((self.root/'.workspace/evidence/native-worker-failures').iterdir());self.assertEqual(len(saved),1)
        self.assertEqual((saved[0]/'input.vsp3').read_text(),'exact original input')
        self.assertEqual(json.loads((saved[0]/'worker-exit.json').read_text())['terminationSignal'],'SIGTERM')

    def test_failed_candidate_never_replaces_aircraft_or_history(self):
        script='import os,signal,sys;open(sys.argv[2],"w").write("partial candidate");os.kill(os.getpid(),signal.SIGTERM)'
        (self.root/'native_worker.py').write_text(script)
        history=['previous'];future=['future']
        with patch.multiple(service,ROOT=self.root,WORK=self.root,MODEL=self.model,REVISION='original',HISTORY=history,FUTURE=future),patch.object(service,'interpreter',return_value=sys.executable):
            with self.assertRaisesRegex(RuntimeError,'SIGTERM'):
                service.mutation({'operation':'parameter','id':'length','value':4,'revision':'original'})
            self.assertEqual(service.REVISION,'original');self.assertEqual(service.HISTORY,['previous']);self.assertEqual(service.FUTURE,['future'])
        self.assertEqual(self.model.read_text(),'unchanged aircraft')
        folders=list((self.root/'transactions').iterdir());self.assertEqual(len(folders),1)
        self.assertEqual((folders[0]/'aircraft.vsp3').read_text(),'partial candidate')
        self.assertEqual(json.loads((folders[0]/'worker-exit.json').read_text())['terminationSignal'],'SIGTERM')
