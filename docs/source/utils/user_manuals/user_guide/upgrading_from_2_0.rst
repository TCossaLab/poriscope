.. _upgrading_from_2_0:

Upgrading from 2.0
==================

Poriscope 3.0 changes the layout of some of the files it saves and some of the numbers its
plugins compute. This page lists what opens in which version, which results change, and what a
plugin author has to update. The full list is under **Breaking Changes** in the
`changelog <https://github.com/TCossaLab/poriscope/blob/main/changelog.md>`_.

Saved files
-----------

.. list-table::
   :header-rows: 1
   :widths: 40 30 30

   * - File
     - Saved by 2.0, opens in 3.0?
     - Saved by 3.0, opens in 2.0?
   * - Session file (**Save Session**) and the autosave
     - Yes, without recorded actions
     - No
   * - ``tab_action_history.json``
     - No
     - 3.0 does not write it
   * - Plot configuration (**Save Plot Configuration**)
     - No
     - No
   * - Metadata database (fitted event database)
     - Yes
     - Yes
   * - Raw event database (**Commit Events** in the Raw Data tab)
     - Yes
     - Yes
   * - Filters file (**Save Filter**)
     - Yes
     - Yes

**Within 3.x.** From 3.0 on, the format of a saved file changes only in a major version, so a
file saved by any 3.x release opens in every other 3.x release. A file saved by a later major
version is refused with a message that says so.

**Sessions and the autosave.** A 2.0 session opens in 3.0 with its plugins and its tabs' filters,
but no recorded actions: 2.0 kept them beside the autosave, in ``tab_action_history.json``, which
3.0 neither reads nor writes. When the autosave holds analysis tabs, the first **Restore Session**
after upgrading says that the session has no actions to replay and, if that file is still in the
session folder, that it cannot be replayed; the file is left in place. That Restore saves the
autosave again in 3.0's format and says so, so the note does not appear again, and from then on
Poriscope 2.0 cannot restore the autosave. A 2.0 session file you open with **Load Session** is
left as it was, so 2.0 can still open it; to keep a session for 2.0, save it with **Save Session**
in 2.0 before upgrading. Poriscope 2.0 refuses a session saved by 3.0, and 3.0 refuses one saved
in a later format with a message naming the version that saved it. See :ref:`menus_and_sessions`
for how sessions work in 3.0.

**Plot configurations.** **Load Plot Configuration** refuses a plot configuration saved by
Poriscope 2.0 with an error and replays none of it; draw the plots again in 3.0 and save them with
**Save Plot Configuration**. Poriscope 2.0 cannot replay one saved by 3.0.

**Metadata databases.** 3.0 indexes a 2.0 database the first time it opens it, which makes
filtered plots faster. Writing into a 2.0 database adds a column recording the plugins and
settings that produced each channel. A database 3.0 creates records its schema version, and one
created by a later major version is refused with a message. When it opens a database, Poriscope
2.0 checks only which tables it holds, and 3.0 adds none; the loader of Poriscope 1.7.0 was
checked against a database 3.0 created and opened it. A metadata database now holds results from
one type of fitter: writing a different type of fitter into one, a 2.0 database included, is
refused, so use a new file per fitter type.

**Raw event databases and filters files** have the same layout in both versions. A raw event
database 3.0 creates also records its schema version, which Poriscope 2.0 ignores: the 2.0.2
loader was checked against one and opened it. A Raw SQL filter can be plotted only in 3.0 (see
:ref:`filtering-raw`).

Results that change
-------------------

These change what a step computes when it runs in 3.0. A database written by 2.0 keeps the
values 2.0 wrote; to compare with 3.0, run the step again.

**Baseline and thresholds** (event finding):

- Baseline sigma, and every threshold set in sigma, moves slightly: the baseline histogram uses
  Rice's rule for its bins, removing a bias that inflated sigma on short chunks, and short clean
  chunks are no longer skipped.
- A chunk mostly in an occupied state reports the open-pore level as its baseline, not the
  occupied level.
- A second population just below the baseline no longer widens the fitted baseline sigma.

**Event boundaries** (event finding, and fitting with ``NoFitter``):

- Event finders place an event's boundaries where the signal leaves and rejoins the baseline, so
  stored event windows, start times and paddings move to the edges.
- ``NoFitter`` places an event's edges in the same way and reports the mean of the blocked
  stretch, and its baseline standard deviation is no longer inflated by the edge.

**Fits** (Event Analysis and Protein):

- ``CUSUM``, ``ClassicCUSUM`` and ``IntraCUSUM`` resolve sublevels that follow a large edge, so
  fits report more sublevels than before.
- ``PeakFinder`` classifies each channel from its own events and never pools channels. Its
  classification report and plots are written per channel, as
  ``<events file>_ch<N>_classification_report.txt`` and
  ``<events file>_ch<N>_<fit>_classification.png``.
- The Protein tab's double-Gaussian fit no longer fits a component narrower than a quarter of a
  bin. A fit whose component sits on that limit, or whose two means nearly coincide, counts as
  finding one population; a real population narrower than half a bin is kept.

**Readers and filters** (everything read from raw data):

- Reads round to the nearest sample, so results can move by one sample at a chunk boundary,
  which no longer duplicates one sample and drops another.
- The Bessel filter accepts low cutoffs it used to refuse; filtered values at other cutoffs are
  unchanged to within a thousandth of the noise.
- An int16 ABF file with a non-zero instrument or signal offset converts as ``pyabf`` does, with
  the offset added after the gain. None of the lab's recordings has one.
- ``TCossaLabABFReader`` and ``LegacyElementsReader`` refuse a file whose current channel's units
  are not a current, instead of reading it as pA, and no longer refuse a file for its ADC channel
  count or channel names.
- ``ChimeraReader20240101`` is removed. ``ChimeraReader20240501`` opens its files, the Chimera
  VC400 ``.log`` files with their settings embedded at the start, and reads the same values from
  them.

**Assisted subset filters** (Metadata and Protein plots and exports):

- A filter containing ``OR``, or ending in a ``--`` comment, is confined to the selected
  experiments and channels. In 2.0 such a filter drew every channel in the database for each one
  ticked.
- A filter whose brackets do not balance is refused, and so is one that starts with ``SELECT``,
  which belongs in Raw SQL mode. See :ref:`filtering-assisted`.

For plugin authors
------------------

A plugin written for 2.0 needs these changes; the changelog lists every one.

Data plugins:

- ``report_channel_status`` is renamed ``report_status``, with the same arguments.
- ``close_resources`` takes no channel and releases the whole plugin; it does nothing by
  default, so a plugin holding nothing need not define it.
- ``reset_channel`` requires a channel, as do ``MetaDatabaseWriter._initialize_database`` and
  ``_write_experiment_metadata``.
- ``MetaEventFinder.get_single_event_data`` raises ``IndexError`` for an index with no event
  instead of returning ``None``.
- ``MetaDatabaseLoader.load_event_data`` yields ``padding_before`` and ``padding_after`` as
  floats in microseconds.
- ``BaseDataPlugin.replace_raw_settings_option`` and ``ABF2Header`` are removed, and
  ``TCossaLabABFReader`` and ``LegacyElementsReader`` are now subclasses of ``ABFReader``.

Analysis tabs:

- Recorded actions are declared on Controller methods only: ``register_action`` takes the
  action's name and requires ``kind=``, ``MetaView.record_action`` and
  ``MetaView.discard_last_tab_action`` are removed, and an action file saved by an earlier
  version is refused.
- The plot configuration is read and written by the tab's Model
  (``MetaModel.save_plot_configuration`` and ``read_plot_configuration``).
- ``MetaView.update_plot_data`` and ``MetaView.plot_data`` are removed; draw through the tab's
  own View methods.
- ``DataPluginModel.apply_settings`` is removed; call ``apply_settings`` on the plugin itself.
- ``MetaSubsetTabControls`` requires ``validate_inputs``, ``MetaSubsetTabView`` requires
  ``_replot_after_shift``, and ``MetaEventTabView`` requires ``_event_controls`` and
  ``_handle_plot_events``.
- Many signals and methods of the Raw Data, Metadata, Protein and Clustering tabs are renamed,
  moved or removed; check the changelog before subclassing one.
