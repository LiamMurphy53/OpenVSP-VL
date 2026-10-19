"""Saved-reader commands must preserve their input database on every exit path."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import native_flow_reader as reader


class FlowReaderIntegrity(unittest.TestCase):
    def test_native_motion_flags_and_database_provenance(self):
        native=SimpleNamespace(STABILITY_P_ANALYSIS=2,STABILITY_Q_ANALYSIS=3,STABILITY_R_ANALYSIS=4)
        with tempfile.TemporaryDirectory() as directory:
            setup=Path(directory)/'aircraft.vspaero';database=setup.with_suffix('.adb')
            payload=b'original solved database';database.write_bytes(payload)
            for unsteady,stability,flag in [(False,0,None),(True,0,'-unsteady'),(True,2,'-pstab'),(True,3,'-qstab'),(True,4,'-rstab')]:
                with self.subTest(unsteady=unsteady,stability=stability):
                    with patch.object(reader,'executable',return_value=(Path('/native/reader'),{})),patch.object(reader.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
                        result=reader.run(native,setup,unsteady,stability)
                    self.assertNotIn('STUDIO_EVALUATED_STATE_FILE',run.call_args.kwargs['env'])
                    self.assertEqual(run.call_args.args[0],['/native/reader','-omp','1','-interrogate']+([flag] if flag else [])+[str(setup.with_suffix(''))])
                    self.assertEqual(result['inputDatabaseSha256'],hashlib.sha256(payload).hexdigest())
                    self.assertEqual(result['outputDatabaseSha256'],result['inputDatabaseSha256'])
                    self.assertEqual(database.read_bytes(),payload)

    def test_rewritten_database_is_rejected_even_when_solver_reports_success(self):
        with tempfile.TemporaryDirectory() as directory:
            setup=Path(directory)/'aircraft.vspaero';database=setup.with_suffix('.adb');database.write_bytes(b'original')
            def solve(arguments,**kwargs):
                database.write_bytes(b'fresh solution');return SimpleNamespace(returncode=0)
            with patch.object(reader,'executable',return_value=(Path('/native/reader'),{})),patch.object(reader.subprocess,'run',side_effect=solve):
                with self.assertRaisesRegex(ValueError,'changed its input database'):
                    reader.run(None,setup,False)

    def test_failed_native_reader_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            setup=Path(directory)/'aircraft.vspaero';setup.with_suffix('.adb').write_bytes(b'original')
            with patch.object(reader,'executable',return_value=(Path('/native/reader'),{})),patch.object(reader.subprocess,'run',return_value=SimpleNamespace(returncode=7)):
                with self.assertRaisesRegex(ValueError,'status 7'):
                    reader.run(None,setup,False)
