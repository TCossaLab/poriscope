# Measurements, gates and metrics

The question this file answers: *how will I know this worked, what is the number blind to, and
can it move for the wrong reason?*

## Contents

- I1 The definition is the number
- I2 A baseline is only a baseline if its instrument is committed
- I3 Ratchet on exact match, in both directions, with a second number
- I5 Check the gate can actually ship
- I6 Scope a shared gate to what your team controls
- I10 Write down what each instrument is blind to
- I11 Some legitimate work moves no metric, or moves it the wrong way
- I12 A heuristic moving either way is a question, not a verdict
- I13 A gate that forces the code to lie has stopped measuring what it is named for
- I14 Changing a metric's definition kills every figure recorded under the old one
- I15 A gate that runs on one path is never asked if your work takes another
- I16 A cached artefact needs a staleness check

## I1 · The definition is the number

Where a metric will be tracked, write its counting rule into the instrument and let the instrument be
the definition. Stating the rule precisely is often what makes a figure reproducible.

*Case:* "21 import statements over 12 pairs" could not be reproduced because nobody had written down
whether `numpy.typing` counts separately. Stating the rule turned it into 22 over 13.

## I2 · A baseline is only a baseline if its instrument is committed

At the exit review, three starting figures did not reproduce as recorded - one because the rule had
since changed deliberately, one because a bare text match had been used, one because "duplicated lines"
had counted near-copies that byte-identity cannot see. Commit the instrument with the baseline, and
re-measure both ends with the same instrument.

## I3 · Ratchet on exact match, in both directions, with a second number

Under `<=`, a step that removes duplication leaves the baseline overstating what remains and slack
accrues silently. Fail on improvement too, so the win is recorded in the commit that earned it (and the
promotion wave becomes the natural commit unit). Pair the headline number with a second one that tells
real progress from apparent progress - a promotion deletes functions, a copy edited into divergence
does not (the refactoring skill's `scripts/measure_duplication.py` reports both). The mirror rule: a loss must not be quietly
absorbed either - re-baseline and record why.

## I5 · Check the gate can actually ship

After writing a baseline file, confirm version control can see it (a blanket `*.json` ignore made two
baselines silently uncommittable; CI would have failed with "baseline is missing"). Stage new files
before trusting a "run on all files" hook, which inspects only tracked ones.

## I6 · Scope a shared gate to what your team controls

A gate must not fail on work that is not yours to gate. Exclude other owners' files by name and
*assert* the exclusion, so a later tidy-up aiming for completeness cannot quietly add them back.
Otherwise the gate becomes something other people route around.

## I10 · Write down what each instrument is blind to

Every gate has a blind spot, and each costs something to find: a duplication ratchet cannot see two
duplicates in one file or five pairwise-distinct copies; a boundary gate cannot see a public reach-in;
a coverage audit cannot see whether a naming test asserts anything; a strict docs build cannot see a
page that stopped existing. Put the blind spots in the plan next to the numbers, or the next reader
treats the total as coverage.

## I11 · Some legitimate work moves no metric, or moves it the wrong way

Record why the number did not move, in the commit and in the plan - left unrecorded it reads as a missed
opportunity, and the temptation becomes work that moves a number instead of work worth doing. Some
changes are predictably adverse: splitting a method that carried duplication doubles the duplication
(count the copies before splitting). And do not trim explanatory docstrings to improve a diffstat: line
count is a proxy for code complexity, and prose is not code.

## I12 · A heuristic moving either way is a question, not a verdict

When a warning fires, prove whether it is real (diff the other copy) rather than dismissing or trusting
it. The inverse slips through more often: a metric moving the way you wanted on a commit that should not
have moved it. Prove the fall was earned; when it was not, bank it anyway and say so.

*Case:* a docstring-only commit dropped the duplication figure by 41 lines and one group - two methods
had been "identical" only because their docstrings matched (the hash included the docstring). Nothing
fails and the re-baseline is routine, which is why nobody asks.

*Also:* a count can fall with nothing fixed when promoting shared code merges two copies of one violation into one. *Case:* a boundary ratchet halved from 10 to 5 when a method holding the same five reach-ins was promoted to a base; the violations were unchanged in kind.

## I13 · A gate that forces the code to lie has stopped measuring what it is named for

When a static check and the code disagree, establish which one is wrong before changing either. Ask
first whether the contorted version is better on its own merits; if not, relax the rule, not the code -
and measure how wide to relax it. The workaround is the measurement telling you the gate is wrong.
Equally, where a gate is counting correctly but reaching zero would make the design worse, record a
**floor** with its reason rather than contorting the code: a gate's target is not a design argument.

*Case:* "no View imports a computation library" counted imports used only in type annotations, and had
already forced one attribute to be typed `Any`. Relaxed to "a name loaded outside an annotation", the
allowlist fell 14 -> 8 and every remaining entry was genuine computation. Exempting the typing module by
name looked simpler and was wrong: the annotation needed both imports.

## I14 · Changing a metric's definition kills every figure recorded under the old one

A metric's definition and its recorded values are one artefact. When the definition moves - widened,
narrowed, or stated precisely for the first time - re-derive every figure that used it in the same
commit, per-unit breakdowns first (the headline is the one someone will re-measure; the breakdowns are
the ones nobody does). A caveat printed beside a table is not a correction; if the table needs a warning
about how it was counted, the table is wrong.

## I15 · A gate that runs on one path is never asked if your work takes another

Check that the CI path where a gate runs is the one your work actually takes. A gate needing coverage
data ran only on pull requests; the refactor merged locally with no PR, so the gate was never asked, and
its local tests skipped with a message that read like a setup nit. A docs build was also bypassed by the
same merge strategy.

## I16 · A cached artefact needs a staleness check

An instrument that reads a cached artefact (coverage data written at the end of the previous run) returns
confident wrong answers: adding a method and its test failed on the first full run and passed on the
second, which looked like a flaky regression. Skip or fail unless the artefact postdates every source
change. If the check cannot be written cheaply, the artefact should not be trusted in that position.
