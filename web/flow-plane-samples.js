// Export the decoder's complete nodal samples, without display rounding or cell
// averaging. Speed is the decoder's vector magnitude, not another solver field.
const csvCell=value=>{const text=String(value);return /[",\r\n]/.test(text)?'"'+text.replaceAll('"','""')+'"':text;};
export function flowPlaneCSV(mesh){
 const fields=['U','V','W','Cp','Speed'].map(name=>mesh.fields.find(f=>f.name===name)?.nodeValues);
 const count=mesh.nodes.length;
 if(mesh.nodeIDs?.length!==count||fields.some(values=>values?.length!==count))throw Error('The flow plane has incomplete nodal sample columns.');
 return 'NodeID,X,Y,Z,U,V,W,Cp,Speed\r\n'+mesh.nodes.map((point,i)=>[mesh.nodeIDs[i],...point,...fields.map(values=>values[i])].map(csvCell).join(',')).join('\r\n')+'\r\n';
}
export function flowPlaneHeader(mesh){
 const axis=({1:'X',2:'Y',3:'Z'})[mesh.direction]||String(mesh.direction);
 return `${axis} = ${mesh.location} · Native reference speed (Vref): ${mesh.referenceSpeed}${Number.isFinite(mesh.solverVelocityScale)?' · Native solver velocity scale (Vmax): '+mesh.solverVelocityScale:''}. Coordinates use native model length units. X/Y/Z velocities and their magnitude use native length/s; Cp is dimensionless. Colours show cell averages; CSV retains every original node sample. Speed is the magnitude of the saved velocity vector.`;
}
