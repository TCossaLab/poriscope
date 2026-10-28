# Finishing a piece of work

The question this file answers: *is it actually done, is the account of what happened true, and
was every finding closed rather than filed?*

## Contents

- Before calling anything done
- X1 A review that only files findings has not finished
- X2 A sweep is finished only where its instrument looked
- X8 A flake the gate found is fixed, not re-run
- X9 Suite time grows with coverage; measure before calling it a regression

## Before calling anything done

- Every finding raised during the work is fixed in this piece of work, or deliberately deferred
  with a recorded reason and its measured number (X1).
- Every "landed" claim is checked by behaviour, not by a text match (verification V12).
- Any sweep's instrument covers every artefact type the rule names (X2).
- A test that failed once and passed on re-run has had its race found and fixed (X8).
- The docs, the changelog, the work queue and the decision log say what is now true
  (collaboration-and-records C6), and nothing that ships cites a plan document that will be
  deleted.

## X1 · A review that only files findings has not finished

Budget for the fix inside the review. Implementing a finding is how you discover whether you understood it.

*Case:* an exit review produced five missing checks and a corrected figure, recorded in two places with all
gates green. Closing them changed two: measuring the doc generators showed one step's risk was smaller than
the plan claimed and another's larger - which writing the finding down would never have revealed.

## X2 · A sweep is finished only where its instrument looked

When a rule is stated over a kind of artefact ("documentation") and measured over a file type (`*.py`), the
gap is invisible to every run of the instrument - the command returns a number, the number matches the
prediction, and a re-measure built from the same command agrees by construction. Read the rule's wording
back against the command, and widen the command rather than narrowing the rule.

*Case:* a sweep of plan citations "out of the docstrings and the published docs" grepped only `*.py`; a
published `.rst` page for extension authors still cited a plan step.

## X8 · A flake the gate found is fixed, not re-run

A test that failed once in a full run and passed alone has a real race. Find it and fix the wait.

*Case:* an export flow waited for two of the three tables it asserted on; the fix was to wait for the table
the export writes last.

## X9 · Suite time grows with coverage; measure before calling it a regression

Normalise per test and compare phases. On the source refactor, 2,950 -> 4,215 tests took 409 -> 517 s, which
is 0.139 -> 0.123 s per test: no regression. A suspected doubling of end-to-end time was run noise, settled by
re-running the files in isolation on both commits.
