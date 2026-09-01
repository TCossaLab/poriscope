# Future Fixes

Queued work and standing policy for the Poriscope codebase. Keep this terse: prune
items as they land rather than leaving completed-work narrative behind. Reasoning about
things deliberately *not* done lives in `DECISIONS.md`; what changed lives in
`changelog.md`.

The full-codebase type-annotation pass is complete (2026-08-26) and its narrative has been
pruned from this file; see `changelog.md` for what was done and `CLAUDE.md` for the
standing rules it left behind. What remains below is only what is still open.

## Structural audit findings (2026-08-25)

A read of the app shell, plugin contract and threading layer - the paths every analysis
tab traverses. Full write-up with per-finding reasoning:
<https://claude.ai/code/artifact/a1bec2cd-a157-4299-acb3-a135738fee41>

Everything here is a logic change, so it needs an approved plan first. The common thread:
the app's main control path is a method name passed as a string and resolved with
`getattr`, which none of the four pre-commit gates can see.

**All four Critical items landed over 2026-08-25/31**, as did three of the four High ones -
the narrative is in `changelog.md`. What survives below is the open remainder of the High
tier (the fourth item, deferred by decision, plus the parts of two landed ones that were
deliberately left out of them) and the untouched Moderate and Minor tiers. None of it
blocks "What to pick up next".

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

- ~~**`_validate_param_ranges` raises the exception its docstring rules out**, plus the
  missing-`Value` `KeyError` and the `Folder` carve-out.~~ **Closed 2026-09-01.** Three of
  the four defects were fixed (see `changelog.md`); the fourth - that the `Options`
  carve-out is three literal parameter names in a universal validator - is **settled as
  won't-fix**, and the `"Validate Options": False` flag this entry used to propose is
  rejected rather than deferred. See `DECISIONS.md`, which also records the better design
  should it ever be needed and the one thing that would justify it: someone needing a
  plugin with more than one file input.
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

## What to pick up next (order revised 2026-09-01)

Two standing constraints reshape the queue below, so read this before working down it in
file order:

- **Another developer owns the existing test suites - do not edit them.** This is about
  avoiding conflicts in her files, **not** a ban on writing tests. A new test file that
  overlaps no existing suite is in scope and should be written rather than deferred; check
  the overlap first. **Corrected 2026-09-01**, having previously read as "new pytest suites
  are out of scope here", which is what wrongly pushed compliance-gate blocks 1, 2 and 7
  down the queue. Block 2 was completed in full under the corrected reading; **blocks 1 and
  7 are worth re-examining against it** rather than left parked.
- **Logic changes need a plan the user approves first.** Read-only investigation and
  measurement do not.

1. **Block 5, the CI gate and `CODEOWNERS`.** There is still no `CODEOWNERS` file, so
   the per-file ownership this project actually operates under is enforced by nothing.
   Note the docs-render gate (block 6, landed 2026-08-31) also wants marking as a required
   status check in branch protection, which is the same out-of-repo admin step block 5
   needs.
2. **Blocks 1 and 7**, re-scoped against the corrected constraint above - both are pytest
   suites that were parked only because of the old reading. Block 1 (behavioural
   conformance) is the larger and the more valuable; block 7 (reader fuzzing) is narrow.
   Neither would touch an existing test file.

Then block 4, block 3's remaining analysis-tab half, the `hist_data` refactor, and the
parked histogram cut-off.

**Blocks 2 and 8 are closed as of 2026-09-01**, and **block 3 is closed for data plugins**
the same day, leaving only its analysis-tab half. See their sections below for what was
done and the evidence.

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
- **Fixed** (2026-09-01): application-wide event filters installed and never removed, which
  was what made `pytest tests/unit` intermittently error at setup. See `changelog.md`, and
  "Left behind by the event-filter fix" below for the three small things deliberately not
  bundled into it.
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

## Left behind by the event-filter fix (2026-09-01)

The application-wide event-filter leak is **fixed** - see `changelog.md` for what changed and
`DECISIONS.md` for why the filter stays on the application rather than being scoped to the
popup. The handoff write-up that used to sit here has been removed with it. Three small
things were deliberately left:

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
- ~~**`_handle_internal_edit` nests a function.**~~ **Closed 2026-09-01, not a defect.**
  `open_dialog_then_reopen` is a three-line closure that captures `name` so it can be
  handed to `QTimer.singleShot`, which is exactly the case the revised `CLAUDE.md`
  convention now permits. Hoisting it to a method plus `functools.partial` was considered
  and rejected as strictly more code for no gain. It is covered by
  `test_edit_filter_callback_called`, which passes.

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
defects that were authorised for repair have all been fixed - each carries a
`NOTE (integration):` comment at the site explaining what changed and why, so the owning
developer can see it when she re-branches; the list is in `changelog.md`. Two questions
were closed by decision rather than by code (the four `None`-placeholder `type: ignore`s,
and not consolidating the double-Gaussian fits) and are recorded in `DECISIONS.md`. What
is still open:

- ~~**Three nested function definitions.**~~ **Closed 2026-09-01**, by the convention
  changing rather than the code: `CLAUDE.md` no longer prohibits nesting outright, so
  `dgfit` inside `bitthresh` is not a violation to be carried. Nothing to do.
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

- **Adopting the rest of ruff `bugbear` (B) and `bandit` (S) is closed.** `B006`/`B020`
  are enforced through `extend-select` in `pyproject.toml`; `B905`, `B904`, `B007`,
  `S110`, `S112` and `S101` were each run as a one-time audit, their findings in our own
  code fixed, and then left unselected. The reasoning for not enabling them - every
  remaining site sits in an owner-held file, so a gate would need a `per-file-ignores`
  entry that hides a real check - is in `DECISIONS.md`, as is the acceptance of the 25
  `S608` sites. What each audit surfaced is in `changelog.md`.

  **All that is left open is 3 cosmetic sites**: 2 `B010` in `LogDecorator.py` and 1
  `B028` (`warnings.warn` without `stacklevel`) in `MetaWriter.py`. There is no further
  bug-finding value here; treat the block as done unless the owner-held files change hands.

  Note this is *not* the same as the bandit proposal in the community-plugin block below:
  that one is scoped to `poriscope/plugins/` as a trust boundary for unvetted
  contributions, this one was codebase-wide as a bug-catcher.

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

**The set's original order was 1 → 2** (cheap, static, highest signal) **→ 3** (makes 1/2
easy to satisfy from the start) **→ 4/5** (merge-gating infrastructure) **→ 6/7/8**
(rounding out coverage). Three blocks are now closed and the rest largely follow that
order again:

- **Block 6 landed 2026-08-31** as `.github/workflows/docs-check.yml`. Its one piece of
  follow-through - marking the check as required in branch protection - is folded into
  block 5.
- **Block 8 closed 2026-09-01** without needing to be built; see its section.
- **Block 2 landed 2026-09-01**, in full rather than the validator half. It had been split
  on the reading that its pytest harness was out of scope, which was wrong - see the
  corrected constraint at the top of this file.
- **Block 3 landed 2026-09-01 for data plugins**, as `scripts/new_plugin.py`. Only its
  analysis-tab half is left, and that is recorded in its own section rather than here.

That leaves **5** (free-standing), then **1** and **7**, which are pytest suites that were
parked only under the old reading of that constraint and should now be re-scoped. Block 1
is worth slightly less than it was: the generated skeleton is now the thing a conformance
suite would be run against first, and block 3's tests already assert that every family's
skeleton instantiates and declares a self-consistent schema.

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

## 2. Settings-schema linter for `get_empty_settings()` - DONE 2026-09-01

Landed in full, not just the validator half; narrative and measurements in `changelog.md`.
`poriscope/utils/settings_schema.py` holds the pure validator,
`poriscope/utils/plugin_schemas.py` the discovery and retrieval,
`tests/unit/utils/test_settings_schema.py` and
`tests/unit/plugins/test_plugin_settings_schema.py` the tests, and
`scripts/check_plugin_schemas.py` the standalone runner. All 24 plugins report clean.

Two things about it are worth carrying forward:

- **No pre-commit hook was wired**, though step 3 of the original plan called for one. The
  test suite covers it on every branch push, and a hook would have made the six owner-held
  `Basic_PeakFinder` findings block commits before the owning developer had seen them.
  Revisit once block 5's `CODEOWNERS` exists.
- **The rules were derived by measurement, not from the docstring**, and one docstring
  claim turned out to be false: "Value and Type are required" was contradicted by 27 of the
  91 shipped parameter entries, the base classes' own included. A missing `Value` is
  therefore treated as unset rather than flagged, and the sentence was corrected in all 31
  files carrying it. If the rule set is ever extended, measure the candidate rule against
  every shipped plugin first - it is a few lines of script and it is what stopped this from
  shipping 27 false positives.

Nothing is left open from this block.

## 3. Contribution scaffold / template generator - DONE 2026-09-01 (data plugins)

Landed as `scripts/new_plugin.py`, with `tests/unit/scripts/test_new_plugin.py` covering
it; the narrative, the measurements and the two defects the real gates caught are in
`changelog.md`. All eight data plugin families and both variant shapes generate output
that passes `pre-commit run --all-files`, the compliance suite and the schema check
untouched.

Three things about it are worth carrying forward:

- **The analysis-tab half is not built and is the open remainder of this block.** A
  Controller/Model/View triad is 8 abstract methods across three files
  (`MetaController` 2, `MetaModel` 1, `MetaView` 5) plus the class-name-equals-filename
  rule and `_init` assigning `self.view`/`self.model`; nothing else needs registering,
  which is why a ~100-line triad is a valid runnable tab. `FAMILIES` in the script is
  shaped so the three can be added to it without rework. Worth knowing when it is picked
  up: **the `HelloWorld` example under `docs/source/_static/images/examples/` is stale**
  and would not instantiate today - it implements 4 of `MetaView`'s 5 abstract methods,
  missing `notify_plugin_state_changed`, and imports `from utils.MetaView import MetaView`
  rather than `poriscope.utils.MetaView`. A generator would replace it with something that
  works.
- **No generated test stub, and the plan's reason for wanting one was wrong.** Step 2
  asked for a `tests/unit/plugins/<category>/` stub "so `test_plugin_compliance.py`'s
  discovery picks it up immediately"; that discovery is `pkgutil.walk_packages` over
  `poriscope.plugins` and needs no test file at all. If a stub is ever added it needs a
  better justification than that one.
- **The body policy is measured, not chosen**, and re-deriving it is a few minutes of
  probing: `pass` under a non-`None` return is mypy `empty-body`, a copied
  `:raises X:` above a `pass` body is pydoclint DOC502, the same field above a
  `raise NotImplementedError` is DOC503, and raising with no field is DOC501. Anyone
  changing what the stubs emit should re-run those four probes rather than reasoning
  about them.

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

Landed as `.github/workflows/docs-check.yml`; see `changelog.md`. The one open remainder is
block 5's out-of-repo admin step: marking the check as a required status check in branch
protection for `main`/`develop`. Enabling `nitpicky` was measured (1170 warnings) and
deliberately left off - that is its own piece of work, not follow-through from this block.

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

## 8. Custom lint rules encoding existing tribal knowledge - CLOSED 2026-09-01

**Nothing here is left to build.** The block proposed mechanically enforcing three
conventions that were held by review attentiveness alone. All three are now resolved,
none of them by writing the checker this block asked for:

1. ~~No nested functions.~~ **Dropped 2026-09-01.** `CLAUDE.md` no longer prohibits
   nesting outright: a short, simple nested function is fine where it is genuinely the
   simpler option, which is a judgement an `ast` walk cannot make. A checker would have
   to encode a line-count or complexity threshold to approximate it, and would flag
   exactly the small callback closures the convention now permits. Do not build it.
2. ~~Bare `except:`.~~ **Already enforced; there was never anything to add.** The block
   asked whether `ruff` had a built-in rule for this and whether it was enabled, and the
   answer to both is yes: `E722` is in Ruff's **default** rule set, which
   `pyproject.toml`'s `extend-select` adds to rather than replaces, so the gate has been
   catching bare `except:` all along even though no line of config names it. Measured
   rather than reasoned - a throwaway file containing a bare `except:` was put under
   `poriscope/` and `pre-commit run ruff --files ...` failed it with
   `E722 Do not use bare except`. The one-line config addition the block held in reserve
   would have been a no-op.
3. ~~Explicit sqlite3 resource cleanup in a `finally` block.~~ **Deferred by design, not
   queued here.** It is a semantic rather than syntactic pattern - a general checker would
   have to track whether a `sqlite3.connect`/`.cursor()` result is closed on every exit
   path - and the block itself concluded the right home for it is block 1's conformance
   suite, whose open-file-handle check catches the same defect empirically. Block 1 is a
   pytest suite and so is owned by another developer; this rides along with it whenever it
   is built, and is not separate work.

The block's step 4, documenting whichever of these became real automated checks, is done
in `quality_control.rst`, whose "Which rules are enabled" note now says that Ruff's
defaults are in force on top of the selected rules and names `E722` as the example that
matters here. It is deliberately **not** added to `CLAUDE.md`: that file is loaded in full
every session and should carry rules a human has to remember, and a rule the gate enforces
on every commit is not one of those.
