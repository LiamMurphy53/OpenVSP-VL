"""Selected profile controls bind original section IDs and geometry."""
import sys
import unittest
import test_native

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class ProfileShapeFields(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_selected_profile_ids_limits_edit_and_reopen_match_sdk(self):
        v=self.v
        for kind,name,new_value in [('WING','ThickChord',.15),('FUSELAGE','Ellipse_Width',2.75)]:
            with self.subTest(kind=kind):
                v.ClearVSPModel();gid=v.AddGeom(kind);v.Update()
                surf=v.GetXSecSurf(gid,0);xid=v.GetXSec(surf,1)
                v.WriteVSPFile(str(self.model),v.SET_ALL)
                before,_=self.worker({'action':'state'})
                component=before['components'][0];section=next(s for s in component['sections'] if s['surface']==0 and s['index']==1)
                fields=section['profileControls']['shapeFields'];by_id={p['id']:p for p in component['params']}
                native_ids=set(v.GetXSecParmIDs(xid));self.assertTrue(fields);self.assertTrue(set(fields)<=native_ids)
                for pid in fields:
                    p=by_id[pid];self.assertEqual(p['value'],v.GetParmVal(pid));self.assertEqual(p['min'],v.GetParmLowerLimit(pid));self.assertEqual(p['max'],v.GetParmUpperLimit(pid))
                pid=next(pid for pid in fields if by_id[pid]['name']==name)
                self.assertTrue(by_id[pid]['active']);self.assertFalse(by_id[pid].get('displayReadOnly',False))
                for other in component['sections']:
                    if other['id']!=xid:self.assertNotIn(pid,other.get('profileControls',{}).get('shapeFields',[]))
                v.SetParmValUpdate(pid,new_value)
                expected={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(gid)}
                def surfaces():
                    result=[]
                    for i in range(v.GetTotalNumSurfs(gid)):
                        u,w=v.GetUWTess01(gid,i%v.GetNumMainSurfs(gid));points=v.CompVecPnt01(gid,i,[a for a in u for _ in w],[b for _ in u for b in w])
                        result.append(dict(index=i,rows=len(u),cols=len(w),points=[[p.x(),p.y(),p.z()] for p in points]))
                    return result
                expected_surfaces=surfaces()
                edited,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=new_value))
                reopened,_=self.worker({'action':'state'},path)
                for state in [edited,reopened]:
                    c=state['components'][0];self.assertEqual({p['id']:p['value'] for p in c['params']},expected);self.assertEqual(c['surfaces'],expected_surfaces)

    def test_fraction_and_limited_integer_slider_values_match_native(self):
        v=self.v
        for name,value in [('Tess_W',38),('XSecImageW',.73)]:
            with self.subTest(name=name):
                v.ClearVSPModel();gid=v.AddGeom('WING');v.Update()
                pid=next(p for p in v.GetGeomParmIDs(gid) if v.GetParmName(p)==name)
                self.assertIn(v.GetParmType(pid),(v.PARM_FRACTION_TYPE,v.PARM_LIMITED_INT_TYPE))
                v.WriteVSPFile(str(self.model),v.SET_ALL)
                v.SetParmValUpdate(pid,value)
                expected={p:v.GetParmVal(p) for p in v.GetGeomParmIDs(gid)}
                edited,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value))
                reopened,_=self.worker(dict(action='state'),path)
                for state in [edited,reopened]:
                    self.assertEqual({p['id']:p['value'] for p in state['components'][0]['params']},expected)
