const members=spec=>spec?.name==='FeaAssemblyMesh'?spec.guide?.memberSizing||[]:[];
export function assemblySizingMarkup(spec,esc){
 if(!members(spec).length)return '';
 return `${(spec.guide?.connectionIssues||[]).map(i=>`<p class="status-error">${esc(i.message)} Repair the endpoints in Modeling tools → Assemblies.</p>`).join('')}<fieldset class="guide-fields"><legend>Assembly mesh settings</legend><label>Settings scope<select id="assembly-sizing-method"><option value="shared">Same settings for every member</option><option value="individual">Separate settings for each member</option></select></label><div id="assembly-member-sizing" hidden><p class="native-tip">Each member uses its own sizing, element and solver-deck settings and native limits. These changes apply to this saved run.</p>${members(spec).map(m=>`<fieldset class="guide-fields"><legend>${esc(m.name)} · ${esc(m.component)}</legend>${m.inputs.map(e=>`<div class="analysis-input"><label>${esc(e.label)}${e.choices?`<select data-member-sizing="${esc(m.id)}" data-sizing-name="${esc(e.name)}">${e.choices.map(c=>`<option value="${c.value}" ${c.value===e.values[0]?'selected':''}>${esc(c.label)}</option>`).join('')}</select>`:`<div class="number-wrap"><input type="number" step="any" min="${e.min}" max="${e.max}" value="${e.values[0]}" data-member-sizing="${esc(m.id)}" data-sizing-name="${esc(e.name)}"></div>`}</label></div>`).join('')}</fieldset>`).join('')}</div></fieldset>`;
}
export function bindAssemblySizing(spec){
 const method=document.querySelector('#assembly-sizing-method');if(!method)return;
 const refresh=()=>{for(const m of members(spec))for(const e of m.inputs){if(!e.applicableWhen)continue;const element=document.querySelector(`[data-member-sizing="${m.id}"][data-sizing-name="${e.name}"]`),controller=document.querySelector(`[data-member-sizing="${m.id}"][data-sizing-name="${e.applicableWhen.input}"]`);if(element&&controller)element.closest('.analysis-input').hidden=!e.applicableWhen.values.some(v=>String(v)===controller.value);}};
 for(const m of members(spec))for(const name of new Set(m.inputs.filter(e=>e.applicableWhen).map(e=>e.applicableWhen.input)))document.querySelector(`[data-member-sizing="${m.id}"][data-sizing-name="${name}"]`)?.addEventListener('change',refresh);
 refresh();
 const update=()=>{const individual=method.value==='individual';document.querySelector('#assembly-member-sizing').hidden=!individual;document.querySelectorAll('#analysis-inputs [id^="analysis-"]').forEach(el=>{if(['INPUT','SELECT','TEXTAREA'].includes(el.tagName))el.disabled=individual;});};
 method.onchange=update;update();
}
export function assemblySizingRequest(spec){
 if(!members(spec).length||document.querySelector('#assembly-sizing-method')?.value!=='individual')return {};
 return {inputs:[],memberInputs:members(spec).map(m=>({id:m.id,inputs:m.inputs.map(e=>{
 const el=document.querySelector(`[data-member-sizing="${m.id}"][data-sizing-name="${e.name}"]`),x=Number(el.value);
 if(!el.value.trim()||!Number.isFinite(x))throw Error(`${m.name}: enter a finite ${e.label.toLowerCase()}.`);
 return {name:e.name,index:0,values:[x]};})}))};
}
export function restoreAssemblySizing(spec,saved){
 if(!members(spec).length||!saved)return;
 if(saved.length!==members(spec).length||saved.some(m=>!members(spec).some(x=>x.id===m.id)))throw Error('The saved assembly members have changed. Open the run’s aircraft to recover its sizing.');
 for(const m of saved)for(const [n,x] of Object.entries(m.values)){const el=document.querySelector(`[data-member-sizing="${m.id}"][data-sizing-name="${n}"]`);if(el)el.value=String(x);}
 document.querySelector('#assembly-sizing-method').value='individual';bindAssemblySizing(spec);
}
