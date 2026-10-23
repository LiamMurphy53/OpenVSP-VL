// Replace sampled coordinates only when the viewer's controls/topology still
// describe the new native geometry. Other changes need a fresh viewer.
export function canReplaceGeometry(previous,next){
 if(!previous.geometryPreview||!next.geometryPreview||previous.fields?.length||next.fields?.length)return false;
 if(previous.nodes.length!==next.nodes.length||!next.nodes.every(p=>p.length===3&&p.every(Number.isFinite)))return false;
 const presentation=mesh=>Object.fromEntries(Object.entries(mesh).filter(([key])=>!['nodes','nodeIDs'].includes(key)));
 return JSON.stringify(presentation(previous))===JSON.stringify(presentation(next));
}
