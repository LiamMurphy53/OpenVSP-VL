// These controls only name and organize parameters returned by OpenVSP.
// Every edit still submits the original parameter ID and native value.
export function geometryTypeLabel(type){
 const names={WING:'Wing',FUSELAGE:'Fuselage',POD:'Pod / fairing',PROP:'Propeller',STACK:'Section stack',ELLIPSOID:'Ellipsoid',BODYOFREVOLUTION:'Body of revolution',BLANK:'Reference / point mass',HINGE:'Hinge / folding joint',CONFORMAL:'Conformal surface',GEAR:'Landing gear',ROUTING:'Routing path',AUXILIARY:'Auxiliary geometry',COBRA:'Cobra body',HUMAN:'Human',MESH:'Imported mesh',WIREFRAME:'Imported wire geometry',PTCLOUD:'Point cloud',BOX:'Box',BOXGROUP:'Box array',DUCT:'Duct',DISK:'Disk',CONE:'Cone',TRANSPORTFUSE:'Transport fuselage',ONOFFEXAMPLE:'Conditional component example'};
 return names[type.toUpperCase()]||type;
}
export function geometryControlGroups(component){
 const find=(group,name,label,choices)=>{const p=component.params.find(p=>p.rawGroup===group&&p.name===name);return p?{...p,label,...(choices?{choices}:{})}:null;};
 const kind=component.type.toUpperCase(),fields=kind==='WING'?[
  ['WingGeom','TotalSpan','Span'],['WingGeom','TotalProjectedSpan','Projected span'],['WingGeom','TotalArea','Planform area'],['WingGeom','TotalAR','Aspect ratio'],['WingGeom','TotalChord','Average chord']
 ]:kind==='FUSELAGE'?[
  ['Design','Length','Body length']
 ]:kind==='POD'?[
  ['Design','Length','Pod length']
 ]:kind==='ELLIPSOID'?[
  ['Design','A_Radius','X radius'],['Design','B_Radius','Y radius'],['Design','C_Radius','Z radius']
 ]:['PROP','PROPELLER'].includes(kind)?[
  ['Design','Diameter','Diameter'],['Design','NumBlade','Number of blades'],['Design','UseBeta34Flag','Pitch driver',[[1,'Pitch at ¾ radius'],[0,'Feather angle']]],component.params.find(p=>p.rawGroup==='Design'&&p.name==='UseBeta34Flag')?.value===0?['Design','Feather','Feather angle']:['Design','Beta34','Pitch at ¾ radius']
 ]:[];
 const library=['CUSTOM','BOX','BOXGROUP','DUCT','DISK','CONE','TRANSPORTFUSE','ONOFFEXAMPLE'].includes(kind)||kind.startsWith('STUDIOPART_');
 const size=library?component.params.filter(p=>p.rawGroup==='Design'):fields.map(args=>find(...args)).filter(Boolean);
 if(kind==='POD'){const ratio=size.find(p=>p.name==='FineRatio');if(ratio)ratio.description='OpenVSP 3.52.2 uses length / radius here. For length / diameter, use half this value.';}
 const mode=find('XForm','Abs_Or_Relitive_flag','Coordinate reference',[[0,'Global coordinates'],[1,'Relative to attachment']]);
 if(mode)mode.description='Choose how position and orientation are specified.';
 const relative=mode?.value===1,position=['X','Y','Z'].map(a=>find('XForm',a+(relative?'_Rel_Location':'_Location'),a+' position')).filter(Boolean);
 const rotation=['X','Y','Z'].map(a=>find('XForm',a+(relative?'_Rel_Rotation':'_Rotation'),a+' rotation')).filter(Boolean);
 const placement=[mode,...position,...rotation,find('XForm','Scale','Scale factor')].filter(Boolean);
 const symmetry=[['Sym_Planar_Flag','Mirror planes'],['Sym_Axial_Flag','Rotation axis'],['Sym_Rot_N','Number of rotation copies'],['Sym_Ancestor','Symmetry reference'],['Sym_Ancestor_Origin_Flag','Reference origin']].map(([name,label])=>find('Sym',name,label)).filter(Boolean);
 const mass=component.params.filter(p=>p.rawGroup==='Mass_Props'),massOrder=['Density','Shell_Flag','Mass_Area','Mass_Prior','PointMass','CGx','CGy','CGz','Ixx','Iyy','Izz','Ixy','Ixz','Iyz'];
 const massFields=massOrder.map(name=>mass.find(p=>p.name===name)).filter(Boolean);
 const byID=new Map(component.params.map(p=>[p.id,p]));
 const family=(component.familyControls||[]).map(g=>({...g,parameters:g.parameters.map(id=>byID.get(id)).filter(Boolean)}));
 return [
  ...(size.length?[{title:'Size & shape',open:true,note:'Labeled dimensions use your chosen display units. OpenVSP updates related dimensions after each edit.',parameters:size}]:[]),
  ...family.filter(g=>g.open),
  ...(placement.length?[{title:'Placement',open:!size.length,note:relative?'Position and rotation follow the component’s native attachment reference.':'Position and rotation use the aircraft’s global axes.',parameters:placement}]:[]),
  ...(kind!=='HINGE'&&symmetry.length?[{title:'Symmetry & repeated components',open:false,note:'OpenVSP generates physical mirror and rotation copies of this component. XY mirrors across Z, XZ across Y and YZ across X. The rotation count includes the original. Choose global axes, this component or an ancestor as the reference; its attachment or component origin sets the symmetry frame.',parameters:symmetry}]:[]),
  ...(kind!=='HINGE'&&massFields.length?[{title:'Mass inputs',open:false,note:'Volume density, shell area density and overlap priority feed the native Mass properties calculation. Additional point mass and its location describe equipment such as batteries or avionics; XYZ is local to this component. Density, mass and inertia retain native units—use one consistent mass and length convention across the aircraft. Labeled XYZ follows your length display preference.',parameters:massFields}]:[]),
  ...family.filter(g=>!g.open)
 ];
}

export function podDiameterMarkup(c,{esc:E,displayValue,unitSuffix}){
 if(c.type.toUpperCase()!=='POD')return '';
 const length=c.params.find(p=>p.rawGroup==='Design'&&p.name==='Length'),ratio=c.params.find(p=>p.rawGroup==='Design'&&p.name==='FineRatio');
 if(!length||!ratio)return '';
 const diameter=2*length.value/ratio.value;
 return `<label class="tool-field" for="pod-diameter">Pod diameter (${E(unitSuffix('length'))})<input id="pod-diameter" aria-label="Pod diameter" type="number" step="any" min="${displayValue(2*length.value/ratio.max,'length')}" max="${displayValue(2*length.value/ratio.min,'length')}" value="${Number(displayValue(diameter,'length').toPrecision(12))}" ${length.value>0?'':'disabled'}><small>Maximum body diameter before component transforms.</small></label><label class="tool-field" for="pod-fineness">Fineness ratio<input id="pod-fineness" aria-label="Fineness ratio" type="number" step="any" min="${ratio.min/2}" max="${ratio.max/2}" value="${Number((ratio.value/2).toPrecision(12))}"><small>Length divided by diameter.</small></label>`;
}
