"""
A metadata database records the schema version it was created with.

The writer stamps ``PRAGMA user_version`` in the same transaction that creates the
schema, and only when it creates it, so a file reads 1 exactly when 2.1 or later
created it; a file from before 2.1 reads 0 and keeps 0 when a later writer appends to
it. A loader opens 0 and every version it knows, and refuses a newer one by name
rather than guessing at a schema it has never seen.
"""

import sqlite3
from pathlib import Path

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from tests.unit.plugins.conformance._recipes import (
    build_db_loader,
    build_db_writer,
    build_event_fitter,
    build_event_loader,
    write_metadata_database,
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


@pytest.fixture
def written(events_db_path, tmp_path: Path) -> Path:
    """
    A metadata database written by the shipped writer from a CUSUM fit.

    :param events_db_path: the conformance events database
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :return: the written database
    :rtype: Path
    """
    return write_metadata_database(
        events_db_path, tmp_path / "metadata.sqlite3", CUSUM, SQLiteDBWriter
    )


def test_a_database_the_writer_creates_is_stamped_with_the_current_version(
    written: Path,
) -> None:
    """A new file carries the version the loader reads up to."""
    assert user_version(written) == SQLiteDBLoader.SCHEMA_VERSION == 1


def test_appending_to_an_older_database_leaves_its_version_alone(
    written: Path, events_db_path
) -> None:
    """
    A file from before 2.1 stays at 0 when a later writer appends to it.

    The stamp says which version *created* the file; it is not a claim that every
    row in it was written by that version.
    """
    stamp(written, 0)

    write_metadata_database(events_db_path, written, CUSUM, SQLiteDBWriter)

    assert user_version(written) == 0


def test_a_creation_that_fails_leaves_no_version(
    events_db_path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The stamp rolls back with the schema it describes, so a file reads 1 only if the
    schema it promises is really there.
    """
    loader = build_event_loader(events_db_path)
    fitter = build_event_fitter(CUSUM, loader)
    out = tmp_path / "failed.sqlite3"
    try:
        writer = build_db_writer(SQLiteDBWriter, fitter, str(out))
        monkeypatch.setattr(
            fitter, "get_event_metadata_types", lambda: {"unstorable": list}
        )
        with pytest.raises(ValueError, match="unstorable"):
            writer._initialize_database(0)
    finally:
        fitter.close_resources()
        loader.close_resources()

    assert user_version(out) == 0


def test_an_older_database_opens(written: Path) -> None:
    """A file from before 2.1, at version 0, opens as it always did."""
    stamp(written, 0)

    loader = build_db_loader(SQLiteDBLoader, str(written))
    try:
        assert loader.get_experiment_names()
    finally:
        loader.close_resources()


def test_a_newer_database_is_refused_by_version(written: Path) -> None:
    """
    A file a later version created is refused, naming both versions, rather than
    read against a schema this version has never seen.
    """
    stamp(written, SQLiteDBLoader.SCHEMA_VERSION + 1)

    with pytest.raises(ValueError, match=r"schema version 2.*reads up to 1"):
        build_db_loader(SQLiteDBLoader, str(written))
