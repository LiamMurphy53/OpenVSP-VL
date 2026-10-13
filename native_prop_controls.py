"""Blade shape guidance from native parameters, activity and curve evaluation."""
import native_preview

OUTPUTS={'AF','CLi','Solidity','TSolidity','PSolidity','Chord','TChord','PChord','BalanceX1','BalanceX2'}
ANGLES={'Beta34','Feather','Rotate','Precone','FoldAngle','AzFoldDir','ElFoldDir'}
LABELS={'UseBeta34Flag':'Pitch driver','Beta34':'Pitch at ¾ radius','Feather':'Feather angle','Rotate':'Blade azimuth',
        'Precone':'Pre-cone angle','ReverseFlag':'Reverse rotation','CylindricalSectionsFlag':'Cylindrical sections',
        'PropMode':'Propeller representation','AF':'Activity factor','AFLimit':'Activity integration start (radius fraction)',
        'CLi':'Integrated design lift coefficient','Solidity':'Geometric solidity','TSolidity':'Thrust-weighted solidity',
        'PSolidity':'Power-weighted solidity','Chord':'Mean chord / radius','TChord':'Thrust-weighted chord / radius',
        'PChord':'Power-weighted chord / radius',
        'BladeAzimuthMode':'Blade spacing','BladeAzimuthDeltaFlag':'Blade angle reference',
        'IndividualBladeFoldFlag':'Folding control','FoldAngle':'Blade 1 / shared fold angle',
        'RFoldAx':'Fold axis radial position / radius','AxFoldAx':'Fold axis axial position / radius',
        'OffFoldAx':'Fold axis offset / radius','AzFoldDir':'Fold axis azimuth',
        'ElFoldDir':'Fold axis elevation','BalanceX1':'Native balance along blade 1',
        'BalanceX2':'Native balance perpendicular to blade 1'}
CURVES={'PROP_CHORD':('Chord / radius',None,'Chord','crd'),
        'PROP_TWIST':('Twist','angle','Twist','tw'),
        'PROP_THICK':('Thickness / chord',None,'Thick','toc'),
        'PROP_CLI':('Design lift coefficient',None,'CLI','cli'),
        'PROP_RAKE':('Rake / radius',None,'Rake','rak'),
        'PROP_SKEW':('Skew / radius',None,'Skew','skw'),
        'PROP_SWEEP':('Sweep','angle','Sweep','sw'),
        'PROP_AXIAL':('Axial offset / radius',None,'Axial','ax'),
        'PROP_TANGENTIAL':('Tangential offset / radius',None,'Tangential','tan')}


def reasons(v,gid):
    ids=list(v.GetGeomParmIDs(gid));active=native_preview.parameter_activity(v,ids);result={}
    individual=bool(v.GetParmVal(gid,'IndividualBladeFoldFlag','Design'))
    for pid in ids:
        name=v.GetParmName(pid);group=v.GetParmGroupName(pid)
        if group=='Design' and name in ('BalanceX1','BalanceX2'):result[pid]='Calculated by OpenVSP from the native blade spacing.'
        elif group=='Design' and name in OUTPUTS:result[pid]='Calculated by OpenVSP from the native blade distributions.'
        elif group=='Design' and name.startswith('FoldAngle_') and not individual:result[pid]='This blade follows the shared native fold angle. Choose individual folding to edit it.'
        elif group=='PropGeom' and name in ('SmallPanelW','MaxGrowth'):result[pid]='Calculated by OpenVSP during native blade tessellation.'
        elif group=='XSecCurve' and name in ('Area','HWRatio'):result[pid]='Calculated by OpenVSP from the profile dimensions supplied by the blade distributions.'
        elif group=='XSec' and name=='RefLength':result[pid]='The native section reference length follows propeller radius.'
        elif not active[pid]:result[pid]='Calculated or locked by OpenVSP. Change the controlling option to edit its source.'
    return active,result


def enrich(v,gid,params,sections):
    active,locked=reasons(v,gid)
    for p in params:
        p['active']=active[p['id']]
        if p['id'] in locked:p.update(displayReadOnly=True,readOnlyReason=locked[p['id']])
        if p['rawGroup']=='Design':
            if p['name'] in LABELS:p['label']=LABELS[p['name']]
            if p['name'] in ANGLES or p['name'].startswith(('BladeAz_','DeltaAz_','FoldAngle_')):p['dimension']='angle'
            if p['name']=='UseBeta34Flag':p['choices']=[[1,'Pitch at ¾ radius'],[0,'Feather angle']]
            if p['name']=='PropMode':p['choices']=[[v.PROP_BLADES,'Individual blades'],[v.PROP_BOTH,'Blades and disk'],[v.PROP_DISK,'Disk only']]
            if p['name']=='BladeAzimuthMode':p['choices']=[[v.PROP_AZI_UNIFORM,'Uniform'],[v.PROP_AZI_FREE,'Free'],[v.PROP_AZI_BALANCED,'Balanced']]
            if p['name']=='BladeAzimuthDeltaFlag':p['choices']=[[0,'Absolute azimuth'],[1,'Offset from uniform spacing']]
            if p['name']=='IndividualBladeFoldFlag':p['choices']=[[0,'All blades together'],[1,'Individual blades']]
            if p['name'].startswith('BladeAz_'):p['label']='Blade '+p['name'].split('_')[-1]+' azimuth'
            if p['name'].startswith('DeltaAz_'):p['label']='Blade '+p['name'].split('_')[-1]+' spacing offset'
            if p['name'].startswith('FoldAngle_'):p['label']='Blade '+str(int(p['name'].split('_')[-1])+1)+' fold angle'
        if p['rawGroup']=='XSec' and p['name']=='RefLength':p['dimension']='length'
        if p['rawGroup']=='XSecCurve':
            if p['name'] in ('Chord','Width','Height','Ellipse_Width','Ellipse_Height','Circle_Diameter'):p['dimension']='length'
            elif p['name']=='Area':p['dimension']='area'
            elif p['name']=='Theta':p['dimension']='angle'
        if p['rawGroup'] in ('Twist','Sweep') and p['name'].startswith(('tw_','sw_')):p['dimension']='angle'
    for section in sections:
        section['propStationControls']=[dict(parameter=pid,label='Profile radius fraction' if v.GetParmName(pid)=='RadiusFrac' else 'Section reference radius')
            for pid in v.GetXSecParmIDs(section['id']) if v.GetParmGroupName(pid)=='XSec' and v.GetParmName(pid) in ('RadiusFrac','RefLength')]


def curve_details(v,gid,curve):
    label,dimension,group,value_prefix=CURVES[curve['name']]
    stations=curve['stations'];sample_stations=[stations[0]+(stations[-1]-stations[0])*i/100 for i in range(101)]
    samples=native_preview.prop_curve_values(v,gid,curve['index'],sample_stations)
    # Only select original native identities; the engine determines constraints.
    pids={v.GetParmName(pid):pid for pid in v.GetGeomParmIDs(gid) if v.GetParmGroupName(pid)==group}
    active=native_preview.parameter_activity(v,list(pids.values()))
    point_controls=[dict(station=pids.get(f'r_{i}'),value=pids.get(f'{value_prefix}_{i}'),
                        stationActive=active.get(pids.get(f'r_{i}'),False),valueActive=active.get(pids.get(f'{value_prefix}_{i}'),False)) for i in range(len(stations))]
    return dict(label=label,dimension=dimension,sampleStations=sample_stations,sampleValues=samples,pointControls=point_controls)


def read_only_reasons(v):
    return {pid:reason for gid in v.FindGeoms() if v.GetGeomTypeName(gid).upper() in ('PROP','PROPELLER') for pid,reason in reasons(v,gid)[1].items()}


def validate_parameter(v,pid):
    owner=next((gid for gid in v.FindGeoms() if v.GetGeomTypeName(gid).upper() in ('PROP','PROPELLER') and pid in v.GetGeomParmIDs(gid)),None)
    if owner:
        reason=reasons(v,owner)[1].get(pid)
        if reason:raise ValueError(reason)
