"""Saved wave plots retain actual original-manager arrays and isolate the model."""
import json
import os
import sys
import unittest
import test_native
import test_guides
import native_wave_references


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use native Python 3.11.')
class WaveReferences(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    fixture=test_guides.NativeGuides.fixture
    direct=test_guides.NativeGuides.direct
    assertNative=test_guides.NativeGuides.assertNative

    def compare_native_plot_arrays(self,flow=False):
        self.fixture();v=self.v
        values=dict(Mach=[1.8],NumSlices=[15],NumRotSects=[5])
        if flow:
            region=v.AddSubSurf(self.pod,v.SS_LINE)
            v.SetParmVal(v.FindParm(region,'Const_Line_Value','SubSurface'),.1)
            v.SetParmVal(v.FindParm(region,'Test_Type','SubSurface'),1)
            v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
            values['SSFlow_vec']=[region]
        expected_results=self.direct('WaveDrag',values)
        rid=v.FindLatestResultsID('WaveDrag')
        expected=dict(resultID=rid,results=expected_results,version=v.GetVSPVersion())
        cwd=os.getcwd()
        try:
            os.chdir(self.path);native_wave_references.save(v,expected)
        finally:os.chdir(cwd)
        data,path=self.worker(dict(action='analysis',name='WaveDrag',inputs=[dict(name=k,index=0,values=a) for k,a in values.items()]))
        self.assertNative(expected_results,data['results'])
        self.assertEqual(data['waveReferenceCurves'],expected['waveReferenceCurves'])
        saved=json.loads((path.parent/data['waveReferenceCurves']['file']).read_text())
        self.assertEqual(saved,{k:value for k,value in data['waveReferenceCurves'].items() if k!='file'})
        self.assertEqual(path.read_bytes(),self.model.read_bytes())
        result=next(r for r in data['results'] if r['id']==data['resultID'])
        slices=[e['values'] for e in result['entries'] if e['name']=='Slice_Area']
        self.assertEqual([c['totalSlices'] for c in saved['cones']],slices)
        self.assertEqual(len(saved['cones']),5)
        if flow:
            self.assertGreater(saved['inletArea'],0)
            self.assertNotEqual(saved['cones'][0]['flowFit'],saved['cones'][0]['totalFit'])
        for cone in saved['cones']:
            self.assertEqual(len(cone['flowFit']),100)
            self.assertEqual(len(cone['componentFit']),len(saved['componentIds']))
            self.assertEqual(len(cone['buildupFit']),len(saved['componentIds']))
            self.assertEqual(len(cone['searsHaack']),100)
            self.assertEqual(cone['searsHaack'][0],0)
            self.assertEqual(cone['searsHaack'][-1],0)

    def test_complete_saved_native_plot_arrays_match_fresh_sdk_and_do_not_edit_aircraft(self):
        self.compare_native_plot_arrays()

    def test_propulsive_inlet_and_corrected_arrays_match_fresh_sdk(self):
        self.compare_native_plot_arrays(True)
