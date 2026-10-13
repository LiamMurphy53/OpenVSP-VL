"""Official analytical API comparisons, singular samples and saved-run isolation."""
import csv
import json
import math
import sys
import time
import unittest
import test_native
from vsp_runtime import load
import native_analytical
import native_service as service


def columns(data,index=0):return {e['name']:e['values'] for e in data['results'][index]['entries']}
def request(name,**values):return dict(action='analysis',name=name,inputs=[dict(name=n,index=0,values=[v]) for n,v in values.items()])
def clean(values):return [v if math.isfinite(v) else None for v in values]


@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use the matching native Python runtime.')
class AnalyticalNative(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_wing_lift_drag_and_half_span_match_official_api(self):
        v=self.v
        for both in [0,1]:
            with self.subTest(bothHalves=both):
                data,path=self.worker(request('HersheyBarTheory',NumPoints=23,AngleOfAttackDegrees=-3.5,FreestreamSpeed=63.,FullSpan=12.,IncludeBothHalves=both))
                lift=list(v.GetHersheyBarLiftDist(23,math.radians(-3.5),63.,12.,bool(both)))
                drag=list(v.GetHersheyBarDragDist(23,math.radians(-3.5),63.,12.,bool(both)))
                actual=columns(data)
                self.assertEqual(actual,dict(SpanStation=[q.x() for q in lift],cl=[q.y() for q in lift],cdi=[q.y() for q in drag]))
                self.assertEqual(path.read_bytes(),self.model.read_bytes())
                self.assertEqual(len(actual['cl']),23*(both+1));self.assertEqual(data['undefinedSamples'],0)
                self.assertIsNone(data['resultID']);self.assertTrue(data['standaloneNative'])
                rows=list(csv.DictReader((path.parent/data['csvFile']).read_text().splitlines()))
                self.assertEqual([float(row['cl']) for row in rows],actual['cl'])

    def test_airfoil_native_pressure_geometry_and_selig_export(self):
        v=self.v;alpha=math.radians(7.);tau=math.radians(12.)
        points=v.GetVKTAirfoilPnts(142,alpha,.18,-.08,tau)
        cp=list(v.GetVKTAirfoilCpDist(alpha,.18,-.08,tau,points))
        data,path=self.worker(request('VKTAirfoilTheory',NumPoints=142,AngleOfAttackDegrees=7.,ThicknessParameter=.18,CamberParameter=-.08,TrailingEdgeAngleDegrees=12.))
        actual=columns(data);nodes=[[p.x(),p.y(),p.z()] for p in points]
        self.assertEqual(actual,dict(X_Loc=[p[0] for p in nodes],Y_Loc=[p[1] for p in nodes],Z_Loc=[p[2] for p in nodes],Cp=clean(cp)))
        self.assertEqual(path.read_bytes(),self.model.read_bytes())
        preview=json.loads((path.parent/data['theoryFile']).read_text());self.assertEqual(preview['nodes'],nodes)
        valid=[i for i,c in enumerate(cp) if math.isfinite(c)]
        self.assertEqual([e['nodes'][0] for e in preview['elements']],valid)
        self.assertEqual(preview['fields'][0]['values'],[cp[i] for i in valid])
        self.assertEqual(preview['initialView'],'profile')
        exported=[list(map(float,line.split())) for line in (path.parent/data['airfoilFile']).read_text().splitlines()[1:]]
        self.assertEqual(exported,[p[:2] for p in nodes])
        # Confirm the generated profile is usable through the native importer.
        surf=v.GetXSecSurf(self.gid,0);v.ChangeXSecShape(surf,1,v.XS_FILE_AIRFOIL)
        section=v.GetXSec(surf,1);v.ReadFileAirfoil(section,str(path.parent/data['airfoilFile']))
        self.assertFalse(v.ErrorMgrSingleton.getInstance().GetNumTotalErrors())
        self.assertGreater(len(v.GetAirfoilUpperPnts(section)),10)

    def test_native_shape_parameters_and_incidence_are_not_percentage_limited(self):
        v=self.v;alpha=math.radians(365.);tau=math.radians(8.)
        points=v.GetVKTAirfoilPnts(82,alpha,1.2,-1.5,tau)
        expected=clean(list(v.GetVKTAirfoilCpDist(alpha,1.2,-1.5,tau,points)))
        data,_=self.worker(request('VKTAirfoilTheory',NumPoints=82,AngleOfAttackDegrees=365.,ThicknessParameter=1.2,CamberParameter=-1.5,TrailingEdgeAngleDegrees=8.))
        self.assertEqual(columns(data)['Cp'],expected)
        self.assertEqual(columns(data)['Y_Loc'],[p.y() for p in points])

    def test_ellipsoid_translation_and_integrals_match_official_api(self):
        v=self.v;abc=v.vec3d(1.5,2.2,.8);velocity=v.vec3d(80.,20.,-10.)
        local=v.GetEllipsoidSurfPnts(v.vec3d(0,0,0),abc,23,25)
        shifted=v.GetEllipsoidSurfPnts(v.vec3d(10.,-8.,3.),abc,23,25)
        expected=clean(list(v.GetEllipsoidCpDist(local,abc,velocity)))
        base=dict(SemiAxisX=1.5,SemiAxisY=2.2,SemiAxisZ=.8,FreestreamVelocity=[80.,20.,-10.],NumPointsU=23,NumPointsW=25)
        data,path=self.worker(request('EllipsoidFlowTheory',Center=[10.,-8.,3.],**base));origin,_=self.worker(request('EllipsoidFlowTheory',**base))
        actual=columns(data)
        self.assertEqual(actual['Cp'],expected);self.assertEqual(actual['Cp'],columns(origin)['Cp'])
        self.assertEqual(list(zip(actual['X_Loc'],actual['Y_Loc'],actual['Z_Loc'])),[(p.x(),p.y(),p.z()) for p in shifted])
        self.assertEqual(columns(data,1),dict(Axis=[0,1,2],Integral=[v.IntegrateEllipsoidFlow(abc,i) for i in range(3)]))
        preview=json.loads((path.parent/data['theoryFile']).read_text())
        self.assertEqual(preview['fields'][0]['values'],expected)
        self.assertEqual(path.read_bytes(),self.model.read_bytes())

    def test_sphere_reference_agrees_with_closed_form_pressure(self):
        # Independent physics check in addition to exact native API equality.
        data,_=self.worker(request('EllipsoidFlowTheory',SemiAxisX=1.,SemiAxisY=1.,SemiAxisZ=1.,NumPointsU=20,NumPointsW=21))
        values=columns(data)
        for x,cp in zip(values['X_Loc'],values['Cp']):self.assertAlmostEqual(cp,1.-2.25*(1.-x*x),places=6)

    def test_undefined_native_pressure_samples_are_retained_without_fabrication(self):
        # Finite input can still overflow native flow evaluation. Preserve the
        # actual undefined result, rather than inventing a finite solution.
        v=self.v;abc=v.vec3d(1.,1.,1.)
        points=v.GetEllipsoidSurfPnts(v.vec3d(0,0,0),abc,20,20)
        for speed in [1e154,1e308]:
            with self.subTest(speed=speed):
                expected=clean(list(v.GetEllipsoidCpDist(points,abc,v.vec3d(speed,0,0))))
                self.assertIn(None,expected)
                data,path=self.worker(request('EllipsoidFlowTheory',SemiAxisX=1.,SemiAxisY=1.,SemiAxisZ=1.,NumPointsU=20,NumPointsW=20,FreestreamVelocity=[speed,0.,0.]))
                self.assertEqual(columns(data)['Cp'],expected);self.assertEqual(data['undefinedSamples'],expected.count(None))
                if expected.count(None)==len(expected):self.assertNotIn('theoryFile',data)
                else:
                    preview=json.loads((path.parent/data['theoryFile']).read_text())
                    self.assertEqual(preview['totalElements'],len(expected)-expected.count(None))
                rows=list(csv.DictReader((path.parent/data['csvFile']).read_text().splitlines()))
                self.assertEqual([r['Cp']=='undefined' for r in rows],[x is None for x in expected])
        self.assertIsNone(native_analytical.pressure_preview([[0.,0.,0.]],[float('nan')],'undefined'))

    def test_input_domains_types_and_schema_are_checked_before_native_execution(self):
        for req in [request('HersheyBarTheory',NumPoints=1),request('HersheyBarTheory',NumPoints=4.5),request('HersheyBarTheory',NumPoints=True),
                    request('HersheyBarTheory',FullSpan=0),request('HersheyBarTheory',FreestreamSpeed=-2),request('HersheyBarTheory',IncludeBothHalves=2),
                    request('VKTAirfoilTheory',ThicknessParameter=-.1),request('VKTAirfoilTheory',TrailingEdgeAngleDegrees=180),
                    request('EllipsoidFlowTheory',SemiAxisX=0),request('EllipsoidFlowTheory',Center=[1.,2.]),
                    request('EllipsoidFlowTheory',FreestreamVelocity=[0.,0.,0.]),request('EllipsoidFlowTheory',NumPointsU=19),
                    request('EllipsoidFlowTheory',Center=[0.,float('inf'),0.]),request('EllipsoidFlowTheory',UnknownInput=4)]:
            with self.subTest(request=req),self.assertRaises(ValueError):self.worker(req)
        state,_=self.worker(dict(action='state'))
        self.assertTrue(set(native_analytical.NAMES)<=set(state['analyses']))
        for name in native_analytical.NAMES:
            spec,_=self.worker(dict(action='schema',name=name));self.assertTrue(spec['standaloneNative'])
            self.assertTrue(spec['label']);self.assertTrue(spec['inputs'])
            if name=='EllipsoidFlowTheory':self.assertEqual(next(e for e in spec['inputs'] if e['name']=='Center')['values'],[[0.,0.,0.]])
        self.assertTrue(self.model.exists())

    def test_native_saved_run_preview_csv_and_isolation_survive_service_reload(self):
        old=(service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION,service.JOBS)
        service.WORK=self.path;service.MODEL=self.model;service.HISTORY=[];service.FUTURE=[];service.REVISION='analytical-verification';service.JOBS={}
        before=self.model.read_bytes()
        try:
            job=service.start_job(dict(name='EllipsoidFlowTheory',revision=service.REVISION,inputs=request('EllipsoidFlowTheory',NumPointsU=20,NumPointsW=20)['inputs']))
            jid=job['id'];deadline=time.monotonic()+30
            while job['status']=='running' and time.monotonic()<deadline:
                time.sleep(.05);job=service.job_state(jid)
            self.assertEqual(job['status'],'complete',job)
            expected=job['result'];service.JOBS={}
            restored=service.job_state(jid);self.assertEqual(restored['result'],expected)
            file=next(f for f in restored['artifacts'] if f['theoryPreview'])
            preview=service.theory_preview(jid,file['name']);self.assertEqual(preview['nodes'][0],[0.,0.,3.])
            self.assertEqual(preview['fields'][0]['values'],columns(expected)['Cp'])
            self.assertIn(b'EllipsoidFlowIntegrals,0,Integral',service.result_csv(jid))
            self.assertEqual(service.artifact_file(jid,expected['csvFile']).read_text().splitlines()[0],'X_Loc,Y_Loc,Z_Loc,Cp')
            self.assertEqual(self.model.read_bytes(),before);self.assertFalse(service.HISTORY)
            for bad in ['../reference.theory.json','engine.log']:
                with self.assertRaises(ValueError):service.theory_preview(jid,bad)
        finally:service.WORK,service.MODEL,service.HISTORY,service.FUTURE,service.REVISION,service.JOBS=old


if __name__=='__main__':unittest.main()
