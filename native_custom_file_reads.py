"""Locate typed native file-handle opens without rewriting unrelated methods."""
import re


def replacements(text,tokens,helper):
    types={'file','int','uint','double','float','bool','string','auto'}
    types.update(tokens[i+1][0] for i,t in enumerate(tokens[:-1]) if t[0] in ('class','interface','enum'))
    scopes=[{}];parens=[];result=[]
    def declaration(i,end):
        if tokens[i][0] not in types:return None
        j=i+1
        while j<end and tokens[j][0] in ('@','&','in','out','inout','const'):j+=1
        if j<end and re.fullmatch(r'[A-Za-z_]\w*',tokens[j][0]):return tokens[j][0],tokens[i][0],j
    for i,token in enumerate(tokens):
        word=token[0]
        if word=='(':
            parens.append(i);continue
        if word==')':
            if parens:parens.pop()
            continue
        if word=='{':
            bindings={}
            if i and tokens[i-1][0]==')':
                depth=1;j=i-2
                while j>=0:
                    if tokens[j][0]==')':depth+=1
                    elif tokens[j][0]=='(':depth-=1
                    if depth==0:break
                    j-=1
                if j>0 and tokens[j-1][0] not in ('if','for','while','switch','catch'):
                    for k in range(j+1,i-1):
                        decl=declaration(k,i-1)
                        if decl:bindings[decl[0]]=decl[1]
            scopes.append(bindings);continue
        if word=='}':
            if len(scopes)>1:scopes.pop()
            continue
        if not parens:
            decl=declaration(i,len(tokens))
            if decl and (decl[2]+1==len(tokens) or tokens[decl[2]+1][0]!='('):scopes[-1][decl[0]]=decl[1]
        if word!='open' or i<2 or i+1>=len(tokens) or tokens[i-1][0]!='.' or tokens[i+1][0]!='(':continue
        receiver=tokens[i-2][0];kind=next((s[receiver] for s in reversed(scopes) if receiver in s),None)
        if kind!='file':continue
        # A plain handle receiver only. Member/index/factory expressions require
        # their own type resolution; never guess from the method name alone.
        if i>=3 and tokens[i-3][0] in ('.',']',')'):continue
        j=i+2;depth=1;commas=[]
        while j<len(tokens):
            if tokens[j][0]=='(':depth+=1
            elif tokens[j][0]==')':depth-=1
            if depth==0:break
            if tokens[j][0]==',' and depth==1:commas.append(j)
            j+=1
        if j==len(tokens) or len(commas)!=1:continue
        result.append((tokens[i-2].start(),tokens[i+1].end(),helper+'_open(@'+receiver+','))
    return result
