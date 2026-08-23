# Future Refactors and Features: Frontend Plugin Base Classes

Context block for a dedicated future session. This file is separate from
`future_fixes.md` on purpose: `future_fixes.md` tracks QA/tooling work (type
annotations, compliance-gate infrastructure for community contributions);
this file tracks *changes to the frontend plugin architecture itself* —
both refactoring of existing code (Part 1) and a new feature that depends on
that refactoring having landed first (Part 2). Keep that QA-vs-architecture
distinction when deciding whether something belongs here or in
`future_fixes.md`.

Both parts are kept in **this one file, in this order, deliberately**: Part 2
(widget-state session persistence) should not be implemented before Part 1's
`BasePluginControls` extraction lands, because Part 2's design leans directly
on that shared base existing. Splitting them into separate files risked
losing that ordering constraint. If Part 1 is ever done incrementally, do the
`BasePluginControls` extraction (Part 1, Tier 1 headline finding) before
starting Part 2, even if the rest of Part 1 is left for later.

---

# Part 1: Promote Duplicated Frontend Plugin Code into Base Classes

## Background and scope

Poriscope's 5 frontend analysis-tab plugin families (RawData, EventAnalysis,
Clustering, Metadata, Protein, all under `poriscope/plugins/analysistabs/`)
each implement a Controller/Model/View triad inheriting from
`poriscope/utils/MetaController.py`, `MetaModel.py`, `MetaView.py`. The
starting observation (from a live session, 2026-08) was that these three base
classes looked "bare bones," with most real logic living in the family-specific
implementations — the question was whether that's actually true, and if so,
what's duplicated across families that could be pulled up.

A read-only audit (3 parallel sub-agents, each covering a disjoint set of
families, cross-referenced against a direct reading of the three `Meta*`
bases) found that the bases are **not** as bare as assumed — a fair amount of
generic plumbing is already promoted (worker/thread/generator management,
progress bars, tab action history, add/edit/delete-plugin signal emission, and
several numeric/range helpers: `_parse_event_indices`, `_shift_ranges`,
`_merge_ranges`, `_format_ranges`, `_expand_event_indices`,
`_logscale_and_filter_multiple_columns`, `_logscale_and_filter_dataframe`).
What follows is what the audit found is **still** duplicated, organized by
confidence/risk tier, plus correctness issues the audit surfaced as a side
effect, and an overall recommendation on whether this is worth doing.

> **Note:** File:line citations below are as reported by the sub-agents that
> did the reading, not independently re-verified line-by-line. Spot-check the
> specific citation before writing a diff against it — files change over
> time and an agent's line numbers can drift by the time this is picked up.

## Headline finding: the `*controls.py` mixins are the densest duplication in the codebase — and they sit outside the `Meta*` triad

Every family's `poriscope/plugins/analysistabs/utils/<name>controls.py` (a
plain `QWidget` mixin the View composes with via multiple inheritance, not a
`Meta*` subclass) reimplements the same ~150–300 line toolkit nearly verbatim:

- `create_comboBox`, `createButton`, `createLabel`, `create_info_button`,
  `create_add_button`, `create_delete_button`, `toggle_info_button`
- the "No X" placeholder guard (`is_placeholder_item`) — every family has its
  own copy with a different literal placeholder string ("No Event Database",
  "No Reader", "No Loader", ...), matching the already-known
  placeholder-guard convention used project-wide
- `show_plugin_edit_manager`, `show_plugin_add_manager`, `delete_plugin`,
  `clear_popup_reference`
- (RawData/EventAnalysis specifically) an identical ~45-line
  `MultiSelectComboBox`-rebuild `update_channels` method

This was independently confirmed by all three sub-agents (byte-identical
between `ClusteringControls`/`MetadataControls`; byte-identical between
`RawDataControls`/`EventAnalysisControls`; the same shape confirmed in
`proteincontrols.py`). It's the single highest-density duplication found in
the whole audit — but because it lives outside the `MetaController`/
`MetaModel`/`MetaView` inheritance chain, the fix is a **new shared mixin**
(e.g. `BasePluginControls(QWidget)` in `poriscope/plugins/analysistabs/utils/`),
not an edit to `MetaView` itself. This makes it the best-isolated, lowest-risk
starting point: it's additive (existing Views don't need to change their
class hierarchy), and it doesn't touch anything `test_plugin_compliance.py`
checks (see Risks below).

## Tier 1 — near-byte-identical, low risk, straightforward promotions

Present in **all 5** families:

- **`update_available_plugins` outer skeleton.** Every View's
  `update_available_plugins` does: call `super().update_available_plugins(...)`,
  then `try:` pull one or more metaclass key-lists out of the
  `available_plugins` dict, hand each to the controls widget's `update_X`
  setter, log success; `except Exception:` log failure. Confirmed
  independently for Clustering/Metadata, RawData/EventAnalysis, and Protein —
  the single most universal finding in the audit. Only the specific
  metaclass keys and setter calls differ per family (and, for RawData, one
  extra genuinely-RawData-specific block initializing
  `self.analysis_time_limits` per event-finder, which must NOT be pulled up).
  Strong template-method candidate: a shared method parameterized by a list
  of `(metaclass_key, setter_callable)` pairs, with a hook for family-specific
  extra steps.
- **`get_save_filename`.** Identical
  `QFileDialog.getSaveFileName(self, "Save CSV File", os.path.expanduser("~"), "CSV Files (*.csv);;All Files (*)")`
  one-liner confirmed in `ClusteringView`, `MetadataView`, `ProteinView`.

Present in **3 of 5** families (Clustering, Metadata, Protein — the ones with
a `MetaDatabaseLoader` dependency):

- **Controller "pure relay" one-liners.** Most Controller methods across
  these families (and, independently, across RawData/EventAnalysis too — see
  below) are literally `self.view.set_X(value)`, one line, existing purely to
  serve as a `global_signal`/`relay_*` callback target. This recurs dozens of
  times per family. See "Tier 3" below for the bigger architectural version
  of this observation.
- **`notify_plugin_state_changed` "only react if it's my currently-selected
  loader" guard.** Near-identical across `ClusteringView`, `MetadataView`,
  `ProteinView`: ignore unless `metaclass == "MetaDatabaseLoader" and reason
  == "columns"`, then only refresh if `plugin_key` matches the family's own
  loader combobox's current selection.
- **The "No X" placeholder guard itself** (see Headline finding above) is
  present in all 5 controls mixins, not just these 3, but is called out again
  here because these 3 families additionally share the specific downstream
  consumer pattern (the loader-selection guard) that uses it.

Present in exactly **RawData + EventAnalysis**:

- `_get_event_index_text`, `validate_single_channel` (100% byte-identical,
  including docstring), `_extract_commit_event_parameters`,
  `set_data_filter_function`, `update_plot_samplerate`, and the filter-
  resolution try/except block (duplicated **4 times total** — twice per file,
  once in `_handle_plot_events` and once in the eventfinder/eventfitter
  start-up flow).
- **`_shift_range_and_update_plot`** — the single strongest individual
  finding in the sweep: a ~50-line orchestration wrapper that chains five
  helpers *already* promoted to `MetaView` (`_parse_event_indices`,
  `_shift_ranges`, `_merge_ranges`, `_format_ranges`, `_expand_event_indices`)
  but was never itself pulled up, so both families independently re-write the
  glue code around already-shared helpers. Promoting this one method removes
  ~50 duplicated lines per family for close to zero risk, since the pieces it
  calls are already shared and already tested by virtue of being shared.

## Tier 2 — same skeleton, real per-family variation (template-method candidates, not literal copy-paste)

- **DB "column exists → confirm destructive overwrite → drop+re-add →
  refresh+notify" flow.** `ClusteringView._commit_clusters` and
  `ProteinView._commit_fits` both independently implement: check column
  existence via `global_signal("MetaDatabaseLoader", ..., "get_table_by_column", ...)`
  → `QMessageBox.question` "already exists, overwrite?" → hand-built
  `ALTER TABLE ... DROP COLUMN` + cleanup queries → `alter_database` → on
  success, refresh available columns and `plugin_state_changed.emit(...,
  "columns")`. Metadata doesn't need this (its DB interaction is read/filter-
  only). A parameterized helper (`table`, `loader`, `columns`, `units`,
  `overwrite_prompt`) could serve both Clustering and Protein.
- **Figure-reset skeleton (`_reset_actions`).** Clustering and Metadata both
  clear/rebuild axes and redraw on reset, but Metadata's `_axes_valid()`
  helper is strictly more correct than Clustering's ad hoc equivalent check —
  if this gets promoted, promote Metadata's version upward rather than
  extracting the lowest common denominator. Protein duplicates the *same*
  clear-add_subplot-tight_layout-draw sequence **twice within itself** (once
  for its histogram figure, once for its VM figure) — worth a local
  `_reset_one_figure(fig, canvas)` helper inside `ProteinView` regardless of
  any cross-family work. RawData and EventAnalysis's `_reset_actions` are
  both pure no-op `pass` implementations (required by the base's abstract
  contract but with nothing to do), so they don't participate in this one.
- **`_start_writer`/`_start_eventfinder`/`_start_eventfitter` generator-wiring
  skeleton** (RawData/EventAnalysis) — normalize channels to a list → resolve
  the data filter → per-channel "already ran, overwrite?" confirmation → emit
  `set_generator` with `ret_args=(channel, key, metaclass)` → `run_generators.emit`.
  See the arg-shape inconsistency flagged under Correctness issues below
  before promoting this one.
- **Protein's subset-filter subsystem** (~450 lines: add/edit/delete/save/load
  named SQL filters, built on shared `AddSubsetFilterDialog`/
  `EditSubsetFilterDialog`/`MultiSelectFilterComboBox` widgets) is almost
  entirely generic plumbing, with only a default-column-list literal
  (`["sublevel_current", "voltage", "duration"]`) that's genuinely
  Protein-specific. Clustering and Metadata weren't audited for this specific
  feature, so whether they need the same subsystem is unconfirmed — check
  before assuming this is a 3-family candidate rather than a Protein-only one.
- **Duplicate-column validation.** Clustering raises `KeyError` for a
  repeated column name; Metadata shows a `QMessageBox.warning` and returns
  `False` for the same underlying check. Extracting the check itself is easy;
  the two families' error-reporting conventions would need to be reconciled
  first, or the shared helper would need to accept the reporting strategy as
  a parameter.

## Tier 3 — architectural observations bigger than any one method

- **The walkthrough mixin should be owned by `MetaView`, not bolted on by
  convention.** All 5 families do the identical dance: declare
  `class <Name>View(MetaView, WalkthroughMixin)`, hand-call
  `self._init_walkthrough()` right after `super().__init__()` inside their
  own `__init__`, and implement `get_current_view()`/`get_walkthrough_steps()`
  as required overrides. `WalkthroughMixin` already declares those two as
  `NotImplementedError`-raising abstract-style hooks — it's already designed
  like part of the base contract, it just isn't integrated into `MetaView`'s
  actual `__init__`/ABC machinery (`QWidgetABCMeta`). This is the cleanest
  "this should always have been on the base class" finding in the audit:
  `MetaView.__init__` could call `_init_walkthrough()` unconditionally, and
  `get_current_view`/`get_walkthrough_steps` could become real
  `@abstractmethod`s on `MetaView` (or on a `MetaView`-owned version of the
  mixin) instead of a separate opt-in multiple-inheritance contract every new
  family must remember to wire up by hand. Note `get_current_view()` in
  Clustering and Metadata just hardcodes `return "ClusteringView"` /
  `"MetadataView"` — exactly `self.__class__.__name__` — which could become
  the mixin's own default instead of a per-subclass override.
- **The Controller-relay pattern suggests `MetaController` might benefit from
  a generic dispatch mechanism** — e.g. a decorator-registered relay table —
  instead of hand-writing a 1–3 line `set_X`/`relay_X` method for every single
  signal, repeated dozens of times per family across at least 4 of the 5
  families. This is a materially bigger and riskier redesign than everything
  else in this file; recorded as an observation for whoever eventually owns
  `MetaController`, not as a concrete near-term recommendation.

## Correctness issues found incidentally (not promotion candidates — worth a look independent of any refactor decision)

- **`update_available_plugins` is re-overridden in `RawDataController` and
  `EventAnalysisController` with the model/view call order reversed**
  relative to `MetaController`'s own default implementation (which does
  view-then-model, and is explicitly commented "should generally be left
  alone by subclasses"). Both subclass overrides do model-then-view instead,
  plus an extra debug log. Possibly harmless, possibly a latent ordering bug
  — worth checking whether any downstream code depends on one order or the
  other before touching this.
- **`_factors(n)` is copy-pasted byte-identical into `RawDataView` and
  `EventAnalysisView` despite already existing, unmodified, on `MetaView`**
  (`MetaView.py:130-148`). Pure dead duplication with zero behavioral
  difference from the inherited version — safe to just delete both overrides
  independent of any other decision in this file.
- **`_start_writer`'s ret-args/call-args tuple shape differs between RawData
  (bare `channel`) and EventAnalysis (`(channel,)`)** for what reads like the
  same conceptual call into the generator-wiring skeleton. Possibly
  intentional (different callee signatures), possibly an inconsistency —
  confirm which before using either as the canonical shape for a Tier-2
  promotion of that skeleton.
- **`RawDataView.update_plot_data` carries the implementer's own comment**
  ("event data now returns a dict - this should be refactored to handle this
  explicitly") describing exactly the dict-unwrapping logic
  (`if isinstance(data, dict): self.plot_data = data["data"] else: ...`) that
  `EventAnalysisView.update_plot_data` independently reimplements too, with
  the same behavior. A good opportunity to resolve the acknowledged TODO and
  promote the fixed version to `MetaView.update_plot_data`'s default body in
  the same change, rather than treating "fix the TODO" and "deduplicate" as
  separate efforts.

## Peripheral finding: `PluginManagerPopup.py` appears to be dead code

`poriscope/plugins/analysistabs/utils/PluginManagerPopup.py` defines a
`PluginManager(QDialog)` that is referenced only in its own file's
`if __name__ == "__main__":` demo block — no other file in the tree
instantiates it. The real add/edit/delete-plugin flow all 5 families actually
use goes through `MetaView.handle_add_triggered`/`handle_edit_triggered`/
`handle_delete_triggered`. This isn't evidence of a missing `MetaView`
affordance (that affordance already exists and is already used) — it looks
like a superseded prototype nobody removed. Confirm with git history or the
original author before deleting; not otherwise part of this refactor.

## Value and wisdom

This is worth doing, but staged, and it's a lower priority than the QA/
compliance-gate work tracked in `future_fixes.md`.

Reasons to do it:

- The single strongest finding — the `update_available_plugins` skeleton
  appearing identically in all 5 families — is exactly the kind of thing a
  future community-contributed 6th tab family would otherwise have to
  reverse-engineer by reading existing tabs, which is literally what the
  plugin development docs currently recommend ("use `Protein*` as a
  template"). Promoting it makes the base class actually teach the contract
  instead of relying on copy-paste-from-an-example.
- The `*controls.py` mixin extraction has the best cost/benefit ratio here:
  highest duplication density, fully additive (no existing class hierarchy
  needs to change), and outside the `Meta*` ABCs entirely, so it carries none
  of the risk described below.

Reasons to be careful and stage it:

- Anything that changes a `MetaView`/`MetaController`/`MetaModel` method
  **signature** (not just its body) risks the exact cascade this codebase
  already hit twice during the pydoclint/annotation work this session:
  `tests/unit/plugins/test_plugin_compliance.py` does exact-equality checks
  on overridden method signatures for these three bases too (they're in its
  `META_CLASSES` set, same as the data-plugin `Meta*` bases) — so promoting
  even a well-chosen method up to `MetaView` means re-verifying all 5
  subclasses' overrides don't now mismatch, and the mypy
  `check_untyped_defs`/annotation-cascade behavior documented in
  `future_fixes.md` is exactly as live here as it was for data plugins.
- The walkthrough-mixin integration is the most conceptually satisfying
  "this obviously belongs on the base class" finding, but also the one with
  the widest blast radius — it means touching all 5 subclasses' `__init__`
  simultaneously to remove the now-redundant manual `_init_walkthrough()`
  call — for a purely structural win (it already works correctly today; this
  only removes repetition).
- A few findings above aren't promotion candidates at all — they're latent
  bugs the audit surfaced as a side effect (the call-order reversal, the
  arg-shape inconsistency). Treat those as independent, smaller fixes; don't
  let them block or get bundled into a refactor decision.

Suggested sequencing if this gets picked up:

1. `BasePluginControls` mixin extraction (additive, highest duplication
   density, zero `test_plugin_compliance.py` risk).
2. The `update_available_plugins` template method (universal across all 5,
   well-understood shape).
3. The RawData/EventAnalysis Tier-1 pairs, two files at a time (well-scoped,
   `_shift_range_and_update_plot` first since it's the highest-value/lowest-
   risk single item).
4. The DB-column-overwrite helper (Clustering/Protein) and figure-reset
   skeleton (Clustering/Metadata, adopting Metadata's `_axes_valid` version),
   once the shape of a template-method promotion is well-exercised from step
   2.
5. Walkthrough-mixin integration last, since it's the widest blast radius for
   the smallest behavioral change.
6. Only after step 1 (`BasePluginControls`) has landed: Part 2 below
   (widget-state session persistence). It's a new feature, not a refactor,
   but it's design-dependent on `BasePluginControls` existing, which is why
   it's recorded in this same file instead of `future_fixes.md` or a
   separate feature-ideas file.

Fix the correctness issues (call-order reversal, arg-shape inconsistency,
dead `_factors` duplication) independently, whenever convenient — they don't
depend on, and shouldn't wait for, any of the above.

---

# Part 2: Session Persistence for Frontend Widget State

**Depends on Part 1's `BasePluginControls` extraction landing first.** Do not
start this until that exists — see "Why this depends on Part 1" below for
why the design leans on it directly, not just for convenience.

## Goal

Extend Poriscope's session save/load so that reloading a session restores
not just which plugins exist (already handled by `session/plugin_history.json`)
and not just the sequence of user actions that shaped memory-heavy state
(already handled by `@register_action` / `session/tab_action_history.json`),
but also the visible state of each tab's **control panel** widgets — which
combobox item is selected, which checkboxes are ticked, what's typed into a
line edit — so a reloaded session looks the way the user left it, not just
functions the way the user left it.

Explicitly out of scope: matplotlib plot canvases and anything in the
display area (`MetaView._set_custom_display_area`'s territory) — only the
control panel (`MetaView._set_control_area`'s territory) is in scope.

## How `@register_action` actually works (context for why this is a different kind of problem)

`poriscope/utils/LogDecorator.py:151-170` implements `@register_action` as a
**command/event-sourcing** pattern: it wraps a method, and after the real
call runs, emits `update_tab_action_history` with
`{"function": func.__name__, "args": args, "kwargs": kwargs}`.
`MetaController.update_tab_actions` appends that into an ordered log; on load,
`MetaView.update_actions_from_json` replays each entry in order via
`getattr(self, val["function"])(*args, **kwargs)`. This exists because raw
memory state (event traces, fit results) is too large to serialize directly
— replaying the cheap recipe that built it is the only practical option at
that scale.

**Widget state does not have that scale problem.** A combobox's current
text, a checkbox's boolean, a line edit's string are all trivially small. So
while the *ergonomic goal* transfers directly (a developer marks something
once, persistence "just happens"), the *mechanism* should not: this should be
a direct snapshot/restore, not an event-sourced replay log. Do not build this
as a decorator that mirrors `@register_action`'s replay design — that
solves a problem this feature doesn't have, and (see below) actively risks a
correctness bug if the two mechanisms' replay/restore ordering isn't
carefully sequenced.

## Recommended design

A hybrid of "pure reflection" plus an escape hatch owned by the widgets
themselves, hosted on the `BasePluginControls` mixin from Part 1:

1. **Default path — reflection, zero per-widget code.** `BasePluginControls`
   (once it exists per Part 1) provides a default `get_state()`/`set_state()`
   that walks its own child widgets (`self.findChildren(QWidget)`), dispatches
   by type to known Qt get/set pairs (`QLineEdit.text`/`setText`,
   `QCheckBox.isChecked`/`setChecked`, `QComboBox.currentText`/`setCurrentText`
   or `currentIndex`/`setCurrentIndex`, spin box `value`/`setValue`, ...), and
   keys the result by each widget's `objectName()`. A developer adding an
   ordinary widget to a control panel gets save/restore for free, with no
   decorator and no registration call, as long as the widget has a distinct
   `objectName()` — already normal Qt/Designer practice.
2. **Escape hatch — built into the custom widget classes directly, not an
   external registry.** The project's two custom composite widgets used
   across control panels, `MultiSelectComboBox` and `MultiSelectFilterComboBox`
   (`poriscope/views/widgets/multiselect.py`, `multiselect_filter.py`), don't
   reduce to one scalar Qt property, so they should implement their own
   `get_widget_state()`/`set_widget_state()` directly on the class, which the
   reflective walker calls in preference to the generic type-dispatch path
   when present. This keeps the "how do I persist myself" knowledge co-located
   with the widget that owns it, rather than in a lookup table the walker
   maintains on behalf of widgets it doesn't own.
3. **Scope boundary is "child of a `BasePluginControls` instance," not
   "anything reachable from the control panel."** Modal dialogs launched from
   a control panel (`SelectionTree`, `TimeWidget`,
   `AddSubsetFilterDialog`/`EditSubsetFilterDialog`, `ClusteringSettingsDialog`
   — all under `poriscope/views/widgets/`) are excluded by construction, since
   they aren't children of the controls widget itself — their results already
   get written back into a plain attribute or into a primitive widget by the
   time they close, which is what actually gets persisted.

## Why this depends on Part 1

Building the reflective walker against the 5 still-divergent
`*controls.py` files (`rawdatacontrols.py`, `eventAnalysisControls.py`,
`clusteringcontrols.py`, `metadatacontrols.py`, `proteincontrols.py`) means
writing it once per family and then having to reconcile 5 near-duplicate
implementations later when `BasePluginControls` eventually gets extracted
anyway per Part 1. Building it against `BasePluginControls` directly means
writing it once. This also gives the (best-effort) `@register_action`
safety check described below a clean scope check — "does this method's body
reference something reachable from `self.<attr>` where `<attr>` is a
`BasePluginControls` instance" — instead of a fuzzier attribute-name grep.

## Confirmed interaction risk with `@register_action` — not hypothetical

Checked directly against the code rather than assumed: `@register_action` is
used at only 5 call sites total (`ClusteringView._reset_actions`,
`MetadataView._reset_actions`/`_overlay_plot`,
`ProteinView._reset_actions`/`_update_distribution_ensemble`), and every one
takes `axis_type` or a `parameters` dict — never a widget object — so there's
no *object-level* overlap between what `@register_action` records and what
this feature would persist.

However, `MetadataView._overlay_plot` (`MetadataView.py:1146-1160`, decorated
with `@register_action`) internally calls `self.get_selected_filters()`
(`MetadataView.py:3099-3106`), which reads live off
`self.metadatacontrols.filter_comboBox.getSelectedItems()` — a control-panel
widget this feature would persist — rather than receiving that value as part
of its own recorded `parameters` argument. This creates a real **load-order
dependency**: on session reload, `_overlay_plot`'s replay is only correct if
widget-state restoration has *already* put `filter_comboBox` back to its
saved selection before the action log reaches this call. If restore runs
after action-replay (or not at all before it), the regenerated plot will
silently use whatever the combobox happens to contain at that moment, not
what was actually saved.

This should be treated as a **prerequisite fix, not just a risk to note**:
before or alongside implementing this feature, `_overlay_plot` should be
changed to receive the filter selection through its own `parameters` dict,
the same way `plot_type`/`db_loader` already arrive — making it a pure
function of its arguments like the other 4 `@register_action` call sites
already are. The general rule this establishes: **a `@register_action`
-decorated method must not read control-panel widget state directly; anything
it needs must arrive as an argument.** Document this rule explicitly (in
`register_action`'s own docstring, and in whatever doc ends up describing
this feature), since it's what keeps the two mechanisms from silently
producing wrong output when combined.

(Separately, and *not* something this feature needs to solve:
`_overlay_plot` also reads `self.selected_experiment_and_channels_by_loader`,
populated only by a modal `SelectionTree` dialog result
(`MetadataView.py:2727-2734`) — not a control-panel widget, not covered by
`@register_action` either. That's a pre-existing gap in what's actually
replayable today, independent of this feature's scope.)

## Enforcing the "no live control-panel reads inside `@register_action`" rule

Two different strengths of enforcement, worth not conflating:

- **Cheap and mechanical:** flag any `@register_action`-decorated method
  whose name looks like a setter (`set_*`/`_set_*`) — a one-line AST/regex
  lint, the same shape as the other tribal-knowledge rules recorded in
  `future_fixes.md`'s docstring/QA discussion.
- **The actual hazard is harder to catch mechanically.** The real problem in
  `_overlay_plot` wasn't its name — it's a method that reads live widget
  state from *inside its body*. A heuristic AST lint flagging any
  `@register_action`-decorated method whose body references
  `self.<attr>.*` where `<attr>` resolves to a `BasePluginControls` instance
  is doable and worth adding once `BasePluginControls` exists (see "Why this
  depends on Part 1" above), but it will have false positives/negatives and
  should be treated as a best-effort aid, not a guarantee. The documented
  rule (previous section) is what actually has to carry the weight here —
  don't oversell the lint as sufficient on its own.

## Confirmed: control-panel widgets are cleanly JSON-primitive, with one scope nuance

Checked directly rather than assumed. Standard widgets (`QLineEdit`,
`QCheckBox`, `QComboBox`, spin boxes) are obviously primitive-valued.
`MultiSelectComboBox.getSelectedItems()` (`multiselect.py:196-201`) returns a
plain `list[str]` — also clean; `MultiSelectFilterComboBox` should be checked
the same way when this is picked up (not independently re-verified here).

The one nuance: the modal dialogs launched from control panels
(`TimeWidget.result`, for example, ends up being a dict of parsed numeric
ranges per `time_widget.py:169`) do hold richer transient state while open —
still primitive-shaped in the one case checked, but more importantly, out of
scope by construction per the "child of `BasePluginControls`" boundary above,
not because their contents happen to be simple. Keep the scope boundary
explicit in whatever gets built: it's "persistent widgets embedded in the
control panel," not "anything reachable from the control panel."

## Restore-time signal re-entrancy

Setting a widget's value programmatically fires the same Qt signal a real
user interaction would, and those signals are typically wired into
`handle_parameter_change`/`global_signal` chains that can trigger side
effects (spawning plugin creation, firing DB queries). Restoring a tab's
worth of widgets at load time needs to do so quietly — block the relevant
signals during restore (e.g. `QWidget.blockSignals(True)`/a guard flag
checked inside handlers) so that repainting the UI to match the saved state
doesn't itself replay a cascade of the actions that originally produced that
state. This needs to be paired with a well-defined position in the existing
load sequence (`MainController.load_session` restores plugins, then
instantiates tabs, per `main_controller.py:451-482`) — widget-state restore
should happen after a tab's plugins are available (in case a combobox
references a plugin key) and its ordering relative to `@register_action`
replay needs to be decided deliberately, not left implicit — see the
`_overlay_plot` risk above for exactly why.

## Value and wisdom

Worth doing, and it's the kind of small polish that meaningfully improves
perceived quality without much conceptual risk once `BasePluginControls`
exists — but it should stay ordered after Part 1's extraction, not attempted
in parallel with it, and the `_overlay_plot` prerequisite fix (or an
equivalent audit for any other `@register_action` site that reads live
widget state) should land before or alongside it, not after. Don't model
this as a decorator mirroring `@register_action` — the event-sourcing
mechanism solves a scale problem this feature doesn't have, and copying it
would import the replay-ordering fragility this section documents without
any corresponding benefit.
