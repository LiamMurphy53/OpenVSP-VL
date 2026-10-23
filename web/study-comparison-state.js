const sameExecution=(a,b)=>a?.study===b?.study&&a?.id===b?.id;

// A comparison belongs to one saved execution and one native result field.
// Request sequence numbers also reject older responses for that same pair.
export function studyComparisonState(){
 let target=null,key=null,data=null,phase='idle',message='',serial=0;
 const current=token=>token.serial===serial&&sameExecution(token,target)&&token.key===key;
 return {
  get snapshot(){return {target,key,data,phase,message};},
  select(execution){
   const next=execution?{study:execution.study,id:execution.id}:null;
   if(sameExecution(target,next))return;
   target=next;key=null;data=null;message='';phase=next?'loading':'idle';serial++;
  },
  begin(field){
   if(!target)throw Error('Choose a saved execution.');
   if(key!==field)data=null;
   key=field;phase='loading';message='';return {...target,key,serial:++serial};
  },
  resolve(token,result){
   if(!current(token))return false;
   if(!sameExecution(target,result)||result.field?.key!==key){
    this.reject(token,Error('The returned results do not match the selected execution and field.'));
    return true;
   }
   data=result;phase='ready';message='';return true;
  },
  reject(token,error){
   if(!current(token))return false;
   data=null;phase='error';message=error.message;return true;
  },
  fail(error){serial++;data=null;phase='error';message=error.message;},
  empty(){serial++;key=null;data=null;phase=target?'empty':'idle';message='';}
 };
}
