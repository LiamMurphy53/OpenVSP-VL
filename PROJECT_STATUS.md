# Project status — 2026-10-12

The full objective remains: all installed OpenVSP engineering capabilities usable end to end in Studio, with native verification. No completion category is closed. Geometry is the current priority; engineering remains queued. Human/crew workflows are deferred by user request.

This is a status view of the existing capability plan, not a new scope or a replacement for its detailed requirements. The original 25 workflow rows are frozen as W01–W25 in `.workspace/evidence/project-fixed-workflow-inventory.json`. Future findings belong to those rows and the four existing categories.

| Existing category | Implementation remaining | Verification remaining |
| --- | --- | --- |
| Modeling | Complete remaining specialized/custom workflows, including other custom device types and runtime companion data; confirm complete section workflows on genuine secondary cross-section surfaces. Compound Streamlined workflows remain partial. | Wider geometry/profile/attachment/symmetry combinations; native save/reopen and browser recovery for the complete scope. Rounded-propeller chevron inconsistency/crash remains unresolved. |
| Engineering | Finish queued guided calculation, result and study workflows; the staged wave ideal-body display is not connected. Inventory gaps against every installed capability rather than relying on registered analysis names. | Full native result/provenance comparisons across CFD, aerodynamic, structural, rotor, utility and study combinations. Native CFD propeller crash, structural variation and prior solver discrepancies remain open. |
| Reliability/delivery | Complete standalone workflow delivery, remaining portability/recovery work and documentation. | Full cold-start UI, relocation, responsive layout, cancellation/recovery and portable end-to-end checks. Current package checks cover selected workflows only. |
| Completion audit | Reconcile every explicit plan requirement and installed capability to authoritative evidence. | No broad row is closed by a narrow passing case. Close only after every requirement is proved and known failures are resolved. |

Latest modeling evidence includes secondary custom-surface copying, generated read-only profile viewers, restored Modeling tools copy routing, strict section indices and original native surface refresh after curve paste. Selected saved and viewport geometry comparisons pass; broad W02/W03 closure remains open.

Custom components can import single scripts or ZIPs with nested helpers, use native named choices, dynamic bindings and parameter-backed/event-only actions. Selected original-engine geometry, save/reopen, rejection and browser Undo checks pass. This does not prove all custom script behavior.

The retained full-suite run discovered 327 tests and completed with two unresolved failures/crashes. It predates recent changes and is not a current full-suite pass. Its exact counts are retained in the fixed inventory; targeted subsequent checks do not replace it.

There is no defensible finish date or percentage yet. The earlier “weeks” answer was a rough planning guess, not an estimate based on measured remaining work. Timing requires reviewing the remaining implementation in W01–W25 and separating it from verification and engine failure investigation. Keep the same checklist while doing that review.
