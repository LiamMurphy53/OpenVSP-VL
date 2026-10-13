"""Guided wheel drivers and auxiliary references against the installed SDK."""
import sys,unittest
import test_native
from vsp_runtime import load
import native_gear_controls as controls
from native_worker import parameter

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class NativeGearControls(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;g=v.AddGeom('GEAR');b=v.CreateAndAddBogie(g);v.SetGeomName(g,'Guided gear');v.Update()
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        self.gear=g;self.bogie=b
        self.ids={v.GetParmName(p):p for p in v.FindContainerParmIDs(b)}
        return g,b

    def assert_native_geometry(self,state,gid=None,generated_groups=()):
        v=self.v;gid=gid or self.gear;c=next(c for c in state['components'] if c['id']==gid)
        if generated_groups:
            # Native CCE DecodeXml creates a new internal FileXSecCurve with
            # new IDs. Compare every generated field by its unique native
            # group/name, while requiring all other original IDs to persist.
            actual={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in v.GetGeomParmIDs(gid)}
            expected={(p['rawGroup'],p['name']):p for p in c['params']}
            self.assertEqual(len(actual),len(c['params']));self.assertEqual(set(actual),set(expected))
            for key,p in expected.items():
                if p['rawGroup'] not in generated_groups:self.assertEqual(p['id'],actual[key],key)
                self.assertEqual(p['value'],v.GetParmVal(actual[key]),key)
        else:
            self.assertEqual(set(v.GetGeomParmIDs(gid)),{p['id'] for p in c['params']})
            for p in c['params']:self.assertEqual(p['value'],v.GetParmVal(p['id']),p['name'])
        for s in c['surfaces']:
            u,w=v.GetUWTess01(gid,s['index']%max(1,v.GetNumMainSurfs(gid)))
            self.assertEqual(s['points'],[[p.x(),p.y(),p.z()] for p in v.CompVecPnt01(gid,s['index'],[x for x in u for _ in w],[y for _ in u for y in w])])

    def test_tire_layout_and_unit_drivers_match_independent_native_updates(self):
        self.fixture();v=self.v;path=self.model
        changes=[('NumAcross',2),('NumTandem',2),('Symmetrical',1),('XContactPt',3),('YContactPt',2),
          ('DiameterMode',v.TIRE_DIM_MODEL),('DiameterModel',2),('WidthMode',v.TIRE_DIM_MODEL),('WidthModel',.6),
          ('SLRMode',v.TIRE_DIM_MODEL),('StaticRadiusModel',.85)]
        for name,value in changes:
            with self.subTest(name=name):
                state,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids[name],value=value),path)
                v.SetParmValUpdate(self.ids[name],value);v.Update();self.assert_native_geometry(state)
        fields={p['name']:p for p in next(g for g in state['tools']['gears'] if g['id']==self.gear)['bogies'][0]['params']}
        self.assertTrue(fields['DiameterIn']['displayReadOnly']);self.assertFalse(fields['DiameterModel'].get('displayReadOnly',False))
        self.assertEqual(v.GetParmVal(self.ids['DiameterIn']),24)
        before=path.read_bytes()
        for name,value in [('DiameterIn',30),('WidthIn',8),('NumAcross',2.5)]:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='parameter',id=self.ids[name],value=value),path)
        self.assertEqual(path.read_bytes(),before)

    def test_all_spacing_drivers_lock_followers_and_match_native(self):
        self.fixture();v=self.v;path=self.model
        modes=[v.BOGIE_CENTER_DIST,v.BOGIE_CENTER_DIST_FRAC,v.BOGIE_GAP,v.BOGIE_GAP_FRAC]
        for prefix,selector in [('Spacing','SpacingType'),('Pitch','PitchType')]:
            fields=[prefix,prefix+'Frac',prefix+'Gap',prefix+'GapFrac']
            for mode,field,value in zip(modes,fields,[2,2,.5,.4]):
                with self.subTest(selector=selector,mode=mode):
                    for name,x in [(selector,mode),(field,value)]:
                        state,path=self.worker(dict(action='mutate',operation='parameter',id=self.ids[name],value=x),path)
                        v.SetParmValUpdate(self.ids[name],x);v.Update();self.assert_native_geometry(state)
                    locked=controls.reasons(v,self.gear)[1]
                    self.assertNotIn(self.ids[field],locked)
                    for other in fields:
                        if other!=field:self.assertIn(self.ids[other],locked)

    def test_studies_use_named_native_options_and_protect_calculated_values(self):
        self.fixture();v=self.v
        import native_study_worker
        schema=native_study_worker.schema(v,parameter);fields={p['id']:p for p in schema['parameters']}
        self.assertFalse(fields[self.ids['DiameterModel']]['editable'])
        self.assertIn('Diameter driver',fields[self.ids['DiameterMode']]['label'])
        self.assertEqual(fields[self.ids['DiameterMode']]['choices'],[dict(value=v.TIRE_DIM_IN,label='Inches'),dict(value=v.TIRE_DIM_MODEL,label='Model units')])
        self.assertFalse(fields[self.ids['DGModel']]['editable'])

    def test_auxiliary_parent_contacts_and_deletion_recovery(self):
        self.fixture();v=self.v;g=self.gear;b=self.bogie;other=v.AddGeom('GEAR');foreign=v.CreateAndAddBogie(other)
        aux=v.AddGeom('AUXILIARY',g);v.SetGeomName(aux,'Clearance');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='auxiliary-setup',geom=aux,parent=g,type=v.AUX_GEOM_SINGLE_GEAR))
        state,path=self.worker(dict(action='mutate',operation='auxiliary-contact',geom=aux,index=0,bogie=b),path)
        a=next(a for a in state['tools']['auxiliary'] if a['id']==aux);self.assertEqual(a['bogies'],[b])
        before=path.read_bytes()
        invalid=[dict(operation='auxiliary-contact',geom=aux,index=1,bogie=foreign),dict(operation='bogie-delete',geom=g,id=b),
          dict(operation='auxiliary-setup',geom=aux,parent=self.gid,type=v.AUX_GEOM_SINGLE_GEAR),dict(operation='auxiliary-setup',geom=aux,parent=aux,type=v.AUX_GEOM_SINGLE_GEAR)]
        for r in invalid:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',**r),path)
            self.assertEqual(path.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='auxiliary-setup',geom=aux,parent=other,type=v.AUX_GEOM_SINGLE_GEAR),path)
        a=next(a for a in state['tools']['auxiliary'] if a['id']==aux);self.assertEqual(a['contacts'],[foreign]*3);self.assertEqual(a['bogies'],[foreign])
        state,path=self.worker(dict(action='mutate',operation='bogie-delete',geom=g,id=b),path)
        self.assertEqual(next(g for g in state['tools']['gears'] if g['id']==self.gear)['bogies'],[])

    def test_malformed_clearance_envelopes_are_rejected_without_native_loader(self):
        self.fixture();v=self.v;aux=v.AddGeom('AUXILIARY',self.gear);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        before=self.model.read_bytes()
        for text in ['invalid\nfile\n','0 0\n','0 0 0\n1 1 1\n','0 NaN\n1 1\n']:
            with self.assertRaisesRegex(ValueError,'clearance-envelope'):self.worker(dict(action='mutate',operation='auxiliary-cce',geom=aux,content=text))
            self.assertEqual(self.model.read_bytes(),before)

    def test_propeller_auxiliary_modes_accept_native_parent_type(self):
        v=self.v;prop=v.AddGeom('PROP');aux=v.AddGeom('AUXILIARY',prop);v.Update()
        v.WriteVSPFile(str(self.model),v.SET_ALL);path=self.model
        for mode in (v.AUX_GEOM_ROTOR_TIP_PATH,v.AUX_GEOM_THROWN_BLADE):
            state,path=self.worker(dict(action='mutate',operation='auxiliary-setup',geom=aux,parent=prop,type=mode),path)
            v.SetGeomParent(aux,prop);v.SetParmValUpdate(aux,'AuxiliaryGeomType','Design',mode);v.Update()
            v.SetAuxiliaryGeomContactPtID(aux,0,v.GetAuxiliaryGeomContactPtID(aux,0));v.Update()
            self.assert_native_geometry(state,aux)

    def test_valid_clearance_envelope_matches_native_file_loader(self):
        self.fixture();v=self.v;bs=[self.bogie,v.CreateAndAddBogie(self.gear),v.CreateAndAddBogie(self.gear)]
        for b,(x,y) in zip(bs,[(0,0),(6,3),(6,-3)]):
            v.SetParmValUpdate(b,'XContactPt','Bogie',x);v.SetParmValUpdate(b,'YContactPt','Bogie',y)
        aux=v.AddGeom('AUXILIARY',self.gear)
        for i,b in enumerate(bs):v.SetAuxiliaryGeomContactPtID(aux,i,b)
        v.SetParmValUpdate(aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_THREE_PT_CCE);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        content='0 0\n2 0\n3 1\n2 2\n0 2\n';f=self.path/'direct.cce';f.write_text(content)
        state,path=self.worker(dict(action='mutate',operation='auxiliary-cce',geom=aux,content=content))
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        # Independently replay the public native evaluation after scale bounds
        # exist, without calling Studio's refresh helper.
        v.SetAuxiliaryGeomContactPtID(aux,0,v.GetAuxiliaryGeomContactPtID(aux,0));v.Update()
        v.ReadAuxiliaryGeomCCEFile(aux,str(f));v.Update()
        v.SetAuxiliaryGeomContactPtID(aux,0,v.GetAuxiliaryGeomContactPtID(aux,0));v.Update()
        generated=('Cap','Chevron','Close','Flap','Trim','XSecCurve','XSecCurve_Background')
        self.assert_native_geometry(state,aux,generated)
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        v.SetAuxiliaryGeomContactPtID(aux,0,v.GetAuxiliaryGeomContactPtID(aux,0));v.Update()
        self.assert_native_geometry(state,aux,generated)
        reopened,_=self.worker(dict(action='state'),path)
        self.assert_native_geometry(reopened,aux,generated)
        fields={p['name']:p for p in next(c for c in reopened['components'] if c['id']==aux)['params'] if p['rawGroup']=='Design'}
        self.assertTrue(fields['ContactPt1_GearMode']['displayReadOnly'])
        curve=next(p for p in next(c for c in reopened['components'] if c['id']==aux)['params'] if p['rawGroup']=='XSecCurve')
        self.assertTrue(curve['displayReadOnly'])
