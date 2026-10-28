# <Project> <version> refactor plan

> Shared page: <link>. The repository file is authoritative where the two disagree.
> Delete this file when the release ships - nothing that ships may cite it.

## Resume here  <!-- rewrite at every stopping point -->

- Branch / commit: `<branch>` at `<sha>` (<date>)
- Last landed: <what>, suite <N passed / M skipped>, gates: <values>
- Next action: <the exact next thing to do>
- Owed: <manual passes, reviews, re-measures not yet done>
- In flight, do not lose: <anything uncommitted or half-decided>

## Live gate table  <!-- update in every commit that moves a gate -->

| Gate | Instrument | Start (`<sha>`) | Now | Target | Floor + reason / blind spots |
|---|---|---|---|---|---|
| Duplication, removable lines | `scripts/measure_duplication.py` | | | | |
| Boundary allowlist | `<test>` | | | 0 | |
| Complexity, functions over N | `scripts/measure_complexity.py` | | | | |
| Refactor-coverage audit | `<test>` | | | 100% pinned (invariant, not a count) | refactor-only: retire at exit |
| Suite | full run | | | - | |

## Why - the diagnosis

<One root cause, measured. Lines/methods per layer, call-direction counts, one path traced hop by hop.>

## Decisions  <!-- settled before implementation; amend with date and who ruled -->

### A · <title> (<date>)
- Context:
- Decision:
- Evidence:
- Accepted trade:
- Revisit if:

## Sequencing

<Steps in order with the reason for each ordering. Moves before protocol changes; pilot first.>
<Reorderings as dated notes, never silent edits.>

## Success criteria

| Metric | Baseline (`<sha>`) | Target | Instrument |
|---|---|---|---|

## Step 0 - baseline (<status, date>)
## Step 1 - prep release: Tier A (defects in code that moves) / B (deferred) / C (tooling)
## Step 2 - safety net (GATE)
## Step 3..n - <steps>

Per step - written when the step comes up, not before (plan -> review -> approve at each level):
- Step review (<date>, `<sha>`): premise re-measured, what moved, scope/order changes; approved by <who>.
  If it voided anything above, the parent change and its re-approval are recorded here first.
- Sub-steps: each gets its own review record when it comes up (mechanism, callers, state, tests first).
- Commit series (templates/commit-series.md): simulated metric per commit; approved by <who> on <date>.
- Per commit: gate values, manual pass record (dated). Findings closed; wrong turns -> method notes.

## Re-verification log

| Pass | Commit | Claims checked | Moved | Notable |
|---|---|---|---|---|

## Owners and asks

<Who owns what; the ask as sent, with numbers; the answer and date; the stated exit if no answer.>

## Method notes  <!-- the lessons, each with the case that produced it; keep the wrong turns -->

1. **<rule>** - <case>.

## Exit review and cleanup

<Procedure checklist and findings; before/after table.>
