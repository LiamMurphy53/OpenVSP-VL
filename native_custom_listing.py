"""Expose package data in native default-directory reads without moving writes."""
import json
import os
import re
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
    # Directory cases include the package root itself. Keep the runtime boundary
    # explicit so lexical parent navigation cannot select another staged bundle.
    targets=[json.loads(value) for value in re.findall(r'return ("(?:\\.|[^"\\])*");',directory_cases)]
    base=min(targets,key=lambda value:len(Path(value).parts)) if targets else root
    path=json.dumps(root);boundary=json.dumps(base);runtime=json.dumps(RUNTIME+'/')
    return f'''
bool {helper}_runtimeV2(){{return true;}}
array<string>@ {helper}_runtimeNames(const string &in filename){{
 array<string> names;file reader;if(reader.open({runtime}+filename,"r")!=0)return names;
 while(reader.getPos()+4<=reader.getSize()){{uint size=uint(reader.readUInt(4));if(size>uint(reader.getSize()-reader.getPos()))break;names.insertLast(reader.readString(size));}}reader.close();return names;
}}
string {helper}_absolutePath(const string &in current,const string &in filename){{
 if(filename.findFirst(":")>=0 || filename.findFirst("/")==0 || filename.findFirst("\\\\")==0)return filename;
 return current+"/"+filename;
}}
string {helper}_normalizedPath(const string &in filename){{
 array<string>@ parts=filename.split("/");array<string> normalized;
 for(uint i=0;i<parts.length();i++){{if(parts[i]=="" || parts[i]==".")continue;if(parts[i]==".." && normalized.length()>0 && normalized[normalized.length()-1]!="..")normalized.removeLast();else normalized.insertLast(parts[i]);}}
 string result=filename.findFirst("/")==0?"/":"";for(uint i=0;i<normalized.length();i++){{if(i>0)result+="/";result+=normalized[i];}}return result;
}}
string {helper}_getCurrentPath(const filesystem@ target){{
 filesystem root;string current=target.getCurrentPath();string prefix=root.getCurrentPath()+"/"+{path};
 if(current==prefix)return root.getCurrentPath();if(current.findFirst(prefix+"/")==0)return root.getCurrentPath()+current.substr(prefix.length());return current;
}}
string {helper}_runtimeName(const string &in filename){{
 filesystem root;string name={helper}_normalizedPath({helper}_absolutePath(root.getCurrentPath(),filename));string prefix=root.getCurrentPath()+"/";
 if(name.findFirst(prefix)!=0)return "";name=name.substr(prefix.length());int slash=name.findFirst("/");return slash<0?name:name.substr(0,slash);
}}
bool {helper}_preferCompanion(const string &in filename){{
 string name={helper}_runtimeName(filename);if(name.length()==0)return false;
 array<string>@ hidden={helper}_runtimeNames("baseline");array<string>@ written={helper}_runtimeNames("written");
 return hidden.find(name)>=0 && written.find(name)<0;
}}
void {helper}_recordWrite(const string &in filename){{
 string name={helper}_runtimeName(filename);if(name.length()==0 || name==".studio-custom-assets")return;
 array<string>@ written={helper}_runtimeNames("written");if(written.find(name)>=0)return;
 file record;if(record.open({runtime}+"written","a")==0){{record.writeUInt(name.length(),4);record.writeString(name);record.close();}}
}}
string {helper}_packagePath(const string &in filename){{
 filesystem root;string native=root.getCurrentPath();string absolute={helper}_absolutePath(native,filename);string relative;
 if(absolute==native)relative="";else if(absolute.findFirst(native+"/")==0)relative=absolute.substr(native.length()+1);else return filename;
 string existing={helper}_normalizedPath(absolute);string staged={helper}_normalizedPath(native+"/"+{boundary});if(filename.findFirst("/")==0 && (existing==staged || existing.findFirst(staged+"/")==0))return filename;
 string candidate=native+"/"+{path}+(relative.length()>0?"/"+relative:"");string normalized={helper}_normalizedPath(candidate);string boundary={helper}_normalizedPath(native+"/"+{boundary});
 if(normalized!=boundary && normalized.findFirst(boundary+"/")!=0)return filename;
 return candidate;
}}
string {helper}_runtimePath(const string &in filename){{
 filesystem root;string absolute={helper}_absolutePath(root.getCurrentPath(),filename);string companion={helper}_packagePath(absolute);
 if(companion==absolute)return filename;
 if({helper}_runtimeName(absolute).length()>0 && !{helper}_preferCompanion(absolute)){{
  if(root.getSize(absolute)>=0)return absolute;
  int slash=absolute.findLast("/");if(slash>=0 && {helper}_normalizedPath(absolute.substr(0,slash))!=root.getCurrentPath() && root.isDir(absolute.substr(0,slash)) && root.getSize(companion)<0)return absolute;
 }}
 return companion;
}}
string {helper}_resolvedPath(const filesystem@ target,const string &in filename){{
 return {helper}_runtimePath({helper}_absolutePath({helper}_getCurrentPath(target),filename));
}}
string {helper}_runtimeFilePath(const string &in filename){{
 filesystem root;string rootPath=root.getCurrentPath()+"/";string normalized=filename;
 if(normalized.findFirst(rootPath)==0)normalized=normalized.substr(rootPath.length());normalized={helper}_normalizedPath(normalized);
 {file_cases}return filename;
}}
string {helper}_runtimeDirectoryPath(const string &in filename){{
 filesystem root;string rootPath=root.getCurrentPath()+"/";string normalized=filename;
 if(normalized.findFirst(rootPath)==0)normalized=normalized.substr(rootPath.length());normalized={helper}_normalizedPath(normalized);if(normalized.length()==0)normalized=".";
 {directory_cases}return filename;
}}
array<string>@ {helper}_listing(const filesystem@ target,bool directories){{
 filesystem root;string logical={helper}_getCurrentPath(target);string companion={helper}_packagePath(logical);
 if(companion==logical)return directories?target.getDirs():target.getFiles();
 array<string> result;filesystem package;
 if(package.changeCurrentPath(companion)){{array<string>@ names=directories?package.getDirs():package.getFiles();result=names;}}
 if({helper}_normalizedPath(logical)!=root.getCurrentPath() && {helper}_runtimeName(logical).length()==0)return result;
 filesystem native;if(!native.changeCurrentPath(logical))return result;
 for(int i=int(result.length())-1;i>=0;i--){{string name=logical+"/"+result[i];if(!{helper}_preferCompanion(name) && native.getSize(name)>=0 && native.isDir(name)!=directories)result.removeAt(i);}}
 array<string>@ current=directories?native.getDirs():native.getFiles();
 for(uint i=0;i<current.length();i++)if(!{helper}_preferCompanion(logical+"/"+current[i]) && result.find(current[i])<0)result.insertLast(current[i]);
 return result;
}}
array<string>@ {helper}_getFiles(const filesystem@ target){{return {helper}_listing(target,false);}}
array<string>@ {helper}_getDirs(const filesystem@ target){{return {helper}_listing(target,true);}}
'''
