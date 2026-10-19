// Analysis numbers remain in their native conventions; these labels do not
// silently apply the geometry inspector's display conversions.
export function analysisInputUnit(spec,e,modelLength='model length'){
 const n=e.name;
 const chosen=name=>{const f=spec.inputs.find(x=>x.name===name);return f?.choices?.find(c=>c.value===f.values[0])?.label;};
 const length=spec.name==='ParasiteDrag'?(chosen('LengthUnit')||modelLength):modelLength;
 if(e.units||e.unit)return e.units||e.unit;
 if(['AlphaStart','AlphaEnd','BetaStart','BetaEnd','Alpha','Beta','WakeAngle'].includes(n))return 'deg';
 if(['Sref','Area_vec'].includes(n))return length+'²';
 if(['bref','cref','Xcg','Ycg','Zcg','XSlicePosVec','YSlicePosVec','ZSlicePosVec','X_vec','StartVal','EndVal','BaseLen','MinLen','MaxGap','FarXScale','FarYScale','FarZScale'].includes(n))return /Scale$/.test(n)?'ratio':length;
 if(['TimeStepSize','TimeStep','HoverRampTime'].includes(n))return 's';
 if(n==='Altitude')return chosen('AltLengthUnit')||length;
 if(n==='Vinf')return spec.name==='ParasiteDrag'?(chosen('VelocityUnit')||'selected airspeed unit'):length+'/s';
 if(n==='Vref')return length+'/s';
 if(n==='Rho')return 'consistent mass/'+length+'³';
 if(n==='Temperature'||n==='DeltaTemp')return chosen('TempUnit')||'selected temperature unit';
 if(n==='Pressure')return chosen('PresUnit')||'selected pressure unit';
 if(n==='Re_L')return '1/'+length;
 if(/^(Mach|ReCref|ReCrefEnd|GrowthRatio|WakeRelax|CoreSizeFactor|FarAway|SpecificHeatRatio|ForwardGMRESConvergenceFactor|AdjointGMRESConvergenceFactor|NonLinearConvergenceFactor)/.test(n))return 'dimensionless';
 return '';
}
