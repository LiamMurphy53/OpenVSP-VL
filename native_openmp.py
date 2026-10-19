"""Pinned, project-local OpenMP dependency for the original-source solver."""
import hashlib,json
from pathlib import Path


def runtime(root):
    root=Path(root);manifest=root/'native_bridge/openmp_runtime.json'
    metadata=json.loads(manifest.read_text());directory=root/'.runtime/openmp'
    for name,expected in metadata['files'].items():
        path=directory/name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('The bundled OpenMP runtime is missing or changed: '+name+'. Restore this Studio installation’s .runtime/openmp folder.')
    return directory,metadata
