"""Local OpenVSP workspace, backed by the official engine."""
import json
import os
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote
import native_service as service
import native_studies as studies

ROOT=Path(__file__).resolve().parent

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT/'web'),**kwargs)

    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        super().end_headers()

    def reply(self,status,body,content_type='application/json',filename=None):
        data=json.dumps(body,allow_nan=False).encode() if content_type=='application/json' and not isinstance(body,bytes) else body
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if filename:self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(filename,safe=''))
        if content_type=='application/x-openvsp': self.send_header('Content-Disposition','attachment; filename="aircraft.vsp3"')
        self.end_headers(); self.wfile.write(data)

    def allowed(self):
        host=self.headers.get('Host','')
        valid=(f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
        return host in valid and self.headers.get('Origin') in (None,f'http://{host}')

    def do_GET(self):
        if not self.allowed(): return self.reply(403,{'error':'Use the local workspace address.'})
        url=urlparse(self.path)
        try:
            if url.path=='/api/health': return self.reply(200,{'application':'OpenVSP Studio','protocol':1,'root':str(ROOT),'workspace':str(service.WORK),'processID':os.getpid()})
            if url.path=='/api/state': return self.reply(200,service.state())
            if url.path=='/api/schema':
                q=parse_qs(url.query)
                return self.reply(200,studies.analysis_schema(q['study'][0],q['name'][0],q.get('structure',[None])[0]) if q.get('study') else service.schema(q['name'][0],q.get('structure',[None])[0]))
            if url.path=='/api/jobs': return self.reply(200,service.list_jobs())
            if url.path=='/api/studies':return self.reply(200,studies.list_studies())
            if url.path=='/api/study-schema':return self.reply(200,studies.study_schema(parse_qs(url.query).get('id',[None])[0]))
            if url.path=='/api/study':return self.reply(200,studies.definition(parse_qs(url.query)['id'][0]))
            if url.path in ('/api/study-batch','/api/study-fields','/api/study-compare','/api/study.csv','/api/study.zip'):
                q=parse_qs(url.query);sid=q['id'][0];bid=q.get('batch',[None])[0]
                if url.path=='/api/study-batch':return self.reply(200,studies.batch_state(sid,bid))
                if url.path=='/api/study-fields':return self.reply(200,studies.result_fields(sid,bid))
                if url.path=='/api/study-compare':return self.reply(200,studies.comparison(sid,bid,q['field'][0]))
                if url.path=='/api/study.csv':return self.reply(200,studies.csv_comparison(sid,bid,q['field'][0]),'text/csv','study-comparison.csv')
                return self.reply(200,studies.bundle(sid,bid),'application/zip','openvsp-study.zip')
            if url.path in ('/api/artifact','/api/mesh','/api/aero','/api/theory','/api/results.csv'):
                q=parse_qs(url.query);jid=q['id'][0]
                if url.path=='/api/mesh':return self.reply(200,service.mesh_preview(jid,q['file'][0]))
                if url.path=='/api/theory':return self.reply(200,service.theory_preview(jid,q['file'][0]))
                if url.path=='/api/aero':return self.reply(200,service.aero_preview(jid,q['file'][0],int(q.get('case',['1'])[0])))
                if url.path=='/api/results.csv':return self.reply(200,service.result_csv(jid),'text/csv','results.csv')
                path=service.artifact_file(jid,q['file'][0]);return self.reply(200,path.read_bytes(),'application/octet-stream',path.name)
            if url.path=='/api/query-export':
                q=parse_qs(url.query);body,kind,filename=service.query_export(q.get('id',[''])[0],q.get('format',[''])[0]);return self.reply(200,body,kind,filename)
            if url.path=='/api/job': return self.reply(200,service.job_state(parse_qs(url.query)['id'][0]))
            if url.path=='/api/export':
                with service.LOCK: return self.reply(200,service.MODEL.read_bytes(),'application/x-openvsp')
            if url.path.startswith('/api/'): return self.reply(404,{'error':'Unknown endpoint.'})
            # This is a local editable workspace. Always serve the current UI,
            # including imported modules, instead of retaining stale editors.
            if 'If-Modified-Since' in self.headers:del self.headers['If-Modified-Since']
            super().do_GET()
        except Exception as exc: self.reply(400,{'error':str(exc)})

    def do_POST(self):
        if not self.allowed(): return self.reply(403,{'error':'Cross-origin requests are not allowed.'})
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=70_000_000: raise ValueError('Invalid request size.')
            req=json.loads(self.rfile.read(length))
            if self.path=='/api/export-geometry':
                filename,data=service.export_geometry(req)
                return self.reply(200,data,'application/octet-stream',filename)
            routes={
                '/api/query':lambda:service.query(req),
                '/api/mutate':lambda:service.mutation(req),
                '/api/undo':lambda:service.undo(revision=req.get('revision')),
                '/api/redo':lambda:service.undo(True,revision=req.get('revision')),
                '/api/import':lambda:service.import_model(req['content'].encode(),req.get('revision')),
                '/api/run':lambda:service.start_job(req),
                '/api/cancel':lambda:service.cancel_job(req['id']),
                '/api/study-save':lambda:studies.save_study(req),
                '/api/study-rebind':lambda:studies.rebind_current_aircraft(req),
                '/api/study-start':lambda:studies.launch(req['id']),
                '/api/study-resume':lambda:studies.launch(req['id'],req['batch']),
                '/api/study-cancel':lambda:studies.cancel(req['id'],req['batch']),
                '/api/native/open':service.native_open,
                '/api/native/sync':lambda:service.native_sync(req.get('revision')),
            }
            if self.path not in routes: return self.reply(404,{'error':'Unknown endpoint.'})
            self.reply(200,routes[self.path]())
        except Exception as exc: self.reply(400,{'error':str(exc)})

if __name__=='__main__':
    try:workspace_server_lock=service.acquire_run_lock(service.WORK/'server.lock')
    except ValueError:
        raise SystemExit('Another Studio server already uses this workspace. Open that server or choose a different OPENVSP_WORKSPACE.')
    service.restore_session()
    port=int(os.environ.get('PORT','8765'))
    print(f'OpenVSP workspace → http://127.0.0.1:{port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
