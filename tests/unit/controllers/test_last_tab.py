"""
Which tab a session names as the last one: where the user last acted, not where a replay recorded.

``MainController.last_tab`` is saved with the session, and a load shows that tab. A replay
the restore dialog started records each step again, so without care the tab whose replay
finished last would become the last tab, by timing alone; so would a tab whose entries a
plugin delete or rename rewrote. Everything the user does - Undo, a plot by hand, Replay
Actions, Load Plot Configuration, Go back - still moves it.

The tabs are real ``MetaController`` subclasses, connected to a real ``MainController`` as
opening a tab connects them; their Model emits a real ``run_finished``.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Tuple
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, Signal
from pytest_mock import MockerFixture

from poriscope.controllers.main_controller import MainController
from poriscope.utils.LogDecorator import RESET_ACTION, register_action
from poriscope.utils.MetaController import MetaController


class _Model(QObject):
    """The part of a ``MetaModel`` a replay reaches; every run finishes with results."""

    run_finished = Signal(int, str)
    update_progressbar = Signal(float, str)
    add_text_to_display = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.thread_running: Dict[str, Dict[int, bool]] = {}
        self.reporter_metaclasses = {"F": "MetaEventFinder"}
        self.cache_plot_data = MagicMock()
        self.stop_workers = MagicMock()
        self.workers: Dict[str, Any] = {}
        self.finishes = True

    def call(self, metaclass: str, key: str, method: str, *args: Any) -> Any:
        if method == "get_num_events":
            return 5 if self.finishes else 0
        return self.finishes


class _Tab(MetaController):
    def _init(self) -> None:
        self.view = type(
            self.__class__.__name__.removesuffix("Controller") + "View",
            (MagicMock,),
            {},
        )()
        self.view.ask_after_replay_failure.return_value = "keep"
        self.model = _Model()  # type: ignore[assignment]
        self.calls: List[str] = []

    def _setup_connections(self) -> None:
        pass

    @register_action(RESET_ACTION, kind="reset", figure="plot")
    def reset(self, axis_type: str = "2d") -> None:
        self.calls.append("reset")

    @register_action("overlay", kind="additive", figure="plot", skip_on_false=True)
    def overlay(self, label: str) -> bool:
        self.calls.append(label)
        return True

    @register_action("trace", kind="view", figure="trace", plugin_args=("reader",))
    def trace(self, reader: str) -> bool:
        self.calls.append(f"trace {reader}")
        return True

    @register_action(
        "find", kind="result", key=("finder", "channel"), skip_on_false=True
    )
    def find(self, finder: str, channel: int) -> bool:
        self.calls.append(f"find {finder}/{channel}")
        return True


class TabAController(_Tab):
    pass


class TabBController(_Tab):
    pass


def _e(action: str, **kwargs: Any) -> Dict[str, Any]:
    return {"action": action, "args": [], "kwargs": kwargs}


#: A loaded tab's actions: a plot, a Find that waits on its run, another plot.
LOADED = [
    _e("reset"),
    _e("overlay", label="A"),
    _e("find", finder="F", channel=1),
    _e("overlay", label="B"),
]


@pytest.fixture
def shell(
    qtbot: Any, mocker: MockerFixture
) -> Iterator[Tuple[MainController, TabAController, TabBController]]:
    """
    A main window's controller with tabs A and B open, loaded with "Loaded" as last tab.

    :param qtbot: pytest-qt fixture, for the application the timers run on
    :param mocker: pytest-mock fixture
    :return: the controller and the two tabs
    """
    mocker.patch("poriscope.controllers.main_controller.DataPluginController")
    controller = MainController(MagicMock(), MagicMock())
    a, b = TabAController(), TabBController()
    for tab in (a, b):
        name = tab.__class__.__name__
        controller.analysis_tabs[name] = tab
        controller.plugin_history[name] = {
            "metaclass": "MetaController",
            "subclass": name,
        }
        tab.update_tab_action_history.connect(controller.update_tab_action_history)
    controller.last_tab = "Loaded"
    yield controller, a, b
    for tab in (a, b):
        tab.replay_sequence.stop(quitting=True)


def _restore(controller: MainController, *tabs: _Tab) -> None:
    """Start these tabs' replays as the restore dialog does, when they are ticked."""
    controller.main_view.ask_which_tabs_to_replay.return_value = [
        tab.view.__class__.__name__ for tab in tabs
    ]
    controller._offer_restore_replays()


def _finish_the_find(tab: _Tab, qtbot: Any) -> None:
    qtbot.waitUntil(lambda: "find F/1" in tab.calls)
    tab.model.run_finished.emit(1, "F")
    qtbot.waitUntil(lambda: not tab.is_replaying())


def test_a_restore_replay_leaves_the_last_tab(shell: Any, qtbot: Any) -> None:
    controller, a, b = shell
    a.hold_session_actions(LOADED, "s.json")
    b.hold_session_actions([_e("overlay", label="b1")], "s.json")

    _restore(controller, a, b)
    qtbot.waitUntil(lambda: not b.is_replaying())
    _finish_the_find(a, qtbot)

    assert a.calls == ["reset", "A", "find F/1", "B"]
    assert controller.last_tab == "Loaded"


def test_undo_during_a_restore_replay_moves_it(shell: Any, qtbot: Any) -> None:
    controller, a, b = shell
    a.hold_session_actions(LOADED, "s.json")
    _restore(controller, a)
    qtbot.waitUntil(lambda: "find F/1" in a.calls)

    a.update_tab_actions(None, True)

    assert controller.last_tab == "TabAController"


def test_a_plot_by_hand_moves_it_and_the_rest_of_the_replay_does_not(
    shell: Any, qtbot: Any
) -> None:
    controller, a, b = shell
    a.hold_session_actions(LOADED, "s.json")
    _restore(controller, a)
    qtbot.waitUntil(lambda: "find F/1" in a.calls)

    a.overlay("by hand")
    assert controller.last_tab == "TabAController"
    b.overlay("in B")
    assert controller.last_tab == "TabBController"
    a.model.run_finished.emit(1, "F")
    qtbot.waitUntil(lambda: not a.is_replaying())

    assert a.calls[-1] == "B"
    assert controller.last_tab == "TabBController"


def test_loading_a_plot_configuration_moves_it(shell: Any, qtbot: Any) -> None:
    controller, a, b = shell

    a.start_replay([_e("overlay", label="X")])
    qtbot.waitUntil(lambda: not a.is_replaying())

    assert controller.last_tab == "TabAController"


def test_replay_actions_after_keep_moves_it(shell: Any, qtbot: Any) -> None:
    controller, a, b = shell
    a.hold_session_actions(LOADED, "s.json")
    a.model.finishes = False
    _restore(controller, a)
    _finish_the_find(a, qtbot)
    assert a.replay_available()
    assert controller.last_tab == "Loaded"

    a.model.finishes = True
    controller.replay_tab_actions("TabAView")
    qtbot.waitUntil(lambda: a.calls.count("find F/1") == 2)
    a.model.run_finished.emit(1, "F")
    qtbot.waitUntil(lambda: not a.is_replaying())

    assert controller.last_tab == "TabAController"


def test_go_back_moves_it(shell: Any, qtbot: Any) -> None:
    controller, a, b = shell
    a.view.ask_after_replay_failure.return_value = "back"
    a.hold_session_actions(LOADED, "s.json")
    a.model.finishes = False
    _restore(controller, a)
    _finish_the_find(a, qtbot)
    qtbot.waitUntil(lambda: not a.is_replaying())

    assert controller.last_tab == "TabAController"


def test_a_plugin_delete_or_rename_leaves_it(shell: Any, qtbot: Any) -> None:
    controller, a, b = shell
    a.trace("R1")
    a.trace("R2")
    controller.last_tab = "TabBController"

    controller.update_plugin_history({}, "R1")
    controller._rewrite_tab_entries("R2", "R3")

    assert [entry["kwargs"]["reader"] for entry in a.tab_action_history.values()] == [
        "R3"
    ]
    assert controller.last_tab == "TabBController"


def test_a_plugin_delete_during_a_restore_replay_leaves_it(
    shell: Any, qtbot: Any
) -> None:
    controller, a, b = shell
    a.hold_session_actions(
        [_e("trace", reader="R1"), _e("find", finder="F", channel=1)], "s.json"
    )
    _restore(controller, a)
    qtbot.waitUntil(lambda: "find F/1" in a.calls)

    controller.update_plugin_history({}, "R1")
    a.model.run_finished.emit(1, "F")
    qtbot.waitUntil(lambda: not a.is_replaying())

    assert controller.last_tab == "Loaded"


# ------------------- what the tab says about a change ---------------------------


def test_a_tab_names_its_restore_replays_changes_and_only_those(
    shell: Any, qtbot: Any
) -> None:
    """
    True for the start, each step and the run it waited for; False otherwise.

    :param shell: the controller and tabs
    :param qtbot: pytest-qt fixture
    """
    controller, a, b = shell
    seen: List[Tuple[str, bool]] = []

    def note(name: str, history: Any) -> None:
        seen.append((str(len(history)), a.history_change_from_restore_replay()))

    a.update_tab_action_history.connect(note)
    a.hold_session_actions(LOADED, "s.json")
    a.start_replay(restore=True)
    _finish_the_find(a, qtbot)
    from_restore = [flag for _, flag in seen]
    seen.clear()
    a.overlay("by hand")
    a.start_replay([_e("overlay", label="X")])
    qtbot.waitUntil(lambda: not a.is_replaying())

    assert from_restore == [True] * 5  # the start, reset, A, the Find's record, B
    assert [flag for _, flag in seen] == [False, False]
    assert not a.history_change_from_restore_replay()
