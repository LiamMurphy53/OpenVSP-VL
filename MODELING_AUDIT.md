# Selected modeling audit — October 14, 2026

Baseline source commit: `b9943e1dd6760f905845a7c8b30f26f947d4e9ef`.

Forty-two test modules ran in separate processes. Thirty-nine modules passed, reporting 240 tests. Two modules completed with assertion failures, reporting eight tests between them. One module terminated with SIGSEGV before reporting a final test count. This is selected modeling coverage, not a full project or installed-capability completion audit.

| Module | Baseline result | Current follow-up |
| --- | --- | --- |
| Chevron patterns | Native segmentation fault | Full/partial check passed alone; a two-method sequence terminated with SIGTRAP; an instrumented repeat passed both methods. Intermittent failure remains unresolved. |
| Import records | PLOT3D parent drawing visibility differed after reopening | Blank drawing policy now follows Studio selection rather than transient engine activity; all four blank/import regressions pass. |
| Surface fitting | Built-in material parameter IDs differed in live variable choices | Saved fitting-state versus live-choice comparison remains under investigation. |

Retained evidence: `.workspace/evidence/current-modeling-audit/summary.json`, per-module logs, `chevron-isolated-trace.log`, `chevron-sequence-trace.log`, `chevron-instrumented-sequence.log`, and `.workspace/evidence/blank-reference-import-regressions.log`.

Standalone startup loaded OpenVSP 3.52.2. The baseline package manifest matched all 329 recorded sources; later smooth-shader and blank-reference changes require their own targeted checks. No frozen workflow row W01–W25 is closed by this audit.
