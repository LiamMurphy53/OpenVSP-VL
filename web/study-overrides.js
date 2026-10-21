const key=e=>`${e.name}|${e.index??0}`;
export function stepInputOverrides(stages,axes,specs){
 const out=[];
 stages.forEach((stage,i)=>{
  const spec=specs[i];if(!spec)return;
  for(const scope of ['inputs','geometryInputs']){
   const fields=scope==='inputs'?spec.inputs:spec.geometryInputs||spec.geometrySchema?.inputs||[];
   for(const field of fields||[]){
    const axis=axes.find(a=>a.kind==='parameter'&&a.id===field.nativeParameter);if(!axis)continue;
    const fixed=(stage[scope]||[]).find(e=>key(e)===key(field));
    const sweeps=axes.filter(a=>a.kind===(scope==='inputs'?'input':'geometryInput')&&a.stage===i&&key(a)===key(field)&&!a.member);
    if(!fixed&&!sweeps.length)continue;
    out.push({stage:i,scope,name:field.name,index:field.index??0,label:(scope==='geometryInputs'?'Geometry preparation / ':'')+(field.label||field.name),parameter:axis.id,defaultValues:axis.values,values:fixed?.values||field.values,choices:field.choices||axis.choices,inputSweep:!!sweeps.length});
   }
  }
 });
 return out;
}
export function useSweptDefault(draft,item){
 const stage=draft.stages[item.stage],k=key(item);
 stage[item.scope]=(stage[item.scope]||[]).filter(e=>key(e)!==k);
 stage.followDefaults=[...(stage.followDefaults||[]).filter(e=>e.scope!==item.scope||key(e)!==k),{scope:item.scope,name:item.name,index:item.index}];
 draft.axes=draft.axes.filter(a=>!(a.kind===(item.scope==='inputs'?'input':'geometryInput')&&a.stage===item.stage&&key(a)===k&&!a.member));
}
export function useAllSweptDefaults(draft,items){for(const item of items)useSweptDefault(draft,item);}
export function omitFollowedDefaults(stage,scope,inputs){return inputs.filter(e=>!(stage.followDefaults||[]).some(f=>f.scope===scope&&key(f)===key(e)));}
export function overridesMarkup(items,esc,dirty){
 const value=(item,x)=>item.choices?.find(c=>c.value===x)?.label??JSON.stringify(x);
 return items.length?`<section id="study-input-overrides" class="tool-card" ${dirty?'hidden':''}><h2>Explicit inputs for swept defaults</h2><p>These step inputs are set separately from the aircraft settings you are sweeping.</p>${items.length>1?`<button data-study-use-all-defaults>Use swept defaults in all listed inputs${items.some(item=>item.inputSweep)?' and remove separate input sweeps':''}</button>`:''}${items.map((item,i)=>`<article class="tool-item"><h3>Step ${item.stage+1} · ${esc(item.label)}</h3><p>Swept aircraft default: ${esc(item.defaultValues.map(x=>value(item,x)).join(', '))}.<br>Step input: ${item.inputSweep?'a separate input sweep':esc(item.values.map(x=>value(item,x)).join(', '))}.</p><button data-study-use-default="${i}">Use swept default${item.inputSweep?' and remove separate input sweep':''}</button></article>`).join('')}</section>`:'';
}
export function followingSpec(spec,stage,scope){
 return {...spec,inputs:spec.inputs.map(e=>(stage.followDefaults||[]).some(f=>f.scope===scope&&key(f)===key(e))?{...e,editable:false}:e)};
}
