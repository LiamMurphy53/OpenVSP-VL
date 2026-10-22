"""Zero process exit must not turn expected failures or skips into passes."""
import json
import io
import shutil
from contextlib import redirect_stdout
from unittest.mock import patch
import run_native_suite as runner
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from run_native_suite import case_status, flatten


class NativeSuiteAccounting(unittest.TestCase):
    def test_actual_unittest_outcomes_are_distinguished(self):
        root=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as folder:
            report=Path(folder)/'outcome.json'
            for method,status in [('pass','pass'),('expected_failure','expected-failure'),('skip','skipped'),
                                  ('unexpected_success','unexpected-success'),('failure','fail'),('error','fail')]:
                with self.subTest(method=method):
                    result=subprocess.run([sys.executable,str(root/'native_case_runner.py'),
                        '--test','native_case_fixture.Outcomes.test_'+method,'--report',str(report)],
                        cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
                    data=json.loads(report.read_text())
                    self.assertEqual(case_status(result.returncode,data),status)
                    if method=='unexpected_success':self.assertEqual(data['unexpectedSuccesses'],1)
                    if method=='expected_failure':self.assertEqual(data['expectedFailures'],1)
                    self.assertFalse(report.with_suffix('.tmp').exists())

    def test_crashes_missing_and_malformed_reports_cannot_pass(self):
        for report in (None,{},dict(testsRun=0),dict(testsRun=1,failures=False,errors=0,
                     skipped=0,expectedFailures=0,unexpectedSuccesses=0)):
            self.assertEqual(case_status(0,report),'invalid-report')
        self.assertEqual(case_status(-11,None),'crash')
        self.assertEqual(case_status(1,None),'fail')
        good=dict(testsRun=1,failures=0,errors=0,skipped=0,expectedFailures=0,unexpectedSuccesses=0)
        self.assertEqual(case_status(0,{**good,'unexpectedSuccesses':1}),'unexpected-success')
        self.assertEqual(list(flatten(unittest.TestSuite([unittest.TestSuite()]))),[])


    def test_parent_manifest_retains_every_outcome_and_returns_nonzero(self):
        source=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);tests=root/'tests';tests.mkdir()
            shutil.copy2(source/'native_case_runner.py',tests/'native_case_runner.py')
            shutil.copy2(source/'native_case_fixture.py',tests/'test_outcomes.py')
            output=root/'logs'
            with patch.object(unittest,'defaultTestLoader',unittest.TestLoader()),patch.object(runner,'ROOT',root),patch.object(sys,'argv',['runner','--output',str(output)]),redirect_stdout(io.StringIO()):
                code=runner.main()
            data=json.loads((output/'summary.json').read_text())
            self.assertEqual(code,1)
            self.assertTrue(data['complete'])
            self.assertEqual(data['total'],6)
            self.assertEqual(data['counts'],{'pass':1,'fail':2,'expected-failure':1,'skipped':1,
                'unexpected-success':1,'crash':0,'timeout':0,'invalid-report':0})
            self.assertTrue(all(r['unittest']['testsRun']==1 for r in data['results']))
