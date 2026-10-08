.. _base_data_plugin:

Base Data Plugin
================

.. autoclass:: poriscope.utils.BaseDataPlugin.BaseDataPlugin
   :no-members:
   :no-index:

Thread safety
-------------

These two are the whole of the thread-safety contract every data plugin inherits. See
:ref:`serial_channel_operations` for when to override the first and what the second does with
the answer.

.. automethod:: poriscope.utils.BaseDataPlugin.BaseDataPlugin.force_serial_channel_operations
   :no-index:

.. automethod:: poriscope.utils.BaseDataPlugin.BaseDataPlugin.serialize_channel_operations
   :no-index:
