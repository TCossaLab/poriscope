# Future Refactors and Features: Poriscope Core Architecture

Context block for a dedicated future session. This file is separate from
`future_fixes.md` on purpose: `future_fixes.md` tracks QA/tooling work (type
annotations, compliance-gate infrastructure for community contributions);
this file tracks *changes to the application's own architecture and
implementation* — refactoring existing code, new features that depend on
that refactoring, and standalone improvements to existing mechanisms. Keep
that QA-vs-architecture distinction when deciding whether something belongs
here or in `future_fixes.md`.

The file grew from one subsystem (the frontend analysis-tab plugin base
classes, Parts 1-3) into a much broader core-codebase audit (Parts 4-12).
It's kept as one file rather than split further because several parts
cross-reference each other (see the per-part notes below), and because
splitting by subsystem would have meant guessing in advance which future
session needs which slice — a single file with clearly labeled, largely
independent parts is easier to navigate than several smaller files whose
boundaries don't cleanly match how the work will actually get picked up.

**Parts 1 and 2** are kept in this order deliberately: Part 2 (widget-state
session persistence) should not be implemented before Part 1's
`BasePluginControls` extraction lands, because Part 2's design leans
directly on that shared base existing. If Part 1 is ever done
incrementally, do the `BasePluginControls` extraction (Part 1, Tier 1
headline finding) before starting Part 2, even if the rest of Part 1 is left
for later.

**Part 3** (`register_action` overwrite-mode recording) has no ordering
dependency on Parts 1/2 — it can be picked up independently, whenever
convenient — but it modifies the exact decorator Part 2 relies on and Part
1 already flags for a documentation pass.

**Parts 4 through 12** are a different kind of entry than Parts 1-3: each is
a raw findings list from a read-only simplification audit of a different
slice of the core (non-plugin) codebase — `poriscope/controllers/`,
`poriscope/models/`, `poriscope/views/`, `poriscope/utils/`, and
`poriscope/main_app.py` — explicitly favoring simplicity/readability over
micro-efficiency, per the audit's own brief. None of Parts 4-12 is a
worked-out design like Parts 1-3, and none of them depend on each other or
on Parts 1-3 — any single finding in any part can be picked up in isolation.
A cross-cutting synthesis of the recurring patterns across Parts 5-12 is at
the very end of the file, after Part 12.

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
- **`@register_action`'s contract should be documented directly on the base
  classes, not left implicit.** Part 2 of this file (widget-state session
  persistence) establishes two standing invariants that `@register_action`
  usage across all 5 families needs to keep holding: a
  `@register_action`-decorated method must never read live control-panel
  widget state (it must be a pure function of its own arguments), and a
  tab's action replay must stay self-contained to that tab (never assume
  another tab's log has been, or will be, replayed). Neither is currently
  written down anywhere near the mechanism itself — `register_action`'s own
  docstring in `poriscope/utils/LogDecorator.py` says nothing about either
  constraint, and `MetaController.tab_action_history`/`MetaView`'s
  replay path don't reference them either. Whenever Part 1 work next touches
  `MetaController.py`, `MetaView.py`, or `LogDecorator.py` for any of the
  reasons above, it's worth adding these two rules to the relevant
  docstrings in the same pass, rather than treating it as a separate future
  documentation task — see Part 2's "Settled design decision: two-step,
  per-tab session load" section for the full reasoning behind both rules.

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
references a plugin key). Its ordering relative to `@register_action` replay
is resolved below, not left implicit.

## Settled design decision: two-step, per-tab session load

Session load is two deliberately separate steps, and both operate per-tab
rather than globally:

1. **Automatic, on load:** plugin restoration (already existing,
   `MainController.load_session`) plus, once built, widget-state restore for
   that tab's control panel.
2. **Explicit, user-triggered, per tab:** `@register_action` replay — i.e.
   re-running whatever expensive memory-state reconstruction that tab's
   action log represents. Never fired automatically as a consequence of step 1.

**This was a deliberate choice, made for two independent reasons that both
hold up:**

- **Avoiding a long-running, blocking operation on file→open.** Action
  replay executes arbitrary registered calls (potentially expensive memory-
  state reconstruction, per the pattern's original motivating case); nothing
  about opening a session file should force the user to wait through that
  before seeing anything.
- **Granularity.** Frontend plugins are standalone by design (each analysis
  tab is an independently instantiated Controller/Model/View triad, per
  `CLAUDE.md`'s architecture description) — a user may want to restore only
  `MetadataView`'s widget state and glance at its settings without paying
  the cost of re-running `RawDataView`'s or `EventAnalysisView`'s action logs
  from scratch. A single global "replay everything" convenience would work
  directly against that and should not be built, even as a later addition,
  unless a future need for it is explicitly identified — per-tab is the
  correct default, not just an inherited accident of the current file-picker
  UI.

**This is confirmed to already be how the codebase behaves, not a new
departure:** `MainController.load_session` never calls
`load_actions_from_json` anywhere (checked directly — it only wires up
*saving* the action log, via `update_tab_action_history`/
`save_tab_action_history`). Loading it has always been a separate, explicit,
per-tab flow through `MetaView._load_actions_from_json()`'s file dialog. The
two-step, per-tab design isn't introducing a new principle — it's
recognizing and preserving one that's already there, and extending step 1 to
also cover widget-state restore rather than trying to fold step 2 into the
automatic path.

**This also resolves the `_overlay_plot`/`get_selected_filters()` ordering
hazard documented above by construction**, not just by convention: as long
as step 1 always fully completes before step 2 is even offered to the user,
there is no window in which action-replay can run against not-yet-restored
widget state. The prerequisite fix to `_overlay_plot` (routing the filter
selection through its own `parameters` argument instead of reading it live)
is still worth doing regardless — a `@register_action`-decorated method
should never depend on being called at a particular moment relative to
some other restore step — but this design removes the one concrete way that
dependency could currently produce a silently wrong result.

**Two standing invariants this design depends on** (both true today, worth
writing down so they don't get accidentally broken by a future contribution):

1. A control-panel widget's *available options* must never depend on
   `@register_action`-replayed state, only on persisted/plugin-queryable
   state. Checked directly: filters, cluster columns, and DB columns are all
   sourced from SQLite tables via loader plugins (already on disk, restored
   in step 1), never from in-memory action-replay artifacts. If a future tab
   populated a combobox's options from something only step 2 creates, the
   per-tab granularity this design is built around would break — a user
   skipping that tab's action replay would be left with a widget offering
   options that don't actually exist yet.
2. A given tab's `@register_action` replay must be self-contained to that
   tab — it must never assume another tab's action log has already been (or
   will be) replayed. This is what makes "restore Metadata but skip RawData
   and EventAnalysis" a coherent thing for a user to do at all, and it's
   consistent with `tab_action_history` already being keyed per tab-subclass
   name rather than as one global sequence.

**Not resolved by this decision alone — a complementary, separate concern:**
making the trigger explicit and per-tab prevents a surprise freeze on file
→open, but doesn't prevent a slow tab's replay from blocking the UI thread
for however long it takes once the user does trigger it, since replay
currently executes synchronously (`getattr(self, function)(*args, **kwargs)`
in a plain loop, per `MetaView.update_actions_from_json`) rather than through
the existing async worker/progress-bar machinery
(`MetaModel.set_generator`/`run_generators`). Worth deciding, whenever a
tab's action log is likely to contain something non-trivial, whether that
tab's "replay actions" trigger should route through that existing
infrastructure instead of assuming a plain synchronous loop stays
acceptable.

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

---

# Part 3: `register_action` — Optional Overwrite-Mode Recording

A standalone, independently-shippable improvement to `@register_action`
itself, unrelated to whether Parts 1 or 2 above ever get built. Recorded
here rather than in a separate file because it modifies the exact same
decorator Part 2 depends on and Part 1's new documentation bullet already
references.

## Current behavior

`register_action()` (`poriscope/utils/LogDecorator.py:151-170`) takes no
arguments today. Every call to a decorated method unconditionally appends a
new entry: `MetaController.update_tab_actions`
(`MetaController.py:461-500`) does
`self.tab_action_history[len(self.tab_action_history)] = history` — a plain
append keyed by the next integer index, with no check for whether the same
function was already recorded earlier. On replay, every one of those
entries gets re-run in order.

## Proposed change

Add a decorator-factory argument controlling how a call is recorded, e.g.
`@register_action(mode="serial")` (the current, and default, behavior) vs.
`@register_action(mode="overwrite")`. In overwrite mode, a new call to the
decorated function replaces whatever entry the *same function* already has
in the log, instead of appending a new one alongside it. This should be a
decoration-time choice (set once per decorated method, like
`register_action()`'s current no-argument form), not a per-call runtime
argument — a given action should consistently behave one way or the other.

**Rationale (the actual problem this solves):** some registered actions are
idempotent in the sense that only their *final* state matters — calling them
repeatedly just resets the same relevant memory state each time. Recording
every intermediate call in serial mode means the saved log is larger than it
needs to be, and replaying it re-runs work that gets immediately superseded
by the next recorded call anyway. Overwrite mode records only what actually
still matters at save time. Defaulting to `mode="serial"` keeps all 5
existing `@register_action` call sites unchanged and behaviorally identical.

## Open design questions to resolve before implementing (not decided here)

- **What identifies "the same function" for overwrite purposes?** The
  natural first answer is `func.__name__` alone, matching how replay already
  dispatches via `getattr(self, history["function"])`. But several of this
  codebase's decorated-method candidates take a channel (or other
  discriminating) argument — if a hypothetical future `@register_action`
  -decorated method were called once per channel, collapsing purely by
  function name would incorrectly discard an earlier channel's recorded call
  when a different channel's call comes in later. Whether overwrite mode
  needs a narrower dedup key (function name *plus* a caller-specified subset
  of args/kwargs that identifies "the same logical target") should be
  settled before this ships, not discovered after the fact on the first
  per-channel action that opts into it.
- **Does an overwrite replace the entry in its original sequence position,
  or move it to the end (the position of the most recent call)?** These
  differ whenever other, unrelated actions were recorded in between the two
  calls to the same function, and the difference is observable on replay if
  anything about those in-between actions is order-sensitive. Pick one
  deliberately; don't let it fall out of whichever is easiest to implement
  against the current `OrderedDict`-by-integer-index storage.
- **Storage/lookup shape.** The current structure is append-only, keyed by
  an ever-incrementing integer with no index from function name to position.
  Supporting "find and replace the existing entry for this function" needs
  either a scan over the existing entries (fine at this scale) or a small
  secondary index — a minor implementation detail, but one that touches the
  same data structure the undo path in `update_tab_actions` already
  manipulates, so it should be designed alongside that logic, not bolted on
  independently.

## Cross-references

- Complements Part 2's synchronous-replay-blocking observation: fewer
  redundant recorded calls directly means less work to redo when a tab's
  action log is eventually replayed, whether or not that replay is ever
  moved onto async infrastructure.
- Should be covered by the same `MetaController`/`MetaView`/`LogDecorator`
  docstring pass flagged in Part 1's Tier 3 (the `@register_action` contract
  bullet) — this argument's semantics (especially the dedup-key question
  above) need to be as clearly documented as the two standing invariants
  already flagged there, for the same reason: nothing about this is
  currently discoverable except by reading the decorator's source.

---

# Part 4: Core Utility Module (`poriscope/utils/`) Simplification Candidates

## Background and scope

A read-only audit (2026-08) of nine small, low-level, widely-imported utility
modules — `LogDecorator.py`, `EventWorker.py`, `QObjectABCMeta.py`,
`QWidgetABCMeta.py`, `BaseLineEdit.py`, `BaseValidator.py`,
`JsonDefaultSerializer.py`, `QtHandler.py`, `DocstringDecorator.py` — looked
for code that's more complex than the problem it solves: over-engineered
decorators/metaclasses, duplicated logic within a file, and control flow
that's harder to follow than the underlying task requires. It deliberately
did not look for correctness bugs or type-hint/docstring gaps (those are
separate, already-completed audits), and it is not a worked-out design like
Parts 1-3 — it's a punch list of specific spots worth a closer look. Each
item below is flagged with what's there and why it stood out; none of them
depend on each other or on Parts 1-3, so any subset can be picked up
independently, whenever convenient. Line numbers are as of the 2026-08 audit
and may drift — re-check the citation before acting on it.

## Findings, roughly in order of expected value if pursued

1. **`LogDecorator.py:96-104` and `111-119` — duplicated exception-suppression
   logic.** The inner `log_call` and `log_return` closures inside `log()`
   each carry an identical try/except that swallows a logging failure and
   sets a one-shot `logger.root.ignore_exceptions` flag (via `hasattr`/
   `setattr` on the root logger object) so the same warning isn't repeated.
   Worth checking whether this can become one shared helper instead of two
   copies — but `log()` wraps nearly every plugin method in the app, so
   whoever picks this up should scope how wide `@log`'s usage actually is
   before touching it.

2. **`LogDecorator.py:34,79-80` — `debug_only` parameter looks dead.**
   `log(_func=None, *, logger, debug_only=False)` documents `debug_only` as
   controlling whether the decorator "is only to run in debug mode," but
   nothing in `decorator_log`/`log_call`/`log_return`/`generator_wrapper`/
   `wrapper` ever reads it, and a repo-wide search found no call site passing
   `debug_only=True`. Unlike `register_action`'s reserved-for-extension
   no-arg factory (Part 3 above), nothing in this file or elsewhere
   documents `debug_only` as an intentional future hook. Worth confirming
   it's genuinely unused (not, say, read by something outside this file via
   introspection) before deciding whether to delete it or wire it up.

3. **`EventWorker.py:70-84` — three near-identical `except` clauses in
   `Worker.process_generator`.** `RuntimeError`, `ValueError`, and `IOError`
   each get their own clause doing the same thing (log at `error`, `break`),
   differing only in which exception type the log message names. (Also note
   `IOError` is just an alias for `OSError` in Python 3 — worth checking
   whether that aliasing was intentional or just how the list grew over
   time.) Candidate for collapsing into one tuple-based `except` clause.

4. **`EventWorker.py:85-90` vs. `run()`'s `finally` at line 112 — possibly
   redundant progress-bar emission.** The catch-all `except Exception`
   branch inside `process_generator` explicitly emits
   `update_progressbar.emit(100, ...)` before breaking, but `run()` (the
   only caller found) already unconditionally emits the same thing in its
   own `finally`. The other three `except` branches (`StopIteration`,
   `RuntimeError`, `ValueError`, `IOError`) don't emit it locally. Worth
   figuring out whether this asymmetry is deliberate (e.g. for some caller
   of `process_generator` that doesn't go through `run()`) before removing
   it — a grep for direct callers of `process_generator` would settle it.

5. **`EventWorker.py:103-110` — `except Exception: raise` inside `run()`
   appears to be a no-op.** It catches every exception only to re-raise it
   unchanged, which reads as behaviorally identical to omitting the
   `except` clause and keeping just `try`/`finally`. Cheap to verify and
   cheap to remove if confirmed inert.

6. **`EventWorker.py:57-61` — `send`-vs-`next` dispatch via catching
   `TypeError`.**
   ```python
   try:
       p = self.generator.send(self.stop_requested)
   except TypeError:
       p = next(self.generator)
   ```
   This leans on the generator-protocol detail that `.send()` on a
   not-yet-started generator raises `TypeError`, so the first iteration
   falls through to `next()`. Worth a closer look at whether a genuine
   `TypeError` raised from inside the wrapped generator's own body (not from
   the send-before-start situation) could be misclassified here and silently
   retried as "generator not started yet" instead of propagating as the
   real error it is — and if so, whether an explicit `started` flag would
   remove that ambiguity. This is the core dispatch loop for every event
   finder/fitter's generator, so any change here needs real test coverage,
   not just a read-through.

7. **`QObjectABCMeta.py:34` / `QWidgetABCMeta.py:34` — leftover commented-out
   line.** Both files contain the identical dead comment
   `# abc._abc_init(cls)` inside `__new__`. Trivial to remove; flagged only
   for completeness.

8. **`QObjectABCMeta.py` / `QWidgetABCMeta.py` — duplicated `__call__`/
   `__new__` across two files.** The two metaclasses are identical except
   for which Qt base (`QObject` vs `QWidget`) they combine with. Real
   duplication, but these are two of the most foundational, most widely
   subclassed types in the whole plugin system — any future session
   considering deduplicating them (e.g. via a shared mixin) should weigh
   that against the blast radius of touching either file, not just the
   line count saved.

9. **`BaseLineEdit.py:39-40,94` — `suspend_validation`/`app_closing` are
   class attributes mutated as de facto process-wide globals**, toggled by
   a `QApplication`-wide event filter that reacts to *any* `QMessageBox`
   shown anywhere in the app (lines 91-97). Not a concurrency bug (Qt event
   filters run on the GUI thread), but it's an action-at-a-distance
   mechanism — reading `focusOutEvent`/`isValid` alone gives no hint that
   their behavior depends on an unrelated modal dialog elsewhere in the
   app. Worth at least a comment at the class-attribute declaration if this
   file is touched for another reason; a behavior-changing fix wasn't
   judged worth the risk on its own.

## Also reviewed, no findings

`BaseValidator.py`, `JsonDefaultSerializer.py`, `QtHandler.py`, and
`DocstringDecorator.py` were read in full as part of the same audit and
found to already be about as simple as the problem they solve — including
`QtHandler.py`'s `_dialog_open` re-entrancy guard, which is genuine
concurrency-adjacent logic already justified by an inline comment (a modal
`QMessageBox` runs a nested event loop that can deliver more queued log
records while it's open). Not included as findings, but listed so a future
session doesn't re-audit them from scratch.

---

# Part 5: App Shell & Generic Data-Plugin Management

Read-only audit (2026-08) of `poriscope/main_app.py`,
`poriscope/controllers/main_controller.py`, `poriscope/models/main_model.py`,
`poriscope/controllers/DataPluginController.py`,
`poriscope/models/DataPluginModel.py`, `poriscope/views/DataPluginView.py`,
`poriscope/exposed.py`, `poriscope/constants.py`. Same brief as Part 4: find
code more complex than the problem it solves, favoring readability over
micro-efficiency; not a correctness or docstring audit (though a couple of
correctness-adjacent issues surfaced anyway and are called out as such).

1. **`DataPluginController.edit_plugin` does five unrelated jobs in one
   ~180-line method** (`DataPluginController.py:72-256`): preparing settings
   for the edit dialog, the delete branch, the rename branch (which itself
   unregisters/re-registers dependents, checks global key-uniqueness, and
   rewrites dependent settings), resolving plugin-reference values back to
   live instances, and applying settings — with 4-5 separate `try/except`
   blocks each independently emitting `add_text_to_display` and calling
   `_restore_parent_dependent_links` as a rollback. Nesting reaches 5 levels
   in the dependent-rename loop (lines 153-179). Splitting into
   `_handle_delete`, `_handle_rename` (with `_rekey_dependents` factored out
   further), and a shared `_resolve_and_apply_settings` would let each
   branch's rollback become one wrapper instead of repeated inline calls.
   High value — the most complex method found in this part — but moderate
   risk to touch given several rollback paths that must be preserved exactly;
   worth pairing with the integration tests under `tests/integration/flows/`.

2. **The same "resolve plugin references, then apply settings" block is
   duplicated between `edit_plugin` (`DataPluginController.py:210-229`) and
   `validate_and_instantiate_plugin` (`:452-483`)**, and the "global plugin
   key collision check" loop is duplicated the same way (`:138-151` vs.
   `:422-434`). Both are copy-pasted, not shared. Extracting
   `_resolve_plugin_references(app_settings)` and
   `_check_key_available(key, exclude_metaclass=None)` as private helpers
   used by both call sites is high value, low risk (pure extraction of
   already-identical logic), and directly shrinks finding #1 too.

3. **`MainController.handle_global_signal`/`handle_data_plugin_controller_signal`
   are near-duplicate ~60-80-line dispatch methods** (`main_controller.py:186-327`)
   that both resolve a target instance, `getattr` a method by name string,
   validate it's callable, call it, and optionally call `return_function`
   with the result — differing only in how the target instance is resolved.
   Nesting reaches 5 levels in `handle_global_signal`. **Correctness-relevant
   detail, not just duplication:** both catch `TypeError` from calling
   `func(*call_args)` and blindly retry with `func(None)` (lines 240-242,
   253-254) — conflating "wrong arg count" with any other `TypeError` the
   callee's own body might raise, silently swallowing real bugs in the
   process. Extract a shared `_dispatch(instance, call_function, call_args,
   return_function, ret_args)` helper for the duplication (safe, high value);
   replace the `TypeError`-retry with an explicit `call_args = () if
   call_args is None else call_args` normalization at the call site instead
   of relying on an exception to detect "argument didn't apply" — this part
   carries real behavior-change risk, so check whether any existing callback
   actually depends on the None-retry fallback before removing it.

4. **`App.create_appdata_folders`** (`main_app.py:55-127`) repeats the same
   `if not X.exists(): X.mkdir(...)` pattern 4 times and the same
   `try: json.dump(...) except Exception: self.logger.warning(...)` pattern
   3 times, differing only in the log message. Extracting `_ensure_dir(path)`
   and `_write_config(config_file_path, config, context_msg)` turns this
   into a short, flat sequence. Medium value, low risk — one-time startup
   path, pure readability win.

5. **`MainModel.replace_classes_with_class_names`/`replace_class_names_with_classes`**
   (`main_model.py:322-358`) are mirror-image recursive tree walkers (one
   direction each), and the latter declares a mutable dict as a default
   argument (`class_dict={"str": str, ...}`, line 341) — harmless since it's
   never mutated, but an unnecessary footgun pattern given no caller ever
   overrides it. Move it to a module-level constant; optionally share one
   generic `_walk_and_transform(d, transform_fn)` helper between the two
   methods, though each is small enough that this is a nice-to-have. Low-
   medium value, essentially zero risk.

6. **`MainController.update_plugin_history`** (`main_controller.py:340-356`)
   calls `history.pop("key")` twice to both read and mutate the caller-
   supplied `history` dict as a side effect, which isn't obvious from either
   call site (`instantiate_analysis_tab`/`validate_and_instantiate_plugin`).
   Assigning `key = history.pop("key")` once up front when `history` is
   truthy, then branching only on `delete_key`, would make the mutation
   explicit. Low value on its own — a good drive-by fix if #1-#3 are being
   touched anyway, since this method is called from both.

**Not flagged** (reviewed, judged acceptable): `DataPluginModel.py`,
`DataPluginView.py`, and `exposed.py`/`constants.py` are thin and
straightforward (`exposed.py`'s long import/`__all__` list is exactly the
"long because the domain is detailed" case the brief excludes).
`MainModel.populate_available_plugins` (`main_model.py:166-239`) has nested
loops but each level does one clear thing and reads linearly; not genuinely
hard to follow as written.

## Addendum (2026-08-23 re-review)

A follow-up read-only re-review of just this part's files (two fresh
sub-agent passes, one per MVC triad) turned up one correction and a few
additional points worth recording alongside the findings above.

**Correction to finding #3:** the claim that "both [dispatch methods] catch
`TypeError` ... and blindly retry" is only true of `handle_global_signal`.
Direct re-check of `handle_data_plugin_controller_signal`
(`main_controller.py:309-323`) confirms it has **no** `TypeError`-retry
fallback around either the `func(*call_args)` call (line 313) or the
`return_function(*retval)` call (line 321) — despite its own docstring
claiming "Same dispatch mechanism as handle_global_signal" (line 277). This
is a real, observable asymmetry between the two methods today, not just
theoretical risk from a shared pattern: a caller relying on the None-retry
fallback behaves differently depending on which of the two signals it goes
through. Decide deliberately (make both retry, or make neither, and fix the
docstring either way) when finding #3 is addressed, rather than assuming the
current split behavior is intentional.

**Second opinion on `populate_available_plugins` (previously "not
flagged"):** re-confirmed that `main_model.py:216-233` does perform a real
second pass — `load_plugin` (called with the full tuple of allowed base
classes) already determines whether a class is a subclass of *any* allowed
base, then the caller loops over `allowed_base_classes.items()` again just
to find *which one* matched. This is genuine, if minor, duplicated work, so
a small fix (have `load_plugin` return the matched metaclass name directly)
is worth a look even though the original "linear and easy to follow"
judgment about readability still stands — the two takes weigh different
things (readability vs. avoiding recomputation) rather than disagreeing on
the facts.

**Additional points not previously recorded:**

- `main_controller.py:407-434` (`instantiate_analysis_tab`) wires 7 fixed
  signal→slot connections as 7 sequential `.connect()` calls, where
  `main_view.py:199-236` (`connect_signals`) already establishes this
  codebase's own convention for exactly this shape — a list of
  `(signal_name, slot)` tuples consumed in a loop via `getattr`.
  Restructuring to match would make it consistent with that convention and
  easier to extend. Moderate value, moderate risk (tab-instantiation
  wiring), mechanical.
- `main_model.py:273` (`get_plugin_data`) reconstructs the plugin-history
  file path from scratch (`Path(user_data_dir(), "Poriscope", "session",
  "plugin_history.json")`) instead of reusing `self.session_path`, already
  built once in `__init__` and reused by `load_session`/`save_session`. Not
  a bug today (same effective path), but a latent inconsistency a future
  path-construction change could silently miss. Trivial, low-risk one-line
  fix.
- `DataPluginController.edit_plugin`'s delete branch (`:114-132`) is close
  enough to `delete_plugin` (`:281-327`) that it's worth calling out
  explicitly as a candidate for `edit_plugin` just calling
  `self.delete_plugin(metaclass, key)` directly, beyond the general "five
  jobs in one method" framing in finding #1 — with the caveat that
  `edit_plugin` already unregisters the instance from its parents earlier
  in the method, so `unregister_dependent`'s idempotency (safe to call
  twice) should be confirmed before merging the two paths.
- The parent-link rollback repeated at `edit_plugin`'s several failure exit
  points (per finding #1) is a good candidate for a small context manager
  (e.g. `with self._parent_link_transaction(metaclass, instance, parents):`
  that unregisters on enter and restores on any exception) rather than a
  hand-repeated "call restore, then return" at each point — the current
  shape is exactly the kind of thing that silently breaks if a future edit
  adds another exit path and forgets the call.
- **Fixed** (2026-08-31): `DataPluginController.validate_and_instantiate_plugin`'s
  settings-from-history block used to read `self.historical_settings` immediately
  after emitting `get_settings_from_history`, relying on the connected slot having
  already run synchronously by the time execution resumed. It now calls a
  constructor-injected `history_lookup` callable directly and uses its return value -
  see `changelog.md` and `future_fixes.md`'s structural-audit entry.

None of these change the overall value/risk conclusions already reached for
this part; fold them in whenever findings #1-#3 above are next revisited.

---

# Part 6: `MetaController` / `MetaModel` / `MetaView` / `BaseDataPlugin`

Read-only audit (2026-08) of the four most foundational shared base classes
— the framework glue every other base and every plugin ultimately depends
on. Same brief as Part 5. Given the signal-relay pattern these classes are
built around (a function name plus args/kwargs carried across a `Signal`,
dispatched via `getattr` elsewhere) is an intentional, already-settled
architectural choice, findings below are about specific methods going
further than that pattern requires, not the pattern itself.

1. **`BaseDataPlugin.apply_settings` uses exception-driven type dispatch
   instead of an explicit check** (`BaseDataPlugin.py:313-350`):
   ```python
   try:
       self.raw_settings[key]["Value"] = self.settings[key]["Value"].get_key()
   except Exception:
       pass
   else:
       # register parents/dependents...
   ```
   Whether a setting value is "a plugin instance" is determined by calling
   `.get_key()` and catching *any* `Exception`, rather than checking
   `isinstance(val["Value"], BaseDataPlugin)` directly — meaning a real bug
   in the registration branch underneath would be silently swallowed by the
   same catch. **This is a correctness hazard, not just a style issue**, in
   a lifecycle method called by every data plugin on construction. Replacing
   it with an explicit `isinstance` check is high value and behavior-
   preserving; pair with a plugin-compliance test run given how central this
   method is.

2. **`MetaController._relay_global_signal`/`_relay_data_plugin_controller_signal`
   are near-duplicate ~60-line methods** (`MetaController.py:311-372,373-433`)
   — identical shape (resolve `return_function`, log, emit, catch+warn),
   differing only in which signal and label text. The `try/except Exception`
   around the `.emit()` call is also misleading: emitting a `Signal` doesn't
   raise for the reason the except-message implies (that check already
   happened above it). Extract a shared `_resolve_and_emit(signal, ...,
   signal_label)` helper; drop or correct the misleading except. High value
   (removes ~50 duplicated lines in the most heavily-relied-on relay
   mechanism in the app), low-moderate risk since behavior is preserved
   exactly — still worth a careful read-through given how central this is.

3. **`MetaController.update_tab_actions`'s undo branch** (`:461-500`) uses
   three nested layers of exception-driven control flow (`try/except
   KeyError: return`, then `try/except StopIteration: pass else: while ...`)
   to express "pop the most recent action, then keep popping past any
   trailing `_reset_actions` markers." A `_pop_last_action_skipping_resets()`
   helper using plain `if`/`while` guards (e.g. `next(reversed(...), None)`
   checked against `None` instead of catching `StopIteration`) would be
   substantially easier to trace. Medium-high value, low risk — self-
   contained, no external callers need to change.

4. **`MetaController.handle_kill_worker`** (`:229-283`) nests parsing,
   defensive full-dict logging, and lookup three levels deep. Flattening
   with early returns (parse-and-return-on-failure, then two more guard
   clauses before the actual stop) would remove the if/else pyramid and one
   duplicated "log the whole dict" call. Medium value, low risk — purely
   diagnostic method.

5. **`MetaView.update_progressbar`** (`:262-336`) mixes "is this a
   completion signal"/"does the bar exist" branching with ~50 lines of
   inline widget construction in the same method. Extracting the widget-
   build block into `_build_progress_bar_widget(identifier, value)` leaves
   `update_progressbar` as a short dispatcher. Medium value, low risk —
   purely additive extraction, no logic change.

6. **`_logscale_and_filter_multiple_columns`/`_logscale_and_filter_dataframe`**
   (`MetaView.py:673-765,767-841`) implement the identical NaN-filter-then-
   sequential-log-rectify algorithm twice, once for a list of arrays and once
   for a `DataFrame`. Having one delegate to the other (convert, call the
   array version, reassemble) would halve the surface area for future bugs.
   Medium value, medium risk — the two implementations already have subtly
   different edge-case handling (e.g. `dropna()` vs. array masking), so
   consolidating needs careful behavior-preserving verification; this logic
   is shared across multiple analysis tabs' plotting flows.

7. **`BaseDataPlugin._validate_param_ranges`** (`:422-446`) hardcodes an
   exemption for two specific parameter names (`"Output File"`, `"Input
   File"`) inside a validator whose own docstring says it's domain-agnostic
   — mixing subclass-specific knowledge into shared base-class validation.
   Moving the exemption out (either subclasses avoid supplying `Options` for
   file-path params, or the exemption moves into each subclass's
   `_validate_settings` override) is medium value, moderate risk — this runs
   on every `apply_settings` call for every plugin, so removing it without
   first checking which reader/writer plugins currently rely on it could
   break them.

8. **Repeated "ensure nested dict key exists" boilerplate across
   `MetaModel`** (in `set_generator`/`run_generators`/`discard_generator`) — the
   `if key not in self.<dict>: self.<dict>[key] = {}` pattern appears with
   minor variations across those methods, operating on parallel per-key/channel
   dicts. Smaller than when this was written: `set_force_serial_channel_operations`
   and the `serial_ops` dict it maintained are both gone, and `reset_lock` is now
   `discard_generator`. A tiny `self._ensure_nested(d, key)` (`d.setdefault(key, {})`)
   helper would collapse each occurrence to one line. Low-medium value,
   low risk.

**Not flagged** (reviewed, judged acceptable): `MetaView._factors` is more
elaborate than picking a near-square subplot grid strictly requires, but is
small, self-contained, and rarely called with large `n`. `MetaModel.stop_workers`'s
self-recursion for the "all keys / all channels / one channel" cases reads
fine as written. `MetaController.__init__`'s dozen-plus signal connections
are a flat, unavoidable enumeration of wiring, not complexity to simplify.

---

# Part 7: `MetaReader` / `MetaFilter` / `MetaEventLoader` / `MetaWriter`

Read-only audit (2026-08) of 4 of the data-plugin contract base classes.
Same brief as Parts 5-6. These classes drive real lifecycle/validation
logic beyond interface declarations, so substantial content here is
expected and, where it's genuinely earning its keep for domain reasons
(channel/buffer bookkeeping), it's noted as such rather than flagged.

1. **`MetaWriter._commit_events`** (`MetaWriter.py:343-471`) is the most
   complex method found in this part: ~130 lines defining a nested
   `lookahead_generator` function local to the method (itself a violation of
   this project's documented "no nested functions" convention), DB init,
   metadata writes, two early-exit checks, per-event bookkeeping across 4-5
   levels of nested `try/except/finally`, and a mutable `abort` flag threaded
   through nested scopes so the outer `finally` can see whether the inner
   loop aborted. Splitting into `_prepare_channel_for_writing(channel)`
   (init + metadata + early-exit checks) and `_write_single_event(...)`
   (the per-event write + bookkeeping, returning whether to abort) would
   leave `_commit_events` as a thin orchestrating generator; promote
   `lookahead_generator` to a module-level helper since it doesn't touch
   `self`. High value — genuinely hard to trace today — but inherited by
   every writer plugin and drives real write-atomicity semantics, so this
   needs careful behavior-preserving review and testing before landing.

2. **`MetaReader.load_data`** (`MetaReader.py:134-248`) mixes type coercion,
   two different `KeyError`→`IndexError` translations, bounds-clamping
   performed *before* bounds-validation (so a `start_index > total_samples`
   check that appears later can now never fire — dead validation, a small
   correctness-adjacent trap), and single-vs-multi-file assembly with the
   same `if raw_data: data, scale, offset = data` conditional unpack
   repeated 4 times. A small `_load_and_convert(...)` helper that always
   returns `(data, scale, offset)` would remove the repeated unpack; the dead
   bounds check should be dropped or the clamp/validate order reversed.
   Medium value — this is the hot path for every reader plugin, so keep any
   change to pure extraction/dead-code removal with reader compliance tests
   run afterward, not a broader rewrite.

3. **`MetaReader._get_file_index`** (`:877-896`) uses `try/except IndexError`
   as its loop-termination mechanism for what's really "find the last index
   `i` such that `file_start_index[i] <= index`" — an out-of-bounds access
   used to detect "reached the last file" instead of an explicit bounds
   check or `bisect.bisect_right`. Low-medium value, low risk — small,
   self-contained, called on every `load_data`/`continuous_read`, but the
   replacement is not meaningfully slower and far more obviously correct.

4. **`MetaReader._scale_data`** (`:826-875`) has an `if not raw_data: ...
   return` branch followed by an `else` that only conditionally raises, with
   the actual "return unchanged data" behavior for the raw+dtype-set case
   living in a `return` statement *outside* the if/else entirely — split
   across a branch and a trailing statement rather than visible together.
   Flattening with an early return would fix this. Low value, low risk,
   purely local readability.

5. **`MetaReader.continuous_read`**'s (`:339-404`) "avoid a small leftover
   chunk at the end" adjustment is a bare, unnamed boolean expression
   (`samples_to_load == chunk_length and last_sample - (i + chunk_length) <
   chunk_length / 2`) whose intent isn't legible without working out the
   arithmetic; naming it (e.g. `avoid_small_tail_chunk = ...`) would fix
   that cheaply. Also duplicates the same conditional-unpack shape as
   finding #2. Low value, low risk — cosmetic, cheap to do alongside #2.

**Not flagged** (reviewed, judged acceptable): `MetaFilter.py` is a thin
abstract contract with two trivial defaults — no complexity to reduce.
`MetaEventLoader.py`'s methods are short and linear. `MetaReader._finalize_initialization`
and `_get_file_start_indices`/`_get_total_channel_samples` are long
sequences of genuine channel/buffer domain bookkeeping, already commented,
not the "solving a simpler problem than its structure suggests" case.
`MetaWriter._rescale_data_to_adc` is branchy but each branch is a distinct,
clearly-labeled numerical conversion case touching a real numerical path —
not obviously simplifiable without losing clarity.

---

# Part 8: `MetaEventFinder` / `MetaEventFitter`

Read-only audit (2026-08) of the two largest data-plugin contract base
classes (~1000 lines each). Genuine domain complexity exists here — chunk-
boundary stitching, event straddling, padding calculation — and is
deliberately **not** flagged; the findings below are about bookkeeping/
control-flow structure that's simplifiable without touching the underlying
algorithm.

1. **`MetaEventFitter.fit_events`'s per-event loop repeats the same reject/
   pop/continue shape ~9 times** (`MetaEventFitter.py:505-707`, duplicate
   blocks at 515-519, 569-578, 579-588, 602-611, 619-628, 629-638, 640-657,
   682-691, 692-701) — increment a rejection counter, log, pop from two
   parallel metadata dicts, `continue`, varying only by reason string. A
   `self._reject_event(channel, index, reason, log_message=None)` helper
   would collapse ~35-40 lines of repetition and make the actual fitting
   logic far easier to scan. **The single biggest readability win found in
   either file.** High value; low-to-medium risk (mechanical, but verify no
   log message text is asserted on anywhere before merging).

2. **`MetaEventFinder.find_events` reimplements `reset_channel`'s reset
   logic inline instead of calling it, and `reset_channel` itself duplicates
   its own two branches** (`MetaEventFinder.py:168-190` vs. `264-274`) — the
   per-channel and "all channels" branches of `reset_channel` repeat the
   same 10 lines twice, and `find_events` repeats them a third time instead
   of calling `self.reset_channel(channel)`. High value, very low risk —
   purely removes duplication with identical behavior; the safest finding
   in the whole part.

3. **Boundary-reconciliation logic is duplicated verbatim** between
   `find_events` (`:342-357`) and `_find_events_single_range` (`:581-597`)
   — pop a trailing unmatched start, pop a leading unmatched end, raise
   `RuntimeError` after `reset_channel` if lengths still mismatch. Extracting
   a shared `_reconcile_event_boundaries(channel)` fixes the duplication.
   **Possible bug flagged alongside this, not confirmed:**
   `_find_events_single_range` sets `eventfinding_finished[channel] = True`
   and yields `1.0` at the end of *every single range* (`:611-612`), not
   just the last one — which could prematurely mark a multi-range channel
   "finished" mid-stream, ahead of `find_events`'s own final pass at line
   360. Worth verifying directly before assuming it's real, and a natural
   thing to check while doing the reconciliation-logic consolidation anyway.

4. **Padding coercion for `padding_before`/`padding_after` is written out
   twice, identically** (`MetaEventFitter.py:525-545`) — the same int/float/
   None type-coercion-or-raise logic, once per variable. A
   `self._coerce_optional_int(value, name)` helper replaces ~20 lines with 2.
   Medium value, low risk.

5. **Four near-identical list comprehensions filtering by `bad_indices`**
   (`MetaEventFinder.py:548-567`, inside `_find_events_single_range`) each
   repeat `[item for idx, item in enumerate(items) if idx not in
   bad_indices]` for a different parallel list. A local `_exclude_indices(items,
   bad_indices)` helper makes the intent ("excluding rejected indices from
   four parallel lists") explicit. Converting `bad_indices` to a `set` first
   would also be a free efficiency win (currently O(n²) via list membership
   testing), secondary to the readability point. Medium value, low risk.

6. **Duplicated "are events available" validation chains** between
   `get_event_data_generator` (`:713-730`) and `get_single_event_data`
   (`:774-784`) — nearly the same if/elif chain checking for `None`/empty/
   mismatched event state, in different order, with one method also
   checking `eventfinding_finished`. A shared `_require_events_ready(channel)`
   guard would consolidate this. Medium value, slightly more risk than #1-#5
   since the two chains aren't 100% identical — preserve exact exception
   types/ordering if anything depends on which error fires first.

7. **`MetaEventFitter.reset_channel`'s misleading exception handling**
   (`:333-349`): `try: self.eventfitting_status[channel] = False except
   KeyError: pass` wraps a plain dict `__setitem__` that can never raise
   `KeyError`, and three `.pop(channel)` calls above it each get the same
   pointless `try/except KeyError: pass` treatment instead of
   `dict.pop(channel, None)`. Collapsing to a small loop over the three dicts
   plus one bare assignment is both shorter and clearer. Low-medium value,
   very low risk.

8. **Possibly-dead redundant range-end normalization** (`MetaEventFinder.py:278-289`
   vs. `302-309`, inside `find_events`) — a list comprehension already
   normalizes every range's `end` to a concrete positive value; a later
   per-range loop re-checks `end is None or end == 0` and recomputes, a
   condition that (given the earlier normalization, and that merging doesn't
   reintroduce `None`/0) should never fire. Flagged for verification only —
   don't remove without confirming no path can still produce that state
   after merging.

**Explicitly not recommended as a near-term action, despite real
structural value:** further splitting `fit_events` (270 lines) and
`_find_events_single_range` (240 lines) into a per-item helper plus a thin
orchestrating loop, once findings #1-#5 are applied. This is the core
control-flow every event-finder/fitter plugin's runtime behavior depends on
(chunk-boundary carry-over state, iteration/abort semantics) — maximal blast
radius, and the smaller mechanical extractions above capture most of the
readability benefit at much lower risk. Only attempt this larger extraction
with full regression coverage across concrete plugins, as a deliberate,
separate follow-up.

---

# Part 9: `MetaDatabaseLoader` / `MetaDatabaseWriter`

Read-only audit (2026-08) of the two SQLite-wrapping data-plugin contract
base classes. `MetaDatabaseLoader.py` is the single largest file in the
core (non-plugin) codebase (~1100 lines).

**Security note, checked specifically and reported separately per the
audit's own instructions — no new issue found:** query-building in both
files splices caller-supplied `conditions: str` directly into f-string SQL
(`MetaDatabaseLoader.py:503,825-834,993-996`), validated afterward via an
abstract `validate_filter_query` hook; column/table *names* used in the same
queries are schema-derived (via `get_table_by_column`/`get_column_names_by_table`),
not raw user text. `alter_database(queries: List[str])`
(`:257-267`) is explicitly documented as an intentional, unvalidated raw-SQL
escape hatch. `get_experiment_id_by_name` (`:392-406`) hand-escapes a string
literal (`.replace("'", "''")`) rather than using a parameterized query —
correct SQLite escaping today, but fragile next to code elsewhere in the
same file that interpolates raw ints; worth simplifying only if the
underlying query layer is ever extended to support bound parameters. Given
this is a single-user local-file desktop app that already exposes
unrestricted raw SQL by design via `alter_database`, this is a design
characteristic, not a newly-introduced hole — flagged for visibility, not
urgency.

1. **An identical `tuple_builder` nested function is defined 3 times**
   (`MetaDatabaseLoader.py:458-466,695-703,958-966`), and `_qualify_conditions_for_events_sublevels_join`
   is nested inside `construct_metadata_query` (`:706-730`) — both violating
   this project's "no nested functions" convention, with the added risk that
   fixing one of the three `tuple_builder` copies and not the other two is
   an easy mistake to make. `MetaDatabaseWriter.write_events` has its own
   nested `lookahead_generator` (`MetaDatabaseWriter.py:120-132`) — the same
   pattern flagged independently in `MetaWriter._commit_events` (Part 7,
   finding #1). Hoist all of these to private methods or a module-level
   helper (e.g. `_build_id_tuple`, `_iter_with_lookahead`). Low risk, decent
   value — pure refactor, brings the file into line with stated convention.

2. **`construct_metadata_query`** (`:647-939`, ~290 lines) is the most
   tangled method in the file: its tail (`:845-932`) is a 6-branch if/elif
   chain hand-writing near-duplicate SQL for every combination of
   `{events, sublevels, experiments columns} × {forced join}`, and the
   method as a whole mixes column-to-table resolution, redundant-column
   filtering against a hardcoded set that must stay in sync with the SELECT
   clauses below it (an unenforced implicit invariant), forced-join
   detection via regex over raw condition text, and regex-based column
   qualification — five concerns in one method. The same OR-of-AND
   experiment/channel clause pattern also appears near-verbatim in
   `construct_event_data_query` (`:988-1000`) and `export_subset_to_csv`
   (`:487-497`) and is worth collapsing at the same time. Highest value in
   the file, but also highest blast radius — this exact SQL shape is almost
   certainly exercised by concrete loader plugins and possibly tests
   asserting particular query strings/column order. Only attempt with strong
   test coverage in place first, not as a quick pass.

3. **`MetaDatabaseWriter.write_events`** (`:105-230`) carries five
   responsibilities sequentially (DB init, experiment metadata write,
   channel metadata write, a precondition check, then the main per-event
   loop), with the three setup blocks (`:134-162`) copy-pasting the same
   try/except-plus-`close_resources` scaffolding. A minor dead-code note:
   `index = 0` at line 170 is immediately superseded by `index = 1` at line
   184 before ever being read. Extracting `_setup_write(channel)` for the
   three setup blocks, and deleting the dead assignment, is medium value,
   low-to-medium risk (behavior-preserving if the same exception/
   `close_resources` sequencing is kept per block).

4. **`export_subset_to_csv`** (`:434-597`) repeats the identical 4-step
   "build query → validate → raise-with-debug-msg-on-failure → load →
   raise-if-None" pattern 5 times (`:503-566`) for events/sublevels/
   experiments/channels/data queries, differing only in the query string and
   error text. A `_run_validated_query(query, empty_error_msg) -> pd.DataFrame`
   helper shrinks ~65 lines to ~15. Good value, low risk — pure mechanical
   deduplication, no behavior change, a leaf function rather than pattern-
   matching logic like #2.

5. **`_qualify_conditions_for_events_sublevels_join`** (`:706-730`) rewrites
   user-supplied condition text via a length-sorted, word-boundary regex
   substitution to inject table aliases in front of bare column references —
   clever but fragile, since it has no awareness of SQL string-literal or
   identifier context (e.g. a condition like `label = 'sublevel_duration'`
   could misfire). Document the limitation clearly at minimum; a real fix
   would need an actual (even minimal) SQL tokenizer rather than blind regex
   substitution over the whole string. Medium value as a robustness note,
   risky to change without a concrete bug driving it — recommend documenting
   now, deferring an actual fix until one surfaces.

**Not flagged** (reviewed, judged acceptable): `report_channel_status` in
both files, `get_experiment_id_by_name`/`get_channel_db_id`, the abstract-
method docstring blocks (intentionally long/detailed — the documented
plugin contract, not a complexity problem), and `construct_event_data_query`'s
use of `.format()` instead of an f-string (style inconsistency only).

---

# Part 10: `main_view.py` / `settings_window.py` / `help.py`

Read-only audit (2026-08) of the app's top-level shell UI — main window,
settings window, help/about view — not any analysis-tab plugin view.

1. **`MainView.switch_to_page`** (`main_view.py:697-758`) blends walkthrough
   gating, milestone-dialog gating *and* its cleanup (two inline nested
   `try/except` blocks), and the actual page switch, nesting 3-4 levels
   deep. The milestone-cleanup block (`:723-747`) also duplicates teardown
   logic already implemented once in `clear_milestone_dialog` (`:904-925`).
   Extracting `_walkthrough_blocks_switch(page_name)` and
   `_milestone_blocks_switch(page_name)` as early-return guards, and routing
   the cleanup through the existing `clear_milestone_dialog` instead of
   duplicating it, is high value (the file's most tangled method, and
   removes a real duplication) and low risk (mechanical, behavior-preserving).

2. **`MainView.connect_signals`** (`:197-240`) has an `isinstance(page, str)`
   branch inside its wiring loop that is **always dead** — every `page`
   value in `page_switch_signals` is a bound method, never a string.
   Deleting the branch (and always doing `getattr(widget, signal).connect(page)`)
   is high value (removes genuinely misleading dead code implying a
   supported input that doesn't exist) and essentially zero risk.

3. **Menu construction is 9 near-identical blocks plus 8 near-identical
   handler methods** (`main_view.py:336-408,455-481,601-607`) —
   `setup_menubar` repeats `submenu = X.addMenu(name); self.add_plugin_actions(submenu,
   "MetaY", self.on_load_Y_button_click)` nine times, and each `on_load_*_button_click`
   handler is a 1-3 line wrapper differing only by plugin-type string. A
   small `[(parent_menu, submenu_title, plugin_type, log_msg), ...]` table
   iterated in a loop, plus one `_on_load_plugin(plugin_type, subclass,
   log_msg=None)` bound per plugin_type via `functools.partial`, cuts ~90
   lines to ~25. Medium-high value (real duplication, easier to add a new
   plugin category later), low risk — purely mechanical, signatures
   unchanged.

4. **`SettingsWindow`'s tab-content builders repeat the same "labeled row +
   divider" pattern ~8 times** (`settings_window.py:559-747`, across
   `add_general_tab_contents`/`add_advanced_settings_tab_contents`/
   `add_about_tab_contents`) — language, data-server, user-plugin, logging-
   level, clear-cache, reset-settings, version-info, developer-info rows all
   hand-build the same shape. A `self._add_settings_row(layout, label_text,
   control_widget)` helper called 8 times instead is medium-high value, low
   risk (pure widget-construction, no logic to preserve).

5. **`SettingsWindow.create_secondary_button`** (`:463-534`) hand-writes two
   ~20-line stylesheet blocks (dark vs. light) differing only in a handful
   of colors, unlike every sibling `create_*` factory in the file which
   parameterizes one f-string. Mirroring the pattern already used in
   `create_push_button` (`:450-453`) is medium value, low risk — makes this
   method consistent with its own siblings.

6. **Logging-level index mapping is two hand-written 6-entry dicts** in
   opposite directions (`:782-806`, in `set_logging_level`/`update_logging_level`)
   that must be kept manually in sync. One ordered `_LOG_LEVELS` list, used
   with `.index(level)`/`[index]`, removes the staleness risk. Low-medium
   value, low risk.

7. **`MainView.get_milestone_step`** (`:980-1011`) wraps
   `self.get_analysis_highlight` in a `lambda: [self.get_analysis_highlight()]`
   that's called synchronously right after being read from the dict and
   immediately unwrapped back down to one element — no deferred-evaluation
   reason for either the lambda or the list. Storing the plain callable (or
   calling it inline) is low-medium value, trivial risk — a genuine "solving
   a simpler problem than the structure suggests" case.

8. **`MainView.populate_plugins_menu`** (`:538-585`) mixes building `QMenu`
   contents with several lines of anchor-relative popup-position arithmetic
   in the same method. Extracting `_show_menu_near_button(menu, button)`
   would separate "what appears" from "where it appears." Low-medium value,
   low risk — lowest priority in this part, worth doing opportunistically
   rather than as dedicated churn.

**Not flagged**: `help.py` in full (long but flat, linear widget
construction, no branching complexity). `MainView`'s walkthrough/milestone
feature state (`_milestone_dialog`, `_expected_next_view`,
`_walkthrough_active`, `_analysis_proxy`, `_walkthrough_origin`, spread
across ~10 methods) is genuinely stateful and would benefit from being a
small dedicated state object — noted as an architectural observation only,
not a recommended action, given the regression risk of touching a guided-
tour feature that's easy to subtly break. `SettingsWindow`'s per-widget
stylesheet strings are already centralized through the `Theme` class with
an explanatory docstring — working as intended.

---

# Part 11: Shared Dialog/Menu Widgets, Group 1

Read-only audit (2026-08) of `poriscope/views/widgets/clustering_settings_widget.py`,
`walkthrough_steps.py`, `icon_menu_widget.py`, `dict_dialog_widget.py`,
`text_menu_widget.py` — shared, reusable widgets used across the app shell
and multiple plugin families.

1. **`dict_dialog_widget.py:362-380` (`on_ok`) uses try/except as type
   dispatch**: three nested `try/except AttributeError` blocks probe whether
   a widget is a checkbox, combobox, or line edit by calling `.isChecked()`,
   then `.currentText()`, then `.text()`, falling through on failure — hiding
   the widget's actual (already-known, at construction time in `init_ui`)
   type behind exception-driven control flow. An `isinstance` dispatch (or
   tracking the widget "kind" alongside it) is high value, low risk.

2. **`clustering_settings_widget.py` has three near-duplicate ~50-line row-
   builder blocks** (`add_column_item_with_values:300-367`,
   `add_column_item:387-454`, `_add_default_row:534-576`) each independently
   building the same combo+unit_label+log_cb+norm_cb+plot_cb(+delete_button)
   row and wiring the same three signal connections. One `_build_column_row(row,
   column="", log=False, norm=False, plot=False, deletable=True)` helper
   used by all three (with `add_column_item` becoming a thin call to
   `add_column_item_with_values`) removes ~100 lines and one source of
   divergence bugs — e.g. `add_column_item_with_values` currently connects
   `_check_apply_enabled` to the combo *before* setting its value, so
   restoring a preselected config fires the check-callback mid-construction,
   easy to miss when copy-pasted three times. Medium-high value, low risk.

3. **Confirmed dead/broken methods that would raise `AttributeError` if
   called**: `clustering_settings_widget.py`'s `update_unit_label`
   (`:376-379`) and `reset_top_inputs` (`:526-532`) reference `self.unit_label`,
   `self.column_combo`, `self.log_cb`, `self.norm_cb`, `self.plot_cb` — none
   of which are ever assigned anywhere in the class (confirmed via grep),
   leftovers from an earlier single-row design predating the current multi-
   row rewrite. Recommend deleting both, after confirming no external caller
   depends on them.

4. **The same dead-code pattern recurs in the menu widgets**:
   `icon_menu_widget.py:390-396` and `text_menu_widget.py:308-317`'s
   `setLanguageChecked`/`setThemeChecked` reference button attributes never
   created in either file's `setupUi`. Same fix — delete, unless a planned
   feature these are stubs for is confirmed with whoever owns the file.

5. **`text_menu_widget.py:206-212` (`menu_button_clicked`)**: a
   `QTimer.singleShot(100, self.uncheckMenuButton)` call is duplicated
   (lines 209 and 211), with a leftover `print("text_menu_button_clicked")`
   sitting next to the proper `self.logger.info(...)` doing the same thing.
   Trivial, zero-risk cleanup.

6. **`dict_dialog_widget.py:105-238` (`init_ui`)** does three jobs at once:
   builds the Name row, loops over `params` dispatching on key/type across 6
   widget kinds, and lays everything into the grid — with the "Input File"
   (`:125-142`) and "Output File" (`:144-161`) branches near-identical,
   differing only in which dialog method (`get_input_file`/`get_output_file`)
   is called. Extracting `_create_entry_widget(key, val) -> QWidget` for the
   dispatch chain, and factoring the Input/Output File duplication into one
   parameterized helper, is medium value; moderate risk since the lambda
   variable-capture (`s=`, `f=`) needs to survive the extraction carefully.

7. **`walkthrough_steps.py`'s `get_global_walkthrough_steps`**
   (`:30-420`) is a single 390-line function returning a flat list of ~40
   tuples spanning 4 tabs, identified only by comments. **Contains a real
   bug**, not just a style issue: lines 257-264 and 265-272 are byte-for-byte
   duplicate tuples (same title "Event Analysis Tab", same "Click 'Commit'..."
   text, same lambda) — one walkthrough step is silently shown twice to
   users. Fix the duplicate outright; separately, splitting the function into
   `_raw_data_steps(pages)`/`_event_analysis_steps(pages)`/
   `_metadata_steps(pages)`/`_clustering_steps(pages)` (concatenated at the
   end) would make one tab's steps findable without scrolling through 400
   unrelated lines. Low risk either way (mostly pure data); the duplicate-
   tuple fix is a genuine bug fix, the split is a navigability improvement.

8. **`icon_menu_widget.py`/`text_menu_widget.py` share extensive structural
   duplication** beyond the dead-code overlap in #4: repeated inline QSS
   blocks (the same `QPushButton:hover/:checked/:pressed` styling appears
   5+ times across the two files), a byte-identical `emitSignal` dispatch-
   dict method in both, and the same `setXChecked` slot pattern — suggesting
   a shared base/mixin would fit. Flagged as lower priority: the two widgets
   are visually/structurally distinct enough (icon-only rail vs. icon+text
   panel) that unifying them is a real, worthwhile refactor but higher
   risk/reward than the others in this part. If pursued, extract just the
   shared QSS constants, `emitSignal`, and the `setXChecked`/signal
   declarations into a small mixin rather than merging the classes outright.

9. **`clustering_settings_widget.py:207-234`** (tail of `init_ui`, the
   preselected-config restore block) wraps ~25 lines of unrelated restore
   logic in one broad `try/except Exception` inside an already-140-line
   method. Extracting `_restore_preselected_config(self)` is low-medium
   value (a naming/separation improvement, not a correctness fix — the broad
   except is arguably fine for "best-effort UI restore" as-is).

**Not flagged**: `_check_apply_enabled` (`:578-617`) branches a fair amount
but uses clean early returns and is checking two different row collections
against the same three rules — a reasonable amount of complexity for what it
does. Long-but-flat widget-construction methods (`createIconButton`,
`createMenuButton`, etc.) are excluded per the audit's own carve-out. The
`if __name__ == "__main__":` demo harness at the bottom of
`clustering_settings_widget.py` (`:669-727`) is unusual in a production
widget file but inert and clearly delimited — not worth churn to remove
unless relocating it to a script/example is independently wanted.

---

# Part 12: Shared Dialog/Menu Widgets, Group 2

Read-only audit (2026-08) of `poriscope/views/widgets/multiselect_filter.py`,
`multiselect.py`, `SelectionTree.py`, `poriscope/views/float_range_line_edit.py`,
`integer_range_line_edit.py`, `poriscope/views/widgets/time_widget.py`,
`poriscope/views/comma_delimited_float_range_edit.py`,
`poriscope/views/widgets/base_widgets/base_subset_filter_dialog.py`,
`poriscope/views/widgets/validators/numeric_validation.py`,
`poriscope/views/widgets/dropdown_selection_widget.py`,
`add_subset_filter_dialog.py`, `edit_subset_filter_dialog.py`.

1. **`multiselect.py`/`multiselect_filter.py` are ~90% duplicate classes**
   — `MultiSelectComboBox` and `MultiSelectFilterComboBox`'s
   `showPopup`/`hidePopup`/`mousePressEvent`/`eventFilter`/`selectAllToggle`/
   `updateSelectAllButton`/`handleItemChanged`/`refreshDisplayText` are
   copy-pasted verbatim or near-verbatim, differing mainly in how an item's
   checked state is read/written. Any bug fix currently has to be applied
   twice (see #3, #4 below). A shared `_BaseMultiSelectComboBox` holding the
   popup/select-all/event-filter machinery, with an overridable hook for the
   item-state accessor, is high value and low risk — the two
   implementations already agree almost line-for-line.

2. **Range-parsing/formatting logic is duplicated *and* subtly
   inconsistent** across `float_range_line_edit.py` (`get_values:98-128`,
   `get_start:141-165`, `get_duration:167-179`), `integer_range_line_edit.py`
   (`get_values:167-196`, `RangeValidator:37-157`),
   `comma_delimited_float_range_edit.py` (`get_values:117-156`), and
   `time_widget.py` (`FloatRangeValidator.validate:18-95`,
   `_parse_ranges:179-196`). Each re-implements "split on `,`, strip, split
   on `-`, parse number(s), handle malformed segments" from scratch, with
   **divergent edge-case handling for what's meant to be the same grammar**
   — e.g. `IntegerRangeLineEdit.get_values` explicitly skips segments
   starting with `-` (`:176-180`); `FloatRangeLineEdit.get_values` has no
   such guard at all. `time_widget.py` derives the same "0-0"/open-ended
   special cases twice within one file (once in the validator, again in
   `_parse_ranges`) with subtly different rules each time (see #6). A shared
   module (e.g. `poriscope/utils/range_parsing.py`) with `split_segments(text)`
   and `parse_range_segment(segment, num_type)` used by all four files is
   high value — this is both the biggest duplication *and* the biggest
   user-facing-inconsistency risk found in this part — but moderate risk to
   refactor, since a decision is needed about which behavior is "correct"
   per case before unifying, not just a mechanical extraction. (Separately
   worth noting: this is a different range grammar than the event-index
   range parsing already promoted onto `MetaView` — per Part 1's headline
   finding, `_parse_event_indices`/`_shift_ranges`/etc. — so this isn't the
   same duplication resurfacing, but it is the second instance of "range-
   list parsing" being reinvented per call site rather than centralized.)

3. **Redundant duplicated if-condition in `handleItemChanged`**
   (`multiselect.py:137-144`, `multiselect_filter.py:176-183`): an inner `if
   item is None or item.checkState() in (Qt.Checked, Qt.Unchecked):` is
   nested inside an identical outer `if`, so it's always true once reached —
   dead conditional obscuring that the signal is unconditionally emitted.
   Deleting the inner `if` is low risk, easy readability win.

4. **Dead/duplicated branches in "select all" button state logic** across
   three files (`multiselect.py:146-173`, `multiselect_filter.py:185-211`,
   `SelectionTree.py:159-186`) — in each, the "none selected" branch and the
   final `else` (partial selection) branch perform the exact same action
   (`setChecked(False)`, `setText("Select All")`), a false 3-way branch where
   two cases coincide. Collapsing to `if all_selected: ... else: ...` (and,
   in `SelectionTree`, folding the `total == 0` case into the same `else`)
   is low risk, modest readability win.

5. **`multiselect_filter.py:299-306` nests a function inside a method**
   (`open_dialog_then_reopen` inside `_handle_internal_edit`), violating this
   project's no-nested-functions convention — a plain closure capturing only
   `self` and `name`, easily hoisted to a private method called via a
   lambda. Low risk, direct convention compliance.

6. **`TimeWidget.FloatRangeValidator.validate`** (`time_widget.py:18-95`,
   ~75 lines) independently re-derives the same "0-0"/open-ended special
   cases that `_parse_ranges` (`:179-196`) also encodes, **with a real
   divergence**: `_parse_ranges` treats `start > end and end == 0.0` as
   open-ended, while `validate` treats `end == 0.0` alone (regardless of
   `start`) as valid/open-ended — two independent encodings of the same
   domain rule in the same file, which is a correctness risk on top of the
   readability one. A shared `_classify_segment(start_str, end_str)` helper
   used by both is medium value, low-to-moderate risk, localized to one file.

7. **Convoluted decimal-place computation in `float_range_line_edit.py`'s
   `set_range`** (`:181-204`): `len(str(round(x, 10)).rstrip("0").split(".")[-1])
   if "." in str(round(x, 10)) else 0`, done twice (once per value) inside
   `max()` calls, to answer "how many significant decimal digits does this
   float have." A small `_decimal_places(x: float) -> int` helper is low-
   medium value, low risk (one-value-in/one-value-out, easy to verify).

8. **Platform-conditional popup construction repeated** between
   `multiselect.py:60-77` and `SelectionTree.py:212-218` — both independently
   branch on `sys.platform == "linux"` for the same "popup-style dialog"
   window-flag/stylesheet workaround (and `multiselect.py`'s version does it
   as two separate `if` statements rather than one `if/else`). A shared
   `make_popup_container(title=None)` helper is low-medium value, low risk —
   cosmetic/structural only.

**Not flagged**: `BaseSubsetFilterDialog`/`AddSubsetFilterDialog`/
`EditSubsetFilterDialog` are already well-factored (a shared base doing
exactly what's needed). `dropdown_selection_widget.py` and
`numeric_validation.py` are short, single-purpose, not overly clever. The
`BaseValidator`/`BaseLineEdit` template-method design itself is reasonable —
the concrete validators (`RangeValidator`, `FloatRangeValidator`) just don't
fully exploit it, per #2/#6 above; the base classes aren't the problem.

---

# Cross-Cutting Themes Across Parts 5-12

Nine independent audits (Part 4 plus Parts 5-12) converged on the same
handful of patterns across otherwise-unrelated files, which suggests these
are real accumulated stylistic drift rather than isolated one-offs.

**Correctness issues surfaced incidentally** (not the goal of a
simplification audit, but worth acting on regardless of any broader
refactor decision): `BaseDataPlugin.apply_settings`'s exception-swallowing
type dispatch (Part 6 #1); `MainController.handle_global_signal`'s
`TypeError`-retry masking real callee bugs (Part 5 #3); the confirmed dead/
broken widget methods that would raise `AttributeError` if ever called
(Part 11 #3-#4); the duplicate walkthrough-step tuple that doubles one
guided-tour step (Part 11 #7); the possible premature
`eventfinding_finished` flag (Part 8 #3, unconfirmed); and the divergent
range-parsing edge-case handling across 4 widget files, which is a user-
facing inconsistency as much as a duplication problem (Part 12 #2, #6).

**The dominant theme by volume: repeated boilerplate blocks inside single
methods/files.** Nearly every part found this, and it's almost always a
low-risk, mechanical extraction: `DataPluginController.edit_plugin`/
`validate_and_instantiate_plugin` (Part 5 #1-#2); `MetaController`'s
near-duplicate relay methods (Part 6 #2); `MetaEventFitter.fit_events`'s
9x-repeated reject/pop/continue (Part 8 #1); `MetaDatabaseLoader.export_subset_to_csv`'s
5x-repeated query pattern and `construct_metadata_query`'s 6-branch
hand-unrolled dispatch (Part 9 #2, #4); `MainView`'s 9 near-identical menu
blocks (Part 10 #3); `SettingsWindow`'s ~8x-repeated row pattern (Part 10
#4); `clustering_settings_widget.py`'s three near-duplicate row-builders
(Part 11 #2); and `MultiSelectComboBox`/`MultiSelectFilterComboBox`'s
~90%-duplicate classes (Part 12 #1).

**Recurring pattern: nested functions, several of which are also duplicated
copies of each other** — violating this project's own stated convention.
`MetaWriter._commit_events`'s `lookahead_generator` (Part 7 #1),
`MetaDatabaseWriter.write_events`'s near-identically-named `lookahead_generator`
(Part 9 #1), `MetaDatabaseLoader`'s `tuple_builder` copy-pasted 3 times plus
`_qualify_conditions_for_events_sublevels_join` (Part 9 #1, #5), and
`multiselect_filter.py`'s `open_dialog_then_reopen` (Part 12 #5). Hoisting
these fixes a convention violation and a duplication finding simultaneously.

**Recurring pattern: exception-driven dispatch used where an explicit check
would be clearer.** Two are correctness-relevant (`BaseDataPlugin.apply_settings`,
`MainController.handle_global_signal`, both above); the rest are pure
clarity issues: `MetaReader._get_file_index`'s `try/except IndexError` as
loop termination (Part 7 #3), `dict_dialog_widget.on_ok`'s three chained
`try/except AttributeError` calls as type dispatch (Part 11 #1), and
`EventWorker`'s `send`/`next` dispatch via catching `TypeError` (Part 4 #6).

**The riskiest "god methods" — worth a dedicated pass with test coverage in
place first, not a quick edit:** `MetaDatabaseLoader.construct_metadata_query`
(Part 9 #2) and `DataPluginController.edit_plugin` (Part 5 #1) top the list;
`MetaEventFitter.fit_events`/`MetaEventFinder._find_events_single_range`
were explicitly *not* recommended for this kind of larger restructuring
despite their size, since chunk-boundary/abort-state control flow there is
genuine domain complexity with maximal blast radius (Part 8, closing note).

**Deliberately not flagged, consistent with "efficiency within reason":**
the chunk-boundary/padding stitching logic in `MetaEventFinder`/
`MetaEventFitter`; `MetaWriter._rescale_data_to_adc`'s branchy-but-clearly-
labeled numerical cases; `MetaReader`'s channel/buffer bookkeeping; the bulk
of Qt widget-construction code that's merely long-but-flat rather than
actually complex; and the duplicated `QObjectABCMeta`/`QWidgetABCMeta` pair,
which was explicitly recommended to leave alone given the blast radius of
touching either of the two most foundational, most widely-inherited types
in the whole plugin system, for a 9-line saving.

## Value and wisdom

Sequence this as: the zero-risk dead-code deletions and the correctness
issues first (cheap, and several are worth fixing regardless of any broader
refactor); then the numerous but individually low-risk mechanical
duplicated-block extractions; and only then, separately, with real test
coverage staged first, the large god-methods
(`construct_metadata_query`, `edit_plugin`) and the range-parsing
consolidation (which needs a decision about which widget's edge-case
behavior is "correct" before it can be unified, not just extracted).
