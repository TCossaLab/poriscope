# Lesson index

Every lesson this skill relies on, by ID. Grep this file for a symptom or keyword, then open
the linked file and read the lesson in full - the case matters as much as the rule.
IDs are unique across the sibling skills.

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

The C, D, E, I, N, P, V and X lessons not listed above are indexed in the general skill's
[lesson-index.md](../../planning-and-executing-changes/reference/lesson-index.md); grep both.
