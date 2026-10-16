.. _filtering-and-querying:

Filtering and Querying
======================

A **filter** picks which events a plot, an event view or an export uses. Poriscope supports two
modes: **Assisted SQL** and **Raw SQL**. Both are available in any tab that supports filters,
including the :ref:`metadata-tab`.

The mode you choose when you create a filter is permanent and is encoded in the filter's name
(``_assisted`` or ``_raw``). Filters can be saved to a JSON file and reloaded in later sessions;
see :ref:`saving-and-loading-filters`.

.. image:: /_static/images/FilterDialog.png
   :alt: Add Filter Dialog
   :align: center

.. toctree::
   :maxdepth: 1
   :caption: The two filter modes

   filtering_assisted
   filtering_raw

Start here
----------

Three things to know before the details:

1. **Scope** chooses the experiments and channels. Everything starts ticked.
2. **The filter** says which events you want. You write it as a condition (**Assisted SQL**) or as a
   complete query (**Raw SQL**).
3. **The plot** runs the filter once for each ticked experiment and channel and draws each result as
   its own dataset.

.. _choosing-a-mode:

Choosing a mode
---------------

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * -
     - :ref:`Assisted SQL <filtering-assisted>`
     - :ref:`Raw SQL <filtering-raw>`
   * - **You write**
     - A condition, such as ``duration > 150``
     - A complete ``SELECT``
   * - **The experiment and channel**
     - Added for you
     - You add them with ``:experiment_id`` and ``:channel_id``
   * - **The columns**
     - Chosen by Poriscope from the axes you pick
     - Chosen by you (start with ``event_id``)
   * - **Good for**
     - Everyday filters; no SQL needed
     - Top-N, aggregates, computed or joined results
   * - **Watch out for**
     - Little to watch for: the scope is always applied
     - Leaving the placeholders out, or an unbracketed ``OR``

One filter, two modes
---------------------

The same filter, "events longer than 150 µs", written both ways. The numbers come from the small
:ref:`example database <example-database>` below, for experiment 1, channel 2, whose events over
150 are 200 and 210.

.. list-table::
   :header-rows: 1
   :widths: 18 41 41

   * -
     - Assisted SQL
     - Raw SQL
   * - **What you write**
     - ``duration > 150``
     - ``SELECT event_id, duration FROM events WHERE duration > 150 AND experiment_id = :experiment_id AND channel_id = :channel_id``
   * - **What Poriscope runs for experiment 1, channel 2**
     - ``SELECT e.id, e.experiment_id, e.channel_id, e.event_id, e.duration FROM events e WHERE (e.duration > 150) AND ((experiment_id = 1 AND channel_id IN (2)))``
     - ``SELECT event_id, duration FROM events WHERE duration > 150 AND experiment_id = 1 AND channel_id = 2``
   * - **Rows for that pair**
     - 2 (200 and 210)
     - 2 (200 and 210)
   * - **Who adds the scope**
     - Poriscope, always
     - You, with the two placeholders
   * - **Who chooses the columns**
     - Poriscope, from the axes you pick
     - You

Both give the same two events. The difference is who writes the scope and the columns. For more
details see :ref:`Assisted SQL filters <filtering-assisted>` and :ref:`Raw SQL filters <filtering-raw>`.

.. _example-database:

The example database
~~~~~~~~~~~~~~~~~~~~

The examples in this guide that give numbers use this tiny database, so you can paste it into a
SQLite viewer such as `DB Browser for SQLite <https://sqlitebrowser.org/>`_ and run every query
yourself. It is made up for the guide and has nothing to do with your data.

.. code-block:: sql

   CREATE TABLE events (experiment_id INTEGER, channel_id INTEGER, event_id INTEGER, duration REAL);
   INSERT INTO events VALUES
     (1,1,0,120), (1,1,1,180),
     (1,2,0,200), (1,2,1,90), (1,2,2,210),
     (2,2,0,160), (2,2,1,140), (2,2,2,230);

It holds two experiments. Experiment 1 has channels 1 and 2, and experiment 2 has channel 2. Five
of the eight events last longer than 150.

.. _how-scope-works:

How scope works
---------------

The **Scope** button lists every experiment and channel in the database, and everything starts
ticked (at least one must stay ticked). When you plot, Poriscope takes the ticked experiments and
channels **one pair at a time**, runs each ticked filter once for that pair, and draws the rows
that come back as one dataset, labelled with the pair and given its own colour.

* In an **Assisted** filter the pair is added to the query for you.
* In a **Raw** filter the pair is *not* added for you. ``:experiment_id`` and ``:channel_id`` stand
  for the pair being plotted, and Poriscope replaces them with that pair's database numbers before
  running the query. A query without them is run the same way for every pair.

For more details see :ref:`Scoping with placeholders <raw-scoping>` and
:ref:`What leaving a placeholder out does <raw-leaving-placeholder-out>`.

Creating a Filter
-----------------

1. Click the **➕** button next to the Filter dropdown.
2. Enter a **name** for the filter.
3. Select the mode using the **Assisted SQL** or **Raw SQL** radio buttons.
   The empty **Filter** box shows an example for the mode you chose (press **Tab** to insert it), and an **info icon** beside the chosen mode
   says, when you hover over it, how to write a filter in that mode and where to read more
   (Help → Help → Documentation, then User Guide → Filtering and Querying). In Raw SQL mode it says
   to add ``WHERE experiment_id = :experiment_id AND channel_id = :channel_id`` to follow the Scope
   selection, and to start with ``SELECT event_id, ...``.
4. Enter the filter expression or query in the **Filter** field.
5. Click **OK**.

The filter is saved with a suffix indicating its mode (``_assisted`` or ``_raw``) and appears
in the filter dropdown immediately.

.. note::

   The mode radio buttons are locked once a filter is created. To change mode, delete the
   filter and recreate it. This is by design — assisted filters contain WHERE clauses and
   raw filters contain complete SELECT statements. These formats are incompatible and cannot
   be safely converted.

Editing a Filter
----------------

1. Select exactly one filter from the filter dropdown.
2. Click the **pencil** (edit) icon.
3. Update the name or filter text as needed.
4. Click **OK**.

The mode (Assisted or Raw) is shown but cannot be changed during editing.

.. warning::

   For Raw SQL filters, the updated text must still begin with ``SELECT`` or the edit
   will be rejected.

.. _saving-and-loading-filters:

Saving and Loading Filters
--------------------------

Your filters are kept in two ways, and they do different jobs.

**Your session keeps them for you.** Filters are part of the session: **File → Save Session** stores
them with the rest of your workspace, and the session Poriscope saves when you quit brings them back
the next time you use **File → Restore Session** (see :ref:`menus_and_sessions`). This covers both
the Metadata and the Protein tab, and Assisted and Raw filters alike. A filter changed in the open
tab, such as one that gained ``event_id`` when you answered Yes to the question, is kept this way too.

**A filters file is for moving them around.** **Save Filter** writes the tab's filters to a ``.json``
file of their own, and **Load Filter** reads one back, so you can share filters with someone else,
keep a set for one kind of database, or update a file after changing a filter:

- **Save Filter**: Exports all current filters to a ``.json`` file. Both ``_assisted``
  and ``_raw`` filters are included.
- **Load Filter**: Imports filters from a ``.json`` file. Raw filters are restored
  directly without re-validation, but a filter that writes is never run. Assisted filters are
  re-validated against the selected loader's database before being added; if no loader is
  selected, they are added unvalidated and a warning is written to the log.

The saved JSON format looks like:

.. code-block:: json

   {
       "long_events_assisted": "duration > 100",
       "multi_sublevel_raw": "SELECT event_id, duration FROM events WHERE experiment_id = :experiment_id AND channel_id = :channel_id AND id IN (SELECT event_db_id FROM sublevels GROUP BY event_db_id HAVING COUNT(*) > 3)"
   }

.. note::

   If any filter name in the file conflicts with an existing filter, no filters from
   that file will be loaded — the load is all or nothing, so you are never left guessing
   which half arrived.

.. note::

   A file that cannot be read — missing, unreadable, not valid JSON, or holding anything
   other than an object of filter names and filter text — is reported on the status
   panel, and the filters you already have are left exactly as they were. That includes
   a **session** file, which is also a JSON object: it is refused whole rather than
   importing its plugin names as filters. A **save** that fails, on a full disk or a
   read-only folder, is reported there too; it used to look exactly like a save that
   worked.

Which plots take a filter
-------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Action
     - Assisted
     - Raw
   * - Update Plot: Histogram, Normalized and Categorical Histogram, Kernel Density,
       Scatterplot, 3D Scatterplot
     - Works
     - Needs the plotted columns in the result; a column of another table (``sublevel_duration``)
       needs a join, which the status panel shows. Drawn once for each ticked channel
   * - Update Plot: Heatmap
     - Works, one experiment, one channel and one filter
     - Needs the plotted columns in the result, one experiment, one channel and one filter
   * - Update Plot: Raw and Filtered All Points Histograms (and normalized)
     - Works
     - Needs ``event_id``. Drawn once for each ticked channel
   * - Update Plot: Raw and Filtered Event Overlay
     - Works, one experiment, one channel and one filter
     - Needs ``event_id``, one experiment, one channel and one filter
   * - Plot Events and the event arrows (Metadata and Protein)
     - Works, one filter and one channel
     - Needs ``event_id``, one filter and one channel
   * - Protein tab: Update Plot (Ensemble), Plot Histogram
     - Works, one filter and one channel
     - Needs ``event_id``, one filter and one channel
   * - Export Subset - CSV
     - Works, one filter
     - Works, one filter, with both placeholders in the query

Filters are never combined. Several filters ticked at once in the Metadata tab are drawn as
separate overlaid datasets, whether they are Assisted, Raw or a mixture of both; there is no AND or
OR between two saved filters. To combine conditions, write them into one filter. The Protein tab
and Export Subset - CSV take one filter only.

Common Mistakes
---------------

.. list-table::
   :header-rows: 1
   :widths: 28 44 28

   * - Mistake
     - Result
     - For more details
   * - WHERE clause entered in Raw SQL mode
     - Rejected at creation: a raw filter has to start with ``SELECT``
     - :ref:`Raw SQL filters <filtering-raw>`
   * - Full ``SELECT`` entered in Assisted mode
     - Refused: an Assisted filter cannot start with ``SELECT``, and the message says to use Raw SQL
     - :ref:`Assisted SQL filters <filtering-assisted>`
   * - Raw filter without ``:experiment_id`` / ``:channel_id``
     - Warning on the status panel; each ticked pair is plotted with everything the query finds, and
       the legend says "(rows not limited to this experiment and channel)"
     - :ref:`What leaving a placeholder out does <raw-leaving-placeholder-out>`
   * - Raw filter without ``event_id``, used for an event plot, Plot Events or the arrows
     - For a plain query Poriscope asks whether to add it, and the plot carries on if you say yes; otherwise the panel says what stops it
     - :ref:`Start with event_id <raw-event-id>`
   * - Raw filter that is missing a column the plot needs
     - The panel names it and, for another table's column, shows the join
     - :ref:`The plot's own columns <raw-plot-columns>`
   * - ``OR`` without brackets in a Raw filter
     - Only its last term is scoped; the first draws every channel. Write ``WHERE (a OR b) AND ...``
     - :ref:`Known gaps <raw-known-gaps>`
   * - Assisted condition whose brackets do not balance
     - Refused, so a stray ``)`` cannot escape the Scope
     - :ref:`Assisted SQL filters <filtering-assisted>`
   * - Raw filter without both placeholders, exported
     - Refused with how to fix it: an export writes files for each channel
     - :ref:`Scoping with placeholders <raw-scoping>`
   * - ``DELETE``, ``UPDATE``, ``DROP`` ... in a Raw filter
     - Not run; the status panel names the keyword
     - :ref:`Raw SQL filters <filtering-raw>`
   * - Typo in a column name
     - Validation error
     - `Available Columns`_

Available Columns
-----------------

The columns available for filtering depend on the loaded database.
Columns present in the YouTube tutorial database are listed below as a reference (see :ref:`running_software`).

**Identifier columns, in every table that carries them:**

- ``experiment_id`` — which experiment the row belongs to
- ``channel_id`` — the physical channel the data came from; filter on this one
- ``channel_db_id`` — the database's own row number for one experiment's channel, not a
  channel number. Writing data under a new experiment name gives the same physical channel
  a new ``channel_db_id``, so it differing between experiments is expected
- ``event_id`` — the event's number within its channel, counted from 0 on each fitting
  run, so it repeats across experiments and channels; ``e.id`` is unique

**events table:**

- ``duration`` — event duration in µs
- ``start_time`` — event start time in seconds
- ``fitted_ecd``, ``raw_ecd`` — equivalent charge displacement
- ``max_blockage``, ``min_blockage`` — maximum and minimum current blockage in pA
- ``max_blockage_duration``, ``min_blockage_duration`` — duration of max/min blockage levels in µs
- ``max_deviation``, ``max_deviation_duration`` — maximum deviation from baseline
- ``baseline_current``, ``baseline_stdev`` — baseline current in pA and its standard deviation
- ``num_sublevels`` — number of detected sublevels within the event
- ``cluster_label``, ``cluster_confidence`` — clustering results if committed

**sublevels table:**

- ``sublevel_duration`` — duration of the sublevel in µs
- ``sublevel_current`` — current during the sublevel in pA
- ``sublevel_blockage`` — blockage magnitude of the sublevel in pA
- ``sublevel_stdev`` — standard deviation of current within the sublevel
- ``sublevel_fitted_ecd``, ``sublevel_raw_ecd`` — sublevel-level ECD values
- ``sublevel_start_times``, ``sublevel_end_times`` — sublevel time boundaries in µs
- ``sublevel_max_deviation`` — maximum deviation from baseline within the sublevel
- ``level_id``, ``levels_left`` — the sublevel's position within its event
- ``event_db_id`` — the ``id`` of the event the sublevel belongs to (``e.id``)

**experiments table:**

- ``name``, ``voltage``, ``thickness``, ``conductivity`` — the experiment's name and its recorded conditions

.. tip::

   To inspect your database structure directly, use a SQLite browser such as
   `DB Browser for SQLite <https://sqlitebrowser.org/>`_.


.. note:: Tutorial Data

   The data used in the YouTube tutorial series is archived on the Federated Research Data Repository (FRDR):

   **DOI:** `10.20383/103.01695 <https://doi.org/10.20383/103.01695>`_

   The full dataset is ~9.92 GB. Individual ``.log`` and ``.json`` files can be downloaded separately from the FRDR page if you only need specific channels.

   The deposit also contains the reference SQLite databases used in the tutorial (``.sqlite3``), and a ``README.txt`` giving the parameters needed to regenerate them from the recordings.
