"""
Tests for poriscope.controllers.main_controller.MainController.

Covers:
- instantiate_analysis_tab flow (new and existing tabs)
- handle_global_signal dispatch
- update_plugin_history CRUD behavior
- setup_connections signal wiring
- resource shutdown, plugin list propagation, sys.path updates
- session restore and emitting instantiated tabs
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.controllers.main_controller import MainController

# --------------------------- helpers ---------------------------


def _fake_signal(mocker: MockerFixture) -> MagicMock:
    """
    Create a lightweight Qt-like signal mock with ``.connect`` and ``.emit``.

    :param mocker: Pytest-mock fixture for creating mocks.
    :return: A mock object exposing ``.connect`` and ``.emit`` callables.
    """
    sig = mocker.Mock()
    sig.connect = mocker.Mock()
    sig.emit = mocker.Mock()
    return sig


# --------------------------- fixtures ---------------------------


@pytest.fixture
def mock_main_model(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked MainModel with the minimal API used by MainController.

    :param mocker: Pytest-mock fixture.
    :return: Mocked main model.
    """
    model: MagicMock = mocker.Mock()
    # Used in __init__ for DataPluginController construction.
    model.get_plugin_classes.return_value = {
        "RawDataController": lambda available_plugins: MagicMock(view=MagicMock())
    }
    model.get_data_server_location.return_value = "/tmp/data"
    # Session handling during __init__.
    model.load_session.return_value = {}
    # Used by instantiate_analysis_tab.
    model.get_available_plugins.return_value = {}
    return model


@pytest.fixture
def mock_main_view(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked MainView with Qt-like signals and slots used by the controller.

    :param mocker: Pytest-mock fixture.
    :return: Mocked main view.
    """
    view: MagicMock = mocker.Mock()

    # Qt-like signals the controller connects to in setup_connections().
    signal_names = [
        "instantiate_plugin",
        "instantiate_analysis_tab",
        "save_session",
        "load_session",
        "get_shared_data_server",
        "get_user_plugin_location",
        "update_data_server_location",
        "update_user_plugin_location",
        "update_logging_level",
        "clear_cache",
        "request_analysis_tabs",
        "received_analysis_tabs",
    ]
    for name in signal_names:
        setattr(view, name, _fake_signal(mocker))

    # Methods called directly.
    view.add_text_to_display = mocker.Mock()
    view.set_data_server = mocker.Mock()
    view.set_user_plugin_location = mocker.Mock()
    view.populate_plugins_menu = mocker.Mock()
    view.add_page = mocker.Mock()
    return view


@pytest.fixture
def controller(
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
    mocker: MockerFixture,
) -> MainController:
    """
    Construct a MainController with DataPluginController patched out.

    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    mocker.patch("poriscope.controllers.main_controller.DataPluginController")
    return MainController(mock_main_model, mock_main_view)


# ----------------------------- tests -----------------------------


def test_instantiate_analysis_tab_adds_tab(
    controller: MainController,
    mock_main_view: MagicMock,
) -> None:
    """
    Instantiate a new analysis tab when it does not exist.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    controller.analysis_tabs = {}
    controller.instantiate_analysis_tab("RawDataController")

    assert "RawDataController" in controller.analysis_tabs
    mock_main_view.add_page.assert_called_once()
    controller.analysis_tabs[
        "RawDataController"
    ].global_signal.connect.assert_called_once()


def test_instantiate_analysis_tab_uses_existing_instance(
    controller: MainController,
    mock_main_view: MagicMock,
) -> None:
    """
    Do not re-add a page if a tab of the given subclass already exists.

    :param controller: Controller under test.
    :param mock_main_view: Mocked main view.
    """
    existing_tab = MagicMock(view=MagicMock())
    controller.analysis_tabs["RawDataController"] = existing_tab

    controller.instantiate_analysis_tab("RawDataController")

    mock_main_view.add_page.assert_not_called()


def test_handle_global_signal_invokes_plugin_function(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Dispatch a global signal to the plugin instance and call the return callback.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    plugin_instance: MagicMock = mocker.Mock()
    plugin_instance.my_function.return_value = "mock_return"

    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin_instance
    )
    callback: MagicMock = mocker.Mock()

    controller.handle_global_signal(
        "MetaReader",
        "MyReader",
        "my_function",
        ("arg1",),
        callback,
        ("ret_arg",),
    )

    plugin_instance.my_function.assert_called_once_with("arg1")
    assert callback.called


def test_handle_global_signal_instance_none(controller, mocker):
    """
    Case: Plugin instance is None.

    This covers the early-return branch where
    DataPluginController.get_plugin_instance() returns None,
    so the method exits before attempting to get a function.
    """
    # Mock get_plugin_instance to return None
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=None
    )
    cb = mocker.Mock()

    # Call the method under test
    controller.handle_global_signal("MetaX", "Key", "doit", ("a",), cb, ("r",))

    # Ensure the method was called but callback was never invoked
    controller.data_plugin_controller.get_plugin_instance.assert_called_once_with(
        "MetaX", "Key"
    )
    cb.assert_not_called()


def test_handle_global_signal_missing_member(controller, mocker):
    """
    Case: Instance exists, but requested member is missing.

    This covers the branch:
    - func = getattr(instance, call_function, None) returns None
    - Method logs error and returns without invoking callback.
    """
    plugin = object()  # No attributes
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = mocker.Mock()

    controller.handle_global_signal("MetaX", "Key", "no_such_method", (), cb, ())

    cb.assert_not_called()


def test_handle_global_signal_member_not_callable(controller, mocker):
    """
    Case: Instance attribute exists but is not callable.

    This covers the branch where func is found but callable(func) is False,
    so an error is logged and the method returns without invoking callback.
    """
    plugin = mocker.Mock()
    plugin.not_callable = 42  # Intentionally not callable
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = mocker.Mock()

    controller.handle_global_signal("MetaX", "Key", "not_callable", (), cb, ())

    cb.assert_not_called()


def test_handle_global_signal_typeerror_then_none_ok(controller, mocker):
    """
    Case: First call raises TypeError, fallback with None succeeds.

    This covers the branch:
    - func(*args) raises TypeError
    - Retry with func(None) returns a value
    - Callback is invoked with that value plus ret_args
    """
    plugin = mocker.Mock()

    def side_effect(*args):
        # First call triggers TypeError
        if args and args[0] == "bad":
            raise TypeError("wrong arity")
        # Second call with None succeeds
        assert args == (None,)
        return "ok"

    plugin.do = mocker.Mock(side_effect=side_effect)
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = mocker.Mock()

    controller.handle_global_signal("MetaX", "Key", "do", ("bad",), cb, ("ret",))

    # Callback receives ("ok", "ret")
    cb.assert_called_once_with("ok", "ret")


def test_handle_global_signal_func_raises(controller, mocker):
    """
    Case: Function raises a non-TypeError Exception.

    This covers the branch:
    - func(*args) raises an Exception (not TypeError)
    - Exception is logged and method returns without invoking callback.
    """
    plugin = mocker.Mock()
    plugin.boom = mocker.Mock(side_effect=ValueError("kaput"))
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = mocker.Mock()

    controller.handle_global_signal("MetaX", "Key", "boom", (), cb, ())

    cb.assert_not_called()
    plugin.boom.assert_called_once_with()


def test_handle_global_signal_callback_typeerror_fallback(controller, mocker):
    """
    Case: Callback raises TypeError, fallback to callback(None) branch.

    This covers:
    - Callback raises TypeError when called with retval + ret_args
    - Fallback to return_function(None) is triggered
    """
    plugin = mocker.Mock()
    plugin.fn = mocker.Mock(return_value="rv")
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )

    # First call raises TypeError; second call accepts None
    cb = mocker.Mock(side_effect=[TypeError("bad arity"), None])

    controller.handle_global_signal("MetaX", "Key", "fn", (), cb, ())

    # Was called twice: first with retval, then with None
    assert cb.call_count == 2
    assert cb.call_args_list[0].args == ("rv",)
    assert cb.call_args_list[1].args == (None,)


def test_handle_global_signal_callback_other_exception(controller, mocker):
    """
    Case: Callback raises non-TypeError exception.

    This covers:
    - Callback raises some other exception
    - Exception is caught and logged, method returns without fallback
    """
    plugin = mocker.Mock()
    plugin.fn = mocker.Mock(return_value="rv")
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = mocker.Mock(side_effect=RuntimeError("oops"))

    # Should not raise; error is logged internally
    controller.handle_global_signal("MetaX", "Key", "fn", (), cb, ("extra",))

    # Callback attempted once with ("rv", "extra"), then stopped
    cb.assert_called_once()
    assert cb.call_args.args == ("rv", "extra")


def test_update_plugin_history_add_and_remove(controller: MainController) -> None:
    """
    Add a history entry, then remove it.

    :param controller: Controller under test.
    """
    controller.plugin_history = {}

    # Add
    controller.update_plugin_history(
        {"key": "test", "subclass": "Sub", "metaclass": "Meta"},
        "",
    )
    assert "test" in controller.plugin_history

    # Remove
    controller.update_plugin_history({}, "test")
    assert "test" not in controller.plugin_history


def test_update_tab_action_history(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Test that the tab action history is updated and saved correctly.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Mock the save_tab_actions method
    controller.main_model.save_tab_actions = mocker.Mock()

    # Initial state: empty history
    controller.tab_action_history = {}

    # Define test data
    tab_key = "SomeTab"
    action_history = {"action": "opened", "timestamp": "2023-01-01"}

    # Call the method under test
    controller.update_tab_action_history(tab_key, action_history)

    # Verify that the tab action history is updated with the given data
    assert controller.tab_action_history[tab_key] == action_history

    # Ensure the history is saved
    controller.main_model.save_tab_actions.assert_called_once_with(
        controller.tab_action_history
    )


def test_update_tab_action_history_with_existing_key(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Test that the tab action history is updated correctly when an existing key is provided.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Mock the save_tab_actions method
    controller.main_model.save_tab_actions = mocker.Mock()

    # Initial state: existing history for "SomeTab"
    controller.tab_action_history = {
        "SomeTab": {"action": "opened", "timestamp": "2023-01-01"}
    }

    # New action history for the same tab key
    new_action_history = {"action": "closed", "timestamp": "2023-01-02"}

    # Call the method under test
    controller.update_tab_action_history("SomeTab", new_action_history)

    # Verify that the tab action history is updated with the new data
    assert controller.tab_action_history["SomeTab"] == new_action_history

    # Ensure the updated history is saved
    controller.main_model.save_tab_actions.assert_called_once_with(
        controller.tab_action_history
    )


def test_update_tab_action_history_empty_history(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Test that the method behaves correctly when the tab action history is initially empty.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Mock the save_tab_actions method
    controller.main_model.save_tab_actions = mocker.Mock()

    # Initial state: empty history
    controller.tab_action_history = {}

    # Define test data
    tab_key = "NewTab"
    action_history = {"action": "opened", "timestamp": "2023-01-01"}

    # Call the method under test
    controller.update_tab_action_history(tab_key, action_history)

    # Verify that the tab action history is updated with the given data
    assert controller.tab_action_history[tab_key] == action_history

    # Ensure the history is saved
    controller.main_model.save_tab_actions.assert_called_once_with(
        controller.tab_action_history
    )


def test_setup_connections_connects_main_signals(
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Connect representative view signals to the controller.

    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    :param mocker: Pytest-mock fixture.
    """
    mocker.patch("poriscope.controllers.main_controller.DataPluginController")

    MainController(mock_main_model, mock_main_view)

    mock_main_view.instantiate_plugin.connect.assert_called()
    mock_main_view.instantiate_analysis_tab.connect.assert_called()
    mock_main_view.clear_cache.connect.assert_called()


def test_send_analysis_tabs_emits_to_view(
    controller: MainController, mock_main_view: MagicMock
) -> None:
    """
    Emit the current analysis tabs to the view.

    :param controller: Controller under test.
    :param mock_main_view: Mocked main view.
    """
    controller.analysis_tabs = {"SomeTab": MagicMock()}
    controller.send_analysis_tabs()
    mock_main_view.received_analysis_tabs.emit.assert_called_once_with(
        controller.analysis_tabs
    )


def test_handle_about_to_quit_stops_workers_and_exits(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Stop all tab workers and call DataPluginController.handle_exit.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    tab1 = mocker.Mock()
    tab2 = mocker.Mock()
    controller.analysis_tabs = {"A": tab1, "B": tab2}

    controller.data_plugin_controller.handle_exit = mocker.Mock()

    controller.handle_about_to_quit()

    tab1.handle_kill_all_workers.assert_called_once_with("A", exiting=True)
    tab2.handle_kill_all_workers.assert_called_once_with("B", exiting=True)
    controller.data_plugin_controller.handle_exit.assert_called_once()


def test_send_curent_data_server(
    controller: MainController, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    Test that the data server is retrieved from the model and passed to the view.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    mock_main_model.get_app_config.return_value = "/tmp/data"

    controller.send_curent_data_server()

    mock_main_view.set_data_server.assert_called_once_with("/tmp/data")


def test_send_curent_user_plugin_location(
    controller: MainController, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    Test that the user plugin location is retrieved from the model and passed to the view.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    mock_main_model.get_app_config.return_value = "/tmp/plugins"

    controller.send_curent_user_plugin_location()

    mock_main_view.set_user_plugin_location.assert_called_once_with("/tmp/plugins")


def test_update_data_server_location(
    controller: MainController, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    Test that the data server location is updated in the model and data plugin controller.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    new_data_server = "/new/data/server"

    controller.update_data_server_location(new_data_server)

    mock_main_model.update_app_config.assert_called_once_with(
        "Parent Folder", new_data_server
    )

    controller.data_plugin_controller.update_data_server_location.assert_called_once_with(
        new_data_server
    )


def test_update_available_plugins_pushes_to_tabs(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Cache the available plugin list and push it to all tabs.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    tab = mocker.Mock()
    controller.analysis_tabs = {"X": tab}

    controller.update_available_plugins("MetaReader", ["R1", "R2"])

    assert controller.data_plugins["MetaReader"] == ["R1", "R2"]
    tab.update_available_plugins.assert_called_once_with(controller.data_plugins)


def test_update_user_plugin_location_adds_parent_to_syspath(
    controller: MainController,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    Add the parent of the user plugin directory to ``sys.path`` if missing.

    :param controller: Controller under test.
    :param monkeypatch: Pytest monkeypatch fixture.
    :param tmp_path: Temporary directory fixture.
    """
    plugins_dir = tmp_path / "my_plugins"
    plugins_dir.mkdir()
    user_plugin_loc = str(plugins_dir)

    # Start with a copy of sys.path we can mutate safely.
    monkeypatch.setattr(sys, "path", list(sys.path))
    parent = str(plugins_dir.parent)
    if parent in sys.path:
        sys.path.remove(parent)

    controller.update_user_plugin_location(user_plugin_loc)

    assert parent in sys.path
    controller.main_model.update_app_config.assert_called_once_with(
        "User Plugin Folder", user_plugin_loc
    )


def test_get_plugin_instance(controller: MainController, mocker: MockerFixture) -> None:
    """
    Test that get_plugin_instance retrieves the correct plugin and invokes the callback.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    plugin_instance = mocker.Mock()

    # Set up the data_plugin_controller mock to return the plugin instance
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin_instance
    )

    # Create a mock callback function
    callback = mocker.Mock()

    # Call the method under test
    controller.get_plugin_instance("MetaReader", "MyReader", callback)

    # Verify that get_plugin_instance was called with the correct parameters
    controller.data_plugin_controller.get_plugin_instance.assert_called_once_with(
        "MetaReader", "MyReader"
    )

    # Verify that the callback was called with the retrieved plugin instance
    callback.assert_called_once_with(plugin_instance)


def test_get_settings_from_history_found_in_current_history(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Test that settings are retrieved from the current plugin history.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Setup mock history
    controller.plugin_history = {
        "plugin_key": {
            "metaclass": "MetaReader",
            "subclass": "MyReader",
            "settings": {"key": "value"},
        }
    }

    # Mock the data_plugin_controller's set_settings method
    controller.data_plugin_controller.set_settings = mocker.Mock()

    # Call the method under test
    controller.get_settings_from_history("MetaReader", "MyReader")

    # Verify that set_settings is called with the correct settings
    controller.data_plugin_controller.set_settings.assert_called_once_with(
        {"key": "value"}
    )


def test_get_settings_from_history_found_in_previous_history(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Test that settings are retrieved from the previous plugin history if not found in current history.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Setup mock previous history
    controller.previous_plugin_history = {
        "plugin_key": {
            "metaclass": "MetaReader",
            "subclass": "MyReader",
            "settings": {"key": "previous_value"},
        }
    }

    # Mock the data_plugin_controller's set_settings method
    controller.data_plugin_controller.set_settings = mocker.Mock()

    # Call the method under test
    controller.get_settings_from_history("MetaReader", "MyReader")

    # Verify that set_settings is called with the correct settings from previous history
    controller.data_plugin_controller.set_settings.assert_called_once_with(
        {"key": "previous_value"}
    )


def test_get_settings_from_history_not_found(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Test that set_settings is called with None if no settings are found in history.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Setup mock histories with no matching settings
    controller.plugin_history = {}
    controller.previous_plugin_history = {}

    # Mock the data_plugin_controller's set_settings method
    controller.data_plugin_controller.set_settings = mocker.Mock()

    # Call the method under test
    controller.get_settings_from_history("MetaReader", "MyReader")

    # Verify that set_settings is called with None
    controller.data_plugin_controller.set_settings.assert_called_once_with(None)


def test_ensure_tuple_with_tuple_input(controller: MainController) -> None:
    """
    Test that _ensure_tuple returns the input unchanged if it is already a tuple.

    :param controller: Controller under test.
    """
    result = controller._ensure_tuple(("arg1", "arg2"))

    # Ensure the result is unchanged and is still a tuple
    assert result == ("arg1", "arg2")
    assert isinstance(result, tuple)


def test_ensure_tuple_with_non_tuple_input(controller: MainController) -> None:
    """
    Test that _ensure_tuple wraps a non-tuple input in a tuple.

    :param controller: Controller under test.
    """
    result = controller._ensure_tuple("arg1")

    # Ensure the result is now a tuple
    assert result == ("arg1",)
    assert isinstance(result, tuple)


def test_ensure_tuple_with_none_input(controller: MainController) -> None:
    """
    Test that _ensure_tuple returns an empty tuple if the input is None.

    :param controller: Controller under test.
    """
    result = controller._ensure_tuple(None)

    # Ensure the result is an empty tuple
    assert result == ()
    assert isinstance(result, tuple)


def test_handle_data_plugin_controller_signal_calls_method_and_callback(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Dispatch a call to DataPluginController and invoke the return callback.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.data_plugin_controller.some_method = mocker.Mock(return_value=("ok",))
    return_cb = mocker.Mock()

    controller.handle_data_plugin_controller_signal(
        metaclass="MetaX",
        subclass_key="Key",
        call_function="some_method",
        call_args=("argA",),
        return_function=return_cb,
        ret_args=("extra",),
    )

    controller.data_plugin_controller.some_method.assert_called_once_with("argA")
    assert return_cb.called


def test_load_session_restores_tabs_and_plugins(
    mocker: MockerFixture, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    Restore MetaController tabs and non-controller plugins from saved history.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    # Patch DPC construction and capture the instance used by the controller.
    dpc_cls = mocker.patch("poriscope.controllers.main_controller.DataPluginController")
    dpc_instance = dpc_cls.return_value

    ctrl = MainController(mock_main_model, mock_main_view)

    # Provide plugin history with both a MetaController entry and a non-MetaController plugin.
    history: Dict[str, dict] = {
        "tab_key": {"metaclass": "MetaController", "subclass": "RawDataController"},
        "reader_key": {
            "metaclass": "MetaReader",
            "subclass": "MyReader",
            "settings": {"a": 1},
        },
    }
    mock_main_model.load_session.return_value = history

    # Make instantiate_analysis_tab succeed.
    # (fully valid mock tab with all required properties)
    tab_instance = mocker.Mock()
    tab_instance.view = mocker.Mock()
    tab_instance.global_signal = mocker.Mock(connect=mocker.Mock())
    tab_instance.create_plugin = mocker.Mock(connect=mocker.Mock())
    tab_instance.data_plugin_controller_signal = mocker.Mock(connect=mocker.Mock())
    tab_instance.add_text_to_display = mocker.Mock(connect=mocker.Mock())
    tab_instance.update_tab_action_history = mocker.Mock(connect=mocker.Mock())
    tab_instance.save_tab_action_history = mocker.Mock(connect=mocker.Mock())
    tab_instance.update_available_plugins = mocker.Mock()

    mock_main_model.get_plugin_classes.return_value = {
        "RawDataController": lambda available: tab_instance
    }
    mock_main_model.get_available_plugins.return_value = {}

    # Exercise.
    ctrl.load_session("session.json")

    # Tab restored.
    assert "RawDataController" in ctrl.analysis_tabs
    # Non-controller plugin restored via DPC.
    dpc_instance.validate_and_instantiate_plugin.assert_any_call(
        metaclass="MetaReader",
        subclass="MyReader",
        settings={"a": 1},
        key="reader_key",
    )


def test_load_session_no_history(controller, mocker):
    """
    Case: load_session returns None.

    This should hit the branch that logs an info message and returns
    without trying to restore any plugins.
    """
    controller.main_model.load_session = mocker.Mock(return_value=None)
    controller.plugin_history = {}

    # Call and verify no further processing happens
    controller.load_session("file.json")
    controller.main_model.save_session.assert_not_called()


def test_load_session_restore_analysis_tab_error(controller, mocker):
    """
    Case: MetaController entry restoration raises an exception.

    This covers the except branch for instantiate_analysis_tab failures.
    """
    controller.plugin_history = {
        "key1": {"metaclass": "MetaController", "subclass": "SomeTab"}
    }
    controller.main_model.load_session = mocker.Mock(
        return_value=controller.plugin_history
    )
    controller.instantiate_analysis_tab = mocker.Mock(side_effect=RuntimeError("fail"))

    controller.load_session("session.json")

    controller.instantiate_analysis_tab.assert_called_once_with("SomeTab")


def test_load_session_restore_plugin_error(controller, mocker):
    """
    Case: Non-MetaController plugin restoration raises an exception.

    This covers the except branch for validate_and_instantiate_plugin failures.
    """
    controller.plugin_history = {
        "key2": {"metaclass": "MetaReader", "subclass": "MyReader", "settings": {}}
    }
    controller.main_model.load_session = mocker.Mock(
        return_value=controller.plugin_history
    )
    controller.data_plugin_controller.validate_and_instantiate_plugin = mocker.Mock(
        side_effect=RuntimeError("fail")
    )

    controller.load_session("session.json")

    controller.data_plugin_controller.validate_and_instantiate_plugin.assert_called_once()


def test_send_analysis_tabs_empty(controller, mocker):
    """
    Case: No analysis tabs present.

    This covers the branch where analysis_tabs is empty and a warning is logged
    before emitting the signal with an empty dict.
    """
    controller.analysis_tabs = {}
    controller.main_view.received_analysis_tabs.emit = mocker.Mock()

    controller.send_analysis_tabs()

    controller.main_view.received_analysis_tabs.emit.assert_called_once_with({})


def test_save_session_with_provided_file(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Test that the session is saved correctly when a file name is provided.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Mock the save_session method in the model
    controller.main_model.save_session = mocker.Mock()

    # Define mock plugin history
    mock_plugin_history = {
        "plugin_key": {
            "metaclass": "MetaReader",
            "subclass": "MyReader",
            "settings": {"key": "value"},
        }
    }
    controller.plugin_history = mock_plugin_history

    # Define a test file name
    test_file = "test_session.json"

    # Call the method under test
    controller.save_session(save_file=test_file)

    # Ensure the save_session method in the model is called with the correct data and file name
    controller.main_model.save_session.assert_called_once_with(
        mock_plugin_history, test_file
    )


def test_save_session_without_file(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Test that the session is saved correctly when no file name is provided.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Mock the save_session method in the model
    controller.main_model.save_session = mocker.Mock()

    # Define mock plugin history
    mock_plugin_history = {
        "plugin_key": {
            "metaclass": "MetaReader",
            "subclass": "MyReader",
            "settings": {"key": "value"},
        }
    }
    controller.plugin_history = mock_plugin_history

    # Call the method under test without providing a file name
    controller.save_session()

    # Ensure the save_session method in the model is called with the correct data and default file name (None or default)
    controller.main_model.save_session.assert_called_once_with(
        mock_plugin_history, None
    )


def test_save_session_empty_history(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Test that the session is saved correctly when plugin history is empty.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Mock the save_session method in the model
    controller.main_model.save_session = mocker.Mock()

    # Define empty plugin history
    controller.plugin_history = {}

    # Call the method under test
    controller.save_session()

    # Ensure the save_session method in the model is called with the empty history
    controller.main_model.save_session.assert_called_once_with({}, None)


def test_save_tab_action_history(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Test that the tab action history is saved correctly using realistic structure.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Mock the save_tab_actions method in the model
    controller.main_model.save_tab_actions = mocker.Mock()

    # Define realistic tab action history using plugin-style structure
    tab_action_history = {
        "SQLiteDBWriter_0": {
            "metaclass": "MetaDatabaseWriter",
            "subclass": "SQLiteDBWriter",
            "settings": {
                "Experiment Name": {"Type": "str", "Value": "test"},
                "Output File": {
                    "Options": [
                        "SQLite3 Files (*.sqlite3)",
                        "Database Files (*.db)",
                        "SQLite Files (*.sqlite)",
                    ],
                    "Type": "str",
                    "Value": "Z:/Poriscope Tests/DB.sqlite3",
                },
                "Conductivity": {
                    "Min": 0,
                    "Type": "float",
                    "Units": "S/m",
                    "Value": 11.0,
                },
                "Voltage": {"Type": "float", "Units": "mV", "Value": 11.0},
                "Membrane Thickness": {
                    "Min": 0,
                    "Type": "float",
                    "Units": "nm",
                    "Value": 11.0,
                },
                "MetaEventFitter": {"Options": None, "Type": "str", "Value": "CUSUM_0"},
            },
        }
    }

    # Call the method under test
    controller.save_tab_action_history(
        tab_action_history, save_file="test_session.json"
    )

    # Ensure the save_tab_actions method in the model is called with the correct data
    controller.main_model.save_tab_actions.assert_called_once_with(
        tab_action_history, "test_session.json"
    )


def test_send_analysis_tabs(controller: MainController, mocker: MockerFixture) -> None:
    """
    Test that the analysis tabs are sent to the view.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # Mock the signal and main view
    mock_main_view = mocker.Mock()
    controller.main_view = mock_main_view

    # Mock the analysis tabs
    controller.analysis_tabs = {"SomeTab": mocker.Mock()}

    # Call the method under test
    controller.send_analysis_tabs()

    # Ensure the signal is emitted with the correct analysis tabs
    mock_main_view.received_analysis_tabs.emit.assert_called_once_with(
        controller.analysis_tabs
    )
