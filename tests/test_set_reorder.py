"""Named-set moves preserve native content, metadata and saved references."""
import unittest
import test_native
import native_components

class SetReorder(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_permutation_preserves_geometry_attributes_modes_and_presets(self):
        v=self.v;g=self.gid;pod=v.AddGeom('POD');v.Update()
        for index,label,members in [(3,'Aircraft A',[g]),(4,'Payload',[pod]),(5,'Combined',[g,pod])]:
            v.SetSetName(index,label)
            for geom in v.FindGeoms():v.SetSetFlag(geom,index,geom in members)
        attrs=[v.AddAttributeString(v.GetGeomSetCollection(i),'Set note',value) for i,value in enumerate(['A metadata','Payload metadata','Combined metadata'])]
        mode=v.CreateAndAddMode('A selection',3,5)
        parameter=v.FindParm(v.FindContainer('ParasiteDragSettings',0),'Set','ParasiteDrag');v.SetParmValUpdate(parameter,3)
        group=v.AddVarPresetGroup('Reference preset');v.AddVarPresetParm(group,parameter);setting=v.AddVarPresetSetting(group,'A');v.SaveVarPresetParmVals(group,setting)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        baseline,_=self.worker(dict(action='state'));before_refs=native_components.references(v)
        order=[5,3,4,*range(6,v.GetNumSets())];mapping={old:new for new,old in enumerate(order,3)}
        state,saved=self.worker(dict(action='mutate',operation='set-reorder',order=order))
        cold,_=self.worker(dict(action='state'),saved)
        for result in (state,cold):
            self.assertEqual(result['components'],baseline['components'])
            for destination,source in enumerate(order,3):
                self.assertEqual(result['tools']['sets'][destination]['name'],baseline['tools']['sets'][source]['name'])
                self.assertEqual(result['tools']['sets'][destination]['members'],baseline['tools']['sets'][source]['members'])
            refs={r['key']:r['value'] for r in result['tools']['setConfig']['references']}
            for r in before_refs:self.assertEqual(refs[r['key']],mapping.get(r['value'],r['value']))
            self.assertEqual(result['tools']['sets'][:3],baseline['tools']['sets'][:3])
        v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update()
        for old,attr in enumerate(attrs,3):
            self.assertEqual(v.GetObjectParent(attr),v.GetGeomSetCollection(mapping[old]-3))
            self.assertEqual(list(v.GetAttributeStringVal(attr)),[['A metadata','Payload metadata','Combined metadata'][old-3]])
        self.assertEqual(list(v.GetVarPresetParmVals(setting)),[4])
        self.assertEqual(v.GetParmVal(parameter),4)

    def test_linked_geometry_lock_rejects_move_without_changing_file(self):
        v=self.v;g=self.gid
        source=v.FindParm(v.FindContainer('ParasiteDragSettings',0),'Set','ParasiteDrag');v.SetParmValUpdate(source,3)
        target=v.GetXSecParm(v.GetXSec(v.GetXSecSurf(g,0),1),'Root_Chord');scale=v.GetParmVal(target)/3
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        state,path=self.worker(dict(action='mutate',operation='link-add',source=source,target=target,scale=scale))
        state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[target],locked=True),path)
        order=list(range(3,v.GetNumSets()));order[0],order[1]=order[1],order[0]
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',operation='set-reorder',order=order),path)
        self.assertEqual(path.read_bytes(),before)

    def test_invalid_permutation_preserves_file(self):
        v=self.v;slots=list(range(3,v.GetNumSets()))
        for order in [slots[:-1],[3,*slots[1:-1],3],[0,*slots[1:]],[True,*slots[1:]]]:
            before=self.model.read_bytes()
            with self.assertRaisesRegex(ValueError,'each user-set index'):self.worker(dict(action='mutate',operation='set-reorder',order=order))
            self.assertEqual(self.model.read_bytes(),before)

if __name__=='__main__':unittest.main()
