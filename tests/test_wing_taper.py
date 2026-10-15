"""Compound whole-wing taper retains area/spans and matches original SDK geometry."""
import sys
import unittest
import test_native


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use native Python 3.11.')
class WingTaper(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_multisection_taper_matches_native_recipe_and_reopens(self):
        v=self.v;g=self.gid
        v.InsertXSec(g,1,v.XS_FOUR_SERIES);v.InsertXSec(g,2,v.XS_FOUR_SERIES)
        surf=v.GetXSecSurf(g,0)
        for i,(span,root,tip) in enumerate([(2,6,5),(2,5,3),(4,3,2)],1):
            v.SetDriverGroup(g,i,v.SPAN_WSECT_DRIVER,v.ROOTC_WSECT_DRIVER,v.TIPC_WSECT_DRIVER)
            x=v.GetXSec(surf,i)
            for name,value in [('Span',span),('Root_Chord',root),('Tip_Chord',tip),('Dihedral',i*7),('Twist',i*2),('Sweep',i*4)]:v.SetParmValUpdate(v.GetXSecParm(x,name),value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        area=v.GetParmVal(g,'TotalArea','WingGeom');projected=v.GetParmVal(g,'TotalProjectedSpan','WingGeom')
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();surf=v.GetXSecSurf(g,0)
        area=v.GetParmVal(g,'TotalArea','WingGeom');projected=v.GetParmVal(g,'TotalProjectedSpan','WingGeom')
        mid=v.GetParmVal(v.GetXSecParm(v.GetXSec(surf,2),'Tip_Chord'))
        # DecodeXml changes this middle chord by one ULP; retain the original
        # engine's loaded input instead of substituting the pre-save literal.
        # Existing chords 6,5,3,2 at spans 0,2,4,8. Doubling overall
        # taper gives station chords 6,6.25,4.5,4 before native area scaling.
        for i in range(1,4):v.SetDriverGroup(g,i,v.SPAN_WSECT_DRIVER,v.ROOTC_WSECT_DRIVER,v.TIPC_WSECT_DRIVER)
        for i,(root,tip) in enumerate([(6,6.25),(6.25,mid*1.5),(mid*1.5,4)],1):
            x=v.GetXSec(surf,i)
            v.SetParmValUpdate(v.GetXSecParm(x,'Root_Chord'),root)
            v.SetParmValUpdate(v.GetXSecParm(x,'Tip_Chord'),tip)
        v.Update();v.SetParmValUpdate(g,'TotalChord','WingGeom',v.GetParmVal(g,'TotalChord','WingGeom')*area/v.GetParmVal(g,'TotalArea','WingGeom'));v.Update()
        ref=self.path/'reference.vsp3';v.WriteVSPFile(str(ref),v.SET_ALL);expected,_=self.worker(dict(action='state'),ref)
        state,path=self.worker(dict(action='mutate',operation='design-assist',geom=g,control='wing-taper',value=2/3))
        c=state['components'][0];e=expected['components'][0]
        self.assertAlmostEqual(c['designAssist']['taper'],2/3)
        # The direct native reference and compound recipe produce complete
        # matching surfaces and parameter values, not only a displayed ratio.
        expected_values={p['id']:p['value'] for p in e['params']}
        self.assertEqual({p['id'] for p in c['params']},set(expected_values))
        differences=[(p['name'],p['rawGroup'],p['value'],expected_values.get(p['id'])) for p in c['params'] if p['value']!=expected_values.get(p['id'])]
        self.assertEqual(differences,[],repr(differences))
        self.assertEqual(c['surfaces'],e['surfaces'])
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(c['surfaces'],cold['components'][0]['surfaces'])
        values={p['name']:p['value'] for p in c['params'] if p['rawGroup']=='WingGeom'}
        self.assertAlmostEqual(values['TotalArea'],area);self.assertAlmostEqual(values['TotalProjectedSpan'],projected)

    def test_locked_area_span_allow_taper_but_root_chord_lock_rejects_atomically(self):
        v=self.v;g=self.gid
        area=v.FindParm(g,'TotalArea','WingGeom');span=v.FindParm(g,'TotalSpan','WingGeom')
        state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[area,span],locked=True))
        state,path=self.worker(dict(action='mutate',operation='design-assist',geom=g,control='wing-taper',value=.4),path)
        surf=v.GetXSecSurf(g,0);root=v.GetXSecParm(v.GetXSec(surf,1),'Root_Chord')
        state,path=self.worker(dict(action='mutate',operation='property-lock',parameters=[root],locked=True),path)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'locked'):
            self.worker(dict(action='mutate',operation='design-assist',geom=g,control='wing-taper',value=.7),path)
        self.assertEqual(path.read_bytes(),before)

    def test_invalid_taper_and_native_limits_preserve_aircraft(self):
        for target in (-1,1e20,True):
            with self.subTest(target=target):
                before=self.model.read_bytes();folders=set(self.path.glob('*/aircraft.vsp3'))
                with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='design-assist',geom=self.gid,control='wing-taper',value=target))
                self.assertEqual(self.model.read_bytes(),before)
                self.assertTrue(all(p.read_bytes()==before for p in set(self.path.glob('*/aircraft.vsp3'))-folders))

    def test_pointed_tip_can_be_created_and_reopened_to_nonzero_taper(self):
        state,path=self.worker(dict(action='mutate',operation='design-assist',geom=self.gid,control='wing-taper',value=0))
        self.assertEqual(state['components'][0]['designAssist']['taper'],0)
        self.assertTrue(state['components'][0]['designAssist']['taperAvailable'])
        state,path=self.worker(dict(action='mutate',operation='design-assist',geom=self.gid,control='wing-taper',value=.5),path)
        self.assertAlmostEqual(state['components'][0]['designAssist']['taper'],.5)
        cold,_=self.worker(dict(action='state'),path)
        self.assertEqual(state['components'][0]['surfaces'],cold['components'][0]['surfaces'])

    def test_pro_drivers_and_asymmetric_reverse_taper_use_native_span_chord_drivers(self):
        v=self.v;g=self.gid
        for symmetry in (v.SYM_XZ,0):
            with self.subTest(symmetry=symmetry):
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
                v.SetParmValUpdate(g,'Sym_Planar_Flag','Sym',symmetry)
                v.SetDriverGroup(g,1,v.AR_WSECT_DRIVER,v.AREA_WSECT_DRIVER,v.TAPER_WSECT_DRIVER)
                v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
                area=v.GetParmVal(g,'TotalArea','WingGeom');span=v.GetParmVal(g,'TotalSpan','WingGeom')
                state,path=self.worker(dict(action='mutate',operation='design-assist',geom=g,control='wing-taper',value=1.5))
                c=state['components'][0];values={p['name']:p['value'] for p in c['params'] if p['rawGroup']=='WingGeom'}
                self.assertAlmostEqual(c['designAssist']['taper'],1.5)
                self.assertAlmostEqual(values['TotalArea'],area);self.assertAlmostEqual(values['TotalSpan'],span)
                v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
                self.assertEqual(list(v.GetDriverGroup(g,1)),[v.SPAN_WSECT_DRIVER,v.ROOTC_WSECT_DRIVER,v.TIPC_WSECT_DRIVER])
                self.assertEqual(v.GetParmVal(g,'Sym_Planar_Flag','Sym'),symmetry)
