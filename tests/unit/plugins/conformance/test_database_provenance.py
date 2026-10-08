"""
Each channel of a metadata database records how its events were produced.

``channels.provenance`` holds JSON naming the database writer, the event fitter and the
event loader - each by class, key and the values of its settings - with the Poriscope
version and the time of the write. It is a column rather than a table because every
release before 2.1 refuses a database with a table it does not know, and a column it
ignores. A file from before 2.1 gains the column the first time a later writer appends a
channel to it; channels written before then read NULL.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from poriscope.constants import __VERSION__
from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from tests.unit.plugins.conformance._recipes import (
    EVENTS_CHANNEL,
    build_db_writer,
    build_event_fitter,
    build_event_loader,
    write_metadata_database,
)

pytestmark = pytest.mark.conformance


def channel_provenance(path: Path) -> List[Optional[str]]:
    """
    The provenance stored for every channel of a database, in row order.

    :param path: the database
    :type path: Path
    :return: each channel's provenance text, or None where it has none
    :rtype: List[Optional[str]]
    """
    connection = sqlite3.connect(str(path))
    try:
        return [row[0] for row in connection.execute("SELECT provenance FROM channels")]
    finally:
        connection.close()


def channel_columns(path: Path) -> List[str]:
    """
    The columns of a database's ``channels`` table.

    :param path: the database
    :type path: Path
    :return: the column names
    :rtype: List[str]
    """
    connection = sqlite3.connect(str(path))
    try:
        return [row[1] for row in connection.execute("PRAGMA table_info(channels)")]
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


def test_a_written_channel_records_the_plugins_that_produced_it(
    written: Path,
) -> None:
    """The writer, the fitter and the event loader are named with their settings."""
    stored = channel_provenance(written)
    assert len(stored) == 1 and stored[0] is not None
    provenance: Dict[str, Any] = json.loads(stored[0])

    assert provenance["poriscope_version"] == __VERSION__
    datetime.fromisoformat(provenance["written_at"])
    assert provenance["writer"]["class"] == "SQLiteDBWriter"
    assert provenance["writer"]["settings"]["Output File"] == str(written)
    assert provenance["fitter"]["class"] == "CUSUM"
    assert isinstance(provenance["fitter"]["settings"]["Step Size"], float)
    assert provenance["event_loader"]["class"] == "SQLiteEventLoader"
    assert provenance["event_loader"]["settings"]["Input File"]


def test_a_plugin_a_setting_refers_to_is_recorded_by_its_key(
    events_db_path, tmp_path: Path
) -> None:
    """
    A setting that refers to another plugin - the writer's fitter, the fitter's
    loader - holds that plugin's key, and the record names the plugin under the same
    key, so the chain can be followed. Keys are set here as the app sets them.
    """
    loader = build_event_loader(events_db_path)
    loader.set_key("events_0")
    fitter = build_event_fitter(CUSUM, loader)
    fitter.set_key("cusum_0")
    out = tmp_path / "keyed.sqlite3"
    try:
        for _progress in fitter.fit_events(EVENTS_CHANNEL):
            pass
        writer = build_db_writer(SQLiteDBWriter, fitter, str(out))
        writer.set_key("metadata_0")
        try:
            for _progress in writer.write_events(EVENTS_CHANNEL):
                pass
        finally:
            writer.close_resources()
    finally:
        fitter.close_resources()
        loader.close_resources()

    provenance = json.loads(channel_provenance(out)[0])

    assert provenance["writer"]["key"] == "metadata_0"
    assert provenance["fitter"]["key"] == "cusum_0"
    assert provenance["event_loader"]["key"] == "events_0"
    assert provenance["writer"]["settings"]["MetaEventFitter"] == "cusum_0"
    assert provenance["fitter"]["settings"]["MetaEventLoader"] == "events_0"


def test_an_older_database_gains_provenance_for_the_channels_written_to_it(
    written: Path, events_db_path
) -> None:
    """
    A file from before 2.1 has no ``provenance`` column; appending a channel adds it
    and fills it for that channel.
    """
    connection = sqlite3.connect(str(written))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("DELETE FROM channels")
        if "provenance" in channel_columns(written):
            connection.execute("ALTER TABLE channels DROP COLUMN provenance")
        connection.execute("PRAGMA user_version = 0")
        connection.commit()
    finally:
        connection.close()
    assert "provenance" not in channel_columns(written)

    write_metadata_database(
        events_db_path, written, CUSUM, SQLiteDBWriter, EVENTS_CHANNEL
    )

    stored = channel_provenance(written)
    assert len(stored) == 1 and stored[0] is not None
    assert json.loads(stored[0])["fitter"]["class"] == "CUSUM"


def test_plugins_made_in_a_script_are_recorded_by_their_own_keys(
    events_db_path, tmp_path: Path
) -> None:
    """
    Plugins built in a script without names still get distinct keys, so the record's
    chain from writer to fitter to loader can be followed.
    """
    out = write_metadata_database(
        events_db_path, tmp_path / "scripted.sqlite3", CUSUM, SQLiteDBWriter
    )

    provenance = json.loads(channel_provenance(out)[0])

    keys = [provenance[role]["key"] for role in ("writer", "fitter", "event_loader")]
    assert all(keys) and len(set(keys)) == 3
    assert provenance["writer"]["settings"]["MetaEventFitter"] == keys[1]
    assert provenance["fitter"]["settings"]["MetaEventLoader"] == keys[2]
