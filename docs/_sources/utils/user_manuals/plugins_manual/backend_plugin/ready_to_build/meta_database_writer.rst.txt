.. _Build_MetaDatabaseWriter:

Build a MetaDatabaseWriter subclass
===================================

.. autoclass:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter
    :no-members:
    :no-index:

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter.get_empty_settings
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter.reset_channel
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter._init
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter._initialize_database
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter._write_experiment_metadata
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter._write_channel_metadata
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter._write_event
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~

Methods in this section have an implementation in either :ref:`BaseDataPlugin` or :ref:`MetaDatabaseWriter`, but they can be overridden if necessary to tweak the behavior of your plugin.

.. automethod:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter.force_serial_channel_operations
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter._finalize_initialization
   :no-index:
