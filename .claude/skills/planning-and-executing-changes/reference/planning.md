# Planning, and verifying the plan

The question this file answers: *is this claim still true, is the work doable as written, and is
it the work I think it is?*

## Contents

- The plan-review-execute loop
- P20 Detail just in time
- P21 Findings flow upward
- P22 Approval at one level is not approval of the level below
- P23 A plan is only as good as its review, so keep each level reviewable
- P1 A finding is a measurement with a date on it
- P2 A number that disagrees with itself was never checked
- P3 Unverifiable is not the same as wrong
- P4 A recorded blocker is a claim like any other
- P7 "Pure" is a claim about the whole body, not about the signature
- P8 A limitation you inferred is a claim - measure it
- P9 The plan's account of a defect is a hypothesis
- P14 A step can be wrong while every one of its numbers is right
- P15 Check what a category contains before executing the verb
- P17 An exit criterion has to survive the step's other constraints
- P18 A right answer reached by a wrong mechanism points at the wrong fix
- P19 Pull open design questions forward

## The plan-review-execute loop

Planning does not end when a plan is approved. The same loop - **plan** at some grain, **review**
that plan against the code and get it approved, **execute** - runs at every level of detail the
work has, and "execute" at every level except the last means *descend one level and run the loop
again*, at the moment that piece of work comes up.

| Size of the work | Levels |
|---|---|
| A one-site fix | Plan (defect, fix, blast radius, tests) -> commit |
| A multi-site fix or a feature | Plan -> per-site or per-part plan when it comes up -> commit series -> commit |
| A multi-week effort | Plan -> step -> sub-step -> commit series -> commit (see the refactoring skill for the full table) |

At each level the review asks the question only that level can answer: the top level asks whether
the diagnosis is measured and the decisions settled; the lowest asks whether each commit leaves the
full suite green and what a person would see in the running program if it broke. Each review is a
real review - re-measure at HEAD, present it, wait for approval, record what was approved - before
descending. Work that "looks mechanical" gets the same treatment; that is where P14 and P15 bite
hardest.

A useful plan shape for a logic change, per site (`templates/change-plan.md`): what the defect is,
why it is or is not a real bug, the fix, what else touches that code, which tests cover it and
which will be written first, where in the running program a regression would show, and any site
where the obvious fix would change behaviour something else depends on.

## P20 · Detail just in time

Write the next level of detail only when that work comes up. A step planned in full weeks ahead is
a set of measurements that will decay before they are used (P1), and a detailed plan invites
execution from stale detail because it *looks* ready. Keep the plan coarse where the work is far
away, and make the detailed review part of starting each step.

*Case:* on the source refactor, every entry of one late step was re-measured when it came up and every
one carried a wrong figure; a claim in another had been written only the day before and was already
wrong.

## P21 · Findings flow upward

A review at a lower level can invalidate the level above: a sub-step whose premise fails, a step
that turns out to be another step's rider, a commit series that shows two "separate" steps share
state. When that happens, stop, rewrite the parent plan - the step entry, the sequence, a decision -
get it re-approved, and only then continue. Working around a voided parent from below leaves the
plan describing work that is not happening, and the next reader (or session) executes the plan.

*Case:* when a sub-step's review showed it was a protocol change rather than a move, the plan's
sequence gained a dated reordering note ("reordered - this moves after the call-conversion step") with
the call-site counts that justified it; when a later review dissolved it entirely, its step entry
said so, dated, and pointed at the step that absorbed it.

## P22 · Approval at one level is not approval of the level below

Approving the plan approves its shape, not every bullet at full elaboration; approving a step
approves its scope, not the commits. Each level's detail gets its own review. The converse also
holds: if the detail grows far past what the level above approved - more machinery, more files, a
new mechanism - that is the signal to stop and go back up a level, not to keep going because the
parent said so.

## P23 · A plan is only as good as its review, so keep each level reviewable

Every level of the recursion ends in a human review, and a plan too long to read carefully gets approved
without being read. Lead each level's artefact with a one-screen summary: what changes, in what order, what
is decided, what it is measured by, and what needs the reviewer's ruling. Put evidence and detail below or
in an appendix. The recursion is what makes this possible: the top-level plan only has to be detailed about
the next step, so it can stay short. Length is a real cost to the reviewer - spend it where a ruling is
needed, not on restating what the procedure already says.

*Case:* in an evaluation of this skill, a plan written with it was judged the stronger plan and also
criticised for its density; the plain-model plan, about 60% of the length, was easier to review.

## P1 · A finding is a measurement with a date on it

Re-verify a step immediately before working it, not when the plan is written. Treat handoff
notes, subagent reports, code comments and your own reasoning from an hour ago the same way: none
of it is evidence until re-derived. Re-run the full suite and every gate at the head commit
before touching anything, so "the branch was green" becomes a measurement with today's date.

*Case:* four verification passes moved 9, 5, 9-of-13 and 3 claims. Most of the third pass was
not code drift - the files were byte-identical since the plan was written; the numbers had simply
been measured wrong. A later pass took apart a claim written the day before, in the plan itself.

## P2 · A number that disagrees with itself was never checked

Grep the plan for its own repeated figures before trusting any of them. When a gate's scope is
widened, every recorded before/after pair under the old scope becomes wrong in the same commit.

*Case:* three times, one section contradicted another - a table of line counts, a tally of
decorated methods, and an allowlist bullet that mandated adding an entry beside a total computed
without it. A fourth arose after the rule was written: a headline "1,889 -> 31" compared a
six-family total with a three-family one, so the refactor looked finished before a whole step had
begun. The rule needs a check, not a reader.

## P3 · Unverifiable is not the same as wrong

A figure produced by an uncommitted script can be neither trusted nor discarded. Build the
instrument, re-derive the baseline, and let the instrument become the definition.

*Case:* a duplication baseline of 1,199 lines came from a one-off script nobody kept. Building a
committed instrument reproduced it exactly - and later, a "7 functions over complexity 10"
figure from another ad-hoc script turned out to be 8, because it had scored `with` as a branch.

## P4 · A recorded blocker is a claim like any other

Re-derive a dependency before obeying it. An unexamined block is worse than a wrong number,
because it stops work rather than misdirecting it. This includes "cannot be done because..." text
living in docstrings and decision logs: every recorded reason is a hypothesis with a date on it.

*Case:* a step sat "blocked on moving the filter state" for days. Checked, the state was the most
uniform thing in the cluster - same names, same types, ~290 lines already byte-identical - so it
was the strongest argument *for* the shared base. A base-class docstring claimed two copies of a
method "differ" and must stay separate; they differed by one blank line.

## P7 · "Pure" is a claim about the whole body, not about the signature

Before choosing a destination on the grounds that code is side-effect-free, grep the body for
instance access, I/O and messaging. Then check the side effects are load-bearing: silence them and
see which tests fail.

*Case:* a helper recorded as "a pure array transform" was headed for a module-level function. Its
signature said arrays in, arrays out; its body emitted three status messages and read the class
name. Silencing the emits failed two characterization tests.

## P8 · A limitation you inferred is a claim - measure it

When a design rests on "X is impossible", find out whether X is impossible, then check whether
the design still stands for a different reason and say which.

*Case:* a batching design was justified by "a signal round trip cannot resume a loop". Three lines
of real framework code showed same-thread signals are synchronous, so it can. The design survived
for a different reason (it keeps answers off the widget) - which had never been the one written down.

## P9 · The plan's account of a defect is a hypothesis

Probe a recorded defect before designing its fix. "Silently mangled" is a different bug from
"rejected", and it changes what ships and what the changelog says.

*Case:* the plan said a raw query "fails validation and is dropped". A six-line probe showed it was
accepted, spliced into invalid SQL, and committed under a renamed, reclassified label.

## P14 · A step can be wrong while every one of its numbers is right

Verifying figures is necessary and not sufficient. Ask what the step counts as success and whether
the recorded metric moves when that happens. The order that falls out: **choose the metric, build
the gate, scope the gate, then work the step.**

*Case:* four line counts for an "app shell" step were exact. Measured in cyclomatic complexity, two
of the four long files had essentially no complex functions - their length was flat widget
construction - so two targets came off and three unnamed ones went on. A repo-wide length gate would
also have aimed at 124 functions mostly in other people's files.

## P15 · Check what a category contains before executing the verb

A bullet naming a category and an action ("omit privates", "8 call sites", "13 parameters") is two
claims, and only the one carrying the number gets checked. Sample the category first. A count of
occurrences is not a count of call sites.

*Case:* "omit private methods from the docs" would have deleted 259 of 516 pages that were the
plugin author's contract - on those bases a leading underscore marks a subclass obligation. "8 call
sites" were mostly an unrelated dict key (3 real). Two of "13 parameters" were passed and never read.

## P17 · An exit criterion has to survive the step's other constraints

Before adopting a one-line exit check, run it against the step's own requirements and ask which
one gives.

*Case:* "a grep for the old mechanism's name over source and docs returns nothing" was incompatible
with the rule that a removed mechanism's docs page is rewritten to redirect readers - which must
name the old mechanism. Split it: nothing in source; in docs only where a page explains the
replacement.

## P18 · A right answer reached by a wrong mechanism points at the wrong fix

Check why a risk exists, not only that it does - only running the tool tells you which you have.

*Case:* the plan warned that a move would silently drop ~50 generated doc directives "because the
generator skips classes with no docstring". The classes had no docstring and were documented anyway.
The real exposure was a *different* step moving code into a directory no generator scanned at all.
Following the stated reason would have hardened the safe step and left the exposed one alone.

## P19 · Pull open design questions forward

An either/or sitting in a late step while earlier steps move the code it depends on is a decision
waiting to be forced by circumstance. Settle it as a decision record now, and state which
compatibility obligations are real.

*Case:* whether replayable actions record method names or declared action names sat open while
methods were being renamed. Ruling that the saved-action format carried no compatibility obligation
unlocked the cleaner design - and stating its invariant ("a replayed action is a pure function of its
recorded arguments") immediately exposed a live defect: two actions read UI state mid-body, so
replay applied whatever filters were selected *now*.
