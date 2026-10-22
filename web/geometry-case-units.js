// Labels only. GeometryAnalysisCase evaluates these values in native conventions.
const angles=new Set(['NominalTip','MinTip','MaxTip','RollAngle','Tip','TipBogie','TipWheel']);
const length=new Set(['GearTurnRadii','MaxRadii','COR','Total_CG','Xac','cbar']);
const resultUnits={WetArea_Volume:'model length²',Planar_Slice:'model length²',Projected_Area:'model length²',Aero_Center:'model length',Plane_2pt_Angle_Interference:'deg',Plane_1pt_Angle_Interference:'deg',Risk_Angle:'deg',Gear_CG_Tipback:'deg',Gear_Tipover:'deg',Gear_Weight_Distribution:'fraction of total weight'};
export function geometryCaseResultUnit(record,entry){
 if(angles.has(entry))return 'deg';
 if(length.has(entry))return 'model length';
 if(entry==='Total_Wet_Area'||entry==='Area')return 'model length²';
 if(entry==='Total_Wet_Vol')return 'model length³';
 if(entry==='Total_Mass')return 'model mass';
 if(entry==='Axis')return 'direction · dimensionless';
 if(entry==='NominalReactions'||entry==='ExcursionReactions')return 'fraction of total weight';
 if(entry==='Result')return resultUnits[record]||'See native description';
 return 'See native description';
}
