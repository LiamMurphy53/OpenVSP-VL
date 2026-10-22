// Dimensional labels for original geometry-analysis arrays; no conversions.
const area=new Set(['Total_Wet_Area','Total_Theo_Area','Theo_Area','Wet_Area','SubSurf_Theo_Area','SubSurf_Wet_Area','Tag_Theo_Area','Tag_Wet_Area']);
const volume=new Set(['Total_Wet_Vol','Total_Theo_Vol','Theo_Vol','Wet_Vol']);
export function geometryResultUnit(record,key){
 if(record==='Comp_Geom')return area.has(key)?'model length²':volume.has(key)?'model length³':'';
 if(record==='Slice')return key==='Slice_Area'?'model length²':['Slice_Loc','Slice_Area_Center'].includes(key)?'model length':key==='Axis_Vector'?'dimensionless':'';
 if(record==='Projection')return ['Area','Comp_Areas'].includes(key)?'model length²':key==='Direction'?'dimensionless':'';
 if(record==='Mass_Properties'){
  if(['Total_Mass','Comp_Mass'].includes(key))return 'model mass';
  if(['Total_Volume','Comp_Vol'].includes(key))return 'model length³';
  if(['Total_CG','Comp_CG'].includes(key))return 'model length';
  if(/^(Total|Comp)_I[xyz][xyz]$/.test(key))return 'model mass × model length²';
 }
 return '';
}
export function geometryResultLabel(record,key,label){const unit=geometryResultUnit(record,key);return unit?`${label} (${unit})`:label;}
