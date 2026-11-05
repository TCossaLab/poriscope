"""
A real Find is recorded once it finished, and a Find that did not finish is not.

Driven through the Raw Data tab's Controller with a real reader and finder, so the
plugin's own answer decides: the unit tests stub it. A Find that found nothing leaves the
channel without events, so the earlier Find is removed from the history too.
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest

from tests.integration.flows._triad import Triad, build_rawdata_tab

FINDER = "finder"


def settle(triad: Triad, qtbot: Any) -> None:
    """Wait until the finder's run ended and its outcome reached the history."""
    controller = triad.tab_controller
    qtbot.waitUntil(
        lambda: not controller.model.workers.get(FINDER)
        and not controller._held_results,
        timeout=120_000,
    )


def find(triad: Triad, qtbot: Any, ranges: List[Any]) -> None:
    channel = triad.channel  # type: ignore[attr-defined]
    assert triad.tab_controller.find_events_on_channel(FINDER, channel, ranges, "", {})
    settle(triad, qtbot)


def finished(triad: Triad, channel: int) -> bool:
    return bool(
        triad.tab_controller.model.call(
            "MetaEventFinder", FINDER, "get_eventfinding_status", channel
        )
    )


def actions(triad: Triad) -> List[Any]:
    return [
        (entry["action"], entry["kwargs"]["ranges"])
        for entry in triad.tab_controller.tab_action_history.values()
    ]


@pytest.mark.timeout(240)
def test_a_find_that_finds_nothing_is_not_recorded(
    qapp, qtbot, tmp_path: Path, sample_chimera: Dict[str, str]
) -> None:
    triad = build_rawdata_tab(tmp_path, sample_chimera)
    messages: List[str] = []
    triad.tab_controller.add_text_to_display.connect(
        lambda text, source: messages.append(text)
    )
    channel = triad.channel  # type: ignore[attr-defined]
    try:
        find(triad, qtbot, [(0.0, 0.0)])
        assert finished(triad, channel)
        assert actions(triad) == [("find_events", [(0.0, 0.0)])]

        find(triad, qtbot, [(0.0, 0.00002)])

        assert not finished(triad, channel)
        assert actions(triad) == []
        assert any(
            f"Ch{channel}: no events found" in message for message in messages
        ), messages
        assert messages[-1] == (
            f"{FINDER} did not finish channel {channel}, so this run is not saved in "
            f"the tab's history; its earlier run on that channel is removed from the "
            f"history too, with what was drawn from it, since the channel no longer holds "
            f"its results"
        )
    finally:
        triad.close()
