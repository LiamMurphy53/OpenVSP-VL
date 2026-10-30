"""Choose the VSPAERO build for a solve.

Single-thread roll, pitch and yaw solves use the original-source recorder. Every
other solve uses the same source build without recording, because the stock
3.52.2 binary reads an uninitialized wake edge and can crash or return NaN.
"""
from contextlib import contextmanager
from pathlib import Path
import os,tempfile

SOLVES=('VSPAEROSweep','VSPAEROSinglePoint')


def eligible(v,name,inputs):
    values={e['name']:e['values'][0] for e in inputs if len(e.get('values',[]))==1}
    return name in SOLVES and values.get('NCPU')==1 and values.get('UnsteadyType') in (v.STABILITY_P_ANALYSIS,v.STABILITY_Q_ANALYSIS,v.STABILITY_R_ANALYSIS) and not values.get('StopBeforeRun',0)


def repaired(name,inputs):
    values={e['name']:e['values'][0] for e in inputs if len(e.get('values',[]))==1}
    return name in SOLVES and not values.get('StopBeforeRun',0)


@contextmanager
def solver(v,name,inputs):
    capture=eligible(v,name,inputs)
    if not capture and not repaired(name,inputs):
        yield None;return
    from native_flow_reader import executable
    from vsp_runtime import ROOT,distribution
    try:binary,meta=executable(v,capture=capture)
    except ValueError:
        # Platforms without the source build keep the installed solver.
        if capture:raise
        yield None;return
    writer=dict(engineSourceTag=meta['engineSourceTag'],writerExecutableSha256=meta['readerExecutableSha256'],writerSourceSha256=meta['readerSourceSha256'],writerPatchSha256=meta['readerPatchSha256']) if capture else None
    previous=v.GetVSPAEROPath()
    with tempfile.TemporaryDirectory(prefix='recording-solver-' if capture else 'solver-',dir=ROOT/'.runtime/native-flow-reader') as directory:
        directory=Path(directory);(directory/'vspaero').symlink_to(binary)
        for original in distribution().iterdir():
            if original.name!='vspaero' and original.is_file() and os.access(original,os.X_OK):(directory/original.name).symlink_to(original.resolve())
        try:
            v.SetVSPAEROPath(str(directory))
            if not v.CheckForVSPAERO(str(directory)):raise ValueError('The native state recorder could not provide the required VSPAERO tools.' if capture else 'The repaired VSPAERO build could not provide the required tools.')
            yield writer
        finally:v.SetVSPAEROPath(previous)


def seal_outputs(writer):
    if writer is None:return None
    import native_evaluated_state
    databases=sorted(Path.cwd().glob('*.adb'))
    if not databases:raise ValueError('The recording solver produced no native database.')
    return dict(mode='captured',bindings=[native_evaluated_state.seal(p,writer) for p in databases])
