.. _filtering-raw:

Raw SQL filters
===============

In **Raw SQL** mode you write a **complete SELECT statement**. Poriscope runs it against the SQLite
database as you wrote it, once for each ticked experiment and channel, with nothing wrapped around
it and nothing applied to its result afterwards. You choose the columns and the structure of the
query, and you are responsible for scoping it.

.. important::

   **Raw mode trusts your query.** Poriscope runs exactly what you wrote and never changes it
   behind your back. Its checks and suggestions (the status panel, the question about
   ``event_id``) are automatic and cautious, and they can miss or misjudge a case. If the result
   is wrong, the query is the first place to look: whether it is the filter you meant is your
   responsibility, and the panel and your own viewer are there to help you check.

Use this mode for what a condition cannot say: aggregates, computed or joined results, ``ORDER BY``
and ``LIMIT``, or simply because you prefer to write your own queries. Compared with writing the
query in a database viewer, two things change: you enter ``:experiment_id`` and ``:channel_id``
instead of knowing the numbers, and Poriscope does not choose the columns for you. It does not
work like a viewer that plots whatever your query returns and picks the axes from its columns. You
choose the plot and its axes in the controls as usual, and the plot then looks for those columns,
by name, in your query's result, so they have to be in your ``SELECT``. The rest is the SQL you
already know, with the few differences listed in the next section.

See :ref:`Filtering and Querying <filtering-and-querying>` for how a filter is created, saved and
used, and :ref:`Assisted SQL filters <filtering-assisted>` for the mode that writes the query for
you.

Saved as: ``<subset_name>_raw``

**In short, three rules:**

1. Write a complete ``SELECT``.
2. Put ``experiment_id = :experiment_id AND channel_id = :channel_id`` in its ``WHERE``.
3. Start the column list with ``event_id``.

The rest of this page explains why, and what the status panel says when one of them is missed.

Is a Raw filter the same as running the SQL in a database viewer?
-----------------------------------------------------------------

Nearly. SQLite runs the text you wrote, as you wrote it, so a raw filter returns what the same
query returns in `DB Browser for SQLite <https://sqlitebrowser.org/>`_ with the numbers typed in.
The status panel shows the query that ran, with the numbers in (``SQL (raw query):``), so you can
paste it into a viewer and compare.

The differences from a viewer:

* **One experiment and channel at a time.** The placeholders become one experiment and channel,
  and the query runs once for each pair ticked. ``LIMIT``, ``ORDER BY``, ``DISTINCT`` and
  aggregates therefore apply *within each pair*, not across the selection: ``LIMIT 5`` with two
  channels ticked gives five events per channel.
* **Read only.** Only a ``SELECT`` runs. ``INSERT``, ``UPDATE``, ``DELETE``, ``DROP``, ``CREATE``,
  ``ALTER``, ``ATTACH``, ``DETACH``, ``PRAGMA``, ``VACUUM``, ``REINDEX``, ``ANALYZE`` and
  ``REPLACE INTO`` are refused, even ``WITH ... DELETE`` and even from a loaded file, and the
  connection itself cannot write, so a raw filter cannot change your database. The dialog asks for
  a query that starts with ``SELECT`` and says what yours starts with if it does not.
* **The plot reads columns by name.** A column the plot needs has to be in the result, and events
  are named by ``event_id`` (see below). A viewer shows you whatever you selected.
* **Poriscope checks the result and tells you** on the status panel; a viewer says nothing.

.. _raw-scoping:

Scoping with placeholders
-------------------------

A raw filter scopes itself. ``:experiment_id`` and ``:channel_id`` stand for the experiment and
channel of the pair being plotted, and Poriscope replaces them with that pair's database numbers
before running the query, so you never need to know the numbers:

.. code-block:: sql

   SELECT event_id, duration FROM events
   WHERE duration > 150 AND experiment_id = :experiment_id AND channel_id = :channel_id

The pairs come from the **Scope** selection: every experiment and channel starts ticked, and at
least one must stay ticked. Because the scope is inside your query, ``LIMIT``, aggregates and
``DISTINCT`` see only that pair's rows. A raw filter is drawn once for each ticked pair, as an
Assisted one is. The plots that work on one channel at a time (the Heatmap, the event overlays, Plot Events, the
arrows and the Protein tab) ask you to select a single experiment and channel when several are
ticked.

The filter dialog shows an example scoped query in the empty box in Raw SQL mode, and an **info icon** beside
Raw SQL with the rule. For how scope works in general, see
:ref:`How scope works <how-scope-works>`.

.. _raw-leaving-placeholder-out:

What leaving a placeholder out does
-----------------------------------

Poriscope runs your query once for every ticked pair, whether or not the query uses the
placeholders. What it returns depends on which ones it uses. The example uses the small
:ref:`example database <example-database>` with the filter ``duration > 150``, and three pairs
ticked: experiment 1 channel 1, experiment 1 channel 2 and experiment 2 channel 2. The events over
150 in the whole database total 5.

.. list-table:: The same filter with different placeholders
   :header-rows: 1
   :widths: 14 24 14 22 26

   * - The query uses
     - Its ``WHERE``
     - Poriscope runs, for experiment 1 channel 2
     - Rows plotted for the three pairs (exp 1 ch 1, exp 1 ch 2, exp 2 ch 2)
     - Viewer query for experiment 1 channel 2, and what it returns
   * - **Both** placeholders
     - ``duration > 150 AND experiment_id = :experiment_id AND channel_id = :channel_id``
     - ``… experiment_id = 1 AND channel_id = 2``
     - **1, 2, 2**: each pair's own rows (5 in all)
     - ``SELECT COUNT(*) FROM events WHERE duration > 150 AND experiment_id = 1 AND channel_id = 2;`` returns **2**
   * - **Neither**
     - ``duration > 150``
     - ``duration > 150`` (nothing to fill in)
     - **5, 5, 5**: the whole result for every pair
     - ``SELECT COUNT(*) FROM events WHERE duration > 150;`` returns **5**
   * - Only ``:channel_id``
     - ``duration > 150 AND channel_id = :channel_id``
     - ``… channel_id = 2``
     - **1, 4, 4**: that channel number from every experiment
     - ``SELECT COUNT(*) FROM events WHERE duration > 150 AND channel_id = 2;`` returns **4**
   * - Only ``:experiment_id``
     - ``duration > 150 AND experiment_id = :experiment_id``
     - ``… experiment_id = 1``
     - **3, 3, 2**: every channel of that experiment
     - ``SELECT COUNT(*) FROM events WHERE duration > 150 AND experiment_id = 1;`` returns **3**

To see how the 5 rows split between the pairs, run:

.. code-block:: sql

   SELECT experiment_id, channel_id, COUNT(*) FROM events
   WHERE duration > 150 GROUP BY experiment_id, channel_id;

**The bottom line, for each case:**

* **Both placeholders:** each pair is plotted with *its own* rows. The three datasets split the 5
  rows between them. This is what you want.
* **Neither:** the Scope selection has no effect. The query runs on the whole database, and every
  ticked pair is plotted with the *whole result*, all 5 rows, instead of only its own. This is
  **not** the same as running the filter for each ticked pair: that gives 1, 2 and 2 (the first
  case), while here every pair gets all 5. The three datasets are identical and overlap exactly.
* **Only** ``:channel_id``: each pair is plotted with its channel number from *every experiment*.
  Experiment 1 channel 2 holds experiment 2's channel 2 events as well, 4 rows instead of its own 2.
* **Only** ``:experiment_id``: each pair is plotted with *every channel* of its experiment, not
  only the one ticked. Experiment 1 channel 2 holds experiment 1's channel 1 event as well, 3 rows
  instead of its own 2.

In the last three cases the status panel warns, and the legend entry of a column plot ends with
``(rows not limited to this experiment and channel)``, so the plot cannot be read as the channel it
is named after. A placeholder inside a subquery only does not scope the main table; see
:ref:`Known gaps <raw-known-gaps>`.

.. _raw-event-id:

Start with event_id
-------------------

.. note::

   **Remember: a plot of events needs** ``event_id`` **in your SELECT.** That is Plot Events, the arrows, the
   event overlays, the all-points histograms and the Protein tab. For a plain query Poriscope asks
   whether to add it; for any other query the plot is refused and the status panel says why.

Write ``SELECT event_id, duration, ...``. The extra column is ignored by a histogram or
scatterplot, and it is what Plot Events, the arrows, the event plots, the Protein tab and Export
Subset - CSV need, so one filter serves them all. ``ORDER BY`` and ``LIMIT`` are fine with it.

What matters is whether **each row of the result is one event**:

* **Put grouping and aggregates in a subquery,** as in Example 5, and keep the outer query one row
  per event. ``GROUP BY``, ``HAVING`` and ``DISTINCT`` inside a subquery, or a function such as
  ``COUNT(DISTINCT x)``, do not change the outer rows, so ``event_id`` is still right.
* **A join that repeats events:** write ``SELECT DISTINCT e.event_id, ...`` so each event appears
  once, and name the table (``e.event_id``), because ``events`` and ``sublevels`` both have one.

.. warning::

   **Do not add** ``event_id`` **to a query that groups or combines its rows.** With ``GROUP BY``
   (of anything but ``event_id``), ``DISTINCT`` of values, an aggregate such as ``AVG(...)`` or a
   top-level ``UNION``, the rows are groups or values rather than events. SQLite then picks one
   event for each group, and a plot can open the wrong one. Group by ``event_id`` itself, or use the
   query only for column plots. Poriscope does not add ``event_id`` to such a query for you, and it
   warns about a ``GROUP BY`` or an aggregate that returns it.

.. important::

   Again, if you trust that your query does what you want it to, go ahead. Poriscope's warnings are
   automatic, cautious checks and cannot know what you meant; they are there to help you notice a
   mistake, not to overrule your query.

If a plot needs ``event_id`` and the filter does not return it, and the query is a plain
``SELECT`` from ``events`` or ``sublevels``, Poriscope **asks** whether to start its column list with
``event_id``, showing the new text. **Yes** changes the filter and the plot carries on; if the new
query cannot be used the filter is put back and the panel says so. **No** leaves it as it is, the
panel shows the same text as an automatic suggestion, and the question is asked again the next time a
plot needs it.
The change is made in the open tab and kept with the session when you quit; use **Save Filter** to
also update your filters file.

For any other query, nothing is offered or changed, because adding ``event_id`` could change its rows
or break it. The panel names the word it found (``GROUP BY``, ``DISTINCT``, an aggregate, ``UNION``
or a join) and why Poriscope left the query alone, with an example of the fix for a join or a grouped
query, and a ``GROUP BY`` that returns
``event_id`` without grouping by the event is warned about, and so is an aggregate that returns it.
The check is automatic and cautious: if
you know adding ``event_id`` is right for your query, add it yourself.

The event overlays, all-points histograms, the Protein distribution plots, Plot Events, the arrows
and the Protein tab's Plot Histogram work on whole events, so the query must return ``event_id``.
A query that does not scope itself must return ``experiment_id``, ``channel_id`` and ``event_id``
together, since an event number repeats from channel to channel. These three mean the same thing in
every table that has them (a sublevel's are its parent event's), so a query on ``sublevels`` or a
join names the right events. ``id`` does not: it is a different row in each table, so a query that
returns only ``id`` is asked for ``event_id`` instead.

A key that names no event in the database, such as a level number labelled ``event_id``, is
refused, and so is one that is not a whole number (``event_id / 2``). A key column the query makes
by renaming another expression (``level_id AS event_id``) draws a warning, since nothing can check
that it was meant, and rows whose key is ``NULL`` name no event: they are left out and the panel
says how many. After each event plot the panel states how many events were selected and their
``event_id`` range.

.. _raw-plot-columns:

The plot's own columns
----------------------

A plot needs the columns you chose on its axes. If the query does not return one, the status panel
names it and nothing is drawn. For a column of another table, such as ``sublevel_duration``, the
panel also shows the join:

.. code-block:: sql

   SELECT e.event_id, s.sublevel_duration
   FROM events e JOIN sublevels s ON s.event_db_id = e.id
   WHERE e.experiment_id = :experiment_id AND e.channel_id = :channel_id

A query that returns the same column name twice (a join's ``SELECT *``) is refused if the plot
reads it; name the one you mean, for example ``SELECT e.duration AS duration, s.sublevel_duration,
...``. The axis menus list only the database's own columns, so a computed column such as
``max_blockage - min_blockage AS blockage_range`` is returned by the query but cannot be chosen on
an axis yet.

Examples
--------

Each one is the raw version of the Assisted example with the same number.

**Example 1 — Long events filter:**

.. code-block:: sql

   SELECT event_id, duration FROM events
   WHERE duration > 100 AND experiment_id = :experiment_id AND channel_id = :channel_id

**Example 2 — High blockage filter:**

.. code-block:: sql

   SELECT event_id, duration, max_blockage FROM events
   WHERE max_blockage > 2000 AND experiment_id = :experiment_id AND channel_id = :channel_id

**Example 3 — Multi-sublevel filter:**

.. code-block:: sql

   SELECT event_id, fitted_ecd FROM events
   WHERE num_sublevels >= 3 AND max_blockage > 1500
     AND experiment_id = :experiment_id AND channel_id = :channel_id

**Example 4 — Cross-table filter:**

.. code-block:: sql

   SELECT event_id, duration FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id
     AND id IN (
       SELECT event_db_id FROM sublevels
       WHERE sublevel_duration > 200
   )

**Example 5 — Aggregation: filter by sublevel count** (Assisted can do this only through a subquery, see its Example 6):

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

**Example 6 — Computed columns** (only in Raw):

A computed column is derived from existing columns using arithmetic. It is defined
in the ``SELECT`` with ``expression AS column_name``.

.. code-block:: sql

   SELECT event_id, duration, max_blockage - min_blockage AS blockage_range FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id

.. code-block:: sql

   SELECT event_id, duration, max_blockage / ABS(baseline_current) AS fractional_blockage FROM events
   WHERE experiment_id = :experiment_id AND channel_id = :channel_id

.. note::

   **A computed column can be returned, but cannot be chosen on an axis yet.** The axis menus list
   only the database's own columns, so ``blockage_range`` and ``fractional_blockage`` appear in the
   result but are not offered.

   What works today:

   * **Select events by a calculation.** Put it in the ``WHERE``, for example
     ``max_blockage - min_blockage > 500``. This works in Raw and in Assisted, and the plot shows
     ordinary columns of the events it selects.
   * **Plot the computed values.** Give the result the name of a column the menus do offer, for
     example ``max_blockage - min_blockage AS max_blockage``, then choose ``max_blockage`` on the
     axis. The plot draws your numbers.

   If you plot a computed value this way, Poriscope still treats it as the real column, so:

   * the **axis label and unit** are the real column's (pA for ``max_blockage``), even if your
     value is a ratio with no unit;
   * **Export Plot Data** writes the values under that same name, so rename that column in the
     exported file to avoid mistaking it for the real one;
   * plotting the real ``max_blockage`` **in the same figure** gives two datasets that look alike
     but mean different things.

   Label such a figure yourself (in its title or caption) and do not mix it with the real column.

Only in Assisted, or only in Raw
--------------------------------

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Only Assisted
     - Only Raw
   * - No SQL beyond a condition, and no placeholders: the scope is added for you
     - Aggregates and grouping as the plotted result (``GROUP BY``, ``DISTINCT``): one row per group
   * - Any column of any table can go on an axis, and a condition on it joins the table by itself
       (``sublevel_duration``, ``voltage``)
     - Computed columns in the result (``max_blockage - min_blockage AS blockage_range``); the axis
       menus do not list them, so they cannot be plotted yet
   * - An ``OR`` or a ``--`` comment cannot widen the scope
     - ``ORDER BY``, ``LIMIT`` and ``OFFSET`` on the plotted rows, applied within each pair
   * - Every plot can use it: Poriscope chooses the columns and the event ids
     - Columns from several tables in one result (a join's output)
   * - The scope cannot be forgotten
     - The query you wrote is the one that runs, so you can paste it into a viewer

Which *events* a filter selects is never the difference: a subquery in an Assisted condition can
select any set of events a raw filter can (see the note on the Assisted page). What Raw adds is
control of the *result*: computed columns, columns from several tables, and aggregates. For Plot
Events, the arrows and the event plots only the events matter, so the two modes can name the same
ones.

An ``OR`` has to be bracketed in Raw SQL, because ``AND`` binds before ``OR``:

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

.. _raw-known-gaps:

Known gaps, and how to guard against them
-----------------------------------------

Raw mode trusts what you write, so a few mistakes give a result that looks plausible. None can
damage the database, and each is either warned about or easy to check:

1. **The placeholders are left out, or only one is used.** The filter ignores the Scope selection,
   wholly or in part, and each ticked pair is plotted with rows that are not its own (see
   :ref:`What leaving a placeholder out does <raw-leaving-placeholder-out>`). The status panel
   warns, the legend entries of a column plot say ``(rows not limited to this experiment and
   channel)``, and an export is refused. Start from the example the dialog shows.
2. **The placeholders sit in a subquery only.** The main table is not scoped. If the result has
   ``experiment_id`` or ``channel_id`` the panel counts the rows from other channels; if not,
   nothing can tell. Put the scope in the outer ``WHERE``.
3. **An unbracketed** ``OR`` (above). The panel warns only when the result carries the
   ``experiment_id`` or ``channel_id`` columns, so bracket every ``OR``.
4. **A key column that is renamed** (``level_id AS event_id``) or rows whose key is ``NULL``. The
   panel warns, or says how many rows were left out.
5. **Whether it is the filter you meant.** After each event plot the panel states how many events
   were selected and their ``event_id`` range; compare it with the count the same query gives in a
   viewer. For a plot of columns, the number of points on the histogram is the number of rows.

Large databases
---------------

A raw filter that names events (Plot Events, the arrows, the event plots, the Protein tab) checks
that every ``event_id`` it returns exists, so its first read is slower than an Assisted filter's,
by less than a factor of three: a couple of seconds with 300,000 events per channel. It is paid once
for a filter and channel; moving through the events afterwards uses the list already read. Reading
the columns of one channel for a histogram is not slower than Assisted. Narrowing the query (a
condition, or ``LIMIT``) shortens it.
