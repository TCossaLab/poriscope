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

The five tabs Poriscope ships fall into two families, and each family has its own set of
bases holding the code its members share.

**Subset tabs** work from a database of *results*. The user picks an experiment and some
channels, builds a named subset filter over the columns in that database, and plots or
exports the rows that come back. Metadata and Protein are these.

**Event tabs** work from a *reader and a raw signal*. The user picks a reader, a filter
and a channel, and the tab finds or fits events in the time series itself. Raw Data and
Event Analysis are these.

Clustering is neither. It reads a database like a subset tab but has no subset filtering,
no experiment selection and no event navigation, so it inherits the common bases
directly — which is a perfectly normal thing for a tab to do.

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
     - ``_init``, ``update_available_plugins``
     - RawDataView, EventAnalysisView
   * - ``MetaView``
     - is neither of the other two
     - ``_init``, ``_reset_actions``, ``notify_plugin_state_changed``, ``update_available_plugins``
     - ClusteringView
   * - ``MetaSubsetTabView``
     - queries a results database with user-defined subset filters
     - the four above, plus ``_delete_filter`` and ``show_edit_filter_dialog``
     - MetadataView, ProteinView

Note the ordering: **an intermediate does not always ask less of you than the base.**
``MetaEventTabView`` asks for *two* methods rather than four, because it implements
``_reset_actions`` and ``notify_plugin_state_changed`` on your behalf — the two event
tabs agree on both. ``MetaSubsetTabView`` asks for *six*, because subset filtering is a
contract of its own: it manages the filters, and you supply the two operations that have
to rebuild your tab's own filter widgets afterwards.

What ``MetaSubsetTabView`` gives you, on top of ``MetaView``: the query and column
setters (``set_query``, ``set_event_query``, ``update_available_columns``,
``update_units``), subset-filter management (``_save_filter``,
``_delete_filter_by_name``, ``_show_filter_info_dialog``,
``clear_pending_filter_state``), the experiment-selection tree
(``show_selection_tree``, ``request_experiment_structure``) and ``get_save_filename``.

What ``MetaEventTabView`` gives you: the event-index range helpers
(``_parse_event_indices``, ``_expand_event_indices``, ``_shift_ranges``,
``_merge_ranges``, ``_format_ranges``) that turn an event-index field into ranges and
back for the navigation arrows, plus ``validate_single_channel``,
``_extract_commit_event_parameters`` and ``set_data_filter_function``.

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
     - the plugin bus, session state, worker management
     - ClusteringController
   * - ``MetaSubsetTabController``
     - sixteen relays for experiment, column, unit and query results
     - MetadataController, ProteinController
   * - ``MetaEventTabController``
     - ``update_available_plugins`` and ``update_plot_samplerate``
     - RawDataController, EventAnalysisController

All three ask for the same two methods: ``_init`` and ``_setup_connections``.

The Model
---------

There is one base, ``MetaModel``, and it asks for ``_init``. Analysis-tab Models are
where computation and data access belong — see :doc:`metamodel_base`.

The controls panel
------------------

Your tab's control panel — the row of comboboxes and buttons above the plot — is a
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
     - the filter combobox and its three buttons, the loader combobox, the bins validator
     - nothing
   * - ``MetaEventTabControls``
     - the channel multiselect, the filter combobox, the event-index field
     - ``validate_inputs``

Every controls class owes two things regardless: its own
``logger = logging.getLogger(__name__)``, so its log records stay attributed to its own
module, and a ``setupUi`` that builds the widgets its base's methods read. Those widgets
are declared on the base as annotations — read the base's class docstring for the list.

Building your control area
--------------------------

You do not write ``_set_control_area`` any more. ``MetaView`` implements it: it calls
``_build_controls()``, connects the four signals every controls panel carries, and
places the widget. So the usual thing to write is three lines:

.. code-block:: python

   def _build_controls(self) -> MyTabControls:
       self.mytabcontrols = MyTabControls()
       return self.mytabcontrols

The hook returns the widget rather than just assigning it, so that your tab can keep it
under whatever name suits — the shipped tabs use ``self.metadatacontrols``,
``self.rawdatacontrols`` and so on, and those names are also the dispatch keys in a
tab's saved action history.

If your panel carries signals beyond the four shared ones, override
``_connect_control_signals``. ``MetaSubsetTabView`` does exactly that, for the two
filter signals only ``MetaSubsetTabControls`` declares.

If your tab lays out its own control area and uses no ``MetaControls`` panel at all,
override ``_set_control_area`` instead and ignore ``_build_controls``. That is what the
Hello World tutorial does.

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
