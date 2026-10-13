import {mountMeshViewer} from './mesh-viewer.js?v=20261010-123';
// Connectivity below joins the engine's own drawing points for display only.
let cleanup=null,generation=0;
export function disposeStructuralPreview(){generation++;if(cleanup){cleanup();cleanup=null;}}
export function drawingMesh(data,component=null){
 const nodes=[],nodeIDs=[],elements=[],groups=[];let serial=0;
 for(const part of [...data.parts,...(data.regions||[])]){
  const group=part.index+1+(part.isRegion?data.parts.length:0),start=elements.length;
  for(const object of part.objects){
   const offset=nodes.length;nodes.push(...object.points);nodeIDs.push(...object.points.map((_,i)=>object.nativeID+' · point '+i));
   const add=(kind,indices)=>elements.push({id:++serial,kind,type:kind==='point'?15:kind==='line'?1:indices.length===4?3:2,group,nodes:indices.map(i=>offset+i),order:1,nativeDrawingID:object.nativeID,nativeDrawingType:object.nativeType,nativeOpacity:object.opacity,nativeSurface:object.surface,displayOverlay:!!part.isRegion});
   const n=object.points.length;
   if(object.kind==='points')for(let i=0;i<n;i++)add('point',[i]);
   if(object.kind==='lines')for(let i=0;i+1<n;i+=2)add('line',[i,i+1]);
   if(object.kind==='strip'||object.kind==='loop'){for(let i=0;i+1<n;i++)add('line',[i,i+1]);if(object.kind==='loop'&&n>1)add('line',[n-1,0]);}
   const width=object.kind==='quads'?4:object.kind==='triangles'?3:0;
   if(width)for(let i=0;i+width<=n;i+=width)add('face',Array.from({length:width},(_,j)=>i+j));
  }
  if(elements.length>start)groups.push({id:group,name:part.name+(part.isRegion?' · region':''),count:elements.length-start});
 }
 for(const [ci,context] of (Array.isArray(component)?component:component?[component]:[]).entries()){
  const start=elements.length,group=-ci;component=context;
  for(const surface of component.surfaces){const offset=nodes.length;nodes.push(...surface.points);nodeIDs.push(...surface.points.map((_,i)=>component.id+' · surface '+surface.index+' · point '+i));for(let i=0;i<surface.rows-1;i++)for(let j=0;j<surface.cols-1;j++){const a=offset+i*surface.cols+j;elements.push({id:++serial,kind:'face',type:'native surface samples',group,nodes:[a,a+surface.cols,a+surface.cols+1,a+1],order:1,nativeSurface:surface.index});}}
  if(elements.length>start)groups.push({id:group,name:component.name+' · aircraft surface',count:elements.length-start,initiallyHidden:!data.showContext});
 }
 const warnings=component?data.warnings.filter(w=>!data.parts.some(p=>p.isSkin&&!p.objects.length&&w.startsWith(p.name+':'))):data.warnings;
 return {nodes,nodeIDs,elements,groups,totalElements:elements.length,unsupportedElements:0,higherOrder:false,geometryPreview:true,filename:data.filename||'Structural construction preview',warnings,displayNote:data.displayNote||'These are OpenVSP’s native part construction surfaces, region boundary samples, outlines and fixed points. Region boundaries are shown through surfaces for inspection. Compute intersection regions after geometry changes. Trimming and final element sizing are evaluated when the structure is meshed.'};
}
export function mountAssemblyPreview(host,assembly,app){return mountStructuralPreview(host,assembly,app,true);}
export function mountStructuralPreview(host,structure,app,isAssembly=false){
 disposeStructuralPreview();
 if(!host||!structure)return;
 const token=generation;
 const revision=app.model().revision;
 host.innerHTML='<div class="tool-actions"><button data-preview-refresh>Refresh preview</button><button data-preview-download disabled>Download native drawing points</button></div><div data-preview-viewer><p>Reading native structural drawing points…</p></div>';
 const viewer=host.querySelector('[data-preview-viewer]'),download=host.querySelector('[data-preview-download]');
 host.querySelector('[data-preview-refresh]').onclick=()=>mountStructuralPreview(host,structure,app,isAssembly);
 app.api('/api/query',isAssembly?{operation:'assembly-preview',assembly:structure.id,revision}:{operation:'structural-preview',structure:structure.id,revision}).then(data=>{
  if(!host.isConnected||app.model().revision!==revision||token!==generation)return;
  const mesh=drawingMesh(data,isAssembly?app.model().components.filter(c=>data.geoms.includes(c.id)):app.model().components.find(c=>c.id===structure.geom));
  if(!mesh.nodes.length){viewer.innerHTML='<p>OpenVSP returned no part drawing points. Add a rib, spar, attachment point or another structural part.</p>';return;}
  cleanup=mountMeshViewer(viewer,mesh,app.esc);
  download.disabled=false;download.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({...data,revision},null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download=isAssembly?'native-assembly-drawing.json':'native-structural-drawing.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 }).catch(error=>{if(host.isConnected&&token===generation)viewer.innerHTML='<p class="status-error">'+app.esc(error.message)+'</p>';});
}
