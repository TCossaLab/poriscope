## Poriscope 1.7: In Progress

* **New Data Plugin: `ThresholdBlockageFinder`**
    * Subclass of `ClassicBlockageFinder` that imposes much tighter bounds on the start and end times flagged in the output.

* **Deprecated Data Plugin: `ABF2Reader`**
    * Renamed to `TCossaLabABFReader` to reduce ambiguity with file types.

* **Updated Data Plugin: `WaveletFilter`**
    * Fixed a ctypes ABI mismatch (`c_int` vs `int64_t`) on the signal-length argument that risked memory corruption on large arrays
    * Calls into the shared native library are now serialized with a lock, since filters are invoked directly by other plugins rather than through the channel-management system

* **Updated Data Plugin: `NoFitter`**
    * Fixed an unbounded backtrack loop that could silently corrupt sublevel edges via negative array indexing instead of cleanly rejecting the event
    * Added missing validation for `None` baseline/padding inputs

* **Updated Data Plugin: `ClassicCUSUM`**
    * Removed an undocumented `/5` threshold divisor and a leftover debug `print()` that made this fitter far more sensitive than `CUSUM`/`IntraCUSUM`

* **Updated Data Plugins: `ClassicBlockageFinder`, `BoundedBlockageFinder`, `ThresholdBlockageFinder`**
    * Fixed a `ZeroDivisionError` on constant-signal chunks in baseline histogram calculation
    * Fixed dead code that silently skipped baseline-histogram window symmetrization
    * Fixed an ambiguous end-of-chunk check that could silently drop the remaining events in a chunk

* **Updated Data Plugins: `CUSUM`, `NoFitter`**
    * Fixed an off-by-one indexing bug that shifted every reported extreme-sublevel duration by one level

* **Updated Data Plugins: `Basic_PeakFinder`, `PeakFinder`**
    * Fixed an empty-slice bug that wrongly rejected legitimate events ending at the trace boundary

* **Updated Data Plugin: `BesselFilter`**
    * Fixed a boundary check that allowed `Poles = 0` despite requiring a positive integer

* **Updated Data Plugins: `ChimeraReader20240101`, `ChimeraReader20240501`, `ChimeraReaderVC100`, `TCossaLabABFReader`, `LegacyElementsReader`**
    * Fixed dead filename-pattern validation code that never actually rejected malformed filenames

* **Updated Data Plugin: `SingleBinaryDecoder`**
    * Fixed exception handling wrapped around the wrong line, leaving real file-open errors unprotected

* **Updated Database Plugins: `SQLiteDBWriter`, `SQLiteEventWriter`, `SQLiteDBLoader`, `SQLitePeakDBLoader`, `SQLiteEventLoader`, `MetaDatabaseLoader`**
    * Fixed several `UnboundLocalError`-masking exception handlers that hid the real database error
    * Fixed a `finally`-block bug that silently swallowed real write errors and reported success instead
    * Unused `SAVEPOINT`s are now properly released/rolled back instead of being a no-op
    * Hardened interpolated experiment/channel/index values and escaped quotes in experiment names so legitimate names no longer break queries
    * Fixed a crash on an empty query result and on a missing unfolded-level value
    * Fixed stray logging arguments that would crash the moment the log line was actually emitted
    * Fixed an overly broad exception clause that made two more specific error handlers unreachable

* **Updated Backend Infrastructure: `MetaEventFinder`, `MetaEventFitter`, `MetaWriter`, `EventWorker`, `MetaModel`, `LogDecorator`, `BaseValidator`, `QtHandler`**
    * Fixed a bug where an unexpected exception during event processing left a channel permanently unable to run again
    * Fixed a falsy-zero bug that silently dropped a legitimate chunk-boundary event start
    * Fixed a `ZeroDivisionError` in fit-progress logging that could permanently wedge a channel
    * Removed a redundant global lock now that the channel dispatcher already serializes correctly
    * App shutdown now correctly waits for worker threads to finish instead of potentially destroying a still-running thread
    * Fixed the `@log` decorator silently breaking exception handling and result logging for every generator-based method in the app
    * `BaseValidator` now properly enforces its abstract validation methods
    * Added a reentrancy guard so concurrent error/warning logs no longer stack multiple modal dialogs

* **Updated Frontend Base Class: `MetaView`**
    * New `plugin_state_changed` signal and abstract `notify_plugin_state_changed` hook, allowing any tab to notify all other tabs when a plugin instance's state changes (e.g. new columns added to a database). Every `MetaView` subclass must now implement `notify_plugin_state_changed`, even if the correct implementation is to do nothing. Non-trivial implementations must determine whether the notification is relevant to that tab, and filter and react accordingly.

* **Updated Frontend Plugins: `MetadataView` and `ProteinView`**
    * Replaced per-click DB queries with a cached event_id list and bisect-based navigation.
    * Previously, the forward/backward arrows shifted the "Event Index" field by a fixed step across the full database, with no awareness of any active filter. This made systematic inspection of filtered events tedious (there was no way to know how far to step to reach the next populated range, and the number of events plotted per step varied unpredictably depending on that range).
    * The old range field has been replaced with two new fields:
        * **Event ID** — snaps to the nearest filtered event at or after the requested ID
        * **# Events** — controls how many filtered events to display starting from that point
    * Forward/backward arrows now move through the filtered set directly, with wrap-around at both ends, so the subplot count is predictable and navigation stays filter-aware.
    * The display panel now shows the first and last event IDs in the filtered set, so users always know where they are.
    * Example: if only event_ids 2, 5, 8, 9, 12, 15 pass a filter (out of 15 total events), entering event_id=3 with # events=2 snaps to event_id 5, plots events 5 and 8, updates the Event ID field to 5, and displays "Filtered events: 6 total | first event_id: 2 | last event_id: 15". Clicking forward moves to event_id 9 and plots events 9 and 12 — always within the filtered set, never jumping over empty ranges.
    * Fetching and snapping is now O(1), a major speedup over the previous worst-case behavior.
    * Filter state (filter name and subset label) is now reflected directly in the display panel message.

* **Updated Frontend Plugin: `MetadataView`**
    * Fixed: some plot types (Categorical Histogram, Scatterplot, Raw/Filtered Event Overlay) failed to render after "Plot Events" + "Update Plot" due to a stale `self.axes` reference not caught by existing staleness check. Added `_axes_valid()` to detect and reset it properly.
    * Fixed: Silent crash in `_export_csv_subset` when the "Export Settings" dialog was canceled. Canceling the dialog now backs out cleanly.
    * Now refreshes its available column list automatically when another tab commits new columns to the currently selected database.
    * Fixed: `ZeroDivisionError` when constructing an event overlay from events that all have the same length
    * Fixed: crash when formatting an axis label for a column with no defined unit
    * Fixed: an unhandled plot type could leave plotting data unbound instead of raising a clear error
    * Fixed: a typo left stale event markers on the plot after a failed feature lookup
    * Removed a dead, exact-duplicate code block in all-points-histogram construction

* **Updated Frontend Plugin: `ProteinView`**
    * Fixed: `hist_min`/`hist_max` persisted across "Plot Histogram" calls and only ever expanded, so bin edges (and resulting histogram shape/fit) depended on plotting order and history instead of the event itself. Per-event histogram binning is now deterministic, and thus, so is plotting.
    * Fixed: Commit silently crashing every time due to a broken plugin-list refresh chain (the DB write itself still succeeded, so the crash went unnoticed). Replaced with a direct `update_available_columns(loader)` call. Removed dead code.
    * Committing now notifies other open tabs, so newly added columns appear immediately in any tab currently displaying that database.
    * Updated Walkthrough instructions. 
    * New **Report All** button in Ensemble mode: displays the double-Gaussian fit parameters (peak amplitude, mean, std) alongside the binning configuration that produced them, plus median ± std summaries of Prolate and Oblate V, a, b, and m from the Monte Carlo sample. Display-only, since Ensemble mode has no per-event id to write a database row against (replaced Commit All button).
    * New: Individual and Ensemble modes now use fully independent canvases for the histogram and V/M plots. Switching modes immediately shows that mode's last-drawn plot with no need to click Update Plot again, and no longer overwrites or erases the other mode's plot and data.
    * Updated: Reset previously cleared fit state for both Individual and Ensemble modes unconditionally, regardless of which mode was active. Reset is now scoped to the currently selected mode only, and the display panel confirms which mode's fit was cleared.
    * New: Running Update Plot in one mode could silently wipe out a valid fit stored in the other mode, causing "No ensemble fit available to report" even when a fit had been successfully computed earlier in the session.
    * Fixed: Clicking Commit Individual with no fit computed raised an unhandled `AttributeError` that was silently swallowed by the Qt event loop, giving no feedback in the UI. Now shows a clear message in the display panel.
    * Fixed: Some validation were passing an extra positional argument to `logger.warning`, crashing before the warning was ever shown.
    * Fixed: Leaving the **N** field blank in Ensemble mode raised a `ValueError` instead of falling back to a default, matching behavior already present in Individual mode.
    * Fixed: Default **N** value was set to 100 in the backend and 1000 in the frontend. Updated frontend to match the backend value.
    * Added Freedman-Diaconis auto-binning for per-event histograms
    * Fixed: zero-baseline divisions silently propagating NaN/Inf into histograms and fits
    * Added a hard cap to a previously-unbounded Monte Carlo sampling loop that could block the UI indefinitely
    * Fixed: plugin-list refresh crashing due to calling `.emit()` on a non-`Signal` method

        
* **Updated Frontend Plugin: `ClusteringView`**
    * Fixed: Commit silently crashing every time due to a broken plugin-list refresh chain (the DB write itself still succeeded, so the crash went unnoticed). Replaced with a direct `update_available_columns(loader)` call. Removed dead code.
    * Committing now notifies other open tabs, so newly added columns appear immediately in any tab currently displaying that database.
    * Fixed: clicking Cancel on the cluster-overwrite confirmation dialog did not actually cancel the commit
    * Fixed: an unrecognized clustering method crashed with an unbound-variable error instead of a clear message
    * Fixed: `ZeroDivisionError` in baseline stats on a flat/constant data chunk

* **Updated Frontend Plugin: `RawDataView`**
    * Fixed: `ZeroDivisionError` in baseline stats on a flat/constant data chunk; now logs a warning and skips just that channel's overlay instead of crashing the whole plot
    * Fixed: power spectral density calculation crashing or silently producing NaNs on very short channels

* **Updated Frontend Plugin: `EventAnalysisView`**
    * Fixed: crash when zero channels were selected while shifting or plotting events
    * Fixed: a failed event load could silently reuse stale data from a previous event
    * Fixed: a typo left stale event markers on the plot after a failed feature lookup

* **Updated Frontend Component: `MainView` / Sidebar Menus**
    * Fixed: Sidebar highlighting (icon and text menus) did not update when an analysis tab was opened via the top menu bar (Analysis → New Analysis Tab) or via the "Add" dropdown menu — the previously active tab's button stayed highlighted instead of switching to the newly opened tab.
    * Fixed: Selecting Raw Data, Event Analysis, or Metadata from the "Add" dropdown did not highlight their dedicated sidebar button.
    * Fixed: The "Add" dropdown menu reopened immediately after selecting an item, due to a duplicate signal connection 

* **Updated Frontend Component: `Settings`**
    * Settings window now follows OS light/dark mode automatically, and updates live if the OS theme changes while the app is open, no restart required
    * Fixed dropdown menus (combobox popups) rendering with a stray focus outline, a disappearing selection highlight on hover, and a double-border artifact
    * Application version in the About tab is now pulled from `poriscope.constants.__VERSION__` instead of a hardcoded string, so it can no longer drift out of sync

* **Updated Utility: `get_icon` (`poriscope.configs.utils`)**
    * Icons now automatically recolor for light/dark mode instead of requiring separate hardcoded black/white icon files
    * New `get_themed_icon_path` helper for cases (like custom stylesheet arrows) that need a real file path rather than an icon object

### General Fixes and Improvements:
    * Fixed `MainView` menu bar action icons silently failing to render due to an incorrect resource path (bug was invisible until now, since it failed silently)
    * Fixed `MetadataControls` DB Loader edit/delete buttons staying enabled when no database was loaded (placeholder text mismatch)
    * Fixed `MetadataControls`/`ProteinControls` crashing when the bins field ended in a trailing comma
    * Fixed `MetadataControls` computing bins-field validity but never actually using it to enable/disable **Update Plot**
    * Removed unused legacy icon assets and the broken/unused Qt `.qrc` resource system (`resources_rc.py`), which nothing in the app actually depended on
    * Standardized edit/add icons across control panels to use the same icon set consistently
    * In `Settings` fixed potential crash (`AttributeError`) if a folder-picker button was clicked before the data server / user plugin location had been set
    * Now: Icons correctly update color depending on dark/light mode
    * Replaced a hardcoded institution-specific network path default with the user's home directory
    * A corrupted config file now regenerates defaults on startup instead of crashing the app
    * `JsonDefaultSerializer` now also handles `Enum`, `datetime`/`date`, and `set`/`frozenset` values instead of only `PurePath`
    * All config file writes in `App`/`MainModel` are now wrapped in error handling instead of letting a write failure crash the app
    * Fixed `IntegerRangeLineEdit`/`CommaFloatRangeLineEdit` silently mis-parsing or truncating ranges containing an extra `-` (e.g. a leading minus sign or a stray third number); these fields only ever represent times or event indices, both non-negative, so a leading `-` is now rejected outright instead of ambiguously parsed
    * Fixed `MetaEventFinder.find_events` not stopping promptly when aborted mid-run: it previously kept processing every remaining range before discarding all results, instead of stopping as soon as the abort was received
    * Fixed `MetaEventFitter.fit_events` crashing with a `KeyError` when a fitter subclass returned mismatched-length sublevel-metadata arrays; the event is now cleanly rejected instead of aborting the whole channel
    * Updated tests in `test_main_controller.py`, `test_classic_cusum.py`, `test_no_fitter.py`, and `test_meta_event_finder.py` to match already-landed fixes (RPC dispatcher log-and-return behavior, corrected `ClassicCUSUM` threshold sensitivity, corrected `NoFitter` duration/extreme-value index alignment, and a dead-code precondition fix in `get_event_data_generator`) that had left their expectations stale
    * Fixed `RawDataModel.integrate_noise` crashing "Update PSD" with an uncaught `IndexError` when a short time window made `welch()` return a single-frequency-bin PSD
    * Fixed `RawDataModel`/`RawDataController`/`RawDataView` PSD calculation silently mislabeling a surviving channel's PSD under the wrong channel name whenever an earlier channel was skipped
    * Fixed `MetaWriter._rescale_data_to_adc`'s auto-scaling fallback computing its offset from `adc_max` instead of `data_max`, which silently corrupted ADC-encoded values (mapping them far outside the valid ADC range) whenever a writer relied on this fallback instead of an explicit gain setting
    * Fixed `BaseDataPlugin._validate_param_types` never actually validating primitive setting types (a broken `isinstance` check made it dead code for every data plugin); `DataPluginController.validate_and_instantiate_plugin` now also resets a resolved plugin-dependency setting's `Type` to `None` (matching `edit_plugin`), so the fixed check correctly skips resolved plugin references instead of rejecting them
    * Fixed `ProteinControls.is_placeholder_item` checking for `"No Database"` instead of the actual `"No Event Database"` placeholder, which left the DB Loader edit/delete buttons wrongly enabled with no database selected
    * Fixed `eventAnalysisControls.py` inserting `"No EventFitter"` into the fitter combo box while everything else checked for `"No Event Fitter"`, so the "no fitter selected" guard never fired and Fit Events could silently target a nonexistent plugin key; `validate_inputs` now also disables **Fit Events** when no real event fitter is selected, matching the loader/writer checks



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
