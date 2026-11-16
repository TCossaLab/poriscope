.. _rawdata-tab:

Raw Data Tab
============

The **Raw Data Tab** allows users to load raw current traces from nanopore experiments, apply filters before analysis, determine the baseline, and detect events.

.. image:: /_static/images/RawDataView.png
   :alt: Raw Data View
   :align: center

Step 1: Loading Your Data
--------------------------

1. **Click** the **➕** beside **READER** to load a data file.

2. A dropdown menu will appear listing supported reader types. These correspond to different file formats and decoding standards. Supported readers include:

   - ``ABFReader`` (for any `.abf` file; its settings choose the ADC channel that records current and the sweep to read, -1 for every sweep back to back), and ``TCossaLabABFReader`` and ``LegacyElementsReader`` (for `.abf` recordings from the lab's own setups, with those settings fixed)
   - ``BinaryReader1X`` and ``SingleBinaryDecoder`` (for `.bin`-like formats), and ``NIBinaryReader`` (for the `.bin` files of the lab's NI DAQ setups: 16 channels in mV, with the sample rate read from the file name and the amplifier's **Sensitivity** in pA/V converting to pA)
   - ``ChimeraReader20240101``, ``ChimeraReader20240501``, ``ChimeraReaderVC100`` (for Chimera system `.log` files or variations; ``ChimeraReader20240101`` is deprecated and will be removed in a future release)

.. note::

   Make sure the reader you choose matches your file type, otherwise loading will fail.

.. note:: Don't have a file to try this with?

   The ``.log`` files of the tutorial dataset (:ref:`tutorial_dataset`) work with
   ``ChimeraReader20240501``.

3. A plugin settings dialog will prompt you to:

   - Enter a **name** for the reader instance; it is prefilled (e.g., ``TCossaLabABFReader_0``).
   - Select the **input file** using the **Select Input File** button.

4. After loading the file, **select a channel** from the **Channel** dropdown menu.

5. In the time-range field, **enter a start-end range** in seconds (e.g., ``0-5`` or ``1.5-6.3``).

6. **Click** the **Update Trace** button to visualize the raw signal.

7. *(Optional)* To analyze noise across frequencies, **click** the **Update PSD** button.

   **PSD Options** beside it sets how the PSD is computed and what is drawn over it:

   - **Points per Average** - the samples in each Welch segment; one frequency bin is the sample rate divided by this. 0 uses a tenth of the range.
   - **Overlap** - how much consecutive segments overlap, in percent; 0 averages separate segments, as the NI DAQ acquisition software does.
   - **Fit 1/f**, **Fit Start** and **Fit End** - fit a straight line to log PSD against log frequency over that range (Hz), draw it, and read it off at 1 Hz. The 1 Hz value appears in each channel's legend and, for every channel, on the status panel. The range needs at least two frequency bins.
   - **Good Noise** and **Decent Noise** (pA²/Hz) - with the fit on, a channel whose 1 Hz value is below Good is shaded green, below Decent orange, and above Decent red.

Step 2: Applying a Filter
-------------------------

1. **Click** the **➕** beside **FILTER** to apply a preprocessing filter.

2. A dropdown will appear listing available filters:

   - ``BesselFilter`` – features a smooth response to signal transients, ideal for reducing high-frequency noise.
   - ``WaveletFilter`` – preserves pulse shape and SNR while denoising using a wavelet transform.

3. A plugin settings dialog will appear, depending on the selected filter:

**For ``BesselFilter``:**

- ``Name``: Identifier for the filter instance (prefilled, e.g. ``BesselFilter_0``).
- ``Cutoff`` (Hz): Frequency above which signals are attenuated.
- ``Samplerate`` (Hz): Sampling rate of the signal.
- ``Poles``: Number of poles in the filter; higher values give a steeper roll-off.

**For ``WaveletFilter``:**

- ``Name``: Identifier for the filter instance (prefilled, e.g. ``WaveletFilter_0``).
- ``Wavelet``: Wavelet basis, ``bior1.3`` or ``bior1.5`` (the default).

4. After configuration, confirm by clicking **OK**.


Step 3: Finding Events
----------------------

1. **Click** the **➕** beside **EVENTFINDER** to load an event detection algorithm.

2. A dropdown will appear listing available event finders:

   - ``ClassicBlockageFinder`` — detects events based on a current threshold.
   - ``ThresholdBlockageFinder`` — the same, with the threshold given in baseline standard deviations.
   - ``BoundedBlockageFinder`` — the same as ``ClassicBlockageFinder``, with the baseline fit restricted to a window you set.

3. A settings window will appear. All three finders share these parameters:

**Shared Parameters:**

- ``Threshold``: How far below the fitted baseline the signal must fall for an event to be detected - in pA for ``ClassicBlockageFinder`` and ``BoundedBlockageFinder``, in σ for ``ThresholdBlockageFinder``. The threshold decides *whether* there is an event; where it begins and ends is judged against the baseline itself (see the note below).
- ``Min Duration`` (µs): Minimum allowed duration for an event.
- ``Max Duration`` (µs): Maximum allowed duration for an event.
- ``Min Separation`` (µs): An event that starts closer than this to the end of the previous one is rejected, not merged.

.. note::

   The threshold decides *whether* there is an event. Its recorded start and end are where
   the signal leaves and rejoins the baseline band (three samples in a row within three
   baseline standard deviations), not the threshold crossings, and the padding stored
   around each event is baseline from those points outward.

**BoundedBlockageFinder-only:**

- ``Min Baseline`` / ``Max Baseline`` (pA), required: The window the baseline fit is restricted to; a fitted baseline outside it is refused.

4. *(Optional)* To limit detection to part of the recording, **click** the **⏱** button beside
   **Find Events**. It sets the time ranges for the selected event finder, one field per
   channel, as comma-separated start-end ranges in seconds (e.g. ``0.0-2.5, 3.0-6.0``).
   ``0-0`` means the whole signal, and an end of ``0`` or no end at all means "to the end",
   so ``9-0`` and ``9-`` both run from 9 seconds to the end.

5. **Click** the **Find Events** button to run the detection process. With **No Filter** selected you are asked to confirm first, since finding events on unfiltered data is rarely intended.

.. note::

   A Find that you cancel, that fails, or that finds no events leaves the channel without events,
   and is not saved in the tab's history. An earlier Find on that channel is removed from the
   history too, with any events plotted from it, since the channel no longer holds them; the
   right-hand panel says so.

6. Once events are detected (you will see confirmation in the right-hand panel), **enter the event indices** you wish to inspect.

7. **Click** the **Plot Events** button to visualize those events.

8. **Use** the **◀ and ▶ arrows** to browse between plotted events.

Step 4: Writing Events
----------------------

1. **Click** the **➕** beside **WRITER** to select a module for saving your detected events.

2. A configuration dialog will appear. If you're using ``SQLiteEventWriter``, you'll be prompted to fill in the following fields:

   - ``Output File``: Path where the SQLite database will be saved (``.sqlite3``, ``.db`` or ``.sqlite``).
   - ``Experiment Name``: A short label to identify this experiment in the database.
   - ``Voltage`` (mV): The applied transmembrane potential during the experiment.
   - ``Membrane Thickness`` (nm): Thickness of the nanopore membrane.
   - ``Conductivity`` (S/m): Conductivity of the solution during the experiment.

3. After confirming the settings, **click** the **Commit Events** button to write the selected events to the database.
   If the database already holds events for a channel, you are asked before they are replaced, and the question
   warns you when those events were committed under a different experiment name. Answering **No** keeps that
   channel's events and skips only it; the other channels are still committed.

4. *(Optional)* You can **click** the **Export Plot Data** button at any time to save the data behind the current graph as a `.csv` file.

.. note::

   This tab records **Update Trace**, **Update PSD**, **Find Events** and **Plot Events** for the session, so loading or restoring it can replay
   them; see :ref:`replay_actions`.
