"""
A CSV subset export takes the same filters a metadata plot does.

The plots run a filter against events joined to their sublevels and experiment, so a
condition on a sublevel or experiment column works there, and an event qualifies if any
of its sublevels match. The export and the count taken before it used to run the filter
against ``events`` alone, so the same condition failed with ``no such column``. Both now
select through the same join, and each exported event still carries all its sublevels.
"""

import sqlite3
from pathlib import Path
from typing import Iterator, Set, Tuple

import pandas as pd
import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.unit.plugins.conformance._recipes import (
    METADATA_CHANNELS,
    METADATA_EVENT_COUNTS,
    METADATA_EXPERIMENT,
    build_db_loader,
)

pytestmark = pytest.mark.conformance

SCOPE = {METADATA_EXPERIMENT: list(METADATA_CHANNELS)}


@pytest.fixture
def loader(metadata_db_path) -> Iterator[SQLiteDBLoader]:
    """
    The shipped loader over the two-channel conformance metadata database.

    :param metadata_db_path: the conformance metadata database
    :return: the loader
    :rtype: Iterator[SQLiteDBLoader]
    """
    db_loader = build_db_loader(SQLiteDBLoader, metadata_db_path)
    assert isinstance(db_loader, SQLiteDBLoader)
    yield db_loader
    db_loader.close_resources()


def plotted_events(loader: SQLiteDBLoader, condition: str) -> Set[Tuple[int, int]]:
    """
    The events a metadata plot selects for a filter, as (channel_id, event_id).

    :param loader: the loader
    :type loader: SQLiteDBLoader
    :param condition: the filter
    :type condition: str
    :return: the selected events
    :rtype: Set[Tuple[int, int]]
    """
    frame = loader.load_metadata(["duration"], condition, SCOPE)
    assert frame is not None
    return {(int(c), int(e)) for c, e in zip(frame["channel_id"], frame["event_id"])}


def exported_events(
    loader: SQLiteDBLoader, condition: str, out: Path
) -> Set[Tuple[int, int]]:
    """
    Export a subset and read back which events it wrote, as (channel_id, event_id).

    :param loader: the loader
    :type loader: SQLiteDBLoader
    :param condition: the filter
    :type condition: str
    :param out: an empty folder to export into
    :type out: Path
    :return: the exported events
    :rtype: Set[Tuple[int, int]]
    """
    for _progress in loader.export_subset_to_csv(str(out), "s", condition, SCOPE):
        pass
    frame = pd.read_csv(out / "s_events.csv")
    return {(int(c), int(e)) for c, e in zip(frame["channel_id"], frame["event_id"])}


def half_by_first_level(path: str) -> str:
    """
    A sublevel filter that selects about half the events.

    The fixture's events share their durations, and every event's padding levels sit
    near the open-pore current, so the filter names the first blocked level and splits
    it at its median current. A filter that silently ignored the sublevel condition, or
    applied it to the wrong table, could not select exactly the plot's half.

    :param path: the database
    :type path: str
    :return: the filter
    :rtype: str
    """
    connection = sqlite3.connect(path)
    try:
        currents = sorted(
            row[0]
            for row in connection.execute(
                "SELECT sublevel_current FROM sublevels WHERE level_id = 1"
            )
        )
    finally:
        connection.close()
    return f"level_id = 1 AND sublevel_current > {currents[len(currents) // 2]}"


def test_a_sublevel_filter_exports_what_the_plot_selects(
    loader: SQLiteDBLoader, metadata_db_path, tmp_path: Path
) -> None:
    """An event is exported when any of its sublevels matches, as it is plotted."""
    condition = half_by_first_level(metadata_db_path)
    plotted = plotted_events(loader, condition)
    assert 0 < len(plotted) < sum(METADATA_EVENT_COUNTS)

    assert loader.count_subset_events(condition, SCOPE) == len(plotted)
    assert exported_events(loader, condition, tmp_path) == plotted


def test_an_exported_event_keeps_all_its_sublevels(
    loader: SQLiteDBLoader, metadata_db_path, tmp_path: Path
) -> None:
    """
    The filter chooses events; it does not cut an exported event's sublevels down to
    the ones that matched.
    """
    condition = half_by_first_level(metadata_db_path)
    exported_events(loader, condition, tmp_path)

    events = pd.read_csv(tmp_path / "s_events.csv")
    sublevels = pd.read_csv(tmp_path / "s_sublevels.csv")
    per_event = sublevels.groupby("event_db_id").size()
    assert set(per_event.index) == set(events["id"])
    assert (per_event.reindex(events["id"]) == events["num_sublevels"].values).all()


def test_an_experiment_filter_exports_what_the_plot_selects(
    loader: SQLiteDBLoader, tmp_path: Path
) -> None:
    """A condition on an experiment column runs in the export as it does in a plot."""
    condition = "voltage > 0"
    plotted = plotted_events(loader, condition)
    assert len(plotted) == sum(METADATA_EVENT_COUNTS)

    assert loader.count_subset_events(condition, SCOPE) == len(plotted)
    assert exported_events(loader, condition, tmp_path) == plotted


def test_an_events_filter_exports_as_it_did(
    loader: SQLiteDBLoader, tmp_path: Path
) -> None:
    """A filter on an events column selects the same events through the join."""
    condition = "duration > 0"
    plotted = plotted_events(loader, condition)

    assert exported_events(loader, condition, tmp_path) == plotted


def test_a_column_both_tables_have_is_read_from_events(
    loader: SQLiteDBLoader, tmp_path: Path
) -> None:
    """
    ``channel_id`` is in both events and sublevels; it is qualified against events, as
    the plots qualify it, rather than refused as ambiguous.
    """
    condition = f"channel_id = {METADATA_CHANNELS[0]}"
    plotted = plotted_events(loader, condition)
    assert len(plotted) == METADATA_EVENT_COUNTS[0]

    assert exported_events(loader, condition, tmp_path) == plotted


def test_a_bare_id_is_refused_as_ambiguous(loader: SQLiteDBLoader) -> None:
    """
    ``id`` names a different row in each joined table, so the export says how to write
    the one meant - the plots' guidance, not SQLite's bare "ambiguous column name".
    """
    with pytest.raises(ValueError, match='write "e.id" for a row of events'):
        loader.count_subset_events("id > 0", SCOPE)
