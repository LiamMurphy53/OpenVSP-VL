import {mountMeshViewer} from './mesh-viewer.js?v=20261010-123';
import {drawingMesh} from './structural-preview.js?v=20261010-123';
let cleanup=null,generation=0;
export function disposeCfdDomain(){generation++;if(cleanup){cleanup();cleanup=null;}}
export function domainEditor(model,helpers){
 const {select,field,button}=helpers,c=model.tools.cfdDomain,p=Object.fromEntries(c.params.map(p=>[p.name,p])),v=n=>p[n].value;
 const choice=(name,label,items)=>select(label,'cfd-'+name,items,v(name));
 const flag=(name,label)=>choice(name,label,[[0,'Off'],[1,'On']]);
 const number=(name,label)=>field(label,'cfd-'+name,v(name));
 const sets=name=>[[-1,'None'],...model.tools.sets.map(s=>[s.index,s.name])].filter(([i])=>i>=p[name].min&&i<=p[name].max);
 return `<p>Choose the geometry, outer boundary and symmetry settings OpenVSP will use for CFD meshing. Sizes and locations use the aircraft’s length units.</p><div class="tool-fields">${flag('UseMode','Use a named mode')}${select('CFD mode','cfd-mode',[['','Choose a mode'],...model.tools.modes.map(m=>[m.id,m.name])],c.mode)}${choice('Set','Normal geometry set',sets('Set'))}${choice('DegenSet','Degenerate geometry set',sets('DegenSet'))}${flag('FarMesh','Mesh an outer boundary')}${choice('FarComp','Boundary shape',[[0,'Box'],[1,'Aircraft component']])}${select('Far-field component','cfd-farGeom',[['','Choose a component'],...model.components.map(g=>[g.id,g.name])],c.farGeom)}${choice('FarAbsSize','Box sizing',[[0,'Relative to aircraft bounds'],[1,'Absolute dimensions']])}${number('FarXScale','Length scale (X)')}${number('FarYScale','Width scale (Y)')}${number('FarZScale','Height scale (Z)')}${number('FarLength','Box length (X)')}${number('FarWidth','Box width (Y)')}${number('FarHeight','Box height (Z)')}${choice('FarManualLoc','Box placement',[[0,'Centered on aircraft bounds'],[1,'Manual location']])}${number('FarXLocation','Upstream face X')}${number('FarYLocation','Center Y')}${number('FarZLocation','Center Z')}${flag('HalfMesh','Keep the positive-Y half')}${flag('SymmetrySplitting','Split the symmetry boundary')}</div><p class="native-tip">A mode supplies its own geometry sets and applies its saved presets during meshing and preview. Manual X places the upstream box face; Y and Z place its center. A component boundary uses that component’s actual surface.</p>${button('save-cfd-domain','Apply domain settings',true)}`;
}
export function bindDomainEditor(model,helpers){
 const {bind,mutate,num,val}=helpers,c=model.tools.cfdDomain;
 const input=n=>document.getElementById('cfd-'+n);
 for(const p of c.params){const el=input(p.name);if(el?.type==='number'){el.min=p.min;el.max=p.max;el.step=p.type===1?'1':'any';}}
 const update=()=>{
  const mode=Number(input('UseMode').value),far=Number(input('FarMesh').value),component=Number(input('FarComp').value),absolute=Number(input('FarAbsSize').value),manual=Number(input('FarManualLoc').value);
  const enabled={mode:mode,Set:!mode,DegenSet:!mode,FarComp:far,farGeom:far&&component,FarAbsSize:far&&!component,FarManualLoc:far&&!component,SymmetrySplitting:!component};
  for(const n of ['FarXScale','FarYScale','FarZScale'])enabled[n]=far&&!component&&!absolute;
  for(const n of ['FarLength','FarWidth','FarHeight'])enabled[n]=far&&!component&&absolute;
  for(const n of ['FarXLocation','FarYLocation','FarZLocation'])enabled[n]=far&&!component&&manual;
  for(const [n,on] of Object.entries(enabled))input(n).disabled=!on;
 };
 for(const n of ['UseMode','FarMesh','FarComp','FarAbsSize','FarManualLoc'])input(n).onchange=update;
 update();
 bind('save-cfd-domain',()=>mutate({operation:'cfd-domain-settings',values:Object.fromEntries(c.params.filter(p=>!input(p.name).disabled).map(p=>[p.name,num('cfd-'+p.name)])),mode:val('cfd-mode'),farGeom:val('cfd-farGeom')}));
}
export function mountCfdDomain(host,app){
 disposeCfdDomain();if(!host)return;
 const token=generation,revision=app.model().revision;
 host.innerHTML='<div class="tool-actions"><button data-domain-refresh>Refresh domain and wakes</button><button data-domain-download disabled>Download native domain drawings</button></div><div data-domain-viewer><p>Reading native domain and wake drawings…</p></div>';
 const viewer=host.querySelector('[data-domain-viewer]'),download=host.querySelector('[data-domain-download]');
 host.querySelector('[data-domain-refresh]').onclick=()=>mountCfdDomain(host,app);
 app.api('/api/query',{operation:'cfd-domain-preview',revision}).then(data=>{
  if(!host.isConnected||app.model().revision!==revision||token!==generation)return;
  cleanup=mountMeshViewer(viewer,drawingMesh(data,data.context),app.esc);
  download.disabled=false;download.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({...data,revision},null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='native-cfd-domain-drawings.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 }).catch(error=>{if(host.isConnected&&token===generation)viewer.innerHTML='<p class="status-error">'+app.esc(error.message)+'</p>';});
}
