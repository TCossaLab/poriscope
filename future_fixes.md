# Future Fix: Full Codebase Type-Annotation Pass

Context block for a dedicated future session. Paste/point Claude Code at this file to
resume this work; it is written to be self-contained. Choices made along the way -
particularly things deliberately *not* done - are recorded in `DECISIONS.md` rather
than here.

## Status

| Step | Scope | State |
| --- | --- | --- |
| 1 | `poriscope/utils/` - the 13 `Meta*`/`BaseDataPlugin`/`LogDecorator` files | Done 2026-08-23 |
| 2 | `analysistabs/` - 5 tab triads, `*controls.py`, `walkthrough*` (22 files) | Done 2026-08-24 |
| 3 | `main_*.py`, `DataPlugin*.py`, `settings_window.py`, `help.py`, `views/widgets/*` | Done 2026-08-24 |
| 3b | Fix pass over the defects step 3 surfaced (list below) | **Next** |
| 4 | Docstring-text cleanup (`DOC105`) in the files step 1 typed | Queued |
| 5 | Decide on `NanoTrees.py`/`Basic_PeakFinder.py`/`PeakFinder.py` (see Exclusions) | Queued |
| 6 | Scope the pre-commit `mypy` hook so it stops checking `tests/` as explicit paths | Queued - blocks step 7 |
| 7 | Flip `disallow_untyped_defs`/`check_untyped_defs`, confirm gates clean, update `CLAUDE.md` | Blocked on 3-6 |

The pydoclint half of what used to be step 7 is **done** (2026-08-24).
`arg-type-hints-in-signature` is now `true` and the baseline was regenerated fresh:
709 entries down to 216, `DOC108` eliminated. It was split out of step 7 because it was
never actually blocked - step 6's problem is that the pre-commit `mypy` hook passes
explicit test paths, and the pydoclint hook is already scoped `files: ^poriscope/`.
`mypy`'s `strict_equality` was turned on at the same time (measured: zero new errors).

Consequence for the remaining batches: a batch now *removes* `DOC106`/`DOC107` lines
from the baseline instead of adding `DOC108` lines to it. Regenerate the baseline at the
end of each batch as before; the count should only ever go down.

Steps 1 and 2 are summarised in `changelog.md` (the two "Type annotations for ..."
entries) and recorded in detail by the `feat(types):` and `fix:` commits on
`feature/loadbearing_docstrings`. That narrative is deliberately not repeated here.

Both completed steps finished with: every parameter and return annotated (checked by an
AST scan, not by eye), zero `DOC104`-`DOC107` under
`pydoclint --arg-type-hints-in-signature=True`, no `# type: ignore` left behind, and a
green `pytest -m "not e2e and not slow"` plus `test_plugin_compliance.py`. Use the same
bar for step 3.

### Step 3 - measured scope and batch plan (2026-08-24, re-measured)

**369 functions across 39 files** have at least one unannotated parameter or return,
once `NanoTrees.py` (45), `PeakFinder.py` (13) and `Basic_PeakFinder.py` (12) are set
aside per the Exclusions section. (An earlier note said 439 across 42 files; that figure
counted those three excluded plugins.)

Re-measure at any time with `scratchpad/check_hints.py`, or the equivalent AST walk over
`poriscope/` - do not trust the numbers below once work has started.

Planned as one family per commit, smallest and most self-contained first:

| # | Batch | Files | Fns |
| --- | --- | --- | --- |
| 1 | Leftovers from steps 1-2 - **done** | `utils/{QObjectABCMeta,QWidgetABCMeta,QtHandler,EventWorker,DocstringDecorator,JsonDefaultSerializer,MetaDatabaseWriter}`, `plugins/{SQLiteEventWriter,BesselFilter,WaveletFilter,SQLiteEventLoader}`, `plugins/datareaders/helpers/ABF2Header.py` | 37 |
| 2 | Line-edit / validator family | `views/{comma_delimited_float_range_edit,float_range_line_edit,integer_range_line_edit}`, `utils/{BaseLineEdit,BaseValidator}`, `views/widgets/validators/numeric_validation` | 44 |
| 3 | `views/widgets` menus | `icon_menu_widget` (30), `text_menu_widget` (18), `dropdown_selection_widget` (5) | 53 |
| 4 | `views/widgets` dialogs | `clustering_settings_widget` (20), `dict_dialog_widget` (10), the three subset-filter dialogs, `walkthrough_steps` | 39 |
| 5 | `views/widgets` remaining | `multiselect_filter` (16), `multiselect` (13), `time_widget` (8), `SelectionTree` (5) | 42 |
| 6 | Settings + help | `views/settings_window.py` (28), `views/help.py` (7) | 35 |
| 7 | Data-plugin management | `controllers/DataPluginController.py` (7), `models/DataPluginModel.py` (4) | 11 |
| 8 | App shell, non-view | `main_app.py` (5), `models/main_model.py` (19), `controllers/main_controller.py` (19) | 43 |
| 9 | `views/main_view.py` | on its own - the largest single file | 65 |

The per-batch counts above are the plan's original estimates and have drifted; batch 1
measured 37, not 51. Re-measure before starting each batch.

Batch 1 exists because steps 1 and 2 left small gaps in areas they reported complete:
`MetaDatabaseWriter.lookahead_generator`, both `Qt*ABCMeta` metaclasses, `QtHandler`,
`EventWorker`, and a `get_empty_settings: standalone` / `_finalize_initialization: ->
None` pair repeated across four data plugins. Worth clearing first so the completed-step
claims are actually true.

## Step 3b - defects surfaced by step 3, to fix in a follow-up pass

Step 3 was annotations and docstrings only; everything below needs a logic, signature or
API change and was deliberately left alone. Nothing here is a regression - these are
pre-existing defects that became visible once mypy could see the bodies concerned.

### A. An attribute shadows an inherited Qt method (5 sites) - DONE (7e374db)

Each of these assigns an instance attribute over the name of a method the Qt base class
already defines, so the inherited method becomes unreachable on that instance.

| Class | Attribute | Shadows |
| --- | --- | --- |
| `NumericLineEdit` (`validators/numeric_validation.py`) | `self.validator` | `QLineEdit.validator()` |
| `DropdownDialog` (`dropdown_selection_widget.py`) | `self.result` | `QDialog.result()` |
| `DictDialog` (`dict_dialog_widget.py`) | `self.result` | `QDialog.result()` |
| `TimeWidget` (`time_widget.py`) | `self.result` | `QDialog.result()` |
| `BaseSubsetFilterDialog` (`base_widgets/base_subset_filter_dialog.py`) | `self.layout` | `QWidget.layout()` |

Renaming is the fix; it is an API change for anything that reads these attributes.

### B. Methods that reference attributes which are never created - PARTLY DONE

Both would raise `AttributeError` on first call. Neither has a caller anywhere in
`poriscope/`, which is the only reason they have never been noticed.

- ~~`setLanguageChecked` / `setThemeChecked` in the two menu widgets~~ - **done**,
  removed along with `handleLanguage` / `handleTheme`; there is no language or theme
  control anywhere in the UI. `handleUser` and the `switchUser` signal in both widgets
  are also unreached, but they are merely unused rather than broken (nothing connects
  to `switchUser`, and `handleUser` references no missing attribute), so they are left
  for a decision rather than deleted.
- `ClusteringSettingsDialog.update_unit_label` and `reset_top_inputs` reference
  `unit_label`, `column_combo`, `log_cb`, `norm_cb` and `plot_cb`, none of which is
  assigned anywhere in the class.

### C. Qt accessors that return `Optional`, used without a guard - RESOLVED (6cf1602)

- ~~`self.lineEdit()` in `multiselect.py` and `multiselect_filter.py`~~ - **done**. It
  returns `None` unless the combo is editable; now bound once as `self._line_edit`
  immediately after `setEditable(True)`, where that guarantee is established.
- `QApplication.instance()` in `BaseLineEdit.__init__` and `multiselect.py`: **no action
  needed**. Both sit in a `QWidget.__init__`, and a `QWidget` cannot be constructed
  before a `QApplication` exists, so `None` is unreachable.
- `item.child(i)` / `topLevelItem(i)` in `SelectionTree.py`: **no action needed**. Every
  site is inside `for j in range(...childCount())`, so the index is always valid; this is
  mypy failing to connect `range(n)` with "valid index", not a defect.

### D. Override signature mismatches

- `MultiSelectComboBox.addItem` and `MultiSelectFilterComboBox.addItem` do not implement
  `QComboBox.addItem`'s icon overload.
- `MainView.show_walkthrough_intro()` takes no argument where
  `WalkthroughMixin.show_walkthrough_intro(current_view: str)` takes one. Latent: every
  `MainView` call site passes nothing, but a mixin-level caller would `TypeError`.

### E. Mutable default arguments

- `DictDialog.__init__(source_plugins=[])`
- `MainModel.replace_class_names_with_classes(class_dict={...})` - read-only in practice.

Both are `B006` hits; see the bugbear/bandit item below.

### F. A parameter that is accepted and silently discarded

`addItem(text, userData=None)` in both multi-select widgets accepts `userData` for
`QComboBox` signature compatibility and never stores it.

### G. Types that are inconsistent across the codebase

- **`MetaModel.generators`** is declared `Dict[str, Dict[int, Generator]]`. A bare
  `Generator` reads as `Generator[Any, None, None]`, but the real contract is
  `Generator[float, Optional[bool], None]`. **Now actionable**: this was previously
  blocked because the five producers disagreed - `_commit_events` was mis-annotated and
  `export_subset_to_csv` genuinely ignored the sent value. Both were fixed in `6cf1602`,
  so all five now share one contract and the storage type can be tightened. Doing so
  touches `set_generator` on both `MetaModel` and `MetaController`.
- ~~**`app_config` path values**~~ - **done** (`6cf1602`). Coerced to `str` at both
  points where they enter the dict, so `get_data_server_location` and
  `get_user_plugin_location` now declare `-> str` honestly. The dangerous branch was the
  upgrade path, which assigns a `Path` into an otherwise all-`str` loaded config and
  never re-reads it; that value pre-populates a Folder setting, which
  `BaseDataPlugin._validate_param_types` rejects unless `isinstance(value, str)`.
- **`DictDialog.result`** holds three shapes: `(params, name)`, `(None, None)`, and the
  sentinel string `"delete"`.
- **`get_values`** returns `List[float]` on `FloatRangeLineEdit` but
  `List[Tuple[Optional[float], Optional[float]]]` on `CommaFloatRangeLineEdit`.
- Two unrelated classes are both named **`FloatRangeValidator`**, in
  `float_range_line_edit.py` and `time_widget.py`.

### H. Lazy imports to hoist to module level

Standing preference: imports belong at module level. All four of these are removable.

| Location | Import |
| --- | --- |
| `main_view.py:453` (`on_help_button_click`) | `from poriscope.views.help import HelpCentre` |
| `MetadataView.py:2136, 2270` | `import bisect` |
| `settings_window.py:844` (`main`) | `import sys` |

Hoisting the `HelpCentre` one also removes the `TYPE_CHECKING` block in `main_view.py`
that exists only to make its annotation resolve. The `TYPE_CHECKING` block in
`main_controller.py` can likewise become plain imports - verified by importing
`main_model`, `main_view` and `main_controller` together with no cycle. The
`TYPE_CHECKING` blocks in `icon_menu_widget.py` and `text_menu_widget.py` **must stay**:
`main_view.py` imports both widgets, so importing `MainView` back would cycle. Both now
carry a comment saying so.

### I. Dead or unreachable code

- `CommaFloatRangeLineEdit` has no callers anywhere in `poriscope/`.
- `get_values_with_type_info` has no callers on either line-edit class.
- `IconMenuWidget.createIconButton`'s `isinstance(iconPathOff, tuple)` branch is
  unreachable - every call site passes an `os.path.join` result.
- In `text_menu_widget.py`, `emitSignal`'s `"menu"` entry is unreachable (no
  `createTextButton` passes that objectName) and would emit a `bool` on
  `menuToggled = Signal()`, which declares no arguments.
- A stray `print("text_menu_button_clicked")` sits in
  `IconTextMenuWidget.menu_button_clicked`, alongside the equivalent `logger.info`.

### J. Aborting any operation is invisible to the user

Surfaced while making CSV export abortable. `MetaController.handle_kill_worker` and
`handle_kill_all_workers` only call `self.logger`; nothing reaches the message panel, so
a user whose log level is above INFO sees no confirmation that a stop took effect - for
any operation, not just export.

Note that a **data plugin cannot emit to the panel directly**: `BaseDataPlugin` is a
plain `ABC`, not a `QObject`, and has no signals. The established route is to return a
string from `report_channel_status()`, which `MetaModel.generate_report` relays to
`relay_add_text_to_display` when a worker finishes. `add_text_to_display` itself exists
only on `MetaController`/`MetaModel`/`MetaView`.

Two options: emit from `handle_kill_worker`/`handle_kill_all_workers`, which fixes every
operation at one site; or have `MetaDatabaseLoader.report_channel_status` mention the
abort, which fixes export alone but can add the "files already written are left in
place" detail only the loader knows.

### Step 6 - why it blocks the flip

The pre-commit `mypy` hook passes explicit file paths, test files included, which
bypasses `mypy.ini`'s `exclude = ^tests/` entirely - `exclude` applies to directory
discovery, not to explicitly listed files. Without scoping the hook itself, flipping
`disallow_untyped_defs` looks clean under `mypy poriscope` and then breaks every real
commit. (That hook also cannot see third-party types at all; `DECISIONS.md` records why
closing *that* gap is judged not worth doing, and why it does not block the flip.)

## Also queued - found during this pass, not part of it

- **Adopt ruff `bugbear` (B) and `bandit` (S).** Proposed in review on the grounds that
  both run against real code logic and so complement pydoclint's docstring/signature
  checking for catching silent bugs. Measured on `poriscope/` (2026-08-24): **B = 106,
  S = 40**.

  | Rule | Hits | Character |
  | --- | --- | --- |
  | `B905` zip-without-explicit-strict | 56 | real silent-truncation class; each site needs a `strict=` decision |
  | `B904` raise-without-from-inside-except | 23 | loses the exception chain; mechanical but touches `raise` statements |
  | `B007` unused-loop-control-variable | 19 | mostly cosmetic |
  | `B006` mutable-argument-default | 4 | near-certain bug |
  | `B010`/`B028`/`B020` | 4 | cosmetic, except `B020` (1) which is a real shadowing bug |
  | `S608` hardcoded-sql-expression | 25 | worth real scrutiny - user-entered subset filters feed `_build_where_clause` |
  | `S101` assert | 8 | asserts in non-test code |
  | `S110` try-except-pass | 7 | silently swallowed exceptions in a GUI app |

  **Keep this out of the type-annotation pass.** Almost every fix above is a logic
  change, and that pass is deliberately hints-and-docstrings only. Suggested order when
  it is picked up: `B006` + `B020` first (5 near-certain bugs), then `S608`, then
  `S110`; enable the rules only once the backlog they gate is small enough not to need
  its own baseline.

  Note this overlaps, but is not the same as, the bandit proposal in the
  community-plugin block below: that one is scoped to `poriscope/plugins/` as a trust
  boundary for unvetted contributions, this one is codebase-wide as a bug-catcher.

- **`hist_data` holds three shapes.** In both `MetadataView` and `ProteinView` it
  receives 1-D arrays from the histogram path, whole DataFrames from the density path,
  and `(x, y)` tuples from the all-points path. Widened to `List[Any]` with a comment;
  unifying it is a real refactor.

## Goal

Add type hints to every parameter (and return type) of every function/method across
`poriscope/` so the codebase can adopt a strict, signature-based typing policy end to
end, instead of the current partial/legacy state.

## Why this matters (background)

Two config knobs currently tolerate untyped code, and they interact:

- `mypy.ini`: `disallow_untyped_defs = False`, `check_untyped_defs = False` — mypy
  does not require annotations on plugin methods, and (more importantly) does not even
  type-check the *body* of a function that has zero annotations.
- `pyproject.toml` `[tool.pydoclint]`: `arg-type-hints-in-signature = false` — pydoclint
  expects type info to live in the docstring, not the signature, and its `DOC108`
  check exists specifically to flag functions that *do* have signature type hints
  under this policy (see `pydoclint/utils/violation.py` and `visitor.py:608-622` in the
  installed package for the exact trigger condition).

As of the `feature/loadbearing_docstrings` branch's pydoclint baseline cleanup
(`.pydoclint-baseline.txt`, ~430 remaining lines), the residual backlog is almost
entirely `DOC108` — i.e. functions that already happen to carry signature type hints,
which is a "policy nag," not a real defect. There is no way to clear these for real
(short of stripping existing hints back out, which would be regressive) other than
flipping `arg-type-hints-in-signature` to `true`. That flip is the actual goal of this
future pass; this file exists because flipping it is not a small edit — see Scope below.

## What flipping the policy actually requires

`pydoclint/visitor.py` only checks a function at all if it has a non-empty docstring
(functions with zero docstring are skipped entirely — "we don't check functions
without docstrings"). But for every function that *does* have a docstring, once
`arg-type-hints-in-signature = true`:

- `DOC106` fires if a documented, parameterized function has **no** signature type
  hints at all.
- `DOC107` fires if it has **some but not all** parameters hinted.

So in practice this pass means adding type hints to essentially every parameter of
every documented function in `poriscope/` (not just the ~430 currently-flagged spots).
Once that's done, `mypy.ini`'s `check_untyped_defs = False` / `disallow_untyped_defs =
False` leniency has nothing left to exempt and becomes a no-op — it can be safely
flipped to `True` (or removed) at that point, verified by the fact that the test suite
and `pre-commit run --all-files` still pass identically before and after the flip.

## Method (lessons carried over from the pydoclint baseline cleanup)

This mirrors the process that worked well for the docstring/baseline cleanup on
`feature/loadbearing_docstrings`:

- Pure type-hint additions (no behavior change) can proceed automatically; anything
  that looks like it would change runtime behavior should pause for a check-in.
- Work file-by-file, or hand independent file groups to parallel subagents
  (`Agent` tool, `general-purpose` type, one self-contained prompt per group) — this
  scaled well last time across ~60 files.
- Commit in small batches (e.g. every 5 files) so a rollback is cheap if a batch turns
  out to have a subtle issue.
- Update `changelog.md` as you go, but keep entries terse — a "New Dev Tooling"-style
  consolidated summary at the end is more useful to other developers than a per-file
  violation list (see the `## Poriscope 1.7` section for the pattern used last time).
- **Write each file's edits as a `rep(old, new)` script, and dry-run it.** Put the
  script in a scratchpad, run it once with writes stubbed out so every anchor string is
  proven to match exactly once, then apply. An anchor that fails the dry run almost
  always means the docstring differs from what you assumed, which is worth discovering
  before touching the file. This scaled cleanly across 22 files in step 2.
- Prepare the next file's script while the current test run is in flight; the suite is
  the long pole, not the editing.

## Known gotchas to expect (all hit during the pydoclint pass; will likely recur)

- **mypy "annotation-unchecked" cascade**: a function with zero annotations is
  currently invisible to mypy's body-checking (`check_untyped_defs = False`). Adding
  *any* annotation to it (even just a return type) flips it to "checked," which can
  surface pre-existing, previously-invisible type errors unrelated to the annotation
  you just added. Fix patterns established last time:
  - If the error is `self.attr = None` being inferred as a `None`-only type, add a
    proper `Optional[X]` annotation at that attribute's first assignment — this is a
    pure type-hint fix, safe to apply on sight.
  - If it's a genuine logic-shaped mismatch, flag it for human review rather than
    fixing blindly — unless it's provably behavior-neutral (e.g. a `cast()` where the
    real runtime type is already guaranteed by surrounding code, as was needed once in
    `MetaReader.load_data`).
- **`test_plugin_compliance.py` exact-equality trap**: its `_return_type_compatible` /
  `_param_type_compatible` checks do not understand real generic covariance — for
  non-"classlike" (generic alias) annotations it falls back to exact equality between
  a `Meta*` base method's annotation and every subclass override's annotation. Widening
  or correcting an abstract method's annotation to satisfy mypy will break this test
  for every subclass whose override doesn't match exactly, and all of them need to be
  updated to match. Run
  `pytest tests/unit/plugins/test_plugin_compliance.py` after touching any `Meta*`
  base signature.
- **Baseline file race condition**: if multiple concurrent agents/processes run
  `pydoclint --baseline=.pydoclint-baseline.txt` with auto-regeneration on narrow file
  subsets, they can corrupt or prune unrelated entries from the shared baseline. Use
  `--auto-regenerate-baseline=False` for read-only checks during the pass, and only do
  one authoritative full-tree `--generate-baseline=True` regeneration once all edits
  for a batch are complete.
- **pydoclint folds trailing prose into the last `:type:`.** A docstring written
  "params first, description last" reports a spurious `DOC105` against whichever
  parameter happens to be documented last. Put the description first. Nine docstrings
  hit this in step 2.
- **Recurring defect classes**, all surfaced by adding hints rather than by reading:
  - *Callback-shape annotations.* `relay_*`-style methods are `global_signal` return
    callbacks, so the parameter type is whatever the *called* `Meta*` method returns -
    usually `Optional[str]` - not the `dict` the parameter name suggests. Nine were
    wrong across three controllers.
  - *Off-by-one nesting.* `get_plot_features` returns one flat list per event; three
    call sites declared list-of-lists.
  - *Channel stringification.* The selection tree hands back display strings while the
    domain type is `int`. Convert once at the derivation site, not at each consumer, or
    cache-staleness comparisons silently compare `str` to `int` and always differ. The
    `exp_and_ch` dicts passed to loader plugins stay strings deliberately -
    `tuple_builder` stringifies them unquoted either way.
  - *Attributes first assigned `None`* need an explicit `Optional[...]` at the
    declaration, or mypy infers `None` and rejects every later assignment.
- **Two gates, blind in different directions.** `pre-commit run mypy --all-files` is
  what blocks a commit and matches CI, but it runs in an isolated venv with no project
  dependencies, so every PySide6/numpy/pandas type is `Any` to it. The project venv's
  `mypy poriscope` sees real types but is a different version and is not the gate.
  Neither alone is sufficient; see `DECISIONS.md`.
- **Never pass test paths in a hand-picked order.** Pytest runs explicitly listed paths
  in the order given, so `pytest tests/unit/views tests/unit/plugins` inverts natural
  collection order and reliably segfaults the interpreter. Let pytest collect naturally,
  or list paths alphabetically. Relatedly, never pipe a test run through `tail`/`grep`
  as its only record: a faulthandler dump names the crashing test at the *top* of its
  output, which is exactly what a tail discards.

## Exclusions (standing project policy — do not spend effort here)

- `NanoTrees.py` — likely to be deprecated soon.
- `Basic_PeakFinder.py` / `PeakFinder.py` — owned by another developer.

## Verification checklist before considering this pass done

- `pre-commit run --all-files` clean (ruff + mypy + pydoclint).
- `pytest -m "not e2e and not slow"` clean (matches CI).
- `pytest tests/unit/plugins/test_plugin_compliance.py` clean.
- `pydoclint --baseline=.pydoclint-baseline.txt poriscope` clean with
  `arg-type-hints-in-signature = true`, baseline regenerated fresh from a clean tree.
- `mypy poriscope` clean with `disallow_untyped_defs = True` /
  `check_untyped_defs = True` (or documented exceptions added deliberately, not by
  default).
- `changelog.md` updated with a concise summary, not an exhaustive per-file list.

---

# Future Fix: Community-Contributed-Plugin Compliance Gate

The context blocks below were designed together, as a set: the goal is a pipeline that
lets a community-contributed data plugin (or, occasionally, a frontend analysis-tab
plugin family) be verified as safe and correct to merge with a bounded amount of human
review, instead of relying entirely on a reviewer reading the diff. Each block below is
independently actionable and can be picked up in its own future session; the suggested
order is 1 → 2 (cheap, static, highest signal) → 3 (makes 1/2 easy to satisfy from the
start) → 4/5 (merge-gating infrastructure) → 6/7/8 (rounding out coverage).

## 1. Behavioral conformance suite (not just signature compliance)

**Goal.** A test suite that instantiates every discovered plugin and actually runs its
core method(s) against small synthetic data, asserting it behaves like a well-formed
member of its `Meta*` family — not just that it has the right method names.

**Why.** `tests/unit/plugins/test_plugin_compliance.py` already does the hard part of
discovery: it walks `poriscope.plugins` with `pkgutil.walk_packages`, imports every
module, and (via `BASE_CLASS_DATA`) knows which concrete classes implement which
`Meta*` base. But it only checks `__abstractmethods__`/type-hint compliance — it never
calls the plugin. A community-contributed plugin can satisfy every signature check and
still crash immediately on real data, leak resources, or silently produce garbage.

**Implementation plan.**
1. Add `tests/unit/plugins/test_plugin_conformance.py`, structured like
   `test_plugin_compliance.py` (reuse its discovery loop and `META_CLASSES` set) but
   parametrized over *concrete* plugin classes rather than base classes.
2. For each `Meta*` family, define one canonical synthetic fixture already present
   under `tests/synthetic_data/` (`synthetic_chimera.py`/`multichannel_chimera.py` for
   readers, `synthetic_events_db.py` for db loaders/writers, `synthetic_metadata_db.py`
   for metadata-consuming plugins) and a minimal valid `settings` dict built from each
   plugin's own `get_empty_settings()` (fill required `Value`s with the midpoint of
   `Min`/`Max` or the first `Options` entry — this doubles as a smoke test that
   `get_empty_settings()` itself returns a self-consistent schema, see block 2 below).
3. Write one generic conformance check per `Meta*` family (not per plugin) that:
   - instantiates the plugin with the synthetic settings dict,
   - drives it through its family's real lifecycle (e.g. for `MetaEventFinder`: find
     events on a synthetic trace and assert the returned event boundaries are
     monotonic, in-bounds, and non-overlapping; for `MetaReader`: `load_data` on a
     synthetic channel and assert dtype/shape match `get_raw_dtype()`/declared
     channel count; for `MetaEventFitter`: fit a synthetic event and assert
     `_populate_event_metadata`'s return dict has the keys the base class documents),
   - calls `close_resources()` afterward and asserts no exception and no dangling
     open file handles/db connections (e.g. via `psutil.Process().open_files()` diffed
     before/after, if `psutil` is already a dependency, otherwise skip this specific
     assertion rather than adding a new dependency just for it).
4. Register this as its own pytest marker (e.g. `conformance`) so it can be run
   standalone in CI for exactly the plugin file(s) that changed in a PR (see block 5).

**Gotchas.** This will only be as strong as the synthetic fixtures are representative —
keep the fixtures' parameters (trace length, noise level, event count) realistic enough
that a finder/fitter can't trivially pass by doing nothing. Don't try to make one
mega-fixture cover every family; a small dedicated fixture per family, reused across
all plugins in that family, is easier to reason about and keeps failures attributable
to the plugin under test rather than the fixture.

**Verification.** Run against every *existing* in-repo plugin first (they should all
pass, since they're already trusted) before treating a conformance failure on a new
contribution as meaningful signal.

## 2. Settings-schema linter for `get_empty_settings()`

**Goal.** A static (no I/O, no instantiation-with-real-data-required) check that a
plugin's declared settings schema is internally self-consistent.

**Why.** `BaseDataPlugin.get_empty_settings()` (see `poriscope/utils/BaseDataPlugin.py`)
returns `Dict[str, Dict[str, Any]]` entries shaped `{"Type", "Value", "Options", "Min",
"Max"}`, and `_validate_param_types`/`_validate_param_ranges` check a *supplied*
settings dict against this schema at runtime, per-instantiation. Nothing currently
checks the schema itself for self-consistency independent of any particular value
supplied — e.g. `Min > Max`, a `Value`/`Options` list mixing incompatible `Type`s, or a
`Type` that doesn't match the Python type of `Value`. These are exactly the kind of
copy-paste mistake a first-time contributor adapting an existing plugin would make.

**Implementation plan.**
1. Add a small pure-Python validator, e.g.
   `poriscope/utils/settings_schema.py::validate_settings_schema(schema: dict) -> list[str]`
   returning a list of human-readable problems (empty list = clean), checking per
   parameter entry: `Type` and `Value` keys are present; if `Value is not None`,
   `isinstance(Value, Type)`; if both `Min` and `Max` are set, `Min <= Max`; if
   `Options` is set, every option's type matches `Type` and (if `Value is not None`)
   `Value in Options`.
2. Add a fast, no-fixture-needed pytest test (can live in `test_plugin_compliance.py`
   itself, right next to the existing structural checks, or as a new
   `test_settings_schema.py`) that calls `plugin_cls().get_empty_settings()` for every
   discovered concrete plugin class and runs it through `validate_settings_schema`,
   asserting an empty problem list. (Most plugins' `get_empty_settings()` should be
   callable without a fully-populated `settings` dict — confirm this holds for all
   existing plugins first; a few may need `standalone=True` passed.)
3. This is cheap enough to run as a blocking pre-commit/CI check on every PR touching
   `poriscope/plugins/**`, well before the more expensive conformance suite in block 1.

**Gotchas.** `Options`/`Min`/`Max` are explicitly optional (can be `None`) per the
existing docstring — don't require them, only check consistency *when present*.

## 3. Contribution scaffold / template generator

**Goal.** Shift compliance left: a new plugin should start out already satisfying
pydoclint, mypy, `test_plugin_compliance.py`, and (once built) blocks 1 and 2 above,
rather than a contributor discovering violations only after opening a PR.

**Why.** Every plugin family's abstract method list, docstring style (sphinx-style,
per `[tool.pydoclint] style = "sphinx"`), and settings-schema shape is already fully
determined by its `Meta*` base — there's no reason a contributor should hand-write
this from a blank file when it can be generated correctly the first time.

**Implementation plan.**
1. Add `scripts/new_plugin.py`, invoked like
   `python scripts/new_plugin.py --family MetaEventFinder --name MyEventFinder`.
2. For the given `--family`, use `inspect` on the corresponding `Meta*` class (same
   introspection `test_plugin_compliance.py` already does via
   `get_required_methods`/`__abstractmethods__`) to generate a stub subclass in the
   right `poriscope/plugins/<category>/` folder, with:
   - one method stub per abstract method, each with a sphinx-style docstring skeleton
     whose `:param:`/`:return:`/`:rtype:` entries are pre-filled from the base method's
     own signature and docstring (so pydoclint passes on the stub immediately),
   - a `get_empty_settings()` stub returning one example parameter entry with a comment
     showing the full `{"Type", "Value", "Options", "Min", "Max"}` shape,
   - a matching `tests/unit/plugins/<category>/test_my_event_finder.py` stub that
     imports the new class (so `test_plugin_compliance.py`'s discovery picks it up
     immediately) and includes a placeholder for the block-1 conformance test.
3. Document the script in `CLAUDE.md` under "Where to add a new plugin" as the
   recommended starting point (the existing prose there, pointing at "an existing tab
   (e.g. `Protein*`) as a template," is a weaker substitute for a scaffold that's
   guaranteed to already pass every check).

**Gotchas.** Keep the generated stub minimal (raise `NotImplementedError` in method
bodies) — the goal is a compliant skeleton, not a working plugin; don't try to
generate real algorithmic logic.

## 4. Static security review for module-level plugin code

**Goal.** Reduce the trust risk inherent in blindly executing arbitrary community-
submitted `.py` files inside a desktop app running with the user's full privileges.

**Why.** Per `MainModel.populate_available_plugins()`'s documented behavior, plugin
discovery imports *every* `.py` file found under `poriscope/plugins/` (and the user
plugin folder) — and Python import always executes module-level code unconditionally,
before any of `test_plugin_compliance.py`'s reflection even runs. For in-house
contributors this is an accepted, low-risk convenience; for unvetted community
submissions landing in the same discovery path, it's a real code-execution trust
boundary that none of the current tooling (ruff/mypy/pydoclint) is designed to police.

**Implementation plan.**
1. Add `bandit` to `requirements-dev.txt` and run it as a `pre-commit` `repo: local`
   hook scoped to `files: ^poriscope/plugins/` (mirroring how the pydoclint hook is
   already scoped), using a conservative rule subset first (e.g. flag
   `subprocess`/`eval`/`exec`/`pickle.load`/dynamic `importlib` calls, network access,
   and filesystem writes outside of an expected data directory) to avoid a noisy
   first run.
2. Additionally add a narrow, purpose-built AST check (simpler and more targeted than
   general-purpose `bandit` rules) that flags any *module-level* statement in a plugin
   file other than imports, constants, and class/function definitions — since a
   compliant plugin should never need top-level side effects, and "module-level code
   that does something when merely imported" is the single highest-risk pattern for
   this specific discovery mechanism.
3. Triage findings as blocking (network/subprocess/eval/exec) vs. advisory (everything
   else) — don't try to make `bandit`'s full default rule set blocking on day one, or
   it will generate enough noise to undermine trust in the check.

**Gotchas.** This is a deliberately narrow first pass, not a sandbox — it raises the
bar for a careless or lazy submission but is not a defense against a determined
adversary (a plugin can still do plenty of damage inside a legitimate-looking method
body that only runs once instantiated). True sandboxing (subprocess isolation,
restricted execution) is a much larger architectural change and is explicitly out of
scope here; if that level of isolation is ever wanted, treat it as a separate,
much larger design discussion, not an incremental addition to this one.

## 5. Required, scoped CI gate + CODEOWNERS for `poriscope/plugins/**`

**Goal.** No plugin file merges without both automated checks (scoped to just the
changed plugin) and a human sign-off — formalizing, for everyone, the informal
per-plugin "ownership" that already exists for a few plugins today.

**Why.** `.github/workflows/ci-fork-pr.yml` already exists specifically for
fork-originated PRs (the realistic path for a community contribution) and already runs
strict `pre-commit run --all-files` plus `pytest -m fast` with `contents: read`
fork-safe permissions — this is the right place to add plugin-specific gating rather
than inventing a parallel workflow. There is currently no `CODEOWNERS` file in the
repo, so plugin review isn't enforced by GitHub at all today.

**Implementation plan.**
1. Add a `CODEOWNERS` file at the repo root mapping each
   `poriscope/plugins/<category>/` folder (and, once it exists, `poriscope/utils/Meta*`)
   to the relevant maintainer(s)/owner(s) — this only takes effect as a *required*
   review gate once "Require review from Code Owners" is turned on for the target
   branch's protection rule in repo Settings (an out-of-repo, admin-only config step;
   note it explicitly here so it isn't forgotten as "already handled" just because the
   file exists).
2. In `ci-fork-pr.yml`, add a step after checkout that computes the changed files
   (`git diff --name-only origin/${{ github.base_ref }}...HEAD`) and, if any match
   `poriscope/plugins/**`, runs the block-2 settings-schema check and block-1
   conformance suite scoped to just those files (e.g.
   `pytest -m conformance -k <derived from changed filenames>`), in addition to the
   existing `pytest -m fast` step — so a plugin-touching PR gets strictly more
   scrutiny than a non-plugin PR, without slowing down every PR with the full
   conformance suite.
3. Mark this new step (and the existing strict `pre-commit` step) as required status
   checks in branch protection for `main`/`develop`.

**Gotchas.** `ci-fork-pr.yml`'s permissions are deliberately `contents: read` for fork
safety — don't add anything to this workflow that needs write access (e.g. auto-fix
commits); that's what `ci-internal-pr.yml` is for, and it isn't fork-safe.

## 6. Docs-render check in CI (Sphinx warnings-as-errors)

**Goal.** Catch a plugin whose docstrings are pydoclint-compliant but still break
Sphinx rendering, before merge rather than after.

**Why.** `.github/workflows/build_and_deploy_docs.yml` only runs
`scripts/generate_all_autodoc_rst.py` + `sphinx-build -b html docs/source docs/build`
on push to `main` (or manual dispatch) — never on a PR, and without `-W`
(warnings-as-errors), so a bad cross-reference or malformed directive in a new
plugin's docstring currently surfaces, if at all, only after it's already merged and
deployed.

**Implementation plan.**
1. Add a `docs-check` job to `ci-fork-pr.yml`/`ci-internal-pr.yml` (or a new dedicated
   PR-triggered workflow) that runs the same two commands
   (`python scripts/generate_all_autodoc_rst.py` then
   `sphinx-build -b html docs/source docs/build`) but with `-W --keep-going` so
   warnings fail the build and all of them are reported in one pass rather than
   stopping at the first.
2. This job doesn't need the full Qt/Xvfb system dependency set that the test jobs
   need (autodoc generation and Sphinx build don't launch the app) — keep it as a
   lighter, faster job so it doesn't slow down the PR feedback loop.
3. No need to deploy anything from this job — it's a build-only check; reuse
   `actions/upload-artifact` only if reviewers want a preview of the rendered docs.

**Gotchas.** Turning on `-W` will likely surface pre-existing warnings from plugins
already in the repo, not just future ones — expect an initial cleanup pass (grandfather
via a suppression list keyed by warning text, mirroring the `.pydoclint-baseline.txt`
pattern, if the initial warning count is large) before this can be made blocking.

## 7. Fuzz / malformed-input testing for data readers

**Goal.** Catch unhandled crashes in community-contributed parsers on truncated,
corrupted, or otherwise malformed binary input — the single most likely crash surface
for a new `MetaReader` subclass, since readers parse arbitrary externally-produced
files by nature.

**Why.** None of the current checks (compliance, conformance from block 1, pydoclint,
mypy) exercise a reader against anything but a well-formed synthetic file. A community-
contributed reader for a new hardware/file format is exactly the plugin family most
likely to choke on a real-world file that's merely slightly off-spec (truncated
mid-record, wrong header magic, unexpected byte order) — the app should degrade
gracefully (raise a clear, caught exception) rather than crash or hang.

**Implementation plan.**
1. Add `tests/unit/plugins/datareaders/test_reader_fuzz.py`, parametrized over every
   concrete `MetaReader` subclass discovered the same way `test_plugin_compliance.py`
   does.
2. For each reader, take its family's existing valid synthetic fixture (e.g.
   `synthetic_chimera.py`'s output for `ChimeraReader*`) and generate a small, fixed
   set of deterministic mutations rather than open-ended random fuzzing (truncate to
   several byte offsets, flip the header's magic bytes, zero out a middle section) —
   deterministic mutations keep the test reproducible and avoid flaky CI, which
   open-ended `hypothesis`-style fuzzing would risk here.
3. Assert only that each mutation results in either a clean successful read (if the
   mutation happened to still be valid) or a caught, well-typed exception — never an
   unhandled crash, hang, or silent data corruption (e.g. returning a truncated array
   without signaling the truncation).
4. This test is necessarily reader-format-specific for the mutation *generation* step
   (each format's header/magic bytes differ), but the assertion logic and discovery
   loop should be shared/generic — write one small per-format "corrupt this fixture"
   helper per reader family, not per individual reader.

**Gotchas.** This only meaningfully applies to `MetaReader`; don't try to generalize it
to every plugin family — event finders/fitters/filters operate on already-validated
in-memory arrays, not raw external files, so this specific risk doesn't apply to them.

## 8. Custom lint rules encoding existing tribal knowledge

**Goal.** Make the project's already-established-but-only-documented-in-CLAUDE.md/
memory conventions mechanically enforced, so they don't depend on a human reviewer
remembering to check for them on every plugin PR.

**Why.** Several patterns are currently enforced only by convention and review
attentiveness: no nested function definitions, no bare `except:` (narrow to
`except Exception:` at minimum so a `Raises` docstring section is even possible), and
explicit `finally`-block cleanup of sqlite3 cursors/connections. These are exactly the
kind of thing a first-time community contributor won't know to do unless a machine
tells them.

**Implementation plan.**
1. No nested functions: a straightforward `ast`-based check (walk each `FunctionDef`
   node's body for a nested `FunctionDef`/`AsyncFunctionDef`) — add as a `ruff`
   custom rule if ruff's plugin API supports it cleanly for this project's ruff
   version, otherwise a small standalone script run as a `pre-commit` `repo: local`
   hook (same pattern as the pydoclint hook), scoped to `files: ^poriscope/`.
2. Bare `except:`: `ruff` already has a built-in rule for this
   (`E722`/`BLE001`-family, depending on ruleset naming in the installed ruff
   version) — check whether it's already enabled in this project's `pyproject.toml`
   ruff config before writing a custom check; if not, this is a one-line config
   addition, not new code.
3. Explicit sqlite3 resource cleanup in a `finally` block: harder to express as a
   generic AST rule (requires tracking whether a `sqlite3.connect`/`.cursor()` call's
   result is closed on every exit path) — likely not worth a fully general static
   checker; instead, cover this via the block-1 conformance suite's open-file-handle
   check for `MetaDatabaseLoader`/`MetaDatabaseWriter`/`MetaWriter` plugins
   specifically, which catches the same defect empirically rather than syntactically.
4. Document whichever of these become real automated checks in `CLAUDE.md`'s
   "General Instructions" section, replacing the current prose-only statement of the
   rule with a note that it's now enforced by `<tool>`.

**Gotchas.** Don't over-invest in generalized static analysis for the sqlite3-cleanup
rule specifically — it's a narrow, semantic (not syntactic) pattern where a runtime
conformance check is a better cost/benefit trade than a bespoke AST checker.
