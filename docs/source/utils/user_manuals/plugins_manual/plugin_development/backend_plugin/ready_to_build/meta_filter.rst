.. _Build_MetaFilter:

Building a MetaFilter subclass
==============================

.. autoclass:: poriscope.utils.MetaFilter.MetaFilter
   :no-members:
   :no-index:

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaFilter.MetaFilter.get_empty_settings
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaFilter.MetaFilter._init
   :no-index:

.. automethod:: poriscope.utils.MetaFilter.MetaFilter._finalize_initialization
   :no-index:

.. automethod:: poriscope.utils.MetaFilter.MetaFilter._apply_filter
   :no-index:
   
.. automethod:: poriscope.utils.MetaFilter.MetaFilter._validate_settings
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~

Methods in this section have an implementation in either :ref:`BaseDataPlugin` or :ref:`MetaFilter`, but they can be overridden if necessary to tweak the behavior of your plugin.

.. automethod:: poriscope.utils.MetaFilter.MetaFilter.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaFilter.MetaFilter.reset_channel
   :no-index:

.. important::

   ``force_serial_channel_operations`` is left out of this list on purpose. Every other
   family can override it to have its channels run one at a time; for a filter nothing
   consults it. A filter runs as a plain callable inside other plugins' loops, on several
   threads at once, so **a filter must be thread-safe**: if ``_apply_filter`` touches
   anything shared between calls, guard it there with a lock of your own. See "Filters
   are a special case" in :doc:`serial_channel_operations`.

.. automethod:: poriscope.utils.MetaFilter.MetaFilter.get_data_requirements
   :no-index:

Override this when your filter's coefficients depend on a property of the data, as
``BesselFilter`` does with ``Samplerate``: return the settings the data must match, keyed
as in your own settings, and the analysis tabs refuse to apply the filter to data at
another rate, naming both. Leave it alone when any array will do, as ``WaveletFilter``
does.
