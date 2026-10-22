// Copy original saved option records explicitly; references stay in the run form.
export function projectionOptionInputs(spec){
 const entries=structuredClone(spec.guide?.savedProjectionOptions||[]);
 for(const entry of entries){
  const field=spec.inputs.find(e=>e.name===entry.name&&e.index===entry.index);
  if(!field||field.editable===false)throw Error('A saved projection option is unavailable. Review the current analysis inputs.');
  if(field.choices&&entry.values.some(value=>!field.choices.some(c=>c.value===value)))throw Error('A saved option is unavailable for projected-area analysis. Review the geometry targets below; plane and point checks are in Modeling tools → Geometry checks.');
 }
 return entries;
}
