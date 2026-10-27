# planning-and-executing-changes

An Agent Skill holding the general method for planning, executing and verifying software changes,
with nearly a hundred field-tested lessons about how plans, handoffs, tests, gates and green CI mislead.
It is the default skill for most planning and execution work; `refactoring-codebases` builds on it.

## Install

- **Project (the tracked source):** this folder lives at `<repo>/.claude/skills/planning-and-executing-changes/`
  and is committed, so version control keeps it current. Edit this copy. `refactoring-codebases` must
  sit beside it: that skill links into this one by relative path (`../planning-and-executing-changes/...`).
- **Personal:** copy the folder to `~/.claude/skills/planning-and-executing-changes/` only on a machine
  with no project copy. A personal skill wins the bare name over a project skill, so a personal copy
  beside a repo copy silently shadows the tracked one.
- **claude.ai:** zip the folder (the zip must contain the `planning-and-executing-changes/` directory)
  and upload it under Settings > Features > Skills. Upload both skills. Claude Code downloads the
  upload into `~/.claude/skills/synced/` and loads it as `anthropic-skills:planning-and-executing-changes`;
  that download is never edited and never uploaded back, so re-upload from this folder after a change.

## Layout

| Path | What |
|---|---|
| `SKILL.md` | The stance, the procedure, standing rules (the first five hold in every session), red flags, and a map to everything else |
| `reference/` | One file per activity, each lesson with the case that produced it; `lesson-index.md` lists all by ID |
| `templates/` | Design document, restatement, ruling (discovery); change plan, manual-pass map, decision entry, handoff |
| `scripts/` | Stdlib-only Python helpers (run with `--help`) |

## Provenance

Split out of `refactoring-codebases` on 2026-09-24. Every lesson here was moved verbatim, keeping its
ID, apart from five cross-references re-pointed at the refactoring skill's templates and scripts; a
script compared every lesson body against the pre-split copy. The cases come from the Poriscope 2.0.0
refactor (September 2026) and are generalised; the rules do not depend on refactoring.

## Maintaining it

Add a general lesson to the reference file for its activity, in the same shape (rule, why, case), under
the next free ID in its letter series - IDs are unique across this skill and `refactoring-codebases`,
so check both indexes. Then regenerate both lesson indexes (the split's `build_indexes.py`, or by hand).
If a lesson must hold in every session, add it to the standing rules' first five and copy it into the
repository instructions that need it. Keep `SKILL.md` under 500 lines, and the description within the
1,024 characters a claude.ai upload accepts (972 on 2026-10-24).

As with the refactoring skill, judge changes by how the next real piece of long work goes, not by
single-prompt evals.
