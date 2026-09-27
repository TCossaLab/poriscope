# Future Fixes

Queued work and standing policy for the Poriscope codebase.

**Only future-facing work belongs here.** When something lands, delete its entry rather
than annotating it as done - the narrative belongs in `changelog.md`. When something is
settled as deliberately not worth doing, move the reasoning to `DECISIONS.md` and delete
the entry. Keep finished-work context only where an open item cannot be understood
without it. Keep entries terse: one to three lines, with the file:line and the measured
number, not the narrative.

Everything outside the tooling tiers is a logic change and needs an approved plan first.
Read-only investigation and measurement do not. Test-suite work is another developer's by
default, but tests for a mechanism you add are yours, and editing an existing test so it stays
relevant to a production change is expected.

**This file is the authoritative record of work to be done on the repository.** Entries sit
under the release they target - 2.0.0, 2.1, 2.2, Later, and Owner-held - grouped within each
by topic or by the review that found them. Move an entry between releases rather than
re-labelling it in place.

Sources: the 2026-09-24 whole-codebase review, seven parallel reviewers with claims checked by
execution (SWOT and roadmap: <https://claude.ai/artifact/NsZSdFtsenMyANLEDLWvKq>; items marked
*(by reading)* were derived from the code, not reproduced); the 2026-09-03 six-slice review
(<https://claude.ai/code/artifact/0886d408-06de-488d-8a8e-7f6a68206651>); and the 2026-08-25
structural audit (<https://claude.ai/code/artifact/a1bec2cd-a157-4299-acb3-a135738fee41>).
Line numbers were re-verified 2026-09-24.

## 2.0.0 - before the release ships

Silent data corruption, wrong science in the docs, user data loss, and release hygiene. Mostly small, local fixes.

Phase 1 (release prep) landed 2026-09-27; its plan is at
<https://claude.ai/artifact/NAGuHCf6pisqD47S9kmyDp>. Nothing else is queued against 2.0.0.

## 2.1 - trust the numbers

Accuracy tests against ground truth, reader and database correctness, type checking that sees the MVC layer, a Windows CI leg.

### The two filters share 16 byte-identical lines (2026-09-27)

`close_resources` and `reset_channel` are identical in `BesselFilter` and `WaveletFilter`,
8 lines each (the `filters` duplication family, measured on entry). Promote them to
`MetaFilter`.

### The API reference has no dead-link gate (2026-09-27)

`-W` passes while references are unresolved, because `conf.py` has no `nitpicky`. With `-n`
the build reports 1,463 warnings (1,503 before the 2026-09-27 base-link fix): about 1,350 are
numpy, pandas, Qt and typing names, which intersphinx plus `nitpick_ignore_regex` would clear,
and about 117 are ours across ~25 files - wrong-owner `:meth:` targets such as
`MetaFilter.apply_settings`, unqualified short names, and undocumented internal classes. Fix
ours, then turn `nitpicky` on so CI catches a dead link.

### A milestone blocks the page switch but not what caused it (2026-09-21)

Found during a manual pass; **pre-existing**. `MainView.switch_to_page:895` refuses to change
page (`:912`) while `_milestone_dialog` is up and the target is not `_expected_next_view` - but
every caller does its work *before* calling it, so the refusal comes too late to prevent
anything:

- `on_raw_data_view_click:611` and its twins `on_event_analysis_click:617` and
  `on_metadata_click:623` call `on_load_analysis_tab_button_click` first, which emits
  `instantiate_analysis_tab` - the tab is created and starts its own walkthrough - then
  `sync_sidebar_highlight`, and only then `switch_to_page`.
- `handle_menu_click:692` highlights before switching.
- `on_load_analysis_tab_button_click:714` highlights as well (`:722`), so the highlight moves
  twice.

Observed: during a milestone, clicking any sidebar button opens that tab and starts its
tutorial, and every menu stays live under the dimming overlay. The gate is in the wrong
layer - it guards the last step of an action whose earlier steps have already run. Fixing
it means asking "is this navigation allowed?" before the handler acts, not inside the
final call; the walkthrough and milestone guards at `switch_to_page:899-925` are that
predicate's body, so move them rather than copy them.

### The capture-rate plot always reports one row dropped (2026-09-14)

`MetadataController.fit_capture_rate:420` (`:472`) compares the surviving interval count against the
**event** count, so a column with no repeated timestamps still reports "1 rows dropped by
log filter" - n events make n-1 intervals by construction. Cosmetic, and preserved exactly
when the calculation moved from `MetadataView` to the Model so that the move changed
nothing the user sees; a test pins it as current behaviour. The fix is to compare against
`initial_length - 1`, and to delete that test with it.

### `MetadataModel.kernel_density` uses a deprecated SciPy namespace (2026-09-14)

`MetadataModel.py:297` calls `stats.kde.gaussian_kde`, which warns
"the `scipy.stats.kde` namespace is deprecated and will be removed in SciPy 2.0.0" on
every density plot. The fix is one line - import `gaussian_kde` from `scipy.stats` - and
the only reason it is queued rather than done is that it belongs with a test run that
exercises the density path rather than with an unrelated branch.

### The experiment/channel scope has three annotations for one value (2026-09-14)

The analysis-tab layer declares it `Optional[Dict[str, List[Optional[int]]]]` in **9**
signatures (`MetadataController.py:513/603/674/742`, `ProteinController.py:225/524/566`,
`MetaSubsetTabController.py:111`, `MetaSubsetTabModel.py:114`); `MetaDatabaseLoader` and its
neighbours declare `Optional[Dict[str, Optional[List[int]]]]` in **10**; and the selection
tree stores `Dict[str, Dict[str, List[str]]]` (`MetaSubsetTabView.py:203`), converted with
`int(selected_channel)` at `MetadataView.py:2009` and `:2114`. The producer at
`MetaSubsetTabView.py:789` builds `{exp: [channel] or None}`, so the loader's form is the
correct one and the tab layer's 9 are transposed. Invisible to mypy because the value is
passed through `call()`, which returns `Any`. Found writing tests against the loader's real
signature; not fixed with them, because it is a layer-wide annotation change rather than
part of pinning two methods.

### `SQLiteDBLoader` opens a fresh connection per schema lookup (2026-09-08)

`get_table_by_column:454` and `get_column_names_by_table:382` each call
`sqlite3.connect(self.db_path)` per invocation, with no cache. Measured: **10 connections
per `construct_metadata_query`** with a WHERE body, 4 without. Cheap on a local file
(1.5 ms/call, so 0.08 s to validate 50 filters) and not the cause of the filter-loading
pause, but the schema cannot change while a loader is open, so a dict cache built in
`_finalize_initialization` would remove all of them. Re-measure on a network-mounted
database before deciding it does not matter.

### Action history: record a declared action name, not a method name

**Deferred out of 2.0.0 on 2026-09-22** as its own feature design step rather than release
mechanics. `DECISIONS.md` 2026-09-17 settled *what* to do; what moved is *when*.

**5** `@register_action` sites over **3** names, all private, replayed off the View:
`_reset_actions` on `ClusteringView`, `MetadataView` and `ProteinView`, plus
`MetadataView._overlay_plot:1396` and `ProteinView._update_distribution_ensemble:1857`. Replay is
`getattr(self, name)` on the View via `MetaView.update_actions_from_json:389` (`:396`), so renaming a
decorated method breaks saved `.json` files today.

Saved action files carry **no compatibility obligation** (Kyle's ruling - the feature is
barely used), so the design is free:

- `@register_action("overlay_plot")` records a declared name instead of `func.__name__`.
- Replay dispatches through the registry those declarations build, not `getattr`, so an
  unknown action name is reported rather than called.
- Recorded arguments stay small and JSON-round-trippable - user intent, not bulk data.
- `register_action` (`LogDecorator.py:177`) has no docstring at all. Write the contract on it:
  the declared name, small recorded arguments, a body that is a pure function of them, and
  replay self-contained to its own tab.

Breaking, and to be called out as such whenever it lands.


### Other queued items

- [2.1] **Raw SQL subset filters can be saved but never plotted.** Six call sites refuse them
  (`MetaSubsetTabView._refuse_raw_filters:234`, called at `MetadataView.py:1409`/`:2067` and
  `ProteinView.py:1356`/`:1451`/`:1710`/`:1871`), because every plot path splices the filter in as a
  WHERE body. The design is settled (`DECISIONS.md` 2026-09-14): a raw filter goes to
  `query_database_directly` (`MetaDatabaseLoader.py:1416`) exactly as written, ignores the
  experiment/channel selection, and the user owns its projection - so a plot missing a column it
  needs must say which, not draw nothing. Clustering only gets this through the shared filter
  base queued under Later.
- **`format_axis_label` truncates a column name containing parentheses.** The pattern
  `\s*\(.*?\)$` is anchored at `$`, so the leftmost match wins and the lazy `.*?` expands
  across every intervening `)`: the strip reaches back to the **first** parenthesis, not the
  last. A column named `Rate (per pore)` plotted with unit `Hz` is labelled `Rate (Hz)`,
  silently losing `per pore`; `a (b) (c) (d)` collapses to `a`. Two copies,
  `ProteinView.py:2357` and `MetadataView.py:2822`; `ClusteringView.py:719-730`'s inline
  builder is unaffected because it never receives a label with a parenthetical. Behaviour is
  pinned in `tests/unit/views/test_duplicated_helpers.py:273-309`, so a fix must update those tests.
- **Two view test modules mock the view's `logger`**, which `tests/unit/views/_qt_mocks.py`'s
  module docstring explicitly warns against: `test_raw_data_view.py:85` and
  `test_metadata_view.py:152` (`logger = mocker.Mock()`). Their log assertions (8 and 2 sites)
  check calls on the mock, not what reaches a handler.

### Data integrity and scientific correctness

- **No test checks fitted values against ground truth.** Conformance asserts level
  counts only (`test_eventfitters.py:295`); there is no `CUSUM` unit test file, the
  ClassicCUSUM tests mock `_calculate_threshold`, and nothing pins the variance-reset fix.
  Plant levels in `synthetic_events_db` and assert current, blockage and duration within
  tolerance for CUSUM, ClassicCUSUM and NoFitter across SNRs and short events.
- **Conformance recipes never leave the happy path**: add multi-file sets.
- **`NoFitter` places event edges asymmetrically** (`NoFitter.py:226`): the start walks
  back to the baseline crossing, the end sits `rise_time` before the threshold crossing (838
  against 860 on a 40-sample ramp), so the overlay and `raw_ecd` shift left.
- **ABF conversion folds the offsets into the gain** (`ABF2Header.py:199-200`) instead of
  `raw*gain + (instOffset - sigOffset)`, and `TCossaLabABFReader:253` hardcodes offset 0.0.
  Latent: the synthetic ABF writer uses 0.0 offsets.
- **`MetaReader._set_sample_rate` checks only each channel's first file**, so a set whose
  files disagree on sample rate is read at the first file's rate.
- **`SQLiteDBLoader._load_event_data` drops an event on a NULL `padding_before`** via
  `try … continue`, logging only at INFO.
- **`IntraCUSUM` defaults make it count noise**: threshold and hysteresis both 0.0
  (`:89`, `:95`) scored 499 crossings on a clean single level (2 at T=200, H=20); nothing
  checks hysteresis < threshold.
- **`ClassicCUSUM` merges short levels on a median but reports them on CUSUM's
  single-sample fallback**, so the merge decision and the reported current use different
  estimators.
- **An event finder reports a multi-range channel finished after its first range**
  *(by reading)*: `_find_events_single_range` sets `eventfinding_finished[channel] = True` and
  yields 1.0 at the end of *every* range (`MetaEventFinder.py:609-610`), not only the last. While
  a later range runs, `get_eventfinding_status` says done, so the writer's gate
  (`MetaWriter.py:457`) lets a commit start on a partial event list, and
  `get_num_events_found` returns a partial count.

### Session and settings persistence

- **`apply_settings` assigns `raw_settings` before validating** (`BaseDataPlugin.py:422`),
  so a rejected edit leaves the rejected values on the plugin.
- **`MetaModel.run_generators` indexes `self.generators[key]` unguarded** (a `KeyError`
  in a slot if nothing was staged), and `set_generator` silently drops a generator for a
  running (key, channel) without closing it.

### Analysis tabs

- **`_shift_range_and_update_plot` is four copies in two drifted pairs.** Subset tabs
  (`MetadataView.py:1987`, `ProteinView.py:1157`): past the end, Metadata clamps and wraps to 0
  while Protein lands on `n_events`, and only Metadata says when no scope is selected. Event
  tabs (`RawDataView.py:461`, `EventAnalysisView.py:194`): only RawData tells the user it cannot
  shift below 0, and they catch different exceptions. Promote each pair to
  `MetaSubsetTabView`/`MetaEventTabView`, with `_get_event_index_text` (`RawDataView.py:528`,
  `EventAnalysisView.py:252`, differing only in the panel attribute).
- **`set_heatmap` passes bin centres as the `imshow` extent** (`MetadataView.py:985`),
  compressing the image by a bin width; its export cache (`:990-995`) is built in the View.

### Fitter performance and logging

- **`fit_events` logs noisily**: INFO `index/total_events` per event (`:557`), wrong for
  index subsets; the generic-exception branch interpolates the whole event dict, data included
  (`:636`); "No further warnings of this type" (`:627`) then warns every time.
- **`get_single_event_metadata` loads each event twice** (`MetaEventFitter.py:859-860`).

### Database

- **No indexes on the foreign-key columns** `data.event_db_id`, `sublevels.event_db_id`
  and `events.channel_db_id`: `construct_event_data_query` plans `SCAN d` + `SCAN s`, 0.16 s for
  5 events in a 16k-event, 203 MB database, linear in file size. `CREATE INDEX IF NOT EXISTS`
  needs no migration.

### Plugin contract

- **The compliance test checks only `__abstractmethods__`** (`test_plugin_compliance.py:43`),
  so overrides of concrete methods such as `load_data` go unchecked, and an
  `except (ValueError, TypeError): pass` skips a comparison silently.
- **Coordinate a run-wide "all channels finished" hook on `MetaEventFitter`** with the
  PeakFinder owner, so the barrier below is built by the base rather than raced in a
  per-channel hook. Breaking on a `Meta*` base.

### Types, tests and CI

- **The mypy hook's blindness hides real errors**: the project-venv run (mypy 2.3.1)
  reports 684, of which ~384 are Qt enum and untyped-import noise; the rest include 81 uses of
  `self.view`/`self.model` the controller bases never declare (`MetaController.py:81-92`), and
  `MetaReader._scale_data(dtype: Optional[str])` (`:955`) receives `np.float64` at all six
  reader call sites. Declare the attributes, fix the annotations, add a non-blocking
  project-venv report, and revisit `DECISIONS.md` 2026-08-24 with these figures.
- **Add a wheel smoke job**: build, install into a fresh venv, `import poriscope.exposed`,
  load the platform's wavelet binary. Pairs with the Windows CI entry.
- **Exact runtime pins in the wheel metadata** (`PySide6==6.9.0`, `numpy==2.2.6`, …)
  conflict with any other package in a user's environment; loosen to compatible ranges, add
  Dependabot for Actions and pip, and pin `pre-commit` in the workflows. The sklearn
  `force_all_finite` FutureWarning in `test_clustering_model` will fail on the next upgrade.

### From the 2026-09-03 review - high

- **`test_plugin_compliance` parametrizes from `__subclasses__()` at import time**, so which
  test doubles it audits depends on module import order. `pytest tests/unit/utils
  tests/unit/plugins` (inverted; `test_plugin_compliance.py:135-145`, `:268-273`) picks up `ConcreteDatabaseLoader`, `ConcreteEventFitter`
  and `MockEventLoader` and reports 4 failures that natural order never sees. Skip classes
  defined under `tests/`.
- **`INSERT OR IGNORE` turns a schema mismatch into a misleading rejection reason.**
  `SQLiteDBWriter._insert_event:787`/`_insert_sublevels:820` infer failure from `cursor.rowcount`
  (`:815`, `:873`),
  so a `NOT NULL` violation surfaces as `IOError("Cannot Overwrite Existing Event")`. Hit
  twice while building the writer-fix harnesses (metadata missing `channel_id`, sublevel
  missing `levels_left`). `OR IGNORE` is there to make a genuine re-write a no-op, so
  distinguish the two: check required columns up front, or use `ON CONFLICT ... DO NOTHING`
  on the uniqueness constraint only.
- **The writers have no tests of their failure paths.** `tests/unit/plugins/conformance/test_writers.py`
  (7 tests) drives both families through real chains on the happy path; nothing covers
  duplicate rows, a schema mismatch, abort, or the `rejected` bookkeeping.
- **`channel: Optional[int] = None` meaning "every channel" - deferred out of 2.0.0** (Kyle,
  2026-09-22). `MetaEventFitter.reset_channel:325-359` ignores `None` and writes
  `eventfitting_status[None]` behind four `type: ignore`s, each inside a `try/except KeyError`
  that `dict.pop(channel, None)` replaces (`:343-358`); `MetaEventFinder.reset_channel:172-195`
  writes the same ten resets twice, once per branch. `close_resources` is `pass` in 15 of
  18 overriding plugin files and the two SQLite writers ignore the argument. Scope, as designed 2026-09-22:
  - `close_resources`, `reset_channel`, `report_channel_status` take a required `channel: int`
    on the six channelled families, every `if channel is None` arm deleted; callers loop, as
    for `get_channel_length`. `MetaFilter` and `MetaDatabaseLoader` take no channel at all.
  - `MetaWriter`/`MetaDatabaseWriter` gain `get_channels()` from their finder/fitter;
    `BaseDataPlugin` stops declaring the three, since the signatures differ by family.
  - Whole-plugin callers - `DataPluginModel.unregister_plugin`/`handle_exit`,
    `DataPluginController:285`/`:828`, `PeakFinder:4786` - loop `get_channels()` or call bare
    by declared base. `BaseDataPlugin.__enter__`/`__exit__` have no users; delete.
  - `MetaDatabaseWriter._initialize_database`/`_write_experiment_metadata` go
    `Optional[int]` -> `int`; always called with a channel.
  - All 21 overrides change verbatim, including the three owner-held fitters (signature and
    docstring only). Breaking. Not in scope: `get_event_counts_by_experiment_and_channel`
    (SQL aggregate, no loop), `MetaModel.stop_workers` (app layer).
- **`ThresholdBlockageFinder`'s σ threshold is compared against a pA mean in the base loop.**
  `MetaEventFinder.find_events:453` skips a chunk when `mean < Threshold`, which is right for
  `ClassicBlockageFinder`'s pA threshold; at 8σ it skips only chunks with a baseline under 8 pA.
  A behaviour question, not a contract one - the key is declared on the base since 2.0.0.
- **`MetaEventFinder._fit_baseline_histogram:964` picks, windows and bins the baseline peak
  on rules nobody chose.** One piece of work, since each answer depends on the one before it;
  every σ threshold in every finder comes from this fit. Needs synthetic-data evidence, not a
  quiet edit.
  - *Peak:* `np.argmax(hist)` (`:1004`) follows the tallest bin, but the baseline is the fitted
    peak farthest from zero (Kyle, 2026-09-20). Baseline 1000 with a second population at 850:
    correct up to 49% occupancy of the lower one, then reports **852** from 55%. Needs a stated
    rule first - prominence floor, fraction of the tallest bin, or minimum separation.
  - *Window:* `hist[peak - half_width : peak + half_width]` (`:1028`) keeps one more bin below the
    peak. It helps only when the contaminant sits *above* the baseline; below it, σ is 1-4% worse
    in six configurations of 40 trials. Settle it after the peak rule (`DECISIONS.md` 2026-09-20).
  - *Bins:* `int(len(data)**(1/3)/2)` (`:994`) is 10 on a 10k-sample chunk, ~6 surviving the two
    windowing passes; the log-linearised fit is biased high at that few points, +2.3% at 10k
    falling to +0.2% at 1M. Rice's rule gives four times as many.
- **No schema version, and the compatibility check has a dead branch.** No
  `PRAGMA user_version` anywhere. `SQLiteDBLoader._finalize_initialization:1034-1039` guards
  `extra_tables` against `"event_counts"`, already in `expected_tables` (`:1004`) and so
  never present - net effect, any table a newer writer adds makes the loader refuse the
  file. `_ensure_event_counts:1089` uses `executescript` (`:1114`), which commits pending work and
  runs each statement unwrapped, so a failure leaves the table created but empty and the
  `table exists` guard (`:1105-1108`) never retries - every count reads 0 forever. It also runs a
  full-table aggregate on the GUI thread at plugin load.
  Store provenance (reader, filter and finder settings as JSON) alongside `user_version`, so a
  database says how its events were produced.

### From the 2026-09-03 review - moderate

- **`BesselFilter` uses the wrong filter form and guards it with a magic constant.** `:214`
  builds `(b, a)` and `:123` runs `filtfilt`, guarded by `if any(np.absolute(p) >= 0.975)`
  at `:95`. Measured against `sosfiltfilt`: at the allowed limit (Wn=0.02) `filtfilt(b,a)`
  already deviates by 6.3e-4 σ, and just past it by 22.6%. `output="sos"` + `sosfiltfilt`
  makes the guard unnecessary *and* unblocks the low cutoffs it rejects today (25 kHz at
  4.17 MHz is refused). Also `:188` makes the user re-enter `Samplerate` the reader already
  knows, so a mismatch silently mis-designs the filter.
- **Windows logging drops any record containing `μ`.** `main_app.py:226` constructs
  `logging.FileHandler` with no `encoding=`, so cp1252 cannot encode U+03BC and the record
  is discarded with `--- Logging error ---` on stderr (reproduced). Six sites write `"μs"`,
  including `metadata_units["duration"]` in both PeakFinders, which reaches the database,
  against 53 writing ASCII `"us"` - one physical unit with two spellings in the database.
- **Chunk boundaries can duplicate a sample through a float round-trip.**
  `MetaReader.continuous_read:386` converts an integer sample index to seconds (`:421-422`) and
  `load_data` truncates it back (`:159-160`, also `_read_bounds:369-371`); measured,
  `int((i/sr)*sr) != i` for 7.7% of the first 2M indices at 100 kHz, and when it slips low
  `i += len(data)` (`:428`) compounds it. Pass sample counts, or `round()`; name the unnamed
  tail-chunk test (`:416-417`) in the same change.
- **`SQLiteEventLoader` opens one connection per event** (`:126`, from
  `MetaEventLoader.get_event_generator:320` per index); `construct_metadata_query` opens ten
  connections for a single call, measured. No connection reuse and no `PRAGMA journal_mode`
  anywhere.
- **`columns.name` is globally `UNIQUE`** (`SQLiteDBWriter.py:616`) with `INSERT OR IGNORE`
  (`:721-729`), so a metric named identically in event and sublevel metadata registers once
  and `get_table_by_column` routes every query for it to the wrong table. Separately
  `level_id`/`levels_left`/sublevel `channel_id` are attached at runtime
  (`MetaEventFitter.py:710-717`) and never registered, so
  `construct_metadata_query(["level_id"])` raises.
- **`fit_events` turns plugin bugs into scientific rejection reasons.**
  `MetaEventFitter.py` has three `except ValueError`/`except Exception` pairs (`:622/631`,
  `:669/678`, `:730/739`) that route through `_reject_event:499`, keying on `str(e)`, so a `TypeError` from a plugin defect lands in the
  user-facing rejection table beside "Too Few Levels" and the channel still finishes with
  `eventfitting_status = True` (`:764`). Also `:641` checks `isinstance(..., Iterable)` then
  `:646` calls `len()` - a generator passes and dies on the call - and `fit_events(indices=[])`
  marks the channel fully fitted while the docstring at `:524` says it fits everything.
- **`get_single_event_data` returns `None` on a bad index** (`MetaEventFinder.py:815`) and
  `get_event_data_generator` yields it into the writer (`:728`), which then fails on it as a
  swallowed rejection. It should raise. The two methods also guard "are events ready" with
  different chains in a different order (`:711-724`, `:768-778`); only the generator checks
  `eventfinding_finished`. One shared guard, keeping which exception fires.
- **Silent scientific fallbacks with no metadata flag, in `CUSUM.py`.** For a sublevel
  shorter than `rise_time`: `sublevel_current` becomes the single last sample before the next
  level's onset instead of a median (`:439`), `sublevel_stdev` becomes `baseline_std` (`:467`), and
  `sublevel_blockage` becomes an unsigned max-absolute instead of a signed mean deviation
  (`:494-503`). The retry loop at `:371-373` fits different events in one channel at 1.5^0
  to 1.5^4 times the user's step size and records which nowhere. `:216`'s
  `np.std(data[-padding_after:])` returns the whole event when `padding_after == 0` and its
  sibling returns `nan` when `padding_before == 0`, poisoning `step_size` at `:222` (both
  verified). `Step Size` has no default and `_validate_settings` is `pass`, so `None`/`0.0`
  reach the division and every event is rejected with an opaque key.
- **`replace_raw_settings_option` is dead in practice.** `BaseDataPlugin.py:356-387` exists
  to track a parent rename into a dependency's `Options`, but both paths reaching
  `apply_settings` blank it first (`_swap_plugin_names_for_instances`, `DataPluginController.py:420`,
  from both `_resolve_plugin_references:385` and `_resolve_new_plugin_references:1009`), so it always
  returns at `if options is None`. Its covering test mocks the instance and asserts only
  that it was called, with fixture data production never produces.
- **`BaseDataPlugin.__init__` registers dependencies under an empty key.** `apply_settings`
  runs at `:114` before any `set_key`, so the scripted `Plugin(settings)` path records `""`.
  The GUI is safe (`DataPluginController.py:900`/`:914` sets the key first); the documented
  standalone path is not.
- **`edit_plugin` mutates the dependency graph partway through with a hand-rolled undo.**
  `DataPluginController._rename_plugin:221` re-points dependents one at a time
  (`_update_dependents_after_rename:299`) and calls `instance.set_key` (`:269`) only *after* the loop, so a mid-loop failure leaves some dependents
  pointing at a key that does not exist, logged per-dependent while the method continues.
  Wants validate-then-commit rather than compensating undo.

### From the 2026-09-03 review - CI, packaging and tooling (not logic changes - no plan needed)

- **`ci-internal-pr.yml:109-114` pushes from a detached HEAD.** `git add -A && git commit
  && git push` on a `pull_request` event, where `actions/checkout` leaves no branch to push -
  guarded by `if ! git diff --quiet`, so it only fires when the manual hooks change a file.
- **No Windows CI job.** Every matrix is single-entry and none runs `windows-latest`, so
  Linux takes the opposite branch from the shipped platform at the platform-conditional sites
  (10 of them) - including `WaveletFilter.py:181-182`'s `os.add_dll_directory`, in the one module
  that loads a native binary.
- **`release.yml` holds `contents: write` plus a PyPI OIDC token (`:12-14`) while calling five
  floating action tags**, three of them third-party, none SHA-pinned. It installs `mingw-w64`
  (`:101`) that nothing in the job uses, and runs no lint gate and no `twine check`.

### From the 2026-09-03 review - Found while verifying the 2.0.0 plan (2026-09-04)

- **`MetaDatabaseLoader.export_subset_to_csv:557` assumes one `data` row per event id, in order.**
  `data["filename"] = filenames` (`:682`) raises a length mismatch if the `data` table holds rows for
  only some of the selected events. An empty `data` table is now rejected explicitly; a
  partially-populated one is not, and the `IN (...)` query at `:655` has no `ORDER BY`.
- **`SQLitePeakDBLoader.get_plot_features:177` indexes `result.iloc[1]`** but the guard at
  `:154` only rules out zero rows, so a single-row result raises `IndexError`.
- **`SQLiteDBLoader._load_metadata_generator:848` returns bare on `sqlite3.Error`** (`:875-877`),
  which inside a generator is an ordinary `StopIteration` and so is indistinguishable from
  exhaustion. Same conflation the `None`-sentinel split fixed for `_load_metadata`
  (2026-09-04), but a generator needs its own contract.

### From the 2026-09-03 review - CUSUM follow-ons (the variance-reset fix landed 2026-09-03)

- **The C resets the counters on any threshold crossing; this implementation resets only on
  an accepted jump**, (`CUSUM.py:316`), so a crossing rejected by the `rise_time` guard still accumulates
  `varS` across the rejected boundary - the same bias the landed fix removed, just rarer. It
  also leaves `gpos`/`gneg` above threshold, so the next iteration re-detects and re-rejects
  the same jump. Moving to the unconditional form changes detection behaviour and needs
  validating against reference data first.
- **The `length - jump > rise_time` half of the C's edge guard is still missing**, already
  flagged by a comment in the loop (`CUSUM.py:302-303`). Adding it would suppress a transition detected too close
  to the end of an event, which the C refuses.

### From the 2026-08-25 structural audit

- **`apply_settings` aliases the settings dict it is handed, and session history holds the
  same object.** Do **not** fix this by copying at `self.raw_settings = settings` - measured,
  the alias is load-bearing. `DictDialog.__init__` aliases the dict it is handed and
  `get_result` returns that same object, so in `edit_plugin` `new_settings is app_settings`;
  `history["settings"]` therefore holds `app_settings`, filed into `plugin_history` by
  reference. `edit_plugin` then swaps plugin-typed `Value`s for live plugin instances, and it
  is `apply_settings` writing back *through the alias* that repairs the dict history holds.
  Copy there without first fixing that ordering and session history holds live `QObject`s for
  `save_session` to serialise. **Fix the ordering first, then the alias.**

## 2.2 - responsiveness and state

Tab state onto the Models, heavy work off the GUI thread, event-finder and CUSUM speed, splitting the large Views.

### Analysis tabs

- **`itertools.tee` buffers the whole subset, raw arrays included**
  (`MetadataModel.py:780`, `ProteinModel.py:583`): a 16 MB peak for 200 events of 80 KB. Use
  two queries or a streaming min/max.
- **Every read and compute path runs on the GUI thread**, not only Protein's: HDBSCAN/GMM
  (`ClusteringModel.py:193,223`, from `ClusteringController:110-122`), `load_metadata_subset`,
  all-points histograms and KDE. Workers are used only for writes and exports.
- **The View still owns domain state, and the Controller reaches into it**: public View
  dicts read and written at `MetaSubsetTabController.py:436,439,473` (invisible to rule 3,
  which keys on underscores); a matplotlib `Axes` passes through 7 Controller slots;
  `ClusteringView._merge_clusters:249-254` mutates the frame later committed, and
  `update_plot` mutates its argument (`:732-733`); `relay_query` opens a `QMessageBox` from the
  Controller (`MetaSubsetTabController.py:677`). Move scope, filters and the event-id cache onto
  `MetaSubsetTabModel`.
- **Plot types are bare strings repeated across View, Controls and Model** ("Heatmap"
  6 times in `MetadataView`) and persisted in saved action parameters; an enum would pin them.

### Fitter performance and logging

- **CUSUM costs 6.3 µs per sample, flat from 2k to 200k** (1.3 s for a 200k-sample
  event), holding the GIL, so per-channel threads give no multi-channel speedup;
  `IntraCUSUM.py:151` adds a second per-sample loop. JIT or C-port behind a golden ratchet.
- **Event finding costs events x chunk length**: `ClassicBlockageFinder._find_events_in_chunk:202,214`
  and `ThresholdBlockageFinder:149,157` recompute `data[index:] < threshold` over the rest of
  the chunk per event. 10 / 400 / 1,600 events at 4 MHz over 4 s took 0.27 / 1.47 / 5.04 s, 4.7 s
  of it in that function. Vectorise the crossings once per chunk.

### Left open by the 2.0.0 refactor (2026-09-22)

- **`MetaSubsetTabController.validate_raw_filter:574` still builds `f"{query} LIMIT 0"`**
  (`:606`) in the Controller. It stayed because no `MetaSubsetTabModel` existed; one has
  since 2026-09-17.

### From the 2026-09-03 review - high

- **The Protein tab blocks the GUI thread with no progress and no cancel.**
  `ProteinView._update_distribution_individual:1728` emits `distribution_fits_requested`,
  which runs `ProteinController.fit_distribution_events:350` -> `ProteinModel.fit_histograms:326`
  (`curve_fit` at `:153`/`:225`) and `sample_event_geometries:1001`, whose rejection sampler
  (`_generate_vm_ensemble:748`) is bounded at 200 x 50,000, over an unbounded event count -
  all as a same-thread call. No worker, progress or cancel in the triad; no `processEvents()`
  in `poriscope/`.

### From the 2026-09-03 review - moderate

- **The CUSUM family's duplication was never ruled on.** `eventfitters` is 193 removable
  (`measure_duplication.py --verbose`): `_populate_event_metadata` (72) and four `_define_*`
  (88) shared by `CUSUM`/`NoFitter` (`CUSUM.py:574,669-746`, `NoFitter.py:428,523-600`), plus 33
  of no-op stubs. `ClassicCUSUM.py:96`'s
  `_locate_sublevel_transitions` is a 202/205-line near-copy of `CUSUM.py:179`, 6 lines
  differing. It was booked as a floor with no recorded reason: rule on it or take it.
- **`format_axis_label` still exists in three places** - a module function at `ProteinView.py:2357`,
  a method at `MetadataView.py:2822` and inlined at `ClusteringView.py:729`. The behavioural drift is
  gone (2026-09-04); the refactor did not merge them, and no ruling says it should not.

### From the 2026-08-25 structural audit

- **Emit-then-read-an-attribute survives at six sites over typed signals.** Each clears the
  attribute, emits a `*_requested` signal, then reads the attribute the Controller's answer
  slot set: `MetadataView.py:1585-1593` (`plot_data`), `:1930-1933` (`column_type`),
  `:2156-2160` (`plot_events_generator`); `ProteinView.py:1344`, `:1804`;
  `MetaSubsetTabView.py:794-796` (`event_id_rows`). The other Views emit and let an answer
  slot do the work. It works only because View and Controller share a thread: every
  connection is the default AutoConnection (no `ConnectionType` anywhere in `poriscope/`), so
  moving a slot to a worker would queue the call and the read would get `None` - silently
  "no data" rather than loudly wrong.
- **Oversized units, measured 2026-09-24.** 13 functions exceed 300 lines, led by
  `metadatacontrols.setupUi` (523), `PeakFinder.report_channel_status` (472),
  `_classify_peak_prominences` (467), `proteincontrols.setupUi` (438) and
  `MetadataView._overlay_plot` (342); nine of the 13 are in the two PeakFinders.
  `ProteinView.py` is 2,363 lines across 51 methods; `MetadataView.py` 2,828 across 45.
  `MetaDatabaseLoader` declares 21 abstract methods over 1,578 lines, which is the real implementation burden behind the compliance gate below. The
  mechanical win is the `setupUi` methods - straight-line widget construction, extractable
  into per-panel builders without touching behaviour.

### Other queued items

- **`EventWorker`/`MetaModel`'s worker lifecycle has no test coverage**, nor does
  `App.configure_logger`; `tests/unit/utils/test_qt_handler.py` covers `QtHandler` only by
  calling `show_message_box` directly. Owed by whoever owns test-writing; the scenarios worth
  encoding are:
  - *Generator failure*: happy path, mid-run `TypeError`, abort, empty generator.
  - *Worker cleanup*: two independent runs to completion, each popped from
    `workers`/`threads`/`generators` without affecting the other, `deleteLater()` not raising.
  - *`QtHandler` through `emit`*: default `ERROR` level; DEBUG/INFO/WARNING raising no dialog;
    four distinct errors behind an open dialog all shown once the queue drains; the bare
    message under the real default formatter.
  - *Abort*: `MetaModel.stop_workers` logging INFO rather than WARNING for a stale key and no
    longer being silent for a stale channel; `MainController.handle_abort_all_analysis`
    reaching every open tab without `exiting=True`.
- **A worker blocked on a lock cannot observe an abort.** `Worker.stop()` (`EventWorker.py:142-144`)
  only sets `stop_requested` (read at `:99`), read on the generator's next turn, so a channel queued behind a
  serial-mode lock keeps waiting until it acquires. Pre-existing; per-instance locks shorten
  the queues but do not change this.
- **`hist_data` holds two shapes in `MetadataView`.** The three 1-D paths now all append a
  raw column array (`:509`, `:771`, `:839`); the all-points path appends an `(x, y)` tuple
  (`:1208`), down from four shapes. `ProteinView`'s copy holds only the tuple (`:784`). Typed `List[Any]` with
  a comment; unifying the last two is a real refactor.

## Later - worth doing, not scheduled

### Controller-side `call()` is a convention, not a checked invariant (2026-09-17)

`check_mvc_boundary.py`'s rule 5 (`plugin_reaches:531`) bans every route to a data plugin
*except* `call()`, and walks `tab_layer_modules()` as one set without asking which layer a
module is - so nothing distinguishes a Model making a plugin call from a Controller making
one. Measured 2026-09-24: **49 `self.model.call(...)` sites across the Controllers, 0 direct
`self.call(...)`, 7 in the Models** - the narrowness has held on review alone. Consider an
allowlist of named wiring operations for Controller-side `call()` before the accumulation is
real; latent today, and the same soft governance as `_get_plugin` staying private.

### Shell and shared-widget duplication (2026-09-27)

- `MainView` menu table: 9 `addMenu` + `add_plugin_actions` blocks at `main_view.py:420-467`
  and nine one-line `on_load_*` wrappers (`:558-714`).
- `MainView.get_milestone_step:1183` wraps each highlight getter in `lambda: [...]` and unwraps
  it with `[0]` on the next line (`:1190-1212`); store the getter. `populate_plugins_menu:641`
  mixes building the menu with 20 lines of anchor-position arithmetic (`:667-688`).
- `SettingsWindow` rows hand-built as HBox + widget + `add_horizontal_line()` in
  `add_general_tab_contents:504`, `add_advanced_settings_tab_contents:571`,
  `add_about_tab_contents:669`; two opposite 6-entry log-level dicts at `:771` and `:785`.
- `MultiSelectComboBox` and `MultiSelectFilterComboBox` still carry the same
  `updateSelectAllButton`, `selectAllToggle`, `getSelectedItems`, `_set_outside_click_filter`
  and `eventFilter` (`multiselect.py:129-250`, `multiselect_filter.py:124-300`), differing only in
  reading a check state off the item or off an embedded `QCheckBox`: a shared base with that
  accessor as its hook. Select-all's three-way branch has two identical arms in both and in
  `SelectionTree.py:169-186`; the Linux popup branch is written as two `if`s (`multiselect.py:62`,
  `:72`) and again at `SelectionTree.py:213`. An empty `MultiSelectComboBox` shows "Deselect All"
  checked, since `checked == total == 0`; `SelectionTree` special-cases it.
- `dict_dialog_widget.on_ok:368` dispatches by nested `try/except AttributeError` probing;
  `init_ui:111` (136 lines) builds its Input File and Output File rows identically but for the
  picker called (`:131-168`).
- `clustering_settings_widget` builds its column rows three times (`:314`, `:397`, `:525`), and
  `init_ui` restores a preselected config inside one broad `except Exception` (`:211-236`).
- `icon_menu_widget`/`text_menu_widget`: `emitSignal` identical but for the `"menu"` key
  (`icon_menu_widget.py:295`, `text_menu_widget.py:276`), six `set*Checked` slots each, and
  `QPushButton:hover` QSS six times. Share the constants and those methods, not the classes.
- `FloatRangeLineEdit.set_range` counts decimal places with the same inline expression twice
  (`float_range_line_edit.py:144-153`).

### The two Chimera readers are near-identical, and the deprecation resolves it

`ChimeraReader20240101` and `ChimeraReader20240501` differ in **27 lines of ~396**. The only
real difference is `_get_configs`: 2024-01 parses a JSON header embedded in the `.log` file,
2024-05 reads a companion `.json` of the same stem. Everything else - `_map_data`,
`_get_file_pattern`, `_get_file_time_stamps`, `_get_file_channel_stamps` and `_convert_data`
- is byte-identical, and the pair is the largest single contributor to the `datareaders`
duplication figure (401).

**Do not give them a shared base.** `ChimeraReader20240101` is slated for deprecation in a
future cycle (Kyle, 2026-09-22), so making the surviving reader subclass it - the
`LegacyElementsReader(TCossaLabABFReader)` pattern this family already uses - would mean
unpicking the inheritance before anything could be deleted. Deprecating 20240101 removes the
duplication for free, and should take `datareaders` to roughly 100.

If it has to move sooner, the direction is the other way round: `ChimeraReader20240501`
absorbs what it needs and stands alone, leaving 20240101 a clean deletion.

### Session and settings persistence

- **Load Actions has no shortcut to the autosaved `session/tab_action_history.json`**: the
  user must find it in the app-data folder. Replay stays explicit and per tab by design
  (`DECISIONS.md` 2026-09-27), so this is a convenience - offer the autosave in each tab's
  Load Actions - not automatic replay.
- **A reloaded session restores plugins but not what the control panels showed.** Snapshot and
  restore each panel's widget state on `MetaControls` by walking its children keyed by
  `objectName` (not every control sets one today), with `MultiSelectComboBox` and
  `MultiSelectFilterComboBox` supplying their own get/set; modal dialogs stay out of scope. A
  direct snapshot, not an event-sourced log like `@register_action`. Restore with signals
  blocked, after the tab's plugins exist and before any replay is offered (`DECISIONS.md`
  2026-09-27: replay stays explicit and per tab). Replay itself is a synchronous loop on the GUI
  thread (`MetaView.update_actions_from_json:389`), so a heavy log wants a worker.
- **`@register_action` has no overwrite mode**: every call appends (`MetaController.py:391`),
  so an action whose final call is all that matters is replayed once per intermediate call.
  Decide the dedup key (name alone, or name plus identifying arguments) and whether a
  replacement keeps its position before building it, alongside the declared-name redesign
  in 2.1.

### Numeric input and widgets

- **Three validation stacks behave three ways**: `NumericLineEdit` disables OK without
  naming the field, `BaseLineEdit` traps focus (`event.ignore(); self.setFocus()`,
  `BaseLineEdit.py:82-86`), and the bare Qt validators check no range.
- **`get_icon` rasterises SVGs at 16x16 before scaling** (`configs/utils.py:167`),
  blurry on HiDPI; its "cleared on each process start" comment (`:46-48`) is false.
- **Walkthrough tidiness**: two positioners fight over the card (the card jumps from
  (469,153) to (113,194)); closed `StepDialog`s are never deleted (3 after three runs); a
  `cast()` at `walkthrough_mixin.py:143-150`; dead `QDialog` fallbacks at
  `walkthrough.py:481-495`; `show_walkthrough_intro` (`:314-328`) is dead and would crash; the
  intro text (`walkthrough.py:111`) omits Protein.
- **Popup tidiness**: `SelectionTree.show_dialog` has no Cancel; select-all in the filter box
  emits `selectionChanged` N+1 times; the popup lists hide their scrollbar (`multiselect.py:58`).
  The duplication itself is under "Shell and shared-widget duplication".
- **No accessibility work**: no accessible names, `QShortcut`s, mnemonics or tab order
  anywhere in `poriscope/`; sidebar colours hardcoded (`icon_menu_widget.py:72-80`,
  `text_menu_widget.py:79-86`); Windows-only fonts hardcoded 7 times.

### Analysis tabs

- **`new_plugin.py` cannot generate a `MetaSubsetTab*` tab**, the likely shape of any
  new database-analysis tab; add `--base subset`.
- **`update_available_plugins` is hand-written in all five Views** (`ClusteringView.py:813`,
  `MetadataView.py:1333`, `ProteinView.py:1008`, `RawDataView.py:376`,
  `EventAnalysisView.py:136`): `super()`, then a `try` pushing each metaclass list into the panel.
  Metadata's and Protein's are identical but for the panel attribute, so `MetaSubsetTabView` can
  own them through `_subset_controls`.
- **`get_save_filename` is four identical bodies** (`ClusteringView.py:143`, `RawDataView.py:141`,
  `EventAnalysisView.py:119`, `MetaSubsetTabView.py:899`), all reached from
  `MetaController.py:170`; it belongs on `MetaView`.
- **The "my selected loader gained columns" guard is written twice**:
  `ClusteringView.notify_plugin_state_changed:831` and `MetadataView:1357` (Protein's is a no-op).
- **Overwriting committed columns is built twice**: the confirm (`ClusteringView.on_cluster_column_checked:286`,
  `ProteinView.confirm_fit_commit:477`) and the drop (`ClusteringModel.drop_cluster_columns:244`,
  `ProteinModel.drop_fit_columns:360`); Protein's `drop_fit_columns(loader, table, columns)` is
  already the general form. Protein's prompt reads "fit data data already exists" (`ProteinView.py:500`).
- **Figure reset differs per tab**: `ClusteringView._reset_actions:161` guards `figure.clear()`
  with `except AttributeError` where Metadata has `_clear_figure_state:315`/`_axes_valid:355`, and
  `ProteinView._reset_actions:671` runs clear/add_subplot/tight_layout/draw twice, once per figure
  (`:687-705`).
- **A repeated column is refused two ways**: Clustering raises `KeyError`
  (`ClusteringView.py:546`), logged at ERROR by its caller after the config is already saved
  under its title; Metadata warns in a `QMessageBox` (`MetadataView.py:1567`) and its panel
  already disables Update Plot (`metadatacontrols.py:865-871`). The clustering dialog's
  `_check_apply_enabled:569` could refuse it the same way.
- **`MetaEventTabController.update_available_plugins:68` re-implements the base** with the Model
  pushed before the View (`MetaController.py:353` does View first). Nothing in the tab layer reads
  `MetaModel.available_plugins` (`MetaModel.py:348`), so the override is a debug log; delete it.
- **Clustering has no named-filter layer**: one anonymous `QTextEdit`
  (`clustering_settings_widget.py:132`), validated only at apply, where Metadata and Protein name,
  save, reload and multi-select filters through ~16 methods on `MetaSubsetTabView` (1,098 lines,
  31 methods). Validation is already shared (`construct_metadata_query`). Putting
  `ClusteringView` under `MetaSubsetTabView` would inherit its scope and event-cache state, so the
  shape is a thin base holding only the filter dict, the add/edit dialogs and save/load, under
  both. Worth it when raw SQL filters are built, or Clustering keeps refusing a `SELECT`.

### App shell and plugin management

- **The plugin-name uniqueness loop is written twice**: `DataPluginController._rename_plugin:254-264`
  and `_key_is_unused:952`, differing only in the rename also restoring parent links.
- **Deleting from the edit dialog** (`_complete_requested_deletion:173`) re-implements
  `delete_plugin:606` and posts no "deleted" message to the panel.
- **`instantiate_analysis_tab` wires seven tab signals as seven `connect` calls**
  (`main_controller.py:572-596`); `MainView.connect_signals:225` already has the table form.
- **`sys.path` only grows**: `update_user_plugin_location` (`main_controller.py:197-201`) and
  startup (`main_app.py:122-125`) append the plugin folder and its parent and never remove a
  previous one, so after the folder changes an abandoned folder's module still wins a name clash
  until relaunch.

### Base-class internals

Readability only; each is behaviour-preserving and wants the covering tests read first.

- `LogDecorator.log`'s one-shot latch is the same block in `log_call` and `log_return`
  (`LogDecorator.py:119-127`, `:134-142`). One helper over a module-level latch also retires the
  two `setattr`s `DECISIONS.md` 2026-09-02 keeps.
- `MetaController.update_tab_actions`' undo walks back through nested `try/except
  KeyError`/`StopIteration` (`MetaController.py:392-411`); `handle_kill_worker:245` nests three
  deep; `MetaView.update_progressbar:315` (74 lines) builds its widget inline; `MetaModel`
  repeats `if key not in self.<dict>` four times (`:205-239`).
- `MetaEventFinder`: boundary reconciliation is duplicated in `find_events:339-356` and
  `_find_events_single_range:578-594`; four comprehensions test `idx not in bad_indices` against
  a list (`:549-564`, quadratic - use a set); the `end is None or end == 0` re-check at `:300`
  cannot fire after the normalisation at `:276-289`.
- `MetaEventFitter.fit_events` coerces `padding_before` and `padding_after` with the same seven
  lines twice (`MetaEventFitter.py:584-598`).
- `MetaReader._get_file_index:855` ends its scan by catching `IndexError` (`:868-872`);
  `bisect_right` says what it means.
- `MetaDatabaseLoader`: the experiment/channel scope clause is hand-built three times
  (`:499-501`, `:1131-1133`, `:1230-1232`, only the last alias-qualified), and
  `export_subset_to_csv:557` repeats validate/query/raise five times (`:601-670`).

### Database

- **34 hand-rolled `sqlite3.connect`/`finally` blocks** across the four SQLite plugins,
  and `lookahead_generator` nested twice (`MetaWriter:390`, `MetaDatabaseWriter:121`) in two
  near-copy write loops. `MetaWriter._commit_events:373` is 164 lines with an abort flag threaded
  through four `try` levels; `MetaDatabaseWriter.write_events:107` repeats
  try/`close_resources`/log/raise for three setup steps (`:137-172`), and its `index = 0`
  (`:182`) is dead - `:196` reassigns it before any read.

### Plugin contract

- **`_validate_param_ranges:559` rejects any `None`**, so a plugin cannot declare an
  optional parameter.
- **Nothing bounds a plugin's `close_resources()`**: Reset Session and quit call it unguarded
  (`DataPluginModel.py:217`, `:239`), so one that hangs freezes the app without naming itself,
  and its contract says only "gracefully close" (`BaseDataPlugin.py:135`). A threaded timeout
  was built and reverted (`DECISIONS.md` 2026-08-31): doing it means `check_same_thread=False` on
  the two writers' `self.conn` (`SQLiteDBWriter.py:299`, `SQLiteEventWriter.py:580`), the quit
  path routed through the same guard, and the contract written down - join your threads, close
  your handles, idempotent, callable from another thread. Lands with or after the
  `channel: Optional[int]` item in 2.1.

### Types, tests and CI

- **Mocks are almost all unspecced**: 677 bare `Mock()`/`MagicMock()` against 10
  `spec`/`autospec`; 556 tests assert only `assert_called*` and 118 assert nothing. Adopt specs
  one fixture file at a time, controllers and views first.
- **Coverage cannot see QThread code** (no `.coveragerc`, no `concurrency`), so
  `EventWorker` (51%) and the writers (60-69%) read lower than they are.
- **A root `__init__.py`** has been tracked since the initial commit; harmless only
  while `tests/` has none.

### Docs and records

- **Split `DECISIONS.md` into active and archive**, so a session loads only the decisions
  that still apply (27.8k words today).

### Left open by the 2.0.0 refactor (2026-09-22)

- **`WalkthroughStep` is a positional 4-tuple** (`views/widgets/walkthrough_mixin.py:40`),
  built as 90 literals across 7 files. A frozen dataclass names the fields; moves no gate.

### From the 2026-09-03 review - high

- **The two multi-select popups disagree about Linux.** `MultiSelectComboBox.__init__`
  builds a frameless `QWidget` popup on Linux and a `QDialog` elsewhere;
  `MultiSelectFilterComboBox.__init__` builds a `QDialog` on every platform, so the filter
  picker never got the Linux treatment (`multiselect.py:62-66`, `multiselect_filter.py:67`).
  Both `__init__`s were left untouched by the popup deduplication precisely because reconciling them changes behaviour on a path CI cannot
  exercise (`DECISIONS.md` 2026-09-01). Needs a Linux check and a manual Windows pass, not a
  code reading.

### From the 2026-09-03 review - moderate

- **Severity is doing double duty as the UI's interruption policy.** `QtHandler` is attached
  to the root logger with no name filter, so any third-party library logging at ERROR pops a
  dialog at the user. Code is now written to game it: `main_model.py:210` chooses ERROR
  *because* it raises a dialog, `EventWorker`'s docstring explains that the progress bar must
  be emitted before the ERROR log or it strands behind the dialog, and
  `MainModel.update_logging_level` special-cases skipping the handler. The fix is to separate
  "how loud is this" from "should this interrupt".
- **Parameter semantics are encoded in the parameter's display name.** Verified: renaming a
  parameter to `"Data File"` makes the same dict raise
  `ValueError: Data File must be one of ['Chimera Logfiles (*.log)']`. `FILE_DIALOG_PARAMS`
  exists for this and is used twice while `dict_dialog_widget.py:216,370` hardcodes the
  literal list. Also `_validate_param_types` is strictly nominal: `Type: float` rejects an
  integer `5` while `Type: int` accepts `True`. **See `DECISIONS.md`** - the
  `"Validate Options"` flag is rejected, and the `"Kind"` key that was the recorded better fix
  was dropped from 2.0.0.
- **`MainView`'s navigation state is a QLabel's rendered text.** `get_current_view:1080`
  returns `self.page_title_label.text()`, keyed into `self.pages` at `:1052` to decide
  whether to launch a walkthrough (`get_walkthrough_steps:1006` reads the label directly too);
  the label starts as `"Home"` (`:749`), in neither, so the app logs a misleading "does not
  support walkthrough" before the first switch. The five tab Views do this correctly with a
  hardcoded literal.
- **~75 attributes are assigned only outside `__init__`** across the five Views (not re-measured since 2026-09-04), with 14
  guards papering over it (2 `hasattr`, 12 `getattr(self, ..., default)`, measured 2026-09-24).
  `ClusteringView.axes` is the clearest case,
  assigned only in `_reset_actions:176/178` and read unguarded at `:735`/`:758`, though it is
  latent: both reads are immediately preceded by a `_reset_actions()` call, and `update_plot`
  carries no `@register_action` so replay cannot reach it out of order. Fixing it properly
  means an `Optional[Axes]` declared in `_init` plus handling at both reads. **`ProteinView.ax_hist`/`ax_vm`
  are not instances of this** - both are properties over axes built eagerly by
  `_set_custom_display_area`, which is on the construction path.
- **`MetaFilter.force_serial_channel_operations` is unenforceable.**
  `get_callable_filter:95` hands out `self.filter_data` as a bare bound method invoked
  inside another plugin's generator, and `@serialize_channels` is restricted to generator
  functions. Either delete the declaration for this family or route `filter_data` through
  the guard.

### From the 2026-09-03 review - CI, packaging and tooling (not logic changes - no plan needed)

- **No pip cache in `ci-internal-pr.yml` or `release.yml`**, and `ci-branches.yml:102` runs
  `pre-commit clean`, discarding the hook-env cache every run.
- **`black` runs only at the manual pre-commit stage**, so formatting is enforced by CI
  rewriting contributors' commits rather than by failing them.
- **`scripts/new_plugin.py`'s two base-class tables are guarded one-directionally.**
  `tests/unit/scripts/test_new_plugin.py` asserts each `FAMILIES` and each `TRIAD` entry
  appears in `main_model.py`, not the reverse, so adding a twelfth `Meta*` base leaves the
  generator and `--list` silently blind with no test failing. Both guards are also regexes
  over another file's source text, so reformatting `main_model.py`'s dict breaks them
  spuriously.

### From the 2026-09-03 review - Docs

- **Two `Meta*` bases carry a byte-identical 3,584-character `get_empty_settings`
  docstring** (`MetaDatabaseLoader.py:296`, `MetaEventLoader.py:105`), and
  `MetaEventFitter.py:167` holds a 3,865-character near-copy that has already drifted.

### From the 2026-08-25 structural audit

- **Routine states still logged at `WARNING`.** 111 `logger.warning` + 13
  `logger.exception` sites under `poriscope/` (2026-09-24). **None interrupts anyone**, since `QtHandler`
  floors at `ERROR`, so this is a log-signal problem and deliberately not urgent. Families
  worth working from:
  - Per-event/per-channel "skipping"/"proceeding without" notes at WARNING from inside
    worker generators: `RawDataController.py:408`, `EventAnalysisController.py:175`,
    `ProteinModel.py:654`, `MetaEventTabController.py:109`, `RawDataModel.py:101, 109`,
    `MetaDatabaseWriter.py:186`.
  - "No selection"/"select only one" user guidance at WARNING: `RawDataView.py:557`,
    `MetaSubsetTabView.py:1059`, `ProteinView.py:1765, 1920`, and `"No column names
    received"` at `ClusteringController.py:345` and `MetaSubsetTabController.py:400`. These
    belong on the panel rather than in the log at all.
  - `DataPluginController._report`/`_report_and_restore` (`:257`, `:478`, `:980`), which emit
    to the panel *and* log, are the model for the intended pattern.
  Deliberately staying at `ERROR`, so do not "finish the job" on these: `main_model.py:216`'s
  plugin-import failure and `SQLiteDBLoader.py:604`'s missing `id` column.
- **The plugin loader executes modules before knowing they are plugins.** `load_plugin`
  calls `exec_module` (`main_model.py:180-184`) on every `.py` file before checking whether it
  holds a plugin (`:193-205`), so a
  helper module executes during discovery and reports as a plugin failure if it raises; and
  it never registers modules in `sys.modules`, so two plugins importing a shared helper by
  file each get their own copy. Worth folding into compliance-gate block 4.
- **`@log` costs roughly 291 ns per call above an undecorated method, with logging off.**
  Measured 2026-09-02 over 300,000 calls: 330 ns/call against 39 ns undecorated, after the
  lazy-name fix. Almost all of it is the wrapper's own call machinery rather than anything a
  level check can skip, so the only lever is not decorating the hottest methods -
  `get_key()` and `WaveletFilter._apply_filter` are the candidates. Profile a real analysis
  run before removing either; 291 ns only matters at a call rate nothing has demonstrated.
- **`save_session` re-serializes the whole history on the GUI thread on every plugin
  change**, deep-copying and rewriting the entire session file whether or not the change
  touched most of it.
- **The 178 `except Exception` handlers are inconsistent about what they leave behind** -
  some leave the UI partially updated. (`validate_and_instantiate_plugin` now reports which
  stage failed, since its split into stages.)

### Other queued items

- **The metadata query's table aliases are only half parameterised.**
  `MetaDatabaseLoader.py:1085-1095` builds an alias map that feeds the projection and the
  WHERE qualification, but the JOIN (`:1164-1175`) hardcodes `s.event_db_id` (`:1169`) and `experiments exp` (`:1173`). Renaming the
  `sublevels` alias emits `JOIN sublevels sl ON e.id = s.event_db_id`, which is invalid SQL.
  Latent - nothing changes the aliases today. Found by
  perturbing the alias to verify `tests/unit/utils/test_metadata_query_goldens.py` was
  actually sensitive.
- **The transitive serial declaration is not fully honoured.** `MetaEventFinder` defers to
  `self.reader.force_serial_channel_operations()` and `MetaEventFitter` to its `eventloader`,
  so a finder declares serial *because its reader is not threadsafe* - but the per-instance
  guard locks the finder, which does not protect a reader shared by two finders. Latent
  today: every reader and loader returns `False`. Deliberately not solved with
  dependency-chain lock ordering, which risks deadlock; see the guard's docstring.
- **`MetaEventFinder.force_serial_channel_operations` raises `AttributeError` when
  `self.reader is None`.** Now called from inside the generator by the serialization guard,
  so it surfaces at the first advance rather than being swallowed by the dispatcher. A finder
  without a reader raises from `find_events` two lines later anyway, so this is a change of
  messenger, not of outcome.
- **`tests/unit/plugins/` has no `conftest.py`, so its widget tests leak real windows.**
  Observed 2026-09-02 on Windows: dialogs and console windows flash throughout, and a
  `StepDialog` built with the walkthrough tests' placeholder steps outlived the run as a
  ghost window. Nothing sets `QT_QPA_PLATFORM=offscreen` locally, so on Windows every test
  widget is a real on-screen window and this tree gets none of the teardown
  `tests/unit/views/conftest.py` provides. Cosmetic, and belongs to whoever owns the test
  suites; mirroring the views conftest is the obvious fix. Setting the offscreen platform in
  `pytest.ini` would silence it globally but should be measured against the full suite first,
  since it can change widget behaviour.
- **`MetaView.lock` guards `progress_bars` in `remove_progress_bar:492` only**; the other three
  accesses (`:326`, `:331`, `:369`) are unguarded, so the lock does not establish the invariant
  it appears to. Its comment at `:92-94` is garbled.
- **A short status-panel message can be lost under a long SQL echo.** Reported 2026-09-14:
  a plot refusal did reach the panel and was scrolled past beneath the applied-query echo,
  which runs to many lines. The panel has no severity marking and no filtering.
- **`pydoclint` class-attribute bug - filed upstream, awaiting a fix.**
  https://github.com/jsh9/pydoclint/issues/304. Nothing to do here until a release lands;
  `check-class-attributes` stays `false`. Kept in case the report needs restating: the
  one-line fix is to replace the two hardcoded `".. attribute ::"` literals in
  `rest_attr_parser.py` with `re.compile(r"^\.\.\s+attribute\s*::\s*(?P<name>.+)$")`, which
  accepts both spellings. Reproduction: a class documented with the *correct*
  `.. attribute::` directive plus any `:param:` block reports `DOC601` + `DOC603`; adding a
  space before the `::` makes it pass. Full diagnosis in `DECISIONS.md`.

### Widget ownership left over from the event-filter work

Neither is a crash risk; both are ownership tidiness. `DECISIONS.md` records why the filter
itself stays on the application.

- **`containerWidget` is still parentless** in both comboboxes (`QDialog(None)` at
  `multiselect.py:66` and `multiselect_filter.py:67`; `QWidget(None)` on the Linux branch at
  `multiselect.py:63`), so it is owned by nobody and is not destroyed with
  its combobox. Note the original rationale for parenting it - that it would stop
  `_close_leftover_widgets` sweeping it as a top-level - **was measured and is false**: a
  parented widget that keeps its window flags is still returned by `topLevelWidgets()`.
- **`BaseLineEdit` still registers one application-wide filter and one `aboutToQuit`
  connection per instance** (3 per controls build; `utils/BaseLineEdit.py:45-48`). Both are now harmless - its `eventFilter`
  returns `False` directly and nothing in its body touches a C++ member of `self`. Replacing
  them with a single application-owned watcher would remove the leak outright, but it is a
  new class and a breaking change to something re-exported from `exposed.py`.

### Community-contributed-plugin compliance gate

Designed as a set: a pipeline that lets a community-contributed plugin be verified as safe
and correct to merge with a bounded amount of human review. Blocks 2, 3, 6, 7 and 8 are done
(block 8's "no custom lint rules" call is in `DECISIONS.md`, 2026-09-01); 1, 4 and 5 remain.
Block 1 is a pytest suite, so it is the test developer's.

#### 1. Behavioural conformance suite — remaining gaps

All eight `Meta*` families are covered in `tests/unit/plugins/conformance/`, `PeakFinder`
included, and no fitter is exempt. Still open:

- **Possibly worth revisiting: `MetaReader.close_resources()` relies on GC rather than
  explicitly releasing its memmap** - see `DECISIONS.md` (2026-09-09) for why the reader
  leak check was scoped to that weaker, currently-documented contract rather than the
  stronger one loaders already meet. Touches the base class's docstring contract (every
  future reader, not just these 7) and `poriscope/utils/`/`poriscope/plugins/datareaders/`
  are both `@shadowk29`-owned - consult before implementing, not a unilateral change.
- **Needs discussing: should anything enforce that a new fitter fixture shape comes with
  a check that reads it?** Today nothing does, and `quality_control.rst`'s add-a-fixture
  table says so. Measured during an end-to-end walk: a tapered-oscillation shape was
  planted, routed and used while all four generic fitter checks passed at the intended
  amplitude *and* at 25x it, since they only ask whether events were fitted. A guard
  asserting "the routed fixture changes what the fitter reports" was tried and removed
  the same day - it proves a difference exists, not that anything asserts it, so that
  same oscillation shape would have passed it, and it was redundant once `"dip"` and
  `"staircase"` each had a real check. The option that would work is fixture mutation
  testing: perturb the planted shape, require some assertion to fail. That is how both
  shape checks were verified by hand, but as a suite feature it means re-running tests
  from inside a test. Worth weighing that cost against how often a new shape is added
  (one in this suite's lifetime) before building anything - and worth agreeing not to
  re-add the weaker existence-of-difference guard.
- **Worth discussing: how much of the writer/loader override path to document.**
  `quality_control.rst`'s conformance section now names it in one sentence; a longer
  version with a worked code block per builder shape was cut. Never exercised: all five
  plugins in `MetaWriter`/`MetaDatabaseWriter`/`MetaDatabaseLoader`/`MetaEventLoader`
  declare nothing beyond the generic parameters their builders already supply, and those
  four families have gained one plugin (`SQLitePeakDBLoader`, 2026-04) against seven
  repo-wide since the 2025-08 import. `_fill`'s `ValueError` already names where the
  value goes. Restore the examples, keep the one sentence, or drop it entirely?
- **Worth asking `@shadowk29`: should readers converge on one exception type for
  malformed input?** `tests/unit/plugins/conformance/test_reader_fuzz.py` measured that a
  0-byte file alone already produces four different exception families depending on
  reader/format - `ValueError` (most), `json.decoder.JSONDecodeError` (`ChimeraReader20240101`,
  a `ValueError` subclass), `struct.error` (both ABF2 readers, *not* a `ValueError`
  subclass) - and a missing sidecar file raises `FileNotFoundError` or `OSError`
  depending on the reader. The fuzz suite deliberately does not enforce a type, since
  that would be proposing a contract change, not testing one. Also worth confirming as
  intentional rather than just observed: neither `ChimeraReader20240501` nor
  `ChimeraReaderVC100` attempts to degrade gracefully when its sidecar file is missing
  today - both raise cleanly instead.

#### 3. Contribution scaffold: simpleCalc is still transcribed

HelloWorld is generated now and included from the real files, so it cannot drift.
**`simpleCalc` is still hand-written inline in `simpleCalc/simpleCalc_code.rst`** - its
import roots and its missing abstract methods were corrected 2026-09-22, but the code has no
executable counterpart and nothing checks it. It wants the same treatment: a real set of
files under `docs/source/_static/examples/`, `literalinclude`d, so `ruff` and `black` see
them. Bigger than HelloWorld because it is a worked example with real widgets, not a scaffold
the generator can emit.

#### 4. The plugin trust boundary — largely settled

Both static gates exist (`ruff-plugin-security`, `plugin-module-level`). `DECISIONS.md`
(2026-09-02) records why there is no `bandit`, why the module-level check skips
`analysistabs/`, and that this is explicitly not a sandbox. What remains is the loader item in
the 2026-08-25 audit above: `exec_module` runs before the file is known to be a plugin, and
modules are never registered in `sys.modules`.

#### 5. Scoped CI gate for `poriscope/plugins/**`

**Goal.** A plugin-touching PR gets checks scoped to just the changed plugin, and reaches the
person who maintains it.

**Ownership: done, and deliberately not a gate.** `.github/CODEOWNERS` routes review requests
and nothing more; *Require review from Code Owners* is off on every branch on purpose. **Do
not read the CI work below as gated on turning that toggle on, and do not "finish" this block
by doing so.** Reasoning and the single reopening condition - the contributor list growing
past six - are in `DECISIONS.md` (2026-09-02); the contributor-facing version is in
`development_workflow/code_ownership.rst`.

**What remains.**

1. In `ci-fork-pr.yml` (which already exists for fork PRs and runs strict
   `pre-commit run --all-files` plus the full `pytest` with fork-safe `contents: read`), add a
   step after checkout computing
   `git diff --name-only origin/${{ github.base_ref }}...HEAD` and, for matches under
   `poriscope/plugins/**`, run block 1's conformance suite scoped to those files
   (`pytest -m conformance -k <derived from changed filenames>`). The schema-check half needs
   nothing: `test_plugin_settings_schema.py` already sweeps all 24 plugins on every push.
2. Mark that step and the existing strict `pre-commit` step as required status checks for
   `main`/`develop`. Automated checks only - this does not extend to code-owner review.
   Marking `docs-check.yml` as a required status check is the same admin-only step.

**Gotcha.** `ci-fork-pr.yml`'s permissions are deliberately `contents: read`; do not add
anything needing write access. That is `ci-internal-pr.yml`, which is not fork-safe.

**Notes from scoping (2026-08-31).** Exception types vary by format on a 0-byte file
(`ValueError` for Chimera/BinaryReader1X, `struct.error` for ABF2) - inconsistent but
none hang.

## Owner-held - flagged for the owning developer, never fixed here

Logic in `PeakFinder.py`, `Basic_PeakFinder.py` and `NanoTrees.py`; see the standing policy at the end.

### Plugin contract

- **PeakFinder's cross-channel barrier can be skipped** *(by reading)*:
  `_post_process_events:2133-2178` runs global classification only when every other channel's
  `eventfitting_status` is already True, but the base sets it after the hook returns
  (`MetaEventFitter.py:763-764`), so two channels finishing together both skip it.
- **PeakFinder switches `matplotlib.use("Agg")` process-wide from a worker thread**
  (`:3182`, `:3694`, `:4128`); harmless today because the views only read `pl.rcParams`.

### Fitter plugin defects

- **`find_mode_blockage_level` guards two of its three Optional parameters.** The body
  handles `data is None` and `baseline_std is None`, then computes
  `abs(data_min - baseline_mean)` with no guard on `baseline_mean`, equally `Optional[float]`
  under the contract. **Now open only in `Basic_PeakFinder.py`** (`:1248`, unguarded at `:1299`).
- **`Basic_PeakFinder._populate_event_metadata` can put `None` into event metadata**, whose
  declared value type is `Union[int, float, str, bool]`. A `None` reaching the database
  writer is not something that contract allows for.
- **`Basic_PeakFinder` writes `NaN` into `sublevel_current` for 23 of 25 events** on the
  conformance dip fixture, from an `np.median` over an empty slice (`Basic_PeakFinder.py:723-731`) - a zero-width level
  whose mean is undefined. Same family as the `sublevel_max_deviation` zero-width crash
  fixed 2026-08, which now returns `0.0`; this path returns `NaN` instead and no one
  notices. In event 0 it is sublevel 9, a row carrying a valid `peak_height` (434.4) with
  `sublevel_current` `NaN`. Distinct from the plugin's *structural* `NaN`s, which are fine:
  it emits 15 sublevels per event interleaving peak rows with the level rows between them,
  so the 16 peak-specific columns are `NaN` on every non-peak row by design. The run emits
  134 `RuntimeWarning`s ("Mean of empty slice", "invalid value encountered in scalar
  divide") that conformance cannot see, since no check asserts finiteness - visible as the
  10 collapsed warnings on any `pytest tests/unit/plugins/conformance` run.
- **`NanoTrees._DNA` slices with two unguarded `Optional[int]` paddings**
  (`data[:padding_before]`, `data[-padding_after:]`), so the negation raises `TypeError` for
  any event loader supplying neither. It has no live caller - the only call site is commented
  out inside `_locate_sublevel_transitions`.
- **`NanoTrees._locate_sublevel_transitions` overwrites both baseline arguments**, recomputing
  `baseline_std`/`baseline_mean` from `data[:padding_before]` and discarding what the loader
  passed. Possibly deliberate, but the two parameters are inert and the docstring's promise to
  handle `None` arguments is met by accident.
- **`PeakFinder` carries a third copy of the CUSUM variance-reset bug.**
  `PeakFinder.py:1008`'s `varS = 0` sits after the `while` loop rather than inside the
  jump-accepted block (`:1000-1007`), so the Welford accumulator is never reset at a detected changepoint
  and the variance estimate is inflated (~586x one sample after a transition, ~5x after a
  hundred). Fixed in `CUSUM.py`/`ClassicCUSUM.py` on 2026-09-03 against the C reference; this
  copy is left for its owner. Note `PeakFinder` uses `threshold = step_size` directly rather
  than `_calculate_threshold`, so the magnitude above is indicative, not transferred.
- **Both PeakFinders' `sublevel_starts` really holds dicts, not indices.** Now consistent
  rather than broken - the `MetaEventFitter` contract was widened to `List[Any]` to match what
  it has always produced - but the parameter name still says "starts" while the payload is
  per-sublevel records.

### Open against the PeakFinder integration

- **The direction classifier's plot drops the outer tails.** `PeakFinder.py:4017` fits a
  trimmed 5-95% core (`DIRECTION_FIT_PERCENTILES`, `:178`), and its plot (`:4128-4144`)
  `np.histogram`s the full array against the core's bins, which silently discards about the
  outer 10%. The other two classifiers now fit the full data (`:3034`, `:3552`) and bin plots
  against the fit's histogram (`_histogram_for_fit:5766`), so they no longer cut off.

## Standing policy

### Exclusions (standing project policy)

- `NanoTrees.py` — a **deprecation candidate**, not an ownership question: its co-author has
  left the lab and `CODEOWNERS` assigns it to `@shadowk29` with the rest of `eventfitters/`.
  Fixing anything in it is permitted but not worth the effort while deprecation is on the
  table.
- `Basic_PeakFinder.py` / `PeakFinder.py` — logic owned by another developer, who is active.
  Consult them before any `MetaEventFitter` signature change, which moves all three owner-held
  fitters in lockstep.

**Docstring, signature and type-hint changes: in scope.** All three are fully annotated and
report zero pydoclint violations.

**Logic changes: out of scope, unconditionally**, even when annotating surfaces a real bug.
Write the honest annotation describing what the code does today, mark the defect with a
narrow `# type: ignore` and a `NOTE:` at the site, record it below, and leave the fix to the
owning developer.
