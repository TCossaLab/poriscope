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
Report which methods the 2.0.0 refactor moves or deduplicates are not pinned by tests.

    pytest --cov=poriscope --cov-report=json:coverage.json
    python scripts/check_refactor_coverage.py [--coverage coverage.json] [--verbose]

The standing criterion for the refactor's safety net is that **every method the
refactor moves or deduplicates must be covered**. The set is therefore derived
from the refactor's own lists, not from a judgement about which methods look
under-tested - that judgement is what left ``_gaussian_fit`` unpinned while it
carried a comment calling itself "THE CRITICAL MATH FIX".

**Two signals, because neither alone is sufficient.**

- *Executed* comes from ``coverage.py``: did the method's body actually run during
  the suite? This is what catches a method that every test replaces with a
  ``Mock`` - its lines never execute, however many times its name appears.
- *Targeted* comes from an AST scan of ``tests/``: does any test call the method
  directly, as opposed to merely running it in passing? A method exercised only
  through a click-driven e2e flow executes, but nothing asserts what it returned.

``_logscale_and_filter_multiple_columns`` is why both are needed. It had 38
references in ``tests/``; every one replaced it with a ``Mock``, so a reference
count called it well covered while its body had no behavioural coverage at all.
Counting call sites is not measuring coverage.

**Line coverage percentages are deliberately not used.** The five analysis-tab
Views were at 87-91% before any characterization test existed, and adding them
moved the numbers by at most one point, because those lines already executed under
the e2e suite with nothing asserting the values they produced. "Executed" and
"pinned" are different properties, and only the per-method pair above distinguishes
them.

**What each verdict does and does not prove.** ``UNTESTED`` is definitive: the body
never ran, so nothing can be asserting it. ``RUNS ONLY`` is definitive in the other
direction: the body ran but no test names it, so it is exercised in passing - almost
always by a click-driven e2e flow - and nothing checks what it produced.

``PINNED`` is the weak one, and deliberately so. The targeted signal is syntactic,
so a call on a ``MagicMock`` reads the same as a call on a real instance; a method
can therefore be marked pinned on the strength of a call that exercised a mock while
its body happened to run somewhere else. **Treat the pinned rows as a list to review
rather than a guarantee**, and read the ``patch`` column beside them: a target with
many substitutions and few direct calls is the shape
``_logscale_and_filter_multiple_columns`` had. Distinguishing the two properly needs
per-test coverage attribution, which is far more machinery than this is worth today;
if it ever becomes worth it, the cheap approximation is a second coverage run under
``-m "not e2e"`` and treating "executed without e2e" as the targeted signal.

Exits 1 on any ``UNTESTED``, ``NOT FOUND`` or ``MISSING FILE`` target, which are the
unambiguous failures. ``RUNS ONLY`` is reported and does not fail, because a method
whose only sensible exercise is an end-to-end flow is a judgement call rather than a
defect.
"""

import argparse
import ast
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
TABS = REPO_ROOT / "poriscope" / "plugins" / "analysistabs"
TESTS = REPO_ROOT / "tests"

#: Methods named explicitly by a refactor step, with the step recorded so a reader
#: can trace each back to `refactor_2.0.0.md`. The deduplicated set is derived
#: rather than listed - see `deduplicated_targets` - and so are the emit-bearing and
#: SQL-authoring methods, which the steps describe by property rather than by name.
MOVED: Tuple[Tuple[str, str, str], ...] = (
    # Step 3d - MetaView -> MetaModel
    ("poriscope/utils/MetaView.py", "_logscale_and_filter_multiple_columns", "3d"),
    ("poriscope/utils/MetaView.py", "_logscale_and_filter_dataframe", "3d"),
    ("poriscope/utils/MetaView.py", "_parse_event_indices", "3d"),
    ("poriscope/utils/MetaView.py", "_shift_ranges", "3d"),
    ("poriscope/utils/MetaView.py", "_merge_ranges", "3d"),
    ("poriscope/utils/MetaView.py", "_format_ranges", "3d"),
    ("poriscope/utils/MetaView.py", "_expand_event_indices", "3d"),
    # Step 3e - tab-specific leakage out of the bases
    ("poriscope/utils/MetaView.py", "set_column_exists", "3e"),
    ("poriscope/utils/MetaController.py", "check_column_exists", "3e"),
    # Step 4c - scientific computation out of the widgets
    (
        "poriscope/plugins/analysistabs/ClusteringView.py",
        "_normalize_column_data",
        "4c",
    ),
    (
        "poriscope/plugins/analysistabs/ClusteringView.py",
        "_update_clusters_hdbscan",
        "4c",
    ),
    ("poriscope/plugins/analysistabs/MetadataView.py", "_calculate_heatmap", "4c"),
    (
        "poriscope/plugins/analysistabs/MetadataView.py",
        "_construct_all_points_histogram",
        "4c",
    ),
    ("poriscope/plugins/analysistabs/MetadataView.py", "is_categorical_type", "4c"),
    ("poriscope/plugins/analysistabs/MetadataView.py", "format_axis_label", "4c"),
    ("poriscope/plugins/analysistabs/ProteinView.py", "_double_gaussian", "4c"),
    ("poriscope/plugins/analysistabs/ProteinView.py", "_fit_double_gaussian", "4c"),
    (
        "poriscope/plugins/analysistabs/ProteinView.py",
        "_fit_and_sanity_check_double_gaussian",
        "4c",
    ),
    (
        "poriscope/plugins/analysistabs/ProteinView.py",
        "_compute_theoretical_blockages",
        "4c",
    ),
    ("poriscope/plugins/analysistabs/ProteinView.py", "_generate_vm_ensemble", "4c"),
    ("poriscope/plugins/analysistabs/ProteinView.py", "_summarize_vm", "4c"),
    (
        "poriscope/plugins/analysistabs/ProteinView.py",
        "_construct_single_event_histogram",
        "4c",
    ),
    (
        "poriscope/plugins/analysistabs/ProteinView.py",
        "_construct_all_points_histogram",
        "4c",
    ),
    (
        "poriscope/plugins/analysistabs/ProteinView.py",
        "_fit_and_plot_ensemble_geometry",
        "4c",
    ),
    ("poriscope/plugins/analysistabs/RawDataView.py", "_get_baseline_stats", "4c"),
    ("poriscope/plugins/analysistabs/RawDataView.py", "_gaussian", "4c"),
    ("poriscope/plugins/analysistabs/RawDataView.py", "_gaussian_fit", "4c"),
    # Step 4e - file I/O to the Model, dialog selection left in the View
    ("poriscope/plugins/analysistabs/MetadataView.py", "_export_csv_subset", "4e"),
)

VIEW_FILES: Tuple[str, ...] = (
    "ClusteringView.py",
    "EventAnalysisView.py",
    "MetadataView.py",
    "ProteinView.py",
    "RawDataView.py",
)

#: Assertion helpers that read like a call on the method but are not one:
#: `view.method.assert_called_once()` walks as an attribute access on the method,
#: never as a call to it, but `mock.assert_called_with(...)` is a Call whose attr
#: would otherwise be counted if a target shared the name.
MOCK_ASSERTIONS: Set[str] = {
    "assert_called",
    "assert_called_once",
    "assert_called_once_with",
    "assert_called_with",
    "assert_any_call",
    "assert_has_calls",
    "assert_not_called",
}


def display(path: Path) -> str:
    """
    Render a path relative to the repository root, with forward slashes.

    :param path: the path to render
    :type path: Path
    :return: a repository-relative path
    :rtype: str
    """
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def method_line_ranges(source_path: Path) -> Dict[str, List[Tuple[int, int]]]:
    """
    Map each method name in a module to the line ranges of its definitions.

    A name can appear more than once - two classes in one module, or an override -
    so every definition is recorded and the method counts as executed if any of
    them ran.

    :param source_path: the module to scan
    :type source_path: Path
    :return: method name to a list of (first line, last line) pairs
    :rtype: Dict[str, List[Tuple[int, int]]]
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    ranges: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = node.end_lineno if node.end_lineno is not None else node.lineno
            ranges[node.name].append((node.lineno, end))
    return ranges


def emit_bearing_methods() -> List[Tuple[str, str, str]]:
    """
    Find every View method containing a ``global_signal.emit`` call.

    Step 4a turns each of these into a call on the Model, so each is a moved
    method. Derived rather than listed because the step describes them by property.

    :return: (file, method, step) triples
    :rtype: List[Tuple[str, str, str]]
    """
    found: List[Tuple[str, str, str]] = []
    for name in VIEW_FILES:
        path = TABS / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "emit"
                    and isinstance(child.func.value, ast.Attribute)
                    and child.func.value.attr == "global_signal"
                ):
                    found.append((f"{display(path)}", node.name, "4a"))
                    break
    return found


def sql_authoring_methods() -> List[Tuple[str, str, str]]:
    """
    Find every View method that builds SQL as a string.

    Step 4b moves these to the loader. Detected by an f-string or a plain string
    containing a SELECT, an ALTER TABLE or a DELETE FROM.

    :return: (file, method, step) triples
    :rtype: List[Tuple[str, str, str]]
    """
    markers = ("SELECT ", "ALTER TABLE", "DELETE FROM")
    found: List[Tuple[str, str, str]] = []
    for name in VIEW_FILES:
        path = TABS / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(node):
                text: Optional[str] = None
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    text = child.value
                if text and any(marker in text for marker in markers):
                    found.append((f"{display(path)}", node.name, "4b"))
                    break
    return found


def deduplicated_targets() -> List[Tuple[str, str, str]]:
    """
    Find every method the duplication measure reports as a cross-file duplicate.

    Step 3 promotes these to a shared base, deleting the copies, so each needs its
    behaviour pinned before the copies can be merged. Derived from
    ``scripts/measure_duplication.py`` so the two instruments cannot disagree.

    :return: (file, method, step) triples
    :rtype: List[Tuple[str, str, str]]
    :raises FileNotFoundError: if the duplication measure cannot be loaded
    """
    spec = importlib.util.spec_from_file_location(
        "measure_duplication", REPO_ROOT / "scripts" / "measure_duplication.py"
    )
    if spec is None or spec.loader is None:
        raise FileNotFoundError("scripts/measure_duplication.py could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    found: List[Tuple[str, str, str]] = []
    for data in module.measure().values():
        for group in data["groups"]:
            for qualified in group["names"]:
                method = str(qualified).split(".")[-1]
                found.append(("", method, "3-dedup"))
    return found


def count_test_calls(
    root: Optional[Path] = None,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Count direct calls and mock substitutions per method name across a test tree.

    A direct call is ``anything.name(...)``. A substitution is the method's name
    appearing as a string argument to a ``patch``-flavoured call, which is how
    ``mocker.patch.object(view, "name")`` reads in the AST.

    :param root: the tree to scan; defaults to the repository's ``tests/``
    :type root: Optional[Path]
    :return: direct-call counts and substitution counts, keyed by method name
    :rtype: Tuple[Dict[str, int], Dict[str, int]]
    """
    direct: Dict[str, int] = defaultdict(int)
    patched: Dict[str, int] = defaultdict(int)

    for path in sorted((root or TESTS).rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr not in MOCK_ASSERTIONS:
                direct[func.attr] += 1
            # The full dotted path, because `mocker.patch.object(...)` has an
            # immediate attribute of `object` - checking only that missed every
            # patch.object call, which is the commonest form in this suite.
            parts: List[str] = []
            node_walk: ast.expr = func
            while isinstance(node_walk, ast.Attribute):
                parts.append(node_walk.attr)
                node_walk = node_walk.value
            if isinstance(node_walk, ast.Name):
                parts.append(node_walk.id)
            if any("patch" in part for part in parts):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        patched[arg.value] += 1
    return direct, patched


def executed_lines(coverage_path: Path) -> Dict[str, Set[int]]:
    """
    Read the executed line numbers per source file out of a coverage JSON report.

    :param coverage_path: the report written by ``--cov-report=json``
    :type coverage_path: Path
    :return: repository-relative posix path to the set of executed lines
    :rtype: Dict[str, Set[int]]
    :raises FileNotFoundError: if the report does not exist
    """
    if not coverage_path.is_file():
        raise FileNotFoundError(
            f"{coverage_path} does not exist. Generate it with:\n"
            f"    pytest --cov=poriscope --cov-report=json:{coverage_path.name}"
        )
    report = json.loads(coverage_path.read_text(encoding="utf-8"))
    out: Dict[str, Set[int]] = {}
    for raw, data in report.get("files", {}).items():
        key = raw.replace("\\", "/")
        out[key] = set(data.get("executed_lines", []))
    return out


def collect_targets() -> List[Tuple[str, str, str]]:
    """
    Assemble the full set of methods the refactor moves or deduplicates.

    Deduplicated methods are resolved to every family file that defines them, so a
    five-way duplicate becomes five targets and each copy is checked in place.

    :return: (repository-relative file, method, step) triples, sorted and unique
    :rtype: List[Tuple[str, str, str]]
    """
    targets: Dict[Tuple[str, str], str] = {}

    for file, method, step in MOVED:
        targets[(file, method)] = step
    for file, method, step in emit_bearing_methods():
        targets.setdefault((file, method), step)
    for file, method, step in sql_authoring_methods():
        targets.setdefault((file, method), step)

    family_files = [TABS / name for name in VIEW_FILES]
    family_files += sorted((TABS).glob("*Controller.py"))
    family_files += sorted((TABS / "utils").glob("*ontrols*.py"))
    definitions: Dict[str, List[Path]] = defaultdict(list)
    for path in family_files:
        for name in method_line_ranges(path):
            definitions[name].append(path)

    for _, method, step in deduplicated_targets():
        for path in definitions.get(method, []):
            targets.setdefault((display(path), method), step)

    return sorted((f, m, s) for (f, m), s in targets.items())


def audit(coverage_path: Path) -> List[Dict[str, object]]:
    """
    Evaluate every target against the executed and targeted signals.

    :param coverage_path: the coverage JSON report to read
    :type coverage_path: Path
    :return: one record per target, sorted worst first
    :rtype: List[Dict[str, object]]
    :raises FileNotFoundError: if the coverage report is missing
    """
    covered = executed_lines(coverage_path)
    direct, patched = count_test_calls()

    ranges_cache: Dict[str, Dict[str, List[Tuple[int, int]]]] = {}
    records: List[Dict[str, object]] = []

    for file, method, step in collect_targets():
        path = REPO_ROOT / file
        if not path.is_file():
            records.append(
                {
                    "file": file,
                    "method": method,
                    "step": step,
                    "executed": False,
                    "direct": 0,
                    "patched": 0,
                    "verdict": "MISSING FILE",
                }
            )
            continue
        if file not in ranges_cache:
            ranges_cache[file] = method_line_ranges(path)
        spans = ranges_cache[file].get(method, [])
        lines = covered.get(file, set())
        executed = any(
            any(line in lines for line in range(start, end + 1)) for start, end in spans
        )
        calls = direct.get(method, 0)
        if not spans:
            verdict = "NOT FOUND"
        elif not executed:
            verdict = "UNTESTED"
        elif calls == 0:
            verdict = "RUNS ONLY"
        else:
            verdict = "PINNED"
        records.append(
            {
                "file": file,
                "method": method,
                "step": step,
                "executed": executed,
                "direct": calls,
                "patched": patched.get(method, 0),
                "verdict": verdict,
            }
        )

    order = {
        "MISSING FILE": 0,
        "NOT FOUND": 1,
        "UNTESTED": 2,
        "RUNS ONLY": 3,
        "PINNED": 4,
    }
    records.sort(
        key=lambda r: (order[str(r["verdict"])], str(r["file"]), str(r["method"]))
    )
    return records


def main(argv: List[str]) -> int:
    """
    Run the audit and report, exiting non-zero if any target is unpinned.

    :param argv: command-line arguments, excluding the program name
    :type argv: List[str]
    :return: 0 if every target is pinned, 1 otherwise
    :rtype: int
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coverage",
        default="coverage.json",
        help="path to the coverage JSON report (default: coverage.json)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="list the pinned targets too"
    )
    args = parser.parse_args(argv)

    try:
        records = audit(Path(args.coverage))
    except (FileNotFoundError, SyntaxError, OSError) as exc:
        print(f"Audit failed: {exc}", file=sys.stderr)
        return 1

    failing = [
        r for r in records if r["verdict"] in {"UNTESTED", "NOT FOUND", "MISSING FILE"}
    ]

    header = f"{'verdict':<13}{'step':<9}{'direct':>7}{'patch':>7}  method"
    print(header)
    print("-" * 78)
    for record in records:
        if record["verdict"] == "PINNED" and not args.verbose:
            continue
        name = f"{Path(str(record['file'])).name}::{record['method']}"
        print(
            f"{record['verdict']:<13}{record['step']:<9}"
            f"{record['direct']:>7}{record['patched']:>7}  {name}"
        )

    counts: Dict[str, int] = defaultdict(int)
    for record in records:
        counts[str(record["verdict"])] += 1
    print("-" * 78)
    print(
        f"{len(records)} targets: "
        + ", ".join(f"{n} {v.lower()}" for v, n in sorted(counts.items()))
    )
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
