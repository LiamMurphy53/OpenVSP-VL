"""Native section-curve region shape and nested parameter workflows."""
import sys
import unittest
import test_native
from vsp_runtime import load


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class RegionCurves(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def fixture(self):
        v=self.v;self.region=v.AddSubSurf(self.gid,v.SS_XSEC_CURVE)
        self.index=v.AddFeaStruct(self.gid);self.sid=v.GetFeaStructID(self.gid,self.index)
        self.structural=v.AddFeaSubSurf(self.gid,self.index,v.SS_XSEC_CURVE)
        v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)

    def row(self,state,structural=False):
        key='structuralSubsurfaces' if structural else 'controls'
        return next(p for p in state['tools'][key] if p['id']==(self.structural if structural else self.region))

    def test_shape_and_nested_dimensions_use_native_parameters_and_survive_reload(self):
        self.fixture();state,path=self.worker(dict(action='state'))
        for structural in (False,True):
            owner=dict(structure=self.sid) if structural else dict(geom=self.gid)
            region=self.structural if structural else self.region
            state,path=self.worker(dict(action='mutate',operation='region-curve-shape',id=region,shape='XS_ELLIPSE',**owner),path)
            curve=self.row(state,structural)['sectionCurve'];self.assertEqual(curve['type'],self.v.XS_ELLIPSE)
            self.assertFalse({p['id'] for p in curve['params']} & {p['id'] for p in self.row(state,structural)['params']})
            width=next(p for p in curve['params'] if p['name']=='Ellipse_Width')
            state,path=self.worker(dict(action='mutate',operation='parameter',id=width['id'],value=.35),path)
            state,path=self.worker(dict(action='state'),path)
            self.assertEqual(next(p['value'] for p in self.row(state,structural)['sectionCurve']['params'] if p['id']==width['id']),.35)
            # Independent direct SDK parameter edit in a separate native model.
            direct=self.path/('direct-'+str(structural)+'.vsp3');v=self.v
            v.ClearVSPModel();v.ReadVSPFile(str(path));v.Update();v.SetParmVal(width['id'],.6);v.Update();v.WriteVSPFile(str(direct),v.SET_ALL)
            changed,changed_path=self.worker(dict(action='mutate',operation='parameter',id=width['id'],value=.6),path)
            if structural:
                request=dict(action='query',operation='structural-preview',structure=self.sid)
                a,_=self.worker(request,changed_path);b,_=self.worker(request,direct)
                self.assertEqual(a['regions'],b['regions'])
            else:
                request=dict(action='query',operation='region-boundaries',geom=self.gid)
                a,_=self.worker(request,changed_path);b,_=self.worker(request,direct)
                def boundaries(data):return [(r['id'],[(p['points'],p['u'],p['w']) for p in r['paths']]) for r in data['regions']]
                self.assertEqual(boundaries(a),boundaries(b))

    def test_every_native_shape_and_invalid_owner_preserve_native_region_identity(self):
        from native_special import SHAPES
        self.fixture();path=self.model
        for structural in (False,True):
            owner=dict(structure=self.sid) if structural else dict(geom=self.gid)
            region=self.structural if structural else self.region
            for shape in SHAPES:
                state,path=self.worker(dict(action='mutate',operation='region-curve-shape',id=region,shape=shape,**owner),path)
                row=self.row(state,structural);self.assertEqual(row['id'],region)
                self.assertEqual(row['sectionCurve']['type'],getattr(self.v,shape))
            before=path.read_bytes()
            for extra in [dict(shape='INVALID'),dict(id='MISSING'),dict(id=self.region if structural else self.structural)]:
                req=dict(action='mutate',operation='region-curve-shape',id=region,shape='XS_CIRCLE',**owner);req.update(extra)
                with self.assertRaises(ValueError):self.worker(req,path)
                self.assertEqual(path.read_bytes(),before)

    def test_copy_between_region_owners_preserves_source_and_target_placement(self):
        self.fixture();state,path=self.worker(dict(action='mutate',operation='region-curve-shape',geom=self.gid,id=self.region,shape='XS_ELLIPSE'))
        for name,value in [('Ellipse_Width',.35),('Ellipse_Height',.2)]:
            pid=next(p['id'] for p in self.row(state)['sectionCurve']['params'] if p['name']==name)
            state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
        source=self.row(state);target=self.row(state,True);placement={p['id']:p['value'] for p in target['params']}
        state,path=self.worker(dict(action='mutate',operation='region-curve-copy-from',structure=self.sid,id=self.structural,source=dict(kind='region',geom=self.gid,id=self.region)),path)
        self.assertEqual(self.row(state),source)
        self.assertEqual({p['id']:p['value'] for p in self.row(state,True)['params']},placement)
        curve=self.row(state,True)['sectionCurve'];self.assertEqual(curve['type'],self.v.XS_ELLIPSE)
        values={p['name']:p['value'] for p in curve['params'] if p['name'].startswith('Ellipse_')}
        self.assertEqual(values,{'Ellipse_Width':.35,'Ellipse_Height':.2})
        before=path.read_bytes()
        for source in [dict(kind='region',geom=self.gid,id='MISSING'),dict(kind='section',geom=self.gid,surface=1,index=0),dict(kind='section',geom=self.gid,index=1.2)]:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='region-curve-copy-from',structure=self.sid,id=self.structural,source=source),path)
            self.assertEqual(path.read_bytes(),before)

    def test_convert_matches_independent_native_section_conversion(self):
        self.fixture();v=self.v
        # Independently convert a normal native section profile of equal size.
        g=v.AddGeom('STACK');surf=v.GetXSecSurf(g,0);v.ChangeXSecShape(surf,1,v.XS_ELLIPSE);x=v.GetXSec(surf,1)
        v.SetXSecWidth(x,.35);v.SetXSecHeight(x,.2);v.ConvertXSecToEdit(g,1);v.Update()
        expected={(v.GetParmGroupName(p),v.GetParmName(p)):v.GetParmVal(p) for p in v.GetXSecParmIDs(x) if v.GetParmName(p).startswith(('X_','Y_','Z_','U_'))}
        self.assertTrue(expected)
        state,path=self.worker(dict(action='mutate',operation='region-curve-shape',geom=self.gid,id=self.region,shape='XS_ELLIPSE'))
        for name,value in [('Ellipse_Width',.35),('Ellipse_Height',.2)]:
            pid=next(p['id'] for p in self.row(state)['sectionCurve']['params'] if p['name']==name)
            state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
        state,path=self.worker(dict(action='mutate',operation='region-curve-convert',geom=self.gid,id=self.region),path)
        curve=self.row(state)['sectionCurve'];self.assertEqual(curve['type'],v.XS_EDIT_CURVE)
        actual={(p['rawGroup'],p['name']):p['value'] for p in curve['params'] if p['name'].startswith(('X_','Y_','Z_','U_'))}
        self.assertEqual(actual,expected)
        state,path=self.worker(dict(action='mutate',operation='region-curve-copy-from',structure=self.sid,id=self.structural,source=dict(kind='region',geom=self.gid,id=self.region)),path)
        self.assertEqual(self.row(state,True)['sectionCurve']['type'],v.XS_EDIT_CURVE)

    def test_file_imports_match_independent_native_readers_without_scratch_geometry(self):
        import xml.etree.ElementTree as ET
        from vsp_runtime import distribution
        self.fixture();baseline,_=self.worker(dict(action='state'))
        samples=[('section','OPENVSP_XSEC_FILE_V1\n0.2 0\n0 -0.15\n-0.2 0\n0 0.15\n0.2 0\n')]
        samples += [('airfoil',(distribution()/'airfoil'/f).read_text()) for f in ('e205_Selig.dat','clarky_Lednicer.dat','N0012_VSP.af')]
        for fmt,text in samples:
            v=self.v;v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update()
            scratch=v.AddGeom('STACK');surf=v.GetXSecSurf(scratch,0)
            v.ChangeXSecShape(surf,1,v.XS_FILE_FUSE if fmt=='section' else v.XS_FILE_AIRFOIL);x=v.GetXSec(surf,1)
            source=self.path/'native-input.txt';source.write_text(text)
            if fmt=='section':v.ReadFileXSec(x,str(source))
            else:
                v.ReadFileAirfoil(x,str(source));v.SetXSecWidth(x,1.0)
            v.Update();curve_id=v.GetParmContainer(v.GetXSecParm(x,'Theta'))
            expected={(v.GetParmGroupName(p),v.GetParmName(p)):v.GetParmVal(p) for p in v.FindContainerParmIDs(curve_id)}
            direct=self.path/'independent-file-reader.vsp3';v.WriteVSPFile(str(direct),v.SET_ALL)
            source_curve=next(n for n in ET.parse(direct).findall('.//XSecCurve') if n.findtext('ParmContainer/ID')==curve_id)
            file_tag='FileXSec' if fmt=='section' else 'FileAirfoil'
            def payload(node):return (node.tag,dict(node.attrib),(node.text or '').strip(),[payload(c) for c in node])
            expected_payload=payload(source_curve.find(file_tag))
            for structural in (False,True):
                owner=dict(structure=self.sid) if structural else dict(geom=self.gid)
                state,path=self.worker(dict(action='mutate',operation='region-curve-import',id=self.structural if structural else self.region,format=fmt,content=text,**owner))
                row=self.row(state,structural);curve=row['sectionCurve']
                self.assertEqual(curve['type'],v.XS_FILE_FUSE if fmt=='section' else v.XS_FILE_AIRFOIL)
                actual={(p['rawGroup'],p['name']):p['value'] for p in curve['params']}
                self.assertEqual({k:(actual.get(k),value) for k,value in expected.items() if actual.get(k)!=value},{})
                self.assertEqual({c['id'] for c in state['components']},{c['id'] for c in baseline['components']})
                self.assertEqual({p['id']:p['value'] for p in row['params']},{p['id']:p['value'] for p in self.row(baseline,structural)['params']})
                stored_curve=next(n for n in ET.parse(path).findall('.//XSecCurve') if n.findtext('ParmContainer/ID')==curve['id'])
                self.assertEqual(payload(stored_curve.find(file_tag)),expected_payload)
                loaded,_=self.worker(dict(action='state'),path)
                reopened=self.row(loaded,structural)['sectionCurve']
                self.assertEqual(reopened['id'],curve['id']);self.assertEqual(reopened['type'],curve['type'])
                before_params={p['id']:p for p in curve['params']};after_params={p['id']:p for p in reopened['params']}
                self.assertEqual(set(before_params),set(after_params))
                differences=[(before_params[pid]['name'],k,before_params[pid][k],after_params[pid][k]) for pid in before_params for k in before_params[pid] if before_params[pid][k]!=after_params[pid][k]]
                self.assertEqual(differences,[])

    def test_invalid_file_import_preserves_saved_curve_and_model(self):
        self.fixture();before=self.model.read_bytes()
        bad=[dict(format='section',content='OPENVSP_XSEC_FILE_V1\n'),dict(format='section',content='OPENVSP_XSEC_FILE_V1\n0 0\nwrong\n'),dict(format='section',content='OPENVSP_XSEC_FILE_V1\n0 0\nnan 1\n1 0\n'),dict(format='airfoil',content='not an airfoil'),dict(format='airfoil',content='bad\n0 0\n1 nan\n0.5 0.2\n1 0\n'),dict(format='unknown',content='anything')]
        for extra in bad:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',operation='region-curve-import',structure=self.sid,id=self.structural,**extra))
            self.assertEqual(self.model.read_bytes(),before)

    def test_editable_region_operations_match_independent_native_section_api(self):
        self.fixture();v=self.v
        for structural in (False,True):
            owner=dict(structure=self.sid) if structural else dict(geom=self.gid)
            region=self.structural if structural else self.region
            state,path=self.worker(dict(action='mutate',operation='region-curve-convert',id=region,**owner))
            placement={p['id']:p['value'] for p in self.row(state,structural)['params']}
            v.ClearVSPModel();scratch=v.AddGeom('STACK');surf=v.GetXSecSurf(scratch,0)
            v.ChangeXSecShape(surf,1,v.XS_CIRCLE);x=v.GetXSec(surf,1);v.SetXSecWidth(x,1.0)
            v.ConvertXSecToEdit(scratch,1);v.Update()
            def check(state):
                curve=self.row(state,structural)['sectionCurve']
                self.assertEqual(curve['controlPoints'],[[p.x(),p.y(),p.z()] for p in v.GetEditXSecCtrlVec(x,True)])
                self.assertEqual(curve['curveU'],list(v.GetEditXSecUVec(x)))
                self.assertEqual(curve['fixedU'],list(v.GetEditXSecFixedUVec(x)))
                self.assertEqual(curve['curveType'],int(v.GetParmVal(v.GetXSecParm(x,'CurveType'))))
                self.assertEqual({p['id']:p['value'] for p in self.row(state,structural)['params']},placement)
            check(state)
            operations=[dict(operation='region-curve-type',type='LINEAR'),dict(operation='region-curve-split',u=.125),dict(operation='region-curve-point',point=2,xyz=[.31,-.17,0]),dict(operation='region-curve-fixed',point=1,fixed=True),dict(operation='region-curve-reparameterize'),dict(operation='region-curve-delete',point=1),dict(operation='region-curve-type',type='PCHIP'),dict(operation='region-curve-type',type='CEDIT')]
            for request in operations:
                op=request['operation']
                if op=='region-curve-type':v.EditXSecConvertTo(x,getattr(v,request['type']))
                elif op=='region-curve-split':v.EditXSecSplit01(x,request['u'])
                elif op=='region-curve-point':v.MoveEditXSecPnt(x,request['point'],v.vec3d(*request['xyz']))
                elif op=='region-curve-fixed':
                    flags=list(v.GetEditXSecFixedUVec(x));flags[request['point']]=request['fixed'];v.SetEditXSecFixedUVec(x,flags)
                elif op=='region-curve-delete':v.EditXSecDelPnt(x,request['point'])
                else:v.ReparameterizeEditXSec(x)
                v.Update()
                state,path=self.worker(dict(action='mutate',id=region,**owner,**request),path)
                check(state)
                reopened,_=self.worker(dict(action='state'),path);check(reopened)

    def test_smooth_tangents_and_symmetric_edits_match_native_constraints(self):
        self.fixture();v=self.v
        for structural in (False,True):
            owner=dict(structure=self.sid) if structural else dict(geom=self.gid)
            region=self.structural if structural else self.region
            for symmetry in (v.SYM_NONE,v.SYM_RL):
                with self.subTest(structural=structural,symmetry=symmetry):
                    state,path=self.worker(dict(action='mutate',operation='region-curve-convert',id=region,**owner))
                    v.ClearVSPModel();g=v.AddGeom('STACK');surf=v.GetXSecSurf(g,0);v.ChangeXSecShape(surf,1,v.XS_CIRCLE);x=v.GetXSec(surf,1);v.SetXSecWidth(x,1);v.ConvertXSecToEdit(g,1);v.Update()
                    pid=next(p['id'] for p in self.row(state,structural)['sectionCurve']['params'] if p['name']=='SymType')
                    v.SetParmValUpdate(v.GetXSecParm(x,'SymType'),symmetry)
                    state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=symmetry),path)
                    v.SetParmValUpdate(v.GetXSecParm(x,'G1_3'),1)
                    state,path=self.worker(dict(action='mutate',operation='region-curve-smooth',id=region,point=3,smooth=True,**owner),path)
                    def check(state,label="smooth enabled"):
                        curve=self.row(state,structural)['sectionCurve']
                        self.assertEqual(curve['controlPoints'],[[p.x(),p.y(),p.z()] for p in v.GetEditXSecCtrlVec(x,True)],label)
                        self.assertEqual(curve['smooth'],[bool(v.GetParmVal(v.GetXSecParm(x,f'G1_{i}'))) for i in range(len(curve['controlPoints']))])
                    check(state)
                    for i,delta,side in ((2,[.04,.03,0],'outgoing'),(3,[.02,.04,0],'outgoing'),(4,[-.03,-.02,0],'outgoing'),(3,[-.01,.02,0],'incoming')):
                        p=v.GetEditXSecCtrlVec(x,True)[i];xyz=[p.x()+delta[0],p.y()+delta[1],p.z()]
                        v.MoveEditXSecPnt(x,i,v.vec3d(*xyz));v.Update()
                        state,path=self.worker(dict(action='mutate',operation='region-curve-point',id=region,point=i,xyz=xyz,tangentSide=side,**owner),path);check(state,f"point {i}")
                        reopened,_=self.worker(dict(action='state'),path);check(reopened,f"reopen point {i}")
                    v.SetParmValUpdate(v.GetXSecParm(x,'G1_3'),0)
                    state,path=self.worker(dict(action='mutate',operation='region-curve-smooth',id=region,point=3,smooth=False,**owner),path);check(state)

    def test_native_activity_tracks_closure_symmetry_and_smooth_constraints(self):
        from native_preview import parameter_activity
        self.fixture();v=self.v
        for structural in (False,True):
            owner=dict(structure=self.sid) if structural else dict(geom=self.gid)
            region=self.structural if structural else self.region
            state,path=self.worker(dict(action='mutate',operation='region-curve-convert',id=region,**owner))
            v.ClearVSPModel();g=v.AddGeom('STACK');surf=v.GetXSecSurf(g,0)
            v.ChangeXSecShape(surf,1,v.XS_CIRCLE);x=v.GetXSec(surf,1)
            v.SetXSecWidth(x,1);v.ConvertXSecToEdit(g,1);v.Update()
            def check(snapshot):
                curve=self.row(snapshot,structural)['sectionCurve'];count=len(curve['controlPoints'])
                names=[f'{prefix}_{i}' for i in range(count) for prefix in ('X','Y','Z','G1','FixedU')]
                ids={name:v.GetXSecParm(x,name) for name in names}
                expected=parameter_activity(v,ids.values())
                actual={p['name']:p['active'] for p in curve['params']}
                self.assertEqual({n:actual[n] for n in names},{n:expected[ids[n]] for n in names})
                self.assertEqual(curve['pointActivity'],[[actual[f'{axis}_{i}'] for axis in 'XYZ'] for i in range(count)])
                self.assertEqual(curve['smoothActivity'],[actual[f'G1_{i}'] for i in range(count)])
                self.assertEqual(curve['fixedActivity'],[actual[f'FixedU_{i}'] for i in range(count)])
                return curve
            for name,value in [('SymType',v.SYM_NONE),('CloseFlag',0),('CloseFlag',1),('SymType',v.SYM_RL),('G1_3',1),('G1_3',0)]:
                v.SetParmValUpdate(v.GetXSecParm(x,name),value)
                pid=next(p['id'] for p in self.row(state,structural)['sectionCurve']['params'] if p['name']==name)
                state,path=self.worker(dict(action='mutate',operation='parameter',id=pid,value=value),path)
                curve=check(state)
                if name=='CloseFlag':
                    self.assertEqual(curve['pointActivity'][-1],[not bool(value)]*3)
                    self.assertEqual(curve['smoothActivity'][0],bool(value))
                if name=='SymType' and value==v.SYM_RL:
                    for i,u in enumerate(curve['curveU']):
                        if .25<u<.75:self.assertEqual(curve['pointActivity'][i],[False]*3)
                before=path.read_bytes();reopened,reloaded=self.worker(dict(action='state'),path)
                check(reopened);self.assertEqual(path.read_bytes(),before);self.assertEqual(reloaded.read_bytes(),before)

    def test_missing_native_activity_parameter_fails_without_changing_engine(self):
        from native_preview import parameter_activity
        v=self.v;ids=list(v.GetGeomParmIDs(self.gid))
        before={p:v.GetParmVal(p) for p in ids}
        with self.assertRaises(ValueError):parameter_activity(v,[ids[0],'MISSING'])
        self.assertEqual({p:v.GetParmVal(p) for p in ids},before)
        self.assertEqual(parameter_activity(v,[]),{})

    def test_invalid_editable_region_operations_preserve_saved_model(self):
        self.fixture();state,path=self.worker(dict(action='mutate',operation='region-curve-convert',id=self.region,geom=self.gid))
        before=path.read_bytes()
        symmetry=next(p for p in self.row(state)['sectionCurve']['params'] if p['name']=='SymType')
        self.assertEqual(symmetry['max'],self.v.SYM_RL)
        with self.assertRaisesRegex(ValueError,'parameter limits'):
            self.worker(dict(action='mutate',operation='parameter',id=symmetry['id'],value=self.v.SYM_TB),path)
        self.assertEqual(path.read_bytes(),before)
        bad=[dict(operation='region-curve-smooth' ,point=1,smooth=True),dict(operation='region-curve-smooth',point=3,smooth='yes'),dict(operation='region-curve-point',point=True,xyz=[0,0,0]),dict(operation='region-curve-point',point=1,xyz=[float('nan'),0,0]),dict(operation='region-curve-fixed',point=1,fixed='yes'),dict(operation='region-curve-delete',point=0),dict(operation='region-curve-delete',point=1),dict(operation='region-curve-split',u=0),dict(operation='region-curve-type',type='unknown')]
        for request in bad:
            with self.assertRaises(ValueError):self.worker(dict(action='mutate',id=self.region,geom=self.gid,**request),path)
            self.assertEqual(path.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'Convert this region'):
            self.worker(dict(action='mutate',operation='region-curve-split',id=self.structural,structure=self.sid,u=.125))

    def test_copy_native_section_profile_and_reject_non_curve_region(self):
        self.fixture();v=self.v;g=v.AddGeom('STACK');surf=v.GetXSecSurf(g,0)
        v.ChangeXSecShape(surf,1,v.XS_ELLIPSE);x=v.GetXSec(surf,1);v.SetXSecWidth(x,.35);v.SetXSecHeight(x,.2)
        rectangle=v.AddSubSurf(self.gid,v.SS_RECTANGLE);v.Update();v.WriteVSPFile(str(self.model),v.SET_ALL)
        curve_id=v.GetParmContainer(v.GetXSecParm(x,'Ellipse_Width'))
        expected={(v.GetParmGroupName(p),v.GetParmName(p)):v.GetParmVal(p) for p in v.FindContainerParmIDs(curve_id)}
        state,path=self.worker(dict(action='mutate',operation='region-curve-copy-from',geom=self.gid,id=self.region,source=dict(kind='section',geom=g,surface=0,index=1)))
        curve=self.row(state)['sectionCurve'];self.assertEqual(curve['type'],v.XS_ELLIPSE)
        actual={(p['rawGroup'],p['name']):p['value'] for p in curve['params']}
        self.assertEqual(actual,expected)
        before=path.read_bytes()
        for operation in ('region-curve-convert','region-curve-copy-from'):
            with self.assertRaisesRegex(ValueError,'section-curve region'):
                self.worker(dict(action='mutate',operation=operation,geom=self.gid,id=rectangle,source=dict(kind='region',geom=self.gid,id=self.region)),path)
            self.assertEqual(path.read_bytes(),before)
        state,path=self.worker(dict(action='mutate',operation='region-curve-convert',structure=self.sid,id=self.structural),path)
        self.assertEqual(self.row(state,True)['sectionCurve']['type'],v.XS_EDIT_CURVE)
