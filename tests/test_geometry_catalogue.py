"""Every installed native geometry type retains original saved surfaces."""
import sys,unittest
from collections import Counter
import test_native

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class GeometryCatalogue(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def compare(self,state,gid,reference=None):
        v=self.v;c=next(c for c in state['components'] if c['id']==gid);gid=reference or gid
        # Generated section containers can repeat group/name pairs. Preserve
        # their full multiplicity instead of dropping values in a dictionary.
        expected=Counter((v.GetParmGroupName(p),v.GetParmName(p),v.GetParmVal(p)) for p in v.GetGeomParmIDs(gid))
        actual=Counter((p['rawGroup'],p['name'],p['value']) for p in c['params'])
        self.assertEqual(len(c['params']),len(v.GetGeomParmIDs(gid)))
        self.assertEqual(actual,expected)
        valid=[i for i in range(v.GetTotalNumSurfs(gid)) if all(len(axis)>=2 for axis in v.GetUWTess01(gid,i%max(1,v.GetNumMainSurfs(gid))))]
        self.assertEqual([s['index'] for s in c['surfaces']],valid)
        for surf in c['surfaces']:
            u,w=v.GetUWTess01(gid,surf['index']%v.GetNumMainSurfs(gid))
            points=v.CompVecPnt01(gid,surf['index'],[a for a in u for _ in w],[b for _ in u for b in w])
            self.assertEqual(surf['points'],[[q.x(),q.y(),q.z()] for q in points])

    def test_all_installed_types_default_transform_and_cold_surfaces_match_original(self):
        v=self.v;types=list(v.GetGeomTypes());self.assertTrue(types)
        for kind in types:
            with self.subTest(kind=kind):
                v.ClearVSPModel();parent=v.AddGeom('WING') if kind=='CONFORMAL' else ''
                v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                reference=v.AddGeom(kind,parent);v.Update()
                saved=self.model.read_bytes()
                state,path=self.worker(dict(action='mutate',operation='add',type=kind,parent=parent));gid=state['changed'];self.compare(state,gid,reference)
                component=next(c for c in state['components'] if c['id']==gid)
                transform=next((p for p in component['params'] if p['rawGroup']=='XForm' and p['name']=='X_Rel_Location' and p.get('active',True) and not p.get('displayReadOnly')),None)
                if transform:
                    pid=transform['id'];original=v.FindParm(reference,'X_Rel_Location','XForm')
                elif parent:pid=original=v.FindParm(parent,'X_Rel_Location','XForm')
                else:
                    # Empty native routes derive their transform from anchors.
                    locked=next(p for p in component['params'] if p['rawGroup']=='XForm' and p['name']=='X_Rel_Location')
                    before=path.read_bytes()
                    with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='parameter',id=locked['id'],value=2.25),path)
                    self.assertEqual(path.read_bytes(),before)
                    cold,_=self.worker(dict(action='state'),path);self.compare(cold,gid,reference)
                    self.assertEqual(self.model.read_bytes(),saved)
                    continue
                state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=2.25),path)
                v.SetParmValUpdate(original,2.25);v.Update();self.compare(state,gid,reference)
                cold,_=self.worker(dict(action='state'),path);self.compare(cold,gid,reference)
                self.assertEqual(self.model.read_bytes(),saved)

    def test_unknown_type_and_missing_conformal_parent_preserve_model(self):
        before=self.model.read_bytes()
        for kind in ['NotAnInstalledGeometry','CONFORMAL']:
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='add',type=kind))
            self.assertEqual(self.model.read_bytes(),before)
