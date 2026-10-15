import {mountMeshViewer} from './mesh-viewer.js?v=20261010-123';
import {drawingMesh} from './structural-preview.js?v=20261010-123';
let cleanup=null,generation=0;
export function disposeFlowPlanePreview(){generation++;if(cleanup){cleanup();cleanup=null;}}
// Original native cutting-plane parameters and undoable setup operations.
export function renderFlowPlanes({app,data:d,helpers:h}){
 const {E,field,select,button,card,params,bind,mutate,val,num}=h;
 const axes=d.flowPlaneAxes.map(c=>[c.value,c.label]);
 document.querySelector('#tool-content').innerHTML=card('Native cutting planes',`<p>Save axis-aligned planes with your aircraft. When enabled, a VSPAERO run produces pressure slices and airflow-plane files at these positions. Open a completed run to inspect the results.</p><p class="native-tip">Positions use native model units. Changing display units does not rescale these positions.</p>${params(d.flowPlaneSettings)}<div class="tool-fields">${field('Plane name','flow-plane-name','Pressure slice','text')}${select('Plane normal','flow-plane-axis',axes,1)}${field('Position (native model units)','flow-plane-position',0)}</div>${button('flow-plane-add','Add cutting plane',true)}<details><summary>Add evenly spaced planes</summary><p>Include both endpoints. Positions use native model units; descending ranges are supported.</p><div class="tool-fields">${field('Series name','flow-series-name','Span cut','text')}${select('Series plane normal','flow-series-axis',axes,1)}${field('Start position (native model units)','flow-series-start',0)}${field('End position (native model units)','flow-series-end',10)}${field('Number of planes','flow-series-count',5)}</div>${button('flow-plane-series','Add plane series')}</details>`)+
 card('Saved planes',d.flowPlanes.length?`<div class="tool-actions"><button id="flow-select-all">Select all</button><button id="flow-select-none">Clear selection</button><button id="flow-delete-selected" disabled>Remove selected planes</button><span id="flow-selection-count" role="status">0 selected</span></div>${d.flowPlanes.map(p=>`<article class="tool-item"><label class="membership-row"><input type="checkbox" data-flow-selected="${E(p.id)}" aria-label="Select ${E(p.name)}"><b>${E(p.name)}</b></label><details><summary>Rename plane</summary><div class="inline-fields">${field('Name for '+p.name,'flow-name-'+p.id,p.name,'text')}<button data-flow-rename="${E(p.id)}">Save name</button></div></details><div class="tool-fields">${params(p.params)}</div><button data-flow-plane-delete="${E(p.id)}">Remove plane</button></article>`).join('')}`:'<p class="empty-state">No cutting planes saved yet.</p>','wide')+card('Cutting-plane preview','<div id="flow-plane-preview"></div>','wide');
 bind('flow-plane-add',()=>mutate({operation:'flow-plane-add',name:val('flow-plane-name'),axis:num('flow-plane-axis'),position:num('flow-plane-position')}));
 bind('flow-plane-series',()=>mutate({operation:'flow-plane-series',name:val('flow-series-name'),axis:num('flow-series-axis'),start:num('flow-series-start'),end:num('flow-series-end'),count:num('flow-series-count')}));
 const host=document.querySelector('#flow-plane-preview'),token=++generation;
 host.innerHTML='<div class="tool-actions"><button data-plane-refresh>Refresh preview</button><button data-plane-download disabled>Download native plane drawings</button></div><div data-plane-viewer>Reading native cutting-plane drawings…</div>';
 const viewer=host.querySelector('[data-plane-viewer]'),download=host.querySelector('[data-plane-download]');
 const load=()=>{const requestRevision=app.model().revision;return app.api('/api/query',{operation:'flow-plane-preview',revision:requestRevision}).then(data=>{
  if(!host.isConnected||token!==generation||app.model().revision!==requestRevision)return;
  if(cleanup){cleanup();cleanup=null;}
  if(!data.parts.some(p=>p.objects.length)){viewer.innerHTML='<p>No visible native cutting planes. Add a plane or turn on Show native cutting plane.</p>';download.disabled=true;return;}
  cleanup=mountMeshViewer(viewer,drawingMesh(data,app.model().components),app.esc);
  download.disabled=false;download.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({...data,revision:requestRevision},null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='native-cutting-plane-drawings.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 }).catch(error=>{if(host.isConnected&&token===generation)viewer.innerHTML='<p>'+E(error.message)+'</p>';});};
 host.querySelector('[data-plane-refresh]').onclick=load;load();
 const selections=()=>[...document.querySelectorAll('[data-flow-selected]')],chosen=()=>selections().filter(el=>el.checked).map(el=>el.dataset.flowSelected);
 const update=()=>{const count=chosen().length;document.querySelector('#flow-delete-selected').disabled=!count;document.querySelector('#flow-selection-count').textContent=count+' selected';};
 for(const el of selections())el.onchange=update;
 bind('flow-select-all',()=>{for(const el of selections())el.checked=true;update();});
 bind('flow-select-none',()=>{for(const el of selections())el.checked=false;update();});
 bind('flow-delete-selected',()=>mutate({operation:'flow-plane-delete-many',ids:chosen()}));
 for(const b of document.querySelectorAll('[data-flow-plane-delete]'))b.onclick=()=>mutate({operation:'flow-plane-delete',id:b.dataset.flowPlaneDelete});
 for(const b of document.querySelectorAll('[data-flow-rename]'))b.onclick=()=>mutate({operation:'flow-plane-rename',id:b.dataset.flowRename,name:val('flow-name-'+b.dataset.flowRename)});
}
