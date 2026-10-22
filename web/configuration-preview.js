export function configurationPreviewMarkup(result,esc){
 const val=x=>x===null?'Unavailable':typeof x==='number'?Number(x.toPrecision(10)):x;
 return `<p>Native evaluation on an isolated aircraft copy. The working aircraft and Undo history are unchanged. Values use native parameter units.</p><p>${result.changes.length} changed, added or removed values. Apply separately to update the aircraft.</p>${result.changes.length?`<div class="curve-table"><table class="result-table"><thead><tr><th>Parameter</th><th>Current</th><th>After applying</th><th>Units</th></tr></thead><tbody>${result.changes.slice(0,200).map(p=>`<tr><td>${esc(p.label)}${p.selected?' · saved input':''}${p.status==='changed'?'':` (${esc(p.status)})`}</td><td>${esc(val(p.before))}</td><td>${esc(val(p.after))}</td><td>${esc(p.unit)}</td></tr>`).join('')}</tbody></table></div>${result.changes.length>200?'<p>First 200 values shown.</p>':''}`:''}<button data-preview-download>Download full preview</button>`;
}
export function bindConfigurationPreviews(root,app,revision){
 for(const button of root.querySelectorAll('[data-preview-configuration]'))button.onclick=async()=>{
  const output=button.parentElement.querySelector('[data-configuration-preview-output]');button.disabled=true;output.textContent='Evaluating with OpenVSP…';
  try{
   const result=await app.api('/api/query',{operation:'configuration-preview',configuration:button.dataset.previewConfiguration,id:button.dataset.id,group:button.dataset.group,setting:button.dataset.setting,revision});
   if(!output.isConnected)return;
   if(app.model().revision!==result.revision){output.textContent='The aircraft changed. Preview this configuration again.';return;}
   output.innerHTML=configurationPreviewMarkup(result,app.esc);
   output.querySelector('[data-preview-download]')?.addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([configurationPreviewPayload(result)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='configuration-preview.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  }catch(error){if(output.isConnected)output.textContent=error.message;}
  finally{if(button.isConnected)button.disabled=false;}
 };
}
export function previewButton(kind,fields,esc){return `<div class="configuration-preview"><button data-preview-configuration="${kind}" ${Object.entries(fields).map(([k,v])=>`data-${k}="${esc(v)}"`).join(' ')}>Preview native changes</button><div data-configuration-preview-output role="status"></div></div>`;}

export function configurationPreviewPayload(result){return JSON.stringify({source:"Official OpenVSP isolated configuration transaction",...result},null,2);}
