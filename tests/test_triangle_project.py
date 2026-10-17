"""Automatic triangle project persistence against live native conversion."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
import native_ngon
import test_native


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativeTriangleProject(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    @staticmethod
    def canonical(data):
        data=copy.deepcopy(data)
        for p in data['points']:p['nodes'].sort()
        for n in data['nodes']:n['edges'].sort()
        for e in data['edges']:e['faces'].sort()
        return data

    def test_automatic_cold_project_restore_matches_live_native_conversion(self):
        script='''import json,sys
from pathlib import Path
from vsp_runtime import load
import native_ngon
p=Path(sys.argv[1]);gid=sys.argv[2];v=load();v.ReadVSPFile(str(p));v.Update()
assert native_ngon.restore_file(v,p)==[gid]
native_ngon.prepare_mesh(v,gid);created=v.CreateNGonMeshGeom(gid)
(p.parent/'cold.json').write_text(json.dumps(native_ngon.snapshot(v,created)))
'''
        v=self.v
        for kinds in [('POD',),('WING',),('POD','WING')]:
            with self.subTest(kinds=kinds):
                v.ClearVSPModel()
                for kind in kinds:v.AddGeom(kind)
                v.Update();gid=v.ComputeCompGeom(v.SET_ALL,False,0)
                v.SetParmValUpdate(gid,'Scale','XForm',1.7)
                v.SetParmValUpdate(gid,'Z_Rel_Rotation','XForm',17.)
                self.assertTrue(native_ngon.capture_mesh(v,gid))
                original=native_ngon.mesh_metadata(v,gid)
                native_ngon.write(v,self.model)
                self.assertEqual(native_ngon.mesh_metadata(v,gid),original)
                self.assertEqual(len(ET.parse(self.model).findall('./Vehicle/Geom/StudioTriangleMetadata')),1)
                created=v.CreateNGonMeshGeom(gid);expected=native_ngon.snapshot(v,created)
                env=dict(os.environ,PYTHONPATH=str(Path(native_ngon.__file__).parent))
                result=subprocess.run([sys.executable,'-c',script,str(self.model),gid],cwd=self.path,env=env,capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                actual=json.loads((self.path/'cold.json').read_text())
                self.assertEqual(self.canonical(actual),self.canonical(expected))

    def test_corrupt_archive_rejects_without_rewriting_file(self):
        v=self.v;gid=v.ComputeCompGeom(v.SET_ALL,False,0);native_ngon.capture_mesh(v,gid);native_ngon.write(v,self.model)
        tree=ET.parse(self.model);tree.find('./Vehicle/Geom/StudioTriangleMetadata').set('sha256','0'*64);tree.write(self.model)
        before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'corrupt'):self.worker(dict(action='state'))
        self.assertEqual(self.model.read_bytes(),before)

    def test_analysis_artifact_survives_property_edit_reopen_and_conversion(self):
        v=self.v;before=self.model.read_bytes()
        result,path=self.worker(dict(action='analysis',name='CompGeom',inputs=[]))
        archive=result['componentMeshModel'];self.assertTrue(archive['triangleMetadata'])
        model=path.parent/archive['file'];gid=archive['geometryIDs'][0]
        state,_=self.worker(dict(action='state'),model)
        self.assertIn(gid,[c['id'] for c in state['components']])
        v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update();native_ngon.restore_file(v,model)
        pid=v.FindParm(gid,'X_Rel_Location','XForm');v.SetParmValUpdate(pid,12.375)
        native_ngon.prepare_mesh(v,gid);created=v.CreateNGonMeshGeom(gid)
        expected=native_ngon.snapshot(v,created);self.assertEqual(len(expected['faces']),448)
        _,edited=self.worker(dict(action='mutate',operation='parameter',id=pid,value=12.375),model)
        self.assertEqual(len(ET.parse(edited).findall('./Vehicle/Geom/StudioTriangleMetadata')),1)
        self.worker(dict(action='state'),edited)
        converted,output=self.worker(dict(action='mutate',operation='mesh-to-polygon',geom=gid),edited)
        node=next(g for g in ET.parse(output).findall('./Vehicle/Geom') if g.findtext('ParmContainer/ID')==converted['changed'])
        actual=json.loads(node.findtext('StudioPolygonSnapshot'))
        self.assertEqual(self.canonical(actual),self.canonical(expected))
        self.assertEqual(self.model.read_bytes(),before)
