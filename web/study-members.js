const clone=x=>structuredClone(x);
export const memberPrefix=(stage,index)=>`study-member-${stage}-${index}`;
export function memberSpecs(spec,stage){
 if(stage.name!=='FeaAssemblyMesh')return [];
 return (spec.guide?.memberSizing||[]).map(member=>{
  const inputs=clone(member.inputs),overrides=[...(stage.memberInputs?.find(x=>x.id===member.id)?.inputs||[]),...(stage.inputs||[])];
  for(const entry of overrides){const field=inputs.find(x=>x.name===entry.name&&x.index===(entry.index??0));if(field)field.values=clone(entry.values);}
  return {...member,spec:{...spec,inputs,guide:{...spec.guide,note:`Saved mesh settings for ${member.name}.`,memberSizing:undefined}}};
 });
}
export function separateMembers(spec,stage){
 stage.memberInputs=memberSpecs(spec,stage).map(m=>({id:m.id,inputs:m.spec.inputs.filter(e=>e.editable!==false).map(e=>({name:e.name,index:e.index,values:clone(e.values)}))}));
 stage.inputs=[];
}
export function shareFirstMember(spec,stage){const first=memberSpecs(spec,stage)[0];if(!first)return;stage.inputs=first.spec.inputs.filter(e=>e.editable!==false).map(e=>({name:e.name,index:e.index,values:clone(e.values)}));delete stage.memberInputs;stage.freezeInputs=true;}
export function memberMarkup(spec,stage,index,{esc,inputMarkup}){
 if(stage.name!=='FeaAssemblyMesh')return '';
 if(!stage.memberInputs?.length)return '<button type="button" data-study-separate-members="'+index+'">Edit settings separately for each member</button>';
 return `<section class="study-member-settings"><h3>Separate member settings</h3><button type="button" data-study-share-members="${index}">Use first member’s settings for all</button><p class="native-tip">Displayed settings are saved explicitly for each member. Member input sweeps replace that member’s saved values; a shared input sweep applies to every member.</p>${memberSpecs(spec,stage).map((m,j)=>`<details><summary>${esc(m.name)} · ${esc(m.component)}</summary>${inputMarkup(m.spec,memberPrefix(index,j))}</details>`).join('')}</section>`;
}
