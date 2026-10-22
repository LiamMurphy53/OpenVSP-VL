import {setInputNames} from './set-selection.js?v=20261022-cg';
// Reuse native recorded values. Set identities distinguish moved/deleted sets
// from a new occupant of the same numeric slot.
export function runInputDraft(spec,inputs,prefix,host,job){
 const draft=[];
 for(const saved of inputs||[]){
  const e=spec?.inputs.find(e=>e.name===saved.name&&e.index===(saved.index??0)&&(saved.type===undefined||e.type===saved.type));
  if(!e)continue;
  const el=host.querySelector(`#${prefix}-${e.name}-${e.index}`);if(!el)continue;
  let value;
  if(el.dataset.numericList==='true')value=saved.values.join(', ');
  else if(el.dataset.vector==='true'||el.dataset.choiceList==='true')value=el.dataset.vector==='true'?saved.values[0].map(String):saved.values;
  else if(el.dataset.scalar==='true')value=e.name.endsWith('FileName')?String(saved.values[0]).split(/[\\/]/).at(-1):String(saved.values[0]);
  else value=JSON.stringify(saved.values);
  const identity=setInputNames.has(e.name)&&e.type===1&&saved.values.length===1&&saved.values[0]>=3?(job.setIdentities?.[saved.values[0]]||`untracked:${job.id}:${saved.values[0]}`):undefined;
  draft.push({name:e.name,index:e.index,value,...(identity?{setIdentity:identity}:{})});
 }
 return draft;
}
