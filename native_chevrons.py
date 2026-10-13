"""Describe the original native 3D chevron parameters and their activity."""
import math
import native_preview


def refresh(v):
    # Compatibility entry point for callers predating the general profile
    # load repair. Ownership does not depend on chevrons being enabled.
    from native_profile_controls import refresh as refresh_profiles
    return refresh_profiles(v)


def controls(v, get):
    field=lambda name:get('Chevron',name)
    result=dict(mode=field('Chevron_Type'),pattern=[field(n) for n in
        ('Number','On_Duty','Off_Duty','Peak_Radius','Valley_Radius')],
        extent=[field(n) for n in ('W01_Mode','W01_Start_Guide','W01_Start',
            'W01_End_Guide','W01_End','W01_Center_Guide','W01_Center','W01_Width')],
        symmetry=[field(n) for n in ('AllSym','TBSym','RLSym')])
    # Native member names and stored left/right amplitude names are swapped.
    result['directions']=[dict(label=direction,parameters=[field(amplitude),field(direction+'_Angle'),field(direction+'_Slew')])
        for direction,amplitude in [('Top','TopAmplitude'),('Right','LeftAmplitude'),
                                    ('Bottom','BottomAmplitude'),('Left','RightAmplitude')]]
    result['parameters']=[result['mode']]+result['pattern']+result['extent']+result['symmetry']+[p for d in result['directions'] for p in d['parameters']]
    return result if all(result['parameters']) else None


def reasons(v, profile):
    c=profile.get('chevrons')
    if not c:return {}
    if profile['shape']==v.XS_POINT:
        return {p:'Point profiles have no outline to modify. Choose another profile family.' for p in c['parameters']}
    active=native_preview.parameter_activity(v,c['parameters'])
    mode=v.GetParmVal(c['mode'])
    return {p:('Choose Partial or Full chevrons to edit the pattern.' if mode==v.CHEVRON_NONE else
               'Calculated or unused under the selected native coverage, guide or symmetry settings.')
            for p in c['parameters'] if not active[p]}


def enrich(v, c, by_id):
    if not c:return
    by_id[c['mode']].update(label='Chevron coverage',choices=[[v.CHEVRON_NONE,'Off'],[v.CHEVRON_PARTIAL,'Partial outline'],[v.CHEVRON_FULL,'Full outline']],
        description='Adds a native three-dimensional repeating pattern to this profile.')
    for pid,label in zip(c['pattern'],('Chevron count','Peak plateau fraction','Valley plateau fraction','Peak rounding radius','Valley rounding radius')):
        by_id[pid]['label']=label
        by_id[pid]['description']='Native fraction of each chevron cycle; peak and valley plateaus share the available cycle.' if 'fraction' in label else 'Native pattern count.' if label=='Chevron count' else 'Rounds the native chevron corners.'
        if 'radius' in label:by_id[pid]['dimension']='length'
    for pid,label in zip(c['extent'],('Coverage drivers','Start guide','Outline start fraction','End guide',
                                     'Outline end fraction','Center guide','Outline center fraction','Outline width fraction')):
        by_id[pid]['label']=label
        by_id[pid]['description']='Native outline parameter; a partial pattern may wrap across the profile seam.'
    by_id[c['extent'][0]]['choices']=[[v.CHEVRON_W01_SE,'Start and end'],[v.CHEVRON_W01_CW,'Center and width']]
    guides=[[v.W_FREE,'Free position'],[v.W_RIGHT_0,'Right / seam start'],[v.W_BOTTOM,'Bottom'],
            [v.W_LEFT,'Left'],[v.W_TOP,'Top'],[v.W_RIGHT_1,'Right / seam end']]
    for pid in c['extent'][1::2][:3]:by_id[pid]['choices']=guides
    for pid,label in zip(c['symmetry'],('Match all directions','Match top and bottom','Match right and left')):
        by_id[pid].update(label=label,description='OpenVSP derives matching amplitudes and directions from the independent side.')
    for d in c['directions']:
        for pid,label,dimension in zip(d['parameters'],('amplitude','direction angle','slew angle'),('length','angle','angle')):
            by_id[pid].update(label=d['label']+' chevron '+label,dimension=dimension,
                description='Native displacement magnitude.' if label=='amplitude' else 'Native orientation of the chevron displacement at this outline guide.')


def validate(v, profile, pid, value, gid):
    c=profile.get('chevrons')
    if not c or pid not in c['parameters']:return
    if profile['kind']=='BODYOFREVOLUTION':
        native_preview.refresh_profile(v,c['mode'],gid)
    reason=reasons(v,profile).get(pid)
    if reason:raise ValueError(reason)
    if value is not None:
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('Enter a finite chevron value.')
        if v.GetParmType(pid) in (v.PARM_INT_TYPE,v.PARM_BOOL_TYPE) and value!=int(value):
            raise ValueError('Chevron counts, choices and switches require whole numbers.')
        proposed={v.GetParmName(p):(value if p==pid else v.GetParmVal(p)) for p in c['parameters']}
        if proposed['Chevron_Type']==v.CHEVRON_PARTIAL:
            if proposed['W01_Mode']==v.CHEVRON_W01_CW:
                empty=proposed['W01_Width']==0
            else:
                position=lambda side:proposed['W01_'+side] if proposed['W01_'+side+'_Guide']==v.W_FREE else proposed['W01_'+side+'_Guide']/4
                empty=position('Start')==position('End')
            if empty:raise ValueError('Partial chevrons need a nonzero outline width. Choose different start/end positions, increase width, or turn chevrons off.')


def priority(name):
    if name=='Chevron_Type':return 0
    if name in ('W01_Mode','AllSym'):return 1
    if name.endswith('_Guide') or name in ('TBSym','RLSym'):return 2
    return 3
