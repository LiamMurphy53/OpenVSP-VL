"""Validate CST requests against native coefficient parameter limits."""
# Original FitCSTAirfoil accepts Airfoil-derived curves independently of the
# section owner. AC25-773 and editable/body curves derive from XSecCurve only.
AIRFOIL_SHAPES=('XS_FOUR_SERIES','XS_SIX_SERIES','XS_BICONVEX','XS_WEDGE',
                'XS_FILE_AIRFOIL','XS_CST_AIRFOIL','XS_VKT_AIRFOIL',
                'XS_FOUR_DIGIT_MOD','XS_FIVE_DIGIT','XS_FIVE_DIGIT_MOD','XS_ONE_SIX_SERIES')


def fitting_allowed(v,shape):
    return shape in {getattr(v,name) for name in AIRFOIL_SHAPES}


def fitting_degree(value):
    if type(value)!=int or not 1<=value<=20:raise ValueError('Choose a fitting degree from 1 to 20.')
    return value


def coefficients(v,parameters,request):
    from native_tools import finite
    fields={v.GetParmName(pid):pid for pid in parameters if v.GetParmGroupName(pid) in ('UpperCoeff','LowerCoeff')}
    for side,prefix in [('upper','Au'),('lower','Al')]:
        values=request.get(side)
        if not isinstance(values,list) or not 1<=len(values)<=31:raise ValueError('Use 1–31 coefficients per surface.')
        for i,value in enumerate(values):
            finite(value)
            # Newly reserved coefficients inherit the native family's limits.
            pid=fields.get(f'{prefix}_{i}',fields[f'{prefix}_0'])
            if not v.GetParmLowerLimit(pid)<=value<=v.GetParmUpperLimit(pid):raise ValueError('Use CST coefficients within the native parameter limits.')
