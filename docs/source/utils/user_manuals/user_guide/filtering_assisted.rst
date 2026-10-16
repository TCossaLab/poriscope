.. _filtering-assisted:

Assisted SQL filters
====================

In **Assisted SQL** mode you write only the **condition**, the part that would follow ``WHERE``.
Poriscope builds the complete query for you: it chooses the columns from the axes you pick, joins
the tables your condition needs, and adds the experiment and channel scope. No SQL knowledge is
needed beyond simple conditions like ``duration > 150``.

Use this mode for most everyday filters. See :ref:`Filtering and Querying <filtering-and-querying>`
for how a filter is created, saved and used, and :ref:`Raw SQL filters <filtering-raw>` for the
mode that gives you the whole query.

Saved as: ``<subset_name>_assisted``

**In short:** write only the condition. Poriscope adds the scope, joins the tables and chooses the
columns, so any plot can use the filter.

What you write, and what Poriscope runs
---------------------------------------

For the filter ``duration > 150``, plotted as a histogram of ``duration`` for experiment 1,
channel 2 of the :ref:`example database <example-database>`, Poriscope runs, roughly:

.. code-block:: sql

   SELECT e.id, e.experiment_id, e.channel_id, e.event_id, e.duration
   FROM events e
   WHERE (e.duration > 150) AND ((experiment_id = 1 AND channel_id IN (2)))

The columns come from the axes you chose, and the scope is added for you. The query is run once
for each ticked experiment and channel (see :ref:`How scope works <how-scope-works>`).

What Assisted does for you
--------------------------

* **The scope is always applied.** You cannot forget it, because you never write it.
* **Your condition is bracketed.** It is put in brackets before it is joined to the scope, so an
  ``OR`` or a trailing ``--`` comment cannot widen the scope. A condition whose brackets do not
  balance is refused.
* **Tables are joined by themselves.** A condition on ``sublevel_duration`` or ``voltage`` joins
  the ``sublevels`` or ``experiments`` table without you writing the join.
* **Any column of any table can go on an axis.** Poriscope builds the query from the axes.
* **Every plot can use it,** including Plot Events, the arrows, the event plots and Export Subset - CSV,
  because Poriscope fetches the event ids itself.

Examples
--------

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

Filter: ``e.id IN (SELECT event_db_id FROM sublevels WHERE sublevel_duration > 100)``

Then select **Histogram**, x-axis: ``duration`` -> events with at least one sublevel
longer than 100 µs. Note that the filter ``sublevel_duration > 100`` says the same thing
more simply, because Example 4's automatic join already means "at least one sublevel
matches".

Filter: ``e.id IN (SELECT event_db_id FROM sublevels GROUP BY event_db_id HAVING COUNT(*) > 3)``

Then select **Histogram**, x-axis: ``duration`` -> events with more than 3 sublevels,
which is the aggregation the note below says the filter itself cannot express.

Limits and details
------------------

.. note::

   Assisted mode handles cross-table filters automatically but cannot put a
   ``GROUP BY`` or ``HAVING`` on the query itself, and cannot return computed
   columns (e.g., ``max_blockage - min_blockage AS blockage_range``); Raw SQL can
   return them, with the limit on plotting them described on its page. A computed *condition*
   such as ``max_blockage - min_blockage > 500`` works in either mode. Aggregation *inside a
   subquery* does work - see Example 6. Window functions and ``WITH`` also work inside a
   subquery, so the *events* an Assisted filter can select are the same as a raw filter's: for
   example the longest 10% of events in each channel is
   ``e.id IN (SELECT id FROM (SELECT id, NTILE(10) OVER (PARTITION BY experiment_id, channel_id
   ORDER BY duration DESC) AS t FROM events) WHERE t = 1)``.

   Text compared against a column is left exactly as you type it, so
   ``sequence = 'duration'`` matches the literal value ``duration`` and is not
   confused with the ``duration`` column. A subquery is left alone the same way:
   it names its own tables, so its column references are never rewritten against
   the outer query's, and a reference to the outer row has to be qualified by you.

   ``id`` on its own is rejected when the query joins more than one table, because every table
   has one and they mean different rows (on events alone it means the event). Write ``e.id`` for an
   event, ``s.id`` for a sublevel or ``exp.id`` for an experiment, and do so always. ``experiment_id``, ``channel_id`` and ``event_id`` need no qualifier -
   they mean the same thing in every table.

.. warning::

   An Assisted filter is a condition, not a query. Poriscope puts what you write inside a ``WHERE``,
   so a filter that starts with ``SELECT`` is refused, and the message says to use Raw SQL mode for a
   complete query. A subquery inside a condition, such as ``e.id IN (SELECT event_db_id FROM
   sublevels)``, is fine.
