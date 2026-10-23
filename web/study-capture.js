// Read every retained axis before changing the draft. A replacement/removal
// may discard one axis's invalid form; unrelated invalid drafts still reject.
export function captureSweepAxes(axes,read,discard=-1){
 const values=axes.map((axis,index)=>index===discard?axis.values:read(axis,index));
 axes.forEach((axis,index)=>{axis.values=values[index];});
}
