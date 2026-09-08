---
name: plugin-architecture
description: How Poriscope's two-layer MVC and plugin system fit together - the app-shell triad, the GUI/analysis-tab and data-plugin families, the signal-relay bus, plugin discovery and the BaseDataPlugin settings lifecycle, and where to add a new data plugin or analysis tab. Load before adding, moving or restructuring a plugin, a Meta* base, or an analysis tab.
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
  `MetaController` wires a `QObject`-based signal bus (`global_signal`,
  `data_plugin_controller_signal`, etc.) so a tab can invoke methods on *another* tab's
  plugin or on a data plugin without a direct reference — the call is relayed up
  through `MainController`, which resolves `(metaclass, subclass_key)` to a live
  instance. When adding cross-tab behavior, follow this signal-relay pattern rather
  than importing another tab's controller directly.

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
- Each `Meta*` base uses `QObjectABCMeta`/`QWidgetABCMeta` (ABCMeta combined with the
  Qt metaclass) so abstract methods are enforced *and* the class stays a valid
  QObject/QWidget.
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
  the compliance suite and the schema check. `--list` shows the eight families and every
  shipped plugin, since the same command also produces a *variant* of an existing plugin
  (`--override <methods>`, bodies delegating to `super()`). Signatures and docstrings are
  copied verbatim from the base, which is what the compliance test's exact-equality
  comparison requires. Hand-writing one still works: pick the matching
  `plugins/<category>/` folder, subclass the matching `Meta*` base, implement its
  `__abstractmethods__`, and drop the file in — no registration needed.
- New analysis tab: add a Controller/Model/View triad under
  `poriscope/plugins/analysistabs/` following an existing tab (e.g. `Protein*`) as a
  template, subclassing `MetaController`/`MetaModel`/`MetaView`.

