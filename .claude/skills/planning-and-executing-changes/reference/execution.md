# Executing changes safely

The question this file answers: *does the mechanism do what its name and its comment claim, and
what does this edit cost that the diff does not show?*

## Contents

- E3 Measure a "no-op" before promoting it, and read the comment as a claim
- E4 A mechanism that reads as a contract may not be one
- E5 Showing a mechanism has an effect is not showing the effect is wanted
- E6 Measure the cost of the design you are about to reject
- E13 Grep classifies; only running tells you which class
- E16 Do not mutate shared state before asking a question that can be refused
- E17 Deferred execution runs its guards on whoever advances it
- E20 Check a path can produce its output before improving what it shows
- E21 Anchor deletions on blocks, not lines
- E22 A splice anchored on its neighbours deletes whatever sits between them
- E23 An auto-fixer reconciles around damage and hides it
- E24 Keep each fix minimal, and close it where you found it
- E25 Fix the contract at the call sites rather than guessing at runtime
- E26 An atomic replace can be refused on Windows; retry it, bounded
- E29 One value, many readers: map the pipeline from input to outcome at every entry point

## E3 · Measure a "no-op" before promoting it, and read the comment as a claim

Two questions, not one: does the call do anything, and does it do what it says? Thirty seconds in a
scratch file often settles a decision that looked risky.

*Case:* one of five copies lacked `setStyleSheet("")  # reset to default style`. Measured: the call is
inert and *cannot* do what the comment claims (an empty stylesheet does not block a parent's
cascade), so the majority version promoted freely.

## E4 · A mechanism that reads as a contract may not be one

Decorators, guards and handlers can be inert while still reading as contracts - and type checkers may
still honour them, which is what makes them dangerous. Measure that the mechanism fires; when it does
not, look for the project's existing answer before inventing one.

*Cases:* `@abstractmethod` is inert on a class whose metaclass is not `ABCMeta` (a Qt widget's is the
binding's own), so a subclass that forgets the method is never told; the project already had a combined
metaclass for this. A `try/except ... else:` around a signal emit could never fire, because a slot's
exception does not propagate to the emitter. A nested function hid a docstring linter's violation in
its parent; hoisting the nested def made the linter fail on a method the commit never touched -
bisect, do not revert.

## E5 · Showing a mechanism has an effect is not showing the effect is wanted

A measurement can establish magnitude without establishing sign. Between "inert" and "a feature" sits
"load-bearing, and pointed the wrong way". Sweep the direction too, and where the sign depends on a
domain fact, ask the owner before writing a rationale. A mechanism nobody can explain gets **pinned**
(comment saying what it does and where the question lives, a test that fails if it moves either way,
the open question filed with its numbers), not justified.

## E6 · Measure the cost of the design you are about to reject

When a benchmark argues against the cleaner design, profile the reason before accepting the verdict:
often you are measuring an accident of the current implementation.

*Case:* collapsing two helpers onto one looked like a 2.7-4.7x slowdown on eight plot paths; the
slowdown came from re-slicing the whole frame once per column. A single-slice rewrite reached parity,
and the decision turned on churn instead (one caller to adapt, not eight).

## E13 · Grep classifies; only running tells you which class

A grep survey of references is a hypothesis about categories, and the run is the experiment. Where the
plan for a deletion depends on the split (what goes now, what defers), delete first in a scratch state
and let the failures classify the references.

*Case:* three end-to-end files matching the old bus name were filed as "vestigial mocks". They were using
the bus as a query mechanism; six tests broke on deletion and had to be converted.

## E16 · Do not mutate shared state before asking a question that can be refused

Synchronous code often does bookkeeping *before* the work and undoes it on failure. After conversion the
answer may be a refusal, leaving the caller holding state the result does not contain. Send the
accumulated state and the newcomer together and let the answer do the appending: nothing is undone because
nothing was done.

## E17 · Deferred execution runs its guards on whoever advances it

A generator function, lazy iterator or deferred task only constructs when called; every guard in its body
fires on first advance, after the caller's `try/except` has passed and possibly on another thread. Ask the
question before starting the work, through the same query the work runs (a separate "is it empty?" query is
a second source of truth). Prefer arrangements that keep a lock, generator or mutable state owned by one
thread for its whole life.

*Case:* an export whose filter matched nothing ran the progress bar to 100%, consumed the next output name
and reported only a worker-thread warning - while the changelog had called it fixed for three days.

## E20 · Check a path can produce its output before improving what it shows

Before fixing what a branch displays, establish it can return anything at all. A path with no working
end-to-end case is dead code wearing a feature's clothes; the fix is deletion, and a queued item to share it
elsewhere would spread it.

*Case:* a commit correctly made a displayed query match the executed one - on a branch that had never
returned a row, because it spliced a complete `SELECT` after `WHERE`.

## E21 · Anchor deletions on blocks, not lines

Deleting a statement by matching its line text can re-parent what follows when indentation carries meaning:
with the last statement of a block gone, the formatter closed the gap and an emit ended up inside the
preceding `if ... return` block. It parsed, type-checked and linted clean; two tests caught it.

## E22 · A splice anchored on its neighbours deletes whatever sits between them

Replacing code by slicing from one `def` to "the next expected `def`" removed a five-line method in the gap,
and the application could not start. Parse the class before and after and assert the set of methods lost is
exactly the set intended (`scripts/structural_diff.py methods`). The check also catches an anchor that
orphans a decorator.

## E23 · An auto-fixer reconciles around damage and hides it

After a bad deletion, the formatter removed the now-unused imports and the tree became self-consistent -
every linter green. Restoring the method then produced a `NameError` on a tidied-away import. Run
auto-fixers before inspecting a destructive change, never between the change and the inspection; when a
strange second failure appears during a revert, suspect a helpful tool in between.

## E24 · Keep each fix minimal, and close it where you found it

Implement the smallest change that fixes the defect: no new types, accessors, plumbing hops or reporting
routes it does not strictly need. If an implementation grows well past the size of the bug, stop and ask.
Prefer failing loudly with an obvious remedy over building machinery that tolerates a user's ambiguous
input. But do fix defects found mid-work in the branch where they surfaced; filing is an explicit,
reasoned exception (another owner, needs a decision, large enough to be its own piece of work).

## E25 · Fix the contract at the call sites rather than guessing at runtime

When a dispatcher cannot tell how to interpret a value, make the contract true at the call sites (e.g. fix
the seven callers passing a bare value where a tuple is declared) and delete the normaliser; next, read
declared annotations; avoid fallback chains that retry side-effecting code with different arguments. A
`try/except` around a pure predicate that reports by raising (such as signature binding) is fine.

## E26 · An atomic replace can be refused on Windows; retry it, bounded

Write-to-temp-then-`os.replace` is the standard atomic save, but on Windows the rename is briefly refused
(`PermissionError`) while a virus scanner, indexer or sync client holds the target open. Retry a few times
with a short sleep, re-raise after the last attempt, and test both the recovery and the give-up path.

*Case:* a session file saved this way failed in about 5% of rapid saves in a temp folder; five attempts
took that to 0 of 600.

## E29 · One value, many readers: map the pipeline from input to outcome at every entry point

When one piece of state, or one rule about it, is used in several places - a selection, a scope, a
setting, a guard - consistency means every entry point runs the same pipeline: the actual order of
steps from input to outcome. Inventory every place that writes it and every place that reads it
(search for each name it travels under), then write down the pipeline each entry point really
follows, **all the way** from the widget to the query or the file, and record what each step does
with an empty value, a missing value and more than one entry. Compare the pipelines step by step. Two
failures follow from skipping this. A guard added to one entry point is missing from another that
reaches the same action, so they disagree. And a conclusion drawn from one end of a path - the
handler, or the bottom layer - describes a path the value never takes, because something in between
rewrites it. When the readers disagree, prefer a fix that makes the troublesome value unreachable
(refuse to store it) over patching each reader, and test that directly.

*Case:* a plot button refused a scope with more than one experiment, channel or filter; the arrows that
re-plot the same events read only the first of each, moved the Event ID field and then had every plot
refused - found only in a manual pass. While tracing the scope, two claims were wrong for the same
reason: one handler was read as the only place the scope is set (another loaded it on plugin creation),
and the loader was read as plotting everything for an empty scope (the caller replaced it with a
sentinel that the loader refuses, as an earlier decision entry already recorded).

