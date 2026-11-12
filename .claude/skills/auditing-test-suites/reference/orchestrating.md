# Running an audit across parallel agents

The question this file answers: *how is a whole-suite audit split, briefed, merged and checked so that
parallel agents speed it up without lowering its standard?*

## Contents

- The shape of a run
- O1 Slice by directory, with one shared brief on disk
- O2 Each worker gets its own worktree and branch; the coordinator cherry-picks
- O3 Cap the machine: agents run single files, the coordinator runs the suite
- O4 Re-derive the claims that decide something
- O5 Relay a finding to the agents whose slice it explains
- O6 Give each agent its own scratch folder
- O7 Check every merged file for corruption the edit tools introduced
- O8 Gate every merged state, and reconcile the counts
- O9 Deliver the audit as a page, and ask only the questions that are the owner's

## The shape of a run

1. **Measure** (one agent per slice, read-only, own worktree): durations, then hypotheses proved by
   mutation or timing.
2. **Merge the findings** into one page the owner rules on (O9).
3. **Execute** (one worker per slice, own branch, shared brief): drops, arms, gaps, docstrings.
4. **Integrate** (coordinator): cherry-pick, check the files, gate, reconcile, write the records.

The coordinator keeps production code and the records (changelog, decision log, work queue) to itself;
workers change tests only. Two hands on the same production file in parallel is how a fix gets lost.

## O1 · Slice by directory, with one shared brief on disk

Split by test directory so no two agents edit the same file, and give every worker the same brief as a
file it reads, plus a short task naming its slice and items. The brief carries the standard, the owner's
rulings, the tool rules, and a list of *reserved* tests the coordinator will change itself.

*Case:* five workers (views, controllers and models, plugins, utils and scripts, integration and e2e)
read one brief file. Reserving the tests tied to production fixes kept two hands off them; the only
conflicts at merge were in files the coordinator had also edited.

## O2 · Each worker gets its own worktree and branch; the coordinator cherry-picks

Workers branch from one base commit in their own worktree and commit there; the coordinator
cherry-picks their commits onto the feature branch in turn. Expect conflicts where the coordinator
edited the same file, and resolve them by intent - two deletions next to each other are both kept as
deletions - then run that file before continuing. Check every worker commit reached the branch before
deleting worker branches: a resolved conflict changes the patch, so patch-identity checks report it as
missing.

*Case:* 24 worker commits came over in five cherry-picks with two conflicts, both deletion beside
deletion. The two resolved commits showed as "not on develop" by patch identity and were found by
subject before the branches were deleted.

## O3 · Cap the machine: agents run single files, the coordinator runs the suite

Each test process can take gigabytes, and seven agents each starting a parallel run will exhaust memory.
Forbid agents the full suite and any parallel run; let them run single files serially. The coordinator
runs every full gate, and its worker-sizing hook adapts to what the agents leave free.

*Case:* a worker peaked at 1.9 GB; seven agents were told mid-run to stop parallel runs. During the
cleanup, the coordinator's gates chose 5 workers instead of 6 because the agents held memory.

## O4 · Re-derive the claims that decide something

Agents' reports are claims (P1). Before acting on a headline, re-read the test and re-run its mutation.
Expect small disagreements in counts and treat them as information, not noise.

*Case:* re-running two vacuity mutations confirmed both. Workers corrected the audit twice (19 copies,
not 18; 5 double-only tests, not 6). One agent's mutation tool reported KILLED from a non-zero process
exit while pytest's own summary said "1 passed" - a stray worker thread at interpreter exit - and the
agent classified it by the summary line.

## O5 · Relay a finding to the agents whose slice it explains

A finding in one slice often explains another's numbers. Relay it at once, and ask the receiving agent
to confirm or refute it rather than adopt it.

*Case:* the plugins agent found explicit collections costing 2.35 s in the full run against 0.1 s alone.
Relayed to the teardown agent, it became the heap hunt that found the window leak; the unit agent's
event-filter finding, relayed the same way, explained a 127 s teardown in another slice.

## O6 · Give each agent its own scratch folder

Agents sharing one scratch directory overwrite each other's probe scripts by name. Give each a folder.

*Case:* `probe.py`, `mut.py` and `mutate.py` were overwritten at least three times between agents in one
shared scratchpad; each agent recovered by moving into its own subfolder.

## O7 · Check every merged file for corruption the edit tools introduced

Edits scripted through a shell can turn escapes into control bytes and break line endings, and nothing
fails loudly. After each merge, scan changed files for NUL, backspace and conflict markers
(`scripts/scan_files.py`). Mutation tools matching multi-line anchors need the file's real line endings.

*Case:* a heredoc-scripted edit wrote a NUL byte into a test file (collection failed) and another wrote
a backspace in place of a regex `\b` into a production comment and two docstrings (nothing failed; a
byte dump found it). Two mutations reported "anchor not found" because the files were CRLF and the
anchors LF.

## O8 · Gate every merged state, and reconcile the counts

Run the full suite after each worker's commits land, read the summary line, and reconcile the test count:
previous passed, minus removed, plus added, must equal the new figure (skipped tests counted
separately). End with a gate on a clean copy of the exact tip with generated artefacts built, so no test
skips for a missing file.

*Case:* 5,843 to 5,805 (41 removed, 3 added), then 5,635 (175 removed of which 2 were skipped, 3 added),
each reconciled; the final clean-copy gate on the tip ran the documentation tests that skip in a fresh
checkout.

## O9 · Deliver the audit as a page, and ask only the questions that are the owner's

Merge the slices into one page grouped by verdict, each row with its evidence, plus a short list of
judgement calls with the case for and against. Recommend; let the owner rule on the calls and on any
production defect. Ask follow-up questions only where the answer changes the work.

*Case:* the owner ruled on five judgement calls in one message, asked for two of them to be elaborated,
and gave one design ruling (a zero-width fit component counts as one population) when the defect was
shown with numbers.
