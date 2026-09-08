"""
Event analysis tab, end to end and headless: load, fit, commit, check the rows.

The tab's job is to turn found events into fitted metadata, so the durable
artifact is a metadata database. ``test_event_analysis_instantiation_pipeline_no_gui.py``
already drives the same loader/fitter/writer chain directly; this adds the layer
it omits - the tab's dispatch, parameter extraction and generator lifecycle.

Both waits follow the shape the raw data flow had to learn twice. The fitter's own
entry in ``model.workers`` emptying is what says fitting finished, because
``workers`` is keyed metaclass then channel and ``not workers`` is true only before
the first key appears. And the commit waits on the **final** row count rather than
the first row, because rows land incrementally on a worker thread - waiting on
``> 0`` passes in isolation and fails under a full-suite run.
"""

import sqlite3
from pathlib import Path
from typing import Any, List

import pytest

from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.plugins.eventloaders.SQLiteEventLoader import SQLiteEventLoader
from tests.integration.flows._triad import Triad, build_triad

LOADER = "events"
FITTER = "fitter"
WRITER = "writer"


def row_count(path: Path, table: str) -> int:
    """
    Count rows in a table, or report -1 while it cannot be read.

    :param path: the database file
    :type path: Path
    :param table: the table to count
    :type table: str
    :return: the row count, or -1 if it cannot currently be read
    :rtype: int
    """
    if not path.exists():
        return -1
    try:
        connection = sqlite3.connect(str(path))
        try:
            names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if table not in names:
                return -1
            return int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
        finally:
            connection.close()
    except sqlite3.Error:
        return -1


@pytest.fixture
def event_analysis_tab(qapp, tmp_path: Path, sample_events_db: str) -> Triad:
    """
    An event analysis tab with a loader, a CUSUM fitter and a writer registered.

    :param qapp: pytest-qt's application fixture; MainView is a real widget
    :type qapp: Any
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param sample_events_db: path to a generated events database
    :type sample_events_db: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_triad("EventAnalysisController", tmp_path)

    loader = SQLiteEventLoader()
    loader_settings = loader.get_empty_settings(standalone=True)
    loader_settings["Input File"]["Value"] = sample_events_db
    loader.apply_settings(loader_settings)
    triad.register(loader, "MetaEventLoader", LOADER)

    fitter = CUSUM()
    fitter_settings = fitter.get_empty_settings(standalone=True)
    fitter_settings["MetaEventLoader"]["Value"] = loader
    fitter_settings["MetaEventLoader"]["Type"] = None
    fitter_settings["Max Sublevels"]["Value"] = 10
    fitter_settings["Rise Time"]["Value"] = 10.0
    fitter_settings["Step Size"]["Value"] = 100.0
    fitter_settings["Sensitivity"]["Value"] = 1.0
    fitter.apply_settings(fitter_settings)
    triad.register(fitter, "MetaEventFitter", FITTER)

    out = tmp_path / "metadata.sqlite3"
    writer = SQLiteDBWriter()
    writer_settings = writer.get_empty_settings(standalone=True)
    writer_settings["MetaEventFitter"]["Value"] = fitter
    writer_settings["MetaEventFitter"]["Type"] = None
    writer_settings["Experiment Name"]["Value"] = "flow_test"
    writer_settings["Voltage"]["Value"] = 200.0
    writer_settings["Membrane Thickness"]["Value"] = 10.0
    writer_settings["Conductivity"]["Value"] = 1.0
    writer_settings["Output File"]["Value"] = str(out)
    writer.apply_settings(writer_settings)
    triad.register(writer, "MetaDatabaseWriter", WRITER)

    triad.out_db = out  # type: ignore[attr-defined]

    yield triad

    triad.close()


def fit_events(triad: Triad, qtbot: Any, channels: List[int]) -> None:
    """
    Drive the tab's fit action and wait for the fitters to finish.

    :param triad: the tab under test
    :type triad: Triad
    :param qtbot: pytest-qt's fixture, used to wait on the worker
    :type qtbot: Any
    :param channels: the channels to fit
    :type channels: List[int]
    :return: None
    :rtype: None
    """
    triad.tab_view.handle_parameter_change(
        "eventAnalysisControls",
        "fit_events",
        (
            {
                "eventfitter": FITTER,
                "filter": "No Filter",
                "channel": [str(c) for c in channels],
            },
        ),
    )
    qtbot.waitUntil(
        lambda: not triad.tab_controller.model.workers.get(FITTER), timeout=120_000
    )


def commit_events(triad: Triad, qtbot: Any, channels: List[int], expected: int) -> None:
    """
    Drive the tab's commit action and wait for every expected row to land.

    :param triad: the tab under test
    :type triad: Triad
    :param qtbot: pytest-qt's fixture, used to wait on the worker
    :type qtbot: Any
    :param channels: the channels to commit
    :type channels: List[int]
    :param expected: the number of event rows the commit should produce
    :type expected: int
    :return: None
    :rtype: None
    """
    triad.tab_view.handle_parameter_change(
        "eventAnalysisControls",
        "commit_events",
        ({"writer": WRITER, "channel": [str(c) for c in channels]},),
    )
    qtbot.waitUntil(
        lambda: row_count(triad.out_db, "events") == expected, timeout=120_000
    )


@pytest.mark.timeout(300)
def test_the_tab_sees_every_registered_plugin(event_analysis_tab: Triad) -> None:
    """All three families reach the tab, not just the plugin registry."""
    assert LOADER in event_analysis_tab.available("MetaEventLoader")
    assert FITTER in event_analysis_tab.available("MetaEventFitter")
    assert WRITER in event_analysis_tab.available("MetaDatabaseWriter")


@pytest.mark.timeout(300)
def test_fitting_and_committing_writes_metadata_rows(
    event_analysis_tab: Triad, qtbot
) -> None:
    """
    The whole point of the tab: found events become fitted metadata rows.

    The synthetic events database holds 25 events on channel 0, so a complete run
    commits 25 event rows with their sublevels beneath them.
    """
    fit_events(event_analysis_tab, qtbot, [0])
    commit_events(event_analysis_tab, qtbot, [0], 25)

    assert row_count(event_analysis_tab.out_db, "events") == 25
    assert row_count(event_analysis_tab.out_db, "sublevels") > 25


@pytest.mark.timeout(300)
def test_the_committed_metadata_carries_its_experiment(
    event_analysis_tab: Triad, qtbot
) -> None:
    """
    The writer's experiment settings reach the database, not just the events.

    A commit that wrote events without their experiment row would leave metadata
    that no later query could scope, which is invisible in an event count.
    """
    fit_events(event_analysis_tab, qtbot, [0])
    commit_events(event_analysis_tab, qtbot, [0], 25)

    connection = sqlite3.connect(str(event_analysis_tab.out_db))
    try:
        names = [row[0] for row in connection.execute("SELECT name FROM experiments")]
    finally:
        connection.close()

    assert names == ["flow_test"]
