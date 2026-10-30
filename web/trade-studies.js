// Studies: change a few things about the aircraft, run analyses on every
// combination, then compare the answers. The native engine does all the work;
// this module builds study definitions and summarizes what the runs returned.
import {analyzeTitle,chart,num,mainWing,openInAnalyze} from './analyze.js?v=20261030';
import {modelLengthUnit} from './display-units.js?v=20261019';

let app,host,schema=null,schemaRevision=null,studies=[],draft=null,current=null,batch=null,metric=null,pollTimer=null,picking=null;
const inputSchemas=new Map(),compareCache=new Map();
const $=s=>host.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const len=()=>{const u=modelLengthUnit();return u==='model length'?'units':u;};
const unitOf=dim=>({length:len(),area:len()+'²',volume:len()+'³',angle:'°'}[dim]||'');

// ---------- What can be calculated per case ----------
// Reference area and chord come from the largest wing when there is one.
const wingReference=m=>mainWing(m)?{RefFlag:1,WingID:mainWing(m).id}:{};
const STEPS=[
 {name:'CompGeom'},
 {name:'MassProp'},
 {name:'ParasiteDrag',settings:['Vinf','VelocityUnit','Altitude','AltLengthUnit'],preset:m=>wingReference(m),sweeps:{Vinf:['Airspeed',''],Altitude:['Altitude','']}},
 {name:'VSPAEROSweep',settings:['AlphaStart','AlphaEnd','AlphaNpts','MachStart'],preset:m=>({...wingReference(m),AlphaStart:-4,AlphaEnd:12,AlphaNpts:9}),sweeps:{MachStart:['Mach number',''],ReCref:['Reynolds number',''],Xcg:['Moment reference X','length']}},
 {name:'Projection',settings:['DirectionType']},
 {name:'PlanarSlice',settings:['NumSlices']},
 {name:'WaveDrag',settings:['Mach'],sweeps:{Mach:['Mach number','']}},
];
const STEP=Object.fromEntries(STEPS.map(s=>[s.name,s]));
const SETTING_LABELS={Vinf:'Airspeed',VelocityUnit:'Unit',Altitude:'Altitude',AltLengthUnit:'Unit',AlphaStart:'α from (°)',AlphaEnd:'α to (°)',AlphaNpts:'Angles',MachStart:'Mach',DirectionType:'Looking along',NumSlices:'Slices',Mach:'Mach'};

// ---------- What the results are summarized as ----------
const finite=a=>(a||[]).filter(x=>typeof x==='number'&&Number.isFinite(x));
const max=a=>{const f=finite(a);return f.length?Math.max(...f):null;};
const sum=a=>finite(a).reduce((p,q)=>p+q,0);
const slope=(x,y)=>{const p=(x||[]).map((v,i)=>[v,y?.[i]]).filter(q=>q.every(Number.isFinite));if(p.length<2)return null;const n=p.length,sx=p.reduce((a,q)=>a+q[0],0),sy=p.reduce((a,q)=>a+q[1],0),sxy=p.reduce((a,q)=>a+q[0]*q[1],0),sxx=p.reduce((a,q)=>a+q[0]*q[0],0);return (n*sxy-sx*sy)/(n*sxx-sx*sx);};
const METRICS=[
 {id:'wet',step:'CompGeom',label:'Wetted area',dim:'area',fields:[['Comp_Geom','Total_Wet_Area']],calc:([a])=>a?.[0]},
 {id:'vol',step:'CompGeom',label:'Volume',dim:'volume',fields:[['Comp_Geom','Total_Wet_Vol']],calc:([a])=>a?.[0]},
 {id:'mass',step:'MassProp',label:'Mass',fields:[['Mass_Properties','Total_Mass']],calc:([a])=>a?.[0]},
 {id:'cgx',step:'MassProp',label:'CG x',dim:'length',fields:[['Mass_Properties','Total_CG']],calc:([a])=>a?.[0]?.[0]},
 {id:'cd0',step:'ParasiteDrag',label:'CD₀',fields:[['Parasite_Drag','Comp_CD'],['Parasite_Drag','Excres_CD_Total']],calc:([cd,ex])=>cd?sum(cd)+(ex?.[0]||0):null},
 {id:'ld',step:'VSPAEROSweep',label:'Best L/D',fields:[['VSPAERO_Polar','L_D']],calc:([a])=>max(a)},
 {id:'clmax',step:'VSPAEROSweep',label:'Highest CL',fields:[['VSPAERO_Polar','CLtot']],calc:([a])=>max(a)},
 {id:'cla',step:'VSPAEROSweep',label:'Lift slope CLα',unit:'/°',fields:[['VSPAERO_Polar','Alpha'],['VSPAERO_Polar','CLtot']],calc:([x,y])=>slope(x,y)},
 {id:'proj',step:'Projection',label:'Projected area',dim:'area',fields:[['Projection','Area']],calc:([a])=>a?.[0]},
 {id:'slice',step:'PlanarSlice',label:'Largest cross-section',dim:'area',fields:[['Slice','Slice_Area']],calc:([a])=>max(a)},
 {id:'cdw',step:'WaveDrag',label:'Wave drag CDw',fields:[['WaveDrag','CDWave']],calc:([a])=>a?.[0]},
];

// ---------- Parameters people actually change ----------
const WHOLE={TotalSpan:['Wingspan','length'],TotalProjectedSpan:['Projected span','length'],TotalArea:['Wing area','area'],TotalChord:['Mean chord','length'],Length:['Length','length'],Diameter:['Diameter','length'],FineRatio:['Fineness ratio',''],
 X_Rel_Location:['X position','length'],Y_Rel_Location:['Y position','length'],Z_Rel_Location:['Z position','length'],X_Rel_Rotation:['Roll angle','angle'],Y_Rel_Rotation:['Pitch angle','angle'],Z_Rel_Rotation:['Yaw angle','angle'],Scale:['Scale factor',''],Density:['Density',''],PointMass:['Point mass','']};
const SECTION={Span:['span','length'],Root_Chord:['root chord','length'],Tip_Chord:['tip chord','length'],Sweep:['sweep','angle'],Dihedral:['dihedral','angle'],Twist:['twist','angle']};
const WHOLE_GROUPS=new Set(['WingGeom','Design','XForm','Mass_Props']);
const component=p=>p.label.split(' / ')[0];
// Size first, then wing sections, then placement and mass.
const SIZE=['TotalSpan','TotalArea','TotalChord','TotalProjectedSpan','Length','Diameter','FineRatio'];
function rank(p){const m=/^XSec_(\d+)$/.exec(p.group);if(m)return 100+(+m[1])*10+Object.keys(SECTION).indexOf(p.name);const i=SIZE.indexOf(p.name);return i>=0?i:1000+Object.keys(WHOLE).indexOf(p.name);}
function nice(p){
 if(!p)return null;
 const m=/^XSec_(\d+)$/.exec(p.group);
 if(m&&+m[1]>0&&SECTION[p.name]&&p.label.includes(' / XSec / '))return {label:`Section ${m[1]} ${SECTION[p.name][0]}`,dim:SECTION[p.name][1]};
 if(WHOLE_GROUPS.has(p.group)&&WHOLE[p.name])return {label:WHOLE[p.name][0],dim:WHOLE[p.name][1]};
 return null;
}
function paramInfo(id){
 const p=schema?.parameters.find(q=>q.id===id);if(!p)return null;
 const n=nice(p);return {p,comp:component(p),label:n?.label||p.label.split(' / ').slice(1).join(' · '),dim:n?.dim||''};
}
function axisLabel(a,steps){
 if(a.kind==='parameter'){const i=paramInfo(a.id);return i?`${i.comp} · ${i.label}`:a.label;}
 const step=steps?.[a.stage]?.name||a.step,sw=STEP[step]?.sweeps?.[a.name];
 return `${analyzeTitle(step)} · ${sw?sw[0]:a.name}`;
}
function axisUnit(a,steps){
 if(a.kind==='parameter')return unitOf(paramInfo(a.id)?.dim);
 const step=steps?.[a.stage]?.name||a.step;return unitOf(STEP[step]?.sweeps?.[a.name]?.[1]);
}

// ---------- Shell ----------
export function installTradeStudies(context){
 app=context;host=document.getElementById('study-page');
 host.innerHTML=`<div class="az st">
 <nav class="az-catalog" aria-label="Studies"><div class="az-catalog-head"><h1>Studies</h1><p class="st-intro">Change part of the aircraft step by step and see how the results respond.</p><button id="st-new" class="primary st-new">New study</button></div><div id="st-list"></div><button id="st-classic" class="az-link">Open the classic study editor</button></nav>
 <section class="az-setup" aria-label="Study setup"><div id="st-builder"></div></section>
 <section class="az-results" aria-label="Study results"><div class="az-results-head"><div><span class="az-eyebrow">Results</span><h2 id="st-result-title">Nothing run yet</h2><p id="st-result-meta"></p></div><div class="az-head-actions"><label class="az-history-label" for="st-runs">Runs of this study</label><select id="st-runs"></select></div></div><div id="st-result-body"></div></section></div>`;
 $('#st-new').onclick=()=>{current=null;draft=blank();batch=null;renderList();renderBuilder();renderResults();};
 $('#st-classic').onclick=()=>document.querySelector('[data-page="studies"]').click();
 $('#st-runs').onchange=e=>current&&e.target.value&&openBatch(current.id,e.target.value);
 document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{host.hidden=b.dataset.page!=='study';document.querySelector('[data-page="study"]').classList.toggle('active',['study','studies'].includes(b.dataset.page));if(host.hidden)clearTimeout(pollTimer);else show();}));
}

async function show(){
 if(!draft)draft=blank();
 renderBuilder();
 await Promise.all([loadSchema(),refreshList()]);
 if(!current&&studies.length&&!draft.dirty)openStudy(studies[0].id);
 else{renderBuilder();if(current&&batch)openBatch(current.id,batch.id);else renderResults();}
}

async function loadSchema(){
 const m=app.model();if(schema&&schemaRevision===m.revision)return;
 try{schema=await app.api('/api/study-schema');schemaRevision=m.revision;}catch(e){app.toast(e.message);}
}
async function refreshList(){try{studies=await app.api('/api/studies');}catch{studies=[];}renderList();}
async function inputSchema(name){if(!inputSchemas.has(name))inputSchemas.set(name,app.api('/api/schema?name='+encodeURIComponent(name)));return inputSchemas.get(name);}

function renderList(){
 const when=t=>new Date(t*1000).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
 $('#st-list').innerHTML=studies.length?`<section><h3>Saved studies</h3>${studies.map(s=>{const last=s.executions?.[0];
  return `<button class="az-item ${s.id===current?.id?'active':''}" data-study="${esc(s.id)}"><b>${esc(s.name)}</b><small>${s.caseCount} case${s.caseCount===1?'':'s'} · ${s.stages.map(x=>analyzeTitle(x.name)).join(', ')}</small><span class="az-tags">${last?`<em class="az-tag ${last.status==='complete'?'ok':['failed','interrupted'].includes(last.status)?'bad':last.status==='partial'?'warn':''}">${esc({complete:'Finished',partial:'Some cases failed',failed:'Failed',running:'Running',cancelled:'Cancelled',interrupted:'Interrupted'}[last.status]||last.status)} · ${esc(when(last.started))}</em>`:'<em class="az-tag">Not run</em>'}</span></button>`;}).join('')}</section>`:'<p class="az-empty">No studies yet. Set one up in the middle column.</p>';
 host.querySelectorAll('[data-study]').forEach(b=>b.onclick=()=>openStudy(b.dataset.study));
}

// ---------- Draft <-> saved definition ----------
function blank(){return {id:null,version:null,name:'New study',axes:[],steps:[{name:'CompGeom',settings:{},extra:[]}],continueOnError:true,locked:null,dirty:false};}
const clean=x=>typeof x==='number'?Number(x.toPrecision(10)):x;
function evenly(v){if(v.length<3||!v.every(Number.isFinite))return false;const d=v[1]-v[0];return d!==0&&v.every((x,i)=>Math.abs(x-(v[0]+d*i))<=1e-9*Math.max(1,Math.abs(x)));}
function axisDraft(a,steps){
 const base={kind:a.kind,values:a.values,baseline:a.baseline,choices:a.choices,integer:a.integer};
 const shape=a.choices?{mode:'choices',picked:a.values}:evenly(a.values)?{mode:'range',from:clean(a.values[0]),to:clean(a.values.at(-1)),count:a.values.length}:{mode:'list',list:a.values.map(clean).join(', ')};
 return a.kind==='parameter'?{...base,...shape,id:a.id}:{...base,...shape,step:steps[a.stage].name,name:a.name};
}
function fromPlan(plan){
 const unsupported=plan.stages.some(s=>!STEP[s.name]||s.sourceStage!=null||s.structure||s.memberInputs?.length||s.geometryInputs?.length)||plan.axes.some(a=>!['parameter','input'].includes(a.kind)||a.valueMode==='array'||a.member!=null||(a.kind==='input'&&!STEP[plan.stages[a.stage]?.name]?.sweeps?.[a.name]));
 const steps=plan.stages.map(s=>{const keep=STEP[s.name]?.settings||[];return {name:s.name,settings:Object.fromEntries((s.inputs||[]).filter(e=>keep.includes(e.name)&&e.values.length===1).map(e=>[e.name,e.values[0]])),extra:(s.inputs||[]).filter(e=>!(keep.includes(e.name)&&e.values.length===1))};});
 return {id:plan.id,version:plan.version,name:plan.name,axes:plan.axes.map(a=>axisDraft(a,plan.stages)),steps,continueOnError:plan.continueOnError,locked:unsupported?'This study uses options only the classic editor can change. You can still run it and read its results here.':null,dirty:false};
}
function axisValues(a){
 if(a.mode==='choices')return a.picked||[];
 if(a.mode==='list'){const t=String(a.list||'').trim();return t?t.split(/[,\s]+/).map(Number):[];}
 const n=Math.max(1,Math.min(200,Math.round(a.count||1)));
 const out=Array.from({length:n},(_,i)=>n===1?Number(a.from):Number(a.from)+(Number(a.to)-Number(a.from))*i/(n-1)).map(x=>a.integer?Math.round(x):Number(x.toPrecision(10)));
 return [...new Set(out)];
}
const caseCount=()=>draft.axes.reduce((p,a)=>p*Math.max(axisValues(a).length,1),1);

async function stepInputs(step){
 const s=await inputSchema(step.name),m=app.model(),wanted={...(STEP[step.name]?.preset?.(m)||{}),...step.settings};
 const out=[...step.extra];
 for(const [name,value] of Object.entries(wanted)){
  const e=s.inputs.find(x=>x.name===name&&x.index===0&&x.editable);
  if(!e||out.some(x=>x.name===name))continue;
  if(String(e.values[0])!==String(value))out.push({name,index:0,values:[value]});
 }
 return out;
}
async function definitionBody(){
 const m=app.model();
 if(!draft.steps.length)throw Error('Choose at least one thing to calculate.');
 for(const a of draft.axes){const v=axisValues(a);if(!v.length||v.some(x=>typeof x==='number'&&!Number.isFinite(x)))throw Error(`${axisLabel(a)}: enter the values to try.`);}
 if(caseCount()>1000)throw Error('That is more than 1000 cases. Use fewer values.');
 const stages=await Promise.all(draft.steps.map(async s=>({name:s.name,inputs:await stepInputs(s)})));
 const axes=draft.axes.map(a=>a.kind==='parameter'?{kind:'parameter',id:a.id,values:axisValues(a)}:{kind:'input',stage:draft.steps.findIndex(s=>s.name===a.step),name:a.name,index:0,values:axisValues(a)});
 const body={name:draft.name.trim()||'Study',description:'',stages,axes,continueOnError:draft.continueOnError,revision:m.revision};
 if(draft.id)Object.assign(body,{id:draft.id,definitionVersion:draft.version,setIdentities:m.tools.sets.map(s=>s.identity)});
 return body;
}

async function openStudy(id){
 const plan=studies.find(s=>s.id===id);if(!plan)return;
 current=plan;draft=fromPlan(plan);batch=null;metric=null;
 renderList();renderBuilder();
 const last=plan.executions?.[0];
 if(last)openBatch(plan.id,last.id);else renderResults();
}

// ---------- Builder ----------
function renderBuilder(){
 const body=$('#st-builder');if(!body||!draft)return;
 const locked=!!draft.locked,dis=locked?'disabled':'';
 const n=caseCount(),runs=n*draft.steps.length;
 body.innerHTML=`<div class="az-head"><span class="az-eyebrow">${draft.id?'Saved study':'New study'}</span><input id="st-name" class="st-name" value="${esc(draft.name)}" aria-label="Study name" ${dis}></div>
 ${locked?`<div class="az-callout warn"><p>${esc(draft.locked)}</p></div>`:''}
 <section class="st-block"><h3><span>1</span>Change</h3><p class="az-hint">Every combination of values becomes one case. Each case runs on its own copy of the aircraft; your model is not changed.</p>
  <div id="st-axes">${draft.axes.map((a,i)=>axisCard(a,i,dis)).join('')||'<p class="st-empty">Nothing yet. With nothing to change, the study runs the current aircraft once.</p>'}</div>
  ${locked?'':picking?pickerMarkup():`<button id="st-add" class="st-add" ${draft.axes.length>=4?'disabled':''}>＋ Add something to change</button>`}
 </section>
 <section class="st-block"><h3><span>2</span>Calculate</h3><p class="az-hint">These analyses run on every case.</p>
  <div class="st-steps">${STEPS.map(s=>{const i=draft.steps.findIndex(x=>x.name===s.name),on=i>=0;return `<div class="st-step ${on?'on':''}"><label><input type="checkbox" data-step="${s.name}" ${on?'checked':''} ${dis}> <b>${esc(analyzeTitle(s.name))}</b></label>${on&&s.settings?`<div class="st-settings" data-settings="${s.name}"></div>`:''}</div>`;}).join('')}
  ${draft.steps.filter(s=>!STEP[s.name]).map(s=>`<div class="st-step on"><label><input type="checkbox" checked disabled> <b>${esc(analyzeTitle(s.name))}</b></label></div>`).join('')}</div>
 </section>
 <div class="st-summary"><b>${n.toLocaleString()} case${n===1?'':'s'}</b> × ${draft.steps.length} analys${draft.steps.length===1?'is':'es'} = ${runs.toLocaleString()} run${runs===1?'':'s'}${draft.steps.some(s=>s.name==='VSPAEROSweep')?' · lift & drag takes the longest':''}</div>
 <div class="az-run st-run"><button id="st-run" class="primary">Run study</button><label class="st-check"><input id="st-continue" type="checkbox" ${draft.continueOnError?'checked':''} ${dis}> Keep going if a case fails</label></div>
 <p id="st-status" class="az-run-status" role="status"></p>`;
 bindBuilder();
 draft.steps.forEach(s=>STEP[s.name]?.settings&&renderSettings(s,locked));
 if(batch?.live)setRunning(true);
}
function axisCard(a,i,dis){
 const preview=axisValues(a),u=axisUnit(a,null);
 const values=a.mode==='choices'?`<div class="st-choices">${(a.choices||[]).map(c=>`<label><input type="checkbox" data-axis-choice="${i}" value="${esc(c.value)}" ${a.picked?.includes(c.value)?'checked':''} ${dis}> ${esc(c.label)}</label>`).join('')}</div>`
  :`<div class="st-values"><select data-axis-mode="${i}" aria-label="How to give values" ${dis}><option value="range" ${a.mode==='range'?'selected':''}>From</option><option value="list" ${a.mode==='list'?'selected':''}>Values</option></select>${a.mode==='range'?`<input type="number" step="any" data-axis="${i}" data-key="from" value="${esc(a.from)}" aria-label="From" ${dis}><span>to</span><input type="number" step="any" data-axis="${i}" data-key="to" value="${esc(a.to)}" aria-label="To" ${dis}><span>in</span><input type="number" min="1" max="200" step="1" data-axis="${i}" data-key="count" value="${esc(a.count)}" class="st-count" aria-label="Number of values" ${dis}><span>steps</span>`:`<input type="text" data-axis="${i}" data-key="list" value="${esc(a.list)}" placeholder="e.g. 28, 30, 32" aria-label="Values" ${dis}>`}</div>`;
 const locks=locksNear(a);
 return `<div class="st-var"><div class="st-var-head"><b>${esc(axisLabel(a))}</b>${a.baseline!=null&&!Array.isArray(a.baseline)?`<small>now ${esc(num(a.baseline))}${u?' '+esc(u):''}</small>`:''}${dis?'':`<button class="st-x" data-remove-axis="${i}" aria-label="Remove">×</button>`}</div>${values}<small class="st-preview">${preview.length} value${preview.length===1?'':'s'}: ${esc(preview.slice(0,8).map(x=>a.choices?(a.choices.find(c=>c.value===x)?.label??x):num(x)).join(', '))}${preview.length>8?' …':''}${u&&a.mode!=='choices'?' '+esc(u):''}</small>${locks.length?`<p class="st-lock">${esc(locks.map(l=>l.label.replace(/ \(.*\)$/,'')+' = '+num(l.value)).join(', '))} ${locks.length===1?'is':'are'} locked on ${esc(paramInfo(a.id)?.comp)}. Cases that would change ${locks.length===1?'it':'them'} fail; unlock under Design → Aircraft property locks if you mean to.</p>`:''}</div>`;
}

// Property locks on the same component as a swept parameter (other than the parameter itself).
function locksNear(a){
 if(a.kind!=='parameter'||!schema)return[];
 const comp=paramInfo(a.id)?.comp;
 return (app.model().tools.propertyLocks||[]).filter(l=>l.id!==a.id&&paramInfo(l.id)?.comp===comp);
}
function pickerMarkup(){
 const m=app.model(),comps=m.components.map(c=>c.name),q=picking.search||'';
 let options='';
 if(picking.comp==='@steps'){
  options=draft.steps.flatMap(s=>Object.entries(STEP[s.name]?.sweeps||{}).map(([name,[label]])=>`<option value="${esc(s.name+'|'+name)}">${esc(analyzeTitle(s.name))} · ${esc(label)}</option>`)).join('')||'<option value="" disabled>Tick lift & drag, parasite drag or wave drag below first</option>';
 }else if(picking.comp){
  const params=(schema?.parameters||[]).filter(p=>component(p)===picking.comp&&p.editable!==false&&p.type!==3);
  const good=params.map(p=>[p,nice(p)]).filter(([,n])=>n).filter(([p])=>!(/^XSec_/.test(p.group))||m.components.find(c=>c.name===picking.comp)?.type==='Wing');
  good.sort((a,b)=>rank(a[0])-rank(b[0]));
  options=good.map(([p,n])=>`<option value="${esc(p.id)}">${esc(n.label)}</option>`).join('')+`<option value="@more">More parameters…</option>`;
 }
 const more=picking.param==='@more'&&picking.comp!=='@steps';
 const found=more?(schema?.parameters||[]).filter(p=>component(p)===picking.comp&&p.editable!==false&&p.type!==3&&(!q||p.label.toLowerCase().includes(q.toLowerCase()))).slice(0,60):[];
 return `<div class="st-picker"><div class="az-field"><label for="st-pick-comp">On</label><select id="st-pick-comp"><option value="">Choose a component…</option>${comps.map(c=>`<option ${c===picking.comp?'selected':''}>${esc(c)}</option>`).join('')}<option value="@steps" ${picking.comp==='@steps'?'selected':''}>An analysis setting (Mach, airspeed…)</option></select></div>
 ${picking.comp?`<div class="az-field"><label for="st-pick-param">Change</label><select id="st-pick-param"><option value="">Choose…</option>${options}</select></div>`:''}
 ${more?`<div class="az-field"><label for="st-pick-search">Search ${esc(picking.comp)}</label><input id="st-pick-search" type="search" value="${esc(q)}" placeholder="e.g. sweep, chord, density"><select id="st-pick-more" size="7">${found.map(p=>`<option value="${esc(p.id)}">${esc(p.label.split(' / ').slice(1).join(' · '))}</option>`).join('')}</select></div>`:''}
 ${schema?'':'<p class="az-hint">Reading aircraft parameters…</p>'}
 <div class="st-picker-actions"><button id="st-pick-cancel" type="button">Cancel</button></div></div>`;
}

function addAxis(value){
 if(!value)return;
 if(picking.comp==='@steps'){
  const [step,name]=value.split('|');
  inputSchema(step).then(s=>{const e=s.inputs.find(x=>x.name===name&&x.index===0),b=e?.values[0]??0;pushAxis({kind:'input',step,name,baseline:b,mode:'range',from:+(b*0.8||0).toPrecision(4),to:+(b*1.2||1).toPrecision(4),count:5});});
  return;
 }
 const p=schema.parameters.find(x=>x.id===value);if(!p)return;
 if(p.choices)return pushAxis({kind:'parameter',id:p.id,baseline:p.value,choices:p.choices,mode:'choices',picked:p.choices.map(c=>c.value)});
 const b=p.value,dim=nice(p)?.dim,spread=dim==='angle'?5:Math.abs(b)*0.2||1;
 let from=b-spread,to=b+spread;if(p.min!=null)from=Math.max(from,p.min);if(p.max!=null)to=Math.min(to,p.max);
 pushAxis({kind:'parameter',id:p.id,baseline:b,integer:!!p.integer,mode:'range',from:+from.toPrecision(4),to:+to.toPrecision(4),count:p.integer?Math.min(5,Math.abs(to-from)+1):5});
}
function pushAxis(a){
 if(draft.axes.some(x=>x.kind===a.kind&&(a.kind==='parameter'?x.id===a.id:x.step===a.step&&x.name===a.name))){app.toast('That is already in this study.');return;}
 draft.axes.push(a);draft.dirty=true;picking=null;renderBuilder();
}

function bindBuilder(){
 const name=$('#st-name');if(name)name.oninput=()=>{draft.name=name.value;draft.dirty=true;};
 const add=$('#st-add');if(add)add.onclick=()=>{picking={comp:'',param:''};renderBuilder();loadSchema().then(()=>picking&&renderBuilder());};
 const comp=$('#st-pick-comp');if(comp)comp.onchange=()=>{picking={comp:comp.value,param:''};renderBuilder();};
 const param=$('#st-pick-param');if(param)param.onchange=()=>{if(param.value==='@more'){picking.param='@more';renderBuilder();$('#st-pick-search')?.focus();}else addAxis(param.value);};
 const search=$('#st-pick-search');if(search)search.oninput=()=>{picking.search=search.value;const pos=search.selectionStart;renderBuilder();const s=$('#st-pick-search');s.focus();s.setSelectionRange(pos,pos);};
 const more=$('#st-pick-more');if(more)more.onchange=()=>addAxis(more.value);
 const cancel=$('#st-pick-cancel');if(cancel)cancel.onclick=()=>{picking=null;renderBuilder();};
 host.querySelectorAll('[data-remove-axis]').forEach(b=>b.onclick=()=>{draft.axes.splice(+b.dataset.removeAxis,1);draft.dirty=true;renderBuilder();});
 host.querySelectorAll('[data-axis-mode]').forEach(s=>s.onchange=()=>{const a=draft.axes[+s.dataset.axisMode],v=axisValues(a);Object.assign(a,s.value==='list'?{mode:'list',list:v.map(x=>num(x,6)).join(', ')}:{mode:'range',from:v[0]??a.baseline,to:v.at(-1)??a.baseline,count:Math.max(v.length,2)});draft.dirty=true;renderBuilder();});
 host.querySelectorAll('[data-axis]').forEach(el=>el.oninput=()=>{const a=draft.axes[+el.dataset.axis];a[el.dataset.key]=el.dataset.key==='list'?el.value:Number(el.value);draft.dirty=true;refreshCounts(+el.dataset.axis);});
 host.querySelectorAll('[data-axis-choice]').forEach(el=>el.onchange=()=>{const a=draft.axes[+el.dataset.axisChoice],v=a.choices.find(c=>String(c.value)===el.value)?.value;a.picked=el.checked?[...new Set([...(a.picked||[]),v])]:a.picked.filter(x=>x!==v);draft.dirty=true;refreshCounts(+el.dataset.axisChoice);});
 host.querySelectorAll('[data-step]').forEach(b=>b.onchange=()=>{
  if(b.checked)draft.steps.push({name:b.dataset.step,settings:{},extra:[]});
  else{draft.steps=draft.steps.filter(s=>s.name!==b.dataset.step);draft.axes=draft.axes.filter(a=>a.kind!=='input'||a.step!==b.dataset.step);}
  draft.steps.sort((x,y)=>STEPS.findIndex(s=>s.name===x.name)-STEPS.findIndex(s=>s.name===y.name));draft.dirty=true;renderBuilder();});
 const cont=$('#st-continue');if(cont)cont.onchange=()=>{draft.continueOnError=cont.checked;draft.dirty=true;};
 $('#st-run').onclick=run;
}
// Keep focus in the field being typed in: update only the counts and preview.
function refreshCounts(i){
 const card=host.querySelectorAll('.st-var')[i],a=draft.axes[i];
 if(card){const tmp=document.createElement('div');tmp.innerHTML=axisCard(a,i,'');card.querySelector('.st-preview').replaceWith(tmp.querySelector('.st-preview'));}
 const n=caseCount(),runs=n*draft.steps.length,sum=$('.st-summary b');if(sum){sum.textContent=`${n.toLocaleString()} case${n===1?'':'s'}`;sum.nextSibling.textContent=` × ${draft.steps.length} analys${draft.steps.length===1?'is':'es'} = ${runs.toLocaleString()} run${runs===1?'':'s'}`;}
}

async function renderSettings(step,locked){
 const s=await inputSchema(step.name),holder=host.querySelector(`[data-settings="${step.name}"]`);if(!holder)return;
 const m=app.model(),preset=STEP[step.name].preset?.(m)||{};
 holder.innerHTML=STEP[step.name].settings.map(name=>{
  const e=s.inputs.find(x=>x.name===name&&x.index===0);if(!e)return'';
  const v=step.settings[name]??preset[name]??e.values[0],id=`st-set-${step.name}-${name}`;
  const control=e.choices?`<select id="${id}" data-set="${name}" ${locked?'disabled':''}>${e.choices.map(c=>`<option value="${esc(c.value)}" ${String(c.value)===String(v)?'selected':''}>${esc(c.label)}</option>`).join('')}</select>`:`<input id="${id}" type="number" step="${e.type===1?1:'any'}" data-set="${name}" value="${esc(v)}" ${locked?'disabled':''}>`;
  return `<div class="az-field"><label for="${id}">${esc(SETTING_LABELS[name]||e.label||name)}</label>${control}</div>`;
 }).join('');
 holder.querySelectorAll('[data-set]').forEach(el=>el.onchange=()=>{const e=s.inputs.find(x=>x.name===el.dataset.set);step.settings[el.dataset.set]=e.type===3?el.value:Number(el.value);draft.dirty=true;});
}

// ---------- Running ----------
async function run(){
 const btn=$('#st-run');btn.disabled=true;status('Saving the study and a copy of the aircraft…');
 try{
  if(!draft.locked||!current){
   const plan=await app.api('/api/study-save',await definitionBody());
   current=plan;draft=fromPlan(plan);
  }
  const started=await app.api('/api/study-start',{id:current.id});
  await refreshList();current=studies.find(s=>s.id===current.id)||current;renderList();renderBuilder();
  openBatch(current.id,started.id);
 }catch(e){btn.disabled=false;status(e.message,'bad');}
}
function status(text,kind=''){const el=$('#st-status');if(el){el.textContent=text;el.className='az-run-status '+kind;}}
function setRunning(on){const r=$('#st-run');if(r)r.disabled=on;if(on)status('Running. You can keep working; results fill in as cases finish.');}

// ---------- Results ----------
function renderRuns(){
 const sel=$('#st-runs'),runs=current?.executions||[];
 sel.innerHTML=runs.length?runs.map(r=>`<option value="${esc(r.id)}" ${r.id===batch?.id?'selected':''}>${esc(new Date(r.started*1000).toLocaleString())} · ${esc(r.status)}</option>`).join(''):'<option value="">No runs yet</option>';
}
async function openBatch(sid,bid){
 clearTimeout(pollTimer);
 let state;try{state=await app.api(`/api/study-batch?id=${encodeURIComponent(sid)}&batch=${encodeURIComponent(bid)}`);}catch(e){$('#st-result-body').innerHTML=`<div class="az-callout bad"><p>${esc(e.message)}</p></div>`;return;}
 if(current?.id!==sid)return;
 const was=batch;batch=state;
 if(!was||was.id!==state.id||was.completed!==state.completed||was.failed!==state.failed||was.status!==state.status)await renderResults();
 else renderProgress();
 if(state.live){setRunning(true);pollTimer=setTimeout(()=>openBatch(sid,bid),2000);}
 else if(was?.live){setRunning(false);status(state.status==='complete'?'Finished.':state.status==='cancelled'?'Cancelled.':`Finished with ${state.failed} failed case${state.failed===1?'':'s'}.`,state.failed?'bad':'');await refreshList();current=studies.find(s=>s.id===sid)||current;renderList();renderRuns();}
}

async function field(stageIndex,result,name){
 const key=JSON.stringify([stageIndex,result,0,name,0]),cache=`${batch.id}|${batch.completed}|${key}`;
 if(!compareCache.has(cache))compareCache.set(cache,app.api(`/api/study-compare?id=${encodeURIComponent(batch.study)}&batch=${encodeURIComponent(batch.id)}&field=${encodeURIComponent(key)}`).catch(()=>null));
 return compareCache.get(cache);
}
async function collect(){
 const stages=batch.plan.stages,metrics=METRICS.filter(x=>stages.some(s=>s.name===x.step));
 const rows=batch.cases.map(c=>({case:c.index,label:c.label,status:c.status,error:c.error||c.stages.find(s=>s.error)?.error,requested:c.values,effective:[...c.values],jobs:c.stages.map(s=>({name:s.name,job:s.job,status:s.status})),values:{},series:{}}));
 if(!batch.completed)return {metrics:[],rows};
 await Promise.all(metrics.map(async x=>{
  const si=stages.findIndex(s=>s.name===x.step);
  const data=await Promise.all(x.fields.map(([r,f])=>field(si,r,f)));
  for(const row of rows){
   const per=data.map(d=>d?.rows.find(r=>r.case===row.case));
   const eff=per.find(p=>p?.effective)?.effective;if(eff)row.effective=eff.map((v,i)=>v??row.requested[i]);
   if(per.some(p=>p?.values)){try{row.values[x.id]=x.calc(per.map(p=>p?.values));}catch{row.values[x.id]=null;}}
  }
 }));
 const aero=stages.findIndex(s=>s.name==='VSPAEROSweep');
 if(aero>=0){
  const [al,cl,cd,ld]=await Promise.all(['Alpha','CLtot','CDtot','L_D'].map(f=>field(aero,'VSPAERO_Polar',f)));
  for(const row of rows){const get=d=>d?.rows.find(r=>r.case===row.case)?.values;row.series={alpha:get(al),cl:get(cl),cd:get(cd),ld:get(ld)};}
 }
 return {metrics:metrics.filter(x=>rows.some(r=>Number.isFinite(r.values[x.id]))),rows};
}

function renderProgress(){
 const el=$('#st-progress');if(!el||!batch)return;
 const total=batch.cases.length,done=batch.completed+batch.failed;
 el.innerHTML=progressMarkup(total,done);
}
function progressMarkup(total,done){
 return `<div class="st-progress"><div class="st-bar"><i style="width:${(done/total*100).toFixed(1)}%"></i></div><span>${done} of ${total} cases done${batch.failed?` · ${batch.failed} failed`:''}</span>${batch.live?'<button id="st-cancel">Cancel</button>':''}</div>`;
}

async function renderResults(){
 renderRuns();
 const body=$('#st-result-body'),title=$('#st-result-title'),meta=$('#st-result-meta');
 if(!current||!batch){title.textContent=current?current.name:'Nothing run yet';meta.textContent='';body.innerHTML=`<div class="az-empty-state"><p>${current?'This study has not been run yet.':'Set up a study in the middle column, then press <b>Run study</b>.'}</p><p>Each case is a copy of your aircraft with the values you chose. Results appear here as cases finish.</p></div>`;return;}
 title.textContent=batch.name;
 const took=batch.finished&&batch.started?` · took ${Math.max(1,Math.round(batch.finished-batch.started))} s`:'';
 meta.textContent=new Date(batch.started*1000).toLocaleString()+took;
 const token=batch.id+'|'+batch.completed;
 const {metrics,rows}=await collect();
 if(token!==batch.id+'|'+batch.completed)return;
 if(!metrics.some(x=>x.id===metric))metric=metrics[0]?.id||null;
 const axes=batch.plan.axes,steps=batch.plan.stages,m=metrics.find(x=>x.id===metric);
 const total=batch.cases.length,done=batch.completed+batch.failed;
 const unit=x=>x.unit||unitOf(x.dim);
 let main='';
 if(m){
  const ok=rows.filter(r=>Number.isFinite(r.values[m.id]));
  if(axes.length===0)main=`<div class="az-kpis"><div><span>${esc(m.label)}</span><strong>${esc(num(ok[0]?.values[m.id]))}${unit(m)?` <small>${esc(unit(m))}</small>`:''}</strong></div></div>`;
  else{
   const groups=new Map();
   for(const r of ok){const g=axes.length>=2?r.effective.slice(1).map((v,i)=>num(v)+(axisUnit(axes[i+1],steps)?' '+axisUnit(axes[i+1],steps):'')).join(', '):'';if(!groups.has(g))groups.set(g,[]);groups.get(g).push(r);}
   const xl=axes.length>2?'Case':`${axisLabel(axes[0],steps)}${axisUnit(axes[0],steps)?` (${axisUnit(axes[0],steps)})`:''}`;
   const series=[...groups].slice(0,8).map(([g,rs])=>{const pts=rs.map(r=>[axes.length>2?r.case+1:Number(r.effective[0]),r.values[m.id]]).sort((a,b)=>a[0]-b[0]);return {label:axes.length>=2?`${axisLabel(axes[1],steps)} = ${g}`:m.label,x:pts.map(p=>p[0]),y:pts.map(p=>p[1])};});
   main=chart(series,xl,`${m.label}${unit(m)?` (${unit(m)})`:''}`)||'<p class="az-hint">The chart appears once at least two cases have finished.</p>';
   const best=ok.reduce((b,r)=>!b||r.values[m.id]>b.values[m.id]?r:b,null),worst=ok.reduce((b,r)=>!b||r.values[m.id]<b.values[m.id]?r:b,null);
   if(ok.length>1)main=`<div class="az-kpis"><div><span>Highest ${esc(lower(m.label))}</span><strong>${esc(num(best.values[m.id]))}</strong><small class="st-kpi-at">${esc(caseText(best,axes,steps))}</small></div><div><span>Lowest ${esc(lower(m.label))}</span><strong>${esc(num(worst.values[m.id]))}</strong><small class="st-kpi-at">${esc(caseText(worst,axes,steps))}</small></div></div>`+main;
  }
 }
 const polars=rows.filter(r=>finiteCount(r.series?.cl)>1).slice(0,8);
 const overlay=polars.length?`<h3>Lift & drag for each case</h3><div class="az-charts">${chart(polars.map(r=>({label:caseText(r,axes,steps)||r.label,x:r.series.cd,y:r.series.cl})),'Drag coefficient CD','Drag polar (CL vs CD)')}${chart(polars.map(r=>({label:caseText(r,axes,steps)||r.label,x:r.series.alpha,y:r.series.ld})),'Angle of attack (°)','Lift-to-drag ratio')}</div>${rows.filter(r=>finiteCount(r.series?.cl)>1).length>8?'<p class="az-hint">Showing the first 8 cases.</p>':''}`:'';
 const table=`<div class="az-table"><table><thead><tr><th>Case</th>${axes.map(a=>`<th>${esc(axisLabel(a,steps))}${axisUnit(a,steps)?` (${esc(axisUnit(a,steps))})`:''}</th>`).join('')}${metrics.map(x=>`<th>${esc(x.label)}${unit(x)?` (${esc(unit(x))})`:''}</th>`).join('')}<th>Status</th></tr></thead><tbody>${rows.map(r=>`<tr class="${r.status==='failed'?'st-failed':''}"><td><button class="st-case" data-case="${r.case}" title="Open this case's runs">${esc(r.label.replace('Case ','#'))}</button></td>${r.effective.map((v,i)=>`<td class="n">${esc(axes[i]?.choices?(axes[i].choices.find(c=>c.value===v)?.label??v):num(v))}</td>`).join('')}${metrics.map(x=>`<td class="n">${esc(num(r.values[x.id]))}</td>`).join('')}<td>${esc({complete:'Done',failed:'Failed',running:'Running',pending:'Waiting',cancelled:'Cancelled'}[r.status]||r.status)}</td></tr>${r.status==='failed'&&r.error?`<tr class="st-error-row"><td colspan="${2+axes.length+metrics.length}">${esc(r.error)}</td></tr>`:''}`).join('')}</tbody></table></div>`;
 const failedRows=rows.filter(r=>r.status==='failed'),allLocked=failedRows.length&&failedRows.every(r=>/is locked/.test(r.error||''));
 body.innerHTML=`<div id="st-progress">${batch.live||done<total?progressMarkup(total,done):''}</div>
 ${batch.failed&&!batch.live?`<div class="az-callout warn"><b>${batch.failed} case${batch.failed===1?'':'s'} failed</b><p>${allLocked?'Each one would have changed a locked property. Unlock it under Design → Aircraft property locks, or change something else.':'The reason is in the table below.'} ${batch.status!=='complete'&&!allLocked?'<button id="st-retry">Retry failed cases</button>':''}</p></div>`:''}
 ${metrics.length?`<div class="st-metrics" role="tablist">${metrics.map(x=>`<button role="tab" aria-selected="${x.id===metric}" class="${x.id===metric?'active':''}" data-metric="${x.id}">${esc(x.label)}</button>`).join('')}</div>`:batch.completed?'':'<p class="az-hint">Results appear as soon as the first case finishes.</p>'}
 ${main}${overlay}<h3>All cases</h3>${table}
 <h3>Files</h3><div class="az-files"><a id="st-csv" href="#"><span>This table (CSV)</span><small>${rows.length} rows</small></a>${batch.live?'':`<a href="/api/study.zip?id=${encodeURIComponent(batch.study)}&batch=${encodeURIComponent(batch.id)}" download><span>Every run's files (ZIP)</span><small>large</small></a>`}</div>`;
 host.querySelectorAll('[data-metric]').forEach(b=>b.onclick=()=>{metric=b.dataset.metric;renderResults();});
 host.querySelectorAll('[data-case]').forEach(b=>b.onclick=()=>caseMenu(rows.find(r=>r.case===+b.dataset.case),b));
 const cancel=$('#st-cancel');if(cancel)cancel.onclick=async()=>{cancel.disabled=true;try{await app.api('/api/study-cancel',{id:batch.study,batch:batch.id});}catch(e){app.toast(e.message);}};
 const retry=$('#st-retry');if(retry)retry.onclick=async()=>{retry.disabled=true;try{const b=await app.api('/api/study-resume',{id:batch.study,batch:batch.id});openBatch(b.study,b.id);}catch(e){app.toast(e.message);retry.disabled=false;}};
 $('#st-csv').onclick=e=>{e.preventDefault();downloadCSV(rows,metrics,axes,steps);};
}
const finiteCount=a=>finite(a).length;
const lower=l=>/^[A-Z][a-z]/.test(l)?l[0].toLowerCase()+l.slice(1):l;
function caseText(r,axes,steps){return axes.map((a,i)=>`${axisLabel(a,steps).split(' · ').pop()} ${a.choices?(a.choices.find(c=>c.value===r.effective[i])?.label??r.effective[i]):num(r.effective[i])}${axisUnit(a,steps)?' '+axisUnit(a,steps):''}`).join(', ');}
function caseMenu(row,anchor){
 document.querySelector('.st-case-menu')?.remove();
 const menu=document.createElement('div');menu.className='st-case-menu';
 menu.innerHTML=`<b>${esc(row.label)}</b>${row.jobs.map(j=>j.job?`<button data-open-job="${esc(j.job)}">Open ${esc(lower(analyzeTitle(j.name)))}</button>`:`<span>${esc(analyzeTitle(j.name))} · not run</span>`).join('')}`;
 anchor.closest('td').append(menu);
 menu.querySelectorAll('[data-open-job]').forEach(b=>b.onclick=()=>openInAnalyze(b.dataset.openJob));
 setTimeout(()=>document.addEventListener('click',function close(e){if(!menu.contains(e.target)){menu.remove();document.removeEventListener('click',close);}}),0);
}
function downloadCSV(rows,metrics,axes,steps){
 const cell=x=>{const s=x==null?'':String(x);return /[",\n]/.test(s)||/^[=+\-@]/.test(s)?'"'+(/^[=+\-@]/.test(s)?"'":'')+s.replace(/"/g,'""')+'"':s;};
 const head=['case',...axes.map(a=>axisLabel(a,steps)+(axisUnit(a,steps)?` (${axisUnit(a,steps)})`:'')),...metrics.map(x=>x.label),'status','error'];
 const lines=[head,...rows.map(r=>[r.label,...r.effective,...metrics.map(x=>r.values[x.id]),r.status,r.error||''])].map(l=>l.map(cell).join(','));
 const url=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/csv'})),a=document.createElement('a');
 a.href=url;a.download=(batch.name||'study').replace(/[^\w-]+/g,'-')+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
