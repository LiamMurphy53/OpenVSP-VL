"""Staged triangle metadata restoration against original live native conversion."""
import copy
import ctypes
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
import native_ngon
from native_preview import adapter
import test_native


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeTriangleMetadataRestore(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown

    def fixture(self,kind='POD'):
        v=self.v;v.ClearVSPModel();v.AddGeom(kind);v.Update();gid=v.ComputeCompGeom(v.SET_ALL,False,0)
        for name,value in [('Scale',1.7),('X_Rel_Location',3.125),('Z_Rel_Rotation',17)]:v.SetParmValUpdate(gid,name,'XForm',value)
        data=native_ngon.mesh_metadata(v,gid);v.WriteVSPFile(str(self.model),v.SET_ALL)
        return gid,data

    def canonical(self,data):
        data=copy.deepcopy(data)
        for p in data['points']:p['nodes'].sort()
        for n in data['nodes']:n['edges'].sort()
        for e in data['edges']:e['faces'].sort()
        return data

    def test_cold_process_matches_complete_live_polygon_graph_and_native_exports(self):
        v=self.v
        script='''import json,sys
from pathlib import Path
from vsp_runtime import load
import native_ngon,native_degenerate
p=Path(sys.argv[1]);gid=sys.argv[2];v=load();v.ReadVSPFile(str(p/'source.vsp3'));v.Update()
data=json.loads((p/'metadata.json').read_text());native_ngon.restore_mesh_metadata(v,gid,data)
assert native_ngon.mesh_metadata(v,gid)==data
v.Update();assert native_ngon.mesh_metadata(v,gid)==data
native_ngon.prepare_mesh(v,gid);created=v.CreateNGonMeshGeom(gid)
(p/'cold-polygon.json').write_text(json.dumps(native_ngon.snapshot(v,created)))
native_degenerate.export_mesh(v,[created],str(p/'cold.msh'))
native_degenerate.export_polygon(v,[created],'cold.vspgeom')
'''
        import native_degenerate
        from mesh_io import read_gmsh
        for kind,faces in [('POD',144),('WING',448)]:
            with self.subTest(kind=kind):
                gid,data=self.fixture(kind);folder=self.path/kind;folder.mkdir();(folder/'source.vsp3').write_bytes(self.model.read_bytes());before=self.model.read_bytes()
                (folder/'metadata.json').write_text(json.dumps(data));created=v.CreateNGonMeshGeom(gid)
                expected=native_ngon.snapshot(v,created);self.assertEqual(len(expected['faces']),faces)
                native_degenerate.export_mesh(v,[created],str(folder/'live.msh'))
                previous=Path.cwd();os.chdir(folder)
                try:native_degenerate.export_polygon(v,[created],'live.vspgeom')
                finally:os.chdir(previous)
                env=dict(os.environ,PYTHONPATH=str(Path(native_ngon.__file__).parent))
                result=subprocess.run([sys.executable,'-c',script,str(folder),gid],cwd=folder,env=env,capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                actual=json.loads((folder/'cold-polygon.json').read_text())
                for key,value in self.canonical(expected).items():self.assertEqual(self.canonical(actual)[key],value,key)
                self.assertEqual((folder/'live.vspgeom').read_bytes(),(folder/'cold.vspgeom').read_bytes())
                a,b=read_gmsh(folder/'live.msh'),read_gmsh(folder/'cold.msh');a.pop('filename');b.pop('filename');self.assertEqual(a,b)
                self.assertEqual(self.model.read_bytes(),before)

    def test_stale_geometry_invalid_schema_and_late_parse_failure_do_not_mutate(self):
        v=self.v;gid,data=self.fixture();v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();before=native_ngon.mesh_metadata(v,gid);file_before=self.model.read_bytes()
        stale=copy.deepcopy(data);stale['meshes'][0]['triangles'][0]['corners'][0]['xyz'][0]+=.1
        with self.assertRaisesRegex(ValueError,'does not match'):native_ngon.restore_mesh_metadata(v,gid,stale)
        self.assertEqual(native_ngon.mesh_metadata(v,gid),before)
        invalid=copy.deepcopy(data);invalid['meshes'][0]['triangles'][0]['ignore']=0
        with self.assertRaisesRegex(ValueError,'Invalid triangle metadata'):native_ngon.restore_mesh_metadata(v,gid,invalid)
        self.assertEqual(native_ngon.mesh_metadata(v,gid),before)
        split=copy.deepcopy(data);split['meshes'][0]['triangles'][0]['split']=[copy.deepcopy(split['meshes'][0]['triangles'][0])]
        with self.assertRaisesRegex(ValueError,'split hierarchy'):native_ngon.restore_mesh_metadata(v,gid,split)
        self.assertEqual(native_ngon.mesh_metadata(v,gid),before)
        root=ET.fromstring(native_ngon._payload(data));mesh=root.find('meshes/item');mesh.remove(mesh.find('xyzGrid'))
        _,engine,bridge=adapter(v);f=bridge.studio_mesh_restore_metadata;f.argtypes=[ctypes.c_char_p]*4;f.restype=ctypes.c_char_p;guard=v.FindParm(gid,'Scale_From_Original','XForm').encode()
        for _ in range(3):
            reply=json.loads(f(engine,gid.encode(),guard,ET.tostring(root)));self.assertIn('Missing polygon snapshot field: xyzGrid',reply['error'])
            self.assertEqual(native_ngon.mesh_metadata(v,gid),before)
        for _ in range(3):native_ngon.restore_mesh_metadata(v,gid,data);self.assertEqual(native_ngon.mesh_metadata(v,gid),data)
        self.assertEqual(self.model.read_bytes(),file_before)

    def test_uv_extremes_and_signed_zero_keep_exact_double_values(self):
        v=self.v;gid,data=self.fixture();v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        uv=[-0.0,5e-324,1.7976931348623157e308];data['meshes'][0]['triangles'][0]['corners'][0]['uw']=uv
        native_ngon.restore_mesh_metadata(v,gid,data)
        actual=native_ngon.mesh_metadata(v,gid)['meshes'][0]['triangles'][0]['corners'][0]['uw']
        self.assertEqual([float(x).hex() for x in actual],[x.hex() for x in uv])

    def test_archived_native_tags_restore_atomically_and_bind_to_actual_source(self):
        v=self.v;gid,data=self.fixture('WING');v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();native_ngon.restore_mesh_metadata(v,gid,data)
        _,engine,bridge=adapter(v);guard=v.FindParm(gid,'Scale_From_Original','XForm').encode()
        raw=bridge.studio_mesh_metadata;raw.argtypes=[ctypes.c_char_p]*3;raw.restype=ctypes.c_char_p
        tags=bridge.studio_mesh_restore_tags;tags.argtypes=[ctypes.c_char_p]*4;tags.restype=ctypes.c_char_p
        # Change only the process-global scratch tables, then prepare the
        # restored source: its archived original tables must win.
        altered=copy.deepcopy(data['tagData'])
        altered['componentNames']=['temporary '+n for n in altered['componentNames']]
        altered['names']=[[i,'temporary '+n] for i,n in altered['names']]
        self.assertNotIn('error',json.loads(tags(engine,gid.encode(),guard,native_ngon._payload(altered))))
        self.assertEqual(json.loads(raw(engine,gid.encode(),guard))['tagData'],altered)
        self.assertTrue(native_ngon.prepare_mesh(v,gid)['restoredTagData'])
        self.assertEqual(json.loads(raw(engine,gid.encode(),guard))['tagData'],data['tagData'])
        root=ET.fromstring(native_ngon._payload(altered));root.remove(root.find('geometryCopies'))
        for _ in range(3):
            result=json.loads(tags(engine,gid.encode(),guard,ET.tostring(root)))
            self.assertIn('Missing polygon snapshot field: geometryCopies',result['error'])
            self.assertEqual(json.loads(raw(engine,gid.encode(),guard))['tagData'],data['tagData'])
        # A real native metadata change bypassing the Python archive must
        # invalidate that archive instead of applying stale tables later.
        changed=copy.deepcopy(data);changed['meshes'][0]['triangles'][0]['corners'][0]['uw'][0]+=.125
        metadata=bridge.studio_mesh_restore_metadata;metadata.argtypes=[ctypes.c_char_p]*4;metadata.restype=ctypes.c_char_p
        self.assertNotIn('error',json.loads(metadata(engine,gid.encode(),guard,native_ngon._payload(changed))))
        native_ngon.mesh_metadata(v,gid)
        self.assertNotIn(gid,v._studio_mesh_tag_data)
