# auditing-test-suites

The method for auditing a whole test suite for speed and for value: finding where a run's time goes,
tracing it to the leaks that cause it, parallelising safely, and judging every test by what it would
catch today, with mutation evidence for every change. 30 lessons in three series - T (speed), Q (value)
and O (orchestrating the work across parallel agents) - with two scripts and two templates. It builds
on `planning-and-executing-changes`, whose testing and verification lessons it cites by ID.

## Install

- **Claude Code (personal):** copy this folder to `~/.claude/skills/auditing-test-suites/` - `SKILL.md`
  exactly one level below `skills/`. `planning-and-executing-changes` must sit beside it: this skill
  tells the reader to load it first and cites its N, P and V lessons.
- **Claude Code (project):** copy it to `<repo>/.claude/skills/auditing-test-suites/`.
- **claude.ai:** zip the folder (the zip must contain the `auditing-test-suites/` directory) and upload it
  under Settings > Features > Skills. The description must be <= 1,024 characters.

Then confirm it appears in the skill listing under its bare name.

## Layout

| Path | What |
|---|---|
| `SKILL.md` | When to run it, the stance, the procedure, standing rules, red flags, scripts and templates |
| `reference/speed.md` | T1-T11: measuring a run, leaks and their amplifiers, harness fixes, parallel workers, repeated work |
| `reference/value.md` | Q1-Q10: the verdicts and their evidence, vacuous shapes, frozen bugs, redundancy, structural tests, dead code |
| `reference/orchestrating.md` | O1-O9: slicing, briefs, worktrees and cherry-picks, resource limits, merging, gating, the findings page |
| `reference/lesson-index.md` | Every lesson by ID |
| `templates/worker-brief.md` | The shared brief each audit or cleanup worker reads |
| `templates/verdict-table.md` | One row per candidate test, plus frozen bugs, judgement calls and disproved suspicions |
| `scripts/durations_report.py` | Phase, directory and file totals from a `--durations=0` log; full-run against alone |
| `scripts/scan_files.py` | Control bytes and conflict markers in files or a git range |

## Provenance

Distilled on 2026-11-12 from one audit of a desktop application's suite (PySide6 and pytest, about 5,850
tests, Windows and Linux CI). The speed pass found the run's time in setup and teardown rather than test
bodies, traced it with a heap census to an integration harness that hid its windows instead of deleting
them, fixed that at the root of the test tree, and then parallelised by file with workers sized from
each machine's cores and memory: 1,650 s serial became about 400 s serial and about 100 s parallel. The
value pass ran seven read-only audit agents over every test file, merged their findings into one page
the owner ruled on, and five cleanup workers carried it out on their own branches: about 440 tests
removed, about 30 armed, 14 gaps covered, two frozen bugs fixed, dead code removed, and the duplication
ratchet widened after a worker found the hole the dropped tests had covered. The general lesson behind
the leak became N17 in `planning-and-executing-changes`.

## Maintaining it

A new lesson goes in the reference file for its activity, takes the next free number in that series (T,
Q or O), and is added to `reference/lesson-index.md`; IDs never change and are unique across the sibling
skills. Keep `SKILL.md` under 500 lines and about 20,000 characters, and run
`python ../building-skills/scripts/check_skill.py .` from this folder after any change. A lesson that
holds for any change, not only an audit, belongs in `planning-and-executing-changes` instead.
