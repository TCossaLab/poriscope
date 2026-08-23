# Future Refactor: Promote Duplicated Frontend Plugin Code into Base Classes

Context block for a dedicated future session. This file is separate from
`future_fixes.md` on purpose: `future_fixes.md` tracks QA/tooling work (type
annotations, compliance-gate infrastructure for community contributions);
this file tracks actual *refactoring* of existing code — restructuring what
already works, not adding new checks. Keep that distinction when adding to
either file in the future.

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

Fix the correctness issues (call-order reversal, arg-shape inconsistency,
dead `_factors` duplication) independently, whenever convenient — they don't
depend on, and shouldn't wait for, any of the above.
