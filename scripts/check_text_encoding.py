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
Check that a text file is UTF-8 with no byte-order mark.

    python scripts/check_text_encoding.py PATH [PATH ...]

``requirements.txt`` was committed as **UTF-16LE with a BOM** and stayed that way
from the initial commit until 2026-09-04, because Windows PowerShell's ``>``
redirection and ``Out-File`` default to UTF-16LE unless given ``-Encoding utf8`` -
so ``pip freeze > requirements.txt`` at a PowerShell prompt produces exactly that
file. ``pip`` itself copes, because it honours the BOM; git does not, and treated
every revision as a binary blob, so a year of dependency changes went unreviewable.

**The stock hook does not cover this case.** ``pre-commit-hooks``'
``fix-byte-order-marker`` matches ``b"\\xef\\xbb\\xbf"`` only, which is the *UTF-8*
BOM; a UTF-16LE file begins ``b"\\xff\\xfe"`` and passes it untouched. That is why
this check exists rather than a line in ``.pre-commit-config.yaml``.

Exits 1 if any file carries a BOM of any width or does not decode as UTF-8, so it
is usable as a gate.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

#: Byte-order marks, longest first so UTF-32 is not read as UTF-16. Each maps to the
#: name of the encoding it announces, which is what the failure message reports.
BYTE_ORDER_MARKS: Tuple[Tuple[bytes, str], ...] = (
    (b"\xff\xfe\x00\x00", "UTF-32LE"),
    (b"\x00\x00\xfe\xff", "UTF-32BE"),
    (b"\xef\xbb\xbf", "UTF-8"),
    (b"\xff\xfe", "UTF-16LE"),
    (b"\xfe\xff", "UTF-16BE"),
)

#: What to do about it, printed with every failure because the cause is a shell
#: default rather than a mistake anyone makes deliberately.
REMEDY = (
    "rewrite it as UTF-8 without a BOM - in PowerShell, redirection and Out-File "
    "default to UTF-16LE, so pass -Encoding utf8 explicitly"
)


def problem(data: bytes) -> Optional[str]:
    """
    Describe what is wrong with a file's bytes, or None if nothing is.

    :param data: the file's contents
    :type data: bytes
    :return: the problem, phrased for a failure message, or None
    :rtype: Optional[str]
    """
    for mark, encoding in BYTE_ORDER_MARKS:
        if data.startswith(mark):
            return f"begins with a {encoding} byte-order mark"

    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return f"is not valid UTF-8: {exc.reason} at byte {exc.start}"
    return None


def main(argv: List[str]) -> int:
    """
    Check every named file and report the ones that are not plain UTF-8.

    :param argv: command-line arguments, excluding the program name
    :type argv: List[str]
    :return: 0 if every checked file is clean, 1 otherwise
    :rtype: int
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", metavar="PATH", help="files to check")
    args = parser.parse_args(argv)

    failed = 0
    for name in args.paths:
        path = Path(name)
        try:
            data = path.read_bytes()
        except OSError as exc:
            failed += 1
            print(f"FAIL {name}: could not be read: {exc!r}", file=sys.stderr)
            continue

        found = problem(data)
        if found is not None:
            failed += 1
            print(f"FAIL {name}: {found}; {REMEDY}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
