"""
A result - a background run of one plugin on one channel - is recorded only once it finished.

The click's values are held from launch. When the Model says that plugin's run on that
channel ended, the Controller asks the plugin whether the channel holds a finished run, which a
run clears as it starts: if it does, the held entry is recorded; if not (cancelled, failed,
nothing found) it is dropped and the status panel says so. An earlier run of the same plugin
and channel stays in the history.
"""

from collections import OrderedDict
from typing import Any, Dict, List

import pytest
from pytest_mock import MockerFixture

from poriscope.utils.LogDecorator import register_action
from poriscope.utils.MetaController import MetaController


class _Tab(MetaController):
    """A Controller with a result, a view drawn from it and a view that is not."""

    def _init(self) -> None:
        pass

    def _setup_connections(self) -> None:
        pass

    @register_action(
        "find", kind="result", key=("finder", "channel"), skip_on_false=True
    )
    def find(self, finder: str, channel: int, ranges: List[Any]) -> bool:
        return True

    @register_action(
        "show", kind="view", figure="plot", depends_on=("finder", "channel")
    )
    def show(self, finder: str, channel: int) -> None:
        pass

    @register_action("trace", kind="view", figure="plot")
    def trace(self, start: float) -> None:
        pass


@pytest.fixture
def tab(mocker: MockerFixture) -> _Tab:
    """
    A tab built without Qt, whose plugins say every channel finished.

    :param mocker: pytest-mock fixture
    :return: the tab
    """
    controller = _Tab.__new__(_Tab)
    controller.view = mocker.Mock()
    controller.model = mocker.Mock()
    controller.model.reporter_metaclasses = {
        "A": "MetaEventFinder",
        "B": "MetaEventFinder",
        "F": "MetaEventFitter",
    }
    controller.model.call.return_value = True
    controller.logger = mocker.Mock()  # type: ignore[attr-defined]
    controller.tab_action_history = OrderedDict()
    # Every tab has a replay sequence; here none is running.
    controller.replay_sequence = mocker.Mock(
        running=False,
        **{"launched.return_value": False, "holds_panel_text.return_value": False},
    )
    for signal in ("add_text_to_display", "update_tab_action_history"):
        setattr(controller, signal, mocker.Mock())
    return controller


def _entry(action: str, **kwargs: Any) -> Dict[str, Any]:
    return {"action": action, "args": (), "kwargs": kwargs}


def _history(tab: _Tab) -> List[Dict[str, Any]]:
    assert list(tab.tab_action_history) == list(range(len(tab.tab_action_history)))
    return list(tab.tab_action_history.values())


def _panel(tab: _Tab) -> List[str]:
    return [call.args[0] for call in tab.add_text_to_display.emit.call_args_list]  # type: ignore[attr-defined]


def test_a_launched_run_is_recorded_only_when_it_finishes(tab: _Tab) -> None:
    tab.find("A", 1, [[0.0, 1.0]])

    assert _history(tab) == []

    tab.record_finished_run(1, "A")

    assert _history(tab) == [_entry("find", finder="A", channel=1, ranges=[[0.0, 1.0]])]
    tab.update_tab_action_history.emit.assert_called_with("_Tab", tab.tab_action_history)  # type: ignore[attr-defined]


def test_a_finder_is_asked_whether_the_channel_holds_a_finished_run(tab: _Tab) -> None:
    """A finder marks a channel finished only when it found events, so its status is enough."""
    tab.find("A", 2, [])

    tab.record_finished_run(2, "A")

    tab.model.call.assert_called_once_with(
        "MetaEventFinder", "A", "get_eventfinding_status", 2
    )


def test_a_fitter_is_asked_whether_the_channel_is_fitted_and_how_many_fits_are_good(
    tab: _Tab,
) -> None:
    """A fitter marks a channel fitted even when no fit was good, so its count is read too."""
    tab.find("F", 2, [])

    tab.record_finished_run(2, "F")

    assert [c.args for c in tab.model.call.call_args_list] == [
        ("MetaEventFitter", "F", "get_eventfitting_status", 2),
        ("MetaEventFitter", "F", "get_num_events", 2),
    ]


def _fitter_answers(fitted: bool, count: Any) -> Any:
    """The fitter's answers: fitted or not, and its count of good fits, or what it raises."""

    def call(metaclass: str, key: str, method: str, *args: Any) -> Any:
        if method == "get_eventfitting_status":
            return fitted
        if method == "get_num_events":
            if isinstance(count, Exception):
                raise count
            return count
        return True

    return call


def test_a_fit_with_no_good_fits_is_not_recorded_as_a_find_with_no_events_is_not(
    tab: _Tab,
) -> None:
    tab.model.call.side_effect = _fitter_answers(True, 0)
    tab.find("F", 2, [])

    tab.record_finished_run(2, "F")

    assert _history(tab) == []
    assert _panel(tab) == [
        "F did not finish channel 2, so this run is not saved in the tab's history"
    ]


def test_a_fit_whose_count_cannot_be_read_is_not_recorded(tab: _Tab) -> None:
    tab.model.call.side_effect = _fitter_answers(True, RuntimeError("no loader"))
    tab.find("F", 2, [])

    tab.record_finished_run(2, "F")

    assert _history(tab) == []


def test_a_rerun_with_no_good_fits_removes_the_earlier_fit_and_what_was_drawn_from_it(
    tab: _Tab,
) -> None:
    """The rerun cleared the channel as it started, as a Find that found nothing does."""
    tab.model.call.side_effect = _fitter_answers(True, 12)
    tab.find("F", 2, [])
    tab.record_finished_run(2, "F")
    tab.show("F", 2)

    tab.model.call.side_effect = _fitter_answers(True, 0)
    tab.find("F", 2, [])
    tab.record_finished_run(2, "F")

    assert _history(tab) == []
    assert _panel(tab)[-1].startswith(
        "F did not finish channel 2, so this run is not saved in the tab's history; its "
        "earlier run on that channel is removed"
    )


def test_a_run_that_did_not_finish_is_not_recorded_and_the_panel_says_so(
    tab: _Tab,
) -> None:
    tab.model.call.return_value = False
    tab.find("A", 1, [])

    tab.record_finished_run(1, "A")

    assert _history(tab) == []
    assert _panel(tab) == [
        "A did not finish channel 1, so this run is not saved in the tab's history"
    ]


def test_a_second_launch_while_the_first_runs_does_not_replace_its_values(
    tab: _Tab,
) -> None:
    """The Model refuses a second run of a plugin on a channel that is still running."""
    tab.find("A", 1, [[0.0, 1.0]])
    tab.find("A", 1, [[5.0, 6.0]])

    tab.record_finished_run(1, "A")

    assert _history(tab) == [_entry("find", finder="A", channel=1, ranges=[[0.0, 1.0]])]


def test_another_plugin_or_channel_finishing_records_nothing_held(tab: _Tab) -> None:
    tab.find("A", 1, [])

    tab.record_finished_run(2, "A")
    tab.record_finished_run(1, "B")
    tab.record_finished_run(1, "writer")

    assert _history(tab) == []
    tab.record_finished_run(1, "A")
    assert [entry["action"] for entry in _history(tab)] == ["find"]


def test_a_run_nothing_was_held_for_asks_no_plugin(tab: _Tab) -> None:
    tab.record_finished_run(1, "writer")

    tab.model.call.assert_not_called()
    assert _history(tab) == []


def test_a_rerun_that_did_not_finish_removes_the_earlier_run_and_what_was_drawn_from_it(
    tab: _Tab,
) -> None:
    """The rerun cleared the channel, so the history must not keep a run it no longer holds."""
    tab.find("A", 1, [[0.0, 1.0]])
    tab.record_finished_run(1, "A")
    tab.show("A", 1)
    tab.trace(2.0)
    tab.find("A", 2, [])
    tab.record_finished_run(2, "A")
    tab.find("B", 1, [])
    tab.record_finished_run(1, "B")
    tab.show("A", 2)

    tab.model.call.return_value = False
    tab.find("A", 1, [[5.0, 6.0]])
    tab.record_finished_run(1, "A")

    assert _history(tab) == [
        _entry("trace", start=2.0),
        _entry("find", finder="A", channel=2, ranges=[]),
        _entry("find", finder="B", channel=1, ranges=[]),
        _entry("show", finder="A", channel=2),
    ]
    tab.update_tab_action_history.emit.assert_called_with("_Tab", tab.tab_action_history)  # type: ignore[attr-defined]
    assert _panel(tab)[-1] == (
        "A did not finish channel 1, so this run is not saved in the tab's history; its "
        "earlier run on that channel is removed from the history too, with what was drawn "
        "from it, since the channel no longer holds its results"
    )


def test_a_first_run_that_did_not_finish_removes_nothing(tab: _Tab) -> None:
    tab.trace(2.0)
    tab.find("B", 1, [])
    tab.record_finished_run(1, "B")
    before = _history(tab)

    tab.model.call.return_value = False
    tab.find("A", 1, [])
    tab.record_finished_run(1, "A")

    assert _history(tab) == before
    assert _panel(tab) == [
        "A did not finish channel 1, so this run is not saved in the tab's history"
    ]


def test_a_status_that_cannot_be_read_counts_as_not_finished(tab: _Tab) -> None:
    tab.model.call.side_effect = KeyError("A")
    tab.find("A", 1, [])

    tab.record_finished_run(1, "A")

    assert _history(tab) == []
    tab.logger.error.assert_called_once()  # type: ignore[attr-defined]


def test_a_plugin_family_with_no_channel_status_is_recorded_unasked(
    tab: _Tab,
) -> None:
    tab.model.reporter_metaclasses["A"] = "MetaWriter"
    tab.find("A", 1, [])

    tab.record_finished_run(1, "A")

    tab.model.call.assert_not_called()
    assert [entry["action"] for entry in _history(tab)] == ["find"]


def test_a_view_is_recorded_at_once(tab: _Tab) -> None:
    tab.trace(1.0)

    assert _history(tab) == [_entry("trace", start=1.0)]
