# Decisions

Short records of choices made deliberately, especially choices *not* to do something, so
the same question is not re-litigated from scratch. Each entry is context, the decision,
the evidence, and what would make it worth revisiting. Detail about work that *was* done
lives in `changelog.md` and git history.

Entries referring to "step 3/4/6/7" mean stages of the full-codebase type-annotation pass,
which ran through August 2026 and is complete. The step numbers only date the decision.

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
the plugin-compliance test would see, to fix a message.

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

**Evidence.** `main_controller._dispatch_to` catches every exception a bus call raises, logs
it, and returns *without invoking the return function*. Because the analysis tabs read the
result off an attribute on the statement after `.emit()`, a raising loader would leave that
attribute holding the previous call's value and the caller's `is None` guard would read stale
data as this call's answer - strictly worse than the conflation being fixed. Twelve emit sites
have no `try/except` at all, so an exception would also escape into a Qt slot.

**Revisit** when the emit-then-read pattern is gone (Step 4a of the 2.0.0 refactor converts
the 77 emits to Controller-mediated calls). Once results are returned rather than read off an
attribute, raising on failure becomes the better contract.

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
(`SQLiteDBLoader.py:316-323`). It was listed alongside the `None`-sentinel conflation in the
2.0.0 plan's Tier A.

**Decision.** Not fixed. It is inert: every consumer erases the distinction anyway -
`metadatacontrols.update_column_units_label` collapses `None` and `""` to a single space for
display, and `ClusteringController` drops both on a falsy test. No golden file can
distinguish the two cases, which is the only reason Tier A exists.

**Revisit** if a caller ever needs to tell "this column has no units" from "there is no such
column" - at which point the fix is a distinct sentinel, and note that two tests pin both
cases to `""` and `docs/source/signals/global_signal/overview.rst` uses this method as its
worked example of a one-argument bus call.

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

**Context.** `CLAUDE.md` has long warned that `pre-commit run mypy` and a bare
`mypy poriscope` "disagree wildly and are blind in opposite directions", and attributed it
solely to the hook's isolated virtualenv having no project dependencies. Measured
2026-09-04, the versions were skewed three ways as well: `pyproject.toml`'s `[dev]` extra
and `requirements-dev.txt` both pinned `mypy==1.9.0`, `.pre-commit-config.yaml` ran
mirrors-mypy `rev: v1.17.1`, and the working virtualenv had `2.3.1` installed. Nothing
anywhere recorded that, so the skew read as an environment quirk rather than a fact of the
configuration.

**Decision.** The declared pin is aligned to `mypy==1.17.1`, matching the hook. **The hook
remains the only gate** - `pre-commit run mypy --all-files` - and the declared pin exists so
that a contributor running mypy from their own environment gets the same *version* the gate
uses, even though they will still see different results because their environment has
PySide6, numpy and pandas types that the hook's isolated env resolves as `Any`.

**Why alignment rather than just documenting the gap.** Aligning costs one character-level
edit in two files and removes a whole class of confusing report. It does not change what the
gate checks, so it cannot break a commit that would otherwise pass. Documenting alone would
have left three numbers in play with nothing reconciling them.

**What alignment does not fix, and must not be mistaken for a fix.** The dependency
blindness is unchanged and is the larger half of the disagreement: the hook sees PySide6,
numpy and pandas as `Any`, so it cannot see errors in code that touches them, while a
project-venv run reports several hundred errors that are overwhelmingly known noise (191
PySide6 short-form enum accesses alone). **Always measure with the hook.**

**Revisit if** the hook's `rev` is bumped - move the declared pin in the same commit, or the
skew silently returns. Also revisit if `additional_dependencies` are ever added to the mypy
hook so it can see real PySide6/numpy/pandas types, which would close the other half and
make a project-venv run meaningful for the first time.

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

## 2026-09-03 - The return-value signal bus becomes a direct call, with plugin references pushed

**Context.** Planning the 2.0.0 refactor. `global_signal(metaclass, key, "method", args,
"return_method", ret_args)` is a string-keyed RPC used as a *blocking* call: emit, then read
the answer off an attribute on the next statement. 82 call sites, 77 of them in analysis-tab
Views. The 2026-08-25 audit deferred fixing this because `MetaController`/`MetaView`
deliberately hold no reference back to `MainController`, which is what keeps tabs pluggable.

**Decision.** `MetaController` and `MetaModel` gain an inherited, non-abstract
`get_plugin(metaclass, key)` / `call(metaclass, key, func, *args)` pair that resolves from a
local dict and invokes directly, so it **returns or raises**. Instances are **pushed** to each
tab, not pulled: `DataPluginController.update_available_plugins` already fires on all four
lifecycle events (create `:613`, delete `:353`, both `edit_plugin` branches `:126`/`:212`) and
`MainController.update_available_plugins:676` already fans out to every tab. Only the
return-value RPC is replaced; `plugin_state_changed`, `add_text_to_display`,
`update_progressbar` and `create_plugin` stay ordinary Qt signals.

**Evidence.** Traced end to end: resolving one experiment id
(`ProteinView._resolve_event_db_ids`) takes 8 hops, 2 Qt emissions and 3 string lookups, and
needs two methods plus one attribute that exist only to carry one `int` back. That shape had
a live bug - a failed dispatch left the reader seeing the **previous call's** experiment id,
because `_dispatch_to` logs and returns without calling the return function
(`main_controller.py:554`) - which is now guarded at each site by clearing the attribute
immediately before the emit, at the cost of repeating that guard everywhere. Also measured: all 77 emits target data plugins and
**none targets another tab**, so `_relay_global_signal`'s docstring advertising calls into
`main_model.plugins['MetaController'][key]` describes a capability nothing uses.

**Rejected: a typed facade injected into the tab.** Both a full `PluginAccess` ABC and a
one-method `PluginResolver` were considered. Rejected because resolving a plugin must not
require the tab or plugin author to know about app-shell internals - the string API is the
isolation. With the push, there is also nothing left to abstract over: `MetaController` holds a
plain dict, `__init__`'s signature does not change, and a test supplies a dict directly.

**Rejected: caching on first use.** Needs invalidation on three events, two of them easy to
miss - a *rename* leaves the cache pointing at a live instance under a dead key, and a
*re-instantiate* leaves it holding an object whose `close_resources` may have run. A push makes
the call that would go stale the call that refreshes it. Its lazy first fetch would also still
have used emit-then-read.

**Accepted cost.** `call()` returns `Any`, so mypy still cannot catch a renamed plugin method.
That is the price of the string API and it is accepted; do not re-argue it by pointing at the
lost type safety. `update_available_plugins(names)` is left untouched for the Views, which want
names for comboboxes - names for the UI, instances for the call path.

**Revisit if** a tab ever needs to call another tab, which no current site does.

---

## 2026-09-03 - Scope decisions for the 2.0.0 refactor

**Context.** The plan in `refactor_2.0.0.md` needed four rulings before implementation.

**MVC mediation is kept.** Commands go View->signal->Controller->call->Model; results go
Model->signal->View with the Controller connecting, formalised as the *preferred* result path
rather than an exception, so no passthrough-per-model-method is needed. Note the rule is
currently vacuous - View/Model direct contact is already zero (no View imports a Model, no
`self.model` in any View); what fails is the View's second unmediated channel to everything
else. Direct View->Model was considered and rejected: Qt's own Model/View works because a
`QAbstractItemModel` is passive and framework-defined, whereas `MetaModel` owns worker threads
and the `workers`/`threads`/`thread_running` dicts.

**2.0.0 takes the queued ABC breaks.** Several entries below defer contract fixes with "revisit
if a third-party plugin ecosystem exists, at which point narrowing an ABC becomes a deprecation
cycle." That window is now and will not reopen cheaply: the `"Kind"` schema key, splitting
`MetaReader.load_data`'s `raw_data` arm, `close_resources` channel dispatch via
`_close_one_channel`, `_write_data`'s 13 parameters, `MetaEventFinder`'s undeclared
`Threshold`. Each is called out explicitly in `changelog.md`.

**1.9.0 ships only what the refactor needs first.** Tier A (defects in code that moves, so
golden files are not generated over known bugs), Tier B2 (zero-risk deletions) and Tier C
(CI/tooling). The High-tier scientific and database defects ship inside 2.0.0 instead.

**Moved tests are re-pointed mechanically.** Import and receiver only, assertions untouched,
test owner reviews the diff. This stretches the standing "do not edit her suites" rule and
**needs her explicit agreement before Step 2 starts** - 1,085 view tests target methods that
move, and `test_metadata_view.py` alone is 6,026 lines. The alternative considered was leaving
a thin View facade per moved method, rejected because ~200 facades would undercut the LOC and
boundary-test metrics the refactor is measured by.

**Revisit if** the refactor stalls after Step 2, at which point the 1.9.0/2.0.0 split is worth
rebalancing so the queued Tier B fixes are not held hostage to it.

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
module invents and hangs off the root logger so all 977 decorated methods share one latch.
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
the only one. Not a bad merge, and not block 5's scoped plugin CI gate, whose step 3
concerns required *status checks* and does not extend to code-owner review.

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

Also: **`dict_dialog_widget.py` has no unit tests.** `test_data_plugin_view.py` patches
`DictDialog` out wholesale, nothing references `get_input_file`/`get_output_file`/
`get_folder`, and the e2e tests only touch `name_entry`. Writing
`tests/unit/views/widgets/test_dict_dialog_widget.py` against current behaviour is a
prerequisite for the refactor, not part of it, and would be most of the work.

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

## 2026-08-25 - The audited `bugbear`/`bandit` rules stay off as gates

*Settled 2026-08-25; reasons re-measured and corrected 2026-09-02 - the decision is
unchanged, the stated reasons were wrong for most of the rules.*

**Context.** Adopting the rest of ruff's `flake8-bugbear` and `bandit` sets was proposed as
a complement to pydoclint. Measured on `poriscope/`: B = 104, S = 54. `B006` and `B020`
were adopted outright; the rest were audited rule by rule.

**Decision.** `B905`, `B904`, `B007`, `S110`, `S112` and `S101` were each run as a one-time
audit, their findings in our own code fixed, and the rule left **unselected**. None is a
gate.

**Why, per rule.** Ruff's actual scope is the whole repository - only
mypy is scoped to `poriscope/`, and measuring these under `poriscope/` is what produced the
wrong answer originally:

- **`S101` - 2,250 sites: 7 in `NanoTrees.py`, 2,243 in `tests/`.** Ownership is not the
  obstacle at all; `assert` is the test suite's fundamental idiom, so a `per-file-ignores`
  for `tests/` would suppress 99.7% of findings. **This stays true however `NanoTrees.py`'s
  ownership resolves and whether or not it is deprecated.**
- **`B904` - 3 sites, all `tests/e2e/_helpers.py`.** Zero under `poriscope/`.
- **`B007` - 5 sites: 3 `PeakFinder.py`, 2 `tests/`.** Only the first three are owner-held.
- **`S112` - 2 sites: 1 `PeakFinder.py`, 1 `scripts/autodoc/`.**
- **`S110` - 3 sites: 2 `scripts/autodoc/`, 1 `tests/unit/views/`.** None owner-held.

In every case enabling the rule still needs a `per-file-ignores` entry, which *hides* a
real check rather than satisfying it - worse than not selecting it, because it looks
enforced. **The three `scripts/autodoc/` sites are ours and are fixable**, and are the only
part of this sweep that is; fixing them would still leave `S110` blocked by one test file
and `S112` by one `PeakFinder` line.

**`B905` (`zip` without `strict=`) is different: the rule itself is the problem.** 54 sites
each need their own judgement, at least one (`MetaDatabaseLoader`'s CSV export, list against
generator) cannot be proven equal-length in advance, and three in `ClusteringView` depend on
truncation deliberately and would raise on every clustering run.

**The audit half earned its keep**: `B905` found `MetadataView` silently dropping unlabelled
plot features, `B904` found the six readers discarding the missing file's name from
`FileNotFoundError`, and `S110` found `apply_settings` swallowing a failed `get_key()` and
leaving the dependency graph incomplete.

**Nothing from this sweep is left unfixed.** The 1 `B028` in `MetaWriter.py` was fixed
2026-09-02 (`stacklevel=2`); the 2 `B010` in `LogDecorator.py` are settled above, not
outstanding. Treat this block as finished, not as a backlog.

**Revisit if** the owner-held fitter files change hands - but that only removes the
objection for `B007` and `S112`, does nothing for `B904`/`S110` (test suite and autodoc
scripts), and nothing at all for `S101`. This is *not* the same question as the
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

`LogDecorator.log` was declared `-> Callable`, so applying it to its 935 call sites replaced
each decorated method's type with `Any` from the caller's point of view. Fixed in `5a215d8`:
`log` and `register_action` take a `TypeVar` bound to `Callable` and return the type they
were handed. Runtime is unchanged.

**The part worth keeping:** turning it on surfaced **84 call-site errors** under a gate that
had been reporting clean - 32 annotation defects and 52 genuine logic defects, all since
resolved (see `changelog.md`). So any pre-`5a215d8` claim of "mypy clean" is not evidence
that call sites were ever checked. They were not.

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

Kept because this hook is exactly the kind of change the crash would be blamed on again.
`bc09de7` (replacing a `moveEvent` monkey-patch with a real class-level override on
`StepDialog`) was a plausible cause of the `pytest tests/unit/views tests/unit/plugins`
segfault, and is **exonerated**: the same subset was re-run with `walkthrough.py` and
`walkthrough_mixin.py` checked back to `0e9433c` (pre-`bc09de7`, `on_move` absent) and it
crashed identically - same access violation, same test, same point in the run.

**Resolved 2026-08-24.** Bisected to `test_multiselect_filter.py` ->
`TestClearSelectionList` -> a single `listWidget.clear()`, and fixed by disposing of widgets
with `deleteLater()` plus a drained event loop instead of `QWidget.destroy()`.

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
