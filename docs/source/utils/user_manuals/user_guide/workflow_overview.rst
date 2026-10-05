.. _workflow_overview:

Workflow Overview
=================


For in-depth information, visit the following sections:

- :ref:`rawdata-tab`
- :ref:`eventAnalysis-tab`
- :ref:`metadata-tab`
- :ref:`clustering-tab`
- :ref:`protein-tab`

1. Raw Data
-----------

- The user selects a raw data file using a compatible reader plugin (e.g., ``ChimeraReader20240501``, ``BinaryReader1X``).
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

- Users can group events into clusters based on selected metadata features.
- Two clustering algorithms are supported:

  - **HDBSCAN**:
    - Requires ``Cluster Size`` (minimum cluster size to form a group),``Min Points`` (minimum samples to define a core point), and ``Sensitivity`` (controls how aggressively clusters are split).
  
  - **Gaussian Mixtures**:
    - Requires only ``Number of Clusters`` to define how many Gaussian components will be used.

- Every column row in the settings dialog is used; two are provided and **Add Column** adds more, up to 8.
- Optional filters can be applied to restrict the input data using SQL-like syntax.
- Users can visualize clusters in 2D or 3D, merge selected clusters manually, and commit results back to the database as new columns (``cluster_label``, ``cluster_confidence``).

.. admonition:: Need a visual guide through Poriscope? 

   Check out the :ref:`tutorial` for a full walkthrough of the interface and workflow.