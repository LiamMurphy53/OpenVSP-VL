"""Profile-only clipboard copies preserve source vectors and target placement."""
import copy
import unittest
import xml.etree.ElementTree as ET
import test_native
from test_curve_point_list import ROWS

class ProfileOnlyCopy(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def check(self,kind):
        from test_shared_point_lists import SharedPointLists
        from native_editable_curves import replace_container_points
        import native_region_curves
        v=self.v;cases=SharedPointLists.fixture(self)
        for key,source,request,cid in cases:
            fields={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
            replace_container_points(v,cid,fields,dict(type='LINEAR',rows=ROWS))
            if key in ('controls','structuralSubsurfaces'):native_region_curves.edit(v,request)
        target=v.AddGeom(kind);surf=v.GetXSecSurf(target,0);v.ChangeXSecShape(surf,1,v.XS_EDIT_CURVE)
        x=v.GetXSec(surf,1);target_cid=v.GetParmContainer(v.GetXSecParm(x,'Theta'))
        v.SetParmValUpdate(target,'X_Rel_Location','XForm',14)
        v.SetParmValUpdate(target,'Z_Rel_Rotation','XForm',17)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        baseline,_=self.worker(dict(action='state'))
        for key,source,_,cid in cases:
            with self.subTest(source=key,target=kind):
                tree=ET.parse(self.model);profile=next(n for n in tree.iter('XSecCurve') if n.findtext('ParmContainer/ID')==cid)
                original=next(n for n in tree.iter('XSecCurve') if n.findtext('ParmContainer/ID')==target_cid)
                parent=next(n for n in tree.iter() if original in list(n));replacement=copy.deepcopy(profile);replacement.find('ParmContainer/ID').text=target_cid
                parent.remove(original);parent.append(replacement)
                owner=source.get('geom',self.gid)
                source_geom=next(n for n in tree.iter('Geom') if n.findtext('ParmContainer/ID')==owner)
                next(n for n in tree.iter() if source_geom in list(n)).remove(source_geom)
                reference=self.path/'reference.vsp3';tree.write(reference,encoding='utf-8',xml_declaration=True)
                expected,_=self.worker(dict(action='state'),reference)
                actual,path=self.worker(dict(action='mutate',operation='section-copy-from',geom=target,surface=0,index=1,curveOnly=True,source=source))
                cold,_=self.worker(dict(action='state'),path)
                ref=next(c for c in expected['components'] if c['id']==target)
                for state in (actual,cold):
                    for original_component in baseline['components']:
                        if original_component['id']==target:continue
                        unchanged=next(c for c in state['components'] if c['id']==original_component['id'])
                        self.assertEqual(unchanged['surfaces'],original_component['surfaces'])
                        self.assertEqual(unchanged['params'],original_component['params'])
                    component=next(c for c in state['components'] if c['id']==target);section=component['sections'][1]
                    self.assertEqual(section['controlPoints'],[r[1:4] for r in ROWS])
                    self.assertEqual(section['rounding'],[r[4] for r in ROWS])
                    self.assertEqual(section['profile'],ref['sections'][1]['profile'])
                    self.assertEqual(component['surfaces'],ref['surfaces'])
                    for name,value in [('X_Rel_Location',14),('Z_Rel_Rotation',17)]:self.assertEqual(next(p['value'] for p in component['params'] if p['name']==name and p['rawGroup']=='XForm'),value)

    def test_referenced_destination_rejects_without_saving(self):
        from native_bor_curves import mutate
        v=self.v;source=v.AddGeom('BODYOFREVOLUTION');mutate(v,dict(operation='bor-curve-convert',geom=source))
        target=v.AddGeom('STACK');surf=v.GetXSecSurf(target,0);v.ChangeXSecShape(surf,1,v.XS_EDIT_CURVE)
        x=v.GetXSec(surf,1);pid=v.GetXSecParm(x,'X_3')
        v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Destination point reference',pid)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'reference'):
            self.worker(dict(action='mutate',operation='section-copy-from',geom=target,surface=0,index=1,curveOnly=True,source=dict(kind='bor',geom=source)))
        self.assertEqual(self.model.read_bytes(),before)
        self.assertEqual(next(self.path.glob('*/aircraft.vsp3')).read_bytes(),before)

    def test_stack_destinations(self):self.check('STACK')
    def test_fuselage_destinations(self):self.check('FUSELAGE')
    def test_wing_destinations(self):self.check('WING')
    def test_propeller_destinations(self):self.check('PROP')

if __name__=='__main__':unittest.main()
