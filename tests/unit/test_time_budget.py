"""
The per-test time budget in ``tests/conftest.py``: which time counts as a test's own, who is over, and how it reaches the controller.

A test's own time is setup + call + teardown, less setting up a fixture wider than the
function and less the teardown that closes a module or class - both of which pytest bills
to whichever test happens to be first or last, not to the one that caused them. These pin
that subtraction, the tiers, the budgets and the opt-out marker, against the conftest's own
bookkeeping, swapped for a clean set inside each test.

Under ``pytest -n auto`` that bookkeeping lives in a worker and the summary is printed by
the controller, so the worker attaches each test's markers and own time to its teardown
report. The last tests pin that hand-over: what the report carries, that it survives the
serialisation xdist sends it through, and what the controller records from it.
"""

from pathlib import Path
from types import ModuleType

import pytest
from _pytest.reports import TestReport

ROOT_CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"
UNIT = "tests/unit/test_x.py::test_a"
INTEGRATION = "tests/integration/flows/test_y_no_gui.py::test_b"
E2E = "tests/e2e/raw_data/test_z.py::test_c"


@pytest.fixture
def root(pytestconfig) -> ModuleType:
    """
    The loaded ``tests/conftest.py``, with empty bookkeeping for the duration of the test.

    :param pytestconfig: pytest's config, whose plugin manager holds the conftest
    :type pytestconfig: pytest.Config
    :yield: the conftest module
    """
    module = next(
        plugin
        for plugin in pytestconfig.pluginmanager.get_plugins()
        if Path(getattr(plugin, "__file__", "") or "").resolve() == ROOT_CONFTEST
    )
    with pytest.MonkeyPatch.context() as local:
        for name, empty in (
            ("_ITEM_DURATIONS", module.defaultdict(float)),
            ("_PHASE_SECONDS", module.defaultdict(float)),
            ("_TEARDOWN_SECONDS", {}),
            ("_WIDER_FIXTURE_SECONDS", module.defaultdict(float)),
            ("_ENDS_A_SCOPE", set()),
            ("_ITEM_MARKERS", {}),
            ("_OWN_SECONDS", {}),
        ):
            local.setattr(module, name, empty)
        yield module


def teardown_report(nodeid: str, seconds: float) -> TestReport:
    """
    A passed teardown report for ``nodeid``, as pytest makes one.

    :param nodeid: the test's node id
    :type nodeid: str
    :param seconds: the teardown's duration
    :type seconds: float
    :return: the report
    :rtype: TestReport
    """
    return TestReport(
        nodeid=nodeid,
        location=(nodeid.split("::", 1)[0], 0, nodeid),
        keywords={},
        outcome="passed",
        longrepr=None,
        when="teardown",
        duration=seconds,
    )


@pytest.mark.parametrize(
    "nodeid, tier",
    [
        (UNIT, "unit"),
        (INTEGRATION, "integration"),
        (E2E, "e2e"),
        ("tests\\e2e\\raw_data\\test_z.py::test_c", "e2e"),
        ("tests/test_safety_net_is_armed.py::test_d", "unit"),
    ],
)
def test_a_test_is_budgeted_by_where_it_lives(root, nodeid, tier):
    assert root._tier(nodeid) == tier


def test_own_time_is_the_whole_of_an_ordinary_test(root):
    root._PHASE_SECONDS[UNIT] = 2.5
    root._TEARDOWN_SECONDS[UNIT] = 0.5
    assert root.own_seconds(UNIT) == 2.5


def test_setting_up_a_wider_fixture_is_not_the_test_s_own_time(root):
    """The first test to ask for a session database does not pay for building it."""
    root._PHASE_SECONDS[UNIT] = 9.0
    root._WIDER_FIXTURE_SECONDS[UNIT] = 8.0
    assert root.own_seconds(UNIT) == pytest.approx(1.0)


def test_a_teardown_that_closes_a_module_is_not_the_test_s_own_time(root):
    """The last test in a module also finalises the module's fixtures in its teardown."""
    root._PHASE_SECONDS[UNIT] = 7.0
    root._TEARDOWN_SECONDS[UNIT] = 6.0
    root._ENDS_A_SCOPE.add(UNIT)
    assert root.own_seconds(UNIT) == pytest.approx(1.0)


def test_each_tier_is_held_to_its_own_budget(root, pytestconfig):
    """Defaults: unit 5 s, integration 20 s, e2e 60 s - each test just over its own."""
    root._OWN_SECONDS.update({UNIT: 5.1, INTEGRATION: 20.1, E2E: 60.1})
    root._OWN_SECONDS["tests/unit/test_x.py::test_fast"] = 4.9
    root._OWN_SECONDS["tests/integration/flows/test_y_no_gui.py::test_ok"] = 19.0

    found = root.over_budget(pytestconfig)

    assert [(nodeid, budget) for nodeid, _, budget in found] == [
        (E2E, 60.0),
        (INTEGRATION, 20.0),
        (UNIT, 5.0),
    ]


def test_a_test_marked_exceeds_time_budget_is_not_reported(root, pytestconfig):
    root._OWN_SECONDS[UNIT] = 50.0
    root._ITEM_MARKERS[UNIT] = ["exceeds_time_budget"]
    assert root.over_budget(pytestconfig) == []


def test_the_teardown_report_carries_the_test_s_markers_and_own_time(root, request):
    """Where the bookkeeping is - a worker, or the one process of a serial run."""
    nodeid = request.node.nodeid
    root._PHASE_SECONDS[nodeid] = 30.0
    root._WIDER_FIXTURE_SECONDS[nodeid] = 28.0

    wrapper = root.pytest_runtest_makereport(request.node, None)
    next(wrapper)
    with pytest.raises(StopIteration) as done:
        wrapper.send(teardown_report(nodeid, 0.5))
    report = done.value.value

    assert report.poriscope_own_seconds == pytest.approx(2.5)
    assert report.poriscope_markers == sorted(
        {m.name for m in request.node.iter_markers()}
    )


def test_the_report_leaves_out_a_teardown_that_closes_a_module(root, request):
    """The teardown being reported is the one subtracted, so it must be known before the sum."""
    nodeid = request.node.nodeid
    root._PHASE_SECONDS[nodeid] = 1.0
    root._ENDS_A_SCOPE.add(nodeid)

    wrapper = root.pytest_runtest_makereport(request.node, None)
    next(wrapper)
    with pytest.raises(StopIteration) as done:
        wrapper.send(teardown_report(nodeid, 6.0))

    assert done.value.value.poriscope_own_seconds == pytest.approx(1.0)


@pytest.mark.characterization
def test_a_marker_on_the_test_reaches_its_report(root, request):
    """The opt-out marker travels the same way, which is what lets the controller honour it."""
    wrapper = root.pytest_runtest_makereport(request.node, None)
    next(wrapper)
    with pytest.raises(StopIteration) as done:
        wrapper.send(teardown_report(request.node.nodeid, 0.0))
    assert "characterization" in done.value.value.poriscope_markers


def test_what_the_report_carries_survives_xdist_and_is_recorded(root, pytestconfig):
    """
    xdist sends a worker's report through these two hooks; the controller logs what arrives.

    Without the hand-over the controller would record no own time and no markers, so a
    test marked exceeds_time_budget would still be reported under ``-n auto``.
    """
    report = teardown_report(UNIT, 0.5)
    report.poriscope_own_seconds = 50.0
    report.poriscope_markers = ["exceeds_time_budget", "integration"]

    sent = pytestconfig.hook.pytest_report_to_serializable(
        config=pytestconfig, report=report
    )
    received = pytestconfig.hook.pytest_report_from_serializable(
        config=pytestconfig, data=sent
    )
    root.pytest_runtest_logreport(received)

    assert root._OWN_SECONDS == {UNIT: 50.0}
    assert root._ITEM_MARKERS == {UNIT: ["exceeds_time_budget", "integration"]}
    assert root.over_budget(pytestconfig) == []


class _Lines:
    """Stand-in for pytest's terminal reporter: keeps what the report writes."""

    def __init__(self) -> None:
        self.lines: list = []

    def write_sep(self, sep: str, title: str) -> None:
        self.lines.append(title)

    def write_line(self, line: str) -> None:
        self.lines.append(line)


def test_marker_stats_count_the_project_s_markers_and_no_builtin(root, pytestconfig):
    """``parametrize`` is pytest's, registered with arguments; only pytest.ini's are counted."""
    root._ITEM_MARKERS.update(
        {UNIT: ["characterization", "parametrize"], E2E: ["e2e", "timeout"]}
    )
    root._ITEM_DURATIONS.update({UNIT: 1.0, E2E: 3.0})
    out = _Lines()

    root._report_marker_stats(out, pytestconfig)

    rows = {line.split()[0] for line in out.lines[2:-1]}
    assert rows == {"characterization", "e2e", "ALL"}


def test_a_report_without_the_attributes_records_no_own_time(root):
    """A report from elsewhere - a plugin's own, say - is counted by duration only."""
    root.pytest_runtest_logreport(teardown_report(UNIT, 0.5))
    assert root._OWN_SECONDS == {}
    assert root._ITEM_MARKERS == {UNIT: []}
    assert root._ITEM_DURATIONS[UNIT] == 0.5
