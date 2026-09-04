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

## The 2.0.0 refactor plan claims much of this queue (2026-09-03)

**Read `refactor_2.0.0.md` before picking anything up here**, and check whether the item is
already assigned to a step. Plan artifact:
<https://claude.ai/code/artifact/304ba119-d177-4918-90af-471d6de6bb80>

Root cause behind most of the findings below: the analysis-tab Models are empty (303 lines
across five, four of them `def _init(self): pass`) while the Views are 11,541 lines and carry
77 of the 82 `global_signal.emit` sites. Decisions A-E are recorded in `DECISIONS.md`.

- **1.9.0 is Tier A + B2 + C of the plan's Step 1** - the defects in code the refactor moves,
  the zero-risk deletions, and the CI/tooling tier. Everything else in the High/Moderate tiers
  below ships inside 2.0.0.
- **Do not fix duplication findings here.** The ~1,900 removable lines, `format_axis_label`'s
  drift, `_factors`, `_setup_canvas`'s dead `num_channels`, `hist_data`'s three shapes and the
  five oversized `setupUi` are the refactor itself, not work to do ahead of it.
- **Blocked on the plan's Step 2** (characterization tests, which do not exist): every
  structural change in Steps 3-5.
- **Needs a person, not code**: the test owner must agree to mechanical test re-pointing before
  Step 2 starts, and the fitter owner must be consulted before any `MetaEventFitter` signature
  change, which moves all three owner-held fitters in lockstep.
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
- **`zip()` without `strict=` over plugin-supplied sequences.** `MetadataView.py:2577` zips
  seven fitter-supplied sequences while `num_events = len(event_data)` two lines above sizes
  the subplot grid, so 20 events' data with 18 sets of vlines draws 18 plots into a 20-cell
  grid, silently. The per-site judgement in `DECISIONS.md` for keeping `B905` off does not
  apply to this one.
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
- **Baseline σ is biased high, and the bias depends on `chunk_length`.**
  `ClassicBlockageFinder.py:316` and `BoundedBlockageFinder.py:133` build
  `np.linspace(bottom, top, len(hist))` across the full edge-to-edge span, stretching the
  axis by `bins/(bins-1)`. Measured on pure noise: +14.7% at 10k samples, +4.8% at 100k,
  +2.1% at 1M - so `ThresholdBlockageFinder`'s σ-denominated threshold moves with chunk
  length. Two adjacent defects: `:309-314`'s bin-width algebra cancels to
  `int(n**(1/3)/2)` regardless of noise, and `:336-347`'s window is right-exclusive so it
  holds `2*half_width` bins instead of `2*half_width+1`, leaving the peak off-centre.
- **Session restore corrupts any setting whose value is a type name.**
  `MainModel.replace_class_names_with_classes` converts any string equal to
  `"str"`/`"int"`/`"float"`/`"bool"` into the type object regardless of key - reproduced,
  `Value: "float"` returns as `<class 'float'>`. Both walkers' list branches are unreachable
  as called (a list nested in a dict is never visited), and the two session writes omit the
  `default=serialize_object` the config write at `:530` uses. Writes are non-atomic, so a
  crash mid-write truncates the file `_suppress_session_save` exists to protect.
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
- **Duplication, measured at ~1,900 removable lines.** Ten byte-identical helpers across the
  five `*controls.py` files are 444 of them and want a `BaseTabControls(QWidget)` - all five
  currently inherit plain `QWidget`. `CUSUM.py`/`NoFitter.py` share 411 identical lines;
  `ClassicCUSUM` is a 195-line override differing in 2 lines and wants to be `CUSUM` with a
  `_normalize_step_size()` hook; the two Chimera readers differ in 23 lines of 390;
  `_get_baseline_stats` and `_find_events_in_chunk` are each duplicated across two finders
  (which is why the baseline-σ bug above has two copies); `QObjectABCMeta.py` and
  `QWidgetABCMeta.py` are 49 lines each differing in 2, and their `__new__` overrides are
  dead - only `__call__` is load-bearing, and it is genuinely required (verified: without
  it Shiboken's metaclass lets an abstract QObject subclass instantiate).
- **`format_axis_label` has drifted between its two copies** - a module function in
  `ProteinView.py:4052` and a method in `MetadataView.py:3627`, disagreeing on a
  whitespace-only unit (`Label ( )` vs `Label`). Symptom of the duplication above.
- **`MainView`'s navigation state is a QLabel's rendered text.** `get_current_view:1079`
  returns `self.page_title_label.text()`, keyed into `self.pages` at `:1052` to decide
  whether to launch a walkthrough; the label starts as `"Home"`, in neither, so the app logs
  a misleading "does not support walkthrough" before the first switch. `on_view_switched`
  writes `self._current_view` at `:1094` and nothing reads it. The five tab Views do this
  correctly with a hardcoded literal.
- **28 attributes are assigned only outside `__init__`**, with 23 `hasattr`/`getattr` guards
  papering over it. `_reset_actions` is never called from any `_init`, so
  `ClusteringView.axes` and `ProteinView.ax_hist`/`ax_vm` do not exist until the first plot.
  `ClusteringView._init:97-99` declares one such attribute with a comment explaining the
  hazard while `self.logs`/`normalized`/`plot`, read three lines away, got none. The e2e
  suite patches one instance rather than surfacing it (`tests/e2e/conftest.py:68-88`).
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
- **`.pre-commit-config.yaml` housekeeping.** `black` runs only at the manual stage, so
  formatting is enforced by CI rewriting contributors' commits rather than by failing them;
  and `scripts/check_plugin_schemas.py` is documented as a gate on the Sphinx QA page but
  wired into no hook or workflow.
- **`scripts/new_plugin.py`'s family table is guarded one-directionally.**
  `tests/unit/scripts/test_new_plugin.py:466-472` asserts each `FAMILIES` entry appears in
  `main_model.py`, not the reverse, so adding a ninth `Meta*` base leaves the generator and
  `--list` silently blind with no test failing. That guard is also a regex over another
  file's source text, so reformatting `main_model.py`'s dict breaks it spuriously.
- **`test_mapping_audit.csv` is stale and nothing executable reads it.** Its
  `LooseMatchFound` column still names files renamed by the very commit that added it
  (`43d556d`). Referenced only from the `test_event_worker.py` note below. Regenerate or drop.

### Found while verifying the 2.0.0 plan (2026-09-04)

Findings the plan's own steps already claim are recorded in `refactor_2.0.0.md`, not here.

- **`ProteinView` has no `update_column_units`, but `ProteinController.py:291` calls it.**
  Not inherited from `MetaView` either; the `AttributeError` is swallowed by
  `main_controller._dispatch_to`, so protein-tab unit labels silently never update. The other
  four tabs either define the method or use `set_units`.
- **`MetaDatabaseLoader.py:1298`'s `if metadata_generator is not None` branch is dead** -
  `_load_metadata_generator` is a generator function, so it is never `None`.

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
- **Two docs screenshots show a sidebar that no longer exists.**
  `_static/images/sidebar_with_tabs.png` and `_static/images/MainView.png` both still show
  the Exit entry, removed 2026-09-02. Needs someone who can drive the UI to retake them.

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
histogram cut-off. **Block 3's analysis-tab half is deferred** until the planned frontend
refactoring lands, to avoid generating triads against a layout about to change.

## Still queued

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
- **`hist_data` holds three shapes.** In both `MetadataView` and `ProteinView` it receives
  1-D arrays from the histogram path, whole DataFrames from the density path, and `(x, y)`
  tuples from the all-points path. Widened to `List[Any]` with a comment; unifying it is a
  real refactor.
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
and correct to merge with a bounded amount of human review. Blocks 2, 6 and 8, and block 3
for data plugins, are done and their sections are gone. What is left is **5**
(free-standing), **4**, block 3's analysis-tab half, and **1** and **7**, which are pytest
suites and so the test developer's.

## 1. Behavioural conformance suite (not just signature compliance) — test developer

**Goal.** Instantiate every discovered plugin and actually run its core methods against
small synthetic data, asserting it behaves like a well-formed member of its `Meta*` family.
`test_plugin_compliance.py` already does the discovery (`pkgutil.walk_packages` plus
`BASE_CLASS_DATA`) but never calls the plugin, so a contribution can satisfy every signature
check and still crash on real data, leak resources, or produce garbage.

**Shape.** A `tests/unit/plugins/test_plugin_conformance.py` reusing that discovery loop but
parametrized over *concrete* classes. One canonical fixture per family from
`tests/synthetic_data/`, and a minimal settings dict built from each plugin's own
`get_empty_settings()` (fill required `Value`s with the `Min`/`Max` midpoint or the first
`Options` entry). One generic check per family, not per plugin: instantiate, drive the real
lifecycle (a finder's event boundaries monotonic, in-bounds and non-overlapping; a reader's
`load_data` dtype/shape matching `get_raw_dtype()`; a fitter's metadata dict carrying the
documented keys), then `close_resources()` and assert no exception and no dangling handles.
Register a `conformance` marker so block 5 can scope it to changed files.

**Gotchas.** It is only as strong as the fixtures are representative - keep trace length,
noise level and event count realistic enough that a finder cannot pass by doing nothing.
Prefer a small dedicated fixture per family over one mega-fixture, so failures stay
attributable. Run it against every existing in-repo plugin first.

**Worth slightly less than it was**, since `scripts/new_plugin.py`'s generated skeleton is now
the first thing such a suite would run against, and that script's own tests already assert
every family's skeleton instantiates and declares a self-consistent schema.

## 3. Contribution scaffold: the analysis-tab half

`scripts/new_plugin.py` generates data plugins for all eight families. The analysis-tab half
is **deferred until the planned frontend refactoring has landed**, so triads are not generated
against a layout about to change. `FAMILIES` is shaped so the three can be added without
rework.

A triad is 8 abstract methods across three files (`MetaController` 2, `MetaModel` 1,
`MetaView` 5) plus the class-name-equals-filename rule and `_init` assigning
`self.view`/`self.model`; nothing else needs registering, which is why a ~100-line triad is a
valid runnable tab.

Two things to know first:

- **The `HelloWorld` example under `docs/source/_static/images/examples/` is stale** and would
  not instantiate: it implements 4 of `MetaView`'s 5 abstract methods (missing
  `notify_plugin_state_changed`) and imports `from utils.MetaView import MetaView`. A
  generator should replace it.
- **The generator's stub-body policy was measured, not chosen.** Re-run the four probes rather
  than reasoning about them: `pass` under a non-`None` return is mypy `empty-body`; a copied
  `:raises X:` above a `pass` body is DOC502; the same field above `raise NotImplementedError`
  is DOC503; raising with no field is DOC501.

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

**Gated on this block:** `scripts/check_plugin_schemas.py` has no pre-commit hook, deliberately
- it would have blocked commits on the six owner-held `Basic_PeakFinder` findings before the
owning developer had seen them. The test suite covers the same ground on every push meanwhile.
`CODEOWNERS` landing does not release this. Wire the hook once the owner has ruled on the six.

## 7. Fuzz / malformed-input testing for data readers — test developer

**Goal.** Catch unhandled crashes in community-contributed parsers on truncated, corrupted or
off-spec binary input - the most likely crash surface for a new `MetaReader`, since readers
parse arbitrary externally-produced files. No current check exercises a reader against
anything but a well-formed synthetic file.

**Shape.** A `tests/unit/plugins/datareaders/test_reader_fuzz.py` parametrized over every
concrete `MetaReader` the way `test_plugin_compliance.py` discovers them. Take each family's
valid synthetic fixture and apply a small, fixed set of *deterministic* mutations - truncate at
several byte offsets, flip the header magic, zero a middle section - rather than open-ended
random fuzzing, which would risk flaky CI. Assert only that each mutation yields either a clean
successful read or a caught, well-typed exception: never an unhandled crash, a hang, or a
silently truncated array. The mutation generation is necessarily format-specific (one "corrupt
this fixture" helper per reader family, not per reader); the assertion logic and discovery loop
are shared.

**Gotcha.** This applies meaningfully only to `MetaReader`. Finders, fitters and filters
operate on already-validated in-memory arrays, so the risk does not transfer.
