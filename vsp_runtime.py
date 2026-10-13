"""Find the official, project-local OpenVSP distribution without altering it."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent

def distribution():
    custom = os.environ.get('OPENVSP_HOME')
    if custom:
        return Path(custom).resolve()
    choices = sorted((ROOT / '.runtime').glob('OpenVSP-*-MacOS'))
    return choices[-1] if choices else None

def interpreter():
    if os.environ.get('OPENVSP_PYTHON'):
        return os.environ['OPENVSP_PYTHON']
    local = ROOT / '.runtime/python-interpreters/cpython-3.11-macos-aarch64-none/bin/python3'
    return str(local) if local.exists() else sys.executable

def load():
    home = distribution()
    if home:
        sys.path[:0] = [str(ROOT / '.runtime/site'), str(home / 'python/openvsp'), str(home / 'python/openvsp_config')]
        import openvsp_config
        openvsp_config._IGNORE_IMPORTS = True
    # The original loader scans ./CustomScripts once per process. Initialize
    # bundled, official component types from the distribution, then restore the
    # caller's job directory before any model or analysis files are opened.
    previous=os.getcwd()
    try:
        if home:os.chdir(home)
        import openvsp as vsp
        vsp.GetGeomTypes()
    finally:
        os.chdir(previous)
    if home:
        vsp.SetVSPAEROPath(str(home))
    return vsp
