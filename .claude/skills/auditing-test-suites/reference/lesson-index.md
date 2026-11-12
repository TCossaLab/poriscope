# Lesson index

Every lesson in this skill, by ID. Grep this file for a symptom or keyword, then open the linked file
and read the lesson in full - the case matters as much as the rule. IDs are unique across the sibling
skills; N, P and V lessons cited in this skill are in `planning-and-executing-changes`.

## Speed (T) - [speed.md](speed.md)

- **T1** Measure every phase of one full run before changing anything
- **T2** Cost that is not local is a leak upstream
- **T3** Count what is alive to find the leaker
- **T4** Know the amplifiers that turn a small leak into minutes
- **T5** Fix harness defects before parallelising
- **T6** Parallelise by whole files, sized from the machine
- **T7** The longest file sets the parallel floor
- **T8** Build deterministic work once and copy it; share only what nobody mutates
- **T9** Sometimes the slow thing is the product - fix the algorithm
- **T10** Do not shrink data whose size is calibrated
- **T11** A speed claim counts only from a full run

## Value (Q) - [value.md](value.md)

- **Q1** Judge a test by what it catches now, not why it was written
- **Q2** Drop only with evidence, and keep by default
- **Q3** A test that passes when broken is armed, not dropped, if nothing else catches the break
- **Q4** Know the shapes vacuous tests take
- **Q5** A test that freezes a bug is a finding
- **Q6** Redundancy concentrates in copies of base-class tests
- **Q7** A structural test must be replaced by a guard that can see the defect
- **Q8** Dead code shows up as tests nothing else needs; check reachability before removing it
- **Q9** Trace a fix's consequences to every output before landing it
- **Q10** Keep a golden that is the only catch, and give it a behaviour test

## Orchestrating (O) - [orchestrating.md](orchestrating.md)

- **O1** Slice by directory, with one shared brief on disk
- **O2** Each worker gets its own worktree and branch; the coordinator cherry-picks
- **O3** Cap the machine: agents run single files, the coordinator runs the suite
- **O4** Re-derive the claims that decide something
- **O5** Relay a finding to the agents whose slice it explains
- **O6** Give each agent its own scratch folder
- **O7** Check every merged file for corruption the edit tools introduced
- **O8** Gate every merged state, and reconcile the counts
- **O9** Deliver the audit as a page, and ask only the questions that are the owner's
