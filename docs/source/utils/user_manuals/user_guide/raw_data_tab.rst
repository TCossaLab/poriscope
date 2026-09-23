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

   - ``TCossaLabABFReader`` and ``LegacyElementsReader`` (for `.abf` files)
   - ``BinaryReader1X`` and ``SingleBinaryDecoder`` (for `.bin`-like formats)
   - ``ChimeraReader20240101``, ``ChimeraReader20240501``, ``ChimeraReaderVC100`` (for Chimera system `.log` files or variations; ``ChimeraReader20240101`` is deprecated and will be removed in a future release)

.. note::

   Make sure the reader you choose matches your file type, otherwise loading will fail.

.. note:: Don't have a file to try this with?

   The dataset used in the YouTube tutorial series is archived on the Federated
   Research Data Repository (FRDR), and its ``.log`` files work with
   ``ChimeraReader20240501``:

   `DOI: 10.20383/103.01695 <https://doi.org/10.20383/103.01695>`_

3. A plugin settings dialog will prompt you to:

   - Enter a **name** for the reader instance (e.g., ``TCossaLabABFReader_1``).
   - Select the **input file** using the **Select Input File** button.

4. After loading the file, **select a channel** from the **Channel** dropdown menu.

5. In the time-range field, **enter a start-end range** in seconds (e.g., ``0-5`` or ``1.5-6.3``).

6. **Click** the **Update Trace** button to visualize the raw signal.

7. *(Optional)* To analyze noise across frequencies, **click** the **Update PSD** button.

Step 2: Applying a Filter
-------------------------

1. **Click** the **➕** beside **FILTER** to apply a preprocessing filter.

2. A dropdown will appear listing available filters:

   - ``BesselFilter`` – features a smooth response to signal transients, ideal for reducing high-frequency noise.
   - ``WaveletFilter`` – preserves pulse shape and SNR while denoising using a wavelet transform.

3. A plugin settings dialog will appear, depending on the selected filter:

**For ``BesselFilter``:**

- ``Name``: Identifier for the filter instance (e.g., ``BesselFilter_1``).
- ``Cutoff`` (Hz): Frequency above which signals are attenuated.
- ``Samplerate`` (Hz): Sampling rate of the signal.
- ``Poles``: Number of poles in the filter; higher values give a steeper roll-off.

**For ``WaveletFilter``:**

- ``Name``: Identifier for the filter instance (e.g., ``WaveletFilter_1``).
- ``Wavelet``: Wavelet basis, ``bior1.3`` or ``bior1.5`` (the default).

.. note::

   Filters help improve event detection by removing baseline drift or noise. Choose the one that best suits your data characteristics.

4. After configuration, confirm by clicking **OK**.

5. *(Optional)* Adjust the **Time Range** using the **⏱ Timer button** to limit the region of interest.


Step 3: Finding Events
----------------------

1. **Click** the **➕** beside **EVENTFINDER** to load an event detection algorithm.

2. A dropdown will appear listing available event finders:

   - ``ClassicBlockageFinder`` — detects events based on a current threshold.
   - ``ThresholdBlockageFinder`` — the same, with the threshold given in baseline standard deviations.
   - ``BoundedBlockageFinder`` — detects events constrained within user-defined amplitude and baseline bounds.

.. note::

   Choose the event finder based on the expected characteristics of your signal. All three share the parameters below but differ in flexibility.

3. A settings window will appear with the following configurable parameters:

**Shared Parameters:**

- ``Threshold``: How far below the fitted baseline the signal must fall for an event to start - in pA for ``ClassicBlockageFinder`` and ``BoundedBlockageFinder``, in σ for ``ThresholdBlockageFinder``.
- ``Min Duration`` (µs): Minimum allowed duration for an event.
- ``Max Duration`` (µs): Maximum allowed duration for an event.
- ``Min Separation`` (µs): Minimum time between consecutive events to treat them as distinct.

**BoundedBlockageFinder-only:**

- ``Min Baseline`` / ``Max Baseline`` (pA), required: The window the baseline fit is restricted to; a fitted baseline outside it is refused.

.. note::

   For `ClassicBlockageFinder`, only a fixed threshold is required. For `BoundedBlockageFinder`, both the threshold and the baseline limits are needed.

4. **Click** the **Find Events** button to run the detection process. With **No Filter** selected you are asked to confirm first, since finding events on unfiltered data is rarely intended.

5. *(Optional)* Adjust the **Time Range** using the **⏱ Timer button** to limit the detection to specific intervals.

.. note::

   A range like ``0-0`` means “start to end” of the loaded signal. You can also specify ranges such as ``0-4``, ``6-7``, or open-ended intervals like ``9-0`` (9 seconds to the end). An omitted end has the same meaning as an end of ``0``, so ``3.0-`` and ``3.0-0`` both run from 3 seconds to the end of the signal.

6. Once events are detected (you will see confirmation in the right-hand panel), **enter the event indices** you wish to inspect.

7. **Click** the **Plot Events** button to visualize those events.

8. **Use** the **◀ and ▶ arrows** to browse between plotted events.

Step 4: Writing Events
----------------------

1. **Click** the **➕** beside **WRITER** to select a module for saving your detected events.

2. A configuration dialog will appear. If you're using ``SQLiteEventWriter``, you'll be prompted to fill in the following fields:

   - ``Output File``: Path where the SQLite `.db` file will be saved.
   - ``Experiment Name``: A short label to identify this experiment in the database.
   - ``Voltage`` (mV): The applied transmembrane potential during the experiment.
   - ``Membrane Thickness`` (nm): Thickness of the nanopore membrane.
   - ``Conductivity`` (S/m): Conductivity of the solution during the experiment.

.. note::

   The results generated during the eventfinding process are stored in a **SQLite database**, allowing for efficient access, export, and integration with downstream tools.

3. After confirming the settings, **click** the **Commit Events** button to write the selected events to the database.

4. *(Optional)* You can **click** the **Export Plot Data** button at any time to save the data behind the current graph as a `.csv` file.
