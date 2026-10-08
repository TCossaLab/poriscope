"""
The metadata database indexes the foreign keys its queries look rows up by.

``data.event_db_id``, ``sublevels.event_db_id`` and ``events.channel_db_id`` are what the
event-data query, a metadata query that joins events to sublevels, and the cascade from
deleting a channel all search on. Without an index on each, those become nested scans:
measured at 20,000 events, a scoped event-column query with a sublevel filter took 31 s
and resetting one channel 333 s. The writer creates the indexes in every file it writes,
and the loader adds them to any file it opens that lacks them, as long as it can write to
it - a file it cannot write still opens, just without them.
"""

import logging
import os
import sqlite3
import stat
import time
from pathlib import Path
from typing import Iterator, Set, Tuple

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from tests.unit.plugins.conformance._recipes import (
    _EXPERIMENT_METADATA,
    EVENTS_CHANNEL,
    build_db_loader,
    build_db_writer,
    build_event_fitter,
    build_event_loader,
)

pytestmark = pytest.mark.conformance

#: (table, column) for each foreign key a query searches on.
FOREIGN_KEYS = {
    ("data", "event_db_id"),
    ("sublevels", "event_db_id"),
    ("events", "channel_db_id"),
}


@pytest.fixture
def written(events_db_path, tmp_path: Path) -> Iterator[Path]:
    """
    A metadata database written by the shipped writer from a CUSUM fit.

    :param events_db_path: the conformance events database
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :return: the written database
    :rtype: Iterator[Path]
    """
    loader = build_event_loader(events_db_path)
    fitter = build_event_fitter(CUSUM, loader)
    for _progress in fitter.fit_events(EVENTS_CHANNEL):
        pass
    out = tmp_path / "metadata.sqlite3"
    writer = build_db_writer(SQLiteDBWriter, fitter, str(out))
    for _progress in writer.write_events(EVENTS_CHANNEL):
        pass
    writer.close_resources()
    fitter.close_resources()
    loader.close_resources()
    yield out


def indexes(path: Path) -> Set[Tuple[str, str, str]]:
    """
    Every named index in a database, as (name, table, leading column).

    :param path: the database
    :type path: Path
    :return: the named indexes; SQLite's own ``sqlite_autoindex_*`` are left out
    :rtype: Set[Tuple[str, str, str]]
    """
    connection = sqlite3.connect(str(path))
    try:
        found = set()
        for name, table in connection.execute(
            "SELECT name, tbl_name FROM sqlite_master "
            "WHERE type = 'index' AND name NOT LIKE 'sqlite_autoindex_%'"
        ):
            leading = connection.execute(f"PRAGMA index_info('{name}')").fetchone()[2]
            found.add((name, table, leading))
    finally:
        connection.close()
    return found


def indexed_foreign_keys(path: Path) -> Set[Tuple[str, str]]:
    """
    The foreign keys that some index in the database leads with.

    :param path: the database
    :type path: Path
    :return: (table, column) pairs from :data:`FOREIGN_KEYS` that are indexed
    :rtype: Set[Tuple[str, str]]
    """
    return {(table, column) for _name, table, column in indexes(path)} & FOREIGN_KEYS


def strip_foreign_key_indexes(path: Path) -> None:
    """
    Turn a database into one written before the foreign keys were indexed.

    :param path: the database
    :type path: Path
    """
    doomed = [
        name for name, table, column in indexes(path) if (table, column) in FOREIGN_KEYS
    ]
    connection = sqlite3.connect(str(path))
    try:
        for name in doomed:
            connection.execute(f"DROP INDEX {name}")
        connection.commit()
    finally:
        connection.close()
    assert indexed_foreign_keys(path) == set()


def open_loader(path: Path) -> SQLiteDBLoader:
    """
    Open a database the way the app does, through the shipped loader.

    :param path: the database
    :type path: Path
    :return: the configured loader
    :rtype: SQLiteDBLoader
    """
    loader = build_db_loader(SQLiteDBLoader, str(path))
    assert isinstance(loader, SQLiteDBLoader)
    return loader


def query_plan(path: Path, query: str) -> str:
    """
    SQLite's plan for a query, one step per line.

    :param path: the database
    :type path: Path
    :param query: the query to plan
    :type query: str
    :return: the plan's detail column, joined by newlines
    :rtype: str
    """
    connection = sqlite3.connect(str(path))
    try:
        rows = connection.execute(f"EXPLAIN QUERY PLAN {query}").fetchall()
    finally:
        connection.close()
    return "\n".join(row[3] for row in rows)


def test_a_written_database_indexes_its_foreign_keys(written: Path) -> None:
    """The writer creates an index on each foreign key a query searches on."""
    assert indexed_foreign_keys(written) == FOREIGN_KEYS


def test_opening_an_older_database_adds_the_indexes(written: Path) -> None:
    """A file written without the indexes has them once a loader has opened it."""
    strip_foreign_key_indexes(written)

    open_loader(written).close_resources()

    assert indexed_foreign_keys(written) == FOREIGN_KEYS


def test_the_writer_and_the_loader_build_the_same_indexes(written: Path) -> None:
    """
    An upgraded file ends up with exactly the indexes a new one is written with.

    The two plugins each carry the statements, so this is what keeps them equal.
    """
    as_written = indexes(written)
    strip_foreign_key_indexes(written)

    open_loader(written).close_resources()

    assert len(as_written) > 0
    assert indexes(written) == as_written


def test_the_event_data_query_searches_by_index(written: Path) -> None:
    """Loading events by id looks their data rows up rather than scanning the table."""
    strip_foreign_key_indexes(written)
    loader = open_loader(written)
    try:
        query, debug = loader.construct_event_data_query("e.id IN (1, 2, 3)")
    finally:
        loader.close_resources()
    assert query, debug

    plan = query_plan(written, query)

    assert "SCAN d" not in plan, plan
    assert "SEARCH d USING INDEX" in plan, plan


def test_a_scoped_query_with_a_sublevel_filter_searches_by_index(
    written: Path,
) -> None:
    """
    An event column filtered on a sublevel column joins without scanning sublevels.

    This is the query that grew quadratically: 871 ms at 5,000 events and 31 s at
    20,000 without the index.
    """
    strip_foreign_key_indexes(written)
    loader = open_loader(written)
    experiment = _EXPERIMENT_METADATA["Experiment Name"]
    try:
        query, debug, _table = loader.construct_metadata_query(
            ["duration"], "sublevel_duration > 0", {experiment: [EVENTS_CHANNEL]}
        )
    finally:
        loader.close_resources()
    assert query, debug

    plan = query_plan(written, query)

    assert "SCAN s" not in plan, plan


@pytest.fixture
def read_only(written: Path) -> Iterator[Path]:
    """
    A database without the indexes that cannot be written to.

    :param written: a written database
    :type written: Path
    :return: the same file, stripped of its indexes and made read-only
    :rtype: Iterator[Path]
    """
    strip_foreign_key_indexes(written)
    os.chmod(written, stat.S_IREAD)
    yield written
    os.chmod(written, stat.S_IREAD | stat.S_IWRITE)


def test_a_database_that_cannot_be_written_still_opens(
    read_only: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Indexing is best-effort: a read-only file opens as it always did, and says why
    it was left unindexed.
    """
    with caplog.at_level(logging.WARNING):
        loader = open_loader(read_only)
    try:
        assert loader.get_experiment_names()
    finally:
        loader.close_resources()

    assert indexed_foreign_keys(read_only) == set()
    assert any(
        record.levelno == logging.WARNING and read_only.name in record.getMessage()
        for record in caplog.records
    ), [record.getMessage() for record in caplog.records]


def test_a_database_another_connection_is_writing_still_opens_promptly(
    written: Path,
) -> None:
    """
    A file another connection holds a write lock on - a writer mid-run, say - opens
    without waiting out SQLite's default five-second lock timeout, and without the
    indexes; the next open adds them.
    """
    strip_foreign_key_indexes(written)
    holder = sqlite3.connect(str(written), isolation_level=None)
    try:
        holder.execute("BEGIN IMMEDIATE")
        started = time.perf_counter()
        open_loader(written).close_resources()
        elapsed = time.perf_counter() - started
        holder.execute("ROLLBACK")
    finally:
        holder.close()

    assert elapsed < 2.0, f"opening waited {elapsed:.1f} s on the lock"
    assert indexed_foreign_keys(written) == set()

    open_loader(written).close_resources()

    assert indexed_foreign_keys(written) == FOREIGN_KEYS
