// Screen-space navigation only; native geometry and solver inputs never change.
export function installViewControls(canvas,{rotate,pan,zoom,select}){
 let drag=null;
 canvas.style.touchAction='none';
 canvas.onpointerdown=e=>{
  if(drag||![0,1].includes(e.button))return;
  e.preventDefault();canvas.focus({preventScroll:true});
  drag={id:e.pointerId,button:e.button,x:e.clientX,y:e.clientY,sx:e.clientX,sy:e.clientY,moved:false};
  canvas.setPointerCapture(e.pointerId);canvas.style.cursor=e.button===1?'grabbing':'move';
 };
 canvas.onpointermove=e=>{
  if(!drag||drag.id!==e.pointerId)return;
  const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
  if(Math.hypot(e.clientX-drag.sx,e.clientY-drag.sy)>=4)drag.moved=true;
  if(drag.button===1)pan(dx,dy);else rotate(dx,dy);
  drag.x=e.clientX;drag.y=e.clientY;
 };
 const end=e=>{if(!drag||e.pointerId!==drag.id)return;const previous=drag;drag=null;canvas.style.cursor='';if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);if(e.type==='pointerup'&&previous.button===0&&!previous.moved)select?.(e);};
 canvas.onpointerup=end;canvas.onpointercancel=end;canvas.onlostpointercapture=()=>{drag=null;canvas.style.cursor='';};
 canvas.addEventListener('wheel',e=>{e.preventDefault();const pixels=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?canvas.clientHeight:1);zoom(pixels);},{passive:false});
}
