"""Compound design controls; every dependent geometry update stays native."""
import math


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
        return dict(kind='wing',thicknessAvailable=thickness_available,camberAvailable=camber_available,sweep=uniform(angles['sweep']) if all(abs(r-.25)<1e-10 for r in references) else None,dihedral=uniform(angles['dihedral']) if not v.GetParmVal(v.FindParm(gid,'RelativeDihedralFlag','WingGeom')) else None,thicknessPercent=100*uniform(thickness) if uniform(thickness) is not None else None,camberPercent=100*uniform(camber) if uniform(camber) is not None else None)
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
        return dict(kind='body',width=max(widths,default=0),height=max(heights,default=0))
    return None


def apply(v,r):
    gid=r['geom'];action=r['control'];value=r['value']
    if gid not in v.FindGeoms():raise ValueError('Choose an existing component.')
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):raise ValueError('Enter a finite value.')
    kind=v.GetGeomTypeName(gid).upper();section_targets=[]
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
    if action in ('wing-sweep','wing-dihedral','wing-thickness','wing-camber'):
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
    for si,index,width,height in section_targets:
        x=v.GetXSec(v.GetXSecSurf(gid,si),index)
        if not math.isclose(v.GetXSecWidth(x),width,rel_tol=1e-9,abs_tol=1e-10) or not math.isclose(v.GetXSecHeight(x),height,rel_tol=1e-9,abs_tol=1e-10):
            raise ValueError('A native section limit prevents proportional resizing. The edit was not saved; adjust that section in Pro.')
    field={'wing-sweep':'sweep','wing-dihedral':'dihedral','wing-thickness':'thicknessPercent','wing-camber':'camberPercent','prop-pitch':'pitch','prop-blades':'blades','prop-thickness':'thicknessPercent','body-width':'width','body-height':'height'}[action]
    actual=metadata(v,gid).get(field)
    if actual is None or not math.isclose(actual,value,rel_tol=1e-9,abs_tol=1e-10):
        raise ValueError('OpenVSP could not apply the requested value consistently under these native limits or constraints. The edit was not saved; configure the individual controls in Pro.')
