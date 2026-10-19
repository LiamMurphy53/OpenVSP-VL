"""The solver dependency must fail closed before build or packaging."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from native_openmp import runtime

class OpenMPRuntime(unittest.TestCase):
    def test_missing_changed_and_linked_dependency_reject(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'native_bridge').mkdir();directory=root/'.runtime/openmp';directory.mkdir(parents=True)
            path=directory/'library';path.write_bytes(b'expected')
            (root/'native_bridge/openmp_runtime.json').write_text(json.dumps(dict(files={'library':hashlib.sha256(b'expected').hexdigest()})))
            self.assertEqual(runtime(root)[0],directory)
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'missing or changed'):runtime(root)
            path.unlink()
            with self.assertRaises(ValueError):runtime(root)
            target=root/'target';target.write_bytes(b'expected');path.symlink_to(target)
            with self.assertRaises(ValueError):runtime(root)
