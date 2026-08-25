# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Poriscope is a PySide6 (Qt) desktop application for selecting and analyzing nanopore
timeseries data (event detection, fitting, clustering, protein analysis, etc.). Python
>= 3.12, Windows-focused but CI runs on Linux under Xvfb.

## Setup

```
pip install -e ".[dev]"
python scripts/setup_hooks.py   # enables pre-commit and post-merge git hooks
```

Run the app with the `poriscope` console-script entry point (`poriscope.main_app:main`).

## Common commands

```
pytest                                        # full suite
pytest -m "not e2e and not slow"              # what CI runs on every branch push
pytest tests/unit/plugins/test_plugin_compliance.py   # plugin interface compliance
pytest path/to/test_file.py::test_name        # single test
pytest -m fast                                # quick tests only (<5s)

pre-commit run --all-files --hook-stage manual   # auto-fix: black, ruff --fix
pre-commit run --all-files                       # strict check: ruff + mypy + pydoclint (what pre-commit/CI enforce on real commits)
mypy poriscope                                    # NOT the gate - see the warning below
pydoclint --baseline=.pydoclint-baseline.txt poriscope   # docstring/signature consistency check directly
```

Note: `black` and the ruff auto-fix hook only run at `stages: [manual]` — they do not
run automatically on `git commit`. Run `pre-commit run --all-files --hook-stage manual`
yourself before committing if you want formatting applied; the pre-commit hook itself
runs ruff (strict, no fix), mypy, and pydoclint.

**`pre-commit run mypy --all-files` is the mypy gate; `mypy poriscope` is not.** The two
disagree wildly and are blind in opposite directions. The hook runs in an isolated
virtualenv with no project dependencies, so PySide6/numpy/pandas types are all `Any` to
it; the project venv's `mypy poriscope` sees real types but is a different version and
reports several hundred errors that are overwhelmingly known noise (191 PySide6
short-form enum accesses alone - see `DECISIONS.md`). **Always measure with the hook.**
The hook is scoped `files: ^poriscope/` because `mypy.ini`'s `exclude = ^tests/` governs
directory discovery only and does not apply to explicitly listed paths.

`pydoclint` checks that a docstring's documented parameters, return type, and raised
exceptions actually match the real function signature/body. It does NOT require every
function to have a docstring — functions with no docstring are skipped entirely — but it
DOES require that a documented function's signature carry type hints, and that those
hints agree with the docstring's `:type:`/`:rtype:`
(`arg-type-hints-in-signature = true` in `pyproject.toml`). **Every function under
`poriscope/` is annotated, with no exclusions**, so new code is expected to be too.

**`.pydoclint-baseline.txt` is empty (0 bytes) as of 2026-08-25** — the ~1,090
grandfathered violations this tool was adopted with are all cleared. Every violation
from here on is a real one that fails the hook, so there is normally nothing to
regenerate. If you ever do need to, `pydoclint --generate-baseline=True
--baseline=.pydoclint-baseline.txt poriscope` — but prefer fixing the violation, and do
not let the file grow back silently.

`check-class-attributes` is deliberately `false`. It cannot work under sphinx style
with the parser pydoclint 0.9.1 ships: only the *malformed* `.. attribute :: name`
(note the space, which makes it a comment rather than a directive) is recognised, while
the correct `.. attribute::` and every canonical field form parse to nothing. See
`DECISIONS.md`; a bug report is drafted for upstream.

Qt-based tests need `qt_api = pyside6` (already set in `pytest.ini`) and, on Linux/CI,
`QT_QPA_PLATFORM=offscreen` plus `xvfb-run`.

Pytest markers (see `pytest.ini`): `compliance`, `fast`, `integration`, `e2e`, `e2e_ux`.

## Architecture

Poriscope is built from two layers that use the *same* MVC pattern recursively:

1. **App shell MVC** — `main_app.py` builds `MainModel` / `MainView` / `MainController`
   (`poriscope/models/main_model.py`, `poriscope/views/main_view.py`,
   `poriscope/controllers/main_controller.py`). This owns app config
   (`%LOCALAPPDATA%/Poriscope/config/config.json` via `platformdirs`), logging setup,
   and session persistence (`session/plugin_history.json`,
   `session/tab_action_history.json`).

2. **Plugin system** — everything else (analysis tabs, data readers/writers/filters/
   finders/fitters/loaders) is a *plugin* discovered and loaded dynamically.

### Two distinct plugin families

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

### Plugin discovery and instantiation

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

### Where to add a new plugin

- New data-processing algorithm: pick the matching `plugins/<category>/` folder,
  subclass the matching `Meta*` base from `poriscope/utils/`, implement the abstract
  methods it requires (check `__abstractmethods__` / the compliance test for the
  authoritative list), and drop the file in — no other registration needed.
- New analysis tab: add a Controller/Model/View triad under
  `poriscope/plugins/analysistabs/` following an existing tab (e.g. `Protein*`) as a
  template, subclassing `MetaController`/`MetaModel`/`MetaView`.

### Testing conventions

- `tests/unit/` mirrors `poriscope/{controllers,models,views,plugins,utils}`.
- `tests/unit/plugins/test_plugin_compliance.py` recursively imports every module
  under `poriscope.plugins` and asserts each plugin subclass implements all abstract
  methods of its `Meta*`/`BaseDataPlugin` base — this is the guardrail that keeps the
  plugin contract intact; run it after touching any `Meta*` base or plugin signature.
- `tests/integration/flows/` instantiate real controller/model/view stacks
  "no_gui" (headless) for cross-plugin flows; `tests/e2e/` drive actual Qt widgets
  (`e2e_ux` marker) end-to-end and are excluded from the standard CI run
  (`not e2e and not slow`).

## Docs

Sphinx docs live in `docs/` and are largely autogenerated from plugin docstrings via
`scripts/autodoc/*.py` / `scripts/generate_all_autodoc_rst.py`, run automatically by
the `post-merge` git hook. Published at https://tcossalab.github.io/poriscope/.

## Changelog

Any time you make changes to the code, update `changelog.md` with a terse explanation under 
the appropriate header/subheader, respecting formatting ceonventions already present in that file.

## Where things are written down

- `changelog.md` — what changed, user-facing. Update it for any code change.
- `future_fixes.md` — what is still queued. Keep it terse; prune items as they land
  rather than leaving completed-work narrative behind.
- `DECISIONS.md` — why we chose *not* to do something, with the evidence and what
  would make it worth revisiting. Check here before re-litigating a settled question.
- `future_refactors_and_features.md` — larger speculative work.

Depth belongs in those files, not in this one: this file is loaded in full at the start
of every session, so it should stay a short list of standing rules.

## General Instructions

- Do not nest functions inside other functions (`utils/LogDecorator.py` is the standing
  exception - decorators require it).
- **Never add `@overload` or `cast()` to work around an over-broad return union.** Verify
  every incoming call and delete the dead branch instead. If both arms are genuinely live,
  flag it for review rather than overloading - the fix is usually to change the callers.
  See `DECISIONS.md`.
- **Call out breaking changes explicitly in `changelog.md`**, rather than describing them
  as ordinary fixes. Narrowing or removing anything on a `Meta*` ABC counts.
- Imports go at module level. Do not add function-local ("lazy") imports, and hoist
  any you come across. The only exception is a real circular import, which goes in an
  `if TYPE_CHECKING:` block with a comment explaining the cycle (see
  `views/widgets/icon_menu_widget.py` for the pattern).
- When the user reports a bug to you and asks you to fix it, double check the assumptions 
  before implementing the fix. Do not blindly accept the assertions of the user as to the
  cause of potential issues. Be thorough in your analysis, ensuring that you fully trace 
  related logic paths to ensure that nothing breaks downstream as the result of an applied
  fix, and explain any issues surfaced to the user and request input before proceeding if
  you find that a user-based assumption or instruction would cause problems.
- We are not in a rush, and the poriscope codebase is complex. Take the time and spend the 
  tokens you need to get it right.
