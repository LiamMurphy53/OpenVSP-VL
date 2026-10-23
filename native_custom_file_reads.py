"""Resolve native file and directory receivers before relocating reads."""
import re


FILESYSTEM_METHODS=(
    "changeCurrentPath","getCurrentPath","getFiles","getDirs",
    "getSize","isDir","isLink","getCreateDateTime","getModifyDateTime",
    "makeDir","removeDir","deleteFile","copyFile","move",
)


def replacements(text,tokens,helper):
    words=[t[0] for t in tokens];count=len(words)
    primitives={'file','filesystem','int','int64','uint','uint64','double','float','bool','string','auto','array'}
    pairs={}
    # Balance call, index and block scopes independently of comparison operators.
    for opening,closing in [('(',')'),('[',']'),('{','}')]:
        pending=[]
        for i,w in enumerate(words):
            if w==opening:pending.append(i)
            elif w==closing and pending:j=pending.pop();pairs[i]=j;pairs[j]=i
    namespace_blocks={};namespace_at=[];namespace='';blocks=[]
    for i,word in enumerate(words):
        namespace_at.append(namespace)
        if word=='namespace':
            j=i+1;parts=[]
            while j<count and words[j] not in ('{',';'):
                if words[j]!=':':parts.append(words[j])
                j+=1
            if j<count and words[j]=='{':namespace_blocks[j]='::'.join(filter(None,[namespace,*parts]))
        if word=='{':
            blocks.append(namespace)
            namespace=namespace_blocks.get(i,namespace)
        elif word=='}' and blocks:namespace=blocks.pop()
    def qualified(i,end):
        if i>=end:return None
        absolute=words[i:i+2]==[':',':']
        j=i+2 if absolute else i
        if j>=end or not re.fullmatch(r'[A-Za-z_]\w*',words[j]):return None
        parts=[words[j]];j+=1
        while j+2<end and words[j:j+2]==[':',':'] and re.fullmatch(r'[A-Za-z_]\w*',words[j+2]):
            parts.append(words[j+2]);j+=3
        return ('::' if absolute else '')+'::'.join(parts),j
    def names(name,index):
        if name.startswith('::'):return [name[2:]]
        namespace=namespace_at[index];result=[]
        while namespace:
            result.append(namespace+'::'+name);namespace=namespace.rpartition('::')[0]
        return result+[name]
    classes={('::'.join(filter(None,[namespace_at[i],words[i+1]]))) for i,w in enumerate(words[:-1]) if w in ('class','interface','enum')}
    def type_at(i,end):
        name=qualified(i,end)
        if not name:return None
        raw,j=name
        kind=next((name for name in names(raw,i) if name in classes),None)
        if kind is None:
            if raw.lstrip(':') not in primitives:return None
            kind=raw.lstrip(':')
        if kind=='array':
            if j>=end or words[j]!='<':return None
            inner=type_at(j+1,end)
            if not inner:return None
            nested,k=inner
            if k>=end or words[k]!='>':return None
            kind='array:'+nested;j=k+1
        while j<end and words[j] in ('@','&','in','out','inout','const'):j+=1
        return kind,j
    def declaration(i,end):
        # Do not rescan the :: suffix of a qualified type as an absolute native
        # type (Other::filesystem must never become ::filesystem). Genuine
        # leading :: declarations, including const ::file, remain available.
        if i and (words[i-1]==':' or words[i]==':' and re.fullmatch(r'[A-Za-z_]\w*',words[i-1]) and words[i-1]!='const'):return None
        parsed=type_at(i,end)
        if parsed:
            kind,j=parsed
            if j<end and re.fullmatch(r'[A-Za-z_]\w*',words[j]):return words[j],kind,j
    class_blocks={};bases={}
    for i,w in enumerate(words[:-1]):
        if w in ('class','interface'):
            j=i+2
            while j<count and words[j] not in ('{',';'):j+=1
            if j<count and words[j]=='{':
                owner='::'.join(filter(None,[namespace_at[i],words[i+1]]));class_blocks[j]=owner
                bases[owner]=[];k=i+3
                while k<j:
                    base=type_at(k,j)
                    if base:bases[owner].append(base[0]);k=base[1]
                    else:k+=1
    global_fields={};namespace_fields={'':global_fields};scopes=[(None,global_fields)];parens=[];fields={};functions={};methods={};calls=[]
    keywords={'if','for','while','switch','catch','return'}
    for i,word in enumerate(words):
        if word=='(':
            parens.append(i);continue
        if word==')':
            if parens:parens.pop()
            continue
        if word=='{':
            owner=class_blocks.get(i);bindings=namespace_fields.setdefault(namespace_blocks[i],{}) if i in namespace_blocks else {}
            if i and words[i-1]==')':
                j=pairs.get(i-1,-1)
                if j>0 and words[j-1] not in keywords:
                    for k in range(j+1,i-1):
                        decl=declaration(k,i-1) if not (k and words[k-1]==':') else None
                        if decl:bindings[decl[0]]=decl[1]
            scopes.append((owner,bindings));continue
        if word=='}':
            if len(scopes)>1:scopes.pop()
            continue
        if not parens:
            decl=declaration(i,count) if not (i and words[i-1]==':') else None
            if decl:
                name,kind,j=decl;owner,bindings=scopes[-1]
                at_namespace=any(bindings is values for values in namespace_fields.values())
                call_style=j+1<count and words[j+1]=='('
                closing=pairs.get(j+1,-1) if call_style else -1
                first=j+2
                while first<count and words[first]=='const':first+=1
                parameter_type=type_at(first,closing) if closing>=0 else None
                function=call_style and (closing+1<count and words[closing+1]=='{' or (at_namespace or owner) and (first==closing or parameter_type is not None))
                if function:
                    if at_namespace:functions['::'.join(filter(None,[namespace_at[i],name]))]=kind
                    elif owner:methods.setdefault(owner,{})[name]=kind
                else:
                    if kind=='auto' and j+2<count and words[j+1]=='=':
                        end=j+2;depth=0
                        while end<count:
                            w=words[end]
                            if depth==0 and w in (';',','):break
                            if w in ('(','['):depth+=1
                            elif w in (')',']'):depth-=1
                            end+=1
                        kind=('auto',j+2,end-1,[(c,dict(s)) for c,s in scopes])
                    bindings[name]=kind
                    if owner:fields.setdefault(owner,{})[name]=kind
                    # A native declaration may introduce several handles. Skip
                    # initializer expressions so their commas are not names.
                    if not isinstance(kind,tuple):
                        k=j+1
                        while k<count and words[k]!=';':
                            if words[k] in ('(','[','{') and k in pairs:k=pairs[k]
                            elif words[k]==',':
                                n=k+1
                                while n<count and words[n]=='@':n+=1
                                if n<count and re.fullmatch(r'[A-Za-z_]\w*',words[n]):
                                    bindings[words[n]]=kind
                                    if owner:fields.setdefault(owner,{})[words[n]]=kind
                            k+=1
        if word in ('open',*FILESYSTEM_METHODS) and i>=2 and i+1<count and words[i-1]=='.' and words[i+1]=='(':
            end=pairs.get(i+1)
            if end is not None:calls.append((i,end,[(c,dict(s)) for c,s in scopes]))
    def bounds(end):
        if end<0:return None
        if words[end] in (')',']'):
            start=pairs.get(end)
            if start is None:return None
            before=start-1
            if before>=0 and (words[end]==']' or re.fullmatch(r'[A-Za-z_]\w*',words[before]) and words[before] not in keywords):return bounds(before)
            return start
        if not re.fullmatch(r'[A-Za-z_]\w*',words[end]):return None
        if end>=2 and words[end-1]=='.':return bounds(end-2)
        if end>=2 and words[end-2:end]==[':',':']:
            before=bounds(end-3)
            return before if before is not None else end-2
        return end
    def member(table,owner,name,visited=()):
        if owner in visited:return None
        own=table.get(owner,{})
        if name in own:return own[name]
        inherited=[member(table,base,name,visited+(owner,)) for base in bases.get(owner,[])]
        inherited=[kind for kind in inherited if kind is not None]
        return inherited[0] if len(inherited)==1 else None

    def resolve(start,end,context,depth=0):
        if depth>20 or start is None or start>end:return None
        def inferred(kind):
            return resolve(kind[1],kind[2],kind[3],depth+1) if isinstance(kind,tuple) else kind
        if words[end] in (')',']'):
            opening=pairs.get(end)
            if opening is None:return None
            if words[end]==']':
                kind=resolve(start,opening-1,context,depth+1)
                return kind[6:] if isinstance(kind,str) and kind.startswith('array:') else None
            if opening==start:return resolve(start+1,end-1,context,depth+1)
            function=words[opening-1]
            constructor=type_at(start,opening)
            if constructor and constructor[1]==opening:return constructor[0]
            qualified_function=qualified(start,opening)
            if qualified_function and qualified_function[1]==opening:
                owner=next((c for c,_ in reversed(context) if c),None)
                kind=member(methods,owner,function) if opening-1==start else None
                return kind if kind is not None else next((functions[n] for n in names(qualified_function[0],start) if n in functions),None)
            if opening>=2 and words[opening-2]=='.':
                owner=resolve(start,opening-3,context,depth+1)
                return member(methods,owner,function)
            return None
        explicit=qualified(start,end+1)
        if explicit and explicit[1]==end+1 and start!=end:
            for name in names(explicit[0],start):
                namespace,_,field=name.rpartition('::')
                if field in namespace_fields.get(namespace,{}):return inferred(namespace_fields[namespace][field])
            return None
        name=words[end]
        if start==end:
            if name=='this':return next((c for c,_ in reversed(context) if c),None)
            kind=None
            for candidate in names(name,start):
                namespace,_,field=candidate.rpartition('::')
                if field in namespace_fields.get(namespace,{}):kind=namespace_fields[namespace][field];break
            for owner,bindings in reversed(context[1:]):
                if name in bindings:kind=bindings[name];break
                inherited=member(fields,owner,name) if owner else None
                if inherited is not None:kind=inherited;break
            return inferred(kind)
        if end>=2 and words[end-1]=='.':
            owner=resolve(start,end-2,context,depth+1)
            return inferred(member(fields,owner,name))
    result=[]
    for i,end,context in calls:
        start=bounds(i-2)
        method=words[i];kind='file' if method=='open' else 'filesystem'
        if resolve(start,i-2,context)!=kind:continue
        commas=0;j=i+2
        while j<end:
            if words[j]==',':commas+=1
            if words[j] in ('(','[') and j in pairs:j=pairs[j]
            j+=1
        empty=end==i+2
        if commas!=(1 if method in ('open','copyFile','move') else 0) or empty!=(method in ('getFiles','getDirs','getCurrentPath')):continue
        receiver=text[tokens[start].start():tokens[i-1].start()]
        result.append((tokens[start].start(),tokens[i+1].end(),helper+'_'+method+'(@('+receiver+')'+('' if empty else ',')))
    return result


def _legacy_helper_code(helper,cases,directory_cases=''):
    # Preserve the established open-only fallback and its exact migration body.
    text=('\nstring '+helper+'_filePath(const string &in filename){'+'string normalized=filename;while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);'+cases+'return filename;}\n'
            '\nint '+helper+'_open(file@ target,const string &in filename,const string &in mode){'+'int status=target.open(filename,mode);'+'if(status!=0 && (mode=="r" || mode=="rb")){string path='+helper+'_filePath(filename);if(path!=filename)return target.open(path,mode);}return status;}\n'
            '\nstring '+helper+'_directoryPath(const string &in filename){'+'string normalized=filename;while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);while(normalized.length()>1 && normalized.substr(normalized.length()-1)=="/")normalized=normalized.substr(0,normalized.length()-1);'+directory_cases+'return filename;}\n'
            # Keep successful native navigation and missing-path status. Only
            # an initial lookup from the worker directory can use a companion.
            # A fresh native object supplies the current job's absolute root;
            # saved scripts contain no paths to an earlier worker directory.
            '\nbool '+helper+'_changeCurrentPath(filesystem@ target,const string &in filename){'+'if(target.changeCurrentPath(filename))return true;filesystem root;if(target.getCurrentPath()!=root.getCurrentPath())return false;string path='+helper+'_directoryPath(filename);if(path==filename)return false;return target.changeCurrentPath(root.getCurrentPath()+"/"+path);}\n')
    return text


def helper_code(helper,cases,directory_cases='',listing=None):
    if not listing:
        text=_legacy_helper_code(helper,cases,directory_cases)
        for method in ('getFiles','getDirs'):
            text+='\narray<string>@ '+helper+'_'+method+'(const filesystem@ target){return target.'+method+'();}\n'
        text+='\nstring '+helper+'_getCurrentPath(const filesystem@ target){return target.getCurrentPath();}\n'
    else:
        from native_custom_listing import helper_code as listing_code
        text=listing_code(helper,**listing)
        text+=('\nstring '+helper+'_filePath(const string &in filename){string listed='+helper+'_runtimeFilePath(filename);if(listed!=filename)return listed;string normalized=filename;while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);'+cases+'return filename;}\n'
               '\nstring '+helper+'_directoryPath(const string &in filename){string listed='+helper+'_runtimeDirectoryPath(filename);if(listed!=filename)return listed;string normalized=filename;while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);while(normalized.length()>1 && normalized.substr(normalized.length()-1)=="/")normalized=normalized.substr(0,normalized.length()-1);'+directory_cases+'return filename;}\n'
               # Invoke native open even for a directory or invalid mode: it
               # closes the previous handle before returning the native error.
               '\nint '+helper+'_open(file@ target,const string &in filename,const string &in mode){string path='+helper+'_runtimePath(filename);int status=target.open(path,mode);if(status==0 && mode!="r" && mode!="rb")'+helper+'_recordWrite(path);if(status!=0 && (mode=="r" || mode=="rb") && '+helper+'_runtimeFilePath(filename)==filename){string fallback='+helper+'_filePath(filename);if(fallback!=filename && fallback!=path)return target.open(fallback,mode);}return status;}\n'
               '\nbool '+helper+'_changeCurrentPath(filesystem@ target,const string &in filename){string path='+helper+'_resolvedPath(target,filename);if(target.changeCurrentPath(path))return true;filesystem root;if('+helper+'_normalizedPath('+helper+'_getCurrentPath(target))!=root.getCurrentPath())return false;string fallback='+helper+'_directoryPath(filename);if(fallback==filename)return false;return target.changeCurrentPath(root.getCurrentPath()+"/"+fallback);}\n')
    # Const methods stay callable through a const filesystem handle. All work
    # uses the original receiver, so argument/receiver expressions run once.
    for method,result in [('getSize','int64'),('isDir','bool'),('isLink','bool'),('getCreateDateTime','datetime'),('getModifyDateTime','datetime')]:
        path=helper+'_resolvedPath(target,filename)' if listing else 'filename'
        text+='\n'+result+' '+helper+'_'+method+'(const filesystem@ target,const string &in filename){return target.'+method+'('+path+');}\n'
    for method in ('makeDir','removeDir','deleteFile'):
        path=helper+'_resolvedPath(target,filename)' if listing else 'filename'
        record=('if(status==0)'+helper+'_recordWrite(path);') if listing and method=='makeDir' else ''
        text+='\nint '+helper+'_'+method+'(filesystem@ target,const string &in filename){string path='+path+';int status=target.'+method+'(path);'+record+'return status;}\n'
    for method in ('copyFile','move'):
        resolve=lambda name:helper+'_resolvedPath(target,'+name+')' if listing else name
        record=('if(status==0)'+helper+'_recordWrite(destination);') if listing else ''
        text+='\nint '+helper+'_'+method+'(filesystem@ target,const string &in source,const string &in filename){string origin='+resolve('source')+';string destination='+resolve('filename')+';int status=target.'+method+'(origin,destination);'+record+'return status;}\n'
    return text
