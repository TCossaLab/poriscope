"""
The MVC boundary gate: the analysis tabs must match their allowlist exactly.

``.mvc-boundary-allowlist.json`` records every known violation of the three rules
in ``scripts/check_mvc_boundary.py`` - a View emitting on the plugin bus, a View
importing a computation library, a Controller reading a View private. **The
allowlist reaching zero is Steps 3-5 of the 2.0.0 refactor finishing**, which is
why it is a progress metric rather than a pass/fail gate: every entry is a known
violation, recorded so a *new* one cannot slip in unnoticed beside it.

The check is exact in both directions. A rise is a new violation. A fall is
progress and fails too, so the win is recorded in the same commit that earned it -
under a "no worse than" rule the allowlist would overstate the violations
remaining, which is the one thing it exists to report.

When a refactor commit legitimately removes a violation, rerun
``python scripts/check_mvc_boundary.py --update`` and commit the new allowlist
alongside the code that earned it.

``scripts/`` is not a package, so the module is loaded by file path.
"""

import importlib.util
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "check_mvc_boundary.py")


@pytest.fixture(scope="module")
def mod() -> types.ModuleType:
    """
    Import ``scripts/check_mvc_boundary.py`` by path, since ``scripts/`` is not a package.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("check_mvc_boundary", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_allowlist_file_exists(mod: types.ModuleType) -> None:
    """The gate is only a gate if its allowlist is checked in."""
    assert mod.ALLOWLIST_PATH.is_file(), (
        f"{mod.ALLOWLIST_PATH.name} is missing. Generate it with "
        f"`python scripts/check_mvc_boundary.py --update`."
    )


def test_boundary_matches_the_allowlist(mod: types.ModuleType) -> None:
    """
    The measured violations equal the recorded allowlist, in both directions.

    A rise means a new View emit, a new computation import in a widget, or a new
    Controller reach into View internals. A fall is progress that has to be banked
    in the same commit.
    """
    problems = mod.compare(mod.to_allowlist(mod.measure()), mod.load_allowlist())
    assert not problems, "\n".join(
        [
            "The analysis-tab MVC boundary no longer matches "
            ".mvc-boundary-allowlist.json:",
            *(f"  - {problem}" for problem in problems),
            "",
            "If a refactor commit legitimately removed a violation, rerun",
            "`python scripts/check_mvc_boundary.py --update` and commit the new",
            "allowlist alongside the change that earned it.",
        ]
    )
