"""Original cutting-plane DrawObjs are readable without changing the aircraft."""
import unittest
import test_native

class FlowPlanePreview(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_native_corners_axes_visibility_transforms_and_cold_reopening(self):
        v=self.v;v.DeleteAllCpSlices();v.DeleteGeom(self.gid);body=v.AddGeom('POD')
        v.SetParmVal(body,'X_Rel_Location','XForm',7);v.SetParmVal(body,'Y_Rel_Location','XForm',-3);v.SetParmVal(body,'Z_Rel_Location','XForm',2);v.SetParmVal(body,'Z_Rel_Rotation','XForm',17);v.Update()
        populated,*bounds=v.GetBBoxSet(v.SET_ALL);self.assertTrue(populated)
        lo=bounds[:3];hi=[a+b for a,b in zip(lo,bounds[3:])]
        positions=[6,-2,1];ids=[v.AddCpSlice(axis,pos) for axis,pos in enumerate(positions)]
        v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        data,path=self.worker(dict(action='query',operation='flow-plane-preview'))
        self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
        self.assertEqual(len(data['parts']),3)
        for axis,part in enumerate(data['parts']):
            self.assertEqual(part['id'],ids[axis]);self.assertEqual([o['kind'] for o in part['objects']],['quads','loop'])
            corners=part['objects'][0]['points'];self.assertEqual(corners,part['objects'][1]['points'])
            self.assertTrue(all(p[axis]==positions[axis] for p in corners))
            for other in set(range(3))-{axis}:
                center=(hi[other]+lo[other])/2;half=(hi[other]-lo[other])/2
                self.assertEqual(min(p[other] for p in corners),center-half);self.assertEqual(max(p[other] for p in corners),center+half)
        cold,_=self.worker(dict(action='query',operation='flow-plane-preview'),path);self.assertEqual(cold,data)
        v.SetParmVal(ids[1],'DrawCutFlag','CpSlice',0);v.WriteVSPFile(str(self.model),v.SET_ALL)
        hidden,_=self.worker(dict(action='query',operation='flow-plane-preview'));self.assertEqual(hidden['parts'][1]['objects'],[])
        self.assertEqual(hidden['parts'][0],data['parts'][0]);self.assertEqual(hidden['parts'][2],data['parts'][2])

    def test_empty_plane_list_is_valid(self):
        self.v.DeleteAllCpSlices();self.v.WriteVSPFile(str(self.model),self.v.SET_ALL)
        data,_=self.worker(dict(action='query',operation='flow-plane-preview'));self.assertEqual(data['parts'],[])
