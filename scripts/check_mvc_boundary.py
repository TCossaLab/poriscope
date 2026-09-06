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
   importing ``poriscope.plugins.analysistabs.utils.walkthrough`` is a layering
   inversion: the shell depends on a plugin. Step 3f fixes it by moving those two
   modules into ``views/widgets/``, and without this rule nothing would observe
   that the step had finished. Added by the Step 2 exit review.

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
TABS = REPO_ROOT / "poriscope" / "plugins" / "analysistabs"

VIEWS: Tuple[str, ...] = (
    "ClusteringView.py",
    "EventAnalysisView.py",
    "MetadataView.py",
    "ProteinView.py",
    "RawDataView.py",
)

CONTROLLERS: Tuple[str, ...] = (
    "ClusteringController.py",
    "EventAnalysisController.py",
    "MetadataController.py",
    "ProteinController.py",
    "RawDataController.py",
)

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
    :raises FileNotFoundError: if a file named in VIEWS or CONTROLLERS is missing
    :raises SyntaxError: if a file cannot be parsed
    """
    emits: Dict[str, int] = {}
    imports: Dict[str, List[str]] = {}
    privates: Dict[str, List[str]] = {}

    for name in VIEWS:
        path = TABS / name
        if not path.is_file():
            raise FileNotFoundError(f"{display(path)} is named in VIEWS but is missing")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        emits[name] = sum(1 for node in ast.walk(tree) if is_global_signal_emit(node))
        imports[name] = forbidden_imports(tree)

    for name in CONTROLLERS:
        path = TABS / name
        if not path.is_file():
            raise FileNotFoundError(
                f"{display(path)} is named in CONTROLLERS but is missing"
            )
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        privates[name] = view_private_reads(tree)

    layering: Dict[str, List[str]] = {}
    for path in shell_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        found = plugin_imports(tree)
        if found:
            layering[display(path)] = found

    return {
        "emits": emits,
        "imports": imports,
        "private_access": privates,
        "layering": layering,
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
    return {
        "emits": {name: count for name, count in sorted(emits.items()) if count},
        "imports": {name: names for name, names in sorted(imports.items()) if names},
        "private_access": {
            name: len(names) for name, names in sorted(privates.items()) if names
        },
        "layering": {name: names for name, names in sorted(layering.items()) if names},
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
    return emits + imports + privates + layering


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
    for rule in ("emits", "imports", "private_access", "layering"):
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
