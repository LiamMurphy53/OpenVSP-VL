"""Readable native structural element policies; no meshing calculations here."""
GROUPS = ('FeaPart', 'SubSurface', 'FeaSubSurface')
NAMES = ('CreateBeamElements', 'MarkDelShellElements', 'KeepDelShellElements',
         'Orientation', 'IncludedElements', 'FeaPropertyIndex', 'CapFeaPropertyIndex')
ORIENTATIONS = [
    ('FEA_ORIENT_GLOBAL_X', 'Global X'), ('FEA_ORIENT_GLOBAL_Y', 'Global Y'),
    ('FEA_ORIENT_GLOBAL_Z', 'Global Z'), ('FEA_ORIENT_COMP_X', 'Component X'),
    ('FEA_ORIENT_COMP_Y', 'Component Y'), ('FEA_ORIENT_COMP_Z', 'Component Z'),
    ('FEA_ORIENT_PART_U', 'Part surface U'), ('FEA_ORIENT_PART_V', 'Part surface V'),
    ('FEA_ORIENT_OML_U', 'Outer surface U'), ('FEA_ORIENT_OML_V', 'Outer surface V'),
    ('FEA_ORIENT_OML_R', 'Outer surface R'), ('FEA_ORIENT_OML_S', 'Outer surface S'),
    ('FEA_ORIENT_OML_T', 'Outer surface T'),
]


def reason(v, pid):
    if v.GetParmGroupName(pid) not in GROUPS:
        return ''
    name = v.GetParmName(pid)
    if name == 'IncludedElements':
        return 'Legacy element-selection field. Use shell treatment and Create beam elements.'
    if name in ('FeaPropertyIndex', 'CapFeaPropertyIndex'):
        return 'Legacy property index. Use the saved shell or beam property picker.'
    return ''


def annotate(v, field):
    if field['rawGroup'] not in GROUPS or field['name'] not in NAMES:
        return
    name = field['name']
    if name == 'CreateBeamElements':
        field['label'] = 'Create beam elements'
    elif name in ('MarkDelShellElements', 'KeepDelShellElements'):
        field['label'] = 'Shell element treatment'
        field['choices'] = [dict(value=v.FEA_KEEP, label='Keep shell elements'),
                            dict(value=v.FEA_DELETE, label='Delete shell elements')]
    elif name == 'Orientation':
        field['label'] = 'Material orientation'
        field['choices'] = [dict(value=getattr(v, enum), label=label)
                            for enum, label in ORIENTATIONS
                            if field['min'] <= getattr(v, enum) <= field['max']]
    why = reason(v, field['id'])
    if why:
        field.update(active=False, editable=False, readOnly=True, readOnlyReason=why)


def validate_parameter(v, pid):
    why = reason(v, pid)
    if why:
        raise ValueError(why)
