## Poriscope 2.0.0: in progress

* **Corrected what filter types 4 and 5 mean; no behaviour change**: they name which arm of the construct the bound star sits on - 5 the long, higher-ECD arm and 4 the short one - and say nothing about the order it threaded, which is what the report's old `star translocates first` / `last` wording claimed and got wrong for every backward event

* The normalized peak prominence report now gives each standard deviation as a single pA span rather than a multiplicative factor and a range, and chains its three unit systems with `~` rather than `=`, since rounding makes them not literally equal

* **A bound-star candidate that is the widest peak in its own event is no longer promoted to type 4 or 5** - a star is a sharp spike, and the depth floor alone admitted carrier bodies and broad folds; events the rule leaves starless are counted separately in the report rather than folded in with the genuinely starless

* **The double-Gaussian fit now fits a flat constant as a seventh free parameter**, so a uniform background is modelled rather than absorbed by widening the two components; the six-parameter fit is run alongside it and kept where the constant made the residual worse, and the first six positions of `params` are unchanged

* **Normalized peak classification is now fitted on a base-10 log scale**, which is the shape the upper population actually has; the plot axis, the threshold annotation and the report read in log units, with the equivalent ratio and - where a reference level is available - the equivalent current in pA alongside

* **Breaking: `PeakFinder`'s shipped defaults are now a working barcode configuration** - `Event Type` `Barcode`, `Number of peaks` 4, filter thresholds -5 and +5, `Peak to Peak Distance Ratio` 30% - so results change for anyone who accepted the old defaults; a saved configuration keeps what it stored, so only new plugin instances see them

* **Five metadata fields are no longer written to the database**: `unfolded_level`, `folded_level`, `bound_star` and `translocation_confidence` from the events table and `base_at_edge` from the sublevels table. They are still computed and every internal reader is unchanged, but a database written from now on replays without the unfolded-level reference line and its sigma bands, the bound-star annotation and the translocation confidence

* `PeakFinder.get_metadata_columns` and `get_sublevel_columns` no longer name the five fields it keeps for itself, so the columns it reports, the types and units it declares and the keys `get_single_event_metadata` hands out all agree again

* **Barcode selection now scores peak width as well as spacing, and no longer prefers on ECD by default**: spacing and width are both set by how fast the construct threaded, so a barcode's labels stay alike in both even when they thread at different depths, which a depth-weighted term does not

* **Breaking: the barcode is now the best-*matched* set of type-1 peaks rather than the most prominent consecutive run**, scored on how alike its consecutive spacings and its peaks' ECDs are; a winning set may skip an off-pattern peak, which keeps its type 1 and so does not appear in the event's `sequence`

* **The bound-star peak now carries its end in its own `filtered` label**, 5 for the long end and 4 for the short, so the starred peak can be pointed at downstream rather than only named on the event; expect the Type -1 count to fall by exactly one peak per starred event

* **Breaking: `filter_peaks` typed carrier-seated peaks as baseline peaks in the barcode branch.** The baseline band is now a fixed 3 sigma rather than sized from `Higher Filter Threshold`, and type 1 is tested ahead of type 0, so which peaks come out 0, 1 and -1 - and therefore which events get a sequence - changes on any dataset whose `Higher Filter Threshold` is not 3

* **A type-1 peak whose base was pinned to an end of the trimmed event is now rejected to -1**: peak detection stops at the array edge, so that base holds whatever the event was doing at its own edge rather than a real minimum, and neither it nor the prominence measured from it describes the peak

* **Peak prominence classification now splits on `normalized_prominence` rather than raw `prominence`**, so the threshold is comparable across events whose carrier level drifts through a run; a peak whose event never got an unfolded level is skipped rather than classified on raw prominence

* The `PeakFinder` changes above are Nada Kerrouri's, integrated from `feature/peakfinders_1.8.0`

* **`BoundedBlockageFinder`'s baseline standard deviation moves by up to 1%**, because the histogram fit it shares with `ClassicBlockageFinder` now lives on `MetaEventFinder` in one copy, and that copy centres the fit window on the histogram peak as Classic always did and Bounded never did

* Removed `ClassicBlockageFinder._gaussian`, which had no callers anywhere in the package or the test suite

* **Breaking: `QWidgetABCMeta` is removed - use `QObjectABCMeta`**, which is the same implementation, since PySide6 gives `QObject` and `QWidget` the same metaclass and the two names were never two classes; abstract Qt classes are refused exactly as before

* The duplication ratchet now measures the event finders as well, so the step that lifts their shared baseline fit out of two copies cannot add a duplicate elsewhere unnoticed

* **Fixed loading a session file as a filter file creating empty, unusable filters**: every entry in a filter file must now hold filter text, so a JSON object that is not a filter file is refused whole and the tab's own filters are left alone

* **Fixed the Protein tab contradicting its own refusal**: a refused event plot - two channels in scope, an experiment the database no longer holds - was followed by "No data available for event_id N", which named the event rather than the reason; that line now appears only when the fetch really did come back empty

* A loader that returns event rows without the id column it was asked for is now reported on the status panel instead of only in the log

* The documentation render check now runs on every push to `develop` as well as on pull requests, since `git flow feature finish` merges locally and opens no pull request for it to see

* A `requirements.txt` written in UTF-16 or carrying a byte-order mark is now refused by a pre-commit hook, since that is what PowerShell redirection produces by default and git records such a file as an unreviewable binary blob

* **Breaking: the event plot's resolve-and-load chain is one method on `MetaSubsetTabController`** rather than a copy in each database-backed tab, so a failed event plot now reports the same way on both: one message naming what was being plotted and the event ids, where the metadata tab named only the ids and the protein tab only the plot type

* A metadata event plot asked for with no events selected is now refused with a message instead of running a query that could not match anything

* **Breaking: the two database-backed tabs' Models now share a `MetaSubsetTabModel` base**, which takes `load_filters` and `save_filters` off `MetaModel` along with the events-table lookups behind an event plot, so a Model that does not back a subset tab no longer inherits them

* **Breaking:** subset filter files are read and written by `MetaSubsetTabModel.load_filters` and `save_filters` rather than in the view, so `MetaSubsetTabView._load_filter` and `_save_filter` only choose the file and `set_loaded_filters` decides what happens to what it held

* **A filter file that cannot be read is now reported on the status panel** and leaves the tab's existing filters untouched, instead of failing with an unhandled error

* **A filter file that cannot be written is now reported on the status panel** - a full disk or a read-only folder used to look exactly like a successful save

* **Breaking:** `MetaView._logscale_and_filter_multiple_columns` is removed. Every plot path now asks its controller for the filtering, which `MetaModel.logscale_and_filter_columns` does, so the published view base no longer carries it - or imports numpy at all

* **Breaking:** the subset tabs' Scatterplot is filtered and log-scaled by `MetaModel.logscale_and_filter_columns` rather than in the view, and the round trip is shared: `scatterplot_requested` and `set_scatterplot` are on `MetaSubsetTabView` and `filter_scatterplot` on `MetaSubsetTabController`, so `MetadataView` and `MetadataController` no longer carry their own

* **Breaking:** the Protein tab's Peak Scatterplot keeps its own `xyerr_scatterplot_requested` and `set_xyerr_scatterplot`, and `_plot_xyerr_scatterplot` now requires both error columns rather than accepting one

* **Fixed the Protein tab's error bars being able to come adrift from the points they annotate**: the error columns were read from the unfiltered data while the values were filtered, so any row the filter dropped left the two different lengths

* **Breaking:** the Protein tab's Monte Carlo geometry sampling is `ProteinModel.sample_vm_solutions` and `sample_event_geometries` rather than the view's, so `ProteinView._generate_vm_ensemble` and `_compute_theoretical_blockages` are gone, `set_distribution_fits` takes the three frames it draws, and `set_ensemble_geometry_fit` takes the two solution sets instead of the pore geometry

* **Breaking:** the Protein tab's Ensemble distribution histogram is averaged by `ProteinModel.build_all_points_histogram` rather than in the view, so `_update_distribution_ensemble` asks for the subset instead of fetching and walking it, `set_ensemble_histogram` draws what comes back, and `ProteinView._construct_all_points_histogram`, `hist_min` and `hist_max` are gone

* **An event with no samples between its paddings no longer fails the Protein tab's Ensemble distribution plot** with an unhandled error - it is skipped, with a note in the log, as a zero-baseline event already was

* **Breaking:** the Protein tab's per-event histograms are binned by `ProteinModel.build_event_histograms` rather than in the view, so `event_histogram_fits_requested` and `distribution_fits_requested` carry the events and the bin request, `set_event_histogram_fits` and `set_distribution_fits` take the histograms as arrays rather than dataframes, and `ProteinView._construct_single_event_histogram` is gone

* **Breaking:** the Protein tab's Individual Distribution plot now bins each event over its own range, as the Event Histogram plot already did - the range used to accumulate across the events of a plot, so the bins an event was drawn on depended on how many events preceded it

* **An event whose baseline is zero is now skipped** on the Protein tab's per-event histograms, as it already was on the all-points histogram, rather than being drawn as an empty subplot and exported as a column of blanks

* **The Protein tab now reports a bin width or count it cannot use** on the status panel, instead of writing one log line per event and drawing a grid of empty subplots

* **Fixed the Metadata tab drawing an Event Overlay on top of the previous plot** instead of replacing it: switching to a Raw or Filtered Event Overlay from any other plot type left whatever was already on the axes, so two unrelated pictures were superimposed

* **Breaking:** the Metadata tab's Kernel Density Plot and Histogram are filtered, log-scaled and given their shared plot limits by `MetadataModel` rather than in the view, so `density_requested` and `histogram_bins_requested` carry the raw columns and their log flag, and `set_kernel_densities` and `set_histogram_bins` take the newest dataset and the widened limits and accumulate it themselves

* **A 1D Density plot on a subset with no usable values now leaves the previous plot in place**, rather than clearing the axes and drawing nothing

* **Breaking:** the Metadata tab's Heatmap, Scatterplot and 3D Scatterplot are filtered and log-scaled by `MetaModel.logscale_and_filter_columns` rather than in the view, so `MetadataView.heatmap_requested` carries the raw columns and their log flags, and `_plot_scatterplot` and `_plot_3d_scatterplot` now request the filtering and draw the answer through `set_scatterplot` and `set_3d_scatterplot`

* **Categorical Histograms are now ordered by count**, tallest bar on the left; when more than one subset is overlaid the order comes from their combined totals, so every subset shares one axis

* **Breaking:** the Metadata tab's All Points Histogram and Event Overlay are built by `MetadataModel.build_all_points_histogram` and `build_event_overlay`, so `MetadataView._construct_all_points_histogram`, `_construct_event_overlay` and `MetadataController.load_event_subset` are gone, and `MetadataView.update_plot` no longer draws the all-points histogram types

* The Metadata tab now reports an All Points Histogram or Event Overlay it cannot build on the status panel, instead of failing with an unhandled error

* **Fixed the Metadata tab's 1D Density plot accepting a bin width and ignoring it.** The shared plot limits were being read off the dataframe rather than the data, so they came out as column names and the width could not be divided into them

* **The 1D Density plot now says when a column is empty for the selected subset** instead of failing with an unhandled error, matching what the 1D Histogram already did

* **Breaking:** the Metadata tab's shared plot limits now describe the filtered, log-scaled values rather than the raw column, so a log-scaled density plot bins differently than before - the limits exist to make overlaid datasets comparable on what is actually drawn

* **Fixed exporting the plot data of a categorical histogram failing with an error.** It had never worked: the export coerced every cached series to a number, which category names are not. Numeric exports are unchanged

* **A capture-rate plot with too few events now says how few**, instead of reporting the generic "no data available after filtering"

* **Breaking:** the Raw Data tab's plot time axes are built by `MetaModel.time_bases` rather than in the view, so `RawDataView.update_plot`, `set_trace_data`, `set_event_plot_data` and `_update_event_plot` take the axis alongside the samples and `baseline_stats_requested` carries it

* **Breaking:** `EventAnalysisModel.event_time_bases` is now `MetaModel.time_bases`, taking a scale and an offset so one derivation serves both an event plot in microseconds and a trace plot in seconds from the start of the recording

* **The Clustering tab now says what is actually wrong with a rejected SQL filter** instead of also telling you to check your column selections, which was the wrong advice for an unknown column, a syntax error or a complete `SELECT` pasted into the filter box

* **Breaking:** the Clustering tab's filtering and log-scaling moved to `ClusteringModel.build_clustering_frame`, so `ClusteringView.cluster_requested` and `ClusteringController.cluster` now carry the unfiltered rows and the column spec rather than a prepared frame

* A clustering request naming a column the loader did not return is now reported on the status panel instead of failing with an unhandled error

* **Breaking:** the Event Analysis plot's time axis is built by `EventAnalysisModel.event_time_bases` rather than in the view, so `EventAnalysisView.update_plot_samplerate` and `plot_samplerate` are gone and `set_event_plot_data` takes the axis as its second argument

* **Breaking:** `MetaEventTabController.update_plot_samplerate` is removed - it relayed a sampling rate to the view, but both event tabs called the view directly and nothing ever called the relay

* The refactor-coverage audit now runs on every branch push, not only on internal pull requests, so a method the refactor moves cannot lose its test coverage unnoticed

* The analysis-tab MVC boundary check no longer counts an import a view uses only to write a type, since that is not computation; `python scripts/check_mvc_boundary.py --verbose` names the imports it exempted

* **Breaking:** `MetaSubsetTabView.event_id_rows` and `set_event_id_rows` are typed `Optional[pandas.DataFrame]` rather than `Optional[Any]`, which is what they have always held

* The subset tabs' controllers no longer write into the view's filter list directly; `MetaSubsetTabView` gained `commit_filter` and `get_subset_filters` for them to go through

* `restore_subset_filters` has moved from `MetadataView` and `ProteinView` to `MetaSubsetTabView`; the two copies were identical apart from the name each held its controls panel under

* **Fixed restoring a session losing the last-restored tab's subset filters**: the session was written back while that tab's filter list was still empty, so the filters survived one restore and were gone from the next - in practice the Metadata tab kept its filters and the Protein tab did not

* **Breaking:** a subset filter being validated now travels with the request instead of being parked on the view: `filter_validation_requested` and `raw_filter_validation_requested` carry the filter's name and the name it replaces, `MetaSubsetTabController.relay_query` and `validate_raw_filter` take them as arguments, and `MetaSubsetTabView.clear_pending_filter_state` and `MetaSubsetTabController.on_raw_filter_validated` are gone

* **Status panel messages are now timestamped**, so the same message arriving twice is visibly two messages rather than looking like the panel never changed

* **Fixed the Metadata and Protein tabs silently widening the experiment and channel scope back to everything**: re-reading the database structure - which happens whenever the loader changes or the selection tree is opened - overwrote the scope you had chosen, so plots quietly used more data than was asked for and heatmaps refused with "Only a single channel can be used"

* **The Metadata tab's Capture Rate plot now honours an explicit bin width**, which was accepted and then ignored, failing with an unhandled error

* Fixed the Metadata tab failing with an error when an All Points Histogram is plotted after a different plot type

* **Categorical histograms now show missing values as an explicit "null" category** instead of failing on a column that contains any

* The Metadata tab now reports a heatmap or capture-rate plot it cannot compute on the status panel, instead of failing with an unhandled error

* **The Protein tab now says on the status panel why a distribution plot was refused** - more than one experiment or channel selected, or an experiment with no channel - instead of writing only to the log and drawing nothing

* **Finding or fitting events with no filter selected now asks for confirmation first**: on a noisy trace an unfiltered run can register almost every sample as an event, which takes a very long time and is hard to tell apart from the application hanging; cancelling works, but only takes effect at the end of the current chunk, so it can be slow to respond

* **Fixed the Raw Data tab asking about the wrong channel before re-running event finding**: if it could not read whether a channel was already finished, it reused the previous channel's answer, so the "start over?" prompt could appear for a channel that was not finished or be skipped for one that was

* Event finding now reports a channel it cannot read or start and continues with the others, and says on the status panel when a channel has no time range set instead of failing silently

* Fixed the Raw Data and Event Analysis tabs failing with an unhandled error, rather than reporting it, when an action arrived with no channel selection

* The Metadata and Protein tabs now report a database whose columns or experiment list cannot be read, instead of leaving the pickers silently unchanged

* **Fixed the Metadata tab renaming a raw SQL filter when it was loaded from a file**: the filter came back as `<name>_raw_assisted` and was treated as an assisted filter from then on, rather than as the raw filter that was saved

* The Protein tab now also reports a raw SQL filter the database itself rejects in a dialog rather than on the status panel, so both ways a raw filter can be refused read the same on both tabs

* **The SQL shown on the status panel is now the query that actually pulls the subset**, rather than the smaller one built to validate the filter, and it is shown when the filter is applied rather than when it is created - repeated only when it changes

* **Fixed the Metadata tab plotting the wrong subset's data when a database call failed**: the query, the column units and the event generator were each reused from the previous subset, so a failure mid-plot drew the previous subset under this one's label, or labelled the axes with another column's units

* A subset the Metadata tab cannot query, load or read the units of is now reported instead of failing silently

* **Fixed the Metadata tab plotting another channel's events when the experiment could not be looked up**: the events to plot were resolved without their experiment and channel scope, so an event number that exists in more than one channel could return the wrong channel's data

* Fixed the headless flow tests aborting the interpreter instead of finishing: the harness closed a tab without stopping its worker threads, so Qt destroyed a thread that was still running

* **Fixed plotting a column that is empty for the selected subset failing with an error** instead of saying there is nothing to plot - most easily hit by histogramming a protein fit column over a subset that was never fitted

* **Fixed the Protein tab drawing empty axes in silence** when the selected subset holds no events; both distribution modes now say so

* **Breaking: raw SQL subset filters can no longer be selected for a plot**, on either tab, and say so when chosen. They never worked - the filter was passed where a WHERE clause was expected, so the database rejected the query and the plot came back empty without a word. Creating, saving and loading them is unchanged

* **Fixed the Protein tab offering to overwrite fit data based on a stale answer**: if it could not read whether the database already held fit columns it reused the previous answer, so the "overwrite?" prompt could appear for a database with nothing to overwrite, or be skipped for one that had; it now reports the failure and commits nothing

* Committing protein fits now reports a database that refuses the write instead of announcing new columns to the other tabs regardless

* **Fixed the Protein tab showing one query on the status panel while running another**: for a raw SQL subset it displayed the query built from the filter and then loaded through a differently scoped one; it now shows the query that runs

* **Fixed the Protein tab reading the whole database when a raw SQL subset could not be scoped**: an experiment or channel it could not place was dropped from the query without a word, so a filter meant for one channel returned every channel's events; it now stops and says so

* The Protein tab now builds and loads its distribution subsets through a direct call from its controller rather than through the signal bus, so a filter the database refuses is reported instead of silently plotting nothing

* Fixed the Protein tab's ensemble distribution failing with an unhandled error, rather than stopping quietly, when no subset produced any data to fit

* **Fixed the Metadata tab not reporting an event-data filter the database refuses, and never showing the SQL for an event plot**: the refusal was invisible and the plot went ahead, because the query builder returns the query and the reason together and only the pair was being checked

* **Fixed the Protein tab plotting another channel's events when the experiment could not be looked up**: the events to plot were resolved without their experiment scope, so an event number that exists in more than one channel could return the wrong channel's data; it now stops and says so

* The Protein tab now asks its database loader for event plot data through a direct call from its controller rather than through the signal bus, so a lookup that fails is reported instead of silently widening the query

* **Fixed the Raw Data tab drawing nothing when the requested time range ran past the end of the file**: it now plots what the channel holds and says on the status panel that it trimmed the range, and says so too when the range starts past the end

* Fixed `construct_event_data_query` not documenting that it raises for an unknown experiment name, and collapsed three identical copies of its SQL id-list helper onto one

* A subset export to CSV that matches no events, or that the database refuses, is now reported before the export starts instead of running the progress bar to the end in silence, and no longer uses up the next export's name

* **A subset filter naming a column the database does not have is now reported instead of silently disappearing**: the Metadata and Protein tabs discarded such a filter with nothing but a line in the log, so it looked as though nothing had happened

* Validating a subset filter no longer queries across all three metadata tables regardless of what the filter references, which was joining `sublevels` and `experiments` even for a filter over `events` alone

* `relay_query` is now provided by `MetaSubsetTabController` instead of being implemented separately by each subset tab

* `_delete_filter` is now provided by `MetaSubsetTabView` instead of being abstract, so a subset-tab plugin no longer has to implement it

* The Protein tab now reports a raw SQL filter that is not a complete SELECT statement in a dialog rather than on the status panel, matching the Metadata tab - the filter dialog has just closed at that point, so a status line was easy to miss

* `show_edit_filter_dialog` is now provided by `MetaSubsetTabView` instead of being abstract, so a subset-tab plugin no longer has to implement it

* Fixed the Metadata tab failing with an unhandled error, rather than reporting it, when the database returned rows with no `event_id` column while rebuilding its filtered-event cache

* The Metadata tab now says the current scope when no events match a filter, and labels a subset with the filter expression when no filter name is selected instead of the word "Filter" - both matching the Protein tab

* **Breaking:** `get_selected_filters` has moved from `MetadataView` and `ProteinView` to `MetaSubsetTabView`, which now requires subclasses to implement a `_subset_controls` property returning their controls panel

* **Breaking:** `update_units` has moved from `MetaSubsetTabView` to `MetadataView` and `update_column_units` is no longer on `MetaSubsetTabController`; only the metadata tab displays column units, so a plugin subclassing the shared subset-tab base no longer inherits either

* The Event Analysis tab now says which event indices were out of range and how many events the channel actually holds, instead of reporting "No data available for plotting"

* An event the Event Analysis tab cannot load, or whose fit features cannot be read, no longer abandons the whole plot: the remaining events are still drawn

* **Fixed the Event Analysis tab asking about the wrong channel before re-fitting**: if it could not read whether a channel was already fitted, it reused the previous channel's answer, so the "start over?" prompt could appear for a channel that was not fitted or be skipped for one that was

* Event fitting now reports a channel it cannot read or start and continues with the others, instead of abandoning the whole batch

* Writing the Event Analysis tab's fitted events now reports a channel the database writer cannot accept and writes the rest, instead of abandoning the whole write; and a loader whose channels cannot be read is reported rather than leaving the channel list silently unchanged

* Committing the Raw Data tab's found events now reports a channel the writer cannot accept and commits the rest, instead of abandoning the whole commit

* The Raw Data tab now says which event indices were out of range and how many events the channel actually holds, instead of reporting "No data available for plotting"

* Stepping the Raw Data tab's event index below 0 now says so on the status panel, instead of declining silently and only logging to the console

* **The "No Filter" option no longer disappears from the Raw Data and Event Analysis filter dropdowns once a filter exists**: choosing not to filter is a valid selection, so it stays available, and it is now also what a dropdown falls back to when the filter it was showing is deleted (a newly created filter is no longer selected for you)

* **Fixed the Raw Data tab's event plots showing the wrong events**: if the tab could not read an event finder's state, it silently reused the previous channel's answers — including the event count that decides which event indices are in range — and an event that failed to load was replaced by the previous one under the wrong index

* **Fixed the Raw Data tab plotting one channel's trace under another channel's label**, and the same fault when a filter failed: a channel the reader could not supply silently reused whichever channel was loaded before it, on both the trace and the noise-spectrum plots

* The Raw Data tab now asks each event finder for its channels through a direct call from its controller rather than through the signal bus, so a finder that cannot answer is reported rather than silently leaving its time ranges unset

* The golden files that pin the app's numerical output are now checked to be running at all, so a missing test dependency can no longer leave those numbers unpinned while the test suite still reports a pass

* **Fixed a tab being unable to use a plugin it was showing in its dropdown**, reported when restoring a saved session: the tab was given the list of plugins before it was given access to them, and filling the dropdown immediately asks the selected plugin for its columns

* **Fixed the clustering settings dialog failing with an error instead of opening** when the column list could not be read from the database

* Analysis tabs can now call a data plugin directly through `call()` on their model or controller, so a failed plugin call raises where it happened instead of being logged several hops away and leaving the caller with the previous call's answer

* The behavioural conformance suite's resource-leak check is extended to readers and loaders, not just writers

* Fixed the pydoclint gate failing on `PeakFinder._curve_fit_bounded`: a failed double-Gaussian fit is now re-raised from inside its own `except` clause rather than stashed and raised after the loop, which the checker could not read as `RuntimeError`/`ValueError`

* The behavioural conformance suite's readers, database loaders and event loaders now fail with a clear message (matching writers) if a new plugin declares a required parameter with no recipe entry, instead of an unrelated validation error

* Conformance failure messages now name the exact dict or builder to edit for the plugin's family, and `scripts/new_plugin.py` points new plugins at the conformance suite alongside the compliance and schema checks

* The CUSUM family (`CUSUM`, `ClassicCUSUM`, `IntraCUSUM`) is now checked against a known planted *sublevel* count, not just a known event count

* Peak-based fitters are now checked against the depth of the planted dip, which their previous conformance checks could not distinguish from a flat blockage

* Which synthetic recording each event fitter is tested against is now one entry in `FITTER_FIXTURES`, replacing three separate sets

* `NanoTrees` is checked against a planted sublevel count too, which its previous conformance settings would have merged into a single level

* The conformance suite no longer has a way to exempt an event fitter; every discovered fitter is driven

* `PeakFinder` is un-skipped in the behavioural conformance suite and passes all four checks, matching `Basic_PeakFinder`

* New fuzz testing for every data reader against malformed input (truncated files, corrupted headers, missing sidecars) - none crash or hang uncaught

* **Breaking:** `MetaReader.load_data()` now raises `ValueError` on an out-of-bounds request instead of silently returning fewer samples than asked for

* Fixed: `Basic_PeakFinder` crashed on a zero-width sublevel in `sublevel_max_deviation`; now returns `0.0` for that case, and is covered by the behavioural conformance suite

* The settings-schema check is extracted for reuse outside pytest (`poriscope/utils/settings_schema.py::validate_settings_schema`) and gated in pre-commit

* `MetaReader` conformance lands: all 24 data plugins across all 8 `Meta*` families now run against real synthetic data

* Behavioural conformance extended to six more plugin families (filters, event finders/loaders, db loaders, writers): 22 of 24 data plugins now run against real data

* Event fitters gain behavioural conformance tests (new `conformance` marker), driven against real data rather than mocked loaders

* Fixed: `pytest tests/unit/views` failed when run on its own; the missing `sys.path` shim now lives in the root `tests/conftest.py`

* Every plugin's `get_empty_settings()` is now checked against its own declared contract; 21 violations fixed (15 missing `Value` keys, 11 `int`-vs-`float` defaults). **Breaking for programmatic callers:** an unfilled required parameter now raises `TypeError` instead of `KeyError`

* The baseline statistics behind the Raw Data tab's green baseline band are now computed in that tab's model rather than in its plot widget

* Removed an unused Gaussian function from the Raw Data view; the baseline fit never called it

* The clustering computation now lives in the clustering tab's model rather than in its plot widget, so the tab no longer carries the clustering libraries itself

* `MetaView._set_control_area` is no longer abstract: it now builds the control area for you from a new `_build_controls` hook and connects the four signals every controls panel carries, so a new tab writes three lines instead of twenty-five; a tab that lays out its own control area can still override it

* **Fixed each analysis tab initialising itself twice on startup**: every tab ran its state setup once before its widgets were built and again afterwards

* Analysis tabs no longer need to inherit `WalkthroughMixin` themselves; it comes with the base class, and a tab written against `MetaView` gets the walkthrough for free

* **Breaking:** the walkthrough widgets have moved from `poriscope.plugins.analysistabs.utils` to `poriscope.views.widgets`; a plugin that imports `WalkthroughMixin` or `WalkthroughStep` needs its import path updated

* Fixed two links in the "Adding a walkthrough" tutorial that had never resolved, and gave `WalkthroughMixin` an API reference page for them to point at

* **Breaking:** `check_column_exists` and `set_column_exists` are no longer on `MetaController` and `MetaView`; they were used only by the protein tab and now live on `ProteinController` and `ProteinView`

* **Breaking:** `MetaView._setup_canvas` no longer takes a `num_channels` argument, which it never read

* The event-index range helpers now live on the shared base for the Raw Data and Event Analysis tabs rather than on the base every tab inherits

* Progress-bar updates in one analysis tab no longer wait on a lock held by another tab

* The Raw Data and Event Analysis control panels now share a common `MetaEventTabControls` base instead of each carrying its own copy of the channel, filter and event-index handling, so a fix to one reaches both

* The Raw Data and Event Analysis tabs now share a common `MetaEventTabView` base instead of each carrying its own copy of the channel validation, commit-parameter and data-filter handling, so a fix to one reaches both

* The Raw Data and Event Analysis tabs now share a common `MetaEventTabController` base instead of each carrying its own copy of the plugin-registry and sample-rate relays, so a fix to one reaches both

* **Breaking:** removed `set_table_by_column` from the Metadata and Protein tab views and `relay_table_by_column` from their controllers - nothing in the app called them, and the table list they appended to was never created, so the call would have raised; deciding which tables a query needs to join is done by the database loader itself

* The Metadata and Protein control panels now share a common `MetaSubsetTabControls` base instead of each carrying its own copy of the same filter combobox, filter buttons and loader handling, so a fix to one reaches both

* The Metadata and Protein tabs now share a common `MetaSubsetTabView` base instead of each carrying its own copy of the same fifteen query, column, filter and experiment-selection methods, so a fix to one reaches both

* The Metadata and Protein tabs now share a common `MetaSubsetTabController` base instead of each carrying its own copy of the same seventeen relay and state methods, so a fix to one reaches both

* The two log-scaling routines behind the plots are now one, so a correction to how data is filtered or log-scaled applies everywhere it is used rather than to one of the two copies

* The five analysis-tab control panels now share a common `MetaControls` base instead of each carrying its own copy of the same widget factories and signals, so a fix to one reaches all five

* Each of the five analysis tabs now has a headless end-to-end test that drives the real tab and asserts on the file or database rows it produces, so a refactor of the tab layer cannot silently change what the app writes

* Every method the 2.0.0 refactor will move or deduplicate is now checked for test coverage by `scripts/check_refactor_coverage.py`, so a method cannot be restructured while nothing pins its behaviour

* The analysis-tab MVC boundary is now checked by `scripts/check_mvc_boundary.py` against a recorded allowlist of 113 known violations across the analysis tabs, the widgets they are built from, the app shell and the shared bases, so no new one can be added while the 2.0.0 refactor removes the existing ones

* Duplication across the five analysis-tab View, Controller and controls files is now measured by `scripts/measure_duplication.py` and held against a checked-in baseline, so a refactor that promotes a shared method has to show that it deleted the copies

* Running a single test file on its own now works: shared test helpers imported as `tests.<module>` resolved only when a higher-level conftest happened to be collected first, so `pytest <one file>` failed with `No module named 'tests'` while the same file passed in a full run

## Poriscope 1.9.0: 2026-09-04

* **Fixed a time range with no end silently finding no events**: a range like `3.0-` was accepted by the Time Range dialog but then discarded, so event finding ran over no time at all; it now means "from 3 seconds to the end of the signal", as an end of `0` always has

* **Fixed the event finder channel list failing permanently** if it could not be read the first time, which then made Find Events fail for every channel of that plugin

* Gaussian Mixtures clustering and the protein tab's shape ensemble are now seeded, so re-running either on the same data gives the same answer instead of a slightly different one each time

* **An analysis run that stops early now says why on the status panel instead of interrupting with an error dialog and a traceback** — exporting a subset that matches no events was the common way to hit it

* A failed database query or an inconsistent database still raises an error dialog during subset export, so a real problem is not mistaken for an empty result

* **Fixed subset export failing on a subset with no fitted sublevels**, which was reported as "Failed to load sublevels data" rather than exporting an empty sublevels table

* **Fixed a metadata plot or clustering run silently reusing the previous subset's rows** when the database call behind it failed, instead of reporting that the subset returned nothing

* A metadata query that matches no rows is now reported as an empty result rather than as a failed query

* **Fixed a subset filter on a sublevel column finding no events when plotting events**: filters like `filtered = 5` were applied to the events table alone, so every one of them failed as an unknown column and was reported as an empty subset — event plotting, its navigation arrows and the protein tab's plots now apply a filter through the same table joins as the metadata plots

* **Assisted filters may now contain a subquery**, which is passed through exactly as typed instead of being rewritten against the outer query's tables; this also makes `GROUP BY`/`HAVING` inside a subquery work in assisted mode

* A filter naming a column that cannot be resolved now raises an error dialog when plotting events, instead of quietly reporting that no events matched

* **Fixed a clean `pip install poriscope` failing on import**: `typing_extensions` was imported by 38 modules but declared as a dependency nowhere; the native `typing.override` replaces it everywhere, including in newly generated plugins

* Test coverage is measured again: `pytest-cov` was declared in no dependency source, so the pull-request workflow's test step failed outright instead of running

* Tests now time out after 300 seconds by default rather than hanging until the CI job's own six-hour limit

* Removed a stray `poriscope/pytest.ini` that enabled coverage against the wrong root whenever pytest was run from inside the package

* `requirements.txt` is now UTF-8 instead of UTF-16, so it reads correctly in diffs and in any tool that assumes UTF-8

* The declared `mypy` version now matches the version the pre-commit hook actually runs

* Removed two dead `pre-commit` settings: an exclude naming a directory that does not exist, and `--exit-non-zero-on-fix` on a hook that applies no fixes

* Removed 455 KB of checked-in test data that no test referenced

* Removed an unused 394-line copy of the guided-walkthrough step list; it was a stale fork of the per-tab lists the app actually shows, and nothing loaded it

* Removed `FloatRangeLineEdit.get_values` and `used_floats`, which nothing called

## Poriscope 1.8.0: 2026-09-03

* **Fixed assisted metadata filters silently returning the wrong rows**, and they now work on experiment voltage, thickness and conductivity and on `experiment_id`/`channel_id`/`event_id` in every plot and when loading event data
    * A quoted value matching a column name was rewritten as a column reference; a filter on an experiment column emitted a table the query did not join
    * A bare `id` is still rejected, since it means a different row in each table, but now with instructions naming the qualifier to use

* Removed `WaveletFilter`'s internal lock; wavelet filtering now runs in parallel across channels and instances instead of one at a time

* **Fixed three ways event writing could lose data silently**
    * Resetting one channel could delete unrelated experiments; databases written by earlier versions are repaired on the next write
    * One failed event discarded every event already written in the same run
    * A write that could not open its output file, failed to commit, or failed to reset a channel reported success anyway

* **Fixed a CUSUM fitting bug that under-detected shallow sublevels** (`CUSUM`, `ClassicCUSUM`, `IntraCUSUM`)
    * Near-threshold transitions at a 3σ step are now found roughly 9 percentage points more often; well-separated transitions are unaffected
    * **Fitting results change** — re-fitting existing data may yield more sublevels than before
    * `PeakFinder` is unchanged and still carries the defect

* **Updated Data Plugin: `PeakFinder`**
    * **BREAKING**: `Peak to Peak Distance Ratio` compared a sample count against microseconds, so it only matched its declared percentage at 1 MHz — multiply an existing value by the sample rate in MHz to keep current clustering
    * **Fitting results change**: `bitthresh` is deleted, all three classifiers now use a double-Gaussian fit, and the threshold is the analytic crossing of the two fitted components rather than the midpoint of their means
    * Both components are re-fit with each mean constrained to its own side of the histogram valley, so the higher one no longer covers the lower population's shoulder
    * A single-population dataset is now recognised as such and split above the fitted population, instead of being force-fit as two
    * The second component no longer collapses to zero width on a sharp mode with a decaying shoulder, and the fit is no longer distorted by a heavy sparse tail
    * Translocation direction is estimated from the 5th–95th percentile of the log-ECD ratio but applied to every event, so no event goes unclassified for being an outlier
    * New `bound_star` event metadata column recording which end of the construct carried the bound star through the pore, as `long end` or `short end`
    * A bound-star candidate must now be deeper than a fold, so a leading fold is no longer labelled as the star
    * New **Bound Star Classification** report section: sequence-bearing events, the starred/unstarred split, and a per-sequence breakdown
    * `filter_peaks` now picks the most prominent barcode candidate rather than the first one it finds
    * Warnings raised during classification are saved into the report instead of only being logged
    * A fitted mean that is not centred on the histogram peak it describes is now logged
    * Fixed the saved classification report being duplicated once per channel
    * Removed the unused **Visualize Classification** setting and its dead `Classify Levels` gate
    * Removed the "Outliers excluded from fit" lines, the "ECD-filtered outliers" report line and the smoothing-spline overlay from the three classification plots
    * Fields absent from an event's metadata are omitted from plot legends rather than printed as `nan`
    * Fixed an event fitted with classification disabled losing its whole figure to a `KeyError`
    * Fixed 14 silently-swallowed exceptions in the three classifiers, one of which dropped events from the folded/unfolded tally with no log line

* **Updated Data Plugin: `SQLitePeakDBLoader`**
    * `get_plot_features` now produces the same labels as `PeakFinder`, including `bound_star` and both confidence values
    * Databases written before those columns existed still plot, degrading to the fields they hold

* **New: `fit_fallbacks.md`**, documenting every fallback in `PeakFinder`'s double-Gaussian fit chain and how each classifier responds to a degraded fit

* **BREAKING: `@log`'s `debug_only` parameter is removed.** It was never read; passing it now raises `TypeError`

* **BREAKING: `DataPluginModel.get_plugin_details` is removed.** Resolve the plugin and call `get_raw_settings()` on it instead

* **BREAKING: nine dead signals are removed and the sidebar Exit button is gone.** `MetaView.save_requested` is the one a plugin author could have referred to; the window close button already ran a more complete shutdown than Exit did

* Fixed `@log`'s debug gate testing the root logger's exact level, so raising one plugin module to DEBUG produced nothing and a root level below DEBUG logged less than DEBUG did

* Fixed a `config.json` missing any key but the most recently added one killing the app before logging existed; every missing key is now restored and named in a warning

* Fixed a failed session save taking the app down, and a failed Save Session saying nothing: an autosave failure now reports on the status panel, a save to a chosen path reports as an error

* Fixed `get_raw_settings()` handing out a live reference to a plugin's internal settings, so renaming a plugin retroactively changed what session history had recorded

* Fixed three defects in plugin settings validation: a missing `Value` raised `KeyError`, a `None` value beside a `Min` raised `TypeError` instead of reporting a missing value, and a `Folder` parameter with file filters was rejected

* Fixed 11 plugin settings defaults declaring `Type: float` but giving an int (`CUSUM`, `ClassicCUSUM`, `IntraCUSUM`, `Basic_PeakFinder`), which rejected the schema on any path handing it back unchanged

* Fixed the `post-merge` hook picking whichever Python started first, which under Git Bash on Windows was the MSYS2 interpreter, so every merge silently skipped the docs, requirements and wavelet-library steps

* Fixed `pytest tests/unit` erroring intermittently with "Internal C++ object already deleted", from multi-select combo box event filters installed on the application and never removed

* Fixed CI: a third-party apt repository the project never uses could fail every workflow; all eight `apt-get update` sites now drop those sources first

* **New Dev Tooling: `scripts/new_plugin.py` generates a compliant data plugin to start from** — `python scripts/new_plugin.py MetaEventFinder MyFinder`; `--list` shows the eight families and every shipped plugin

* **New Dev Tooling: plugin settings schemas are checked for self-consistency**, by `python scripts/check_plugin_schemas.py` and on every branch push

* **New Dev Tooling: two pre-commit gates for plugin code**, since plugin discovery executes every file it finds — a `ruff` security selection over `poriscope/plugins/`, and a check that the eight data-plugin families run nothing at module level

* **New Dev Tooling: `.github/CODEOWNERS`**, so a pull request automatically requests the maintainer of the code it touches. Advisory only — it never blocks a merge

* **New Dev Tooling: the autodoc generators now delete pages for modules that no longer exist**

* Changed: the no-nested-functions convention is relaxed — a short, simple closure handed to a callback, timer or signal is now permitted

* **Docs**
    * The Scripting guide explains how to raise the log level for one plugin at a time; the Settings window keeps one application-wide level
    * `PeakFinder.py` gained a full comment and docstring pass, including where every method is called from
    * The docs render is fixed for classes whose name begins with an underscore, and for a docstring type ending in an underscore
    * The reasons for the six declined lint rules are recorded per rule rather than as one claim that only held for two of them

## Poriscope 1.7.1: 2026-08-31

* Fixed the documentation build failing on CI with several hundred `wrapper loop when unwrapping PySide6.QtGui` errors: `conf.py`'s PySide6 mock is removed, and both docs workflows now install the Qt native libraries the build needs
* Fixed a broken image on the Menus and Sessions page, from a filename case mismatch only Linux resolves strictly
* Fixed hotfix branches running no CI at all; `hotfix/*` is now in the trigger list for the branch tests and the docs render check
* Changed: `poriscope/__init__.py` logs a warning when `exposed` imports only partly, instead of passing silently

## Poriscope 1.7.0: 2026-08-31

### What's New since Poriscope 1.6:

* **New: Reset Session**, under File
    * Returns the app to a freshly-launched state without quitting: every data plugin deleted, every analysis tab closed, both histories cleared, landing page restored
    * Running workers are stopped first, an active walkthrough is cancelled, and the sidebar highlight, status panel, sidebar layout and Help window are all reset
    * The saved session files are left on disk, so Restore Session still works afterwards
    * The plugin menus are re-scanned, so a plugin added mid-session appears as it would after a relaunch

* **New: Save Session captures each tab's live subset filters, and Load Session restores them**
    * `MetadataView`/`ProteinView` filters previously vanished when a session was closed and reopened
    * New `MetaController.get_session_state()`/`restore_session_state()` hook, so any tab can persist its own state
    * Session state is now flushed on a normal app close, not only when a plugin or tab changes

* **New: the Settings window's Reset button is hooked**
    * Restores the data server location, user plugin folder and logging level to their defaults, routed so they take effect immediately
    * Touches only `config.json` — saved sessions, configured plugins and log files are left alone
    * The Settings rows now describe what each action does and what it leaves alone; "Clear Cache" empties the application log file

* **New: changing the user plugin folder takes effect immediately**, so plugins in the new folder appear in the menus without a restart

* **New Data Plugin: `ThresholdBlockageFinder`**
    * Subclass of `ClassicBlockageFinder` that imposes much tighter bounds on the start and end times flagged in the output

* **Deprecated Data Plugin: `ABF2Reader`**
    * Renamed to `TCossaLabABFReader` to reduce ambiguity with file types
    * Fixed `ABF2Header` never closing its file handle after parsing an ABF header
    * Fixed `ABF2Header`'s per-channel scale factor reading `nTelegraphEnable[0]` for every channel, corrupting current scaling on multi-channel files

* **Updated Data Plugin: `WaveletFilter`**
    * Fixed a ctypes ABI mismatch (`c_int` vs `int64_t`) on the signal-length argument that risked memory corruption on large arrays
    * Fixed `reset_channel`'s docstring being a copy-paste of `close_resources`'s

* **Updated Data Plugin: `NoFitter`**
    * Fixed an unbounded backtrack loop that could corrupt sublevel edges via negative indexing instead of rejecting the event
    * Added missing validation for `None` baseline and padding inputs
    * Fixed `_locate_sublevel_transitions`'s docstring being abstract-method boilerplate rather than describing the single baseline crossing it locates

* **Updated Data Plugin: `ClassicCUSUM`**
    * Removed an undocumented `/5` threshold divisor and a leftover debug `print()` that made this fitter far more sensitive than `CUSUM`/`IntraCUSUM`
    * Fixed `_locate_sublevel_transitions`'s docstring not mentioning this class's actual difference from `CUSUM`: Step Size is used directly in units of σ

* **Updated Data Plugins: `ClassicBlockageFinder`, `BoundedBlockageFinder`, `ThresholdBlockageFinder`**
    * Fixed a `ZeroDivisionError` on constant-signal chunks in baseline histogram calculation
    * Fixed dead code that silently skipped baseline-histogram window symmetrization
    * Fixed an ambiguous end-of-chunk check that could silently drop the remaining events in a chunk
    * Removed a dead `median_abs_deviation(data)` call whose result was discarded (`ClassicBlockageFinder`/`BoundedBlockageFinder`)
    * Replaced `_filter_events`' opening `assert` with an explicit `RuntimeError`, so a missing reader is still reported under `python -O`
    * Fixed `_filter_events`'s `channel` docstring describing it as a bool, and `_get_baseline_stats`'s promising three return values where it returns two

* **Updated Data Plugins: `CUSUM`, `IntraCUSUM`, `NoFitter`**
    * Fixed an off-by-one indexing bug that shifted every reported extreme-sublevel duration by one level
    * `NoFitter._locate_sublevel_transitions` now validates `padding_after`/`baseline_std` for `None`, as its own docstring promised
    * `IntraCUSUM._populate_event_metadata` now raises rather than computing `np.sign(baseline_mean)` with no `None` guard
    * `_populate_sublevel_metadata` now raises a clean `ValueError` when `baseline_std` is `None`, instead of failing silently later
    * Removed a dead `get_samplerate(channel)` call in `construct_fitted_event`, and fixed a stale copy-pasted "CUSUM cannot operate..." message in `NoFitter`'s error path
    * Fixed `construct_fitted_event`'s docstrings claiming `:raises RuntimeError:` when both actually return `None`
    * Fixed `CUSUM._locate_sublevel_transitions`'s docstring being abstract-method boilerplate rather than describing its log-likelihood-ratio changepoint detection

* **Updated Data Plugins: `Basic_PeakFinder`, `PeakFinder`**
    * Fixed an empty-slice bug that wrongly rejected legitimate events ending at the trace boundary
    * Fixed seven latent defects in the classifier: unguarded `Optional` values used in arithmetic, a `None` test that could never fire, and a `baseline_std` conversion that hid a legitimate `None`
    * Removed `PeakFinder.fit_2_gauss`, which had no callers and could never have run

* **Updated Data Plugin: `BesselFilter`**
    * Fixed a boundary check that allowed `Poles = 0` despite requiring a positive integer
    * Fixed `reset_channel`'s docstring being a copy-paste of `close_resources`'s

* **Updated Data Plugins: `ChimeraReader20240101`, `ChimeraReader20240501`, `ChimeraReaderVC100`, `TCossaLabABFReader`, `LegacyElementsReader`**
    * Fixed dead filename-pattern validation that never actually rejected malformed filenames
    * File-not-found and permission errors now name the file that is missing or inaccessible, instead of "at least one of the input raw data files"
    * Removed a dead `config["v_offset"]` lookup in `ChimeraReaderVC100._convert_data`, and fixed its class docstring saying "VC1100"
    * Fixed `_convert_data`/`_get_configs` docstrings claiming "data is already scaled"/"no config files needed" when each applies a conversion and parses a header

* **Updated Data Plugin: `SingleBinaryDecoder`**
    * Fixed exception handling wrapped around the wrong line, leaving real file-open errors unprotected
    * Fixed the class docstring being a leftover "Chimera VC1100" description; this reader is a generic, fully user-configured binary decoder

* **Updated Database Plugins: `SQLiteDBWriter`, `SQLiteEventWriter`, `SQLiteDBLoader`, `SQLitePeakDBLoader`, `SQLiteEventLoader`, `MetaDatabaseLoader`, `MetaDatabaseWriter`**
    * Fixed several `UnboundLocalError`-masking exception handlers that hid the real database error
    * Fixed a `finally`-block bug that swallowed real write errors and reported success instead
    * Unused `SAVEPOINT`s are now released or rolled back instead of being a no-op
    * Hardened interpolated experiment/channel/index values and escaped quotes in experiment names, so legitimate names no longer break queries
    * Fixed a crash on an empty query result and on a missing unfolded-level value
    * Fixed `SQLiteDBWriter` writing sublevel and event-data rows keyed on a `None` event id instead of rolling back
    * Fixed three regressions in `SQLitePeakDBLoader.get_plot_features`: a lost `return`, a dropped `None`-result guard and a dropped unfolded-level guard
    * CSV export can now be aborted, like every other long-running operation
    * Fixed stray logging arguments that would crash the moment the log line was emitted
    * Fixed an overly broad exception clause that made two more specific handlers unreachable
    * Fixed `SQLiteDBLoader.get_experiment_names`/`_ensure_event_counts` never closing their connections, and `_ensure_event_counts` never closing its cursor
    * Fixed `SQLiteDBLoader.get_empty_settings` being decorated twice with `@log`, double-logging every call
    * Fixed a warning log in `SQLiteDBLoader._load_event_data` missing an `f` prefix, so it logged the placeholders instead of the values
    * Fixed `MetaDatabaseLoader.load_event_data`/`query_database_directly_and_get_generator` never closing the inner generator they wrap
    * Fixed `SQLiteDBWriter._write_event` reporting every database error as "Cannot Overwrite Existing Event"; real errors now propagate with their own message
    * Fixed `MetaDatabaseWriter.write_events` never calling `_write_event(..., abort=True)` on abort, so subclasses never got the rollback and close they rely on
    * Fixed `reset_channel` opening a savepoint that was never released, and corrected both docstrings, which described closing resources for a method that deletes the channel's rows
    * Documented that `reset_channel(channel=None)` does not reset all channels, since SQL `channel_id = NULL` never matches
    * Fixed `SQLiteDBWriter.close_resources`'s docstring documenting per-channel behaviour for a method that ignores its `channel` argument
    * Fixed `SQLiteDBWriter._insert_event_data`'s docstring documenting a nonexistent `channel` parameter
    * Fixed `SQLiteEventWriter._write_data`'s docstring documenting a nonexistent `batch_size` parameter, and a stale comment claiming `executemany` batching
    * Fixed `SQLiteEventLoader._finalize_initialization` stripping `sqlite_sequence` after the table comparison had already run, so it was misreported alongside genuinely unexpected tables
    * Fixed `SQLiteEventLoader.get_valid_indices`'s docstring claiming an "all channels" mode it does not have
    * Removed `SQLiteEventLoader.get_num_events`'s unreachable `None`-row check and the dead `except ValueError` beside it

* **Updated Backend Infrastructure: `MetaEventFinder`, `MetaEventFitter`, `MetaWriter`, `MetaReader`, `MetaController`, `EventWorker`, `MetaModel`, `LogDecorator`, `BaseValidator`, `QtHandler`**
    * Fixed an unexpected exception during event processing leaving a channel permanently unable to run again
    * Fixed a falsy-zero bug that silently dropped a legitimate chunk-boundary event start
    * Fixed a `ZeroDivisionError` in fit-progress logging that could permanently wedge a channel
    * Fixed a `TypeError` raised inside any plugin generator being reported as a successful run that found nothing
    * Fixed event fitting progress never reaching 100% whenever any event was rejected
    * `force_serial_channel_operations()` is now enforced per plugin instance rather than per analysis-tab model, so one writer can no longer run two channels at once while unrelated plugins serialize for nothing
    * All five worker-driven generators share one abort contract, and an aborted generator is closed explicitly rather than left to garbage collection (`MetaModel.reset_lock` is renamed `discard_generator`)
    * Fixed finished `Worker`/`WorkerThread` objects, and everything their generator closure captured, being retained for the whole app session
    * App shutdown now waits for worker threads to finish instead of potentially destroying a still-running thread
    * Fixed the `@log` decorator silently breaking exception handling and result logging for every generator-based method in the app
    * `BaseValidator` now properly enforces its abstract validation methods
    * Added a reentrancy guard so concurrent error/warning logs no longer stack multiple modal dialogs
    * Corrected `MetaReader.load_data`/`continuous_read` documenting `start`/`length`/`total_length`/`chunk_length` as sample indices when they are times in seconds; the out-of-bounds error now reports genuine seconds
    * Fixed `MetaEventFinder.__init__` resetting `self.reader` after `apply_settings`, discarding an already-configured reader
    * Fixed `MetaEventFinder.find_events` processing every remaining range before discarding the results when aborted mid-run, instead of stopping when the abort arrived
    * Fixed `MetaEventFitter.fit_events` crashing with a `KeyError` on mismatched-length sublevel metadata; the event is now cleanly rejected instead of aborting the channel
    * Fixed `MetaWriter._rescale_data_to_adc`'s auto-scaling fallback taking its offset from `adc_max` instead of `data_max`, silently corrupting ADC-encoded values
    * Fixed `MetaWriter._validate_param_types` never calling `super()`, which skipped primitive-type validation for every `MetaWriter` subclass
    * Fixed `MetaReader.report_channel_status` always formatting the samplerate to 2 decimal places, from a dead ternary inside the f-string's format spec
    * Fixed `MetaEventFinder._find_events_single_range`'s orphan-event-end check being dead code, which discarded every event in a chunk whenever the range started mid-event
    * Fixed `MetaController`'s two relays logging the literal `"str(e)"` instead of the exception, and reporting a relay failure as "not a callable attribute" for a callback that had already resolved
    * Fixed `MetaEventFinder.report_channel_status` skipping the "Accepted ...s of data" line whenever a channel had zero rejected data
    * Fixed `MetaEventFinder.find_events` swallowing a `RuntimeError` that is only raised after the channel's accumulated events have been reset; it now propagates. Removed an unreachable `except StopIteration` beside it
    * Fixed `MetaEventFinder.get_event_indices` comparing its per-channel dicts against an empty list, so it never raised on a fresh instance; dropped its unused `index` parameter
    * Fixed `MetaEventFinder.get_single_event_data`'s docstring documenting an `IndexError` it catches internally
    * Fixed `MetaEventFitter.get_metadata_columns`/`get_sublevel_columns` sampling event 0's metadata, which crashed with `KeyError: 0` whenever event 0 was rejected; both now sample any available entry

* **Updated Plugin Management: `DataPluginController`, `DataPluginModel`, `BaseDataPlugin`**
    * Fixed `_validate_param_types` never actually validating primitive setting types, and made the fixed check skip resolved plugin references rather than reject them
    * Fixed `apply_settings` registering parent/dependent relationships under the wrong metaclass for any plugin subclassing another concrete plugin, which could crash deletion of an unrelated plugin
    * Fixed `apply_settings` catching every exception while deciding whether a settings value is a plugin, so an unexpected failure left a plugin deletable out from under a live dependent
    * Fixed a user plugin silently replacing a built-in of the same filename; the first file found now wins and the collision is reported
    * Fixed editing a plugin and dismissing the dialog with Esc or the close button crashing and leaving the plugin's parent links broken in the live model
    * Fixed `delete_plugin` never removing the deleted plugin from `plugin_history.json`, leaving deleted plugins persisted across restarts
    * Fixed `edit_plugin` unregistering a plugin from all of its parents up front and never restoring those links on any abort path
    * Fixed `update_plugin_key` silently overwriting and orphaning any plugin already registered under the destination key; it now refuses the rename
    * Fixed `edit_plugin`'s docstring documenting a nonexistent `subclass` parameter and a raise it never performs, and `update_plugin_key`/`register_plugin`/`get_temp_instance`'s docstrings naming exceptions that never happen
    * Fixed `set_settings`/`update_data_server_location` each carrying the other's docstring, and `DataPluginModel`'s class docstring calling it a "controller"

* **Updated App Shell: `MainController`, `MainModel`, `MainView`**
    * Fixed Load Session / Restore Session failing with an "already exists" error when the workspace already held state; a load now resets the session first, syncs the sidebar highlight, and names what it loaded on the status panel
    * The signal-bus dispatcher no longer retries a failed call with `func(None)`: arity is checked by reflection first, so a target runs at most once and a `TypeError` from its body is reported with a traceback
    * The dispatcher unpacks a return value from the callee's declared return type rather than by trial, which also fixes a `None` result never reaching a callback that takes trailing arguments
    * Both signal-bus handlers now share one dispatch body, so an unregistered metaclass no longer crashes out of a Qt slot and the two cannot diverge in what they log
    * Fixed seven emit sites passing a bare value where the signal declares a tuple, and made the six global-signal connections explicitly `DirectConnection`
    * Fixed the main menu's **Abort Analysis** item doing nothing whatsoever
    * Replaced a hardcoded institution-specific network path default with the user's home directory
    * A corrupted config file now regenerates defaults on startup instead of crashing the app
    * `JsonDefaultSerializer` now also handles `Enum`, `datetime`/`date` and `set`/`frozenset` values instead of only `PurePath`
    * All config file writes are wrapped in error handling instead of letting a write failure crash the app
    * `app_config` path values are normalised to `str`, so a `Path` can no longer reach a plugin's `Folder` setting and be rejected
    * Fixed a missing comma in `config_path` construction that concatenated `".."` and `"configs"` into one path segment
    * `MainController.previous_plugin_history` is always initialized to a dict, removing a fresh-install path that relied on a caught `AttributeError`
    * Fixed `send_curent_data_server`/`send_curent_user_plugin_location` being decorated `@Slot(str, str, object)` despite taking no parameters
    * Fixed `populate_available_plugins`'s `try/except` around `os.walk` being dead code, so a plugin directory that does not exist contributed zero plugins with no diagnostic
    * Fixed `clear_cache`'s docstring documenting nonexistent parameters and deletion behaviour it does not have; it truncates `app.log`
    * Removed a dead `except ValueError` in `load_session` special-casing a message that is never raised
    * Added class docstrings to `MainController`, `MainModel` and `MainView`, and method docstrings to both signal-dispatch entry points

* **Updated Frontend Base Class: `MetaView`**
    * New `plugin_state_changed` signal and abstract `notify_plugin_state_changed` hook, so any tab can notify all others when a plugin's state changes (e.g. new columns added to a database). Every subclass must now implement it, even as a no-op
    * `_set_control_area` takes a `QBoxLayout` rather than a `QLayout`, restoring the intent of its original docstring
    * Removed a stray, uncallable leftover `add(a, b)` method

* **Updated Frontend Widgets: `IntegerRangeLineEdit`, `CommaFloatRangeLineEdit`, `FloatRangeLineEdit`, `FloatRangeValidator`, `DictDialog`, `MultiSelectComboBox` (`multiselect_filter.py`)**
    * Fixed `IntegerRangeLineEdit`/`CommaFloatRangeLineEdit` mis-parsing ranges containing an extra `-`; these fields only ever hold times or event indices, so a leading `-` is now rejected outright
    * Fixed `FloatRangeLineEdit` crashing with an `AttributeError` on any invalid or empty input, because it never defined a `logger`
    * Fixed `DictDialog`'s hidden Input File/Output File/Folder "has a value" checkbox always starting unchecked, which disabled OK on an already-configured plugin until the file picker was re-run
    * Fixed `FloatRangeValidator` inflating a bare-integer end value (`"2"` → `"20"`) before the ordering check, so an inverted integer range like `"10-2"` was accepted and stored backwards
    * Fixed `MultiSelectComboBox.addItems` (filter variant) never refreshing the Select All button text or summary line-edit after repopulating
    * Fixed the filter variant's outside-click handler falling through to `super().eventFilter(...)`, so the dismiss-click also reached the widget underneath
    * Both multi-select combo boxes no longer accept an `addItem` `userData` argument they silently threw away
    * Five widget classes no longer store state under a name that shadows an inherited Qt method (`NumericLineEdit.validator`, `DictDialog`/`DropdownDialog`/`TimeWidget.result`, `BaseSubsetFilterDialog.layout`)
    * Removed `_edit_button_clicked`/`_delete_button_clicked`, two dead methods superseded by the `edit_filter`/`delete_filter` callback chain
    * Removed the unused `comma_delimited_float_range_edit.py` module, `FloatRangeLineEdit.get_values_with_type_info`, `ClusteringSettingsDialog.update_unit_label`/`reset_top_inputs`, and two stray debug `print()` calls

* **Updated Frontend Controls: `RawDataControls`, `EventAnalysisControls`, `ClusteringControls`, `MetadataControls`, `ProteinControls`**
    * Fixed `MetadataControls`/`ProteinControls` crashing when the bins field ended in a trailing comma
    * Fixed an unmapped `button_type` raising `AttributeError` in three of the five files instead of being ignored, as it already was in the other two
    * Removed the duplicated, uncallable `get_nested_value`/`get_plugin_data` helpers from all five files, along with their two dedicated test classes

* **Updated Frontend Infrastructure: Walkthrough**
    * Fixed the transparent "Analysis" menu highlight overlay leaking whenever a milestone dialog was dismissed manually instead of by navigating on
    * Fixed the auto-advance polling loop rescheduling itself after the dialog was manually dismissed, risking a late call into the completion handler
    * Fixed an abandoned walkthrough polling at 5 Hz for the rest of the process's life, each callback closing over a widget that might already be gone
    * Dialog repositioning uses a real `on_move` hook on `StepDialog` instead of monkey-patching `moveEvent`, which had suppressed `QDialog`'s own handler
    * `start_walkthrough` returns its fallback dialog directly instead of constructing one guaranteed to raise

* **Updated Frontend Plugins: `MetadataView` and `ProteinView`**
    * Event navigation is now filter-aware, driven by a cached event_id list and bisect search instead of a DB query per click
    * The old range field is replaced by **Event ID** (snaps to the nearest filtered event at or after the requested id) and **# Events** (how many filtered events to show from there)
    * Forward/backward arrows step through the filtered set with wrap-around, so the subplot count is predictable and no step lands on an empty range
    * The display panel shows the filtered total, the first and last event ids, and the active filter name and subset label
    * Fixed the scoped channel identifier being the selection tree's display string rather than an `int`, so cache-staleness comparisons silently never matched
    * Selecting no database loader no longer logs an error and raises a dialog
    * `_load_filter` no longer raises into its own `except` handler, so a genuine Qt failure below the parse step surfaces; both views now report a duplicate filter name identically and on the message panel

* **Updated Frontend Plugin: `MetadataView`**
    * Fixed Categorical Histogram, Scatterplot and Raw/Filtered Event Overlay failing to render after "Plot Events" + "Update Plot", from a stale `self.axes` reference the staleness check missed
    * Fixed a silent crash in `_export_csv_subset` when the Export Settings dialog was cancelled
    * Now refreshes its available column list when another tab commits new columns to the selected database
    * Fixed the tab re-plotting datasets it had already drawn, because the overlay guard compared a display string against an `int` channel id
    * Fixed a no-op Update Plot click still recording an Undo step that re-rendered an identical figure
    * Fixed plot features arriving with a short or absent label list silently dropping lines and markers from the plot
    * Fixed a `ZeroDivisionError` when building an event overlay from events that all have the same length
    * Fixed a crash formatting an axis label for a column with no defined unit
    * Fixed an unhandled plot type leaving plotting data unbound instead of raising a clear error
    * Fixed a typo that left stale event markers on the plot after a failed feature lookup
    * Removed a dead, exact-duplicate code block in all-points-histogram construction
    * Fixed the DB Loader edit/delete buttons staying enabled with no database loaded, from a placeholder text mismatch
    * Fixed `MetadataControls` computing bins-field validity but never using it to enable **Update Plot**, and requiring whole numbers even when "Sizes" was checked

* **Updated Frontend Plugin: `ProteinView`**
    * Added a **RAW** checkbox to event plots, matching `MetadataView`: raw traces before fitting, and alongside fitted results once fitting is complete
    * New **Report All** button in Ensemble mode, showing the double-Gaussian fit parameters and binning configuration plus median ± std summaries of Prolate and Oblate V, a, b and m (replaces Commit All; display-only, since Ensemble mode has no per-event id)
    * Individual and Ensemble modes now use fully independent canvases, so switching modes shows that mode's last plot and neither overwrites the other
    * Reset is now scoped to the currently selected mode, and the display panel confirms which mode's fit was cleared
    * Fixed Update Plot in one mode wiping out a valid fit stored in the other, which produced "No ensemble fit available to report" after a successful fit
    * Removed the Undo and Reset buttons from the Protein Tab, and updated the walkthrough instructions
    * Added Freedman-Diaconis auto-binning for per-event histograms
    * Fixed `hist_min`/`hist_max` persisting across "Plot Histogram" calls and only ever expanding, so bin edges depended on plotting order rather than the event
    * Fixed Commit silently crashing every time from a broken plugin-list refresh chain (the write itself succeeded, so it went unnoticed)
    * Committing now notifies other open tabs, so new columns appear immediately in any tab displaying that database
    * Fixed Commit Individual with no fit computed raising an `AttributeError` swallowed by the Qt event loop; it now reports on the display panel
    * Fixed `_commit_fits` not aborting on Cancel in the Confirm Overwrite dialog, and added the missing `ProteinController.check_column_exists` without which that dialog could never appear
    * Fixed some validation passing an extra positional argument to `logger.warning`, crashing before the warning was shown
    * Fixed a blank **N** field in Ensemble mode raising `ValueError` instead of falling back to a default, and the frontend default of 1000 disagreeing with the backend's 100
    * Fixed zero-baseline divisions propagating NaN/Inf into histograms and fits
    * Added a hard cap to a previously unbounded Monte Carlo sampling loop that could block the UI indefinitely
    * Fixed a plugin-list refresh crashing on `.emit()` against a non-`Signal` method
    * Extracted `_update_distribution_ensemble`'s ~105-line fit and sampling block into `_fit_and_plot_ensemble_geometry`, called once after the loop rather than relying on careful indentation
    * Fixed `is_placeholder_item` checking for `"No Database"` instead of `"No Event Database"`, leaving the DB Loader buttons enabled with nothing selected
    * Fixed the `ProteinView` class docstring still being the unfilled `"Subclass of MetaView for TBD"` placeholder, and `ProteinModel`'s being a copy of `MetadataModel`'s

* **Updated Frontend Plugin: `ClusteringView`**
    * Fixed Commit silently crashing every time from a broken plugin-list refresh chain (the write itself succeeded, so it went unnoticed)
    * Committing now notifies other open tabs, so new columns appear immediately in any tab displaying that database
    * Fixed Cancel on the cluster-overwrite confirmation dialog not actually cancelling the commit
    * Fixed an unrecognized clustering method crashing with an unbound-variable error instead of a clear message
    * Fixed a `ZeroDivisionError` in baseline stats on a flat or constant data chunk
    * Fixed Gaussian Mixture clustering fitting on data that still included the `id` column, whose unnormalized magnitude could dominate the fit
    * Fixed `self.units` serving as both a column-to-unit map and a positional list, so opening the settings dialog after a plot passed a list to code expecting a dict
    * Fixed the plotted-column list being derived from the dataframe's own columns, which carry trailing `id`/`cluster_label`/`cluster_confidence` entries
    * Fixed `ClusteringSettingsDialog.remove_column_item` never refreshing the Apply-button state, leaving Apply stuck disabled after deleting the offending row
    * Added a missing docstring to `ClusteringController.display_write_status`

* **Updated Frontend Plugin: `RawDataView`**
    * Fixed a `ZeroDivisionError` in baseline stats on a flat or constant chunk; it now warns and skips that channel's overlay instead of crashing the plot
    * Fixed power spectral density calculation crashing or producing NaNs on very short channels
    * Fixed committing events doing nothing at all when the channel argument was a single value rather than a list
    * Fixed `RawDataModel.integrate_noise` crashing "Update PSD" with an `IndexError` when a short window made `welch()` return a single frequency bin
    * Fixed PSD calculation labelling a surviving channel's PSD under the wrong channel name whenever an earlier channel was skipped
    * Fixed a log message missing an `f` prefix, so the intended values were never interpolated (same bug also fixed in `EventAnalysisView`)
    * Fixed `_get_baseline_stats`'s docstring documenting a two-value return, missing the local amplitude that is the first of three
    * Fixed `RawDataController.update_channels` being decorated `@Slot(dict)` despite always receiving a `List[int]`
    * Added missing docstrings to `RawDataController.update_available_plugins`/`update_plot_data`

* **Updated Frontend Plugin: `EventAnalysisView`**
    * Fixed a crash when zero channels were selected while shifting or plotting events
    * Fixed a failed event load silently reusing stale data from a previous event
    * Fixed a typo that left stale event markers on the plot after a failed feature lookup
    * Fixed a crash on a fitted event whose features carry no labels
    * Fixed the fitter combo box inserting `"No EventFitter"` while everything else checked for `"No Event Fitter"`, so Fit Events could silently target a nonexistent plugin key
    * Fixed `_start_eventfitter` re-raising a filter-loading failure instead of proceeding without one, as `_handle_plot_events` already did
    * Fixed answering "No" to one channel's "already fitted" prompt cancelling fitting for every remaining channel in the batch
    * Fixed `_update_event_plot` never referencing its `use_raw` parameter, so the raw-trace toggle worked only by accident
    * Fixed `_extract_plot_event_parameters`'s docstring documenting a 4-tuple return, omitting `loader` from the real 5-tuple
    * Fixed `EventAnalysisController.update_channels` being decorated `@Slot(dict)` despite always receiving a `List[int]`, and added a missing docstring to `update_available_plugins`

* **Updated Frontend Component: `MainView`**
    * Fixed sidebar highlighting not updating when a tab was opened from the menu bar or the "Add" dropdown, and not highlighting the dedicated Raw Data / Event Analysis / Metadata buttons
    * Fixed the "Add" dropdown reopening immediately after selecting an item, from a duplicate signal connection
    * Fixed the "All Analysis Tabs" dropdown always opening at the window's top-left corner instead of near the clicked button
    * Fixed menu bar action icons silently failing to render from an incorrect resource path
    * Fixed `add_page` leaking an orphaned wrapper `QWidget` every time a page name was reused, e.g. every time Settings was opened
    * Menu actions are now parented to the menu that shows them, so a rebuild destroys them instead of leaving a full menu bar's worth alive on the window
    * Removed `display_data`/`on_file_loaded`, two dead methods with no callers whose target no longer exists
    * Removed the abandoned language and theme sidebar controls — six methods setting buttons that are never constructed — along with `handleUser`/`switchUser`
    * Fixed `IconTextMenuWidget.menu_button_clicked` scheduling the same `QTimer.singleShot` twice

* **Updated Frontend Component: `Settings`**
    * The Settings window follows OS light/dark mode automatically and updates live if the OS theme changes, with no restart
    * Fixed combobox popups rendering with a stray focus outline, a disappearing hover highlight and a double-border artifact
    * The About tab's version is pulled from `poriscope.constants.__VERSION__` rather than a hardcoded string
    * Fixed a potential `AttributeError` if a folder-picker button was clicked before the data server or user plugin location had been set
    * Fixed the Logging Level combobox always opening at "None" regardless of the configured level, since nothing pulled the persisted value back into the widget

* **Updated Utility: `get_icon` (`poriscope.configs.utils`)**
    * Icons now recolor automatically for light/dark mode instead of requiring separate black and white files
    * New `get_themed_icon_path` helper for cases (like custom stylesheet arrows) that need a real file path
    * Removed unused legacy icon assets and the broken, unused Qt `.qrc` resource system (`resources_rc.py`)
    * Standardized edit/add icons across control panels

### Breaking Changes:

* `QtHandler` no longer raises a dialog for every `WARNING` and no longer inherits the root logger's level; its constructor takes a `level`, defaulting to `ERROR`. A burst of errors is queued and shown in turn rather than losing all but the first, and the dialog carries the bare message instead of a formatted log line
* `BaseDataPlugin.lock` is a per-instance `RLock`, not one class attribute shared by every data plugin in the process. Class-level access breaks; `self.lock` now means "my lock"
* `MetaReader.get_channel_length` takes a required channel and returns an `int`; the no-argument whole-dict form is gone
* `MainModel.get_plugin_classes` takes a required metaclass; `MainModel.get_available_plugins` takes no argument and always returns the full mapping
* `DictDialog.get_result()` always returns `(settings, name)`, with deletion reported by a new `delete_requested()` instead of a `"delete"` sentinel; `DataPluginView.get_user_settings` returns `(settings, name, delete_requested)`
* `DataPluginController.__init__` takes a required `history_lookup` callable; its `get_settings_from_history` signal and `set_settings` are removed, and `MainController.get_settings_from_history` is now `_lookup_historical_settings` and returns a value
* `MainView.kill_all_workers` is replaced by `abort_all_analysis`, handled for every open tab rather than hard-coded to one
* `MetaView` gains an abstract `notify_plugin_state_changed`, which every subclass must implement
* `requires-python` is raised to `>=3.12.10`, blocking installation on 3.12.0–3.12.9
* The `fast` and `slow` pytest markers are removed; `-m fast` and `-m slow` now select nothing

### New Dev Tooling:

* **`pydoclint`**, a blocking pre-commit/CI check that a docstring's documented parameters, return type and raised exceptions match the real function. Run it with `pydoclint --baseline=.pydoclint-baseline.txt poriscope`; see `[tool.pydoclint]` in `pyproject.toml`. The ~1,090-violation backlog it was adopted with is fully cleared and the baseline file is now empty
* **Every function under `poriscope/` is annotated**, with no exclusions, and `mypy`'s `disallow_untyped_defs`, `check_untyped_defs` and `strict_equality` are on, so a new unannotated `def` fails the hook. `mypy.ini` pins `python_version = 3.12`, and the hook is scoped to `poriscope/` so it no longer checks `tests/`
* **The `@log` decorator no longer erases the signatures it wraps** (935 methods across 71 files), so call sites into plugin and controller methods are type-checked for the first time; turning it on surfaced 84 real call-site errors
* **The Sphinx documentation render is a CI gate.** New `docs-check.yml` regenerates the autodoc `.rst` files and runs `sphinx-build -W --keep-going` on every pull request targeting `main`, `develop` or `release/*`; the deploy workflow and the local `post-merge` hook use the same flags. The 18 pre-existing warnings that blocked it are fixed
* **New end-to-end test suite** covering the RawData, EventAnalysis, Metadata, Clustering and Protein tabs, plus a shared `tests/synthetic_data` package, so no test depends on a checked-in recording or database. `tests/data/` is removed
* **`setup_hooks.py` sets `gitflow.prefix.versiontag` to `v`**, so plain `git flow release finish <version>` creates the `v<version>` tag `release.yml` triggers on. Git config is per-clone, so a fresh checkout must run the script before cutting a release
* **`pytest --marker-stats`** prints per-marker test counts and mean durations. `e2e` and `integration` are applied by path, `--strict-markers` is on, and all four workflows run plain `pytest` with no marker filter
* The view test suite is roughly 7.6x faster: widgets are actually deleted at teardown rather than only hidden, the GC sweep is generation-limited, and the protein and event-analysis tests build mocked views instead of real Qt widgets
* Tests can no longer reach the developer's real app-data directory, via an autouse fixture in a new top-level `tests/conftest.py`
* Fixed the test suite segfaulting when `tests/unit/views` ran before `tests/unit/plugins`, from widgets torn down with `QWidget.destroy()` leaving posted events behind
* Fixed four e2e tests waiting on a file existing before asserting on its contents, and a leaked `patch.object` that turned one failure into eighteen
* Fixed the `post-merge` git hook failing silently on Windows: a POSIX-shell shim now selects a working interpreter by executing each candidate, and `.gitattributes` pins it to LF
* `ruff`'s `B006` and `B020` checks are enabled, and the `Programming Language :: Python :: 3.12` classifier is declared to PyPI

### General Fixes and Improvements:

* Fixed 19 routine states being logged at ERROR, and so raising a modal dialog each — including one per keystroke in a range box and one per channel with no data. Empty-state guards now report on the message panel
* Fixed aborting an operation giving no feedback while failing to abort raised a dialog containing a repr of the whole worker dictionary; every branch now reports on the message panel
* Fixed placeholder combobox text (`"No Reader"`, `"No Eventfinder"`, `"No Event Database"`, etc.) reaching `global_signal.emit(...)` as a real plugin key, flooding startup and session-restore with failed lookups
* Exception chaining restored across 23 `raise` sites, so the original error is preserved rather than discarded
* Silently swallowed exceptions outside the owner-held fitter plugins reduced to zero; four remaining cosmetic handlers now log at debug with a traceback
* Cleared 17 unused loop-control variables, and hardened three `zip` sites whose length invariant was implicit
* Fixed `"id"` never actually being excluded from clustering normalization, from two dead lines whose result was discarded
* Replaced deprecated `set_constrained_layout(True)` with `set_layout_engine('constrained')` in `ClusteringView` and `EventAnalysisView`
* All function-local ("lazy") imports removed; the only `TYPE_CHECKING` blocks left are the two forced by a real import cycle
* Two shared mutable argument defaults fixed, and `time_widget`'s `FloatRangeValidator` renamed `TimeRangeValidator` so it no longer collides with the unrelated validator of the same name
* Every dataset link in the documentation now points at the current FRDR record, the Python download link is no longer pinned to a superseded patch release, and the installation pages state `>=3.12.10` consistently
* New contributor documentation: a Quality Control page describing every automated gate with a pre-PR checklist, and a `serial_channel_operations` page covering what `force_serial_channel_operations()` promises and who applies the decorator
* Fixed `MetaReader.load_data`/`continuous_read` reassigning their own seconds-valued parameters to sample counts mid-body, which is how their docstrings came to be wrong
* Corrected 80 docstrings whose documented parameter types disagreed with the signature, and the docs workflow's own comments, which claimed it published from `develop` while triggering on `main`
* Updated tests whose expectations had gone stale against already-landed fixes (`test_main_controller.py`, `test_classic_cusum.py`, `test_no_fitter.py`, `test_meta_event_finder.py`, `test_peak_finder.py`), and removed a dead, shadowed `main_model` fixture

## Poriscope 1.6.1: 2026-06-04

* **Bug hotfix
    * Fixed plotting bugs with `Peakfinder` plugin families

## Poriscope 1.6: 2026-06-04

### What's New since Poriscope 1.5:
    
* **PyPi integration**
    * Poriscope is now available on PyPi and can be installed with `pip install poriscope`
    
* **Updated Data Plugin Base Class: `MetaDatabaseLoader`**
    * Replaced N×M `COUNT(*)` query loop in `report_channel_status` with a `event_counts` summary table, making DB loading and experiment/channel count reporting ~10x faster.  
    * The `event_counts` summary table is maintained automatically via SQLite triggers in case of manual edits (event removal)
    * Backwards compatible — existing databases are upgraded automatically on first load
    * Added template for `get_plot_features()` function that can be implemented by subclasses that want to visualize data printed by specific `MetaEventFitter` subclasses
    
* **Updated Data Plugin Base Class: `CUSUM`**
    * Fixed numerical bug that was causing underestimates of sublevel transition probabilities
    * Fixed numerical bug that was causing shallow steps to be accepted when they should not have been
    * Reverted threshold loop to exact port of original C code implementation
    * Added new parameter Sensitivity to allow greater fine-tuning of step detection

* **Updated Data Plugin Base Class: `Peakfinder`**
    * Redefined sublevels by regions relative to peak flanks
    * Added new metadata to calculate peak mean blockage
    * Added settings for peak filtering fine-tuning
    * Fixed peak numbering relative to new sublevel definition
    * Fixed current direction dependance problem for peakfinding function
    
* **Updated Frontend Plugin: `MetadataView`**
    * Added **RAW** checkbox to the Plot Events section — raw data is always shown before fitting; once fitting is complete, checking RAW includes raw traces alongside the fitted results
    * Full SQL will always be printed after filter creation/editing, regardless of validity
    * Added the loader to both the legend label and the duplicate-check key so plots from different loaders are treated and displayed as separate datasets allowing for different loaders with the same experiment name to be overlayed.
    * Added **RAW** checkbox to the Plot Events section — when checked, raw data traces are included alongside filtered and fitted traces in event plots
    * New plot type: Categorical Histogram that plots bar charts of data counts for unique values of the specified database column
    * Fixed bug with baseline fitting that caused off centered fit when baseline drift was present
    * Two event filter modes: **Assisted SQL** (WHERE clause only, Poriscope builds the query) and **Raw SQL** (complete SELECT statement, executed directly). Raw mode enables aggregations, computed columns, and subqueries not possible in assisted mode. See *Filtering and Querying* in the documentation. `ProteinView` brought to parity with MetadataView. 

* **Updated Frontend Plugin: `RawDataView`**
    * Fixed bug causing float drift in trace navigation 

* **Updated Frontend Plugin: `ClusteringView`**
    * Increased size of color palette cycle when plotting large numbers of clusters
    * Increased markers size when plotting

* **Documentation**
    * Fixed missing method documentation in all `MetaView` subclasses caused by unresolved PySide6 imports at Sphinx build time
    
* **New Frontend Plugins: `ProteinView`/`ProteinController`/`ProteinModel`**	 
    * Allows fitting, visualization, and postprocessing of the Mayer model to protein volume and shape factors
    
* **New Data Plugin: `ClassicCUSUM`**	 
    * Reverts Step Size to being a multiple of the local baseline standard deviation instead of an absolute number
    * Ported bug fixes from base CUSUM class
    
* **New Data Plugin: `ClassicBlockageFinder`**	 
    * Fixed bug with baseline fitting that caused off centered fit when baseline drift was present
    
* **New Data Plugin: `BoundedBlockageFinder`**	 
    * Fixed bug with baseline fitting that caused off centered fit when baseline drift was present
    
* **New Data plugin: `SQLitePeakDBLoader`**
    * Subclasses SQLiteDBLoader to add specific plotting features used by the `PeakFinder` plugin - only usable on databases created by `PeakFinder`
    
* **New Data Plugin: `Basic_Peakfinder`**	 
    * Stable release of basic and minimal peak finding features

### General Fixes and Improvements:
* Fixed bug with baseline calculation that was causing inaccurate baseline whenever drift was present
* Fixed crash when resetting or updating heatmaps in the Metadata tab
* Bin and size changes now trigger correct overlay replotting when clicking "Update Plot"
* Cross-table filtering is now supported for events plot filtered by sublevels column, and sublevels plot filtered by events column.
* Fixed float-to-index rounding drift in PeakFinder and NanoTrees 
* Added strict runtime length check in MetaEventFitter so any mismatch now fails immediately and loudly instead of silently propagating to plotting or downstream logic
* Fixed plugins' settings not being able to be edited 
* Single shared legend from all axes in the EventAnalysis Tab to prevent overlapping and sublplots shifting
* Fixed "Update Plot" not working after "Plot Events" due to stale figure state and tracking variables not being reset
* Select all items by default in MultiSelectComboBox
* Auto-select newly added filter to match reader's, loader's and writer's combobox population behavior

Disclaimer: As of version 1.6.0, Poriscope has experimental Linux support and is primarily tested through an Ubuntu virtual machine environment.

## Poriscope 1.5: 2025-12-08

### What's New since Poriscope 1.4:
* **linting and unit tests**
    * repository now runs sanity checks before allowing commits
    
* **workflow script**
    * Example script showing implementation of a "one-click" poriscope workflow added to the repository
    
* **pip integration**
    * Poriscope now includes setup.py and can be installed as a pip package
    
* **Tutorial Updates**
    * Tutorial now includes `ClusteringView`
    * Users can now add a walkthrough to their own plugin by inheriting from WalkthroughMixin.
        * For detailed instructions, see the documentation: User Manuals/Next Steps/Adding a Walkthrough.
        
* **Documentation Updates**
    * Data plugin creation tutorial and documentation added
    * scripting workflow example tutorial added
    * General improvements to cross-referencing within the documentation
    * **NOTE** to build and view docs, run `python scripts/hooks/post-merge-run_autodoc_pipeline.py` in  the top level repository folder

* **Updated Data Plugin Base Class: `MetaDatabaseWriter`**
    * All generators can now be aborted early to force axhaustion by sending in a boolean flag

* **Updated Data Plugin Base Class: `MetaEventWriter`**
    * All generators can now be aborted early to force axhaustion by sending in a boolean flag
    
* **Updated Data Plugin Base Class: `MetaEventFinder`**
    * Now allows finding of events in a series of disconnected chunks with a single progressbar over all chunks
    * All generators can now be aborted early to force axhaustion by sending in a boolean flag
    
* **Updated Data Plugin Base Class: `MetaEventFitter`**
    * Enforce that sublevel_duration exist in the database and force crash during event fitting if it does not
    * All generators can now be aborted early to force axhaustion by sending in a boolean flag
    
* **DEPRECATED Data Plugin: `BinaryEventLoader`**
    * Per last release notes, `BinaryEventLoader` has been deprecated and is no longer available
    
* **Updated Data Plugin Base Class: `MetaDatabaseLoader`**
    * Updated load_event_data to also return padding before and padding after. 
    * Updated all metadata and data loading functions to take optional channel and experiment lists as arguments to unify SQL query construction logic
    * Columns in the experiments table are now included in the query builder
    * **DEPRECATED**: export sqlite subsets no longer works, in favor of persistent subset filters

* **Updated Frontend Plugins: `RawDataView`, `EventAnalysisView`,  `ClusteringView`, `MetadataView`**
    * Control panels now have a “delete” button next to the edit button in each view. This allows users to delete the currently selected plugina s long as it does not have dependent plugins
    * Change all long-running tasks that generate progress bars to allow cancellation regardless of serial or parallel status by moving abort functions to the data plugins
    * Plugin names can now be edited
    
* **Updated Frontend Plugin: `MetadataView`**
    * Complete overhaul of control panel
    * Subset and sql filters are now persistent objects that can be saved and reloaded
    * **DEPRECATED**: export sqlite subsets no longer works, in favor of persistent subset filters
    * Subsets can now be automatically segregated by experiment and channel id independent of other filters applied using the Scope button
    * Events can now be plotted directly in the view
    * You can now set bins either by size or counts
    * When plotting multiple overlaid histograms, bins will adjust to match across subsets
    * Enforces single exp/channel selection for event plots, which allows event_id to be used instead of global_id to identify events for plotting
    
* **Updated Frontend Plugin: `RawDataView`**
    * Added the option to calculate and plot the baseline stats on the raw data panel
    
* **Updated Frontend Plugin: `EventAnalysisView`**
    * Event plot line and  point elements now cycle through the matplotlib color cycle
    
* **Updated class structures**
    * Miscellaneous changes to data plugin base classes to explicitly include all required abstract methods in metaclasses for ease of subclass creation
    
* **Updated repository management**
    * Now includes pre-commit checks for code quality, linting, and proper type hinting
    * Post-merge pipeline updated to account for docs updates

### General Fixes and Improvements:
* **Click outside the pop-up or the x button in the selection menus (compatible with MacOs and Linux)**
* **Append SQL-like filters instead of overriding when loading a new .json file in the Metadata tab**

## Poriscope 1.4: 2025-06-09

### What's New since Poriscope 1.3:


* **Updated Data Plugins: `SQLiteEventLoader` and `SQLiteDBLoader`**
    * Now sanity checks database schema for expected tables and rejects initialization if it is non conformant
* **Updated Data Plugin: `IntraCUSUM`**
    * Now inherits from `CUSUM` instead of `MetaEventFitter` to allow common functionality to be preserved
* **Updated Data Plugin: `BoundedBlockageFinder`**
    * Now inherits from `ClassicBlockageFinder` instead of `MetaEventFinder` to allow common functionality to be preserved
* **Updated Data Plugins: `SQLiteEventWriter` and `SQLiteDBWriter`**
    * Implemented "close_resources".
* **Updated Base Classes: `MetaEventFinder`, `MetaEventFitter`, `MetaWriter`**
    * Allows base class settings key to have child plugin base class anywhere in the inheritance chain to allow for serial subclassing of data plugins
* **Updated Base Classes: `MetaEventFinder`**:
	* Allows for segments of the file to be analyzed as specified by comme-delimited list
* **Updated Base Class: `MetaDatabaseLoader`**
    * Metadata requests now return the id column to allow cross-referencing after querying
    * Now allows new columns to be written to existing database tables while preserving cross-table relationships
    * Now corrects for redundant column requests when attempting to plot event_id and will remove redundant columns from returned data
	 
* **Updated Frontend Plugins: `RawDataView` and `EventAnalysisView`**	 
    * Next and previous arrow buttons added to frontend to simplify flipping through data, events, and fits
* **Updated Frontend Plugin: `MetadataView`**	 
    * Now allows plotting of event_id and gracefully handles missing units in metadata databases
	* Now allows independent setting of x and y bin counts using a comma-delimited list. Extra entries beyond those needed are ignored. 
* **Updated Frontend Plugin: `EventAnalysisView`**	 
    * Now allows plotting of vertical and horizontal lines and points by coordinate on top of fitted events

* **Updated Frontend Base Classes: `MetaView`**	 
    * added a signal to cause plugin instantiation from analysis tabs
	 
* **New Frontend Plugins: `ClusteringView`/`ClusteringController`/`ClusteringModel`**	 
    * Allows HDBscan and Gaussian Mixtures clustering of arbitrary subsets of data, merging of clusters, and addition of cluster columns to sql databases of event metadata
	 
* **Logging Behavior Update**
    * logging at level "info" will now not print entry and exit points, only non-critical but potentially user-useful information to the console without blocking. Other logging level behaviors unchanged. 

* **New Feature: Sphinx Documentation**
    * Full plugin and base class documentation is now included using Sphinx.
    * Users can explore architecture, plugin structure, and extension workflows directly from the docs.
    * Plugin development guide 1.0 included. 

* **New Feature: Automation Scripts and Setup Hooks**
    * Scripts are now included to auto-generate Sphinx documentation.
    * Setup hooks allow backend commands to be automatically run during initial project configuration or environment setup.
 
* **Updated Frontend Plugins: `RawDataView`, `EventAnalysisView`,  `ClusteringView`, `MetadataView`**
    * Control panels now have a “+” button next to the edit button in each view. This allows users to instantiate the corresponding  metaclass plugin directly, without needing to access the top bar menu.
	* Frontend plugins now have tutorials that walk you through the use cases
	
* **Updated Frontend Plugin: `RawDataView`**
    * Control panel now has backward and forward arrows for "Plot Events".
    * Removed "Include" and "Exclude" events buttons from the control panel.

* **Updated Frontend Plugin: `MetadataView`**
    * Removed "New Axis" button.
    * Changed "Overlay" to "Update Plot".

* **Updated Event Finding Time Limits: `RawDataView`**
    * Takes comma delimited int/float ranges
    * Finds events for each of the ranges
    * Goes from any intermediate value to zero by doing: x-0

 **Tutorial: `MainView`,`RawDataView`, `EventAnalysisView`, `MetadataView`**
    * An interactive tutorial can be triggered from the Help menu (Help->Tutorial)
    * The tutorial walks you through all the components of the Tabs listed above
    * It can be triggered at any point or closed.

* **Main app updates**
	* App now defines a user plugin folder that will be searched for valid plugins at runtime and can be changed in settings
	* App will recognize imports relative to either the `app` folder, or the `[[user_plugin]]` folder, where `[[user_plugin]]` must be replaced with whatever the actual name of your user plugin folder is.

 **Tutorial: `ClusteringView`**
    * The tutorial has been extended to include ClusteringView.


## Poriscope 1.3: Released 2025-05-21

### What's New since Poriscope 1.2:

* **New Data Plugin: `MetaEventWriter` subclass `SQLEventWriter`**
    * Stores raw data in SQLite database format.
* **New Data Plugin: `MetaEventLoader` subclass `SQLEventLoader`**
    * Loads data from `SQLEventWriter` databases
* **New Data Plugin: `MetaEventFitter` subclass `PeakFinder`**
    * Allows extraction of peaks that do not reach steady states.
	* new function get_plot_features that allows x and y values to be highlighted as features of interest for plotting
* **New Data Plugin: `MetaEventFitter` subclass `IntraCUSUM`**
    * Allows for counting threshold crossings if necessary.
* **New Data Plugin: `MetaEventFinder` subclass `BoundedBlockageFinder`**
    * Allows users to specify valid baseline limits for event finding.
* **Updated Data Plugin: `MetaEventFitter` subclass `NanoTrees`**
    * Now is able to run safely in multiple threads

* **New Frontend Plugin: `Clustering` tab**
    * Has been added.
* **Updated Frontend Plugin: `MetadataView`**
    * Allows export of subsets into human-readable CSV format.
* **Updated Frontend Plugin: `RawDataView`**
    * Allows specification of time limits for event finding.
* **Updated Frontend Plugin: `EventAnalysisView`**
    * Now allows plotting of horizontal and vertical lines on plots to highlight features of interest

### Deprecated:

* `BinaryEventWriter` has been removed to enforce consistent file formats internally.

### Notice of Future Deprecation:

* `BinaryEventLoader` will be deprecated in a future release. Please convert any datasets written with BinaryEventWriter to the new SQLEventWriter before the next release. 

### Optimization:

* `SQLEventWriter` has been heavily optimized for speed.
* `SQLDBWriter` has been heavily optimized for speed.

### Metaclass Update:

* **`MetaEventLoader` and `MetaEventWriter`**
    * Have had updates to their interface to change the structure of databases.
* **`MetaDatabaseWriter`**
    * Now enforces inclusion of raw data, filtered data, and fitted data in the database.
    * Allows writing from plugins with different metadata to the same common database.
    * *Note: Missing values will be null.*
* **All Data Metaclasses**
    * Can now enforce serial channel operations through a flag if necessary.
    * Metaclasses that create generators that are operated on by the GUI (these being `MetaEventFinder`, `MetaEventFitter`, and `MetaEventWriter`) now allow internal early abort of the generator through provision of a flag to the generator.

* **All Frontend Metaclasses** 
    * Now set an abort Boolean and allow abort and cleanup to be handled internal to the plugin, which fixes a bug in which threads were not being properly canceled when serial operations were in force. 
    * Plugin editor no longer allows changing source plugins or names for the sake of internal state consistency

### General Fixes and Improvements:

* Plugin menu position adjusted for consistency.
* Bugs relating to canceling plugin initialization have been fixed.
* Plugins that use database connections have been updated to enforce transient database connections to avoid issues with open database handles between threads.
* Miscellaneous frontend cleanup.
* Updates to reports generated when plugins are loaded and/or complete their analysis.
