---
name: refactoring-codebases
description: Plans and executes large refactors of existing codebases end to end - diagnosing the structural root cause, re-verifying the plan against the code, building a safety net (characterization tests, goldens, exact-match ratchets) before anything moves, sequencing the work into commits that each bank a measured win, verifying beyond the test suite, and running an exit review and post-refactor cleanup. Builds on the planning-and-executing-changes skill, which holds the general lessons about plans, tests, gates and verification; this one adds what is specific to moving code while preserving behaviour. Use whenever the user asks to plan, scope, review, sequence or carry out a refactor, restructure, layering or architecture fix, deduplication, base-class or API redesign, mechanism replacement, or tech-debt cleanup spanning more than a few files, or asks to write or check a refactor plan, safety net, ratchet, handoff or exit review - even if they never say "refactor".
---

# Refactoring codebases

A refactor is a claim that behaviour is preserved while structure improves. Both halves need
an instrument, or the claim is only asserted. This skill is the procedure for making both
halves measurable, and the catalogue of ways the measurements lie.

It was distilled from a three-week, nine-step refactor of a desktop MVC application with a
plugin system (roughly 2,900 tests growing to 4,200 along the way), whose plan was re-verified
ten times during execution and moved claims every time. Every lesson carries the case that produced it. The cases are illustrations; the
rules are language- and framework-neutral.

**Load `planning-and-executing-changes` first.** Most of what that refactor taught applies to any
change, so it lives in that skill: re-deriving inherited claims, the plan-review-execute loop,
tests that can fail, gates that are blind, verification beyond the suite, finishing, and records.
This skill adds what is specific to a refactor. Lesson IDs are unique across the two skills; an ID
cited here that is not in this skill's reference files is in the general one, and
[lesson-index.md](reference/lesson-index.md) lists both.

## The stance

The general stance - every claim is a dated measurement, check the mechanism not its name, every
gate is blind somewhere, record the wrong turns - is in `planning-and-executing-changes`. A refactor
adds two:

1. **Pin what moves before moving it**, scoped by what the refactor touches, not by what looks
   under-tested.
2. **Build instruments that fail in both directions**, so every commit must bank its own win
   and none can quietly borrow one.

## Reference files - read the one for the phase you are in

| File | Read when |
|---|---|
| `planning-and-executing-changes` (the general skill) | Always, first: its planning, testing, measurement, execution, verification, finishing and records files hold most of the lessons |
| [reference/planning.md](reference/planning.md) | Writing or re-verifying a refactor plan; sizing or sequencing a step; a step "looks cheap" |
| [reference/safety-net.md](reference/safety-net.md) | Deciding what to pin before a move; building characterization tests, goldens, equivalence tables, flows |
| [reference/instruments.md](reference/instruments.md) | Building or reading a ratchet, allowlist, coverage audit or any progress metric |
| [reference/execution.md](reference/execution.md) | Moving, promoting, deduplicating, converting calls, deleting code, editing tests after a move |
| [reference/verification.md](reference/verification.md) | What a refactor adds to the general verification routine |
| [reference/exit-and-cleanup.md](reference/exit-and-cleanup.md) | The last structural change has landed: exit review, cleanup procedure, release readiness |
| [reference/collaboration-and-records.md](reference/collaboration-and-records.md) | What a refactor adds to the general records lessons: the plan document's shape |
| [reference/lesson-index.md](reference/lesson-index.md) | Looking up a lesson by ID or by symptom (grep it) |

Templates live in `templates/`; deterministic helpers in `scripts/` (see the end of this file).
The general skill has the rest: `run_logged.py`, `mutation_probe.py`, `structural_diff.py`, and the
manual-pass map, decision-entry, handoff and change-plan templates.

## The shape: plan, review, execute - recursively, at every level of detail

The whole refactor runs one loop at four levels of detail. At each level you **plan** at that
grain, **review** the plan against the code and get it approved, and only then **execute** -
where "execute" at every level but the last means *descend and run the same loop one level down*,
at the moment that piece of work comes up:

```
Plan      the refactor: diagnosis, decisions, ordered steps      -> review -> approve
  Step      when it comes up: re-derive premise, scope, order      -> review -> approve
    Sub-step  when it comes up: mechanism, callers, gates, tests   -> review -> approve
      Commit series: each commit's change, simulated metric,
                     tests, manual check                         -> review -> approve -> execute
```

So nothing moves until it has been reviewed at least three times at increasing resolution, each
review asking the question that only that level can answer. Two rules make the recursion work:

- **Detail just in time.** Plan the next level down only when its work comes up. Detail written
  weeks ahead decays before it is used (P1); a coarse plan kept coarse cannot.
- **Findings flow upward.** A review at a lower level can void the level above - a sub-step whose
  premise fails, a step that dissolves into another. Rewrite the parent plan and re-approve it;
  never quietly work around it below.

The level-by-level questions, the approval artefact at each level, and the cases are in
[planning.md](reference/planning.md) under "The recursive plan-review-execute loop".

## The procedure

Copy this checklist into the plan document and keep it current:

```
Refactor progress:
- [ ] 0. Frame: root cause measured, decisions settled, owners asked, approval obtained
- [ ] 1. Re-verify the plan against the code (and again before every step)
- [ ] 2. Baseline with committed instruments; prep release of defects in code that will move
- [ ] 3. Safety net built, audited, and armed (GATE - nothing moves before this)
- [ ] 4. Execute step by step: plan series -> simulate -> approve -> commit -> verify
- [ ] 5. Verify beyond the suite at every step that moves application code
- [ ] 6. Exit review: plan against reality, before/after on every metric
- [ ] 7. Post-refactor cleanup, burn-in, then release
```

### 0 · Frame the refactor

- **Find the one root cause under the queue.** Measure it (lines and methods per layer, call
  direction counts such as `self.view.*` vs `self.model.*`, where cross-component calls
  originate). A refactor justified by "improved maintainability" has no finish line; one
  justified by "the Model layer is 2.6% of the tab code and 75 of 77 cross-plugin calls
  originate in widgets" does.
- **Settle design decisions before implementation**, as lettered, dated records (context,
  decision, evidence, what would reopen it). An either/or left open inside a late step is a
  decision waiting to be forced by circumstance - pull it forward.
- **Ask whether compatibility obligations are real.** A barely-used persisted format that
  nobody relies on may be broken deliberately if that frees the design; say so explicitly.
- **Open ownership conversations now**, each with measurements attached and a stated exit if
  the owner does not engage. A critical path ending in "blocked on a person" with no exit is
  how a gate sits idle. See [collaboration-and-records.md](reference/collaboration-and-records.md).
- **Get the plan approved before any logic change.** Present blast radius, not just the diff.
- **Publish the plan** in the repository and, where the tooling allows, as a shareable page
  kept in sync with it (`templates/plan.md`).

### 1 · Re-verify the plan against the code

Re-measure every claim immediately before working the step it belongs to, not when the plan
is written. On the source refactor, passes moved 9, 5, 9-of-13 and 3 claims - most of one pass
was not code drift at all, just figures measured wrong the first time. Checks that pay every
time ([planning.md](reference/planning.md) has the evidence):

- Grep the plan for its own repeated figures. Two sections that disagree mean neither was checked.
- For each move: count the call sites and check the destination is reachable from them.
  "It already lives on the base" answers where code is defined, not who calls it.
- For each step: which other step already rewrites the same callers? The cheap one rides the
  expensive one.
- For each category-plus-verb bullet ("omit privates", "delete dead code"): sample what the
  category actually contains before executing the verb.
- For each recorded blocker or "X is impossible": re-derive it. Unexamined blocks stop work.
- Ask what the step counts as success and whether the recorded metric moves when that
  happens. Right numbers can describe the wrong problem.

### 2 · Baseline, and a prep release

- **Commit the instruments that take the baseline.** An uncommitted one-off script produces a
  figure nobody can re-derive, and a baseline is only a baseline if its instrument survives.
- **Ship a prep release first** containing: defects in code the refactor will move (so goldens
  pin correct behaviour, not bugs), zero-risk deletions, and CI/tooling fixes. Seed or remove
  nondeterminism before goldens exist. **Defer pure-duplication findings into the refactor -
  do not fix twice.**
- **Re-baseline after the prep release lands**, or the ratchet credits prep work to the refactor.
- Record the baseline commit, date and command beside every figure.

### 3 · The safety net (a hard gate)

Build it before anything moves; see [safety-net.md](reference/safety-net.md) and
[instruments.md](reference/instruments.md). Typical components:

1. **Harness prerequisites** - test dependencies declared in *every* source each CI workflow
   installs from, markers registered, imports independent of collection order.
2. **Structural ratchets** - duplication (exact-match, both directions), layer-boundary
   allowlist keyed by file and symbol (not line), complexity where it is the right measure.
   Implemented as tests so every CI path enforces them.
3. **Characterization tests and goldens** over the behaviour that moves and has no assertion
   today - executed-but-unasserted lines count as unpinned.
4. **A refactor-coverage audit**: every method the refactor moves or deduplicates is pinned by
   a behavioural test - target list *derived* from the move and dedup lists, never curated.
5. **Outcome-level flows** through the application's public entry points, asserting on
   artefacts (files, rows, exports), so they survive the refactor by construction.
6. **An exit review of the net itself**, and a test that fails loudly if the net is not armed.

Every pin is proven to discriminate by mutation (the general skill's `scripts/mutation_probe.py`).

### 4 · Execute, step by step

Order: **moves before protocol changes; leaves before roots; the smallest self-contained unit
as the pilot; one unit at a time, never big-bang.** The dependency graph picks the order - a
promoted method may only call what is already on the base, so the largest win often lands last.

For every step, run this inner loop - the step and sub-step levels of the recursion. For a
large step, run the first three lines once for the step, split it into sub-steps, and run the
whole loop again for each sub-step as it comes up:

```
Step loop:
- [ ] Re-measure the step's premise and figures at HEAD (suite + every gate green first)
- [ ] Review the step plan at this resolution; if it voids the parent plan, rewrite that first
- [ ] Split into sub-steps if large; each gets this loop when it comes up, not before
- [ ] Map where a regression would surface in the running app (general skill: templates/manual-pass-map.md)
- [ ] Plan a commit series; simulate each commit's metric against modified text in memory
- [ ] Present the series for approval; record it in the plan before executing
- [ ] Per commit: change -> update baselines that must move -> full suite -> read summary line
- [ ] New runtime mechanism? Tests first, seen red, then green; assert the invariant
- [ ] After each move: grep tests for every name the moved body referenced (patch targets)
- [ ] Manual pass at each commit boundary that moves application code; record it dated
- [ ] Close findings in the same piece of work; record the wrong turns as method notes
- [ ] Update plan, live gate table, handoff "resume here"; finish the branch
```

The execution hazards - diffing "identical" copies, inert mechanisms, shared state, converting
calls into requests, deletion mechanics - are in [execution.md](reference/execution.md).

### 5 · Verify beyond the suite

The routine and its lessons (V1-V15) are in the general skill: full suite in natural order, read
this run's summary line and sentinel (its `scripts/run_logged.py`), attribute defects to a
revision, bisect instead of arguing. The refactor-specific emphasis: **launch the application at
every commit boundary that moves application code.** In the source refactor 4,287 tests, eight
hooks, a complexity ratchet and a coverage audit were green over an app that could not start; one
launch caught it. See [verification.md](reference/verification.md).

### 6 · Exit review

Walk the plan against what landed - every step, every "done", every gate row - with read-only
reviewers on disjoint slices and a hand re-check of every finding that carries weight. Verify
"landed" by behaviour, not by a grep hit or a signature that predates the plan. Re-measure every
baseline metric at both ends with one committed instrument, and report: before/after, targets
met / missed / ruled the wrong instrument, starting figures that do not reproduce, and what was
deferred (`templates/exit-review.md`). **A review that only files findings has not finished** -
close them; closing them is how you find out whether you understood them.

### 7 · Post-refactor cleanup and burn-in

The ordered procedure is in [exit-and-cleanup.md](reference/exit-and-cleanup.md): plan against
reality, code against docs, dead production code, dead test code, orphaned assets, plan citations
out of prose, retire refactor-only tooling, suite-time check, exit review, changelog regroup
(last), record it. Then let the result burn in with real users before cutting the release;
defects returning from burn-in are the point of the exercise, not its failure. Before the cut, install
the real built artefact in a clean environment, build what depends on you, keep externally observable
names (loggers, metrics, CLI flags, config keys) stable or call them out as breaking, remove the
refactor's temporary shims, and list mechanical mass-change commits in `.git-blame-ignore-revs`.

## Standing rules

The general skill's standing rules apply in every phase: re-derive inherited claims; green means
you read this run's summary line; never reshape production code to keep a test passing, and stub
collaborators as they really behave; the smallest fix, closed where it was found; code never cites
the plan; approved plans for logic changes; tests for a mechanism you add are yours; fix contracts
at the call sites; replace documentation for a removed mechanism; one branch per piece of work;
separate environment artefacts from measurements. A refactor adds:

- **Nothing moves before the safety net is built, audited and armed** - scoped by the move and
  dedup lists, not by what looks under-tested (N1).
- **Move verbatim, then change, in separate commits**, so a reviewer, a golden and a bisect can each
  tell which one changed the outcome.
- **Every commit banks a measured win and runs green**, simulated before the branch is cut (I4).
- **Defer pure duplication into the refactor** rather than fixing it twice in a prep release.
- **A conversion owes tests to its destination** - a stubbed new method is covered by nothing (N6).

## Red flags - stop and check

The general red flags (inherited claims, broken tests, mutations, green gates, bisecting, landed
claims, sweeps, splices) are in the general skill. These are specific to moving code:

| You notice | Check | Lesson |
|---|---|---|
| A step looks like "just a move" | Call sites, reachability, who else rewrites them | P5, P6 |
| Two copies are "the same code" | `diff` them; decide which behaviour survives | E1, E2 |
| You just converted callers and stubbed the new method | Does the new method have tests of its own? | N6 |
| You promoted or moved a method | Grep tests for every name its body referenced | E11 |
| A metric did not move for real work | Record why in the commit and plan | I11 |
| A golden regenerated at a new path | Diff against the pre-move golden first | N11 |
| You are about to trim docs to fix a diffstat | Do not; line count is a proxy for code | I11 |
| A move commit also changes the moved code | Split it: verbatim move first, change second | E1, execution sequencing |
| The release candidate was only ever run from a checkout | Install the built artefact in a clean environment | exit-and-cleanup release readiness |

## Scripts

Stdlib-only Python 3.9+. The structural ones parse Python; for other languages, keep the
principle and swap the parser. Run each with `--help` for options.

| Script | Purpose |
|---|---|
| `scripts/measure_duplication.py` | Byte-identical function groups and removable lines per family; exact-match baseline in both directions; `--simulate` modified text |
| `scripts/measure_complexity.py` | McCabe complexity per function with the counting rule stated; exact-match ratchet on functions over a threshold |
| `scripts/api_surface_diff.py` | Breaking-change inventory for public classes between two git refs, flagging classes that are themselves new |
| `scripts/find_stale_names.py` | Names defined at a baseline ref and gone at HEAD that tests still mention - deletion residue |
| `scripts/find_plan_citations.py` | Plan-step citations across every text file type, not just source files |

The general skill's `run_logged.py`, `mutation_probe.py` and `structural_diff.py` complete the set.
Execute these rather than reading them; read one only to adapt it to a new language.
