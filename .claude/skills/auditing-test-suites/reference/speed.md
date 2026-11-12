# Making a test suite fast without making it weaker

The question this file answers: *where does the suite's time actually go, and which change buys it back
without losing a single thing the tests catch?*

## Contents

- The speed pass, in order
- T1 Measure every phase of one full run before changing anything
- T2 Cost that is not local is a leak upstream
- T3 Count what is alive to find the leaker
- T4 Know the amplifiers that turn a small leak into minutes
- T5 Fix harness defects before parallelising
- T6 Parallelise by whole files, sized from the machine
- T7 The longest file sets the parallel floor
- T8 Build deterministic work once and copy it; share only what nobody mutates
- T9 Sometimes the slow thing is the product - fix the algorithm
- T10 Do not shrink data whose size is calibrated
- T11 A speed claim counts only from a full run

## The speed pass, in order

1. One full serial run with per-test durations for every phase (setup, call, teardown), saved to a file
   (`scripts/durations_report.py` aggregates it). Note the machine and what else was running.
2. Rank by file and by phase. Setup and teardown above a few percent of the total are suspects (T1).
3. For each slow file, time it alone and compare it with its full-run time (T2). A large ratio is a leak
   upstream, not slowness here.
4. Census what is alive per file to find the leaker (T3); look for the amplifiers (T4).
5. Fix the harness, prove it with one full serial run (T5, T11).
6. Only then parallelise (T6), and attack the longest file (T7) and repeated work (T8).
7. Profile what is left; some of it is the product (T9).

## T1 · Measure every phase of one full run before changing anything

A suite's time is not where the test bodies are. Record setup, call and teardown separately for every
test in one full run (`pytest --durations=0 --durations-min=0`, saved to a file) and aggregate by phase,
directory and file before forming any hypothesis. The phase split alone usually names the problem: test
bodies doing real work show up as *call*; harness defects show up as *setup* and *teardown*.

*Case:* a 1,650 s suite of about 5,800 tests spent 466 s in test bodies, 644 s in setup and 509 s in
teardown. Two files held 448 s of the teardown - one 126.85 s teardown on a single test, and 4.7 s after
every test of another. Neither was visible from "the suite is slow".

## T2 · Cost that is not local is a leak upstream

Time each slow file alone and compare it with its time in the full run. A file far slower in the full
run, or one whose time sits in setup and teardown rather than its bodies, is paying for state earlier
tests left behind. It is the victim: fixing it is wasted work, and it will be slow again. The general
lesson behind this is N17 in `planning-and-executing-changes`.

*Case:* a conformance file took 27.3 s in the full run and 4.7 s alone; an integration directory took
588 s in the full run and the same alone, so the leak was inside it. The 127 s single teardown belonged
to the first file of the next directory, which happened to destroy 9,300 windows other tests had leaked.

## T3 · Count what is alive to find the leaker

A census - live top-level windows, live objects by type, heap size - logged after every file, located in
one run what reading could not. Count after cleanup, not after the call you trust to clean up: a closed
window is hidden, not destroyed, and a scheduled deletion is not a deletion until its event is delivered.

*Case:* a heap census plugin (objects by type, per file) showed 2.47 million live objects and 9,306
top-level windows when the view tests started, and named the integration flows as the leakers: about 880
widgets per test harness, held alive through signal connections the collector cannot see. One root-level
fixture that deleted every top-level window after every test took the suite from 1,650 s to 493 s with
no assertion changed.

## T4 · Know the amplifiers that turn a small leak into minutes

A leak costs little until something multiplies it. Three did, all measured:

- **Per-instance registration on a global object.** Each leaked line edit stayed an application-wide event
  filter, so every later event made one Python call per leaked widget: building one controller took 52 ms
  with none alive, 11.6 s with 1,000.
- **Explicit full garbage collection.** Its cost scales with everything alive: 0.1 s alone, about 2.4 s in
  the full run. A fixture collecting twice per test cost 321 s, and no file-lock retry it existed for ever
  fired. Collect only on the failure path that needs it.
- **A per-test fixture whose cost grows with the run.** An autouse fixture asked for `tmp_path` in every test,
  and the framework lists its whole base directory to number each new one: about 47 s over the suite. One
  session directory with a counter gave each test the same fresh sandbox.

*Case:* the three above, from one suite on 2026-11-12. The first also slowed the shipped application,
which registered one filter per field; one shared filter replaced them.

## T5 · Fix harness defects before parallelising

Parallel workers divide a leak's cost without removing it, so they hide it and the next leak with it.
Fix what the census found, prove the fix with one full serial run, then parallelise. Put cleanup of a
process-wide resource at process scope and make it fail the test when something survives (N17), so the
next helper that leaks fails at once.

*Case:* the leak fix alone took the serial run from 1,650 s to 493 s; parallelising afterwards took it to
128 s on 4 workers. The same leak had been fixed once before in one directory only, and came back through
a harness written later in another.

## T6 · Parallelise by whole files, sized from the machine

- **Distribute by file** (`--dist loadfile` in xdist), so each file runs whole and in its own order on
  one worker; test order has mattered in suites with shared GUI state.
- **Size workers from the machine, never a constant.** Use the smaller of logical cores and free memory
  divided by a measured per-worker peak. Logical, because a 4-vCPU cloud runner reports two physical cores.
  Let an environment variable override, and have the sizing hook defer to it rather than shadow it.
- **Keep the serial run working**, and do not make parallel the default for single-test runs: every worker
  starts the whole framework.
- **Make collection deterministic.** Every worker must collect the same tests in the same order, so any
  parametrization built from a set or a dict of discovered classes has to be sorted.

*Case:* one worker peaked at 1.9 GB, so a 22-core machine with 13 GB free got 6 workers rather than 16
and a 4-vCPU, 16 GB runner got 4. The first parallel run failed to start: a compliance test
parametrized over a set of subclasses collected in a different order on each worker.

## T7 · The longest file sets the parallel floor

With whole files per worker, the run cannot finish before its longest file, so more workers stop
helping early. Look at the longest file next: it usually repeats work its tests could share.

*Case:* 16 workers took 98 s against 128 s on 4, because one 45 s replay file set the floor. Its tests
recorded and replayed the same histories several times; recording each once and replaying each mode once
cut 28 recordings and 28 replays to 8 and 20, with every test keeping its own assertions. The same
production mutations failed the same test IDs before and after.

## T8 · Build deterministic work once and copy it; share only what nobody mutates

Generated recordings and databases built per test can be built once per session and copied per test, so
each test still owns its files. Results that tests only read - a complete fit, a complete search - can be
computed once per module. Never share an object a test changes: rebuild it, and make it cheap instead.

*Case:* a 2 s, 4 MHz recording generated for about 30 tests became a session template copied per test
(8.0 s to 4.4 s on one file); a database written through the real writer for each of 22 tests became a
module template (11.7 s to 6.9 s setup). A plotting tab was not shared: every test changed its figure and
history, and once the leak was fixed a fresh one cost 0.25 s.

## T9 · Sometimes the slow thing is the product - fix the algorithm

Profile what is left after the harness is clean. A test that is slow because the code under test is slow
points at a cost every user pays.

*Case:* an event finder's edge search scanned the whole data chunk for every event, O(samples x events):
a 12-million-sample chunk with 100 events took 15.8 s. Searching outward in growing slices, and the same
for the threshold crossings, took it to 0.05 s with identical events, shown by an equivalence test at
every slice seam and mutations that broke each seam.

## T10 · Do not shrink data whose size is calibrated

Smaller synthetic data is the obvious lever and usually the wrong one. Statistical tolerances, event
counts and margins were set against the current sizes, and once data comes from a copied template its
size costs milliseconds.

*Case:* an audit of the numerical tests proposed no shrinking: tolerances cited calibrated counts
("11/25"), halving a recording would have saved about 2 s once the finder was fixed, and it would have
broken a deliberate match with the integration parameters.

## T11 · A speed claim counts only from a full run

Per-file and per-subset timings by several agents on a shared, loaded machine are estimates; their sum is
not the suite's saving, and a single file's figure can be off by a factor. Accept a speed claim only from
a full run, serial and parallel, in a clean copy of the exact commit.

*Case:* subset measurements summed to about 890 s saved; the full run showed 1,157 s. One prototype was
reported at 23.4 s to 7.1 s and measured 19.0 s to 15.0 s after landing.
