#!/usr/bin/env python3
"""
Report control bytes and leftover conflict markers in files.

Why it exists: an edit scripted through a shell can turn an escape sequence into the
byte it names, and nothing fails loudly. In one 2026-11-12 cleanup a heredoc-written
edit put a NUL byte into a test file (collection failed with "source code string cannot
contain null bytes") and another put a backspace where a regex ``\\b`` was meant, into a
production comment and two docstrings - every test still passed, and only a byte dump
found it. Merging several workers' branches by hand adds the other risk: a conflict
marker left in a file that happens not to be imported by the tests run so far.

Usage::

    python scan_files.py path/one.py path/two.py
    python scan_files.py --git-range develop..HEAD      # every file the range changed
    python scan_files.py --git-range HEAD~3             # the same, from a single commit

Exit status is 1 when any file has a problem, 0 otherwise.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

#: Bytes that never belong in source or text: NUL, backspace, vertical tab, form feed,
#: and the rest of C0 except tab, newline and carriage return.
CONTROL = {b for b in range(32) if b not in (9, 10, 13)}
#: The opening and closing conflict markers. The ``=======`` separator is left out: a
#: reStructuredText underline is the same line, and a real conflict carries both of these.
MARKERS = (b"<<<<<<< ", b">>>>>>> ")


def changed_files(git_range: str) -> List[str]:
    """Files changed in a git range (or since a single commit), that still exist."""
    spec = git_range if ".." in git_range else f"{git_range}..HEAD"
    out = subprocess.run(
        ["git", "diff", "--name-only", spec], capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line and Path(line).is_file()]


def problems(path: str) -> List[str]:
    """Describe every problem found in one file."""
    data = Path(path).read_bytes()
    found = []
    bad = sorted({b for b in data if b in CONTROL})
    if bad:
        names = ", ".join(f"0x{b:02x}" for b in bad)
        first = min(data.index(bytes([b])) for b in bad)
        line = data[:first].count(b"\n") + 1
        found.append(f"control byte(s) {names}, first on line {line}")
    for marker in MARKERS:
        if marker in data:
            found.append(f"conflict marker {marker.strip().decode()!r}")
    return found


def main(argv: List[str]) -> int:
    """Scan the files named, or changed in a range; return 1 if any has a problem."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="*", help="files to scan")
    parser.add_argument("--git-range", help="scan every file changed in this git range")
    args = parser.parse_args(argv)

    paths = list(args.paths)
    if args.git_range:
        paths += changed_files(args.git_range)
    if not paths:
        parser.error("name files, or give --git-range")

    failed = 0
    for path in paths:
        for problem in problems(path):
            failed += 1
            print(f"{path}: {problem}")
    print(f"scanned {len(paths)} file(s), {failed} problem(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
