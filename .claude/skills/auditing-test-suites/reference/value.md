# Auditing what each test is worth today

The question this file answers: *which tests would catch nothing if they were deleted, which ones claim
a check they do not make, and what does the suite fail to catch at all?*

## Contents

- The verdicts, and the evidence each needs
- Q1 Judge a test by what it catches now, not why it was written
- Q2 Drop only with evidence, and keep by default
- Q3 A test that passes when broken is armed, not dropped, if nothing else catches the break
- Q4 Know the shapes vacuous tests take
- Q5 A test that freezes a bug is a finding
- Q6 Redundancy concentrates in copies of base-class tests
- Q7 A structural test must be replaced by a guard that can see the defect
- Q8 Dead code shows up as tests nothing else needs; check reachability before removing it
- Q9 Trace a fix's consequences to every output before landing it
- Q10 Keep a golden that is the only catch, and give it a behaviour test

## The verdicts, and the evidence each needs

| Verdict | Means | Evidence |
|---|---|---|
| **Drop (a) covered** | A named test that stays fails for the same production defect | A mutation of *production* code; candidate and survivor both fail; the mutation confirmed applied |
| **Drop (b) cannot meaningfully fail** | Its failure would not be a defect: a private attribute, a call count, a mock checking itself, a census, a removed name | Reading, plus a mutation where the claim is not obvious |
| **Drop (c) vacuous** | It passes with what it names broken, and a survivor catches the break | A surviving mutation, and the survivor's failure |
| **Arm** | Vacuous, and nothing else catches the break | The tightened test fails under the mutation and passes without it |
| **Gap** | Nothing catches a real defect | A new test that fails under the mutation demonstrating it |
| **Bug** | The test pins a defect, or the code under it is dead | A ruling for the owner, then a fix with a test that failed on the old code |
| **Keep** | Default | None needed |

`templates/verdict-table.md` is the shape to report them in.

## Q1 · Judge a test by what it catches now, not why it was written

"Written for a refactor that is finished" is not a reason to drop anything. A characterization test that
still pins behaviour no other test pins is regression coverage. Ask only: if this test were deleted
today, which defect would go uncaught?

*Case:* 22 files marked as a past refactor's safety net, about 410 tests: none was a pure leftover. About
31 tests could go, and the SQL golden turned out to be the *only* test catching a real defect: two
experiments' scopes joined with AND instead of OR, so selecting two experiments returned nothing.

## Q2 · Drop only with evidence, and keep by default

Every drop names one of the three kinds of evidence above, and covered means a named survivor fails under
a mutation of production code - "touches the same code" is not evidence. Confirm each mutation applied
(a mutation tool reporting an anchor not found is not a result). Re-run one representative mutation per
group before deleting, because an audit's evidence can be stale by the time the cleanup runs.

*Case:* about 440 tests were dropped across five slices, each with its mutation recorded. Workers re-ran
the evidence before acting and twice kept a test the audit had listed: a query smoke test that was the
only catch for a column-dedupe removal, and peak-fitter key tests that were the only guard against a
declared column never produced.

## Q3 · A test that passes when broken is armed, not dropped, if nothing else catches the break

A vacuous test with no survivor still names a check worth having. Tighten its assertion or its wait so
that it fails under the mutation that exposed it, and show both runs. A real defect nothing catches gets
a new test, written first and seen failing under the mutation.

*Case:* about 30 tests were armed - a fitted-length check that never passed a wrong length, a padding
clamp asserted as `<= 10` where the answer is 3, abort tests over a single row, an export asserting only a
non-empty frame - and 14 gaps got tests, among them the AND/OR scope, a restore count, and a walkthrough
placement whose only tests had been skipped since the file was created.

## Q4 · Know the shapes vacuous tests take

Each of these passed with the behaviour its name claims removed:

- A helper that reads back what the fixture just wrote, not what the code under test received.
- `except Exception: pass` around the assertion, which swallows the `AssertionError` itself.
- An assertion always true for an unrelated reason (a stylesheet always containing "black" because of the
  border; `>= 0` on a count).
- A wait satisfied by state that existed before the action (the old figure still on screen, a combobox
  that always holds a placeholder, `count >= before`).
- Steps guarded by `if button.isEnabled():`, so a never-enabled button skips the check.
- A stub that ignores the input the test is about (a WHERE clause the fake loader never applies).
- A fixture that never makes the case (one row for an abort test; a "duplicate" column assignment that
  overwrites instead of duplicating).
- A widget never shown, so `isVisible()` is always False.
- A test that checks only that its own monkeypatch undid itself.

*Case:* every bullet is a test from one 2026-11-12 audit, each shown vacuous by a surviving mutation.

## Q5 · A test that freezes a bug is a finding

A test named `..._bug`, or one accepting "either outcome", pins a defect or pins nothing. Report it with
the defect, get a ruling, fix the code, and replace the test with one that failed on the old code. Trace
the fix's effect on everything users see first (Q9).

*Case:* two protein-model tests froze defects. A sanity check accepted, on a clean single peak, a
two-population fit whose second component had zero width; the owner ruled a zero-width component is no
second population, and a half-bin floor fixed it. A negative form factor returned NaN where the docstring
said it raised; no caller could pass one, so the fix changed no output.

## Q6 · Redundancy concentrates in copies of base-class tests

When behaviour moves onto a base class, the per-subclass tests usually stay behind, each a weaker copy.
Family-wide conformance tests supersede per-plugin contract tests the same way. Look there first, and
keep the strongest single test of the shared behaviour.

*Case:* one grid helper on a base view was tested 20 more times across three tab files; with rows and
columns swapped, 18 of the 20 copies still passed and the one behaviour test failed. Eighteen copies of a
base controller's tests sat in one tab's file, each failing together with its twin in another.

## Q7 · A structural test must be replaced by a guard that can see the defect

"The base owns the only copy", "this removed name is still absent" and hard-coded counts usually cannot
fail meaningfully: they fail on a harmless change and miss the same defect under another name. Drop them
in favour of an invariant guard - but check that the guard can see the case they covered, with the
mutation they covered.

*Case:* "only copy" tests were dropped in favour of a duplication ratchet, which failed on every
representative mutation. A worker then found the ratchet saw a base method copied onto *one* tab only as
"one more function", not as duplication: the bases were not in its measured families. Adding them closed
it (a pasted copy now fails and is named), and surfaced 66 lines two sibling bases already shared. A test
claiming that a tenth plugin family "fails here" compared a constant with a constant; it now compares
with the folders on disk.

## Q8 · Dead code shows up as tests nothing else needs; check reachability before removing it

Tests that are the only callers of a method point at dead code. Remove the code and its tests together,
call out a removed public method as breaking, and update any documentation that recommends it. Before
removing a guard, find the input that reaches it: an "unreachable" branch often has a corner case.

*Case:* a base-view method that stored data nothing read was removed with its six tests; the plugin guide
listed it as the way to push data to a view, so the guide changed with it. A `start >= end` skip that
looked unreachable after range merging was kept: a negative start on a zero-length channel reaches it.

## Q9 · Trace a fix's consequences to every output before landing it

A fix found by an audit changes results someone sees. Trace the changed value to every print, report,
file and database column before landing it, and say what users will now see.

*Case:* the owner asked whether the zero-width-fit fix would break printed results or new database
columns. Tracing showed the "no fit" path already existed for noisy peaks: the ensemble report says it
cannot fit, an event without a fit gets no row and its new columns stay NULL, and when no event fits the
panel says so and nothing is stored.

## Q10 · Keep a golden that is the only catch, and give it a behaviour test

A golden pins exact output, so a deliberate change regenerates it wholesale, and a regression made in the
same change rides along. Where a golden is the only test catching a defect, add a behaviour test that
executes the output and checks a result, so regeneration cannot carry the defect through.

*Case:* only the SQL golden caught the AND/OR scope join. A test that runs a two-experiment query against
a real database and expects rows from both now catches it too; a dozen weak smoke tests on the same query
builder were dropped, since their assertions (`"SELECT" in query`) could not have caught it either.
