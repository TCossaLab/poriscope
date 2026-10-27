"""
Clustering write-back: a recorded entry's values are shown in a fresh tab.

``write_back`` writes what an entry used, so a restored tab shows what produced its result: for a run,
the loader and the settings the next dialog opens with; for a merge, the two labels. It never reads a
widget (it runs while a replay is under the tripwire), and it never emits an action: a handler reacting
to a value that was just written would undo it. These tests build a real tab with a loader registered.
"""

from pathlib import Path
from typing import Any, List

import pytest

from poriscope.utils.MetaView import MetaView
from poriscope.utils.ReplayGuard import replaying
from tests.integration.flows._triad import Triad, build_clustering_tab, hdbscan_config

LOADER = "loader"


@pytest.fixture
def tab(qapp: Any, tmp_path: Path, sample_metadata_db: str) -> Triad:
    triad = build_clustering_tab(tmp_path, sample_metadata_db, LOADER)
    yield triad
    triad.close()


@pytest.fixture
def actions(tab: Triad, mocker: Any) -> Any:
    """Replace the View's dispatch with a spy: a write-back must not trigger an action."""
    return mocker.patch.object(tab.tab_view, "handle_parameter_change")


def test_a_run_entry_shows_its_loader_and_stores_its_settings_for_the_next_dialog(
    tab: Triad, actions: Any
) -> None:
    view = tab.tab_view
    view.clusteringcontrols.db_loader_comboBox.addItem("another database")
    view.clusteringcontrols.set_db_loader("another database")
    config = hdbscan_config()

    view.write_back("cluster_run", (config, LOADER), {})
    config["method"] = "changed after recording"

    assert view.clusteringcontrols.db_loader_comboBox.currentText() == LOADER
    assert view.clustering_config_map[LOADER]["method"] == "HDBSCAN"
    actions.assert_not_called()


def test_writing_back_a_loader_asks_for_its_columns(tab: Triad, actions: Any) -> None:
    """The held-off combobox signal would have asked; the settings dialog lists them."""
    asked: List[str] = []
    tab.tab_view.column_names_requested.connect(asked.append)

    tab.tab_view.write_back("cluster_run", (hdbscan_config(), LOADER), {})

    assert asked == [LOADER]


def test_a_merge_entry_shows_its_two_labels(tab: Triad, actions: Any) -> None:
    controls = tab.tab_view.clusteringcontrols
    controls.update_clusters([-1, 0, 1])

    tab.tab_view.write_back("merge_clusters", (1, -1), {})

    assert controls.label_x_comboBox.currentText() == "1"
    assert controls.label_y_comboBox.currentText() == "-1"
    actions.assert_not_called()


def test_values_that_are_not_options_are_skipped_and_said(
    tab: Triad, actions: Any
) -> None:
    said: List[str] = []
    tab.tab_view.add_text_to_display.connect(
        lambda message, source: said.append(message)
    )
    tab.tab_view.clusteringcontrols.update_clusters([0, 1])

    tab.tab_view.write_back(
        "cluster_run", (hdbscan_config(), "a loader that is gone"), {}
    )
    tab.tab_view.write_back("merge_clusters", (7, 0), {})

    assert any("a loader that is gone" in message for message in said)
    assert any("7" in message for message in said)


def test_write_back_reads_no_widget(tab: Triad, actions: Any) -> None:
    """It runs under the replay tripwire: a read of a controls helper would raise."""
    tab.tab_view.clusteringcontrols.update_clusters([0, 1])

    with replaying():
        tab.tab_view.write_back("cluster_run", (hdbscan_config(), LOADER), {})
        tab.tab_view.write_back("merge_clusters", (0, 1), {})


def test_an_action_with_nothing_to_show_is_ignored(tab: Triad, actions: Any) -> None:
    tab.tab_view.write_back("an_action_from_another_tab", ("x",), {})

    actions.assert_not_called()


def test_the_not_shown_message_is_shared_by_every_tab() -> None:
    """One copy on ``MetaView``, so each tab's write-back says the same thing."""
    assert "_say_not_shown" in MetaView.__dict__
