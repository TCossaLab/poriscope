"""
Clustering tab, end to end and headless: load, cluster, commit, check the database.

The metadata tab's flow ends in a CSV; this one ends in a *database write*, which
is the clustering tab's equivalent durable artifact. Committing labels back against
the wrong rows is the failure that matters here, and it is invisible in any
assertion about widget state - the plot would look identical.

Everything the flow drives is an action name on ``handle_parameter_change``, the
entry point the controls widget uses. It names no internal method, so computation
can move between the View and the Model without touching it.

The clustering settings dialog is stubbed the same way the metadata flow stubs the
folder picker: it returns the configuration a user would have chosen, so the paths
either side of it are real. HDBSCAN is used rather than Gaussian Mixtures because
it is deterministic - ``ClusteringView`` seeds the GMM, but HDBSCAN needs no seed
at all, so the flow cannot become flaky for reasons unrelated to what it tests.
"""

import copy
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
from PySide6.QtWidgets import QDialog

from tests.integration.flows._triad import (
    CLUSTERING_COLUMNS,
    Triad,
    build_clustering_tab,
    hdbscan_config,
)

LOADER_KEY = "loader"
#: Three plotted columns, so the result is drawn on 3-D axes.
THREE_COLUMNS = CLUSTERING_COLUMNS + ("baseline_current",)


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
    triad = build_clustering_tab(tmp_path, sample_metadata_db, LOADER_KEY)

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
def test_clustering_labels_every_row_it_loaded(clustering_tab: Triad) -> None:
    """
    The clustering runs for real and produces one label per event.

    40 events across the two channels, so a label array of any other length means
    rows were dropped or duplicated between the query and the clustering - which
    would then be committed against mismatched ids.
    """
    cluster(clustering_tab, hdbscan_config())

    data = clustering_tab.tab_controller.model.cluster_columns()
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
    cluster(clustering_tab, hdbscan_config())
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
    cluster(clustering_tab, hdbscan_config())
    table = clustering_tab.tab_view.table_name
    labelled = clustering_tab.tab_controller.model.cluster_columns()
    expected = dict(zip(labelled["id"], labelled["cluster_label"], strict=True))

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


def merge(triad: Triad, keep: str, merged: str) -> None:
    """
    Drive the tab through a merge, as the Merge button does.

    :param triad: the tab under test
    :type triad: Triad
    :param keep: the label kept
    :type keep: str
    :param merged: the label merged into it
    :type merged: str
    :return: None
    :rtype: None
    """
    triad.tab_view.handle_parameter_change(
        "clusteringcontrols",
        "merge_clusters",
        ({"db_loader": LOADER_KEY, "label_x": keep, "label_y": merged},),
    )


def recorded(triad: Triad) -> List[Tuple[str, Dict[str, Any]]]:
    """
    The tab's history as (action, values) pairs.

    :param triad: the tab under test
    :type triad: Triad
    :return: what the tab recorded, in order
    :rtype: List[Tuple[str, Dict[str, Any]]]
    """
    return [
        (entry["action"], entry["kwargs"])
        for entry in triad.tab_controller.tab_action_history.values()
    ]


@pytest.mark.timeout(90)
def test_each_run_records_one_reset_and_a_merge_records_none(
    clustering_tab: Triad,
) -> None:
    """A run starts a new figure; a merge redraws the same result, and a 3-D projection is part of drawing it."""
    cluster(clustering_tab, hdbscan_config())
    merge(clustering_tab, "0", "1")
    cluster(clustering_tab, hdbscan_config(THREE_COLUMNS))
    merge(clustering_tab, "0", "1")

    assert [action for action, _values in recorded(clustering_tab)] == [
        "reset",
        "cluster_run",
        "merge_clusters",
        "reset",
        "cluster_run",
        "merge_clusters",
    ]
    assert [ax.name for ax in clustering_tab.tab_view.figure.axes] == ["3d"]


@pytest.mark.timeout(90)
def test_a_run_that_matches_nothing_leaves_the_figure_and_records_nothing(
    clustering_tab: Triad,
) -> None:
    """The reset is recorded only once there is a result to draw."""
    cluster(clustering_tab, hdbscan_config())
    before = recorded(clustering_tab)
    drawn = [len(ax.collections) for ax in clustering_tab.tab_view.figure.axes]
    nothing = hdbscan_config()
    nothing["filter"] = "duration < -1"

    cluster(clustering_tab, nothing)

    assert recorded(clustering_tab) == before
    assert [len(ax.collections) for ax in clustering_tab.tab_view.figure.axes] == drawn


@pytest.mark.timeout(120)
def test_a_replay_records_the_history_it_replays(
    qapp, tmp_path: Path, sample_metadata_db: str
) -> None:
    """Each replayed run would otherwise record its reset a second time, after the replayed one."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    tab_a = build_clustering_tab(tmp_path / "a", sample_metadata_db, LOADER_KEY)
    tab_b = build_clustering_tab(tmp_path / "b", sample_metadata_db, LOADER_KEY)
    try:
        cluster(tab_a, hdbscan_config())
        merge(tab_a, "0", "1")
        cluster(tab_a, hdbscan_config(THREE_COLUMNS))
        history = copy.deepcopy(list(tab_a.tab_controller.tab_action_history.values()))

        tab_b.tab_controller.replay(history)

        assert recorded(tab_b) == recorded(tab_a)
        assert [ax.name for ax in tab_b.tab_view.figure.axes] == ["3d"]
    finally:
        tab_a.close()
        tab_b.close()


def said(triad: Triad) -> List[str]:
    """
    Collect what the tab's Controller says on the status panel from now on.

    :param triad: the tab under test
    :type triad: Triad
    :return: the list each message is appended to
    :rtype: List[str]
    """
    messages: List[str] = []
    triad.tab_controller.add_text_to_display.connect(
        lambda text, _source: messages.append(text)
    )
    return messages


@pytest.mark.timeout(90)
def test_a_merge_says_on_the_panel_how_many_events_it_moved(
    clustering_tab: Triad,
) -> None:
    cluster(clustering_tab, hdbscan_config())
    _frame, labels, _confidence = clustering_tab.tab_controller.model.result
    moved = int((labels == 1).sum())
    messages = said(clustering_tab)

    merge(clustering_tab, "0", "1")

    assert messages == [f"Merged cluster 1 into cluster 0 ({moved} events)"]


@pytest.mark.timeout(90)
def test_a_label_merged_into_itself_changes_nothing_and_says_so(
    clustering_tab: Triad,
) -> None:
    cluster(clustering_tab, hdbscan_config())
    before = recorded(clustering_tab)
    result = clustering_tab.tab_controller.model.result
    messages = said(clustering_tab)

    merge(clustering_tab, "0", "0")

    assert messages == ["Choose two different cluster labels to merge"]
    assert recorded(clustering_tab) == before
    assert clustering_tab.tab_controller.model.result is result
