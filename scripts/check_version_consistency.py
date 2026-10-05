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
Check that the version in ``CITATION.cff`` matches ``constants.py`` and the release tag.

    python scripts/check_version_consistency.py
    python scripts/check_version_consistency.py --tag v1.9.0

``CITATION.cff``'s version is a hand-maintained copy of ``poriscope/constants.py``'s, and
``release.yml`` validated only that the file parsed as CFF - never that it said the right
thing. **Zenodo builds its record from ``CITATION.cff``**, so a stale version there
publishes the new release under the old number and nothing fails: the release succeeds, the
DOI resolves, and the metadata is wrong. That is the failure this exists to stop.

Both files are read as text rather than imported or YAML-parsed. Reading them means this
runs with bare Python on a fresh checkout, before anything is installed - so it can sit in
the workflow's validation job rather than waiting on the build job, and so a developer can
run it before cutting a release without a working environment.
"""

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The CFF ``version`` field is a top-level scalar by the format's own specification, so a
#: line-anchored match is safe here in a way a regex over arbitrary YAML would not be.
#: Quoting is optional in CFF, hence the optional quotes.
_CFF_FIELD = r'^{0}:\s*["\']?([^"\'\s]+)["\']?\s*$'


def read_constants() -> Tuple[str, str]:
    """
    Read the version and release date declared in ``poriscope/constants.py``.

    Parsed rather than imported: importing pulls the package, which needs it installed, and
    this has to run on a bare checkout.

    :raises SystemExit: if either assignment is missing or is not a plain literal
    :return: the version string and the release date as ``YYYY-MM-DD``
    :rtype: Tuple[str, str]
    """
    source = Path(REPO_ROOT, "poriscope", "constants.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    version: Optional[str] = None
    date: Optional[str] = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "__VERSION__" in names and isinstance(node.value, ast.Constant):
            version = str(node.value.value)
        if "VERSION_DATE" in names and isinstance(node.value, ast.Call):
            # datetime.strptime("2026-09-04", "%Y-%m-%d") - the date is the first literal
            if node.value.args and isinstance(node.value.args[0], ast.Constant):
                date = str(node.value.args[0].value)

    if version is None:
        sys.exit("constants.py declares no __VERSION__ string literal")
    if date is None:
        sys.exit("constants.py declares no VERSION_DATE built from a date literal")
    return version, date


def read_citation() -> Tuple[str, str]:
    """
    Read the version and release date declared in ``CITATION.cff``.

    :raises SystemExit: if either field is missing, or appears more than once
    :return: the version string and the release date as ``YYYY-MM-DD``
    :rtype: Tuple[str, str]
    """
    source = Path(REPO_ROOT, "CITATION.cff").read_text(encoding="utf-8")
    found = []
    for field in ("version", "date-released"):
        matches = re.findall(_CFF_FIELD.format(field), source, re.MULTILINE)
        if len(matches) != 1:
            sys.exit(
                f"CITATION.cff has {len(matches)} top-level '{field}:' fields, expected 1"
            )
        found.append(matches[0])
    return found[0], found[1]


def disagreements(tag: Optional[str]) -> List[str]:
    """
    List every way the declared versions and dates fail to agree.

    All of them, not the first: a release that has drifted has usually drifted in more than
    one place, and reporting one at a time turns a single fix into several CI rounds.

    :param tag: the release tag being published, with or without its ``v`` prefix, or None
    :type tag: Optional[str]
    :return: one message per disagreement, empty if everything matches
    :rtype: List[str]
    """
    code_version, code_date = read_constants()
    cff_version, cff_date = read_citation()

    problems: List[str] = []
    if code_version != cff_version:
        problems.append(
            f"version: constants.py says {code_version!r}, "
            f"CITATION.cff says {cff_version!r}"
        )
    if code_date != cff_date:
        problems.append(
            f"release date: constants.py says {code_date!r}, "
            f"CITATION.cff says {cff_date!r}"
        )
    if tag is not None:
        # Release tags carry a 'v' prefix because release.yml triggers on 'v*'.
        stripped = tag[1:] if tag.startswith("v") else tag
        if stripped != code_version:
            problems.append(
                f"tag: {tag!r} does not match constants.py's {code_version!r}"
            )
        if stripped != cff_version:
            problems.append(
                f"tag: {tag!r} does not match CITATION.cff's {cff_version!r}"
            )
    return problems


def main(argv: List[str]) -> int:
    """
    Report every version disagreement, and fail if there are any.

    :param argv: command-line arguments, excluding the program name
    :type argv: List[str]
    :return: 0 when everything agrees, 1 otherwise
    :rtype: int
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        default=None,
        help="the release tag to check against, e.g. v1.9.0",
    )
    args = parser.parse_args(argv)

    problems = disagreements(args.tag)
    if problems:
        print("Version metadata does not agree:\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nZenodo builds its record from CITATION.cff, so releasing with these out of "
            "step publishes under the wrong version and reports no error.",
            file=sys.stderr,
        )
        return 1

    version, date = read_constants()
    print(f"version {version}, released {date} - constants.py and CITATION.cff agree")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
