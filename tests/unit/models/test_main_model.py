import json
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from poriscope.models.main_model import MainModel

# Set up logging for the tests
logger = logging.getLogger("MainModelTest")


# Mock base classes
class MetaReader:
    pass


class MetaEventFinder:
    pass


@pytest.fixture
def main_model():
    # Mock configuration for testing
    app_config = {
        "User Plugin Folder": "/mock/path/to/plugins",
        "Parent Folder": "/mock/data/server/location",
    }
    return MainModel(app_config)


def test_clear_cache(main_model):
    """
    Test the clear_cache method to ensure log file reset.
    """
    log_file_path = Path(main_model.log_path, "app.log")
    log_file_str = str(log_file_path)

    m = mock_open()

    # Create a mock FileHandler with baseFilename set to the log file path
    mock_file_handler = MagicMock(spec=logging.FileHandler)
    mock_file_handler.baseFilename = log_file_str

    with patch("builtins.open", m):
        with patch("logging.getLogger") as mock_get_logger:
            mock_get_logger.return_value.handlers = [mock_file_handler]
            main_model.clear_cache()

    # Ensure open was called with the correct string path
    m.assert_called_once_with(log_file_str, "w")


def test_load_plugin_valid(main_model):
    plugin_key = "MetaReader"
    plugin_folder = "/mock/path/to/plugins"
    allowed_base_classes = MetaReader

    mock_spec = MagicMock()
    mock_spec.loader = MagicMock()
    mock_module = MagicMock()
    mock_module.MetaReader = MetaReader

    with patch("importlib.util.spec_from_file_location", return_value=mock_spec), patch(
        "importlib.util.module_from_spec", return_value=mock_module
    ), patch("pathlib.Path.exists", return_value=True), patch.object(
        mock_spec.loader, "exec_module"
    ):
        plugin_class = main_model.load_plugin(
            plugin_key, plugin_folder, allowed_base_classes
        )

    assert plugin_class == MetaReader


def test_load_plugin_invalid(main_model):
    """
    Test loading a plugin that doesn't exist or is invalid.
    """
    plugin_key = "NonExistentPlugin"
    plugin_folder = "/mock/path/to/plugins"
    allowed_base_classes = {"MetaReader": MetaReader}

    plugin_class = main_model.load_plugin(
        plugin_key, plugin_folder, allowed_base_classes
    )

    assert plugin_class is None


def test_populate_available_plugins(main_model):
    """
    Test the population of available plugins.
    """
    with patch(
        "os.walk", return_value=[("/mock/path", [], ["MetaReader.py", "MetaFilter.py"])]
    ):
        available_plugin_classes, available_plugins_list = (
            main_model.populate_available_plugins()
        )

        assert isinstance(available_plugin_classes, dict)
        assert "MetaReader" in available_plugins_list
        assert "MetaFilter" in available_plugins_list


def test_get_plugin_data_existing(main_model, tmp_path, monkeypatch):
    # Ensure MainModel looks under temp user_data_dir
    monkeypatch.setattr(
        "poriscope.models.main_model.user_data_dir",
        lambda *a, **k: str(tmp_path),
        raising=False,
    )

    plugin_key = "MetaReader"
    mock_data = {plugin_key: {"Value": "SomeData"}}

    # Create the exact directory tree MainModel expects:
    # <user_data_dir>/Poriscope/session/plugin_history.json
    session_dir = tmp_path / "Poriscope" / "session"
    session_dir.mkdir(parents=True, exist_ok=True)

    plugin_history = session_dir / "plugin_history.json"
    plugin_history.write_text(json.dumps(mock_data))

    got = main_model.get_plugin_data(plugin_key)
    assert got == {"Value": "SomeData"}

def test_get_plugin_data_nonexistent(main_model):
    """
    Test the fetching of plugin data when the session file does not exist.
    """
    plugin_key = "MetaReader"

    with patch("builtins.open", MagicMock(side_effect=FileNotFoundError)):
        plugin_data = main_model.get_plugin_data(plugin_key)

    assert plugin_data == {}


def test_save_session(main_model):
    """
    Test saving the session to a JSON file.
    """
    plugin_history = {"plugin": "MetaReader"}

    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        main_model.save_session(plugin_history)

    mock_open.assert_called_once()


def test_load_session_default_path(main_model):
    mock_data = {"plugin": "MetaReader"}
    m = mock_open(read_data=json.dumps(mock_data))

    with patch("builtins.open", m):
        with patch("pathlib.Path.exists", return_value=True):
            result = main_model.load_session()

    assert result == mock_data


def test_load_session_nonexistent(main_model):
    """
    Test loading a session when the session file doesn't exist.
    """
    file_name = "non_existent_session.json"

    with patch("builtins.open", MagicMock(side_effect=FileNotFoundError)):
        session_data = main_model.load_session(file_name)

    assert session_data is None


def test_replace_classes_with_class_names_all_paths(main_model):
    class DummyA:
        pass

    class DummyB:
        pass

    data = {"a": DummyA, "b": {"nested": DummyB}, "c": [DummyA, {"deep": DummyB}]}

    main_model.replace_classes_with_class_names(data)
    main_model.replace_classes_with_class_names(
        data["c"]
    )  # Ensure list is also processed

    assert data["a"] == "DummyA"
    assert data["b"]["nested"] == "DummyB"
    assert data["c"][0] == "DummyA"
    assert data["c"][1]["deep"] == "DummyB"


def test_replace_class_names_with_classes_all_paths(main_model):
    data = {"a": "int", "b": {"nested": "float"}, "c": ["str", {"deep": "bool"}]}

    class_dict = {"int": int, "float": float, "str": str, "bool": bool}

    main_model.replace_class_names_with_classes(data, class_dict)
    main_model.replace_class_names_with_classes(
        data["c"], class_dict
    )  # Ensure list is processed

    assert data["a"] is int
    assert data["b"]["nested"] is float
    assert data["c"][0] is str
    assert data["c"][1]["deep"] is bool


def test_update_app_config(main_model):
    """
    Test updating the application configuration.
    """
    key = "Log Level"
    val = 30

    with patch("builtins.open", MagicMock()):
        main_model.update_app_config(key, val)

    assert main_model.app_config[key] == val


def test_update_logging_level_handlers(main_model):
    mock_handler = MagicMock()
    with patch("builtins.open", MagicMock()), patch(
        "logging.getLogger"
    ) as mock_get_logger:
        mock_logger = MagicMock()
        mock_logger.handlers = [mock_handler]
        mock_get_logger.return_value = mock_logger

        main_model.update_logging_level(20)

        mock_logger.setLevel.assert_called_once_with(20)
        mock_handler.setLevel.assert_called_once_with(20)


def test_save_tab_actions(main_model):
    plugin_history = {"plugin": "MetaReader"}

    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        main_model.save_tab_actions(plugin_history)

    mock_open.assert_called_once()


def test_get_plugin_existing(main_model):
    class Dummy:
        pass

    main_model.available_plugin_classes = {"MetaReader": {"MyReader": Dummy}}
    result = main_model.get_plugin("MetaReader", "MyReader")
    assert result == Dummy


def test_get_available_plugins(main_model):
    main_model.available_plugins_list = {"MetaReader": ["MockReader"]}

    assert main_model.get_available_plugins() == {"MetaReader": ["MockReader"]}
    assert main_model.get_available_plugins("MetaReader") == ["MockReader"]


def test_get_plugin_classes(main_model):
    main_model.available_plugin_classes = {"MetaReader": {"MyReader": object}}

    assert main_model.get_plugin_classes() == {"MetaReader": {"MyReader": object}}
    assert main_model.get_plugin_classes("MetaReader") == {"MyReader": object}


def test_get_plugin_success(main_model):
    class Dummy:
        pass

    main_model.available_plugin_classes = {"MetaReader": {"MyReader": Dummy}}
    assert main_model.get_plugin("MetaReader", "MyReader") == Dummy


def test_get_plugin_failure(main_model, caplog):
    with caplog.at_level(logging.ERROR):
        main_model.available_plugin_classes = {}
        result = main_model.get_plugin("MetaReader", "DoesNotExist")
        assert result is None
        assert "unable to load class MetaReader DoesNotExist" in caplog.text


def test_get_plugin_data_file_missing(main_model, caplog):
    plugin_key = "MetaReader"
    with patch("pathlib.Path.exists", return_value=False):
        result = main_model.get_plugin_data(plugin_key)
        assert result == {}
        assert "Plugin data file does not exist" in caplog.text


def test_get_data_server_location(main_model):
    assert main_model.get_data_server_location() == "/mock/data/server/location"


def test_get_user_plugin_location(main_model):
    assert main_model.get_user_plugin_location() == "/mock/path/to/plugins"


def test_populate_available_plugins_os_walk_fails(main_model):
    """
    Test the behavior when os.walk() raises an exception.
    Should handle the exception and continue gracefully.
    """
    with patch("os.walk", side_effect=Exception("Walk error")):
        available_plugin_classes, available_plugins_list = (
            main_model.populate_available_plugins()
        )

    # All values should be empty lists or dicts
    assert isinstance(available_plugin_classes, dict)
    assert all(isinstance(v, dict) and not v for v in available_plugin_classes.values())
    assert isinstance(available_plugins_list, dict)
    assert all(isinstance(v, list) and not v for v in available_plugins_list.values())


def test_populate_available_plugins_os_walk_raises(monkeypatch):
    model = MainModel(app_config={"User Plugin Folder": "fake/path"})

    def mock_os_walk_raise(path):
        raise OSError("Walk failed")

    monkeypatch.setattr(os, "walk", mock_os_walk_raise)

    # This should now hit the 'Skipping plugin directory' log line
    model.populate_available_plugins()


def test_populate_available_plugins_file_list_fails(monkeypatch):
    model = MainModel(app_config={"User Plugin Folder": "fake/path"})

    # Simulate os.walk returning something valid
    monkeypatch.setattr(
        os,
        "walk",
        lambda path: [("some/dir", [], None)],  # None will break the 'for f in files'
    )

    model.populate_available_plugins()  # This will hit 'Error reading files in {root_dir}'


def test_populate_available_plugins_load_plugin_fails(main_model):
    """
    Test when load_plugin fails internally (returns None).
    Should handle the exception and skip the plugin.
    """
    with patch(
        "os.walk", return_value=[("/mock/path", [], ["MetaReader.py"])]
    ), patch.object(main_model, "load_plugin", side_effect=Exception("Load error")):
        available_plugin_classes, available_plugins_list = (
            main_model.populate_available_plugins()
        )

    # Ensure the plugin was not added due to load_plugin failure
    assert isinstance(available_plugin_classes, dict)
    assert all(not v for v in available_plugin_classes.values())
