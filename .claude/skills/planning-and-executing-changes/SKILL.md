---
name: planning-and-executing-changes
description: The default method for planning, executing and verifying any non-trivial software change - a bug fix, feature, review, investigation, migration or release step - from the first design discussion on, even before any plan or code is wanted. Restates a rough request and confirms use cases before planning, re-derives inherited claims, gets approval before logic changes, writes tests that can fail, verifies beyond the suite, and closes findings rather than filing them; nearly a hundred field-tested lessons on how plans, handoffs, tests, gates and green CI mislead. Use whenever you are about to discuss a design or a rough feature request, write or check a plan, accept a claim from a handoff, subagent, comment or earlier session, fix a reported defect, write or edit tests, interpret a test or gate run, decide that something is done or has landed, or write a handoff - even for a one-site fix. For a refactor, also load refactoring-codebases, which builds on this one.
---

# Planning and executing changes

Most failures in software work are not failures to write the code. They are failures to notice
that a claim was stale, that a test could not fail, that a gate was blind, or that "done" was a
text match. This skill is the method for noticing, and the catalogue of the ways each of those
misleads.

It was distilled from a three-week, nine-step refactor of a desktop application with a plugin
system (about 2,900 tests growing to 4,200), whose plan was re-verified ten times and moved claims
every time. Most of what that work taught applies to any change, so it lives here; what is specific
to refactoring lives in the `refactoring-codebases` skill, which builds on this one. Every lesson
carries the case that produced it. The cases are illustrations; the rules are language- and
framework-neutral.

## The stance, in six sentences

1. **Every claim is a measurement with a date on it** - a plan's numbers, a handoff note, a
   subagent's report, a code comment, a user's diagnosis, your own reasoning from an hour ago.
   Re-derive before building on it.
2. **Check the mechanism, not its name or its comment** - decorators, guards, "pure" helpers,
   "no-op" calls and recorded blockers are claims until run.
3. **A test is evidence only if it can fail** when the behaviour it names breaks, exercising
   collaborators the way they really behave.
4. **Every gate is blind somewhere.** A green board is evidence about what the gates measure,
   never about whether the program works. Launch it.
5. **Make the smallest change that fixes the defect, and close what you find** in the piece of work
   where you found it.
6. **Write state down so an interruption costs nothing**, and record the wrong turns - a record of
   only the final state teaches nothing.

## Reference files - read the one for what you are doing

| File | Read when |
|---|---|
| [reference/discovery.md](reference/discovery.md) | Turning a rough request or note into something plannable; a design discussion; writing use cases; "exploratory design" |
| [reference/planning.md](reference/planning.md) | Writing, reviewing or re-verifying a plan; sizing work; a step "looks cheap"; a claim or blocker you inherited |
| [reference/testing.md](reference/testing.md) | Writing or editing tests, stubs, fixtures, goldens, waits; a correct change broke a test |
| [reference/measurement.md](reference/measurement.md) | Building or reading a gate, ratchet, allowlist or any progress metric |
| [reference/execution.md](reference/execution.md) | Editing code whose mechanism you have not measured; deleting or splicing code; sizing a fix |
| [reference/verification.md](reference/verification.md) | Running suites, manual passes, probes; triaging a reported defect; deciding something "landed" |
| [reference/finishing.md](reference/finishing.md) | Deciding a piece of work is done; closing a review; a flake |
| [reference/collaboration-and-records.md](reference/collaboration-and-records.md) | Approvals, owners, branches, plan documents, handoffs, changelog, decision log, docs, delegated work |
| [reference/lesson-index.md](reference/lesson-index.md) | Looking up a lesson by ID or by symptom (grep it) |

Templates live in `templates/`; deterministic helpers in `scripts/` (see the end of this file).

## The procedure

For any change beyond a typo, copy this checklist into your working notes and keep it current:

```
Change progress:
- [ ] 0. Discover (features and rough requests): restate the note and confirm it; use cases confirmed; only then ways to build it, as rulings (reference/discovery.md)
- [ ] 1. Understand: reproduce or measure the problem at HEAD; re-derive every inherited claim
- [ ] 2. Plan at the level the work needs; get approval before any logic change
- [ ] 3. Tests: new mechanism or diagnosed regression -> test first, seen red
- [ ] 4. Execute: smallest change that fixes it; structural check on any deletion or splice
- [ ] 5. Verify: full suite, read the summary line; every gate's verdict; launch the program
- [ ] 6. Finish: close findings, update the records, report faithfully
```

### 1 · Understand before changing anything

- **Reproduce the defect, or measure the claim, at HEAD.** A reported cause is a hypothesis, the
  user's included: probe it before designing the fix (P9). "Silently mangled" and "rejected" are
  different bugs.
- **Establish reachability** before reasoning about behaviour: write the input that would trigger
  it and see whether the code accepts it (V8).
- **Attribute a regression to a revision** by reproducing on the parent, not by reading the diff
  you just made (V7); bisect when the cause is somewhere in a set (V14).
- **Re-derive inherited work** - handoffs, plans, subagent reports, comments, recorded blockers
  (P1, P4, C10). Good news gets checked least (V12).

### 2 · Plan at the level the work needs

The loop is **plan -> review -> approve -> execute**, recursively: a one-site fix has one level; a
feature has a plan, per-part plans when each part comes up, and a commit series; a multi-week effort
has more ([planning.md](reference/planning.md)). Detail is written just in time (P20); a finding at a
lower level that voids the level above sends you back up (P21); approval at one level is not
approval of the level below (P22). Lead each plan with a one-screen summary a reviewer can rule on
(P23). Use `templates/change-plan.md` for a logic change.

Before approving your own plan, ask the checks that pay every time: does the plan disagree with
itself (P2)? does the category a bullet names contain what it says (P15)? does the success measure
move when the work succeeds (P14)? which open design question should be settled now (P19)?

### 3 · Tests that tell you something

- **A new runtime mechanism is written test-first**, against its invariant, seen red on the
  unmodified code and then green (N7). A regression the suite missed gets a test as soon as it is
  diagnosed.
- **Stub collaborators the way they really behave** - side effects, real signature, declared
  return type (N5). A conversion owes tests to its destination (N6).
- **A correct change that breaks a test is information**: rewrite the test; never reshape the code
  to keep it green (N15).
- **Prove a pin discriminates** by mutating what it claims to cover, and confirm the mutation
  happened (N4). Waits are satisfied only by this run's finished state (N8).

### 4 · Execute

- **The smallest change that fixes the defect**, with no machinery around it; if it grows past the
  size of the bug, stop and ask (E24). Fix the contract at the call sites rather than guessing at
  runtime (E25).
- **Measure a mechanism before relying on it** - that a "no-op" is one, that a decorator fires, that
  an effect has the sign you want (E3, E4, E5).
- **Deletions and splices get a structural before/after check** (E21, E22,
  `scripts/structural_diff.py`), and auto-fixers run before you inspect, never between (E23).

### 5 · Verify beyond the suite

Full suite, natural order, before every commit (V1). Green means you read *this run's* summary line
and sentinel (V2, `scripts/run_logged.py`). Read every gate's verdict, not a tail. When application
code changed, **launch it** and walk the manual-pass map (V3, V4, `templates/manual-pass-map.md`);
assert on the surface the user reads (V5) and, for persisted state, on the file (V6). Keep probes out
of the user's real data (V10). The routine is in [verification.md](reference/verification.md).

### 6 · Finish

A review that only files findings has not finished (X1); a sweep is finished only where its
instrument looked (X2); a flake is fixed, not re-run (X8). Update the changelog, the work queue and the
decision log, each with only its kind of information (C6); write the handoff (C5,
`templates/handoff.md`); finish the branch (C3); and report the outcome faithfully, including any
damage (C12). [finishing.md](reference/finishing.md) has the checklist.

## Standing rules

These apply to every task. **The first five hold in every session** and are the ones worth copying
into a repository's always-loaded instructions (CLAUDE.md or equivalent); keep them here too, since
that file does not travel between repositories.

1. **Re-derive every inherited claim before building on it** - plan figures, handoff notes, subagent
   reports, comments, a user's diagnosis, your own earlier reasoning. None of it is evidence until
   re-measured (P1).
2. **Green means you read this run's summary line** - not an exit code, a progress line or a `tail` -
   and every gate is blind somewhere, so launch the program when its code changed (V2, V3).
3. **Never reshape production code to keep a test passing.** Edit the test, and stub collaborators the
   way they really behave (N15, N5).
4. **Make the smallest change that fixes the defect, and close findings where they surface** rather
   than filing them; deferral is a recorded exception with a reason (E24, X1).
5. **Code, comments and tests never cite a plan document** that will be deleted; describe the
   mechanism and the reason, naming the old mechanism where that helps findability.

Also standing, with evidence in the reference files:

- **Logic changes need an approved plan**; read-only investigation does not (C1). Design discussion is
  not "read-only investigation": it decides what the plan will be, so discovery applies (D1-D3).
- **Tests for a mechanism you add are yours** (N6, N7).
- **Prefer fixing the contract at the call sites over runtime guessing** and fallback chains (E25).
- **Replace documentation for a removed mechanism; do not delete it** (C8).
- **One branch per piece of work**, finished before the next starts (C3).
- **Separate environment artefacts from measurements** and report which is which (V13).
- **Put each kind of information in exactly one place**, tersely (C6).

## Red flags - stop and check

| You notice | Check | Lesson |
|---|---|---|
| Your summary of a request uses different words from the request | Restate it literally and ask which reading is meant | D1 |
| You are designing in an area the decision log or work queue may already cover | Grep both for the topic first | D2 |
| You are about to answer a question the user's request asked | Is it theirs to decide? List it as a ruling | D3 |
| You are about to hand over a design, use case, plan or mock-up | Audit it: every element cites a source; anything resting on an open ruling is conditional; anything unsourced is removed or raised as a ruling | D3 |
| A design document describes the current code | Label each claim today or planned; give `file:line` for today | D4 |
| A design or use case says "every tab", "all plugins" or "per tab" | Build the per-member table first: what each member has today | P15 |
| You are writing use cases from your own plan | Write them from the request instead, and check the plan against them | D8 |
| You are about to build on a figure, note or report you did not produce today | Re-derive it | P1 |
| A comment, docstring or decision says something can't be done | Re-derive it | P4 |
| The user or a report names the cause of a defect | Probe it before designing the fix | P9 |
| A suspicious code shape looks like a bug | Write the input that reaches it | V8 |
| You add or fix a guard, or reason about a value used in several places | Map each entry point's pipeline, input to outcome; compare step by step | E29 |
| A reported regression in code you just changed | Reproduce on the parent revision | V7 |
| You are about to reason about which commit or test caused a failure | Bisect it instead | V14 |
| You are adding wiring that did not exist before | Tests first, seen red; assert the invariant | N7 |
| A correct change broke a test | Rewrite the test; never reshape the code for it | N15 |
| You stubbed a collaborator with a bare mock | Does it behave like the real one? | N5 |
| A test passed after a mutation | Confirm the mutation happened | N4 |
| You are deleting one statement inside a block, or splicing between anchors | Structural before/after check | E21, E22 |
| The fix is growing well past the size of the bug | Stop and ask | E24 |
| A metric moved the way you wanted | Prove it was earned | I12 |
| A background run "exited 0" | Read the summary line and the sentinel | V2 |
| Every gate is green after changing app code | Launch the app | V3 |
| A probe will construct the real app | Redirect its user-data paths first | V10 |
| You are about to record something as landed | Check what it does, and the date of what you found | V12 |
| A sweep reports zero remaining | Does the command cover every artefact type the rule names? | X2 |
| A test failed once and passed on re-run | Find the race | X8 |
| You are about to execute detail approved only at a coarser level | Review and approve it at its own level | P22 |
| A lower-level review contradicts the plan above it | Rewrite and re-approve the parent first | P21 |

## Scripts and templates

Stdlib-only Python 3.9+. Run each with `--help` for options; execute them rather than reading them.

| Script | Purpose |
|---|---|
| `scripts/run_logged.py` | Run a command, keep the full log, append a `REALEXIT=` sentinel, print the real summary and warn on a green summary with a non-zero exit |
| `scripts/mutation_probe.py` | Apply unique-anchor mutations one at a time, run the named tests, restore; reports KILLED / SURVIVED / BOTCHED |
| `scripts/structural_diff.py` | Between two revisions of a file: methods lost/gained per class (`methods`), or proof that only prose changed (`prose`) |

| Template | Use |
|---|---|
| `templates/design-document.md` | The discovery stage's one document: section order, and which step fills each |
| `templates/restatement.md` | Restating a rough note before any design, for the user to confirm (D1) |
| `templates/ruling.md` | One open design choice: summary, options, issues, impact trace, evaluation (D3) |
| `templates/change-plan.md` | A plan for a logic change, per site, for approval |
| `templates/manual-pass-map.md` | Where in the running program each change would show if broken |
| `templates/decision-entry.md` | A decision-log entry: context, decision, evidence, revisit condition |
| `templates/handoff.md` | A "resume here" note at a stopping point |
