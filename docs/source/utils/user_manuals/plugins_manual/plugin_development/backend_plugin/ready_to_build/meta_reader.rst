.. _Build_MetaReader:

Build a MetaReader subclass
===========================

.. autoclass:: poriscope.utils.MetaReader.MetaReader
    :no-members:
    :no-index:

.. note::

   **A reader carries one testing obligation the other plugin families do not.** The
   conformance suite drives every reader against a synthetic recording in its own on-disk
   format, so every reader needs an entry in ``READER_DATASET_BUILDERS``
   (``tests/unit/plugins/conformance/_recipes.py``). Reuse is the common case - the eight
   shipped readers are served by five synthetic-recording modules (Chimera, Chimera VC100,
   raw binary, NI binary and ABF2) - and a new format needs a small writer under
   ``tests/synthetic_data/``. See :ref:`plugin_conformance_testing` for which case is yours,
   and :ref:`reader_fuzz_testing` for the malformed-input checks a reader is also held to;
   both are worth reading before you implement.

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaReader.MetaReader.get_empty_settings
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader.reset_channel
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaReader.MetaReader._init
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._set_file_extension
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._get_file_pattern
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._get_configs
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._get_file_time_stamps
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._get_file_channel_stamps
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._map_data
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._convert_data
   :no-index:
   
.. automethod:: poriscope.utils.MetaReader.MetaReader._validate_settings
   :no-index:

Every read is in pA through ``_convert_data``. If your format needs its on-disk sample
type, build it in a private method and use it from ``_map_data``, as
``SingleBinaryDecoder`` does.

.. automethod:: poriscope.utils.MetaReader.MetaReader._validate_file_type
   :no-index:

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~

Methods in this section have an implementation in either :ref:`BaseDataPlugin` or :ref:`MetaReader`, but they can be overridden if necessary to tweak the behavior of your plugin.

.. automethod:: poriscope.utils.MetaReader.MetaReader.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader.force_serial_channel_operations
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._finalize_initialization
   :no-index:
