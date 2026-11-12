# Proving equivalence

The question this file answers: *how do you show the port computes what the original computed, except where
it was ruled to differ - and that the difference is the ruled one?*

## Contents

- A9 Bring the original's outputs over as goldens, on a generator kept in the repository
- A10 Prove each fixed defect by putting the original's behaviour back
- A11 Finish with every value on the real data, from a clean copy

## A9 · Bring the original's outputs over as goldens, on a generator kept in the repository

The original is the only oracle a port has, and it will not be runnable for ever - it is often
unversioned, untested and on one person's machine. Write a deterministic generator for its input format
into the host's test tree, run the original on the generated data once for each setting that changes the
computation, and save its outputs beside the generator. The port's tests then compare against those
files at a tolerance stated with its reason (A7). Seed or remove all randomness first; a golden the port
produced itself pins nothing (general lesson N11).

*Case:* a synthetic writer in the test tree produces a complete experiment folder - CSV, both biases'
recordings, a short recording and a PSD every second cycle. The original's harness (A3) ran on it for two
settings, the defaults and a changed gain with a narrower fit range, and its 1 Hz values went into a JSON
file. The port's model and loader tests compare against it at a relative tolerance of 1e-9, the rounding
allowance from the unit conversion.

## A10 · Prove each fixed defect by putting the original's behaviour back

A test that passes on the port says the port behaves; it does not say the test would notice the original's
defect returning. For every defect the port fixes, write a probe that restores the original's behaviour at
one anchor - the old cache key, the old index - and confirm a named test fails, and that the probe really
changed the code (general lesson N4). Keep the probes in a file so the check can be rerun after any
refactor of the port.

*Case:* four probes, each restoring one of the original's behaviours: noise bands placed by cycle index,
results cached by experiment only, CSVs ordered by name instead of stamp, and a short recording passed
over without a note. All four were killed by the tests named for them.

## A11 · Finish with every value on the real data, from a clean copy

Goldens on generated data cover the cases someone thought of; the real data holds the rest. As the last
step, run the original and the port on the full real dataset and compare every value, not a sample, at the
golden tolerance, from a clean copy of the commit being merged - print the module path the comparison
imported, since a script run from another working copy may import the editable install instead (general
lesson V19). Time both while you are there, more than once: a first run that disagrees wildly with the
second is usually the machine, not the code (general lesson V13).

*Case:* 71 cycles x 16 channels x 2 biases = 2,272 values agreed, the worst relative difference 3.0e-14,
the cycle lists identical, and the short recording noted. The first timing put the port at 397 s against
the original's 18.5 s, 21 times slower; one channel profiled at 1.8 s, and a repeat of the whole comparison
gave 15.1 s against 21.7 s. The slow run had started minutes after 71 recordings (900 MB) were renamed
in a cloud-synced folder.
