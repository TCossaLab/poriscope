.. _Build_MetaConditioningLoader:

Building a MetaConditioningLoader subclass
==========================================

.. autoclass:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader
   :no-members:
   :no-index:

A loader for a new acquisition format only has to say where the pore sizes and the PSD
recordings are. The Conditioning tab does the spectral analysis itself, so a loader returns
each recording's samples in pA with its sample rate and points per average, never a PSD.
``NIConditioningLoader`` is the shipped example: it reads the CSVs with pandas and opens each
binary recording with an ``NIBinaryReader`` it owns, closing them in ``close_resources``.

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.get_empty_settings
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.get_channels
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.get_cycles
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.get_pore_sizes
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.get_psd_polarities
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.get_psd_segment_count
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.get_psd_cycle
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.get_psd_samplerate
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.get_psd_points_per_average
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.load_psd_segment
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader._init
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader._finalize_initialization
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader._validate_settings
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~

Methods in this section have an implementation in either :ref:`BaseDataPlugin` or :ref:`MetaConditioningLoader`, but they can be overridden if necessary to tweak the behavior of your plugin.

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.report_status
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.reset_channel
   :no-index:

.. automethod:: poriscope.utils.MetaConditioningLoader.MetaConditioningLoader.force_serial_channel_operations
   :no-index:

The Conditioning tab reads every channel on its own worker thread, so ``load_psd_segment``
is called from several threads at once. Reading memory-mapped files, as
``NIConditioningLoader`` does, is safe; a loader that holds an open file handle and seeks in
it is not, and must return ``True`` here. See :ref:`serial_channel_operations`.
