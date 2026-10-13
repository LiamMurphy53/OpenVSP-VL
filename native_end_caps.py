"""Guide supported native cap parameters and activity, never cap math.

OpenVSP 3.52.2: Geom::UpdateEndCaps, GeomScreen::UpdateCapControls,
XSecCurve::DetermineWingType/CapLE/CapTE and VspCurve::Modify.
"""
import math
import native_preview

MODES = (
    ('NO_END_CAP', 'None'), ('FLAT_END_CAP', 'Flat'),
    ('ROUND_END_CAP', 'Round'), ('EDGE_END_CAP', 'Edge'),
    ('SHARP_END_CAP', 'Sharp'), ('POINT_END_CAP', 'Point'),
    ('ROUND_EXT_END_CAP_NONE', 'Extended round'),
    ('ROUND_EXT_END_CAP_LE', 'Extended round · leading edge'),
    ('ROUND_EXT_END_CAP_TE', 'Extended round · trailing edge'),
    ('ROUND_EXT_END_CAP_BOTH', 'Extended round · both edges'),
)


def choices(v, profile=False, kind=''):
    supported = ('FLAT_END_CAP', 'ROUND_END_CAP', 'EDGE_END_CAP', 'SHARP_END_CAP')
    return [[getattr(v, name), label] for name, label in MODES
            if (name in supported if profile else
                (kind in ('WING', 'PROP', 'PROPELLER') or not name.startswith('ROUND_EXT_')))]


def records(v, gid):
    """Each record contains original SDK identities, including dormant settings."""
    kind = v.GetGeomTypeName(gid).upper()
    ids = list(v.GetGeomParmIDs(gid))
    end = {v.GetParmName(p): p for p in ids if v.GetParmGroupName(p) == 'EndCap'}
    labels = ('Root', 'Tip') if kind in ('WING', 'PROP', 'PROPELLER') else ('Nose', 'Tail') if kind == 'FUSELAGE' else ('Start', 'End')
    for prefix, label in zip(('CapUMin', 'CapUMax'), labels):
        fields = {key: end.get(prefix + name) for key, name in
                  [('mode', 'Option'), ('length', 'Length'), ('offset', 'Offset'),
                   ('strength', 'Strength'), ('sweep', 'SweepFlag')]}
        if all(fields.values()):
            yield dict(label=label, profile=False, fields=fields, choices=choices(v, kind=kind),
                       unused='This component has no native parametric surfaces to cap.'
                       if not v.GetNumMainSurfs(gid) else '')
    profiles = []
    if kind in ('WING', 'PROP', 'PROPELLER', 'FUSELAGE', 'STACK'):
        for si in range(v.GetNumXSecSurfs(gid)):
            surf = v.GetXSecSurf(gid, si)
            for i in range(v.GetNumXSec(surf)):
                x = v.GetXSec(surf, i)
                profiles.append((si, i, v.GetXSecShape(x), list(v.GetXSecParmIDs(x))))
    elif kind in ('BODYOFREVOLUTION', 'BODYOFREVOLUTIONGEOM', 'BOR'):
        profiles.append((None, None, v.GetBORXSecShape(gid), ids))
    for si, i, shape, pids in profiles:
        by_name = {v.GetParmName(p): p for p in pids if v.GetParmGroupName(p) == 'Cap'}
        for prefix, label in [('LE', 'Leading edge'), ('TE', 'Trailing edge')]:
            fields = {key: by_name.get(prefix + '_Cap_' + name) for key, name in
                      [('mode', 'Type'), ('length', 'Length'), ('offset', 'Offset'), ('strength', 'Strength')]}
            if all(fields.values()):
                unused = 'Point profiles have no edge to shape.' if shape == v.XS_POINT else ''
                if kind in ('FUSELAGE', 'STACK'):
                    unused = 'Profile edge caps apply to wings, propeller blades and bodies of revolution.'
                yield dict(label=label, profile=True, surface=si, index=i, fields=fields, choices=choices(v, True), unused=unused)


def reasons(v, gid, caps=None):
    caps = list(records(v, gid)) if caps is None else caps
    result = {}
    shaped = {getattr(v, name) for name, _ in MODES if name not in
              ('NO_END_CAP', 'FLAT_END_CAP', 'POINT_END_CAP')}
    for cap in caps:
        fields = cap['fields']; mode = v.GetParmVal(fields['mode'])
        allowed = {c[0] for c in cap['choices']}
        for key, pid in fields.items():
            if cap['unused']:
                result[pid] = cap['unused']
            elif key != 'mode' and (mode not in shaped or mode not in allowed):
                result[pid] = 'Unused for this cap shape. Choose Round, Edge or Sharp to edit shaping values.' if cap['profile'] else 'Unused for this cap shape. Choose a shaped cap to edit these values.'
            elif key == 'strength' and mode != v.SHARP_END_CAP:
                result[pid] = 'Tangent strength is set by OpenVSP for this cap shape. Choose Sharp to edit it.'
    return result


def enrich(v, gid, params, sections):
    caps = list(records(v, gid)); by_id = {p['id']: p for p in params}
    locked = reasons(v, gid, caps)
    ids = [pid for cap in caps for pid in cap['fields'].values()]
    tess = next((p for p in params if p['rawGroup'] == 'EndCap' and p['name'] == 'CapUMinTess'), None)
    if tess:
        ids.append(tess['id']); tess['label'] = 'Cap sampling (both ends)'
        tess['description'] = 'Native tessellation count shared by the two ends. This changes display and exported surface sampling, not the cap shape.'
        if not v.GetNumMainSurfs(gid):
            locked[tess['id']] = 'This component has no native parametric surfaces to cap.'
    active = native_preview.parameter_activity(v, ids) if ids else {}
    for pid in ids:
        p = by_id[pid]; p['active'] = active[pid]
        if pid in locked: p.update(displayReadOnly=True, readOnlyReason=locked[pid])
    for cap in caps:
        if not cap['profile'] and v.GetParmVal(cap['fields']['mode']) == v.POINT_END_CAP:
            cap['hint'] = 'OpenVSP closes this surface end to its native cap point. Length, offset, tangent strength and sweep stretch do not apply to Point caps.'
        for key, pid in cap['fields'].items():
            p = by_id[pid]
            p['label'] = cap['label'] + ' ' + dict(mode='cap shape', length='cap length factor',
                offset='cap offset factor', strength='cap tangent strength', sweep='cap sweep stretch')[key]
            if key == 'mode':
                if cap['profile']:
                    p['description'] = 'Native profile edge shaping. Flat preserves the edge; Round, Edge and Sharp use the shaping factors below.'
                p['choices'] = list(cap['choices'])
                if p['value'] not in {c[0] for c in p['choices']}:
                    p['choices'].append([p['value'], f'Saved native value {p["value"]:g} (outside supported cap choices)'])
            elif key in ('length', 'offset'):
                p['description'] = 'Scaled native cap value; independent of the length display units.'
            elif key == 'strength':
                p['description'] = 'Native tangent strength for a Sharp cap. Other cap shapes choose their own strength.'
        if cap['profile']:
            section = next((s for s in sections if s['surface'] == cap['surface'] and s['index'] == cap['index']), None)
            if section is not None and v.GetGeomTypeName(gid).upper() in ('WING', 'PROP', 'PROPELLER'):
                section.setdefault('edgeCapControls', []).append(cap)
    ends = [c for c in caps if not c['profile']]
    if not ends or not v.GetNumMainSurfs(gid): return None
    hints = []
    if v.GetGeomTypeName(gid).upper() in ('FUSELAGE', 'STACK'):
        for si in range(v.GetNumXSecSurfs(gid)):
            surf = v.GetXSecSurf(gid, si)
            for index, label in [(0, ends[0]['label']), (v.GetNumXSec(surf)-1, ends[1]['label'])]:
                if v.GetXSecShape(v.GetXSec(surf, index)) == v.XS_POINT:
                    hints.append(f'{label} (surface {si}) already has a point profile. Choose a non-point end profile in Cross-sections & profiles and set its width and height to shape a cap on an open end.')
                elif v.GetXSecWidth(v.GetXSec(surf, index)) == 0 or v.GetXSecHeight(v.GetXSec(surf, index)) == 0:
                    hints.append(f'{label} (surface {si}) has a zero-width or zero-height end profile. Set both dimensions in Body section dimensions before shaping its cap.')
    kind = v.GetGeomTypeName(gid).upper()
    if kind in ('PROP', 'PROPELLER'):
        hints.append('Root and tip caps apply to each native blade. A disk-only representation has no blade ends to shape.')
    return dict(ends=ends, sampling=tess['id'] if tess else None, hints=hints,
                profile=[c for c in caps if c['profile']] if kind in ('BODYOFREVOLUTION', 'BODYOFREVOLUTIONGEOM', 'BOR') else [])


def read_only_reasons(v):
    result = {}
    for gid in v.FindGeoms():
        result.update(reasons(v, gid))
        if not v.GetNumMainSurfs(gid):
            result.update({p: 'This component has no native parametric surfaces to cap.' for p in v.GetGeomParmIDs(gid)
                           if v.GetParmGroupName(p) == 'EndCap'})
    return result


def study_choices(v):
    """Use the same native cap modes and names as the modeling controls."""
    return {cap['fields']['mode']: dict(label=cap['label']+' cap shape',
                                      choices=[dict(value=value,label=label) for value,label in cap['choices']])
            for gid in v.FindGeoms() for cap in records(v,gid)}


def validate_parameter(v, pid, value=None):
    group = v.GetParmGroupName(pid)
    if group not in ('EndCap', 'Cap'): return
    gid = next((g for g in v.FindGeoms() if pid in v.GetGeomParmIDs(g)), None)
    if not gid: return
    reason = read_only_reasons(v).get(pid)
    if reason: raise ValueError(reason)
    if value is None: return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Enter a finite native cap value.')
    if v.GetParmType(pid) in (v.PARM_INT_TYPE, v.PARM_BOOL_TYPE) and value != int(value):
        raise ValueError('Cap shapes, sweep flags and sampling require whole numbers.')
    if v.GetParmName(pid) in ('LE_Cap_Type', 'TE_Cap_Type') and value not in {c[0] for c in choices(v, True)}:
        raise ValueError('Profile edges support Flat, Round, Edge and Sharp caps. Extended and Point caps apply to surface ends.')
    if controller(v, pid) and group == 'EndCap' and value not in {c[0] for c in choices(v, kind=v.GetGeomTypeName(gid).upper())}:
        raise ValueError('Choose a supported cap shape for this geometry. Extended round caps apply to wings and propeller blades; body ends support None, Flat, Round, Edge, Sharp and Point.')


def controller(v, pid):
    return (v.GetParmGroupName(pid) == 'EndCap' and v.GetParmName(pid) in ('CapUMinOption', 'CapUMaxOption')) or (v.GetParmGroupName(pid) == 'Cap' and v.GetParmName(pid) in ('LE_Cap_Type', 'TE_Cap_Type'))
