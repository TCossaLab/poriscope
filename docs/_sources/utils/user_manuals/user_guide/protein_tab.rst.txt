.. _protein-tab:

Protein Tab
============

The **Protein Tab** estimates the size and shape of a translocating protein from its nanopore blockage signal. Given the pore's diameter and length, it fits a two-population (prolate/oblate) volume-and-shape-factor model to either a single event at a time (**Individual** mode) or the aggregate distribution across many events (**Ensemble** mode), using Monte Carlo rejection sampling to recover the most likely volume and shape factor for each population.

.. Add a ProteinView.png screenshot here once available, following the pattern used by the other tab pages.

Step 1: Load a Fitted Events Database
--------------------------------------

1. Click the **➕** button to load a database of fitted events (the output of the EventAnalysis tab's ``Commit``).
2. A plugin dialog (e.g., ``SQLiteDBLoader``) will appear. Enter a custom **Name** for the loader instance and select the SQLite ``.db`` file to load.

Step 2: Choose Scope
---------------------

Click the **Scope** button to select which experiments and channels contribute to the current plot. By default, everything is selected.

Step 3: Enter Pore Geometry
-----------------------------

Enter the **pore diameter** and **pore length**, in nanometers, in their respective fields. Both are required for the volume/shape-factor fit; without them, the physical model has no way to convert a blockage fraction into a volume.

Step 4: Choose a Fitting Mode
-------------------------------

Select **Individual** to fit each event separately, or **Ensemble** to fit one shared volume/shape-factor distribution across every event currently in scope.

.. note::

   Individual and Ensemble modes keep fully independent plots and fit state. Switching modes shows that mode's own last-drawn plot immediately, with no need to re-run **Update Plot**, and never overwrites the other mode's results.

Step 5: Configure Sampling and Binning
-----------------------------------------

1. Set **N**, the number of Monte Carlo samples used to estimate volume and shape factor for each population.
2. Specify the histogram **bins** as a count (e.g., ``50``), or check **Sizes** to specify bin widths instead.

.. note::

   A bin count or width the tab cannot use is reported once on the status panel, rather
   than once per event in the log.

   **Each event is binned over its own range.** In Individual mode the range used to
   accumulate across the events of a plot, so the bins an event was drawn on depended on
   how many events preceded it; both per-event paths follow the same rule now.

   An event whose baseline is zero, or which has no samples between its paddings, cannot
   be turned into a fractional blockage. Its panel is left empty and it contributes
   nothing to **Export Plot Data**, with the reason written to the log.

Step 6: Generate the Fit
--------------------------

Click **Update Plot** to run the fit for the current mode. This draws:

- A ΔI/I (or volume) histogram, or a Peak Scatterplot in Individual mode.
- The Prolate/Oblate volume vs. shape-factor solutions on the second plot.

.. note::

   A distribution the tab cannot draw is refused on the status panel with the reason:
   more than one experiment or channel in scope, or an experiment with no channel
   selected. It used to write the reason to the log only and draw nothing.

Step 7a: Commit Individual Fits
----------------------------------

In **Individual** mode, once a fit has been generated, click **Commit Individual** to write the per-event fit results to the database. If the target columns already exist, you'll be prompted before anything is overwritten.

Step 7b: Report Ensemble Fit
-------------------------------

In **Ensemble** mode, click **Report All** to display the double-Gaussian fit parameters (peak amplitude, mean, standard deviation) for the current binning, along with median ± standard deviation summaries of Prolate and Oblate volume, ``a``, ``b``, and shape factor ``m`` from the Monte Carlo sample. Ensemble mode has no single event to write a database row against, so this is display-only.

Step 8: Apply Filters
-----------------------

You can restrict the events included in a fit to a named subset:

1. Click the **➕** filter button to define a new filter. Raw SQL filters can be saved and loaded but cannot be selected for a plot.
2. Use the filter dropdown to choose which saved subset(s) are active for the current plot.
3. Click the info/edit button next to the dropdown to view or modify the currently selected subset.
4. Click the delete button to remove selected subsets (individual ones can also be removed directly from the dropdown).
5. Use **Save Filter** / **Load Filter** to persist subsets for future sessions.

Step 9: Export Plot Data
---------------------------

Click **Export Plot Data** to save the data currently shown in your plots to disk.

Step 10: Inspect Individual Events
-------------------------------------

1. Use **Scope** to select exactly one experiment and channel.
2. Enter a starting **event ID** and the number of events to visualize.
3. Click **Plot Events** to view raw/filtered/fitted traces, or **Plot Histogram** for a ΔI/I histogram, for the selected events.
4. Use the left/right arrow buttons to step through events in the filtered set.
5. Check the **RAW** box to overlay the unfiltered raw signal alongside the filtered and fitted traces.
