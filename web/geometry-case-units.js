// Labels only. GeometryAnalysisCase evaluates these values in native conventions.
const angles=new Set(['NominalTip','MinTip','MaxTip','RollAngle','Tip','TipBogie','TipWheel']);
const length=new Set(['GearTurnRadii','MaxRadii','COR','Total_CG','Xac','cbar','Min_Dist','Max_Dist','MaxMin_Dist']);
const resultUnits={WetArea_Volume:'model length²',Planar_Slice:'model length²',Projected_Area:'model length²',Aero_Center:'model length',Plane_2pt_Angle_Interference:'deg',Plane_1pt_Angle_Interference:'deg',Risk_Angle:'deg',Gear_CG_Tipback:'deg',Gear_Tipover:'deg',Gear_Weight_Distribution:'fraction of total weight'};
const constraintRecords=new Set(['External_Interference','Packaging_Interference','External_Self_Interference','Static_Plane_Distance_Interference','Carrier_Composite_Envelope_Interference','Linear_Swept_Volume_Interference']);
export const geometryCaseHasConstraintScore=record=>constraintRecords.has(record);
const flags=new Set(['Interference','Intersection','Primary_In_Secondary','Secondary_In_Primary']);
export function geometryCaseResultUnit(record,entry){
 if(angles.has(entry))return 'deg';
 if(length.has(entry))return 'model length';
 if(entry==='Total_Wet_Area'||entry==='Area')return 'model length²';
 if(flags.has(entry))return 'flag · 0/1';
 if(['InterferenceVol','Vol_Primary','Vol_Secondary'].includes(entry))return 'model length³';
 if(entry==='Result'&&constraintRecords.has(record))return 'native constraint score';
 if(entry==='Total_Wet_Vol')return 'model length³';
 if(entry==='Total_Mass')return 'model mass';
 if(entry==='Axis')return 'direction · dimensionless';
 if(entry==='NominalReactions'||entry==='ExcursionReactions')return 'fraction of total weight';
 if(entry==='Result')return resultUnits[record]||'See native description';
 return 'See native description';
}
