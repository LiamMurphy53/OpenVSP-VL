import {displayValue,nativeValue,unitSuffix} from './display-units.js?v=20261010-123';
const continuityChoices=[[0,'C0 — position'],[1,'C1 — tangent'],[2,'C2 — curvature']];
export function skinningMarkup(component,section,{esc,parameterField}){
 const controls=section?.skinControls;if(!controls)return '';
 const byID=new Map(component.params.map(p=>[p.id,p]));
 const field=(id,label,choices)=>{const p=byID.get(id),description=p.description==='Default Description'?(p.name.endsWith('Set')?'Manual constraints use the values below; automatic constraints follow the body geometry.':p.name.endsWith('Eq')?'Couple the after-side value to the before-side value.':p.name.endsWith('Angle')?'Set the direction in which the skin meets this section.':p.name.endsWith('Strength')?'Set the native tangent magnitude.':p.name.endsWith('Slew')?'Set OpenVSP’s tangent slew angle.':'Set the native curvature constraint.'):p.description;return parameterField({...p,label,description,...(choices?{choices}:{})});};
 const flags=(items,manual=false)=>items.map(p=>field(p.parameter,p.label,manual?[[0,'Automatic'],[1,'Manual']]:undefined)).join('');
 const direction=(d)=>`<div class="skin-direction"><h3>${esc(d.label)} of profile</h3>${d.metrics.map(m=>`<details class="wing-secondary-controls" data-group="skin-${d.label}-${m.label.replaceAll(' ','-')}" ${m.label==='Tangent angle'?'open':''}><summary>${esc(m.label)}</summary>${field(m.before,`${d.label} before ${m.label.toLowerCase()}`)}${field(m.after,`${d.label} after ${m.label.toLowerCase()}`)}${field(m.equal,`${d.label} equal ${m.label.toLowerCase()}`)}</details>`).join('')}</div>`;
 return `<details class="parameter-group geometry-primary skin-editor" data-group="body-skin"><summary>Section blending</summary><p class="native-tip">Control how the skin approaches and leaves this profile. Automatic values come from OpenVSP; enable manual tangent or curvature constraints to shape the blend.</p>${controls.endpoint?`<p class="native-tip">${esc(controls.endpoint)}</p>`:''}${field(controls.continuity,'Section continuity',continuityChoices)}<div class="skin-primary-fields">${flags(controls.manual,true)}</div><details class="wing-secondary-controls" data-group="skin-symmetry" open><summary>Blending symmetry</summary>${flags(controls.symmetry)}</details>${direction(controls.directions[0])}<details class="wing-secondary-controls" data-group="skin-other-directions"><summary>Right, bottom & left directions</summary>${controls.directions.slice(1).map(direction).join('')}</details><p class="native-tip">Angle and slew use your display angle units. Strength and curvature retain OpenVSP’s native conventions. Equality and continuity can make the after-side values follow the before side.</p><div class="tool-actions"><button data-skin-reset>Reset this section’s blending</button><button data-skin-reset-all>Reset all body blending</button></div></details>`;
}
export function skinningField(p,esc){
 const value=Number(displayValue(p.value,p.dimension).toPrecision(12)),locked=p.active===false||p.displayReadOnly;
 const choices=p.choices||(p.type===2?[[0,'Off'],[1,'On']]:null);
 return `<label class="tool-field" title="${esc(p.readOnlyReason||p.description)}">${esc(p.label)}${p.dimension?` (${esc(unitSuffix(p.dimension))})`:''}${locked?' · calculated':''}${choices?`<select aria-label="${esc(p.label)}" data-skin-param="${esc(p.id)}" ${locked?'disabled':''}>${choices.map(([v,label])=>`<option value="${v}" ${v===p.value?'selected':''}>${esc(label)}</option>`).join('')}</select>`:`<input aria-label="${esc(p.label)}" data-skin-param="${esc(p.id)}" type="number" step="any" min="${displayValue(p.min,p.dimension)}" max="${displayValue(p.max,p.dimension)}" value="${value}" ${locked?'readonly':''}>`}<small>${esc(p.readOnlyReason||p.description)}</small></label>`;
}
export function bindSkinning(host,component,section,{mutate,toast}){
 if(!section?.skinControls)return;
 const common={geom:component.id,surface:section.surface,index:section.index};
 host.querySelector('[data-skin-reset]').onclick=()=>mutate({...common,operation:'section-skin-reset'});
 host.querySelector('[data-skin-reset-all]').onclick=()=>mutate({geom:component.id,operation:'body-skin-reset-all'});
 for(const input of host.querySelectorAll('[data-skin-param]')){
  const p=component.params.find(p=>p.id===input.dataset.skinParam),original=Number(displayValue(p.value,p.dimension).toPrecision(12));let pending=false;
  const commit=async()=>{if(pending||p.active===false||p.displayReadOnly)return;if(!input.value.trim()||!Number.isFinite(Number(input.value))){toast('Enter a finite number.');input.value=original;return;}if(Number(input.value)===original)return;const value=nativeValue(Number(input.value),p.dimension);if(value<p.min||value>p.max){toast('Use a value within the native limits.');input.value=original;return;}pending=true;try{await mutate({operation:'parameter',id:p.id,value});}finally{pending=false;}};
  input.onchange=commit;input.onblur=commit;input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();input.blur();}};
 }
}
