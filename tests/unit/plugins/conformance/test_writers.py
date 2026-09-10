"""
Behavioural conformance for the two writer families.

``MetaWriter`` stores located events; ``MetaDatabaseWriter`` stores fitted event
metadata. Both sit at the end of a real plugin chain, so both are driven here through
one: reader to finder to writer, and loader to fitter to database writer.

A writer is the one family where "it did not raise" is especially weak evidence -
SQLite will happily accept a commit that produced no rows. Each family is therefore
checked for having written the expected number of events, for passing SQLite's own
integrity check, and for being *readable back* by the matching loader, which is the
only thing that proves the file is usable rather than merely present.

The read-back also doubles as a resource-leak check: on Windows an open handle blocks
``os.unlink``, so unlinking the output after ``close_resources()`` proves the writer
let go of it. That is stricter than inspecting the process's open files, and needs no
extra dependency.
"""

import sqlite3
from pathlib import Path
from typing import List, Type

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.utils.MetaDatabaseWriter import MetaDatabaseWriter
from poriscope.utils.MetaWriter import MetaWriter
from tests.unit.plugins.conformance._recipes import (
    CHIMERA_CHANNEL,
    CHIMERA_EVENTS,
    EVENTS_CHANNEL,
    EVENTS_COUNT,
    build_db_loader,
    build_db_writer,
    build_event_finder,
    build_event_fitter,
    build_event_loader,
    build_reader,
    build_writer,
    discover_concrete,
)

WRITERS: List[Type[MetaWriter]] = discover_concrete(MetaWriter)
DB_WRITERS: List[Type[MetaDatabaseWriter]] = discover_concrete(MetaDatabaseWriter)


def identity(data):
    """
    Return data unchanged, standing in for a filter.

    :param data: The chunk handed over by the caller.
    :type data: numpy.ndarray
    :return: The same chunk.
    :rtype: numpy.ndarray
    """
    return data


def describe_database(path: Path) -> dict:
    """
    Read back a written database without leaving a handle open.

    ``sqlite3``'s context manager commits a transaction; it does **not** close the
    connection, so it is closed explicitly here. Getting this wrong makes the caller
    look like the leaking party.

    :param path: Path to the SQLite file to inspect.
    :type path: Path
    :return: Its integrity verdict, table names and event-row count.
    :rtype: dict
    """
    connection = sqlite3.connect(str(path))
    try:
        cursor = connection.cursor()
        integrity = cursor.execute("PRAGMA integrity_check;").fetchone()[0]
        tables = {
            row[0]
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        events = cursor.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    finally:
        connection.close()
    return {"integrity": integrity, "tables": tables, "events": events}


# ===========================================================================
# MetaWriter: reader -> finder -> writer
# ===========================================================================


@pytest.fixture(params=WRITERS, ids=[cls.__name__ for cls in WRITERS])
def committed(request, chimera_log_path, tmp_path):
    """
    Drive a full reader/finder/writer chain and commit the located events.

    :param request: Pytest request, carrying the parametrised writer class.
    :type request: pytest.FixtureRequest
    :param chimera_log_path: Path to the synthetic Chimera recording.
    :type chimera_log_path: str
    :param tmp_path: Per-test temporary directory for the writer's output.
    :type tmp_path: pathlib.Path
    :return: The writer and the path it wrote to.
    :rtype: tuple
    """
    reader = build_reader(chimera_log_path)
    finder = build_event_finder(ClassicBlockageFinder, reader)
    for _progress in finder.find_events(CHIMERA_CHANNEL, [(0.0, 0.0)], 3.0, identity):
        pass

    out_path = tmp_path / "committed.sqlite3"
    writer = build_writer(request.param, finder, str(out_path))
    for _progress in writer.commit_events(CHIMERA_CHANNEL):
        pass

    yield writer, out_path
    writer.close_resources()
    finder.close_resources()
    reader.close_resources()


@pytest.mark.conformance
def test_writer_produces_a_readable_database(committed) -> None:
    """
    A writer stores every located event in a database that passes integrity check.

    :param committed: Writer and output path from the fixture.
    :type committed: tuple
    """
    writer, out_path = committed

    assert out_path.exists() and out_path.stat().st_size > 0, "no output written"
    assert (
        Path(writer.get_output_file_name()).name == out_path.name
    ), "get_output_file_name does not name the file that was written"

    described = describe_database(out_path)
    assert described["integrity"] == "ok", f"integrity: {described['integrity']}"
    assert {"channels", "events", "columns"}.issubset(
        described["tables"]
    ), f"unexpected schema: {sorted(described['tables'])}"
    assert described["events"] == CHIMERA_EVENTS, (
        f"wrote {described['events']} of {CHIMERA_EVENTS} located events:"
        f"\n{writer.report_channel_status()}"
    )


@pytest.mark.conformance
def test_written_events_round_trip_through_a_loader(committed) -> None:
    """
    An event loader reads back exactly what the writer stored.

    This is the seam the writer exists to serve. Checking the row count alone would
    not catch a writer that stored events the loader cannot interpret.

    :param committed: Writer and output path from the fixture.
    :type committed: tuple
    """
    _writer, out_path = committed

    loader = build_event_loader(str(out_path))
    try:
        channels = loader.get_channels()
        assert (
            CHIMERA_CHANNEL in channels
        ), f"writer stored channel {CHIMERA_CHANNEL} but loader sees {channels}"
        assert loader.get_num_events(CHIMERA_CHANNEL) == CHIMERA_EVENTS
        event = loader.load_event(CHIMERA_CHANNEL, 0, None)
        assert event["data"].size > 0, "round-tripped event has no data"
    finally:
        loader.close_resources()


@pytest.mark.conformance
def test_writer_releases_its_output_file(committed) -> None:
    """
    ``close_resources`` lets go of the output file.

    On Windows an open handle blocks ``os.unlink``, so this is a real leak check
    rather than a formality; on POSIX it degrades to asserting the file existed.

    :param committed: Writer and output path from the fixture.
    :type committed: tuple
    """
    writer, out_path = committed

    writer.close_resources()
    try:
        out_path.unlink()
    except PermissionError as exc:
        pytest.fail(f"output still locked after close_resources: {exc}")


# ===========================================================================
# MetaDatabaseWriter: loader -> fitter -> database writer
# ===========================================================================


@pytest.fixture(params=DB_WRITERS, ids=[cls.__name__ for cls in DB_WRITERS])
def written(request, events_db_path, tmp_path):
    """
    Drive a full loader/fitter/database-writer chain and write the fitted metadata.

    :param request: Pytest request, carrying the parametrised writer class.
    :type request: pytest.FixtureRequest
    :param events_db_path: Path to the shared synthetic events database.
    :type events_db_path: str
    :param tmp_path: Per-test temporary directory for the writer's output.
    :type tmp_path: pathlib.Path
    :return: The writer and the path it wrote to.
    :rtype: tuple
    """
    loader = build_event_loader(events_db_path)
    fitter = build_event_fitter(CUSUM, loader)
    for _progress in fitter.fit_events(EVENTS_CHANNEL):
        pass

    out_path = tmp_path / "metadata.sqlite3"
    writer = build_db_writer(request.param, fitter, str(out_path))
    for _progress in writer.write_events(EVENTS_CHANNEL):
        pass

    yield writer, out_path
    writer.close_resources()
    fitter.close_resources()
    loader.close_resources()


@pytest.mark.conformance
def test_db_writer_produces_a_readable_database(written) -> None:
    """
    A database writer stores every fitted event, with the sublevel tables present.

    :param written: Writer and output path from the fixture.
    :type written: tuple
    """
    writer, out_path = written

    assert out_path.exists() and out_path.stat().st_size > 0, "no output written"

    described = describe_database(out_path)
    assert described["integrity"] == "ok", f"integrity: {described['integrity']}"
    assert {"experiments", "channels", "events", "sublevels"}.issubset(
        described["tables"]
    ), f"unexpected schema: {sorted(described['tables'])}"
    assert described["events"] == EVENTS_COUNT, (
        f"wrote {described['events']} of {EVENTS_COUNT} fitted events:"
        f"\n{writer.report_channel_status()}"
    )


@pytest.mark.conformance
def test_written_metadata_round_trips_through_a_db_loader(written) -> None:
    """
    A database loader reads back the experiment and channel the writer stored.

    The metadata tab opens exactly this file, so this is the seam that decides
    whether an analysis is usable after fitting.

    :param written: Writer and output path from the fixture.
    :type written: tuple
    """
    _writer, out_path = written

    loader = build_db_loader(SQLiteDBLoader, str(out_path))
    try:
        names = loader.get_experiment_names()
        assert names, "database writer produced no readable experiment"
        channels = loader.get_channels_by_experiment(names[0])
        assert (
            channels and EVENTS_CHANNEL in channels
        ), f"writer stored channel {EVENTS_CHANNEL} but loader sees {channels}"
        columns = loader.get_column_names_by_table("events")
        assert columns, "no event columns readable from the written database"
    finally:
        loader.close_resources()


@pytest.mark.conformance
def test_db_writer_releases_its_output_file(written) -> None:
    """
    ``close_resources`` lets go of the output file.

    :param written: Writer and output path from the fixture.
    :type written: tuple
    """
    writer, out_path = written

    writer.close_resources()
    try:
        out_path.unlink()
    except PermissionError as exc:
        pytest.fail(f"output still locked after close_resources: {exc}")


@pytest.mark.conformance
def test_both_writer_families_were_discovered() -> None:
    """Guard against either discovery walk silently finding nothing."""
    assert WRITERS, "no concrete MetaWriter subclasses were discovered"
    assert DB_WRITERS, "no concrete MetaDatabaseWriter subclasses were discovered"
