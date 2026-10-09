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

import shutil
import sqlite3
from pathlib import Path
from typing import List, Type

import numpy as np
import pytest

from poriscope.plugins.datareaders.SingleBinaryDecoder import SingleBinaryDecoder
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
    _fill,
    assert_reports_whole_and_each_channel,
    build_db_loader,
    build_db_writer,
    build_event_finder,
    build_event_fitter,
    build_event_loader,
    build_reader,
    build_reader_dataset,
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
        f"\n{writer.report_status()}"
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


def event_starts(path: Path, channel: int) -> List[int]:
    """
    List the stored event starts for one channel, closing the connection after.

    :param path: Path to the SQLite file to inspect.
    :type path: Path
    :param channel: The physical channel to list.
    :type channel: int
    :return: The ``absolute_start`` of each stored event, in order.
    :rtype: List[int]
    """
    connection = sqlite3.connect(str(path))
    try:
        rows = connection.execute(
            "SELECT absolute_start FROM events WHERE channel_id = ? ORDER BY event_id",
            (channel,),
        ).fetchall()
    finally:
        connection.close()
    return [row[0] for row in rows]


@pytest.mark.conformance
def test_a_second_commit_into_a_held_channel_is_refused(committed) -> None:
    """
    Committing a channel the output already holds fails loudly and changes nothing.

    The writer used to accept the commit, silently keep the old events through
    ``INSERT OR IGNORE`` and report "Wrote 0/N" - or, with more events the second
    time, keep the old ones and add the rest. Without ``overwrite`` there is no way to
    tell which run the file should reflect, so it refuses.

    :param committed: Writer and output path from the fixture.
    :type committed: tuple
    """
    writer, out_path = committed
    before = event_starts(out_path, CHIMERA_CHANNEL)

    with pytest.raises(ValueError, match="already holds events"):
        for _progress in writer.commit_events(CHIMERA_CHANNEL):
            pass

    assert event_starts(out_path, CHIMERA_CHANNEL) == before
    assert writer.written[CHIMERA_CHANNEL] == 0, "a refused commit reports writes"


@pytest.mark.conformance
def test_overwrite_replaces_only_that_channel(committed) -> None:
    """
    ``overwrite=True`` replaces the channel's events and leaves other channels alone.

    Another channel's row is planted by hand, standing in for a second run filed in
    the same file, so a reset that deleted more than its own channel would show.

    :param committed: Writer and output path from the fixture.
    :type committed: tuple
    """
    writer, out_path = committed
    other = CHIMERA_CHANNEL + 100
    connection = sqlite3.connect(str(out_path))
    try:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.execute(
            "INSERT INTO channels (name, channel_id, voltage, thickness, "
            "conductivity, samplerate, data_format) VALUES ('other', ?, 1, 1, 1, 1, '<f8')",
            (other,),
        )
        channel_db_id = connection.execute(
            "SELECT id FROM channels WHERE channel_id = ?", (other,)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO events (channel_db_id, channel_id, event_id, absolute_start, "
            "padding_before, padding_after, baseline_mean, baseline_std, raw_data) "
            "VALUES (?, ?, 0, 7, 0, 0, 0, 0, x'00')",
            (channel_db_id, other),
        )
        connection.commit()
    finally:
        connection.close()
    before = event_starts(out_path, CHIMERA_CHANNEL)

    for _progress in writer.commit_events(CHIMERA_CHANNEL, overwrite=True):
        pass

    assert event_starts(out_path, CHIMERA_CHANNEL) == before
    assert writer.written[CHIMERA_CHANNEL] == CHIMERA_EVENTS
    assert event_starts(out_path, other) == [7], "overwrite reached another channel"


@pytest.mark.conformance
@pytest.mark.parametrize("writer_cls", WRITERS, ids=[cls.__name__ for cls in WRITERS])
def test_the_committed_experiment_is_reported_without_creating_a_file(
    writer_cls, chimera_log_path, tmp_path
) -> None:
    """
    A writer names the experiment a channel is filed under, and None before a commit.

    The question is asked before anything is written, so asking must not create the
    output file.

    :param writer_cls: The writer class under test.
    :type writer_cls: Type[MetaWriter]
    :param chimera_log_path: Path to the synthetic Chimera recording.
    :type chimera_log_path: str
    :param tmp_path: Per-test temporary directory.
    :type tmp_path: pathlib.Path
    """
    reader = build_reader(chimera_log_path)
    finder = build_event_finder(ClassicBlockageFinder, reader)
    for _progress in finder.find_events(CHIMERA_CHANNEL, [(0.0, 0.0)], 3.0, identity):
        pass
    out_path = tmp_path / "fresh.sqlite3"
    writer = build_writer(writer_cls, finder, str(out_path))
    try:
        assert writer.get_committed_experiment_name(CHIMERA_CHANNEL) is None
        assert not out_path.exists(), "asking created the output file"

        for _progress in writer.commit_events(CHIMERA_CHANNEL):
            pass
        assert writer.get_committed_experiment_name(CHIMERA_CHANNEL) == "conformance"
        assert writer.get_committed_experiment_name(CHIMERA_CHANNEL + 1) is None
    finally:
        writer.close_resources()
        finder.close_resources()
        reader.close_resources()


@pytest.mark.conformance
@pytest.mark.parametrize("writer_cls", WRITERS, ids=[cls.__name__ for cls in WRITERS])
def test_a_stored_trace_is_the_readers_scaled_data(writer_cls, tmp_path) -> None:
    """
    What a writer stores for an event is exactly what the reader returns for it.

    Every other test here drives a Chimera recording, whose int16 samples can never
    match a float writer's output type. A float64 source can, so it is the case that
    shows whether anything between the reader and the file bypasses the reader's
    Scale and Offset: with both non-trivial, a stored trace that differs from
    ``load_data`` over the same span is one that skipped the scaling, and it would
    disagree with the ``baseline_mean`` stored beside it.

    :param writer_cls: The writer class under test.
    :type writer_cls: Type[MetaWriter]
    :param tmp_path: Per-test temporary directory.
    :type tmp_path: pathlib.Path
    """
    dataset = build_reader_dataset(SingleBinaryDecoder, tmp_path / "data")
    reader = SingleBinaryDecoder()
    settings = reader.get_empty_settings(standalone=True)
    _fill(
        settings,
        {
            "Input File": str(dataset.data_path),
            "Sampling Rate": dataset.samplerate,
            "Scale": 2.0,
            "Offset": 100.0,
        },
        "SingleBinaryDecoder",
    )
    reader.apply_settings(settings)
    reader.report_status(init=True)
    channel = dataset.channel

    finder = build_event_finder(ClassicBlockageFinder, reader)
    for _progress in finder.find_events(channel, [(0.0, 0.0)], 3.0, identity):
        pass
    assert finder.get_num_events_found(channel) > 0, "no events to write"

    out_path = tmp_path / "scaled.sqlite3"
    writer = build_writer(writer_cls, finder, str(out_path))
    for _progress in writer.commit_events(channel):
        pass
    writer.close_resources()

    expected = finder.get_single_event_data(channel, 0)
    assert expected is not None
    loader = build_event_loader(str(out_path))
    try:
        stored = loader.load_event(channel, 0, None)
    finally:
        loader.close_resources()
        finder.close_resources()
        reader.close_resources()

    np.testing.assert_array_equal(stored["data"], expected["data"])


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
        f"\n{writer.report_status()}"
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


# ===========================================================================
# A writer refuses an output file it cannot write into
# ===========================================================================


def _copy(source: str, tmp_path: Path, name: str) -> Path:
    target = tmp_path / name
    shutil.copyfile(source, target)
    return target


def _not_a_database(tmp_path: Path) -> Path:
    target = tmp_path / "notes.sqlite3"
    target.write_text("not a database, just text\n", encoding="utf-8")
    return target


@pytest.fixture
def finder(chimera_log_path):
    """A finder with events located, as an event writer needs."""
    reader = build_reader(chimera_log_path)
    finder = build_event_finder(ClassicBlockageFinder, reader)
    for _progress in finder.find_events(CHIMERA_CHANNEL, [(0.0, 0.0)], 3.0, identity):
        pass
    yield finder
    finder.close_resources()
    reader.close_resources()


@pytest.fixture
def fitter(events_db_path):
    """A fitter attached to an events database, as a database writer needs."""
    loader = build_event_loader(events_db_path)
    fitter = build_event_fitter(CUSUM, loader)
    yield fitter
    fitter.close_resources()
    loader.close_resources()


@pytest.mark.conformance
@pytest.mark.parametrize("writer_cls", WRITERS, ids=[cls.__name__ for cls in WRITERS])
def test_an_event_writer_refuses_a_metadata_database(
    writer_cls, finder, metadata_db_path, tmp_path
) -> None:
    """
    Choosing a fitted-metadata database as an event writer's output is refused up front.

    Both kinds of file have an ``events`` table, so nothing stopped the choice, and the
    writer failed only once it tried to write.
    """
    wrong = _copy(metadata_db_path, tmp_path, "metadata.sqlite3")
    with pytest.raises(ValueError, match="metadata"):
        build_writer(writer_cls, finder, str(wrong))


@pytest.mark.conformance
@pytest.mark.parametrize(
    "writer_cls", DB_WRITERS, ids=[cls.__name__ for cls in DB_WRITERS]
)
def test_a_database_writer_refuses_an_events_database(
    writer_cls, fitter, events_db_path, tmp_path
) -> None:
    """
    Choosing an events database as a metadata writer's output is refused up front.

    It used to be accepted, and every channel then failed on
    ``no such column: experiment_id`` once writing started.
    """
    wrong = _copy(events_db_path, tmp_path, "events.sqlite3")
    with pytest.raises(ValueError, match="events"):
        build_db_writer(writer_cls, fitter, str(wrong))


@pytest.mark.conformance
@pytest.mark.parametrize("writer_cls", WRITERS, ids=[cls.__name__ for cls in WRITERS])
def test_an_event_writer_refuses_a_file_that_is_not_a_database(
    writer_cls, finder, tmp_path
) -> None:
    with pytest.raises(ValueError, match="not an SQLite database"):
        build_writer(writer_cls, finder, str(_not_a_database(tmp_path)))


@pytest.mark.conformance
@pytest.mark.parametrize(
    "writer_cls", DB_WRITERS, ids=[cls.__name__ for cls in DB_WRITERS]
)
def test_a_database_writer_refuses_a_file_that_is_not_a_database(
    writer_cls, fitter, tmp_path
) -> None:
    with pytest.raises(ValueError, match="not an SQLite database"):
        build_db_writer(writer_cls, fitter, str(_not_a_database(tmp_path)))


@pytest.mark.conformance
@pytest.mark.parametrize("writer_cls", WRITERS, ids=[cls.__name__ for cls in WRITERS])
def test_an_event_writer_accepts_an_existing_events_database(
    writer_cls, finder, events_db_path, tmp_path
) -> None:
    """Its own kind of file is accepted: re-committing into one is intended."""
    own = _copy(events_db_path, tmp_path, "events.sqlite3")
    writer = build_writer(writer_cls, finder, str(own))
    writer.close_resources()


@pytest.mark.conformance
@pytest.mark.parametrize(
    "writer_cls", DB_WRITERS, ids=[cls.__name__ for cls in DB_WRITERS]
)
def test_a_database_writer_accepts_an_existing_metadata_database(
    writer_cls, fitter, metadata_db_path, tmp_path
) -> None:
    """Its own kind of file is accepted: appending experiments to one is intended."""
    own = _copy(metadata_db_path, tmp_path, "metadata.sqlite3")
    writer = build_db_writer(writer_cls, fitter, str(own))
    writer.close_resources()


@pytest.mark.conformance
def test_the_status_report_covers_the_writer_and_each_channel(committed) -> None:
    """
    An event writer reports on itself as a whole and on any one channel.

    :param committed: Writer and output path from the fixture.
    :type committed: tuple
    """
    writer, _out_path = committed
    assert_reports_whole_and_each_channel(writer, CHIMERA_CHANNEL)


@pytest.mark.conformance
def test_the_status_report_covers_the_db_writer_and_each_channel(written) -> None:
    """
    A database writer reports on itself as a whole and on any one channel.

    :param written: Writer and output path from the fixture.
    :type written: tuple
    """
    writer, _out_path = written
    assert_reports_whole_and_each_channel(writer, EVENTS_CHANNEL)
