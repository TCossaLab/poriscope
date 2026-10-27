# <skill-name>

<One paragraph: what the skill holds, how many lessons, and how it relates to sibling skills.>

## Install

- **Claude Code (personal):** copy this folder to `~/.claude/skills/<skill-name>/` - `SKILL.md` exactly
  one level below `skills/`. <Sibling skills that must sit beside it, and why.>
- **Claude Code (project):** copy it to `<repo>/.claude/skills/<skill-name>/`.
- **claude.ai:** zip the folder (the zip must contain the `<skill-name>/` directory) and upload it under
  Settings > Features > Skills. The description must be <= 1,024 characters.

Then confirm it appears in the skill listing under its bare name.

## Layout

| Path | What |
|---|---|
| `SKILL.md` | <stance, procedure, standing rules, red flags, map> |
| `reference/` | <one file per activity; `lesson-index.md` lists all by ID> |
| `templates/` | <...> |
| `scripts/` | <stdlib-only helpers (run with `--help`)> |

## Provenance

<The work it was distilled from, with dates; any split or merge, and how the move was checked.>

## Maintaining it

<Where a new lesson goes; the ID series and the uniqueness rule; the size limit; tooling, copies or
published pages that must be updated with it.>
