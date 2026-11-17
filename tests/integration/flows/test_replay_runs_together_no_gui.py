"""
A replay launches its runs together, on a real reader and finder over two channels.

A Find on both channels is recorded by hand in one tab and replayed into another. The
finder's chunks are held on gates, so the test decides when each run goes on: both runs
have started before either is let past its first chunk, and one is stopped while the other
is still working, which is when the replay asks whether to go back or keep.
"""

import copy
import threading
from pathlib import Path
from typing import Any, Dict, List

import pytest

from tests.integration.flows._triad import Triad, build_rawdata_tab

FINDER = "finder"


class HeldChunks:
    """
    Holds every run's first chunk on one gate and its second chunk on another.

    A run reads a stop between chunks, so a run stopped while it is held on the first gate
    ends there once the gate opens, and one still to do its second chunk is going until the
    second gate opens. The recording spans two chunks.
    """

    def __init__(self, finder: Any) -> None:
        self.first = threading.Event()
        self.second = threading.Event()
        self.runs_started = 0
        self._lock = threading.Lock()
        self._run = threading.local()
        self._chunk = finder._find_events_in_chunk
        finder._find_events_in_chunk = self

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        chunks = self._run.chunks = getattr(self._run, "chunks", 0) + 1
        if chunks == 1:
            with self._lock:
                self.runs_started += 1
            self.first.wait(timeout=60)
        elif chunks == 2:
            self.second.wait(timeout=60)
        return self._chunk(*args, **kwargs)

    def open(self) -> None:
        self.first.set()
        self.second.set()


def settle(triad: Triad, qtbot: Any) -> None:
    """Wait until no run of the finder is left and every finished one is recorded."""
    controller = triad.tab_controller
    qtbot.waitUntil(
        lambda: not controller.model.workers.get(FINDER)
        and not controller._held_results,
        timeout=120_000,
    )


def finished(triad: Triad, channel: int) -> bool:
    return bool(
        triad.tab_controller.model.call(
            "MetaEventFinder", FINDER, "get_eventfinding_status", channel
        )
    )


def found_channels(triad: Triad) -> List[int]:
    """The channel of each Find in the tab's history, in the history's order."""
    return [
        entry["kwargs"]["channel"]
        for entry in triad.tab_controller.tab_action_history.values()
        if entry["action"] == "find_events"
    ]


@pytest.fixture
def recorded(qtbot: Any, tmp_path: Path, two_channel_chimera: Dict[str, Any]) -> Any:
    """
    A Find on both channels, clicked once in a tab of its own, as its history holds it.

    :return: the recorded entries
    """
    (tmp_path / "recorded").mkdir()
    triad = build_rawdata_tab(tmp_path / "recorded", two_channel_chimera)
    channels = two_channel_chimera["channels"]
    try:
        view = triad.tab_view
        view.analysis_time_limits[FINDER] = {
            channel: {"start": 0.0, "end": 0.0} for channel in channels
        }
        view.handle_parameter_change(
            "rawdatacontrols",
            "find_events",
            (
                {
                    "eventfinder": FINDER,
                    "filter": "No Filter",
                    "channel": [str(channel) for channel in channels],
                },
            ),
        )
        settle(triad, qtbot)
        history = list(triad.tab_controller.tab_action_history.values())
        assert sorted(found_channels(triad)) == sorted(channels)
        return copy.deepcopy(history)
    finally:
        triad.close()


@pytest.fixture
def replaying_tab(
    qtbot: Any, tmp_path: Path, two_channel_chimera: Dict[str, Any]
) -> Any:
    """
    A second tab over the same recording, with its finder's chunks held.

    :return: the tab, the gates, and every line the tab sent to the status panel
    """
    (tmp_path / "replayed").mkdir()
    triad = build_rawdata_tab(tmp_path / "replayed", two_channel_chimera)
    controller = triad.tab_controller
    held = HeldChunks(controller.model._plugin_instances["MetaEventFinder"][FINDER])
    lines: List[str] = []
    controller.add_text_to_display.connect(lambda text, source: lines.append(text))
    try:
        yield triad, held, lines
    finally:
        held.open()
        controller.replay_sequence.stop(quitting=True)
        triad.close()


def _answer(triad: Triad, choice: str) -> List[Dict[str, Any]]:
    """Answer the replay's question, noting what was still going when it was asked."""
    controller = triad.tab_controller
    asked: List[Dict[str, Any]] = []

    def ask(tab: str, step: int, total: int, action: str, *rest: Any) -> str:
        asked.append(
            {
                "action": action,
                "replaying": controller.is_replaying(),
                "going": sorted(controller.model.workers.get(FINDER, {})),
            }
        )
        return choice

    triad.tab_view.ask_after_replay_failure = ask  # type: ignore[method-assign]
    return asked


def _stop_the_first_while_both_are_held(
    triad: Triad, held: HeldChunks, recorded: List[Any], qtbot: Any
) -> List[int]:
    """
    Start the replay, see both runs started, stop the first and let it go on to its end.

    :return: the stopped channel, then the other
    """
    controller = triad.tab_controller
    stopped, other = (entry["kwargs"]["channel"] for entry in recorded)
    assert controller.start_replay(recorded)
    qtbot.waitUntil(lambda: held.runs_started == 2, timeout=60_000)
    controller.handle_kill_worker(controller.__class__.__name__, f"{FINDER}/{stopped}")
    held.first.set()
    return [stopped, other]


@pytest.mark.timeout(240)
def test_both_channels_runs_have_started_before_either_ends(
    qapp, qtbot, recorded: List[Any], replaying_tab: Any
) -> None:
    triad, held, lines = replaying_tab
    controller = triad.tab_controller

    assert controller.start_replay(recorded)
    qtbot.waitUntil(lambda: held.runs_started == 2, timeout=60_000)

    assert sorted(controller.model.workers[FINDER]) == sorted(
        entry["kwargs"]["channel"] for entry in recorded
    )
    held.open()
    qtbot.waitUntil(lambda: not controller.is_replaying(), timeout=120_000)
    settle(triad, qtbot)
    assert lines[-1] == "replay done"
    assert found_channels(triad) == [e["kwargs"]["channel"] for e in recorded]


@pytest.mark.timeout(240)
def test_keeping_after_one_run_is_stopped_leaves_the_other_and_reruns_only_the_stopped(
    qapp, qtbot, recorded: List[Any], replaying_tab: Any
) -> None:
    triad, held, lines = replaying_tab
    controller = triad.tab_controller
    asked = _answer(triad, "keep")

    stopped, other = _stop_the_first_while_both_are_held(triad, held, recorded, qtbot)
    qtbot.waitUntil(lambda: bool(asked), timeout=60_000)

    assert asked == [{"action": "find_events", "replaying": True, "going": [other]}]

    held.second.set()
    qtbot.waitUntil(lambda: not controller.is_replaying(), timeout=120_000)
    settle(triad, qtbot)
    assert not finished(triad, stopped)
    assert finished(triad, other)
    assert found_channels(triad) == [other]

    assert controller.start_replay()
    qtbot.waitUntil(lambda: not controller.is_replaying(), timeout=120_000)
    settle(triad, qtbot)

    assert held.runs_started == 3
    assert len(asked) == 1
    assert finished(triad, stopped)
    assert found_channels(triad) == [stopped, other]


@pytest.mark.timeout(240)
def test_going_back_after_one_run_is_stopped_stops_the_other_and_clears_the_tab(
    qapp, qtbot, recorded: List[Any], replaying_tab: Any
) -> None:
    triad, held, lines = replaying_tab
    controller = triad.tab_controller
    asked = _answer(triad, "back")

    stopped, other = _stop_the_first_while_both_are_held(triad, held, recorded, qtbot)
    qtbot.waitUntil(lambda: bool(asked), timeout=60_000)

    assert asked == [{"action": "find_events", "replaying": True, "going": [other]}]
    assert f"Stopping {FINDER} on channel {other}." in lines
    assert controller.is_replaying()

    held.second.set()
    qtbot.waitUntil(lambda: not controller.is_replaying(), timeout=120_000)
    settle(triad, qtbot)

    assert lines[-1] == "back to before the replay"
    assert not finished(triad, stopped)
    assert not finished(triad, other)
    assert list(controller.tab_action_history.values()) == []
