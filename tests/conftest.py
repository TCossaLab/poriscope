"""Project-wide test fixtures.

Poriscope resolves its config, session and log directories through
``platformdirs.user_data_dir()``, so anything that builds a real ``MainModel``
writes into the developer's actual ``%LOCALAPPDATA%/Poriscope`` profile and can
overwrite their real saved session and tab-action history.

This autouse fixture makes the redirection an inherited default rather than a
convention each area has to remember, so a test added anywhere cannot reach real
user state. ``tests/e2e/conftest.py``'s autouse ``sandbox_appdata`` runs after it
and deliberately overrides it with its own root, because the e2e assertions depend
on the specific layout it builds. The ``main_model`` fixture in
``tests/unit/models/test_main_model.py`` relies on this one alone.
"""

import itertools
import os
import sys
from collections import defaultdict
from pathlib import Path

import psutil
import pytest

from tests._window_cleanup import destroy_leftover_windows

# ===========================================================================
# Repo root on sys.path
# ===========================================================================
#
# Test modules import shared helpers by absolute path - ``tests.synthetic_data``,
# ``tests.unit.views._qt_mocks``, ``tests.e2e._helpers``. None of those resolve on
# their own: there is no ``__init__.py`` anywhere under ``tests/``, so pytest's
# prepend import mode inserts each test file's own directory rather than the repo
# root, and the bare ``pytest`` command (unlike ``python -m pytest``) does not add
# the current directory either. The editable install only exposes ``poriscope``.
#
# This lives here, in the root conftest, because pytest imports it before any
# subtree's conftest or test module, so the import works whatever paths a run
# selects. It used to be copied into tests/e2e/conftest.py and
# tests/integration/conftest.py, which left ``pytest tests/unit/views`` failing
# standalone while the full suite passed.
_TESTS_DIR = Path(__file__).resolve().parent
for _candidate in [_TESTS_DIR, *_TESTS_DIR.parents]:
    if (_candidate / "poriscope").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break


_SANDBOX_NUMBERS = itertools.count()


@pytest.fixture(scope="session")
def _sandbox_parent(tmp_path_factory):
    """
    One directory per session holding every test's sandbox.

    Asking for ``tmp_path`` in every test is what this avoids: pytest lists its whole
    base directory to number each new one, so that cost grows with every test run
    before it - about 47 s over the suite.

    :param tmp_path_factory: pytest's session-wide temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    :return: the directory the sandboxes are made in
    :rtype: pathlib.Path
    """
    return tmp_path_factory.mktemp("appdata_sandboxes", numbered=False)


@pytest.fixture(autouse=True)
def sandbox_user_data_dir(monkeypatch, _sandbox_parent):
    """
    Point ``platformdirs.user_data_dir()`` at a fresh per-test directory.

    :param monkeypatch: pytest's monkeypatch fixture.
    :type monkeypatch: pytest.MonkeyPatch
    :param _sandbox_parent: the session directory each test's sandbox is made in.
    :type _sandbox_parent: pathlib.Path
    """
    appdata_root = _sandbox_parent / str(next(_SANDBOX_NUMBERS)) / "appdata"
    for subdir in ("session", "config", "logs", "user_plugins"):
        (appdata_root / "Poriscope" / subdir).mkdir(parents=True, exist_ok=True)

    def _fake_user_data_dir(*args, **kwargs):
        return str(appdata_root)

    monkeypatch.setattr(
        "poriscope.models.main_model.user_data_dir",
        _fake_user_data_dir,
        raising=True,
    )
    # main_app is the other consumer, but no test imports it today and patching
    # it by string would force that import - and QApplication construction -
    # into every test. Only redirect it if something has already pulled it in.
    if "poriscope.main_app" in sys.modules:
        monkeypatch.setattr(
            "poriscope.main_app.user_data_dir",
            _fake_user_data_dir,
            raising=True,
        )


# One worker's peak memory, rounded up: 1.9 GB measured on 2026-11-12 with four workers
# over tests/integration and tests/unit/views, the heaviest directories.
_WORKER_MEMORY_BYTES = 2 * 1024**3


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_auto_num_workers(config):
    """
    Size ``pytest -n auto`` from this machine: one worker per logical core, but no more
    workers than the available memory holds.

    Logical rather than physical cores, because a 4-vCPU CI runner reports two physical
    cores. Every worker loads Qt, matplotlib and the session's synthetic data, so memory
    is the tighter limit on a many-core desktop. ``PYTEST_XDIST_AUTO_NUM_WORKERS`` still
    overrides the count: returning ``None`` defers to xdist's own hook, which reads it.

    :param config: the pytest configuration
    :type config: pytest.Config
    :return: the number of workers, or None to let xdist decide
    :rtype: Optional[int]
    """
    if os.environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS"):
        return None
    cores = os.cpu_count() or 1
    by_memory = psutil.virtual_memory().available // _WORKER_MEMORY_BYTES
    return max(1, min(cores, int(by_memory)))


@pytest.fixture(autouse=True)
def destroy_windows_after_each_test():
    """
    Delete every window a test leaves behind, and fail the test if one survives.

    This is root-level because the ``QApplication`` is shared by the whole session: a
    window left alive in one directory slows every test in every directory after it.
    It is autouse and declared here, so it is torn down after every fixture a test
    asks for - a triad has stopped its workers before its windows go.
    """
    yield
    survivors = destroy_leftover_windows()
    if survivors:
        pytest.fail(f"Windows still alive after the cleanup: {survivors}")


# ===========================================================================
# Real recordings on a developer's machine
# ===========================================================================
#
# Real lab recordings are gigabytes each and never enter the repository. A test
# that needs one is marked ``real_data`` and takes this fixture, which resolves
# the directory ``PORISCOPE_REAL_DATA_DIR`` names and skips the test wherever the
# variable is unset or points nowhere - so CI, which has no such directory, skips
# the whole tier without a failure, and a developer with the recordings runs it
# by setting one variable.


@pytest.fixture(scope="session")
def real_data_dir() -> Path:
    """
    Return the directory of real recordings, or skip when none is configured.

    :return: the directory ``PORISCOPE_REAL_DATA_DIR`` names
    :rtype: pathlib.Path
    """
    configured = os.environ.get("PORISCOPE_REAL_DATA_DIR")
    if not configured:
        pytest.skip("PORISCOPE_REAL_DATA_DIR is not set; real-recording tests need it")
    directory = Path(configured)
    if not directory.is_dir():
        pytest.skip(f"PORISCOPE_REAL_DATA_DIR={configured!r} is not a directory")
    return directory


# ===========================================================================
# Path-derived markers
# ===========================================================================
#
# `e2e` and `integration` describe *where a test lives*, not something a test
# author decides per function, so they are derived from the path rather than
# hand-applied: a new file under tests/e2e/ carries the marker the moment it is
# added, with nothing to remember and nothing to keep in sync.
#
# `compliance`, `smoke` and `e2e_ux` stay hand-applied: they are genuine
# per-test choices that no directory implies.
_PATH_MARKERS = (
    ("/tests/e2e/", "e2e"),
    ("/tests/integration/", "integration"),
)

_ITEM_MARKERS: "dict[str, list[str]]" = {}
_ITEM_DURATIONS: "defaultdict[str, float]" = defaultdict(float)


def pytest_addoption(parser):
    """Register the --marker-stats reporting flag."""
    parser.addoption(
        "--marker-stats",
        action="store_true",
        default=False,
        help="After the run, print test count and mean duration per marker.",
    )


def pytest_collection_modifyitems(items):
    """Apply path-derived markers and index each test's markers for reporting."""
    for item in items:
        path = str(getattr(item, "path", item.fspath)).replace("\\", "/")
        for fragment, marker in _PATH_MARKERS:
            if fragment in path:
                item.add_marker(getattr(pytest.mark, marker))
        _ITEM_MARKERS[item.nodeid] = sorted({m.name for m in item.iter_markers()})


def pytest_runtest_logreport(report):
    """Accumulate setup + call + teardown time per test, for --marker-stats."""
    _ITEM_DURATIONS[report.nodeid] += report.duration


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print per-marker test counts and mean durations when --marker-stats is set."""
    if not config.getoption("--marker-stats"):
        return

    # Report only the project's own markers, read straight from pytest.ini, so
    # this stays correct when a marker is added or removed and does not drown in
    # pytest builtins (parametrize, skip, timeout, usefixtures...).
    declared = {
        line.split(":", 1)[0].strip()
        for line in config.getini("markers")
        if line.strip()
    }

    counts: "defaultdict[str, int]" = defaultdict(int)
    totals: "defaultdict[str, float]" = defaultdict(float)
    for nodeid, markers in _ITEM_MARKERS.items():
        duration = _ITEM_DURATIONS.get(nodeid, 0.0)
        own = [m for m in markers if m in declared]
        for marker in own or ["(no project marker)"]:
            counts[marker] += 1
            totals[marker] += duration

    if not counts:
        return

    grand = sum(_ITEM_DURATIONS.values())
    terminalreporter.write_sep("=", "marker stats")
    terminalreporter.write_line(
        f"{'marker':<16}{'tests':>8}{'total_s':>10}{'mean_s':>9}{'% time':>9}"
    )
    for marker in sorted(counts, key=lambda m: -totals[m]):
        n, total = counts[marker], totals[marker]
        share = (100 * total / grand) if grand else 0.0
        terminalreporter.write_line(
            f"{marker:<16}{n:>8}{total:>10.1f}{total / n:>9.3f}{share:>8.1f}%"
        )
    terminalreporter.write_line(
        f"{'ALL':<16}{len(_ITEM_DURATIONS):>8}{grand:>10.1f}"
        f"{grand / max(len(_ITEM_DURATIONS), 1):>9.3f}{100.0:>8.1f}%"
    )
    terminalreporter.write_line(
        "Note: a test counts once per marker it carries, so marker rows overlap "
        "and do not sum to ALL."
    )
