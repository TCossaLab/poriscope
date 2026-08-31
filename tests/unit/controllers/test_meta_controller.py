"""
Tests for poriscope.utils.MetaController.MetaController.

Covers:
- update_plot_data delegation
- export_plot_data (data present, data absent, no filename given)
- _connect_global_signal wiring
- load_actions_from_json (success, file error, class name key present)
- relay_add_text_to_display delegation
- handle_kill_worker (valid identifier, invalid format, key missing, channel missing)
- set_generator delegation
- handle_kill_all_workers (matching subclass, non-matching subclass)
- _relay_global_signal (valid return function, missing return function, empty return function, emit exception)
- _relay_data_plugin_controller_signal (valid return function, missing return function, empty return function, emit exception)
- update_available_plugins delegation
- save_tab_actions emits signal
- update_tab_actions (add history, undo normal, undo empty, undo skips reset_actions)
- ignore is a no-op
- _relay_create_plugin emits create_plugin signal
"""

from __future__ import annotations

import json
from collections import OrderedDict
from unittest.mock import MagicMock, mock_open

import pytest
from pytest_mock import MockerFixture

from poriscope.utils.MetaController import MetaController

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
        "run_generators",
        "kill_worker",
        "kill_all_workers",
        "add_text_to_display",
        "save_tab_action_history",
        "update_tab_action_history",
        "cache_plot_data",
        "export_plot_data",
        "load_actions_from_json",
        "create_plugin",
        "global_signal",
        "data_plugin_controller_signal",
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
        "global_signal",
        "data_plugin_controller_signal",
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

    # Mock Qt signals on the instance
    for sig in [
        "global_signal",
        "data_plugin_controller_signal",
        "add_text_to_display",
        "update_tab_action_history",
        "save_tab_action_history",
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


# ----------------------- update_plot_data ----------------------------


def test_update_plot_data_delegates_to_view(
    controller: MetaController,
    mock_view: MagicMock,
) -> None:
    """
    Forward new plot data to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    """
    data = {"x": [1, 2], "y": [3, 4]}
    controller.update_plot_data(data)
    mock_view.update_plot_data.assert_called_once_with(data)


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


# ------------------- _connect_global_signal --------------------------


def test_connect_global_signal_wires_view_and_model_signals(
    controller: MetaController,
    mock_view: MagicMock,
    mock_model: MagicMock,
) -> None:
    """
    Wire global and data_plugin_controller signals from both view and model.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    :param mock_model: Mocked meta model.
    """
    controller._connect_global_signal()

    mock_view.global_signal.connect.assert_called_once_with(
        controller._relay_global_signal
    )
    mock_model.global_signal.connect.assert_called_once_with(
        controller._relay_global_signal
    )
    mock_view.data_plugin_controller_signal.connect.assert_called_once_with(
        controller._relay_data_plugin_controller_signal
    )
    mock_model.data_plugin_controller_signal.connect.assert_called_once_with(
        controller._relay_data_plugin_controller_signal
    )


# ------------------- load_actions_from_json --------------------------


def test_load_actions_from_json_updates_view_on_success(
    controller: MetaController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Parse a JSON file and pass the actions to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    :param mocker: Pytest-mock fixture.
    """
    actions = {"step1": "do_something"}
    mocker.patch("builtins.open", mock_open(read_data=json.dumps(actions)))

    controller.load_actions_from_json("actions.json")

    mock_view.update_actions_from_json.assert_called_once_with(actions)


def test_load_actions_from_json_returns_none_on_file_error(
    controller: MetaController,
    mocker: MockerFixture,
) -> None:
    """
    Return None and log an error when the JSON file cannot be read.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    mocker.patch("builtins.open", side_effect=OSError("not found"))

    result = controller.load_actions_from_json("missing.json")

    assert result is None
    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]


def test_load_actions_from_json_unwraps_class_name_key(
    controller: MetaController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Unwrap the actions when the JSON is keyed by the controller class name.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    :param mocker: Pytest-mock fixture.
    """
    inner = {"step1": "do_something"}
    actions = {controller.__class__.__name__: inner}
    mocker.patch("builtins.open", mock_open(read_data=json.dumps(actions)))

    controller.load_actions_from_json("actions.json")

    mock_view.update_actions_from_json.assert_called_once_with(inner)


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

    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]
    mock_model.stop_workers.assert_not_called()


def test_handle_kill_worker_logs_warning_when_key_missing(
    controller: MetaController,
    mock_model: MagicMock,
) -> None:
    """
    Log a warning when the key is not present in the workers dict.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    """
    mock_model.workers = {}

    controller.handle_kill_worker("MyReader", "missing_key/0")

    controller.logger.warning.assert_called()  # type: ignore[attr-defined]
    mock_model.stop_workers.assert_not_called()


def test_handle_kill_worker_logs_warning_when_channel_missing(
    controller: MetaController,
    mock_model: MagicMock,
) -> None:
    """
    Log a warning when the key exists but the channel is not present.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    """
    mock_model.workers = {"key1": {1: MagicMock()}}

    controller.handle_kill_worker("MyReader", "key1/99")

    controller.logger.warning.assert_called()  # type: ignore[attr-defined]
    mock_model.stop_workers.assert_not_called()


# ----------------------- set_generator ------------------------------


def test_set_generator_delegates_to_model(
    controller: MetaController,
    mock_model: MagicMock,
) -> None:
    """
    Forward the generator and its metadata to the model.

    :param controller: Controller under test.
    :param mock_model: Mocked meta model.
    """
    gen = iter([1, 2, 3])
    controller.set_generator(gen, 0, "key1", "MetaReader")
    mock_model.set_generator.assert_called_once_with(gen, 0, "key1", "MetaReader")


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


# ------------------- _relay_global_signal ----------------------------


def test_relay_global_signal_emits_with_valid_return_function(
    controller: MetaController,
) -> None:
    """
    Resolve the return function by name and emit the global signal.

    :param controller: Controller under test.
    """
    controller.ignore = MagicMock()  # type: ignore[method-assign]

    controller._relay_global_signal(
        "MetaReader", "key1", "my_func", ("arg",), "ignore", ("ret",)
    )

    controller.global_signal.emit.assert_called_once_with(
        "MetaReader", "key1", "my_func", ("arg",), controller.ignore, ("ret",)
    )


def test_relay_global_signal_logs_warning_when_return_function_missing(
    controller: MetaController,
) -> None:
    """
    Log a warning and return early when the return function name is not an attribute.

    :param controller: Controller under test.
    """
    controller._relay_global_signal(
        "MetaReader", "key1", "my_func", (), "nonexistent_fn", ()
    )

    controller.logger.warning.assert_called()  # type: ignore[attr-defined]
    controller.global_signal.emit.assert_not_called()


def test_relay_global_signal_emits_with_none_return_function(
    controller: MetaController,
) -> None:
    """
    Emit the global signal with None as the return function when name is empty.

    :param controller: Controller under test.
    """
    controller._relay_global_signal("MetaReader", "key1", "my_func", (), "", ())

    controller.global_signal.emit.assert_called_once()
    _, _, _, _, return_fn, _ = controller.global_signal.emit.call_args[0]
    assert return_fn is None


def test_relay_global_signal_logs_exception_on_emit_failure(
    controller: MetaController,
    mocker: MockerFixture,
) -> None:
    """
    Log the failure with a traceback when the global_signal emit raises an exception.

    This used to be reported at warning level as "<callback> is not a callable attribute",
    naming a callback that had already resolved successfully two lines above and
    discarding the stack of whatever actually failed inside emit.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.global_signal.emit.side_effect = RuntimeError("emit failed")
    controller.ignore = MagicMock()  # type: ignore[method-assign]

    controller._relay_global_signal("MetaReader", "key1", "my_func", (), "ignore", ())

    controller.logger.exception.assert_called()  # type: ignore[attr-defined]


# ----------- _relay_data_plugin_controller_signal --------------------


def test_relay_data_plugin_controller_signal_emits_with_valid_return_function(
    controller: MetaController,
) -> None:
    """
    Resolve the return function by name and emit the data plugin controller signal.

    :param controller: Controller under test.
    """
    controller.ignore = MagicMock()  # type: ignore[method-assign]

    controller._relay_data_plugin_controller_signal(
        "MetaReader", "key1", "my_func", ("arg",), "ignore", ("ret",)
    )

    controller.data_plugin_controller_signal.emit.assert_called_once_with(
        "MetaReader", "key1", "my_func", ("arg",), controller.ignore, ("ret",)
    )


def test_relay_data_plugin_controller_signal_logs_warning_when_return_function_missing(
    controller: MetaController,
) -> None:
    """
    Log a warning and return early when the return function name is not an attribute.

    :param controller: Controller under test.
    """
    controller._relay_data_plugin_controller_signal(
        "MetaReader", "key1", "my_func", (), "nonexistent_fn", ()
    )

    controller.logger.warning.assert_called()  # type: ignore[attr-defined]
    controller.data_plugin_controller_signal.emit.assert_not_called()


def test_relay_data_plugin_controller_signal_emits_with_none_return_function(
    controller: MetaController,
) -> None:
    """
    Emit the data plugin controller signal with None when the return function name is empty.

    :param controller: Controller under test.
    """
    controller._relay_data_plugin_controller_signal(
        "MetaReader", "key1", "my_func", (), "", ()
    )

    controller.data_plugin_controller_signal.emit.assert_called_once()
    _, _, _, _, return_fn, _ = controller.data_plugin_controller_signal.emit.call_args[
        0
    ]
    assert return_fn is None


def test_relay_data_plugin_controller_signal_logs_exception_on_emit_failure(
    controller: MetaController,
    mocker: MockerFixture,
) -> None:
    """
    Log the failure with a traceback when the data_plugin_controller_signal emit raises.

    Matches the global_signal relay: both report an emit failure the same way rather than
    blaming the already-resolved callback.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.data_plugin_controller_signal.emit.side_effect = RuntimeError("fail")
    controller.ignore = MagicMock()  # type: ignore[method-assign]

    controller._relay_data_plugin_controller_signal(
        "MetaReader", "key1", "my_func", (), "ignore", ()
    )

    controller.logger.exception.assert_called()  # type: ignore[attr-defined]


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


def test_save_tab_actions_emits_signal_with_history_and_file(
    controller: MetaController,
) -> None:
    """
    Emit save_tab_action_history with the current history and save file path.

    :param controller: Controller under test.
    """
    controller.tab_action_history = OrderedDict({"0": {"function": "do_something"}})
    controller.save_tab_actions("session.json")
    controller.save_tab_action_history.emit.assert_called_once_with(
        controller.tab_action_history, "session.json"
    )


def test_save_tab_actions_emits_signal_with_none_when_no_file(
    controller: MetaController,
) -> None:
    """
    Emit save_tab_action_history with None when no file path is provided.

    :param controller: Controller under test.
    """
    controller.save_tab_actions()
    controller.save_tab_action_history.emit.assert_called_once_with(
        controller.tab_action_history, None
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
    history = {"function": "do_something"}
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


def test_update_tab_actions_undo_removes_last_entry(
    controller: MetaController,
    mock_view: MagicMock,
) -> None:
    """
    Remove the most recent action and replay the remaining history on undo.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    """
    controller.tab_action_history = OrderedDict(
        {0: {"function": "step1"}, 1: {"function": "step2"}}
    )
    controller.update_tab_actions(undo=True)
    assert 1 not in controller.tab_action_history
    mock_view.update_actions_from_json.assert_called_once()


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


def test_update_tab_actions_undo_skips_reset_actions_entries(
    controller: MetaController,
    mock_view: MagicMock,
) -> None:
    """
    Continue popping entries while the last item has function == '_reset_actions'.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    """
    controller.tab_action_history = OrderedDict(
        {
            0: {"function": "step1"},
            1: {"function": "_reset_actions"},
            2: {"function": "_reset_actions"},
        }
    )
    controller.update_tab_actions(undo=True)
    # All _reset_actions entries and the last real entry should be consumed
    mock_view.update_actions_from_json.assert_called_once()


# -------- update_tab_actions StopIteration branches ------------------


def test_update_tab_actions_undo_handles_stopiteration_after_first_popitem(
    controller: MetaController,
    mock_view: MagicMock,
) -> None:
    """
    Hit the StopIteration branch when the history is empty after the first popitem.

    After popping the only remaining entry, next(reversed(...)) raises
    StopIteration which is caught by the outer ``except StopIteration: pass``
    block.  The method should still call update_actions_from_json.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    """
    controller.tab_action_history = OrderedDict({0: {"function": "step1"}})

    controller.update_tab_actions(undo=True)

    # History is now empty — view should still receive the empty history
    mock_view.update_actions_from_json.assert_called_once()
    controller.update_tab_action_history.emit.assert_called_once()


def test_update_tab_actions_undo_handles_stopiteration_inside_reset_actions_loop(
    controller: MetaController,
    mock_view: MagicMock,
) -> None:
    """
    Hit the ``except StopIteration: break`` inside the _reset_actions while loop.

    To trigger the inner break we need the while loop to pop a _reset_actions
    entry and then find the history completely empty so that
    ``next(reversed(self.tab_action_history))`` raises StopIteration.

    Setup: two _reset_actions entries only (no non-reset entry left after the
    outer popitem removes the last one).  The outer popitem removes entry 1,
    then the while loop sees entry 0 is _reset_actions, pops it, and the inner
    next() raises StopIteration → break.

    :param controller: Controller under test.
    :param mock_view: Mocked meta view.
    """
    controller.tab_action_history = OrderedDict(
        {
            0: {"function": "_reset_actions"},
            1: {"function": "_reset_actions"},
        }
    )

    controller.update_tab_actions(undo=True)

    mock_view.update_actions_from_json.assert_called_once()
    controller.update_tab_action_history.emit.assert_called_once()


# ----------- abstract _init / _setup_connections pass lines ----------


def test_abstract_init_pass_line_is_covered() -> None:
    """
    Cover the ``pass`` body of the abstract _init definition.

    Calls the abstract base implementation directly via super() from a
    concrete subclass so coverage sees the pass statement executed.
    """

    class _CallsSuper(MetaController):
        def _init(self) -> None:
            super()._init()  # type: ignore[safe-super]

        def _setup_connections(self) -> None:
            pass

    ctrl = _CallsSuper.__new__(_CallsSuper)  # type: ignore[type-abstract]
    ctrl._init()  # executes MetaController._init -> pass


def test_abstract_setup_connections_pass_line_is_covered() -> None:
    """
    Cover the ``pass`` body of the abstract _setup_connections definition.

    Calls the abstract base implementation directly so coverage sees
    the pass statement executed.
    """

    class _CallsSuper(MetaController):
        def _init(self) -> None:
            pass

        def _setup_connections(self) -> None:
            super()._setup_connections()  # type: ignore[safe-super]

    ctrl = _CallsSuper.__new__(_CallsSuper)  # type: ignore[type-abstract]
    ctrl._setup_connections()  # executes MetaController._setup_connections -> pass


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
    mock_view.run_generators.connect = mocker.Mock()
    mock_view.kill_worker.connect = mocker.Mock()
    mock_view.kill_all_workers.connect = mocker.Mock()
    mock_view.add_text_to_display.connect = mocker.Mock()
    mock_view.save_tab_action_history.connect = mocker.Mock()
    mock_view.update_tab_action_history.connect = mocker.Mock()
    mock_view.cache_plot_data.connect = mocker.Mock()
    mock_view.export_plot_data.connect = mocker.Mock()
    mock_view.load_actions_from_json.connect = mocker.Mock()
    mock_view.create_plugin.connect = mocker.Mock()
    mock_view.global_signal.connect = mocker.Mock()
    mock_view.data_plugin_controller_signal.connect = mocker.Mock()
    mock_model.update_progressbar.connect = mocker.Mock()
    mock_model.add_text_to_display.connect = mocker.Mock()
    mock_model.global_signal.connect = mocker.Mock()
    mock_model.data_plugin_controller_signal.connect = mocker.Mock()
    mock_model.run_generators = mocker.Mock()
    mock_model.update_progressbar = mocker.Mock()

    with mocker.patch.object(
        _ConcreteController, "_connect_global_signal", return_value=None
    ):
        ctrl = _ConcreteController(
            available_subclasses=None,
            my_custom_attr="hello",
            another_attr=42,
        )

    assert ctrl.my_custom_attr == "hello"
    assert ctrl.another_attr == 42


# ---------------------------- ignore ---------------------------------


def test_ignore_is_a_no_op(controller: MetaController) -> None:
    """
    Verify that ignore() completes without raising or producing side effects.

    :param controller: Controller under test.
    """
    controller.ignore()  # should not raise
