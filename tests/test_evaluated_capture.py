"""Recorder selection and process-local SDK path restoration."""
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import native_evaluated_capture as capture

class EvaluatedCapture(unittest.TestCase):
    def inputs(self,**changes):return [dict(name=n,values=[x]) for n,x in (dict(NCPU=1,UnsteadyType=3,StopBeforeRun=0)|changes).items()]
    def test_verified_selection_excludes_other_policies(self):
        v=SimpleNamespace(STABILITY_Q_ANALYSIS=3)
        self.assertTrue(capture.eligible(v,'VSPAEROSweep',self.inputs()))
        for name,values in [('CompGeom',self.inputs()),('VSPAEROSweep',self.inputs(NCPU=2)),('VSPAEROSweep',self.inputs(UnsteadyType=2)),('VSPAEROSweep',self.inputs(StopBeforeRun=1))]:self.assertFalse(capture.eligible(v,name,values))

    def test_sdk_path_restored_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'.runtime/native-flow-reader').mkdir(parents=True);vendor=root/'vendor';vendor.mkdir();v=SimpleNamespace(STABILITY_Q_ANALYSIS=3,path='original')
            v.GetVSPAEROPath=lambda:v.path;v.SetVSPAEROPath=lambda p:setattr(v,'path',p);v.CheckForVSPAERO=lambda p:True
            meta=dict(engineSourceTag='OpenVSP_3.52.2',readerExecutableSha256='a'*64,readerSourceSha256='b'*64,readerPatchSha256='c'*64)
            with patch('vsp_runtime.ROOT',root),patch('vsp_runtime.distribution',return_value=vendor),patch('native_flow_reader.executable',return_value=(root/'recorded',meta)):
                with self.assertRaisesRegex(RuntimeError,'native failure'):
                    with capture.solver(v,'VSPAEROSweep',self.inputs()) as writer:
                        self.assertNotEqual(v.path,'original');self.assertEqual(writer['writerSourceSha256'],'b'*64);raise RuntimeError('native failure')
            self.assertEqual(v.path,'original');self.assertEqual(list((root/'.runtime/native-flow-reader').iterdir()),[])

if __name__=='__main__':unittest.main()
