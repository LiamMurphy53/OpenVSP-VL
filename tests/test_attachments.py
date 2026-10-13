"""Native attachment transforms, coordinate bases, guarded edits and persistence."""
import math
import sys
import unittest
import test_native
import native_attachments
import native_preview
import native_study_worker
import native_worker


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the installed native Python runtime.')
class Attachments(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def parm(self,name,group='Attach',geom=None):
        return self.v.FindParm(geom or self.child,name,group)

    def fixture(self,kind='FUSELAGE',mode=0):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom(kind);self.child=v.AddGeom('POD',self.gid)
        for name,value in [('X_Rel_Location',3.),('Y_Rel_Location',-2.),('Z_Rel_Location',1.),
                           ('X_Rel_Rotation',7.),('Y_Rel_Rotation',-11.),('Z_Rel_Rotation',19.)]:
            v.SetParmValUpdate(self.parm(name,'XForm',self.gid),value)
        for name,value in [('Trans_Attach_Flag',mode),('Rots_Attach_Flag',0),('U_Attach_Location',.37),
                           ('V_Attach_Location',.28),('R_Attach_Location',.41),('S_Attach_Location',.36),
                           ('T_Attach_Location',.62),('L_Attach_Location',.46),('M_Attach_Location',.29),
                           ('N_Attach_Location',.64),('Eta_Attach_Location',.43)]:
            v.SetParmValUpdate(self.parm(name),value)
        for name,value in [('X_Rel_Location',.7),('Y_Rel_Location',-.4),('Z_Rel_Rotation',8.)]:
            v.SetParmValUpdate(self.parm(name,'XForm'),value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        # Compare from the same saved baseline each worker loads.
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()

    def compare(self,state):
        v=self.v;v.GetNumUnsteadyGroups();v.GetNumActuatorDisks()
        for c in state['components']:
            self.assertEqual({p['id'] for p in c['params']},set(v.GetGeomParmIDs(c['id'])))
            for p in c['params']:self.assertAlmostEqual(p['value'],v.GetParmVal(p['id']),places=10,msg=c['name']+'/'+p['name'])
            for surface in c['surfaces']:
                u,w=v.GetUWTess01(c['id'],surface['index']%max(1,v.GetNumMainSurfs(c['id'])))
                points=v.CompVecPnt01(c['id'],surface['index'],[a for a in u for _ in w],[b for _ in u for b in w])
                self.assertEqual(len(points),len(surface['points']))
                for p,q in zip(points,surface['points']):
                    for a,b in zip([p.x(),p.y(),p.z()],q):self.assertAlmostEqual(a,b,places=10)

    def origin(self,mode):
        v=self.v;value=lambda name:v.GetParmVal(self.parm(name))
        if mode==0:return [0.,0.,0.]
        if mode==1:return [v.GetParmVal(self.parm(axis+'_Location','XForm',self.gid)) for axis in 'XYZ']
        if mode==2:p=v.CompPnt01(self.gid,0,value('U_Attach_Location'),value('V_Attach_Location'))
        elif mode==3:p=v.CompPntRST(self.gid,0,*[value(axis+'_Attach_Location') for axis in 'RST'])
        else:
            l=value('L_Attach_Location')
            if mode==5:
                l=value('Eta_Attach_Location')
                if v.GetGeomTypeName(self.gid).upper()=='WING':
                    r=v.ConvertEtatoU(self.gid,l)/v.GetParmUpperLimit(self.parm('U_Attach_Location0N'))
                    l=v.ConvertRtoL(self.gid,0,r)
            rst=v.ConvertLMNtoRST(self.gid,0,l,value('M_Attach_Location'),value('N_Attach_Location'))
            p=v.CompPntRST(self.gid,0,*rst)
        return [p.x(),p.y(),p.z()]

    def test_all_six_references_on_four_surface_parents_match_native(self):
        v=self.v
        for kind in ('WING','FUSELAGE','STACK','PROP'):
            for mode in range(6):
                with self.subTest(kind=kind,mode=mode):
                    self.fixture(kind,mode);pid=self.parm('Rots_Attach_Flag')
                    state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=mode))
                    v.SetParmValUpdate(pid,mode);v.Update();self.compare(state)
                    child=next(c for c in state['components'] if c['id']==self.child);frame=child['attachment']['frame']
                    for a,b in zip(frame['points'][0],self.origin(mode)):self.assertAlmostEqual(a,b,places=10)
                    for end in frame['points'][1:]:self.assertAlmostEqual(math.dist(frame['points'][0],end),1.,places=10)
                    for row in range(3):self.assertEqual(frame['matrix'][12+row],frame['points'][0][row])
                    self.assertEqual(child['attachment']['parent'],self.gid)
                    v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update();self.compare(state)

    def test_mixed_references_and_native_coordinate_basis_edits(self):
        v=self.v;self.fixture(mode=2);saved=self.model
        requests=[('Rots_Attach_Flag',3),('U_01',0),('U_Attach_Location0N',1.2),
                  ('R_01',0),('R_Attach_Location0N',1.6),('Trans_Attach_Flag',4),
                  ('L_01',0),('L_Attach_Location0Len',4.)]
        for name,value in requests:
            with self.subTest(name=name):
                v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update();pid=self.parm(name)
                state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),saved)
                v.SetParmValUpdate(pid,value);v.Update();self.compare(state)
                c=next(c for c in state['components'] if c['id']==self.child)
                for a,b in zip(c['attachment']['frame']['points'][0],self.origin(int(v.GetParmVal(self.parm('Trans_Attach_Flag'))))):self.assertAlmostEqual(a,b,places=10)
        c=next(c for c in state['components'] if c['id']==self.child)
        self.assertEqual([g['title'] for g in c['attachment']['groups'] if g['enabled']],['Section volume coordinates','Uniform volume coordinates','Cross-volume coordinates'])
        self.assertEqual(next(p for p in c['params'] if p['id']==self.parm('L_Attach_Location0Len'))['dimension'],'length')

    def test_calculated_unused_and_absolute_coordinates_guarded_in_edits_and_studies(self):
        v=self.v;self.fixture(mode=2);original=self.model.read_bytes()
        for name,group in [('U_Attach_Location0N','Attach'),('R_Attach_Location','Attach'),('L_01','Attach'),('X_Location','XForm')]:
            with self.subTest(name=name):
                pid=self.parm(name,group)
                with self.assertRaisesRegex(ValueError,'Calculated|Select this attachment'):
                    self.worker(dict(action='mutate',operation='parameter',id=pid,value=.5))
                schema=native_study_worker.schema(v,native_worker.parameter)
                self.assertFalse(next(p for p in schema['parameters'] if p['id']==pid)['editable'])
                with self.assertRaises(ValueError):native_study_worker.prepare(v,dict(parameters=[dict(id=pid,value=.5)]),self.path/'case.vsp3',native_worker.errors)
                self.assertFalse((self.path/'case.vsp3').exists())
        self.assertEqual(self.model.read_bytes(),original)
        pid=self.parm('U_Attach_Location')
        schema=native_study_worker.schema(v,native_worker.parameter)
        self.assertTrue(next(p for p in schema['parameters'] if p['id']==pid).get('editable',True))
        record=native_study_worker.prepare(v,dict(parameters=[dict(id=pid,value=.6)]),self.path/'case.vsp3',native_worker.errors)
        self.assertEqual(record['parameters'][0]['effective'],.6)

    def test_joint_and_blank_parents_and_reparent_cycle_guard(self):
        v=self.v
        for kind in ('BLANK','HINGE'):
            with self.subTest(kind=kind):
                self.fixture(kind,2);state,saved=self.worker(dict(action='state'));self.compare(state)
                c=next(c for c in state['components'] if c['id']==self.child)
                self.assertFalse(c['attachment']['parentHasSurface']);self.assertEqual(c['attachment']['isJoint'],kind=='HINGE')
                if kind=='HINGE':
                    for name in ('Trans_Attach_Flag','Rots_Attach_Flag','U_Attach_Location'):
                        self.assertFalse(next(p for p in c['params'] if p['id']==self.parm(name))['active'])
                        with self.assertRaisesRegex(ValueError,'locked'):self.worker(dict(action='mutate',operation='parameter',id=self.parm(name),value=1))
                else:
                    for a,b in zip(c['attachment']['frame']['points'][0],self.origin(1)):self.assertAlmostEqual(a,b,places=10)
                with self.assertRaisesRegex(ValueError,'descendant'):self.worker(dict(action='mutate',operation='reparent',geom=self.gid,parent=self.child))
                state,saved=self.worker(dict(action='mutate',operation='reparent',geom=self.child,parent=''))
                v.SetGeomParent(self.child,v.GetVehicleID());v.Update();self.compare(state)
                self.assertEqual(next(c for c in state['components'] if c['id']==self.child)['attachment']['parent'],'NONE')

    def test_absolute_placement_preserved_after_reference_change(self):
        v=self.v;self.fixture(mode=1);pid=self.parm('Abs_Or_Relitive_flag','XForm')
        v.SetParmValUpdate(pid,v.ABS);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        original=[v.GetParmVal(self.parm(axis+'_Location','XForm')) for axis in 'XYZ']
        pid=self.parm('Trans_Attach_Flag');state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=2))
        v.SetParmValUpdate(pid,2);v.Update();self.compare(state)
        self.assertEqual([v.GetParmVal(self.parm(axis+'_Location','XForm')) for axis in 'XYZ'],original)
        c=next(c for c in state['components'] if c['id']==self.child)
        self.assertFalse(next(p for p in c['params'] if p['id']==self.parm('X_Rel_Location','XForm'))['active'])


if __name__=='__main__':unittest.main()
