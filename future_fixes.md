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
under the release they target - 2.1, 2.2, Later, and Owner-held - grouped within each
by topic or by the review that found them. Move an entry between releases rather than
re-labelling it in place.

Sources: the 2026-09-24 whole-codebase review, seven parallel reviewers with claims checked by
execution (SWOT and roadmap: <https://claude.ai/artifact/NsZSdFtsenMyANLEDLWvKq>; items marked
*(by reading)* were derived from the code, not reproduced); the 2026-09-03 six-slice review
(<https://claude.ai/code/artifact/0886d408-06de-488d-8a8e-7f6a68206651>); and the 2026-08-25
structural audit (<https://claude.ai/code/artifact/a1bec2cd-a157-4299-acb3-a135738fee41>).
Line numbers were re-verified 2026-09-24.

## 2.1 - trust the numbers

Accuracy tests against ground truth, reader and database correctness, type checking that sees the MVC layer, a Windows CI leg.

**Plan:** <https://claude.ai/artifact/W9G3cHAQvSopQsRrJH6s3z> (order, rulings, live gate figures,
per-step commit series; updated as steps land). Items below sit under the plan's step; each step is
re-measured at HEAD when it comes up. Anchors re-verified 2026-10-05 at `90ad82e9`. Rulings so far
(Kyle, 2026-10-05): the ground-truth harness is ours to build; one release, step 8 included (the
PeakFinder owner approved its changes 2026-10-09); runtime pins loosen to compatible ranges while
`requirements.txt` stays exact; the ABF offset arithmetic is correct (`DECISIONS.md` 2026-10-05).

**Two tracks** (Kyle, 2026-10-05). Steps 1-8 and 10 are Kyle's track, in order. **Step 9 (9a, 9b) is
Carolina's track**, run in parallel: its files (`plugins/analysistabs/`, `utils/Meta{View,Controller,
SubsetTab*,EventTab*}`, `views/main_view.py`) and its instruments (duplication and complexity
ratchets, MVC boundary allowlist, headless flows) are disjoint from the data-plugin layer steps 1-6
change, and tabs reach plugins only through `call()`. Rules of the road: start once step 0's Windows
and wheel runs are green on `develop`; one feature branch per sub-step, in the order 9a lists; a
promotion updates `.duplication-baseline.json` in the same commit; each track edits only its own
step sections here and its own changelog lines, and rebases onto `develop` before `feature finish`.
Step 10 waits for both tracks.

### Step 8 - data-plugin API break (breaking)

Design ruled by Kyle 2026-10-09 (plan page, step 8 Q1-Q6), replacing the 2026-09-22 scope. The
PeakFinder changes below are approved by Nada (2026-10-09).

- **`PeakFinder.py:1019-1045` carries the CUSUM detector step 5 fixed**: reset only on an accepted
  jump and `varS = 0` outside the reset (`:1045`). Apply `CUSUM.py:315-330`'s form.
- **`"μs"` where every other plugin writes `"us"`**: `PeakFinder.py:2068`, `Basic_PeakFinder.py:1197`
  and four settings labels at `Basic_PeakFinder.py:127-140`.
- **Event paddings truncated to whole µs**: `SQLiteDBLoader.py:1021-1022` `int()`s both paddings (up
  to 4 samples at 4 MHz). Keep them float; the declared tuple on `MetaDatabaseLoader._load_event_data`
  changes.

### Step 9a - analysis-tab views (Carolina's track)

- **The experiment/channel scope has three annotations for one value.** The tab layer declares
  `Optional[Dict[str, List[Optional[int]]]]` in 9 signatures (`MetadataController.py:513/603/674/742`,
  `ProteinController.py:225/524/566`, `MetaSubsetTabController.py:111`, `MetaSubsetTabModel.py:114`);
  `MetaDatabaseLoader` and neighbours declare `Optional[Dict[str, Optional[List[int]]]]` in 14; the
  selection tree stores `Dict[str, Dict[str, List[str]]]` (`MetaSubsetTabView.py:204`), converted at
  `MetadataView.py:2022` and `:2127`. The producer at `MetaSubsetTabView.py:796` builds
  `{exp: [channel] or None}`, so the loader's form is correct and the 9 are transposed; invisible to
  mypy because the value passes through `call()`.
- **The column-names chain lives on the subset-tab bases but only Metadata runs it.**
  `MetaSubsetTabView.update_available_columns:1013` emits `column_names_requested` (`:115`),
  `MetaSubsetTabController.request_column_names` (`:98` connect) answers it by calling
  `self.view.update_column_names`, which only `MetadataView.py:2597` defines; `ProteinView`
  never calls `update_available_columns` (its callers are `MetadataView.py:1388`/`:1901`), so
  on Protein the slot would raise `AttributeError`. Found by mypy once `view` was declared
  (2026-10-05). Move the method, the signal and the slot to the Metadata pair, as
  `update_column_units` was in 2.0.0; `test_protein_view.py:1031`/`:1188-1220` and
  `test_plugin_state_notifications.py` pin the inherited method and go with it.
- **`_shift_range_and_update_plot` is four copies in two drifted pairs.** Subset tabs
  (`MetadataView.py:1990`, `ProteinView.py:1160`): Metadata clamps to `n-1`, Protein wraps to 0;
  only Metadata reports no scope; Protein dispatches on `_last_event_action`. Event tabs
  (`RawDataView.py:461`, `EventAnalysisView.py:194`): different exceptions, only RawData reports
  underflow. Neither base has the hooks the bodies call, so: add hooks to
  `MetaEventTabView`/`MetaSubsetTabView`, rule the differences, then promote, with
  `_get_event_index_text` (`RawDataView.py:528`, `EventAnalysisView.py:252`).
- **The capture-rate plot always reports one row dropped.** `MetadataController.fit_capture_rate:420`
  (`:472`) compares surviving intervals against the **event** count; n events make n-1 intervals.
  Compare against `initial_length - 1` and delete the test pinning the current behaviour.
- **`set_heatmap` passes bin centres as the `imshow` extent** (`MetadataView.py:986`), compressing
  the image by a bin width.
- **`RawDataModel.get_baseline_stats:117` is a pre-2026-09-20 copy of the finders' baseline fit**
  (linspace bin centres, so sigma comes back × bins/(bins−1); `argmax` peak; the old window and
  bin count), feeding the tab's baseline readout. After 2.1 step 4 (ruling D) it disagrees with
  the finders' fit; share the base fit instead of keeping a second one.
- **`format_axis_label` truncates a column name containing parentheses.** `\s*\(.*?\)$` anchored at
  `$` lets the lazy `.*?` expand across every `)`, so `Rate (per pore)` with unit `Hz` becomes
  `Rate (Hz)`. Two copies, `ProteinView.py:2337` and `MetadataView.py:2840`; pinned in
  `test_duplicated_helpers.py:273-316`, so the fix updates those tests.

### Step 9b - breaking tab designs and the milestone guard (Carolina's track)

- **Raw SQL subset filters can be saved but never plotted.** Six call sites refuse them
  (`MetaSubsetTabView._refuse_raw_filters:234`, from `MetadataView.py:1409`/`:2070` and
  `ProteinView.py:1359`/`:1454`/`:1713`/`:1874`). Design settled (`DECISIONS.md` 2026-09-14): a raw
  filter goes to `query_database_directly` (`MetaDatabaseLoader.py:1416`) as written, ignores the
  experiment/channel selection, and a plot missing a column it needs says which. Clustering only
  gets this through the shared filter base queued under Later.
- **Action history: record a declared action name, not a method name.** `DECISIONS.md`
  2026-09-17 settled the design. 5 `@register_action` sites over 3 names, all private
  (`_reset_actions` on Clustering/Metadata/Protein views, `MetadataView._overlay_plot:1396`,
  `ProteinView._update_distribution_ensemble:1860`); replay is `getattr(self, name)` via
  `MetaView.update_actions_from_json:389` (`:396`). Saved action files carry no compatibility
  obligation (Kyle). Declared names, registry dispatch, small JSON-round-trippable arguments, and a
  docstring on `register_action` (`LogDecorator.py:177`, none today). Breaking.
- **A milestone blocks the page switch but not what caused it.** `MainView.switch_to_page:895`
  refuses (`:912`) while `_milestone_dialog` is up, but every caller does its work first:
  `on_raw_data_view_click:611`/`on_event_analysis_click:617`/`on_metadata_click:623` emit
  `instantiate_analysis_tab` then `sync_sidebar_highlight` then `switch_to_page`;
  `handle_menu_click:692` and `on_load_analysis_tab_button_click:714` (`:722`) highlight first.
  Move the guards at `:899-924` into a predicate asked before the handlers act.

### Step 2b - ABF readers on pyabf (deferred to here; ruling H, `DECISIONS.md` 2026-10-06)

- **One general `ABFReader` plugin, header from `pyabf` (`ABF(path, loadData=False)`, 2.3.8
  suffices), memmap by the plugin**, usable alone with one file as the dataset; the shipped
  readers become subclasses adding only `_get_file_pattern`, `_get_file_time_stamps` and
  `_get_file_channel_stamps` (set recognition and ordering); `LegacyElementsReader` may collapse
  into the base; retire `helpers/ABF2Header.py` and its tests; `pyabf` moves from `dev` extra to
  runtime dependency. Spike (2026-10-06, 13 real files): headers and conversions agree to
  3.6e-12 pA. Rate from the protocol section's `fADCSequenceInterval` (not the `int` `dataRate`
  nor `dataSecPerPoint`); rule the offset form (`pyabf` adds offsets, `ABF2Header` folds them;
  no real file has a non-zero one). Goldens: S1.4's int16 recipe and `test_real_recordings.py`.

### Step 10 - docs dead-link gate and release prep

- **The API reference has no dead-link gate.** `-W` passes while references are unresolved
  because `conf.py` has no `nitpicky`. With `-n` the build reports 1,463 warnings: about 1,350 are
  numpy, pandas, Qt and typing names (intersphinx + `nitpick_ignore_regex`), about 117 ours across
  ~25 files - wrong-owner `:meth:` targets, unqualified short names, undocumented internal classes.
  Fix ours, then turn `nitpicky` on.
- **The standing-policy text at the end of this file** says "all three owner-held fitters"; only the
  two PeakFinders are owner-held and NanoTrees is a deprecation candidate. Correct it.

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
  `metadatacontrols.setupUi` (523), `PeakFinder.report_status` (472),
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

### Provenance stops at the fitter (2026-10-08)

A database's `channels.provenance` records the writer, the fitter and the event loader, which is
all the database writer can reach. The reader, finder and filter that produced the events are not
stored in the events file (`SQLiteEventWriter.py:84-118`), and a filter is a callable, never a
setting. Carrying them needs the events writer to record them and the event loader to expose them.

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
