"""Native CFD source drawings, independent manager equality and read-only queries."""
import ctypes
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import test_native
from vsp_runtime import ROOT,distribution,load

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class CfdSourcePreview(unittest.TestCase):
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    @classmethod
    def setUpClass(cls):
        cls.v=load();cls.reference_temp=tempfile.TemporaryDirectory(prefix='openvsp-cfd-reference-')
        target=Path(cls.reference_temp.name)/'reference.dylib'
        subprocess.run(['/usr/bin/clang++','-std=c++17','-O2','-dynamiclib','-I',str(ROOT/'native_bridge/vendor/openvsp-3.52.2'),str(ROOT/'tests/cfd_native_reference.cpp'),'-o',str(target)],capture_output=True,text=True,check=True)
        cls.library=ctypes.CDLL(str(target));cls.reference=cls.library.native_cfd_manager_drawings
        cls.reference.argtypes=[ctypes.c_char_p];cls.reference.restype=ctypes.c_char_p

    @classmethod
    def tearDownClass(cls):cls.reference_temp.cleanup()

    def native_reference(self):
        v=self.v;container=v.FindContainersWithName('CFDMeshSettings')[0]
        original={p:v.GetParmVal(p) for p in v.FindContainerParmIDs(container)}
        try:
            for p in original:
                name=v.GetParmName(p)
                if name.startswith('Draw') or name in ['UseMode','Set','DegenSet']:
                    v.SetParmVal(p,1 if name=='DrawSourceWake' else v.SET_ALL if name=='Set' else v.SET_NONE if name=='DegenSet' else 0)
            data=json.loads(self.reference(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode()))
        finally:
            for p,value in original.items():v.SetParmVal(p,value)
        self.assertEqual({p:v.GetParmVal(p) for p in original},original)
        self.assertIsInstance(data,list);return data

    @staticmethod
    def drawings(objects):
        # Draw IDs are random engine identifiers; compare every type and point.
        return sorted((o['nativeType'],tuple(tuple(p) for p in o['points'])) for o in objects)

    def add_sources(self,geom,surface=0):
        v=self.v;ids=[]
        for name in ['POINT_SOURCE','LINE_SOURCE','BOX_SOURCE','ULINE_SOURCE','WLINE_SOURCE']:
            v.AddCFDSource(getattr(v,name),geom,surface,.2,.7,0,.3,.1,.4,.65,.75)
            index=v.GetNumCFDSources(geom)-1;v.SetCFDSourceName(geom,index,name)
            ids.append(v.GetCFDSourceID(geom,index))
        v.Update();return ids

    def test_every_source_family_and_mirror_matches_independent_native_manager(self):
        v=self.v;ids=self.add_sources(self.gid)
        for name,value in [('X_Rel_Location',2),('Y_Rel_Location',1),('Z_Rel_Rotation',23)]:v.SetParmVal(self.gid,name,'XForm',value)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        expected=self.native_reference();data,path=self.worker(dict(action='query',operation='cfd-source-preview',geom=self.gid))
        self.assertEqual(data['engineOperation'],'Geom::UpdateSources / BaseSimpleSource::LoadDrawObjs')
        self.assertEqual([s['id'] for s in data['parts']],ids)
        self.assertEqual(self.drawings([o for s in data['parts'] for o in s['objects']]),self.drawings(expected))
        for source in data['parts']:
            self.assertEqual([c['surface'] for c in source['copies']],[0,1]);self.assertTrue(source['objects'])
            self.assertTrue(all(o['visible'] for o in source['objects']))
        for copy in data['parts'][0]['copies']:
            center=v.CompPnt01(self.gid,copy['surface'],0,.3)
            for p in copy['objects'][0]['points']:
                self.assertAlmostEqual(math.dist(p,[center.x(),center.y(),center.z()]),.7,places=12)
        self.assertEqual(path.read_bytes(),before);self.assertEqual(self.model.read_bytes(),before)
        self.assertFalse(list(path.parent.glob('*.msh')))

    def test_multi_surface_propeller_sources_keep_native_parent_and_copies(self):
        v=self.v;v.ClearVSPModel();self.gid=v.AddGeom('PROP');v.Update()
        self.assertGreater(v.GetNumMainSurfs(self.gid),1);ids=self.add_sources(self.gid,1)
        v.WriteVSPFile(str(self.model),v.SET_ALL);expected=self.native_reference()
        data,path=self.worker(dict(action='query',operation='cfd-source-preview',geom=self.gid))
        self.assertEqual([s['id'] for s in data['parts']],ids)
        self.assertEqual(self.drawings([o for s in data['parts'] for o in s['objects']]),self.drawings(expected))
        self.assertTrue(all(any(c['surface']==1 for c in s['copies']) for s in data['parts']))
        reopened,_=self.worker(dict(action='query',operation='cfd-source-preview',geom=self.gid),path)
        self.assertEqual(self.drawings([o for s in reopened['parts'] for o in s['objects']]),self.drawings(expected))

    def test_source_edit_and_delete_refresh_native_drawings_and_invalid_query_preserves_file(self):
        v=self.v;ids=self.add_sources(self.gid);v.WriteVSPFile(str(self.model),v.SET_ALL)
        first,path=self.worker(dict(action='query',operation='cfd-source-preview',geom=self.gid))
        radius=next(p for p in v.FindContainerParmIDs(ids[0]) if v.GetParmName(p)=='SrcRad')
        _,path=self.worker(dict(action='mutate',operation='parameter',id=radius,value=1.25),path)
        changed,path=self.worker(dict(action='query',operation='cfd-source-preview',geom=self.gid),path)
        self.assertNotEqual(self.drawings(first['parts'][0]['objects']),self.drawings(changed['parts'][0]['objects']))
        v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update()
        self.assertEqual(self.drawings([o for s in changed['parts'] for o in s['objects']]),self.drawings(self.native_reference()))
        _,path=self.worker(dict(action='mutate',operation='source-delete',geom=self.gid,index=0),path)
        deleted,path=self.worker(dict(action='query',operation='cfd-source-preview',geom=self.gid),path)
        self.assertEqual([s['id'] for s in deleted['parts']],ids[1:])
        before=path.read_bytes()
        for geom in ['UNKNOWN',None]:
            with self.assertRaises(ValueError):self.worker(dict(action='query',operation='cfd-source-preview',geom=geom),path)
            self.assertEqual(path.read_bytes(),before)

    def test_empty_sources_and_exact_official_header_provenance(self):
        before=self.model.read_bytes();data,path=self.worker(dict(action='query',operation='cfd-source-preview',geom=self.gid))
        self.assertEqual(data['parts'],[]);self.assertEqual(path.read_bytes(),before)
        folder=ROOT/'native_bridge/vendor/openvsp-3.52.2';provenance=json.loads((folder/'PROVENANCE.json').read_text())
        for name in ['GridDensity.h','ParmContainer.h','BndBox.h','Matrix4d.h']:
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(),provenance['sha256'][name])
