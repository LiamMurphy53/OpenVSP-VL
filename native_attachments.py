"""Readable attachment references and native activity; no transform arithmetic."""
import native_preview

MODE_NAMES=(('NONE','None'),('COMP','Parent component axes'),('UV','Parent surface (U / W)'),
            ('RST','Section volume (R / S / T)'),('LMN','Uniform volume (L / M / N)'),('EtaMN','Wing span (eta / M / N)'))
FAMILIES=((2,'Surface coordinates',['U_01','U_Attach_Location','U_Attach_Location0N','V_Attach_Location']),
          (3,'Section volume coordinates',['R_01','R_Attach_Location','R_Attach_Location0N','S_Attach_Location','T_Attach_Location']),
          (4,'Uniform volume coordinates',['L_01','L_Attach_Location','L_Attach_Location0Len']),
          (5,'Wing span coordinate',['Eta_Attach_Location']),
          ((4,5),'Cross-volume coordinates',['M_Attach_Location','N_Attach_Location']))
LABELS={'U_01':'U coordinate basis','R_01':'R coordinate basis','L_01':'L coordinate basis',
        'U_Attach_Location':'U (fraction)','U_Attach_Location0N':'U (native section coordinate)','V_Attach_Location':'W (fraction)',
        'R_Attach_Location':'R (fraction)','R_Attach_Location0N':'R (native section coordinate)',
        'S_Attach_Location':'S (fraction)','T_Attach_Location':'T (fraction)',
        'L_Attach_Location':'L (fraction)','L_Attach_Location0Len':'L (distance along parent)',
        'M_Attach_Location':'M (fraction)','N_Attach_Location':'N (fraction)','Eta_Attach_Location':'Eta (wing span fraction)'}


def fields(v,gid):
    return [p for p in v.GetGeomParmIDs(gid) if v.GetParmGroupName(p) in ('XForm','Attach')]


def enrich(v,gid,params):
    ids=fields(v,gid);activity=native_preview.parameter_activity(v,ids);by_name={p['name']:p for p in params if p['rawGroup']=='Attach'}
    for p in params:
        if p['id'] in activity:
            p['active']=activity[p['id']]
            if not p['active']:p['readOnlyReason']='Calculated or locked by OpenVSP for the selected coordinate reference.'
    if not by_name:return None
    selected={int(by_name[n]['value']) for n in ('Trans_Attach_Flag','Rots_Attach_Flag')}
    groups=[]
    for mode,title,names in FAMILIES:
        enabled=bool(selected.intersection(mode if isinstance(mode,tuple) else [mode]))
        controls=[]
        for name in names:
            p=by_name.get(name)
            if not p:continue
            p['label']=LABELS[name]
            if not enabled:
                p['displayReadOnly']=True;p['readOnlyReason']='Select this attachment reference to edit these coordinates.'
            if name in ('U_01','R_01'):p['choices']=[[1,'Normalized fraction (0–1)'],[0,'Native section coordinate']]
            if name=='L_01':p['choices']=[[1,'Normalized fraction (0–1)'],[0,'Distance along parent']]
            if name=='L_Attach_Location0Len':p['dimension']='length'
            controls.append(p['id'])
        groups.append(dict(title=title,enabled=enabled,parameters=controls))
    for prefix,name,label in [('TRANS','Trans_Attach_Flag','Position attachment'),('ROT','Rots_Attach_Flag','Rotation attachment')]:
        by_name[name]['label']=label
        by_name[name]['choices']=[[getattr(v,'ATTACH_'+prefix+'_'+enum),label] for enum,label in MODE_NAMES]
    parent=v.GetGeomParent(gid);parent_exists=parent in v.FindGeoms();parent_type=v.GetGeomTypeName(parent).upper() if parent_exists else ''
    return dict(parent=parent,parentType=parent_type,parentHasSurface=parent_exists and v.GetNumMainSurfs(parent)>0,
                isJoint=parent_type=='HINGE',groups=groups,parameters=[by_name[name]['id'] for name in ('Trans_Attach_Flag','Rots_Attach_Flag')]+[pid for group in groups for pid in group['parameters']],
                frame=native_preview.attachment_frame(v,gid))


def read_only_reasons(v):
    result={}
    for gid in v.FindGeoms():
        ids=fields(v,gid)
        for pid,active in native_preview.parameter_activity(v,ids).items():
            if not active:result[pid]='Calculated or locked by OpenVSP for the saved coordinate reference.'
        attach={v.GetParmName(p):p for p in ids if v.GetParmGroupName(p)=='Attach'}
        if not attach:continue
        selected={int(v.GetParmVal(attach[n])) for n in ('Trans_Attach_Flag','Rots_Attach_Flag')}
        for mode,title,names in FAMILIES:
            if selected.intersection(mode if isinstance(mode,tuple) else [mode]):continue
            for name in names:
                if name in attach:result[attach[name]]='Select this attachment reference before editing its coordinates.'
    return result


def validate_parameter(v,pid):
    if v.GetParmGroupName(pid) not in ('XForm','Attach'):return
    reason=read_only_reasons(v).get(pid)
    if reason:raise ValueError(reason)
