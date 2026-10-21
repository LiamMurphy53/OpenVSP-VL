"""A rebased native study preserves the geometry each explicit set selects."""
import json,unittest
import test_studies
import native_service as service
import native_studies as studies
from native_study_sets import rebind

class StudySets(unittest.TestCase):
    setUpClass=classmethod(test_studies.NativeStudies.setUpClass.__func__)
    setUp=test_studies.NativeStudies.setUp
    tearDown=test_studies.NativeStudies.tearDown
    save=test_studies.NativeStudies.save
    wait=test_studies.NativeStudies.wait

    def test_review_maps_stage_and_sweep_sets_preserving_frozen_runs(self):
        v=self.v;p=v.AddGeom('POD');v.SetGeomName(self.gid,'Wing');v.SetGeomName(p,'Payload')
        for i,members in [(3,[self.gid]),(4,[p])]:
            v.SetSetName(i,'Same')
            for g in v.FindGeoms():v.SetSetFlag(g,i,g in members)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        stages=[dict(name='CompGeom',inputs=[dict(name='Set',index=0,values=[3])])]
        axes=[dict(kind='input',stage=0,name='Set',index=0,valueMode='element',values=[3,4])]
        plan=self.save(axes,stages);folder=studies.study_folder(plan['id']);frozen=(folder/'aircraft.vsp3').read_bytes();definition=(folder/'definition.json').read_bytes()
        order=list(range(3,v.GetNumSets()));order[0],order[1]=order[1],order[0]
        service.mutation(dict(operation='set-reorder',order=order,revision=service.REVISION))
        with self.assertRaisesRegex(ValueError,'Review the current aircraft'):
            self.save(axes,stages,id=plan['id'],definitionVersion=plan['version'],baseline='current')
        review=studies.rebind_current_aircraft(dict(id=plan['id'],definitionVersion=plan['version'],revision=service.REVISION))
        self.assertEqual(review['stages'][0]['inputs'][0]['values'],[4]);self.assertEqual(review['axes'][0]['values'],[4,3])
        self.assertEqual((folder/'aircraft.vsp3').read_bytes(),frozen);self.assertEqual((folder/'definition.json').read_bytes(),definition)
        original=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(original['status'],'complete')
        updated=self.save(review['axes'],review['stages'],id=plan['id'],definitionVersion=plan['version'],baseline='current',setIdentities=review['setIdentities'])
        result=self.wait(plan['id'],studies.launch(plan['id'])['id']);self.assertEqual(result['status'],'complete')
        for batch in [original,result]:
            names=[]
            for case in batch['cases']:
                response=service.job_state(case['stages'][0]['job'])['result'];entries=response['results'][0]['entries'];names.append(next(e['values'] for e in entries if e['name']=='Comp_Name'))
            self.assertEqual(names,[['Wing'],['Payload']])
        self.assertEqual(updated['axes'][0]['values'],[4,3])

    def test_mapping_supports_geometry_arrays_and_parameter_selectors(self):
        old=['builtin:0','builtin:1','builtin:2','wing','payload'];new=[*old[:3],'payload','wing']
        stages=[dict(geometryInputs=[dict(name='ThinGeomSet',values=[3])])]
        axes=[dict(kind='geometryInput',name='ThinGeomSet',values=[[3,4],[-1,0]]),dict(kind='parameter',id='selector',values=[3,4])]
        mapped,mapped_axes,matches=rebind(old,new,stages,axes,{'selector'})
        self.assertEqual(mapped[0]['geometryInputs'][0]['values'],[4]);self.assertEqual(mapped_axes[0]['values'],[[4,3],[-1,0]]);self.assertEqual(mapped_axes[1]['values'],[4,3]);self.assertEqual(stages[0]['geometryInputs'][0]['values'],[3])
        with self.assertRaisesRegex(ValueError,'removed or replaced'):rebind(old,[*old[:3],'replacement','wing'],stages,axes,{'selector'})
        with self.assertRaisesRegex(ValueError,'identity is unavailable'):rebind(None,new,stages,axes,{'selector'})
