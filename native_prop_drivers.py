"""Native actuator-disk choices and dependent-field guidance, without rotor math."""
import native_preview
import native_references

DRIVERS=[('RPM_PROP_DRIVER','RotorRPM','RPM'),('CT_PROP_DRIVER','RotorCT','Thrust coefficient (CT)'),
         ('CP_PROP_DRIVER','RotorCP','Power coefficient (CP)'),('T_PROP_DRIVER','RotorThrust','Thrust'),
         ('ETA_PROP_DRIVER','RotorEta','Efficiency'),('J_PROP_DRIVER','RotorJ','Advance ratio (J)'),
         ('P_PROP_DRIVER','RotorPower','Power'),('CQ_PROP_DRIVER','RotorCQ','Torque coefficient (CQ)'),
         ('Q_PROP_DRIVER','RotorTorque','Torque')]


def configuration(v,cid,refs,parameter):
    choices=refs.get(cid,{}).get('propDrivers',[])
    if len(choices)!=3 or len(set(choices))!=3:
        raise ValueError('The saved native actuator disk has an incomplete driver selection.')
    values={p['name']:p for p in [parameter(v,p) for p in v.FindContainerParmIDs(cid)]}
    drivers=[dict(value=getattr(v,enum),name=name,label=label,parameter=values[name]['id']) for enum,name,label in DRIVERS]
    selected={d['name'] for d in drivers if d['value'] in choices}
    automatic=bool(values['AutoHubDiaFlag']['value'])
    for p in values.values():
        if p['name'] in {d['name'] for d in drivers}:p['active']=p['name'] in selected
        elif p['name']=='RotorDiameter':p['active']=False
        elif p['name']=='RotorHubDiameter':
            p['active']=not automatic
            # UpdateRotorDisks clamps the hub to the current native diameter.
            # Preserve SDK Parm bounds separately from this effective limit.
            p['effectiveMax']=values['RotorDiameter']['value']
            p['description']+=' OpenVSP limits the hub to the current disk diameter when updating the rotor. Automatic hub diameter follows the source propeller geometry.'
    return dict(params=list(values.values()),drivers=drivers,driverChoices=choices)


def mutate(v,r):
    cid=r['id']
    if cid not in [v.FindActuatorDisk(i) for i in range(v.GetNumActuatorDisks())]:
        raise ValueError('This native actuator disk no longer exists.')
    choices=r.get('choices')
    if not isinstance(choices,list) or len(choices)!=3 or any(type(c)!=int for c in choices):
        raise ValueError('Choose three distinct actuator-disk drivers.')
    if sorted(choices) not in native_preview.prop_driver_combinations(v):
        raise ValueError('OpenVSP does not support this combination. Choose three independent drivers.')
    native_references.set_references(v,cid,'Rotor',{'DriverGroup/ChoiceVec':', '.join(map(str,choices))+', '})


def group_read_only_reason(v,pid):
    cid=v.GetParmContainer(pid)
    if cid not in [v.FindUnsteadyGroup(i) for i in range(v.GetNumUnsteadyGroups())]:return None
    name=v.GetParmName(pid)
    if name in ('RotorDia','Ox','Oy','Oz','Rx','Ry','Rz'):
        return 'Calculated by OpenVSP from the rotating group geometry. Sweep the source geometry parameter instead.'
    if name=='RPM':
        kind=v.FindParm(cid,'GeomPropertyType',v.GetParmGroupName(pid))
        if v.GetParmVal(kind)!=2:
            return 'OpenVSP sets this fixed group RPM to zero. Choose a rotating propeller group.'
    return None


def validate_parameter(v,pid):
    reason=group_read_only_reason(v,pid)
    if reason:raise ValueError(reason)
    cid=v.GetParmContainer(pid)
    if cid not in [v.FindActuatorDisk(i) for i in range(v.GetNumActuatorDisks())]:return
    refs=native_references.references(v)
    from native_worker import parameter
    p=next(p for p in configuration(v,cid,refs,parameter)['params'] if p['id']==pid)
    if p.get('active') is False:
        raise ValueError('OpenVSP derives this value. Choose it as a disk driver, or disable automatic hub diameter to edit the hub.')
