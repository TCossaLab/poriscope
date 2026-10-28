# Lesson index

Every lesson in this skill, by ID. Grep this file for a symptom or keyword, then open
the linked file and read the lesson in full - the case matters as much as the rule.
The refactoring-codebases skill adds refactor-specific lessons under the same ID scheme;
IDs are unique across the two skills.

## Discovery (D) - [discovery.md](discovery.md)

- **D1** Restate a rough note before designing from it
- **D2** Search the decision log and the work queue before designing
- **D3** A question in the request is the requester's until they answer it
- **D4** Label every claim about the system "today" or "planned"
- **D5** Check both halves of a lifecycle verb or a persisted file
- **D6** On a failure path, what the user can do next is a ruling
- **D7** "Never automatic" is not "never offered"
- **D8** Write use cases from the request, before the plan

## Planning (P) - [planning.md](planning.md)

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

## Testing (N) - [testing.md](testing.md)

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

## Measurement (I) - [measurement.md](measurement.md)

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

## Execution (E) - [execution.md](execution.md)

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
- **E26** An atomic replace can be refused on Windows; retry it, bounded
- **E29** One value, many readers: map the pipeline from input to outcome at every entry point
- **E30** A grep hit is a line, not a function; read the whole body before saying what it does or what a change would cause

## Verification (V) - [verification.md](verification.md)

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
- **V15** A merge of upstream work produces a tree nobody has tested
- **V16** A long run must say where it is while it runs
- **V17** Save a failure's output before any rerun

## Finishing (X) - [finishing.md](finishing.md)

- **X1** A review that only files findings has not finished
- **X2** A sweep is finished only where its instrument looked
- **X8** A flake the gate found is fixed, not re-run
- **X9** Suite time grows with coverage; measure before calling it a regression

## Collaboration and records (C) - [collaboration-and-records.md](collaboration-and-records.md)

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
