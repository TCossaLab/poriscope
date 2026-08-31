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
Pre-commit/CI gate: every plugin's get_empty_settings() must be self-consistent.

Runs poriscope.utils.settings_schema.validate_settings_schema() against every
concrete data plugin discovered under poriscope.plugins, without needing pytest -
this is what lets the check run as a fast, standalone pre-commit hook scoped to
poriscope/plugins/**, ahead of the much more expensive behavioural conformance
suite under tests/unit/plugins/conformance/.

The full test suite (tests/unit/plugins/test_settings_schema.py) covers the same
ground plus a second check this script does not attempt: whether a plugin's
*default* values would pass that plugin's own validators. That half needs a live
plugin instance's real _validate_param_types/_validate_param_ranges rather than a
static schema check, so it stays a pytest-only check.

Usage: python scripts/check_settings_schema.py
Exit code 0 if every plugin's schema is clean, 1 otherwise (with every
violation printed, grouped by plugin).
"""

import importlib
import inspect
import logging
import pkgutil
import sys

# poriscope's @log decorator writes a DEBUG record on every call, which would
# otherwise bury this script's output - every plugin's __init__ chain, every
# get_empty_settings() call, one line each. Silence it before importing
# anything under poriscope so the debug handler never sees a record to emit.
logging.disable(logging.CRITICAL)

import poriscope.plugins as plugins_pkg  # noqa: E402
from poriscope.utils.BaseDataPlugin import BaseDataPlugin  # noqa: E402
from poriscope.utils.settings_schema import validate_settings_schema  # noqa: E402


def discover_concrete_plugins():
    for _finder, modname, _ispkg in pkgutil.walk_packages(
        plugins_pkg.__path__, prefix=f"{plugins_pkg.__name__}."
    ):
        importlib.import_module(modname)

    found = set()
    queue = list(BaseDataPlugin.__subclasses__())
    while queue:
        cls = queue.pop()
        if cls in found:
            continue
        found.add(cls)
        queue.extend(cls.__subclasses__())
    return sorted(
        (cls for cls in found if not inspect.isabstract(cls)),
        key=lambda cls: cls.__name__,
    )


def main() -> int:
    had_errors = False
    for plugin_cls in discover_concrete_plugins():
        try:
            settings = plugin_cls().get_empty_settings(standalone=True)
        except Exception as exc:
            print(f"{plugin_cls.__name__}: could not build settings: {exc!r}")
            had_errors = True
            continue

        errors = validate_settings_schema(settings)
        if errors:
            had_errors = True
            print(f"{plugin_cls.__name__}:")
            for error in errors:
                print(f"  {error}")

    if had_errors:
        print("\nsettings-schema check failed - see violations above")
        return 1

    print("settings-schema check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
