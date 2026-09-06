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
Measure byte-identical methods across the five-file analysis-tab families.

    python scripts/measure_duplication.py [--verbose] [--update] [--check]

The 2.0.0 refactor's headline claim is that promoting a method to a shared base
deletes its copies. Nothing measured that: the Step 0 figures came from a one-off
script that was never committed, so the baseline they quote cannot be re-derived.
This is that script, committed, so the number is reproducible and can be ratcheted.

**The rule, stated exactly, because the definition is the number.**

- Three families, each five files, enumerated explicitly below rather than globbed.
  A ``*controls.py`` glob is case-sensitive and silently misses
  ``eventAnalysisControls.py`` - 742 lines, 17% of that family.
- Within a family, every *module-level function* and every *method of a
  module-level class* is considered. Functions nested inside another function are
  not: their text is already contained in their parent's, so counting both would
  double-count the same lines.
- A function's text is ``ast.get_source_segment`` output with its indentation
  depth normalised away (see ``normalise``) and stripped.
  Note ``get_source_segment`` starts at the ``def`` line, so **decorators are not
  part of the compared text** - two methods with identical bodies but different
  decorators compare equal. That is deliberate: the body is what a promotion
  deletes.
- Two functions are duplicates when that text is byte-identical. A group counts
  only if the text appears in **more than one file** of the family; a file that
  repeats a body internally is not duplication across the family.
- Removable lines for a group = (files carrying it - 1) x its line count: what
  would be deleted by promoting one copy to a shared base.

This is a floor, not the whole prize. Byte identity cannot see a 195-line override
that differs in two lines, so a family can shrink by more than this measures.

**Byte identity is brittle in one direction, and it matters.** Editing a few
characters in *one* copy of a five-way duplicate drops that copy out of its group,
so the removable count falls by a whole copy's worth while nothing was
deduplicated - and the duplication is in fact worse, five near-identical bodies
instead of five identical ones. That is not hypothetical here: ``multiselect.py``
and ``multiselect_filter.py`` are ~90% duplicates where a fix demonstrably was
applied to only one of them. No similarity measure is needed to catch it, because
the two cases differ in a number already recorded: promoting a method to a shared
base **deletes** the copies, so ``functions`` falls too, while an edit into
divergence leaves it untouched. ``--check`` says so when it sees that shape.

Exits 1 under ``--check`` if the measurement disagrees with
``.duplication-baseline.json``, in **either** direction. Going up is a regression.
Going down is a win that has to be recorded in the same commit that earned it -
otherwise the baseline overstates the duplication left and the slack accrues
silently.
"""

import argparse
import ast
import json
import sys
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The families the refactor deduplicates, enumerated rather than globbed and
#: given as repository-relative paths. Case matters in the analysis-tab controls
#: family: ``eventAnalysisControls.py`` is camelCase and does not match
#: ``*controls.py``, so a glob would silently drop 742 lines, 17% of it.
#:
#: The three analysis-tab families are Step 3's; the rest are Steps 5a and 5d, and
#: were added by the Step 2 exit review, which found 772 removable lines sitting
#: outside the ratchet in exactly the families those steps work on.
#:
#: ``PeakFinder.py``, ``Basic_PeakFinder.py`` and ``NanoTrees.py`` are deliberately
#: absent from the fitters family. Their logic is another developer's under standing
#: policy, so a ratchet over them would fail on their owner's commits and block work
#: that is not ours to gate. Their duplication is therefore unmeasured by design, not
#: by oversight.
FAMILIES: Dict[str, Tuple[str, ...]] = {
    "*View.py": (
        "poriscope/plugins/analysistabs/ClusteringView.py",
        "poriscope/plugins/analysistabs/EventAnalysisView.py",
        "poriscope/plugins/analysistabs/MetadataView.py",
        "poriscope/plugins/analysistabs/ProteinView.py",
        "poriscope/plugins/analysistabs/RawDataView.py",
    ),
    "*Controller.py": (
        "poriscope/plugins/analysistabs/ClusteringController.py",
        "poriscope/plugins/analysistabs/EventAnalysisController.py",
        "poriscope/plugins/analysistabs/MetadataController.py",
        "poriscope/plugins/analysistabs/ProteinController.py",
        "poriscope/plugins/analysistabs/RawDataController.py",
    ),
    "*controls.py": (
        "poriscope/plugins/analysistabs/utils/clusteringcontrols.py",
        "poriscope/plugins/analysistabs/utils/eventAnalysisControls.py",
        "poriscope/plugins/analysistabs/utils/metadatacontrols.py",
        "poriscope/plugins/analysistabs/utils/proteincontrols.py",
        "poriscope/plugins/analysistabs/utils/rawdatacontrols.py",
    ),
    "eventfitters": (
        "poriscope/plugins/eventfitters/ClassicCUSUM.py",
        "poriscope/plugins/eventfitters/CUSUM.py",
        "poriscope/plugins/eventfitters/IntraCUSUM.py",
        "poriscope/plugins/eventfitters/NoFitter.py",
    ),
    "datareaders": (
        "poriscope/plugins/datareaders/BinaryReader1X.py",
        "poriscope/plugins/datareaders/ChimeraReader20240101.py",
        "poriscope/plugins/datareaders/ChimeraReader20240501.py",
        "poriscope/plugins/datareaders/ChimeraReaderVC100.py",
        "poriscope/plugins/datareaders/LegacyElementsReader.py",
        "poriscope/plugins/datareaders/SingleBinaryDecoder.py",
        "poriscope/plugins/datareaders/TCossaLabABFReader.py",
    ),
    "views/widgets": (
        "poriscope/views/widgets/add_subset_filter_dialog.py",
        "poriscope/views/widgets/clustering_settings_widget.py",
        "poriscope/views/widgets/dict_dialog_widget.py",
        "poriscope/views/widgets/dropdown_selection_widget.py",
        "poriscope/views/widgets/edit_subset_filter_dialog.py",
        "poriscope/views/widgets/icon_menu_widget.py",
        "poriscope/views/widgets/multiselect.py",
        "poriscope/views/widgets/multiselect_filter.py",
        "poriscope/views/widgets/SelectionTree.py",
        "poriscope/views/widgets/text_menu_widget.py",
        "poriscope/views/widgets/time_widget.py",
    ),
}

BASELINE_PATH = REPO_ROOT / ".duplication-baseline.json"

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


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


def normalise(segment: str) -> str:
    """
    Strip a function's source down to a form that ignores its indentation depth.

    ``textwrap.dedent`` alone is not enough here. ``ast.get_source_segment``
    starts at the ``def`` token rather than at the start of its line, so the first
    line of a method carries no leading whitespace while its body carries the
    class indent. The common prefix across those lines is therefore ``""`` and
    dedent does nothing, leaving a method and an identically-bodied module-level
    function comparing unequal.

    Dedenting everything *after* the first line fixes that while preserving the
    body's internal structure.

    :param segment: the raw source segment for one function
    :type segment: str
    :return: the segment with its indentation depth normalised away
    :rtype: str
    """
    head, newline, tail = segment.partition("\n")
    if not newline:
        return head.strip()
    return (head.strip() + newline + textwrap.dedent(tail)).strip()


def collect_functions(source: str, filename: str) -> List[Tuple[str, str]]:
    """
    Collect every module-level function and method of a module-level class.

    Functions nested inside another function are deliberately skipped, because
    their source is already part of their parent's and counting both would
    double-count the same lines.

    :param source: the file's text
    :type source: str
    :param filename: the name to attribute syntax errors to
    :type filename: str
    :return: one (qualified name, dedented source text) pair per function
    :rtype: List[Tuple[str, str]]
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

    collected: List[Tuple[str, str]] = []
    for name, node in found:
        segment = ast.get_source_segment(source, node)
        if segment is None:
            continue
        collected.append((name, normalise(segment)))
    return collected


def measure_family(files: List[Path]) -> Dict[str, object]:
    """
    Measure duplicate function bodies across one family's files.

    :param files: the family's files, already resolved
    :type files: List[Path]
    :return: the family's counts plus its duplicate groups, largest first
    :rtype: Dict[str, object]
    :raises SyntaxError: if any of the files cannot be parsed
    """
    #: text -> {file display name -> the names it appears under in that file}
    by_text: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    total_functions = 0

    for path in files:
        name = display(path)
        for func_name, text in collect_functions(
            path.read_text(encoding="utf-8"), name
        ):
            total_functions += 1
            by_text[text][name].append(func_name)

    groups = []
    for text, per_file in by_text.items():
        if len(per_file) < 2:
            continue
        lines = len(text.splitlines())
        groups.append(
            {
                "names": sorted({n for names in per_file.values() for n in names}),
                "files": len(per_file),
                "lines": lines,
                "removable": (len(per_file) - 1) * lines,
            }
        )
    groups.sort(key=lambda g: (-int(g["removable"]), g["names"][0]))

    return {
        "files": len(files),
        "functions": total_functions,
        "identical_bodies": len(groups),
        "removable_lines": sum(int(g["removable"]) for g in groups),
        "groups": groups,
    }


def measure() -> Dict[str, Dict[str, object]]:
    """
    Measure every family.

    :return: one entry per family, keyed by the family's glob-style label
    :rtype: Dict[str, Dict[str, object]]
    :raises FileNotFoundError: if a file named in FAMILIES does not exist
    """
    results: Dict[str, Dict[str, object]] = {}
    for family, names in FAMILIES.items():
        files = [REPO_ROOT / name for name in names]
        for path in files:
            if not path.is_file():
                raise FileNotFoundError(
                    f"{display(path)} is named in FAMILIES but does not exist; "
                    f"the family list is deliberately explicit, so update it"
                )
        results[family] = measure_family(files)
    return results


def to_baseline(results: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, int]]:
    """
    Reduce a measurement to the counts the baseline file records.

    The per-group detail is deliberately left out: it is useful to read and
    useless to diff, and it would churn the baseline on every rename.

    :param results: a full measurement
    :type results: Dict[str, Dict[str, object]]
    :return: per-family counts only
    :rtype: Dict[str, Dict[str, int]]
    """
    return {
        family: {
            "files": int(data["files"]),
            "functions": int(data["functions"]),
            "identical_bodies": int(data["identical_bodies"]),
            "removable_lines": int(data["removable_lines"]),
        }
        for family, data in results.items()
    }


def load_baseline() -> Dict[str, Dict[str, int]]:
    """
    Read the checked-in baseline.

    :return: the recorded per-family counts
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
    for family in sorted(set(current) | set(baseline)):
        if family not in baseline:
            problems.append(f"{family}: measured but absent from the baseline")
            continue
        if family not in current:
            problems.append(f"{family}: in the baseline but no longer measured")
            continue
        for key in sorted(set(current[family]) | set(baseline[family])):
            was = baseline[family].get(key)
            now = current[family].get(key)
            if was == now:
                continue
            if was is None or now is None:
                problems.append(f"{family}.{key}: baseline {was!r}, measured {now!r}")
            elif now > was:
                problems.append(
                    f"{family}.{key}: rose from {was} to {now} - duplication was added"
                )
            else:
                problems.append(
                    f"{family}.{key}: fell from {was} to {now} - record the win by "
                    f"rerunning with --update in the same commit"
                )

        problems.extend(_divergence_warning(family, current, baseline))
    return problems


def _divergence_warning(
    family: str,
    current: Dict[str, Dict[str, int]],
    baseline: Dict[str, Dict[str, int]],
) -> List[str]:
    """
    Warn when removable lines fell but no function was actually deleted.

    Byte identity is brittle in one direction: editing a few characters in *one*
    copy of a five-way duplicate drops that copy out of its group, so the removable
    count falls by a whole copy's worth while nothing was deduplicated. The
    duplication is in fact worse - five near-identical bodies instead of five
    identical ones - and this repository has form for it, ``multiselect.py`` and
    ``multiselect_filter.py`` being ~90% duplicates where a fix demonstrably was
    applied to only one.

    The two cases are distinguishable without any similarity measure: promoting a
    method to a shared base **deletes** the copies, so the function count falls too.
    An edit into divergence leaves it untouched.

    :param family: the family being reported on
    :type family: str
    :param current: the measurement just taken
    :type current: Dict[str, Dict[str, int]]
    :param baseline: the checked-in counts
    :type baseline: Dict[str, Dict[str, int]]
    :return: at most one warning, empty if the shape does not match
    :rtype: List[str]
    """
    if family not in current or family not in baseline:
        return []

    removable_fell = current[family].get("removable_lines", 0) < baseline[family].get(
        "removable_lines", 0
    )
    functions_fell = current[family].get("functions", 0) < baseline[family].get(
        "functions", 0
    )
    if removable_fell and not functions_fell:
        return [
            f"{family}: removable lines fell but no function was deleted. A real "
            f"promotion removes the copies, so `functions` falls too. Check that a "
            f"copy was not simply edited into divergence before running --update - "
            f"that reads as progress here while making the duplication worse."
        ]
    return []


def report(results: Dict[str, Dict[str, object]], verbose: bool) -> None:
    """
    Print the measurement as a table, optionally with each duplicate group.

    :param results: a full measurement
    :type results: Dict[str, Dict[str, object]]
    :param verbose: whether to list the duplicate groups under each family
    :type verbose: bool
    :return: None
    :rtype: None
    """
    header = (
        f"{'family':<16}{'files':>7}{'functions':>11}{'identical':>11}{'removable':>11}"
    )
    print(header)
    print("-" * len(header))

    totals = [0, 0, 0, 0]
    for family, data in results.items():
        row = [
            int(data["files"]),
            int(data["functions"]),
            int(data["identical_bodies"]),
            int(data["removable_lines"]),
        ]
        totals = [a + b for a, b in zip(totals, row, strict=True)]
        print(f"{family:<16}{row[0]:>7}{row[1]:>11}{row[2]:>11}{row[3]:>11}")

        if verbose:
            groups: List[Dict[str, object]] = data["groups"]  # type: ignore[assignment]
            for group in groups:
                names = ", ".join(str(n) for n in group["names"])  # type: ignore[union-attr]
                print(
                    f"    {group['removable']:>4} removable "
                    f"({group['lines']} lines x {group['files']} files)  {names}"
                )

    print("-" * len(header))
    print(f"{'total':<16}{totals[0]:>7}{totals[1]:>11}{totals[2]:>11}{totals[3]:>11}")


def main(argv: List[str]) -> int:
    """
    Measure the families and report, update the baseline, or check against it.

    :param argv: command-line arguments, excluding the program name
    :type argv: List[str]
    :return: 0 on success, 1 if --check found a disagreement or a file is missing
    :rtype: int
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="list every duplicate group, largest first",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="write the measurement to .duplication-baseline.json",
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

    if args.update:
        BASELINE_PATH.write_text(
            json.dumps(to_baseline(results), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote {display(BASELINE_PATH)}.")

    if args.check:
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
