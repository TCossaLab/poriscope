# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Kyle Briggs

"""
Check the analysis-tab MVC boundary, against a shrinking allowlist.

    python scripts/check_mvc_boundary.py [--verbose] [--update] [--check]

The analysis-tab layer never grew a real Model, so the Views absorbed the work a
Model should do. Four rules describe the boundary the 2.0.0 refactor is putting
back, and the allowlist counts how far it still is from holding. **That count going
to zero is Steps 3-5 finishing**, which is why it is the refactor's headline metric
rather than a pass/fail gate: every entry is a known violation, recorded so that a
*new* one cannot slip in beside it.

The four rules:

1. **No View emits on the plugin bus.** A ``global_signal.emit`` in a widget means a
   cross-plugin call originates in the View. Step 4a turns these into
   ``self.call(...)`` on the Model.
2. **No View imports a computation library** - numpy, scipy, sklearn, hdbscan,
   pandas, ``fast_histogram`` or sqlite3. ``fast_histogram`` is in that list because
   ``RawDataView`` imports it and Step 4c moves it; without it, 4c could finish with
   the rule still reporting success. ``sqlite3`` contributes **zero** today - the
   Views build SQL as f-strings and hand it to the loader rather than importing a
   driver - and stays in as a ratchet against that changing.
3. **No Controller reads a View private.** ``self.view._x`` is the Controller
   reaching past the View's interface into its internals; Step 4d moves that state
   to the Model.
4. **No app-shell module imports from a plugin package.** ``poriscope/views/``
   importing ``poriscope.plugins.analysistabs.utils.walkthrough`` was a layering
   inversion: the shell depending on a plugin. Step 3f fixed it by moving those two
   modules into ``views/widgets/``, and without this rule nothing would have observed
   that the step had finished. Added by the Step 2 exit review; **reads zero since
   2026-09-06**, and stays in as a ratchet against a new inversion appearing.
5. **No analysis-tab module reaches a data plugin except through ``call()``.**
   ``MetaController.call`` and ``MetaModel.call`` are the whole plugin-facing API a tab
   gets (Step 4a, Decision A); a tab that resolves an instance for itself, or imports a
   concrete plugin class, has gone around it. Added 2026-09-07 and **reads zero**, so
   it is a ratchet from the start rather than a backlog. Python cannot enforce this at
   runtime without inspecting the call stack on every plugin call, which would cost
   more than it is worth and would reject the worker-thread path; a static ratchet
   fails on the commit instead, which is earlier and cheaper.

**The rule's exact definition is the number, so it is stated here rather than left
to be inferred.** An earlier count of "21 import statements over 12 View x module
pairs" could not be reproduced because it was never written down precisely enough:

- An import contributes **one entry per import statement**, keyed by the dotted
  module path as written. ``import numpy as np`` and ``import numpy.typing as npt``
  are two entries, ``numpy`` and ``numpy.typing``; ``from pandas.api.types import
  is_float_dtype`` is one entry, ``pandas.api.types``. A statement counts when its
  **top-level** package is in ``FORBIDDEN_IMPORTS``, so a submodule of a forbidden
  package is forbidden too.
- The distinct (View, top-level module) pair count is a separate, smaller figure
  reported for context. It is not what the allowlist totals.
- An emit is an ``ast.Call`` on an attribute named ``emit`` whose receiver is an
  attribute named ``global_signal``, so ``self.global_signal.emit(...)`` counts and
  a different signal's ``emit`` does not.
- A private access is an attribute read whose receiver is ``self.view`` and whose
  name starts with a single underscore. Dunders are excluded; they are Python
  protocol, not View internals.
- A layering violation is one import statement in ``poriscope/views``,
  ``poriscope/controllers`` or ``poriscope/models`` naming anything under
  ``poriscope.plugins``. Relative imports are skipped and ``__init__.py`` files are
  not scanned, since re-exports there would be noise rather than dependencies.
- A plugin-reach violation is one of three things in an analysis-tab module: a call to
  ``get_plugin_instance``, an attribute access named ``data_plugin_controller``, or an
  import of a module under ``poriscope.plugins.<family>`` for one of the eight data
  plugin families. The signal named ``data_plugin_controller_signal`` is a different
  identifier and does not count. ``_plugin_instances`` is not counted either: that is
  the sanctioned mechanism ``call()`` reads, pushed in by ``MainController``.

**Which files each rule reads.** Rules 1-3 originally scanned ten hardcoded filenames
under ``poriscope/plugins/analysistabs/``, which made them blind to their own refactor:
a method promoted to a base in ``poriscope/utils/`` left the measurement without being
fixed, and Step 3b's first promotion carries 100% of rule 3's violations. So layer
membership is now *derived* over the whole of ``poriscope/``, by two tests - a
directory whose contents are all one layer, or a filename suffix that names the role
wherever the module lives. The suffix test is the part that matters: a base promoted
into ``poriscope/utils/`` is measured the moment it is named ``MetaEventTabView.py``.
Widening it moved the View layer from 5 modules to 33 and the Controller layer from 5
to 8, and added exactly two entries - ``MetaView``'s ``numpy`` and ``numpy.typing``,
a real rule-2 violation the narrow scan could not see, which clears when Step 3d moves
``_logscale_and_filter_multiple_columns`` to ``MetaModel``.

**Rule 4 is deliberately *not* widened to ``poriscope/utils/``.** Those are shared
bases rather than app shell, and ``poriscope/utils/plugin_schemas.py`` imports
``poriscope.plugins`` on purpose, to walk the plugin package for schemas. Booking it
would put an entry on the allowlist that the refactor has no intention of removing,
which is the one thing that would make the total meaningless.

Exits 1 under ``--check`` if the counts disagree with
``.mvc-boundary-allowlist.json`` in **either** direction. A rise is a new violation.
A fall is progress, and it fails too, so the win is recorded in the same commit that
earned it - the allowlist is the progress metric, and it is only meaningful if it is
kept current.
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
PORISCOPE = REPO_ROOT / "poriscope"

#: Directories whose every module is View-layer code: the app shell's own widgets
#: and the widgets an analysis tab is assembled from.
VIEW_DIRS: Tuple[str, ...] = (
    "poriscope/views",
    "poriscope/plugins/analysistabs/utils",
)

#: Filename suffixes that make a module View-layer wherever it lives. This is what
#: keeps the set derived rather than a second hardcoded list: a base promoted into
#: ``poriscope/utils/`` is measured the moment it is named ``MetaEventTabView.py``.
#: ``poriscope/utils/`` cannot be taken wholesale - it is flat and holds bases for
#: every layer, including eight data-plugin bases that import numpy by design - so
#: role is read off the filename there.
VIEW_SUFFIXES: Tuple[str, ...] = ("View.py", "Controls.py", "controls.py")

#: The Controller layer, by the same two tests.
CONTROLLER_DIRS: Tuple[str, ...] = ("poriscope/controllers",)
CONTROLLER_SUFFIXES: Tuple[str, ...] = ("Controller.py",)

#: Top-level packages a View has no business importing. ``sqlite3`` is zero today
#: and kept as a ratchet; ``fast_histogram`` is here because Step 4c moves it.
FORBIDDEN_IMPORTS: Set[str] = {
    "fast_histogram",
    "hdbscan",
    "numpy",
    "pandas",
    "scipy",
    "sklearn",
    "sqlite3",
}

#: The app shell. Nothing under here may import from a plugin package.
SHELL_ROOTS: Tuple[str, ...] = (
    "poriscope/views",
    "poriscope/controllers",
    "poriscope/models",
)

#: The package the shell must not depend on.
PLUGIN_PACKAGE = "poriscope.plugins"

#: The eight data plugin families. An analysis tab must not import a concrete plugin
#: from any of them - it reaches them by key through ``call()``.
PLUGIN_FAMILIES: Set[str] = {
    "datareaders",
    "datawriters",
    "db_loaders",
    "db_writers",
    "eventfinders",
    "eventfitters",
    "eventloaders",
    "filters",
}

#: Filename suffixes that put a ``poriscope/utils/`` base in the analysis-tab layer for
#: rule 5. Deliberately narrower than the View/Controller layers above: the data plugin
#: bases (``MetaReader`` and its seven siblings) legitimately hold one another, so they
#: are not tab modules and rule 5 does not apply to them.
TAB_LAYER_SUFFIXES: Tuple[str, ...] = (
    "View.py",
    "Controller.py",
    "Model.py",
    "Controls.py",
)

ALLOWLIST_PATH = REPO_ROOT / ".mvc-boundary-allowlist.json"


def display(path: Path) -> str:
    """
    Render a path for the report, relative to the repository root where possible.

    :param path: the path to render
    :type path: Path
    :return: a repository-relative path, or the path unchanged if it lies outside
    :rtype: str
    """
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def is_global_signal_emit(node: ast.AST) -> bool:
    """
    Report whether a node is a ``<something>.global_signal.emit(...)`` call.

    Keyed on the receiver's name so that a different signal's ``emit`` does not
    count - the rule is about the plugin bus, not about Qt signals in general.

    :param node: the node to inspect
    :type node: ast.AST
    :return: True if the node is a call to emit on a global_signal attribute
    :rtype: bool
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "emit"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "global_signal"
    )


def forbidden_imports(tree: ast.Module) -> List[str]:
    """
    List every forbidden import statement, as the dotted module path it names.

    One entry per statement. A statement counts when its top-level package is
    forbidden, so a submodule of a forbidden package is forbidden too. Relative
    imports are skipped: they are in-package and cannot reach a third-party library.

    :param tree: the parsed module
    :type tree: ast.Module
    :return: the dotted module paths, sorted
    :rtype: List[str]
    """
    found: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module is None:
                continue
            if node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                found.append(node.module)
    return sorted(found)


def view_private_reads(tree: ast.Module) -> List[str]:
    """
    List every ``self.view._x`` access, by attribute name, one entry per site.

    Dunders are excluded - they are Python protocol rather than View internals.

    :param tree: the parsed module
    :type tree: ast.Module
    :return: the attribute names, one per access site, sorted
    :rtype: List[str]
    """
    found: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not node.attr.startswith("_") or node.attr.startswith("__"):
            continue
        receiver = node.value
        if (
            isinstance(receiver, ast.Attribute)
            and receiver.attr == "view"
            and isinstance(receiver.value, ast.Name)
            and receiver.value.id == "self"
        ):
            found.append(node.attr)
    return sorted(found)


def plugin_imports(tree: ast.Module) -> List[str]:
    """
    List every import of a plugin module, as the dotted path it names.

    :param tree: the parsed module
    :type tree: ast.Module
    :return: the dotted module paths, sorted
    :rtype: List[str]
    """
    found: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PLUGIN_PACKAGE):
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module is None:
                continue
            if node.module.startswith(PLUGIN_PACKAGE):
                found.append(node.module)
    return sorted(found)


def package_modules() -> List[Path]:
    """
    Every module under ``poriscope/``, excluding package ``__init__`` files.

    :return: the files, sorted
    :rtype: List[Path]
    """
    return [p for p in sorted(PORISCOPE.rglob("*.py")) if p.name != "__init__.py"]


def in_layer(path: Path, dirs: Tuple[str, ...], suffixes: Tuple[str, ...]) -> bool:
    """
    Report whether a module belongs to a layer, by directory or by filename.

    :param path: the module to classify
    :type path: Path
    :param dirs: repository-relative directories whose contents are all in the layer
    :type dirs: Tuple[str, ...]
    :param suffixes: filename suffixes that place a module in the layer anywhere
    :type suffixes: Tuple[str, ...]
    :return: True if the module belongs to the layer
    :rtype: bool
    """
    name = display(path)
    return name.startswith(tuple(f"{d}/" for d in dirs)) or name.endswith(suffixes)


def view_modules() -> List[Path]:
    """
    Every View-layer module rules 1 and 2 apply to.

    :return: the files, sorted
    :rtype: List[Path]
    """
    return [p for p in package_modules() if in_layer(p, VIEW_DIRS, VIEW_SUFFIXES)]


def controller_modules() -> List[Path]:
    """
    Every Controller-layer module rule 3 applies to.

    :return: the files, sorted
    :rtype: List[Path]
    """
    return [
        p
        for p in package_modules()
        if in_layer(p, CONTROLLER_DIRS, CONTROLLER_SUFFIXES)
    ]


def tab_layer_modules() -> List[Path]:
    """
    Every analysis-tab module rule 5 applies to.

    Everything under ``poriscope/plugins/analysistabs/``, plus the ``poriscope/utils/``
    bases those tabs inherit - which are named for their role, so the data plugin bases
    are correctly excluded.

    :return: the files, sorted
    :rtype: List[Path]
    """
    modules: List[Path] = []
    for path in package_modules():
        name = display(path)
        if name.startswith("poriscope/plugins/analysistabs/"):
            modules.append(path)
        elif name.startswith("poriscope/utils/Meta") and name.endswith(
            TAB_LAYER_SUFFIXES
        ):
            modules.append(path)
    return modules


def plugin_reaches(tree: ast.Module) -> List[str]:
    """
    List every way a module reaches a data plugin other than through ``call()``.

    Three shapes, one entry each. ``data_plugin_controller_signal`` is a different
    identifier and is not matched, and ``_plugin_instances`` is not matched either -
    that is the map ``call()`` itself reads, pushed in by ``MainController``.

    :param tree: the parsed module
    :type tree: ast.Module
    :return: one description per site, sorted
    :rtype: List[str]
    """
    found: List[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get_plugin_instance"
        ):
            found.append("get_plugin_instance")
        elif isinstance(node, ast.Attribute) and node.attr == "data_plugin_controller":
            found.append("data_plugin_controller")
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module is None:
                continue
            if _is_plugin_family_import(node.module):
                found.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_plugin_family_import(alias.name):
                    found.append(alias.name)
    return sorted(found)


def _is_plugin_family_import(module: str) -> bool:
    """
    Report whether a dotted path names a module inside a data plugin family.

    :param module: the dotted module path as written
    :type module: str
    :return: True if it lies under one of the eight families
    :rtype: bool
    """
    parts = module.split(".")
    return (
        len(parts) > 2
        and parts[0] == "poriscope"
        and parts[1] == "plugins"
        and parts[2] in PLUGIN_FAMILIES
    )


def shell_modules() -> List[Path]:
    """
    Every app-shell module the layering rule applies to.

    :return: the files, sorted
    :rtype: List[Path]
    """
    files: List[Path] = []
    for root in SHELL_ROOTS:
        files.extend(sorted((REPO_ROOT / root).rglob("*.py")))
    return [f for f in files if f.name != "__init__.py"]


def measure() -> Dict[str, Dict[str, object]]:
    """
    Measure all three rules across the Views and Controllers.

    :return: the per-file findings, grouped by rule
    :rtype: Dict[str, Dict[str, object]]
    :raises FileNotFoundError: if either layer scan comes back empty
    :raises SyntaxError: if a file cannot be parsed
    """
    emits: Dict[str, int] = {}
    imports: Dict[str, List[str]] = {}
    privates: Dict[str, List[str]] = {}

    views = view_modules()
    controllers = controller_modules()
    # A derived scan has no list to go stale, but it can go silently empty if a
    # directory is renamed - and an empty layer would read as a clean one.
    if not views:
        raise FileNotFoundError("the View layer scan matched no modules")
    if not controllers:
        raise FileNotFoundError("the Controller layer scan matched no modules")

    for path in views:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        name = display(path)
        emits[name] = sum(1 for node in ast.walk(tree) if is_global_signal_emit(node))
        imports[name] = forbidden_imports(tree)

    for path in controllers:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        privates[display(path)] = view_private_reads(tree)

    layering: Dict[str, List[str]] = {}
    for path in shell_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        found = plugin_imports(tree)
        if found:
            layering[display(path)] = found

    plugin_reach: Dict[str, List[str]] = {}
    tabs = tab_layer_modules()
    if not tabs:
        raise FileNotFoundError("the analysis-tab layer scan matched no modules")
    for path in tabs:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        found = plugin_reaches(tree)
        if found:
            plugin_reach[display(path)] = found

    return {
        "emits": emits,
        "imports": imports,
        "private_access": privates,
        "layering": layering,
        "plugin_reach": plugin_reach,
    }


def to_allowlist(results: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, object]]:
    """
    Reduce a measurement to the shape the allowlist file records.

    Emits and private accesses are counts; imports keep their dotted module paths,
    because the *identity* of the library is the interesting part and its list
    length is the statement count.

    :param results: a full measurement
    :type results: Dict[str, Dict[str, object]]
    :return: the allowlist-shaped mapping
    :rtype: Dict[str, Dict[str, object]]
    """
    emits: Dict[str, int] = results["emits"]  # type: ignore[assignment]
    imports: Dict[str, List[str]] = results["imports"]  # type: ignore[assignment]
    privates: Dict[str, List[str]] = results["private_access"]  # type: ignore[assignment]
    layering: Dict[str, List[str]] = results["layering"]  # type: ignore[assignment]
    reach: Dict[str, List[str]] = results["plugin_reach"]  # type: ignore[assignment]
    return {
        "emits": {name: count for name, count in sorted(emits.items()) if count},
        "imports": {name: names for name, names in sorted(imports.items()) if names},
        "private_access": {
            name: len(names) for name, names in sorted(privates.items()) if names
        },
        "layering": {name: names for name, names in sorted(layering.items()) if names},
        "plugin_reach": {name: names for name, names in sorted(reach.items()) if names},
    }


def total(allowlist: Dict[str, Dict[str, object]]) -> int:
    """
    Total the allowlist: the single number the refactor drives to zero.

    :param allowlist: an allowlist-shaped mapping
    :type allowlist: Dict[str, Dict[str, object]]
    :return: emits plus forbidden import statements plus private-access sites
    :rtype: int
    """
    emits = sum(int(v) for v in allowlist.get("emits", {}).values())
    imports = sum(len(v) for v in allowlist.get("imports", {}).values())  # type: ignore[arg-type]
    privates = sum(int(v) for v in allowlist.get("private_access", {}).values())
    layering = sum(len(v) for v in allowlist.get("layering", {}).values())  # type: ignore[arg-type]
    reach = sum(len(v) for v in allowlist.get("plugin_reach", {}).values())  # type: ignore[arg-type]
    return emits + imports + privates + layering + reach


def distinct_pairs(allowlist: Dict[str, Dict[str, object]]) -> int:
    """
    Count distinct (View, top-level module) pairs, reported for context only.

    This is the smaller figure that an earlier count conflated with the statement
    count. It is not what the allowlist totals.

    :param allowlist: an allowlist-shaped mapping
    :type allowlist: Dict[str, Dict[str, object]]
    :return: the number of distinct View-and-package pairs
    :rtype: int
    """
    pairs = set()
    for name, modules in allowlist.get("imports", {}).items():
        for module in modules:  # type: ignore[union-attr]
            pairs.add((name, str(module).split(".")[0]))
    return len(pairs)


def load_allowlist() -> Dict[str, Dict[str, object]]:
    """
    Read the checked-in allowlist.

    :return: the recorded allowlist
    :rtype: Dict[str, Dict[str, object]]
    :raises FileNotFoundError: if the allowlist has not been written yet
    """
    if not ALLOWLIST_PATH.is_file():
        raise FileNotFoundError(
            f"{display(ALLOWLIST_PATH)} does not exist; run this script with --update"
        )
    loaded: Dict[str, Dict[str, object]] = json.loads(
        ALLOWLIST_PATH.read_text(encoding="utf-8")
    )
    return loaded


def compare(
    current: Dict[str, Dict[str, object]], allowed: Dict[str, Dict[str, object]]
) -> List[str]:
    """
    Report every way the measurement disagrees with the allowlist.

    :param current: the measurement just taken
    :type current: Dict[str, Dict[str, object]]
    :param allowed: the checked-in allowlist
    :type allowed: Dict[str, Dict[str, object]]
    :return: one human-readable message per disagreement, empty if they match
    :rtype: List[str]
    """
    problems: List[str] = []
    for rule in ("emits", "imports", "private_access", "layering", "plugin_reach"):
        now = current.get(rule, {})
        was = allowed.get(rule, {})
        for name in sorted(set(now) | set(was)):
            if now.get(name) == was.get(name):
                continue
            if name not in was:
                problems.append(
                    f"{rule}: {name} is not on the allowlist at all - "
                    f"a new violation was introduced ({now[name]!r})"
                )
            elif name not in now:
                problems.append(
                    f"{rule}: {name} is clean now but still on the allowlist "
                    f"({was[name]!r}) - record the win with --update"
                )
            else:
                problems.append(
                    f"{rule}: {name} was {was[name]!r}, is now {now[name]!r}"
                )
    return problems


def report(results: Dict[str, Dict[str, object]], verbose: bool) -> None:
    """
    Print the current state of each rule and the allowlist total.

    :param results: a full measurement
    :type results: Dict[str, Dict[str, object]]
    :param verbose: whether to name every import and private attribute
    :type verbose: bool
    :return: None
    :rtype: None
    """
    allowlist = to_allowlist(results)

    emits: Dict[str, int] = allowlist["emits"]  # type: ignore[assignment]
    imports: Dict[str, List[str]] = allowlist["imports"]  # type: ignore[assignment]
    privates: Dict[str, int] = allowlist["private_access"]  # type: ignore[assignment]

    print("1. global_signal.emit in a View")
    for name, count in emits.items():
        print(f"     {count:>3}  {name}")
    print(f"     {sum(emits.values()):>3}  total")

    print("\n2. Forbidden imports in a View (one entry per import statement)")
    for name, modules in imports.items():
        detail = f"  {', '.join(modules)}" if verbose else ""
        print(f"     {len(modules):>3}  {name}{detail}")
    print(f"     {sum(len(m) for m in imports.values()):>3}  total")

    print("\n3. Controller reading a View private")
    raw: Dict[str, List[str]] = results["private_access"]  # type: ignore[assignment]
    for name, count in privates.items():
        detail = f"  {', '.join(sorted(set(raw[name])))}" if verbose else ""
        print(f"     {count:>3}  {name}{detail}")
    print(f"     {sum(privates.values()):>3}  total")

    print("\n4. App-shell module importing from a plugin package")
    layering_rule: Dict[str, List[str]] = allowlist["layering"]  # type: ignore[assignment]
    for name, modules in layering_rule.items():
        detail = f"  {', '.join(modules)}" if verbose else ""
        print(f"     {len(modules):>3}  {name}{detail}")
    print(f"     {sum(len(m) for m in layering_rule.values()):>3}  total")

    print("\n5. Analysis-tab module reaching a data plugin outside call()")
    reach_rule: Dict[str, List[str]] = allowlist["plugin_reach"]  # type: ignore[assignment]
    for name, sites in reach_rule.items():
        detail = f"  {', '.join(sites)}" if verbose else ""
        print(f"     {len(sites):>3}  {name}{detail}")
    print(f"     {sum(len(s) for s in reach_rule.values()):>3}  total")

    print(
        f"\nAllowlist total: {total(allowlist)} "
        f"({distinct_pairs(allowlist)} distinct View x package pairs). Target: 0."
    )


def main(argv: List[str]) -> int:
    """
    Measure the boundary and report, update the allowlist, or check against it.

    :param argv: command-line arguments, excluding the program name
    :type argv: List[str]
    :return: 0 on success, 1 if --check disagreed or a file could not be read
    :rtype: int
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="name every forbidden import and private attribute",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="write the measurement to .mvc-boundary-allowlist.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the measurement disagrees with the allowlist",
    )
    args = parser.parse_args(argv)

    try:
        results = measure()
    except (FileNotFoundError, SyntaxError, OSError) as exc:
        print(f"Measurement failed: {exc}", file=sys.stderr)
        return 1

    report(results, args.verbose)

    if args.update:
        ALLOWLIST_PATH.write_text(
            json.dumps(to_allowlist(results), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote {display(ALLOWLIST_PATH)}.")

    if args.check:
        try:
            allowed = load_allowlist()
        except (FileNotFoundError, ValueError) as exc:
            print(f"\nAllowlist could not be read: {exc}", file=sys.stderr)
            return 1
        problems = compare(to_allowlist(results), allowed)
        if problems:
            print(f"\n{len(problems)} disagreement(s) with the allowlist:")
            for problem in problems:
                print(f"       {problem}")
            return 1
        print("\nMatches the allowlist.")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
