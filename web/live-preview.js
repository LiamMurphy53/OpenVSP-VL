// Serialize native queries and keep only the newest requested preview.
// A superseded response must never enable saving an obsolete inspection.
export function latestPreview({request,show,fail,pending,isCurrent=()=>true,delay=120,setTimer=setTimeout,clearTimer=clearTimeout}){
 let serial=0,queued=null,active=null,running=false,timer=null,disposed=false,lastKey=null;
 const current=()=>!disposed&&isCurrent();
 async function run(){
  timer=null;if(running||!queued||!current())return;
  const work=queued;queued=null;active=work;running=true;
  try{const data=await request(work.value);if(current()&&work.serial===serial){show(data);lastKey=work.key;}}
  catch(error){if(current()&&work.serial===serial){lastKey=null;fail(error);}}
  finally{running=false;active=null;if(queued&&current())run();}
 }
 return {
  schedule(value,immediate=false){
   if(!current())return;
   const key=JSON.stringify(value);
   if(key===lastKey&&!queued&&!running)return;
   if(key===active?.key&&active.serial===serial)return;
   if(key===queued?.key){if(immediate&&!running){if(timer!==null)clearTimer(timer);timer=null;run();}return;}
   queued={value,key,serial:++serial};pending();
   if(immediate){if(timer!==null)clearTimer(timer);timer=null;run();}
   else if(!running&&timer===null)timer=setTimer(run,delay);
  },
  invalidate(){serial++;queued=null;lastKey=null;if(timer!==null)clearTimer(timer);timer=null;},
  dispose(){disposed=true;this.invalidate();}
 };
}
