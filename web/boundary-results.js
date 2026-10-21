// Count original exported node/direction records; do not infer support adequacy.
export function boundaryResults(report,E){
 if(!report)return '';
 if(!report.available)return `<section class="native-tip"><h3>Exported node constraints</h3><p>${E(report.reason)}</p></section>`;
 return `<section class="native-tip"><h3>Exported node constraints</h3><p>${E(report.nodeCount)} constrained nodes · ${E(report.degreeCount)} constrained degrees of freedom in ${E(report.sourceFile)}.</p>${report.nodeCount?`<table class="result-table"><thead><tr><th>Direction</th><th>Constrained nodes</th></tr></thead><tbody>${['Translation X','Translation Y','Translation Z','Rotation X','Rotation Y','Rotation Z'].map((label,i)=>`<tr><td>${label}</td><td>${E(report.directionCounts[i])}</td></tr>`).join('')}</tbody></table>`:'<p>No nodes were constrained in this export. Check saved constraint directions, targets and coordinate filters if you expected supports.</p>'}<p>Combined native boundary records from ${E(report.definedConditions)} saved condition${report.definedConditions===1?'':'s'}. Overlapping node/direction records count once. Assembly connection equations are separate.</p></section>`;
}
