# Future Fixes

Queued work and standing policy for the Poriscope codebase. Keep this terse: prune
items as they land rather than leaving completed-work narrative behind. Reasoning about
things deliberately *not* done lives in `DECISIONS.md`; what changed lives in
`changelog.md`.

**The full-codebase type-annotation pass is complete (2026-08-26).** Every function
under `poriscope/` is annotated with no exclusions, `.pydoclint-baseline.txt` is a
zero-byte file, and `mypy.ini` enforces `disallow_untyped_defs`, `check_untyped_defs`
and `strict_equality`. All four pre-commit gates are green. The step-by-step plan, the
batch tables and the retrospective that used to fill this file have been removed now
that they describe finished work; the narrative is in `changelog.md` and the standing
rules that came out of it are in `CLAUDE.md` and `DECISIONS.md`. What remains below is
only what is still open.

## Structural audit findings (2026-08-25)

A read of the app shell, plugin contract and threading layer - the paths every analysis
tab traverses. None of these were already recorded here or in `DECISIONS.md`. Full
write-up with per-finding reasoning:
<https://claude.ai/code/artifact/a1bec2cd-a157-4299-acb3-a135738fee41>

Everything here is a logic change, so it needs an approved plan first. **This section
outranks "What to pick up next" below until it is cleared.** The common thread: the app's
main control path is a method name passed as a string and resolved with `getattr`, which
none of the four pre-commit gates can see.

**All four Critical items are cleared** (2026-08-31): the signal dispatcher's `TypeError`
retries, CI's marker filter, the generator failure reported as success, and the
serial-channel lock granularity. What they had in common is that each failed silently in
the `getattr` blind spot; the narrative is in `changelog.md` and the limitations the last
two left behind are under "Still queued" below.

**High is now cleared too** (2026-08-31), except for one item held open by decision. The
plugin-shadowing and routine-ERROR items both landed; the remaining High entry is the
emit-then-read-an-attribute pattern in the analysis-tab Views, which is **deferred
deliberately** rather than queued: the explicit `Qt.ConnectionType.DirectConnection` on
that bus already makes those reads deterministic, so what is left is structural clarity
and not behaviour. Do not treat it as blocking "What to pick up next" below.

### High - working today, but for reasons nothing records or tests

- **Closed, but undercounted at "two sites" - the real pattern recurred roughly a dozen
  more times.** The `MetaModel.py`/`self.serial_ops` site was already gone (per-plugin-
  locks work). The `DataPluginController.get_settings_from_history`/
  `self.historical_settings` site is now fixed the same way: `DataPluginController`
  takes a `history_lookup` callable at construction (`MainController._lookup_historical_settings`)
  and calls it directly instead of emitting a signal and reading an attribute back -
  correct now by construction, not by an assumption about connection type.
  **What's still open**: the same shape of bug - emit `global_signal`/
  `data_plugin_controller_signal` with a `return_function_name` callback, then read the
  result off an attribute on the very next statement, trusting the callback already ran -
  recurs in the analysis-tab View layer, uncounted by the original audit:
  `RawDataView._apply_filter` (`RawDataView.py:1416-1443`); `MetadataView.py:2021-2030`,
  `:2063-2072`, `:2306-2330`, `:2340-2348`, `:1411-1445`, `:1472-1490`; `ProteinView.py:1583-1592`,
  `:1770-1779`, `:1872-1881`, `:421`; `ClusteringView.py:286-295`, `:579-601`;
  `EventAnalysisView.py:940-964`. These can't be fixed the same way as the
  `DataPluginController` site: `MetaController`/`MetaView` deliberately hold no reference
  back to `MainController` (that's what keeps analysis tabs pluggable, resolved purely by
  `(metaclass, subclass_key)` string), and a real `Signal.emit()` cannot hand back a
  return value even over a direct connection - which is exactly why this attribute/callback
  side-channel exists here at all. As a bounded mitigation (not a fix), the six
  `.connect()` calls that carry this bus now pass
  `type=Qt.ConnectionType.DirectConnection` explicitly
  (`MetaController._connect_global_signal`'s four, `MainController.instantiate_analysis_tab`'s
  two), so a future refactor that moves one of these objects onto a `QThread` fails loudly
  (or at least deterministically synchronously) instead of silently degrading to a stale
  read. Restructuring the View-layer sites into a genuine synchronous-call abstraction that
  preserves the plugin-decoupling property remains open - a real multi-file refactor
  touching Views with heavy existing test coverage.
- **Fixed** (2026-08-31): every `WARNING` and `ERROR` record used to raise a modal
  dialog. `QtHandler` now defaults to `ERROR`, is skipped by
  `MainModel.update_logging_level`'s handler loop (which was the only place its level was
  ever set, and would have silently undone a static floor the first time a user changed
  the log level), carries a `"%(message)s"` formatter instead of the shared log-line one,
  and queues records that arrive while a dialog is up rather than discarding them. See
  `changelog.md`.
  **The ERROR half is also now closed** (2026-08-31): 19 routine conditions logged at
  `ERROR`, and therefore raising a dialog each, were re-levelled or moved to the
  `add_text_to_display` panel - the six parse/empty-input sites in
  `float_range_line_edit.py` and `BaseValidator`'s per-keystroke blanket `except`, two
  per-channel loop notes in `RawDataView`, and nine empty-state guards across the five
  analysis tabs. See `changelog.md`.
  **What's still open** is the `WARNING` half. Roughly 109 `logger.warning` +
  16 `logger.exception` sites under `poriscope/` still record routine states at a level
  that reads as a problem. **None of them interrupts anyone**, since `QtHandler` floors at
  `ERROR`, so this is purely a log-signal and tidiness problem and is deliberately not
  queued as urgent. If it is ever picked up, the families worth working from are:
  - Per-event and per-channel "skipping"/"proceeding without" notes logged at WARNING from
    inside worker generators: `RawDataView.py:853, 869, 881, 1071, 1549`,
    `EventAnalysisView.py:419, 436, 588, 950`, `ProteinView.py:1103, 1152`,
    `RawDataModel.py:101, 109`, `MetaDatabaseWriter.py:178-180`.
  - "No selection"/"select only one" user guidance at WARNING across `MetadataView`,
    `ProteinView`, `RawDataView` and the three controllers' `"No column names received"`.
    These belong on the panel rather than in the log at all, the way the nine ERROR-level
    guards now are.
  - A handful of sites already emit to the panel *and* log at WARNING for the same event
    (`DataPluginController.py:155-161`, `:470-476`; `MetadataView.py:1848-1849`;
    `ProteinView.py:1343-1344`). Those are the model for the intended pattern, and are
    now the only copy the user sees.
  Deliberately staying at `ERROR`, so do not "finish the job" by changing them:
  `main_model.py`'s plugin-import failure (a broken plugin is worth interrupting for, and
  with no pre-import check it is the only signal the user gets), `ClusteringView.py:530`'s
  empty dataframe, and `SQLiteDBLoader.py:605`'s missing `id` column.
- **Fixed** (2026-08-31): a user plugin used to silently replace a built-in of the same
  filename. Discovery walks `poriscope/plugins/` and then the user folder into one flat
  `{subclass_name: class}` map, and both the assignment and the menu-list `append` were
  unconditional, so a user `ClassicBlockageFinder.py` overwrote the shipped one with no
  warning and no way to tell which ran. `populate_available_plugins` now keeps a set of
  plugin names already claimed and logs at ERROR, which is a dialog, for the second and
  any subsequent file claiming a name; the first one found wins, so a built-in can no
  longer be displaced. See `changelog.md`.
  **What's still open** in the same code, deliberately left out of that fix to keep it
  proportionate: `load_plugin` calls `exec_module` on every `.py` file *before* checking
  whether it holds a plugin at all, so a helper module that was never a plugin executes
  during discovery and reports as a plugin failure if it raises (see the log-level item
  above); and it never registers modules in `sys.modules`, so two plugins importing a
  shared helper by file each get their own copy. Worth folding into compliance-gate
  block 4 below.
- **Fixed** (2026-08-31): finished `Worker`/`WorkerThread` objects used to be retained for
  the whole session - `discard_generator` cleared only `thread_running` and `generators`,
  never popping `self.workers[key][channel]`/`self.threads[key][channel]`, so every dead
  `QThread` stayed alive holding its generator closure and the data it touched, and
  `handle_kill_worker`/`stop_workers` logged "Stopping worker for channel N" for runs that
  had finished hours earlier. `discard_generator` now pops both and calls `deleteLater()`
  on each - see `changelog.md`. Verified with a throwaway script, the same way as the two
  fixes immediately below it in this file; `EventWorker.py`/`MetaModel.py` still have no
  real test coverage (see "Still queued").

### Moderate

- **`@log`'s debug gate reads the root logger's exact level.** `LogDecorator.py:106,128`:
  `if logger.root.level == logging.DEBUG`. Testing the root rather than the decorated
  module's effective level makes per-module debug logging impossible, and `==` disables
  argument logging at any level that is not exactly 10 (confirmed at level 5).
  `logger.isEnabledFor(logging.DEBUG)` fixes both. Separately, across 949 decorated
  methods the per-call cost is paid whether logging is on or not - `log_call` builds the
  f-string name before the level is consulted. Build it lazily inside the check, and
  consider dropping the decorator from `get_key()` and `WaveletFilter._apply_filter`,
  which run per dependency-wiring call and per data chunk respectively.
- **`get_raw_settings()` hands out live internal state and callers write to it.**
  `DataPluginController.py:169-185`. On rename, `edit_plugin` mutates each dependent's dict
  directly (`dsettings[metaclass]["Value"] = key`, `Options.remove(...)`) *and* calls
  `update_raw_settings`, which does the same write through the accessor - drop the direct
  one. Worse, `dhistory["settings"] = dsettings` stores a live reference to plugin-internal
  state in session history, so a later mutation retroactively changes what is persisted.
  `BaseDataPlugin.apply_settings:266` compounds it by aliasing rather than copying
  (`self.raw_settings = settings`). Return a copy; make `update_raw_settings` the only
  writer.
- **`save_session` has no error handling, unlike `update_app_config` beside it.**
  `main_model.py:307-316` opens a user-supplied path and calls `json.dump` bare, from a Qt
  slot - and PySide6 does not tolerate an exception escaping a slot invoked from C++, so a
  read-only destination can take the process down. It also re-serializes the whole history
  on the GUI thread on every plugin change. Contrast the 161 `except Exception` handlers
  elsewhere: `validate_and_instantiate_plugin` alone has six sequential
  try/except/log/return blocks, so a failure leaves the UI partially updated with no
  indication of which stage failed.
- **Oversized units, measured.** Five functions exceed 300 lines:
  `metadatacontrols.setupUi` (524), `PeakFinder._classify_folded_unfolded` (446),
  `proteincontrols.setupUi` (439), `_classify_translocation_direction` (391),
  `_locate_sublevel_transitions` (377). `ProteinView.py` is 4,027 lines across 83 methods;
  `MetadataView.py` 3,598 across 70. `MetaDatabaseLoader` declares 21 abstract methods over
  1,344 lines, which is the real implementation burden behind the community-plugin gate
  below. The mechanical win is the `setupUi` methods - straight-line widget construction,
  extractable into per-panel builders without touching behaviour.

### Minor

- **`_validate_param_ranges` raises the exception its docstring rules out.**
  `BaseDataPlugin.py:437-455`. The bound comparisons run before any `None` check, so
  `Value: None` with a `Min` set raises `TypeError: '<' not supported between instances of
  'NoneType' and 'float'` (confirmed) where the docstring promises `ValueError`. The caller
  reports every failure with one generic message, so the user sees a type error instead of
  "Threshold is required". Same method: the `Options` check special-cases the literal names
  `"Output File"` and `"Input File"` - plugin-specific knowledge in the universal validator.
  A `"Validate Options": False` flag in the settings schema expresses it without the base
  class knowing any names.
- **Two dead conditions in the plugin loader.** `main_model.py:190` filters
  `f.endswith(".py") and f not in ("__init__.py", "__pycache__")` - no filename both ends in
  `.py` and equals `__pycache__`, which is a directory `os.walk` yields in the dirs list the
  code ignores, so the clause has never excluded anything. `main_model.py:55`'s
  `_JSON_CLASS_NAMES` maps `"null"` to `None`, but the writer emits `type.__name__`, which
  for `None`'s type is `"NoneType"` - the entry can never match.
- **A missing config key at startup is fatal before logging exists.** `main_app.py:31`
  reads `self.app_config["Log Level"]` by subscript, but the backfill at `:96-104` covers
  only `"User Plugin Folder"`. A hand-edited or older `config.json` therefore dies with a
  `KeyError` before any handler exists to record it. Backfill every key from
  `default_app_config`, or read through `.get()` with a default.

## What to pick up next (order revised 2026-08-25)

The structural audit section above outranks this list until it is cleared. Two standing
constraints also reshape the queue below, so read this before working down it in file
order:

- **Test-writing is owned by another developer.** New pytest suites are out of scope
  here, which pushes compliance-gate blocks 1 and 7 down the queue indefinitely, and
  splits block 2 (its validator module is in scope; its discovery-and-assert harness is
  not). Editing or deleting existing tests as part of a cleanup is fine.
- **Logic changes need a plan the user approves first.** Read-only investigation and
  measurement do not.

**Block 6 (the docs-render CI gate) is done** (2026-08-31), along with the two one-line
items that used to sit at 3, the docs-workflow comment fix, and the `QtHandler`
severity/modality split paired with the abort-feedback bug - see `changelog.md`. What
remains, ranked cheapest real value first:

1. **Block 2's validator half only**: `validate_settings_schema()` as a real module
   under `poriscope/utils/`. Useful from a script or pre-commit hook without the pytest
   harness that is out of scope.
3. **Block 8, custom lint rules for the conventions `CLAUDE.md` only documents.**
   Well-motivated: no-nested-functions, no-bare-except and explicit sqlite cleanup were
   all enforced by hand during the 2026-08-25 lint sweep.
4. **Block 5, the CI gate and `CODEOWNERS`.** There is still no `CODEOWNERS` file, so
   the per-file ownership this project actually operates under is enforced by nothing.
   Note the docs-render gate added in block 6 also wants marking as a required status
   check in branch protection, which is the same out-of-repo admin step block 5 needs.

Then blocks 3 and 4, the `hist_data` refactor, and the parked histogram cut-off.

## Still queued

- **The transitive serial declaration is not fully honoured.** `MetaEventFinder` defers to
  `self.reader.force_serial_channel_operations()` and `MetaEventFitter` to its
  `eventloader`, so a finder declares serial *because its reader is not threadsafe*. The
  per-instance guard locks the finder, which does not protect a reader shared by two
  finders. Latent today: every reader and loader returns `False` and no concrete plugin
  overrides. A future reader returning `True` would not actually be protected. Deliberately
  not solved with dependency-chain lock ordering, which risks deadlock - see the guard's
  docstring.
- **`MetaEventFinder.force_serial_channel_operations` raises `AttributeError` when
  `self.reader is None`.** Now called from inside the generator by the serialization guard
  rather than over the signal bus, so it surfaces at the first advance instead of being
  swallowed by the dispatcher. A finder without a reader raises `AttributeError` from
  `find_events` anyway, two lines later, so this is a change of messenger and not of
  outcome - but it is the guard that speaks first now.
- **Application-wide event filters are installed and never removed**, which is what makes
  `pytest tests/unit` intermittently error at setup. Written up in full below under
  "Handoff: the application-wide event-filter leak" - it is three sites rather than the
  one originally recorded here, and it is owed to whoever picks up the widget layer.
- **Placeholder guards on UI-supplied plugin keys are applied inconsistently.** A scan of
  every `global_signal` emit in the analysis-tab views whose plugin key is a
  UI-supplied parameter found 19 sites with no placeholder check in the emitting method.
  Two were traced and are guarded by their callers (`_apply_filter` behind
  `if data_filter and data_filter != "No Filter"`, `_commit_clusters` behind a deliberate
  user action), which is very likely true of most of the rest - they are private helpers
  reached from action handlers. The three that were *not* guarded anywhere were the
  reactive `update_units` methods, now fixed. Worth auditing the remaining 17 properly
  rather than assuming; the distinction that matters is whether a path is reactive
  (runs on plugin-state change or combobox repopulation, so the placeholder is live) or
  action-driven (the user already chose a real plugin).
- **`EventWorker`/`MetaModel`'s worker lifecycle still has no test coverage.** The
  generator-failure fix and the worker/thread cleanup fix both landed verified only by
  throwaway scripts (generator-failure: happy path, mid-run `TypeError`, abort, empty
  generator; cleanup: two independent runs to completion, each popped from
  `workers`/`threads`/`generators` without affecting the other, `deleteLater()` doesn't
  raise). `test_event_worker.py` does not exist - see `test_mapping_audit.csv` - and
  neither does a test file for `MetaModel.py`; this is the single dispatch loop behind
  every event finder, fitter and writer run. Owed by whoever owns test-writing; the
  scenarios above are the ones worth encoding.
  **`QtHandler.py` and `App.configure_logger` are in the same position** as of
  2026-08-31: the severity/modality work landed verified by two throwaway scripts rather
  than tests, because `test_qt_handler.py` and `test_main_app.py` do not exist either.
  The scenarios those scripts cover, and which are worth encoding, are: the handler's
  default `ERROR` level; DEBUG/INFO/WARNING raising no dialog; one ERROR raising exactly
  one; a burst of four distinct errors arriving behind an open dialog all being shown
  rather than three being dropped; fifty *identical* errors collapsing to one dialog;
  `update_logging_level` lowering every other handler but leaving `QtHandler` at `ERROR`;
  and the dialog body carrying the bare message rather than a formatted log line. Also
  worth encoding on the abort side, likewise script-verified only: `MetaModel.stop_workers`
  logging INFO rather than WARNING for a stale key and no longer being silent for a stale
  channel, and `MainController.handle_abort_all_analysis` reaching every open tab without
  `exiting=True`.
- **A worker blocked on a lock cannot observe an abort.** `Worker.stop()` only sets
  `stop_requested`, which is read on the generator's next turn, so a channel queued behind a
  serial-mode lock keeps waiting until it acquires. Pre-existing and unrelated to the
  granularity fix; per-instance locks shorten the queues but do not change this.
- **`MetaView.lock` is a class attribute shared by every tab view.** `MetaView.py:90`. It
  guards `progress_bars` in `remove_progress_bar` only; the other three accesses
  (`:282`, `:287`, `:325`) are unguarded, so the lock does not actually establish the
  invariant it looks like it establishes.

## Handoff: the application-wide event-filter leak (2026-08-31)

Written up for handoff rather than fixed here. It is a logic change in widgets with real
existing coverage, so it needs its own approved plan, and it is not one site but three.

### The mechanism

`QApplication.instance().installEventFilter(self)` runs unconditionally in the widget's
`__init__`, registering it on the application singleton - whose lifetime is the whole
process. `installEventFilter` stores a raw `QObject*` in the application's filter list, and
Qt drops it only when the filter object goes through the normal `QObject` destructor path.
Under Shiboken the Python wrapper and the C++ object can be torn down in an order, and at a
garbage-collection time, where the application still calls into a half-dead wrapper. The
filter's own body then dereferences `self.containerWidget` - a C++-backed attribute - and
Shiboken refuses to resolve `self`:

```
RuntimeError: Internal C++ object (MultiSelectFilterComboBox) already deleted
```

Two things make it worse than a slow leak. First, `eventFilter` **ignores its `obj`
parameter entirely** - it is accepted and passed straight to `super()`, never inspected - so
the filter runs for every object in the application receiving any event, and N stale filters
cost N Python calls per delivered event. Second, on the branch it does act on it returns
`True`, swallowing the click, so a bug here is not confined to teardown.

**Reproduced on 2026-08-31 while working on an unrelated branch**, and the traceback
refines the above in a way that matters: the failure was

```
poriscope/views/widgets/multiselect_filter.py:135: in eventFilter
    return super().eventFilter(obj, event)
E   RuntimeError: Error calling Python override of QComboBox::eventFilter():
    Internal C++ object (MultiSelectFilterComboBox) already deleted.
```

with `event` a `QDynamicPropertyChangeEvent` - not a `QEvent.MouseButtonPress`. So the crash
is not on the `containerWidget` dereference at all; it is on `super()` resolving a dead
`self` at the fall-through `return`. **Every event type reaching a stale filter can raise
it, not just mouse presses**, which makes the exposure considerably wider than the
`MouseButtonPress` gate suggests and means narrowing the *event* test would not help. Only
removing the registration, or scoping it to an object with the right lifetime, does.

### Three sites, not one

Fixing only the site originally recorded leaves the failure alive via the others.

| Site | Class | Production instantiations |
| --- | --- | --- |
| `views/widgets/multiselect_filter.py:125`, `eventFilter` at `:127-135` | `MultiSelectFilterComboBox` | `metadatacontrols.py:411`, `proteincontrols.py:410` |
| `views/widgets/multiselect.py:124`, `eventFilter` at `:255-262` | `MultiSelectComboBox` | `rawdatacontrols.py:177`, `eventAnalysisControls.py:197` |
| `utils/BaseLineEdit.py:45` | `BaseLineEdit` | 13 construction sites across the controls widgets |

The first two bodies are near-identical - `multiselect.py` calls `self.hidePopup()` where
`multiselect_filter.py` calls `self.containerWidget.close()` - and are already recorded as
~90% duplicates and a merge candidate in `future_refactors_and_features.md:1591-1592`.
`BaseLineEdit` is much less crash-prone, because its `eventFilter` does check `obj`
(`isinstance(obj, QMessageBox)`) and touches no C++ member of `self`, but it leaks at far
the highest rate: ~13 more registrations per controls-widget build. It also connects
`QApplication.instance().aboutToQuit` to a bound method per instance, a second permanent
application-lifetime reference, and mutates the *class*-level `suspend_validation` /
`app_closing` flags, so its instances interfere with each other globally.

`removeEventFilter` appears **zero** times anywhere in the repository.

### A second defect in the same constructor

`multiselect_filter.py:68` does `self.containerWidget = QDialog(None)` - parentless. So the
popup is a top-level widget owned by nobody, it is not destroyed when the combobox is
destroyed, and it is precisely the object `eventFilter` dereferences.
`tests/unit/views/conftest.py::_close_leftover_widgets` walks
`QApplication.topLevelWidgets()` and `close()`/`deleteLater()`s exactly these, which can
kill `containerWidget` while its combobox - or a stale filter pointing at it - is still
registered. **Fixing the filter without also parenting or explicitly deleting
`containerWidget` leaves half the hazard in place.**

### Why it bites the test suite and not the running app

`MainController.instantiate_analysis_tab:527-553` reuses an existing tab of the same
subclass and never removes an entry from `self.analysis_tabs`, so the app constructs at most
one Metadata and one Protein tab per session and never destroys either. The real app
therefore caps at ~2 registrations for these two classes (plus ~13 per controls build from
`BaseLineEdit`), and the `RuntimeError` is effectively unreachable there because nothing
dies. Note the repopulation path mutates the existing combobox (`clear()` + `addItems()`,
e.g. `proteincontrols.py:1044-1052`) rather than constructing a new one, so filters do not
accumulate per repopulate.

The suite is the opposite. Every one of these builds a real widget with no disposal:

- `tests/unit/controllers/test_protein_controller.py` - function-scoped `controller`
  fixture (`:37-47`) constructs a real `ProteinController`, hence a real `ProteinView` ->
  `ProteinControls` -> one real `MultiSelectFilterComboBox`, with **no `yield`, no
  `deleteLater`, no `close`**, across 51 test methods (48 before the
  `feature/saveSessionRefactor` merge added `TestSessionState`). **`tests/unit/controllers/`
  has no `conftest.py` at all**, so none of the view suite's widget-teardown or
  blocking-dialog protections apply.
- `tests/unit/views/test_protein_view.py` - `real_view` fixture (`:79-105`), referenced 92
  times.
- `tests/unit/views/widgets/test_multiselect_filter.py` - ~34 comboboxes, each *correctly*
  disposed in `tearDown` via `deleteLater()` + a drained loop. This is the worst case
  precisely because it does the right thing: it manufactures ~34 **stale** registrations.
- `tests/e2e/metadata/*` and `tests/e2e/protein/*` build real views too.

Order of magnitude for a full `pytest tests/unit`: 150-200+ registrations on one
process-lifetime `QApplication`, an unknown but large fraction of them stale. The reported
victim is a `TestRelayQuery` case in `test_protein_controller.py`, and it is a different
case each run, because the victim is whichever test happens to be constructing a widget
when the interpreter frees an earlier view.

### Measurement

1 failure in 3 runs on `develop` and 3 in 3 on `feature/per-plugin-locks` (2026-08-31). The
per-plugin lock work does not cause it; it very likely shifts allocation and therefore GC
timing, which is enough to change how often a latent lifetime bug surfaces. Re-measured the
same day on `develop` at 646d48f: **2 runs, both green** (2623 passed, 2 skipped, ~167s
each). So absence of a failure is not evidence of a fix - reproduce it before and after by
running the suite repeatedly, not once.

### The pattern a fix should follow

There is in-repo precedent, and it is the opposite of what these three do:

- `plugins/analysistabs/utils/walkthrough.py:181` installs on `parent`, not the
  application, and its `eventFilter` (`:196-210`) **checks `obj`** before acting
  (`if watched == self.parent() and event.type() in {...}`). It needs no removal, because it
  dies with the parent relationship. It is also the only event filter in the codebase with a
  direct test: `tests/unit/plugins/analysistabs/utils/test_walkthrough.py:92-97`, including
  a non-matching-`obj` case.
- `views/help.py:117` is the self-scoped variant (`self.installEventFilter(self)`), also
  `obj`-checking, also tested directly (`tests/unit/views/test_help.py:206-238`).
- Both `multiselect*.py` files carry an abandoned `# self.listWidget.installEventFilter(self)`
  at line 107 - the author knew a narrower target was possible.
- Release Qt objects with `deleteLater()` plus a drained loop, never `destroy()` - see
  `MetaModel.py:194`'s docstring and `tests/unit/views/conftest.py:84-113`, which explains
  why `close()` alone leaks and why `deleteLater()` needs
  `QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` after it.

**Read `DECISIONS.md` first** - the entry on the view-test GC sweep. A prior long-running
segfault was bisected to `test_multiselect_filter.py::TestClearSelectionList` and resolved
by moving from `QWidget.destroy()` to `deleteLater()` + a drained loop. This file already
has one Qt-lifetime crash in its history.

**Do not** wrap `eventFilter` in `try/except RuntimeError`. That hides the symptom while the
filters keep accumulating for the whole session in the real app too.

### Suggested shape, to accept or reject

Scope the filter to `self.containerWidget` (or `self`) instead of the application; check
`obj` before acting; parent `containerWidget` to the combobox; apply the same change to
`multiselect.py` in the same pass, since leaving it makes the intermittent failure persist;
and consider a `tests/unit/controllers/conftest.py` mirroring
`tests/unit/views/conftest.py::_close_leftover_widgets` so those tests stop leaking real
views regardless of what the widgets do. Whether `BaseLineEdit` is folded into the same
change or handled separately is a judgement call - it is the highest-volume leak but has
never been observed to crash.

## Exclusions (standing project policy)

Revised 2026-08-25. These three files are no longer excluded wholesale; the exclusion
now splits by *kind of change*.

- `NanoTrees.py` — likely to be deprecated soon.
- `Basic_PeakFinder.py` / `PeakFinder.py` — owned by another developer.

**Docstring, signature and type-hint changes: in scope.** All three are now fully
annotated and report zero pydoclint violations.

**Logic changes: out of scope, unconditionally.** This holds even when annotating
surfaces a real bug, and several did. Write the honest annotation describing what the
code does today, mark the defect with a narrow `# type: ignore` and a `NOTE:` at the
site, record it under "Defects in the formerly excluded fitter plugins" below, and leave
the fix to the owning developer.

## Defects in the formerly excluded fitter plugins - flagged, never to be fixed here

Policy as of 2026-08-25: `NanoTrees.py`, `PeakFinder.py` and `Basic_PeakFinder.py` are
**in scope for docstring, signature and type-hint work but never for logic changes**,
even when annotating surfaces a real bug. The logic in these files belongs to another
developer. Everything below was found while annotating and left in place, marked with a
narrow `# type: ignore` and a `NOTE:` comment at the site.

- **`find_mode_blockage_level` guards two of its three Optional parameters.** The body
  explicitly handles `data is None` and `baseline_std is None`, then computes
  `abs(data_min - baseline_mean)` with no guard at all on `baseline_mean`, which is
  equally `Optional[float]` under the `MetaEventFitter` contract. A caller with no
  baseline estimate gets a `TypeError`. The asymmetry looks like a simple oversight
  rather than a decision. **Now open only in `Basic_PeakFinder.py`** - `PeakFinder.py`
  has since gained an explicit `if baseline_mean is None: raise RuntimeError(...)`,
  matching its docstring.
- **`PeakFinder.filter_peaks` multiplies by a possibly-`None` `baseline_std`** at three
  adjacent lines (`type0_thresh`/`type1_thresh`/`type2_thresh`). Same root cause.
- **`Basic_PeakFinder._populate_event_metadata` can put `None` into event metadata.**
  It assigns `baseline_mean` and `baseline_std` straight into `event_metadata`, whose
  declared value type is `Union[int, float, str, bool]`. A `None` reaching the database
  writer downstream is not something that contract allows for.
- **`PeakFinder.filter_peaks` treats a sample count as microseconds.** Its only caller
  passes `len(data[padding_before:-padding_after])` as `event_length`, and the body then
  computes `event_length * samplerate * 1e-6` and logs it as
  `f"event_length={event_length:.1f} us"`. Either the argument or the label is wrong.
- **`NanoTrees._DNA` slices with two unguarded `Optional[int]` paddings.**
  `data[:padding_before]` and `data[-padding_after:]` are computed with no `None`
  check, so the negation raises `TypeError` for any event loader that supplies
  neither. The method has no live caller today - the only call site is commented out
  inside `_locate_sublevel_transitions` - which is presumably why it has gone unnoticed.
- **`NanoTrees._locate_sublevel_transitions` overwrites both baseline arguments.**
  Its first two statements recompute `baseline_std` and `baseline_mean` from
  `data[:padding_before]`, discarding whatever the event loader passed in. That may
  well be deliberate, but it means the two parameters are inert and the docstring's
  promise to "handle gracefully the case where any of the arguments except data are
  None" is met by accident rather than by design.
- **Both PeakFinders' `sublevel_starts` really holds dicts, not indices.** Their
  `_locate_sublevel_transitions` returns a list of dicts keyed `"type"` and friends. This
  is now consistent rather than broken - the `MetaEventFitter` contract was widened to
  `List[Any]` to match what it has always actually produced - but it is worth knowing
  that the parameter name still says "starts" while the payload is per-sublevel records.

## Open against the PeakFinder integration (2026-08-26)

Found while merging `feature_Peakfinder_classifier` into the docstring/type work. The
defects below were **authorised for repair** and have been fixed - each carries a
`NOTE (integration):` comment at the site explaining what changed and why, so the owning
developer can see it when she re-branches. What remains open is listed under "Still open"
at the end of this section.

### Fixed during the integration

- **`fit_2_gauss` could never succeed.** Its nested `Gauss` declared four parameters
  (`x, Amplitude, mean, stdev`) but was called with five in both places inside `Gauss_2`,
  so every call raised `TypeError`; the `curve_fit` call is wrapped in a bare
  `except Exception`, which swallowed it and took the `popt is None` path forever. Since
  the return statement unpacks `popt` in two groups of four, four parameters per Gaussian
  is the intended shape, so `Gauss` gained an `offset` term and `Gauss_2`'s parameters
  were renamed from `A/x/m/s` to `A/u/s/c` to say which is which.
- **`find_mode_blockage_level` used `baseline_mean` unguarded.** Now raises `RuntimeError`
  up front. Its `baseline_std` handling was also a `float()` inside a bare
  `except Exception`, which made a legitimately-`None` value indistinguishable from a
  conversion failure; the `None` case now selects the `'auto'` binning path explicitly.
- **`redefine_padding` divided by `2 * baseline_std` with no `None` check.** Now raises.
- **`filter_peaks` scaled every threshold by a possibly-`None` `baseline_std`** at seven
  sites. Guarded once at function entry with a raise.
- **`_populate_event_metadata` passed metadata-dict values straight into
  `find_mode_blockage_level`**, where the base contract's
  `Union[int, float, str, bool]` is wider than the `Optional[float]` accepted. Now
  narrowed with explicit `isinstance` checks that raise on a non-numeric value, and the
  returned primary level is checked for `None` before being stored.
- **A dead `None` test in `_save_classification_report`.** It called
  `float(prominence_stats.get("threshold"))` and only *then* tested
  `threshold is not None` - a test that can never fire, since `float()` either returns a
  float or raises. A missing key therefore raised `TypeError` instead of skipping the
  line. The check now guards the conversion, and the `cast()` it needed is gone.
- **Two `float(bt.get("midpoint"))` calls** on an `Optional` lookup, in
  `_classify_peak_prominences` and `_classify_translocation_direction`. Both now raise.
- **`test_cluster_of_type1_labeled_type3` deleted** as out of date, on instruction: it
  asserted that two nearby type-2 peaks both become type 3, which the current clustering
  logic does not do.

### Closed by decision, not by code

Both settled 2026-08-25; the reasoning is in `DECISIONS.md`. Recorded here only so they
are not re-raised as open work.

- The four `# type: ignore[assignment]` on the deliberate `None` placeholder writes in
  `_populate_event_metadata` **stay**. They are safe and correct; clearing them would mean
  widening a `Meta*` ABC across six fitter plugins.
- The **double-Gaussian consolidation is not being pursued here.** The owning developer is
  rewriting that fitting code from scratch, which supersedes it. `fit_2_gauss`, the dead
  third implementation, has already been deleted.

### Still open

- **`SQLitePeakDBLoader` no longer casts its interpolated SQL values to `int`.** Reviewed
  and **deliberately accepted**: the database is a local file owned by the user running
  the app, so there is no privilege boundary for an injection to cross. Recorded here
  only so the same finding is not re-raised. This also downgrades the `S608` item in the
  bandit proposal below, which described these sites as "worth real scrutiny".
- **Three nested function definitions** remain: `dgfit` inside `bitthresh`, and formerly
  `Gauss`/`Gauss_2` inside the now-deleted `fit_2_gauss`. `CLAUDE.md` forbids nested
  functions but nothing enforces it (that is block 8 below). Annotated in place and left
  nested, on instruction.
- **The histogram low-end cut-off in the classifier plots.** Diagnosed but not fixed, and
  parked pending the double-Gaussian rewrite: the "All Events (incl. outliers)" bar chart
  is binned against edges `bitthresh` computed from a *filtered subset*, and
  `np.histogram` silently discards values outside the given bin range. Which subset wins
  is decided by discrete ratio tests, so the plot's left edge jumps to the 25th percentile
  when the blockage-filter re-run branch fires - which is why the cut-off appears at
  certain threshold settings and not others. Three call sites share the pattern
  (`_classify_folded_unfolded`, `_classify_peak_prominences`,
  `_classify_translocation_direction`). The fix is to build the histogram once from the
  full data and pass it into the fit, rather than letting the fit dictate the plot's bins.

## Also queued - found during the type-annotation pass, not part of it

- **`pydoclint` class-attribute bug - filed upstream, now awaiting a fix.** Reported to
  the maintainer as https://github.com/jsh9/pydoclint/issues/304; jsh9 maintains both
  `pydoclint` and `docstring_parser_fork`. Nothing to do here until a release lands -
  `check-class-attributes` stays `false` in `pyproject.toml` in the meantime. Kept in
  case the report needs restating: the one-line fix is to replace the two hardcoded
  `".. attribute ::"` literals in `rest_attr_parser.py` with
  `re.compile(r"^\.\.\s+attribute\s*::\s*(?P<name>.+)$")`, which accepts both spellings
  so no existing docstring breaks. Reproduction: a class documented with the *correct*
  `.. attribute::` directive plus any `:param:` block reports `DOC601` + `DOC603`;
  adding a space before the `::` makes it pass. Full diagnosis in `DECISIONS.md` under
  the `IntroDialog` entry.

- **Adopt the rest of ruff `bugbear` (B) and `bandit` (S).** Proposed in review on the
  grounds that both run against real code logic and so complement pydoclint's
  docstring/signature checking for catching silent bugs. `B006` and `B020` are **done**
  and are now enforced through `extend-select` in `pyproject.toml`; everything below is
  what is left. Re-measured on `poriscope/` (2026-08-25): **B = 104, S = 54**. `tests/`
  adds 10 more B hits, one of which is a `B023` closure-over-a-loop-variable - a real
  bug class, but test code belongs to another developer.

  | Rule | Hits | Character |
  | --- | --- | --- |
  | `B905` zip-without-explicit-strict | 54 | **Audited and closed 2026-08-25; deliberately not enabled as a gate.** 50 sites were in scope (the other 7 are in owner-held fitter files); 43 zipped sequences that are built together and need nothing. The 4 that mattered are fixed: 3 in `MetadataView` were silently dropping plot features that had no label, and `ClusteringView` no longer mutates `columns`, so its two zips now assert their alignment with `strict=True` rather than depending on truncation to hide the appended `"id"`. `SQLiteDBWriter`'s sublevel transpose was verified equal-length upstream and now says so with `strict=True`. Not enabled because the 54 remaining sites would each need their own `strict=` decision, and at least one - the list-against-generator zip in `MetaDatabaseLoader` CSV export - cannot be proven equal-length in advance. The rule earned its keep as a one-time audit. |
  | `B904` raise-without-from-inside-except | 1 | **Done 2026-08-25; not enabled as a gate.** All 23 in-scope sites now chain with `from e`; the one remaining is in `PeakFinder.py` (owner-held), so enabling the rule would need a `per-file-ignores` entry that hides a real check rather than satisfying it. Worth recording that this was not purely cosmetic: the 12 data-reader sites were discarding the name of the missing file, leaving the user with "at least one of the input raw data files is missing" and no way to tell which. |
  | `B007` unused-loop-control-variable | 3 | **Done 2026-08-25.** 17 of 20 cleared: 13 `dict.items()` loops became `.values()` or plain key iteration, one pointless `enumerate` dropped, and 3 `zip` sites underscore-prefixed rather than restructured so their iteration count is untouched. The 3 remaining are in `PeakFinder.py`. |
  | `B010` set-attr-with-constant | 2 | both in `LogDecorator.py`; cosmetic |
  | `B028` no-explicit-stacklevel | 1 | one `warnings.warn` in `MetaWriter.py`; cosmetic |
  | `S608` hardcoded-sql-expression | 25 | **downgraded.** The database is a local file owned by the user running the app, so there is no privilege boundary for an injection to cross. Settled - see the `SQLitePeakDBLoader` note above. |
  | `S110` try-except-pass | 13 | **Triaged 2026-08-25; all 13 remaining are in `PeakFinder.py`.** The 6 that were in our own code are fixed: two `set.remove()` handlers became `set.discard()`, one settings-value type test narrowed to `except AttributeError`, and three cosmetic `tight_layout` handlers now log at debug. Enabling the rule would need either the owner to fix hers or a `per-file-ignores` entry for `PeakFinder.py` - the latter hides a real check rather than satisfying it, so it is not proposed. |
  | `S101` assert | 7 | **Done 2026-08-25.** The one site in non-owner code, `ClassicBlockageFinder._filter_events`, now raises `RuntimeError` rather than asserting - asserts vanish under `python -O`, which would have left an opaque `AttributeError` instead. The 7 remaining are all in `NanoTrees.py`, owner-held and a deprecation candidate. |
  | `S112` try-except-continue | 1 | the single site is in `PeakFinder.py` (`_classify_folded_unfolded`, a bare `continue` on an array index); see the `S110` row. |

  Almost every remaining fix is a logic change, so this is unclaimed rather than
  blocked. **This block is now essentially finished.** `B905`, `S110`, `S112`, `B904`,
  `S101` and `B007` are all closed (see their rows above): what each surfaced in our own
  code is fixed, and every site that remains sits in an owner-held file - which is also
  why none of them is enabled as a gate. What is left is `S608` (25, accepted: the
  database is a local file owned by the user running the app) and 3 cosmetic
  `B010`/`B028` sites. There is no further bug-finding value in this block; treat it as
  done unless the owner-held files change hands.

  Note this overlaps, but is not the same as, the bandit proposal in the
  community-plugin block below: that one is scoped to `poriscope/plugins/` as a trust
  boundary for unvetted contributions, this one is codebase-wide as a bug-catcher.

- **`hist_data` holds three shapes.** In both `MetadataView` and `ProteinView` it
  receives 1-D arrays from the histogram path, whole DataFrames from the density path,
  and `(x, y)` tuples from the all-points path. Widened to `List[Any]` with a comment;
  unifying it is a real refactor.

---

# Future Fix: Community-Contributed-Plugin Compliance Gate

The context blocks below were designed together, as a set: the goal is a pipeline that
lets a community-contributed data plugin (or, occasionally, a frontend analysis-tab
plugin family) be verified as safe and correct to merge with a bounded amount of human
review, instead of relying entirely on a reviewer reading the diff. Each block below is
independently actionable and can be picked up in its own future session.

**The set's original order no longer applies.** It was 1 → 2 (cheap, static, highest
signal) → 3 (makes 1/2 easy to satisfy from the start) → 4/5 (merge-gating
infrastructure) → 6/7/8 (rounding out coverage). That sequence assumed blocks 1 and 2
could be built first, and both are pytest suites, which are owned by another developer
and therefore out of scope here. Blocks **6, 8 and 5** are the ones that stand alone
with nothing built before them, and they are the order given at the top of this file.
**Block 6 is now done** (2026-08-31), leaving 8 then 5.
Note in particular that block 3 exists largely to make blocks 1 and 2 easy to satisfy
from a blank file, so building 3 while they do not exist loses most of its value.

## 1. Behavioral conformance suite (not just signature compliance)

**Goal.** A test suite that instantiates every discovered plugin and actually runs its
core method(s) against small synthetic data, asserting it behaves like a well-formed
member of its `Meta*` family — not just that it has the right method names.

**Why.** `tests/unit/plugins/test_plugin_compliance.py` already does the hard part of
discovery: it walks `poriscope.plugins` with `pkgutil.walk_packages`, imports every
module, and (via `BASE_CLASS_DATA`) knows which concrete classes implement which
`Meta*` base. But it only checks `__abstractmethods__`/type-hint compliance — it never
calls the plugin. A community-contributed plugin can satisfy every signature check and
still crash immediately on real data, leak resources, or silently produce garbage.

**Implementation plan.**
1. Add `tests/unit/plugins/test_plugin_conformance.py`, structured like
   `test_plugin_compliance.py` (reuse its discovery loop and `META_CLASSES` set) but
   parametrized over *concrete* plugin classes rather than base classes.
2. For each `Meta*` family, define one canonical synthetic fixture already present
   under `tests/synthetic_data/` (`synthetic_chimera.py`/`multichannel_chimera.py` for
   readers, `synthetic_events_db.py` for db loaders/writers, `synthetic_metadata_db.py`
   for metadata-consuming plugins) and a minimal valid `settings` dict built from each
   plugin's own `get_empty_settings()` (fill required `Value`s with the midpoint of
   `Min`/`Max` or the first `Options` entry — this doubles as a smoke test that
   `get_empty_settings()` itself returns a self-consistent schema, see block 2 below).
3. Write one generic conformance check per `Meta*` family (not per plugin) that:
   - instantiates the plugin with the synthetic settings dict,
   - drives it through its family's real lifecycle (e.g. for `MetaEventFinder`: find
     events on a synthetic trace and assert the returned event boundaries are
     monotonic, in-bounds, and non-overlapping; for `MetaReader`: `load_data` on a
     synthetic channel and assert dtype/shape match `get_raw_dtype()`/declared
     channel count; for `MetaEventFitter`: fit a synthetic event and assert
     `_populate_event_metadata`'s return dict has the keys the base class documents),
   - calls `close_resources()` afterward and asserts no exception and no dangling
     open file handles/db connections (e.g. via `psutil.Process().open_files()` diffed
     before/after, if `psutil` is already a dependency, otherwise skip this specific
     assertion rather than adding a new dependency just for it).
4. Register this as its own pytest marker (e.g. `conformance`) so it can be run
   standalone in CI for exactly the plugin file(s) that changed in a PR (see block 5).

**Gotchas.** This will only be as strong as the synthetic fixtures are representative —
keep the fixtures' parameters (trace length, noise level, event count) realistic enough
that a finder/fitter can't trivially pass by doing nothing. Don't try to make one
mega-fixture cover every family; a small dedicated fixture per family, reused across
all plugins in that family, is easier to reason about and keeps failures attributable
to the plugin under test rather than the fixture.

**Verification.** Run against every *existing* in-repo plugin first (they should all
pass, since they're already trusted) before treating a conformance failure on a new
contribution as meaningful signal.

## 2. Settings-schema linter for `get_empty_settings()`

**Goal.** A static (no I/O, no instantiation-with-real-data-required) check that a
plugin's declared settings schema is internally self-consistent.

**Why.** `BaseDataPlugin.get_empty_settings()` (see `poriscope/utils/BaseDataPlugin.py`)
returns `Dict[str, Dict[str, Any]]` entries shaped `{"Type", "Value", "Options", "Min",
"Max"}`, and `_validate_param_types`/`_validate_param_ranges` check a *supplied*
settings dict against this schema at runtime, per-instantiation. Nothing currently
checks the schema itself for self-consistency independent of any particular value
supplied — e.g. `Min > Max`, a `Value`/`Options` list mixing incompatible `Type`s, or a
`Type` that doesn't match the Python type of `Value`. These are exactly the kind of
copy-paste mistake a first-time contributor adapting an existing plugin would make.

**Implementation plan.**
1. Add a small pure-Python validator, e.g.
   `poriscope/utils/settings_schema.py::validate_settings_schema(schema: dict) -> list[str]`
   returning a list of human-readable problems (empty list = clean), checking per
   parameter entry: `Type` and `Value` keys are present; if `Value is not None`,
   `isinstance(Value, Type)`; if both `Min` and `Max` are set, `Min <= Max`; if
   `Options` is set, every option's type matches `Type` and (if `Value is not None`)
   `Value in Options`.
2. Add a fast, no-fixture-needed pytest test (can live in `test_plugin_compliance.py`
   itself, right next to the existing structural checks, or as a new
   `test_settings_schema.py`) that calls `plugin_cls().get_empty_settings()` for every
   discovered concrete plugin class and runs it through `validate_settings_schema`,
   asserting an empty problem list. (Most plugins' `get_empty_settings()` should be
   callable without a fully-populated `settings` dict — confirm this holds for all
   existing plugins first; a few may need `standalone=True` passed.)
3. This is cheap enough to run as a blocking pre-commit/CI check on every PR touching
   `poriscope/plugins/**`, well before the more expensive conformance suite in block 1.

**Gotchas.** `Options`/`Min`/`Max` are explicitly optional (can be `None`) per the
existing docstring — don't require them, only check consistency *when present*.

## 3. Contribution scaffold / template generator

**Goal.** Shift compliance left: a new plugin should start out already satisfying
pydoclint, mypy, `test_plugin_compliance.py`, and (once built) blocks 1 and 2 above,
rather than a contributor discovering violations only after opening a PR.

**Why.** Every plugin family's abstract method list, docstring style (sphinx-style,
per `[tool.pydoclint] style = "sphinx"`), and settings-schema shape is already fully
determined by its `Meta*` base — there's no reason a contributor should hand-write
this from a blank file when it can be generated correctly the first time.

**Implementation plan.**
1. Add `scripts/new_plugin.py`, invoked like
   `python scripts/new_plugin.py --family MetaEventFinder --name MyEventFinder`.
2. For the given `--family`, use `inspect` on the corresponding `Meta*` class (same
   introspection `test_plugin_compliance.py` already does via
   `get_required_methods`/`__abstractmethods__`) to generate a stub subclass in the
   right `poriscope/plugins/<category>/` folder, with:
   - one method stub per abstract method, each with a sphinx-style docstring skeleton
     whose `:param:`/`:return:`/`:rtype:` entries are pre-filled from the base method's
     own signature and docstring (so pydoclint passes on the stub immediately),
   - a `get_empty_settings()` stub returning one example parameter entry with a comment
     showing the full `{"Type", "Value", "Options", "Min", "Max"}` shape,
   - a matching `tests/unit/plugins/<category>/test_my_event_finder.py` stub that
     imports the new class (so `test_plugin_compliance.py`'s discovery picks it up
     immediately) and includes a placeholder for the block-1 conformance test.
3. Document the script in `CLAUDE.md` under "Where to add a new plugin" as the
   recommended starting point (the existing prose there, pointing at "an existing tab
   (e.g. `Protein*`) as a template," is a weaker substitute for a scaffold that's
   guaranteed to already pass every check).

**Gotchas.** Keep the generated stub minimal (raise `NotImplementedError` in method
bodies) — the goal is a compliant skeleton, not a working plugin; don't try to
generate real algorithmic logic.

## 4. Static security review for module-level plugin code

**Goal.** Reduce the trust risk inherent in blindly executing arbitrary community-
submitted `.py` files inside a desktop app running with the user's full privileges.

**Why.** Per `MainModel.populate_available_plugins()`'s documented behavior, plugin
discovery imports *every* `.py` file found under `poriscope/plugins/` (and the user
plugin folder) — and Python import always executes module-level code unconditionally,
before any of `test_plugin_compliance.py`'s reflection even runs. For in-house
contributors this is an accepted, low-risk convenience; for unvetted community
submissions landing in the same discovery path, it's a real code-execution trust
boundary that none of the current tooling (ruff/mypy/pydoclint) is designed to police.

**Implementation plan.**
1. Add `bandit` to `requirements-dev.txt` and run it as a `pre-commit` `repo: local`
   hook scoped to `files: ^poriscope/plugins/` (mirroring how the pydoclint hook is
   already scoped), using a conservative rule subset first (e.g. flag
   `subprocess`/`eval`/`exec`/`pickle.load`/dynamic `importlib` calls, network access,
   and filesystem writes outside of an expected data directory) to avoid a noisy
   first run.
2. Additionally add a narrow, purpose-built AST check (simpler and more targeted than
   general-purpose `bandit` rules) that flags any *module-level* statement in a plugin
   file other than imports, constants, and class/function definitions — since a
   compliant plugin should never need top-level side effects, and "module-level code
   that does something when merely imported" is the single highest-risk pattern for
   this specific discovery mechanism.
3. Triage findings as blocking (network/subprocess/eval/exec) vs. advisory (everything
   else) — don't try to make `bandit`'s full default rule set blocking on day one, or
   it will generate enough noise to undermine trust in the check.

**Gotchas.** This is a deliberately narrow first pass, not a sandbox — it raises the
bar for a careless or lazy submission but is not a defense against a determined
adversary (a plugin can still do plenty of damage inside a legitimate-looking method
body that only runs once instantiated). True sandboxing (subprocess isolation,
restricted execution) is a much larger architectural change and is explicitly out of
scope here; if that level of isolation is ever wanted, treat it as a separate,
much larger design discussion, not an incremental addition to this one.

## 5. Required, scoped CI gate + CODEOWNERS for `poriscope/plugins/**`

**Goal.** No plugin file merges without both automated checks (scoped to just the
changed plugin) and a human sign-off — formalizing, for everyone, the informal
per-plugin "ownership" that already exists for a few plugins today.

**Why.** `.github/workflows/ci-fork-pr.yml` already exists specifically for
fork-originated PRs (the realistic path for a community contribution) and already runs
strict `pre-commit run --all-files` plus the full `pytest` suite with `contents: read`
fork-safe permissions — this is the right place to add plugin-specific gating rather
than inventing a parallel workflow. There is currently no `CODEOWNERS` file in the
repo, so plugin review isn't enforced by GitHub at all today.

**Implementation plan.**
1. Add a `CODEOWNERS` file at the repo root mapping each
   `poriscope/plugins/<category>/` folder (and, once it exists, `poriscope/utils/Meta*`)
   to the relevant maintainer(s)/owner(s) — this only takes effect as a *required*
   review gate once "Require review from Code Owners" is turned on for the target
   branch's protection rule in repo Settings (an out-of-repo, admin-only config step;
   note it explicitly here so it isn't forgotten as "already handled" just because the
   file exists).
2. In `ci-fork-pr.yml`, add a step after checkout that computes the changed files
   (`git diff --name-only origin/${{ github.base_ref }}...HEAD`) and, if any match
   `poriscope/plugins/**`, runs the block-2 settings-schema check and block-1
   conformance suite scoped to just those files (e.g.
   `pytest -m conformance -k <derived from changed filenames>`), in addition to the
   existing full `pytest` step — so a plugin-touching PR gets strictly more
   scrutiny than a non-plugin PR, without slowing down every PR with the full
   conformance suite.
3. Mark this new step (and the existing strict `pre-commit` step) as required status
   checks in branch protection for `main`/`develop`.

**Gotchas.** `ci-fork-pr.yml`'s permissions are deliberately `contents: read` for fork
safety — don't add anything to this workflow that needs write access (e.g. auto-fix
commits); that's what `ci-internal-pr.yml` is for, and it isn't fork-safe.

## 6. Docs-render check in CI (Sphinx warnings-as-errors) - DONE 2026-08-31

Landed as `.github/workflows/docs-check.yml`, running the autodoc generator plus
`sphinx-build -W --keep-going` on every pull request targeting `main`, `develop` or
`release/*`, with the same flags added to the deploy workflow and the local `post-merge`
hook. Full narrative in `changelog.md`.

Two notes worth keeping. The block's Gotcha - "expect an initial cleanup pass, grandfather
via a suppression list if the initial warning count is large" - **did not apply**: the
count was 18, in five causes, twelve of them from a single bug in
`plugins_generate_autodoc.py`, so all were fixed outright and no baseline was built. And
`nitpicky` was measured at 1170 warnings (1152 `reference target not found` for
numpy/pandas/matplotlib types missing from the intersphinx inventories) and deliberately
left off; enabling it needs an extended inventory map plus a `nitpick_ignore_regex` and is
its own piece of work.

The remaining follow-through belongs to block 5: marking the new check as a required
status check in branch protection for `main`/`develop` is an out-of-repo, admin-only step.

## 7. Fuzz / malformed-input testing for data readers

**Goal.** Catch unhandled crashes in community-contributed parsers on truncated,
corrupted, or otherwise malformed binary input — the single most likely crash surface
for a new `MetaReader` subclass, since readers parse arbitrary externally-produced
files by nature.

**Why.** None of the current checks (compliance, conformance from block 1, pydoclint,
mypy) exercise a reader against anything but a well-formed synthetic file. A community-
contributed reader for a new hardware/file format is exactly the plugin family most
likely to choke on a real-world file that's merely slightly off-spec (truncated
mid-record, wrong header magic, unexpected byte order) — the app should degrade
gracefully (raise a clear, caught exception) rather than crash or hang.

**Implementation plan.**
1. Add `tests/unit/plugins/datareaders/test_reader_fuzz.py`, parametrized over every
   concrete `MetaReader` subclass discovered the same way `test_plugin_compliance.py`
   does.
2. For each reader, take its family's existing valid synthetic fixture (e.g.
   `synthetic_chimera.py`'s output for `ChimeraReader*`) and generate a small, fixed
   set of deterministic mutations rather than open-ended random fuzzing (truncate to
   several byte offsets, flip the header's magic bytes, zero out a middle section) —
   deterministic mutations keep the test reproducible and avoid flaky CI, which
   open-ended `hypothesis`-style fuzzing would risk here.
3. Assert only that each mutation results in either a clean successful read (if the
   mutation happened to still be valid) or a caught, well-typed exception — never an
   unhandled crash, hang, or silent data corruption (e.g. returning a truncated array
   without signaling the truncation).
4. This test is necessarily reader-format-specific for the mutation *generation* step
   (each format's header/magic bytes differ), but the assertion logic and discovery
   loop should be shared/generic — write one small per-format "corrupt this fixture"
   helper per reader family, not per individual reader.

**Gotchas.** This only meaningfully applies to `MetaReader`; don't try to generalize it
to every plugin family — event finders/fitters/filters operate on already-validated
in-memory arrays, not raw external files, so this specific risk doesn't apply to them.

## 8. Custom lint rules encoding existing tribal knowledge

**Goal.** Make the project's already-established-but-only-documented-in-CLAUDE.md/
memory conventions mechanically enforced, so they don't depend on a human reviewer
remembering to check for them on every plugin PR.

**Why.** Several patterns are currently enforced only by convention and review
attentiveness: no nested function definitions, no bare `except:` (narrow to
`except Exception:` at minimum so a `Raises` docstring section is even possible), and
explicit `finally`-block cleanup of sqlite3 cursors/connections. These are exactly the
kind of thing a first-time community contributor won't know to do unless a machine
tells them.

**Implementation plan.**
1. No nested functions: a straightforward `ast`-based check (walk each `FunctionDef`
   node's body for a nested `FunctionDef`/`AsyncFunctionDef`) — add as a `ruff`
   custom rule if ruff's plugin API supports it cleanly for this project's ruff
   version, otherwise a small standalone script run as a `pre-commit` `repo: local`
   hook (same pattern as the pydoclint hook), scoped to `files: ^poriscope/`.
2. Bare `except:`: `ruff` already has a built-in rule for this
   (`E722`/`BLE001`-family, depending on ruleset naming in the installed ruff
   version) — check whether it's already enabled in this project's `pyproject.toml`
   ruff config before writing a custom check; if not, this is a one-line config
   addition, not new code.
3. Explicit sqlite3 resource cleanup in a `finally` block: harder to express as a
   generic AST rule (requires tracking whether a `sqlite3.connect`/`.cursor()` call's
   result is closed on every exit path) — likely not worth a fully general static
   checker; instead, cover this via the block-1 conformance suite's open-file-handle
   check for `MetaDatabaseLoader`/`MetaDatabaseWriter`/`MetaWriter` plugins
   specifically, which catches the same defect empirically rather than syntactically.
4. Document whichever of these become real automated checks in `CLAUDE.md`'s
   "General Instructions" section, replacing the current prose-only statement of the
   rule with a note that it's now enforced by `<tool>`.

**Gotchas.** Don't over-invest in generalized static analysis for the sqlite3-cleanup
rule specifically — it's a narrow, semantic (not syntactic) pattern where a runtime
conformance check is a better cost/benefit trade than a bespoke AST checker.
