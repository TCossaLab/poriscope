.. _Build_MetaReader:

Build a MetaReader subclass
===========================

.. autoclass:: poriscope.utils.MetaReader.MetaReader
    :no-members:
    :no-index:

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaReader.MetaReader.get_empty_settings
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader.reset_channel
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaReader.MetaReader._init
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._set_file_extension
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._set_raw_dtype
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._get_file_pattern
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._get_configs
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._get_file_time_stamps
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._get_file_channel_stamps
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._map_data
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._convert_data
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~

Methods in this section have an implementation in either :ref:`BaseDataPlugin` or :ref:`MetaReader`, but they can be overridden if necessary to tweak the behavior of your plugin.

.. automethod:: poriscope.utils.MetaReader.MetaReader.force_serial_channel_operations
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._finalize_initialization
   :no-index:
