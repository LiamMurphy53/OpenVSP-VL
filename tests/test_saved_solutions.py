"""Saved native solutions reopen and slice through the same engine as direct calls."""
import json,os,shutil,sys,time,unittest
from pathlib import Path
import test_studies,test_native,test_degenerate
import native_service as service
import native_worker
from vsp_runtime import load


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeSavedSolutions(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    canonical=test_degenerate.NativeDegenerate.canonical
    assertResults=test_degenerate.NativeDegenerate.assertResults

    def wait_job(self,jid):
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            job=service.job_state(jid)
            if job['status']!='running':
                self.assertEqual(job['status'],'complete',job.get('error'));return job
            time.sleep(.03)
        self.fail('Native saved-solution operation did not finish.')

    def direct(self,name,source,inputs):
        folder=self.path/('direct-'+name);folder.mkdir()
        for p in service.job_folder(source).iterdir():
            if p.is_file() and not p.name.startswith('.') and p.suffix!='.json' and p.name!='engine.log':shutil.copy2(p,folder/p.name)
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(folder/'aircraft.vsp3'));v.Update();v.SetVSP3FileName(str(folder/'aircraft.vsp3'))
        v.SetAnalysisInputDefaults(name)
        for key,values in inputs.items():v.SetDoubleAnalysisInput(name,key,values)
        old=os.getcwd();os.chdir(folder)
        try:rid=v.ExecAnalysis(name);native_worker.errors(v);self.assertTrue(rid);return native_worker.sanitize(native_worker.collect_results(v))
        finally:os.chdir(old)

    def test_reopen_and_slice_native_solution_preserve_source_and_current_aircraft(self):
        baseline=self.model.read_bytes()
        inputs=[dict(name=k,values=value) for k,value in dict(GeomSet=[-1],ThinGeomSet=[0],AlphaStart=[3.],AlphaEnd=[3.],AlphaNpts=[1],BetaNpts=[1],MachNpts=[1],ReCrefNpts=[1],WakeNumIter=[3],NumWakeNodes=[16],NCPU=[1]).items()]
        source=self.wait_job(service.start_job(dict(name='VSPAEROSweep',inputs=inputs,revision=service.REVISION))['id'])
        files={p.name:p.read_bytes() for p in service.job_folder(source['id']).iterdir() if p.is_file()}
        for name,values in [('VSPAEROReadPreviousAnalysis',{}),('CpSlicer',dict(XSlicePosVec=[.5],YSlicePosVec=[1.,3.],ZSlicePosVec=[]))]:
            with self.subTest(name=name):
                spec=service.schema(name);self.assertIn(source['id'],[s['id'] for s in spec['savedSolutions']])
                expected=self.direct(name,source['id'],values)
                job=self.wait_job(service.start_job(dict(name=name,sourceRun=source['id'],inputs=[dict(name=k,values=x) for k,x in values.items()],revision=service.REVISION))['id'])
                self.assertResults(expected,job['result']['results']);self.assertEqual(job['sourceRun'],source['id']);self.assertEqual(job['revision'],source['revision'])
                self.assertEqual(service.aero_preview(job['id'],next(f['name'] for f in job['artifacts'] if f['aeroPreview']),1),service.aero_preview(source['id'],next(f['name'] for f in source['artifacts'] if f['aeroPreview']),1))
                self.assertEqual(self.model.read_bytes(),baseline)
                self.assertEqual({p.name:p.read_bytes() for p in service.job_folder(source['id']).iterdir() if p.is_file()},files)
                if name=='CpSlicer':self.assertTrue(any(r['name']=='CpSlicer_Case' for r in job['result']['results']))

    def test_missing_source_and_empty_slice_positions_are_actionable(self):
        baseline=self.model.read_bytes()
        for name in ('VSPAEROReadPreviousAnalysis','CpSlicer'):
            with self.assertRaisesRegex(ValueError,'Choose a completed saved'):
                service.start_job(dict(name=name,inputs=[],revision=service.REVISION))
        self.assertEqual(service.list_jobs(),[]);self.assertEqual(self.model.read_bytes(),baseline)
        spec=native_worker.analysis_schema(self.v,'CpSlicer')
        self.assertTrue(all(e['numericList'] for e in spec['inputs']))
        with self.assertRaisesRegex(ValueError,'at least one slice'):
            native_worker.set_inputs(self.v,'CpSlicer',[dict(name=e['name'],values=[]) for e in spec['inputs']])
