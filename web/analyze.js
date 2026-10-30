// Analyze: choose a question, set the few inputs that matter, read the answer.
// Every number shown comes from the native run; this module only formats it.
import {mountMeshViewer} from './mesh-viewer.js?v=20261022-run-status';
import {setInputNames} from './set-selection.js?v=20261022-cg';
import {modelLengthUnit} from './display-units.js?v=20261019';

let app,host,current=null,schema=null,geometrySchema=null,values=new Map(),drafts=new Map(),viewed=null,running=null,pollTimer=null,clockTimer=null,generation=0,jobsCache=[],disposeMesh=null;
const $=s=>host.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const key=e=>e.name+'|'+e.index;
const num=(x,p=4)=>typeof x!=='number'||!Number.isFinite(x)?'—':Math.abs(x)<1e-10?'0':Math.abs(x)>=1e5||(Math.abs(x)<1e-3&&x!==0)?x.toExponential(p-1):Number(x.toPrecision(p)).toLocaleString(undefined,{maximumFractionDigits:8});
const len=()=>{const u=modelLengthUnit();return u==='model length'?'units':u;};
const area=()=>len()+'²',vol=()=>len()+'³';

// ---------- Catalog ----------
// Names are the native analyses; everything else is presentation.
const wings=m=>m.components.filter(c=>c.type==='Wing');
const mainWing=m=>{const w=wings(m);return w.map(c=>[c,c.params.find(p=>p.name==='TotalArea')?.value||0]).sort((a,b)=>b[1]-a[1])[0]?.[0];};
const savedAero=()=>jobsCache.some(j=>j.status==='complete'&&j.name==='VSPAEROSweep');
const CATALOG=[
 {group:'Size & weight',items:[
  {name:'CompGeom',title:'Wetted area & volume',blurb:'Surface area exposed to the air and the enclosed volume, per component and in total. Overlapping parts are trimmed.',essentials:['Set','HalfMeshFlag']},
  {name:'MassProp',title:'Mass, CG & inertia',blurb:'Mass, center of gravity and moments of inertia from each component’s density and any point masses.',essentials:['Set','NumMassSlices'],note:m=>m.components.some(c=>c.params.some(p=>p.name==='Density'&&p.value!==1))?'':'Every component still has the default density of 1, so “mass” here equals volume. Set densities under Design → Mass inputs for real weights.'},
  {name:'Projection',title:'Projected area',blurb:'Silhouette area seen along an axis: frontal area, side area or planform from above.',essentials:['DirectionType','DirectionGeomID','Direction','TargetType','TargetSet','TargetGeomID']},
  {name:'PlanarSlice',title:'Cross-section areas',blurb:'Cuts the aircraft into slices along an axis and reports each slice’s area: the area-ruling curve.',essentials:['Set','Norm','NumSlices','AutoBoundFlag','StartVal','EndVal']},
 ]},
 {group:'Aerodynamics',items:[
  {name:'VSPAEROSweep',title:'Lift & drag polar',blurb:'VSPAERO vortex-lattice solution swept over angle of attack: lift, drag, pitching moment and L/D.',essentials:['AlphaStart','AlphaEnd','AlphaNpts','MachStart','ReCref','RefFlag','WingID','Sref','bref','cref','Xcg'],labels:{AlphaStart:'Angle of attack from',AlphaEnd:'to',AlphaNpts:'Number of angles',MachStart:'Mach number',ReCref:'Reynolds number (on reference chord)',RefFlag:'Reference dimensions',WingID:'Reference wing',Xcg:'Moment reference X (CG)'},units:{AlphaStart:'°',AlphaEnd:'°',Xcg:len},preset:m=>({RefFlag:[1],WingID:[mainWing(m)?.id||''],AlphaStart:[-4],AlphaEnd:[12],AlphaNpts:[9]}),geometry:true,slow:'Usually 10–60 s per angle'},
  {name:'ParasiteDrag',title:'Parasite drag buildup',blurb:'Skin-friction and form drag per component at one flight condition, summed into the zero-lift drag coefficient CD₀.',essentials:['Vinf','VelocityUnit','Altitude','AltLengthUnit','LengthUnit','RefFlag','WingID','Sref'],half:['Vinf','VelocityUnit','Altitude','AltLengthUnit'],labels:{Vinf:'Airspeed',VelocityUnit:'Unit',Altitude:'Altitude',AltLengthUnit:'Unit',LengthUnit:'Model is drawn in',RefFlag:'Reference area',WingID:'Reference wing'},preset:m=>({RefFlag:[1],WingID:[mainWing(m)?.id||'']})},
  {name:'WaveDrag',title:'Supersonic wave drag',blurb:'Far-field wave drag from the area distribution at a supersonic Mach number.',essentials:['Mach','Set','NumSlices','NumRotSects']},
  {name:'BladeElement',title:'Propeller blade elements',blurb:'Chord, twist and section data along each propeller blade, as used by blade-element methods.',essentials:['PropID'],requires:m=>m.components.some(c=>/prop/i.test(c.type))?'':'Add a propeller component in Design first.'},
 ]},
 {group:'From a saved lift & drag run',items:[
  {name:'CpSlicer',title:'Pressure slices',blurb:'Pressure coefficient along cuts through a finished VSPAERO solution.',essentials:['YSlicePosVec','XSlicePosVec','ZSlicePosVec'],source:true,requires:()=>savedAero()?'':'Run “Lift & drag polar” first; slices are read from its saved solution.'},
  {name:'FlowPlaneSlicer',title:'Airflow planes',blurb:'Velocity and pressure on planes through the flow around a finished VSPAERO solution.',source:true,requires:()=>savedAero()?'':'Run “Lift & drag polar” first; flow planes are read from its saved solution.'},
  {name:'VSPAEROReadPreviousAnalysis',title:'Reopen solver results',blurb:'Reads the native result files of a finished VSPAERO solution again.',source:true,requires:()=>savedAero()?'':'Run “Lift & drag polar” first.'},
 ]},
 {group:'Meshes & exports',items:[
  {name:'CfdMeshAnalysis',title:'CFD surface mesh',blurb:'Watertight triangle surface mesh for external CFD tools (STL, Cart3D, Wavefront, TetGen, Facet, Gmsh).',essentials:['SelectedSetIndex','BaseLen','MinLen','MaxGap','GrowthRatio','GenerateHalfMesh'],labels:{BaseLen:'Largest triangle edge',MinLen:'Smallest triangle edge'},units:{BaseLen:len,MinLen:len,MaxGap:len},slow:'Can take minutes on detailed models'},
  {name:'SurfaceIntersection',title:'CAD export (STEP / IGES)',blurb:'Intersects all surfaces and writes trimmed CAD solids and curves.',essentials:['SelectedSetIndex','STEPFileFlag','IGESFileFlag','CADLenUnit'],slow:'Can take several minutes where many surfaces meet'},
  {name:'DegenGeom',title:'Degenerate geometry',blurb:'Plate, stick and point representations of each component for low-order tools (CSV and MATLAB).',essentials:['Set']},
  {name:'DegenGeomMesh',title:'Degenerate geometry mesh',blurb:'Mesh of the degenerate plate representation.',essentials:['Set','DegenGeomMeshType']},
  {name:'VSPAEROComputeGeometry',title:'VSPAERO geometry only',blurb:'Writes the panel geometry VSPAERO would use, without solving. Useful to check what the solver sees.',essentials:['ThinGeomSet','GeomSet']},
  {name:'SurfacePatches',title:'Surface patch points',blurb:'Structured grid of points and normals on every surface patch.',essentials:['Set']},
  {name:'FeaMeshAnalysis',title:'Structural mesh',blurb:'Finite-element mesh of one internal structure (ribs, spars, skins) with solver decks.',structure:'structures',requires:m=>m.tools.structures.length?'':'Define a structure in Modeling tools → Structures first.'},
  {name:'FeaAssemblyMesh',title:'Structural assembly mesh',blurb:'Finite-element mesh of a whole assembly of structures with connections.',structure:'assemblies',requires:m=>m.tools.assemblies.length?'':'Define an assembly in Modeling tools → Structures first.'},
 ]},
 {group:'Checks',items:[
  {name:'GeometryAnalysis',title:'Interference & clearance checks',blurb:'Runs the saved geometry-check cases: interference, clearance and similar.',essentials:['CaseID'],requires:m=>m.tools.geometryCases?.length?'':'Create a case in Modeling tools → Geometry checks first.'},
 ]},
 {group:'Textbook references',note:'These do not use your aircraft.',items:[
  {name:'AtmosphereReference',title:'Standard atmosphere',blurb:'Temperature, pressure and density at an altitude.'},
  {name:'HersheyBarTheory',title:'Rectangular wing (lifting line)',blurb:'Spanwise lift and induced drag on an idealized rectangular wing.'},
  {name:'VKTAirfoilTheory',title:'Analytic airfoil',blurb:'Von Kármán–Trefftz airfoil shape and surface pressure.'},
  {name:'EllipsoidFlowTheory',title:'Ellipsoid in flow',blurb:'Exact potential-flow pressure on an ellipsoid.'},
  {name:'DragEquationReference',title:'Skin-friction equations',blurb:'Friction-coefficient and form-factor equations used by the drag buildup.'},
  {name:'EmintonLord',title:'Wave drag from areas',blurb:'Eminton–Lord wave drag for a station/area list you type in.'},
 ]},
];
const ITEMS=Object.fromEntries(CATALOG.flatMap(g=>g.items.map(i=>[i.name,{...i,group:g.group}])));
export const analyzeTitle=n=>ITEMS[n]?.title||n;
// File names written for the engine's own bookkeeping, not results.
const INTERNAL=/^(request|response|analysis-setup|job|worker-exit)\.json$|\.guide\.json$|^engine\.log$|studio-state\.json$/;
const HIDDEN_INPUT=/FileName$|^RedirectFile$|^BEMFileName$/;

// ---------- Shell ----------
export function installAnalyze(context){
 app=context;host=document.getElementById('analyze-page');
 host.innerHTML=`<div class="az">
 <nav class="az-catalog" aria-label="Analyses"><div class="az-catalog-head"><h1>Analyze</h1><input id="az-filter" type="search" placeholder="Find an analysis" aria-label="Find an analysis"></div><div id="az-list"></div><button id="az-classic" class="az-link">Open the classic analysis workspace</button></nav>
 <section class="az-setup" aria-labelledby="az-title"><div id="az-setup-body"></div></section>
 <section class="az-results" aria-label="Results"><div class="az-results-head"><div><span class="az-eyebrow">Result</span><h2 id="az-result-title">No run selected</h2><p id="az-result-meta"></p></div><div class="az-head-actions"><label class="az-history-label" for="az-history">Past runs</label><select id="az-history"></select></div></div><div id="az-result-body"></div></section></div>`;
 $('#az-filter').oninput=renderCatalog;
 $('#az-classic').onclick=()=>document.querySelector('[data-page="analysis"]').click();
 $('#az-history').onchange=e=>e.target.value&&openRun(e.target.value);
 document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{host.hidden=b.dataset.page!=='analyze';document.querySelector('[data-page="analyze"]').classList.toggle('active',['analyze','analysis'].includes(b.dataset.page));if(!host.hidden)show();}));
}

async function show(){
 await refreshJobs();renderCatalog();
 const active=jobsCache.find(j=>j.status==='running'||j.stopping);
 if(active){running=active.id;await choose(active.name,false);openRun(active.id);return;}
 if(!current)await choose('CompGeom');
 else if(schema&&schema.revision!==app.model().revision)await choose(current,false);
}

async function refreshJobs(){try{jobsCache=await app.api('/api/jobs');}catch{jobsCache=[];}renderHistory();return jobsCache;}

function renderCatalog(){
 const m=app.model();if(!m)return;
 const q=$('#az-filter').value.trim().toLowerCase();
 $('#az-list').innerHTML=CATALOG.map(g=>{
  const items=g.items.filter(i=>!q||(i.title+' '+i.blurb+' '+i.name).toLowerCase().includes(q));
  if(!items.length)return'';
  return `<section><h3>${esc(g.group)}</h3>${g.note?`<p>${esc(g.note)}</p>`:''}${items.map(i=>{const need=i.requires?.(m),last=jobsCache.find(j=>j.name===i.name);
   return `<button class="az-item ${i.name===current?'active':''}" data-analysis="${esc(i.name)}" aria-pressed="${i.name===current}"><b>${esc(i.title)}</b><small>${esc(i.blurb.split('.')[0])}.</small><span class="az-tags">${need?'<em class="az-tag warn">Needs setup</em>':''}${i.slow?'<em class="az-tag">Slow</em>':''}${last?`<em class="az-tag ${last.status==='complete'?'ok':last.status==='failed'?'bad':''}">${last.status==='complete'?'Has result':last.status==='failed'?'Last run failed':last.status}</em>`:''}</span></button>`;}).join('')}</section>`;
 }).join('')||'<p class="az-empty">No analysis matches.</p>';
 host.querySelectorAll('[data-analysis]').forEach(b=>b.onclick=()=>choose(b.dataset.analysis));
}

// ---------- Setup ----------
async function choose(name,openLatest=true){
 if(current&&schema)drafts.set(current,new Map(values));
 current=name;const item=ITEMS[name],m=app.model(),token=++generation;
 renderCatalog();
 const need=item.requires?.(m);
 const body=$('#az-setup-body');
 body.innerHTML=`<div class="az-head"><span class="az-eyebrow">${esc(item.group)}</span><h2 id="az-title">${esc(item.title)}</h2><p>${esc(item.blurb)}</p></div><div class="az-loading">Reading settings from OpenVSP…</div>`;
 if(openLatest){const last=jobsCache.find(j=>j.name===name&&j.status!=='cancelled');if(last&&!running)openRun(last.id);else if(!running)clearResult(item);}
 if(need&&!item.source){schema=null;body.querySelector('.az-loading').outerHTML=`<div class="az-callout warn"><b>Not ready yet</b><p>${esc(need)}</p></div>`;return;}
 try{
  const structure=item.structure?m.tools[item.structure][0]?.id:null;
  const s=await app.api('/api/schema?name='+encodeURIComponent(name)+(structure?'&structure='+encodeURIComponent(structure):''));
  const g=item.geometry?await app.api('/api/schema?name=VSPAEROComputeGeometry'):null;
  if(token!==generation)return;
  schema={...s,revision:m.revision};geometrySchema=g;
  values=drafts.get(name)||defaults(s,g,item.preset?.(m)||{});
  renderSetup(structure);
 }catch(e){if(token===generation)body.querySelector('.az-loading').outerHTML=`<div class="az-callout bad"><b>OpenVSP could not prepare this analysis</b><p>${esc(e.message)}</p></div>`;}
}

function defaults(s,g,preset){
 const out=new Map();
 for(const e of s.inputs)out.set(key(e),preset[e.name]&&e.editable?preset[e.name]:e.values);
 for(const e of g?.inputs||[])out.set('geo:'+key(e),e.values);
 return out;
}

const editable=e=>e.editable&&!HIDDEN_INPUT.test(e.name);
function applies(rule,prefix=''){
 if(!rule)return true;
 if(rule.any)return rule.any.some(r=>applies(r,prefix));
 if(rule.all)return rule.all.every(r=>applies(r,prefix));
 const v=values.get(prefix+rule.input+'|0');return !!v&&rule.values.some(x=>String(x)===String(v[0]));
}
// Hide choices that only make sense when the model has them (modes, for example).
function relevant(e){
 const m=app.model();
 if(/^(UseModeFlag|UseMode|UseCGModeFlag)$/.test(e.name)&&!m.tools.modes.length)return false;
 if(e.choices&&e.choices.length===1&&e.choices[0].value==='')return false;
 return true;
}

function renderSetup(structure){
 const item=ITEMS[current],m=app.model(),body=$('#az-setup-body');
 const inputs=schema.inputs.filter(e=>editable(e)&&relevant(e));
 const main=item.essentials?inputs.filter(e=>item.essentials.includes(e.name)).sort((a,b)=>item.essentials.indexOf(a.name)-item.essentials.indexOf(b.name)):schema.standaloneNative||!inputs.length?inputs:inputs.slice(0,6);
 const rest=inputs.filter(e=>!main.includes(e));
 const geo=(geometrySchema?.inputs||[]).filter(e=>editable(e)&&relevant(e));
 const note=item.note?.(m),need=item.requires?.(m);
 const sources=schema.savedSolutions||[];
 body.innerHTML=`<div class="az-head"><span class="az-eyebrow">${esc(item.group)}</span><h2 id="az-title">${esc(item.title)}</h2><p>${esc(item.blurb)}</p></div>
 ${need?`<div class="az-callout warn"><b>Not ready yet</b><p>${esc(need)}</p></div>`:''}
 ${note?`<div class="az-callout"><p>${esc(note)}</p></div>`:''}
 <form id="az-form" novalidate>
 ${item.source?`<div class="az-field"><label for="az-source">Saved solution</label><select id="az-source">${sources.length?sources.map(j=>`<option value="${esc(j.id)}">${esc(analyzeTitle(j.name))} · ${esc(new Date(j.started*1000).toLocaleString())}</option>`).join(''):'<option value="">No finished solution yet</option>'}</select></div>`:''}
 ${item.structure?`<div class="az-field"><label for="az-structure">${item.structure==='assemblies'?'Assembly':'Structure'}</label><select id="az-structure">${m.tools[item.structure].map(s=>`<option value="${esc(s.id)}" ${s.id===structure?'selected':''}>${esc(s.name)}</option>`).join('')}</select></div><fieldset class="az-checks"><legend>Also write</legend>${(schema.exportFormats||[]).filter(f=>f!=='GMSH').map(f=>`<label><input type="checkbox" data-format="${esc(f)}" ${['CALCULIX','NASTRAN','MASS'].includes(f)?'checked':''}> ${esc(f)}</label>`).join('')}</fieldset>`:''}
 <div class="az-fields">${main.map(e=>field(e)).join('')}</div>
 ${rest.length||geo.length?`<details class="az-more"><summary>All engine settings <span>${rest.length+geo.length}</span></summary><p class="az-hint">Defaults come from OpenVSP and the aircraft file. Only values you change are sent.</p><div class="az-fields">${rest.map(e=>field(e)).join('')}</div>${geo.length?`<h4>Solver geometry</h4><div class="az-fields">${geo.map(e=>field(e,'geo:')).join('')}</div>`:''}</details>`:''}
 </form>
 <div class="az-run"><button id="az-run" class="primary" ${need&&!sources.length?'disabled':''}>Run ${esc(item.title.toLowerCase())}</button><button id="az-cancel" hidden>Cancel</button><button id="az-reset" class="az-link" type="button">Reset to defaults</button></div>
 <p id="az-run-status" class="az-run-status" role="status">${item.slow?esc(item.slow)+'.':''}</p>`;
 bindForm();refreshVisibility();
 $('#az-run').onclick=run;$('#az-cancel').onclick=cancel;
 $('#az-reset').onclick=()=>{drafts.delete(current);values=defaults(schema,geometrySchema,item.preset?.(m)||{});renderSetup(structure);};
 const st=$('#az-structure');if(st)st.onchange=async()=>{const s=await app.api('/api/schema?name='+encodeURIComponent(current)+'&structure='+encodeURIComponent(st.value));schema={...s,revision:m.revision};values=defaults(s,null,{});renderSetup(st.value);};
 if(running)setRunning(true);
}

const COMMON={Set:'Components',GeomSet:'Thick components',ThinGeomSet:'Thin components (lifting surfaces)',SelectedSetIndex:'Components',TargetSet:'Components',UseModeFlag:'Choose components by',UseMode:'Choose components by',ModeID:'Mode',HalfMeshFlag:'Mesh',GenerateHalfMesh:'Mesh',NCPU:'Processor cores'};
function label(e){const item=ITEMS[current];return item.labels?.[e.name]||COMMON[e.name]||e.label||e.name.replace(/([a-z])([A-Z])/g,'$1 $2');}
function unit(e){const u=ITEMS[current].units?.[e.name];return typeof u==='function'?u():u||e.unit||'';}
function setOptions(e,v){
 const sets=app.model().tools.sets.filter(s=>s.index<3?s.name!=='Not_Shown'||s.members.length:s.members.length||!/^Set_\d+$/.test(s.name)||s.index===v);
 const name=s=>({All:'All components',Shown:'Shown components',Not_Shown:'Hidden components'}[s.name]||s.name.replace(/_/g,' '));
 return `${e.values[0]===-1||v===-1?`<option value="-1" ${v===-1?'selected':''}>None</option>`:''}${sets.map(s=>`<option value="${s.index}" ${s.index===v?'selected':''}>${esc(name(s))}${s.members.length&&s.index>1?` · ${s.members.length}`:''}</option>`).join('')}`;
}
function field(e,prefix=''){
 const id='az-'+prefix.replace(':','-')+e.name+'-'+e.index,v=values.get(prefix+key(e))??e.values,u=unit(e),k=prefix+key(e);
 const attrs=`id="${id}" data-key="${esc(k)}" data-type="${e.type}"`;
 let control;
 if(e.numericList)control=`<input ${attrs} data-kind="list" type="text" value="${esc(v.join(', '))}" placeholder="e.g. 0, 2.5, 5">`;
 else if(e.choiceList)control=`<select ${attrs} data-kind="multi" multiple size="4">${e.choiceList.map(c=>`<option value="${esc(c.value)}" ${v.includes(c.value)?'selected':''}>${esc(c.label)}</option>`).join('')}</select>`;
 else if(e.type===4&&v.length===1&&Array.isArray(v[0]))control=`<div class="az-vector" data-kind="vector" ${attrs}>${['X','Y','Z'].map((a,i)=>`<label>${a}<input type="number" step="any" value="${esc(v[0][i])}" aria-label="${esc(label(e))} ${a}"></label>`).join('')}</div>`;
 else if(e.choices)control=`<select ${attrs} data-kind="choice">${e.choices.map(c=>`<option value="${esc(c.value)}" ${String(c.value)===String(v[0])?'selected':''}>${esc(c.label)}</option>`).join('')}</select>`;
 else if(e.type===1&&setInputNames.has(e.name))control=`<select ${attrs} data-kind="number">${setOptions(e,v[0])}</select>`;
 else if([1,2].includes(e.type)&&v.length===1)control=`<input ${attrs} data-kind="number" type="number" step="${e.type===1?1:'any'}" ${e.min!=null?`min="${e.min}"`:''} ${e.max!=null?`max="${e.max}"`:''} value="${esc(v[0])}">`;
 else if(e.type===3&&v.length<=1)control=`<input ${attrs} data-kind="text" type="text" value="${esc(v[0]??'')}">`;
 else control=`<textarea ${attrs} data-kind="json" rows="2">${esc(JSON.stringify(v))}</textarea>`;
 const plain=t=>String(t||'').toLowerCase().replace(/[^a-z0-9]/g,'');
 const help=e.description&&plain(e.description)!==plain(e.label)&&!/^Flag to control|^ID for|set for analysis|^Geometry Set| enum\.?$| GeomID\.?$/i.test(e.description)&&e.description!==label(e)?`<small>${esc(e.description)}</small>`:'';
 return `<div class="az-field${ITEMS[current].half?.includes(e.name)?' half':''}" data-rule='${esc(JSON.stringify(e.applicableWhen||null))}' data-prefix="${esc(prefix)}"><label for="${id}">${esc(label(e))}${u?` <span class="az-unit">${esc(u)}</span>`:''}</label>${control}${help}</div>`;
}
function read(el){
 const kind=el.dataset.kind,type=Number(el.dataset.type);
 if(kind==='list'){const t=el.value.trim();return t?t.split(/[,\s]+/).map(Number):[];}
 if(kind==='multi')return [...el.selectedOptions].map(o=>o.value);
 if(kind==='vector')return [[...el.querySelectorAll('input')].map(i=>Number(i.value))];
 if(kind==='json')return JSON.parse(el.value);
 if(kind==='text'||(kind==='choice'&&type===3))return [el.value];
 return [Number(el.value)];
}
function bindForm(){
 host.querySelectorAll('#az-form [data-key]').forEach(el=>{
  const update=()=>{try{values.set(el.dataset.key,read(el));el.closest('.az-field').classList.remove('invalid');}catch{el.closest('.az-field').classList.add('invalid');}refreshVisibility();};
  el.addEventListener(el.tagName==='SELECT'?'change':'input',update);
 });
}
function refreshVisibility(){host.querySelectorAll('#az-form .az-field[data-rule]').forEach(f=>{f.hidden=!applies(JSON.parse(f.dataset.rule),f.dataset.prefix);});}

function changed(spec,prefix=''){
 return (spec?.inputs||[]).filter(e=>editable(e)&&applies(e.applicableWhen,prefix)).flatMap(e=>{
  const v=values.get(prefix+key(e));
  if(!v||JSON.stringify(v)===JSON.stringify(e.values))return[];
  if(v.some(x=>typeof x==='number'&&!Number.isFinite(x))||v.flat().some(x=>typeof x==='number'&&!Number.isFinite(x)))throw Error(`${label(e)}: enter a number.`);
  return [{name:e.name,index:e.index,values:v}];
 });
}

// ---------- Running ----------
async function run(){
 if(running||!schema)return;
 const item=ITEMS[current];
 try{
  const request={name:current,inputs:changed(schema),revision:app.model().revision};
  if(item.geometry)request.geometryInputs=changed(geometrySchema,'geo:');
  if(item.source){request.sourceRun=$('#az-source').value;if(!request.sourceRun)throw Error('Run “Lift & drag polar” first.');}
  if(item.structure){request.structure=$('#az-structure').value;request.formats=[...host.querySelectorAll('[data-format]:checked')].map(e=>e.dataset.format);}
  if(schema.standaloneNative||item.source)request.inputs=schema.inputs.filter(editable).map(e=>({name:e.name,index:e.index,values:values.get(key(e))}));
  const job=await app.api('/api/run',request);
  running=job.id;setRunning(true);await refreshJobs();openRun(job.id);
 }catch(e){status(e.message,'bad');}
}
async function cancel(){if(!running)return;try{await app.api('/api/cancel',{id:running});}catch(e){app.toast(e.message);}}
function setRunning(on){
 const r=host.querySelector('#az-run'),c=host.querySelector('#az-cancel');
 if(r)r.disabled=on;if(c)c.hidden=!on;
 host.querySelectorAll('.az-item').forEach(b=>b.classList.toggle('locked',on));
 clearInterval(clockTimer);
 if(on){const job=jobsCache.find(j=>j.id===running),start=job?.started?job.started*1000:Date.now();const tick=()=>status(`Running ${analyzeTitle(job?.name||current).toLowerCase()} · ${Math.round((Date.now()-start)/1000)} s`);tick();clockTimer=setInterval(tick,1000);}
}
function status(text,kind=''){const el=host.querySelector('#az-run-status');if(el){el.textContent=text;el.className='az-run-status '+kind;}}

// ---------- Results ----------
function renderHistory(){
 const sel=host?.querySelector('#az-history');if(!sel)return;
 sel.innerHTML=`<option value="">${jobsCache.length?'Choose a run…':'No runs yet'}</option>`+jobsCache.slice(0,80).map(j=>`<option value="${esc(j.id)}" ${j.id===viewed?'selected':''}>${esc(analyzeTitle(j.name))} · ${esc(new Date(j.started*1000).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}))}${j.status==='complete'?'':' · '+j.status}</option>`).join('');
}
function clearResult(item){
 viewed=null;clearTimeout(pollTimer);disposeMesh?.();disposeMesh=null;renderHistory();
 $('#az-result-title').textContent='No result yet';$('#az-result-meta').textContent='';
 $('#az-result-body').innerHTML=`<div class="az-empty-state"><p>Run <b>${esc(item.title.toLowerCase())}</b> to see results here.</p><p>Every run is kept with a copy of the aircraft it used, so you can come back to it from <b>Past runs</b>.</p></div>`;
}
async function openRun(id){
 viewed=id;clearTimeout(pollTimer);renderHistory();
 let job;try{job=await app.api('/api/job?id='+encodeURIComponent(id));}catch(e){$('#az-result-body').innerHTML=`<div class="az-callout bad"><p>${esc(e.message)}</p></div>`;return;}
 if(viewed!==id)return;
 const live=job.status==='running'||job.stopping;
 $('#az-result-title').textContent=analyzeTitle(job.name);
 const took=job.finished&&job.started?` · took ${Math.max(1,Math.round(job.finished-job.started))} s`:'';
 $('#az-result-meta').textContent=new Date(job.started*1000).toLocaleString()+took;
 if(live){
  const tail=(job.log||'').trim().split('\n').slice(-12).join('\n');
  $('#az-result-body').innerHTML=`<div class="az-progress"><div class="az-spinner" aria-hidden="true"></div><div><b>${job.stopping?'Stopping…':'OpenVSP is working'}</b><p>The rest of Studio stays usable while this runs.</p></div></div>${tail?`<pre class="az-log">${esc(tail)}</pre>`:''}`;
  pollTimer=setTimeout(()=>openRun(id),1500);return;
 }
 if(running===id){running=null;setRunning(false);status(job.status==='complete'?'Finished.':job.status==='cancelled'?'Cancelled.':'Failed. See the result panel.',job.status==='failed'?'bad':'');await refreshJobs();renderCatalog();}
 disposeMesh?.();disposeMesh=null;
 $('#az-result-body').innerHTML=job.status==='complete'?resultView(job):failureView(job);
 bindResult(job);
}
function failureView(job){
 const raw=job.error||'OpenVSP stopped without a result.',crash=/SIG(SEGV|BUS|ABRT|ILL)/.test(raw);
 const msg=job.status==='cancelled'?'This run was cancelled before it finished.':crash?'OpenVSP crashed while processing this geometry. That is a bug inside the engine, not a problem with your settings. Try a smaller set of components, or simplify where surfaces meet. ('+raw+')':raw;
 return `<div class="az-callout ${job.status==='cancelled'?'':'bad'}"><b>${job.status==='cancelled'?'Cancelled':'The run failed'}</b><p>${esc(msg)}</p></div>${logView(job)}${filesView(job)}`;
}

const R=(job,name)=>job.result?.results?.find(r=>r.name===name);
const named=list=>list.map((n,i)=>{const k=list.filter(x=>x===n).length;return k>1?`${n} (${list.slice(0,i+1).filter(x=>x===n).length})`:n;});
const V=(r,name)=>r?.entries.find(e=>e.name===name)?.values||[];
const S=(r,name)=>V(r,name)[0];
function kpis(list){return `<div class="az-kpis">${list.filter(Boolean).map(([l,v,u])=>`<div><span>${esc(l)}</span><strong>${esc(v)}${u?` <small>${esc(u)}</small>`:''}</strong></div>`).join('')}</div>`;}
function table(cols,rows,cls=''){return `<div class="az-table ${cls}"><table><thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((c,i)=>`<td${i?' class="n"':''}>${typeof c==='number'?esc(num(c)):esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;}
function bars(labels,vals,unitLabel){
 const max=Math.max(...vals.map(Math.abs),1e-12);
 return `<div class="az-bars">${labels.map((l,i)=>`<div><span>${esc(l)}</span><i style="--w:${(Math.abs(vals[i])/max*100).toFixed(1)}%"></i><b>${esc(num(vals[i],3))}${unitLabel?' '+esc(unitLabel):''}</b></div>`).join('')}</div>`;
}
// Small line chart: series = [{label, x:[], y:[]}]
function chart(series,xl,yl){
 const pts=series.flatMap(s=>s.x.map((x,i)=>[x,s.y[i]])).filter(p=>p.every(Number.isFinite));
 if(pts.length<2)return'';
 let [x0,x1]=[Math.min(...pts.map(p=>p[0])),Math.max(...pts.map(p=>p[0]))],[y0,y1]=[Math.min(...pts.map(p=>p[1])),Math.max(...pts.map(p=>p[1]))];
 if(x1===x0){x0-=1;x1+=1;}if(y1===y0){y0-=Math.abs(y0)*.1||1;y1+=Math.abs(y1)*.1||1;}
 const pad=(y1-y0)*.08;y0-=pad;y1+=pad;
 const W=460,H=230,L=52,B=34,T=12,Rm=12,X=x=>L+(x-x0)/(x1-x0)*(W-L-Rm),Y=y=>T+(1-(y-y0)/(y1-y0))*(H-T-B);
 const ticks=(a,b)=>[0,1,2,3,4].map(i=>a+(b-a)*i/4);
 const grid=ticks(y0,y1).map(v=>`<line x1="${L}" x2="${W-Rm}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${L-6}" y="${Y(v)+3}" text-anchor="end">${esc(num(v,3))}</text>`).join('')+ticks(x0,x1).map(v=>`<text x="${X(v)}" y="${H-B+15}" text-anchor="middle">${esc(num(v,3))}</text>`).join('');
 const zero=y0<0&&y1>0?`<line class="zero" x1="${L}" x2="${W-Rm}" y1="${Y(0)}" y2="${Y(0)}"/>`:'';
 const lines=series.map((s,k)=>{const p=s.x.map((x,i)=>[x,s.y[i]]).filter(q=>q.every(Number.isFinite));return `<g class="s${k}"><polyline points="${p.map(q=>X(q[0]).toFixed(1)+','+Y(q[1]).toFixed(1)).join(' ')}"/>${p.map(q=>`<circle cx="${X(q[0]).toFixed(1)}" cy="${Y(q[1]).toFixed(1)}" r="2.6"><title>${esc(num(q[0]))}, ${esc(num(q[1]))}</title></circle>`).join('')}</g>`;}).join('');
 return `<figure class="az-chart"><figcaption>${esc(yl)}</figcaption><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(yl)} versus ${esc(xl)}"><g class="grid">${grid}</g>${zero}${lines}<text class="axis" x="${(L+W-Rm)/2}" y="${H-3}" text-anchor="middle">${esc(xl)}</text></svg>${series.length>1?`<div class="az-legend">${series.map((s,k)=>`<span class="s${k}">${esc(s.label)}</span>`).join('')}</div>`:''}</figure>`;
}

const VIEWS={
 CompGeom(job){
  const r=R(job,'Comp_Geom'),names=named(V(r,'Comp_Name'));
  return kpis([['Total wetted area',num(S(r,'Total_Wet_Area')),area()],['Total volume',num(S(r,'Total_Wet_Vol')),vol()],['Components',names.length],['Triangles',num(S(r,'Total_Num_Tris'),6)]])
  +`<h3>Wetted area by component</h3>`+bars(names,V(r,'Wet_Area'),area())
  +table(['Component','Wetted area','Theoretical area','Volume','Theoretical volume'],names.map((n,i)=>[n,V(r,'Wet_Area')[i],V(r,'Theo_Area')[i],V(r,'Wet_Vol')[i],V(r,'Theo_Vol')[i]]))
  +(V(r,'Meshes_Merged_Names').length?`<p class="az-hint">Open surfaces merged before trimming: ${esc(V(r,'Meshes_Merged_Names').join(', '))}.</p>`:'');
 },
 MassProp(job){
  const r=R(job,'Mass_Properties'),cg=S(r,'Total_CG')||[],names=named(V(r,'Comp_Name'));
  return kpis([['Total mass',num(S(r,'Total_Mass'))],['CG x',num(cg[0]),len()],['CG y',num(cg[1]),len()],['CG z',num(cg[2]),len()],['Ixx',num(S(r,'Total_Ixx'))],['Iyy',num(S(r,'Total_Iyy'))],['Izz',num(S(r,'Total_Izz'))]])
  +`<h3>Mass by component</h3>`+bars(names,V(r,'Comp_Mass'))
  +table(['Component','Mass','Volume','CG x','CG y','CG z','Ixx','Iyy','Izz'],names.map((n,i)=>{const c=V(r,'Comp_CG')[i]||[];return [n,V(r,'Comp_Mass')[i],V(r,'Comp_Vol')[i],c[0],c[1],c[2],V(r,'Comp_Ixx')[i],V(r,'Comp_Iyy')[i],V(r,'Comp_Izz')[i]];}))
  +`<p class="az-hint">Mass is density × volume in whatever units you gave the densities. Inertia is about the total CG.</p>`;
 },
 Projection(job){
  const r=R(job,'Projection'),names=named(V(r,'Comp_Names')),dir=S(r,'Direction')||[1,0,0];
  return kpis([['Projected area',num(S(r,'Area')),area()],['Looking along',`${num(dir[0],2)}, ${num(dir[1],2)}, ${num(dir[2],2)}`]])+outline(r,dir)
  +(names.length?`<h3>Area by component</h3>`+bars(names,V(r,'Comp_Areas'),area()):'')
  +`<p class="az-hint">Component areas overlap, so they add up to more than the total.</p>`;
 },
 PlanarSlice(job){
  const r=R(job,'Slice'),x=V(r,'Slice_Loc'),a=V(r,'Slice_Area'),i=a.indexOf(Math.max(...a));
  return kpis([['Largest slice',num(a[i]),area()],['at',num(x[i]),len()],['Slices',a.length]])+chart([{label:'Area',x,y:a}],`Position (${len()})`,`Cross-section area (${area()})`)+table(['Position','Area'],x.map((v,k)=>[v,a[k]]).map(r=>[num(r[0]),r[1]]));
 },
 ParasiteDrag(job){
  const r=R(job,'Parasite_Drag'),names=named(V(r,'Comp_Label')),cd=V(r,'Comp_CD'),total=cd.reduce((a,b)=>a+b,0)+(S(r,'Excres_CD_Total')||0);
  return kpis([['CD₀ (parasite)',num(total,4)],['Drag area f',num(V(r,'Comp_f').reduce((a,b)=>a+b,0)+(S(r,'Excres_f_Total')||0)),area()],['Reference area',num(S(r,'FC_Sref')),area()],['Airspeed',num(S(r,'FC_Vinf'))],['Altitude',num(S(r,'FC_Alt'))+' '+(S(r,'Alt_Label')||'').replace(/^Altitude ?\(?|\)$/g,'')],['Mach',num(S(r,'FC_Mach'),3)]])
  +`<h3>Share of parasite drag</h3>`+bars(names,V(r,'Comp_PercTotalCD').map(x=>x*100),'%')
  +table(['Component','Wetted area','Reynolds no.','Cf','Form factor','Interference Q','CD','% of total'],names.map((n,i)=>[n,V(r,'Comp_Swet')[i],V(r,'Comp_Re')[i],V(r,'Comp_Cf')[i],V(r,'Comp_FFOut')[i],V(r,'Comp_Q')[i],V(r,'Comp_CD')[i],num(V(r,'Comp_PercTotalCD')[i]*100,3)+'%']));
 },
 VSPAEROSweep(job){
  const polar=R(job,'VSPAERO_Polar');
  if(!polar)return job.result?.executionMode==='setup-only'?'<div class="az-callout"><p>Solver files were written without running VSPAERO. Download them below.</p></div>':'';
  const g=n=>V(polar,n),a=g('Alpha'),cl=g('CLtot'),cd=g('CDtot'),cm=g('CMytot'),ld=g('L_D').length?g('L_D'):cl.map((c,i)=>c/cd[i]),cdi=g('CDi'),cdo=g('CDo'),e=g('E');
  const best=ld.indexOf(Math.max(...ld.filter(Number.isFinite)));
  let slope=null;if(a.length>1){const n=a.length,sx=a.reduce((p,q)=>p+q,0),sy=cl.reduce((p,q)=>p+q,0),sxy=a.reduce((p,q,i)=>p+q*cl[i],0),sxx=a.reduce((p,q)=>p+q*q,0);slope=(n*sxy-sx*sy)/(n*sxx-sx*sx);}
  return kpis([['Best L/D',num(ld[best],3)],['at α',num(a[best],3),'°'],['CL at best L/D',num(cl[best],3)],['Lift slope CLα',slope==null?'—':num(slope,3),'/°'],e.length?['Span efficiency e',num(e[best],3)]:null,['Mach',num(g('Mach')[0],3)]])
  +`<div class="az-charts">${chart([{label:'CL',x:a,y:cl}],'Angle of attack (°)','Lift coefficient CL')}${chart([{label:'Polar',x:cd,y:cl}],'Drag coefficient CD','Drag polar (CL vs CD)')}${chart([{label:'L/D',x:a,y:ld}],'Angle of attack (°)','Lift-to-drag ratio')}${chart([{label:'CMy',x:a,y:cm}],'Angle of attack (°)','Pitching moment CMy')}</div>`
  +table(['α (°)','CL','CD','CDi','CD₀','L/D','CMy'],a.map((x,i)=>[num(x,4),cl[i],cd[i],cdi[i],cdo[i],ld[i],cm[i]]));
 },
 WaveDrag(job){
  const r=R(job,'WaveDrag');
  const cdw=S(r,'CDWave')??S(r,'Wave_Drag_Coeff')??S(r,'CD_Wave');
  return kpis([cdw!=null?['Wave drag CDw',num(cdw,4)]:null,['Mach',num(S(r,'Mach')??S(r,'Mach_Num'),3)],['Reference area',num(S(r,'S_ref')??S(r,'Sref')),area()]])+generic(job,['WaveDrag']);
 },
};
// Projected outline drawn from the native boundary paths.
function outline(r,dir){
 const paths=r.entries.filter(e=>e.name==='Path').map(e=>e.values);if(!paths.length)return'';
 const d=dir.map(Math.abs),ax=d[0]>=d[1]&&d[0]>=d[2]?[1,2]:d[1]>=d[2]?[0,2]:[0,1];
 const pts=paths.flat();const xs=pts.map(p=>p[ax[0]]),ys=pts.map(p=>p[ax[1]]);
 const [x0,x1,y0,y1]=[Math.min(...xs),Math.max(...xs),Math.min(...ys),Math.max(...ys)],s=Math.min(440/(x1-x0||1),200/(y1-y0||1));
 const P=p=>`${(10+(p[ax[0]]-x0)*s).toFixed(1)},${(10+(y1-p[ax[1]])*s).toFixed(1)}`;
 return `<figure class="az-chart az-outline"><figcaption>Silhouette</figcaption><svg viewBox="0 0 ${(x1-x0)*s+20} ${(y1-y0)*s+20}" role="img" aria-label="Projected outline">${paths.map(p=>`<polygon points="${p.map(P).join(' ')}"/>`).join('')}</svg></figure>`;
}
// Fallback: scalars become tiles, equal-length arrays become one table per result.
function generic(job,only){
 const results=(job.result?.results||[]).filter(r=>!only||only.includes(r.name));
 if(!results.length)return'';
 const groups=new Map();for(const r of results){if(!groups.has(r.name))groups.set(r.name,[]);groups.get(r.name).push(r);}
 return [...groups].slice(0,8).map(([name,rs])=>{
  const r=rs[0],skip=/^(Analysis_Duration_Sec|Mesh_GeomID|.*_ID|.*GeomID)$/;
  const scalars=r.entries.filter(e=>e.values.length===1&&!Array.isArray(e.values[0])&&!skip.test(e.name));
  const arrays=r.entries.filter(e=>e.values.length>1&&e.values.every(v=>typeof v!=='object')&&!skip.test(e.name));
  const n=Math.max(0,...arrays.map(e=>e.values.length)),cols=arrays.filter(e=>e.values.length===n).slice(0,8);
  return `<h3>${esc(name.replace(/_/g,' '))}${rs.length>1?` <small>(${rs.length} records, first shown)</small>`:''}</h3>${scalars.length?kpis(scalars.slice(0,12).map(e=>[e.name.replace(/_/g,' '),typeof e.values[0]==='number'?num(e.values[0]):String(e.values[0])])):''}${cols.length?table(cols.map(e=>e.name.replace(/_/g,' ')),Array.from({length:Math.min(n,200)},(_,i)=>cols.map(e=>e.values[i]))):''}`;
 }).join('');
}
function filesView(job){
 const files=(job.artifacts||[]).filter(f=>!INTERNAL.test(f.name)&&!f.name.startsWith('.'));
 if(!files.length)return'';
 const size=b=>b>1e6?(b/1e6).toFixed(1)+' MB':b>1e3?Math.round(b/1e3)+' KB':b+' B';
 const nice=f=>f.name==='aircraft.vsp3'?'Aircraft as analyzed':f.name;
 return `<h3>Files</h3><div class="az-files">${job.result?.results?.length?`<a href="/api/results.csv?id=${encodeURIComponent(job.id)}" download>All results (CSV)</a>`:''}${files.map(f=>`<a href="/api/artifact?id=${encodeURIComponent(job.id)}&file=${encodeURIComponent(f.name)}" download><span>${esc(nice(f))}</span><small>${size(f.size)}</small></a>`).join('')}</div>`;
}
function logView(job){return job.log?.trim()?`<details class="az-raw"><summary>Engine log</summary><pre class="az-log">${esc(job.log.trim().split('\n').slice(-400).join('\n'))}</pre></details>`:'';}
function resultView(job){
 const view=VIEWS[job.name];let main='';
 try{main=view?view(job):generic(job);}catch(e){main=`<div class="az-callout bad"><p>Could not summarize this result (${esc(e.message)}). The raw values are below.</p></div>`;}
 const mesh=job.result?.meshFile||(job.artifacts||[]).find(f=>f.preview)?.name;
 return (main||'<p class="az-hint">This analysis writes files rather than numbers. Download them below.</p>')
  +(mesh?`<div class="az-mesh"><button id="az-show-mesh" data-file="${esc(job.result?.meshFile||mesh)}">Show the mesh in 3D</button><div id="az-mesh-host"></div></div>`:'')
  +filesView(job)
  +(view?`<details class="az-raw"><summary>All values returned by OpenVSP</summary>${generic(job)}</details>`:'')
  +logView(job);
}
function bindResult(job){
 const b=host.querySelector('#az-show-mesh');
 if(b)b.onclick=async()=>{b.disabled=true;b.textContent='Loading mesh…';try{const mesh=await app.api('/api/mesh?id='+encodeURIComponent(job.id)+'&file='+encodeURIComponent(b.dataset.file));const d=mountMeshViewer(host.querySelector('#az-mesh-host'),mesh,esc);disposeMesh=typeof d==='function'?d:null;b.remove();}catch(e){b.disabled=false;b.textContent='Show the mesh in 3D';app.toast(e.message);}};
}
