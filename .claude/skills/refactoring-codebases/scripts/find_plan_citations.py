#!/usr/bin/env python3
"""Find references to a refactor plan's step numbering in everything that ships.

The plan document is deleted when the work ships, so "extracted in Step 5c.6" in a docstring,
comment, test name, script or published doc page promises an explanation that will not exist.
This searches EVERY text file type - a sweep scoped to ``*.py`` once declared the docs clean
while a published ``.rst`` page still cited a plan step.

Default patterns (extend with --pattern, which takes a Python regex):
    Step 4 / Step 4a / Step 5c.6 / step 3d-pre
    Decision C
    5e.3 / 4a-bis style sub-step tokens
    method rule 52 / rule 52

Every hit is a lead, not a verdict: a tutorial's "Step 1: click the menu" or a gate's own
numbered rules are legitimate prose. Triage by reading the line.

Usage:
    python find_plan_citations.py .                       # whole tree (git-tracked files if in a repo)
    python find_plan_citations.py src tests docs --exclude refactor_plan.md --exclude CHANGELOG.md
    python find_plan_citations.py . --pattern "\\bPhase [IVX]+\\b"
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PATTERNS = [
    r"\b[Ss]teps?\s+\d+[a-z]?(?:[.-]\d+[a-z]?|-pre|-bis)?\b",
    r"\bDecision\s+[A-Z]\b",
    r"(?<![\w.])\d[a-z](?:\.\d+|-bis|-pre)\b",
    r"\b(?:method\s+)?rule\s+\d+\b",
]


# Data formats whose content is not prose (SVG path data such as "3a.5" is an arc command).
SKIP_SUFFIXES = {".svg", ".csv", ".tsv", ".png", ".jpg", ".gif", ".ico", ".pdf", ".lock"}


def candidate_files(roots: list[str]) -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "--", *roots], check=True, capture_output=True, text=True).stdout
        files = [Path(p) for p in out.splitlines() if p]
        if files:
            return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    files = []
    for r in roots:
        p = Path(r)
        files.extend([p] if p.is_file() else [q for q in p.rglob("*") if q.is_file() and ".git" not in q.parts])
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roots", nargs="*", default=["."])
    ap.add_argument("--pattern", action="append", default=[], help="additional regex")
    ap.add_argument("--only", action="store_true", help="use only --pattern regexes, not the defaults")
    ap.add_argument("--exclude", action="append", default=[], help="path substring to skip (e.g. the plan)")
    ap.add_argument("--no-skip", action="store_true", help=f"also scan {sorted(SKIP_SUFFIXES)}")
    args = ap.parse_args(argv)

    patterns = [re.compile(p) for p in ((args.pattern if args.only else DEFAULT_PATTERNS + args.pattern))]
    by_ext: Counter[str] = Counter()
    scanned: Counter[str] = Counter()
    total = 0
    for path in candidate_files(args.roots):
        posix = path.as_posix()
        if any(x in posix for x in args.exclude) or (path.suffix.lower() in SKIP_SUFFIXES and not args.no_skip):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        scanned[path.suffix or "(none)"] += 1
        for i, line in enumerate(lines, 1):
            found = [m.group(0) for p in patterns for m in p.finditer(line)]
            if found:
                total += len(found)
                by_ext[path.suffix or "(none)"] += len(found)
                print(f"{posix}:{i}: {', '.join(found)}  |  {line.strip()[:120]}")
    print(f"\n{total} citation(s).")
    print("File types scanned: " + ", ".join(f"{k} x{v}" for k, v in sorted(scanned.items())))
    if by_ext:
        print("Citations by type:  " + ", ".join(f"{k} x{v}" for k, v in sorted(by_ext.items())))
    print("Check the scanned types cover every kind of artefact the rule names (code, tests, scripts, docs).")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
