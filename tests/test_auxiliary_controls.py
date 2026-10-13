"""Auxiliary workflows checked against the installed native SDK and native files."""
import sys,unittest,xml.etree.ElementTree as ET
import test_native,test_gear_controls
from vsp_runtime import load
from native_special import SHAPES
import native_auxiliary_controls as controls

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native runtime.')
class NativeAuxiliaryControls(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    assert_native_geometry=test_gear_controls.NativeGearControls.assert_native_geometry

    def fixture(self):
        v=self.v;self.gear=v.AddGeom('GEAR');self.bs=[v.CreateAndAddBogie(self.gear) for _ in range(3)]
        for b,(x,y) in zip(self.bs,[(0,0),(6,3),(6,-3)]):
            for n,a in [('XContactPt',x),('YContactPt',y),('Symmetrical',1),('TravelZ',.8),('TravelCompressed',.3),('TravelExtended',.2)]:v.SetParmValUpdate(b,n,'Bogie',a)
        self.prop=v.AddGeom('PROP');self.aux=v.AddGeom('AUXILIARY',self.gear)
        for i,b in enumerate(self.bs):v.SetAuxiliaryGeomContactPtID(self.aux,i,b)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def evaluate(self):
        v=self.v;v.Update();v.SetAuxiliaryGeomContactPtID(self.aux,0,v.GetAuxiliaryGeomContactPtID(self.aux,0));v.Update()

    def reopen(self,path):
        v=self.v
        # GearGeom's native destructor leaves Bogie containers registered.
        for g in list(v.FindGeoms()):
            if v.GetGeomTypeName(g).upper()=='GEAR':v.DelAllBogies(g)
            elif v.GetGeomTypeName(g).upper()=='AUXILIARY':
                # AuxiliaryGeom's empty destructor also leaves its standalone
                # curve alive. Delete it through the native shape replacement
                # before this test's same-process reload; workers are fresh.
                v.SetParmValUpdate(g,'AuxiliaryGeomType','Design',v.AUX_GEOM_SUPER_CONE)
                current=controls.curve(v,g)['type']
                controls.curve(v,g,1,v.XS_CIRCLE if current==v.XS_POINT else v.XS_POINT)
        v.ClearVSPModel();v.ReadVSPFile(str(path));self.evaluate()

    def aux_entry(self,state):return next(a for a in state['tools']['auxiliary'] if a['id']==self.aux)

    def curve_xml(self,path):
        return next(n for n in ET.parse(path).findall('.//Geom') if n.findtext('ParmContainer/ID')==self.aux).find('Geom/Auxiliary/XSecCurve')

    def test_all_twelve_modes_match_native_setup_and_reopening(self):
        self.fixture();v=self.v;path=self.model
        for name,(count,groups) in controls.SPECS.items():
            with self.subTest(mode=name):
                mode=getattr(v,name);parent=self.prop if name in ('AUX_GEOM_ROTOR_TIP_PATH','AUX_GEOM_THROWN_BLADE') else self.gear
                state,path=self.worker(dict(action='mutate',operation='auxiliary-setup',geom=self.aux,parent=parent,type=mode),path)
                v.SetGeomParent(self.aux,parent);v.SetParmValUpdate(self.aux,'AuxiliaryGeomType','Design',mode);self.evaluate()
                # Studio resets foreign contacts when the parent changes.
                if self.aux_entry(state)['contacts']!=[v.GetAuxiliaryGeomContactPtID(self.aux,i) for i in range(3)]:
                    for i,b in enumerate(self.aux_entry(state)['contacts']):v.SetAuxiliaryGeomContactPtID(self.aux,i,b)
                    self.evaluate()
                if count>=2:
                    for i,b in enumerate(self.bs):
                        state,path=self.worker(dict(action='mutate',operation='auxiliary-contact',geom=self.aux,index=i,bogie=b),path)
                        v.SetAuxiliaryGeomContactPtID(self.aux,i,b)
                    self.evaluate()
                generated=('Cap','Chevron','Close','Flap','Trim','XSecCurve','XSecCurve_Background') if mode==v.AUX_GEOM_THREE_PT_CCE else ()
                self.assert_native_geometry(state,self.aux,generated)
                a=self.aux_entry(state);self.assertEqual(a['controls']['mode'],name);self.assertEqual(a['controls']['contactCount'],count)
                self.assertEqual(a['controls']['groups'],[dict(title=t,names=ns) for t,ns in groups])
                self.reopen(path);cold,_=self.worker(dict(action='state'),path);self.assert_native_geometry(cold,self.aux,generated)

    def test_native_fragment_thrown_blade_and_failure_variants(self):
        self.fixture();v=self.v;path=self.model
        cases=[('AUX_GEOM_ROTOR_FRAGMENT','RotorFragmentMode',[x[0] for x in controls.choices(v)['RotorFragmentMode']],self.gear),
          ('AUX_GEOM_THROWN_BLADE','ThrownBladeMode',[v.PROP_BLADE_TRADITIONAL,v.PROP_BLADE_NONTRADITIONAL],self.prop),
          ('AUX_GEOM_WHEEL_TIRE_FAILURE','m_WheelTireFailureMode',[v.WHEEL_TIRE_1LG,v.WHEEL_TIRE_1SM,v.WHEEL_TIRE_2,v.WHEEL_TIRE_3E,v.WHEEL_TIRE_3R],self.gear)]
        for mode,selector,variants,parent in cases:
            state,path=self.worker(dict(action='mutate',operation='auxiliary-setup',geom=self.aux,parent=parent,type=getattr(v,mode)),path)
            v.SetGeomParent(self.aux,parent);v.SetParmValUpdate(self.aux,'AuxiliaryGeomType','Design',getattr(v,mode));self.evaluate()
            for value in variants:
                with self.subTest(mode=mode,variant=value):
                    pid=v.FindParm(self.aux,selector,'Design');state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
                    v.SetParmValUpdate(pid,value);self.evaluate();self.assert_native_geometry(state,self.aux)
            self.reopen(path);state,_=self.worker(dict(action='state'),path);self.assert_native_geometry(state,self.aux)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'does not implement'):self.worker(dict(action='mutate',operation='parameter',id=v.FindParm(self.aux,'m_WheelTireFailureMode','Design'),value=v.WHEEL_TIRE_4),path)
        self.assertEqual(path.read_bytes(),before)

    def test_three_contact_clearance_file_units_and_native_contact_parameters(self):
        self.fixture();v=self.v
        v.SetParmValUpdate(self.aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_THREE_PT_CCE);self.evaluate();v.WriteVSPFile(str(self.model),v.SET_ALL);path=self.model
        for i,b in enumerate(self.bs):
            state,path=self.worker(dict(action='mutate',operation='auxiliary-contact',geom=self.aux,index=i,bogie=b),path)
            v.SetAuxiliaryGeomContactPtID(self.aux,i,b);self.evaluate()
        text='0 0\n2 0\n3 1\n2 2\n0 2\n';f=self.path/'independent.cce';f.write_text(text)
        state,path=self.worker(dict(action='mutate',operation='auxiliary-cce',geom=self.aux,content=text),path);v.ReadAuxiliaryGeomCCEFile(self.aux,str(f));self.evaluate()
        generated=('Cap','Chevron','Close','Flap','Trim','XSecCurve','XSecCurve_Background');self.assert_native_geometry(state,self.aux,generated)
        for name,value in [('CCEUnits',v.LEN_FT),('CCEMainGearOffset',.2),('ContactPt1_SuspensionMode',v.GEAR_SUSPENSION_COMPRESSED),('ContactPt2_SuspensionMode',v.GEAR_SUSPENSION_EXTENDED),('ContactPt3_TireMode',v.TIRE_GROWTH_CONTACT),('ContactPt2_Isymm',1)]:
            pid=v.FindParm(self.aux,name,'Design');state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
            v.SetParmValUpdate(pid,value);self.evaluate();self.assert_native_geometry(state,self.aux,generated)
        self.assertEqual(self.aux_entry(state)['contacts'],self.bs)
        self.reopen(path);cold,_=self.worker(dict(action='state'),path);self.assert_native_geometry(cold,self.aux,generated)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'clearance-envelope'):self.worker(dict(action='mutate',operation='auxiliary-cce',geom=self.aux,content='0 nan\n1 2\n'),path)
        self.assertEqual(path.read_bytes(),before)

    def test_cce_saved_coordinates_units_contacts_and_mirror_guard(self):
        self.fixture();v=self.v
        v.SetParmValUpdate(self.aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_THREE_PT_CCE);self.evaluate();v.WriteVSPFile(str(self.model),v.SET_ALL)
        text='-3 0\n-2 1\n0 2\n2 1\n3 0\n';f=self.path/'native-coordinate-check.cce';f.write_text(text)
        state,path=self.worker(dict(action='mutate',operation='auxiliary-cce',geom=self.aux,content=text));v.ReadAuxiliaryGeomCCEFile(self.aux,str(f));self.evaluate()
        generated=('Cap','Chevron','Close','Flap','Trim','XSecCurve','XSecCurve_Background')
        self.assert_native_geometry(state,self.aux,generated)
        c=self.aux_entry(state)['controls'];self.assertEqual([p['point'] for p in c['contactPositions']['contacts']],[[0,0,0],[6,3,0],[6,-3,0]])
        self.assertEqual(c['clearanceCoordinates']['points'],[[0,-3,0],[0,-2,1],[0,0,2],[0,2,1],[0,3,0]])
        self.assertTrue(c['clearanceCoordinates']['exportable']);self.assertFalse(c['clearanceCoordinates']['nativeDefault']);self.assertEqual(c['contactPositions']['units'],v.LEN_FT)
        for unit in (v.LEN_MM,v.LEN_CM,v.LEN_M,v.LEN_IN,v.LEN_FT,v.LEN_YD,v.LEN_UNITLESS):
            with self.subTest(unit=unit):
                pid=v.FindParm(self.aux,'CCEUnits','Design');state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=unit),path);v.SetParmValUpdate(pid,unit);self.evaluate();self.assert_native_geometry(state,self.aux,generated)
                c=self.aux_entry(state)['controls'];self.assertEqual(c['clearanceCoordinates']['units'],unit);self.assertEqual(c['clearanceCoordinates']['modelUnits'],v.LEN_FT)
                cold,_=self.worker(dict(action='state'),path);self.assertEqual(self.aux_entry(cold)['controls'],c)
        mirror=v.FindParm(self.aux,'ContactPt2_Isymm','Design');state,path=self.worker(dict(action='mutate',operation='parameter',id=mirror,value=1),path);v.SetParmValUpdate(mirror,1);self.evaluate();self.assert_native_geometry(state,self.aux,generated)
        self.assertEqual(self.aux_entry(state)['controls']['contactPositions']['contacts'][1]['point'],[6,-3,0])
        state,path=self.worker(dict(action='mutate',operation='parameter',id=mirror,value=0),path)
        bid=self.bs[1];pid=v.FindParm(bid,'Symmetrical','Bogie');state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=0),path)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'Enable Mirror wheel group'):self.worker(dict(action='mutate',operation='parameter',id=mirror,value=1),path)
        self.assertEqual(path.read_bytes(),before)
        self.reopen(path);cold,_=self.worker(dict(action='state'),path);self.assert_native_geometry(cold,self.aux,generated)

    def test_all_twenty_cone_shapes_and_native_file_replay(self):
        self.fixture();v=self.v;v.SetParmValUpdate(self.aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_SUPER_CONE);self.evaluate();v.WriteVSPFile(str(self.model),v.SET_ALL);path=self.model
        self.assertEqual(len(SHAPES),20)
        for shape in SHAPES:
            with self.subTest(shape=shape):
                state,path=self.worker(dict(action='mutate',operation='auxiliary-profile-shape',geom=self.aux,shape=shape),path)
                # Read the native file with the independent public SDK. Shape
                # and driver choices come from the original EncodeXml schema.
                self.assertEqual(int(self.curve_xml(path).findtext('XSecCurve/Type')),getattr(v,shape))
                self.reopen(path);self.assert_native_geometry(state,self.aux)
                dimensions=self.aux_entry(state)['controls']['profile']
                if shape=='XS_EDIT_CURVE':
                    self.assertEqual(int(self.curve_xml(path).findtext('EditCurveXSec/NumPts')),len(dimensions['controlPoints']))
                    self.assertGreater(len(dimensions['controlPoints']),0)
                component=next(c for c in state['components'] if c['id']==self.aux)
                for driver in dimensions['driverControls']:
                    field=next(p for p in component['params'] if p['id']==driver['parameter'])
                    if driver['value'] not in dimensions['drivers'] or field.get('displayReadOnly') or not field.get('active',True) or field['name'].endswith('_Dummy'):continue
                    value=.2 if field['name']=='ThickChord' else 40 if driver['value']==0 else 20
                    self.reopen(path)
                    state,path=self.worker(dict(action='mutate',operation='parameter',id=field['id'],value=value),path)
                    v.SetParmValUpdate(field['id'],value);self.evaluate();self.assert_native_geometry(state,self.aux)
                self.reopen(path);self.assert_native_geometry(state,self.aux)
                profile=self.aux_entry(state)['controls']['profile'];self.assertEqual(profile['type'],getattr(v,shape));self.assertEqual(len(profile['profile']),101)
                cold,_=self.worker(dict(action='state'),path);self.assert_native_geometry(cold,self.aux)
                self.assertEqual(self.aux_entry(cold)['controls']['profile'],profile)

    def test_editable_cone_operations_match_independent_section_sdk(self):
        self.fixture();v=self.v
        v.SetParmValUpdate(self.aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_SUPER_CONE)
        source=v.AddGeom('STACK');surf=v.GetXSecSurf(source,0);v.ChangeXSecShape(surf,1,v.XS_ELLIPSE);x=v.GetXSec(surf,1)
        v.SetXSecWidth(x,40);v.SetXSecHeight(x,20);v.ConvertXSecToEdit(source,1);v.Update()
        self.evaluate();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='auxiliary-profile-copy',geom=self.aux,source=source,index=1))
        def check(state):
            p=self.aux_entry(state)['controls']['profile']
            self.assertEqual(p['controlPoints'],[[a.x(),a.y(),a.z()] for a in v.GetEditXSecCtrlVec(x,True)])
            self.assertEqual(p['curveU'],list(v.GetEditXSecUVec(x)))
            self.assertEqual(p['fixedU'],list(v.GetEditXSecFixedUVec(x)))
            self.assertEqual(p['smooth'],[bool(v.GetParmVal(v.GetXSecParm(x,f'G1_{i}'))) for i in range(len(p['controlPoints']))])
            self.assertEqual(p['curveType'],int(v.GetParmVal(v.GetXSecParm(x,'CurveType'))))
        check(state)
        sym=next(p['id'] for p in next(c for c in state['components'] if c['id']==self.aux)['params'] if p['name']=='SymType' and p['rawGroup']=='XSecCurve')
        for symmetry in (v.SYM_RL,v.SYM_NONE):
            v.SetParmValUpdate(v.GetXSecParm(x,'SymType'),symmetry)
            state,path=self.worker(dict(action='mutate',operation='parameter',id=sym,value=symmetry),path);check(state)
            for request in [dict(operation='smooth',point=3,smooth=True),dict(operation='point',point=2,xyz=[.34,-.25,0]),dict(operation='type',type='LINEAR'),dict(operation='split',u=.125),dict(operation='point',point=1,xyz=[.31,-.17,0]),dict(operation='fixed',point=1,fixed=True),dict(operation='reparameterize'),dict(operation='delete',point=1),dict(operation='type',type='PCHIP'),dict(operation='type',type='CEDIT')]:
                with self.subTest(symmetry=symmetry,operation=request['operation']):
                    op=request['operation']
                    if op=='smooth':v.SetParmValUpdate(v.GetXSecParm(x,f"G1_{request['point']}"),int(request['smooth']))
                    elif op=='point':v.MoveEditXSecPnt(x,request['point'],v.vec3d(*request['xyz']))
                    elif op=='type':v.EditXSecConvertTo(x,getattr(v,request['type']))
                    elif op=='split':v.EditXSecSplit01(x,request['u'])
                    elif op=='delete':v.EditXSecDelPnt(x,request['point'])
                    elif op=='fixed':
                        flags=list(v.GetEditXSecFixedUVec(x));flags[request['point']]=request['fixed'];v.SetEditXSecFixedUVec(x,flags)
                    else:v.ReparameterizeEditXSec(x)
                    v.Update();state,path=self.worker({**request,'action':'mutate','geom':self.aux,'operation':'auxiliary-profile-edit-'+op},path)
                    check(state);cold,_=self.worker(dict(action='state'),path);check(cold)
        before=path.read_bytes()
        for request in [dict(operation='point',point=True,xyz=[0,0,0]),dict(operation='point',point=1,xyz=[float('nan'),0,0]),dict(operation='point',point=1,xyz=[1e15,0,0]),dict(operation='smooth',point=1,smooth=True),dict(operation='fixed',point=1,fixed='yes'),dict(operation='delete',point=0),dict(operation='split',u=0),dict(operation='type',type='unknown')]:
            op=request['operation']
            with self.assertRaises(ValueError):self.worker({**request,'action':'mutate','geom':self.aux,'operation':'auxiliary-profile-edit-'+op},path)
            self.assertEqual(path.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='parameter',id=sym,value=v.SYM_RL),path)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'locked by OpenVSP'):
            self.worker(dict(action='mutate',geom=self.aux,operation='auxiliary-profile-edit-point',point=4,xyz=[.4,.1,0]),path)
        self.assertEqual(path.read_bytes(),before)
        self.reopen(path);cold,_=self.worker(dict(action='state'),path);self.assert_native_geometry(cold,self.aux)

    def test_copy_native_dimension_drivers_and_imports(self):
        self.fixture();v=self.v;v.SetParmValUpdate(self.aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_SUPER_CONE)
        body=v.AddGeom('FUSELAGE');surf=v.GetXSecSurf(body,0);v.ChangeXSecShape(surf,1,v.XS_ELLIPSE);section=v.GetXSec(surf,1)
        v.SetDriverGroup(body,1,v.AREA_XSEC_DRIVER,v.HWRATIO_XSEC_DRIVER);v.SetParmValUpdate(v.GetXSecParm(section,'Area'),100);v.SetParmValUpdate(v.GetXSecParm(section,'HWRatio'),.6)
        self.evaluate();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='auxiliary-profile-copy',geom=self.aux,source=body,index=1))
        source_cid=v.GetParmContainer(v.GetXSecParm(section,'Area'))
        source={(v.GetParmGroupName(p),v.GetParmName(p)):v.GetParmVal(p) for p in v.FindContainerParmIDs(source_cid)}
        profile=self.aux_entry(state)['controls']['profile']
        target={(p['rawGroup'],p['name']):p['value'] for p in next(c for c in state['components'] if c['id']==self.aux)['params'] if p['id'] in profile['parameterIDs']}
        self.assertEqual(source,target)
        self.reopen(path);self.assert_native_geometry(state,self.aux)
        fields={p['name']:p for p in next(c for c in state['components'] if c['id']==self.aux)['params'] if p['id'] in profile['parameterIDs']}
        self.assertFalse(fields['Area'].get('displayReadOnly',False));self.assertFalse(fields['HWRatio'].get('displayReadOnly',False));self.assertTrue(fields['Ellipse_Width']['displayReadOnly']);self.assertTrue(fields['Ellipse_Height']['displayReadOnly'])
        for name,value in [('Area',150),('HWRatio',.8)]:
            self.reopen(path)
            state,path=self.worker(dict(action='mutate',operation='parameter',id=fields[name]['id'],value=value),path)
            v.SetParmValUpdate(fields[name]['id'],value);self.evaluate();self.assert_native_geometry(state,self.aux)
        before=path.read_bytes()
        with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='parameter',id=fields['Ellipse_Width']['id'],value=40),path)
        self.assertEqual(path.read_bytes(),before)
        for drivers in ([0,2],[1,3],[0,1],[1,2],[0,3],[2,3]):
            state,path=self.worker(dict(action='mutate',operation='auxiliary-profile-drivers',geom=self.aux,drivers=drivers),path)
            self.assertEqual(self.aux_entry(state)['controls']['profile']['drivers'],drivers)
            self.reopen(path);self.assert_native_geometry(state,self.aux)
        before=path.read_bytes()
        for drivers in ([0,0],[0],[True,2],[0,7]):
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='auxiliary-profile-drivers',geom=self.aux,drivers=drivers),path)
            self.assertEqual(path.read_bytes(),before)
        for fmt,text,shape in [('section','OPENVSP_XSEC_FILE_V1\n1 0\n0 1\n-1 0\n0 -1\n1 0\n',v.XS_FILE_FUSE),('airfoil','Independent airfoil\n1 0\n.5 .1\n0 0\n.5 -.1\n1 0\n',v.XS_FILE_AIRFOIL)]:
            with self.subTest(format=fmt):
                f=self.path/('independent.fxs' if fmt=='section' else 'independent.dat');f.write_text(text)
                source=v.AddGeom('STACK');surf=v.GetXSecSurf(source,0);v.ChangeXSecShape(surf,1,shape);xid=v.GetXSec(surf,1)
                if fmt=='section':v.ReadFileXSec(xid,str(f))
                else:v.ReadFileAirfoil(xid,str(f));v.SetXSecWidth(xid,1)
                v.Update();native_file=self.path/'independent-import.vsp3';v.WriteVSPFile(str(native_file),v.SET_ALL)
                cid=v.GetParmContainer(v.GetXSecParm(xid,'Area'))
                original=next(n for n in ET.parse(native_file).findall('.//XSecCurve') if n.findtext('ParmContainer/ID')==cid)
                def payload(node):return [(e.tag,(e.text or '').strip()) for child in node if child.tag!='ParmContainer' for e in child.iter()]
                expected_payload=payload(original)
                v.DeleteGeom(source);v.Update()
                state,path=self.worker(dict(action='mutate',operation='auxiliary-profile-import',geom=self.aux,format=fmt,content=text),path)
                self.assertEqual(int(self.curve_xml(path).findtext('XSecCurve/Type')),shape)
                # Public ComputeXSecPnt includes the Stack's placement/basis.
                # Compare the complete native curve/file coordinate payload
                # instead of inventing an inverse coordinate transformation.
                self.assertEqual(payload(self.curve_xml(path)),expected_payload)
                self.reopen(path);self.assert_native_geometry(state,self.aux)
                cold,_=self.worker(dict(action='state'),path);self.assert_native_geometry(cold,self.aux)
        state,path=self.worker(dict(action='mutate',operation='auxiliary-profile-convert',geom=self.aux),path)
        self.assertEqual(int(self.curve_xml(path).findtext('XSecCurve/Type')),v.XS_EDIT_CURVE);self.reopen(path);self.assert_native_geometry(state,self.aux)
        before=path.read_bytes()
        for r in [dict(operation='auxiliary-profile-shape',shape='missing'),dict(operation='auxiliary-profile-import',format='section',content='invalid'),dict(operation='auxiliary-profile-copy',source=self.gear,index=0)]:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',geom=self.aux,**r),path)
            self.assertEqual(path.read_bytes(),before)
