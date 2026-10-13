// Typed sweep cases are passed unchanged to native workers; no engineering math.
export const structuredSweep=a=>a.valueMode==='array'||a.type===3||a.type===4&&a.component==null||!!a.choices?.length;
export function mountSweepValues(root,a,index,{esc:E,changed,toast}){
 let cases=structuredClone(a.values);
 const id=(c,j,k)=>`study-value-${index}-${c}-${j}${k===undefined?'':'-'+k}`;
 const numeric=(el,integer=false)=>{const value=Number(el.value);if(!el.value.trim()||!Number.isFinite(value)||integer&&!Number.isInteger(value))throw Error(integer?'Enter integer case values.':'Enter finite case values.');return value;};
 const choices=a.choices||a.choiceList;
 const scalar=(value,c,j)=>{
  const label=`Case ${c+1} · value ${j+1}`,key=id(c,j);
  if(a.type===4)return `<div class="study-value-vector" role="group" aria-label="${label}">${['X','Y','Z'].map((axis,k)=>`<label for="${id(c,j,k)}">${label} · ${axis}<input id="${id(c,j,k)}" type="number" step="any" value="${E(value[k])}"></label>`).join('')}</div>`;
  const options=choices?[...choices]:null;
  if(options&&!options.some(x=>JSON.stringify(x.value)===JSON.stringify(value)))options.unshift({value,label:'Current native value · '+String(value)});
  return `<label for="${key}">${label}${options?`<select id="${key}">${options.map(x=>`<option value="${E(JSON.stringify(x.value))}" ${JSON.stringify(x.value)===JSON.stringify(value)?'selected':''}>${E(x.label)}</option>`).join('')}</select>`:`<input id="${key}" type="${a.type===3?'text':'number'}" ${a.type===3?'':`step="${a.type===1?'1':'any'}"`} value="${E(value)}">`}</label>`;
 };
 const input=(c,j,k)=>root.querySelector('#'+id(c,j,k));
 const readOne=(c,j)=>a.type===4?[0,1,2].map(k=>numeric(input(c,j,k))):choices?JSON.parse(input(c,j).value):a.type===3?input(c,j).value:numeric(input(c,j),a.type===1);
 const size=()=>cases.reduce((n,x)=>n+(a.valueMode==='array'?x.length:1)*(a.type===4?3:1),0);
 // Keep large imported definitions editable without mounting thousands of fields.
 if(size()>500){root.innerHTML=`<label for="study-values-${index}">Case values (JSON)<textarea id="study-values-${index}" rows="8">${E(JSON.stringify(cases))}</textarea></label><p class="native-tip">Each outer entry is one case. Complete arrays and XYZ vectors keep their native order.</p>`;root.querySelector('textarea').oninput=()=>changed(null);return()=>{const values=JSON.parse(root.querySelector('textarea').value);if(!Array.isArray(values)||!values.length)throw Error('Give every dimension at least one case.');return values;};}
 const read=()=>cases.map((x,c)=>a.valueMode==='array'?x.map((_,j)=>readOne(c,j)):readOne(c,0));
 const defaultValue=()=>a.type===4?[0,0,0]:choices?.[0]?.value??(a.type===3?'':0);
 const mutate=fn=>()=>{try{cases=read();fn();a.values=structuredClone(cases);draw();changed(cases.length);}catch(e){toast(e.message);}};
 const draw=()=>{
  root.innerHTML=cases.map((value,c)=>`<fieldset class="study-value-case"><legend>Case ${c+1}</legend>${(a.valueMode==='array'?value:[value]).map((x,j)=>`<div class="study-value-row">${scalar(x,c,j)}${a.valueMode==='array'?`<button data-sweep-remove-value="${c},${j}" aria-label="Remove case ${c+1} value ${j+1}">Remove value</button>`:''}</div>`).join('')||'<p>No input values: this case passes an empty native array.</p>'}<div class="tool-actions">${a.valueMode==='array'?`<button data-sweep-add-value="${c}">Add input value</button>`:''}<button data-sweep-copy-case="${c}">Duplicate case</button><button data-sweep-remove-case="${c}" ${cases.length===1?'disabled':''}>Remove case</button><button data-sweep-up-case="${c}" ${c===0?'disabled':''}>Move up</button></div></fieldset>`).join('')+`<button data-sweep-add-case ${cases.length>=1000?'disabled':''}>Add another case</button>`;
  root.querySelectorAll('input,select').forEach(el=>el.addEventListener('input',()=>changed(cases.length)));
  root.querySelectorAll('[data-sweep-remove-value]').forEach(b=>b.onclick=mutate(()=>{const [c,j]=b.dataset.sweepRemoveValue.split(',').map(Number);cases[c].splice(j,1);}));
  root.querySelectorAll('[data-sweep-add-value]').forEach(b=>b.onclick=mutate(()=>{const row=cases[Number(b.dataset.sweepAddValue)];if(row.length>=10000)throw Error('Use up to 10,000 values in one native input array.');row.push(structuredClone(defaultValue()));}));
  root.querySelectorAll('[data-sweep-remove-case]').forEach(b=>b.onclick=mutate(()=>cases.splice(Number(b.dataset.sweepRemoveCase),1)));
  root.querySelectorAll('[data-sweep-copy-case]').forEach(b=>b.onclick=mutate(()=>{if(cases.length>=1000)throw Error('Use up to 1,000 cases per dimension.');const c=Number(b.dataset.sweepCopyCase);cases.splice(c+1,0,structuredClone(cases[c]));}));
  root.querySelectorAll('[data-sweep-up-case]').forEach(b=>b.onclick=mutate(()=>{const c=Number(b.dataset.sweepUpCase);[cases[c-1],cases[c]]=[cases[c],cases[c-1]];}));
  root.querySelector('[data-sweep-add-case]').onclick=mutate(()=>cases.push(structuredClone(cases.at(-1)??a.baseline)));
 };
 draw();return read;
}
