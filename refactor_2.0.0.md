# Poriscope 2.0.0 Refactor Plan

Approved 2026-09-03. **Step 0 and the whole of Step 1 (Tiers A, B2 and C) landed
2026-09-04** and are pushed; Step 2 onwards is open. 1.9.0 is ready and uncut.

**Every measurement below is re-baselined on `develop` at `062ef6f`, 2026-09-04.** Step 1
landed after the original `fc4fdf7` baseline (46 files, +416/-779 under `poriscope/`), so a
ratchet anchored there would credit Step 1's deletions to the refactor. Re-verifying this
document against `062ef6f` corrected nine of thirteen checkable Step 3a sub-claims, six Step 2
claims and the Decision E figure; the corrections are inline below.

**Step 2 was checked a fourth time at `c9fe294`, 2026-09-05, when it was planned in detail, and
three more claims moved** — the allowlist seed (106 → **107**), the duplication baseline (not
reproducible; no measurement tool exists), and the golden target list (most named methods are
already covered; a different set has zero coverage). Two of those three changed what the work
*is*, not just its numbers. See Step 2 below.

Full write-up: <https://claude.ai/code/artifact/304ba119-d177-4918-90af-471d6de6bb80>

Excluded throughout by standing policy: `PeakFinder.py`, `Basic_PeakFinder.py`, `NanoTrees.py`.

## Why

The analysis-tab layer never grew a real Model, so the Views absorbed everything.

| Layer | Lines | Methods | Note |
| --- | --- | --- | --- |
| 5 tab Views | 11,557 | 259 | `ProteinView` 4,043; `MetadataView` 3,651 |
| 5 Controls widgets | 4,381 | 145 | all inherit plain `QWidget`; no base class |
| 5 tab Controllers | 1,411 | 81 | 114 `self.view.*` against 8 `self.model.*` |
| 5 tab Models | 298 | 7 | 4 of 5 are `def _init(self): pass` |

75 of 77 `global_signal.emit` sites are in Views, 0 in Controllers. Views import `hdbscan`,
`GaussianMixture`, `curve_fit`, `find_peaks`, `fast_histogram`, and author raw SQL.
641 removable lines of byte-identical methods across the 5 Controls files, 444 of them
identical in all five; ~600 duplicated lines *each* between `MetadataView` and `ProteinView`;
17 of 23 Metadata/Protein Controller methods identical.

No characterization tests exist. Coverage runs (`pytest-cov` landed 2026-09-04) but nothing
fails on a drop.

## Decisions

Reasoning is in `DECISIONS.md` (2026-09-03, two entries).

- **A.** The return-value signal bus becomes `get_plugin`/`call` on `MetaController` and
  `MetaModel`, with instances **pushed** down the existing notification path.
  Fire-and-forget signals (`plugin_state_changed`, `add_text_to_display`,
  `update_progressbar`, `create_plugin`) are unchanged.
- **B.** Controller mediation is kept. Commands View→signal→Controller→call→Model; results
  Model→signal→View with the Controller connecting. `RawDataController.calculate_psd` is the
  template.
- **C.** 2.0.0 takes the queued ABC breaks: the `"Kind"` schema key, splitting
  `MetaReader.load_data`'s `raw_data` arm, `close_resources` channel dispatch,
  `_write_data`'s 13 parameters, `MetaEventFinder`'s undeclared `Threshold`.
- **D.** 1.9.0 ships Tier A + B2 + C only. Tier B ships inside 2.0.0.
- **E.** Moved tests are re-pointed, test owner reviews. **Needs her agreement before Step 2
  starts** - see "The ask to Carolina" below, which scopes it and corrects the earlier
  "1,085 view tests" figure to 324. Re-pointing is *mostly* mechanical, not entirely: 175 of
  the 324 are a receiver rename, but 75 encode a same-object stub seam and 46 more assert on a
  `global_signal.emit` that Step 4a deletes.

## Sequencing

Tab by tab. Clustering first (969 lines, self-contained, no bus calls in the hot path), then
RawData/EventAnalysis, then Metadata/Protein. Full suite green at every step; one feature
branch per piece, finished into `develop` before the next starts.

```
Step 0 (measurement) ──┐
                       ├──→ Step 2 (tests, GATE) ──┬──→ Step 3 ──→ Step 6 ──→ Step 7
Step 1 (1.9.0)      ───┘                           ├──→ Step 4
                                                   └──→ Step 5 (parallel)
Decision A ──→ Step 4a ──→ Protein threading fix, and Step 5b's relay extraction
Step 3a — independent of the test gate, but gated on directory ownership.
```

Hard blocks:

- Step 2 blocks Steps 3–5 absolutely.
- **Ownership, not just tests.** `.github/CODEOWNERS` assigns `tests/` and
  `poriscope/plugins/analysistabs/utils/` **solely** to @Carogg28, and `poriscope/views/` and
  `poriscope/plugins/analysistabs/` jointly. Step 3a rewrites all five `*controls.py` inside
  that solely-owned directory and lifts shared code out into Kyle-owned `poriscope/utils/`;
  Step 3f moves `walkthrough.py` and `walkthrough_mixin.py` out of it. So 3a is **not** the
  un-gated escape hatch an earlier handoff called it - it is independent of Step 2 and gated on
  the same person.
- Tier A had to land before goldens are generated, or goldens encode known bugs — done
  2026-09-04, so Step 2 is now unblocked on this axis.
- Decision E must be agreed before Step 2 starts.
- Protein threading fix is already recorded as blocked on the emit-then-read conversion.
- `new_plugin.py`'s analysis-tab half is already deferred until this lands; it becomes Step 6.
- `@register_action` records `func.__name__` and `MetaView.update_actions_from_json` replays
  via `getattr(self, name)` **on the View**. **5** decorator sites over 4 distinct names
  (`ClusteringView.py:141`, `MetadataView.py:304`, `:1234`, `ProteinView.py:683`, `:2818`), not
  the 11 recorded earlier - six of those hits were docstring prose. None is on any move list,
  but decorated `_update_distribution_ensemble` is the twin of the moving
  `_update_distribution_individual`, so splitting the pair breaks the symmetry the tests are
  written against. Moving a decorated method breaks saved `.json` action files.
- Any `MetaEventFitter` signature change forces lockstep edits in the three owner-held
  fitters, because `test_plugin_compliance` compares annotations by equality. Check in first.

## The ask to Carolina — agreed 2026-09-04 (Step 2 unblocked)

**Status: put to her 2026-09-04 and answered affirmatively the same day — green light to
proceed with the plan.** Decision E is satisfied, so **Step 2 is no longer gated**, and neither
are Steps 3a and 3f. What was asked is recorded below, because the agreement is only as wide as
the ask it answered.

**Confirmed on the Step 2 split: there is no split.** Part 1 asked which half she wanted to
write; the answer is that **the whole plan is ours and she will not write any of it**. So all
five Step 2 deliverables are ours - the characterization goldens over View methods, the SQL
goldens, the `ast` boundary test, the duplication ratchet and the five no-GUI tab flows - as is
re-pointing her existing unit and e2e suites in Steps 3d and 4a-4e. Do not offer test work back
and do not treat a test-shaped deliverable as a reason to stop. This is a standing exception to
the "test-writing is hers" rule **for this plan only**; compliance-gate blocks 1 and 7 in
`future_fixes.md` remain hers.

Decision E had been recorded as a one-line ask about tests and stalled for a day because nobody
could state it precisely. It is one conversation with one person, in four parts, and three of
them are not about tests. Carolina González (@Carogg28) solely owns `tests/` and
`analysistabs/utils/`, co-owns `poriscope/views/` and `analysistabs/`, and authored 203 of the
~358 commits under `tests/` (59 against 22 in `tests/unit/views/`, 71 against 3 in
`tests/e2e/`).

1. **Who writes Step 2.** This is the gate, so it is the part that unblocks everything. Of the
   five deliverables, the `ast` boundary test, the duplication ratchet and the five no-GUI flows
   are new files overlapping no existing suite and fit the standing carve-out; the
   **characterization goldens over View methods overlap her view suites** and are hers to take
   or hand over.
2. **Re-pointing when a method changes receiver** - the original Decision E, scoped to Steps 3d
   and 4a-4e. **324 test functions** reference a moving name (11.7% of the suite's 2,781), of
   which **175 are a receiver rename**. Cheaper than it looks: each affected unit test takes one
   receiver fixture named once in its signature, there is one construction site per file, and
   `_qt_mocks.shadow_signals` finds signals by introspection so it covers a Model's signals with
   no edit at all.
3. **What is not mechanical, said up front.** 60 entries stub a moving method *as a collaborator
   on the receiver* and 15 assert on that stub - a same-object seam a View/Model split breaks,
   almost all in `test_metadata_view.py`. 46 more assert on a `global_signal.emit` that Step 4a
   deletes (`global_signal` appears in 142 test functions). Beyond that, 108 test names contain
   `view`, ~50 controller-test docstrings say "forward to the view", and Step 4d touches her
   **e2e** suites too, where `subset_filters` appears 14 times in a single test inside lambdas
   and f-strings.
4. **Structural rewrites inside her directories.** Step 3a across all five `*controls.py` (444
   removable lines, only 12 test functions touched) and Step 3f moving `walkthrough.py` /
   `walkthrough_mixin.py`. Neither is gated on Step 2.

**Offer 3a as the pilot**: it is the smallest, it re-points no test (pulling a method up to a
base preserves every `view.method(...)` call site), and it is the cheapest way to see what
"reviewed as a diff" means before agreeing to the rest.

**The escalation exit was never needed**, but it is worth keeping the principle: an ownership
block is asked first and gets a stated exit rather than an indefinite hold, because `CODEOWNERS`
is advisory by deliberate choice and Kyle has final say. Do **not** re-derive or re-send the ask:
it is above, with its measurements, and it has been answered.

## Step 0 — measurement baseline (landed 2026-09-04, re-baselined at `062ef6f`)

Re-measured on `develop` at `062ef6f`, full suite green (2,948 passed, 2 skipped). Re-run any
row with the command beside it; these are the numbers Steps 3-5 are judged against, and they
supersede the `fc4fdf7` figures.

**Coverage** — `pytest --cov=poriscope --cov-report=term-missing`. Repo total **83%**
(21,441 statements, 3,693 missed). Every percentage below is unchanged from `fc4fdf7`; only
statement counts moved, so Step 1 neither improved nor eroded coverage. Analysis-tab layer:

| Module | Stmts | Cover | | Module | Stmts | Cover |
| --- | --- | --- | --- | --- | --- | --- |
| `ClusteringView` | 359 | 89% | | `ClusteringController` | 55 | 100% |
| `EventAnalysisView` | 456 | 87% | | `EventAnalysisController` | 57 | 100% |
| `MetadataView` | 1,457 | 91% | | `MetadataController` | 136 | 96% |
| `ProteinView` | 1,587 | 90% | | `ProteinController` | 127 | 97% |
| `RawDataView` | 673 | 87% | | `RawDataController` | 56 | 100% |

The four empty Models are 12 statements each at 100%; `RawDataModel` is 40 at 88%. The
`Meta*` bases are the weak spot: `MetaWriter` 69%, `MetaReader` 71%, `MetaModel` 73%,
`MetaDatabaseWriter` 73%, `MetaEventFitter` 74%, `MetaEventLoader` 76%.

**LOC per layer** — `wc -l`. Views 11,557 (Protein 4,043, Metadata 3,651, RawData 1,722,
EventAnalysis 1,172, Clustering 969); Controls widgets 4,381; Controllers 1,411; Models 298.

**Byte-identical methods** — AST parse of each family, `ast.get_source_segment` per
function, dedented and stripped, counted where the identical text appears in more than one
file of the family. Removable lines = duplicate copies beyond the first.

| Family | Files | Methods | Identical bodies | Removable lines |
| --- | --- | --- | --- | --- |
| `*View.py` | 5 | 259 | 23 | 351 |
| `*Controller.py` | 5 | 81 | 20 | 207 |
| `*controls.py` | 5 | 145 | 25 | 641 |

Of the Controls family's 641, only **444 lines across 10 groups** are identical in all five
files and so belong to Step 3a. The rest is 152 in Metadata/Protein pairs (Step 3b), 39 in a
4-of-5 group (`createButton`) and 6 in a 3-of-5 group. The total is unchanged from `fc4fdf7`;
Step 1 removed no duplicate method.

**1,199 lines total, and now reproducible**: `python scripts/measure_duplication.py` re-derives
this table exactly, and `--check` holds it against `.duplication-baseline.json`. The original
figure was produced by a one-off unversioned script and could not be re-checked; the committed
instrument confirms it — 23/20/25 identical bodies and 351/207/641 removable lines — and also
confirms Step 3a's 444 lines across the ten groups identical in all five controls files.
The plan's ~1,900 and the >= 2,500 target both include
near-identical code this measure cannot see (`ClassicCUSUM`'s 195-line override differing in
2 lines, the Chimera readers differing in 23 of 390), so treat 1,199 as the *floor* the
ratchet starts from, not the whole prize. Largest single wins: `create_info_button` and
`create_delete_button` at 29 lines x 5 files each, `create_add_button` 17 x 5,
`update_channels` 52 x 2.

**Emit count** — `grep -rc "global_signal.emit" poriscope/`. **75** in Views
(Protein 21, Metadata 20, RawData 14, EventAnalysis 13, Clustering 7), 2 in
`MetaModel`/`MetaController`, 0 elsewhere. **77 total.** `062ef6f` removed the two
`query_database_directly` calls that `_build_where_clause`'s deletion collapsed.

`pytest-cov==7.1.0` is declared, the stray `poriscope/pytest.ini` is deleted, and
`typing_extensions` is gone from all 38 modules and from `new_plugin.py`'s generated
template in favour of the native `typing.override` — verified by importing all 124
`poriscope` modules with `typing_extensions` blocked at the meta-path.

## Step 1 — Poriscope 1.9.0 (landed 2026-09-04)

All three tiers are in. Tiers A and B2 were rewritten at `fc4fdf7` after the original lists
(drafted from the 2026-08-25 audit) named work `0abd08c`/`41adc07` had already done, and were
then **re-verified again at `c8dc953` immediately before implementation**, which corrected
five further claims — recorded inline below. The lesson stands for every remaining step:
**re-verify a tier immediately before working it.**

**Manually verified on Windows 2026-09-04 and all good**: the `3.0-` timer dialog, the
eventfinder channel list populating, and both export paths — a legitimately-empty sublevels
table writing an empty CSV, versus a filter matching no events reporting on the status panel
with no dialog. That was the last outstanding item on these tiers, so **nothing blocks cutting
1.9.0**. Note this is *not* the 2.0.0 manual pass in the Verification section below, which is a
wider sweep (all five tabs through the walkthrough plus the multiselect popup path) and is still
owed for the refactor itself.

### Tier A — before goldens are generated (landed)

What landed, and what the second verification pass changed:

- Seeding, `zip(strict=True)`, the `format_axis_label` alignment, `timer_channels` and the
  loader `None`-split all landed as described below.
- **Corrections found at `c8dc953`:** the `format_axis_label` drift is **latent, not live** —
  every unit reaching `ProteinView`'s copy is a hardcoded literal, and `proteincontrols` has
  no units label, so the single-space unit that produces `Label ( )` cannot arrive; the
  `zip` item's "size the grid from the materialised list" is redundant once `strict=True`
  raises, and was dropped; `RawDataView`'s line numbers were each off by one (registration
  `:375`, emit `:376`, read `:384`), and `timer_channels` is also never cleared between
  finders, so a failed dispatch seeded one finder with another's channels; the loaders live in
  `poriscope/plugins/db_loaders/`, not `plugins/dataplugins/databaseloaders/`;
  `_parse_ranges` splits on **every** hyphen, not the first, so a two-hyphen segment was
  dropped as well as an empty-end one.
- **`get_column_units` was not fixed** — its `""` conflation is inert, since every consumer
  erases the distinction. `DECISIONS.md` 2026-09-04.
- **`ClusteringView.axes` was not fixed.** Verified latent: both unguarded reads are
  immediately preceded by a `_reset_actions()` call, and `update_plot` carries no
  `@register_action`, so replay cannot reach it out of order. A real fix needs an
  `Optional[Axes]` declaration plus handling at both reads, which belongs with the
  canvas-lifecycle work in **Step 3**. Requeued in `future_fixes.md` with the corrected
  ~75/26 attribute counts.
- **Failure signalling:** the split is empty-frame-for-no-rows with `None` **kept** for
  failure, because `_dispatch_to` swallows exceptions and leaves the caller reading a stale
  attribute. `DECISIONS.md` 2026-09-04.

The verified detail, kept for reference:

- `ClusteringView.py:660` `GaussianMixture(n_init=100)` is unseeded; add `random_state`.
  `PeakFinder.py:5817`/`:5850` already pass `random_state=42`, so the convention exists.
  `ProteinView._generate_vm_ensemble:3268/3284/3300/3352` draws from the global NumPy RNG and
  needs the same treatment; HDBSCAN at `ClusteringView.py:912` is deterministic.
- `MetadataView.py:2576-2586` `zip()` without `strict=` over 7 fitter sequences while
  `num_events` sizes the grid. **Latent, not live** — the sole caller (`:2393-2400`) appends to
  all seven lists unconditionally per event, so lengths are structurally equal today. If they
  diverged, `labelnum` is computed from `num_events` rather than the trip count, so *no*
  subplot would get an x-axis label. Add `strict=True` and size the grid from the materialised
  list; do **not** add it to the three inner label zips at `:2619/2638/2656`, which are
  deliberately pre-padded with `None`.
- `None` means both "query failed" and "no rows" in `SQLiteDBLoader._load_metadata:823-852`
  (empty result and `sqlite3.Error` both return `None` at `:844`), and
  `MetaDatabaseLoader.load_metadata:1162` is declared `-> pd.DataFrame` while returning `None`
  at `:1189`/`:1194` — `load_metadata_raw:1145` has the same defect and
  `query_database_directly:1280` adds a third meaning, "failed validation".
  **`get_column_units` is not an instance of this**: `None` there means only "query failed";
  the conflation is `""`, which means both "units are NULL" and "no such column".
  **`get_experiment_id_by_name:400` silently depends on the current behaviour** — its
  `result.at[0, "id"]` would `KeyError` on an empty frame, so it must be fixed in the same
  commit. So must `export_subset_to_csv:522/566`, which reject a legitimately-empty
  `sublevels`/`data` table as "Failed to load".
- `RawDataView.timer_channels` used before assignment; papered over by the autouse fixture at
  `tests/e2e/conftest.py:67-86`, whose own docstring concedes the defect. One assignment
  (`:350`), one read (`:385`). The bus dispatch is `DirectConnection` so the happy path works;
  a failed dispatch raises `AttributeError`, swallowed at `:391` as "Updating ComboBoxes
  failed". **The damage is permanent**, because `:376` registers the finder key before the
  emit and the enclosing guard never retries. Add `self.timer_channels: Sequence[int] = []` to
  `_init`, move the `:376` registration after the loop, and delete the fixture.
- `format_axis_label` drifted between `ProteinView.py:4052` (module function) and
  `MetadataView.py:3626` (method). The difference is exactly ` and unit.strip()` and it is
  **behavioural, not cosmetic**: `metadatacontrols.update_column_units_label:879-889` coerces
  a missing unit to the single-space string `" "` for display and `collect_parameters:1014-1016`
  reads it straight back, so ProteinView renders `Label ( )`. A third divergent copy is inlined
  at `ClusteringView.py:733` using `unit != " "` instead of `.strip()`. 12 call sites in
  MetadataView, 8 in ProteinView, none cross-module.
- **~75 attributes assigned only outside `__init__`** across the five Views (not 28), with 26
  defensive guards (6 `hasattr`, 20 `getattr(self, ..., default)`), not 23.
  `ClusteringView.axes` is confirmed: assigned only in `_reset_actions:159/161`, read unguarded
  at `:740`/`:763`, while MetadataView guards its equivalent with `getattr`.
  **`ProteinView.ax_hist`/`ax_vm` are not an instance of this** — both are `@property` over
  axes built eagerly by `_set_custom_display_area`, which is on the construction path.

### Tier B2 — smaller than advertised (landed 2026-09-04)

Two of the six original items were already fixed by `0abd08c`/`41adc07` on 2026-08-24: the
four `AttributeError` methods (`update_unit_label`, `reset_top_inputs`, `setLanguageChecked`,
`setThemeChecked`) and `text_menu_widget`'s duplicated `QTimer.singleShot` plus stray
`print()`. What remains:

- **Landed 2026-09-04**: deleted `poriscope/views/widgets/walkthrough_steps.py`. Its duplicate
  tuple was real but had no user impact — `get_global_walkthrough_steps` had zero callers and
  all 394 lines were dead; each View carries its own live `get_walkthrough_steps`. Also
  deleted `FloatRangeLineEdit.get_values`/`used_floats`, uncalled and expanding `"3-5"` into 21
  values at 0.1 steps.
- `MainView.connect_signals:242-249`'s `isinstance(page, str)` branch is always dead — the list
  is a local literal three lines above the loop and all six values are bound methods. Delete
  the branch and correct `tests/unit/views/test_main_view.py:101-104`, whose docstring claims
  to cover it.
- **`TimeWidget` is a live user-facing bug, and not the one recorded.** The validator and
  `_parse_ranges` agree on a literal `end == 0.0`; they disagree on an *empty* end. `:69`
  substitutes `"0"` for an empty end string, so `"3.0-"` validates `Acceptable` and enables OK,
  while `_parse_ranges:188` has no such fallback, `float("")` raises, and the segment is
  dropped. `_on_ok` then stores `ranges = []` and `RawDataView.py:1118-1128` runs
  `find_events(channel, [], ...)` — event finding over no time at all, silently. Fix
  `_parse_ranges` (`split("-", 1)` plus empty-end to `0.0`), not the validator, which
  `tests/unit/views/widgets/test_time_widget.py:90-92` pins. **The `:78` unfiltered
  segment count was left alone**: `0-0` means the whole file and cannot legally be followed by
  anything, and `Invalid` on a `QValidator` refuses the keystroke outright, which is the right
  feedback. `DECISIONS.md` 2026-09-04.
- `IntegerRangeLineEdit` vs `FloatRangeLineEdit` leading-`-` handling is a **structural**
  difference only — no input produces different output, because the float version's every
  leading-`-` shape falls into its bare `except ValueError`. Nothing to rule on; Step 5d
  consolidates.

### Tier C — CI/tooling (landed 2026-09-04)

`requirements.txt` converted to UTF-8 (the Sphinx pins stay: `docs-check.yml` needs Sphinx and
the numeric stack from one file for autodoc); the mypy skew was three-way, not two (declared
1.9.0, hook v1.17.1, working venv 2.3.1) and the declared pin is now aligned to 1.17.1 with a
`DECISIONS.md` entry; `pytest.ini` gained `timeout = 300`; the dead `^tests/slow/` excludes and
the no-op `--exit-non-zero-on-fix` are gone from `.pre-commit-config.yaml`;
`tests/integration/data/` (455 KiB, referenced by nothing) is deleted.

### Deferred to 2.0.0 (Tier B)

Baseline-σ bias (+14.7%/+4.8%/+2.1% by chunk length, **two copies** — merge in 5a first);
`INSERT OR IGNORE` masking schema mismatch; `PRAGMA user_version` and the dead `extra_tables`
branch; session-restore type-name corruption; `Optional[int]` channel dispatch;
`test_plugin_compliance`'s import-order parametrization.

### Deferred into the refactor — do not fix twice

Duplication (~1,900 lines); `_setup_canvas`'s dead `num_channels`; `_factors` duplicated into
two subclasses that inherit it; `main_view.py:110-111`'s dead Figure; `hist_data`'s three
shapes; `MainView`'s navigation state as QLabel text; the five oversized `setupUi`; the
WARNING-level routine-state sweep.

## Step 2 — tests (GATE)

Re-verified at `062ef6f` (six claims moved, one bullet already done) and again at **`c9fe294`**
on 2026-09-05 when it was planned in detail — **three more moved, and two of them changed what
the work is**. Decision E is agreed and all five deliverables are ours.

### What the fourth pass changed

1. **Allowlist seed is 107, not 106.** 75 emits (21/20/14/13/7, confirmed) + **22** forbidden
   import statements over **13** distinct (View, module) pairs + 10 private-access sites. The
   bullet below instructs "add `fast_histogram`" and then quotes a total computed *before* that
   addition; `RawDataView.py:34` is the missing entry.
2. **The duplication baseline was not reproducible — now it is.** No measurement tool existed;
   Step 0's 1,199 / 68 came from a one-off unversioned script. `scripts/measure_duplication.py`
   now re-derives it and **confirms every figure exactly**, including Step 3a's 444 lines across
   ten all-five groups. So the number was right; it simply could not be checked, which is a
   different failure and a reminder that "unverifiable" is not the same as "wrong".
3. **The golden targets were wrong.** `_calculate_heatmap`, `_double_gaussian`,
   `_fit_double_gaussian`, `_compute_theoretical_blockages`, `_generate_vm_ensemble`,
   `_normalize_column_data` and both `_construct_all_points_histogram` copies **already have
   direct tests**. What has none: `RawDataView._gaussian_fit` (`:574` — its own source comment
   calls it "THE CRITICAL MATH FIX"), `RawDataView._get_baseline_stats` (`:467`, listed as
   covered in `test_raw_data_view.py:28`'s docstring with no such test),
   `MetaView._logscale_and_filter_dataframe` (`:789`), and `ProteinView._summarize_vm` (`:497`).
   Worst: **`MetaView._logscale_and_filter_multiple_columns` (`:696`) has 38 test references and
   every one is a `Mock`** — no behavioural coverage at all, on every 1-D and 2-D plot path.

### Execution — seven branches, in order

**Landed 2026-09-05: branches 1-4.** `develop` carries the harness, the duplication
ratchet, the MVC boundary allowlist and the characterization goldens. Suite at 3,136
passed / 2 skipped, up from 2,948 at the 1.9.0 baseline. Branch 5 is the coverage audit
added below; 6 and 7 are unchanged.

One branch per piece, finished into `develop` before the next starts. **Both gates are pytest
tests, not pre-commit hooks**, with measurement logic in `scripts/`: only a test is enforced by
all four CI workflows with no extra wiring and appears in `--marker-stats`, and the script keeps
"what do I have to fix" runnable on its own.

**1. `feature/step-2-test-harness`** — LANDED 2026-09-05. The shared prerequisite.
- `chore(test):` `pytest-regressions` pinned `==` in **both** `pyproject.toml [dev]` and
  `requirements-dev.txt` — `ci-branches.yml`/`ci-fork-pr.yml` install only from the latter and
  never read `pyproject.toml`; `release.yml` installs only the former. Register a
  `characterization` marker in `pytest.ini` (`--strict-markers` makes an unregistered marker a
  *collection error*). Add `pythonpath = .` — without it `tests.*` resolves only because
  `tests/e2e/conftest.py` is collected first, and `pytest tests/unit/views/test_event_analysis_view.py`
  alone fails with `ModuleNotFoundError: No module named 'tests'`.
- `docs:` `quality_control.rst` "Test Suite Configuration"; `changelog.md` under a new
  `## Poriscope 2.0.0: in progress`; `DECISIONS.md` on tests-not-hooks.

**2. `feature/step-2-duplication-ratchet`** — LANDED 2026-09-05. Second, not last: it makes Step 3a's "no copy was
lost" claim provable, and 3a precedes it.
- `chore(scripts):` `scripts/measure_duplication.py`, shaped like
  `scripts/check_plugin_module_level.py`. Algorithm per Step 0: AST-parse each file in a family,
  `ast.get_source_segment` per function, dedent + strip, group by identical text, removable lines
  = copies beyond the first. **Enumerate the five paths per family explicitly** — the fifth
  controls file is `eventAnalysisControls.py`, camelCase, and a `*controls.py` glob silently
  drops 742 lines (17% of the family).
- `test(scripts):` cover the instrument against small synthetic module texts, not the real tree,
  so the tests do not move when the refactor does.
- `test:` `.duplication-baseline.json` (precedent: `.pydoclint-baseline.txt`) plus the ratchet.
  **Exact match, not `<=`** — a commit that removes duplication lowers the baseline in the same
  commit, which is how the win gets recorded instead of accruing as slack. Correct Step 0's table
  to the re-derived numbers.

**3. `feature/step-2-mvc-boundary`** — LANDED 2026-09-05. The headline metric; this reaching 0 *is* Steps 3–5 finishing.
- `chore(scripts):` `scripts/check_mvc_boundary.py`. Three rules: no View contains
  `global_signal.emit`; no View imports numpy/scipy/sklearn/hdbscan/pandas/**`fast_histogram`**/sqlite3;
  no Controller reads a `view._private`. `sqlite3` contributes 0 today (Views build SQL as
  f-strings) and stays as a ratchet. **Pin the rule's exact definition in the module docstring —
  the definition *is* the number**: `numpy.typing` counts as `numpy` for the pair count but as its
  own `ast.Import` node, and that ambiguity is what produced the unreproducible 21/12.
- `test:` `.mvc-boundary-allowlist.json` seeded at **107**, keyed by file and symbol rather than
  line number so ordinary edits do not churn it, plus the exact-match gate.
- `docs:` `changelog.md` and a `DECISIONS.md` entry recording the rule definition. (The
  106 → 107 correction is already applied above and in the Verification table.)

**4. `feature/step-2-characterization-goldens`** — LANDED 2026-09-05. Pins the surface
nothing tested.
`pytest-regressions` where the output is an array or DataFrame; plain explicit assertions for
scalars, strings and short tuples. Keep samples small so every golden stays well under
`check-added-large-files --maxkb=123`.
- `test(views):` the two `_logscale_*` filters and the five range helpers, in `tests/unit/utils/`.
  Pin the divergence Step 3d proposes unifying: `~np.isnan` masking vs `df.dropna()` (which also
  drops nulls in columns nobody asked to log), `return ()` vs returning the *original object* on
  empty, and the `astype(np.float64)` the frame version forces. Replace `test_protein_view.py:1138`
  `TestRangeHelpers`' `or`-chained assertions — `_shift_ranges` **reflects** rather than translates
  a multi-element range, which is unpinned.
- `test(views):` `_gaussian_fit`, `_get_baseline_stats`, `_gaussian`; correct the stale coverage
  roster at `test_raw_data_view.py:28`.
- `test(views):` `_summarize_vm`, all three branches.
- `test(views):` equivalence tables — three `_factors` copies (`MetaView.py:139`,
  `RawDataView.py:109`, `EventAnalysisView.py:121`) and three `format_axis_label` copies
  (`ProteinView.py:4037` module function, `MetadataView.py:3645` method, and the **inlined,
  genuinely divergent** `ClusteringView.py:731-742`, which does not strip a trailing `(...)` and
  accepts `"  "` where the others reject it). Pin the divergence so Step 3's merge is a decision.

Reuse `_qt_mocks.shadow_signals` and the `__new__`-bypass fixture (`test_protein_view.py:108-161`);
`tests/unit/views/conftest.py` gives dialog patching and widget/GC teardown free. **Do not mock
the view's `logger`** — it blinds `caplog`.

**5. `feature/step-2-refactor-coverage-audit`** — **the criterion branches 1-4 were not built
to.** They pinned what had *zero* behavioural coverage plus equivalence for the copies Step 3
merges. The standing criterion is wider and better defined: **every method the refactor moves
or deduplicates must be covered**, derived from the refactor's own lists rather than from a
judgement about which methods look thin.
- `chore(scripts):` an audit that enumerates the affected set and reports what is unpinned.
  The **deduplicated** half is machine-derivable - `scripts/measure_duplication.py` already
  names every method in every duplicate group, **66 distinct methods**. The **moved** half is
  prose in Steps 3d and 4a-4e below and has to be written out explicitly before it can be
  checked; that list becomes part of the audit's input.
- **Counting call sites is not measuring coverage.** `_logscale_and_filter_multiple_columns`
  had 38 references and every one was a `Mock`, so it looked covered and was not. The audit
  must discriminate direct calls on a real instance from mock substitutions, and a naive
  reference count scored 64 of the 66 dedup methods "covered" on exactly that flawed basis.
- Known already from a first pass: **`_on_sizes_checkbox_toggled`** appears in
  `test_metadata_controls.py:108` *only as a comment*, and **`notify_plugin_state_changed`**
  appears in `tests/` only as stub definitions. Both are real zero-coverage cases.
- `test:` close the gaps the audit finds, then check the audit in so Steps 3-5 cannot move or
  merge a method that nothing pins.
- **Progress 2026-09-05.** `scripts/check_refactor_coverage.py` and its tests landed on the
  branch (`af14745`); suite 3,151 passed / 2 skipped. First run: **284 targets, 273 pinned,
  11 runs only, 0 untested.** The 11 are five `notify_plugin_state_changed` (now closed,
  23 tests), two `_on_sizes_checkbox_toggled`, `check_column_exists`/`set_column_exists`
  (Step 3e), and `ProteinView._resolve_event_db_ids` / `RawDataView._start_eventfinder`
  (Step 4a). **All 11 are now closed**, with 71 new tests across four files:
  `test_plugin_state_notifications.py` (23), `test_controls_bins_validator.py` (9),
  `test_column_exists_relay.py` (10), plus `_resolve_event_db_ids` added to
  `test_protein_view_characterization.py` and `_start_eventfinder` to
  `test_raw_data_view_characterization.py`. **Decided 2026-09-05:** the gate is *split*. Its structural half
  runs under plain `pytest` everywhere (`tests/unit/scripts/test_refactor_coverage_gate.py`);
  its execution half runs where coverage already exists — `ci-internal-pr.yml` now emits
  `--cov-report=json` and invokes the script. Exit is strict: anything not `PINNED` fails,
  `RUNS ONLY` included. Reasoning in `DECISIONS.md` 2026-09-05.
  **Audit now reports 284 targets, 284 pinned.**

**Note on line coverage.** It is the wrong instrument for this and should not be used as the
audit's measure. The five Views were at 87-91% *before* any characterization test existed, and
adding them moved the numbers by at most one point - those lines already executed under the e2e
suite, and nothing asserted the values. Post-branch-4: Metadata 91%, EventAnalysis 87%,
RawData 88%, Protein 90%, Clustering 89%, `MetaView` 92%.

**6. `feature/step-2-sql-goldens`** — today **no test anywhere asserts on generated SQL text**;
all 110 tests in `test_meta_database_loader.py` use substring containment, so a refactor could
reorder joins, reassign aliases or change the projection and every one would still pass.
- `test(db):` exact-text goldens over `construct_metadata_query` (`:877`) across the shapes those
  classes already enumerate, pinning all three tuple elements.
- `test(db):` direct tests for `_split_on_opaque_spans` (`:712`), `_references_column` (`:763`),
  `_qualify_conditions` (`:785`), `_find_ambiguous_id` (`:835`) and `_end_of_subquery` (`~:695`) —
  **none has one**, and `_split_on_opaque_spans`' documented `"".join(result) == input` invariant
  is never asserted.
- `test(views):` the View-authored SQL, pinned *before* the refactor moves it into the loader —
  `MetadataView.py:2351`, `ProteinView.py:1778`, and `ProteinView.py:1957-1967`'s `scoped_query`,
  which appends a scope clause to arbitrary user SQL on a naive `"WHERE" in query.upper()` test.
  **Pin it and file it; do not fix it here.**

**7. `feature/step-2-tab-flows`** — five flows, load → filter → plot → export, asserting on
exported CSV content rather than widget state.
- `test(integration):` `tests/integration/flows/_triad.py`. **This rung does not exist**: the three
  existing `*_no_gui.py` build no View or Controller, and there is no headless triad fixture
  between the mock-only unit controller tests and the click-driven e2e suites. Build it from the
  e2e construction at `tests/e2e/raw_data/test_trace_load_navigate_psd.py:102-120`, driving the
  controller API directly instead of the menubar. Reuse `tests/integration/conftest.py`'s
  `sample_*` fixtures and the four currently-unused `make_synthetic_*` factories, and the
  `Type = None` wiring idiom at `test_raw_data_instantiation_pipeline_no_gui.py:69-86`.
- `test(integration):` one tab first, to prove the harness. Where a flow waits on writer output,
  wait on committed **rows** via `sqlite_row_count` (`tests/e2e/_helpers.py:410`), never on table
  presence — `DECISIONS.md` 2026-09-03.
- `test(integration):` the remaining four. The `integration` marker is applied by path; do not
  hand-apply it.
- `docs:` close out Step 2 here, in `changelog.md`, `DECISIONS.md`, `future_fixes.md`, and the
  artifact.

### Already in place — do not rebuild

- **`test_plugin_compliance` already covers the triad** (all three bases, 15 of its 71 tests). The
  real gap is that `MetaModel` has exactly **one** abstract method, which 4 of 5 tab Models
  implement as `pass`, so `[MetaModel-*]` passes no matter what the refactor does to the Model
  layer. The same equality comparison that binds the owner-held fitters applies to `MetaView`'s
  five abstract methods once Step 3 promotes into the base.
- **`tests/e2e/` is already a characterization net** — 16 files, 5,469 lines, a full flow per tab
  driven through clicks, naming almost no internal method. The exception is exactly what Step 4d
  moves: `subset_filters` in 4 files, `view._analysis_mode`/`_display_mode` in 2 more.
- **Destination coverage stays absent, by design.** `tests/unit/models/` holds 3 files, only
  `test_protein_model.py` (64 lines, 8 tests) covers a tab Model, and `MetaModel` (363 lines, 12
  methods) has no test file. Step 2 does not close that; the goldens make the move observable and
  the destination's coverage comes with the move, in Steps 3d and 4a–4e.

### Deferred out of Step 2 — file, do not fix

The 13 dead `sys.path` shims in the e2e modules (placed *after* the import they exist to enable);
`test_raw_data_view.py` and `test_metadata_view.py` mocking the view's `logger` against
`_qt_mocks.py`'s explicit warning; `tests/conftest.py:8-15` referencing a conftest deleted in
`c99249ea`; `ProteinView`'s naive `WHERE` substring test; and `ClusteringView`'s GMM branch
(`:660-670`), which has no extracted method to pin and gets one in Step 4c.

## Step 3 — promotion to `Meta*` bases

- **3a `MetaControls(QWidget)`** — highest value, independent of the test gate, **gated on
  ownership** (the five files are solely @Carogg28's and the shared code moves into Kyle's
  `poriscope/utils/`). Re-verified at `062ef6f`, where nine of thirteen sub-claims moved; the
  files are byte-unchanged since `fc4fdf7`, so every correction below was a measurement error.
  New file `poriscope/utils/MetaControls.py` (name is free; no `Meta*` enumeration needs it -
  `main_model.py:197-207`'s dict is data-plugin families plus the triad).
  - **444 removable lines, not ~590** — the 10 groups identical in all five files.
    `create_info_button` **29** L×5, `create_delete_button` **29** L×5, `create_add_button`
    **17** L×5 (Step 0's own table already said 29/29/17), plus **7** more, not 6. The
    remaining 197 of the family's 641 belong to 3b/3c or to 4-of-5 and 3-of-5 groups.
  - The **4 signals redeclared 5 times** holds, byte-identical including the trailing comment.
    Metadata and Protein carry two more (`edit_filter_requested`, `delete_filter_requested`)
    that are 3b-scoped.
  - The **duplicate `logger =` in 3 of 5** holds exactly (`clusteringcontrols.py:59`,
    `metadatacontrols.py:72`, `proteincontrols.py:71`).
  - `is_signal_connected` is **fully dead** — 5 definitions, 0 reads, 0 writes anywhere. Delete
    it; do not promote it.
  - `setupUi` is **523/438/235/222/107** and stays per-tab, decomposed into per-panel builders.
    `connect_signals` (18/26/57/61/43) is 5-way distinct and must stay per-tab too.
  - **Four things that stop this being "zero risk".** `createButton` is identical in 4 of 5 but
    EventAnalysis's copy omits `button.setStyleSheet("")`, so promoting the majority version
    changes EventAnalysis behaviour — almost certainly a no-op, but decide it rather than merge
    it silently. `update_filters` exists in 4 files under **incompatible contracts** (a plain
    `QComboBox` in EventAnalysis/RawData, a `MultiSelectFilterComboBox` in Metadata/Protein), so
    defining it on the base creates a silent override hazard — leave it to 3b/3c. Promoting any
    `@log(logger=logger)` method re-binds `logging.getLogger(__name__)` from the tab module to
    `poriscope.utils.MetaControls`, changing every record's logger name. And the autodoc
    generators emit **own methods only**, and skip classes with no docstring — none of the five
    has one — so ~50 `automethod` lines would vanish from the published docs with CI still green
    unless `MetaControls` gets a class docstring and its own page.
  - **Three near-misses the byte-identity measure cannot see**, worth ~45 more lines:
    `is_placeholder_item` (5 copies differing only in a string list → base method plus a
    `_placeholder_texts` attribute), `on_loader_changed` (3 copies differing only in the view
    name → a `_view_name` attribute), and `retranslateUi` (semantically `pass` in all five,
    four textual variants).
  - Only **12 test functions** touch anything 3a moves, all in
    `tests/unit/views/utils/test_metadata_controls.py` and `test_event_analysis_controls.py`;
    Protein, RawData and Clustering controls have no unit test file at all. Pulling a method up
    to a base preserves every `view.method(...)` call site, so **3a re-points no test** — but
    the duplication ratchet that would prove no copy was lost is Step 2's, which 3a precedes.
- **3a-bis `_set_control_area` as a `MetaView` template method** — separable from `MetaControls`,
  and **the recorded premise was wrong twice over**. The five bodies are in the *View* files, not
  the controls files, and they are pairwise distinct at 21/22/23/25/27 lines: Clustering has a
  stray blank line, EventAnalysis wraps one connect over three lines, and Metadata and Protein
  each add two filter connects. The stale comment naming `rawdatacontrols` is in **4 of 5** and
  genuinely stale in **3** (RawData's is correct; EventAnalysis's names its own widget).
  `MetaView.py:210` **already declares the hook `@abstractmethod`**, called once from
  `_setup_ui:690`, so making it concrete relaxes an ABC contract every subclass satisfies today -
  no break, but it is a contract change Decision C does not list, and the two docs tutorial
  examples (`HelloWorldView.py`, `SimpleCalcView.py`) override it, so the tutorial prose moves
  with it. Six tests call it directly, and the Metadata ones patch
  `poriscope.plugins.analysistabs.MetadataView.MetadataControls`, so any template method must
  preserve that patch target.
- **3b `MetaDatabaseTabView` + `MetaDatabaseTabController`** (Metadata/Protein) — largest
  cluster in the repo. **Blocked on 4d**: subset-filter state must find its layer first.
- **3c `MetaEventTabView`** (RawData/EventAnalysis). Both re-override `_factors`, shadowing
  the concrete base version they could inherit — delete those two.
  **Correction, 2026-09-05: `notify_plugin_state_changed` is NOT an instance of this.**
  `MetaView` declares it `@abstractmethod` (`:518`) and its docstring says it "must be
  implemented by subclasses, even if the correct" response is nothing, so RawData's and
  EventAnalysis's `pass` bodies are required by the ABC. Deleting them makes both classes
  uninstantiable. Asserted in `tests/unit/views/test_plugin_state_notifications.py` so the
  claim cannot be acted on by mistake.
- **3d** Move `_logscale_and_filter_multiple_columns` (`MetaView.py:696`) and
  `_logscale_and_filter_dataframe` (`:789`) — ~170 lines of pandas in a `QWidget` base — and the
  five event-index range helpers to `MetaModel`. Note this is `MetaView` → `MetaModel`, **not**
  View → Model: both already live on the base, which is why the first has 34 tests (all
  exercising it as a stub through `MetadataView`, one of them baked into the fixture 346 of 347
  tests use) and the second has none. Note the two logscale methods implement the same algorithm twice with different
  edge cases (`dropna()` vs array masking) — unifying is medium-risk, needs 2A coverage first.
- **3e** Remove tab-specific leakage: `MetaController.check_column_exists` and
  `MetaView.set_column_exists` are Clustering-only; `_setup_canvas`'s `num_channels` unused;
  `MetaView.lock` is a class attribute shared by every tab view guarding 1 of 4 accesses.
- **3f** Layering inversion: `views/main_view.py:53,58`,
  `views/widgets/add_subset_filter_dialog.py:30` and
  `views/widgets/clustering_settings_widget.py:52` import *up* from
  `plugins/analysistabs/utils/walkthrough*`. Move to `poriscope/views/widgets/`. **Gated on
  ownership like 3a** — `walkthrough.py` (495 lines) and `walkthrough_mixin.py` (387) are in
  the solely-owned directory, and `walkthrough.py` also holds `IntroDialog`, `Overlay` and
  `StepDialog`, each of which has its own autodoc page keyed off the module path. Make
  `WalkthroughStep` (a 4-tuple alias used across 8 modules) a frozen dataclass.
- **3g** `__init__` is byte-identical in all 5 Views (8 lines, `super().__init__()` +
  `_init_walkthrough()`). Delete; fold into `MetaView`/mixin.

## Step 4 — View code that is Model code

- **4a** The **75** emits become `self.call(...)` in the Model. Highest value in the refactor.
  Note the cost on the test side: `global_signal` appears in 142 test functions and **46 assert
  on the emit**, so those assertions are rewritten rather than re-pointed. The stale-read guard
  `062ef6f` left at `MetadataView.py:2334-2336` (clear the attribute immediately before the
  emit) is code this step deletes.
- **4b** SQL out of the widget: `_rebuild_event_id_cache` (`MetadataView.py:2039`,
  `ProteinView.py:1538` — 4 parameters now, not 5), `_resolve_event_db_ids`
  (`ProteinView.py:1731`), `_fetch_event_data` (`:1794`), `_build_load_event_data_args`
  (`:1908`), and `MetadataView.py:2351`'s raw `SELECT`. **`_build_where_clause` is gone** —
  `062ef6f` deleted it from both Views and routed both caches through
  `construct_metadata_query`, which is a large part of 4b already landed. (`DECISIONS.md`
  2026-08-25 accepts the f-string interpolation itself — this is about *where* the SQL lives.)
- **4c** Computation. Clustering is the pilot (`_update_clusters_hdbscan`,
  `_load_metadata_and_cluster`'s GMM, `_normalize_column_data` — 6 existing tests, no bus
  calls). Then Protein (`_double_gaussian`, `_fit_double_gaussian`,
  `_fit_and_sanity_check_double_gaussian`, `_compute_theoretical_blockages`,
  `_generate_vm_ensemble`, `_update_distribution_individual`, `_summarize_vm`), Metadata
  (`_calculate_heatmap`, `_construct_all_points_histogram`, `_construct_event_overlay`,
  `_plot_1d_density`, `_plot_capture_rate`, `is_categorical_type`), RawData
  (`_get_baseline_stats`, `_gaussian`, `_gaussian_fit`, the `histogram1d` binning).
  Does **not** reopen the 2026-08-25 double-Gaussian decision; `PeakFinder`'s copy is untouched.
- **4d** Domain state off the View: `subset_filters` (declared `MetadataView.py:152`,
  `ProteinView.py:232`), `_pending_filter_name`, `_pending_filter_text`,
  `_pending_old_filter_name` → Model. Removes the Controller-reaches-into-View-privates
  violation, which is **10 sites across two files**, not the one recorded:
  `MetadataController.py:199-200` and `:221-223`, **and `ProteinController.py:153-154` and
  `:175-177`**. Twelve further `self.view.subset_filters` / `restore_subset_filters` reach-ins
  across the same two Controllers move with them, and the `_private` rule will not flag those.
  This is the step that reaches her **e2e** suites. Resolve `hist_data`'s three shapes here
  (21 tests reference it, so those assertions change by design).
- **4e** File I/O: `_export_csv_subset`, `_save_filter`/`_load_filter`, `_commit_fits`,
  `_commit_clusters`, `_merge_clusters`. Keep `QFileDialog` path selection in the View.
  `MetaController.export_plot_data` is the precedent.

Stays in the View: matplotlib artists, axes/canvas lifecycle, widget state, file dialogs,
walkthrough step lists.

## Step 5 — outside the analysis tabs

Absorbs `future_refactors_and_features.md` Parts 5–12. Order: zero-risk deletions and
correctness issues, then mechanical extractions, then god-methods (coverage first).

- **5a data plugins (~1,000 lines).** `CUSUM`/`NoFitter` share 411 identical lines;
  `ClassicCUSUM` is a 195-line override differing in 2 → `CUSUM` + `_normalize_step_size()`;
  the two Chimera readers differ in 23 of 390; `_get_baseline_stats`/`_find_events_in_chunk`
  duplicated across two finders — **merge first, then fix the baseline-σ bug once**;
  `QObjectABCMeta`/`QWidgetABCMeta` 49 lines differing in 2 with dead `__new__` overrides;
  four `Meta*` bases carry a byte-identical 3,584-char `get_empty_settings` docstring.
- **5b `Meta*` internals.** Correctness first: `BaseDataPlugin.apply_settings` decides "is
  this a plugin instance" via `.get_key()` in a bare `except Exception`. Then
  `fit_events`' nine repeated reject blocks (`_reject_event` helper, ~35-40 lines);
  `find_events` reimplementing `reset_channel` inline (three copies of 10 lines — recorded as
  the safest finding in the part); `export_subset_to_csv`'s 4-step pattern ×5 (~65→~15 lines);
  `tuple_builder` defined three times. `MetaController`'s two ~60-line relay methods are
  **blocked on 4a** — most of that code is deleted rather than extracted.
- **5c app shell.** `DataPluginController.edit_plugin` (+ `_resolve_plugin_references` and
  `_check_key_available` extractions that shrink it); `MainView`'s 9 menu blocks + 8 handlers
  → table + `functools.partial` (~90→~25 lines); `switch_to_page` duplicating
  `clear_milestone_dialog`; `SettingsWindow`'s ~8 repeated row blocks and two mirror-image
  log-level dicts.
- **5d shared widgets.** `multiselect.py`/`multiselect_filter.py` ~90% duplicate — 8 methods
  copy-pasted, and demonstrably diverged (the redundant nested `if` and the false 3-way
  "select all" branch exist in both). **`DECISIONS.md` 2026-09-01 requires the event filter to
  stay on the application and records the load-bearing path as unexercisable on Linux CI —
  manual Windows check required.** Range parsing → `poriscope/utils/range_parsing.py` using the
  Tier B2 rulings. `dict_dialog_widget.on_ok`'s try/except type dispatch — but note
  `DECISIONS.md` 2026-09-01: that file has **no unit tests** and writing them is a prerequisite,
  not part of it. `clustering_settings_widget`'s three ~50-line row builders.

Constraints: `MetaEventFitter` changes force owner-held edits (check in first); the
`close_resources()` timeout was **built and reverted once** for a documented reason — the recipe
is in `future_refactors_and_features.md`, do not re-derive it; `BaseLineEdit` is re-exported
from `exposed.py` so changing it is breaking.

## Step 6 — scaffold and docs

- `scripts/new_plugin.py`'s analysis-tab half. **Generating a working ~100-line triad against
  the new structure is the acceptance test.** Re-run the four stub-body probes rather than
  reasoning about them (`pass` under a non-`None` return is mypy `empty-body`; a copied
  `:raises X:` above `pass` is DOC502; the same above `raise NotImplementedError` is DOC503;
  raising with no field is DOC501).
- Replace the stale `HelloWorld` example (4 of `MetaView`'s 5 abstract methods; imports
  `from utils.MetaView import MetaView`).
- Autodoc publishes 478 private methods across 1,119 `automethod` directives — omit privates.
- Update `quality_control.rst`; regenerate autodoc.

## Step 7 — release mechanics

- Breaking-change inventory in `changelog.md`, each called out explicitly, including every
  Decision C contract change.
- **Action history**: **5** `@register_action` sites over 4 names, replayed by name off the View. Keep them
  as thin View façades, or ship a name-migration map. Saved `.json` files are user data.
- **Session state**: `get_session_state` serializes `self.view.subset_filters`; verify against
  a real 1.x session file after 4d.
- `CITATION.cff`'s version is a hand-maintained copy of `constants.py`; `release.yml` never
  checks it against the tag.

## Verification

| Metric | Baseline | Target | Instrument |
| --- | --- | --- | --- |
| MVC boundary allowlist | **107** (75 emits, 22 imports, 10 privates) | 0 | `ast` test (Step 2 branch 3) |
| Duplicated lines removed | 0 of 1,199 (re-derived, baselined) | ≥ 2,500 | `scripts/measure_duplication.py` + ratchet |
| Analysis-tab coverage | unmeasured | ratchet up | `pytest-cov` (Step 0) |
| Numerical output | unpinned | unchanged | golden files (2A) |
| Minimal runnable triad | n/a | ~100 lines | `new_plugin.py` (Step 6) |

Full `pytest` green before every commit, no path arguments and no marker filter.
`pre-commit run --all-files` is the mypy gate. **Manual Windows pass** driving all five tabs
through the walkthrough plus the multiselect popup path — CI is Linux under Xvfb and
`DECISIONS.md` records that path as structurally unexercisable there.

**Baseline manual pass: run 2026-09-04, all clear.** All five tabs through the walkthrough; the
column and filter multiselect popups on both Metadata and Protein (open, select, deselect,
select-all, dismiss on an outside click, reopen with the selection intact); and no widget
outliving the app on close. That is the pre-refactor baseline, so a later failure is
attributable. **Re-run it after each structural step** — certainly after 3a, which rewrites all
five controls widgets, and after 3f, which moves the walkthrough modules.
