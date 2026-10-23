"""Retain custom package data in the native document and stage it before loading."""
import base64
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from native_section_file_validation import validate_profile_file

ATTRIBUTE='Studio.CustomAssets'
MISSING_ATTRIBUTE='Studio.MissingCustomAsset'
INVALID_ATTRIBUTE='Studio.InvalidCustomAsset'


def design_record_ids(path,fmt):
    """Check file records only; the original reader still applies every value."""
    import math
    try:
        text=path.read_text(encoding='utf-8')
        if len(text.encode())>5_000_000 or '<!DOCTYPE' in text.upper():raise ValueError()
        records=[]
        if fmt=='DES':
            rows=[line.strip() for line in text.splitlines() if line.strip()]
            count=int(rows[0])
            if not 0<=count<=10000 or len(rows)!=count+1:raise ValueError()
            for row in rows[1:]:
                label,separator,value=row.rpartition(':')
                if not separator:raise ValueError()
                records.append((label.split(':',1)[0],float(value)))
        else:
            root=ET.fromstring(text)
            if root.tag!='Model':raise ValueError()
            for node in root:
                if node.tag in ('Variable','Constant'):
                    records.append((node.attrib['VSPID'],float(node.attrib['Value'])))
            if len(records)>10000:raise ValueError()
        ids=[pid for pid,_ in records]
        if len(set(ids))!=len(ids) or any(not pid or not math.isfinite(value) or abs(value)>1e12 for pid,value in records):raise ValueError()
        return ids
    except (ValueError,IndexError,KeyError,UnicodeError,ET.ParseError):
        raise ValueError('Malformed custom '+fmt+' design file: '+path.name) from None


def stage(raw):
    from native_custom_scripts import unpack_package
    digest=hashlib.sha256(raw).hexdigest()
    folder=Path.cwd()/'.studio-custom-assets'/digest
    # Assets are confined to each isolated native job, never the original package.
    parent=folder.parent
    if parent.is_symlink() or folder.is_symlink():raise ValueError('Custom asset staging must use ordinary directories.')
    entry=unpack_package(raw,folder)
    for file in folder.rglob('*'):
        if file.is_file():validate_profile_file(file)
    return folder,entry,digest


def listing_context(entry,base,asset_root):
    import native_custom_listing
    return dict(root=(asset_root/entry.parent.relative_to(base)).relative_to(Path.cwd()).as_posix(),
                file_cases=native_custom_listing.cases(entry.parent,base,asset_root),
                directory_cases=native_custom_listing.cases(entry.parent,base,asset_root,directories=True))


def listing_calls(text):
    """Find real native listing calls after includes have been expanded."""
    from native_custom_file_reads import replacements
    tokens=[m for m in re.finditer(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[A-Za-z_]\w*|[^\s]',text,re.S) if not m[0].startswith(('//','/*'))]
    return any(replacement.startswith(('StudioListing_getFiles(', 'StudioListing_getDirs(')) for _,_,replacement in replacements(text,tokens,'StudioListing'))


def rewrite_reads(text,source,base,asset_root,runtime_entry=None):
    """Relocate packaged reader arguments while retaining native script evaluation."""
    # Tokenize comments separately so examples and labels cannot become edits.
    tokens=[m for m in re.finditer(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[A-Za-z_]\w*|[^\s]',text,re.S) if not m[0].startswith(('//','/*'))]
    replacements=[];dynamic=False;wrappers=set()
    helper='StudioPackageProfile_'+hashlib.sha256((str(asset_root)+str(source.relative_to(base))).encode()).hexdigest()[:16]
    from native_custom_file_reads import replacements as file_replacements
    file_reads=file_replacements(text,tokens,helper)
    for start,end,replacement in sorted(file_reads,reverse=True):text=text[:start]+replacement+text[end:]
    if file_reads:tokens=[m for m in re.finditer(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[A-Za-z_]\w*|[^\s]',text,re.S) if not m[0].startswith(('//','/*'))]
    dynamic=bool(file_reads)
    readers={'ReadFileAirfoil':1,'ReadFileXSec':1,'ReadBORFileAirfoil':1,'ReadBORFileXSec':1,'ReadAuxiliaryGeomCCEFile':1,'ReadAdvLinkCodeFile':1,'ReadApplyDESFile':0,'ReadApplyXDDMFile':0}
    for i,token in enumerate(tokens):
        if token[0] not in readers or i+1>=len(tokens) or tokens[i+1][0]!='(':continue
        kind='code' if token[0]=='ReadAdvLinkCodeFile' else 'profile'
        j=i+1
        if readers[token[0]]:
            depth=1;j=i+2
            while j<len(tokens):
                part=tokens[j][0]
                if part=='(':depth+=1
                elif part==')':depth-=1
                elif part==',' and depth==1:break
                if depth==0:break
                j+=1
        if j+2>=len(tokens) or tokens[j][0]!=(',' if readers[token[0]] else '('):continue
        if not tokens[j+1][0].startswith('"') or tokens[j+2][0]!=')':
            end=j+1;depth=1
            while end<len(tokens):
                if tokens[end][0]=='(':depth+=1
                elif tokens[end][0]==')':depth-=1
                if depth==0:break
                if tokens[end][0]==',' and depth==1:raise ValueError('Use the original native file-reader arguments.')
                end+=1
            if end==len(tokens):raise ValueError('Unclosed native file-profile call.')
            start=tokens[j+1].start();stop=tokens[end].start()
            if readers[token[0]]==0:
                wrappers.add(token[0])
                replacements.append((token.start(),tokens[end].end(),helper+'_'+token[0]+'('+text[start:stop]+')'))
            else:replacements.append((start,stop,helper+'('+text[start:stop]+')'))
            dynamic=True
            continue
        literal=tokens[j+1]
        try:filename=json.loads(literal[0])
        except ValueError:raise ValueError('Use a plain relative profile filename in the package.')
        relative=Path(filename)
        candidates={(source.parent/relative).resolve(),(base/relative).resolve()}
        candidates=[p for p in candidates if p.is_relative_to(base) and p.is_file()]
        # In a native directory workflow all included functions share the
        # entry script's working folder, independent of their source file.
        runtime_file=(runtime_entry.parent/relative).resolve() if runtime_entry else None
        if runtime_file is not None and runtime_file.is_relative_to(base) and runtime_file.is_file():candidates=[runtime_file]
        if len(candidates)!=1:raise ValueError('Choose an unambiguous in-package '+kind+' file: '+filename)
        destination=asset_root/candidates[0].relative_to(base)
        if readers[token[0]]==0:
            design_record_ids(candidates[0],'DES' if token[0]=='ReadApplyDESFile' else 'XDDM')
            wrappers.add(token[0]);dynamic=True
            replacements.append((token.start(),tokens[j+2].end(),helper+'_'+token[0]+'('+json.dumps(filename)+')'))
        else:replacements.append((literal.start(),literal.end(),json.dumps(destination.relative_to(Path.cwd()).as_posix())))
    for start,end,replacement in sorted(replacements,reverse=True):text=text[:start]+replacement+text[end:]
    if dynamic:
        cases=choice_cases(source,base,asset_root)
        listing=listing_context(runtime_entry,base,asset_root) if runtime_entry else None
        missing_path=asset_root/'.unavailable-profile'
        while (base/missing_path.relative_to(asset_root)).exists():missing_path=Path(str(missing_path)+'_')
        missing=missing_path.relative_to(Path.cwd()).as_posix()
        if file_reads or listing:
            # Preserve native writes and read-after-write behavior. Pure reads
            # prefer a bundled companion over untouched worker infrastructure;
            # other reads try the native filename before fallback. Evaluate once.
            from native_custom_file_reads import helper_code
            text+=helper_code(helper,cases,choice_cases(source,base,asset_root,directories=True),listing=listing)
        # Unknown computed names are recorded for rejection. Profile readers
        # retain their native diagnostic; unsafe design readers are skipped.
        runtime_profile=('string runtimePath='+helper+'_runtimeFilePath(filename);if(runtimePath!=filename)return runtimePath;\n') if listing else ''
        text+='\nstring '+helper+'(const string &in filename){\n'+runtime_profile+discovered_profile_cases(cases)+'string normalized=filename;\nwhile(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);\n'+cases+'AddAttributeString(GetChildCollection(GetCurrCustomGeom()),'+json.dumps(MISSING_ATTRIBUTE)+',filename);\nreturn '+json.dumps(missing)+';\n}\n'
        # These native void readers can crash on a missing file. Leave the
        # original reader untouched for resolved data, and skip unresolved
        # calls so the worker can reject the recorded failure before saving.
        for reader in sorted(wrappers):
            valid=[]
            for file in sorted(base.rglob('*')):
                if not file.is_file():continue
                try:ids=design_record_ids(file,'DES' if reader=='ReadApplyDESFile' else 'XDDM')
                except ValueError:continue
                target=(asset_root/file.relative_to(base)).relative_to(Path.cwd()).as_posix()
                check=' && '.join('ValidParm('+json.dumps(pid)+')' for pid in ids) or 'true'
                valid.append('if(path=='+json.dumps(target)+' && ('+check+')){'+reader+'(path);return;}')
            text+='\nvoid '+helper+'_'+reader+'(const string &in filename){string path='+helper+'(filename);if(path=='+json.dumps(missing)+')return;'+''.join(valid)+'AddAttributeString(GetChildCollection(GetCurrCustomGeom()),'+json.dumps(INVALID_ATTRIBUTE)+',filename);}\n'
    return text


def require_reads(v):
    """Catch unresolved computed reads even when a native reader clears errors."""
    for gid in v.FindGeoms():
        for aid in v.FindAttributesInCollection(v.GetChildCollection(gid)):
            if v.GetAttributeName(aid)==MISSING_ATTRIBUTE:
                names=v.GetAttributeStringVal(aid)
                raise ValueError('Missing or ambiguous custom package file: '+(names[0] if names else 'unknown filename'))
            if v.GetAttributeName(aid)==INVALID_ATTRIBUTE:
                names=v.GetAttributeStringVal(aid)
                raise ValueError('Malformed custom design file or unavailable parameter: '+(names[0] if names else 'unknown filename'))


def save(v,gid,raw):
    encoded=base64.b64encode(raw).decode('ascii')
    v.AddAttributeString(v.GetChildCollection(gid),ATTRIBUTE,encoded)


def restore(model):
    """Stage companions before native custom Init/Update runs during ReadVSPFile."""
    if Path(model).exists():_stage_tree(ET.parse(model))


def _stage_tree(tree):
    # Region workers and direct saved-model restoration also load scripts,
    # independently of the ordinary native worker's run entry point.
    import native_custom_listing
    native_custom_listing.begin()
    staged={}
    for node in tree.iter('Attribute'):
        if node.get('Name')!=ATTRIBUTE:continue
        encoded=node.get('StrData','')
        if len(encoded)>67_000_000:raise ValueError('Saved custom package exceeds 50 MB.')
        try:raw=base64.b64decode(encoded,validate=True)
        except ValueError:raise ValueError('Saved custom package data is invalid.')
        if not raw or len(raw)>50_000_000:raise ValueError('Saved custom package exceeds 50 MB.')
        staged[node]=stage(raw)
    return staged


def choice_cases(source,base,asset_root,directories=False):
    import os
    choices={}
    for file in ([base,*base.rglob('*')] if directories else base.rglob('*')):
        if not (file.is_dir() if directories else file.is_file()):continue
        target=(asset_root/file.relative_to(base)).relative_to(Path.cwd()).as_posix()
        for key in {file.relative_to(base).as_posix(),Path(os.path.relpath(file,source.parent)).as_posix()}:
            choices.setdefault(key,set()).add(target)
    return ''.join('if(normalized=='+json.dumps(key)+')return '+json.dumps(next(iter(paths)))+';\n' for key,paths in sorted(choices.items()) if len(paths)==1)


def discovered_profile_cases(cases,allowed=None):
    """Canonicalize exact native-discovered files, retaining design validation."""
    targets={json.loads(value) for value in re.findall(r'return ("(?:\\.|[^"\\])*");',cases)}
    if allowed is not None:targets.intersection_update(allowed)
    if not targets:return ''
    return ('filesystem studioProfileRoot;string studioProfileRootPath=studioProfileRoot.getCurrentPath()+"/";\n'+
            ''.join('if(filename=='+json.dumps(target)+' || filename==studioProfileRootPath+'+json.dumps(target)+')return '+json.dumps(target)+';\n' for target in sorted(targets)))


def upgrade_profile_resolver(body,allowed):
    """Recognize the previous generated resolver, preserving its source aliases."""
    quoted=r'"(?:\\.|[^"\\])*"'
    prefix='\nstring normalized=filename;\nwhile(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);\n'
    suffix='AddAttributeString(GetChildCollection(GetCurrCustomGeom()),'+json.dumps(MISSING_ATTRIBUTE)+',filename);\nreturn '
    match=re.fullmatch(re.escape(prefix)+'(?P<cases>(?:if\\(normalized=='+quoted+r'\)return '+quoted+r';\n)*)'+re.escape(suffix)+quoted+r';\n',body)
    return discovered_profile_cases(match['cases'],allowed) if match else ''


def generated_functions(text,tokens):
    """Identify individual reserved generated functions, including array handles."""
    functions=[]
    for i,token in enumerate(tokens):
        name=token[0]
        if not re.fullmatch(r'StudioPackage(?:Profile|Upgrade)_[0-9a-f]{16}(?:_[A-Za-z0-9_]+)?',name):continue
        if i+1>=len(tokens) or tokens[i+1][0]!='(':continue
        if i and tokens[i-1][0] in ('string','void','int','bool'):start=i-1
        elif i>=5 and [t[0] for t in tokens[i-5:i]]==['array','<','string','>','@']:start=i-5
        else:continue
        j=i+1;depth=0
        while j<len(tokens):
            if tokens[j][0]=='(':depth+=1
            elif tokens[j][0]==')':depth-=1
            j+=1
            if depth==0:break
        if j>=len(tokens) or tokens[j][0]!='{':continue
        k=j;depth=0
        while k<len(tokens):
            if tokens[k][0]=='{':depth+=1
            elif tokens[k][0]=='}':depth-=1
            k+=1
            if depth==0:break
        if depth:continue
        functions.append(dict(name=name,start=tokens[start].start(),end=tokens[k-1].end(),body_start=tokens[j].end(),body_end=tokens[k-1].start(),body=text[tokens[j].end():tokens[k-1].start()]))
    return functions


def upgrade_listing_helpers(functions,helper,allowed):
    """Upgrade only known generated bodies; keep their source-specific aliases."""
    from native_custom_file_reads import helper_code
    edits=[];quoted=r'"(?:\\.|[^"\\])*"'
    cases=r'(?:if\(normalized=='+quoted+r'\)return '+quoted+r';\n)*'
    normalize='string normalized=filename;while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);'
    trim='while(normalized.length()>1 && normalized.substr(normalized.length()-1)=="/")normalized=normalized.substr(0,normalized.length()-1);'
    for function in functions:
        name=function['name'];body=function['body'];replacement=None
        for suffix,kind,prefix in [('_filePath','File',normalize),('_directoryPath','Directory',normalize+trim)]:
            if name.endswith(suffix) and re.fullmatch(re.escape(prefix)+cases+re.escape('return filename;'),body):
                replacement='string listed='+helper+'_runtime'+kind+'Path(filename);if(listed!=filename)return listed;'+body
        if name.endswith(('_open','_changeCurrentPath')):
            owner=name.rsplit('_',1)[0]
            # Compare the complete old generated implementation, not a user's
            # similarly named wrapper. Reuse the generator for the new body.
            old=helper_code(owner,'','');new=helper_code(owner,'','',listing=dict(root='',file_cases='',directory_cases=''))
            pattern=r'\b'+re.escape(name)+r'\([^\n]*?\)\{(.*)\}\n'
            previous=re.search(pattern,old);updated=re.search(pattern,new)
            if previous and updated and body==previous[1]:
                replacement=updated[1]
                for suffix in ('_runtimeFilePath','_runtimeDirectoryPath','_recordWrite','_preferCompanion'):
                    replacement=replacement.replace(owner+suffix,helper+suffix)
        if re.fullmatch(r'StudioPackageProfile_[0-9a-f]{16}',name):
            core='string normalized=filename;\nwhile(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);\n'
            suffix='AddAttributeString(GetChildCollection(GetCurrCustomGeom()),'+json.dumps(MISSING_ATTRIBUTE)+',filename);\nreturn '
            match=re.search(re.escape(core)+'(?P<cases>'+cases+')'+re.escape(suffix)+quoted+r';\n\Z',body)
            if match and body[:match.start()] in ('\n','\n'+discovered_profile_cases(match['cases'],allowed)):
                if body[:match.start()]=='\n':body='\n'+discovered_profile_cases(match['cases'],allowed)+body[1:]
                replacement='\nstring runtimePath='+helper+'_runtimeFilePath(filename);if(runtimePath!=filename)return runtimePath;'+body
        if replacement is not None:edits.append((function['body_start'],function['body_end'],replacement))
    return edits


def prepare(v,model):
    """Upgrade embedded file receivers in an isolated native-load copy only."""
    import ctypes,native_preview
    model=Path(model);tree=ET.parse(model);staged=_stage_tree(tree)
    changed=False;candidates=[]
    for geom in tree.iter('Geom'):
        script=geom.find('CustomGeom/ScriptFileContents')
        if script is None or not script.text:continue
        assets=[a for a in geom.findall('ParmContainer/AttributeCollection/Attribute') if a.get('Name')==ATTRIBUTE]
        if assets:candidates.append((script,assets))
    if not candidates:return model
    _,engine,bridge=native_preview.adapter(v);convert=bridge.studio_script_xml_text
    convert.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_bool];convert.restype=ctypes.c_char_p
    def codec(text,decode):
        result=json.loads(convert(engine,text.encode(),decode))
        if isinstance(result,dict):raise ValueError(result.get('error','Native script XML conversion failed.'))
        return result
    from native_custom_file_reads import replacements as file_replacements,helper_code
    for script,assets in candidates:
        if len(assets)!=1:raise ValueError('Custom component has ambiguous embedded package records.')
        folder,entry,_=staged[assets[0]]
        text=codec(script.text,True)
        tokens=[m for m in re.finditer(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[A-Za-z_]\w*|[^\s]',text,re.S) if not m[0].startswith(('//','/*'))]
        # Includes can place generated helpers before later user callbacks.
        # Exclude individual helper bodies, not the remainder of the script.
        functions=generated_functions(text,tokens);resolver_edits=[]
        allowed={(file.relative_to(Path.cwd()).as_posix()) for file in folder.rglob('*') if file.is_file()}
        helper='StudioPackageUpgrade_'+hashlib.sha256(text.encode()).hexdigest()[:16]
        edits=[edit for edit in file_replacements(text,tokens,helper) if not any(f['start']<=edit[0]<f['end'] for f in functions)]
        listing=listing_context(entry,folder,folder) if any(edit[2].startswith((helper+'_getFiles(',helper+'_getDirs(')) for edit in edits) else None
        if listing:resolver_edits=upgrade_listing_helpers(functions,helper,allowed)
        else:
            for function in functions:
                if re.fullmatch(r'StudioPackageProfile_[0-9a-f]{16}',function['name']):
                    upgrade=upgrade_profile_resolver(function['body'],allowed)
                    if upgrade:resolver_edits.append((function['body_start'],function['body_start'],'\n'+upgrade))
        if not edits and not resolver_edits:continue
        for start,end,replacement in sorted(edits+resolver_edits,reverse=True):text=text[:start]+replacement+text[end:]
        if edits:text+=helper_code(helper,choice_cases(entry,folder,folder),choice_cases(entry,folder,folder,directories=True),listing=listing)
        script.text=codec(text,False);changed=True
    if not changed:return model
    import os,tempfile
    fd,filename=tempfile.mkstemp(prefix='.studio-custom-readable-',suffix='.vsp3',dir=Path.cwd()/'.studio-custom-assets')
    with os.fdopen(fd,'wb') as output:tree.write(output,encoding='utf-8',xml_declaration=True)
    return Path(filename)
