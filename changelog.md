## Poriscope 1.5: In Progress

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
