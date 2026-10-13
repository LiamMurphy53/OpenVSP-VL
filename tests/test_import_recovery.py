"""Unsafe native import records fail before parsing; valid geometry stays native."""
import base64
from pathlib import Path
import sys
import unittest
import test_native
from vsp_runtime import load


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class ImportRecovery(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixtures(self):
        v=self.v;prop=v.AddGeom('PROP');v.Update();v.SetBEMPropID(prop)
        files={}
        for fmt,enum,ext in [('NASCART',v.EXPORT_NASCART,'dat'),('BEM',v.EXPORT_BEM,'bem')]:
            p=self.path/('native.'+ext);v.ExportFile(str(p),v.SET_ALL,enum);files[fmt]=p.read_bytes()
        files['POINTS']=b'0, 0, 0\n1 2 3\n-2.5 4e-2 6\n0x1p1, -0x1p-2, 0x1p8\n'
        files['VSP_V2']=b'<Vsp_Geometry><Version>2</Version><Name>Legacy fixture</Name><Component_List><Component><Type>Pod</Type></Component></Component_List></Vsp_Geometry>'
        return files

    def test_complete_valid_imports_match_direct_native_parameters_and_geometry(self):
        v=self.v;fixtures=self.fixtures();source=self.model.read_bytes()
        enums={'NASCART':v.IMPORT_NASCART,'BEM':v.IMPORT_BEM,'POINTS':v.IMPORT_PTS,'VSP_V2':v.IMPORT_V2}
        for fmt,raw in fixtures.items():
            with self.subTest(format=fmt):
                state,target=self.worker(dict(action='mutate',operation='geometry-import',format=fmt,content=base64.b64encode(raw).decode(),name='Imported native geometry'))
                imported=[c for c in state['components'] if c['id']!=self.gid]
                self.assertEqual(len(imported),1);actual=imported[0]
                if fmt!='VSP_V2':self.assertEqual(actual['name'],'Imported native geometry')
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();p=self.path/'direct-import';p.write_bytes(raw)
                before=set(v.FindGeoms());gid=v.ImportFile(str(p),enums[fmt],'');v.Update();added=set(v.FindGeoms())-before
                self.assertEqual(len(added),1)
                if fmt=='VSP_V2':self.assertEqual(gid,'');gid=next(iter(added))
                else:self.assertIn(gid,added);v.SetGeomName(gid,'Imported native geometry');v.Update()
                expected={(v.GetParmName(pid),v.GetParmGroupName(pid)):v.GetParmVal(pid) for pid in v.GetGeomParmIDs(gid)}
                self.assertEqual({(p['name'],p['rawGroup']):p['value'] for p in actual['params']},expected)
                self.assertEqual(actual['type'],v.GetGeomTypeName(gid))
                if fmt=='POINTS':
                    self.assertEqual(actual['points'],[[p.x(),p.y(),p.z()] for p in v.GetPtCloudPnts(gid)])
                elif fmt=='NASCART':
                    rid=v.CreateGeomResults(gid,'Independent import geometry')
                    self.assertEqual(actual['mesh']['points'],[[p.x(),p.y(),p.z()] for p in v.GetVec3dResults(rid,'Tri_Pnts')])
                    self.assertEqual(actual['mesh']['triangles'],[list(t) for t in zip(*[list(v.GetIntResults(rid,'Tri_Index'+str(i))) for i in range(3)])])
                else:
                    self.assertEqual(len(actual['surfaces']),v.GetTotalNumSurfs(gid))
                    for surface in actual['surfaces']:
                        index=surface['index'];u,w=v.GetUWTess01(gid,index%max(1,v.GetNumMainSurfs(gid)))
                        points=v.CompVecPnt01(gid,index,[a for a in u for b in w],[b for a in u for b in w])
                        self.assertEqual(surface['points'],[[p.x(),p.y(),p.z()] for p in points])
                reopened,_=self.worker(dict(action='state'),target)
                saved=next(c for c in reopened['components'] if c['id']==actual['id'])
                for key in ['type','surfaces','mesh','points']:
                    if key in actual:self.assertEqual(saved[key],actual[key])
                self.assertEqual(self.model.read_bytes(),source)

    def test_malformed_records_preserve_complete_native_model(self):
        fixtures=self.fixtures();source=self.model.read_bytes()
        cases=[(fmt,b'This is not a geometry file.\n') for fmt in fixtures]
        cases += [('POINTS',b'0 1\n'),('POINTS',b'0 1 nan\n'),('POINTS',b'0 1 2\ninvalid\n'),('POINTS',b'\xef\xbb\xbf0 1 2\n'),
                  ('NASCART',b'9'*5000+b' 1\n'),
                  ('NASCART',b'3 1\n0 0 0\n1 0 0\n0 1 0\n1 2 4 0\n'),('NASCART',b'999999999 1\n0 0 0\n'),
                  ('NASCART',b'3 1\n0 0 0\n1e300 0 0\n0 1 0\n1 2 3 0\n'),('VSP_V2',b'<Vsp_Geometry>'),
                  ('VSP_V2',b'<Other/>'),('VSP_V2',b'<Vsp_Geometry/>')]
        bem=fixtures['BEM']
        cases += [('POINTS','١ ٢ ٣\n'.encode()),('POINTS','\u00a00 1 2\n'.encode()),('NASCART','٣ ١\n'.encode()),
                  ('BEM',b'\n'+bem),('BEM',bem.replace(b'\n','\u2028'.encode())),
                  ('BEM',b'x'*255+b'\n'+b'\n'.join(bem.splitlines()[1:])),
                  ('BEM',bem.replace(b'Num_Sections: 12',b'Num_Sections: 0')),('BEM',b'\n'.join(bem.splitlines()[:14])),
                  ('BEM',bem.replace(b'Diameter: 30.00000000',b'Diameter: nan'))]
        for fmt,raw in cases:
            with self.subTest(format=fmt,payload=raw[:60]):
                with self.assertRaisesRegex(ValueError,fmt+':'):
                    self.worker(dict(action='mutate',operation='geometry-import',format=fmt,content=base64.b64encode(raw).decode()))
                target=max((p for p in self.path.iterdir() if p.is_dir() and p.name.isdigit()),key=lambda p:int(p.name))/'aircraft.vsp3'
                self.assertEqual(target.read_bytes(),source)
                self.assertEqual(self.model.read_bytes(),source)

    def test_imported_subtrees_honor_selected_native_parent(self):
        v=self.v;fixtures=self.fixtures();source=self.model.read_bytes()
        enums={'NASCART':v.IMPORT_NASCART,'BEM':v.IMPORT_BEM,'POINTS':v.IMPORT_PTS,'VSP_V2':v.IMPORT_V2}
        for fmt,raw in fixtures.items():
            with self.subTest(format=fmt):
                state,target=self.worker(dict(action='mutate',operation='geometry-import',format=fmt,parent=self.gid,content=base64.b64encode(raw).decode()))
                imported=[c for c in state['components'] if c['id']!=self.gid];self.assertEqual(len(imported),1);actual=imported[0]
                self.assertEqual(actual['parent'],self.gid)
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();p=self.path/'parented-import';p.write_bytes(raw)
                before=set(v.FindGeoms());v.ImportFile(str(p),enums[fmt],self.gid);v.Update();added=set(v.FindGeoms())-before;self.assertEqual(len(added),1);gid=next(iter(added))
                if v.GetGeomParent(gid)!=self.gid:v.SetGeomParent(gid,self.gid)
                v.Update()
                self.assertEqual({(p['name'],p['rawGroup']):p['value'] for p in actual['params']},{(v.GetParmName(p),v.GetParmGroupName(p)):v.GetParmVal(p) for p in v.GetGeomParmIDs(gid)})
                if fmt=='POINTS':self.assertEqual(actual['points'],[[p.x(),p.y(),p.z()] for p in v.GetPtCloudPnts(gid)])
                elif fmt=='NASCART':
                    rid=v.CreateGeomResults(gid,'Independent parented import');self.assertEqual(actual['mesh']['points'],[[p.x(),p.y(),p.z()] for p in v.GetVec3dResults(rid,'Tri_Pnts')]);v.DeleteResult(rid)
                else:
                    for s in actual['surfaces']:
                        u,w=v.GetUWTess01(gid,s['index']%max(1,v.GetNumMainSurfs(gid)));points=v.CompVecPnt01(gid,s['index'],[a for a in u for b in w],[b for a in u for b in w])
                        self.assertEqual(s['points'],[[p.x(),p.y(),p.z()] for p in points])
                reopened,_=self.worker(dict(action='state'),target);self.assertEqual(next(c for c in reopened['components'] if c['id']==actual['id'])['parent'],self.gid)
                self.assertEqual(self.model.read_bytes(),source)
