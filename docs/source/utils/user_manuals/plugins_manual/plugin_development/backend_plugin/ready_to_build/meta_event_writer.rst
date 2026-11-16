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
   
.. automethod:: poriscope.utils.MetaWriter.MetaWriter._validate_settings
   :no-index:

.. automethod:: poriscope.utils.MetaWriter.MetaWriter._init
   :no-index:

.. automethod:: poriscope.utils.MetaWriter.MetaWriter._finalize_initialization
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~

Event data always reaches ``_write_data`` in pA, exactly as the reader's ``load_data``
returns it; choose the stored numeric type with ``_set_output_dtype``.

.. automethod:: poriscope.utils.MetaWriter.MetaWriter.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaWriter.MetaWriter.force_serial_channel_operations
   :no-index:
