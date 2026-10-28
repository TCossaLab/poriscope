"""
Tests for the per-tab action registry, ``record_action`` and ``replay`` on ``MetaController``.

A recorded action is dispatched by its declared name through a registry built from the
decorated methods of the tab's Controller and, during the transition, its View. These
tests use a real concrete Controller and a real View-like object carrying decorated
methods, wired the way the app wires them, so replay is exercised end to end: a recorded
entry survives a JSON round trip and, replayed, records itself again.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.utils.LogDecorator import RESET_ACTION, register_action
from poriscope.utils.MetaController import MetaController
from poriscope.utils.ReplayGuard import ReplayWidgetReadError, forbid_while_replaying


class _View:
    """A View-like object: decorated methods, and the transitional ``record_action``."""

    def __init__(self) -> None:
        self.calls: List[str] = []
        self.recorded_into: Any = None

    def record_action(self, entry: Dict[str, Any]) -> None:
        self.recorded_into.update_tab_actions(entry, False)

    @register_action(RESET_ACTION)
    def _reset_actions(self, axis_type: str = "2d") -> None:
        self.calls.append(f"reset:{axis_type}")

    @register_action("overlay_plot")
    def overlay_plot(self, label: str) -> None:
        self.calls.append(f"overlay:{label}")

    def update_available_columns(self, loader: str) -> None:
        self.calls.append(f"columns:{loader}")


class _Controller(MetaController):
    """A concrete Controller with one decorated method of its own."""

    def _init(self) -> None:
        pass

    def _setup_connections(self) -> None:
        pass

    @register_action("start_run")
    def start_run(self, name: str, repeats: int = 1) -> None:
        self.runs.append((name, repeats))


def _make(mocker: MockerFixture, view: Any = None) -> _Controller:
    """
    Build a Controller without Qt, the way ``test_meta_controller`` does.

    :param mocker: pytest-mock fixture
    :param view: the View to own, a fresh ``_View`` if omitted
    :return: the controller, with its signals replaced by mocks
    """
    controller = _Controller.__new__(_Controller)  # type: ignore[type-abstract]
    controller.view = view if view is not None else _View()
    controller.model = mocker.Mock()
    controller.logger = mocker.Mock()  # type: ignore[attr-defined]
    controller.tab_action_history = OrderedDict()
    controller.runs = []  # type: ignore[attr-defined]
    for signal in ("add_text_to_display", "update_tab_action_history"):
        mock_signal = mocker.Mock()
        mock_signal.emit = mocker.Mock()
        setattr(controller, signal, mock_signal)
    if isinstance(controller.view, _View):
        controller.view.recorded_into = controller
    return controller


@pytest.fixture
def controller(mocker: MockerFixture) -> _Controller:
    """
    A Controller with decorated methods, owning a View with decorated methods.

    :param mocker: pytest-mock fixture
    :return: the controller
    """
    return _make(mocker)


def _entry(action: Any, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    return {"action": action, "args": list(args), "kwargs": kwargs}


class TestRecordAction:
    def test_record_action_appends_and_notifies_the_main_window(
        self, controller: _Controller
    ) -> None:
        controller.record_action(_entry("start_run", "a"))

        assert controller.tab_action_history[0] == _entry("start_run", "a")
        controller.update_tab_action_history.emit.assert_called_once_with(  # type: ignore[attr-defined]
            "_Controller", controller.tab_action_history
        )

    def test_a_decorated_controller_method_records_itself(
        self, controller: _Controller
    ) -> None:
        controller.start_run("a", repeats=2)

        assert list(controller.tab_action_history.values()) == [
            {"action": "start_run", "args": (), "kwargs": {"name": "a", "repeats": 2}}
        ]


class TestRegistry:
    def test_it_holds_every_declared_name_of_the_controller_and_its_view(
        self, controller: _Controller
    ) -> None:
        assert set(controller.action_registry()) == {
            "start_run",
            RESET_ACTION,
            "overlay_plot",
        }

    def test_a_method_without_a_declaration_is_not_in_it(
        self, controller: _Controller
    ) -> None:
        registered = controller.action_registry().values()

        assert controller.view.update_available_columns not in registered  # type: ignore[attr-defined]

    def test_a_name_declared_twice_raises_when_the_registry_is_built(
        self, mocker: MockerFixture
    ) -> None:
        class _Clashing(_View):
            @register_action("start_run")
            def also_start_run(self) -> None:
                pass

        controller = _make(mocker, _Clashing())

        with pytest.raises(ValueError, match="start_run"):
            controller.action_registry()

    def test_a_subclass_override_wins_over_the_inherited_declaration(
        self, mocker: MockerFixture
    ) -> None:
        class _Overriding(_View):
            @register_action("overlay_plot")
            def overlay_plot(self, label: str) -> None:
                self.calls.append(f"override:{label}")

        view = _Overriding()
        controller = _make(mocker, view)

        controller.replay([_entry("overlay_plot", "x")])

        assert view.calls == ["override:x"]

    def test_a_mock_view_declares_nothing(self, mocker: MockerFixture) -> None:
        """Existing controller tests give the Controller a bare Mock for a View."""
        controller = _make(mocker, mocker.Mock())

        assert set(controller.action_registry()) == {"start_run"}


class TestReplay:
    def test_it_calls_a_controller_method_with_the_recorded_arguments(
        self, controller: _Controller
    ) -> None:
        controller.replay([_entry("start_run", "a", repeats=3)])

        assert controller.runs == [("a", 3)]  # type: ignore[attr-defined]

    def test_it_calls_a_view_method_with_the_recorded_arguments(
        self, controller: _Controller
    ) -> None:
        controller.replay([_entry("overlay_plot", "x"), _entry(RESET_ACTION, "3d")])

        assert controller.view.calls == ["overlay:x", "reset:3d"]  # type: ignore[attr-defined]

    def test_an_unknown_name_is_reported_and_nothing_is_called(
        self, controller: _Controller
    ) -> None:
        controller.replay([_entry("no_such_action")])

        controller.add_text_to_display.emit.assert_called_once_with(  # type: ignore[attr-defined]
            "Not replayed: 'no_such_action' is not a recorded action of _Controller",
            "_Controller",
        )
        assert controller.view.calls == []  # type: ignore[attr-defined]

    def test_a_real_method_with_no_declaration_is_reported_not_called(
        self, controller: _Controller
    ) -> None:
        """Replay used to call any method of the View whose name was in the file."""
        controller.replay([_entry("update_available_columns", "loader")])

        assert controller.view.calls == []  # type: ignore[attr-defined]
        controller.add_text_to_display.emit.assert_called_once()  # type: ignore[attr-defined]

    def test_an_entry_in_the_old_format_is_reported_and_replay_moves_on(
        self, controller: _Controller
    ) -> None:
        old = {"function": "_reset_actions", "args": ["2d"], "kwargs": {}}

        controller.replay([old, _entry("overlay_plot", "x")])

        assert controller.view.calls == ["overlay:x"]  # type: ignore[attr-defined]
        message = controller.add_text_to_display.emit.call_args[0][0]  # type: ignore[attr-defined]
        assert message.startswith("Not replayed")

    def test_entries_run_in_the_order_given(self, controller: _Controller) -> None:
        controller.replay(
            [
                _entry("overlay_plot", "a"),
                _entry(RESET_ACTION),
                _entry("overlay_plot", "b"),
            ]
        )

        assert controller.view.calls == ["overlay:a", "reset:2d", "overlay:b"]  # type: ignore[attr-defined]

    def test_a_recorded_entry_survives_a_json_round_trip_and_replays(
        self, controller: _Controller
    ) -> None:
        controller.start_run("a", repeats=2)
        controller.view.overlay_plot("x")  # type: ignore[attr-defined]
        saved = json.loads(json.dumps(controller.tab_action_history))
        controller.runs.clear()  # type: ignore[attr-defined]
        controller.view.calls.clear()  # type: ignore[attr-defined]

        controller.replay(saved.values())

        assert controller.runs == [("a", 2)]  # type: ignore[attr-defined]
        assert controller.view.calls == ["overlay:x"]  # type: ignore[attr-defined]

    def test_replay_records_each_action_again(self, controller: _Controller) -> None:
        """Undo relies on this: it replays from the history and the history regrows."""
        controller.replay([_entry("start_run", "a"), _entry("overlay_plot", "x")])

        assert [e["action"] for e in controller.tab_action_history.values()] == [
            "start_run",
            "overlay_plot",
        ]


class TestUndoUsesTheDeclaredResetName:
    def test_undo_replays_from_the_last_reset_and_keeps_the_rest(
        self, controller: _Controller
    ) -> None:
        controller.tab_action_history = OrderedDict(
            {
                0: _entry("overlay_plot", "a"),
                1: _entry(RESET_ACTION),
                2: _entry("overlay_plot", "b"),
                3: _entry("overlay_plot", "c"),
            }
        )

        controller.update_tab_actions(undo=True)

        assert controller.view.calls == ["reset:2d", "overlay:b"]  # type: ignore[attr-defined]
        assert [e["action"] for e in controller.tab_action_history.values()] == [
            "overlay_plot",
            RESET_ACTION,
            "overlay_plot",
        ]

    def test_undo_drops_trailing_resets_with_the_entry_it_removes(
        self, controller: _Controller
    ) -> None:
        controller.tab_action_history = OrderedDict(
            {
                0: _entry("overlay_plot", "a"),
                1: _entry(RESET_ACTION),
                2: _entry(RESET_ACTION),
            }
        )

        controller.update_tab_actions(undo=True)

        assert controller.view.calls == ["overlay:a"]  # type: ignore[attr-defined]


class TestLoadActionsFromJson:
    def test_a_loaded_file_is_replayed_through_the_controller(
        self, controller: _Controller, tmp_path: Any
    ) -> None:
        path = tmp_path / "actions.json"
        path.write_text(json.dumps({"0": _entry("start_run", "a")}), encoding="utf-8")

        controller.load_actions_from_json(str(path))

        assert controller.runs == [("a", 1)]  # type: ignore[attr-defined]

    def test_a_file_keyed_by_the_class_name_is_unwrapped(
        self, controller: _Controller, tmp_path: Any
    ) -> None:
        path = tmp_path / "actions.json"
        path.write_text(
            json.dumps({"_Controller": {"0": _entry("start_run", "b")}}),
            encoding="utf-8",
        )

        controller.load_actions_from_json(str(path))

        assert controller.runs == [("b", 1)]  # type: ignore[attr-defined]


def test_a_mock_view_does_not_break_replay(mocker: MockerFixture) -> None:
    view: MagicMock = mocker.Mock()
    controller = _make(mocker, view)

    controller.replay([_entry("start_run", "a")])

    assert controller.runs == [("a", 1)]  # type: ignore[attr-defined]


class TestReplayRunsInsideTheTripwire:
    """A recorded action that reads a widget fails during a replay, and only then."""

    def test_a_widget_read_inside_a_replayed_action_raises(
        self, mocker: MockerFixture
    ) -> None:
        class _Leaky(_View):
            @register_action("leaky")
            def leaky(self) -> None:
                forbid_while_replaying("a widget read")

        controller = _make(mocker, _Leaky())

        with pytest.raises(ReplayWidgetReadError):
            controller.replay([_entry("leaky")])

    def test_the_same_read_is_fine_when_the_user_clicks(
        self, mocker: MockerFixture
    ) -> None:
        class _Leaky(_View):
            @register_action("leaky")
            def leaky(self) -> None:
                forbid_while_replaying("a widget read")

        view = _Leaky()
        _make(mocker, view)

        view.leaky()  # called as a click calls it, outside any replay

    def test_the_tripwire_is_off_again_once_the_replay_ends(
        self, mocker: MockerFixture
    ) -> None:
        controller = _make(mocker)
        controller.replay([_entry("start_run", "a")])

        forbid_while_replaying("after the replay")
