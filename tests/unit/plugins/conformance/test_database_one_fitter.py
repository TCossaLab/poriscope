"""
A metadata database holds results from one type of fitter, from any number of runs.

The column registry maps each name to one table, so two fitters that declare the same
name on different tables - ``max_blockage`` is an event column in the CUSUM family and a
sublevel column in the PeakFinders - would send the second fitter's values to a column
nothing reads. The writer refuses, when it is configured and before anything is written,
to write one fitter into a file holding another's. A file written by 2.1 names its fitter
in each channel's provenance and is checked by class. A file from before 2.1 names none,
so it is checked by its columns: every column the new fitter declares must already be
registered, on the table the fitter declares it for. Columns the file has beyond those -
an analysis tab's cluster labels, say - do not count against it.
"""

import sqlite3
from pathlib import Path

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
from poriscope.plugins.eventfitters.Basic_PeakFinder import Basic_PeakFinder
from poriscope.plugins.eventfitters.ClassicCUSUM import ClassicCUSUM
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from tests.unit.plugins.conformance._recipes import (
    EVENTS_COUNT,
    build_db_loader,
    build_db_writer,
    build_event_fitter,
    build_event_loader,
    write_metadata_database,
)

pytestmark = pytest.mark.conformance


@pytest.fixture
def cusum_file(events_db_path, tmp_path: Path) -> Path:
    """
    A metadata database holding one channel of CUSUM results, written by 2.1.

    :param events_db_path: the conformance events database
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :return: the database
    :rtype: Path
    """
    return write_metadata_database(
        events_db_path, tmp_path / "metadata.sqlite3", CUSUM, SQLiteDBWriter
    )


def as_pre_2_1(path: Path) -> None:
    """
    Make a written database look like one from before 2.1: no fitter recorded.

    :param path: the database
    :type path: Path
    """
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("UPDATE channels SET provenance = NULL")
        connection.execute("PRAGMA user_version = 0")
        connection.commit()
    finally:
        connection.close()


def configure_writer(fitter_cls, events_db_path, out: Path):
    """
    Configure the shipped writer for a fitter of the given class, writing to ``out``.

    Configuration is where a second fitter is refused; nothing needs fitting first.

    :param fitter_cls: the fitter class to attach
    :param events_db_path: an events database for the fitter's loader
    :param out: the metadata database to write to
    :type out: Path
    :return: the configured writer
    """
    loader = build_event_loader(events_db_path)
    fitter = build_event_fitter(fitter_cls, loader)
    return build_db_writer(SQLiteDBWriter, fitter, str(out))


def event_count(path: Path) -> int:
    """
    The number of events stored in a database.

    :param path: the database
    :type path: Path
    :return: its ``events`` row count
    :rtype: int
    """
    connection = sqlite3.connect(str(path))
    try:
        return int(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
    finally:
        connection.close()


def test_a_second_fitter_is_refused_before_anything_is_written(
    cusum_file: Path, peaked_events_db_path
) -> None:
    """Basic_PeakFinder into a CUSUM file is refused at configuration, naming both."""
    with pytest.raises(ValueError, match=r"CUSUM.*Basic_PeakFinder"):
        configure_writer(Basic_PeakFinder, peaked_events_db_path, cusum_file)

    assert event_count(cusum_file) == EVENTS_COUNT


def test_a_fitter_built_on_another_still_counts_as_another(
    cusum_file: Path, events_db_path
) -> None:
    """ClassicCUSUM extends CUSUM, and is still a different fitter for this rule."""
    with pytest.raises(ValueError, match="ClassicCUSUM"):
        configure_writer(ClassicCUSUM, events_db_path, cusum_file)


def test_the_same_fitter_is_accepted(cusum_file: Path, events_db_path) -> None:
    """Another CUSUM instance - other settings, another run - writes to the file."""
    writer = configure_writer(CUSUM, events_db_path, cusum_file)
    writer.close_resources()


def test_an_older_file_accepts_the_fitter_whose_columns_it_holds(
    cusum_file: Path, events_db_path
) -> None:
    """A pre-2.1 CUSUM file, with no fitter recorded, takes CUSUM by its columns."""
    as_pre_2_1(cusum_file)

    writer = configure_writer(CUSUM, events_db_path, cusum_file)
    writer.close_resources()


def test_an_older_file_refuses_a_fitter_whose_columns_land_elsewhere(
    cusum_file: Path, peaked_events_db_path
) -> None:
    """
    Basic_PeakFinder declares ``max_blockage`` on sublevels, where this file has it on
    events, so it is refused by column with no provenance to go on.
    """
    as_pre_2_1(cusum_file)

    with pytest.raises(ValueError, match="max_blockage"):
        configure_writer(Basic_PeakFinder, peaked_events_db_path, cusum_file)


def test_columns_an_analysis_tab_added_do_not_count_against_an_older_file(
    cusum_file: Path, events_db_path
) -> None:
    """
    Clustering registers its labels as an events column; the file still takes CUSUM.
    """
    as_pre_2_1(cusum_file)
    connection = sqlite3.connect(str(cusum_file))
    try:
        connection.execute("ALTER TABLE events ADD COLUMN cluster INTEGER")
        connection.execute(
            "INSERT INTO columns (name, table_name, units) VALUES ('cluster', 'events', ' ')"
        )
        connection.commit()
    finally:
        connection.close()

    writer = configure_writer(CUSUM, events_db_path, cusum_file)
    writer.close_resources()


def test_sublevel_indices_can_be_queried(cusum_file: Path) -> None:
    """``level_id`` and ``levels_left`` are registered as sublevel columns."""
    loader = build_db_loader(SQLiteDBLoader, str(cusum_file))
    try:
        frame = loader.load_metadata(["level_id", "levels_left"])
    finally:
        loader.close_resources()

    assert frame is not None and len(frame) > 0
    assert set(frame["level_id"]) >= {0, 1}
