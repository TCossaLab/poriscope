# Poriscope 2.0.0 Refactor Plan

Approved 2026-09-03. **Step 0 and the whole of Step 1 (Tiers A, B2 and C) landed
2026-09-04** and are pushed; Step 2 onwards is open. 1.9.0 is ready and uncut.

**Every measurement below is re-baselined on `develop` at `062ef6f`, 2026-09-04.** Step 1
landed after the original `fc4fdf7` baseline (46 files, +416/-779 under `poriscope/`), so a
ratchet anchored there would credit Step 1's deletions to the refactor. Re-verifying this
document against `062ef6f` corrected nine of thirteen checkable Step 3a sub-claims, six Step 2
claims and the Decision E figure; the corrections are inline below.

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

## The ask to Carolina (blocks Step 2)

Decision E was recorded as a one-line ask about tests and stalled for a day because nobody
could state it precisely. It is one conversation with one person, in four parts, and three of
them are not about tests. Carolina González (@Carogg28) solely owns `tests/` and
`analysistabs/utils/`, co-owns `poriscope/views/` and `analysistabs/`, and authored 203 of the
~358 commits under `tests/` (59 against 22 in `tests/unit/views/`, 71 against 3 in
`tests/e2e/`). Paste-ready wording lives outside the repo in
`~/.claude/plans/carolina-2.0.0-ask.md`.

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

**If the conversation stalls, control reverts to Kyle and the work proceeds.** Ask first, and
say plainly in the plan and the commit trail that the owner was asked and did not engage -
`CODEOWNERS` is advisory by deliberate choice and Kyle has final say. An ownership block gets a
stated exit, not an indefinite hold.

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

**1,199 lines total.** The plan's ~1,900 and the >= 2,500 target both include
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

Re-verified at `062ef6f`; six claims moved and one bullet turned out to be already done.
Authorship of each deliverable is part of the ask to Carolina above.

- **Goldens** via `pytest-regressions` (`num_regression`/`dataframe_regression` compare float
  arrays with tolerances). **`pytest-regressions` is declared nowhere and is not installed**, so
  this is greenfield; declare it in *both* `pyproject.toml [dev]` and `requirements-dev.txt`.
  `pytest.ini` sets `--strict-markers`, so registering a `characterization` marker there is a
  hard prerequisite, not a nicety - an unregistered marker is a collection error. Drive
  computational View methods directly on a headless instance, fed from `tests/synthetic_data/`
  (five generators, present). **The mechanism is not what was recorded**: the `__new__` bypass
  lives in each test module's own `mock_view` fixture, and the load-bearing helper is
  `tests/unit/views/_qt_mocks.py`'s `shadow_signals`, which replaces every class-level `Signal`
  with a `FakeSignal` because a `__new__`-built view has no C++ QObject behind it. Verified
  empirically: `_init()`, a real computational method and a shadowed emit all work with
  `QApplication.instance()` still `None`. Two of the four files using the pattern import the
  shared helper; the other two roll their own. Its docstring's warning applies to goldens -
  **do not mock the view's `logger`**, it blinds `caplog`.
- **SQL goldens** across filter/experiment/channel/table shapes. **Re-target this**:
  `_build_where_clause` was deleted by `062ef6f` and has 0 references in `poriscope/` and
  `tests/`. Its "2 test hits" were both `mocker.Mock` *replacements*, so it never had
  behavioural coverage at all. The live surface is `MetaDatabaseLoader.construct_metadata_query`
  plus `_split_on_opaque_spans`, `_references_column`, `_qualify_conditions` and
  `_find_ambiguous_id`, which already carry substantial tests in
  `tests/unit/utils/test_meta_database_loader.py`. Precedent: the 2026-09-03 metadata-query fix
  was validated by diffing generated SQL across all seven branch shapes.
- **`ast` MVC boundary test**: no `analysistabs/*View.py` imports
  numpy/scipy/sklearn/hdbscan/pandas/**`fast_histogram`**/sqlite3; no View contains
  `global_signal.emit`; no Controller touches a `view._private`. **Add `fast_histogram`** -
  `RawDataView.py:34` imports it and Step 4c moves it, so the rule as first written would let
  4c's completion go unregistered. `sqlite3` contributes **0** (no View imports it; the Views
  build SQL as f-strings and hand it to the loader), but keep it in the rule as a ratchet.
  Allowlist seed at `062ef6f`: **106 entries** - 75 emits, 21 forbidden import statements
  (12 distinct View x module pairs), 10 private-access sites. The allowlist size is the headline
  progress metric.
- **Duplication ratchet** on byte-identical-method counts across the three 5-file families;
  Step 0's numbers, re-measured above, are the starting point.
- **One no-GUI flow per tab** in `tests/integration/flows/`: load → filter → plot → export,
  asserting on exported CSV content, not widget state. Survives the refactor unchanged by
  construction. **This is five new tests, not two.** The three flows there today are
  `*_instantiation_pipeline_no_gui.py` - they construct no View and no Controller and export no
  CSV, so by this bullet's own definition **0 of 5 tabs are covered**. When such a flow waits on
  writer output, follow `DECISIONS.md` 2026-09-03 (`SQLiteEventWriter`'s two-connection commit
  split): wait on committed **rows** via `sqlite_row_count`, never on table presence alone -
  note that helper currently lives at `tests/e2e/_helpers.py:410`, so it needs importing across
  trees or relocating.
- ~~Extend `test_plugin_compliance` to the analysis-tab triad.~~ **Already done** -
  `MetaController`/`MetaModel`/`MetaView` are in `META_CLASSES` and `BASE_CLASS_DATA`, and 15 of
  its 71 tests are the triad. The real gap is that the check is near-vacuous: `MetaModel` has
  exactly **one** abstract method (`_init`), which 4 of the 5 tab Models implement as `pass`, so
  `[MetaModel-*]` passes unchanged no matter what the refactor does to the Model layer. Worth
  keeping in mind that the same equality-comparison constraint that binds the owner-held fitters
  applies to `MetaView`'s five abstract methods once Step 3 starts promoting into the base.
- **Already-existing characterization net, worth not rebuilding.** `tests/e2e/` is 16 files /
  5,469 lines with a full flow per tab plus a CSV-export test, driven through clicks, so it names
  almost no internal method and survives Steps 3 and 4 by construction. The exception is exactly
  the state Step 4d moves - `subset_filters` in 4 files and `view._analysis_mode` /
  `view._display_mode` in 2 more.
- **Destination coverage is nearly absent.** `tests/unit/models/` holds 3 files, of which only
  `test_protein_model.py` (64 lines, 8 tests) covers a tab Model; there is no `test_meta_model.py`
  and `poriscope/utils/MetaModel.py` (363 lines, 12 methods) has no dedicated test file. That is
  where Steps 3d and 4a-4e land.

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
- **3c `MetaEventTabView`** (RawData/EventAnalysis). Both re-override `_factors` and
  `notify_plugin_state_changed`, shadowing base versions they could inherit — delete.
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
| MVC boundary allowlist | 106 (75 emits, 21 imports, 10 privates) | 0 | `ast` test (2B) |
| Duplicated lines removed | 0 of 1,199 measured | ≥ 2,500 | duplication ratchet |
| Analysis-tab coverage | unmeasured | ratchet up | `pytest-cov` (Step 0) |
| Numerical output | unpinned | unchanged | golden files (2A) |
| Minimal runnable triad | n/a | ~100 lines | `new_plugin.py` (Step 6) |

Full `pytest` green before every commit, no path arguments and no marker filter.
`pre-commit run --all-files` is the mypy gate. **Manual Windows pass** driving all five tabs
through the walkthrough plus the multiselect popup path — CI is Linux under Xvfb and
`DECISIONS.md` records that path as structurally unexercisable there.
