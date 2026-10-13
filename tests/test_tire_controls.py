"""Tire drivers and inspection surfaces compared with independent public SDK calls."""
import itertools
import sys
import unittest
import test_native
import test_gear_controls
from vsp_runtime import load
from native_worker import parameter


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class NativeTireControls(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    assert_native_geometry=test_gear_controls.NativeGearControls.assert_native_geometry

    def fixture(self,mechanism=True):
        v=self.v;self.gear=v.AddGeom('GEAR',self.gid);self.bogie=v.CreateAndAddBogie(self.gear)
        for n in ('AutoPlaneFlag','ShowNominalGroundPlane'):v.SetParmValUpdate(self.gear,n,'GroundPlane',0)
        for n,x in [('X_Rel_Location',3),('Y_Rel_Location',4),('Z_Rel_Location',2),('X_Rel_Rotation',11),('Y_Rel_Rotation',17),('Z_Rel_Rotation',23)]:v.SetParmValUpdate(self.gear,n,'XForm',x)
        self.ids={v.GetParmName(p):p for p in v.FindContainerParmIDs(self.bogie)}
        values=[('NumAcross',2),('NumTandem',2),('Symmetrical',1),('YContactPt',2),('TravelX',.2),('TravelY',.3),('TravelZ',1),('TravelCompressed',.4),('TravelExtended',.2),('StowZRelLoc',3),('StowYRelRot',70)]
        if mechanism:values += [('RetMode',v.GEAR_MECHANISM),('MechZRelLoc',2),('Mech_RetAngle',75),('MechKneePos',.4),('MechKneeAngle',20)]
        for n,x in values:v.SetParmValUpdate(self.ids[n],x)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def change(self,path,name,value):
        state,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids[name],value=value),path)
        self.v.SetParmValUpdate(self.ids[name],value);self.v.Update();self.assert_native_geometry(state)
        return state,path

    def sample(self,gid):
        v=self.v;result=[]
        for i in range(v.GetTotalNumSurfs(gid)):
            u,w=v.GetUWTess01(gid,i%max(1,v.GetNumMainSurfs(gid)))
            points=v.CompVecPnt01(gid,i,[x for x in u for _ in w],[y for _ in u for y in w])
            result.append(dict(index=i,rows=len(u),cols=len(w),points=[[p.x(),p.y(),p.z()] for p in points]))
        return result

    def direct_inspection(self,settings):
        # Independent native API setup. No Studio inspection helper is used.
        v=self.v;a=v.AddGeom('AUXILIARY',self.gear)
        v.SetParmValUpdate(a,'AuxiliaryGeomType','Design',v.AUX_GEOM_SINGLE_GEAR)
        v.SetAuxiliaryGeomContactPtID(a,0,self.bogie)
        for name,key in [('ContactPt1_Isymm','mirror'),('ContactPt1_ClearanceMode','clearance'),('ContactPt1_SuspensionMode','suspension'),('ContactPt1_GearMode','configuration'),('ContactPt1_KRetract','fraction'),('BogieTheta','pitch')]:v.SetParmValUpdate(a,name,'Design',settings[key])
        v.Update();v.SetAuxiliaryGeomContactPtID(a,0,self.bogie);v.Update()
        return a

    def settings(self):
        v=self.v
        return dict(clearance=v.TIRE_GROWTH_CLEARANCE,suspension=v.GEAR_SUSPENSION_COMPRESSED,mirror=1,configuration=v.GEAR_CONFIGURATION_INTERMEDIATE,fraction=.4,pitch=11)

    def test_rim_drivers_and_followers_match_native(self):
        self.fixture();v=self.v;path=self.model
        for prefix in ('Drim','Wrim'):
            values=[6,.5,.5] if prefix=='Drim' else [3,.25,.5]
            for (mode,suffix),value in zip([(v.TIRE_DIM_IN,'In'),(v.TIRE_DIM_MODEL,'Model'),(v.TIRE_DIM_FRAC,'Frac')],values):
                with self.subTest(prefix=prefix,mode=mode):
                    state,path=self.change(path,prefix+'Mode',mode);state,path=self.change(path,prefix+suffix,value)
                    fields={p['name']:p for p in state['tools']['gears'][0]['bogies'][0]['params']}
                    self.assertFalse(fields[prefix+suffix].get('displayReadOnly',False))
                    before=path.read_bytes()
                    for other in ('In','Model','Frac'):
                        if other==suffix:continue
                        self.assertTrue(fields[prefix+other]['displayReadOnly'])
                        with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='parameter',id=self.ids[prefix+other],value=1),path)
                    self.assertEqual(path.read_bytes(),before)
        state,_=self.worker(dict(action='state'),path);self.assert_native_geometry(state)

    def test_shoulder_native_model_mode_uses_fraction_and_study_locks(self):
        self.fixture();v=self.v;path=self.model
        for prefix in ('Ws','Hs'):
            for mode in (v.TIRE_DIM_IN,v.TIRE_DIM_MODEL,v.TIRE_DIM_FRAC):
                with self.subTest(prefix=prefix,mode=mode):
                    state,path=self.change(path,prefix+'Mode',mode)
                    suffix='In' if mode==v.TIRE_DIM_IN else 'Frac'
                    state,path=self.change(path,prefix+suffix,1.4 if suffix=='In' else .6)
                    fields={p['name']:p for p in state['tools']['gears'][0]['bogies'][0]['params']}
                    self.assertFalse(fields[prefix+suffix].get('displayReadOnly',False))
                    for other in ('In','Model','Frac'):
                        if other!=suffix:
                            self.assertTrue(fields[prefix+other]['displayReadOnly'])
                            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='parameter',id=self.ids[prefix+other],value=.9),path)
                    if mode==v.TIRE_DIM_MODEL:
                        before=v.GetParmVal(self.ids[prefix+'Model'])
                        v.SetParmValUpdate(self.ids[prefix+'Model'],before+1)
                        self.assertEqual(v.GetParmVal(self.ids[prefix+'Model']),before)
                        self.assertIn('native uses fraction',fields[prefix+'Mode']['choices'][1]['label'])
        import native_study_worker
        fields={p['id']:p for p in native_study_worker.schema(v,parameter)['parameters']}
        for prefix in ('Ws','Hs'):
            self.assertTrue(fields[self.ids[prefix+'Frac']].get('editable',True));self.assertFalse(fields[self.ids[prefix+'Model']]['editable'])
        state,_=self.worker(dict(action='state'),path);self.assert_native_geometry(state)

    def test_suspension_steering_and_pitch_values_survive_reopen(self):
        self.fixture();path=self.model
        for n,x in [('TravelX',.4),('TravelY',-.2),('TravelZ',.8),('TravelCompressed',.7),('TravelExtended',.5),('BogieThetaMin',-30),('BogieThetaMax',35),('SteeringAngle',25)]:state,path=self.change(path,n,x)
        state,_=self.worker(dict(action='state'),path);self.assert_native_geometry(state)

    def test_all_inspection_positions_shapes_sides_match_native_without_writes(self):
        self.fixture();v=self.v;before=self.model.read_bytes();variants=[]
        for clearance,suspension,mirror,configuration in itertools.product([v.TIRE_NOMINAL_CLEARANCE,v.TIRE_GROWTH_CLEARANCE,v.TIRE_CLEARANCE],[v.GEAR_SUSPENSION_NOMINAL,v.GEAR_SUSPENSION_COMPRESSED,v.GEAR_SUSPENSION_EXTENDED],[0,1],[v.GEAR_CONFIGURATION_DOWN,v.GEAR_CONFIGURATION_UP,v.GEAR_CONFIGURATION_INTERMEDIATE]):
            settings=dict(clearance=clearance,suspension=suspension,mirror=mirror,configuration=configuration,fraction=.4,pitch=11)
            with self.subTest(**settings):
                data,path=self.worker(dict(action='query',operation='gear-tire-preview',geom=self.gear,bogie=self.bogie,**settings))
                a=self.direct_inspection(settings)
                self.assertEqual(data['component']['surfaces'],self.sample(a));self.assertEqual(data['settings'],settings)
                self.assertEqual(data['geom'],self.gear);self.assertEqual(data['bogie'],self.bogie)
                self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
                self.assertEqual(data['warnings'],[]);self.assertEqual(data['component']['mainSurfaceCount'],v.GetNumMainSurfs(a))
                variants.append(data['component']['surfaces'][0]['points']);v.DeleteGeom(a);v.Update()
        self.assertEqual(len(variants),54)
        # Native TireToBogie ignores suspension/pitch during retraction.
        # All 54 settings above must match, including their repeated poses.
        self.assertNotEqual(variants[0],variants[6]);self.assertEqual(variants[1],variants[7]);self.assertEqual(variants[2],variants[8])

    def test_stowed_pose_and_invalid_selection_recovery(self):
        self.fixture(mechanism=False);v=self.v;settings=self.settings();settings['configuration']=v.GEAR_CONFIGURATION_UP
        data,path=self.worker(dict(action='query',operation='gear-tire-preview',geom=self.gear,bogie=self.bogie,**settings));a=self.direct_inspection(settings)
        self.assertEqual(data['component']['surfaces'],self.sample(a));v.DeleteGeom(a);v.Update()
        foreign=v.AddGeom('GEAR');foreign_bogie=v.CreateAndAddBogie(foreign);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        before=self.model.read_bytes();invalid=[dict(configuration=v.GEAR_CONFIGURATION_INTERMEDIATE),dict(fraction=1.1),dict(pitch=181),dict(clearance=99),dict(suspension=99),dict(mirror=True),dict(fraction=True),dict(bogie='missing'),dict(bogie=foreign_bogie),dict(geom=self.gid)]
        for patch in invalid:
            with self.subTest(patch=patch),self.assertRaises(ValueError):self.worker({**dict(action='query',operation='gear-tire-preview',geom=self.gear,bogie=self.bogie,**settings),**patch})
            self.assertEqual(self.model.read_bytes(),before)
        v.SetParmValUpdate(self.ids['Symmetrical'],0);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        with self.assertRaisesRegex(ValueError,'mirroring'):self.worker(dict(action='query',operation='gear-tire-preview',geom=self.gear,bogie=self.bogie,**settings))

    def test_all_six_native_tire_families_and_clearance_profiles(self):
        self.fixture();v=self.v
        for tire in (v.TIRE_TRA,v.TIRE_FAIR_FLANGE,v.TIRE_FAIR_WHEEL,v.TIRE_BALLOON,v.TIRE_BALLOON_WHEEL,v.TIRE_BALLOON_FAIR_WHEEL):
            v.SetParmValUpdate(self.ids['TireMode'],tire);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
            for clearance in (v.TIRE_NOMINAL_CLEARANCE,v.TIRE_GROWTH_CLEARANCE,v.TIRE_CLEARANCE):
                settings=self.settings();settings.update(clearance=clearance,configuration=v.GEAR_CONFIGURATION_DOWN,suspension=v.GEAR_SUSPENSION_EXTENDED)
                with self.subTest(tire=tire,clearance=clearance):
                    data,path=self.worker(dict(action='query',operation='gear-tire-preview',geom=self.gear,bogie=self.bogie,**settings));a=self.direct_inspection(settings)
                    self.assertEqual(data['component']['surfaces'],self.sample(a));self.assertEqual(path.read_bytes(),before)
                    v.DeleteGeom(a);v.Update()

    def test_saved_inspection_is_native_auxiliary_with_exact_cold_surfaces(self):
        self.fixture();v=self.v;settings=self.settings()
        state,path=self.worker(dict(action='mutate',operation='gear-inspection-create',geom=self.gear,bogie=self.bogie,**settings))
        created=[c for c in state['components'] if c['type'].upper()=='AUXILIARY'];self.assertEqual(len(created),1);c=created[0]
        a=self.direct_inspection(settings);self.assertEqual(c['surfaces'],self.sample(a))
        expected={(v.GetParmGroupName(p),v.GetParmName(p)):v.GetParmVal(p) for p in v.GetGeomParmIDs(a)}
        actual={(p['rawGroup'],p['name']):p['value'] for p in c['params']};self.assertEqual(actual,expected)
        aux=next(x for x in state['tools']['auxiliary'] if x['id']==c['id']);self.assertEqual(aux['parent'],self.gear);self.assertEqual(aux['contacts'][0],self.bogie)
        reopened,_=self.worker(dict(action='state'),path);cold=next(x for x in reopened['components'] if x['id']==c['id'])
        self.assertEqual(c['name'],'Tire and suspension inspection');self.assertEqual(cold['name'],c['name'])
        self.assertEqual(cold['surfaces'],c['surfaces']);self.assertEqual({p['id']:p['value'] for p in cold['params']},{p['id']:p['value'] for p in c['params']})

    def test_native_undefined_tire_shape_cannot_be_inspected_or_saved(self):
        import math
        self.fixture();v=self.v
        v.SetParmValUpdate(self.ids['DrimFrac'],.6);v.SetParmValUpdate(self.ids['WrimFrac'],1);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        settings=self.settings();settings.update(clearance=v.TIRE_NOMINAL_CLEARANCE,configuration=v.GEAR_CONFIGURATION_DOWN)
        a=self.direct_inspection(settings);samples=self.sample(a)
        self.assertTrue(any(not math.isfinite(x) for s in samples for p in s['points'] for x in p));v.DeleteGeom(a);v.Update()
        before=self.model.read_bytes()
        state,path=self.worker(dict(action='state'));self.assertTrue(any('contains undefined points' in w for w in state['warnings']))
        self.assertEqual(path.read_bytes(),before)
        for action,operation in [('query','gear-tire-preview'),('mutate','gear-inspection-create')]:
            with self.assertRaisesRegex(ValueError,'undefined tire inspection'):self.worker(dict(action=action,operation=operation,geom=self.gear,bogie=self.bogie,**settings))
            self.assertEqual(self.model.read_bytes(),before)
