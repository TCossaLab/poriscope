"""
How a tab's Controller runs a replay one entry at a time.

The Controller owns a ``ReplaySequence``: the Model's ``run_finished`` reaches it after the
Controller has recorded the run, a loaded plot configuration replays through it, and stopping
every operation of the tab stops it too. The tab is a real ``QObject`` Controller whose Model
emits a real ``run_finished``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, Signal

from poriscope.utils.LogDecorator import register_action
from poriscope.utils.MetaController import MetaController


class _Model(QObject):
    """The part of a ``MetaModel`` a replay and the kill-all slot reach."""

    run_finished = Signal(int, str)
    update_progressbar = Signal(float, str)
    add_text_to_display = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.thread_running: Dict[str, Dict[int, bool]] = {}
        self.reporter_metaclasses = {"A": "MetaEventFinder"}
        self.cache_plot_data = MagicMock()
        self.stop_workers = MagicMock()

    def call(self, metaclass: str, key: str, method: str, *args: Any) -> Any:
        assert method == "get_eventfinding_status"
        return True


class _Tab(MetaController):
    def _init(self) -> None:
        self.view = MagicMock()
        self.model = _Model()  # type: ignore[assignment]
        self.calls: List[str] = []

    def _setup_connections(self) -> None:
        pass

    @register_action("draw", kind="view", figure="plot", skip_on_false=True)
    def draw(self, label: str) -> bool:
        self.calls.append(f"draw:{label}")
        return True

    @register_action(
        "find", kind="result", key=("finder", "channel"), skip_on_false=True
    )
    def find(self, finder: str, channel: int) -> bool:
        self.calls.append(f"find:{finder}/{channel}")
        return True


@pytest.fixture
def tab(qtbot: Any) -> _Tab:
    """
    :param qtbot: pytest-qt fixture, for the application the timers run on
    :return: a tab whose finder says every channel finished
    """
    return _Tab()


@pytest.fixture
def panel(tab: _Tab) -> List[str]:
    """
    :param tab: the tab
    :return: every line the tab sends to the status panel, in order
    """
    lines: List[str] = []
    tab.add_text_to_display.connect(lambda text, source: lines.append(text))
    return lines


def _entry(action: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    return {"action": action, "args": list(args), "kwargs": kwargs}


def test_the_models_run_finished_reaches_the_replay_after_the_run_is_recorded(
    tab: _Tab, qtbot: Any
) -> None:
    assert tab.start_replay([_entry("find", "A", 1), _entry("draw", "b")])
    qtbot.waitUntil(lambda: tab.calls == ["find:A/1"])

    tab.model.run_finished.emit(1, "A")
    qtbot.waitUntil(lambda: not tab.is_replaying())

    assert tab.calls == ["find:A/1", "draw:b"]
    assert [entry["action"] for entry in tab.tab_action_history.values()] == [
        "find",
        "draw",
    ]


def test_a_loaded_file_is_replayed_one_entry_at_a_time(
    tab: _Tab, panel: List[str], qtbot: Any, tmp_path: Any
) -> None:
    path = tmp_path / "actions.json"
    path.write_text(
        json.dumps(
            {"_Tab": {"0": _entry("draw", label="a"), "1": _entry("draw", label="b")}}
        ),
        encoding="utf-8",
    )

    tab.load_actions_from_json(str(path))

    assert tab.calls == []
    assert tab.is_replaying()
    qtbot.waitUntil(lambda: not tab.is_replaying())
    assert tab.calls == ["draw:a", "draw:b"]
    assert panel == ["replay done"]


def test_the_2_0_action_autosave_loaded_as_a_plot_configuration_is_refused(
    tab: _Tab, qtbot: Any, tmp_path: Any, mocker: Any
) -> None:
    """2.0 kept each tab's history under the tab's name in ``tab_action_history.json``."""
    path = tmp_path / "tab_action_history.json"
    path.write_text(
        json.dumps({"_Tab": {"0": {"function": "draw", "args": ["a"], "kwargs": {}}}}),
        encoding="utf-8",
    )
    error = mocker.patch.object(tab.logger, "error")

    tab.load_actions_from_json(str(path))

    assert not tab.is_replaying()
    assert tab.calls == []
    error.assert_called_once()


def test_a_file_loaded_during_a_replay_is_refused(
    tab: _Tab, panel: List[str], qtbot: Any, tmp_path: Any
) -> None:
    path = tmp_path / "actions.json"
    path.write_text(json.dumps({"0": _entry("draw", label="late")}), encoding="utf-8")
    tab.start_replay([_entry("find", "A", 1)])
    qtbot.waitUntil(lambda: tab.calls == ["find:A/1"])

    tab.load_actions_from_json(str(path))

    assert panel == ["a replay is already running; stop it, or let it finish, first"]
    tab.model.run_finished.emit(1, "A")
    qtbot.waitUntil(lambda: not tab.is_replaying())
    assert "draw:late" not in tab.calls


def test_stopping_the_tabs_operations_stops_its_replay(
    tab: _Tab, panel: List[str], qtbot: Any
) -> None:
    tab.start_replay([_entry("find", "A", 1), _entry("draw", "b")])
    qtbot.waitUntil(lambda: tab.calls == ["find:A/1"])

    tab.handle_kill_all_workers("_Tab")
    tab.model.run_finished.emit(1, "A")
    qtbot.wait(20)

    assert not tab.is_replaying()
    assert tab.calls == ["find:A/1"]
    assert panel == ["Stopping all running operations.", "replay stopped"]


def test_the_next_start_continues_from_the_stopped_entry(tab: _Tab, qtbot: Any) -> None:
    tab.start_replay([_entry("find", "A", 1), _entry("draw", "b")])
    qtbot.waitUntil(lambda: tab.calls == ["find:A/1"])
    tab.handle_kill_all_workers("_Tab")
    tab.model.run_finished.emit(1, "A")

    assert tab.start_replay()
    qtbot.waitUntil(lambda: tab.calls == ["find:A/1", "find:A/1"])
    tab.model.run_finished.emit(1, "A")
    qtbot.waitUntil(lambda: not tab.is_replaying())

    assert tab.calls == ["find:A/1", "find:A/1", "draw:b"]


def test_a_kill_all_for_another_tab_leaves_the_replay_running(
    tab: _Tab, qtbot: Any
) -> None:
    tab.start_replay([_entry("find", "A", 1)])
    qtbot.waitUntil(lambda: tab.calls == ["find:A/1"])

    tab.handle_kill_all_workers("OtherTab")

    assert tab.is_replaying()


def test_quitting_stops_the_replay_without_a_line(
    tab: _Tab, panel: List[str], qtbot: Any
) -> None:
    tab.start_replay([_entry("find", "A", 1)])
    qtbot.waitUntil(lambda: tab.calls == ["find:A/1"])

    tab.handle_kill_all_workers("_Tab", exiting=True)

    assert not tab.is_replaying()
    assert panel == []
