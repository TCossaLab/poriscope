"""
The Replay Actions button under the status panel, and the two signals behind it.

A tab says whether it has a replay to continue (``replay_state_changed``); the main window
keeps that per page and enables the button for the page showing. A click asks for the page
showing (``replay_actions_requested``), and ``MainController`` continues that tab's replay.
Real tabs over a mock window, wired by ``MainController.instantiate_analysis_tab``.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, Signal
from pytest_mock import MockerFixture

from poriscope.controllers.main_controller import MainController
from poriscope.utils.LogDecorator import register_action
from poriscope.utils.MetaController import MetaController


class _Model(QObject):
    run_finished = Signal(int, str)
    update_progressbar = Signal(float, str)
    add_text_to_display = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.thread_running: Dict[str, Dict[int, bool]] = {}
        self.reporter_metaclasses: Dict[str, str] = {}
        self.cache_plot_data = MagicMock()
        self.stop_workers = MagicMock()
        self.set_plugin_instances = MagicMock()
        self.update_available_plugins = MagicMock()


class _TabView(MagicMock):
    pass


class _OtherView(MagicMock):
    pass


class _Tab(MetaController):
    view_class: type = _TabView

    def _init(self) -> None:
        self.view = self.view_class()
        self.view.ask_after_replay_failure.return_value = "keep"
        self.model = _Model()  # type: ignore[assignment]
        self.calls: List[str] = []
        self.refuse: set = set()

    def _setup_connections(self) -> None:
        pass

    @register_action("draw", kind="view", figure="plot", skip_on_false=True)
    def draw(self, label: str) -> bool:
        self.calls.append(f"draw:{label}")
        return label not in self.refuse


class _Other(_Tab):
    view_class = _OtherView


@pytest.fixture
def main(qtbot: Any, mocker: MockerFixture) -> MainController:
    """
    :param qtbot: pytest-qt fixture, for the application the timers run on
    :param mocker: pytest-mock fixture
    :return: a MainController over a mock window, with both test tabs open
    """
    mocker.patch("poriscope.controllers.main_controller.DataPluginController")
    model = mocker.Mock()
    model.get_plugin_classes.return_value = {
        "_Tab": lambda plugins: _Tab(),
        "_Other": lambda plugins: _Other(),
    }
    model.get_available_plugins.return_value = {}
    controller = MainController(model, mocker.Mock())
    controller.instantiate_analysis_tab("_Tab")
    controller.instantiate_analysis_tab("_Other")
    return controller


def _tab(main: MainController) -> _Tab:
    tab = main.analysis_tabs["_Tab"]
    assert isinstance(tab, _Tab)
    return tab


def _entry(action: str, *args: Any) -> Dict[str, Any]:
    return {"action": action, "args": list(args), "kwargs": {}}


def _states(main: MainController) -> List[Any]:
    return [c.args for c in main.main_view.set_replay_available.call_args_list]  # type: ignore[attr-defined]


def test_a_tab_says_on_its_page_when_it_has_a_replay_to_continue(
    main: MainController, qtbot: Any
) -> None:
    tab = _tab(main)
    tab.refuse.add("b")

    tab.start_replay([_entry("draw", "a"), _entry("draw", "b"), _entry("draw", "c")])
    qtbot.waitUntil(lambda: not tab.is_replaying())

    assert _states(main) == [("_TabView", False), ("_TabView", True)]


def test_a_replay_that_ends_with_nothing_left_says_so(
    main: MainController, qtbot: Any
) -> None:
    tab = _tab(main)

    tab.start_replay([_entry("draw", "a")])
    qtbot.waitUntil(lambda: not tab.is_replaying())

    assert _states(main) == [("_TabView", False), ("_TabView", False)]


def test_the_click_continues_the_replay_of_the_page_showing(
    main: MainController, qtbot: Any
) -> None:
    tab = _tab(main)
    tab.refuse.add("b")
    tab.start_replay([_entry("draw", "a"), _entry("draw", "b"), _entry("draw", "c")])
    qtbot.waitUntil(lambda: not tab.is_replaying())
    tab.refuse.clear()

    main.replay_tab_actions("_TabView")
    qtbot.waitUntil(lambda: not tab.is_replaying())

    assert tab.calls == ["draw:a", "draw:b", "draw:b", "draw:c"]
    assert main.analysis_tabs["_Other"].calls == []  # type: ignore[attr-defined]


def test_a_click_on_a_page_that_is_no_tab_does_nothing(main: MainController) -> None:
    main.replay_tab_actions("SettingsView")

    assert not _tab(main).is_replaying()


def test_the_click_signal_reaches_the_controller(main: MainController) -> None:
    main.main_view.replay_actions_requested.connect.assert_called_once_with(  # type: ignore[attr-defined]
        main.replay_tab_actions
    )
