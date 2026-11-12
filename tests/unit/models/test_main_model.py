import json
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from poriscope.constants import __VERSION__
from poriscope.models.main_model import LoadedSession, MainModel, SessionRefused
from poriscope.utils.MetaModel import PLOT_CONFIGURATION_FORMAT
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
    Discovery walks the shipped tree and files each plugin class under its family.

    Every family key is present before anything is found, so the check is on what
    discovery put under them, not on the keys.
    """
    available_plugin_classes, available_plugins_list = (
        main_model.populate_available_plugins()
    )

    assert "SQLiteDBLoader" in available_plugins_list["MetaDatabaseLoader"]
    assert "BesselFilter" in available_plugins_list["MetaFilter"]
    found = available_plugin_classes["MetaDatabaseLoader"]["SQLiteDBLoader"]
    assert found.__name__ == "SQLiteDBLoader"


SESSION = {"reader": {"metaclass": "MetaReader", "subclass": "SomeReader"}}

#: A session as the app holds it: data plugins in their order, then a tab.
HISTORY = {
    "R1": {"metaclass": "MetaReader", "subclass": "SomeReader", "settings": {}},
    "F1": {"metaclass": "MetaEventFinder", "subclass": "SomeFinder", "settings": {}},
    "MetadataController": {
        "metaclass": "MetaController",
        "subclass": "MetadataController",
        "subset_filters": {"long": "duration > 1"},
    },
}


def _written(path: Path) -> dict:
    return json.loads(path.read_text())


def test_save_session_writes_the_layout_load_session_reads(main_model, tmp_path):
    """
    Version and last tab at the top, data plugins as a list in their order, tabs apart.

    A plugin is restored after the plugins it depends on, and JSON keeps no order for an
    object's keys, so the plugins are a list.
    """
    path = tmp_path / "session.json"

    main_model.save_session(HISTORY, path, last_tab="MetadataController")

    assert _written(path) == {
        "format_version": 2,
        "poriscope_version": __VERSION__,
        "last_tab": "MetadataController",
        "plugins": [
            {
                "key": "R1",
                "metaclass": "MetaReader",
                "subclass": "SomeReader",
                "settings": {},
            },
            {
                "key": "F1",
                "metaclass": "MetaEventFinder",
                "subclass": "SomeFinder",
                "settings": {},
            },
        ],
        "tabs": {"MetadataController": {"subset_filters": {"long": "duration > 1"}}},
    }


def test_a_saved_session_loads_back_as_what_was_saved(main_model, tmp_path):
    path = tmp_path / "session.json"
    main_model.save_session(HISTORY, path, last_tab="MetadataController")

    loaded = main_model.load_session(path)

    assert loaded == LoadedSession(HISTORY, "MetadataController")
    assert list(loaded.plugin_history) == ["R1", "F1", "MetadataController"]


def test_a_type_in_the_settings_comes_back_a_type(main_model, tmp_path):
    path = tmp_path / "session.json"
    history = {
        "R1": {
            "metaclass": "MetaReader",
            "subclass": "S",
            "settings": {"Rate": {"Type": float, "Value": 1.0}},
        }
    }

    main_model.save_session(history, path)

    assert _written(path)["plugins"][0]["settings"]["Rate"]["Type"] == "float"
    assert main_model.load_session(path).plugin_history == history


def test_a_subset_filter_named_type_in_a_saved_action_stays_text(main_model, tmp_path):
    """
    Type names are turned back into types under a ``Type`` key; a recorded filter named
    ``Type`` is data, and the actions, a list, are never walked for them.
    """
    path = tmp_path / "session.json"
    entry = {
        "action": "overlay_plot",
        "args": [],
        "kwargs": {"filters": {"Type": "float"}},
    }
    history = {
        "MetadataController": {
            "metaclass": "MetaController",
            "subclass": "MetadataController",
            "actions": [entry],
        }
    }

    main_model.save_session(history, path)

    loaded = main_model.load_session(path).plugin_history
    assert loaded["MetadataController"]["actions"] == [entry]


def test_load_session_default_path(main_model):
    """Restore reads the default session file."""
    default = Path(main_model.session_path, "plugin_history.json")
    main_model.save_session(SESSION)

    assert default.exists()
    assert main_model.load_session().plugin_history == SESSION


def test_a_2_0_session_still_loads_with_its_tabs_after_the_plugins(
    main_model, tmp_path
):
    """The 2.0 layout is a map of entries, a tab wherever it was opened."""
    path = tmp_path / "old.json"
    tab = HISTORY["MetadataController"]
    path.write_text(
        json.dumps(
            {"MetadataController": tab, "R1": HISTORY["R1"], "F1": HISTORY["F1"]}
        )
    )

    loaded = main_model.load_session(path)

    assert loaded == LoadedSession(HISTORY, "")
    assert list(loaded.plugin_history) == ["R1", "F1", "MetadataController"]


def test_a_renamed_plugin_key_loads_by_its_name_with_its_dependents(
    main_model, tmp_path
):
    """
    A reader the user renamed comes back under that name, before what depends on it.

    The session is a real 1.x file holding a reader renamed to ``testrename`` and a
    finder whose ``MetaReader`` setting names it. Restoring instantiates by key in
    this order, so a load that re-keyed the entry, or moved it after its dependent,
    would leave the finder pointing at a plugin that does not exist. Saved again in
    this version's layout, it has to read back the same way.
    """
    saved = Path(__file__).parents[1] / "views" / "saved_state" / "session_1x.json"

    loaded = main_model.load_session(saved).plugin_history
    main_model.save_session(loaded, tmp_path / "resaved.json")
    reloaded = main_model.load_session(tmp_path / "resaved.json").plugin_history

    for history in (loaded, reloaded):
        keys = list(history)
        assert history["testrename"]["subclass"] == "ChimeraReader20240501"
        finder = history["ClassicBlockageFinder_0"]
        assert finder["settings"]["MetaReader"]["Value"] == "testrename"
        assert keys.index("testrename") < keys.index("ClassicBlockageFinder_0")


def test_load_session_refuses_a_file_that_is_not_a_session(main_model, tmp_path):
    """
    A tab action history sits beside the session file under the same *.json filter.

    Loading one as a session used to come back as a dict, and the controller then
    reset the workspace and overwrote the autosave with it before failing on the first
    entry, so the next Restore failed the same way.
    """
    path = tmp_path / "tab_action_history.json"
    path.write_text(
        json.dumps({"MetadataController": {"0": {"function": "_reset_actions"}}})
    )

    with pytest.raises(SessionRefused, match="does not hold a Poriscope session"):
        main_model.load_session(path)


def test_load_session_accepts_an_empty_session(main_model, tmp_path):
    """Nothing open is a valid session, and restores as nothing."""
    path = tmp_path / "empty.json"
    path.write_text("{}")

    assert main_model.load_session(path) == LoadedSession()


def test_a_session_in_a_format_this_version_does_not_read_is_refused_whole(
    main_model, tmp_path
):
    """A later layout may have changed any part of the file, plugins included."""
    path = tmp_path / "later.json"
    path.write_text(
        json.dumps(
            {"format_version": 3, "poriscope_version": "9.9", "plugins": [], "tabs": {}}
        )
    )

    with pytest.raises(SessionRefused, match=r"by Poriscope 9\.9 .*format 3"):
        main_model.load_session(path)


@pytest.mark.parametrize(
    "content",
    [
        {"format_version": 2, "plugins": {}, "tabs": {}},
        {"format_version": 2, "plugins": [], "tabs": []},
        {"format_version": 2, "plugins": [], "tabs": {}, "last_tab": 1},
        {
            "format_version": 2,
            "plugins": [{"metaclass": "M", "subclass": "S"}],
            "tabs": {},
        },
        {
            "format_version": 2,
            "plugins": [
                {"key": "R1", "metaclass": "M", "subclass": "S"},
                {"key": "R1", "metaclass": "M", "subclass": "S"},
            ],
            "tabs": {},
        },
        {"format_version": 2, "plugins": [], "tabs": {"MetadataController": []}},
        {
            "format_version": 2,
            "plugins": [],
            "tabs": {"MetadataController": {"actions": {"0": {}}}},
        },
        {
            "format_version": 2,
            "plugins": [
                {"key": "MetadataController", "metaclass": "M", "subclass": "S"}
            ],
            "tabs": {"MetadataController": {}},
        },
        [],
    ],
    ids=[
        "plugins-not-a-list",
        "tabs-not-an-object",
        "last-tab-not-text",
        "plugin-without-key",
        "duplicate-key",
        "tab-not-an-object",
        "actions-not-a-list",
        "tab-named-like-a-plugin",
        "not-an-object",
    ],
)
def test_a_malformed_session_is_refused_before_anything_is_applied(
    main_model, tmp_path, content
):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(content))

    with pytest.raises(SessionRefused, match="does not hold a Poriscope session"):
        main_model.load_session(path)


def test_a_failed_session_save_keeps_the_previous_file(main_model, tmp_path):
    """
    A save that fails partway leaves the last good file, not a truncated one.

    The file was opened for writing before the data was serialised, so a value that
    could not be serialised left it cut off mid-entry.
    """
    path = tmp_path / "session.json"
    main_model.save_session(SESSION, path)
    before = path.read_text()

    main_model.save_session({"reader": {"metaclass": object()}}, path)

    assert path.read_text() == before
    assert not list(tmp_path.glob("*.tmp")), "the failed save left its temp file"


def test_load_session_nonexistent(main_model):
    """
    Test loading a session when the session file doesn't exist.
    """
    file_name = "non_existent_session.json"

    with patch("builtins.open", MagicMock(side_effect=FileNotFoundError)):
        with pytest.raises(SessionRefused) as refused:
            main_model.load_session(file_name)

    assert refused.value.missing


def test_a_session_that_cannot_be_read_is_refused_with_the_reason(main_model, tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json")

    with pytest.raises(SessionRefused, match="could not be read") as refused:
        main_model.load_session(path)

    assert not refused.value.missing


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


def test_a_save_retries_a_briefly_locked_target(main_model, tmp_path, mocker):
    """
    A rename refused for a moment is retried, not reported as a failed autosave.

    On Windows a file just written is briefly held open by scanners such as Defender, and
    ``os.replace`` onto it fails with "Access is denied" - measured at 14 of 300 rapid
    saves in the temp folder. Reporting that as a failure tells the user autosave has
    stopped when it has not.
    """
    path = tmp_path / "session.json"
    real_replace = os.replace
    attempts = []

    def locked_twice(src, dst):
        attempts.append(src)
        if len(attempts) <= 2:
            raise PermissionError(13, "Access is denied")
        return real_replace(src, dst)

    mocker.patch("poriscope.utils.json_files.os.replace", side_effect=locked_twice)
    mocker.patch("poriscope.utils.json_files.time.sleep")
    reported = mocker.patch.object(main_model, "add_text_to_display")

    main_model.save_session(SESSION, path)

    assert main_model.load_session(path).plugin_history == SESSION
    assert len(attempts) == 3
    reported.emit.assert_not_called()


def test_a_target_that_stays_locked_is_reported_and_left_intact(
    main_model, tmp_path, mocker
):
    """If the rename never succeeds, the old file stays and the temp file goes."""
    path = tmp_path / "session.json"
    main_model.save_session(SESSION, path)
    before = path.read_text()
    mocker.patch(
        "poriscope.utils.json_files.os.replace",
        side_effect=PermissionError(13, "Access is denied"),
    )
    mocker.patch("poriscope.utils.json_files.time.sleep")

    main_model.save_session({"other": {"metaclass": "M", "subclass": "S"}}, path)

    assert path.read_text() == before
    assert not list(tmp_path.glob("*.tmp"))


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
# Each is driven directly as well as through populate_available_plugins.


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

    def test_the_twelve_families_are_the_recognised_set(self, main_model):
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
            "MetaConditioningLoader",
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


def test_the_old_action_autosave_is_found_and_left_alone(main_model):
    """2.0 wrote the action history to its own file, which this version never reads."""
    old = Path(main_model.session_path, "tab_action_history.json")
    assert not main_model.old_action_history_exists()

    old.write_text("{}")

    assert main_model.old_action_history_exists()
    assert old.read_text() == "{}"


def test_a_plot_configuration_is_refused_as_a_session(main_model, tmp_path):
    """Load Session of a plot configuration says what it is, and loads nothing."""
    path = tmp_path / "plots.json"
    path.write_text(
        json.dumps(
            {
                "format": PLOT_CONFIGURATION_FORMAT,
                "format_version": 1,
                "poriscope_version": "3.0.0",
                "tab": "MetadataController",
                "actions": [],
            }
        )
    )

    with pytest.raises(SessionRefused) as refused:
        main_model.load_session(path)

    assert refused.value.reason == (
        "it is a plot configuration, not a session; load it with Metadata's Load Plot "
        "Configuration"
    )


def test_a_file_of_another_named_format_is_refused_as_a_session(main_model, tmp_path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"format": "something.else", "format_version": 2}))

    with pytest.raises(SessionRefused) as refused:
        main_model.load_session(path)

    assert refused.value.reason == "it does not hold a Poriscope session"


def test_a_2_0_session_with_a_plugin_called_format_still_loads(main_model, tmp_path):
    """In the 2.0 layout a plugin's name is a top-level key, so `format` can be one."""
    path = tmp_path / "session.json"
    path.write_text(
        json.dumps({"format": {"metaclass": "MetaFilter", "subclass": "BesselFilter"}})
    )

    loaded = main_model.load_session(path)

    assert list(loaded.plugin_history) == ["format"]
