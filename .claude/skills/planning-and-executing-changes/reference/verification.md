# Verification, and not being lied to

The question this file answers: *did the thing I ran actually run, did it finish, and does the
program still work for a person using it?*

## Contents

- The verification routine
- V1 Run the whole suite, in natural order, before every commit
- V2 Green means you read this run's summary line
- V3 Every automated gate can pass over an application that cannot start
- V4 Plan the manual pass before the branch, and make it performable
- V5 Assert on the surface the user reads, not the call that writes to it
- V6 For persisted state, read the file, not the object
- V7 Attribute a reported defect to a revision, not to the change you just made
- V8 A defect report needs a reachable input, not just a suspicious shape
- V9 "Not reproducible" is a result; a quiet probe measures the wrong program
- V10 A probe that boots the app writes to the user's real data
- V11 Build the tool, then use it for real work
- V12 "Landed" is a claim about behaviour, so a text match cannot settle it
- V13 Separate environment artefacts from measurements
- V14 Bisect, don't argue
- V15 A merge of upstream work produces a tree nobody has tested
- V16 A long run must say where it is while it runs
- V17 Save a failure's output before any rerun

## The verification routine

Before every commit:

1. Full suite, no path arguments, no marker filter - run in the background with the full output
   redirected to a file (`scripts/run_logged.py -- <test command>`).
2. Read the real summary line from this run's log, and the sentinel exit code. If they disagree,
   investigate (V2).
3. All static gates, reading every hook's verdict, not the last few lines.
4. If application code changed: launch the app and walk the manual-pass map for this commit (V4).
5. Record the result dated wherever the work is tracked (suite counts, gate values, manual pass
   outcome).

Iterating on a single failing test while debugging is fine; the gate is a full green run
immediately before the commit. Documentation-only changes need no run. Do not re-run the suite to
watch CI's own result - CI is the backstop, not a second local gate.

## V1 · Run the whole suite, in natural order, before every commit

Choosing a subset is itself the error-prone step. "It is only tests" is not a reason to scope the run;
it is exactly where collection order and shared state do their damage. Never pass test paths in a
hand-picked order: inverting the natural order has segfaulted interpreters from leaked GUI state and
exposed test doubles to compliance scans that never see them otherwise.

*Cases:* a scoped run skipping one test directory let a broken commit reach CI. A test double placed
under a directory collected earlier was audited by a compliance test and failed - invisible for days in
its previous location. A timing race failed only in the full run.

## V2 · Green means you read this run's summary line

Not the harness's exit code, not a progress line, not `| tail`. Append a sentinel (`REALEXIT=$?`) to the
log itself and wait on that, so what you poll is written by the process you care about. For multi-hook
gates, grep for every verdict (`Passed|Failed`) - with a multi-line summary the tail is as arbitrary a
window as the head. And the converse is worse: **a green summary line with a non-zero exit** means the
process died after the tests (teardown, threads, atexit) - that is a failure.

*Cases:* a backgrounded run reported "exit code 0" while the command inside had returned 127 and never
run a test - the zero belonged to the shell wrapper. It recurred later with the sentinel reading
`REALEXIT=1` over four errors. `pre-commit | tail -4` showed four green hooks and hid a failure three
lines above. A module exited 127 three runs out of three while reporting "8 passed".

*Also:* read every failure line, not only the first. *Case:* a real failure and a stale-cache failure arrived in one run, and the first line explained only one of them.

## V3 · Every automated gate can pass over an application that cannot start

Each gate is blind for its own unrelated reason, and the conjunction is what matters: they do not agree,
they merely all happen to miss. Where no test constructs the top-level object (a singleton application,
a process entry point), a human starting it is the only instrument pointed at that question.

*Case:* a commit deleted a method the constructor calls. 4,287 tests: green (nothing constructs the
application object). Eight hooks: green (the auto-fixer had reconciled the imports). The complexity
ratchet: green (a rising function count read as a split). The coverage audit: green (not a target). One
launch caught it.

## V4 · Plan the manual pass before the branch, and make it performable

Before starting a branch, map where in the running application a regression in each changed function
would surface - derived from the call sites, not the function names (`templates/manual-pass-map.md`).
Then pause at commit boundaries that move application code. Rules for the checklist:

- **State each step's preconditions.** A path behind a guard needs the guard's required state listed, or
  the pass exercises the guard instead. (Two channels selected: the View refused before the request
  reached the Controller, and the refusal looked like a finding.)
- **Read the status panel from the top**, not the last line - panels hide evidence below the fold, and
  cannot show that an identical line arrived twice.
- **Only list steps a human can actually perform.** A failure path that needs a plugin to raise or a
  file to be corrupt belongs in an automated test; say in the checklist that it is covered there.
- **Check that each step is possible in the state it assumes.** For every control a step clicks, read what
  enables it (its validation function) or launch the app and try it: a button that is disabled in that
  state makes the step impossible, however reachable its code path looks. An expected message is a claim
  too. Take it from a run of the app, not from the code path that could emit it; if you could not run it,
  label it "expected from the code, unverified". When a step fails because it cannot be done, the checklist
  was wrong, not the program.
- **Say plainly when a commit carries no app risk** (instrument-only commits) to save attention for those
  that do.
- **Record every pass dated**, so a later failure is attributable. Manual passes found four defects in
  nine checks on one step that ended with every automated gate green.

*Also:* have each checklist item name the code it exercises, so a pass that finds nothing still says what ran.

*Case:* an event finder that found no events left its channel unfinished, and the pass told the user to click
Plot Events on that channel and expect a "not finished" message. The button is disabled there (it needs a
reader, a selected channel and a valid event index), so the step could not be performed and the message was
reachable only in a state the pass never described. An earlier pass in the same series told the user to change
an axis and overlay a second plot, which resets the figure instead; both were steps written from the call
path without checking what the interface allows.

## V5 · Assert on the surface the user reads, not the call that writes to it

A test that pins the log is not a test that pins the message. Drive the real path and read the widget's
text, the file, the response body.

*Case:* a refusal had four passing tests asserting on captured logs; the user saw nothing, because the
UI log handler sat at ERROR and the message was a WARNING.

## V6 · For persisted state, read the file, not the object

When the symptom is about state that survives a restart, assert on the persisted artefact - one save-and-
load away from the live object. And when a report names two components, ask whether swapping their order
swaps the symptom: it is often naming the order, not the identity.

*Case:* "restore brings back tab A's filters but not tab B's". Two probes showed the in-memory restore
working perfectly. The session written back *during* the restore had an empty list for whichever tab was
restored last - B was simply opened second.

## V7 · Attribute a reported defect to a revision, not to the change you just made

Reproduce on the parent revision in a separate worktree before answering. A diff shows what changed; a
defect is about what behaves. Wrongly accepting the attribution means hunting a regression that does not
exist; wrongly denying it dismisses a real report. Fix it either way - provenance decides the commit
message and the changelog, not whether it is worth fixing. Use real collaborators in the probe: a mocked
axes object silently passed a case the real one failed.

Once the parent revision shows the defect is new, find the commit rather than reading the whole
branch diff: `git bisect run <script that reproduces it>` across the branch's commits (V14).

*Case:* four "regressions" reported after a rewrite: three pre-existing, one not a defect at all.

## V8 · A defect report needs a reachable input, not just a suspicious shape

Establish reachability before reasoning about behaviour. Structural evidence (an AST query) feels
conclusive and says nothing about the guard forty lines up. Write the input that would trigger it and see
whether the code accepts it - and read the comment already on the declaration.

*Case:* an accumulator reset inside a loop and consumed outside it was reported as "every subset but the
last is discarded". Guards above ensured all three loops ran exactly once, and a comment said so.

A defect found through a test or a review gets the same check *before* any fix is brainstormed or dropped:
trace how a user could trigger it through the UI - which button, which caller, which values that caller
really passes - and say in the plan whether it is user-reachable. The answer sets the framing (bug fix,
cleanup or deliberate drop) and what the changelog may claim.

*Case:* a label-formatting regex found while writing characterization tests was queued as a live defect. Only
at execution did tracing the callers show every in-app writer passes fixed, parenthesis-free column names, so
nothing could trigger it; the framing and changelog wording had to be walked back.

## V9 · "Not reproducible" is a result; a quiet probe measures the wrong program

Exonerate hypotheses by measurement, record what was ruled out, and invent nothing to fill the gap. If a
probe turns something off to stay readable (logging), that thing is now outside what it measured - the
app's own timestamped logs on the real machine are often the better instrument.

*Case:* a multi-second pause was chased through six hypotheses, each measured and ruled out, then stopped
reproducing. The first probes ran with logging disabled; re-measured with logging on, DEBUG cost 22
records per item and 40% more wall clock.

## V10 · A probe that boots the app writes to the user's real data

A scratch directory protects the repository, not the machine. A probe instantiating production classes
inherits every path they choose, and an application's job is to persist things outside the project. Find
what the code uses to locate user state and redirect it in the probe *before* the first object is built;
check that the redirect target exists, since a save that swallows its own failure looks like a no-op. If
damage happens anyway, say so plainly alongside the finding.

*Case:* a headless session round-trip overwrote the user's real session history; the platform user-data
lookup ignored both the test's temp path and the environment variable.

## V11 · Build the tool, then use it for real work

A test supplies its own inputs; a real use supplies the world's. Schedule one honest use before calling a
tool finished - ideally a job you already owed, so the dogfooding is free and the output is kept.

*Case:* a scaffold generator shipped with 47 passing tests and every gate green. Regenerating the tutorial
example with it surfaced three defects: a base method called but never declared, a sibling import that
could not resolve in a folder with a space, and a startup path putting the wrong folder on the import path.

## V12 · "Landed" is a claim about behaviour, so a text match cannot settle it

Before recording a fix as landed, ask what it would do and check that. Check the date of what you found - a
match that predates the plan cannot be the plan's work. Good news gets checked least.

*Case:* two of five contract breaks were credited as landed: one was a line inside a docstring example; the
other was a signature that had existed on every base since before the refactor. Both survived a breaking-
change audit built on a parsed signature diff, which neither changes.

## V13 · Separate environment artefacts from measurements

A cloud-synced checkout, a cold file cache or one slow machine can dominate a timing. Measure warm and cold,
report which is which, and do not propose code changes whose only justification is a development-machine
artefact. Keep such measurements in the decision log rather than the work queue, so they survive without
implying a task. For suite-time comparisons, run both revisions in worktrees outside the synced folder.

## V14 · Bisect, don't argue

When a failure has a cause somewhere in a set - commits, test files, the hunks of one diff - halve the
set and re-run rather than reasoning about which member is guilty. Reasoning picks the plausible suspect;
bisection finds the actual one, and it also exonerates: the suspect you would have "fixed" is cleared by
an experiment rather than by an argument. Script the reproduction so each probe is one command
(`git bisect run`, or a loop over test-file subsets), and bisect along whichever axis the failure varies:

- **Commits**, when a behaviour changed between two revisions (after V7 has shown it did).
- **Test files and classes**, when a crash depends on what ran before it. The test that dies is often the
  victim, not the cause.
- **The hunks of one change**, when a commit trips a gate in code it never touched: apply the change in
  halves until the one hunk that matters is left.

*Cases:* an interpreter crash in a GUI test suite was repeatedly blamed on whatever had been committed last.
Bisected over the test files, it narrowed to one file, then one test class, then a single `clear()` call
on a widget disposed of unsafely hundreds of tests earlier; the test that crashed only happened to spin the
event loop. The prime suspect commit was exonerated by re-running with its files reverted, which crashed
identically. Separately, a commit that only removed nested helper functions made a docstring linter fail on
a method it never touched. Checking the old file (passes) against the same file with just the helpers
removed (fails) proved the helpers had been hiding a pre-existing violation, so the fix was to document the
method rather than revert the commit.

## V15 · A merge of upstream work produces a tree nobody has tested

When integrating a branch that moved while you worked - a refused `finish`, a diverged remote - the merged
tree is new: each side was green alone, the combination never ran. Run the full suite and the ratchets on
the merge before building further on it, and say whose work came in.

*Case:* finishing a one-file fix was refused because another developer had pushed about 1,300 lines of
changes to the same plugin family upstream. Only the changelog overlapped and the merge was clean, which
proves nothing about behaviour; the suite on the merged tree was the first run of both together.

## V16 · A long run must say where it is while it runs

A logger that saves output only when the command ends shows nothing about a run that stops. Stream a
long suite's output to the file as it goes, give each test a timeout (pytest-timeout's `--timeout`),
and watch the file for a stall rather than waiting for an exit, so a stop can be told apart from a
hang and a hang names the test it is in. Before blaming the code for a stall, check the machine: a
sleep, hibernation or power cut stops the run and shows the same silent log.

*Case:* a full suite run through `run_logged.py` sat for 11 hours with a one-line log. The wrapper read
line by line, but the Python child block-buffered its piped output and the log was never flushed (both
fixed in the script since), so nothing showed where it was. The guess was contention with the app the
user had open; the cause was the computer hibernating after a power problem. Rerun with streamed
verbose output and a 300-second per-test timeout, it passed in 7 minutes.

## V17 · Save a failure's output before any rerun

The first failure is the only one that carries the evidence, so write its full output to a file before
any rerun (redirect the run; do not read a tail and re-run). A loop of reruns saves every failing run's
output too. A failure that will not reproduce is not closed: record it as open, with the file and the run
counts, and read the next full and clean-copy runs for it.

*Case:* a replay scenario failed once in about 35 runs, right after its perturbation was made effective. The output
was not kept, so a hundred quiet reruns afterwards proved nothing and the cause stayed unknown.

*See also:* V2 for reading the run you saved, and V9 for recording what a non-reproduction ruled out.
