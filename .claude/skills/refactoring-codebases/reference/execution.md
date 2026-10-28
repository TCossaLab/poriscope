# Executing the refactor

The question this phase answers: *does the mechanism do what its name and its comment claim, and
what does this move cost that the diff does not show?*

## Contents

- Sequencing and commit series
- Before promoting or merging copies: E1, E2
- Designing the destination: E7-E10
- After a move: E11, E12
- Converting calls into requests: E14, E15, E18, E19

The general execution lessons - E3-E6, E13, E16, E17 and E20-E25, including measuring a "no-op"
before relying on it, structural checks on deletions and splices, keeping fixes minimal and fixing
contracts at the call sites - are in the general skill's [execution.md](../../planning-and-executing-changes/reference/execution.md). This
file adds the hazards of moving, promoting and converting code.

## Sequencing and commit series

- **Moves before protocol changes.** A move is covered by ratchets and characterization tests; a
  protocol change introduces a mechanism and needs test-first work (N7, general skill).
- **Pilot on the smallest self-contained unit** - it shows concretely what "re-pointed
  mechanically, reviewed as a diff" looks like before the expensive units.
- **Move verbatim, then change, in separate commits.** A commit that relocates code should leave its text
  byte-identical (prove it with the general skill's `scripts/structural_diff.py` or a plain diff of the moved block). Any
  cleanup, rename or behaviour change goes in the next commit, so a reviewer, a golden and a bisect can
  each tell which of the two changed the outcome.
- **The dependency graph picks the order.** A promoted method may only call what is already on the
  base, so leaves go first and the largest single win often lands last. Say so in the plan.
- **Plan each step as a commit series in which every commit banks a measurable win and runs
  green.** Simulate each commit's metric first (instruments I4), present the series for approval,
  record the approved series in the plan, then execute. Use `templates/commit-series.md`.
- **After a promotion step, check that no duplicate group survives at the old arity** - one that
  does means the step missed a copy.
- **When shared state forces two methods into one commit, check whether unifying that state is
  the commit's real deliverable** (E15).
- The refactor finishes before the features it uncovers: file domain questions it raises with their
  measurements rather than working them mid-step.

## Before promoting or merging copies

### E1 · "The same code twice" is the claim a promotion rests on - diff it

Diff the copies line by line rather than reading them, and diff what they *resolve* too: identical bodies
in different modules can see different module-level names (a `CURRENCY` constant, an import aliased to a
different library, a locale or decimal context set at import time), so after the move one caller silently
gets the other's environment. Then decide explicitly which behaviour the survivor gets: measure the difference, write a dated decision entry naming it, add a changelog line
if user-visible. Where the copies are identical the diff costs a minute; where they are not, it is
the whole finding.

*Case:* two event finders carried "the same code twice"; a three-line difference inside the shared
half - one symmetrised a histogram window, one did not - meant the promotion changed one plugin's
science whichever way it went.

### E2 · A numeric difference between near-copies may be the domain's rule, not drift

Near-identical code that differs in a constant is not only "drift" or "bug". Ask whoever owns the
domain before classifying it, and when the answer is that it is principled, write the rule next to
the constant so the next deduplication attempt fails loudly.

*Case:* four copies of a bin-width calculation; one used a fourth root where three used a cube root.
It was the exponent `1/(2 + D)` for D binning dimensions - the 2-D case - and must never be collapsed.

## Designing the destination

### E7 · Interface width, not hierarchy depth, is the expensive axis on a published base

On a base class that is a published extension API, a stateless self-contained method can sit on the
common base even if only some subclasses use it. Behaviour that brings instance state, abstract hooks or
new imports needs an intermediate base, because it is a second contract inside the first. Keep one
composition mechanism: if the codebase is folding its only mixin into a base, do not add mixins. And do
not make extension authors learn app-internal types to implement the contract - keep the extension API
self-contained, even at the cost of static checking.

### E8 · A promoted method reaches shared state through an accessor, not a second stored reference

Storing a second reference to an object on the base gives it two sources of truth; every substitution
(a test double, a rebuild, a lazily replaced widget) updates only one. A one-line abstract accessor
each subclass implements over the name it already uses has one. Tests that break on the first design are
the cheap signal: write the promotion against the existing suite before choosing the mechanism.

### E9 · For a layering rule, "who consumes this?" beats "where did it come from?"

A value belongs in the model layer when it leaves the view (exported, cached, reused), not because it is
"a property of the data". Ask whether moving it creates complexity where none is needed. The governing
question in a layering refactor is responsibility and maintainability, not the gate's target.

*Case:* an axis roll-off index was moved to the Model as "a property of the data", wired through a
Controller and setter, and reverted: nothing outside the drawing method used it. The plot's time axis
did leave the View (cached, exported to CSV), so the Model builds that.

### E10 · A test reaching a shared method through an unrelated subclass hides a mis-homing

If the subclass a test goes through to reach a base method is arbitrary, the method is probably higher
in the hierarchy than it should be.

*Case:* five range helpers on the root base, used by two of five subclasses, were tested through a third
with no relationship to them - which is why nobody noticed they were on the wrong base.

## After a move

### E11 · A promotion moves the tests' patch targets

`patch("pkg.module.Name")` patches the name in the module that *imports* it. When the method reading
that name moves to a base in another module, the patch stops intercepting. Some fail loudly; others let
the real collaborator run and the assertion drifts. After promoting, **grep the tests for every name the
moved body referenced**, not just the method names. A stale patch on a real dialog, filesystem or
network entry point will *crash* rather than fail: a native modal dialog in a headless run killed the
interpreter with no summary line, at a different place each run, and was twice misread as flakiness.
Never shape the base so old patch strings still resolve - that is production code written around a test.

### E12 · After a signature change, grep all tests for the name

The test file sharing the module's name is the obvious one and not the only one. A second suite covering
the same class (a characterization file) still called the old shape while the scoped run went green.

### E28 · Tests passing untouched across a move are the evidence

After a pure move, existing tests passing with no edit is what shows the behaviour was preserved; editing
them in the same commit forfeits that evidence. During a conversion the fallout splits the other way:
delete tests that set internal state and asserted on what was done with it (they pinned the mechanism), and
re-point the ones that asserted an outcome.

*Case:* three split commits ran 45 and 49 existing tests with none edited. A conversion that broke 73
tests deleted those setting pending state on the widget and re-pointed the outcome tests by passing the
context as arguments.

## Converting calls into requests

These apply whenever a synchronous call becomes a message, signal, request or callback.

### E14 · Convert the chain, not its links

"Replace each call with an intent" reads as one intent per call and keeps an answer-slot per link on the
caller - the pattern you are deleting, re-expressed. The test: does anything except the next call
consume what comes back? If not, one intent for the whole chain; the intermediate slots disappear, and
failures in the middle finally have somewhere to be handled.

### E15 · The unit of a move is the state it writes, not the method it lives in

Before scoping a move to a method, list the state it writes and find every other writer. Shared mutable
state appears in no signature, so it is the coupling that gets missed - and a wrong split can pass every
test and gate because the divergence it creates is unobservable while some reset happens to hold.

*Case:* two plot methods wrote the same min/max and appended to one accumulator that held four element
types depending on which plot last ran. Converted together, the accumulator went to two types; the
correct unit of work was also the one that reduced the coupling.

### E18 · When a failure's explanation moves layers, clean up what the old layer still says

After moving error reporting down a layer, grep the old caller for what it still says on that path; a left-
behind message fails no test and moves no gate. Make the caller able to tell a refusal (already explained)
from an empty result (e.g. `None` vs `[]`), and then find every upstream log-only branch in the same commit,
since the caller is now silent on refusals. Route routine empty results to user-visible status at a
warning level and genuine failures at error level.

### E19 · A converted call can leave a live-looking dead slot behind

When converting an emit or callback, check the slot's connection sites as well as its call sites. A method
kept reachable only by its own tests looks alive through later steps and audits. Deleting it belongs to the
step that orphaned it.

### E27 · A call that interleaves a question becomes two requests

When a synchronous method calls a service, asks the user something, then calls again, converting it to
requests makes it two-phase: resolve what the question needs, prompt, then send the approved items forward
as a second request. Carry the context (a filter key, the selection) through both halves as arguments;
parking it on the view between them recreates the answer-slot the conversion removes.

*Case:* launching event finding resolved each channel's status, the view asked about already-finished
channels, and only the approved channels came back; committing fits went two-phase the same way.
