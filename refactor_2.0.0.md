# Poriscope 2.0.0 Refactor Plan

Approved 2026-09-03. Step 0 and Step 1's Tier C landed 2026-09-04; everything else is
open. Measurements taken on `develop` at `4fe1618`, re-verified at `fc4fdf7`.
Full write-up: <https://claude.ai/code/artifact/304ba119-d177-4918-90af-471d6de6bb80>

Excluded throughout by standing policy: `PeakFinder.py`, `Basic_PeakFinder.py`, `NanoTrees.py`.

## Why

The analysis-tab layer never grew a real Model, so the Views absorbed everything.

| Layer | Lines | Methods | Note |
| --- | --- | --- | --- |
| 5 tab Views | 11,541 | 260 | `ProteinView` 4,058; `MetadataView` 3,633 |
| 5 Controls widgets | 4,381 | 143 | all inherit plain `QWidget`; no base class |
| 5 tab Controllers | 1,417 | 81 | 114 `self.view.*` against 8 `self.model.*` |
| 5 tab Models | 303 | 7 | 4 of 5 are `def _init(self): pass` |

77 of 82 `global_signal.emit` sites are in Views, 0 in Controllers. Views import `hdbscan`,
`GaussianMixture`, `curve_fit`, `find_peaks`, `fast_histogram`, and author raw SQL.
~590 lines of byte-identical widget factories across the 5 Controls files; ~600 duplicated
lines *each* between `MetadataView` and `ProteinView`; 17 of 23 Metadata/Protein Controller
methods identical.

No characterization tests exist and coverage does not run (`pytest-cov` declared nowhere, so
`ci-internal-pr.yml` exits 4 on its test step).

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
- **E.** Moved tests are re-pointed mechanically (import/receiver only, assertions untouched),
  test owner reviews. **Needs her agreement before Step 2 starts.**

## Sequencing

Tab by tab. Clustering first (962 lines, self-contained, no bus calls in the hot path), then
RawData/EventAnalysis, then Metadata/Protein. Full suite green at every step; one feature
branch per piece, finished into `develop` before the next starts.

```
Step 0 (measurement) ──┐
                       ├──→ Step 2 (tests, GATE) ──┬──→ Step 3 ──→ Step 6 ──→ Step 7
Step 1 (1.9.0)      ───┘                           ├──→ Step 4
                                                   └──→ Step 5 (parallel)
Decision A ──→ Step 4a ──→ Protein threading fix, and Step 5b's relay extraction
Step 3a — independent of everything; safe first branch.
```

Hard blocks:

- Step 2 blocks Steps 3–5 absolutely.
- Tier A must land before goldens are generated, or goldens encode known bugs.
- Decision E must be agreed before Step 2 starts.
- Protein threading fix is already recorded as blocked on the emit-then-read conversion.
- `new_plugin.py`'s analysis-tab half is already deferred until this lands; it becomes Step 6.
- `@register_action` records `func.__name__` and `MetaView.update_actions_from_json` replays
  via `getattr(self, name)` **on the View**. 11 decorated methods; moving one breaks saved
  `.json` action files.
- Any `MetaEventFitter` signature change forces lockstep edits in the three owner-held
  fitters, because `test_plugin_compliance` compares annotations by equality. Check in first.

## Step 0 — measurement baseline (landed 2026-09-04)

Recorded on `develop` at `fc4fdf7`, full suite green (2,950 passed, 2 skipped, 213 s).
Re-run any row with the command beside it; these are the numbers Steps 3-5 are judged against.

**Coverage** — `pytest --cov=poriscope --cov-report=term-missing`. Repo total **83%**
(21,443 statements, 3,698 missed). Analysis-tab layer:

| Module | Stmts | Cover | | Module | Stmts | Cover |
| --- | --- | --- | --- | --- | --- | --- |
| `ClusteringView` | 358 | 89% | | `ClusteringController` | 55 | 100% |
| `EventAnalysisView` | 456 | 87% | | `EventAnalysisController` | 57 | 100% |
| `MetadataView` | 1,461 | 91% | | `MetadataController` | 136 | 96% |
| `ProteinView` | 1,597 | 90% | | `ProteinController` | 127 | 97% |
| `RawDataView` | 672 | 87% | | `RawDataController` | 56 | 100% |

The four empty Models are 12 statements each at 100%; `RawDataModel` is 40 at 88%. The
`Meta*` bases are the weak spot: `MetaWriter` 69%, `MetaReader` 71%, `MetaModel` 73%,
`MetaDatabaseWriter` 73%, `MetaEventFitter` 74%, `MetaEventLoader` 76%.

**LOC per layer** — `wc -l`. Views 11,541 (Protein 4,058, Metadata 3,633, RawData 1,715,
EventAnalysis 1,173, Clustering 962); Controls widgets 4,381; Controllers 1,417; Models 303.

**Byte-identical methods** — AST parse of each family, `ast.get_source_segment` per
function, dedented and stripped, counted where the identical text appears in more than one
file of the family. Removable lines = duplicate copies beyond the first.

| Family | Files | Methods | Identical bodies | Removable lines |
| --- | --- | --- | --- | --- |
| `*View.py` | 5 | 261 | 23 | 351 |
| `*Controller.py` | 5 | 81 | 20 | 207 |
| `*controls.py` | 5 | 145 | 25 | 641 |

**1,199 lines total.** The plan's ~1,900 and the >= 2,500 target both include
near-identical code this measure cannot see (`ClassicCUSUM`'s 195-line override differing in
2 lines, the Chimera readers differing in 23 of 390), so treat 1,199 as the *floor* the
ratchet starts from, not the whole prize. Largest single wins: `create_info_button` and
`create_delete_button` at 29 lines x 5 files each, `create_add_button` 17 x 5,
`update_channels` 52 x 2.

**Emit count** — `grep -rc "global_signal.emit" poriscope/`. 77 in Views
(Protein 22, Metadata 21, RawData 14, EventAnalysis 13, Clustering 7), 2 in
`MetaModel`/`MetaController`, 0 elsewhere. 79 total.

`pytest-cov==7.1.0` is declared, the stray `poriscope/pytest.ini` is deleted, and
`typing_extensions` is gone from all 38 modules and from `new_plugin.py`'s generated
template in favour of the native `typing.override` — verified by importing all 124
`poriscope` modules with `typing_extensions` blocked at the meta-path.

## Step 1 — Poriscope 1.9.0

Tier C landed 2026-09-04. Tiers A and B2 below were **re-verified at `fc4fdf7` and
rewritten**; the original lists were drafted from the 2026-08-25 audit and named work that
`0abd08c`/`41adc07` had already done on 2026-08-24. Do not re-derive them from an earlier
revision of the artifact.

### Tier A — before goldens are generated

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

### Tier B2 — smaller than advertised

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
  `tests/unit/views/widgets/test_time_widget.py:90-92` pins. Separately `:78` counts unfiltered
  empty segments, so the legal trailing comma in `"0-0,"` is wrongly rejected.
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

- **Goldens** via `pytest-regressions` (`num_regression`/`dataframe_regression` compare float
  arrays with tolerances). Register a `characterization` marker. Drive computational View
  methods directly on a headless instance — `tests/unit/views/_qt_mocks.py`'s `__new__`-bypass
  needs no `QApplication` — fed from `tests/synthetic_data/`.
- **SQL goldens** across filter/experiment/channel/table shapes. `_build_where_clause` has 2
  test hits today and is a 4b move target — highest value per line of test in the plan.
  Precedent: the 2026-09-03 metadata-query fix was validated by diffing generated SQL across
  all seven branch shapes.
- **`ast` MVC boundary test**: no `analysistabs/*View.py` imports
  numpy/scipy/sklearn/hdbscan/pandas/sqlite3; no View contains `global_signal.emit`; no
  Controller touches a `view._private`. Seed with today's violations as an allowlist; the
  allowlist size is the headline progress metric.
- **Duplication ratchet** on byte-identical-method counts across the three 5-file families.
- **One no-GUI flow per tab** in `tests/integration/flows/` (3 tests total today): load →
  filter → plot → export, asserting on exported CSV content, not widget state. Survives the
  refactor unchanged by construction.
  When such a flow waits on writer output, follow `DECISIONS.md` 2026-09-03
  (`SQLiteEventWriter`'s two-connection commit split): wait on committed **rows** via
  `sqlite_row_count`, never on table presence alone.
- Extend `test_plugin_compliance` to the analysis-tab triad.

## Step 3 — promotion to `Meta*` bases

- **3a `MetaControls(QWidget)`** — highest value, zero risk, independent; safe first branch.
  ~590 lines of byte-identical factories (`create_info_button` 31 L×5, `create_delete_button`
  31 L×5, `create_add_button` 19 L×5, plus 6 more), the 4 signals redeclared 5 times, the
  duplicate `logger =` in 3 of 5, the `is_signal_connected` class flag. The 5
  `_set_control_area` bodies are the same 11 lines — including a stale comment naming
  `rawdatacontrols` in all five — so that becomes a `MetaView` template method. `setupUi`
  (524/439/236/223/109) stays per-tab, decomposed into per-panel builders.
  New file `poriscope/utils/MetaControls.py`.
- **3b `MetaDatabaseTabView` + `MetaDatabaseTabController`** (Metadata/Protein) — largest
  cluster in the repo. **Blocked on 4d**: subset-filter state must find its layer first.
- **3c `MetaEventTabView`** (RawData/EventAnalysis). Both re-override `_factors` and
  `notify_plugin_state_changed`, shadowing base versions they could inherit — delete.
- **3d** Move `_logscale_and_filter_multiple_columns`/`_logscale_and_filter_dataframe`
  (~170 lines of pandas in a `QWidget` base) and the five event-index range helpers to
  `MetaModel`. Note the two logscale methods implement the same algorithm twice with different
  edge cases (`dropna()` vs array masking) — unifying is medium-risk, needs 2A coverage first.
- **3e** Remove tab-specific leakage: `MetaController.check_column_exists` and
  `MetaView.set_column_exists` are Clustering-only; `_setup_canvas`'s `num_channels` unused;
  `MetaView.lock` is a class attribute shared by every tab view guarding 1 of 4 accesses.
- **3f** Layering inversion: `views/main_view.py`, `views/widgets/add_subset_filter_dialog.py`
  and `views/widgets/clustering_settings_widget.py` import *up* from
  `plugins/analysistabs/utils/walkthrough*`. Move to `poriscope/views/widgets/`. Make
  `WalkthroughStep` (a 4-tuple alias used across 8 modules) a frozen dataclass.
- **3g** `__init__` is byte-identical in all 5 Views (8 lines, `super().__init__()` +
  `_init_walkthrough()`). Delete; fold into `MetaView`/mixin.

## Step 4 — View code that is Model code

- **4a** The 77 emits become `self.call(...)` in the Model. Highest value in the refactor.
- **4b** SQL out of the widget: `_build_where_clause`, `_rebuild_event_id_cache`,
  `_resolve_event_db_ids`, `_fetch_event_data`, `_build_load_event_data_args`, and
  `MetadataView.py:2347`'s raw `SELECT`. (`DECISIONS.md` 2026-08-25 accepts the f-string
  interpolation itself — this is about *where* the SQL lives.)
- **4c** Computation. Clustering is the pilot (`_update_clusters_hdbscan`,
  `_load_metadata_and_cluster`'s GMM, `_normalize_column_data` — 6 existing tests, no bus
  calls). Then Protein (`_double_gaussian`, `_fit_double_gaussian`,
  `_fit_and_sanity_check_double_gaussian`, `_compute_theoretical_blockages`,
  `_generate_vm_ensemble`, `_update_distribution_individual`, `_summarize_vm`), Metadata
  (`_calculate_heatmap`, `_construct_all_points_histogram`, `_construct_event_overlay`,
  `_plot_1d_density`, `_plot_capture_rate`, `is_categorical_type`), RawData
  (`_get_baseline_stats`, `_gaussian`, `_gaussian_fit`, the `histogram1d` binning).
  Does **not** reopen the 2026-08-25 double-Gaussian decision; `PeakFinder`'s copy is untouched.
- **4d** Domain state off the View: `subset_filters`, `_pending_filter_name`,
  `_pending_filter_text`, `_pending_old_filter_name` → Model. Removes the
  Controller-reaches-into-View-privates violation at `MetadataController.py:200-252`. Resolve
  `hist_data`'s three shapes here.
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
- **Action history**: 11 `@register_action` methods replayed by name off the View. Keep them
  as thin View façades, or ship a name-migration map. Saved `.json` files are user data.
- **Session state**: `get_session_state` serializes `self.view.subset_filters`; verify against
  a real 1.x session file after 4d.
- `CITATION.cff`'s version is a hand-maintained copy of `constants.py`; `release.yml` never
  checks it against the tag.

## Verification

| Metric | Baseline | Target | Instrument |
| --- | --- | --- | --- |
| MVC boundary allowlist | 77 emits + imports | 0 | `ast` test (2B) |
| Duplicated lines removed | 0 | ≥ 2,500 | duplication ratchet |
| Analysis-tab coverage | unmeasured | ratchet up | `pytest-cov` (Step 0) |
| Numerical output | unpinned | unchanged | golden files (2A) |
| Minimal runnable triad | n/a | ~100 lines | `new_plugin.py` (Step 6) |

Full `pytest` green before every commit, no path arguments and no marker filter.
`pre-commit run --all-files` is the mypy gate. **Manual Windows pass** driving all five tabs
through the walkthrough plus the multiselect popup path — CI is Linux under Xvfb and
`DECISIONS.md` records that path as structurally unexercisable there.
