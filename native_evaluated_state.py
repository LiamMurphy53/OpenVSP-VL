"""Validate lossless native evaluated-state companions and bind them to an ADB."""
import hashlib,json,math,os,re,tempfile
from pathlib import Path

MAGIC='STUDIO_EVALUATED_STATE_1'
MAX_BYTES=150_000_000
HASH=re.compile(r'[0-9a-f]{64}')


def regular(path,limit=None):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or limit is not None and path.stat().st_size>limit:
        raise ValueError('Native evaluated-state input is missing, linked, or exceeds its size limit: '+path.name)
    return path


def digest(path):
    with regular(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):
    path=regular(path,MAX_BYTES);records=[];previous=None;previous_instant=None
    try:
        with path.open(encoding='ascii') as stream:
            if stream.readline().rstrip('\n')!=MAGIC:raise ValueError('Invalid native evaluated-state header.')
            for line in stream:
                fields=line.split()
                if len(fields)!=6 or fields[0]!='R':raise ValueError('Invalid native evaluated-state record.')
                time,level,count,surfaces=map(int,fields[1:5]);instant=float.fromhex(fields[5])
                if not 0<=time<10000 or not 0<=level<=100 or not 0<surfaces<=count<=1_000_000 or not math.isfinite(instant) or instant<0:
                    raise ValueError('Invalid native evaluated-state dimensions or time.')
                if previous is None and time!=0 or previous is not None and time not in (0,previous+1):raise ValueError('Native evaluated-state time records are incomplete or out of order.')
                if time==0 and instant!=0 or time>0 and previous_instant is not None and instant<=previous_instant:raise ValueError('Native evaluated-state times do not follow their record order.')
                gamma=[]
                for _ in range(count):
                    value=stream.readline().strip()
                    if not re.fullmatch(r'[+-]?0x[0-9a-fA-F]+(?:\.[0-9a-fA-F]*)?p[+-]?\d+',value):raise ValueError('Native evaluated circulation is truncated, nonfinite, or malformed.')
                    number=float.fromhex(value)
                    if not math.isfinite(number):raise ValueError('Native evaluated circulation is nonfinite.')
                    gamma.append(number)
                records.append(dict(time=time,level=level,loops=count,surfaces=surfaces,currentTime=instant,gamma=gamma));previous=time;previous_instant=instant
                if len(records)>10000:raise ValueError('Too many native evaluated-state records.')
    except (UnicodeError,OverflowError) as error:raise ValueError('Invalid native evaluated-state encoding or number.') from error
    if not records:raise ValueError('Native evaluated-state companion is empty.')
    return records


def paths(database):
    database=regular(Path(database))
    if database.suffix!='.adb':raise ValueError('Choose an original native ADB database.')
    return database,database.with_suffix('.studio-state'),database.with_suffix('.studio-state.json'),Path(str(database)+'.cases')


def writer_metadata(writer):
    if not isinstance(writer,dict) or writer.get('engineSourceTag')!='OpenVSP_3.52.2':raise ValueError('Unsupported native evaluated-state writer.')
    for key in ['writerExecutableSha256','writerSourceSha256','writerPatchSha256']:
        if not isinstance(writer.get(key),str) or not HASH.fullmatch(writer[key]):raise ValueError('Native evaluated-state writer provenance is incomplete.')
    return {key:writer[key] for key in ['engineSourceTag','writerExecutableSha256','writerSourceSha256','writerPatchSha256']}


def seal(database,writer):
    from aero_io import case_list
    database,state,manifest,cases=paths(database);writer=writer_metadata(writer)
    hashes={p.name:digest(p) for p in [database,regular(state,MAX_BYTES),regular(cases,10_000_000)]}
    records=read(state)
    if len(records)!=len(case_list(database)):raise ValueError('Native evaluated-state records do not match the saved database case list.')
    if any(digest(p)!=hashes[p.name] for p in [database,state,cases]):raise ValueError('Native evaluated-state inputs changed during validation.')
    data=dict(format=1,files=hashes,recordCount=len(records),writer=writer)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=manifest.parent,prefix=manifest.name+'.',delete=False) as stream:
            temporary=Path(stream.name);json.dump(data,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        temporary.replace(manifest)
    finally:
        if temporary and temporary.exists():temporary.unlink()
    return data


def validate(database):
    from aero_io import case_list
    database,state,manifest,cases=paths(database)
    if not state.exists() and not state.is_symlink() and not manifest.exists() and not manifest.is_symlink():return None
    try:
        regular(manifest,65536);data=json.loads(manifest.read_text());writer_metadata(data['writer'])
        if type(data['format']) is not int or data['format']!=1 or type(data['recordCount']) is not int:raise ValueError('Unsupported native evaluated-state binding.')
        expected={p.name:digest(regular(p,MAX_BYTES if p==state else 10_000_000 if p==cases else None)) for p in [database,state,cases]}
        if data['files']!=expected:raise ValueError('Native evaluated-state binding does not match this database, case list, or companion.')
        records=read(state)
        if len(records)!=data['recordCount'] or len(records)!=len(case_list(database)):raise ValueError('Native evaluated-state record count changed.')
        if any(digest(p)!=expected[p.name] for p in [database,state,cases]):raise ValueError('Native evaluated-state inputs changed during validation.')
        return dict(binding=data,records=records)
    except (KeyError,TypeError,json.JSONDecodeError) as error:raise ValueError('Invalid native evaluated-state binding.') from error
