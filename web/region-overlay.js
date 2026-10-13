// Region coordinates and polygon sampling come directly from OpenVSP.
let app,data=null,revision=null,generation=0,focus='';
const $=s=>document.querySelector(s);
export function installRegionOverlays(context){
 app=context;
 $('#show-region-boundaries').onchange=()=>app.draw();
 $('#region-boundary-choice').onchange=e=>{focus=e.target.value;status();app.draw();};
 $('#refresh-region-boundaries').onclick=()=>refreshRegionOverlays(true);
 $('#download-region-boundaries').onclick=()=>{
  if(!data||revision!==app.model().revision)return;
  const regions=data.regions.filter(r=>!focus||r.id===focus),saved={...data,regions,revision};
  const url=URL.createObjectURL(new Blob([JSON.stringify(saved,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='native-region-boundaries.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
}
function status(){
 const regions=(data?.regions||[]).filter(r=>!focus||r.id===focus),paths=regions.flatMap(r=>r.paths).filter(p=>p.valid),points=paths.reduce((n,p)=>n+p.points.length,0);
 $('#region-boundary-count').textContent=`${paths.length} paths`;
 $('#region-boundary-status').textContent=`${paths.length} native boundary paths · ${points} native points. Includes native symmetry copies. Lines show through surfaces for inspection.`;
 const warnings=(data?.warnings||[]).filter(w=>!focus||w.startsWith(regions[0]?.name+':'));
 if(warnings.length)$('#region-boundary-status').textContent+=' '+warnings.join(' ');
 if(focus&&regions[0]&&app.model().components.find(c=>c.id===regions[0].geom)?.shown===false)$('#region-boundary-status').textContent+=' The parent component is hidden; show it to see this boundary.';
}
export async function refreshRegionOverlays(force=false){
 if(!app||!app.model())return;const model=app.model(),token=force||revision!==model.revision?++generation:generation;
 $('#region-overlay-panel').hidden=!model.tools.controls.length;
 if(!model.tools.controls.length){data=null;revision=model.revision;app.draw();return;}
 if(!force&&revision===model.revision)return;
 revision=model.revision;data=null;$('#region-boundary-count').textContent='reading…';$('#region-boundary-status').textContent='Reading native boundary samples…';$('#download-region-boundaries').disabled=true;
 try{
  const saved=await app.api('/api/query',{operation:'region-boundaries',revision:model.revision});
  if(token!==generation||app.model().revision!==model.revision)return;
  data=saved;
  if(focus&&!saved.regions.some(r=>r.id===focus))focus='';
  $('#region-boundary-choice').innerHTML='<option value="">All surface regions</option>'+saved.regions.map(r=>`<option value="${app.esc(r.id)}">${app.esc(app.model().components.find(c=>c.id===r.geom)?.name)} · ${app.esc(r.name)}</option>`).join('');
  $('#region-boundary-choice').value=focus;$('#download-region-boundaries').disabled=false;status();app.draw();
 }catch(e){if(token!==generation)return;$('#region-boundary-count').textContent='unavailable';$('#region-boundary-status').textContent=e.message+' Use Refresh boundaries to retry.';}
}
export function focusRegionBoundary(id){
 focus=id;$('#show-region-boundaries').checked=true;$('#region-overlay-panel').open=true;
 $('#region-boundary-choice').value=id;if(data){status();app.draw();}
}
export function drawRegionOverlays(ctx,project){
 if(!data||revision!==app.model().revision||!$('#show-region-boundaries').checked)return;
 const visible=new Set(app.model().components.filter(c=>c.shown!==false).map(c=>c.id));
 ctx.save();ctx.setLineDash([]);ctx.globalAlpha=1;ctx.lineWidth=focus?2.3:1.5;
 for(const [i,r] of data.regions.entries()){
  if(!visible.has(r.geom)||focus&&r.id!==focus)continue;
  ctx.strokeStyle=['#b56826','#296e8b','#9b4a77','#6c7832','#655ea2','#287c64'][i%6];ctx.fillStyle=ctx.strokeStyle;
  for(const path of r.paths){
   if(!path.valid)continue;const pts=path.points.map(project);ctx.beginPath();
   pts.forEach((p,j)=>j?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.stroke();
   if(pts.length===1){ctx.beginPath();ctx.arc(pts[0][0],pts[0][1],3,0,Math.PI*2);ctx.fill();}
  }
 }
 ctx.restore();
}
