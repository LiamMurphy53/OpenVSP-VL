"""Saved native VSPAERO cutting planes; all geometry and slicing stay native."""
from native_tools import finite, name, one


def ids(v):
    return [v.GetCpSliceID(i) for i in range(v.GetNumCpSlices())]


def snapshot(v, parameter):
    choices=[dict(value=getattr(v,n),label=l) for n,l in [('X_DIR','X · longitudinal'),('Y_DIR','Y · spanwise'),('Z_DIR','Z · vertical')]]
    planes=[]
    for cid in ids(v):
        ps=[parameter(v,p) for p in v.FindContainerParmIDs(cid)]
        for p in ps:
            if p['name']=='CutType':p.update(label='Plane normal',choices=choices)
            elif p['name']=='CutPosition':p['label']='Position (native model units)'
            elif p['name']=='DrawCutFlag':p['label']='Show native cutting plane'
        planes.append(dict(id=cid,name=v.GetContainerName(cid),params=ps))
    cid=v.FindContainer('VSPAEROSettings',0)
    settings=[parameter(v,v.FindParm(cid,n,'VSPAERO')) for n in ['CpSliceFlag','QuadTreeBufferLevels']]
    settings[0]['label']='Calculate pressure slices with VSPAERO'
    settings[1]['label']='Flow-plane buffer levels'
    return dict(flowPlanes=planes,flowPlaneAxes=choices,flowPlaneSettings=settings)


def mutate(v,r):
    op=r['operation']
    if op=='flow-plane-series':
        axis=int(one(finite(r.get('axis')),[v.X_DIR,v.Y_DIR,v.Z_DIR],'Choose X, Y or Z as the plane normal.'))
        count=r.get('count')
        if type(count)!=int or not 2<=count<=100:raise ValueError('Choose 2–100 cutting planes.')
        start,end=finite(r.get('start')),finite(r.get('end'));label=name(r.get('name','Cut'))
        if not -1e12<=start<=1e12 or not -1e12<=end<=1e12:raise ValueError('Position is outside OpenVSP’s cutting-plane limits.')
        if start==end:raise ValueError('Choose different start and end positions.')
        labels=[name(label+' '+str(i+1)) for i in range(count)]
        positions=[start if i==0 else end if i==count-1 else start+(end-start)*i/(count-1) for i in range(count)]
        if len(set(positions))!=count:raise ValueError('These positions are too close to distinguish. Use fewer planes or a wider range.')
        for title,position in zip(labels,positions):
            cid=v.AddCpSlice(axis,position)
            if not cid:raise ValueError('OpenVSP did not create the cutting plane.')
            v.SetContainerName(cid,title)
    elif op=='flow-plane-add':
        axis=int(one(finite(r.get('axis')),[v.X_DIR,v.Y_DIR,v.Z_DIR],'Choose X, Y or Z as the plane normal.'))
        position=finite(r.get('position'));label=name(r.get('name','Pressure slice'))
        # Native limits must be checked before AddCpSlice can clamp them.
        if not -1e12<=position<=1e12:raise ValueError('Position is outside OpenVSP’s cutting-plane limits.')
        cid=v.AddCpSlice(axis,position)
        if not cid:raise ValueError('OpenVSP did not create the cutting plane.')
        v.SetContainerName(cid,label)
    elif op=='flow-plane-delete':
        current=ids(v);cid=one(r.get('id'),current)
        v.DelCpSlice(current.index(cid))
    else:raise ValueError('Unknown cutting-plane operation.')
    v.Update()
    return True,None
