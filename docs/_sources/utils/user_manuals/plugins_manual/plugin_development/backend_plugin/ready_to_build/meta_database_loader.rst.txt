.. _Build_MetaDatabaseLoader:

Build a MetaDatabaseLoader subclass
===================================

.. autoclass:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader
    :no-members:
    :no-index:

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_empty_settings
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.reset_channel
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_llm_prompt
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_experiment_names
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_channels_by_experiment
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_event_counts_by_experiment_and_channel
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_column_units
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_column_names_by_table
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_table_names
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.validate_filter_query
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_samplerate_by_experiment_and_channel
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_table_by_column
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.add_columns_to_table
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.alter_database
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._init
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._load_metadata
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._load_metadata_generator
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._load_event_data
   :no-index:
   
.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._validate_settings
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~

Methods in this section have an implementation in either :ref:`BaseDataPlugin` or :ref:`MetaDatabaseLoader`, but they can be overridden if necessary to tweak the behavior of your plugin.

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.force_serial_channel_operations
   :no-index:

.. automethod:: poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._finalize_initialization
   :no-index:
