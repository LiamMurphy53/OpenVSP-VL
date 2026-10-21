"""Summaries of the installed engine's explicit CalculiX boundary records."""
from pathlib import Path


def read(path):
    path=Path(path);pairs=set();records=0;active=False
    with path.open() as stream:
        for number,line in enumerate(stream,1):
            text=line.strip()
            if not text or text.startswith('**'):continue
            if text.startswith('*'):
                active=text.split(',',1)[0].upper()=='*BOUNDARY'
                continue
            if not active:continue
            fields=text.split(',')
            try:
                if len(fields)!=2:raise ValueError()
                node,direction=map(int,fields)
                if node<1 or direction not in range(1,7):raise ValueError()
            except ValueError:
                return dict(available=False,sourceFile=path.name,reason=f'Boundary record format at line {number} is not supported by this summary. Inspect the original solver file.')
            records+=1;pairs.add((node,direction))
    return dict(available=True,sourceFile=path.name,nodeCount=len({n for n,d in pairs}),degreeCount=len(pairs),recordCount=records,directionCounts=[sum(d==i for n,d in pairs) for i in range(1,7)])


def report(v,members,formats,path):
    count=sum(len(v.GetFeaBCIDVec(s)) for s in members)
    if not count:return None
    if 'CALCULIX' not in formats:
        return dict(available=False,definedConditions=count,reason='Include the CalculiX export to inspect constrained-node counts.')
    result=read(path);result['definedConditions']=count
    return result
