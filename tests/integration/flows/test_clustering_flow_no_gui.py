"""
Clustering tab, end to end and headless: load, cluster, commit, check the database.

The metadata tab's flow ends in a CSV; this one ends in a *database write*, which
is the clustering tab's equivalent durable artifact. Committing labels back against
the wrong rows is the failure that matters here, and it is invisible in any
assertion about widget state - the plot would look identical.

Everything the flow drives is an action name on ``handle_parameter_change``, the
entry point the controls widget uses. It names no internal method, so Steps 3-5 can
move the computation to the Model without touching it.

The clustering settings dialog is stubbed the same way the metadata flow stubs the
folder picker: it returns the configuration a user would have chosen, so the paths
either side of it are real. HDBSCAN is used rather than Gaussian Mixtures because
it is deterministic - ``ClusteringView`` seeds the GMM, but HDBSCAN needs no seed
at all, so the flow cannot become flaky for reasons unrelated to the refactor.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pytest
from PySide6.QtWidgets import QDialog

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad

LOADER_KEY = "loader"

#: Two columns every synthetic metadata database carries, so the clustering has
#: something real to work on without the flow depending on a fitter's output shape.
COLUMNS = ("duration", "max_deviation")


class _StubSettingsDialog:
    """
    Stand-in for the clustering settings dialog.

    Reports the configuration a user would have chosen and accepts, so the
    clustering and commit either side of it run for real.
    """

    config: Dict[str, Any] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Accept whatever the View passes without inspecting it.

        :param args: positional arguments from the caller
        :type args: Any
        :param kwargs: keyword arguments from the caller
        :type kwargs: Any
        """

    def exec(self) -> int:
        """
        Accept immediately rather than blocking on the user.

        :return: the accepted result code
        :rtype: int
        """
        return QDialog.Accepted

    def get_result(self) -> Dict[str, Any]:
        """
        Report the chosen clustering configuration.

        :return: the config the View will act on
        :rtype: Dict[str, Any]
        """
        return type(self).config


def clustering_config(columns: tuple = COLUMNS) -> Dict[str, Any]:
    """
    Build a HDBSCAN configuration over the given columns.

    :param columns: the metadata columns to cluster on
    :type columns: tuple
    :return: a config of the shape the dialog returns
    :rtype: Dict[str, Any]
    """
    return {
        "columns": [
            {"column": name, "unit": None, "log": False, "norm": True, "plot": True}
            for name in columns
        ],
        "filter": None,
        "method": "HDBSCAN",
        "method_params": {
            "HDBSCAN_Cluster_Size_input": 5,
            "HDBSCAN_Min_Points_input": 1,
            "HDBSCAN_Sensitivity_input": 1.0,
        },
    }


@pytest.fixture(autouse=True)
def stub_the_settings_dialog(mocker) -> None:
    """
    Replace the clustering settings dialog for every test in this module.

    :param mocker: pytest-mock's fixture
    :type mocker: Any
    :return: None
    :rtype: None
    """
    mocker.patch(
        "poriscope.plugins.analysistabs.ClusteringView.ClusteringSettingsDialog",
        _StubSettingsDialog,
    )


@pytest.fixture
def clustering_tab(qapp, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """
    A clustering tab with a real loader over the synthetic database.

    :param qapp: pytest-qt's application fixture; MainView is a real widget
    :type qapp: Any
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param sample_metadata_db: path to a generated metadata database
    :type sample_metadata_db: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_triad("ClusteringController", tmp_path)

    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = sample_metadata_db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER_KEY)
    triad.db_path = sample_metadata_db  # type: ignore[attr-defined]

    yield triad

    triad.close()


def columns_of(db_path: str, table: str) -> List[str]:
    """
    List a table's column names straight out of the database file.

    Read with sqlite3 rather than through the loader, so the assertion does not
    depend on the code path that wrote them.

    :param db_path: the database file
    :type db_path: str
    :param table: the table to inspect
    :type table: str
    :return: the column names
    :rtype: List[str]
    """
    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        try:
            return [row[1] for row in cursor.execute(f"PRAGMA table_info({table})")]
        finally:
            cursor.close()
    finally:
        connection.close()


def cluster(triad: Triad, config: Dict[str, Any]) -> None:
    """
    Drive the tab through opening its settings and clustering.

    :param triad: the tab under test
    :type triad: Triad
    :param config: the configuration the stubbed dialog will report
    :type config: Dict[str, Any]
    :return: None
    :rtype: None
    """
    _StubSettingsDialog.config = config
    triad.tab_view.handle_parameter_change(
        "clusteringcontrols", "open_cluster_settings", ({"db_loader": LOADER_KEY},)
    )


@pytest.mark.timeout(90)
def test_the_tab_sees_the_registered_loader(clustering_tab: Triad) -> None:
    """Registration reaches the tab, not just the plugin registry."""
    assert LOADER_KEY in clustering_tab.available("MetaDatabaseLoader")


@pytest.mark.timeout(90)
def test_clustering_labels_every_row_it_loaded(clustering_tab: Triad) -> None:
    """
    The clustering runs for real and produces one label per event.

    40 events across the two channels, so a label array of any other length means
    rows were dropped or duplicated between the query and the clustering - which
    would then be committed against mismatched ids.
    """
    cluster(clustering_tab, clustering_config())

    data = clustering_tab.tab_view.cluster_data
    assert data is not None
    assert len(data) == 40
    assert "cluster_label" in data.columns
    assert "cluster_confidence" in data.columns


@pytest.mark.timeout(90)
def test_committing_writes_the_columns_into_the_database(
    clustering_tab: Triad,
) -> None:
    """
    The durable artifact: two new columns, readable with plain sqlite3.

    Asserting against the file rather than the loader means the test does not
    depend on the same code path that performed the write.
    """
    cluster(clustering_tab, clustering_config())
    table = clustering_tab.tab_view.table_name

    clustering_tab.tab_view.handle_parameter_change(
        "clusteringcontrols", "commit_clusters", ({"db_loader": LOADER_KEY},)
    )

    written = columns_of(clustering_tab.db_path, table)
    assert "cluster_label" in written
    assert "cluster_confidence" in written


@pytest.mark.timeout(90)
def test_the_committed_labels_match_the_rows_they_were_computed_for(
    clustering_tab: Triad,
) -> None:
    """
    The failure this flow exists to catch: labels written against the wrong ids.

    A plot would look identical either way, so nothing about widget state can see
    it. Every committed row is compared back to the label the clustering assigned
    to that same event id.
    """
    cluster(clustering_tab, clustering_config())
    table = clustering_tab.tab_view.table_name
    expected = dict(
        zip(
            clustering_tab.tab_view.cluster_data["id"],
            clustering_tab.tab_view.cluster_data["cluster_label"],
            strict=True,
        )
    )

    clustering_tab.tab_view.handle_parameter_change(
        "clusteringcontrols", "commit_clusters", ({"db_loader": LOADER_KEY},)
    )

    connection = sqlite3.connect(clustering_tab.db_path)
    try:
        cursor = connection.cursor()
        try:
            rows = cursor.execute(
                f"SELECT id, cluster_label FROM {table} WHERE cluster_label IS NOT NULL"
            ).fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

    assert rows, "nothing was committed"
    for row_id, label in rows:
        assert expected[row_id] == label
