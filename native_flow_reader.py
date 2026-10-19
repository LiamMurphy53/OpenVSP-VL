"""Version-locked official solver build with saved-record restoration fixes.

The vendor source is original OpenVSP. The reviewable patch changes only the
saved-solution reader and restoration calls; aerodynamic equations are unchanged.
The installed solver and the original saved database are never modified.
"""
import hashlib,json,os,platform,shutil,subprocess,tempfile
from pathlib import Path
from vsp_runtime import ROOT


def executable(v,capture=False):
    if platform.system()!='Darwin' or platform.machine()!='arm64' or v.GetVSPVersion()!='OpenVSP 3.52.2':
        raise ValueError('Saved airflow restoration currently requires macOS arm64 OpenVSP 3.52.2.')
    vendor=ROOT/'native_bridge/vendor/vspaero-3.52.2'
    patch=ROOT/'native_bridge/flow_reader_3_52_2.patch'
    state_patch=ROOT/'native_bridge/evaluated_state_read_3_52_2.patch'
    patches=[patch,state_patch]
    if capture:patches.append(ROOT/'native_bridge/evaluated_state_3_52_2.patch')
    patch_bytes=b''.join(p.read_bytes() for p in patches)
    sources=sorted(p for p in vendor.iterdir() if p.suffix in ('.C','.H'))
    flags=['-std=c++17','-O1','-DMYTIME','-Domp_get_max_threads()=1','-Wno-format','-Wno-format-security','-Wno-non-pod-varargs']
    digest=hashlib.sha256(patch_bytes+json.dumps(flags).encode()+b''.join(p.name.encode()+p.read_bytes() for p in sources)).hexdigest()
    cache=ROOT/'.runtime/native-flow-reader';cache.mkdir(parents=True,exist_ok=True)
    destination=cache/(digest[:24]+'-vspaero')
    if not destination.exists():
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            work=Path(directory);src=work/'reader-repair';src.mkdir()
            for p in sources:shutil.copy2(p,src/p.name)
            for source_patch in patches:
                applied=subprocess.run(['/usr/bin/patch','-p1','-i',str(source_patch)],cwd=src,capture_output=True,text=True,timeout=30)
                if applied.returncode:raise ValueError('Could not apply the saved-reader compatibility repair: '+applied.stdout[-2000:]+applied.stderr[-2000:])
            cmake=(vendor/'CMakeLists.txt').read_text().split('SET( VSPAERO_CORE_FILES',1)[1].split(')',1)[0]
            files=[s.strip() for s in cmake.splitlines() if s.strip().endswith('.C') and not s.lstrip().startswith('#')]+['vspaero.C']
            output=work/'vspaero'
            command=['/usr/bin/clang++',*flags,'-iquote',str(src),*[str(src/name) for name in files],'-o',str(output)]
            built=subprocess.run(command,capture_output=True,text=True,timeout=120)
            (cache/(digest[:24]+'.build.log')).write_text(built.stdout+built.stderr)
            if built.returncode:raise ValueError('Could not build the saved airflow reader: '+built.stderr[-3000:])
            output.replace(destination)
    return destination,dict(engineSourceTag='OpenVSP_3.52.2',readerSourceSha256=digest,readerExecutableSha256=hashlib.sha256(destination.read_bytes()).hexdigest(),readerPatchSha256=hashlib.sha256(patch_bytes).hexdigest(),readerMode='serial',readerRepair='Saved geometry records, active wake positions, native rotor-wake initialization, all-grid circulation, original core widths, time-aligned motion, stored near-body velocities and distinct temporal output records')


def run(v,setup,unsteady,stability=0):
    database=Path(setup).with_suffix('.adb')
    import native_evaluated_state
    captured=native_evaluated_state.validate(database)
    solver,provenance=executable(v)
    environment=os.environ.copy();environment.pop('STUDIO_EVALUATED_STATE_FILE',None)
    if captured:environment['STUDIO_EVALUATED_STATE_FILE']=str(database.with_suffix('.studio-state').resolve())
    with database.open('rb') as stream:
        original=hashlib.file_digest(stream,'sha256').hexdigest()
    arguments=[str(solver),'-interrogate']
    if unsteady:
        flags={v.STABILITY_P_ANALYSIS:'-pstab',v.STABILITY_Q_ANALYSIS:'-qstab',v.STABILITY_R_ANALYSIS:'-rstab'}
        arguments.append(flags.get(stability,'-unsteady'))
    arguments.append(str(Path(setup).with_suffix('')))
    # Inherit the worker log and process group for ordinary cancellation/recovery.
    result=subprocess.run(arguments,env=environment)
    with database.open('rb') as stream:
        restored=hashlib.file_digest(stream,'sha256').hexdigest()
    if restored!=original:
        raise ValueError('Saved airflow interrogation changed its input database. These outputs cannot be accepted as restored results.')
    if captured and native_evaluated_state.validate(database)['binding']!=captured['binding']:raise ValueError('Native evaluated-state binding changed during restoration.')
    if result.returncode:raise ValueError(f'The saved airflow reader exited with status {result.returncode}. Inspect its native log.')
    provenance.update(readerOperation='saved-database-interrogation',inputDatabaseSha256=original,outputDatabaseSha256=restored)
    provenance['evaluatedState']=dict(mode='captured' if captured else 'legacy',binding=captured['binding'] if captured else None)
    return provenance
