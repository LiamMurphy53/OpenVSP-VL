"""Retraction references and geometry replayed through native XML and public SDK."""
import sys,unittest,xml.etree.ElementTree as ET
import test_native
import test_gear_controls
from vsp_runtime import load
from native_worker import parameter
import native_gear_retraction as retraction

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class NativeGearRetraction(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    assert_native_geometry=test_gear_controls.NativeGearControls.assert_native_geometry

    def fixture(self):
        v=self.v;self.gear=v.AddGeom('GEAR');self.bogie=v.CreateAndAddBogie(self.gear)
        for n in ('AutoPlaneFlag','ShowNominalGroundPlane'):v.SetParmValUpdate(self.gear,n,'GroundPlane',0)
        v.SetParmValUpdate(self.gear,'GearConfigMode','Gear',v.GEAR_CONFIGURATION_UP_AND_DOWN)
        v.Update();self.ids=retraction.names(v,self.bogie);v.WriteVSPFile(str(self.model),v.SET_ALL)

    def direct_parent(self,side,parent):
        v=self.v;p=self.path/'independent-reference.vsp3';v.WriteVSPFile(str(p),v.SET_ALL);tree=ET.parse(p)
        nodes=[n for gear in tree.findall('.//Gear') for n in list(gear) if n.findtext('ParmContainer/ID')==self.bogie];self.assertEqual(len(nodes),1)
        key='StowParentID' if side=='stow' else 'MechParentID';nodes[0].find('Bogie/'+key).text=parent
        tree.write(p,encoding='utf-8',xml_declaration=True)
        # 3.52.2's GearGeom destructor does not release its Bogie containers.
        # Explicit public cleanup prevents ID collisions on same-process reload;
        # Studio's transactional workers already start in fresh processes.
        for g in v.FindGeoms():
            if v.GetGeomTypeName(g).upper()=='GEAR':v.DelAllBogies(g)
        v.ClearVSPModel();v.ReadVSPFile(str(p));v.Update()

    def change(self,path,name,value):
        state,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids[name],value=value),path)
        self.v.SetParmValUpdate(self.ids[name],value);self.v.Update();self.assert_native_geometry(state)
        return state,path

    def evaluate_direct_gear(self):
        # Independent public SDK evaluation after every referenced component
        # exists. Decode can evaluate the gear before a forward joint reference;
        # dirty/restore an input to request its native surface evaluation.
        pid=self.ids['StowYRelLoc'];value=self.v.GetParmVal(pid)
        self.v.SetParmValUpdate(pid,value+1);self.v.SetParmValUpdate(pid,value);self.v.Update()

    def test_stowed_surface_references_and_coordinates_match_native(self):
        self.fixture();v=self.v;path=self.model
        state,path=self.worker(dict(action='mutate',operation='bogie-attachment',geom=self.gear,id=self.bogie,side='stow',parent=self.gid),path)
        self.direct_parent('stow',self.gid);self.assert_native_geometry(state)
        meta=next(g for g in state['tools']['gears'] if g['id']==self.gear)['bogies'][0]['retraction'];self.assertEqual(meta['stowParent'],self.gid)
        for name,x in [('StowTransAttachFlag',v.ATTACH_TRANS_UV),('StowRotAttachFlag',v.ATTACH_ROT_COMP),('StowULoc',.4),('StowWLoc',.25),('StowXRelLoc',1),('StowZRelLoc',2),('StowYRelRot',35),('StowU01',0),('StowU0NLoc',.6),('StowTransAttachFlag',v.ATTACH_TRANS_EtaMN),('StowEtaLoc',.3)]:state,path=self.change(path,name,x)
        self.assertTrue(retraction.reasons(v,self.bogie)[self.ids['Mech_RetAngle']])
        before=path.read_bytes()
        with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='parameter',id=self.ids['Mech_RetAngle'],value=40),path)
        self.assertEqual(path.read_bytes(),before)
        reopened,_=self.worker(dict(action='state'),path);self.assert_native_geometry(reopened)

    def test_mechanism_pose_intermediate_and_back_calculation_match_native(self):
        self.fixture();v=self.v;path=self.model
        for name,x in [('StowYRelRot',90),('StowZRelLoc',2),('RetMode',v.GEAR_MECHANISM)]:state,path=self.change(path,name,x)
        state,path=self.worker(dict(action='mutate',operation='bogie-attachment',geom=self.gear,id=self.bogie,side='mechanism',parent=self.gid),path)
        self.direct_parent('mechanism',self.gid);self.assert_native_geometry(state)
        for name,x in [('MechTransAttachFlag',v.ATTACH_TRANS_COMP),('MechZRelLoc',2),('Mech_X_Axis',0),('Mech_Y_Axis',1),('Mech_Z_Axis',0),('Mech_RetAngle',75),('MechKneePos',.4),('MechKneeDownAngle',150),('MechKneeAngle',20),('MechKneeElevationAngle',10),('Mech_TwistAngle',8),('m_MechRollAngle',7),('Mech_BogieAngle',5),('Mech_StrutDL',.2),('GearConfigMode',v.GEAR_CONFIGURATION_INTERMEDIATE),('MechKRetract',.4)]:
            if name=='GearConfigMode':self.ids[name]=v.FindParm(self.gear,name,'Gear')
            state,path=self.change(path,name,x)
        fields=next(g for g in state['tools']['gears'] if g['id']==self.gear)['bogies'][0]['params'];self.assertTrue(next(p for p in fields if p['name']=='StowXRelLoc')['displayReadOnly'])
        reopened,_=self.worker(dict(action='state'),path);self.assert_native_geometry(reopened)
        objects=next(g for g in reopened['tools']['gears'] if g['id']==self.gear)['bogies'][0]['retraction']['objects'];self.assertTrue(any(o['nativeID'].endswith('MStrut') for o in objects))

    def test_cycle_parent_surface_and_delete_guards_are_atomic(self):
        self.fixture();v=self.v;child=v.AddGeom('POD',self.gear);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        before=self.model.read_bytes()
        for parent in (self.gear,child,'missing'):
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='bogie-attachment',geom=self.gear,id=self.bogie,side='stow',parent=parent))
            self.assertEqual(self.model.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='bogie-attachment',geom=self.gear,id=self.bogie,side='stow',parent=self.gid))
        before=path.read_bytes()
        for request in [dict(operation='delete',geom=self.gid),dict(operation='reparent',geom=self.gid,parent=self.gear),dict(operation='bogie-attachment',geom=self.gear,id=self.bogie,side='mechanism',parent=self.gid),dict(operation='parameter',id=self.ids['StowTransAttachFlag'],value=8)]:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',**request),path)
            self.assertEqual(path.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids['StowTransAttachFlag'],value=v.ATTACH_TRANS_UV),path)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'actual surface'):self.worker(dict(action='mutate',operation='parameter',id=self.ids['StowSurfIndx'],value=99),path)
        self.assertEqual(path.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='bogie-attachment',geom=self.gear,id=self.bogie,side='stow',parent=''),path)
        state,path=self.worker(dict(action='mutate',operation='delete',geom=self.gid),path);self.assertNotIn(self.gid,[c['id'] for c in state['components']])

    def test_joint_parent_and_named_study_guards(self):
        self.fixture();v=self.v;joint=v.AddGeom('HINGE');v.SetParmValUpdate(joint,'X_Rel_Location','XForm',2);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='bogie-attachment',geom=self.gear,id=self.bogie,side='stow',parent=joint))
        self.direct_parent('stow',joint);self.evaluate_direct_gear();self.assert_native_geometry(state)
        meta=next(g for g in state['tools']['gears'] if g['id']==self.gear)['bogies'][0]['retraction'];self.assertTrue(meta['stowJoint'])
        import native_study_worker
        schema=native_study_worker.schema(v,parameter);fields={p['id']:p for p in schema['parameters']};self.assertFalse(fields[self.ids['StowTransAttachFlag']]['editable']);self.assertFalse(fields[self.ids['Mech_RetAngle']]['editable'])
        self.assertEqual(fields[self.ids['StowAbsRelFlag']]['choices'][0]['label'],'Gear coordinates')

    def test_saved_forward_joint_reference_and_later_joint_edits(self):
        self.fixture();v=self.v;joint=v.AddGeom('HINGE');v.SetParmValUpdate(joint,'X_Rel_Location','XForm',2);v.Update()
        self.direct_parent('stow',joint);input_file=self.path/'independent-reference.vsp3';before=input_file.read_bytes()
        self.evaluate_direct_gear()
        state,path=self.worker(dict(action='state'),input_file);self.assert_native_geometry(state);self.assertEqual(input_file.read_bytes(),before)
        pid=v.FindParm(joint,'X_Rel_Location','XForm')
        state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=5),path)
        v.SetParmValUpdate(pid,5);self.evaluate_direct_gear();self.assert_native_geometry(state)
        self.assertEqual(v.GetParmVal(self.ids['StowXLoc']),5)
        reopened,_=self.worker(dict(action='state'),path);self.assert_native_geometry(reopened)

    def test_study_case_controllers_precede_mechanism_values(self):
        self.fixture();v=self.v
        config=v.FindParm(self.gear,'GearConfigMode','Gear')
        edits=[(self.ids['Mech_ZLoc'],2),(self.ids['MechKRetract'],.4),(self.ids['MechAbsRelFlag'],v.ABS),(config,v.GEAR_CONFIGURATION_INTERMEDIATE),(self.ids['RetMode'],v.GEAR_MECHANISM)]
        prepared,path=self.worker(dict(action='study-model',parameters=[dict(id=p,value=x) for p,x in edits]))
        for p,x in reversed(edits):v.SetParmValUpdate(p,x);v.Update()
        state,_=self.worker(dict(action='state'),path);self.assert_native_geometry(state)
        self.assertEqual([(p['id'],p['effective']) for p in prepared['parameters']],edits)

    def test_missing_saved_reference_can_be_reassigned(self):
        self.fixture();v=self.v;self.direct_parent('stow','XXXXXXXXXX')
        source=self.path/'independent-reference.vsp3';before=source.read_bytes()
        state,path=self.worker(dict(action='state'),source)
        meta=next(g for g in state['tools']['gears'] if g['id']==self.gear)['bogies'][0]['retraction']
        self.assertNotIn(meta['stowParent'],v.FindGeoms());self.assertTrue(meta['stowParent']);self.assertEqual(source.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='bogie-attachment',geom=self.gear,id=self.bogie,side='stow',parent=''),path)
        meta=next(g for g in state['tools']['gears'] if g['id']==self.gear)['bogies'][0]['retraction'];self.assertEqual(meta['stowParent'],'')
        reopened,_=self.worker(dict(action='state'),path);self.assert_native_geometry(reopened)
