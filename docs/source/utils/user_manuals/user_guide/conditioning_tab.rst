.. _conditioning-tab:

Conditioning Tab
================

The **Conditioning Tab** follows a pore conditioning experiment cycle by cycle: each channel's
pore size against its target band, with the noise of the PSD recordings taken along the way.
It reads an experiment written by the lab's LabVIEW and NI DAQ acquisition software, and
replaces the standalone conditioning analysis script that read the same folders.

Open it from **Analysis** → **New Analysis Tab** → ``ConditioningController``.

What an experiment folder holds
-------------------------------

An experiment is one folder with up to three subfolders:

- ``Conditioning`` - one CSV row per cycle, with three columns per channel: the measured
  pore size, the upper target and the lower target, in nm. When the acquisition was
  restarted part-way there may be several CSVs; they are read as one, in the order of the
  ``YYYYMMDD_HHMMSS`` stamp in their names.
- ``Cond PSD Pos`` and ``Cond PSD Neg`` - one NI binary file per PSD recording, at positive
  and negative bias. Either may be missing. Each file name carries its settings, as in
  ``TS1_M1-M4_PSD-100000_1_10000Hz_20261110_154005.bin``: 100,000 points per average, 1
  average, sampled at 10 kHz.

Step 1: Adding an Experiment
----------------------------

1. **Click** the **➕** beside **EXPERIMENT** and choose ``NIConditioningLoader``. The same
   loader is also under **Data** → **Load Conditioning Experiment**.
2. In the settings dialog:

   - **Folder** - the experiment folder, the one that holds ``Conditioning``.
   - **Number of Channels** - 16 for the NI DAQ setups.
   - **PSD Every N Cycles** - a PSD was recorded every this many cycles. The first
     recording belongs to cycle N, the next to cycle 2N, and so on.
   - **Sensitivity** (pA/V) - the amplifier gain, which converts the recordings from mV to pA.
   - **Sampling Rate** and **Points per Average** - leave them at 0 to read each recording's
     values from its file name, or type a value to use it for every recording.

3. The status panel reports the cycles, the channels and the PSD recordings found, and
   names any recording shorter than its points per average.

Step 2: Plotting
----------------

1. Choose the **CHANNEL**\ s to plot. Channels are numbered from 0, as everywhere in
   Poriscope, so the CSV's ``CH1`` is channel 0.
2. Set the analysis values:

   - **FIT START** and **FIT END** (Hz) - the range of the straight-line fit of log PSD
     against log frequency. The 1 Hz noise is that line's value at 1 Hz. The range needs at
     least two frequency bins: a recording's bin width is its sampling rate divided by its
     points per average.
   - **GOOD NOISE** and **DECENT NOISE** (pA²/Hz) - a cycle whose 1 Hz noise is below Good is
     shaded green, below Decent orange, and above Decent red.
   - **NOISE AXIS MIN** (pA²/Hz) - the lower end of the noise axes, where they meet in the
     middle of each panel.
   - **Noise bands** - untick it for a plain background.

3. **Click** **Plot**. The first plot of an experiment reads every PSD recording of every
   chosen channel, which takes some seconds per channel; a progress bar shows each channel's
   progress. Plotting again with the same experiment and fit range redraws at once, even for
   other thresholds or a subset of the channels. Changing the fit range, or editing the
   experiment's settings, computes the noise again.

Reading the plot
----------------

Each channel has one panel. The black points are the measured pore size and the dashed
lines its target band, against the left axis. The right axes are logarithmic: the red
diamonds in the top half are the 1 Hz noise at positive bias, and the blue diamonds in the
bottom half the noise at negative bias, with that axis inverted so that more noise points
away from the dividing line in both halves. Both noise axes share one range across every
channel, so channels compare at a glance. A channel whose pore size is 0 in every cycle is
greyed out as disabled.

.. note::

   A PSD recording shorter than its points per average is still analysed, as one shorter
   segment, and the status panel says which one. Its frequency bins are wider than the
   others', so check its fit range has at least two of them.

Step 3: Exporting
-----------------

**Click** **Export Plot Data** to save the plotted pore sizes and 1 Hz noise values of every
channel to a CSV file.

.. note::

   This tab records **Plot** for the session, so loading or restoring a session can draw
   the last plot again. A replayed plot computes in the background like any other, and is
   drawn when it finishes. A plot whose 1 Hz noise does not finish for every channel is
   still drawn, without that noise, but is not saved in the session, and the status panel
   says so; in a replay it stops the tab's replay and asks whether to **Go back** or
   **Keep**.

Single PSD recordings
---------------------

To look at one PSD recording in detail - its full spectrum and the fit through it - load it
in the :ref:`rawdata-tab` with ``NIBinaryReader`` and use **Update PSD** with the fit
switched on in **PSD Options**.
