# Custom component control audit — OpenVSP 3.52.2

This audit belongs to the existing W05 custom/specialized modeling workflow. It does not close W05 or change the installed-engine objective.

## Authoritative implementation

The exact installed release declares 31 GDEV values. Its custom-screen constructor implements 18 of them; the remaining 13 have no device-construction branch. Declared enum values alone are not evidence of a usable native custom control.

Sources: [CustomScreen.cpp](https://github.com/OpenVSP/OpenVSP/blob/8782f46d4399ac04d0a1277d414246bb37035666/src/gui_and_draw/CustomScreen.cpp), [GuiDevice.cpp](https://github.com/OpenVSP/OpenVSP/blob/8782f46d4399ac04d0a1277d414246bb37035666/src/gui_and_draw/GuiDevice.cpp), [APIDefines.h](https://github.com/OpenVSP/OpenVSP/blob/8782f46d4399ac04d0a1277d414246bb37035666/src/geom_api/APIDefines.h). Matching local source was inspected; the enum header is already vendored for the native adapter.

## Implemented native device mapping

| Native device | Current Studio access | Proof and remaining verification |
| --- | --- | --- |
| INPUT | Parameter number fields, native limits/activity and script labels/bindings | Existing native script and geometry checks cover numeric edits. |
| SLIDER_INPUT, SLIDER_ADJ_RANGE_INPUT | Sliders beside numeric fields, original script ranges, native limits, unit conversion and optional narrow/widen buttons | Own and external bindings, saved geometry, keyboard interaction, stable slider windows, Undo/Redo, cold reload and lock rejection have selected native/browser evidence. Presentation is modernized; native FLTK stop-button behavior and every binding/widget combination remain unverified. |
| TOGGLE_BUTTON | Boolean parameter Off/On control | Native ToggleButton requires BoolParm; a numeric binding asserts/fails in its SetValAndLimits path. Existing custom box toggle tests cover dynamic bindings and native generated geometry. |
| TRIGGER_BUTTON | Parameter-backed buttons and unbound Component actions | Existing tests cover script choice-driven parameter triggers, event-only actions, once-per-click consumption, persistence and native geometry. |
| CHOICE, ADD_CHOICE_ITEM | Named native option lists in original declaration order | Existing custom BoxGroup tests verify option labels/codes and resulting native array geometry. |
| COUNTER, INDEX_SELECTOR | Native parameter fields; index selectors also expose −10/−1/+1/+10 controls | Dedicated scripts verify edits, limits, retained IDs, complete geometry and reopening. Index steps follow original integer conversion and clamping; four bounded array cases, disconnected controls and browser buttons/Undo pass. The raw parameter field remains available. A three-stage own-component row/column rebinding sequence also passes native geometry and reopening checks. Wider ranges and selected parent-owned index/scalar bindings now have saved/native/browser evidence. Other owner and widget combinations remain unverified. |
| PARM_BUTTON | Properties Link parameter shortcut opens Links & presets with the native source ID selected | Native custom script test proves affine link updates, complete geometry and reopened links. Browser shortcut/source selection, link creation, dependent edit and three Undo restorations pass in an isolated aircraft. Other link/preset/expression combinations remain unverified. |
| TAB, SCROLL_TAB, YGAP, DIVIDER_BOX, BEGIN_SAME_LINE, END_SAME_LINE, FORCE_WIDTH, SET_FORMAT | Studio property groups and modern workspace layout | These organize/present the old GUI. Script-defined TAB/SCROLL_TAB names now group bound own-component fields first in Pro Properties, in native declaration order. Selected browser edit/reload/Undo coverage passes; Streamlined retains combined guided controls. Native raw parameter groups and IDs remain unchanged. Divider/spacing/format layout is not reconstructed. Generic numeric formatting preserves operational editing; script layout/usability parity remains an explicit audit item. |

## Declared but absent from native CustomScreen

GDEV_GROUP, GDEV_OUTPUT, GDEV_SLIDER, GDEV_SLIDER_ADJ_RANGE, GDEV_CHECK_BUTTON, GDEV_CHECK_BUTTON_BIT, GDEV_RADIO_BUTTON, GDEV_TOGGLE_BUTTON_FREE, GDEV_TOGGLE_RADIO_GROUP, GDEV_SLIDER_ADJ_RANGE_TWO_INPUT, GDEV_FRACT_PARM_SLIDER, GDEV_STRING_INPUT, GDEV_COLOR_PICKER.

Studio additionally recognizes declared OUTPUT fields as read-only computed outputs. This is a Studio convenience; it must not be cited as an implemented native CustomScreen device.

## Current verification limits

Existing custom tests cover compiler/package import, nested helpers, choices, trigger modes, disconnected bindings, arbitrary parameter groups, companion profiles and native geometry. They do not prove every supported custom widget or every script/runtime API. Wider index ranges/rebinding and custom link/preset/expression combinations remain checks inside W05; unsupported enum entries should not generate new implementation requirements.

## External binding workflow

Custom controls bound through original UpdateGui to another component's parameter now appear in Properties with their owner name. The native parameter remains owned by its original component. Edits resolve the current GUI binding and reject stale parameter IDs, disconnected bindings and output widgets before the normal native parameter validation/setter runs. Selected parent-owned scalar/index, choice labels, output protection and row/column rebinding are verified; browser owner labels, physical-unit edit, index stepping, rebinding and five Undo restorations pass. Global/structural owner combinations and the full custom runtime scope remain unproven.

An external wing average-chord input also preserves its owning section's native driver activity: calculated edits reject atomically, selecting Average chord enables editing, and full native geometry/saved reopening match an independent SDK reference. This is selected wing-driver coverage, not proof of every owner/driver combination.


### 2026-10-13 — external custom control groups

Parent-owned custom controls retain original script TAB/SCROLL_TAB labels and declaration order in both Properties modes. Native owner labels and current parameter IDs remain visible; edit and index-step binding validation is unchanged. Five external-binding regressions pass (7.094s), including native parent geometry, stale-target rejection, choices, read-only outputs and wing-driver constraints. Browser shows separate Array counts/Parent dimensions groups, edits the actual parent Length5→9ft, verifies the parent field, and restores Length5 plus the original isolated aircraft with Undo. Evidence: `.workspace/evidence/external-custom-tab-tests.log`, `.workspace/evidence/external-custom-tab-browser.png`. Broader custom runtime/layout and full W05 closure remain open.


### 2026-10-13 — custom BOR companion profiles

Custom ZIP packages now relocate original ReadBORFileXSec and ReadBORFileAirfoil filenames, alongside the ordinary section readers. Literal and script-computed filenames use the same embedded-package restoration. Four BOR reader/filename cases compare all 101 profile samples against the original compiler/reader, remove original script/data and staging folders, and preserve complete saved/reopened native surfaces. All seven companion-file regressions pass (4.778s), including ordinary readers, helper-selected profiles, missing-file rejection and native-reader preconditions. Evidence: `.workspace/evidence/custom-bor-companion-regressions.log`. Other runtime data readers and full W05 closure remain open.


### 2026-10-13 — custom clearance-envelope companions

Custom packages relocate the original ReadAuxiliaryGeomCCEFile argument and restore its embedded envelope before cold native script execution. Literal and computed filename cases remove original script/envelope plus temporary staging, then compare all generated auxiliary surface samples and saved envelope-local coordinates against the original compiler/reader. All nine custom companion regressions pass (6.781s), retaining ordinary/BOR profiles and existing failure checks. Evidence: `.workspace/evidence/custom-clearance-companion-regressions.log`. This adds selected runtime data coverage within W05; arbitrary script file I/O and full modeling closure remain unproved.


### 2026-10-13 — custom design-file companions

Custom packages now relocate original ReadApplyDESFile and ReadApplyXDDMFile single filename arguments, while preserving the original compiler and design-variable application. Four reader/literal/computed cases use files exported by the original SDK, verify parent Length10→18 and complete native surface geometry, remove all original data/staging, and verify cold reopening. All ten companion-file regressions pass (8.976s). Evidence: `.workspace/evidence/custom-design-companion-regressions.log`. Missing or malformed computed DES/XDDM data has no selected regression yet; original wrappers clear their last-call error flag, so prior profile-reader failure evidence must not be generalized to these readers. Remaining file-I/O and W05 closure stay open.


### 2026-10-14 — missing computed design-data recovery

The original DES/XDDM readers can terminate a fresh worker on unresolved computed files. Package-generated wrappers now record unresolved filenames in a reserved native attribute and skip only those unsafe calls; resolved data still uses the original native reader. Import, cold-load and pre-save checks reject recorded failures before committing a model. Native import-time and parameter-edit-time rejection tests preserve candidate and original aircraft bytes exactly for both readers. All 30 custom assets/scripts/external-binding regressions pass (30.278s), including valid literal/computed design files, native geometry/reopening, dynamic choices/indexes and reference/driver protection. Evidence: `.workspace/evidence/custom-missing-design-final-regressions.log`. This supersedes the earlier missing-design-file uncertainty. Malformed design-data validation and full W05/modeling closure remain unfinished.


### 2026-10-14 — custom design-data validation

Packaged DES/XDDM readers now preflight file record shape/count, finite bounded values, duplicate IDs and XML structure/doctype constraints. Generated wrappers check original ValidParm IDs at execution and call the original reader only for validated resolved data. Literal malformed files reject before native import; computed malformed/stale-reference files record a reserved failure and reject before save. Arbitrary companion extensions are supported, and unused package files are not rejected merely for another format. Sixteen reader/input/literal-computed rejection cases preserve original and candidate aircraft bytes exactly. All 13 companion regressions pass (12.063s), including independent native valid-reader geometry and source-free cold reopening. Evidence: `.workspace/evidence/custom-design-validation-regressions.log`. Native DES name/spacing quirks and arbitrary runtime file I/O remain outside this selected check; W05/full modeling remain open.

## Selected global and structural bindings — October 15

Original custom UpdateGui bindings to VSPAERO MachStart and a user-created shell Thickness now have explicit regression evidence. The existing generic external-control path required no implementation change. Both inputs retain their original global/structural owner names and parameter IDs, update through current-binding validation and original setters, survive fresh-worker reopening, and do not duplicate parameters into the custom component. Complete geometry stays unchanged, as expected for these saved configuration inputs; a separate SDK read confirms both saved values. The one new regression passes in source (1.613s) and the packaged worker (1.749s). Source: `tests/test_custom_global_bindings.py`. This proves these two owner/input cases, not structural analysis results or full W05 closure.


### 2026-10-15 — custom sliders and adjustable windows

The native GuiDef bridge now copies each original m_Range with full double precision. Supported SLIDER_INPUT and SLIDER_ADJ_RANGE_INPUT controls expose sliders beside the existing numeric input, including external parent/global/structural bindings. Initial windows use the original script range and native limits. Adjustable controls provide narrower/wider windows; ordinary sliders omit those buttons. Display units convert both bounds and values. Window positions persist across saved edits within the current page. Invalid or collapsed ranges retain numeric editing. Geometry changes use the existing validated native transaction when a drag/keyboard change completes; window adjustment only changes presentation.

The external property Lock button now resolves the original bound parameter instead of searching only the custom component's own fields. Browser locking and an attempted parent slider change show the native constraint warning and restore the saved value. Two new worker regressions pass (2.031 s), 13 existing custom-script tests pass (16.846 s), five external-binding tests pass (7.760 s), and JavaScript window/unit/integer/disabled-state checks pass. Browser Box Length5→8.74975, Undo5 and Redo8.74975 retain the adjusted bounds; a direct SDK edit matches every native parameter and sampled surface for both components exactly. A parent-bound slider changes Length5→15, survives reopening, and rejects locked15→25; both complete components match the direct SDK edit exactly. Evidence: `.workspace/evidence/custom-slider-verification/`. The same two new cases pass through the packaged worker (2.291 s); standalone preflight loads OpenVSP 3.52.2 and all 337 packaged source hashes match. Full W05/custom runtime parity remains unproven.

### 2026-10-15 — custom advanced-link code companions

Custom ZIP components now relocate literal and computed ReadAdvLinkCodeFile filenames while preserving the native link-index expression, reader and compiler. Tests compare original native geometry, remove original files/staging, reopen, replace serialized expression code, and verify a subsequent custom update restores and executes the embedded companion. Missing or out-of-package files reject without changing original/candidate aircraft bytes. The fixture enumerates existing link names before reading because native custom evaluation can precede link decoding during load. Browser package import, expression inspection, Length18→Y4.5, Undo/Redo and reopening pass. Custom components now display a readable type label instead of the generated script identifier. Evidence: tests/test_custom_code_assets.py and .workspace/evidence/custom-code-verification/. These selected cases advance W05; arbitrary script file I/O, full custom parity and the broader engineering objective remain unproved.

Delivery check: three new tests pass in source (3.044 s) and through the packaged worker (3.481 s). Standalone startup reports OpenVSP 3.52.2; all 339 packaged source checksums match.

### 2026-10-15 — native file-handle data companions

A fresh original-SDK script read length12 from length.txt, while the same packaged script previously imported at its fallback/default length5. Custom packages now recognize plain typed native file-handle open calls (including typed function parameters and lexical shadowing). A generated helper evaluates the original arguments once and tries the original native open first. Only failed pure reads fall back to an unambiguous embedded companion. Optional missing reads retain native status, while writes and read-after-write continue using the original filename. Native file reading/parsing and all component geometry remain in OpenVSP. Method-prefix edits preserve nested argument expressions; profile/design reader rewriting follows that pass.

Five selected native methods cover literal/computed text, native binary readDouble, optional missing files, writes/read-after-write, typed function parameters and a different class with an identically named open method. Complete source-free/cold component surfaces match the original SDK. Four cases plus13 existing companion-file and3 code-file regressions pass together (20 methods,19.359 s); the additional binary case passes separately (0.725 s). All five new cases pass through the packaged worker (4.103 s). Browser loads the preimported native aircraft, shows Length12, edits Width7→9 while retaining12, then restores Width7 with Undo and verifies Length12/Width7 after reopening. The browser did not re-upload the ZIP in this check. Evidence: .workspace/evidence/custom-generic-file-gap/comparison.json (before12/5), after.json (after12/12), regressions.log and browser-controls.png. The isolated server is stopped.

This does not establish arbitrary script filesystem/runtime parity. Member/index/factory receiver expressions, auto-inferred handles, more complex declarations and ambiguous companion paths require further type/path resolution and verification; native calls outside recognized plain handles are preserved rather than guessed. W05 and full modeling remain open.

### 2026-10-15 — compound custom file receivers

File-open relocation now resolves receiver types across native file handles, auto-inferred constructors, named object members, array elements, known file-returning functions/methods, multiple declarations and local array constructors. Class fields/method returns and function parameters remain distinct from local shadows. Balanced call/index/block scopes keep argument expressions intact. Only receivers resolved as native file objects receive the existing optional companion fallback; unrelated member/factory open calls remain original. No native file decoder or geometry computation changes.

Ten reader methods pass in source, including four member/index/getter/auto-object variants, auto file handles, multiple handles, constructor-sized arrays and different-class factories/members with matching method names. A side-effect fixture encodes factory/mode call order and count into the native dimension and compares full original SDK geometry; it verifies each expression evaluates once in the original order. All source-free and cold geometry comparisons retain exact surfaces. Combined new reader13-profile/code companion coverage passes26 methods (26.993 s); all10 reader methods also pass through the packaged worker (10.451 s). Evidence: tests/test_custom_file_reads.py and .workspace/evidence/custom-generic-file-gap/receiver-combined.log / receiver-packaged.log. This supersedes the prior plain-handle-only restriction for the tested receiver forms. More complex language/type resolution, namespace/inheritance cases, filesystem directory operations and migration of older embedded code remain unproved; W05/full custom runtime closure is still open. No new browser check was performed for this source-typing extension; the existing package import/editor workflow and preceding browser evidence remain separately scoped.


### 2026-10-15 — older embedded custom file readers

Opening an older aircraft with embedded custom ZIP assets now updates recognized native file receivers in an isolated temporary load copy. The installed engine's original XmlUtil conversions decode and re-encode ScriptFileContents; no script XML substitution rules or geometry equations are copied. Individual generated helper bodies are excluded, including helpers expanded before later user callbacks. Native callbacks retain the original aircraft filename. Read-only queries preserve original/candidate bytes, temporary load files are removed, normal edits persist the updated script, and subsequent loading is idempotent. Ambiguous duplicate component package attributes reject without modifying the aircraft.

Four migration methods cover plain/compound legacy receivers, full original SDK surface comparisons after source removal, helpers before callbacks, original filename callbacks, duplicate records and cold reopen. Combined reader/profile/code regressions pass30 methods (28.015 s); related region/cap integration passes6 (3.654 s). The packaged worker passes all4 migration methods (3.210 s). Browser evidence from the isolated legacy aircraft shows Length12 and Width7→9 while saving the upgraded code; Undo restores the exact original aircraft SHA256. The temporary browser tab was unavailable on continuation, so no additional browser reopen is claimed. Evidence: tests/test_custom_file_upgrade.py and .workspace/evidence/custom-generic-file-gap/upgrade-*.log / upgraded-saved-model.png.

This closes the tested older-file migration gap. Namespace/inheritance/type ambiguity, directory operations, arbitrary custom runtime parity and full W05 closure remain unproved.
