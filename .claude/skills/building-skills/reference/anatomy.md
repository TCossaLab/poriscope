# The anatomy of a house skill

The question this file answers: *what does a new skill, or a new part of one, look like, and why is each
piece there?*

## Contents

- The layout
- Frontmatter
- SKILL.md, in section order
- Reference files and lessons
- Lesson IDs and the index
- Templates and scripts
- The README
- S8 The description names every stage, or that stage never triggers
- S9 Every rule carries its case
- S10 Put what matters most at the top of SKILL.md
- S11 Generalise the rule, keep the case
- S12 Write standing rules, not one-time steps

## The layout

```
<skill-name>/
├── SKILL.md            # always read on load: stance, reference map, procedure, rules, red flags
├── README.md           # for humans: install, layout, provenance, maintaining (never loaded)
├── reference/          # one file per activity or phase, read on demand
│   ├── <activity>.md
│   └── lesson-index.md
├── templates/          # artefacts the procedure produces, as fill-in skeletons
└── scripts/            # deterministic helpers, executed rather than read
```

Location decides who sees it: `~/.claude/skills/<name>/` for every project on the machine,
`<repo>/.claude/skills/<name>/` for one repository (committed, so collaborators get it). `SKILL.md`
must sit exactly one level below the skills root (S13). The folder name is the skill's name.

A small project skill can be `SKILL.md` alone - one repository's architecture skill is 107 lines with no
reference files, because it is a map of one codebase, not a catalogue of lessons. Add the rest when the content
needs it, not to match the shape.

## Frontmatter

Use only `name` and `description` unless the skill needs a Claude Code feature. Those two (plus
`license`, `compatibility`, `metadata`, `allowed-tools`) are all the Agent Skills spec allows, and a
claude.ai upload fails hard on any other key. The spec also requires: `name` 1-64 characters of
lowercase letters, digits and single hyphens, matching the folder; `description` 1-1,024 characters.
Claude Code is looser (descriptions to 1,536), so a skill can work locally and still fail to upload (S18).

Claude Code-only keys worth knowing: `disable-model-invocation: true` (only `/name` loads it),
`user-invocable: false` (hidden from the menu), `paths` (auto-load only for matching files),
`context: fork` (run as a subagent - useless for a guidelines skill, which has no task), `allowed-tools`
(pre-approve a bundled script, e.g. `Bash(python ${CLAUDE_SKILL_DIR}/scripts/x.py *)`), and `hooks`.

## SKILL.md, in section order

1. **Title and a short opening**: what failure the skill prevents, in two or three sentences, and where
   its lessons came from.
2. **The stance**, in a handful of numbered sentences - the whole skill compressed, for a reader who
   reads nothing else. Each sentence cites its lesson IDs.
3. **Reference map**: a table of each reference file and *when* to read it. "Read when" is phrased as the
   situation the reader is in, not the file's topic.
4. **The procedure**: a copyable checklist (`- [ ] 0. ...`), then a short section per step citing lesson
   IDs. The reader copies the checklist into working notes and keeps it current.
5. **Standing rules**: the rules that hold throughout. If some must hold in every session, mark them
   (the general skill's "first five") so they can be copied into always-loaded instructions.
6. **Red flags**: a three-column table, *You notice | Check | Lesson*. The left column is a symptom the
   reader can observe in the moment, not a principle.
7. **Scripts and templates**: what each does, with "run with `--help`; execute rather than read".

Keep it under 500 lines and about 5,000 tokens (S10). A skill that builds on another says so near the
top ("Load X first") and lists only its own additions in each section.

## Reference files and lessons

One file per activity or phase, each opening with the question it answers, then a Contents list, then
its lessons. A lesson is:

```
## <ID> · <the rule, as a short imperative or claim>

<The rule and why, in one or two paragraphs. What to do, what it prevents, how to tell.>

*Case:* <what actually happened - the date where known, the measured number, the correction>.
```

A long file may group its lessons under `##` topic headings, with each lesson a `###` (the refactoring
skill's `execution.md` does). Some files start with a short procedural section ("Before calling anything done", "The discovery
steps") before the lessons; that is where a checklist for the activity goes. Files over 300 lines need
the Contents list; give it to every file anyway.

## Lesson IDs and the index

IDs are a letter series per activity plus a number (`P1`, `V12`, `S3`), unique across every skill that
links to another. An ID never changes once assigned - SKILL.md, red-flag tables, other skills, handoffs
and memory all cite it (S16). New lessons take the next free number in their series, so numbers within a
file need not be in order; series letters in use today are C, D, E, I, N, P, V, X (the two method skills)
and S (this one).

`reference/lesson-index.md` lists every lesson as `- **<ID>** <title>` under a heading per file, linked
to the file. It exists to be grepped by symptom, so titles are the rule's words. `check_skill.py` checks
that headings and index agree in both directions.

## Templates and scripts

A template is the skeleton of an artefact the procedure tells the reader to produce (a plan, a handoff, a
decision entry, a proposal) - placeholders in `<angle brackets>`, no prose about how to fill it beyond what
the placeholder says.

A script exists when a check is deterministic and easy to get wrong by eye. House conventions:
stdlib-only Python 3.9+, `#!/usr/bin/env python3`, a module docstring that opens with **why it exists**
(the failure it catches) before usage, `argparse` with `--help`, and a non-zero exit when the check
fails. SKILL.md tells the reader to execute it rather than read it; read one only to adapt it. Reference
a bundled script from SKILL.md by its path relative to the skill (`scripts/x.py`), or as
`${CLAUDE_SKILL_DIR}/scripts/x.py` where it must resolve from any working directory.

## The README

Not loaded by the model; it is for whoever maintains or installs the skill. Sections: **Install** (each
target, and which sibling skills must sit beside it), **Layout** (a table), **Provenance** (what work it
was distilled from, when, and any split or merge with how it was checked), **Maintaining it** (where a
new lesson goes, the ID rule, the size limit, what tooling must be updated with it), and, where relevant,
**Why there are no evals** (S17). `templates/README-skeleton.md` has the shape.

## S8 · The description names every stage, or that stage never triggers

The description is the only text in every session; the model decides from it alone whether to load the
skill. Name what the skill does *and* each situation that should load it, in the words a user would use,
and include situations where the user would not name the skill ("even for a one-site fix", "even if they
never say refactor"). When a skill gains a stage, the description must gain it too. Write the
description last, and put the key use case first, since a long one may be cut.

*Case:* when the discovery stage was added to `planning-and-executing-changes`, its description gained
"starting from the first design discussion, even when no plan or code is wanted yet" and "Use whenever
you are about to discuss a design or a rough feature request". The older synced copy, without that
stage, has neither: a design discussion would not have loaded it.

## S9 · Every rule carries its case

A rule without the evidence that produced it is easy to misapply and impossible to re-derive: the reader
cannot tell where its edges are, or whether it still holds. Keep the case - what happened, when, the
measured number - directly under the rule. If no case can be found, the rule was a guess; drop it or mark
it as one.

*Case:* the refactoring skill's provenance states it directly: project names were removed from the rules,
"the cases are kept, generalised, because a rule without the evidence that produced it is easy to
misapply."

## S10 · Put what matters most at the top of SKILL.md

After compaction, Claude Code re-attaches each invoked skill's first 5,000 tokens only, within a 25,000
token budget shared by all invoked skills, most recent first. Whatever is below that line is gone for the
rest of the session unless the skill is invoked again. Lead with the stance and the rules; put tables of
scripts and long procedure detail last or in reference files. Measure: about 4 characters per token, so
20,000 characters is the line.

*Case:* on 2026-10-24 `planning-and-executing-changes/SKILL.md` was 15,525 characters (about 3,900
tokens, all of it survives) and `refactoring-codebases/SKILL.md` 18,801 (about 4,700 - its red flags and
scripts tables are the part nearest the cut).

## S11 · Generalise the rule, keep the case

A general skill's rules name no project, file or class; its cases may, generalised enough to read
outside the project ("a desktop application with a plugin system", "an export flow waited for two of the
three tables"). Generalising the case further than that strips the detail that makes it evidence.

*Case:* both method skills open with the same sentence of provenance - "distilled from a three-week,
nine-step refactor of a desktop application with a plugin system (about 2,900 tests growing to 4,200)" -
and then cite cases at that level of detail throughout, with no project module names in any rule.

## S12 · Write standing rules, not one-time steps

A loaded skill stays in the conversation and is not re-read, so an instruction phrased as a single step
("run the tests") is followed once and then forgotten. Phrase what must persist as a rule over the whole
task ("run the full suite before every commit"), and make the procedure a checklist the reader copies into
notes and keeps current, so its state survives in the conversation rather than in the reader's attention.

*Case:* both method skills say "copy this checklist into your working notes and keep it current" rather
than listing steps to follow once; the Claude Code documentation gives the same advice for a skill whose
guidance stops being followed after the first response.
