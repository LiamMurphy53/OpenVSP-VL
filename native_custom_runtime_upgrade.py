"""Upgrade the complete first-generation embedded filesystem helper group."""
import hashlib
import re


SUFFIXES=('_filePath','_open','_directoryPath','_changeCurrentPath',
          '_runtimeNames','_runtimeName','_preferCompanion','_recordWrite',
          '_runtimeFilePath','_runtimeDirectoryPath','_listing','_getFiles','_getDirs')
# Complete generated declarations and bodies from 2487962, with only the owner, source alias
# tables, runtime alias tables and package root replaced/removed. A partial or
# user-modified group is not an upgrade candidate.
V1_DIGEST='f2d51fabdebe42f897934344970eb7a7fb1f3917128fe8a16990ae822c5c0b0a'
QUOTED=r'"(?:\\.|[^"\\])*"'
SOURCE_CASE=r'if\(normalized=='+QUOTED+r'\)return '+QUOTED+r';\n'
RUNTIME_CASE=r'if\(normalized=='+QUOTED+r' \|\| normalized==rootPath\+'+QUOTED+r'\)return '+QUOTED+r';\n'
SOURCE_SLOT=re.compile('(?P<cases>(?:'+SOURCE_CASE+r')*)return filename;\Z')
RUNTIME_SLOT=re.compile('(?P<cases>(?:'+RUNTIME_CASE+r')*)return filename;\n\Z')


def edits(functions,listing):
    """Return whole-group edits and owners upgraded without touching profiles."""
    from native_custom_file_reads import helper_code
    groups={}
    for function in functions:
        match=re.fullmatch(r'(StudioPackage(?:Profile|Upgrade)_[0-9a-f]{16})(_[A-Za-z0-9_]+)',function['name'])
        if match and match[2] in SUFFIXES:
            groups.setdefault(match[1],{}).setdefault(match[2],[]).append(function)
    result=[];upgraded=set()
    for owner,group in groups.items():
        if set(group)!=set(SUFFIXES) or any(len(items)!=1 for items in group.values()):continue
        group={suffix:items[0] for suffix,items in group.items()}
        normalized=[];aliases={};valid=True
        for suffix,function in group.items():
            body=function['body'].replace(owner,'OWNER')
            slot=SOURCE_SLOT if suffix in ('_filePath','_directoryPath') else RUNTIME_SLOT if suffix in ('_runtimeFilePath','_runtimeDirectoryPath') else None
            if slot:
                match=slot.search(body)
                if not match:valid=False;break
                aliases[suffix]=slot.search(function['body'])['cases']
                body=body[:match.start('cases')]+body[match.end('cases'):]
            if suffix=='_listing':
                body=re.sub(r'(package.changeCurrentPath\(root.getCurrentPath\(\)\+"/"\+)'+QUOTED,r'\1"ROOT"',body)
            normalized.append((suffix,function['declaration'].replace(owner,'OWNER'),body))
        if not valid or hashlib.sha256(repr(sorted(normalized)).encode()).hexdigest()!=V1_DIGEST:continue
        updated=helper_code(owner,aliases['_filePath'],aliases['_directoryPath'],listing=listing)
        ordered=sorted(group.values(),key=lambda function:function['start'])
        for index,function in enumerate(ordered):
            result.append((function['start'],function['end'],updated if index==0 else ''))
        upgraded.add(owner)
    return result,upgraded
