"""Component names cannot impersonate original engineering settings managers."""
import unittest
import test_native
import native_managers
from native_worker import parameter

class ManagerNames(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;real={n:native_managers.manager(v,n) for n in native_managers.NAMES};geoms=[]
        for n in sorted(native_managers.NAMES):
            g=v.AddGeom('POD');v.SetGeomName(g,n);geoms.append(g)
            v.CreateAndAddMode(n,0,-1)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        return real,geoms

    def test_colliding_names_load_and_edit_original_managers_after_cold_reload(self):
        v=self.v;real,geoms=self.fixture()
        for n,c in real.items():self.assertEqual(native_managers.manager(v,n),c)
        state,path=self.worker(dict(action='state'));cold,_=self.worker(dict(action='state'),path)
        for result in (state,cold):
            self.assertEqual({x['id'] for x in result['tools']['globalSettings']},set(real.values()))
            self.assertTrue(set(geoms)<={x['id'] for x in result['components']})
            self.assertEqual({m['name'] for m in result['tools']['modes']},native_managers.NAMES)
        pid=v.FindParm(real['VSPAEROSettings'],'NoiseUnits','VSPAERO');state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=1),path)
        field=next(p for c in state['tools']['globalSettings'] if c['id']==real['VSPAEROSettings'] for p in c['params'] if p['id']==pid)
        self.assertEqual(field['value'],1);self.assertTrue(field['choices'])
        cold,_=self.worker(dict(action='state'),path);self.assertEqual(state['components'],cold['components'])

    def test_collision_survives_component_rename_and_preserves_native_geometry(self):
        v=self.v;v.SetGeomName(self.gid,'Reference wing');v.WriteVSPFile(str(self.model),v.SET_ALL)
        baseline,path=self.worker(dict(action='state'))
        state,path=self.worker(dict(action='mutate',operation='rename',geom=self.gid,name='SurfaceIntersectSettings'),path)
        self.assertEqual(state['components'][0]['surfaces'],baseline['components'][0]['surfaces'])
        state,path=self.worker(dict(action='mutate',operation='intersection-defaults',values=dict(CADLenUnit=v.LEN_CM,STEPRepresentation=v.STEP_SHELL)),path)
        settings=next(c for c in state['tools']['globalSettings'] if c['name']=='SurfaceIntersectSettings')
        self.assertNotEqual(settings['id'],self.gid)
        values={p['name']:p['value'] for p in settings['params']};self.assertEqual(values['CADLenUnit'],v.LEN_CM);self.assertEqual(values['STEPRepresentation'],v.STEP_SHELL)
        self.assertEqual(state['components'][0]['surfaces'],baseline['components'][0]['surfaces'])
