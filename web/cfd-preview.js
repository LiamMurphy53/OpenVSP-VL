import {mountMeshViewer} from './mesh-viewer.js?v=20261010-123';
import {drawingMesh} from './structural-preview.js?v=20261010-123';
let cleanup=null,generation=0;
export function disposeCfdPreview(){generation++;if(cleanup){cleanup();cleanup=null;}}
export function mountCfdPreview(host,component,app){
 disposeCfdPreview();if(!host||!component)return;
 const token=generation,revision=app.model().revision;
 host.innerHTML='<div class="tool-actions"><button data-cfd-refresh>Refresh source preview</button><button data-cfd-download disabled>Download native source drawings</button></div><div data-cfd-viewer><p>Reading native refinement-source drawings…</p></div>';
 const viewer=host.querySelector('[data-cfd-viewer]'),download=host.querySelector('[data-cfd-download]');
 host.querySelector('[data-cfd-refresh]').onclick=()=>mountCfdPreview(host,component,app);
 app.api('/api/query',{operation:'cfd-source-preview',geom:component.id,revision}).then(data=>{
  if(!host.isConnected||app.model().revision!==revision||token!==generation)return;
  const mesh=drawingMesh(data,component);
  if(!data.parts.some(p=>p.objects.length)){viewer.innerHTML='<p>Add a refinement source to see its native influence outline on this component.</p>';return;}
  cleanup=mountMeshViewer(viewer,mesh,app.esc);
  download.disabled=false;download.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({...data,revision},null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='native-cfd-source-drawings.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 }).catch(error=>{if(host.isConnected&&token===generation)viewer.innerHTML='<p class="status-error">'+app.esc(error.message)+'</p>';});
}
