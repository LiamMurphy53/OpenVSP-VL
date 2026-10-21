// Keep each native settings container's search across edits and history refreshes.
const queries=new Map();
export function bindEngineeringSearch(root,owner){
 const input=root.querySelector('#settings-search');if(!input)return;
 input.value=queries.get(owner)||'';
 const apply=()=>{
  queries.set(owner,input.value);const query=input.value.toLowerCase();
  for(const field of root.querySelectorAll('#settings-fields .tool-field'))field.hidden=!`${field.textContent} ${field.title}`.toLowerCase().includes(query);
 };
 input.oninput=apply;apply();
}
