"""Original atmosphere API and original drag-equation verification writers."""
from pathlib import Path
import math

NAMES=('AtmosphereReference','DragEquationReference')


def schema(v,name):
    if name=='AtmosphereReference':
        description='Original OpenVSP atmosphere at one altitude and temperature deviation. Inputs use meters and kelvin differences; pressure is returned in kPa. The separate native standard-day table uses its fixed altitude grid and zero temperature deviation.'
        fields=[dict(name='AtmosphereModel',index=0,type=v.INT_DATA,values=[v.ATMOS_TYPE_US_STANDARD_1976],editable=True,label='Atmosphere model',choices=[dict(value=v.ATMOS_TYPE_US_STANDARD_1976,label='US Standard Atmosphere 1976'),dict(value=v.ATMOS_TYPE_HERRINGTON_1966,label='USAF / Herrington 1966')],description='Only the two original automatic atmosphere models are supported by CalcAtmosphere; manual parasite-drag atmosphere choices are not applicable.'),
                dict(name='AltitudeMeters',index=0,type=v.DOUBLE_DATA,values=[4000.],editable=True,label='Altitude (m)',description='Altitude in meters, independently of the geometry display units.'),
                dict(name='TemperatureDeviationKelvin',index=0,type=v.DOUBLE_DATA,values=[0.],editable=True,label='Temperature deviation (K)',description='Temperature difference from the selected model, in kelvin; the same numerical increment as degrees Celsius.')]
        label='Atmosphere · native model and standard-day table'
    else:
        description='Original OpenVSP verification tables for body/wing form factors, skin friction or partial turbulence. These fixed reference grids use the engine writer’s preset conditions; they do not calculate this aircraft’s drag. Review the recorded native parameters and original CSV.'
        fields=[dict(name='TableKind',index=0,type=v.INT_DATA,values=[0],editable=True,label='Native reference table',choices=[dict(value=i,label=s) for i,s in enumerate(['Body form factors','Wing form factors','Skin-friction equations','Partial turbulence'])],description='The original writer selects its grid, equation families and reference conditions. Singular native samples remain undefined.')]
        label='Drag equations · native reference tables'
    return dict(name=name,label=label,standaloneNative=True,description=description,inputs=fields,
                guide=dict(title=label,note=description,sensitivityNote='The native standard-day table uses zero temperature deviation on its fixed altitude grid; the at-altitude output uses your requested deviation.' if name=='AtmosphereReference' else 'The table uses the original writer’s preset grid and conditions. It does not establish aircraft drag or solver convergence.',sections=[dict(title='Native reference inputs',inputs=[e['name'] for e in fields])]))


def run(v,req):
    from native_analytical import inputs,result,write_csv
    from native_worker import collect_results
    spec,p=inputs(v,req);name=req['name'];v.DeleteAllResults()
    if name=='AtmosphereReference':
        allowed=(v.ATMOS_TYPE_US_STANDARD_1976,v.ATMOS_TYPE_HERRINGTON_1966)
        if p['AtmosphereModel'] not in allowed:raise ValueError('Choose US Standard 1976 or USAF / Herrington 1966.')
        values=list(v.CalcAtmosphere(p['AltitudeMeters'],p['TemperatureDeviationKelvin'],p['AtmosphereModel']))
        if len(values)!=4:raise ValueError('OpenVSP returned an incomplete atmosphere output.')
        fields=[('Altitude_m',[p['AltitudeMeters']],'Requested altitude in meters.'),('Temperature_K',[values[0]],'Original native temperature in kelvin.'),('Pressure_kPa',[values[1]],'Original native pressure in kPa.'),('PressureRatio',[values[2]],'Original pressure ratio relative to sea-level standard day.'),('DensityRatio',[values[3]],'Original density ratio relative to sea-level standard day.')]
        point=result(v,'AtmosphereAtAltitude',fields,spec['description'])
        file='native-standard-day-atmosphere.csv';v.WriteAtmosphereCSVFile(file,p['AtmosphereModel'])
        outputs=[point,*collect_results(v)];sample_file=write_csv('AtmosphereAtAltitude',fields)
        functions=['CalcAtmosphere','WriteAtmosphereCSVFile'];native_name='Atmosphere'
    else:
        writers=[('WriteBodyFFCSVFile','Body_Form_Factor'),('WriteWingFFCSVFile','Wing_Form_Factor'),('WriteCfEqnCSVFile','Friction_Coefficient'),('WritePartialCfMethodCSVFile','Friction_Coefficient')]
        if p['TableKind'] not in range(len(writers)):raise ValueError('Choose one of the four original native drag reference tables.')
        function,native_name=writers[p['TableKind']];file='native-'+function+'.csv';getattr(v,function)(file)
        outputs=collect_results(v);sample_file=None;functions=[function]
    if not Path(file).is_file() or not Path(file).stat().st_size or not outputs:raise ValueError('OpenVSP did not produce the original reference table.')
    undefined=sum(not math.isfinite(x) for r in outputs for e in r['entries'] if e['type'] in (v.INT_DATA,v.DOUBLE_DATA) for x in e['values'])
    return dict(version=v.GetVSPVersion(),analysis=name,resultID=v.FindLatestResultsID(native_name),engineOperation=', '.join(functions),nativeFunctions=functions,
                standaloneNative=True,description=spec['description'],inputs=spec['inputs'],geometryInputs=[],results=outputs,csvFile=file,sampleCsvFile=sample_file,undefinedSamples=undefined)
