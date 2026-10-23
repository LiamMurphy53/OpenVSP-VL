"""Dimensional metadata for known native result fields; values stay unchanged."""
AREA={'Total_Wet_Area','Total_Theo_Area','Theo_Area','Wet_Area','SubSurf_Theo_Area','SubSurf_Wet_Area','Tag_Theo_Area','Tag_Wet_Area'}
VOLUME={'Total_Wet_Vol','Total_Theo_Vol','Theo_Vol','Wet_Vol'}

def result_unit(record,key):
    if key=='Analysis_Duration_Sec':return 's'
    if record=='Comp_Geom':return 'model length²' if key in AREA else 'model length³' if key in VOLUME else ''
    if record=='Slice':return 'model length²' if key=='Slice_Area' else 'model length' if key in ('Slice_Loc','Slice_Area_Center') else 'dimensionless' if key=='Axis_Vector' else ''
    if record=='Projection':return 'model length²' if key in ('Area','Comp_Areas') else 'dimensionless' if key=='Direction' else ''
    if record=='Mass_Properties':
        if key in ('Total_Mass','Comp_Mass'):return 'model mass'
        if key in ('Total_Volume','Comp_Vol'):return 'model length³'
        if key in ('Total_CG','Comp_CG'):return 'model length'
        if any(key==prefix+'_I'+axis for prefix in ('Total','Comp') for axis in ('xx','yy','zz','xy','xz','yz')):return 'model mass × model length²'
    return ''
