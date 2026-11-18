# Decisions

Short records of choices made deliberately, especially choices *not* to do something, so
the same question is not re-litigated from scratch. Each entry is context, the decision,
the evidence, and what would make it worth revisiting. Detail about work that *was* done
lives in `changelog.md` and git history.

Entries referring to "step 3/4/6/7" mean stages of the full-codebase type-annotation pass,
which ran through August 2026 and is complete. The step numbers only date the decision.

Entries from September 2026 that name a "Step 4a", "5c.1", "Decision C", "Tier A" or the
"closeout" refer to the 2.0.0 refactor plan, `refactor_2.0.0.md`, deleted at release; it is
in git history (last present at the parent of the commit that deleted it) and its write-up,
with the method rules, is at <https://claude.ai/code/artifact/304ba119-d177-4918-90af-471d6de6bb80>.
Like the annotation-pass numbers, these labels only date and place the decision.
`future_refactors_and_features.md`, cited by some entries, was folded into `future_fixes.md`
and deleted on 2026-09-27; it too is in git history.

---

## 2026-11-18 - A filter is never serialised: it is told to be thread-safe, and an override is not refused

**Context.** A filter is handed out as a bare callable (`MetaFilter.get_callable_filter`) and run
inside other plugins' generators, on several worker threads at once and on the GUI thread for plots.
Nothing ever consulted `force_serial_channel_operations` for one, yet `MetaFilter` carried a
word-for-word copy of `BaseDataPlugin`'s method and its docs page listed it as an optional override.

**Decision** (Kyle, 2026-11-18). The copy goes. The method is still inherited from the base, so
nothing a plugin can observe changes and this is not a break. `MetaFilter`'s class docstring,
`get_callable_filter` and `_apply_filter` say a filter must be thread-safe, as do the filter page and
the serial-operations page, and `new_plugin.py` neither offers that override for a filter nor
generates it when asked by name.

**Not taken.** Refusing to load a filter class that defines the method: it would turn a false sense
of safety into an error, but it breaks a filter that loads today, for a method that does nothing.
Wrapping the callable in the plugin's guard, so that the declaration would mean something for a
filter: the requirement is stated instead of adding a lock on every filter call.

**Revisit if** a filter is needed that cannot be made thread-safe; wrapping the callable that
`get_callable_filter` returns is the place to start.

---

## 2026-11-18 - Saved files break only at a major version: one rule for every file Poriscope writes

**Context.** Six kinds of file followed three rules. The session file refused any format number but
its own and read a file with none as the 2.0 layout; the metadata database read anything up to its
`SCHEMA_VERSION`; a plot configuration refused a file that did not name its format; the events
database, Save Filter files and `config.json` carried no version. The rule had to be settled before
3.0 shipped, because the shipped reader is the one that meets files written later.

**Decision** (Kyle, 2026-11-18). A saved file follows the release's version discipline (2026-11-12):
only a major release may stop reading a file, or write one an earlier release of the same major
cannot read. Minor versions never break a saved file, and a reader refuses only across majors.

- A format number (`SESSION_FORMAT_VERSION`, `PLOT_CONFIGURATION_FORMAT_VERSION`, each SQLite
  plugin's `SCHEMA_VERSION`) changes only in a major release. `tests/unit/test_saved_file_formats.py`
  pins the numbers per major, reading the release from the changelog's first header, since
  `constants.py` carries the previous version until the release bump.
- Within a major a file changes only by addition, and a reader ignores what it does not know: the
  session reader and the plot-configuration reader ignore unknown keys, and both database loaders
  require their core tables and leave any other alone. `SQLiteEventLoader` refused every unknown
  table until now; it tells a fitted-metadata database apart by its `experiments` table instead.
- A reader refuses a newer number, naming the versions. A file with no number is the layout from
  before versioning, handled explicitly: a 2.0 session is read without actions, a 2.0 plot
  configuration is refused, a database at version 0 is read.
- A writer refuses to add to a database with a newer number: rows in an older layout damage a file
  that a reader could otherwise only fail to open.
- The events database is stamped `user_version` 1 in the transaction that creates its schema, as
  the metadata database is (ruling E, 2026-10-06). The 2.0.2 loader opened a file 3.0 stamped.
- Save Filter files and `config.json` stay unversioned: a filter file is a hand-editable map of name
  to filter text that every release reads, and `config.json` is read key by key with defaults.

**Accepted as it stands** (Kyle). The 3.0 formats were designed before this rule and are not
renumbered: the session reader refuses any number but 2, an older one included, and no build ever
wrote format 1.

**Rejected.** Versioning every file: 2.0 could not read a 3.0 filter file, and it would stop being
hand-editable. Recording today's behaviour and changing nothing: a later change to the events
database could be noticed only by its table names. Comparing `poriscope_version` strings in place
of format numbers: the format is what a reader has to understand, and a development build carries
the last release's version.

**Revisit if** a format has to change inside a major: that is a breaking change, and it makes the
release a major one.

---

## 2026-11-18 - Ruling A confirmed: the ground-truth tolerances the fitter accuracy tests enforce

**Context.** The tolerance policy for fitted values against planted ones was proposed on 2026-10-05,
approved "as a starting point", re-measured on Bessel-filtered data the same day and enforced from
then on, with no recorded approval of the amended bounds and no entry here.

**Decision** (Kyle, 2026-11-18): the bounds as shipped, in
`tests/unit/plugins/conformance/test_fitter_accuracy.py`. Fixtures are Bessel-filtered at 100 kHz
with Rise Time 16 us; CUSUM's step is 100 pA and ClassicCUSUM's 10 sigma. Per event and per planted
sublevel, against the stored (post-filter) sigma: current and blockage within 1.0 sigma at 83-sample
steps and 2.0 sigma at 40- and 20-sample steps; duration within 2 samples at 15 pA of drawn noise
and 12 at 50 pA; the level count exact at 15 pA and on at least 24 of 25 events at 50 pA, the missing
event named. Required bands: 15 and 50 pA at 83- and 40-sample steps, 15 pA at 20-sample steps. The
100 pA band is informative, kept as strict expected failures (ClassicCUSUM's 10 sigma threshold
exceeds the 150 pA step).

**Why wider than white-noise intuition.** A median over low-pass noise has far fewer effective
samples than the step is wide: about 9 per 83-sample step and about five per 40. ClassicCUSUM's
step is 10 sigma because the 3 sigma first proposed, 12.7 pA at the post-filter sigma, found the
planted levels on 2 of 24 events.

**Revisit if** a fitter's mechanism changes - re-measure every expected-failure mark that blames
it - or a fitter that models events differently is added, which opts in by name (2026-10-06).

---

## 2026-11-18 - A reference links only what the docs publish; the build fails on a dead one

**Context.** `sphinx-build -W` passed with 139 references that resolved to nothing (91 targets),
because `nitpicky` was off; 42 of them arrived during one month of analysis-tab work with nothing
to show it. Three causes covered almost all: a generated page declares its class by a label, not as
a Python object; a method is published only on the class that defines it; and a class docstring is
rendered as page text, where a short `:meth:` has no class to resolve against.

**Decision** (2026-11-18). `nitpicky = True`, so the existing `-W` build, CI's Docs Render Check and
the post-merge hook all fail on a dead reference. Prose links a class by `:ref:` and a method in
full on its defining class; anything unpublished is a literal. `conf.py` links a class named in a
type field or signature to its generated page (a type field cannot hold `:ref:`), and
`nitpick_ignore_regex` lists the eight supporting types a signature must name that have no page.

**Rejected.** Resolving any bare name that is unique in the inventory: it links whatever shares the
name, and breaks silently when a second one appears. Publishing a page per supporting type: the
methods that take or return them already describe them (`ActionDeclaration` set the precedent,
2026-11-03). A page for every private helper a docstring mentions: the published private contract
is the abstract hooks, by design.

**Revisit if** the ignore list grows past a handful, which would mean supporting types have become
something contributors look up and want pages.

---

## 2026-11-18 - A Protein fit component is bounded at a quarter bin, not rejected under half a bin

**Context.** A Protein tab user's rerun on develop lost fits they had before. On their database
(`Ub_250mV_0p2MPa_CUSUM_A1`, 4.17 MHz, Filtered Histogram, automatic bins, which HEAD reproduced
exactly) the 2026-11-12 half-bin rule rejected 88 of the 177 fits passing every other check. 72 of
those had a component under 0.01 bin: the unbounded fit (`min_std = 0`) parks a delta on one sparse
bin, often the first filtered samples of the event. But real levels were rejected too: events 2045
and 2164 at 0.39 bin, and 26 of 40 synthetic two-level events at n = 1000, separation 12 sigma.
Automatic bins are sized from the spread of the whole event, which spans both populations, so a
clean population is routinely narrower than half a bin. This met that entry's "Revisit if".

**Decision** (Kyle, 2026-11-18). `_fit_double_gaussian` bounds each sigma at
`MIN_FIT_STD_BINS = 0.25` bin, both seeds, clipping the start into the bounds. The sanity check
rejects a fit with a component on that bound (within 1%) or with means closer than
`MIN_SEPARATION_STD = 0.25` of the wider sigma, in place of the half-bin rule. On that database:
104 fits accepted instead of 89, none with a component under 0.39 bin, all 46 of the user's current
fits kept.

**Evidence.** Floors swept on all 5,997 events: 0.1 bin leaves 9 delta fits, 0.15 to 0.3 none, 0.35
two, 0.4 eleven; 0.5 (PeakFinder's) leaves 33 components pinned at the bound. Trimming or
percentile-clipping the event edges (seven variants) left 61-70 delta fits: the delta moves to the
next spike. Without the separation check, the bounded fit splits a noise-free single peak (width
0.05) into two components on one mean that pass the t-test; on real data the smallest accepted gap
is 0.41 of the wider sigma, so 0.25 costs none. PeakFinder's one-FWHM separation would drop 6-14.

**Rejected.** Lowering the half-bin threshold to 0.1 bin alone (96 accepted against 104: the delta
fits are refused, but a fit that lands on a delta never finds the second population the bounded one
does, and 7 of the 16 it misses fail the parameter-error check on the delta's covariance); trimming the
event edges (above); a separate rule for zero width on top of the other mean (on short events it
restored most false two-population fits along with the real ones).

**Revisit if** short events matter: under automatic binning, events under ~150 samples get 2-7 bins
and cannot be fitted by any of these rules (see `future_fixes.md`).

---

## 2026-11-17 - A replay restores the state the actions produced, not their order: independent runs start together

**Context.** A replay ran one entry at a time and waited for each Find or Fit, so a Find clicked once on four channels
replayed one channel after another: 1.6 s by hand, 2.8 s replayed (four channels of 10 s at 4 MHz, clean copy of
`3511c2de`, 2026-11-16). The lab's recordings are 1,000 s or more at 5 MHz.

**Decision** (Carolina, 2026-11-16). A replay restores the state the recorded actions produced; the order and timing
of the steps are not part of that state. Each `result` is launched as soon as nothing earlier holds it back: an earlier
run of its own key, or a view drawn from that run. Every other entry keeps its place among the entries that are not
results, and waits for the run its `depends_on` names. When the replay ends, the panel and the history read as in
recorded order. When an entry fails, nothing new starts and the user is asked at once while the runs already going
carry on; each later failure is asked about in turn. Go back stops those runs, then clears. Keep lets them end, and the
next Replay Actions replays only what did not finish. No shipped tab has a run that reads another run's output, so a
replay cannot yet start one run after another; a run that did would read that output unfinished. A view that shows a
run's output names it in `depends_on`. This is documented for contributors, not enforced.

**Rejected.** Grouping only neighbouring runs: a plot between two Finds would still serialise them. Recording which
runs one click launched: every run happens before the user acts, so the grouping tells a restore nothing, and it would
change the session file. A cap on how many runs start together: a click has none. Carrying on after Keep with the steps
that don't depend on the failed one: that is "Skip this step" without its button, and the declarations between views
are incomplete (Clustering's Merge). Leaving the history in the order the runs finished.

**Revisit if** a run needs another run's output: a run would name the run it reads, as a view does with `depends_on`,
and the replay would wait for it. Or if "Skip this step" lands.

---

## 2026-11-17 - Flow tests keep rediscovering plugins and drawing figures: two speed-ups measured and dropped

**Context.** Each flow test builds a whole app, which loads all 51 plugin files again (~155 ms
locally) and draws its figures. Two test-only speed-ups were built: a cache that discovered plugins
once per process and shared the classes, with a guard that restored any class state a test changed;
and a stub that skipped `FigureCanvasAgg.draw` unless a test was marked `renders`.

**Decision.** Neither landed (Carolina, 2026-11-17). Every flow test rediscovers plugins and draws
its figures for real, as the app does.

**Evidence.** Locally, clean worktrees, one run at a time, no standby, 2 workers: with the cache the
flow tests took 270 s summed against 720 s on develop `f411056c`, and the full suite 636 s to 396 s
with both speed-ups; the stub alone was worth 7 s (352 s against 359 s on `33f57ad5`). On CI the
test steps did not change within their run-to-run noise of about +/-25 s per leg, with both (#733
`a64182ab` against #734 `33f57ad5`) or with the stub alone (#734 against #735 `92a05345`),
2026-11-17. A benchmark of one discovery explains it (locally 2026-11-17; CI #742 `e3d5005c`,
2026-11-18): ~155 ms locally against 28-42 ms on CI's four legs, Windows and Linux alike. The
difference is opening the compiled plugin files - about 68 ms per discovery locally against 1-3 ms
on the runners - while the abstract-base-class subclass checks cost tens of milliseconds everywhere.
At CI's cost the cache saves roughly 25 s per leg, the size of the noise. The cost is in how that
machine opens files, not in the code: the same files open several times faster on every CI runner, Windows
ones included; what slows them there was not established. Against it: under the cache the flow tests
diverged from the app (a session reset gets new plugin classes in the app, the same ones under the
cache), plugin modules' import-time code ran once per process (30 sklearn warnings the app hides),
and it needed the guard and an import ratchet; the stub hid draw-time errors.

**Revisit if** plugin discovery or rendering becomes a measured share of CI's test time (the junit
artifacts show it per test), or several developers' machines show the cost after machine-side
causes are ruled out.
---

## 2026-11-17 - Test time is recorded on every CI run and checked two ways, both warn-only

**Context.** The suite slowed several-fold twice with every test green (Aug 2026; 2026-10-29, CI test
step 313 s to 713 s, tests +5%), and CI kept only the summary line.

**Decision.** Every test job writes `--junitxml` (`junit_duration_report = total`) and a
per-directory summary; branch CI keeps it 30 days. On the Linux 3.12.0 leg only: `--time-budget`
warns on a test over its tier's budget (unit 5 s, integration 20 s, e2e 60 s; wider fixture setup and
scope-closing teardown not counted; opt-out `exceeds_time_budget(reason)`), and
`test_durations.py check` warns above 1.3x the suite's or 1.5x a directory's expected time. Both warn,
neither fails (Carolina, 2026-11-11). Every warning is acted on before merging: fixed, marked with a reason, or noted as noise (Carolina, 2026-11-17). Under xdist the worker attaches each test's own time and markers
to its teardown report for the controller (Carolina, 2026-11-16); the alternative, computing from the
junit file, loses the fixture-time corrections and the opt-out. The baseline is each directory's
median over several CI runs.

**Evidence.** One test's time varied up to +60% over 12 local loops; CI's Linux leg ranged 187-298 s
in one day, so ~25% is run-level noise. A real `-n 2` run warned on slow tests and skipped the marked
one.

The budget becomes failing once 30 develop runs in a row show no false failure - a test over its
budget in one run and within it in the runs around it, with no change to it (Carolina, 2026-11-17).

**Revisit if** the size check warns on runs with no real change.

---

## 2026-11-17 - A test that leaves a QThread running fails at teardown

**Context.** Destroying a window whose worker thread runs aborts the interpreter, and an abort names
no test. Measured on `642648b0`, no integration or e2e test reaches teardown with a running thread.

**Decision.** A root autouse fixture records each `QThread.start` (weak references), is torn down
before the window cleanup, waits up to 5 s per running thread, then writes the test and thread past
pytest's capture and fails the test (Carolina, 2026-11-16). Names come from `key`/`channel`
attributes, not `isinstance`: importing `WorkerThread` would load all of `poriscope` (7 s) into every
run's root conftest.

Teardown runs replays, then threads, then windows: `stop_replays_after_each_test` asks for this guard,
and this guard for the window cleanup, so a replay left running is stopped and named as a replay
before its threads are checked (Carolina, 2026-11-17).

**Evidence.** A deliberate 7 s thread was named on the terminal and errored at teardown, no abort; the
full suite passes under the guard.

**Revisit if** a thread is started outside Python's `QThread.start` (a `QThreadPool`, C++).

---

## 2026-11-16 - Two duplication floors stay: the loader bases' 66 lines and CUSUM/NoFitter's 171

**Context.** `measure_duplication.py --verbose` (2026-11-16): `MetaDatabaseLoader` and `MetaEventLoader` carry the
same 58-line `get_empty_settings` and 8-line `force_serial_channel_operations` (66 removable); `CUSUM` and `NoFitter`
share `_populate_event_metadata` (72), the four `_define_*` declarations (88), `_pre_process_events` (6) and `_init`
(5), 171 removable, all of the `eventfitters` family's.

**Decision** (Kyle, 2026-11-16). Both are accepted floors under 2026-09-19 "No new inheritance layers in the data
plugins". Removing either needs a base neither has: one above two `Meta*` families (a data-plugin API change), one
between CUSUM and NoFitter, or the column declarations on `MetaEventFitter`, where other fitters declare other columns.
The duplication ratchet keeps both from growing.

**Revisit** on 2026-09-19's condition: a third loader base or fitter sharing the same code.

---

## 2026-11-16 - A merge is gated on a clean worktree of the exact commit, not the shared checkout

**Context.** On 2026-10-10 the duplication ratchet passed in the shared checkout on code that fails it in every clean
copy. The checkout's uncommitted and ignored state at that moment was not recorded, and every committed copy fails, so
the cause cannot be reproduced.

**Decision.** The merge gate is a full suite in `git worktree add --detach <path> <commit>`, after
`python scripts/generate_all_autodoc_rst.py` there (a clean copy lacks the gitignored autodoc, so those tests skip).
Taking the unrecorded state out of the result is cheaper than hunting for it.

**Revisit if** the two disagree again: run `git status --ignored` in the shared checkout and keep the output before
touching anything, so the cause can be found.

---

## 2026-11-16 - `git flow release finish` is run by a human, in the background, with the tree left alone

**Context.** The finish opens three editors: two merge messages, which `GIT_MERGE_AUTOEDIT=no` suppresses, and the tag
annotation, which git flow prefills with nothing. At 1.9.0, `GIT_EDITOR=true` gave an empty message and the command
died with `fatal: no tag message?` after the merge into `main` had landed, leaving the release half-finished. Passing
`-m` makes git flow append its own text: the annotation read `v1.8.0 v1.8.0`. 1.9.0 was salvaged by pointing
`GIT_EDITOR` at a command that writes the annotation into the file, which is idempotent over a completed merge but
fragile. The `post-merge` hook (autodoc and Sphinx) ran past a two-minute timeout at 1.8.0 and past ten minutes in a
`feature finish` on 2026-09-26; both times the git work had finished and only the branch deletion was left. On
2026-10-19 a `git stash pop` during the hook left the merged branch undeleted, because git flow re-checks for a clean
tree before deleting it; `git branch -d` finished it.

**Decision** (Kyle). Claude prepares a release up to the finish; a human runs
`GIT_MERGE_AUTOEDIT=no git flow release finish <version>`, checks the annotation (fix a duplicate with
`git tag -d <tag> && git tag -a <tag> -m "<tag>" <commit>`) and pushes `main`, `develop` and the tag. Finishes run in
the background with no timeout; nothing touches the tree until they report, and `git branch`/`git tag` are checked
before re-running anything.

**Revisit if** git flow can take the tag message non-interactively without duplicating it, or the hook stops
rebuilding the docs.

---

## 2026-11-12 - The replay-scenario failure of 2026-10-26 stops being tracked, undiagnosed

**Context.** `test_replay_guard_no_gui.py::test_a_replay_reproduces_what_the_action_produced[EventAnalysisController]`
failed once on 2026-10-26, in the first run after its second-tab perturbation was made effective. The output was not
kept, so it was queued as an open failure.

**Decision** (Carolina, 2026-11-11). Delete the queue item. The failure cannot be diagnosed: there is no output, and
the code it ran is gone. The test then replayed entry by entry through `replay()` with a wait between entries; since
`0bc10f2b` (2026-11-11) every scenario replays through `start_replay` and waits for the sequence to end, and since
`282f4c0f` (2026-11-03) `settle` also waits for the held results of a finished run.

**Evidence.** About 110 local runs after the failure, none failing. Of the 51 CI (Branches) runs from 2026-10-26 to
44134467491 on `a64182ab` (2026-11-17), 8 failed (40261590138, 40965910820, 41516801896, 41521392204, 41541645874,
43144925224, 43144951706, 44112181488), none in this file. The test as it is now: the whole file 30 times in a row in
a clean copy of `3511c2de`, 39 passed each time (2026-11-12), and the 20 completed CI runs from 43072520051 on
`0bc10f2b` to 44134467491 on `a64182ab`.

**Revisit if** a replay scenario fails again: save the full output before any rerun, and diagnose it.

---

## 2026-11-12 - Protein's reachable fraction is the fit's mass inside the traced region, not an acceptance rate

**Context.** A user asked for a per-event "success rate", the reverse-sampler analogue of their old
forward n/N (blockage pairs drawn from the fit that have a (V, m) root). Accepted / proposals inside
4 sigma stays at 0.065-0.20 whatever the geometry (0.095 for a fit 98% unreachable, 0.126 for one
wholly reachable): every proposal is producible by construction, and each batch is normalised by its
own best likelihood. Binning forward-mapped proposals over the fit's box (the user confirmed it tracks
their old n/N) costs 1.05-1.47 s per family per event at 10M proposals, against 12 ms for both
families' sampling at N=100, and reads 0.01-0.03 high at the region's edge.

**Decision** (Kyle, 2026-11-12: "prioritize speed"). The forward map's Jacobian keeps one sign over the
sampler's geometry space (360,000 points, 4 pores, both families), so the reachable region is exactly
the image of that space's edge; `ProteinModel.reachable_fractions` integrates the fit's Gaussian over it
on a 65x65 grid across +/-4 sigma, 100 points per edge: 1.9 ms per family, within 0.0006 of a
257x257, 4,000-point reference. The sigmas are the sampler's floored ones (1% of the mean), so the
fraction describes the target the ensemble beside it was drawn from; a fit component is never
narrower than a quarter of a bin anyway. A fit names its larger mean the maximum, while near m = 1 the forward
model's `dI_max` is up to 0.3% below its `dI_min` (V = 200, d = 10, L = 20); the sampler compares them
the same unsorted way, so the region and the ensemble agree.

**Rejected.** The 4 sigma acceptance ratio (measures the cutoff, not reachability); the binned estimate
(slow, budget-dependent, biased high, and under-reads the flat oblate corner: 142 of 500,000 proposals
reached a fit there); a root-finder over drawn blockage pairs (new inversion code, Monte Carlo in N).

**Revisit if** `_compute_theoretical_blockages` changes and `test_the_forward_map_never_folds_over_the_geometry_space`
fails (sorting `dI_max`/`dI_min` inside it, the tidy-looking fix for the near-sphere swap, folds the map
and fails it), or the sampler's geometry limits move off the shared class constants.

---

## 2026-11-12 - The duplication baseline names the duplicated functions; tests that only pinned a copy go

**Context.** The test-value audit found six tests asserting that a base class owns the only copy
of a method. Each failed together with the duplication ratchet when a copy was pasted into a
subclass, but the ratchet's failure invited `--update`, and the baseline held counts only, so it
could not say what had been copied.

**Decision** (Kyle left the redundancy to Claude, 2026-11-12). The ratchet is the single guard: the
baseline also lists each family's `duplicated_functions` (`file.py:Class.method`), a rise names the
ones that are new, and its message says a rise is usually a copy to remove. The names are never
compared, so a rename does not churn the baseline. The per-method "only copy" tests are dropped.

Each family now also holds the `Meta*` bases its files inherit: until then a base method copied
onto one subclass had no identical twin in the family and counted only as one more function.
Pasting `show_selection_tree` onto `MetadataView` now fails as duplication and names both copies.

**Revisit if** a copy lands through `--update` unnoticed: then an explicit per-method test is worth
its upkeep for that method.

---

## 2026-11-12 - A Protein double-Gaussian component narrower than half a bin is no second population

**Context.** `ProteinModel._fit_and_sanity_check_double_gaussian` accepted, on a clean single peak
(sigma 0.05 or 0.1 over 200 bins) and on a peak 1000x a second, a fit whose second component had
sigma 0 on top of the first: the degenerate covariance passed the t-test on the means. A noisy single
peak was rejected. `test_single_peak_fallback_degenerate_bug` pinned the raw helper's output.

**Decision** (Kyle, 2026-11-12: "a zero-width component fit should be treated like failure to find two
populations"). The sanity check rejects a fit whose narrower component has sigma under half a bin
(FWHM under about 1.2 bins), the resolution limit of the histogram it was fitted to. The raw
`_fit_double_gaussian` is unchanged; every acceptance rule stays in the sanity check.

**Revisit if** a real dataset has a population genuinely narrower than one bin: then the binning, not
this rule, is what should change.

*Superseded 2026-11-18: one did, at 0.39 bin, and the binning was not the cause; the fit's width is
bounded at a quarter bin instead (see that entry).*

---

## 2026-11-12 - The suite runs in parallel by whole files, workers sized by logical cores and free memory

**Context.** After the window cleanup, a serial run took 493-517 s. With `pytest-xdist` and
`--dist loadfile`: 128 s at 4 workers, 98 s at 16, all green; one worker peaked at 1.9 GB.

**Decision.** `pytest -n auto` is the gate, locally and on CI; plain `pytest` stays serial.
`--dist loadfile` is in `addopts`, so a file keeps its order on one worker (leaked Qt state has
made order matter before). The root conftest's `pytest_xdist_auto_num_workers` returns
`min(logical cores, free memory // 2 GB)`. Logical, because a 4-vCPU runner reports 2 physical
cores; memory, because 16 workers do not fit 13 GB free. `psutil` is a dev dependency for the
memory reading. `test_plugin_compliance` sorts its cases, since workers must collect identically.

**Rejected.** `-n auto` in `addopts`: every single-test run would start a pool of Qt workers.
`--dist load` (per test): it splits files, reorders them, and runs module fixtures once per worker.

**Revisit if** the longest file stops setting the floor (`test_replay_guard_no_gui.py`, 45 s), or
a worker's peak memory moves far from 2 GB.

---

## 2026-11-12 - A release with any breaking change is a major version; the 2.1 work ships as 3.0

**Context.** The 2.1 changelog carries about 36 breaking lines (2.0.0 had 54; the 1.x minors 0-2):
the data-plugin contract (`report_status` with no alias, `close_resources`, `reset_channel`,
`get_single_event_data`), refused 2.0 plot configurations and action histories, and changed
scientific results. The wheel declares compatible-release ranges, so a `poriscope~=2.0` pin would
install it and break. The 2026-10-09 ruling had shipped the plugin breaks in a minor anyway.

**Decision** (Kyle, 2026-11-12). Release numbers follow semantic versioning: a release whose
`changelog.md` section has any entry under Breaking Changes - API, saved files or results - is a
major version; compatible additions are a minor; fixes that break nothing are a patch. The 2.1.0 work
was renamed 3.0.0 (done 2026-11-12).

**Revisit if** the project moves to a different scheme, such as calendar versions. Until then,
read the release's Breaking Changes section before choosing its number.

---

## 2026-11-12 - Qt windows are deleted after every test at root scope, and a survivor fails the test

**Context.** A full serial run took 1,650 s. `Triad.close()` only hid its `MainView`, so the
integration flows left about 9,300 top-level windows and 2.47M objects alive. Each leaked
`BaseLineEdit` stayed an application-wide event filter (`ProteinController()` built in 52 ms with
none alive, 11.6 s with 1,000), and every full `gc.collect()` took about 2.4 s against 0.1 s.
The views conftest had fixed the same leak in 2026-08, for its own directory only.

**Decision.** An autouse fixture in the root conftest calls `tests/_window_cleanup.py` after
every test: deliver queued events, close and `deleteLater()` every top-level widget, send the
deferred deletes, and fail the test if any window survives. The `gc.collect()` calls in the
SQLite loader, Chimera deprecation and standalone-settings fixtures go: none freed anything a
test checked, and no file-lock retry ever fired. The views conftest keeps its own pass and its
gc cadence (2026-08-28 entry).

**Evidence.** Serial run 1,650 s to 493 s, 5,824 passed, no assertion changed. Without the
first `processEvents()`, a worker's queued "finished" reached a deleted view in the
conditioning flow.

**Revisit if** a test legitimately needs a window to outlive it (none does today): give it a
session fixture that owns the window, not an exemption in the guard.

---

## 2026-11-12 - The Raw Data PSD tests compare to scipy within `rtol=1e-12`, not exactly

**Context.** Branch CI's fresh-stack legs (3.14, Linux and Windows) failed two tests in
`test_rawdata_psd_fit_no_gui.py`: 51/101 and ~120/251 bins off by a few ULPs. `NIBinaryReader.load_data`
returns an `np.memmap` (owning a copy); the test calls `welch` on a plain ndarray of identical values.
scipy 1.18.1 sums the two in a different order; 1.15.3 does not (numpy 2.2.6 vs 2.5.4 makes no difference).

**Decision.** Relax the test, not the reader: the PSD is correct, and stripping the subclass would
change what every caller receives for no user-visible gain. `rtol=1e-12` still fails an overlap of 124
for 125, or a segment one sample short.

**Revisit if** an exact comparison against a library is needed again: pass it the same array type.

---

## 2026-11-11 - The conditioning app is ported as a data-plugin family, an NI reader, a Raw Data option and a tab

**Context.** The lab's tkinter conditioning script (Michel Stephan) read a folder - pore-size CSV, PSD `.bin`
files per bias - computed each file's 1 Hz noise and plotted it beside the pore size; a second script did one file's
PSD with the fit. No tab reads input files, no family fits the CSV, and `MetaReader` joins a folder's files into one
timeline, while one of the 142 sample files is short (67,000 of 100,000 frames), so file boundaries cannot be found
by length.

**Decision** (Kyle, 2026-11-11: inputs and outputs kept, paths through native machinery). A ninth family,
`MetaConditioningLoader`, serves cycles, pore sizes and per-recording samples, sample rate and points per average;
the tab does the spectral analysis. `NIConditioningLoader` decodes each file through an `NIBinaryReader` it owns, so
the format is implemented once. The single-file view is Raw Data's Update PSD with PSD Options, every option
defaulting to the old PSD so saved entries replay. Welch and the power-law fit live once on `MetaModel`, the shading
once on `MetaView` (two tabs, stateless). The plot is a recorded `view` that starts one worker per channel and draws
when the last ends: the replay contract's only background kind, `result`, is keyed on one plugin and one channel.
Channels are 0-based, as in every other tab.

**Fixed against the original,** each pinned by a test a mutation probe killed: results cached by folder alone (stale
after a settings change), noise bands placed by cycle index (wrong when a PSD is not taken every cycle), the short
file analysed silently, several CSVs picked arbitrarily (now joined in file-name time order).

**Evidence.** On a synthetic experiment the tab's 1 Hz values match the script's to 1e-9 relative for two settings
(`tests/synthetic_data/conditioning_original_app_goldens.json`). The script took 17 s on AL_TS (8.9 s PSD+, 8.0 s
PSD-), hence the workers.

**Revisit** if a second conditioning format arrives that does not fit the family's API, or if the replay contract
gains a keyed background kind, which the plot should then use.

---

## 2026-11-10 - A plot configuration names its format, and the tab's Model reads and writes it

**Context.** Save Plot Configuration wrote the live history, keyed by position, with no version, through the main
window's model; the tab read it back itself. Load Session accepted an empty one as an empty session, and a JSON list
raised in the slot.

**Decision** (Carolina, 2026-11-10). `{"format": "poriscope.plot_configuration", "format_version": 1,
"poriscope_version", "tab", "actions": [...]}`, holding the tab's kept actions. `MetaModel.save_plot_configuration`
writes it (atomically, `json_files.write_json_atomically`) and `read_plot_configuration` checks the whole file first:
another format, version or tab, or no format at all - 2.0 and every earlier 3.0 build - is refused with the reason.
The session reader refuses a file that names another format. The route through the main window is removed, as Save
and Load Filter already work in the tab's Model. `format` names the file because `kind` already means an action's kind.

**Rejected.** A session file with one tab (Load Session would accept it and clear the workspace). A version key of its
own name (each format inventing its key). Today's layout plus a version (keys by position; collides with the
session's `format_version`). The live history (replays plots a later one replaced). Telling a session from an
earlier plot configuration at Load Plot Configuration (the tab's Model would have to know the session layout).

**Revisit** closed 2026-11-18: the saved-file policy of that date keeps both formats as they are.

---

## 2026-11-09 - The session file versions the whole file, lists the plugins in order, and keeps the tabs apart

**Context.** Each tab's recorded actions go in the session file, which then needs a format version and the last tab.
The 2.0 file was one map of entries, tabs among the plugins; its reader refuses any top-level value that is not an
entry.

**Decision** (Carolina, 2026-11-09). `{"format_version", "poriscope_version", "last_tab", "plugins": [...], "tabs":
{...}}`: the version covers the whole file, `poriscope_version` is for messages only, the data plugins are a list
(a plugin is restored after the plugins it depends on, and JSON keeps no order for an object's keys), each tab's
state and `actions` sit under its class name. Only `MainModel` knows the layout; the in-memory history is unchanged.
A file with no version is the 2.0 layout and loads; another version is refused whole. Loading restores the plugins,
then the tabs. A plugin cannot take a tab's name.

**Rejected.** The version and `last_tab` in each tab's entry (repeated per tab; versions part of the file). Top-level
keys beside the entries (a plugin the user names `format` collides). A reserved fake entry. 2.0 compatibility was
not weighed (Carolina, 2026-11-09), as for action files (`DECISIONS.md` 2026-09-17); 3.0 session files do not open
in 2.0.

**Revisit if** a file must open in an older version, or a part of the file needs its own version.

---

## 2026-11-09 - A plugin edit is told from a rename by its settings, without a signal

**Context.** Deleting a plugin drops the recorded entries naming it; renaming rewrites them; editing drops them and
its dependents', since an edit leaves results on screen its new settings did not produce. The only way to rename is
the Edit dialog, which always re-applies the settings, and an edit without a rename reaches the shell as
`(entry, "")`, like a new plugin or a dependent re-saved after its parent's rename.

**Decision** (Carolina, 2026-11-09). `MainController.update_plugin_history` compares the incoming settings with the
stored ones, leaving out the settings that name another plugin: a difference is an edit (drop, and a panel line); none
with a new key is a rename (rewrite); none at all changes nothing. It rests on the Edit dialog never changing a plugin
reference (`editable_source_plugins=False`), pinned by a test. Measured 2026-11-09 at `742ec83a`: an untouched Edit
dialog gives back identical settings for all 23 plugins a recorded action can name. The drop and the rewrite reach
every copy a tab holds (`MetaController.rewrite_plugin_entries`).

**Rejected.** A `plugin_edited` signal (a new signal for what the slot can already see). Every edit dropping (a rename
would drop every Find of a renamed reader's finders). Every rename rewriting (a rename with new settings would keep
entries that replay with settings they never ran with).

**Revisit if** the Edit dialog lets a plugin reference change, or a setting stops round-tripping through the dialog.

---

## 2026-11-09 - The autosave holds only what a tab ran

**Context.** At load, the autosave holds the loaded actions, not yet replayed. A replay records each step again,
and Keep or Go back leave the tab with part of them or none.

**Decision** (Carolina, 2026-11-09). Until a tab is replayed or worked in after the load, its autosave entry holds
the loaded actions; from then on, the kept history of what it ran. Starting a replay of the loaded actions counts, so
a replay whose first step fails and records nothing leaves the tab's entry empty. After
Keep or Go back on the loaded actions, the status panel says which steps the autosave lacks: Replay Actions still has them while the app is open, and loading
the session file again brings them back. Replay Actions is disabled once the loaded actions have all replayed, until
Go back or another load.

**Rejected.** Writing the loaded steps not yet replayed into the autosave (after Keep they start with the step that
failed, so a Restore would fail there again, and the file would describe steps that never ran).

**Revisit if** a crash must cost no replay at all.

---

## 2026-11-05 - Metadata's Reset button empties the history; Undo straight after brings it back

**Context.** Reset was one more recorded `reset`, shared with the resets the tab makes itself (a new figure, the first
Plot Events). Every earlier entry stayed, so Save, the saved session and Go back carried the whole history: in a manual
test, Go back re-ran every plot since the tab opened.

**Decision** (Carolina, 2026-11-05). The button calls `MetadataController.clear_history`, which records nothing, clears
the figure and calls `MetaController.set_history_aside`: the history is emptied and kept aside. Undo on the emptied
history replays it; anything recorded and kept first drops it (a refused plot, discarded, does not). A Reset of an empty
history keeps what was set aside. The panel says each turn: "Reset: plot and history cleared; Undo now will bring it
back", then "Reset: plot and history cleared" when a kept entry drops it, "Reset: Undo now will bring it back" when a
refused plot puts it back, and "Reset: plot cleared" with nothing to set aside. Memory only: the session file keeps only
what followed the Reset. Automatic resets stay recorded.

**Rejected.** Each Reset stacked, so repeated Undo walks back through them: the history only ever grows and can never be
cleared. Recording the button's reset with a flag: the entry would still carry the cleared history in every save.

**Revisit if** another tab gains a Reset button, or a session must restore an Undo across a restart.

---

## 2026-11-05 - A replayed step fails when it raises, does nothing, or leaves no finished run with results; 0 results is a failure

**Context.** A replay (`MetaController.start_replay`, `poriscope/utils/replay_sequence.py`) runs a tab's history one
entry at a time and has to decide when to stop and ask the user Go back or Keep. Telling a cancelled run from a failed
one needs the plugin's outcome, which the plugins do not report yet (queued in `future_fixes.md`). Kyle proposed
treating a run with 0 events the same as a failed run, since it would only happen from a settings issue; a Fit that ends
with 0 good fits is read the same way.

**Decision** (Kyle's ruling, Carolina 2026-11-04 and 2026-11-05). A replayed entry fails when it raises; when an action
declared `skip_on_false` returns `False`; or, for a Find or Fit, when its run does not leave a finished channel with
results: the status method is False (cancelled, failed, 0 events) or, for a Fit, `get_num_events` is 0. A cancel is a
failure too, for now. An entry that names no action or whose values no longer fit is reported and skipped, as before.
*Corrected 2026-11-17: the ruling covers live runs too, which this entry first left out.* A run with 0 results is
not saved in the tab's history, live or replayed, a Fit with 0 good fits as a Find with 0 events
(`MetaController._run_finished_channel`); the fitter still marks such a channel fitted, so it can still be plotted
and written. *Extended 2026-11-09: the question is the only dialog a replay opens; every error a dialog would show while a
replay runs - its runs' worker threads included - goes to the log file and into the question, under "What the step
reported".* *Extended 2026-11-12: a step that is not a `result` but starts background runs, Conditioning's plot, fails
when, once those runs have ended, the tab's `MetaController.background_step_failure` names a reason.* *Extended
2026-11-17: the question is asked as soon as an entry fails, with the runs already going left to go on.*

**Rejected.** Any `False` as a failure: a recorded overlay that drew nothing would fail every replay (`overlay_plot` is
recorded either way). Making the overlay `skip_on_false`: changes live recording.

**Revisit if** a run with 0 results turns out to be a legitimate outcome, or when the queued outcome tracking lands (a
cancel could then carry on). The rule is one check in `MetaController._run_finished_channel` plus its tests; telling 0 events
from a cancel or an error for Find needs the plugin's outcome (queued in `future_fixes.md`).

---

## 2026-11-04 - The Python floor is 3.12 with no cap, both ends of every range are tested, and 3.10 is out

**Context.** `requires-python = ">=3.12.10"` came from a README note that named no dependency (`7f8cbdeb`), and the
`ubuntu-24.04` image pin (added 2026-11-02, when `ubuntu-latest` moved to 26.04) existed only to keep installing
that patch. Measured on the full suite in a clean worktree of
`ce836c54` on Windows with the `requirements.txt` pins: 3.12.0 passed all but one test (`test_meta_model_generators`
asserted `getgeneratorstate` on a generator closed before it started, which 3.12.0 alone reports as `GEN_CREATED`);
3.11.18 passed with `typing.override` shimmed from `typing_extensions` (40 files import it); 3.10.22 failed two writer
tests (`SQLiteDBWriter.py:912` reads `sqlite_errorname`, added in 3.11); 3.13.18 passed. 3.14.10 cannot install the
pins (PySide6 6.9.0 is `<3.14`; numpy 2.2.6, scipy 1.15.3, matplotlib 3.10.3 and pandas 2.2.3 ship no cp314 wheel)
but passed on the `pyproject.toml` ranges (PySide6 6.12.0, numpy 2.5.4, matplotlib 3.11.2) once matplotlib 3.11's
RGB-tuple colour cycle was normalised at two sites and the static tripwire read class annotations through
`inspect.get_annotations` (PEP 649). `setup-python` builds 3.12.0 for Ubuntu 24.04 only; 26.04 starts at 3.12.13.

**Decision.** `requires-python = ">=3.12"` with no upper bound: the cap is enforced already by the dependencies'
own metadata and wheels, and a `requires-python` cap blocks every later interpreter until a release lifts it. Each
range's lower bound is the pinned version, so both ends are tested on every push: pinned legs at exactly 3.12.0
(`ubuntu-24.04`, `windows-latest`) and ranges legs at the newest supported interpreter (`ubuntu-latest`,
`windows-latest`) with `requirements.txt` not applied. `requirements.txt` stays exact; a pin and its lower bound move
together.

**Rejected.** 3.11: one import line in 40 files plus `typing_extensions`, no known user, and a convention to police
for the year 3.11 has left. 3.10: end of life October 2026, and the writer change on top. Capping matplotlib `<3.11`
instead of normalising two colour reads: it would keep 3.14 out for a two-line fix. Three-component `~=` ranges:
they would refuse the wheels 3.14 needs.

**Revisit** if a user turns up on 3.11 (an afternoon, by the measurement above), or when a ranges leg fails: the
fix is a tighter range for that one package, not an interpreter cap. The floor legs stay on `ubuntu-24.04` until
GitHub announces its retirement or `setup-python` builds 3.12.0 for a newer image.

---

## 2026-11-03 - A restored session keeps what each action's declared kind says it needs

**Context.** A tab's live history keeps every entry, because Undo replays from the last reset. A restore needs only
what the screen and the tab's results depend on now, and the rule has to hold for a contributor's tab too.

**Decision** (Carolina, 2026-11-02). Every `register_action` declares a required `kind` - `result`, `view`,
`additive` or `reset` - with the figure it acts on or, for a result, its plugin and channel parameters.
`build_kept_history` drops what later entries made irrelevant: an older run of the same result, a view or overlay its
figure no longer shows, an earlier reset of the same figure, and a view drawn from a result run again later (that view's
figure is left empty). Nothing of the declaration is saved in an entry. Clustering's run and merges are `additive`: a run
records a reset first, which ends the old run and its merges.

**Rejected.** Saving each entry's key (copies values already in `kwargs`, which can drift apart, and files saved before
it have none); a default `kind` (a forgotten declaration would keep or drop the wrong entries without a word); keeping
the overlays a Plot Events replaced (the same screen for two wasted queries).

**Revisit** if a tab gains a figure that a drawing both replaces and adds to, or a result that is not one plugin on one
channel.

---

## 2026-11-03 - A Find or Fit is recorded only once it finishes, and a rerun that does not finish removes the earlier run

**Context.** Each Find or Fit raises two separate questions: what the tab's *history* holds, which is what a restore
replays, and what the *channel* holds, which is the plugin's results. A run clears its channel as it starts. A Find or
Fit used to be recorded when it was clicked, so a run that was then cancelled stayed in the history and a restore would
have run it in full.

**Decision 1, the history** (Carolina, 2026-11-02). A click's values are held until `MetaModel.run_finished` says the
run ended. The tab then asks the plugin whether the channel holds a finished run (`get_eventfinding_status` /
`get_eventfitting_status`); since the run cleared the channel, the answer is this run's. If yes, the entry is recorded;
if not (cancelled, failed, nothing found), it is dropped and the status panel says so.

**Decision 2, keeping the two in agreement** (Carolina, 2026-11-04). Decision 1 alone opens a gap: a rerun that does not
finish is not recorded, but it has cleared the channel, so the earlier run's entry would describe results the tab no
longer holds and a restore would bring them back. So the tab also removes the earlier run of that plugin and channel
from the history, with every `view` whose `depends_on` names it, and the panel says so. This is an exception to the live
history keeping every entry; only Undo reads that, and no tab with a Find or Fit has Undo.

**Rejected.** Closing the gap from the plugin side instead: the rerun puts the channel's earlier results back, so the
earlier run's history entry stays true (built 2026-11-03, `f4cbcc67`). It turned out to be the enabler of a larger
change, so it was withdrawn and is queued in `future_fixes.md`, 3.2, "Keep a channel's earlier
results when a Find/Fit rerun doesn't produce results".

**Revisit both together** when that queued work lands. If a rerun keeps the earlier results, decision 2 must go (the
earlier run's history entry describes what the channel holds again, so it must stay), and decision 1 must ask how the
run ended rather than the channel status, which reads finished after a put-back even though the rerun was not.

---

## 2026-10-30 - Clustering records one reset per run, on the Controller, and no View records an action

**Context.** Clustering's reset was recorded on `ClusteringView._reset_actions`, inside the drawing a run or a merge
started; a 3-column plot recorded a second to switch projection, and a replayed run recorded its reset again (10
recorded entries replayed as 16; `test_a_replay_records_the_history_it_replays` pins it now). It was the last action
recorded on a View, so `MetaView.record_action` and the View half of `action_registry` stayed in use.

**Decision** (Carolina, 2026-10-30). A run records `ClusteringController.reset` before it draws, unless the last entry
is already a reset; the figure is cleared either way (`ClusteringView.clear_plot`). A merge and a 3-D projection clear
unrecorded. `MetaView.record_action` and the View half of the registry are removed; a static test fails a tab View
that declares an action. `MetaView.update_tab_action_history` stays: Metadata's Undo emits it.

**Rejected.** A reset before each merge (a reset ends what came before it, parting a merge from its run); no recorded
Clustering reset (the one tab without one); skipping the clear with the recording, as `ProteinController._start_figure`
does (it relies on the figure being clear whenever the last entry is a reset).

**Revisit** if a merge draws anything but the run's result, or a 3-D projection has to be replayed on its own.

---

## 2026-10-30 - Protein's Plot Events and Plot Histogram record no reset

**Context.** Both draw on the event page, which is neither mode's figure, and the tab's one history holds all three.
A probe showed the shared Undo, replaying from the last reset, leaves another figure's plot (and fit) in place.

**Decision** (Carolina, 2026-10-30). No reset for the event plots, and no per-figure Undo: Protein has no Undo button,
so nothing reachable replays its history partway. A replayed plot records its own reset only when the last entry is not
already one of its mode (`ProteinController._start_figure`), so a replay records the history it replays.

**Rejected.** The event page as a third figure with its own reset, and Undo per figure (both needed only by an Undo).

**Revisit** if Protein gains Undo, or when session restore's Go back resets a Protein tab: it must clear both modes' figures and fits.

---

## 2026-10-29 - The `event_id` question is asked on the click, never during a replay

**Context.** The question was asked inside the recorded overlay and Protein plots, after the entry had recorded the
filter as typed. A yes ran the new text but the history kept the old one, so Undo and a saved configuration asked again,
and each yes rewrote the tab's filter mid-replay.

**Decision** (Carolina, 2026-10-29). The click asks, through `MetaSubsetTabController._ask_event_id_for_raw_filters`,
running each raw filter once, then calls the recorded action with the text that runs. While replaying
(`ReplayGuard.is_replaying`) the offer is skipped and an entry still lacking `event_id` is refused with the usual message.

**Rejected.** Never asking during a replay but asking inside the action (replay refuses exactly the plots approved at the
click); asking during a replay (a modal mid-sequence that rewrites stored filters).

**Revisit** if running the filter once more on the click is too slow for a large database.

---

## 2026-10-29 - Protein's Update Plot is recorded on the Controller per mode, and its fits are the Model's

**Context.** The plot ran in `ProteinView`: its figures followed the mode showing, its fits lived on the View, an
Ensemble plot recorded two resets, and fields recorded for an overlay decision were never read.

**Decision** (Carolina, 2026-10-29). `update_individual_distribution` and `update_ensemble_distribution` on
`ProteinController` each draw on their mode's figures by name and record one `reset(axis_type, mode)`. The fits are
`ProteinModel.individual_fit` and `ensemble_fit`, read by Commit and Report All. The unread fields are deleted. The base's
scatterplot round trip goes; `set_scatterplot` stays for Metadata. A refused plot leaves figure, fit and history as they were.

**Rejected.** Switching the live mode before each replayed plot (a replay flips the page, and the reset still reads the
live mode); moving the unread fields into `OverlayState` (no decision reads them); fits on the View (a replay could not
rebuild what Commit reads); keeping the base round trip for a future subset tab (dead API the ratchets keep counting).

**Revisit** if a third mode is added, or the kept history needs one history per mode.

---

## 2026-10-29 - Metadata's Plot Events records a reset only when the history holds none

**Context.** Plot Events' clear of the figure is unrecorded, so Undo after it replays from the last reset and the
overlay it replaced comes back. With no reset in the history, Undo removed Plot Events and replayed nothing, leaving the
event grid drawn.

**Decision** (Carolina, 2026-10-29). `MetadataController.plot_events` records a reset before it draws when the history
holds none, after the events have loaded, so a fetch that loads nothing records nothing. Otherwise the clear stays
unrecorded. Every history then starts from a cleared figure, as the overlay's first-figure reset already ensures.

**Rejected.** Always unrecorded (Undo left the grid drawn); always recorded (replaying a saved reset and Plot Events
records the reset twice, as Plot Events did before this).

**Revisit** if Plot Events gets a figure of its own, or a saved configuration keeps only part of a history.

---

## 2026-10-28 - Every recorded value is saved under its parameter name, and replay checks an entry fits

**Context.** An entry saved its arguments as called, so a saved file showed bare values in order.

**Decision.** `register_action` binds each call to the method's signature and saves every value by name, defaults
filled in, in every tab. Replay binds a saved entry before calling it, and reports and skips one that no longer fits.
*Settled 2026-11-09: a file saved before this, or by 2.0, is refused whole at Load Plot Configuration.*

**Rejected.** Saving positionally (unreadable); converting old files now (the saved-history format changes again).

**Revisit** when the saved-history format is next changed.

---

## 2026-10-28 - Metadata's overlay is decided on the Controller and kept by the Model

**Context.** The loop, its reset-or-add decision and its bookkeeping lived in `MetadataView`, which handed the
Controller the plot's `Axes`; a recorded action could not be checked or replayed without a figure.

**Decision.** `MetadataController.overlay_plot` runs the loop and the View only draws. What the figure holds is an
`OverlayState` on `MetaSubsetTabModel`, its kind (empty, overlay, event grid) included. The recorded reset is
`MetadataController.reset`. An empty figure records a reset before its first dataset unless it was just reset, so
every history replays onto a cleared figure.

**Rejected.** A recorded Controller method over the View's loop (seven slots kept taking the `Axes`); the state on
`MetadataModel` only (Protein holds the same fields, so it would move again); a View query for whether the figure can
take a plot (a recorded action would read View state, which the replay static test forbids).

**Revisit** if a figure can change without the Model being told: the decision reads only the Model's figure kind,
which Plot Events sets to the event grid.

---

## 2026-10-27 - Clustering's result lives in the Model; how it is drawn stays in the View

**Context.** Recording Merge meant giving it a Controller method. It mutated `ClusteringView.cluster_data`, a frame the View held, and Commit sent that frame from the View. A recorded run also had to tell whether it produced anything: `cluster` runs inside the View's emit and reports its own failure, so `load_metadata_for_clustering` could not see it.

**Decision** (Carolina, 2026-10-27). The result, (frame, labels, confidence), is `ClusteringModel.result`. `ClusteringController.merge_clusters` folds labels there (new arrays) and asks the View to redraw; Commit takes the rows from `ClusteringModel.cluster_columns()`, so `cluster_commit_requested` lost its frame. The recorded run is recorded only when a new result reached the Model. The display flags (`logs`, `normalized`, `plot_units`, `plot`) stay on the View: they say how to draw, `update_plot` sets them from the run's own arguments, and the Controller never uses them. `update_plot` draws a copy of the frame it is given, because it writes the label columns into it; that is the one point both a run and a merge pass through. `cluster` keeps taking the loaded rows: it is not recorded, and changing it would remove `cluster_requested` for no replay gain.

**Rejected.** A thin Controller method calling today's View merge (smallest, no breaking signal) left the replayed logic and the result in the View. Copying only in the merge redraw missed the first run.

**Revisit if** another caller needs the display flags (move them to the Model then), or a run must be recorded before its clustering finishes (the success test reads the Model after the emit returns, which relies on the same-thread connection).

---

## 2026-10-26 - A recorded Event Analysis fit carries no loader

**Context.** `request_fitting_statuses` refuses a fit when the loader selected in the tab is not the one the fitter was built on, once, before any channel starts (`EventAnalysisController.py:473`). The recorded fit (`fit_events`, `fit_channel`) could carry the loader and repeat that check.

**Decision** (Carolina, 2026-10-26). `fit_channel` takes the fitter, the channel and the filter key only. The loader check stays on the click path, where the loader is selected.

**Why.** A fitter reads only its own loader, so the selection never changes what a fit computes (`MetaEventFitter.fit_events` uses `self.eventloader`, `:558`, `:570`, `:587`; `DECISIONS.md` 2026-10-20), and `fit_channel` never reads a loader. The check guards what the user is looking at against what the fitter reads, so a recorded loader could only repeat it with the old selection and would not change what runs. `plot_events` does carry the loader because a plot reads the selected loader's events.

**Revisit if** a replayed entry can run a fit under a fitter key whose fitter now sits on a different loader than when it was recorded: the replay would then fit a file the original did not. The Edit dialog cannot cause it, because it disables the source-plugin dropdown when editing (`DataPluginController.edit_plugin` passes `editable_source_plugins=False`, `dict_dialog_widget.py:190-193`). Deleting the fitter and creating another under the same key can; deleting a plugin is meant to drop the recorded entries that name it, which closes it once that is built. If it is not, record the fitter's loader and refuse on replay when it differs.

---

## 2026-10-26 - Event Analysis's replay scenario does not exercise `raw`

**Context.** `load_event_plot` (recorded as `plot_events`) takes `raw`, which overlays each event's unfiltered trace. It changes the plot only when a filter is selected. The behavioural replay scenario (`test_replay_guard_no_gui.py`) runs with "No Filter", because no filter plugin is registered in `build_event_analysis_tab`, so changing the raw checkbox in the second tab changes nothing the scenario compares. The scenario therefore cannot tell a replay that uses the recorded `raw` from one that reads the checkbox or ignores it.

**Decision** (Carolina, 2026-10-26). Leave it. The scenario stays without a filter plugin and `raw` is not exercised by it.

**Why.** Each plausible mistake is caught by another layer, measured by mutation on 2026-10-26. Reading `raw` from the checkbox: killed by the static test and by the unit tests, survived the scenario. Ignoring the `raw` argument (a constant `False`): killed by the `TestLoadEventPlot` raw tests, survived the static test and the scenario. A filter plugin would add setup (a registered filter, its callable and its samplerate declaration) to cover one checkbox that matters only under a filter, which the cheaper layers already cover.

**Revisit when** any of these holds, and then register a filter in `build_event_analysis_tab`, plot with it in the scenario with `raw` true, and set `raw` false in the second tab:
- the `TestLoadEventPlot` raw tests are removed or weakened, so that no layer asserts `raw` drives the unfiltered overlay;
- a bug is reported where a replayed Event Analysis plot shows the wrong overlay;
- another recorded argument turns out to matter only under a filter, so the same blind spot appears twice;
- the scenario gains a filter plugin for another reason, at which point `raw` costs nothing to add.

---

## 2026-10-26 - A finder run that finds no events reports it, and the channel stays unfinished

**Context.** `MetaEventFinder.find_events` ends a run with no events by calling `reset_channel`, so the status report read "event finding incomplete" for a run that completed, the same as an abort (seen after a Find over a short range with no events). `get_eventfinding_status` gates Plot Events and Start over. The writer skips a channel that reports no events (`MetaWriter.py:432`), and an unfinished channel reports 0 (`get_num_events_found`), so an empty run commits nothing for it; this entry does not change that.

**Decision** (Carolina, 2026-10-26). `MetaEventFinder.no_events_found[channel]` is set after the reset when a completed run found nothing, cleared by the next `reset_channel`, and `report_status` says "no events found". The finished flag stays False, so nothing that gates on it changes.

**Rejected.** Counting an empty run as finished with 0 events: Plot Events would say "No events to display", but "finished" would then mean something different to every reader of it (Start over would ask on an empty channel; loaders and finders would need rechecking), for what is a message fix.

**Revisit.** If a caller needs to tell an empty run from an abort without parsing the report; `RawDataController.load_event_plot_data`'s "No events to display" branch stays unreachable while the flag is False for an empty run.

---

## 2026-10-26 - A recorded call that did nothing is not recorded

**Context.** Raw Data's Update Trace, Update PSD and Plot Events return early when the reader has nothing to plot, and Find can be refused or fail to launch. A decorator that records on entry would put those no-ops in the history, and replay would repeat them.

**Decision** (Carolina, 2026-10-26). `register_action(name, skip_on_false=True)` records only if the method did not return a literal `False`; the four RawData methods return `bool`. Opt-in, so existing actions keep recording unconditionally. Find is recorded per channel (`find_events_on_channel`) with its Timer limits, because a replayed entry has no batch loop around it.

**Rejected.** Raising on refusal (changes what the click path sees); recording first and pruning later (history briefly lies); checking the result in each caller (every caller must remember).

**Revisit.** If a recorded method needs to report more than done/not-done.

---

## 2026-10-26 - A recorded action reads no widget: a tripwire, a static test and a behavioural guard

**Context.** 2026-09-17 rule 5 (a recorded action is a pure function of its arguments) was met by
hand for two plot methods and enforced by nothing; Protein's recorded reset still read the live mode.

**Decision.** Three checks, built before any new action is recorded. (1) `ReplayGuard.py`: the seven
widget-reading helpers raise `ReplayWidgetReadError` inside `MetaController.replay`. A module, not a
per-View flag, because five of the helpers are the controls panels' `collect_parameters`, which hold no
reference to a View or Controller. (2) A static test walks each declared action and its callees (a
Controller action into its View, a property into its getter) and fails on a widget-value call, a panel
helper, a `*controls` attribute, widget-derived state or an `Axes`/array parameter; a known exception goes
in its `ALLOWED` table with the condition that removes it. (3) A behavioural flow records each action in
one tab and replays it into a second, perturbed tab, comparing plugin calls, plot cache, figures and
bookkeeping; a declared action with no scenario fails. Protein's reset stops clearing fits and each plot
action clears its own: a `mode` argument was rejected because the compliance test audits `_reset_actions`'s
signature against `MetaView`'s, and no caller needed it.

**Evidence.** 5 mutations killed (restoring the mode branch; dropping the `replaying()` wrap; dropping one
helper's guard call; the Metadata overlay reading the live filter selection, and the bins field). The
tripwire cannot see a direct `.text()`; the static test does.

**Known gap, recorded not fixed.** Protein's figures are properties that pick the Individual or Ensemble
figure by the live mode, so a plot recorded in Ensemble and replayed into an Individual-mode tab draws on
the wrong figures. The two Protein actions are in `ALLOWED` and a strict `xfail` pins it.

**Revisit** when replay writes the recorded mode back before it runs an action: remove the `ALLOWED` entries
and the `xfail` marker. *Closed 2026-10-29: Protein draws on each mode's figures by name, and the `ALLOWED`
entries and the `xfail` are gone (see that entry).* *Measured 2026-11-12: a replay writes each step's recorded values
into the panel before it runs, so the behavioural guard cannot see a step that reads the panel; Conditioning reading its
bands and fit range from the panel survived it and was killed by the static test. The guard keeps an explicit list of
the tabs Poriscope ships with, Conditioning added (Carolina, 2026-11-12); finding every tab instead was rejected, since
nothing enforces a tab's behaviour tests and it would make a contributor's tab need replay scenarios.*

---

## 2026-10-25 - A recorded action is declared on the Controller, and replay is dispatched by the Controller

**Context.** The 2026-09-17 rules had replay run on the View. Kyle proposed that a new tab
integrate by decorating Controller methods, so recording moves to the Controller. Only a
function that is a pure function of its arguments may be decorated: one that reads no frontend widget
(`DECISIONS.md` 2026-09-17, rule 5), which is what makes a Controller the right home for it.

**Decision.** `@register_action("name")` goes on Controller methods and records through
`self.record_action(entry)` (`MetaController` appends to the tab history; `MetaView.record_action` keeps the
old View path for the 5 View methods until their tab converts). One registry per tab, built from the
declared methods of the Controller, and during the transition of its View, serves replay, Undo and Load
Plot Configuration; a duplicate name raises, and an unknown name or an old-format entry is reported on the
status panel, not called. Undo finds resets by `RESET_ACTION = "reset"`. *`MetaView.record_action` and
the View half of the registry were removed 2026-10-30: no View records an action (see that entry).*

**Evidence.** The old decorator recorded by emitting a signal named `update_tab_action_history` on the
decorated object (`LogDecorator.py`); `MetaController` has a signal of that name that sends the whole
history to the main window, so decorating a Controller method would have sent it a malformed message.

**Revisit if** a recorded Controller method has to take data rather than intent (2026-09-17 rule 4).

---

## 2026-10-25 - After a load, a dialog replays the tabs the user ticks

**Context.** 2026-09-27 kept replay a per-tab step, with no "replay everything". Since 2026-11-09 a load hands each
tab its saved actions, and Replay Actions replays one tab at a time.

**Decision.** After Load or Restore Session, a dialog lists every tab with actions to replay, all ticked; Replay starts
the ticked tabs at once, each its own replay, and every tab keeps Replay Actions. It opens last, over the tab the user
lands on, and says that replaying commits, exports and saves nothing. `MainView.ask_which_tabs_to_replay` returns the
ticked pages, so no signal was added. The two rules of 2026-09-27 still hold: a control's options never depend on
replayed state, and no tab's replay needs another's. The one cross-tab source, an Event Analysis fitter's event
loader, reads a database on disk (`SQLiteEventLoader`, the only event loader), and a replay redoes no commit.

**Rejected.** A yes/no "restore the state as well?" (no choice of tabs). A File-menu item of its own (two ways to load
one session). Replaying without asking (it can take long).

**Revisit if** a tab's replay comes to need another tab's results in memory, or replays must run one tab after another.

---

## 2026-10-20 - The Event Analysis commit is not gated on the selected loader; fitting and plotting are

**Context.** A guard added on 2026-10-10, in no release, made
`EventAnalysisController.write_events` refuse a commit when the selected loader was not the one the
writer's fitter was built on, alongside the same check on fitting and on plotting fits. A user
(Nada, 2026-10-20) found it blocked writing one fitter's results while looking at another loader's
events, which is a routine thing to do.

**Decision** (Kyle, 2026-10-20). The commit guard is removed, with the loader argument it needed on
`write_requested` and `write_events`. The fitting and plotting guards stay.

**Evidence.** A writer reads its fitter, which reads only its own loader, so the selection never
changes what a commit writes; the guard only stopped the user. A plot takes its traces from the
selected loader and its fit from the fitter, so a crossed plot draws one file's fits over another's
events. A fitter also fits its own loader whatever is selected, so the fit guard protects what the
user believes was fitted, not what is computed: on two synthetic events databases with one CUSUM
built on the first (2026-10-10), a crossed Fit Events raised `No samplerate found for channel 1`
when only the selected loader had the channel, and when both had channel 0 it fitted its own
loader's 5 events while the screen showed the other's 2, with the "start over?" prompt describing
the fitter's file. A channel the writer's fitter has not fitted is still reported and skipped per
channel.

**Why a crossing is explained, not prevented** (ruled 2026-10-10). A crossed plot draws the traces,
which are valid, without fit overlays and names the fitter's loader on the status panel; refusing
the whole plot was rejected because the traces are right. A crossed fit is refused before any
prompt, and so is a fitter whose loader cannot be read. Listing only the fitters built on the
selected loader would remove the cases at the source, but needs View and controls work and a way
to plot with no fit; it is queued in `future_fixes.md`, unscheduled.

**Revisit if** a writer ever takes the loader from the tab rather than from its fitter's parents.
Dropping the fit guard as the commit guard was dropped needs an answer to the silent case above.

---

## 2026-10-17 - A loaded session shows the tab the user last acted in

**Context.** After a load, the page showing was the tab restored last, an accident of restore order. The user is left
where they were when the session was saved, not moved as replays start.

**Decision** (Carolina, 2026-10-17). The session saves `last_tab`, the tab whose history last changed, and a load
shows it. *Settled 2026-11-10:* a change the user did not make leaves it alone. Every replayed step records itself, so
after the restore dialog replays several tabs, whichever finished last - a background Find, say - would become the
last tab by timing alone, and a plugin delete, rename or edit would move it to the tab whose entries it rewrote. A
replay the dialog starts is marked (`start_replay(restore=True)`); the tab says whether a change is that replay's own -
its start, a step, or the run it waits for (`MetaController.history_change_from_restore_replay`) - and the main window
leaves `last_tab` alone for those, and while plugin changes rewrite the tabs. Undo, a plot by hand, Replay Actions,
Load Plot Configuration and Go back still move it. Measured 2026-11-10 on real tab Controllers: nine cases
(`tests/unit/controllers/test_last_tab.py`).

**Rejected.** The view following replays as they start (they start together; there is nothing to follow). A list of
the dialog's tabs in the main window, dropped at the user's first change (the rest of that replay then moved it back).
Every change during a restore replay counted as the replay's (Undo and plots by hand would not count). The page
showing when the file is written (where the user looked, not what they did).

**Revisit if** another kind of change is made for the user rather than by them.

---

## 2026-10-17 - Go back clears every tab's state, and rebuilds the history from before the replay

**Context.** When a replay stops on a failed step, the user can Go back. By then the replay has redrawn the figure,
changed the tab's own state and may have finished runs on channels, so the tab has to be put back as it was before the
replay started.

**Decision.** Each tab clears its state through `MetaController.clear_for_replay`: the default clears the figure (Raw
Data, Event Analysis); Metadata also forgets what the figure held, Clustering drops `ClusteringModel.result`, Protein
clears both modes' figures and both fits. Go back resets each channel a run of the replay finished, then replays the
history from before the replay through the sequencer; if that fails, the tab is left cleared with an empty history and
the panel says so.

**Rejected.** Clear only, without rebuilding: the user loses the state they had before the replay.

---

## 2026-10-17 - A replay shows each step's recorded values in the panel, not a snapshot of the widgets

**Context.** After a restore, a tab's panel has to show something: what the user last typed, what the panel showed
when the session was saved, or the values the replayed result was made with.

**Decision** (Carolina, 2026-10-17). Before each replayed step runs, the View writes that step's recorded values into
the panel and into the inputs a dialog or button stores (`MetaView.write_back`, called by `ReplaySequence`): plugins,
channels, ranges, filters, plot settings, Find's Timer limits, the scope, Protein's mode, Clustering's settings. So
the panel never disagrees with the plot, and the next click starts from what produced it. Write-back only writes,
with signals held off; the step runs on its recorded values, never on what was written. A value that is no longer
an option is skipped and said on the status panel.

**Rejected.** A snapshot of each panel's widgets saved with the session: it can disagree with the replayed plot, and
needs every control to carry an `objectName` (kept in `future_fixes.md` only for a tab the user does not replay).
Leaving the panel as the user had it: the next click would not start from what drew the screen.

**Evidence.** A manual pass on 2026-11-10 found `write_back` was never called; `0bfa4afb` calls it on every step,
tested on real tabs in `tests/integration/flows/test_replay_writes_back_no_gui.py`.

**Revisit if** a recorded value has no widget to show it in, or a session must restore a tab it does not replay.

---

## 2026-10-17 - A replay runs one step per turn of the event loop, and waits for each Find or Fit

**Context.** The old replay was one synchronous loop on the GUI thread: the window froze, a Find or Fit started a
worker and the next entry ran before it finished, and several tabs could not replay at once.

**Decision** (Carolina, 2026-10-17; how it hears a run end, 2026-11-05). Each tab replays through its own
`ReplaySequence` (`MetaController.start_replay`). Each step is scheduled with `QTimer.singleShot(0, ...)`, so the
window stays responsive and tabs' sequences interleave. A step whose action is a `result` waits for its own run's
`MetaModel.run_finished`, and one whose plugin and channel already have a run going waits that run out first. When a
step fails the replay stops and asks Go back or Keep (2026-11-05, 2026-10-17). Undo keeps the synchronous
`MetaController.replay`: it replays only Metadata's plots, which hold no Find or Fit. *Extended 2026-11-12: any
other step that starts background runs waits for every run it started (not runs already going), and ends a turn of the
event loop later, so the tab has drawn before the next step. Still runs of its own tab, so the revisit below does not
apply.* *Superseded 2026-11-17 for runs: waiting for each run was there so that no step ran before the run it reads
had finished, not to keep runs apart, but it also made independent runs start one after another, which a click does
not. Independent runs now start together; see that entry.*

**Rejected.** `record_finished_run` telling the sequencer when it ends (two jobs in one slot); a sequencer slot on
`run_finished` that runs the next step inside the emission (depends on connection order); polling `model.workers`
with a timer; a worker thread for the replay (the steps draw on the GUI).

**Revisit if** a step must wait for something other than a run of its own tab, or replays must run one tab after
another.

---

## 2026-10-16 - A plot offers to add `event_id` to a plain raw filter; a raw filter is never rewritten silently

**Context.** Event plots, Plot Events, the arrows and the export need each raw result row to name
an event by `event_id`. A filter written for a histogram usually lacks it, so the plot refused and
the user had to edit the filter. Needing `event_id` is a Poriscope requirement, not an SQL one: a
viewer never asks for it, so a user cannot know it from the SQL they write.

**Decision** (Carolina, 2026-10-16). When a plot needs `event_id`, the result lacks it, and the query is a plain `SELECT`
from `events` or `sublevels` (no top-level `DISTINCT`, `GROUP BY`, aggregate, `UNION`, `WITH`, join,
comma join, derived table or `SELECT *`), `MetaSubsetTabView.offer_event_id` asks, showing the new
text. Yes changes the filter in the tab (the session keeps it; Save Filter writes the file) and the
plot carries on; the filter is put back, with a line on the panel, if the new query fails. No is
closed without a change, and asked again the next time a plot needs it. Any other query gets a message naming the word that stops it, and a
top-level `GROUP BY` or aggregate that returns `event_id` without grouping by the event is warned about. The
offer is made because, in most cases, adding `event_id` has no consequence and a little help with a
Poriscope-specific rule is cheap.

**Rejected.**
1. *Adding `event_id` automatically.* It needs a SQL parser, and it changes results: `DISTINCT`
   changes rows, and a bare `event_id` beside `GROUP BY` or an aggregate is one arbitrary event per
   group. It also breaks "runs as written".
2. *A token such as `{event_id}` filled in per plot.* One saved filter would return different rows
   per plot (`SELECT DISTINCT {event_id}, duration`: 5 rows in a histogram, 6 in Plot Events on the
   example data), it does not run in a viewer, and a column plot ignores `event_id` anyway, so the
   user still has to write something at the start of the `SELECT`.
3. *A button in the filter dialog.* It is a reminder before the problem exists, when the user cannot
   see why they need it; help should arrive when it matters.
4. *Notes for column plots on `DISTINCT`, `GROUP BY` and `UNION`, and a "repeats events" warning.* A
   viewer shows the same rows, and both fire on correct queries (`SELECT DISTINCT e.event_id`, a
   sublevel histogram).

**Evidence.** Keywords are read at bracket depth 0, outside strings and comments, so a `GROUP BY` in
a subquery or `COUNT(DISTINCT x)` is not counted. Assisted cannot hit any of this: it writes one row
per event itself (`SELECT DISTINCT e.id, ...` for a sublevel condition).

**Revisit if** Accepting the offer starts breaking users' queries, or users want `event_id` on
every filter and find the question tiresome, or `DISTINCT`, `GROUP BY`, `UNION` and aggregates turn
out to be common in raw filters.

---

## 2026-10-16 - The filter dialog teaches by an example in the empty box and an info icon, not a label

**Context.** The Raw SQL hint ("add `WHERE experiment_id = :experiment_id AND channel_id =
:channel_id`, start with `SELECT event_id`") was a three-line label that took space in every dialog
and stayed after the user knew it.

**Decision** (Carolina, 2026-10-16). The empty filter box shows a grey example for the chosen mode (a condition for
Assisted, a scoped query starting with `event_id` for Raw); Tab in the empty box inserts it. An info icon beside each mode's radio
button carries the rule in a tooltip and points to the guide (Help > Help > Documentation, then User
Guide > Filtering and Querying). The icon is drawn from `info-circle.svg` through `get_icon`, tinted
for the theme and rendered at 64 px so it stays sharp on a high-resolution screen.

**Rejected.** The label (space); a placeholder alone (it disappears as soon as the user types, which
is when the rule matters); an "Add event_id" button (see the 2026-10-16 entry on the `event_id` offer).

**Revisit if** Users still write unscoped raw filters at the same rate: then a persistent line is
worth its space again.

---

## 2026-10-16 - A raw filter's name travels with its text through the subset signals

**Context.** A raw filter is told from an Assisted one by its `_raw` name, and the Controller has to
run it itself: bind the placeholders for each pair, check the result, warn and ask by the filter's
name, and write an accepted `event_id` back to that filter. The subset and event request signals
carried only the filter's text, which is all the Assisted path needs, because the loader builds the
whole query. Protein carried this idea until 2026-09-12: `event_distribution_data_requested` took a
`subset_name` whose `_raw` suffix picked a separate route for raw filters. The argument was sound;
the route it fed never worked, because it passed a complete `SELECT` to `load_event_data` as a
WHERE-clause body, and the 2026-09-12 entry removed both. The name travels again, this time with a
Controller that runs the query itself.

**Decision** (Carolina, 2026-10-16). Seven signals gained the name as a trailing `str`:
`event_id_cache_requested`, `all_points_histogram_requested`, `event_overlay_requested`,
`metadata_subset_requested`, `csv_subset_export_requested`, `event_distribution_data_requested` and
`ensemble_histogram_requested`, with their slots, `_fetch_event_subset` and `_rebuild_event_id_cache`.
Each signal is one declaration, one emit and one connect, plus its slot. Listed as breaking in the
changelog.

**Rejected.** Sniffing the text for `SELECT`: the mode is fixed by the name's suffix when the filter
is created, so the text would be a second source that could disagree with it. (A one-column `SELECT`
was accepted in Assisted mode when this was decided, which made the text ambiguous; an Assisted filter
that starts with `SELECT` is refused now, but the name stays the one source.) Looking the name up in the
View's filters from the Controller: it reaches into View state where the convention is arguments, and
identical texts under two names are ambiguous. A one-entry `{name: text}` dict in place of the text:
it changes an argument's meaning, breaks as much and reads worse. A default value on the Python
methods: Qt signals have a fixed arity, and an old caller would silently treat a raw filter as
Assisted.

**Revisit if** someone subclasses `MetaSubsetTabView` or `MetaSubsetTabController` outside this repo
(today only the Metadata and Protein tabs do). Then carry the mode and name in one small value passed
unchanged, so the next addition does not change every signal again.

---

## 2026-10-14 - The milestone guard names a non-dedicated tab's page as `<Name>View`; no `view_class` declaration

**Context.** `on_load_analysis_tab_button_click` must name the page a tab will open before the tab is built, so a
refused click builds and saves nothing. A controller builds its view inside `__init__`, so before that only the
controller's name is known. The plan's "Plugins" is a sidebar-highlight key, not a page, and would have refused the
tour's own Clustering step.

**Decision.** Guess the page from the controller name (`ClusteringController` -> `ClusteringView`). Reason (Carolina): the
tabs shipped with Poriscope have a naming convention, as Python has its own; Poriscope would never name a tab's view,
controller and model differently, and each is always named with the word View, Model or Controller. It is a convention for
the tabs we ship, not for external ones. A test, `tests/unit/plugins/test_analysis_tab_naming.py`, checks every shipped
tab follows it, and `ready_to_build/index.rst` states it.

Rejected: an optional `view_class` on `MetaController` (base change plus generator, five tabs and the compliance test); a
base class that builds the view and model (breaking, every `_init`); refusing only when the milestone expects one of the
three dedicated views (fails open - a custom tab's walkthrough has no expected view, so the tab is built and then
refused); building the tab first and checking after (the bug).

**Evidence.** The five shipped controllers redeclare `view: XView` and `model: XModel`, and the generator writes the
pattern. The loader dedups only the controller's class name (`main_model.py:269-283`); the generator checks all four
(`new_plugin.py:1687`). The convention is not enforced for user tabs, so a wrong guess there is possible but narrow, found
by reading the code and not run with a user-folder tab: milestones only expect built-in views, a user view reusing a
built-in view's name would have a legitimate click refused, and a user controller reusing a built-in name loses the
loader's name collision.

**Revisit.** If a shipped tab breaks the convention or a user tab hits a milestone. Then read each controller's
`view:`/`model:` annotations with `typing.get_type_hints`; queued in `future_fixes.md`.

## 2026-10-14 - A contributor tab's walkthrough does not chain to other tabs

**Context.** `get_expected_next_view` is a fixed table (Main -> RawData -> EventAnalysis -> Metadata -> Clustering), so
a tab outside it has no expected next view and, while its walkthrough runs, every page switch, the Settings page, the
analysis-tabs list and the Help window are refused until it ends.

**Decision.** Keep it. Tabs added by contributors are for specific users, not part of the core workflow, so they should
not take part in the tour. The walkthrough ends on its last step's Done or the dialog's X; Esc only flickers the dialog,
and Alt+F4 closes the app. Documented in `adding_walkthrough.rst`.

**Evidence.** Probe with a stand-in tab and the 2026-10-14 manual runs. A bare `dialog.close()` skips `done_signal` and
would leave the block on, but no user route reaches it, so it is not queued.

**Revisit.** If contributors need a walkthrough that continues into another tab.

---

## 2026-10-13 - Plot-data export writes whole-number columns as integers; 1.9.0's `1.0` form is not restored

**Context.** 2.0.0 changed `format_cache_data` to pad with `None` and let pandas infer each column, so
categorical histograms could export. Its changelog line says "Numeric exports are unchanged", verified
byte for byte on float arrays only. Whole-number arrays now write `1` where 1.9.0 wrote `1.0`.

**Decision.** Leave it. Restoring the float form means per-column type handling, in the code that crashed on text
categories in 1.9.0, and would change every export including those that are correct. The repeated time and
frequency columns stay, as in 1.9.0.

**Evidence.** Whole-number arrays `[1,2,3]`/`[4,5,6]`: 1.9.0 `1.0,4.0`, now `1,4`. Uneven lengths give `1,4.0`
in one file because the padded column reads as float. Seen in a real scatterplot export: `event_id` printed `0`
beside `0.0` in the same row. 0 of the 11 original cache-export tests used an integer array, so none pins either
form. Values are equal and any CSV reader parses both.

**Revisit if** (1) a user's pipeline breaks on `1` vs `1.0`; restore floats for numeric columns only, text kept as text.
(2) Anything starts comparing exports across versions byte for byte. (3) Repeated identical x columns are
deduplicated on purpose; compare values, not labels, since overlaid datasets share labels.

---

## 2026-10-10 - `format_axis_label` appends a unit; it no longer replaces a different one

**Context.** Three copies (`ProteinView` function, `MetadataView` method, `ClusteringView` inline) stripped
a trailing `(...)` before attaching the unit, which truncated a column named `Rate (per pore)` to `Rate (Hz)`.
A tighter regex cannot fix it: `Rate (per pore)` and `Duration (us)` are both `word (word)`, and no registry of
units exists (the `columns.units` text is free-form, including `" "`).

**Decision.** One `MetaView` `@staticmethod`: append `" (unit)"`, except when the label already ends in that exact
suffix. Replacing a *different* unit on relabel was dropped.

**Evidence.** 0 of 20 call sites (12 `MetadataView`, 8 `ProteinView`) pass the function's own prior output;
all pass a raw column name. No shipped or in-app-written column has parentheses (the Clustering and Protein writers use fixed
names), so the truncation had no in-app trigger; `add_columns_to_table` still accepts any name.

**Fixed anyway, though not user-facing.** The behaviour change is about 3 lines of logic and about 60 lines
once its tests and records are counted; the rest of the branch (about 140 insertions, 150 deletions) is the
merge of three copies into one, with the import and call-site changes, the whitespace-check unification, the
new Clustering test and the baseline update. Dropping the change would have saved almost no code, and would
have left Clustering to either keep its inline copy or gain the truncation.

**Revisit if** (1) a caller starts re-labelling an already-decorated label with a different unit; carry the bare
name and unit separately rather than re-parsing the string. (2) A column name with parentheses becomes reachable
in the app (a user-nameable derived column, a database importer): the no-in-app-trigger premise is gone, so decide
whether `Duration (us) (ms)` is acceptable. (3) A registry of valid units appears, which would allow a precise
strip-and-replace.

---

## 2026-10-09 - The Raw Data baseline readout shares the finders' fit through `@staticmethod`

**Context.** `RawDataModel.get_baseline_stats` kept a pre-2026-09-20 copy of the baseline fit
(linspace bin centres, `argmax` peak, quarter-Rice bins), disagreeing with Ruling D's fit. The
2026-09-19 "shared code goes on the family's `Meta*` base" ruling covers duplication inside the
finder family; this is a second, unrelated consumer (an analysis-tab Model) of the same math.

**Decision** (Carolina, 2026-10-09). `MetaEventFinder._fit_baseline_histogram` and `_gaussian_fit`
are `@staticmethod`s - both touch no instance state - and `RawDataModel` calls them on the class
over the chunk's own min/max, as `ClassicBlockageFinder` does unbounded. No helper module, and no
plugin-call channel (`MetaModel.call()` refuses private methods). The fit returns `(mean, std)`, so
the never-read `amplitude` was dropped from `get_baseline_stats` rather than re-growing the shared
contract for one caller.

**Evidence.** The seeded sweep's sigma moved from 15.59/5.19/20.90/1.07/2.13 to
15.01/4.99/19.99/1.00/2.00 for true 15/5/20/1/2. A 57%-occupied window read Mean -0.11 nA, Std 1.90
nA before (the occupied level) against a true baseline near -4.2 nA.

**Revisit if** a third consumer needs more than these two helpers, at which point a shared module
beats widening `MetaEventFinder`'s statics. A test pins `get_baseline_stats` to the shared fit
bit for bit.

---

## 2026-10-09 - Subset-tab arrows treat an Event ID past every filtered id as just past the end

**Context.** Promoting `_shift_range_and_update_plot` to `MetaSubsetTabView` forced one rule for
an `event_id` with no cached id at or after it (`bisect_left` returns `n`). Metadata clamped the
position to `n - 1`, Protein reset it to `0`; both then stepped, so each skipped an event on one
arrow. With ids `[0, 3, 5, 7]` and Event ID 99: Protein right -> 3 (skips 0), Metadata left -> 5
(skips 7).

**Decision** (Carolina, 2026-10-09). The rule is that the Event ID field snaps to the nearest
filtered event at or after the requested ID. Past every filtered event there is none, so the
position stays at `n`, just past the end: right -> 0, left -> 7, nothing skipped, and nothing is
reported, since reaching the first or last event is ordinary wrap-around. Both rejected rules skip
an event. Plot Events and Plot Histogram snap the same input to the first id - they plot from a
position rather than step from one - and say so on the status panel (`_snap_to_filtered`), since
the plot then starts somewhere other than the entered id.

**Revisit if** navigation gains a mode where "past the end" should stop instead of wrap.

---

## 2026-10-09 - The ABF readers on pyabf: one general reader, offsets added after the gain

**Context.** Ruling H (Kyle, 2026-10-06) moved the ABF readers off the hand-written `ABF2Header` parser
(since deleted), correct for the lab's files but specific to them, onto the maintained `pyabf`, as one
general plugin plus subclasses for the lab's file families. A spike on 13 real files agreed to 3.6e-12 pA.

**Decision** (Kyle, 2026-10-09).
- `ABFReader` opens any file `pyabf` opens (ABF1/ABF2, int16/float32, gap-free/episodic). Settings:
  `Current Channel` (default 0) and `Sweep` (-1, the default, reads every sweep back to back; a
  single sweep of a variable-length event-driven file is refused). A subclass fixes a setting by
  deleting its key, which then takes the default; there is no hidden-setting mechanism.
- `TCossaLabABFReader` and `LegacyElementsReader` stay, as subclasses adding only the file-set
  methods; Legacy is kept rather than collapsed so saved sessions and scripts naming it still load.
  Their ADC-count and `"I"`-name checks are dropped for the base's check that the channel records a
  current; an unknown unit, which `ABF2Header` read as pA, is refused.
- Offsets are added after the gain, as `pyabf` applies them. `ABF2Header` folded them into the scale
  (a 2026-10-05 ruling had called that form correct); no real file has a non-zero offset, so no
  recording moves either way.
- The rate is 1e6 over the header's float interval (ABF2 `fADCSequenceInterval`; ABF1
  `fADCSampleInterval` x channels). That and the gain, offset and dtype come from `pyabf`'s private
  attributes (`_protocolSection`, `_headerV1`, `_dataGain`, `_dataOffset`, `_dtype`): the public
  `dataRate` is an `int` (6666666 for 6666666.401757145). Held by `pyabf>=2.3.8,<3`.
- The reader memmaps the data itself: `pyabf`'s `abf.data` is float32 and loads the whole file
  (1.8e-3 pA off at 14 nA; 3.2 GB for the Legacy file). `ABF.getOnlySweep` (swharden/pyabf#138) is
  unreleased and reads float32 with the integer rate, so it is not used either. The memmap covers
  exactly the header's point count, and a shorter file is refused by name: an over-long map raises
  `OSError` (WinError 8) on Windows, which the old wrapper reported as a sync issue.

**Evidence.** Before this change `pyabf` could not open the synthetic ABF2 fixtures (four header
fields were missing or wrong). On all 376 ABF files on the second machine (12 sets, including the
16-channel e16 sets in uA) `ABFReader` matches `ABF2Header`'s conversion bit for bit: rate, length,
and the first and last 200,000 samples; every offset is zero, so the offset change moves no recorded
file; the stitched sets read identically across file boundaries. `test_real_recordings.py` passes on
the two recordings present there.

**Revisit if** a `pyabf` release renames those private attributes, or a recording reads differently
from what the acquisition software shows. `LegacyElementsReader` has since been run on the real
Legacy recording, which is only on the first machine, and passed (Kyle, 2026-11-18).

---

## 2026-10-09 - The CUSUM reset does not pause on a rejected crossing

**Context.** Kyle asked whether a crossing the rise-time guard rejects should *pause* the
running mean and variance (leaving that sample out) while the accumulators keep running,
instead of restarting everything as the C does: (a) paused until the next accepted edge;
(b) a temporary pause, ended by an accepted edge or, failing one within a rise time, by the
full reset.

**Decision** (Kyle, 2026-10-09). Keep the reset on every crossing (entry below).

**Evidence.** Prototypes patched into `CUSUM._locate_sublevel_transitions` and run through the
step 1 harness, 50 events per band (seeds 42 and 7), plus flat blockages and a 5 pA band; the
reimplementation of the shipped rule matched it on all 1,650 fits. (a) locks up: with no
accumulator restart the argmin stays on the ramp sample past the accepted edge, so every later
sample is a rejected crossing (124 in a row on the staircase below, edges `[0, 98, 222]`);
0/50 on every 15 pA and 5 pA staircase, every fitter. (b) passes every required pin but a pause
almost never ends in an accepted edge (2 of 3,021 at one rise time, 28 of 2,983 at two): the
frozen statistics still hold the ramp, so the argmin stays on it, and the pause is a reset
delayed by the window that loses a step arriving inside it. CUSUM/IntraCUSUM at 50 pA with
20-sample steps 37/50 → 25 (one rise time) and 3 (two), ClassicCUSUM 40 → 38 and 35; one extra
level at 50 pA with 40-sample steps; identical elsewhere. Also measured: paused statistics with
the accumulators restarted - 37 → 50 on that band, but a duration 29 samples off at 50 pA with
40-sample steps (bound 12) and more over-detection at 100 pA (28 → 31 events).

**Revisit if** the ramp is kept out of the statistics another way, such as restarting them at
`jump + rise_time` after an accepted edge (not measured).

---

## 2026-10-09 - A fitter's run is the channels fitted together; a partial run is not post-processed

**Context.** `_post_process_events` was documented as the whole-dataset step but ran once per
channel, before that channel was marked done. PeakFinder guessed whether it was last from the
other channels' flags, so two channels finishing together could both skip its classification.
`fit_events` returns a generator, so a channel used to register only when its worker first ran
it, and could finish before another channel of the same run had registered.

**Decision** (Kyle, 2026-10-09). `_post_process_events(channels)` is repurposed rather than a
`_post_process_run` added: its docstring always described the run-wide step, and four fitters
left it empty. A run is the channels whose fits are in flight together: a channel joins when
`fit_events` is *called* and leaves however its generator ends; the last one out runs the hook
once with the run's channels, and only if every one finished - an aborted, failed or closed
channel cancels it for that run.

**Rejected** (Kyle). An explicit run-boundary API: it keeps the API simple not to add one when
existing machinery fits the purpose - the tab already creates every channel's generator before
starting any worker (`EventAnalysisController.py:490-518`), so calling `fit_events` is the
boundary. Running the step on a partial run: the default follows PeakFinder's existing
behaviour, since it was the only fitter using the hook; its barrier ran the classification only
when every channel in `event_metadata` had finished, so an aborted run never classified.

**Evidence.** Test-first on a real CUSUM over two channels, requested together, in parallel
threads, one after another, aborted and failed; four mutations of the run logic killed
(`d447555d`). Consequences accepted: a script fitting channels one after another gets one pass
per channel; a generator never iterated keeps its run open.

**Amended 2026-10-09: the last channel is done only after the step** (Kyle). As landed, a
channel reported 1.0 and was marked fitted before the step ran; 1.0 is 100% to the worker and
the tab then drops the channel's progress bar, the only "done" a user sees, and the database
writer (`MetaDatabaseWriter.py:172`) and event plots gate on the mark, so a write could read
PeakFinder's metadata mid-classification. A channel is now marked fitted only when everything
that applies to it is done (Kyle, reversing a first ruling that marked early channels as they
ended): PeakFinder's step rewrites every channel it holds (`PeakFinder.py:2164`), so every
finished channel of a run is marked when the run is over - after the step, or as the run ends
if the step is skipped; none if it raises. This holds for every fitter, so an early channel of
a CUSUM run waits too, which costs only a write attempted mid-run. Progress stays below 1.0
while fitting and the last channel reports 1.0 after the step, so its bar stays up; earlier
channels' bars drop as they end (accepted), and their status reads "waiting for the other
channels of its run" rather than "fitting incomplete". PeakFinder marks its channels after its
last classifier, just before its report, which reads the mark. On 40 comb events (5-10 teeth
each) PeakFinder's metadata and classification are identical before and after, every tooth
found. **Open** (with Nada): channels from an earlier run that a later run's step re-classifies
stay marked while it does.

**Revisit if** a caller needs one run over fits started separately, or a user wants the
run-wide step after aborting a channel.

**Superseded 2026-10-19** (Nada, via Kyle): pooling channels was a bug, not the hook's purpose.
See the next entry.

---

## 2026-10-19 - PeakFinder classifies each channel on its own; channels never pool

**Context.** PeakFinder's classifiers (folding, peak prominence, translocation direction,
bound star) fitted one distribution over every channel the fitter held, wrote one set of
result attributes and one report file for the whole run, and the 2026-10-09 run barrier
above existed to make that pooling safe. Nada, who owns the science, confirmed the pooling
was a bug: every channel is its own experiment and must be fitted, classified and reported
from its own events alone.

**Decision** (Nada's ruling, Kyle 2026-10-19). Each classifier takes one channel and reads
only that channel's events. Every result store is a dict keyed by channel and dropped by
`PeakFinder.reset_channel`; `report_status(channel)` renders that channel's section and the
report file and the three fit plots are written per channel (`<stem>_ch<N>_...`). Channels
are classified on their own worker threads, so the warning collector keeps only its own
thread's records and the plots are drawn with `matplotlib.figure.Figure` rather than the
process-global `pyplot` state. Consequence accepted: a channel fitted earlier is not
re-classified when another channel is fitted later.

**Rejected.** One report file rewritten as each channel finishes: two threads would race on
it. Keeping the result attributes unkeyed and serialising channels: the point of the ruling
is that channels do not interact.

**Evidence.** Spies on the classifier chain over two planted channels see one call per
channel with only that channel's indices and levels; a warning logged while channel 1
classifies is absent from channel 0's record; the real chain over a two-channel synthetic
database writes `_ch0_` and `_ch1_` reports that each count only their own channel's fits
(`tests/unit/plugins/eventfitters/test_peak_finder.py`, 229 tests green).

**Amended 2026-10-19: the run barrier goes too** (Kyle). With nothing pooling, the
2026-10-09 machinery had no purpose: `MetaEventFitter`'s run registration, the rule that a
channel is marked fitted only when its run ends, the "waiting" status, and `MetaModel`'s
batch re-report are deleted. `_post_process_events(channel)` runs inside `fit_events` when
the channel's last event is fitted, before the channel is marked and before the generator
yields 1.0, so a bar stays up and a write waits until that channel's own post-processing is
done, with no reference to any other channel. The hook stays a concrete no-op rather than
returning to abstract, so the four empty overrides stay deleted. Pinned in
`tests/unit/utils/test_meta_event_fitter_post_processing.py`.

**Revisit if** a cross-channel classifier is ever wanted on purpose; it would be a new,
explicitly named step, not a change to these per-channel ones.

---

## 2026-10-09 - The `experiments_and_channels` shape stays `Optional[Dict[str, Optional[List[int]]]]`; two adjacent shapes left alone

**Context.** Step 9a's first item unified 10 analysis-tab-layer signatures that declared
`experiments_and_channels` backwards (`List[Optional[int]]`) or as an unrelated third shape
(`List[str]`), onto the form `MetaDatabaseLoader` and the real producer
(`MetaSubsetTabView._rebuild_event_id_cache`) already use. Tracing the runtime shape
surfaced two adjacent, pre-existing behaviors worth ruling on rather than silently leaving
for someone to re-discover and get nervous about.

**Decision** (Carolina, 2026-10-09). Both left as-is, not fixed:
- `MetaDatabaseLoader._id_tuple` raising `ValueError` on a channel list containing only
  `None` (e.g. `{"exp1": [None]}`) is intentional: `tests/unit/utils/test_meta_database_loader.py:1088-1092`
  pins it as the expected refusal for a malformed per-experiment value. `None` is only
  meaningful as the whole per-experiment value ("all channels"), never as a list member.
- `MetadataController.overlay_plot`'s `{None: [None]}` "nothing selected" sentinel
  (`MetadataController.py:295`) reaches `MetaDatabaseLoader.construct_metadata_query`'s
  `KeyError(f"Could not find experiment ID(s) for: {exp_name}")` guard, but that `KeyError`
  is already caught by `load_metadata_subset`/`_fetch_event_subset`'s own
  `try/except Exception` and reported to the status panel. Reachable, but already a caught,
  reported refusal - not silent wrong output, not a crash.

**Rejected.** Fixing either: neither is a defect introduced or exposed by the annotation
unification, and folding a second, unrelated logic change into a type-consistency fix risks
conflating two different kinds of change in one commit.

**Revisit if** the `{None: [None]}` sentinel's error message ("...for: None") is reported as
confusing by a user - then it is a small, separate wording fix in `MetadataController.overlay_plot`
and its `ProteinView` counterparts, not a behavior change.

---

## 2026-10-08 - A plugin keeps its own copy of its settings; history comes from the plugin

**Context.** `apply_settings` stored the caller's dict and wrote plugin keys back into it. The
edit flow depended on that: the dialog's dict was both what was applied and what was emitted as
history, and only the write-back made it saveable. A refused edit left that dict - holding the
live parent - on the plugin, and the next edit's `deepcopy` crashed on its `RLock`.

**Decision** (Kyle, 2026-10-08). `apply_settings` validates first, then keeps its own copy: each
parameter's dict and lists copied, a plugin it depends on stored by key. It never writes into the
caller's dict. The controller records history from `get_raw_settings()` after an accepted edit, and
an edit renames only after the plugin accepts its settings. A plugin made without `key=` is named
`<ClassName>_<n>` before its settings are applied; an explicit key is taken as given.

**Rejected.** A `deepcopy` of the settings: it holds live plugins, so it is the crash itself.
Keeping the alias and documenting it: every caller would have to know the plugin rewrites its dict,
and a script reusing one dict for a second plugin was refused. Checking explicit keys for
duplicates: a script has no registry to check against.

**Revisit if** settings ever hold something other than plain values and plugins - a nested dict
or a mutable object in `Value` would be shared, since the copy stops at lists.

---

## 2026-10-08 - A database holds results from one type of fitter

**Context.** `columns.name` is `UNIQUE` across tables and registered with `INSERT OR IGNORE`, so a
metric name lands in whichever table registered it first. No single fitter declares a name in
both tables, but `max_blockage` is an event column in the CUSUM family, NanoTrees and NoFitter and
a sublevel column in both PeakFinders: writing two of them into one file sends the second's values
to a column the loader never reads.

**Decision** (Kyle, 2026-10-08). The database writer refuses, at `_validate_settings`, to write a
fitter into a file that holds another type's results. Type means plugin class: any number of runs
of one fitter - other channels, recordings or settings - aggregate in one file, and ClassicCUSUM
after CUSUM is refused. A 3.0 file names its fitter in each channel's provenance. A pre-3.0 file
is accepted if every column the new fitter declares is already registered on the table it declares
it for; amended from "registered columns equal the declared set" because the Clustering and
Protein tabs register their own columns, so equality would refuse even the original fitter. A
fitter whose columns are a subset of the file's is therefore not told apart; its values still land
in the right columns. Breaking.

**Rejected.** Refusing only the colliding name (the narrow fix) and a per-table namespace
(`UNIQUE(name, table_name)`), which changes how every query maps a column to its table. Refusing
every append to a pre-3.0 file, or letting the first 3.0 write claim it.

**Revisit if** comparing fitters in one database becomes a workflow; the per-table namespace is
then the change to make.

---

## 2026-10-08 - A database loader adds the foreign-key indexes to any file it opens, best-effort

**Context.** The metadata database had no index on its foreign keys; its three named indexes
duplicated `UNIQUE` autoindexes. A scoped metadata query with a sublevel filter was quadratic
(871 ms at 5k events, 31.1 s at 20k), and clearing a channel, which runs on every aborted database
write, cascaded through un-indexed children (19.8 s at 5k, 333 s at 20k).

**Decision** (2026-10-08). The writer creates indexes on `data(event_db_id)`,
`sublevels(event_db_id)` and `events(channel_db_id)`, and `SQLiteDBLoader` adds any that are missing
to every file it opens, after its schema check: `CREATE INDEX IF NOT EXISTS` under a 0.25 s lock
timeout (`INDEX_LOCK_TIMEOUT_S`). A read-only or locked file logs one line, opens as before and is
tried again at the next open.

**Evidence** (writer-built databases, 2026-10-08). At 20k events the filtered query fell from
31.1 s to 15 ms and clearing one channel from 333 s to 168 ms. Building the three indexes takes
60 ms at 5k events and 162 ms at 20k; the first open of the 20k file takes 165 ms, later opens 1 ms.

**Why a reader may write.** An index changes no row, and the oldest loader still in use opened a
file carrying the new indexes (checked 2026-10-08), so it is an addition, which the saved-file rule
(2026-11-18) allows inside a major.

**Revisit if** a loader must open a file it may not modify, such as a shared or archived database,
or an index build becomes slow enough to notice at open.

---

## 2026-10-08 - Database loaders keep one connection per call

**Context.** Every `SQLiteDBLoader` method opens and closes its own connection in a
`try/finally`, and `SQLiteEventLoader.load_event` one per event, so nothing stays
open after a call whatever fails; the generators hold theirs only while iterated. 3.0 queued
connection reuse and a `journal_mode`.

**Decision** (Kyle, 2026-10-08). Keep the design. The guarantee against a leaked connection, and
a file Windows will not let the user move while Poriscope runs, is worth more than the cost. No
schema cache: it saves a few milliseconds and risks a stale column list when a writer or the
Clustering and Protein tabs add columns. No WAL.

**Evidence** (local NVMe, 2026-10-08). A connect and close takes 76 µs; a schema lookup 192 µs
fresh against 20 µs on a held connection. One metadata plot opens 23 connections (about 4 ms), a
CSV export 25 (under 1% of 2.7 s), a fit of 500 events 502 (about 85 ms of 623 ms). The loaders
run on the GUI thread and on workers at once, so a held connection would need one per thread. The
lab does not work from network storage, where an open costs milliseconds. Populating `event_counts`
(`_ensure_event_counts`) takes 48 ms at 16k events and 59 ms at 160k, since the autoindex covers
the `GROUP BY`, so it stays on the GUI thread.

**Revisit if** a per-connect cost measured on the storage people actually use shows in a plot or
a fit; a schema cache is the first step then, before any held connection.

---

## 2026-10-08 - `get_plot_features` reads the second sublevel on purpose

**Context.** `SQLitePeakDBLoader.get_plot_features` reads `result.iloc[1]` (`:178`) behind a guard
that rules out only an empty result (`:155`), which the 3.0 queue listed as a defect.

**Decision.** Leave it. Row 0 is the padding, so row 1's start time is where the event begins,
matching `PeakFinder`'s own `start_times[1]`. The fitter rejects any event with three or fewer
boundaries, so a shipped writer always stores three or more sublevel rows; one row comes only from
an edited or foreign file, and `MetadataController` reports the `IndexError` at ERROR.

**Revisit if** a writer can store an event with fewer than three sublevels.

---

## 2026-10-07 - CUSUM's retry factor is not recorded

**Context.** With `Max Sublevels` set, `_locate_sublevel_transitions` retries at 1.5× the
step size up to four times when it finds too many levels; which factor fitted an event is
recorded nowhere. `_populate_event_metadata` does not receive the located edges, and instance
state races across the per-channel threads, so carrying it out needs a sublevel column repeated
on every row, a per-thread value, or a `Meta*` signature change.

**Decision** (Kyle, 2026-10-07; amended 2026-10-09). Not recorded: the information is not
needed, and the hook keeps its signature. No event on any planted band needed a retry
(`Max Sublevels` 10); the retry runs only when the user sets the cap and is described on the
setting.

**Revisit if** a user asks which step size fitted an event.

---

## 2026-10-07 - A fitter fault on an event is a rejection of that event, never an abort

**Context.** `MetaEventFitter.fit_events` wrapped each fitter hook in `except ValueError`
and `except Exception`, both routed through `_reject_event` keyed on `str(e)`, so a
`TypeError` in a plugin landed in the rejection table beside "Too Few Levels" under its
message text, at INFO, and the channel finished as fitted; a hook returning something
that was not a sequence raised out of the generator and left the channel "fitting
incomplete". The question was whether a plugin exception should abort the channel.

**Decision** (Kyle, 2026-10-07). Never abort on a per-event fault and make no judgment
about whether it is systematic: tally it as `Plugin Error (<exception type>)`, log it at
ERROR with the traceback, skip the event and finish the channel, so a fault that hits
every event shows as "0 of N good fits" with its reason and the user decides. A `None`
or empty return is tallied as "No Sublevels" the same way. What still stops the channel
is malformed loader data (the declared `TypeError`/`ValueError`) and a fitter whose
declared columns omit `sublevel_duration`, which is wrong for every event by
construction and is the plugin's declaration, not its data.

**Evidence.** The alternative, aborting after the first N consecutive faults, needs a
threshold nobody can justify and turns a bad event near the start of a channel into a
lost channel; the report already carries counts per reason. `Worker.process_generator`
shows an escaping exception on the status panel, so the abort path stays usable for the
contract failures that keep it.

**Revisit if** a fitter needs to signal "stop this channel" deliberately - that would
be a declared exception type on the base, not `except Exception`.

---

## 2026-10-07 - CUSUM-family settings: no defaults for the physical ones, zero refused

**Context.** `Step Size` and `Rise Time` ship without a default; `IntraCUSUM`'s
`Intraevent Threshold` and `Intraevent Hysteresis` defaulted to 0.0. A zero threshold
counts every noise crossing of the carrier level (1,006 crossings on a clean σ 10 pA
level), and a zero `Step Size` passes the base range check (`Min: 0.0`) and reaches
`ARL`'s `h / s` as a `ZeroDivisionError` that `fit_events` tallies as a rejection reason
on every event. `_validate_settings` was `pass` in every fitter.

**Decision** (Kyle, 2026-10-07). `Step Size` and `Rise Time` stay required: no value is
right across instruments and filters, and the dialog already shows an empty field for a
required setting. `Intraevent Threshold` becomes required for the same reason;
`Intraevent Hysteresis` keeps 0.0. `CUSUM._validate_settings` refuses a step size that is
not larger than zero and `IntraCUSUM._validate_settings` a hysteresis above its threshold,
both as `ValueError` at `apply_settings`, where the dialog reports them.

**Evidence.** The probes above; no shipped flow or test instantiates `IntraCUSUM` from
its defaults (the conformance and ground-truth recipes set the threshold explicitly), so
nothing else moves.

**Revisit if** a default step size can be derived from the data the fitter is attached
to - the loader's reported baseline sigma would make a σ-denominated default possible.

---

## 2026-10-07 - NoFitter's edges are where each edge begins, found by its slope

**Context.** NoFitter walked back from the finder's start estimate to the first sample at
or above the baseline mean and called the count `rise_time`; the start edge went to that
sample and the end edge to the end estimate minus the same count. The geometry was the
intended one - the start where the signal leaves baseline, the end where the return
begins (Kyle, 2026-10-07) - but on low-pass noise the stop rule is a coin flip per
sample once the signal is back on baseline: the walk averaged 8 samples and reached 33
(43 on 20 kHz edges). Both edges landed a random distance early, the blockage median
lost the same random number of steady samples and slid onto a ramp (2.2 σ error at
40-sample steps, 16.8 σ at 20), and the trailing padding's statistics began inside the
blockage's own edge (`baseline_stdev` 3.05× planted at 15 pA, 10.7× on slow edges).

**Decision** (Kyle, 2026-10-07; amended the same day from his manual testing). Each edge is
found from the baseline side - inward from the finder's estimate to the nearest departure
sustained for 3 samples whose run reaches twice the band of 3 local sigmas, skipping noise
excursions - and then walked inward with a slope threshold set from the noise of the data's
own first differences on quiet samples, since on low-pass data consecutive samples differ by
far less than σ. Each sublevel's statistics cover its steady part only: the leading padding
to the last sample within the band of baseline, the blockage from where the leading edge
flattens out to the end edge, the trailing padding from the first sample back within the band.
The current is the mean of the steady blocked stretch, not a median, so NoFitter reports the
average of all blocked states. No setting: NoFitter stays the fitter that adds none, and the
band is a class constant (`EDGE_BAND_SIGMA`). The finders' +1 σ boundary walk got the same
judgement: `MetaEventFinder._event_start_from_the_baseline` / `_event_end_from_the_baseline`
put the start at the sample after the last run of three within-band samples before the
crossing and the end at the first such run after the return crossing, for every shipped finder.

**Rejected.** The first version, walking the slope back from each estimate:
`ClassicBlockageFinder`'s +1 σ estimates sit in the baseline, far out on correlated noise
(real chain at 500 kHz: −20 / +13 samples at a 100 kHz cutoff, −115 / +91 at 20 kHz, up to
−263 / +177), so the walk went nowhere and the end sat after the whole trailing edge. A
global depth (the deepest sustained level): an event may hold several blocked states and the
deepest need not be the last. Mirroring the walk at the end: durations would grow by two
noise-driven walks. Edges at the estimates with untrimmed statistics (`baseline_stdev` 3.9×,
the padding holding the half-edge); with trimmed padding statistics they measured as well on
everything except where the edges sit. A 2 σ band: noise extended the start walk (offsets to
−8) with no gain elsewhere.

**Evidence** (planted bands, 25 events each; the 20 kHz slow-edge fixture, 10). Start and
end offsets from the planted 50% points: −3.7 / −4.0 at 15 pA, −2.0 / −3.0 at 50 pA,
0.0 / −1.9 at 100 pA (the band exceeds the per-sample step), −12.0 / −12.1 on slow edges
(−18.5 / −20.7 after the amendment, the bands otherwise unchanged); duration within 1-2
samples everywhere; blockage current 0.57 σ at 83-sample steps, 1.25 at 40, 1.68 at 20, 0.78
on slow edges; `baseline_stdev` 0.92-0.96 of planted (0.76 on the 57-sample slow-edge
padding, a small-sample effect of heavily correlated noise). Real chain after the amendment:
100 kHz start −2.9 / end −3.1, 20 kHz −17.9 / −21.9 (400 pA) and −12.8 / −17.8 (100 pA),
current within 0.8 σ, `baseline_stdev` 0.88-0.99 of planted, both staircase orders (deepest
first or last) unchanged; the finders' boundaries moved from −115 / +91 (worst −263 / +177)
to the tops of the edges, consistent to within a few samples across events.

**Revisit if** a finder reports an estimate on the far side of its edge (inside the
blockage): the inward walk from there would skip the true edge for the next one.

---

## 2026-10-07 - The CUSUM detector resets on every threshold crossing

**Context.** `3c755291` (2026-05-01) gated the detector's reset behind an accepted jump,
departing from the C reference, to cure variance inflation after a transition; `f7b97900`
(2026-09-03) then reset `varS` inside that block. The step 1 harness showed `ClassicCUSUM`
finding one inner level on 25/25 planted events at 15 pA / 40-sample steps and 22/25 at
83, while finding 25/25 at 50 pA.

**Decision** (Kyle, 2026-10-07). Reset on every crossing, accepted or not, and guard the end
of the data as the C does (`length - jump > rise_time`). The fix lands once in `CUSUM.py`
and reaches `ClassicCUSUM` and `IntraCUSUM` by inheritance; `PeakFinder.py:1019-1045`
(gated reset, `varS` reset outside the loop) waits for Kyle's step 8 PeakFinder work. The
C reference is public (<https://github.com/shadowk29/CUSUM>, `detector.c`); its core maths
is the Python's, its wrapping logic is not a target.

**Evidence.** Trace of one event (Classic, 10 σ, threshold 0.4): the 64 σ leading edge is
accepted at k = 98 mid-ramp; at k = 100 the still-falling signal crosses again, the jump
lands at 99 and the rise-time guard rejects it; with no reset the anchor stays at 98 and
Welford's variance from it swallows the rest of the ramp (195 to 442 σ² over k = 100-104,
decaying as 1/(k − anchor)); `logp`/`logn` scale as 1/variance, so 145 consecutive
crossings re-locate the same rejected jump and the 24 σ steps at 140 and 180 never
register - edges `[0, 98, 219]`. With the C reset the anchor moves at 100 and 102, the
variance returns to 2-4 σ², edges `[0, 98, 139, 179, 217]` against planted 100/140/180/220.
The inflation scales with (edge/σ)², which is why it showed at *higher* SNR. Planted bands:
Classic 22/25 → 25/25 and 0/25 → 25/25 at 15 pA; CUSUM/IntraCUSUM 24/25 → 25/25 at 50 pA;
every variant resolves the 20-sample band (0/25 → 25/25, current ≤ 1.78 σ); the 100 pA
informative band 9/25 → 11/25; currents and durations elsewhere unchanged; no retries and
no trailing sublevel ≤ rise time with or without the guard. The guard is neutral on these
bands and makes the sublevel-shorter-than-rise-time fallbacks unreachable (0 of ~1,900
sublevels hit them before), so they are deleted rather than flagged in metadata.

**Revisit if** a recording shows the reset on a rejected crossing discarding evidence of a
true transition that the gated form would have kept.

**Landed in PeakFinder 2026-10-09** (Kyle: fix it although it is uncalled). `redefine_padding`
takes the same reset, `varS` reset and end guard; no results move, its one call site being
commented out. Its threshold is still the bare step size, not `_calculate_threshold`, so on the
staircase above it fires at the start of the 64 σ ramp, the variance takes the rest of it, and
the step at 140 is missed with either reset (edges `[0, 98, 178, 217]`; `[0, 98, 219]` before).
Left as it is while the method is uncalled; revisit if it is ever wired back in.

---

## 2026-10-06 - A read request in seconds rounds to the nearest sample; no sample-indexed read on the reader base

**Context.** `MetaReader._slice_request` truncated a time in seconds to a sample index, and three
callers build those seconds from integer sample indices. Floating point put 7.7% of indices at
100 kHz one sample early (191 of 3,052 one-sample requests in the test that pins it), so a chunk
boundary duplicated one sample and dropped another.

**Decision** (Kyle, 2026-10-06). Round, in `_slice_request` only. The end is rounded as its own
time, so a request ending at the channel end lands on it.

**Rejected.** A sample-indexed `load_samples` on the reader base: a new method on every reader's
contract is not worth a rounding error, and the one change makes every seconds-based caller exact.

**Revisit if** a caller needs a sample-exact read that a time in seconds cannot express.

---

## 2026-10-06 - A filter declares the settings its data must match; the caller verifies

**Context.** `BesselFilter` takes `Samplerate` as a setting the user types, and nothing checks
it against the data the filter is then applied to: a wrong rate is a silently wrong cutoff.
The data's rate is known only at the call - the selected reader in the Raw Data tab, the
finder's reader, or the event loader during fitting - and the selection can change after the
filter was made. Not every filter needs a rate (`WaveletFilter` declares none).

**Decision** (Kyle, 2026-10-06). A filter declares which of its settings the data must match,
through `MetaFilter.get_data_requirements`, empty by default, which `BesselFilter` overrides to
name `Samplerate`; `get_callable_filter` is unchanged. The caller verifies at the one
resolution point the tabs share (`MetaEventTabController._resolve_callable_filter`, which the
Raw Data trace path also goes through) against the rate it is about to filter at, within
a relative tolerance of 0.1% so a hand-typed 3333333 passes against a header's
3333333.2008785727, and refuses with both rates named on a mismatch rather than filtering
anyway.

**Alternatives rejected.** Prefilling the dialog from a reader: the selection changes later.
Returning `(callable, requirements)` from `get_callable_filter`: a breaking change to a public
`Meta*` method, and the forgetting risk it guards against is already contained by the single
resolution point. Locking filters to readers as child plugins: filters are also applied to
loader data in fitting, the lock still needs an identity check at the call, and standalone
filters in saved sessions and scripts would need migration. Passing the rate per call
(`filter_data(data, samplerate)`): correct by construction, but a breaking ABC change; it is
where this ends up if verification leaks.

**Revisit if** a filter needs a setting matched that no caller can supply, or a second
resolution point appears that bypasses the shared helper.

---

## 2026-10-06 - Ruling E: a file-level schema version, provenance per write, columns stay optional per loader

**Context.** Databases carried no version and no record of the plugins and settings that produced
their events; `SQLitePeakDBLoader` already had a per-column compatibility scheme
(`OPTIONAL_EVENT_COLUMNS`).

**Decision** (Kyle, 2026-10-06; amended 2026-10-08). `PRAGMA user_version = 1` is written inside
the transaction that creates the schema (when `experiments` is absent) and rolls back with it, so
a file is 1 only if 3.0 created it: the writer always appends and nothing else marks a file as
new. 0 reads as pre-3.0, and a loader refuses a version newer than it knows rather than guessing.
Provenance is a nullable `provenance` column on `channels` - a write is one channel - holding what
the writer can reach: itself, the fitter and the event loader (class and settings), the Poriscope
version and a timestamp. Not a table, because the loader of every release from 1.5.0 refuses an
unknown table: v1.7.0's refused a `provenance` table and opened a file with the column, the new
indexes and the stamp. The loader's schema check now requires the core tables and ignores others,
so the version decides whether a file can be read. The Peak loader's column list stays as the
column-level mechanism.

**Revisit if** a schema change ever needs an in-place migration; version 1 carries none, and
the refusal-on-unknown rule is what makes adding one later safe.

---

## 2026-10-06 - Ruling D: how the baseline histogram picks its peak, window and bins

**Context.** `MetaEventFinder._fit_baseline_histogram` followed the tallest bin (`np.argmax`),
windowed it asymmetrically and binned by `int(len(data)**(1/3)/2)`, rules nobody chose; every
sigma-denominated finder threshold comes from this fit.
Measured 2026-10-05 (S1.3 pins): sigma bias +2.0% at 10k samples, +0.6% at 100k; a second
population at 850 pA beside a 1000 pA baseline wins the fit from 55% occupancy; a second
population widens the fitted sigma by about 2.5% through the window.

**Decision** (Kyle, 2026-10-06). *Peak:* the baseline is the local maximum of the histogram
farthest from zero among those at least 10% of the tallest, so occupancy alone never promotes
a shallower level and noise bumps never qualify. *Window:* not symmetric. It runs from the
3 σ tail above the rectified largest peak down to whichever is nearer below it - the 3 σ tail
or the local minimum between that peak and its neighbour - so when two populations sit close
together the window stops at the valley and the neighbour's edge never enters the fit.
*Bins:* Rice's rule, `2 * n ** (1/3)`, four times the old count.

**Evidence (2026-10-06; synthetic rows re-derived at `df639eba`).** Four versions of
the fit on the same samples, sigma bias against a planted 15 pA, the mean reported where the
fit followed the wrong level; the neighbour sits below a 1000 pA baseline, 100k samples,
seed 9 unless stated:

| Case | shipped | Rice's bins | bins + peak | bins + peak + window (ruled) |
| --- | --- | --- | --- | --- |
| N(1000, 15) seed 0, 10k / 100k / 1M | +2.12% / +0.25% / +0.26% | +0.03% / −0.06% / +0.11% | same | +0.48% / 0.00% / +0.08%; 5-seed max at 10k 0.98% |
| 850 (10 σ) at 30% / 55% / 70% | +2.84% / mean 850 / mean 850 | +0.90% / mean 850 / mean 850 | +0.90% / +0.59% / +2.08% | +0.61% / +0.26% / +0.49% |
| 880 (8 σ) at 60% | mean 880 | mean 880 | +1.03% | +0.22% |
| 910 (6 σ) at 45% | +2.70% | +0.79% | +0.79% | +0.89% |
| 940 (4 σ) at 30% / 50% | +12.0% / mean 941 | +3.7% / mean 940 | +3.7% / +11.4% | +6.7% / +5.4% |
| 3 σ apart, 35%, planted 25 (the old 38.29 characterisation) | 38.29 | 30.29 | 30.29 | 29.61 |
| −1000 beside −850 at 55% | mean −850 | mean −850 | mean −1000, +0.59% | mean −1000, +0.26% |
| Planted 100 kHz recording, 12 events, 0.19 / 0.7 / 1.0 s chunks | 0 / 8 / 12 found, short chunks skipped on a singular fit | 12 / 12 / 12 found, nothing rejected, under all three | | |

Real Chimera 2024-05, first second of channel 1 through `ClassicBlockageFinder`: mean −4315.1 pA,
sigma 572.7, against −4323.6 / 571.3 shipped. Rice's bins carry most of the win and end the
short-chunk singular fit; the peak rule makes the baseline right past 50% occupancy; the window
earns its keep at high occupancy and wide separation and is neutral at 6 σ. Three details the
ruling left to the code: peaks qualify by *prominence* ≥ 10% of the tallest bin
(`scipy.signal.find_peaks`), not by height, because on Rice's finer bins a height rule admits
flank bumps and the valley walk stops at the first noise dip - the first draft biased unimodal
sigma −1.7% and the mean 1.3 pA that way; the window's sigma comes from the peak's width at 60%
of its height; the chosen peak is kept by position through the windowing, never re-found by
`argmax`, which could hand the fit a taller neighbour inside the window.

**Known limit.** Below about 4 σ separation no window helps: `_gaussian_fit`'s own 3 σ mask
takes in the neighbour's shoulder. At 4 σ the ruled window reads +6.7% at 30% occupancy against
+3.7% without it and +5.4% at 50% against +11.4%; at 3 σ both read about +20%. A symmetric
window capped at the valley distance, tried as a cure for truncation bias, was no better
anywhere. Recorded, not pinned.

**Revisit if** a recording's baseline is genuinely the population nearest zero (a rectified
trace with its open-pore level below an occupied one), which the farthest-from-zero rule
would misread; no shipped reader produces that today. Or if populations closer than 4 σ
matter in practice, which needs a two-Gaussian fit rather than a window.

---

## 2026-10-06 - Ground-truth tests name their plugins; contract tests cover the family

**Context.** The conformance suite discovers every concrete plugin of a `Meta*` family with
`discover_concrete()` and checks the contract: signatures, settings schema, happy-path
behaviour. The 3.0 ground-truth tests (`test_fitter_accuracy.py`, `test_baseline_sigma_planted.py`)
plant a staircase or a Gaussian baseline and assert what a fitter or finder recovers from it.
The question was whether those, too, should be parametrised over the family.

**Decision** (Kyle, 2026-10-06). No. A planted staircase is a statement about step-detection
fitters and a planted Gaussian about histogram-fit finders; a future fitter need not model
events as steps at all, and would not be wrong for failing a staircase. Ground-truth tests
parametrise over an explicit list of plugin classes and say so in their docstring; a new
plugin opts in by being added. Contract and failure-path tests (a writer's `rejected`, a
reader's bounds, the compliance and schema checks) stay family-wide, because every member
owes those regardless of how it models the data.

**Evidence.** `test_fitter_accuracy.py` already lists `CUSUM`, `ClassicCUSUM`, `IntraCUSUM` and
`NoFitter` by name; under a family-wide parametrisation `PeakFinder` and `Basic_PeakFinder`,
which look for peaks rather than levels, would have failed every staircase band for reasons
that are not defects.

**Revisit if** a family gains a shared, model-free invariant worth planting - for instance
that every fitter's event duration matches the planted blockage length - which would be a
family-wide ground-truth test by construction.

---

## 2026-10-05 - Ranges in the wheel metadata, exact pins in requirements.txt, `-c` in CI

**Context.** `pyproject.toml` declared exact pins (`numpy==2.2.6`, `PySide6==6.9.0`, ...), so
the published wheel refused to install beside any package needing a different patch release.
Loosening them risks CI resolving newer versions than the goldens were captured with:
`release.yml` and the wheel smoke install from the wheel's own metadata.

**Decision** (Kyle, 2026-10-05; ranges reshaped 2026-11-04). `pyproject.toml` declares ranges
for installers, each from the `requirements.txt` pin to the next major (`>=2.2.6,<3`; why not
`~=`: the 2026-11-04 entry). `requirements.txt` keeps the exact versions the suite is tested
against: the pinned CI legs and the release install with `-c requirements.txt`, while the
ranges legs resolve fresh. Dependabot moves the exact pins and the action SHAs weekly against
`develop`, where branch CI tests the bump on both platforms before merge.

**Evidence.** The built wheel's `Requires-Dist` carries the ranges; the suite is green under
the one pin that moved with it (`hdbscan` 0.8.40 -> 0.8.44, which removed 16 `force_all_finite`
FutureWarnings that scikit-learn 1.8 would have turned into failures).

**Revisit if** a range admits a release that breaks a golden before Dependabot's exact-pin
PR has caught it; the ranges legs should see it first.

---

## 2026-10-05 - The release workflow runs on the tag only; release branches get branch CI

**Context.** `release.yml` ran on every push to `main` as well as on `v*` tags: the same job,
minus the publish steps, on the same merge commit the tag then pointed at. Meanwhile no
`release/*` branch had ever had a workflow run - `ci-branches.yml` listed develop, feature,
bugfix and hotfix, and `docs-check.yml` only saw release branches through pull requests,
which git flow never opens - so the 2.0.0 preparation commit's first CI was after it had
merged into `main`.

**Decision** (Kyle, 2026-10-05). Drop the `main` push trigger from `release.yml` and add
`release/*` to the push triggers of `ci-branches.yml` and `docs-check.yml`. The gate moves
to before the merge; the tag run still runs the full suite before it publishes.

**Evidence.** The `main` run bought only a staged push order - push `main`, see green, then
push the tag. When that run fails the broken merge commit is already public on `main` and a
hotfix is needed regardless; all the staging saves is a tag with no release behind it, and
the tag run refuses to publish on a failed suite anyway. For 2.0.0 both runs went green on
`c2d79e9f` six minutes apart, for one answer. GitHub showed 0 runs for `release/1.9.0` and
`release/1.8.0`.

**Residual risk.** A merge commit can differ from the release tip when `main` carries commits
`develop` does not (two bot binary commits, this release); the tag run still tests that exact
commit before publishing. A push to `main` outside git flow now runs only the docs deploy -
a branch-protection question, not a workflow one.

**Revisit if** a release run on the tag fails on something the release branch's run passed,
which would mean the merge commit is where the risk lives after all.

---

## 2026-09-27 - Session load restores plugins; action replay stays an explicit, per-tab step

**Context.** A session holds `plugin_history.json` and each tab's `tab_action_history.json`.
Replay re-runs recorded actions, which can mean expensive reconstruction, synchronously on the
GUI thread. Recorded in the 2026-08 architecture notes as settled design, with no owner named.

**Decision.** Opening a session restores plugins (and, once built, control-panel state)
automatically; replaying a tab's actions stays a separate, user-triggered step per tab, and
no "replay everything" is built. Two invariants follow: a control's *options* never depend on
replayed state, only on plugins and the database; and a tab's replay never assumes another
tab's has run.

**Evidence.** Already how the code behaves: `MainController.load_session` never replays, and
replay is reached only through `MetaView._load_actions_from_json`'s file dialog. History is
keyed per tab class, and every analysis tab is an independent triad, so restoring Metadata
without re-running RawData is coherent. Filters, cluster columns and database columns all come
from loader plugins, not from replay.

**Revisit if** a user needs a whole session's plots back in one step, or a tab starts
populating a control from something only replay creates.
*Superseded in part 2026-10-25: after a load, a dialog replays the tabs the user ticks (see that entry); the
two rules above still hold.*

---

## 2026-09-27 - Replacing a channel does not renumber `events.id`

**Context.** After a re-commit replaced a channel, its rows in the events file took new,
higher `events.id` values instead of restarting (manual pass, 2026-09-27).

**Decision** (Kyle, 2026-09-27). Not a defect; `events.id` and `channels.id` are storage keys
and are never renumbered. `AUTOINCREMENT` guarantees a row id is never reused, both tables
hold every channel's rows in one sequence, so restarting one channel's ids would collide with
another channel's rows or force renumbering them. The per-channel `event_id`, which does
restart, is the only event number anything reads.

**Evidence.** `SQLiteEventLoader` selects by `(channel_id, event_id)`, counts and lists by
`channel_id`, and uses `channels.id` only as a join key (`:131`, `:200`, `:295`).

**Revisit if** something starts reading `events.id` as a position or showing it to the user.

---

## 2026-09-26 - Non-finite event data is rejected in the base, before any fitter

**Context.** A NaN or infinite sample poisons every statistic a fitter computes, and each
fitter tripped over it differently.

**Decision** (Kyle, 2026-09-26, as recommended). `MetaEventFitter.fit_events` rejects the
event as "Non-finite Data" right after loading (after any filter), so no fitter needs its
own guard and the hooks are documented as receiving finite data. Filed as a breaking result
change, because some fitters used to keep such events.

**Evidence.** One planted NaN per event, 25 events: CUSUM and IntraCUSUM rejected 25 as "Too
Few Levels", ClassicCUSUM 21 (4 fitted), Basic_PeakFinder rejected 5 as "No Peaks Found" (20
fitted), PeakFinder 25 "No Peaks Found", NanoTrees 25 with sklearn's "Input y contains NaN.",
and NoFitter fitted all 25. Now all seven reject 25 as "Non-finite Data".

**Revisit if** a fitter is added that can meaningfully fit through gaps in the data.

---

## 2026-09-25 - NoFitter's per-event geometry travels in its sublevel entries

**Context.** NoFitter stored each event's rise time on the instance between
`_locate_sublevel_transitions` and `_populate_sublevel_metadata`, and one instance fits every
channel on a thread per channel, so another channel's event could replace it in between.

**Decision** (Kyle, 2026-09-25). Per-event geometry rides in the sublevel list the base already
passes from one step to the next (`List[Any]` exists for that), never on the instance; since
2026-10-07 the entries are `(edge, statistics_start, statistics_end)`. No contract change:
serialising NoFitter would cost parallelism, and neither step is given the channel to key a dict by.

**Evidence.** An event located in between shifted `sublevel_stdev` by 8.5 in a
single-threaded interleave test, which now passes; conformance is unchanged.

**Revisit if** the base contract gains a per-event channel for plugins.

---

## 2026-09-25 - CUSUM Sensitivity is documented as it works, not inverted

**Context.** `Sensitivity` was documented as "higher is more conservative", but CUSUM
returns `threshold / Sensitivity`, so higher detects more transitions.

**Decision** (Kyle, 2026-09-25). Fix the documentation, not the setting: the name already
describes the behaviour, the range (1-5, default 1) makes the default the most conservative,
and inverting it would silently change every saved session and configuration.

**Evidence.** At a 2σ step over 30 events, Sensitivity 1 fitted the planted four sublevels
in 30/30, 3 in 16/30, and 5 in 0/30 (8-34 sublevels each).

**Revisit if** users read the name the other way round in practice.

---

## 2026-09-25 - Quitting saves the session only when something is open

**Context.** Quit always flushed the session, so quitting after Reset Session - or straight
after launch - wrote `{}` over the file Restore reads.

**Decision** (Kyle, 2026-09-25). Skip the flush when the history is empty, rather than track
a "dirty since reset" flag: an empty history is already saved (every delete autosaves) or
means nothing happened. Session writes go through a temporary file and `os.replace`
without `default=serialize_object`: no reachable value needs it, a failed save now leaves
the last good file, and a default would turn a reported failure into a silent coercion.

**Evidence.** Reset -> quit -> relaunch and launch -> quit -> relaunch both restored nothing;
an unserialisable value truncated the file mid-entry. Both pinned by tests. The rename is
retried on `PermissionError` (5 attempts, 50 ms steps): Windows briefly refuses a rename onto
a file a scanner still holds - 14 of 300 rapid saves in the temp folder failed without the
retry, 0 of 600 with it - which would have reported autosave as stopped.

**Revisit if** a non-JSON value is found reaching the session history.

---

## 2026-09-25 - Numeric fields use the C locale, and a comma disables OK

**Context.** Float fields validated with the system locale and parsed with `float()`, so a
comma-decimal system refused '.', and every locale let a group separator through to a
`float()` that raised.

**Decision** (Kyle, 2026-09-25). Give each numeric validator `QLocale.c()`, per validator
rather than app-wide (tests see it; plugin authors' own widgets are left alone), and treat
a comma as invalid rather than converting it - `1,000.5` would silently become 1.0005.
Integer fields accept a prefix that more digits can bring into range.

**Evidence.** Under fr_CA a pre-filled `1.0` disabled OK and `0.5` saved as 5.0; under
en_CA `1,000` raised at OK; `-5` saved as +5 in PeakFinder's thresholds. All pinned by
widget tests. `TimeRangeValidator` and the bins fields already use ',' as a list separator.

**Revisit if** users ask to type in their own locale's notation - that is parsing with the
locale end to end, not a validator change.

---

## 2026-09-25 - Reader file sets are globbed on each format's own grammar

**Context.** Five readers globbed `<base>*<ext>`, so `exp1` also picked up `exp10`: the other
recording was spliced into the channel, or the sort crashed on a tied timestamp.

**Decision** (Kyle, 2026-09-25). Anchor each pattern on what follows the base and
`glob.escape` the base: Chimera on `_HS` (always present) with the date-time left wild,
since the reader takes its timestamp from the sidecar, not the name; VC100 and TCossaLab on
their digit counts, the TCossaLab 12-digit stamp still wild within a set; Legacy Elements
on the exact file name, because its recordings are always one file. The timestamp sort
keys on the timestamp alone, so a tie no longer compares memmaps.

**Evidence.** A sibling-prefix conformance test failed on all five readers and a bracketed
name on six; both pass, and multi-HS and multi-part sets still load.

**Revisit if** a format's real file names turn out not to follow the grammar coded here.

---

## 2026-09-25 - A re-commit is confirmed per channel and keyed on channel alone

**Context.** A second commit into an events file that already held a channel kept the old
events through `INSERT OR IGNORE`. The fix asks first, then resets the channel.

**Decision** (Kyle, 2026-09-25). The writer refuses a held channel unless `overwrite=True`;
the Raw Data tab asks once per held channel (No skips only that channel, as the
event-finding prompt does) and passes `overwrite`. A held channel is matched on channel
alone: `channels.channel_id` is unique and nothing downstream reads the experiment `name`,
so a differing name is flagged in the question for the user to decide, not treated as a
separate slot. `DontConfirmOverwrite` stays on the file picker - no file is replaced, and
`SQLiteDBWriter` appends to one on purpose.

**Evidence.** Commit 10, re-find 5, commit reported "Wrote 0/5" and kept the 10; a later,
larger run stored some events twice and lost others. `reset_channel` already cascades to
the channel's events and leaves other channels intact.

**Revisit if** the events loader starts distinguishing experiments - then one file could
hold the same channel for two experiments and the key would need the name.

---

## 2026-09-25 - The raw-data path is removed: every read and every stored event is in pA

**Context.** Readers, finders and writers carried a second, unscaled path: `load_raw_data`,
`continuous_read_raw`, `_convert_raw_data`, `_set_raw_dtype`/`get_raw_dtype`, a `raw_data`
flag on the finder's event methods, and `MetaWriter._rescale_data_to_adc`. Its only use was
the writer storing the file's samples whenever the reader's dtype equalled its own `<f8`,
which for a `SingleBinaryDecoder` with Scale or Offset set stored unscaled traces beside a
scaled `baseline_mean`.

**Decision** (Kyle, 2026-09-25). Remove the path at every layer; everything goes through
`load_data` in pA. No user relies on it, and float64 pA loses nothing that matters. The
`events.raw_data` column keeps its name: it means unfiltered, not unscaled, and removing the
path removes the ambiguity.

**Evidence.** The writer shortcut was the only producer; no view, export, filter or loader
consumed a raw symbol. `datareaders` duplication fell 446 -> 401. A conformance test pins a
stored trace to `load_data` under Scale=2, Offset=100 (798 of 798 samples differed before). A
database written through the old shortcut records no Scale, so it cannot be found automatically;
its `baseline_mean` divided by the median of an event's padding is roughly the Scale, and the
remedy is to commit the events again to a new file.

**Revisit if** a format needs lossless integer storage - that would be a writer choosing its
own output dtype, not a second read path.

---

## 2026-09-23 - The refactor-coverage audit is retired, and CI stops collecting coverage

**Context.** `scripts/check_refactor_coverage.py` held every method the 2.0.0 refactor moved
or deduplicated to "named by a test and executed". Its target list was the refactor's own, so
it had nothing to check once the moves were done, and its execution half was the only reason
`ci-branches.yml` ran `--cov` (added 2026-09-14).

**Decision.** Delete the script, its two test files and both CI steps, and drop `--cov` from
`ci-branches.yml` and `ci-internal-pr.yml` along with the coverage-XML upload and notice (Kyle).
`pytest-cov` stays in `[dev]` for a local `pytest --cov=poriscope`.

**Evidence.** CI's test step went 184 s -> 275 s across the commit that added `--cov`. Nothing
failed on a coverage drop, so the notice was information nothing acted on.

**Revisit if** another large refactor moves code: rebuild the audit from that refactor's own
move list, which is the part of it that generalises. No coverage ratchet either (Kyle,
2026-09-27); one would first need QThread code traced (`concurrency` in a `.coveragerc`), or worker
and writer coverage reads falsely low.

---

## 2026-09-22 - Two uncalled methods kept through the orphan sweep

**Decision** (Kyle, 2026-09-22). The 2.0.0 sweep deleted about 70 methods with no production
caller, but `BaseDataPlugin.__enter__`/`__exit__` stay although nothing in the app or tests calls
them: they let a script use any data plugin as a context manager. Pinned by
`test_base_data_plugin_context_manager.py`, checked against a mutation.

**Revisit if** scripting support for data plugins is dropped.

---

## 2026-09-22 - Decisions C and D amended at the exit review

**Decision** (Kyle; landed 2026-10-09 in 3.0). The plugin channel and status contract:
- One `report_status(channel=None, init=False)` on `BaseDataPlugin`; `report_channel_status` was
  removed with no alias ("I do not want multiple paths to getting plugin reports").
- `close_resources()` takes no channel and is a concrete no-op, overridden only where a plugin
  really holds something.
- `reset_channel(channel: int)` is required on every plugin (a no-op on `MetaFilter`).
- `__enter__`/`__exit__` stay for scripts.
- `Threshold` is declared on `MetaEventFinder` with `"Units": None`, each finder setting its own
  unit, since the shipped finders disagree (pA against σ).
- The `"Kind"` schema key was never built (see 2026-09-01).

**Evidence** (at `70230b39`). 16 of 18 `close_resources` overrides were empty, and the two that
acted closed one shared connection, so a per-channel close never existed. `None` was wrong in three
of the four `reset_channel` bodies that did work.

**Revisit if** a later audit finds a break not called out in `changelog.md`.

---

## 2026-09-22 - The tab scaffold generates the controls panel, and authors it

**Decision** (Kyle asked for it after a generated tab opened over an empty strip). The scaffold
writes a fourth file, `<Name>Controls.py`, plus a `_build_controls` override, with one button and a
real `handle_parameter_change` that answers it on the status panel, so a fresh tab proves the path
from a click to the View. This one file is an authored template, not copied signatures:
`MetaControls` declares its methods only in its docstring and cannot make them abstract, because
`MetaView._build_controls` instantiates it for its default (`scripts/new_plugin.py` says the same).
It goes beside the triad, keeping in-repo and user-folder output identical and staying out of the
`CODEOWNERS`-assigned `analysistabs/utils/`. Pinned by `tests/unit/views/test_generated_analysis_tab.py`,
which clicks the button with nothing patched.

**Revisit if** `MetaControls` ever declares its own contract, at which point most of this
template becomes derivable like the rest.

---

## 2026-09-22 - The tab scaffold writes two bodies rather than stubbing them

**Decision.** Stubbing every abstract method gives a triad that is legal and does not run, so two
bodies are written: `_init` builds the View and Model (the constructor connects them as soon as
`_init` returns), and any abstract method whose base body is more than a docstring and `pass` gets a
`super()` call (`has_real_body` in `scripts/new_plugin.py`). Today that is only
`MetaView.update_available_plugins`, which records the plugins on the View.

**Revisit if** a base grows an abstract method whose body must *not* be delegated to. The
rule would then need an opt-out rather than a new special case.

---

## 2026-09-22 - The scaffold's acceptance test lives under tests/unit/views

**Context.** Everything else asserted about `new_plugin.py` is static and lives in
`tests/unit/scripts`. The test that constructs a generated triad cannot be.

**Decision.** `tests/unit/views/test_generated_analysis_tab.py`. Building a `MetaView` creates a
Matplotlib canvas on a Qt widget, and the offscreen platform, `Agg` backend and dialog guard are set
up by `tests/unit/views/conftest.py`, not by `tests/unit/scripts` (`QT_QPA_PLATFORM` is set in the
e2e, integration and unit/views conftests). A Qt test in `scripts/` would depend on another
directory's conftest being collected first, the coupling that has segfaulted this suite before.

**Revisit if** the platform and backend setup is hoisted to `tests/conftest.py`.

---

## 2026-09-22 - The user plugin folder goes on sys.path, not just its parent

**Context.** A multi-file plugin (an analysis tab's Controller importing its View and Model) could
not import its own parts from the user folder: only the folder's *parent* was on `sys.path`, and one
real installation calls the folder `User Plugins`, which no import can spell. The path also used the
*default* folder while `MainModel` scans the *configured* one.

**Decision** (Kyle, 2026-09-22). Append the configured folder itself alongside its parent; files
import siblings by bare stem, always an identifier because it equals the class defined. Appended,
not inserted, so a plugin file cannot shadow a stdlib or site-packages module. The generator tests
use a `User Plugins` folder and `tests/unit/test_main_app.py` moves the configured folder off the
default. The View class the menus register and the one the Controller builds are distinct module
objects; that is inert, because `MainController` only instantiates the Controller.

**Revisit if** plugin files ever stop being named for the class they define, which is what
makes a bare-stem import safe.

---

## 2026-09-21 - Error dialogs get a parent; the startup ordering is left alone

**Context.** A plugin-name collision logged at ERROR during startup discovery made the app appear
to hang: `QtHandler`'s modal dialog opened, parentless, behind a main window that had not painted,
and an invisible modal still holds the input grab.

**Decision** (Kyle, 2026-09-21). Parent the dialog to `QApplication.activeWindow()` and raise it;
pinned in `tests/unit/utils/test_qt_handler.py` (both assertions fail on the parentless version) and
checked by a manual Windows pass. **The ordering is deliberately not addressed**: an ERROR logged
before any window exists still has no parent. Holding startup records until the window shows was set
aside as a larger change than the symptom warrants.

**Revisit if** a startup error is reported as a hang again. The answer then is to queue
records until the main window is shown, reusing the queue `QtHandler` already keeps for
records arriving while a dialog is open.

---

## 2026-09-21 - Startup cost is imports, and the cold-start penalty is not ours

**Context.** Kyle reported launches that are "slow sometimes, but not consistently - repeated
starts are usually fast". The intuitive suspect was `populate_available_plugins`, which walks
the plugin tree and *executes* every `.py` file it finds.

**Decision.** Leave it. Measure warm, not cold, when judging Poriscope's own I/O cost.

**Evidence.** `populate_available_plugins` is **0.07s** - not a factor, and the intuitive
suspect is the wrong one. Importing `poriscope.main_app` is **2.97s warm against 8.65s
cold**; within the warm 3s, `scipy.optimize` 0.86s, `matplotlib.pyplot` 0.67s and `pandas`
0.66s dominate. The ~5.7s difference is first-touch file I/O on this checkout, which sits on
a OneDrive-synced path - a development-machine artifact that users do not have (Kyle,
2026-09-21). The obvious remedy for the warm 3s, deferring heavy imports into the functions
that need them, is barred by the module-level import rule in any case.

**Revisit if** the warm 3s becomes a complaint in its own right, at which point the answer is
a splash screen during import rather than lazy imports.

---

## 2026-09-21 - A splice anchored on neighbours can delete what sits between them

**Context.** A 2.0.0 splice anchored on two `def` lines deleted `initialize_components`, which sat
between them; `ruff --fix` then removed its now-unused imports, every gate passed, the full suite
stayed green, and the app could not start. The general lessons are skill lessons E22 and E23
(planning-and-executing-changes); this entry keeps the Poriscope-specific part.

**Decision.** Nothing constructs `App` under test (one `QApplication` per process, so
`tests/unit/test_main_app.py` borrows its methods onto a stub, and a method nothing borrows can
vanish silently). Two guards stay there: `TestAppIsWhole`, an AST check that every method `App`
calls on itself is defined, and `TestInitializeComponents`, which borrows the real method and patches
its classes *by their names in `main_app`*, so the borrow fails if the method goes and the patch
fails if an import does. Both were verified against the real mutations.

**Revisit if** a way is found to construct `App` under test. A real smoke test would
subsume both guards; until then they are shallow by necessity, proving the methods exist
rather than that they work.

---

## 2026-09-20 - Step 5c is measured in complexity, not in lines

**Decision.** The app shell (nine files no other gate covers) is measured in **cyclomatic
complexity**, not lines, by `scripts/measure_shell_complexity.py` (textbook McCabe; its docstring
states the rule) against `.shell-complexity-baseline.json`.

**Evidence.** Over the nine files, 8 functions exceeded complexity 10. `settings_window.py` had
**zero** despite 890 lines (long, flat Qt widget construction) and `main_view.py` two despite 1,235,
so a length target would chase a number that describes no problem. An earlier uncommitted ad-hoc
count was rejected: it scored `with` as a branch, marking functions down for explicit cleanup.

**Revisit if** a shell file grows a long-and-flat method that is genuinely hard to read for
reasons complexity cannot see - at which point the answer is a second metric, not a
replacement, because a file can be bad in more than one way.

---

## 2026-09-20 - Range parsing stays spread out, because it is not one thing copied

**Context.** Step 5d listed "range parsing is spread over 4 modules" as a consolidation
target, with `poriscope/utils/range_parsing.py` named as the destination.

**Decision.** Leave it. The spread is real and the duplication is not.

**Evidence.** 10 functions across `MetaEventTabView.py`, `float_range_line_edit.py`,
`integer_range_line_edit.py` and `time_widget.py` split a segment on a hyphen, and
`measure_duplication.py` reports **zero** byte-identical bodies between them. Reading them
says why: they implement five different grammars. `FloatRangeValidator` forbids commas and
requires a hyphen; `RangeValidator` allows commas, forbids dots, rejects a leading `-` and
accepts bare values; `time_widget._parse_ranges` encodes an omitted end as `0.0`/`None`;
`_parse_event_indices` is parameterised on a caster; `_expand_event_indices` expands to a
set of ints. The common core is a six-line tokeniser, and a shared validator base would
need four flags to cover the grammar differences.

**Revisit if** a fifth caller appears that wants an existing grammar rather than a new one,
or if one of these grammars is deliberately changed - at that point the tokeniser has a
second reason to exist and the flags stop being hypothetical.

---

## 2026-09-20 - Correcting the baseline sigma, knowing it changes every result

**Decision** (Kyle). The baseline histogram's bins are labelled by their true centres, not by
`np.linspace(bottom, top, bins)`, which stretched the axis by `bins/(bins-1)` - and a Gaussian fit
reports σ in the units of the axis it is handed. A deliberate result change: every finder now
detects at the threshold the user asked for, so the same settings find more events, most on short
chunks.

**Evidence.** 40 trials of pure Gaussian noise per size: σ was +13.9% high at 10k samples, +5.2% at
100k and +2.3% at 1M, and +2.3%, +0.6%, +0.2% after; the mean was never biased. The bin count and
the window and peak choice were later re-ruled (Ruling D, 2026-10-06).

---

## 2026-09-20 - No alias module for a removed exposed name

**Context.** Collapsing `QWidgetABCMeta` into `QObjectABCMeta` first kept a one-line alias
module, since both names were in `exposed.py` and a third-party plugin might import either.

**Decision** (Kyle, 2026-09-20). Delete the alias: there are no third-party plugins to break,
and an alias module is orphaned code. A removed exposed name is a breaking change in the
changelog instead.

**Revisit if** Poriscope acquires third-party plugins, when a deprecation period is worth it.

---

## 2026-09-19 - `_find_events_in_chunk` stays one copy per finder

**Context.** `ClassicBlockageFinder` and `ThresholdBlockageFinder` each override it, differing in
13 lines.

**Decision** (2026-09-19). Leave both, as a recorded duplication floor. The 13 lines are the
policy: Classic's threshold is in pA over sigma with hysteresis 1 and walks the event *start* back
into the baseline; Threshold's is already in sigma with hysteresis 0 and walks the *end* back. A
helper parameterised on which edge to walk is more machinery than the duplication costs.

**Revisit if** a third finder needs the same loop, or the two policies converge.

---

## 2026-09-19 - Code shared by a plugin family goes on its `Meta*` base

**Context.** The histogram fit behind `_get_baseline_stats` was the same ~60 lines in two
finders, and the first proposal was a module-level helper.

**Decision** (Kyle, 2026-09-19). Shared code stays in the family, as a concrete protected
method on the `Meta*` base that already exists, never in a helper module beside it; the
abstract hook it serves stays abstract, so each plugin still writes its own policy around one
call. It applies only to code universal to the family: code shared by three of seven readers
*because they read one vendor's format* is not, and is answered on its own terms.

**Revisit if** the shared code needs state or imports the base should not carry.

---

## 2026-09-19 - No new inheritance layers in the data plugins, and the no-op hooks stay abstract

**Context.** Deduplicating the reader, finder and fitter families invited intermediate bases
(a Chimera base, a CUSUM-family base, a finder base) and making the no-op hooks concrete.

**Decision** (Kyle, 2026-09-19). `BaseDataPlugin` -> `Meta*` -> plugin is deep enough:
deduplicate with protected methods on the base, parameters and deletions, and record what
remains as a floor with its reason - some duplication is acceptable. The abstract hooks
`_init`, `reset_channel`, `_validate_settings` and `_validate_file_type` stay abstract even
though most plugins implement them as a docstring plus `pass`, because the hook exists to make the
author decide, and a plugin that really holds a file handle is the one that must not inherit a
silent no-op. *`close_resources` was made a concrete no-op in 3.0 (see "Decisions C and D amended",
2026-09-22): 16 of its 18 overrides were empty.*

**Revisit if** a sub-family grows past three members, which is when an intermediate base
starts paying for itself.

---

## 2026-09-19 - A refusal is explained once, by whoever refused it

**Context.** The protein tab reported a refusal ("has no experiment named x") and then, under it,
"No data available for event_id 10" - naming the one thing that was not wrong - because a refusal
and an empty result both came back as `[]`.

**Decision.** A refused fetch returns **None** once the refuser has reported it, and a list when the
fetch ran; callers speak only about an empty list. Rows returned without the `id` column are now
reported too, not only logged: with the caller silent on a refusal, a log-only branch is a plot that
fails with nothing said. Pinned in `tests/unit/controllers/test_protein_fetch_slots.py`.

**Revisit if** a refusal path is added that does *not* report - then None would be silent
in both layers, and the rule "whoever refuses, explains" has to be re-checked rather than
assumed.

---

## 2026-09-19 - The global signal bus is removed in 2.0.0, not deprecated

**Decision, Kyle.** The `global_signal` machinery was deleted outright, with the
`data_plugin_controller_signal` pair on the same dispatcher and the pages documenting the bus
(a "removed" stub page remains), rather than deprecated once nothing emitted on it. A mechanism
nothing uses is not free: its dispatcher swallowed failures, the shape behind the stale-read bugs,
and a documented bus invites a plugin author to build on it. `check_mvc_boundary` rule 1 keeps it
from returning.

**Revisit if** something turns out to need string-dispatched cross-plugin calls.

---

## 2026-09-19 - The docs render check runs on pushes to develop, not only on pull requests

**Context.** `docs-check.yml` built the docs with `-W` on pull requests to `main`, `develop`
and `release/*`, plus pushes to `hotfix/*`. Work reaches `develop` through
`git flow feature finish`, which merges locally and opens no pull request, so the gate never
ran over the branches this project actually lands on; the first build such a change got was
`build_and_deploy_docs.yml` against `main`, after the fact.

**Decision.** Add `develop` to the push trigger.

A branch that also has a pull request open renders twice, a few wasted minutes on a rare case.

**Revisit if** feature branches start reaching `develop` through pull requests, which would
make the push trigger redundant.

---

## 2026-09-17 - Action replay records a declared action name, not a method name

**Context.** `@register_action` records `func.__name__` with the call's args and kwargs, and
`MetaView.update_actions_from_json` replays them by `getattr(self, name)(*args, **kwargs)` on
the **View**. Step 7 left the refactor's obligation as an either/or - thin View facades, or a
name-migration map - and it had to be settled before the next conversion touches a decorated
method.

**Decision.** Replay is a record of *what the user did*, so it stays on the View and its
arguments stay small. What changes is the identifier: a decorated method declares a **stable
action name**, and replay dispatches through the registry those declarations build rather
than through `getattr` on whatever the file happens to name. Five rules:

1. **Replay runs on the View.** The thing being replayed is the user's action, not a
   computation, so the decorated method is the entry point a click reaches. A conversion may
   move what it computes to the Model; the entry point stays. *Reversed 2026-10-25: the Controller
   dispatches replay and a Controller method is the recorded action; see that entry.*
2. **The declared action name is the contract, not the method name.** `@register_action("overlay_plot")`
   on `_overlay_plot`, so the method may be renamed, split or re-homed freely and the saved
   files do not care. *Implemented 2026-10-25.*
3. **Replay resolves only registered actions.** An unknown name is reported, not called. *Implemented
   2026-10-25.*
4. **A recorded argument is small, JSON-round-trippable user intent** - a controls panel's
   `parameters` dict - never data. Arrays and frames are what replay re-derives. *Reshaped 2026-10-28: the
   intent is the action's explicit parameters, each saved by name; see that entry.*
5. **A replayable action is a pure function of its recorded arguments.** Everything it
   depends on is captured when the action is recorded and passed in; the body reads **no**
   widget state. Replay has to reproduce what the user actually did, not press the button
   again against whatever is in the entry boxes now. *Met 2026-09-25 for both decorated plot methods: the filter and channel selection is recorded in their parameters (`MetaSubsetTabView._record_selection`), without the registry.* *Enforced 2026-10-26 by a replay tripwire, a static test and a behavioural flow; see that entry.*

**Backward compatibility is explicitly not a constraint.** Kyle's ruling, 2026-09-17: the
feature is barely used, so existing `.json` action files may be broken where doing so makes
the design better. That is what frees rules 2 and 3; protecting those files was the only
argument for freezing method names, and it was a constraint on every conversion in Step 4 in
exchange for compatibility nobody is relying on.

**Evidence.** 5 decorator sites over **3** distinct names, re-measured today: `_reset_actions`
on `ClusteringView:162`, `MetadataView:391` and `ProteinView:731`, plus
`MetadataView._overlay_plot:1413` and `ProteinView._update_distribution_ensemble:1933` - the
plan recorded 4, and 11 before that. **All three are private names**, so today's file format is
coupled to internals, which is exactly what rule 2 undoes. Every recorded argument is already a
`str` or a `Dict[str, Any]`, so rule 4 is written down rather than imposed.

**Rule 5 is the one with work behind it, and it names a live defect** - filed in
`future_fixes.md` rather than left here. Both non-trivial decorated methods call
`self.get_selected_filters()` *inside the body* (`MetadataView._overlay_plot:1414-1755`,
`ProteinView._update_distribution_ensemble:1934-2038`), and that reads
`self._subset_controls.filter_comboBox.getSelectedItems()` - live widget state. So replaying a
saved plot applies **whichever filters are selected now** to a recorded request, silently, and
the plot that comes back is not the plot that was saved. The fix is to capture the selection
into the recorded payload at record time, which also makes the decorated method testable
without a widget and trivially movable by a Step 4 conversion. `_reset_actions` reads nothing
and already satisfies the rule.

Rule 3 closes a real
robustness hole rather than a theoretical one: `MetaController.load_actions_from_json` reads a
user-chosen file with no validation and `update_actions_from_json` does `getattr(self, name, None)`
and calls it, so any callable attribute on the View is reachable from a shared action file. Not
a new trust boundary - plugin discovery already executes local `.py` files - but free to close.

**What it settles for 4c Protein.** Only `_update_distribution_ensemble` is decorated, not its
twin `_update_distribution_individual`, and under rule 2 a rename would no longer matter anyway.
The pair converts together, and the recorded worry that splitting them breaks replay does not
arise.

**Not implemented here.** The decorator change, the registry and the replay guard are Step 7
work; this entry is the decision that stops the next conversion having to take it under
pressure. *Implemented 2026-10-25 (declared names, the registry) and 2026-10-26 (the replay
guard); with rule 1 reversed, replay runs on the Controller. See those entries.*

**Revisit** if replay is ever wanted over a Model rather than a View. That would mean recording
data instead of intent, which is what rule 4 exists to refuse.

---

## 2026-09-17 - The promoted event-plot message names both the plot type and the ids

**Context.** Promoting `load_event_plot_data` leaves one body where there were two, and the
two differed in three messages: Metadata named the event ids ("no data available for plotting
with indices in the specified range [5, 10]") and Protein named the plot type ("no data
available for the requested histograms"). One method can only send one.

**Decision.** The shared message carries both - `No data available for the requested
{action_label}: {event_ids}`. Kyle's ruling, 2026-09-17.

Neither tab loses information and both gain some. Protein's empty-request guard came with it; it
cannot fire on the metadata side (`snap_idx` wraps to 0 and the caller returns on an empty cache).

**Revisit** if a third subset tab wants a third wording, which would mean the label is carrying
too much.

---

## 2026-09-17 - The event-plot Model half promotes, and the projection difference was vestigial

**Decision.** The two subset tabs' event-plot Model half (`resolve_event_ids`, `load_events_by_id`,
`load_filters`/`save_filters`) lives on a new `MetaSubsetTabModel`, with the projection narrowed to
`id` for both: nothing read Protein's extra `event_id` column (narrowing it failed only 7 tests,
all on query text). A new base rather than `MetaModel` (Kyle, 2026-09-17): the three timeseries
tabs have no events table to query and no filter file to write.

**Revisit** if a third tab becomes database-backed, which would make the base's membership
a question rather than a pair.

---

## 2026-09-15 - The barcode search stays a pruned walk, not an exact DP

**Context.** `_select_barcode_peaks` scores every legal set of `Number of peaks` type-1
candidates, which is exponential in how many candidates fall inside one `max_distance`
window.

**Decision.** Keep the depth-first walk with its two exact prunes and the
`BARCODE_SEARCH_NODE_CAP` bound. An exact `O(N*d^2*k)` DP over `(prev, last, count)` was
built and discarded.

**Evidence.** The DP agreed with the walk on 400 random events but ran **2-12x slower at
every size measured**: the cost prune fires almost immediately on a near-ideal barcode,
while the DP always pays its full state space. Walk cost per event runs ~70 us on a clean
4-peak barcode, ~500 us at 16 candidates with `Number of peaks` 6, and ~8.5 ms on a
40-candidate event with the window opened wide.

**Separately, what the objective can and cannot discriminate.** The search is exact
(verified against brute-force enumeration); whether it prefers the *true* barcode is a
different question. Recovery of a planted 4-peak barcode over 60 random events per cell:
100% with no strays at any jitter, 95% with 2-4 strays, 85-90% with 8, and **43% with 16
strays** at +/-3 us jitter on a 45 us period (3% at +/-12 us). Strays there carry ECDs
uniform over 0.3-6.0 against a label ECD of 2.0, so some sit essentially on the label
value; real folds and blips should separate more easily.

**Revisit** if a real dataset is peak-dense enough to hit the node cap routinely, which
the log names, or if the weights prove unable to separate real strays.

---

## 2026-09-15 - Prominence classification is fitted on log values, accepting a new failure mode

**Context.** The upper normalized-prominence population is right-skewed; a log-normal was
measured to beat a Gaussian on it by 24% RMS. Fitting a log-normal component directly
would break the six-element `params` contract shared by the plotting code and all three
classifiers, so the input is transformed instead (`PROMINENCE_FIT_LOG_SCALE`).

**Decision.** Fit `log10(normalized_prominence)`, and accept that the log fit can fail
outright where the linear one only degraded.

**Evidence.** Synthetic double-log-normal data, 600 peaks per trial, medians 0.2 and 0.6,
sigma_log 0.45, 12 trials: the linear fit returned `n_components = 1` in **10 of 12**
trials and recovered the true classes **61%** of the time, against **1 of 12** and **85%**
on the log scale. The cost is that the log fit raised "could not fit a double Gaussian"
in **2 of 12**, where the linear fit never did - an exception classifies nothing at all
rather than degrading to a coarser rung. Poisson-weighted `curve_fit` was also measured on the
same real data and made the fit worse unless paired with tail trimming, where the pairing is
cliff-edged; do not revisit it alongside this.

**Revisit** on the first real dataset moved onto this scale; `PROMINENCE_FIT_LOG_SCALE =
False` restores the linear fit for a side-by-side.

---

## 2026-09-15 - `num_sublevels` stays in the events table

**Context.** Four event fields and one sublevel field became `PRIVATE_EVENT_METADATA` /
`PRIVATE_SUBLEVEL_METADATA` and are no longer persisted. `num_sublevels` was considered
alongside them and kept.

**Decision.** Leave it. It is not the plugin's to drop.

**Evidence.** `MetaEventFitter._define_metadata_types` injects it after the plugin's dict
is built, and it is a hard-coded `NOT NULL` column in `SQLiteDBWriter`'s `CREATE TABLE
events` alongside `start_time` and `event_id`. Suppressing it plugin-side would leave the
writer inserting no value into a `NOT NULL` column.

**Revisit** only as part of a wider breaking change that moves both the ABC's injected
fields and the writer's fixed schema.

---

## 2026-09-14 - A raw SQL filter runs as written, and its scope is the user's (superseded 2026-10-10)

**Context.** A raw filter is a complete `SELECT`, but every plot path passes it where a
WHERE body is expected, so it is refused at six call sites (2026-09-12). Making it work was
framed as teaching `MetaDatabaseLoader` to *scope* a user's `SELECT` to the experiment and
channel selection.

**Decision** (Kyle, 2026-09-14). No scoping and no rewriting: validate the text, then pass it
to `query_database_directly` exactly as written. A raw filter ignores the selection tree, and
the user is responsible both for selecting the rows they mean and for projecting every column
the downstream plot reads.

**Evidence.** `query_database_directly` already takes a complete statement; scoping one
means wrapping it as a subquery, which changes what columns reach the plot and puts a
generated clause around text the user wrote. Withdrawing raw filters from the UI was priced as
the smaller alternative before this ruling.

**Revisit if** users need a raw filter restricted by the selection tree, or nobody turns out
to have a filter only expressible as raw SQL - then withdrawing it is cheaper than building it.


**Superseded 2026-10-10** (Carolina, approved by Kyle): a raw filter follows the Scope selection,
without the user knowing database ids. First built as a wrapper, `SELECT * FROM (<query>) WHERE
<selection>`, then replaced by placeholders: `:experiment_id` and `:channel_id` in the query are bound
to the selected pair, one channel at a time, so the scope sits inside the query. The wrapper applied
the selection after the query, so it disagreed with it: on a real database `LIMIT 5` gave two
channels 3 and 2 rows, an ungrouped aggregate landed on one channel, and the query had to return the
scope columns, with ten safeguards (about 760 lines) around that. Placeholders trade that for two gaps,
both warned about: a query that omits them ignores the selection, and one that scopes only a subquery
leaks rows (counted when the result has the columns). Events are named by
`(experiment_id, channel_id, event_id)`, not `id`, which is a different row in each table: a
sublevel's `id` that was also a same-channel event once loaded the wrong events silently. A
sublevel's key is its parent event's, so a join is safe. Only a read is run: the loader's
validator accepts any statement, and `WITH x AS (SELECT 1) DELETE FROM events` emptied a scratch
database (Python's SQLite module opens a transaction only for statements that start with
`INSERT`/`UPDATE`/`DELETE`, so it committed). Poriscope refuses any writing keyword, and the loader's
two read connections set `PRAGMA query_only = ON`. Measured on 600,000 events (300,000 per channel, `events` table only): one channel reads in 0.54 s raw against 0.93 s Assisted, and the navigation list takes 2.7 s raw against 1.0 s, the difference being the check that every key exists in `events`; both are paid when the filter or channel changes. Re-measured 2026-10-16 on the real schema (with its `UNIQUE (experiment_id, channel_id, event_id)` index), 300,025 events in one channel: the navigation list takes 2.1-2.2 s raw against 1.3 s Assisted, about 1.7x rather than 2.7x; the guide states only the bound. Export Subset - CSV takes a raw filter as one subquery per selected channel, `e.event_id IN (SELECT event_id FROM (<bound query>))` pinned to that experiment and channel, built after the plot checks pass for it; unrolling keys into an id list was rejected because its text grows with the subset. An unscoped query is refused for export, since it would write the same events for every channel. **Revisit if** users keep omitting the placeholders.

**Later, same entry** (Carolina, 2026-10-16). A query that uses only one placeholder, or none, is not refused: it runs, the panel says what each dataset now holds (that channel number from every other experiment; every channel of the experiment; or everything the query finds), and a column plot's legend says "(rows not limited to this experiment and channel)". The Scope starts with everything ticked and always keeps one channel, so there is no empty-scope case to design for. No text check for an unbracketed `OR`: only a parser can say whether it escapes the scope, a viewer would not warn either, and a raw user is expected to know that `AND` binds first. The existing leak warning covers it when the result carries `experiment_id` or `channel_id`, and the guide says to bracket every `OR`.

**Placeholder form** (Carolina, 2026-10-16). The names are `:experiment_id` and `:channel_id`, the colon form SQLite uses for named parameters and the names of the columns they stand for. There are two because the Scope is exactly an experiment and a channel. They exist because a user cannot be expected to type database ids: an experiment's `experiments.id` need not follow the order or numbering of the names the Scope shows, so ids written by hand are error prone and give a plausible-looking wrong plot. They are replaced by the whole numbers Poriscope looked up for the pair, never by user text, and text inside strings, quoted names and comments is left as written. The wrapper (`SELECT * FROM (<query>) WHERE <selection>`) was tried first and dropped as over-engineering: preventing its edge cases (a `LIMIT`, an aggregate, the scope columns) took ten safeguards and about 760 lines, and placeholders avoid them by putting the scope inside the query. The gaps placeholders leave are covered where they can be detected: a missing or partial placeholder by the panel warning, the legend label and the export refusal; a scope only in a subquery, or an unbracketed `OR`, only when the result carries `experiment_id` or `channel_id`. **Revisit if** omitting the placeholders, with the legend label and the panel warnings, is still not enough and users get wrong data, or a third thing needs binding.

---

## 2026-09-14 - The logscale helper lives on MetaModel

**Decision.** The log-scale-and-filter helper (`MetaModel.logscale_and_filter_columns`) lives on
`MetaModel`, not on `MetaView` and not as a module-level function in `poriscope/utils/`. It is not
a pure array transform: it reports dropped-point counts on the status panel through
`add_text_to_display`, which needs `self` (pinned in `tests/unit/models/test_meta_model_logscale.py`).
Leaving a wrapper on `MetaView` was rejected because it would put numpy back on the published plugin
base.

**Revisit if** the helper stops reporting to the status panel, at which point a plain function would
do.

---

## 2026-09-14 - Dead code the refactor exposes comes out with it

**Decision, Kyle's call.** Dead code the current change exposes is removed in the same commit,
not filed. "Dead" is demonstrated, not asserted: no production callers, no signal connections, and
where only tests still reference it, say so - a slot reached only by its own tests (passing against
a `MagicMock`) looks alive. A removal from a `Meta*` base is breaking and is called out in
`changelog.md`; since 2026-11-12 any breaking change makes the release major.

---

## 2026-09-14 - `set_heatmap`'s export reshape stays in the View

**Context.** `MetadataView.show_heatmap` (formerly `set_heatmap`) turns the Model's heatmap into the
long-form CSV rows: `np.meshgrid(x, y)`, flatten, undo the log2. Those rows leave the View through
the plot cache, so the leaves-the-View test says data, while the code only reshapes the Model's own
output for one consumer.

**Decision, Kyle's ruling.** It stays in the View; `calculate_heatmap` keeps returning one shape.
`MetadataView` therefore keeps numpy, a recorded floor (it is on the MVC allowlist). Moving it would
make `calculate_heatmap` return two shapes of one result, the "pile of extras" the governing test
rules out; replacing `meshgrid` with comprehensions is slower and harder to read. This is not a
general licence: domain computation from that tab went to `MetadataModel`.

**Revisit if** the export ever wants the heatmap in a form the drawing does not, at which
point the two consumers have genuinely diverged and the Model is the right place for the
second one.

---

## 2026-09-14 - Where the View/Model line falls for plotting numerics

**Decision.** The test is **whether the value leaves the View**, not whether it is derived from the
data. A time base is data (the x-coordinate of every point, cached and exported to CSV), so the
Model builds it. Axis limits never leave the View, so they stay, and their numpy went away instead
(`math` and `bisect`, equivalent to the numpy bounds on 2,000 randomised cases with zero mismatches).
"Property of the data" is the wrong test: the PSD roll-off index is one, and useless outside the axis
it bounds (sent to the Model, then reverted). Pure styling stays in the View.

**The governing test, Kyle 2026-09-14.** *"The point of MVC separation is responsibility
separation and clean, maintainable code, and that should be the basis for how we decide.
The litmus test is this: does moving it to the model create complexity where it is not
needed? Does removing an import create complexity where it is not needed?"* So **where the
View is the only consumer of a calculated quantity derived from the data, source the data
from the Model and do the visualisation calculation in the View** rather than have the
Model hand back a pile of extras nothing else wants. Rule 2's remaining numpy is therefore
settled per site by judgement, with the genuinely ambiguous ones put to Kyle rather than
guessed - and **the computation still moves**: histogram construction and the Monte Carlo
ensembles are not drawing responsibilities by any reading.

**And numpy in a View is not itself the problem** (Kyle, 2026-09-14). Some array
manipulation is genuinely a drawing responsibility, and there is nothing wrong with the
import when that is what it is for. Rule 2 is aimed at *the View doing the Model's job*,
which for numpy the gate cannot tell apart statically - it can see the import, not the
intent. So rule 2's target for numpy is **not necessarily 0**: a genuinely view-side site is left
and recorded as a floor, or sheds the import for free. scipy, sklearn, hdbscan and
`fast_histogram` are never a drawing responsibility, and building a DataFrame is not either.

**Revisit if** a View needs a derived value that is genuinely consumed outside it, which
would put it back on the Model side of the line.

---

## 2026-09-14 - Boundary rule 2 counts computation, not annotations

**Decision.** A forbidden import in a View counts only if a name it binds is loaded outside an
annotation: an import that only writes a type describes arrays the loader really hands the View,
and dropping it means lying about the parameter or adding a marshalling hop. Exempting
`numpy.typing` *by name* was rejected: `npt.NDArray[np.float64]` needs both imports, so it would
leave a false positive. The exact rule is in `scripts/check_mvc_boundary.py`'s docstring. The
allowlist went 14 -> 8 that day; it now holds two entries, `MetadataView` and `ProteinView` numpy.

**Revisit if** a View reaches a forbidden library through a module-level type alias or a
string annotation, neither of which the annotation scan sees.

---

## 2026-09-13 - `subset_filters` stays on the View; the Controller stops reaching into it

**Decision.** The `subset_filters` dict stays on `MetaSubsetTabView`; the Controller asks through
View methods (`get_subset_filters`, `restore_subset_filters`) rather than mutating it.

**Evidence** (at `3d1d457f`). No Model reads it: query construction receives one filter's *text*.
It has 16 synchronous View reads that need the value inside the same call (11
`get_selected_filters()` at plot and export entry points, plus dialog checks and saving). No
boundary gate moves either way, and the move would have cost 165 test references.

**Rejected.** A View-side cache over a Model copy stores the dict twice, the stale-read shape the
refactor removed everywhere else. Splitting all 16 readers into two-phase intents was priced at 11
plot entry points and 4 dialogs each cut in half.

**Revisit if** a Model ever needs the filter set rather than one filter's text - a headless
or scripted mode that applies named subsets without a GUI is the plausible trigger - or if
`get_selected_filters` stops being the only synchronous consumer on the plot path. The
honest reading today is that `subset_filters` is user-authored widget configuration, the
same category as the ticked channels and selected columns the refactor leaves on the View
everywhere else, and not domain state that happens to be in the wrong place.

---

## 2026-09-13 - ProteinModel's fit returns the fitted curve, not just the parameters

**Context.** The protein tab's double-gaussian fit moved to `ProteinModel`.
`_double_gaussian`, the model function `curve_fit` is handed, had three further callers
in `ProteinView` that evaluate the fit for drawing. Moving only the fit would have left
the View importing numpy to evaluate a model it no longer owns.

**Decision.** `fit_histogram` returns `(popt, curve)`, the curve evaluated at the bins
that were fitted, and `_double_gaussian` moves with the fit.

**Evidence.** All three View sites evaluate at exactly the x the fit was made on
(`plot_data["Normalized Current"].values` in every case), so the curve the Model can
compute is the curve every caller wanted. No site needed the model function for anything
else. A test pins that the curve is drawn as handed over, so reintroducing a View-side
evaluation would fail rather than merely duplicate.

**Revisit if** a caller ever needs the fit evaluated on a *different* grid - a smooth
overlay at higher resolution than the histogram, say - at which point the model function
is wanted as well and should be exposed on the Model rather than copied back.

---

## 2026-09-12 - The trace plot trims its own request; the reader's clamp is not restored

**Context.** The merge from `develop` made `MetaReader.load_data` raise `ValueError` on an
out-of-bounds request instead of clamping it (declared **Breaking** in `changelog.md`).
Nothing between the Raw Data tab's time inputs and the reader bounds the request -
`RawDataView._validate_plot_parameters` only checks the values are present - so a range
running past the end of a file went from drawing what existed to drawing nothing, with the
reason reaching only the log.

**Decision.** `RawDataController._bounded_length` trims each channel's request to that
channel's length before asking, and reports on the status panel both when it trims and when
the range starts past the end. The reader's stricter contract stays.

**Evidence.** Measured against a real `BinaryReader1X` over a 2 s synthetic recording: a
request for 0-4 s, one starting at 3 s, and one overrunning the final sliver all raise
`ValueError` now. Every *other* caller of `load_data` already trims against
`get_channel_length` and is unaffected - `MetaEventFinder._find_events:426`
(`if end > total_samples: end = total_samples`), that finder's last-event padding at `:609`,
and `MetaReader.continuous_read:372`. Confirmed empirically for the finder: driven over a
whole file, all three finders leave ~198,000 samples of headroom at both ends. The trace plot
was the only caller with no bound of its own, which is why the fix belongs in the tab and
uses the same `get_channel_length` idiom the other three already use.

**Revisit if** a second tab grows a direct `load_data` call, at which point the trim wants to
be shared rather than copied.

---

## 2026-09-12 - The flow harness kills a tab's workers, because the app does

**Context.** CI aborted at **exit 134** (`Fatal Python error: Aborted`) during
`sample_metadata_db` fixture setup, with a second thread carrying `<no Python frame>`.
The same fault had been recorded in `future_fixes.md` as an unexplained intermittent
**exit 127** on Windows, reproducing on the metadata export flow module.

**Decision.** `Triad.close()` now kills each tab's workers with `exiting=True` *before*
closing the data plugins, which is exactly what `MainController.handle_about_to_quit`
does. It previously did only the second half.

**Evidence.** The tab's worker threads live on its `MetaModel`; `handle_exit()` closes the
*data plugin* model and touches none of them. So a flow test that started an export left a
live `QThread`, and Qt aborts when it destroys one. Measured:
`test_metadata_export_flow_no_gui.py` exited 127 on **three runs out of three** while
reporting `8 passed`; with the fix, **zero out of four**, and the integration directory
three out of three clean. Reverting it fails both new tests in `test_triad_teardown.py`.
**CI green on `7fbeca37`**, which is the confirmation that counts - the abort had only ever
been seen on Linux under Xvfb, so the local runs could narrow the cause but never close it.

It read as flakiness because the process dies after the summary line prints, with no failing
test, and wherever in the integration block a worker-starting module happened to run.

**Revisit if** a flow test ever needs a worker to outlive its triad. Nothing does today,
and the shutdown blocks by design.

---

## 2026-09-12 - The protein tab's raw-filter branch is deleted, because it never worked

**Context.** `ProteinView._build_load_event_data_args` - converted to
`ProteinController._scope_raw_subset_query` earlier the same day - scoped a raw SQL subset
filter and handed it to `load_event_data` as its `conditions` argument. Kyle could not
construct any raw filter that produced a plot, and proposed removing the branch.

**Decision.** Removed, along with the three signal arguments that fed it. Raw filters are
refused at the plot entry points instead (`MetaSubsetTabView._refuse_raw_filters`, six call
sites across the two tabs). Creating, validating, saving and loading them is unchanged.

**Evidence.** There is no valid query, and that is a property of the plumbing rather than of
the filter. `load_event_data` passes `conditions` straight to `construct_event_data_query`,
which splices it in after `WHERE`, so a complete `SELECT` becomes
`... WHERE SELECT * FROM events WHERE ...`. Measured against a real `SQLiteDBLoader`:
SQLite reports `near "SELECT": syntax error`, the builder returns `("", debug)`, and the
generator yields **0 events** where the same filter as an ordinary WHERE body yields 10. So
the branch has never produced a plot, and the earlier commit's fix to *what it displayed*
was a fix to a dead path.

**This also voids the queued "share it with the metadata tab" item**, which read the metadata
tab's lack of a `_raw` branch as a gap. It is not a gap: the branch being shared does not
work. Raw filters are refused on both tabs now rather than half-implemented on one.

**Revisit if** raw filters are wanted for real, which is a feature build rather than a fix:
the filter would have to travel as the whole query rather than as a WHERE-clause body, which
is a `MetaDatabaseLoader` change and wants its own plan.

**Superseded 2026-10-16** (Carolina): raw filters are wanted and now work, as a complete query run
with the scope inside it rather than as a WHERE-clause body (see the 2026-09-14 entry). So
`_refuse_raw_filters` and its six call sites are removed, and the filter's name goes back onto the
signals, on all of them rather than only Protein's, as it was before this entry (see the 2026-10-16
entry on the filter's name).

---

## 2026-09-12 - A nested function can hide pydoclint's raise checks, so hoisting one can surface real violations

**Context.** Collapsing three byte-identical nested `tuple_builder` helpers in
`MetaDatabaseLoader` onto one `_id_tuple` method made `pydoclint` fail with DOC501/DOC503 on
`construct_event_data_query` - a method whose body and docstring the commit never touched.

**Decision.** Treat the violation as real and document the `KeyError`, rather than reading the
new failure as something the cleanup broke. Nothing is added to
`.pydoclint-baseline.txt`, which stays empty.

**Evidence.** Bisected directly: `git show HEAD:...MetaDatabaseLoader.py` passes `pydoclint`;
the same file with only the nested helpers removed and the calls re-pointed reports
DOC501/DOC503 on `construct_event_data_query`. The method has raised an undocumented
`KeyError` for an unknown experiment name since long before this branch. A minimal
two-function probe did *not* reproduce the blindness, so the trigger is narrower than "any
nested function" and was not chased further - what matters is that the check can be silently
absent.

**Consequence worth knowing:** `CLAUDE.md`'s preference for module- or class-level functions
over nested ones has a gate consequence as well as a readability one, and **a pydoclint pass
is not evidence that a function containing a nested `def` documents its exceptions**. Same
family as `check-class-attributes` (2026-08-25): an instrument that is quietly not looking.

**Revisit if** pydoclint is upgraded - re-run the bisection above and delete this entry if the
blindness is gone.

---

## 2026-09-12 - An empty subset is counted before the export worker starts, not raised inside it

**Context.** A CSV subset export whose filter matched no rows ran the progress bar to 100%,
consumed the next `Subset_N` name, and reported only a worker-thread WARNING that names the
loader twice and not the subset. `changelog.md` had claimed this fixed since `e7ce9ba0`.
`export_subset_to_csv` is a **generator function**, so `call()` only constructs it: every
guard in its body, its own `No events found matching subset criteria` included, fires on the
worker's first advance - after `MetadataController`'s `try/except` has passed and after
`on_subset_export_started` has advanced the index.

**Decision.** `MetaDatabaseLoader.count_subset_events` answers "will this write anything?"
synchronously, and `MetadataController.export_csv_subset` calls it before staging a worker.
The events query moved into `_build_subset_events_query`, which both the count and the export
use, so the two cannot drift into asking about different subsets.

**Evidence.** Measured on real synthetic databases of 25/250/1000 events, 15 runs each: the
count is **7-9 ms, flat in event count**, against 46-80 ms to the export's first yield and
32 ms-1.3 s for the rest. Three tests fail when the refusal is removed - two flow tests
driving the real loader and one Controller test. The pre-existing Controller test
`test_a_refused_export_stages_nothing_and_says_why` passed throughout, because its model's
`call` raised synchronously, which the real generator-returning plugin can never do.

**Rejected: priming the generator** (`next()` in the Controller, hand the started generator to
the worker). It fixes both halves with no new method, but `SerializeDecorator` holds
`BaseDataPlugin.lock` - an owner-bound `RLock` - across `yield`, so a generator started on the
GUI thread and finished on a worker would raise `cannot release un-acquired lock` for any
plugin whose `force_serial_channel_operations()` returns `True`. None does today, which makes
it a latent trap rather than a live fault. Kyle's standing rule: avoid cross-thread anything
where possible.

**Revisit if** a subset's events query ever becomes expensive enough that 7-9 ms on the GUI
thread is felt - at which point the count wants to move onto the worker with a way to report
back, not to be deleted.

---

## 2026-09-09 - Reader and loader leak checks use different patterns, deliberately

**Context.** Extending `test_writers.py`'s leak check to readers and loaders. An earlier
scoping note (2026-08-31, now removed from `future_fixes.md`) claimed a reader's
`close_resources()` "does not reliably release its `numpy.memmap` handle immediately" on
Windows. Re-tested properly before writing the real check: that claim was a testing
mistake, not a defect - the probe never dropped its own reference to the reader before
checking, so of course the file stayed open. With `del` + `gc.collect()`, release is
100% reliable across all 7 readers, confirmed empirically.

**Decision.** `MetaReader.close_resources()`'s own docstring says a memmap-backed reader
"need not explicitly close" it - the base class contract is "GC will handle it," not
"closed means released immediately." So `test_reader_releases_its_input_file`
(`test_readers.py`) asserts the weaker, correct thing: the file becomes releasable once
nothing references the reader (`del` + `gc.collect()`), not that `close_resources()`
alone releases it. Loaders got the stronger check instead -
`test_loader_releases_its_input_file`/`test_db_loader_releases_its_input_file`
(`test_eventloaders.py`/`test_dbloaders.py`) assert immediate release after
`close_resources()` alone, matching the writer pattern - because a SQLite connection is
not something the garbage collector reclaims for free the way a memmap is, and measured
directly: all 3 loaders (`SQLiteEventLoader`, `SQLiteDBLoader`, `SQLitePeakDBLoader`)
already close their connection explicitly and release immediately.

**Evidence.** Probed both ways for every reader and loader before writing either test:
readers fail immediately after `close_resources()` while still referenced, and pass
100% of the time once `del`ed and collected; all three loaders pass immediately, with
or without dropping the reference.

**Revisit if** a reader test written against this weaker contract ever needs to prove
something stronger - at that point the difference from the loader contract stops being
free, and the two would need to converge or the difference re-justified per plugin.

---

## 2026-09-09 - An unresolvable experiment stops an event plot rather than running unscoped

**Context.** A failed experiment-name lookup left the id `None`, and the event-plot query
`SELECT id FROM events` ran with no scope at all (Metadata 2026-09-09, Protein 2026-09-12).

**Decision.** Both subset tabs report and return instead (now one copy,
`MetaSubsetTabController`, "has no experiment named ..."). Channel scoping is applied independently
of the experiment lookup. A user-visible change on the protein tab, called out in `changelog.md`.

**Evidence.** `event_id` is unique only within an experiment and channel, so an unscoped match
returns whichever row shares the number. Reverting the guard fails
`test_an_unresolvable_experiment_stops_the_plot`.

**Revisit if** a database legitimately holds events whose experiment is unknown, in which
case the fallback needs to be scoped by channel rather than unscoped.

---

## 2026-09-08 - `ci-branches.yml`/`ci-fork-pr.yml` install `poriscope` itself, not just its dependencies

**Context.** The `settings-schema` pre-commit hook (`scripts/check_plugin_schemas.py`) imports
`poriscope` directly, and these two workflows installed only the requirements files, so the hook
failed with `ModuleNotFoundError`.

**Decision.** Install the package (`pip install -e ".[dev]"`) with the
`|| pip install -r requirements-dev.txt` fallback, which matters for `ci-fork-pr.yml`: a broken fork
`pyproject.toml` should degrade rather than fail the job. A `sys.path` shim in the scripts was
rejected: it diverges from the documented setup and skips exercising `pyproject.toml`'s real
metadata the way an install does.

**Revisit if** another workflow needs `poriscope` importable outside pytest.

---

## 2026-09-08 - The status panel shows the applied query, deduplicated, not the validation one

**Decision** (Kyle). The status panel echoes the query that actually runs when a subset is
fetched (`MetaSubsetTabController._echo_applied_query`, both subset tabs), and only when it differs
from the last one shown: a plot builds one query per (experiment, channel), so echoing each would
bury the panel. Kyle chose this over "every query" and "first per plot". Creation-time validation
stays as a pre-check with immediate feedback.

**Evidence.** The validation verdict does not depend on the selected columns: identical verdicts
for four valid and two broken filters across a one-column set, a histogram, a two-table scatter and
a three-table 3D scatter.

**Revisit if** users want the query for every experiment/channel, which would key the dedupe on
the scope as well as the SQL.

---

## 2026-09-08 - The Controller picks the filter-validation columns, and asks for events only

**Decision.** A filter is validated against one **events** column the Controller gets from
`get_column_names_by_table("events")`, not a hardcoded triple or `available_columns[:3]` (whose
order depends on writer insertion order and an unordered `SELECT`).

**Evidence.** Join counts with one events column: 0 for `duration < 300`, 0 with no conditions, 1
for a filter that references sublevels or experiments, against 2 in every case for the triple.
Joins follow the *conditions*, so a filter naming all three tables still validates against all
three; `nonsense_column > 1` is still refused. `["event_id"]` is unusable (in `redundant_cols`, no
table for `get_table_by_column`).

**Revisit if** the validation query and the applied query are unified.

---

## 2026-09-08 - Subset-tab filter methods are shared on the base; rejections go in a modal

**Decision** (2.0.0 promotions). `_delete_filter`, `show_edit_filter_dialog` and the rest of the
filter handling are concrete on `MetaSubsetTabView`, reaching the panel through `_subset_controls`;
the two tabs' copies differed only in the panel's name. A rejected raw filter is reported in a
`QMessageBox.warning` on both tabs (the user's choice), not a status line, because the filter dialog
has just closed and a status line is missed. `tests/unit/_dialog_guard.py` is installed in the
views and controllers conftests, deliberately not at the root: the e2e suite opts into dismissal
through `auto_dismiss_message_boxes`, which a blanket patch would make vacuous.

**Revisit if** a third subset tab's filter widgets genuinely differ (make `_delete_filter` abstract
again), or the modal is being dismissed unread.

---

## 2026-09-08 - `_load_filter` promotes Protein's raw bypass, which fixes the metadata tab

**Context.** The last of the four methods Step 4a promotes, and the only one where the
divergence was a defect rather than a choice: only `ProteinView` let a filter whose name ends
in `_raw` skip `construct_metadata_query`.

**Decision.** Protein's version, so the promotion **fixes** the metadata tab rather than
merging two behaviours. The hardcoded validation triple both copies carried is replaced by
`_validation_columns`, promoted in the previous commit.

**Evidence.** The consequence of not bypassing was measured rather than assumed, and it is
not what the plan predicted. `construct_metadata_query` does **not** refuse a complete SELECT
passed as `conditions`: it emits `... WHERE SELECT e.dwell_time FROM events WHERE ...` with an
**empty debug message**, so `relay_query` takes the success path and commits the filter as
`<name>_raw_assisted` - renamed, and reclassified as assisted. The filter is not dropped, as
the plan said; it is silently mangled, which is worse to diagnose.

**Not fixed here:** the metadata tab has no `endswith("_raw")` branch in any plotting path, so
a raw filter selected there is still used as a WHERE-clause body. That is a larger gap, queued
in `future_fixes.md`, and Step 4a's commit 6 is where Protein's branch moves.

**Revisit if** raw filters are dropped from the metadata tab entirely, which would make both
the bypass and the queued gap moot.

---

## 2026-09-08 - `_rebuild_event_id_cache` merges to ProteinView's copy, with the guards reordered

**Decision.** Protein's behaviour on both tabs (the user's choice for the visible parts): reject a
result with no `event_id` column, name the scope in the empty-subset message, and label an unnamed
active filter with its expression. Emptiness is checked before the missing column: `pd.read_sql`
returns a zero-row frame that keeps its columns, so the order matters only for a columnless frame,
which is better reported as "no matching events" than as a malformed query.

**Revisit if** a loader plugin legitimately returns a subset without `event_id`.

---

## 2026-09-08 - A promoted subset-tab method reaches its controls panel through a property

**Decision.** An abstract `_subset_controls` property, one line per tab over its own panel name -
not a second attribute stored beside the panel.

**Evidence.** The stored-attribute version broke three tests that swap the panel for a `Mock` under
the tab's own name, leaving the stored copy on the real widget; the property broke none, and there
is no second reference to go stale.

**Revisit if** a promoted method needs something only one tab's panel has.

---

## 2026-09-06 - Shared tab behaviour goes in a base class; no new mixins

**Context.** Step 3b could have shared the Metadata/Protein code through a
`SubsetFilterMixin` instead of a `MetaSubsetTabView` intermediate. Mixins compose where
single inheritance does not, which matters because a few duplicate pairs cross the tab
families - `update_plot_features` is byte-identical between `EventAnalysisView` and
`MetadataView`, spanning both of Step 3's intended intermediates.

**Decision.** No new mixins. Shared analysis-tab behaviour goes into the `Meta*` base chain:
onto an existing base if it is stateless and self-contained, onto a new intermediate base if
it carries state, abstract hooks or new imports.

**Evidence.** `WalkthroughMixin` is the codebase's only mixin. 2.0.0 put it on `MetaView`'s
bases, so no tab declares it, but it stays a mixin because `MainView` and two dialogs outside
the `Meta*` chain host it (corrected 2026-09-27; the plan had been to fold it away). It is the
one sanctioned exception, and a second mixin would still leave two competing composition
mechanisms and no rule for choosing. The split above is what keeps `MetaView` - the published
plugin API, exported from `exposed.py` and documented as the extension point - from widening
with contracts most subclasses do not participate in: folding 3b's View half into it would
have put subset-filter state on every tab instance, forced `_delete_filter` and
`show_edit_filter_dialog` to be either abstract (breaking the other three tabs) or concrete
no-ops (a silent-override hazard), and pulled `SelectionTree` and `MultiSelectComboBox` into
all five tabs. Cross-family duplication is ~39 lines against ~639 within-family, so the
families are real; a stateless cross-family pair like `update_plot_features` goes on
`MetaView` itself.

**Revisit if** a third tab needs *part* of an intermediate's behaviour but not the rest, or
two intermediates must both supply behaviour to one tab. Either would mean the
single-inheritance chain has stopped expressing the structure. Raise it rather than acting on
it.

---

## 2026-09-06 - `poriscope/utils/` may import from `poriscope/views/widgets/`

**Context.** `MetaSubsetTabView` needs `SelectionTree` and `MultiSelectComboBox`, and before
Step 3b no module in `poriscope/utils/` imported from `poriscope/views/` at all.

**Decision.** Accepted. Shared bases may depend on shared widgets.

**Evidence.** It is the same direction Step 3f moves `walkthrough` in, and neither side
depends on a plugin package, so it is not the layering inversion rule 4 exists to catch.
`SelectionTree`, `multiselect` and `multiselect_filter` import nothing from `poriscope.utils`,
so there is no cycle. The alternative was leaving `show_selection_tree`,
`update_available_columns` and `_show_filter_info_dialog` per-tab, costing real duplication to
avoid a dependency that is correct.

**Revisit if** a `views/widgets/` module ever needs something from `poriscope/utils/`, which
would close the cycle.

---

## 2026-09-06 - Step 3b's shared bases are named `MetaSubsetTab*`, not `MetaDatabaseTab*`

**Context.** `Meta` does not mean the same thing in every `poriscope/utils/` base. In
`MetaView`, `MetaController`, `MetaReader` and most of the rest it marks an abstract base
class. In **`MetaDatabaseLoader` and `MetaDatabaseWriter` it means metadata** - those plugins
read and write databases of metadata *about events*: duration, blockage, sublevels. The two
senses are not distinguishable from the name.

**Decision.** The shared bases for the Metadata and Protein tab triads are
`MetaSubsetTabView`, `MetaSubsetTabController` and `MetaSubsetTabControls`. The plan had said
`MetaDatabaseTab*`; that name is retired.

**Evidence.** Read as intended it is *Meta* + *DatabaseTab* + *View*; read as written it is
*MetaDatabase* + *TabView*, which puts it beside the event-metadata plugin bases and borrows
the wrong sense of the prefix. `MetaSubsetTab*` names what the two tabs actually share - both
build subset filters over a queried database - and collides with nothing.

**Revisit if** the `Meta` ambiguity is ever resolved by renaming the metadata-sense classes.
Until then, do not begin a new analysis-tab base with `MetaDatabase`, and name a base for the
behaviour its subclasses share rather than for the storage they sit on.

---

## 2026-09-06 - The MVC boundary's layers are derived from filenames, not listed

**Decision.** `check_mvc_boundary.py` classifies every module under `poriscope/` by directory or by
filename suffix (`*View.py`/`*Controls.py`, `*Controller.py`), not by a hardcoded list: the list
of ten files went stale and a method promoted into `poriscope/utils/` left the measurement unfixed.
Rule 4 is not widened to `poriscope/utils/` (`plugin_schemas.py` imports `poriscope.plugins` on
purpose). The script's docstring carries the detail and the measurements.

**Revisit if** a View- or Controller-layer module is added under a name that matches neither
test. `measure()` raises on an empty layer, but a single unclassified module is silently
unmeasured - which is the one weakness a derived scan has that a list does not.

---

## 2026-09-06 - The DataFrame log-scaling helper is deleted, not merged into the array one

**Context.** `MetaView` carried two log-scaling helpers implementing one algorithm: an array form
(8 callers) and a DataFrame form (1 caller, Clustering).

**Decision.** Keep the array form (now `MetaModel.logscale_and_filter_columns`); delete the frame
form and adapt its one caller to pass arrays and rebuild the frame.

**Evidence.** Dtype handling and status messages were identical when run side by side; the two
real differences (frame-wide `dropna()`, tolerance of a text column) were inert at the only caller.
Direction was chosen by caller count, which also took `import pandas` off `MetaView`. Performance
did not decide it: the frame form measured 2.7-4.7x slower only because it re-sliced per column, and
a single-slice rewrite reached 1.06x at 1M rows.

**Revisit if** a caller needs to row-filter a frame carrying non-numeric columns alongside the logged
ones: add a frame adapter over the array core, not a second algorithm.

---

## 2026-09-06 - `createButton`'s majority version is promoted, `setStyleSheet("")` included

**Context.** `createButton` was byte-identical in four of the five `*controls.py` files;
`eventAnalysisControls.py` omitted the trailing `button.setStyleSheet("")  # Resetting to
default style` the other four ended with. Step 3a promotes one copy to `MetaControls`, so
one of the two behaviours had to be chosen. `tests/unit/views/test_duplicated_helpers.py`
pinned the divergence precisely so the choice could not be made silently.

**Decision.** Promote the majority version, reset included. EventAnalysis's four buttons
gain the call; the other four files are behaviourally untouched.

**Evidence.** The call is inert, measured rather than argued. Two `QPushButton`s under a
parent carrying `QPushButton { color: rgb(1,2,3); }`, one given `setStyleSheet("")` and one
not: both report `styleSheet() == ""` and both still resolve `ButtonText` to
`(1,2,3,255)`. So an empty stylesheet neither differs from never having set one nor blocks
a parent's cascade - the comment "Resetting to default style" describes something the call
cannot do. Separately, no `createButton` product in any of the five files is given a
stylesheet afterwards, so nothing downstream depends on either behaviour.

**Revisit if** a controls panel starts applying a stylesheet to a `createButton` product,
or a parent stylesheet is introduced that a child is meant to opt out of - the second needs
a real reset (an explicit rule, or `setAttribute`), not an empty string.

---

## 2026-09-05 - The 2.0.0 structural gates are pytest tests, not pre-commit hooks

**Context.** Step 2 adds two "a count must not grow" gates: an `ast` MVC boundary check and a
duplication ratchet. The repo has precedent for both mechanisms - `plugin-module-level` and
`pydoclint --baseline` are local pre-commit hooks, while `test_plugin_compliance` is a pytest
test that reflects over the whole plugin tree.

**Decision.** Both gates are **pytest tests**, with their measurement logic in `scripts/` so it
stays runnable on its own. Baselines are checked-in JSON compared for **exact match**, not `<=`.

**Evidence.** Only a test is enforced by all four test-running workflows with no extra wiring:
`ci-branches.yml` and `ci-fork-pr.yml` run `pytest` but would each need the hook added
separately. Only a test appears in `--marker-stats`. Exact match rather than `<=` is what makes
a refactor commit record its own win - under `<=` a step that removes duplication leaves the
baseline overstated and the slack accrues silently.

**Revisit if / check for when touching this area:** a gate needs to block the commit rather than
the push (then it wants a hook as well, calling the same script); or the measurement becomes slow
enough to matter in a full run - all three ratchets are AST-only.

---

## 2026-09-04 - Worker generator failures report at WARNING on the panel, not as dialogs

**Context.** `EventWorker.process_generator` funnels every exception from a plugin generator
through one `except Exception` arm - deliberately, because per-type handling in that loop is
what let a failed analysis be logged as a successful finish. That arm logged at ERROR with a
traceback, and `QtHandler` is attached to the root logger at ERROR, so it raised a modal
dialog. Exporting a subset whose filter matched no events therefore met the user with a
traceback dialog framed as `Worker [...] failed`, for an ordinary empty result.

**Decision.** The arm reports at **WARNING** and sends the exception's message to the
`add_text_to_display` panel, via a new `Worker.add_text_to_display` signal relayed by
`MetaModel.emit_text_to_display`. The traceback still reaches the console and the log file
through `exc_info=True`.

**Why not special-case the empty result.** A generator cannot signal "nothing matched" versus
"this failed" without the per-type handling that loop must not grow, and data plugins are
plain ABCs with no Qt signals, so the loader cannot post to the panel itself. Telling them
apart at the raise site would have needed a new public counting method on
`MetaDatabaseLoader` for the View to call first - a contract change every database loader and
the plugin-compliance test would see, to fix a message. *That method was added on 2026-09-12 for
the empty-subset export after all (`count_subset_events`, see that entry); the WARNING rule stands
for every other failure.*

**The accepted cost.** *Every* worker generator failure now reports this way, not just the
empty ones: a corrupt database, a permission error writing the CSVs or a full disk becomes a
panel line rather than an interruption. Taken deliberately, on the grounds that `QtHandler`'s
own policy is that the user should be told on the panel rather than interrupted, and that a
traceback dialog is developer-facing. The log file keeps the full diagnosis either way.

**Revisit** if a failure class turns up that the user must not be allowed to miss. The fix
then is for that plugin to report it at ERROR itself, before raising - not to reintroduce
per-type handling in the worker loop.

---

## 2026-09-04 - A failed database query keeps returning None rather than raising

**Context.** `_load_metadata`, `load_metadata` and `query_database_directly` all used `None`
for both "the query matched no rows" and "the query could not be run", which made a
legitimately-empty table indistinguishable from a failure (subset export rejected an event
with no sublevels as "Failed to load sublevels data"). Splitting the two could have been done
either way round: empty frame for no rows and `None` kept for failure, or empty frame for no
rows and an exception for failure.

**Decision.** No-rows returns an empty DataFrame; **failure keeps returning `None`**, and the
annotations that claimed `-> pd.DataFrame` are corrected to `Optional[pd.DataFrame]`.

**Evidence.** Under the signal bus, a raising loader was swallowed by the dispatcher and the
caller read the previous call's answer off an attribute as this call's - worse than the
conflation being fixed.

**Revisit** when the emit-then-read pattern is gone, since raising on failure is then the better
contract. *Met: the bus was removed in 2.0.0 and every tab gets a return value from `call()`, but
the loaders still return `Optional[pd.DataFrame]` (`MetaDatabaseLoader.py:1412`, `:1527`, `:1591`).
"Raise on a failed query instead of returning None" is queued in `future_fixes.md` for 4.0, since it is a break.*

---

## 2026-09-04 - A subquery is opaque to condition rewriting, and both event caches reuse the query builder

**Context.** A saved subset filter had two consumers that disagreed about the SQL context it
is evaluated in. `construct_metadata_query` derives the joins the filter needs and qualifies
its columns against them; `MetadataView._rebuild_event_id_cache` and its `ProteinView` twin
spliced the same text into a hand-built `SELECT event_id FROM events`. So any filter naming a
sublevels column - `filtered = 5`, the natural way to say "every event with at least one
sublevel that matches" - worked for the subset and the scatter plots and failed as an unknown
column in the event viewer, where `query_database_directly` returned `None` and the caller
reported it to the user as "No filtered events found". Separately, `_qualify_conditions`
rewrote column references *inside* subqueries, so `e.id IN (SELECT event_db_id FROM sublevels
WHERE filtered = 5)` became `... WHERE s.filtered = 5`, silently correlating the subquery to
the outer row.

**Decision.** Extends the 2026-09-03 literal-skipping decision below: a parenthesised
subquery is opaque exactly as a single-quoted literal already was. `_split_on_opaque_spans`
protects both, and all three consumers - `_qualify_conditions`, `_references_column` and
`_find_ambiguous_id` - read it, which is what keeps them agreeing about what the outer query
refers to. A subquery names its own tables, so it needs no outer
alias and forces no join. Both event caches now call `load_metadata(["event_id"], filter,
{exp: [channel]})`, which routes through the same derivation, and `_build_where_clause` is
deleted from both views.

**Evidence.** Against a production database (191 events, 2499 sublevels, 35 of them
`filtered = 5`): before, *no* filter text worked in both consumers. `filtered = 5` and
`e.id IN (...)` saved and returned the right 35 rows for the subset but failed as an unknown
column in the event viewer, while the `id IN (...)`, `rowid IN (...)` and `EXISTS (...)` forms
the viewer accepted were all rejected at save time. After, `filtered = 5` and `e.id IN (...)`
each return the same 35 events in both. Aggregation inside a subquery
(`GROUP BY event_db_id HAVING COUNT(*) > 3`) also works in assisted mode now, which the user
guide had said was impossible.

**A failed query is still not an empty subset.** `load_metadata` returning `None` means the
query could not be built or run, which both caches log at ERROR so `QtHandler` raises its
dialog; an empty frame keeps the quiet status-panel line. Same split as the subset-export fix
above.

**Revisit if** a filter legitimately needs the outer row inside a subquery without naming it.
Today the user writes `e.id`, which is what SQL requires of them anyway.

---

## 2026-09-04 - get_column_units' empty-string conflation is left alone

**Context.** `get_column_units` returns `""` both when a column's `units` field is NULL and
when the column does not exist, and `None` only when the query itself failed
(`poriscope/plugins/db_loaders/SQLiteDBLoader.py:350`).

**Decision.** Not fixed. It is inert: every consumer erases the distinction anyway -
`metadatacontrols.update_column_units_label` collapses `None` and `""` to a single space for
display, and `ClusteringController` drops both on a falsy test.

**Revisit** if a caller ever needs to tell "this column has no units" from "there is no such
column" - the fix is then a distinct sentinel, and two tests pin both cases to `""`.

---

## 2026-09-04 - TimeRangeValidator is right to refuse a comma after "0-0"

**Context.** `TimeRangeValidator` splits on "," before filtering empty segments and then
tests `len(parts) > 1` to enforce that `0-0` appears alone, so typing a trailing comma after
`0-0` is rejected. The 2.0.0 plan recorded this as a defect ("the legal trailing comma in
`0-0,` is wrongly rejected").

**Decision.** Correct as it stands; changed nothing. `0-0` means the whole file and cannot
legally be combined with any other range, so no input that could follow the comma would ever
validate. And because this is a `QValidator` on a `QLineEdit`, `Invalid` refuses the keystroke
outright rather than merely disabling OK - which is the clearest possible feedback that the
range being typed cannot be extended.

**Revisit** only if `0-0` stops meaning "the whole file".

---

## 2026-09-04 - The mypy version skew is the cause of the "two disagree wildly" phenomenon

**Context.** Measured 2026-09-04, mypy was pinned three ways: `mypy==1.9.0` in `[dev]` and
`requirements-dev.txt`, mirrors-mypy `rev: v1.17.1` in the hook, and 2.3.1 in the working venv.

**Decision.** The declared pin is aligned to the hook (`mypy==1.17.1`), so a contributor running
mypy locally gets the gate's version. The hook stays the only gate. Alignment does not fix the
larger half of the disagreement, the hook's dependency blindness (see `CLAUDE.md` and 2026-08-24).

**Revisit if** the hook's `rev` is bumped - move the declared pin in the same commit, or the skew
silently returns - or if `additional_dependencies` are added to the hook.

---

## 2026-09-03 - `SQLiteEventWriter`'s two-connection commit split stays; tests must wait on rows, not tables

**Context.** `commit_events` calls `_initialize_database`, which opens its own short-lived
connection, creates `channels`/`events`/`columns`, and commits and closes immediately. It
then writes event rows on a second, longer-lived connection (`self.conn`) that only commits
once at `last_call`, at the end of the whole batch. `test_commit_events_writes_exact_schema`
polled `sqlite_has_tables(out_db, {...})` as its `qtbot.waitUntil` predicate - satisfied the
moment the first connection commits, which can be well before the batch's event rows are
written and committed on the second. This read 0 rows instead of 5 in one CD run
(`33438867072`, `release/1.7.0`, 2026-08-31) under full-suite CPU contention; it did not
reproduce in isolation or in the paired tag-push run of the identical commit seconds later.

**Decision.** Keep the two-connection design in `SQLiteEventWriter` as-is - it is not a bug,
the writer is correct regardless of when its tables become visible to an external reader.
Fixed the test instead: added `sqlite_row_count()` alongside `sqlite_has_tables()` in
`tests/e2e/_helpers.py` and made the wait predicate require
`sqlite_row_count(out_db, "events") == ds.num_events` too, so the test cannot observe a
"done" state before the batch's final commit lands.

**Why this is a standing risk, not a one-off.** The gap exists because commit happens on a
background `EventWorker`/`WorkerThread` fired via `run_generators`, decoupled from the click
that starts it, and nothing in `MetaWriter`/`MetaModel` exposes a "commit finished" signal a
test can await - so any e2e test against a writer plugin is reduced to polling the output
file for a proxy condition. `sqlite_has_tables` was already a fix for an *earlier* version
of this same race (it replaced polling on file existence); it still wasn't sufficient, since
table creation and row insertion are two different commits. The same shape of bug can
recur wherever a test infers "the write finished" from a partial signal instead of the
actual final state.

**Revisit if / check for when touching this area:**
- A new e2e test is added against `SQLiteEventWriter`, `SQLiteDBWriter`, or any other
  `MetaWriter` subclass that writes through more than one connection or commits - reuse
  `sqlite_row_count`, don't reintroduce a `sqlite_has_tables`-only wait.
- `MetaModel.run_generators`/`discard_generator` ever gains a real "batch finished" signal -
  tests should switch to awaiting that instead of polling the database file at all.
- Anyone consolidates `_initialize_database` and `_write_data` onto a single connection -
  re-check whether the race actually closes (it narrows the window but a background-thread
  write is still async relative to a polling test) before relying on it.

---

## 2026-09-03 - Tabs reach plugins through `MetaModel.call()` over pushed instances

**Context.** The string-keyed `global_signal` RPC was used as a blocking call (emit, then read the
answer off an attribute), and a failed dispatch left the caller reading the previous call's answer.
Tabs deliberately hold no reference to `MainController`, which keeps them pluggable.

**Decision** (2026-09-03, tightened 2026-09-07). `MetaModel.call(metaclass, key, method, *args,
**kwargs)` resolves from a local dict and invokes directly, so it returns or raises. Instances are
**pushed** to every tab (`MetaController.set_plugin_instances`) on each plugin lifecycle event, never
pulled or cached. `_get_plugin` is private, `call()` refuses a method name starting with `_`, and
`check_mvc_boundary` rule 5 counts the ways around both. No call-stack inspection. Names still go to
the Views for comboboxes: names for the UI, instances for the call path.

**Rejected.** A typed facade (`PluginAccess` ABC or `PluginResolver`): the string API is the
isolation, so no tab or plugin author needs app-shell internals. Caching on first use: a rename leaves
it on a dead key and a re-instantiate on a closed object, while a push refreshes on exactly those
events. Call-stack inspection: `inspect.stack` per chunk and per event; plugins legitimately hold
plugins (`MetaEventFinder` holds a `MetaReader`); worker threads start at Qt's thread entry; and it
would fail on a user's machine, not on the commit.

**Accepted cost.** `call()` returns `Any`, so mypy cannot catch a renamed plugin method. That is the
price of the string API; do not re-argue it.

**Revisit if** a tab needs to call another tab, or a tab genuinely needs a raw plugin instance (make
`_get_plugin` public deliberately then, and expect rule 5 to move).

---

## 2026-09-03 - Analysis tabs keep MVC mediation; no direct View-to-Model contact

**Decision** (2.0.0 scope ruling). Commands go View -> signal -> Controller -> `call` -> Model; results
go Model -> signal -> View with the Controller connecting. That is the preferred result path, so no
passthrough Controller method per Model method is needed. Direct View -> Model was rejected: Qt's
Model/View works because a `QAbstractItemModel` is passive and framework-defined, whereas `MetaModel`
owns worker threads and their bookkeeping.

**Also ruled then, still standing.** Moved tests are re-pointed rather than kept alive through thin
View facades (about 200 facades would have hidden the split). An ownership block gets a stated exit:
if an owner does not engage, control reverts to Kyle (`CODEOWNERS` is advisory, 2026-09-02).

**Revisit if** a tab's Model becomes passive enough that a View reading it directly is simpler.

---

## 2026-09-03 - The metadata query derives its FROM clause instead of enumerating seven branches

**Context.** `construct_metadata_query` hand-wrote seven query branches, one per
combination of selected tables. Each rolled its own FROM clause and its own qualification,
so they drifted: only one qualified the condition at all, none forced an `experiments`
join, and a filter on an events column against a sublevels+experiments plot hit a branch
with no `events` table. The literal-rewriting fix earlier the same day had to be applied to
one branch and left the other six wrong.

**Decision.** Compute the joined tables once as an ordered `aliases` map and derive the
SELECT list, FROM clause and `DISTINCT` from it. `_qualify_conditions(cond, aliases)`
qualifies against whatever the query actually joins, so the same filter text means the same
thing in every shape, and in `construct_event_data_query` too. An `experiments` join is
forced when the condition needs one, matching the existing events/sublevels forcing.

**Bare `id` stays an error.** `experiment_id`, `channel_db_id`, `channel_id` and `event_id`
are anchored automatically because a sublevel row carries its parent event's value for each
(`SQLiteDBWriter._insert_sublevels`, `MetaEventFitter` fills `event_id`/`channel_id`), so
the anchor cannot change which rows match. `id` is the events row id in one table and the
sublevels row id in the other, so guessing would silently filter the wrong thing.
`_find_ambiguous_id` rejects it with instructions naming the aliases that query offers, and
`relay_query` puts that text on the display panel as well as in the modal.

**Evidence.** Generated SQL diffed across all seven branch shapes plus experiment/channel
scoping: `table_name` identical everywhere, and the only deltas are the intended ones -
two unaliased branches gained aliases, three branches' shared identity columns moved
between equivalent tables, and conditions became qualified. Executed against a database on
the production schema, the four cases that failed before (three `voltage > 50` shapes and
`experiment_id` on an events+sublevels plot) now return the right rows, and the other seven
are unchanged.

**Revisit if** a query shape needs a FROM clause the alias map cannot express - an outer
join, or the same table joined twice.

---

## 2026-09-03 - Condition qualification skips string literals rather than parsing SQL

**Context.** `construct_metadata_query`'s qualification pass prefixed bare column names by
regex over the whole condition text, so `sequence = 'sublevel_duration'` became
`sequence = 's.sublevel_duration'` - valid SQL returning the wrong rows with no error. The
same blindness made the join-detection scan force a join on a column name that only
appeared as a value.

**Decision.** Split the condition on single-quoted literals and rewrite only the code
segments, rather than tokenizing or parsing SQL. Both the qualification pass and the
detection scan use the same split, so they cannot disagree about what a column reference
is. Experiments columns are no longer qualified at all in the events/sublevels join
branch, since that FROM clause has no `experiments` table.

**Evidence.** Reproduced against `ConcreteDatabaseLoader`: `name = 'sublevel_duration' AND
sublevel_duration < 100` produced `exp.name = 's.sublevel_duration' AND
s.sublevel_duration < 100`, and `sublevel_duration < 100 AND date > 50` produced
`exp.date > 50` against `FROM events e JOIN sublevels s`. Doubled-quote escapes
(`'it''s sublevel_duration'`) are covered by the split.

**Superseded in part.** The experiments-join gap this entry left open was closed the same
day; see the entry above. The literal-splitting decision stands.

**Revisit if** conditions ever need to carry double-quoted identifiers or bracket-quoted
names, which the literal split does not handle.

---

## 2026-09-03 - `WaveletFilter` takes no lock; the wavelet library is thread-safe for the entry point we call

**Context.** A review flagged that `WaveletFilter._dll_lock` was class-level for a
process-wide guarantee, but a plugin re-scan re-executes the module and produces a new
class with a new lock - so the guarantee did not hold. The proposal was to stabilise the
class object across re-scans.

**Decision.** The lock is removed instead, restoring the pre-`b679954` form. The library
needs no serialization, so there is nothing to guarantee and nothing for a re-scan to
break. Re-scan behaviour is left alone.

**Evidence.**

- *Source.* `filter_signal_wt` holds no state across calls: the `wdenoise_object` and
  scratch buffer are created and freed per call, and every `static` on the denoise path is
  a function or a `static const` coefficient table. The library's one mutable global
  (`int errorcode`) and one non-reentrant call (`strtok`) are both in `utils.c`'s DAQ
  settings code, which `filter_signal_wt` never reaches.
- *Measurement.* `ctypes.cdll` genuinely releases the GIL (8 threads, 3.5x faster than
  serial). Under real concurrency, 128 calls of 200k samples at one length/wavelet, 768
  calls mixing both wavelets and eight lengths, and 384 calls through two live plugin
  instances' `get_callable_filter()` were **all bit-identical to the serial reference**.

`force_serial_channel_operations()` returns `False` here anyway, and the filter ran
unlocked from the project's start until 2026-08-18 with no reported corruption.

**Rejected: a private copy of the library per instance.** `LoadLibrary` refcounts by path,
so a private copy means writing a 658 KB DLL to a unique temp path per instance plus
lifetime and crash-cleanup handling - to buy parallelism the library already provides. It
*would* give each copy its own `errorcode`, so it is the right shape of fix if the library
ever becomes genuinely non-reentrant.

**Revisit if** `filter_signal_wt` gains state across calls, a new entry point touches
`utils.c`'s `errorcode`/`strtok` paths, or a rebuild against a newer wavelib adds caching
on the denoise path. Re-run the concurrency measurement before reaching for a lock; if one
is needed, use the private-copy shape, since the class-level lock is what a re-scan breaks.

---

## 2026-09-02 - Per-module log levels are a scripting facility; the app keeps one global level

**Context.** Fixing `@log`'s debug gate to read the decorated module's own effective level
made per-module DEBUG possible for the first time, raising the question of whether the
Settings window should expose it.

**Decision.** No. The app keeps one global level; per-module control stays a scripting
facility, documented on the Scripting page with the Settings page pointing at it.

**Why.** Two things would have to move. A UI would mean designing an interface for an
open-ended list of dotted module names - a developer's tool in a general user's interface.
Independently, `MainModel.update_logging_level` pins every non-`QtHandler` handler to the
app-wide level, so once the dropdown is touched a raised module's records are dropped at
the handler rather than the logger. Exposing per-module levels therefore also requires
unpinning the handlers, changing what the dropdown means for everyone.

**Evidence.** Measured 2026-09-02: raising one plugin's logger works in the shape
`scripting.rst` documents (handlers at `NOTSET`) and produces nothing once handlers are
pinned. The global path is unaffected either way, with `QtHandler` holding its `ERROR` floor.

**Revisit if** someone regularly debugs a single plugin from inside the GUI and cannot
drive it from a script instead.

---

## 2026-09-02 - `LogDecorator`'s two `setattr` calls stay; they are what satisfies mypy

**Context.** Two `B010` findings, both `setattr(logger.root, "ignore_exceptions", True)` -
the one-shot latch that stops the decorator reporting the same logger fault forever.
`B010` advises the plain assignment.

**Decision.** They stay, and they are not cosmetic. `ignore_exceptions` is a flag this
module invents and hangs off the root logger so every decorated method shares one latch.
mypy accepts the *read* two lines above (narrowed by `hasattr`), but that narrowing does
not extend to a write.

**Evidence.** Probed against `mypy.ini`: the plain assignment reports
``"RootLogger" has no attribute "ignore_exceptions" [attr-defined]``; `setattr` is clean.
So "fixing" `B010` means adding a `# type: ignore` to satisfy a rule that is not a gate.

**Revisit if** the latch moves onto something this codebase declares - a small module-level
state object - at which point both findings disappear on their own.

---

## 2026-09-02 - The plugin trust boundary is checked with ruff, not bandit, and is not a sandbox

**Context.** Plugin discovery executes every file it walks, so module-level code in any
`.py` file under `poriscope/plugins/` or the user plugin folder runs at app start, before
any compliance check inspects the class. `ruff-plugin-security` and `plugin-module-level`
now police that; three parts of the original proposal were dropped.

**Decision 1: no `bandit`.** Ruff is already pinned, already implements flake8-bandit's
`S` rules and already runs in CI. A second tool means a second config, a second pinned
version, overlapping findings, and edits to both `requirements-dev.txt` and
`pyproject.toml`'s `[dev]` extra, which the post-merge hook keeps byte-identical. Known
gaps: `S403`/`S404` need ruff preview and are not stable rules; `__import__("os")` is
flagged by neither tool (verified against a probe), though a module-level `__import__` is
caught by `plugin-module-level`. **Revisit if** a submission turns up a dangerous pattern
ruff structurally cannot see.

**Decision 2: the module-level check skips `analysistabs/`.** It is scoped to the eight
data-plugin families, which is what an outside contribution realistically adds. Measured:
those 34 files have zero module-level statements outside imports, constants, classes and
functions, so the rule needs no exceptions. Extending it would mean permitting three
further patterns for six benign sites (`warnings.filterwarnings` x3, an `os.environ` write
under a `sys.platform` guard, two `__main__` demo blocks), and a rule with carve-outs is
weaker than one with none. Those files stay covered by `ruff-plugin-security`.

**Decision 3: this is not a sandbox, and no workflow was touched.** Anything inside a
method body is beyond a static pass, and neither check sees the runtime path - a file
dropped into `%LOCALAPPDATA%/Poriscope/user_plugins` is executed with no PR and no CI.
Human review is the real gate. No changed-file computation was built because
`ci-fork-pr.yml` and `ci-branches.yml` already run `pre-commit run --all-files`.

**Revisit if** true isolation is wanted (subprocess isolation, restricted execution) -
that is its own design discussion, not an increment on this one.

---

## 2026-09-02 - `CODEOWNERS` stays advisory; code-owner review is not enforced

**Context.** `.github/CODEOWNERS` maps each subsystem and plugin family to its maintainer
so a PR requests the right reviewer automatically. GitHub's *Require review from Code
Owners* branch protection would turn the same file into a merge block.

**Decision. The toggle stays off, on every branch.** The file routes attention; it is not
an edit limit or a barrier to contribution.

**Why.**

- **Team size.** Three people have commits in the last six months. Enforced review is a
  coordination mechanism for a team large enough that the right reviewer is not obvious.
- **Fork contributions are a first-class path** (`ci-fork-pr.yml` exists for them), and
  enforcement would put one named individual in front of every community plugin.
- **Some owners cannot answer.** Two named contributors have left the lab and one has no
  GitHub handle. GitHub silently ignores a line naming anyone without write access, so
  enforcement would block on some paths and quietly not on others.
- **The checks that matter already block** - the hooks and CI in `quality_control.rst`.
  Owner review adds judgement, worth requesting and not worth requiring.

**Revisit if the contributor list grows past six people.** That is the stated trigger and
the only one; a bad merge is not, and neither are required *status checks*, a separate setting.

---

## 2026-09-01 - No custom lint rules for the three conventions `CLAUDE.md` documents

Proposed as block 8 of the compliance gate: `ast` checkers for three conventions held by
review attentiveness. **Nothing was built, and nothing should be.**

- **No nested functions - the convention itself changed.** A short, simple nested function
  is now fine where it is genuinely simpler, typically a closure captured for a callback or
  timer. That is a judgement an `ast` walk cannot make; a line-count or complexity
  threshold would flag exactly the closures the revised convention permits.
- **Bare `except:` - already enforced, and always was.** `E722` is in Ruff's *default* rule
  set and `pyproject.toml` uses `extend-select`, which adds to the defaults. Measured: a
  throwaway file with a bare `except:` under `poriscope/` fails the existing ruff hook.
- **Explicit sqlite3 cleanup - semantic, not syntactic.** A checker would have to track
  whether every `connect`/`cursor()` result is closed on every exit path. Its home is the
  behavioural conformance suite (block 1), whose open-file-handle check catches the same
  defect empirically; that suite belongs to the test developer.

`quality_control.rst` records that Ruff's defaults are in force on top of the selected
rules, naming `E722`. Deliberately **not** added to `CLAUDE.md`, which should carry rules a
human has to remember rather than ones the gate enforces every commit.

**Revisit if** a convention turns up that is genuinely syntactic and that review keeps
missing. The owner-held fitter files changing hands would not reopen this.

---

## 2026-09-01 - The three reserved file-parameter names stay as they are

**Context.** `_validate_param_ranges` skips its `Value in Options` check for three literal
names - `Input File`, `Output File`, `Folder` - because there `Options` holds file-dialog
filters rather than permissible values. The proposed fix was a `"Validate Options": False`
schema flag so the base class need not know any names.

**Decision.** Keep the literal names and the shared `settings_schema.FILE_DIALOG_PARAMS`
constant. **The flag is rejected outright rather than deferred.** No code changes.

**Why.** It aims at the wrong site. The names appear at roughly 20 places, **17 of them in
`views/widgets/dict_dialog_widget.py`** (widget dispatch, picker write-backs,
`key not in [...]` tests, `check_validity` clauses); one is the constant, one is
`DataPluginController`'s `Folder` default, and the validator itself now holds none. The
flag would clear the one site already contained behind a shared definition.

It is also the wrong *shape* of key: `"Validate Options": False` describes what not to
check, whereas a key describing what the parameter **is** could drive both the validator
and the dialog's widget selection. Adopting it would spend the schema-contract change on
the lesser fix.

**The better fix, if ever needed:** an optional `"Kind"` key taking `"input file"`,
`"output file"` or `"folder"`. Every site asking "is this key named `Input File`?" asks
"is this parameter of kind `input file`?" instead. The five bases that create these entries
(`MetaReader`, `MetaWriter`, `MetaEventLoader`, `MetaDatabaseLoader`, `MetaDatabaseWriter`)
declare the kind, and since every plugin builds its schema from `super()`, all 24 shipped
plugins inherit it unchanged. A `kind = entry.get("Kind") or _legacy_kind_for_name(key)`
fallback keeps hand-rolled user plugins working.

**Consequences.** Each picker callback hardcodes the key it writes, so **a plugin can have
at most one file input, one file output and one folder**, and a file parameter cannot be
given a descriptive name. A reader taking a data file *and* a calibration file cannot be
expressed. That is the real cost of the design and is accepted here.

**Revisit if** someone needs a plugin taking **more than one file input** (or output, or
folder). That is the capability this design forecloses. Removing plugin-specific names from
the universal validator is explicitly *not* a reason - that was the original motivation and
it measured out to be worth far less than it sounded.

---

## 2026-09-01 - The multiselect popups' event filter stays on the application

**Context.** Both multi-select combo boxes closed their popup on an outside click using a
filter installed on the `QApplication` singleton and never removed - a leak causing an
intermittent `RuntimeError: Internal C++ object ... already deleted`. The obvious fix was
to scope the filter to `containerWidget` or `self`.

**Decision.** The filter stays **on the application**. Only its *lifetime* was narrowed:
installed in `showPopup()`, removed in `hidePopup()`.

**Why.** Scoping to the container would have silently broken click-outside-to-close on
Windows and macOS. `Qt::WindowType` is a value in the low byte of the flags word, not
independent bits, and `Tool == Popup | Dialog == 11`. Both widgets build their container as
a `QDialog` and OR `Qt.Popup` into flags that already include `Qt::Dialog`, so
`windowType()` comes out `Qt::Tool` - verified against PySide6 6.9.0 with the real
construction pattern. A tool window is not a popup: `isPopup()` is false, there is no
implicit mouse grab, and a press elsewhere is never routed to the container, so a filter
there would never see the click it exists to detect. Qt also does not auto-close even a
genuine popup on an outside press - that behaviour is `QMenu`'s own `mousePressEvent`.

Only `multiselect.py`'s Linux branch produces a real popup, because it calls
`setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)`, *replacing* the flags. That asymmetry
is very likely why the application-wide filter was written.

**Consequences.** The Linux/offscreen CI run cannot exercise the load-bearing path, because
there the container really is a popup. Any change to this filter needs a manual Windows
check. Scoping a filter to a narrower object (the `walkthrough.py`/`help.py` precedent) is
still the right default - it just does not apply to a widget whose purpose is to observe
events aimed at *other* widgets.

**Revisit if** the containers are converted to genuine `Qt::Popup` windows on every
platform. That was considered and deliberately not bundled into a crash fix: the popup
would lose its title bar, caption, close button and movability on the primary platform.

---

## 2026-08-31 - `close_resources()` does not get a threaded timeout in this shape

**Context.** Reset Session and quit call every plugin's `close_resources()` unguarded, so a
hung one freezes the app without naming itself. A fix ran each call on a thread joined with a
10 s timeout, logging a named failure and deleting the plugin anyway.

**Decision** (2026-08-31). Reverted before commit, although its three tests and the full
suite passed. The approach stands; this shape does not.

**Evidence.** A closer thread is a third thread relative to whichever one opened a resource.
`SQLiteDBWriter` and `SQLiteEventWriter` hold a `sqlite3` connection with the default
`check_same_thread=True`, so closing from the new thread raises `ProgrammingError` - leaking
the file lock in one and silently skipping the commit in the other. The quit path
(`DataPluginModel.handle_exit`) was left unguarded, so it fixed half the exposure.

**Revisit** when the queued `future_fixes.md` item is worked, which carries the shape. Re-audit
the overrides first: `NIConditioningLoader` now closes child readers too.

---

## 2026-08-31 - Plugin name collisions are the user's to rename, not ours to accommodate

**Context.** Discovery walks `poriscope/plugins/` then the user plugin folder into one flat
map keyed by class name (also the filename stem). A collision used to be silent and
last-writer-wins. Fixing it raised what *should* happen: let the user copy win and report
the override, keep both under disambiguated names, or record provenance.

**Decision.** None of those. Discovery keeps a set of claimed names and logs at `ERROR` -
which `QtHandler` raises as a dialog - for any later file claiming a taken name, skipping
it. The first file found wins and built-ins are walked first, so **a built-in cannot be
displaced by a user plugin of the same name**. The user is told which file was ignored and
that renaming it will load it.

**Why.** The goal is that people rename their collisions, not that the application manages
collisions in a way that lets them persist. A name resolving to two implementations is
ambiguous in session history and in any discussion of a result; an override mechanism -
however well reported - lives with that ambiguity instead of removing it.

**Consequences.** There is deliberately no way to override a shipped plugin by shadowing its
filename; a modified built-in must have its own name, which also makes the modification
visible in the menus and session history. The check is keyed on the name alone rather than
per metaclass, because plugin names are unique application-wide.

**Revisit if** a concrete workflow needs a built-in replaced in place and cannot use a
differently-named plugin. Reporting the override more elaborately - a provenance map, a
panel message, a startup summary - is *not* a reason; that was considered and rejected as
machinery around a problem the rename already solves.

---

## 2026-08-28 - The view-test GC sweep stays; it is generation-limited, not removed

**Context.** `tests/unit/views/conftest.py`'s autouse teardown ends with `gc.collect()`.
Matplotlib figures wrapping PySide6 widgets segfault in C++ when their Python wrappers are
collected after the Qt widgets are destroyed, and the explicit sweep forces collection
while Qt is still alive. Not theoretical - it took three commits to settle repeated CI
segfaults (`06679373`, `cc2fd863`, `d829d688`). Profiling on 2026-08-28 found this one call
was the largest cost in the suite: **193.0s across 1,494 tests, 129ms each, 95.9% of all
teardown time**.

**Decision.** Keep the per-test sweep. Make it generation-limited - `gc.collect(1)` every
test, full `gc.collect()` every 50 - rather than removing or de-frequencing it.

**Evidence.** Full view tree, back to back, all variants 1,494 passed:

| variant | wall clock |
| --- | --- |
| full `gc.collect()` every test (previous) | 340.4s |
| **`gc.collect(1)` every test + full every 50 (chosen)** | **168.5s** |
| full `gc.collect()` every 50 only | 176.9s |
| `gc.collect(1)` every test | 178.4s |
| `gc.collect(0)` every test | 184.9s |
| no GC at all | 163.7s |

Removing the sweep is only 4.8s faster and gives up the property that fixed CI. "Full every
50 only" is both slower *and* less safe - the only fast variant that stops collecting after
every test. The chosen option reaches 97% of the no-GC floor without changing the cadence
at all. A full collect walks the long-lived generation holding PySide6, numpy, pandas,
sklearn and matplotlib; that traversal is the 129ms, and per-test Qt garbage is not in it.

**Caveat.** All six runs are Windows; CI is Linux under Xvfb, where destruction ordering
differs and the original segfaults appeared. One condition has genuinely changed: at the
time of those segfaults teardown only called `widget.close()`, so wrappers accumulated and
were swept in large unpredictable batches. As of `d2ac785b` widgets are destroyed
deterministically. That lowers the risk; it does not eliminate it.

**Revisit if** a segfault reappears in CI in the view tests - first try restoring the
unconditional full `gc.collect()`, a one-line change. Do **not** "simplify" `gc.collect(1)`
to `gc.collect()` on the assumption it is a typo; it costs 172s.

---

## 2026-08-25 - The audited `bugbear`/`bandit` rules stay off as gates, except `S110`

**Context.** Adopting the rest of ruff's `flake8-bugbear` and `bandit` sets was proposed as
a complement to pydoclint. `B006` and `B020` were adopted outright; the rest were audited rule
by rule.

**Decision.** `B905`, `B904`, `B007`, `S112` and `S101` were each run as a one-time audit, their
findings in our own code fixed, and the rule left **unselected**. `S110` reached zero findings and
is enforced since 2026-11-16 (`extend-select` in `pyproject.toml`).

**Why, per rule.** Ruff's scope is the whole repository, not `poriscope/` (measuring only
`poriscope/` produced the wrong answer originally). Re-measured 2026-11-16 with the pinned ruff
0.12.11:

- **`S101` - 5,278 sites, 7 in `NanoTrees.py` and the rest in `tests/`.** `assert` is the test
  suite's fundamental idiom, so a `per-file-ignores` for `tests/` would suppress >99% of findings,
  however `NanoTrees.py`'s ownership resolves.
- **`B904` - 3 sites, all `tests/e2e/_helpers.py`.** Zero under `poriscope/`.
- **`B007` - 4 sites: 2 `PeakFinder.py` (owner-held), 2 `tests/`.**
- **`S112` - 1 site, `PeakFinder.py`** (owner-held).
- **`S110` - 0 sites**, so it became a gate.

For the rest, enabling the rule needs a `per-file-ignores` entry, which *hides* a real check
rather than satisfying it - worse than not selecting it, because it looks enforced.

**`B905` (`zip` without `strict=`) is different: the rule itself is the problem.** 77 sites
each need their own judgement, at least one (`MetaDatabaseLoader`'s CSV export, list against
generator) cannot be proven equal-length in advance, and three in `ClusteringView` depend on
truncation deliberately and would raise on every clustering run.

**The audit half earned its keep**: `B905` found `MetadataView` silently dropping unlabelled
plot features, `B904` found the six readers discarding the missing file's name from
`FileNotFoundError`, and `S110` found `apply_settings` swallowing a failed `get_key()` and
leaving the dependency graph incomplete.

**Nothing from this sweep is left unfixed** (`B028` fixed 2026-09-02; the 2 `B010` in
`LogDecorator.py` are settled in their own entry). Treat this block as finished, not as a backlog.

**Revisit if** the owner-held fitter files change hands - that removes the objection for `B007`
and `S112` only, nothing for `B904` (test suite) or `S101`. This is *not* the same question as the
plugins-scoped trust-boundary proposal, which is settled separately above.

---

## 2026-08-25 - Interpolated SQL in the database plugins is accepted (`S608`)

**Context.** `S608` reports 25 sites under `poriscope/` where query strings are built by
f-string interpolation rather than parameter binding.

**Decision.** Accepted as-is. Not fixed, and `S608` is not enabled.

**Why.** There is no privilege boundary for an injection to cross. The database is a local
SQLite file, opened by a desktop app, owned by and running as the user who launched it. An
attacker who can supply a malicious experiment name to that application can already run
code as that user. Injection defends a privilege *gradient*, and there is none here.

**Consequences.** Correctness bugs from interpolation are a different matter and have been
fixed on their merits - `MetadataView`/`ProteinView` converting experiment/channel values
once at the derivation site, and quote-escaping so legitimate experiment names stop breaking
queries. Accepting `S608` is not a licence to leave interpolation that produces *wrong
results*.

**Revisit if** the database is ever opened over a network path with multiple users at
different privilege levels, exposed through a service, or fed by a file the user did not
create.

---

## 2026-08-31 - `Basic_PeakFinder`'s conformance fixture uses a raised-cosine taper, not a rectangle

**Context.** `Basic_PeakFinder` crashed (`ValueError: zero-size array...`) on a zero-width
sublevel, reachable whenever `scipy.signal.find_peaks`'s interpolated half-height crossing
lands on the same sample twice - itself only reachable once the fitter was driven against a
fixture with an actual intra-event dip to find (block 1 of `future_fixes.md`).

**Decision.** Fix the crash by returning `0.0` for a zero-width sublevel (no data to take a
deviation over, matching `sublevel_raw_ecd`'s existing empty-slice tolerance). For the new
fixture knob (`peaked_events_db_path`), use a smooth Hann-window taper rather than a
rectangular dip.

**Evidence.** A rectangular dip was tried first and made the crash *more* frequent (its
abrupt edges resolve into two close peaks under noise), not less.

---

## 2026-08-25 - Keep the four `None`-placeholder `type: ignore`s in `PeakFinder`

**Context.** `PeakFinder._populate_event_metadata` deliberately stores `None` for
`unfolded_level`, `folded_level`, `translocation_direction` and `sequence`, which are
decided globally in `_post_process_events` and cannot be known per event. Both
`MetaEventFitter._populate_event_metadata`'s declared return and
`_define_event_metadata_types` disagree with the value written; four narrow
`# type: ignore[assignment]` mark the sites.

**Decision.** Leave them. Do not widen the ABC to clear them.

**Evidence.** The behaviour is correct: `SQLiteDBWriter` maps declared types to
`REAL`/`TEXT` columns and SQLite accepts `NULL` in any column without `NOT NULL`. This is a
type-contract mismatch, not a latent crash. Clearing it means widening two `Meta*` ABC
methods to `Optional[...]`, and because `test_plugin_compliance.py` compares annotations
**by equality**, every override moves in lockstep - `CUSUM`, `IntraCUSUM`, `NoFitter`,
`NanoTrees`, `PeakFinder`, `Basic_PeakFinder`: six files, two owned by another developer and
one a deprecation candidate. It would also be a breaking change to the plugin contract.

**Cheaper alternative if ever wanted:** do not write the keys at all until post-processing
fills them - absence rather than `None`. The schema still comes from
`_define_event_metadata_types`. That is a logic change in the owning developer's file and
needs checking that the writer tolerates a row missing a declared key.

**Revisit if** a third-party plugin ecosystem exists, or someone wants `NOT NULL`
constraints on those columns.

---

## 2026-08-25 - Do not consolidate the double-Gaussian fits (RESOLVED)

Three implementations existed: `bitthresh`'s nested `dgfit`,
`ProteinView._fit_double_gaussian`, and `PeakFinder.fit_2_gauss`. Consolidating onto the
ProteinView one was deferred because the owner was rewriting the fitting code.

**Outcome.** The rewrite landed and *is* the ProteinView port: `bitthresh` and `dgfit` are
deleted and `PeakFinder`'s classifiers call a `fit_threshold` built on ported copies of
`_double_gaussian`/`_fit_double_gaussian`. `fit_2_gauss` was deleted separately - it had no
callers and could not have run. The logic is now shared by copy rather than by import,
because the two live in different plugin families with no common base; folding them into
one helper is a further step, not a blocker. The port keeps only the convergence checks and
drops the perr, t-test and amplitude-ratio rejections on purpose, so the fit's failure rate
stays observable.

---

## 2026-08-24 - Leave two of the three unguarded `Optional` Qt accessors alone

**Context.** The annotation pass flagged three Qt accessor families returning `Optional` and
used without a `None` check: `QApplication.instance()`, `QComboBox.lineEdit()`, and
`QTreeWidgetItem.child(i)`/`topLevelItem(i)`.

**Decision.** Only `lineEdit()` was changed - now bound once in `__init__` immediately after
the `setEditable(True)` that makes it non-`None`, because that guarantee previously sat
hundreds of lines from the uses depending on it. The other two need no action:

- `QApplication.instance()` is called inside a `QWidget.__init__`, and a `QWidget` cannot be
  constructed before a `QApplication` exists.
- `child(j)`/`topLevelItem(i)` are always called inside `for j in range(...childCount())`.
  This is mypy being unable to connect `range(n)` with "valid index".

**Revisit if** either call moves outside a widget constructor, or an index stops being
derived from the matching count.

---

## 2026-08-26 - `@log` no longer erases decorated signatures (RESOLVED)

`log` and `register_action` return the type they are handed (`5a215d8`; before, `-> Callable` made
every decorated method `Any` to its callers). Turning it on surfaced 84 call-site errors (32
annotation, 52 logic) under a gate that had read clean, so a pre-`5a215d8` "mypy clean" says nothing
about call sites.

---

## 2026-08-26 - Never `@overload` around an over-broad return union

**Context.** `MetaReader.get_channel_length` was
`(self, channel: Optional[int] = None) -> int | Dict[int, int]`. mypy resolves a return type
from the declaration, not the argument, so every caller saw the union and 15 call-site
errors were arithmetic on it. The obvious typing fix is two `@overload` stubs.

**Decision.** Do not. When a return union makes a value unusable at its call sites,
**verify every incoming call and delete the dead branch instead**. `cast()` at the call
sites is equally rejected. If both arms are genuinely live, **flag it for review** rather
than overloading - the preferred resolution is to change the incoming calls.

**Evidence.** The dict branch had **no callers anywhere**: all five sites in `poriscope/`
passed a channel, the `MetaReader` test double has always declared `channel` as required,
and internally the dict was reached through `total_channel_samples` directly. Narrowing to
`(self, channel: int) -> int` cleared all 15 errors with no casts.
`MainModel.get_available_plugins` had the identical shape and outcome.

**On breaking the plugin contract.** Both are public API and `MetaReader` is a `Meta*` ABC.
Acceptable, because no third-party plugins exist yet. The remaining obligation is that
**the break is called out explicitly in `changelog.md`**.

**When both arms are genuinely live.** `MainModel.get_plugin_classes` was the first such
case. The resolution is **to delete the optional-argument arm, not the parameter** - make
the argument required so the function has one job and one return shape, and let the single
call site wanting the aggregate rebuild it with a comprehension. First check whether that
call site receives a *live reference* to a mutable attribute something else later mutates,
since a comprehension hands over a fresh object; for `get_plugin_classes` it was safe.

**Revisit if** a third-party plugin ecosystem exists, at which point narrowing an ABC
becomes a deprecation cycle instead.

---

## 2026-08-26 - Scoping the mypy hook to `poriscope/` gives up type-checking of `tests/`

**Context.** The pre-commit `mypy` hook is scoped `files: ^poriscope/`, because it had been
passing test files as explicit paths and `mypy.ini`'s `exclude = ^tests/` governs directory
discovery only.

**Decision.** Accept that test files are unchecked by the gate.

**Evidence, including the cost.** The blind spot caught a real defect once - the
`{"MetaReader": []}` fixture shape in `test_data_plugin_controller.py` that should have been
`{"MetaReader": {}}`. Still right: `tests/` is excluded by policy in `mypy.ini`, the hook
was contradicting that policy by accident, and leaving it would mean `disallow_untyped_defs`
failing every commit on unannotated test code nobody intends to annotate. If test
type-checking is wanted, it should be a deliberate second hook with its own config.

**Revisit if** someone decides `tests/` should be type-checked on purpose.

---

## 2026-08-24 - Leave the PySide6 short-form enum accesses alone

**Context.** A stub-aware `mypy poriscope` reports 191 `attr-defined` errors of the form
`"type[QSizePolicy]" has no attribute "Expanding"` across ~11 files, because the bundled
stubs no longer declare the unscoped enum members.

**Decision.** Do not rewrite them to the scoped form (`QSizePolicy.Policy.Expanding`).

**Evidence.** On PySide6 6.9.0, `QSizePolicy.Expanding` emits no warning and
`QSizePolicy.Expanding is QSizePolicy.Policy.Expanding` is `True` - identical objects, so
this is a stub omission, not a code defect. A 191-site mechanical rename would bury real
changes and rewrite `git blame` across eleven files. The tempting justification - that
clearing them makes a stub-aware mypy usable for review - does not hold: of the 377 errors
that run reports, ~308 are noise from other sources (34 `import-untyped`, 38
`MetaController.view`/`model`, 34 numpy stub pedantry, 11 known-accepted
`sublevel_starts`), so clearing the enums still leaves ~117 noise items.

**Revisit if** PySide6 removes forgiving-enum mode. Waiting costs nothing: every site would
fail loudly at widget construction, pointing at its own location.

---

## 2026-08-24 - Accept that the pre-commit mypy hook cannot see project dependencies

**Context.** The `mirrors-mypy` hook runs in an isolated virtualenv containing only mypy,
with `--ignore-missing-imports`, so PySide6, numpy, pandas, scipy and sklearn all resolve to
`Any` under the gate. Concretely,
`reveal_type(button_mapping.get(button_type, lambda: None))` prints `Any` under the hook and
`QPushButton | (def ())` under the project venv - which is why the gate could not see the
`on_button_clicked` fallback bug.

**Decision.** Do not add stubs to the hook, and do not treat this as a blocker for the
type-policy flags.

**Revisited 2026-10-05.** The hook stays the gate; `ci-branches.yml` now prints the project-venv
`mypy poriscope` count, non-blocking (607 with mypy 2.3.1, about a third enum and untyped-import
noise; see `CLAUDE.md`). Declaring `view`/`model` per controller let the hook see three real
contract mismatches, fixed in `c3b71161`.

**Evidence.** The genuine signal was 11 `union-attr` findings, all one narrow class (a Qt
getter that can return `None`), three of which were the `button_mapping` bug and eight of
which remain in `SelectionTree.py` and `MetaView.__init__`. Against that, closing the gap
means suppressing or fixing ~191 enum sites first and then keeping pinned stub versions in
sync with the runtime PySide6 forever - and stub drift produced that noise in the first
place. The hook still checks all first-party logic and the whole `Meta*` plugin contract.

**Cheaper alternative:** run `mypy poriscope` in the dev venv periodically and review by
hand, or add it to the pre-PR checklist, rather than making it block commits.

**Revisit if** the `union-attr` class of bug starts recurring in production, or the enum
noise is cleared for other reasons.

---

## 2026-08-24 - The walkthrough `moveEvent` hook is not the cause of the test-suite segfault

`bc09de7` (the class-level `StepDialog.moveEvent` override) is exonerated: the segfault reproduced
identically with it reverted. The cause was one `listWidget.clear()` in `test_multiselect_filter.py`,
fixed by disposing of widgets with `deleteLater()` and a drained event loop instead of `destroy()`.

---

## 2026-08-25 - `check-class-attributes` stays `false`; the pydoclint parser is broken upstream

**Context.** `IntroDialog`'s class docstring documented its Qt signal as
`.. attribute :: start_walkthrough` - with a space before the `::`, which docutils reads as
a comment, so Sphinx rendered nothing for it. Correcting the RST turned one DOC605 into two
findings (DOC601 + DOC603), as did every canonical field form (`:ivar:`, `:cvar:`, `:var:`)
and every attribute-annotation variant - all measured directly rather than guessed.

**Cause.** `docstring_parser_fork/rest_attr_parser.py` hardcodes the literal
`".. attribute ::"`, so pydoclint recognises **only** the form Sphinx ignores and ignores
the form Sphinx renders. pydoclint's own documentation prescribes the invalid spelling. Both
packages were at their latest release (`pydoclint` 0.9.1, `docstring_parser_fork` 0.0.16).

**Decision.** The RST in `walkthrough.py` is corrected so Sphinx renders the signal, and
`check-class-attributes = false` in `pyproject.toml` with the rationale recorded inline.
Filed upstream as https://github.com/jsh9/pydoclint/issues/304.

**Revisit if** a `pydoclint` release fixes the parser. Until then do not flip the setting
back on; a one-line reproduction is kept in `future_fixes.md`.

---

## 2026-08-26 - Do not use GMM/BIC to decide whether a `PeakFinder` dataset has one population or two

**Context.** A real dataset that `fit_threshold` fit as two populations (centres 1786/2087)
turned out on inspection to be one - a single decaying population, not a fitting bug. The
classifiers need to tell that case apart from a genuine two-population dataset, and BIC
model selection was the obvious candidate, since `GaussianMixture` is already imported.

**Decision.** Do not use it. Comparing 1-component against 2-component BIC on the raw
samples **decisively picks 2 on the real single-population dataset this feature exists
for.** Measured on a tuned reconstruction (sharp core plus decaying right shoulder,
n=6233): BIC 88,198 at k=2 versus 90,936 at k=1 - a drop past any conventional "decisive"
threshold - and log-space fares no better (-16,771 vs -15,519). The reason is structural: a
skewed non-Gaussian single population is genuinely closer in likelihood to two Gaussians
than to one, and BIC's five-parameter penalty does not overcome that at this sample size.
No margin fixes this in general, since the margin needed depends on the skew and the sample
size.

**What was done instead.** The one-vs-two decision reuses the collapsed-component and
centres-not-separated diagnostics `_fit_and_check_double_gaussian` already computes, via a
`"n_components"` key. This is evaluated against the fit to *this* data's actual shape rather
than an idealised Gaussian, and costs nothing extra - the double-Gaussian fit already runs
in all three classifiers, where a BIC comparison would be a second fit.

**Revisit if** a dataset shape turns up where the fit-diagnostic approach itself gets the
count wrong - e.g. two genuinely separate but heavily overlapping populations that still
pass the centres-not-separated check. BIC would then be worth reconsidering only alongside a
non-Gaussian null (skew-normal or gamma), not as a drop-in with a tuned margin.
