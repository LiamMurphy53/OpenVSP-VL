"""Guide original profile modifier parameters; geometry stays in OpenVSP.

Eligibility follows OpenVSP 3.52.2 Wing/Prop Modify screens and
XSecCurve::DetermineWingType, CloseLE/TE, TrimLE/TE and DeflectTE.
"""
import math
import native_preview
import native_chevrons

TRANSFORMS = ('Theta', 'Scale', 'DeltaX', 'DeltaY', 'ShiftLE')
GROUPS = ('Close', 'Trim', 'Flap', 'Chevron')


def refresh(v):
    # Circle DecodeXml can retain the constructor's obsolete parent ID.
    # Validate actual curve ownership for every BOR, independently of which
    # modifiers are enabled, and let the native parent evaluate the curve.
    repaired=[]
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper()!='BODYOFREVOLUTION':continue
        flap=v.FindParm(gid,'TE_Flap_Type','Flap')
        if v.GetBORXSecShape(gid)==v.XS_CIRCLE and v.ValidParm(flap) and v.GetParmVal(flap)!=v.FLAP_NONE:
            raise ValueError('This saved circular body-of-revolution profile has a flap that crashes the installed OpenVSP engine. Use an airfoil profile for the flap. The saved aircraft has not been changed.')
        pid=v.FindParm(gid,'Theta','XSecCurve')
        result=native_preview.refresh_profile(v,pid,gid)
        if result['parentBefore']!=result['parentAfter']:repaired.append(gid)
    if repaired:v.Update()
    return repaired


def profiles(v, gid):
    kind = v.GetGeomTypeName(gid).upper()
    wing = kind in ('WING', 'PROP', 'PROPELLER', 'BODYOFREVOLUTION')
    entries = []
    if kind in ('WING', 'PROP', 'PROPELLER', 'FUSELAGE', 'STACK'):
        for si in range(v.GetNumXSecSurfs(gid)):
            surf = v.GetXSecSurf(gid, si)
            for i in range(v.GetNumXSec(surf)):
                x = v.GetXSec(surf, i)
                entries.append((si, i, v.GetXSecShape(x), list(v.GetXSecParmIDs(x))))
    elif kind == 'BODYOFREVOLUTION':
        entries.append((None, None, v.GetBORXSecShape(gid), list(v.GetGeomParmIDs(gid))))
    for si, i, shape, pids in entries:
        by_key = {(v.GetParmGroupName(p), v.GetParmName(p)): p for p in pids}
        get = lambda group, name: by_key.get((group, name))
        transforms = [get('XSecCurve', n) for n in TRANSFORMS]
        close = []; trim = []
        for edge, label in [('LE', 'Leading edge'), ('TE', 'Trailing edge')]:
            close.append(dict(edge=edge, label=label, fields={
                key: get('Close', edge + '_Close_' + suffix) for key, suffix in
                [('mode', 'Type'), ('basis', 'AbsRel'), ('gap', 'Thick'), ('gapFraction', 'Thick_Chord')]}))
            trim.append(dict(edge=edge, label=label, fields={
                key: get('Trim', edge + '_Trim_' + suffix) for key, suffix in
                [('mode', 'Type'), ('basis', 'AbsRel'), ('distance', 'X'), ('distanceFraction', 'X_Chord'),
                 ('thickness', 'Thick'), ('thicknessFraction', 'Thick_Chord')]}))
        # OpenVSP deliberately names the Flap group's basis TE_Trim_AbsRel.
        flap = {key: get('Flap', name) for key, name in
                [('mode', 'TE_Flap_Type'), ('basis', 'TE_Trim_AbsRel'), ('length', 'TE_Flap_X'),
                 ('lengthFraction', 'TE_Flap_X_Chord'), ('hinge', 'TE_Flap_Y_Frc'),
                 ('deflection', 'TE_Flap_Deflection'), ('active', 'TE_Flap_Flag'),
                 ('parameter', 'TE_Flap_T'), ('arc', 'TE_Flap_DT')]}
        ids = transforms + [p for c in close + trim for p in c['fields'].values()] + list(flap.values())
        if any(p is None for p in ids): continue
        shape_fields=[p for (group,name),p in by_key.items() if group=='XSecCurve' and name not in (*TRANSFORMS,'Area','HWRatio','FitDegree')]
        chevrons=native_chevrons.controls(v,get)
        if chevrons:ids+=chevrons['parameters']
        yield dict(surface=si, index=i, shape=shape, wing=wing, kind=kind, manualFlapBreak=kind in ('PROP','PROPELLER'), transforms=transforms,
                   close=close, trim=trim, flap=flap, chevrons=chevrons, shapeFields=shape_fields, parameters=ids+shape_fields)


def close_choices(v, edge):
    names = [('CLOSE_NONE', 'Original edge'), ('CLOSE_SKEWLOW', 'Skew lower surface'),
             ('CLOSE_SKEWUP', 'Skew upper surface'), ('CLOSE_SKEWBOTH', 'Skew both surfaces')]
    if edge == 'TE': names.append(('CLOSE_EXTRAP', 'Extrapolate trailing edge'))
    return [[getattr(v, name), label] for name, label in names]


def reasons(v, profile):
    result = {}; point = profile['shape'] == v.XS_POINT
    shape={v.GetParmName(p):p for p in profile.get('shapeFields',[])}
    activity=native_preview.parameter_activity(v,list(shape.values())) if shape else {}
    result.update({pid:'Calculated or unused under the selected native profile family and drivers.' for pid,active in activity.items() if not active})
    if 'CamberInputFlag' in shape and 'Camber' in shape and 'IdealCl' in shape:
        follower='IdealCl' if v.GetParmVal(shape['CamberInputFlag'])==v.MAX_CAMB else 'Camber'
        result[shape[follower]]='Calculated by OpenVSP from the selected camber driver and camber location.'
    if 'SymmThick' in shape and v.GetParmVal(shape['SymmThick']):
        for name in ('ThickLocLow','FlatLow'):
            if name in shape:result[shape[name]]='Follows the upper surface while symmetric thickness is enabled.'
    if 'Super_TopBotSym' in shape and v.GetParmVal(shape['Super_TopBotSym']):
        for name in ('Super_M_bot','Super_N_bot'):
            if name in shape:result[shape[name]]='Follows the upper exponent while top/bottom symmetry is enabled.'
    if 'RoundedRect_RadiusSymmetryType' in shape:
        mode=v.GetParmVal(shape['RoundedRect_RadiusSymmetryType'])
        followers={v.SYM_ALL:('RoundRectXSec_RadiusBR','RoundRectXSec_RadiusBL','RoundRectXSec_RadiusTL'),v.SYM_TB:('RoundRectXSec_RadiusBR','RoundRectXSec_RadiusBL'),v.SYM_RL:('RoundRectXSec_RadiusBL','RoundRectXSec_RadiusTL')}.get(mode,())
        for name in followers:
            if name in shape:result[shape[name]]='Calculated from the independent corners under the selected radius symmetry.'
    if point:
        return {p: 'Point profiles have no outline to modify. Choose another profile family.' for p in profile['parameters']}
    for cap in profile['close']:
        f = cap['fields']; mode = v.GetParmVal(f['mode']); basis = v.GetParmVal(f['basis'])
        if not profile['wing']:
            result.update({p: 'Edge closure settings apply to wing, blade and body-of-revolution profiles.' for p in f.values()})
        elif mode == v.CLOSE_NONE or mode not in {c[0] for c in close_choices(v, cap['edge'])}:
            result.update({p: 'Calculated or unused with the original edge. Choose a closure method to set an edge gap.' for key, p in f.items() if key != 'mode'})
        else:
            result[f['gapFraction'] if basis == v.ABS else f['gap']] = 'Calculated by OpenVSP from the selected gap and dimension basis.'
    for cap in profile['trim']:
        f = cap['fields']; mode = v.GetParmVal(f['mode']); basis = v.GetParmVal(f['basis'])
        if not profile['wing']:
            result.update({p: 'Edge trimming applies to wing, blade and body-of-revolution profiles.' for p in f.values()})
        elif mode == v.TRIM_NONE:
            result.update({p: 'Calculated or unused with trimming off. Choose a trim method to edit its dimensions.' for key, p in f.items() if key != 'mode'})
        else:
            editable = ('distance' if mode == v.TRIM_X else 'thickness') + ('Fraction' if basis == v.REL else '')
            result.update({p: 'Calculated by OpenVSP from the selected trim method and dimension basis.' for key, p in f.items() if key not in ('mode', 'basis', editable)})
    f = profile['flap']; mode = v.GetParmVal(f['mode']); basis = v.GetParmVal(f['basis'])
    if not profile['wing']:
        result.update({p: 'Profile flaps apply to wing, blade and body-of-revolution profiles.' for p in f.values()})
    elif mode == v.FLAP_NONE:
        result.update({p: 'Calculated or unused with the flap off. Choose Plain flap to edit hinge and deflection.' for key, p in f.items() if key != 'mode'})
    else:
        result[f['lengthFraction'] if basis == v.ABS else f['length']] = 'Calculated by OpenVSP from the selected flap length and dimension basis.'
    if profile['manualFlapBreak']:
        if mode != v.FLAP_NONE and (not v.GetParmVal(f['active']) or v.GetParmVal(f['arc']) <= 0):
            result[f['deflection']] = 'Enable blade flap geometry and set a positive hinge transition width before changing deflection.'
    else:
        for key in ('active', 'parameter', 'arc'):
            result[f[key]] = 'Calculated by OpenVSP to align the flap break across native neighboring profiles.'
    # The installed native circular BOR flap path terminates in its setup.
    # Airfoil BOR flap geometry is verified separately with the native SDK.
    if profile['kind']=='BODYOFREVOLUTION' and profile['shape']==v.XS_CIRCLE:
        result.update({p:'Choose an airfoil profile for a body-of-revolution flap.' for p in f.values()})
    result.update(native_chevrons.reasons(v,profile))
    return result


def enrich(v, gid, params, sections):
    by_id = {p['id']: p for p in params}; bor = None
    for profile in profiles(v, gid):
        locked = reasons(v, profile); active = native_preview.parameter_activity(v, profile['parameters'])
        for pid in profile['parameters']:
            p = by_id[pid]; p['active'] = active[pid]
            if pid in locked: p.update(displayReadOnly=True, readOnlyReason=locked[pid])
        shape_labels={'Chord':'Profile chord','ThickChord':'Thickness / chord','Camber':'Maximum camber / chord','CamberLoc':'Camber location / chord','IdealCl':'Design lift coefficient','Invert':'Invert profile','SharpTEFlag':'Sharp trailing edge','CamberInputFlag':'Camber driver'}
        shape_labels.update({'Super_M':'Upper horizontal exponent','Super_N':'Upper vertical exponent','Super_M_bot':'Lower horizontal exponent','Super_N_bot':'Lower vertical exponent','Super_TopBotSym':'Match top and bottom shape','Super_MaxWidthLoc':'Maximum width location','Super_Width':'Profile width','Super_Height':'Profile height','RoundedRect_RadiusSymmetryType':'Corner radius symmetry','RoundRectXSec_Radius':'Top-right corner radius','RoundRectXSec_RadiusTL':'Top-left corner radius','RoundRectXSec_RadiusBR':'Bottom-right corner radius','RoundRectXSec_RadiusBL':'Bottom-left corner radius','RoundedRect_Width':'Profile width','RoundedRect_Height':'Profile height','RoundRect_Skew':'Horizontal skew','RoundRect_VSkew':'Vertical skew','RoundRect_Keystone':'Keystone taper','RoundRectXSec_KeyCorner':'Key corner'})
        shape_labels.update({'ThickLoc':'Upper maximum thickness location / chord','ThickLocLow':'Lower maximum thickness location / chord','LERadIndx':'Leading-edge radius index','FlatUp':'Upper plateau length / chord','FlatLow':'Lower plateau length / chord','ZCamber':'Camber height / chord','UForeUp':'Upper forward corner U','UForeLow':'Lower forward corner U','DuUp':'Upper plateau U extent','DuLow':'Lower plateau U extent','SymmThick':'Symmetric thickness distribution'})
        for pid in profile['shapeFields']:
            p=by_id[pid]
            if p['name'] in shape_labels:p['label']=shape_labels[p['name']]
            if p['description']=='Default Description':p['description']={'Camber':'Maximum camber as a fraction of chord.','CamberLoc':'Position of maximum camber along the chord.','ThickChord':'Maximum thickness as a fraction of chord.','CamberInputFlag':'Choose maximum camber or design lift coefficient as the input.','IdealCl':'Lift coefficient used to define the airfoil camber.','Invert':'Flip the airfoil vertically.','SharpTEFlag':'Use a sharp trailing edge.','Chord':'Section chord; wing section drivers or blade distributions may determine this value.'}.get(p['name'],'')
            if p['name'] in ('Chord','Super_Width','Super_Height','RoundedRect_Width','RoundedRect_Height') or p['name'].startswith('RoundRectXSec_Radius'):p['dimension']='length'
            if p['name']=='RoundedRect_RadiusSymmetryType':p['choices']=[[v.SYM_NONE,'Independent corners'],[v.SYM_RL,'Match right / left'],[v.SYM_TB,'Match top / bottom'],[v.SYM_ALL,'Match all corners']]
            if p['name']=='ThickLoc' and profile['shape']!=v.XS_WEDGE:p['label']='Maximum thickness location / chord'
            if p['name']=='Tau' and profile['shape']==v.XS_VKT_AIRFOIL:p.update(label='Trailing-edge angle',dimension='angle')
            if p['name']=='Series' and profile['shape']==v.XS_SIX_SERIES:p.update(label='NACA six-series family',choices=[[i,n] for i,n in enumerate(('63','64','65','66','67','63A','64A','65A'))],description='Select the original NACA six-series pressure-distribution family.')
            if p['name']=='A' and profile['shape']==v.XS_SIX_SERIES:p.update(label='Loading extent a',description='Fraction of chord with uniform loading. A-series profiles fix this value at 0.8.')
            if p['name']=='CamberInputFlag':p['choices']=[[v.MAX_CAMB,'Maximum camber'],[v.DESIGN_CL,'Design lift coefficient']]
        for pid, label in zip(profile['transforms'], ('Profile rotation', 'Profile scale',
                'Profile X offset (width fraction)', 'Profile Y offset (width fraction)', 'Leading-edge alignment')):
            p = by_id[pid]; p['label'] = label
            p['description'] = 'Native local profile transform, applied before the section is placed on the aircraft.' if p['name'] != 'ShiftLE' else 'Controls how neighboring profiles line up along the section parameter.'
            if p['name'] == 'Theta': p['dimension'] = 'angle'
        for cap in profile['close']:
            f = cap['fields']; edge = cap['label']
            by_id[f['mode']].update(label=edge + ' closure', choices=close_choices(v, cap['edge']),
                description='Choose how the native upper and lower surfaces meet at this edge.')
            by_id[f['basis']].update(label=edge + ' gap basis', choices=[[v.ABS, 'Length'], [v.REL, 'Fraction of chord / width']])
            by_id[f['basis']]['description'] = 'Choose a length in the model convention or a fraction of native chord / profile width.'
            by_id[f['gap']].update(label=edge + ' gap', dimension='length')
            by_id[f['gapFraction']]['label'] = edge + ' gap / chord'
        for cap in profile['trim']:
            f = cap['fields']; edge = cap['label']
            by_id[f['mode']].update(label=edge + ' trim', choices=[[v.TRIM_NONE, 'No trimming'], [v.TRIM_X, 'By distance'], [v.TRIM_THICK, 'By thickness']],
                description='OpenVSP finds the new edge from the chosen distance or thickness.')
            by_id[f['basis']].update(label=edge + ' trim basis', choices=[[v.ABS, 'Length'], [v.REL, 'Fraction of chord / width']])
            by_id[f['basis']]['description'] = 'Choose a length in the model convention or a fraction of native chord / profile width.'
            for key, label in [('distance', 'trim distance'), ('distanceFraction', 'trim distance / chord'),
                               ('thickness', 'trim thickness'), ('thicknessFraction', 'trim thickness / chord')]:
                by_id[f[key]]['label'] = edge + ' ' + label
                if key in ('distance', 'thickness'): by_id[f[key]]['dimension'] = 'length'
        f = profile['flap']
        by_id[f['mode']].update(label='Trailing-edge flap', choices=[[v.FLAP_NONE, 'Off'], [v.FLAP_PLAIN, 'Plain flap']],
            description='Changes the native profile shape at its trailing edge. For surface-region control groups, use Modeling tools.')
        by_id[f['basis']].update(label='Flap length basis', choices=[[v.ABS, 'Length'], [v.REL, 'Fraction of chord / width']])
        by_id[f['basis']]['description'] = 'Flap length follows the chosen absolute length or chord / width fraction.'
        by_id[f['length']].update(label='Flap length from trailing edge', dimension='length')
        by_id[f['lengthFraction']]['label'] = 'Flap length / chord'
        by_id[f['hinge']].update(label='Hinge position through thickness', description='Fraction from the lower to the upper profile surface at the hinge; 0.5 is halfway through.')
        by_id[f['deflection']].update(label='Flap deflection', dimension='angle')
        for key, label in [('active', 'Native flap break active'), ('parameter', 'Native flap break parameter'), ('arc', 'Native flap arc parameter')]:
            by_id[f[key]]['label'] = label
        if profile['manualFlapBreak']:
            by_id[f['active']].update(label='Enable blade flap geometry', description='This native engine requires explicit blade flap break settings. Enter the hinge transition width before applying nonzero deflection.')
            by_id[f['parameter']].update(label='Blade flap alignment break', description='Native profile parameter fraction used to align the flap break. Use a matching break on neighboring blade profiles.')
            by_id[f['arc']].update(label='Hinge transition width', description='Native profile parameter width for the hinge arc. A deflected blade flap needs a positive width; alignment break plus width must be below 1.')
        for cap in profile['close']:
            p = by_id[cap['fields']['mode']]
            if p['value'] not in {c[0] for c in p['choices']}:
                p['choices'].append([p['value'], f'Saved native value {p["value"]:g} (outside supported closure choices)'])
        native_chevrons.enrich(v,profile['chevrons'],by_id)
        chevrons=profile['chevrons']
        if (chevrons and profile['manualFlapBreak'] and
                v.GetParmVal(chevrons['mode'])==v.CHEVRON_PARTIAL and
                any(v.GetParmVal(pid)!=0 for pid in chevrons['pattern'][3:])):
            chevrons['notice']='This combination has produced inconsistent blade shapes in OpenVSP. Its results are not yet reliable.'
        # Keep dormant body edge fields in advanced settings; local transforms
        # and actual profile samples still have a guided body workflow.
        profile['edgeEditing'] = profile['wing'] and profile['shape'] != v.XS_POINT
        if profile['surface'] is None:
            profile['preview'] = [[p.x(), p.y(), p.z()] for p in (v.ComputeBORXSecPnt(gid, i / 100) for i in range(101))]
            bor = profile
        else:
            section = next(s for s in sections if s['surface'] == profile['surface'] and s['index'] == profile['index'])
            section['profileControls'] = profile
    return bor


def read_only_reasons(v):
    return {pid: reason for gid in v.FindGeoms() for profile in profiles(v, gid) for pid, reason in reasons(v, profile).items()}


def validate_parameter(v, pid, value=None):
    group = v.GetParmGroupName(pid); name = v.GetParmName(pid)
    if group not in GROUPS and group != 'XSecCurve': return
    owner = next((g for g in v.FindGeoms() if pid in v.GetGeomParmIDs(g)), None)
    if owner is None: return
    for profile in profiles(v, owner):
        if pid not in profile['parameters']: continue
        if group=='Chevron':
            native_chevrons.validate(v,profile,pid,value,owner)
            return
        reason = reasons(v, profile).get(pid)
        if reason: raise ValueError(reason)
        if value is None: return
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Enter a finite profile value.')
        if v.GetParmType(pid) in (v.PARM_INT_TYPE, v.PARM_BOOL_TYPE) and value != int(value):
            raise ValueError('Profile methods and dimension bases require whole numbers.')
        if name == 'LE_Close_Type' and value not in {c[0] for c in close_choices(v, 'LE')}:
            raise ValueError('Leading-edge closure supports Original edge or skewing either or both surfaces. Extrapolation applies to the trailing edge.')
        if profile['manualFlapBreak'] and pid in profile['flap'].values():
            f=profile['flap']; proposed=lambda key:value if pid==f[key] else v.GetParmVal(f[key])
            if proposed('parameter')+proposed('arc')>=1:
                raise ValueError('Blade flap alignment break plus hinge transition width must be below 1.')
            if proposed('active') and proposed('deflection')!=0 and proposed('arc')<=0:
                raise ValueError('A deflected blade flap needs a positive hinge transition width.')
        return


def controller_priority(v, pid):
    if v.GetParmGroupName(pid)=='XSecCurve' and v.GetParmName(pid) in ('CamberInputFlag','Super_TopBotSym','RoundedRect_RadiusSymmetryType','Series','SymmThick'):return 0
    if v.GetParmGroupName(pid) not in GROUPS: return 2
    name = v.GetParmName(pid)
    if v.GetParmGroupName(pid)=='Chevron':return native_chevrons.priority(name)
    if v.GetParmGroupName(pid)=='Flap':
        if name in ('TE_Flap_T','TE_Flap_DT'):return 2
        if name=='TE_Flap_Flag':return 3
        if name=='TE_Flap_Deflection':return 4
    return 0 if name.endswith('_Type') else 1 if name.endswith('_AbsRel') else 2
