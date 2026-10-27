# Tests that tell you something

The question this file answers: *does this test fail when the behaviour it names breaks, and does
it exercise the program the way the program really runs?*

## Contents

- N3 Enter, set up and tear down through the application's own doors
- N2 Executed is not pinned, and mentioned is not covered
- N4 Prove every pin discriminates, and confirm the mutation happened
- N5 Stub a collaborator the way it really behaves
- N6 A stub standing in for a collaborator hides that the collaborator is untested
- N7 New runtime mechanisms are written test-first, against the invariant
- N8 A wait must be satisfied only by the finished state, and only by this run's
- N9 Choose the deterministic path when the net has a choice
- N10 Pick awkward fixture values
- N11 Never keep a self-generated golden across a move
- N12 Structure-reading tests should announce their own obsolescence
- N14 Assert the net is armed
- N15 Never reshape production code to keep a test passing

## N3 · Enter, set up and tear down through the application's own doors

A characterization test that names internals has to be edited by the very change it exists to
check, which is the moment it stops being evidence. Drive the net through public entry points (action
names, the API, the CLI) and assert on outcomes. Arrange state the way the app arranges it -
registering a plugin by the call that announces the registration, not by writing into a registry.
Tear down through the app's shutdown path too.

*Case:* five outcome flows went through one dispatch method's action names and survived three steps
of restructuring by construction. A later net registered its stub directly into the registry the
old mechanism resolved against; the replacement resolved against a different registry, so the net
would have failed for a setup reason mid-change. Separately, a harness that closed data plugins but
not worker threads (the app did both) produced an interpreter abort *after* "8 passed" on slow CI
machines - recorded for weeks as unexplained flakiness.

*Also:* a stub that borrows real methods off a class the test cannot construct should name each borrowed method explicitly, so a new helper the real class starts calling fails loudly instead of being quietly absent. *Case:* sixteen tests calling an app-setup method on a logger-only stub broke when the method gained a helper; the stub now borrows the named real methods.

## N2 · Executed is not pinned, and mentioned is not covered

Separate "the body executed" (coverage) from "a test named it" (static scan) from "an assertion
depends on its output" (mutation). A method needs the last. Count `Mock` replacements separately
from real calls.

*Case:* one filter method had 38 test references and every one replaced it with a mock - it sat on
every plot path with no behavioural coverage. A naive reference count scored 64 of 66 methods
covered. Separately, five Views sat at 87-91% line coverage before any characterization test
existed, and adding them moved the figure at most one point: the end-to-end suite executed the
lines and nothing asserted the values.

## N4 · Prove every pin discriminates, and confirm the mutation happened

Change each constant or clause a test claims to cover and watch the test fail. Run it as a pass over
a list of (anchor, replacement, test) triples, restoring the source in a `finally`
(`scripts/mutation_probe.py`). Three refinements:

- **An equality assertion cannot see a missing type coercion.** `== [(0, True)]` passed with a
  `bool()` removed, because `1 == True`. Assert `is True` and feed a truthy non-`True` value.
- **Where a perturbation moves nothing, either the input is too clean or the code is dead weight -
  and the fork is not symmetric.** "Dead weight" is a claim about every input; a probe over one
  cannot support it. Ask what degenerate case the mechanism was written for and measure that. A
  window, clamp, fallback or guard always looks inert on the happy path.
- **A botched mutation reads exactly like a weak test.** Assert the anchor is unique, print the
  removed text, or diff before and after. A botched mutation never produces a false alarm, only
  false reassurance - which invites rewriting a good test.

*Case:* a golden "covering the windowing constants" was insensitive to two of four, because a fit is
exact on a true Gaussian over any symmetric window; a second golden over contaminated profiles fixed
it. Another asymmetric window, perturbed over unimodal noise, moved sigma 0.13 points and was deleted
as dead; over a bimodal baseline it was worth several percent. A mutation script anchored on a
string occurring twice spliced the wrong region; the test "passed" because nothing had changed.

## N5 · Stub a collaborator the way it really behaves

A bare `Mock()` where the real collaborator has a side effect makes every downstream assertion
vacuous. Write each stub from the collaborator's **real behaviour, real signature and declared
return type** - never from the code you just wrote. Every answer in a recording stub is an assertion.

*Case:* a call moving from a tuple-packing dispatcher to a direct call kept its tuple; every unit
test passed because the model was a `Mock`, and the new test asserted the tuple shape - pinning the
bug. Only a real reader in an end-to-end test raised `missing 1 required positional argument`.
Later, a stub answered with a bare string where the collaborator returns `(str, str)`; in production
the tuple was always truthy, so two "empty query" guards could never fire.

## N6 · A stub standing in for a collaborator hides that the collaborator is untested

When you convert callers to use a new method and stub it in their tests, the new method itself is
covered by nothing - and every gate stays green, because a method that did not exist before is on
nobody's target list. A conversion owes tests to its destination. After each conversion, list the
destination's new methods and ask what names each one.

*Case:* two new Controller methods shipped with thirty-odd re-pointed View tests stubbing them and
no test of their own. Fired five times in one refactor before it became a checklist item.

*Also:* before deleting the source copy of moved code, port the pins that exist only on it - two of twelve pins on a deleted copy had no equivalent at the destination, and deleting first would have dropped them silently. Remove any test left asserting on a mock of a method that no longer exists: a mock of nothing cannot fail.

## N7 · New runtime mechanisms are written test-first, against the invariant

Moves are covered by ratchets and characterization tests; a *new* mechanism (a push, a lifecycle hook,
a dispatch scheme, a cache) is not, because absence has no signature - a missing call at one of two
sites is not duplication, not a boundary crossing and not an uncovered target. So:

1. State the invariant in prose ("whatever a component is told exists, it can call, at the moment it
   is told").
2. Write it as a test; run it against the unmodified code and watch it fail.
3. Write the mechanism; watch it pass.
4. Cover construction *and restore* orderings, not just the happy one.
5. For a missing-call failure mode, consider a structural test asserting the relationship between
   call sites.

Any regression the suite missed gets a test as soon as it is positively diagnosed - the fix alone is
not the deliverable.

*Case:* the first new mechanism of the refactor pushed both names and instances at one site and only
names at another; a user found it under session restore. The first test written asserted both pushes
happened - and passed on the broken code, because the counts were right and only the order was wrong.

## N8 · A wait must be satisfied only by the finished state, and only by this run's

Write a wait predicate against the completed state and scope it to the artefact this run created.
Knowing the rule does not prevent the mistake - review every predicate.

*Case:* three wrong predicates in one branch - "no workers" was true before the first worker was
registered; "any CSV with rows in this folder" was satisfied by a previous run's export; "row count >
0" passed alone and failed the full suite because rows land incrementally on a worker thread. The last
was written in a file whose own docstring cited the decision documenting exactly that failure.

## N9 · Choose the deterministic path when the net has a choice

A net that can go flaky for reasons unrelated to the change stops being believed, and a net nobody
believes still costs review time. Seed or remove randomness before capturing goldens, preferring
algorithms that need no seed, and use a local RNG rather than the global one.

## N10 · Pick awkward fixture values

Where a fixture value flows into generated code, a path, an identifier or a query, choose the
awkward one: a space, a hyphen, non-ASCII, a reserved word. A well-behaved value makes the suite agree
with itself about a world that does not exist.

*Case:* 47 generator tests passed generating into `user_plugins`; the real folder is `User Plugins`,
and the first real use produced a `SyntaxError` in a generated import.

## N11 · Never keep a self-generated golden across a move

Regression fixtures write a fresh golden when none exists at the (new) path. Accepting it turns the
test into a tautology. Let it generate, diff the generated file against the pre-move golden, and only
then move the original into place.

## N12 · Structure-reading tests should announce their own obsolescence

A test that extracts code by AST or reads source text should *raise* with a message naming what
happened when its target disappears, rather than fail on a bare mismatch or pass over an empty set. Its
docstring should say which future change is allowed to break it. When it breaks, rewrite the whole
test class against the new structure: after a conversion, the tests that *still pass* are the dangerous
ones, because they may now assert something trivially true ("no bus call happened" once the method makes
none).

*Also:* when production code works around a defect in a dependency, pin the defect itself in a test, so an upstream release that fixes it fails that test and announces that the workaround can go. *Case:* a guard against a Qt binding that instantiates abstract subclasses kept a test asserting the binding still does so.

## N14 · Assert the net is armed

A net can be disarmed by a missing dependency, and that reads as a pass: a handful of fixture-not-found
errors beside thousands of passes looks like an environment nit, not like the entire numeric net not
running. Add a test that fails loudly and names the cause when the net's dependencies are absent. Treat
any dependency whose absence silently removes coverage as a gate in its own right.

*Also:* when a test guards a file the repository ships (a version string, a generated page), assert on the checked-in file as well as on a temporary fixture. A test that only ever reads the fixture passes while the tracked file drifts. *Case:* a version-agreement check gained a test reading the committed files, beside seven that used fixtures.

## N15 · Never reshape production code to keep a test passing

When a correct change breaks tests, edit the tests. Never introduce a variable, guard, ordering or code
path whose only justification is that a test pre-sets some state; tests then pass without exercising the
contract. Test ownership does not change this - editing an existing test to keep it relevant is expected,
and strictly better than weakening the code or the test's meaning.

*Case:* clearing a result attribute before an emit broke twelve tests that pre-assigned the attribute
under a bare mock. Reworking production code to keep them green was rejected; the right fix gave each
mock a side effect setting the attribute as the real dispatcher does.
