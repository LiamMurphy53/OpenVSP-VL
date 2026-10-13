// Typed metadata values are persisted by the native OpenVSP attribute APIs.
export function mountAttributeValueEditor(root,kind,values,h){
 const {E,field,select,paramOptions,val,num,bind}=h;
 const existing=values!==null;values=values||[];
 if(kind==='Group'){root.innerHTML='<p>A group holds a nested native attribute collection.</p>';return()=>null;}
 if(kind==='Parameter'){
  const choices=paramOptions(),id=values[0]||'';
  if(id&&!choices.some(([p])=>p===id))choices.unshift([id,`Current native reference · ${id}`]);
  root.innerHTML=select('Referenced parameter','attribute-reference',choices,id);return()=>val('attribute-reference');
 }
 if(kind==='Boolean'){root.innerHTML=select('Value','attribute-value',[[0,'False'],[1,'True']],Number(values[0])||0);return()=>!!num('attribute-value');}
 if(kind==='Text'){root.innerHTML=`<label class="tool-field">Value<textarea id="attribute-value" rows="5">${E(values[0]??'')}</textarea></label>`;return()=>val('attribute-value');}
 if(['Integer','Number'].includes(kind)){root.innerHTML=field('Value','attribute-value',values[0]??0);return()=>num('attribute-value');}
 const vector=kind==='Vector';let rows=existing?values.map(row=>[...row]):vector?[[0,0,0]]:[[1,0],[0,1]],columns=vector?3:rows[0]?.length||0;
 // Large imported matrices remain editable without mounting millions of fields.
 if(rows.length*columns>10000){root.innerHTML=`<p>This large ${vector?'vector list':'matrix'} uses a compact value editor. All native values are included.</p><label class="tool-field">${vector?'Vectors [[X,Y,Z],…]':'Matrix [[row],…]'}<textarea id="attribute-value" rows="12">${E(JSON.stringify(rows))}</textarea></label>`;return()=>JSON.parse(val('attribute-value'));}
 const read=()=>rows.map((row,i)=>row.map((_,j)=>num(`attribute-cell-${i}-${j}`)));
 const draw=()=>{
  root.innerHTML=`<p>${vector?'Each row is one native vector. All rows are saved together.':'Edit the native matrix by row and column.'}</p><div class="attribute-table"><table><thead><tr><th scope="col">${vector?'Vector':'Row'}</th>${Array.from({length:columns},(_,j)=>`<th scope="col">${vector?['X','Y','Z'][j]:`Column ${j+1}`}</th>`).join('')}<th scope="col">Actions</th></tr></thead><tbody>${rows.map((row,i)=>`<tr><th scope="row">${i+1}</th>${row.map((x,j)=>`<td>${field(`${vector?'Vector':'Row'} ${i+1} · ${vector?['X','Y','Z'][j]:`column ${j+1}`}`,`attribute-cell-${i}-${j}`,x)}</td>`).join('')}<td><button data-attribute-row="${i}" aria-label="Remove ${vector?'vector':'row'} ${i+1}">Remove</button></td></tr>`).join('')||`<tr><td colspan="${columns+2}">No values. Add a ${vector?'vector':'row'} to enter data.</td></tr>`}</tbody></table></div><div class="tool-actions"><button id="attribute-row-add">Add ${vector?'vector':'row'}</button>${vector?'':'<button id="attribute-column-add">Add column</button><button id="attribute-column-remove">Remove last column</button>'}</div><p class="native-tip">${rows.length} ${vector?'vectors':`rows × ${columns} columns`}</p>`;
  document.querySelector('#attribute-row-add').disabled=rows.length>=(vector?10000:1000)||(rows.length+1)*columns>10000;
  bind('attribute-row-add',()=>{rows=read();rows.push(Array(columns).fill(0));draw();});
  root.querySelectorAll('[data-attribute-row]').forEach(b=>b.onclick=()=>{try{rows=read();rows.splice(Number(b.dataset.attributeRow),1);draw();}catch(e){h.toast(e.message);}});
  if(!vector){document.querySelector('#attribute-column-add').disabled=columns>=1000||rows.length*(columns+1)>10000;document.querySelector('#attribute-column-remove').disabled=columns===0;bind('attribute-column-add',()=>{rows=read().map(row=>[...row,0]);columns++;draw();});bind('attribute-column-remove',()=>{rows=read().map(row=>row.slice(0,-1));columns--;draw();});}
 };
 draw();return read;
}
