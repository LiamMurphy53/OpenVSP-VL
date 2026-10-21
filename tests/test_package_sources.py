"""A fresh package carries the audit referenced by its capability inventory."""
from pathlib import Path
import tempfile,unittest,json,subprocess,sys
from package_studio import copy_sources
from vsp_runtime import ROOT
class PackageSources(unittest.TestCase):
    def test_fresh_source_package_contains_current_engineering_audit_and_no_working_models(self):
        with tempfile.TemporaryDirectory(prefix='studio delivery sources ') as folder:
            target=Path(folder);copy_sources(ROOT,target)
            self.assertEqual((target/'ENGINEERING_UTILITY_AUDIT.md').read_bytes(),(ROOT/'ENGINEERING_UTILITY_AUDIT.md').read_bytes())
            inventory=json.loads((target/'CAPABILITY_INVENTORY.json').read_text());self.assertIn('ENGINEERING_UTILITY_AUDIT.md',json.dumps(inventory))
            for name in ['.workspace','.runtime','aircraft.vsp3','tests']:self.assertFalse((target/name).exists(),name)
            for name in ['server.py','native_worker.py','web/app.js','native_bridge/structural_preview.cpp']:self.assertTrue((target/name).is_file(),name)

    def test_native_harness_respects_preloaded_runtime_root(self):
        with tempfile.TemporaryDirectory(prefix='packaged runtime root ') as folder:
            package=Path(folder)/'studio';package.mkdir()
            script="""from pathlib import Path
import sys,types
runtime=types.ModuleType('vsp_runtime');runtime.ROOT=Path(sys.argv[1]);runtime.load=lambda:None;runtime.interpreter=lambda:'unused'
sys.modules['vsp_runtime']=runtime
sys.path.insert(0,sys.argv[2])
import test_native
assert test_native.ROOT==runtime.ROOT
assert str(Path(sys.argv[2]).parent) not in sys.path
"""
            subprocess.run([sys.executable,'-I','-c',script,str(package),str(Path(__file__).resolve().parent)],check=True,cwd=folder,capture_output=True,text=True)
