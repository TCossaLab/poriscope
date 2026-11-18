# Future Fixes

The authoritative record of open work, under the release it targets (3.0, 3.1, Later,
Owner-held) and grouped by topic. A landed entry is deleted (its history is in `changelog.md`);
won't-fix reasoning goes to `DECISIONS.md`. One to three lines per entry, with the `file:line`
and the measured number.

Sources: the 2026-09-24 review (<https://claude.ai/artifact/NsZSdFtsenMyANLEDLWvKq>; *(by
reading)* marks items derived from the code, not reproduced), the 2026-09-03 review
(<https://claude.ai/code/artifact/0886d408-06de-488d-8a8e-7f6a68206651>) and the 2026-08-25
audit (<https://claude.ai/code/artifact/a1bec2cd-a157-4299-acb3-a135738fee41>).

## 3.0 - trust the numbers

Accuracy tests against ground truth, reader and database correctness, type checking that sees the MVC layer, a Windows CI leg.

**Plan:** <https://claude.ai/artifact/W9G3cHAQvSopQsRrJH6s3z>; each step is re-measured at HEAD
when it comes up.

Steps 0 to 9 have landed, and so has the pre-release half of step 10: the docs dead-link gate, the
saved-file version rule and the user guide's "Upgrading from 2.0" page. `develop` now burns in with
lab users for a few weeks before 3.0 is cut (Kyle, 2026-11-18): no release branch until he says. A
defect found meanwhile is an ordinary fix on `develop`, with its line under 3.0.0.

### Step 10 - release prep, after the burn-in

**Step plan:** <https://claude.ai/artifact/TX3JE9RqmwceSnaipXKHrv>: the rulings, and the commit series
through the release hand-off.

- **Cut 3.0.0 when the burn-in ends.** `git flow release start 3.0.0`; on the release branch, the
  records-and-docs sweep of what changed since the 2026-11-16 trim, then the preparation commit
  (`constants.py`, `CITATION.cff`, the changelog header; this section and the plan link leave this
  file), with a full suite in a clean copy, the wheel installed in a clean venv and the app launched.
  Kyle runs `release finish`.
- **The release manual pass includes the capture-rate check owed since 2026-10-09.** On the Metadata
  tab's capture-rate log filter, a clean timestamp column reports no dropped row, and a column with a
  duplicate timestamp reports one fewer than 2.0 did. Needs the real app.

## 3.1 - responsiveness and state

Tab state onto the Models, heavy work off the GUI thread, CUSUM speed, splitting the large Views.

### Analysis tabs

- **A raw filter's result columns cannot be chosen on a plot axis.** The axis menus list only the
  database's own columns (`metadatacontrols.update_axes:656`), so a computed or aliased column such
  as `max_blockage - min_blockage AS range` is returned by the query but never selectable, and
  every axis is picked by hand even when the result holds only the columns the user selected. Worth
  addressing because shaping the result is the point of a raw filter, and that shaping cannot reach
  a plot. SQL viewers that can plot choose the axes from the query's own columns and preselect them
  automatically. Found in a manual pass; the tests set the axis column directly and cannot see it.
- **Auto-binned histogram overlays re-bin the earlier datasets.** With bins left empty,
  `MetadataModel.overlaid_histograms:450` estimates bins from all overlaid datasets, so each added
  dataset changes the first one's edges (measured on `develop`: 4 bins 56 wide alone, 7 at 32 with
  one overlay, 11 at 20 with two); a fixed bin count does not move. Decide whether to freeze the
  edges at the first dataset.
- **`itertools.tee` buffers the whole subset, raw arrays included**
  (`MetadataModel.py:789`, `ProteinModel.py:663`): a 16 MB peak for 200 events of 80 KB. Use
  two queries or a streaming min/max.
- **Every read and compute path runs on the GUI thread; workers serve only writes and exports.**
  Worst is Protein, with no progress or cancel: `ProteinController.update_individual_distribution:728`
  runs `ProteinModel.fit_histograms:396` (`curve_fit` `:217`/`:289`) and `sample_event_geometries:1232`,
  whose rejection sampler (`_generate_vm_ensemble:829`) is bounded at 200 x 50,000 (`:886-891`), over
  an unbounded event count. Also HDBSCAN/GMM (`ClusteringModel.py:244,271`, from
  `ClusteringController.py:117-120`), `load_metadata_subset`, all-points histograms and KDE. No
  `processEvents()` in `poriscope/`.
- **The View still owns domain state, and the Controller reaches into it**: public View
  dicts read and written at `MetaSubsetTabController.py:1653,1656,1690` (invisible to rule 3,
  which keys on underscores); `relay_query` opens a `QMessageBox` from the Controller
  (`MetaSubsetTabController.py:1895`). Move scope, filters and the event-id cache onto
  `MetaSubsetTabModel`.
- **Two data round trips through the View remain** (14 before action replay, 2 measured
  2026-11-02): Clustering's run (`ClusteringView.on_metadata_loaded:565` receives the rows and
  emits them back at `:646` to `ClusteringController.cluster:80`) and Raw Data's baseline band
  (`RawDataView.py:1113` sends the loaded trace back to `RawDataController.compute_baseline_stats:772`).
  Neither affects replay. Have the Controller go from load to compute and hand the View only the
  result. Why the Clustering one was kept: `DECISIONS.md` 2026-10-27.
- **Plot types are bare strings repeated across Controller and Controls** ("Heatmap"
  4 times in `MetadataController`, 4 in `metadatacontrols`) and persisted in saved action
  parameters; an enum would pin them.
- **Event Analysis channel ticks do not follow the loader.**
  `MetaEventTabControls.update_channels:100` ticks every channel only when the list is empty
  (`is_first_load`, `:118`); a later load keeps only numbers already ticked (`:134`). Measured: first
  load `[0,1,2]` -> all ticked; a loader holding `[5,6]` -> none ticked and Fit Events disabled,
  unexplained - and another recording's channel numbers are not the same channels. Decide the rule
  (tick all on every loader change, or only when nothing carries over) and apply it to
  `RawDataView.update_channels:1410` if it shares the behaviour.
- **Event Analysis dropdowns still allow a crossed loader/fitter/writer selection** (S9a.8-S9a.10
  refuse it after the fact; option 3 of the S9a.8 ruling). Filter the fitter and writer lists to
  the selected loader from the existing loader-change hook (`EventAnalysisView._handle_other_actions:683`
  -> `request_loader_channels`), reusing `EventAnalysisController._parent_key`, and apply it again in
  `update_available_plugins:120` or a plugin change undoes it. Estimate by reading: ~100 lines plus
  ~15 tests, no new signal. Risks: every combobox's `currentIndexChanged` is wired to
  `on_parameter_changed` (`eventAnalysisControls.py:87,182,224,272`), so repopulating loops without
  signal blocking; a restored session selecting a hidden fitter silently falls back to the first
  one; extra `parameter_changed` history entries; a loader with no fitters shows "No Event
  Fitter". Keep the S9a.8-S9a.10 guards, since scripts and replayed actions bypass the dropdowns.
  Needs a ruling on hiding versus greying out mismatched entries. **Not scheduled: first see how
  the S9a.8-S9a.10 refusals are received, and revisit this if users trip over them or ask for the
  crossing to be prevented instead.**

- **The subset tabs pass a channel as the selection tree's digit string where the loader takes an `int` (2026-10-28,
  re-measured 2026-11-11, anchors 2026-11-17).** Six sites: `MetadataController.py:512`, `:734`, `:852`; `ProteinController.py:299`,
  `:627`, `:779`, each handing `{exp: [channel]}` (typed `Dict[Any, Any]` where named) to methods declaring
  `Optional[Dict[str, Optional[List[int]]]]` (`DECISIONS.md` 2026-10-09). No wrong output: the loader renders ids
  with `str()` (`MetaDatabaseLoader._id_tuple`) and the raw path converts with `int()`; `"0"` and `0` gave the same
  queries, rows and counts (2026-11-11). Fix it with `overlay_plot`'s "nothing selected" sentinel `{None: [None]}`
  (`MetadataController.py:359`, and Protein's at `ProteinController.py:179`), refused before any fetch, so the annotation can be true; three Protein unit tests
  pin the string form (`test_protein_controller.py:373`, `:482`, `:894`).

### Session replay

- **Keep a channel's earlier results when a Find/Fit rerun doesn't produce results (2026-11-04).** A rerun clears the
  channel as it starts, so a cancelled, failed or 0-result rerun loses earlier results. A working approach is in
  history: `f4cbcc67` added it and `312fe6c2` removed it (`git revert 312fe6c2` or `git cherry-pick f4cbcc67`).
  - How it worked, on `MetaEventFinder` and `MetaEventFitter` each:
    - Which results belong to a channel: a module tuple naming the per-channel result dicts, `_FINDER_RESULTS` (12:
      event starts and ends, paddings, baselines, counts, rejections, the finished flags) and `_FITTER_RESULTS` (7:
      event and sublevel metadata, sublevel starts, event lengths, rejections, applied filters, the fitted flag).
    - As a run starts, `_set_aside_channel(channel)` `pop`s those entries for the channel into a dict (a move, no
      copy) instead of clearing them.
    - In the run's `finally`, `_put_back_channel(channel, aside)` restores them unless the run finished with results;
      if it did, they are dropped.
    - PeakFinder overrides both to add its six classification dicts (`_CLASSIFICATION_RESULTS`).
    - `last_run` (per channel: finished, no events, cancelled, failed) and `last_run_finished(channel)` record how the
      run ended, since after a put-back the channel reads finished even though the rerun was not.
  - Measured: one extra copy of the rerun channel's results, only during the run: ~1 MB per 10,000 events for finders,
    ~37 MB per 10,000 good fits for NoFitter and CUSUM, ~89 MB for PeakFinder (synthetic 200 and 2,000 events and a
    real 2 kbp recording, `ce836c54` vs `ff3a82a2`, 2026-11-04).
  - Why it is queued: it was the fix chosen for the gap that recording a Find or Fit only once it finishes opens (see
    `DECISIONS.md` 2026-11-03), but it turned out to be an enabler for a bigger change, so it was withdrawn and the
    gap closed in the tab instead. To plan:
    - Where it lives: potentially one copy of the set-aside and put-back on `BaseDataPlugin` (Kyle, 2026-11-04).
      Based on a preliminary review of `f4cbcc67`, it would be shared by every family: each family only declares its
      result fields, and PeakFinder, or any plugin with per-channel results of its own, extends its family's list
      instead of overriding methods.
    - Always on, or an opt-in `keep_previous` on `find_events` / `fit_events`, depending on whether scripts rerun a
      channel on the same plugin instance.
    - A readable outcome (`last_run_outcome`), so a replay can tell a cancel from a failure.
    - 0 results handling. Settled input (Kyle, 2026-11-05): a run with 0 results counts as failed, since it only
      comes from a settings issue (a Find with 0 events, a Fit with 0 good fits); neither is saved in the tab's history,
      live or replayed, but the fitter still marks a 0-good-fits channel fitted, so it can still be plotted and written.
    - The writers refusing a run that did not complete before deleting or writing anything.
    - If earlier results are kept again, keeping the earlier run's history entry instead of removing it.
    - Until then, a rerun that does not finish leaves the figure showing events from the cleared run (as in 2.0); the
      history no longer holds them, so a restore does not redraw them.

- **A "Skip this step" choice when a replayed step fails (2026-11-09).** Today a failed step starts
  nothing new and asks Go back or Keep at once, while runs already going carry on (`ReplaySequence._fail`,
  `MetaView.ask_after_replay_failure`); a later step that had not started never runs, even one that does not depend
  on the failed step. A third button would skip the failed step
  and the steps declared as depending on it, and carry on. Declare first what the declarations miss: Clustering's
  Merge needs the run before it (both only `additive` on `clusters`), and an Event Analysis fit needs the Raw Data
  tab's Find (another tab). Changes the replay rule (`DECISIONS.md` 2026-11-05, 2026-10-17 and 2026-11-17), so it needs a ruling before it is built.
- **A refusal of the user's own click waits for the replay to end (2026-11-17).** While a tab replays, every
  status-panel line it sends is held until "replay done" (`MetaController.panel_text_to_show:489-515`), so "<finder>
  is already running on channel <n>; this request was ignored" (`MetaModel.run_generators:248-250`), answering a Find
  clicked during the replay, showed ~1 min late (manual pass, `a64182ab`, 2026-11-17). Show it at once, as the second-replay
  refusal does (`_panel_text_now`, `MetaController.py:350-357`); the Model cannot tell a click from a replay launch,
  and the fix may need a signal change, so it needs a ruling before it is built.

### Fitter performance

- **CUSUM costs 6.3 µs per sample, flat from 2k to 200k** (1.3 s for a 200k-sample
  event), holding the GIL, so per-channel threads give no multi-channel speedup;
  `IntraCUSUM.py:148` adds a second per-sample loop. JIT or C-port behind a golden ratchet.
  Measured before `38b5d514` moved `ClassicCUSUM` onto CUSUM's detector; re-measure first.

### Data plugin API

- **Database loaders return `None` for a failed query instead of raising**
  (`MetaDatabaseLoader.load_metadata_raw:1409`, `load_metadata:1426`, `query_database_directly:1527`,
  abstract `_load_metadata:1591`), so each of the 6 tab call sites needs an `is None` branch
  (`MetaSubsetTabController.load_event_id_cache:1568`). `DECISIONS.md` 2026-09-04 kept `None` only
  for the signal bus, which is gone: raise on failure. Breaking for loader plugins.

### Structure

- **Emit-then-read-an-attribute survives at one site over typed signals.** It clears the
  attribute, emits a `*_requested` signal, then reads the attribute the Controller's answer
  slot set: `MetaSubsetTabView.py:803-807` (`event_id_rows`). The other Views emit and let an answer
  slot do the work. It works only because View and Controller share a thread: every
  connection is the default AutoConnection (no `ConnectionType` anywhere in `poriscope/`), so
  moving a slot to a worker would queue the call and the read would get `None` - silently
  "no data" rather than loudly wrong.
- **Oversized units, measured 2026-11-16.** 13 functions exceed 300 lines, led by
  `_classify_peak_prominences` (531), `metadatacontrols.setupUi` (525),
  `_classify_translocation_direction` (494), `_classification_section` (488),
  `_classify_folded_unfolded` (447) and `proteincontrols.setupUi` (438); 10 of the 13 are in the
  two PeakFinders. `ProteinView.py` is 1,376 lines across 34 functions; `MetadataView.py` 1,612
  across 40. `MetaDatabaseLoader` declares 20 abstract methods over 1,692 lines, the real
  implementation burden behind the compliance gate below. The mechanical win is the `setupUi`
  methods - straight-line widget construction, extractable into per-panel builders.

### Workers and tests

- **Other flow tests may read a worker's report before it arrives.** `fit_events` and similar
  helpers wait on `model.workers`, which empties before `generate_report`'s queued slot shows the
  report; one test read the fit's report as the commit's under load (fixed 2026-11-17). Delaying
  `generate_report` 1.5 s across `tests/integration` gave 16 failures and 16 errors, but a report
  that fires after its test ends breaks later tests too, so real races are not yet told apart.
  A probe that cancels its delayed reports at teardown would separate them.
- **`EventWorker`/`MetaModel`'s worker lifecycle has no direct tests**, nor does
  `App.configure_logger`; owed by whoever owns test-writing. Scenarios worth encoding:
  - *Generator failure*: happy path, mid-run `TypeError`, abort, empty generator.
  - *Worker cleanup*: two independent runs to completion, each popped from
    `workers`/`threads`/`generators` without affecting the other, `deleteLater()` not raising.
  - *`QtHandler` through `emit`* (`test_qt_handler.py` reaches `emit` only in its replay tests):
    the default `ERROR` level, and four errors behind an open dialog all shown once the queue drains.
  - *Abort*: `MetaModel.stop_workers` logging INFO rather than WARNING for a stale key and no
    longer being silent for a stale channel; `MainController.handle_abort_all_analysis`
    reaching every open tab without `exiting=True`.
- **A worker blocked on a lock cannot observe an abort.** `Worker.stop()` (`EventWorker.py:142-144`)
  only sets `stop_requested` (read at `:99`), read on the generator's next turn, so a channel queued behind a
  serial-mode lock keeps waiting until it acquires. Pre-existing; per-instance locks shorten
  the queues but do not change this.
- **`hist_data` holds two shapes in `MetadataView`.** The three 1-D paths now all append a
  raw column array (`:509`, `:771`, `:839`); the all-points path appends an `(x, y)` tuple
  (`:1208`), down from four shapes. `ProteinView`'s copy holds only the tuple (`:597`). Typed `List[Any]` with
  a comment; unifying the last two is a real refactor.

## Later - worth doing, not scheduled

### Protein two-population calls ignore that filtered samples are correlated (2026-11-18)

Filtered noise stays correlated for a median 11 samples (9-14) on `Ub_250mV_0p2MPa_CUSUM_A1`, so a
100-sample event holds ~9 independent measurements; 5,719 of its 5,997 events are under 100. A
prototype two-component mixture on the samples, BIC (margin 10) with n divided by each event's
padding correlation length, resolves none of the 5,817 events under 150 samples, where the
histogram fit accepts 18; uncorrected it calls 52% of 50-99-sample events two populations. On
events over 150 samples the two disagree (27 both, 77 histogram only, 20 mixture only). Rulings:
replace the fit, decide acceptance only, or only label events too short; validate on filtered
synthetic events first. Write-up: <https://claude.ai/artifact/D7ojrzmfUTXp5Rrq5UD8aJ>.

### The column-names/plugin-state reaction pair is near-duplicated, invisible to the ratchet (2026-10-09)

`ClusteringView` and `MetadataView`'s `update_available_columns` (identical code, differing
docstrings) and `notify_plugin_state_changed` (identical docstrings, differing only in
`clusteringcontrols`/`metadatacontrols`) are near-identical, but `measure_duplication.py` only
catches byte-identical bodies, so the `*View.py` family shows 0 removable. No shared base fits
today: Clustering isn't in the `MetaSubsetTabView` family, and `MetaView` would spread the pair
onto RawData/EventAnalysis/Protein too. Consider a mixin for just `{MetadataView,
ClusteringView}` once a third tab needs this capability, or widen the ratchet to catch
near-identical bodies.

### Provenance stops at the fitter (2026-10-08)

A database's `channels.provenance` records the writer, the fitter and the event loader, which is
all the database writer can reach. The reader, finder and filter that produced the events are not
stored in the events file (`SQLiteEventWriter.py:84-118`), and a filter is a callable, never a
setting. Carrying them needs the events writer to record them and the event loader to expose them.

### Controller-side `call()` is a convention, not a checked invariant (2026-09-17)

`check_mvc_boundary.py`'s rule 5 (`plugin_reaches:532`) bans every route to a data plugin
*except* `call()`, and walks `tab_layer_modules()` as one set without asking which layer a
module is - so nothing distinguishes a Model making a plugin call from a Controller making
one. Measured 2026-11-16: **63 `self.model.call(...)` sites across the Controllers (49 on
2026-09-24), 0 direct `self.call(...)`, 18 in the Models** - the narrowness has held on review alone. Consider an
allowlist of named wiring operations for Controller-side `call()` before the accumulation is
real; latent today, and the same soft governance as `_get_plugin` staying private.

### Shell and shared-widget duplication (2026-09-27)

- `MainView` menu table: 10 `addMenu` + `add_plugin_actions` blocks at `main_view.py:450-504`
  and the one-line `on_load_*` wrappers (`:610-780`).
- `MainView.get_milestone_step:1471` wraps each highlight getter in `lambda: [...]` and unwraps
  it with `[0]` (`:1478-1500`); store the getter. `populate_plugins_menu:699`
  mixes building the menu with 20 lines of anchor-position arithmetic (`:728-748`).
- `SettingsWindow` rows hand-built as HBox + widget + `add_horizontal_line()` in
  `add_general_tab_contents:504`, `add_advanced_settings_tab_contents:571`,
  `add_about_tab_contents:669`; two opposite 6-entry log-level dicts at `:772` and `:786`.
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
  (`icon_menu_widget.py:296`, `text_menu_widget.py:277`), six `set*Checked` slots each, and
  `QPushButton:hover` QSS six times. Share the constants and those methods, not the classes.
- `FloatRangeLineEdit.set_range` counts decimal places with the same inline expression twice
  (`float_range_line_edit.py:144-153`).

### Remove the deprecated `ChimeraReader20240101`

- **Its deprecation was announced in 2.0.0** (Kyle, 2026-09-22); apart from that notice it differs
  from `ChimeraReader20240501` only in `_get_configs` (embedded JSON header vs companion `.json`).
  Removing it takes 161 of `datareaders`' 348 removable lines (`measure_duplication.py`,
  2026-11-16). No shared base (`DECISIONS.md` 2026-09-19); if it must move sooner, 20240501
  absorbs what it needs and 20240101 stays a clean deletion.

### Session and settings persistence

- **A reloaded session restores plugins but not what the control panels showed.** Snapshot and
  restore each panel's widget state on `MetaControls` by walking its children keyed by
  `objectName` (not every control sets one today), with `MultiSelectComboBox` and
  `MultiSelectFilterComboBox` supplying their own get/set; modal dialogs stay out of scope. A
  direct snapshot, not an event-sourced log like `@register_action`. Restore with signals
  blocked, after the tab's plugins exist and before the restore dialog offers a replay. A
  replay writes each step's recorded values back into the panel (`ReplaySequence`, through
  `MetaView.write_back`); this is for a tab the user does not replay.

- **Go back replays the live history, not the kept one (2026-11-17).** `ReplaySequence._go_back` replays
  `_history_before`, the live history, so a Find run twice on a channel is run twice after a Go back, where once gives
  the same tab. Replaying `build_kept_history` of it instead would avoid that, but would shorten Metadata's Undo after
  a Go back.

### Numeric input and widgets

- **A disabled OK or action button never says what to fix** (2026-10-10, by reading).
  `DictDialog.check_validity:347` and `TimeWidget._check_validity:171` disable OK with no label,
  tooltip or highlight (`NumericLineEdit.isValid` knows the range but never shows it); the tab
  controls' `validate_inputs` (Event Analysis `:294`, and the other four tabs) only `logger.debug`
  the reason. `ClusteringSettingsDialog.plot_warning_label` (`clustering_settings_widget.py:190-615`)
  is the one that says why. Recommended: a one-line hint naming the first problem and its constraint,
  one helper shared by dialogs and tab controls, plus a tooltip on the disabled button (Qt still
  shows it). The other two validation stacks differ again: `BaseLineEdit` traps focus
  (`event.ignore(); self.setFocus()`, `BaseLineEdit.py:82-83`) and the bare Qt validators check no range.
- **`get_icon` rasterises an SVG at its own small size unless the caller passes `size`**
  (`configs/utils.py:164-167`; 1 of 23 calls does), blurry on HiDPI; its "cleared on each
  process start" comment (`:46-48`) is false - nothing clears `poriscope_icons`.
- **Walkthrough tidiness**: two positioners fight over the card (the card jumps from
  (469,153) to (113,194)); closed `StepDialog`s are never deleted (3 after three runs); a
  `cast()` at `walkthrough_mixin.py:150-151`; dead `QDialog` fallbacks at
  `walkthrough.py:528`, `:535`; `WalkthroughMixin.show_walkthrough_intro` (`walkthrough_mixin.py:316-328`,
  shadowed by `MainView`'s) is reached only by its own tests; the intro text (`walkthrough.py:115`) omits
  Protein and Conditioning.
- **Popup tidiness**: `SelectionTree.show_dialog` has no Cancel; select-all in the filter box
  emits `selectionChanged` N+1 times; the popup lists hide their scrollbar (`multiselect.py:58`).
  The duplication itself is under "Shell and shared-widget duplication".
- **No accessibility work**: no accessible names, `QShortcut`s, mnemonics or tab order
  anywhere in `poriscope/`; sidebar colours hardcoded (`icon_menu_widget.py:72-80`,
  `text_menu_widget.py:79-86`); Windows-only fonts hardcoded 7 times.

### Analysis tabs

- **A recorded Plot Events holds the expanded event list (2026-11-10).** Raw Data's
  `load_event_plot_data` (`RawDataController.py:425`) and Event Analysis's (`EventAnalysisController.py:86`)
  take `events: List[int]`, so a typed `0-99999` saves 100,000 ints, 688,890 bytes of JSON, in the history
  and the session file; `_parse_event_indices` (`MetaEventTabView.py:89`) has no cap. Recording the range
  text changes the action's parameters, so earlier entries would be reported and skipped.
- **An Assisted filter cannot define a derived column.** It is a condition, so
  `max_blockage - min_blockage > 500` selects events, but nothing can put a computed value such as
  `range = max_blockage - min_blockage` on an axis. Worth addressing because it is the one way of
  shaping a result for which the user must leave Assisted for raw SQL, and raw has its own column
  limitation (the entry under 3.1).
- **Event-tab arrows stop at 0 but run past the last event; wrap them (wanted for Raw Data's
  Plot Events), or decline, at both ends.** `MetaEventTabView._shift_range_and_update_plot:220` declines below 0 (`:274`); past
  the end it moves the field and the Controller reports the overflow (`RawDataController.py:439`,
  `EventAnalysisController.py:150`). Pros: matches the subset tabs' wrap, symmetric ends. Cons:
  positions 0..N-1 are not a browsed set, and a multi-range field (`3, 7-9, 15-19`) has no clean
  wrap. Feasibility: the View has no event count (only the Controller reads it), so either needs
  the count pushed to the View or the shift moved to the Controller - a contract change.
- **Check that Abort Analysis and a progress bar's cancel stop a Raw Data event finder.** Find
  Events runs one worker per channel (`RawDataController.find_events_on_channel`); `find_events`
  reads the abort flag at every chunk boundary (`MetaEventTabView.py:398`) and
  `MetaModel.stop_workers:522` stops them, but a cancel can look unregistered when a chunk holds
  many events. Not exercised end to end for finders; confirm both paths stop every channel and
  leave the tab usable.
- **`new_plugin.py` cannot generate a `MetaSubsetTab*` tab**, the likely shape of any
  new database-analysis tab; add `--base subset`.
- **`update_available_plugins` is hand-written in all five Views** (`ClusteringView.py:824`,
  `MetadataView.py:701`, `ProteinView.py:763`, `RawDataView.py:376`,
  `EventAnalysisView.py:136`): `super()`, then a `try` pushing each metaclass list into the panel.
  Metadata's and Protein's are identical but for the panel attribute, so `MetaSubsetTabView` can
  own them through `_subset_controls`.
- **The "my selected loader gained columns" guard is written twice**:
  `ClusteringView.notify_plugin_state_changed:841` and `MetadataView:726` (Protein's is a no-op).
- **Overwriting committed columns is built twice**: the confirm (`ClusteringView.on_cluster_column_checked:326`,
  `ProteinView.confirm_fit_commit:325`) and the drop (`ClusteringModel.drop_cluster_columns:244`,
  `ProteinModel.drop_fit_columns:360`); Protein's `drop_fit_columns(loader, table, columns)` is
  already the general form. Protein's prompt reads "fit data data already exists" (`ProteinView.py:345`).
- **Figure reset differs per tab**: `ClusteringView.clear_plot:162` guards `figure.clear()`
  with `except AttributeError` where Metadata has `_clear_figure_state:185`/`_axes_valid:225`, and
  `ProteinView.clear_plot:517` runs clear/add_subplot/tight_layout/draw once per figure of the mode.
- **A repeated column is refused two ways**: Clustering raises `KeyError`
  (`ClusteringView.py:559`), logged at ERROR by its caller after the config is already saved
  under its title; Metadata says so on the status panel (`MetadataController.py:483-489`) and its
  panel already disables Update Plot (`metadatacontrols.py:882-952`). The clustering dialog's
  `_check_apply_enabled` (`clustering_settings_widget.py:569`) could refuse it the same way.
- **`MetaEventTabController.update_available_plugins:79` re-implements the base** with the Model
  pushed before the View (`MetaController.py:930` does View first). Only `ConditioningController.py:254`
  reads `MetaModel.available_plugins` (`MetaModel.py:390`), outside this family, so the override
  is a debug log; delete it.
- **Clustering has no named-filter layer**: one anonymous `QTextEdit`
  (`clustering_settings_widget.py:132`), validated only at apply, where Metadata and Protein name,
  save, reload and multi-select filters through ~16 methods on `MetaSubsetTabView` (1,375 lines,
  34 methods). Validation is already shared (`construct_metadata_query`). Putting
  `ClusteringView` under `MetaSubsetTabView` would inherit its scope and event-cache state, so the
  shape is a thin base holding only the filter dict, the add/edit dialogs and save/load, under
  both. Worth it when raw SQL filters are built, or Clustering keeps refusing a `SELECT`.

### App shell and plugin management

- **The plugin-name uniqueness loop is written twice**: `DataPluginController._rename_plugin:274`
  and `_key_is_unused:987`, differing only in the rename also restoring parent links.
- **Deleting from the edit dialog** (`_complete_requested_deletion:226`) re-implements
  `delete_plugin:643` and posts no "deleted" message to the panel.
- **`instantiate_analysis_tab` wires seven tab signals as seven `connect` calls**
  (`main_controller.py:755-776`); `MainView.connect_signals:255` already has the table form.
- **`sys.path` only grows**: `update_user_plugin_location` (`main_controller.py:213-216`) and
  startup (`main_app.py:122-125`) append the plugin folder and its parent and never remove a
  previous one, so after the folder changes an abandoned folder's module still wins a name clash
  until relaunch.
- **A user tab's view and model class names are not checked for uniqueness at load, and the page
  guard guesses a non-dedicated tab's view as `<Name>View`.** `main_model.py:269-283` dedups only the
  controller; `scripts/new_plugin.py:1687` checks all four names but a hand-written tab skips it. Two
  user views sharing a bare module name may collide in `sys.modules` (not reproduced).
  `MainView.on_load_analysis_tab_button_click` guesses the view name from the controller name.
  Reproduce the collision first. Then read each controller's `view:`/`model:` annotations
  (`typing.get_type_hints`, no instantiation) in one helper, treating the inherited `MetaView` as
  undeclared; use it to reject a taken name at load and as the guard's exact page name, falling back
  to the guess. Makes an optional `view_class` and a base class that builds the view unnecessary.
- **The walkthrough overlay does not block clicks outside the highlighted widget.**
  `Overlay` (`walkthrough.py:165`) sets `WA_TransparentForMouseEvents` (`:177`), so only the
  page-switch refusal and the icon guards in `MainView` stop an out-of-sequence click. Mask
  everything except the target. The Plugins dropdown is a separate `QMenu` popup the overlay
  cannot reach, so it needs its own handling.

### Base-class internals

- **Undo finds a reset by its name, not its figure (2026-11-04).** `MetaController.py:998`, `:1014`
  stop at the last `RESET_ACTION` whatever figure it clears; harmless while Metadata, with one figure,
  is the only tab with Undo. Match the declared figure before a tab with two figures gains Undo.

The rest are readability only; each is behaviour-preserving and wants the covering tests read first.

- `LogDecorator.log`'s one-shot latch is the same block in `log_call` and `log_return`
  (`LogDecorator.py:165-173`, `:180-188`). One helper over a module-level latch also retires the
  two `setattr`s `DECISIONS.md` 2026-09-02 keeps.
- `MetaController.update_tab_actions`' undo walks back through nested `try/except
  KeyError`/`StopIteration` (`MetaController.py:998-1018`); `handle_kill_worker:820` nests three
  deep; `MetaView.update_progressbar:431` (74 lines) builds its widget inline; `MetaModel`
  repeats `if key not in self.<dict>` four times (`:244-286`).
- `MetaEventFinder`: boundary reconciliation is duplicated in `find_events:332-346` and
  `_find_events_single_range:575-591`; four comprehensions test `idx not in bad_indices` against
  a list (`:545-560`, quadratic - use a set); the `end is None or end == 0` re-check at `:291`
  cannot fire after the normalisation at `:268-278`.
- `MetaEventFitter.fit_events` coerces `padding_before` and `padding_after` with the same seven
  lines twice (`MetaEventFitter.py:602-617`).
- `MetaReader._get_file_index:863` ends its scan by catching `IndexError` (`:879`);
  `bisect_right` says what it means.
- `MetaDatabaseLoader`: the experiment/channel scope clause is hand-built three times
  (`:511`, `:1236`, `:1341`, only the last alias-qualified), and
  `export_subset_to_csv:569` repeats validate/query/raise five times (`:604-683`).

### Database

- **37 hand-rolled `sqlite3.connect`/`finally` blocks** across the SQLite plugins.
  `MetaWriter._commit_events:367` threads an abort flag through four `try` levels;
  `MetaDatabaseWriter.write_events:103` nests `lookahead_generator` (`:117`), repeats
  try/`close_resources`/log/raise for its setup steps, and its `index = 0` (`:178`) is dead -
  `:192` reassigns it before any read.

### Plugin contract

- **`_validate_param_ranges:582` rejects any `None`** (`:602`), so a plugin cannot declare an
  optional parameter.
- **Nothing bounds a plugin's `close_resources()`**: Reset Session and quit call it unguarded
  (`DataPluginModel.py:217`, `:243`), so one that hangs freezes the app without naming itself. A
  threaded timeout was built and reverted (`DECISIONS.md` 2026-08-31): doing it means
  `check_same_thread=False` on the two writers' `self.conn` (`SQLiteDBWriter.py:304`,
  `SQLiteEventWriter.py:579`), the quit path routed through the same guard, and "callable from
  another thread" added to the contract (`BaseDataPlugin.py:268`), which already asks for idempotence.

### Types, tests and CI

- **`test_replay_runs_together_no_gui.py` records a real Find for each of its three tests** (the `recorded`
  fixture, about 1.1 s of setup each; 2026-11-18 audit). Build the recorded history once for the module; it needs
  a wait helper that is not tied to the per-test `qtbot`.
- **`--time-budget` and the duration check only warn.** Once on develop, build
  `tests/test_duration_baseline.json` from the median of several Linux 3.12.0 CI artifacts. Add a `history` report
  to `scripts/test_durations.py` that reads the last 30 develop runs' artifacts, counts false failures (over budget
  in one run, within it in the runs around it, the test unchanged) and lists tests near their budget; switch
  `--time-budget` to failing when it counts none (`DECISIONS.md` 2026-11-17).
  `test_peak_finder.py::test_two_channels_fitted_together_each_get_their_own_report` took 4.8 s serial and 6.3 s
  under 2 workers (local, 2026-11-17) against its 5 s budget.
- **Mocks are almost all unspecced**: 698 bare `Mock()`/`MagicMock()` against 23
  `spec`/`autospec`/`spec_set` (2026-11-16). Adopt specs one fixture file at a time, controllers
  and views first.
- **Coverage cannot see QThread code** (no `.coveragerc`, no `concurrency`), so
  `EventWorker` (51%) and the writers (60-69%) read lower than they are.
- **A root `__init__.py`** has been tracked since the initial commit; harmless only
  while `tests/` has none.
- **The SQLite writers commit once per event (2026-11-02).** `SQLiteDBWriter._write_event` and
  `SQLiteEventWriter._write_data` take a savepoint per event with no transaction open, so each `RELEASE` commits:
  48 commits for the 40-event `sample_metadata_db` build, 10 with one transaction per batch (probe). Two Windows CI
  runs timed out on a stalled commit (40965910820, 41521392204; 2 of ~56 runs since 2026-10-05, a different test
  each time, not tied to a commit). The integration tests now build that database once per run (~40 commits instead
  of ~10,000 per Windows run); delete this half once Windows CI stays clean. The e2e `synthetic_metadata_database`
  fixtures still build through the writer in every test.
  One transaction per batch is not the fix: with it open, a Clustering or Protein `SQLiteDBLoader.alter_database`
  commit into the same file raised "database is locked" after 5.5 s. Measure the commits' share of a 10,000-event
  write first; if it matters, commit about once a second, which keeps every wait under sqlite3's 5 s.

- **A contributor cannot run the replay guard on their own tab (2026-11-17).** `test_replay_guard_no_gui.py`
  checks only the six tabs Poriscope ships with (`TABS`). A way to point it at a contributor's tab would check that a
  replay reproduces the action, that no recorded action reads a widget, and that each view names its run in
  `depends_on`, which a replay now relies on to order a view after its run. Left out for now because a contribution
  is checked as any other is: static checks (the plugin compliance test, mypy, pydoclint, ruff, the module-level code
  and settings-schema hooks) cover its shape, and nothing runs its logic. The guard would; worth weighing.

- **The Ubuntu test job aborted once in native code (2026-11-03).** CI (Branches) run 41721366639 attempt 1 on
  `a84c70ca`: `free(): invalid pointer`, `Fatal Python error: Aborted`, exit 134, after 954 passing tests; attempt 2
  on the same commit passed (5,428). The commit changed no runtime code. Test #955 in collection order is the first
  of `tests/unit/controllers/test_protein_fetch_slots.py`, right after `test_protein_controller.py`, which builds a
  real `ProteinView`; a Qt widget freed twice at teardown fits, unproven. Not seen in the 30 runs before it, nor in
  a Linux container matching the job (`python:3.12.10-slim-bookworm`, CI's apt packages, `xvfb-run`, 2026-11-03):
  the two files together 40 times, and the whole suite with `-v` and faulthandler twice. If it recurs, rerun with
  `-v` so the crash names its test. Not seen since: the 38 CI (Branches) runs after it, 41728161120 on `a84c70ca`
  (2026-11-03) through 44134467491 on `a64182ab` (2026-11-17), ran 72 Ubuntu test jobs; 67 passed on the first
  attempt, 4 failed on a test assertion (43142602372, 43144925224, 43144951706, 44112181488), 1 was cancelled, none
  aborted. Passing runs cannot show it gone, so watch the next runs before deleting this.

### Docs and records

- **Split `DECISIONS.md` into active and archive**, so a session loads only the decisions
  that still apply (51.2k words at `3511c2de`, before the 2026-11-16 trim; re-measure after it).

### Widgets

- **`WalkthroughStep` is a positional 4-tuple** (`views/widgets/walkthrough_mixin.py:40`),
  built as 90 literals across 7 files. A frozen dataclass names the fields; moves no gate.
- **The two multi-select popups are built differently, and parentless.** `MultiSelectComboBox`
  builds a frameless `QWidget(None)` on Linux and a `QDialog(None)` elsewhere (`multiselect.py:62-72`);
  `MultiSelectFilterComboBox` a `QDialog(None)` on every platform (`multiselect_filter.py:67`), so the
  filter picker never got the Linux treatment, and neither container is destroyed with its
  combobox. Reconciling them changes behaviour on a path CI cannot exercise (`DECISIONS.md`
  2026-09-01, which also keeps the event filter on the application): needs a Linux check and a
  manual Windows pass. Parenting would not stop `topLevelWidgets()` listing it (measured).

### Cross-cutting design

- **Severity is doing double duty as the UI's interruption policy.** `QtHandler` is attached
  to the root logger with no name filter (`main_app.py:246`), so any third-party library logging at
  ERROR pops a dialog at the user. Code is now written to game it: `main_model.py:248-254` chooses
  ERROR *because* it raises a dialog, `EventWorker`'s docstring explains that the progress bar must
  be emitted before the ERROR log or it strands behind the dialog, and
  `MainModel.update_logging_level` special-cases skipping the handler. The fix is to separate
  "how loud is this" from "should this interrupt".
- **`_validate_param_types` is strictly nominal** (`BaseDataPlugin.py:577-578`): at apply time
  `Type: float` rejects an integer `5` and `Type: int` accepts `True` (only a default `Value` has
  the bool refused, by the schema check at `settings_schema.py:146`). Parameter semantics living in the display name is settled in
  `DECISIONS.md` 2026-09-01.
- **`MainView`'s navigation state is a QLabel's rendered text.** `get_current_view:1293`
  returns `self.page_title_label.text()`, keyed into `self.pages` to decide whether to launch a
  walkthrough (`get_walkthrough_steps:1167`); the label starts as `"Home"` (`:821`), not a page,
  so the app logs a misleading "does not support walkthrough" before the first switch. The tab
  Views do this correctly with a hardcoded literal.
- **~75 attributes are assigned only outside `__init__`** across the tab Views (not re-measured
  since 2026-09-04), with 11 `hasattr`/`getattr(self, ..., default)` guards papering over it
  (2026-11-16; 14 on 2026-09-24). `ClusteringView.axes` is the clearest case, assigned only in
  `clear_plot` (`:180`/`:182`) and read unguarded in `update_plot` (`:756`/`:779`); latent, since every
  drawing path clears first (`ClusteringController._start_figure`, the merge redraw at `:299`).
  Fixing it properly means an `Optional[Axes]` declared in `_init` plus handling at both reads.
- **`MetaFilter.force_serial_channel_operations` is unenforceable.**
  `get_callable_filter:97` hands out `self.filter_data` as a bare bound method invoked
  inside another plugin's generator, and `@serialize_channels` is restricted to generator
  functions. Either delete the declaration for this family or route `filter_data` through
  the guard.

### CI, packaging and tooling (not logic changes - no plan needed)

- **No pip cache in `ci-internal-pr.yml` or `release.yml`**, and `ci-branches.yml:144` runs
  `pre-commit clean`, discarding the hook-env cache every run.
- **`black` runs only at the manual pre-commit stage**, so formatting is enforced by CI
  rewriting contributors' commits rather than by failing them.
- **`scripts/new_plugin.py`'s two base-class tables are guarded one-directionally.**
  `tests/unit/scripts/test_new_plugin.py` asserts each `FAMILIES` and each `TRIAD` entry
  appears in `main_model.py` (`test_new_plugin.py:758`, `:882`), not the reverse, so adding a
  thirteenth `Meta*` base to `ALLOWED_BASE_CLASSES` (`main_model.py:137`) leaves the
  generator and `--list` silently blind with no test failing. Both guards are also regexes
  over another file's source text, so reformatting `main_model.py`'s dict breaks them
  spuriously.

### Logging and error handling

- **Routine states still logged at `WARNING`**: 108 `logger.warning` + 4 `logger.exception` under
  `poriscope/` (2026-11-16; 111 + 13 on 2026-09-24). None interrupts anyone (`QtHandler` floors at
  `ERROR`), so this is a log-signal problem, deliberately not urgent. Families: per-event "skipping"
  /"proceeding without" notes from worker generators (`EventAnalysisController.py:213`,
  `ProteinModel.py:734`, `MetaEventTabController.py:131`, `RawDataModel.py:108`); user guidance that
  belongs on the panel, not the log ("select only one", `RawDataView.py:670`, `MetaSubsetTabView.py:1362`;
  "No column names received", `ClusteringController.py:446`, `MetadataController.py:1978`).
  `DataPluginController._report`/`_report_and_restore` (`:565`, `:515`), which emit to the panel
  *and* log, are the model. Deliberately staying at `ERROR`: the plugin-import failure
  (`main_model.py:254`) and the missing `id` column (`SQLiteDBLoader.py:660`).
- **The plugin loader executes modules before knowing they are plugins.** `load_plugin`
  calls `exec_module` (`main_model.py:286`) on every `.py` file before checking whether it
  holds a plugin (`:231-246`), so a helper module executes during discovery and reports as a
  plugin failure if it raises; and it never registers modules in `sys.modules`, so two plugins
  importing a shared helper by file each get their own copy. The last open piece of the
  compliance gate's trust boundary (`DECISIONS.md` 2026-09-02 settles the rest).
- **`@log` costs roughly 291 ns per call above an undecorated method, with logging off.**
  Measured 2026-09-02 over 300,000 calls: 330 ns/call against 39 ns undecorated, after the
  lazy-name fix. Almost all of it is the wrapper's own call machinery rather than anything a
  level check can skip, so the only lever is not decorating the hottest methods -
  `get_key()` and `WaveletFilter._apply_filter` are the candidates. Profile a real analysis
  run before removing either; 291 ns only matters at a call rate nothing has demonstrated.
- **`save_session` re-serializes the whole history on the GUI thread on every plugin
  change**, deep-copying and rewriting the entire session file whether or not the change
  touched most of it.
- **The 194 `except Exception` handlers (2026-11-16) are inconsistent about what they leave behind** -
  some leave the UI partially updated. (`validate_and_instantiate_plugin` now reports which
  stage failed, since its split into stages.)

### Other queued items

- **The metadata query's table aliases are only half parameterised.**
  `MetaDatabaseLoader.py:1184-1192` builds an alias map that feeds the projection and the
  WHERE qualification, but the JOIN hardcodes `e.id = s.event_db_id` (`:1275`) and `experiments exp` (`:1278`). Renaming the
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
- **`MetaView.lock` guards `progress_bars` in `remove_progress_bar:644` only**; the other three
  accesses (`:444`, `:449`, `:487`) are unguarded, so the lock does not establish the invariant
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

### Community-contributed-plugin compliance gate

Designed as a set: a pipeline that lets a community-contributed plugin be verified as safe
and correct to merge with a bounded amount of human review. Blocks 1 and 5 remain; block 4
(the trust boundary) is down to the plugin-loader item under "Logging and error handling", and
the rest are done (block 8's "no custom lint rules" call is in `DECISIONS.md`, 2026-09-01).
Block 1 is a pytest suite, so it is the test developer's.

#### 1. Behavioural conformance suite — remaining gaps

All nine data-plugin families are covered in `tests/unit/plugins/conformance/`, `PeakFinder`
included, and no fitter is exempt. Still open:

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
- **Decide how much of the writer/loader override path to document.** `quality_control.rst`
  names it in one sentence (worked examples were cut); none of the 5 plugins in the four
  writer/loader families declares anything beyond its builder's generic parameters, and `_fill`'s
  `ValueError` already names where a value goes. Restore the examples, keep the sentence, or drop it.
- **Decide whether readers converge on one exception type for malformed input.** A 0-byte file
  raises `ValueError` (most), `json.decoder.JSONDecodeError` (`ChimeraReader20240101`, a `ValueError`
  subclass) or `NotImplementedError` (the three ABF readers, from `pyabf`); a missing sidecar raises
  `FileNotFoundError` or `OSError`; none hangs (`test_reader_fuzz.py`, which deliberately enforces no
  type). Also confirm that `ChimeraReader20240501` and `ChimeraReaderVC100` raising rather than
  degrading on a missing sidecar is intended.

#### 5. Scoped CI gate for `poriscope/plugins/**`

**Goal.** A plugin-touching PR gets checks scoped to just the changed plugin, and reaches the
person who maintains it. Ownership routing is done and deliberately not a gate: `CODEOWNERS`
stays advisory (`DECISIONS.md` 2026-09-02), so nothing below waits on code-owner review.

**What remains.**

1. In `ci-fork-pr.yml` (which already exists for fork PRs and runs strict
   `pre-commit run --all-files` plus the full `pytest` with fork-safe `contents: read`), add a
   step after checkout computing
   `git diff --name-only origin/${{ github.base_ref }}...HEAD` and, for matches under
   `poriscope/plugins/**`, run block 1's conformance suite scoped to those files
   (`pytest -m conformance -k <derived from changed filenames>`). The schema-check half needs
   nothing: `test_plugin_settings_schema.py` already sweeps all 27 plugins on every push.
2. Mark that step and the existing strict `pre-commit` step as required status checks for
   `main`/`develop`. Automated checks only - this does not extend to code-owner review.
   Marking `docs-check.yml` as a required status check is the same admin-only step.

**Gotcha.** `ci-fork-pr.yml`'s permissions are deliberately `contents: read`; do not add
anything needing write access. That is `ci-internal-pr.yml`, which is not fork-safe.

## Owner-held - flagged for the owning developer, never fixed here

The logic in `PeakFinder.py` and `Basic_PeakFinder.py` belongs to another developer, who is
active. Docstring, signature and type-hint changes there are in scope (both are fully annotated,
with zero pydoclint violations); logic changes are not, even when annotating surfaces a real bug:
write the honest annotation, mark the defect with a narrow `# type: ignore` and a `NOTE:` at the
site, record it here, and leave the fix to the owner. Consult them before any `MetaEventFitter`
signature change, which moves both PeakFinders in lockstep. `NanoTrees.py` is not owner-held but a
deprecation candidate (its co-author has left; `CODEOWNERS` gives it to `@shadowk29` with the rest
of `eventfitters/`): fixing it is permitted but not worth the effort while deprecation is pending.

### Fitter plugin defects

- **`PeakFinder.py:1889` truncates a microsecond time to a sample index** (`int(start_us * samplerate * 1e-6)`),
  which floating point can put one sample early: 7 samples at 3 MHz multiply back to 6.9999 (2026-10-09).
  The tabs' identical conversions round since 2.1.
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
