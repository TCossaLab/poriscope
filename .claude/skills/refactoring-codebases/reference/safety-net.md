# Building the safety net

The question this phase answers: *what has to be pinned before anything moves, and does the pin
actually hold?* The safety net is a hard gate: nothing structural moves until it is built,
audited and armed.

## Contents

- Build procedure
- N1 Scope the net by what moves, and derive the list
- N13 An expected golden diff needs a stated rule

The general testing lessons - N2-N12, N14 and N15, including stubbing collaborators as they really
behave, test-first mechanisms, mutation-proving pins and never reshaping code to keep a test
passing - are in the general skill's [testing.md](../../planning-and-executing-changes/reference/testing.md). This file adds how to build a
net before a refactor moves anything.

## Build procedure

Build in this order, each piece its own reviewable commit or branch:

1. **Harness.** Declare every test dependency in *every* file each CI workflow installs from
   (different workflows often read different files). Register custom markers if the runner is
   strict. Make test imports independent of collection order (a test file that only imports
   because another directory's conftest happened to load first will fail alone).
2. **Structural instruments** (see instruments.md): duplication ratchet, layer-boundary allowlist,
   complexity ratchet if relevant. Test each instrument against small synthetic source texts, not
   only the real tree.
3. **Characterization tests** over what moves and has no behavioural assertion today. Use golden
   files (array/frame/text regression fixtures) where output is large; literal assertions where it
   is a scalar or short tuple - a golden file for a three-element tuple is less legible than the
   literal. Keep sample sizes small so golden files stay reviewable and under any large-file hook.
   Do not mock the logger - it blinds log-capture assertions.
4. **Exact-text goldens for generated text** (SQL, config, code). Substring-containment tests let a
   refactor reorder joins, rename aliases or change projections unnoticed. Normalise whitespace so
   reformatting the generator does not raise false alarms.
5. **Equivalence tables** for copies about to be merged: assert the copies agree on a shared input
   set, so where they genuinely diverge the merge becomes a recorded decision instead of a silent
   behaviour change.
6. **Refactor-coverage audit**: for every method on the move and dedup lists, require behavioural
   coverage (the body executed under a test *and* a test names it). Derive the dedup half from the
   duplication instrument; write the moved half out from the plan and check it against the plan text.
7. **Outcome flows**: one headless flow per top-level feature, driven through the same entry point
   the UI or API uses, asserting on artefacts (exported CSV, committed rows, written files). If no
   harness rung exists between mock-only unit tests and click-driven end-to-end tests, build it.
8. **Review the net** before starting: is every moving method a target? does every gate cover the
   directories the refactor will touch? is anything curated by testability? Close what the review
   finds before Step 3 starts.

## N1 · Scope the net by what moves, not by what looks thin - and derive the list

The covered set comes from the refactor's own move and deduplication lists, mechanically where
possible. The net's own scope is the thing most likely to be quietly narrowed, because narrowing is
invisible - every remaining target passes. Where a list cannot be derived, check it against the
source text that defines it. "Which of these is easy to test" is a scheduling question, not a
scoping one.

*Case:* a first pass pinned only zero-coverage methods, letting genuinely moved methods through.
Later, the hand-typed half of the target list silently dropped every method entangled with a
plotting surface - four of which the plan named explicitly. An exit review of the net caught it.

## N13 · An expected golden diff needs a stated rule

A refactor that also corrects behaviour must break the tests pinning the old behaviour. State the rule:
a failing characterization test is an expected diff only when the same commit carries the fix, the
rewritten expectation and a dated decision entry naming the behaviour corrected; otherwise it is a
regression. A convention followed perfectly and stated nowhere is still a documentation gap - and the
most misleading one.

