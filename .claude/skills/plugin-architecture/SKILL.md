---
name: plugin-architecture
description: How Poriscope's two-layer MVC and plugin system fit together - the app-shell triad, the GUI/analysis-tab and data-plugin families, how a tab reaches data plugins, plugin discovery and the BaseDataPlugin settings lifecycle, where to add a new data plugin or analysis tab, and trap questions to answer from the code before designing in an area. Load before reading, reasoning about, designing or changing anything in a plugin, a Meta* base, an analysis tab, the app-shell controllers or session persistence - including design discussion with no code change planned.
---

# Architecture

Poriscope is built from two layers that use the *same* MVC pattern recursively:

1. **App shell MVC** — `main_app.py` builds `MainModel` / `MainView` / `MainController`
   (`poriscope/models/main_model.py`, `poriscope/views/main_view.py`,
   `poriscope/controllers/main_controller.py`). This owns app config
   (`%LOCALAPPDATA%/Poriscope/config/config.json` via `platformdirs`), logging setup,
   and session persistence (`session/plugin_history.json`,
   `session/tab_action_history.json`).

2. **Plugin system** — everything else (analysis tabs, data readers/writers/filters/
   finders/fitters/loaders) is a *plugin* discovered and loaded dynamically.

## Two distinct plugin families

- **GUI/analysis-tab plugins** (`poriscope/plugins/analysistabs/`): each tab (RawData,
  EventAnalysis, Clustering, Metadata, Protein) is its own Controller/Model/View triad
  inheriting `MetaController`/`MetaModel`/`MetaView` (`poriscope/utils/Meta*.py`).
  A tab reaches a data plugin by calling `self.call(metaclass, key, method, ...)` on its
  Model (`MetaModel.call`), which raises at the call site on failure and refuses `_private`
  methods. It resolves against the live instance map that `MainController.update_available_plugins`
  pushes to every tab (`set_plugin_instances`, always before the names). Creating, editing and
  deleting plugins, plugin-state changes, status text and action history go out on typed
  signals that `MainController.instantiate_analysis_tab` connects point to point. This replaced
  the string-dispatched `global_signal` / `data_plugin_controller_signal` bus that used to relay
  every call up through `MainController`; that bus is gone, so do not rebuild one, and never
  import another tab's modules.

- **Data plugins** (`poriscope/plugins/{datareaders,datawriters,eventfinders,
  eventfitters,eventloaders,filters,db_loaders,dbwriters}/`): algorithmic/IO plugins,
  each inheriting one of the `Meta*` ABCs in `poriscope/utils/` (`MetaReader`,
  `MetaFilter`, `MetaEventFinder`, `MetaEventFitter`, `MetaEventLoader`, `MetaWriter`,
  `MetaDatabaseLoader`, `MetaDatabaseWriter`), which all ultimately inherit
  `BaseDataPlugin`. These are managed generically by `DataPluginController`/
  `DataPluginModel` (not per-plugin controllers) — instantiation, settings validation,
  renaming, and deletion of any data plugin goes through that one shared controller.

## Plugin discovery and instantiation

- `MainModel.populate_available_plugins()` walks `poriscope/plugins/` **and** the
  user plugin folder (`%LOCALAPPDATA%/Poriscope/user_plugins`, appended to `sys.path`),
  importing every `.py` file and keeping only classes matching the module's own
  filename that subclass one of the allowed `Meta*` base classes. A plugin is just a
  Python file dropped in the right subfolder — no registry/manifest to update.
- Each `Meta*` base uses `QObjectABCMeta` (ABCMeta combined with the Qt metaclass) so
  abstract methods are enforced *and* the class stays a valid QObject/QWidget. One class
  serves both hierarchies, because PySide6 gives `QObject` and `QWidget` the same
  metaclass.
- `BaseDataPlugin.__init__` -> `apply_settings()` drives a fixed lifecycle:
  `_validate_param_types` -> `_validate_param_ranges` -> `_validate_settings` (subclass
  hook) -> `_finalize_initialization` (subclass hook). Settings are dicts of
  `{"Type":..., "Value":..., "Options":..., "Min":..., "Max":...}` per parameter
  (see `get_empty_settings()` docstring in `BaseDataPlugin`).
- Data plugins can depend on other data plugins (e.g. an event finder depends on a
  reader). This is tracked explicitly via `register_parent`/`register_dependent`
  (metaclass, key) pairs on `BaseDataPlugin`, and enforced when
  `DataPluginController.delete_plugin`/`edit_plugin` refuse to delete/rename a plugin
  that still has dependents.
- Every plugin instance is keyed by a globally-unique string (`get_key()`/`set_key()`);
  `DataPluginController` enforces uniqueness of that key across *all* metaclasses, not
  just within one.

## Where to add a new plugin

- New data plugin: **generate it, don't hand-write it.**
  `python scripts/new_plugin.py MetaEventFinder MyFinder` (or with no arguments, to be
  asked) writes a stub in the right folder that already passes ruff, mypy, pydoclint,
  the compliance suite and the schema check. `--list` shows the eight families, the
  `AnalysisTab` keyword and every shipped plugin, since the same command also produces a *variant* of an existing plugin
  (`--override <methods>`, bodies delegating to `super()`). Signatures and docstrings are
  copied verbatim from the base, which is what the compliance test's exact-equality
  comparison requires. Hand-writing one still works: pick the matching
  `plugins/<category>/` folder, subclass the matching `Meta*` base, implement its
  `__abstractmethods__`, and drop the file in. The *app* needs no registration.
- **The repository does.** A new data plugin file is not finished until it is in each of
  these; the first two fail the suite until it is:
  - `scripts/measure_duplication.py`'s family list for its folder
    (`test_every_plugin_and_widget_file_is_measured_or_excluded`), then
    `python scripts/measure_duplication.py --update` in the same commit, the reason in the
    commit message if the number rose;
  - its conformance recipe in `tests/unit/plugins/conformance/_recipes.py`: each family's
    dict raises `KeyError` naming itself for a plugin without one (`READER_DATASET_BUILDERS`,
    `EVENT_FINDER_SETTINGS`, `EVENT_FITTER_SETTINGS`, `FILTER_SETTINGS`). A reader also takes
    `READER_EXTRA_SETTINGS` for a setting with no default, and any format-specific fuzz
    mutation in `MUTATIONS` (the shared ones follow `READER_DATASET_BUILDERS` automatically);
  - `poriscope/exposed.py`'s imports and `__all__`, so scripts can import it;
  - the user guide's list for its family (readers: `user_guide/raw_data_tab.rst`) and a
    `changelog.md` line. The autodoc page is generated (`docs/source/autodoc/` is gitignored).
- Draft a plugin outside the tree while a suite is running: `new_plugin.py ... --output-dir`
  writes anywhere, and plugin discovery imports every file in the package.
- **A general plugin with narrowing subclasses** (the ABF readers, 2026-10-09): the base is a
  usable plugin whose settings cover every variant of its format, and a subclass for one
  recording family fixes some of them by *deleting their keys* in `get_empty_settings`. There
  is no hidden or read-only setting in the dialog, so the base reads each such setting through
  a helper that falls back to a module-level defaults dict - one source for the dialog's
  default and the deleted key's value (`ABFReader._abf_setting`, `SETTING_DEFAULTS`). The
  subclass overrides only `get_empty_settings` and the file-set methods.
- New analysis tab: generate it too. `python scripts/new_plugin.py AnalysisTab MyTab`
  writes the Controller/Model/View triad and its controls panel under
  `poriscope/plugins/analysistabs/`, subclassing `MetaController`/`MetaModel`/`MetaView`.

## Trap questions: check before designing

Each area below lists questions whose obvious answer has been wrong before. Before designing in that area,
answer each one fresh from the code, starting where it says, and put the answers with `file:line` in your
overview. Don't answer from this file, from memory or from a design document: the case note says what was
assumed, not what is true now.

Add a trap only with evidence: a design or claim that went wrong, with its case. No speculative entries.
When a correction shows a wrong assumption about the codebase, propose it as a trap for its area and ask
the user before adding it.

### Tabs, sessions and the action history

- **How many instances of this tab can exist, and what tears one down?**
  Start at `MainController.instantiate_analysis_tab` and every place `analysis_tabs` is cleared.
  *Case:* use cases assumed a second tab of the same type and a per-tab close.
- **For each session file: who writes it, when, and who reads it on load, and does that reader accept it?**
  Start at `MainModel.save_session`, `save_tab_actions` and `load_session`.
  *Case:* designs assumed the action history comes back with a loaded session.
- **Which tabs expose this mechanism to the user, as opposed to inheriting it from a base class?**
  Start at each tab's controls panel and its `handle_parameter_change` dispatch, not at the `Meta*` base.
  *Case:* a design wrote Undo for every tab; the logic is shared, but only one tab wires a control to it.
- **Does replaying an action record it again?**
  Start at `MetaView.update_actions_from_json` and `LogDecorator.register_action`, then follow the history
  signal into `MetaController.update_tab_actions`.
  *Case:* a design note stated that replay bypasses the decorator; rollback reasoning was built on that.
- **Is this reset global to the tab, or scoped to a mode?**
  Read each tab's `_reset_actions` body, not the base docstring.
  *Case:* a design made every reset invalidate all earlier history; one tab's reset clears only the active
  mode's state.
- **Does a recorded method depend on anything not in its recorded arguments: a widget, or view state a
  widget sets?**
  Read the body of every method that is, or will be, decorated with `@register_action`, and the methods it
  calls on `self`. List every `self.` attribute it reads, and for each, find what sets it.
  *Case:* two recorded plot actions read the live selection mid-body, so replay applied whatever was
  selected at replay time (`DECISIONS.md` 2026-09-17, rule 5). After that was fixed, one tab's recorded
  reset still branched on a mode flag that the mode buttons set, which is not among its recorded arguments.
- **What does this Controller slot actually receive, and how is each argument built?**
  Start at the View method that emits the signal, and the helper that builds each argument.
  *Case:* a design said `RawDataController.start_eventfinding` loses the Timer limits; its time ranges are
  the limits, reshaped by `RawDataView._ranges_for_channel`.
- **Does this action chain reactively, or does the View drive it?**
  Start at the action's View handler. After its first request, does the View read the reply or loop, or
  does the Controller call the next View step?
  *Case:* a design generalised Metadata's View-driven overlay plot to every subset tab; the Clustering run
  is reactive and replays whole from its first Controller step.
- **Do the Controller's arguments carry intent or data?**
  Start at the slot's signature.
  *Case:* a fix list for recording on the Controller named only the matplotlib `Axes` argument; the same
  Metadata slots (`calculate_histogram_bins` and its siblings) also receive the plotted arrays.
- **Does replaying only the recorded calls reproduce the result? Run it, don't predict it.**
  Start at `tests/integration/flows/_triad.py` `build_triad`: capture the calls, replay them into a fresh
  tab, and compare the figure, the plot cache and the tab's bookkeeping.
  *Case:* a design predicted Metadata's plot would differ; it drew the same bars, but left the plot cache and
  the "already plotted" record empty.
