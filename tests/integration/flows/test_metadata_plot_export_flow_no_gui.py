"""
Metadata tab, headless: what Export Plot Data writes after several datasets are plotted.

The reported symptom was a scatterplot of two datasets whose exported CSV held only
the last one. Every dataset is cached under the same two axis labels, and the export
once collapsed repeated labels into one column. The unit tests pin the formatting;
this one drives the whole path a user's export takes - plot, plot again, export - and
reads the file back.

What is real here: the shell, the Metadata triad, a real ``SQLiteDBLoader`` over the
synthetic database, the cache signal from the view to the model and the export slot.
What is not: the widgets' own clicks, stood in for by selecting filters on the real
filter combobox and calling the ``handle_parameter_change`` the controls panel calls,
and the save dialog, which returns a path in the test's scratch directory.
"""

import csv
import sqlite3
import statistics
from pathlib import Path
from typing import Any, Dict, List

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad

LOADER = "loader"


@pytest.fixture
def metadata_tab(qapp, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """
    A metadata tab with a real loader and two filters that select different events.

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

    # The cut is the median of this database's own channel 0, so the second filter
    # keeps some events and drops others. Start time is used because the generator
    # gives every event the same duration, which no cut could split.
    with sqlite3.connect(sample_metadata_db) as conn:
        start_times = [
            row[0]
            for row in conn.execute(
                "SELECT start_time FROM events WHERE channel_id = 0"
            )
        ]
    median = statistics.median(start_times)

    view = triad.tab_view
    combo = view._subset_controls.filter_comboBox
    view.subset_filters["everything"] = "start_time >= 0"
    combo.addItem("everything")
    view.subset_filters["long"] = f"start_time > {median}"
    combo.addItem("long")

    yield triad

    triad.close()


def scatter_parameters() -> Dict[str, Any]:
    """
    Build the parameters the controls panel sends for a scatterplot.

    :return: the parameters dict
    :rtype: Dict[str, Any]
    """
    return {
        "db_loader": LOADER,
        "plot_type": "Scatterplot",
        "x_axis": "start_time",
        "y_axis": "num_sublevels",
        "z_axis": "duration",
        "x_log": False,
        "y_log": False,
        "z_log": False,
        "bins": [20],
        "sizes": False,
    }


def plot(triad: Triad, filter_name: str) -> None:
    """
    Select one filter on channel 0, as a user would, then press Plot.

    :param triad: the tab under test
    :type triad: Triad
    :param filter_name: the filter to select
    :type filter_name: str
    """
    view = triad.tab_view
    combo = view._subset_controls.filter_comboBox
    for name in list(combo.getSelectedItems()):
        combo.selectItem(name, select=False)
    combo.selectItem(filter_name, select=True)
    view.selected_experiment_and_channels_by_loader[LOADER] = {"exp_a": ["0"]}
    view.handle_parameter_change(
        "metadatacontrols", "update_plot", (scatter_parameters(),)
    )


def export_plot_data(triad: Triad, target: Path) -> List[List[str]]:
    """
    Press Export Plot Data, saving to ``target``, and read the file back.

    Read with the ``csv`` module rather than pandas, which renames repeated column
    headers and would hide the very thing under test.

    :param triad: the tab under test
    :type triad: Triad
    :param target: where the save dialog's answer points
    :type target: Path
    :return: the file's rows, header first
    :rtype: List[List[str]]
    """
    triad.tab_view.get_save_filename = lambda: str(target)
    triad.tab_view.handle_parameter_change(
        "metadatacontrols", "export_plot_data", ({},)
    )
    with open(target, newline="") as handle:
        return list(csv.reader(handle))


@pytest.mark.timeout(120)
def test_a_scatter_of_two_datasets_exports_both(
    metadata_tab: Triad, tmp_path: Path
) -> None:
    """Export keeps the first dataset's points as well as the second's."""
    plot(metadata_tab, "everything")
    plot(metadata_tab, "long")
    assert len(metadata_tab.tab_controller.model.overlay.datasets) == 2

    rows = export_plot_data(metadata_tab, tmp_path / "plot.csv")

    header, body = rows[0], rows[1:]
    assert len(header) == 4, f"expected one x and one y column per dataset: {header}"
    assert header[0] == header[2] and header[1] == header[3]
    first = [r[0] for r in body if r[0] != ""]
    second = [r[2] for r in body if r[2] != ""]
    assert first and second
    assert len(first) > len(second), "the filter that keeps fewer events lost its rows"
    assert set(second) <= set(first)


@pytest.mark.timeout(120)
def test_a_scatter_of_one_dataset_exports_two_columns(
    metadata_tab: Triad, tmp_path: Path
) -> None:
    """A single dataset is unchanged: one x column and one y column."""
    plot(metadata_tab, "everything")

    rows = export_plot_data(metadata_tab, tmp_path / "plot.csv")

    assert len(rows[0]) == 2
