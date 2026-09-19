MetaModel as a Base Class
=========================

:ref:`MetaModel`  is the abstract base class for all analysis tab models in Poriscope.
It handles the logic, processing, and backend operations that power your tab — things like running calculations, managing worker threads, and storing cached data.

This class does a lot of the heavy lifting behind the scenes, so you can focus on implementing just the part that makes your model unique.

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

**Signals and communication**

Built-in signals allow your model to communicate with the view, controller, or even other plugins:

- :ref:`GlobalSignal` and :ref:`DataPluginControllerSignal` for inter-plugin communication
- ``update_progressbar`` to visually track long computations
- ``add_text_to_display`` to send log output or feedback to the interface

**Calling a data plugin**

``call(metaclass, key, method, *args, **kwargs)`` runs a method on a data plugin — a
reader, a loader, a fitter — and returns its result. Use it wherever your tab needs data
from a plugin:

.. code-block:: python

   rows = self.call("MetaDatabaseLoader", loader_name, "load_metadata", query)

**Failures raise at the call site** rather than being logged somewhere else, so a
``try``/``except`` around the call is a working guard and the Controller can report what
went wrong. ``MetaController.call`` is the same method for the Controller's own use;
neither the View nor the Controller should reach a plugin any other way.

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
- Automatically generate final reports after threads finish

**Helper functions you don’t need to write yourself**

- ``stop_workers()`` to gracefully terminate long-running tasks
- ``discard_generator()`` to clean up when threads complete
- ``set_generator()`` and ``run_generators()`` to queue and execute background operations

What You Need to Implement
--------------------------

Only one method is abstract, and that’s ``_init()``. This is where you set up any plugin-specific logic or configuration. It’s automatically called at the end of the base class constructor.

.. note::

   Want the technical breakdown?  
   Check the :ref:`MetaModel` section of this manual — it walks through each method’s purpose and parameters.
