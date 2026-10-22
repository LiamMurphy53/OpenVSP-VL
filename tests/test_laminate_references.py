"""Layer lifetime and order retain original native references and properties."""
import unittest
import test_laminate_units
import native_files

class LaminateReferences(unittest.TestCase):
    setUpClass=classmethod(test_laminate_units.LaminateUnits.setUpClass.__func__)
    setUp=test_laminate_units.LaminateUnits.setUp
    tearDown=test_laminate_units.LaminateUnits.tearDown
    worker=test_laminate_units.LaminateUnits.worker
    fixture=test_laminate_units.LaminateUnits.fixture

    def test_referenced_layer_delete_is_atomic_for_five_consumers(self):
        v=self.v
        for kind in ['link','preset','expression','design','attribute']:
            with self.subTest(kind=kind):
                v.ClearVSPModel();self.gid=v.AddGeom('WING');self.fixture()
                layers=list(v.GetFeaLayerIDVec(self.material));layer=layers[1]
                pid=v.FindParm(layer,'Theta','FeaLayer')
                target=v.FindParm(self.gid,'X_Rel_Location','XForm')
                if kind=='link':v.AddParmLink(pid,target)
                elif kind=='preset':
                    group=v.AddVarPresetGroup('Layer angle');v.AddVarPresetParm(group,pid)
                    setting=v.AddVarPresetSetting(group,'Layup');v.SaveVarPresetParmVals(group,setting)
                elif kind=='expression':
                    v.AddAdvLink('Layer angle');index=v.GetLinkIndex('Layer angle')
                    v.AddAdvLinkInput(index,pid,'layer_angle');v.AddAdvLinkOutput(index,target,'position')
                    v.SetAdvLinkCode(index,'position = layer_angle;');v.BuildAdvLinkScript(index)
                elif kind=='design':v.AddDesignVar(pid,v.XDDM_VAR);native_files.save_design(v)
                else:v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Layer angle',pid)
                v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
                with self.assertRaisesRegex(ValueError,'laminate layer parameter IDs'):
                    self.worker(dict(action='mutate',operation='layer-delete',material=self.material,id=layer))
                self.assertEqual(self.model.read_bytes(),before)

    def test_reorder_retains_layer_ids_and_matches_original_material(self):
        self.fixture();v=self.v
        initial,_=self.worker(dict(action='state'));original_ids=[l['id'] for l in initial['tools']['layers'] if l['material']==self.material];path=self.model
        for direction,index in [('REORDER_MOVE_TOP',2),('REORDER_MOVE_DOWN',0),('REORDER_MOVE_BOTTOM',0),('REORDER_MOVE_UP',2)]:
            v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
            native_layers=list(v.GetFeaLayerIDVec(self.material))
            state,_=self.worker(dict(action='state'),path)
            layers=[l for l in state['tools']['layers'] if l['material']==self.material]
            layer=layers[index]
            state,path=self.worker(dict(action='mutate',operation='layer-reorder',material=self.material,id=layer['id'],direction=direction),path)
            v.ReorderFeaLayer(self.material,native_layers[index],getattr(v,direction));v.Update()
            expected=[{v.GetParmName(p):v.GetParmVal(p) for p in v.FindContainerParmIDs(l)} for l in v.GetFeaLayerIDVec(self.material)]
            actual=[{p['name']:p['value'] for p in l['params']} for l in state['tools']['layers'] if l['material']==self.material]
            self.assertEqual(actual,expected)
            self.assertEqual({l['id'] for l in state['tools']['layers'] if l['material']==self.material},set(original_ids))
            material=next(m for m in state['tools']['materials'] if m['id']==self.material)
            self.assertEqual({p['name']:p['value'] for p in material['params']},{v.GetParmName(p):v.GetParmVal(p) for p in v.FindContainerParmIDs(self.material)})

    def test_unreferenced_delete_matches_native_and_last_layer_is_retained(self):
        self.fixture();v=self.v;path=self.model
        for _ in range(2):
            state,_=self.worker(dict(action='state'),path)
            layers=[l for l in state['tools']['layers'] if l['material']==self.material]
            v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
            native_layers=list(v.GetFeaLayerIDVec(self.material))
            v.DeleteFeaLayer(self.material,native_layers[1]);v.Update()
            expected={v.GetParmName(p):v.GetParmVal(p) for p in v.FindContainerParmIDs(self.material)}
            state,path=self.worker(dict(action='mutate',operation='layer-delete',material=self.material,id=layers[1]['id']),path)
            self.assertEqual([l['id'] for l in state['tools']['layers'] if l['material']==self.material],[l['id'] for i,l in enumerate(layers) if i!=1])
            material=next(m for m in state['tools']['materials'] if m['id']==self.material)
            self.assertEqual({p['name']:p['value'] for p in material['params']},expected)
        last=next(l for l in state['tools']['layers'] if l['material']==self.material)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'at least one layer'):
            self.worker(dict(action='mutate',operation='layer-delete',material=self.material,id=last['id']),path)
        self.assertEqual(path.read_bytes(),before)
