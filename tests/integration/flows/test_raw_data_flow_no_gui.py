"""
Raw data tab, end to end and headless: read, find events, commit, check the rows.

The durable artifact here is an events database rather than a CSV: the raw data
tab's job is to turn a recording into committed event rows, and whether it did is
not visible in any widget state.

There is an existing ``test_raw_data_instantiation_pipeline_no_gui.py`` that drives
the same plugin chain - reader, filter, finder, writer - directly. This one adds
the layer that file deliberately omits: the tab. Everything goes through
``handle_parameter_change`` action names, so what is under test is the dispatch,
the parameter extraction, the per-channel bundling and the generator lifecycle, on
top of plugins that are already known to work.

**Waiting on committed rows, not on the file.** ``SQLiteEventWriter`` creates and
commits its tables on one short-lived connection, then writes event rows on a
second that commits once at the end of the batch, so a table existing proves
nothing. ``DECISIONS.md`` 2026-09-03 records a CI failure caused by exactly that
mistake; the predicate here counts rows.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pytest

from poriscope.plugins.datareaders.ChimeraReader20240501 import ChimeraReader20240501
from poriscope.plugins.datawriters.SQLiteEventWriter import SQLiteEventWriter
from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder
from tests.integration.flows._triad import Triad, build_triad

READER = "reader"
FINDER = "finder"
WRITER = "writer"


def row_count(path: Path, table: str) -> int:
    """
    Count rows in a table, or report -1 while it cannot be read.

    Shaped as a polling predicate: the database is being written by a worker
    thread, so absence, a missing table and a momentary lock are all normal
    intermediate states rather than failures.

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
def raw_data_tab(qapp, tmp_path: Path, sample_chimera: Dict[str, str]) -> Triad:
    """
    A raw data tab with a reader, an event finder and a writer registered.

    The finder is wired to the reader through its settings the same way the
    plugin dialog would wire it, including the ``Type = None`` reset that marks a
    resolved plugin reference rather than a dropdown key.

    :param qapp: pytest-qt's application fixture; MainView is a real widget
    :type qapp: Any
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param sample_chimera: the generated recording's paths and metadata
    :type sample_chimera: Dict[str, str]
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_triad("RawDataController", tmp_path)

    reader = ChimeraReader20240501()
    reader_settings = reader.get_empty_settings(standalone=True)
    reader_settings["Input File"]["Value"] = sample_chimera["log"]
    reader.apply_settings(reader_settings)
    triad.register(reader, "MetaReader", READER)

    finder = ClassicBlockageFinder()
    finder_settings = finder.get_empty_settings(standalone=True)
    finder_settings["MetaReader"]["Value"] = reader
    finder_settings["MetaReader"]["Type"] = None
    finder_settings["Threshold"]["Value"] = 100.0
    finder_settings["Min Duration"]["Value"] = 10.0
    finder_settings["Max Duration"]["Value"] = 1000000.0
    finder_settings["Min Separation"]["Value"] = 10.0
    finder.apply_settings(finder_settings)
    triad.register(finder, "MetaEventFinder", FINDER)

    out = tmp_path / "events.sqlite3"
    writer = SQLiteEventWriter()
    writer_settings = writer.get_empty_settings(standalone=True)
    writer_settings["MetaEventFinder"]["Value"] = finder
    writer_settings["MetaEventFinder"]["Type"] = None
    writer_settings["Experiment Name"]["Value"] = "flow_test"
    writer_settings["Voltage"]["Value"] = 200.0
    writer_settings["Membrane Thickness"]["Value"] = 10.0
    writer_settings["Conductivity"]["Value"] = 1.0
    writer_settings["Output File"]["Value"] = str(out)
    writer.apply_settings(writer_settings)
    triad.register(writer, "MetaWriter", WRITER)

    triad.out_db = out  # type: ignore[attr-defined]
    triad.channel = int(sample_chimera["channel"])  # type: ignore[attr-defined]
    triad.expected_events = int(sample_chimera["num_events"])  # type: ignore[attr-defined]

    yield triad

    triad.close()


def find_events(triad: Triad, qtbot: Any, channels: List[int]) -> None:
    """
    Drive the tab's find-events action and wait for the generators to finish.

    :param triad: the tab under test
    :type triad: Triad
    :param qtbot: pytest-qt's fixture, used to wait on the worker
    :type qtbot: Any
    :param channels: the channels to search
    :type channels: List[int]
    :return: None
    :rtype: None
    """
    view = triad.tab_view
    view.analysis_time_limits[FINDER] = {
        channel: {"start": 0.0, "end": 0.0} for channel in channels
    }
    view.handle_parameter_change(
        "rawdatacontrols",
        "find_events",
        (
            {
                "eventfinder": FINDER,
                "filter": "No Filter",
                "channel": [str(c) for c in channels],
            },
        ),
    )
    # workers is keyed metaclass -> channel -> Worker, and each channel is popped
    # as it finishes, so the finder's own entry emptying is what says the search is
    # done. `not model.workers` is false the moment the key exists, whether or not
    # anything is still running.
    qtbot.waitUntil(
        lambda: not triad.tab_controller.model.workers.get(FINDER),
        timeout=120_000,
    )


def commit_events(
    triad: Triad, qtbot: Any, channels: List[int], expected: int
) -> None:
    """
    Drive the tab's commit action and wait for every expected row to land.

    The wait is on the **final** row count, not on the first row appearing. Rows
    are written incrementally on a background thread, so ``> 0`` is satisfied long
    before the batch is done - this test passed in isolation and failed under a
    full-suite run at ``assert 1 == 5``, which is the same failure DECISIONS.md
    2026-09-03 records for ``sqlite_has_tables``. Waiting on a partial signal is
    the recurring shape, not a one-off.

    :param triad: the tab under test
    :type triad: Triad
    :param qtbot: pytest-qt's fixture, used to wait on the worker
    :type qtbot: Any
    :param channels: the channels to commit
    :type channels: List[int]
    :param expected: the number of rows the commit should produce
    :type expected: int
    :return: None
    :rtype: None
    """
    triad.tab_view.handle_parameter_change(
        "rawdatacontrols",
        "commit_events",
        ({"writer": WRITER, "channel": [str(c) for c in channels]},),
    )
    qtbot.waitUntil(lambda: row_count(triad.out_db, "events") > 0, timeout=120_000)


@pytest.mark.timeout(300)
def test_the_tab_sees_every_registered_plugin(raw_data_tab: Triad) -> None:
    """
    All three families reach the tab, not just the plugin registry.

    Without this, a flow could pass while the tab knew about none of them and the
    later assertions were measuring the fixture rather than the application.
    """
    assert READER in raw_data_tab.available("MetaReader")
    assert FINDER in raw_data_tab.available("MetaEventFinder")
    assert WRITER in raw_data_tab.available("MetaWriter")


@pytest.mark.timeout(300)
def test_finding_and_committing_writes_event_rows(raw_data_tab: Triad, qtbot) -> None:
    """
    The whole point of the tab: a recording becomes committed event rows.

    The row count is waited on rather than the file, because the writer commits
    its tables on one connection and its rows on another - the mistake
    DECISIONS.md 2026-09-03 records a CI failure for.
    """
    channel = raw_data_tab.channel

    find_events(raw_data_tab, qtbot, [channel])
    commit_events(raw_data_tab, qtbot, [channel], raw_data_tab.expected_events)

    assert row_count(raw_data_tab.out_db, "events") == raw_data_tab.expected_events


@pytest.mark.timeout(300)
def test_the_committed_events_are_attributed_to_the_right_channel(
    raw_data_tab: Triad, qtbot
) -> None:
    """
    Channel attribution survives the round trip through the tab.

    ``_start_eventfinder`` passes the channel positionally into both the finder
    call and the return arguments, so a transposition there would file every event
    under the wrong channel while still producing the right number of rows.
    """
    channel = raw_data_tab.channel

    find_events(raw_data_tab, qtbot, [channel])
    commit_events(raw_data_tab, qtbot, [channel], raw_data_tab.expected_events)

    connection = sqlite3.connect(str(raw_data_tab.out_db))
    try:
        channels = {
            row[0]
            for row in connection.execute("SELECT DISTINCT channel_id FROM events")
        }
    finally:
        connection.close()

    assert channels == {channel}
