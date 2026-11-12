"""
Tests for poriscope.utils.MetaController.MetaController.

Covers:
- export_plot_data (data present, data absent, no filename given)
- load_actions_from_json (a saved plot configuration replays; unreadable, earlier and other-tab files refused)
- relay_add_text_to_display delegation
- handle_kill_worker (valid identifier, invalid format, key missing, channel missing)
- handle_kill_all_workers (matching subclass, non-matching subclass)
- update_available_plugins delegation
- save_tab_actions writes the kept actions as a plot configuration
- update_tab_actions (add history, undo normal, undo empty, undo skips reset_actions)
- _relay_create_plugin emits create_plugin signal
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, override
from unittest.mock import MagicMock

import numpy as np
import pytest
from pytest_mock import MockerFixture

from poriscope.utils.LogDecorator import RESET_ACTION
from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaModel import MetaModel

# ----------------------------- fixtures ------------------------------


@pytest.fixture
def mock_view(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked MetaView with all signals and slots used by MetaController.

    :param mocker: Pytest-mock fixture.
    :return: Mocked meta view.
    """
    view: MagicMock = mocker.Mock()
    for signal in [
        "kill_worker",
        "kill_all_workers",
        "add_text_to_display",
        "save_tab_action_history",
        "update_tab_action_history",
        "cache_plot_data",
        "export_plot_data",
        "load_actions_from_json",
        "create_plugin",
    ]:
        attr = mocker.Mock()
        attr.connect = mocker.Mock()
        setattr(view, signal, attr)
    return view


@pytest.fixture
def mock_model(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked MetaModel with all signals and slots used by MetaController.

    :param mocker: Pytest-mock fixture.
    :return: Mocked meta model.
    """
    model: MagicMock = mocker.Mock()
    for signal in [
        "update_progressbar",
        "add_text_to_display",
    ]:
        attr = mocker.Mock()
        attr.connect = mocker.Mock()
        setattr(model, signal, attr)
    model.workers = {}
    return model


@pytest.fixture
def controller(
    mock_view: MagicMock,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> MetaController:
    """
    Construct a concrete MetaController subclass with view and model replaced by mocks.

    Uses ``__new__`` and manually wires view/model/logger/signals to avoid
    instantiating any real Qt objects.

    :param mock_view: Mocked meta view.
    :param mock_model: Mocked meta model.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """

    # Build a minimal concrete subclass to satisfy the abstract methods.
    class _ConcreteController(MetaController):
        def _init(self) -> None:
            pass

        def _setup_connections(self) -> None:
            pass

    ctrl: _ConcreteController = _ConcreteController.__new__(_ConcreteController)  # type: ignore[type-abstract]
    ctrl.view = mock_view
    ctrl.model = mock_model
    ctrl.logger = mocker.Mock()  # type: ignore[attr-defined]
    ctrl.tab_action_history = OrderedDict()
    # Replay has its own tests (test_action_registry, test_meta_controller_replay); here
    # it is only observed.
    ctrl.replay = mocker.Mock()  # type: ignore[method-assign]
    ctrl.start_replay = mocker.Mock(return_value=True)  # type: ignore[method-assign]
    ctrl.replay_sequence = mocker.Mock()

    # Mock Qt signals on the instance
    for sig in [
        "add_text_to_display",
        "update_tab_action_history",
        "create_plugin",
    ]:
        mock_sig = mocker.Mock()
        mock_sig.emit = mocker.Mock()
        setattr(ctrl, sig, mock_sig)

    return ctrl


# ----------------------- _relay_create_plugin ------------------------


def test_relay_create_plugin_emits_create_plugin_signal(
    controller: MetaController,
) -> None:
    """
    Emit the create_plugin signal with metaclass and subclass strings.

    :param controller: Controller under test.
    """
    controller._relay_create_plugin("MetaReader", "MyReader")
    controller.create_plugin.emit.assert_called_once_with("MetaReader", "MyReader")


# ----------------------- export_plot_data ----------------------------


def test_export_plot_data_saves_csv_when_data_and_filename_present(
    controller: MetaController,
    mock_view: MagicMock,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Retrieve cached data, prompt for a filename, and write a CSV file.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    :param mock_model: Mocked meta model.
    :param mocker: Pytest-mock fixture.
    """
    mock_df = mocker.Mock()
    mock_df.fillna.return_value = mock_df
    mock_model.format_cache_data.return_value = mock_df
    mock_view.get_save_filename.return_value = "output.csv"

    controller.export_plot_data()

    mock_df.to_csv.assert_called_once_with("output.csv", index=False)


def test_export_plot_data_returns_early_when_no_cached_data(
    controller: MetaController,
    mock_model: MagicMock,
    mock_view: MagicMock,
) -> None:
    """
    Return early and log a warning when no cached data is available.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    :param mock_view: Mocked meta view.
    """
    mock_model.format_cache_data.return_value = None

    controller.export_plot_data()

    controller.logger.warning.assert_called_once()  # type: ignore[attr-defined]
    mock_view.get_save_filename.assert_not_called()


def test_export_plot_data_does_not_save_when_no_filename(
    controller: MetaController,
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Do not write a CSV when the user cancels the save dialog.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    :param mock_view: Mocked meta view.
    :param mocker: Pytest-mock fixture.
    """
    mock_df = mocker.Mock()
    mock_model.format_cache_data.return_value = mock_df
    mock_view.get_save_filename.return_value = ""

    controller.export_plot_data()

    mock_df.to_csv.assert_not_called()


# ------------------- load_actions_from_json --------------------------


class _RealModel(MetaModel):
    """A concrete MetaModel, so the plot configuration is read and written for real."""

    @override
    def _init(self) -> None:
        pass


@pytest.fixture
def real_model(controller: MetaController, qapp: Any) -> MetaModel:
    """
    Give the controller a real Model, as the tab has, for the file it reads and writes.

    :param controller: Controller under test.
    :param qapp: pytest-qt's application, which a QObject needs.
    :return: the model now on the controller
    """
    model = _RealModel()
    controller.model = model
    return model


ENTRIES: List[Dict[str, Any]] = [
    {"action": "reset", "args": [], "kwargs": {"axis_type": "2d"}},
    {"action": "overlay_plot", "args": [], "kwargs": {"loader": "DB1"}},
]


def _tab(controller: MetaController) -> str:
    return controller.__class__.__name__


def test_a_saved_plot_configuration_is_replayed(
    controller: MetaController, real_model: MetaModel, tmp_path: Path
) -> None:
    path = str(tmp_path / "plots.json")
    real_model.save_plot_configuration(path, _tab(controller), ENTRIES)

    controller.load_actions_from_json(path)

    controller.start_replay.assert_called_once_with(ENTRIES)  # type: ignore[attr-defined]
    controller.logger.error.assert_not_called()  # type: ignore[attr-defined]


def test_a_file_that_cannot_be_read_replays_nothing(
    controller: MetaController, real_model: MetaModel, tmp_path: Path
) -> None:
    controller.load_actions_from_json(str(tmp_path / "missing.json"))

    controller.start_replay.assert_not_called()  # type: ignore[attr-defined]
    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]
    assert controller.logger.error.call_args[0][0].startswith(  # type: ignore[attr-defined]
        "Error loading plot configuration:"
    )


#: An overlay and its reset as Poriscope 2.0.2's Save Plot Configuration saved them: the
#: View method's name under ``function``, the panel's values in one dict.
_SAVED_BY_2_0 = {
    "0": {"function": "_reset_actions", "args": [], "kwargs": {}},
    "1": {
        "function": "_overlay_plot",
        "args": [{"db_loader": "DB1", "plot_type": "Histogram", "x_axis": "duration"}],
        "kwargs": {},
    },
}

#: The same as develop saved it after actions got declared names, before the overlay's
#: values were saved by name.
_SAVED_BEFORE_NAMED_VALUES = {
    "0": {"action": "reset", "args": [], "kwargs": {"axis_type": "2d"}},
    "1": {
        "action": "overlay_plot",
        "args": [{"db_loader": "DB1", "plot_type": "Histogram"}],
        "kwargs": {},
    },
}

#: As develop saved it once values were named, before the file named its format.
_SAVED_WITHOUT_A_FORMAT = {
    "0": {"action": "reset", "args": [], "kwargs": {"axis_type": "2d"}},
    "1": {"action": "overlay_plot", "args": [], "kwargs": {"loader": "DB1"}},
}


@pytest.mark.parametrize(
    "saved",
    [_SAVED_BY_2_0, _SAVED_BEFORE_NAMED_VALUES, _SAVED_WITHOUT_A_FORMAT, [ENTRIES]],
    ids=["2.0", "before-named-values", "no-format", "a-list"],
)
def test_an_earlier_plot_configuration_is_refused_whole(
    controller: MetaController,
    real_model: MetaModel,
    tmp_path: Path,
    saved: Any,
) -> None:
    """
    Nothing replays, and one error, a dialog, says why and how to keep the plots.

    :param controller: Controller under test.
    :param real_model: the controller's real Model.
    :param tmp_path: pytest's temporary folder.
    :param saved: the file's content
    """
    path = tmp_path / "old.json"
    path.write_text(json.dumps(saved), encoding="utf-8")

    controller.load_actions_from_json(str(path))

    controller.start_replay.assert_not_called()  # type: ignore[attr-defined]
    controller.logger.error.assert_called_once_with(  # type: ignore[attr-defined]
        f"{path} cannot be replayed: it was saved by an earlier version of Poriscope, or "
        "is not a plot configuration. To keep these plots, draw them again and save "
        "them with Save Plot Configuration."
    )


def test_another_tabs_plot_configuration_is_refused(
    controller: MetaController, real_model: MetaModel, tmp_path: Path
) -> None:
    path = str(tmp_path / "protein.json")
    real_model.save_plot_configuration(path, "ProteinController", ENTRIES)

    controller.load_actions_from_json(path)

    controller.start_replay.assert_not_called()  # type: ignore[attr-defined]
    controller.logger.error.assert_called_once_with(  # type: ignore[attr-defined]
        f"{path} cannot be replayed: it holds the plot configuration of "
        "ProteinController."
    )


# ----------------- relay_add_text_to_display -------------------------


def test_relay_add_text_to_display_emits_signal(
    controller: MetaController,
) -> None:
    """
    Re-emit text and source via the add_text_to_display signal.

    :param controller: Controller under test.
    """
    controller.relay_add_text_to_display("hello", "SomeSource")
    controller.add_text_to_display.emit.assert_called_once_with("hello", "SomeSource")


# -------------------- handle_kill_worker -----------------------------


def test_handle_kill_worker_stops_worker_when_key_and_channel_match(
    controller: MetaController,
    mock_model: MagicMock,
) -> None:
    """
    Stop the correct worker when both key and channel are found in the workers dict.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    """
    mock_model.workers = {"key1": {0: MagicMock()}}

    controller.handle_kill_worker("MyReader", "key1/0")

    mock_model.stop_workers.assert_called_once_with("key1", 0)
    # The success path used to log at INFO only, which is below the default log
    # level, so an abort that worked gave the user no confirmation at all.
    controller.add_text_to_display.emit.assert_called_once()  # type: ignore[attr-defined]
    text, _source = controller.add_text_to_display.emit.call_args[0]  # type: ignore[attr-defined]
    assert "key1" in text


def test_handle_kill_worker_logs_error_on_invalid_identifier_format(
    controller: MetaController,
    mock_model: MagicMock,
) -> None:
    """
    Log an error and return early when the identifier cannot be split into key/channel.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    """
    controller.handle_kill_worker("MyReader", "bad_format")

    # Stays at ERROR: unlike the "nothing running" branches this is a real defect
    # rather than a routine state, so a dialog is warranted.
    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]
    controller.add_text_to_display.emit.assert_called_once()  # type: ignore[attr-defined]
    mock_model.stop_workers.assert_not_called()


def test_handle_kill_worker_reports_to_panel_when_key_missing(
    controller: MetaController,
    mock_model: MagicMock,
) -> None:
    """
    Tell the user nothing is running when the key is not present in the workers dict.

    Reported on the display panel at INFO rather than as a WARNING: a finished run
    is popped out of the workers dict, so pressing kill just after one completes
    reaches this branch routinely and must not raise a modal dialog.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    """
    mock_model.workers = {}

    controller.handle_kill_worker("MyReader", "missing_key/0")

    controller.logger.warning.assert_not_called()  # type: ignore[attr-defined]
    controller.add_text_to_display.emit.assert_called_once()  # type: ignore[attr-defined]
    text, _source = controller.add_text_to_display.emit.call_args[0]  # type: ignore[attr-defined]
    assert "missing_key" in text
    mock_model.stop_workers.assert_not_called()


def test_handle_kill_worker_reports_to_panel_when_channel_missing(
    controller: MetaController,
    mock_model: MagicMock,
) -> None:
    """
    Tell the user nothing is running when the key exists but the channel does not.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    """
    mock_model.workers = {"key1": {1: MagicMock()}}

    controller.handle_kill_worker("MyReader", "key1/99")

    controller.logger.warning.assert_not_called()  # type: ignore[attr-defined]
    controller.add_text_to_display.emit.assert_called_once()  # type: ignore[attr-defined]
    text, _source = controller.add_text_to_display.emit.call_args[0]  # type: ignore[attr-defined]
    assert "99" in text
    mock_model.stop_workers.assert_not_called()


# ------------------- handle_kill_all_workers -------------------------


def test_handle_kill_all_workers_stops_workers_when_subclass_matches(
    controller: MetaController,
    mock_model: MagicMock,
) -> None:
    """
    Stop all workers when the subclass name matches the controller class name.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    """
    controller.handle_kill_all_workers(controller.__class__.__name__)
    mock_model.stop_workers.assert_called_once_with(exiting=False)
    controller.replay_sequence.stop.assert_called_once_with(quitting=False)  # type: ignore[attr-defined]


def test_handle_kill_all_workers_passes_exiting_flag(
    controller: MetaController,
    mock_model: MagicMock,
) -> None:
    """
    Pass the exiting flag through to model.stop_workers.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    """
    controller.handle_kill_all_workers(controller.__class__.__name__, exiting=True)
    mock_model.stop_workers.assert_called_once_with(exiting=True)
    controller.replay_sequence.stop.assert_called_once_with(quitting=True)  # type: ignore[attr-defined]


def test_handle_kill_all_workers_does_nothing_when_subclass_does_not_match(
    controller: MetaController,
    mock_model: MagicMock,
) -> None:
    """
    Do not stop workers when the subclass name does not match.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    """
    controller.handle_kill_all_workers("SomeOtherController")
    mock_model.stop_workers.assert_not_called()
    controller.replay_sequence.stop.assert_not_called()  # type: ignore[attr-defined]


# ------------------- update_available_plugins ------------------------


def test_update_available_plugins_delegates_to_view_and_model(
    controller: MetaController,
    mock_view: MagicMock,
    mock_model: MagicMock,
) -> None:
    """
    Forward the available plugins mapping to both view and model.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    :param mock_model: Mocked meta model.
    """
    plugins = {"MetaReader": ["R1", "R2"]}
    controller.update_available_plugins(plugins)
    mock_view.update_available_plugins.assert_called_once_with(plugins)
    mock_model.update_available_plugins.assert_called_once_with(plugins)


# ----------------------- save_tab_actions ----------------------------


def test_save_tab_actions_writes_the_kept_actions_as_this_tabs_configuration(
    controller: MetaController,
    real_model: MetaModel,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """
    What a restored session would replay is saved, not the live history.

    :param controller: Controller under test.
    :param real_model: the controller's real Model.
    :param tmp_path: pytest's temporary folder.
    :param mocker: Pytest-mock fixture.
    """
    controller.tab_action_history = OrderedDict(
        enumerate(ENTRIES + [{"action": "superseded", "args": [], "kwargs": {}}])
    )
    controller.kept_actions = mocker.Mock(return_value=ENTRIES)  # type: ignore[method-assign]
    path = str(tmp_path / "plots.json")

    controller.save_tab_actions(path)

    assert real_model.read_plot_configuration(path, _tab(controller)) == ENTRIES
    controller.logger.error.assert_not_called()  # type: ignore[attr-defined]


def test_a_failed_save_says_so_and_leaves_the_earlier_file(
    controller: MetaController,
    real_model: MetaModel,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    path = str(tmp_path / "plots.json")
    real_model.save_plot_configuration(path, _tab(controller), ENTRIES)
    before = Path(path).read_text()
    controller.kept_actions = mocker.Mock(  # type: ignore[method-assign]
        return_value=[{"action": "x", "args": [], "kwargs": {"bad": object()}}]
    )

    controller.save_tab_actions(path)

    assert Path(path).read_text() == before
    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]
    assert controller.logger.error.call_args[0][0].startswith(  # type: ignore[attr-defined]
        f"Unable to save the plot configuration to {path}:"
    )


# ---------------------- update_tab_actions ---------------------------


def test_update_tab_actions_adds_history_entry(
    controller: MetaController,
) -> None:
    """
    Append a new history entry and emit the updated history.

    :param controller: Controller under test.
    """
    controller.tab_action_history = OrderedDict()
    history = {"action": "do_something"}
    controller.update_tab_actions(history=history)
    assert controller.tab_action_history[0] == history
    controller.update_tab_action_history.emit.assert_called_once()


def test_update_tab_actions_does_not_add_empty_history(
    controller: MetaController,
) -> None:
    """
    Do not append anything when the history dict is empty or None.

    :param controller: Controller under test.
    """
    controller.tab_action_history = OrderedDict()
    controller.update_tab_actions(history=None)
    assert len(controller.tab_action_history) == 0


def test_discarding_drops_the_last_action_without_replaying(
    controller: MetaController,
    mock_view: MagicMock,
) -> None:
    """
    A discarded action leaves the rest of the history, and the figure, alone.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    """
    controller.tab_action_history = OrderedDict(
        {0: {"action": "step1"}, 1: {"action": "step2"}}
    )

    controller.discard_last_tab_action()

    assert controller.tab_action_history == OrderedDict({0: {"action": "step1"}})
    controller.replay.assert_not_called()
    controller.update_tab_action_history.emit.assert_called_once()


def test_discarding_from_an_empty_history_does_nothing(
    controller: MetaController,
) -> None:
    """
    Nothing to drop is not an error.

    :param controller: Controller under test.
    """
    controller.tab_action_history = OrderedDict()

    controller.discard_last_tab_action()

    controller.update_tab_action_history.emit.assert_not_called()


def test_undo_replays_from_the_last_reset_and_keeps_the_rest(
    controller: MetaController,
    mock_view: MagicMock,
) -> None:
    """
    Only what the last reset left on the figure is redrawn; the earlier history stays.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    """
    controller.tab_action_history = OrderedDict(
        {
            0: {"action": "plot_a"},
            1: {"action": RESET_ACTION},
            2: {"action": "plot_b"},
            3: {"action": "plot_c"},
        }
    )

    controller.update_tab_actions(undo=True)

    replayed = controller.replay.call_args[0][0]  # type: ignore[attr-defined]
    assert [entry["action"] for entry in replayed] == [
        RESET_ACTION,
        "plot_b",
    ]
    assert controller.tab_action_history == OrderedDict({0: {"action": "plot_a"}})


@pytest.mark.parametrize(
    "history, expected",
    [
        ([RESET_ACTION, "plot_a"], [RESET_ACTION]),
        (["plot_a", RESET_ACTION, "plot_b"], [RESET_ACTION, "plot_a"]),
    ],
    ids=["the only plot", "an old history with no reset before its first plot"],
)
def test_undo_with_no_reset_left_replays_the_one_it_removed(
    controller: MetaController, history: List[str], expected: List[str]
) -> None:
    """
    The reset an undone plot started its figure with is replayed first, or the figure
    would keep the plot that was undone.

    :param controller: Controller under test.
    :param history: the recorded action names, oldest first
    :param expected: the action names replayed
    """
    controller.tab_action_history = OrderedDict(
        (i, {"action": name}) for i, name in enumerate(history)
    )

    controller.update_tab_actions(undo=True)

    replayed = controller.replay.call_args[0][0]  # type: ignore[attr-defined]
    assert [entry["action"] for entry in replayed] == expected


def test_undo_after_a_reset_replays_no_extra_reset(controller: MetaController) -> None:
    """
    Undoing a Reset brings back what it cleared, from the reset before it.

    :param controller: Controller under test.
    """
    controller.tab_action_history = OrderedDict(
        (i, {"action": name})
        for i, name in enumerate([RESET_ACTION, "plot_a", RESET_ACTION])
    )

    controller.update_tab_actions(undo=True)

    replayed = controller.replay.call_args[0][0]  # type: ignore[attr-defined]
    assert [entry["action"] for entry in replayed] == [RESET_ACTION, "plot_a"]


def test_update_tab_actions_undo_on_empty_history_returns_early(
    controller: MetaController,
) -> None:
    """
    Return early without error when undo is called on an empty history.

    :param controller: Controller under test.
    """
    controller.tab_action_history = OrderedDict()
    controller.update_tab_actions(undo=True)
    # No exception raised and signal still emitted
    controller.update_tab_action_history.emit.assert_not_called()


# -------- update_tab_actions StopIteration branch ---------------------


def test_update_tab_actions_undo_handles_stopiteration_after_first_popitem(
    controller: MetaController,
    mock_view: MagicMock,
) -> None:
    """
    Hit the StopIteration branch when the history is empty after the first popitem.

    After popping the only remaining entry, next(reversed(...)) raises
    StopIteration which is caught by the outer ``except StopIteration: pass``
    block.  The method should still call replay.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    """
    controller.tab_action_history = OrderedDict({0: {"action": "step1"}})

    controller.update_tab_actions(undo=True)

    # History is now empty — view should still receive the empty history
    controller.replay.assert_called_once()
    controller.update_tab_action_history.emit.assert_called_once()


# ----------- __init__ kwargs setattr branch --------------------------


def test_init_kwargs_are_set_as_instance_attributes(
    mock_view: MagicMock,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Verify that kwargs passed to __init__ are stored as instance attributes.

    Covers the ``setattr(self, k, v)`` line inside the kwargs loop in
    MetaController.__init__.

    :param mock_view: Mocked meta view.
    :param mock_model: Mocked meta model.
    :param mocker: Pytest-mock fixture.
    """

    class _ConcreteController(MetaController):
        def _init(self) -> None:
            self.view = mock_view
            self.model = mock_model

        def _setup_connections(self) -> None:
            pass

    # Patch all Qt signal connections so __init__ completes without real Qt
    mock_view.set_available_subclasses = mocker.Mock()
    mock_view.kill_worker.connect = mocker.Mock()
    mock_view.kill_all_workers.connect = mocker.Mock()
    mock_view.add_text_to_display.connect = mocker.Mock()
    mock_view.save_tab_action_history.connect = mocker.Mock()
    mock_view.update_tab_action_history.connect = mocker.Mock()
    mock_view.cache_plot_data.connect = mocker.Mock()
    mock_view.export_plot_data.connect = mocker.Mock()
    mock_view.load_actions_from_json.connect = mocker.Mock()
    mock_view.create_plugin.connect = mocker.Mock()
    mock_model.update_progressbar.connect = mocker.Mock()
    mock_model.add_text_to_display.connect = mocker.Mock()
    mock_model.run_generators = mocker.Mock()
    mock_model.update_progressbar = mocker.Mock()

    ctrl = _ConcreteController(
        available_subclasses=None,
        my_custom_attr="hello",
        another_attr=42,
    )

    assert ctrl.my_custom_attr == "hello"
    assert ctrl.another_attr == 42


class _RealCacheModel(MetaModel):
    """A concrete MetaModel, so the export below runs the real formatting."""

    @override
    def _init(self) -> None:
        pass


def test_export_plot_data_writes_every_dataset_of_an_overlay(
    controller: MetaController,
    mock_view: MagicMock,
    tmp_path: Path,
) -> None:
    """
    Write a file holding both datasets when two are cached under the same labels.

    The tests above replace the model with a mock, so the formatting between the
    cache and the file never ran in them. This one keeps the real model and the real
    slot and reads the file back, which is the path a user's export takes.

    :param controller: Controller under test, with its model replaced below.
    :param mock_view: Mocked meta view that supplies the save location.
    :param tmp_path: Per-test scratch directory.
    """
    model = _RealCacheModel()
    model.cache_data = [
        np.array([1.0, 2.0]),
        np.array([3.0, 4.0]),
        np.array([5.0, 6.0, 7.0]),
        np.array([8.0, 9.0, 1.0]),
    ]
    model.cache_labels = ["duration (us)", "num_sublevels"] * 2
    controller.model = model
    target = tmp_path / "plot.csv"
    mock_view.get_save_filename.return_value = str(target)

    controller.export_plot_data()

    assert target.read_text().splitlines() == [
        "duration (us),num_sublevels,duration (us),num_sublevels",
        "1.0,3.0,5.0,8.0",
        "2.0,4.0,6.0,9.0",
        ",,7.0,1.0",
    ]


# ------------- the Reset button sets the history aside -------------


def _names(entries: Any) -> List[str]:
    return [entry["action"] for entry in entries]


def _history(*names: str) -> "OrderedDict[int, Dict[str, Any]]":
    return OrderedDict((i, {"action": name}) for i, name in enumerate(names))


def test_setting_the_history_aside_empties_it_and_says_so(
    controller: MetaController,
) -> None:
    """
    :param controller: Controller under test.
    """
    controller.tab_action_history = _history(RESET_ACTION, "plot_a")

    controller.set_history_aside()

    assert controller.tab_action_history == OrderedDict()
    controller.update_tab_action_history.emit.assert_called_once_with(  # type: ignore[attr-defined]
        type(controller).__name__, OrderedDict()
    )


def test_undo_straight_after_brings_back_what_was_set_aside_once(
    controller: MetaController,
) -> None:
    """
    :param controller: Controller under test.
    """
    controller.tab_action_history = _history(RESET_ACTION, "plot_a", "plot_b")
    controller.set_history_aside()

    controller.update_tab_actions(undo=True)
    controller.update_tab_actions(undo=True)

    assert controller.replay.call_count == 1  # type: ignore[attr-defined]
    replayed = controller.replay.call_args[0][0]  # type: ignore[attr-defined]
    assert _names(replayed) == [RESET_ACTION, "plot_a", "plot_b"]


def test_recording_after_the_reset_drops_what_was_set_aside(
    controller: MetaController,
) -> None:
    """
    :param controller: Controller under test.
    """
    controller.tab_action_history = _history(RESET_ACTION, "plot_a")
    controller.set_history_aside()

    controller.update_tab_actions({"action": "plot_b"})
    controller.update_tab_actions(undo=True)
    controller.update_tab_actions(undo=True)

    for call in controller.replay.call_args_list:  # type: ignore[attr-defined]
        assert "plot_a" not in _names(call[0][0])


def test_a_reset_of_an_empty_history_keeps_what_an_earlier_one_set_aside(
    controller: MetaController,
) -> None:
    """
    :param controller: Controller under test.
    """
    controller.tab_action_history = _history(RESET_ACTION, "plot_a")
    controller.set_history_aside()
    controller.set_history_aside()

    controller.update_tab_actions(undo=True)

    replayed = controller.replay.call_args[0][0]  # type: ignore[attr-defined]
    assert _names(replayed) == [RESET_ACTION, "plot_a"]


def test_a_refused_plot_after_the_reset_keeps_what_was_set_aside(
    controller: MetaController,
) -> None:
    """
    A refused plot is recorded and then discarded, so nothing was kept after the Reset.

    :param controller: Controller under test.
    """
    controller.tab_action_history = _history(RESET_ACTION, "plot_a")
    controller.set_history_aside()

    controller.update_tab_actions({"action": "plot_b"})
    controller.discard_last_tab_action()
    controller.update_tab_actions(undo=True)

    replayed = controller.replay.call_args[0][0]  # type: ignore[attr-defined]
    assert _names(replayed) == [RESET_ACTION, "plot_a"]


def test_the_first_entry_kept_after_the_reset_says_the_clear_is_final(
    controller: MetaController,
) -> None:
    """
    :param controller: Controller under test.
    """
    controller.tab_action_history = _history(RESET_ACTION, "plot_a")
    controller.set_history_aside()

    controller.update_tab_actions({"action": "plot_b"})
    controller.update_tab_actions({"action": "plot_c"})

    controller.add_text_to_display.emit.assert_called_once_with(  # type: ignore[attr-defined]
        "Reset: plot and history cleared", type(controller).__name__
    )


def test_an_entry_with_nothing_set_aside_says_nothing(
    controller: MetaController,
) -> None:
    """
    :param controller: Controller under test.
    """
    controller.update_tab_actions({"action": "plot_a"})

    controller.add_text_to_display.emit.assert_not_called()  # type: ignore[attr-defined]


def test_a_refused_plot_after_the_reset_says_undo_still_brings_it_back(
    controller: MetaController,
) -> None:
    """
    :param controller: Controller under test.
    """
    controller.tab_action_history = _history(RESET_ACTION, "plot_a")
    controller.set_history_aside()

    controller.update_tab_actions({"action": "plot_b"})
    controller.discard_last_tab_action()

    said = [c.args[0] for c in controller.add_text_to_display.emit.call_args_list]  # type: ignore[attr-defined]
    assert said == [
        "Reset: plot and history cleared",
        "Reset: Undo now will bring it back",
    ]
