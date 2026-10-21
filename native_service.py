"""Transactional native models and isolated, asynchronous analysis jobs."""
import json
import re
import csv
import io
from mesh_io import read_gmsh
from aero_io import read_adb, read_flow_plane
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid
from vsp_runtime import ROOT, interpreter, distribution

WORK = Path(os.environ.get('OPENVSP_WORKSPACE',str(ROOT / '.workspace'))).expanduser().resolve()
MODEL = WORK / 'aircraft.vsp3'
LOCK = threading.RLock()
HISTORY = []
FUTURE = []
JOBS = {}
REVISION = uuid.uuid4().hex
NATIVE_PROCESS = None
RUN_RESERVATION = None
SESSION_WARNING = None
LAST_EDIT_GROUP = None
SET_IDENTITIES = {}


def acquire_run_lock(path):
    import fcntl
    path.parent.mkdir(parents=True,exist_ok=True)
    stream=path.open('a+')
    try:fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close();raise ValueError('A native analysis or study is already running. Finish or cancel it first.')
    return stream


def lock_is_held(path):
    import fcntl
    if not path.exists():return False
    with path.open('a+') as stream:
        try:fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return True
        fcntl.flock(stream.fileno(),fcntl.LOCK_UN);return False


def invoke(request, model, folder, timeout=90, log=None, inherited_locks=()):
    folder.mkdir(parents=True,exist_ok=True)
    request_path=folder/'request.json'; response=folder/'response.json'
    request_path.write_text(json.dumps(request))
    if response.exists(): response.unlink()
    fds=tuple(stream.fileno() for stream in inherited_locks)
    cmd=[interpreter(),str(ROOT/'native_worker.py'),str(request_path),str(model),str(response),*[str(fd) for fd in fds]]
    if log is None:
        with (folder/'engine.log').open('w') as stream:
            with subprocess.Popen(cmd,cwd=folder,stdout=stream,stderr=subprocess.STDOUT,pass_fds=fds) as process:
                timed_out=False
                try:process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out=True;process.kill();process.wait()
                    raise
                finally:
                    import signal
                    code=process.returncode
                    try:stopped=signal.Signals(-code).name if code is not None and code<0 else None
                    except ValueError:stopped='signal '+str(-code)
                    (folder/'worker-exit.json').write_text(json.dumps(dict(processID=process.pid,returncode=code,terminationSignal=stopped,timedOut=timed_out),indent=2)+'\n')
    else:
        process=subprocess.Popen(cmd,cwd=folder,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,pass_fds=fds)
        return process,response
    if not response.exists():
        raise RuntimeError(f'OpenVSP worker {process.pid} stopped with {stopped or "exit code "+str(process.returncode)} without a response. See {folder / "engine.log"} and worker-exit.json.')
    data=json.loads(response.read_text())
    if process.returncode or 'error' in data: raise ValueError(data.get('error','OpenVSP process failed.'))
    return data


def save_session(clear_warning=True):
    """Persist the native model revision and undo/redo paths for normal restarts."""
    global SESSION_WARNING
    import hashlib
    if not MODEL.is_file():return
    retained={'current',*(str(p.relative_to(WORK)) for p in [*HISTORY,*FUTURE])}
    for key in list(SET_IDENTITIES):
        if key not in retained:del SET_IDENTITIES[key]
    data=dict(revision=REVISION,modelHash=hashlib.sha256(MODEL.read_bytes()).hexdigest(),
              history=[str(p.relative_to(WORK)) for p in HISTORY],future=[str(p.relative_to(WORK)) for p in FUTURE],setIdentities=SET_IDENTITIES)
    WORK.mkdir(parents=True,exist_ok=True);temp=WORK/'session.json.tmp';temp.write_text(json.dumps(data));os.replace(temp,WORK/'session.json')
    if clear_warning:SESSION_WARNING=None


def restore_session():
    """Restore a verified native history; preserve inconsistent records for recovery."""
    global REVISION,HISTORY,FUTURE,SESSION_WARNING,SET_IDENTITIES
    import hashlib
    with LOCK:
        path=WORK/'session.json'
        if not path.is_file():return False
        try:
            data=json.loads(path.read_text())
            if not isinstance(data['revision'],str) or not re.fullmatch(r'[a-f0-9]{32}',data['revision']):raise ValueError('Invalid saved workspace revision.')
            if data['modelHash']!=hashlib.sha256(MODEL.read_bytes()).hexdigest():raise ValueError('The aircraft changed outside the saved workspace session.')
            def snapshots(items):
                if not isinstance(items,list):raise ValueError('Invalid saved history list.')
                result=[]
                for item in items:
                    candidate=WORK/item
                    if candidate.parent.resolve()!=(WORK/'history').resolve() or candidate.is_symlink() or candidate.suffix!='.vsp3' or not candidate.is_file():raise ValueError('A saved history aircraft is missing or outside this workspace.')
                    result.append(candidate)
                return result
            history=snapshots(data['history']);future=snapshots(data['future'])
            identities=data.get('setIdentities',{})
            from native_set_identity import validate_registry
            validate_registry(identities)
            SET_IDENTITIES=identities
            REVISION=data['revision'];HISTORY=history;FUTURE=future;SESSION_WARNING=None;return True
        except (ValueError,OSError,KeyError,TypeError) as exc:
            backup=WORK/('session-recovery-'+uuid.uuid4().hex+'.json');shutil.copy2(path,backup)
            REVISION=uuid.uuid4().hex;HISTORY=[];FUTURE=[];SET_IDENTITIES={};SESSION_WARNING=str(exc)+' The saved history record was preserved for recovery.';return False


def state_meta(state):
    from native_set_identity import annotate
    if annotate(state,SET_IDENTITIES):save_session(clear_warning=False)
    state.update(revision=REVISION,canUndo=bool(HISTORY),canRedo=bool(FUTURE),name='Aircraft',
                 nativeOpen=bool(NATIVE_PROCESS and NATIVE_PROCESS.poll() is None))
    if SESSION_WARNING:state['warnings'].append(SESSION_WARNING)
    return state


def state():
    with LOCK:
        WORK.mkdir(exist_ok=True)
        action='state' if MODEL.exists() else 'create'
        return state_meta(invoke({'action':action},MODEL,WORK/'state'))


def check_revision(value):
    if value != REVISION: raise ValueError('The model changed in another window. Reload the workspace before editing.')


def commit(candidate,history_group=None,set_count=None,set_order=None):
    global REVISION,LAST_EDIT_GROUP
    grouped=history_group is not None and LAST_EDIT_GROUP==(history_group,REVISION)
    if MODEL.exists() and not grouped:
        path=WORK/'history'/f'{uuid.uuid4().hex}.vsp3'; path.parent.mkdir(exist_ok=True)
        shutil.copy2(MODEL,path); HISTORY.append(path)
        if 'current' in SET_IDENTITIES:SET_IDENTITIES[str(path.relative_to(WORK))]=list(SET_IDENTITIES['current'])
        # Keep old history files on disk; only cap the visible undo chain.
        del HISTORY[:-40]
    FUTURE.clear()
    if set_count is not None:
        from native_set_identity import transfer
        transfer(set_count,set_order,SET_IDENTITIES)
    else:SET_IDENTITIES.pop('current',None)
    os.replace(candidate,MODEL)
    REVISION=uuid.uuid4().hex
    LAST_EDIT_GROUP=(history_group,REVISION) if history_group is not None else None
    save_session()


def mutation(req):
    with LOCK:
        check_revision(req.get('revision'))
        history_group=None
        if req.get('editGesture') is not None:
            token=req['editGesture']
            if not isinstance(token,str) or not re.fullmatch(r'[0-9a-f]{32}',token) or req.get('operation') not in ('parameter','design-assist','cst-coefficients'):
                raise ValueError('Invalid live modeling edit gesture.')
            values=('upper','lower') if req.get('operation')=='cst-coefficients' else ('value',)
            target={k:v for k,v in req.items() if k not in (*values,'revision','editGesture')}
            history_group=(token,json.dumps(target,sort_keys=True))
        folder=WORK/'transactions'/uuid.uuid4().hex; folder.mkdir(parents=True)
        candidate=folder/'aircraft.vsp3'; shutil.copy2(MODEL,candidate)
        data=invoke(dict(req,action='mutate'),candidate,folder)
        commit(candidate,history_group,set_count=len(data['tools']['sets']),set_order=req.get('order') if req.get('operation')=='set-reorder' else None)
        return state_meta(data)


def import_model(content,revision):
    if len(content)>50_000_000: raise ValueError('Model is larger than 50 MB.')
    # Check the native format before loading arbitrary content into OpenVSP.
    import xml.etree.ElementTree as ET
    if b'<!DOCTYPE' in content.upper(): raise ValueError('Document type declarations are not supported.')
    root=ET.fromstring(content)
    if root.tag!='Vsp_Geometry': raise ValueError('Choose a native OpenVSP .vsp3 file.')
    with LOCK:
        check_revision(revision)
        folder=WORK/'imports'/uuid.uuid4().hex; folder.mkdir(parents=True)
        candidate=folder/'aircraft.vsp3'; candidate.write_bytes(content)
        data=invoke({'action':'state'},candidate,folder)
        commit(candidate)
        return state_meta(data)


def undo(redo=False, revision=None):
    global REVISION
    with LOCK:
        check_revision(revision)
        source,target=(FUTURE,HISTORY) if redo else (HISTORY,FUTURE)
        if not source: raise ValueError('No more history.')
        path=WORK/'history'/f'{uuid.uuid4().hex}.vsp3'; path.parent.mkdir(exist_ok=True)
        shutil.copy2(MODEL,path); target.append(path)
        if 'current' in SET_IDENTITIES:SET_IDENTITIES[str(path.relative_to(WORK))]=list(SET_IDENTITIES['current'])
        previous=source.pop();ids=SET_IDENTITIES.get(str(previous.relative_to(WORK)))
        if ids is None:SET_IDENTITIES.pop('current',None)
        else:SET_IDENTITIES['current']=list(ids)
        shutil.copy2(previous,MODEL); REVISION=uuid.uuid4().hex
        save_session()
        return state()


def schema(name,structure=None):
    with LOCK:
        data=invoke({'action':'schema','name':name,'structure':structure},MODEL,WORK/'schemas'/uuid.uuid4().hex)
        if name in ('CpSlicer','VSPAEROReadPreviousAnalysis','FlowPlaneSlicer'):
            data['savedSolutions']=[{**j,'pressureFiles':[f['name'] for f in artifacts(j['id']) if f['aeroPreview']]} for j in list_jobs() if j['status']=='complete' and any(f['aeroPreview'] for f in artifacts(j['id']))]
        return data


def start_job(req, *, model_source=None, source_revision=None, study_context=None, inherited_locks=()):
    with LOCK:
        if model_source is None:check_revision(req.get('revision'))
        if RUN_RESERVATION and study_context!=RUN_RESERVATION:raise ValueError('A design study is running. Finish or cancel it first.')
        if any(j['status']=='running' for j in list_jobs()): raise ValueError('An analysis is already running. Wait for it or cancel it first.')
        source=req.get('sourceRun')
        source_job=None
        if req['name'] in ('CpSlicer','VSPAEROReadPreviousAnalysis','FlowPlaneSlicer') and not source:
            raise ValueError('Choose a completed saved aerodynamic solution before reading results or creating pressure slices.')
        if source:
            if req['name'] not in ('CpSlicer','VSPAEROReadPreviousAnalysis','FlowPlaneSlicer'):
                raise ValueError('Saved solution inputs are supported for pressure slices and reading previous aerodynamic results.')
            source_job=job_state(source)
            if source_job['status']!='complete':raise ValueError('Choose a completed native aerodynamic solution.')
            if not any(f['aeroPreview'] for f in source_job['artifacts']):raise ValueError('This run contains no native pressure database.')
        jid=uuid.uuid4().hex; folder=WORK/'jobs'/jid; folder.mkdir(parents=True)
        model=folder/'aircraft.vsp3'
        if source_job:
            for file in job_folder(source).iterdir():
                if file.is_file() and not file.is_symlink() and not file.name.startswith('.') and (file.suffix!='.json' or file.name.endswith('.studio-state.json')) and file.name!='engine.log' and not (req['name']=='FlowPlaneSlicer' and re.fullmatch(r'.+\.case\.-?\d+\.quad\.\d+\.dat',file.name)):
                    shutil.copy2(file,folder/file.name)
        else:shutil.copy2(model_source or MODEL,model)
        job=dict(id=jid,name=req['name'],status='running',started=time.time(),revision=source_revision or REVISION)
        if study_context:job.update(study=study_context[0],batch=study_context[1],case=req.get('studyCase'),stage=req.get('studyStage'),attempt=req.get('studyAttempt'))
        if source_job:job.update(sourceRun=source,revision=source_job['revision'])
        JOBS[jid]=job
        request=dict(req,action='analysis',revision=job['revision'])
        if req['name']=='FlowPlaneSlicer' and source_job:
            request['sourceSolverInputs']=source_job.get('result',{}).get('inputs',source_job.get('analysisSetup',{}).get('inputs',[]))
        if study_context:request.update(studyID=study_context[0],studyBatch=study_context[1])
        log=(folder/'engine.log').open('w')
        run_lock=None;engine_lock=None
        try:
            if not study_context:run_lock=acquire_run_lock(WORK/'run.lock')
            engine_lock=acquire_run_lock(folder/'.engine.lock')
            process,response=invoke(request,model,folder,log=log,inherited_locks=(*inherited_locks,*([run_lock] if run_lock else []),engine_lock))
        except Exception:
            log.close();JOBS.pop(jid,None);raise
        finally:
            if run_lock:run_lock.close()
            if engine_lock:engine_lock.close()
        job['_process']=process
        job['processID']=process.pid
        save_job(job)
        def finish():
            try:
                code=process.wait(timeout=1800)
                with LOCK:
                    job['exitCode']=code
                    if code<0:
                        import signal
                        try:job['terminationSignal']=signal.Signals(-code).name
                        except ValueError:job['terminationSignal']='signal '+str(-code)
                    if job['status']=='cancelled': return
                    stopped='OpenVSP stopped before producing results'
                    if job.get('terminationSignal'):stopped+=' ('+job['terminationSignal']+')'
                    elif code:stopped+=' (exit code '+str(code)+')'
                    data=json.loads(response.read_text()) if response.exists() else {'error':stopped+'. Inspect the saved aircraft and run log.'}
                    if code or 'error' in data: job.update(status='failed',error=data.get('error','Engine failed.'))
                    else: job.update(status='complete',result=data)
            except subprocess.TimeoutExpired:
                import signal
                os.killpg(process.pid,signal.SIGTERM)
                with LOCK:job.update(status='failed',error='Analysis exceeded the 30-minute limit. The process was stopped.')
            finally:
                log.close()
                with LOCK:job['finished']=time.time();save_job(job)
        threading.Thread(target=finish,daemon=True).start()
        return job_state(jid)


def job_folder(jid):
    if not isinstance(jid,str) or not re.fullmatch(r'[a-f0-9]{32}',jid):raise ValueError('Invalid run ID.')
    path=WORK/'jobs'/jid
    if not path.is_dir() or path.is_symlink():raise ValueError('Unknown analysis run.')
    return path


def save_job(job):
    folder=job_folder(job['id']);path=folder/'job.json'
    data={k:v for k,v in job.items() if not k.startswith('_') and k!='result'}
    temp=folder/'job.json.tmp';temp.write_text(json.dumps(data));os.replace(temp,path)


def load_job(jid):
    folder=job_folder(jid);request=json.loads((folder/'request.json').read_text())
    meta=folder/'job.json'
    job=json.loads(meta.read_text()) if meta.exists() else dict(id=jid,name=request.get('name','Analysis'),revision=request.get('revision','unknown'),started=(folder/'request.json').stat().st_mtime,status='running' if lock_is_held(folder/'.engine.lock') else 'interrupted')
    if request.get('studyID'):job.update(study=request['studyID'],batch=request['studyBatch'],case=request['studyCase'],stage=request['studyStage'],attempt=request.get('studyAttempt'))
    if not job.get('processID') and (folder/'.engine-owner.json').is_file():job['processID']=json.loads((folder/'.engine-owner.json').read_text())['pid']
    result_path=folder/'response.json'
    if result_path.exists():
        result=json.loads(result_path.read_text())
        if job.get('status') not in ('cancelled','failed'):
            if 'error' in result:job.update(status='failed',error=result['error'])
            else:job.update(status='complete',result=result)
    elif job.get('status')=='running' and not lock_is_held(folder/'.engine.lock'):job.update(status='interrupted',error='The engine process ended before this run produced results.')
    JOBS[jid]=job
    return job


def list_jobs():
    with LOCK:
        for folder in (WORK/'jobs').glob('*'):
            if folder.name not in JOBS:
                try:load_job(folder.name)
                except (ValueError,OSError,KeyError):continue
        for jid,j in list(JOBS.items()):
            if j['status']=='running' and '_process' not in j:load_job(jid)
        return [dict((k,v) for k,v in j.items() if k in ('id','name','status','started','finished','revision','error','study','batch','case','stage','attempt')) for j in sorted(JOBS.values(),key=lambda j:j['started'],reverse=True)]


def artifacts(jid):
    folder=job_folder(jid)
    return [dict(name=p.name,size=p.stat().st_size,preview=p.suffix.lower()=='.msh',
                 theoryPreview=p.name.endswith('.theory.json'),
                 aeroPreview=p.suffix.lower()=='.adb',flowPreview=bool(re.fullmatch(r'.+\.case\.-?\d+\.quad\.\d+\.dat',p.name)))
            for p in sorted(folder.iterdir()) if p.is_file() and not p.is_symlink() and not p.name.startswith('.') and p.name not in ('job.json','job.json.tmp','response.json.tmp')]


def artifact_file(jid,filename):
    folder=job_folder(jid)
    if not isinstance(filename,str) or Path(filename).name!=filename or filename.startswith('.') or filename in ('job.json','job.json.tmp','response.json.tmp'):raise ValueError('Invalid run filename.')
    path=folder/filename
    if path.is_symlink() or not path.is_file() or path.resolve().parent!=folder.resolve():raise ValueError('Run file not found.')
    return path


def mesh_preview(jid,filename):
    path=artifact_file(jid,filename)
    if path.suffix.lower()!='.msh':raise ValueError('Choose a native Gmsh mesh for preview.')
    result=job_state(jid).get('result') or {}
    companion=None
    if result.get('analysis') in ('FeaMeshAnalysis','FeaAssemblyMesh') and 'NASTRAN' in result.get('formats',[]):
        companion=artifact_file(jid,path.with_suffix('.bdf').name)
    mesh=read_gmsh(path,companion)
    if result.get('analysis')=='CfdMeshAnalysis':mesh['displayNote']='This is the native CFD mesh from the saved run. Review its native problem-geometry checks and engine log; mesh generation alone does not establish quality or solver suitability.'
    return mesh


def theory_preview(jid,filename):
    path=artifact_file(jid,filename)
    if not filename.endswith('.theory.json'):raise ValueError('Choose a saved native reference preview.')
    if path.stat().st_size>30_000_000:raise ValueError('Reference preview is too large; download its native samples.')
    return json.loads(path.read_text())


def aero_preview(jid,filename,case=1):
    path=artifact_file(jid,filename)
    if path.suffix.lower()=='.adb':
        artifact_file(jid,filename+'.cases')
        return read_adb(path,case)
    if re.fullmatch(r'.+\.case\.-?\d+\.quad\.\d+\.dat',filename):
        return read_flow_plane(path)
    raise ValueError('Choose a native pressure database or flow plane.')


def result_csv(jid):
    job=job_state(jid)
    if job['status']!='complete':raise ValueError('This run has no completed results.')
    out=io.StringIO();writer=csv.writer(out);writer.writerow(['result','result_index','field','field_index','sample','value'])
    for r in job['result']['results']:
        for e in r['entries']:
            for i,value in enumerate(e['values']):
                row=[r['name'],r['index'],e['name'],e['index'],i,json.dumps(value) if isinstance(value,(list,dict)) else value]
                writer.writerow(["'"+x if isinstance(x,str) and x.startswith(('=','+','-','@')) else x for x in row])
    return out.getvalue().encode()


def job_state(jid):
    if jid not in JOBS or (JOBS[jid]['status']=='running' and '_process' not in JOBS[jid]):load_job(jid)
    job=JOBS[jid]
    data={k:v for k,v in job.items() if not k.startswith('_')}
    folder=job_folder(jid)
    setup=folder/'analysis-setup.json'
    if setup.is_file() and not setup.is_symlink():
        data['analysisSetup']=json.loads(setup.read_text())
    elif (folder/'request.json').is_file():
        request=json.loads((folder/'request.json').read_text())
        if request.get('inputs') or request.get('memberInputs'):
            data['requestedSetup']={k:request[k] for k in ('inputs','memberInputs','geometryInputs','structure','formats') if k in request}
            data['requestedSetup'].setdefault('inputs',[])
    if data.get('name') in ('VSPAEROSweep','VSPAEROSinglePoint') and data.get('status')=='complete' and data.get('result') and 'solverSetup' not in data['result']:
        import native_solver_setup
        try:setup=native_solver_setup.read(job_folder(jid))
        except (ValueError,OSError,UnicodeError) as exc:setup=dict(available=False,note='Unable to inspect this saved native setup: '+str(exc))
        # Older results acquire a read-only view; their saved response stays exact.
        data['result']={**data['result'],'solverSetup':setup}
    data['artifacts']=artifacts(jid)
    path=WORK/'jobs'/jid/'engine.log'
    if path.exists():
        with path.open('rb') as f:
            f.seek(max(0,path.stat().st_size-14000)); data['log']=f.read().decode(errors='replace')
    if job['status']!='running':
        import native_diagnostics
        data['diagnostics']=native_diagnostics.saved(path)
    return data


def cancel_job(jid):
    import signal
    with LOCK:
        job_state(jid);job=JOBS[jid]
        if job['status']=='running':
            process=job.get('_process');pid=process.pid if process else job.get('processID')
            if not process and (not pid or not lock_is_held(job_folder(jid)/'.engine.lock')):raise ValueError('The native process is no longer running.')
            job['status']='cancelled'
            try: os.killpg(pid,signal.SIGTERM)
            except ProcessLookupError: pass
            save_job(job)
        return job_state(jid)


def native_open():
    global NATIVE_PROCESS
    with LOCK:
        if NATIVE_PROCESS and NATIVE_PROCESS.poll() is None:
            return {'message':'The native OpenVSP window is already open. Save there, then use Bring back native edits.'}
        home=distribution()
        if not home or not (home/'vsp').exists(): raise ValueError('The native OpenVSP application could not be found.')
        folder=WORK/'native'; folder.mkdir(exist_ok=True)
        shutil.copy2(MODEL,folder/'aircraft.vsp3')
        with (folder/'launch.log').open('w') as log:
            bundle=ROOT/'.runtime/OpenVSP Native.app'
            command=['/usr/bin/open','-W','-n','-a',str(bundle)] if bundle.exists() else [str(home/'vsp'),'aircraft.vsp3']
            NATIVE_PROCESS=subprocess.Popen(command,cwd=folder,stdout=log,stderr=log)
        return {'message':'Opened the current model in native OpenVSP. Save in that window, then bring its edits back here.'}


def native_sync(revision):
    path=WORK/'native/aircraft.vsp3'
    if not path.exists(): raise ValueError('Open the model in native OpenVSP first.')
    return import_model(path.read_bytes(),revision)


def export_geometry(req):
    with LOCK:
        check_revision(req.get('revision'))
        folder=WORK/'exports'/uuid.uuid4().hex;folder.mkdir(parents=True)
        path=folder/'source.vsp3';shutil.copy2(MODEL,path)
        data=invoke(dict(req,action='export-geometry'),path,folder)
        files=data.get('files',[data['filename']])
        if len(files)==1:
            result=folder/files[0]
            return result.name,result.read_bytes()
        import zipfile
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
            for file in files:
                result=folder/file
                if result.is_symlink() or not result.resolve().is_relative_to(folder.resolve()):raise ValueError('Invalid native export path.')
                bundle.write(result,result.name)
        label='polygon-vspgeom' if req.get('kind')=='polygon-mesh' else req['format'].lower()
        return 'openvsp-'+label+'.zip',archive.getvalue()


def query(req):
    with LOCK:
        check_revision(req.get('revision'))
        identifier=uuid.uuid4().hex;folder=WORK/'queries'/identifier
        data=invoke(dict(req,action='query'),MODEL,folder)
        if req.get('operation')=='cloud-fit-plane':
            record=dict(operation=req['operation'],revision=REVISION,engineVersion=data['engineVersion'],request=req,data=data)
            (folder/'plane.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
            output=io.StringIO(newline='');writer=csv.writer(output)
            writer.writerow(['Point','X','Y','Z','SignedOffset'])
            writer.writerows([i+1,*point,data['signedOffsets'][i]] for i,point in enumerate(data['points']))
            (folder/'plane.csv').write_bytes(output.getvalue().encode())
            data['exports']={fmt:'/api/query-export?id='+identifier+'&format='+fmt for fmt in ('json','csv')}
        return data


def query_export(identifier,format):
    if not isinstance(identifier,str) or not re.fullmatch(r'[0-9a-f]{32}',identifier):raise ValueError('Invalid saved query.')
    if format not in ('json','csv'):raise ValueError('Choose JSON or CSV.')
    folder=WORK/'queries'/identifier;path=folder/('plane.'+format)
    if folder.is_symlink() or path.is_symlink() or not path.is_file() or folder.resolve().parent!=(WORK/'queries').resolve():raise ValueError('Saved query export not found.')
    return path.read_bytes(),('application/json' if format=='json' else 'text/csv'),'native-cloud-plane.'+format
