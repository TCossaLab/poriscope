# porting-applications

The method for porting an existing application, script or tool into a host codebase as native features:
understanding the original, mapping it onto the host's machinery, and proving the port computes what the
original did. Eleven lessons (A1-A11), each with the case that produced it. It builds on
`planning-and-executing-changes`, which holds the general lessons on discovery, plans, tests, gates and
verification; this skill adds only what having an original to port changes.

## Install

- **Claude Code (project):** this folder sits at `<repo>/.claude/skills/porting-applications/`, beside
  `planning-and-executing-changes`, `refactoring-codebases` and `building-skills`. Its links into
  `planning-and-executing-changes` are by lesson ID, so it works without that skill but loses the
  lessons it cites.
- **Claude Code (personal):** copy it to `~/.claude/skills/porting-applications/` - `SKILL.md` exactly one
  level below `skills/`. Do not keep a personal copy beside a project copy: the personal one wins the bare
  name.
- **claude.ai:** zip the folder (the zip must contain the `porting-applications/` directory) and upload it
  under Settings > Features > Skills. The description must be <= 1,024 characters.

Then confirm it appears in the skill listing under its bare name.

## Layout

| Path | What |
|---|---|
| `SKILL.md` | Stance, reference map, procedure, standing rules, red flags |
| `reference/understanding-the-original.md` | A1-A4: entry points, data formats, running the original, defects |
| `reference/mapping-onto-the-host.md` | A5-A8: native machinery, equivalence, units, defaults that refuse input |
| `reference/proving-equivalence.md` | A9-A11: goldens from the original, restoring probes, real-data comparison |
| `reference/lesson-index.md` | Every lesson by ID |
| `templates/capability-map.md` | The step-2 mapping: capabilities, defects, unread data, format checks |

## Provenance

Distilled on 2026-11-11 from porting a lab's conditioning-analysis scripts (three scripts, 1,136 lines,
untested and unversioned) into a desktop analysis application with a plugin system: a new data-plugin
family, a new analysis tab, a new binary reader and new options on an existing spectrum view. The design
document's corrections log and its notes kept for this skill were the sources; every case was re-checked
against the rulings register, the code and the measured runs before it was written in. Project names were
removed from the rules; the cases are kept, generalised.

## Maintaining it

A new lesson takes the next free number in the A series (A12 onward) and goes in the reference file for
the activity it is used in. IDs are unique across the sibling skills: check every sibling's
`lesson-index.md` before assigning one, and never renumber. A lesson that applies to any change, not
only a port, belongs in `planning-and-executing-changes` instead. Keep `SKILL.md` under 500 lines and
the description under 1,024 characters. Run `building-skills/scripts/check_skill.py` on this folder after
any change.

## Why there are no evals

A port plays out over days of discovery, rulings, commits and comparisons; its lessons change outcomes a
little at each of many steps, which no single-prompt eval shows. Judge a change to this skill by how the
next real port goes.
