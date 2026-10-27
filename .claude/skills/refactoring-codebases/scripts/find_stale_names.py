#!/usr/bin/env python3
"""Find deletion residue: names defined in the source at a baseline ref, gone now, still in the tests.

Mocks accept any attribute, so a test can go on patching, stubbing or asserting on a method the
refactor deleted and nothing will fail. Reading test files does not find this; a set difference does.

Defined names collected from Python source: functions, methods, classes, and attributes assigned
on ``self`` / ``cls``. A name counts as gone when it is defined nowhere under ``--src`` at HEAD
(the working tree). Hits are word-boundary matches in any text file under ``--tests``.

Caution: a hit can be an unrelated identically-named thing (another class's method of the same
name). Every hit is a lead to check, not a verdict.

Usage:
    python find_stale_names.py --baseline v1.9.0 --src src/app --tests tests
    python find_stale_names.py --baseline v1.9.0 --src src/app --tests tests --min-length 6
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path


def defined_names(source: str) -> set[str]:
    names: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store) \
                and isinstance(node.value, ast.Name) and node.value.id in ("self", "cls"):
            names.add(node.attr)
    return names


def names_at_ref(ref: str, src: str) -> set[str]:
    listing = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref, "--", src], check=True,
                             capture_output=True, text=True).stdout.split("\n")
    names: set[str] = set()
    for path in filter(lambda p: p.endswith(".py"), listing):
        text = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout
        names |= defined_names(text)
    return names


def names_now(src: str) -> set[str]:
    names: set[str] = set()
    for path in Path(src).rglob("*.py"):
        names |= defined_names(path.read_text(encoding="utf-8", errors="replace"))
    return names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", required=True, help="git ref before the refactor (tag or sha)")
    ap.add_argument("--src", required=True, help="source directory (repo-relative)")
    ap.add_argument("--tests", required=True, help="test directory to search")
    ap.add_argument("--min-length", type=int, default=4, help="ignore shorter names (noise)")
    args = ap.parse_args(argv)

    gone = {n for n in names_at_ref(args.baseline, args.src) - names_now(args.src)
            if len(n) >= args.min_length and not (n.startswith("__") and n.endswith("__"))}
    if not gone:
        print("No names were removed between the baseline and HEAD.")
        return 0
    pattern = re.compile(r"\b(" + "|".join(sorted(map(re.escape, gone), key=len, reverse=True)) + r")\b")
    hits: dict[str, list[str]] = {}
    for path in Path(args.tests).rglob("*"):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(lines, 1):
            for name in {m.group(1) for m in pattern.finditer(line)}:
                hits.setdefault(name, []).append(f"{path.as_posix()}:{i}")
    print(f"{len(gone)} names defined at {args.baseline} are gone from {args.src}; "
          f"{len(hits)} are still named in {args.tests}.\n")
    for name in sorted(hits, key=lambda n: (-len(hits[n]), n)):
        locs = hits[name]
        print(f"{name}  ({len(locs)})")
        for loc in locs[:8]:
            print(f"    {loc}")
        if len(locs) > 8:
            print(f"    ... {len(locs) - 8} more")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
