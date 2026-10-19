const key='openvsp-studio-display-units-v1';
export const lengthUnits={model:['Model units',null],m:['Meters',1],cm:['Centimeters',.01],mm:['Millimeters',.001],ft:['Feet',.3048],in:['Inches',.0254]};
let settings={base:'ft',length:'ft',angle:'deg'};
try{const old=JSON.parse(localStorage.getItem(key));if(old&&lengthUnits[old.base]&&lengthUnits[old.length]&&['deg','rad'].includes(old.angle))settings=old;}catch{}
// Only explicitly identified dimensions are converted. Native normalized
// coordinates, ratios, flags, solver settings and unknown parameters stay native.
export function parameterDimension(p){
 if(p.type!==0)return null;
 if(['length','area','volume','angle'].includes(p.dimension))return p.dimension;
 if(p.rawGroup==='XForm'){
  if(/^[XYZ]_(Rel_)?Location$/.test(p.name))return 'length';
  if(/^[XYZ]_(Rel_)?Rotation$/.test(p.name))return 'angle';
 }
 if(p.rawGroup==='WingGeom')return ({TotalSpan:'length',TotalProjectedSpan:'length',TotalChord:'length',MAC:'length',TotalArea:'area',CurvedArea:'area'})[p.name]||null;
 if(p.rawGroup==='Design')return ({Length:'length',Diameter:'length',Beta34:'angle'})[p.name]||null;
 if(p.rawGroup==='XSec'||/^XSec_\d+$/.test(p.rawGroup))return ({Span:'length',ProjectedSpan:'length',Root_Chord:'length',Tip_Chord:'length',Avg_Chord:'length',Area:'area',Sweep:'angle',Sec_Sweep:'angle',Dihedral:'angle',Twist:'angle'})[p.name]||null;
 return null;
}
export function displayFactor(dimension){
 if(dimension==='angle')return settings.angle==='rad'?Math.PI/180:1;
 if(!['length','area','volume'].includes(dimension)||settings.base==='model'||settings.length==='model')return 1;
 return (lengthUnits[settings.base][1]/lengthUnits[settings.length][1])**({length:1,area:2,volume:3}[dimension]);
}
export function unitSuffix(dimension){
 if(dimension==='angle')return settings.angle==='rad'?'rad':'°';
 if(!['length','area','volume'].includes(dimension))return '';
 const unit=settings.base==='model'||settings.length==='model'?'model units':settings.length;
 return unit+({length:'',area:'²',volume:'³'}[dimension]);
}
export function displayValue(value,dimension){return value*displayFactor(dimension);}
export function nativeValue(value,dimension){return value/displayFactor(dimension);}
export function modelLengthUnit(){return settings.base==='model'?'model length':settings.base;}
export function unitsSummary(){return unitSuffix('length')+' · '+(settings.angle==='deg'?'Degrees':'Radians');}
export function installDisplayUnits({modal,changed,esc}){
 const button=document.getElementById('workspace-units'),footer=document.getElementById('footer-units');
 function update(){button.textContent='Units: '+unitsSummary();footer.textContent='Geometry: '+unitsSummary();}
 button.onclick=()=>{
  const choices=(selected)=>Object.entries(lengthUnits).map(([id,[name]])=>`<option value="${id}" ${selected===id?'selected':''}>${esc(name)}</option>`).join('');
  modal('Geometry units',`<p>OpenVSP geometry uses a length convention chosen when the aircraft was built. Tell Studio what one model unit means, then choose how to display dimensions.</p><div class="tool-field"><label for="unit-base">Length of one model unit</label><select id="unit-base">${choices(settings.base)}</select></div><div class="tool-field"><label for="unit-length">Display lengths in</label><select id="unit-length">${choices(settings.length)}</select></div><div class="tool-field"><label for="unit-angle">Display angles in</label><select id="unit-angle"><option value="deg" ${settings.angle==='deg'?'selected':''}>Degrees</option><option value="rad" ${settings.angle==='rad'?'selected':''}>Radians</option></select></div><p class="native-tip" id="unit-help"></p><p>Applies to labeled dimensions in Design, the wing metrics, and guided section blending. Other modeling tools, analyses, and downloaded files retain their native units. These preferences are saved in this browser; check the model convention when opening a different aircraft. Changing display units preserves the aircraft’s dimensions.</p><button id="apply-units" class="primary">Apply display units</button>`);
  const base=document.getElementById('unit-base'),length=document.getElementById('unit-length'),help=document.getElementById('unit-help');
  const explain=()=>{length.disabled=base.value==='model';help.textContent=base.value==='model'?'Choose the model’s length convention to enable metric or imperial display.':'One native model unit represents one '+({m:'meter',cm:'centimeter',mm:'millimeter',ft:'foot',in:'inch'})[base.value]+'.';};base.onchange=()=>{if(base.value!=='model'&&length.value==='model')length.value=base.value;explain();};explain();
  document.getElementById('apply-units').onclick=()=>{settings={base:base.value,length:base.value==='model'?'model':length.value,angle:document.getElementById('unit-angle').value};try{localStorage.setItem(key,JSON.stringify(settings));}catch{}document.getElementById('modal').close();update();changed();};
 };update();
}
