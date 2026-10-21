"""Specialist saved-case requirements and results against original native calls."""
import sys,unittest,math,json,subprocess
from pathlib import Path
import test_geometry_cases,test_native,test_gear_controls
import native_geometry_cases,native_references,native_worker
from vsp_runtime import load,interpreter

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class NativeGearCases(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    assert_native_geometry=test_gear_controls.NativeGearControls.assert_native_geometry
    canonical=test_geometry_cases.NativeGeometryCases.canonical
    assertResults=test_geometry_cases.NativeGeometryCases.assertResults

    def fixture(self):
        v=self.v;self.gear=v.AddGeom('GEAR');self.bogies=[v.CreateAndAddBogie(self.gear) for _ in range(3)]
        for bid,(x,y) in zip(self.bogies,[(0,0),(6,3),(6,-3)]):
            v.SetParmVal(bid,'XContactPt','Bogie',x);v.SetParmVal(bid,'YContactPt','Bogie',y)
        for axis,val in [('X',3),('Y',0),('Z',3)]:
            for suffix,offset in [('Min',-.1),('Max',.1),('Nominal',0)]:v.SetParmVal(self.gear,axis+'CG'+suffix+'Local','GroundPlane',val+offset)
        self.aux=v.AddGeom('AUXILIARY',self.gear);v.SetParmVal(self.aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_THREE_PT_GROUND)
        for i,b in enumerate(self.bogies):v.SetAuxiliaryGeomContactPtID(self.aux,i,b)
        v.Update();v.SetAuxiliaryGeomContactPtID(self.aux,0,self.bogies[0]);v.Update()
        self.cid=v.AddGeometryAnalysis();v.SetContainerName(self.cid,'Gear loads')
        v.SetParmVal(self.cid,'IntererenceCheckType','InterferenceCase',v.GEAR_WEIGHT_DISTRIBUTION_ANALYSIS)
        v.SetParmVal(self.cid,'PrimaryType','InterferenceCase',v.GEOM_TARGET)
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        # Persist only the original manager's reference field, through native XML.
        try:native_references.set_reference(v,self.cid,'GeometryAnalysis','PrimaryGeomID',self.aux)
        except native_references.ReloadRequired:pass

    def test_gear_reactions_match_native_and_require_compatible_plane(self):
        self.fixture();v=self.v
        # Reference reload is necessary for the original native case object.
        for b in list(v.GetAllBogies(self.gear)):v.DelBogie(self.gear,b)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.SetAuxiliaryGeomContactPtID(self.aux,0,self.bogies[0]);v.Update()
        native_geometry_cases.update(v);v.SetAnalysisInputDefaults('GeometryAnalysis');v.SetStringAnalysisInput('GeometryAnalysis','CaseID',[self.cid]);v.ExecAnalysis('GeometryAnalysis');native_worker.errors(v)
        expected=native_worker.collect_results(v)
        baseline=self.model.read_bytes()
        data,path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[self.cid])]))
        self.assertResults(expected,data['results']);self.assertEqual(path.read_bytes(),baseline)
        reactions=next(e['values'] for r in data['results'] for e in r['entries'] if e['name']=='NominalReactions')
        self.assertTrue(all(math.isfinite(x) for row in reactions for x in row))
        self.assertEqual(len(reactions),1);self.assertEqual(len(reactions[0]),3)
        self.assertTrue(all(x>0 for x in reactions[0]))
        setup=data['geometryCases'][0]['specialistSetup'];self.assertEqual(setup['problems'],[]);self.assertEqual(setup['selected'],self.aux)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(self.aux,'AuxiliaryGeomType','Design'),value=v.AUX_GEOM_TWO_PT_GROUND),path)
        setup=state['tools']['geometryCases'][0]['specialistSetup'];self.assertTrue(setup['problems']);before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'three-contact'):self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[self.cid])]),path)
        self.assertEqual(path.read_bytes(),before)
        type_id=v.FindParm(self.cid,'IntererenceCheckType','InterferenceCase')
        for typ in (v.GEAR_CG_TIPBACK_ANALYSIS,v.GEAR_TIPOVER_ANALYSIS):
            state,path=self.worker(dict(action='mutate',operation='parameter',id=type_id,value=typ),path)
            setup=state['tools']['geometryCases'][0]['specialistSetup']
            self.assertEqual(setup['role'],'Primary');self.assertEqual(setup['problems'],[])
            self.assertEqual([g['id'] for g in setup['compatible']],[self.aux])
        state,path=self.worker(dict(action='mutate',operation='parameter',id=type_id,value=v.GEAR_TURN_ANALYSIS),path)
        setup=state['tools']['geometryCases'][0]['specialistSetup'];self.assertEqual(setup['role'],'Secondary');self.assertTrue(setup['problems'])
        secondary=next(p for c in state['tools']['geometryCases'] if c['id']==self.cid for p in c['params'] if p['name']=='SecondaryType')
        self.assertEqual(secondary['value'],v.GEOM_TARGET);self.assertTrue(secondary['readOnly'])
        with self.assertRaisesRegex(ValueError,'requires a secondary component'):self.worker(dict(action='mutate',operation='parameter',id=secondary['id'],value=v.SET_TARGET),path)
        state,path=self.worker(dict(action='mutate',operation='geometry-case-reference',id=self.cid,key='SecondaryGeomID',value=self.aux),path)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(self.aux,'AuxiliaryGeomType','Design'),value=v.AUX_GEOM_THREE_PT_GROUND),path)
        setup=state['tools']['geometryCases'][0]['specialistSetup'];self.assertEqual(setup['problems'],[])

    def test_tipback_tipover_and_turn_match_original_native_results(self):
        self.fixture();v=self.v
        v.SetParmVal(self.bogies[0],'SteeringAngle','Bogie',35)
        direct=self.path/'direct-cases.py'
        root=Path(native_worker.__file__).parent
        direct.write_text("import sys,json;sys.path.insert(0,"+repr(str(root))+");from vsp_runtime import load;import native_worker,native_geometry_cases;v=load();v.ReadVSPFile(sys.argv[1]);v.Update();g=sys.argv[3];v.SetAuxiliaryGeomContactPtID(g,0,v.GetAuxiliaryGeomContactPtID(g,0));v.Update();native_geometry_cases.update(v);v.SetAnalysisInputDefaults('GeometryAnalysis');v.SetStringAnalysisInput('GeometryAnalysis','CaseID',[sys.argv[2]]);v.ExecAnalysis('GeometryAnalysis');native_worker.errors(v);open(sys.argv[4],'w').write(json.dumps(native_worker.collect_results(v)))")
        for typ in (v.GEAR_CG_TIPBACK_ANALYSIS,v.GEAR_TIPOVER_ANALYSIS,v.GEAR_TURN_ANALYSIS):
            with self.subTest(calculation=typ):
                mode=v.AUX_GEOM_THREE_PT_GROUND if typ==v.GEAR_TURN_ANALYSIS else v.AUX_GEOM_TWO_PT_GROUND
                v.SetParmVal(self.aux,'AuxiliaryGeomType','Design',mode)
                contact_ids=self.bogies if typ!=v.GEAR_CG_TIPBACK_ANALYSIS else [self.bogies[1],self.bogies[2],self.bogies[0]]
                for i,b in enumerate(contact_ids):v.SetAuxiliaryGeomContactPtID(self.aux,i,b)
                v.SetParmVal(self.cid,'IntererenceCheckType','InterferenceCase',typ)
                v.SetParmVal(self.cid,'PrimaryType','InterferenceCase',v.GEOM_TARGET)
                v.SetParmVal(self.cid,'SecondaryType','InterferenceCase',v.GEOM_TARGET)
                v.Update();v.SetAuxiliaryGeomContactPtID(self.aux,0,contact_ids[0]);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                try:native_references.set_references(v,self.cid,'GeometryAnalysis',dict(PrimaryGeomID=self.gid if typ==v.GEAR_TURN_ANALYSIS else self.aux,SecondaryGeomID=self.aux))
                except native_references.ReloadRequired:pass
                out=self.path/'direct-results.json';p=subprocess.run([interpreter(),str(direct),str(self.model),self.cid,self.aux,str(out)],capture_output=True,text=True,timeout=90)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr);expected=json.loads(out.read_text())
                before=self.model.read_bytes();data,path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[self.cid])]))
                self.assertResults(expected,data['results']);self.assertEqual(path.read_bytes(),before)
                key='GearTurnRadii' if typ==v.GEAR_TURN_ANALYSIS else 'NominalTip'
                values=next(e['values'] for r in data['results'] for e in r['entries'] if e['name']==key)
                self.assertTrue(values);self.assertTrue(all(math.isfinite(x) for x in values))
                drawing=json.loads((path.parent/data['guideFile']).read_text())
                native_points=next(e['values'] for r in expected for e in r['entries'] if e['name']=='Pts')
                self.assertEqual(drawing['nodes'],native_points)
                self.assertEqual([e['nodes'] for e in drawing['elements']],[[i,i+1] for i in range(0,len(native_points),2)])

    def test_cg_frames_preserve_native_transforms_and_guard_followers(self):
        self.fixture();v=self.v
        # Use original gear parameters and native limits; never transform in Studio.
        for name,value in [('X_Rel_Location',5),('Y_Rel_Location',2),('Z_Rel_Location',1),('Z_Rel_Rotation',20)]:v.SetParmValUpdate(self.gear,name,'XForm',value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        path=self.model
        for frame in (0,1):
            state,path=self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(self.gear,'CGLocalFlag','GroundPlane'),value=frame),path)
            v.SetParmValUpdate(self.gear,'CGLocalFlag','GroundPlane',frame);v.Update()
            self.assert_native_geometry(state,self.gear)
            follower='Local' if frame==0 else 'Global'
            fields=next(c for c in state['components'] if c['id']==self.gear)['params']
            for p in fields:
                if p['rawGroup']=='GroundPlane' and 'CG' in p['name'] and p['name'].endswith(follower):
                    self.assertTrue(p['displayReadOnly']);before=path.read_bytes()
                    with self.assertRaisesRegex(ValueError,'Calculated'):self.worker(dict(action='mutate',operation='parameter',id=p['id'],value=p['value']),path)
                    self.assertEqual(path.read_bytes(),before)

    def test_native_mode_preset_is_resolved_at_execution_without_baseline_rejection(self):
        self.fixture();v=self.v;v.SetSetName(3,'Gear check selection');v.SetSetFlag(self.aux,3,True)
        mode=v.CreateAndAddMode('Tipback configuration',3,-1)
        group=v.AddVarPresetGroup('Ground plane family');pid=v.FindParm(self.aux,'AuxiliaryGeomType','Design');v.AddVarPresetParm(group,pid)
        setting=v.AddVarPresetSetting(group,'Two contacts');v.SetVarPresetParmVal(group,setting,pid,v.AUX_GEOM_TWO_PT_GROUND);v.ModeAddGroupSetting(mode,group,setting)
        v.SetParmVal(self.cid,'IntererenceCheckType','InterferenceCase',v.GEAR_CG_TIPBACK_ANALYSIS);v.SetParmVal(self.cid,'PrimaryType','InterferenceCase',v.MODE_TARGET)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        try:native_references.set_references(v,self.cid,'GeometryAnalysis',dict(PrimaryModeID=mode,PrimaryGeomID=''))
        except native_references.ReloadRequired:pass
        state,path=self.worker(dict(action='state'))
        setup=state['tools']['geometryCases'][0]['specialistSetup'];self.assertEqual(setup['problems'],[]);self.assertEqual(setup['selected'],self.aux)
        self.assertEqual(setup['mode']['normalSet'],3);self.assertEqual(setup['mode']['presets'],[dict(group=group,setting=setting)])
        # Baseline three-contact geometry is intentionally incompatible with
        # tipback until the ORIGINAL mode applies its two-contact preset.
        self.assertEqual(next(p['value'] for c in state['components'] if c['id']==self.aux for p in c['params'] if p['name']=='AuxiliaryGeomType'),v.AUX_GEOM_THREE_PT_GROUND)
        root=Path(native_worker.__file__).parent;script=self.path/'mode-direct.py';out=self.path/'mode-direct.json'
        script.write_text("import sys,json;sys.path.insert(0,"+repr(str(root))+");from vsp_runtime import load;import native_worker,native_geometry_cases;v=load();v.ReadVSPFile(sys.argv[1]);v.Update();native_geometry_cases.update(v);v.SetAnalysisInputDefaults('GeometryAnalysis');v.SetStringAnalysisInput('GeometryAnalysis','CaseID',[sys.argv[2]]);v.ExecAnalysis('GeometryAnalysis');native_worker.errors(v);open(sys.argv[3],'w').write(json.dumps(native_worker.collect_results(v)))")
        proc=subprocess.run([interpreter(),str(script),str(path),self.cid,str(out)],capture_output=True,text=True,timeout=90);self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        before=path.read_bytes();data,path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[self.cid])]),path)
        self.assertResults(json.loads(out.read_text()),data['results']);self.assertEqual(path.read_bytes(),before)
        # A mode changing the auxiliary also enables a later component case in
        # native ExecAll order. Both cases share the original mode side effect.
        # Single-case compatibility remains checked against its own baseline.
        state,path=self.worker(dict(action='mutate',operation='geometry-case-add',name='After mode',type=v.GEAR_CG_TIPBACK_ANALYSIS),path)
        later=state['tools']['geometryCases'][-1]
        primary_id=next(p['id'] for p in later['params'] if p['name']=='PrimaryType')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=primary_id,value=v.GEOM_TARGET),path)
        state,path=self.worker(dict(action='mutate',operation='geometry-case-reference',id=later['id'],key='PrimaryGeomID',value=self.aux),path)
        # The second case is incompatible until the first native mode executes.
        self.assertTrue(state['tools']['geometryCases'][-1]['specialistSetup']['problems'])
        proc=subprocess.run([interpreter(),str(script),str(path),'ALL',str(out)],capture_output=True,text=True,timeout=90);self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        before=path.read_bytes();data,path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=['ALL'])]),path)
        self.assertResults(json.loads(out.read_text()),data['results']);self.assertEqual(path.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='mode-delete',id=mode),path)
        self.assertTrue(state['tools']['geometryCases'][0]['specialistSetup']['problems'])
        with self.assertRaisesRegex(ValueError,'available primary native mode'):self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[self.cid])]),path)



    def test_transformed_component_planes_match_native_and_guide_valid_targets(self):
        self.fixture();v=self.v
        for name,value in [('IntererenceCheckType',v.PLANE_STATIC_DISTANCE_INTERFERENCE),('PrimaryType',v.GEOM_TARGET),('SecondaryType',v.GEOM_TARGET)]:v.SetParmVal(self.cid,name,'InterferenceCase',value)
        for axis,value in [('X_Rel_Location',1.),('Y_Rel_Location',2.),('Z_Rel_Location',-1.),('Y_Rel_Rotation',13.),('Z_Rel_Rotation',20.)]:v.SetParmVal(self.gear,axis,'XForm',value)
        script=self.path/'plane-reference.py';out=self.path/'plane-reference.json';root=Path(native_worker.__file__).parent
        script.write_text("import sys,json;sys.path.insert(0,"+repr(str(root))+");from vsp_runtime import load;import native_worker,native_geometry_cases;v=load();v.ReadVSPFile(sys.argv[1]);v.Update();g=sys.argv[3];v.SetAuxiliaryGeomContactPtID(g,0,v.GetAuxiliaryGeomContactPtID(g,0));v.Update();native_geometry_cases.update(v);v.SetAnalysisInputDefaults('GeometryAnalysis');v.SetStringAnalysisInput('GeometryAnalysis','CaseID',[sys.argv[2]]);v.ExecAnalysis('GeometryAnalysis');native_worker.errors(v);open(sys.argv[4],'w').write(json.dumps(native_worker.collect_results(v)))")
        for target,mode in [(self.gear,v.AUX_GEOM_THREE_PT_GROUND),(self.aux,v.AUX_GEOM_THREE_PT_GROUND),(self.aux,v.AUX_GEOM_THREE_PT_CCE)]:
            with self.subTest(target=target,mode=mode):
                v.SetParmVal(self.aux,'AuxiliaryGeomType','Design',mode);v.Update();v.SetAuxiliaryGeomContactPtID(self.aux,0,self.bogies[0]);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                try:native_references.set_references(v,self.cid,'GeometryAnalysis',dict(PrimaryGeomID=self.gid,SecondaryGeomID=target))
                except native_references.ReloadRequired:pass
                before=self.model.read_bytes();state,_=self.worker({'action':'state'});setup=state['tools']['geometryCases'][0]['specialistSetup'];self.assertEqual(setup['title'],'Plane clearance setup');self.assertEqual(setup['problems'],[]);self.assertIn(target,[g['id'] for g in setup['compatible']])
                process=subprocess.run([interpreter(),str(script),str(self.model),self.cid,self.aux,str(out)],capture_output=True,text=True,timeout=90);self.assertEqual(process.returncode,0,process.stdout+process.stderr)
                actual,path=self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[self.cid])]))
                self.assertResults(json.loads(out.read_text()),actual['results']);self.assertEqual(path.read_bytes(),before)
        _,path=self.worker(dict(action='mutate',operation='geometry-case-reference',id=self.cid,key='SecondaryGeomID',value=self.gid));before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'ground plane'):
            self.worker(dict(action='analysis',name='GeometryAnalysis',inputs=[dict(name='CaseID',values=[self.cid])]),path)
        self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main()
