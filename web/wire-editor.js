export function wireEditor(component,esc){
 if(!component.wireSettings)return '';
 const fields=component.wireSettings.fields,groups=[...new Set(fields.map(p=>p.section))];
 const points=component.surfaces.reduce((n,s)=>n+s.points.length,0),segments=component.paths?.length||0;
 return `<section class="wire-editor"><h3>Imported wire geometry</h3><p class="native-tip">${points} native surface points · ${segments} line segments. Use X Form below to position, rotate, and resize with Scale.</p><p class="native-tip">I and J follow the imported grid. Trimming removes rows or columns; sampling keeps every chosen stride and the last boundary. OpenVSP applies orientation, trimming, sampling, then patches.</p>${groups.map(group=>`<details class="parameter-group" ${group==='Classification'?'open':''}><summary>${esc(group)}</summary>${fields.filter(p=>p.section===group).map(p=>`<div class="field"><label for="wire-${p.name}">${esc(p.label)}</label>${p.choices?`<select id="wire-${p.name}" data-wire-setting="${p.name}">${p.choices.map(c=>`<option value="${c.value}" ${c.value===p.value?'selected':''}>${esc(c.label)}</option>`).join('')}</select>`:`<input id="wire-${p.name}" data-wire-setting="${p.name}" type="number" step="1" min="${p.min}" max="${p.max}" value="${p.value}">`}<small>${esc(p.help)}</small></div>`).join('')}</details>`).join('')}<button id="apply-wire-settings" class="primary">Apply wire settings</button><p class="native-tip">Apply saves the complete setting group. Undo restores the previous geometry.</p></section>`;
}

export function bindWireEditor(component,{transact,toast}){
 const button=document.getElementById('apply-wire-settings');if(!button)return;
 button.onclick=async()=>{
  try{
   const values={};
   for(const p of component.wireSettings.fields){
    const el=document.getElementById('wire-'+p.name),value=Number(el.value);
    if(!el.value.trim()||!Number.isFinite(value)||!Number.isInteger(value))throw Error(p.label+': enter a whole number.');
    if(value<p.min||value>p.max)throw Error(p.label+': value is outside the native limits.');
    values[p.name]=value;
   }
   await transact('/api/mutate',{operation:'wire-settings',geom:component.id,values});
  }catch(e){toast(e.message);}
 };
}
