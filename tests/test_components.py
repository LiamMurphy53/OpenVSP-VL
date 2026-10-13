"""Groups, hierarchy and set slots verified against the official OpenVSP API."""
import sys
import unittest
import uuid
import test_native
import native_components
import native_service as service
from vsp_runtime import load


def points(v,g):
    return [[p.x(),p.y(),p.z()] for s in range(v.GetTotalNumSurfs(g))
            for p in v.CompVecPnt01(g,s,[.17,.43,.76],[.23,.52,.81])]


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeComponents(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v
        self.child=v.AddGeom('POD',self.gid);self.follow=v.AddGeom('POD',self.gid);self.other=v.AddGeom('POD')
        for g in [self.child,self.follow]:
            v.SetParmValUpdate(v.FindParm(g,'Trans_Attach_Flag','Attach'),v.ATTACH_TRANS_COMP)
            v.SetParmValUpdate(v.FindParm(g,'Rots_Attach_Flag','Attach'),v.ATTACH_ROT_COMP)
            v.SetParmValUpdate(v.FindParm(g,'Abs_Or_Relitive_flag','XForm'),v.REL)
            v.SetParmValUpdate(v.FindParm(g,'X_Rel_Location','XForm'),2.)
            v.SetParmValUpdate(v.FindParm(g,'Y_Rel_Location','XForm'),3.)
        v.SetParmValUpdate(v.FindParm(self.other,'X_Location','XForm'),20.)
        v.SetSetFlag(self.gid,3,True);v.SetSetFlag(self.child,3,True)
        v.SetSetName(3,'Parent and attached child');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return [self.gid,self.child,self.follow,self.other]

    def assertPoints(self,a,b):
        self.assertEqual(len(a),len(b))
        for p,q in zip(a,b):
            for x,y in zip(p,q):self.assertAlmostEqual(x,y,places=10)

    def test_group_transforms_match_direct_native_surfaces_including_attached_nonmembers(self):
        v=self.v;geoms=self.fixture()
        for typ,flag in [('translate',None),('rotate',None),('scale',None),('combined',False),('combined',True)]:
            with self.subTest(type=typ,scaleTranslations=flag):
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
                before={g:points(v,g) for g in geoms}
                r=dict(action='mutate',operation='group-transform',set=3,type=typ)
                if typ=='translate':r['xyz']=[1.2,-3.4,.7];v.TranslateSet(3,v.vec3d(*r['xyz']))
                elif typ=='rotate':r['xyz']=[8.,-13.,27.];v.RotateSet(3,*r['xyz'])
                elif typ=='scale':r['value']=1.4;v.ScaleSet(3,r['value'])
                else:
                    r.update(xyz=[1.2,-3.4,.7],rotation=[8.,-13.,27.],value=1.4,scaleTranslations=flag)
                    v.TransformSet(3,v.vec3d(*r['xyz']),*r['rotation'],r['value'],flag)
                v.Update();expected={g:points(v,g) for g in geoms};box=list(v.GetBBoxSet(3))
                state,path=self.worker(r)
                v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
                for g in geoms:self.assertPoints(points(v,g),expected[g])
                self.assertPoints(points(v,self.other),before[self.other])
                # Native ScaleSet scales selected geometry only; translations
                # and rotations also propagate to this attached nonmember.
                if typ=='scale':self.assertPoints(points(v,self.follow),before[self.follow])
                else:self.assertNotEqual(points(v,self.follow),before[self.follow])
                bounds=state['tools']['sets'][3]['bounds']
                for x,y in zip(bounds['min']+bounds['size'],box[1:]):self.assertAlmostEqual(x,y,places=10)

    def test_native_root_and_child_reordering_preserves_subtrees_and_save_reopen(self):
        v=self.v;self.fixture();v.AddGeom('POD',self.gid);v.AddGeom('POD');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        path=self.model
        for g in [self.other,self.child]:
            for direction in ['REORDER_MOVE_TOP','REORDER_MOVE_DOWN','REORDER_MOVE_BOTTOM','REORDER_MOVE_UP']:
                with self.subTest(geom=g,direction=direction):
                    v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();v.ReorderGeom(g,getattr(v,direction));v.Update()
                    expected=list(v.FindGeoms());children=list(v.GetGeomChildren(self.gid))
                    state,path=self.worker(dict(action='mutate',operation='component-reorder',geom=g,direction=direction),path)
                    self.assertEqual([c['id'] for c in state['components']],expected)
                    v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
                    self.assertEqual(list(v.FindGeoms()),expected);self.assertEqual(list(v.GetGeomChildren(self.gid)),children)

    def test_set_create_and_copy_preserve_existing_slots_names_and_attributes(self):
        v=self.v;self.fixture();v.SetSetName(4,'Keep destination name')
        a=v.AddAttributeString(v.GetGeomSetCollection(1),'Set note','Destination metadata');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        count=v.GetNumSets();expected=list(v.GetGeomSetAtIndex(3))
        state,path=self.worker(dict(action='mutate',operation='set-create',name='Appended group',source=3))
        self.assertEqual(len(state['tools']['sets']),count+1);self.assertEqual(state['tools']['sets'][-1]['index'],count)
        self.assertEqual(state['tools']['sets'][-1]['name'],'Appended group');self.assertEqual(state['tools']['sets'][-1]['members'],expected)
        state,path=self.worker(dict(action='mutate',operation='set-copy',index=4,source=3),path)
        self.assertEqual(state['tools']['sets'][4]['members'],expected);self.assertEqual(state['tools']['sets'][4]['name'],'Keep destination name')
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.assertEqual(list(v.GetAttributeStringVal(a)),['Destination metadata'])
        state,path=self.worker(dict(action='mutate',operation='set-copy',index=4,source=0),path)
        self.assertEqual(state['tools']['sets'][4]['members'],list(v.FindGeoms()))
        state,path=self.worker(dict(action='mutate',operation='set-create',name='Empty group'),path)
        self.assertFalse(state['tools']['sets'][-1]['members']);self.assertEqual(state['tools']['setConfig']['count'],22)

    def test_set_count_reassigns_native_modes_settings_and_presets_and_persists(self):
        v=self.v;self.fixture();p=native_components.count_parameter(v);v.SetParmValUpdate(p,22)
        mode=v.CreateAndAddMode('Trailing set mode',24,23)
        global_id=v.FindParm(v.FindContainer('ParasiteDragSettings',0),'Set','ParasiteDrag');v.SetParmValUpdate(global_id,24)
        group=v.AddVarPresetGroup('Set preset');v.AddVarPresetParm(group,global_id);setting=v.AddVarPresetSetting(group,'Trailing set');v.SaveVarPresetParmVals(group,setting)
        retained=v.AddAttributeString(v.GetGeomSetCollection(0),'Keep','Retained metadata');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        refs=native_components.references(v);affected=[r for r in refs if r['value']>=23]
        self.assertEqual(len(affected),4)
        with self.assertRaisesRegex(ValueError,'replacement sets'):self.worker(dict(action='mutate',operation='set-count',count=20))
        replacements={r['key']:3 if 'group' not in r else 4 for r in affected}
        state,path=self.worker(dict(action='mutate',operation='set-count',count=20,replacements=replacements))
        self.assertEqual(len(state['tools']['sets']),23)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual(v.GetParmVal(p),20);self.assertEqual(v.GetParmVal(global_id),3)
        self.assertEqual(list(v.GetVarPresetParmVals(setting)),[4.]);self.assertEqual(list(v.GetAttributeStringVal(retained)),['Retained metadata'])
        self.assertEqual([v.GetParmVal(pid) for pid in v.FindContainerParmIDs(mode)],[3.,3.])
        self.assertTrue(all(r['value']<23 for r in state['tools']['setConfig']['references']))

    def test_invalid_set_edits_rejected_without_committing_and_generic_count_guarded(self):
        v=self.v;p=native_components.count_parameter(v);v.SetParmValUpdate(p,21);v.CreateAndAddMode('Guard',23,3);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        invalid=[dict(operation='set-count',count=x) for x in [19,998,20.5,True]]
        invalid += [dict(operation='set-copy',index=x,source=0) for x in [0,3.5,True,24]]
        invalid += [dict(operation='group-transform',set=3,type='translate',xyz=[1,2,3]),dict(operation='set-create',name=''),
                    dict(operation='parameter',id=p,value=20),dict(operation='set-count',count=20,replacements={'invented':3})]
        original=self.model.read_bytes()
        for r in invalid:
            with self.subTest(r=r),self.assertRaises(ValueError):self.worker(dict(r,action='mutate'))
            self.assertEqual(self.model.read_bytes(),original)
        v.SetSetFlag(self.gid,3,True);v.WriteVSPFile(str(self.model),v.SET_ALL)
        for r in [dict(type='scale',value=0),dict(type='rotate',xyz=[1,2]),dict(type='combined',xyz=[0,0,0],rotation=[0,0,0],value=1,scaleTranslations=1),dict(type='translate',xyz=[True,0,0])]:
            with self.subTest(r=r),self.assertRaises(ValueError):self.worker(dict(r,action='mutate',operation='group-transform',set=3))

    def test_transform_and_count_undo_redo_restore_native_geometry_and_set_attributes(self):
        self.fixture();v=self.v;p=native_components.count_parameter(v);v.SetParmValUpdate(p,21)
        a=v.AddAttributeString(v.GetGeomSetCollection(20),'Removed slot note','Recover me');v.SetSetFlag(self.gid,23,True);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        old=service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION,service.SESSION_WARNING
        try:
            service.WORK=self.path;service.MODEL=self.model;service.HISTORY=[];service.FUTURE=[];service.REVISION=uuid.uuid4().hex;service.SESSION_WARNING=None
            original=self.model.read_bytes()
            service.mutation(dict(operation='group-transform',set=3,type='combined',xyz=[2.,3.,4.],rotation=[0.,12.,0.],value=1.2,scaleTranslations=True,revision=service.REVISION));transformed=self.model.read_bytes()
            service.mutation(dict(operation='set-count',count=20,revision=service.REVISION));reduced=self.model.read_bytes()
            self.assertTrue(service.restore_session());service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),transformed)
            v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();self.assertEqual(list(v.GetAttributeStringVal(a)),['Recover me']);self.assertTrue(v.GetSetFlag(self.gid,23))
            service.undo(revision=service.REVISION);self.assertEqual(self.model.read_bytes(),original)
            service.undo(redo=True,revision=service.REVISION);service.undo(redo=True,revision=service.REVISION);self.assertEqual(self.model.read_bytes(),reduced)
        finally:service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION,service.SESSION_WARNING=old

    def test_preset_set_count_change_cannot_bypass_reference_guard(self):
        v=self.v;p=native_components.count_parameter(v);v.SetParmValUpdate(p,21)
        mode=v.CreateAndAddMode('Referenced slot',23,3);mp=v.FindParm(mode,'NormalSet','Sets')
        group=v.AddVarPresetGroup('Set count configuration');v.AddVarPresetParm(group,p)
        setting=v.AddVarPresetSetting(group,'Twenty sets');v.SaveVarPresetParmVals(group,setting);v.SetVarPresetParmVal(group,setting,p,20)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);original=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'removed set'):self.worker(dict(action='mutate',operation='preset-apply',group=group,setting=setting))
        self.assertEqual(self.model.read_bytes(),original)
        v.AddVarPresetParm(group,mp);v.SaveVarPresetParmVals(group,setting)
        v.SetVarPresetParmVal(group,setting,p,20);v.SetVarPresetParmVal(group,setting,mp,3)
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='preset-apply',group=group,setting=setting))
        self.assertEqual(len(state['tools']['sets']),23)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();self.assertEqual(v.GetParmVal(mp),3)

if __name__=='__main__':unittest.main()
