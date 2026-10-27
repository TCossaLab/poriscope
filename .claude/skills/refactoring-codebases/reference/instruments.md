# Instruments, ratchets and gates

The question this phase answers: *how will I know this worked, what is the number blind to, and
can it move for the wrong reason?*

## Contents

- Design rules for a refactor instrument
- I4 Make instruments take text, and simulate before choosing commit boundaries
- I7 A derived gate has no baseline - record the invariant, and zero is success
- I8 An instrument that names what you moved needs the same edit in the same commit
- I9 Check whether the instrument can still see the code you are about to move
- I17 Separate refactor-only gates from result gates at build time

The general measurement lessons - I1-I3, I5, I6 and I10-I16, including exact-match ratchets,
writing down each instrument's blind spots and not letting a gate force the code to lie - are in
the general skill's [measurement.md](../../planning-and-executing-changes/reference/measurement.md). This file adds the instruments a
refactor needs while code is moving.

## Design rules for a refactor instrument

- **Implement gates as tests** (with measurement logic in a runnable script) rather than only as
  pre-commit hooks: a test is enforced on every CI path with no extra wiring, and the script answers
  "what do I actually have to fix?" on its own.
- **Key allowlists by file and symbol, never line number**, so ordinary edits do not churn them.
- **Enumerate the files in a family explicitly.** A case-sensitive glob `*controls.py` silently
  dropped `eventAnalysisControls.py` - 17% of the family, 742 lines.
- **Put the counting rule in the instrument's docstring**, including edge cases (does a typing-only
  import count? does `with` count as a branch? do docstrings count as body?).
- **Test the instrument** against small synthetic sources that exercise each rule and edge case.
- **Choose instruments that measure the problem the step exists to solve** (P14, general skill): line counts
  for duplication, complexity for tangled control flow, boundary crossings for layering.
- **Keep a "live table"** of every gate in the plan: start, now, target, and the reason for any floor.
- **Commit a gate only for drift that is continuous.** A question asked once per release - does the ABC
  surface differ from the last tag? - is answered by a throwaway script; committed, it becomes a gate nobody
  agreed to.

## I4 · Make instruments take text, and simulate before choosing commit boundaries

An instrument whose core function takes source text rather than paths can measure a proposed change held
in memory. Run each planned commit through it before writing code: "roughly 489 lines in four commits"
became four checkable numbers, and every one matched when the commits landed.
(`measure_duplication.py --simulate path=modified_file`.)

## I7 · A derived gate has no baseline - record the invariant, and zero is success

A gate whose target list is computed live (e.g. from another instrument) drifts silently when its source
changes. Write the invariant into the plan ("100% pinned"), never the value ("298 of 298") - the value
did not survive one legitimate change. A derived count is *supposed* to fall as the work lands. Split
its tests into "the derivation works" (against a fixture that really contains a target, so a detector
that stops matching still fails) and "what it currently finds" (`== []`, with a message saying a new
entry is the regression). Asserting the list is non-empty turns the suite red for success.

## I8 · An instrument that names what you moved needs the same edit in the same commit

Deleting a method the coverage audit listed broke two tests immediately. That is the tripwire working:
a target silently dropping off would shrink the covered set unnoticed. Delete the entry with a comment
saying why, in the same commit; never loosen the existence check.

## I9 · Check whether the instrument can still see the code you are about to move

A gate scoped by file path stops measuring the moment code leaves that path - and fails silently,
because the number goes the direction you wanted. Before each move, ask which gates can see the
destination, and widen the instrument's scope before the step that would fool it.

*Case:* a boundary gate scanned named files under one package; promoting a method to a base in a
utilities package would have made 100% of one rule's violations vanish while still existing.

## I17 · Separate refactor-only gates from result gates at build time

Some instruments guard the refactor (their target list *is* the plan - e.g. a refactor-coverage audit);
others guard the result (boundary allowlist, duplication and complexity ratchets, characterization
tests). Mark which is which when you build them. At exit, delete the first kind - with its tests, CI
steps and any CI cost only it justified - and keep the second, with its plan citations stripped.
