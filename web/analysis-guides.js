import {projectionOptionInputs} from './projection-defaults.js?v=20261021';
import {waveAreaResults,bindWaveAreaResults} from './wave-area-results.js?v=20261015';
import {parasiteFlightResults} from './parasite-flight-results.js?v=20261012-1';
import {pressureSliceResults} from './saved-solutions.js?v=20261010-123';
import {referenceResults} from './reference-results.js?v=20261011-references';
import {geometryCaseResults} from './geometry-cases.js?v=20261010-123';
import {surfacePatchResults} from './surface-patch-results.js?v=20261010-123';
import {degenerateResults} from './degen-results.js?v=20261010-123';
import {aeroResults} from './aero-results.js?v=20261010-123';
import {bladeResults} from './blade-results.js?v=20261010-123';
// Guides format official input schemas and returned samples; no analysis math.
const guidedNames=new Set(['FlowPlaneSlicer','CfdMeshAnalysis','FeaAssemblyMesh','FeaMeshAnalysis','CpSlicer','VSPAEROReadPreviousAnalysis','GeometryAnalysis','MassProp','PlanarSlice','Projection','WaveDrag','ParasiteDrag','SurfaceIntersection','VSPAEROSweep','VSPAEROComputeGeometry','BladeElement','EmintonLord','CompGeom','DegenGeom','DegenGeomMesh','SurfacePatches']);
export const hasGuide=name=>guidedNames.has(name)||['AtmosphereReference','DragEquationReference'].includes(name);
const $=s=>document.querySelector(s);
const number=x=>typeof x==='number'&&Number.isFinite(x)?Number(x.toPrecision(9)):x===null?'undefined':x;
const display=x=>Array.isArray(x)?x.map(display).join(', '):String(number(x)??'—');
export function setupGuide(spec,esc){
 if(!spec.guide)return'';const g=spec.guide;
 const reference=g.reference?`<div class="guide-reference"><h3>Wave-drag reference area</h3><p>Saved native reference area: <strong>${esc(display(g.reference.value))}</strong> · ${g.reference.source?'native wing reference':'entered area'}. Copying a wing area below saves its current native value as an entered area.</p><label for="guide-reference-area">Reference area (square model units)</label><input id="guide-reference-area" type="number" step="any" min="${g.reference.min}" max="${g.reference.max}" value="${g.reference.value}"><button id="guide-save-reference">Save reference area</button><label for="guide-reference-wing">Copy native wing area</label><select id="guide-reference-wing">${g.reference.wings.map(w=>`<option value="${esc(w.id)}">${esc(w.name)} · ${esc(display(w.area))}</option>`).join('')}</select><button id="guide-copy-reference" ${g.reference.wings.length?'':'disabled'}>Use this wing’s area</button><p class="native-tip">This is an undoable aircraft edit. Flight-condition inputs below are preserved. A copied area stays fixed until you copy or edit it again.</p></div>`:'';
 const preparation=g.preparation?`<div class="guide-reference"><h3>Saved intersection preparation</h3><p>Cubic approximation: ${g.preparation.values.DemoteSurfsCubicFlag?'on':'off'} · Tolerance: ${esc(display(g.preparation.values.CubicSurfTolerance))} · Positive-Y half: ${g.preparation.values.HalfMesh?'on':'off'} · STEP point merging: ${g.preparation.values.STEPMergePoints?'on':'off'}.</p><button id="guide-edit-intersection-settings">Edit saved intersection preparation</button><p class="native-tip">These settings come from the aircraft. Edit them in Modeling tools, then return here. Run-specific inputs below remain separate.</p></div>`:'';
 const mass=g.massComponents?`<details class="guide-mass-settings"><summary>Aircraft mass settings</summary><p>These values come from the saved native aircraft. Edit density, shell and point-mass settings in Design, then return to this analysis.</p>${g.massComponents.map(c=>`<article><h3>${esc(c.name)}</h3><dl>${c.settings.map(p=>`<div><dt>${esc(p.name.replace(/_/g,' '))}</dt><dd>${esc(display(p.value))}</dd></div>`).join('')||'<dt>No mass parameters on this component.</dt>'}</dl><button data-guide-mass-component="${esc(c.id)}">Edit ${esc(c.name)} mass settings</button></article>`).join('')}</details>`:'';
 const members=g.memberSizing?`<details class="guide-mass-settings"><summary>Saved member sizing (${g.memberSizing.length} structures)</summary><p>These are each member’s saved settings before this run. Shared sizing starts from the first member and applies to every member. Choose separate sizing to preserve or edit each member’s own settings.</p><table class="result-table"><thead><tr><th>Structure</th>${['Maximum edge','Minimum edge','Surface gap','Circle target','Growth ratio','Rigorous growth','Positive-Y half'].map(n=>`<th>${n}</th>`).join('')}</tr></thead><tbody>${g.memberSizing.map(m=>`<tr><th>${esc(m.name)} · ${esc(m.component)}</th>${['BaseLen','MinLen','MaxGap','NCircSeg','GrowthRatio','RigorLimit','HalfMeshFlag'].map(n=>`<td>${esc(['RigorLimit','HalfMeshFlag'].includes(n)?m.values[n]?'On':'Off':display(m.values[n]))}</td>`).join('')}</tr>`).join('')}</tbody></table></details>`:'';
 return `<section class="analysis-guide"><h3>${esc(g.title)}</h3><p>${esc(g.note)}</p><p class="native-tip">${spec.standaloneNative?'Reference results use the inputs below.':'Results use the aircraft saved with this run.'} ${esc(g.sensitivityNote||'Compare runs with more slices or sections to check sensitivity.')}${spec.name==='ParasiteDrag'?' Atmosphere choices determine which supplied properties drive parasite drag; its results report the properties OpenVSP actually used.':''}</p>${spec.name==='GeometryAnalysis'?'<button id="guide-edit-geometry-cases">Configure saved geometry checks</button>':''}${g.savedProjectionOptions?'<button id="guide-projection-options">Apply saved projection options</button><p class="native-tip">Copies saved selection types, hull flags and vector. Geometry, mode and boundary references stay as entered below. Reset projection inputs restores the standard options.</p>':''}${reference}${mass}${preparation}${members}</section>`;
}
export function refreshGuideFields(spec,prefix='analysis'){
 const groups=new Set();
 for(const e of spec?.inputs||[]){
  const field=document.getElementById(`${prefix}-${e.name}-${e.index}`)?.closest('.analysis-input');
  if(field?.closest('.guide-fields'))groups.add(field.closest('.guide-fields'));
  const applies=rule=>rule.any?rule.any.some(applies):rule.all?rule.all.every(applies):(()=>{const controller=document.getElementById(`${prefix}-${rule.input}-0`);return controller&&rule.values.some(v=>String(v)===controller.value);})();
  if(field&&e.applicableWhen)field.hidden=!applies(e.applicableWhen);
  if(e.minWhen){const input=document.getElementById(`${prefix}-${e.name}-${e.index}`);if(input)input.min=String(applies(e.minWhen)?e.minWhen.value:e.min);}
 }
 for(const group of groups)group.hidden=![...group.querySelectorAll('.analysis-input')].some(field=>!field.hidden);
}
export function bindGuideFields(spec,prefix='analysis'){
 refreshGuideFields(spec,prefix);
 const controllers=rule=>rule.any?rule.any.flatMap(controllers):rule.all?rule.all.flatMap(controllers):[rule.input];
 for(const input of new Set((spec?.inputs||[]).flatMap(e=>[...e.applicableWhen?controllers(e.applicableWhen):[],...e.minWhen?controllers(e.minWhen):[]])))document.getElementById(`${prefix}-${input}-0`)?.addEventListener('change',()=>refreshGuideFields(spec,prefix));
}
export function bindAeroGeometryCopy(spec,flightPrefix,geometryPrefix,onCopy=()=>{}){
 const first=document.getElementById(`${geometryPrefix}-UseModeFlag-0`);
 if(!first)return;
 const button=document.createElement('button');button.type='button';button.textContent='Use flight geometry selections for preparation';
 button.dataset.aeroGeometryCopy=geometryPrefix;
 first.closest('.guide-fields')?.before(button);
 button.onclick=()=>{
  for(const name of ['UseModeFlag','ModeID','GeomSet','ThinGeomSet','Symmetry']){
   const from=document.getElementById(`${flightPrefix}-${name}-0`),to=document.getElementById(`${geometryPrefix}-${name}-0`);
   if(from&&to)to.value=from.value;
  }
  refreshGuideFields(spec,geometryPrefix);onCopy();
 };
}
export function bindSetupGuide(spec,{saveReference,editComponent,editIntersectionSettings,editGeometryCases,toast}){
 if(!spec.guide)return;
 $('#guide-projection-options')?.addEventListener('click',()=>{try{const entries=projectionOptionInputs(spec);for(const e of entries){const el=document.getElementById('analysis-'+e.name+'-'+e.index);if(el)el.value=e.name==='Direction'?JSON.stringify(e.values):e.values[0];}refreshGuideFields(spec);}catch(error){toast(error.message);}});
 $('#guide-edit-geometry-cases')?.addEventListener('click',()=>editGeometryCases?.());
 $('#guide-edit-intersection-settings')?.addEventListener('click',()=>editIntersectionSettings?.(spec.guide.preparation.id));
 bindGuideFields(spec);
 const save=async body=>{try{await saveReference(body);}catch(e){toast(e.message);}};
 $('#guide-save-reference')?.addEventListener('click',()=>{const text=$('#guide-reference-area').value,value=Number(text);if(!text.trim()||!Number.isFinite(value)){toast('Enter a finite reference area.');return;}save({operation:'analysis-reference',analysis:'WaveDrag',value});});
 $('#guide-copy-reference')?.addEventListener('click',()=>save({operation:'analysis-reference',analysis:'WaveDrag',wing:$('#guide-reference-wing').value}));
 document.querySelectorAll('[data-guide-mass-component]').forEach(b=>b.onclick=()=>editComponent(b.dataset.guideMassComponent));
}
export function guidedResults(results,esc,plotSVG,settings,inputs=[],analysisData={}){
 const references=referenceResults(analysisData,esc,plotSVG);if(references)return references;
 const slices=pressureSliceResults(results,esc,plotSVG);if(slices)return slices;
 const checks=geometryCaseResults(analysisData,esc);if(checks)return checks;
 const patches=surfacePatchResults(results,esc);if(patches)return patches;
 const degenerate=degenerateResults(results,esc,plotSVG,analysisData.degenerateMesh);if(degenerate)return degenerate;
 const integral=results.find(r=>r.name==='EmintonLord');
 if(integral){const stations=inputs.find(e=>e.name==='X_vec')?.values||[],areas=inputs.find(e=>e.name==='Area_vec')?.values||[];const distribution=stations.length&&stations.length===areas.length?`<h4>Saved area distribution</h4>${plotSVG(stations,areas,'Longitudinal station','Cross-sectional area')}`:'';const drag=integral.entries.find(e=>e.name==='Donq')?.values||[],coeff=integral.entries.find(e=>e.name==='Coeff')?.values||[];return `<section class="guided-result" data-guided-result="EmintonLord"><h3>Area-distribution wave drag</h3>${distribution}<div class="result-highlights"><div><span>Native drag area (Donq)</span><strong>${esc(display(drag))}</strong></div></div><p class="native-tip">Drag area uses square model length units. Native integration coefficients below are not an aircraft drag coefficient. Full-precision samples remain in JSON and CSV.</p><section class="guide-result-table"><h4>Native integration coefficients</h4><div class="guide-table-scroll"><table><thead><tr><th>Coefficient index</th><th>Native coefficient</th></tr></thead><tbody>${coeff.map((c,i)=>`<tr><td>${i}</td><td>${esc(display(c))}</td></tr>`).join('')}</tbody></table></div></section></section>`;}
 const blade=bladeResults(results,esc,plotSVG);if(blade)return blade;
 const aero=aeroResults(results,esc,plotSVG);if(aero)return aero;
 const r=results.find(r=>['Mass_Properties','Slice','Projection','WaveDrag','Parasite_Drag','Comp_Geom'].includes(r.name));if(!r)return'';
 const values=(key,index=0)=>r.entries.find(e=>e.name===key&&e.index===index)?.values||[],one=key=>values(key)[0];
 const metrics=keys=>`<div class="result-highlights">${keys.map(([key,label])=>values(key).length?`<div><span>${esc(label)}</span><strong>${esc(display(one(key)))}</strong></div>`:'').join('')}</div>`;
 const table=(title,columns,count)=>`<section class="guide-result-table"><h3>${esc(title)}</h3><div class="guide-table-scroll"><table><thead><tr>${columns.map(([key,label])=>`<th>${esc(label)}</th>`).join('')}</tr></thead><tbody>${Array.from({length:count},(_,i)=>`<tr>${columns.map(([key])=>`<td>${esc(display(values(key)[i]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`;
 const diagnosticKeys=['Num_Open_Meshes_Merged','Num_Open_Meshes_Removed','Num_Degen_Triangles_Removed','Num_Degen_Tris_Removed','Ambiguous_Subsurf_Flag'];
 const diagnostics=r.entries.filter(e=>diagnosticKeys.includes(e.name)&&e.values.some(x=>Number.isFinite(x)&&x!==0));
 const diagnostic=diagnostics.length?`<details class="guide-diagnostics" open><summary>Native geometry diagnostics</summary><ul>${diagnostics.map(e=>`<li>${esc(e.description||e.name)}: ${esc(display(e.values))}</li>`).join('')}</ul><p>Review the reported geometry handling and compare resolution before relying on this run.</p></details>`:'';
 let html='';
 if(r.name==='Comp_Geom'){
  html=metrics([['Total_Wet_Area','Combined wetted area'],['Total_Wet_Vol','Combined volume'],['Total_Theo_Area','Untrimmed component area sum'],['Total_Theo_Vol','Untrimmed component volume sum']])+table('Native component contributions',[['Comp_Name','Component'],['Theo_Area','Untrimmed area'],['Wet_Area','Wetted area'],['Theo_Vol','Untrimmed volume'],['Wet_Vol','Trimmed volume']],values('Comp_Name').length);
  if(values('SubSurf_Name').length)html+=table('Native surface regions',[['SubSurf_Name','Region'],['SubSurf_ID','Native region ID'],['SubSurf_Theo_Area','Untrimmed area'],['SubSurf_Wet_Area','Wetted area']],values('SubSurf_Name').length);
  if(values('Tag_Name').length)html+=`<details><summary>Native surface tags (${values('Tag_Name').length})</summary>${table('Native tagged surface contributions',[['Tag_Name','Surface tag'],['Tag_ID','Native tag ID'],['Tag_Theo_Area','Untrimmed area'],['Tag_Wet_Area','Wetted area']],values('Tag_Name').length)}</details>`;
  html+=metrics([['Total_Num_Meshes','Starting meshes'],['Num_Meshes','Result components'],['Total_Num_Tris','Starting triangles']])+['Meshes_Merged_Names','Meshes_Removed_Names'].map(key=>values(key).length?`<p class="native-tip">${key==='Meshes_Merged_Names'?'Native merged meshes':'Native removed meshes'}: ${esc(display(values(key)))}</p>`:'').join('')+'<p class="native-tip">Areas use square model units; volumes use cubic model units. Native names may repeat for symmetry copies or separately trimmed meshes; rows stay in native order. The viewer shows OpenVSP’s saved trimmed mesh. Its exported region numbers are preserved; they are not replaced with guessed component labels. Review geometry handling and tessellation before relying on these results.</p>';
 }

 if(r.name==='Mass_Properties')html=metrics([['Total_Mass','Total mass'],['Total_Volume','Total volume'],['Total_CG','Center of gravity']])+table('Native component mass and inertia',[['Comp_Name','Component'],['Comp_Mass','Mass'],['Comp_Vol','Volume'],['Comp_CG','Center of gravity (X, Y, Z)'],['Comp_Ixx','Ixx'],['Comp_Iyy','Iyy'],['Comp_Izz','Izz'],['Comp_Ixy','Ixy'],['Comp_Ixz','Ixz'],['Comp_Iyz','Iyz']],values('Comp_Name').length)+metrics(['Ixx','Iyy','Izz','Ixy','Ixz','Iyz'].map(x=>['Total_'+x,'Total '+x]));
 if(r.name==='Slice'){
  html=metrics([['Num_Slices','Native slices'],['Axis_Vector','Native slice direction']])+table('Native slice samples',[['Slice_Loc','Native slice location'],['Slice_Area','Area'],['Slice_Area_Center','Area centroid (X, Y, Z)']],values('Slice_Area').length);
  const locations=values('Slice_Loc'),areas=values('Slice_Area');
  if(locations.every(Number.isFinite)&&locations.length===areas.length)html+=`<section class="guide-slice-plots"><h3>Native cross-sectional area distribution</h3>${plotSVG(locations,areas,'Native slice location','Native slice area')}<p class="native-tip">Locations and areas are the exact native samples along the reported slice direction.</p></section>`;
 }
 if(r.name==='Projection')html=metrics([['Area','Combined projected area'],['Direction','Native direction']])+table('Native component projection',[['Comp_Names','Component'],['Comp_Areas','Projected area']],values('Comp_Names').length)+'<p class="native-tip">Component projections can overlap. The combined area above is OpenVSP’s union or clipped result. The outline viewer shows its native boundary paths.</p>';
 if(r.name==='WaveDrag'){
  html=waveAreaResults(analysisData.waveReferenceCurves,esc)+metrics([['CDWave','Wave drag coefficient'],['Mach','Mach'],['Num_Cone_Sections','Cone sections'],['Num_Slices','Axial slices'],['Inlet_Area','Inlet area'],['Exit_Area','Exit area']])+(settings?`<p class="native-tip">Native reference area used for this run: <strong>${esc(display(settings.Sref))}</strong>.</p>`:'')+table('Native cone-section results',[['Theta','Cone angle'],['Start_X','Start X'],['End_X','End X'],['Length','Length'],['MaxArea','Maximum area'],['Volume','Volume']],values('Theta').length);
  const slices=r.entries.filter(e=>e.name==='Slice_Area'),x=values('X_Norm');
  html+=`<details class="guide-wave-sections" open><summary>Native area distributions (${slices.length} sections)</summary>${slices.map(e=>`<section><h4>Section ${e.index} · native angle ${esc(display(values('Theta')[e.index]))}</h4>${x.length===e.values.length?plotSVG(x,e.values,'Native normalized X','Section area'): '<p>Native coordinate and area arrays have different lengths; inspect the exact arrays below.</p>'}</section>`).join('')}</details>`;
 }
 if(r.name==='Parasite_Drag')html=metrics([['Total_CD_Total','Total parasite CD'],['Geom_CD_Total','Geometry CD'],['Excres_CD_Total','Excrescence CD'],['FC_Sref','Native reference area'],['FC_Mach','Native Mach'],['FC_Vinf',one('Vinf_Label')||'Airspeed']])+table('Native component drag buildup',[['Comp_Label','Component'],['Comp_Swet',one('Swet_Label')||'Wetted area'],['Comp_Lref',one('Lref_Label')||'Reference length'],['Comp_Re','Reynolds number'],['Comp_Cf','Friction coefficient'],['Comp_FFEqnName','Form-factor method'],['Comp_FFOut','Form factor'],['Comp_Q','Interference factor'],['Comp_CD','CD'],['Comp_PercTotalCD','Fraction of total CD']],values('Comp_Label').length)+table('Native excrescences',[['Excres_Label','Name'],['Excres_Type','Native type'],['Excres_Input','Input'],['Excres_Amount','Amount']],values('Excres_Label').length)+`<p class="native-tip">${esc(one('LamCfEqnName')||'')} · ${esc(one('TurbCfEqnName')||'')}. Atmosphere and reference values in the full native results describe this saved run.</p>`;
 if(r.name==='Parasite_Drag')html+=parasiteFlightResults(r,esc);
 return `<section class="guided-result" data-guided-result="${esc(r.name)}"><h3>${esc({Comp_Geom:'Component areas and volumes',Mass_Properties:'Mass properties',Slice:'Cross-sectional areas',Projection:'Projected area',WaveDrag:'Wave drag',Parasite_Drag:'Parasite drag buildup'}[r.name])}</h3>${html}${diagnostic}<p class="native-tip">${r.name==='Parasite_Drag'?'Buildup summaries are rounded for reading; the flight-condition table retains saved precision.':'Displayed values are rounded for reading.'} Full-precision native arrays remain in the result tables, JSON and CSV.</p></section>`;
}

export function bindGuidedResults(data={}){
 bindWaveAreaResults(data.waveReferenceCurves,x=>String(x).replace(/[&<>"\']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])));
 document.querySelectorAll('.guided-result svg:not([data-wave-reference-chart])').forEach((svg,i)=>{const button=document.createElement('button');button.textContent='Download this native plot';button.className='guide-plot-export';svg.after(button);button.onclick=()=>{const copy=svg.cloneNode(true);copy.setAttribute('xmlns','http://www.w3.org/2000/svg');copy.setAttribute('style','font:12px sans-serif;background:white');const url=URL.createObjectURL(new Blob([copy.outerHTML],{type:'image/svg+xml'})),a=document.createElement('a');a.href=url;a.download=`native-analysis-plot-${i+1}.svg`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};});
}
