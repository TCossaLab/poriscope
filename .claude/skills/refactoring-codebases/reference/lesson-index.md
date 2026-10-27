# Lesson index

Every lesson this skill relies on, by ID. Grep this file for a symptom or keyword, then open
the linked file and read the lesson in full - the case matters as much as the rule.
IDs are unique across this skill and planning-and-executing-changes.

# In this skill - specific to refactoring

## Planning (P) - [planning.md](planning.md)

- **P5** Count the callers before believing a move is cheap
- **P6** Ask which other step already owns those callers
- **P10** Before moving state to a layer, check that the layer reads it
- **P11** Take a duplication number apart before planning against it
- **P12** Before deleting duplication, ask whether another gate is why it exists
- **P13** A pending deprecation changes the right answer to a duplication finding
- **P16** Aim a step at the metric it can actually move, and check that first

## Safety net (N) - [safety-net.md](safety-net.md)

- **N1** Scope the net by what moves, not by what looks thin - and derive the list
- **N13** An expected golden diff needs a stated rule

## Instruments (I) - [instruments.md](instruments.md)

- **I4** Make instruments take text, and simulate before choosing commit boundaries
- **I7** A derived gate has no baseline - record the invariant, and zero is success
- **I8** An instrument that names what you moved needs the same edit in the same commit
- **I9** Check whether the instrument can still see the code you are about to move
- **I17** Separate refactor-only gates from result gates at build time

## Execution (E) - [execution.md](execution.md)

- **E1** "The same code twice" is the claim a promotion rests on - diff it
- **E2** A numeric difference between near-copies may be the domain's rule, not drift
- **E7** Interface width, not hierarchy depth, is the expensive axis on a published base
- **E8** A promoted method reaches shared state through an accessor, not a second stored reference
- **E9** For a layering rule, "who consumes this?" beats "where did it come from?"
- **E10** A test reaching a shared method through an unrelated subclass hides a mis-homing
- **E11** A promotion moves the tests' patch targets
- **E12** After a signature change, grep all tests for the name
- **E14** Convert the chain, not its links
- **E15** The unit of a move is the state it writes, not the method it lives in
- **E18** When a failure's explanation moves layers, clean up what the old layer still says
- **E19** A converted call can leave a live-looking dead slot behind
- **E27** A call that interleaves a question becomes two requests
- **E28** Tests passing untouched across a move are the evidence

## Exit and cleanup (X) - [exit-and-cleanup.md](exit-and-cleanup.md)

- **X3** A breaking-change inventory must be derived, and honest in both directions
- **X4** Code outlives the plan, so it must not cite the plan
- **X5** Deletion residue is found by diffing name sets, not by reading
- **X6** Retire the tooling that guarded the refactor
- **X7** Regroup the changelog last, and verify the mapping by script

# In planning-and-executing-changes - general lessons this skill builds on

## Planning (P) - [planning.md](../../planning-and-executing-changes/reference/planning.md)

- **P20** Detail just in time
- **P21** Findings flow upward
- **P22** Approval at one level is not approval of the level below
- **P23** A plan is only as good as its review, so keep each level reviewable
- **P1** A finding is a measurement with a date on it
- **P2** A number that disagrees with itself was never checked
- **P3** Unverifiable is not the same as wrong
- **P4** A recorded blocker is a claim like any other
- **P7** "Pure" is a claim about the whole body, not about the signature
- **P8** A limitation you inferred is a claim - measure it
- **P9** The plan's account of a defect is a hypothesis
- **P14** A step can be wrong while every one of its numbers is right
- **P15** Check what a category contains before executing the verb
- **P17** An exit criterion has to survive the step's other constraints
- **P18** A right answer reached by a wrong mechanism points at the wrong fix
- **P19** Pull open design questions forward

## Testing (N) - [testing.md](../../planning-and-executing-changes/reference/testing.md)

- **N3** Enter, set up and tear down through the application's own doors
- **N2** Executed is not pinned, and mentioned is not covered
- **N4** Prove every pin discriminates, and confirm the mutation happened
- **N5** Stub a collaborator the way it really behaves
- **N6** A stub standing in for a collaborator hides that the collaborator is untested
- **N7** New runtime mechanisms are written test-first, against the invariant
- **N8** A wait must be satisfied only by the finished state, and only by this run's
- **N9** Choose the deterministic path when the net has a choice
- **N10** Pick awkward fixture values
- **N11** Never keep a self-generated golden across a move
- **N12** Structure-reading tests should announce their own obsolescence
- **N14** Assert the net is armed
- **N15** Never reshape production code to keep a test passing

## Measurement (I) - [measurement.md](../../planning-and-executing-changes/reference/measurement.md)

- **I1** The definition is the number
- **I2** A baseline is only a baseline if its instrument is committed
- **I3** Ratchet on exact match, in both directions, with a second number
- **I5** Check the gate can actually ship
- **I6** Scope a shared gate to what your team controls
- **I10** Write down what each instrument is blind to
- **I11** Some legitimate work moves no metric, or moves it the wrong way
- **I12** A heuristic moving either way is a question, not a verdict
- **I13** A gate that forces the code to lie has stopped measuring what it is named for
- **I14** Changing a metric's definition kills every figure recorded under the old one
- **I15** A gate that runs on one path is never asked if your work takes another
- **I16** A cached artefact needs a staleness check

## Execution (E) - [execution.md](../../planning-and-executing-changes/reference/execution.md)

- **E3** Measure a "no-op" before promoting it, and read the comment as a claim
- **E4** A mechanism that reads as a contract may not be one
- **E5** Showing a mechanism has an effect is not showing the effect is wanted
- **E6** Measure the cost of the design you are about to reject
- **E13** Grep classifies; only running tells you which class
- **E16** Do not mutate shared state before asking a question that can be refused
- **E17** Deferred execution runs its guards on whoever advances it
- **E20** Check a path can produce its output before improving what it shows
- **E21** Anchor deletions on blocks, not lines
- **E22** A splice anchored on its neighbours deletes whatever sits between them
- **E23** An auto-fixer reconciles around damage and hides it
- **E24** Keep each fix minimal, and close it where you found it
- **E25** Fix the contract at the call sites rather than guessing at runtime

## Verification (V) - [verification.md](../../planning-and-executing-changes/reference/verification.md)

- **V1** Run the whole suite, in natural order, before every commit
- **V2** Green means you read this run's summary line
- **V3** Every automated gate can pass over an application that cannot start
- **V4** Plan the manual pass before the branch, and make it performable
- **V5** Assert on the surface the user reads, not the call that writes to it
- **V6** For persisted state, read the file, not the object
- **V7** Attribute a reported defect to a revision, not to the change you just made
- **V8** A defect report needs a reachable input, not just a suspicious shape
- **V9** "Not reproducible" is a result; a quiet probe measures the wrong program
- **V10** A probe that boots the app writes to the user's real data
- **V11** Build the tool, then use it for real work
- **V12** "Landed" is a claim about behaviour, so a text match cannot settle it
- **V13** Separate environment artefacts from measurements
- **V14** Bisect, don't argue

## Finishing (X) - [finishing.md](../../planning-and-executing-changes/reference/finishing.md)

- **X1** A review that only files findings has not finished
- **X2** A sweep is finished only where its instrument looked
- **X8** A flake the gate found is fixed, not re-run
- **X9** Suite time grows with coverage; measure before calling it a regression

## Collaboration and records (C) - [collaboration-and-records.md](../../planning-and-executing-changes/reference/collaboration-and-records.md)

- **C1** Logic changes need an approved plan
- **C2** Ownership: ask first, with measurements, and state the exit
- **C3** One branch per piece of work
- **C4** Keep one plan, in the repository and in a shareable page, telling the same story
- **C5** Write the handoff so a cold start costs nothing
- **C6** Put each kind of information in exactly one place
- **C7** Keep the wrong turns
- **C8** Replace documentation for a removed mechanism; do not delete it
- **C9** Documentation coverage is a judgement about readers
- **C10** Treat delegated work as claims, and attribute authorship explicitly
- **C11** Stay out of the repository while someone else is driving it
- **C12** Report outcomes faithfully, including the damage
