"""Expose package data in native default-directory reads without moving writes."""
import json
import os
from pathlib import Path
import struct

RUNTIME='.studio-custom-runtime'


def begin():
    """Keep a job's initial infrastructure separate from script-created files."""
    root=Path.cwd();folder=root/RUNTIME
    if folder.is_symlink():raise ValueError('Custom runtime metadata must use an ordinary directory.')
    folder.mkdir(exist_ok=True);baseline=folder/'baseline'
    for metadata in (baseline,folder/'written'):
        if metadata.is_symlink() or metadata.exists() and not metadata.is_file():
            raise ValueError('Custom runtime metadata must use ordinary files.')
    if baseline.exists():return
    names={p.name for p in root.iterdir()}
    names.update([RUNTIME,'.studio-custom-assets','component-package','imported.vsppart',
                  'request.json','response.json','response.json.tmp','reload-request.json',
                  'engine.log','log.txt','worker-exit.json','.engine-owner.json','.engine-owner.json.tmp'])
    baseline.write_bytes(b''.join(struct.pack('<I',len(name.encode()))+name.encode() for name in sorted(names)))


def cases(source_root,base,asset_root,directories=False):
    """All includes share the entry script's native runtime root."""
    choices=[]
    for path in ([base,*base.rglob('*')] if directories else base.rglob('*')):
        if not (path.is_dir() if directories else path.is_file()):continue
        alias=Path(os.path.relpath(path,source_root)).as_posix()
        target=(asset_root/path.relative_to(base)).relative_to(Path.cwd()).as_posix()
        choices.append((alias,target))
    return ''.join('if(normalized=='+json.dumps(alias)+' || normalized==rootPath+'+json.dumps(alias)+')return '+json.dumps(target)+';\n' for alias,target in sorted(choices))


def helper_code(helper,root,file_cases,directory_cases):
    path=json.dumps(root);runtime=json.dumps(RUNTIME+'/')
    return f'''
array<string>@ {helper}_runtimeNames(const string &in filename){{
 array<string> names;file reader;if(reader.open({runtime}+filename,"r")!=0)return names;
 while(reader.getPos()+4<=reader.getSize()){{uint size=uint(reader.readUInt(4));if(size>uint(reader.getSize()-reader.getPos()))break;names.insertLast(reader.readString(size));}}reader.close();return names;
}}
string {helper}_runtimeName(const string &in filename){{
 filesystem root;string name=filename;string prefix=root.getCurrentPath()+"/";
 if(name.findFirst(prefix)==0)name=name.substr(prefix.length());while(name.length()>=2 && name.substr(0,2)=="./")name=name.substr(2);
 if(name.findFirst("/")>=0)return "";return name;
}}
bool {helper}_preferCompanion(const string &in filename){{
 string name={helper}_runtimeName(filename);if(name.length()==0)return false;
 array<string>@ hidden={helper}_runtimeNames("baseline");array<string>@ written={helper}_runtimeNames("written");
 return hidden.find(name)>=0 && written.find(name)<0;
}}
void {helper}_recordWrite(const string &in filename){{
 string name={helper}_runtimeName(filename);if(name.length()==0)return;
 array<string>@ written={helper}_runtimeNames("written");if(written.find(name)>=0)return;
 file record;if(record.open({runtime}+"written","a")==0){{record.writeUInt(name.length(),4);record.writeString(name);record.close();}}
}}
string {helper}_runtimeFilePath(const string &in filename){{
 filesystem root;string rootPath=root.getCurrentPath()+"/";string normalized=filename;
 if(normalized.findFirst(rootPath)==0)normalized=normalized.substr(rootPath.length());
 while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);
 {file_cases}return filename;
}}
string {helper}_runtimeDirectoryPath(const string &in filename){{
 filesystem root;string rootPath=root.getCurrentPath()+"/";string normalized=filename;
 if(normalized.findFirst(rootPath)==0)normalized=normalized.substr(rootPath.length());
 while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);
 while(normalized.length()>1 && normalized.substr(normalized.length()-1)=="/")normalized=normalized.substr(0,normalized.length()-1);
 {directory_cases}return filename;
}}
array<string>@ {helper}_listing(filesystem@ target,bool directories){{
 filesystem root;array<string>@ current=directories?target.getDirs():target.getFiles();
 if(target.getCurrentPath()!=root.getCurrentPath())return current;
 filesystem package;if(!package.changeCurrentPath(root.getCurrentPath()+"/"+{path}))return current;
 array<string>@ result=directories?package.getDirs():package.getFiles();
 array<string>@ hidden={helper}_runtimeNames("baseline");array<string>@ written={helper}_runtimeNames("written");
 for(uint i=0;i<current.length();i++)if((hidden.find(current[i])<0 || written.find(current[i])>=0) && result.find(current[i])<0)result.insertLast(current[i]);
 return result;
}}
array<string>@ {helper}_getFiles(filesystem@ target){{return {helper}_listing(target,false);}}
array<string>@ {helper}_getDirs(filesystem@ target){{return {helper}_listing(target,true);}}
'''
