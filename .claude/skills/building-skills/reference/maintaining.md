# Maintaining, installing and evaluating skills

The question this file answers: *a skill exists - how do you change it without losing a lesson, and how
do you know the copy you changed is the one that loads?*

## Contents

- Adding a lesson
- S13 A skill is installed only once you have seen it load
- S14 One editable source per skill; copies drift
- S15 Restructuring a skill strands its tooling
- S16 Move lessons verbatim, keep their IDs, and check by script
- S17 Judge a long-horizon skill by the next real piece of work
- S18 Keep a skill uploadable if it will ever leave the machine

## Adding a lesson

1. Grep every sibling skill's `lesson-index.md` for the symptom. If a lesson already covers it, add the
   new case under the existing lesson (a second `*Case:*`) or sharpen its rule; do not add a near-duplicate.
2. Pick the reference file for the activity the lesson is used in, not the one it was learned in.
3. Take the next free ID in that file's series, checking every sibling skill's index (S16).
4. Write it in the lesson shape ([anatomy.md](anatomy.md)), add it to the file's Contents and to
   `lesson-index.md`.
5. If a symptom would tell the reader to look for it, add a red-flag row to `SKILL.md`. If it changes the
   procedure or must hold throughout, cite it there. If it adds a stage, update the description (S8).
6. Run `scripts/check_skill.py` on the skill, then report the ID and file to the user.

## S13 · A skill is installed only once you have seen it load

Claude Code discovers a skill only at `<skills-root>/<name>/SKILL.md`. One folder too deep, a missing or
unparseable frontmatter block (the `---` must be the file's first line), or a refused name, and the skill
silently does not load - while every check on its content still passes. After writing or moving one,
confirm it in the session's skill listing (or `/skills`) under its bare name, and run
`check_skill.py --root` on the root. Edits inside a watched skills directory reload live; a new top-level
skills directory needs `/reload-skills`, and a rename outside a watched directory needs a restart.

*Case:* since 2026-10-06 the personal `refactoring-codebases` has lived at
`~/.claude/skills/refactoring-codebases/refactoring-codebases/SKILL.md`. It never loaded. Sessions got
only `anthropic-skills:refactoring-codebases`, the older claude.ai-synced copy, which differs in seven
files from the one being maintained. The nesting also broke all fourteen of its relative links into
`planning-and-executing-changes`; copied to the right depth, it checked clean. Found on 2026-10-24 by
comparing the listing against the folders.

## S14 · One editable source per skill; copies drift

A skill can exist as a personal folder, a project folder, a claude.ai upload synced back into
`~/.claude/skills/synced/`, and a zip. Only one is the source; the rest are regenerated from it and never
edited. When two copies are both listed, the session may load either. After changing the source,
re-publish every copy that is meant to exist, or delete it. Never name a folder `synced`: Claude Code owns
that one.

*Case:* on 2026-10-24 the synced `planning-and-executing-changes` lacked `reference/discovery.md` and
differed from the personal source in fourteen files, and both were in the listing - the personal one bare,
the synced one as `anthropic-skills:planning-and-executing-changes`, with the older description that
does not trigger on design discussion.

## S15 · Restructuring a skill strands its tooling

A skill's README, build scripts, published guide pages and sibling skills all carry its file names,
lesson counts and layout. A split, merge or rename leaves them describing the old shape, and nothing
fails. Grep for the old names and counts after a restructure and update or retire each hit in the same
piece of work; if one cannot be updated now, say so in the README.

*Case:* after the 2026-09-24 split, the refactoring skill's lesson-index builder still expected all seven
reference files to hold lessons (it would have dropped the general section on its next run) and its
published field-manual page still described the pre-split skill. Both sat recorded as "behind" for a
month; on 2026-10-24 they were retired, and the index is now kept by hand and checked by `check_skill.py`.

## S16 · Move lessons verbatim, keep their IDs, and check by script

When lessons move between files or skills, move the text unchanged and keep each ID, so every citation
elsewhere still resolves; re-point only the cross-references the move itself broke. Then compare every
moved lesson body against the pre-move copy with a script - a by-eye check of eighty lessons misses the
one that lost a paragraph. IDs are unique across sibling skills, so a citation never needs a skill name.

*Case:* the split moved 84 lessons verbatim with their IDs; five cross-references were re-pointed at the
refactoring skill's templates and scripts, and a script compared every lesson body against the pre-split
copy. Both READMEs record that this was done and how.

## S17 · Judge a long-horizon skill by the next real piece of work

Single-prompt evals measure one answer to one message. A method skill used across hundreds of steps over
weeks changes outcomes by small per-step margins that compound, which no single answer shows. Use
`skill-creator`'s evals (or `claude plugin eval` for a plugin skill) where the output is checkable in one
turn - a file transform, a fixed workflow - and its description optimization for a trigger rate. For a
long-horizon skill, judge a change by how the next real piece of work goes; `skill-creator`'s blind
comparison can still answer one narrow question, such as which of two versions writes the more
reviewable plan. Run each eval in a fresh session: context left over from writing the skill hides its gaps.

*Case:* evals for the refactoring skill were tried and dropped on 2026-09-24 for this reason. A narrower
comparison was still useful: a plan written with the skill was judged stronger but criticised for density
against a plain plan about 60% of its length, which produced the lesson "keep each level reviewable".

## S18 · Keep a skill uploadable if it will ever leave the machine

Claude Code accepts descriptions up to 1,536 characters and frontmatter keys the Agent Skills spec does
not; a claude.ai or API upload rejects a description over 1,024 characters or any non-spec key. If the
skill will be uploaded or shared, keep it inside the spec, and check before uploading rather than after.

*Case:* on 2026-10-24 the personal `planning-and-executing-changes` description was 1,165 characters,
over the upload limit, so the newer copy could not replace the synced one (924 characters) without
trimming first. It was cut to 972 the same day by shortening only the "what it does" half; the
"Use whenever" triggers were kept word for word (S8).
