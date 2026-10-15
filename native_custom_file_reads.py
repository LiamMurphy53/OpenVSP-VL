"""Resolve native file receivers before relocating their open calls."""
import re


def replacements(text,tokens,helper):
    words=[t[0] for t in tokens];count=len(words)
    classes={words[i+1] for i,w in enumerate(words[:-1]) if w in ('class','interface','enum')}
    types={'file','int','uint','double','float','bool','string','auto','array'}|classes
    pairs={}
    # Balance call, index and block scopes independently of comparison operators.
    for opening,closing in [('(',')'),('[',']'),('{','}')]:
        pending=[]
        for i,w in enumerate(words):
            if w==opening:pending.append(i)
            elif w==closing and pending:j=pending.pop();pairs[i]=j;pairs[j]=i
    def type_at(i,end):
        if i>=end or words[i] not in types:return None
        kind=words[i];j=i+1
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
        parsed=type_at(i,end)
        if parsed:
            kind,j=parsed
            if j<end and re.fullmatch(r'[A-Za-z_]\w*',words[j]):return words[j],kind,j
    class_blocks={}
    for i,w in enumerate(words[:-1]):
        if w in ('class','interface'):
            j=i+2
            while j<count and words[j] not in ('{',';'):j+=1
            if j<count and words[j]=='{':class_blocks[j]=words[i+1]
    global_fields={};scopes=[(None,global_fields)];parens=[];fields={};functions={};methods={};calls=[]
    keywords={'if','for','while','switch','catch','return'}
    for i,word in enumerate(words):
        if word=='(':
            parens.append(i);continue
        if word==')':
            if parens:parens.pop()
            continue
        if word=='{':
            owner=class_blocks.get(i);bindings={}
            if i and words[i-1]==')':
                j=pairs.get(i-1,-1)
                if j>0 and words[j-1] not in keywords:
                    for k in range(j+1,i-1):
                        decl=declaration(k,i-1)
                        if decl:bindings[decl[0]]=decl[1]
            scopes.append((owner,bindings));continue
        if word=='}':
            if len(scopes)>1:scopes.pop()
            continue
        if not parens:
            decl=declaration(i,count)
            if decl:
                name,kind,j=decl;owner,bindings=scopes[-1]
                call_style=j+1<count and words[j+1]=='('
                closing=pairs.get(j+1,-1) if call_style else -1
                first=j+2
                while first<count and words[first]=='const':first+=1
                parameter_type=type_at(first,closing) if closing>=0 else None
                function=call_style and (closing+1<count and words[closing+1]=='{' or (len(scopes)==1 or owner) and (first==closing or parameter_type is not None))
                if function:
                    if len(scopes)==1:functions[name]=kind
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
        if word=='open' and i>=2 and i+1<count and words[i-1]=='.' and words[i+1]=='(':
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
        return end
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
            if opening-1==start:return functions.get(function)
            if opening>=2 and words[opening-2]=='.':
                owner=resolve(start,opening-3,context,depth+1)
                return methods.get(owner,{}).get(function)
            return None
        name=words[end]
        if start==end:
            if name=='this':return next((c for c,_ in reversed(context) if c),None)
            kind=next((fields.get(c,{}).get(name) if c else s[name] for c,s in reversed(context[1:]) if name in s or c and name in fields.get(c,{})),global_fields.get(name))
            return inferred(kind)
        if end>=2 and words[end-1]=='.':
            owner=resolve(start,end-2,context,depth+1)
            return inferred(fields.get(owner,{}).get(name))
    result=[]
    for i,end,context in calls:
        start=bounds(i-2)
        if resolve(start,i-2,context)!='file':continue
        commas=0;j=i+2
        while j<end:
            if words[j]==',':commas+=1
            if words[j] in ('(','[') and j in pairs:j=pairs[j]
            j+=1
        if commas!=1:continue
        receiver=text[tokens[start].start():tokens[i-1].start()]
        result.append((tokens[start].start(),tokens[i+1].end(),helper+'_open(@('+receiver+'),'))
    return result


def helper_code(helper,cases):
    return ('\nstring '+helper+'_filePath(const string &in filename){string normalized=filename;while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);'+cases+'return filename;}\n'
            '\nint '+helper+'_open(file@ target,const string &in filename,const string &in mode){int status=target.open(filename,mode);if(status!=0 && (mode=="r" || mode=="rb")){string path='+helper+'_filePath(filename);if(path!=filename)return target.open(path,mode);}return status;}\n')
