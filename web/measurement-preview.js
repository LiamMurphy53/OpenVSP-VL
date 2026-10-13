import {mountMeshViewer} from './mesh-viewer.js?v=20261010-123';
import {drawingMesh} from './structural-preview.js?v=20261010-123';
let cleanup=null,generation=0;
export function disposeMeasurementPreview(){generation++;if(cleanup){cleanup();cleanup=null;}}
export function mountMeasurementPreview(host,app,model){
 disposeMeasurementPreview();const token=generation,revision=model.revision;host.innerHTML='<div class="tool-actions"><button data-measurement-preview-refresh>Refresh measurements</button><button data-measurement-preview-download disabled>Download native measurement drawings</button></div><div data-measurement-preview-viewer><p>Loading native measurement drawings…</p></div>';
 const viewer=host.querySelector('[data-measurement-preview-viewer]'),download=host.querySelector('[data-measurement-preview-download]');host.querySelector('[data-measurement-preview-refresh]').onclick=()=>mountMeasurementPreview(host,app,app.model());
 app.api('/api/query',{operation:'measurement-preview',revision}).then(data=>{
  if(token!==generation||!host.isConnected||app.model().revision!==revision)return;
  if(!data.parts.length){viewer.innerHTML='<p>Add a ruler, probe or protractor to inspect its native anchors.</p>';return;}
  const mesh=drawingMesh(data,model.components);for(const group of mesh.groups){const part=data.parts.find(p=>p.index+1===group.id);if(part&&part.objects.every(o=>!o.visible))group.initiallyHidden=true;}
  cleanup=mountMeshViewer(viewer,mesh,app.esc);download.disabled=false;download.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({...data,revision},null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='native-measurement-drawings.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 }).catch(error=>{if(token===generation&&host.isConnected)viewer.innerHTML='<p>'+app.esc(error.message)+'</p>';});
}
