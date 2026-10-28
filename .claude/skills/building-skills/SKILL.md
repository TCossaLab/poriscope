---
name: building-skills
description: How to recognise when a new Agent Skill is warranted, and how to build, extend, split, install and maintain one in this house's shape - lessons with IDs and cases, one reference file per activity, a lesson index, standing rules, red flags, templates and stdlib scripts. Sorts every new lesson by audience first (any project, this repository, this person), so most lessons extend an existing skill, a project skill or memory instead of starting a new one. Use whenever first-of-a-kind work finishes, a correction or wrong turn surfaces that no loaded skill covers, the same kind of correction recurs, the user says "remember how to", "turn this into a skill" or "record the lessons", a SKILL.md or reference file is getting long, or you are about to add a lesson to, split, merge, rename, install, sync or check a skill - even if nobody says "skill". For evals, benchmarks, description tuning or packaging, also load skill-creator.
---

# Building skills

A skill is how one session's hard-won lesson reaches the next session that needs it. It fails in
three ways: the lesson is never written down, it is written where the next session will not look, or
it is written somewhere that never loads. This skill is the method for avoiding all three, and the
house shape the existing skills (`planning-and-executing-changes`, `refactoring-codebases`, and a
repository's own architecture skill) were built in. Anthropic's `skill-creator` skill is the companion for
measuring a skill - evals, benchmarks, description tuning, packaging; this one decides whether a skill
should exist, what goes in it and where, and how it is kept loading (see "Using skill-creator" below).

Every lesson carries the case that produced it. The cases come from building and maintaining those
skills (September-October 2026).

## The stance, in five sentences

1. **Sort a lesson by audience before deciding where it goes** - any project, this repository, or this
   person - because the audience picks the container (S1).
2. **Extend before you create.** A new skill costs context in every session and competes with every
   other skill's trigger; it has to earn that with an activity no existing skill's trigger reaches (S2, S3).
3. **Distil from finished real work, never from anticipated work**, and keep the case with every rule (S4, S9).
4. **The description is the only part that is always loaded**, so a stage it does not name never
   triggers (S8).
5. **A skill is only installed once you have seen it load** - in the listing, unprefixed, from the copy
   you edited (S13, S14).

## Reference files - read the one for what you are doing

| File | Read when |
|---|---|
| [reference/recognizing.md](reference/recognizing.md) | Something surprised you; first-of-a-kind work is ending; deciding whether a lesson goes to memory, CLAUDE.md, an existing skill or a new one; whether to split a skill |
| [reference/anatomy.md](reference/anatomy.md) | Writing a new skill or a new section: the house layout, frontmatter, description, lesson shape, IDs, index, templates, scripts, README |
| [reference/maintaining.md](reference/maintaining.md) | Adding or moving a lesson; renaming, splitting or merging a skill; installing, syncing or uploading one; deciding how to evaluate a change |
| [reference/lesson-index.md](reference/lesson-index.md) | Looking up a lesson by ID or symptom (grep it) |

Templates are in `templates/`; `scripts/check_skill.py` checks a skill or a whole skills root.

## Recognising that a skill is needed

Watch for these during any work, and act on them at the end of it, before the branch is finished:

- **A correction the user had to give** that a loaded skill should have prevented, or a wrong turn of
  your own caught late. Log both kinds as they happen (S7); they are the raw material.
- **First-of-a-kind work** - the first plugin of a family, the first release, the first migration. Its
  unwritten steps surface exactly once (S4).
- **The same correction a second time**, in any session. The first was a fact; the second is a pattern.
- **A skill or reference file outgrowing its trigger** - most of its lessons apply where its
  description would never fire (S5), or `SKILL.md` nears 500 lines or 5,000 tokens (S10).
- **A rule that must hold every single time.** That is not a skill at all: it is a hook or an
  always-loaded instruction (S6).

Then sort and place each item with the table below. Only the last row creates a skill.

| The lesson is about | It goes in | Lesson |
|---|---|---|
| This person's preference, ruling or working style | Memory, one fact per file | S1 |
| A rule that must hold in every session of one repository | That repo's `CLAUDE.md` (and the general skill's standing rules, if general) | S6 |
| How this repository works (registries, trap questions, procedures) | The repo's project skill under `.claude/skills/`, with a one-line `CLAUDE.md` pointer | S1 |
| A method that holds in any project, inside an existing skill's activity | A new lesson in that skill's reference file for the activity | S2 |
| An existing skill's activity, but a phase it has no file for | A new reference file in that skill | S2 |
| A distinct activity with its own trigger, several lessons, likely to recur | **A new skill** - propose it first (`templates/skill-proposal.md`) | S2, S3 |

## Building one - the procedure

Copy this checklist into your working notes and keep it current:

```
Skill progress:
- [ ] 0. Propose: the evidence (cases), audience, trigger, name, location, neighbours; get approval
- [ ] 1. Harvest: every lesson with its real case, from the conversation, corrections log, memory, decision log
- [ ] 2. Generalise: project names out of the rules; cases kept, generalised; IDs assigned (unique across siblings)
- [ ] 3. Write: SKILL.md from templates/SKILL-skeleton.md; one reference file per activity; index; README
- [ ] 4. Description: what + when, every stage named, triggers in the user's words, <= 1,024 chars
- [ ] 5. Wire: CLAUDE.md pointer / standing-rule copies; links to sibling skills by relative path
- [ ] 6. Verify: check_skill.py clean; skill shows in the listing, unprefixed; scripts run --help
- [ ] 7. Report: what was recorded where, and what was deliberately not recorded
```

### 0 · Propose before writing

A new skill is a standing change to every future session, so it needs the user's approval the way a
logic change does. Bring the evidence: the cases it would carry, which existing skill each was checked
against, and why none of them fits (`templates/skill-proposal.md`). Extending an existing skill with a
lesson needs no proposal, only a report of what was added.

### 1-2 · Harvest and generalise

Each lesson needs a real case - the date, what happened, the measured number. A rule with no case is
easy to misapply and impossible to re-derive (S9). Strip project names from the rule; keep the case,
generalised enough to read outside the project. A lesson that only makes sense with project names in it
was a project lesson (S1).

### 3-4 · Write it in the house shape

[anatomy.md](reference/anatomy.md) has the layout, section order and conventions. The parts that matter
most: the description is written last and names every stage (S8); the most important content sits at
the top of `SKILL.md`, because compaction keeps only the first 5,000 tokens (S10); and the body states
standing rules, not one-time steps, because a loaded skill is not re-read (S12).

Where triggering is contested - several skills share vocabulary, or the skill keeps loading for the
wrong requests - offer `skill-creator`'s description optimization once the body is settled (below).

### 5-6 · Wire and verify

Run `python scripts/check_skill.py <skill-dir>` on the skill, and `python scripts/check_skill.py --root
<skills-root>` on its root. If the skill will be uploaded, also run `skill-creator`'s
`scripts/quick_validate.py`, the spec check its packager applies. Then confirm the skill is in the
session's skill listing under its bare name. A skill folder nested one level too deep, or shadowed by a
stale synced copy, passes every content check and never loads (S13, S14).

### 7 · Report

Say what was recorded where - each lesson's ID and file, each memory, each `CLAUDE.md` line - and what
you chose not to record and why. The user is the reviewer of a skill change; they cannot review what
they were not told about.

## Using skill-creator

Anthropic ships `skill-creator` (on claude.ai as `anthropic-skills:skill-creator`; in Claude Code as the
`skill-creator@claude-plugins-official` plugin). It measures skills; it does not decide where a lesson
belongs or keep a catalogue of them. Load it for these, and keep this skill for the rest:

| Need | Use | Notes |
|---|---|---|
| Does the skill improve outputs that can be checked in one turn? | `skill-creator` test cases, with-skill vs. baseline runs, grader, benchmark, review viewer | Right for transforms, fixed workflows, generators; wrong as the main judge of a long-horizon method skill (S17) |
| Does the description trigger on the right requests and not the near-misses? | `skill-creator` description optimization (`scripts/run_loop.py`) | Needs `claude -p`, so Claude Code only; run it after the body is settled; keep the result within 1,024 characters and naming every stage (S8, S18) |
| Is version B of a skill better than version A on one narrow question? | `skill-creator` blind comparison (`agents/comparator.md`) | A narrow comparison is how the "keep each level reviewable" lesson was found (S17) |
| Will it pass an upload? | `skill-creator` `scripts/quick_validate.py`; `scripts/package_skill.py` builds a `.skill` file | Complements `check_skill.py`, which checks install depth, synced copies and the lesson index |
| Should this be a skill at all, and where does each lesson go? | This skill | Recognising, the placement table, proposals |
| Lesson shape, IDs, index, red flags, provenance, splits, copies | This skill | The house shape and its maintenance |

Two conventions differ. `skill-creator` writes test cases into an `evals/` folder inside the skill and runs
into a `<name>-workspace/` folder beside it: put that workspace outside the skills root, or it is one more
folder there with no `SKILL.md`. Its writing advice - explain the why instead of capital-letter MUSTs, keep
the prompt lean, bundle a script that every test run rewrote - agrees with this skill's and is worth
applying when drafting.

## Standing rules

1. **Sort by audience first; extend before creating** (S1, S2).
2. **Every lesson carries its case** - date, what happened, the number (S9).
3. **Never renumber a lesson ID**; a moved lesson keeps its ID, and IDs are unique across sibling skills (S16).
4. **One editable source per skill**; every other copy is regenerated from it, never edited (S14).
5. **A skill change is finished when it loads**, not when the file is written (S13).
6. **Ask before creating, renaming, splitting or deleting a skill**; adding a lesson needs only a report.
7. **A rule that must hold every time goes in a hook or always-loaded instructions**, not only a skill (S6).

## Red flags - stop and check

| You notice | Check | Lesson |
|---|---|---|
| You are about to start a new skill | Grep every existing skill's index for the topic; would one new reference file do? | S2, S3 |
| A lesson mentions a project's file, class or registry | Is it a project lesson? Project skill + CLAUDE.md pointer | S1 |
| A lesson is a preference ("the user prefers...") | Memory, not a skill | S1 |
| You are writing a rule with no case | Find the case or drop the rule | S9 |
| You added a stage, phase or reference file | Does the description name it? | S8 |
| A rule must hold "always" or "before every X" | Hook or always-loaded instructions | S6 |
| `SKILL.md` is near 500 lines or 20,000 characters | Move detail to a reference file; keep the stance and rules at the top | S10 |
| Most of a skill's lessons would apply outside its trigger | Propose a split | S5 |
| You finished writing a skill | Is it in the listing, unprefixed? `check_skill.py --root` clean? | S13 |
| Two copies of a skill exist (personal, project, synced) | Which one loads? Which one did you edit? | S14 |
| You restructured a skill | Grep its README and tools for the old file names and counts | S15 |
| You are moving lessons between skills | Move verbatim, keep IDs, compare by script | S16 |
| You want evals for a long-horizon method skill | Will a single answer show the difference? If not, a narrow `skill-creator` comparison or the next real piece of work | S17 |
| A skill keeps loading for the wrong requests, or not for the right ones | `skill-creator` description optimization with near-miss negatives | S8 |
| The description is over 1,024 characters | It loads in Claude Code but fails a claude.ai upload | S18 |

## Script and templates

`scripts/check_skill.py` (stdlib-only Python 3.9+; run with `--help`): for one skill, checks frontmatter,
name, description length, `SKILL.md` size, relative links, Contents sections in long reference files, and
that every lesson heading is in the index and every index entry has a heading; with `--root`, finds skill
folders nested too deep, folders with no `SKILL.md`, reserved names, and personal skills shadowed by a
synced copy that differs.

| Template | Use |
|---|---|
| `templates/skill-proposal.md` | Asking to create, split or merge a skill |
| `templates/SKILL-skeleton.md` | A new skill's `SKILL.md`, in house section order |
| `templates/lesson.md` | One lesson: ID, title, rule, why, case |
| `templates/README-skeleton.md` | A new skill's README: install, layout, provenance, maintaining |
