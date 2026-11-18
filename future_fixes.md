# Future Fixes

The authoritative record of open work, under the release it is planned for and grouped by topic. A
landed entry is deleted (its history is in `changelog.md`); won't-fix reasoning goes to
`DECISIONS.md`. One to three lines per entry, with the `file:line` and the measured number. A line
number is a measurement from the day the entry was last worked: re-anchor it when the entry is.

Size tags: **S** under a day, **M** days, **L** a week or more. **Ruling** means Kyle rules before
it is built.

Sources: the 2026-09-24 review (<https://claude.ai/artifact/NsZSdFtsenMyANLEDLWvKq>; *(by
reading)* marks items derived from the code, not reproduced), the 2026-09-03 review
(<https://claude.ai/code/artifact/0886d408-06de-488d-8a8e-7f6a68206651>) and the 2026-08-25
audit (<https://claude.ai/code/artifact/a1bec2cd-a157-4299-acb3-a135738fee41>).

## The release series (planned 2026-11-18)

**Plan page:** <https://claude.ai/artifact/XJSQzf54ng5AhJhq1V5691>: what each release is for, and
the rulings below with their options.

A release with any breaking change is a major (`DECISIONS.md` 2026-11-12): narrowing, removing or
renaming anything a plugin or tab can override or call, changing a saved file other than by
addition (2026-11-18), or changing results. A minor only adds; a patch only fixes. So the queue is
sorted by what each fix does to compatibility, then by theme.

| Release | Theme | Holds |
|---|---|---|
| 3.0.0 | Trust the numbers | Cut after the burn-in; release prep only |
| 3.0.x | Patches | Defects found after the tag, on hotfix branches; nothing planned |
| 3.1 | Responsiveness and state | Compute off the GUI thread, tab state onto the Models, CUSUM speed |
| 3.2 | Replay and sessions | Carolina's track; may run beside 3.1 and take whichever number is free |
| 3.3 | Tabs and filters | Filter results on plot axes, clearer refusals, one filter layer for the subset tabs |
| 3.4 | Plugin contract and contributor gate | Additive contract changes, and the notice for everything 4.0 removes |
| 4.0 | The breaking batch | Every queued break, once; removes only what a 3.x release announced |

Each minor also takes the entries under "Any release" that sit in files it already opens.

**Rulings owed on the series:**

- **The order of 3.1 to 3.4**, and whether 3.2 runs as a parallel track.

**Ruled 2026-11-18 (Kyle):** seven changes go into 3.0 while it is the open major ("Before the cut",
below), and `NanoTrees` stays.

## 3.0.0 - trust the numbers

Accuracy tests against ground truth, reader and database correctness, type checking that sees the MVC layer, a Windows CI leg.

Everything planned has landed. `develop` burns in with lab users for a few weeks before 3.0 is cut
(Kyle, 2026-11-18): no release branch until he says. A defect found meanwhile is an ordinary fix on
`develop`, with its line under 3.0.0.

### Before the cut (ruled 2026-11-18)

**Plans, awaiting approval:** <https://claude.ai/artifact/LffgYJDjd8U95z3Rvv1oMs>. Nothing is built
until its plan is approved; each lands on its own branch, tests first.

- **A filter must be threadsafe, said where a filter author reads it.**
  `MetaFilter.force_serial_channel_operations` (`MetaFilter.py:136`) is a word-for-word copy of the
  concrete method on `BaseDataPlugin` and is never consulted: a filter runs as a bare callable inside
  other plugins' loops. Delete the copy (not a break: the method is still inherited), put the note
  on `MetaFilter`, `get_callable_filter` and `_apply_filter`, correct `meta_filter.rst` and
  `serial_channel_operations.rst`, and have `new_plugin.py` refuse that override for a filter. **S**
- **One Chimera VC400 reader for both layouts.** `ChimeraReader20240501._get_configs` learns the
  2024-01 layout (a JSON header embedded in the `.log`, ending `<END HEADER>`), told by the marker in
  the file; `ChimeraReader20240101` is removed (161 of `datareaders`' 348 removable lines); the
  survivor is renamed `ChimeraReaderVC400` (30 files name it) and both old class names are mapped to
  it where a session is read. The real 2024-01 set (`vc400/v2024_01`, first machine only) must be run
  through the merged reader before the cut. **M**
- **A recorded Plot Events holds its range as text.** `RawDataController.load_event_plot_data:530`
  and `EventAnalysisController.load_event_plot:71` take `events: List[int]`; a typed `0-99999` costs
  3.49 MB in the indented session file and 464 bytes as text. The replay's fit check binds names,
  not types (`MetaController.resolve_replayed_entry:743`), so the parameter is renamed for an old
  entry to be skipped cleanly. **M**
- **Database loaders raise on a failed query** (`MetaDatabaseLoader.load_metadata_raw:1408`,
  `load_metadata:1425`, `query_database_directly:1526`, abstract `_load_metadata:1590`). All six tab
  call sites already catch and report; three (`ClusteringController.py:256`,
  `MetadataController.py:519`, `MetaSubsetTabController.fetch_event_plot_data:659`) show "nothing
  matched" for a failure today. 15 in-loader call lines in 9 functions test for `None`, and 21 tests
  pin it. `DECISIONS.md` 2026-09-04 kept `None` only for the signal bus, which is gone. **M**
- **3.0's readers must tolerate what a later minor adds** (probed 2026-11-18 on a real saved
  session). A recorded action that gains a parameter has every saved call dropped: the recorder saves
  every parameter, and the check refuses a name it lacks (`MetaController.resolve_replayed_entry:743`).
  A plugin that gains a setting restores, but New Plugin of that class then fails
  (`DataPluginController.py:971-973`, `KeyError`) and Edit crashes if the dialog cannot draw the
  type. A setting left `None` refuses the plugin (`BaseDataPlugin._validate_param_ranges:601`). An
  unknown tab is skipped with a cryptic error and not counted (`main_controller.py:727-734`). Fix the
  reader in 3.0, or none of these can ship in a minor. Both databases, plot configurations and
  `config.json` tolerate additions as they are. **M**

### Release prep, after the burn-in

- **Cut 3.0.0 when the burn-in ends.** `git flow release start 3.0.0`; on the release branch, the
  records-and-docs sweep of what changed since 2026-11-18, then the preparation commit
  (`constants.py`, `CITATION.cff`, the changelog header; this section leaves this file), with a full
  suite in a clean copy, the wheel installed in a clean venv and the app launched. Push the release
  branch and see CI green. Kyle runs `release finish`.
- **The release manual pass includes the capture-rate check owed since 2026-10-09.** On the Metadata
  tab's capture-rate log filter, a clean timestamp column reports no dropped row, and a column with a
  duplicate timestamp reports one fewer than 2.0 did. Needs the real app.
- **The manual pass starts from the 44 hand checks written on 2026-10-08**
  (<https://claude.ai/artifact/3dpvo3x8QvejyVEnU1TLE8>), the only list of what the reader, finder,
  fitter, database and plugin-lifecycle changes should show, each with its expected result. Before
  reuse: "2.1" reads 3.0; c18's note is void (the Raw Data readout shares the finders' fit); c42 and
  c44 run `check_scripted_keys.py`, which no longer exists. It has nothing for the plugin API break,
  the analysis tabs and replay, Conditioning or the saved-file rule: write those against the running
  app. Delete the page after the pass.
- **Some 3.0 changelog lines sit under 2.0.0.** Three are confirmed: "Fixed the Event Analysis tab
  drawing one loader's fitter's fits over another loader's events", "Fit Events ... now refuses to
  run" and "Commit Events ... now refuses to run" (`changelog.md:690-694`) come from commits of
  2026-10-10 that are in no tag. Move the first two to 3.0.0; delete the third with its reversal
  ("no longer refuses", `:391`), since the guard never shipped. 39 bullets of today's 2.0.0 section
  are not verbatim in `v2.0.2:changelog.md`; most are the 2026-11-16 rewording of shipped lines, so
  check each one's commit against the tag in the records sweep.
- **Settled for the cut (Kyle, 2026-11-18):** the PeakFinder owner's testing does not block 3.0.

## 3.1 - responsiveness and state

Heavy work off the GUI thread, tab state onto the Models, CUSUM speed, the large Views split. Nothing
here may break a plugin, a tab or a saved file.

### Off the GUI thread

Do these in order: the first two remove what the third would otherwise carry onto a worker.

- **`itertools.tee` buffers the whole subset, raw arrays included** (`MetadataModel.py:789`,
  `ProteinModel.py:674`): a 16 MB peak for 200 events of 80 KB. Fetch twice through
  `_fetch_event_subset` instead; a single streaming pass cannot pick bins. **S**
- **Three data round trips through the View remain** (14 before action replay): Clustering's run
  (`ClusteringView.on_metadata_loaded:568` receives the rows and emits them back at `:649` to
  `ClusteringController.cluster:80`), Raw Data's baseline band (`RawDataView.py:1214` to
  `RawDataController.compute_baseline_stats:887`) and Raw Data's PSD
  (`RawDataView.set_trace_for_psd:1276` emits at `:1305` to `RawDataController.calculate_psd:931`, then
  reads the answer off its own attributes). None affects replay. Have the Controller go from load to
  compute and hand the View only the result; it removes three signals on shipped tabs. Why the
  Clustering one was kept: `DECISIONS.md` 2026-10-27. **M**
- **Every analysis-tab read and plot path but Conditioning's runs on the GUI thread.** Workers serve
  finding, fitting, writes, exports and Conditioning's 1 Hz noise. Worst is Protein, with no progress
  or cancel: `ProteinController.update_individual_distribution:728` runs
  `ProteinModel.fit_histograms:407` (`curve_fit` `:227`/`:299`) and `sample_event_geometries:1243`,
  whose rejection sampler (`_generate_vm_ensemble:840`) is bounded at 200 x 50,000 (`:897-902`), over
  an unbounded event count. Also HDBSCAN/GMM (`ClusteringModel.py:244,271`, from
  `ClusteringController.py:117-120`), `load_metadata_subset`, all-points histograms and KDE. No
  `processEvents()` in `poriscope/`. A recorded action reports success as it returns, so each one
  moved needs the `MetaController.background_step_failure` route, and moving Clustering meets the
  revisit clause of `DECISIONS.md` 2026-10-27. **L, ruling** (progress and cancel, which paths first)
- **A worker blocked on a lock cannot observe an abort.** `Worker.stop()` (`EventWorker.py:142-144`)
  only sets `stop_requested`, read on the generator's next turn (`:99`), and `serialize_channels`
  takes the plugin's lock with a blocking `with` before the first yield
  (`SerializeDecorator.py:69-70`), so a channel queued behind a serial-mode lock waits until it
  acquires. Fix it in the decorator; a new argument on `serialize_channel_operations` would be a
  break. **S-M**
- **`save_session` rewrites the whole session on the GUI thread on every plugin change and every
  tab-history change** (`main_controller.py:471`, `:701`): `MainModel._session_file:546` deep-copies
  the history (`:559`) and the file is rewritten whole. No cost has been measured: measure first, then
  coalesce the writes. **S-M**
- **The SQLite writers commit once per event (2026-11-02).** `SQLiteDBWriter._write_event` and
  `SQLiteEventWriter._write_data` take a savepoint per event with no transaction open (`:313`/`:384`,
  `:603`/`:646`), so each `RELEASE` commits: 48 commits for a 40-event build, 10 with one transaction
  per batch (probe). One transaction per batch is not the fix: with it open, a Clustering or Protein
  `SQLiteDBLoader.alter_database` commit into the same file raised "database is locked" after 5.5 s.
  Measure the commits' share of a 10,000-event write first; if it matters, commit about once a second.
  The e2e `synthetic_metadata_database` fixtures still build through the writer in every test. **M**
- **`@log` costs roughly 291 ns per call above an undecorated method, with logging off** (330 ns
  against 39 ns over 300,000 calls, 2026-09-02). The only lever is not decorating the hottest methods:
  `get_key()` and `WaveletFilter._apply_filter`. Profile a real analysis run before removing either.
  **S**

### Fitter performance

- **CUSUM costs 6.3 µs per sample, flat from 2k to 200k** (1.3 s for a 200k-sample event), holding
  the GIL, so per-channel threads give no multi-channel speedup: a per-sample Python loop in
  `CUSUM._locate_sublevel_transitions:168`, and a second in `IntraCUSUM.py:148`. JIT or C-port behind
  a golden ratchet: bit-identical, or it changes results and waits for 4.0. Measured before
  `38b5d514`; re-measure first. **M, ruling** (a new build or runtime dependency)

### State on the Models

- **The View still owns the scope, and the Controller reaches into it**: public View dicts read and
  written at `MetaSubsetTabController.py:1654,1657,1691` (invisible to boundary rule 3, which keys on
  underscores), and `relay_query` opens a `QMessageBox` from the Controller (`:1896`). Move the scope
  and the event-id cache (`MetaSubsetTabView.event_id_rows:244`) onto `MetaSubsetTabModel`. The View
  keeps its public scope attributes (`MetaSubsetTabView.py:194-196`) as properties: removing them is
  4.0's. The filters stay on the View (`DECISIONS.md` 2026-09-13). **M**
- **Emit-then-read-an-attribute survives at one site**: `MetaSubsetTabView.py:812-816` clears
  `event_id_rows`, emits `event_id_cache_requested`, then reads what the Controller's slot set. It
  works only because View and Controller share a thread on a default connection; a queued one would
  read `None`, silently "no data". Keep the signal and slot on the base (removing them is a break). **S**
- **The subset tabs pass a channel as the selection tree's digit string where the loader takes an
  `int`.** Six sites: `MetadataController.py:512`, `:734`, `:852`; `ProteinController.py:299`, `:627`,
  `:779`, each handing `{exp: [channel]}` to methods declaring
  `Optional[Dict[str, Optional[List[int]]]]`. No wrong output: `"0"` and `0` gave the same queries,
  rows and counts (2026-11-11). Convert at the six call sites, not in the tree: the recorded scope in
  a saved history holds strings. Refuse `overlay_plot`'s "nothing selected" sentinel `{None: [None]}`
  (`MetadataController.py:359`, `ProteinController.py:179`) before any fetch, which goes a step past
  `DECISIONS.md` 2026-10-09's revisit clause; three Protein tests pin the string form
  (`test_protein_controller.py:373`, `:482`, `:894`). No type check can see this class of mismatch:
  `call()` dispatches by name, untyped. **S**
- **An overlay's kept values hold two shapes.** `OverlayState.values`
  (`MetaSubsetTabModel.py:106`, `List[Any]`) takes a raw column array from three paths
  (`MetadataController.py:1113`, `:1196`, `:1241`) and a `(bincenters, counts)` tuple from all-points
  (`:1644`); `ProteinView.hist_data` (`:614`) holds only the tuple. **S-M**
- **Plot types are bare strings repeated across Controller and Controls** ("Heatmap" 5 times in
  `MetadataController`, 3 in `metadatacontrols`) and saved in recorded action parameters. A `StrEnum`
  whose values are today's strings pins them; renaming a value is a saved-file break. **S**
- **37 attributes of the tab Views are first assigned outside `__init__` and `_init`** (Protein 22,
  Raw Data 6, Clustering 5), with 5 `hasattr`/`getattr` guards in the Views, 1 on the subset base and
  5 in `MainView`. `ClusteringView.axes` is the clearest: assigned only in `clear_plot`
  (`:183`/`:185`) and read unguarded in `update_plot` (`:759`/`:782`); latent, since every drawing
  path clears first. Declare an `Optional[Axes]` in `_init` and handle it at both reads. **S** for
  `axes`, **M** for the rest

### The large units

- **13 functions exceed 300 lines** (2026-11-18), led by `_classify_peak_prominences` (531),
  `metadatacontrols.setupUi` (525), `_classify_translocation_direction` (494),
  `_classification_section` (488), `_classify_folded_unfolded` (447) and `proteincontrols.setupUi`
  (438); 10 of the 13 are in the two PeakFinders, which are their owner's. `ProteinView.py` is 1,390
  lines across 34 functions; `MetadataView.py` 1,616 across 40. The mechanical win is the two
  `setupUi` methods: straight-line widget construction, extractable into per-panel builders with the
  object names kept. **S-M** each

## 3.2 - replay and sessions

Carolina's track. Additive only: a recorded action's parameters and the session file change by
addition, or the change waits for 4.0.

- **Keep a channel's earlier results when a Find/Fit rerun doesn't produce results (2026-11-04).** A rerun clears the
  channel as it starts, so a cancelled, failed or 0-result rerun loses earlier results. A working approach is in
  history: `f4cbcc67` added it and `312fe6c2` removed it (`git revert 312fe6c2` or `git cherry-pick f4cbcc67`).
  **L, ruling**
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
    gap closed in the tab instead. Landing it reverses that entry's second decision in the same change. To plan:
    - Where it lives: potentially one copy of the set-aside and put-back on `BaseDataPlugin` (Kyle, 2026-11-04).
      Based on a preliminary review of `f4cbcc67`, it would be shared by every family: each family only declares its
      result fields, and PeakFinder, or any plugin with per-channel results of its own, extends its family's list
      instead of overriding methods.
    - Always on, or an opt-in `keep_previous` on `find_events` / `fit_events`, depending on whether scripts rerun a
      channel on the same plugin instance. Opt-in is additive; always-on changes what a third-party finder or
      fitter with results of its own sees after a failed rerun, so it is 4.0's.
    - A readable outcome (`last_run_outcome`), so a replay can tell a cancel from a failure. "Skip this step" below
      wants the same thing: build it once.
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
  tab's Find (another tab). Changes the replay rule (`DECISIONS.md` 2026-11-05, 2026-10-17 and 2026-11-17).
  **M, ruling**
- **A refusal of the user's own click waits for the replay to end (2026-11-17).** While a tab replays, every
  status-panel line it sends is held until "replay done" (`MetaController.panel_text_to_show:489-516`), so "<finder>
  is already running on channel <n>; this request was ignored" (`MetaModel.set_generator:248-251`), answering a Find
  clicked during the replay, showed ~1 min late (manual pass, `a64182ab`, 2026-11-17). Show it at once, as the second-replay
  refusal does (`_panel_text_now`, `MetaController.py:350-357`); the Model cannot tell a click from a replay launch,
  and the fix may need a signal change. **S-M, ruling**
- **Go back replays the live history, not the kept one (2026-11-17).** `ReplaySequence._go_back`
  (`replay_sequence.py:820`) replays `_history_before`, the live history, so a Find run twice on a channel is run
  twice after a Go back, where once gives the same tab. Replaying `build_kept_history` of it instead would avoid
  that, but would shorten Metadata's Undo after a Go back. **S, ruling**
- **A reloaded session restores plugins but not what the control panels showed.** Snapshot and
  restore each panel's widget state on `MetaControls`, with `MultiSelectComboBox` and
  `MultiSelectFilterComboBox` supplying their own get/set; modal dialogs stay out of scope. The
  controls are not keyed by `objectName` today (one read, `clustering_settings_widget.py:513`), so
  naming them is part of it. A direct snapshot under a new key in each tab's session entry, not an
  event-sourced log like `@register_action`. Restore with signals blocked, after the tab's plugins
  exist and before the restore dialog offers a replay. A replay writes each step's recorded values back
  into the panel (`MetaView.write_back`); this is for a tab the user does not replay
  (`DECISIONS.md` 2026-09-27 anticipates it). **M-L, ruling** (which controls)
- **One Plot Events request may ask for any number of events.** Recording the range as text (3.0)
  fixes the session file, not the request: a typed `0-99999` still builds the full list, makes one
  plugin call and one subplot per event, and its out-of-range message lists every index. Both panels
  also expand the text on every keystroke. Three expanders with different rules do it
  (`IntegerRangeLineEdit.get_values`, `MetaEventTabView._expand_event_indices:196`,
  `_parse_event_indices:89`): a cap or a confirmation, and one expander. **S-M, ruling**
- **A replay can wait forever for a run that reports under another key.** A saved `find_events`
  whose channel is the string `"3"` starts a run that ends as `(3, "finder")` while the replay waits
  for `("finder", "3")` (`replay_sequence.py:376-391`); a probe gave up after 150 s (2026-11-18). No
  release should write a changed type, but a damaged or hand-edited session should fail, not hang. **S**
- **Undo finds a reset by its name, not its figure (2026-11-04).** `MetaController.py:1022`, `:1038`
  stop at the last `RESET_ACTION` whatever figure it clears; harmless while Metadata, with one figure,
  is the only tab with Undo. Match the declared figure before a tab with two figures gains Undo. **S-M**

## 3.3 - tabs and filters

What the analysis tabs let a user do with a filter and a plot, and what they say when they refuse.
Easier after 3.1 has moved the scope onto the Models.

### Filters and axes

- **A raw filter's result columns cannot be chosen on a plot axis.** The axis menus list only the
  database's own columns (`metadatacontrols.update_axes:678`, filled from
  `MetadataController.request_column_names:1950`), so a computed or aliased column such as
  `max_blockage - min_blockage AS range` is returned by the query but never selectable, and
  every axis is picked by hand even when the result holds only the columns the user selected. Worth
  addressing because shaping the result is the point of a raw filter, and that shaping cannot reach
  a plot. SQL viewers that can plot choose the axes from the query's own columns and preselect them
  automatically. Found in a manual pass; the tests set the axis column directly and cannot see it.
  **M, ruling** (preselect the axes, or only list them)
- **An Assisted filter cannot define a derived column.** It is a condition, so
  `max_blockage - min_blockage > 500` selects events, but nothing can put a computed value such as
  `range = max_blockage - min_blockage` on an axis: the one way of shaping a result for which the
  user must leave Assisted for raw SQL. Building it meets the unit-label ruling's revisit clause
  (`DECISIONS.md` 2026-10-10). **L, ruling**; after the entry above
- **Clustering has no named-filter layer**: one anonymous `QTextEdit`
  (`clustering_settings_widget.py:132`), validated only at apply, where Metadata and Protein name,
  save, reload and multi-select filters through 17 methods on `MetaSubsetTabView` (1,391 lines,
  34 methods). Validation is already shared (`construct_metadata_query`). Putting
  `ClusteringView` under `MetaSubsetTabView` would inherit its scope and event-cache state, so the
  shape is a thin base holding only the filter dict, the add/edit dialogs and save/load, under
  both. It is also the home the three entries below are waiting for. **L, ruling**
- **The column-names and plugin-state reactions are written twice.** `ClusteringView` and
  `MetadataView`'s `update_available_columns` (`:391`, `:1369`; identical code) and
  `notify_plugin_state_changed` (`:836`, `:730`; identical but for the panel attribute; Protein's is
  a no-op) are near-identical, but `measure_duplication.py` only catches byte-identical bodies, so
  the `*View.py` family shows 0 removable. No shared base fits today; the thin filter base above
  would. No mixin (`DECISIONS.md` 2026-09-06). **S** once the base exists
- **`update_available_plugins` is hand-written in all six Views** (`ClusteringView.py:818`,
  `MetadataView.py:706`, `ProteinView.py:789`, `RawDataView.py:458`, `EventAnalysisView.py:121`,
  `ConditioningView.py:146`): `super()`, then each metaclass list pushed into the panel. Metadata's
  and Protein's are identical but for the panel attribute, so `MetaSubsetTabView` can own them
  through `_subset_controls`. **S**
- **Overwriting committed columns is built twice**: the confirm
  (`ClusteringView.on_cluster_column_checked:329`, `ProteinView.confirm_fit_commit:334`) and the drop
  (`ClusteringModel.drop_cluster_columns:295`, `ProteinModel.drop_fit_columns:441`); Protein's
  `drop_fit_columns(loader, table, columns)` is the general form and drops only the columns present.
  Protein's prompt reads "fit data data already exists" (`ProteinView.py:354`). **S**

### Plots and navigation

- **Auto-binned histogram overlays re-bin the earlier datasets.** With bins left empty,
  `MetadataModel.overlaid_histograms:450` estimates bins from all overlaid datasets, so each added
  dataset changes the first one's edges (measured: 4 bins 56 wide alone, 7 at 32 with one overlay,
  11 at 20 with two); a fixed count keeps its count but its edges still move when an overlay widens
  the range. Shared edges were introduced on purpose in 1.x. Decide whether to freeze them at the
  first dataset. **S, ruling**
- **Event-tab arrows stop at 0 but run past the last event; wrap them (wanted for Raw Data's
  Plot Events), or decline, at both ends.** `MetaEventTabView._shift_range_and_update_plot:254`
  declines below 0 (`:304-311`); past the end it moves the field and the Controller reports the
  overflow (`RawDataController.py:617-633`, `EventAnalysisController.py:155-167`). Pros: matches the
  subset tabs' wrap, symmetric ends. Cons: positions 0..N-1 are not a browsed set, and a multi-range
  field (`3, 7-9, 15-19`) has no clean wrap. The View has no event count: push the count to it
  (additive); moving the shift to the Controller re-signs a method on a tab base, a break. **S-M,
  ruling**
- **Figure reset differs per tab**: `ClusteringView.clear_plot:165` guards `figure.clear()`
  with `except AttributeError` where Metadata has `_clear_figure_state:187`/`_axes_valid:227`, and
  `ProteinView.clear_plot:534` runs clear/add_subplot/tight_layout/draw once per figure of the mode.
  **S-M**

### What a refusal says

- **A disabled OK or action button never says what to fix** (2026-10-10, by reading).
  `DictDialog.check_validity:347` and `TimeWidget._check_validity:171` disable OK with no label,
  tooltip or highlight (`NumericLineEdit.isValid` knows the range but never shows it); the six tab
  controls' `validate_inputs` (Event Analysis `:294`, Raw Data `:320`, Metadata `:868`, Protein
  `:635`, Clustering `:259`, Conditioning `:159`) at most `logger.debug` the reason.
  `ClusteringSettingsDialog.plot_warning_label` (`clustering_settings_widget.py:190-615`) is the one
  that says why. Recommended: a one-line hint naming the first problem and its constraint, one helper
  shared by dialogs and tab controls, plus a tooltip on the disabled button. The other two validation
  stacks differ again: `BaseLineEdit` traps focus (`BaseLineEdit.py:82-83`) and the bare Qt
  validators check no range. **M, ruling** (the wording)
- **A repeated column is refused two ways**: Clustering raises `KeyError`
  (`ClusteringView.py:562`), logged at ERROR by its caller after the config is already saved
  under its title; Metadata says so on the status panel (`MetadataController.py:485-490`) and its
  panel already disables Update Plot (`metadatacontrols.py:882-952`). The clustering dialog's
  `_check_apply_enabled` (`clustering_settings_widget.py:569`) could refuse it the same way. **S**
- **Event Analysis channel ticks do not follow the loader.**
  `MetaEventTabControls.update_channels:100` ticks every channel only when the list is empty
  (`:118`); a later load keeps only numbers already ticked (`:134`). Measured: first load `[0,1,2]`
  -> all ticked; a loader holding `[5,6]` -> none ticked and Fit Events disabled, unexplained - and
  another recording's channel numbers are not the same channels. Raw Data inherits the method, so
  one fix covers both. Conditioning already keeps what carries over and otherwise ticks all
  (`conditioningcontrols.py:207`). **S, ruling** (that rule, or tick all on every loader change)
- **Severity is doing double duty as the UI's interruption policy.** `QtHandler` is attached to the
  root logger with no name filter (`main_app.py:244-246`), so any library logging at ERROR pops a
  dialog. Code is written to game it: `main_model.py:248-254` chooses ERROR *because* it raises a
  dialog, `MainModel.update_logging_level:878` special-cases skipping the handler, and the handler now
  also holds the replay's rule (`QtHandler.py:94-98`). Separate "how loud is this" from "should this
  interrupt"; ERROR must keep interrupting by default, or third-party plugins' errors go quiet. **M,
  ruling**
- **Routine states still logged at `WARNING`**: 108 `logger.warning(` + 4 `logger.exception(` calls
  under `poriscope/`. None interrupts anyone, so this is a log-signal problem. Families: per-event
  "skipping"/"proceeding without" notes from worker generators (`EventAnalysisController.py:213`,
  `ProteinModel.py:745`, `MetaEventTabController.py:131`, `RawDataModel.py:108`); user guidance that
  belongs on the panel ("select only one", `RawDataView.py:670`, `MetaSubsetTabView.py:1378`; "No
  column names received", `ClusteringController.py:446`, `MetadataController.py:1978`).
  `DataPluginController._report`/`_report_and_restore` (`:565`, `:515`), which emit to the panel
  *and* log, are the model. Deliberately staying at `ERROR`: the plugin-import failure
  (`main_model.py:254`) and the missing `id` column (`SQLiteDBLoader.py:660`). **M**
- **A short status-panel message can be lost under a long SQL echo** (reported 2026-09-14). Each line
  now carries a time and a source, but the panel has no severity marking and no filtering, and the
  entry above would send it more. Plan the two together. **M, ruling**
- **Event Analysis's fitter list offers fitters built on another loader.** Fitting and plotting
  refuse the crossing after the fact (`EventAnalysisController.py:510-520`, `:183-196`); writing is
  deliberately not gated (`DECISIONS.md` 2026-10-20), so only the fitter list is a candidate. Filter
  it to the selected loader from both loader-change paths (`EventAnalysisView._handle_other_actions:749`
  and `_write_back_loader:715`, which a replay and a restore use), reusing
  `EventAnalysisController._parent_key:452`, and again in `update_available_plugins:121`. Risks: every
  combobox's `currentIndexChanged` is wired to `on_parameter_changed`
  (`eventAnalysisControls.py:88,183,225,273`), so repopulating loops without signal blocking; a
  restored session selecting a hidden fitter silently falls back to the first one. **M, ruling**
  (hide or grey out). **Not scheduled: first see how the refusals are received.**
- **The walkthrough overlay does not block clicks outside the highlighted widget.**
  `Overlay` (`walkthrough.py:205`) sets `WA_TransparentForMouseEvents` (`:217`), so only the
  page-switch refusal and the icon guards in `MainView` stop an out-of-sequence click. Mask
  everything except the target. The Plugins dropdown is a separate `QMenu` popup the overlay
  cannot reach, so it needs its own handling. **M**

## 3.4 - plugin contract and contributor gate

Additive changes to what a plugin or a contributed tab may rely on, the gate that checks a
contribution, and the notice for what 4.0 removes.

### Plugin contract

- **`_validate_param_ranges:582` rejects any `None`** (`:602`), so a plugin cannot declare an
  optional parameter. A minor may add one only as a new setting, and only if 3.0 ships a reader that
  lets `None` through for it (3.0, before the cut); a setting 3.0's plugin code reads cannot become
  optional before 4.0. **S-M**
- **`_validate_param_types` accepts only the exact type** (`BaseDataPlugin.py:577-578`): at apply
  time `Type: float` rejects an integer `5`. Accepting it is additive. **S**
- **Provenance stops at the fitter (2026-10-08).** A database's `channels.provenance` records the
  writer, the fitter and the event loader, which is all the database writer can reach
  (`SQLiteDBWriter._provenance_json:1112`). The reader, finder and filter that produced the events are
  not stored in the events file (`SQLiteEventWriter.py:83-121`), and a filter is a callable, never a
  setting. Carrying them needs the events writer to record them (a nullable column) and the event
  loader to expose them (a concrete method, not an abstract one). **M**
- **The transitive serial declaration is not fully honoured.** `MetaEventFinder` defers to
  `self.reader.force_serial_channel_operations()` and `MetaEventFitter` to its `eventloader`,
  so a finder declares serial *because its reader is not threadsafe* - but the guard locks the
  finder, which does not protect a reader shared by two finders. Latent: every reader and loader
  returns `False`. Taking the parent's lock too risks deadlock through lock order, which is why it
  was not done; that reason is written nowhere else. **M, ruling**
- **The plugin loader executes modules before knowing they are plugins.** `_import_plugin_module`
  calls `exec_module` (`main_model.py:286`) on every `.py` file before the class check
  (`:230-245`), so a helper module executes during discovery and reports as a plugin failure if it
  raises; and it never registers modules in `sys.modules`, which is what lets an edited file reload on
  a rescan, so two plugins importing a shared helper by file each get their own copy. An `ast` check
  for a class of the file's name before executing refuses nothing that loads today. The last open
  piece of the compliance gate's trust boundary (`DECISIONS.md` 2026-09-02). **S-M, ruling**
- **`sys.path` only grows**: `update_user_plugin_location` (`main_controller.py:213-216`) and
  startup (`main_app.py:122-125`) append the plugin folder and its parent and never remove a
  previous one, so after the folder changes an abandoned folder's module still wins a name clash
  until relaunch. Removing the path is not enough: the old folder's modules stay in `sys.modules`. **S**
- **Two user tabs' modules may collide by bare name, and the page guard guesses a non-dedicated
  tab's view as `<Name>View`.** Discovery already refuses a view or model file whose name is taken
  (`main_model.py:321-327`). What remains: a user Controller imports its siblings by bare stem, so a
  module of the same name from another folder may win in `sys.modules` (not reproduced), and
  `MainView.on_load_analysis_tab_button_click` (`main_view.py:776`) guesses the view name from the
  controller's. Reproduce first; then read each controller's `view:`/`model:` annotations
  (`typing.get_type_hints`) for the guard's exact page name, falling back to the guess. **M**
- **Nothing says which exception a reader raises for malformed input.** A 0-byte file raises
  `ValueError` (most), `json.decoder.JSONDecodeError` (`ChimeraReader20240101`) or
  `NotImplementedError` (the three ABF readers, from `pyabf`); a missing sidecar raises
  `FileNotFoundError`; none hangs (`test_reader_fuzz.py`, which enforces no type). One new type that
  inherits from what each reader raises today is additive; replacing them is 4.0's. Also confirm that
  `ChimeraReader20240501` and `ChimeraReaderVC100` raising on a missing sidecar is intended. **M,
  ruling**
- **Announce what 4.0 removes.** Each removal in the 4.0 section needs a notice in a 3.x release:
  written for `ChimeraReader20240101` (2.0.0); owed for anything else ruled into 4.0. **S** each

### Contributor gate

Designed as a set: a pipeline that lets a community-contributed plugin be verified as safe and
correct to merge with a bounded amount of human review. The conformance suite covers all nine
data-plugin families (`tests/unit/plugins/conformance/`), `PeakFinder` included; the trust boundary
is down to the plugin-loader entry above. Block 1 is a pytest suite, so it is the test developer's.

- **Should anything enforce that a new fitter fixture shape comes with a check that reads it?**
  Nothing does (`conformance_recipes.rst:100-127`). There are three shapes; `"deep_dip"`, added for
  PeakFinder, has no check of its own and is read only because PeakFinder rejects every event on a
  flat blockage. A guard asserting "the routed fixture changes what the fitter reports" was tried and
  removed the same day: it proves a difference exists, not that anything asserts it. What would work
  is fixture mutation testing (perturb the planted shape, require an assertion to fail), which means
  re-running tests from inside a test. Weigh that against how often a shape is added, and agree not
  to re-add the weaker guard. **Ruling**
- **Decide how much of the writer/loader override path to document.** It is one paragraph in
  `conformance_recipes.rst:146-156`, with no worked example; none of the 5 plugins in the four
  writer/loader families declares anything beyond its builder's generic parameters. Keep the
  paragraph and close this, or restore the examples. **S, ruling**
- **A scoped CI gate for `poriscope/plugins/**`.** In `ci-fork-pr.yml` (strict `pre-commit` plus the
  full suite, `contents: read`), add a step computing
  `git diff --name-only origin/${{ github.base_ref }}...HEAD` and running the conformance suite for
  the plugins it names. The checkout needs `fetch-depth: 0` or the diff fails on a shallow clone. The
  full suite already runs every conformance test there, so the step adds a readable signal, not
  coverage. Then mark it, the strict `pre-commit` step and `docs-check.yml` as required status checks
  for `main`/`develop` (admin only; `CODEOWNERS` stays advisory, `DECISIONS.md` 2026-09-02). Add
  nothing needing write access: that is `ci-internal-pr.yml`, which is not fork-safe. **S**
- **A contributor cannot run the replay guard on their own tab (2026-11-17).**
  `test_replay_guard_no_gui.py` checks only the six shipped tabs (`TABS`). A way to point it at a
  contributor's tab would check that a replay reproduces the action, that no recorded action reads a
  widget, and that each view names its run in `depends_on`. Finding every tab automatically was
  rejected (`DECISIONS.md` 2026-10-26, noted 2026-11-12); an opt-in pointer was not. **M-L, ruling**
- **`new_plugin.py` cannot generate a `MetaSubsetTab*` tab**, the likely shape of any new
  database-analysis tab; add `--base subset`. **S-M**
- **`scripts/new_plugin.py`'s two base-class tables are guarded in one direction.**
  `test_new_plugin.py:758`, `:882` assert each `FAMILIES` and `TRIAD` entry appears in
  `main_model.py` by regex over its source, not the reverse, so a thirteenth base in
  `ALLOWED_BASE_CLASSES` (`main_model.py:137`) goes unnoticed until a shipped plugin uses it. Import
  the dict and compare both ways. **S**
- **Controller-side `call()` is a convention, not a checked invariant (2026-09-17).**
  `check_mvc_boundary.py`'s rule 5 (`plugin_reaches:532`) bans every route to a data plugin *except*
  `call()`, and nothing distinguishes a Model making a plugin call from a Controller making one: 63
  `self.model.call(...)` sites across the Controllers (49 on 2026-09-24), 0 direct `self.call(...)`,
  18 in the Models. An allowlist of named wiring operations would check it. **S, ruling** (whether
  it is worth doing)

## 4.0 - the breaking batch

Every break queued, landed together. A saved file's format number may change only here.

- **The rest of the loader family returns `None` for a failure.** After 3.0 makes the four query
  methods raise, eleven other `MetaDatabaseLoader` getters (`get_experiment_names`,
  `get_channels_by_experiment`, `get_table_by_column` among them) still return `None` for both
  "failed" and "nothing there", and `get_channel_db_id` swallows every exception. **M**
- **Nothing bounds a plugin's `close_resources()`**: Reset Session and quit call it unguarded
  (`DataPluginModel.py:217`, `:243`), so one that hangs freezes the app without naming itself. A
  threaded timeout was built and reverted (`DECISIONS.md` 2026-08-31): doing it means
  `check_same_thread=False` on the two writers' `self.conn` (`SQLiteDBWriter.py:304`,
  `SQLiteEventWriter.py:594`), the quit path routed through the same guard, and "callable from
  another thread" added to the contract (`BaseDataPlugin.py:268`), which breaks a plugin holding
  thread-bound resources. **M, ruling**
- **Remove what the 3.x releases kept for compatibility**, as each lands: the public scope dicts on
  `MetaSubsetTabView`, `event_id_cache_requested` and its slot, the old reader exception types.
- **Make an existing plugin setting optional.** A minor may add a setting that is optional; one that
  3.0's plugin code reads cannot become `None` without breaking 3.0's reader.
- **Results that change are a break too.** The owner-held fixes that move a stored number (the
  PeakFinders' truncated sample index, `Basic_PeakFinder`'s `NaN` current), either Protein
  two-population ruling that changes which fits are accepted, and a CUSUM port that is not
  bit-identical all wait for here.
- **Rename `sublevel_starts` on `MetaEventFitter`**, if the owner agrees: it holds dicts
  (PeakFinders), tuples (`NoFitter`) and a `HackyList` (`NanoTrees`), never bare start indices. The
  compliance test compares signatures by equality, so every third-party fitter fails until renamed.
  The docstrings can say so in any release. **S, ruling**

## Any release - cleanups, tests and tooling

Behaviour-preserving unless an entry says otherwise. Take an entry with the release that opens its
file; each wants the covering tests read first. An overridable method on a `Meta*` or tab base keeps
its name and signature.

### Shell and shared widgets (2026-09-27)

- `MainView` menu table: 10 `addMenu` + `add_plugin_actions` blocks at `main_view.py:450-503`
  and the one-line `on_load_*` wrappers (`:610-776`).
- `MainView.get_milestone_step:1471` wraps one getter, `get_analysis_highlight()`, in four lambdas
  and unwraps it with `[0]` (`:1478-1501`). `populate_plugins_menu:699` mixes building the menu with
  20 lines of anchor-position arithmetic (`:728-748`).
- **`MainView`'s navigation state is a QLabel's rendered text.** `get_current_view:1293` returns
  `self.page_title_label.text()`, and `get_walkthrough_steps:1167`, the sidebar sync (`:1031`) and
  Replay Actions (`:1310`) key off it. Store the page name in an attribute set in `switch_to_page`.
- `MainController.instantiate_analysis_tab` wires seven tab signals as seven `connect` calls
  (`main_controller.py:755-777`); `MainView.connect_signals:255` already has the table form.
- **Deleting from the edit dialog** (`DataPluginController._complete_requested_deletion:226`)
  re-implements `delete_plugin:643` and posts no "deleted" message to the panel.
- `SettingsWindow` rows hand-built as a layout + widget + `add_horizontal_line()` in
  `add_general_tab_contents:504`, `add_advanced_settings_tab_contents:571`,
  `add_about_tab_contents:669`; two opposite 6-entry log-level dicts at `:772` and `:786`.
- **The two multi-select boxes.** `MultiSelectComboBox` and `MultiSelectFilterComboBox` share a base
  (`multiselect_base.py`) but still each carry `updateSelectAllButton`, `selectAllToggle`,
  `getSelectedItems`, `_set_outside_click_filter` and `eventFilter` (`multiselect.py:129-250`,
  `multiselect_filter.py:124-300`), differing only in reading a check state off the item or off an
  embedded `QCheckBox`: move them onto the base with that accessor as its hook. Select-all's
  three-way branch has two identical arms in both and in `SelectionTree.py:169-186`. An empty
  `MultiSelectComboBox` shows "Deselect All" checked, since `checked == total == 0`. Select-all in
  the filter box emits `selectionChanged` N+1 times; both popup lists hide their scrollbar
  (`multiselect.py:58`, `multiselect_filter.py:63`); `SelectionTree.show_dialog` has no Cancel.
- **The two multi-select popups are built differently, and parentless.** `MultiSelectComboBox`
  builds a frameless `QWidget(None)` on Linux and a `QDialog(None)` elsewhere (`multiselect.py:62-72`);
  `MultiSelectFilterComboBox` a `QDialog(None)` on every platform (`multiselect_filter.py:67`), so the
  filter picker never got the Linux treatment, and neither container is destroyed with its
  combobox. Reconciling them changes behaviour on a path CI cannot exercise (`DECISIONS.md`
  2026-09-01): needs a Linux check and a manual Windows pass. **M, ruling**
- `dict_dialog_widget.on_ok:368` dispatches by nested `try/except AttributeError` probing;
  `init_ui:111` (136 lines) builds its Input File and Output File rows identically but for the
  picker called (`:131-167`).
- `clustering_settings_widget` builds its column rows three times (`:314`, `:397`, `:525`), and
  `init_ui` restores a preselected config inside one broad `except Exception` (`:211-236`).
- `icon_menu_widget`/`text_menu_widget`: `emitSignal` identical but for the `"menu"` key
  (`icon_menu_widget.py:296`, `text_menu_widget.py:277`), six `set*Checked` slots each, and
  `QPushButton:hover` QSS six times. Share the constants and those methods, not the classes.
- `FloatRangeLineEdit.set_range` counts decimal places with the same inline expression twice
  (`views/float_range_line_edit.py:143-154`).
- `TimeRangeValidator.validate` (`time_widget.py:35`) logs 6 to 37 DEBUG records per keystroke
  through 19 `logger.debug` calls; drop the per-branch ones.
- **`get_icon` rasterises an SVG at its own small size unless the caller passes `size`**
  (`configs/utils.py:164-167`; 1 of 20 calls does), blurry on HiDPI; its "cleared on each
  process start" comment (`:44-47`) is false - nothing clears `poriscope_icons`.
- **Walkthrough tidiness**: two positioners fight over the card (it jumps from (469,153) to
  (113,194)); closed `StepDialog`s are never deleted (3 after three runs); a `cast()` at
  `walkthrough_mixin.py:150-151` over dead `QDialog` fallbacks at `walkthrough.py:528`, `:535`
  (remove the fallbacks, then the cast); the intro text (`walkthrough.py:115`) omits Protein, which
  has a walkthrough.
- **`WalkthroughStep` is a positional 4-tuple** (`views/widgets/walkthrough_mixin.py:40`), built as
  90 literals across 7 files. A `NamedTuple` names the fields and still accepts the plain tuples a
  contributed tab returns; a dataclass would not.

### Base classes and plugins

- `LogDecorator.log`'s one-shot latch is the same block in `log_call` and `log_return`
  (`LogDecorator.py:168-176`, `:183-191`). One helper over a module-level latch also retires the
  two `setattr`s `DECISIONS.md` 2026-09-02 keeps.
- `MetaController.update_tab_actions`' undo walks back through nested `try/except
  KeyError`/`StopIteration` (`MetaController.py:1006-1044`); `handle_kill_worker:830` nests three
  deep; `MetaView.update_progressbar:432` (72 lines) builds its widget inline; `MetaModel`
  repeats `if key not in self.<dict>` four times (`:244-286`).
- **A plugin whose parent could not be restored is refused with a type error that does not name the
  parent.** The reference resolves to `None` silently (`DataPluginController.py:464-470`) and the
  family's check then says the key "must have as value an object that inherits from MetaReader"
  (`MetaEventFinder.py:1452-1456`). Say which parent is missing.
- `MetaEventTabController.update_available_plugins:79` re-implements the base with the Model
  pushed before the View (`MetaController.py:940` does View first). Only `ConditioningController.py:254`
  reads `MetaModel.available_plugins`, outside this family, so the override is a debug log: delete
  it, with its line in the class docstring.
- `MetaEventFinder`: boundary reconciliation is duplicated in `find_events:332-346` and
  `_find_events_single_range:575-591` - factor it into one helper both call, since `find_events`'
  copy is what protects a finder overriding the other; four comprehensions test
  `idx not in bad_indices` against a list (`:545-560`, quadratic - use a set); the
  `end is None or end == 0` re-check at `:291` cannot fire after the normalisation at `:267-278`.
- `MetaEventFitter.fit_events` coerces `padding_before` and `padding_after` with the same seven
  lines twice (`MetaEventFitter.py:602-616`).
- `MetaReader._get_file_index:863` ends its scan by catching `IndexError` (`:879`);
  `bisect_right`, clamped at 0, says what it means.
- `MetaDatabaseLoader`: the experiment/channel scope clause is hand-built three times
  (`:511`, `:1236`, `:1341`, only the last alias-qualified), and
  `export_subset_to_csv:569` repeats validate/query/raise five times (`:612-674`).
- **The metadata query's table aliases are only half parameterised.**
  `MetaDatabaseLoader.py:1184-1194` builds an alias map that feeds the projection and the WHERE
  qualification, but the JOIN hardcodes `e.id = s.event_db_id` (`:1275`) and `experiments exp`
  (`:1278`), and `_build_subset_events_query` (`:492-503`) hardcodes the whole join. Renaming the
  `sublevels` alias emits invalid SQL. Latent: nothing changes the aliases today.
- **37 hand-rolled `sqlite3.connect`/`finally` blocks** across the four SQLite plugins.
  `MetaWriter._commit_events:367` threads an abort flag through four `try` levels;
  `MetaDatabaseWriter.write_events:103` nests `lookahead_generator` (`:117`), repeats
  try/`close_resources`/log/raise for its setup steps, and its `index = 0` (`:178`) is dead -
  `:192` reassigns it before any read. **M**

### Tests

Test-suite work is the test developer's by default.

- **Other flow tests may read a worker's report before it arrives.** `fit_events` and similar
  helpers wait on `model.workers`, which empties one queued slot before `generate_report` shows the
  report (`MetaModel.run_generators:301-308`); one test read the fit's report as the commit's under
  load (fixed 2026-11-17). Delaying `generate_report` 1.5 s across `tests/integration` gave 16
  failures and 16 errors, but a report that fires after its test ends breaks later tests too, so real
  races are not yet told apart. A probe that cancels its delayed reports at teardown would separate
  them. **S-M**
- **`EventWorker`/`MetaModel`'s worker lifecycle is thinly tested.**
  `test_meta_model_generators.py` covers a refused second request and report-before-finish.
  `Worker.process_generator` has no test, and `MetaModel.stop_workers` is only ever a mock. Scenarios
  worth encoding:
  - *Generator failure*: happy path, mid-run `TypeError`, abort, empty generator.
  - *Worker cleanup*: two independent runs to completion, each popped from
    `workers`/`threads`/`generators` without affecting the other, `deleteLater()` not raising.
  - *`QtHandler` through `emit`* (`test_qt_handler.py` reaches `emit` only in its replay tests):
    the default `ERROR` level, and four errors behind an open dialog all shown once the queue drains.
  - *Abort*: `MetaModel.stop_workers` logging INFO rather than WARNING for a stale key or channel;
    `MainController.handle_abort_all_analysis` reaching every open tab without `exiting=True`; Abort
    Analysis stopping a Raw Data finder on several channels and leaving the tab usable (one channel's
    cancel is tested, `test_results_recorded_when_finished_no_gui.py:84`).
- **`test_replay_runs_together_no_gui.py` records a real Find for each of its three tests** (the
  `recorded` fixture, about 1.1 s of setup each). Build the recorded history once for the module; it
  needs a wait helper not tied to the per-test `qtbot`, and module-scoped inputs. **S**
- **`--time-budget` and the duration check only warn.** Build `tests/test_duration_baseline.json`
  from the median of several Linux 3.12.0 CI artifacts (without it the CI comparison step never
  runs). Add a `history` report to `scripts/test_durations.py` that reads the last 30 develop runs'
  artifacts, counts false failures and lists tests near their budget; switch `--time-budget` to
  failing when it counts none (`DECISIONS.md` 2026-11-17).
  `test_peak_finder.py::test_two_channels_fitted_together_each_get_their_own_report` took 4.8 s
  serial and 6.3 s under 2 workers (2026-11-17) against its 5 s budget. **M**
- **Mocks are almost all unspecced**: 700 bare `Mock()`/`MagicMock()` and 245 more with arguments
  but no spec, against 23 `spec`/`autospec`/`spec_set`. Adopt specs one fixture file at a time,
  controllers and views first.
- **The real-data tier runs on one machine.** The recordings `test_real_recordings.py` and the manual
  checks read are on the first machine only, so the tier skips everywhere else; owed since 2026-10-06
  is a data package that travels with the work (Kyle).
- **A root `__init__.py`** has been tracked since the initial commit; harmless only while `tests/`
  has none. **S**
- **The scripting-guide test runs the shared checkout's code in a clean copy (by reading).**
  `test_scripting_guide_no_gui.py:106-111` runs the guide in a subprocess with no `env`, so with
  Poriscope installed editable from the main checkout the child imports that tree: it failed once in
  a clean copy (2026-11-10) and otherwise passes while testing the wrong code. Pass the worktree
  root on `PYTHONPATH`. **S**

### CI and tooling (not logic changes - no plan needed)

- **No pip cache in `ci-internal-pr.yml` or `release.yml`**, and no workflow caches the pre-commit
  hook environments, so every lint run builds them from scratch; `ci-branches.yml:144`'s
  `pre-commit clean` discards nothing on a fresh runner. Cache `~/.cache/pre-commit` keyed on
  `.pre-commit-config.yaml`. **S**
- **`black` runs only at the manual pre-commit stage**, so formatting is enforced by CI rewriting
  contributors' commits, and never checked on a fork PR. `black --check` at the strict stage keeps "a
  commit never changes your files" true; it reverses a documented choice, so the QA page changes
  with it. **S, ruling**

## Unscheduled - a ruling on whether, before a release

- **Protein two-population calls ignore that filtered samples are correlated (2026-11-18).** Filtered
  noise stays correlated for a median 11 samples (9-14) on `Ub_250mV_0p2MPa_CUSUM_A1`, so a
  100-sample event holds ~9 independent measurements; 5,719 of its 5,997 events are under 100. A
  prototype two-component mixture on the samples, BIC (margin 10) with n divided by each event's
  padding correlation length, resolves none of the 5,817 events under 150 samples, where the
  histogram fit accepts 18; uncorrected it calls 52% of 50-99-sample events two populations. On
  events over 150 samples the two disagree (27 both, 77 histogram only, 20 mixture only). Rulings:
  replace the fit or decide acceptance only (both change results: 4.0), or only label events too
  short (additive: any minor); validate on filtered synthetic events first, and answer
  `DECISIONS.md` 2026-08-26, which ruled BIC out for PeakFinder. Write-up:
  <https://claude.ai/artifact/D7ojrzmfUTXp5Rrq5UD8aJ>. **L, ruling**
- **No accessibility work**: no accessible names, `QShortcut`s, mnemonics or tab order
  anywhere in `poriscope/`; sidebar colours hardcoded (`icon_menu_widget.py:81-89`,
  `text_menu_widget.py:80-89`); Windows-only fonts hardcoded 7 times. **M-L, ruling** (the scope)
- **The 194 `except Exception` handlers are inconsistent about what they leave behind** - some leave
  the UI partially updated. Too broad to work as one entry: name the sites that matter, or drop it.
- **Split `DECISIONS.md` into active and archive**, so a session loads only the decisions that still
  apply (42.4k words on 2026-11-18, 51.2k before the 2026-11-16 trim). The archive must stay
  greppable. **M, ruling** (what counts as active)
- **Coverage cannot see QThread code** (no `.coveragerc`, no `concurrency`), so `EventWorker` (51%)
  and the writers (60-69%) read lower than they are. Nothing consumes coverage since 2026-09-23.
- **Are the Conditioning `Cond PSD Pos` recordings really 500 kHz (2026-11-11)?** All 71 are named
  `PSD-100000_1_500000Hz` and are 12,800,000 bytes, the size of the 10 kHz files. At 500 kHz a
  recording is 0.2 s with 5 Hz bins, so the 1-30 Hz fit uses 6 bins and extrapolates to 1 Hz. No
  answer is recorded; Kyle to ask the lab. The loader's `Sampling Rate` setting covers a mislabelled file.

## Watching - nothing to do unless it happens

- **The Ubuntu test job aborted once in native code (2026-11-03).** CI (Branches) run 41721366639
  attempt 1 on `a84c70ca`: `free(): invalid pointer`, exit 134, after 954 passing tests; attempt 2
  passed. Test #955 is the first of `tests/unit/controllers/test_protein_fetch_slots.py`, right after
  `test_protein_controller.py`, which builds a real `ProteinView`; a Qt widget freed twice at teardown
  fits, unproven. Not reproduced in a matching container, and not seen in the 52 runs and 100 Ubuntu
  test jobs since (to 44363863749 on `48208dbb`). If it recurs, rerun with `-v` so the crash names
  its test; delete this at the 3.0 cut if it has not.
- **`pydoclint` class-attribute bug - filed upstream, awaiting a fix.**
  https://github.com/jsh9/pydoclint/issues/304, open on 2026-11-18; `check-class-attributes` stays
  `false`. The bug is in `docstring_parser_fork`'s `rest_attr_parser.py` (0.0.16 still has it): two
  hardcoded `".. attribute ::"` literals that should be
  `re.compile(r"^\.\.\s+attribute\s*::\s*(?P<name>.+)$")`. Reproduction: a class documented with the
  correct `.. attribute::` directive plus any `:param:` block reports `DOC601` + `DOC603`; a space
  before the `::` makes it pass. Full diagnosis in `DECISIONS.md`.

## Owner-held - flagged for the owning developer, never fixed here

The logic in `PeakFinder.py` and `Basic_PeakFinder.py` belongs to another developer, who is
active. Docstring, signature and type-hint changes there are in scope (both are fully annotated,
with zero pydoclint violations); logic changes are not, even when annotating surfaces a real bug:
write the honest annotation, mark the defect with a narrow `# type: ignore` and a `NOTE:` at the
site, record it here, and leave the fix to the owner. Consult them before any `MetaEventFitter`
signature change, which moves both PeakFinders in lockstep. `NanoTrees.py` is not owner-held (its
co-author has left; `CODEOWNERS` gives it to `@shadowk29` with the rest of `eventfitters/`) and is
no longer a deprecation candidate: it stays, and may be rescued (Kyle, 2026-11-18). Fixing it is
permitted; a fix that moves a stored number is still a break.

### Fitter plugin defects

- **Both PeakFinders truncate a microsecond time to a sample index** (`int(... * samplerate * 1e-6)`
  at `PeakFinder.py:1919-1922` and `:1950-1956`, `Basic_PeakFinder.py:1070-1075`), which floating
  point can put one sample early: 7 samples at 3 MHz multiply back to 6.9999 (2026-10-09). The tabs'
  identical conversions round since 3.0. Rounding moves a stored level by up to one sample: 4.0.
- **`Basic_PeakFinder.find_mode_blockage_level` guards two of its three Optional parameters.** The
  body (`:1231`) handles `data is None` and `baseline_std is None`, then uses `baseline_mean`,
  equally `Optional[float]`, unguarded at `:1282` and `:1290` (the second carries no marker).
  PeakFinder's raises.
- **`Basic_PeakFinder._populate_event_metadata` can put `None` into event metadata** (`:1068`,
  `:1083`), whose declared value type is `Union[int, float, str, bool]`. A `None` reaching the
  database writer is not something that contract allows for.
- **`Basic_PeakFinder` writes `NaN` into `sublevel_current` for 23 of 25 events** on the
  conformance dip fixture, from an `np.median` over an empty slice (`Basic_PeakFinder.py:715-735`) -
  a zero-width level whose mean is undefined. Same family as the `sublevel_max_deviation`
  zero-width crash fixed 2026-08, which now returns `0.0`; this path returns `NaN` instead and no one
  notices. In event 0 it is sublevel 9, a row carrying a valid `peak_height` (434.4) with
  `sublevel_current` `NaN`. Distinct from the plugin's *structural* `NaN`s, which are fine:
  it emits 15 sublevels per event interleaving peak rows with the level rows between them,
  so the 16 peak-specific columns are `NaN` on every non-peak row by design. The run emits
  134 `RuntimeWarning`s that conformance cannot see, since no check asserts finiteness. Writing a
  number there changes results: 4.0.
- **`NanoTrees._DNA` slices with two unguarded `Optional[int]` paddings** (`NanoTrees.py:571`), so
  the negation raises `TypeError` for any event loader supplying neither. It has no live caller - the
  only call site is commented out (`:660`).
- **`NanoTrees._locate_sublevel_transitions` overwrites both baseline arguments** (`:655-656`),
  recomputing them from `data[:padding_before]` and discarding what the loader passed. Possibly
  deliberate, but the two parameters are inert and the docstring's promise to handle `None` is met by
  accident. Four of its author's `ToDo` notes are also open (`:252`, `:300`, `:842`, and `:1236`, an
  empty slice when the rise time outruns the sublevel).

### Open against the PeakFinder integration

- **The direction classifier's plot drops the outer tails.** `_classify_translocation_direction`
  fits a trimmed 5-95% core (`PeakFinder.py:4207`; `DIRECTION_FIT_PERCENTILES`, `:182`), and its plot
  (`:4339-4418`) `np.histogram`s the full array against the core's bins, which silently discards about
  the outer 10%. The other two classifiers fit the full data (`:3060`, `:3664`) and bin plots against
  the fit's histogram (`_histogram_for_fit:6078`), so they no longer cut off.
- **`feature/peakfinder_EM` is neither merged nor recorded.** A local branch only (its remote is
  gone): 6 commits by the owner, 2026-08-28 to 08-31, adding a Student-t EM fit and a 2-D
  prominence-by-width classifier, 3,027 lines of `PeakFinder.py` changed against a base 32 `develop`
  commits old. Ask whether it is abandoned or pending; it reworks the plotting the entry above names.
- **Three questions the records leave open** (2026-11-18): the Protein and PeakFinder double-Gaussian
  fits, shared by copy, now bound sigma differently (a quarter bin and half a bin); the prominence
  log-scale fit was to be revisited on the first real dataset (`PROMINENCE_FIT_LOG_SCALE`,
  `PeakFinder.py:208`, `DECISIONS.md` 2026-09-15); and two `None`-threshold guards cannot fire
  (`fit_fallbacks.md`, "Guards that cannot fire").
