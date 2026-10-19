"""Native assembly export capabilities, member sizing and independent mesh parity."""
import sys,unittest,json
from pathlib import Path
import test_native,native_mesh
from mesh_io import read_gmsh
from vsp_runtime import load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class AssemblyMesh(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;self.members=[];points=[];self.aid=v.AddFeaAssembly();v.SetFeaAssemblyName(self.aid,'Two-wing assembly')
        for j,g in enumerate([self.gid,v.AddGeom('WING')]):
            v.SetGeomName(g,['Front wing','Rear wing'][j]);v.SetParmVal(v.FindParm(g,'X_Rel_Location','XForm'),j*20.)
            i=v.AddFeaStruct(g);s=v.GetFeaStructID(g,i);v.SetFeaStructName(g,i,['Front structure','Rear structure'][j]);self.members.append(s);v.AddFeaAssemblyStructure(self.aid,s)
            points.append(v.AddFeaPart(g,i,v.FEA_FIX_POINT))
            for n,x in [('BaseLen',1.+j),('MinLen',.2+j*.1),('MaxGap',.03),('GrowthRatio',1.3+j*.2)]:v.SetFeaMeshVal(g,i,getattr(v,native_mesh.FEA_INPUTS[n]),x)
        v.AddFeaAssemblyConnection(self.aid,points[0],self.members[0],0,points[1],self.members[1],0)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def test_native_assembly_capabilities_and_mixed_member_defaults(self):
        self.fixture();v=self.v;spec=native_mesh.assembly_schema(v,self.aid)
        self.assertEqual(spec['exportFormats'],['GMSH','CALCULIX','NASTRAN','MASS','STL'])
        for sid,m in zip(self.members,spec['guide']['memberSizing']):
            g=v.GetFeaStructParentGeomID(sid);i=v.GetFeaStructIndex(sid)
            self.assertEqual(m['id'],sid);self.assertEqual(m['name'],v.GetFeaStructName(g,i))
            expected={n:v.GetParmVal(pid) for n,pid in native_mesh.sizing_parameters(v,sid).items() if n not in native_mesh.FEA_CAD}
            self.assertEqual(m['values'],expected)
            self.assertEqual({n:m['values'][n] for n in native_mesh.FEA_INPUTS},{n:v.GetFeaMeshVal(g,i,getattr(v,e)) for n,e in native_mesh.FEA_INPUTS.items()})
        self.assertNotEqual(spec['guide']['memberSizing'][0]['values'],spec['guide']['memberSizing'][1]['values'])
        self.assertEqual({e['name']:e['values'][0] for e in spec['inputs']},spec['guide']['memberSizing'][0]['values'])

    def test_unsupported_exports_and_invalid_later_member_do_not_mutate_any_member(self):
        self.fixture();v=self.v
        before=lambda:{p:v.GetParmVal(p) for s in self.members+[self.aid] for p in v.FindContainerParmIDs(s)}
        original=before()
        for fmt in ['NKEY','SRF','CURV','PLOT3D','IGES','STEP']:
            with self.subTest(format=fmt),self.assertRaises(ValueError):native_mesh.run_assembly(v,dict(structure=self.aid,formats=[fmt]))
            self.assertEqual(before(),original)
        g=v.GetFeaStructParentGeomID(self.members[1]);i=v.GetFeaStructIndex(self.members[1]);v.SetFeaMeshVal(g,i,v.CFD_MAX_EDGE_LEN,.1);original=before()
        with self.assertRaises(ValueError):native_mesh.run_assembly(v,dict(structure=self.aid,inputs=[dict(name='MinLen',values=[.2])]))
        self.assertEqual(before(),original)

    def test_all_supported_exports_share_independent_original_assembly_mesh_and_sizing(self):
        self.fixture();v=self.v;values={'BaseLen':1.,'MinLen':.2,'MaxGap':.03,'NCircSeg':20.5,'GrowthRatio':1.5,'RigorLimit':1,'HalfMeshFlag':1}
        req=dict(action='analysis',name='FeaAssemblyMesh',structure=self.aid,formats=list(native_mesh.ASSEMBLY_EXPORTS),inputs=[dict(name=n,values=[x]) for n,x in values.items()])
        source=self.model.read_bytes();result,out=self.worker(req)
        self.assertEqual(out.read_bytes(),source);self.assertEqual(result['assemblyComputations'],1)
        self.assertEqual([{n:m['values'][n] for n in values} for m in result['memberSizing']],[values,values])
        self.assertTrue(all(set(m['values'])==set(native_mesh.FEA_PARAMETERS)-set(native_mesh.FEA_CAD) for m in result['memberSizing']))
        setup=json.loads((out.parent/'analysis-setup.json').read_text())
        for key in ['structure','formats','inputs','memberSizing','members']:self.assertEqual(setup[key],result[key])
        for fmt,ext in native_mesh.ASSEMBLY_EXPORTS.items():self.assertGreater((out.parent/('assembly.'+ext)).stat().st_size,0,fmt)
        self.assertGreater((out.parent/'assembly.dat').stat().st_size,0)
        for s in self.members:
            g=v.GetFeaStructParentGeomID(s);i=v.GetFeaStructIndex(s)
            for n,x in values.items():v.SetFeaMeshVal(g,i,getattr(v,native_mesh.FEA_INPUTS[n]),x)
        for p in v.FindContainerParmIDs(self.aid):
            if v.GetParmGroupName(p)=='ExportFEA' and v.GetParmName(p).endswith('_Export'):v.SetParmVal(p,int(v.GetParmName(p) in ['GMSH_Export','CALCULIX_Export']))
        v.SetFeaAssemblyFileName(self.aid,v.FEA_GMSH_FILE_NAME,str(self.path/'direct.msh'));v.SetFeaAssemblyFileName(self.aid,v.FEA_CALCULIX_FILE_NAME,str(self.path/'direct.inp'));v.ComputeFeaAssemblyMesh(self.aid)
        generated=native_mesh.assembly_schema(v,self.aid)['guide']['memberSizing']
        self.assertEqual(result['generatedMemberSizing'],generated)
        expected=read_gmsh(self.path/'direct.msh');actual=read_gmsh(out.parent/'assembly.msh')
        for key in ['nodeIDs','nodes','elements','groups']:self.assertEqual(actual[key],expected[key],key)
        self.assertIn('*EQUATION',(out.parent/'assembly.inp').read_text())
        nodes={};reading=False
        for line in (out.parent/'assembly.inp').read_text().splitlines():
            if line.startswith('*'):reading=line.upper().startswith('*NODE');continue
            if reading and line.strip():
                f=line.split(',');nodes[int(f[0])]=list(map(float,f[1:4]))
        gmsh_nodes=dict(zip(actual['nodeIDs'],actual['nodes']))
        # Native CalculiX includes connection-only fixed-point nodes omitted
        # by original Gmsh. Preserve both formats, verify all common nodes
        # and the entire solver deck against an independent native export.
        self.assertEqual({n:nodes[n] for n in gmsh_nodes},gmsh_nodes)
        self.assertEqual(len(set(nodes)-set(gmsh_nodes)),2)
        self.assertEqual((out.parent/'assembly.inp').read_bytes(),(self.path/'direct.inp').read_bytes())

    def test_individual_member_sizing_matches_original_mesh_and_study_retains_inputs(self):
        self.fixture();v=self.v;before=self.model.read_bytes()
        records=[dict(id=s,inputs=[dict(name='BaseLen',values=[x]),dict(name='MinLen',values=[x/5])]) for s,x in zip(self.members,[.7,1.4])]
        req=dict(action='analysis',name='FeaAssemblyMesh',structure=self.aid,formats=['GMSH'],inputs=[],memberInputs=records)
        result,out=self.worker(req)
        self.assertEqual([m['values']['BaseLen'] for m in result['memberSizing']],[.7,1.4])
        self.assertEqual(json.loads((out.parent/'analysis-setup.json').read_text())['memberSizing'],result['memberSizing'])
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        for record in records:
            s=record['id'];g=v.GetFeaStructParentGeomID(s);i=v.GetFeaStructIndex(s)
            for e in record['inputs']:v.SetFeaMeshVal(g,i,getattr(v,native_mesh.FEA_INPUTS[e['name']]),e['values'][0])
        for p in v.FindContainerParmIDs(self.aid):
            if v.GetParmGroupName(p)=='ExportFEA' and v.GetParmName(p).endswith('_Export'):v.SetParmVal(p,int(v.GetParmName(p)=='GMSH_Export'))
        v.SetFeaAssemblyFileName(self.aid,v.FEA_GMSH_FILE_NAME,str(self.path/'individual-direct.msh'));v.ComputeFeaAssemblyMesh(self.aid)
        actual=read_gmsh(out.parent/'assembly.msh');expected=read_gmsh(self.path/'individual-direct.msh')
        self.assertEqual(actual.pop('filename'),'assembly.msh');self.assertEqual(expected.pop('filename'),'individual-direct.msh')
        self.assertEqual(actual,expected)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        import native_study_worker,native_worker
        cleaned=native_study_worker.validate(v,dict(stages=[req],axes=[]),native_worker.parameter,native_worker.analysis_schema,native_worker.set_inputs)
        self.assertEqual(cleaned['stages'][0]['memberInputs'],records)
        self.assertEqual([m['values']['BaseLen'] for m in cleaned['stageSchemas'][0]['guide']['memberSizing']],[.7,1.4])
        self.assertEqual(out.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)

    def test_saved_run_reload_and_reuse_preserve_submitted_offsets(self):
        import native_service as service,time,tempfile
        self.fixture();previous=service.WORK,service.JOBS
        try:
            with tempfile.TemporaryDirectory() as folder:
                service.WORK=Path(folder);service.JOBS={}
                request=dict(name='FeaAssemblyMesh',structure=self.aid,formats=['GMSH'],inputs=[],memberInputs=[dict(id=sid,inputs=[dict(name='NodeOffset',values=[0.]),dict(name='ElementOffset',values=[0.])]) for sid in self.members])
                job=service.start_job(request,model_source=self.model,source_revision='assembly-offset-reuse')
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    state=service.job_state(job['id'])
                    if state.get('finished'):break
                    time.sleep(.02)
                self.assertEqual(state['status'],'complete',state)
                service.JOBS={};cold=service.job_state(job['id'])
                self.assertEqual(cold['result']['memberSizing'],cold['analysisSetup']['memberSizing'])
                self.assertEqual([m['values']['NodeOffset'] for m in cold['result']['memberSizing']],[0.,0.])
                self.assertNotEqual(cold['result']['generatedMemberSizing'],cold['result']['memberSizing'])
                reused=[dict(id=m['id'],inputs=[dict(name=n,values=[x]) for n,x in m['values'].items()]) for m in cold['result']['memberSizing']]
                result,out=self.worker(dict(action='analysis',name='FeaAssemblyMesh',structure=self.aid,formats=['GMSH'],inputs=[],memberInputs=reused))
                self.assertEqual(result['memberSizing'],cold['result']['memberSizing'])
                original=service.job_folder(job['id'])/'assembly.msh'
                self.assertEqual((out.parent/'assembly.msh').read_bytes(),original.read_bytes())
        finally:service.WORK,service.JOBS=previous

    def test_invalid_member_sizing_does_not_change_any_native_member(self):
        self.fixture();v=self.v
        before={p:v.GetParmVal(p) for s in self.members+[self.aid] for p in v.FindContainerParmIDs(s)}
        records=[dict(id=self.members[0],inputs=[dict(name='BaseLen',values=[.7])]),dict(id=self.members[1],inputs=[dict(name='MinLen',values=[100])])]
        for items in [records,[records[0],records[0]],[dict(id='missing',inputs=[])]]:
            with self.assertRaises(ValueError):native_mesh.run_assembly(v,dict(structure=self.aid,memberInputs=items))
            self.assertEqual({p:v.GetParmVal(p) for p in before},before)
        merged=native_mesh.assembly_inputs(dict(memberInputs=[records[0]],inputs=[dict(name='BaseLen',values=[3])]),self.members)
        self.assertEqual([e['values'] for e in merged[self.members[0]] if e['name']=='BaseLen'],[[3]])

    def test_independent_member_sweeps_preserve_other_settings_and_original_mesh(self):
        self.fixture();v=self.v;source=self.model.read_bytes()
        import native_studies,native_study_worker,native_worker,itertools
        records=[dict(id=s,inputs=[dict(name='BaseLen',values=[x]),dict(name='MinLen',values=[x/5])]) for s,x in zip(self.members,[.7,1.4])]
        stage=dict(name='FeaAssemblyMesh',structure=self.aid,formats=['GMSH','CALCULIX'],inputs=[dict(name='MaxGap',values=[.04])],memberInputs=records)
        axes=[dict(kind='input',stage=0,member=s,name='BaseLen',values=values) for s,values in zip(self.members,[[.8,1.],[1.6,1.8]])]
        plan=native_study_worker.validate(v,dict(stages=[stage],axes=axes),native_worker.parameter,native_worker.analysis_schema,native_worker.set_inputs)
        self.assertEqual([a['member'] for a in plan['axes']],self.members)
        self.assertEqual([a['baseline'] for a in plan['axes']],[.7,1.4]);self.assertEqual(plan['caseCount'],4)
        for i,values in enumerate(itertools.product(*[a['values'] for a in plan['axes']])):
            req=native_studies.case_stages(plan,dict(values=values))[0]
            result,out=self.worker(dict(req,action='analysis'))
            self.assertEqual([m['values']['BaseLen'] for m in result['memberSizing']],list(values))
            self.assertEqual([m['values']['MinLen'] for m in result['memberSizing']],[.7/5,1.4/5])
            self.assertEqual([m['values']['MaxGap'] for m in result['memberSizing']],[.04,.04])
            v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
            for j,s in enumerate(self.members):
                g=v.GetFeaStructParentGeomID(s);index=v.GetFeaStructIndex(s)
                for name,x in [('BaseLen',values[j]),('MinLen',[.7/5,1.4/5][j]),('MaxGap',.04)]:v.SetFeaMeshVal(g,index,getattr(v,native_mesh.FEA_INPUTS[name]),x)
            for p in v.FindContainerParmIDs(self.aid):
                if v.GetParmGroupName(p)=='ExportFEA' and v.GetParmName(p).endswith('_Export'):v.SetParmVal(p,int(v.GetParmName(p) in ['GMSH_Export','CALCULIX_Export']))
            direct=self.path/('member-sweep-'+str(i));direct.mkdir()
            for fmt,ext in [('GMSH','msh'),('CALCULIX','inp')]:v.SetFeaAssemblyFileName(self.aid,getattr(v,'FEA_'+fmt+'_FILE_NAME'),str(direct/('assembly.'+ext)))
            v.ComputeFeaAssemblyMesh(self.aid)
            self.assertEqual(read_gmsh(out.parent/'assembly.msh'),read_gmsh(direct/'assembly.msh'))
            for name in ['assembly.msh','assembly.inp']:self.assertEqual((out.parent/name).read_bytes(),(direct/name).read_bytes())
            self.assertEqual(out.read_bytes(),source)
        self.assertEqual(self.model.read_bytes(),source)

    def test_member_sweep_rejects_missing_members_and_overlapping_shared_fields(self):
        self.fixture();v=self.v
        import native_study_worker,native_worker
        stage=dict(name='FeaAssemblyMesh',structure=self.aid,inputs=[])
        member=dict(kind='input',stage=0,member=self.members[0],name='BaseLen',values=[1.])
        for axes in [[{**member,'member':'missing'}],[member,dict(kind='input',stage=0,name='BaseLen',values=[2.])],[member,member],[{**member,'values':[-1.]}]]:
            with self.assertRaises(ValueError):native_study_worker.validate(v,dict(stages=[stage],axes=axes),native_worker.parameter,native_worker.analysis_schema,native_worker.set_inputs)

if __name__=='__main__':unittest.main()
