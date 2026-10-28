"""
Raw Data write-back: a recorded entry's values are shown in a fresh tab's panel.

``write_back`` writes the panel and the stored inputs an entry used, so a restored tab shows
what produced its result. It never reads a widget (it runs while a replay is under the
tripwire), and it never emits an action: a handler reacting to a value that was just written
would undo it. These tests build a real tab, which has the reader and finder registered and
the Controller that answers the channel-list request, then write entries into it.
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest

from poriscope.utils.ReplayGuard import replaying
from tests.integration.flows._triad import Triad, build_rawdata_tab, named

READER = "reader"
FINDER = "finder"


@pytest.fixture
def tab(qapp: Any, tmp_path: Path, sample_chimera: Dict[str, str]) -> Triad:
    triad = build_rawdata_tab(tmp_path, sample_chimera, READER, FINDER)
    yield triad
    triad.close()


@pytest.fixture
def actions(tab: Triad, mocker: Any) -> Any:
    """Replace the View's dispatch with a spy: a write-back must not trigger an action."""
    return mocker.patch.object(tab.tab_view, "handle_parameter_change")


def test_an_update_trace_entry_shows_its_source_and_range(
    tab: Triad, actions: Any
) -> None:
    channel = tab.channel  # type: ignore[attr-defined]
    controls = tab.tab_view.rawdatacontrols

    tab.tab_view.write_back(
        "update_trace",
        (),
        named(tab, "update_trace", READER, [channel], 1.0, 0.5, "", False),
    )

    assert controls.readers_comboBox.currentText() == READER
    assert controls.channel_comboBox.getSelectedItems() == [str(channel)]
    assert controls.filters_comboBox.currentText() == "No Filter"
    assert controls.start_time_lineEdit.get_start() == 1.0
    assert controls.start_time_lineEdit.get_duration() == 0.5
    actions.assert_not_called()


def test_an_update_psd_entry_shows_the_same_fields(tab: Triad, actions: Any) -> None:
    channel = tab.channel  # type: ignore[attr-defined]
    controls = tab.tab_view.rawdatacontrols

    tab.tab_view.write_back(
        "update_psd", (), named(tab, "update_psd", READER, [channel], 2.0, 0.25, "")
    )

    assert controls.channel_comboBox.getSelectedItems() == [str(channel)]
    assert controls.start_time_lineEdit.get_start() == 2.0
    assert controls.start_time_lineEdit.get_duration() == 0.25
    actions.assert_not_called()


def test_a_find_entry_shows_its_finder_and_restores_its_timer_limits(
    tab: Triad, actions: Any
) -> None:
    channel = tab.channel  # type: ignore[attr-defined]
    view = tab.tab_view
    limits = {"start": 0.5, "end": 1.0}

    view.write_back(
        "find_events",
        (),
        named(tab, "find_events", FINDER, channel, [(0.5, 1.0)], "", limits),
    )
    limits["end"] = 99.0  # the tab holds its own copy

    assert view.rawdatacontrols.eventfinders_comboBox.currentText() == FINDER
    assert view.rawdatacontrols.channel_comboBox.getSelectedItems() == [str(channel)]
    assert view.analysis_time_limits[FINDER][channel] == {"start": 0.5, "end": 1.0}
    actions.assert_not_called()


@pytest.mark.parametrize(
    "events, text",
    [
        ([0, 1, 2, 3, 4], "0-4"),
        ([0, 1, 2, 5], "0-2,5"),
        ([7], "7"),
        ([5, 3, 4, 3], "3-5"),
    ],
)
def test_a_plot_events_entry_writes_the_event_index_in_canonical_form(
    tab: Triad, actions: Any, events: List[int], text: str
) -> None:
    channel = tab.channel  # type: ignore[attr-defined]
    view = tab.tab_view

    view.write_back(
        "plot_events", (), named(tab, "plot_events", FINDER, channel, events, "")
    )

    assert view.rawdatacontrols.event_index_lineEdit.text() == text
    assert view.rawdatacontrols.eventfinders_comboBox.currentText() == FINDER
    actions.assert_not_called()


@pytest.mark.parametrize("action", ["update_trace", "find_events", "plot_events"])
def test_a_named_filter_is_shown_for_every_kind_of_entry(
    tab: Triad, actions: Any, action: str
) -> None:
    channel = tab.channel  # type: ignore[attr-defined]
    controls = tab.tab_view.rawdatacontrols
    controls.filters_comboBox.addItem("a filter")
    entries = {
        "update_trace": (READER, [channel], 0.0, 1.0, "a filter", False),
        "find_events": (FINDER, channel, [(0.0, 1.0)], "a filter", {}),
        "plot_events": (FINDER, channel, [0], "a filter"),
    }

    tab.tab_view.write_back(action, (), named(tab, action, *entries[action]))

    assert controls.filters_comboBox.currentText() == "a filter"
    actions.assert_not_called()


def test_writing_back_a_reader_asks_for_its_channel_list(
    tab: Triad, actions: Any
) -> None:
    """The held-off combobox signal would have asked; the channels are selected after."""
    asked: List[str] = []
    tab.tab_view.reader_channels_requested.connect(asked.append)
    channel = tab.channel  # type: ignore[attr-defined]

    tab.tab_view.write_back(
        "update_trace",
        (),
        named(tab, "update_trace", READER, [channel], 0.0, 1.0, "", False),
    )

    assert asked == [READER]


def test_a_value_that_is_not_an_option_is_skipped_and_said(
    tab: Triad, actions: Any
) -> None:
    said: List[str] = []
    tab.tab_view.add_text_to_display.connect(
        lambda message, source: said.append(message)
    )
    controls = tab.tab_view.rawdatacontrols
    before = controls.readers_comboBox.currentText()

    tab.tab_view.write_back(
        "update_trace",
        (),
        named(tab, "update_trace", "a reader that is gone", [0], 0.0, 1.0, "", False),
    )

    assert controls.readers_comboBox.currentText() == before
    assert any("a reader that is gone" in message for message in said)


def test_write_back_reads_no_widget(tab: Triad, actions: Any) -> None:
    """It runs under the replay tripwire: a read of a controls helper would raise."""
    channel = tab.channel  # type: ignore[attr-defined]

    with replaying():
        tab.tab_view.write_back(
            "update_trace",
            (),
            named(tab, "update_trace", READER, [channel], 1.0, 0.5, "", False),
        )
        tab.tab_view.write_back(
            "plot_events", (), named(tab, "plot_events", FINDER, channel, [0, 1], "")
        )


def test_an_action_with_nothing_to_show_is_ignored(tab: Triad, actions: Any) -> None:
    tab.tab_view.write_back("an_action_from_another_tab", ("x",), {})

    actions.assert_not_called()
