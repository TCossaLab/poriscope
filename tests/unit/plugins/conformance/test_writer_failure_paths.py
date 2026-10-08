"""
Writers and the event-data loader on their failure paths.

The conformance writer tests drive both writer families through real chains on the happy
path and read back ``written``. Nothing read a writer's ``rejected`` or exercised a
duplicate row, a schema violation, an abort, or an event the upstream plugin could not
supply. These tests do, against the behaviour each failure is declared to have, so a fix
has a red test to turn green where today's behaviour differs:

- A duplicate row is one rejected event under one reason. Green today.
- A row the schema refuses (a NOT NULL column handed ``None``) is rejected under a reason
  that names the column, not as ``Cannot Overwrite Existing Event``.
- An event the fitter hands over with a missing component is a rejected event, not a
  silent skip.
- An abort leaves the channel empty and ``written`` at zero. Green today.
- A rejected event does not shift the indices of the events after it.
- A stored event row the loader cannot interpret (a NULL ``padding_before``) is reported,
  not dropped at INFO; a failed query raises rather than looking exhausted; an export says
  how many events it could not write.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Iterator, List, Type
from unittest.mock import patch

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.utils.MetaDatabaseWriter import MetaDatabaseWriter
from poriscope.utils.MetaWriter import MetaWriter
from tests.unit.plugins.conformance._recipes import (
    CHIMERA_CHANNEL,
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
    write_metadata_database,
)
from tests.unit.plugins.conformance.test_writers import describe_database, identity

pytestmark = pytest.mark.conformance

DB_WRITERS: List[Type[MetaDatabaseWriter]] = discover_concrete(MetaDatabaseWriter)
WRITERS: List[Type[MetaWriter]] = discover_concrete(MetaWriter)


# --- upstream plugins, fitted or found once per test --------------------------------------
@pytest.fixture
def fitted(events_db_path):
    """
    A CUSUM fitter that has fitted every event of the flat conformance database.

    :param events_db_path: the conformance events database
    :return: the fitter
    """
    loader = build_event_loader(events_db_path)
    fitter = build_event_fitter(CUSUM, loader)
    for _progress in fitter.fit_events(EVENTS_CHANNEL):
        pass
    yield fitter
    fitter.close_resources()
    loader.close_resources()


@pytest.fixture
def found(chimera_log_path):
    """
    A finder that has located every planted event of the conformance Chimera recording.

    :param chimera_log_path: the conformance recording
    :return: the finder
    """
    reader = build_reader(chimera_log_path)
    finder = build_event_finder(ClassicBlockageFinder, reader)
    for _progress in finder.find_events(CHIMERA_CHANNEL, [(0.0, 0.0)], 3.0, identity):
        pass
    yield finder
    finder.close_resources()
    reader.close_resources()


def drain(generator: Iterator[float]) -> None:
    """
    Run a writer generator to completion.

    :param generator: the write generator
    :type generator: Iterator[float]
    """
    for _progress in generator:
        pass


def event_ids(path: Path, channel: int) -> List[int]:
    """
    Read back the event ids stored for a channel, in order.

    :param path: the written database
    :type path: Path
    :param channel: the channel
    :type channel: int
    :return: the stored ``event_id`` values
    :rtype: List[int]
    """
    connection = sqlite3.connect(str(path))
    try:
        rows = connection.execute(
            "SELECT event_id FROM events WHERE channel_id = ? ORDER BY event_id",
            (channel,),
        ).fetchall()
    finally:
        connection.close()
    return [row[0] for row in rows]


# --- MetaDatabaseWriter ---------------------------------------------------------------
@pytest.mark.parametrize("writer_cls", DB_WRITERS, ids=[c.__name__ for c in DB_WRITERS])
def test_a_duplicate_write_is_rejected_under_one_reason(
    writer_cls: Type[MetaDatabaseWriter], fitted, tmp_path: Path
) -> None:
    """Writing the same fitted channel twice rejects every event the second time, once each."""
    out = tmp_path / "metadata.sqlite3"
    first = build_db_writer(writer_cls, fitted, str(out))
    drain(first.write_events(EVENTS_CHANNEL))
    first.close_resources()
    assert describe_database(out)["events"] == EVENTS_COUNT

    second = build_db_writer(writer_cls, fitted, str(out))
    drain(second.write_events(EVENTS_CHANNEL))
    second.close_resources()
    assert second.written[EVENTS_CHANNEL] == 0
    assert second.rejected[EVENTS_CHANNEL] == {
        "Cannot Overwrite Existing Event": EVENTS_COUNT
    }
    assert describe_database(out)["events"] == EVENTS_COUNT


def _with_event_zero_mutated(fitter, mutate):
    """
    Wrap the fitter's metadata generator so event zero's tuple is altered before writing.

    :param fitter: the fitted fitter
    :param mutate: a function from the five-tuple to the altered five-tuple
    :return: a context manager patching the generator
    """
    real = fitter.get_event_metadata_generator

    def wrapped(channel):
        for position, item in enumerate(real(channel)):
            yield mutate(item) if position == 0 else item

    return patch.object(fitter, "get_event_metadata_generator", wrapped)


@pytest.mark.parametrize("writer_cls", DB_WRITERS, ids=[c.__name__ for c in DB_WRITERS])
def test_a_schema_violation_is_reported_by_column_not_as_a_duplicate(
    writer_cls: Type[MetaDatabaseWriter], fitted, tmp_path: Path
) -> None:
    """A row the schema refuses names the offending column in its rejection reason."""

    def null_start_time(item):
        event_metadata, sublevels, filtered, raw, fit = item
        broken = dict(event_metadata)
        broken["start_time"] = None  # NOT NULL in the events table
        return broken, sublevels, filtered, raw, fit

    out = tmp_path / "metadata.sqlite3"
    writer = build_db_writer(writer_cls, fitted, str(out))
    with _with_event_zero_mutated(fitted, null_start_time):
        drain(writer.write_events(EVENTS_CHANNEL))
    writer.close_resources()

    rejected = writer.rejected[EVENTS_CHANNEL]
    assert writer.written[EVENTS_CHANNEL] == EVENTS_COUNT - 1
    assert sum(rejected.values()) == 1, rejected
    assert "Cannot Overwrite Existing Event" not in rejected, rejected
    assert any("start_time" in reason for reason in rejected), rejected


@pytest.mark.parametrize("writer_cls", DB_WRITERS, ids=[c.__name__ for c in DB_WRITERS])
def test_a_sublevel_the_schema_refuses_names_its_column_and_stores_nothing(
    writer_cls: Type[MetaDatabaseWriter], fitted, tmp_path: Path
) -> None:
    """
    A sublevel row the schema refuses is reported by its column, and its event's
    row - already inserted when the sublevels fail - is rolled back with it.
    """

    def null_level_ids(item):
        event_metadata, sublevels, filtered, raw, fit = item
        broken = dict(sublevels)
        broken["level_id"] = [None] * len(sublevels["level_id"])  # NOT NULL
        return event_metadata, broken, filtered, raw, fit

    out = tmp_path / "metadata.sqlite3"
    writer = build_db_writer(writer_cls, fitted, str(out))
    with _with_event_zero_mutated(fitted, null_level_ids):
        drain(writer.write_events(EVENTS_CHANNEL))
    writer.close_resources()

    rejected = writer.rejected[EVENTS_CHANNEL]
    assert writer.written[EVENTS_CHANNEL] == EVENTS_COUNT - 1
    assert sum(rejected.values()) == 1, rejected
    assert any("level_id" in reason for reason in rejected), rejected
    assert describe_database(out)["events"] == EVENTS_COUNT - 1


@pytest.mark.parametrize("writer_cls", DB_WRITERS, ids=[c.__name__ for c in DB_WRITERS])
def test_an_event_with_a_missing_component_is_rejected_not_skipped(
    writer_cls: Type[MetaDatabaseWriter], fitted, tmp_path: Path
) -> None:
    """An event the fitter cannot fully supply is a rejected event, counted and named."""

    def drop_fit_data(item):
        event_metadata, sublevels, filtered, raw, _fit = item
        return event_metadata, sublevels, filtered, raw, None

    out = tmp_path / "metadata.sqlite3"
    writer = build_db_writer(writer_cls, fitted, str(out))
    with _with_event_zero_mutated(fitted, drop_fit_data):
        drain(writer.write_events(EVENTS_CHANNEL))
    writer.close_resources()

    assert writer.written[EVENTS_CHANNEL] == EVENTS_COUNT - 1
    assert sum(writer.rejected[EVENTS_CHANNEL].values()) == 1, writer.rejected


@pytest.mark.parametrize("writer_cls", DB_WRITERS, ids=[c.__name__ for c in DB_WRITERS])
def test_an_aborted_write_leaves_the_channel_empty(
    writer_cls: Type[MetaDatabaseWriter], fitted, tmp_path: Path
) -> None:
    """Sending abort into the write generator resets the channel and reports nothing written."""
    out = tmp_path / "metadata.sqlite3"
    writer = build_db_writer(writer_cls, fitted, str(out))
    generator = writer.write_events(EVENTS_CHANNEL)
    next(generator)
    next(generator)
    with pytest.raises(StopIteration):
        generator.send(True)
    writer.close_resources()

    assert writer.written[EVENTS_CHANNEL] == 0
    assert describe_database(out)["events"] == 0


# --- MetaWriter ----------------------------------------------------------------------------
@pytest.mark.parametrize("writer_cls", WRITERS, ids=[c.__name__ for c in WRITERS])
def test_a_rejected_event_does_not_shift_the_indices_after_it(
    writer_cls: Type[MetaWriter], found, tmp_path: Path
) -> None:
    """
    When event 2 cannot be read, it is rejected under the reader's own reason and the
    stored events keep their own indices: every index but 2, rather than 0..n-2 with
    every later event renumbered, and the commit carries on past it.
    """
    total = found.get_num_events_found(CHIMERA_CHANNEL)
    assert total >= 4
    real = found.get_single_event_data

    def event_two_unreadable(channel, index, data_filter=None, rectify=False):
        if index == 2:
            raise ValueError("read runs past the end of the recording")
        return real(channel, index, data_filter, rectify)

    out = tmp_path / "events.sqlite3"
    writer = build_writer(writer_cls, found, str(out))
    with patch.object(found, "get_single_event_data", event_two_unreadable):
        drain(writer.commit_events(CHIMERA_CHANNEL))
    writer.close_resources()

    assert writer.written[CHIMERA_CHANNEL] == total - 1
    assert writer.rejected[CHIMERA_CHANNEL] == {
        "read runs past the end of the recording": 1
    }, writer.rejected
    assert event_ids(out, CHIMERA_CHANNEL) == [i for i in range(total) if i != 2]


@pytest.mark.parametrize("writer_cls", WRITERS, ids=[c.__name__ for c in WRITERS])
def test_an_aborted_commit_leaves_the_channel_empty(
    writer_cls: Type[MetaWriter], found, tmp_path: Path
) -> None:
    """Sending abort into the commit generator resets the channel and reports nothing written."""
    out = tmp_path / "events.sqlite3"
    writer = build_writer(writer_cls, found, str(out))
    generator = writer.commit_events(CHIMERA_CHANNEL)
    next(generator)
    next(generator)
    with pytest.raises(StopIteration):
        generator.send(True)
    writer.close_resources()

    assert writer.written[CHIMERA_CHANNEL] == 0
    assert describe_database(out)["events"] == 0


# --- SQLiteDBLoader ---------------------------------------------------------------------
@pytest.fixture
def null_padding_db(events_db_path, tmp_path: Path) -> Path:
    """
    A database from the shipped writer in which one event's leading padding is NULL.

    ``padding_before`` is the level-0 sublevel's ``sublevel_duration``, a nullable
    column, so the shipped writer stores a NULL there when a fitter hands it one; this
    sets it on the event with ``event_id`` 1 after the fact.

    :param events_db_path: the conformance events database
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :return: the database
    :rtype: Path
    """
    out = write_metadata_database(
        events_db_path, tmp_path / "metadata.sqlite3", CUSUM, SQLiteDBWriter
    )
    connection = sqlite3.connect(str(out))
    try:
        connection.execute(
            "UPDATE sublevels SET sublevel_duration = NULL WHERE level_id = 0 "
            "AND event_db_id = (SELECT id FROM events WHERE event_id = 1)"
        )
        connection.commit()
    finally:
        connection.close()
    return out


def test_a_null_padding_before_is_reported_not_dropped(
    null_padding_db: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A stored row the loader cannot read yields nothing for that event and says so at
    WARNING or above, naming the event; the rows around it still come through.
    """
    loader = build_db_loader(SQLiteDBLoader, str(null_padding_db))
    try:
        with caplog.at_level(logging.INFO):
            events = list(loader.load_event_data())
    finally:
        loader.close_resources()

    assert [event["event_id"] for event in events] == [
        i for i in range(EVENTS_COUNT) if i != 1
    ]
    reports = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("event 1 " in message for message in reports), reports


def test_an_exception_thrown_into_the_event_reader_is_not_swallowed(
    null_padding_db: Path,
) -> None:
    """
    The reader's handling of an unreadable row covers that row, not whatever a caller
    throws into the generator while it is suspended.
    """
    loader = build_db_loader(SQLiteDBLoader, str(null_padding_db))
    query, debug = loader.construct_event_data_query()
    assert query, debug
    generator = loader._load_event_data(query)
    try:
        next(generator)
        with pytest.raises(RuntimeError, match="thrown in"):
            generator.throw(RuntimeError("thrown in"))
    finally:
        generator.close()
        loader.close_resources()


@pytest.mark.parametrize("method", ["_load_event_data", "_load_metadata_generator"])
def test_a_query_that_fails_says_so_rather_than_looking_exhausted(
    method: str, null_padding_db: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A database error ends the iteration with that error, logged at ERROR so the user
    is told, instead of ending it as if every row had been read.
    """
    loader = build_db_loader(SQLiteDBLoader, str(null_padding_db))
    try:
        with caplog.at_level(logging.ERROR), pytest.raises(sqlite3.Error):
            list(getattr(loader, method)("SELECT * FROM no_such_table"))
    finally:
        loader.close_resources()
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_an_export_says_how_many_events_it_could_not_write(
    null_padding_db: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    ``data.csv`` lists every selected event, so one without a trace file is said to be
    missing rather than left for the reader of the export to find.
    """
    out = tmp_path / "export"
    out.mkdir()
    loader = build_db_loader(SQLiteDBLoader, str(null_padding_db))
    try:
        with caplog.at_level(logging.WARNING):
            drain(loader.export_subset_to_csv(str(out), "s"))
    finally:
        loader.close_resources()

    assert len(list(out.glob("s_event_*.csv"))) == EVENTS_COUNT - 1
    reports = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(f"1 of {EVENTS_COUNT}" in message for message in reports), reports
