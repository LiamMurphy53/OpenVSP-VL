"""Native import record variants and atomic malformed-file recovery."""
import base64
import ctypes
import json
from pathlib import Path
import struct
import sys
import unittest
import test_native
import test_wire_geometry as wire_native_tests
from vsp_runtime import distribution


STL_ASCII=b'''solid fixture
facet normal 0 0 1
outer loop
vertex -3 2 0
vertex 1 -2 1
vertex 2 3 -1
endloop
endfacet
endsolid fixture
'''
STL_BINARY=b'Native STL fixture'.ljust(80,b'\0')+struct.pack('<i',1)+struct.pack('<12fH',0,0,1,-3,2,0,1,-2,1,2,3,-1,32769)


def record(data,endian='<'):
    return struct.pack(endian+'i',len(data))+data+struct.pack(endian+'i',len(data))


def cart3d(binary=False,endian='<',precision='f',tags='complete',hexadecimal=False):
    coords=[-3.125,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.,1.];conn=[1,2,3,1,3,4]
    if not binary:
        value=lambda n:float(n).hex() if hexadecimal else str(n)
        raw=('4 2\n'+' '.join(value(x) for x in coords)+'\n'+' '.join(map(str,conn))+'\n').encode()
        return raw+{'complete':b'7 -2\n','partial':b'7\n','absent':b'','malformed':b'7 unknown\n'}[tags]
    raw=record(struct.pack(endian+'2i',4,2),endian)+record(struct.pack(endian+'12'+precision,*coords),endian)+record(struct.pack(endian+'6i',*conn),endian)
    return raw+{'complete':record(struct.pack(endian+'2i',7,-2),endian),'partial':record(struct.pack(endian+'i',7),endian),'absent':b'','malformed':b'\x08\0\0\0\x07\0'}[tags]


def plot3d(binary=False,endian='<',precision='f',ndim=3,arrays=3,hexadecimal=False):
    dims=[(3,2,2 if ndim==3 else 1),(4,1,1)];data=[]
    for ni,nj,nk in dims:
        points=[(i+.1*k,j+.2*k,i*.1+j*.2+.3*k) for k in range(nk) for j in range(nj) for i in range(ni)]
        values=[p[a] for a in range(2 if arrays==2 else 3) for p in points]
        if binary:
            chunk=struct.pack(endian+str(len(values))+precision,*values)
            if arrays==4:chunk+=struct.pack(endian+str(len(points))+'i',*([1]*len(points)))
            data.append(chunk)
        else:
            if arrays==4:values.extend([1]*len(points))
            data.append(' '.join(float(n).hex() if hexadecimal else str(n) for n in values))
    if not binary:return ('2\n'+'\n'.join(' '.join(map(str,d)) for d in dims)+'\n'+'\n'.join(data)+'\n').encode()
    return record(struct.pack(endian+'i',2),endian)+record(struct.pack(endian+str(ndim*2)+'i',*[n for d in dims for n in d[:ndim]]),endian)+b''.join(record(d,endian) for d in data)


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class ImportRecords(unittest.TestCase):
    setUpClass=classmethod(wire_native_tests.WireGeometry.setUpClass.__func__)
    tearDownClass=classmethod(wire_native_tests.WireGeometry.tearDownClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def native_import(self,fmt,raw):
        v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();p=self.path/'direct-import';p.write_bytes(raw)
        before=set(v.FindGeoms());v.ImportFile(str(p),getattr(v,{'STL':'IMPORT_STL','CART3D':'IMPORT_CART3D_TRI','XSEC_MESH':'IMPORT_XSEC_MESH','XSEC_WIRE':'IMPORT_XSEC_WIRE','PLOT3D_WIRE':'IMPORT_P3D_WIRE'}[fmt]),'');v.Update()
        return [g for g in v.FindGeoms() if g not in before]

    def compare(self,fmt,raw,reference=None):
        state,model=self.worker(dict(action='mutate',operation='geometry-import',format=fmt,content=base64.b64encode(raw).decode()))
        actual=[c for c in state['components'] if c['id']!=self.gid];expected=self.native_import(fmt,raw if reference is None else reference)
        self.assertEqual([c['type'] for c in actual],[self.v.GetGeomTypeName(g) for g in expected]);self.assertTrue(expected)
        for c,g in zip(actual,expected):
            self.assertEqual({(p['name'],p['rawGroup']):p['value'] for p in c['params']},{(self.v.GetParmName(p),self.v.GetParmGroupName(p)):self.v.GetParmVal(p) for p in self.v.GetGeomParmIDs(g)})
            if c['type']=='Mesh':
                rid=self.v.CreateGeomResults(g,'Independent import mesh')
                self.assertEqual(c['mesh']['points'],[[p.x(),p.y(),p.z()] for p in self.v.GetVec3dResults(rid,'Tri_Pnts')])
                self.assertEqual(c['mesh']['triangles'],[list(t) for t in zip(*[list(self.v.GetIntResults(rid,'Tri_Index'+str(i))) for i in range(3)])]);self.v.DeleteResult(rid)
            elif c['type']=='WireFrame':
                native=json.loads(self.reference(str(distribution()/'python/openvsp/openvsp/_vsp.so').encode(),g.encode()))
                self.assertEqual(dict(surfaces=[{k:s[k] for k in ['rows','cols','points','normals']} for s in c['surfaces']],paths=c['paths']),native)
        reopened,_=self.worker(dict(action='state'),model)
        normalized=lambda c:dict(c,params=sorted(c['params'],key=lambda p:p['id']))
        self.assertEqual([normalized(c) for c in reopened['components'] if c['id']!=self.gid],[normalized(c) for c in actual])
        return state,model

    def test_native_export_files_for_all_five_remaining_import_families(self):
        v=self.v;source=self.model.read_bytes()
        for fmt,enum,ext in [('STL',v.EXPORT_STL,'stl'),('CART3D',v.EXPORT_CART3D,'tri'),('XSEC_MESH',v.EXPORT_XSEC,'hrm'),('XSEC_WIRE',v.EXPORT_XSEC,'hrm'),('PLOT3D_WIRE',v.EXPORT_PLOT3D,'p3d')]:
            with self.subTest(format=fmt):
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();p=self.path/('native.'+ext);v.ExportFile(str(p),v.SET_ALL,enum);self.compare(fmt,p.read_bytes())
                self.assertEqual(self.model.read_bytes(),source)

    def test_binary_and_formatted_variants_preserve_complete_native_geometry(self):
        from native_import_validation import validate
        fixtures=[('STL',STL_BINARY,STL_ASCII),('STL',STL_ASCII.replace(b'\n',b'\n\n'),STL_ASCII),
                  ('STL',STL_ASCII.split(b'endsolid')[0].rstrip(),STL_ASCII),
                  ('STL',STL_ASCII.replace(b'solid fixture',b'solid UTF8 \xc3\xa9'),STL_ASCII)]
        self.assertEqual(validate(STL_BINARY,'STL')[80:],STL_BINARY[80:])
        fixtures += [('CART3D',cart3d(tags=tags),None) for tags in ['complete','partial','absent','malformed']]
        fixtures += [('CART3D',cart3d(True,e,p,tags),None) for e in ['<','>'] for p in ['f','d'] for tags in ['complete','partial','absent','malformed']]
        fixtures += [('CART3D',cart3d(hexadecimal=True),None)]
        fixtures += [('PLOT3D_WIRE',plot3d(arrays=a),None) for a in [2,3,4]]
        fixtures += [('PLOT3D_WIRE',plot3d(True,e,p,n,a),None) for e in ['<','>'] for p in ['f','d'] for n in [2,3] for a in [2,3,4]]
        fixtures += [('PLOT3D_WIRE',plot3d(hexadecimal=True),None)]
        fixtures += [('PLOT3D_WIRE',b'0'*511+b'1\n1 1 1\n0 0 0\n',None)]
        source=self.model.read_bytes()
        for fmt,raw,reference in fixtures:
            with self.subTest(format=fmt,header=raw[:24]):
                self.compare(fmt,raw,reference);self.assertEqual(self.model.read_bytes(),source)
                if fmt!='STL':self.assertEqual(validate(raw,fmt),raw)

    def test_incomplete_nonfinite_and_unsafe_records_preserve_entire_aircraft(self):
        from native_import_validation import validate
        v=self.v;p=self.path/'valid.hrm';v.ExportFile(str(p),v.SET_ALL,v.EXPORT_XSEC);hrm=p.read_bytes()
        cases=[(fmt,b'Not a geometry file.\n') for fmt in ['STL','CART3D','XSEC_MESH','XSEC_WIRE','PLOT3D_WIRE']]
        cases += [('STL',STL_BINARY[:-1]),('STL',STL_BINARY[:80]+struct.pack('<i',100000000)+STL_BINARY[84:]),
                  ('STL',STL_BINARY[:84]+struct.pack('<f',float('nan'))+STL_BINARY[88:]),
                  ('STL',STL_ASCII.replace(b'vertex 1 -2 1',b'vertex nan -2 1')),('STL',STL_ASCII.replace(b'endloop\n',b'')),
                  ('STL',STL_ASCII.replace(b'vertex 1 -2 1',b'vertex 1e300 -2 1'))]
        cases += [('CART3D',b'999999999 1\n0 0 0\n'),('CART3D',cart3d().replace(b'1 2 3 1 3 4',b'1 2 5 1 3 4')),
                  ('CART3D',b'9'*5000+b' 1\n'),
                  ('CART3D',cart3d().replace(b'-3.125',b'nan')),('CART3D',cart3d(True)[:30]),
                  ('CART3D',cart3d(True)[:8]+struct.pack('<i',8)+cart3d(True)[12:]),
                  ('CART3D',record(struct.pack('<2i',4,2))+record(struct.pack('<12f',*([float('inf')]*12))))]
        for fmt in ['XSEC_MESH','XSEC_WIRE']:
            cases += [(fmt,hrm[:100]),(fmt,hrm.replace(b'CROSS SECTIONS',b'UNKNOWN RECORD',1)),
                      (fmt,b'HERMITE INPUT FILE\nNUMBER OF COMPONENTS = 1\nGrid\nGROUP NUMBER = 0\nTYPE = 0\nCROSS SECTIONS = 0\nPTS/CROSS SECTION = 2\n'),
                      (fmt,b'HERMITE INPUT FILE\nNUMBER OF COMPONENTS = 1\nGrid\nGROUP NUMBER = 0\nTYPE = 0\nCROSS SECTIONS = 2147483647\nPTS/CROSS SECTION = 2147483647\n0 0 0\n'),
                      (fmt,b'HERMITE INPUT FILE\nNUMBER OF COMPONENTS = 1\nGrid\nGROUP NUMBER = 0\nTYPE = 0\nCROSS SECTIONS = 1\nPTS/CROSS SECTION = 1\n0 nan 0\n')]
        cases += [('PLOT3D_WIRE',b'1\n3 2 1\n0 1 2\n'),('PLOT3D_WIRE',b'1\n-1 2 1\n'),
                  ('PLOT3D_WIRE',b'9'*5000+b'\n'),
                  ('PLOT3D_WIRE',b'1\n2147483647 2147483647 2147483647\n0 0 0\n'),
                  ('PLOT3D_WIRE',plot3d().replace(b'0.0',b'nan',1)),('PLOT3D_WIRE',plot3d(True)[:-1]),
                  ('PLOT3D_WIRE',plot3d(True)[:8]+struct.pack('<i',5)+plot3d(True)[12:]),
                  ('PLOT3D_WIRE',record(struct.pack('<i',1))+record(struct.pack('<3i',3,2,1))+record(struct.pack('<18f',*([float('nan')]*18))))]
        source=self.model.read_bytes()
        for fmt,raw in cases:
            with self.subTest(format=fmt,payload=raw[:24]):
                with self.assertRaisesRegex(ValueError,fmt+':'):validate(raw,fmt)
                with self.assertRaisesRegex(ValueError,fmt+':'):self.worker(dict(action='mutate',operation='geometry-import',format=fmt,content=base64.b64encode(raw).decode()))
                target=max((p for p in self.path.iterdir() if p.is_dir() and p.name.isdigit()),key=lambda p:int(p.name))/'aircraft.vsp3'
                self.assertEqual(target.read_bytes(),source);self.assertEqual(self.model.read_bytes(),source)
        # The platform's native scanf accepts a 512-character count token but
        # rejects this 5001-character zero-padded token. Preserve that native
        # decision and verify complete recovery, rather than treating it as a
        # valid native import or changing its engineering records.
        unsupported=b'0'*5000+b'1\n1 1 1\n0 0 0\n'
        self.assertEqual(self.native_import('PLOT3D_WIRE',unsupported),[])
        self.assertEqual(validate(unsupported,'PLOT3D_WIRE'),unsupported)
        with self.assertRaisesRegex(ValueError,'PLOT3D_WIRE: OpenVSP produced no geometry'):
            self.worker(dict(action='mutate',operation='geometry-import',format='PLOT3D_WIRE',content=base64.b64encode(unsupported).decode()))
        target=max((p for p in self.path.iterdir() if p.is_dir() and p.name.isdigit()),key=lambda p:int(p.name))/'aircraft.vsp3'
        self.assertEqual(target.read_bytes(),source);self.assertEqual(self.model.read_bytes(),source)
