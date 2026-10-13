"""Shared point lists agree with independent ordinary-section SDK replacement."""
import sys,unittest
import test_native
from test_curve_point_list import ROWS

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native Python.')
class SharedPointLists(unittest.TestCase):
    setUpClass=classmethod(test_native.NativeIntegration.setUpClass.__func__)
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        import native_bor_curves,native_region_curves,native_auxiliary_controls as auxiliary,native_references
        v=self.v;bor=v.AddGeom('BODYOFREVOLUTION');region=v.AddSubSurf(self.gid,v.SS_XSEC_CURVE)
        index=v.AddFeaStruct(self.gid);sid=v.GetFeaStructID(self.gid,index);fea=v.AddFeaSubSurf(self.gid,index,v.SS_XSEC_CURVE)
        aux=v.AddGeom('AUXILIARY');v.SetParmValUpdate(aux,'AuxiliaryGeomType','Design',v.AUX_GEOM_SUPER_CONE)
        native_bor_curves.mutate(v,dict(operation='bor-curve-convert',geom=bor))
        native_region_curves.mutate(v,dict(operation='region-curve-convert',geom=self.gid,id=region))
        native_region_curves.mutate(v,dict(operation='region-curve-convert',structure=sid,id=fea))
        auxiliary.mutate(v,dict(operation='auxiliary-profile-convert',geom=aux));v.Update();refs=native_references.references(v)
        cases=[('bor',dict(kind='bor',geom=bor),dict(operation='bor-curve-replace-points',geom=bor),native_bor_curves.container(v,bor)),('controls',dict(kind='region',geom=self.gid,id=region),dict(operation='region-curve-replace-points',geom=self.gid,id=region),refs[region]['curveID']),('structuralSubsurfaces',dict(kind='region',structure=sid,id=fea),dict(operation='region-curve-replace-points',structure=sid,id=fea),refs[fea]['curveID']),('auxiliary',dict(kind='auxiliary',geom=aux),dict(operation='auxiliary-profile-edit-replace-points',geom=aux),auxiliary.curve_container(v,aux))]
        for _,_,_,cid in cases:v.SetParmValUpdate(next(p for p in v.FindContainerParmIDs(cid) if v.GetParmName(p)=='SymType'),v.SYM_NONE)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL);return cases

    def curve(self,data,key,request):
        if key=='bor':return next(r for r in data['tools']['bodiesOfRevolution'] if r['id']==request['geom'])['editable']
        if key=='auxiliary':return next(r for r in data['tools']['auxiliary'] if r['id']==request['geom'])['controls']['profile']
        return next(r for r in data['tools'][key] if r['id']==request['id'])['sectionCurve']

    def test_all_shared_owners_and_interpolations_match_native_sdk(self):
        import native_bor_clipboard,native_region_curves,native_auxiliary_controls as auxiliary
        v=self.v;cases=self.fixture()
        for key,source,request,cid in cases:
            for typ in ('LINEAR','PCHIP','CEDIT'):
                with self.subTest(owner=key,interpolation=typ):
                    # Native clipboard decoding grows existing arrays but does not shrink them.
                    # A 25-point reference exceeds each native preset's initial count.
                    rows=[[i/24,*ROWS[i%4][1:4],0] for i in range(25)]
                    scratch=v.AddGeom('STACK');native_bor_clipboard.copy(v,source);v.PasteXSecCurve(scratch,1)
                    x=v.GetXSec(v.GetXSecSurf(scratch,0),1);v.EditXSecConvertTo(x,getattr(v,typ));v.SetEditXSecPnts(x,[r[0] for r in rows],[v.vec3d(*r[1:4]) for r in rows],[r[4] for r in rows]);v.Update()
                    points=[[p.x(),p.y(),p.z()] for p in v.GetEditXSecCtrlVec(x,True)]
                    # Transfer the SDK-encoded native curve into the destination's
                    # saved native record, then let a fresh official engine decode it.
                    # Clipboard CopyFrom retains old points and clamps U to old limits.
                    import copy,xml.etree.ElementTree as ET
                    encoded=self.path/'sdk-profile.vsp3';v.WriteVSPFile(str(encoded),v.SET_ALL)
                    source_cid=v.GetParmContainer(v.GetXSecParm(x,'Theta'))
                    profile=next(n for n in ET.parse(encoded).iter('XSecCurve') if n.findtext('ParmContainer/ID')==source_cid)
                    tree=ET.parse(self.model);target=next(n for n in tree.iter('XSecCurve') if n.findtext('ParmContainer/ID')==cid)
                    parent=next(n for n in tree.iter() if target in list(n));replacement=copy.deepcopy(profile);replacement.find('ParmContainer/ID').text=cid
                    parent.remove(target);parent.append(replacement);reference=self.path/'reference.vsp3';tree.write(reference,encoding='utf-8',xml_declaration=True)
                    v.DeleteGeom(scratch);v.Update()
                    expected,_=self.worker(dict(action='state'),reference)
                    state,path=self.worker(dict(action='mutate',type=typ,rows=rows,**request));cold,_=self.worker(dict(action='state'),path)
                    for result in (state,cold):
                        actual=self.curve(result,key,request);ref=self.curve(expected,key,request)
                        self.assertEqual(actual['controlPoints'],points);self.assertEqual(actual['rounding'],ref['rounding']);self.assertEqual(actual['curveU'],ref['curveU'])
                        g=request.get('geom',self.gid)
                        self.assertEqual(next(c['surfaces'] for c in result['components'] if c['id']==g),next(c['surfaces'] for c in expected['components'] if c['id']==g))
                    if key in ('controls','structuralSubsurfaces'):
                        query=dict(action='query',operation='structural-preview',structure=request['structure']) if 'structure' in request else dict(action='query',operation='region-boundaries',geom=request['geom'])
                        a,_=self.worker(query,path);b,_=self.worker(query,reference)
                        if 'structure' in request:self.assertEqual(a['regions'],b['regions'])
                        else:
                            # Native DrawObj IDs are regenerated in each process.
                            def boundaries(data):return [(r['id'],[(p['points'],p['u'],p['w']) for p in r['paths']]) for r in data['regions']]
                            self.assertEqual(boundaries(a),boundaries(b))

    def test_short_lists_really_remove_old_points_and_survive_reopening(self):
        for key,source,request,cid in self.fixture():
            state,path=self.worker(dict(action='mutate',type='LINEAR',rows=ROWS,**request));cold,_=self.worker(dict(action='state'),path)
            for result in (state,cold):
                curve=self.curve(result,key,request)
                self.assertEqual(curve['controlPoints'],[r[1:4] for r in ROWS]);self.assertEqual(curve['rounding'],[r[4] for r in ROWS])
            self.assertEqual({c['id']:c['surfaces'] for c in state['components']},{c['id']:c['surfaces'] for c in cold['components']})

    def test_shared_invalid_rows_and_referenced_points_preserve_candidate(self):
        v=self.v;cases=self.fixture()
        for key,source,request,cid in cases:
            before=self.model.read_bytes();existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',type='CEDIT',rows=ROWS,**request))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)
            pid=next(p for p in v.FindContainerParmIDs(cid) if v.GetParmName(p)=='X_3');v.AddAttributeParm(v.GetChildCollection(v.GetVehicleID()),'Shared point '+key,pid)
        v.WriteVSPFile(str(self.model),v.SET_ALL);before=self.model.read_bytes()
        for _,_,request,_ in cases:
            existing=set(self.path.glob('*/aircraft.vsp3'))
            with self.assertRaisesRegex(ValueError,'point IDs used by parameter reference'):
                self.worker(dict(action='mutate',type='LINEAR',rows=ROWS,**request))
            candidate=next(iter(set(self.path.glob('*/aircraft.vsp3'))-existing));self.assertEqual(candidate.read_bytes(),before)

if __name__=='__main__':unittest.main()
