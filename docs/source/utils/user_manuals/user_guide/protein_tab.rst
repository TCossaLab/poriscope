.. _protein-tab:

Protein Tab
============

The **Protein Tab** estimates the size and shape of a translocating protein from its nanopore blockage signal. Given the pore's diameter and length, it fits a two-population (prolate/oblate) volume-and-shape-factor model to either a single event at a time (**Individual** mode) or the aggregate distribution across many events (**Ensemble** mode), using Monte Carlo rejection sampling to recover the most likely volume and shape factor for each population.

.. Add a ProteinView.png screenshot here once available, following the pattern used by the other tab pages.

Step 1: Load a Fitted Events Database
--------------------------------------

1. Click the **➕** beside **DB LOADER** to load a database of fitted events (the output of the Event Analysis tab's **Commit Events**).
2. A plugin dialog (e.g., ``SQLiteDBLoader``) will appear. Enter a **Name** for the loader instance and select the database file.

Step 2: Choose Scope
---------------------

Click the **Scope** button and select **one experiment and one channel**. Everything starts
selected, but the fits and the event plots on this tab work on a single experiment,
channel and subset, and refuse a wider scope with a message.

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

   A bin count or width the tab cannot use is reported once on the status panel. Each
   event is binned over its own range.

   An event whose baseline is zero, or which has no samples between its paddings, cannot
   be turned into a fractional blockage. Its panel is left empty and it contributes
   nothing to **Export Plot Data**, with the reason written to the log.

Step 6: Generate the Fit
--------------------------

Click **Update Plot** to run the fit for the current mode. This draws:

- A ΔI/I histogram, or a Peak Scatterplot in Individual mode.
- The Prolate/Oblate volume vs. shape-factor solutions on the second plot.

.. note::

   A distribution the tab cannot draw is refused on the status panel with the reason:
   more than one experiment, channel or subset in scope, an experiment with no channel
   selected, or no usable events. The previous plot stays on screen.

Step 7a: Commit Individual Fits
----------------------------------

In **Individual** mode, once a fit has been generated, click **Commit Individual** to write the per-event fit results to the database. If the target columns already exist, you'll be prompted before anything is overwritten.

Each event's row gets the median prolate and oblate volume, shape factor and semi-axes, its two fitted blockages and their standard deviations, and two **reachable fractions**:

- ``prolate_reachable_fraction`` and ``oblate_reachable_fraction`` are the share of the event's fitted blockage distribution that some prolate, or oblate, spheroid fitting the pore can produce. Near 1, the fit is well inside what that shape can do; near 0, no spheroid of that shape matches it, and any geometry sampled for it lies on the edge of what that shape can do, nearest the fit; about 0.5, the fit is centred on that edge. The standard deviations are taken as at least 1% of their mean, as the sampling does.
- To keep only events a shape can explain, commit, then add a subset filter on the column (for example ``prolate_reachable_fraction >= 0.5``), select it, and run **Update Plot** again.

Committing over a fit made by an earlier version replaces it and adds any columns that version did not write.

Step 7b: Report Ensemble Fit
-------------------------------

In **Ensemble** mode, click **Report All** to display the double-Gaussian fit parameters (peak amplitude, mean, standard deviation) for the current binning, the Prolate and Oblate reachable fractions of the fit (see Step 7a), and median ± standard deviation summaries of Prolate and Oblate volume, ``a``, ``b``, and shape factor ``m`` from the Monte Carlo sample. Ensemble mode has no single event to write a database row against, so this is display-only.

Step 8: Apply Filters
-----------------------

You can restrict the events included in a fit to a named subset filter, created, edited and
saved exactly as in the Metadata tab (see :ref:`filtering-and-querying`). Select **at most
one** subset for a fit or plot. A Raw SQL filter scopes itself with ``:experiment_id`` and
``:channel_id``, and must return ``event_id`` to be used for the distribution plots,
**Plot Events** and **Plot Histogram**.

Step 9: Export Plot Data
---------------------------

Click **Export Plot Data** to save the data currently shown in your plots to disk.

Step 10: Inspect Individual Events
-------------------------------------

**Plot Events**, its arrows and **RAW** work as in the Metadata tab (see Step 5 of
:ref:`metadata-tab`); here the starting field is **EVENT ID**. **Plot Histogram** draws a
ΔI/I histogram of the same events instead of their traces.

.. note::

   This tab records **Update Plot**, **Plot Events** and **Plot Histogram** for the session, so loading or restoring it can replay
   them; see :ref:`replay_actions`.
