.. _filtering-and-querying:

Filtering and Querying
======================

Poriscope supports two modes for filtering event data: **Assisted SQL** and **Raw SQL**. Both modes are available in any tab that supports filters, including the :ref:`metadata-tab`.

Filters can be saved to a JSON file and reloaded in future sessions using the **Save Filter** and **Load Filter** buttons. See :ref:`saving-and-loading-filters`.
The mode you choose at creation time is permanent and encoded directly in the filter name.

.. image:: /_static/images/FilterDialog.png
   :alt: Add Filter Dialog
   :align: center

Filter Modes
------------

Assisted SQL
~~~~~~~~~~~~

In **Assisted SQL** mode, you write only the **WHERE clause** condition. Poriscope constructs the full SQL query automatically, handling column qualification, table joins, and experiment/channel scoping. You do not control which columns are returned or how the query is structured (Poriscope decides that based on what axes you select in the UI).

Use this mode for most everyday filters, and if you are not familiar with SQL 
()no SQL knowledge is required, just simple conditions like ``duration > 100``).

**Example 1 — Long events only:**

Filter: ``duration > 100``

Then select **Histogram**, x-axis: ``duration`` → histogram of events longer than 100 µs.

**Example 2 — High blockage events:**

Filter: ``max_blockage > 2000``

Then select **Scatterplot**, x-axis: ``duration``, y-axis: ``max_blockage`` → scatter of high-blockage events.

**Example 3 — Multi-sublevel events with significant blockage:**

Filter: ``num_sublevels >= 3 and max_blockage > 1500``

Then select **Histogram**, x-axis: ``fitted_ecd`` → distribution of ECD for complex events.

**Example 4 — Cross-table filter** (join handled automatically by Poriscope):

Filter: ``sublevel_duration > 200``

Then select **Histogram**, x-axis: ``duration`` → returns the ``duration`` of events
that contain at least one sublevel longer than 200 µs. Poriscope detects that
``sublevel_duration`` belongs to the ``sublevels`` table and automatically joins it
with the ``events`` table to apply the filter.

**Example 5 — Filter by a property of the experiment:**

Filter: ``voltage > 50``

Then select **Histogram**, x-axis: ``duration`` → events from the experiments run above
50 mV. Poriscope joins the ``experiments`` table automatically, the same way it joins
``sublevels`` in Example 4.

**Example 6 - Subquery, including aggregation:**

A subquery is passed through exactly as you type it, so it can do things the filter
itself cannot. Qualify any reference to the outer row yourself - ``e.id`` for the event.

Filter: ``e.id IN (SELECT event_db_id FROM sublevels WHERE filtered = 5)``

Then select **Histogram**, x-axis: ``duration`` -> events with at least one sublevel
whose ``filtered`` value is 5. Note that the filter ``filtered = 5`` says the same thing
more simply, because Example 4's automatic join already means "at least one sublevel
matches".

Filter: ``e.id IN (SELECT event_db_id FROM sublevels GROUP BY event_db_id HAVING COUNT(*) > 3)``

Then select **Histogram**, x-axis: ``duration`` -> events with more than 3 sublevels,
which is the aggregation the note above says the filter itself cannot express.

Saved as: ``<subset_name>_assisted``

.. note::

   Assisted mode handles cross-table filters automatically but cannot put a
   ``GROUP BY`` or ``HAVING`` on the query itself, and cannot return computed
   columns (e.g., ``max_blockage - min_blockage AS blockage_range``). Use Raw SQL
   for those cases. Aggregation *inside a subquery* does work - see Example 6.

   Text compared against a column is left exactly as you type it, so
   ``sequence = 'duration'`` matches the literal value ``duration`` and is not
   confused with the ``duration`` column. A subquery is left alone the same way:
   it names its own tables, so its column references are never rewritten against
   the outer query's, and a reference to the outer row has to be qualified by you.

   ``id`` on its own is rejected, because every table has one and they mean different
   rows. Write ``e.id`` for an event, ``s.id`` for a sublevel or ``exp.id`` for an
   experiment. ``experiment_id``, ``channel_id`` and ``event_id`` need no qualifier -
   they mean the same thing in every table.

Raw SQL
~~~~~~~

In **Raw SQL** mode, you write a **complete SELECT statement**. Poriscope executes
it against the SQLite database without rewriting or modifying the query content.

You have full control over which columns are returned and how the query is structured.

A raw filter scopes itself. Write ``:experiment_id`` and ``:channel_id`` where you want the
experiment and channel ticked in the **Scope** selection, and Poriscope puts the selected
experiment's id and the channel in, one selected channel at a time - so you never need to know
the ids in the database:

.. code-block:: sql

   SELECT duration FROM events
   WHERE duration > 100 AND experiment_id = :experiment_id AND channel_id = :channel_id

Because the scope is inside your query, ``LIMIT``, aggregates and ``DISTINCT`` see only that
channel's rows, and a raw filter is drawn once for each channel selected, as an Assisted one is.
A few things are yours to provide:

* **Use both placeholders.** A query that uses neither ignores the selection, and one that uses
  only one ignores half of it; the same rows are drawn for every channel, and the status panel
  says so. A placeholder in a subquery only does not scope the main table: if the result has
  ``experiment_id`` or ``channel_id``, rows from other channels are counted on the panel. With
  nothing selected, or more than one channel, a query that uses a placeholder is refused, since
  there is nothing to put in.
* **The plot's own columns.** A plot needs the columns you chose on its axes: if the query does
  not return one, the status panel names it and nothing is drawn. A query that returns the same
  column name twice (a join's ``SELECT *``) is refused if the plot reads it; name the one you
  mean, for example ``SELECT e.duration AS duration, s.sublevel_duration, ...``.
* **``event_id`` for anything that loads events.** The event overlays, all-points histograms, the
  Protein distribution plots, Plot Events, the event navigation arrows and the Protein tab's Plot
  Histogram work on whole events, so the query must return ``event_id``, for example
  ``SELECT event_id FROM events WHERE experiment_id = :experiment_id AND channel_id =
  :channel_id``. A query that does not scope itself must return ``experiment_id``,
  ``channel_id`` and ``event_id`` together, since an event number repeats from channel to
  channel. These three mean the same thing in every table that has them (a sublevel's are its
  parent event's), so a query on ``sublevels`` or a join names the right events. ``id`` does
  not: it is a different row in each table, so a query that returns only ``id`` is asked for
  ``event_id`` instead. A key that names no event in the database, such as a level number
  labelled ``event_id``, is refused, and so is one that is not a whole number
  (``event_id / 2``). A key column the query makes by renaming another expression
  (``level_id AS event_id``) draws a warning, since nothing can check that it was meant, and
  rows whose key is ``NULL`` name no event: they are left out and the panel says how many. After
  each event plot the panel states how many events were selected and their ``event_id`` range.
* **Only a ``SELECT`` is run.** A query has to start with ``SELECT`` (or ``WITH``); anything else
  is not run and the panel says so.

Use this mode to write queries that need aggregations or computed columns, or when you
simply prefer writing complete SQL.

**Example 1 — Same long events filter, written as Raw SQL:**

.. code-block:: sql

   SELECT duration FROM events
   WHERE duration > 100 AND experiment_id = :experiment_id AND channel_id = :channel_id

**Example 2 — Same high blockage filter, written as Raw SQL:**

.. code-block:: sql

   SELECT duration, max_blockage FROM events
   WHERE max_blockage > 2000 AND experiment_id = :experiment_id AND channel_id = :channel_id

**Example 3 — Same multi-sublevel filter, written as Raw SQL:**

.. code-block:: sql

   SELECT fitted_ecd FROM events
   WHERE num_sublevels >= 3 AND max_blockage > 1500
     AND experiment_id = :experiment_id AND channel_id = :channel_id

**Example 4 — Same cross-table filter, written as Raw SQL:**

.. code-block:: sql

   SELECT duration FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id
     AND id IN (
       SELECT event_db_id FROM sublevels
       WHERE sublevel_duration > 200
   )

**Example 5 — Aggregation: filter by sublevel count** (not possible in Assisted):

``GROUP BY`` groups all sublevel rows by their parent event. ``HAVING COUNT(*) > 3``
then keeps only events that have more than 3 sublevel rows.

.. code-block:: sql

   SELECT duration FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id
     AND id IN (
       SELECT event_db_id FROM sublevels
       GROUP BY event_db_id
       HAVING COUNT(*) > 3
   )

You can also aggregate a sublevel property per event and filter on that:

.. code-block:: sql

   SELECT duration FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id
     AND id IN (
       SELECT event_db_id FROM sublevels
       GROUP BY event_db_id
       HAVING AVG(sublevel_duration) > 150
   )

**Example 6 — Computed columns** (not possible in Assisted):

A computed column is derived from existing columns using arithmetic. It is defined
in the ``SELECT`` with ``expression AS column_name``.

Blockage range — difference between maximum and minimum blockage:

.. code-block:: sql

   SELECT duration, max_blockage - min_blockage AS blockage_range FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id

Fractional blockage — blockage normalised to baseline current:

.. code-block:: sql

   SELECT duration, max_blockage / ABS(baseline_current) AS fractional_blockage FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id

Saved as: ``<subset_name>_raw``

.. warning::

   Raw SQL filters must begin with ``SELECT``. Entering a WHERE clause in Raw SQL mode
   (e.g., ``duration > 100``) will be rejected with an error message.

Creating a Filter
-----------------

1. Click the **➕** button next to the Filter dropdown.
2. Enter a **name** for the filter.
3. Select the mode using the **Assisted SQL** or **Raw SQL** radio buttons.
   In Raw SQL mode the dialog reminds you to add ``WHERE experiment_id = :experiment_id AND channel_id = :channel_id``
   to follow the Scope selection.
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

Filters can be saved to a JSON file and reloaded in future sessions.

- **Save Filter**: Exports all current filters to a ``.json`` file. Both ``_assisted``
  and ``_raw`` filters are included.
- **Load Filter**: Imports filters from a ``.json`` file. Raw filters are restored
  directly without re-validation. Assisted filters are re-validated against the selected
  loader's database before being added; if no loader is selected, they are added
  unvalidated and a warning is written to the log.

The saved JSON format looks like:

.. code-block:: json

   {
       "long_events_assisted": "duration > 100",
       "multi_sublevel_raw": "SELECT duration FROM events WHERE id IN (SELECT event_db_id FROM sublevels GROUP BY event_db_id HAVING COUNT(*) > 3)"
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

Common Mistakes
---------------

+------------------------------------------+--------------------------------------------------+
| Mistake                                  | Result                                           |
+==========================================+==================================================+
| WHERE clause entered in Raw SQL mode     | Rejected at creation — must start with SELECT    |
+------------------------------------------+--------------------------------------------------+
| Full SELECT entered in Assisted mode     | Fails validation — treated as a WHERE clause     |
+------------------------------------------+--------------------------------------------------+
| Raw SQL filter without                   | Status panel warns that it ignores the Scope     |
| ``:experiment_id`` / ``:channel_id``     | selection; the same rows draw for every channel  |
+------------------------------------------+--------------------------------------------------+
| Raw SQL filter without ``event_id`` used | Status panel asks for ``event_id``; nothing is   |
| for an event plot, Plot Events or arrows | plotted                                          |
+------------------------------------------+--------------------------------------------------+
| Typo in column name                      | Validation error                                 |
+------------------------------------------+--------------------------------------------------+
| ``event_id`` used to match a sublevel    | Empty result - use ``e.id``; see note above      |
+------------------------------------------+--------------------------------------------------+

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

.. tip::

   To inspect your database structure directly, use a SQLite browser such as
   `DB Browser for SQLite <https://sqlitebrowser.org/>`_.


.. note:: Tutorial Data

   The data used in the YouTube tutorial series is archived on the Federated Research Data Repository (FRDR):

   **DOI:** `10.20383/103.01695 <https://doi.org/10.20383/103.01695>`_

   The full dataset is ~9.92 GB. Individual ``.log`` and ``.json`` files can be downloaded separately from the FRDR page if you only need specific channels.

   The deposit also contains the reference SQLite databases used in the tutorial (``.sqlite3``), and a ``README.txt`` giving the parameters needed to regenerate them from the recordings.
