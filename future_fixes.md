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

### Four plan-step citations survived the sweep (2026-09-24)

`refactor_2.0.0.md` is deleted when 2.0.0 ships. Rewrite each as the mechanism it stands for;
docstring/comment-only, so no tests and no changelog entry:
`scripts/autodoc/metaclasses_generate_autodoc.py:128` ("Step 3b"),
`tests/unit/scripts/test_duplication_ratchet.py:5` ("Steps 3a-3c"),
`tests/unit/scripts/test_mvc_boundary_allowlist.py:7` ("Steps 3-5"),
`tests/integration/flows/test_clustering_flow_no_gui.py:10` ("Steps 3-5").

### Action replay re-reads the filter selection instead of replaying it (2026-09-17)

Both non-trivial `@register_action` methods call `self.get_selected_filters()` inside their
own bodies - `MetadataView._overlay_plot:1405` and
`ProteinView._update_distribution_ensemble:1898` - and that reads
`self._subset_controls.filter_comboBox.getSelectedItems()`, i.e. live widget state. Everything
else the action needs arrives in its recorded `parameters` dict, so **replaying a saved plot
applies whichever filters are selected at replay time**, silently, and the plot is not the one
that was saved. Capture the selection into the recorded payload at record time and pass it in;
`_reset_actions` already reads nothing. `DECISIONS.md` 2026-09-17 rule 5 is the standing rule
this violates.

**It is reachable from Undo, not only from a saved file** (2026-09-24). `@register_action`
records after the call whatever it returned (`LogDecorator.py:177-194`); a refused overlay -
including "every dataset already plotted", so a double-click on Plot - emits `(None, True)`
(`MetadataView.py:1941-1943`), and `MetaController.update_tab_actions:443-484` then replays
the *whole* remaining history, since nothing truncates it at `_reset_actions`. Measured with
a stub harness: one refusal after 10 overlays replayed 11 actions, each re-querying the
database on the GUI thread. Plot under filter A, switch to B, plot, Undo: the replay draws B.
Fix ahead of the registry below: pop without replaying on refusal, replay only from the last
`_reset_actions`, and record the filter selection in the payload.

### The metadata export flow is still intermittently flaky

`tests/integration/flows/test_metadata_export_flow_no_gui.py` failed once on 2026-09-22 with
`pandas.errors.EmptyDataError: No columns to parse from file`. `a35e7bc8` made the wait
(`subset_is_written:141-159`) require the three table CSVs to parse with rows, but a race is
still live: `MetaDatabaseLoader.export_subset_to_csv` writes `data.csv` (`:683`) and only then
the per-event `{name}_event_{id}.csv` files (`:700`), while `export()` returns
`folder.glob(f"{name}_*.csv")` (`:161`) - which includes per-event files still being written -
and `row_counts()` (`:178-195`) reads every one. Glob only the table files, or wait for the
worker to finish. Derived from the code, not reproduced.

### Data integrity and scientific correctness

- **The raw write path drops scale and offset.** `MetaWriter._commit_events:421-424`
  takes the raw path whenever the finder's dtype equals the writer's `<f8`, and
  `SQLiteEventWriter._write_data` never applies scale/offset (`:526-528`). `SingleBinaryDecoder`
  (float64 by default) with Scale=2 stored `baseline_mean` 1999.9 pA against a trace median of
  996 pA, so every fitted metric from that database is wrong.
- **A second commit into an existing events file silently keeps the old events.**
  Nothing resets the channel (`RawDataController.commit_events:171`); `channels.channel_id` is
  UNIQUE and events use `INSERT OR IGNORE`; the file dialog passes `DontConfirmOverwrite`
  (`dict_dialog_widget.py:304`). Commit 10, re-find 5, commit: "Wrote 0/5", no reason given, 10
  old events remain. More events the second time mixes both runs.
- **Reader filename globs over-match sibling prefixes.** `prefix*.log` at
  `ChimeraReader20240501:223-225`, and the same shape in `ChimeraReaderVC100:209-212`,
  `TCossaLabABFReader:229-231`, `LegacyElementsReader:113-115`, `ChimeraReader20240101`:
  opening `exp1_…` also reads `exp10_…` (channel 3 read 1.0 s where the file holds 0.5 s).
- **CUSUM `Sensitivity` is documented backwards.** `CUSUM.py:76-77` and
  `event_analysis_tab.rst:68` say "higher is more conservative"; `:824` returns
  `threshold / Sensitivity`. At a 2σ step, Sensitivity 1 gave 3 levels in 30/30 events and
  Sensitivity 5 gave 6-26.
- **The fitter contract's own docstring example is rejected by the base.**
  `MetaEventFitter._locate_sublevel_transitions`'s example (`:936`) returns 3 entries with no
  terminal index; `fit_events` rejects 3 or fewer as "Too Few Levels" (`:653`) and expects
  `len(sublevel_starts) - 1` values per key (`:690`), while `:959` says "exactly equal".
- **`NoFitter` passes per-event state through `self.rise_time`** (`NoFitter.py:228`
  written, `:268` read) on an instance shared by parallel channel threads: 30 of 3,000 events
  took another channel's `sublevel_stdev` with the switch interval forced to 10 µs, 0 at 5 ms.
- **One NaN rejects an event as "Too Few Levels".** It poisons `varM` and every
  comparison goes false; reject with an explicit "Non-finite data" reason instead.

### Session and settings persistence

- **Loading the wrong JSON destroys the workspace and the autosave.**
  `MainController.load_session:651-664` calls `reset_session()` and `save_session()` before
  checking the file's shape, then indexes `plugin["metaclass"]` outside any try: a
  `tab_action_history.json` (same folder, same `*.json` filter) raises `KeyError` in the slot
  after `plugin_history.json` is overwritten. A parse failure logs at INFO, below the default
  level, and reaches no panel. Validate before resetting; do not autosave until restored.
- **Quitting after a reset writes `{}` over the session.** `handle_about_to_quit`
  saves unconditionally (`main_controller.py:133`) though `reset_session` tells the user saved
  files are untouched. Decide what quit-after-reset should do.

### Numeric input and widgets

- **Float fields break under a comma-decimal locale** in every plugin-settings dialog:
  `NumericLineEdit` uses a locale-following `QDoubleValidator` (`numeric_validation.py:57`) but
  parses with `float()` (`:77`, `dict_dialog_widget.py:376-389`), and the app sets no `QLocale`.
  Under fr_CA a pre-filled `1.0` disables OK, `0.5` is saved as **5.0**, and `1,5` raises.
  Same in `clustering_settings_widget.py:285-287`.
- **`CustomIntValidator` returns `Invalid` for in-range prefixes**
  (`numeric_validation.py:103-108`): with Min=10 you cannot type 15, and `-` never, so
  PeakFinder's two `Min: -10` fields (`PeakFinder.py:389-400`) cannot be re-entered once cleared.
- **Finishing the tutorial inside a dialog, then closing it, raises `AttributeError`**:
  the `finished` lambdas at `ClusteringView.py:485-488` and `MetaSubsetTabView.py:648-651` call
  `dialog.walkthrough_dialog.force_close()` after `walkthrough_mixin.py:209` set it to `None`.
- **The clustering dialog's Apply ignores method and parameters**
  (`_check_apply_enabled`, `clustering_settings_widget.py:540-579`); the error surfaces later
  in `ClusteringView.py:590-614`.
- **Three widget modules call `logging.basicConfig(DEBUG)` at import**
  (`views/widgets/time_widget.py:35`, `utils/BaseLineEdit.py:34`,
  `views/float_range_line_edit.py:39`): importing `main_app` leaves root at DEBUG with a stray
  handler, so every console line prints twice; `TimeRangeValidator` logs ~10 records a keystroke.
- **The icon sidebar's Help and Settings emit their switch signal twice**
  (`icon_menu_widget.py:320-326` and `:291-292`), so `on_settings_button_click` runs twice.
- **Broken icon references**: `help-252.png` does not exist (`icon_menu_widget.py:151`);
  `tcossalab.png` (`:259`) is `TCossaLab.png` on disk, which breaks on case-sensitive Linux;
  the text menu's "Raw Data" reuses `stats-black.svg` (`text_menu_widget.py:131`).

### Analysis tabs

- **Dead load-plot branch**: `MetadataView.py:1948-1951` calls
  `self._update_actions_from_json`, which exists nowhere, behind a condition that is always
  false; `ProteinView._update_distribution_ensemble` returns None, so it never rolls back a
  refusal the way Metadata does.

### Types, tests and CI

- **The duplication ratchet fails any new method as added duplication**:
  `measure_duplication.py:404-419` has no `functions` special case (the complexity ratchet got
  one, `measure_shell_complexity.py:397`), so one trivial method in `MetadataController`
  fails with "rose from 68 to 69 - duplication was added". Conversely a new plugin file is never
  measured, since the family lists are explicit.
- **`ci-internal-pr.yml:129` runs `--maxfail=1 --disable-warnings`**, unlike every other
  workflow, hiding every failure after the first.
- **The post-merge wavelet hook reaches deep into a contributor's machine**: without
  MSYS2's `mingw32-make`, `full_setup_and_build.py` runs `pacman -Syuu --noconfirm` (`:113`)
  before checking the tracked DLL exists (`:125`), and opens a modal folder dialog mid-merge
  (`:38-59`) whose cancel fails the hook.
- **The shipped `wavelet.dylib` is an x86-64 Linux ELF** (cross-built by `make dylib` on
  Ubuntu, `build_wavelet.yml:76`), so `WaveletFilter`'s Darwin branch (`:160`) cannot load it.
  Build a Mach-O on `macos-latest` or drop the macOS claim.
- **Wavelet rebuilds are not deterministic**: `build_wavelet.yml` rebuilds on every
  push to main (20+ bot commits differing only in the PE timestamp, e.g. `1b072fe4` ->
  `9d2b9e8a`, 673,945 bytes each), so `origin/main` holds commits `develop` lacks. Make it
  `workflow_dispatch`-only or link with `--no-insert-timestamp`.
- **Stale line-number comments** in `test_data_plugin_controller.py:903-1126` ("lines
  88-91", "lines 56-73") point into docstrings since `edit_plugin` was split. Comment-only.

### Docs and records

- **The autodoc generator writes 9 dead base-class links** (`plugins_generate_autodoc.py:315-316`
  prefixes any non-Meta base with `poriscope.plugins.`, e.g. `poriscope.plugins.CUSUM`) and
  publishes private helper classes; `conf.py` has no `nitpicky`, so the `-W` build passes.
- **`future_refactors_and_features.md` analyses deleted code** with no status markers:
  Part 5 #3 (`:871-880`) and Part 6 #2 (`:1044`) study `handle_global_signal`/`_relay_global_signal`,
  Part 1's `BasePluginControls` exists as `MetaControls`, and it cites `global_signal` 10 times.
  Delete what the refactor made moot; tag the rest open or partial.
- **Distil `refactor_2.0.0.md` before deleting it at release**: its ~96 method rules go
  to the `planning-and-executing-changes` / `refactoring-codebases` skills, lasting decisions to
  `DECISIONS.md`, then delete it and its `CLAUDE.md` entry.
- **The dev install instructions disagree**: `README.md:15` and
  `plugins_manual/getting_started.rst:59` say `pip install -e .`, `CLAUDE.md` and the post-merge
  hook need `.[dev]`, and the getting-started page never mentions `setup_hooks.py`; README typos
  ("dor", "run_"). No CONTRIBUTING.md.
- **Stale claims in the docs and changelog**: `quality_control.rst:1284` says the tab
  layer "never grew a real Model" (the Models are 2,608 lines); the 2.0.0 changelog cites "113
  known violations" beside a live 2 and "22 of 24 data plugins" beside "all 24"; both Chimera
  readers' `get_empty_settings` docstrings name a `.mat` settings file their JSON-based
  `_get_configs` never reads (20240101 `:410-415`, 20240501 `:380-385`).
- **Two stale docstrings in the app shell**: `SerializeDecorator.py` says `__wrapped__`
  matters for "the signal dispatcher in `MainController`", which is gone, and
  `main_model.py`'s `load_plugin` has a Google-style docstring with the wrong parameters.
- **`DECISIONS.md:1772` rests on a premise that did not happen**: that `WalkthroughMixin`
  folds into the base. It is still a mixin with four hosts, two outside `MetaView`; correct the
  entry or schedule the fold.
- **Remove the leftovers of the bus on `MetaController`**: `call`/`_get_plugin`/
  `_plugin_instances` (`MetaController.py:184-262`) duplicate `MetaModel`'s with no production
  caller, plus `MainController.get_plugin_instance(…, callback)` (`:377`, tested but uncalled),
  `MetaController.ignore()` and `MainController.config_path` (`:52`). Breaking on a `Meta*` base.

### Left open by the 2.0.0 refactor (2026-09-22)

- **`ProteinView.available_columns` is write-only** (`:322`, `:652`) since `de13e2eb` removed
  its reader; only `tests/unit/views/test_protein_view.py:278` reads it.

### From the 2026-09-03 review - high

- **The two session writes are non-atomic and omit `default=serialize_object`.** The
  config write uses it; `save_session` (`main_model.py:457`) and `save_tab_actions` (`:496`)
  open the file for writing and then `json.dump` without it, so a value neither can serialise
  raises mid-write - now caught and reported, but the file `_suppress_session_save` exists to
  protect is already truncated. Write to a temporary file and `os.replace`.
- **`SQLitePeakDBLoader.py:150-153`'s comment is stale** since `f6f75a8e`: it says
  `query_database_directly` returns None for an empty result, which now returns an empty
  frame. Comment-only.

### From the 2026-09-03 review - CI, packaging and tooling (not logic changes - no plan needed)

- **`test_mapping_audit.csv` is stale and nothing executable reads it.** Its
  `LooseMatchFound` column still names files renamed by the very commit that added it
  (`43d556d`). Referenced by nothing but this entry. Regenerate or drop.

### From the 2026-09-03 review - Docs

- **One stale doc claim.** `future_refactors_and_features.md:283` still asks someone to
  confirm whether `PluginManagerPopup.py` is dead code; it was deleted in `d0dbc53`.

### Other queued items

- **Three `scripts/autodoc/` lint sites are ours to fix, and are the only part of the
  declined-rules sweep that is.** Two `S110` in `metaclasses_generate_autodoc.py:237-238` and
  `plugins_generate_autodoc.py:227-228`, one `S112` in the latter (`:279-280`). Fixing them would not enable
  either rule. **Not licence to re-propose the rules** - `DECISIONS.md` records why all six
  stay off, per rule.

## 2.1 - trust the numbers

Accuracy tests against ground truth, reader and database correctness, type checking that sees the MVC layer, a Windows CI leg.

### A milestone blocks the page switch but not what caused it (2026-09-21)

Found during a manual pass; **pre-existing**. `MainView.switch_to_page:893` refuses to change
page (`:909`) while `_milestone_dialog` is up and the target is not `_expected_next_view` - but
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
final call.

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
`MetadataView._overlay_plot:1395` and `ProteinView._update_distribution_ensemble:1887`. Replay is
`getattr(self, name)` on the View via `MetaView.update_actions_from_json:387` (`:394`), so renaming a
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

### Other queued items

- [2.1] **Raw SQL subset filters still cannot scope a plot**, and the fix is a feature build in
  `MetaDatabaseLoader` rather than a defect repair - see `future_refactors_and_features.md`
  Part 13. Queued deliberately for after the 2.0.0 refactor.
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
- **Conformance recipes never leave the happy path**: add non-unit scale, a re-commit,
  sibling-prefix files and multi-file sets, which is where the four entries above live.
- **`NoFitter` places event edges asymmetrically** (`NoFitter.py:226`): the start walks
  back to the baseline crossing, the end sits `rise_time` before the threshold crossing (838
  against 860 on a 40-sample ramp), so the overlay and `raw_ecd` shift left.
- **ABF conversion folds the offsets into the gain** (`ABF2Header.py:199-200`) instead of
  `raw*gain + (instOffset - sigOffset)`, and `TCossaLabABFReader:253` hardcodes offset 0.0.
  Latent: the synthetic ABF writer uses 0.0 offsets.
- **`LegacyElementsReader` cannot open a multi-file set**:
  `_get_file_channel_stamps:96` returns `[0]` whatever the count, so sorting raises
  `ValueError` (verified with `_0000`/`_0001`).
- **`MetaReader.load_raw_data:296` returns the last file piece's scale/offset**, so a
  read across files with different gains is mis-scaled; `_set_sample_rate:719-726` checks only
  each channel's first file. `_sort_objects_by_channel_and_time:937-941` raises `TypeError`
  on a timestamp tie *(by reading)*.
- **`SQLiteDBLoader._load_event_data` drops an event on a NULL `padding_before`** via
  `try … continue`, logging only at INFO.
- **`IntraCUSUM` defaults make it count noise**: threshold and hysteresis both 0.0
  (`:89`, `:95`) scored 499 crossings on a clean single level (2 at T=200, H=20); nothing
  checks hysteresis < threshold.
- **`ClassicCUSUM` merges short levels on a median but reports them on CUSUM's
  single-sample fallback**, so the merge decision and the reported current use different
  estimators.

### Session and settings persistence

- **`apply_settings` assigns `raw_settings` before validating** (`BaseDataPlugin.py:422`),
  so a rejected edit leaves the rejected values on the plugin.
- **`MetaModel.run_generators` indexes `self.generators[key]` unguarded** (a `KeyError`
  in a slot if nothing was staged), and `set_generator` silently drops a generator for a
  running (key, channel) without closing it.

### Analysis tabs

- **The Metadata and Protein `_shift_range_and_update_plot` copies have drifted**
  (`MetadataView.py:1977`, `ProteinView.py:1187`): past the end, Metadata clamps and wraps to 0
  while Protein lands on `n_events`; only Metadata tells the user when no scope is selected.
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
  2026-09-22). `MetaEventFitter.reset_channel:325-356` ignores `None` and writes
  `eventfitting_status[None]` behind four `type: ignore`s; `close_resources` is `pass` in 15 of
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
- **The baseline histogram is coarse, at `int(len(data)**(1/3)/2)` bins** (`MetaEventFinder.py:1029`). (Same method as
  Part 15 of `future_refactors_and_features.md`; likely belongs in that piece of work.) That is 10 bins
  on a 10k-sample chunk, of which ~6 survive the two windowing passes, and the
  log-linearised fit is biased high at that few points: +2.3% at 10k, falling to +0.2% at
  1M. Rice's rule would give four times as many bins. Retuning it changes which events are
  found, so it needs the same treatment the σ correction got, not a quiet edit.
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
  `MetaReader.py:461-462` and `:505-506` convert an integer sample index to seconds and
  `:161-162` (also `:407-409`) truncate it back; measured, `int((i/sr)*sr) != i` for 7.7% of the first 2M indices at
  100 kHz, and when it slips low `i += len(data)` (`:468`, `:510`) compounds it. Pass sample counts, or
  `round()`.
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
- **`get_single_event_data` returns `None` on a bad index** (`MetaEventFinder.py:834`) and
  yields it into the writer (`:731`), which then fails on it as a swallowed rejection. It
  should raise.
- **Silent scientific fallbacks with no metadata flag, in `CUSUM.py`.** For a sublevel
  shorter than `rise_time`: `sublevel_current` becomes the single last sample before the next
  level's onset instead of a median (`:438`), `sublevel_stdev` becomes `baseline_std` (`:466`), and
  `sublevel_blockage` becomes an unsigned max-absolute instead of a signed mean deviation
  (`:493-502`). The retry loop at `:370-372` fits different events in one channel at 1.5^0
  to 1.5^4 times the user's step size and records which nowhere. `:215`'s
  `np.std(data[-padding_after:])` returns the whole event when `padding_after == 0` and its
  sibling returns `nan` when `padding_before == 0`, poisoning `step_size` at `:221` (both
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
  (10 of them) - including `WaveletFilter.py:178-179`'s `os.add_dll_directory`, in the one module
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
  an accepted jump**, (`CUSUM.py:314`), so a crossing rejected by the `rise_time` guard still accumulates
  `varS` across the rejected boundary - the same bias the landed fix removed, just rarer. It
  also leaves `gpos`/`gneg` above threshold, so the next iteration re-detects and re-rejects
  the same jump. Moving to the unconditional form changes detection behaviour and needs
  validating against reference data first.
- **The `length - jump > rise_time` half of the C's edge guard is still missing**, already
  flagged by a comment in the loop (`CUSUM.py:301-302`). Adding it would suppress a transition detected too close
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
  (88) shared by `CUSUM`/`NoFitter` (`CUSUM.py:573,668-745`, `NoFitter.py:422,517-594`), plus 33
  of no-op stubs. `ClassicCUSUM.py:94`'s
  `_locate_sublevel_transitions` is a 202/205-line near-copy of `CUSUM.py:178`, 6 lines
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

### Leftovers from `future_refactors_and_features.md` Parts 10-12 (2026-09-24)

- `MainView` menu table: 9 `addMenu` + `add_plugin_actions` blocks at `main_view.py:420-467`
  and nine one-line `on_load_*` wrappers (`:558-714`).
- `SettingsWindow` rows hand-built as HBox + widget + `add_horizontal_line()` in
  `add_general_tab_contents:504`, `add_advanced_settings_tab_contents:571`,
  `add_about_tab_contents:669`; two opposite 6-entry log-level dicts at `:771` and `:785`.
- Select-all branches identical in `multiselect.py:148-155`, `multiselect_filter.py:241-248`
  and `SelectionTree.py:169-186` (three of four identical).
- `dict_dialog_widget.on_ok:368` dispatches by nested `try/except AttributeError` probing.
- `clustering_settings_widget` builds its checkbox rows three times (`:301`, `:384`, `:512`).

### The two Chimera readers are near-identical, and the deprecation resolves it

`ChimeraReader20240101` and `ChimeraReader20240501` differ in **27 lines of ~396**. The only
real difference is `_get_configs`: 2024-01 parses a JSON header embedded in the `.log` file,
2024-05 reads a companion `.json` of the same stem. Everything else - `_map_data`,
`_get_file_pattern`, `_get_file_time_stamps`, `_get_file_channel_stamps`, `_set_raw_dtype`,
`_convert_data`, `_convert_raw_data` - is byte-identical, and the pair is the largest single
contributor to the `datareaders` duplication figure (446).

**Do not give them a shared base.** `ChimeraReader20240101` is slated for deprecation in a
future cycle (Kyle, 2026-09-22), so making the surviving reader subclass it - the
`LegacyElementsReader(TCossaLabABFReader)` pattern this family already uses - would mean
unpicking the inheritance before anything could be deleted. Deprecating 20240101 removes the
duplication for free, and should take `datareaders` to roughly 100.

If it has to move sooner, the direction is the other way round: `ChimeraReader20240501`
absorbs what it needs and stands alone, leaving 20240101 a clean deletion.

### Session and settings persistence

- **The autosaved `tab_action_history.json` is never read back** except by a manual
  "load actions".

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
- **Popup helpers are still triplicated** across the two multiselect boxes and
  `SelectionTree`; `SelectionTree.show_dialog` has no Cancel; select-all in the filter box
  emits `selectionChanged` N+1 times; the popup lists hide their scrollbar (`multiselect.py:58`).
- **No accessibility work**: no accessible names, `QShortcut`s, mnemonics or tab order
  anywhere in `poriscope/`; sidebar colours hardcoded (`icon_menu_widget.py:72-80`,
  `text_menu_widget.py:79-86`); Windows-only fonts hardcoded 7 times.

### Analysis tabs

- **`new_plugin.py` cannot generate a `MetaSubsetTab*` tab**, the likely shape of any
  new database-analysis tab; add `--base subset`.

### Database

- **34 hand-rolled `sqlite3.connect`/`finally` blocks** across the four SQLite plugins,
  and `lookahead_generator` nested twice (`MetaWriter:362`, `MetaDatabaseWriter:121`) in two
  near-copy write loops.

### Plugin contract

- **`_validate_param_ranges:559` rejects any `None`**, so a plugin cannot declare an
  optional parameter.
- **A trivial reader implements 15 abstract methods**, 29 of the shipped bodies `pass`;
  default implementations for the lifecycle no-ops would cut that to about 8.

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
