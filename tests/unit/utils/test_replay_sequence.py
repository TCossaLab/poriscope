"""
Tests for ``ReplaySequence``: a tab's recorded actions replayed one entry at a time.

Each entry runs on its own turn of the event loop. A result entry - a background run of one
plugin on one channel - waits for that run to end before the next entry, and fails the replay
unless the run left a finished channel with results. A synchronous entry fails the replay when
it raises, or when an action that returns ``False`` for "did nothing" does so. The tab is a real
``QObject`` Controller, since every step is scheduled with the Controller as its context.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
import shiboken6
from PySide6.QtCore import QTimer

from poriscope.utils.LogDecorator import register_action
from poriscope.utils.MetaController import MetaController
from poriscope.utils.replay_sequence import ReplaySequence


class _Model:
    """
    The part of a ``MetaModel`` a replay reads: which runs are going, and the plugins' answers.

    ``call`` answers the two status methods and ``get_num_events`` from per-key tables,
    with the real methods' signatures ``(metaclass, key, method, channel)``.
    """

    def __init__(self) -> None:
        self.thread_running: Dict[str, Dict[int, bool]] = {}
        self.reporter_metaclasses: Dict[str, str] = {
            "A": "MetaEventFinder",
            "B": "MetaEventFinder",
            "F": "MetaEventFitter",
        }
        self.finished: Dict[str, bool] = {"A": True, "B": True, "F": True}
        self.counts: Dict[str, Any] = {"F": 12}
        self.resets: List[Any] = []
        self.update_progressbar = MagicMock()
        self.run_finished = MagicMock()
        self.add_text_to_display = MagicMock()
        self.cache_plot_data = MagicMock()

    def call(self, metaclass: str, key: str, method: str, *args: Any) -> Any:
        if method in ("get_eventfinding_status", "get_eventfitting_status"):
            return self.finished[key]
        if method == "reset_channel":
            self.resets.append((metaclass, key, *args))
            return None
        if method == "get_num_events":
            count = self.counts[key]
            if isinstance(count, Exception):
                raise count
            return count
        raise AssertionError(f"unexpected plugin call {method}")


class _Tab(MetaController):
    """A Controller with a result, views that can refuse, an overlay and an action that raises."""

    def _init(self) -> None:
        self.view = MagicMock()
        self.model = _Model()  # type: ignore[assignment]
        self.calls: List[str] = []
        self.draws: Dict[str, bool] = {}

    def _setup_connections(self) -> None:
        pass

    @register_action("draw", kind="view", figure="plot", skip_on_false=True)
    def draw(self, label: str) -> bool:
        self.calls.append(f"draw:{label}")
        if label == "marks":
            QTimer.singleShot(0, lambda: self.calls.append("event loop turn"))
        return self.draws.get(label, True)

    @register_action("overlay", kind="additive", figure="plot")
    def overlay(self, label: str) -> bool:
        self.calls.append(f"overlay:{label}")
        return False

    @register_action("boom", kind="view", figure="plot")
    def boom(self) -> None:
        self.calls.append("boom")
        raise RuntimeError("the column is gone")

    @register_action(
        "find", kind="result", key=("finder", "channel"), skip_on_false=True
    )
    def find(self, finder: str, channel: int) -> bool:
        self.calls.append(f"find:{finder}/{channel}")
        return True


@pytest.fixture
def tab(qtbot: Any) -> _Tab:
    """
    A tab whose plugins say every channel finished, with a fitter that fitted 12 events.

    :param qtbot: pytest-qt fixture, for the application the timers run on
    :return: the tab
    """
    return _Tab()


@pytest.fixture
def panel(tab: _Tab) -> List[str]:
    """
    Every line the tab sends to the status panel, in order.

    :param tab: the tab
    :return: the lines
    """
    lines: List[str] = []
    tab.add_text_to_display.connect(lambda text, source: lines.append(text))
    return lines


def _entry(action: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    return {"action": action, "args": list(args), "kwargs": kwargs}


def _replay(tab: _Tab, entries: List[Dict[str, Any]], qtbot: Any) -> ReplaySequence:
    sequence = ReplaySequence(tab)
    assert sequence.start(entries)
    qtbot.waitUntil(lambda: not sequence.running or sequence.waiting_for is not None)
    return sequence


def _run_ends(tab: _Tab, sequence: ReplaySequence, channel: int, key: str) -> None:
    """The Model's ``run_finished``: the tab records the run, then the replay hears of it."""
    tab.record_finished_run(channel, key)
    sequence.on_run_finished(channel, key)


def _ended(sequence: ReplaySequence, qtbot: Any) -> None:
    qtbot.waitUntil(lambda: not sequence.running)


class TestOrder:
    def test_nothing_runs_until_the_event_loop_turns(self, tab: _Tab) -> None:
        sequence = ReplaySequence(tab)

        sequence.start([_entry("draw", "a")])

        assert tab.calls == []
        assert sequence.running

    def test_entries_run_in_order_with_a_turn_of_the_event_loop_between_them(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        """A timer the first entry starts fires before the second entry runs."""
        sequence = _replay(tab, [_entry("draw", "marks"), _entry("draw", "b")], qtbot)

        assert tab.calls == ["draw:marks", "event loop turn", "draw:b"]
        assert not sequence.running
        assert panel[-1] == "_Tab: replay done"

    def test_an_unknown_entry_is_reported_and_the_rest_run(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        _replay(tab, [_entry("gone"), _entry("draw", "b")], qtbot)

        assert tab.calls == ["draw:b"]
        assert panel == [
            "Not replayed: 'gone' is not a recorded action of _Tab",
            "_Tab: replay done",
        ]

    def test_a_replayed_action_is_recorded_again(self, tab: _Tab, qtbot: Any) -> None:
        _replay(tab, [_entry("draw", "a")], qtbot)

        assert list(tab.tab_action_history.values()) == [
            {"action": "draw", "args": (), "kwargs": {"label": "a"}}
        ]

    def test_a_second_start_while_running_is_refused(self, tab: _Tab) -> None:
        sequence = ReplaySequence(tab)
        sequence.start([_entry("draw", "a")])

        assert not sequence.start([_entry("draw", "b")])


class TestSynchronousFailure:
    def test_an_entry_that_raises_stops_the_replay(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        sequence = _replay(tab, [_entry("boom"), _entry("draw", "b")], qtbot)

        assert tab.calls == ["boom"]
        assert not sequence.running
        assert sequence.failed_at == 0
        assert panel == [
            "_Tab: replay stopped at step 1 of 2: boom raised RuntimeError: the column "
            "is gone"
        ]

    def test_an_action_that_did_nothing_stops_the_replay(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        tab.draws["a"] = False

        sequence = _replay(tab, [_entry("draw", "a"), _entry("draw", "b")], qtbot)

        assert tab.calls == ["draw:a"]
        assert sequence.failed_at == 0
        assert panel == ["_Tab: replay stopped at step 1 of 2: draw did nothing"]

    def test_an_overlay_that_drew_nothing_does_not(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        """An overlay is recorded whether or not it drew, so its ``False`` is no refusal."""
        sequence = _replay(tab, [_entry("overlay", "x"), _entry("draw", "b")], qtbot)

        assert tab.calls == ["overlay:x", "draw:b"]
        assert sequence.failed_at is None
        assert panel == ["_Tab: replay done"]


class TestResults:
    def test_a_result_waits_for_its_own_run_to_end(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        sequence = _replay(tab, [_entry("find", "A", 1), _entry("draw", "b")], qtbot)

        assert sequence.waiting_for == ("A", 1)
        _run_ends(tab, sequence, 2, "A")
        _run_ends(tab, sequence, 1, "B")
        qtbot.wait(20)
        assert tab.calls == ["find:A/1"]

        _run_ends(tab, sequence, 1, "A")
        _ended(sequence, qtbot)

        assert tab.calls == ["find:A/1", "draw:b"]
        assert panel == ["_Tab: replay done"]

    @pytest.mark.parametrize("plugin", ["A", "F"])
    def test_a_run_that_did_not_finish_stops_the_replay(
        self, tab: _Tab, panel: List[str], qtbot: Any, plugin: str
    ) -> None:
        """Cancelled, failed or no events found: the plugin says the channel is not finished."""
        tab.model.finished[plugin] = False  # type: ignore[attr-defined]
        sequence = _replay(tab, [_entry("find", plugin, 3), _entry("draw", "b")], qtbot)

        _run_ends(tab, sequence, 3, plugin)
        _ended(sequence, qtbot)

        assert tab.calls == [f"find:{plugin}/3"]
        assert sequence.failed_at == 0
        assert panel == [
            f"{plugin} did not finish channel 3, so this run is not saved in the tab's "
            f"history",
            f"_Tab: replay stopped at step 1 of 2: {plugin} did not leave a finished "
            f"run with results on channel 3",
        ]

    def test_a_fit_with_no_good_fits_stops_the_replay(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        """A fitter marks the channel fitted even when no fit was good."""
        tab.model.counts["F"] = 0  # type: ignore[attr-defined]
        sequence = _replay(tab, [_entry("find", "F", 3)], qtbot)

        _run_ends(tab, sequence, 3, "F")
        _ended(sequence, qtbot)

        assert sequence.failed_at == 0
        assert panel == [
            "_Tab: replay stopped at step 1 of 1: F did not leave a finished run with "
            "results on channel 3"
        ]

    def test_a_fit_whose_count_cannot_be_read_stops_the_replay(
        self, tab: _Tab, qtbot: Any
    ) -> None:
        tab.model.counts["F"] = RuntimeError("no loader")  # type: ignore[attr-defined]
        sequence = _replay(tab, [_entry("find", "F", 3)], qtbot)

        _run_ends(tab, sequence, 3, "F")
        _ended(sequence, qtbot)

        assert sequence.failed_at == 0

    def test_a_find_that_found_events_carries_on(self, tab: _Tab, qtbot: Any) -> None:
        """A finder's channel is finished only when events were found, so no count is read."""
        sequence = _replay(tab, [_entry("find", "A", 1)], qtbot)

        _run_ends(tab, sequence, 1, "A")
        _ended(sequence, qtbot)

        assert sequence.failed_at is None

    @pytest.mark.parametrize("going", ["thread", "held"])
    def test_a_run_already_going_on_that_channel_is_waited_out(
        self, tab: _Tab, qtbot: Any, going: str
    ) -> None:
        """
        Launched now, it would be refused and the replay would wait on the other run.

        A run whose worker is gone but whose end has not reached the tab yet is still held.
        """
        if going == "thread":
            tab.model.thread_running = {"A": {1: True}}  # type: ignore[attr-defined]
        else:
            tab._held()[("A", 1)] = _entry("find", finder="A", channel=1)
        sequence = _replay(tab, [_entry("find", "A", 1)], qtbot)
        qtbot.wait(20)

        assert tab.calls == []
        assert sequence.waiting_for == ("A", 1)

        tab.model.thread_running = {}  # type: ignore[attr-defined]
        tab._held().clear()
        _run_ends(tab, sequence, 1, "A")
        qtbot.waitUntil(lambda: tab.calls == ["find:A/1"])

        assert sequence.waiting_for == ("A", 1)
        assert sequence.running


class TestStop:
    def test_stop_ends_the_replay_and_the_next_start_reruns_the_cancelled_entry(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        sequence = _replay(tab, [_entry("find", "A", 1), _entry("draw", "b")], qtbot)

        sequence.stop()
        _run_ends(tab, sequence, 1, "A")
        qtbot.wait(20)

        assert not sequence.running
        assert tab.calls == ["find:A/1"]
        assert panel == ["_Tab: replay stopped"]

        assert sequence.start()
        qtbot.waitUntil(lambda: sequence.waiting_for is not None)
        _run_ends(tab, sequence, 1, "A")
        _ended(sequence, qtbot)

        assert tab.calls == ["find:A/1", "find:A/1", "draw:b"]

    def test_a_step_scheduled_before_a_stop_does_not_run(
        self, tab: _Tab, qtbot: Any
    ) -> None:
        sequence = ReplaySequence(tab)
        sequence.start([_entry("draw", "a")])

        sequence.stop()
        qtbot.wait(20)

        assert tab.calls == []

    def test_a_step_from_before_a_restart_does_not_run_alongside_the_new_one(
        self, tab: _Tab, qtbot: Any
    ) -> None:
        """Two chains of steps would run the second entry before the loop turns."""
        sequence = ReplaySequence(tab)
        sequence.start([_entry("draw", "marks"), _entry("draw", "b")])
        sequence.stop()
        sequence.start()

        _ended(sequence, qtbot)

        assert tab.calls == ["draw:marks", "event loop turn", "draw:b"]

    def test_stopping_on_quit_writes_nothing(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        sequence = _replay(tab, [_entry("find", "A", 1)], qtbot)

        sequence.stop(quitting=True)

        assert not sequence.running
        assert panel == []

    def test_nothing_left_to_continue_is_not_started(
        self, tab: _Tab, qtbot: Any
    ) -> None:
        sequence = _replay(tab, [_entry("draw", "a")], qtbot)

        assert not sequence.start()

    def test_a_step_scheduled_before_the_tab_is_destroyed_does_nothing(
        self, qtbot: Any
    ) -> None:
        tab = _Tab()
        calls = tab.calls
        sequence = ReplaySequence(tab)
        sequence.start([_entry("draw", "a")])

        shiboken6.delete(tab)
        qtbot.wait(20)

        assert calls == []


class TestAfterAFailure:
    """The user is asked to go back to before the replay, or keep what was replayed."""

    @staticmethod
    def _answer(tab: _Tab, choice: str, order: List[str]) -> MagicMock:
        def ask(*args: Any) -> str:
            order.append("asked")
            return choice

        tab.view.ask_after_replay_failure = MagicMock(side_effect=ask)
        tab.add_text_to_display.connect(lambda text, source: order.append(text))
        return tab.view.ask_after_replay_failure

    def test_the_dialog_names_the_step_and_the_reason_after_the_panel_has_said_so(
        self, tab: _Tab, qtbot: Any
    ) -> None:
        order: List[str] = []
        ask = self._answer(tab, "keep", order)

        _replay(tab, [_entry("draw", "a"), _entry("boom")], qtbot)

        ask.assert_called_once_with(
            "_Tab", 2, 2, "boom", "boom raised RuntimeError: the column is gone"
        )
        assert order[-2:] == [
            "_Tab: replay stopped at step 2 of 2: boom raised RuntimeError: the "
            "column is gone",
            "asked",
        ]

    def test_keep_leaves_what_was_replayed_and_continues_from_the_failed_entry(
        self, tab: _Tab, qtbot: Any
    ) -> None:
        self._answer(tab, "keep", [])
        tab.draws["b"] = False
        sequence = _replay(
            tab, [_entry("draw", "a"), _entry("draw", "b"), _entry("draw", "c")], qtbot
        )

        assert [e["kwargs"]["label"] for e in tab.tab_action_history.values()] == ["a"]
        assert sequence.has_remaining()

        tab.draws["b"] = True
        assert sequence.start()
        _ended(sequence, qtbot)

        assert tab.calls == ["draw:a", "draw:b", "draw:b", "draw:c"]

    def test_go_back_clears_the_tab_and_rebuilds_its_history_from_before(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        tab.draw("before")
        tab.calls.clear()
        tab.clear_for_replay = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda: tab.calls.append("cleared")
        )
        self._answer(tab, "back", [])
        sequence = _replay(tab, [_entry("find", "A", 1), _entry("boom")], qtbot)
        _run_ends(tab, sequence, 1, "A")
        qtbot.waitUntil(lambda: "draw:before" in tab.calls)
        _ended(sequence, qtbot)

        assert tab.calls == ["find:A/1", "boom", "cleared", "draw:before"]
        assert tab.model.resets == [("MetaEventFinder", "A", 1)]  # type: ignore[attr-defined]
        assert list(tab.tab_action_history.values()) == [
            {"action": "draw", "args": (), "kwargs": {"label": "before"}}
        ]
        assert panel[-2:] == [
            "_Tab: going back to before the replay",
            "_Tab: back to before the replay",
        ]
        assert not sequence.has_remaining()

    def test_a_failed_go_back_leaves_the_tab_cleared_and_asks_nothing_more(
        self, tab: _Tab, panel: List[str], qtbot: Any
    ) -> None:
        tab.draw("before")
        tab.draws["before"] = False
        tab.clear_for_replay = MagicMock()  # type: ignore[method-assign]
        ask = self._answer(tab, "back", [])
        states: List[bool] = []
        tab.replay_state_changed.connect(states.append)
        sequence = _replay(tab, [_entry("boom")], qtbot)
        qtbot.waitUntil(lambda: panel[-1].startswith("_Tab: going back stopped"))
        _ended(sequence, qtbot)

        assert states == [False, True, False, False]

        ask.assert_called_once()
        assert tab.clear_for_replay.call_count == 2
        assert list(tab.tab_action_history.values()) == []
        assert panel[-1] == (
            "_Tab: going back stopped at step 1 of 1: draw did nothing; the tab is "
            "left cleared"
        )
        assert not sequence.has_remaining()
