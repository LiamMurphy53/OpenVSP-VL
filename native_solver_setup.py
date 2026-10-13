"""Read the official solver's saved setup text; never reconstruct rotor math."""
from pathlib import Path
import re


def read(folder):
    folder=Path(folder);files=list(folder.glob('*.vspaero'))
    if len(files)!=1:return dict(available=False,note='The saved run has no unique native solver setup file.')
    source=files[0];lines=source.read_text().splitlines();fields=[];disks=[];planes=[]
    for i,line in enumerate(lines):
        match=re.fullmatch(r'([^=]+)\s*=\s*(.*)',line.strip())
        if match:fields.append(dict(name=match[1].strip(),value=match[2].strip()))
        if match and match[1].strip()=='NumberOfQuadTrees':
            count=match[2].strip()
            if not re.fullmatch(r'\d+',count):raise ValueError('The native cutting-plane count is invalid.')
            records=lines[i+1:i+1+int(count)]
            if len(records)!=int(count):raise ValueError('The native cutting-plane list is incomplete.')
            for record in records:
                parts=record.split()
                if len(parts)!=3 or not parts[0].isdigit() or parts[1] not in ('1','2','3'):
                    raise ValueError('The native cutting-plane record is invalid.')
                planes.append(dict(index=parts[0],axis=parts[1],position=parts[2]))
        if re.fullmatch(r'PropElement_\d+',line.strip()):
            block=lines[i+1:i+9]
            if len(block)!=8:raise ValueError('The native actuator-disk setup block is incomplete.')
            disks.append(dict(element=line.strip(),index=block[0].strip(),fields=[dict(name=name,value=value.strip()) for name,value in zip(('Center XYZ','Normal XYZ','Radius','Hub radius','Signed RPM','CT','CP'),block[1:])]))
    declared=next((f['value'] for f in fields if f['name']=='NumberOfRotors'),None)
    if declared is not None and (not re.fullmatch(r'\d+',declared) or int(declared)!=len(disks)):
        raise ValueError('The native actuator-disk count does not match its saved records.')
    groups=[];groupfile=source.with_suffix('.groups')
    if groupfile.is_file():
        lines=groupfile.read_text().splitlines()
        if not lines or not re.fullmatch(r'\d+',lines[0].strip()):raise ValueError('The native moving-group setup header is invalid.')
        expected=int(lines[0]);current=None;i=1
        while i<len(lines):
            line=lines[i].strip();i+=1
            if not line or line=='#':continue
            match=re.fullmatch(r'([^=]+)\s*=\s*(.*)',line)
            if not match:raise ValueError('The native moving-group setup field is invalid.')
            key,value=match[1].strip(),match[2].strip()
            if key=='GroupName':
                current=dict(name=value,fields=[],components=[]);groups.append(current)
            if current is None:raise ValueError('The native moving-group setup has no group name.')
            current['fields'].append(dict(name=key,value=value))
            if key=='NumberOfComponents':
                if not re.fullmatch(r'\d+',value):raise ValueError('The native component count is invalid.')
                count=int(value);current['components']=[x.strip() for x in lines[i:i+count]]
                if len(current['components'])!=count:raise ValueError('The native group component list is incomplete.')
                i+=count
        if len(groups)!=expected:raise ValueError('The native moving-group count does not match its saved records.')
    return dict(available=True,source=source.name,groupSource=groupfile.name if groupfile.is_file() else None,fields=fields,disks=disks,groups=groups,planes=planes,note='These are the exact fields written in this run’s native solver setup. Automatic time-step sentinels remain as written; actual times are in the native result histories. Group component numbers are native solver indices.')
