"""Launch the local modern workspace using the installed official engine."""
import argparse
import html
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.error import URLError
import webbrowser
from vsp_runtime import ROOT,distribution,interpreter
_started_processes={}


def health(port,workspace):
    workspace=Path(workspace).expanduser().resolve()
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/health',timeout=.5) as response:
            data=json.load(response)
        return data if (data.get('application')=='OpenVSP Studio' and data.get('protocol')==1
                        and data.get('root')==str(ROOT) and data.get('workspace')==str(workspace)) else None
    except (URLError,TimeoutError,OSError,ValueError):return None


def check_runtime():
    home=distribution()
    if not home or not (home/'python/openvsp').is_dir():
        raise ValueError('The official OpenVSP runtime is missing. Restore this Studio installation’s .runtime folder or set OPENVSP_HOME to an installed distribution.')
    python=interpreter()
    try:
        probe="""from vsp_runtime import load
from native_preview import symmetry_count
v=load()
g=v.AddGeom('BLANK')
v.Update()
if symmetry_count(v,g)!=1:
    raise ValueError('Native modeling adapter returned an invalid startup result.')
v.DeleteGeom(g)
print('STUDIO_ADAPTER=ready')
print('STUDIO_ENGINE='+v.GetVSPVersion())
"""
        result=subprocess.run([python,'-c',probe],cwd=ROOT,capture_output=True,text=True,timeout=120)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ValueError('The native Python runtime could not start. Restore the matching Python runtime or set OPENVSP_PYTHON.') from exc
    version=next((line.removeprefix('STUDIO_ENGINE=') for line in result.stdout.splitlines() if line.startswith('STUDIO_ENGINE=')),None)
    if result.returncode or not version or 'STUDIO_ADAPTER=ready' not in result.stdout.splitlines():
        raise ValueError('Studio’s native engine or modeling adapter could not load. Check the matching Python/engine installation and native adapter build requirements.\n'+result.stderr[-1500:])
    return version


def start(port,workspace,timeout=35):
    workspace=Path(workspace).expanduser().resolve();workspace.mkdir(parents=True,exist_ok=True)
    existing=health(port,workspace)
    if existing:return existing,False
    # Serialize launch attempts; server.lock separately protects a workspace
    # across different ports for servers started by this version.
    import fcntl
    with (workspace/'launcher.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        existing=health(port,workspace)
        if existing:return existing,False
        with socket.socket() as probe:
            try:probe.bind(('127.0.0.1',port))
            except OSError as exc:
                raise ValueError(f'Port {port} is already in use by another server. Use that existing workspace or choose --port with a free port. No running process was changed.') from exc
        version=check_runtime()
        env=dict(os.environ,PORT=str(port),OPENVSP_WORKSPACE=str(workspace))
        with (workspace/'studio-server.log').open('ab') as log:
            process=subprocess.Popen([interpreter(),str(ROOT/'server.py')],cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True)
        _started_processes[process.pid]=process
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            info=health(port,workspace)
            if info:
                info['engineVersion']=version
                (workspace/'studio-launch.json').write_text(json.dumps(dict(info,port=port),indent=2))
                return info,True
            if process.poll() is not None:
                _started_processes.pop(process.pid,None)
                raise ValueError('Studio could not start. Another Studio server may already use this workspace. Details: '+str(workspace/'studio-server.log'))
            time.sleep(.1)
        raise ValueError('Studio has not answered its startup check yet. Its process was left running; inspect '+str(workspace/'studio-server.log')+' before trying again.')


def port_available(port):
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',port));return True
        except OSError:return False


def start_auto(workspace,preferred=8765,timeout=35):
    """Reuse a verified saved endpoint, or select a free local port."""
    import fcntl
    workspace=Path(workspace).expanduser().resolve();workspace.mkdir(parents=True,exist_ok=True)
    with (workspace/'launcher-selection.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        record={}
        try:record=json.loads((workspace/'studio-launch.json').read_text())
        except (OSError,ValueError):pass
        saved=record.get('port')
        if type(saved)==int and 1<=saved<=65535 and record.get('root')==str(ROOT) and record.get('workspace')==str(workspace):
            info=health(saved,workspace)
            if info:return {**info,'port':saved},False
            if not port_available(saved):raise ValueError('The saved Studio address is still in use but did not answer its workspace check. Its server was left unchanged. Check '+str(workspace/'studio-server.log')+' before trying again.')
        info=health(preferred,workspace)
        if info:return {**info,'port':preferred},False
        if port_available(preferred):port=preferred
        else:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        info,created=start(port,workspace,timeout)
        return {**info,'port':port},created


def main():
    parser=argparse.ArgumentParser(description='Open the modern OpenVSP Studio workspace.')
    parser.add_argument('--port',type=int,help='Use this explicit port; automatic launches reuse a saved endpoint or find a free port.')
    parser.add_argument('--workspace',type=Path,default=Path(os.environ.get('OPENVSP_WORKSPACE',str(ROOT/'.workspace'))))
    parser.add_argument('--no-open',action='store_true',help='Start or reuse Studio without opening a browser.')
    parser.add_argument('--check',action='store_true',help='Verify the native engine and modeling adapter without starting a server.')
    args=parser.parse_args()
    try:
        explicit=args.port if args.port is not None else int(os.environ['PORT']) if os.environ.get('PORT') else None
        if explicit is not None and not 1<=explicit<=65535:raise ValueError('Choose a port between 1 and 65535.')
        if args.check:print(check_runtime());return 0
        if explicit is None:info,created=start_auto(args.workspace);port=info['port']
        else:info,created=start(explicit,args.workspace);port=explicit
        url=f'http://127.0.0.1:{port}/'
        print(('Started' if created else 'Reusing')+' OpenVSP Studio: '+url)
        if not args.no_open:webbrowser.open(url)
        return 0
    except ValueError as exc:
        print(str(exc),file=sys.stderr)
        if not args.no_open and not args.check:
            try:
                folder=args.workspace.expanduser().resolve();folder.mkdir(parents=True,exist_ok=True)
                report=folder/'studio-startup-help.html'
                recovery='Restore or rebuild this packaged Studio app, then open it again.' if (ROOT.parent/'studio-package.json').is_file() else 'Keep OpenVSP Studio.app inside the project folder, with its .runtime folder. Resolve the issue above, then open the shortcut again.'
                report.write_text('<!doctype html><meta charset="utf-8"><title>OpenVSP Studio startup</title><style>body{font:18px system-ui;max-width:760px;margin:80px auto;padding:24px;color:#26463b}pre{white-space:pre-wrap;font:inherit}p{line-height:1.6}</style><h1>Studio could not open yet</h1><pre>'+html.escape(str(exc))+'</pre><p>Your saved aircraft and running servers were not replaced. '+html.escape(recovery)+'</p>')
                webbrowser.open(report.as_uri())
            except OSError:pass
        return 1


if __name__=='__main__':sys.exit(main())
