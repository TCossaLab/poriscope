import json
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from poriscope.models.main_model import MainModel
from poriscope.utils.QtHandler import QtHandler

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

    with (
        patch("importlib.util.spec_from_file_location", return_value=mock_spec),
        patch("importlib.util.module_from_spec", return_value=mock_module),
        patch("pathlib.Path.exists", return_value=True),
        patch.object(mock_spec.loader, "exec_module"),
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
    """
    Every type in a settings tree becomes its name, however deeply nested.

    This used to hand the walker a list directly to reach its
    list branch; that branch was unreachable from every real caller and is now
    gone. A settings tree is dicts inside dicts, which is what this walks.
    """

    class DummyA:
        pass

    class DummyB:
        pass

    data = {"Threshold": {"Type": DummyA}, "Group": {"Inner": {"Type": DummyB}}}

    main_model.replace_classes_with_class_names(data)

    assert data["Threshold"]["Type"] == "DummyA"
    assert data["Group"]["Inner"]["Type"] == "DummyB"


def test_replace_class_names_with_classes_all_paths(main_model):
    """
    Type names become types again, however deeply nested, under the keys that hold types.

    Rewritten on both counts: the conversion is gated on the key now, so
    the names sit under ``Type`` rather than arbitrary keys, and the list branch
    this used to exercise is gone.
    """
    data = {"Threshold": {"Type": "int"}, "Group": {"Inner": {"Type": "float"}}}
    class_dict = {"int": int, "float": float, "str": str, "bool": bool}

    main_model.replace_class_names_with_classes(data, class_dict)

    assert data["Threshold"]["Type"] is int
    assert data["Group"]["Inner"]["Type"] is float


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
    # QtHandler raises a modal dialog per record, so its level is a decision about
    # interrupting the user rather than about how much to record, and it must keep
    # its own ERROR floor. Before this carve-out it was the only handler whose level
    # was ever set here, so picking a more verbose log level in the settings window
    # silently turned every routine warning back into a dialog.
    mock_qt_handler = MagicMock(spec=QtHandler)
    with (
        patch("builtins.open", MagicMock()),
        patch("logging.getLogger") as mock_get_logger,
    ):
        mock_logger = MagicMock()
        mock_logger.handlers = [mock_handler, mock_qt_handler]
        mock_get_logger.return_value = mock_logger

        main_model.update_logging_level(20)

        mock_logger.setLevel.assert_called_once_with(20)
        mock_handler.setLevel.assert_called_once_with(20)
        mock_qt_handler.setLevel.assert_not_called()


def test_save_tab_actions(main_model):
    plugin_history = {"plugin": "MetaReader"}

    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        main_model.save_tab_actions(plugin_history)

    mock_open.assert_called_once()


def test_get_available_plugins(main_model):
    main_model.available_plugins_list = {"MetaReader": ["MockReader"]}

    assert main_model.get_available_plugins() == {"MetaReader": ["MockReader"]}


def test_get_plugin_classes(main_model):
    main_model.available_plugin_classes = {"MetaReader": {"MyReader": object}}

    assert main_model.get_plugin_classes("MetaReader") == {"MyReader": object}


def test_get_data_server_location(main_model):
    assert main_model.get_data_server_location() == "/mock/data/server/location"


def test_get_user_plugin_location(main_model):
    assert main_model.get_user_plugin_location() == "/mock/path/to/plugins"


def test_populate_available_plugins_no_valid_directories(main_model, monkeypatch):
    """
    Test the behavior when none of the plugin directories exist on disk.
    Should skip them (logging a warning for each) and return empty results.
    """
    monkeypatch.setattr(Path, "is_dir", lambda self: False)
    available_plugin_classes, available_plugins_list = (
        main_model.populate_available_plugins()
    )

    # All values should be empty lists or dicts
    assert isinstance(available_plugin_classes, dict)
    assert all(isinstance(v, dict) and not v for v in available_plugin_classes.values())
    assert isinstance(available_plugins_list, dict)
    assert all(isinstance(v, list) and not v for v in available_plugins_list.values())


def test_populate_available_plugins_invalid_user_plugin_folder(caplog):
    model = MainModel(app_config={"User Plugin Folder": "fake/path"})

    # "fake/path" does not exist -> should hit the 'Skipping plugin directory' log line
    with caplog.at_level(logging.WARNING):
        model.populate_available_plugins()

    assert "Skipping plugin directory" in caplog.text


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
    with (
        patch("os.walk", return_value=[("/mock/path", [], ["MetaReader.py"])]),
        patch.object(main_model, "load_plugin", side_effect=Exception("Load error")),
    ):
        available_plugin_classes, available_plugins_list = (
            main_model.populate_available_plugins()
        )

    # Ensure the plugin was not added due to load_plugin failure
    assert isinstance(available_plugin_classes, dict)
    assert all(not v for v in available_plugin_classes.values())


class TestResetAppConfig:
    """Reset of the three stored settings, and what it leaves alone."""

    def test_restores_defaults_in_memory(self, main_model):
        main_model.update_app_config("Parent Folder", "/somewhere/else")
        main_model.update_app_config("Log Level", logging.DEBUG)

        defaults = main_model.reset_app_config()

        assert main_model.get_app_config("Parent Folder") == str(Path.home())
        assert main_model.get_app_config("Log Level") == logging.WARNING
        assert defaults["Parent Folder"] == str(Path.home())

    def test_persists_to_config_file(self, main_model):
        main_model.update_app_config("Parent Folder", "/somewhere/else")
        main_model.reset_app_config()

        config_file = Path(main_model.config_path, "config.json")
        with open(config_file) as f:
            written = json.load(f)
        assert written["Parent Folder"] == str(Path.home())
        assert written["Log Level"] == logging.WARNING

    def test_returns_a_fresh_dict_each_call(self, main_model):
        first = main_model.reset_app_config()
        first["Parent Folder"] = "mutated"
        second = main_model.reset_app_config()
        assert second["Parent Folder"] == str(Path.home())

    def test_leaves_the_saved_session_alone(self, main_model):
        session_file = Path(main_model.session_path, "plugin_history.json")
        session_file.write_text('{"kept": true}', encoding="utf-8")

        main_model.reset_app_config()

        assert session_file.exists(), "resetting settings must not touch the session"


# ------------- plugin discovery's extracted helpers -----------------------
#
# Each is in the refactor-coverage audit's MOVED table, so each is driven
# directly as well as through populate_available_plugins.


class TestPythonFiles:
    """Which files in a directory listing are worth importing."""

    def test_keeps_modules_and_drops_the_package_marker(self, main_model):
        """``__init__.py`` defines the package, never a plugin."""
        kept = main_model._python_files(
            "/somewhere", ["Reader.py", "__init__.py", "notes.txt", "Finder.py"]
        )

        assert kept == ["Reader.py", "Finder.py"]

    def test_an_unreadable_listing_yields_nothing_rather_than_raising(
        self, main_model, caplog
    ):
        """
        One bad directory must not stop discovery, since the user's folder is walked too.

        The listing is passed as something that raises on iteration, which is the
        only way this inherited guard can fire.
        """

        class _Hostile(list):
            def __iter__(self):
                raise OSError("listing exploded")

        with caplog.at_level(logging.WARNING):
            assert main_model._python_files("/bad", _Hostile()) == []
        assert "Error reading files in /bad" in caplog.text


class TestMetaclassFor:
    """Naming the family a plugin class belongs to."""

    def test_names_the_family_a_class_subclasses(self, main_model):
        """The mapping is the definition of what counts as a plugin."""
        real_base = MainModel.ALLOWED_BASE_CLASSES["MetaReader"]

        class MyReader(real_base):
            pass

        assert main_model._metaclass_for(MyReader) == "MetaReader"

    def test_gives_none_for_a_class_that_is_not_a_plugin(self, main_model):
        """A file can define a class without defining a plugin."""

        class Unrelated:
            pass

        assert main_model._metaclass_for(Unrelated) is None

    def test_the_eleven_families_are_the_recognised_set(self, main_model):
        """
        Pinned because this mapping *is* the definition of a plugin family.

        Adding one is a deliberate act; losing one silently would make every
        plugin of that family vanish from the app with no error anywhere.
        """
        assert set(MainModel.ALLOWED_BASE_CLASSES) == {
            "MetaFilter",
            "MetaReader",
            "MetaWriter",
            "MetaEventLoader",
            "MetaEventFinder",
            "MetaEventFitter",
            "MetaDatabaseWriter",
            "MetaDatabaseLoader",
            "MetaController",
            "MetaView",
            "MetaModel",
        }


class TestLoadPluginClass:
    """Importing one candidate file, which executes it."""

    def test_returns_what_load_plugin_gives(self, main_model):
        """The ordinary case."""
        sentinel = type("Sentinel", (), {})
        with patch.object(main_model, "load_plugin", return_value=sentinel):
            assert (
                main_model._load_plugin_class("Sentinel", Path("/plugins")) is sentinel
            )

    def test_a_file_that_explodes_on_import_yields_none(self, main_model, caplog):
        """
        Discovery executes every file it walks, including the user's, so one bad
        file must not stop the rest of the plugins loading.
        """
        with patch.object(main_model, "load_plugin", side_effect=RuntimeError("boom")):
            with caplog.at_level(logging.WARNING):
                assert main_model._load_plugin_class("Bad", Path("/plugins")) is None
        assert "Failed to load plugin Bad" in caplog.text


class TestClassifyPluginFile:
    """Import a file and decide what, if anything, it contributes."""

    def test_gives_the_family_name_and_class(self, main_model):
        """The name comes off the filename, not out of the module."""
        real_base = MainModel.ALLOWED_BASE_CLASSES["MetaReader"]

        class MyReader(real_base):
            pass

        with patch.object(main_model, "load_plugin", return_value=MyReader):
            assert main_model._classify_plugin_file(Path("/p"), "MyReader.py") == (
                "MetaReader",
                "MyReader",
                MyReader,
            )

    def test_a_failed_import_is_not_a_plugin(self, main_model):
        """``load_plugin`` returning None must not reach ``issubclass``."""
        with patch.object(main_model, "load_plugin", return_value=None):
            assert main_model._classify_plugin_file(Path("/p"), "Broken.py") is None

    def test_something_that_is_not_a_class_is_not_a_plugin(self, main_model):
        """
        The ``isinstance(..., type)`` guard, which the original spelled out inline.

        A file can define a name that is not a class at all, and ``issubclass``
        raises on a non-class rather than returning False.
        """
        with patch.object(main_model, "load_plugin", return_value="not a class"):
            assert main_model._classify_plugin_file(Path("/p"), "Odd.py") is None

    def test_a_class_of_no_known_family_is_not_a_plugin(self, main_model):
        """A plain class in the plugin tree is ignored rather than mis-filed."""

        class Unrelated:
            pass

        with patch.object(main_model, "load_plugin", return_value=Unrelated):
            assert main_model._classify_plugin_file(Path("/p"), "Unrelated.py") is None


class TestPluginFiles:
    """Where discovery looks, and in what order."""

    def test_skips_a_directory_that_is_not_there(self, main_model, caplog, tmp_path):
        """
        A missing plugin directory is warned about and stepped over, not fatal.

        The user's folder is routinely absent - a fresh install has nothing in it -
        so this is the common path rather than an edge case. Both directories are
        pointed at paths that do not exist, since the fixture leaves
        ``plugin_path`` aimed at the real shipped tree.
        """
        main_model.plugin_path = Path(tmp_path, "no-such-shipped-tree")
        main_model.app_config["User Plugin Folder"] = str(
            Path(tmp_path, "no-such-user")
        )

        with caplog.at_level(logging.WARNING):
            assert list(main_model._plugin_files()) == []

        assert caplog.text.count("not a valid directory") == 2

    def test_walks_the_shipped_tree_before_the_user_folder(self, main_model, tmp_path):
        """
        Order is load-bearing: the caller rejects the *second* file of a given
        name, so walking shipped plugins first is what makes a user file lose a
        collision rather than win it.
        """
        shipped = Path(tmp_path, "shipped")
        user = Path(tmp_path, "user")
        for folder in (shipped, user):
            folder.mkdir()
            Path(folder, "Clash.py").write_text("", encoding="utf-8")

        main_model.plugin_path = shipped
        main_model.app_config["User Plugin Folder"] = str(user)

        found = list(main_model._plugin_files())

        assert [str(folder) for folder, _ in found] == [str(shipped), str(user)]
        assert {name for _, name in found} == {"Clash.py"}


# ------------- the session-restore type round trip -----------------------
#
# Plugin settings carry a real type under "Type". JSON cannot hold one, so it is
# written as its name on save and turned back into the type on load. The bug was
# that the load side converted *any* string matching a type name, whatever key it
# sat under.


class TestTypeRoundTrip:
    """Saving and restoring the one key that legitimately holds a type."""

    def test_a_type_survives_the_round_trip(self, main_model):
        """The feature these two walkers exist for."""
        settings = {"Threshold": {"Type": float, "Value": 3.0}}

        main_model.replace_classes_with_class_names(settings)
        assert settings["Threshold"]["Type"] == "float"

        main_model.replace_class_names_with_classes(settings)
        assert settings["Threshold"]["Type"] is float

    def test_a_value_that_reads_like_a_type_name_is_left_alone(self, main_model):
        """
        The corruption: a setting whose value is the string "float" came back as
        ``<class 'float'>``, because the walker matched on the string and ignored
        which key it sat under. Reproduced before the fix.
        """
        restored = {"Event Type": {"Type": str, "Value": "float"}}

        main_model.replace_class_names_with_classes(restored)

        assert restored["Event Type"]["Value"] == "float"
        assert isinstance(restored["Event Type"]["Value"], str)

    def test_every_type_name_is_safe_as_a_value(self, main_model):
        """All four names the map knows, since any of them could be a real setting."""
        restored = {
            "P": {"Value": "str"},
            "Q": {"Value": "int"},
            "R": {"Value": "bool"},
        }

        main_model.replace_class_names_with_classes(restored)

        assert [v["Value"] for v in restored.values()] == ["str", "int", "bool"]

    def test_an_unknown_type_name_is_left_as_written(self, main_model):
        """A Type the map does not know stays a string rather than vanishing."""
        restored = {"Odd": {"Type": "SomeClass"}}

        main_model.replace_class_names_with_classes(restored)

        assert restored["Odd"]["Type"] == "SomeClass"

    def test_nested_settings_are_still_walked(self, main_model):
        """Plugin history nests settings two deep, so the recursion is load-bearing."""
        history = {"reader_0": {"settings": {"Threshold": {"Type": "int"}}}}

        main_model.replace_class_names_with_classes(history)

        assert history["reader_0"]["settings"]["Threshold"]["Type"] is int

    def test_saving_a_type_under_an_unexpected_key_is_reported(
        self, main_model, caplog
    ):
        """
        The save side still converts any type, so no existing save can break - but
        it says so, because the load side will not convert that key back. Without
        the warning the asymmetry would be silent and the setting would come back
        as a string.
        """
        settings = {"Surprise": {"Codec": bool}}

        with caplog.at_level(logging.WARNING):
            main_model.replace_classes_with_class_names(settings)

        assert settings["Surprise"]["Codec"] == "bool"
        assert "Codec" in caplog.text
