"""Compound design controls; every dependent geometry update stays native."""
import math


def body_stations(v,gid):
    """Eligible axial stations for a compound fuselage end-length edit."""
    if v.GetGeomTypeName(gid).upper()!='FUSELAGE':return None
    surf=v.GetXSecSurf(gid,0)
    sections=[v.GetXSec(surf,i) for i in range(v.GetNumXSec(surf))]
    if len(sections)<4 or any(v.GetXSecShape(x)!=v.XS_POINT for x in (sections[0],sections[-1])) or any(v.GetXSecShape(x)==v.XS_POINT for x in sections[1:-1]):return None
    ids=[v.GetXSecParm(x,'XLocPercent') for x in sections]
    positions=[v.GetParmVal(p) for p in ids]
    length=v.GetParmVal(gid,'Length','Design')
    if length<=0 or any(b<=a for a,b in zip(positions,positions[1:])):return None
    return ids,positions,length


def wing_twist_stations(v,gid):
    surf=v.GetXSecSurf(gid,0)
    sections=[v.GetXSec(surf,i) for i in range(v.GetNumXSec(surf))]
    spans=[v.GetParmVal(v.GetXSecParm(x,'Span')) for x in sections[1:]]
    if not spans or any(span<=0 for span in spans):return None
    positions=[0]
    for span in spans:positions.append(positions[-1]+span)
    twists=[v.GetParmVal(v.GetXSecParm(x,'Twist')) for x in sections]
    if v.GetParmVal(gid,'RelativeTwistFlag','WingGeom'):
        for i in range(1,len(twists)):twists[i]+=twists[i-1]
    return sections,[p/positions[-1] for p in positions],twists


def wing_planform(v,gid):
    """Native station chords and section spans for a whole-wing taper recipe."""
    if v.GetGeomTypeName(gid).upper()!='WING':return None
    surf=v.GetXSecSurf(gid,0)
    sections=[v.GetXSec(surf,i) for i in range(1,v.GetNumXSec(surf))]
    if not sections:return None
    spans=[v.GetParmVal(v.GetXSecParm(x,'Span')) for x in sections]
    chords=[v.GetParmVal(v.GetXSecParm(sections[0],'Root_Chord'))]+[v.GetParmVal(v.GetXSecParm(x,'Tip_Chord')) for x in sections]
    if any(not math.isfinite(x) or x<=0 for x in spans) or chords[0]<=0 or any(not math.isfinite(x) or x<0 for x in chords):return None
    return sections,spans,chords


def metadata(v,gid):
    kind=v.GetGeomTypeName(gid).upper()
    if kind=='WING':
        surf=v.GetXSecSurf(gid,0);angles={'sweep':[],'dihedral':[]};thickness=[];camber=[];thickness_ids=[];camber_drivers=0
        for i in range(v.GetNumXSec(surf)):
            x=v.GetXSec(surf,i);ids=list(v.GetXSecParmIDs(x));by_name={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in ids}
            if i:
                for key,name in [('sweep','Sweep'),('dihedral','Dihedral')]:
                    p=by_name.get(('XSec',name))
                    if p:angles[key].append(v.GetParmVal(p))
            p=by_name.get(('XSecCurve','ThickChord'))
            if p:thickness.append(v.GetParmVal(p));thickness_ids.append(p)
            cp=by_name.get(('XSecCurve','Camber'))
            if cp:camber.append(v.GetParmVal(cp))
            if by_name.get(('XSecCurve','CamberInputFlag')):camber_drivers+=1
        references=[v.GetParmVal(v.GetXSecParm(v.GetXSec(surf,i),'Sweep_Location')) for i in range(1,v.GetNumXSec(surf))]
        uniform=lambda values:values[0] if values and all(abs(a-values[0])<1e-10 for a in values) else None
        from native_preview import parameter_activity
        thickness_available=len(thickness)==v.GetNumXSec(surf) and all(parameter_activity(v,thickness_ids).values())
        camber_available=len(camber)==v.GetNumXSec(surf) and camber_drivers==v.GetNumXSec(surf)
        stations=wing_twist_stations(v,gid);washout=None
        if stations:
            sections,fractions,twists=stations
            difference=twists[0]-twists[-1]
            if all(math.isclose(t,twists[0]-difference*f,abs_tol=1e-9) for t,f in zip(twists,fractions)) and all(math.isclose(v.GetParmVal(v.GetXSecParm(x,'Twist_Location')),.25,abs_tol=1e-10) for x in sections):washout=difference
        planform=wing_planform(v,gid)
        return dict(kind='wing',taperAvailable=bool(planform),taper=planform[2][-1]/planform[2][0] if planform else None,aspectRatio=v.GetParmVal(gid,'TotalAR','WingGeom'),washoutAvailable=bool(stations),washout=washout,thicknessAvailable=thickness_available,camberAvailable=camber_available,sweep=uniform(angles['sweep']) if all(abs(r-.25)<1e-10 for r in references) else None,dihedral=uniform(angles['dihedral']) if not v.GetParmVal(v.FindParm(gid,'RelativeDihedralFlag','WingGeom')) else None,thicknessPercent=100*uniform(thickness) if uniform(thickness) is not None else None,camberPercent=100*uniform(camber) if uniform(camber) is not None else None)
    if kind in ('PROP','PROPELLER'):
        values=list(v.PCurveGetValVec(gid,v.PROP_THICK))
        thickness=values[0]*100 if values and all(abs(a-values[0])<1e-10 for a in values) else None
        return dict(kind='prop',pitch=v.GetParmVal(gid,'Beta34','Design'),blades=int(v.GetParmVal(gid,'NumBlade','Design')),thicknessPercent=thickness)
    if kind in ('FUSELAGE','STACK'):
        widths=[];heights=[]
        for si in range(v.GetNumXSecSurfs(gid)):
            s=v.GetXSecSurf(gid,si)
            for i in range(v.GetNumXSec(s)):
                x=v.GetXSec(s,i)
                if v.GetXSecShape(x)!=v.XS_POINT:widths.append(v.GetXSecWidth(x));heights.append(v.GetXSecHeight(x))
        result=dict(kind='body',width=max(widths,default=0),height=max(heights,default=0))
        stations=body_stations(v,gid)
        if stations:
            _,positions,length=stations
            result.update(noseLength=length*(positions[1]-positions[0]),tailLength=length*(positions[-1]-positions[-2]))
        return result
    return None


def apply(v,r):
    gid=r['geom'];action=r['control'];value=r['value']
    if gid not in v.FindGeoms():raise ValueError('Choose an existing component.')
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):raise ValueError('Enter a finite value.')
    kind=v.GetGeomTypeName(gid).upper();section_targets=[];parameter_targets=[]
    def set_value(pid,val):
        if not v.ValidParm(pid) or not v.GetParmLowerLimit(pid)<=val<=v.GetParmUpperLimit(pid):raise ValueError('The requested value is outside a native parameter limit.')
        v.SetParmValUpdate(pid,val)
    if action=='wing-mount':
        if type(r.get('followOrientation',False))!=bool:raise ValueError('Choose whether to follow wing axes.')
        parent=r['parent']
        if parent not in v.FindGeoms() or v.GetGeomTypeName(parent).upper()!='WING':raise ValueError('Choose an existing parent wing.')
        if not 0<=value<=100:raise ValueError('Use a span position from 0 to 100 percent.')
        import native_tools
        native_tools.mutate(v,dict(operation='reparent',geom=gid,parent=parent))
        set_value(v.FindParm(gid,'Trans_Attach_Flag','Attach'),v.ATTACH_TRANS_EtaMN)
        set_value(v.FindParm(gid,'Rots_Attach_Flag','Attach'),v.ATTACH_ROT_COMP if r.get('followOrientation') else v.ATTACH_ROT_NONE)
        set_value(v.FindParm(gid,'Abs_Or_Relitive_flag','XForm'),1)
        for name,val in [('Eta_Attach_Location',value/100),('M_Attach_Location',.5),('N_Attach_Location',.5)]:set_value(v.FindParm(gid,name,'Attach'),val)
        for axis in 'XYZ':set_value(v.FindParm(gid,axis+'_Rel_Location','XForm'),0)
        v.Update();return
    if action=='wing-aspect-ratio':
        if kind!='WING':raise ValueError('Choose a wing.')
        v.Update()
        area=v.GetParmVal(gid,'TotalArea','WingGeom')
        aspect=v.GetParmVal(gid,'TotalAR','WingGeom')
        span=v.GetParmVal(gid,'TotalProjectedSpan','WingGeom')
        if value<=0 or area<=0 or aspect<=0 or span<=0:raise ValueError('Aspect ratio, wing area and projected span must be positive.')
        # Native projected-span editing keeps chords fixed, so AR changes linearly.
        # Native area editing then scales span and chords together, retaining AR.
        set_value(v.FindParm(gid,'TotalProjectedSpan','WingGeom'),span*value/aspect)
        v.Update()
        set_value(v.FindParm(gid,'TotalArea','WingGeom'),area)
        v.Update()
        if not math.isclose(v.GetParmVal(gid,'TotalArea','WingGeom'),area,rel_tol=1e-9,abs_tol=1e-10):raise ValueError('Native section limits prevent retaining wing area. The edit was not saved.')
    elif action=='wing-taper':
        if kind!='WING':raise ValueError('Choose a wing.')
        planform=wing_planform(v,gid)
        if not planform or value<0:raise ValueError('Overall taper must be nonnegative; section spans and root chord must be positive. Configure degenerate sections in Pro.')
        sections,spans,chords=planform
        area=v.GetParmVal(gid,'TotalArea','WingGeom')
        projected=v.GetParmVal(gid,'TotalProjectedSpan','WingGeom')
        if area<=0:raise ValueError('Wing area must be positive.')
        # Progressively scale existing station chords, retaining planform
        # features instead of replacing every section with a straight taper.
        factor=value/(chords[-1]/chords[0]) if chords[-1]>0 else None;position=0;targets=[chords[0]];total_span=sum(spans)
        for span,chord in zip(spans,chords[1:]):
            position+=span
            targets.append(chord*(1+(factor-1)*position/total_span) if factor is not None else chord+chords[0]*value*position/total_span)
        targets[-1]=chords[0]*value  # Avoid cancellation at very small taper.
        for i in range(1,len(sections)+1):v.SetDriverGroup(gid,i,v.SPAN_WSECT_DRIVER,v.ROOTC_WSECT_DRIVER,v.TIPC_WSECT_DRIVER)
        for x,span,root,tip in zip(sections,spans,targets,targets[1:]):
            for name,target in [('Span',span),('Root_Chord',root),('Tip_Chord',tip)]:set_value(v.GetXSecParm(x,name),target)
        v.Update()
        current_area=v.GetParmVal(gid,'TotalArea','WingGeom')
        chord=v.GetParmVal(gid,'TotalChord','WingGeom')
        if current_area<=0 or chord<=0:raise ValueError('Native chord limits prevent this taper. The edit was not saved.')
        # Original UpdateTotalChord scales chords only. Read native area back
        # to normalize the result; no wing area equation is reproduced.
        set_value(v.FindParm(gid,'TotalChord','WingGeom'),chord*area/current_area)
        v.Update()
        actual=wing_planform(v,gid)
        if not actual or any(not math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-10) for a,b in zip(spans,actual[1])) or not math.isclose(v.GetParmVal(gid,'TotalArea','WingGeom'),area,rel_tol=1e-9,abs_tol=1e-10) or not math.isclose(v.GetParmVal(gid,'TotalProjectedSpan','WingGeom'),projected,rel_tol=1e-9,abs_tol=1e-10):
            raise ValueError('Native section limits prevent retaining wing area and spans. The edit was not saved.')
    elif action=='wing-washout':
        if kind!='WING':raise ValueError('Choose a wing.')
        stations=wing_twist_stations(v,gid)
        if not stations:raise ValueError('Every wing section needs positive span for distributed washout. Configure sections in Pro.')
        sections,fractions,twists=stations
        for x,fraction in zip(sections,fractions):
            parameter_targets.extend([(v.GetXSecParm(x,'Twist_Location'),.25),(v.GetXSecParm(x,'Twist'),twists[0]-value*fraction)])
        # Check the whole recipe before changing its reference mode.
        if any(not v.GetParmLowerLimit(p)<=target<=v.GetParmUpperLimit(p) for p,target in parameter_targets):raise ValueError('Requested washout exceeds a native section twist limit.')
        set_value(v.FindParm(gid,'RelativeTwistFlag','WingGeom'),0)
        for pid,target in parameter_targets:set_value(pid,target)
    elif action in ('wing-sweep','wing-dihedral','wing-thickness','wing-camber'):
        if kind!='WING':raise ValueError('Choose a wing.')
        s=v.GetXSecSurf(gid,0)
        if action=='wing-dihedral':set_value(v.FindParm(gid,'RelativeDihedralFlag','WingGeom'),0)
        for i in range(v.GetNumXSec(s)):
            if action not in ('wing-thickness','wing-camber') and i==0:continue
            x=v.GetXSec(s,i);ids=list(v.GetXSecParmIDs(x));lookup={(v.GetParmGroupName(p),v.GetParmName(p)):p for p in ids}
            if action=='wing-sweep':
                drivers=list(v.GetDriverGroup(gid,i))
                if v.SECSWEEP_WSECT_DRIVER in drivers:v.SetDriverGroup(gid,i,v.SPAN_WSECT_DRIVER,v.ROOTC_WSECT_DRIVER,v.TIPC_WSECT_DRIVER)
                set_value(lookup[('XSec','Sweep_Location')],.25);set_value(lookup[('XSec','Sweep')],value)
            elif action=='wing-dihedral':set_value(lookup[('XSec','Dihedral')],value)
            elif action=='wing-camber':
                pid=lookup.get(('XSecCurve','Camber'));driver=lookup.get(('XSecCurve','CamberInputFlag'))
                if not pid or not driver:raise ValueError('Every profile needs a maximum-camber driver for this control. Configure incompatible profiles in Pro first.')
                set_value(driver,v.MAX_CAMB)
                import native_profile_controls
                native_profile_controls.validate_parameter(v,pid,value/100);set_value(pid,value/100)
            else:
                pid=lookup.get(('XSecCurve','ThickChord'))
                if not pid:raise ValueError('Every wing profile needs an editable thickness/chord parameter for uniform thickness. Configure that profile in Pro first.')
                import native_profile_controls
                native_profile_controls.validate_parameter(v,pid,value/100);set_value(pid,value/100)
    elif action in ('prop-pitch','prop-blades','prop-thickness'):
        if kind not in ('PROP','PROPELLER'):raise ValueError('Choose a propeller.')
        if action=='prop-pitch':
            set_value(v.FindParm(gid,'UseBeta34Flag','Design'),1)
            set_value(v.FindParm(gid,'Beta34','Design'),value)
        elif action=='prop-blades':
            if value!=int(value):raise ValueError('Enter a whole number of blades.')
            set_value(v.FindParm(gid,'BladeAzimuthMode','Design'),v.PROP_AZI_UNIFORM)
            set_value(v.FindParm(gid,'NumBlade','Design'),value)
        else:
            ratio=value/100
            ids=[p for p in v.GetGeomParmIDs(gid) if v.GetParmGroupName(p)=='Thick' and v.GetParmName(p).startswith('toc_')]
            if not ids or any(not v.GetParmLowerLimit(p)<=ratio<=v.GetParmUpperLimit(p) for p in ids):raise ValueError('Use thickness within the native radial-curve limits.')
            stations=list(v.PCurveGetTVec(gid,v.PROP_THICK));typ=v.PCurveGetType(gid,v.PROP_THICK)
            v.SetPCurve(gid,v.PROP_THICK,stations,[ratio]*len(stations),typ)
    elif action in ('body-nose','body-tail'):
        stations=body_stations(v,gid)
        if not stations:raise ValueError('Use a fuselage with point ends and at least two ordered interior sections. Configure stations in Pro.')
        ids,positions,length=stations
        a,b=positions[1],positions[-2]
        new_a=positions[0]+value/length if action=='body-nose' else a
        new_b=positions[-1]-value/length if action=='body-tail' else b
        if value<=0 or not positions[0]<new_a<new_b<positions[-1]:raise ValueError('Nose and tail lengths must leave space between the interior body stations.')
        targets=[(ids[i],new_a+(p-a)*(new_b-new_a)/(b-a)) for i,p in enumerate(positions[1:-1],1)]
        if new_a>a or new_b>b:targets.reverse()
        for pid,target in targets:set_value(pid,target)
        v.Update()
        if any(not math.isclose(v.GetParmVal(pid),target,abs_tol=1e-10,rel_tol=1e-9) for pid,target in targets):raise ValueError('Native station limits prevent this end length. The edit was not saved; configure stations in Pro.')
    elif action in ('body-width','body-height'):
        if kind not in ('FUSELAGE','STACK'):raise ValueError('Choose a fuselage or stack.')
        if value<=0:raise ValueError('Enter a positive body dimension.')
        current=metadata(v,gid)['width' if action=='body-width' else 'height']
        if current<=0:raise ValueError('Choose a body with nonzero section dimensions.')
        factor=value/current
        for si in range(v.GetNumXSecSurfs(gid)):
            surf=v.GetXSecSurf(gid,si)
            for i in range(v.GetNumXSec(surf)):
                x=v.GetXSec(surf,i);shape=v.GetXSecShape(x)
                if shape==v.XS_POINT:continue
                width=v.GetXSecWidth(x);height=v.GetXSecHeight(x)
                from native_preview import body_driver_parameters
                ids=body_driver_parameters(v,gid,si,i)
                if shape==v.XS_CIRCLE:v.SetDriverGroup(gid,i,v.WIDTH_XSEC_DRIVER)
                elif ids and v.GetParmName(ids[2])!='ThickChord':v.SetDriverGroup(gid,i,v.WIDTH_XSEC_DRIVER,v.HEIGHT_XSEC_DRIVER)
                if shape==v.XS_CIRCLE:width*=factor;height*=factor
                elif action=='body-width':width*=factor
                else:height*=factor
                v.SetXSecWidthHeight(x,width,height)
                section_targets.append((si,i,width,height))
        v.Update()
    else:raise ValueError('Choose a supported design control.')
    v.Update()
    if any(not math.isclose(v.GetParmVal(pid),target,rel_tol=1e-9,abs_tol=1e-10) for pid,target in parameter_targets):raise ValueError('Native twist constraints prevent distributed washout. The edit was not saved; configure sections in Pro.')
    for si,index,width,height in section_targets:
        x=v.GetXSec(v.GetXSecSurf(gid,si),index)
        if not math.isclose(v.GetXSecWidth(x),width,rel_tol=1e-9,abs_tol=1e-10) or not math.isclose(v.GetXSecHeight(x),height,rel_tol=1e-9,abs_tol=1e-10):
            raise ValueError('A native section limit prevents proportional resizing. The edit was not saved; adjust that section in Pro.')
    field={'wing-taper':'taper','wing-aspect-ratio':'aspectRatio','wing-washout':'washout','wing-sweep':'sweep','wing-dihedral':'dihedral','wing-thickness':'thicknessPercent','wing-camber':'camberPercent','prop-pitch':'pitch','prop-blades':'blades','prop-thickness':'thicknessPercent','body-width':'width','body-height':'height','body-nose':'noseLength','body-tail':'tailLength'}[action]
    actual=metadata(v,gid).get(field)
    if actual is None or not math.isclose(actual,value,rel_tol=1e-9,abs_tol=0 if action=='wing-taper' else 1e-10):
        raise ValueError('OpenVSP could not apply the requested value consistently under these native limits or constraints. The edit was not saved; configure the individual controls in Pro.')
