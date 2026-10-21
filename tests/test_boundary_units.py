"""Boundary coordinate filters use scaled solver coordinates, not model units."""
import sys,unittest
import test_native

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class BoundaryUnits(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_feet_model_filter_units_match_each_original_solver_export(self):
        v=self.v;index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index)
        bid=v.AddFeaBC(sid,v.FEA_BC_STRUCTURE)
        vehicle=v.GetVehicleID();model_unit=v.FindParm(vehicle,'StructModelUnit','FeaStructure');solver=v.FindParm(vehicle,'StructUnit','FeaStructure')
        v.SetParmVal(model_unit,v.LEN_FT)
        setp=lambda n,x:v.SetParmVal(v.FindParm(bid,n,'FeaBC'),x)
        setp('ConMode',v.FEA_BCM_PIN);setp('YLGFlag',1);setp('YLTFlag',1)
        cases=[(v.SI_UNIT,'m',.3048),(v.CGS_UNIT,'cm',30.48),(v.MPA_UNIT,'mm',304.8),(v.BFT_UNIT,'ft',1.),(v.BIN_UNIT,'in',12.)]
        for system,unit,scale in cases:
            with self.subTest(system=system):
                v.SetParmValUpdate(solver,system);v.Update()
                setp('YGTVal',-scale);setp('YLTVal',scale)
                for key,value in [('CFD_MAX_EDGE_LEN',scale),('CFD_MIN_EDGE_LEN',.2*scale),('CFD_MAX_GAP',.03*scale)]:v.SetFeaMeshVal(self.gid,index,getattr(v,key),value)
                v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);saved=self.model.read_bytes()
                state,_=self.worker(dict(action='state'))
                b=next(b for b in state['tools']['boundaryConditions'] if b['id']==bid)
                self.assertEqual(b['coordinateUnit'],unit)
                for name in ['YGTVal','YLTVal']:
                    field=next(p for p in b['params'] if p['name']==name)
                    self.assertEqual(field['nativeUnit'],unit);self.assertIn('('+unit+')',field['label'])
                    self.assertEqual(field['value'],v.GetParmVal(field['id']))
                data,out=self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=sid,formats=['CALCULIX']))
                self.assertEqual(self.model.read_bytes(),saved);self.assertEqual(out.read_bytes(),saved)
                direct=self.path/'direct.inp';v.SetFeaMeshFileName(self.gid,index,v.FEA_CALCULIX_FILE_NAME,str(direct));v.ComputeFeaMesh(self.gid,index,v.FEA_CALCULIX_FILE_NAME)
                self.assertEqual((out.parent/'structure.inp').read_bytes(),direct.read_bytes())
                nodes={};constrained=set();section=''
                for line in direct.read_text().splitlines():
                    if line.startswith('**'):continue
                    if line.startswith('*'):section=line.split(',',1)[0].upper();continue
                    if not line.strip():continue
                    fields=line.split(',')
                    if section=='*NODE':nodes[int(fields[0])]=list(map(float,fields[1:4]))
                    elif section=='*BOUNDARY':constrained.add(int(fields[0]))
                self.assertGreater(len(constrained),0);self.assertLess(len(constrained),len(nodes))
                self.assertTrue(all(abs(nodes[n][1])<=scale+1e-6 for n in constrained))
                self.assertTrue(any(abs(p[1])>2*scale for p in nodes.values()))
                self.assertEqual(data['boundaryReport']['nodeCount'],len(constrained))

    def test_changing_solver_system_relabels_but_preserves_native_filter_values(self):
        v=self.v;index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index);bid=v.AddFeaBC(sid,v.FEA_BC_STRUCTURE)
        pid=v.FindParm(bid,'YLTVal','FeaBC');v.SetParmVal(pid,.75)
        solver=v.FindParm(v.GetVehicleID(),'StructUnit','FeaStructure')
        v.SetParmVal(solver,v.BFT_UNIT);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=solver,value=v.SI_UNIT))
        reopened,_=self.worker(dict(action='state'),path)
        for data in [state,reopened]:
            b=next(b for b in data['tools']['boundaryConditions'] if b['id']==bid)
            self.assertEqual(b['coordinateUnit'],'m')
            field=next(p for p in b['params'] if p['id']==pid)
            self.assertEqual(field['value'],.75);self.assertEqual(field['nativeUnit'],'m')
