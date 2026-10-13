"""Original saved cutting-plane controls and solver records, with real SDK."""
import sys,unittest
from pathlib import Path
import test_native
from vsp_runtime import load
from native_worker import parameter
import native_flow_planes as planes
import native_solver_setup


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class NativeFlowPlanes(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_native_add_edit_delete_and_cold_save_preserve_geometry(self):
        v=self.v;source=self.model.read_bytes()
        original={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)}
        state,path=self.worker(dict(action='mutate',operation='flow-plane-add',axis=v.Z_DIR,position=3.125,name='Vertical cut'))
        plane=next(p for p in state['tools']['flowPlanes'] if p['name']=='Vertical cut')
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertIn(plane['id'],planes.ids(v))
        self.assertEqual(v.GetParmVal(plane['id'],'CutType','CpSlice'),v.Z_DIR)
        self.assertEqual(v.GetParmVal(plane['id'],'CutPosition','CpSlice'),3.125)
        self.assertEqual(original,{p:v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)})
        pid=next(p['id'] for p in plane['params'] if p['name']=='CutPosition')
        edited,second=self.worker(dict(action='mutate',operation='parameter',id=pid,value=-2.75),model=path)
        self.assertEqual(next(q for p in edited['tools']['flowPlanes'] if p['id']==plane['id'] for q in p['params'] if q['name']=='CutPosition')['value'],-2.75)
        deleted,last=self.worker(dict(action='mutate',operation='flow-plane-delete',id=plane['id']),model=second)
        self.assertNotIn(plane['id'],[p['id'] for p in deleted['tools']['flowPlanes']])
        self.assertEqual(self.model.read_bytes(),source)

    def test_invalid_requests_do_not_change_native_planes(self):
        v=self.v;before=planes.snapshot(v,parameter)
        for req in [dict(operation='flow-plane-add',axis=True,position=0),dict(operation='flow-plane-add',axis=3,position=0),dict(operation='flow-plane-add',axis=v.X_DIR,position=float('nan')),dict(operation='flow-plane-add',axis=v.X_DIR,position=1e13),dict(operation='flow-plane-delete',id='missing')]:
            with self.assertRaises(ValueError):planes.mutate(v,req)
            self.assertEqual(before,planes.snapshot(v,parameter))

    def test_saved_solver_planes_match_original_native_records(self):
        v=self.v;v.DeleteAllCpSlices()
        for axis,pos in [(v.X_DIR,1.25),(v.Y_DIR,2.5),(v.Z_DIR,-.75)]:v.AddCpSlice(axis,pos)
        v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        inputs={'AlphaStart':4.,'AlphaEnd':4.,'AlphaNpts':1,'NCPU':1,'MachStart':.1,'MachEnd':.1,'MachNpts':1}
        result,path=self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=[dict(name=n,values=[x]) for n,x in inputs.items()]))
        expected=[dict(index=str(i+1),axis=str(a+1),position=format(x,'.17g')) for i,(a,x) in enumerate([(v.X_DIR,1.25),(v.Y_DIR,2.5),(v.Z_DIR,-.75)])]
        self.assertEqual(result['solverSetup']['planes'],expected)
        import json
        applied=json.loads((path.parent/'analysis-setup.json').read_text())['cuttingPlanes']
        self.assertEqual(len(applied['flowPlanes']),3)
        self.assertEqual(next(p['value'] for p in applied['flowPlaneSettings'] if p['name']=='CpSliceFlag'),1)
        self.assertEqual(native_solver_setup.read(path.parent)['planes'],expected)
        self.assertTrue(any(r['name'].startswith('CpSlice') for r in result['results']))
        self.assertEqual(path.read_bytes(),before)
        # Independent original SDK execution checks every returned slice sample.
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.DeleteAllResults()
        v.SetVSP3FileName(str(self.path/'direct-slices.vsp3'))
        v.SetAnalysisInputDefaults('VSPAEROComputeGeometry');v.ExecAnalysis('VSPAEROComputeGeometry')
        v.SetAnalysisInputDefaults('VSPAEROSweep')
        for n,x in inputs.items():
            setter=v.SetIntAnalysisInput if v.GetAnalysisInputType('VSPAEROSweep',n)==v.INT_DATA else v.SetDoubleAnalysisInput
            setter('VSPAEROSweep',n,[x])
        v.ExecAnalysis('VSPAEROSweep')
        from native_worker import collect_results
        def cases(results):
            return [dict(name=r['name'],index=r['index'],entries=r['entries']) for r in results if r['name']=='CpSlicer_Case']
        actual=cases(result['results']);expected=cases(collect_results(v))
        self.assertTrue(actual,'Native slice samples must be present.')
        self.assertEqual(actual,expected)
        # The original solver itself emits flow planes during this sweep.
        from aero_io import read_flow_plane
        files=sorted(path.parent.glob('*.case.*.quad.*.dat'))
        direct=sorted(self.path.glob('direct-slices.case.*.quad.*.dat'))
        self.assertEqual(len(files),3);self.assertEqual(len(direct),3)
        for saved,original in zip(files,direct):
            self.assertEqual(saved.read_bytes(),original.read_bytes())
            mesh=read_flow_plane(saved)
            rows=saved.read_text().splitlines();count,cells=map(int,rows[1].split())
            self.assertEqual(len(mesh['nodes']),count);self.assertEqual(len(mesh['elements']),cells)
            for row,point,velocity,pressure in zip(rows[2:2+count],mesh['nodes'],mesh['velocities'],mesh['fields'][0]['nodeValues']):
                values=list(map(float,row.split()[1:]));self.assertEqual(point+velocity+[pressure],values)

    def test_disabled_saved_planes_do_not_generate_flow_files(self):
        v=self.v;cid=v.FindContainer('VSPAEROSettings',0)
        v.SetParmVal(v.FindParm(cid,'CpSliceFlag','VSPAERO'),0)
        v.WriteVSPFile(str(self.model),v.SET_ALL);source=self.model.read_bytes()
        result,path=self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=[dict(name='NCPU',values=[1])]))
        self.assertEqual(result['solverSetup']['planes'],[])
        self.assertEqual(list(path.parent.glob('*.case.*.quad.*.dat')),[])
        self.assertFalse(any(r['name']=='CpSlicer_Case' for r in result['results']))
        self.assertEqual(source,path.read_bytes())

    def test_single_component_preparation_runs_solver_and_study_validation(self):
        v=self.v;v.AddGeom('POD');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        selection=[dict(name='GeomSet',values=[-1]),dict(name='ThinGeomSet',values=[-1])]
        prep=selection+[dict(name='SingleGeomID',values=[self.gid])]
        inputs=selection+[dict(name='AlphaNpts',values=[1]),dict(name='NCPU',values=[1])]
        source=self.model.read_bytes()
        data,path=self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=inputs,geometryInputs=prep))
        self.assertTrue(data['resultID']);self.assertTrue(list(path.parent.glob('*.case.*.quad.*.dat')))
        self.assertEqual(path.read_bytes(),source)
        import native_study_worker,native_worker,native_guides
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        spec=native_study_worker.stage_schema(v,dict(name='VSPAEROSweep',inputs=inputs,geometryInputs=prep),native_worker.analysis_schema,native_worker.set_inputs)
        native_guides.validate(v,'VSPAEROSweep',spec)
        self.assertEqual(spec['preparedSingleGeomID'],self.gid)
        with self.assertRaisesRegex(ValueError,'containing components'):
            native_worker.set_inputs(v,'VSPAEROSweep',selection)

    def test_native_last_sweep_case_negative_filename_remains_previewable(self):
        from aero_io import read_flow_plane
        import native_service as service
        data,path=self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=[dict(name=n,values=[x]) for n,x in [('AlphaStart',2.),('AlphaEnd',5.),('AlphaNpts',2),('NCPU',1)]]))
        files=sorted(path.parent.glob('*.case.*.quad.*.dat'))
        self.assertEqual(len(files),2)
        self.assertTrue(any('.case.-2.' in p.name for p in files),'The original solver uses a negative last-case sentinel in its filename.')
        old=service.WORK;root=self.path/'preview-work';folder=root/'jobs'/('a'*32)
        import shutil
        shutil.copytree(path.parent,folder)
        try:
            service.WORK=root
            previews=[f for f in service.artifacts('a'*32) if f['flowPreview']]
            self.assertEqual({f['name'] for f in previews},{p.name for p in files})
            for p in files:self.assertEqual(service.aero_preview('a'*32,p.name),read_flow_plane(p))
        finally:service.WORK=old


if __name__=='__main__':unittest.main()
