"""Retain original applied inputs before entering a native calculation."""
import json
from pathlib import Path


def save(v,analysis,inputs,**details):
    setup=dict(analysis=analysis,version=v.GetVSPVersion(),inputs=inputs,
               stage='before native execution',**details)
    setup.setdefault('geometryInputs',[])
    path=Path.cwd()/'analysis-setup.json';temp=path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(setup));temp.replace(path)
    return setup
