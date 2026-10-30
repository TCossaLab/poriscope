"""
A raw SQL filter on the Protein tab, and under Undo and a saved plot configuration.

The Protein tab reads a subset three ways - the event-id list behind Plot Events and the
arrows, the traces themselves, and the ensemble average behind its histogram - and each
takes the filter name so a raw filter can scope itself per channel. On the Metadata tab,
Undo and Load Plot Configuration replay recorded plots, so a raw plot has to come back as
it was drawn, with its own channel bound. Real shell, tab and loader over a synthetic
database whose channels hold different numbers of events, so a filter that leaks across
channels shows as a count.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, Set, Tuple

import pytest
from PySide6.QtWidgets import QMessageBox

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad
from tests.synthetic_data.synthetic_metadata_db import generate_metadata_database

LOADER = "loader"
SCOPE = "experiment_id = :experiment_id AND channel_id = :channel_id"
CHANNEL_0 = 5
CHANNEL_1 = 8


@pytest.fixture
def database(tmp_path: Path) -> str:
    """
    A database with 5 events on channel 0 and 8 on channel 1.

    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :return: path to the written database
    :rtype: str
    """
    written = generate_metadata_database(
        tmp_path / "raw_scope.sqlite3",
        experiments=[
            {
                "name": "exp_a",
                "channels": [
                    {"channel_id": 0, "num_events": CHANNEL_0, "seed": 1},
                    {"channel_id": 1, "num_events": CHANNEL_1, "seed": 2},
                ],
            }
        ],
    )
    return str(written.db_path)


def build_tab(controller: str, tmp_path: Path, database: str, controls: str) -> Triad:
    """
    A tab of the given kind with a real loader, two raw filters and one assisted one.

    :param controller: the tab's controller class name
    :type controller: str
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param database: the metadata database to read
    :type database: str
    :param controls: the name of the tab's controls panel
    :type controls: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_triad(controller, tmp_path)
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = database
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER)
    triad.tab_view.handle_parameter_change(
        controls, "loader_changed", ({"db_loader": LOADER},)
    )
    filters = {
        "own_raw": f"SELECT event_id, duration FROM events WHERE {SCOPE}",
        "later_raw": f"SELECT event_id, duration FROM events WHERE event_id >= 2 AND {SCOPE}",
        "everything": "duration > 0",
    }
    combo = triad.tab_view._subset_controls.filter_comboBox
    for name, query in filters.items():
        triad.tab_view.subset_filters[name] = query
        combo.addItem(name)
    return triad


def select(triad: Triad, filter_name: str, channel: str) -> None:
    """
    Select one filter and one channel, as the panel and the selection tree would.

    :param triad: the tab under test
    :type triad: Triad
    :param filter_name: the filter to select
    :type filter_name: str
    :param channel: the channel, as the selection tree reports it
    :type channel: str
    """
    combo = triad.tab_view._subset_controls.filter_comboBox
    for name in list(combo.getSelectedItems()):
        combo.selectItem(name, select=False)
    combo.selectItem(filter_name, select=True)
    triad.tab_view.selected_experiment_and_channels_by_loader[LOADER] = {
        "exp_a": [channel]
    }


@pytest.fixture
def protein_tab(qapp: Any, tmp_path: Path, database: str) -> Triad:
    """
    A protein tab over the database.

    :param qapp: pytest-qt's application fixture
    :type qapp: Any
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param database: the metadata database
    :type database: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_tab("ProteinController", tmp_path, database, "proteincontrols")
    yield triad
    triad.close()


def plot_events(triad: Triad, event_id: int = 0, n_events: int = 1) -> None:
    """
    Press Plot Events.

    :param triad: the tab under test
    :type triad: Triad
    :param event_id: the first event to plot
    :type event_id: int
    :param n_events: how many events to plot
    :type n_events: int
    """
    triad.tab_view.handle_parameter_change(
        "proteincontrols",
        "plot_events",
        ({"db_loader": LOADER, "event_id": event_id, "n_events": n_events},),
    )


@pytest.mark.timeout(120)
@pytest.mark.parametrize(("channel", "expected"), [("0", CHANNEL_0), ("1", CHANNEL_1)])
def test_the_protein_event_list_is_the_selected_channels_own_events(
    protein_tab: Triad, channel: str, expected: int
) -> None:
    """
    The ids behind Plot Events and the arrows come from the query bound to the channel.
    """
    select(protein_tab, "own_raw", channel)

    plot_events(protein_tab)

    assert len(protein_tab.tab_view.filtered_event_ids) == expected


@pytest.mark.timeout(120)
def test_the_protein_event_list_follows_a_raw_filters_own_condition(
    protein_tab: Triad,
) -> None:
    """
    A condition beside the scope narrows the list within the channel, not across it.
    """
    select(protein_tab, "later_raw", "1")

    plot_events(protein_tab)

    assert len(protein_tab.tab_view.filtered_event_ids) == CHANNEL_1 - 2


@pytest.mark.timeout(120)
def test_changing_channel_rebuilds_the_protein_event_list(protein_tab: Triad) -> None:
    """
    The cache is keyed by the channel too, so a raw filter's other channel is not stale.
    """
    select(protein_tab, "own_raw", "0")
    plot_events(protein_tab)
    select(protein_tab, "own_raw", "1")

    plot_events(protein_tab)

    assert len(protein_tab.tab_view.filtered_event_ids) == CHANNEL_1


@pytest.mark.timeout(120)
def test_protein_plot_events_draws_the_events_a_raw_filter_names(
    protein_tab: Triad, mocker: Any
) -> None:
    """
    The traces fetched are the selected channel's, found by the query's event key: three
    events come back for the three asked for, and the figure was handed them to draw.
    """
    drawn = mocker.spy(protein_tab.tab_view, "show_events")
    select(protein_tab, "own_raw", "1")

    plot_events(protein_tab, event_id=0, n_events=3)

    assert drawn.call_count == 1
    assert len(drawn.call_args[0][0]) == 3


@pytest.fixture
def metadata_tab(qapp: Any, tmp_path: Path, database: str) -> Triad:
    """
    A metadata tab over the database.

    :param qapp: pytest-qt's application fixture
    :type qapp: Any
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param database: the metadata database
    :type database: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_tab("MetadataController", tmp_path, database, "metadatacontrols")
    yield triad
    triad.close()


def plot(triad: Triad, filter_name: str, channel: str) -> None:
    """
    Select one filter and one channel, then press Plot on a duration histogram.

    :param triad: the tab under test
    :type triad: Triad
    :param filter_name: the filter to select
    :type filter_name: str
    :param channel: the channel, as the selection tree reports it
    :type channel: str
    """
    select(triad, filter_name, channel)
    parameters: Dict[str, Any] = {
        "db_loader": LOADER,
        "plot_type": "Histogram",
        "x_axis": "duration",
        "y_axis": "duration",
        "z_axis": "duration",
        "x_log": False,
        "y_log": False,
        "z_log": False,
        "bins": [20],
        "sizes": False,
    }
    triad.tab_view.handle_parameter_change(
        "metadatacontrols", "update_plot", (parameters,)
    )


def on_figure(triad: Triad) -> Set[Tuple[int, str]]:
    """
    Report what the figure holds, as (channel, filter) pairs.

    :param triad: the tab under test
    :type triad: Triad
    :return: the plotted datasets
    :rtype: Set[Tuple[int, str]]
    """
    return {
        (entry[2], entry[4]) for entry in triad.tab_controller.model.overlay.datasets
    }


def undo(triad: Triad) -> None:
    """
    Press Undo.

    :param triad: the tab under test
    :type triad: Triad
    """
    triad.tab_view.handle_parameter_change("metadatacontrols", "undo_plot", ({},))


def plotted_row_count(triad: Triad) -> int:
    """
    Count the values drawn on the figure, summed over its histogram bars.

    :param triad: the tab under test
    :type triad: Triad
    :return: how many values were drawn
    :rtype: int
    """
    return sum(
        int(patch.get_height())
        for ax in triad.tab_view.figure.get_axes()
        for patch in ax.patches
    )


@pytest.mark.timeout(120)
def test_undo_redraws_a_raw_plot_on_the_channel_it_was_drawn_on(
    metadata_tab: Triad,
) -> None:
    """
    The replay binds the recorded channel, not the one selected when Undo is pressed.
    """
    plot(metadata_tab, "own_raw", "0")
    plot(metadata_tab, "everything", "1")

    undo(metadata_tab)

    assert on_figure(metadata_tab) == {(0, "own_raw")}
    assert plotted_row_count(metadata_tab) == CHANNEL_0


@pytest.mark.timeout(120)
def test_undo_after_two_raw_plots_keeps_the_first_with_its_own_rows(
    metadata_tab: Triad,
) -> None:
    """
    Two raw plots on different channels: Undo leaves the first, still only its channel.
    """
    plot(metadata_tab, "own_raw", "0")
    plot(metadata_tab, "later_raw", "1")
    assert on_figure(metadata_tab) == {(0, "own_raw"), (1, "later_raw")}

    undo(metadata_tab)

    assert on_figure(metadata_tab) == {(0, "own_raw")}
    assert plotted_row_count(metadata_tab) == CHANNEL_0


@pytest.mark.timeout(120)
def test_the_database_is_unchanged_by_raw_plots_and_undo(
    metadata_tab: Triad, database: str
) -> None:
    """
    Replaying reads only: the event count is what it was.
    """
    plot(metadata_tab, "own_raw", "0")
    plot(metadata_tab, "own_raw", "1")
    undo(metadata_tab)

    with sqlite3.connect(database) as conn:
        total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert total == CHANNEL_0 + CHANNEL_1


def plot_ensemble(triad: Triad, filter_name: str, channel: str) -> None:
    """
    Switch to Ensemble mode, select one filter and channel, and press Plot.

    :param triad: the tab under test
    :type triad: Triad
    :param filter_name: the filter to select
    :type filter_name: str
    :param channel: the channel, as the selection tree reports it
    :type channel: str
    """
    triad.tab_view.handle_parameter_change(
        "proteincontrols", "set_mode_ensemble", ({},)
    )
    select(triad, filter_name, channel)
    parameters: Dict[str, Any] = {
        "db_loader": LOADER,
        "plot_type": "Filtered Histogram",
        "pore_diameter": 10.0,
        "pore_length": 10.0,
        "n_values": 20,
        "bins": [20],
        "sizes": False,
    }
    triad.tab_view.handle_parameter_change(
        "proteincontrols", "update_plot", (parameters,)
    )


@pytest.mark.timeout(120)
@pytest.mark.parametrize("channel", [0, 1])
def test_the_protein_ensemble_histogram_averages_the_selected_channels_events(
    protein_tab: Triad, channel: int
) -> None:
    """
    The averaged subset is the one the query names for the channel, drawn once.
    """
    plot_ensemble(protein_tab, "own_raw", str(channel))

    view = protein_tab.tab_view
    labels = [line.get_label() for line in view.ax_hist_ensemble.lines]
    assert [label for label in labels if label != "Fit"] == [
        f"{LOADER} | exp_a Ch {channel}: own_raw"
    ]
    assert f"channel_id = {channel}" in view.event_query


@pytest.mark.timeout(120)
def test_a_saved_plot_configuration_replays_raw_plots_on_their_own_channels(
    metadata_tab: Triad, tmp_path: Path, mocker: Any
) -> None:
    """
    Save two raw plots, reset, and load: both come back, each bound to its own channel.

    The file holds the filter's text with its placeholders, not a channel baked into it,
    and a replay does not need the filter to still be in the list.
    """
    saved = tmp_path / "config.json"
    mocker.patch(
        "poriscope.utils.MetaView.QFileDialog.getSaveFileName",
        return_value=(str(saved), ""),
    )
    mocker.patch(
        "poriscope.utils.MetaView.QFileDialog.getOpenFileName",
        return_value=(str(saved), ""),
    )
    view = metadata_tab.tab_view
    plot(metadata_tab, "own_raw", "0")
    plot(metadata_tab, "own_raw", "1")
    view.handle_parameter_change("metadatacontrols", "save_plot_config", ({},))
    assert ":experiment_id" in saved.read_text(encoding="utf-8")

    view.handle_parameter_change("metadatacontrols", "reset_plot", ({},))
    assert on_figure(metadata_tab) == set()
    view.subset_filters.pop("own_raw")
    view.handle_parameter_change("metadatacontrols", "load_plot", ({},))

    assert on_figure(metadata_tab) == {(0, "own_raw"), (1, "own_raw")}
    assert plotted_row_count(metadata_tab) == CHANNEL_0 + CHANNEL_1


# ------------------------------------------------- the event_id question and replay

#: A raw filter written for a column plot: it does not return event_id.
NO_EVENT_ID = f"SELECT duration FROM events WHERE {SCOPE}"


def event_overlay(triad: Triad, filter_name: str, channel: str) -> None:
    """
    Select one filter and one channel, and press Update Plot for a Raw Event Overlay.

    :param triad: the tab under test
    :type triad: Triad
    :param filter_name: the filter to select
    :type filter_name: str
    :param channel: the channel, as the selection tree reports it
    :type channel: str
    """
    select(triad, filter_name, channel)
    triad.tab_view.handle_parameter_change(
        "metadatacontrols",
        "update_plot",
        (
            {
                "db_loader": LOADER,
                "plot_type": "Raw Event Overlay",
                "x_axis": "duration",
                "y_axis": "duration",
                "z_axis": "duration",
                "x_log": False,
                "y_log": False,
                "z_log": False,
                "bins": [20],
                "sizes": False,
            },
        ),
    )


@pytest.fixture
def no_event_id(metadata_tab: Triad, mocker: Any) -> Any:
    """
    Give the tab a raw filter without event_id, and answer the question it raises.

    :return: the patched question, answering yes unless a test changes it
    :rtype: Any
    """
    view = metadata_tab.tab_view
    view.subset_filters["noid_raw"] = NO_EVENT_ID
    view._subset_controls.filter_comboBox.addItem("noid_raw")
    return mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )


def recorded_filters(triad: Triad) -> list:
    return [
        entry["kwargs"]["filters"]
        for entry in triad.tab_controller.tab_action_history.values()
        if entry["action"] == "overlay_plot"
    ]


@pytest.mark.timeout(120)
def test_the_event_id_question_is_asked_before_the_plot_is_recorded(
    metadata_tab: Triad, no_event_id: Any
) -> None:
    """The entry holds the text that ran, so a replay has nothing to ask."""
    event_overlay(metadata_tab, "noid_raw", "0")

    assert no_event_id.call_count == 1
    (filters,) = recorded_filters(metadata_tab)
    assert filters["noid_raw"].startswith("SELECT event_id")
    assert on_figure(metadata_tab) == {(0, "noid_raw")}


@pytest.mark.timeout(120)
def test_undo_redraws_such_a_plot_without_asking_again(
    metadata_tab: Triad, no_event_id: Any
) -> None:
    event_overlay(metadata_tab, "noid_raw", "0")
    event_overlay(metadata_tab, "noid_raw", "1")

    undo(metadata_tab)

    assert no_event_id.call_count == 1
    assert on_figure(metadata_tab) == {(0, "noid_raw")}


@pytest.mark.timeout(120)
def test_a_declined_question_records_nothing(
    metadata_tab: Triad, no_event_id: Any
) -> None:
    no_event_id.return_value = QMessageBox.No

    event_overlay(metadata_tab, "noid_raw", "0")

    assert no_event_id.call_count == 1
    assert recorded_filters(metadata_tab) == []
    assert metadata_tab.tab_view.subset_filters["noid_raw"] == NO_EVENT_ID


@pytest.mark.timeout(120)
def test_a_replay_never_asks_and_refuses_an_entry_without_event_id(
    metadata_tab: Triad, no_event_id: Any
) -> None:
    """An entry saved before the question moved to the click, or edited since."""
    entry = {
        "action": "overlay_plot",
        "args": (),
        "kwargs": {
            "loader": LOADER,
            "plot_type": "Raw Event Overlay",
            "axes": ["duration", "duration", "duration"],
            "logs": [False, False, False],
            "bins": [20],
            "sizes": False,
            "filters": {"noid_raw": NO_EVENT_ID},
            "scope": {"exp_a": ["0"]},
        },
    }

    metadata_tab.tab_controller.replay([entry])

    assert no_event_id.call_count == 0
    assert on_figure(metadata_tab) == set()
    assert metadata_tab.tab_view.subset_filters["noid_raw"] == NO_EVENT_ID


@pytest.mark.timeout(120)
@pytest.mark.parametrize(
    ("mode", "action"),
    [
        ("individual", "update_individual_distribution"),
        ("ensemble", "update_ensemble_distribution"),
    ],
)
def test_a_protein_plot_asks_about_event_id_before_it_is_recorded(
    protein_tab: Triad, mocker: Any, mode: str, action: str
) -> None:
    """As on the Metadata tab: the entry holds the text that ran."""
    view = protein_tab.tab_view
    view.subset_filters["noid_raw"] = NO_EVENT_ID
    view._subset_controls.filter_comboBox.addItem("noid_raw")
    asked = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QMessageBox.question",
        return_value=QMessageBox.Yes,
    )
    view.handle_parameter_change("proteincontrols", f"set_mode_{mode}", ({},))
    select(protein_tab, "noid_raw", "0")

    view.handle_parameter_change(
        "proteincontrols",
        "update_plot",
        (
            {
                "db_loader": LOADER,
                "pore_diameter": 10.0,
                "pore_length": 10.0,
                "n_values": 20,
                "bins": [20],
                "sizes": False,
            },
        ),
    )

    assert asked.call_count == 1
    entries = [
        entry
        for entry in protein_tab.tab_controller.tab_action_history.values()
        if entry["action"] == action
    ]
    assert entries[0]["kwargs"]["filters"]["noid_raw"].startswith("SELECT event_id")
