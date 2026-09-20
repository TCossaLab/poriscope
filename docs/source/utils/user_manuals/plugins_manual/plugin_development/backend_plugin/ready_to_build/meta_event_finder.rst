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

Helpers You Can Call
~~~~~~~~~~~~~~~~~~~~

These are implemented for you on the base. ``_get_baseline_stats`` above is abstract
because each finder decides for itself which part of a chunk counts as baseline, but the
histogram-and-fit half that follows from assuming Gaussian baseline noise is shared, so
most implementations are a few lines of policy around one call to
``_fit_baseline_histogram``.

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._fit_baseline_histogram
   :no-index:

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._gaussian_fit
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder.force_serial_channel_operations
   :no-index:
   
.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._finalize_initialization
   :no-index:
	  
.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder.reset_channel
   :no-index:
