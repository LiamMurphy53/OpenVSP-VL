// Run state comes from the job, never from a saved preview artifact.
export const withRunStatus=(data,status)=>({...data,runStatus:status});
export function runPreviewNotice(status){
 if(status===undefined||status==='complete')return '';
 if(status==='failed')return 'Failed run. Saved output may be incomplete or invalid; use it for diagnosis.';
 if(status==='cancelled')return 'Cancelled run. Saved output may be incomplete; use it for diagnosis.';
 if(status==='running')return 'Run in progress. Saved output is provisional and may be incomplete.';
 return 'This run has not completed successfully. Saved output is unvalidated.';
}
