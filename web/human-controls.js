import {mountMeshViewer} from './mesh-viewer.js?v=20261010-123';
import {drawingMesh} from './structural-preview.js?v=20261010-123';
let inspectionCleanup=null;
// Crew workflows are deferred while the workspace focuses on autonomous aircraft.
export const crewToolsEnabled=false;
export function disposeHumanInspection(){if(inspectionCleanup){inspectionCleanup();inspectionCleanup=null;}}
const body=['LenUnit','MassUnit','GenderFlag','Stature','Mass','Age','SitFrac'];
const distribution=['Stature_pct','BMI','BMI_pct'];
const right=['ShoulderABADRt','ShoulderFERt','ShoulderIERt','ElbowRt','ForearmRt','WristRt','HipABADRt','HipFERt','KneeRt','AnkleRt'];
const left=right.map(n=>n.replace(/Rt$/,'Lt'));
const middle=['Back','Waist','Nod','RotateHead'];
export function humanPromotedIDs(c){return crewToolsEnabled&&c.humanControls?c.params.filter(p=>['Anthropometric','Pose'].includes(p.rawGroup)||p.name==='Density').map(p=>p.id):[];}
export function humanControlsMarkup(c,{esc:E,parameterField:field,nativeAngles=false}){
 if(!crewToolsEnabled||!c.humanControls)return '';
 const fields=names=>names.map(n=>c.params.find(p=>p.name===n)).filter(Boolean).map(p=>field(nativeAngles&&p.dimension==='angle'?{...p,label:p.label+' (degrees)'}:p)).join('');
 const preset=c.params.find(p=>p.name==='PresetPose');
 return `<details class="parameter-group geometry-primary" data-group="human-body" open><summary>Human size &amp; body model</summary><p class="native-tip">Human units control size values and generated coordinates. Match the aircraft’s length convention. Geometry display units elsewhere do not change this native choice. OpenVSP updates the related stature, percentiles, BMI and mass after each edit.</p>${fields(body)}<details data-group="human-distribution"><summary>Body proportions &amp; percentiles</summary><p class="native-tip">Percentiles use fractions from 0.05 to 0.95. These are OpenVSP’s native body-model distributions.</p>${fields(distribution)}</details><details data-group="human-density"><summary>Calculated volume &amp; density</summary>${fields(['Volume','AutoDensity','Density'])}</details></details>
 <details class="parameter-group geometry-primary" data-group="human-pose" open><summary>Human pose</summary><p class="native-tip">Apply a standing or sitting preset, then adjust the joints. Presets reset the native joint angles and enable matching left and right sides. Undo restores the previous pose.</p><label class="tool-field">Pose preset<select id="human-preset-choice" aria-label="Pose preset">${[[0,'Standing'],[1,'Sitting']].map(([v,s])=>`<option value="${v}" ${preset.value===v?'selected':''}>${s}</option>`).join('')}</select></label><button id="human-preset-apply">Apply native pose</button>${fields(['RLSym'])}<details data-group="human-torso" open><summary>Torso &amp; head</summary>${fields(middle)}</details><details data-group="human-right"><summary>Right arm &amp; leg</summary>${fields(right)}</details><details data-group="human-left"><summary>Left arm &amp; leg</summary><p class="native-tip">Left joints follow the right side while matching is on.</p>${fields(left)}</details></details>
 <details class="parameter-group" data-group="human-eye"><summary>Native design-eye locations</summary><p class="native-tip">OpenVSP’s design-eye points in world XYZ, including physical symmetry copies. Coordinates use the aircraft model convention.</p><table><thead><tr><th>Copy</th><th>X</th><th>Y</th><th>Z</th></tr></thead><tbody>${c.humanControls.eyes.map((p,i)=>`<tr><td>${i+1}</td>${p.map(x=>`<td>${E(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></details>${humanSkeletonMarkup(c,{esc:E,parameterField:field})}`;
}
export function humanSkeletonMarkup(c,{esc:E,parameterField:field}){
 if(!crewToolsEnabled||!c.humanControls)return '';
 return `<details class="parameter-group" data-group="human-skeleton"><summary>Inspect native skeleton</summary><p class="native-tip">Standing reference and current pose in native body coordinates (${E(c.humanControls.lengthUnit)}). Placement, attachment and aircraft symmetry are shown in the main Model view; this inspection shows the original body-frame joint lines.</p>${field(c.params.find(p=>p.name==='ShowSkelFlag'))}<button id="human-skeleton-download">Download native skeleton points</button><div id="human-skeleton-view"></div></details>`;
}
export function bindHumanControls(c,mutate,E,root){
 disposeHumanInspection();
 if(!crewToolsEnabled)return;
 const b=root.querySelector('#human-preset-apply');if(b)b.onclick=()=>mutate({operation:'human-preset',geom:c.id,preset:Number(root.querySelector('#human-preset-choice').value)});
 const host=root.querySelector('#human-skeleton-view');if(!host)return;
 const records=c.humanControls.skeleton,visible=records.filter(o=>o.visible&&o.points.length);
 if(visible.length){const mesh=drawingMesh({parts:visible.map((o,i)=>({index:i,name:o.label,objects:[o]})),warnings:[],filename:'Human skeleton · body coordinates',displayNote:'Original OpenVSP standing and posed joint-line records. Native body coordinates ('+c.humanControls.lengthUnit+').'});inspectionCleanup=mountMeshViewer(host,mesh,E);}
 else host.innerHTML='<p class="native-tip">Turn Show native skeleton on to inspect the original joint lines. If the aircraft component or native feature lines are hidden, enable their visibility.</p>';
 root.querySelector('#human-skeleton-download').onclick=()=>{const data={component:{id:c.id,name:c.name},coordinateFrame:c.humanControls.skeletonFrame,lengthUnit:c.humanControls.lengthUnit,objects:records},url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='human-skeleton.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
}
