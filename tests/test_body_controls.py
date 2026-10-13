"""Native body dimension drivers, section identity, persistence and study policy."""
import itertools
import sys
import unittest
import test_native
import native_body_controls
import native_preview
import native_study_worker
import native_worker


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class BodyControls(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def body(self,kind='FUSELAGE',shape=None):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom(kind)
        if shape is not None:v.ChangeXSecShape(v.GetXSecSurf(self.gid,0),1,shape)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return v.GetXSec(v.GetXSecSurf(self.gid,0),1)

    def compare(self,state):
        v=self.v;c=state['components'][0]
        for p in c['params']:self.assertAlmostEqual(p['value'],v.GetParmVal(p['id']),places=10,msg=p['name'])
        for s in c['surfaces']:
            u,w=v.GetUWTess01(self.gid,0)
            pts=v.CompVecPnt01(self.gid,s['index'],[a for a in u for _ in w],[b for _ in u for b in w])
            self.assertEqual(len(pts),len(s['points']))
            for a,b in zip(s['points'],pts):
                for x,y in zip(a,[b.x(),b.y(),b.z()]):self.assertAlmostEqual(x,y,places=10)

    def test_all_native_combinations_and_actual_dimension_ids(self):
        v=self.v
        for shape,circle in [(v.XS_ELLIPSE,False),(v.XS_CIRCLE,True)]:
            xid=self.body(shape=shape);accepted=[]
            for choice in ([list(c) for c in itertools.combinations(range(4),2)] if not circle else [[i] for i in range(2)]):
                v.SetDriverGroup(self.gid,1,*choice);native_worker.errors(v)
                self.assertEqual(list(v.GetDriverGroup(self.gid,1)),choice);accepted.append(choice)
            self.assertEqual(accepted,native_preview.body_driver_combinations(v,circle))
            names=['Circle_Diameter','Area'] if circle else ['Ellipse_Width','Area','Ellipse_Height','HWRatio']
            self.assertEqual(native_preview.body_driver_parameters(v,self.gid,0,1),[v.GetXSecParm(xid,name) for name in names])

    def test_each_driver_edit_matches_native_geometry_and_reopening(self):
        v=self.v
        for kind in ('FUSELAGE','STACK'):
            self.body(kind);source=self.model.read_bytes()
            for choices in native_preview.body_driver_combinations(v):
                with self.subTest(kind=kind,choices=choices):
                    self.model.write_bytes(source);v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
                    state,saved=self.worker(dict(action='mutate',operation='drivers',geom=self.gid,surface=0,index=1,drivers=choices))
                    v.SetDriverGroup(self.gid,1,*choices);v.Update();v.Update();v.WriteVSPFile(str(self.path/'direct.vsp3'),v.SET_ALL)
                    v.ClearVSPModel();v.ReadVSPFile(str(self.path/'direct.vsp3'));v.Update()
                    s=state['components'][0]['sections'][1];pid=s['bodyDriverControls'][choices[0]]['parameter']
                    value={0:4.,1:9.,2:3.5,3:1.5}[choices[0]]
                    state,edited=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),saved)
                    v.SetParmValUpdate(pid,value);v.Update()
                    self.compare(state)
                    readonly={p['id']:p.get('displayReadOnly',False) for p in state['components'][0]['params']}
                    self.assertEqual([d['value'] for d in s['bodyDriverControls'] if not readonly[d['parameter']]],choices)
                    reopened,_=self.worker(dict(action='state'),edited)
                    self.assertEqual(reopened['components'][0]['sections'][1]['bodyDrivers'],choices)

    def test_circle_area_and_shape_change_recover_native_drivers(self):
        v=self.v;xid=self.body(shape=v.XS_CIRCLE)
        state,saved=self.worker(dict(action='mutate',operation='drivers',geom=self.gid,index=1,drivers=[1]))
        area=v.GetXSecParm(xid,'Area')
        state,edited=self.worker(dict(action='mutate',operation='parameter',id=area,value=12.),saved)
        v.SetDriverGroup(self.gid,1,1);v.Update();v.SetParmValUpdate(area,12.);v.Update();self.compare(state)
        state,_=self.worker(dict(action='mutate',operation='shape',geom=self.gid,index=1,shape=v.XS_ELLIPSE),edited)
        self.assertEqual(len(state['components'][0]['sections'][1]['bodyDrivers']),2)

    def test_invalid_and_calculated_edits_and_studies_preserve_source(self):
        v=self.v;xid=self.body();before=self.model.read_bytes()
        for choices,index in [([0,0],1),([0,4],1),([True,2],1),([0],1),([0,2],0)]:
            with self.subTest(choices=choices,index=index),self.assertRaises(ValueError):
                self.worker(dict(action='mutate',operation='drivers',geom=self.gid,index=index,drivers=choices))
        area=v.GetXSecParm(xid,'Area')
        with self.assertRaisesRegex(ValueError,'calculates'):
            self.worker(dict(action='mutate',operation='parameter',id=area,value=10.))
        point=v.GetXSec(v.GetXSecSurf(self.gid,0),0)
        for name in ('Area','HWRatio'):
            with self.subTest(point=name),self.assertRaisesRegex(ValueError,'Point profile'):
                self.worker(dict(action='mutate',operation='parameter',id=v.GetXSecParm(point,name),value=2.))
        schema=native_study_worker.schema(v,native_worker.parameter)
        self.assertIs(next(p for p in schema['parameters'] if p['id']==area)['editable'],False)
        req=dict(stages=[dict(name='CompGeom',inputs=[])],axes=[dict(kind='parameter',id=area,values=[3.])])
        with self.assertRaisesRegex(ValueError,'driver'):
            native_study_worker.validate(v,req,native_worker.parameter,native_worker.analysis_schema,native_worker.set_inputs)
        with self.assertRaisesRegex(ValueError,'driver'):
            native_study_worker.prepare(v,dict(parameters=[dict(id=area,value=3.)]),self.path/'case.vsp3',native_worker.errors)
        self.assertEqual(before,self.model.read_bytes())

    def test_airfoil_drivers_are_fixed_and_thickness_remains_dimensionless(self):
        v=self.v;xid=self.body(shape=v.XS_FOUR_SERIES)
        state,_=self.worker(dict(action='state'));c=state['components'][0];s=c['sections'][1]
        self.assertIs(s['bodyDriversFixed'],True);self.assertEqual(s['bodyDriverCombinations'],[[0,2]])
        pid=v.GetXSecParm(xid,'ThickChord');p=next(p for p in c['params'] if p['id']==pid)
        self.assertNotIn('dimension',p);self.assertFalse(p['displayReadOnly'])
        with self.assertRaisesRegex(ValueError,'fixes airfoil'):
            self.worker(dict(action='mutate',operation='drivers',geom=self.gid,index=1,drivers=[1,3]))
        state,_=self.worker(dict(action='mutate',operation='parameter',id=pid,value=.2))
        v.SetParmValUpdate(pid,.2);v.Update();self.compare(state)
