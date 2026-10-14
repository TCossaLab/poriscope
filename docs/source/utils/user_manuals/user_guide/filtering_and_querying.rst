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
(no SQL knowledge is required, just simple conditions like ``duration > 100``).

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
   columns (e.g., ``max_blockage - min_blockage AS blockage_range``); Raw SQL can
   return them, with the limit on plotting them described under its Example 6.
   A computed *condition* such as ``max_blockage - min_blockage > 500`` works in either
   mode. Aggregation *inside a subquery* does work - see Example 6.

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

   SELECT event_id, duration FROM events
   WHERE duration > 100 AND experiment_id = :experiment_id AND channel_id = :channel_id

Because the scope is inside your query, ``LIMIT``, aggregates and ``DISTINCT`` see only that
channel's rows, and a raw filter is drawn once for each channel selected, as an Assisted one is.
A few things are yours to provide:

* **Use both placeholders.** A query that uses neither ignores the selection, and one that uses
  only one ignores half of it; the same rows are drawn for every channel, and the status panel
  says so. A placeholder in a subquery only does not scope the main table: if the result has
  ``experiment_id`` or ``channel_id``, rows from other channels are counted on the panel. With
  nothing selected a query that uses a placeholder is refused, since there is nothing to put in;
  that happens only for a database with no experiments, because the Scope starts with every
  experiment and channel ticked and always keeps at least one. A query without the placeholders
  draws the same rows once for each ticked channel, so tick a single channel if you want it once.
  The plots that work on one channel at a time (the event overlays, Plot Events, the arrows and
  the Protein tab) ask you to select a single channel when several are ticked.
* **The plot's own columns.** A plot needs the columns you chose on its axes: if the query does
  not return one, the status panel names it and nothing is drawn. A query that returns the same
  column name twice (a join's ``SELECT *``) is refused if the plot reads it; name the one you
  mean, for example ``SELECT e.duration AS duration, s.sublevel_duration, ...``.
* **Start with ``event_id`` unless the query is not one row per event.** Write ``SELECT event_id,
  duration, ...``: the extra column is ignored by a histogram or scatterplot and is what Plot
  Events, the arrows, the event plots, the Protein tab and Export Subset - CSV need, so one filter
  serves them all. Leave it out of a query whose own rows are grouped or combined (``DISTINCT``,
  ``GROUP BY``, ``UNION`` or ``WITH`` at the top level; inside a subquery, as in Example 5, they do
  not matter), where adding a column changes the rows or the query, and name the table in a join
  (``e.event_id``). If it is missing when it is needed, the status panel shows your query with
  ``event_id`` added for you to copy, except for a query that contains any of those words, which it
  leaves alone to be safe; nothing is ever changed for you.
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
* **Only a ``SELECT`` is run.** The dialog asks for a query that starts with ``SELECT`` and says what
  yours starts with if it does not. A statement that writes (``DELETE``, ``UPDATE``, ``DROP``,
  ``WITH ... DELETE`` and the others) is never run, even if it came from a loaded file; the panel
  names the keyword.

Use this mode to write queries that need aggregations or computed columns, or when you
simply prefer writing complete SQL.

**Example 1 — Same long events filter, written as Raw SQL:**

.. code-block:: sql

   SELECT event_id, duration FROM events
   WHERE duration > 100 AND experiment_id = :experiment_id AND channel_id = :channel_id

**Example 2 — Same high blockage filter, written as Raw SQL:**

.. code-block:: sql

   SELECT event_id, duration, max_blockage FROM events
   WHERE max_blockage > 2000 AND experiment_id = :experiment_id AND channel_id = :channel_id

**Example 3 — Same multi-sublevel filter, written as Raw SQL:**

.. code-block:: sql

   SELECT event_id, fitted_ecd FROM events
   WHERE num_sublevels >= 3 AND max_blockage > 1500
     AND experiment_id = :experiment_id AND channel_id = :channel_id

**Example 4 — Same cross-table filter, written as Raw SQL:**

.. code-block:: sql

   SELECT event_id, duration FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id
     AND id IN (
       SELECT event_db_id FROM sublevels
       WHERE sublevel_duration > 200
   )

**Example 5 — Aggregation: filter by sublevel count** (not possible in Assisted):

``GROUP BY`` groups all sublevel rows by their parent event. ``HAVING COUNT(*) > 3``
then keeps only events that have more than 3 sublevel rows.

.. code-block:: sql

   SELECT event_id, duration FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id
     AND id IN (
       SELECT event_db_id FROM sublevels
       GROUP BY event_db_id
       HAVING COUNT(*) > 3
   )

You can also aggregate a sublevel property per event and filter on that:

.. code-block:: sql

   SELECT event_id, duration FROM events
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

   SELECT event_id, duration, max_blockage - min_blockage AS blockage_range FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id

Fractional blockage — blockage normalised to baseline current:

.. code-block:: sql

   SELECT event_id, duration, max_blockage / ABS(baseline_current) AS fractional_blockage FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id

.. note::

   The query returns these columns, but the **axis menus list only the database's own
   columns**, so ``blockage_range`` and ``fractional_blockage`` cannot be chosen on an axis,
   and a plot cannot use them yet. What a computed column is good for today is the
   ``WHERE``, where it works in Assisted too, or reading the result in a viewer by pasting the
   query Poriscope echoes on the status panel.

Saved as: ``<subset_name>_raw``

.. warning::

   Raw SQL filters must begin with ``SELECT``. Entering a WHERE clause in Raw SQL mode
   (e.g., ``duration > 100``) will be rejected with an error message.

How the two modes run your filter
---------------------------------

What Poriscope runs
~~~~~~~~~~~~~~~~~~~

The same filter, ``duration > 100``, on channel 0 of experiment 1, plotted as a histogram of
``duration``.

**Assisted** - you write the condition, Poriscope writes the query. Roughly:

.. code-block:: sql

   SELECT e.id, e.experiment_id, e.channel_id, e.event_id, e.duration
   FROM events e
   WHERE (e.duration > 100) AND ((experiment_id = 1 AND channel_id IN (0)))

The columns come from the axes you chose, and the Scope selection is added for you. Your
condition is put in brackets before it is joined to the scope, so an ``OR`` in it cannot
widen the scope; a condition whose brackets do not balance is refused. Tables are joined
when the condition names their columns (``sublevel_duration``, ``voltage``).

**Raw** - you write the query, Poriscope puts the ids in and runs it once for each selected
channel:

.. code-block:: sql

   SELECT event_id, duration FROM events
   WHERE duration > 100 AND experiment_id = 1 AND channel_id = 0

Nothing is wrapped around it and nothing is applied to its result afterwards.

Is a Raw filter the same as running the SQL in a database viewer?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Nearly. SQLite runs the text you wrote, as you wrote it, so a raw filter returns what the same
query returns in `DB Browser for SQLite <https://sqlitebrowser.org/>`_ with the numbers typed
in. The status panel shows the query that ran, with the numbers in (``SQL (events):``), so you
can paste it into a viewer and compare. An Assisted filter is not like that: you wrote only a
condition, and the query around it is Poriscope's.

The differences from a viewer:

* **One channel at a time.** The placeholders become one experiment and channel, and the query
  runs once for each channel ticked. ``LIMIT``, ``ORDER BY``, ``DISTINCT`` and aggregates
  therefore apply *within each channel*, not across the selection: ``LIMIT 5`` with two
  channels ticked gives five events per channel.
* **Read only.** Only ``SELECT`` (or ``WITH``) runs. ``INSERT``, ``UPDATE``, ``DELETE``,
  ``DROP``, ``CREATE``, ``ALTER``, ``ATTACH``, ``DETACH``, ``PRAGMA``, ``VACUUM``,
  ``REINDEX``, ``ANALYZE`` and ``REPLACE INTO`` are refused, and the connection itself cannot
  write, so a raw filter cannot change your database.
* **The plot reads columns by name.** A column the plot needs has to be in the result, and
  events are named by ``event_id`` (see above). A viewer shows you whatever you selected.
* **Poriscope checks the result and tells you** on the status panel; a viewer says nothing.

Same filter, both modes
~~~~~~~~~~~~~~~~~~~~~~~

The six examples above come in pairs. Two things differ between the modes that the pairs do
not show.

An ``OR`` has to be bracketed in Raw SQL. ``AND`` binds before ``OR``, so

.. code-block:: sql

   SELECT event_id, duration FROM events
   WHERE duration > 100 OR max_blockage > 2000
     AND experiment_id = :experiment_id AND channel_id = :channel_id

scopes only the second term, and the first is drawn for every channel in the database. Write

.. code-block:: sql

   SELECT event_id, duration FROM events
   WHERE (duration > 100 OR max_blockage > 2000)
     AND experiment_id = :experiment_id AND channel_id = :channel_id

In Assisted mode the condition ``duration > 100 OR max_blockage > 2000`` is enough, because
Poriscope brackets it.

The same events from the sublevels table, with a condition on the sublevels:

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Assisted
     - Raw
   * - ``sublevel_duration > 200``
     - ``SELECT event_id, duration FROM events WHERE experiment_id = :experiment_id AND channel_id =
       :channel_id AND id IN (SELECT event_db_id FROM sublevels WHERE sublevel_duration > 200)``

Only in Assisted, or only in Raw
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Only Assisted
     - Only Raw
   * - No SQL beyond a condition, and no placeholders: the Scope is added for you
     - Aggregates and grouping as the plotted result (``GROUP BY``, ``DISTINCT``): one row per group
   * - Any column of any table can go on an axis, and a condition on it joins the table by itself (``sublevel_duration``, ``voltage``)
     - Computed columns in the result (``max_blockage - min_blockage AS blockage_range``); the axis menus do not list them, so they cannot be plotted yet
   * - An ``OR`` or a ``--`` comment cannot widen the scope
     - ``ORDER BY``, ``LIMIT`` and ``OFFSET`` on the plotted rows, applied within each channel
   * - Every plot works: Poriscope chooses the columns and the event ids
     - Columns from several tables in one result (a join's output)
   * - The Scope selection cannot be forgotten
     - The query you wrote is the one that runs, so you can paste it into a viewer
   * - The filter is drawn once for each ticked channel
     - The same, when it uses the placeholders; without them the same rows are drawn once for
       each ticked channel

Which *events* a filter selects is never the difference. A subquery in an Assisted condition
selects any set of events a raw filter can, including window functions, ``WITH`` and queries
that compare an event with its own channel: for example the longest 10% of events in each
channel is
``e.id IN (SELECT id FROM (SELECT id, NTILE(10) OVER (PARTITION BY experiment_id, channel_id
ORDER BY duration DESC) AS t FROM events) WHERE t = 1)``. What Raw adds is control of the
*result*: computed columns, columns from several tables, and aggregates. The axis menus list
only the database's own columns, so today a plot can use only those, selected by the query;
the rest is for reading the result in a viewer. For Plot Events, the arrows and the event plots
only the events matter, so the two modes can name the same ones.

Which plots take a filter
~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Action
     - Assisted
     - Raw
   * - Update Plot: Histogram, Normalized and Categorical Histogram, Kernel Density, Heatmap,
       Scatterplot, 3D Scatterplot
     - Works
     - Needs the plotted columns in the result; a column of another table (``sublevel_duration``) needs a join, which the status panel shows. Drawn once for each ticked channel
   * - Update Plot: Raw and Filtered All Points Histograms (and normalized)
     - Works
     - Needs ``event_id``. Drawn once for each ticked channel
   * - Update Plot: Raw and Filtered Event Overlay
     - Works, one channel
     - Needs ``event_id``, one channel
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
separate overlaid datasets, whether they are Assisted, Raw or a mixture of both; there is no
AND or OR between two saved filters. To combine conditions, write them into one filter. The
Protein tab and Export Subset - CSV take one filter only.

Known gaps, and how to guard against them
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Raw mode trusts what you write, so a few mistakes give a result that looks plausible. None can
damage the database, and each is either warned about or easy to check:

1. **The placeholders are left out, or only one is used.** The filter ignores the Scope
   selection, wholly or in part, and the same rows are drawn for every channel. The status
   panel warns, and an export is refused. Start from the dialog's hint line.
2. **The placeholders sit in a subquery only.** The main table is not scoped. If the result
   has ``experiment_id`` or ``channel_id`` the panel counts the rows from other channels; if
   not, nothing can tell. Put the scope in the outer ``WHERE``.
3. **An unbracketed ``OR``** (above). The panel warns only when the result carries the
   ``experiment_id`` or ``channel_id`` columns, so bracket every ``OR``.
4. **A key column that is renamed** (``level_id AS event_id``) or rows whose key is ``NULL``.
   The panel warns, or says how many rows were left out.
5. **Whether it is the filter you meant.** After each event plot the panel states how many
   events were selected and their ``event_id`` range; compare it with the count the same
   query gives in a viewer. For a plot of columns, the number of points on the histogram is
   the number of rows.

Large databases
~~~~~~~~~~~~~~~

A raw filter that names events (Plot Events, the arrows, the event plots, the Protein tab)
checks that every ``event_id`` it returns exists, so its first read is slower than an Assisted
filter's: roughly two to three times as long, a few seconds with 300,000 events per channel.
It is paid once for a filter and channel; moving through the events afterwards uses the list
already read. Reading the columns of one channel for a histogram is not slower than Assisted.
Narrowing the query (a condition, or ``LIMIT``) shortens it.

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
| ``OR`` without brackets in Raw SQL       | Only its last term is scoped; the first draws    |
|                                          | every channel - write ``WHERE (a OR b) AND ...`` |
+------------------------------------------+--------------------------------------------------+
| Assisted condition whose brackets do not | Refused, so a stray ``)`` cannot escape the      |
| balance                                  | Scope                                            |
+------------------------------------------+--------------------------------------------------+
| Raw filter without both placeholders,    | Refused with how to fix it; an export writes     |
| exported                                 | files per channel                                |
+------------------------------------------+--------------------------------------------------+
| ``DELETE``, ``UPDATE``, ``DROP`` ... in  | Not run - the status panel names the keyword     |
| a Raw SQL filter                         |                                                  |
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
