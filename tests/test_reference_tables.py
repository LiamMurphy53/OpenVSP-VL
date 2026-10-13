"""Reference results and CSV records equal original native API output."""
import json,math,sys,unittest
from pathlib import Path
import test_native
from vsp_runtime import load
from native_worker import collect_results

def clean(data):
    if isinstance(data,float) and not math.isfinite(data):return None
    if isinstance(data,list):return [clean(x) for x in data]
    if isinstance(data,dict):return {k:clean(x) for k,x in data.items() if k!='id'}
    return data

def records(path):return [line for line in Path(path).read_text().splitlines() if not line.startswith(('Results_Timestamp,','Results_Date,','Results_Time,'))]

@unittest.skipUnless(sys.version_info[:2]==(3,11),'Use matching native runtime.')
class NativeReferenceTables(unittest.TestCase):
    setUpClass=classmethod(lambda cls:setattr(cls,'v',load()))
    setUp=test_native.NativeIntegration.setUp
    tearDown=test_native.NativeIntegration.tearDown
    worker=test_native.NativeIntegration.worker

    def test_both_atmosphere_models_point_and_standard_day_table_match_native(self):
        v=self.v;source=self.model.read_bytes()
        for model in [v.ATMOS_TYPE_US_STANDARD_1976,v.ATMOS_TYPE_HERRINGTON_1966]:
            for alt,dt in [(0.,0.),(4000.,5.),(11001.,-10.)]:
                with self.subTest(model=model,altitude=alt,temperatureDeviation=dt):
                    req=dict(action='analysis',name='AtmosphereReference',inputs=[dict(name=n,values=[x]) for n,x in [('AtmosphereModel',model),('AltitudeMeters',alt),('TemperatureDeviationKelvin',dt)]])
                    data,path=self.worker(req);values=list(v.CalcAtmosphere(alt,dt,model));point={e['name']:e['values'][0] for e in data['results'][0]['entries']}
                    self.assertEqual([point[n] for n in ['Temperature_K','Pressure_kPa','PressureRatio','DensityRatio']],values)
                    v.DeleteAllResults();direct=self.path/'native-atmosphere.csv';v.WriteAtmosphereCSVFile(str(direct),model)
                    self.assertEqual(clean(data['results'][1:]),clean(collect_results(v)))
                    self.assertEqual(records(path.parent/data['csvFile']),records(direct))
                    self.assertEqual(path.read_bytes(),source)

    def test_all_four_equation_tables_match_every_native_sample_and_csv_record(self):
        v=self.v;source=self.model.read_bytes()
        for kind,function in enumerate(['WriteBodyFFCSVFile','WriteWingFFCSVFile','WriteCfEqnCSVFile','WritePartialCfMethodCSVFile']):
            with self.subTest(writer=function):
                data,path=self.worker(dict(action='analysis',name='DragEquationReference',inputs=[dict(name='TableKind',values=[kind])]))
                v.ClearVSPModel();v.ReadVSPFile(str(self.model));v.Update();v.DeleteAllResults();direct=self.path/(function+'.csv');getattr(v,function)(str(direct))
                self.assertEqual(clean(data['results']),clean(collect_results(v)))
                self.assertEqual(records(path.parent/data['csvFile']),records(direct))
                self.assertEqual(path.read_bytes(),source);self.assertEqual(data['nativeFunctions'],[function])

    def test_invalid_models_selectors_and_nonfinite_input_preserve_source(self):
        before=self.model.read_bytes()
        for name,field,value in [('AtmosphereReference','AtmosphereModel',self.v.ATMOS_TYPE_MANUAL_P_T),('DragEquationReference','TableKind',4),('AtmosphereReference','AltitudeMeters',float('inf')),('AtmosphereReference','TemperatureDeviationKelvin',float('nan')),('DragEquationReference','TableKind',.5)]:
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):self.worker(dict(action='analysis',name=name,inputs=[dict(name=field,values=[value])]))
            self.assertEqual(self.model.read_bytes(),before)
