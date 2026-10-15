// Coalesce model-driven refreshes while a workspace is hidden. Returning to an
// unchanged workspace retains its DOM, including unsaved form inputs and views.
export function visibleRenderer(render){
 let visible=false,dirty=true;
 const flush=()=>{if(visible&&dirty){dirty=false;render();}};
 return {request(){dirty=true;flush();},setVisible(value){visible=!!value;flush();}};
}
