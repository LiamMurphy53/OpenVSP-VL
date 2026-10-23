// Read every retained axis before changing the draft. A replacement/removal
// may discard one axis's invalid form. Local rearrangements can retain the last
// valid values while raw DOM drafts survive separately; save stays strict.
export function captureSweepAxes(axes,read,discard=-1,draftOnly=false){
 const values=axes.map((axis,index)=>{if(index===discard)return axis.values;try{return read(axis,index);}catch(error){if(!draftOnly)throw error;return axis.values;}});
 axes.forEach((axis,index)=>{axis.values=values[index];});
}
