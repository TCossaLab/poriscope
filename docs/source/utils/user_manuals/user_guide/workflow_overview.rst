.. _workflow_overview:

Workflow Overview
=================


Each tab has its own page with the details: :ref:`rawdata-tab`, :ref:`eventAnalysis-tab`,
:ref:`metadata-tab`, :ref:`clustering-tab`, :ref:`protein-tab` and :ref:`conditioning-tab`.

1. Raw Data
-----------

- The user selects a raw data file using a compatible reader plugin (e.g., ``ChimeraReaderVC400``, ``BinaryReader1X``).
- Available metadata (duration, number of channels, sampling rate, etc.) is extracted and displayed.
- Users choose the desired channel(s), time ranges, and optionally apply filters for preprocessing the data.
- Live previews allow validation of selected parameters before further analysis.
- Users initiate event detection within one or more time ranges for selected channels.
- Event-finder plugins (e.g., ``ClassicBlockageFinder``) scan the filtered signal to identify translocation events or blockages.
- Progress is tracked through per-task progress bars, and results are dynamically updated within the view.
- The system supports multithreaded execution, allowing multiple event-finding operations to run in parallel.
- Found events are committed to an event database, together with experiment metadata such as voltage.

2. Event Analysis
-----------------

- Users load a committed event database and fit each event with an event-fitter plugin (e.g., ``CUSUM``).
- The fitted metadata (sublevels, baseline current, etc.) is written to a metadata database for the tabs below.

3. Metadata Handling
--------------------

- Metadata related to fitted events can be viewed, filtered, and exported.
- Users can create visualizations such as histograms, scatterplots, density plots, and heatmaps.
- SQL-like filters enable interactive data subsetting.
- Plot configurations can be saved and reloaded, and filtered subsets exported for external use.

4. Clustering
-------------

- Users group events into clusters over up to 8 metadata columns, with **HDBSCAN** or
  **Gaussian Mixtures**, optionally restricted by an SQL-like filter.
- Clusters are shown in 2D or 3D, can be merged by hand, and are committed back to the
  database as new columns (``cluster_label``, ``cluster_confidence``).

5. Protein
----------

- From a database of fitted events and the pore's diameter and length, users estimate a
  translocating protein's volume and shape factor, one event at a time (**Individual**) or
  over the distribution of many events (**Ensemble**).

Pore conditioning
-----------------

- Separately from the event workflow, the Conditioning tab follows a pore conditioning
  experiment cycle by cycle: each channel's pore size against its target band, and the
  noise of the PSD recordings taken along the way.

.. admonition:: Need a visual guide through Poriscope? 

   Check out the :ref:`tutorial` for a full walkthrough of the interface and workflow.