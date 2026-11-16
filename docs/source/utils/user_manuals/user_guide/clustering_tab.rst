.. _clustering-tab:

Clustering Tab
==============

The **Clustering Tab** allows you to group similar events based on selected metadata features using clustering algorithms such as **HDBSCAN** and **Gaussian Mixtures**. It is designed to uncover patterns and groupings within large sets of fitted nanopore event data.

.. image:: /_static/images/ClusteringView.png
   :alt: Clustering View
   :align: center

Step 1: Load Metadata Database
------------------------------

1. Click the **➕** beside **DB LOADER** to select your fitted events database.
2. If you have previously loaded DB files, they will automatically appear. 

Step 2: Configure Clustering Settings
-------------------------------------

1. Click the **Cluster Settings** button.

   Inside the dialog:

   - **Select Method**: Choose one of the following:
     
   - **HDBSCAN** groups points by density, finds the number of clusters itself, and labels
     low-confidence points as noise:

     - ``Cluster Size``: the minimum number of points a cluster must contain. Larger
       values give fewer, larger clusters.
     - ``Min Points``: how dense a region must be to form a cluster. Higher values are
       more conservative.
     - ``Sensitivity``: a distance, in the units of the clustered columns after **LOG**
       and **NORM**, below which clusters are merged (HDBSCAN's
       ``cluster_selection_epsilon``). 0 merges nothing; higher values give fewer, larger
       clusters.

   - **Gaussian Mixtures** fits a mixture of Gaussian distributions:

     - ``Number of Clusters``: how many Gaussian components to fit.

   - **FILTER** *(optional)*: an Assisted SQL condition (see :ref:`filtering-assisted`)
     that narrows which events are clustered, applied to the whole database - there is no
     scope here. Example: ``duration > 200 and max_blockage < 800``

   - **Select Columns**: Choose a metadata column to use for clustering.
     
     You may optionally enable:

     - **LOG**: Apply log10 scaling.
     - **NORM**: Normalize using median absolute deviation.
     - **PLOT**: Include in the clustering visualization.

   - **Add Column**: The dialog starts with two column rows, and every row is used.
     **Add Column** adds another, up to 8.

     .. note::

        **Apply** stays disabled until a method is chosen and each of its parameters
        holds a valid value, every row has a column, and 2 or 3 rows are ticked
        **PLOT**; the line above the buttons says what is missing. The parameters
        take scikit-learn's own minimums: ``Cluster Size`` at least 2, ``Min Points``
        and ``Number of Clusters`` at least 1, and ``Sensitivity`` at least 0.


   - Click **Apply** to launch the clustering process, or **Cancel** to discard changes.

.. note::

   Anything that stops a clustering run is reported on the status panel - a filter the
   database rejects is shown with the database's own message.

Step 3: Merge Clusters (Optional)
---------------------------------

After clustering is complete:

1. Use the ``KEEP LABEL`` and ``MERGE WITH`` dropdowns to select two different clusters.
2. Click **Merge** to reassign all events in the ``MERGE`` cluster to the ``KEEP`` cluster. The
   status panel says how many events moved; the same label in both dropdowns is refused.


Step 4: Commit Cluster Labels
-----------------------------

Click **Commit** to write the clustering results to your metadata database.

- Adds two new columns: ``cluster_label`` and ``cluster_confidence``.
- If the table already contains clustering data, you will be prompted before overwriting.

Step 5: Export Plot Data
------------------------

Click **Export Plot Data** to save the current clustering visualization as a csv file.

.. note::

   This tab records a clustering run (**Apply** in **Cluster Settings**) and **Merge** for the session, so loading or restoring it can replay
   them; see :ref:`replay_actions`.
