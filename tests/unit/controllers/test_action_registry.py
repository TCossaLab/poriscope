"""
Tests for the per-tab action registry, ``record_action`` and ``replay`` on ``MetaController``.

A recorded action is dispatched by its declared name through a registry built from the
decorated methods of the tab's Controller. These tests use a real concrete Controller
carrying decorated methods, so replay is exercised end to end: a recorded entry survives a
JSON round trip and, replayed, records itself again.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.ClusteringController import ClusteringController
from poriscope.plugins.analysistabs.EventAnalysisController import (
    EventAnalysisController,
)
from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.analysistabs.ProteinController import ProteinController
from poriscope.plugins.analysistabs.RawDataController import RawDataController
from poriscope.utils.LogDecorator import (
    RESET_ACTION,
    ActionDeclaration,
    register_action,
)
from poriscope.utils.MetaController import MetaController, declarations_of
from poriscope.utils.MetaView import MetaView
from poriscope.utils.ReplayGuard import ReplayWidgetReadError, forbid_while_replaying


class _View:
    """A View-like object with a decorated method, which the registry does not reach."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    @register_action("view_plot", kind="view", figure="plot")
    def view_plot(self, label: str) -> None:
        self.calls.append(f"view:{label}")


class _Controller(MetaController):
    """A concrete Controller with decorated methods, and one without a declaration."""

    def _init(self) -> None:
        pass

    def _setup_connections(self) -> None:
        pass

    @register_action("start_run", kind="view", figure="plot")
    def start_run(self, name: str, repeats: int = 1) -> None:
        self.runs.append((name, repeats))

    @register_action(RESET_ACTION, kind="reset", figure="plot")
    def reset(self, axis_type: str = "2d") -> None:
        self.calls.append(f"reset:{axis_type}")

    @register_action("overlay_plot", kind="view", figure="plot")
    def overlay_plot(self, label: str) -> None:
        self.calls.append(f"overlay:{label}")

    def update_available_columns(self, loader: str) -> None:
        self.calls.append(f"columns:{loader}")


def _make(
    mocker: MockerFixture, view: Any = None, cls: type = _Controller
) -> _Controller:
    """
    Build a Controller without Qt, the way ``test_meta_controller`` does.

    :param mocker: pytest-mock fixture
    :param view: the View to own, a fresh ``_View`` if omitted
    :param cls: the Controller class to build
    :return: the controller, with its signals replaced by mocks
    """
    controller = cls.__new__(cls)  # type: ignore[type-abstract]
    controller.view = view if view is not None else _View()
    controller.model = mocker.Mock()
    controller.logger = mocker.Mock()  # type: ignore[attr-defined]
    controller.tab_action_history = OrderedDict()
    controller.runs = []  # type: ignore[attr-defined]
    controller.calls = []  # type: ignore[attr-defined]
    for signal in ("add_text_to_display", "update_tab_action_history"):
        mock_signal = mocker.Mock()
        mock_signal.emit = mocker.Mock()
        setattr(controller, signal, mock_signal)
    return controller


@pytest.fixture
def controller(mocker: MockerFixture) -> _Controller:
    """
    A Controller with decorated methods, owning a View with a decorated method.

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
    def test_it_holds_every_declared_name_of_the_controller(
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

        assert controller.update_available_columns not in registered

    def test_a_method_declared_on_the_view_is_not_in_it(
        self, controller: _Controller
    ) -> None:
        """Recording and replay are the Controller's; a View holds no recorded action."""
        assert "view_plot" not in controller.action_registry()

    def test_the_view_base_has_no_recording_hook(self) -> None:
        """Without it a decorated View method has nowhere to record into."""
        assert not hasattr(MetaView, "record_action")

    def test_a_name_declared_twice_raises_when_the_registry_is_built(
        self, mocker: MockerFixture
    ) -> None:
        class _Clashing(_Controller):
            @register_action("start_run", kind="view", figure="plot")
            def also_start_run(self) -> None:
                pass

        controller = _make(mocker, cls=_Clashing)

        with pytest.raises(ValueError, match="start_run"):
            controller.action_registry()

    def test_a_subclass_override_wins_over_the_inherited_declaration(
        self, mocker: MockerFixture
    ) -> None:
        class _Overriding(_Controller):
            @register_action("overlay_plot", kind="view", figure="plot")
            def overlay_plot(self, label: str) -> None:
                self.calls.append(f"override:{label}")

        controller = _make(mocker, cls=_Overriding)

        controller.replay([_entry("overlay_plot", "x")])

        assert controller.calls == ["override:x"]  # type: ignore[attr-defined]

    def test_a_mock_view_declares_nothing(self, mocker: MockerFixture) -> None:
        """Existing controller tests give the Controller a bare Mock for a View."""
        controller = _make(mocker, mocker.Mock())

        assert set(controller.action_registry()) == {
            "start_run",
            RESET_ACTION,
            "overlay_plot",
        }


class TestReplay:
    def test_it_calls_a_controller_method_with_the_recorded_arguments(
        self, controller: _Controller
    ) -> None:
        controller.replay([_entry("start_run", "a", repeats=3)])

        assert controller.runs == [("a", 3)]  # type: ignore[attr-defined]

    def test_it_calls_each_declared_method_with_its_recorded_arguments(
        self, controller: _Controller
    ) -> None:
        controller.replay([_entry("overlay_plot", "x"), _entry(RESET_ACTION, "3d")])

        assert controller.calls == ["overlay:x", "reset:3d"]  # type: ignore[attr-defined]

    def test_a_view_method_named_in_a_file_is_reported_not_called(
        self, controller: _Controller
    ) -> None:
        controller.replay([_entry("view_plot", "x")])

        assert controller.view.calls == []  # type: ignore[attr-defined]
        controller.add_text_to_display.emit.assert_called_once()  # type: ignore[attr-defined]

    def test_an_unknown_name_is_reported_and_nothing_is_called(
        self, controller: _Controller
    ) -> None:
        controller.replay([_entry("no_such_action")])

        controller.add_text_to_display.emit.assert_called_once_with(  # type: ignore[attr-defined]
            "Not replayed: 'no_such_action' is not a recorded action of _Controller",
            "_Controller",
        )
        assert controller.calls == []  # type: ignore[attr-defined]

    def test_a_real_method_with_no_declaration_is_reported_not_called(
        self, controller: _Controller
    ) -> None:
        """Replay used to call any method of the View whose name was in the file."""
        controller.replay([_entry("update_available_columns", "loader")])

        assert controller.calls == []  # type: ignore[attr-defined]
        controller.add_text_to_display.emit.assert_called_once()  # type: ignore[attr-defined]

    def test_an_entry_in_the_old_format_is_reported_and_replay_moves_on(
        self, controller: _Controller
    ) -> None:
        old = {"function": "_reset_actions", "args": ["2d"], "kwargs": {}}

        controller.replay([old, _entry("overlay_plot", "x")])

        assert controller.calls == ["overlay:x"]  # type: ignore[attr-defined]
        message = controller.add_text_to_display.emit.call_args[0][0]  # type: ignore[attr-defined]
        assert message.startswith("Not replayed")

    @pytest.mark.parametrize(
        "entry",
        [
            _entry("overlay_plot"),
            _entry("overlay_plot", "x", "an extra value"),
            {"action": "overlay_plot", "args": [], "kwargs": {"colour": "red"}},
        ],
        ids=["a value missing", "a value too many", "a name it does not take"],
    )
    def test_an_entry_whose_values_do_not_fit_its_action_is_reported_and_skipped(
        self, controller: _Controller, entry: Dict[str, Any]
    ) -> None:
        """
        What an entry saved before an action's parameters changed looks like: the name
        is still declared, but its values no longer fit. It is reported like an unknown
        name, and replay goes on, rather than raising and losing the rest.
        """
        controller.replay([entry, _entry("overlay_plot", "y")])

        assert controller.calls == ["overlay:y"]  # type: ignore[attr-defined]
        message = controller.add_text_to_display.emit.call_args[0][0]  # type: ignore[attr-defined]
        assert message.startswith("Not replayed")
        assert "overlay_plot" in message

    def test_an_action_that_raises_a_type_error_itself_is_not_mistaken_for_a_misfit(
        self, controller: _Controller
    ) -> None:
        """Only the values are checked before the call; the action's own errors propagate."""

        def broken(label: str) -> None:
            raise TypeError("inside the action")

        controller.action_registry()["overlay_plot"] = broken

        with pytest.raises(TypeError, match="inside the action"):
            controller.replay([_entry("overlay_plot", "x")])

    def test_entries_run_in_the_order_given(self, controller: _Controller) -> None:
        controller.replay(
            [
                _entry("overlay_plot", "a"),
                _entry(RESET_ACTION),
                _entry("overlay_plot", "b"),
            ]
        )

        assert controller.calls == ["overlay:a", "reset:2d", "overlay:b"]  # type: ignore[attr-defined]

    def test_a_recorded_entry_survives_a_json_round_trip_and_replays(
        self, controller: _Controller
    ) -> None:
        controller.start_run("a", repeats=2)
        controller.overlay_plot("x")
        saved = json.loads(json.dumps(controller.tab_action_history))
        controller.runs.clear()  # type: ignore[attr-defined]
        controller.calls.clear()  # type: ignore[attr-defined]

        controller.replay(saved.values())

        assert controller.runs == [("a", 2)]  # type: ignore[attr-defined]
        assert controller.calls == ["overlay:x"]  # type: ignore[attr-defined]

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

        assert controller.calls == ["reset:2d", "overlay:b"]  # type: ignore[attr-defined]
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

        # No reset is left before the overlay, so the last one removed clears the
        # figure first.
        assert controller.calls == ["reset:2d", "overlay:a"]  # type: ignore[attr-defined]


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
        class _Leaky(_Controller):
            @register_action("leaky", kind="view", figure="plot")
            def leaky(self) -> None:
                forbid_while_replaying("a widget read")

        controller = _make(mocker, cls=_Leaky)

        with pytest.raises(ReplayWidgetReadError):
            controller.replay([_entry("leaky")])

    def test_the_same_read_is_fine_when_the_user_clicks(
        self, mocker: MockerFixture
    ) -> None:
        class _Leaky(_Controller):
            @register_action("leaky", kind="view", figure="plot")
            def leaky(self) -> None:
                forbid_while_replaying("a widget read")

        controller = _make(mocker, cls=_Leaky)

        controller.leaky()  # type: ignore[attr-defined]  # as a click calls it, outside any replay

    def test_the_tripwire_is_off_again_once_the_replay_ends(
        self, mocker: MockerFixture
    ) -> None:
        controller = _make(mocker)
        controller.replay([_entry("start_run", "a")])

        forbid_while_replaying("after the replay")


def _view(name: str, figure: str, *depends_on: str) -> ActionDeclaration:
    return ActionDeclaration(
        name, "view", figure=figure, depends_on=depends_on, skip_on_false=True
    )


def _additive(name: str, figure: str, skip_on_false: bool = True) -> ActionDeclaration:
    return ActionDeclaration(
        name, "additive", figure=figure, skip_on_false=skip_on_false
    )


@pytest.mark.parametrize(
    "controller_class, expected",
    [
        (
            RawDataController,
            [
                ActionDeclaration(
                    "find_events",
                    "result",
                    key=("eventfinder", "channel"),
                    skip_on_false=True,
                ),
                _view("update_trace", "plot"),
                _view("update_psd", "plot"),
                _view("plot_events", "plot", "eventfinder", "channel"),
            ],
        ),
        (
            EventAnalysisController,
            [
                ActionDeclaration(
                    "fit_events",
                    "result",
                    key=("eventfitter", "channel"),
                    skip_on_false=True,
                ),
                _view("plot_events", "plot", "eventfitter", "channel"),
            ],
        ),
        (
            ClusteringController,
            [
                ActionDeclaration(RESET_ACTION, "reset", figure="clusters"),
                _additive("cluster_run", "clusters"),
                _additive("merge_clusters", "clusters"),
            ],
        ),
        (
            MetadataController,
            [
                ActionDeclaration(RESET_ACTION, "reset", figure="plot"),
                _additive("overlay_plot", "plot", skip_on_false=False),
                _view("plot_events", "plot"),
            ],
        ),
        (
            ProteinController,
            [
                ActionDeclaration(RESET_ACTION, "reset", figure_from="mode"),
                _additive("update_individual_distribution", "individual"),
                _additive("update_ensemble_distribution", "ensemble"),
                _view("plot_events", "events"),
                _view("plot_event_histograms", "events"),
            ],
        ),
    ],
    ids=lambda value: value.__name__ if isinstance(value, type) else "",
)
def test_each_tab_declares_what_a_restore_keeps_of_its_actions(
    controller_class: type, expected: List[ActionDeclaration]
) -> None:
    """
    A result is replaced per plugin and channel and a view per figure; the drawings a
    reset clears share its figure, and Protein's reset names the mode's figure.
    """
    assert declarations_of(controller_class) == {
        declaration.name: declaration for declaration in expected
    }
