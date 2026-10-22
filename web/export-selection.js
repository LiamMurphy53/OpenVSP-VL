import {resolveSetSelection} from './set-selection.js?v=20261021';
// Export drafts follow native set identities, including duplicate names and Undo.
export function reconcileExportDraft(draft,sets){
 const missing=[];
 for(const key of ['set','thin']){
  const selected=resolveSetSelection(sets,draft[key],draft[key+'Identity']);
  draft[key+'Identity']=selected.identity;
  if(selected.value==='')missing.push(key);
  else draft[key]=Number(selected.value);
 }
 return missing;
}
export function exportReferenceChoices(choices,value,label){
 return value&&!choices.some(([id])=>String(id)===String(value))?[[value,'Unavailable '+label+' — choose a replacement'],...choices]:choices;
}
export function selectExportSet(draft,key,value,sets){
 draft[key]=Number(value);draft[key+'Identity']=sets.find(s=>s.index===Number(value))?.identity||'';
}
export function validateExportDraft(draft,sets,components,data){
 if(reconcileExportDraft(draft,sets).length)throw Error('Choose replacements for unavailable export geometry sets.');
 if(draft.mode&&!data.modes.some(m=>m.id===draft.mode))throw Error('Choose a replacement configuration mode or use geometry sets.');
 if(draft.format==='BEM'&&!components.some(c=>c.id===draft.prop&&['PROP','PROPELLER'].includes(c.type.toUpperCase())))throw Error('Choose an available propeller for BEM export.');
 if(draft.format.endsWith('_STRUCTURE')&&!data.structures.some(s=>s.id===draft.structure))throw Error('Choose an available structure for CAD export.');
}
