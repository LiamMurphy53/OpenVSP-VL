// Native definitions retain saved IDs when renamed; usage is supplied by the engine snapshot.
export function libraryControls(item,kind,h){
 const {E,field}=h,users=item.libraryUsers||[];
 const copy=`<button data-library-copy="${E(item.id)}" data-library-kind="${kind}">${item.builtIn?'Create editable material copy':'Duplicate '+kind}</button>`;
 if(item.builtIn)return `<p class="native-tip">Built-in OpenVSP material. Copy its native values and units into an independent custom material.</p>${copy}`;
 return `<div class="inline-fields">${field(kind==='property'?'Property name':'Material name','library-name-'+item.id,item.name,'text')}<button data-library-rename="${E(item.id)}" data-library-kind="${kind}">Rename ${kind}</button></div>${users.length?`<details><summary>Used by ${users.length} saved ${users.length===1?'assignment':'assignments'}</summary><ul>${users.map(u=>`<li>${E(u.name)} · ${E(u.role)}</li>`).join('')}</ul><p class="native-tip">Reassign these owners before removing this ${kind}.</p></details>`:'<p class="native-tip">No saved assignments use this definition.</p>'}<div class="tool-actions">${copy}<button data-library-delete="${E(item.id)}" data-library-kind="${kind}" ${users.length?'disabled':''}>Remove ${kind}</button></div>`;
}
export function bindStructuralLibrary(h){
 document.querySelectorAll('[data-library-copy]').forEach(b=>b.onclick=()=>h.mutate({operation:b.dataset.libraryKind+'-copy',id:b.dataset.libraryCopy}));
 document.querySelectorAll('[data-library-rename]').forEach(b=>b.onclick=()=>h.mutate({operation:b.dataset.libraryKind+'-rename',id:b.dataset.libraryRename,name:h.val('library-name-'+b.dataset.libraryRename)}));
 document.querySelectorAll('[data-library-delete]').forEach(b=>b.onclick=()=>h.mutate({operation:b.dataset.libraryKind+'-delete',id:b.dataset.libraryDelete}));
}
