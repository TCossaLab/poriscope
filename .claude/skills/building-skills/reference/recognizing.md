# Recognising when a skill is needed, and where a lesson belongs

The question this file answers: *something was learned - should it be written down, and if so, where
will the next session that needs it actually find it?*

## Contents

- S1 Sort every lesson by audience before deciding where it goes
- S2 Extend an existing skill before creating one
- S3 A new skill is a standing cost to every session
- S4 Distil from finished work; first-of-a-kind work is where the lessons are
- S5 Split a skill when most of its lessons apply outside its trigger
- S6 A rule that must hold every time is not a skill
- S7 Log corrections as they happen, both kinds

## S1 · Sort every lesson by audience before deciding where it goes

Three audiences, three containers. A method that holds in any project goes in a general skill. How one
repository works goes in that repository's project skill, with a one-line pointer in its always-loaded
instructions. A person's preference or ruling goes in memory. Sorting first prevents the two common
failures: a project fact buried in a general skill, where it misleads every other project, and a general
method buried in a memory file, where only one project's sessions ever see it. A lesson that only makes
sense with project names in it is a project lesson, however general it sounded.

*Case:* the first plugin written from scratch in a plugin-based application (2026-10-09) surfaced
registries that the plugin generator did not touch, found only by a failing suite. They went to the
repository's architecture skill (a "the repository also needs" list) with a `CLAUDE.md` pointer, the
general "first-of-a-kind work is where unwritten steps surface" went to memory as the user's standing
instruction, and the design ruling (a general plugin with narrowing subclasses) went to memory and the
project skill. None of it became a new skill.

## S2 · Extend an existing skill before creating one

Before proposing a skill, grep every existing skill's lesson index and description for the topic. If the
activity is one an existing skill already triggers on, the lesson goes in that skill's reference file for
the activity; if the activity is covered but a phase is not, add a reference file. A new skill is right
only when the activity has its own trigger - the user's words or the situation that should load it differ
from every existing skill's - and it carries several lessons, not one.

*Case:* the discovery stage (restating a rough request, rulings, use cases) was a new activity with eight
lessons, but it is the front of the same plan-execute loop, so it became `reference/discovery.md` and a
step 0 in `planning-and-executing-changes`, with the description widened to trigger on design discussion.
A separate "discovery" skill would have had to be loaded alongside the planning skill every time anyway.

## S3 · A new skill is a standing cost to every session

Every skill's description sits in every session's skill listing. The listing's budget is about 1% of the
context window; when it overflows, descriptions are dropped, least-used skills first, which removes the
keywords that trigger them. Each description is also capped at 1,536 characters in Claude Code. A new
skill therefore spends context in every session and competes with every other skill's trigger - it must
earn that with work it changes, not with tidiness.

*Case:* on 2026-10-24 one account's listing held about thirty skills, three of them house skills whose
descriptions run 362 to 1,165 characters. Adding a fourth general skill moves the listing closer to the
point where the rarely used house skills lose their descriptions first.

## S4 · Distil from finished work; first-of-a-kind work is where the lessons are

Write a skill from work that has happened, with its record in hand - never from work you expect to do. A
skill drafted ahead of the work contains guesses phrased as rules. The richest source is the first
instance of a kind of task, because that is where the unwritten steps surface; record them before the
branch is finished, while the cases are still exact.

*Case:* `refactoring-codebases` was distilled after the three-week, nine-step 2.0.0 refactor, from its
plan, its execution record, its 97 method rules and the maintainer's corrections along the way. Every
lesson kept the case that produced it, which is what later let 84 of them be recognised as general.

## S5 · Split a skill when most of its lessons apply outside its trigger

A skill's trigger decides when its lessons are seen. If most of its lessons would help in work its
description never fires on, they are stranded: move them to a skill whose trigger covers that work, and
make the original build on it. Move them verbatim, keeping their IDs (S16).

*Case:* on 2026-09-24, 84 of `refactoring-codebases`' 115 lessons turned out to be about plans, tests,
gates and verification in general, invisible to a bug fix because the skill only triggered on refactors.
They were split into `planning-and-executing-changes`, now "the default method" for any change, and the
refactoring skill was rewritten to load it first.

## S6 · A rule that must hold every time is not a skill

A skill loads only when its description matches, and once loaded it is not re-read; after compaction,
only its first 5,000 tokens come back. A rule that must hold in every session, or before every edit,
belongs where it is always present: a hook (Claude Code runs it on every matching event whatever the
model is attending to) or always-loaded instructions such as `CLAUDE.md`. Keep it in the skill as well,
since the instructions file does not travel between repositories.

*Case:* `planning-and-executing-changes` marks its first five standing rules as the ones that "hold in
every session" and copies them into the repository's `CLAUDE.md`, because the skill does not load for a
session that never matches its description.

## S7 · Log corrections as they happen, both kinds

The raw material of a lesson is a correction: one the user gave, or one of your own caught late (a claim
withdrawn, a count that was wrong, a recommendation reversed). Log each as it happens with the date, what
was assumed, the correction, and whether it is a lesson candidate. Own errors are the ones that go
unrecorded, because nobody else saw them.

*Case:* a design session logged all ten of the user's corrections as they came, but not its own premature
"nothing is left open", a wrong count, or a reversed recommendation. The first became a lesson only
because the session happened to remember it.
