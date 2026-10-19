"""Native companion integrity, lossless values and explicit legacy behavior."""
import unittest,tempfile,json,math
from pathlib import Path
from unittest.mock import patch
import native_evaluated_state as state

WRITER=dict(engineSourceTag='OpenVSP_3.52.2',writerExecutableSha256='a'*64,writerSourceSha256='b'*64,writerPatchSha256='c'*64)

class EvaluatedState(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.database=self.root/'aircraft.adb';self.database.write_bytes(b'original database bytes')
        self.cases=Path(str(self.database)+'.cases');self.cases.write_text('.1 4 0 Time 0\n.1 4 0 Time 1\n');self.companion=self.database.with_suffix('.studio-state')
        self.text=state.MAGIC+'\nR 0 1 2 1 0x0p+0\n-0x0p+0\n0x1.fffffffffffffp+20\nR 1 1 2 1 0x1p-5\n0x1.0000000000001p-20\n-0x1p+3\n';self.companion.write_text(self.text)
    def tearDown(self):self.temp.cleanup()

    def test_binding_lossless_values_and_legacy(self):
        before={p.name:p.read_bytes() for p in [self.database,self.cases,self.companion]};binding=state.seal(self.database,WRITER);loaded=state.validate(self.database)
        self.assertEqual(loaded['binding'],binding);self.assertEqual(loaded['records'][1]['gamma'][0].hex(),'0x1.0000000000001p-20');self.assertEqual(math.copysign(1,loaded['records'][0]['gamma'][0]),-1)
        self.assertEqual(before,{p.name:p.read_bytes() for p in [self.database,self.cases,self.companion]})
        self.companion.unlink();self.database.with_suffix('.studio-state.json').unlink();self.assertIsNone(state.validate(self.database))

    def test_changed_missing_symlink_and_wrong_provenance_reject(self):
        state.seal(self.database,WRITER)
        for p in [self.database,self.cases,self.companion]:
            old=p.read_bytes();p.write_bytes(old+b'changed')
            with self.subTest(file=p.name),self.assertRaises(ValueError):state.validate(self.database)
            p.write_bytes(old)
        old=self.companion.read_bytes();self.companion.unlink()
        with self.assertRaises(ValueError):state.validate(self.database)
        target=self.root/'target';target.write_bytes(old);self.companion.symlink_to(target)
        with self.assertRaises(ValueError):state.validate(self.database)
        self.companion.unlink();self.companion.write_bytes(old)
        manifest=self.database.with_suffix('.studio-state.json');manifest.unlink()
        with self.assertRaises(ValueError):state.validate(self.database)
        for writer in [{},WRITER|{'engineSourceTag':'unknown'},WRITER|{'writerExecutableSha256':'bad'}]:
            with self.assertRaises(ValueError):state.seal(self.database,writer)

    def test_bad_records_and_case_count_reject_without_overwriting_binding(self):
        state.seal(self.database,WRITER);manifest=self.database.with_suffix('.studio-state.json');before=manifest.read_bytes()
        for text in ['',self.text[:-8],self.text.replace('R 1','R 3'),self.text.replace('2 1 0x0','0 1 0x0'),self.text.replace('-0x1p+3','nan'),self.text.replace('R 0','R 1'),self.text+'extra\n',self.text.replace('R 1 1 2 1 0x1p-5','R 1 1 2 1 0x0p+0')]:
            self.companion.write_text(text)
            with self.subTest(text=text),self.assertRaises(ValueError):state.seal(self.database,WRITER)
            self.assertEqual(manifest.read_bytes(),before)
        self.companion.write_text(self.text);self.cases.write_text('.1 4 0 only one\n')
        with self.assertRaises(ValueError):state.seal(self.database,WRITER)
        self.assertEqual(manifest.read_bytes(),before)

    def test_reader_rejects_changed_binding_before_start_and_after_child(self):
        from types import SimpleNamespace
        import native_flow_reader as reader
        state.seal(self.database,WRITER);setup=self.database.with_suffix('.vspaero')
        original=self.companion.read_bytes();self.companion.write_bytes(original+b'changed')
        with patch.object(reader,'executable') as executable:
            with self.assertRaises(ValueError):reader.run(None,setup,False)
            executable.assert_not_called()
        self.companion.write_bytes(original)
        def child(arguments,env):
            self.assertEqual(env['STUDIO_EVALUATED_STATE_FILE'],str(self.companion.resolve()))
            self.companion.write_bytes(original+b'changed')
            return SimpleNamespace(returncode=0)
        with patch.object(reader,'executable',return_value=(Path('/native/reader'),{})),patch.object(reader.subprocess,'run',side_effect=child):
            with self.assertRaises(ValueError):reader.run(None,setup,False)

    def test_atomic_binding_failure_preserves_previous_manifest(self):
        state.seal(self.database,WRITER);manifest=self.database.with_suffix('.studio-state.json');before=manifest.read_bytes()
        with patch('pathlib.Path.replace',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):state.seal(self.database,WRITER)
        self.assertEqual(manifest.read_bytes(),before);self.assertEqual(list(self.root.glob(manifest.name+'.*')),[])

if __name__=='__main__':unittest.main()
