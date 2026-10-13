import {mountMeshViewer} from './mesh-viewer.js?v=20261010-123';
import {drawingMesh} from './structural-preview.js?v=20261010-123';
let cleanup=null,generation=0;
export function disposeFamilyWorkflows(){generation++;if(cleanup){cleanup();cleanup=null;}}
export function familyWorkflowsMarkup(c,{esc:E}){
 if(c.conformalSource){
  const s=c.conformalSource,options=[...s.choices];
  if(!options.some(o=>o.id===s.id))options.unshift({id:s.id,name:s.name,type:s.type||'Unavailable'});
  return `<details class="parameter-group geometry-primary" data-group="conformal-source" open><summary>Conformal source surface</summary><p class="native-tip">Current native source: ${E(s.name)}${s.type?' · '+E(s.type):''}. The source surface can differ from the hierarchy parent after detachment. Enable Detach from source component below to choose a separate source.</p><label class="tool-field">Source component<select data-conformal-source aria-label="Conformal source component" ${s.detached?'':'disabled'}>${options.map(o=>`<option value="${E(o.id)}" ${o.id===s.id?'selected':''}>${E(o.name)} · ${E(o.type)}</option>`).join('')}</select></label><button data-conformal-apply disabled>Apply source surface</button><p class="native-tip" data-conformal-status role="status">${s.detached?'Choose a source with native surfaces.':'Attached source follows the native parent.'}</p></details>`;
 }
 if(c.type.toUpperCase()==='HINGE')return `<details class="parameter-group" data-group="hinge-inspection"><summary>Inspect hinge motion guides</summary><p class="native-tip">Original base, attachment and moving-joint axes, motion arrows and target lines in world XYZ. Geometry is sampled by OpenVSP. Inspector group visibility is independent of main-window feature visibility.</p><button data-hinge-refresh>Refresh native guides</button><button data-hinge-download disabled>Download native hinge points</button><div data-hinge-view><p>Open this section to load native hinge guides.</p></div></details>`;
 return '';
}
export function bindFamilyWorkflows(c,root,app){
 if(c.conformalSource){
  const s=c.conformalSource,choice=root.querySelector('[data-conformal-source]'),button=root.querySelector('[data-conformal-apply]'),status=root.querySelector('[data-conformal-status]');
  choice.onchange=()=>{button.disabled=!s.detached||choice.value===s.id;status.textContent=button.disabled?'Source matches the saved aircraft.':'Apply to update the original native source surface.';};
  button.onclick=()=>app.mutate({operation:'conformal-source',geom:c.id,source:choice.value});
 }
 const detail=root.querySelector('[data-group="hinge-inspection"]');if(!detail)return;
 const viewer=root.querySelector('[data-hinge-view]'),refresh=root.querySelector('[data-hinge-refresh]'),download=root.querySelector('[data-hinge-download]');
 let loaded=false,loading=false;
 const load=async()=>{
  if(loading)return;loading=true;refresh.disabled=true;download.disabled=true;
  const token=++generation,revision=app.model().revision;
  if(cleanup){cleanup();cleanup=null;}
  viewer.innerHTML='<p>Reading original native hinge guides…</p>';
  try{
   const data=await app.api('/api/query',{operation:'hinge-preview',geom:c.id,revision});
   if(!root.isConnected||token!==generation||app.model().revision!==revision)return;
   const mesh=drawingMesh(data,app.model().components.filter(g=>g.shown!==false));
   cleanup=mountMeshViewer(viewer,mesh,app.esc);loaded=true;download.disabled=false;
   download.onclick=()=>{
    const url=URL.createObjectURL(new Blob([JSON.stringify({...data,revision,version:app.model().version},null,2)],{type:'application/json'})),link=document.createElement('a');
    link.href=url;link.download='native-hinge-guides.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   };
  }catch(error){if(root.isConnected&&token===generation)viewer.innerHTML='<p class="status-error">'+app.esc(error.message)+'</p>';}
  finally{loading=false;if(root.isConnected&&token===generation)refresh.disabled=false;}
 };
 refresh.onclick=load;detail.ontoggle=()=>{if(detail.open&&!loaded)load();};
}
