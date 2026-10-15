"""Unmodified public-SDK profile oracle in a fresh engine process.

No Studio snapshot, adapter or mutation helpers are used by this reference.
"""
import json
import subprocess
import shutil
import uuid
from pathlib import Path

SCRIPT=r'''
import json,sys,faulthandler,signal
faulthandler.enable()
if hasattr(signal,'SIGTRAP'):faulthandler.register(signal.SIGTRAP,all_threads=True,chain=True)
from vsp_runtime import load
v=load();v.ReadVSPFile(sys.argv[1]);v.Update();g=sys.argv[2]
pid=sys.argv[3]
if pid:
 v.SetParmValUpdate(pid,json.loads(sys.argv[4]));v.Update()
params={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(g)}
xyz=lambda p:[p.x(),p.y(),p.z()]
surfaces=[]
for i in range(v.GetTotalNumSurfs(g)):
 u,w=v.GetUWTess01(g,i%v.GetNumMainSurfs(g))
 surfaces.append(dict(index=i,rows=len(u),cols=len(w),points=[xyz(p) for p in v.CompVecPnt01(g,i,[a for a in u for _ in w],[b for _ in u for b in w])]))
sections=[]
for si in range(v.GetNumXSecSurfs(g)):
 surf=v.GetXSecSurf(g,si)
 for i in range(v.GetNumXSec(surf)):
  x=v.GetXSec(surf,i)
  sections.append(dict(surface=si,index=i,profile=[xyz(v.ComputeXSecPnt(x,j/100)) for j in range(101)]))
print(json.dumps(dict(params=params,surfaces=surfaces,sections=sections)))
'''

def retain_failure(path,gid,pid,value,result):
    folder=Path(__file__).resolve().parents[1]/'.workspace/evidence/native-profile-failures'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    shutil.copy2(path,folder/'before.vsp3')
    (folder/'request.json').write_text(json.dumps(dict(geom=gid,id=pid,value=value,returnCode=result.returncode),indent=2)+'\n')
    (folder/'stderr.log').write_text(result.stderr)
    return folder


def reference(path,gid,pid='',value=None):
    from vsp_runtime import interpreter
    result=subprocess.run([interpreter(),'-c',SCRIPT,str(path),gid,pid,json.dumps(value)],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30)
    if result.returncode:
        archive=retain_failure(path,gid,pid,value,result)
        raise AssertionError('Unmodified SDK profile reference failed: '+str(result.returncode)+'; preserved input and stderr: '+str(archive)+' '+result.stderr[-2000:])
    return json.loads(result.stdout)
