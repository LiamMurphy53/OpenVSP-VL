"""Run every native unittest in a separate process; preserve failures/crashes.

The app isolates native engine work in subprocesses. This runner also keeps one
native crash from preventing execution/evidence for the remaining test cases.
It does not replace the ordinary shared-process suite or alter assertions.
"""
import argparse,json,os,subprocess,sys,time,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def flatten(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite):yield from flatten(test)
        else:yield test

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=300)
    args=parser.parse_args()
    if args.timeout<1:parser.error('timeout must be positive')
    if sys.version_info[:2]!=(3,11):parser.error('Use the matching native Python 3.11 runtime')
    args.output.mkdir(parents=True,exist_ok=True)
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py')
    ids=[t.id() for t in flatten(suite)]
    if any(name.startswith('unittest.loader._FailedTest') for name in ids):
        unittest.TextTestRunner(verbosity=2).run(suite);return 1
    env=os.environ.copy();env['PYTHONPATH']=os.pathsep.join([str(ROOT/'tests'),str(ROOT),env.get('PYTHONPATH','')])
    manifest=dict(python=sys.executable,tests=ids,total=len(ids),started=time.time(),results=[],complete=False)
    summary=args.output/'summary.json'
    def save():
        tmp=summary.with_suffix('.tmp');tmp.write_text(json.dumps(manifest,indent=2));tmp.replace(summary)
    save()
    for i,name in enumerate(ids):
        log=args.output/(name+'.log');started=time.monotonic()
        with log.open('wb') as stream:
            try:
                result=subprocess.run([sys.executable,'-m','unittest',name,'-v'],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=args.timeout)
                status='pass' if result.returncode==0 else 'crash' if result.returncode<0 else 'fail'
                rc=result.returncode
            except subprocess.TimeoutExpired:
                status='timeout';rc=None
        manifest['results'].append(dict(test=name,status=status,returncode=rc,seconds=time.monotonic()-started,log=log.name));save()
        print(f'{i+1}/{len(ids)} {status}: {name}',flush=True)
    manifest.update(complete=True,finished=time.time(),counts={s:sum(r['status']==s for r in manifest['results']) for s in ['pass','fail','crash','timeout']});save()
    print(json.dumps(manifest['counts']),flush=True)
    return int(any(r['status']!='pass' for r in manifest['results']))

if __name__=='__main__':sys.exit(main())
