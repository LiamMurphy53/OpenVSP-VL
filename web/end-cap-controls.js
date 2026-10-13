// Native surface caps and profile edge caps have different mode choices.
// Values and constraints come from the official engine's original parameters.
export function endCapPromotedIDs(component,sectionIndex){
 const caps=component.endCaps;if(!caps)return [];
 const edges=component.sections[sectionIndex]?.edgeCapControls||caps.profile||[];
 return [...caps.ends,...edges].flatMap(c=>Object.values(c.fields)).concat(caps.sampling?[caps.sampling]:[]);
}

export function endCapControlsMarkup(component,sectionIndex,{esc,parameterField}){
 const caps=component.endCaps;if(!caps)return '';
 const byID=new Map(component.params.map(p=>[p.id,p]));
 const panel=(cap,key)=>{
  const fields=Object.values(cap.fields).map(id=>byID.get(id)).filter(Boolean),mode=byID.get(cap.fields.mode);
  const editable=fields.filter(p=>p.id!==mode.id&&!p.displayReadOnly&&p.active!==false);
  const fixed=fields.filter(p=>p.id!==mode.id&&(p.displayReadOnly||p.active===false));
  return `<details class="wing-secondary-controls" data-group="cap-${key}" open><summary>${esc(cap.label)}</summary>${parameterField(mode)}${editable.map(parameterField).join('')}${cap.hint?`<p class="native-tip">${esc(cap.hint)}</p>`:''}${cap.unused?`<p class="native-tip">${esc(cap.unused)}</p>`:''}${fixed.length?`<details data-group="cap-${key}-unused"><summary>Values unused or fixed by this shape</summary>${fixed.map(parameterField).join('')}</details>`:''}</details>`;
 };
 const section=component.sections[sectionIndex],edges=section?.edgeCapControls||caps.profile||[];
 const profiles=component.sections.filter(s=>s.edgeCapControls?.length);
 const profilePicker=profiles.length?`<div class="tool-field"><label for="cap-profile-choice">Edge cap profile</label><select id="cap-profile-choice">${component.sections.map((s,i)=>s.edgeCapControls?.length?`<option value="${i}" ${i===sectionIndex?'selected':''}>Surface ${s.surface} · Profile ${s.index}</option>`:'').join('')}</select></div>`:'';
 return `<details class="parameter-group geometry-primary" data-group="end-caps"><summary>End caps</summary><p class="native-tip">Close or shape the native surface ends. Length and offset are scaled factors; display units do not change them.</p>${caps.hints.map(h=>`<p class="native-tip">${esc(h)}</p>`).join('')}${caps.ends.map((cap,i)=>panel(cap,'end-'+i)).join('')}${caps.sampling?`<details class="wing-secondary-controls" data-group="cap-sampling"><summary>Surface sampling</summary>${parameterField(byID.get(caps.sampling))}</details>`:''}${edges.length?`<details class="wing-secondary-controls" data-group="profile-edge-caps"><summary>Profile edge caps</summary><p class="native-tip">Leading and trailing edge shaping changes a profile, separately from the root and tip. Flat preserves the edge without additional shaping. Extended round caps apply to wing and blade ends.</p>${profilePicker}${edges.map((cap,i)=>panel(cap,'profile-'+i)).join('')}</details>`:''}</details>`;
}
