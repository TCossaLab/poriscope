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
# Alejandra Carolina González González

"""
Per-file and per-test durations from a pytest run, and the difference between two runs.

Record a run - ``pytest.ini`` sets ``junit_duration_report = total``, so each test's setup,
call and teardown count together:

    pytest --junitxml=run.xml

then:

    python scripts/test_durations.py report run.xml            # per-file, then per-test
    python scripts/test_durations.py report run.xml --top 50   # only the 50 slowest tests
    python scripts/test_durations.py summary run.xml           # markdown table per directory
    python scripts/test_durations.py compare old.xml new.xml   # what got slower, what is new
    python scripts/test_durations.py baseline a.xml b.xml c.xml > tests/test_duration_baseline.json
    python scripts/test_durations.py check run.xml tests/test_duration_baseline.json

``compare`` lists every file whose total moved, slowest change first, marking files that
exist in only one run, and ends with the share of the change that new tests account for
against tests present in both runs.

``check`` answers "the suite got slower - is that just more tests?". It expects each
directory to cost (its tests now) x (its milliseconds per test in the baseline); a directory
the baseline does not have is expected at its tier's average. It warns when the suite takes
more than 1.3x what it expects, or a directory of at least five tests costs more than 1.5x
its baseline per test: adding ten tests should add about ten tests' worth of time, so time
growing much faster than the test count means each test got dearer. The margins sit above
the roughly 25% that runner noise moves a whole run. It only warns, and always exits 0.
``baseline`` writes the file ``check`` reads, each directory's median over the runs given;
regenerate it deliberately, from several runs of the CI leg ``check`` runs on, when a
slowdown is accepted or a speed-up should be held.

Without ``junit_duration_report = total`` pytest records only the call phase, which hides
fixture and teardown cost.
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_MODULE = re.compile(r"^test_\w*$|^\w+_test$")


def test_path(classname: str, name: str) -> Tuple[str, str]:
    """
    Turn a junit ``classname`` and ``name`` back into a file path and a pytest node id.

    pytest writes ``tests.unit.views.test_x.TestCls`` as the classname. The module is the
    last dotted component named like a test module; everything after it is a class.

    :param classname: the testcase's ``classname`` attribute
    :type classname: str
    :param name: the testcase's ``name`` attribute
    :type name: str
    :return: the file path and the full node id
    :rtype: Tuple[str, str]
    """
    parts = classname.split(".")
    cut = max(
        (i for i, p in enumerate(parts) if _MODULE.match(p)), default=len(parts) - 1
    )
    path = "/".join(parts[: cut + 1]) + ".py"
    return path, "::".join([path, *parts[cut + 1 :], name])


def load(junit: str) -> Dict[str, Tuple[str, float]]:
    """
    Read a junit XML file into node id -> (file path, seconds).

    :param junit: path to the junit XML pytest wrote
    :type junit: str
    :return: every test case's file and duration, keyed by node id
    :rtype: Dict[str, Tuple[str, float]]
    """
    out: Dict[str, Tuple[str, float]] = {}
    for case in ET.parse(junit).getroot().iter("testcase"):
        path, node = test_path(case.get("classname", ""), case.get("name", ""))
        out[node] = (path, float(case.get("time", "0") or 0))
    return out


def by_file(tests: Dict[str, Tuple[str, float]]) -> Dict[str, List[float]]:
    """
    Group test durations by the file they live in.

    :param tests: node id -> (file path, seconds), as ``load`` returns
    :type tests: Dict[str, Tuple[str, float]]
    :return: file path -> the durations of its tests
    :rtype: Dict[str, List[float]]
    """
    files: Dict[str, List[float]] = defaultdict(list)
    for path, secs in tests.values():
        files[path].append(secs)
    return files


def report(junit: str, top: Optional[int]) -> None:
    """
    Print per-file totals, then per-test durations, slowest first.

    :param junit: path to the junit XML pytest wrote
    :type junit: str
    :param top: print only this many of the slowest tests; ``None`` prints all of them
    :type top: Optional[int]
    """
    tests = load(junit)
    files = by_file(tests)
    total = sum(s for _, s in tests.values())
    print(f"{len(tests)} tests in {len(files)} files, {total:.1f}s summed\n")
    print("=== Per-file total duration ===")
    for path, times in sorted(files.items(), key=lambda kv: -sum(kv[1])):
        n = len(times)
        print(f"{sum(times):9.2f}s  ({n:3d} tests, avg {sum(times) / n:5.2f}s)  {path}")
    print("\n=== Per-test duration (sorted slowest first) ===")
    ranked = sorted(tests.items(), key=lambda kv: -kv[1][1])
    for node, (_, secs) in ranked[:top] if top else ranked:
        print(f"{secs:9.2f}s  {node}")


def directory(path: str) -> str:
    """
    The directory a test file is grouped under: at most three levels, e.g. ``tests/unit/views``.

    :param path: a test file's path, as ``test_path`` returns it
    :type path: str
    :return: the grouping directory
    :rtype: str
    """
    return "/".join(path.split("/")[:-1][:3])


def summary(junit: str) -> None:
    """
    Print a markdown table of tests, summed seconds and milliseconds per test, per directory.

    Written for a CI job summary, where a directory whose ms/test jumps is the first sign
    of a fixture cost being multiplied across a growing family of tests. The seconds are
    the tests' own times added up; with parallel workers that is more than the wall time.

    :param junit: path to the junit XML pytest wrote
    :type junit: str
    """
    tests = load(junit)
    dirs: Dict[str, List[float]] = defaultdict(list)
    for path, secs in tests.values():
        dirs[directory(path)].append(secs)
    total = sum(s for _, s in tests.values())
    print("| Directory | Tests | Summed (s) | ms/test |")
    print("|---|---:|---:|---:|")
    for name, times in sorted(dirs.items(), key=lambda kv: -sum(kv[1])):
        print(
            f"| `{name}` | {len(times)} | {sum(times):.1f} | {1000 * sum(times) / len(times):.0f} |"
        )
    print(
        f"| **all** | {len(tests)} | {total:.1f} | {1000 * total / max(len(tests), 1):.0f} |"
    )


SUITE_RATIO = 1.3
DIRECTORY_RATIO = 1.5
MIN_TESTS = 5
PYTEST_INI = Path(__file__).resolve().parents[1] / "pytest.ini"


def budgets() -> Dict[str, float]:
    """
    The per-tier time budgets from ``pytest.ini``, which ``tests/conftest.py`` also reads.

    :return: tier -> seconds; tiers the file does not set keep the conftest's defaults
    :rtype: Dict[str, float]
    """
    found = {"unit": 5.0, "integration": 20.0, "e2e": 60.0}
    parser = configparser.ConfigParser()
    parser.read(PYTEST_INI, encoding="utf-8")
    for name in found:
        if parser.has_option("pytest", f"time_budget_{name}"):
            found[name] = parser.getfloat("pytest", f"time_budget_{name}")
    return found


def per_directory(junit: str) -> Dict[str, Dict[str, float]]:
    """
    Tests and milliseconds per test for each directory of one run.

    Each test counts for at most its tier's time budget. One stalled test - a runner
    pausing, a leak paid for all at once - would otherwise swamp a directory's mean; a
    test over its budget is the per-test budget's to report, and this measures the shift
    across a directory instead.

    :param junit: path to the junit XML pytest wrote
    :type junit: str
    :return: directory -> {"tests": count, "ms_per_test": mean}
    :rtype: Dict[str, Dict[str, float]]
    """
    caps = budgets()
    dirs: Dict[str, List[float]] = defaultdict(list)
    for path, secs in load(junit).values():
        name = directory(path)
        dirs[name].append(min(secs, caps.get(tier(name), caps["unit"])))
    return {
        name: {
            "tests": len(times),
            "ms_per_test": round(1000 * sum(times) / len(times), 1),
        }
        for name, times in sorted(dirs.items())
    }


def baseline(junits: List[str]) -> Dict[str, Dict[str, float]]:
    """
    The baseline ``check`` compares with: each directory's median over several runs.

    One run's directory mean moves with whatever else the runner was doing, so a baseline
    taken from a single run can be an outlier that every later check is measured against.
    The median of a few runs is not moved by one slow or one fast run. A directory missing
    from some runs takes the median of the runs that have it.

    :param junits: paths to the junit XML files of the runs, one or more
    :type junits: List[str]
    :return: directory -> {"tests": median count, "ms_per_test": median mean}
    :rtype: Dict[str, Dict[str, float]]
    """
    runs = [per_directory(junit) for junit in junits]
    names = sorted({name for run in runs for name in run})
    return {
        name: {
            "tests": statistics.median(
                run[name]["tests"] for run in runs if name in run
            ),
            "ms_per_test": round(
                statistics.median(
                    run[name]["ms_per_test"] for run in runs if name in run
                ),
                1,
            ),
        }
        for name in names
    }


def tier(name: str) -> str:
    """
    The tier a directory belongs to, ``tests/<tier>/...``, for a directory with no baseline.

    :param name: a directory, as ``directory`` returns it
    :type name: str
    :return: the second path component, or the directory itself when it has none
    :rtype: str
    """
    parts = name.split("/")
    return parts[1] if len(parts) > 1 else name


def expected_ms(name: str, base: Dict[str, Dict[str, float]]) -> Optional[float]:
    """
    Milliseconds per test a directory is expected to cost.

    :param name: the directory
    :type name: str
    :param base: the baseline, as ``baseline`` returns it
    :type base: Dict[str, Dict[str, float]]
    :return: its own baseline, else its tier's test-weighted average, else None
    :rtype: Optional[float]
    """
    if name in base:
        return base[name]["ms_per_test"]
    peers = [v for k, v in base.items() if tier(k) == tier(name)]
    count = sum(v["tests"] for v in peers)
    if not count:
        return None
    return sum(v["tests"] * v["ms_per_test"] for v in peers) / count


def check(junit: str, baseline_path: str) -> List[str]:
    """
    Warn when the run took far longer than its test count says it should.

    Prints a markdown table of expected against actual per directory, and one warning
    line per finding - as a GitHub annotation when run on GitHub Actions.

    :param junit: path to the junit XML pytest wrote
    :type junit: str
    :param baseline_path: path to the JSON ``baseline`` wrote
    :type baseline_path: str
    :return: the warnings, empty when the run is within its margins
    :rtype: List[str]
    """
    with open(baseline_path, encoding="utf-8") as handle:
        base = json.load(handle)
    now = per_directory(junit)
    warnings: List[str] = []
    expected_total = actual_total = 0.0
    print("| Directory | Tests (baseline -> now) | ms/test (baseline -> now) | Ratio |")
    print("|---|---:|---:|---:|")
    for name, row in sorted(
        now.items(), key=lambda kv: -kv[1]["tests"] * kv[1]["ms_per_test"]
    ):
        expect = expected_ms(name, base)
        actual_ms = row["ms_per_test"]
        actual_total += row["tests"] * actual_ms
        if expect is None:
            print(f"| `{name}` | new: {row['tests']:.0f} | {actual_ms:.0f} | - |")
            expected_total += row["tests"] * actual_ms
            continue
        expected_total += row["tests"] * expect
        ratio = actual_ms / expect if expect else 1.0
        was = base.get(name, {}).get("tests", 0)
        print(
            f"| `{name}` | {was:.0f} -> {row['tests']:.0f} | {expect:.0f} -> {actual_ms:.0f} | {ratio:.2f} |"
        )
        if row["tests"] >= MIN_TESTS and ratio > DIRECTORY_RATIO:
            warnings.append(
                f"{name}: {actual_ms:.0f} ms per test against {expect:.0f} expected "
                f"({ratio:.2f}x) - its tests got dearer, not just more numerous"
            )
    suite = actual_total / expected_total if expected_total else 1.0
    print(
        f"| **all** | {sum(v['tests'] for v in base.values()):.0f} -> "
        f"{sum(v['tests'] for v in now.values()):.0f} | expected {expected_total / 1000:.0f} s, "
        f"took {actual_total / 1000:.0f} s | {suite:.2f} |"
    )
    if suite > SUITE_RATIO:
        warnings.insert(
            0,
            f"the suite took {suite:.2f}x what its test count predicts "
            f"({actual_total / 1000:.0f} s against {expected_total / 1000:.0f} s)",
        )
    for line in warnings:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::warning title=Test suite slower than its size explains::{line}")
        else:
            print(f"WARNING: {line}")
    return warnings


def compare(old_junit: str, new_junit: str, top: int) -> None:
    """
    Print the per-file change between two runs and how much of it new tests explain.

    :param old_junit: the earlier run's junit XML
    :type old_junit: str
    :param new_junit: the later run's junit XML
    :type new_junit: str
    :param top: how many of the most-changed files and tests to print
    :type top: int
    """
    old, new = load(old_junit), load(new_junit)
    old_files, new_files = by_file(old), by_file(new)
    old_total = sum(s for _, s in old.values())
    new_total = sum(s for _, s in new.values())
    print(
        f"old: {len(old)} tests, {old_total:.1f}s   new: {len(new)} tests, {new_total:.1f}s"
    )
    print(f"change: {new_total - old_total:+.1f}s ({new_total / old_total:.2f}x)\n")

    rows = []
    for path in set(old_files) | set(new_files):
        a, b = old_files.get(path, []), new_files.get(path, [])
        tag = "NEW " if not a else "GONE" if not b else "    "
        rows.append((sum(b) - sum(a), tag, path, len(a), len(b), sum(a), sum(b)))
    rows.sort(key=lambda r: -abs(r[0]))
    print("=== Per-file change (largest first) ===")
    print(f"{'delta':>9}       {'old s':>8} {'new s':>8}  {'tests':>11}  file")
    for delta, tag, path, na, nb, sa, sb in rows[:top]:
        print(f"{delta:+9.2f}s {tag} {sa:8.2f} {sb:8.2f}  {na:4d} -> {nb:4d}  {path}")

    common = set(old) & set(new)
    added = set(new) - set(old)
    removed = set(old) - set(new)
    d_common = sum(new[k][1] - old[k][1] for k in common)
    d_added = sum(new[k][1] for k in added)
    d_removed = sum(old[k][1] for k in removed)
    print("\n=== Where the change comes from ===")
    print(f"{len(added):5d} new tests        {d_added:+9.1f}s")
    print(f"{len(removed):5d} removed tests    {-d_removed:+9.1f}s")
    print(f"{len(common):5d} tests in both    {d_common:+9.1f}s")

    print(f"\n=== Tests in both runs that slowed most (top {top}) ===")
    slowed = sorted(common, key=lambda k: -(new[k][1] - old[k][1]))
    for k in slowed[:top]:
        print(
            f"{new[k][1] - old[k][1]:+8.2f}s  {old[k][1]:7.2f} -> {new[k][1]:7.2f}  {k}"
        )


def main(argv: Optional[List[str]] = None) -> int:
    """
    Parse the command line and run the chosen subcommand.

    :param argv: the arguments, without the program name; ``None`` reads ``sys.argv``
    :type argv: Optional[List[str]]
    :return: the process exit code
    :rtype: int
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    rep = sub.add_parser("report", help="per-file and per-test durations of one run")
    rep.add_argument("junit")
    rep.add_argument(
        "--top", type=int, default=None, help="print only the N slowest tests"
    )
    summ = sub.add_parser(
        "summary", help="markdown table per directory, for a CI job summary"
    )
    summ.add_argument("junit")
    base_ = sub.add_parser(
        "baseline", help="per-directory baseline JSON for check, median over runs"
    )
    base_.add_argument("junits", nargs="+", metavar="junit")
    chk = sub.add_parser("check", help="warn when time grew faster than the test count")
    chk.add_argument("junit")
    chk.add_argument("baseline")
    cmp_ = sub.add_parser("compare", help="what changed between two runs")
    cmp_.add_argument("old")
    cmp_.add_argument("new")
    cmp_.add_argument(
        "--top", type=int, default=25, help="rows per section (default 25)"
    )
    args = parser.parse_args(argv)
    if args.command == "report":
        report(args.junit, args.top)
    elif args.command == "summary":
        summary(args.junit)
    elif args.command == "baseline":
        print(json.dumps(baseline(args.junits), indent=1))
    elif args.command == "check":
        check(args.junit, args.baseline)
    else:
        compare(args.old, args.new, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
