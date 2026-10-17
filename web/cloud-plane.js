import {downloadQueryResult} from './volume-tools.js?v=20261010-123';
const results=new Map();
export function cloudPlaneCSV(data){
 const number=value=>Object.is(value,-0)?'-0':String(value);
 return 'Point,X,Y,Z,SignedOffset\n'+data.points.map((point,i)=>[i+1,...point,data.signedOffsets[i]].map(number).join(',')).join('\n')+'\n';
}
export function mountCloudPlane(host,cloud,model,app,h){
 const {E,button,bind}=h,format=value=>E(Number(value.toPrecision(10))),key=cloud.id;
 const result=results.get(key),data=result?.data;
 const changed=result&&result.revision!==model.revision;
 host.innerHTML=`<p>Fit a least-squares plane through this cloud in model coordinates. The aircraft is unchanged.</p>${button('cloud-fit-plane','Fit plane',true)}${data?`${changed?'<p role="status">Aircraft changed. Fit again to refresh.</p>':''}<p>${data.pointCount.toLocaleString()} points · ${E(data.coordinateFrame)}. Center coordinates and signed offsets use model units.</p>${data.pointSpread!=='noncollinear'?'<p role="status">These points do not define a unique plane. OpenVSP’s returned normal is one of several possible directions.</p>':''}<table class="result-table"><thead><tr><th></th><th>X</th><th>Y</th><th>Z</th></tr></thead><tbody><tr><th>Plane center</th>${data.center.map(x=>`<td>${format(x)}</td>`).join('')}</tr><tr><th>Normal direction</th>${data.normal.map(x=>`<td>${format(x)}</td>`).join('')}</tr></tbody></table><p>The normal’s sign follows OpenVSP. Reversing it describes the same plane and reverses the signed offsets.</p><div class="tool-actions">${button('cloud-plane-json','Download plane JSON')}${button('cloud-plane-csv','Download point offsets CSV')}</div><details><summary>Point offsets${data.pointCount>200?' · first 200 shown':''}</summary><div class="guide-table-scroll"><table class="result-table"><thead><tr><th>Point</th><th>X</th><th>Y</th><th>Z</th><th>Signed offset</th></tr></thead><tbody>${data.points.slice(0,200).map((point,i)=>`<tr><td>${i+1}</td>${[...point,data.signedOffsets[i]].map(x=>`<td>${format(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`:''}`;
 host.querySelector('#cloud-fit-plane').disabled=cloud.points.length<3;
 bind('cloud-fit-plane',async()=>{
  const button=host.querySelector('#cloud-fit-plane');button.disabled=true;
  try{
   const request={operation:'cloud-fit-plane',geom:key},data=await app.api('/api/query',{...request,revision:model.revision});
   results.set(key,{operation:request.operation,revision:model.revision,engineVersion:model.version,request,data});
   if(host.isConnected)mountCloudPlane(host,cloud,app.model(),app,h);
  }finally{if(host.isConnected)host.querySelector('#cloud-fit-plane').disabled=cloud.points.length<3;}
 });
 if(data){
  bind('cloud-plane-json',()=>downloadQueryResult(result));
  bind('cloud-plane-csv',()=>{
   const url=URL.createObjectURL(new Blob([cloudPlaneCSV(data)],{type:'text/csv'})),a=document.createElement('a');a.href=url;a.download='native-cloud-plane-offsets.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
 }
}
