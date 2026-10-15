"""Plane-series setup preserves original native cutting planes and geometry."""
import unittest
import test_native
import native_flow_planes
from native_worker import parameter

class FlowPlaneSeries(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_axes_and_descending_series_match_original_native_records(self):
        v=self.v
        for axis,start,end in [(v.X_DIR,-3,7),(v.Y_DIR,8,-2),(v.Z_DIR,-1,1)]:
            with self.subTest(axis=axis):
                v.DeleteAllCpSlices();v.AddCpSlice(v.Z_DIR,12);v.WriteVSPFile(str(self.model),v.SET_ALL)
                baseline,_=self.worker(dict(action='state'))
                expected=[12]+[start+(end-start)*i/4 for i in range(5)]
                state,path=self.worker(dict(action='mutate',operation='flow-plane-series',name='Station',axis=axis,start=start,end=end,count=5))
                for result in (state,self.worker(dict(action='state'),path)[0]):
                    ps=result['tools']['flowPlanes'];self.assertEqual(len(ps),6)
                    self.assertEqual([next(p['value'] for p in c['params'] if p['name']=='CutPosition') for c in ps],expected)
                    self.assertEqual([c['name'] for c in ps[1:]],['Station '+str(i) for i in range(1,6)])
                    self.assertTrue(all(next(p['value'] for p in c['params'] if p['name']=='CutType')==axis for c in ps[1:]))
                    self.assertEqual(result['components'],baseline['components'])
                v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
                self.assertEqual([v.GetParmVal(cid,'CutPosition','CpSlice') for cid in native_flow_planes.ids(v)],expected)

    def test_bad_series_reject_before_adding_any_planes_and_preserve_files(self):
        v=self.v;before=native_flow_planes.snapshot(v,parameter)
        base=dict(operation='flow-plane-series',axis=v.Y_DIR,start=0,end=10,count=5,name='Cut')
        for changes in [dict(count=True),dict(count=1),dict(count=101),dict(count=2.5),dict(start=10),dict(end=1e13),dict(start=float('nan')),dict(axis=True),dict(name='x'*120),dict(start=1e12,end=1e12-.0001220703125)]:
            with self.subTest(changes=changes):
                request={**base,**changes}
                with self.assertRaises(ValueError):native_flow_planes.mutate(v,request)
                self.assertEqual(native_flow_planes.snapshot(v,parameter),before)
                original=self.model.read_bytes()
                with self.assertRaises(ValueError):self.worker(dict(action='mutate',**request))
                self.assertEqual(self.model.read_bytes(),original)
                self.assertTrue(all(p.read_bytes()==original for p in self.path.glob('*/aircraft.vsp3')))

    def test_series_generates_original_solver_pressure_and_airflow_files(self):
        from native_worker import collect_results
        v=self.v;v.DeleteAllCpSlices();v.WriteVSPFile(str(self.model),v.SET_ALL)
        _,saved=self.worker(dict(action='mutate',operation='flow-plane-series',name='Span',axis=v.Y_DIR,start=-2,end=2,count=3))
        inputs={'AlphaStart':4.,'AlphaEnd':4.,'AlphaNpts':1,'NCPU':1,'MachStart':.1,'MachEnd':.1,'MachNpts':1}
        result,path=self.worker(dict(action='analysis',name='VSPAEROSweep',inputs=[dict(name=n,values=[x]) for n,x in inputs.items()]),saved)
        self.assertEqual([float(p['position']) for p in result['solverSetup']['planes']],[-2,0,2])
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.DeleteAllResults()
        for position in [-2,0,2]:v.AddCpSlice(v.Y_DIR,position)
        v.SetVSP3FileName(str(self.path/'direct-series.vsp3'))
        v.SetAnalysisInputDefaults('VSPAEROComputeGeometry');v.ExecAnalysis('VSPAEROComputeGeometry');v.SetAnalysisInputDefaults('VSPAEROSweep')
        for n,x in inputs.items():
            setter=v.SetIntAnalysisInput if v.GetAnalysisInputType('VSPAEROSweep',n)==v.INT_DATA else v.SetDoubleAnalysisInput
            setter('VSPAEROSweep',n,[x])
        v.ExecAnalysis('VSPAEROSweep')
        slices=lambda results:[dict(name=r['name'],index=r['index'],entries=r['entries']) for r in results if r['name']=='CpSlicer_Case']
        self.assertTrue(slices(result['results']));self.assertEqual(slices(result['results']),slices(collect_results(v)))
        files=sorted(path.parent.glob('*.case.*.quad.*.dat'));direct=sorted(self.path.glob('direct-series.case.*.quad.*.dat'))
        self.assertEqual(len(files),3);self.assertEqual(len(direct),3)
        self.assertEqual([p.read_bytes() for p in files],[p.read_bytes() for p in direct])
