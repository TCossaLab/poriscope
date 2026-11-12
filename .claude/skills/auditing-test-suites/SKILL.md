---
name: auditing-test-suites
description: Audits a whole test suite for speed and for value, end to end - measuring every phase of a full run, tracing setup and teardown cost to leaks earlier tests leave behind, fixing harness defects before parallelising, sizing parallel workers from the machine, then judging every test by what it would catch today, dropping only with mutation evidence, arming tests that pass when broken, adding tests for gaps, and treating tests that freeze a bug as findings. Covers splitting the audit across parallel agents and merging their work. Builds on planning-and-executing-changes. Use before every major release, and whenever the user asks to audit, review, prune, clean up or speed up the tests or CI - "the tests are slow", "CI takes too long", "which tests are useless", "are these tests still needed" - even if they only ask why one test file got slow.
---

# Auditing test suites

A test suite decays in two directions at once. It slows down, mostly from state one test leaves for the
next, and nobody sees why, because the cost lands far from its cause. And it fills with tests that
catch nothing - copies of other tests, assertions always true, waits satisfied before anything happens -
which cost time, read as coverage, and hide the real gaps. This skill is the method for finding both,
fixing them without losing anything the suite catches, and proving it.

It was distilled from one audit of a desktop application's suite (about 5,850 tests, PySide6 and pytest,
Windows and Linux CI) on 2026-11-12. The serial run went from 1,650 s to about 400 s and a parallel run
to about 100 s; about 440 tests were removed, about 30 armed and 14 gaps covered, with mutation evidence
for every change. Every lesson carries the case that produced it.

**Load `planning-and-executing-changes` first**; its testing and verification lessons (N4, N8, N17, V2,
P1) are the ground this stands on. Lesson IDs are unique across the sibling skills.

## When to run it

- **Before every major release**, as part of release preparation.
- **Whenever the user asks** to audit, prune or speed up the tests or CI.
- A smaller version - T1 and T2 only - whenever one file or one CI leg gets noticeably slower.

## The stance, in six sentences

1. **Measure every phase of one full run before changing anything**; cost hides in setup and teardown (T1).
2. **Cost that is not local is a leak upstream** - fix the cause, never the victim, and fix it at the scope
   of the resource (T2, T3, N17).
3. **Fix the harness before parallelising, then parallelise by whole files with workers sized from the
   machine** (T5, T6).
4. **Judge each test by what it would catch today**, never by why it was written (Q1).
5. **Remove nothing without evidence: a mutation of production code that a named survivor catches, or
   that shows the test cannot fail meaningfully**; a test that passes when broken with nothing else to
   catch the break is armed, not dropped (Q2, Q3).
6. **A speed claim counts only from a full run, and an audit's claim only once re-run** (T11, O4).

## Reference files - read the one for what you are doing

| File | Read when |
|---|---|
| [reference/speed.md](reference/speed.md) | The suite or a file is slow; reading a durations report; a leak, a teardown, parallel workers, repeated setup |
| [reference/value.md](reference/value.md) | Deciding whether a test is worth keeping; a test looks vacuous, redundant or structural; a test pins a bug; dead code |
| [reference/orchestrating.md](reference/orchestrating.md) | Splitting the audit across agents; briefing workers; merging their branches; gating and reconciling |
| [reference/lesson-index.md](reference/lesson-index.md) | Looking up a lesson by ID or symptom (grep it) |

## The procedure

Copy this checklist into your working notes and keep it current:

```
Test audit progress:
- [ ] 0. Baseline: one full serial run, every phase timed, saved; machine load noted (T1)
- [ ] 1. Diagnose speed: rank by file and phase; slow files timed alone; census what is alive (T2-T4)
- [ ] 2. Fix the harness; prove it with one full serial run (T5, T11)
- [ ] 3. Parallelise by file, sized from the machine; deterministic collection; attack the longest file (T6-T8)
- [ ] 4. Value audit: slice the suite, one brief, a verdict with evidence per candidate (Q1-Q4, O1)
- [ ] 5. Findings page; owner rules on judgement calls, bugs and dead code (Q5, Q8, O9)
- [ ] 6. Execute: workers drop, arm, add gaps on their own branches; coordinator does production fixes (Q3, O2)
- [ ] 7. Integrate: cherry-pick, scan files, gate every merged state, reconcile counts (O7, O8)
- [ ] 8. Final: clean-copy gate on the exact tip, records updated, lessons recorded
```

### 0-1 · Measure, then diagnose

`scripts/durations_report.py` turns a `--durations=0` log into per-phase, per-directory and per-file
totals and, given a second log of files run alone, the full-run-to-alone ratio per file. A high ratio, or
time in setup and teardown, means look upstream (T2). Log live objects and windows per file to find the
leaker (T3). Check for the amplifiers: global registration per instance, explicit full collections,
per-test fixtures whose cost grows with the run (T4).

### 2-3 · Fix, then parallelise

The cleanup for a process-wide resource goes at the root of the test tree, and fails the test when
something survives (N17). Parallelise only after a full serial run proves the fix (T5). Whole files per
worker, worker count from cores and free memory, an override, the serial run kept, collection sorted (T6).

### 4-7 · Audit value, then act on it

Slice by directory across agents, one shared brief file (`templates/worker-brief.md`), verdicts in
`templates/verdict-table.md`. Everything defaults to keep. The owner rules on judgement calls, frozen
bugs and dead code before any production change (Q5, Q8, O9). Workers change tests only; the coordinator
owns production code and the records (O1, O2).

## Standing rules

1. **No drop without evidence**, recorded with the drop (Q2).
2. **A test that passes when broken is armed if nothing else catches the break**, and shown failing (Q3).
3. **A speed or test-count claim is accepted only from a full run's summary line** (T11, O8, V2).
4. **Workers change tests; production code and records stay with one coordinator** (O1).
5. **Every merged state is gated, and the last gate is on a clean copy of the exact tip** (O8).

## Red flags - stop and check

| You notice | Check | Lesson |
|---|---|---|
| Setup or teardown is a large share of the run | A leak from earlier tests: compare the file alone | T1, T2 |
| A file is far slower in the full run than alone | Census what is alive after each file | T2, T3 |
| One teardown takes minutes | It is the first file to clean up what others leaked | T2 |
| A fixture calls a full garbage collection | Its cost grows with the heap; collect only on the failure path | T4 |
| You are about to add parallel workers to a slow suite | Is the slowness a leak? Fix it first | T5 |
| A worker count is a constant | Size it from cores and free memory, with an override | T6 |
| Parallel workers refuse to start, or collect different tests | A parametrization from a set or dict; sort it | T6 |
| More workers stopped helping | The longest file sets the floor | T7 |
| You are about to shrink test data for speed | Is its size calibrated? Copy a template instead | T8, T10 |
| A test is listed to drop as "covered" | Name the survivor and run the mutation | Q2 |
| An assertion is `>= 0`, `is not None`, or inside `try/except` | Mutate what it names; does it fail? | Q4 |
| A wait could be satisfied before the action | Wait on this run's own completion | Q4, N8 |
| A test name or comment says "bug" or "either outcome" | It freezes a defect: rule, fix, replace | Q5 |
| Several tab or plugin files test the same base method | Keep the strongest one | Q6 |
| You are replacing structural tests with a ratchet | Can the ratchet see the exact case they caught? | Q7 |
| A method's only callers are tests | Dead code: remove both, after checking reachability | Q8 |
| An audit fix changes a computed result | Trace it to every print, file and column | Q9 |
| A golden is the only test catching a defect | Add a behaviour test that executes the output | Q10 |
| Several agents will run tests at once | No full or parallel runs in agents | O3 |
| Agents share a scratch folder | One folder each | O6 |
| An edit was scripted through a shell | Scan for control bytes before testing | O7 |
| The test count after a merge is not old minus removed plus added | Find the difference before going on | O8 |

## Scripts and templates

Stdlib-only Python 3.9+. Run each with `--help`; execute them rather than reading them.

| Script | Purpose |
|---|---|
| `scripts/durations_report.py` | Aggregate a pytest `--durations=0` log by phase, directory and file; with `--alone`, the full-run-to-alone ratio per file |
| `scripts/scan_files.py` | Report NUL, backspace and other control bytes, and leftover conflict markers, in given files or a git diff range |

| Template | Use |
|---|---|
| `templates/worker-brief.md` | The shared brief every cleanup or audit worker reads |
| `templates/verdict-table.md` | One row per candidate test: verdict, standard, evidence, survivor, coverage lost |
