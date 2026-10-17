"""Self-contained Studio polygon files through real worker transactions."""
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
import native_ngon
import native_files
import test_native
import test_ngon_snapshot


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativePolygonProject(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker
    generate=test_ngon_snapshot.NativePolygonSnapshot.generate

    def test_file_roundtrip_and_worker_edit_keep_native_geometry(self):
        v=self.v;gid=self.generate(('POD','WING'))
        v.SetParmValUpdate(gid,'Scale','XForm',1.7)
        flags={g:[v.GetSetFlag(g,i) for i in range(v.GetNumSets())] for g in v.FindGeoms()}
        expected=native_files.mesh_geometry(v,gid)
        self.assertTrue(expected['points']);self.assertTrue(expected['triangles'])
        self.assertEqual(set(v.FindGeoms()),set(flags))
        self.assertEqual(flags,{g:[v.GetSetFlag(g,i) for i in range(v.GetNumSets())] for g in v.FindGeoms()})
        native_ngon.write(v,self.model);baseline=self.model.read_bytes()
        saved=ET.parse(self.model).findall('./Vehicle/Geom/StudioPolygonSnapshot');self.assertEqual(len(saved),1)
        data=next(json.loads(n.text) for n in saved)
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        self.assertEqual(native_ngon.snapshot(v,gid)['points'],[])
        self.assertEqual(native_ngon.restore_file(v,self.model),[gid])
        self.assertEqual(native_ngon.snapshot(v,gid),data)
        state,path=self.worker(dict(action='state'))
        self.assertEqual(next(c for c in state['components'] if c['id']==gid)['mesh'],expected)
        active=next(p for c in state['components'] if c['id']==gid for p in c['params'] if p['name']=='ActiveMesh' and p['rawGroup']=='RefMesh')
        self.assertEqual(active['max'],0)
        with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='parameter',id=active['id'],value=1))
        self.assertEqual(self.model.read_bytes(),baseline);self.assertEqual(path.read_bytes(),baseline)
        pid=v.FindParm(gid,'X_Rel_Location','XForm');v.SetParmValUpdate(pid,12.375)
        changed=native_files.mesh_geometry(v,gid)
        edited,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=12.375))
        self.assertEqual(next(c for c in edited['components'] if c['id']==gid)['mesh'],changed)
        reopened,reopened_path=self.worker(dict(action='state'),path)
        self.assertEqual(next(c for c in reopened['components'] if c['id']==gid)['mesh'],changed)
        self.assertEqual(path.read_bytes(),reopened_path.read_bytes())
        ypid=v.FindParm(gid,'Y_Rel_Location','XForm');v.SetParmValUpdate(ypid,-3.)
        study_expected=native_files.mesh_geometry(v,gid)
        _,study_path=self.worker(dict(action='study-model',parameters=[dict(id=ypid,value=-3.)]),path)
        study_state,_=self.worker(dict(action='state'),study_path)
        self.assertEqual(next(c for c in study_state['components'] if c['id']==gid)['mesh'],study_expected)
        self.assertEqual(self.model.read_bytes(),baseline)
        self.assertFalse(list(self.path.rglob('.studio-polygons-*')))
        self.assertFalse(list(self.path.rglob('polygon-preview-*.msh')))

    def test_corrupt_saved_snapshot_rejects_without_rewriting_project(self):
        v=self.v;self.generate(('WING',));native_ngon.write(v,self.model)
        tree=ET.parse(self.model);entry=tree.find('./Vehicle/Geom/StudioPolygonSnapshot');entry.set('sha256','0'*64);tree.write(self.model)
        before=self.model.read_bytes()
        with self.assertRaisesRegex(ValueError,'corrupt'):self.worker(dict(action='state'))
        self.assertEqual(self.model.read_bytes(),before)

    def test_models_without_polygons_keep_original_native_file_bytes(self):
        v=self.v;v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        native_ngon.write(v,self.model);self.assertEqual(self.model.read_bytes(),before)
        self.assertEqual(native_ngon.restore_file(v,self.model),[])

    def test_failed_atomic_file_replacement_keeps_previous_model_and_filename(self):
        v=self.v;gid=self.generate(('WING',));native_ngon.write(v,self.model)
        before=self.model.read_bytes();filename=v.GetVSPFileName();graph=native_ngon.snapshot(v,gid)
        directory=self.path/'destination';directory.mkdir()
        with self.assertRaises(OSError):native_ngon.write(v,directory)
        self.assertEqual(v.GetVSPFileName(),filename);self.assertEqual(self.model.read_bytes(),before)
        self.assertEqual(native_ngon.snapshot(v,gid),graph)
        self.assertFalse(list(self.path.glob('.studio-polygons-*')))

    def test_multiple_polygon_components_restore_by_saved_native_identity(self):
        v=self.v;first=self.generate(('WING',));slot=v.GetNumSets()-1
        for g in v.FindGeoms():v.SetSetFlag(g,slot,g!=first)
        v.SetAnalysisInputDefaults('DegenGeomMesh');v.SetIntAnalysisInput('DegenGeomMesh','Set',[slot]);v.SetIntAnalysisInput('DegenGeomMesh','DegenGeomMeshType',[v.NGON_MESH_TYPE])
        result=v.ExecAnalysis('DegenGeomMesh');second=v.GetStringResults(result,'Mesh_GeomID')[0]
        self.assertNotEqual(first,second);v.SetParmValUpdate(second,'Y_Rel_Location','XForm',3.)
        expected={g:native_files.mesh_geometry(v,g) for g in [first,second]}
        native_ngon.write(v,self.model);before=self.model.read_bytes()
        state,path=self.worker(dict(action='state'))
        for g in expected:self.assertEqual(next(c for c in state['components'] if c['id']==g)['mesh'],expected[g])
        self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
