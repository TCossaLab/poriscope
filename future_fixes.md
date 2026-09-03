# Future Fixes

Queued work and standing policy for the Poriscope codebase.

**Only future-facing work belongs here.** When something lands, delete its entry rather
than annotating it as done - the narrative belongs in `changelog.md`. When something is
settled as deliberately not worth doing, move the reasoning to `DECISIONS.md` and delete
the entry. Keep a sentence of finished-work context only where an item still open cannot
be understood without it.

## Structural audit findings (2026-08-25)

A read of the app shell, plugin contract and threading layer - the paths every analysis
tab traverses. Full write-up with per-finding reasoning:
<https://claude.ai/code/artifact/a1bec2cd-a157-4299-acb3-a135738fee41>

Everything here is a logic change, so it needs an approved plan first. The common thread:
the app's main control path is a method name passed as a string and resolved with
`getattr`, which none of the four pre-commit gates can see. None of it blocks "What to
pick up next".

### High - working today, but for reasons nothing records or tests

- **Emit-then-read-an-attribute, in the analysis-tab View layer.** The pattern - emit
  `global_signal`/`data_plugin_controller_signal` with a `return_function_name` callback,
  then read the result off an attribute on the very next statement, trusting the callback
  already ran - was fixed at the two sites the audit counted, but recurs roughly a dozen
  more times in the Views, uncounted:
  `RawDataView._apply_filter` (`RawDataView.py:1416-1443`); `MetadataView.py:2021-2030`,
  `:2063-2072`, `:2306-2330`, `:2340-2348`, `:1411-1445`, `:1472-1490`; `ProteinView.py:1583-1592`,
  `:1770-1779`, `:1872-1881`, `:421`; `ClusteringView.py:286-295`, `:579-601`;
  `EventAnalysisView.py:940-964`. **This is deferred deliberately rather than queued**, and
  is not a correctness problem today: the six `.connect()` calls that carry this bus pass
  `type=Qt.ConnectionType.DirectConnection` explicitly
  (`MetaController._connect_global_signal`'s four, `MainController.instantiate_analysis_tab`'s
  two), so the callback is guaranteed to have run before the attribute is read, and a
  future refactor that moves one of these objects onto a `QThread` fails loudly instead of
  silently degrading to a stale read. What is left is structural clarity.
  It also can't be fixed the way the two counted sites were: `MetaController`/`MetaView`
  deliberately hold no reference back to `MainController` (that's what keeps analysis tabs
  pluggable, resolved purely by `(metaclass, subclass_key)` string), and a real
  `Signal.emit()` cannot hand back a return value even over a direct connection - which is
  exactly why this attribute/callback side-channel exists here at all. Restructuring the
  View-layer sites into a genuine synchronous-call abstraction that preserves the
  plugin-decoupling property is a real multi-file refactor touching Views with heavy
  existing test coverage.
- **Routine states still logged at `WARNING`.** Roughly 109 `logger.warning` +
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
- **The plugin loader executes modules before knowing they are plugins.** Left out of the
  2026-08-31 name-collision fix to keep it proportionate: `load_plugin` calls `exec_module`
  on every `.py` file *before* checking whether it holds a plugin at all, so a helper
  module that was never a plugin executes during discovery and reports as a plugin failure
  if it raises (see the log-level item above); and it never registers modules in
  `sys.modules`, so two plugins importing a shared helper by file each get their own copy.
  Worth folding into compliance-gate block 4 below.

### Moderate

- **`@log` costs roughly 291 ns per call above an undecorated method, with logging off.**
  Measured 2026-09-02 over 300,000 calls of a trivial decorated method: 330 ns/call
  against 39 ns/call undecorated, after the lazy-name fix. Almost all of that is the
  wrapper's own call machinery rather than anything a level check can skip, so the only
  remaining lever is not decorating the hottest methods at all - `get_key()`, which runs
  once per dependency-wiring step, and `WaveletFilter._apply_filter`, which runs per data
  chunk, are the two candidates. Profile a real analysis run before removing either;
  291 ns only matters at a call rate nothing has yet demonstrated.
- **`apply_settings` aliases the settings dict it is handed, and session history holds the
  same object.** `BaseDataPlugin.apply_settings`: `self.raw_settings = settings`. Do **not**
  fix this by copying there - measured, the alias is load-bearing. `DictDialog.__init__`
  aliases the dict it is handed and `get_result` returns that same object, so in
  `edit_plugin` `new_settings is app_settings`; `history["settings"]` therefore holds
  `app_settings`, which `MainController.update_plugin_history` files into `plugin_history`
  by reference. `edit_plugin` then swaps plugin-typed `Value`s for live plugin instances,
  and it is `apply_settings` writing the keys back *through the alias* that repairs the dict
  history is holding. Copy there without first fixing that instance-resolution ordering and
  session history is left holding live `QObject`s for `save_session` to serialise. Fix the
  ordering first, then the alias.
- **`save_session` re-serializes the whole history on the GUI thread on every plugin
  change.** Every plugin-history event deep-copies and rewrites the entire session file
  from the GUI thread, whether or not the change touched most of it.
- **The 161 `except Exception` handlers are inconsistent about what they leave behind.**
  `validate_and_instantiate_plugin` alone has six sequential try/except/log/return blocks,
  so a failure leaves the UI partially updated with no indication of which stage failed.
- **Two docs screenshots show a sidebar that no longer exists.**
  `_static/images/sidebar_with_tabs.png` and `_static/images/MainView.png` both still show
  the Exit entry, removed 2026-09-02. Nothing fails - they are images - but they are wrong.
  Needs someone who can drive the UI to retake them.
- **Oversized units, measured.** Five functions exceed 300 lines:
  `metadatacontrols.setupUi` (524), `PeakFinder._classify_folded_unfolded` (446),
  `proteincontrols.setupUi` (439), `_classify_translocation_direction` (391),
  `_locate_sublevel_transitions` (377). `ProteinView.py` is 4,027 lines across 83 methods;
  `MetadataView.py` 3,598 across 70. `MetaDatabaseLoader` declares 21 abstract methods over
  1,344 lines, which is the real implementation burden behind the community-plugin gate
  below. The mechanical win is the `setupUi` methods - straight-line widget construction,
  extractable into per-panel builders without touching behaviour.

## What to pick up next

Two standing constraints reshape the queue below, so read this before working down it in
file order:

- **Another developer owns test-writing.** Do not edit her existing suites; a new test
  file that overlaps no existing suite is acceptable for covering tooling you have just
  built (as `tests/unit/scripts/test_new_plugin.py` does), but **taking on a test suite as
  the piece of work itself is hers**. Blocks 1 and 7 were handed to her on 2026-09-02 and
  are no longer in this queue.
- **Logic changes need a plan the user approves first.** Read-only investigation and
  measurement do not.

1. **Block 5, the scoped CI gate.** `CODEOWNERS` has landed (see block 5); what remains
   here is the CI half. Marking the Docs Render Check
   (`.github/workflows/docs-check.yml`) as a required status check is still outstanding
   and is an admin-only step outside the repo. Block 5's step 2 wants block 1's
   conformance suite, which is now the test developer's. **The schema-check half of that
   step needs nothing built either**, contrary to what this item used to say:
   `tests/unit/plugins/test_plugin_settings_schema.py` already sweeps all 24 plugins and
   `ci-fork-pr.yml` runs `pytest -q` with no marker filter, so every plugin-touching PR
   already runs it in full - a scoped duplicate step would add nothing. Note also that the
   required-review toggle that used to be listed here is **not** outstanding work -
   advisory-only was chosen deliberately.

Then the rest of the Moderate audit tier, the `hist_data` refactor, and the
parked histogram cut-off. The Minor tier is empty - both of its items landed.

**Block 3's analysis-tab half is deferred** until the planned frontend refactoring has
landed, to avoid generating triads against a layout that is about to change.

## Still queued

- **The "owned by another developer" justification for the declined lint rules is now
  partly stale.**
  `docs/source/utils/user_manuals/plugins_manual/development_workflow/quality_control.rst`
  and several `DECISIONS.md` entries decline `B905`, `B904`, `B007`, `S110`, `S112` and
  `S101` on the grounds that every site that still reports "sits in a file owned by
  another developer", so enabling the rule would need a `per-file-ignores` entry that
  hides a real check.
  With `NanoTrees.py` no longer owner-held (its co-author has left the lab; see the
  exclusions section), that is no longer true of every remaining site. The conclusion may
  well survive - `NanoTrees.py` is still a deprecation candidate, which is an independent
  reason not to spend effort there, and `PeakFinder.py`/`Basic_PeakFinder.py` really are
  owner-held - but the *stated reasoning* wants re-checking, and if it changes, so does
  the wording in both places. **This is a bookkeeping task, not licence to re-propose the
  rules**; read the `DECISIONS.md` entry first.
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
- **`tests/unit/plugins/` has no `conftest.py`, so its widget tests leak real windows.**
  Observed 2026-09-02 on Windows during a routine `tests/unit/{controllers,models,plugins,utils}`
  run: dialogs and console windows flash on screen throughout, and a `StepDialog` from
  `plugins/analysistabs/utils/walkthrough.py` built with the walkthrough tests' placeholder
  steps ("Title"/"Msg") outlived the run as a ghost window. Nothing sets
  `QT_QPA_PLATFORM=offscreen` locally - `pytest.ini` leaves it to CI, where Linux sets it
  alongside `xvfb-run` - so on Windows every test widget is a genuine on-screen window, and
  this tree gets none of the teardown `tests/unit/views/conftest.py::_close_leftover_widgets`
  provides. Cosmetic rather than a correctness problem, and it belongs to whoever owns the
  test suites; mirroring the views conftest is the obvious fix. Setting the offscreen
  platform in `pytest.ini` would silence it globally but should be measured against the full
  suite first, since it can change widget behaviour.
- **`MetaView.lock` is a class attribute shared by every tab view.** `MetaView.py:90`. It
  guards `progress_bars` in `remove_progress_bar` only; the other three accesses
  (`:282`, `:287`, `:325`) are unguarded, so the lock does not actually establish the
  invariant it looks like it establishes.

## Widget ownership left over from the event-filter work

Neither is a crash risk; both are ownership tidiness that had no place in a crash fix.
`DECISIONS.md` records why the filter itself stays on the application.

- **`containerWidget` is still parentless** in both comboboxes (`QDialog(None)`;
  `QWidget(None)` on the Linux branch), so it is owned by nobody and is not destroyed with
  its combobox. Parenting it was in the plan on the grounds that it would stop
  `tests/unit/views/conftest.py::_close_leftover_widgets` sweeping it as a top-level -
  **that rationale was measured and is false**: a parented widget that keeps its window
  flags is still returned by `QApplication.topLevelWidgets()`. What remains is ownership
  tidiness, which is worth doing but is not a crash fix and had no place in one.
- **`BaseLineEdit` still registers one application-wide filter and one `aboutToQuit`
  connection per instance** (3 per controls build). Both are now harmless - its
  `eventFilter` returns `False` directly rather than calling into the base class, and
  nothing in its body touches a C++ member of `self`, so a stale registration is inert.
  Replacing them with a single application-owned watcher would remove the leak outright
  rather than defusing it, but it is a new class and a breaking change to something
  re-exported from `exposed.py`.

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
even when annotating surfaces a real bug. Everything below was found while annotating and
left in place, marked with a narrow `# type: ignore` and a `NOTE:` comment at the site.

The reason differs by file, and as of 1.8.0 they are no longer the same reason. The logic
in `PeakFinder.py` and `Basic_PeakFinder.py` belongs to another developer, who is active -
that exclusion is unchanged. `NanoTrees.py` is excluded because it is a **deprecation
candidate**, not because of ownership: its co-author has left the lab and `CODEOWNERS`
now assigns it to `@shadowk29` along with the rest of `eventfitters/`. Fixing anything in
it is therefore permitted but still not worth the effort while deprecation is on the
table.

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

## Open against the PeakFinder integration

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

- **A log-normal higher component in `PeakFinder.fit_threshold`.** The upper population
  of a real prominence dataset is right-skewed (skew +2.09), and a log-normal beat a
  Gaussian on it by 24% RMS (12.4 vs 16.4) when both were fit to the same data above the
  valley. Peeling the two components apart (landed 2026-08-27) removed the worst symptom
  by stopping the higher component from absorbing the lower population's shoulder, but a
  symmetric Gaussian still cannot represent a skewed population's tail. Deferred because
  it breaks the six-element `params` contract that both the plotting code and all three
  `_classify_*` methods unpack; needs a decision on how a mixed Gaussian/log-normal
  result should be reported. Do **not** revisit Poisson-weighted `curve_fit` alongside
  it without re-reading the changelog entry: measured on the same data, it makes the fit
  worse unless paired with tail trimming, and the pairing is cliff-edged.

## Also queued

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

Blocks 2, 6 and 8, and block 3 for data plugins, are done and their sections are gone;
what is left is **5** (free-standing), **4**, block 3's analysis-tab half, and **1** and
**7**, which are pytest suites and so the test developer's. Block 1 is worth slightly less
than it was: the generated skeleton from `scripts/new_plugin.py` is now the first thing a
conformance suite would run against, and that script's own tests already assert every
family's skeleton instantiates and declares a self-consistent schema.

## 1. Behavioral conformance suite (not just signature compliance)

**Owner: the test developer** - this is a pytest suite. The plan is kept here because
block 5 wants to run it scoped to changed plugin files.

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

## 3. Contribution scaffold: the analysis-tab half

`scripts/new_plugin.py` generates data plugins for all eight families. The analysis-tab
half is not built, and is **deferred until the planned frontend refactoring has landed**
so that triads are not generated against a layout about to change.

A Controller/Model/View triad is 8 abstract methods across three files (`MetaController`
2, `MetaModel` 1, `MetaView` 5) plus the class-name-equals-filename rule and `_init`
assigning `self.view`/`self.model`; nothing else needs registering, which is why a
~100-line triad is a valid runnable tab. `FAMILIES` in the script is shaped so the three
can be added without rework.

Two things to know before starting:

- **The `HelloWorld` example under `docs/source/_static/images/examples/` is stale** and
  would not instantiate today: it implements 4 of `MetaView`'s 5 abstract methods, missing
  `notify_plugin_state_changed`, and imports `from utils.MetaView import MetaView` rather
  than `poriscope.utils.MetaView`. A generator should replace it with something that works.
- **The generator's stub-body policy was measured, not chosen**, and anyone changing what
  it emits should re-run the four probes rather than reason about them: `pass` under a
  non-`None` return is mypy `empty-body`; a copied `:raises X:` above a `pass` body is
  pydoclint DOC502; the same field above a `raise NotImplementedError` is DOC503; and
  raising with no field is DOC501.

## 5. Scoped CI gate for `poriscope/plugins/**` (CODEOWNERS half done)

**Goal.** A plugin-touching PR gets automated checks scoped to just the changed plugin,
and automatically reaches the person who maintains it. The ownership half is done and is
**advisory by design**; the CI half is what remains.

**Ownership: done, and deliberately not a gate.** `.github/CODEOWNERS` exists as of
1.8.0. It routes review requests and nothing more: GitHub's "Require review from Code
Owners" branch protection is switched **off** on every branch on purpose, because
Poriscope accepts plugin contributions through fork PRs and a required-owner-review rule
would put a named individual in front of each one. **Do not read the remaining CI work
below as gated on turning that toggle on, and do not "finish" this block by doing so.**
The reasoning and the single condition that would reopen it - the contributor list growing
past six people - are recorded in `DECISIONS.md` under 2026-09-02; the contributor-facing
version is in
`docs/source/utils/user_manuals/plugins_manual/development_workflow/code_ownership.rst`.

**Why.** `.github/workflows/ci-fork-pr.yml` already exists specifically for
fork-originated PRs (the realistic path for a community contribution) and already runs
strict `pre-commit run --all-files` plus the full `pytest` suite with `contents: read`
fork-safe permissions — this is the right place to add plugin-specific gating rather
than inventing a parallel workflow.

**Implementation plan.**
1. ~~Add a `CODEOWNERS` file mapping each `poriscope/plugins/<category>/` folder to its
   maintainer(s).~~ **Done in 1.8.0**, at `.github/CODEOWNERS` rather than the repo root.
   No separate `poriscope/utils/Meta*` rule was added: `/poriscope/utils/` already
   resolves to the same owner, so the line would be a no-op. Add one if `Meta*` ownership
   ever diverges from the rest of `utils/`.
2. In `ci-fork-pr.yml`, add a step after checkout that computes the changed files
   (`git diff --name-only origin/${{ github.base_ref }}...HEAD`) and, if any match
   `poriscope/plugins/**`, runs the block-2 settings-schema check and block-1
   conformance suite scoped to just those files (e.g.
   `pytest -m conformance -k <derived from changed filenames>`), in addition to the
   existing full `pytest` step — so a plugin-touching PR gets strictly more
   scrutiny than a non-plugin PR, without slowing down every PR with the full
   conformance suite.
3. Mark this new step (and the existing strict `pre-commit` step) as required status
   checks in branch protection for `main`/`develop`. This is about *automated* checks
   only - it does not extend to code-owner review, which stays advisory.

**Gotchas.** `ci-fork-pr.yml`'s permissions are deliberately `contents: read` for fork
safety — don't add anything to this workflow that needs write access (e.g. auto-fix
commits); that's what `ci-internal-pr.yml` is for, and it isn't fork-safe.

**Gated on this block:** `scripts/check_plugin_schemas.py` has no pre-commit hook. One was
deliberately not wired, because it would have blocked commits on the six owner-held
`Basic_PeakFinder` findings before the owning developer had seen them. The test suite covers
the same ground on every branch push in the meantime. **`CODEOWNERS` landing does not
release this**, despite the earlier wording here: the file is advisory and changes nothing
about whether those findings have been acted on. Wire the hook once the owner has ruled on
the six findings.

## 7. Fuzz / malformed-input testing for data readers

**Owner: the test developer** - this is a pytest suite.

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
