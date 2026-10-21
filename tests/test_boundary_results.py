"""Native coordinate-filtered constraints and exported record summaries."""
import sys,unittest
from pathlib import Path
import test_native
import native_boundary_results

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class BoundaryResults(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_native_presets_custom_filters_and_empty_selection_match_original_decks(self):
        v=self.v;index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index)
        bid=v.AddFeaBC(sid,v.FEA_BC_STRUCTURE)
        for key,value in [('CFD_MAX_EDGE_LEN',1.),('CFD_MIN_EDGE_LEN',.2),('CFD_MAX_GAP',.03)]:v.SetFeaMeshVal(self.gid,index,getattr(v,key),value)
        setp=lambda n,x:v.SetParmVal(v.FindParm(bid,n,'FeaBC'),x)
        cases=[(v.FEA_BCM_ALL,63,False),(v.FEA_BCM_PIN,7,False),(v.FEA_BCM_SYMM,42,False),(v.FEA_BCM_ASYMM,21,False),(v.FEA_BCM_USER,17,False),(v.FEA_BCM_ALL,63,True)]
        for mode,mask,empty in cases:
            with self.subTest(mode=mode,empty=empty):
                setp('ConMode',mode)
                if mode==v.FEA_BCM_USER:setp('Constraints',mask)
                setp('YLGFlag',1);setp('YLTFlag',1)
                setp('YGTVal',100 if empty else -.1);setp('YLTVal',101 if empty else .1)
                v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);source=self.model.read_bytes()
                data,out=self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=sid,formats=['CALCULIX']))
                self.assertEqual(out.read_bytes(),source);self.assertEqual(self.model.read_bytes(),source)
                direct=self.path/'direct.inp'
                v.SetFeaMeshFileName(self.gid,index,v.FEA_CALCULIX_FILE_NAME,str(direct));v.ComputeFeaMesh(self.gid,index,v.FEA_CALCULIX_FILE_NAME)
                self.assertEqual((out.parent/'structure.inp').read_bytes(),direct.read_bytes())
                lines=direct.read_text().splitlines();start=lines.index('*BOUNDARY')+1
                native=set()
                for line in lines[start:]:
                    if line.startswith('*'):break
                    if line.strip():native.add(tuple(map(int,line.split(','))))
                report=data['boundaryReport'];self.assertTrue(report['available']);self.assertEqual(report['definedConditions'],1)
                self.assertEqual(report['degreeCount'],len(native))
                self.assertEqual(report['nodeCount'],len({n for n,d in native}))
                self.assertEqual(report['directionCounts'],[len({n for n,d in native if d==i}) for i in range(1,7)])
                if empty:self.assertEqual(native,set())
                else:
                    self.assertGreater(report['nodeCount'],0)
                    self.assertEqual({d for n,d in native},{i+1 for i in range(6) if mask&(1<<i)})
                if mode==v.FEA_BCM_PIN:
                    # Read original solver coordinates to verify the configured strip.
                    active=False;nodes={}
                    for line in lines:
                        if line.startswith('*'):active=line.upper().startswith('*NODE');continue
                        if active and line.strip():
                            fields=line.split(',');nodes[int(fields[0])]=list(map(float,fields[1:4]))
                    self.assertTrue(all(-.1<=nodes[n][1]<=.1 for n,d in native))
                    self.assertTrue(any(abs(p[1])>.1 for p in nodes.values()))
        result,out=self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=sid,formats=['GMSH']))
        self.assertFalse(result['boundaryReport']['available'])
        self.assertIn('CalculiX',result['boundaryReport']['reason'])

    def test_duplicate_records_count_once_and_unknown_formats_are_not_invented(self):
        path=self.path/'records.inp'
        path.write_text('*BOUNDARY\n10,1\n10,1\n10,3\n** comment\n*BOUNDARY\n12,6\n*MATERIAL\n')
        report=native_boundary_results.read(path)
        self.assertEqual((report['nodeCount'],report['degreeCount'],report['recordCount']),(2,3,4))
        self.assertEqual(report['directionCounts'],[1,0,1,0,0,1])
        path.write_text('*BOUNDARY\nNSET_A,1,6\n')
        report=native_boundary_results.read(path)
        self.assertFalse(report['available']);self.assertNotIn('nodeCount',report)

    def test_assembly_members_combine_boundaries_without_counting_connection_equations(self):
        from test_assembly_mesh import AssemblyMesh
        AssemblyMesh.fixture(self);v=self.v
        for sid,mode in zip(self.members,[v.FEA_BCM_SYMM,v.FEA_BCM_ASYMM]):
            bid=v.AddFeaBC(sid,v.FEA_BC_STRUCTURE)
            v.SetParmVal(v.FindParm(bid,'ConMode','FeaBC'),mode)
            v.SetParmVal(v.FindParm(bid,'YLTFlag','FeaBC'),1)
            v.SetParmVal(v.FindParm(bid,'YLGFlag','FeaBC'),1)
            v.SetParmVal(v.FindParm(bid,'YGTVal','FeaBC'),-.1)
            v.SetParmVal(v.FindParm(bid,'YLTVal','FeaBC'),.1)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);saved=self.model.read_bytes()
        data,out=self.worker(dict(action='analysis',name='FeaAssemblyMesh',structure=self.aid,formats=['CALCULIX']))
        self.assertEqual(out.read_bytes(),saved)
        text=(out.parent/'assembly.inp').read_text()
        self.assertIn('*EQUATION',text)
        exported=set()
        for block in text.split('*BOUNDARY\n')[1:]:
            for line in block.split('*',1)[0].splitlines():
                if line.strip():exported.add(tuple(map(int,line.split(','))))
        report=data['boundaryReport']
        self.assertEqual(report['definedConditions'],2)
        self.assertGreater(report['nodeCount'],0)
        self.assertEqual(report['degreeCount'],len(exported))
        self.assertEqual(report['nodeCount'],len({n for n,d in exported}))
        self.assertEqual(report['directionCounts'],[len({n for n,d in exported if d==i}) for i in range(1,7)])
        self.assertEqual(report['degreeCount'],3*report['nodeCount'])
