"""Retain custom package data in the native document and stage it before loading."""
import base64
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ATTRIBUTE='Studio.CustomAssets'


def stage(raw):
    from native_custom_scripts import unpack_package
    digest=hashlib.sha256(raw).hexdigest()
    folder=Path.cwd()/'.studio-custom-assets'/digest
    # Assets are confined to each isolated native job, never the original package.
    parent=folder.parent
    if parent.is_symlink() or folder.is_symlink():raise ValueError('Custom asset staging must use ordinary directories.')
    entry=unpack_package(raw,folder)
    return folder,entry,digest


def rewrite_reads(text,source,base,asset_root):
    """Relocate literal filenames in the original native file-profile APIs."""
    # Tokenize comments separately so examples and labels cannot become edits.
    tokens=[m for m in re.finditer(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[A-Za-z_]\w*|[^\s]',text,re.S) if not m[0].startswith(('//','/*'))]
    replacements=[]
    for i,token in enumerate(tokens):
        if token[0] not in ('ReadFileAirfoil','ReadFileXSec') or i+1>=len(tokens) or tokens[i+1][0]!='(':continue
        depth=1;j=i+2
        while j<len(tokens):
            part=tokens[j][0]
            if part=='(':depth+=1
            elif part==')':depth-=1
            elif part==',' and depth==1:break
            if depth==0:break
            j+=1
        if j+2>=len(tokens) or tokens[j][0]!=',' or not tokens[j+1][0].startswith('"') or tokens[j+2][0]!=')':continue
        literal=tokens[j+1]
        try:filename=json.loads(literal[0])
        except ValueError:raise ValueError('Use a plain relative profile filename in the package.')
        relative=Path(filename)
        candidates={(source.parent/relative).resolve(),(base/relative).resolve()}
        candidates=[p for p in candidates if p.is_relative_to(base) and p.is_file()]
        if len(candidates)!=1:raise ValueError('Choose an unambiguous in-package profile file: '+filename)
        destination=asset_root/candidates[0].relative_to(base)
        replacements.append((literal.start(),literal.end(),json.dumps(destination.relative_to(Path.cwd()).as_posix())))
    for start,end,replacement in reversed(replacements):text=text[:start]+replacement+text[end:]
    return text


def save(v,gid,raw):
    encoded=base64.b64encode(raw).decode('ascii')
    v.AddAttributeString(v.GetChildCollection(gid),ATTRIBUTE,encoded)


def restore(model):
    """Stage companions before native custom Init/Update runs during ReadVSPFile."""
    if not Path(model).exists():return
    for node in ET.parse(model).iter('Attribute'):
        if node.get('Name')!=ATTRIBUTE:continue
        encoded=node.get('StrData','')
        if len(encoded)>67_000_000:raise ValueError('Saved custom package exceeds 50 MB.')
        try:raw=base64.b64decode(encoded,validate=True)
        except ValueError:raise ValueError('Saved custom package data is invalid.')
        if not raw or len(raw)>50_000_000:raise ValueError('Saved custom package exceeds 50 MB.')
        stage(raw)
