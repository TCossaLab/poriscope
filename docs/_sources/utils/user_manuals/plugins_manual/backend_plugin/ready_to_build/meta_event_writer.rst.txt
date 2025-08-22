.. _Build_MetaWriter:

Building a MetaWriter subclass
==============================

.. autoclass:: poriscope.utils.MetaWriter.MetaWriter
    :no-members:
    :no-index:

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaWriter.MetaWriter.get_empty_settings
   :no-index:

.. automethod:: poriscope.utils.MetaWriter.MetaWriter.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaWriter.MetaWriter.reset_channel
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaWriter.MetaWriter._initialize_database
   :no-index:

.. automethod:: poriscope.utils.MetaWriter.MetaWriter._set_output_dtype
   :no-index:

.. automethod:: poriscope.utils.MetaWriter.MetaWriter._write_channel_metadata
   :no-index:

.. automethod:: poriscope.utils.MetaWriter.MetaWriter._write_data
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaWriter.MetaWriter._rescale_data_to_adc
   :no-index:

.. automethod:: poriscope.utils.MetaWriter.MetaWriter.force_serial_channel_operations
   :no-index:
