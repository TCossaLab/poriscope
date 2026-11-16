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
This skill adds what is specific to a refactor. Lesson IDs are unique across the sibling skills; an
ID cited here that is not in this skill's reference files is in the general one, whose
lesson-index lists it.

## The stance

The general stance applies. A refactor adds two:

1. **Pin what moves before moving it**, scoped by what the refactor touches, not by what looks
   under-tested.
2. **Build instruments that fail in both directions**, so every commit must bank its own win
   and none can quietly borrow one.

## Reference files - read the one for the phase you are in

| File | Read when |
|---|---|
| [reference/planning.md](reference/planning.md) | Writing or re-verifying a refactor plan; sizing or sequencing a step; a step "looks cheap" |
| [reference/safety-net.md](reference/safety-net.md) | Deciding what to pin before a move; building characterization tests, goldens, equivalence tables, flows |
| [reference/instruments.md](reference/instruments.md) | Building or reading a ratchet, allowlist, coverage audit or any progress metric |
| [reference/execution.md](reference/execution.md) | Moving, promoting, deduplicating, converting calls, deleting code, editing tests after a move |
| [reference/exit-and-cleanup.md](reference/exit-and-cleanup.md) | The last structural change has landed: exit review, cleanup procedure, release readiness |
| [reference/lesson-index.md](reference/lesson-index.md) | Looking up a lesson by ID or by symptom (grep it) |

Templates live in `templates/`; deterministic helpers in `scripts/` (see the end of this file).
The general skill holds the manual-pass map, decision-entry, handoff and change-plan templates.

## The shape: plan, review, execute - recursively, at every level of detail

The general skill's plan-review-execute loop (P20-P23) runs at four levels in a refactor:

```
Plan      the refactor: diagnosis, decisions, ordered steps      -> review -> approve
  Step      when it comes up: re-derive premise, scope, order      -> review -> approve
    Sub-step  when it comes up: mechanism, callers, gates, tests   -> review -> approve
      Commit series: each commit's change, simulated metric,
                     tests, manual check                         -> review -> approve -> execute
```

Each level is planned, reviewed and approved when its work comes up, never before (P20), and a
lower-level finding that voids the level above sends you back up (P21). The per-level questions,
artefacts and cases are in [planning.md](reference/planning.md), "The recursive plan-review-execute
loop".

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
  how a gate sits idle (C2).
- **Get the plan approved before any logic change.** Present blast radius, not just the diff.
- **Publish the plan** in the repository and, where the tooling allows, as a shareable page
  kept in sync with it (`templates/plan.md`).

### 1 · Re-verify the plan against the code

Re-measure every claim immediately before working the step it belongs to (P1). Checks that pay
every time:

- Grep the plan for its own repeated figures (P2).
- For each move: count the call sites and check the destination is reachable from them (P5).
- For each step: which other step already rewrites the same callers (P6)?
- For each category-plus-verb bullet: sample what the category contains first (P15).
- For each recorded blocker or "X is impossible": re-derive it (P4, P8).
- Does the recorded metric move when the step succeeds (P14, P16)?

### 2 · Baseline, and a prep release

- **Commit the instruments that take the baseline.** An uncommitted one-off script produces a
  figure nobody can re-derive, and a baseline is only a baseline if its instrument survives.
- **Ship a prep release first** containing: defects in code the refactor will move (so goldens
  pin correct behaviour, not bugs), zero-risk deletions, and CI/tooling fixes. Seed or remove
  nondeterminism before goldens exist.
- **Re-baseline after the prep release lands**, or the ratchet credits prep work to the refactor.
- Record the baseline commit, date and command beside every figure.

### 3 · The safety net (a hard gate)

Build it before anything moves, in the order of [safety-net.md](reference/safety-net.md)'s build
procedure: harness, structural ratchets ([instruments.md](reference/instruments.md)),
characterization tests and goldens, a refactor-coverage audit derived from the move and dedup lists
(N1), outcome flows, and a review of the net with a test that fails if it is not armed (N14). Every
pin is proven to discriminate by mutation (N4).

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

The general routine applies. A refactor adds: **launch the application at every commit boundary
that moves application code** (V3), mapping each branch's manual pass from the call sites of what
moves; and run **one full-scope manual pass before the first structural change and one at exit** -
the first makes a later failure attributable, and without the last nothing checks the finished whole.

### 6 · Exit review

Walk the plan against what landed and re-measure every baseline metric at both ends with one
committed instrument ([exit-and-cleanup.md](reference/exit-and-cleanup.md), `templates/exit-review.md`);
verify "landed" by behaviour (V12), and close what the review finds (X1).

### 7 · Post-refactor cleanup and burn-in

Run the ordered cleanup procedure in [exit-and-cleanup.md](reference/exit-and-cleanup.md), then let
the result burn in with real users before cutting the release, and work through its release-readiness
list (install the built artefact cleanly, build dependants, stable external names, shims removed).

## Standing rules

The general skill's standing rules apply in every phase. A refactor adds:

- **Nothing moves before the safety net is built, audited and armed** - scoped by the move and
  dedup lists, not by what looks under-tested (N1).
- **Move verbatim, then change, in separate commits**, so a reviewer, a golden and a bisect can each
  tell which one changed the outcome.
- **Every commit banks a measured win and runs green**, simulated before the branch is cut (I4).
- **Defer pure duplication into the refactor** rather than fixing it twice in a prep release.

## Red flags - stop and check

The general red flags (inherited claims, broken tests, mutations, green gates, bisecting, landed
claims, sweeps, splices) are in the general skill. These are specific to moving code:

| You notice | Check | Lesson |
|---|---|---|
| A step looks like "just a move" | Call sites, reachability, who else rewrites them | P5, P6 |
| Two copies are "the same code" | `diff` them; decide which behaviour survives | E1, E2 |
| You just converted callers and stubbed the new method | Does the new method have tests of its own? | N6 |
| You promoted or moved a method | Grep tests for every name its body referenced | E11 |
| A metric did not move for real work, or you are about to trim docs to fix a diffstat | Record why in the commit and plan; line count is a proxy for code | I11 |
| A golden regenerated at a new path | Diff against the pre-move golden first | N11 |
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
