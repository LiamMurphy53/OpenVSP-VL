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
| TAB, SCROLL_TAB, YGAP, DIVIDER_BOX, BEGIN_SAME_LINE, END_SAME_LINE, FORCE_WIDTH, SET_FORMAT | Studio property groups and modern workspace layout | These organize/present the old GUI. Script-defined tab/group layout is not reconstructed. Generic numeric formatting preserves operational editing; script layout/usability parity remains an explicit audit item. |

## Declared but absent from native CustomScreen

GDEV_GROUP, GDEV_OUTPUT, GDEV_SLIDER, GDEV_SLIDER_ADJ_RANGE, GDEV_CHECK_BUTTON, GDEV_CHECK_BUTTON_BIT, GDEV_RADIO_BUTTON, GDEV_TOGGLE_BUTTON_FREE, GDEV_TOGGLE_RADIO_GROUP, GDEV_SLIDER_ADJ_RANGE_TWO_INPUT, GDEV_FRACT_PARM_SLIDER, GDEV_STRING_INPUT, GDEV_COLOR_PICKER.

Studio additionally recognizes declared OUTPUT fields as read-only computed outputs. This is a Studio convenience; it must not be cited as an implemented native CustomScreen device.

## Current verification limits

Existing custom tests cover compiler/package import, nested helpers, choices, trigger modes, disconnected bindings, arbitrary parameter groups, companion profiles and native geometry. They do not prove every supported custom widget or every script/runtime API. Wider index ranges/rebinding and custom link/preset/expression combinations remain checks inside W05; unsupported enum entries should not generate new implementation requirements.

## External binding workflow

Custom controls bound through original UpdateGui to another component's parameter now appear in Properties with their owner name. The native parameter remains owned by its original component. Edits resolve the current GUI binding and reject stale parameter IDs, disconnected bindings and output widgets before the normal native parameter validation/setter runs. Selected parent-owned scalar/index, choice labels, output protection and row/column rebinding are verified; browser owner labels, physical-unit edit, index stepping, rebinding and five Undo restorations pass. Global/structural owner combinations and the full custom runtime scope remain unproven.

An external wing average-chord input also preserves its owning section's native driver activity: calculated edits reject atomically, selecting Average chord enables editing, and full native geometry/saved reopening match an independent SDK reference. This is selected wing-driver coverage, not proof of every owner/driver combination.
