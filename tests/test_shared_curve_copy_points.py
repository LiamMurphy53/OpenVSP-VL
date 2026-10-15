"""Short shared profile copies match fresh native XML decoding, not retained points."""
import copy
import unittest
import xml.etree.ElementTree as ET
import test_native
from test_curve_point_list import ROWS

class SharedCurveCopyPoints(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def check_copy(self,cubic=False):
        from native_bor_curves import mutate,container
        v=self.v;source=v.AddGeom('STACK');bor=v.AddGeom('BODYOFREVOLUTION')
        surf=v.GetXSecSurf(source,0);v.ChangeXSecShape(surf,1,v.XS_EDIT_CURVE);x=v.GetXSec(surf,1)
        v.SetParmValUpdate(v.GetXSecParm(x,'SymType'),v.SYM_NONE);v.EditXSecConvertTo(x,v.LINEAR)
        v.SetEditXSecPnts(x,[r[0] for r in ROWS],[v.vec3d(*r[1:4]) for r in ROWS],[r[4] for r in ROWS])
        if cubic:
            v.EditXSecConvertTo(x,v.CEDIT)
            v.SetParmValUpdate(v.GetXSecParm(x,'G1_3'),1)
            fixed=list(v.GetEditXSecFixedUVec(x));fixed[3]=True;v.SetEditXSecFixedUVec(x,fixed)
        v.Update()
        expected_points=[[p.x(),p.y(),p.z()] for p in v.GetEditXSecCtrlVec(x,True)]
        expected_rounding=[v.GetParmVal(v.GetXSecParm(x,'R_'+str(i))) for i in range(len(expected_points))]
        expected_flags={name:v.GetParmVal(v.GetXSecParm(x,name)) for i in range(len(expected_points)) for name in ('G1_'+str(i),'FixedU_'+str(i))}
        mutate(v,dict(operation='bor-curve-convert',geom=bor));v.Update()
        cid=container(v,bor);v.SetParmValUpdate(v.FindParm(cid,'SymType','XSecCurve'),v.SYM_NONE)
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        source_cid=v.GetParmContainer(v.GetXSecParm(x,'Theta'))
        tree=ET.parse(self.model);profile=next(n for n in tree.iter('XSecCurve') if n.findtext('ParmContainer/ID')==source_cid)
        target=next(n for n in tree.iter('XSecCurve') if n.findtext('ParmContainer/ID')==cid)
        parent=next(n for n in tree.iter() if target in list(n));replacement=copy.deepcopy(profile);replacement.find('ParmContainer/ID').text=cid
        parent.remove(target);parent.append(replacement)
        source_geom=next(n for n in tree.iter('Geom') if n.findtext('ParmContainer/ID')==source)
        next(n for n in tree.iter() if source_geom in list(n)).remove(source_geom)
        reference=self.path/'reference.vsp3';tree.write(reference,encoding='utf-8',xml_declaration=True)
        expected,_=self.worker(dict(action='state'),reference)
        result,saved=self.worker(dict(action='mutate',operation='bor-profile-copy',geom=bor,source=dict(kind='section',geom=source,surface=0,index=1)))
        cold,_=self.worker(dict(action='state'),saved)
        for state in (result,cold):
            editable=next(item for item in state['tools']['bodiesOfRevolution'] if item['id']==bor)['editable']
            self.assertEqual(editable['controlPoints'],expected_points)
            self.assertEqual(editable['rounding'],expected_rounding)
            flags={p['name']:p['value'] for p in editable['params'] if p['name'] in expected_flags}
            self.assertEqual(flags,expected_flags)
            self.assertEqual(next(c['surfaces'] for c in state['components'] if c['id']==bor),next(c['surfaces'] for c in expected['components'] if c['id']==bor))

    def test_referenced_destination_point_rejects_atomically(self):
        from native_bor_curves import mutate,container
        v=self.v;source=v.AddGeom('STACK');bor=v.AddGeom('BODYOFREVOLUTION')
        surf=v.GetXSecSurf(source,0);v.ChangeXSecShape(surf,1,v.XS_EDIT_CURVE);x=v.GetXSec(surf,1)
        v.SetParmValUpdate(v.GetXSecParm(x,'SymType'),v.SYM_NONE);v.EditXSecConvertTo(x,v.LINEAR)
        v.SetEditXSecPnts(x,[r[0] for r in ROWS],[v.vec3d(*r[1:4]) for r in ROWS],[r[4] for r in ROWS])
        mutate(v,dict(operation='bor-curve-convert',geom=bor));v.Update()
        cid=container(v,bor);pid=v.FindParm(cid,'X_3','XSecCurve')
        v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Referenced destination point',pid)
        v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'reference'):
            self.worker(dict(action='mutate',operation='bor-profile-copy',geom=bor,source=dict(kind='section',geom=source,surface=0,index=1)))
        self.assertEqual(self.model.read_bytes(),before)
        candidate=next(self.path.glob('*/aircraft.vsp3'));self.assertEqual(candidate.read_bytes(),before)

    def test_short_linear_copy(self):self.check_copy()

    def test_short_cubic_copy_preserves_smooth_and_fixed_flags(self):self.check_copy(True)

if __name__=='__main__':unittest.main()
