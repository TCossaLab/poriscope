"""
Raw SQL filter edge cases, run against a real loader and database.

Each test states what a user would need to be told, or what must match a SQL viewer, and
runs it for real. A test that fails here is a silent wrong answer.
"""

import sqlite3
from typing import Any, Dict
from unittest.mock import Mock

import pytest

from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.synthetic_data.synthetic_metadata_db import generate_metadata_database

SCOPE_CH0 = {"exp_a": [0]}
SCOPE_CH1 = {"exp_a": [1]}
SCOPED = "experiment_id = :experiment_id AND channel_id = :channel_id"


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


def panel_of(controller: MetadataController) -> str:
    """
    Everything the controller put on the status panel, joined.

    :param controller: the controller under test
    :type controller: MetadataController
    :return: the messages
    :rtype: str
    """
    return " ".join(controller.panel)  # type: ignore[attr-defined]


def query(db_path: str, sql: str) -> list:
    """
    Run a query straight against the database file.

    :param db_path: the metadata database
    :type db_path: str
    :param sql: the query
    :type sql: str
    :return: its rows
    :rtype: list
    """
    with sqlite3.connect(db_path) as conn:
        return conn.execute(sql).fetchall()


@pytest.mark.timeout(120)
def test_a_limit_counts_the_selected_channels_rows_not_the_whole_database(
    controller: MetadataController,
) -> None:
    """
    The scope sits in the query's own WHERE, so ``LIMIT 5`` gives each channel its own
    five - where applying the selection afterwards split the database's five between
    them.
    """
    sql = f"SELECT duration FROM events WHERE {SCOPED} ORDER BY start_time DESC LIMIT 5"

    for scope in (SCOPE_CH0, SCOPE_CH1):
        run = controller._run_raw_filter("L", sql, scope, "x_raw")
        assert run is not None
        assert len(run.rows) == 5


@pytest.mark.timeout(120)
def test_an_aggregate_is_computed_on_each_channels_own_rows(
    controller: MetadataController, sample_metadata_db: str
) -> None:
    """
    One row per channel, each the average of its own events - not an arbitrary row of a
    whole-database aggregate.
    """
    sql = f"SELECT AVG(start_time) AS m FROM events WHERE {SCOPED}"

    for channel, scope in ((0, SCOPE_CH0), (1, SCOPE_CH1)):
        run = controller._run_raw_filter("L", sql, scope, "x_raw")
        assert run is not None and len(run.rows) == 1
        expected = query(
            sample_metadata_db,
            f"SELECT AVG(start_time) FROM events WHERE channel_id = {channel}",
        )[0][0]
        assert run.rows["m"].iloc[0] == pytest.approx(expected)


@pytest.mark.timeout(120)
def test_a_query_that_only_scopes_a_subquery_is_warned_about(
    controller: MetadataController, sample_metadata_db: str
) -> None:
    """
    The main table is not scoped, so channel 1's rows come back for channel 0, and the
    panel says how many instead of drawing them under channel 0's name unremarked.
    """
    sql = (
        "SELECT experiment_id, channel_id, duration FROM events WHERE duration >= "
        "(SELECT AVG(duration) FROM events WHERE experiment_id = :experiment_id "
        "AND channel_id = :channel_id)"
    )

    run = controller._run_raw_filter("L", sql, SCOPE_CH0, "x_raw")

    assert run is not None
    other = query(
        sample_metadata_db, "SELECT COUNT(*) FROM events WHERE channel_id = 1"
    )[0][0]
    assert f"{other} of {len(run.rows)} rows" in panel_of(controller)
    assert "other experiments or channels" in panel_of(controller)


@pytest.mark.timeout(120)
def test_a_query_that_uses_only_one_placeholder_is_warned_about(
    controller: MetadataController,
) -> None:
    """
    The same rows would be drawn for every channel of the experiment.
    """
    sql = "SELECT duration FROM events WHERE experiment_id = :experiment_id"

    run = controller._run_raw_filter("L", sql, SCOPE_CH0, "x_raw")

    assert run is not None
    assert "uses :experiment_id but not :channel_id" in panel_of(controller)


@pytest.mark.timeout(120)
def test_only_a_select_is_run_and_the_database_is_untouched(
    controller: MetadataController, sample_metadata_db: str
) -> None:
    """
    The loader's validator accepts a DELETE; Poriscope does not run it.
    """
    before = query(sample_metadata_db, "SELECT COUNT(*) FROM events")

    for sql in ("DELETE FROM events", "UPDATE events SET duration = 1"):
        assert controller._run_raw_filter("L", sql, SCOPE_CH0, "x_raw") is None

    assert query(sample_metadata_db, "SELECT COUNT(*) FROM events") == before
    assert "not a SELECT" in panel_of(controller)


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT duration FROM events WHERE experiment_id = :experiment_id "
        "AND channel_id = :channel_id ORDER BY duration LIMIT 5",
        "SELECT duration FROM events WHERE channel_id = :channel_id LIMIT 5 OFFSET 2",
        "SELECT duration FROM events WHERE channel_id = :channel_id -- only this one",
    ],
)
def test_a_raw_filter_with_its_own_limit_or_a_trailing_comment_can_be_saved(
    controller: MetadataController, sql: str
) -> None:
    """
    The check validates the text as written. It used to add ``LIMIT 0``, which made a
    filter that ends in its own ``LIMIT`` a syntax error, so it could not be saved.
    """
    controller.validate_raw_filter("L", sql, "x_raw", None)

    valid = controller.view.on_raw_filter_validated.call_args[0][0]
    assert valid is True


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    "sql",
    [
        "WITH x AS (SELECT 1) DELETE FROM events",
        "WITH x AS (SELECT 1) UPDATE events SET duration = 1",
    ],
)
def test_a_write_behind_a_with_changes_nothing(tmp_path: Any, sql: str) -> None:
    """
    ``WITH x AS (...) DELETE`` starts like a read, and Python's SQLite module commits it.
    Poriscope refuses it, and the loader's read connection could not write it anyway -
    each layer on its own, on a scratch database.
    """
    scratch = generate_metadata_database(
        tmp_path / "scratch.sqlite3",
        experiments=[
            {
                "name": "exp_a",
                "channels": [{"channel_id": 0, "num_events": 5, "seed": 1}],
            }
        ],
    )
    path = str(scratch.db_path)
    ctrl = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
    ctrl.model = LoaderModel(open_loader(path))  # type: ignore[assignment]
    ctrl.logger = Mock()  # type: ignore[assignment,method-assign]
    ctrl.panel = []  # type: ignore[attr-defined]
    ctrl.add_text_to_display = Mock()  # type: ignore[assignment,method-assign]
    ctrl.add_text_to_display.emit = lambda message, *_: ctrl.panel.append(message)  # type: ignore[attr-defined]
    before = query(path, "SELECT COUNT(*), SUM(duration) FROM events")

    assert ctrl._run_raw_filter("L", sql, None, "x_raw") is None
    assert "so it was not run" in panel_of(ctrl)
    assert query(path, "SELECT COUNT(*), SUM(duration) FROM events") == before

    # the second layer: past Poriscope's check, the loader's own read cannot write
    assert open_loader(path).query_database_directly(sql) is None
    assert query(path, "SELECT COUNT(*), SUM(duration) FROM events") == before


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
    parents = sorted(
        r[0]
        for r in query(
            sample_metadata_db,
            "SELECT DISTINCT e.event_id FROM sublevels s "
            "JOIN events e ON s.event_db_id = e.id WHERE s.id <= 10",
        )
    )
    by_id = sorted(
        r[0]
        for r in query(sample_metadata_db, "SELECT event_id FROM events WHERE id <= 10")
    )
    named = sorted(int(i) for i in conditions.split("IN (")[1].rstrip(")").split(","))
    assert named == parents
    assert named != by_id


@pytest.mark.timeout(120)
def test_rows_with_a_null_event_id_are_reported_not_dropped_silently(
    controller: MetadataController, sample_metadata_db: str
) -> None:
    """
    A CASE can leave event_id NULL on some rows, which then name no event. They are left
    out of the plot, and the panel says how many.
    """
    sql = (
        "SELECT CASE WHEN event_id % 2 = 0 THEN event_id END AS event_id FROM events "
        f"WHERE {SCOPED}"
    )

    out = controller._raw_filter_conditions("L", sql, SCOPE_CH0, "x_raw")

    assert out is not None
    panel = panel_of(controller)
    assert "NULL" in panel and "left out" in panel


@pytest.mark.timeout(120)
def test_what_an_event_plot_selected_is_stated_on_the_panel(
    controller: MetadataController, sample_metadata_db: str
) -> None:
    """
    How many events, on which channel, and their range - so a key that names other
    events than the user meant is visible.
    """
    sql = f"SELECT event_id FROM events WHERE {SCOPED}"

    out = controller._raw_filter_conditions("L", sql, SCOPE_CH0, "x_raw")

    assert out is not None
    count = query(
        sample_metadata_db, "SELECT COUNT(*) FROM events WHERE channel_id = 0"
    )[0][0]
    assert f"x_raw: {count} events on exp_a Ch 0" in panel_of(controller)


@pytest.mark.timeout(120)
@pytest.mark.parametrize("scope", [None, {}])
def test_with_no_scope_a_raw_filter_returns_what_an_assisted_one_does(
    controller: MetadataController, scope: Any
) -> None:
    """
    No experiment named means no restriction for either kind of filter, so a raw filter
    without placeholders runs and returns every row, as an assisted one does.
    """
    assisted = controller.model.call(
        "M", "L", "load_metadata", ["duration"], "duration > 0", scope
    )

    run = controller._run_raw_filter("L", "SELECT duration FROM events", scope, "x_raw")

    assert run is not None
    assert len(run.rows) == len(assisted) > 0
    assert "ignores the Scope selection" not in panel_of(controller)


@pytest.mark.timeout(120)
def test_the_event_counts_the_probes_rely_on(sample_metadata_db: str) -> None:
    """
    Both channels hold more than the limit the tests above use.

    :param sample_metadata_db: path to a generated metadata database
    :type sample_metadata_db: str
    """
    counts: Dict[int, int] = dict(
        query(
            sample_metadata_db,
            "SELECT channel_id, COUNT(*) FROM events GROUP BY channel_id",
        )
    )
    assert counts and min(counts.values()) > 5


@pytest.mark.timeout(120)
def test_an_unbracketed_or_that_leaks_is_warned_about_when_the_result_has_the_keys(
    controller: MetadataController, sample_metadata_db: str
) -> None:
    """
    ``a OR b AND scope`` scopes only ``b``; with the key columns returned the leak is
    counted, and the warning names the unbracketed ``OR`` as a cause.
    """
    sql = (
        "SELECT experiment_id, channel_id, event_id FROM events "
        "WHERE duration > 0 OR max_blockage > 0 "
        "AND experiment_id = :experiment_id AND channel_id = :channel_id"
    )

    run = controller._run_raw_filter("L", sql, SCOPE_CH0, "x_raw")

    assert run is not None
    assert set(run.rows["channel_id"]) == {0, 1}
    assert "OR is not in brackets" in panel_of(controller)


@pytest.mark.timeout(120)
def test_a_missing_column_of_another_table_is_told_to_join_it(
    controller: MetadataController,
) -> None:
    """
    ``sublevel_duration`` is not in ``events``, so adding it to the ``SELECT`` is not
    enough; the message names its table and shows the join.
    """
    sql = (
        "SELECT event_id, duration FROM events "
        "WHERE experiment_id = :experiment_id AND channel_id = :channel_id"
    )

    controller.load_metadata_subset("L", ["sublevel_duration"], sql, SCOPE_CH0, "x_raw")

    panel = panel_of(controller)
    assert "needs: sublevel_duration" in panel
    assert "column of the sublevels table" in panel
    assert "JOIN sublevels s ON s.event_db_id = e.id" in panel


@pytest.mark.timeout(120)
def test_a_missing_column_of_events_is_told_to_add_it_to_the_select(
    controller: MetadataController,
) -> None:
    """
    A column of ``events`` only has to be added to the column list.
    """
    sql = (
        "SELECT event_id FROM events "
        "WHERE experiment_id = :experiment_id AND channel_id = :channel_id"
    )

    controller.load_metadata_subset("L", ["duration"], sql, SCOPE_CH0, "x_raw")

    panel = panel_of(controller)
    assert "needs: duration" in panel
    assert "Add duration to its SELECT" in panel
    assert "JOIN" not in panel
