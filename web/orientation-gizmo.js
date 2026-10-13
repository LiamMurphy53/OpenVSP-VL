// Camera orientation indicator; it does not transform native geometry.
export function drawOrientationGizmo(canvas,yaw,pitch){
 const ctx=canvas.getContext('2d'),size=88,dpr=Math.min(devicePixelRatio||1,2);
 canvas.width=size*dpr;canvas.height=size*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,size,size);
 const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch),origin=[44,44];
 const axes=[['X','#bd5b52',[cy,sy*sp,sy*cp]],['Y','#33846d',[-sy,cy*sp,cy*cp]],['Z','#557eae',[0,-cp,sp]]].sort((a,b)=>a[2][2]-b[2][2]);
 ctx.lineCap='round';ctx.font='bold 11px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';
 const labels=[];
 for(const [name,color,[x,y]] of axes){
  const end=[origin[0]+x*29,origin[1]+y*29],angle=Math.atan2(y,x);
  ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(...origin);ctx.lineTo(...end);ctx.stroke();
  if(Math.hypot(x,y)>.15){ctx.beginPath();ctx.moveTo(end[0]-6*Math.cos(angle-.45),end[1]-6*Math.sin(angle-.45));ctx.lineTo(...end);ctx.lineTo(end[0]-6*Math.cos(angle+.45),end[1]-6*Math.sin(angle+.45));ctx.stroke();}
  const label=Math.hypot(x,y)<.2?[origin[0]+(name==='X'?-15:15),origin[1]-15]:[origin[0]+x*38,origin[1]+y*38];
  if(labels.some(l=>Math.hypot(l.point[0]-label[0],l.point[1]-label[1])<16))label[0]=Math.max(9,Math.min(79,label[0]+(name==='X'?-17:17)));
  labels.push({name,color,point:label});
 }
 ctx.fillStyle='#fff';ctx.strokeStyle='#8c9c8c';ctx.lineWidth=1;ctx.beginPath();ctx.arc(...origin,3,0,2*Math.PI);ctx.fill();ctx.stroke();
 for(const {name,color,point} of labels){ctx.fillStyle='#f5f8f0';ctx.beginPath();ctx.arc(...point,8,0,2*Math.PI);ctx.fill();ctx.fillStyle=color;ctx.fillText(name,...point);}
}
