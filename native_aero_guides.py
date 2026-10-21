"""Guided VSPAERO input organization. Numerical operations stay in OpenVSP."""
import native_managers
SECTIONS=[
 ('Aircraft geometry',['UseModeFlag','ModeID','GeomSet','ThinGeomSet','Symmetry']),
 ('Reference dimensions',['RefFlag','WingID','Sref','bref','cref','ScurveFlag','MACFlag']),
 ('Moment reference',['Xcg','Ycg','Zcg','UseCGModeFlag','CGModeID','CGGeomSet','CGDegenSet','NumMassSlice','MassSliceDir']),
 ('Flight conditions',['Vinf','Rho','AlphaStart','AlphaEnd','AlphaNpts','BetaStart','BetaEnd','BetaNpts','MachStart','MachEnd','MachNpts','ReCref','ReCrefEnd','ReCrefNpts','ManualVrefFlag','Vref','Machref']),
 ('Propellers and stability',['PropBladesMode','UnsteadyType','FromSteadyState','AutoTimeStepFlag','AutoTimeNumRevs','TimeStepSize','NumTimeSteps','StartAveragingTimeStep']),
 ('Ground and hover',['GroundEffectToggle','GroundEffect','HoverRampFlag','HoverRamp']),
 ('Wake evolution',['FixedWakeFlag','NumWakeNodes','WakeNumIter','WakeRelax','CoreSizeFactor','FreezeWakeAtIteration','FreezeWakeRootVortices','ImplicitWake','ImplicitWakeStartIteration']),
 ('Lift model',['StallModel','CLMax2D','Clo2D']),
 ('Solver accuracy',['NCPU','FarDistToggle','FarDist','FarAway','FreezeMultiPoleAtIteration','QuadTreeBufferLevels','ForwardGMRESConvergenceFactor','AdjointGMRESConvergenceFactor','NonLinearConvergenceFactor','UpdateMatrixPreconditioner','UseWakeNodeMatrixPreconditioner']),
 ('Noise',['NoiseCalcFlag','NoiseCalcType','NoiseUnits']),
 ('Run and exports',['StopBeforeRun','RedirectFile','2DFEMFlag','TecplotFlag'])]


def organization(inputs):
    """Keep every native field exactly once; flag new engine inputs explicitly."""
    available={e['name'] for e in inputs};seen=set();groups=[]
    for title,names in SECTIONS:
        selected=[name for name in names if name in available]
        if seen.intersection(selected):raise ValueError('Duplicate VSPAERO guided input.')
        seen.update(selected)
        if selected:groups.append(dict(title=title,inputs=selected))
    remainder=sorted(available-seen)
    if remainder:groups.append(dict(title='Additional native solver inputs',inputs=remainder))
    return groups


def enum_choices(v):
    """Shared original enum codes for saved settings and analysis inputs."""
    choices=lambda pairs:[dict(value=getattr(v,key),label=label) for key,label in pairs]
    return {
      'RefFlag':choices([('MANUAL_REF','Entered dimensions'),('COMPONENT_REF','Native wing dimensions')]),
      'MassSliceDir':choices([('X_DIR','X · longitudinal'),('Y_DIR','Y · spanwise'),('Z_DIR','Z · vertical')]),
      'PropBladesMode':choices([('VSPAERO_PROP_STATIC','Static blades'),('VSPAERO_PROP_UNSTEADY','Unsteady rotating blades'),('VSPAERO_PROP_PSEUDO_STEADY','Pseudo-steady rotating blades')]),
      'UnsteadyType':choices([('STABILITY_OFF','No stability analysis'),('STABILITY_DEFAULT','Steady stability'),('STABILITY_ADJOINT','Steady adjoint stability'),('STABILITY_PITCH','Simplified pitch'),('STABILITY_P_ANALYSIS','Unsteady roll'),('STABILITY_Q_ANALYSIS','Unsteady pitch'),('STABILITY_R_ANALYSIS','Unsteady yaw')]),
      'StallModel':choices([('STALL_OFF','Off'),('STALL_ON','On')]),
      'NoiseCalcType':choices([('NOISE_FLYBY','Flyby'),('NOISE_FOOTPRINT','Footprint'),('NOISE_STEADY','Steady')]),
      'NoiseUnits':choices([('NOISE_SI','SI · m, N, kg, s'),('NOISE_ENGLISH','English · ft, lbf, slug, s')])}


SET_FIELDS={'GeomSet':'Thick geometry set','ThinGeomSet':'Thin geometry set',
            'MassSet':'Mass geometry set','MassDegenSet':'Mass degenerate geometry set'}


def saved_set_parameter(v,pid):
    return (v.GetParmGroupName(pid)=='VSPAERO' and v.GetParmName(pid) in SET_FIELDS
            and v.GetParmContainer(pid)==native_managers.manager(v,'VSPAEROSettings'))


def validate_saved_parameter(v,pid,value):
    if saved_set_parameter(v,pid) and (type(value) not in (int,float) or value not in range(-1,v.GetNumSets())):
        raise ValueError('Choose an existing native geometry set, or None.')


def annotate_parameter(v,p):
    if p['rawGroup']!='VSPAERO':return
    if v.GetParmContainer(p['id'])!=native_managers.manager(v,'VSPAEROSettings'):return
    if p['name'] in SET_FIELDS:
        p['label']=SET_FIELDS[p['name']]
        p['choices']=[dict(value=-1,label='None')]+[dict(value=i,label=f'{v.GetSetName(i)} · {i}') for i in range(v.GetNumSets())]
        if p['value'] not in range(-1,v.GetNumSets()):p['choices'].append(dict(value=p['value'],label='Unavailable native set · '+str(p['value'])))
        return
    name={'m_PropBladesMode':'PropBladesMode'}.get(p['name'],p['name'])
    options=enum_choices(v).get(name)
    if options:
        p['choices']=[o for o in options if p['min']<=o['value']<=p['max']]
        p['label']={'RefFlag':'Reference dimensions source','MassSliceDir':'Mass slicing direction',
                    'PropBladesMode':'Propeller blade model','UnsteadyType':'Stability analysis',
                    'StallModel':'Stall model','NoiseCalcType':'Noise calculation','NoiseUnits':'Noise units'}[name]


def annotate(v,inputs,geometry=False):
    import re
    cid=native_managers.manager(v,'VSPAEROSettings')
    parms={v.GetParmName(p):p for p in v.FindContainerParmIDs(cid)}
    aliases={'NumWakeNodes':'RootWakeNodes','PropBladesMode':'m_PropBladesMode','FreezeWakeAtIteration':'m_FreezeWakeAtIteration','2DFEMFlag':'Write2DFEMFlag','TecplotFlag':'WriteTecplotFlag','CGGeomSet':'MassSet','CGDegenSet':'MassDegenSet','UseModeFlag':'UseMode','UseCGModeFlag':'CGUseMode','ScurveFlag':'SCurveFlag'}
    maps=enum_choices(v)
    maps['StopBeforeRun']=[dict(value=0,label='Run solver'),dict(value=1,label='Write native solver files only')]
    modes=[dict(value='',label='Choose a mode…')]+[dict(value=m,label=v.GetModeName(m)) for m in v.GetAllModes()]
    maps['ModeID']=modes;maps['CGModeID']=modes
    maps['WingID']=[dict(value='',label='Choose a wing…')]+[dict(value=g,label=v.GetGeomName(g)) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()=='WING']
    if geometry:maps['SingleGeomID']=[dict(value='',label='No additional component')]+[dict(value=g,label=v.GetGeomName(g)) for g in v.FindGeoms() if v.GetGeomTypeName(g).upper()!='BLANK']
    rules={}
    def when(key,controller,values):rules[key]=dict(input=controller,values=values)
    when('CullFrac','CullFracFlag',[1])
    when('ModeID','UseModeFlag',[1])
    for key in ('GeomSet','ThinGeomSet'):when(key,'UseModeFlag',[0])
    when('CGModeID','UseCGModeFlag',[1])
    for key in ('CGGeomSet','CGDegenSet'):when(key,'UseCGModeFlag',[0])
    when('WingID','RefFlag',[v.COMPONENT_REF])
    for key in ('Sref','bref','cref'):when(key,'RefFlag',[v.MANUAL_REF])
    for key in ('MACFlag','ScurveFlag'):when(key,'RefFlag',[v.COMPONENT_REF])
    for key in ('Vref','Machref'):when(key,'ManualVrefFlag',[1])
    when('FarDist','FarDistToggle',[1]);when('GroundEffect','GroundEffectToggle',[1])
    for key in ('NoiseCalcType','NoiseUnits'):when(key,'NoiseCalcFlag',[1])
    rotating=[v.VSPAERO_PROP_UNSTEADY,v.VSPAERO_PROP_PSEUDO_STEADY]
    rules['AutoTimeNumRevs']=dict(all=[dict(input='PropBladesMode',values=rotating),dict(input='AutoTimeStepFlag',values=[1])])
    when('AutoTimeStepFlag','PropBladesMode',rotating)
    when('StartAveragingTimeStep','PropBladesMode',rotating)
    for key in ('TimeStepSize','NumTimeSteps'):rules[key]=dict(all=[dict(input='PropBladesMode',values=rotating),dict(input='AutoTimeStepFlag',values=[0])])
    for key in ('AlphaNpts','BetaNpts','MachNpts','UnsteadyType'):rules[key]=dict(all=[dict(input='PropBladesMode',values=[v.VSPAERO_PROP_STATIC]),dict(input='GroundEffectToggle',values=[0])])
    rules['ReCrefNpts']=dict(all=[dict(input='PropBladesMode',values=[v.VSPAERO_PROP_STATIC]),dict(input='GroundEffectToggle',values=[0]),dict(input='UnsteadyType',values=[v.STABILITY_OFF,v.STABILITY_DEFAULT,v.STABILITY_ADJOINT,v.STABILITY_PITCH])])
    labels={'UseModeFlag':'Geometry selection','UseCGModeFlag':'CG geometry selection','ModeID':'Aircraft mode','CGModeID':'CG mode','GeomSet':'Thick geometry set','ThinGeomSet':'Thin geometry set','CGGeomSet':'CG normal geometry set','CGDegenSet':'CG degenerate geometry set','RefFlag':'Reference dimension source','WingID':'Reference wing','Sref':'Reference area','bref':'Reference span','cref':'Reference chord','ScurveFlag':'Use curved wing area','MACFlag':'Use mean aerodynamic chord','UnsteadyType':'Stability analysis','PropBladesMode':'Propeller blade model','Vinf':'Freestream airspeed','Rho':'Freestream density','NCPU':'Solver processors','NumWakeNodes':'Wake nodes','RedirectFile':'Native output destination','SingleGeomID':'Additional thin component'}
    for e in inputs:
        key=e['name'];pid=parms.get(aliases.get(key,key));e['label']=labels.get(key,re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',key).replace('_',' '))
        if pid:
            e['nativeParameter']=pid;e['min']=v.GetParmLowerLimit(pid);e['max']=v.GetParmUpperLimit(pid)
            if v.GetParmType(pid)==v.PARM_BOOL_TYPE:maps.setdefault(key,[dict(value=0,label='Off'),dict(value=1,label='On')])
        if key in ('UseModeFlag','UseCGModeFlag'):maps[key]=[dict(value=0,label='Geometry sets'),dict(value=1,label='Native mode')]
        if key in ('GroundEffect','FarDist'):
            e['minWhen']=dict(input='GroundEffectToggle' if key=='GroundEffect' else 'FarDistToggle',values=[1],value=0)
        if key in maps:
            e['nativeChoiceValues']=[c['value'] for c in maps[key]]
            e['choices']=list(maps[key])
            if len(e['values'])==1 and e['values'][0] not in [c['value'] for c in e['choices']]:e['choices'].append(dict(value=e['values'][0],label='Current native value · '+str(e['values'][0])))
        if key in ('HoverRampFlag','HoverRamp'):
            e['editable']=False
            e['label']='Legacy hover ramp switch' if key=='HoverRampFlag' else 'Legacy hover ramp value'
            e['description']='Registered legacy input. OpenVSP 3.52.2 preserves this value but does not write it to the VSPAERO solver or use it in its calculations.'
        if key=='SingleGeomID':e['description']='Adds this component’s native degenerate surfaces alongside the selected sets. To prepare only this component, choose None for both geometry sets.'
        if key=='UnsteadyType':e['description']+=' Static-blade unsteady roll, pitch and yaw use the installed solver’s 128-step motion preset and 32 wake nodes; rotating-blade time controls do not change that preset.'
        if key=='AutoTimeStepFlag':e['description']+=' For unsteady rotating blades, automatic timing uses the fastest rotor for the time step. Actual saved times appear in the completed result; the setup retains OpenVSP’s negative automatic values.'
        if key=='AutoTimeNumRevs':e['description']+=' For unsteady rotating blades, this requests revolutions of the fastest rotor. With different rotor speeds, OpenVSP also requires at least two revolutions of the slowest rotor, so the run can contain more steps than this value suggests.'
        if key in rules:e['applicableWhen']=rules[key]
    if geometry:
        return dict(guide=dict(title='VSPAERO geometry preparation',note='OpenVSP prepares the native thin and thick geometry used by the solver. Keep these selections consistent with the flight setup. Refinement and orphan-region culling are native mesh operations.',sensitivityNote='Compare native mesh refinements and solver histories across saved runs.',sections=[dict(title='Geometry selection',inputs=['UseModeFlag','ModeID','GeomSet','ThinGeomSet','SingleGeomID','Symmetry']),dict(title='Native mesh preparation',inputs=['NRef','CullFracFlag','CullFrac','FindBodyWakesFlag'])]))
    return dict(guide=dict(title='VSPAERO flight and solver setup',note='Select native thick and thin geometry, reference dimensions and flight conditions. Rotor groups and blade settings come from the saved aircraft. OpenVSP uses static blades when the selected aircraft has no rotating rotor groups. Rotating blades or ground effect use one alpha, beta, Mach and Reynolds condition and turn stability analysis off; hidden sweep settings remain saved. With automatic reference speed, OpenVSP uses the freestream airspeed. Compare saved solver histories and wake resolution before relying on a result.',sensitivityNote='Compare wake iterations, wake nodes and solver residual histories across saved runs to assess convergence.',sections=organization(inputs)))


def validate(v,schema):
    fields={e['name']:e for e in schema['inputs']}
    def value(key):
        vals=fields[key]['values']
        if len(vals)!=1:raise ValueError(fields[key]['label']+': enter one value.')
        return vals[0]
    def applies(rule):
        if 'any' in rule:return any(applies(r) for r in rule['any'])
        if 'all' in rule:return all(applies(r) for r in rule['all'])
        return value(rule['input']) in rule['values']
    for key,e in fields.items():
        x=value(key)
        if e.get('applicableWhen') and not applies(e['applicableWhen']):continue
        if 'nativeChoiceValues' in e and x not in e['nativeChoiceValues']:
            raise ValueError(e['label']+': choose an available native option.')
        lower=e.get('min');upper=e.get('max')
        if e.get('minWhen') and applies(e['minWhen']):lower=e['minWhen']['value']
        if isinstance(x,(int,float)) and ((lower is not None and x<lower) or (upper is not None and x>upper)):
            raise ValueError(e['label']+': value is outside the native setting limits.')
    if value('UseModeFlag'):
        if value('ModeID') not in v.GetAllModes():raise ValueError('Choose an existing aircraft mode.')
    else:
        sets=[value('GeomSet'),value('ThinGeomSet')]
        single=value('SingleGeomID') if schema['name']=='VSPAEROComputeGeometry' else schema.get('preparedSingleGeomID','')
        if any(s not in range(-1,v.GetNumSets()) for s in sets) or not (any(s>=0 and v.GetGeomSetAtIndex(s) for s in sets) or single in v.FindGeoms()):
            raise ValueError('Choose thick or thin geometry containing components.')
    if schema['name']=='VSPAEROComputeGeometry':return
    if value('UseCGModeFlag') and value('CGModeID') not in v.GetAllModes():raise ValueError('Choose an existing CG mode.')
    if value('RefFlag')==v.COMPONENT_REF:
        g=value('WingID')
        if g not in v.FindGeoms() or v.GetGeomTypeName(g).upper()!='WING':raise ValueError('Choose an existing reference wing.')


def align_geometry(req,flight,preparation):
    """Share explicit selection inputs; reject conflicting active selections.

    Both native analyses retain their own numerical inputs and native defaults.
    A selection supplied only once is used by both phases of the same run.
    """
    import copy
    out=copy.deepcopy(req)
    sides=[('inputs',flight),('geometryInputs',preparation)]
    supplied=[];effective=[]
    for key,spec in sides:
        entries=out.setdefault(key,[])
        supplied.append({e['name']:e for e in entries if e.get('index',0)==0})
        effective.append({e['name']:e['values'] for e in spec['inputs'] if e['index']==0})
    shared=('UseModeFlag','ModeID','GeomSet','ThinGeomSet','Symmetry')
    for name in shared:
        if not all(name in s for s in effective):continue
        for i in (0,1):
            if name in supplied[i]:effective[i][name]=supplied[i][name]['values']
        for i in (0,1):
            if name in supplied[1-i] and name not in supplied[i]:
                entry=copy.deepcopy(supplied[1-i][name]);out[sides[i][0]].append(entry)
                effective[i][name]=entry['values']
    for name in shared:
        if not all(name in s for s in effective):continue
        if name=='ModeID' and effective[0].get('UseModeFlag')==[0] and effective[1].get('UseModeFlag')==[0]:continue
        if name in ('GeomSet','ThinGeomSet') and effective[0].get('UseModeFlag')==[1] and effective[1].get('UseModeFlag')==[1]:continue
        if effective[0][name]!=effective[1][name]:
            label=next(e.get('label',name) for e in flight['inputs'] if e['name']==name)
            raise ValueError(label+': flight setup and geometry preparation must use the same selection. Copy the flight geometry selections into preparation, or edit both before running.')
    return out
