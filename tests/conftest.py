"""Project-wide test fixtures.

Poriscope resolves its config, session and log directories through
``platformdirs.user_data_dir()``, so anything that builds a real ``MainModel``
writes into the developer's actual ``%LOCALAPPDATA%/Poriscope`` profile and can
overwrite their real saved session and tab-action history.

Every place that currently does so already redirects that call for itself -
``tests/e2e/conftest.py``'s autouse ``sandbox_appdata`` covers the whole e2e
tree, and ``tests/unit/models/conftest.py``'s ``main_model`` fixture covers the
model tests. This fixture makes the redirection an inherited default rather
than a convention each area has to remember, so a test added anywhere else
cannot reach real user state. Both existing fixtures still run after this one
and deliberately override it with their own roots, because their assertions
depend on the specific layout they build.
"""

import sys
from collections import defaultdict

import pytest


@pytest.fixture(autouse=True)
def sandbox_user_data_dir(monkeypatch, tmp_path):
    """
    Point ``platformdirs.user_data_dir()`` at a per-test temporary directory.

    :param monkeypatch: pytest's monkeypatch fixture.
    :type monkeypatch: pytest.MonkeyPatch
    :param tmp_path: pytest's per-test temporary directory.
    :type tmp_path: pathlib.Path
    """
    appdata_root = tmp_path / "appdata"
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
