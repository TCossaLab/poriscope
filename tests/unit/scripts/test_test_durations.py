"""
Tests for ``scripts/test_durations.py``, which reads a pytest junit file into per-file and per-test times.

The junit files here are written by hand, so each test pins one rule of the reading:
how a dotted ``classname`` maps back to a file, how files group into directories, how
``compare`` splits a change between new, removed and surviving tests, how a baseline caps a
stalled test, and when ``check`` warns.

``scripts/`` is not a package, so the module under test is loaded by file path.
"""

import importlib.util
import json
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "test_durations.py")


def load_script() -> types.ModuleType:
    """
    Import ``scripts/test_durations.py`` by path, since ``scripts/`` is not a package.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("test_durations_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> types.ModuleType:
    """
    The imported script, shared across the module's tests.

    :return: the imported module
    :rtype: types.ModuleType
    """
    return load_script()


def junit(tmp_path: Path, name: str, cases: list) -> str:
    """
    Write a junit file holding the given ``(classname, name, seconds)`` cases.

    :param tmp_path: where to write it
    :type tmp_path: Path
    :param name: the file name
    :type name: str
    :param cases: one tuple per test case
    :type cases: list
    :return: the file's path
    :rtype: str
    """
    body = "".join(
        f'<testcase classname="{c}" name="{n}" time="{t}"/>' for c, n, t in cases
    )
    path = tmp_path / name
    path.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>")
    return str(path)


@pytest.mark.parametrize(
    "classname, name, expected",
    [
        (
            "tests.unit.views.test_main_view",
            "test_a",
            (
                "tests/unit/views/test_main_view.py",
                "tests/unit/views/test_main_view.py::test_a",
            ),
        ),
        (
            "tests.unit.views.test_main_view.TestOuter.TestInner",
            "test_b[x-1]",
            (
                "tests/unit/views/test_main_view.py",
                "tests/unit/views/test_main_view.py::TestOuter::TestInner::test_b[x-1]",
            ),
        ),
        (
            "tests.integration.flows.test_triad_teardown",
            "test_c",
            (
                "tests/integration/flows/test_triad_teardown.py",
                "tests/integration/flows/test_triad_teardown.py::test_c",
            ),
        ),
    ],
)
def test_a_classname_maps_back_to_its_file_and_node_id(mod, classname, name, expected):
    """A module is the last component named like a test module; what follows it are classes."""
    assert mod.test_path(classname, name) == expected


def test_a_class_named_like_a_module_is_not_taken_for_one(mod):
    """Classes start ``Test`` with a capital, so ``TestFoo`` never ends the file path."""
    path, _ = mod.test_path("tests.unit.test_x.TestFoo", "test_y")
    assert path == "tests/unit/test_x.py"


@pytest.mark.parametrize(
    "path, expected",
    [
        ("tests/unit/views/widgets/test_a.py", "tests/unit/views"),
        ("tests/unit/test_main_app.py", "tests/unit"),
        ("tests/test_safety_net_is_armed.py", "tests"),
    ],
)
def test_files_group_under_at_most_three_directory_levels(mod, path, expected):
    """Grouping deeper than ``tests/<tier>/<area>`` would split one family across rows."""
    assert mod.directory(path) == expected


def test_load_reads_every_case_with_its_seconds(mod, tmp_path):
    """Each case is keyed by node id and carries its file and its total time."""
    path = junit(
        tmp_path,
        "a.xml",
        [("tests.unit.test_x", "test_a", 1.5), ("tests.unit.test_x", "test_b", 0.25)],
    )
    assert mod.load(path) == {
        "tests/unit/test_x.py::test_a": ("tests/unit/test_x.py", 1.5),
        "tests/unit/test_x.py::test_b": ("tests/unit/test_x.py", 0.25),
    }


def test_summary_totals_each_directory_and_the_run(mod, tmp_path, capsys):
    """The table carries tests, total seconds and ms/test per directory, then the whole run."""
    path = junit(
        tmp_path,
        "a.xml",
        [
            ("tests.integration.flows.test_x", "test_a", 3.0),
            ("tests.integration.flows.test_x", "test_b", 1.0),
            ("tests.unit.views.test_y", "test_c", 0.5),
        ],
    )
    mod.summary(path)
    out = capsys.readouterr().out
    assert "| `tests/integration/flows` | 2 | 4.0 | 2000 |" in out
    assert "| `tests/unit/views` | 1 | 0.5 | 500 |" in out
    assert "| **all** | 3 | 4.5 | 1500 |" in out


def test_compare_splits_the_change_between_new_removed_and_surviving_tests(
    mod, tmp_path, capsys
):
    """A regression's cause shows as which of the three groups the seconds landed in."""
    old = junit(
        tmp_path,
        "old.xml",
        [
            ("tests.unit.test_x", "test_kept", 1.0),
            ("tests.unit.test_x", "test_gone", 2.0),
        ],
    )
    new = junit(
        tmp_path,
        "new.xml",
        [
            ("tests.unit.test_x", "test_kept", 1.5),
            ("tests.unit.test_z", "test_new", 4.0),
        ],
    )
    mod.compare(old, new, top=10)
    out = capsys.readouterr().out
    assert "    1 new tests             +4.0s" in out
    assert "    1 removed tests         -2.0s" in out
    assert "    1 tests in both         +0.5s" in out
    assert "NEW " in out and "tests/unit/test_z.py" in out


def test_the_budgets_are_read_from_pytest_ini(mod):
    """One source for the budget, shared with tests/conftest.py's --time-budget."""
    assert mod.budgets() == {"unit": 5.0, "integration": 20.0, "e2e": 60.0}


def test_a_baseline_caps_each_test_at_its_tier_budget(mod, tmp_path):
    """One stalled test would swamp a directory's mean; the per-test budget reports it instead."""
    path = junit(
        tmp_path,
        "a.xml",
        [
            ("tests.unit.views.test_x", "test_a", 0.1),
            ("tests.unit.views.test_x", "test_stalled", 300.0),
        ],
    )
    assert mod.baseline([path]) == {
        "tests/unit/views": {"tests": 2, "ms_per_test": 2550.0}
    }


def test_a_baseline_from_several_runs_takes_each_directory_median(mod, tmp_path):
    """One slow run among three moves the baseline not at all; a mean would take a third of it."""
    runs = [
        junit(tmp_path, f"{i}.xml", cases("tests.unit.views.test_x", 10, seconds))
        for i, seconds in enumerate([0.1, 0.12, 0.9])
    ]
    runs.append(junit(tmp_path, "3.xml", cases("tests.unit.models.test_y", 4, 0.2)))
    assert mod.baseline(runs) == {
        "tests/unit/models": {"tests": 4, "ms_per_test": 200.0},
        "tests/unit/views": {"tests": 10, "ms_per_test": 120.0},
    }


def write_baseline(tmp_path: Path, rows: dict) -> str:
    """
    Write a baseline file holding the given directory rows.

    :param tmp_path: where to write it
    :type tmp_path: Path
    :param rows: directory -> {"tests": n, "ms_per_test": ms}
    :type rows: dict
    :return: the file's path
    :rtype: str
    """
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(rows))
    return str(path)


def cases(classname: str, count: int, seconds: float) -> list:
    """
    ``count`` junit cases in one module, each taking ``seconds``.

    :param classname: the module's dotted name
    :type classname: str
    :param count: how many
    :type count: int
    :param seconds: each one's time
    :type seconds: float
    :return: the cases
    :rtype: list
    """
    return [(classname, f"test_{i}", seconds) for i in range(count)]


def test_more_tests_at_the_same_cost_each_is_not_a_warning(mod, tmp_path, capsys):
    """Ten times the tests and ten times the time is just a bigger suite."""
    base = write_baseline(
        tmp_path, {"tests/unit/views": {"tests": 10, "ms_per_test": 100.0}}
    )
    run = junit(tmp_path, "run.xml", cases("tests.unit.views.test_x", 100, 0.1))
    assert mod.check(run, base) == []
    assert "expected 10 s, took 10 s | 1.00 |" in capsys.readouterr().out


def test_tests_that_got_dearer_warn_for_the_suite_and_the_directory(mod, tmp_path):
    base = write_baseline(
        tmp_path, {"tests/integration/flows": {"tests": 10, "ms_per_test": 1000.0}}
    )
    run = junit(tmp_path, "run.xml", cases("tests.integration.flows.test_x", 10, 3.0))
    warnings = mod.check(run, base)
    assert warnings[0].startswith("the suite took 3.00x what its test count predicts")
    assert warnings[1].startswith(
        "tests/integration/flows: 3000 ms per test against 1000 expected"
    )


def test_a_directory_under_five_tests_does_not_warn_on_its_own(mod, tmp_path):
    """A handful of tests is too few to read a per-test mean from; the suite ratio still counts."""
    base = write_baseline(
        tmp_path,
        {
            "tests/e2e/raw_data": {"tests": 2, "ms_per_test": 1000.0},
            "tests/unit/views": {"tests": 100, "ms_per_test": 1000.0},
        },
    )
    run = junit(
        tmp_path,
        "run.xml",
        cases("tests.e2e.raw_data.test_x", 2, 3.0)
        + cases("tests.unit.views.test_y", 100, 1.0),
    )
    assert mod.check(run, base) == []


def test_a_new_directory_is_expected_at_its_tier_average(mod, tmp_path):
    """No baseline of its own, so it is held to what its tier's tests cost on average."""
    base = write_baseline(
        tmp_path,
        {
            "tests/unit/views": {"tests": 30, "ms_per_test": 100.0},
            "tests/unit/models": {"tests": 10, "ms_per_test": 500.0},
        },
    )
    assert (
        mod.expected_ms("tests/unit/brand_new", json.loads(Path(base).read_text()))
        == 200.0
    )
    run = junit(tmp_path, "run.xml", cases("tests.unit.brand_new.test_x", 10, 1.0))
    assert mod.check(run, base)[1].startswith(
        "tests/unit/brand_new: 1000 ms per test against 200 expected"
    )


def test_on_github_actions_a_warning_is_an_annotation(
    mod, tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    base = write_baseline(
        tmp_path, {"tests/unit/views": {"tests": 10, "ms_per_test": 100.0}}
    )
    run = junit(tmp_path, "run.xml", cases("tests.unit.views.test_x", 10, 1.0))
    mod.check(run, base)
    assert (
        "::warning title=Test suite slower than its size explains::the suite took"
        in capsys.readouterr().out
    )


def test_main_dispatches_each_subcommand(mod, tmp_path, capsys):
    """The command line reaches every subcommand, and each exits 0."""
    path = junit(tmp_path, "a.xml", [("tests.unit.test_x", "test_a", 1.0)])
    assert mod.main(["report", path]) == 0
    assert "Per-test duration" in capsys.readouterr().out
    assert mod.main(["summary", path]) == 0
    assert "| **all** |" in capsys.readouterr().out
    assert mod.main(["compare", path, path]) == 0
    assert "tests in both" in capsys.readouterr().out
    assert mod.main(["baseline", path]) == 0
    base = tmp_path / "base.json"
    base.write_text(capsys.readouterr().out)
    assert json.loads(base.read_text()) == {
        "tests/unit": {"tests": 1, "ms_per_test": 1000.0}
    }
    assert mod.main(["check", path, str(base)]) == 0
    assert "| **all** |" in capsys.readouterr().out
