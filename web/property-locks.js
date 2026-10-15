export function propertyLocksMarkup(locks=[],E){
 if(!locks.length)return '';
 return `<details class="parameter-group" data-group="saved-property-locks" ${locks.some(p=>p.conflict)?'open':''}><summary>Aircraft property locks (${locks.length})</summary>${locks.map(p=>`<div class="field"><strong>${E(p.label||p.id)}</strong><small>${p.available?(p.conflict?'Value changed outside this constraint. Unlock to accept the current value.':'Locked'):'Property no longer exists. Unlock to remove this saved constraint.'}</small><button type="button" data-release-property-lock="${E(p.id)}" aria-label="Unlock saved ${E(p.label||p.id)}">Unlock</button></div>`).join('')}</details>`;
}
export function bindPropertyLocks(host,mutate){
 host.querySelectorAll('[data-release-property-lock]').forEach(button=>button.onclick=()=>mutate({operation:'property-lock',parameters:[button.dataset.releasePropertyLock],locked:false}));
}
