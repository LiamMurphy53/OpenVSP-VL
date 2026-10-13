"""Guide component drag inputs using original enums and saved native parameters."""
BODY=[('FF_B_MANUAL','Manual'),('FF_B_SCHEMENSKY_FUSE','Schemensky · fuselage'),('FF_B_SCHEMENSKY_NACELLE','Schemensky · nacelle'),('FF_B_HOERNER_STREAMBODY','Hoerner · streamlined body'),('FF_B_TORENBEEK','Torenbeek'),('FF_B_SHEVELL','Shevell'),('FF_B_COVERT','Covert'),('FF_B_JENKINSON_FUSE','Jenkinson · fuselage'),('FF_B_JENKINSON_WING_NACELLE','Jenkinson · wing nacelle'),('FF_B_JENKINSON_AFT_FUSE_NACELLE','Jenkinson · aft fuselage nacelle')]
WING=[('FF_W_MANUAL','Manual'),('FF_W_EDET_CONV','EDET · conventional airfoil'),('FF_W_EDET_ADV','EDET · advanced airfoil'),('FF_W_HOERNER','Hoerner'),('FF_W_COVERT','Covert'),('FF_W_SHEVELL','Shevell'),('FF_W_KROO','Kroo'),('FF_W_TORENBEEK','Torenbeek'),('FF_W_DATCOM','DATCOM'),('FF_W_SCHEMENSKY_6_SERIES_AF','Schemensky · 6-series airfoil'),('FF_W_SCHEMENSKY_4_SERIES_AF','Schemensky · 4-series airfoil'),('FF_W_JENKINSON_WING','Jenkinson · wing'),('FF_W_JENKINSON_TAIL','Jenkinson · tail'),('FF_W_SCHEMENSKY_SUPERCRITICAL_AF','Schemensky · supercritical airfoil')]
LABELS={'PercLam':'Laminar flow (%)','FFBodyEqnType':'Body form-factor equation','FFWingEqnType':'Wing form-factor equation','FFUser':'Manual form factor','Q':'Interference factor','Roughness':'Roughness height (drag length units)','TeTwRatio':'Freestream / wall temperature','TawTwRatio':'Adiabatic wall / wall temperature','IncorporatedGen':'Combine drag with ancestor','ExpandedList':'Expand component drag rows'}


def enrich(v,gid,params):
    fields={p['name']:p for p in params if p['rawGroup']=='ParasiteDragProps'}
    for n,p in fields.items():
        if n in LABELS:p['label']=LABELS[n]
        if n in ('FFBodyEqnType','FFWingEqnType'):
            p['choices']=[dict(value=getattr(v,enum),label=label) for enum,label in (BODY if n=='FFBodyEqnType' else WING)]
    if 'IncorporatedGen' in fields:
        choices=[dict(value=0,label='Report separately')];parent=v.GetGeomParent(gid);seen={gid}
        while parent in v.FindGeoms() and parent not in seen:
            choices.append(dict(value=len(choices),label=v.GetGeomName(parent)+' · ancestor '+str(len(choices))))
            seen.add(parent);parent=v.GetGeomParent(parent)
        current=int(fields['IncorporatedGen']['value'])
        if current not in [c['value'] for c in choices]:choices.append(dict(value=current,label='Saved ancestor generation '+str(current)+' · review hierarchy'))
        fields['IncorporatedGen']['choices']=choices
    if not fields or not v.GetNumMainSurfs(gid):return []
    # Original ParasiteDragMgr uses GetSurfType(0) for component form factors.
    body=v.GetGeomVSPSurfType(gid,0)==v.NORMAL_SURF
    equation='FFBodyEqnType' if body else 'FFWingEqnType'
    primary=['PercLam',equation,'Q','IncorporatedGen']
    manual=v.FF_B_MANUAL if body else v.FF_W_MANUAL
    if fields.get(equation,{}).get('value')==manual:primary.insert(2,'FFUser')
    def group(title,names,note):return dict(title=title,parameters=[fields[n]['id'] for n in names if n in fields],note=note,open=False)
    return [group('Component parasite drag',primary,'Set the component’s laminar percentage, form-factor method and interference factor for Parasite drag buildup in Analyze. Select Manual to supply a form factor. Ancestor grouping combines wetted area in the native drag report.'),
            group('Drag roughness & temperature',['Roughness','TeTwRatio','TawTwRatio','ExpandedList'],'Roughness and temperature ratios are used by the chosen native skin-friction equation. Roughness uses the length convention configured for Parasite drag buildup; these values retain native units. Expanded rows controls native report detail.')]
