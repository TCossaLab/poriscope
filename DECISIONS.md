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

## 2026-09-02 - The plugin trust boundary is checked with ruff, not bandit, and is not a sandbox

**Context.** Plugin discovery executes every file it walks:
`MainModel.populate_available_plugins()` runs from the constructor and `load_plugin` calls
`spec.loader.exec_module`, so module-level code in any `.py` file under
`poriscope/plugins/` or the user's plugin folder runs at app start, before any compliance
check has inspected the class. Block 4 in `future_fixes.md` proposed policing that. Two
gates now do - `ruff-plugin-security` and `plugin-module-level` - and three parts of the
original proposal were deliberately dropped.

**Decision 1: no `bandit`.** Block 4 step 1 called for adding `bandit` to
`requirements-dev.txt` as its own hook. It was not added. Ruff `0.12.11` is already
pinned in `.pre-commit-config.yaml`, already implements flake8-bandit's `S` rules, and
already runs in CI; a second tool would mean a second config, a second pinned version,
overlapping findings on the same files, and an edit to both `requirements-dev.txt` and
`pyproject.toml`'s `[dev]` extra, which
`scripts/hooks/post-merge-update_requirements.py` keeps byte-identical.

The gaps that leaves are known rather than guessed. `S403`/`S404` - importing `pickle` or
`subprocess` without calling them - require ruff preview mode and are not available as
stable rules, so they are not in the selection. `__import__("os")` is flagged by neither
ruff nor bandit; verified against a probe file. A module-level `__import__` is caught by
`plugin-module-level` instead, but one inside a method body is invisible to both.

**Revisit if** a submission actually turns up a dangerous pattern that ruff structurally
cannot see. Adding bandit to close a hypothetical gap is not worth a second toolchain;
adding it to close a real one would be.

**Decision 2: the module-level check skips `analysistabs/`.** It is scoped to the eight
data-plugin families, which is what an outside contribution realistically adds - nobody
submits an unreviewed Controller/Model/View triad from a fork. Measured: those 34 files
have zero module-level statements outside imports, constants, classes and functions, so
the rule needs no exceptions at all. Extending it to `analysistabs/` would require
permitting three further patterns for six benign sites - `warnings.filterwarnings` (3),
an `os.environ` write under a `sys.platform` guard (1), and `if __name__ == "__main__":`
demo blocks (2) - and a rule with carve-outs is weaker than a rule with none, because the
carve-outs are what an attacker writes against. Those files remain covered by
`ruff-plugin-security`, which is scoped to the whole plugin tree and needs no exemptions
anywhere.

**Decision 3: this is not a sandbox, and no CI workflow was touched.** Block 4's own
gotcha said as much and it is worth restating, because the checks are easy to mistake for
more than they are. Anything inside a method body that only runs once the plugin is
instantiated is beyond a static pass, and **neither check sees the runtime path at all** -
a user dropping a `.py` file into `%LOCALAPPDATA%/Poriscope/user_plugins` gets it executed
with no pull request and no CI in between. Plugins are reviewed by a human before they
merge, and that review is the real gate; these hooks raise the bar against a careless
submission.

No workflow file changed, and no changed-file computation was built, because
`ci-fork-pr.yml` and `ci-branches.yml` already run `pre-commit run --all-files` - so a
pre-commit hook is already enforced on every incoming PR. Block 5 step 2's
`git diff --name-only` machinery is unnecessary for a check that reports zero.

**Revisit if** true isolation is ever wanted (subprocess isolation, restricted execution).
That is a much larger architectural change and belongs in its own design discussion, not
as an increment on this one.

## 2026-09-02 - `CODEOWNERS` stays advisory; code-owner review is not enforced

**Context.** `.github/CODEOWNERS` landed in 1.8.0, mapping each subsystem and plugin
family to its maintainer so a pull request automatically requests review from the right
person. GitHub offers a branch-protection setting, *Require review from Code Owners*,
that turns the same file into a merge block. `future_fixes.md` block 5 had assumed from
the start that the file was only worth having with that setting on, describing the goal as
"no plugin file merges without ... a human sign-off" and calling the toggle the thing that
would give the file "teeth".

**Decision. The toggle stays off, on every branch.** The file is a guideline for routing
attention, not a hard edit limit and not a barrier to contribution. Block 5's wording was
corrected rather than implemented, so the enforcement step is not left looking like
unfinished work.

**Evidence and reasoning.**

- **Team size.** Three people have commits in the last six months, and five have ever been
  named as contributors. Enforced review is a coordination mechanism for a team large
  enough that the right reviewer is not obvious; at this size everyone already knows who
  maintains what, and the file exists to spare them having to remember to tag each other,
  not to referee them.
- **Fork contributions are a first-class path.** `.github/workflows/ci-fork-pr.yml` exists
  specifically for pull requests from forks, which is the realistic route for a community
  plugin. A required-owner-review rule would put one named individual in front of every
  such contribution.
- **Some owners cannot answer.** Two contributors named in `# Contributors:` headers have
  left the lab, and one of them has no GitHub handle at all. GitHub silently ignores a
  `CODEOWNERS` line naming anyone without write access, so under enforcement the gate
  would be unpredictable as well as unwelcome - blocking on some paths and quietly not on
  others.
- **The checks that matter already block.** Correctness is gated by the automated hooks
  and CI described in `quality_control.rst`, which every pull request must pass. Owner
  review adds judgement, which is worth requesting and not worth requiring.

**Revisit if the contributor list grows past six people.** That is the user's stated
trigger, and it is a scale judgement rather than an objection to enforcement in principle
- so the question is genuinely open again at that point, and only at that point. Nothing
else reopens it: not a bad merge, and not the arrival of the scoped plugin CI gate in
block 5, whose step 3 concerns required *status checks* and explicitly does not extend to
code-owner review.

## 2026-09-01 - No custom lint rules for the three conventions `CLAUDE.md` documents

Proposed as block 8 of the community-plugin compliance gate: write `ast`-based checkers
enforcing three conventions that were held by review attentiveness alone. **Nothing was
built, and nothing should be.** All three resolved without a checker.

**No nested functions - dropped, because the convention itself changed.** `CLAUDE.md` no
longer prohibits nesting outright: a short, simple nested function is fine where it is
genuinely the simpler option, typically a small closure captured for a callback or timer.
That is a judgement an `ast` walk cannot make. A checker would have to approximate it with
a line-count or complexity threshold and would flag exactly the small callback closures the
revised convention permits. Do not build it.

**Bare `except:` - already enforced, and always was.** The block asked whether Ruff had a
built-in rule and whether it was enabled; the answer to both is yes. `E722` is in Ruff's
**default** rule set, and `pyproject.toml`'s `extend-select` adds to that set rather than
replacing it, so the gate has been catching bare `except:` all along even though no line of
config names it. Measured rather than reasoned: a throwaway file containing a bare `except:`
was placed under `poriscope/` and `pre-commit run ruff --files ...` failed it with
`E722 Do not use bare except`. The one-line config addition the block held in reserve would
have been a no-op.

**Explicit sqlite3 cleanup in a `finally` block - deferred by design, not queued.** This is
a semantic rather than syntactic pattern: a general checker would have to track whether a
`sqlite3.connect`/`.cursor()` result is closed on every exit path. The block itself
concluded the right home for it is the behavioural conformance suite (block 1), whose
open-file-handle check catches the same defect empirically. That suite is owned by the test
developer, so this rides along with it whenever it is built rather than being separate work.

Documenting whichever of these became real automated checks is done: `quality_control.rst`'s
"Which rules are enabled" note says Ruff's defaults are in force on top of the selected
rules and names `E722` as the example that matters. It is deliberately **not** added to
`CLAUDE.md`, which is loaded in full every session and should carry rules a human has to
remember - a rule the gate enforces on every commit is not one of those.

**What would reopen this:** the owner-held fitter files changing hands would not; only a
convention that is genuinely syntactic, and that review keeps missing, would justify a
custom checker.

## 2026-09-01 - The three reserved file-parameter names stay as they are

**Context.** `BaseDataPlugin._validate_param_ranges` skips its `Value in Options` check for
three literal parameter names - `Input File`, `Output File`, `Folder` - because for those
the `Options` list holds file-dialog filters (`"ABF2 Files (*.abf)"`) rather than
permissible values. This was recorded in `future_fixes.md` as "plugin-specific knowledge in
the universal validator", with a proposed fix: a `"Validate Options": False` flag in the
settings schema, so the base class would not need to know any names. The question came up
again on 2026-09-01 when the three other defects in that same entry were fixed and the
names were consolidated into `settings_schema.FILE_DIALOG_PARAMS`.

**Decision.** Keep the three literal names and the shared constant. **The
`"Validate Options": False` flag is rejected outright rather than deferred.** No code
changes.

**Reasoning.** The proposal aims at the wrong site. The names appear at roughly 20 places,
and **17 of them are in `views/widgets/dict_dialog_widget.py`** - the widget dispatch at
`:131`/`:150`/`:169`, the picker write-backs at `:277`/`:318`/`:343`, the
`key not in [...]` tests at `:216`/`:370`, and the three `check_validity` clauses at
`:356-363`. One is the `FILE_DIALOG_PARAMS` constant, one is `DataPluginController:517-524`'s
`Folder` default, and the validator itself now holds none, since it imports the constant.
So the flag would clear the single site that is already contained behind a shared
definition and leave every load-bearing one untouched.

It is also the wrong *shape* of key. `"Validate Options": False` describes what not to
check. A schema key that described what the parameter **is** could drive both the
validator and the dialog's widget selection; a suppression flag can only ever do the
former. Adopting it would foreclose the better fix by spending the schema-contract change
on the lesser one.

**The better fix, if it is ever needed**, recorded so it does not have to be rediscovered:
an optional `"Kind"` key taking `"input file"`, `"output file"` or `"folder"`. Every site
that currently asks "is this key named `Input File`?" asks "is this parameter of kind
`input file`?" instead. The five bases that create these entries (`MetaReader:311`,
`MetaWriter:168`, `MetaEventLoader:160`, `MetaDatabaseLoader:351`,
`MetaDatabaseWriter:460`) declare the kind, and since every plugin is required to build its
schema from `super().get_empty_settings()`, all 24 shipped plugins inherit it with no edit
of their own. A `kind = entry.get("Kind") or _legacy_kind_for_name(key)` fallback keeps a
hand-rolled user plugin working and confines the literal names to one function.

**Consequences worth knowing.** Each picker callback hardcodes the key it writes to
(`self.params["Input File"]["Value"] = input_file`), so **a plugin can have at most one
file input, one file output and one folder**, and a file parameter cannot be given a
descriptive name - not "Calibration File", only "Input File". A reader taking a data file
*and* a separate calibration file cannot be expressed today. That limitation is accepted
here; it is the real cost of the design, and it is what the revisit trigger below is about.

Also worth knowing before anyone attempts this: **`dict_dialog_widget.py` has no unit
tests.** `tests/unit/views/test_data_plugin_view.py` patches `DictDialog` out wholesale,
and nothing in the repository references `get_input_file`, `get_output_file` or
`get_folder`; the e2e tests construct the real dialog but only ever touch `name_entry`. So
the widget dispatch, the three picker callbacks, `check_validity` and `on_ok` are
unverified by anything, on a path every plugin creation traverses. Writing
`tests/unit/views/widgets/test_dict_dialog_widget.py` against the *current* behaviour is a
prerequisite for the refactor, not part of it, and would be most of the work.

**Revisit if.** Someone expresses a need for a plugin that takes **more than one file
input** - or more than one output, or more than one folder. That is the capability this
design forecloses, and it is the only thing that makes the change worth its risk. Removing
plugin-specific names from the universal validator is explicitly **not** a reason to
revisit: that was the original motivation, it was measured, and it turned out to be worth
far less than it sounded.

---

## 2026-09-01 - The multiselect popups' event filter stays on the application

**Context.** `MultiSelectFilterComboBox` and `MultiSelectComboBox` closed their popup when
the user clicked outside it, using a filter installed on the `QApplication` singleton and
never removed - a leak that caused an intermittent `RuntimeError: Internal C++ object ...
already deleted` in the test suite. The obvious fix, and the one the handoff note in
`future_fixes.md` recommended, was to scope the filter to `containerWidget` or to `self`
instead of the application, following the `walkthrough.py`/`help.py` precedent.

**Decision.** The filter stays **on the application**. Only its *lifetime* was narrowed: it
is installed in `showPopup()` and removed in `hidePopup()`, so it exists only while a popup
is open.

**Reasoning.** Scoping it to the container would have silently broken click-outside-to-close
on Windows and macOS. `Qt::WindowType` is a value in the low byte of the flags word, not a
set of independent bits, and `Tool == Popup | Dialog == 11`. Both widgets build their
container as a `QDialog` and then OR `Qt.Popup` into the existing flags - which already
include `Qt::Dialog` - so `windowType()` comes out as **`Qt::Tool`**, not `Qt::Popup`.
Verified against the installed PySide6 6.9.0 with the real construction pattern:

```
Dialog=3  Popup=9  Tool=11
Dialog|Popup == Tool          -> True
(Dialog|Popup) & Mask == Popup -> False
QDialog(...) + windowFlags()|Qt.Popup  ->  windowType=11 (Tool)
```

A tool window is not a popup: `isPopup()` is false, Qt never enters popup mode for it, there
is no implicit mouse grab, and a press elsewhere in the application is delivered to whatever
is under the cursor and never routed to the container. A filter installed on the container
would therefore never see the click it exists to detect. Qt also does **not** auto-close even
a genuine popup on an outside press - `QWidgetWindow::handleMouseEvent` only closes *disabled*
popups; the familiar behaviour is implemented by `QMenu` in its own `mousePressEvent`.

Only `multiselect.py`'s Linux branch produces a real popup, because it calls
`setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)`, which *replaces* the flags rather than
OR-ing into them. That asymmetry is very likely why the application-wide filter was written
in the first place, and why the Linux path was special-cased.

**Consequences worth knowing.** The Linux/offscreen CI run cannot exercise the load-bearing
path, because there the container really is a popup. Anything that changes this filter needs
a manual check on Windows. The `walkthrough.py`/`help.py` precedent of scoping a filter to a
narrower object is still the right default - it just does not apply to a widget whose whole
purpose is to observe events aimed at *other* widgets.

**Revisit if.** The containers are converted to genuine `Qt::Popup` windows on every platform
(`setWindowFlags` rather than OR-ing), which would let Qt's grab do the routing and unify the
two platform paths. That was considered and deliberately not bundled into a crash fix: it is a
visible UX change on the primary platform, since the popup would lose its title bar, its
"Select Filter"/"Select Channel" caption, its close button and its movability.

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
