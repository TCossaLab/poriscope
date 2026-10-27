#!/usr/bin/env python3
"""Prove that tests discriminate: apply source mutations one at a time and run the tests aimed at each.

A test that has never been seen to fail is not known to test anything. This runs a list of
deliberate mutations, each paired with the test command expected to catch it:

    KILLED    the test command failed with the mutation applied - the test discriminates
    SURVIVED  the test command passed - the test (or its input) cannot see this change
    BOTCHED   the mutation could not be applied exactly (anchor missing or not unique) -
              NOT evidence about the test; a botched mutation reads exactly like a weak test

Safety: the original bytes are restored in a ``finally`` and verified after every mutation.
The unmutated baseline is run first; if it fails, nothing else is meaningful and the script stops.

Mutation file (JSON list):
    [
      {"name": "drop bool coercion",
       "file": "src/app/model.py",
       "anchor": "return bool(status)",
       "replacement": "return status",
       "test": "pytest -q tests/unit/test_model.py::TestStatus"}
    ]

Anchors are matched byte-exactly against the file (CRLF files keep "
"), so prefer
single-line anchors. Keep each test command narrow - one test class - so a mutation costs seconds.

Usage:
    python mutation_probe.py mutations.json
    python mutation_probe.py mutations.json --skip-baseline
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def run(cmd: str) -> int:
    return subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mutations")
    ap.add_argument("--skip-baseline", action="store_true")
    args = ap.parse_args(argv)
    muts = json.loads(Path(args.mutations).read_text(encoding="utf-8"))

    if not args.skip_baseline:
        for cmd in sorted({m["test"] for m in muts}):
            if run(cmd) != 0:
                print(f"BASELINE FAILS: {cmd}\nFix the unmutated run first; mutation results would be meaningless.")
                return 2
        print("Baseline: every test command passes unmutated.\n")

    results = []
    for m in muts:
        path = Path(m["file"])
        original = path.read_bytes()
        text = original.decode("utf-8")  # bytes-exact: CRLF files keep their line endings
        name = m.get("name", m["anchor"][:40])
        count = text.count(m["anchor"])
        if count != 1:
            results.append(("BOTCHED", name, f"anchor occurs {count} times"))
            continue
        mutated = text.replace(m["anchor"], m["replacement"], 1)
        if mutated == text:
            results.append(("BOTCHED", name, "replacement equals anchor"))
            continue
        t0 = time.time()
        try:
            payload = mutated.encode("utf-8")
            path.write_bytes(payload)
            if path.read_bytes() != payload:
                results.append(("BOTCHED", name, "mutated text did not land on disk"))
                continue
            code = run(m["test"])
        finally:
            path.write_bytes(original)
        if path.read_bytes() != original:
            print(f"RESTORE FAILED for {path} - stop and restore from version control.")
            return 3
        verdict = "KILLED" if code != 0 else "SURVIVED"
        results.append((verdict, name, f"{time.time() - t0:.1f}s  removed: {m['anchor']!r}"))

    width = max(len(r[1]) for r in results) if results else 10
    for verdict, name, detail in results:
        print(f"{verdict:9s} {name:{width}s}  {detail}")
    survived = sum(r[0] == "SURVIVED" for r in results)
    botched = sum(r[0] == "BOTCHED" for r in results)
    print(f"\n{len(results)} mutations: {len(results) - survived - botched} killed, {survived} survived, {botched} botched.")
    if survived:
        print("SURVIVED: the input may be too clean for this mechanism, or the code may be dead weight. "
              "Ask what degenerate case it was written for and probe that before concluding either.")
    return 1 if survived or botched else 0


if __name__ == "__main__":
    sys.exit(main())
