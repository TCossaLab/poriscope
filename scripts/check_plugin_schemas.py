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
Check that every data plugin declares a self-consistent settings schema.

    python scripts/check_plugin_schemas.py [--quiet] [PluginName ...]

The same check ``tests/unit/plugins/test_plugin_settings_schema.py`` runs, available
outside pytest so a contributor can point it at the one plugin they are working on.
Exits 1 if any plugin reports a problem, so it is usable as a gate.
"""

import argparse
import logging
import sys
from typing import List

from poriscope.utils.plugin_schemas import discover_plugin_classes, get_declared_schema
from poriscope.utils.settings_schema import validate_settings_schema


def main(argv: List[str]) -> int:
    """
    Validate the settings schema of every requested plugin and report the results.

    :param argv: command-line arguments, excluding the program name
    :type argv: List[str]
    :return: 0 if every checked plugin is clean, 1 otherwise
    :rtype: int
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "plugins",
        nargs="*",
        metavar="PluginName",
        help="plugin class names to check; defaults to all discovered plugins",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="report only the plugins that have problems",
    )
    args = parser.parse_args(argv)

    # Discovery imports every plugin file, and several log at import time. That output
    # is noise here, where the report is the point.
    logging.disable(logging.WARNING)

    discovered = discover_plugin_classes()
    if not discovered:
        print("No data plugins were discovered.", file=sys.stderr)
        return 1

    selected = sorted(discovered)
    if args.plugins:
        unknown = sorted(set(args.plugins) - set(discovered))
        if unknown:
            print(
                f"Unknown plugin(s): {', '.join(unknown)}\n"
                f"Discovered: {', '.join(sorted(discovered))}",
                file=sys.stderr,
            )
            return 1
        selected = sorted(args.plugins)

    failed = 0
    for name in selected:
        try:
            schema = get_declared_schema(discovered[name])
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: schema could not be retrieved: {exc!r}")
            continue

        problems = validate_settings_schema(schema)
        if problems:
            failed += 1
            print(f"FAIL {name}: {len(problems)} problem(s)")
            for problem in problems:
                print(f"       {problem}")
        elif not args.quiet:
            print(f"ok   {name}: {len(schema)} parameter(s)")

    print(f"\n{len(selected) - failed}/{len(selected)} plugins clean.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
