"""
A recorded Plot Events holds its event range as text, and the Controller expands it.

The Raw Data and Event Analysis tabs used to record the expanded list, so a typed
``0-99999`` put 100,000 integers in the history and the session file. The View now
sends the range in its canonical spelling and the Controller expands it, through one
method both tabs share.
"""

import json
from typing import Any, List
from unittest.mock import MagicMock

import pytest

from poriscope.plugins.analysistabs.RawDataView import RawDataView
from poriscope.utils.MetaEventTabController import MetaEventTabController
from poriscope.views.integer_range_line_edit import IntegerRangeLineEdit

expand = MetaEventTabController._expand_event_range


@pytest.fixture
def formatter() -> RawDataView:
    """
    A View built without Qt, for the range helpers alone, which read no widget.

    :return: a view whose ``__init__`` never ran
    """
    return RawDataView.__new__(RawDataView)


class TestExpandingARange:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("", []),
            ("  ", []),
            ("7", [7]),
            ("0-2", [0, 1, 2]),
            ("0-2,5", [0, 1, 2, 5]),
            ("5,0-2", [0, 1, 2, 5]),
            ("3,3,2-4", [2, 3, 4]),
            (" 1 , 4-5 ", [1, 4, 5]),
            ("9-9", [9]),
        ],
    )
    def test_indices_and_ranges_expand_to_a_sorted_list(
        self, text: str, expected: List[int]
    ) -> None:
        assert expand(text) == expected

    @pytest.mark.parametrize(
        "text",
        ["a", "1-", "-3", "1-2-3", "5-3", "1,,2", "1;2", "1.5", "0-2,x", "--"],
    )
    def test_text_that_is_not_a_list_of_indices_and_ranges_gives_none(
        self, text: str
    ) -> None:
        """Nothing is guessed from a damaged range: the caller refuses the whole text."""
        assert expand(text) is None

    def test_a_long_range_is_expanded_in_full(self) -> None:
        assert expand("0-99999") == list(range(100000))


class TestTheControllerAgreesWithTheField:
    """
    Three steps turn typed text into the events plotted: the field expands it, the View
    writes that in canonical form, and the Controller expands the canonical form. The
    last has to give back what the first produced.
    """

    @pytest.mark.parametrize(
        "typed",
        [
            "5",
            "0-4",
            "2,3,4",
            "9,1-3",
            "1-3,2-6",
            "4,4,4",
            "7-5",
            "-3,8",
            "1-2-3,6",
            "0-2,,5",
            "",
        ],
    )
    def test_the_canonical_text_expands_back_to_what_the_field_gave(
        self, qtbot: Any, formatter: RawDataView, typed: str
    ) -> None:
        field = IntegerRangeLineEdit()
        qtbot.addWidget(field)
        field.setText(typed)
        from_the_field = field.get_values()

        canonical = formatter._format_event_indices(from_the_field)

        assert expand(canonical) == from_the_field


class TestWhatASessionHolds:
    def test_a_hundred_thousand_events_are_saved_as_their_range(
        self, formatter: RawDataView
    ) -> None:
        canonical = formatter._format_event_indices(list(range(100000)))

        assert canonical == "0-99999"
        saved = json.dumps({"event_range": canonical}, indent=4)
        assert len(saved) < 100

    def test_the_two_plot_events_actions_take_the_range_by_that_name(self) -> None:
        import inspect

        from poriscope.plugins.analysistabs.EventAnalysisController import (
            EventAnalysisController,
        )
        from poriscope.plugins.analysistabs.RawDataController import RawDataController

        for action in (
            RawDataController.load_event_plot_data,
            EventAnalysisController.load_event_plot,
        ):
            parameters = inspect.signature(action).parameters
            assert "event_range" in parameters
            assert "events" not in parameters
            assert parameters["event_range"].annotation is str


class TestAnEntrySavedBeforeTheChange:
    def test_an_entry_holding_the_list_is_reported_and_skipped(self) -> None:
        """
        Sessions saved by a development build hold the list under ``events``. Such an
        entry is said on the status panel and not called: there is nothing to convert.
        """
        from poriscope.plugins.analysistabs.RawDataController import RawDataController

        controller = RawDataController.__new__(RawDataController)
        controller.view = MagicMock()
        controller.add_text_to_display = MagicMock()
        old = {
            "action": "plot_events",
            "args": [],
            "kwargs": {
                "eventfinder": "finder",
                "channel": 0,
                "events": [0, 1, 2],
                "data_filter": "",
            },
        }

        assert controller.resolve_replayed_entry(old) is None

        message = controller.add_text_to_display.emit.call_args[0][0]
        assert message.startswith("Not replayed")
        assert "plot_events" in message
