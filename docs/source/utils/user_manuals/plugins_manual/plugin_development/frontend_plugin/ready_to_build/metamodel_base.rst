MetaModel as a Base Class
=========================

:ref:`MetaModel`  is the abstract base class for all analysis tab models in Poriscope.
It handles the logic, processing, and backend operations that power your tab — things like running calculations, managing worker threads, and storing cached data.

This class does a lot of the heavy lifting behind the scenes, so you can focus on implementing just the part that makes your model unique.

What You Get by Inheriting MetaModel
------------------------------------

**Thread and worker management**

You don’t have to manually manage threads or signals. ``MetaModel`` handles:

- Spawning and tracking worker threads (``WorkerThread``)
- Connecting signals for progress updates
- Running generators in parallel or serial mode per channel

**Signals and communication**

Built-in signals allow your model to communicate with the view, controller, or even other plugins:

- - :ref:`GlobalSignal` and :ref:`DataPluginControllerSignal` for inter-plugin communication
- ``update_progressbar`` to visually track long computations
- ``add_text_to_display`` to send log output or feedback to the interface

**Caching and reporting**

- Store intermediate data with ``cache_plot_data()``
- Format and return a cached ``DataFrame`` with ``format_cache_data()``
- Automatically generate final reports after threads finish

**Helper functions you don’t need to write yourself**

- ``stop_workers()`` to gracefully terminate long-running tasks
- ``reset_lock()`` to clean up when threads complete
- ``set_generator()`` and ``run_generators()`` to queue and execute background operations

What You Need to Implement
--------------------------

Only one method is abstract, and that’s ``_init()``. This is where you set up any plugin-specific logic or configuration. It’s automatically called at the end of the base class constructor.

.. note::

   Want the technical breakdown?  
   Check the :ref:`MetaModel` section of this manual — it walks through each method’s purpose and parameters.
