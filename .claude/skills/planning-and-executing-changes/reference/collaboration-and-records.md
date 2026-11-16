# Collaboration and records

Work is interrupted constantly - by sessions ending, by other people, by the work itself changing
its mind. This file covers how to work with the people involved and how to write state down so an
interruption costs nothing.

## Contents

- C1 Logic changes need an approved plan
- C2 Ownership: ask first, with measurements, and state the exit
- C3 One branch per piece of work
- C4 Keep one plan, in the repository and in a shareable page, telling the same story
- C5 Write the handoff so a cold start costs nothing
- C6 Put each kind of information in exactly one place
- C7 Keep the wrong turns
- C8 Replace documentation for a removed mechanism; do not delete it
- C9 Documentation coverage is a judgement about readers
- C10 Treat delegated work as claims, and attribute authorship explicitly
- C11 Stay out of the repository while someone else is driving it
- C12 Report outcomes faithfully, including the damage
- C13 Split a finished tree into the plan's commits by rebuilding each step
- C14 Before every release, audit the records and docs on the release branch
- C15 A line number in a long-lived record is a measurement with a date
- C16 An approval page must hand its decisions back through a channel you can read

## C1 · Logic changes need an approved plan

Do the read-only work first (measure, read the sites, trace the call paths), then present the plan
and wait. Being queued in a backlog is not approval, and approval of a plan is not licence to build
every bullet at full elaboration. The per-site plan shape is in planning.md and
`templates/change-plan.md`. Comments, docstrings and type
hints can usually proceed under a standing grant; confirm which grants exist.

For multi-commit work, present the commit series (the refactoring skill's `templates/commit-series.md`
has a shape for it) with the simulated metric per commit and the manual-pass map, get approval,
record the approved series in the plan, then execute.

## C2 · Ownership: ask first, with measurements, and state the exit

Where code or tests belong to someone else, the conversation is the correct opening move and costs
little. Make the ask answerable: break it into parts, each with the number it costs them (e.g. "324
test functions reference a moving name; 175 are a plain receiver rename; 75 encode a same-object stub
seam; 46 assert on a mechanism being deleted") - and say up front where "assertions untouched" is not
true rather than letting them discover it. An agreement is only as wide as the ask it answered, so keep
the ask on record.

Never write a plan whose critical path ends in "blocked on a person" with no exit. Every ownership block
needs a stated fallback - what happens and who decides if the owner does not engage. Advisory ownership
files (CODEOWNERS) are guidelines, not merge gates. Other owners' domain logic stays out of scope even
while you touch their files for mechanical reasons (docstrings, formatting), and a shared gate is scoped
so it cannot fail on their commits (measurement I6).

"Leave X's work alone" has a narrow and a wide reading - their active work, or everything they wrote.
Measure the boundary (authorship from `git blame`, the tracks they own) and ask which reading is meant,
with the numbers, before editing anything near it.

*Case:* 2026-11-16, a pre-release docs cleanup was told to skip two colleagues' work. Blame showed one had
written 908 lines of the decision log and three-quarters of the contributor QA page, so the wide reading
would have held most of the approved cuts; asked with those figures, the user chose the narrow one (their
active feature tracks only), and later released one entry the blame rule had held that was not on either
track.

## C3 · One branch per piece of work

Start a branch per step, commit, finish it into the integration branch as soon as the piece is
complete, and start a fresh one for the next. Do not ask whether to continue on the current branch, and
do not pile loosely related work onto a finished one. Use the repository's configured workflow commands
plainly. Do not push unless asked; the user decides when batches go out. A defect found against an
already-released version goes on a hotfix branch with a patch bump, not a feature branch.

## C4 · Keep one plan, in the repository and in a shareable page, telling the same story

The plan document in the repository is authoritative; where the tooling allows, publish a readable
page (an artifact, a wiki page) and update it as the plan executes rather than leaving it a snapshot of
the proposal. Record the page's link in the repository file. Include (the refactoring skill's `templates/plan.md` has the full shape for a long effort):

- Diagnosis with measurements, decisions A-Z, sequencing with reasons.
- A **live gate table** - start, now, target, floor and reason - updated in every commit that moves one.
- Each step's status, dated, with suite counts and gate values at completion.
- Every re-verification pass: what claims moved, from what to what, at which commit.
- A **method notes** section: each lesson learned, with the case that produced it (C7).
- Owed items (manual passes, reviews) until they are done.

*Also:* when a record keeps several tables of the same figures, mark every one but the live table as a dated snapshot never to be edited. *Case:* a branch began by updating a snapshot's row as though it were live, because the live figures sat elsewhere and the snapshot was the nearest thing that looked current.

## C5 · Write the handoff so a cold start costs nothing

At every stopping point, write a "Resume here" section: current branch and commit, what landed, the
exact next action, the gates' current values, what is owed, and anything in flight that must not be
lost. The next session - which may be you with no memory - should re-measure rather than trust it
(planning P1), but should never need to reconstruct it.

## C6 · Put each kind of information in exactly one place

- **Changelog** - what changed, for users. One line per change, no evidence or reasoning. Breaking
  changes are explicitly called out as breaking. Each of these counts: narrowing or removing anything on a
  public base, adding an abstract method to one, changing a signal's or a slot's signature, and changing
  the format of a saved file.
  Update it with every code change. After merging a stale branch, move its entries out of whatever
  released section they landed in and into the in-progress one.
- **Decision log** - why something was or was not done: context, decision, evidence, what would reopen
  it. Check it before re-litigating a settled question.
- **Work queue** - only what is still to do: one to three lines, `file:line` and the measured number.
  Delete a landed entry outright rather than marking it done; when part lands, rewrite the remainder as a
  forward-facing item. A queued finding without its number must be re-measured before it can be worked.
- **Plan** - the approved plan and its execution record; deleted when the release ships.
- **Contributor docs** - update whenever tooling or its configuration changes, or they go on stating a
  policy that no longer holds.

Keep all of them terse: several are read by agents, and every needless sentence is context spent.
Forward-looking status claims in old entries ("will be fixed in X") are corrected when they go stale.

## C7 · Keep the wrong turns

Record the method, not only the outcome: each lesson with the evidence that made it worth stating,
including judgement and instrument lessons that are neither code changes nor status updates. A plan
that records only its final state teaches nothing about avoiding the same errors, and the method notes
are what turns one project's cost into the next one's checklist. Group them by phase at the end; they
accumulate in the order learned, which is not the order used.

## C8 · Replace documentation for a removed mechanism; do not delete it

Ask what question the page answered, and rewrite it to answer that question with the new approach. Name
the old mechanism so someone searching for it lands on the redirect. A deprecation note is a placeholder,
not an end state. Check exit criteria against this requirement (planning P17). Surface a deprecation where
the affected user actually looks (the UI text they read daily), not only in the changelog.

*Also:* keep the old cross-reference labels alive on a rewritten page, so every existing link still resolves and the old names stay searchable; delete detailed sub-pages for the removed API rather than leave a reference for something that no longer exists.

## C9 · Documentation coverage is a judgement about readers

The useful question is not "how many generated pages do we lose" but "which of these does a reader reach
for". Publish the contract a contributor implements; drop internals no prose links to; hand-write a page
for the one internal a live tutorial depends on. Generate tutorial code from the real tool and include the
real files, so the example cannot drift and linters check it. Make examples educational - the route real
code takes - rather than faithful to an escape hatch.

*Case:* preserving 26 generated directives for four internal dialogs would have cost a new generator and
published 260 directives of undocumented widgets. Only one backed a tutorial - and that tutorial's two
cross-references had been escaped into plain text pointing at labels that never existed.

## C10 · Treat delegated work as claims, and attribute authorship explicitly

Delegate broad, read-only work (audits, reviews, citation sweeps) to parallel agents on disjoint slices,
then re-check every finding that carries weight by hand, and prove mechanical edits mechanically (an AST
diff showing only prose changed). Other contributors may use the same assistant, so prose style is not
evidence of authorship: when reporting a merge or integration, state explicitly what came from whom.

## C11 · Stay out of the repository while someone else is driving it

When the user is running version-control operations themselves, stop running commands against the repo
and wait, rather than polling state that is mid-change.

## C12 · Report outcomes faithfully, including the damage

If tests fail, say so with the output; if a step was skipped, say that; if a probe damaged something,
report the cost alongside the finding - reporting one without the other is choosing which half of the
result to hand over. When something is done and verified, state it plainly.

## C13 · Split a finished tree into the plan's commits by rebuilding each step

When work is finished uncommitted and the commits must follow the plan's steps, staging hunks cannot
express a file whose final content belongs to several steps, or a generated baseline that differs at each.
Rebuild each step's state in a separate staging worktree from the final files - shared files reconstructed
as they stood after that step, generated baselines regenerated - and commit there with the hooks and that
step's targeted tests. Check that the last commit's tree is byte-identical to the working tree, then move
the branch to it.

*Case:* 2026-11-11, a five-step port finished in one working tree was split into five commits this way.
Rebuilding the fifth step with its own run caught a duplication ratchet that pinned a file family at five
members after a sixth had been moved in - missed in the working tree, where only the moved files' own tests
had been rerun.

## C14 · Before every release, audit the records and docs on the release branch

Records and hand-written docs rot one true sentence at a time: a queued item lands and stays queued, a
decision is reversed and both versions stand, a doc keeps the count it had before a new member joined,
an always-loaded instruction file accretes stories. No single change is to blame, so no single change
fixes it. Before every release (minor ones too, not only major), after `release start` and before the
preparation commit, sweep the changelog, decision log, work queue, always-loaded instructions, skills
and hand-written docs, so that what ships and what gets published say what is true. Split the sweep by
file across parallel reviewers that check each claim against the code (C10); deliver the proposed cuts
for approval, with evidence per item; re-verify every "safe to cut" claim again at edit time, not from
the review; leave other owners' active work alone (C2). Look for: landed or duplicated queue entries,
superseded or mechanism-gone decisions, stale counts and line references (C15), docs for a removed
mechanism that were never replaced (C8), copies of one list that have drifted apart (measurement I18),
and changelog entries that narrate rather than state.

*Case:* 2026-11-16, before a major release: six review passes over about 22,900 lines of records, skills
and docs proposed about 5,400 lines of cuts. They found 7 work-queue entries that had already landed, 6
duplicated pairs, 19 decision entries for mechanisms that were gone or reversed, a decision log
grown to 51,000 words, a README command that no longer ran, a pre-commit hook whose folder list skipped
the newest plugin family, and user docs that never picked up a tab added the week before. Re-checking at
edit time turned up one more change: an entry the review called removable still held the only copy of a
revisit condition, which had to move before the entry could go.

## C15 · A line number in a long-lived record is a measurement with a date

A `file:line` citation is exact the day it is written and drifts with every edit above it; a header
saying the whole file "was re-verified on <date>" is a claim that expires silently and makes every
anchor beneath it look fresher than it is. In a decision log, cite the function or class; in a work
queue, keep the line (it makes the item workable) but re-anchor it when the item is worked, and never
assert a blanket re-verification.

*Case:* 2026-11-16, a work queue's header said its line numbers had been re-verified on 2026-09-24;
about 40 of its anchors had moved, and decision-log citations such as a `main_model.py` line range now
landed inside a different function. Function names in the same entries were all still right.

## C16 · An approval page must hand its decisions back through a channel you can read

A review page with per-item approve/skip controls is only useful if its decisions reach the session.
State kept in the viewer's own browser storage never does. Use a channel the agent can read: a copy
button that produces text to paste back, comment threads, or a store the page and the agent share. Say
on the page how the decisions get back.

*Case:* 2026-11-16, a 75-item cleanup review saved each mark in browser storage. "Proceed as marked"
arrived with nothing readable: no comments, no shared state. The work waited until the user pasted the
page's copied summary. The copy button was the one channel that worked.
