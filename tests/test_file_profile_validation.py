"""Shared native section-file validation across all file-profile editors."""
import sys
import unittest
import test_native

VALID='OPENVSP_XSEC_FILE_V1\n1 0\n0 -1\n-1 0\n0 1\n1 0\n'
UNSAFE='OPENVSP_XSEC_FILE_V1\n1 0\n0 1\n-1 0\n0 -1\n1 0\n'


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class FileProfiles(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_unsafe_order_preserves_candidate_for_four_editors(self):
        v=self.v;stack=v.AddGeom('STACK');bor=v.AddGeom('BODYOFREVOLUTION')
        region=v.AddSubSurf(self.gid,v.SS_XSEC_CURVE);index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index);fea=v.AddFeaSubSurf(self.gid,index,v.SS_XSEC_CURVE)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        requests=[dict(operation='section-profile-import',geom=stack,surface=0,index=1),dict(operation='bor-profile',geom=bor),dict(operation='region-curve-import',geom=self.gid,id=region,format='section'),dict(operation='region-curve-import',structure=sid,id=fea,format='section')]
        for request in requests:
            existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,'point order'):
                self.worker(dict(action='mutate',content=UNSAFE,**request))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing))
            self.assertEqual(candidate.read_bytes(),before)

    def test_valid_section_and_bor_imports_match_native_saved_geometry(self):
        v=self.v;stack=v.AddGeom('STACK');bor=v.AddGeom('BODYOFREVOLUTION');v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        source=self.path/'profile.fxs';source.write_text(VALID)
        for gid,operation in [(stack,'section-profile-import'),(bor,'bor-profile')]:
            v.ClearVSPModel();v.ReadVSPFile(str(self.model))
            if gid==stack:
                surf=v.GetXSecSurf(gid,0);v.ChangeXSecShape(surf,1,v.XS_FILE_FUSE);v.ReadFileXSec(v.GetXSec(surf,1),str(source))
            else:v.ChangeBORXSecShape(gid,v.XS_FILE_FUSE);v.ReadBORFileXSec(gid,str(source))
            v.Update();reference=self.path/'direct.vsp3';v.WriteVSPFile(str(reference),v.SET_ALL)
            expected,_=self.worker(dict(action='state'),reference)
            request=dict(action='mutate',operation=operation,geom=gid,content=VALID)
            if gid==stack:request.update(surface=0,index=1)
            actual,path=self.worker(request)
            expected=next(c for c in expected['components'] if c['id']==gid)['surfaces']
            self.assertEqual(next(c for c in actual['components'] if c['id']==gid)['surfaces'],expected)
            reopened,_=self.worker(dict(action='state'),path)
            self.assertEqual(next(c for c in reopened['components'] if c['id']==gid)['surfaces'],expected)


if __name__=='__main__':unittest.main()
