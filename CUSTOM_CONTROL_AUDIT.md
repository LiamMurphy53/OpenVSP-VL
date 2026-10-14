# Custom component control audit — OpenVSP 3.52.2

This audit belongs to the existing W05 custom/specialized modeling workflow. It does not close W05 or change the installed-engine objective.

## Authoritative implementation

The exact installed release declares 31 GDEV values. Its custom-screen constructor implements 18 of them; the remaining 13 have no device-construction branch. Declared enum values alone are not evidence of a usable native custom control.

Sources: [CustomScreen.cpp](https://github.com/OpenVSP/OpenVSP/blob/8782f46d4399ac04d0a1277d414246bb37035666/src/gui_and_draw/CustomScreen.cpp), [GuiDevice.cpp](https://github.com/OpenVSP/OpenVSP/blob/8782f46d4399ac04d0a1277d414246bb37035666/src/gui_and_draw/GuiDevice.cpp), [APIDefines.h](https://github.com/OpenVSP/OpenVSP/blob/8782f46d4399ac04d0a1277d414246bb37035666/src/geom_api/APIDefines.h). Matching local source was inspected; the enum header is already vendored for the native adapter.

## Implemented native device mapping

| Native device | Current Studio access | Proof and remaining verification |
| --- | --- | --- |
| INPUT, SLIDER_INPUT, SLIDER_ADJ_RANGE_INPUT | Parameter number fields, native limits/activity and script labels/bindings | Existing native script and geometry checks cover numeric edits. Slider drag/range presentation is not reproduced; separate widget-specific interaction coverage remains. |
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
