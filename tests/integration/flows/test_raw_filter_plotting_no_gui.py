"""
A raw SQL subset filter, saved, is also plotted - through a real loader.

The cases are the example queries in ``filtering_and_querying.rst``, each run as the
Metadata tab runs a raw filter: selected in the combobox, plotted from the
parameters the controls panel sends, against a real ``SQLiteDBLoader`` over the
synthetic database. The assertion is on the rows that reached the plot, compared with
the same query run straight against the database file, so it does not name any
internal method.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad

LOADER = "loader"

#: The documented raw examples, as (subset name, query, the column plotted). The
#: thresholds of examples 2, 3 and 5 are scaled to the synthetic database, whose events
#: all last 500, block to about 400 and carry three sublevels - the literal queries
#: match no row of it, and an empty subset is a different assertion from a plotted one.
DOCUMENTED = [
    ("long_raw", "SELECT duration FROM events WHERE duration > 100", "duration"),
    (
        "blocked_raw",
        "SELECT duration, max_blockage FROM events WHERE max_blockage > 350",
        "duration",
    ),
    (
        "sublevels_raw",
        "SELECT fitted_ecd FROM events WHERE num_sublevels >= 3 AND max_blockage > 350",
        "fitted_ecd",
    ),
    (
        "cross_table_raw",
        "SELECT duration FROM events WHERE id IN "
        "(SELECT event_db_id FROM sublevels WHERE sublevel_duration > 200)",
        "duration",
    ),
    (
        "aggregate_raw",
        "SELECT duration FROM events WHERE id IN (SELECT event_db_id FROM sublevels "
        "GROUP BY event_db_id HAVING COUNT(*) >= 3)",
        "duration",
    ),
    (
        "computed_raw",
        "SELECT duration, max_blockage - min_blockage AS blockage_range FROM events",
        "blockage_range",
    ),
]


@pytest.fixture
def metadata_tab(qapp: Any, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """
    A metadata tab with a real loader, the documented raw filters and one assisted one.

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
    filters["missing_raw"] = "SELECT id FROM events"
    filters["short"] = "duration >= 0"
    for name, query in filters.items():
        view.subset_filters[name] = query
        combo.addItem(name)

    yield triad

    triad.close()


def plot(
    triad: Triad, filter_name: str, column: str, channels: List[str]
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
        "plot_type": "Histogram",
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


def rows_in_database(db_path: str, query: str) -> int:
    """
    Run a query straight against the database file and count its rows.

    :param db_path: the metadata database
    :type db_path: str
    :param query: a complete SELECT
    :type query: str
    :return: the number of rows it returns
    :rtype: int
    """
    with sqlite3.connect(db_path) as conn:
        return len(conn.execute(query).fetchall())


@pytest.mark.timeout(120)
@pytest.mark.parametrize(("name", "query", "column"), DOCUMENTED)
def test_a_documented_raw_filter_plots_exactly_its_own_rows(
    metadata_tab: Triad,
    sample_metadata_db: str,
    name: str,
    query: str,
    column: str,
) -> None:
    """
    The rows on the plot are the rows the query returns, however the selection reads.

    Two channels are selected on purpose: a raw filter ignores them, so it must be
    drawn once and from the whole database.
    """
    plot(metadata_tab, name, column, ["0", "1"])

    view = metadata_tab.tab_view
    assert {entry[4] for entry in view.plotted_datasets} == {name}
    assert len(view.plotted_datasets) == 1
    assert len(view.plot_data) == rows_in_database(sample_metadata_db, query)
    assert column in view.plot_data.columns


@pytest.mark.timeout(120)
def test_a_raw_filter_missing_a_plotted_column_draws_nothing(
    metadata_tab: Triad,
) -> None:
    """
    The user's projection is the plot's data: what it lacks is reported, not drawn.
    """
    plot(metadata_tab, "missing_raw", "duration", ["0"])

    assert metadata_tab.tab_view.plotted_datasets == set()


@pytest.mark.timeout(120)
def test_an_assisted_filter_is_still_scoped_beside_a_raw_one(
    metadata_tab: Triad, sample_metadata_db: str
) -> None:
    """
    The scoped path is unchanged: one dataset per channel, restricted to it.
    """
    plot(metadata_tab, "long_raw", "duration", ["0"])
    plot(metadata_tab, "short", "duration", ["0", "1"])

    datasets = {(entry[2], entry[4]) for entry in metadata_tab.tab_view.plotted_datasets}
    assert datasets == {(None, "long_raw"), (0, "short"), (1, "short")}
