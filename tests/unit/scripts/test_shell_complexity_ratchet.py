"""
The shell complexity ratchet: the nine app-shell files must match their baseline exactly.

Step 5c restructures the app shell, and until now nothing measured it.
``check_mvc_boundary.py`` reads 0 on all three of its rules over these files and no
duplication family covers them, so the only instrument pointed at the shell is this
one. ``.shell-complexity-baseline.json`` records the counts and this test holds them.

**The check is exact, not ``<=``.** A rise means complexity was added. A fall is a
win, and it fails too, so that the win is recorded in the same commit that earned
it - under ``<=`` the baseline would quietly overstate the complexity still present
and the slack would accrue unnoticed.

When a refactor commit legitimately reduces complexity, rerun
``python scripts/measure_shell_complexity.py --update`` and commit the new baseline
alongside the code that earned it. Read the failure message first: it distinguishes
a real split, which leaves the pieces in the file and raises its function count,
from a method moved out to a module the file list does not name, which does not.
See ``scripts/measure_shell_complexity.py``'s module docstring for the counting rule
and why each deviation from textbook McCabe was chosen.

``scripts/`` is not a package, so the module is loaded by file path.
"""

import importlib.util
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "measure_shell_complexity.py")


@pytest.fixture(scope="module")
def mod() -> types.ModuleType:
    """
    Import ``scripts/measure_shell_complexity.py`` by path, since ``scripts/`` is not a package.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("measure_shell_complexity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_baseline_file_exists(mod: types.ModuleType) -> None:
    """The ratchet is only a ratchet if its baseline is checked in."""
    assert mod.BASELINE_PATH.is_file(), (
        f"{mod.BASELINE_PATH.name} is missing. Generate it with "
        f"`python scripts/measure_shell_complexity.py --update`."
    )


def test_shell_complexity_matches_the_baseline(mod: types.ModuleType) -> None:
    """
    The measured complexity equals the recorded baseline, in both directions.

    A rise is added complexity. A fall is a win that has to be banked in the same
    commit, so it fails too rather than letting the baseline drift above reality.
    """
    problems = mod.compare(mod.to_baseline(mod.measure()), mod.load_baseline())
    assert not problems, "\n".join(
        [
            "App-shell complexity no longer matches .shell-complexity-baseline.json:",
            *(f"  - {problem}" for problem in problems),
            "",
            "If a refactor commit legitimately reduced complexity, rerun",
            "`python scripts/measure_shell_complexity.py --update` and commit the new",
            "baseline alongside the change that earned it.",
        ]
    )
