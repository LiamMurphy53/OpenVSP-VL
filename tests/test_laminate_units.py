"""Multi-angle native laminate outputs retain explicit structural unit labels."""
import sys,unittest,xml.etree.ElementTree as ET,math
import test_native

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class LaminateUnits(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v
        self.material=v.AddFeaMaterial();v.SetContainerName(self.material,'Three-angle laminate')
        v.SetParmValUpdate(v.FindParm(self.material,'FeaMaterialType','FeaMaterial'),v.FEA_LAMINATE)
        v.SetParmValUpdate(v.FindParm(self.material,'LengthUnit','FeaMaterial'),v.LEN_MM)
        self.layers=list(v.GetFeaLayerIDVec(self.material))
        while len(self.layers)<3:self.layers.append(v.AddFeaLayer(self.material))
        for layer,t,angle in zip(self.layers,[.2,.3,.4],[0,45,-45]):
            v.SetParmVal(v.FindParm(layer,'Thickness','FeaLayer'),t)
            v.SetParmVal(v.FindParm(layer,'Theta','FeaLayer'),angle)
        lamina=next(m for m in v.GetFeaMaterialIDVec() if m.startswith('_') and v.GetParmVal(v.FindParm(m,'FeaMaterialType','FeaMaterial'))==v.FEA_ENG_ORTHO)
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        # Original saved string-reference representation, not Studio setters.
        tree=ET.parse(self.model)
        for node in tree.findall('.//FeaLayerInfo'):
            if node.findtext('ParmContainer/ID') in self.layers:node.find('FeaLaminaID').text=lamina
        tree.write(self.model,encoding='utf-8',xml_declaration=True)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        self.unit=v.FindParm(v.GetVehicleID(),'StructUnit','FeaStructure')

    def test_all_five_systems_match_original_multiangle_laminate(self):
        self.fixture();v=self.v
        systems=[(v.SI_UNIT,'m','kg/m³','Pa','1/K'),(v.CGS_UNIT,'cm','g/cm³','barye','1/K'),(v.MPA_UNIT,'mm','tonne/mm³','MPa','1/K'),(v.BFT_UNIT,'ft','slug/ft³','psf','1/°R'),(v.BIN_UNIT,'in','lbf·s²/in⁴','psi','1/°R')]
        original=self.model.read_bytes()
        for system,length,density,modulus,thermal in systems:
            with self.subTest(system=system):
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
                v.SetParmValUpdate(self.unit,system)
                v.Update()
                expected={p:v.GetParmVal(p) for p in v.FindContainerParmIDs(self.material)}
                state,path=self.worker(dict(action='mutate',operation='parameter',id=self.unit,value=system))
                reopened,_=self.worker(dict(action='state'),path)
                for data in [state,reopened]:
                    material=next(m for m in data['tools']['materials'] if m['id']==self.material)
                    fields={p['name']:p for p in material['params']}
                    self.assertEqual({p['id']:p['value'] for p in material['params']},expected)
                    for name,unit in [('Thickness','mm'),('Thickness_FEM',length),('MassDensity_FEM',density),('E1_FEM',modulus),('G12_FEM',modulus),('A1_FEM',thermal),('nu12','dimensionless')]:
                        self.assertEqual(fields[name]['nativeUnit'],unit)
                        self.assertTrue(math.isfinite(fields[name]['value']))
                    self.assertAlmostEqual(fields['Thickness']['value'],.9)
                    self.assertGreater(fields['E1_FEM']['value'],0)
                    self.assertNotEqual(fields['E1_FEM']['value'],fields['E2_FEM']['value'])
                self.assertEqual(self.model.read_bytes(),original)

    def test_layer_edit_reopen_and_solver_decks_match_original(self):
        self.fixture();v=self.v
        index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index)
        for key,value in [('CFD_MAX_EDGE_LEN',1.),('CFD_MIN_EDGE_LEN',.2),('CFD_MAX_GAP',.03)]:v.SetFeaMeshVal(self.gid,index,getattr(v,key),value)
        v.WriteVSPFile(str(self.model),v.SET_ALL);tree=ET.parse(self.model)
        skin=tree.find('.//FeaPartInfo');prop=skin.findtext('FeaPropertyID')
        property_node=next(n for n in tree.findall('.//FeaPropertyInfo') if n.findtext('ParmContainer/ID')==prop)
        property_node.find('FeaMaterialID').text=self.material
        tree.write(self.model,encoding='utf-8',xml_declaration=True)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.Update()
        material_node=next(n for n in tree.findall('.//FeaMaterialInfo') if n.findtext('ParmContainer/ID')==self.material)
        angle=material_node.findall('FeaLayerInfo')[1].find('ParmContainer/FeaLayer/Theta').get('ID')
        # The in-process original loader remaps layer IDs that still exist in
        # its registry; address the independent reference by current layer order.
        reference_layer=v.GetFeaLayerIDVec(self.material)[1]
        v.SetParmValUpdate(v.FindParm(reference_layer,'Theta','FeaLayer'),30.);v.Update()
        expected={p:v.GetParmVal(p) for p in v.FindContainerParmIDs(self.material)}
        state,path=self.worker(dict(action='mutate',operation='parameter',id=angle,value=30.))
        reopened,_=self.worker(dict(action='state'),path)
        for data in [state,reopened]:
            material=next(m for m in data['tools']['materials'] if m['id']==self.material)
            self.assertEqual({p['id']:p['value'] for p in material['params']},expected)
        saved=path.read_bytes()
        result,out=self.worker(dict(action='analysis',name='FeaMeshAnalysis',structure=sid,formats=['CALCULIX','NASTRAN','MASS']),path)
        self.assertEqual(path.read_bytes(),saved);self.assertEqual(out.read_bytes(),saved)
        self.assertGreater(result['meshSummary']['nodes'],0)
        for fmt,ext in [('CALCULIX','inp'),('NASTRAN','dat')]:
            v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();v.Update()
            reference=self.path/('direct-laminate.'+ext)
            v.SetFeaMeshFileName(self.gid,index,getattr(v,'FEA_'+fmt+'_FILE_NAME'),str(reference))
            v.ComputeFeaMesh(self.gid,index,getattr(v,'FEA_'+fmt+'_FILE_NAME'))
            if fmt=='NASTRAN':reference=reference.with_suffix('.bdf')
            actual=out.parent/('structure.'+('bdf' if fmt=='NASTRAN' else ext))
            self.assertEqual(actual.read_bytes(),reference.read_bytes(),fmt)
