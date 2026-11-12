# Understanding the original

The question this file answers: *what does the original actually do, to what data, how fast, and where
is it wrong - before any of it is designed into the host?*

## Contents

- A1 Inventory capabilities per entry point
- A2 Derive data formats from the sample files as well as the code
- A3 Run the original headlessly before designing
- A4 The original's defects, and the data it never reads, are rulings

## A1 · Inventory capabilities per entry point

An application is rarely one program. A core script, the GUI wrapped around it, a viewer for single files
and the notebook someone runs on Fridays each add behaviour of their own, and a port scoped from the core
alone loses whatever lived only in a wrapper. List every entry point first, then the capabilities each one
offers, with `file:line`, and mark which entry point owns each. The list is what the user rules on when
scoping, so it has to be complete before options are written.

*Case:* the original was three scripts. The core read a folder and plotted; its GUI wrapper added a cache
of loaded results per folder, manual overrides for the sample rate and points per average (otherwise read
from the file name), a channel-subset grid and a background thread; a third script viewed one recording's
spectra. Scoping from the core would have dropped the overrides and the channel subsets, both of which the
port keeps (as experiment settings and a channel selector), and missed the cache, which turned out to be
defective (A4).

## A2 · Derive data formats from the sample files as well as the code

Reader code says what the author expected; the files say what the instrument wrote. For a binary format,
divide a sample file's size by channels times sample width to get its frame count, and check it against
the counts and rates the code and the file names claim. Do it for every file, not one: the anomalies are
in the outliers, and an outlier can rule out a design (a reader that stitches recordings into one timeline
cannot survive one short recording) or show that past results computed from the names were wrong. A
contradiction between a file and its name is a question for whoever owns the data, asked before the port
decides which to trust.

*Case:* 16 channels of big-endian float64 at 128 bytes a frame put every recording at 100,000 frames -
except one at 67,000, a truncated file the original analysed silently at a different frequency
resolution. That one file ruled out a stitched-timeline reader. A second check found all 71
positive-bias recordings named for 500 kHz while the same size as the 10 kHz negative-bias ones: at
500 kHz each would be 0.2 s long and its 1-30 Hz fit would rest on 6 frequency bins instead of about 291.
The lab confirmed the names were wrong and the files were renamed. The original had read the rate from
the name, so every positive-bias noise value it had produced was fitted at the wrong rate - a finding
about the lab's past results, not about the port.

## A3 · Run the original headlessly before designing

Import the original as a library - non-interactive plotting backend, module-level settings assigned from
the harness, its functions called directly - and run it on the real sample data. The run time decides
whether the port needs background work and progress reporting; the same harness later captures goldens
(A9) and runs the final comparison (A11). A port designed before the original has been run designs from
the code's intentions, which A2 shows can differ from what it does.

*Case:* the harness set the module's channel count, sensitivity and fit range, then called its folder
function for each bias: the CSV read in 0.015 s, and the 71 recordings of each bias took 8.9 s and 8.0 s.
Seconds per experiment meant the port computes on per-channel background workers with progress, and
keeps results so a replot is instant. The same twenty-line harness later produced the goldens and the
real-data comparison.

## A4 · The original's defects, and the data it never reads, are rulings

Read the original for defects as you would a review: list each with `file:line` and what it does to a
result. Whether the port fixes or reproduces each one is the user's ruling, because users may have
published numbers that depend on the defect, or compare new results against old ones. List too what the
sample data holds that the original never reads - another subfolder, another file type - and ask whether
it is in scope; it may be the next feature, or a reason the data was sent.

*Case:* the review listed seven defects. Two changed results: the GUI cached fitted values keyed only on
the folder, so after changing the sensitivity or fit range it redrew the old values; and noise bands were
placed by cycle index, landing on the wrong cycles whenever a recording was taken every second cycle,
and raising once the index passed the file count. The user ruled that the port fixes the defects and
matches the original wherever it is right; each of those two is pinned by a probe that restores it (A10).
Two more became features: several CSVs, which the original took in arbitrary order, are joined in the
order of their file-name stamps, and a truncated recording is named on the status panel instead of being
analysed without a word. The sample folder also held current-voltage sweeps and standalone spectra the
original never opened; asked, the user ruled both out of scope.
