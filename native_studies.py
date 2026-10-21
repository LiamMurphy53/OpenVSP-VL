"""Persistent, isolated native design studies and exact result comparisons.

This module schedules native workers. It never evaluates engineering math.
"""
import copy
import csv
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
import zipfile
import native_service as service

RUNNERS={}


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{32}',value):raise ValueError('Invalid study ID.')
    return value


def study_folder(sid):
    path=service.WORK/'studies'/identifier(sid)
    if not path.is_dir() or path.is_symlink():raise ValueError('Unknown saved study.')
    return path


def batch_folder(sid,bid):
    path=study_folder(sid)/'batches'/identifier(bid)
    if not path.is_dir() or path.is_symlink():raise ValueError('Unknown study execution.')
    return path


def write_json(path,data):
    temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(data,allow_nan=False));os.replace(temp,path)


def read_json(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def study_schema(sid=None):
    with service.LOCK:
        source=study_folder(sid)/'aircraft.vsp3' if sid else service.MODEL
        return service.invoke(dict(action='study-schema'),source,service.WORK/'study-schemas'/uuid.uuid4().hex)


def analysis_schema(sid,name,structure=None):
    with service.LOCK:
        source=study_folder(sid)/'aircraft.vsp3' if sid else service.MODEL
        return service.invoke(dict(action='schema',name=name,structure=structure),source,service.WORK/'study-schemas'/uuid.uuid4().hex)


def save_study(req):
    from native_tools import name
    title=name(req.get('name'));notes=req.get('description','')
    if not isinstance(notes,str) or len(notes)>10000:raise ValueError('Use a description up to 10000 characters.')
    with service.LOCK:
        service.check_revision(req.get('revision'))
        sid=identifier(req['id']) if req.get('id') else uuid.uuid4().hex
        folder=study_folder(sid) if req.get('id') else service.WORK/'studies'/sid
        folder.mkdir(parents=True,exist_ok=True)
        validation=folder/'validation'/uuid.uuid4().hex;validation.mkdir(parents=True)
        if req.get('id') and req.get('definitionVersion')!=definition(sid)['version']:raise ValueError('This study was edited in another window. Reopen its latest definition.')
        source_plan=definition(sid) if req.get('id') else None
        current_state=service.state()
        current_ids=[s['identity'] for s in current_state['tools']['sets']]
        selector_ids={r['id'] for r in current_state['tools']['setConfig']['references'] if 'group' not in r}
        saved_baseline=bool(req.get('id') and req.get('baseline')=='saved')
        previous=source_plan if saved_baseline else None
        if source_plan and not saved_baseline and req.get('setIdentities')!=current_ids:
            from native_study_sets import rebind
            _,_,set_matches=rebind(source_plan.get('setIdentities'),current_ids,req.get('stages',[]),req.get('axes',[]),selector_ids)
            if any(m['changed'] for m in set_matches):raise ValueError('Geometry sets moved. Review the current aircraft before replacing this study baseline.')
        candidate=validation/'aircraft.vsp3';shutil.copy2(folder/'aircraft.vsp3' if saved_baseline else service.MODEL,candidate)
        data=service.invoke(dict(action='study-validate',stages=req.get('stages'),axes=req.get('axes')),candidate,validation)
        plan=dict(id=sid,name=title,description=notes,version=uuid.uuid4().hex,updated=time.time(),
                        sourceRevision=previous['sourceRevision'] if previous else service.REVISION,sourceHash=digest(candidate),engineVersion=data['version'],
                        setIdentities=previous.get('setIdentities') if previous else current_ids,axes=data['axes'],stages=data['stages'],stageSchemas=data['stageSchemas'],caseCount=data['caseCount'],continueOnError=bool(req.get('continueOnError',True)))
        # Older executions keep their own definition and baseline aircraft.
        os.replace(candidate,folder/'aircraft.vsp3');write_json(folder/'definition.json',plan)
        return plan


def rebind_current_aircraft(req):
    """Preview exact rotor matches without changing a saved study or aircraft."""
    with service.LOCK:
        service.check_revision(req.get('revision'))
        sid=identifier(req.get('id'));plan=definition(sid)
        if req.get('definitionVersion')!=plan['version']:raise ValueError('This study was edited in another window. Reopen its latest definition.')
        old=study_schema(sid);current=study_schema()
        current_state=service.state();current_ids=[s['identity'] for s in current_state['tools']['sets']]
        selector_ids={r['id'] for r in current_state['tools']['setConfig']['references'] if 'group' not in r}
        original={p['id']:p for p in old['parameters']};available={p['id']:p for p in current['parameters']}
        axes=copy.deepcopy(req.get('axes',plan['axes']))
        if not isinstance(axes,list) or len(axes)>10:raise ValueError('Use up to ten study dimensions.')
        matches=[]
        for i,a in enumerate(axes):
            if not isinstance(a,dict):raise ValueError('Choose known study fields.')
            if a.get('kind')!='parameter':continue
            source=original.get(a.get('id'));target=available.get(a.get('id'))
            if source and source.get('rotorBinding'):
                targets=[p for p in current['parameters'] if p.get('rotorBinding')==source['rotorBinding']]
                if len(targets)!=1:raise ValueError(source['label']+': no unique current rotor has the same component and native surface membership. Restore its representation, selection and symmetry first.')
                target=targets[0]
            elif not target:raise ValueError('A study parameter has no matching current native field. Choose its replacement explicitly.')
            if source and source.get('rotorBinding') and target.get('editable') is False:raise ValueError(target['label']+': '+target['readOnlyReason']+' Choose an editable current driver.')
            matches.append(dict(axis=i,oldId=a['id'],id=target['id'],oldLabel=source['label'] if source else a.get('label',a['id']),label=target['label'],changed=a['id']!=target['id']))
            a['id']=target['id']
        from native_study_sets import rebind
        stages,axes,set_matches=rebind(req.get('setIdentities',plan.get('setIdentities')),current_ids,req.get('stages',plan['stages']),axes,selector_ids)
        folder=service.WORK/'study-schemas'/uuid.uuid4().hex
        data=service.invoke(dict(action='study-validate',axes=axes,stages=stages),service.MODEL,folder)
        return dict(axes=data['axes'],stages=data['stages'],stageSchemas=data['stageSchemas'],schema=current,matches=matches,setMatches=set_matches,setIdentities=current_ids,revision=service.REVISION,sourceHash=digest(service.MODEL))


def definition(sid):return read_json(study_folder(sid)/'definition.json')


def list_studies():
    with service.LOCK:
        result=[]
        for path in (service.WORK/'studies').glob('*/definition.json'):
            try:
                data=definition(path.parent.name);data['executions']=list_batches(data['id']);result.append(data)
            except (ValueError,OSError,KeyError):continue
        return sorted(result,key=lambda d:d['updated'],reverse=True)


def cases_for(plan):
    cases=[]
    for index,values in enumerate(itertools.product(*(a['values'] for a in plan['axes']))):
        cases.append(dict(index=index,label=f'Case {index+1:03d}',values=list(values),status='pending',
                          stages=[dict(index=i,name=s['name'],status='pending',attempts=[]) for i,s in enumerate(plan['stages'])]))
    return cases


def case_stages(plan,case):
    stages=copy.deepcopy(plan['stages'])
    for axis,value in zip(plan['axes'],case['values']):
        if axis['kind']=='parameter':continue
        # Resolve partial arrays against each case's actual native defaults in
        # its worker. Untouched elements must not be frozen to the saved model.
        patch=dict(kind=axis['kind'],name=axis['name'],index=axis['index'],valueMode=axis.get('valueMode','element'),element=axis.get('element',0),component=axis.get('component'),value=copy.deepcopy(value))
        if axis.get('member') is not None:patch['member']=axis['member']
        stages[axis['stage']].setdefault('inputSweeps',[]).append(patch)
    return stages


def mark_unstarted_steps(case):
    # A rejected aircraft or failed earlier step leaves no calculation queued.
    # Preserve actual attempts and distinguish unstarted steps from pending work.
    for stage in case['stages']:
        if not stage.get('job') and stage['status'] in ('pending','starting'):
            stage['status']='not-run'


def reconcile(batch):
    jobs=service.list_jobs()
    for case in batch['cases']:
        for stage in case['stages']:
            if stage.get('attemptToken'):
                candidate=next((j for j in jobs if j.get('study')==batch['study'] and j.get('batch')==batch['id'] and j.get('case')==case['index'] and j.get('stage')==stage['index'] and j.get('attempt')==stage['attemptToken']),None)
                if candidate:
                    stage['job']=candidate['id']
                    if candidate['id'] not in stage['attempts']:stage['attempts'].append(candidate['id'])
            if not stage.get('job'):continue
            try:
                job=service.job_state(stage['job']);stage['status']=job['status']
                if job.get('error'):stage['error']=job['error']
                else:stage.pop('error',None)
            except ValueError:stage.update(status='interrupted',error='The saved native run could not be found.')
        if case['status']=='failed':mark_unstarted_steps(case)
        statuses=[s['status'] for s in case['stages']]
        if all(s=='complete' for s in statuses):case['status']='complete';case.pop('error',None)
        elif 'running' in statuses:case['status']='running'
        elif any(s in ('failed','cancelled','interrupted') for s in statuses):case['status']='failed'
    return batch


def batch_state(sid,bid):
    with service.LOCK:
        folder=batch_folder(sid,bid);batch=reconcile(read_json(folder/'batch.json'))
        live=service.lock_is_held(folder/'.batch.lock')
        if all(c['status']=='complete' for c in batch['cases']):batch['status']='complete'
        elif batch['status'] in ('running','cancelling') and not live:
            batch['status']='cancelled' if batch.get('cancelRequested') else 'interrupted'
        batch['live']=live;batch['completed']=sum(c['status']=='complete' for c in batch['cases']);batch['failed']=sum(c['status']=='failed' for c in batch['cases'])
        if not live:write_json(folder/'batch.json',{k:v for k,v in batch.items() if k!='live'})
        return batch


def list_batches(sid):
    result=[]
    for folder in (study_folder(sid)/'batches').glob('*'):
        try:
            b=batch_state(sid,folder.name);result.append({k:b[k] for k in ('id','study','status','started','completed','failed')})
        except (ValueError,OSError,KeyError):continue
    return sorted(result,key=lambda b:b['started'],reverse=True)


def launch(sid,bid=None):
    with service.LOCK:
        sid=identifier(sid);plan=definition(sid)
        if bid:
            folder=batch_folder(sid,bid);batch=batch_state(sid,bid)
            if batch['live']:return batch
            if batch['status']=='complete':return batch
        else:
            bid=uuid.uuid4().hex;folder=study_folder(sid)/'batches'/bid;folder.mkdir(parents=True)
            batch=dict(id=bid,study=sid,name=plan['name'],started=time.time(),status='pending',plan=plan,cases=cases_for(plan))
            shutil.copy2(study_folder(sid)/'aircraft.vsp3',folder/'aircraft.vsp3');write_json(folder/'batch.json',batch)
        if any(j['status']=='running' for j in service.list_jobs()):raise ValueError('A native analysis is still running. Let it finish or cancel it before starting this study.')
        run_lock=service.acquire_run_lock(service.WORK/'run.lock')
        try:batch_lock=service.acquire_run_lock(folder/'.batch.lock')
        except Exception:run_lock.close();raise
        if digest(folder/'aircraft.vsp3')!=batch['plan']['sourceHash']:
            run_lock.close();batch_lock.close();raise ValueError('The saved study baseline changed. Save a new study from a verified aircraft.')
        context=(sid,bid);service.RUN_RESERVATION=context
        batch.pop('live',None);batch.pop('error',None);batch.update(status='running',cancelRequested=False,lastResumed=time.time())
        # Completed steps keep their original job, model and exact native results.
        for case in batch['cases']:
            if case['status']!='complete':
                case['status']='pending';case.pop('error',None)
                for stage in case['stages']:
                    if stage['status']!='complete':
                        stage['status']='pending';stage.pop('error',None);stage.pop('job',None);stage.pop('attemptToken',None)
        write_json(folder/'batch.json',batch)
        thread=threading.Thread(target=execute,args=(batch,folder,run_lock,batch_lock),daemon=True);RUNNERS[context]=thread;thread.start()
        return batch_state(sid,bid)


def execute(batch,folder,run_lock,batch_lock):
    sid=batch['study'];bid=batch['id'];context=(sid,bid);plan=batch['plan'];locks=(run_lock,batch_lock)
    def cancelled():return bool(read_json(folder/'batch.json').get('cancelRequested'))
    def save():
        with service.LOCK:
            batch['cancelRequested']=cancelled();write_json(folder/'batch.json',batch)
    try:
        for case in batch['cases']:
            if cancelled():break
            if case['status']=='complete':continue
            case_folder=folder/'cases'/str(case['index']);case_folder.mkdir(parents=True,exist_ok=True)
            case_model=case_folder/'aircraft.vsp3'
            case['status']='running';save()
            try:
                if not case.get('prepared'):
                    shutil.copy2(folder/'aircraft.vsp3',case_model)
                    params=[dict(id=a['id'],value=x) for a,x in zip(plan['axes'],case['values']) if a['kind']=='parameter']
                    case['prepared']=service.invoke(dict(action='study-model',parameters=params),case_model,case_folder,inherited_locks=locks)
                    case['modelHash']=digest(case_model);save()
                elif not case_model.is_file() or digest(case_model)!=case['modelHash']:raise ValueError('This case’s native aircraft changed. Start a new execution to rebuild it.')
                for stage,spec in zip(case['stages'],case_stages(plan,case)):
                    if cancelled():break
                    if stage['status']=='complete':continue
                    source=spec.pop('sourceStage',None)
                    if source is not None:spec['sourceRun']=case['stages'][source]['job']
                    stage.update(status='starting',attemptToken=uuid.uuid4().hex);save()
                    spec.update(studyCase=case['index'],studyStage=stage['index'],studyAttempt=stage['attemptToken'],studyParameters=[a['id'] for a in plan['axes'] if a['kind']=='parameter'])
                    with service.LOCK:
                        job=service.start_job(spec,model_source=case_model,source_revision=plan['sourceRevision'],study_context=context,inherited_locks=locks,set_identities=plan.get('setIdentities'))
                        stage.update(job=job['id'],status=job['status']);stage['attempts'].append(job['id']);save()
                    while job['status']=='running':
                        if cancelled():job=service.cancel_job(job['id'])
                        else:
                            time.sleep(.1)
                            with service.LOCK:job=service.job_state(job['id'])
                    stage['status']=job['status']
                    if job.get('error'):stage['error']=job['error']
                    save()
                    if job['status']!='complete':raise ValueError(job.get('error','The native run was '+job['status']+'.'))
                case['status']='cancelled' if cancelled() else 'complete';save()
            except Exception as exc:
                case.update(status='failed',error=str(exc))
                mark_unstarted_steps(case);save()
                if not plan['continueOnError']:break
        batch['status']='cancelled' if cancelled() else 'complete' if all(c['status']=='complete' for c in batch['cases']) else 'partial' if any(c['status']=='complete' for c in batch['cases']) else 'failed'
    except Exception as exc:batch.update(status='failed',error=str(exc))
    finally:
        batch['finished']=time.time()
        with service.LOCK:
            try:save()
            finally:
                if service.RUN_RESERVATION==context:service.RUN_RESERVATION=None
                RUNNERS.pop(context,None);batch_lock.close();run_lock.close()


def cancel(sid,bid):
    with service.LOCK:
        folder=batch_folder(sid,bid);batch=batch_state(sid,bid)
        if not batch['live']:return batch
        batch.pop('live',None);batch.update(cancelRequested=True,status='cancelling');write_json(folder/'batch.json',batch)
        for case in batch['cases']:
            for stage in case['stages']:
                if stage.get('job') and service.job_state(stage['job'])['status']=='running':service.cancel_job(stage['job'])
        return batch_state(sid,bid)


def result_fields(sid,bid):
    batch=batch_state(sid,bid);fields={}
    for case in batch['cases']:
        for stage in case['stages']:
            if stage['status']!='complete':continue
            data=service.job_state(stage['job'])['result']
            for r in data['results']:
                for e in r['entries']:
                    key=json.dumps([stage['index'],r['name'],r['index'],e['name'],e['index']],separators=(',',':'))
                    fields[key]=dict(key=key,stage=stage['index'],result=r['name'],resultIndex=r['index'],field=e['name'],fieldIndex=e['index'],type=e['type'],description=e.get('description',''),
                                     numeric=e['type'] in (1,2) and all(x is None or isinstance(x,(int,float)) for x in e['values']),samples=max(len(e['values']),fields.get(key,{}).get('samples',0)))
            for prop,label in [('nodes','Nodes'),('elements','Elements')]:
                value=data.get('meshSummary',{}).get(prop)
                if not isinstance(value,int) or isinstance(value,bool):continue
                key=json.dumps([stage['index'],'meshSummary',prop],separators=(',',':'))
                fields[key]=dict(key=key,stage=stage['index'],result='Saved native mesh',resultIndex=0,field=label,fieldIndex=0,type=1,numeric=True,samples=1,kind='meshSummary',property=prop,
                                 description=label+' recorded in this run’s original native mesh file. These counts describe mesh size; they do not establish mesh quality or convergence.')
            for item in data.get('flowPlanes',[]):
                for prop in ('X','Y','Z','Cp','U','V','W'):
                    key=json.dumps([stage['index'],'flowPlane',item['file'],prop],separators=(',',':'))
                    fields[key]=dict(key=key,stage=stage['index'],result='Native airflow · '+item['file'],resultIndex=0,field=prop,fieldIndex=0,type=2,numeric=True,samples=max(item['nodes'],fields.get(key,{}).get('samples',0)),kind='flowPlane',file=item['file'],property=prop,
                                     description='Original native nodal '+prop+' samples in file order. Plane positions and node locations can differ between cases; these samples are not interpolated onto common spatial points.')
    return sorted(fields.values(),key=lambda e:(e['stage'],e['result'],e['resultIndex'],e['field'],e['fieldIndex']))


def comparison(sid,bid,key):
    batch=batch_state(sid,bid);field=next((f for f in result_fields(sid,bid) if f['key']==key),None)
    if not field:raise ValueError('Choose a field returned by the native study runs.')
    rows=[]
    for case in batch['cases']:
        stage=case['stages'][field['stage']];values=None;locations=None
        if stage['status']=='complete':
            data=service.job_state(stage['job'])['result']
            if field.get('kind')=='meshSummary':
                value=data.get('meshSummary',{}).get(field['property'])
                if isinstance(value,int) and not isinstance(value,bool):values=[value]
            elif field.get('kind')=='flowPlane':
                if any(item['file']==field['file'] for item in data.get('flowPlanes',[])):
                    mesh=service.aero_preview(stage['job'],field['file'])
                    locations=mesh['nodes']
                    prop=field['property']
                    if prop in ('X','Y','Z'):values=[p['XYZ'.index(prop)] for p in mesh['nodes']]
                    else:values=next(e['nodeValues'] for e in mesh['fields'] if e['name']==prop)
            else:
                result=next((r for r in data['results'] if r['name']==field['result'] and r['index']==field['resultIndex']),None)
                entry=next((e for e in result['entries'] if e['name']==field['field'] and e['index']==field['fieldIndex']),None) if result else None
                if entry:values=entry['values']
        effective=[]
        for axis,requested in zip(batch['plan']['axes'],case['values']):
            value=None
            if axis['kind']=='parameter':
                if stage['status']=='complete':value=next((p['value'] for p in service.job_state(stage['job'])['result'].get('studyParameters',[]) if p['id']==axis['id']),None)
                else:value=next((p['effective'] for p in case.get('prepared',{}).get('parameters',[]) if p['id']==axis['id']),None)
            else:
                input_stage=case['stages'][axis['stage']]
                if input_stage.get('job') and input_stage['status']=='complete':
                    out=service.job_state(input_stage['job'])['result'];entries=out.get('inputs' if axis['kind']=='input' else 'geometryInputs',[])
                    if axis.get('member') is not None:
                        member=next((m for m in out.get('memberSizing',[]) if m['id']==axis['member']),None)
                        entries=member.get('inputs',[]) if member else []
                    e=next((e for e in entries if e['name']==axis['name'] and e.get('index',0)==axis['index']),None)
                    if e:
                        if axis.get('valueMode')=='array':value=copy.deepcopy(e['values'])
                        elif axis.get('element',0)<len(e['values']):
                            item=e['values'][axis.get('element',0)]
                            value=copy.deepcopy(item if axis.get('component') is None else item[axis['component']])
            effective.append(value)
        warnings=service.job_state(stage['job'])['result'].get('studyParameterWarnings',[]) if stage['status']=='complete' else []
        rows.append(dict(case=case['index'],label=case['label'],status=case['status'],stageStatus=stage['status'],job=stage.get('job'),requested=case['values'],effective=effective,values=values,error=case.get('error') or stage.get('error'),warnings=warnings,**(dict(sampleLocations=locations) if field.get('kind')=='flowPlane' else {})))
    return dict(id=bid,study=sid,name=batch['name'],field=field,axes=batch['plan']['axes'],sourceHash=batch['plan']['sourceHash'],sourceRevision=batch['plan']['sourceRevision'],rows=rows)


def csv_comparison(sid,bid,key):
    data=comparison(sid,bid,key);out=io.StringIO();writer=csv.writer(out)
    def safe(x):
        if isinstance(x,(list,dict)):x=json.dumps(x,separators=(',',':'))
        return "'"+x if isinstance(x,str) and x.startswith(('=','+','-','@')) else x
    spatial=data['field'].get('kind')=='flowPlane'
    writer.writerow(['case','status','stage_status','native_run',*[a['label']+' requested' for a in data['axes']],*[a['label']+' native' for a in data['axes']],'result','result_index','field','field_index','sample','value','native_setting_notes',*(['native_node_X','native_node_Y','native_node_Z'] if spatial else [])])
    for row in data['rows']:
        for i,value in enumerate(row['values'] if row['values'] is not None else [None]):
            location=(row.get('sampleLocations') or [])[i:i+1]
            writer.writerow([safe(x) for x in [row['label'],row['status'],row['stageStatus'],row['job'],*row['requested'],*row['effective'],data['field']['result'],data['field']['resultIndex'],data['field']['field'],data['field']['fieldIndex'],i,value,' | '.join(row.get('warnings',[])),*((location[0] if location else [None,None,None]) if spatial else [])]])
    return out.getvalue().encode()


def bundle(sid,bid=None):
    root=batch_folder(sid,bid) if bid else study_folder(sid);output=io.BytesIO()
    if bid and batch_state(sid,bid)['live']:raise ValueError('Finish or cancel the study before downloading its complete run bundle.')
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in ('aircraft.vsp3','batch.json' if bid else 'definition.json'):
            path=root/name
            if path.is_file():archive.write(path,name)
        if bid:
            batch=batch_state(sid,bid)
            for case in batch['cases']:
                model=root/'cases'/str(case['index'])/'aircraft.vsp3'
                if model.is_file():archive.write(model,f'cases/{case["index"]}/aircraft.vsp3')
                for stage in case['stages']:
                    for attempt,jid in enumerate(stage['attempts']):
                        for file in service.artifacts(jid):
                            path=service.artifact_file(jid,file['name']);archive.write(path,f'cases/{case["index"]}/step-{stage["index"]}/attempt-{attempt}/{path.name}')
    return output.getvalue()
