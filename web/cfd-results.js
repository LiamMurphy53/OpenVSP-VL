import {drawingMesh} from './structural-preview.js?v=20261010-123';
export function cfdChecksCard(job,esc){
 const c=job.result?.cfdChecks;if(!c)return '';
 if(c.available===false)return `<section class="tool-card"><h3>Native drawing checks</h3><p>${esc(c.reason)}</p><p class="native-tip">Existing run files and the original engine log remain available.</p></section>`;
 const labels={BADEDGE:'Problem edges',BADTRI:'Problem triangles',BADQUAD:'Problem quads',ISECTCURVE:'Adapted intersection segments',BORDERCURVE:'Adapted border segments',RAWISECTCURVE:'Raw intersection segments',RAWBORDERCURVE:'Raw border segments'};
 const file=job.artifacts?.find(f=>f.name===c.drawingFile),preview=file&&file.size<=30000000;
 return `<section class="tool-card"><h3>${c.kind==='surface-intersections'?'Native surface intersections':'Native CFD checks and intersections'}</h3><table class="result-table"><tbody>${Object.entries(labels).filter(([k])=>Object.hasOwn(c.counts,k)).map(([k,label])=>`<tr><td>${label}</td><td>${Number(c.counts[k]||0).toLocaleString()}</td><td>${preview&&['BADEDGE','BADTRI','BADQUAD'].includes(k)&&c.counts[k]>0?`<button data-cfd-problem="${k}">Inspect ${esc(label.toLowerCase())}</button>`:''}</td></tr>`).join('')}</tbody></table>${c.warnings.map(w=>`<p class="native-tip">${esc(w)}</p>`).join('')}<div class="tool-actions">${preview?`<button data-cfd-results>${c.kind==='surface-intersections'?'Inspect native intersection curves':'Inspect native intersections and problem geometry'}</button>`:'<p>Drawing data is too large for the interactive preview; download the complete native data.</p>'}${job.result.meshFile?'<button data-cfd-mesh>Show mesh</button>':''}</div><div class="tool-actions">${[c.drawingFile,c.rawCurvesFile,c.adaptedCurvesFile].map(f=>`<a href="/api/artifact?id=${job.id}&file=${encodeURIComponent(f)}" download="${esc(f)}">↓ ${esc(f)}</a>`).join('')}</div><p class="native-tip">Checks and curves belong to this saved run, not to later aircraft edits. Review the original engine log as well.</p></section>`;
}
export function intersectionDrawings(data){const mesh=drawingMesh(data);mesh.groups=mesh.groups.map(g=>({...g,initiallyHidden:g.name.startsWith('Raw')}));return mesh;}
export function withCfdDrawings(mesh,data){
 const draw=drawingMesh(data),offset=mesh.nodes.length,groupMax=mesh.groups.reduce((m,g)=>Math.max(m,g.id),0),idMax=mesh.elements.reduce((m,e)=>Math.max(m,e.id),0);
 return {...mesh,filename:'CFD mesh with native intersections and checks',geometryPreview:true,nodes:[...mesh.nodes,...draw.nodes],nodeIDs:[...mesh.nodeIDs,...draw.nodeIDs],
  elements:[...mesh.elements,...draw.elements.map(e=>({...e,id:idMax+e.id,group:groupMax+e.group,nodes:e.nodes.map(i=>offset+i)}))],
  groups:[...mesh.groups,...draw.groups.map(g=>({...g,id:groupMax+g.id,color:g.name.startsWith('Native problem')?'#cc4433':undefined,initiallyHidden:g.name.startsWith('Raw')||g.name==='Adapted border curves'}))],
  totalElements:mesh.totalElements+draw.totalElements,warnings:[...(mesh.warnings||[]),...data.warnings],displayNote:data.displayNote+' Mesh nodes and connectivity come from the original saved Gmsh file; drawing points are additional display geometry.'};
}
export function nativeMessagesCard(job,esc){
 const d=job.diagnostics;if(!d?.messages?.length)return '';
 return `<section class="tool-card"><h3>Native engine messages to review</h3><p>OpenVSP printed these messages during this run. Review affected outputs before using them.</p><table class="result-table"><thead><tr><th>Message</th><th>Occurrences</th></tr></thead><tbody>${d.messages.map(m=>`<tr><td><b>${esc(m.severity)}</b> · ${esc(m.text)}<br><small>First appears on log line ${m.firstLine}</small></td><td>${m.count.toLocaleString()}</td></tr>`).join('')}</tbody></table>${d.omittedOccurrences?`<p>${d.omittedOccurrences.toLocaleString()} additional matched occurrences are omitted from this summary.</p>`:''}${d.abbreviated?'<p>Long messages are abbreviated here.</p>':''}<a href="/api/artifact?id=${job.id}&file=engine.log" download="engine.log">↓ Read the complete native engine log</a></section>`;
}

export function focusCfdProblem(mesh,kind){
 const names={BADEDGE:'Native problem edges',BADTRI:'Native problem triangles',BADQUAD:'Native problem quads'},name=names[kind];
 if(!name||!mesh.groups.some(g=>g.name===name&&g.count>0))throw Error('The saved native drawing has no matching problem geometry. Review its complete drawing data and engine log.');
 return {...mesh,groups:mesh.groups.map(g=>({...g,initiallyHidden:g.name!==name})),displayNote:`Initial view: ${name.toLowerCase()}. Use Show all groups for context or Show mesh to return to the saved mesh. `+(mesh.displayNote||'')};
}
