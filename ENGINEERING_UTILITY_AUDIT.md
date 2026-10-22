# Standalone engineering reference audit

Reviewed 2026-10-20 against installed OpenVSP 3.52.2. This audit covers public standalone aerodynamic references and atmosphere/drag reference writers. It does not claim coverage of every installed engineering capability, registered analysis, geometry/manager operation, general vector helper or browser workflow.

The installed Python wrapper SHA256 is `0d6ccf450d3f868f17390593eb869b16e77c7b53f5c6178482a0c6c17b11d3fd`. Exact wrapper function locations and regression log references are recorded in `.workspace/evidence/standalone-api-audit-20261020/inventory.json`.

| Native functions | Studio workflow in Analyze → Reference calculations | Implementation | Native verification |
| --- | --- | --- | --- |
| GetHersheyBarLiftDist, GetHersheyBarDragDist | Rectangular wing · lift and drag | native_analytical.py, HersheyBarTheory | tests/test_analytical.py: half/full-span distributions against original API |
| GetVKTAirfoilPnts, GetVKTAirfoilCpDist | Analytical airfoil · profile and pressure | native_analytical.py, VKTAirfoilTheory | tests/test_analytical.py: original coordinates/Cp, Selig export, incidence and mapping parameters |
| GetEllipsoidSurfPnts, GetEllipsoidCpDist, IntegrateEllipsoidFlow | Ellipsoid · pressure and flow integrals | native_analytical.py, EllipsoidFlowTheory | tests/test_analytical.py: original surface/Cp/integrals, translated centers, sphere pressure and undefined native samples |
| CalcAtmosphere, WriteAtmosphereCSVFile | Atmosphere · native model and standard-day table | native_reference_tables.py, AtmosphereReference | tests/test_reference_tables.py: both original atmosphere models, point outputs and native fixed-grid CSV records |
| WriteBodyFFCSVFile, WriteWingFFCSVFile, WriteCfEqnCSVFile, WritePartialCfMethodCSVFile | Drag equations · native reference tables | native_reference_tables.py, DragEquationReference | tests/test_reference_tables.py: every native result sample and CSV record for all four writers |

All 13 named functions are present in the installed wrapper and invoked by the five listed workflows. `native_worker.snapshot` includes the workflow names in the analysis list; `analysis_schema` and native execution route them through `native_analytical`. `web/app.js` groups those names in the reference calculations selector. Existing saved-run/study/result workflows supply reopening, input reuse, plots and exports; their entire browser scope is not newly verified by this audit.

The frozen baseline at `4eb7e977db783095bc2fa53fce96e3ec27f100cf` includes eight successful `test_analytical` processes and three successful `test_reference_tables` processes. Those eleven specific logs were checked in `.workspace/evidence/full-native-audit-20261020/`; this is existing baseline evidence, not a fresh execution after later source changes.

These are original-engine reference calculations, with their existing applicability limits. They do not replace an aircraft solve, establish convergence, model stall or viscosity beyond their documented equations, or certify physical validity. No additional missing standalone calculation was identified in this reviewed family. Broader W23 closure still requires the remaining parameter/performance coverage and end-to-end delivery evidence in the capability inventory.

## 2026-10-21 — reference workflow delivery checks

The three analytical schemas now provide explicit angle, dimensionless mapping/normalized-span, consistent length and consistent velocity labels. Sample-count labels identify what is counted without duplicate units. These are presentation labels; values sent to the engine are unchanged. Standalone setup guidance now describes reference inputs rather than claiming aircraft geometry drives them.

Fresh source tests: 12 passed in 8.051 seconds. Packaged-module/interpreter/worker tests: 12 passed in 6.648 seconds; the harness asserts package imports. All 14 JavaScript test modules passed. Logs and the package harness are under `.workspace/evidence/reference-workflows-20261021/`.

Nine browser-created saved runs covered a negative-incidence rectangular wing, a VKT airfoil, a translated ellipsoid with oblique velocity, both atmosphere models at 11001 m with −10 K deviation, and all four original drag-table writers. Independent original API calls reproduced every result array and analytical CSV sample exactly, plus the native fixed-grid CSV records (excluding only timestamp/date/time metadata). The VKT Selig profile, pressure-preview coordinates and finite colored sample associations matched exactly. Each run retained its input aircraft bytes. The comparison script and full receipts are `compare-browser.py` and `browser-verification.json` in that evidence directory.

The browser showed the native results, plots/pressure previews and export links. Native CSV links were exercised for skin friction, partial turbulence and atmosphere; earlier wing-sample and VKT-profile links were also exercised. A separate local HTTP check delivered all 14 saved CSV/profile/pressure artifacts byte-exact (`artifact-delivery.json`); this is server-delivery evidence, not a claim that every download was captured from the browser's download manager. Saved reopening and input reuse restored the translated ellipsoid vectors and Herrington model/altitude/deviation. The saved atmosphere screenshot and accessibility states are retained.

This closes the listed desktop reference cases only. Broader parameter/performance, narrow layouts, browser recovery and study combinations remain unproven. W23 and the overall engineering-capability goal remain open.


## 2026-10-21 — saved engineering choices and projection options

Six Vehicle-owned fields now show original named enum choices: mass and planar slicing axes, projection direction and boundary type, degenerate mesh representation, and measurement units. Same-name user fields do not acquire these controls. Only original directly inherited MassProp and DegenGeomMesh inputs declare native parameter bindings. Planar normal vectors are not treated as scalar-axis aliases.

Projection's original SetDefaults hardcodes standard options rather than inheriting saved Vehicle projection values. Analyze therefore offers an explicit Apply saved projection options action; reset retains original standard behavior. Copy validates all option records before changing the form, preserves entered geometry/set/mode references, and rejects plane/point targets unsupported by area Projection.

Source and strict relocated suites each passed three native tests (relocated 1.125 s), including all 24 enum codes, cold reopen, same-name user controls, native reset inheritance, all mass slicing axes, and existing component/set/mode/boundary/vector projection paths. Browser-created MassProp and Projection jobs matched independent original SDK results exactly across 35 and 5 numerical fields respectively, preserving aircraft bytes. Browser copy preserved the entered Shown target set, while reset restored All and X direction. Evidence: `.workspace/evidence/global-choice-audit-20261021/`, including `packaged-final.log`, `browser-verification.json`, `applied-state.txt`, and `reset-state.txt`. These specific checks do not establish full W10/W11/W24 closure.


## 2026-10-21 — guided limit ownership

MassProp, PlanarSlice, WaveDrag and ParasiteDrag input limits now resolve the original Vehicle/settings manager and exact native group. The previous display-name scan could overwrite limits with same-name controls. A native API proxy collision test verifies exact native bounds for these four analyses; this deliberately injected collision is a lookup regression, not evidence of a naturally occurring malformed aircraft. All nine existing guided-analysis tests passed (8.937 s). Seven strict relocated tests passed (10.666 s), including the ownership regression, five live-edit history checks and full native propeller curve-edit/interpolation geometry comparison. Loaded production module paths were asserted inside the relocated bundle. Evidence: `.workspace/evidence/slider-and-guide-owners-20261021/packaged.log` and `verification.json`.

The accompanying slider milestone adds live propeller distribution point controls, preserves native activity locks and exact-value entry, and groups each curve drag into one Undo step. A wing-mount span slider synchronizes with percentage entry and retains explicit Apply. JavaScript slider markup/binding checks passed; this milestone has not received a new interactive browser drag check. Broader delivery and workflow closure remain unproven.
