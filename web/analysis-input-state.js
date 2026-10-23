// One applicability rule for guide visibility and single-run inputs.
export function analysisInputApplies(rule,prefix,host){
 if(rule.any)return rule.any.some(r=>analysisInputApplies(r,prefix,host));
 if(rule.all)return rule.all.every(r=>analysisInputApplies(r,prefix,host));
 const controller=host.getElementById(`${prefix}-${rule.input}-0`);
 return !!controller&&rule.values.some(value=>String(value)===controller.value);
}
export function editableAnalysisInputs(spec,prefix,host,includeInactive=false,applicability=null){
 return (spec?.inputs||[]).filter(e=>e.editable&&(includeInactive||!e.applicableWhen||(applicability?applicability(e.applicableWhen):analysisInputApplies(e.applicableWhen,prefix,host))));
}

// Study controllers may activate configured fields in later cases. Keep valid
// inactive values for that purpose; incomplete inactive drafts can be omitted.
export function collectAnalysisInputs(spec,prefix,host,all=false,includeInactive=false,applicability=null){
 const out=[];
 for(const e of editableAnalysisInputs(spec,prefix,host,includeInactive,applicability)){
  const active=!e.applicableWhen||(applicability?applicability(e.applicableWhen):analysisInputApplies(e.applicableWhen,prefix,host));
  const el=host.getElementById(`${prefix}-${e.name}-${e.index}`);let values;
  try{
   if(!el)throw Error(`${e.name}: input is unavailable.`);
   if(!active&&el.tagName==='SELECT'&&(!el.value.trim()||el.selectedOptions?.[0]?.disabled))continue;
   if(el.dataset.numericList==='true'){
    const text=el.value.trim();values=text?text.split(/[,\s]+/).map(x=>{const value=Number(x);if(!Number.isFinite(value))throw Error(`${e.label||e.name}: enter finite positions separated by commas or spaces.`);return value;}):[];
   }else if(el.dataset.choiceList==='true')values=[...el.selectedOptions].map(o=>o.value);
   else if(el.dataset.vector==='true')values=[[...el.querySelectorAll('[data-coordinate]')].map(input=>{const value=Number(input.value);if(!input.value.trim()||!Number.isFinite(value))throw Error(`${e.name}: enter three finite coordinates.`);return value;})];
   else if(el.dataset.scalar==='true'){
    if(e.type===3)values=[el.value];
    else{
     if(el.tagName==='SELECT'&&!el.value.trim())throw Error(`${e.name}: choose a replacement geometry set.`);
     const value=Number(el.value);if(!el.value.trim()||!Number.isFinite(value)||(e.type===1&&!Number.isInteger(value)))throw Error(`${e.name}: enter a valid ${e.type===1?'integer':'number'}.`);values=[value];
    }
   }else{
    try{values=JSON.parse(el.value);}catch{throw Error(`${e.name}: enter a valid JSON array.`);}
    if(!Array.isArray(values))throw Error(`${e.name}: wrap values in [brackets].`);
   }
  }catch(error){if(includeInactive&&!active)continue;throw error;}
  if(all||JSON.stringify(values)!==JSON.stringify(e.values))out.push({name:e.name,index:e.index,values});
 }
 return out;
}
