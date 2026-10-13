const names=['DemoteSurfsCubicFlag','CubicSurfTolerance','HalfMesh','STEPMergePoints'];
export function intersectionSelection(group,d,h){
 const c=group.selection,p=Object.fromEntries(c.params.map(p=>[p.name,p]));
 const sets=name=>[[-1,'None'],...d.sets.map(s=>[s.index,`${s.name} (${s.index})`])].filter(([i])=>i>=p[name].min&&i<=p[name].max);
 const modes=[['','Choose a mode'],...d.modes.map(m=>[m.id,m.name])];
 if(c.mode&&!d.modes.some(m=>m.id===c.mode))modes.push([c.mode,'Unavailable mode · '+c.mode]);
 return h.card('Saved intersection geometry',`<p>Choose the native selection used as the starting point for future intersection runs. Run inputs can override it.</p><div class="tool-fields">${h.select('Geometry selection','intersection-selection-UseMode',[[0,'Geometry sets'],[1,'Native mode']],p.UseMode.value)}${h.select('Intersection mode','intersection-selection-mode',modes,c.mode)}${h.select('Normal geometry set','intersection-selection-Set',sets('Set'),p.Set.value)}${h.select('Thin geometry set','intersection-selection-DegenSet',sets('DegenSet'),p.DegenSet.value)}</div><p class="native-tip">A mode supplies its own sets and applies its saved presets during native execution. Selecting it here saves the reference without applying those presets to the aircraft.</p>${h.button('save-intersection-selection','Apply intersection geometry',true)}${c.mode?h.button('clear-intersection-mode','Clear saved mode and use sets'):''}`,'wide');
}
export function bindIntersectionSelection(group,h){
 const input=n=>document.getElementById('intersection-selection-'+n);
 const update=()=>{const mode=Number(input('UseMode').value);input('mode').disabled=!mode;input('Set').disabled=!!mode;input('DegenSet').disabled=!!mode;};
 input('UseMode').onchange=update;update();
 h.bind('clear-intersection-mode',()=>h.mutate({operation:'intersection-selection',values:{UseMode:0,Set:h.num('intersection-selection-Set'),DegenSet:h.num('intersection-selection-DegenSet')},mode:''}));
 h.bind('save-intersection-selection',()=>h.mutate({operation:'intersection-selection',values:Object.fromEntries(group.selection.params.filter(p=>!input(p.name).disabled).map(p=>[p.name,h.num('intersection-selection-'+p.name)])),mode:h.val('intersection-selection-mode')}));
}
export function intersectionSettings(group,h){
 const p=Object.fromEntries(group.params.map(p=>[p.name,p]));
 const flag=(name,label)=>h.select(label,'intersection-'+name,[[0,'Off'],[1,'On']],p[name].value);
 return h.card('Saved intersection preparation',`<p>These options persist in the aircraft and are read by OpenVSP when a surface-intersection run starts.</p><div class="tool-fields">${flag('DemoteSurfsCubicFlag','Approximate higher-order surfaces as cubic')}${h.field('Cubic approximation tolerance','intersection-CubicSurfTolerance',p.CubicSurfTolerance.value)}${flag('HalfMesh','Keep the positive-Y half')}${flag('STEPMergePoints','Merge STEP points')}</div><p class="native-tip">Cubic approximation applies only to surface directions above degree three. The tolerance controls OpenVSP’s approximation. Half selection filters surfaces using the native symmetry rules. Point merging is passed to the native STEP exporter.</p>${h.button('save-intersection-settings','Apply intersection settings',true)}`,'wide');
}
export function bindIntersectionSettings(group,h){
 const p=Object.fromEntries(group.params.map(p=>[p.name,p]));
 const input=name=>document.getElementById('intersection-'+name);
 const tolerance=input('CubicSurfTolerance');tolerance.min=p.CubicSurfTolerance.min;tolerance.max=p.CubicSurfTolerance.max;
 const update=()=>{tolerance.disabled=Number(input('DemoteSurfsCubicFlag').value)!==1;};
 input('DemoteSurfsCubicFlag').onchange=update;update();
 h.bind('save-intersection-settings',()=>h.mutate({operation:'intersection-settings',values:Object.fromEntries(names.filter(n=>!input(n).disabled).map(n=>[n,h.num('intersection-'+n)]))}));
}
