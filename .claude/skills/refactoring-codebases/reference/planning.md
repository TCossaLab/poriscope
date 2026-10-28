# Planning, and verifying the plan

The question this phase answers: *is this claim still true, is the step doable as written, and
is it the step I think it is?*

## Contents

- The recursive plan-review-execute loop
- Framing procedure
- P5 Count the callers before believing a move is cheap
- P6 Ask which other step already owns those callers
- P10 Before moving state to a layer, check that the layer reads it
- P11 Take a duplication number apart before planning against it
- P12 Before deleting duplication, ask whether another gate is why it exists
- P13 A pending deprecation changes the right answer
- P16 Aim a step at the metric it can actually move

The general planning lessons - P1-P4, P7-P9, P14, P15 and P17-P23, including detail just in time,
findings flowing upward and re-verifying every claim - are in the general skill's
[planning.md](../../planning-and-executing-changes/reference/planning.md). Read that first; this file adds what is specific to a refactor.

## The recursive plan-review-execute loop

Planning is not a phase that ends when the plan is approved. The same three-part loop - **plan**
at some grain, **review** that plan against the code and get it approved, **execute** - runs at
four levels of detail, and "execute" at every level except the last means *descend one level and
run the loop again*, at the moment that piece of work comes up. By the time any code moves, it
has been reviewed at the plan, the step, the sub-step and the commit-series level, each time at a
finer resolution and each time asking a question the coarser review could not.

| Level | Written when | The review asks | Approved artefact |
|---|---|---|---|
| **Plan** | Once, at the start | Is the diagnosis measured and right? Are the design decisions settled, with trade-offs stated? Is the sequence sound (moves before protocol changes, pilot first)? Is every success criterion an instrument + baseline + target? Are owners asked, with exits? | Plan document with lettered decisions, ordered steps, success criteria |
| **Step** | When the step comes up, not before | Does its premise still hold at HEAD (P1)? Is it the step I think - a move, or a protocol change (P5)? Is the metric the right one (P14)? Which other step owns its callers (P6)? What is it worth on each gate, and can the gates see its destination (P16, instruments I9)? Does the category it names contain what it says (P15)? | Step entry rewritten with re-measured figures, its sub-steps, and the manual-pass map |
| **Sub-step** | When the sub-step comes up | The mechanism: are the "identical" copies identical (execution E1)? Is the no-op a no-op (E3)? What state does it write, and who else writes it (E15)? Is anything here a new runtime mechanism that needs tests first (N7, general skill)? Which tests' patch targets will move (E11)? | Sub-step plan: what moves where, what is decided, what tests come first |
| **Commit series** | Before the branch is cut | Does every commit bank a measurable win and leave the full suite green? Has each commit's metric been simulated (I4)? Is the order forced by dependencies, and which gates are expected *not* to move and why? Which tests will break and how will they be rewritten? What is each commit's app risk and manual check? | `templates/commit-series.md`, approved and recorded in the plan before the first commit |
| **Commit** (execute) | One at a time | The per-commit loop: change, baselines that must move, full suite, read the summary line, manual pass if app code moved | The commit, and its gate values recorded in the plan's live table |

Each review is a real review: re-measure at HEAD, present it, wait for approval, record what was
approved - in the repository plan and its shared page - before descending. A step that "looks
mechanical" gets the same treatment; that is where P5 and P14 bite hardest.

**What the recursion bought on the source refactor.** The plan was approved and re-verified at the
start. Then, at each level, review changed the work before anything moved:

- *Step level.* Step 2 (the safety net) was re-verified when it was planned in detail, just before it began;
  three claims moved and two changed what the work was: the duplication baseline turned out to be unreproducible,
  so building the instrument became the job, and the golden targets were the wrong methods. Step 5
  was re-derived on the day it started and most of its entry did not survive; its sub-steps were
  agreed only then. Step 7 was mapped into commits against a re-measure because two of its four
  bullets had moved.
- *Sub-step level.* One sub-step was taken apart on the morning it was to be worked and stopped
  being a step at all: its "pure" helper was not pure, and 7 of its 8 callers belonged to a later
  step, so it was folded into that step. Another sub-step's four figures were all exact and its
  conclusions wrong, so it was re-scoped from line counts to cyclomatic complexity, with the
  instrument built first. A third, recorded as "blocked" on a later step, was re-derived and turned
  out to be the one that should go first.
- *Commit-series level.* A five-commit promotion series was simulated before the branch was cut -
  every figure in the table was written in advance and every one matched when the commits landed.
  A later branch's series narrowed its own scope mid-review when two methods turned out to share
  state and had to convert together.

None of these was visible from the level above. Each was cheap to find at its own level and would
have been expensive to find in a diff.

## Framing procedure

These are the plan-level contents - the top of the recursion.

1. **Diagnose one root cause.** Most of a long refactor queue usually traces to one structural
   fact (a layer that never got real code, a dispatcher everything routes through, a base class
   that absorbed everything). Measure it in numbers a reader can re-derive: lines and methods
   per layer, call-direction counts, where cross-component calls originate, duplicated lines per
   family of sibling files.
2. **Trace one representative path end to end** and count the hops. "Eight hops and three
   string lookups to move one integer" makes the design argument better than any adjective, and
   usually exposes a live bug on the way (a result parked on an attribute that is never reset,
   so a failed call reads the *previous* call's answer).
3. **Write the decisions down before the steps** - lettered, dated, each with context, decision,
   evidence, and what would reopen it. Include what is deliberately *kept* (e.g. "fire-and-forget
   notifications stay as signals; only the return-value RPC is replaced") and the accepted
   trade-offs ("the call returns `Any`, so the type checker cannot catch a renamed method -
   accepted to keep the extension API string-keyed").
4. **Tier the preparatory work.** Tier A: defects in code the refactor will move - fix before
   goldens are captured, so the goldens pin correct behaviour. Tier B: domain defects that ship
   inside the refactor. Tier C: CI and tooling. Defer pure duplication into the refactor - do not
   fix twice.
5. **Sequence** so moves precede protocol changes, the pilot is the smallest self-contained
   unit, and each unit finishes before the next begins. Record the reason for each ordering;
   reorderings should be dated notes, not silent edits.
6. **Define success criteria as instrument + baseline + target**, one row per metric. A target no
   instrument can measure (e.g. "remove 2,500 duplicated lines" when the instrument sees only
   byte-identical bodies) will be missed for a reason that has nothing to do with the work.

## P5 · Count the callers before believing a move is cheap

What decides whether a move is mechanical is who calls it, not where it is defined. Count the
call sites and check the destination is reachable from them synchronously. A layer boundary the
callers cannot cross turns a move into a protocol change.

*Case:* a step was classified as a simple promotion because both helpers "already live on the
base class". All fifteen call sites were synchronous inline uses in Views, and no View could reach
the Model synchronously at all. Five minutes of counting reclassified it.

## P6 · Ask which other step already owns those callers

Plan steps partition the work by concern while sharing callers. Two steps that touch one method
are one step in disguise; the cheap one should ride the expensive one rather than precede it, so
every caller is rewritten once.

*Case:* a step with 8 call sites had 7 of them already listed as targets of a later step - an
answer the repository held in one table. Running it first would have restructured seven callers
twice, five of them inside a 327-line orchestrator with five nested loops.

## P10 · Before moving state to a layer, check that the layer reads it

The question that decides a relocation is who reads the value, not what it is called. Grep the
destination layer for the name; if the answer is zero, the state is not misplaced - the label is.

*Case:* a map of user-named filter clauses "was domain state" by every description. No Model read
it, and moving it would have converted 16 synchronous reads into round trips. The real defect was
smaller and elsewhere: a Controller mutating the View's dict directly at four sites.

## P11 · Take a duplication number apart before planning against it

Classify duplicated lines into boilerplate a contract forces, declarations that are per-instance by
nature, and genuinely shared logic. Only the third is deduplication, and the first is usually the
largest.

*Case:* a step priced at ~1,000 duplicated lines was 280 lines of `pass`-only implementations of
abstract hooks - removing them is a decision about the contract, not a refactor - and the owner
chose to keep them.

## P12 · Before deleting duplication, ask whether another gate is why it exists

A project with several gates can have one gate's target held in place by another's rule. Check
what every other gate and policy says about the thing, in the same pass that measures it.

*Case:* 22 byte-identical docstrings (31,711 characters) looked like the cheapest win on the board.
A compliance test requires every method defined on a plugin subclass to carry its own docstring,
so the copies were enforced policy, not oversight.

## P13 · A pending deprecation changes the right answer to a duplication finding

A duplication measurement is a fact about today; a refactoring decision is a bet on tomorrow.
Before deduplicating a near-identical pair, ask whether either copy is on its way out. If it has
to move sooner, let the survivor absorb what it needs and stand alone, leaving a clean deletion.

*Case:* two readers differing in 27 of ~396 lines were the largest duplication contributor. The
obvious fix, subclassing, would have made the survivor inherit from the one scheduled for deletion.

## P16 · Aim a step at the metric it can actually move, and check that first

Before starting, compute what the step is worth on each gate. The same step on a different unit can
be worth 3 points or 0; a five-minute count says which.

*Case:* removing forbidden imports from one View dropped three (each had one user); on another,
one import had eight users and stayed. Knowing that in advance set the order.

