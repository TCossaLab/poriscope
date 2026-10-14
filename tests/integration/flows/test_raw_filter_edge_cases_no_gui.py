"""
Raw SQL filter edge cases, run against a real loader and database.

Each test states what a user would need to be told, or what must match an Assisted
filter, and runs it for real. A test that fails here is a silent wrong answer.
"""

import sqlite3
from typing import Any, Dict
from unittest.mock import Mock

import pytest

from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader

SCOPE_CH0 = {"exp_a": [0]}


def open_loader(db_path: str) -> SQLiteDBLoader:
    """
    A real loader over a database file.

    :param db_path: the metadata database to read
    :type db_path: str
    :return: the configured loader
    :rtype: SQLiteDBLoader
    """
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = db_path
    loader.apply_settings(settings)
    return loader


class LoaderModel:
    """
    A Model whose ``call`` goes straight to a real loader.
    """

    def __init__(self, loader: SQLiteDBLoader) -> None:
        """
        :param loader: the loader every call is made on
        :type loader: SQLiteDBLoader
        """
        self.loader = loader

    def call(self, metaclass: str, key: str, method: str, *args: Any) -> Any:
        """
        Call the loader's method.

        :param metaclass: ignored
        :type metaclass: str
        :param key: ignored
        :type key: str
        :param method: the method to call
        :type method: str
        :param args: its arguments
        :type args: Any
        :return: whatever the loader returns
        :rtype: Any
        """
        return getattr(self.loader, method)(*args)


@pytest.fixture
def controller(sample_metadata_db: str) -> MetadataController:
    """
    A bare Metadata controller that queries the real synthetic database.

    :param sample_metadata_db: path to a generated metadata database
    :type sample_metadata_db: str
    :return: the controller, with ``panel`` collecting what it said
    :rtype: MetadataController
    """
    ctrl = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
    ctrl.model = LoaderModel(open_loader(sample_metadata_db))  # type: ignore[assignment]
    ctrl.view = Mock()
    ctrl.logger = Mock()  # type: ignore[assignment,method-assign]
    ctrl.panel = []  # type: ignore[attr-defined]
    ctrl.add_text_to_display = Mock()  # type: ignore[assignment,method-assign]
    ctrl.add_text_to_display.emit = lambda message, *_: ctrl.panel.append(message)  # type: ignore[attr-defined]
    return ctrl


def event_counts(db_path: str) -> Dict[int, int]:
    """
    How many events each channel holds.

    :param db_path: the metadata database
    :type db_path: str
    :return: channel to event count
    :rtype: Dict[int, int]
    """
    with sqlite3.connect(db_path) as conn:
        return dict(
            conn.execute("SELECT channel_id, COUNT(*) FROM events GROUP BY channel_id")
        )


@pytest.mark.timeout(120)
def test_a_sublevels_key_names_its_parent_event(
    controller: MetadataController, sample_metadata_db: str
) -> None:
    """
    A sublevel carries its parent event's experiment, channel and event number, so a
    query on sublevels names the right events - not the events whose ``id`` happens to
    equal a sublevel's, which is what trusting ``id`` would have loaded.
    """
    sql = (
        "SELECT s.experiment_id, s.channel_id, s.event_id FROM sublevels s "
        "WHERE s.id <= 10"
    )

    out = controller._raw_filter_conditions("L", sql, SCOPE_CH0, "x_raw")

    assert out is not None
    conditions, _ = out
    with sqlite3.connect(sample_metadata_db) as conn:
        parents = sorted(
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT e.event_id FROM sublevels s "
                "JOIN events e ON s.event_db_id = e.id WHERE s.id <= 10"
            )
        )
        by_id = sorted(
            r[0] for r in conn.execute("SELECT event_id FROM events WHERE id <= 10")
        )
    named = sorted(int(i) for i in conditions.split("IN (")[1].rstrip(")").split(","))
    assert named == parents
    assert named != by_id


@pytest.mark.timeout(120)
def test_rows_with_null_scope_columns_are_not_dropped_without_saying_so(
    controller: MetadataController, sample_metadata_db: str
) -> None:
    """
    A LEFT JOIN, or a CASE, can leave experiment_id NULL on some rows; the selection's
    WHERE drops them. The panel should say that rows were left out.
    """
    sql = (
        "SELECT CASE WHEN event_id % 2 = 0 THEN experiment_id END AS experiment_id, "
        "channel_id, duration FROM events"
    )

    out = controller._run_raw_filter("L", sql, SCOPE_CH0, "x_raw")

    assert out is not None
    rows, _ = out
    assert len(rows) < event_counts(sample_metadata_db)[0]
    assert any(
        "null" in message.lower() or "left out" in message.lower()
        for message in controller.panel  # type: ignore[attr-defined]
    ), "rows were dropped for a NULL scope column and nothing said so"


@pytest.mark.timeout(120)
def test_rows_with_a_null_event_id_are_reported_not_dropped_silently(
    controller: MetadataController, sample_metadata_db: str
) -> None:
    """
    A CASE can leave event_id NULL on some rows, which then name no event. They are left
    out of the plot, and the panel says how many.
    """
    sql = (
        "SELECT experiment_id, channel_id, "
        "CASE WHEN event_id % 2 = 0 THEN event_id END AS event_id FROM events"
    )

    out = controller._raw_filter_conditions("L", sql, SCOPE_CH0, "x_raw")

    assert out is not None
    panel = " ".join(controller.panel)  # type: ignore[attr-defined]
    assert "NULL" in panel and "left out" in panel
    with sqlite3.connect(sample_metadata_db) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM events WHERE channel_id = 0"
        ).fetchone()[0]
    odd = total - len([1 for r in range(total) if r % 2 == 0])
    assert odd > 0


@pytest.mark.timeout(120)
@pytest.mark.parametrize("scope", [None, {}])
def test_with_no_scope_a_raw_filter_returns_what_an_assisted_one_does(
    controller: MetadataController, scope: Any
) -> None:
    """
    No experiment named means no restriction for either kind of filter, so a raw filter
    without the scope columns runs and returns every row, as an assisted one does.
    """
    assisted = controller.model.call(
        "M", "L", "load_metadata", ["duration"], "duration > 0", scope
    )

    out = controller._run_raw_filter("L", "SELECT duration FROM events", scope, "x_raw")

    assert out is not None
    assert len(out[0]) == len(assisted) > 0
