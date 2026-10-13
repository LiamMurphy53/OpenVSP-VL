"""SkinScreen/GuiDevice control eligibility; all blending math stays native."""
import native_preview

DIRECTIONS = ('Top', 'Right', 'Bottom', 'Left')
METRICS = (('Angle', 'Tangent angle', 'angle'), ('Strength', 'Tangent strength', None),
           ('Slew', 'Tangent slew', 'angle'), ('Curve', 'Curvature', None))


def enrich_section(v, xid, index, count, parameters):
    ids = set(v.GetXSecParmIDs(xid))
    by_name = {p['name']: p for p in parameters if p['id'] in ids and p['rawGroup'] == 'XSec'}
    if 'AllSym' not in by_name:
        return None
    selected = [by_name[n] for n in ('AllSym', 'TBSym', 'RLSym')]
    selected += [by_name['Continuity' + d] for d in DIRECTIONS]
    selected += [by_name[d + s + m + ending] for d in DIRECTIONS for m, _, _ in METRICS
                 for s, ending in [('L', ''), ('R', ''), ('L', 'Set'), ('R', 'Set'), ('LR', 'Eq')]]
    activity = native_preview.parameter_activity(v, [p['id'] for p in selected])
    for p in selected:
        p['active'] = activity[p['id']]
        p['displayReadOnly'] = False
    def value(n): return by_name[n]['value']
    def lock(n, reason): by_name[n].update(displayReadOnly=True, readOnlyReason=reason)
    all_sym = bool(value('AllSym'))
    if all_sym:
        for n in ('TBSym', 'RLSym'): lock(n, 'All directions already follow Top. Turn off All directions together to edit this symmetry.')
    for d in DIRECTIONS:
        mirrored = (d != 'Top' and all_sym) or (d == 'Bottom' and value('TBSym')) or (d == 'Left' and value('RLSym'))
        continuity = int(value('Continuity' + d))
        if d != 'Top': lock('Continuity' + d, 'OpenVSP enforces continuity for the whole section using Top continuity.')
        elif index in (0, count - 1): lock('ContinuityTop', 'Continuity joins adjacent sections; the first and last sections have only one neighboring section.')
        for metric, _, dimension in METRICS:
            left_set = bool(value(d + 'L' + metric + 'Set'))
            right_set = bool(value(d + 'R' + metric + 'Set'))
            equal = bool(value(d + 'LR' + metric + 'Eq'))
            threshold = 2 if metric == 'Curve' else 1
            for side, enabled in [('L', left_set), ('R', right_set)]:
                n = d + side + metric
                if dimension: by_name[n]['dimension'] = dimension
                if not enabled: lock(n, 'Calculated by OpenVSP while this constraint is automatic. Enable the corresponding manual constraint to edit it.')
                elif side == 'R' and equal: lock(n, 'Follows the before-side value through native equality. Change the before-side value or release equality.')
                n += 'Set'
                if d != 'Top' or metric in ('Strength', 'Slew'):
                    lock(n, 'OpenVSP shares this manual constraint across the section. Tangent angle also controls strength and slew.')
                elif side == 'R' and (equal or continuity >= threshold):
                    lock(n, 'Native equality or continuity determines the after-side manual constraint.')
            if not left_set: lock(d + 'LR' + metric + 'Eq', 'Enable the before-side manual constraint to couple both sides.')
            elif continuity >= threshold: lock(d + 'LR' + metric + 'Eq', 'The selected continuity enforces equality in OpenVSP.')
            if mirrored:
                for n in (d + 'L' + metric, d + 'R' + metric, d + 'L' + metric + 'Set', d + 'R' + metric + 'Set', d + 'LR' + metric + 'Eq'):
                    lock(n, 'Follows another direction through native skinning symmetry.')
    def pid(n): return by_name[n]['id']
    return dict(parameters=[p['id'] for p in selected],
                symmetry=[dict(parameter=pid(n), label=label) for n, label in [('AllSym', 'All directions together'), ('TBSym', 'Top / bottom together'), ('RLSym', 'Right / left together')]],
                continuity=pid('ContinuityTop'),
                manual=[dict(parameter=pid('Top' + side + metric + 'Set'), label=label + ' ' + name)
                        for side, label in [('L', 'Before'), ('R', 'After')]
                        for metric, name in [('Angle', 'manual tangent'), ('Curve', 'manual curvature')]],
                directions=[dict(label=d, metrics=[dict(label=label, before=pid(d + 'L' + metric), after=pid(d + 'R' + metric), equal=pid(d + 'LR' + metric + 'Eq')) for metric, label, _ in METRICS]) for d in DIRECTIONS],
                endpoint=('At the first section, OpenVSP uses Before constraints to shape the outgoing segment; After constraints are unused.' if index == 0 else
                          'At the last section, Before constraints shape the incoming segment; After constraints are unused.' if index == count - 1 else None),
                source='SkinScreen::Update / SkinControl::Update; SkinXSec::ValidateParms / GetRib')


def read_only_reasons(v):
    from native_worker import parameter
    reasons = {}
    for gid in v.FindGeoms():
        if v.GetGeomTypeName(gid).upper() not in ('FUSELAGE', 'STACK'): continue
        parameters = [parameter(v, p) for p in v.GetGeomParmIDs(gid)]
        for surface in range(v.GetNumXSecSurfs(gid)):
            surf = v.GetXSecSurf(gid, surface); count = v.GetNumXSec(surf)
            for i in range(count): enrich_section(v, v.GetXSec(surf, i), i, count, parameters)
        reasons.update({p['id']: p.get('readOnlyReason', 'Locked by OpenVSP.') for p in parameters if p.get('displayReadOnly') or p.get('active') is False})
    return reasons


def validate_parameter(v, pid):
    if not any(v.GetGeomTypeName(g).upper() in ('FUSELAGE', 'STACK') and pid in v.GetGeomParmIDs(g) for g in v.FindGeoms()): return
    reason = read_only_reasons(v).get(pid)
    if reason: raise ValueError(reason)
