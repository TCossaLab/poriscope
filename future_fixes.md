# Future Fix: Full Codebase Type-Annotation Pass

Context block for a dedicated future session. Paste/point Claude Code at this file to
resume this work; it is written to be self-contained.

## Progress (2026-08-23)

First installment landed on `feature/loadbearing_docstrings`: type hints added, copied
from each family's `Meta*` base, to every method across `poriscope/plugins/datareaders/`,
`eventfinders/`, `filters/`, `eventloaders/`, `datawriters/`, `db_loaders/`, `dbwriters/`,
plus the CUSUM-family fitters (`ClassicCUSUM.py`, `CUSUM.py`, `IntraCUSUM.py`,
`NoFitter.py`). `NanoTrees.py`/`Basic_PeakFinder.py`/`PeakFinder.py` excluded per the
Exclusions section below, as always. `.pydoclint-baseline.txt` regenerated once,
centrally, to absorb the new `DOC108` entries. See `changelog.md`'s "New Dev Tooling:
Type annotations for data plugins" entry for the summary, and the individual commits
(`feat(types): add type hints to ...`) on that branch for the per-family diffs.

**Still remaining before this pass is done** (per Scope below): the rest of the data
plugin families not yet covered (`Basic_PeakFinder`/`NanoTrees`/`PeakFinder` themselves,
once someone other than this pass's owner picks them up), the `Meta*` ABCs in
`poriscope/utils/` (several, e.g. `MetaEventFitter.py`, already carry partial
annotations from earlier work but were not exhaustively re-verified here beyond what
this batch's mypy runs happened to touch), and all of controllers/models/views/app-shell
code. Steps 2-4 in Scope (flipping the pydoclint/mypy policy flags) have **not** been
started - do not flip those until annotation coverage is much closer to complete.

**Gotchas confirmed empirically this round, worth internalizing before the next
session continues this pass:**
- The "annotation-unchecked cascade" gotcha is real and non-trivial in volume: adding
  hints to a ~20-file batch surfaced 14 real, blocking `pre-commit run mypy --all-files`
  errors, none of which were caused by the new hints themselves - all were pre-existing
  logic/contract mismatches that were simply invisible to mypy before. Budget time for
  this triage on every future batch, not just the mechanical hint-copying.
- **Don't trust a bare local `mypy <files>` invocation as the pass/fail signal.**
  It resolved to a different, newer mypy version than pre-commit's pinned
  `mirrors-mypy` hook in this environment, and - more importantly - passing a narrow
  file subset let mypy's import-following pull in unrelated files (via package
  `__init__.py` re-exports) and report pre-existing errors in files nobody touched
  (`MetaController.py`, `NanoTrees.py`, `PeakFinder.py`), none of which actually block a
  commit. `pre-commit run mypy --all-files` (or `pre-commit run mypy --files <paths>`
  for a quick spot check) is the only trustworthy gate - it matches what CI enforces.
  Verify this empirically with `git stash` before assuming any mypy output is
  attributable to your own change.
- Three concrete "genuine logic-shaped mismatch, flag don't fix" discrepancies were
  initially suppressed with narrow, commented `# type: ignore[<code>]` lines (not
  fixed, not hidden silently) so the batch could land, then resolved for real in the
  same session once reviewed: `CUSUM`/`NoFitter`'s `baseline_std` (`Optional[float]`
  used in unguarded arithmetic) now raises a clear `ValueError` if `None`;
  `sublevel_starts` (`List[int]`-declared but ndarray at runtime) is now wrapped in
  `np.asarray(...)` at the two arithmetic call sites rather than widening
  `MetaEventFitter`'s declared type (which turned out to be intentionally generic -
  worth double-checking a `Meta*` base's docstring for "this can be more than it
  looks like" language before assuming a narrower type is the right fix, as the
  first-pass suggestion here was wrong until that was checked); and
  `SQLiteEventWriter._write_data`'s `Optional[int]` params passed straight into
  `int()` now get an explicit `ValueError` guard instead. See `changelog.md`'s
  updated entries for the final resolutions and the no-longer-relevant
  `# type: ignore` lines have been removed - none remain from this batch.

## Measured remaining scope (2026-08-23)

Rather than guess, both policy flags were flipped temporarily (`arg-type-hints-in-signature = true` in `pyproject.toml`, `disallow_untyped_defs`/`check_untyped_defs = True` in `mypy.ini`), the real gates run against the whole tree, then both reverted. Findings:

**pydoclint** (`arg-type-hints-in-signature = true`): 995 new violation lines across 48 files - `plugins/` (31 files), `utils/` (13), `controllers/` (2), `models/` (1), `views/` (1). Two distinct kinds of work, not one:
1. Genuinely unannotated methods (`DOC106`/`DOC107`), concentrated entirely in files this pass hasn't touched: all 13 `Meta*`/`BaseDataPlugin`/`LogDecorator` files in `utils/`, the whole `analysistabs/` GUI family (5 Controller/Model/View triads + `utils/*controls.py` mixins + `walkthrough*`), `DataPluginController.py`/`DataPluginModel.py`/`main_controller.py`, and `dict_dialog_widget.py`. Plus the excluded `NanoTrees.py`/`Basic_PeakFinder.py`/`PeakFinder.py`, which need an explicit decision (permanent exclusion vs. eventually annotating) before any global flip, since they can't just stay silently broken once the policy is on.
2. Stale docstring `:type:` text in files this pass *already* typed (`DOC105` - hint exists, docstring wording doesn't match it exactly), a smaller mechanical cleanup in those 13 already-completed data-plugin files: e.g. `MetaReader._validate_file_type`'s docstring says `os.Pathlike` (lowercase typo) instead of `os.PathLike`; `_get_file_pattern`'s docstring still says `os.PathLike` for a parameter that's actually `str`; `_convert_data`'s docstring says generic `numpy.ndarray` instead of the real `npt.NDArray[np.int16]`; and every `get_empty_settings`/`standalone`/`globally_available_plugins` docstring line needs its optional-argument phrasing tightened to match exactly. These propagated into every subclass that copied the same base docstring.

**mypy** (`disallow_untyped_defs`/`check_untyped_defs = True`): 3248 errors, but 2167 of those are in `tests/` - a gotcha not previously documented here: pre-commit's `mypy` hook passes explicit file paths (including test files), which bypasses `mypy.ini`'s `exclude = ^tests/` entirely (`exclude` only applies to directory-discovery, not explicitly-listed files - a known mypy quirk). **The pre-commit hook config needs its own `exclude`/`files` scoping added before this flip**, independent of `mypy.ini`, or the flip will look clean via `mypy poriscope` but break every real commit. The remaining 1021 real errors in `poriscope/` are heavily concentrated in the same not-yet-annotated areas: `analysistabs/ProteinView.py` (78), `main_view.py` (67), `MetadataView.py` (62), `NanoTrees.py` (45), `RawDataView.py` (41), the `*controls.py` mixins, tapering down through the rest of `utils/`, `views/widgets/`, and the controllers/models.

**Ordered remaining work:**
1. `poriscope/utils/` - the 13 `Meta*`/base files (biggest leverage: everything else depends on them). **Done** (2026-08-23): all 13 files (`BaseDataPlugin.py`, `LogDecorator.py`, `MetaController.py`, `MetaDatabaseLoader.py`, `MetaDatabaseWriter.py`, `MetaEventFinder.py`, `MetaEventFitter.py`, `MetaEventLoader.py`, `MetaFilter.py`, `MetaModel.py`, `MetaReader.py`, `MetaView.py`, `MetaWriter.py`) now fully annotated per the same contract-matching rule as the data-plugin batch. `test_plugin_compliance.py` (71 cases) and `pre-commit run mypy --all-files` both pass clean with everything applied together. **Correction:** an earlier version of this note claimed `.pydoclint-baseline.txt` needed no regeneration - that was wrong, confirmed by directly running `pre-commit run --all-files`, which failed on 21 new, not-yet-baselined `DOC108` lines across `BaseDataPlugin.py`/`MetaController.py`/`MetaEventFinder.py`/`MetaEventFitter.py`/`MetaModel.py`/`MetaReader.py`/`MetaView.py` (methods that had zero prior hints, not partial ones, so nothing pre-baselined them). Regenerated fresh from the full tree (`pydoclint --generate-baseline=True --baseline=.pydoclint-baseline.txt poriscope`); the diff was a clean 21-line addition with nothing removed or altered. See `changelog.md`'s updated "New Dev Tooling: Type annotations for data plugins" entry for the per-file summary and the couple of genuinely new flagged discrepancies (`MetaEventFitter.reset_channel`'s `channel=None` no-op gap, `MetaView`'s two unguarded-`Optional` call sites) - both marked with commented `# type: ignore` and left for a follow-up pass, not fixed, per this round's no-logic-changes instruction.

   **Process note:** this batch was run as 6 parallel forks; 4 of them were killed mid-task by the Claude account's own session usage limit (not a bug in the fork prompts) after already writing their file edits to disk but before sending a final report. All 4 killed forks' edits were independently verified afterward (full diff review + compliance/mypy re-run) and found complete and correct, but this is a real risk worth remembering: **don't assume a fork's edits are trustworthy just because a report arrived - and don't assume they're worthless just because a report *didn't* arrive.** Verify by re-running the real checks and diffing the actual files, either way. Launching 6 forks at once on files this large may have contributed to hitting the limit; a future large batch might do 3-4 at a time instead, or check remaining session budget first if that becomes visible.
2. `analysistabs/` GUI family - 5 tab triads + `*controls.py` mixins + `walkthrough*` (the largest single chunk of remaining volume). **Done** (2026-08-24): all 22 files annotated, one tab family per commit, in the order shared-utils -> Clustering -> EventAnalysis -> RawData -> Metadata -> Protein. Every file passes the AST completeness scan (no parameter or return left unannotated) and `pydoclint --arg-type-hints-in-signature=True` reports zero `DOC104`-`DOC107` anywhere under `analysistabs/`. `pre-commit run --all-files`, `test_plugin_compliance.py` (71 cases), and `pytest -m "not e2e and not slow"` (2615 passed, 2 skipped) were all run green after each tab before committing it. `.pydoclint-baseline.txt` was regenerated per tab; every regeneration was a pure addition of `DOC108` policy nags with nothing removed or altered.

   **Method that worked well and is worth reusing for step 3:** write each file's edits as a standalone `rep(old, new)` Python script in a scratchpad, dry-run it with writes stubbed out to validate every anchor string matches exactly once, then apply. Anchors that fail the dry run are almost always a sign the docstring differs from what you assumed, which is worth knowing *before* touching the file. Prepare the next tab's scripts while the current tab's 35-minute test run is in flight - the suite is the long pole, not the editing.

   **Recurring defect classes this surfaced** (all corrected, none behavioural): (a) *callback-shape annotations* - `relay_*`/`update_column_units`/`relay_units`/`relay_table_by_column`/`relay_column_type` are `global_signal` return-callbacks, so their parameter type is whatever the *called* `Meta*` method returns (usually `Optional[str]`), not the `dict` the parameter name suggests; nine of these were typed wrong across three controllers. (b) *off-by-one nesting on plot features* - `get_plot_features` returns one flat list per event, but three call sites declared list-of-lists. (c) *channel stringification* - `current_channel`/`plotted_datasets` slots declared `Optional[int]` while holding the selection-tree display string (`MetadataView` converts with `int(channel)` and genuinely is `int`; `ProteinView` does not and is `str` - they differ, which is itself worth a look). (d) *attributes first assigned `None`* need an explicit `Optional[...]` in `_init` or mypy infers `None` and every later assignment errors.

   **pydoclint parser quirk worth internalising:** prose placed *after* a sphinx field list gets folded into the last field's `:type:`, producing a spurious `DOC105` on whichever parameter happens to be documented last. Nine docstrings across `MetadataView`/`ProteinView` hit this; the fix is to put the description first, which is the conventional layout anyway.

   **Flagged, not fixed** - all marked in-place with narrow commented `# type: ignore` lines, listed here for a follow-up pass: `start_walkthrough` passes a possibly-`None` overlay into `StepDialog`, which declares it non-optional and relies on the resulting `AttributeError` producing its fallback dialog; `ClusteringView.units` is a `Dict[str, str]` when filled column-by-column but a positional sequence when set by `update_plot`; `EventAnalysisView._update_event_plot` zips each feature list against its label list guarding only on the feature list, so a fitter returning features without labels raises `TypeError`; `on_raw_filter_validated` in both `MetadataView` and `ProteinView` uses `_pending_filter_name`/`_pending_filter_text` as a dict key and value with no `None` guard; `MetadataView.hist_data` and `ProteinView.hist_data` hold three different shapes depending on which plot path filled them; and `on_button_clicked` in both `rawdatacontrols` and `eventAnalysisControls` ends with `button_mapping.get(button_type, lambda: None).setChecked(False)`, which would raise on an unmapped button type (mypy does not catch this one - `.get()`'s default widens the inferred type).
3. `main_controller.py`/`main_model.py`/`main_view.py`, `DataPluginController.py`/`DataPluginModel.py`, `settings_window.py`, `help.py`, `views/widgets/*`. Measured 2026-08-24, after step 2: **439 functions across 42 files** still have at least one unannotated parameter or return, concentrated in `views/main_view.py` (65), `views/widgets/icon_menu_widget.py` (30), `views/settings_window.py` (28), `views/widgets/clustering_settings_widget.py` (20), `models/main_model.py` (19), `controllers/main_controller.py` (19), and `views/widgets/text_menu_widget.py` (18), tapering into the smaller widgets. `NanoTrees.py` (45), `PeakFinder.py` (13) and `Basic_PeakFinder.py` (12) are in that count but excluded per the standing policy below.
4. A docstring-text-only cleanup pass over the 13 files already typed by the first installment (the `DOC105` stale-wording list above).
5. A decision on `NanoTrees.py`/`Basic_PeakFinder.py`/`PeakFinder.py` - permanent carve-out or eventual inclusion - before flipping anything globally.
6. Add `exclude`/scoping to the pre-commit `mypy` hook itself so it stops checking `tests/` as explicit paths, independent of `mypy.ini`.
7. Only then: flip both flags, regenerate the pydoclint baseline fresh, confirm both gates are clean, update `CLAUDE.md`.

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

## Scope / sequencing

1. Add type hints file-by-file (or in small independent batches via subagents — see
   Method below) across all of `poriscope/`, including `Meta*` ABCs in
   `poriscope/utils/`, all plugin families, controllers/models/views, and app-shell
   code.
2. Once annotation coverage is effectively complete, flip
   `[tool.pydoclint] arg-type-hints-in-signature = true` in `pyproject.toml`, run
   `pydoclint --generate-baseline=True --baseline=.pydoclint-baseline.txt poriscope`
   fresh from a clean tree, and confirm the new baseline is empty or near-empty (a
   near-empty remainder here would represent a real gap to close, not something to
   wave through).
3. Flip `mypy.ini`'s `disallow_untyped_defs`/`check_untyped_defs` to `True` and confirm
   `mypy poriscope` is still clean (or fix what it now surfaces — see Known gotchas).
4. Update `CLAUDE.md`'s description of the pydoclint/mypy config to reflect the new,
   stricter policy (it currently documents the old permissive one).

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
