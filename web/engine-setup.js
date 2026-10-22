// Stage original flowpath inputs so dependent stations and role update together.
const labels={GeomIOType:'Flowpath component',GeomInType:'Modeled inlet geometry',GeomOutType:'Modeled outlet geometry',InletModeType:'Inlet representation',OutletModeType:'Outlet representation'};
const ends=['InletLip','InletFace','OutletLip','OutletFace'];
export function engineSetupMarkup(component,E){
 const fields=component.params.filter(p=>p.rawGroup==='EngineModel');
 if(!fields.length||!['FUSELAGE','STACK'].includes(component.type.toUpperCase()))return '';
 const byName=new Map(fields.map(p=>[p.name,p]));
 const select=(name,label)=>{const p=byName.get(name);return p?`<label class="tool-field">${E(label)}<select data-engine-setting="${name}" aria-label="Setup ${E(label.toLowerCase())}" ${p.userLocked?'disabled':''}>${p.choices.map(c=>`<option value="${c.value}" ${c.value===p.value?'selected':''}>${E(c.label)}</option>`).join('')}</select></label>`:'';};
 const number=(name,label)=>{const p=byName.get(name);return p?`<label class="tool-field">${E(label)}<input type="number" data-engine-setting="${name}" aria-label="Setup ${E(label.toLowerCase())}" value="${p.value}" min="${p.min}" max="${p.max}" step="any" ${p.userLocked?'disabled':''}></label>`:'';};
 return `<details class="parameter-group geometry-primary" data-group="engine-setup"><summary>Configure flowpath</summary><p class="native-tip">Set the role and station locations, then apply them together. Locations refer to this body’s existing sections.</p><div class="tool-fields">${Object.entries(labels).map(([n,l])=>select(n,l)).join('')}</div>${ends.map(end=>{const label=end.replace(/(Lip|Face)$/,' $1').toLowerCase();return `<fieldset data-engine-end="${end}"><legend>${E(label)}</legend>${select(end+'Mode',label+' basis')}${select(end+'Index',label+' section')}${number(end+'U',label+' U fraction (0–1)')}</fieldset>`;}).join('')}<p class="native-tip">Section and U inputs are alternatives. Distinct inlet/outlet stations are required when enabling both; coincident default stations can crash the installed engine. Additional native flowpath settings are in the properties below.</p><button data-engine-apply>Apply flowpath setup</button><p data-engine-status role="status"></p></details>`;
}
export function engineSetupRequest(host,component){
 const settings={};
 for(const input of host.querySelectorAll('[data-engine-setting]')){
  if(input.disabled)continue;
  if(!input.value.trim()||!Number.isFinite(Number(input.value)))throw Error('Enter finite flowpath values.');
  settings[input.dataset.engineSetting]=Number(input.value);
 }
 return {operation:'engine-configure',geom:component.id,settings};
}
export function bindEngineSetup(host,component,mutate){
 const button=host.querySelector('[data-engine-apply]');if(!button)return;
 const locked=new Set(component.params.filter(p=>p.userLocked).map(p=>p.name));
 const update=()=>{for(const end of ends){
  const mode=Number(host.querySelector(`[data-engine-setting="${end}Mode"]`).value);
  host.querySelector(`[data-engine-setting="${end}Index"]`).disabled=locked.has(end+'Index')||mode!==0;
  host.querySelector(`[data-engine-setting="${end}U"]`).disabled=locked.has(end+'U')||mode!==1;
 }};
 for(const end of ends)host.querySelector(`[data-engine-setting="${end}Mode"]`).onchange=update;
 update();
 button.onclick=()=>{try{return mutate(engineSetupRequest(host,component));}catch(error){host.querySelector('[data-engine-status]').textContent=error.message;}};
}
