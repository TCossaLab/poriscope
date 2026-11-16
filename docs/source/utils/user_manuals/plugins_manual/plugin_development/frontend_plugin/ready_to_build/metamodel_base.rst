MetaModel as a Base Class
=========================

:ref:`MetaModel` is the abstract base class for all analysis tab models in Poriscope: it
runs calculations, manages worker threads and caches plot data.

**The Model is where computation and data access belong.** A tab's View draws; anything
that turns data into other data — filtering, scaling, binning, fitting, building an axis,
querying a plugin — is the Model's job, and the shared parts of it are already here. If
your tab reads its rows from a :ref:`MetaDatabaseLoader`, inherit
:ref:`MetaSubsetTabModel` instead; it adds the events-table lookups behind an event plot
and the subset filter file's JSON. See :ref:`choosing_a_base`.

What You Get by Inheriting MetaModel
------------------------------------

**Thread and worker management**

You don’t have to manually manage threads or signals. ``MetaModel`` handles:

- Spawning and tracking worker threads (``WorkerThread``)
- Connecting signals for progress updates
- Running one generator per channel, each on its own worker thread. Whether a plugin's
  channels may overlap is decided by the plugin itself, not here - see
  :ref:`serial_channel_operations`

**Signals**

- ``update_progressbar`` to visually track long computations
- ``add_text_to_display`` to send log output or feedback to the interface
- ``run_finished(channel, key)``, emitted once a plugin's run on a channel has ended and its
  status was reported; the Controller listens to it to record a finished Find or Fit

**Calling a data plugin**

``call(metaclass, key, method, *args, **kwargs)`` runs a method on a data plugin - a
reader, a loader, a fitter - and returns its result:

.. code-block:: python

   rows = self.call("MetaDatabaseLoader", loader_name, "load_metadata", columns)

Failures raise at the call site, so a ``try``/``except`` around the call is a working
guard. ``call()`` is on the Model only: a Controller slot uses ``self.model.call(...)``,
and neither the View nor the Controller should reach a plugin any other way. See
:ref:`CallingAPlugin`.

**Computation you inherit**

Two pieces of shared numerics live here, so no tab writes them twice and no View has to
import ``numpy`` to get them:

- ``logscale_and_filter_columns(*data, log_flags=...)`` drops every row in which any
  column is NaN, then applies base-10 scaling to the columns you flag. This is what
  filters and log-scales every plot in the application, and it reports what it dropped on
  the status panel.
- ``time_bases(traces, samplerate, scale=1.0, offset=0.0)`` builds the time axis for each
  trace. The samples and the rate are the Model's, so the axis is derived here; the scale
  and offset serve both an event plot in microseconds and a trace plot in seconds from the
  start of a recording.

**Caching and reporting**

- Store intermediate data with ``cache_plot_data()``
- Format and return a cached ``DataFrame`` with ``format_cache_data()``
- Put each plugin's status report on the status panel when its run on a channel finishes

**Helper functions you don’t need to write yourself**

- ``stop_workers()`` to gracefully terminate long-running tasks
- ``discard_generator()`` to clean up when threads complete
- ``set_generator()`` and ``run_generators()`` to queue and execute background operations

What You Need to Implement
--------------------------

Only ``_init()`` is abstract. Set up your Model's own state there; the base constructor
calls it at the end. Each method's contract is on the :ref:`MetaModel` reference page.
