.. _conformance_recipes:

Writing a Conformance Recipe
============================

This page is the reference for :ref:`plugin_conformance_testing`: what, if anything, you add
so the conformance suite can build and drive your plugin. Run ``pytest -m conformance`` first;
its failure names exactly what is missing.

**Every edit below is in one file**, ``tests/unit/plugins/conformance/_recipes.py``, called
``_recipes.py`` from here on; the only exceptions are called out where they arise.

* **``MetaFilter``, ``MetaEventFinder``, ``MetaEventFitter``: yes, always.** Each of
  these is looked up by class name in a dict in ``_recipes.py``
  (``FILTER_SETTINGS``, ``EVENT_FINDER_SETTINGS``, ``EVENT_FITTER_SETTINGS``), where an
  entry is a plain ``{"YourClassName": {"Param Name": value, ...}}`` dict:

  .. code-block:: python

     # _recipes.py
     EVENT_FINDER_SETTINGS: Dict[str, Dict[str, Any]] = {
         "ClassicBlockageFinder": {"Threshold": 200.0},
     }

  You only need to list a *parameter* here if ``get_empty_settings()`` leaves it with
  no default (``Value`` omitted or ``None``) — anything your plugin already defaults is
  used as-is. If yours is a **variant** of a shipped plugin, that includes everything
  its parent left without a default, not just what you added: a variant of
  ``BesselFilter`` still has to supply ``Cutoff`` and ``Samplerate``. The ``ValueError``
  names them, so you do not have to work it out in advance.

  **The entry itself is still required even when you have nothing to put in it**, since
  the lookup is on dict membership rather than on unset parameters. A plugin whose every
  parameter has a default takes an empty dict, and two shipped fitters do exactly that:

  .. code-block:: python

     EVENT_FITTER_SETTINGS: Dict[str, Dict[str, Any]] = {
         "NoFitter": {},
         "PeakFinder": {},
     }

  The two failures you can hit are therefore distinct. No entry at all gives
  ``KeyError: No conformance recipe for YourPlugin. Add one to ...`` — which an empty
  dict resolves. An entry that exists but leaves an undefaulted parameter unset gives
  ``ValueError: YourPlugin's conformance recipe leaves [...] unset and they have no
  default``, naming the exact parameters rather than just the plugin.

  Pick those values for the test signal, not for real data. The fixtures build a 2000 pA
  baseline with 15 pA of noise and -400 pA events, so the ``Threshold: 200.0`` above says
  "halfway down a 400 pA event in this recording" — it is not a recommended setting for
  your plugin, and it would need changing if the fixture's noise or event size ever did.
  That is also why these values live in the test file rather than on your plugin class:
  they describe the test, not the science.

  **Event fitters additionally choose which events database they are driven against.**
  A *fixture* is a synthetic recording with known content planted in it, so what your
  plugin reports can be checked against what went in - and it has to contain the feature
  your fitter looks for: a step detector handed a recording with no steps proves nothing.
  A fitter gets a flat blockage by default; if that is wrong for yours, map your class to
  whichever of these shapes fits, in ``FITTER_FIXTURES``:

  .. list-table::
     :header-rows: 1
     :widths: 22 46 32

     * - Shape
       - if your fitter needs
       - as these already do
     * - *not listed*
       - nothing inside the event; the blockage alone is enough
       - ``NoFitter``
     * - ``"dip"``
       - a resolvable dip inside the blockage, as a peak-based fitter does
       - ``Basic_PeakFinder``
     * - ``"staircase"``
       - a known number of discrete levels, as a step or changepoint detector does
       - ``CUSUM``, ``ClassicCUSUM``, ``IntraCUSUM``, ``NanoTrees``
     * - ``"deep_dip"``
       - a dip both deeper than the carrier blockage and narrower than the
         peak-search window
       - ``PeakFinder``

  Those four rows account for every fitter that ships, so the quickest way to place
  your own is to find the one it most resembles. Naming it is one line:

  .. code-block:: python

     # _recipes.py
     FITTER_FIXTURES: Dict[str, str] = {
         "CUSUM": "staircase",
         "YourFitter": "staircase",
     }

  **If none of the three suits your fitter** - it looks for an exponential decay or an
  oscillation, say - **add a fixture of your own**: a new shape in the events-database
  generator, wired through to the suite in four edits, with the staircase as the worked
  example to copy.

  .. list-table::
     :header-rows: 1
     :widths: 30 38 32

     * - Edit, to add a fixture shape
       - What goes there
       - Copy from the staircase
     * - ``tests/synthetic_data/synthetic_events_db.py``
       - a new planting parameter, threaded through ``generate_events_database``,
         ``_write_channel`` and ``_build_event_trace`` — all three, or it never
         reaches the trace. Taper the shape rather than making it rectangular: sharp
         edges were measured to trip fitters *more* often, not less.
       - ``sublevel_amplitudes_pA``
     * - ``conformance/conftest.py``
       - a session-scoped fixture building a database with that parameter set
       - ``staircase_events_db_path``
     * - ``conformance/_recipes.py``
       - the shape's constants, its name added to ``FITTER_FIXTURE_SHAPES``, and a
         ``FITTER_FIXTURES`` entry mapping your fitter to it
       - ``STAIRCASE_LEVEL_AMPLITUDES_PA``, ``"staircase"``
     * - ``conformance/test_eventfitters.py``
       - add your shape to the ``by_shape`` map in the ``fitter`` fixture, **and
         write a check that reads the planted shape**. The mapping alone buys
         nothing: the four generic fitter checks pass on any signal that yields
         events, so without an assertion of your own the fixture is built, routed,
         used - and never actually examined. Nothing enforces that last part; the
         staircase and dip checks are the worked examples to copy.
       - ``staircase_fitter``,
         ``test_sublevel_count_matches_the_planted_staircase``

  There is deliberately no way to exempt a fitter: one the current fixtures cannot
  exercise fails rather than being skipped, because a missing shape is almost always
  something to plant. The generator computes arbitrary arrays, multi-channel recordings
  included (``generate_multichannel_dataset``).

  How loudly the wrong choice fails depends on your fitter, and it is worth knowing
  that "loudly" is not guaranteed. A strict peak fitter left out of its set rejects
  every planted event, which is obvious. A tolerant one does not: measured,
  ``Basic_PeakFinder`` fits all 25 events on a flat blockage and reports 6-24
  sublevels per event, because it finds peaks in the 15 pA noise — so the flat
  database looks like a success. Leaving a step detector out of
  ``"staircase"`` in ``FITTER_FIXTURES`` is quieter still: its sublevel-count check is
  never collected, so the suite goes green having never tested what the fitter is
  for.

  Check the fixture and the recipe together, since a wrong pairing of the two hides
  itself: a threshold set above the feature you are looking for costs nothing on a
  fixture that has no such feature in it.
* **``MetaWriter``, ``MetaDatabaseWriter``, ``MetaDatabaseLoader``, ``MetaEventLoader``:
  usually nothing.** These build generically from the file parameter every plugin in the
  family already has, plus the four experiment-metadata parameters the two writers
  share — and no plugin shipped in these families declares anything beyond that, so all
  four are covered with zero recipe work today. If yours does declare an extra required
  parameter with no default, you get the same
  ``ValueError: YourPlugin's conformance recipe leaves ['Your Param'] unset`` as above,
  and it names where the value goes: these four have no per-class dict, so it belongs
  in the ``overrides`` built inside that family's ``build_*`` function.
* **``MetaReader``: always, and it is the one real piece of work.** A reader's
  "recipe" is not settings — it is a synthetic file in its actual on-disk format,
  since that is the entire thing a reader varies over. Every existing format has a
  writer module under ``tests/synthetic_data/``, derived from the real parsing code
  rather than guessed - see each module's docstring for that derivation. Every reader needs an
  entry in ``READER_DATASET_BUILDERS`` in ``_recipes.py``, keyed by class name rather
  than by format, and a reader with no entry fails the same way the other families
  do — including one whose format is already covered, since the lookup is per class.
  Note what the *value* is: not settings, but a callable that writes a recording and
  returns the ground truth for it.

  .. code-block:: python

     # _recipes.py
     READER_DATASET_BUILDERS: Dict[str, Callable[[Path], SyntheticDataset]] = {
         "ChimeraReader20240501": _chimera_20240501_dataset,
         "YourReader": _your_format_dataset,
     }

  What that entry costs depends on how far your format sits from a covered one. Most
  readers land on the first row:

  .. list-table::
     :header-rows: 1
     :widths: 32 68

     * - If your reader
       - the entry is
     * - reads a covered format and wants the same signal
       - one line pointing at that format's existing builder — the usual case for a
         variant of a shipped reader.
     * - reads a covered format from a rig whose numbers mean something different
       - a call to the existing generator with your own config. The config carries
         the signal and the electronics: baseline, noise, event amplitude and
         duration, ``samplerate``, plus per-format fields such as ``tia_gain``,
         ``i_offset`` and ``filter_gain``.
     * - stores the same samples, but arranged differently in the file
       - a new generator function in that format's existing module, since the config
         describes the signal and cannot describe file layout.
         ``synthetic_chimera.py`` holds two generators for exactly this reason: the
         samples are encoded identically, but one layout keeps its metadata in a
         separate ``.json`` file and the other embeds it in the recording's own
         header. One reader opens both, so only the first is its conformance
         fixture; the second is driven by that reader's own tests.
     * - reads a genuinely new format
       - a new writer module under ``tests/synthetic_data/`` — a
         ``BaseSyntheticRecordingWriter`` subclass implementing ``_write()``.

  Your reader may need a **setting that the file itself does not carry**, the way
  ``SingleBinaryDecoder`` has to be told its sample rate because nothing in the file
  records it. Supply those in ``READER_EXTRA_SETTINGS``, as a small function that reads
  what it needs off the recording that was just written:

  .. code-block:: python

     # _recipes.py
     READER_EXTRA_SETTINGS: Dict[str, Callable[[SyntheticDataset], Dict[str, Any]]] = {
         "SingleBinaryDecoder": lambda dataset: {"Sampling Rate": dataset.samplerate},
     }

  Leave that out and you get the same ``ValueError`` as the other families, naming the
  parameter, rather than an unhelpful error from deep inside ``apply_settings``.

  Finally, once your reader has a fixture it is fuzz-tested for free: the suite feeds it
  truncated and corrupted copies of its own recording and checks it fails cleanly instead
  of hanging or crashing. You add nothing for that — see :ref:`reader_fuzz_testing`.

  What those shared mutations cannot know about is anything particular to *your* format.
  If yours has a part that identifies or describes it — a signature at the start of the
  file, a header, a companion file beside the recording — add a **mutation**: a short
  function that damages that one thing, so you find out what your parser does when it is
  wrong. Two edits, both in ``_recipes.py``. Write the function, next to the shipped ones
  — this one is ``_flip_abf2_signature`` with the name changed, and it is the whole of it:

  .. code-block:: python

     def _corrupt_your_marker(dataset: SyntheticDataset) -> None:
         """Corrupt the marker your format puts at the start of the file."""
         data = bytearray(dataset.data_path.read_bytes())
         data[0:4] = b"\x00\x00\x00\x00"
         dataset.data_path.write_bytes(bytes(data))

  then register it for your reader, below where ``MUTATIONS`` is built:

  .. code-block:: python

     MUTATIONS["YourReader"].append(("corrupt_your_marker", _corrupt_your_marker))

  The name in that tuple is what appears in the test id, so a failure points straight at
  the mutation that caused it. Nothing fails if you skip all this, which is how the most
  distinctive part of a format ends up being the one part never tested.
* **``MetaConditioningLoader``: always.** Like a reader, a conditioning loader varies over
  its on-disk format, so its entry in ``CONDITIONING_LOADER_BUILDERS`` is a callable that
  writes a synthetic experiment folder and returns the loader with its settings applied.
  ``_ni_conditioning_loader``, over ``tests/synthetic_data/synthetic_ni.py``'s
  ``generate_conditioning_folder``, is the worked example. A loader with no entry fails
  with a ``KeyError`` naming the dict.

However much or little your family turned out to need, the suite is run the same way.
Scope it to your own plugin by name while you are iterating — the parametrised test ids
carry the class name, so ``-k`` matches it:

.. code-block:: bash

   pytest -m conformance                    # every plugin, all nine families
   pytest -m conformance -k YourPlugin      # only yours, while you work

.. tip::

   Watch the units. Two plugins in this codebase declare a parameter in sigma where
   their siblings use picoamps — ``ThresholdBlockageFinder``'s ``Threshold`` and
   ``ClassicCUSUM``'s ``Step Size`` — so a recipe value copied from a sibling silently
   detects nothing. Read the parameter's ``Units`` entry rather than the sibling's
   number. Declaring ``Units`` on your own parameters is what makes this checkable.
