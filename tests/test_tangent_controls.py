"""Named tangent drivers must reproduce direct official MoveEditXSecPnt calls."""
import sys
import unittest
import test_native
from vsp_runtime import load
from native_preview import parameter_activity


@unittest.skipUnless(sys.version_info[:2] == (3, 11), 'Use the matching native Python runtime.')
class TangentControls(unittest.TestCase):
    setUpClass = classmethod(lambda cls: setattr(cls, 'v', load()))
    setUp = test_native.NativeIntegration.setUp
    tearDown = test_native.NativeIntegration.tearDown
    worker = test_native.NativeIntegration.worker

    def fixture(self, kind='STACK', closed=True, symmetry=None):
        v = self.v
        v.ClearVSPModel()
        self.gid = v.AddGeom(kind)
        surf = v.GetXSecSurf(self.gid, 0)
        v.ChangeXSecShape(surf, 1, v.XS_CIRCLE)
        v.ConvertXSecToEdit(self.gid, 1)
        v.Update()
        x = v.GetXSec(surf, 1)
        v.SetParmValUpdate(v.GetXSecParm(x, 'SymType'), v.SYM_NONE if symmetry is None else symmetry)
        v.SetParmValUpdate(v.GetXSecParm(x, 'CloseFlag'), int(closed))
        v.SetParmValUpdate(v.GetXSecParm(x, 'G1_3'), 1)
        v.WriteVSPFile(str(self.model), v.SET_ALL)
        return x

    def assert_native(self, state):
        v = self.v
        c = next(c for c in state['components'] if c['id'] == self.gid)
        self.assertEqual({p['id']: p['value'] for p in c['params']},
                         {p: v.GetParmVal(p) for p in v.GetGeomParmIDs(self.gid)})
        for surface in c['surfaces']:
            u, w = v.GetUWTess01(self.gid, surface['index'] % v.GetNumMainSurfs(self.gid))
            expected = v.CompVecPnt01(self.gid, surface['index'], [x for x in u for _ in w], [y for _ in u for y in w])
            self.assertEqual(surface['points'], [[p.x(), p.y(), p.z()] for p in expected])
        x = v.GetXSec(v.GetXSecSurf(self.gid, 0), 1)
        s = next(s for s in c['sections'] if s['surface'] == 0 and s['index'] == 1)
        points = [[p.x(), p.y(), p.z()] for p in v.GetEditXSecCtrlVec(x, True)]
        self.assertEqual(s['controlPoints'], points)
        self.assertEqual(s['profile'], [[p.x(), p.y(), p.z()] for p in [v.ComputeXSecPnt(x, i / 100) for i in range(101)]])
        for control in s['tangentControls']:
            anchor = control['anchor']
            self.assertEqual(control['u'], v.GetParmVal(v.GetXSecParm(x, f'U_{anchor}')))
            self.assertEqual(control['smooth'], bool(v.GetParmVal(v.GetXSecParm(x, f'G1_{anchor}'))))
            for side, handle in control['handles'].items():
                i = anchor - 1 if side == 'incoming' else anchor + 1
                if i == -1: i = len(points) - 2
                if i == len(points): i = 1
                self.assertEqual(handle['point'], i)
                self.assertEqual(handle['coordinates'], points[i])
                ids = [v.GetXSecParm(x, f'{axis}_{i}') for axis in 'XYZ']
                active = parameter_activity(v, ids)
                self.assertEqual([p['id'] for p in handle['parameters']], ids)
                self.assertEqual([p['active'] for p in handle['parameters']], [active[p] for p in ids])
        return s

    def apply_direct_and_compare(self, anchor, side, index, path=None):
        v = self.v
        source = path or self.model
        v.ClearVSPModel(); v.ReadVSPFile(str(source)); v.Update()
        x = v.GetXSec(v.GetXSecSurf(self.gid, 0), 1)
        p = v.GetEditXSecCtrlVec(x, True)[index]
        xyz = [p.x(), p.y(), p.z()]
        active = parameter_activity(v, [v.GetXSecParm(x, f'{axis}_{index}') for axis in 'XYZ'])
        # Change every active coordinate, preserving exact locked coordinates.
        for k, axis in enumerate('XYZ'):
            if active[v.GetXSecParm(x, f'{axis}_{index}')]: xyz[k] += [.035, -.026, .004][k]
        v.MoveEditXSecPnt(x, index, v.vec3d(*xyz)); v.Update()
        state, saved = self.worker(dict(action='mutate', operation='curve-tangent', geom=self.gid,
                                        surface=0, index=1, anchor=anchor, side=side, xyz=xyz), source)
        self.assert_native(state)
        v.ClearVSPModel(); v.ReadVSPFile(str(saved)); v.Update()
        reopened, _ = self.worker(dict(action='state'), saved)
        self.assert_native(reopened)
        return saved

    def test_both_drivers_on_all_section_families_open_and_closed(self):
        for kind in ('WING', 'FUSELAGE', 'STACK', 'PROP'):
            for closed in (False, True):
                self.fixture(kind, closed)
                for side, handle in [('incoming', 2), ('outgoing', 4)]:
                    with self.subTest(kind=kind, closed=closed, side=side):
                        self.apply_direct_and_compare(3, side, handle)

    def test_native_wrap_endpoints_and_symmetry_constraints(self):
        v = self.v
        for closed in (False, True):
            for symmetry in (v.SYM_NONE, v.SYM_RL):
                x = self.fixture(closed=closed, symmetry=symmetry)
                count = len(v.GetEditXSecCtrlVec(x, True))
                effective_closed = bool(v.GetParmVal(v.GetXSecParm(x, 'CloseFlag')))
                cases = [(0, 'outgoing', 1), (3, 'incoming', 2), (3, 'outgoing', 4)]
                cases += [(0, 'incoming', count - 2)] if effective_closed else [(count - 1, 'incoming', count - 2)]
                for anchor, side, handle in cases:
                    with self.subTest(closed=closed, symmetry=symmetry, anchor=anchor, side=side):
                        self.apply_direct_and_compare(anchor, side, handle)

    def test_unsmoothed_tangents_remain_independent(self):
        v = self.v
        x = self.fixture()
        v.SetParmValUpdate(v.GetXSecParm(x, 'G1_3'), 0)
        v.WriteVSPFile(str(self.model), v.SET_ALL)
        for side, index, opposite in [('incoming', 2, 4), ('outgoing', 4, 2)]:
            v.ClearVSPModel(); v.ReadVSPFile(str(self.model)); v.Update()
            x = v.GetXSec(v.GetXSecSurf(self.gid, 0), 1)
            p = v.GetEditXSecCtrlVec(x, True)[opposite]
            before = [p.x(), p.y(), p.z()]
            self.apply_direct_and_compare(3, side, index)
            x = v.GetXSec(v.GetXSecSurf(self.gid, 0), 1)
            p = v.GetEditXSecCtrlVec(x, True)[opposite]
            self.assertEqual([p.x(), p.y(), p.z()], before)

    def test_invalid_tangents_are_atomic_and_endpoints_are_described(self):
        v = self.v
        x = self.fixture(closed=False, symmetry=v.SYM_NONE)
        state, path = self.worker(dict(action='state'))
        section = state['components'][0]['sections'][1]
        first, last = section['tangentControls'][0], section['tangentControls'][-1]
        self.assertEqual(list(first['handles']), ['outgoing'])
        self.assertEqual(list(last['handles']), ['incoming'])
        before = path.read_bytes()
        base = dict(anchor=3, side='outgoing', xyz=section['controlPoints'][4])
        invalid = [dict(anchor=True), dict(anchor=1), dict(anchor=3.1), dict(anchor=-3),
                   dict(anchor=999), dict(side='middle'), dict(xyz=[0, 1]),
                   dict(xyz=[float('nan'), 0, 0]), dict(xyz=[True, 0, 0]),
                   dict(anchor=0, side='incoming'), dict(anchor=last['anchor'], side='outgoing')]
        for extra in invalid:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.worker(dict(action='mutate', operation='curve-tangent', geom=self.gid, index=1, **(base | extra)), path)
            self.assertEqual(path.read_bytes(), before)
        state, path = self.worker(dict(action='mutate', operation='curve-type', geom=self.gid, index=1, type='LINEAR'), path)
        self.assertEqual(state['components'][0]['sections'][1]['tangentControls'], [])
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'cubic Bezier'):
            self.worker(dict(action='mutate', operation='curve-tangent', geom=self.gid, index=1, **base), path)
        self.assertEqual(path.read_bytes(), before)
        self.fixture(symmetry=v.SYM_RL)
        state, path = self.worker(dict(action='state'))
        before = path.read_bytes()
        section = state['components'][0]['sections'][1]
        c, side, h, k = next((c, side, h, k) for c in section['tangentControls'] for side, h in c['handles'].items()
                             for k, p in enumerate(h['parameters']) if not p['active'])
        xyz = list(h['coordinates']); xyz[k] += .1
        with self.assertRaisesRegex(ValueError, 'locked by OpenVSP'):
            self.worker(dict(action='mutate', operation='curve-tangent', geom=self.gid, index=1,
                             anchor=c['anchor'], side=side, xyz=xyz), path)
        self.assertEqual(path.read_bytes(), before)
