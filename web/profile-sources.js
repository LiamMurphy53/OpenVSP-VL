// Every choice is an original native curve owner, copied within one transaction.
export function profileSources(components,data,exclude=''){
 const name=g=>components.find(c=>c.id===g)?.name||g;
 const choice=(source,label)=>[JSON.stringify(source),label];
 return [...components.flatMap(g=>g.sections.map(s=>choice({kind:'section',geom:g.id,surface:s.surface,index:s.index},`${g.name} · ${g.id.slice(0,6)} · surface ${s.surface} · section ${s.index}`))),...(data.bodiesOfRevolution||[]).filter(b=>b.id!==exclude).map(b=>choice({kind:'bor',geom:b.id},`${name(b.id)} · revolution profile`)),...(data.auxiliary||[]).filter(a=>a.id!==exclude&&a.controls.profile).map(a=>choice({kind:'auxiliary',geom:a.id},`${name(a.id)} · cone profile`)),...(data.controls||[]).filter(r=>r.id!==exclude&&r.sectionCurve).map(r=>choice({kind:'region',geom:r.geom,id:r.id},`${name(r.geom)} · ${r.name}`)),...(data.structuralSubsurfaces||[]).filter(r=>r.id!==exclude&&r.sectionCurve).map(r=>choice({kind:'region',structure:r.structure,id:r.id},`${data.structures.find(s=>s.id===r.structure)?.name||r.structure} · ${r.name}`))];
}
