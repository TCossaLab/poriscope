"""
The duplication ratchet: the analysis-tab families must match their baseline exactly.

This is the instrument that makes the 2.0.0 refactor's central claim checkable.
Steps 3a-3c promote byte-identical methods to shared bases; the whole point is
that the copies are deleted, and until now nothing would have noticed if they
were not. ``.duplication-baseline.json`` records the counts and this test holds
them.

**The check is exact, not ``<=``.** A rise means duplication was added. A fall is
a win, and it fails too, so that the win is recorded in the same commit that
earned it - under ``<=`` the baseline would quietly overstate the duplication
still present and the slack would accrue unnoticed.

When a refactor commit legitimately removes duplication, rerun
``python scripts/measure_duplication.py --update`` and commit the new baseline
alongside the code that earned it. Read the failure message first: it
distinguishes a real promotion, which deletes functions, from a copy edited into
divergence, which does not. See ``scripts/measure_duplication.py``'s module
docstring for the counting rule and why that distinction matters.

``scripts/`` is not a package, so the module is loaded by file path.
"""

import importlib.util
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "measure_duplication.py")


@pytest.fixture(scope="module")
def mod() -> types.ModuleType:
    """
    Import ``scripts/measure_duplication.py`` by path, since ``scripts/`` is not a package.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("measure_duplication", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_baseline_file_exists(mod: types.ModuleType) -> None:
    """The ratchet is only a ratchet if its baseline is checked in."""
    assert mod.BASELINE_PATH.is_file(), (
        f"{mod.BASELINE_PATH.name} is missing. Generate it with "
        f"`python scripts/measure_duplication.py --update`."
    )


def test_duplication_matches_the_baseline(mod: types.ModuleType) -> None:
    """
    The measured duplication equals the recorded baseline, in both directions.

    A rise is added duplication. A fall is a win that has to be banked in the same
    commit, so it fails too rather than letting the baseline drift upward of
    reality.
    """
    problems = mod.compare(mod.to_baseline(mod.measure()), mod.load_baseline())
    assert not problems, "\n".join(
        [
            "Analysis-tab duplication no longer matches .duplication-baseline.json:",
            *(f"  - {problem}" for problem in problems),
            "",
            "If a refactor commit legitimately removed duplication, rerun",
            "`python scripts/measure_duplication.py --update` and commit the new",
            "baseline alongside the change that earned it.",
        ]
    )
