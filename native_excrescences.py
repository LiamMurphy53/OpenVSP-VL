"""Saved native parasite-drag allowance records and original SDK operations."""
import native_managers
import os
from native_tools import finite,name,one
import native_references

TYPES=[('EXCRESCENCE_COUNT','Drag counts (10000 × CD)'),('EXCRESCENCE_CD','Drag coefficient CD'),('EXCRESCENCE_PERCENT_GEOM','Percent of geometry CD'),('EXCRESCENCE_MARGIN','Margin (% of total CD)'),('EXCRESCENCE_DRAGAREA','Drag area (D/q)')]


def choices(v):return [dict(value=n,label=l,nativeValue=getattr(v,n)) for n,l in TYPES]


def read(v):
    path,tree=native_references.document(v)
    try:
        node=tree.find('.//ParasiteDragMgr/Excrescence');out=[]
        if node is not None:
            for i in range(int(node.findtext('NumExcres','0'))):
                row=node.find('Excres_'+str(i));typ=int(row.findtext('Type'));key,label=next(((n,l) for n,l in TYPES if getattr(v,n)==typ),(None,'Unavailable native type'))
                out.append(dict(index=i,name=row.findtext('Label',''),type=key,typeLabel=label,value=float(row.findtext('Input'))))
        return out
    finally:path.unlink(missing_ok=True)


def value(v,x):
    x=finite(x);pid=v.FindParm(native_managers.manager(v,'ParasiteDragSettings'),'ExcresVal','ParasiteDrag')
    low,high=v.GetParmLowerLimit(pid),v.GetParmUpperLimit(pid)
    if not low<=x<=high:raise ValueError(f'Allowance value must be within the current native limits {low}–{high}.')
    return x


def mutate(v,r):
    op=r['operation']
    if op=='excrescence-add':
        typ=one(r.get('type'),[n for n,_ in TYPES]);rows=read(v)
        if typ=='EXCRESCENCE_MARGIN' and any(x['type']==typ for x in rows):raise ValueError('OpenVSP permits only one saved margin allowance.')
        v.AddExcrescence(name(r['name']),getattr(v,typ),value(v,r['value']))
        if v.GetNumExcrescences()!=len(rows)+1:raise ValueError('OpenVSP did not add this allowance.')
    elif op=='excrescence-delete':v.DeleteExcrescence(one(r['index'],range(v.GetNumExcrescences())))
    elif op=='excrescence-clear':v.DeleteAllExcrescences()
    elif op=='excrescence-update':
        index=one(r.get('index'),range(v.GetNumExcrescences()));label=name(r['name']);x=value(v,r['value']);filename=v.GetVSPFileName();path,tree=native_references.document(v)
        try:
            row=tree.find(f'.//ParasiteDragMgr/Excrescence/Excres_{index}')
            if row is None:raise ValueError('The saved allowance is unavailable.')
            row.find('Label').text=label;row.find('Input').text=format(x,'.17g')
            tree.write(path,encoding='utf-8',xml_declaration=True);os.replace(path,filename)
        finally:path.unlink(missing_ok=True)
        raise native_references.ReloadRequired()
    else:raise ValueError('Unknown drag-allowance operation.')
    return True,None
