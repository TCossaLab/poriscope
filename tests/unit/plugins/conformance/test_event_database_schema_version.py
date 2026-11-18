"""
An events database records the schema version it was created with.

The same rule as the metadata database (``test_database_schema_version.py``): the writer
stamps ``PRAGMA user_version`` in the transaction that creates the schema, and only when
it creates it, so a file reads 1 exactly when 3.0 or later created it and a file from
before 3.0 reads 0 and keeps 0. The loader opens 0 and every version it knows and
refuses a newer one by name; the writer refuses to add to a newer one, since rows in an
older layout would damage a file a reader could otherwise only fail to open.

The chain that writes the template runs once for the module; each test works on its own
copy of the file.
"""

import shutil
import sqlite3
from pathlib import Path
from typing import Iterator, Tuple

import pytest

from poriscope.plugins.datawriters.SQLiteEventWriter import SQLiteEventWriter
from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder
from poriscope.plugins.eventloaders.SQLiteEventLoader import SQLiteEventLoader
from poriscope.utils.MetaEventFinder import MetaEventFinder
from tests.unit.plugins.conformance._recipes import (
    CHIMERA_CHANNEL,
    CHIMERA_EVENTS,
    build_event_finder,
    build_event_loader,
    build_reader,
    build_writer,
)

pytestmark = pytest.mark.conformance


def user_version(path: Path) -> int:
    """
    The schema version stamped in a database file.

    :param path: the database
    :type path: Path
    :return: its ``PRAGMA user_version``
    :rtype: int
    """
    connection = sqlite3.connect(str(path))
    try:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])
    finally:
        connection.close()


def stamp(path: Path, version: int) -> None:
    """
    Set a database's schema version, as an older or newer writer would have left it.

    :param path: the database
    :type path: Path
    :param version: the version to stamp
    :type version: int
    """
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(f"PRAGMA user_version = {version}")
        connection.commit()
    finally:
        connection.close()


def unchanged(data):
    """
    Return data unchanged, standing in for a filter.

    :param data: the chunk handed over by the finder
    :type data: numpy.ndarray
    :return: the same chunk
    :rtype: numpy.ndarray
    """
    return data


@pytest.fixture(scope="module")
def chain(
    chimera_log_path, tmp_path_factory
) -> Iterator[Tuple[MetaEventFinder, Path]]:
    """
    A finder that has found its events, and an events database the shipped writer made.

    :param chimera_log_path: the synthetic Chimera recording
    :param tmp_path_factory: pytest's session-scoped temporary directory factory
    :return: the finder and the written template database
    :rtype: Iterator[Tuple[MetaEventFinder, Path]]
    """
    reader = build_reader(chimera_log_path)
    finder = build_event_finder(ClassicBlockageFinder, reader)
    for _progress in finder.find_events(CHIMERA_CHANNEL, [(0.0, 0.0)], 3.0, unchanged):
        pass
    template = tmp_path_factory.mktemp("event_schema_version") / "events.sqlite3"
    writer = build_writer(SQLiteEventWriter, finder, str(template))
    try:
        for _progress in writer.commit_events(CHIMERA_CHANNEL):
            pass
    finally:
        writer.close_resources()
    yield finder, template
    finder.close_resources()
    reader.close_resources()


@pytest.fixture
def finder(chain: Tuple[MetaEventFinder, Path]) -> MetaEventFinder:
    """
    The module's finder, its events already found.

    :param chain: the module's finder and template
    :type chain: Tuple[MetaEventFinder, Path]
    :return: the finder
    :rtype: MetaEventFinder
    """
    return chain[0]


@pytest.fixture
def written(chain: Tuple[MetaEventFinder, Path], tmp_path: Path) -> Path:
    """
    This test's own copy of the events database the shipped writer made.

    :param chain: the module's finder and template
    :type chain: Tuple[MetaEventFinder, Path]
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :return: the copy
    :rtype: Path
    """
    return Path(shutil.copy(chain[1], tmp_path / "events.sqlite3"))


def test_an_events_database_the_writer_creates_is_stamped_with_the_current_version(
    written: Path,
) -> None:
    """A new file carries the version the loader reads up to."""
    assert (
        user_version(written)
        == SQLiteEventWriter.SCHEMA_VERSION
        == SQLiteEventLoader.SCHEMA_VERSION
        == 1
    )


def test_writing_to_an_older_events_database_leaves_its_version_alone(
    written: Path, finder: MetaEventFinder
) -> None:
    """
    A file from before 3.0 stays at 0 when a later writer prepares it for a channel.

    The stamp says which version *created* the file; it is not a claim about every
    row in it.
    """
    stamp(written, 0)

    writer = build_writer(SQLiteEventWriter, finder, str(written))
    try:
        writer._initialize_database(CHIMERA_CHANNEL)
    finally:
        writer.close_resources()

    assert user_version(written) == 0


def test_the_writer_adds_to_an_events_database_at_the_current_version(
    written: Path, finder: MetaEventFinder
) -> None:
    """A file this version created is accepted again: re-committing into one is intended."""
    writer = build_writer(SQLiteEventWriter, finder, str(written))
    try:
        writer._initialize_database(CHIMERA_CHANNEL)
    finally:
        writer.close_resources()

    assert user_version(written) == SQLiteEventWriter.SCHEMA_VERSION


def test_a_creation_that_fails_leaves_no_version(
    finder: MetaEventFinder, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The stamp rolls back with the schema it describes, so a file reads 1 only if the
    schema it promises is really there.
    """
    out = tmp_path / "failed.sqlite3"
    writer = build_writer(SQLiteEventWriter, finder, str(out))

    def no_settings() -> dict:
        raise ValueError("no units to record")

    monkeypatch.setattr(writer, "get_empty_settings", no_settings)
    try:
        with pytest.raises(ValueError, match="no units to record"):
            writer._initialize_database(CHIMERA_CHANNEL)
    finally:
        writer.close_resources()

    assert user_version(out) == 0


@pytest.mark.parametrize("version", [0, SQLiteEventLoader.SCHEMA_VERSION])
def test_an_events_database_up_to_the_current_version_opens(
    written: Path, version: int
) -> None:
    """A file from before 3.0, at version 0, opens as it always did, as does a new one."""
    stamp(written, version)

    loader = build_event_loader(str(written))
    try:
        assert loader.get_num_events(CHIMERA_CHANNEL) == CHIMERA_EVENTS
    finally:
        loader.close_resources()


def test_a_newer_events_database_is_refused_by_version(written: Path) -> None:
    """
    A file a later major version created is refused, naming both versions, rather than
    read against a schema this version has never seen.
    """
    stamp(written, SQLiteEventLoader.SCHEMA_VERSION + 1)

    with pytest.raises(ValueError, match=r"schema version 2.*reads up to 1"):
        build_event_loader(str(written))


def test_the_writer_refuses_to_add_to_a_newer_events_database(
    written: Path, finder: MetaEventFinder
) -> None:
    """
    Events in this version's layout are never added to a file a later major version
    created: the refusal comes when the writer is configured, before anything is written.
    """
    stamp(written, SQLiteEventWriter.SCHEMA_VERSION + 1)

    with pytest.raises(ValueError, match=r"schema version 2.*writes up to 1"):
        build_writer(SQLiteEventWriter, finder, str(written))


def test_an_events_database_with_a_table_this_version_does_not_know_opens(
    written: Path,
) -> None:
    """
    Only the three core tables are required. A table a later release of the same major
    adds, one a user adds, and ``sqlite_stat1`` from ``ANALYZE`` are left alone: within a
    major a file changes only by addition, so an addition is never a reason to refuse it.
    """
    connection = sqlite3.connect(str(written))
    try:
        connection.execute("CREATE TABLE added_later (id INTEGER PRIMARY KEY);")
        connection.execute("ANALYZE;")
        connection.commit()
    finally:
        connection.close()

    loader = build_event_loader(str(written))
    try:
        assert loader.get_num_events(CHIMERA_CHANNEL) == CHIMERA_EVENTS
    finally:
        loader.close_resources()


def test_a_metadata_database_is_refused_for_what_it_is(metadata_db_path) -> None:
    """
    A fitted-metadata database also holds ``events``, ``channels`` and ``columns``, so
    it is told apart by its ``experiments`` table and named, not read as raw events.
    """
    with pytest.raises(ValueError, match="fitted-metadata database, not an events"):
        build_event_loader(metadata_db_path)


def test_a_database_missing_a_core_table_is_refused(written: Path) -> None:
    """A file without the tables every events database has is not one."""
    connection = sqlite3.connect(str(written))
    try:
        connection.execute("DROP TABLE columns;")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ValueError, match="Missing tables: columns"):
        build_event_loader(str(written))

