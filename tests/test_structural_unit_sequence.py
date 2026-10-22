"""Sequential saved unit edits preserve exact cold original solver exports."""
import unittest,subprocess,json,hashlib,sys
from pathlib import Path
import test_native,vsp_runtime

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class StructuralUnitSequence(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_inch_mpa_si_mpa_saved_edits_match_fresh_original_decks(self):
        v=self.v;index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index)
        bid=v.AddFeaBC(sid,v.FEA_BC_STRUCTURE)
        solver=v.FindParm(v.GetVehicleID(),'StructUnit','FeaStructure')
        v.SetParmVal(v.FindParm(v.GetVehicleID(),'StructModelUnit','FeaStructure'),v.LEN_FT)
        for name,value in [('ConMode',v.FEA_BCM_PIN),('YLGFlag',1),('YLTFlag',1)]:v.SetParmVal(v.FindParm(bid,name,'FeaBC'),value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);path=self.model
        for n,(system,scale) in enumerate([(v.BIN_UNIT,12.),(v.MPA_UNIT,304.8),(v.SI_UNIT,.3048),(v.MPA_UNIT,304.8)]):
            with self.subTest(system=system,step=n):
                state,path=self.worker(dict(action='mutate',operation='parameter',id=solver,value=system),path)
                for name,value in [('YGTVal',-scale),('YLTVal',scale)]:
                    pid=next(p['id'] for b in state['tools']['boundaryConditions'] if b['id']==bid for p in b['params'] if p['name']==name)
                    state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
                saved=path.read_bytes()
                inputs=[dict(name=name,values=[value]) for name,value in [('BaseLen',scale),('MinLen',scale*.2),('MaxGap',scale*.03)]]
                result,out=self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=sid,formats=['CALCULIX'],inputs=inputs),path)
                direct=self.path/f'original-{n}.inp'
                script="import sys;from vsp_runtime import load;v=load();v.ClearVSPModel();v.ReadVSPFile(sys.argv[1]);v.Update();g=sys.argv[2];i=int(sys.argv[3]);s=float(sys.argv[5]);[(v.SetFeaMeshVal(g,i,getattr(v,k),x)) for k,x in [('CFD_MAX_EDGE_LEN',s),('CFD_MIN_EDGE_LEN',s*.2),('CFD_MAX_GAP',s*.03)]];v.Update();v.SetFeaMeshFileName(g,i,v.FEA_CALCULIX_FILE_NAME,sys.argv[4]);v.ComputeFeaMesh(g,i,v.FEA_CALCULIX_FILE_NAME)"
                env=__import__('os').environ.copy();env['PYTHONPATH']=str(vsp_runtime.ROOT)
                r=subprocess.run([vsp_runtime.interpreter(),'-c',script,str(path),self.gid,str(index),str(direct),str(scale)],capture_output=True,text=True,env=env,timeout=120)
                self.assertEqual(r.returncode,0,r.stdout+r.stderr)
                if (out.parent/'structure.inp').read_bytes()!=direct.read_bytes():
                    import shutil,uuid
                    evidence=test_native.ROOT/'.workspace/evidence/structural-unit-sequence-mismatches'/uuid.uuid4().hex
                    shutil.copytree(out.parent,evidence);shutil.copy2(direct,evidence/'original.inp');(evidence/'original.log').write_text(r.stdout+r.stderr)
                    (evidence/'reference.json').write_text(json.dumps(dict(command=r.args,pythonPath=env['PYTHONPATH'],inputSha256=hashlib.sha256(saved).hexdigest(),step=n,system=system,scale=scale),indent=2))
                self.assertEqual((out.parent/'structure.inp').read_bytes(),direct.read_bytes())
                self.assertEqual(path.read_bytes(),saved);self.assertEqual(out.read_bytes(),saved)
                self.assertGreater(result['boundaryReport']['nodeCount'],0)
