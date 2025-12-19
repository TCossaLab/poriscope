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

.. automethod:: poriscope.utils.MetaFilter.MetaFilter.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaFilter.MetaFilter.reset_channel
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

.. automethod:: poriscope.utils.MetaFilter.MetaFilter.force_serial_channel_operations
   :no-index:
