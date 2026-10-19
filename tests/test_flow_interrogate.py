"""Saved-database restoration equals a fresh independent original solver run."""
import csv,hashlib,io,json,os,shutil,subprocess,sys,unittest
from pathlib import Path
import test_saved_solutions,test_studies
import native_service as service
import native_flow_slices
import native_studies as studies
from vsp_runtime import load,distribution


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching original SDK runtime.')
class NativeFlowInterrogate(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    wait_job=test_saved_solutions.NativeSavedSolutions.wait_job
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def test_rotating_propeller_saved_planes_keep_every_native_time_record(self):
        self.rotor_case(self.v.VSPAERO_PROP_UNSTEADY,0,5)

    def test_automatic_rotor_timing_preserves_original_sentinels_and_every_plane(self):
        self.rotor_case(self.v.VSPAERO_PROP_UNSTEADY,1,21)

    def test_pseudo_steady_rotor_saved_planes_match_original_solver(self):
        self.rotor_case(self.v.VSPAERO_PROP_PSEUDO_STEADY,0,1)

    def test_different_speed_rotors_preserve_native_automatic_timing_and_all_planes(self):
        self.rotor_case(self.v.VSPAERO_PROP_UNSTEADY,1,81,rotor_speeds=(2000.,1000.))

    def rotor_case(self,mode,automatic,expected_records,rotor_speeds=None):
        v=self.v;v.DeleteGeom(self.gid)
        prop=v.AddGeom('PROP');v.SetGeomName(prop,'Native rotating propeller')
        if rotor_speeds:
            other=v.AddGeom('PROP');v.SetGeomName(other,'Native slower propeller')
            v.SetParmValUpdate(other,'Y_Rel_Location','XForm',40.)
            aero=v.FindContainer('VSPAEROSettings',0)
            uniform=next(p for p in v.FindContainerParmIDs(aero) if v.GetParmName(p)=='UniformPropRPMFlag')
            v.SetParmValUpdate(uniform,0)
            v.GetNumUnsteadyGroups()
            for geom,speed in zip((prop,other),rotor_speeds):
                group=next(v.FindUnsteadyGroup(i) for i in range(v.GetNumUnsteadyGroups()) if geom in v.GetUnsteadyGroupCompIDs(i))
                rpm=next(p for p in v.FindContainerParmIDs(group) if v.GetParmName(p)=='RPM')
                v.SetParmValUpdate(rpm,speed)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);baseline=self.model.read_bytes()
        settings={'GeomSet':-1,'ThinGeomSet':0,'RefFlag':v.MANUAL_REF,'AlphaNpts':1,'MachStart':.1,'MachNpts':1,'NCPU':1,'PropBladesMode':mode,'AutoTimeStepFlag':automatic,'AutoTimeNumRevs':1,'NumTimeSteps':4,'TimeStepSize':.002,'StartAveragingTimeStep':1,'NumWakeNodes':8,'WakeNumIter':3}
        try:
            source=self.wait_job(service.start_job(dict(name='VSPAEROSweep',revision=service.REVISION,inputs=[dict(name=k,values=[x]) for k,x in settings.items()]))['id'])
            folder=service.job_folder(source['id']);original={p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
            self.assertNotIn('nan',(folder/'aircraft.history').read_text().lower())
            if automatic:
                fields={e['name']:e['value'] for e in source['result']['solverSetup']['fields']}
                self.assertEqual(fields['NumberOfTimeSteps'],'-1')
                self.assertEqual(float(fields['TimeStep']),-1.)
            if rotor_speeds:
                groups=source['result']['solverSetup']['groups']
                written=[{e['name']:e['value'] for e in g['fields']} for g in groups]
                self.assertEqual(sorted(float(g['Omega']) for g in written),sorted(speed*2*3.141592653589793/60 for speed in rotor_speeds))
            entries=[dict(name='XSlicePosVec',values=[1.25]),dict(name='YSlicePosVec',values=[1.]),dict(name='ZSlicePosVec',values=[]),dict(name='QuadTreeBufferLevels',values=[0])]
            result=self.wait_job(service.start_job(dict(name='FlowPlaneSlicer',sourceRun=source['id'],revision=service.REVISION,inputs=entries))['id'])
            from aero_io import case_list,read_flow_plane
            records=case_list(folder/'aircraft.adb');self.assertEqual(len(records),expected_records)
            self.assertEqual(len(result['result']['flowPlanes']),2*len(records))
            for p in result['result']['flowPlanes']:
                self.assertEqual(p['timeAccurate'],mode==v.VSPAERO_PROP_UNSTEADY)
                self.assertEqual(p['solutionLabel'],records[p['solutionRecord']-1]['label'])
                read_flow_plane(service.job_folder(result['id'])/p['file'])
            direct=self.path/'original-rotor-final';direct.mkdir()
            child=service.job_folder(result['id'])
            for p in child.iterdir():
                if p.suffix in ('.vspgeom','.vspaero','.vkey','.groups'):shutil.copy2(p,direct/p.name)
            with (direct/'native.log').open('w') as log:
                flags=['-unsteady'] if mode==v.VSPAERO_PROP_UNSTEADY else []
                run=subprocess.run([str(distribution()/'vspaero'),'-omp','1',*flags,str(direct/'aircraft')],cwd=direct,stdout=log,stderr=log,timeout=60)
            self.assertEqual(run.returncode,0)
            self.assertEqual(case_list(direct/'aircraft.adb'),records)
            reference_files=list(direct.glob('*.case.*.quad.*.dat'));self.assertEqual(len(reference_files),2)
            for p in reference_files:
                import re
                actual=child/re.sub(r'\.case\.-?\d+\.',f'.case.{len(records)}.',p.name)
                self.assertEqual([float(x) for x in actual.read_text().split()],[float(x) for x in p.read_text().split()],p.name)
            self.assertEqual(original,{p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()})
            self.assertEqual(self.model.read_bytes(),baseline)
        finally:
            suffix='' if not automatic and mode==v.VSPAERO_PROP_UNSTEADY else '-automatic' if automatic else '-pseudo-steady'
            if rotor_speeds:suffix='-different-speeds'
            evidence=Path(__file__).resolve().parents[1]/('.workspace/evidence/rotating-propeller-saved-flow-native'+suffix)
            shutil.copytree(self.path,evidence,dirs_exist_ok=True)

    def test_native_pitch_reader_restores_original_final_planes_without_resolving(self):
        v=self.v;v.DeleteAllCpSlices()
        for axis,position in [(v.X_DIR,1.25),(v.Y_DIR,0.),(v.Y_DIR,1.)]:v.AddCpSlice(axis,position)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);baseline=self.model.read_bytes()
        settings={'GeomSet':-1,'ThinGeomSet':0,'RefFlag':v.COMPONENT_REF,'WingID':self.gid,'AlphaStart':4.,'AlphaNpts':1,'MachStart':.1,'MachNpts':1,'NCPU':1,'NonLinearConvergenceFactor':0.,'UnsteadyType':v.STABILITY_Q_ANALYSIS}
        source=self.wait_job(service.start_job(dict(name='VSPAEROSweep',revision=service.REVISION,inputs=[dict(name=k,values=[x]) for k,x in settings.items()]))['id'])
        folder=service.job_folder(source['id']);original={p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
        self.assertNotIn('nan',(folder/'aircraft.history').read_text().lower())
        entries=[dict(name='XSlicePosVec',values=[1.25]),dict(name='YSlicePosVec',values=[0.,1.]),dict(name='ZSlicePosVec',values=[]),dict(name='QuadTreeBufferLevels',values=[0])]
        result=self.wait_job(service.start_job(dict(name='FlowPlaneSlicer',sourceRun=source['id'],revision=service.REVISION,inputs=entries))['id'])
        child=service.job_folder(result['id']);provenance=result['result']['readerProvenance']
        self.assertEqual(provenance['inputDatabaseSha256'],hashlib.sha256(original['aircraft.adb']).hexdigest())
        self.assertEqual(provenance['inputDatabaseSha256'],provenance['outputDatabaseSha256'])
        from aero_io import read_flow_plane,case_list
        records=case_list(folder/'aircraft.adb');self.assertEqual(len(records),129)
        files=sorted(child.glob('*.case.*.quad.*.dat'));self.assertEqual(len(files),3*len(records))
        summaries={p['file']:p for p in result['result']['flowPlanes']}
        for p in files:
            read_flow_plane(p)
            summary=summaries[p.name];self.assertTrue(summary['timeAccurate'])
            record=summary['solutionRecord']
            self.assertEqual(summary['solutionLabel'],records[record-1]['label'])
            if record==len(records):
                reference=p.name.replace('.case.129.','.case.1.')
                self.assertEqual(p.read_bytes(),(folder/reference).read_bytes(),p.name)
        service.JOBS.pop(result['id'])
        self.assertEqual(service.job_state(result['id'])['result'],result['result'])
        self.assertEqual(original,{p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()})
        self.assertEqual(self.model.read_bytes(),baseline)

    def test_unsteady_saved_airflow_restoration_matches_original_final_plane(self):
        baseline=self.model.read_bytes()
        inputs=[dict(name=n,values=[x]) for n,x in [('GeomSet',-1),('ThinGeomSet',0),('RefFlag',1),('WingID',self.gid),('AlphaStart',4.),('AlphaNpts',1),('MachStart',.1),('MachNpts',1),('NCPU',1),('NumTimeSteps',4),('TimeStepSize',.02),('NumWakeNodes',8),('WakeNumIter',3),('UnsteadyType',self.v.STABILITY_P_ANALYSIS)]]
        try:
            source=self.wait_job(service.start_job(dict(name='VSPAEROSweep',revision=service.REVISION,inputs=inputs))['id'])
            folder=service.job_folder(source['id']);original={p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
            entries=[dict(name='XSlicePosVec',values=[]),dict(name='YSlicePosVec',values=[1.]),dict(name='ZSlicePosVec',values=[]),dict(name='QuadTreeBufferLevels',values=[1])]
            result=self.wait_job(service.start_job(dict(name='FlowPlaneSlicer',sourceRun=source['id'],revision=service.REVISION,inputs=entries))['id'])
            child=service.job_folder(result['id'])
            direct=self.path/'unsteady-direct';direct.mkdir()
            for p in child.iterdir():
                if p.suffix in ('.vspgeom','.vspaero','.vkey','.groups'):shutil.copy2(p,direct/p.name)
            with (direct/'native.log').open('w') as log:
                run=subprocess.run([str(distribution()/'vspaero'),'-omp','1','-pstab',str(direct/'aircraft')],cwd=direct,stdout=log,stderr=log,timeout=30)
            self.assertEqual(run.returncode,0)
            files=sorted(child.glob('*.case.*.quad.*.dat'));self.assertTrue(files)
            for p in files:self.assertEqual(p.read_bytes(),(direct/p.name).read_bytes())
            self.assertEqual(original,{p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()})
        except Exception:
            evidence=Path(__file__).resolve().parents[1]/'.workspace/evidence/flow-reader-unsteady-native-failure'
            shutil.copytree(self.path,evidence,dirs_exist_ok=True)
            self.assertEqual(self.model.read_bytes(),baseline)
            raise
        self.assertEqual(self.model.read_bytes(),baseline)

    def test_pitch_saved_airflow_restoration_matches_original_final_plane(self):
        baseline=self.model.read_bytes()
        inputs=[dict(name=n,values=[x]) for n,x in [('GeomSet',-1),('ThinGeomSet',0),('RefFlag',1),('WingID',self.gid),('AlphaStart',4.),('AlphaNpts',1),('MachStart',.1),('MachNpts',1),('NCPU',1),('NumTimeSteps',4),('TimeStepSize',.02),('NumWakeNodes',8),('WakeNumIter',3),('UnsteadyType',self.v.STABILITY_Q_ANALYSIS)]]
        try:
            source=self.wait_job(service.start_job(dict(name='VSPAEROSweep',revision=service.REVISION,inputs=inputs))['id'])
            folder=service.job_folder(source['id']);original={p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
            entries=[dict(name='XSlicePosVec',values=[]),dict(name='YSlicePosVec',values=[1.]),dict(name='ZSlicePosVec',values=[]),dict(name='QuadTreeBufferLevels',values=[1])]
            result=self.wait_job(service.start_job(dict(name='FlowPlaneSlicer',sourceRun=source['id'],revision=service.REVISION,inputs=entries))['id'])
            child=service.job_folder(result['id'])
            direct=self.path/'pitch-direct';direct.mkdir()
            for p in child.iterdir():
                if p.suffix in ('.vspgeom','.vspaero','.vkey','.groups'):shutil.copy2(p,direct/p.name)
            with (direct/'native.log').open('w') as log:
                run=subprocess.run([str(distribution()/'vspaero'),'-omp','1','-qstab',str(direct/'aircraft')],cwd=direct,stdout=log,stderr=log,timeout=30)
            self.assertEqual(run.returncode,0)
            planes=result['result']['flowPlanes'];self.assertGreater(len(planes),1)
            self.assertEqual(sorted(p['solutionRecord'] for p in planes),list(range(1,len(planes)+1)))
            final=max(planes,key=lambda p:p['solutionRecord'])
            self.assertEqual((child/final['file']).read_bytes(),(direct/'aircraft.case.1.quad.1.dat').read_bytes())
            self.assertEqual(original,{p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()})
        except Exception:
            evidence=Path(__file__).resolve().parents[1]/'.workspace/evidence/flow-reader-pitch-native-failure'
            shutil.copytree(self.path,evidence,dirs_exist_ok=True)
            self.assertEqual(self.model.read_bytes(),baseline)
            raise
        self.assertEqual(self.model.read_bytes(),baseline)

    def test_saved_airflow_study_preserves_case_sources_and_original_sample_comparisons(self):
        baseline=self.model.read_bytes()
        flight=dict(name='VSPAEROSweep',inputs=[dict(name=n,values=[x]) for n,x in [('GeomSet',-1),('ThinGeomSet',0),('AlphaStart',2.),('AlphaEnd',5.),('AlphaNpts',2),('NCPU',1),('Vinf',37.),('MachStart',.1),('MachEnd',.1)]])
        planes=dict(name='FlowPlaneSlicer',sourceStage=0,inputs=[dict(name='XSlicePosVec',values=[1.25]),dict(name='YSlicePosVec',values=[1.]),dict(name='ZSlicePosVec',values=[]),dict(name='QuadTreeBufferLevels',values=[1])])
        plan=self.save([dict(kind='input',stage=1,name='YSlicePosVec',valueMode='array',values=[[1.],[1.,3.]])],stages=[flight,planes])
        frozen=(studies.study_folder(plan['id'])/'aircraft.vsp3').read_bytes()
        batch=studies.launch(plan['id']);batch=self.wait(plan['id'],batch['id'])
        self.assertEqual(batch['status'],'complete',batch)
        for case in batch['cases']:
            source,child=[service.job_state(stage['job']) for stage in case['stages']]
            self.assertEqual(child['sourceRun'],source['id'])
            self.assertEqual((service.job_folder(source['id'])/'aircraft.adb').read_bytes(),(service.job_folder(child['id'])/'aircraft.adb').read_bytes())
            folder=service.job_folder(child['id']);direct=self.path/('native-study-'+str(case['index']));direct.mkdir()
            for p in folder.iterdir():
                if p.suffix in ('.vspgeom','.vspaero','.vkey'):shutil.copy2(p,direct/p.name)
            with (direct/'native.log').open('w') as log:
                run=subprocess.run([str(distribution()/'vspaero'),'-omp','1',str(direct/'aircraft')],cwd=direct,stdout=log,stderr=log,timeout=30)
            self.assertEqual(run.returncode,0)
            files=sorted(folder.glob('*.case.*.quad.*.dat'));self.assertEqual(len(files),2*(1+len(case['values'][0])))
            for p in files:self.assertEqual(p.read_bytes(),(direct/p.name).read_bytes())
        fields=[f for f in studies.result_fields(plan['id'],batch['id']) if f.get('kind')=='flowPlane']
        self.assertEqual(len(fields),6*7)
        for field in fields:
            compared=studies.comparison(plan['id'],batch['id'],field['key'])
            for row,case in zip(compared['rows'],batch['cases']):
                self.assertEqual(row['effective'],case['values'])
                folder=service.job_folder(row['job']);path=folder/field['file']
                if not path.exists():
                    self.assertIsNone(row['values']);self.assertIsNone(row['sampleLocations']);continue
                mesh=service.aero_preview(row['job'],path.name);prop=field['property']
                expected=[p['XYZ'.index(prop)] for p in mesh['nodes']] if prop in 'XYZ' else next(e['nodeValues'] for e in mesh['fields'] if e['name']==prop)
                self.assertEqual(row['values'],expected)
                self.assertEqual(row['sampleLocations'],mesh['nodes'])
            csv_rows=list(csv.DictReader(io.StringIO(studies.csv_comparison(plan['id'],batch['id'],field['key']).decode())))
            self.assertEqual(len(csv_rows),sum(len(row['values']) if row['values'] is not None else 1 for row in compared['rows']))
            expected_csv=[value for row in compared['rows'] for value in (row['values'] if row['values'] is not None else [None])]
            self.assertEqual([float(row['value']) if row['value'] else None for row in csv_rows],expected_csv)
            expected_locations=[point for row in compared['rows'] for point in (row['sampleLocations'] if row['sampleLocations'] is not None else [[None,None,None]])]
            actual_locations=[[float(row[key]) if row[key] else None for key in ('native_node_X','native_node_Y','native_node_Z')] for row in csv_rows]
            self.assertEqual(actual_locations,expected_locations)
        all_fields=studies.result_fields(plan['id'],batch['id'])
        cold_reference=studies.comparison(plan['id'],batch['id'],fields[-1]['key'])
        service.JOBS={}
        self.assertEqual(studies.batch_state(plan['id'],batch['id'])['status'],'complete')
        self.assertEqual(studies.result_fields(plan['id'],batch['id']),all_fields)
        self.assertEqual(studies.comparison(plan['id'],batch['id'],fields[-1]['key']),cold_reference)
        self.assertEqual(self.model.read_bytes(),baseline)
        self.assertEqual((studies.study_folder(plan['id'])/'aircraft.vsp3').read_bytes(),frozen)

    def test_saved_solution_interrogation_matches_original_files_and_preserves_history(self):
        baseline=self.model.read_bytes()
        installed_hash=hashlib.sha256((distribution()/'vspaero').read_bytes()).hexdigest()
        source=self.wait_job(service.start_job(dict(name='VSPAEROSweep',revision=service.REVISION,inputs=[dict(name=n,values=[x]) for n,x in [('GeomSet',-1),('ThinGeomSet',0),('AlphaStart',2.),('AlphaEnd',5.),('AlphaNpts',2),('NCPU',1),('Vinf',37.),('MachStart',.1),('MachEnd',.1)]]))['id'])
        folder=service.job_folder(source['id']);before={p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
        entries=[dict(name='XSlicePosVec',values=[1.25]),dict(name='YSlicePosVec',values=[1.,3.]),dict(name='ZSlicePosVec',values=[]),dict(name='QuadTreeBufferLevels',values=[1])]
        spec=service.schema('FlowPlaneSlicer');self.assertIn(source['id'],[j['id'] for j in spec['savedSolutions']])
        try:
            result=self.wait_job(service.start_job(dict(name='FlowPlaneSlicer',sourceRun=source['id'],revision=service.REVISION,inputs=entries))['id'])
        except AssertionError:
            evidence=Path(__file__).resolve().parents[1]/'.workspace/evidence/flow-interrogate-native-failure'
            shutil.copytree(self.path,evidence,dirs_exist_ok=True)
            self.assertEqual(self.model.read_bytes(),baseline)
            self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()})
            raise
        self.assertEqual(result['sourceRun'],source['id']);self.assertEqual(len(result['result']['flowPlanes']),6)
        provenance=result['result']['readerProvenance']
        self.assertEqual(provenance['readerOperation'],'saved-database-interrogation')
        self.assertEqual(provenance['inputDatabaseSha256'],hashlib.sha256(before['aircraft.adb']).hexdigest())
        self.assertEqual(provenance['outputDatabaseSha256'],provenance['inputDatabaseSha256'])
        self.assertEqual(provenance['engineSourceTag'],'OpenVSP_3.52.2')
        self.assertEqual(provenance['readerMode'],'serial')
        for key in ('readerSourceSha256','readerExecutableSha256','readerPatchSha256'):
            self.assertRegex(provenance[key],r'^[0-9a-f]{64}$')
        child=service.job_folder(result['id']);self.assertEqual(self.model.read_bytes(),baseline)
        self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()})
        self.assertEqual((child/'aircraft.adb').read_bytes(),(folder/'aircraft.adb').read_bytes())
        fields={e['name']:e['value'] for e in result['result']['solverSetup']['fields']};self.assertEqual(fields['Vinf'],'37')
        direct=self.path/'direct-flow';direct.mkdir()
        for p in child.iterdir():
            if p.is_file() and (p.suffix in ('.adb','.vspaero','.vspgeom','.groups','.vkey') or p.name.endswith('.adb.cases')):shutil.copy2(p,direct/p.name)
        with (direct/'solver.log').open('w') as log:
            process=subprocess.run([str(distribution()/'vspaero'),'-omp','1',str(direct/'aircraft')],cwd=direct,stdout=log,stderr=log,timeout=90)
        self.assertEqual(process.returncode,0)
        files=sorted(child.glob('*.case.*.quad.*.dat'));self.assertEqual(len(files),6)
        for p in files:
            self.assertEqual(p.read_bytes(),(direct/p.name).read_bytes())
            self.assertTrue(service.aero_preview(result['id'],p.name)['nodes'])
        service.JOBS.pop(result['id']);reopened=service.job_state(result['id'])
        self.assertEqual(reopened['result'],result['result']);self.assertEqual(reopened['analysisSetup'],result['analysisSetup'])
        self.assertEqual(self.model.read_bytes(),baseline)
        self.assertEqual(installed_hash,hashlib.sha256((distribution()/'vspaero').read_bytes()).hexdigest())

    def test_missing_source_and_invalid_planes_preserve_aircraft(self):
        before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'Choose a completed saved'):
            service.start_job(dict(name='FlowPlaneSlicer',revision=service.REVISION,inputs=[]))
        for entries in [[dict(name=a+'SlicePosVec',values=[]) for a in 'XYZ'],[dict(name='YSlicePosVec',values=[float('inf')])],[dict(name='QuadTreeBufferLevels',values=[.5])]]:
            with self.assertRaises(ValueError):native_flow_slices.inputs(self.v,dict(inputs=entries))
        self.assertEqual(before,self.model.read_bytes());self.assertEqual(service.list_jobs(),[])


if __name__=='__main__':unittest.main()
