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

#. Emits a global signal to request filtering.

#. `MetaController` relays it to `MainController`.

#. `MainController` identifies the correct plugin and executes the call.

#. Filtered data is sent back and displayed.

This enables fully decoupled, modular plugin communication.

.. tip::

   - `MainController` owns both the `DataPluginController` and Analysis plugins.
   - This makes it the natural mediator for handling global signals.


