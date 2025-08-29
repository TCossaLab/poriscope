.. _Build_MetaEventFinder:

Building a MetaEventFinder subclass
===================================

.. autoclass:: poriscope.utils.MetaEventFinder.MetaEventFinder
    :no-members:
    :no-index:

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder.get_empty_settings
   :no-index:
   
.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder.close_resources
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._get_baseline_stats
   :no-index:

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._find_events_in_chunk
   :no-index:

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._filter_events
   :no-index:
   
.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._validate_settings
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder.force_serial_channel_operations
   :no-index:
   
.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._finalize_initialization
   :no-index:
	  
.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder.reset_channel
   :no-index:
