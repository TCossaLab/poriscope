"""
A replaying tab's status-panel lines are held back, then shown together when it ends.

Every line a tab sends to the panel reaches one ``MainController`` method, bound to that
tab, which asks the tab what to show. While the tab replays it shows nothing; the first
line once the replay has ended - "replay done", "replay stopped" or the failure - brings the
held lines with it, in order. The tab's own signal still carries every line as it happens.
Real tabs, wired by ``MainController.instantiate_analysis_tab``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, Signal
from pytest_mock import MockerFixture

from poriscope.controllers.main_controller import MainController
from poriscope.utils.LogDecorator import register_action
from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaModel import PLOT_CONFIGURATION_FORMAT, MetaModel


def _plot_configuration(tab: str, entries: List[Dict[str, Any]]) -> str:
    """A plot configuration file's text, as Save Plot Configuration writes it."""
    return json.dumps(
        {
            "format": PLOT_CONFIGURATION_FORMAT,
            "format_version": 1,
            "poriscope_version": "2.1.0",
            "tab": tab,
            "actions": entries,
        }
    )


class _Model(QObject):
    run_finished = Signal(int, str)
    update_progressbar = Signal(float, str)
    add_text_to_display = Signal(str, str)

    #: The real reader, so a loaded file is checked as the tab's Model checks it.
    read_plot_configuration = MetaModel.read_plot_configuration

    def __init__(self) -> None:
        super().__init__()
        self.thread_running: Dict[str, Dict[int, bool]] = {}
        self.reporter_metaclasses = {"A": "MetaEventFinder"}
        self.cache_plot_data = MagicMock()
        self.stop_workers = MagicMock()
        self.set_plugin_instances = MagicMock()
        self.update_available_plugins = MagicMock()

    def call(self, metaclass: str, key: str, method: str, *args: Any) -> Any:
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
        self.add_text_to_display.emit(f"drew {label}", self.__class__.__name__)
        return True

    @register_action(
        "find", kind="result", key=("finder", "channel"), skip_on_false=True
    )
    def find(self, finder: str, channel: int) -> bool:
        self.calls.append(f"find:{finder}/{channel}")
        self.model.add_text_to_display.emit(f"Ch{channel}: searching", finder)
        return True


class _Other(_Tab):
    pass


@pytest.fixture
def main(qtbot: Any, mocker: MockerFixture) -> Iterator[MainController]:
    """
    A MainController over a mock window, whose plugin classes are the two test tabs.

    :param qtbot: pytest-qt fixture, for the application the timers run on
    :param mocker: pytest-mock fixture
    :return: the controller, with both tabs open; a replay still waiting on a run at the
        end of the test is stopped, as quitting does, so it collects no later test's errors
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
    yield controller
    for tab in controller.analysis_tabs.values():
        tab.replay_sequence.stop(quitting=True)


def _shown(main: MainController) -> List[str]:
    return [call.args[0] for call in main.main_view.add_text_to_display.call_args_list]  # type: ignore[attr-defined]


def _entry(action: str, *args: Any) -> Dict[str, Any]:
    return {"action": action, "args": list(args), "kwargs": {}}


def _tab(main: MainController, name: str = "_Tab") -> _Tab:
    tab = main.analysis_tabs[name]
    assert isinstance(tab, _Tab)
    return tab


def _replay_up_to_the_find(main: MainController, qtbot: Any) -> _Tab:
    tab = _tab(main)
    tab.start_replay([_entry("draw", "a"), _entry("find", "A", 1), _entry("draw", "b")])
    qtbot.waitUntil(lambda: tab.calls == ["draw:a", "find:A/1"])
    return tab


def test_a_tabs_lines_reach_the_panel_as_they_come_when_it_is_not_replaying(
    main: MainController,
) -> None:
    _tab(main).draw("a")

    assert _shown(main) == ["drew a"]


def test_a_replaying_tabs_lines_are_held_until_it_is_done(
    main: MainController, qtbot: Any
) -> None:
    tab = _replay_up_to_the_find(main, qtbot)

    assert _shown(main) == []

    tab.model.run_finished.emit(1, "A")
    qtbot.waitUntil(lambda: not tab.is_replaying())

    assert _shown(main) == [
        "drew a",
        "Ch1: searching",
        "drew b",
        "replay done",
    ]


def test_the_tabs_own_signal_still_carries_each_line_as_it_happens(
    main: MainController, qtbot: Any
) -> None:
    lines: List[str] = []
    _tab(main).add_text_to_display.connect(lambda text, source: lines.append(text))

    _replay_up_to_the_find(main, qtbot)

    assert lines == ["drew a", "Ch1: searching"]


def test_another_tabs_lines_are_not_held(main: MainController, qtbot: Any) -> None:
    _replay_up_to_the_find(main, qtbot)

    _tab(main, "_Other").draw("x")

    assert _shown(main) == ["drew x"]


def test_a_stopped_replay_shows_its_held_lines_then_says_it_stopped(
    main: MainController, qtbot: Any
) -> None:
    tab = _replay_up_to_the_find(main, qtbot)

    tab.handle_kill_all_workers("_Tab")

    assert _shown(main) == [
        "drew a",
        "Ch1: searching",
        "Stopping all running operations.",
        "replay stopped",
    ]


def test_a_refused_load_is_shown_at_once(
    main: MainController, qtbot: Any, tmp_path: Any
) -> None:
    tab = _replay_up_to_the_find(main, qtbot)
    path = tmp_path / "actions.json"
    path.write_text(
        _plot_configuration(
            tab.__class__.__name__,
            [{"action": "draw", "args": [], "kwargs": {"label": "late"}}],
        ),
        encoding="utf-8",
    )

    tab.load_actions_from_json(str(path))

    assert _shown(main) == [
        "a replay is already running; stop it, or let it finish, first"
    ]
    assert tab.is_replaying()
