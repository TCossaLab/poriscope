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

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._init
   :no-index:

Helpers You Can Call
~~~~~~~~~~~~~~~~~~~~

These are implemented for you on the base. ``_get_baseline_stats`` above is abstract
because each finder decides for itself which part of a chunk counts as baseline, but the
histogram-and-fit half that follows from assuming Gaussian baseline noise is shared, so
most implementations are a few lines of policy around one call to
``_fit_baseline_histogram``.
Both fit helpers are static methods that use no finder state, so the Raw Data tab calls
them on the class to show the same baseline the finders see.

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._fit_baseline_histogram
   :no-index:

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._gaussian_fit
   :no-index:

Where an event begins and ends is likewise shared. A finder's ``_find_events_in_chunk``
decides *that* there is an event from its threshold crossings; it then hands those
crossings to the two methods below, which place the recorded start where the signal left
the baseline band and the recorded end where it rejoined it, each judged over a run of
samples so a single noisy sample is never taken for an edge. ``NoFitter`` applies the same
judgement when it walks an event's edges, so the two agree on where an event is.

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._event_start_from_the_baseline
   :no-index:

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._event_end_from_the_baseline
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder.force_serial_channel_operations
   :no-index:
   
.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder._finalize_initialization
   :no-index:
	  
.. automethod:: poriscope.utils.MetaEventFinder.MetaEventFinder.reset_channel
   :no-index:
