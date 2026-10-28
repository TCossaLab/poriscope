# Verification during a refactor

Every verification lesson (V1-V15) and the before-every-commit routine are in the general skill's
[verification.md](../../planning-and-executing-changes/reference/verification.md): the full suite in natural order, reading this run's summary
line, launching the program because every gate can pass over one that cannot start, planning the
manual pass, attributing a defect to a revision, and bisecting instead of arguing.

What a refactor adds to that routine:

- **Launch the application at every commit boundary that moves application code**, not only at the
  end of a step. A move is exactly the change that leaves every gate green over a program that cannot
  start (V3): nothing constructs the top-level object, the auto-fixer reconciles the imports, and a
  rising function count reads as a split.
- **Map the manual pass per branch, before the branch is cut** (`templates/manual-pass-map.md` in the
  general skill), derived from the call sites of what moves, and record each pass dated in the plan's
  step entry.
- **Run one full-scope manual pass before the first structural change and one at exit.** The first is
  the baseline that makes a later failure attributable; the passes between cover only each step's
  surface, so without the exit pass nothing checks the finished whole.
- **Re-run the suite and every gate at HEAD before each step**, so the step's premise is measured
  today (P1), and record the counts in the plan's live table.
