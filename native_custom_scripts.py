"""Import custom components using the original OpenVSP script compiler."""
import ctypes,json
from pathlib import Path
import native_preview

def import_script(v,path,name,parent="",package_root=None,asset_root=None):
    path=Path(path).resolve()
    if not path.is_file():raise ValueError('Choose an existing custom component script.')
    import re
    base=Path(package_root).resolve() if package_root else path.parent
    visited=set();active=set();ordered=[]
    def check_includes(current,depth=0):
        if depth>32:raise ValueError('Custom script includes exceed 32 levels.')
        if current in active:raise ValueError('Custom script helpers contain an include cycle.')
        if current in visited:return
        active.add(current)
        try:text=current.read_text(encoding='utf-8')
        except UnicodeDecodeError:raise ValueError('Custom component scripts and helpers must be UTF-8 text.')
        for include in re.findall(r'#include\s*"([^"]+)"',text):
            target=(current.parent/include).resolve()
            if not target.is_relative_to(base) or not target.is_file():raise ValueError('Missing or out-of-package helper script: '+include)
            check_includes(target,depth+1)
        active.remove(current);visited.add(current);ordered.append(current)
        if len(visited)>200:raise ValueError('Use at most 200 custom script helper files.')
    check_includes(path)
    _,engine,bridge=native_preview.adapter(v)
    f=bridge.studio_custom_script_import
    f.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p];f.restype=ctypes.c_char_p
    if len(ordered)>1 or asset_root is not None:
        import tempfile
        expand=bridge.studio_custom_script_expand
        expand.argtypes=[ctypes.c_char_p,ctypes.c_char_p];expand.restype=ctypes.c_char_p
        with tempfile.TemporaryDirectory() as temporary:
            staged=Path(temporary)
            for source in ordered:
                destination=staged/source.relative_to(base)
                destination.parent.mkdir(parents=True,exist_ok=True)
                text=source.read_text(encoding='utf-8')
                if asset_root is not None:
                    from native_custom_assets import rewrite_reads
                    text=rewrite_reads(text,source,base,asset_root)
                destination.write_text(text,encoding='utf-8')
                expanded=json.loads(expand(engine,str(destination).encode()))
                if isinstance(expanded,dict):raise ValueError(expanded.get('error','Native include expansion failed.'))
                # Original ReplaceIncludes retains a commented #include line.
                # Rename that generated comment so a later native expansion
                # or EncodeXml cannot interpret it as a new include directive.
                expanded=re.sub(r'(?m)^//#include([^\n]*)$',r'// Included helper\1',expanded)
                if len(expanded.encode('utf-8'))>20_000_000:raise ValueError('Expanded custom script exceeds 20 MB.')
                destination.write_text(expanded,encoding='utf-8')
            result=json.loads(f(engine,str(staged/path.relative_to(base)).encode(),name.encode(),parent.encode()))
    else:
        result=json.loads(f(engine,str(path).encode(),name.encode(),parent.encode()))
    if isinstance(result,dict):raise ValueError(result.get('error','Custom script import failed.'))
    import native_custom_assets
    native_custom_assets.require_reads(v)
    v.Update()
    if result not in v.FindGeoms():raise ValueError('The custom component was not created.')
    return result


def unpack_package(raw,folder):
    """Stage one entry script and its companions without escaping the job."""
    import io,zipfile,stat
    from pathlib import PurePosixPath
    try:archive=zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:raise ValueError('Choose a valid custom component ZIP package.')
    entries=archive.infolist()
    if not entries or len(entries)>200:raise ValueError('Use a package with 1 to 200 entries.')
    if sum(i.file_size for i in entries)>20_000_000:raise ValueError('The unpacked component package must be smaller than 20 MB.')
    seen=set();scripts=[]
    for entry in entries:
        path=PurePosixPath(entry.filename)
        if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename or not path.parts:
            raise ValueError('Package files must have relative paths within the package.')
        key=str(path).casefold()
        if key in seen:raise ValueError('Package file paths must be unique.')
        seen.add(key)
        if stat.S_ISLNK(entry.external_attr>>16):raise ValueError('Package symbolic links are not supported.')
        if entry.flag_bits&1:raise ValueError('Encrypted packages are not supported.')
        if entry.file_size>5_000_000:raise ValueError('Each component package file must be smaller than 5 MB.')
        if not entry.is_dir() and path.suffix.lower()=='.vsppart':scripts.append(path)
    if len(scripts)!=1:raise ValueError('Include exactly one .vsppart entry script in the package.')
    folder=Path(folder)
    for entry in entries:
        target=folder/entry.filename
        if entry.is_dir():target.mkdir(parents=True,exist_ok=True)
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            try:target.write_bytes(archive.read(entry))
            except (zipfile.BadZipFile,RuntimeError):raise ValueError('The component package could not be unpacked.')
    return folder/str(scripts[0])


def gui_definitions(v,gid):
    _,engine,bridge=native_preview.adapter(v)
    f=bridge.studio_custom_gui_definitions
    f.argtypes=[ctypes.c_char_p,ctypes.c_char_p];f.restype=ctypes.c_char_p
    result=json.loads(f(engine,gid.encode()))
    if isinstance(result,dict):raise ValueError(result.get('error','Custom controls unavailable.'))
    return result


def surface_topology(v,gid):
    _,engine,bridge=native_preview.adapter(v)
    f=bridge.studio_surface_topology
    f.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];f.restype=ctypes.c_char_p
    result=json.loads(f(engine,gid.encode(),v.GetNumMainSurfs(gid)))
    if isinstance(result,dict):raise ValueError(result.get('error','Native surface validation unavailable.'))
    return result


def gui_updates(v,gid):
    from native_worker import errors
    from collections import Counter
    errors(v)
    definitions=gui_definitions(v,gid)
    _,engine,bridge=native_preview.adapter(v)
    f=bridge.studio_custom_gui_updates
    f.argtypes=[ctypes.c_char_p,ctypes.c_char_p];f.restype=ctypes.c_char_p
    result=json.loads(f(engine,gid.encode()))
    if isinstance(result,dict):raise ValueError(result.get('error','Custom control bindings unavailable.'))
    by_index={d['index']:d for d in definitions}
    expected=Counter();previous={}
    for update in result:
        index=update['index'];pid=update['parameterId']
        if pid:previous[index]=pid
        else:
            group=by_index.get(index,{}).get('group','')
            if not group and previous.get(index) and v.ValidParm(previous[index]):group=v.GetParmGroupName(previous[index])
            if group:expected['FindParm::Can\'t Find Parm  '+group]+=1
    manager=v.ErrorMgrSingleton.getInstance();unexpected=[]
    while manager.GetNumTotalErrors():
        error=manager.PopLastError();message=error.m_ErrorString
        if expected[message]>0:expected[message]-=1
        else:unexpected.append(message)
    if unexpected:raise ValueError('; '.join(unexpected))
    return result


def actions(v,gid):
    definitions=gui_definitions(v,gid)
    bindings={u['index']:u['parameterId'] for u in gui_updates(v,gid)}
    return [dict(index=d['index'],label=d['label'] or 'Run action') for d in definitions if d['type']==v.GDEV_TRIGGER_BUTTON and not bindings.get(d['index'])]


def trigger(v,gid,index):
    if type(index)!=int or index not in {a['index'] for a in actions(v,gid)}:raise ValueError('Choose an available custom component action.')
    _,engine,bridge=native_preview.adapter(v)
    f=bridge.studio_custom_gui_trigger
    f.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];f.restype=ctypes.c_char_p
    result=json.loads(f(engine,gid.encode(),index))
    if isinstance(result,dict):raise ValueError(result.get('error','Custom component action failed.'))
    gui_updates(v,gid)
    v.Update()


def index_step(v,gid,index,delta):
    """Mirror IndexSelector's GUI integer stepping; geometry stays native."""
    import math,native_custom_library
    from native_preview import parameter_activity
    if type(index)!=int or type(delta)!=int or delta not in (-10,-1,1,10):raise ValueError('Choose an index step of −10, −1, +1 or +10.')
    definition=next((d for d in gui_definitions(v,gid) if d['index']==index and d['type']==v.GDEV_INDEX_SELECTOR),None)
    if definition is None:raise ValueError('Choose an available custom index selector.')
    bindings={u['index']:u['parameterId'] for u in gui_updates(v,gid)}
    pid=bindings.get(index) if index in bindings else next((p for p in v.GetGeomParmIDs(gid) if v.GetParmName(p)==definition['parameter'] and v.GetParmGroupName(p)==definition['group']),None)
    if not pid or not v.ValidParm(pid):raise ValueError('This custom index selector is disconnected.')
    native_custom_library.validate(v,pid)
    if not parameter_activity(v,[pid])[pid]:raise ValueError('This index parameter is locked by OpenVSP.')
    values=[v.GetParmLowerLimit(pid),v.GetParmUpperLimit(pid),v.GetParmVal(pid)]
    if any(not math.isfinite(x) or not -2147483648<=x+.5<=2147483647 for x in values):raise ValueError('Index selector limits exceed the native integer range. Edit the parameter field instead.')
    lower,upper,current=[math.trunc(x+.5) for x in values]
    # Original IndexSelector::SetValAndLimits, DeviceCB and SetIndex.
    value=max(lower,min(upper,max(lower,min(upper,current))+delta))
    v.SetParmValUpdate(pid,value);gui_updates(v,gid);v.Update()
