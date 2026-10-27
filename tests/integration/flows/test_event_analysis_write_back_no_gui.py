"""
Event Analysis write-back: a recorded entry's values are shown in a fresh tab's panel.

``write_back`` writes the panel an entry used, so a restored tab shows what produced its result. It never
reads a widget (it runs while a replay is under the tripwire), and it never emits an action: a handler
reacting to a value that was just written would undo it. These tests build a real tab, which has the
loader and fitter registered and the Controller that answers the channel-list request, then write
entries into it.
"""

from pathlib import Path
from typing import Any, List

import pytest

from poriscope.utils.ReplayGuard import replaying
from tests.integration.flows._triad import Triad, build_event_analysis_tab

LOADER = "events"
FITTER = "fitter"
CHANNEL = 0


@pytest.fixture
def tab(qapp: Any, tmp_path: Path, sample_events_db: str) -> Triad:
    triad = build_event_analysis_tab(tmp_path, sample_events_db, LOADER, FITTER)
    yield triad
    triad.close()


@pytest.fixture
def actions(tab: Triad, mocker: Any) -> Any:
    """Replace the View's dispatch with a spy: a write-back must not trigger an action."""
    return mocker.patch.object(tab.tab_view, "handle_parameter_change")


def test_a_plot_events_entry_shows_everything_the_plot_used(
    tab: Triad, actions: Any
) -> None:
    controls = tab.tab_view.eventAnalysisControls
    controls.set_raw(False)

    tab.tab_view.write_back(
        "plot_events", (LOADER, FITTER, CHANNEL, [0, 1, 2], "", True), {}
    )

    assert controls.loaders_comboBox.currentText() == LOADER
    assert controls.eventfitters_comboBox.currentText() == FITTER
    assert controls.filters_comboBox.currentText() == "No Filter"
    assert controls.channel_comboBox.getSelectedItems() == [str(CHANNEL)]
    assert controls.raw_checkbox.isChecked() is True
    assert controls.event_index_lineEdit.text() == "0-2"
    actions.assert_not_called()


def test_a_fit_events_entry_shows_its_fitter_channel_and_filter(
    tab: Triad, actions: Any
) -> None:
    controls = tab.tab_view.eventAnalysisControls
    controls.eventfitters_comboBox.addItem("another fitter")
    controls.set_eventfitter("another fitter")
    controls.set_channels([])

    tab.tab_view.write_back("fit_events", (FITTER, CHANNEL, ""), {})

    assert controls.eventfitters_comboBox.currentText() == FITTER
    assert controls.channel_comboBox.getSelectedItems() == [str(CHANNEL)]
    assert controls.filters_comboBox.currentText() == "No Filter"
    actions.assert_not_called()


def test_a_fit_entry_leaves_the_loader_alone_because_it_does_not_record_one(
    tab: Triad, actions: Any
) -> None:
    controls = tab.tab_view.eventAnalysisControls
    before = controls.loaders_comboBox.currentText()

    tab.tab_view.write_back("fit_events", (FITTER, CHANNEL, ""), {})

    assert controls.loaders_comboBox.currentText() == before


@pytest.mark.parametrize(
    "events, text",
    [
        ([0, 1, 2, 3, 4], "0-4"),
        ([0, 1, 2, 5], "0-2,5"),
        ([7], "7"),
        ([5, 3, 4, 3], "3-5"),
    ],
)
def test_the_event_index_is_written_in_canonical_form(
    tab: Triad, actions: Any, events: List[int], text: str
) -> None:
    tab.tab_view.write_back(
        "plot_events", (LOADER, FITTER, CHANNEL, events, "", False), {}
    )

    assert tab.tab_view.eventAnalysisControls.event_index_lineEdit.text() == text
    actions.assert_not_called()


@pytest.mark.parametrize("action", ["fit_events", "plot_events"])
def test_a_named_filter_is_shown_for_every_kind_of_entry(
    tab: Triad, actions: Any, action: str
) -> None:
    controls = tab.tab_view.eventAnalysisControls
    controls.filters_comboBox.addItem("a filter")
    entries = {
        "fit_events": (FITTER, CHANNEL, "a filter"),
        "plot_events": (LOADER, FITTER, CHANNEL, [0], "a filter", False),
    }

    tab.tab_view.write_back(action, entries[action], {})

    assert controls.filters_comboBox.currentText() == "a filter"
    actions.assert_not_called()


def test_writing_back_a_plot_asks_for_the_loaders_channel_list(
    tab: Triad, actions: Any
) -> None:
    """The held-off combobox signal would have asked; the channels are selected after."""
    asked: List[str] = []
    tab.tab_view.loader_channels_requested.connect(asked.append)

    tab.tab_view.write_back(
        "plot_events", (LOADER, FITTER, CHANNEL, [0], "", False), {}
    )

    assert asked == [LOADER]


def test_a_value_that_is_not_an_option_is_skipped_and_said(
    tab: Triad, actions: Any
) -> None:
    said: List[str] = []
    tab.tab_view.add_text_to_display.connect(
        lambda message, source: said.append(message)
    )
    controls = tab.tab_view.eventAnalysisControls
    before = controls.loaders_comboBox.currentText()

    tab.tab_view.write_back(
        "plot_events",
        ("a loader that is gone", "a fitter that is gone", CHANNEL, [0], "", False),
        {},
    )

    assert controls.loaders_comboBox.currentText() == before
    assert any("a loader that is gone" in message for message in said)
    assert any("a fitter that is gone" in message for message in said)


def test_write_back_reads_no_widget(tab: Triad, actions: Any) -> None:
    """It runs under the replay tripwire: a read of a controls helper would raise."""
    with replaying():
        tab.tab_view.write_back(
            "plot_events", (LOADER, FITTER, CHANNEL, [0, 1], "", True), {}
        )
        tab.tab_view.write_back("fit_events", (FITTER, CHANNEL, ""), {})


def test_an_action_with_nothing_to_show_is_ignored(tab: Triad, actions: Any) -> None:
    tab.tab_view.write_back("an_action_from_another_tab", ("x",), {})

    actions.assert_not_called()
