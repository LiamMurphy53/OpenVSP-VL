// Saved property IDs, filtered by the native shell/beam property model.
export const elementFields=['CreateBeamElements','MarkDelShellElements','KeepDelShellElements','Orientation','IncludedElements','FeaPropertyIndex','CapFeaPropertyIndex'];
export function partProperties(part,data,h,region=false){
 if(!region&&(part.fixedPoint||part.type===data.partTypes.FEA_TRIM))return '';
 const {E}=h;
 const order=['MarkDelShellElements','KeepDelShellElements','CreateBeamElements','Orientation'];
 const fields=order.flatMap(name=>part.params.filter(p=>p.name===name));
 return `<section class="element-properties"><h4>Elements and properties</h4>${h.paramDetails(fields,['MarkDelShellElements','KeepDelShellElements','CreateBeamElements','Orientation'])}<div class="tool-fields">${[['shell','Shell property','FeaPropertyID','Shell'],['beam','Beam property','CapFeaPropertyID','Beam']].map(([role,label,key,model])=>{
  const saved=part.propertyReferences?.[key]||'',props=data.properties.filter(p=>{const f=p.params.find(f=>f.name==='FeaPropertyType');return f?.choices?.find(c=>c.value===f.value)?.label===model;}),missing=saved&&!props.some(p=>p.id===saved);
  return `<label class="tool-field">${region?'Region '+label.toLowerCase():label}<select data-${region?'region':'part'}-property="${E(part.id)}" data-property-role="${role}"><option value="" disabled ${!saved?'selected':''}>No saved assignment</option>${props.map(p=>`<option value="${E(p.id)}" ${saved===p.id?'selected':''}>${E(p.name)}</option>`).join('')}${missing?`<option value="${E(saved)}" selected>Unavailable or incompatible saved property</option>`:''}</select></label>`;
 }).join('')}</div><p class="native-tip">Beam properties take effect when beam elements are enabled. Deleted shell elements do not use the shell assignment. Material orientation is evaluated by OpenVSP on the chosen surface.</p></section>`;
}
