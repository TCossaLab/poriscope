# Decisions

Short records of choices made deliberately, especially choices *not* to do something.
The point is to stop the same question being re-litigated from scratch. Each entry is
context, the decision, the evidence behind it, and what would make it worth revisiting.

Detail about work that *was* done lives in `changelog.md` and in git history; this file
is only for the reasoning that would otherwise be lost.

Several entries below refer to "step 3", "step 4", "step 6" or "step 7". Those were the
numbered stages of the full-codebase type-annotation pass, which ran through August 2026
and is now complete; the plan they refer to has been pruned from `future_fixes.md` and
the outcome is summarised in `changelog.md`. The step numbers are kept here only because
they date the decision.

---

## 2026-08-25 - The audited `bugbear`/`bandit` rules stay off as gates

*Settled 2026-08-25; moved here from `future_fixes.md` on 2026-09-01, where it had been
sitting as a mostly-closed backlog table.*

**Context.** Adopting the rest of ruff's `flake8-bugbear` (B) and `bandit` (S) rule sets
was proposed on the grounds that both check real code logic and so complement pydoclint's
docstring/signature checking. Measured on `poriscope/`: **B = 104, S = 54**. `B006` and
`B020` were adopted outright and are enforced through `extend-select` in `pyproject.toml`.
The rest were audited rule by rule.

**Decision.** Every remaining audited rule - `B905`, `B904`, `B007`, `S110`, `S112`,
`S101` - was run as a **one-time audit**, its findings in our own code fixed, and the rule
then left **unselected**. None is a gate. What each surfaced is in `changelog.md`; the
short version is that the audits were worth running and the gates are not worth keeping.

**Reasoning.** Two separate reasons, and it matters which applies to which rule.

- **For `B904`, `B007`, `S110`, `S112` and `S101`, every site that remains is in an
  owner-held file** (`PeakFinder.py`, `Basic_PeakFinder.py`, `NanoTrees.py` - see the
  standing exclusion policy in `future_fixes.md`). Enabling any of them would therefore
  require a `per-file-ignores` entry for those files, which *hides* a real check rather
  than satisfying it - a worse state than not selecting the rule, because it looks
  enforced.
- **For `B905` (`zip` without `strict=`) the rule itself is the problem.** 54 sites would
  each need their own `strict=` judgement, and at least one - the list-against-generator
  zip in `MetaDatabaseLoader`'s CSV export - cannot be proven equal-length in advance. Three
  in `ClusteringView` depend on truncation deliberately and would raise on every clustering
  run. A rule that cannot be satisfied without per-site analysis is an audit, not a gate.

The audit half genuinely earned its keep: `B905` found `MetadataView` silently dropping
plot features that had no label, `B904` found the six data readers discarding the name of
the missing file from `FileNotFoundError`, and `S110` found `apply_settings` swallowing a
failed `get_key()` and leaving the dependency graph incomplete.

**Consequences worth knowing.** What is left unfixed is 2 `B010` sites in
`LogDecorator.py` and 1 `B028` in `MetaWriter.py`, all cosmetic. There is no further
bug-finding value in this block - treat it as finished rather than as a backlog.

**Revisit if.** The owner-held fitter files change hands, which would remove the
`per-file-ignores` objection for the five rules it applies to. Note this is *not* the same
question as the `bandit` proposal scoped to `poriscope/plugins/` as a trust boundary for
unvetted community contributions, which is still open (block 4 in `future_fixes.md`).

---

## 2026-08-25 - Interpolated SQL in the database plugins is accepted (`S608`)

*Settled 2026-08-25; moved here from `future_fixes.md` on 2026-09-01.*

**Context.** `bandit`'s `S608` (hardcoded-sql-expression) reports **25 sites** under
`poriscope/`, where query strings are built by f-string interpolation rather than by
parameter binding. `SQLitePeakDBLoader` in particular no longer casts its interpolated
values to `int`, which was raised in review as worth real scrutiny.

**Decision.** Accepted as-is. Not fixed, and `S608` is not enabled.

**Reasoning.** There is no privilege boundary for an injection to cross. The database is a
local SQLite file, opened by the desktop application, owned by and running as the user who
launched it. An attacker who can supply a malicious experiment name or channel id to that
application already has the ability to run code as that user, so nothing is gained by
escaping it. Injection is a defence against a *less*-privileged input reaching a *more*-
privileged executor, and that gradient does not exist here.

**Consequences worth knowing.** Correctness bugs from interpolation are a different matter
and *have* been fixed on their merits - `MetadataView`/`ProteinView` converting
experiment/channel values once at the derivation site, and the earlier quote-escaping so
legitimate experiment names stop breaking queries (both in `changelog.md`). Accepting
`S608` is not a licence to leave interpolation that produces *wrong results*.

**Revisit if.** The database is ever opened over a network path with multiple users at
different privilege levels, exposed through a service, or fed by a file the user did not
create - any of which introduces the privilege gradient this decision says does not exist.

---

## 2026-08-31 - Plugin name collisions are the user's to rename, not ours to accommodate

**Context.** Plugin discovery walks `poriscope/plugins/` and then the user plugin folder
into one flat map keyed by the plugin's class name, which is also its filename stem. Until
2026-08-31 a collision was silent and last-writer-wins, so a user file named after a
built-in replaced the shipped plugin with no way to tell which had run. Fixing that raised
the question of what *should* happen, and several accommodating answers were on the table:
let the user copy win and report the override, keep both under disambiguated names, or
record provenance so a run could at least be attributed after the fact.

**Decision.** None of those. `populate_available_plugins` keeps a set of the names already
claimed and logs at `ERROR` - which `QtHandler` raises as a dialog - for any later file
claiming a taken name, and skips it. The first file found wins, and built-ins are walked
first, so **a built-in cannot be displaced by a user plugin of the same name**. The user is
told which file was ignored and that renaming it will load it.

**Reasoning.** The goal is that people rename their collisions, not that the application
manages collisions in a way that lets them persist. A name that resolves to two different
implementations is ambiguous in the session history and in any discussion of a result, and
an override mechanism - however well reported - is a way of living with that ambiguity
rather than removing it. Making the failure loud and the remedy obvious (rename the file)
costs the user one rename, once.

**Consequences worth knowing.** There is deliberately no way to override a shipped plugin
by shadowing its filename. Someone who wants to modify a built-in's behaviour must give
their plugin its own name, which is also what makes the modification visible in the menus
and in session history. The check is keyed on the plugin name alone rather than per
metaclass, because plugin names are unique application-wide - the menus and
`DataPluginController`'s key-uniqueness check both rely on it - and a collision across two
different metaclasses was the quietest variant, leaving both classes live under one name in
two different menus.

**Revisit if.** A concrete workflow appears that genuinely needs a built-in replaced in
place and cannot use a differently-named plugin. Reporting the override more elaborately -
a provenance map, a panel message, a startup summary - is *not* a reason to revisit; that
was considered and rejected as machinery around a problem the rename already solves.

---

## 2026-08-28 - The view-test GC sweep stays; it is generation-limited, not removed

**Context.** `tests/unit/views/conftest.py`'s autouse `_close_leftover_widgets` fixture
ends with a `gc.collect()`. Matplotlib figures wrapping PySide6 widgets segfault in C++
when their Python wrappers are collected asynchronously after the Qt widgets are already
destroyed, and the explicit sweep forces that collection to happen deterministically
while Qt is still alive. This was not a theoretical hazard: it produced repeated
segfaults in CI and was settle through - `06679373` (2026-08-14) titled "prevent Matplotlib/
PySide GC segfaults in view tests".

Profiling the teardown on 2026-08-28 found that this one call was the single largest
cost in the whole test suite: **193.0s across 1,494 tests, 129ms each, 95.9% of all
teardown time and 55% of the view tree's wall clock** - roughly 30% of the entire suite.

**Decision.** Keep the per-test sweep. Make it generation-limited - `gc.collect(1)`
after every test, with a full `gc.collect()` every 50 - rather than removing or
de-frequencing it.

**Evidence.** Measured on the full view tree, back to back, all variants 1,494 passed:

| variant | wall clock |
| --- | --- |
| full `gc.collect()` every test (previous) | 340.4s |
| **`gc.collect(1)` every test + full every 50 (chosen)** | **168.5s** |
| full `gc.collect()` every 50 only | 176.9s |
| `gc.collect(1)` every test | 178.4s |
| `gc.collect(0)` every test | 184.9s |
| no GC at all | 163.7s |

Removing the sweep entirely is only 4.8s faster than the chosen option and gives up the
property that fixed CI. Dropping to "full sweep every 50 only" is both slower *and* less
safe, because it is the only fast variant that stops collecting after every test. The
chosen option reaches 97% of the theoretical maximum while changing the cadence not at
all: a collection still runs after every single test. The one behavioural difference is
that an object promoted to generation 2 waits up to 50 tests for its full sweep instead
of zero.

Why generation-limiting is nearly free: a full collect walks every generation, including
the long-lived one holding PySide6, numpy, pandas, sklearn and matplotlib. That old-
generation traversal is the 129ms, and per-test Qt garbage is not in it. Note also that
`gc.collect(0)` is *slower* than `gc.collect(1)`, and that the periodic full sweep makes
the run faster than `gc.collect(1)` alone - leaving garbage uncollected costs more later
than collecting it costs now.

**A caveat on the evidence.** All six runs above are Windows. CI is Linux under Xvfb,
where Qt/Shiboken destruction ordering differs, and that is where the original segfaults
appeared. Local green runs are not a substitute for a green CI run here.

One condition has genuinely changed since those segfaults, which is why this was worth
revisiting at all: when they occurred, the teardown only called `widget.close()`, which
hides a widget without destroying it, so Shiboken wrappers accumulated for the life of
the process and were swept in large unpredictable batches - the exact failure mode. As of
`d2ac785b` widgets are destroyed deterministically at each teardown. That lowers the risk;
it does not eliminate it.

**Revisit if.** A segfault reappears in CI in the view tests. The first thing to try is
restoring the unconditional full `gc.collect()` - a one-line change at the call site -
before investigating anything else. Do not "simplify" `gc.collect(1)` to `gc.collect()`
on the assumption it is a typo; it is deliberate and costs 172s.

---

## 2026-08-25 - Keep the four `None`-placeholder `type: ignore`s in `PeakFinder`

**Context.** `PeakFinder._populate_event_metadata` deliberately stores `None` for
`unfolded_level`, `folded_level`, `translocation_direction` and `sequence`, because those
are decided globally in `_post_process_events` and cannot be known per event.
`MetaEventFitter._populate_event_metadata` declares its return as
`Dict[str, Union[int, float, str, bool]]`, and `_define_event_metadata_types` separately
declares those same four keys as `float`/`float`/`str`/`str`, so both contracts disagree
with the value actually written. Four narrow `# type: ignore[assignment]` mark the sites.

**Decision.** Leave them. Do not widen the ABC to clear them.

**Evidence.** The behaviour is correct: `SQLiteDBWriter` maps the declared types through
`pytype_to_sql_type` to build `REAL`/`TEXT` columns, and SQLite accepts `NULL` in any
column without a `NOT NULL` constraint, so nothing fails at runtime. This is a
type-contract mismatch, not a latent crash. Against that, clearing it means widening two
`Meta*` ABC methods to `Optional[...]`, and because `test_plugin_compliance.py` compares
annotations **by equality** every override has to move in lockstep - `CUSUM`,
`IntraCUSUM`, `NoFitter`, `NanoTrees`, `PeakFinder` and `Basic_PeakFinder`, six files, two
of which belong to another developer and one of which may be deprecated. It would also be
a breaking change to the plugin contract requiring a changelog callout. Four documented
suppressions are the smaller cost.

**The cheaper alternative if it is ever wanted.** Do not write the keys at all until
post-processing fills them - absence rather than `None`. The columns still come from
`_define_event_metadata_types`, so the schema is unaffected. That is a logic change in the
owning developer's file and needs checking that the writer tolerates a row missing a
declared key.

**Revisit if.** A third-party plugin ecosystem exists, or someone wants `NOT NULL`
constraints on those columns.

---

## 2026-08-25 - Do not consolidate the double-Gaussian fits; the owner is rewriting them

**Context.** Three separate double-Gaussian implementations existed: `bitthresh`'s nested
`dgfit`, `ProteinView._fit_double_gaussian`, and `PeakFinder.fit_2_gauss`. Consolidating
onto the ProteinView implementation was scoped in detail - it is the only one with a
sanity-check layer (covariance checks, a t-test on mean separation, an amplitude-ratio
floor), and its normalization turned out to live in the caller rather than in the fit, so
it is already scale-agnostic and portable as-is.

**Decision.** Do not do it. The developer who owns the PeakFinder family is rewriting that
fitting code from scratch, which supersedes the consolidation.

**What was done instead.** `fit_2_gauss` was deleted. It had no call sites and could not
have run: beyond a nested `Gauss` declared with four parameters and called with five, it
passed a 1000-point linspace as `xdata` against the raw `(N, 1)` sample array as `ydata` -
rejected by `curve_fit` unless an event is exactly 1000 samples, and not a distribution
fit in any case, since both axes are current values rather than bin centres and counts.
Deleting a dead third implementation does not conflict with a rewrite. `bitthresh` and
`dgfit` are untouched and remain the live path.

**Revisit if.** The rewrite lands and still leaves two divergent implementations, at which
point the ProteinView port is the obvious target and the scoping above still holds.

---

## 2026-08-24 - Leave two of the three unguarded `Optional` Qt accessors alone

**Context.** The type-annotation pass flagged three families of Qt accessor that return
`Optional` and are used without a `None` check: `QApplication.instance()`,
`QComboBox.lineEdit()`, and `QTreeWidgetItem.child(i)`/`topLevelItem(i)`.

**Decision.** Only `lineEdit()` was changed. It is now bound once in `__init__`,
immediately after the `setEditable(True)` that makes it non-`None`, because that
guarantee previously sat hundreds of lines away from the uses depending on it. The other
two need no action and should not be "fixed" later:

- `QApplication.instance()` is called inside a `QWidget.__init__`. A `QWidget` cannot be
  constructed before a `QApplication` exists, so `None` is unreachable there.
- `item.child(j)` / `topLevelItem(i)` are always called inside
  `for j in range(...childCount())`, so the index is always valid. This is mypy being
  unable to connect `range(n)` with "valid index", not a defect.

**Revisit if.** Either call moves somewhere that is not a widget constructor, or an
index stops being derived from the matching count.

---

## 2026-08-24 - `@log` erases decorated signatures (RESOLVED 2026-08-26)

**Context.** `LogDecorator.log` is declared `-> Callable`, i.e. `Callable[..., Any]`.
Applying it therefore replaces the decorated method's type with `Any` from the caller's
point of view. Verified with `reveal_type` against the project mypy: for a method
`decorated(self, x: int) -> str`, `reveal_type(p.decorated)` is `Any` and
`reveal_type(p.decorated(1))` is `Any`, while the undecorated twin reveals
`def (x: int) -> str` and `str`. A deliberately wrong call - `p.decorated("not an int")`
- raises no error, where the same call on the undecorated twin does.

**Why it matters.** `@log(logger=logger)` is applied to **935 methods across 71 files**.
So the type-annotation pass had made every *body* checkable, but call sites into any
decorated method were still unchecked, and turning on `disallow_untyped_defs` would not
have changed that. That is why this had to be fixed before the pass could be closed.

**Original decision (2026-08-24).** Not fixed as part of the annotation pass, which was
scoped to hints and docstrings. Recorded as a prerequisite for getting full value from
step 7.

**RESOLVED 2026-08-26 (commit `5a215d8`).** Fixed as written: `log` and `register_action`
now take a `TypeVar` bound to `Callable` and return the type they were handed, with
`@overload`s for `log`'s two calling conventions. `reveal_type` confirms the erasure is
gone - a decorated `(x: int) -> str` reveals as `def (x: int) -> str` rather than `Any`,
generator methods keep their `Generator[...]` type through the `yield from` wrapper, and
deliberately wrong calls now error. Runtime is unchanged; the two `cast()` calls are
no-ops and `functools.wraps` / `inspect.signature` / `isgeneratorfunction` all behave as
before.

**What it cost, which is the part worth knowing.** Turning it on surfaced **84 call-site
errors** under a gate that had been reporting **clean**. 32 were annotation defects and
were fixed in the same commit; **52 were genuine logic defects**, all since resolved -
see `changelog.md` for what each of them was. So the pre-commit gate's clean history up
to this point should not be read as evidence that call sites were ever checked - they
were not. Treat any pre-`5a215d8` claim of "mypy clean" accordingly.

---

## 2026-08-26 - Never `@overload` around an over-broad return union

**Context.** `MetaReader.get_channel_length` was
`(self, channel: Optional[int] = None) -> int | Dict[int, int]` - one channel's sample
count when given a channel, a dict of every channel when given nothing. Because mypy
resolves a return type from the declaration and not from the argument passed, every caller
saw the union, and 15 of the 84 errors above were arithmetic on `int | dict[int, int]`.
The obvious typing fix is two `@overload` stubs.

**Decision.** Do not do that. When a return union makes a value unusable at its call
sites, **verify every incoming call and delete the dead branch instead**. `cast()` at the
call sites is equally rejected. If *both* arms turn out to be genuinely live, **flag it
for review** rather than overloading - the preferred resolution is to change the incoming
calls so the branch is unnecessary. In practice `@overload` is never the answer here.

**Evidence.** The `get_channel_length` dict branch had **no callers anywhere**: all five
call sites in `poriscope/` passed a channel, the `MetaReader` test double at
`tests/unit/utils/test_meta_event_finder.py:48` has always declared `channel` as required,
and internally the dict was reached through the `total_channel_samples` attribute directly
rather than through the method. The union dated to the initial commit and no caller ever
motivated it. Narrowing to `(self, channel: int) -> int` cleared all 15 errors with no
casts and no overloads. `MainModel.get_available_plugins` had the identical shape and the
identical outcome.

**On breaking the plugin contract.** Both of those are public API - `MetaReader` is a
`Meta*` ABC. This is acceptable: there are no third-party plugins in existence yet. The
obligation that remains is that **the break is called out explicitly in `changelog.md`**,
because the changelog is what a future plugin author will read.

**When both arms are genuinely live.** `MainModel.get_plugin_classes` was the first case
where neither branch was dead: `main_controller.py:64` used the no-argument dict-of-dicts
form and `:405` used `get_plugin_classes("MetaController")[subclass]`. The resolution is
**to delete the optional-argument arm, not the parameter** - make the argument required so
the function has one job and one return shape, and let the single call site that wanted the
aggregate rebuild it with a comprehension. The preference is for functions that do not take
`None` as a mode switch, not merely for functions that avoid unions.

Check one thing before doing it: whether the call site currently receives a *live
reference* to a mutable attribute that something else later mutates, since a comprehension
hands over a fresh outer object instead. For `get_plugin_classes` that was safe -
`available_plugin_classes` is populated exactly once in `MainModel.__init__` and never
reassigned or mutated afterwards.

**Revisit if.** A third-party plugin ecosystem actually exists, at which point the
cost/benefit of narrowing an ABC changes and these become deprecation cycles instead.

---

## 2026-08-26 - Scoping the mypy hook to `poriscope/` gives up type-checking of `tests/`

**Context.** Step 6 scoped the pre-commit `mypy` hook with `files: ^poriscope/`, because
it had been passing test files as explicit paths and `mypy.ini`'s `exclude = ^tests/`
does not apply to explicitly listed paths - only to directory discovery.

**Decision.** Accept that test files are now unchecked by the gate.

**Evidence, including the cost.** That blind spot was not purely noise: it caught a real
defect once, the `{"MetaReader": []}` fixture shape in
`tests/unit/controllers/test_data_plugin_controller.py` that should have been
`{"MetaReader": {}}` (see `changelog.md`, "Type annotations for data-plugin management").
So this trades away one genuine finding source. It is still right: `tests/` is excluded by
project policy in `mypy.ini`, the hook was contradicting that policy by accident rather
than by design, and leaving it would mean `disallow_untyped_defs` starts failing every
commit on unannotated test code that nobody intends to annotate. If test type-checking is
ever wanted, it should be a deliberate second hook with its own config, not a side effect
of how pre-commit passes filenames.

**Revisit if.** Someone decides `tests/` should be type-checked on purpose.

---

## 2026-08-24 - Leave the PySide6 short-form enum accesses alone

**Context.** A stub-aware `mypy poriscope` reports 191 `attr-defined` errors of the form
`"type[QSizePolicy]" has no attribute "Expanding"` across ~11 files, because the bundled
PySide6 stubs no longer declare the unscoped enum members.

**Decision.** Do not rewrite them to the scoped form (`QSizePolicy.Policy.Expanding`).

**Evidence.** On the installed PySide6 6.9.0, `QSizePolicy.Expanding` emits no warning of
any kind, and `QSizePolicy.Expanding is QSizePolicy.Policy.Expanding` is `True` - as is
the equivalent for `Qt.AlignCenter`. These are the identical objects, not lookalike
aliases, so this is a stub omission rather than a code defect. A 191-site mechanical
rename with no behavioural change would make review harder, not easier: it buries real
changes and rewrites `git blame` across eleven files. The tempting justification - that
clearing them makes a stub-aware mypy usable as a review tool - does not hold either,
because of the 377 errors that run reports, roughly 308 are noise from other sources
(34 `import-untyped`, 38 `MetaController.view`/`model`, 34 numpy stub pedantry, 11
known-accepted `sublevel_starts`), so clearing the enums alone still leaves ~117 noise
items against a handful of real findings.

**Revisit if.** PySide6 deprecates or removes forgiving-enum mode. Waiting costs nothing:
on the day it changes, every site fails loudly at widget construction and the fix is a
mechanical find-and-replace with the failures pointing at each location.

---

## 2026-08-24 - Accept that the pre-commit mypy hook cannot see project dependencies

**Context.** The `mirrors-mypy` hook runs in an isolated virtualenv containing only mypy,
with `additional_dependencies: []` and upstream default args
`["--ignore-missing-imports", "--scripts-are-modules"]`. PySide6, numpy, pandas, scipy
and sklearn therefore all resolve to `Any` under the gate. Concretely,
`reveal_type(button_mapping.get(button_type, lambda: None))` where
`button_mapping: Dict[str, QPushButton]` prints `Any` under the hook and
`QPushButton | (def ())` under the project venv's mypy - which is why the gate could not
see the `on_button_clicked` fallback bug.

**Decision.** Do not add stubs to the hook. Do not treat this as a blocker for flipping
the type-policy flags.

**Evidence.** See the composition breakdown in the entry above: the genuine signal was 11
`union-attr` findings, all one narrow class (a Qt getter that can return `None`), of
which three were the `button_mapping` bug and eight remain in `SelectionTree.py` and
`MetaView.__init__`. Against that, closing the gap means suppressing or fixing ~191 enum
sites first and then keeping pinned stub versions in sync with the runtime PySide6
forever - and stub drift is what produced that noise in the first place. The hook still
checks all first-party logic and the whole `Meta*` plugin contract, which is the
load-bearing part of this architecture.

**Cheaper alternative if wanted.** Run `mypy poriscope` in the dev venv periodically and
review by hand - possible today with no config change - or add it to the pre-PR
checklist, rather than making it block commits.

**Revisit if.** The `union-attr` class of bug starts recurring in production, or the enum
noise is cleared for other reasons.

---

## 2026-08-24 - The walkthrough `moveEvent` hook is not the cause of the test-suite segfault

**Context.** Running `pytest tests/unit/views tests/unit/plugins` (views first) segfaults
the interpreter inside
`test_walkthrough_mixin.py::test_no_valid_widgets_logs_error`. Commit `bc09de7` had just
replaced a `moveEvent` monkey-patch with a real class-level override on `StepDialog`,
which was a plausible cause: it puts a Python virtual on the move path, `StepDialog`
starts a 300 ms `reposition_timer` that calls `move()`, and the file already carries a
documented `Overlay`/`StepDialog` double-delete hazard (two tests are skipped for
"Qt object lifetime makes this unreliable across platforms").

**Decision.** `bc09de7` is exonerated. Do not revert it, and do not re-derive this
theory.

**Evidence.** The same subset was re-run with `walkthrough.py` and `walkthrough_mixin.py`
checked back to `0e9433c` (pre-`bc09de7`, `on_move` absent from both files, verified) and
the views-first ordering held constant. It crashed identically - same access violation,
same test, same point in the run. The real cause is pre-existing Qt state leakage that
only manifests when `tests/unit/views` runs before `tests/unit/plugins`; pytest executes
explicitly listed paths in the order given, and natural alphabetical collection puts
`plugins` first, which is why CI and the full suite never see it.

**Revisit if.** The crash appears under natural collection order, which would mean it is
a different problem.

**Resolved 2026-08-24.** Bisected to `tests/unit/views/widgets/test_multiselect_filter.py`
-> `TestClearSelectionList` -> the single `listWidget.clear()` call, and fixed by disposing
of widgets with `deleteLater()` plus a drained event loop instead of `QWidget.destroy()`.
See `changelog.md`. The exoneration above stands and is kept because the `moveEvent` hook
is exactly the kind of change this crash would be blamed on again.

---

## 2026-08-25 - Leave `_load_filter`'s DOC501/DOC503 baselined; the `ValueError` never escapes

**Context.** Step 4 finished the in-scope pydoclint backlog and left five entries in the
baseline. Four of them are a matched DOC501/DOC503 pair on `MetadataView._load_filter`
(`MetadataView.py:1802`) and `ProteinView._load_filter` (`ProteinView.py:1295`): each body
contains `raise ValueError("Invalid filter file format. Expected a dictionary.")` while the
docstring has no `Raises` section.

**Decision.** Do not add a `:raises ValueError:` line to either docstring. Leave both pairs
baselined.

**Evidence.** In both methods the `raise` sits inside a `try:` whose `except Exception as e:`
is in the *same function* and merely logs (`self.logger.error(f"Failed to load filters: {e}")`).
The exception cannot reach a caller, so documenting it would tell callers to handle something
they will never see - strictly worse than the current silence. pydoclint's DOC501 counts
`raise` statements syntactically and does no try/except reachability analysis, so it reports
these regardless.

**What would actually fix it.** The `raise`/`except` pair is being used as a local goto: the
honest form is to log the error and `return` at that point instead of raising into the
function's own handler. That is a logic change, deliberately out of scope for the
type-annotation pass, and it is queued in `future_fixes.md`.

**Revisit if.** That control flow is straightened out, at which point both pairs disappear
from the baseline on their own.

**Resolved 2026-08-25.** The control flow was straightened out on request. The read and
parse step keeps a narrow `except (OSError, json.JSONDecodeError)`, the shape check is a
plain log-and-return, and the forty lines of combo-box and signal work below are no longer
wrapped - so a genuine Qt failure there now surfaces instead of being swallowed. Both
`DOC501`/`DOC503` pairs disappeared with the `raise`. See `changelog.md`.

---

## 2026-08-25 - Leave `IntroDialog`'s DOC605 baselined rather than keep malformed RST to satisfy it

**Context.** The fifth surviving in-scope baseline entry is DOC605 on `IntroDialog`
(`plugins/analysistabs/utils/walkthrough.py:52`), whose class docstring documents its Qt
signal as:

```
    .. attribute :: start_walkthrough
        :type: Signal
```

against a bare `start_walkthrough = Signal()`. Note the space before the `::`.

**Decision.** Leave it exactly as it is, and leave the DOC605 baselined.

**Evidence.** Every combination was measured against pydoclint directly rather than guessed:

| Docstring form | Attribute declaration | Result |
| --- | --- | --- |
| `.. attribute :: ` (as-is) | `= Signal()` | DOC605 - one entry |
| `.. attribute:: ` (valid RST) | `= Signal()` | DOC601 + DOC603 - two entries |
| `.. attribute:: ` | `: Signal = Signal()` | DOC601 + DOC603 |
| `.. attribute:: ` | `: ClassVar[Signal] = Signal()` | DOC601 + DOC603 |
| `:ivar:`/`:vartype:` | either | DOC601 + DOC603 |
| `.. attribute :: ` (as-is) | `: Signal = Signal()` | clean |

So the only form pydoclint accepts is the one that keeps the malformed directive. Correcting
the reStructuredText makes the baseline *worse*, because pydoclint stops recognising the
attribute at all.

**The cost of leaving it.** `.. attribute :: name` is not a valid docutils directive - the
space before `::` turns it into a comment - so Sphinx renders nothing for it either. This is
the codebase's only use of the construct, so there is no convention at stake.

**What would actually fix it.** Either set `check-class-attributes = false` under
`[tool.pydoclint]`, which is defensible given that no sphinx-style attribute syntax appears to
satisfy this version, or annotate the signal and switch the docstring to a form that both
Sphinx and pydoclint read. The latter touches a PySide6 `Signal` declaration and so needs a
test run; it is not a docstring-only change and was therefore out of scope for step 4.

**Revisit if.** `pydoclint` fixes the parser, at which point the correct directive should
start being recognised and the check can be turned back on.

**Resolved 2026-08-25, and the cause is an upstream bug rather than a quirk.**
`docstring_parser_fork/rest_attr_parser.py` hardcodes the literal `".. attribute ::"` -
*with a space before the `::`* - in both `parse_attributes()` and `parse_attribute_block()`.
That is not a valid reStructuredText directive: docutils requires `.. name:: arguments`, and
the extra space makes the line a comment, which is why Sphinx rendered nothing for it. The
correct `.. attribute::` form and every canonical field form (`:ivar:`, `:cvar:`, `:var:`)
all parse to an empty attribute list, so under sphinx style the check could only ever fire
against docstrings that were wrong. pydoclint's own documentation page prescribes the
invalid spelling. Both packages were already at their latest release (`pydoclint` 0.9.1,
`docstring_parser_fork` 0.0.16), so there was no upgrade to take.

The resolution was therefore to correct the reStructuredText in `walkthrough.py` so Sphinx
actually renders the signal, and set `check-class-attributes = false` in `pyproject.toml`
with that rationale recorded inline. **The upstream bug has now been filed as
https://github.com/jsh9/pydoclint/issues/304.** Nothing further is needed from this end;
`check-class-attributes` stays `false` until a `pydoclint` release fixes the parser, per
the revisit condition above. The one-line fix and a reproduction are kept in
`future_fixes.md` in case the report needs to be restated.
