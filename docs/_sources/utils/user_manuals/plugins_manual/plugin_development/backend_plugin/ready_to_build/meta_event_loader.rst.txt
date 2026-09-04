.. _Build_MetaEventLoader:

Build a MetaEventLoader subclass
================================

.. autoclass:: poriscope.utils.MetaEventLoader.MetaEventLoader
    :no-members:
    :no-index:

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader.get_empty_settings
   :no-index:

.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader.load_event
   :no-index:

.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader.get_num_events
   :no-index:

.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader.get_samplerate
   :no-index:

.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader.get_channels
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader._init
   :no-index:
   
.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader._validate_settings
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~

Methods in this section have an implementation in either :ref:`BaseDataPlugin` or :ref:`MetaEventLoader`, but they can be overridden if necessary to tweak the behavior of your plugin.

.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader.force_serial_channel_operations
   :no-index:

.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader._finalize_initialization
   :no-index:

.. automethod:: poriscope.utils.MetaEventLoader.MetaEventLoader.reset_channel
   :no-index:
