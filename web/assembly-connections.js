// Connection settings route to original native parts, copies and constraint modes.
export function connectionEditor(assembly,connection,h){
 const {E,select,params}=h,id=connection.id,points=assembly.fixedPoints||[],field=name=>connection.params.find(p=>p.name===name),custom=field('ConMode')?.choices?.find(c=>c.label==='Custom degrees of freedom')?.value===field('ConMode')?.value,mask=field('Constraints')?.value||0;
 const endpoint=side=>{
  const cap=side==='start'?'Start':'End',saved=connection.references[cap+'StructID']+'|'+connection.references[cap+'FixPtID'],point=points.find(p=>p.structure+'|'+p.id===saved),copy=field(cap+'FixPtSurfIndex')?.value??0;
  const choices=points.map(p=>[p.structure+'|'+p.id,p.label]);if(!choices.some(([v])=>v===saved))choices.push([saved,'Unavailable saved fixed point']);
  const copies=(point?.copies||[]).map((p,i)=>[i,`Copy ${i} · ${p.map(x=>Number(x.toPrecision(7))).join(', ')}`]);if(!copies.some(([v])=>v===copy))copies.push([copy,'Unavailable saved copy · '+copy]);
  return select(cap+' fixed point','connection-'+id+'-'+side,choices,saved)+select(cap+' copy','connection-'+id+'-'+side+'-copy',copies,copy);
 };
 return `<article class="tool-item"><h3>Connection ${connection.index+1}</h3><div class="tool-fields">${endpoint('start')}${endpoint('end')}</div><button data-connection-edit="${h.E(id)}" data-connection-assembly="${h.E(assembly.id)}">Apply fixed-point endpoints</button><p class="native-tip">Copy positions come from OpenVSP in native model units. Copy numbers include native mirrored and repeated fixed points.</p><div class="tool-fields">${params(connection.params.filter(p=>p.name==='ConMode'))}</div><fieldset><legend>Constrained degrees of freedom</legend>${['Translation X','Translation Y','Translation Z','Rotation X','Rotation Y','Rotation Z'].map((label,i)=>`<label class="membership-row"><input type="checkbox" data-connection-dof="${E(id)}" value="${i}" ${mask&(1<<i)?'checked':''} ${custom?'':'disabled'}>${label}</label>`).join('')}</fieldset><button data-connection-mask="${E(id)}" ${custom?'':'disabled'}>Apply custom constraints</button><p class="native-tip">Rigid and pinned presets are calculated by OpenVSP. Choose Custom degrees of freedom to change the six constraints.</p><button data-connection-delete="${E(assembly.id)}" data-connection-index="${connection.index}">Remove connection</button></article>`;
}
export function bindConnectionEditors(assemblies,h,app){
 const find=id=>assemblies.flatMap(a=>a.connections).find(c=>c.id===id);
 const run=async body=>{try{await h.mutate(body);}catch(e){app.toast(e.message);}};
 for(const a of assemblies)for(const c of a.connections)for(const side of ['start','end']){
  const point=document.querySelector('#connection-'+c.id+'-'+side),copy=document.querySelector('#connection-'+c.id+'-'+side+'-copy');
  if(point)point.onchange=()=>{const p=a.fixedPoints.find(p=>p.structure+'|'+p.id===point.value);copy.innerHTML=(p?.copies||[]).map((xyz,i)=>`<option value="${i}">Copy ${i} · ${h.E(xyz.map(x=>Number(x.toPrecision(7))).join(', '))}</option>`).join('');};
 }
 document.querySelectorAll('[data-connection-edit]').forEach(b=>b.onclick=()=>{const id=b.dataset.connectionEdit,body={operation:'assembly-connection-edit',assembly:b.dataset.connectionAssembly,id};for(const side of ['start','end']){const [structure,point]=h.val('connection-'+id+'-'+side).split('|');body[side+'Structure']=structure;body[side+'Point']=point;body[side+'Index']=h.num('connection-'+id+'-'+side+'-copy');}return run(body);});
 document.querySelectorAll('[data-connection-mask]').forEach(b=>b.onclick=()=>{const c=find(b.dataset.connectionMask),value=[...document.querySelectorAll(`[data-connection-dof="${c.id}"]:checked`)].reduce((mask,e)=>mask|(1<<Number(e.value)),0);return run({operation:'parameter',id:c.params.find(p=>p.name==='Constraints').id,value});});
}
