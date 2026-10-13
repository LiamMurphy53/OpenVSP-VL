"""Native cross-section activity, locking and cold persistence."""
import sys
import unittest
import test_native
from vsp_runtime import load
from native_preview import parameter_activity


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class SectionActivity(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_activity_matches_native_on_each_supported_section_owner(self):
        v=self.v
        for kind in ('WING','FUSELAGE','STACK','PROP'):
            with self.subTest(kind=kind):
                v.ClearVSPModel();gid=v.AddGeom(kind);surf=v.GetXSecSurf(gid,0)
                v.ChangeXSecShape(surf,1,v.XS_CIRCLE);v.ConvertXSecToEdit(gid,1);v.Update()
                xid=v.GetXSec(surf,1)
                for name,value in [('SymType',v.SYM_NONE),('CloseFlag',0),('CloseFlag',1),('SymType',v.SYM_RL),('G1_3',1)]:
                    v.SetParmValUpdate(v.GetXSecParm(xid,name),value)
                    ids=list(v.GetXSecParmIDs(xid));expected=parameter_activity(v,ids)
                    points=[[p.x(),p.y(),p.z()] for p in v.GetEditXSecCtrlVec(xid,True)]
                    v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
                    state,path=self.worker(dict(action='state'))
                    component=next(c for c in state['components'] if c['id']==gid)
                    section=next(s for s in component['sections'] if s['surface']==0 and s['index']==1)
                    self.assertEqual(section['controlPoints'],points)
                    self.assertEqual(section['pointActivity'],[[expected[v.GetXSecParm(xid,f'{axis}_{i}')] for axis in 'XYZ'] for i in range(len(points))])
                    self.assertEqual(section['fixedActivity'],[expected[v.GetXSecParm(xid,f'FixedU_{i}')] for i in range(len(points))])
                    self.assertEqual(section['smoothActivity'],[expected[v.GetXSecParm(xid,f'G1_{i}')] for i in range(len(points))])
                    for p in section['curveParameters']:self.assertEqual(p['active'],expected[p['id']])
                    for p in component['params']:
                        if p['id'] in expected:self.assertEqual(p['active'],expected[p['id']])
                    if name=='CloseFlag':self.assertEqual(section['pointActivity'][-1],[not bool(value)]*3)
                    self.assertEqual(self.model.read_bytes(),before);self.assertEqual(path.read_bytes(),before)

    def test_section_edit_keeps_native_constraints_and_activity_through_reload(self):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom('STACK');surf=v.GetXSecSurf(self.gid,0)
        v.ChangeXSecShape(surf,1,v.XS_CIRCLE);v.ConvertXSecToEdit(self.gid,1);v.Update();x=v.GetXSec(surf,1)
        v.SetParmValUpdate(v.GetXSecParm(x,'SymType'),v.SYM_RL);v.SetParmValUpdate(v.GetXSecParm(x,'G1_3'),1)
        v.WriteVSPFile(str(self.model),v.SET_ALL)
        p=v.GetEditXSecCtrlVec(x,True)[3];xyz=[p.x()+.04,p.y()+.03,p.z()]
        v.MoveEditXSecPnt(x,3,v.vec3d(*xyz));v.Update()
        expected=[[p.x(),p.y(),p.z()] for p in v.GetEditXSecCtrlVec(x,True)]
        state,path=self.worker(dict(action='mutate',operation='curve-point',geom=self.gid,index=1,point=3,xyz=xyz))
        section=state['components'][0]['sections'][1];self.assertEqual(section['controlPoints'],expected)
        self.assertFalse(section['pointActivity'][3][0]);self.assertTrue(section['pointActivity'][3][1])
        reopened,_=self.worker(dict(action='state'),path)
        self.assertEqual(reopened['components'][0]['sections'][1],section)

    def test_guided_smooth_and_arc_length_spacing_match_native_api(self):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom('STACK');surf=v.GetXSecSurf(self.gid,0)
        v.ChangeXSecShape(surf,1,v.XS_CIRCLE);v.ConvertXSecToEdit(self.gid,1);v.Update()
        x=v.GetXSec(surf,1);v.SetParmValUpdate(v.GetXSecParm(x,'SymType'),v.SYM_NONE)
        v.WriteVSPFile(str(self.model),v.SET_ALL);path=self.model
        requests=[dict(operation='curve-smooth',point=3,smooth=True),dict(operation='curve-point',point=2,xyz=[.32,-.44,0]),dict(operation='curve-fixed',point=3,fixed=True),dict(operation='curve-reparameterize'),dict(operation='curve-smooth',point=3,smooth=False)]
        for request in requests:
            # A fresh SDK model evaluates the same saved input for each transaction.
            v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();x=v.GetXSec(v.GetXSecSurf(self.gid,0),1)
            if request['operation']=='curve-smooth':v.SetParmValUpdate(v.GetXSecParm(x,'G1_3'),int(request['smooth']))
            elif request['operation']=='curve-point':v.MoveEditXSecPnt(x,2,v.vec3d(*request['xyz']))
            elif request['operation']=='curve-fixed':
                flags=list(v.GetEditXSecFixedUVec(x));flags[3]=True;v.SetEditXSecFixedUVec(x,flags)
            else:v.ReparameterizeEditXSec(x)
            v.Update();points=[[p.x(),p.y(),p.z()] for p in v.GetEditXSecCtrlVec(x,True)]
            u=list(v.GetEditXSecUVec(x));fixed=list(v.GetEditXSecFixedUVec(x))
            smooth=[bool(v.GetParmVal(v.GetXSecParm(x,f'G1_{i}'))) for i in range(len(points))]
            profile=[[p.x(),p.y(),p.z()] for p in [v.ComputeXSecPnt(x,i/100) for i in range(101)]]
            state,path=self.worker(dict(action='mutate',geom=self.gid,index=1,**request),path)
            section=state['components'][0]['sections'][1]
            for key,expected in [('controlPoints',points),('curveU',u),('fixedU',fixed),('smooth',smooth),('profile',profile)]:self.assertEqual(section[key],expected,request['operation']+' '+key)
            reopened,_=self.worker(dict(action='state'),path);self.assertEqual(reopened['components'][0]['sections'][1],section)

    def test_invalid_guided_smooth_inputs_preserve_native_file(self):
        v=self.v;state,path=self.worker(dict(action='mutate',operation='curve-convert',geom=self.gid,index=1))
        before=path.read_bytes()
        locked=next(i for i,active in enumerate(state['components'][0]['sections'][1]['smoothActivity']) if i%3==0 and not active)
        with self.assertRaisesRegex(ValueError,'locked by OpenVSP'):
            self.worker(dict(action='mutate',operation='curve-smooth',geom=self.gid,index=1,point=locked,smooth=True),path)
        self.assertEqual(path.read_bytes(),before)
        for extra in [dict(point=True,smooth=True),dict(point=1,smooth=True),dict(point=3,smooth='yes'),dict(point=-1,smooth=True),dict(point=10000,smooth=True)]:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='curve-smooth',geom=self.gid,index=1,**extra),path)
            self.assertEqual(path.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='curve-type',geom=self.gid,index=1,type='LINEAR'),path)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'cubic Bezier'):self.worker(dict(action='mutate',operation='curve-smooth',geom=self.gid,index=1,point=0,smooth=True),path)
        self.assertEqual(path.read_bytes(),before)
