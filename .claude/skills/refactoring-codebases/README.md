# refactoring-codebases

An Agent Skill for planning and executing large refactors end to end. It builds on
`planning-and-executing-changes`, which holds the general lessons (84 of the original 115); this
skill keeps the 31 that were specific to refactoring (33 since E27-E28 were added from the
2.0.0 plan's prose on 2026-09-27), plus the procedure, templates and instruments
for moving code while preserving behaviour.

**Install both skills side by side** - this one links into the general skill by relative path
(`../planning-and-executing-changes/...`).

## Install

- **Claude Code (personal):** copy this folder to `~/.claude/skills/refactoring-codebases/`.
- **Claude Code (project):** copy it to `<repo>/.claude/skills/refactoring-codebases/`.
- **claude.ai:** zip the folder (the zip must contain the `refactoring-codebases/` directory)
  and upload it under Settings > Features > Skills.
- **API:** upload through the Skills API (`/v1/skills`).

## Layout

| Path | What |
|---|---|
| `SKILL.md` | The procedure, standing rules, red flags, and a map to everything else |
| `reference/` | One file per phase, each lesson with the case that produced it; `lesson-index.md` lists all by ID |
| `templates/` | Plan, commit series, manual-pass map, decision entry, exit review, handoff |
| `scripts/` | Stdlib-only Python instruments (run with `--help`) |

## Provenance

Distilled from the Poriscope 2.0.0 refactor (September 2026): its plan, its execution record and
its 97 method rules, plus the standing corrections its maintainer gave along the way. Project
names were removed from the rules; the cases are kept, generalised, because a rule without the
evidence that produced it is easy to misapply.

## Why there are no evals

Single-prompt evals were tried and dropped (2026-09-24; runs archived in
`refactoring-codebases-workspace/`). They measure one answer to one message, and a refactor is
hundreds of sequential plan, review and execute steps over weeks. A modest per-step difference, such
as catching the trap in 9 of 10 steps instead of 7 of 10, compounds across that sequence into the
difference between a refactor that lands and one that does not, and no single-answer check can see
that. Judge changes to this skill by how the next real refactor goes.

## Maintaining it

A lesson that applies beyond refactoring goes in `planning-and-executing-changes`, not here. Add a
refactor-specific lesson to the reference file for its phase, in the same shape (rule, why, case),
under the next free ID - IDs are unique across both skills. Keep `SKILL.md` under 500 lines.

**The build tools are behind the split (2026-09-24).** `tools/build_lesson_index.py` in the skill
source folder still expects all seven reference files to hold lessons and would drop the general
section from `lesson-index.md`; `tools/build_guide.py` and the field manual artifact
(https://claude.ai/artifact/1jHTUzqZUo5UqA7Vbk1YvR) still describe the pre-split skill. Update them
to read both skills before regenerating either.
