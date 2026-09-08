Example Usage: RawDataView
===========================

.. code-block:: python

   @log(logger=logger)
   def _apply_filter(self, data_filter, channel_data):
      try:
         filter_data_args = (channel_data,)
         self.global_signal.emit('MetaFilter', data_filter, 'filter_data', filter_data_args, 'update_plot_data', ())
         return self.plot_data
      except Exception as e:
         self.logger.error(f"Unable to filter data with {data_filter}: {repr(e)}")
         return channel_data

Detailed Explanation
--------------------

This function, used in ``RawDataView``, delegates filtering to a subclass of ``MetaFilter``.

Steps:

#. Emits a global signal to request filtering. ``filter_data_args`` is a genuine
   one-element tuple, and ``'update_plot_data'`` is the *name* of a method on the
   ``RawDataController``, not on the view.

#. ``MetaController`` resolves that name against itself, checks it is callable, and
   relays the call to ``MainController``.

#. ``MainController`` resolves ``('MetaFilter', data_filter)`` to a live plugin
   instance, checks that ``filter_data`` will accept ``filter_data_args``, and calls
   it once.

#. ``MetaFilter.filter_data`` is annotated ``-> npt.NDArray[np.float64]``, which is not
   a tuple type, so the filtered array is passed to the callback as a single argument
   followed by ``ret_args`` (here empty): ``update_plot_data(filtered)``.

#. The controller forwards it to the view, which displays it.

This enables fully decoupled, modular plugin communication.

.. warning::

   ``_apply_filter`` reads ``self.plot_data`` on the line after the ``emit`` and returns
   it. That works only because every hop in this chain is a synchronous call: the
   connections carrying ``global_signal``/``data_plugin_controller_signal``
   (``MetaController._connect_global_signal``, ``MainController.instantiate_analysis_tab``)
   are wired with ``type=Qt.ConnectionType.DirectConnection`` explicitly, precisely so
   the callback has already run by the time the next statement executes. Before
   2026-08-31 this relied on Qt's default ``AutoConnection`` happening to resolve to a
   direct call because sender and receiver were on the same thread - true, but nowhere
   stated as a requirement. The explicit ``DirectConnection`` closes that gap: it cannot
   silently degrade to a deferred, queued call the way ``AutoConnection`` would if a
   future refactor ever moved a View/Controller onto its own ``QThread``. It still means
   this pattern must never be used from anything but the GUI thread. If you are writing
   new code, prefer doing the work *in* the callback rather than emitting and then
   reading an attribute the callback happens to have set.

.. tip::

   - `MainController` owns both the `DataPluginController` and Analysis plugins.
   - This makes it the natural mediator for handling global signals.


