# building-skills

An Agent Skill for recognising when a lesson deserves to be written down, deciding where it belongs
(memory, `CLAUDE.md`, a project skill, an existing skill, or a new one), and building, maintaining and
installing skills in the shape `planning-and-executing-changes`, `refactoring-codebases` and a
repository architecture skill were built in. Eighteen lessons, series S. It defers to Anthropic's
`skill-creator` for evals, benchmarks, description tuning and packaging.

## Install

- **Project (the tracked source):** this folder lives at `<repo>/.claude/skills/building-skills/` and is
  committed, so version control keeps it current. Edit this copy. It names the method skills but does not
  link into them, so it works alone.
- **Personal:** copy the folder to `~/.claude/skills/building-skills/` only on a machine with no project
  copy - `SKILL.md` exactly one level below `skills/`. A personal skill wins the bare name over a project
  skill, so a personal copy beside a repo copy silently shadows the tracked one.
- **claude.ai:** zip the folder (the zip must contain `building-skills/`) and upload it under
  Settings > Features > Skills. The description is inside the 1,024-character spec limit. Claude Code
  downloads the upload into `~/.claude/skills/synced/` and loads it as `anthropic-skills:building-skills`;
  that download is never edited and never uploaded back, so re-upload from this folder after a change.

Then confirm it appears in the skill listing as `building-skills`.

## Layout

| Path | What |
|---|---|
| `SKILL.md` | Stance, when a skill is needed and where a lesson goes, the build procedure, standing rules, red flags |
| `reference/` | `recognizing.md` (S1-S7), `anatomy.md` (house shape, S8-S12), `maintaining.md` (S13-S18), `lesson-index.md` |
| `templates/` | Skill proposal, SKILL.md skeleton, lesson, README skeleton |
| `scripts/check_skill.py` | Checks one skill's frontmatter, size, links and index; with `--root`, nesting, reserved names and drifted synced copies |

## Provenance

Written on 2026-10-24 from the three existing house skills, their READMEs and provenance notes, the
user's memory on recording lessons after first-of-a-kind work, the Claude Code skills documentation
(https://code.claude.com/docs/en/skills) and the Agent Skills specification
(https://agentskills.io/specification). The cases are from building and maintaining those skills in
September and October 2026; S13, S14 and S18 come from defects found while writing this one.

## Maintaining it

A new lesson takes the next free S number and goes in the file for the activity it is used in; follow
`reference/maintaining.md`'s "Adding a lesson", including this skill's own red-flag table. Lessons about
the method of any change belong in `planning-and-executing-changes`, not here. Keep `SKILL.md` under 500
lines and 20,000 characters, and run `python scripts/check_skill.py .` after every change. Judge changes by
whether the next lesson lands in the right place, not by single-prompt evals.
