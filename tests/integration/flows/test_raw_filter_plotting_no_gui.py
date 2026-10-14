"""
A raw SQL subset filter, saved, is also plotted - through a real loader.

The cases are the example queries in ``filtering_and_querying.rst``, each run as the
Metadata tab runs a raw filter: selected in the combobox, plotted from the parameters the
controls panel sends, against a real ``SQLiteDBLoader`` over the synthetic database. A raw
filter scopes itself - ``:experiment_id`` and ``:channel_id`` in its text are replaced by
the selected experiment's id and the channel - so the assertion is on the rows that
reached the plot, compared with the same query run straight against the database file with
those numbers in, and does not name any internal method.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad

LOADER = "loader"
SCOPE = "experiment_id = :experiment_id AND channel_id = :channel_id"

#: The documented raw examples, as (subset name, query, the column plotted). The
#: thresholds of examples 2, 3 and 5 are scaled to the synthetic database, whose events
#: all last 500, block to about 400 and carry three sublevels - the literal queries
#: match no row of it, and an empty subset is a different assertion from a plotted one.
DOCUMENTED = [
    (
        "long_raw",
        f"SELECT duration FROM events WHERE duration > 100 AND {SCOPE}",
        "duration",
    ),
    (
        "blocked_raw",
        f"SELECT duration, max_blockage FROM events WHERE max_blockage > 350 AND {SCOPE}",
        "duration",
    ),
    (
        "sublevels_raw",
        "SELECT fitted_ecd FROM events WHERE num_sublevels >= 3 "
        f"AND max_blockage > 350 AND {SCOPE}",
        "fitted_ecd",
    ),
    (
        "cross_table_raw",
        f"SELECT duration FROM events WHERE {SCOPE} AND id IN "
        "(SELECT event_db_id FROM sublevels WHERE sublevel_duration > 200)",
        "duration",
    ),
    (
        "aggregate_raw",
        f"SELECT duration FROM events WHERE {SCOPE} AND id IN "
        "(SELECT event_db_id FROM sublevels GROUP BY event_db_id HAVING COUNT(*) >= 3)",
        "duration",
    ),
    (
        "computed_raw",
        "SELECT duration, max_blockage - min_blockage AS blockage_range FROM events "
        f"WHERE {SCOPE}",
        "blockage_range",
    ),
]


@pytest.fixture
def metadata_tab(qapp: Any, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """
    A metadata tab with a real loader, the documented raw filters and a few more.

    :param qapp: pytest-qt's application fixture; MainView is a real widget
    :type qapp: Any
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param sample_metadata_db: path to a generated metadata database
    :type sample_metadata_db: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_triad("MetadataController", tmp_path)
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = sample_metadata_db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER)

    view = triad.tab_view
    combo = view._subset_controls.filter_comboBox
    filters = {name: query for name, query, _ in DOCUMENTED}
    filters["short"] = "duration >= 0"
    filters["forgot_raw"] = "SELECT duration FROM events"
    filters["events_raw"] = f"SELECT event_id, duration FROM events WHERE {SCOPE}"
    filters["no_event_id_raw"] = f"SELECT duration FROM events WHERE {SCOPE}"
    # SELECT * over a join returns both tables' key columns, which are equal.
    filters["join_raw"] = (
        "SELECT * FROM sublevels s JOIN events e ON s.event_db_id = e.id "
        "WHERE e.experiment_id = :experiment_id AND e.channel_id = :channel_id"
    )
    filters["aliased_raw"] = (
        "SELECT e.event_id, s.id AS sublevel_id, e.duration FROM events e "
        "JOIN sublevels s ON s.event_db_id = e.id "
        "WHERE e.experiment_id = :experiment_id AND e.channel_id = :channel_id"
    )
    # A sublevel's id, where an event is wanted: a different row in each table.
    filters["sublevel_id_raw"] = (
        "SELECT s.id AS id FROM sublevels s "
        "WHERE s.experiment_id = :experiment_id AND s.channel_id = :channel_id"
    )
    # A number that is not an event's: it names events the channel does not have.
    filters["mislabelled_raw"] = (
        f"SELECT event_id + 100000 AS event_id FROM events WHERE {SCOPE}"
    )
    filters["nav_raw"] = f"SELECT event_id FROM events WHERE duration > 100 AND {SCOPE}"
    filters["nav_join_raw"] = (
        "SELECT * FROM sublevels s JOIN events e ON s.event_db_id = e.id "
        "WHERE e.experiment_id = :experiment_id AND e.channel_id = :channel_id"
    )
    for name, query in filters.items():
        view.subset_filters[name] = query
        combo.addItem(name)

    yield triad

    triad.close()


def plot(
    triad: Triad,
    filter_name: str,
    column: str,
    channels: List[str],
    plot_type: str = "Histogram",
) -> Dict[str, Any]:
    """
    Select one filter and the given channels, then press Plot, as a user would.

    :param triad: the tab under test
    :type triad: Triad
    :param filter_name: the filter to select
    :type filter_name: str
    :param column: the column on the histogram's x axis
    :type column: str
    :param channels: the channels to select, as the selection tree reports them
    :type channels: List[str]
    :param plot_type: the plot to draw
    :type plot_type: str
    :return: the parameters sent
    :rtype: Dict[str, Any]
    """
    view = triad.tab_view
    combo = view._subset_controls.filter_comboBox
    for name in list(combo.getSelectedItems()):
        combo.selectItem(name, select=False)
    combo.selectItem(filter_name, select=True)
    view.selected_experiment_and_channels_by_loader[LOADER] = {"exp_a": channels}
    parameters = {
        "db_loader": LOADER,
        "plot_type": plot_type,
        "x_axis": column,
        "y_axis": column,
        "z_axis": column,
        "x_log": False,
        "y_log": False,
        "z_log": False,
        "bins": [20],
        "sizes": False,
    }
    view.handle_parameter_change("metadatacontrols", "update_plot", (parameters,))
    return parameters


def rows_for(db_path: str, query: str, channel: int) -> int:
    """
    Run a query straight against the database file for one channel and count its rows.

    :param db_path: the metadata database
    :type db_path: str
    :param query: a complete SELECT with the two scope placeholders
    :type query: str
    :param channel: the channel to bind
    :type channel: int
    :return: the number of rows it returns
    :rtype: int
    """
    with sqlite3.connect(db_path) as conn:
        experiment = conn.execute(
            "SELECT id FROM experiments WHERE name = 'exp_a'"
        ).fetchone()[0]
        bound = query.replace(":experiment_id", str(experiment)).replace(
            ":channel_id", str(channel)
        )
        return len(conn.execute(bound).fetchall())


@pytest.mark.timeout(120)
@pytest.mark.parametrize(("name", "query", "column"), DOCUMENTED)
def test_a_documented_raw_filter_plots_exactly_its_own_rows_in_the_selected_channel(
    metadata_tab: Triad,
    sample_metadata_db: str,
    name: str,
    query: str,
    column: str,
) -> None:
    """
    The rows on the plot are the query's rows for the selected channel, not the whole
    database: the query scopes itself.
    """
    plot(metadata_tab, name, column, ["0"])

    view = metadata_tab.tab_view
    assert {(entry[2], entry[4]) for entry in view.plotted_datasets} == {(0, name)}
    assert len(view.plot_data) == rows_for(sample_metadata_db, query, 0)
    assert column in view.plot_data.columns


@pytest.mark.timeout(120)
def test_a_raw_filter_is_drawn_once_per_selected_channel(metadata_tab: Triad) -> None:
    """
    Like an assisted filter: one dataset per channel, each for its own.
    """
    plot(metadata_tab, "long_raw", "duration", ["0", "1"])

    datasets = {
        (entry[2], entry[4]) for entry in metadata_tab.tab_view.plotted_datasets
    }
    assert datasets == {(0, "long_raw"), (1, "long_raw")}


@pytest.mark.timeout(120)
def test_a_raw_filter_that_ignores_the_selection_is_warned_about_and_still_plots(
    metadata_tab: Triad, sample_metadata_db: str
) -> None:
    """
    No placeholders, so every channel gets the whole database - which the panel says.
    """
    plot(metadata_tab, "forgot_raw", "duration", ["0"])

    view = metadata_tab.tab_view
    with sqlite3.connect(sample_metadata_db) as conn:
        everything = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert len(view.plot_data) == everything
    assert (
        "ignores the Scope selection" in metadata_tab.tab_controller._last_scope_warning
    )


@pytest.mark.timeout(120)
def test_a_plotted_column_the_query_does_not_return_draws_nothing(
    metadata_tab: Triad,
) -> None:
    """
    The user's projection is the plot's data: what it lacks is reported, not drawn.
    """
    plot(metadata_tab, "no_event_id_raw", "max_blockage", ["0"])

    assert metadata_tab.tab_view.plotted_datasets == set()


@pytest.mark.timeout(120)
def test_an_assisted_filter_is_still_scoped_beside_a_raw_one(
    metadata_tab: Triad,
) -> None:
    """
    The scoped path is unchanged: one dataset per channel, restricted to it.
    """
    plot(metadata_tab, "long_raw", "duration", ["0"])
    plot(metadata_tab, "short", "duration", ["0", "1"])

    datasets = {
        (entry[2], entry[4]) for entry in metadata_tab.tab_view.plotted_datasets
    }
    assert datasets == {(0, "long_raw"), (0, "short"), (1, "short")}


@pytest.mark.timeout(120)
def test_a_raw_filter_plots_an_all_points_histogram_of_the_selected_events(
    metadata_tab: Triad,
) -> None:
    """
    Event-data plots take the events the query names for the selected channel; it
    returns only ``event_id``, because it scoped itself.
    """
    plot(
        metadata_tab,
        "events_raw",
        "duration",
        ["1"],
        plot_type="Raw All Points Histogram",
    )

    view = metadata_tab.tab_view
    assert {(entry[2], entry[4]) for entry in view.plotted_datasets} == {
        (1, "events_raw")
    }
    assert "channel_id = 1" in view.event_query
    assert view.hist_max is not None


@pytest.mark.timeout(120)
def test_a_raw_filter_without_event_id_draws_no_event_plot(
    metadata_tab: Triad,
) -> None:
    """
    Nothing names the events to load, so nothing is drawn.
    """
    plot(
        metadata_tab,
        "no_event_id_raw",
        "duration",
        ["0"],
        plot_type="Raw All Points Histogram",
    )

    assert metadata_tab.tab_view.plotted_datasets == set()


@pytest.mark.timeout(120)
def test_a_join_returning_the_key_twice_still_plots_an_event_plot(
    metadata_tab: Triad,
) -> None:
    """
    ``SELECT *`` over a join returns the sublevel's key beside the event's, and the two
    are equal, so the events are named correctly however the join is written.
    """
    plot(
        metadata_tab,
        "join_raw",
        "duration",
        ["0"],
        plot_type="Raw All Points Histogram",
    )

    assert {(e[2], e[4]) for e in metadata_tab.tab_view.plotted_datasets} == {
        (0, "join_raw")
    }


@pytest.mark.timeout(120)
def test_a_join_that_names_its_columns_plots_an_event_plot(metadata_tab: Triad) -> None:
    """
    Naming the sublevel's ``id`` differently keeps it beside the event's key.
    """
    plot(
        metadata_tab,
        "aliased_raw",
        "duration",
        ["0"],
        plot_type="Raw All Points Histogram",
    )

    assert {(e[2], e[4]) for e in metadata_tab.tab_view.plotted_datasets} == {
        (0, "aliased_raw")
    }


@pytest.mark.timeout(120)
def test_an_id_column_does_not_name_an_event(metadata_tab: Triad) -> None:
    """
    ``id`` is a different row in each table, so a sublevel's cannot stand for an event:
    the query is asked for ``event_id`` instead of loading the wrong events.
    """
    plot(
        metadata_tab,
        "sublevel_id_raw",
        "duration",
        ["1"],
        plot_type="Raw All Points Histogram",
    )

    assert metadata_tab.tab_view.plotted_datasets == set()


@pytest.mark.timeout(120)
def test_a_key_that_names_no_event_draws_no_event_plot(metadata_tab: Triad) -> None:
    """
    A column labelled ``event_id`` whose values are not the channel's events is refused.
    """
    plot(
        metadata_tab,
        "mislabelled_raw",
        "duration",
        ["0"],
        plot_type="Raw All Points Histogram",
    )

    assert metadata_tab.tab_view.plotted_datasets == set()


def navigate(triad: Triad, filter_name: str, action: str, channel: str = "0") -> None:
    """
    Select one filter and one channel, then press Plot Events or an arrow.

    :param triad: the tab under test
    :type triad: Triad
    :param filter_name: the filter to select
    :type filter_name: str
    :param action: ``plot_events``, ``shift_range_forward`` or ``shift_range_backward``
    :type action: str
    :param channel: the channel to select, as the selection tree reports it
    :type channel: str
    """
    view = triad.tab_view
    combo = view._subset_controls.filter_comboBox
    for name in list(combo.getSelectedItems()):
        combo.selectItem(name, select=False)
    combo.selectItem(filter_name, select=True)
    view.selected_experiment_and_channels_by_loader[LOADER] = {"exp_a": [channel]}
    view.handle_parameter_change(
        "metadatacontrols",
        action,
        ({"db_loader": LOADER, "event_id": 0, "n_events": 1},),
    )


@pytest.mark.timeout(120)
def test_plot_events_takes_its_event_list_from_a_raw_filter(
    metadata_tab: Triad, sample_metadata_db: str
) -> None:
    """
    The events stepped through are the raw query's, within the selected channel.
    """
    navigate(metadata_tab, "nav_raw", "plot_events")

    view = metadata_tab.tab_view
    with sqlite3.connect(sample_metadata_db) as conn:
        expected = sorted(
            r[0]
            for r in conn.execute(
                "SELECT event_id FROM events WHERE duration > 100 AND channel_id = 0"
            )
        )
    assert view.filtered_event_ids == expected
    assert expected


@pytest.mark.timeout(120)
def test_the_arrows_step_through_a_raw_filters_events(metadata_tab: Triad) -> None:
    """
    Navigation reads the same list, so an arrow moves to the next event in it.
    """
    navigate(metadata_tab, "nav_raw", "plot_events")
    first = metadata_tab.tab_view.filtered_event_ids[0]

    navigate(metadata_tab, "nav_raw", "shift_range_forward")

    assert metadata_tab.tab_view.filtered_event_ids[0] == first
    assert "experiment_id = :experiment_id" in metadata_tab.tab_view.current_sql_filter


@pytest.mark.timeout(120)
def test_plot_events_refuses_a_raw_filter_without_event_id(
    metadata_tab: Triad,
) -> None:
    """
    No ``event_id`` column: nothing is navigated.
    """
    navigate(metadata_tab, "no_event_id_raw", "plot_events")

    assert not metadata_tab.tab_view.filtered_event_ids


@pytest.mark.timeout(120)
def test_plot_events_lists_each_event_once_for_a_join(
    metadata_tab: Triad, sample_metadata_db: str
) -> None:
    """
    A join repeats an event once per sublevel; the list holds it once.
    """
    navigate(metadata_tab, "nav_join_raw", "plot_events")

    with sqlite3.connect(sample_metadata_db) as conn:
        expected = sorted(
            r[0]
            for r in conn.execute("SELECT event_id FROM events WHERE channel_id = 0")
        )
    assert metadata_tab.tab_view.filtered_event_ids == expected


@pytest.mark.timeout(120)
def test_a_dataset_whose_query_ignores_the_scope_says_so_in_its_label(
    metadata_tab: Triad,
) -> None:
    """
    The label names the ticked channel, so a query that does not use it is marked: its rows
    are not that channel's. A query that scopes itself is not.
    """
    plot(metadata_tab, "forgot_raw", "duration", ["0", "1"])
    labels = list(metadata_tab.tab_view.hist_labels)

    assert labels
    assert all(label.endswith("(query ignores Scope)") for label in labels)

    metadata_tab.tab_view.handle_parameter_change(
        "metadatacontrols", "reset_plot", ({},)
    )
    plot(metadata_tab, "long_raw", "duration", ["0"])

    assert not any(
        "ignores Scope" in label for label in metadata_tab.tab_view.hist_labels
    )
