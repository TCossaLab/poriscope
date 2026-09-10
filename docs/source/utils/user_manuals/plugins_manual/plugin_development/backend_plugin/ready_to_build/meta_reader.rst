.. _Build_MetaReader:

Build a MetaReader subclass
===========================

.. autoclass:: poriscope.utils.MetaReader.MetaReader
    :no-members:
    :no-index:

.. note::

   **A reader carries one testing obligation the other plugin families do not.** The
   behavioural conformance suite drives every reader against a real file in its own
   on-disk format, so it needs a *synthetic recording* in that format — settings alone
   cannot stand in for it, since the format is the entire thing a reader varies over.

   Every reader needs an entry in ``READER_DATASET_BUILDERS``, in
   ``tests/unit/plugins/conformance/_recipes.py``, keyed by your class name — the
   suite cannot guess which format your reader speaks. How much work that entry is
   depends on the format:

   - **A covered format, same signal** (Chimera 2024-01/2024-05, Chimera VC100, raw
     binary, ABF2): the entry is one line pointing at that format's existing builder.
   - **A covered format, different rig**: call the existing generator with your own
     config. The config carries the signal and the electronics — baseline, noise,
     amplitude, ``samplerate``, and per-format fields such as ``tia_gain`` — so this
     is the rung when your reader differs in what the numbers *mean*. ``channel`` is a
     keyword argument of the generator, not a config field.
   - **A covered encoding, different container**: add a generator function to that
     format's existing module. ``synthetic_chimera.py`` holds two —
     ``generate_chimera_dataset`` and ``generate_chimera_20240101_dataset`` — sharing
     one encoder and differing only in whether the metadata sits in a sidecar
     ``.json`` or an embedded ``<END HEADER>``. No config can express that.
   - **A genuinely new format**: write a small writer under
     ``tests/synthetic_data/`` — a subclass of ``BaseSyntheticRecordingWriter``
     implementing ``_write()`` — and point your entry at that.

   Reuse is the common case: seven shipped readers are served by four writer modules.
   That does not make those formats identical, though — the two Chimera readers share
   an encoding, not a container.

   Separately, if your reader takes a setting the file itself does not carry, such as
   an externally supplied sample rate, add an entry to ``READER_EXTRA_SETTINGS`` in
   that same module.

   See :ref:`plugin_conformance_testing` for both mechanisms and the exact failure
   messages, and :ref:`reader_fuzz_testing` for the malformed-input checks your reader
   is additionally held to. Worth reading *before* you implement, not after — the
   existing writers were each derived from the real parsing code, and reading one is
   the fastest way to see what your own parser has to tolerate.

Required Public API Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaReader.MetaReader.get_empty_settings
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader.close_resources
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader.reset_channel
   :no-index:

Required Private Methods
~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: poriscope.utils.MetaReader.MetaReader._init
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._set_file_extension
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._set_raw_dtype
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

Optional Method Overrides
~~~~~~~~~~~~~~~~~~~~~~~~~

Methods in this section have an implementation in either :ref:`BaseDataPlugin` or :ref:`MetaReader`, but they can be overridden if necessary to tweak the behavior of your plugin.

.. automethod:: poriscope.utils.MetaReader.MetaReader.force_serial_channel_operations
   :no-index:

.. automethod:: poriscope.utils.MetaReader.MetaReader._finalize_initialization
   :no-index:
