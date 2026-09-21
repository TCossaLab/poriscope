"""
Characterization tests for ``App.create_appdata_folders``.

This is the app's first-run bootstrap: it creates ``Poriscope/`` and its four
subfolders under the platform's user data directory, writes or repairs
``config/config.json``, and puts the user-plugin folder's *parent* on
``sys.path`` so plugin discovery can import from it.

It was at **0% coverage** - 52 statements, none of them executed by any test -
while being complexity 17 and the thing that runs before anything else in the
application. Step 5c.5 splits it, so it is pinned first (5c.1).

These call the method **unbound**, against a stub carrying only a logger. It
touches nothing on ``self`` that it does not itself assign, so this exercises the
real code without constructing a ``QApplication`` - which would collide with the
one pytest-qt manages.

Two globals are involved and both are restored by fixture rather than left to
chance: ``user_data_dir`` is redirected into ``tmp_path`` so the developer's real
``%LOCALAPPDATA%\\Poriscope`` is never touched, and ``sys.path`` is swapped for a
copy, since the method appends to it.
"""

import builtins
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from poriscope.main_app import App
from poriscope.utils.app_config import default_app_config


class _StubApp:
    """
    A stand-in for ``App`` carrying only what ``create_appdata_folders`` reads.

    The method assigns every other attribute it uses, so nothing else is needed.
    Using a stub rather than a real ``App`` keeps ``QApplication`` out of these
    tests entirely.
    """

    def __init__(self) -> None:
        """
        Give the stub the mock logger the method reports failures through.

        :return: None
        :rtype: None
        """
        self.logger = MagicMock()


@pytest.fixture
def app_root(tmp_path, monkeypatch):
    """
    Redirect the platform user-data directory into ``tmp_path`` and isolate ``sys.path``.

    :param tmp_path: pytest's per-test temporary directory
    :type tmp_path: pathlib.Path
    :param monkeypatch: pytest's monkeypatch fixture
    :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
    :return: the directory that will hold the ``Poriscope`` folder
    :rtype: pathlib.Path
    """
    monkeypatch.setattr("poriscope.main_app.user_data_dir", lambda: str(tmp_path))
    # The method appends to sys.path; give it a copy so the real one is untouched.
    monkeypatch.setattr(sys, "path", list(sys.path))
    return tmp_path


def _run(app_root):
    """
    Run ``create_appdata_folders`` once against a fresh stub.

    :param app_root: the redirected user-data directory
    :type app_root: pathlib.Path
    :return: the stub the method wrote its attributes onto
    :rtype: _StubApp
    """
    stub = _StubApp()
    App.create_appdata_folders(stub)
    return stub


def _config_path(app_root):
    """
    Give the path the method writes its configuration to.

    :param app_root: the redirected user-data directory
    :type app_root: pathlib.Path
    :return: the path of ``config.json``
    :rtype: pathlib.Path
    """
    return Path(app_root, "Poriscope", "config", "config.json")


class TestTheFirstRun:
    """What a fresh installation gets."""

    def test_creates_the_folder_tree(self, app_root) -> None:
        """All four subfolders are created under ``Poriscope``, along with the root."""
        _run(app_root)

        root = Path(app_root, "Poriscope")
        assert root.is_dir()
        for name in ("logs", "session", "user_plugins", "config"):
            assert Path(root, name).is_dir(), f"{name} was not created"

    def test_records_each_path_on_the_instance(self, app_root) -> None:
        """
        The four paths are attributes, because the rest of ``App.__init__`` reads them.

        ``configure_logger`` and ``initialize_components`` both run straight
        after this method and expect them to exist.
        """
        stub = _run(app_root)

        root = Path(app_root, "Poriscope")
        assert stub.app_folder == root
        assert stub.log_path == Path(root, "logs")
        assert stub.session_path == Path(root, "session")
        assert stub.user_plugin_path == Path(root, "user_plugins")
        assert stub.config_path == Path(root, "config")

    def test_writes_a_default_config_file(self, app_root) -> None:
        """The config file is created on disk and holds the shared defaults."""
        stub = _run(app_root)

        written = json.loads(_config_path(app_root).read_text(encoding="utf-8"))
        assert written == default_app_config(Path(app_root, "Poriscope", "user_plugins"))
        assert stub.app_config == written

    def test_log_level_is_readable_by_subscript(self, app_root) -> None:
        """
        ``App.__init__`` reads ``self.app_config["Log Level"]`` immediately.

        It does so before ``configure_logger`` has installed a handler, so a
        missing key there is a ``KeyError`` that nothing can record. That is the
        reason the backfill below exists, and this pins the happy path of it.
        """
        stub = _run(app_root)

        assert stub.app_config["Log Level"] == logging.WARNING


class TestPluginDiscoveryPath:
    """The ``sys.path`` side effect, which is how user plugins become importable."""

    def test_adds_the_user_plugin_folders_parent(self, app_root) -> None:
        """
        The *parent* goes on the path, not the plugin folder itself.

        Discovery imports ``user_plugins`` as a package, so the importable
        location is the directory containing it.
        """
        _run(app_root)

        expected = str(Path(app_root, "Poriscope").resolve())
        assert expected in sys.path

    def test_does_not_add_a_duplicate_on_a_second_run(self, app_root) -> None:
        """
        Running twice leaves one entry, which is what the membership check is for.

        A duplicate would be harmless but unbounded - the method runs once per
        launch, and a developer restarting the app in-process would grow it.
        """
        _run(app_root)
        _run(app_root)

        expected = str(Path(app_root, "Poriscope").resolve())
        assert sys.path.count(expected) == 1


class TestAnExistingInstallation:
    """A config file that is already there is read, not overwritten."""

    def test_keeps_a_stored_value(self, app_root) -> None:
        """The whole point of persisting the config: a user's choice survives a restart."""
        _run(app_root)
        stored = json.loads(_config_path(app_root).read_text(encoding="utf-8"))
        stored["Log Level"] = logging.DEBUG
        stored["Parent Folder"] = "D:/somewhere/else"
        _config_path(app_root).write_text(json.dumps(stored), encoding="utf-8")

        stub = _run(app_root)

        assert stub.app_config["Log Level"] == logging.DEBUG
        assert stub.app_config["Parent Folder"] == "D:/somewhere/else"

    def test_leaves_the_folder_tree_alone(self, app_root) -> None:
        """A second run over an existing tree neither fails nor discards anything."""
        _run(app_root)
        marker = Path(app_root, "Poriscope", "logs", "poriscope.log")
        marker.write_text("previous session", encoding="utf-8")

        _run(app_root)

        assert marker.read_text(encoding="utf-8") == "previous session"


class TestRepairingTheConfig:
    """The damaged-config paths, and what each one degrades to."""

    def test_backfills_a_missing_key_and_warns(self, app_root) -> None:
        """
        Every default is restored, not just the one added most recently.

        A config written by an older version, or hand-edited, can be missing any
        of them.
        """
        _run(app_root)
        _config_path(app_root).write_text(
            json.dumps({"Parent Folder": "D:/kept"}), encoding="utf-8"
        )

        stub = _run(app_root)

        assert stub.app_config["Parent Folder"] == "D:/kept"
        assert stub.app_config["Log Level"] == logging.WARNING
        assert "User Plugin Folder" in stub.app_config
        stub.logger.warning.assert_called_once()
        assert "restored to default" in stub.logger.warning.call_args[0][0]

    def test_persists_the_backfill(self, app_root) -> None:
        """
        The repaired config is written back, so the warning is not repeated every launch.
        """
        _run(app_root)
        _config_path(app_root).write_text(
            json.dumps({"Parent Folder": "D:/kept"}), encoding="utf-8"
        )
        _run(app_root)

        on_disk = json.loads(_config_path(app_root).read_text(encoding="utf-8"))
        assert on_disk["Log Level"] == logging.WARNING
        assert on_disk["Parent Folder"] == "D:/kept"

    def test_regenerates_an_unreadable_config_and_warns(self, app_root) -> None:
        """
        Unparseable JSON degrades to a fresh default config rather than a crash.

        This runs before the logger has a handler, so the app cannot report it
        any other way and must not fail to start.
        """
        _run(app_root)
        _config_path(app_root).write_text("{not json at all", encoding="utf-8")

        stub = _run(app_root)

        assert stub.app_config == default_app_config(
            Path(app_root, "Poriscope", "user_plugins")
        )
        stub.logger.warning.assert_called_once()
        assert "regenerating defaults" in stub.logger.warning.call_args[0][0]

    def test_regenerates_a_config_that_parses_but_is_not_an_object(
        self, app_root
    ) -> None:
        """
        Valid JSON of the wrong shape is repaired by the handler, not by luck.

        This is the case that distinguishes the handler's own
        ``self.app_config = default_app_config(...)`` from the assignment made
        before the ``try``. When ``json.load`` itself raises, the earlier
        assignment is still standing and the handler's reassignment is
        redundant - so deleting it breaks nothing and no test notices.

        Here the load *succeeds*, leaving a list in ``app_config``, and the
        backfill then fails trying to subscript it by name. Only the handler's
        reassignment turns that back into a usable config.
        """
        _run(app_root)
        _config_path(app_root).write_text("[1, 2, 3]", encoding="utf-8")

        stub = _run(app_root)

        assert stub.app_config == default_app_config(
            Path(app_root, "Poriscope", "user_plugins")
        )
        stub.logger.warning.assert_called_once()
        assert "regenerating defaults" in stub.logger.warning.call_args[0][0]

    def test_persists_the_regenerated_config(self, app_root) -> None:
        """The replacement is written back, so the file is valid next launch."""
        _run(app_root)
        _config_path(app_root).write_text("{not json at all", encoding="utf-8")
        _run(app_root)

        on_disk = json.loads(_config_path(app_root).read_text(encoding="utf-8"))
        assert on_disk == default_app_config(
            Path(app_root, "Poriscope", "user_plugins")
        )


def _block_writes_to(monkeypatch, blocked: Path) -> None:
    """
    Make opening one path for writing raise, leaving every other ``open`` alone.

    Used to drive the three "unable to write the config" handlers. Patching
    ``builtins.open`` rather than the filesystem keeps the failure precisely
    where the test means it, so a handler that swallows the wrong error is still
    visible.

    :param monkeypatch: pytest's monkeypatch fixture
    :type monkeypatch: _pytest.monkeypatch.MonkeyPatch
    :param blocked: the path that may not be opened for writing
    :type blocked: pathlib.Path
    :return: None
    :rtype: None
    """
    real_open = builtins.open

    def _guarded(file, mode="r", *args, **kwargs):
        if Path(file) == blocked and "w" in mode:
            raise OSError("config file is not writable")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", _guarded)


class TestAnUnwritableConfig:
    """
    Each of the three write attempts is guarded, and none of them may abort startup.

    A read-only or permission-denied config directory must still leave a usable
    application, because this runs before anything can report a failure to the
    user.
    """

    def test_first_run_warns_and_carries_on(self, app_root, monkeypatch) -> None:
        """
        The initial write fails, and the defaults are still in memory.

        The folder tree and ``sys.path`` must still be set up, since nothing
        downstream re-does them.
        """
        _block_writes_to(monkeypatch, _config_path(app_root))

        stub = _run(app_root)

        assert stub.app_config == default_app_config(
            Path(app_root, "Poriscope", "user_plugins")
        )
        assert not _config_path(app_root).exists()
        assert Path(app_root, "Poriscope", "logs").is_dir()
        assert str(Path(app_root, "Poriscope").resolve()) in sys.path
        stub.logger.warning.assert_called_once()
        assert "Unable to write initial config file" in stub.logger.warning.call_args[0][0]

    def test_a_failed_backfill_write_still_repairs_memory(
        self, app_root, monkeypatch
    ) -> None:
        """
        The backfill is reported twice and the in-memory config is complete anyway.

        Once for the missing key, once for being unable to persist it - the
        launch succeeds with a correct config that simply will not stick.
        """
        _run(app_root)
        _config_path(app_root).write_text(
            json.dumps({"Parent Folder": "D:/kept"}), encoding="utf-8"
        )
        _block_writes_to(monkeypatch, _config_path(app_root))

        stub = _run(app_root)

        assert stub.app_config["Log Level"] == logging.WARNING
        assert stub.app_config["Parent Folder"] == "D:/kept"
        messages = [call.args[0] for call in stub.logger.warning.call_args_list]
        assert any("restored to default" in m for m in messages)
        assert any("Unable to persist updated config file" in m for m in messages)

    def test_a_failed_regeneration_write_still_returns_defaults(
        self, app_root, monkeypatch
    ) -> None:
        """
        A corrupt config that also cannot be replaced still yields a usable default.

        The file is left as it was, so the same repair is attempted next launch.
        """
        _run(app_root)
        _config_path(app_root).write_text("{not json at all", encoding="utf-8")
        _block_writes_to(monkeypatch, _config_path(app_root))

        stub = _run(app_root)

        assert stub.app_config == default_app_config(
            Path(app_root, "Poriscope", "user_plugins")
        )
        messages = [call.args[0] for call in stub.logger.warning.call_args_list]
        assert any("regenerating defaults" in m for m in messages)
        assert any(
            "Unable to persist regenerated default config file" in m for m in messages
        )
        assert _config_path(app_root).read_text(encoding="utf-8") == "{not json at all"
