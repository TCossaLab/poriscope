"""
Metadata tab, headless: Plot Events and its arrows as recorded actions, and what Undo leaves.

Plot Events draws a grid of events in place of whatever the figure held. It is recorded on
the Controller with the events it drew, already resolved from the Event ID through the
filtered-event cache, so a replay draws those events whatever the panel holds then. Its clear
of the figure is not recorded, so Undo after it replays from the last reset and the overlay
comes back; on a figure whose history holds no reset it records one first, so Undo clears the
grid instead of leaving it drawn.

What is real here: the shell, the Metadata triad and a real ``SQLiteDBLoader`` over the
synthetic database. The clicks are stood in for by selecting filters on the real filter
combobox and calling the same ``handle_parameter_change`` the controls panel calls.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.utils.MetaSubsetTabModel import FigureKind
from tests.integration.flows._triad import Triad, build_triad

LOADER = "loader"


@pytest.fixture
def metadata_tab(qapp, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """
    A metadata tab with a real loader and three named filters.

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
    for name, text in (
        ("F0", "duration >= 0"),
        ("F1", "duration >= 1"),
        ("Nothing", "duration >= 999999"),
    ):
        view.subset_filters[name] = text
        combo.addItem(name)

    yield triad

    triad.close()


def select(triad: Triad, filters: List[str], channels: List[str]) -> None:
    """
    Select filters and channels of the one experiment, as a user would.

    :param triad: the tab under test
    :type triad: Triad
    :param filters: the filters to select
    :type filters: List[str]
    :param channels: the channels to select, as the selection tree reports them
    :type channels: List[str]
    """
    view = triad.tab_view
    combo = view._subset_controls.filter_comboBox
    for name in list(combo.getSelectedItems()):
        combo.selectItem(name, select=False)
    for name in filters:
        combo.selectItem(name, select=True)
    view.selected_experiment_and_channels_by_loader[LOADER] = {"exp_a": channels}


def press(
    triad: Triad, action: str, parameters: Optional[Dict[str, Any]] = None
) -> None:
    """
    Press a control on the Metadata panel, with the parameters it sends.

    :param triad: the tab under test
    :type triad: Triad
    :param action: the action the control sends
    :type action: str
    :param parameters: what the panel sends with it
    :type parameters: Optional[Dict[str, Any]]
    """
    triad.tab_view.handle_parameter_change(
        "metadatacontrols", action, (dict(parameters or {}),)
    )


def plot_events(triad: Triad, event_id: int = 0, n_events: int = 4) -> None:
    """
    Press Plot Events with an Event ID and an event count.

    :param triad: the tab under test
    :type triad: Triad
    :param event_id: the Event ID typed
    :type event_id: int
    :param n_events: how many events to plot
    :type n_events: int
    """
    press(
        triad,
        "plot_events",
        {"db_loader": LOADER, "event_id": event_id, "n_events": n_events, "raw": False},
    )


def histogram(triad: Triad) -> None:
    """
    Press Update Plot for a duration histogram of what is selected.

    :param triad: the tab under test
    :type triad: Triad
    """
    press(
        triad,
        "update_plot",
        {
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
        },
    )


def history(triad: Triad) -> List[Dict[str, Any]]:
    """
    The tab's recorded history, oldest first.

    :param triad: the tab under test
    :type triad: Triad
    :return: the recorded entries
    :rtype: List[Dict[str, Any]]
    """
    return list(triad.tab_controller.tab_action_history.values())


def actions(triad: Triad) -> List[str]:
    """
    The names of the tab's recorded actions, oldest first.

    :param triad: the tab under test
    :type triad: Triad
    :return: the action names
    :rtype: List[str]
    """
    return [entry["action"] for entry in history(triad)]


def grid_titles(triad: Triad) -> List[str]:
    """
    The titles of the event grid's subplots, one per event drawn.

    :param triad: the tab under test
    :type triad: Triad
    :return: the subplot titles
    :rtype: List[str]
    """
    return [ax.get_title() for ax in triad.tab_view.figure.axes]


def drawn_event_ids(triad: Triad) -> List[int]:
    """
    The event ids the grid shows, read off its subplot titles.

    :param triad: the tab under test
    :type triad: Triad
    :return: the event ids, in grid order
    :rtype: List[int]
    """
    return [int(title.rsplit(" ", 1)[1]) for title in grid_titles(triad)]


def figure_is_empty(triad: Triad) -> bool:
    """
    Does the figure hold one empty axes, as a cleared figure does?

    :param triad: the tab under test
    :type triad: Triad
    :return: True if nothing is drawn
    :rtype: bool
    """
    axes = triad.tab_view.figure.axes
    return (
        len(axes) == 1
        and not axes[0].lines
        and not axes[0].patches
        and not axes[0].collections
    )


def test_plot_events_is_recorded_with_the_events_it_drew(metadata_tab: Triad) -> None:
    """The entry carries the resolved ids and the selection, not the Event ID typed."""
    select(metadata_tab, ["F0"], ["0"])

    plot_events(metadata_tab, event_id=0, n_events=4)

    entry = history(metadata_tab)[-1]
    assert entry["action"] == "plot_events"
    kwargs = entry["kwargs"]
    assert kwargs["loader"] == LOADER
    assert kwargs["event_ids"] == drawn_event_ids(metadata_tab)
    assert len(kwargs["event_ids"]) == 4
    assert kwargs["experiment"] == "exp_a"
    assert kwargs["channel"] == "0"
    assert kwargs["subset_name"] == "F0"
    assert kwargs["sql_filter"] == "duration >= 0"
    assert kwargs["raw"] is False
    assert metadata_tab.tab_controller.model.overlay.figure is FigureKind.EVENT_GRID


def test_plot_events_first_on_a_figure_records_a_reset_before_it(
    metadata_tab: Triad,
) -> None:
    select(metadata_tab, ["F0"], ["0"])

    plot_events(metadata_tab)

    assert actions(metadata_tab) == ["reset", "plot_events"]


def test_undo_of_plot_events_first_on_a_figure_clears_the_grid(
    metadata_tab: Triad,
) -> None:
    select(metadata_tab, ["F0"], ["0"])
    plot_events(metadata_tab)

    press(metadata_tab, "undo_plot")

    assert figure_is_empty(metadata_tab)
    assert metadata_tab.tab_controller.model.overlay.figure is FigureKind.EMPTY_2D


def test_plot_events_after_an_overlay_records_no_reset_and_undo_brings_it_back(
    metadata_tab: Triad,
) -> None:
    select(metadata_tab, ["F0"], ["0"])
    histogram(metadata_tab)
    plot_events(metadata_tab)

    assert actions(metadata_tab) == ["reset", "overlay_plot", "plot_events"]

    press(metadata_tab, "undo_plot")

    assert actions(metadata_tab) == ["reset", "overlay_plot"]
    datasets = metadata_tab.tab_controller.model.overlay.datasets
    assert {(key[2], key[4]) for key in datasets} == {(0, "F0")}
    assert len(metadata_tab.tab_view.figure.axes) == 1


def test_an_overlay_after_plot_events_starts_a_figure_and_undo_returns_to_the_events(
    metadata_tab: Triad,
) -> None:
    select(metadata_tab, ["F0"], ["0"])
    plot_events(metadata_tab)
    drawn = drawn_event_ids(metadata_tab)
    histogram(metadata_tab)

    assert actions(metadata_tab) == ["reset", "plot_events", "reset", "overlay_plot"]

    press(metadata_tab, "undo_plot")

    assert drawn_event_ids(metadata_tab) == drawn
    assert metadata_tab.tab_controller.model.overlay.figure is FigureKind.EVENT_GRID


def test_the_arrow_records_the_shifted_events_and_undo_steps_back_one_block(
    metadata_tab: Triad,
) -> None:
    select(metadata_tab, ["F0"], ["0"])
    plot_events(metadata_tab, event_id=0, n_events=2)
    first = drawn_event_ids(metadata_tab)
    typed = int(metadata_tab.tab_view.metadatacontrols.event_id_lineEdit.text())

    press(
        metadata_tab,
        "shift_range_forward",
        {"db_loader": LOADER, "event_id": typed, "n_events": 2, "raw": False},
    )

    second = drawn_event_ids(metadata_tab)
    assert second != first
    assert actions(metadata_tab) == ["reset", "plot_events", "plot_events"]
    assert history(metadata_tab)[-1]["kwargs"]["event_ids"] == second

    press(metadata_tab, "undo_plot")

    assert drawn_event_ids(metadata_tab) == first


@pytest.mark.parametrize(
    ("filters", "channels"),
    [
        (["F0", "F1"], ["0"]),  # two filters
        (["F0"], ["0", "1"]),  # two channels
        (["Nothing"], ["0"]),  # a filter that keeps no event
    ],
    ids=["two filters", "two channels", "no filtered events"],
)
def test_a_refused_plot_events_records_nothing(
    metadata_tab: Triad, filters: List[str], channels: List[str]
) -> None:
    select(metadata_tab, filters, channels)

    plot_events(metadata_tab)

    assert actions(metadata_tab) == []
    assert figure_is_empty(metadata_tab)


def test_plot_events_that_loads_no_event_records_nothing(metadata_tab: Triad) -> None:
    """Refused by the fetch, as a saved entry naming events no longer there is: no stray reset either."""
    drawn = metadata_tab.tab_controller.plot_events(
        loader=LOADER,
        event_ids=[999999],
        experiment="exp_a",
        channel="0",
        subset_name="F0",
        sql_filter="duration >= 0",
        raw=False,
    )

    assert drawn is False
    assert actions(metadata_tab) == []
    assert figure_is_empty(metadata_tab)


def test_a_replayed_plot_events_records_once(metadata_tab: Triad) -> None:
    """Replaying the reset and the plot records the reset and the plot, nothing more."""
    select(metadata_tab, ["F0"], ["0"])
    plot_events(metadata_tab)
    recorded = history(metadata_tab)
    drawn = drawn_event_ids(metadata_tab)
    press(metadata_tab, "reset_plot")
    metadata_tab.tab_controller.tab_action_history.clear()

    metadata_tab.tab_controller.replay(recorded)

    assert actions(metadata_tab) == ["reset", "plot_events"]
    assert drawn_event_ids(metadata_tab) == drawn


def panel_lines(triad: Triad) -> List[str]:
    """Every line that reaches the status panel from now on."""
    lines: List[str] = []
    triad.tab_controller.add_text_to_display.connect(
        lambda text, _source: lines.append(text)
    )
    return lines


def test_a_refusal_clicked_again_is_not_repeated_on_the_panel(
    metadata_tab: Triad,
) -> None:
    """The View's refusal is the line directly above the second click's, so it is left out."""
    lines = panel_lines(metadata_tab)
    select(metadata_tab, ["F0"], ["0", "1"])

    for _ in range(3):
        plot_events(metadata_tab)

    assert lines == ["Only a single channel can be used for plotting events"]


def test_a_refusal_is_shown_again_once_another_line_is_between(
    metadata_tab: Triad,
) -> None:
    lines = panel_lines(metadata_tab)
    select(metadata_tab, ["F0"], ["0", "1"])
    plot_events(metadata_tab)
    metadata_tab.tab_controller.add_text_to_display.emit("another line", "test")

    plot_events(metadata_tab)

    assert lines == [
        "Only a single channel can be used for plotting events",
        "another line",
        "Only a single channel can be used for plotting events",
    ]
