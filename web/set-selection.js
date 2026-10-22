// User-set collection IDs move with native set contents. Never infer identity
// from names or membership: both may be identical for different sets.
export const setInputNames=new Set(['Set','GeomSet','ThinGeomSet','ThickGeomSet','DegenSet','SelectedSetIndex','SelectedDegenSetIndex','TargetSet','BoundarySet','CGGeomSet','CGDegenSet']);
export function resolveSetSelection(sets,value,identity){
 if(identity){const set=sets.find(s=>s.identity===identity);return {value:set?String(set.index):'',identity};}
 const set=sets.find(s=>String(s.index)===String(value));
 return {value:set?String(set.index):String(value)==='-1'?'-1':'',identity:set?.identity||''};
}
export function setOptions(sets,esc){return '<option value="-1">None</option>'+sets.map(s=>`<option value="${s.index}" data-set-identity="${esc(s.identity||'')}">${esc(s.name)} (${s.index})</option>`).join('');}
export function restoreSetSelection(el,sets,value,identity,esc){
 const selected=resolveSetSelection(sets,value,identity);
 el.innerHTML=setOptions(sets,esc);el.value=selected.value;
 if(selected.value===''){
  el.dataset.missingSetValue=value;
  el.insertAdjacentHTML('afterbegin',`<option value="" data-set-identity="${esc(selected.identity)}" disabled selected>Choose a replacement geometry set…</option>`);el.value='';
 }else delete el.dataset.missingSetValue;
 return selected.value!=='';
}
export function refreshSetSelections(host,sets,esc){
 for(const el of host.querySelectorAll('select[data-input]')){
  if(el.dataset.prefix?.startsWith('study-')||!setInputNames.has(el.dataset.input))continue;
  restoreSetSelection(el,sets,el.value||el.dataset.missingSetValue||'',el.selectedOptions[0]?.dataset.setIdentity||'',esc);
 }
}
