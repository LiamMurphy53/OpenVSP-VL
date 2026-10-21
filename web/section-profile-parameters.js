// Resolve native IDs from the selected surface/profile, never from a repeated
// section index or display group name shared by other profiles.
export function sectionProfileParameters(component,section){
 if(!section||section.generated||Array.isArray(section.controlPoints))return [];
 const ids=new Set(section.profileControls?.shapeFields||[]);
 const rank=['Chord','Width','Height','ThickChord','Camber','CamberLoc','IdealCl'];
 return (component.params||[]).filter(p=>ids.has(p.id)).sort((a,b)=>{
  const order=p=>{const i=rank.indexOf(p.name);return i<0?rank.length:i;};
  return order(a)-order(b);
 });
}
