"""Loaded BOR profiles must match a correctly parented public-SDK curve."""
import sys
import unittest
import test_chevrons
import native_profile_controls
import native_preview


@unittest.skipUnless(sys.version_info[:2] == (3, 11), 'Use the matching native runtime.')
class BORProfileLoading(unittest.TestCase):
    setUpClass = test_chevrons.Chevrons.__dict__['setUpClass']
    setUp = test_chevrons.Chevrons.setUp
    tearDown = test_chevrons.Chevrons.tearDown
    worker = test_chevrons.Chevrons.worker
    fixture = test_chevrons.Chevrons.fixture
    parm = test_chevrons.Chevrons.parm
    fresh_bor = test_chevrons.Chevrons.fresh_bor
    compare_bor = test_chevrons.Chevrons.compare_bor

    def saved_circle(self, values):
        self.fixture('BODYOFREVOLUTION')
        for group, name, value in values:
            self.v.SetParmValUpdate(self.parm(name, group), value)
        self.v.Update()
        self.v.WriteVSPFile(str(self.model), self.v.SET_ALL)
        return self.model

    def test_default_circle_modifiers_reopen_with_complete_native_geometry(self):
        configurations = [
            [('XSecCurve', 'Circle_Diameter', 2.3)],
            [('XSecCurve', name, value) for name, value in
             [('Theta', 7.), ('Scale', 1.08), ('DeltaX', .03), ('DeltaY', -.02), ('ShiftLE', .08)]],
            [('Close', name, value) for name, value in
             [('LE_Close_Type', 1), ('LE_Close_Thick', .03),
              ('TE_Close_Type', 3), ('TE_Close_Thick', .015)]],
            [('Trim', name, value) for name, value in
             [('LE_Trim_Type', 1), ('LE_Trim_X', .03),
              ('TE_Trim_Type', 2), ('TE_Trim_Thick', .04)]],
        ]
        for values in configurations:
            with self.subTest(values=values):
                path = self.saved_circle(values)
                source = path.read_bytes()
                expected = self.fresh_bor(path)
                state, reopened = self.worker(dict(action='state'), path)
                self.compare_bor(state, expected)
                self.assertEqual(path.read_bytes(), source)
                self.assertEqual(reopened.read_bytes(), source)

    def test_circle_edit_and_prepared_study_preserve_original_ids(self):
        path = self.saved_circle([('XSecCurve', 'DeltaY', .06),
                                  ('Close', 'TE_Close_Type', 3), ('Close', 'TE_Close_Thick', .02)])
        pid = self.parm('Scale', 'XSecCurve')
        expected = self.fresh_bor(path, pid, 1.2)
        state, saved = self.worker(dict(action='mutate', operation='parameter', id=pid, value=1.2), path)
        self.compare_bor(state, expected)
        reopened, _ = self.worker(dict(action='state'), saved)
        self.compare_bor(reopened, self.fresh_bor(saved))
        prepared, target = self.worker(dict(action='study-model', parameters=[dict(id=pid, value=1.2)]), path)
        state, _ = self.worker(dict(action='state'), target)
        self.assertEqual(prepared['parameters'][0]['effective'], 1.2)
        # Compare serialized cases with native cold loads, including their
        # evaluated outputs, rather than pre-serialization snapshots.
        self.compare_bor(state, self.fresh_bor(target))

    def test_saved_native_crashing_flap_is_rejected_without_changing_aircraft(self):
        self.fixture('BODYOFREVOLUTION')
        # Set without evaluation: this valid native parameter combination
        # crashes when the correctly parented circular curve is evaluated.
        self.v.SetParmVal(self.parm('TE_Flap_Type', 'Flap'), self.v.FLAP_PLAIN)
        self.v.WriteVSPFile(str(self.model), self.v.SET_ALL)
        source=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError, 'saved circular.*flap'):
            self.worker(dict(action='state'))
        self.assertEqual(self.model.read_bytes(), source)

    def test_correct_native_parent_is_unchanged_and_geometry_parameter_is_rejected(self):
        self.fixture('BODYOFREVOLUTION')
        before={p:self.v.GetParmVal(p) for p in self.v.GetGeomParmIDs(self.gid)}
        points=lambda:[[p.x(),p.y(),p.z()] for p in
                      (self.v.ComputeBORXSecPnt(self.gid,i/100) for i in range(101))]
        profile=points()
        self.assertEqual(native_profile_controls.refresh(self.v), [])
        self.assertEqual(before, {p:self.v.GetParmVal(p) for p in self.v.GetGeomParmIDs(self.gid)})
        self.assertEqual(profile, points())
        with self.assertRaisesRegex(ValueError, 'curve parameter'):
            native_preview.refresh_profile(self.v,self.v.FindParm(self.gid,'Diameter','Design'),self.gid)
