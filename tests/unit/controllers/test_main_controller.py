"""
Tests for poriscope.controllers.main_controller.MainController.

Covers:
- instantiate_analysis_tab (new tab, existing tab, sidebar highlight, instantiation error)
- update_plugin_history CRUD (add, delete, rename, save_session called, tab state synced)
- update_tab_action_history stores and saves
- setup_connections signal wiring
- handle_about_to_quit flushes session state, stops workers and calls handle_exit
- send_curent_data_server delegates to model and view
- send_curent_user_plugin_location delegates to model and view
- update_data_server_location delegates to model and data_plugin_controller
- update_user_plugin_location adds the folder and its parent to sys.path, once
- _lookup_historical_settings (found in current, found in previous, not found)
- update_available_plugins caches and pushes to tabs
- save_session (with file, without file, tab state synced first)
- load_session (restore tabs, plugins and subset filters, reset first, None history,
  tab error, plugin ValueError, plugin other error, report of unrestored entries)
- send_analysis_tabs (tabs present, tabs empty)
- reset_session, refresh_available_plugins and _renamed_history
"""

from __future__ import annotations

import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Tuple
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import LoadedSession, SessionRefused

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
    model.get_plugin_classes.return_value = {
        "RawDataController": lambda available_plugins: MagicMock(view=MagicMock())
    }
    model.get_data_server_location.return_value = "/tmp/data"
    model.load_session.return_value = LoadedSession()
    model.old_action_history_exists.return_value = False
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
    # The restore dialog: by default nothing is ticked, as Not now answers.
    view.ask_which_tabs_to_replay = mocker.Mock(return_value=[])
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


def test_a_history_change_saves_the_session_with_each_tabs_kept_actions(
    controller: MainController,
    mock_main_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    The tab's kept actions go in its entry of the one session file, with the last tab.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mocker: Pytest-mock fixture.
    """
    kept = [{"action": "overlay_plot", "args": [], "kwargs": {"loader": "DB1"}}]
    controller.plugin_history = {
        "MetadataController": {
            "metaclass": "MetaController",
            "subclass": "MetadataController",
        }
    }
    tab = mocker.Mock()
    tab.get_session_state.return_value = {}
    tab.kept_actions.return_value = kept
    controller.analysis_tabs = {"MetadataController": tab}

    controller.update_tab_action_history("MetadataController", OrderedDict())

    assert controller.last_tab == "MetadataController"
    assert controller.plugin_history["MetadataController"]["actions"] == kept
    mock_main_model.save_session.assert_called_once_with(
        controller.plugin_history, last_tab="MetadataController"
    )


def test_every_open_tab_saves_its_actions_with_any_session_save(
    controller: MainController,
    mock_main_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Save Session, and the autosave after a plugin change, carry every tab's actions too.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    :param mocker: Pytest-mock fixture.
    """
    controller.plugin_history = {
        "RawDataController": {
            "metaclass": "MetaController",
            "subclass": "RawDataController",
        },
        "R1": {"metaclass": "MetaReader", "subclass": "SomeReader"},
    }
    tab = mocker.Mock()
    tab.get_session_state.return_value = {}
    tab.kept_actions.return_value = []
    tab.session_actions.return_value = None  # not loaded from a session
    controller.analysis_tabs = {"RawDataController": tab}

    controller.save_session("session.json")

    assert controller.plugin_history["RawDataController"]["actions"] == []
    assert "actions" not in controller.plugin_history["R1"]


def test_a_tabs_actions_are_saved_even_when_its_own_session_state_is_overridden(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Metadata and Protein override ``get_session_state`` without calling the base, so
    the actions are written beside it, not through it.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.plugin_history = {
        "MetadataController": {
            "metaclass": "MetaController",
            "subclass": "MetadataController",
        }
    }
    tab = mocker.Mock()
    tab.get_session_state.return_value = {"subset_filters": {"f": "x > 1"}}
    tab.kept_actions.return_value = [{"action": "reset", "args": [], "kwargs": {}}]
    tab.session_actions.return_value = None  # not loaded from a session
    controller.analysis_tabs = {"MetadataController": tab}

    controller.save_session("session.json")

    entry = controller.plugin_history["MetadataController"]
    assert entry["subset_filters"] == {"f": "x > 1"}
    assert entry["actions"] == [{"action": "reset", "args": [], "kwargs": {}}]


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
        controller.plugin_history, None, ""
    )


def test_quitting_with_nothing_open_does_not_overwrite_the_session(
    controller: MainController,
    mock_main_model: MagicMock,
) -> None:
    """
    An empty history on quit is not saved over the last real session.

    Quitting straight after launch, or after Reset Session, wrote ``{}`` over the
    session file, so the next Restore brought back nothing - though the reset tells the
    user saved files are untouched. An empty history is either already saved (every
    delete autosaves) or means nothing happened, so there is nothing to flush.

    :param controller: Controller under test.
    :param mock_main_model: Mocked main model.
    """
    controller.plugin_history = {}
    controller.analysis_tabs = {}
    controller.data_plugin_controller.handle_exit = MagicMock()

    controller.handle_about_to_quit()

    mock_main_model.save_session.assert_not_called()


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


def test_update_user_plugin_location_adds_the_folder_itself_to_syspath(
    controller: MainController,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    The folder goes on sys.path too, so a multi-file plugin can import its own parts.

    Pointing the app at a folder whose name is not a Python identifier - "User Plugins",
    as a real installation had it - leaves the parent entry useless, because no import
    can name the folder. The folder itself works whatever it is called.

    :param controller: Controller under test.
    :param monkeypatch: Pytest monkeypatch fixture.
    :param tmp_path: Temporary directory fixture.
    """
    plugins_dir = tmp_path / "User Plugins"
    plugins_dir.mkdir()

    monkeypatch.setattr(sys, "path", list(sys.path))
    folder = str(plugins_dir.resolve())
    if folder in sys.path:
        sys.path.remove(folder)

    controller.update_user_plugin_location(str(plugins_dir))

    assert folder in sys.path


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
        controller.plugin_history, "test_session.json", ""
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

    mock_main_model.save_session.assert_called_once_with({}, None, "")


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
        controller.plugin_history, "test_session.json", ""
    )


def test_sync_tab_session_state_into_history_ignores_tabs_with_no_state(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    A tab with no extra state gets only its actions in its history entry.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.plugin_history = {"RawDataController": {"metaclass": "MetaController"}}
    tab = mocker.Mock()
    tab.get_session_state.return_value = {}
    tab.kept_actions.return_value = []
    tab.session_actions.return_value = None  # not loaded from a session
    controller.analysis_tabs = {"RawDataController": tab}

    controller._sync_tab_session_state_into_history()

    assert controller.plugin_history["RawDataController"] == {
        "metaclass": "MetaController",
        "actions": [],
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
    mock_main_model.load_session.return_value = LoadedSession(history)

    tab_instance = mocker.Mock()
    tab_instance.view = mocker.Mock()
    tab_instance.create_plugin = mocker.Mock(connect=mocker.Mock())
    tab_instance.add_text_to_display = mocker.Mock(connect=mocker.Mock())
    tab_instance.update_tab_action_history = mocker.Mock(connect=mocker.Mock())
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
    mock_main_model.load_session.return_value = LoadedSession(history)

    tab_instance = mocker.Mock()
    tab_instance.view = mocker.Mock()
    tab_instance.create_plugin = mocker.Mock(connect=mocker.Mock())
    tab_instance.add_text_to_display = mocker.Mock(connect=mocker.Mock())
    tab_instance.update_tab_action_history = mocker.Mock(connect=mocker.Mock())
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


def test_load_session_persists_restored_tab_state_before_returning(
    mocker: MockerFixture,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
) -> None:
    """
    Write the restored tabs' own state back into the saved session, not an empty copy.

    Restoring a tab takes two steps, and only the first of them refreshes
    plugin_history: instantiate_analysis_tab ends on update_plugin_history, which
    snapshots every open tab while this one's filter list is still empty, and
    restore_session_state fills it in afterwards. Each tab's entry was therefore
    only corrected by the sync the *next* tab's instantiation happened to trigger,
    so the last tab restored was saved with no subset filters and lost them on the
    following restore - which is why Metadata kept its filters and Protein, opened
    and so restored second, did not.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    mocker.patch("poriscope.controllers.main_controller.DataPluginController")

    ctrl = MainController(mock_main_model, mock_main_view)

    history: Dict[str, dict] = {
        "MetadataController": {
            "metaclass": "MetaController",
            "subclass": "MetadataController",
            "subset_filters": {"f1": "voltage > 0"},
        },
    }
    mock_main_model.load_session.return_value = LoadedSession(history)

    # A tab that answers get_session_state from what it was actually restored with,
    # the way MetaSubsetTabController does. A Mock returning a fixed dict would pass
    # whether or not the restore had happened yet, which is the whole question here.
    restored: Dict[str, str] = {}

    tab_instance = mocker.Mock()
    tab_instance.view = mocker.Mock()
    for signal in (
        "create_plugin",
        "plugin_state_changed",
        "add_text_to_display",
        "update_tab_action_history",
    ):
        setattr(tab_instance, signal, mocker.Mock(connect=mocker.Mock()))
    tab_instance.update_available_plugins = mocker.Mock()
    tab_instance.restore_session_state.side_effect = lambda state: restored.update(
        state.get("subset_filters", {})
    )
    tab_instance.get_session_state.side_effect = lambda: {
        "subset_filters": dict(restored)
    }

    mock_main_model.get_plugin_classes.return_value = {
        "MetadataController": lambda available: tab_instance
    }
    mock_main_model.get_available_plugins.return_value = {}

    ctrl.load_session("session.json")

    saved = mock_main_model.save_session.call_args_list[-1][0][0]
    assert saved["MetadataController"]["subset_filters"] == {"f1": "voltage > 0"}


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
    controller.main_model.load_session = mocker.Mock(
        return_value=LoadedSession(loaded_history)
    )

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
    Return early when the model refuses the file.

    A failed load must not tear down the current workspace for nothing -
    reset_session() is only worth running once there is something to apply.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.main_model.load_session = mocker.Mock(
        side_effect=SessionRefused("it does not hold a Poriscope session")
    )
    controller.plugin_history = {}
    reset_spy = mocker.patch.object(controller, "reset_session")

    controller.load_session("file.json")

    controller.main_model.save_session.assert_not_called()
    reset_spy.assert_not_called()


def test_a_chosen_file_that_is_not_a_session_is_reported_as_an_error(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    The user picked this file, so failing to load it gets a dialog, not silence.

    It used to log at INFO, below the default level, so nothing reached the user. ERROR
    is what QtHandler raises a dialog for.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.main_model.load_session = mocker.Mock(
        side_effect=SessionRefused("it does not hold a Poriscope session")
    )

    controller.load_session("not_a_session.json")

    controller.logger.error.assert_called_once()
    assert controller.logger.error.call_args[0][0] == (
        "not_a_session.json was not loaded: it does not hold a Poriscope session"
    )


def test_restore_of_a_session_it_cannot_read_says_why_on_the_status_panel(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    A saved session Restore cannot read is not "nothing saved": the panel gives the reason.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.main_model.load_session = mocker.Mock(
        side_effect=SessionRefused(
            "it was saved by Poriscope 9.9 in a session format this version does not "
            "read (format 3)"
        )
    )

    controller.load_session(None)

    controller.logger.error.assert_not_called()
    controller.main_view.add_text_to_display.assert_called_once_with(
        "The last saved session was not restored: it was saved by Poriscope 9.9 in a "
        "session format this version does not read (format 3)",
        "MainController",
    )


def test_restore_with_no_saved_session_says_so_on_the_status_panel(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Nothing to restore is routine, so it is a warning on the panel, not a dialog.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.main_model.load_session = mocker.Mock(
        side_effect=SessionRefused("there is no saved session", missing=True)
    )

    controller.load_session(None)

    controller.logger.error.assert_not_called()
    controller.logger.warning.assert_called_once()
    controller.main_view.add_text_to_display.assert_called_once_with(
        "There is no saved session to restore", "MainController"
    )


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
    controller.main_model.load_session = mocker.Mock(
        return_value=LoadedSession(loaded_history)
    )
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
    controller.main_model.load_session = mocker.Mock(return_value=LoadedSession())

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
    controller.main_model.load_session = mocker.Mock(return_value=LoadedSession())

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
    controller.main_model.load_session = mocker.Mock(
        return_value=LoadedSession(loaded_history)
    )
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
    controller.main_model.load_session = mocker.Mock(
        return_value=LoadedSession(loaded_history)
    )
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
    controller.main_model.load_session = mocker.Mock(
        return_value=LoadedSession(loaded_history)
    )
    controller.data_plugin_controller.validate_and_instantiate_plugin = mocker.Mock(
        side_effect=RuntimeError("unexpected")
    )

    controller.load_session("session.json")

    controller.logger.error.assert_called()  # type: ignore[attr-defined]


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
        controller.analysis_tabs = {"RawDataController": MagicMock()}
        controller.data_plugin_controller.delete_all_plugins.return_value = []

        controller.reset_session()

        assert controller.plugin_history == {}
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


# ------------- the session-restore summary --------------------------------


def test_load_session_reports_entries_that_could_not_be_restored(
    mocker: MockerFixture,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
) -> None:
    """
    A partial restore says so, instead of signing off with an unqualified success line.

    Loading a session written by an older Poriscope produced ten error messages
    and then "Loaded session from ...", because validate_and_instantiate_plugin
    reported internally and returned None, so the loop's own except never fired
    and nothing counted the failures.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    dpc_cls = mocker.patch("poriscope.controllers.main_controller.DataPluginController")
    dpc_cls.return_value.validate_and_instantiate_plugin.return_value = False

    ctrl = MainController(mock_main_model, mock_main_view)
    mock_main_model.load_session.return_value = LoadedSession(
        {
            "reader_key": {
                "metaclass": "MetaReader",
                "subclass": "ABF2Reader",
                "settings": {"a": 1},
            }
        }
    )
    mock_main_model.get_available_plugins.return_value = {}

    ctrl.load_session("session.json")

    messages = [c.args[0] for c in mock_main_view.add_text_to_display.call_args_list]
    assert any("1 of 1 entries could not be restored" in m for m in messages), messages
    assert any("reader_key" in m for m in messages), messages


def test_load_session_says_nothing_extra_when_every_entry_restored(
    mocker: MockerFixture,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
) -> None:
    """
    The ordinary case keeps its plain message, so the warning stays meaningful.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    dpc_cls = mocker.patch("poriscope.controllers.main_controller.DataPluginController")
    dpc_cls.return_value.validate_and_instantiate_plugin.return_value = True

    ctrl = MainController(mock_main_model, mock_main_view)
    mock_main_model.load_session.return_value = LoadedSession(
        {
            "reader_key": {
                "metaclass": "MetaReader",
                "subclass": "MyReader",
                "settings": {"a": 1},
            }
        }
    )
    mock_main_model.get_available_plugins.return_value = {}

    ctrl.load_session("session.json")

    messages = [c.args[0] for c in mock_main_view.add_text_to_display.call_args_list]
    assert "Loaded session from session.json." in messages, messages
    assert not any("could not be restored" in m for m in messages), messages


# ------------- renaming a plugin in the session history -------------------


class TestRenamedHistory:
    """Rebuilding the history with one entry renamed, in place."""

    def test_keeps_the_renamed_entry_where_the_old_one_sat(
        self,
        mocker: MockerFixture,
        mock_main_model: MagicMock,
        mock_main_view: MagicMock,
    ) -> None:
        """
        The reason this rebuilds rather than popping and reinserting.

        A plugin's place in the history is its place in the session file and in
        everything restored from it, so popping the old key and adding the new
        one would move the renamed plugin to the end - a rename would silently
        reorder the user's workspace.

        :param mocker: Pytest-mock fixture.
        :param mock_main_model: Mocked main model.
        :param mock_main_view: Mocked main view.
        """
        mocker.patch("poriscope.controllers.main_controller.DataPluginController")
        ctrl = MainController(mock_main_model, mock_main_view)
        ctrl.plugin_history = {"first": {}, "middle": {}, "last": {}}

        renamed = ctrl._renamed_history("middle", {"key": "renamed", "settings": {}})

        assert list(renamed) == ["first", "renamed", "last"]
        assert renamed["renamed"] == {"settings": {}}

    def test_leaves_the_history_alone_when_the_key_is_not_there(
        self,
        mocker: MockerFixture,
        mock_main_model: MagicMock,
        mock_main_view: MagicMock,
    ) -> None:
        """
        A rename away from a key that is gone drops the new entry rather than
        appending it, which is the pre-existing behaviour and is what stops a
        stale rename resurrecting a deleted plugin.

        :param mocker: Pytest-mock fixture.
        :param mock_main_model: Mocked main model.
        :param mock_main_view: Mocked main view.
        """
        mocker.patch("poriscope.controllers.main_controller.DataPluginController")
        ctrl = MainController(mock_main_model, mock_main_view)
        ctrl.plugin_history = {"first": {}, "second": {}}

        renamed = ctrl._renamed_history("gone", {"key": "renamed"})

        assert list(renamed) == ["first", "second"]


# ------------- the last tab travels with the session -------------------
def test_a_loaded_sessions_last_tab_is_saved_with_it(
    controller: MainController,
    mocker: MockerFixture,
) -> None:
    """
    Every save after a load carries the loaded session's last tab, and Save Session too.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.main_model.load_session = mocker.Mock(
        return_value=LoadedSession({}, "MetadataController")
    )

    controller.load_session("session.json")
    controller.save_session("copy.json")

    saves = controller.main_model.save_session.call_args_list
    assert saves
    for call in saves:
        last_tab = call.kwargs.get(
            "last_tab", call.args[2] if len(call.args) > 2 else None
        )
        assert last_tab == "MetadataController", call


def test_reset_session_forgets_the_last_tab(controller: MainController) -> None:
    """
    A clean workspace has no last tab.

    :param controller: Controller under test.
    """
    controller.last_tab = "MetadataController"
    controller.data_plugin_controller.delete_all_plugins.return_value = []

    controller.reset_session()

    assert controller.last_tab == ""


def test_a_refused_restore_at_startup_leaves_no_previous_settings(
    mocker: MockerFixture,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
) -> None:
    """
    The autosave read at startup is only for settings look-ups; a refusal is not an error.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    mocker.patch("poriscope.controllers.main_controller.DataPluginController")
    mock_main_model.load_session.side_effect = SessionRefused(
        "there is no saved session", missing=True
    )

    ctrl = MainController(mock_main_model, mock_main_view)

    assert ctrl.previous_plugin_history == {}


# ------------- a loaded session's actions -------------------
def _tab_entry(subclass: str, actions: object = None) -> Dict[str, object]:
    entry: Dict[str, object] = {"metaclass": "MetaController", "subclass": subclass}
    if actions is not None:
        entry["actions"] = actions
    return entry


def _loading_controller(
    mocker: MockerFixture,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
    history: Dict[str, object],
) -> MainController:
    """
    A shell whose tabs are mocks that hold what they are handed, loading ``history``.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    :param history: the session the model hands back
    :return: the controller, the session loaded
    """
    mocker.patch("poriscope.controllers.main_controller.DataPluginController")
    tabs: Dict[str, MagicMock] = {}

    def make_tab(available_plugins: object) -> MagicMock:
        tab = mocker.Mock()
        tab.view = mocker.Mock()
        tab.get_session_state.return_value = {}
        tab.kept_actions.return_value = [{"action": "live", "args": [], "kwargs": {}}]
        held: Dict[str, object] = {}
        tab.hold_session_actions.side_effect = lambda entries, source: held.update(
            entries=entries
        )
        tab.session_actions.side_effect = lambda: held.get("entries")
        tabs[str(len(tabs))] = tab
        return tab

    mock_main_model.get_plugin_classes.return_value = {
        name: make_tab for name in ("MetadataController", "RawDataController")
    }
    ctrl = MainController(mock_main_model, mock_main_view)
    mock_main_model.load_session.return_value = LoadedSession(history)
    return ctrl


def test_a_loaded_session_hands_each_tab_its_actions_once(
    mocker: MockerFixture, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    Read from the loaded entry itself: opening the tab replaces its history entry.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    entries = [{"action": "overlay_plot", "args": [], "kwargs": {}}]
    ctrl = _loading_controller(
        mocker,
        mock_main_model,
        mock_main_view,
        {"MetadataController": _tab_entry("MetadataController", entries)},
    )

    ctrl.load_session("session.json")

    tab = ctrl.analysis_tabs["MetadataController"]
    tab.hold_session_actions.assert_called_once_with(entries, "session.json")
    assert mock_main_model.load_session.call_count == 2  # startup, then this load


def test_the_autosave_after_a_load_holds_the_loaded_actions(
    mocker: MockerFixture, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    Restore gives you what you had: until its history changes, a tab saves what it loaded.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    entries = [{"action": "overlay_plot", "args": [], "kwargs": {}}]
    ctrl = _loading_controller(
        mocker,
        mock_main_model,
        mock_main_view,
        {"MetadataController": _tab_entry("MetadataController", entries)},
    )

    ctrl.load_session(None)

    saved = mock_main_model.save_session.call_args_list[-1].args[0]
    assert saved["MetadataController"]["actions"] == entries


def test_after_its_history_changes_a_tab_saves_what_it_ran(
    mocker: MockerFixture, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    The autosave holds only what ran, once the tab's history has changed since the load.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    entries = [{"action": "overlay_plot", "args": [], "kwargs": {}}]
    ctrl = _loading_controller(
        mocker,
        mock_main_model,
        mock_main_view,
        {
            "MetadataController": _tab_entry("MetadataController", entries),
            "RawDataController": _tab_entry("RawDataController", entries),
        },
    )
    ctrl.load_session("session.json")

    ctrl.update_tab_action_history("MetadataController", OrderedDict())

    saved = mock_main_model.save_session.call_args_list[-1].args[0]
    assert saved["MetadataController"]["actions"] == [
        {"action": "live", "args": [], "kwargs": {}}
    ]
    assert saved["RawDataController"]["actions"] == entries


def test_a_history_change_during_the_load_is_not_the_users_work(
    mocker: MockerFixture, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    Anything a tab records while it is being restored is part of the load.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    entries = [{"action": "overlay_plot", "args": [], "kwargs": {}}]
    ctrl = _loading_controller(
        mocker,
        mock_main_model,
        mock_main_view,
        {"MetadataController": _tab_entry("MetadataController", entries)},
    )
    original = ctrl.instantiate_analysis_tab

    def instantiate_then_record(subclass: str) -> None:
        original(subclass)
        ctrl.update_tab_action_history(subclass, OrderedDict())

    mocker.patch.object(ctrl, "instantiate_analysis_tab", instantiate_then_record)

    ctrl.load_session("session.json")

    saved = mock_main_model.save_session.call_args_list[-1].args[0]
    assert saved["MetadataController"]["actions"] == entries


def test_a_session_whose_tabs_hold_no_actions_says_so(
    mocker: MockerFixture, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    A session saved before actions were kept loads its plugins and says it has none.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    ctrl = _loading_controller(
        mocker,
        mock_main_model,
        mock_main_view,
        {"MetadataController": _tab_entry("MetadataController")},
    )

    ctrl.load_session("session.json")

    messages = [c.args[0] for c in mock_main_view.add_text_to_display.call_args_list]
    assert messages[-1] == (
        "Loaded session from session.json. This session has no saved actions to replay."
    )


@pytest.mark.parametrize(
    "history",
    [
        {"MetadataController": _tab_entry("MetadataController", [])},
        {},
    ],
    ids=["empty-actions", "no-tab"],
)
def test_a_session_with_nothing_to_replay_but_actions_kept_says_nothing_extra(
    mocker: MockerFixture,
    mock_main_model: MagicMock,
    mock_main_view: MagicMock,
    history: Dict[str, object],
) -> None:
    """
    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    :param history: the session loaded
    """
    ctrl = _loading_controller(mocker, mock_main_model, mock_main_view, history)

    ctrl.load_session("session.json")

    messages = [c.args[0] for c in mock_main_view.add_text_to_display.call_args_list]
    assert messages[-1] == "Loaded session from session.json."


def test_a_restore_with_the_old_action_autosave_says_it_cannot_be_replayed(
    mocker: MockerFixture, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    The first Restore after upgrading from 2.0 says where the old history went.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    ctrl = _loading_controller(
        mocker,
        mock_main_model,
        mock_main_view,
        {"MetadataController": _tab_entry("MetadataController")},
    )
    mock_main_model.old_action_history_exists.return_value = True

    ctrl.load_session(None)

    messages = [c.args[0] for c in mock_main_view.add_text_to_display.call_args_list]
    assert messages[-1] == (
        "Restored last saved session. This session has no saved actions to replay. "
        "The action history saved by an earlier version (tab_action_history.json) "
        "cannot be replayed. The autosave has been saved in this version's format, so "
        "this note will not appear again."
    )


def test_a_restore_without_the_old_file_still_says_the_autosave_was_converted(
    mocker: MockerFixture, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    Restore rewrites the autosave with each tab's actions, so the note does not come back.

    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    ctrl = _loading_controller(
        mocker,
        mock_main_model,
        mock_main_view,
        {"MetadataController": _tab_entry("MetadataController")},
    )

    ctrl.load_session(None)

    messages = [c.args[0] for c in mock_main_view.add_text_to_display.call_args_list]
    assert messages[-1] == (
        "Restored last saved session. This session has no saved actions to replay. "
        "The autosave has been saved in this version's format, so this note will not "
        "appear again."
    )


def test_loading_a_chosen_file_never_mentions_the_old_action_autosave(
    mocker: MockerFixture, mock_main_model: MagicMock, mock_main_view: MagicMock
) -> None:
    """
    :param mocker: Pytest-mock fixture.
    :param mock_main_model: Mocked main model.
    :param mock_main_view: Mocked main view.
    """
    ctrl = _loading_controller(
        mocker,
        mock_main_model,
        mock_main_view,
        {"MetadataController": _tab_entry("MetadataController")},
    )
    mock_main_model.old_action_history_exists.return_value = True

    ctrl.load_session("session.json")

    messages = [c.args[0] for c in mock_main_view.add_text_to_display.call_args_list]
    assert "tab_action_history.json" not in messages[-1]


# ------------- a plugin deleted, renamed or edited -------------------
def _plugin(key: str, value: object = 1, reader: str = "R1") -> Dict[str, object]:
    return {
        "key": key,
        "metaclass": "MetaEventFinder",
        "subclass": "SomeFinder",
        "settings": {
            "Threshold": {"Type": float, "Value": value},
            "MetaReader": {"Type": None, "Value": reader},
        },
    }


def _stored(entry: Dict[str, object]) -> Dict[str, object]:
    return {name: value for name, value in entry.items() if name != "key"}


@pytest.fixture
def shell(controller: MainController, mocker: MockerFixture) -> MainController:
    """
    A shell holding finder F1 on reader R1, writer W1 on F1, and one open tab.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    :return: the controller
    """
    controller.main_model.get_available_plugins.return_value = {
        "MetaReader": [],
        "MetaEventFinder": [],
        "MetaWriter": [],
    }
    controller.plugin_history = {"F1": _stored(_plugin("F1"))}
    finder, writer = mocker.Mock(), mocker.Mock()
    finder.get_dependents.return_value = {("MetaWriter", "W1")}
    writer.get_dependents.return_value = set()
    controller.data_plugin_controller.get_plugin_instances.return_value = {
        "MetaEventFinder": {"F1": finder, "F2": finder},
        "MetaWriter": {"W1": writer},
    }
    tab = mocker.Mock()
    tab.get_session_state.return_value = {}
    tab.session_actions.return_value = None
    tab.kept_actions.return_value = []
    tab.rewrite_plugin_entries.return_value = True
    controller.analysis_tabs = {"RawDataController": tab}
    return controller


def _rewrites(shell: MainController) -> List[object]:
    tab = shell.analysis_tabs["RawDataController"]
    return [call.args for call in tab.rewrite_plugin_entries.call_args_list]


def test_deleting_a_plugin_drops_its_entries_without_a_word(
    shell: MainController,
) -> None:
    shell.update_plugin_history({}, "F1")

    assert _rewrites(shell) == [("F1", None)]
    shell.main_view.add_text_to_display.assert_not_called()


def test_renaming_a_plugin_without_changing_a_setting_rewrites_its_entries(
    shell: MainController,
) -> None:
    shell.update_plugin_history(_plugin("F2"), "F1")

    assert _rewrites(shell) == [("F1", "F2")]


def test_editing_a_setting_drops_the_plugin_s_entries_and_its_dependents(
    shell: MainController,
) -> None:
    shell.update_plugin_history(_plugin("F1", value=2), "")

    assert _rewrites(shell) == [("F1", None), ("W1", None)]
    shell.main_view.add_text_to_display.assert_called_once_with(
        "F1 was edited, so its earlier runs are removed from the history: run them "
        "again to save them in the session.",
        "MainController",
    )


def test_a_rename_with_a_changed_setting_drops_under_the_old_name(
    shell: MainController,
) -> None:
    shell.update_plugin_history(_plugin("F2", value=2), "F1")

    assert _rewrites(shell) == [("F1", None), ("W1", None)]


@pytest.mark.parametrize(
    "history",
    [
        _plugin("F1", reader="R2"),
        _plugin("F1"),
        _plugin("F9"),
        {"key": "MetadataController", "metaclass": "MetaController", "subclass": "M"},
    ],
    ids=["a-parent-renamed", "nothing-changed", "a-new-plugin", "a-tab-opened"],
)
def test_what_is_no_edit_changes_no_entry(
    shell: MainController, history: Dict[str, object]
) -> None:
    """
    A dependent re-saved after its parent's rename differs only in the parent it names.

    :param shell: the shell
    :param history: what the plugin controller sends
    """
    shell.update_plugin_history(history, "")

    assert _rewrites(shell) == []


# ------------- the starting tab after a load ---------------------------------
def _named_view_tab(mocker: MockerFixture, view_name: str) -> MagicMock:
    """
    A restored tab whose View's class is named as the real one is, which names its page.

    :param mocker: Pytest-mock fixture.
    :param view_name: the View class name, e.g. "ProteinView"
    :return: the tab
    """
    tab = mocker.Mock()
    tab.view = type(view_name, (), {})()
    tab.get_session_state.return_value = {}
    tab.session_actions.return_value = None
    tab.kept_actions.return_value = []
    tab.replay_available.return_value = False
    return tab


def _load_with_tabs(
    controller: MainController,
    mocker: MockerFixture,
    last_tab: str,
    failing: str = "",
    with_actions: Tuple[str, ...] = (),
) -> None:
    """
    Load a session holding the Raw Data and Protein tabs, with the given last tab.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    :param last_tab: the session's last tab
    :param failing: a tab whose opening raises, as a tab that cannot be restored does
    :param with_actions: the tabs that hold saved actions to replay
    """
    controller.data_plugin_controller.delete_all_plugins.return_value = []
    views = {"ProteinController": "ProteinView", "RawDataController": "RawDataView"}

    def instantiate(subclass: str) -> None:
        if subclass == failing:
            raise RuntimeError("cannot be opened")
        tab = _named_view_tab(mocker, views[subclass])
        tab.replay_available.return_value = subclass in with_actions
        controller.analysis_tabs[subclass] = tab

    controller.instantiate_analysis_tab = mocker.Mock(side_effect=instantiate)  # type: ignore[method-assign]
    history = OrderedDict(
        (name, {"metaclass": "MetaController", "subclass": name})
        for name in ("ProteinController", "RawDataController")
    )
    controller.main_model.load_session = mocker.Mock(
        return_value=LoadedSession(history, last_tab)
    )
    controller.load_session("session.json")


def _page_calls(controller: MainController) -> List[str]:
    """
    The page and highlight calls the load made, and its messages, in order.

    Reset Session's own return to the landing page, which every load starts with, is left
    out.

    :param controller: Controller under test.
    :return: "method:first argument" for each call
    """
    return [
        f"{call[0]}:{call[1][0]}"
        for call in controller.main_view.mock_calls
        if call[0]
        in ("sync_sidebar_highlight", "switch_to_page", "add_text_to_display")
        and call[1][0] != "MainView"
    ]


def test_after_a_load_the_sessions_last_tab_is_showing(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Its button is highlighted and its page switched to, after every tab is restored.

    Raw Data is restored after Protein, so without this Raw Data's page would show.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    _load_with_tabs(controller, mocker, "ProteinController")

    calls = _page_calls(controller)
    assert calls[-3:-1] == [
        "sync_sidebar_highlight:ProteinView",
        "switch_to_page:ProteinView",
    ]
    assert calls[-1].startswith("add_text_to_display:Loaded session from session.json.")


@pytest.mark.parametrize(
    "last_tab, failing",
    [
        ("", ""),
        ("ProteinController", "ProteinController"),
        ("ClusteringController", ""),
    ],
    ids=["none", "not-restored", "not-in-the-session"],
)
def test_a_last_tab_that_cannot_be_shown_leaves_the_page_as_it_was(
    controller: MainController, mocker: MockerFixture, last_tab: str, failing: str
) -> None:
    """
    With no last tab, or one that is not open, the page is left as the restore left it.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    :param last_tab: the session's last tab
    :param failing: a tab whose opening raises
    """
    _load_with_tabs(controller, mocker, last_tab, failing)

    assert [
        call for call in _page_calls(controller) if not call.startswith("add_text")
    ] == []


# ------------- the restore dialog after a load ---------------------------------
def test_after_a_load_the_tabs_with_actions_are_offered_last(
    controller: MainController, mocker: MockerFixture
) -> None:
    """
    Asked once, with those tabs' pages in restore order, after the page and the message.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    _load_with_tabs(
        controller,
        mocker,
        "ProteinController",
        with_actions=("ProteinController", "RawDataController"),
    )

    view = controller.main_view
    view.ask_which_tabs_to_replay.assert_called_once_with(
        ["ProteinView", "RawDataView"]
    )
    names = [call[0] for call in view.mock_calls]
    asked = names.index("ask_which_tabs_to_replay")
    assert names.index("switch_to_page", names.index("sync_sidebar_highlight")) < asked
    assert max(i for i, n in enumerate(names) if n == "add_text_to_display") < asked


def test_only_the_ticked_tabs_replay(
    controller: MainController, mocker: MockerFixture
) -> None:
    controller.main_view.ask_which_tabs_to_replay.return_value = ["RawDataView"]

    _load_with_tabs(
        controller,
        mocker,
        "ProteinController",
        with_actions=("ProteinController", "RawDataController"),
    )

    controller.analysis_tabs["RawDataController"].start_replay.assert_called_once_with()
    controller.analysis_tabs["ProteinController"].start_replay.assert_not_called()


def test_not_now_replays_nothing(
    controller: MainController, mocker: MockerFixture
) -> None:
    _load_with_tabs(
        controller, mocker, "ProteinController", with_actions=("ProteinController",)
    )

    controller.main_view.ask_which_tabs_to_replay.assert_called_once()
    for tab in controller.analysis_tabs.values():
        tab.start_replay.assert_not_called()


def test_a_session_whose_tabs_have_nothing_to_replay_asks_nothing(
    controller: MainController, mocker: MockerFixture
) -> None:
    _load_with_tabs(controller, mocker, "ProteinController")

    controller.main_view.ask_which_tabs_to_replay.assert_not_called()


def test_a_refused_load_asks_nothing(controller: MainController) -> None:
    controller.main_model.load_session.side_effect = SessionRefused("it is broken")

    controller.load_session("broken.json")

    controller.main_view.ask_which_tabs_to_replay.assert_not_called()
