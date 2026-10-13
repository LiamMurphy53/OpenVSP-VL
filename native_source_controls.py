"""Name original CFD source coordinates without replacing source geometry."""
LABELS={'SrcLen':'Target edge length (model units)','SrcRad':'Influence radius (model units)','SrcLen2':'Second target edge length (model units)','SrcRad2':'Second influence radius (model units)','MainSurfIndx':'Parent surface','U_Loc':'Point U (0–1)','W_Loc':'Point W (0–1)','U_Loc1':'First point U (0–1)','W_Loc1':'First point W (0–1)','U_Loc2':'Second point U (0–1)','W_Loc2':'Second point W (0–1)'}
NAMES={'POINT_SOURCE':'Point','LINE_SOURCE':'Line','BOX_SOURCE':'Box','ULINE_SOURCE':'Constant U line','WLINE_SOURCE':'Constant W line'}


def enrich(v,g,typ,fields):
    for p in fields:
        if p['name'] in LABELS:p['label']=LABELS[p['name']]
        if p['name']=='MainSurfIndx':p['choices']=[dict(value=i,label=f'Surface {i}') for i in range(v.GetNumMainSurfs(g))]
        if p['name']=='Val':p['label']='Constant '+('U' if typ==v.ULINE_SOURCE else 'W')+' (0–1)'
    return next(label for name,label in NAMES.items() if getattr(v,name)==typ)


def creation_fields(typ):
    common=['length','radius']
    return common+({'POINT_SOURCE':['u','w'],'LINE_SOURCE':['u','w','length2','radius2','u2','w2'],'BOX_SOURCE':['u','w','u2','w2'],'ULINE_SOURCE':['u'],'WLINE_SOURCE':['w']}[typ])
