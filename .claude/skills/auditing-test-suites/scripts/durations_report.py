#!/usr/bin/env python3
"""
Aggregate a pytest ``--durations=0`` log by phase, directory and file.

Why it exists: a slow suite's time is rarely in its test bodies. Recorded in one
2026-11-12 audit, a 1,650 s run spent 466 s in test calls, 644 s in setup and 509 s in
teardown, and two files held 448 s of that teardown. Read as a flat list of slowest
tests, the same log points at whichever test happened to pay for state an earlier test
leaked. Splitting by phase and by file, and comparing a file's full-run time with its
time run alone, is what points at the cause instead.

Produce the input with::

    pytest --durations=0 --durations-min=0 > full.log 2>&1

and, for the files you suspect, a second log of them run alone (one file per pytest
invocation is best, so nothing leaks between them), appended into one file.

Usage::

    python durations_report.py full.log
    python durations_report.py full.log --top 40
    python durations_report.py full.log --alone alone.log

Exit status is 0 unless the log holds no duration lines, which usually means pytest
was not run with ``--durations=0 --durations-min=0``.
"""

import argparse
import collections
import re
import statistics
import sys
from typing import Dict, List, Tuple

LINE = re.compile(r"^\s*([\d.]+)s (setup|call|teardown)\s+(\S.*?)\s*$")


def parse(path: str) -> List[Tuple[float, str, str]]:
    """Return (seconds, phase, node id) for every duration line in a log."""
    rows = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = LINE.match(line)
            if match:
                rows.append((float(match[1]), match[2], match[3]))
    return rows


def file_of(node: str) -> str:
    """The test file a node id belongs to."""
    return node.split("::", 1)[0]


def directory_of(node: str, depth: int) -> str:
    """The first ``depth`` path parts of a node's file."""
    parts = file_of(node).replace("\\", "/").split("/")
    return "/".join(parts[: min(depth, len(parts))])


def per_file(rows: List[Tuple[float, str, str]]) -> Dict[str, float]:
    """Total seconds per test file."""
    totals: Dict[str, float] = collections.defaultdict(float)
    for seconds, _phase, node in rows:
        totals[file_of(node)] += seconds
    return totals


def report(rows: List[Tuple[float, str, str]], top: int, depth: int) -> None:
    """Print the phase split, the directories, the files and the slowest phases."""
    total = sum(r[0] for r in rows)
    phases: Dict[str, float] = collections.defaultdict(float)
    for seconds, phase, _ in rows:
        phases[phase] += seconds
    print(f"{len(rows)} phase records, {total:.0f} s in all")
    for phase in ("setup", "call", "teardown"):
        share = 100 * phases[phase] / total if total else 0
        print(f"  {phase:9s} {phases[phase]:8.1f} s  {share:5.1f}%")

    by_dir: Dict[str, float] = collections.defaultdict(float)
    by_file: Dict[str, Dict[str, float]] = collections.defaultdict(
        lambda: collections.defaultdict(float)
    )
    calls: Dict[str, int] = collections.defaultdict(int)
    for seconds, phase, node in rows:
        by_dir[directory_of(node, depth)] += seconds
        by_file[file_of(node)][phase] += seconds
        if phase == "call":
            calls[file_of(node)] += 1

    print("\nby directory:")
    for name, seconds in sorted(by_dir.items(), key=lambda kv: -kv[1]):
        print(f"  {seconds:8.1f} s  {name}")

    print(f"\ntop {top} files (total | setup call teardown | tests | mean per test):")
    ranked = sorted(by_file.items(), key=lambda kv: -sum(kv[1].values()))[:top]
    for name, split in ranked:
        whole = sum(split.values())
        count = max(calls[name], 1)
        print(
            f"  {whole:7.1f} | {split['setup']:7.1f} {split['call']:7.1f} "
            f"{split['teardown']:7.1f} | {calls[name]:5d} | {whole / count:6.2f}  {name}"
        )

    print(f"\ntop {top} single phases:")
    for seconds, phase, node in sorted(rows, reverse=True)[:top]:
        print(f"  {seconds:7.2f} s {phase:8s} {node[:140]}")

    per_test: Dict[str, float] = collections.defaultdict(float)
    for seconds, _phase, node in rows:
        per_test[node] += seconds
    values = sorted(per_test.values())
    if values:
        print(
            f"\n{len(values)} tests: median {statistics.median(values):.3f} s, "
            f"90th percentile {values[int(0.9 * (len(values) - 1))]:.3f} s; "
            f"tests over 1 s account for {sum(v for v in values if v >= 1):.0f} s"
        )


def compare(full: Dict[str, float], alone: Dict[str, float], top: int) -> None:
    """Print each file's full-run time against its time alone, worst ratio first."""
    shared = [name for name in alone if name in full and alone[name] > 0]
    if not shared:
        print("\nno file appears in both logs")
        return
    print("\nfull run against alone (a high ratio means paying for earlier tests):")
    ranked = sorted(shared, key=lambda n: -(full[n] / alone[n]))[:top]
    for name in ranked:
        print(
            f"  {full[name]:7.1f} s full  {alone[name]:7.1f} s alone  "
            f"x{full[name] / alone[name]:5.1f}  {name}"
        )


def main(argv: List[str]) -> int:
    """Run the report; return 1 when the log holds no duration lines."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("log", help="a full run's output with --durations=0 --durations-min=0")
    parser.add_argument("--alone", help="a log of the suspect files run alone, for the ratio")
    parser.add_argument("--top", type=int, default=30, help="rows per ranked list (default 30)")
    parser.add_argument(
        "--depth", type=int, default=3, help="path parts that name a directory (default 3)"
    )
    args = parser.parse_args(argv)

    rows = parse(args.log)
    if not rows:
        print(
            f"no duration lines in {args.log}: run pytest with --durations=0 --durations-min=0",
            file=sys.stderr,
        )
        return 1
    report(rows, args.top, args.depth)
    if args.alone:
        compare(per_file(rows), per_file(parse(args.alone)), args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
