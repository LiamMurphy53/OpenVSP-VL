"""Complete native wire drawings, settings, transforms and file persistence."""
import base64
import ctypes
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import test_native
from vsp_runtime import load,distribution,ROOT


def plot3d(binary=False,endian='<',precision='d',iblank=False):
    # Three native blocks: a surface, an I-only curve and a J-only curve.
    dims=[(7,5,1),(4,1,1),(1,4,1)]
    arrays=[]
    for ni,nj,nk in dims:
        points=[(i*.5,j*.4,i*j*.07) for j in range(nj) for i in range(ni)]
        arrays.append([p[axis] for axis in range(3) for p in points])
    if not binary:
        return ('3\n'+'\n'.join(' '.join(map(str,d)) for d in dims)+'\n'+'\n'.join(' '.join(map(str,a)) for a in arrays)+'\n').encode()
    def record(data):return struct.pack(endian+'i',len(data))+data+struct.pack(endian+'i',len(data))
    raw=record(struct.pack(endian+'i',3))+record(struct.pack(endian+'9i',*[n for d in dims for n in d]))
    for d,values in zip(dims,arrays):
        data=struct.pack(endian+str(len(values))+precision,*values)
        if iblank:data+=struct.pack(endian+str(d[0]*d[1])+'i',*([1]*(d[0]*d[1])))
        raw+=record(data)
    return raw


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class WireGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v=load();cls.reference_dir=tempfile.TemporaryDirectory(prefix='openvsp-wire-reference-')
        library=Path(cls.reference_dir.name)/'reference.dylib'
        subprocess.run(['/usr/bin/clang++','-std=c++17','-O2','-dynamiclib','-I',str(ROOT/'native_bridge/vendor/openvsp-3.52.2'),str(ROOT/'tests/wire_native_reference.cpp'),'-o',str(library)],capture_output=True,check=True)
        cls.library=ctypes.CDLL(str(library));cls.reference=cls.library.native_wire_reference
        cls.reference.argtypes=[ctypes.c_char_p,ctypes.c_char_p];cls.reference.restype=ctypes.c_char_p
    @classmethod
    def tearDownClass(cls):cls.reference_dir.cleanup()
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def assert_drawing(self,component):
        expected=json.loads(self.reference(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode(),component['id'].encode()))
        actual=dict(surfaces=[{k:s[k] for k in ('rows','cols','points','normals')} for s in component['surfaces']],paths=component['paths'])
        self.assertEqual(actual,expected)
        for p in component['params']:self.assertEqual(p['value'],self.v.GetParmVal(p['id']))

    def persisted(self,component):
        # Native ParmContainer iteration order changes after file reload.
        # Keep every parameter ID and every value; only canonicalize ordering.
        return dict(component,params=sorted(component['params'],key=lambda p:p['id']))

    def test_both_wire_imports_and_plot3d_binary_layouts_match_native_drawings(self):
        v=self.v;hrm=self.path/'native.hrm';v.ExportFile(str(hrm),v.SET_ALL,v.EXPORT_XSEC)
        fixtures=[('XSEC_WIRE',hrm.read_bytes()),('PLOT3D_WIRE',plot3d())]
        fixtures += [('PLOT3D_WIRE',plot3d(True,endian,precision,iblank)) for endian in ['<','>'] for precision in ['f','d'] for iblank in [False,True]]
        source=self.model.read_bytes()
        for fmt,raw in fixtures:
            with self.subTest(format=fmt,header=raw[:16]):
                state,target=self.worker(dict(action='mutate',operation='geometry-import',format=fmt,content=base64.b64encode(raw).decode(),name='Imported wire blocks'))
                wires=[c for c in state['components'] if c['type']=='WireFrame'];self.assertTrue(wires)
                v.ClearVSPModel();v.ReadVSPFile(str(target));v.Update()
                for c in wires:self.assert_drawing(c)
                if fmt=='PLOT3D_WIRE':
                    self.assertEqual(len(wires),3);self.assertEqual(sum(len(c['paths']) for c in wires),6)
                    self.assertEqual(sum(len(c['surfaces']) for c in wires),1)
                reopened,_=self.worker(dict(action='state'),target)
                self.assertEqual([self.persisted(c) for c in reopened['components'] if c['type']=='WireFrame'],[self.persisted(c) for c in wires])
                self.assertEqual(self.model.read_bytes(),source)

    def test_complete_settings_transforms_patches_empty_and_recovery_match_native(self):
        v=self.v
        state,model=self.worker(dict(action='mutate',operation='geometry-import',format='PLOT3D_WIRE',content=base64.b64encode(plot3d()).decode()))
        gid=next(c['id'] for c in state['components'] if c['type']=='WireFrame' and c['surfaces'])
        def component(state):return next(c for c in state['components'] if c['id']==gid)
        # Every transform is evaluated in the SDK before comparing the worker.
        for name,value in [('X_Rel_Location',2.75),('Y_Rel_Location',-1.3),('Z_Rel_Location',.6),('X_Rel_Rotation',17),('Y_Rel_Rotation',-23),('Z_Rel_Rotation',31),('Scale',1.8)]:
            before_points=component(state)['surfaces'][0]['points']
            v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update();pid=v.FindParm(gid,name,'XForm');self.assertTrue(pid)
            v.SetParmValUpdate(pid,value);v.Update()
            state,model=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),model);self.assert_drawing(component(state))
            self.assertNotEqual(component(state)['surfaces'][0]['points'],before_points)
        values={p['name']:p['value'] for p in component(state)['wireSettings']['fields']}
        variants=[dict(WireType=1,InvertFlag=1,FlipIJFlag=1,RevIFlag=1,RevJFlag=1,ISkipStart=1,ISkipEnd=1,JSkipStart=1,JSkipEnd=1,IStride=2,JStride=2)]
        variants += [{n:patch for n in ['IStartPatchType','IEndPatchType','JStartPatchType','JEndPatchType']} for patch in [v.PATCH_POINT,v.PATCH_LINE,v.PATCH_COPY,v.PATCH_HALFWAY,v.PATCH_NONE]]
        variants += [dict(ISkipStart=100),dict(ISkipStart=0,ISkipEnd=0,JSkipStart=0,JSkipEnd=0)]
        for edits in variants:
            values.update(edits);v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update()
            fields=component(state)['wireSettings']['fields']
            for p in fields:v.SetParmValUpdate(p['id'],values[p['name']])
            v.Update()
            state,model=self.worker(dict(action='mutate',operation='wire-settings',geom=gid,values=values),model);c=component(state);self.assert_drawing(c)
            if values['ISkipStart']==100:self.assertFalse(c['surfaces']);self.assertFalse(c['paths']);self.assertTrue(any('reduce trimming' in w for w in state['warnings']))
            else:self.assertTrue(c['surfaces'] or c['paths'])
            reopened,_=self.worker(dict(action='state'),model);self.assertEqual(self.persisted(component(reopened)),self.persisted(c))
        locked={p['name'] for p in component(state)['params'] if p.get('active') is False}
        self.assertTrue({'Sym_Planar_Flag','Sym_Axial_Flag','Sym_Rot_N','Density'}.issubset(locked))
        before=model.read_bytes()
        for name,value in [('IStride',0),('ISkipEnd',1.5),('JStride',float('nan')),('InvertFlag',2),('IStartPatchType',5)]:
            bad=dict(values);bad[name]=value
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='wire-settings',geom=gid,values=bad),model)
            self.assertEqual(model.read_bytes(),before)
            target=max((p for p in self.path.iterdir() if p.is_dir() and p.name.isdigit()),key=lambda p:int(p.name))/'aircraft.vsp3'
            self.assertEqual(target.read_bytes(),before)

    def test_single_imported_wire_point_is_visible_and_query_preserves_file(self):
        raw=b'1\n1 1 1\n2.5\n-3\n4.25\n'
        state,model=self.worker(dict(action='mutate',operation='geometry-import',format='PLOT3D_WIRE',content=base64.b64encode(raw).decode()))
        c=next(c for c in state['components'] if c['type']=='WireFrame')
        self.assertEqual(c['points'],[[2.5,-3,4.25]])
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update();self.assert_drawing(c)
        before=model.read_bytes();self.worker(dict(action='state'),model);self.assertEqual(model.read_bytes(),before)

    def test_native_wire_import_groups_honor_parent_and_keep_complete_subtrees(self):
        v=self.v;hrm=self.path/'parented.hrm';v.ExportFile(str(hrm),v.SET_ALL,v.EXPORT_XSEC)
        source=self.model.read_bytes()
        for fmt,raw in [('XSEC_WIRE',hrm.read_bytes()),('PLOT3D_WIRE',plot3d(True,'>','f',True))]:
            state,model=self.worker(dict(action='mutate',operation='geometry-import',format=fmt,parent=self.gid,content=base64.b64encode(raw).decode()))
            imported=[c for c in state['components'] if c['id']!=self.gid];ids={c['id'] for c in imported}
            roots=[c for c in imported if c['parent'] not in ids];self.assertEqual(len(roots),1);self.assertEqual(roots[0]['parent'],self.gid)
            wires=[c for c in imported if c['type']=='WireFrame'];self.assertTrue(wires);self.assertTrue(all(c['parent']==roots[0]['id'] for c in wires))
            v.ClearVSPModel();v.ReadVSPFile(str(model));v.Update()
            for c in wires:self.assert_drawing(c)
            reopened,_=self.worker(dict(action='state'),model)
            self.assertEqual({c['id']:c['parent'] for c in reopened['components']},{c['id']:c['parent'] for c in state['components']})
            self.assertEqual(self.model.read_bytes(),source)
