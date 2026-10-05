"""
Writers and the event-data loader on their failure paths.

The conformance writer tests drive both writer families through real chains on the happy
path and read back ``written``. Nothing read a writer's ``rejected`` or exercised a
duplicate row, a schema violation, an abort, or an event the upstream plugin could not
supply. These tests do, against the behaviour 2.1 declares for each, so that step 6 has a
red test to turn green where today's behaviour differs:

- A duplicate row is one rejected event under one reason. Green today.
- A row the schema refuses (a NOT NULL column handed ``None``) is rejected under a reason
  that names the column. Today ``INSERT OR IGNORE`` swallows the violation and the writer
  infers failure from ``rowcount``, so it reports ``Cannot Overwrite Existing Event``
  (``SQLiteDBWriter._insert_event:828``). Strict expected failure.
- An event the fitter hands over with a missing component is a rejected event, not a
  silent skip (``MetaDatabaseWriter.write_events:197-237``). Strict expected failure.
- An abort leaves the channel empty and ``written`` at zero. Green today.
- A rejected event does not shift the indices of the events after it
  (``MetaWriter.write_events:470-503`` continues past ``index += 1``). Strict expected
  failure.
- A stored event row the loader cannot interpret (a NULL ``padding_before``) is reported,
  not dropped at INFO (``SQLiteDBLoader._load_event_data:886-980``). Strict expected
  failure.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Iterator, List, Type
from unittest.mock import patch

import numpy as np
import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.utils.MetaDatabaseWriter import MetaDatabaseWriter
from poriscope.utils.MetaWriter import MetaWriter
from tests.unit.plugins.conformance._recipes import (
    CHIMERA_CHANNEL,
    EVENTS_CHANNEL,
    EVENTS_COUNT,
    build_db_writer,
    build_event_finder,
    build_event_fitter,
    build_event_loader,
    build_reader,
    build_writer,
    discover_concrete,
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SQLiteDBWriter._insert_event:828 infers failure from rowcount under INSERT OR "
        "IGNORE, so a NOT NULL violation is reported as 'Cannot Overwrite Existing "
        "Event' instead of naming the column; 2.1 step 6"
    ),
)
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "MetaDatabaseWriter.write_events:197-237 skips an event whose tuple holds a None "
        "with no yield and no rejected entry; 2.1 step 6"
    ),
)
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
@pytest.mark.xfail(
    strict=True,
    reason=(
        "MetaWriter.write_events:470-503 records a rejection and `continue`s past "
        "`index += 1`, so the next event is written under the rejected event's index; "
        "2.1 step 6"
    ),
)
@pytest.mark.parametrize("writer_cls", WRITERS, ids=[c.__name__ for c in WRITERS])
def test_a_rejected_event_does_not_shift_the_indices_after_it(
    writer_cls: Type[MetaWriter], found, tmp_path: Path
) -> None:
    """
    When event 2 cannot be written, the stored events keep their own indices: every index
    but 2, rather than 0..n-2 with every later event renumbered.
    """
    total = found.get_num_events(CHIMERA_CHANNEL)
    assert total >= 4
    real = found.get_event_data_generator

    def with_event_two_missing(channel, data_filter=None, rectify=False):
        for position, event in enumerate(real(channel, data_filter, rectify)):
            yield None if position == 2 else event

    out = tmp_path / "events.sqlite3"
    writer = build_writer(writer_cls, found, str(out))
    with patch.object(found, "get_event_data_generator", with_event_two_missing):
        drain(writer.commit_events(CHIMERA_CHANNEL))
    writer.close_resources()

    assert writer.written[CHIMERA_CHANNEL] == total - 1
    assert sum(writer.rejected[CHIMERA_CHANNEL].values()) == 1, writer.rejected
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
EVENT_DATA_QUERY = (
    "SELECT e.id, e.event_id, e.channel_id, e.experiment_id, d.data_format, "
    "d.samplerate, d.padding_before, d.padding_after, d.raw_data, d.filtered_data, "
    "d.fit_data FROM events e JOIN data d ON e.id = d.event_id"
)


def _database_with_a_null_padding(path: Path) -> None:
    """
    Write a two-event metadata database whose second data row has a NULL padding_before.

    The hand-built loader fixture declares the column NOT NULL, which is why this one
    exists: the production writer can be bypassed by any tool that edits the file.

    :param path: where to write it
    :type path: Path
    """
    blob = np.array([1.0, 2.0, 3.0], dtype=np.float64).tobytes()
    connection = sqlite3.connect(str(path))
    try:
        connection.executescript(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL,
                experiment_id INTEGER NOT NULL, channel_id INTEGER NOT NULL
            );
            CREATE TABLE data (
                id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL,
                data_format TEXT NOT NULL, samplerate REAL NOT NULL,
                padding_before INTEGER, padding_after INTEGER NOT NULL,
                raw_data BLOB, filtered_data BLOB, fit_data BLOB
            );
            INSERT INTO events (id, event_id, experiment_id, channel_id) VALUES (1, 0, 1, 0);
            INSERT INTO events (id, event_id, experiment_id, channel_id) VALUES (2, 1, 1, 0);
            """
        )
        connection.execute(
            "INSERT INTO data (event_id, data_format, samplerate, padding_before, "
            "padding_after, raw_data, filtered_data, fit_data) "
            "VALUES (1, 'float64', 10000.0, 10, 10, ?, ?, ?)",
            (blob, blob, blob),
        )
        connection.execute(
            "INSERT INTO data (event_id, data_format, samplerate, padding_before, "
            "padding_after, raw_data, filtered_data, fit_data) "
            "VALUES (2, 'float64', 10000.0, NULL, 10, ?, ?, ?)",
            (blob, blob, blob),
        )
        connection.commit()
    finally:
        connection.close()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SQLiteDBLoader._load_event_data:886-980 wraps the whole yield in `except "
        "Exception: log INFO; continue`, so a row it cannot interpret is dropped with "
        "nothing above INFO to say so; 2.1 step 6"
    ),
)
def test_a_null_padding_before_is_reported_not_dropped(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A stored row the loader cannot interpret yields nothing for that event and says so
    at WARNING or above, naming the event; the rows around it still come through.
    """
    db_path = tmp_path / "broken.sqlite3"
    _database_with_a_null_padding(db_path)
    settings = {"Input File": {"Type": str, "Value": str(db_path)}}
    with patch.object(SQLiteDBLoader, "_init"):
        loader = SQLiteDBLoader(settings=settings)
    loader.db_path = db_path

    with caplog.at_level(logging.INFO):
        rows = list(loader._load_event_data(EVENT_DATA_QUERY))

    assert len(rows) == 1 and rows[0][3] == 0  # the good event came through
    reports = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert reports, "the dropped row was not reported above INFO"
    assert any("1" in r.getMessage() for r in reports), [
        r.getMessage() for r in reports
    ]
