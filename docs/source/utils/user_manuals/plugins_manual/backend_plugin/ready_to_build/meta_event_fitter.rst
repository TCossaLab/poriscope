.. _Build_MetaEventFitter:

Build a MetaEventFitter subclass
================================

.. autoclass:: poriscope.utils.MetaEventFitter.MetaEventFitter
    :no-members:
    :no-index:

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter.get_empty_settings
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter.construct_fitted_event
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._init
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._define_event_metadata_types
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._define_event_metadata_units
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._define_sublevel_metadata_types
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._define_sublevel_metadata_units
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._pre_process_events
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._locate_sublevel_transitions
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._populate_sublevel_metadata
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._populate_event_metadata
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._post_process_events
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~

Methods in this section have an implementation in either :ref:`BaseDataPlugin` or :ref:`MetaEventFitter`, but they can be overridden if necessary to tweak the behavior of your plugin.

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter.force_serial_channel_operations
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter._finalize_initialization
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter.reset_channel
   :no-index:

.. automethod:: poriscope.utils.MetaEventFitter.MetaEventFitter.get_plot_features
   :no-index:
