# Mapping onto the host

The question this file answers: *where does each of the original's capabilities land in the host, and how
do you know the host's version computes the same thing?*

## Contents

- A5 Port the inputs and outputs, not the program
- A6 "The host already does this" needs a numeric equivalence check
- A7 Carry units across the host's contract explicitly
- A8 A default that refuses the users' input needs their say

## A5 · Port the inputs and outputs, not the program

The users need the original's inputs to go in and its outputs to come out; they do not need its file
pickers, caches, threads or screens. Map each capability onto the machinery the host already has - its
plugin families, settings dialogs, readers, workers, status display, export - and write down what the host
would have to grow where nothing fits. Scope options written as "build the original's view X" are a
transcription in disguise: rewrite them as "X's inputs and outputs, through host mechanism Y" before
asking. Anything new in the host - a new family, a new tab, a new option on an existing view - is a
ruling, with the native alternatives listed beside it (`templates/capability-map.md`).

*Case:* the first scope options listed the original's capabilities as things to port, including its
single-file spectrum viewer as a view of its own. The user's correction: inputs and outputs must be there,
but the path should be the host's own machinery wherever possible. Re-mapped, the single-file viewer
became options (segment length, overlap, a power-law fit) on the host's existing spectrum view; the
recordings are read by a variant of an existing binary reader; and the experiment folder became a new
data-plugin family, so it gets the host's settings dialog, plugin lifecycle, status reporting and session
persistence instead of a folder picker and a private cache.

## A6 · "The host already does this" needs a numeric equivalence check

A host feature with the same name as the original's is not the same computation until the same input
through both gives the same number. Read the whole host function, not the line a search found, and list
every convention that can differ - for a spectrum: window, segment length, overlap, scaling, one- or
two-sided - then run both on one real file and compare. Where they differ, the difference is a design
input: extend the host feature with the missing option, or keep the original's computation, as a ruling.

*Case:* the design document said the host's spectrum used one segment per recording and was "equivalent"
for this data - a claim built on a search hit. Reading the whole function showed a segment of a tenth of
the recording with 50% overlap; on these recordings that left no frequency bins at all inside the 1-30 Hz
fit range the analysis depends on. The port added segment length and overlap options to the host's view,
with defaults equal to its old behaviour so saved sessions replay unchanged (general lesson E30).

## A7 · Carry units across the host's contract explicitly

The original and the host rarely store the same unit. Find the unit at each boundary - what the
instrument wrote, what the original converted to, what the host's contract requires - write the
conversion down, and work out where it makes agreement inexact. A port that converts once, at the
host's boundary, will disagree with an original that converts late by rounding; say so, and set the
comparison tolerance from it rather than from what passed (A9).

*Case:* the recordings were in millivolts. The original divided each sample by 1000 to get volts and
multiplied the finished spectrum by the squared amplifier gain; the host's readers must return picoamps,
so the port multiplies each sample by gain / 1000 as it is read. The two orders of operations agree to rounding, not bit for bit, so
the goldens are compared at a relative tolerance of 1e-9; the worst difference on the real data was 3e-14.

## A8 · A default that refuses the users' input needs their say

Where the original is ambiguous - several files where it expects one, a gap it ignores - the safe-looking
recommendation is to refuse the input with a clear message. That is the wrong default if the users'
acquisition routinely produces that input. Ask how the files arise before recommending a refusal, and put
the refusal and the accommodation side by side as a ruling.

*Case:* the original took whichever of several CSVs a directory listing returned first. The plan
recommended refusing a folder with more than one. The user overruled it: acquisition restarts part-way
through an experiment write a second CSV, so the port orders them by the date-time stamp in their names
and reads them as one file. A probe that orders them by name instead fails the loader's tests (A10).
