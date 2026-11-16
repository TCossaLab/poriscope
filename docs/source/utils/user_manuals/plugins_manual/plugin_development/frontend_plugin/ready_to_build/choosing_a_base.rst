.. _choosing_a_base:

Choosing What to Inherit From
=============================

An analysis tab is three classes — a View, a Model and a Controller — and for the View
and the Controller there is now more than one base to pick from. Picking the right one
is the difference between writing two methods and writing twenty.

The short version: **find the shipped tab that most resembles the one you are building,
and inherit what it inherits.** The rest of this page is how to tell.

Two shapes of tab
-----------------

Four of the six tabs Poriscope ships fall into two families, and each family has its own
set of bases holding the code its members share.

**Subset tabs** work from a database of *results*. The user picks an experiment and some
channels, builds a named subset filter over the columns in that database, and plots or
exports the rows that come back. Metadata and Protein are these.

**Event tabs** work from a *reader and a raw signal*. The user picks a reader, a filter
and a channel, and the tab finds or fits events in the time series itself. Raw Data and
Event Analysis are these.

Clustering and Conditioning are neither, so they inherit the common bases directly -
which is a perfectly normal thing for a tab to do. Clustering reads a database like a
subset tab but has no subset filtering, no experiment selection and no event navigation;
Conditioning reads a conditioning experiment through its own loader family.

The View
--------

.. list-table::
   :header-rows: 1
   :widths: 22 30 24 24

   * - Inherit
     - When your tab…
     - You must implement
     - Shipped tabs
   * - ``MetaEventTabView``
     - finds or fits events in a raw signal from a reader
     - ``_init``, ``handle_parameter_change``, ``update_available_plugins``, ``_handle_plot_events``, plus the ``_event_controls`` property
     - RawDataView, EventAnalysisView
   * - ``MetaView``
     - is neither of the other two
     - ``_init``, ``_reset_actions``, ``handle_parameter_change``, ``notify_plugin_state_changed``, ``update_available_plugins``
     - ClusteringView, ConditioningView
   * - ``MetaSubsetTabView``
     - queries a results database with user-defined subset filters
     - the five above, ``_replot_after_shift``, plus the ``_subset_controls`` property
     - MetadataView, ProteinView

Note the ordering: **an intermediate does not always ask less of you than the base.**
``MetaEventTabView`` implements ``_reset_actions`` and ``notify_plugin_state_changed`` on
your behalf — the two event tabs agree on both — and asks instead for
``_handle_plot_events``, which its event navigation re-plots through, and a one-line
``_event_controls`` property returning your controls panel under a name its shared
methods can use. ``MetaSubsetTabView`` asks for *seven*: the five ``MetaView`` wants, the
same kind of one-line ``_subset_controls`` property, and ``_replot_after_shift``, which
re-plots after event navigation in whichever display your tab is showing. Subset
filtering is a contract of its own, but it is one this base implements entirely - it
manages the filters, the dialogs that edit them and the combobox that shows them,
reaching your panel through that property.

``MetaSubsetTabView`` adds, on top of ``MetaView``, the query setters, subset-filter
management and its dialogs, the filtered-event cache and event navigation through it, an
event plot's click, scatterplot drawing and the experiment-selection tree.
``MetaEventTabView`` adds the navigation arrows and their event-index range helpers,
single-channel validation, and the modal that asks before a run with no filter selected.
The reference pages :ref:`MetaSubsetTabView` and :ref:`MetaEventTabView` list every
method.

The Controller
--------------

The same split, and you normally match it to whichever View you chose.

.. list-table::
   :header-rows: 1
   :widths: 26 40 34

   * - Inherit
     - What it adds
     - Shipped tabs
   * - ``MetaController``
     - the typed plugin signals, the action history and replay, session state, worker
       management (a data plugin is reached through the Model's ``call()``)
     - ClusteringController, ConditioningController
   * - ``MetaSubsetTabController``
     - the experiment and channel scope, units, filter validation and
       query results, the event-plot chain, the filter file's load and save, and session
       state
     - MetadataController, ProteinController
   * - ``MetaEventTabController``
     - ``update_available_plugins``, ``_resolve_callable_filter`` and
       ``_verify_filter_samplerate``
     - RawDataController, EventAnalysisController

``MetaController`` and ``MetaEventTabController`` ask for ``_init`` and
``_setup_connections``. ``MetaSubsetTabController`` asks only for ``_init``: it implements
``_setup_connections`` itself, so an override must call ``super()._setup_connections()``
first or the shared lookups are never wired.

The Model
---------

Two bases, and both ask for ``_init``. Analysis-tab Models are where computation and
data access belong — see :doc:`metamodel_base`.

.. list-table::
   :header-rows: 1
   :widths: 26 40 34

   * - Inherit
     - What it adds
     - Shipped tabs
   * - ``MetaModel``
     - the plugin call, worker management, the logscale filter, the plot time base,
       plot-data caching
     - ClusteringModel, ConditioningModel, RawDataModel, EventAnalysisModel
   * - ``MetaSubsetTabModel``
     - the events-table lookups behind an event plot, and the subset filter file's JSON
     - MetadataModel, ProteinModel

Inherit ``MetaSubsetTabModel`` only if your tab reads its data from a
``MetaDatabaseLoader``; a tab that reads a timeseries has no events table to query and
no filter file to write.

The controls panel
------------------

Your tab's control panel — the row of comboboxes and buttons below the plot — is a
separate widget, and it has the same three-way choice.

.. list-table::
   :header-rows: 1
   :widths: 28 46 26

   * - Inherit
     - What it adds
     - You must implement
   * - ``MetaControls``
     - widget factories, the plugin edit/add/delete icon buttons, the placeholder guard
     - nothing
   * - ``MetaSubsetTabControls``
     - the filter combobox and its three buttons, the loader combobox, the bins validator,
       the event-id field's setter, and the write-back setters for the loader, bins and
       Sizes, event count, Raw and filters
     - ``validate_inputs``
   * - ``MetaEventTabControls``
     - the channel multiselect, the filter combobox, the event-index field
     - ``validate_inputs``

Every controls class owes two things regardless: its own
``logger = logging.getLogger(__name__)``, so its log records stay attributed to its own
module, and a ``setupUi`` that builds the widgets its base's methods read. Those widgets
are declared on the base as annotations — read the base's class docstring for the list.

Building your control area
--------------------------

You override ``_build_controls`` to return your panel, and ``MetaView`` places it and
connects the four signals every controls panel carries; :doc:`metaview_base` shows the
three lines. If your panel carries signals beyond the four shared ones, override
``_connect_control_signals``, as ``MetaSubsetTabView`` does for the two filter signals
only ``MetaSubsetTabControls`` declares.

If you only want part of one
----------------------------

Ask which half you want.

**A method with no state behind it** can be pulled up to the common base even if only
some tabs call it. Inherited behaviour that carries no state and no contract costs
nothing.

**Behaviour that comes with instance state, abstract hooks or new dependencies** should
not go on ``MetaView``. ``MetaView`` is the published extension point, and widening it
means every future tab author has to work out whether a contract applies to them. That
is what the intermediates exist for.

**Do not reach for a mixin.** Poriscope has one, ``WalkthroughMixin``, and it is
inherited by ``MetaView`` rather than mixed into each tab; a second composition
mechanism would leave no rule for choosing between them.

If you find yourself wanting exactly half of an intermediate, or wanting two of them at
once, that is worth raising rather than working around — single inheritance has stopped
describing the structure, and the right answer is probably to move something.
