"""
Metadata tab, headless: what Undo and a refused plot leave on the figure.

Every plot is recorded in the tab's action history, and both Undo and a refused plot
roll that history back by replaying it. Replay used to re-read the filter and channel
selection from the widgets, so an earlier plot came back drawn with whatever was
selected *now*; a refused plot - including "everything is already plotted", so a
double-click on Plot - replayed the whole history the same way; and Undo replayed
from the very first action even when a reset made everything before it irrelevant.

What is real here: the shell, the Metadata triad and a real ``SQLiteDBLoader`` over the
synthetic database. What is not: the widgets' own clicks, which the tests stand in for
by selecting filters on the real filter combobox and calling the same
``handle_parameter_change`` the controls panel calls.
"""

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad

LOADER = "loader"


@pytest.fixture
def metadata_tab(qapp, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """
    A metadata tab with a real loader and four named filters.

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
    for index in range(12):
        name = f"F{index}"
        view.subset_filters[name] = f"duration >= {index}"
        combo.addItem(name)
    view.subset_filters["Raw_raw"] = "SELECT * FROM events"
    combo.addItem("Raw_raw")

    yield triad

    triad.close()


def plot_parameters(bins: int = 20) -> Dict[str, Any]:
    """
    Build the parameters the controls panel sends for a histogram.

    :param bins: the bin count requested
    :type bins: int
    :return: the parameters dict
    :rtype: Dict[str, Any]
    """
    return {
        "db_loader": LOADER,
        "plot_type": "Histogram",
        "x_axis": "duration",
        "y_axis": "duration",
        "z_axis": "duration",
        "x_log": False,
        "y_log": False,
        "z_log": False,
        "bins": [bins],
        "sizes": False,
    }


def plot(triad: Triad, filter_name: str, channel: str = "0", bins: int = 20) -> None:
    """
    Select one filter and one channel, as a user would, then press Plot.

    :param triad: the tab under test
    :type triad: Triad
    :param filter_name: the filter to select
    :type filter_name: str
    :param channel: the channel to select, as the selection tree reports it
    :type channel: str
    :param bins: the bin count requested
    :type bins: int
    """
    view = triad.tab_view
    combo = view._subset_controls.filter_comboBox
    for name in list(combo.getSelectedItems()):
        combo.selectItem(name, select=False)
    combo.selectItem(filter_name, select=True)
    view.selected_experiment_and_channels_by_loader[LOADER] = {"exp_a": [channel]}
    view.handle_parameter_change(
        "metadatacontrols", "update_plot", (plot_parameters(bins),)
    )


def undo(triad: Triad) -> None:
    """
    Press Undo.

    :param triad: the tab under test
    :type triad: Triad
    """
    triad.tab_view.handle_parameter_change("metadatacontrols", "undo_plot", ({},))


def on_figure(triad: Triad) -> Set[Tuple[int, str]]:
    """
    Report what the figure holds, as (channel, filter) pairs.

    :param triad: the tab under test
    :type triad: Triad
    :return: the plotted datasets
    :rtype: Set[Tuple[int, str]]
    """
    return {(entry[2], entry[4]) for entry in triad.tab_view.plotted_datasets}


def count_queries(triad: Triad) -> List[Any]:
    """
    Record every subset query the View makes from now on.

    :param triad: the tab under test
    :type triad: Triad
    :return: a list that grows by one per query
    :rtype: List[Any]
    """
    queries: List[Any] = []
    triad.tab_view.metadata_subset_requested.connect(lambda *args: queries.append(args))
    return queries


@pytest.mark.timeout(120)
def test_plotting_what_is_already_shown_changes_nothing(metadata_tab: Triad) -> None:
    """
    A double-click on Plot is refused and leaves the figure and its history alone.

    The refusal used to undo the last step, replaying the rest with the current
    selection, so the figure lost F0.
    """
    plot(metadata_tab, "F0")
    plot(metadata_tab, "F1")
    history = len(metadata_tab.tab_controller.tab_action_history)

    plot(metadata_tab, "F1")

    assert on_figure(metadata_tab) == {(0, "F0"), (0, "F1")}
    assert len(metadata_tab.tab_controller.tab_action_history) == history


@pytest.mark.timeout(120)
def test_a_refused_plot_replays_nothing(metadata_tab: Triad) -> None:
    """Ten overlays then a refusal: no query at all, since nothing needs redrawing."""
    for index in range(10):
        plot(metadata_tab, f"F{index}")
    queries = count_queries(metadata_tab)

    plot(metadata_tab, "F9")

    assert queries == []
    assert len(on_figure(metadata_tab)) == 10


@pytest.mark.timeout(120)
def test_a_refusal_after_a_reset_keeps_the_figure_empty(metadata_tab: Triad) -> None:
    """
    A refusal after Reset does not bring back what was reset away.

    Pins the order the recorded selection depends on: rolling the refusal back must
    not pop the user's own Reset and replay what came before it.
    """
    plot(metadata_tab, "F0")
    metadata_tab.tab_view.handle_parameter_change(
        "metadatacontrols", "reset_plot", ({},)
    )

    plot(metadata_tab, "Raw_raw")

    assert on_figure(metadata_tab) == set()


@pytest.mark.timeout(120)
def test_undo_redraws_the_earlier_plot_with_its_own_filter(metadata_tab: Triad) -> None:
    """Plot F0, then F1, then Undo: F0 comes back, not F1 drawn in its place."""
    plot(metadata_tab, "F0")
    plot(metadata_tab, "F1")

    undo(metadata_tab)

    assert on_figure(metadata_tab) == {(0, "F0")}


@pytest.mark.timeout(120)
def test_undo_redraws_the_earlier_plot_on_its_own_channel(metadata_tab: Triad) -> None:
    """The channel selection is replayed as recorded too, not as currently selected."""
    plot(metadata_tab, "F0", channel="0")
    plot(metadata_tab, "F1", channel="1")

    undo(metadata_tab)

    assert on_figure(metadata_tab) == {(0, "F0")}


@pytest.mark.timeout(120)
def test_undo_replays_only_from_the_last_reset(metadata_tab: Triad) -> None:
    """
    Five overlays, a bin change that resets the figure, two overlays, Undo: two queries.

    Everything before the reset is off the figure, so replaying it re-queried the
    database on the GUI thread for nothing - twelve queries where two are needed.
    """
    for index in range(5):
        plot(metadata_tab, f"F{index}")
    plot(metadata_tab, "F5", bins=40)
    plot(metadata_tab, "F6", bins=40)
    queries = count_queries(metadata_tab)

    undo(metadata_tab)

    assert on_figure(metadata_tab) == {(0, "F5")}
    assert len(queries) <= 2
