"""Fresh-process polygon restoration and staged failure rejection."""
import copy
import ctypes
import json
import math
from pathlib import Path
import os
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
import native_ngon
from native_preview import adapter
import test_ngon_snapshot
import test_native


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativePolygonRestore(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    generate=test_ngon_snapshot.NativePolygonSnapshot.generate

    def test_cold_process_restores_exact_graph_and_original_native_exports(self):
        v=self.v
        script='''import json,sys
from pathlib import Path
from vsp_runtime import load
import native_ngon,native_degenerate
p=Path(sys.argv[1]);gid=sys.argv[2];v=load();v.ReadVSPFile(str(p/'model.vsp3'));v.Update()
before=native_ngon.snapshot(v,gid);assert not before['points']
data=json.loads((p/'graph.json').read_text());native_ngon.restore(v,gid,data)
assert native_ngon.snapshot(v,gid)==data
v.Update();assert native_ngon.snapshot(v,gid)==data
(p/'restored.json').write_text(json.dumps(native_ngon.snapshot(v,gid),sort_keys=True))
v.ExportFile(str(p/'after.vspgeom'),v.GetNumSets()-1,v.EXPORT_VSPGEOM,1)
native_degenerate.export_mesh(v,[gid],str(p/'after.msh'))
'''
        for kinds in [('POD',),('WING',),('POD','WING')]:
            with self.subTest(kinds=kinds):
                gid=self.generate(kinds)
                for name,value in [('X_Rel_Location',3.125),('Y_Rel_Location',-2.25),('Z_Rel_Rotation',31),('Scale',1.7)]:v.SetParmValUpdate(gid,name,'XForm',value)
                folder=self.path/('-'.join(kinds));folder.mkdir()
                slot=v.GetNumSets()-1
                for g in v.FindGeoms():v.SetSetFlag(g,slot,g==gid)
                # Export first so native numbering and alternate triangulation caches
                # are part of the graph that must survive a cold restore.
                v.ExportFile(str(folder/'before.vspgeom'),slot,v.EXPORT_VSPGEOM,1)
                import native_degenerate
                native_degenerate.export_mesh(v,[gid],str(folder/'before.msh'))
                data=native_ngon.snapshot(v,gid);native_ngon.validate(data)
                (folder/'graph.json').write_text(json.dumps(data))
                v.WriteVSPFile(str(folder/'model.vsp3'),v.SET_ALL);baseline=(folder/'model.vsp3').read_bytes()
                env=dict(os.environ,PYTHONPATH=str(Path(native_ngon.__file__).parent))
                run=subprocess.run([sys.executable,'-c',script,str(folder),gid],cwd=folder,env=env,capture_output=True,text=True,timeout=30)
                self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                self.assertEqual((folder/'before.vspgeom').read_bytes(),(folder/'after.vspgeom').read_bytes())
                from mesh_io import read_gmsh
                expected,actual=read_gmsh(folder/'before.msh'),read_gmsh(folder/'after.msh')
                expected.pop('filename');actual.pop('filename');self.assertEqual(actual,expected)
                self.assertEqual((folder/'model.vsp3').read_bytes(),baseline)
                self.assertEqual(json.loads((folder/'restored.json').read_text()),data)

    def test_invalid_snapshots_and_late_native_parse_failure_preserve_live_graph(self):
        v=self.v;gid=self.generate(('WING',));before=native_ngon.snapshot(v,gid)
        bad=[]
        for edit in [lambda d:d['nodes'][0].update(point=-1),lambda d:d['edges'][0].update(nodes=[0,0]),lambda d:d['points'][0]['xyz'].__setitem__(0,math.nan),lambda d:d['meshes'][0]['nodes'].append(0),lambda d:d['nodes'][0].update(edges=[]),lambda d:d.update(activeMesh=99)]:
            data=copy.deepcopy(before);edit(data);bad.append(data)
        for data in bad:
            with self.assertRaisesRegex(ValueError,'snapshot'):native_ngon.restore(v,gid,data)
            self.assertEqual(native_ngon.snapshot(v,gid),before)
        # Bypass Python validation deliberately: all native allocations occur,
        # then a missing late metadata field must discard only the staged graph.
        root=ET.fromstring(native_ngon._payload(before));root.remove(root.find('tagIDs'))
        _,engine,bridge=adapter(v);f=bridge.studio_ngon_restore;f.argtypes=[ctypes.c_char_p]*4;f.restype=ctypes.c_char_p
        guard=v.FindParm(gid,'Scale_From_Original','XForm').encode()
        for _ in range(3):
            reply=json.loads(f(engine,gid.encode(),guard,ET.tostring(root)))
            self.assertIn('Missing polygon snapshot field: tagIDs',reply['error'])
            self.assertEqual(native_ngon.snapshot(v,gid),before)
        # Restoring repeatedly also destroys the old native graph safely.
        for _ in range(3):
            native_ngon.restore(v,gid,before);self.assertEqual(native_ngon.snapshot(v,gid),before)

    def test_full_precision_extremes_and_signed_zero_survive_restore(self):
        v=self.v;gid=self.generate(('POD',));data=native_ngon.snapshot(v,gid)
        # Restore does not compute geometry; these finite payload coordinates
        # exercise serialization independently of later geometry calculations.
        data['points'][0]['xyz']=[-0.0,5e-324,1.7976931348623157e308]
        native_ngon.restore(v,gid,data);actual=native_ngon.snapshot(v,gid)
        self.assertEqual([float(x).hex() for x in actual['points'][0]['xyz']],[x.hex() for x in data['points'][0]['xyz']])
