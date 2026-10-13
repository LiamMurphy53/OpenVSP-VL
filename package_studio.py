"""Build a self-contained local macOS arm64 Studio app from installed runtimes."""
import argparse,hashlib,json,os,plistlib,shutil,subprocess,tempfile
from pathlib import Path
from vsp_runtime import ROOT


def digest(source,headers):
    return hashlib.sha256(source.read_bytes()+b''.join(p.read_bytes() for p in sorted(headers.glob('*.h')))).hexdigest()[:20]


def build(output):
    output=Path(output).expanduser().resolve()
    if output.suffix!='.app':raise ValueError('Choose an output path ending in .app.')
    if output.exists():raise ValueError('The output already exists. Choose a new app path to preserve it.')
    engine=ROOT/'.runtime/OpenVSP-3.52.2-MacOS';python=ROOT/'.runtime/python-interpreters/cpython-3.11-macos-aarch64-none';site=ROOT/'.runtime/site'
    for source in (engine,python,site):
        if not source.is_dir():raise ValueError('A bundled runtime source is missing: '+str(source))
    source=ROOT/'native_bridge/structural_preview.cpp';headers=ROOT/'native_bridge/vendor/openvsp-3.52.2';key=digest(source,headers);library=ROOT/'.runtime/native-preview'/(key+'.dylib')
    if not library.is_file():
        result=subprocess.run([str(python/'bin/python3'),str(ROOT/'studio_launcher.py'),'--check'],cwd=ROOT,capture_output=True,text=True,timeout=120)
        if result.returncode:raise ValueError('Native preflight failed: '+result.stderr[-2000:])
    if not library.is_file():raise ValueError('The matching compiled native adapter is unavailable.')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='studio-package-',dir=output.parent) as temp:
        staged=Path(temp)/output.name;contents=staged/'Contents';studio=contents/'Resources/studio';studio.mkdir(parents=True);macos=contents/'MacOS';macos.mkdir()
        print('Copying Studio interface and native workflows',flush=True)
        for path in ROOT.glob('*.py'):shutil.copy2(path,studio/path.name)
        for name in ('README.md','FEATURE_STATUS.md','CAPABILITY_PLAN.md'):shutil.copy2(ROOT/name,studio/name)
        shutil.copytree(ROOT/'web',studio/'web');shutil.copytree(ROOT/'native_bridge',studio/'native_bridge')
        runtime=studio/'.runtime';runtime.mkdir();print('Copying original OpenVSP distribution',flush=True);shutil.copytree(engine.resolve(),runtime/engine.name,symlinks=False)
        print('Copying matching Python and dependencies',flush=True);shutil.copytree(python.resolve(),runtime/'python-interpreters/cpython-3.11-macos-aarch64-none',symlinks=False);shutil.copytree(site,runtime/'site',symlinks=False)
        (runtime/'native-preview').mkdir();shutil.copy2(library,runtime/'native-preview'/library.name)
        info=plistlib.loads((ROOT/'OpenVSP Studio.app/Contents/Info.plist').read_bytes());info['CFBundleIdentifier']='local.openvsp.modernstudio';(contents/'Info.plist').write_bytes(plistlib.dumps(info))
        launcher=macos/'launch';launcher.write_text('''#!/bin/sh
studio_root=$(CDPATH= cd "$(dirname "$0")/../Resources/studio" && pwd) || exit 1
studio_python=${OPENVSP_PYTHON:-"$studio_root/.runtime/python-interpreters/cpython-3.11-macos-aarch64-none/bin/python3"}
export OPENVSP_WORKSPACE="${OPENVSP_WORKSPACE:-$HOME/Library/Application Support/OpenVSP Studio}"
cd "$studio_root" || exit 1
exec "$studio_python" "$studio_root/studio_launcher.py" "$@"
''');launcher.chmod(0o755)
        environment=dict(os.environ);environment.pop('OPENVSP_HOME',None);environment.pop('OPENVSP_PYTHON',None);environment['PYTHONDONTWRITEBYTECODE']='1'
        print('Checking packaged original engine and modeling adapter',flush=True)
        check=subprocess.run([str(launcher),'--check'],cwd=temp,env=environment,capture_output=True,text=True,timeout=120)
        if check.returncode:raise ValueError('The staged app could not load its native engine/adapter: '+check.stderr[-2000:])
        inputs=[p for p in studio.rglob('*') if p.is_file() and '.runtime' not in p.relative_to(studio).parts and '__pycache__' not in p.parts]
        manifest=dict(format=1,application='OpenVSP Studio',platform='macOS arm64',nativeEngine='OpenVSP 3.52.2',nativeAdapter=library.name,packagedNativePreflight=check.stdout.strip(),implementationStatus='Under development; full workflow parity remains unverified.',sourceHashes={str(p.relative_to(studio)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inputs)})
        (contents/'Resources/studio-package.json').write_text(json.dumps(manifest,indent=2)+'\n')
        staged.rename(output)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'.workspace/distribution/OpenVSP Studio.app');args=parser.parse_args()
    try:print(build(args.output));return 0
    except (ValueError,OSError,subprocess.TimeoutExpired) as error:parser.exit(1,str(error)+'\n')


if __name__=='__main__':main()
