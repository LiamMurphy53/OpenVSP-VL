const sections=[['Curves and regions',['IntersectSubSurfs','RelCurveTol','ExportRawFlag']],['Default native files',['SRF_Export','CURV_Export','PLOT3D_Export','IGES_Export','STEP_Export']],['CAD units and labels',['CADLenUnit','CADLabelDelim','CADLabelID','CADLabelName','CADLabelSurfNo','CADLabelSplitNo']],['STEP representation',['STEPRepresentation','STEPTol']]];
export function intersectionDefaults(group,h){
 const p=Object.fromEntries(group.exportDefaults.params.map(p=>[p.name,p]));
 const control=name=>p[name].choices?h.select(p[name].label,'intersection-default-'+name,p[name].choices.map(c=>[c.value,c.label]),p[name].value):h.field(p[name].label,'intersection-default-'+name,p[name].value);
 return h.card('Saved intersection export defaults',`<p>These settings supply native defaults for future runs. Per-run inputs can override them.</p>${sections.map(([title,names])=>`<fieldset class="guide-fields"><legend>${h.E(title)}</legend><div class="tool-fields">${names.map(control).join('')}</div></fieldset>`).join('')}<p class="native-tip">OpenVSP supplies initial output filenames from the aircraft. Choose filenames in Analyze for each saved run. The native engine generates the curves and CAD files; inspect its messages and check CAD topology in the receiving tool.</p>${h.button('save-intersection-defaults','Apply export defaults',true)}`,'wide');
}
export function bindIntersectionDefaults(group,h){
 const input=n=>document.getElementById('intersection-default-'+n);
 for(const p of group.exportDefaults.params){const e=input(p.name);if(e.type==='number'){e.min=p.min;e.max=p.max;e.step=p.type===1?'1':'any';}}
 const update=()=>{
  const cad=Number(input('IGES_Export').value)||Number(input('STEP_Export').value),step=Number(input('STEP_Export').value);
  for(const n of ['CADLenUnit','CADLabelDelim','CADLabelID','CADLabelName','CADLabelSurfNo','CADLabelSplitNo'])input(n).disabled=!cad;
  for(const n of ['STEPRepresentation','STEPTol'])input(n).disabled=!step;
 };
 input('IGES_Export').onchange=update;input('STEP_Export').onchange=update;update();
 h.bind('save-intersection-defaults',()=>h.mutate({operation:'intersection-defaults',values:Object.fromEntries(group.exportDefaults.params.filter(p=>!input(p.name).disabled).map(p=>[p.name,h.num('intersection-default-'+p.name)]))}));
}
