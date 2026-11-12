---
name: porting-applications
description: Ports an existing application, script or tool into a host codebase as native features rather than a transcription - inventorying the original's capabilities per entry point, deriving its data formats from real sample files, running it headlessly to time it and capture its outputs, mapping each capability onto the host's own machinery with numeric equivalence checks, ruling on the original's defects, and proving the port with goldens from the original, a mutation probe per fixed defect and a value-for-value comparison on real data. Builds on planning-and-executing-changes. Use whenever the user asks to port, migrate, bring over, integrate, absorb, re-implement or replace an existing app, lab script, notebook, GUI or tool in this codebase or another, or to check a port against its original - even if they call it "adding a feature like X" or "making X a plugin".
---

# Porting applications

A port fails in two directions. Transcribe the original and the host gains a second program living
inside it, with its own file handling, caches and conventions, and the original's defects carried over
unexamined. Re-imagine it freely and nobody can say whether the port computes what the original did.
This skill is the method for landing between the two: the original's inputs and outputs, carried onto
the host's own machinery, with the agreement measured rather than asserted.

It was distilled from porting a lab's conditioning-analysis scripts (a core script, its GUI wrapper and a
single-file viewer: 1,136 lines of untested Python reading 16-channel instrument recordings) into a desktop analysis application with a plugin
system, in November 2026: a new data-plugin family, a new analysis tab, a new file reader and an option
on an existing view, about 5,800 tests at the end. Every lesson carries the case that produced it.

**Load `planning-and-executing-changes` first.** Discovery, rulings, plans, tests, gates and
verification are its subject; this skill adds what is specific to having an original to port. Lesson IDs
are unique across the sibling skills; an ID cited here that is not in this skill's reference files is in
the general one.

## The stance, in five sentences

1. **Port the inputs and outputs, not the program**: each capability is mapped onto machinery the host
   already has, and anything the host would have to grow is a ruling (A5, A8).
2. **The original is an instrument before it is a specification** - run it, time it and capture its
   outputs before designing anything (A3, A9).
3. **The sample data is evidence the code is not** - derive formats from the files, and expect the files to
   contradict the code and their own names (A2).
4. **"The host already does this" is a numeric claim** until the two agree on the same input (A6, A7).
5. **Every defect in the original is a ruling, and every fixed one is proved** by putting the original's
   behaviour back and watching a test fail (A4, A10).

## Reference files - read the one for what you are doing

| File | Read when |
|---|---|
| [reference/understanding-the-original.md](reference/understanding-the-original.md) | Reading the original, its entry points and its sample data; listing its capabilities and defects; before any design |
| [reference/mapping-onto-the-host.md](reference/mapping-onto-the-host.md) | Deciding where each capability lands in the host; a host feature "already does" part of it; units, defaults and conventions differ |
| [reference/proving-equivalence.md](reference/proving-equivalence.md) | Building goldens from the original, testing fixed defects, the final comparison on real data |
| [reference/lesson-index.md](reference/lesson-index.md) | Looking up a lesson by ID or symptom (grep it) |

## The procedure

This sits inside the general skill's procedure: steps 0-2 here are its discovery and planning, step 3 its
tests, step 4 its verification. Copy this checklist into your working notes and keep it current:

```
Port progress:
- [ ] 0. Inventory: capabilities per entry point; data formats from the sample files; what the data holds that the original never reads (A1, A2)
- [ ] 1. Run the original headlessly: time it on real data; build the harness that will capture goldens (A3)
- [ ] 2. Map: each capability onto host machinery (templates/capability-map.md); equivalence measured, not asserted; defects and new machinery as rulings (A4-A8)
- [ ] 3. Goldens: deterministic generator in the repo, the original run on it, tolerance stated; one mutation probe per fixed defect (A9, A10)
- [ ] 4. Real data: every value, port against original, from a clean copy; timings warm and cold (A11)
```

### 0 · Inventory

- List capabilities **per entry point** - a script, its GUI wrapper and its notebook each add their own (A1).
- Derive each format from the sample files: size divided by channels and sample width is a frame count,
  to be checked against the code and the file names (A2).
- List what the sample data holds that the original never reads, and ask whether it is in scope (A4).

### 1 · Run the original

- Import it headlessly (non-interactive plotting backend, module constants set from the script) and call
  its functions on the real data: the run time decides whether the port needs background work, and the
  harness is reused for goldens (A3).

### 2 · Map

- Fill in `templates/capability-map.md`: each capability, its host mechanism, the measured equivalence,
  and the ruling it needs (A5).
- Every "the host already does this" gets the same input through both and a number compared (A6); every
  unit crosses the host's contract explicitly (A7).
- Each defect in the original, and each default that would refuse the users' real input, is listed as a
  ruling with options - not decided in the plan (A4, A8).

### 3 · Goldens

- A deterministic generator in the repository, the original run on it once per setting that matters,
  saved; the port compared at a stated tolerance with the reason for it (A9).
- For each defect the port fixes, a probe that puts the original's behaviour back must fail a test (A10).

### 4 · Real data

- Every value, not a sample, from a clean copy whose import path you have printed; time both programs
  more than once and separate the environment from the code (A11, V13).

## Standing rules

1. **Map onto the host's machinery; anything new in the host is a ruling for the user** (A5).
2. **No equivalence claim without the same input through both and a number** (A6).
3. **The original's defects are listed and ruled on, never silently fixed or silently kept** (A4).
4. **A fixed defect is proved by a probe that restores it** (A10).

## Red flags - stop and check

| You notice | Check | Lesson |
|---|---|---|
| Your scope options name the original's screens or functions as things to build | Rewrite them as inputs and outputs on host machinery | A5 |
| You read only the core script, not the wrapper or notebook around it | Inventory every entry point | A1 |
| A format comes from the reader code alone | Divide a sample file's size; compare with the name and the code | A2 |
| A file's size disagrees with its name, or with its siblings | It is a question for the data's owner, and possibly a defect in past results | A2 |
| You are about to design a background worker, or decide not to | Time the original on real data first | A3 |
| "The host already does X" is in your design | Same input through both; compare the numbers | A6 |
| The original stores or reports in different units | Write the conversion and where the agreement stops being exact | A7 |
| Your recommended default refuses some of the users' files | Ask how the files arise before refusing them | A8 |
| A golden was produced by the port itself | It pins nothing; capture it from the original | A9, N11 |
| A defect is "fixed" with no test that fails on the old behaviour | Write the restoring probe | A10 |
| The final comparison was a sample of channels or files | Compare every value | A11 |
| The port is much slower or faster than the original | Repeat warm; check what else the machine was doing | A11, V13 |

## Templates

| Template | Use |
|---|---|
| `templates/capability-map.md` | The mapping table from step 2: capability, entry point, host mechanism, equivalence, ruling |
