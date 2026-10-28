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

## C1 · Logic changes need an approved plan

Do the read-only work first (measure, read the sites, trace the call paths), then present the plan
and wait. Being queued in a backlog is not approval, and approval of a plan is not licence to build
every bullet at full elaboration. A useful plan shape per site: what the defect is, why it is or is
not a real bug, the fix, what else touches that code, which tests cover it - and flag any site where
the obvious fix would change behaviour something else depends on. Comments, docstrings and type
hints can usually proceed under a standing grant; confirm which grants exist.

For multi-commit work, present the commit series (the refactoring skill's `templates/commit-series.md`
has a shape for it) with the simulated metric per commit and the manual-pass map, get approval,
record the approved series in the plan, then execute. For a single change, `templates/change-plan.md`.

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
