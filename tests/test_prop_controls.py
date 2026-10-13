"""Blade pitch, native curve evaluation, activity and study protection."""
import sys
import unittest
import test_native
import native_preview
import native_worker
import native_study_worker
import native_prop_controls


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the installed native runtime.')
class PropControls(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom('PROP');v.SetParmValUpdate(self.gid,'Diameter','Design',6.)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def compare(self,state):
        v=self.v;c=state['components'][0];v.GetNumUnsteadyGroups();v.GetNumActuatorDisks()
        curve_groups={item[2] for item in native_prop_controls.CURVES.values()}
        ids=list(v.GetGeomParmIDs(self.gid))
        for p in c['params']:
            if v.ValidParm(p['id']):pid=p['id']
            else:
                # Inserting/deleting points allocates different IDs in separate
                # native processes. Compare original curve group/name identity.
                self.assertIn(p['rawGroup'],curve_groups)
                candidates=[pid for pid in ids if v.GetParmGroupName(pid)==p['rawGroup'] and v.GetParmName(pid)==p['name']]
                self.assertEqual(len(candidates),1);pid=candidates[0]
            self.assertAlmostEqual(p['value'],v.GetParmVal(pid),places=10,msg=p['name'])
        self.assertEqual({p['id'] for p in c['params'] if p['rawGroup'] not in curve_groups},{pid for pid in ids if v.GetParmGroupName(pid) not in curve_groups})
        self.assertEqual(len(c['params']),len(ids))
        for surface in c['surfaces']:
            u,w=v.GetUWTess01(self.gid,surface['index']%v.GetNumMainSurfs(self.gid))
            pts=v.CompVecPnt01(self.gid,surface['index'],[a for a in u for _ in w],[b for _ in u for b in w])
            self.assertEqual(len(pts),len(surface['points']))
            for p,q in zip(pts,surface['points']):
                for a,b in zip([p.x(),p.y(),p.z()],q):self.assertAlmostEqual(a,b,places=10)

    def test_all_nine_curve_samples_match_independent_blade_element_results(self):
        v=self.v;self.fixture()
        # BEM samples come from the independent SDK analysis path, not this bridge.
        names={'PROP_CLI':'CLi','PROP_THICK':'Thick'}
        for typ in (v.LINEAR,v.PCHIP,v.CEDIT):
            for curve_name in native_prop_controls.CURVES:v.PCurveConvertTo(self.gid,getattr(v,curve_name),typ)
            v.Update();v.SetAnalysisInputDefaults('BladeElement');v.SetStringAnalysisInput('BladeElement','PropID',[self.gid]);rid=v.ExecAnalysis('BladeElement')
            radii=list(v.GetDoubleResults(rid,'Radius'));self.assertGreater(len(radii),2)
            for curve_name in native_prop_controls.CURVES:
                with self.subTest(type=typ,curve=curve_name):
                    result_name=names.get(curve_name,curve_name.removeprefix('PROP_').title())
                    actual=native_preview.prop_curve_values(v,self.gid,getattr(v,curve_name),radii)
                    self.assertEqual(actual,list(v.GetDoubleResults(rid,result_name)))
                    curve=dict(name=curve_name,index=getattr(v,curve_name),stations=list(v.PCurveGetTVec(self.gid,getattr(v,curve_name))))
                    details=native_prop_controls.curve_details(v,self.gid,curve)
                    self.assertEqual(len(details['sampleValues']),101)
                    self.assertEqual(details['sampleValues'][0],actual[0]);self.assertAlmostEqual(details['sampleValues'][-1],actual[-1],places=10)

    def test_pitch_drivers_and_arrangement_match_native_and_reopen(self):
        v=self.v;self.fixture();saved=self.model
        for name,value in [('UseBeta34Flag',0),('Feather',9.),('Rotate',17.),('Precone',6.),('ReverseFlag',1),('UseBeta34Flag',1),('Beta34',27.),('CylindricalSectionsFlag',1),('PropMode',1),('PropMode',2),('PropMode',0)]:
            with self.subTest(name=name,value=value):
                v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update();pid=v.FindParm(self.gid,name,'Design')
                state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),saved)
                v.SetParmValUpdate(pid,value);v.Update();self.compare(state)
                by_name={p['name']:p for p in state['components'][0]['params'] if p['rawGroup']=='Design'}
                self.assertEqual(by_name['Beta34']['active'],bool(by_name['UseBeta34Flag']['value']))
                self.assertEqual(by_name['Feather']['active'],not bool(by_name['UseBeta34Flag']['value']))
                self.assertTrue(by_name['AF']['displayReadOnly']);self.assertEqual(by_name['Feather']['dimension'],'angle')
                v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update()
                reopened,_=self.worker(dict(action='state'),saved);self.compare(reopened)

    def test_curve_edit_station_and_interpolation_match_complete_native_geometry(self):
        v=self.v;self.fixture();saved=self.model
        requests=[dict(operation='prop-curve-type',curve='PROP_CHORD',type='PCHIP'),
                  dict(operation='prop-curve-set',curve='PROP_CHORD',stations=[.2,.45,.7,1.],values=[.08,.19,.15,.04]),
                  dict(operation='prop-curve-split',curve='PROP_CHORD',station=.6),
                  dict(operation='prop-curve-delete',curve='PROP_CHORD',index=2),
                  dict(operation='prop-curve-type',curve='PROP_TWIST',type='LINEAR')]
        for req in requests:
            v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update();state,saved=self.worker(dict(req,action='mutate',geom=self.gid),saved)
            curve=getattr(v,req['curve']);op=req['operation']
            if op=='prop-curve-type':v.PCurveConvertTo(self.gid,curve,getattr(v,req['type']))
            elif op=='prop-curve-set':v.SetPCurve(self.gid,curve,req['stations'],req['values'],v.PCurveGetType(self.gid,curve))
            elif op=='prop-curve-split':v.PCurveSplit(self.gid,curve,req['station'])
            else:v.PCurveDeletePt(self.gid,curve,req['index'])
            v.Update();self.compare(state)
        v.ClearVSPModel();v.ReadVSPFile(str(saved));v.Update();xid=v.GetXSec(v.GetXSecSurf(self.gid,0),1);pid=v.GetXSecParm(xid,'RadiusFrac')
        state,saved=self.worker(dict(action='mutate',operation='parameter',id=pid,value=.5),saved)
        v.SetParmValUpdate(pid,.5);v.Update();self.compare(state)
        self.assertTrue(all(c['pointControls'][0]['stationActive'] is False for c in state['tools']['propellers'][0]['curves']))

    def test_calculated_fields_protected_and_prop_attachment_extras_preserved(self):
        v=self.v;self.fixture();original=self.model.read_bytes();xid=v.GetXSec(v.GetXSecSurf(self.gid,0),1)
        pids=[v.FindParm(self.gid,name,'Design') for name in ('AF','Solidity','Chord','Feather')]
        pids.extend(v.FindParm(self.gid,name,'PropGeom') for name in ('SmallPanelW','MaxGrowth'))
        pids+=[v.GetXSecParm(xid,name) for name in ('Chord','ThickChord','IdealCl','RefLength','Area','HWRatio')]
        for pid in pids:
            with self.subTest(name=v.GetParmName(pid)),self.assertRaisesRegex(ValueError,'Calculated|native section'):
                self.worker(dict(action='mutate',operation='parameter',id=pid,value=.3))
        schema=native_study_worker.schema(v,native_worker.parameter)
        for pid in pids:self.assertIs(next(p for p in schema['parameters'] if p['id']==pid)['editable'],False)
        pid=v.FindParm(self.gid,'Feather','Design')
        with self.assertRaisesRegex(ValueError,'Calculated'):
            native_study_worker.prepare(v,dict(parameters=[dict(id=pid,value=3.)]),self.path/'case.vsp3',native_worker.errors)
        self.assertEqual(self.model.read_bytes(),original);self.assertFalse((self.path/'case.vsp3').exists())
        state,_=self.worker(dict(action='state'));c=state['components'][0]
        attachment=set(c['attachment']['parameters'])
        for name in ('TipMarkerScale','TipMarkerScaleFlag'):
            pid=v.FindParm(self.gid,name,'Attach');self.assertIn(pid,{p['id'] for p in c['params']});self.assertNotIn(pid,attachment)

    def test_curve_query_invalid_arguments_leave_native_geometry_unchanged(self):
        v=self.v;self.fixture();before=self.model.read_bytes()
        for gid,curve,radii in [(self.gid,99,[.3]),(self.gid,v.PROP_CHORD,[float('nan')]),(self.gid,v.PROP_CHORD,[-1]),('missing',v.PROP_CHORD,[.3])]:
            with self.assertRaises(ValueError):native_preview.prop_curve_values(v,gid,curve,radii)
        self.assertEqual(self.model.read_bytes(),before)


if __name__=='__main__':unittest.main()
