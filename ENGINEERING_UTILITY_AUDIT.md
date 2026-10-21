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
