"""
Tests for poriscope.controllers.main_controller.MainController.

Covers:
- instantiate_analysis_tab (new tab, existing tab, instantiation error)
- handle_global_signal dispatch (success, instance None, missing member,
  non-callable member, unbindable call args, body TypeError not retried, func
  raises, None result reaching the callback, tuple return splatted by annotation,
  callback other exception)
- update_plugin_history CRUD (add, delete, rename, save_session called)
- update_tab_action_history stores and saves
- setup_connections signal wiring
- handle_about_to_quit stops workers and calls handle_exit
- send_curent_data_server delegates to model and view
- send_curent_user_plugin_location delegates to model and view
- update_data_server_location delegates to model and data_plugin_controller
- update_user_plugin_location adds parent to sys.path and saves config
- get_plugin_instance retrieves instance and invokes callback
- _lookup_historical_settings (found in current, found in previous, not found)
- handle_data_plugin_controller_signal (success with callback, func missing raises,
  non-callable raises, callback exception logged with traceback) - it shares
  _dispatch_to with handle_global_signal, so the cases above cover both paths
- update_available_plugins caches and pushes to tabs
- save_session (with file, without file, empty history)
- save_tab_action_history delegates to model
- load_session (success restore tabs and plugins, None history, tab error,
  plugin ValueError already-exists, plugin other error)
- send_analysis_tabs (tabs present, tabs empty)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
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


class _BodyTypeErrorPlugin:
    """
    Plugin double whose dispatched method binds cleanly but raises ``TypeError`` from its body.
    """

    def __init__(self) -> None:
        self.calls: List[Tuple[Any, ...]] = []

    def fn(self, channel: int) -> None:
        """
        Record the call, then raise from the body rather than at the call boundary.

        :param channel: Arbitrary single argument.
        """
        self.calls.append((channel,))
        raise TypeError("raised from the body, not the call boundary")


class _NoneReturningPlugin:
    """
    Plugin double whose dispatched method takes one argument and returns ``None``.
    """

    def __init__(self) -> None:
        self.calls: List[Tuple[Any, ...]] = []

    def fn(self, channel: int) -> None:
        """
        Record the call and return nothing, as an ``Optional``-returning plugin method does on a miss.

        :param channel: Arbitrary single argument.
        """
        self.calls.append((channel,))


class _TupleReturningPlugin:
    """
    Plugin double whose dispatched method declares a ``Tuple`` return, as ``validate_filter_query`` does.
    """

    def __init__(self) -> None:
        self.calls: List[Tuple[Any, ...]] = []

    def fn(self, channel: int) -> Tuple[str, str]:
        """
        Record the call and return a pair for the dispatcher to splat.

        :param channel: Arbitrary single argument.
        :return: A pair of values.
        """
        self.calls.append((channel,))
        return ("first", "second")


class _Callback:
    """
    Callback double with exactly one required parameter.
    """

    def __init__(self) -> None:
        self.calls: List[Tuple[Any, ...]] = []

    def __call__(self, value: Any) -> None:
        """
        Record the single argument it was called with.

        :param value: The value passed by the dispatcher.
        """
        self.calls.append((value,))


class _TwoArgCallback:
    """
    Callback double with two required parameters, mirroring ``update_column_units(units, axis)``.
    """

    def __init__(self) -> None:
        self.calls: List[Tuple[Any, ...]] = []

    def __call__(self, value: Any, axis: Any) -> None:
        """
        Record both arguments it was called with.

        :param value: The result of the dispatched call.
        :param axis: The trailing ``ret_args`` entry.
        """
        self.calls.append((value, axis))


# --------------------------- fixtures ---------------------------


@pytest.fixture
def mock_main_model(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked MainModel with the minimal API used by MainController.

    :param mocker: Pytest-mock fixture.
    :return: Mocked main model.
    """
    model: MagicMock = mocker.Mock()
    model.get_plugin_classes.return_value = {
        "RawDataController": lambda available_plugins: MagicMock(view=MagicMock())
    }
    model.get_data_server_location.return_value = "/tmp/data"
    model.load_session.return_value = {}
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

    The instance-level logger is replaced with a Mock after construction so
    that log-assertion tests work without touching the real logging system.

    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    mocker.patch("poriscope.controllers.main_controller.DataPluginController")
    ctrl = MainController(mock_main_model, mock_main_view)
    mocker.patch.object(ctrl, "logger", mocker.Mock())  # type: ignore[attr-defined]
    return ctrl


# ----------------------------- tests -----------------------------


def test_instantiate_analysis_tab_adds_new_tab(
    controller: MainController,
    mock_main_view: MagicMock,
) -> None:
    """
    Instantiate a new analysis tab and wire all signals when it does not yet exist.

    :param controller: Controller under test.
    :param mock_main_view: Mocked main view.
    """
    controller.analysis_tabs = {}
    controller.instantiate_analysis_tab("RawDataController")

    assert "RawDataController" in controller.analysis_tabs
    mock_main_view.add_page.assert_called_once()
    controller.analysis_tabs[
        "RawDataController"
    ].global_signal.connect.assert_called_once()


def test_instantiate_analysis_tab_syncs_the_sidebar_highlight(
    controller: MainController,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
) -> None:
    """
    Highlight the sidebar button for a newly created tab's view.

    The normal button-click handlers (on_raw_data_view_click and similar)
    sync the sidebar themselves alongside emitting the signal that reaches
    this method, so this looks redundant for that path. A caller that
    reaches this method directly instead - load_session restoring a saved
    session, in particular - never goes through a click handler at all, and
    without this the sidebar was left showing nothing, or whatever was
    highlighted before, with no tab actually behind it.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    tab_view = MagicMock()
    tab_view.__class__.__name__ = "RawDataView"
    mock_main_model.get_plugin_classes.return_value = {
        "RawDataController": lambda available_plugins: MagicMock(view=tab_view)
    }
    controller.analysis_tabs = {}

    controller.instantiate_analysis_tab("RawDataController")

    mock_main_view.sync_sidebar_highlight.assert_called_once_with("RawDataView")


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
    mock_main_view.sync_sidebar_highlight.assert_not_called()


def test_instantiate_analysis_tab_logs_error_on_instantiation_failure(
    controller: MainController,
    mock_main_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Log an error and return early when the plugin class raises during instantiation.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mocker: Pytest-mock fixture.
    """
    mock_main_model.get_plugin_classes.return_value = {
        "BadTab": mocker.Mock(side_effect=RuntimeError("boom"))
    }
    controller.analysis_tabs = {}

    controller.instantiate_analysis_tab("BadTab")

    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]
    assert "BadTab" not in controller.analysis_tabs


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


def test_handle_global_signal_instance_none(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Return early without calling the callback when get_plugin_instance returns None.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=None
    )
    cb = mocker.Mock()

    controller.handle_global_signal("MetaX", "Key", "doit", ("a",), cb, ("r",))

    controller.data_plugin_controller.get_plugin_instance.assert_called_once_with(
        "MetaX", "Key"
    )
    cb.assert_not_called()


def test_handle_global_signal_missing_member(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Log an error and return early when the requested member does not exist on the instance.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    plugin = object()
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = mocker.Mock()

    controller.handle_global_signal("MetaX", "Key", "no_such_method", (), cb, ())

    cb.assert_not_called()


def test_handle_global_signal_member_not_callable(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Log an error and return early when the resolved attribute is not callable.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    plugin = mocker.Mock()
    plugin.not_callable = 42
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = mocker.Mock()

    controller.handle_global_signal("MetaX", "Key", "not_callable", (), cb, ())

    cb.assert_not_called()


def test_handle_global_signal_never_guesses_at_the_forward_call(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Call a plugin method at most once, and only when the arguments actually bind.

    The dispatcher used to catch a TypeError from the call and retry it with a single
    None, which cannot be distinguished from a call-boundary arity mismatch and so ran
    a method that had already run once more with different arguments. Arity is now
    checked up front instead, which covers both halves of that: a method that raises
    TypeError from its body is called exactly once and the error is logged, and a call
    whose arguments cannot bind is reported without being attempted at all.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _BodyTypeErrorPlugin()
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = _Callback()

    controller.handle_global_signal("MetaX", "Key", "fn", ("chan",), cb, ("ret",))

    assert plugin.calls == [("chan",)]
    assert cb.calls == []

    unbindable = _NoneReturningPlugin()
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=unbindable
    )

    controller.handle_global_signal(
        "MetaX", "Key", "fn", ("one", "two", "three"), cb, ()
    )

    assert unbindable.calls == []
    assert cb.calls == []


def test_handle_global_signal_unpacks_the_result_by_declared_return_type(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Decide from the callee's return annotation whether to splat its result or pass it whole.

    A method returning a pair and a method returning two values produce the same object,
    and a method with an Optional return type that returns None is not returning an empty
    argument list, so the runtime value cannot settle this. The declared return type can,
    and does: a non-tuple return reaches the callback as one argument, None included, with
    ret_args still appended after it; a Tuple return is splatted across the callback's
    parameters.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _NoneReturningPlugin()
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = _TwoArgCallback()

    controller.handle_global_signal("MetaX", "Key", "fn", ("chan",), cb, ("x_axis",))

    assert cb.calls == [(None, "x_axis")]

    pair = _TupleReturningPlugin()
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=pair
    )
    splatted = _TwoArgCallback()

    controller.handle_global_signal("MetaX", "Key", "fn", ("chan",), splatted, ())

    assert splatted.calls == [("first", "second")]


def test_handle_global_signal_func_raises(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Log and return early when the function raises a non-TypeError exception.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
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


def test_handle_global_signal_none_result_reaches_the_callback(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Pass an explicit None to a callback that needs a result slot when the call returned None.

    A plugin method with an Optional return type says "no result" by returning None,
    which _ensure_tuple renders as an empty argument list. A callback expecting a
    result must still be given a None to put in that slot, and must be called once.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _NoneReturningPlugin()
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = _Callback()

    controller.handle_global_signal("MetaX", "Key", "fn", ("chan",), cb, ())

    assert cb.calls == [(None,)]


def test_handle_global_signal_none_result_keeps_ret_args(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Keep ret_args alongside the substituted None rather than dropping them.

    This is the ``get_column_units`` -> ``update_column_units(units, axis)`` shape:
    a None result used to fall back to a bare ``callback(None)``, which discarded the
    axis and raised a second TypeError, so the callback never ran at all.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _NoneReturningPlugin()
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = _TwoArgCallback()

    controller.handle_global_signal("MetaX", "Key", "fn", ("chan",), cb, ("x_axis",))

    assert cb.calls == [(None, "x_axis")]


def test_handle_global_signal_callback_other_exception(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Log and return without fallback when the callback raises a non-TypeError exception.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    plugin = mocker.Mock()
    plugin.fn = mocker.Mock(return_value="rv")
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin
    )
    cb = mocker.Mock(side_effect=RuntimeError("oops"))

    controller.handle_global_signal("MetaX", "Key", "fn", (), cb, ("extra",))

    cb.assert_called_once()
    assert cb.call_args.args == ("rv", "extra")


def test_update_plugin_history_add_entry(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    Add a new history entry keyed by the plugin key.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    controller.plugin_history = {}

    controller.update_plugin_history(
        {"key": "test", "subclass": "Sub", "metaclass": "Meta"}, ""
    )

    assert "test" in controller.plugin_history
    mock_main_model.save_session.assert_called()


def test_update_plugin_history_delete_entry(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    Remove a history entry by delete_key.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    controller.plugin_history = {"test": {"subclass": "Sub", "metaclass": "Meta"}}

    controller.update_plugin_history({}, "test")

    assert "test" not in controller.plugin_history
    mock_main_model.save_session.assert_called()


def test_update_plugin_history_rename_entry(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    Rename a history entry by replacing the old key with the new one.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    controller.plugin_history = {"old_key": {"subclass": "Sub", "metaclass": "Meta"}}

    controller.update_plugin_history(
        {"key": "new_key", "subclass": "Sub", "metaclass": "Meta"}, "old_key"
    )

    assert "new_key" in controller.plugin_history
    assert "old_key" not in controller.plugin_history
    mock_main_model.save_session.assert_called()


def test_update_tab_action_history_stores_and_saves(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    Store the tab action history and save it via the model.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    controller.tab_action_history = {}
    history = {"action": "opened"}

    controller.update_tab_action_history("SomeTab", history)

    assert controller.tab_action_history["SomeTab"] == history
    mock_main_model.save_tab_actions.assert_called_once_with(
        controller.tab_action_history
    )


def test_update_tab_action_history_overwrites_existing_key(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    Overwrite an existing tab action entry when the same key is updated.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    controller.tab_action_history = {"SomeTab": {"action": "opened"}}
    new_history = {"action": "closed"}

    controller.update_tab_action_history("SomeTab", new_history)

    assert controller.tab_action_history["SomeTab"] == new_history
    mock_main_model.save_tab_actions.assert_called_once_with(
        controller.tab_action_history
    )


def test_setup_connections_connects_main_signals(
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Connect representative view signals during construction.

    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    :param mocker: Pytest-mock fixture.
    """
    mocker.patch("poriscope.controllers.main_controller.DataPluginController")

    MainController(mock_main_model, mock_main_view)

    mock_main_view.instantiate_plugin.connect.assert_called()
    mock_main_view.instantiate_analysis_tab.connect.assert_called()
    mock_main_view.clear_cache.connect.assert_called()


def test_handle_about_to_quit_stops_workers_and_exits(
    controller: MainController,
    mocker: MockerFixture,
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


def test_handle_about_to_quit_flushes_session_state_first(
    controller: MainController,
    mock_main_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Flush current session state (including tab-only state like subset filters) to the
    default session file on quit, so it survives even if the user never explicitly
    clicked Save Session or touched a data plugin after their last edit.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mocker: Pytest-mock fixture.
    """
    controller.plugin_history = {"MetadataController": {"metaclass": "MetaController"}}
    tab = mocker.Mock()
    tab.get_session_state.return_value = {"subset_filters": {"f1": "voltage > 0"}}
    controller.analysis_tabs = {"MetadataController": tab}
    controller.data_plugin_controller.handle_exit = mocker.Mock()

    controller.handle_about_to_quit()

    assert controller.plugin_history["MetadataController"]["subset_filters"] == {
        "f1": "voltage > 0"
    }
    mock_main_model.save_session.assert_called_once_with(
        controller.plugin_history, None
    )


def test_send_curent_data_server_delegates_to_model_and_view(
    controller: MainController,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
) -> None:
    """
    Retrieve the data server from the model and pass it to the view.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    mock_main_model.get_app_config.return_value = "/tmp/data"

    controller.send_curent_data_server()

    mock_main_view.set_data_server.assert_called_once_with("/tmp/data")


def test_send_curent_user_plugin_location_delegates_to_model_and_view(
    controller: MainController,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
) -> None:
    """
    Retrieve the user plugin location from the model and pass it to the view.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    mock_main_model.get_app_config.return_value = "/tmp/plugins"

    controller.send_curent_user_plugin_location()

    mock_main_view.set_user_plugin_location.assert_called_once_with("/tmp/plugins")


def test_update_data_server_location_updates_model_and_controller(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    Save the new data server path to the model and forward it to the data plugin controller.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    controller.update_data_server_location("/new/data/server")

    mock_main_model.update_app_config.assert_called_once_with(
        "Parent Folder", "/new/data/server"
    )
    controller.data_plugin_controller.update_data_server_location.assert_called_once_with(
        "/new/data/server"
    )


def test_update_user_plugin_location_adds_parent_to_syspath(
    controller: MainController,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    Add the parent of the user plugin directory to sys.path when not already present.

    :param controller: Controller under test.
    :param monkeypatch: Pytest monkeypatch fixture.
    :param tmp_path: Temporary directory fixture.
    """
    plugins_dir = tmp_path / "my_plugins"
    plugins_dir.mkdir()
    user_plugin_loc = str(plugins_dir)

    monkeypatch.setattr(sys, "path", list(sys.path))
    parent = str(plugins_dir.parent)
    if parent in sys.path:
        sys.path.remove(parent)

    controller.update_user_plugin_location(user_plugin_loc)

    assert parent in sys.path
    controller.main_model.update_app_config.assert_called_once_with(
        "User Plugin Folder", user_plugin_loc
    )


def test_update_user_plugin_location_does_not_duplicate_syspath(
    controller: MainController,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    Do not add the parent path to sys.path when it is already present.

    :param controller: Controller under test.
    :param monkeypatch: Pytest monkeypatch fixture.
    :param tmp_path: Temporary directory fixture.
    """
    plugins_dir = tmp_path / "my_plugins"
    plugins_dir.mkdir()
    parent = str(plugins_dir.parent)

    monkeypatch.setattr(sys, "path", list(sys.path) + [parent])

    controller.update_user_plugin_location(str(plugins_dir))

    assert sys.path.count(parent) == 1


def test_get_plugin_instance_calls_callback_with_result(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Retrieve a plugin instance from the data plugin controller and invoke the callback.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    plugin_instance = mocker.Mock()
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        return_value=plugin_instance
    )
    callback = mocker.Mock()

    controller.get_plugin_instance("MetaReader", "MyReader", callback)

    controller.data_plugin_controller.get_plugin_instance.assert_called_once_with(
        "MetaReader", "MyReader"
    )
    callback.assert_called_once_with(plugin_instance)


def test_lookup_historical_settings_found_in_current_history(
    controller: MainController,
) -> None:
    """
    Return the settings dict from plugin_history when found.

    :param controller: Controller under test.
    """
    controller.plugin_history = {
        "plugin_key": {
            "metaclass": "MetaReader",
            "subclass": "MyReader",
            "settings": {"key": "value"},
        }
    }

    result = controller._lookup_historical_settings("MetaReader", "MyReader")

    assert result == {"key": "value"}


def test_lookup_historical_settings_found_in_previous_history(
    controller: MainController,
) -> None:
    """
    Fall back to previous_plugin_history when not found in current history.

    :param controller: Controller under test.
    """
    controller.plugin_history = {}
    controller.previous_plugin_history = {
        "plugin_key": {
            "metaclass": "MetaReader",
            "subclass": "MyReader",
            "settings": {"key": "previous_value"},
        }
    }

    result = controller._lookup_historical_settings("MetaReader", "MyReader")

    assert result == {"key": "previous_value"}


def test_lookup_historical_settings_not_found_returns_none(
    controller: MainController,
) -> None:
    """
    Return None when no matching entry exists in either history.

    :param controller: Controller under test.
    """
    controller.plugin_history = {}
    controller.previous_plugin_history = {}

    result = controller._lookup_historical_settings("MetaReader", "MyReader")

    assert result is None


def test_handle_data_plugin_controller_signal_calls_method_and_callback(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Call a method on the data plugin controller and invoke the return callback.

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


def test_handle_data_plugin_controller_signal_missing_function_logs_and_returns(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Log an error and return early when the requested function does not exist
    on the data plugin controller, instead of raising out of the Qt slot.

    MagicMock auto-creates attributes by default, so we must configure
    getattr to explicitly return None for the missing function name to
    trigger the early-return branch.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.data_plugin_controller.configure_mock(**{"nonexistent_fn": None})
    return_cb = mocker.Mock()

    controller.handle_data_plugin_controller_signal(
        metaclass="MetaX",
        subclass_key="Key",
        call_function="nonexistent_fn",
        call_args=(),
        return_function=return_cb,
        ret_args=(),
    )

    return_cb.assert_not_called()
    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]


def test_handle_data_plugin_controller_signal_non_callable_logs_and_returns(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Log an error and return early when the resolved attribute is not callable,
    instead of raising out of the Qt slot.

    We set the attribute to an integer so callable(func) is False,
    triggering the early-return branch.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.data_plugin_controller.not_callable_attr = 42
    return_cb = mocker.Mock()

    controller.handle_data_plugin_controller_signal(
        metaclass="MetaX",
        subclass_key="Key",
        call_function="not_callable_attr",
        call_args=(),
        return_function=return_cb,
        ret_args=(),
    )

    return_cb.assert_not_called()
    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]


def test_update_available_plugins_caches_and_pushes_to_tabs(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Cache the plugin list and push it to all analysis tabs.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    tab = mocker.Mock()
    controller.analysis_tabs = {"X": tab}

    controller.update_available_plugins("MetaReader", ["R1", "R2"])

    assert controller.data_plugins["MetaReader"] == ["R1", "R2"]
    tab.update_available_plugins.assert_called_once_with(controller.data_plugins)


def test_update_available_plugins_skips_none_tabs(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Skip None tab entries when pushing plugin updates.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.analysis_tabs = {"X": None}

    controller.update_available_plugins("MetaReader", ["R1"])

    assert controller.data_plugins["MetaReader"] == ["R1"]


def test_save_session_with_provided_file(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    Save the plugin history to the specified file.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    controller.plugin_history = {"key": {"metaclass": "MetaReader"}}

    controller.save_session(save_file="test_session.json")

    mock_main_model.save_session.assert_called_once_with(
        controller.plugin_history, "test_session.json"
    )


def test_save_session_without_file(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    Save the plugin history with None as the file path when no file is provided.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    controller.plugin_history = {}

    controller.save_session()

    mock_main_model.save_session.assert_called_once_with({}, None)


def test_save_session_syncs_tab_state_before_saving(
    controller: MainController,
    mock_main_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Merge each open tab's extra session state into plugin history before saving.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mocker: Pytest-mock fixture.
    """
    controller.plugin_history = {"MetadataController": {"metaclass": "MetaController"}}
    tab = mocker.Mock()
    tab.get_session_state.return_value = {"subset_filters": {"f1": "voltage > 0"}}
    controller.analysis_tabs = {"MetadataController": tab}

    controller.save_session(save_file="test_session.json")

    assert controller.plugin_history["MetadataController"]["subset_filters"] == {
        "f1": "voltage > 0"
    }
    mock_main_model.save_session.assert_called_once_with(
        controller.plugin_history, "test_session.json"
    )


def test_sync_tab_session_state_into_history_ignores_tabs_with_no_state(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Leave a tab's history entry untouched when get_session_state returns nothing.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.plugin_history = {"RawDataController": {"metaclass": "MetaController"}}
    tab = mocker.Mock()
    tab.get_session_state.return_value = {}
    controller.analysis_tabs = {"RawDataController": tab}

    controller._sync_tab_session_state_into_history()

    assert controller.plugin_history["RawDataController"] == {
        "metaclass": "MetaController"
    }


def test_update_plugin_history_syncs_tab_session_state(
    controller: MainController,
    mock_main_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Merge live tab session state into history whenever plugin history autosaves.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mocker: Pytest-mock fixture.
    """
    controller.plugin_history = {"MetadataController": {"metaclass": "MetaController"}}
    tab = mocker.Mock()
    tab.get_session_state.return_value = {"subset_filters": {"f1": "voltage > 0"}}
    controller.analysis_tabs = {"MetadataController": tab}

    controller.update_plugin_history(None, "nonexistent_key")

    assert controller.plugin_history["MetadataController"]["subset_filters"] == {
        "f1": "voltage > 0"
    }


def test_save_tab_action_history_delegates_to_model(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    Forward the tab action history dict and save file to the model.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    history = {"SomeTab": {"action": "opened"}}

    controller.save_tab_action_history(history, save_file="session.json")

    mock_main_model.save_tab_actions.assert_called_once_with(history, "session.json")


def test_send_analysis_tabs_emits_to_view(
    controller: MainController,
    mock_main_view: MagicMock,
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


def test_send_analysis_tabs_does_not_warn_when_empty(
    controller: MainController,
    mock_main_view: MagicMock,
) -> None:
    """
    Having no analysis tabs is a normal state, so it must not log a warning.

    It is what the application looks like at startup and after a session reset.
    QtHandler promotes WARNING to a modal dialog, so warning here would pop a
    dialog at both of those moments.

    :param controller: Controller under test.
    :param mock_main_view: Mocked main view.
    """
    controller.analysis_tabs = {}

    controller.send_analysis_tabs()

    controller.logger.warning.assert_not_called()  # type: ignore[attr-defined]
    mock_main_view.received_analysis_tabs.emit.assert_called_once_with({})


def test_load_session_restores_tabs_and_plugins(
    mocker: MockerFixture,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
) -> None:
    """
    Restore MetaController tabs and non-controller plugins from saved history.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    dpc_cls = mocker.patch("poriscope.controllers.main_controller.DataPluginController")
    dpc_instance = dpc_cls.return_value

    ctrl = MainController(mock_main_model, mock_main_view)

    history: Dict[str, dict] = {
        "tab_key": {"metaclass": "MetaController", "subclass": "RawDataController"},
        "reader_key": {
            "metaclass": "MetaReader",
            "subclass": "MyReader",
            "settings": {"a": 1},
        },
    }
    mock_main_model.load_session.return_value = history

    tab_instance = mocker.Mock()
    tab_instance.view = mocker.Mock()
    tab_instance.global_signal = mocker.Mock(connect=mocker.Mock())
    tab_instance.create_plugin = mocker.Mock(connect=mocker.Mock())
    tab_instance.data_plugin_controller_signal = mocker.Mock(connect=mocker.Mock())
    tab_instance.add_text_to_display = mocker.Mock(connect=mocker.Mock())
    tab_instance.update_tab_action_history = mocker.Mock(connect=mocker.Mock())
    tab_instance.save_tab_action_history = mocker.Mock(connect=mocker.Mock())
    tab_instance.update_available_plugins = mocker.Mock()
    tab_instance.get_session_state.return_value = {}

    mock_main_model.get_plugin_classes.return_value = {
        "RawDataController": lambda available: tab_instance
    }
    mock_main_model.get_available_plugins.return_value = {}

    ctrl.load_session("session.json")

    assert "RawDataController" in ctrl.analysis_tabs
    dpc_instance.validate_and_instantiate_plugin.assert_any_call(
        metaclass="MetaReader",
        subclass="MyReader",
        settings={"a": 1},
        key="reader_key",
    )


def test_load_session_restores_subset_filters_for_newly_created_tab(
    mocker: MockerFixture,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
) -> None:
    """
    Restore saved subset filters onto a tab that session load just instantiated.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    mocker.patch("poriscope.controllers.main_controller.DataPluginController")

    ctrl = MainController(mock_main_model, mock_main_view)

    history: Dict[str, dict] = {
        "tab_key": {
            "metaclass": "MetaController",
            "subclass": "MetadataController",
            "subset_filters": {"f1": "voltage > 0"},
        },
    }
    mock_main_model.load_session.return_value = history

    tab_instance = mocker.Mock()
    tab_instance.view = mocker.Mock()
    tab_instance.global_signal = mocker.Mock(connect=mocker.Mock())
    tab_instance.create_plugin = mocker.Mock(connect=mocker.Mock())
    tab_instance.data_plugin_controller_signal = mocker.Mock(connect=mocker.Mock())
    tab_instance.add_text_to_display = mocker.Mock(connect=mocker.Mock())
    tab_instance.update_tab_action_history = mocker.Mock(connect=mocker.Mock())
    tab_instance.save_tab_action_history = mocker.Mock(connect=mocker.Mock())
    tab_instance.update_available_plugins = mocker.Mock()
    # instantiate_analysis_tab's own update_plugin_history() call syncs session state
    # from every open tab, so this needs a real dict back, not an unconfigured Mock.
    tab_instance.get_session_state.return_value = {}

    mock_main_model.get_plugin_classes.return_value = {
        "MetadataController": lambda available: tab_instance
    }
    mock_main_model.get_available_plugins.return_value = {}

    ctrl.load_session("session.json")

    tab_instance.restore_session_state.assert_called_once_with(history["tab_key"])


def test_load_session_resets_an_already_open_tab_before_restoring(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Tear down an already-open tab via reset_session() before applying a load,
    rather than preserving its live state.

    A load always starts from a clean workspace now, the same as Reset
    Session does on its own - so the previously-open tab is closed (its
    workers killed) rather than left alone, and the freshly created
    replacement is what gets the saved state restored onto it.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    existing_tab = mocker.Mock()
    controller.analysis_tabs = {"MetadataController": existing_tab}
    controller.data_plugin_controller.delete_all_plugins.return_value = []

    new_tab = mocker.Mock()
    new_tab.get_session_state.return_value = {}
    controller.instantiate_analysis_tab = mocker.Mock(
        side_effect=lambda subclass: controller.analysis_tabs.__setitem__(
            subclass, new_tab
        )
    )

    loaded_history = {
        "tab_key": {
            "metaclass": "MetaController",
            "subclass": "MetadataController",
            "subset_filters": {"f1": "voltage > 0"},
        }
    }
    controller.main_model.load_session = mocker.Mock(return_value=loaded_history)

    controller.load_session("session.json")

    existing_tab.handle_kill_all_workers.assert_called_once_with(
        "MetadataController", exiting=True
    )
    existing_tab.restore_session_state.assert_not_called()
    new_tab.restore_session_state.assert_called_once_with(loaded_history["tab_key"])


def test_load_session_returns_early_when_history_is_none(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Return early and log info when load_session returns None.

    A failed load must not tear down the current workspace for nothing -
    reset_session() is only worth running once there is something to apply.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.main_model.load_session = mocker.Mock(return_value=None)
    controller.plugin_history = {}
    reset_spy = mocker.patch.object(controller, "reset_session")

    controller.load_session("file.json")

    controller.main_model.save_session.assert_not_called()
    reset_spy.assert_not_called()


def test_load_session_resets_before_applying_the_loaded_history(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Clear the current workspace before restoring anything from a load.

    Applying a loaded session on top of whatever is already instantiated
    collided with anything already registered under the same key or name -
    a plugin key already taken, a named filter already added - and surfaced
    as an "already exists" error for state the user never meant to keep.
    Both "Load Session" and "Restore Session" go through this same method,
    so this covers both.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    order: List[str] = []
    mocker.patch.object(
        controller, "reset_session", side_effect=lambda: order.append("reset")
    )
    loaded_history = {
        "reader_key": {
            "metaclass": "MetaReader",
            "subclass": "MyReader",
            "settings": {},
        }
    }
    controller.main_model.load_session = mocker.Mock(return_value=loaded_history)
    controller.data_plugin_controller.validate_and_instantiate_plugin = mocker.Mock(
        side_effect=lambda **kwargs: order.append("restore")
    )

    controller.load_session("session.json")

    assert order == ["reset", "restore"]
    assert controller.plugin_history == loaded_history


def test_load_session_displays_the_loaded_file_name(
    controller: MainController,
    mock_main_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Name the loaded file on the status/log panel, since reset_session()
    already left its own message there clearing the previous workspace.

    :param controller: Controller under test.
    :param mock_main_view: Mocked main view.
    :param mocker: Pytest-mock fixture.
    """
    mocker.patch.object(controller, "reset_session")
    controller.main_model.load_session = mocker.Mock(return_value={})

    controller.load_session("my_session.json")

    mock_main_view.add_text_to_display.assert_called_once_with(
        "Loaded session from my_session.json.", "MainController"
    )


def test_load_session_displays_a_restored_message_with_no_file_name(
    controller: MainController,
    mock_main_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Report "Restore Session" (file_name=None) distinctly from a chosen file.

    :param controller: Controller under test.
    :param mock_main_view: Mocked main view.
    :param mocker: Pytest-mock fixture.
    """
    mocker.patch.object(controller, "reset_session")
    controller.main_model.load_session = mocker.Mock(return_value={})

    controller.load_session(None)

    mock_main_view.add_text_to_display.assert_called_once_with(
        "Restored last saved session.", "MainController"
    )


def test_load_session_logs_error_on_analysis_tab_failure(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Log an error and continue when instantiate_analysis_tab raises.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # A separate dict, not controller.plugin_history itself: reset_session()
    # now runs before this is applied and clears that dict in place, which
    # would otherwise wipe out the same object this mock returns.
    loaded_history = {"key1": {"metaclass": "MetaController", "subclass": "SomeTab"}}
    controller.main_model.load_session = mocker.Mock(return_value=loaded_history)
    controller.instantiate_analysis_tab = mocker.Mock(side_effect=RuntimeError("fail"))

    controller.load_session("session.json")

    controller.instantiate_analysis_tab.assert_called_once_with("SomeTab")


def test_load_session_logs_error_on_other_value_error(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Log an error when validate_and_instantiate_plugin raises a different ValueError.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # A separate dict, not controller.plugin_history itself: reset_session()
    # now runs before this is applied and clears that dict in place, which
    # would otherwise wipe out the same object this mock returns.
    loaded_history = {
        "key2": {"metaclass": "MetaReader", "subclass": "MyReader", "settings": {}}
    }
    controller.main_model.load_session = mocker.Mock(return_value=loaded_history)
    controller.data_plugin_controller.validate_and_instantiate_plugin = mocker.Mock(
        side_effect=ValueError("some other error")
    )

    controller.load_session("session.json")

    controller.logger.error.assert_called()  # type: ignore[attr-defined]


def test_load_session_logs_error_on_unexpected_plugin_exception(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Log an error and continue when an unexpected exception occurs during plugin restore.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    # A separate dict, not controller.plugin_history itself: reset_session()
    # now runs before this is applied and clears that dict in place, which
    # would otherwise wipe out the same object this mock returns.
    loaded_history = {
        "key2": {"metaclass": "MetaReader", "subclass": "MyReader", "settings": {}}
    }
    controller.main_model.load_session = mocker.Mock(return_value=loaded_history)
    controller.data_plugin_controller.validate_and_instantiate_plugin = mocker.Mock(
        side_effect=RuntimeError("unexpected")
    )

    controller.load_session("session.json")

    controller.logger.error.assert_called()  # type: ignore[attr-defined]


def test_handle_global_signal_outer_except_swallows_exception(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Swallow and log an exception raised while resolving the target instance.

    The outer bare except catches anything that escapes the inner blocks, including a
    failure of the instance lookup itself: ``DataPluginModel.get_plugin_instance``
    subscripts ``self.plugins[metaclass]`` and so raises KeyError for an unregistered
    metaclass, which must not escape into the Qt caller.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.data_plugin_controller.get_plugin_instance = mocker.Mock(
        side_effect=KeyError("MetaTypo")
    )

    # Should not raise - the outer guard catches it and logs with a traceback
    controller.handle_global_signal("MetaX", "Key", "fn", (), None, ())

    controller.logger.exception.assert_called_once()  # type: ignore[attr-defined]


def test_handle_data_plugin_controller_signal_callback_exception_is_logged_and_swallowed(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Log a raising return callback with its traceback and swallow it, rather than letting
    it propagate out of the Qt slot.

    This path used to use ``logger.error``, losing the stack, while the global_signal
    path used ``logger.exception``. Both now share one dispatch body, so they cannot
    diverge again.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.data_plugin_controller.some_method = mocker.Mock(return_value="ok")
    return_cb = mocker.Mock(side_effect=RuntimeError("callback blew up"))

    # Should not raise -- the exception is caught and logged
    controller.handle_data_plugin_controller_signal(
        metaclass="MetaX",
        subclass_key="Key",
        call_function="some_method",
        call_args=(),
        return_function=return_cb,
        ret_args=(),
    )

    controller.logger.exception.assert_called_once()  # type: ignore[attr-defined]


def test_update_plugin_history_rename_preserves_other_entries(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    Cover the ``else: new_history[key] = val`` branch in update_plugin_history.

    When both history and delete_key are provided, entries that do NOT match
    delete_key must be copied unchanged into new_history.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    controller.plugin_history = {
        "old_key": {"subclass": "Sub", "metaclass": "Meta"},
        "other_key": {"subclass": "Other", "metaclass": "Meta"},
    }

    controller.update_plugin_history(
        {"key": "new_key", "subclass": "Sub", "metaclass": "Meta"}, "old_key"
    )

    # Renamed entry present
    assert "new_key" in controller.plugin_history
    # Old key removed
    assert "old_key" not in controller.plugin_history
    # Unrelated entry preserved via the else branch
    assert "other_key" in controller.plugin_history
    mock_main_model.save_session.assert_called()


class TestResetSession:
    """
    Returning the workspace to its freshly-launched state.

    The saved session surviving is the whole point: Reset Session is meant to be
    reversible via Restore Session. Both histories persist themselves on every
    change, and teardown emits one history update per deleted plugin, so without
    a guard the reset writes an empty session over the file it is supposed to
    leave alone.
    """

    def test_clears_the_in_memory_workspace(self, controller):
        controller.plugin_history = {"reader_1": {"metaclass": "MetaReader"}}
        controller.tab_action_history = {"RawDataController": ["action"]}
        controller.analysis_tabs = {"RawDataController": MagicMock()}
        controller.data_plugin_controller.delete_all_plugins.return_value = []

        controller.reset_session()

        assert controller.plugin_history == {}
        assert controller.tab_action_history == {}
        assert controller.analysis_tabs == {}

    def test_does_not_overwrite_the_saved_session(self, controller):
        controller.plugin_history = {"reader_1": {"metaclass": "MetaReader"}}
        # deleting a plugin emits a history update, exactly as delete_plugin does
        controller.data_plugin_controller.delete_all_plugins.side_effect = lambda: (
            controller.update_plugin_history(None, "reader_1"),
            [],
        )[1]

        controller.reset_session()

        assert not controller.main_model.save_session.called
        assert not controller.main_model.save_tab_actions.called

    def test_saving_resumes_after_the_reset(self, controller):
        controller.data_plugin_controller.delete_all_plugins.return_value = []
        controller.reset_session()

        controller.update_plugin_history({"key": "reader_1"}, None)

        assert controller.main_model.save_session.called
        assert controller._suppress_session_save is False

    def test_guard_is_released_even_if_teardown_raises(self, controller):
        controller.data_plugin_controller.delete_all_plugins.side_effect = RuntimeError(
            "boom"
        )

        with pytest.raises(RuntimeError):
            controller.reset_session()

        assert controller._suppress_session_save is False

    def test_stops_workers_before_deleting_the_plugins_they_run_against(
        self, controller
    ):
        # Ordering is the whole point: deleting a plugin closes its resources, so
        # a worker still running against one would be reading from a handle that
        # has just been closed. Killing workers afterwards would be useless.
        order = []
        tab = MagicMock()
        tab.handle_kill_all_workers.side_effect = lambda *a, **k: order.append("kill")
        controller.analysis_tabs = {"RawDataController": tab}
        controller.data_plugin_controller.delete_all_plugins.side_effect = lambda: (
            order.append("delete"),
            [],
        )[1]

        controller.reset_session()

        assert order == ["kill", "delete"]

    def test_waits_for_workers_rather_than_only_signalling_them(self, controller):
        # exiting=True is what blocks until the thread actually finishes.
        # Signalling without waiting would let a worker outlive the plugin.
        tab = MagicMock()
        controller.analysis_tabs = {"RawDataController": tab}
        controller.data_plugin_controller.delete_all_plugins.return_value = []

        controller.reset_session()

        tab.handle_kill_all_workers.assert_called_once_with(
            "RawDataController", exiting=True
        )

    def test_cancels_a_walkthrough_before_returning_to_the_landing_page(
        self, controller
    ):
        # Ordering matters: switch_to_page is refused while a walkthrough is
        # active, so cancelling afterwards would leave the user on a page the
        # teardown had already destroyed.
        order = []
        controller.main_view.cancel_walkthrough.side_effect = lambda: order.append(
            "cancel"
        )
        controller.main_view.switch_to_page.side_effect = lambda _p: order.append(
            "switch"
        )
        controller.data_plugin_controller.delete_all_plugins.return_value = []

        controller.reset_session()

        assert order == ["cancel", "switch"]

    def test_returns_to_the_landing_page(self, controller):
        controller.data_plugin_controller.delete_all_plugins.return_value = []

        controller.reset_session()

        controller.main_view.remove_pages_except.assert_called_once_with(["MainView"])
        controller.main_view.switch_to_page.assert_called_once_with("MainView")

    def test_closes_settings_before_removing_its_page(self, controller):
        # Settings' widget is a singleton, not disposable like an analysis
        # tab's view - it has to be detached before remove_pages_except would
        # otherwise destroy it along with its wrapper.
        controller.data_plugin_controller.delete_all_plugins.return_value = []
        order = []
        controller.main_view.close_settings_page.side_effect = lambda: order.append(
            "detach"
        )
        controller.main_view.remove_pages_except.side_effect = (
            lambda _keep: order.append("remove")
        )

        controller.reset_session()

        assert order == ["detach", "remove"]

    def test_clears_the_sidebar_highlight_and_the_display_panel(self, controller):
        # A landing page with nothing open should not still show whichever
        # section, or whichever logged messages, were there before the reset.
        controller.data_plugin_controller.delete_all_plugins.return_value = []

        controller.reset_session()

        assert controller.main_view.clear_sidebar_highlight.called
        assert controller.main_view.clear_display.called

    def test_collapses_the_sidebar_and_closes_the_help_window(self, controller):
        # Neither follows from tearing down tabs and plugins: an expanded
        # sidebar and an open Help window are untouched by that teardown.
        controller.data_plugin_controller.delete_all_plugins.return_value = []

        controller.reset_session()

        assert controller.main_view.reset_sidebar_layout.called
        assert controller.main_view.close_help_window.called

    def test_rescans_the_plugin_menus(self, controller):
        # populate_available_plugins() otherwise only ever runs once, at
        # startup, so a plugin file added mid-session would stay invisible
        # in the menus after a reset unless this re-scans too.
        controller.data_plugin_controller.delete_all_plugins.return_value = []

        controller.reset_session()

        assert controller.main_model.refresh_available_plugins.called
        assert controller.data_plugin_controller.set_available_plugins.called
        assert controller.main_view.refresh_available_plugins.called

    def test_names_plugins_it_could_not_delete(self, controller):
        controller.data_plugin_controller.delete_all_plugins.return_value = ["stuck_1"]

        controller.reset_session()

        message = controller.main_view.add_text_to_display.call_args.args[0]
        assert "stuck_1" in message


class TestRefreshAvailablePlugins:
    """
    Propagating a re-scan to everyone holding a copy of the plugin list.

    The scan runs once in MainModel's constructor and its results are copied into
    three places, so refreshing the model alone changes nothing a user can see.
    """

    def test_changing_the_plugin_folder_triggers_a_rescan(self, controller):
        controller.update_user_plugin_location("/some/new/folder")

        assert controller.main_model.refresh_available_plugins.called

    def test_rescan_reaches_the_data_plugin_controller_and_the_view(self, controller):
        controller.refresh_available_plugins()

        assert controller.data_plugin_controller.set_available_plugins.called
        assert controller.main_view.refresh_available_plugins.called

    def test_rescan_happens_after_the_config_is_written(self, controller):
        # The scan reads "User Plugin Folder" back out of the config, so writing
        # it afterwards would re-scan the old location.
        order = []
        controller.main_model.update_app_config.side_effect = lambda *a: order.append(
            "config"
        )
        controller.main_model.refresh_available_plugins.side_effect = (
            lambda: order.append("scan")
        )

        controller.update_user_plugin_location("/some/new/folder")

        assert order == ["config", "scan"]
