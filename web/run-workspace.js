import {waveDrawingsCard} from './wave-drawings.js?v=20261012-1';
import {cfdChecksCard,withCfdDrawings,intersectionDrawings,nativeMessagesCard} from './cfd-results.js?v=20261010-123';
import {mountMeshViewer} from './mesh-viewer.js?v=20261010-123';
import {solverSetupCard} from './solver-setup.js?v=20261010-123';
import {drawingMesh} from './structural-preview.js?v=20261010-123';
let app,dispose=null,generation=0;
const $=s=>document.querySelector(s);
function flowPlaneLabel(file,setup,summaries){
 const match=file.match(/\.case\.(-?\d+)\.quad\.(\d+)\.dat$/);
 if(!match)return file;
 const plane=setup?.planes?.find(p=>Number(p.index)===Number(match[2]));
 const saved=summaries?.find(p=>p.file===file);
 const record=saved?.timeAccurate?`Time record ${saved.solutionRecord} · ${saved.solutionLabel}`:`Case ${Math.abs(Number(match[1]))}`;
 return `${record} · ${plane?(['X','Y','Z'][Number(plane.axis)-1]+' = '+plane.position):('Plane '+match[2])}`;
}
export function installRunWorkspace(context){app=context;$('#refresh-history').onclick=()=>refreshHistory();}
export async function refreshHistory(){try{const jobs=await app.api('/api/jobs');$('#run-history-list').innerHTML=jobs.slice(0,60).map(j=>`<button data-open-run="${j.id}"><span><b>${app.esc(app.analysisLabel(j.name))}</b><small>${app.esc(new Date(j.started*1000).toLocaleString())} · ${app.esc(j.revision?.slice(0,8))}</small></span><em class="run-${app.esc(j.status)}">${app.esc(j.status)}</em></button>`).join('')||'<p class="native-tip">Your analysis runs will stay here after a refresh or restart.</p>';document.querySelectorAll('[data-open-run]').forEach(b=>b.onclick=()=>app.open(b.dataset.openRun));return jobs;}catch(e){$('#run-history-list').textContent=e.message;return[];}}
export function clearRunWorkspace(){generation++;if(dispose)dispose();dispose=null;$('#run-files').innerHTML='';}
export function renderRunWorkspace(job){
 clearRunWorkspace();const token=generation,esc=app.esc,setup=job.result?.inputs?job.result:(job.analysisSetup||job.requestedSetup),requestedOnly=!job.result?.inputs&&!job.analysisSetup,artifacts=job.artifacts||[],adb=artifacts.find(f=>f.aeroPreview);
 const timeRecords=[...new Map((job.result?.flowPlanes||[]).filter(p=>p.timeAccurate).map(p=>[p.solutionRecord,p.solutionLabel])).entries()].sort((a,b)=>a[0]-b[0]);
 $('#run-files').innerHTML=`<section class="run-artifacts"><h3>Files from this run</h3><p class="native-tip">Saved with model revision ${esc(job.revision?.slice(0,8))}. Inputs on the left configure your next run.</p>${job.sourceRun?`<p class="native-tip">Uses the saved geometry and pressure database from <button id="open-source-run">source solution ${esc(job.sourceRun.slice(0,8))}</button>.</p>`:''}${job.result?.standaloneNative?'<button id="reuse-reference-inputs">Reuse these reference inputs</button>':setup?.inputs&&(!['FeaAssemblyMesh','FeaMeshAnalysis'].includes(job.name)||job.result?.inputs||job.analysisSetup?.structure||job.requestedSetup?.memberInputs)&&['CfdMeshAnalysis','FeaAssemblyMesh','FeaMeshAnalysis','MassProp','PlanarSlice','Projection','WaveDrag','ParasiteDrag','SurfaceIntersection','BladeElement','EmintonLord','CompGeom','DegenGeom','DegenGeomMesh','SurfacePatches','GeometryAnalysis','VSPAEROComputeGeometry','CpSlicer','VSPAEROReadPreviousAnalysis','FlowPlaneSlicer'].includes(job.name)?`<button id="reuse-run-inputs">${requestedOnly?'Restore recorded overrides':'Reuse saved analysis inputs'}</button>${requestedOnly?'<p class="native-tip">This run retains requested overrides. Other controls use the current aircraft defaults when restored.</p>':''}`:''}${job.result?.meshGenerations===1&&job.result.formats?.length>1?'<p class="native-tip">All selected structural files were exported from the same native mesh.</p>':''}${job.name==='FeaAssemblyMesh'?'<p class="native-tip">Assembly connections are exported in the native solver decks. The viewer shows OpenVSP’s original Gmsh records, which can omit connection-only fixed-point nodes.</p>':''}${job.name==='CfdMeshAnalysis'&&job.result?.nativeSettingOverrides?`<p class="native-tip">Applied native mesh growth ratio: ${esc(job.result.nativeSettingOverrides.GrowthRatio.value)} · XYZ intersection curves: ${job.result.nativeSettingOverrides.XYZIntCurveFlag.value?'On':'Off'}. These values belong to this saved run.</p>`:''}${nativeMessagesCard(job,esc)}${solverSetupCard(job.result?.solverSetup,esc,job.result?.executionMode)}${cfdChecksCard(job,esc)}${artifacts.some(f=>f.flowPreview)?`<details class="flow-plane-results" open><summary>Airflow planes from this solution</summary><p>These are the original solver’s saved Cp and velocity samples. Select a plane, then choose Cp, speed or a velocity component in the viewer.</p>${timeRecords.length?`<label>Saved time <select id="flow-time-record">${timeRecords.map(([index,label])=>`<option value="${index}">${index} · ${esc(label)}</option>`).join('')}</select></label>`:''}${artifacts.filter(f=>f.flowPreview).map(f=>`<button data-flow-file="${esc(f.name)}">Inspect ${esc(flowPlaneLabel(f.name,job.result?.solverSetup,job.result?.flowPlanes))}</button>`).join('')}</details>`:''}${waveDrawingsCard(job,esc)}${job.result?.geometryCaseDrawings?.length?`<details open><summary>Native geometry-check drawings</summary><p>Inspect original result meshes, lines and points saved with each evaluated case.</p>${job.result.geometryCaseDrawings.map(c=>`<div class="tool-actions"><button data-case-drawing="${esc(c.file)}">Inspect ${esc(c.name)}</button><a href="/api/artifact?id=${job.id}&file=${encodeURIComponent(c.file)}" download="${esc(c.file)}">Download native drawing points</a><small>${c.points.toLocaleString()} native point records</small></div>`).join('')}</details>`:''}<div id="solution-cases"></div><div id="mesh-host"></div>
 ${adb&&job.status==='complete'?`<details class="pressure-slices"><summary>Pressure slices from this solution</summary><p>OpenVSP slices the saved solver result. Use positions in this run’s model units.</p><label>Direction <select id="slice-axis"><option value="Y">Y · span stations</option><option value="X">X · longitudinal stations</option><option value="Z">Z · height stations</option></select></label><label>Positions (separated by commas)<input id="slice-positions" value="1, 3, 5"></label><button id="compute-pressure-slices">Compute pressure slices</button></details>`:''}
 ${job.result?.csvFile?`<a class="download-csv" href="/api/artifact?id=${job.id}&file=${encodeURIComponent(job.result.csvFile)}" download="${esc(job.result.csvFile)}">↓ ${job.name==='ParasiteDrag'?'Native drag buildup CSV':['AtmosphereReference','DragEquationReference'].includes(job.name)?'Original native reference CSV':'Native samples CSV'}</a>`:''}${job.result?.airfoilFile?` <a class="download-csv" href="/api/artifact?id=${job.id}&file=${encodeURIComponent(job.result.airfoilFile)}" download="${esc(job.result.airfoilFile)}">↓ Selig airfoil profile</a>`:''}
 <details class="run-downloads"><summary>Download run files (${artifacts.length})</summary><div class="run-file-list">${artifacts.map(f=>`<div><a href="/api/artifact?id=${job.id}&file=${encodeURIComponent(f.name)}" download="${esc(f.name)}">↓ ${esc(f.name)}</a><small>${(f.size/1024).toFixed(1)} KB</small>${f.preview?`<button data-preview-file="${esc(f.name)}">Inspect mesh</button>`:''}${f.aeroPreview?`<button data-aero-file="${esc(f.name)}">Pressure & wake</button>`:''}${f.theoryPreview||f.name.endsWith('.theory.json')?`<button data-theory-file="${esc(f.name)}">Inspect native samples</button>`:''}${f.flowPreview?`<button data-flow-file="${esc(f.name)}">Inspect flow plane</button>`:''}</div>`).join('')}</div></details>${job.status==='complete'&&job.result?.results.length?`<a class="download-csv" href="/api/results.csv?id=${job.id}" download="results.csv">↓ Results CSV</a>`:''}${setup?`<details><summary>${requestedOnly?'Recorded input overrides':'Recorded analysis inputs'}</summary>${['VSPAEROSweep','VSPAEROSinglePoint'].includes(job.name)?'<p class="native-tip">OpenVSP can adjust dependent settings during execution. Native solver histories report the returned flight conditions.</p>':''}<pre>${esc(JSON.stringify({engineOperation:setup.engineOperation||job.name,structure:setup.structure,sourceRun:job.sourceRun,inputs:setup.inputs,geometryInputs:setup.geometryInputs,cuttingPlanes:job.analysisSetup?.cuttingPlanes},null,2))}</pre></details>`:''}</section>`;
 $('#reuse-run-inputs')?.addEventListener('click',()=>app.reuseRunInputs(job));
 $('#reuse-reference-inputs')?.addEventListener('click',()=>app.reuseReferenceInputs(job));
 $('#open-source-run')?.addEventListener('click',()=>app.open(job.sourceRun));
 let previewSequence=0;
 async function preview(file,kind='mesh',caseIndex=1){
  const sequence=++previewSequence;if(dispose)dispose();dispose=null;$('#mesh-host').textContent='Loading native '+(kind==='mesh'||kind==='cfd'?'mesh':'solution')+'…';
  if(kind!=='aero')$('#solution-cases').innerHTML='';
  try{const query='?id='+job.id+'&file='+encodeURIComponent(file)+'&case='+caseIndex;let data;
   try{data=['guide','cfd','case','wave'].includes(kind)?await app.api('/api/artifact'+query):await app.api('/api/'+(kind==='mesh'?'mesh':kind==='theory'?'theory':'aero')+query);}catch(e){
    // Already-running workspace servers can read the saved JSON artifact
    // while their newer dedicated preview route waits for the next restart.
    if(kind!=='theory'||e.message!=='Unknown endpoint.')throw e;
    data=await app.api('/api/artifact'+query);
   }
   if(kind==='cfd'&&job.result.meshFile){const nativeMesh=await app.api('/api/mesh?id='+job.id+'&file='+encodeURIComponent(job.result.meshFile));data=withCfdDrawings(nativeMesh,data);}else if(kind==='cfd')data=intersectionDrawings(data);
   if(kind==='mesh'&&job.name==='CompGeom')data.displayNote='This is the exact native trimmed component mesh from this saved area/volume analysis. Review its merged, removed and degenerate mesh diagnostics and compare tessellation before relying on the results.';
   if(kind==='mesh'&&job.name==='DegenGeomMesh')data.displayNote=job.result?.degenerateMesh?.nativeGeomType==='NGonMesh'?'OpenVSP exported this polygon mesh as triangles for viewing. Download the native VSPGEOM file and companions for polygon data; this engine saves only polygon parameter records in VSP3.':'OpenVSP generated and exported this mesh as triangles. The generated mesh is also preserved in the downloadable degenerate-mesh.vsp3 aircraft.';
   if(token!==generation||sequence!==previewSequence)return;
   if(kind==='case')data=drawingMesh(data);
   if(kind==='wave'){const saved=data,plane=saved.planes.find(p=>p.coneIndex===caseIndex)||saved.planes[0];if(!plane)throw Error('The original engine returned no wave plane drawings.');$('#solution-cases').innerHTML=`<label class="solution-case">Wave cone section <select id="wave-cone-section">${saved.planes.map(p=>`<option value="${p.coneIndex}" ${p.coneIndex===plane.coneIndex?'selected':''}>${p.coneIndex} · θ ${esc(p.thetaDegrees)}° · X ${esc(p.position)}</option>`).join('')}</select></label>`;$('#wave-cone-section').onchange=e=>preview(file,'wave',Number(e.target.value));data=drawingMesh(plane,saved.context);}
   if(['cfd','guide','case','wave'].includes(kind)&&!data.nodes.length){$('#mesh-host').innerHTML='<p class="empty-state">'+esc(data.warnings[0]||'OpenVSP returned no drawing points for this run.')+'</p>';return;}
   if(data.cases){$('#solution-cases').innerHTML=`<label class="solution-case" for="solution-case">Solver case <select id="solution-case">${data.cases.map(c=>`<option value="${c.index}" ${c.index===data.case?'selected':''}>${c.index} · Mach ${c.mach} · α ${c.alpha}° · β ${c.beta}° · ${esc(c.label)}</option>`).join('')}</select></label>`;$('#solution-case').onchange=e=>preview(file,'aero',Number(e.target.value));}
   dispose=mountMeshViewer($('#mesh-host'),data,esc);
  }catch(e){if(token===generation&&sequence===previewSequence)$('#mesh-host').textContent=e.message;}
 }
 $('[data-cfd-results]')?.addEventListener('click',()=>preview(job.result.cfdChecks.drawingFile,'cfd'));
 $('[data-cfd-mesh]')?.addEventListener('click',()=>preview(job.result.meshFile));
 document.querySelectorAll('[data-preview-file]').forEach(b=>b.onclick=()=>preview(b.dataset.previewFile));
 document.querySelectorAll('[data-wave-drawing]').forEach(b=>b.onclick=()=>preview(b.dataset.waveDrawing,'wave',job.result.waveDrawings.selectedCone));
 document.querySelectorAll('[data-case-drawing]').forEach(b=>b.onclick=()=>preview(b.dataset.caseDrawing,'case'));
 document.querySelectorAll('[data-aero-file]').forEach(b=>b.onclick=()=>preview(b.dataset.aeroFile,'aero'));
 document.querySelectorAll('[data-theory-file]').forEach(b=>b.onclick=()=>preview(b.dataset.theoryFile,'theory'));
 document.querySelectorAll('[data-flow-file]').forEach(b=>b.onclick=()=>preview(b.dataset.flowFile,'flow'));
 const timeSelect=$('#flow-time-record');
 if(timeSelect){
  const showTime=()=>{
   const record=Number(timeSelect.value);
   document.querySelectorAll('.flow-plane-results [data-flow-file]').forEach(b=>{
    const plane=job.result.flowPlanes.find(p=>p.file===b.dataset.flowFile);
    b.style.display=plane?.solutionRecord===record?'':'none';
   });
  };
  timeSelect.onchange=()=>{
   showTime();
   const plane=job.result.flowPlanes.find(p=>p.solutionRecord===Number(timeSelect.value));
   if(plane)preview(plane.file,'flow');
  };
  showTime();
 }

 $('#compute-pressure-slices')?.addEventListener('click',async()=>{
  const fields=$('#slice-positions').value.split(',').map(s=>s.trim());const values=fields.map(Number);
  if(!fields.length||fields.some(s=>!s)||values.some(v=>!Number.isFinite(v))){app.toast('Enter finite slice positions separated by commas.');return;}
  const axis=$('#slice-axis').value;
  await app.start({name:'CpSlicer',sourceRun:job.id,inputs:['X','Y','Z'].map(direction=>({name:direction+'SlicePosVec',index:0,values:direction===axis?values:[]}))});
 });
 if(job.result?.meshFile)preview(job.result.meshFile);else if(job.result?.cfdChecks?.drawingFile)preview(job.result.cfdChecks.drawingFile,'cfd');else if(job.result?.theoryFile)preview(job.result.theoryFile,'theory');else if(job.result?.waveDrawings?.enabled)preview(job.result.waveDrawings.file,'wave',job.result.waveDrawings.selectedCone);else if(job.result?.geometryCaseDrawings?.length)preview(job.result.geometryCaseDrawings[0].file,'case');else if(job.result?.guideFile)preview(job.result.guideFile,'guide');else if(job.name==='FlowPlaneSlicer'&&artifacts.some(f=>f.flowPreview))preview(artifacts.find(f=>f.flowPreview).name,'flow');else if(adb)preview(adb.name,'aero');
}
