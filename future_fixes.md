# Future Fixes

Queued work and standing policy for the Poriscope codebase.

**Only future-facing work belongs here.** When something lands, delete its entry rather
than annotating it as done - the narrative belongs in `changelog.md`. When something is
settled as deliberately not worth doing, move the reasoning to `DECISIONS.md` and delete
the entry. Keep finished-work context only where an open item cannot be understood
without it. Keep entries terse: one to three lines, with the file:line and the measured
number, not the narrative.

Everything outside the tooling tiers is a logic change and needs an approved plan first.
Read-only investigation and measurement do not.

- **Raw SQL subset filters still cannot scope a plot**, and the fix is a feature build in
  `MetaDatabaseLoader` rather than a defect repair - see `future_refactors_and_features.md`
  Part 13. Queued deliberately for after the 2.0.0 refactor.

## A milestone blocks the page switch but not what caused it (2026-09-21)

Found during 5c.6's manual pass; **pre-existing**, and the gating is byte-identical to
what it was. `MainView.switch_to_page:913` refuses to change page while
`_milestone_dialog` is up and the target is not `_expected_next_view` - but every caller
does its work *before* calling it, so the refusal comes too late to prevent anything:

- `on_raw_data_view_click:616` and its EventAnalysis and Metadata twins call
  `on_load_analysis_tab_button_click` first, which emits `instantiate_analysis_tab` - the
  tab is created and starts its own walkthrough - then `sync_sidebar_highlight`, and only
  then `switch_to_page`.
- `handle_menu_click:697` highlights before switching.
- `on_load_analysis_tab_button_click:727` highlights as well, so the highlight moves twice.

Observed: during a milestone, clicking any sidebar button opens that tab and starts its
tutorial, and every menu stays live under the dimming overlay. The gate is in the wrong
layer - it guards the last step of an action whose earlier steps have already run. Fixing
it means asking "is this navigation allowed?" before the handler acts, not inside the
final call.

## Shipped code cites refactor plan step numbers (2026-09-21)

`refactor_2.0.0.md` is deleted when 2.0.0 ships, so every `Step 4a`, `5c.6` or `5e.3` in a
docstring, comment or test points at a document that will not exist. Counted across
`poriscope/`, `tests/` and `scripts/`: **~330 citations**, led by `Step 4a` (101), `Step 4`
(58), `Step 4c` (42), and the 5c/5e series from this session (~80). Kyle, 2026-09-21: worth
doing, not now.

Not a regex job - each needs rewriting to explain the mechanism instead. "Step 4a turns
these into `self.call(...)`" becomes "these became `self.call(...)` on the Model". Naming
the *old mechanism* is wanted, since that is what makes a docstring findable; naming the
plan step is what breaks. Docstring-only, so no tests and no changelog entry.

## Action replay re-reads the filter selection instead of replaying it (2026-09-17)

Both non-trivial `@register_action` methods call `self.get_selected_filters()` inside their
own bodies - `MetadataView._overlay_plot:1414` and
`ProteinView._update_distribution_ensemble:1934` - and that reads
`self._subset_controls.filter_comboBox.getSelectedItems()`, i.e. live widget state. Everything
else the action needs arrives in its recorded `parameters` dict, so **replaying a saved plot
applies whichever filters are selected at replay time**, silently, and the plot is not the one
that was saved. Capture the selection into the recorded payload at record time and pass it in;
`_reset_actions` already reads nothing. `DECISIONS.md` 2026-09-17 rule 5 is the standing rule
this violates.

## Controller-side `call()` is a convention, not a checked invariant (2026-09-17)

`check_mvc_boundary.py`'s rule 5 (`plugin_reaches:530`) bans every route to a data plugin
*except* `call()`, and walks `tab_layer_modules()` as one set without asking which layer a
module is - so nothing distinguishes a Model making a plugin call from a Controller making
one. Measured 2026-09-17: **50 `self.model.call(...)` sites across the Controllers, 0 direct
`self.call(...)`, 6 in the Models** - the narrowness has held on review alone. Consider an
allowlist of named wiring operations for Controller-side `call()` before the accumulation is
real; latent today, and the same soft governance as `_get_plugin` staying private.

## The capture-rate plot always reports one row dropped (2026-09-14)

`MetadataController.fit_capture_rate` compares the surviving interval count against the
**event** count, so a column with no repeated timestamps still reports "1 rows dropped by
log filter" - n events make n-1 intervals by construction. Cosmetic, and preserved exactly
when the calculation moved from `MetadataView` to the Model so that the move changed
nothing the user sees; a test pins it as current behaviour. The fix is to compare against
`initial_length - 1`, and to delete that test with it.

## `MetadataModel.kernel_density` uses a deprecated SciPy namespace (2026-09-14)

`MetadataModel.py:296` calls `stats.kde.gaussian_kde`, which warns
"the `scipy.stats.kde` namespace is deprecated and will be removed in SciPy 2.0.0" on
every density plot. The fix is one line - import `gaussian_kde` from `scipy.stats` - and
the only reason it is queued rather than done is that it belongs with a test run that
exercises the density path rather than with an unrelated branch.

## The experiment/channel scope has three annotations for one value (2026-09-14)

The analysis-tab layer declares it `Optional[Dict[str, List[Optional[int]]]]` at **14**
sites; `MetaDatabaseLoader.load_event_data` and its neighbours declare
`Optional[Dict[str, Optional[List[int]]]]` at **19**; and the selection tree stores
`Dict[str, Dict[str, List[str]]]` (`MetaSubsetTabView.py:169`), converted with
`int(selected_channel)` at `MetadataView.py:2048`. The producer at
`MetaSubsetTabView.py:742` builds `{exp: [channel] or None}`, so the loader's form is the
correct one and the tab layer's 14 are transposed. Invisible to mypy because the value is
passed through `call()`, which returns `Any`. Found writing tests against the loader's real
signature; not fixed with them, because it is a layer-wide annotation change rather than
part of pinning two methods.

## `SQLiteDBLoader` opens a fresh connection per schema lookup (2026-09-08)

`get_table_by_column:454` and `get_column_names_by_table:382` each call
`sqlite3.connect(self.db_path)` per invocation, with no cache. Measured: **10 connections
per `construct_metadata_query`** with a WHERE body, 4 without. Cheap on a local file
(1.5 ms/call, so 0.08 s to validate 50 filters) and not the cause of the filter-loading
pause, but the schema cannot change while a loader is open, so a dict cache built in
`_finalize_initialization` would remove all of them. Re-measure on a network-mounted
database before deciding it does not matter.

## `_validation_columns`' fallback triple is wrong twice over (2026-09-08)

`MetaSubsetTabView._validation_columns` falls back to
`["sublevel_current", "voltage", "duration"]`, which is one column from each of the three
tables - so **every** filter validation joins all three, measured as 2 JOINs even for a
filter with no conditions at all. A single events column yields the joins the filter itself
needs and nothing more: 0 for `dwell_time < 300`, 1 for a sublevels- or experiments-only
filter, and all of them still build, so validation is unaffected. The triple is also not
guaranteed to exist in a given database, which is the second half of the same defect: only
`ProteinView.update_column_names:626` fills `available_columns`, so
`MetadataView.update_column_names:2677` - which updates its axis comboboxes and stores
nothing - always takes the fallback.

One fix, two lines: store `column_names` in Metadata's `update_column_names`, and narrow the
fallback to a single column. **`["event_id"]` does not work** as that column - it is in
`construct_metadata_query`'s `redundant_cols` and `get_table_by_column("event_id")` returns
None, so it raises `ValueError: columns could not be mapped to tables`. Two tests in
`tests/unit/views/test_duplicated_helpers.py` are written to flip when this lands.

## `MetaSubsetTabControls.get_selected_filter_names` has no production caller (2026-09-08)

`MetaSubsetTabControls.py:153` wraps `filter_comboBox.getSelectedItems()` and is called only
from `tests/unit/views/utils/test_metadata_controls.py:544`. Its obvious caller,
`MetaSubsetTabView.get_selected_filters`, reaches past it to the combobox. Either delegate or
delete; delegating changes what the tab tests mock, so it was left out of the promotion.

## The 2.0.0 refactor plan claims much of this queue (2026-09-03)

**Read `refactor_2.0.0.md` before picking anything up here**, and check whether the item is
already assigned to a step. Plan artifact:
<https://claude.ai/code/artifact/304ba119-d177-4918-90af-471d6de6bb80>

Root cause behind most of the findings below: the analysis-tab Models are empty (298 lines
across five, four of them `def _init(self): pass`) while the Views are 11,557 lines and carry
75 of the 77 `global_signal.emit` sites - re-measured at `062ef6f`. Decisions A-E are recorded
in `DECISIONS.md`.

- **1.9.0 is Tier A + B2 + C of the plan's Step 1** - the defects in code the refactor moves,
  the zero-risk deletions, and the CI/tooling tier. Everything else in the High/Moderate tiers
  below ships inside 2.0.0.
- **Do not fix duplication findings here.** The ~1,900 removable lines, the three
  `format_axis_label` copies, `_factors`, `_setup_canvas`'s dead `num_channels`, `hist_data`'s
  three shapes and the five oversized `setupUi` are the refactor itself, not work to do ahead
  of it.
- **Blocked on the plan's Step 2** (characterization tests, which do not exist): every
  structural change in Steps 3-5.
- **The person-blocker is cleared.** The four-part ask in `refactor_2.0.0.md` was sent
  2026-09-04 and **agreed the same day** - green light to proceed. Decision E is satisfied, so
  Step 2 is unblocked and so are Steps 3a/3f in `analysistabs/utils/`. **The whole plan is ours,
  tests included** - all five Step 2 deliverables plus re-pointing the existing suites. A standing
  exception to "test-writing is hers" for this plan only; blocks 1 and 7 below remain hers. The
  fitter owner still must be consulted before any `MetaEventFitter` signature change, which moves
  all three owner-held fitters in lockstep.
- `future_refactors_and_features.md` Parts 5-12 are absorbed as the plan's Step 5.

## Review findings (2026-09-03)

Six-slice review: app shell, `Meta*` ABCs, algorithmic plugins, database layer, Qt/GUI,
test/CI surface, docs. Full write-up with reproductions:
<https://claude.ai/code/artifact/0886d408-06de-488d-8a8e-7f6a68206651>

Already recorded under the 2026-08-25 audit below and not repeated here: the
emit-then-read-an-attribute pattern, the plugin loader executing modules before it knows
they are plugins, the `apply_settings` alias, the `except Exception` inconsistency, and
the oversized `setupUi` methods. This review re-confirmed each with fresh counts.

### High

- **`test_plugin_compliance` parametrizes from `__subclasses__()` at import time**, so which
  test doubles it audits depends on module import order. `pytest tests/unit/utils
  tests/unit/plugins` (inverted) picks up `ConcreteDatabaseLoader`, `ConcreteEventFitter`
  and `MockEventLoader` and reports 4 failures that natural order never sees. Skip classes
  defined under `tests/`.
- **`INSERT OR IGNORE` turns a schema mismatch into a misleading rejection reason.**
  `SQLiteDBWriter._insert_event`/`_insert_sublevels` infer failure from `cursor.rowcount`,
  so a `NOT NULL` violation surfaces as `IOError("Cannot Overwrite Existing Event")`. Hit
  twice while building the writer-fix harnesses (metadata missing `channel_id`, sublevel
  missing `levels_left`). `OR IGNORE` is there to make a genuine re-write a no-op, so
  distinguish the two: check required columns up front, or use `ON CONFLICT ... DO NOTHING`
  on the uniqueness constraint only.
- **Neither writer has any unit tests.** No `tests/unit/plugins/dbwriters/` and no test file
  for `MetaWriter` or `MetaDatabaseWriter`, so the component owning the whole database
  schema is unverified. Test authoring is another developer's remit - a coverage gap, not
  work to pick up here.
- **`Optional[int] = None` channel dispatch is documented 21 times and implemented almost
  nowhere.** `close_resources` is `@abstractmethod` in all six bases, none implements the
  dispatch, and 18 of 21 shipped plugins ignore the argument.
  `MetaEventFitter.reset_channel:336-340` self-documents the failure, then `:354` writes
  `self.eventfitting_status[None] = False` into a `Dict[int, bool]` behind a
  `type: ignore[index]` guarded by an `except KeyError` that cannot fire. It clears 4 of 7
  per-channel dicts, so `sublevel_starts`, `event_lengths` and `applied_filters` survive an
  abort holding stale data. One template method on `BaseDataPlugin` plus a
  `_close_one_channel(channel: int)` hook fixes all of it and removes four `type: ignore`s.
- **`MetaEventFinder`'s base loop reads a setting no schema declares.** `:459` reads
  `self.settings["Threshold"]["Value"]` from base-class code, but `get_empty_settings:1056`
  declares only `MetaReader` and `scripts/new_plugin.py` emits no `Threshold`, so any
  generated eventfinder `KeyError`s inside the base. `:459` also compares it against a mean
  in pA while `ThresholdBlockageFinder:83` declares it in σ.
- **The two multi-select popups disagree about Linux.** `MultiSelectComboBox.__init__`
  builds a frameless `QWidget` popup on Linux and a `QDialog` elsewhere;
  `MultiSelectFilterComboBox.__init__` builds a `QDialog` on every platform, so the filter
  picker never got the Linux treatment. Both `__init__`s were left untouched by 5d's
  deduplication precisely because reconciling them changes behaviour on a path CI cannot
  exercise (`DECISIONS.md` 2026-09-01). Needs a Linux check and a manual Windows pass, not a
  code reading.
- **The baseline histogram is coarse, at `int(len(data)**(1/3)/2)` bins.** (Same method as
  Part 15 of `future_refactors_and_features.md`; likely belongs in that piece of work.) That is 10 bins
  on a 10k-sample chunk, of which ~6 survive the two windowing passes, and the
  log-linearised fit is biased high at that few points: +2.3% at 10k, falling to +0.2% at
  1M. Rice's rule would give four times as many bins. Retuning it changes which events are
  found, so it needs the same treatment the σ correction got, not a quiet edit.
- **The two session writes are non-atomic and omit `default=serialize_object`.** The
  config write uses it; `save_session` and `save_tab_actions` do not, so a value neither
  can serialise raises `TypeError` mid-write. The write is not atomic either, so that
  crash truncates the very file `_suppress_session_save` exists to protect. Write to a
  temporary file and replace. (The key-agnostic type restoration and the unreachable list
  branches in the same two walkers were fixed in 5c.6, 2026-09-21.)
- **No schema version, and the compatibility check has a dead branch.** No
  `PRAGMA user_version` anywhere. `SQLiteDBLoader._finalize_initialization:1042-1047` guards
  `extra_tables` against `"event_counts"`, already in `expected_tables` (`:1012`) and so
  never present - net effect, any table a newer writer adds makes the loader refuse the
  file. `_ensure_event_counts:1122` uses `executescript`, which commits pending work and
  runs each statement unwrapped, so a failure leaves the table created but empty and the
  `table exists` guard (`:1116`) never retries - every count reads 0 forever. It also runs a
  full-table aggregate on the GUI thread at plugin load.
- **`None` means both "query failed" and "no rows".** `SQLiteDBLoader._load_metadata:840-847`
  returns `None` for an empty result set *and* for `sqlite3.Error`, logging only a warning,
  and `query_database_directly`/`load_metadata` propagate it. Same shape in
  `get_column_units:316-324`; `SQLitePeakDBLoader.py:151-154` documents having been bitten.
  `MetaDatabaseLoader.load_metadata` is declared `-> pd.DataFrame` but returns `None` at
  `:1106` and `:1111`; the mypy hook runs without pandas, so this is invisible to the gate.
- **The Protein tab blocks the GUI thread with no progress and no cancel.** `ProteinView.py`
  contains no `update_progressbar`/`progress`/`kill_`/`abort`/`cancel` across 4,058 lines,
  while `_update_distribution_individual:2462` runs a rejection sampler bounded at
  200 x 50,000 twice per event plus up to two `curve_fit` calls, over an unbounded event
  count. No `processEvents()` anywhere in the repo. The threaded path exists but is reached
  from 5 view sites, all writes. **Blocked on** converting the emit-then-read sites in the
  2026-08-25 tier to real callbacks.

### Moderate

- **`BesselFilter` uses the wrong filter form and guards it with a magic constant.** `:212`
  builds `(b, a)` and `:124` runs `filtfilt`, guarded by `if any(np.absolute(p) >= 0.975)`
  at `:96`. Measured against `sosfiltfilt`: at the allowed limit (Wn=0.02) `filtfilt(b,a)`
  already deviates by 6.3e-4 σ, and just past it by 22.6%. `output="sos"` + `sosfiltfilt`
  makes the guard unnecessary *and* unblocks the low cutoffs it rejects today (25 kHz at
  4.17 MHz is refused). Also `:186` makes the user re-enter `Samplerate` the reader already
  knows, so a mismatch silently mis-designs the filter.
- **Windows logging drops any record containing `μ`.** `main_app.py:165` constructs
  `logging.FileHandler` with no `encoding=`, so cp1252 cannot encode U+03BC and the record
  is discarded with `--- Logging error ---` on stderr (reproduced). Six sites write `"μs"`,
  including `metadata_units["duration"]` in both PeakFinders, which reaches the database,
  against 65 writing ASCII `"us"` - one physical unit with two spellings in the database.
- **Severity is doing double duty as the UI's interruption policy.** `QtHandler` is attached
  to the root logger with no name filter, so any third-party library logging at ERROR pops a
  dialog at the user. Code is now written to game it: `main_model.py:170` chooses ERROR
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
  `"Validate Options"` flag is rejected and the `"Kind"` key is the recorded better fix.
- **`MetaReader.load_data`'s return annotation is false, with a `cast()` over it.**
  `:137-139` declares `-> npt.NDArray[np.float64]` but `:244-248` returns a 3-tuple when
  `raw_data=True`, with `cast(np.ndarray, data)` at `:245`. Per `DECISIONS.md` the remedy is
  splitting `raw_data` into a second method, not widening the union.
- **Chunk boundaries can duplicate a sample through a float round-trip.**
  `MetaReader.py:389-394` converts an integer sample index to seconds and `:160-161`
  truncates it back; measured, `int((i/sr)*sr) != i` for 7.7% of the first 2M indices at
  100 kHz, and when it slips low `i += len(data)` compounds it. Pass sample counts, or
  `round()`.
- **Duplication, measured at 1,400 removable lines** (was 1,889; Step 3a's `MetaControls`
  took 489). `CUSUM.py`/`NoFitter.py` share 411 identical lines;
  `ClassicCUSUM` is a 195-line override differing in 2 lines and wants to be `CUSUM` with a
  `_normalize_step_size()` hook; the two Chimera readers differ in 23 lines of 390;
  `_find_events_in_chunk` is duplicated across two finders.
- **`format_axis_label` still exists in three places** - a module function in `ProteinView.py`,
  a method in `MetadataView.py` and inlined in `ClusteringView.py`. The behavioural drift is
  gone (2026-09-04); merging the copies is the refactor's Step 3.
- **`MainView`'s navigation state is a QLabel's rendered text.** `get_current_view:1079`
  returns `self.page_title_label.text()`, keyed into `self.pages` at `:1052` to decide
  whether to launch a walkthrough; the label starts as `"Home"`, in neither, so the app logs
  a misleading "does not support walkthrough" before the first switch. `on_view_switched`
  writes `self._current_view` at `:1094` and nothing reads it. The five tab Views do this
  correctly with a hardcoded literal.
- **~75 attributes are assigned only outside `__init__`** across the five Views, with 26
  guards papering over it (6 `hasattr`, 20 `getattr(self, ..., default)`) - re-measured
  2026-09-04, the earlier "28 and 23" was wrong. `ClusteringView.axes` is the clearest case,
  assigned only in `_reset_actions:158/160` and read unguarded at `:739`/`:762`, though it is
  latent: both reads are immediately preceded by a `_reset_actions()` call, and `update_plot`
  carries no `@register_action` so replay cannot reach it out of order. Fixing it properly
  means an `Optional[Axes]` declared in `_init` plus handling at both reads, which belongs
  with the canvas-lifecycle work in Step 3, not ahead of it. **`ProteinView.ax_hist`/`ax_vm`
  are not instances of this** - both are properties over axes built eagerly by
  `_set_custom_display_area`, which is on the construction path.
- **`MetaFilter.force_serial_channel_operations` is unenforceable.**
  `get_callable_filter:105` hands out `self.filter_data` as a bare bound method invoked
  inside another plugin's generator, and `@serialize_channels` is restricted to generator
  functions. Either delete the declaration for this family or route `filter_data` through
  the guard.
- **Half-finished multi-channel plotting left dead code in the base.**
  `MetaView._setup_canvas:221` never uses its `num_channels` parameter though its docstring
  promises subplots per channel; `MetaView._factors:139` is duplicated verbatim into
  `RawDataView.py:109` and `EventAnalysisView.py:122`, shadowing the base the other two tabs
  inherit; and `main_view.py:110-111` allocates a `Figure` + `FigureCanvas` never referenced
  again.
- **`SQLiteEventLoader` opens one connection per event** (`:127`, from
  `MetaEventLoader.get_event_generator:320` per index); `construct_metadata_query` opens ten
  connections for a single call, measured. No connection reuse and no `PRAGMA journal_mode`
  anywhere.
- **`columns.name` is globally `UNIQUE`** (`SQLiteDBWriter.py:529`) with `INSERT OR IGNORE`
  (`:608-616`), so a metric named identically in event and sublevel metadata registers once
  and `get_table_by_column` routes every query for it to the wrong table. Separately
  `level_id`/`levels_left`/sublevel `channel_id` are attached at runtime
  (`MetaEventFitter.py:674-685`) and never registered, so
  `construct_metadata_query(["level_id"])` raises.
- **`fit_events` turns plugin bugs into scientific rejection reasons.**
  `MetaEventFitter.py:578-717` has four near-identical `except` pairs keying
  `self.rejected[channel][str(e)]`, so a `TypeError` from a plugin defect lands in the
  user-facing rejection table beside "Too Few Levels" and the channel still finishes with
  `eventfitting_status = True`. Also `:601` checks `isinstance(..., Iterable)` then `:605`
  calls `len()` - a generator passes and dies on the call - and `fit_events(indices=[])`
  marks the channel fully fitted while the docstring at `:481` says it fits everything.
- **`_write_data` takes 13 parameters** (`MetaWriter.py:255-270`) where the caller
  (`:438-452`) unpacks one dict. Related: `get_single_event_data` really returns `None`
  (`MetaEventFinder.py:835`) and its only caller subscripts it unchecked
  (`MetaWriter.py:427`), producing a swallowed rejection reading
  `'NoneType' object is not subscriptable`. It should raise.
- **Silent scientific fallbacks with no metadata flag, in `CUSUM.py`.** For a sublevel
  shorter than `rise_time`: `sublevel_current` becomes a single sample from the next level's
  onset instead of a median (`:446`), `sublevel_stdev` becomes `baseline_std` (`:474`), and
  `sublevel_blockage` becomes an unsigned max-absolute instead of a signed mean deviation
  (`:501-510`). The retry loop at `:377-380` fits different events in one channel at 1.5^0
  to 1.5^4 times the user's step size and records which nowhere. `:229`'s
  `np.std(data[-padding_after:])` returns the whole event when `padding_after == 0` and its
  sibling returns `nan` when `padding_before == 0`, poisoning `step_size` at `:235` (both
  verified). `Step Size` has no default and `_validate_settings` is `pass`, so `None`/`0.0`
  reach the division and every event is rejected with an opaque key.
- **`replace_raw_settings_option` is dead in practice.** `BaseDataPlugin.py:356-387` exists
  to track a parent rename into a dependency's `Options`, but both paths reaching
  `apply_settings` blank it first (`DataPluginController.py:233`, `:576`), so it always
  returns at `if options is None`. Its covering test mocks the instance and asserts only
  that it was called, with fixture data production never produces.
- **`BaseDataPlugin.__init__` registers dependencies under an empty key.** `apply_settings`
  runs at `:114` before any `set_key`, so the scripted `Plugin(settings)` path records `""`.
  The GUI is safe (`DataPluginController.py:551` sets the key first); the documented
  standalone path is not.
- **`edit_plugin` mutates the dependency graph partway through with a hand-rolled undo.**
  `DataPluginController.py:77-260` re-points dependents one at a time and calls
  `instance.set_key` only *after* the loop, so a mid-loop failure leaves some dependents
  pointing at a key that does not exist, logged per-dependent while the method continues.
  Wants validate-then-commit rather than compensating undo.

### CI, packaging and tooling (not logic changes - no plan needed)

- **`ci-internal-pr.yml:108-116` pushes from a detached HEAD.** `git add -A && git commit
  && git push` on a `pull_request` event, where `actions/checkout` leaves no branch to push -
  guarded by `if ! git diff --quiet`, so it only fires when the manual hooks change a file.
  There is still **no coverage gate**: the step now runs (`pytest-cov` landed 2026-09-04) and
  prints `::notice::Line Coverage`, but nothing fails on a drop. Baseline 83%.
- **No Windows CI job.** Every matrix is single-entry and none runs `windows-latest`, so
  Linux takes the opposite branch from the shipped platform at 6 of 11
  platform-conditional sites - including `WaveletFilter.py:192`'s `os.add_dll_directory`, in
  the one module that loads a native binary and is referenced nowhere in `tests/`.
- **`release.yml` holds `contents: write` plus a PyPI OIDC token while calling four floating
  third-party action tags**, none SHA-pinned. It installs `mingw-w64` nothing in the job
  uses, and runs no lint gate and no `twine check`. `CITATION.cff`'s version is a
  hand-maintained copy of `poriscope/constants.py` and the workflow validates the CFF schema
  but never that the version matches the tag, so Zenodo can publish under a stale version.
- **No pip cache in `ci-internal-pr.yml` or `release.yml`**, and `ci-branches.yml:101` runs
  `pre-commit clean`, discarding the hook-env cache every run.
- **`black` runs only at the manual pre-commit stage**, so formatting is enforced by CI
  rewriting contributors' commits rather than by failing them.
- **`scripts/new_plugin.py`'s two base-class tables are guarded one-directionally.**
  `tests/unit/scripts/test_new_plugin.py` asserts each `FAMILIES` and each `TRIAD` entry
  appears in `main_model.py`, not the reverse, so adding a twelfth `Meta*` base leaves the
  generator and `--list` silently blind with no test failing. Both guards are also regexes
  over another file's source text, so reformatting `main_model.py`'s dict breaks them
  spuriously.
- **`test_mapping_audit.csv` is stale and nothing executable reads it.** Its
  `LooseMatchFound` column still names files renamed by the very commit that added it
  (`43d556d`). Referenced only from the `test_event_worker.py` note below. Regenerate or drop.

### Found while verifying the 2.0.0 plan (2026-09-04)

Findings the plan's own steps already claim are recorded in `refactor_2.0.0.md`, not here.

- **Step 4a leaves dead callback sinks behind it; sweep them once a tab reaches zero
  emits.** In `EventAnalysisView` the seven attributes `update_plot_features` and
  `set_num_events_allowed` assign are now written and never read, and with no emits left
  in the View nothing reaches those methods or their Controller relays
  (`update_features`, `set_num_events_allowed`) either. The plan's 4a bullet predicts
  ~30 such `relay_*`/`set_*` sinks across the tabs. Check for callers in `tests/` and
  the other tabs before deleting any, and do it per tab as each hits zero.
- **`MetaSubsetTabView.update_units` is Metadata-only behaviour on a shared base.**
  Re-diagnosed 2026-09-08; the earlier entry here said "protein-tab unit labels silently
  never update", which implied Protein has unit labels it should be updating. It has none:
  `proteincontrols` contains no units label, `ProteinView` keeps no units cache, and its
  axis labels use hardcoded unit literals. `update_units` is called from
  `MetadataView:1878` and nowhere else, so `ProteinView`'s missing `update_column_units`
  is **unreachable rather than swallowed**. The fix is to move `update_units` down to
  `MetadataView` and make `MetaSubsetTabController.update_column_units` a Metadata-only
  relay — the same shape as the Clustering-only `check_column_exists`/`set_column_exists`
  that Step 3e moved down. Folded into Step 4a's first subset-tab commit.
- **`MetaDatabaseLoader.export_subset_to_csv:605` assumes one `data` row per event id.**
  `data["filename"] = filenames` raises a length mismatch if the `data` table holds rows for
  only some of the selected events. An empty `data` table is now rejected explicitly; a
  partially-populated one is not.
- **`SQLitePeakDBLoader.get_plot_features:176-178` indexes `result.iloc[1]`** but the guard at
  `:154` only rules out zero rows, so a single-row result raises `IndexError`.
- **`SQLiteDBLoader._load_metadata_generator:886` returns bare on `sqlite3.Error`** (method at
  `:859`), which
  inside a generator is an ordinary `StopIteration` and so is indistinguishable from
  exhaustion. Same conflation the `None`-sentinel split fixed for `_load_metadata`
  (2026-09-04), but a generator needs its own contract.
- **Five methods on the 2.0.0 move list have zero test coverage**, so moving them is unobservable
  by the current suite: `MetaView._logscale_and_filter_dataframe:789`,
  `RawDataView._gaussian:556`, `RawDataView._gaussian_fit:574`, `ProteinView._summarize_vm:497`
  and `RawDataView._get_baseline_stats:467` (the two hits for that name belong to the
  `MetaEventFinder` copy). Closing this is the Step 2 gate's job, not separate work.
- **The destination layer for Steps 3d and 4a-4e is unverified.** `MetaModel` is 363 lines over
  12 methods with no dedicated test file, and `tests/unit/models/` covers the tab Models only
  through `test_protein_model.py` (64 lines, 8 tests). A coverage gap, and test authoring is the
  test developer's remit.

### CUSUM follow-ons (the variance-reset fix landed 2026-09-03)

- **The C resets the counters on any threshold crossing; this implementation resets only on
  an accepted jump**, so a crossing rejected by the `rise_time` guard still accumulates
  `varS` across the rejected boundary - the same bias the landed fix removed, just rarer. It
  also leaves `gpos`/`gneg` above threshold, so the next iteration re-detects and re-rejects
  the same jump. Moving to the unconditional form changes detection behaviour and needs
  validating against reference data first.
- **The `length - jump > rise_time` half of the C's edge guard is still missing**, already
  flagged by a comment in the loop. Adding it would suppress a transition detected too close
  to the end of an event, which the C refuses.

### Docs

- **Autodoc publishes 478 private methods.** `plugins_generate_autodoc.py` emits 1,119
  `automethod` directives across 78 pages, 43% single-underscore privates, so
  `peakfinder.rst` publishes 45 members (32 private) inlining 1,528 lines of internal
  rationale onto one public API page. The generator should omit a private-methods section.
  Precedent for moving that prose exists - `fit_fallbacks.md` holds the narrative that was
  "too large to carry in docstrings", and `PeakFinder`'s class docstring points at it.
- **One stale doc claim.** `future_refactors_and_features.md:283` still asks someone to
  confirm whether `PluginManagerPopup.py` is dead code; it was deleted in `d0dbc53`.
- **Four `Meta*` bases carry a byte-identical 3,584-character `get_empty_settings`
  docstring** (`MetaEventFitter`, `MetaDatabaseLoader`, `MetaEventLoader`,
  `SQLiteEventLoader`) - four copies of one document that can drift independently.

## Structural audit findings (2026-08-25)

A read of the app shell, plugin contract and threading layer. Full write-up:
<https://claude.ai/code/artifact/a1bec2cd-a157-4299-acb3-a135738fee41>

The common thread: the app's main control path is a method name passed as a string and
resolved with `getattr`, which none of the four pre-commit gates can see.

### High - working today, but for reasons nothing records or tests

- **Emit-then-read-an-attribute, in the analysis-tab View layer.** Emit
  `global_signal`/`data_plugin_controller_signal` with a `return_function_name` callback,
  then read the result off an attribute on the next statement. Fixed at the two sites the
  audit counted; recurs roughly a dozen more times, uncounted:
  `RawDataView.py:1416-1443`; `MetadataView.py:1411-1445`, `:1472-1490`, `:2021-2030`,
  `:2063-2072`, `:2306-2330`, `:2340-2348`; `ProteinView.py:421`, `:1583-1592`,
  `:1770-1779`, `:1872-1881`; `ClusteringView.py:286-295`, `:579-601`;
  `EventAnalysisView.py:940-964`. **Deferred deliberately, and not a correctness problem
  today**: the six `.connect()` calls carrying this bus pass
  `type=Qt.ConnectionType.DirectConnection` explicitly, so the callback is guaranteed to have
  run and a future thread move fails loudly instead of degrading to a stale read. It also
  cannot be fixed the way the two counted sites were - `MetaController`/`MetaView`
  deliberately hold no reference back to `MainController`, which is what keeps analysis tabs
  pluggable, and a real `Signal.emit()` cannot hand back a return value even over a direct
  connection. What is left is structural clarity, at the cost of a multi-file refactor over
  Views with heavy test coverage.
- **Routine states still logged at `WARNING`.** ~109 `logger.warning` + 16
  `logger.exception` sites under `poriscope/`. **None interrupts anyone**, since `QtHandler`
  floors at `ERROR`, so this is a log-signal problem and deliberately not urgent. Families
  worth working from:
  - Per-event/per-channel "skipping"/"proceeding without" notes logged at WARNING from inside
    worker generators: `RawDataView.py:853, 869, 881, 1071, 1549`,
    `EventAnalysisView.py:419, 436, 588, 950`, `ProteinView.py:1103, 1152`,
    `RawDataModel.py:101, 109`, `MetaDatabaseWriter.py:178-180`.
  - "No selection"/"select only one" user guidance at WARNING across `MetadataView`,
    `ProteinView`, `RawDataView` and the three controllers' `"No column names received"`.
    These belong on the panel rather than in the log at all.
  - Sites already emitting to the panel *and* logging at WARNING for the same event
    (`DataPluginController.py:155-161`, `:470-476`; `MetadataView.py:1848-1849`;
    `ProteinView.py:1343-1344`) are the model for the intended pattern.
  Deliberately staying at `ERROR`, so do not "finish the job" on these:
  `main_model.py`'s plugin-import failure, `ClusteringView.py:530`'s empty dataframe, and
  `SQLiteDBLoader.py:605`'s missing `id` column.
- **The plugin loader executes modules before knowing they are plugins.** `load_plugin`
  calls `exec_module` on every `.py` file before checking whether it holds a plugin, so a
  helper module executes during discovery and reports as a plugin failure if it raises; and
  it never registers modules in `sys.modules`, so two plugins importing a shared helper by
  file each get their own copy. Worth folding into compliance-gate block 4.

### Moderate

- **`@log` costs roughly 291 ns per call above an undecorated method, with logging off.**
  Measured 2026-09-02 over 300,000 calls: 330 ns/call against 39 ns undecorated, after the
  lazy-name fix. Almost all of it is the wrapper's own call machinery rather than anything a
  level check can skip, so the only lever is not decorating the hottest methods -
  `get_key()` and `WaveletFilter._apply_filter` are the candidates. Profile a real analysis
  run before removing either; 291 ns only matters at a call rate nothing has demonstrated.
- **`apply_settings` aliases the settings dict it is handed, and session history holds the
  same object.** Do **not** fix this by copying at `self.raw_settings = settings` - measured,
  the alias is load-bearing. `DictDialog.__init__` aliases the dict it is handed and
  `get_result` returns that same object, so in `edit_plugin` `new_settings is app_settings`;
  `history["settings"]` therefore holds `app_settings`, filed into `plugin_history` by
  reference. `edit_plugin` then swaps plugin-typed `Value`s for live plugin instances, and it
  is `apply_settings` writing back *through the alias* that repairs the dict history holds.
  Copy there without first fixing that ordering and session history holds live `QObject`s for
  `save_session` to serialise. **Fix the ordering first, then the alias.**
- **`save_session` re-serializes the whole history on the GUI thread on every plugin
  change**, deep-copying and rewriting the entire session file whether or not the change
  touched most of it.
- **The 161 `except Exception` handlers are inconsistent about what they leave behind.**
  `validate_and_instantiate_plugin` alone has six sequential try/except/log/return blocks, so
  a failure leaves the UI partially updated with no indication of which stage failed.
- **Oversized units, measured.** Five functions exceed 300 lines:
  `metadatacontrols.setupUi` (524), `PeakFinder._classify_folded_unfolded` (446),
  `proteincontrols.setupUi` (439), `_classify_translocation_direction` (391),
  `_locate_sublevel_transitions` (377). `ProteinView.py` is 4,027 lines across 83 methods;
  `MetadataView.py` 3,598 across 70. `MetaDatabaseLoader` declares 21 abstract methods over
  1,344 lines, which is the real implementation burden behind the compliance gate below. The
  mechanical win is the `setupUi` methods - straight-line widget construction, extractable
  into per-panel builders without touching behaviour.

## What to pick up next

Two standing constraints reshape the queue:

- **Another developer owns test-writing.** Do not edit her existing suites. A new test file
  overlapping no existing suite is acceptable for covering tooling you have just built (as
  `tests/unit/scripts/test_new_plugin.py` does), but taking on a test suite as the piece of
  work itself is hers. Blocks 1 and 7 were handed to her on 2026-09-02.
- **Logic changes need a plan the user approves first.**

1. **Block 5, the CI half.** Marking the Docs Render Check (`docs-check.yml`) as a required
   status check is an admin-only step outside the repo. Block 5's step 2 wants block 1's
   conformance suite, now the test developer's; its schema-check half needs nothing built,
   since `tests/unit/plugins/test_plugin_settings_schema.py` already sweeps all 24 plugins
   and `ci-fork-pr.yml` runs `pytest -q` with no marker filter. The required-review toggle
   is **not** outstanding work - advisory-only was chosen deliberately.

Then the rest of the Moderate audit tier, the `hist_data` refactor, and the parked
histogram cut-off.

## Action history: record a declared action name, not a method name

**Deferred out of Step 7 on 2026-09-22** as its own feature design step rather than release
mechanics. `DECISIONS.md` 2026-09-17 settled *what* to do; what moved is *when*.

**5** `@register_action` sites over **3** names, all private, replayed off the View:
`_reset_actions` on `ClusteringView`, `MetadataView` and `ProteinView`, plus
`MetadataView._overlay_plot` and `ProteinView._update_distribution_ensemble`. Replay is
`getattr(self, name)` on the View via `MetaView.update_actions_from_json`, so renaming a
decorated method breaks saved `.json` files today.

Saved action files carry **no compatibility obligation** (Kyle's ruling - the feature is
barely used), so the design is free:

- `@register_action("overlay_plot")` records a declared name instead of `func.__name__`.
- Replay dispatches through the registry those declarations build, not `getattr`, so an
  unknown action name is reported rather than called.
- Recorded arguments stay small and JSON-round-trippable - user intent, not bulk data.

Breaking, and to be called out as such whenever it lands.

**It also has to fix a live defect, which is the reason it is a design step and not an
edit.** A replayable action must be a pure function of its recorded arguments, and both
non-trivial decorated methods call `get_selected_filters()` inside their own bodies, reading
the combobox. Everything else they need arrives in the recorded `parameters`, so replaying a
saved plot applies *whichever filters are selected now* and the plot that comes back is not
the plot that was saved. Recording the selection alongside the rest of the intent is the
obvious fix and needs the registry design above to carry it.

## The metadata export flow is still intermittently flaky

`tests/integration/flows/test_metadata_export_flow_no_gui.py::test_a_channel_exports_its_own_events_and_sublevels`
failed once on 2026-09-22 with `pandas.errors.EmptyDataError: No columns to parse from file`,
then passed three times in isolation and again in a full re-run. It reads an exported CSV
before the writer has put a header in it.

**The changelog entry claiming this was fixed is about the same test and the same cause** -
it waited for the exported-file count to settle, which happens before the last files are
written. That fix narrowed the window rather than closing it: the count settling still does
not mean the contents are there. A fix has to wait on the *file* being complete, not on how
many of them exist.

Unrelated to the reader work it surfaced during - the test references neither `MetaReader`
nor `load_data`, and reads a synthetic database.

## The two Chimera readers are near-identical, and the deprecation resolves it

`ChimeraReader20240101` and `ChimeraReader20240501` differ in **27 lines of ~396**. The only
real difference is `_get_configs`: 2024-01 parses a JSON header embedded in the `.log` file,
2024-05 reads a companion `.json` of the same stem. Everything else - `_map_data`,
`_get_file_pattern`, `_get_file_time_stamps`, `_get_file_channel_stamps`, `_set_raw_dtype`,
`_convert_data`, `_convert_raw_data` - is byte-identical, and the pair is the largest single
contributor to the `datareaders` duplication figure (446 after 7c).

**Do not give them a shared base.** `ChimeraReader20240101` is slated for deprecation in a
future cycle (Kyle, 2026-09-22), so making the surviving reader subclass it - the
`LegacyElementsReader(TCossaLabABFReader)` pattern this family already uses - would mean
unpicking the inheritance before anything could be deleted. Deprecating 20240101 removes the
duplication for free, and should take `datareaders` to roughly 100.

If it has to move sooner, the direction is the other way round: `ChimeraReader20240501`
absorbs what it needs and stands alone, leaving 20240101 a clean deletion.

## Still queued

- **The metadata query's table aliases are only half parameterised.**
  `MetaDatabaseLoader.py:1021-1029` builds an alias map that feeds the projection and the
  WHERE qualification, but the JOIN's `ON` clause hardcodes `s.event_db_id`. Renaming the
  `sublevels` alias emits `JOIN sublevels sl ON e.id = s.event_db_id`, which is invalid SQL.
  Latent - nothing changes the aliases today - and live the moment Step 4b does. Found by
  perturbing the alias to verify `tests/unit/utils/test_metadata_query_goldens.py` was
  actually sensitive.
- **`format_axis_label` truncates a column name containing parentheses.** The pattern
  `\s*\(.*?\)$` is anchored at `$`, so the leftmost match wins and the lazy `.*?` expands
  across every intervening `)`: the strip reaches back to the **first** parenthesis, not the
  last. A column named `Rate (per pore)` plotted with unit `Hz` is labelled `Rate (Hz)`,
  silently losing `per pore`; `a (b) (c) (d)` collapses to `a`. Two copies,
  `ProteinView.py:4037` and `MetadataView.py:3645`; `ClusteringView.py:731-742`'s inline
  builder is unaffected because it never receives a label with a parenthetical. Behaviour is
  pinned in `tests/unit/views/test_duplicated_helpers.py`, so a fix must update those tests.
- **`pytest.ini` sets no `pythonpath`, so `tests.*` imports resolve only by luck.**
  `pytest tests/unit/views/test_event_analysis_view.py` alone fails with
  `ModuleNotFoundError: No module named 'tests'`; it works only when `tests/e2e/conftest.py`
  is collected first. Step 2 branch 1 adds `pythonpath = .`. **The 13 dead `sys.path` shims
  in the e2e test modules are then deletable** - each is placed *after* the import it exists
  to enable, so none of them ever did anything.
- **Two view test modules mock the view's `logger`**, which `tests/unit/views/_qt_mocks.py`'s
  module docstring explicitly warns against: `test_raw_data_view.py:73` and
  `test_metadata_view.py:97`. Every `caplog` assertion in those two files is blind. They also
  hand-mock `global_signal` instead of using `shadow_signals`.
- **`tests/conftest.py:8-15` describes a `tests/unit/models/conftest.py` deleted in
  `c99249ea`.** The `main_model` fixture now lives at `tests/unit/models/test_main_model.py:25`
  and relies wholly on the autouse `sandbox_user_data_dir`.
- **`ProteinView._build_load_event_data_args:1957-1967` appends a scope clause to arbitrary
  user SQL on a naive `"WHERE" in scoped_query.upper()` test**, so a `WHERE` inside a subquery
  or a string literal mis-fires. This is exactly what `MetaDatabaseLoader._split_on_opaque_spans`
  exists to handle, and this path does not use it. `MetadataView` has no equivalent. Step 2
  branch 5 pins the current behaviour; the fix is separate.
- **`test_raw_data_view.py:28`'s module docstring lists `_get_baseline_stats` as covered and
  no such test exists.** Corrected by Step 2 branch 4, which also adds the missing test.
- **Three `scripts/autodoc/` lint sites are ours to fix, and are the only part of the
  declined-rules sweep that is.** Two `S110` in `metaclasses_generate_autodoc.py` and
  `plugins_generate_autodoc.py`, one `S112` in the latter. Fixing them would not enable
  either rule. **Not licence to re-propose the rules** - `DECISIONS.md` records why all six
  stay off, per rule.
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
- **Placeholder guards on UI-supplied plugin keys are applied inconsistently.** A scan of
  every `global_signal` emit in the analysis-tab views whose plugin key is a UI-supplied
  parameter found 19 sites with no placeholder check in the emitting method. Two were traced
  and are guarded by their callers, which is very likely true of most of the rest. The three
  that were not guarded anywhere were the reactive `update_units` methods, now fixed. Audit
  the remaining 17 properly: the distinction that matters is reactive (runs on plugin-state
  change or combobox repopulation, so the placeholder is live) versus action-driven.
- **`EventWorker`/`MetaModel`'s worker lifecycle has no test coverage**, nor do
  `QtHandler.py` and `App.configure_logger`. All of that work landed verified by throwaway
  scripts. Owed by whoever owns test-writing; the scenarios worth encoding are:
  - *Generator failure*: happy path, mid-run `TypeError`, abort, empty generator.
  - *Worker cleanup*: two independent runs to completion, each popped from
    `workers`/`threads`/`generators` without affecting the other, `deleteLater()` not raising.
  - *`QtHandler`*: default `ERROR` level; DEBUG/INFO/WARNING raising no dialog; one ERROR
    raising exactly one; four distinct errors behind an open dialog all shown; fifty
    *identical* errors collapsing to one; `update_logging_level` lowering every other handler
    but leaving `QtHandler` at `ERROR`; the dialog body carrying the bare message.
  - *Abort*: `MetaModel.stop_workers` logging INFO rather than WARNING for a stale key and no
    longer being silent for a stale channel; `MainController.handle_abort_all_analysis`
    reaching every open tab without `exiting=True`.
- **A worker blocked on a lock cannot observe an abort.** `Worker.stop()` only sets
  `stop_requested`, read on the generator's next turn, so a channel queued behind a
  serial-mode lock keeps waiting until it acquires. Pre-existing; per-instance locks shorten
  the queues but do not change this.
- **`tests/unit/plugins/` has no `conftest.py`, so its widget tests leak real windows.**
  Observed 2026-09-02 on Windows: dialogs and console windows flash throughout, and a
  `StepDialog` built with the walkthrough tests' placeholder steps outlived the run as a
  ghost window. Nothing sets `QT_QPA_PLATFORM=offscreen` locally, so on Windows every test
  widget is a real on-screen window and this tree gets none of the teardown
  `tests/unit/views/conftest.py` provides. Cosmetic, and belongs to whoever owns the test
  suites; mirroring the views conftest is the obvious fix. Setting the offscreen platform in
  `pytest.ini` would silence it globally but should be measured against the full suite first,
  since it can change widget behaviour.
- **`MetaView.lock` is a class attribute shared by every tab view** (`MetaView.py:90`). It
  guards `progress_bars` in `remove_progress_bar` only; the other three accesses (`:282`,
  `:287`, `:325`) are unguarded, so the lock does not establish the invariant it appears to.
- **`ProteinView._update_distribution_ensemble` does not reset on a plot-type change**
  (`ProteinView.py:2345`). It resets only when the bin request changes, so switching Raw
  Histogram to Filtered Histogram with the same bins superimposes the two. The same defect
  the Metadata tab's event overlay had, fixed 2026-09-14; Step 4's branch 5 owns this file.
- **A short status-panel message can be lost under a long SQL echo.** Reported 2026-09-14:
  a plot refusal did reach the panel and was scrolled past beneath the applied-query echo,
  which runs to many lines. The panel has no severity marking and no filtering.
- **`hist_data` holds two shapes in `MetadataView`.** The three 1-D paths now all append a
  raw column array; the all-points path appends an `(x, y)` tuple. Step 4's closeout took it
  from four shapes to two. `ProteinView`'s copy holds only the tuple. Typed `List[Any]` with
  a comment; unifying the last two is a real refactor.
- **`pydoclint` class-attribute bug - filed upstream, awaiting a fix.**
  https://github.com/jsh9/pydoclint/issues/304. Nothing to do here until a release lands;
  `check-class-attributes` stays `false`. Kept in case the report needs restating: the
  one-line fix is to replace the two hardcoded `".. attribute ::"` literals in
  `rest_attr_parser.py` with `re.compile(r"^\.\.\s+attribute\s*::\s*(?P<name>.+)$")`, which
  accepts both spellings. Reproduction: a class documented with the *correct*
  `.. attribute::` directive plus any `:param:` block reports `DOC601` + `DOC603`; adding a
  space before the `::` makes it pass. Full diagnosis in `DECISIONS.md`.

## Widget ownership left over from the event-filter work

Neither is a crash risk; both are ownership tidiness. `DECISIONS.md` records why the filter
itself stays on the application.

- **`containerWidget` is still parentless** in both comboboxes (`QDialog(None)`;
  `QWidget(None)` on the Linux branch), so it is owned by nobody and is not destroyed with
  its combobox. Note the original rationale for parenting it - that it would stop
  `_close_leftover_widgets` sweeping it as a top-level - **was measured and is false**: a
  parented widget that keeps its window flags is still returned by `topLevelWidgets()`.
- **`BaseLineEdit` still registers one application-wide filter and one `aboutToQuit`
  connection per instance** (3 per controls build). Both are now harmless - its `eventFilter`
  returns `False` directly and nothing in its body touches a C++ member of `self`. Replacing
  them with a single application-owned watcher would remove the leak outright, but it is a
  new class and a breaking change to something re-exported from `exposed.py`.

## Exclusions (standing project policy)

- `NanoTrees.py` — a **deprecation candidate**, not an ownership question: its co-author has
  left the lab and `CODEOWNERS` assigns it to `@shadowk29` with the rest of `eventfitters/`.
  Fixing anything in it is permitted but not worth the effort while deprecation is on the
  table.
- `Basic_PeakFinder.py` / `PeakFinder.py` — logic owned by another developer, who is active.

**Docstring, signature and type-hint changes: in scope.** All three are fully annotated and
report zero pydoclint violations.

**Logic changes: out of scope, unconditionally**, even when annotating surfaces a real bug.
Write the honest annotation describing what the code does today, mark the defect with a
narrow `# type: ignore` and a `NOTE:` at the site, record it below, and leave the fix to the
owning developer.

## Defects in the formerly excluded fitter plugins - flagged, never to be fixed here

- **`find_mode_blockage_level` guards two of its three Optional parameters.** The body
  handles `data is None` and `baseline_std is None`, then computes
  `abs(data_min - baseline_mean)` with no guard on `baseline_mean`, equally `Optional[float]`
  under the contract. **Now open only in `Basic_PeakFinder.py`** - `PeakFinder.py` has since
  gained an explicit `raise RuntimeError`.
- **`PeakFinder.filter_peaks` multiplies by a possibly-`None` `baseline_std`** at
  `type0_thresh`/`type1_thresh`/`type2_thresh`. Same root cause.
- **`Basic_PeakFinder._populate_event_metadata` can put `None` into event metadata**, whose
  declared value type is `Union[int, float, str, bool]`. A `None` reaching the database
  writer is not something that contract allows for.
- **`Basic_PeakFinder` writes `NaN` into `sublevel_current` for 23 of 25 events** on the
  conformance dip fixture, from a `numpy.mean` over an empty slice - a zero-width level
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
  `PeakFinder.py:736`'s `varS = 0` sits at the `while` loop's indentation rather than inside
  the jump-accepted block, so the Welford accumulator is never reset at a detected changepoint
  and the variance estimate is inflated (~586x one sample after a transition, ~5x after a
  hundred). Fixed in `CUSUM.py`/`ClassicCUSUM.py` on 2026-09-03 against the C reference; this
  copy is left for its owner. Note `PeakFinder` uses `threshold = step_size` directly rather
  than `_calculate_threshold`, so the magnitude above is indicative, not transferred.
- **Both PeakFinders' `sublevel_starts` really holds dicts, not indices.** Now consistent
  rather than broken - the `MetaEventFitter` contract was widened to `List[Any]` to match what
  it has always produced - but the parameter name still says "starts" while the payload is
  per-sublevel records.

## Open against the PeakFinder integration

- **The histogram low-end cut-off in the classifier plots.** The "All Events" bar chart is
  binned against edges computed from a *filtered subset*, and `np.histogram` silently discards
  values outside the given range. Which subset wins is decided by discrete ratio tests, so the
  left edge jumps to the 25th percentile when the blockage-filter re-run branch fires - which
  is why the cut-off appears at some threshold settings and not others. Three call sites share
  the pattern. The fix is to build the histogram once from the full data and pass it into the
  fit, rather than letting the fit dictate the plot's bins.
- **A log-normal higher component in `PeakFinder.fit_threshold`.** The upper population of a
  real prominence dataset is right-skewed (skew +2.09), and a log-normal beat a Gaussian on it
  by 24% RMS (12.4 vs 16.4) when both were fit above the valley. Deferred because it breaks
  the six-element `params` contract that the plotting code and all three `_classify_*` methods
  unpack, and needs a decision on how a mixed Gaussian/log-normal result should be reported.
  Do **not** revisit Poisson-weighted `curve_fit` alongside it: measured on the same data it
  makes the fit worse unless paired with tail trimming, and the pairing is cliff-edged.

---

# Future Fix: Community-Contributed-Plugin Compliance Gate

Designed as a set: a pipeline that lets a community-contributed plugin be verified as safe
and correct to merge with a bounded amount of human review. Blocks 2, 6, 7 and 8, and block 3
are done and their sections are gone (block 8's "no custom lint rules" call is recorded in
`DECISIONS.md`, 2026-09-01). What is left is **5** (free-standing), **4**, and **1**, which
is a pytest suite and so the test developer's.

## 1. Behavioural conformance suite — remaining gaps

All eight `Meta*` families are covered in `tests/unit/plugins/conformance/`, `PeakFinder`
included, and no fitter is exempt; see `changelog.md`. Still open:
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

## 3. Contribution scaffold: simpleCalc is still transcribed

HelloWorld is generated now and included from the real files, so it cannot drift.
**`simpleCalc` is still hand-written inline in `simpleCalc/simpleCalc_code.rst`** - its
import roots and its missing abstract methods were corrected 2026-09-22, but the code has no
executable counterpart and nothing checks it. It wants the same treatment: a real set of
files under `docs/source/_static/examples/`, `literalinclude`d, so `ruff` and `black` see
them. Bigger than HelloWorld because it is a worked example with real widgets, not a scaffold
the generator can emit.

## 4. The plugin trust boundary — largely settled

Both static gates exist (`ruff-plugin-security`, `plugin-module-level`). `DECISIONS.md`
(2026-09-02) records why there is no `bandit`, why the module-level check skips
`analysistabs/`, and that this is explicitly not a sandbox. What remains is the loader item in
the 2026-08-25 audit above: `exec_module` runs before the file is known to be a plugin, and
modules are never registered in `sys.modules`.

## 5. Scoped CI gate for `poriscope/plugins/**`

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

**Gotcha.** `ci-fork-pr.yml`'s permissions are deliberately `contents: read`; do not add
anything needing write access. That is `ci-internal-pr.yml`, which is not fork-safe.

**Notes from scoping (2026-08-31).** Exception types vary by format on a 0-byte file
(`ValueError` for Chimera/BinaryReader1X, `struct.error` for ABF2) - inconsistent but
none hang.
