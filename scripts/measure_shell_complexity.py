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
Measure cyclomatic complexity across the nine app-shell files.

    python scripts/measure_shell_complexity.py [--verbose] [--update] [--check]

Step 5c restructures the app shell, and nothing measured it. ``check_mvc_boundary.py``
reads 0 on all three of its rules over these files, and no duplication family covers
them, so the shell could be restructured in either direction unobserved. This is the
instrument, built before the work it would measure (method rule 24).

**The shell is measured in complexity, not in lines.** ``DECISIONS.md`` 2026-09-20
records why: ``settings_window.py`` has *zero* functions over the threshold despite
890 lines, and ``main_view.py`` has two despite 1,235 - their length is flat Qt widget
construction that a 2026-08 audit already reviewed with no findings. Driving those line
counts down would chase a number that does not describe a problem.

**The rule, stated exactly, because the definition is the number.**

A function starts at 1 and gains a point for each of:

- ``if`` - and therefore each ``elif``, which parses as a nested ``if``. ``else``
  adds nothing; it is the far side of a decision already counted.
- ``for``, ``async for``, ``while``.
- each ``except`` handler. The ``try`` itself is not a branch, and neither is
  ``finally``.
- an inline conditional, ``a if c else b``.
- each short-circuit in a boolean operator: ``a and b and c`` adds **two**, not one.
- each generator in a comprehension, plus each ``if`` filtering it. Set, dict and
  generator forms all count as the list form does.
- each ``case`` of a ``match``.

**Three constructs deliberately do not count, and the choices are load-bearing.**

- ``with`` **is not a branch.** An earlier ad-hoc measurement counted it, which scores
  a function worse for using a context manager - directly against this project's rule
  that database resources are closed explicitly. It inflated
  ``create_appdata_folders`` from 17 to 20 on its four ``with`` blocks alone, and it
  held ``main_view.py::remove_pages_except`` at exactly 10, hiding it under the
  threshold rather than judging it. Excluding ``with`` is why the recorded baseline
  moved from 7 functions / 110 to **8 / 121**.
- ``assert`` is excluded, so a debug check cannot push a function over the gate. No
  scoped function has one today, so this is the simpler rule rather than a measured
  choice.
- ``return``, ``break`` and ``continue`` are excluded. The path that reaches one was
  already counted by whatever decided to take it, and counting both would double-count
  every guard clause - which is exactly the shape Step 5c extracts.

**What counts as a function.** Module-level functions and methods of module-level
classes. A function nested inside another is scored *within* its parent and not
reported separately, because reading the parent means reading it; reporting both would
count its branches twice in the total. This matches ``measure_duplication.py``, so the
two instruments agree on what a function is.

**What the baseline records.** Per file: how many functions were scanned, how many
exceed the threshold, and the summed complexity of those that do. The total is the
weight of the problem rather than the weight of the file - summing every function would
move on any edit anywhere and stop reading as "how much is left to do". The
per-function detail is left out of the baseline on purpose: useful to read under
``--verbose``, useless to diff, and it would churn on every rename.

**The scope is nine files, not the repository.** Repo-wide, 124 functions exceed 80
lines, most of them in owner-held fitters and in the ``setupUi`` methods the plan keeps
per-tab, so a repo-wide gate would fail on commits that are not ours to gate (rule 18).
The list is explicit rather than globbed, and two guards keep it honest: every named
file must exist, and ``poriscope/controllers/`` and ``poriscope/models/`` must contain
nothing that is not named. That second guard is the one Step 5c needs - splitting a
god-method into a new module in the same package would otherwise take its complexity
out of sight and read as a win. It cannot cover ``poriscope/views/``, which holds
unscoped modules alongside ``main_view.py`` and ``settings_window.py``; an extraction
into a *new* file there would escape the gate, and must be added to ``SHELL_FILES`` by
hand.

Exits 1 under ``--check`` if the measurement disagrees with
``.shell-complexity-baseline.json``, in **either** direction. Going up is a regression.
Going down is a win that has to be recorded in the same commit that earned it -
otherwise the baseline overstates the complexity left and the slack accrues silently.
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The app shell, enumerated rather than globbed and given as repository-relative
#: paths: the two controller and two model modules with their package ``__init__``
#: files, the two large views, and the application entry point. Nine files, 189
#: functions, which is the scope ``DECISIONS.md`` 2026-09-20 records.
#:
#: The ``__init__.py`` files carry no functions today. They are listed anyway, because
#: the scope is *the package*, and a helper dropped into one of them would otherwise be
#: unmeasured - the same reasoning that added ``multiselect_base.py`` to the duplication
#: measurer before it had anything in it.
#:
#: Nothing under ``poriscope/plugins/`` belongs here. The plugin tree is measured by
#: ``measure_duplication.py``, and much of it is owner-held.
SHELL_FILES: Tuple[str, ...] = (
    "poriscope/controllers/__init__.py",
    "poriscope/controllers/DataPluginController.py",
    "poriscope/controllers/main_controller.py",
    "poriscope/models/__init__.py",
    "poriscope/models/DataPluginModel.py",
    "poriscope/models/main_model.py",
    "poriscope/main_app.py",
    "poriscope/views/main_view.py",
    "poriscope/views/settings_window.py",
)

#: Packages that must be enumerated completely by ``SHELL_FILES``. A new module here
#: fails the guard until it is listed, which is what stops an extraction from carrying
#: complexity out of the gate's sight. ``poriscope/views/`` cannot be swept this way -
#: it holds modules that are deliberately out of scope.
SCOPED_PACKAGES: Tuple[str, ...] = (
    "poriscope/controllers",
    "poriscope/models",
)

#: Functions are recorded when their complexity is **strictly above** this. Ten is the
#: conventional line between "follow it by reading" and "follow it by tracing", and it
#: is the threshold the 2026-09-20 scoping decision measured against.
THRESHOLD = 10

BASELINE_PATH = REPO_ROOT / ".shell-complexity-baseline.json"

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)

#: Nodes worth exactly one point each. ``With`` and ``Try`` are deliberately absent;
#: see the module docstring.
SINGLE_POINT_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.IfExp,
)

COMPREHENSION_NODES = (
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


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


def complexity(node: ast.AST) -> int:
    """
    Compute one function's cyclomatic complexity under the rule in the module docstring.

    The walk descends into nested functions on purpose: a closure's branches are part
    of what reading its parent costs.

    :param node: the function node to measure
    :type node: ast.AST
    :return: the function's cyclomatic complexity, at least 1
    :rtype: int
    """
    score = 1
    for child in ast.walk(node):
        if isinstance(child, SINGLE_POINT_NODES):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += len(child.values) - 1
        elif isinstance(child, COMPREHENSION_NODES):
            score += sum(1 + len(gen.ifs) for gen in child.generators)
        elif isinstance(child, ast.Match):
            score += len(child.cases)
    return score


def collect_nodes(source: str, filename: str) -> List[Tuple[str, ast.AST]]:
    """
    Collect every module-level function and method of a module-level class, as nodes.

    :param source: the file's text
    :type source: str
    :param filename: the name to attribute syntax errors to
    :type filename: str
    :return: one (qualified name, node) pair per function, in source order
    :rtype: List[Tuple[str, ast.AST]]
    :raises SyntaxError: if the source cannot be parsed
    """
    tree = ast.parse(source, filename=filename)

    found: List[Tuple[str, ast.AST]] = []
    for node in tree.body:
        if isinstance(node, FUNCTION_NODES):
            found.append((node.name, node))
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, FUNCTION_NODES):
                    found.append((f"{node.name}.{child.name}", child))
    return found


def collect_functions(source: str, filename: str) -> List[Tuple[str, int]]:
    """
    Score every function in one module's text.

    :param source: the file's text
    :type source: str
    :param filename: the name to attribute syntax errors to
    :type filename: str
    :return: one (qualified name, complexity) pair per function, in source order
    :rtype: List[Tuple[str, int]]
    :raises SyntaxError: if the source cannot be parsed
    """
    return [(name, complexity(node)) for name, node in collect_nodes(source, filename)]


def measure_source(source: str, filename: str) -> Dict[str, object]:
    """
    Measure one module's text: how many functions, how many over the threshold, how heavy.

    :param source: the file's text
    :type source: str
    :param filename: the name to attribute syntax errors to
    :type filename: str
    :return: the file's counts plus its over-threshold functions, heaviest first
    :rtype: Dict[str, object]
    :raises SyntaxError: if the source cannot be parsed
    """
    over: List[Dict[str, object]] = []
    total_functions = 0

    for name, node in collect_nodes(source, filename):
        total_functions += 1
        score = complexity(node)
        if score <= THRESHOLD:
            continue
        start = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", start)
        over.append({"name": name, "complexity": score, "lines": end - start + 1})

    over.sort(key=lambda entry: (-int(entry["complexity"]), str(entry["name"])))

    return {
        "functions": total_functions,
        "over_threshold": len(over),
        "total_complexity": sum(int(entry["complexity"]) for entry in over),
        "over": over,
    }


def measure() -> Dict[str, Dict[str, object]]:
    """
    Measure every shell file.

    :return: one entry per file, keyed by its repository-relative path
    :rtype: Dict[str, Dict[str, object]]
    :raises FileNotFoundError: if a file named in SHELL_FILES does not exist
    """
    results: Dict[str, Dict[str, object]] = {}
    for name in SHELL_FILES:
        path = REPO_ROOT / name
        if not path.is_file():
            raise FileNotFoundError(
                f"{name} is named in SHELL_FILES but does not exist; "
                f"the file list is deliberately explicit, so update it"
            )
        results[name] = measure_source(path.read_text(encoding="utf-8"), name)
    return results


def unlisted_scoped_files() -> List[str]:
    """
    Find modules sitting in a scoped package that ``SHELL_FILES`` does not name.

    A method extracted into a new module in ``controllers/`` or ``models/`` would
    otherwise take its complexity out of the gate's sight and read as a win.

    :return: the repository-relative paths that should be listed but are not
    :rtype: List[str]
    """
    listed = set(SHELL_FILES)
    missing = []
    for package in SCOPED_PACKAGES:
        for path in sorted((REPO_ROOT / package).glob("*.py")):
            name = display(path)
            if name not in listed:
                missing.append(name)
    return missing


def to_baseline(
    results: Dict[str, Dict[str, object]],
) -> Dict[str, Dict[str, int]]:
    """
    Reduce a measurement to the counts the baseline file records.

    The per-function detail is deliberately left out: it is useful to read and useless
    to diff, and it would churn the baseline on every rename.

    :param results: a full measurement
    :type results: Dict[str, Dict[str, object]]
    :return: per-file counts only
    :rtype: Dict[str, Dict[str, int]]
    """
    return {
        name: {
            "functions": int(data["functions"]),
            "over_threshold": int(data["over_threshold"]),
            "total_complexity": int(data["total_complexity"]),
        }
        for name, data in results.items()
    }


def load_baseline() -> Dict[str, Dict[str, int]]:
    """
    Read the checked-in baseline.

    :return: the recorded per-file counts
    :rtype: Dict[str, Dict[str, int]]
    :raises FileNotFoundError: if the baseline has not been written yet
    """
    if not BASELINE_PATH.is_file():
        raise FileNotFoundError(
            f"{display(BASELINE_PATH)} does not exist; run this script with --update"
        )
    loaded: Dict[str, Dict[str, int]] = json.loads(
        BASELINE_PATH.read_text(encoding="utf-8")
    )
    return loaded


def compare(
    current: Dict[str, Dict[str, int]], baseline: Dict[str, Dict[str, int]]
) -> List[str]:
    """
    Report every way the current measurement disagrees with the baseline.

    :param current: the measurement just taken
    :type current: Dict[str, Dict[str, int]]
    :param baseline: the checked-in counts
    :type baseline: Dict[str, Dict[str, int]]
    :return: one human-readable message per disagreement, empty if they match
    :rtype: List[str]
    """
    problems = []
    for name in sorted(set(current) | set(baseline)):
        if name not in baseline:
            problems.append(f"{name}: measured but absent from the baseline")
            continue
        if name not in current:
            problems.append(f"{name}: in the baseline but no longer measured")
            continue
        for key in sorted(set(current[name]) | set(baseline[name])):
            was = baseline[name].get(key)
            now = current[name].get(key)
            if was == now:
                continue
            if was is None or now is None:
                problems.append(f"{name}.{key}: baseline {was!r}, measured {now!r}")
            elif key == "functions":
                # A changing function count is not itself good or bad: extracting a
                # helper raises it and that is the point, deleting dead code lowers
                # it. Only `_escape_warning` below can tell the dangerous case apart,
                # so say plainly what moved rather than calling it a regression.
                direction = "gained" if now > was else "lost"
                problems.append(
                    f"{name}.{key}: {was} -> {now}, the file {direction} functions - "
                    f"expected when a method is split or removed; rerun with --update "
                    f"in the same commit to record it"
                )
            elif now > was:
                problems.append(
                    f"{name}.{key}: rose from {was} to {now} - complexity was added"
                )
            else:
                problems.append(
                    f"{name}.{key}: fell from {was} to {now} - record the win by "
                    f"rerunning with --update in the same commit"
                )

        problems.extend(_escape_warning(name, current, baseline))
    return problems


def _escape_warning(
    name: str,
    current: Dict[str, Dict[str, int]],
    baseline: Dict[str, Dict[str, int]],
) -> List[str]:
    """
    Warn when complexity fell but the file lost functions rather than gaining them.

    A genuine split leaves every piece in the file, so its function count *rises* while
    its complexity falls. Complexity and function count falling together is the other
    shape: a method moved out to a module the file list does not name, which reads as
    progress here while the code is untouched.

    :param name: the file being reported on
    :type name: str
    :param current: the measurement just taken
    :type current: Dict[str, Dict[str, int]]
    :param baseline: the checked-in counts
    :type baseline: Dict[str, Dict[str, int]]
    :return: at most one warning, empty if the shape does not match
    :rtype: List[str]
    """
    if name not in current or name not in baseline:
        return []

    complexity_fell = current[name].get("total_complexity", 0) < baseline[name].get(
        "total_complexity", 0
    )
    functions_fell = current[name].get("functions", 0) < baseline[name].get(
        "functions", 0
    )
    if complexity_fell and functions_fell:
        return [
            f"{name}: complexity fell but the file lost functions, so some of it may "
            f"have left the measured scope rather than being reduced. A real split "
            f"leaves the pieces in the file and raises its function count. Check that "
            f"nothing moved into a module SHELL_FILES does not name before running "
            f"--update."
        ]
    return []


def report(results: Dict[str, Dict[str, object]], verbose: bool) -> None:
    """
    Print the measurement as a table, optionally with each over-threshold function.

    :param results: a full measurement
    :type results: Dict[str, Dict[str, object]]
    :param verbose: whether to list the over-threshold functions under each file
    :type verbose: bool
    :return: None
    :rtype: None
    """
    width = max(len(name) for name in results) + 2
    header = f"{'file':<{width}}{'functions':>11}{'over ' + str(THRESHOLD):>10}{'complexity':>12}"
    print(header)
    print("-" * len(header))

    totals = [0, 0, 0]
    for name, data in results.items():
        row = [
            int(data["functions"]),
            int(data["over_threshold"]),
            int(data["total_complexity"]),
        ]
        totals = [a + b for a, b in zip(totals, row, strict=True)]
        print(f"{name:<{width}}{row[0]:>11}{row[1]:>10}{row[2]:>12}")

        if verbose:
            over: List[Dict[str, object]] = data["over"]  # type: ignore[assignment]
            for entry in over:
                print(
                    f"    cx {entry['complexity']:>3}  "
                    f"{entry['lines']:>4} lines  {entry['name']}"
                )

    print("-" * len(header))
    print(f"{'total':<{width}}{totals[0]:>11}{totals[1]:>10}{totals[2]:>12}")


def main(argv: List[str]) -> int:
    """
    Measure the shell files and report, update the baseline, or check against it.

    :param argv: command-line arguments, excluding the program name
    :type argv: List[str]
    :return: 0 on success, 1 if --check found a disagreement or a file is missing
    :rtype: int
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="list every function over the threshold, heaviest first",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="write the measurement to .shell-complexity-baseline.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the measurement disagrees with the baseline",
    )
    args = parser.parse_args(argv)

    try:
        results = measure()
    except (FileNotFoundError, SyntaxError, OSError) as exc:
        print(f"Measurement failed: {exc}", file=sys.stderr)
        return 1

    report(results, args.verbose)

    unlisted = unlisted_scoped_files()
    if unlisted:
        print(
            f"\n{len(unlisted)} module(s) in a scoped package are not in SHELL_FILES, "
            f"so their complexity is unmeasured:"
        )
        for name in unlisted:
            print(f"       {name}")

    if args.update:
        BASELINE_PATH.write_text(
            json.dumps(to_baseline(results), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote {display(BASELINE_PATH)}.")

    if args.check:
        if unlisted:
            return 1
        try:
            baseline = load_baseline()
        except (FileNotFoundError, ValueError) as exc:
            print(f"\nBaseline could not be read: {exc}", file=sys.stderr)
            return 1
        problems = compare(to_baseline(results), baseline)
        if problems:
            print(f"\n{len(problems)} disagreement(s) with the baseline:")
            for problem in problems:
                print(f"       {problem}")
            return 1
        print("\nMatches the baseline.")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
