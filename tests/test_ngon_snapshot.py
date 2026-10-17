"""Original-engine polygon graph capture, without saving away native data."""
from collections import Counter
import ctypes
import json
import sys
import unittest
import test_native
import native_ngon
from native_preview import adapter


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class NativePolygonSnapshot(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',test_native.load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    def generate(self, kinds):
        v=self.v;v.ClearVSPModel()
        for kind in kinds:v.AddGeom(kind)
        v.Update();v.SetAnalysisInputDefaults('DegenGeomMesh')
        v.SetIntAnalysisInput('DegenGeomMesh','DegenGeomMeshType',[v.NGON_MESH_TYPE])
        rid=v.ExecAnalysis('DegenGeomMesh')
        return v.GetStringResults(rid,'Mesh_GeomID')[0]

    def check_graph(self, data):
        points,nodes,edges,faces=(data[k] for k in ('points','nodes','edges','faces'))
        for i,p in enumerate(points):
            for n in p['nodes']:self.assertEqual(nodes[n]['point'],i)
        for i,n in enumerate(nodes):
            self.assertIn(i,points[n['point']]['nodes'])
            for e in n['edges']:self.assertIn(i,edges[e]['nodes'])
        for i,e in enumerate(edges):
            for n in e['nodes']:self.assertIn(i,nodes[n]['edges'])
            for f in e['faces']:self.assertIn(i,faces[f]['edges'])
        for i,f in enumerate(faces):
            self.assertGreaterEqual(len(f['edges']),3)
            for e in f['edges']:self.assertIn(i,edges[e]['faces'])
            self.assertTrue(0<=f['parent']<len(faces))
        for m in data['meshes']:
            self.assertEqual(len(m['wingWakes']),len(m['wingWakeParts']))
            self.assertEqual(len(m['bodyWakes']),len(m['bodyWakeParts']))
            self.assertEqual(len(m['bodyWakeNodes']),len(m['bodyWakeNodeParts']))
            for wake in m['wingWakes']+m['bodyWakes']:
                self.assertTrue(all(0<=e<len(edges) for e in wake))

    def test_live_graph_matches_native_export_and_preserves_state(self):
        v=self.v
        for kinds in [('POD',),('WING',),('POD','WING')]:
            with self.subTest(kinds=kinds):
                gid=self.generate(kinds);before=native_ngon.snapshot(v,gid)
                self.check_graph(before);self.assertEqual(native_ngon.snapshot(v,gid),before)
                self.assertEqual(json.loads(json.dumps(before,allow_nan=False)),before)
                filename=self.path/'reference.vspgeom';slot=v.GetNumSets()-1
                for g in v.FindGeoms():v.SetSetFlag(g,slot,g==gid)
                v.ExportFile(str(filename),slot,v.EXPORT_VSPGEOM,1)
                lines=filename.read_text().splitlines();levels=int(lines[1]);counts=[list(map(int,x.split())) for x in lines[2:2+levels]]
                xyz=[tuple(map(float,x.split())) for x in lines[2+levels:2+levels+counts[-1][0]]]
                expected=Counter(tuple(float(format(x,'.10g')) for x in p['xyz']) for p in before['points'])
                self.assertEqual(Counter(xyz),expected)
                self.assertEqual(sum(len(m['faces']) for m in before['meshes']),sum(x[1] for x in counts))
                if 'WING' in kinds:self.assertTrue(any(m['wingWakes'] for m in before['meshes']))

    def test_transforms_do_not_bake_into_local_graph(self):
        v=self.v;gid=self.generate(('WING',));before=native_ngon.snapshot(v,gid)
        for name,value in [('X_Rel_Location',3.125),('Z_Rel_Rotation',31),('Scale',1.7)]:v.SetParmValUpdate(gid,name,'XForm',value)
        after=native_ngon.snapshot(v,gid)
        self.assertNotEqual(after['scaleMatrix'],before['scaleMatrix'])
        for key in before:
            if key!='scaleMatrix':self.assertEqual(after[key],before[key],key)
        v.WriteVSPFile(str(self.model),v.SET_ALL);saved=self.model.read_bytes()
        v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
        cold=native_ngon.snapshot(v,gid);self.assertEqual(cold['points'],[])
        self.assertEqual(self.model.read_bytes(),saved)

    def test_wrong_geometry_and_layout_guard_reject(self):
        v=self.v
        with self.assertRaisesRegex(ValueError,'polygon mesh'):native_ngon.snapshot(v,self.gid)
        gid=self.generate(('POD',));_,engine,bridge=adapter(v);f=bridge.studio_ngon_snapshot
        f.argtypes=[ctypes.c_char_p]*3;f.restype=ctypes.c_char_p
        result=json.loads(f(engine,gid.encode(),v.FindParm(gid,'Scale','XForm').encode()))
        self.assertIn('layout does not match',result['error'])


