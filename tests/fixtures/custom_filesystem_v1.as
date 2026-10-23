// Exact generated filesystem helpers from 2487962; placeholders are substituted by the migration test.

string OWNER_filePath(const string &in filename){string listed=OWNER_runtimeFilePath(filename);if(listed!=filename)return listed;string normalized=filename;while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);FILE_CASESreturn filename;}

int OWNER_open(file@ target,const string &in filename,const string &in mode){if((mode=="r" || mode=="rb") && OWNER_preferCompanion(filename)){string companion=OWNER_runtimeFilePath(filename);if(companion!=filename)return target.open(companion,mode);}int status=target.open(filename,mode);if(status==0 && mode!="r" && mode!="rb")OWNER_recordWrite(filename);if(status!=0 && (mode=="r" || mode=="rb")){string path=OWNER_filePath(filename);if(path!=filename)return target.open(path,mode);}return status;}

string OWNER_directoryPath(const string &in filename){string listed=OWNER_runtimeDirectoryPath(filename);if(listed!=filename)return listed;string normalized=filename;while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);while(normalized.length()>1 && normalized.substr(normalized.length()-1)=="/")normalized=normalized.substr(0,normalized.length()-1);DIRECTORY_CASESreturn filename;}

bool OWNER_changeCurrentPath(filesystem@ target,const string &in filename){filesystem start;if(target.getCurrentPath()==start.getCurrentPath() && OWNER_preferCompanion(filename)){string companion=OWNER_runtimeDirectoryPath(filename);if(companion!=filename)return target.changeCurrentPath(start.getCurrentPath()+"/"+companion);}if(target.changeCurrentPath(filename))return true;filesystem root;if(target.getCurrentPath()!=root.getCurrentPath())return false;string path=OWNER_directoryPath(filename);if(path==filename)return false;return target.changeCurrentPath(root.getCurrentPath()+"/"+path);}

array<string>@ OWNER_runtimeNames(const string &in filename){
 array<string> names;file reader;if(reader.open(".studio-custom-runtime/"+filename,"r")!=0)return names;
 while(reader.getPos()+4<=reader.getSize()){uint size=uint(reader.readUInt(4));if(size>uint(reader.getSize()-reader.getPos()))break;names.insertLast(reader.readString(size));}reader.close();return names;
}
string OWNER_runtimeName(const string &in filename){
 filesystem root;string name=filename;string prefix=root.getCurrentPath()+"/";
 if(name.findFirst(prefix)==0)name=name.substr(prefix.length());while(name.length()>=2 && name.substr(0,2)=="./")name=name.substr(2);
 if(name.findFirst("/")>=0)return "";return name;
}
bool OWNER_preferCompanion(const string &in filename){
 string name=OWNER_runtimeName(filename);if(name.length()==0)return false;
 array<string>@ hidden=OWNER_runtimeNames("baseline");array<string>@ written=OWNER_runtimeNames("written");
 return hidden.find(name)>=0 && written.find(name)<0;
}
void OWNER_recordWrite(const string &in filename){
 string name=OWNER_runtimeName(filename);if(name.length()==0)return;
 array<string>@ written=OWNER_runtimeNames("written");if(written.find(name)>=0)return;
 file record;if(record.open(".studio-custom-runtime/"+"written","a")==0){record.writeUInt(name.length(),4);record.writeString(name);record.close();}
}
string OWNER_runtimeFilePath(const string &in filename){
 filesystem root;string rootPath=root.getCurrentPath()+"/";string normalized=filename;
 if(normalized.findFirst(rootPath)==0)normalized=normalized.substr(rootPath.length());
 while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);
 RUNTIME_FILE_CASESreturn filename;
}
string OWNER_runtimeDirectoryPath(const string &in filename){
 filesystem root;string rootPath=root.getCurrentPath()+"/";string normalized=filename;
 if(normalized.findFirst(rootPath)==0)normalized=normalized.substr(rootPath.length());
 while(normalized.length()>=2 && normalized.substr(0,2)=="./")normalized=normalized.substr(2);
 while(normalized.length()>1 && normalized.substr(normalized.length()-1)=="/")normalized=normalized.substr(0,normalized.length()-1);
 RUNTIME_DIRECTORY_CASESreturn filename;
}
array<string>@ OWNER_listing(filesystem@ target,bool directories){
 filesystem root;array<string>@ current=directories?target.getDirs():target.getFiles();
 if(target.getCurrentPath()!=root.getCurrentPath())return current;
 filesystem package;if(!package.changeCurrentPath(root.getCurrentPath()+"/"+ROOT_LITERAL))return current;
 array<string>@ result=directories?package.getDirs():package.getFiles();
 array<string>@ hidden=OWNER_runtimeNames("baseline");array<string>@ written=OWNER_runtimeNames("written");
 for(uint i=0;i<current.length();i++)if((hidden.find(current[i])<0 || written.find(current[i])>=0) && result.find(current[i])<0)result.insertLast(current[i]);
 return result;
}
array<string>@ OWNER_getFiles(filesystem@ target){return OWNER_listing(target,false);}
array<string>@ OWNER_getDirs(filesystem@ target){return OWNER_listing(target,true);}
