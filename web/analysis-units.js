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
 if(['FarDist','GroundEffect'].includes(n))return length;
 if(['CLMax2D','Clo2D','CullFrac','RelCurveTol'].includes(n))return 'dimensionless';
 if(n==='NCircSeg')return 'segments';
 if(n==='Norm'||n==='Direction')return 'direction vector · dimensionless';
 if(n==='STEPTol')return (chosen('CADLenUnit')||['mm','cm','m','in','ft','yd'][spec.inputs.find(x=>x.name==='CADLenUnit')?.values[0]]||'CAD export length');
 // ParasiteDragMgr uses AltLengthUnit to select its atmosphere's mass/length
 // system independently of the geometry LengthUnit (UpdateAlt/UpdateExportLabels).
 if(spec.name==='ParasiteDrag'&&['Density','DynaVisc','KineVisc'].includes(n)){
  const altitude=spec.inputs.find(x=>x.name==='AltLengthUnit')?.values[0];
  if(![0,1].includes(altitude))return 'selected atmosphere units';
  const metric=altitude===1;
  return n==='Density'?(metric?'kg/m³':'slug/ft³'):n==='DynaVisc'?(metric?'kg/(m·s)':'slug/(ft·s)'):(metric?'m²/s':'ft²/s');
 }
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
