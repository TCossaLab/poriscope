"""
Characterization tests for ``App.create_appdata_folders``.

This is the app's first-run bootstrap: it creates ``Poriscope/`` and its four
subfolders under the platform's user data directory, writes or repairs
``config/config.json``, and puts the user-plugin folder's *parent* on
``sys.path`` so plugin discovery can import from it.

It was at **0% coverage** - 52 statements, none of them executed by any test -
while being complexity 17 and the thing that runs before anything else in the
application. Step 5c.5 splits it, so it is pinned first (5c.1).

These drive a stub that **borrows the real methods off ``App``**, so the code
under test is the shipped code, but no ``QApplication`` is constructed - one would
collide with the one pytest-qt manages. The stub needs nothing of its own but a
logger, because the method assigns every other attribute it uses.

Borrowing rather than subclassing is what keeps 5c.5's helpers honest: each is
listed below by name, so a helper added to ``create_appdata_folders`` without
being brought across fails loudly here instead of being quietly mocked away.

Two globals are involved and both are restored by fixture rather than left to
chance: ``user_data_dir`` is redirected into ``tmp_path`` so the developer's real
``%LOCALAPPDATA%\\Poriscope`` is never touched, and ``sys.path`` is swapped for a
copy, since the method appends to it.
"""

import ast
import builtins
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from poriscope.main_app import App
from poriscope.utils.app_config import default_app_config

REPO_ROOT = Path(__file__).resolve().parents[2]


class _StubApp:
    """
    A stand-in for ``App`` carrying the real bootstrap methods and a mock logger.

    The methods are taken off ``App`` unbound and rebound here, so these tests
    run the shipped implementations rather than copies of them, while leaving
    ``QApplication.__init__`` out of it entirely.
    """

    create_appdata_folders = App.create_appdata_folders
    initialize_components = App.initialize_components
    _ensure_folder = App._ensure_folder
    _write_config = App._write_config
    _backfill_missing_config = App._backfill_missing_config

    def __init__(self) -> None:
        """
        Give the stub the mock logger the methods report failures through.

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
    stub.create_appdata_folders()
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
        assert written == default_app_config(
            Path(app_root, "Poriscope", "user_plugins")
        )
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
        The parent goes on the path, so the folder can be imported as a package.

        This only works when the folder is named like an identifier, which is why
        the folder itself goes on too - see the test below.
        """
        _run(app_root)

        expected = str(Path(app_root, "Poriscope").resolve())
        assert expected in sys.path

    def test_adds_the_user_plugin_folder_itself(self, app_root) -> None:
        """
        The folder itself is what makes a multi-file plugin work.

        An analysis tab is three files and its Controller imports the other two. The
        parent alone cannot carry that: it requires an import naming the folder, and a
        folder called "User Plugins" - as a real installation had it - cannot be named
        in any import statement at all, so the generated Controller was a SyntaxError.
        With the folder on the path the siblings import by their own file names, which
        are always identifiers because each equals the class it defines.
        """
        _run(app_root)

        expected = str(Path(app_root, "Poriscope", "user_plugins").resolve())
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
        assert (
            "Unable to write initial config file" in stub.logger.warning.call_args[0][0]
        )

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


# ------------- 5c.5: the extracted helpers --------------------------------
#
# Each is in the refactor-coverage audit's MOVED table, so each is driven
# directly as well as through create_appdata_folders.


class TestEnsureFolder:
    """Create a folder if it is not there, and hand back its path."""

    def test_creates_a_missing_folder_and_returns_it(self, tmp_path) -> None:
        """Returning the path is what lets the caller name and create in one line."""
        target = Path(tmp_path, "made", "deeply")

        returned = _StubApp()._ensure_folder(target)

        assert returned == target
        assert target.is_dir()

    def test_leaves_an_existing_folder_and_its_contents_alone(self, tmp_path) -> None:
        """Second and later launches take this path for every folder."""
        target = Path(tmp_path, "already")
        target.mkdir()
        marker = Path(target, "keep.txt")
        marker.write_text("kept", encoding="utf-8")

        assert _StubApp()._ensure_folder(target) == target
        assert marker.read_text(encoding="utf-8") == "kept"

    def test_does_not_raise_when_a_file_occupies_the_path(self, tmp_path) -> None:
        """
        The reason the existence check is kept rather than left to ``exist_ok``.

        ``mkdir(exist_ok=True)`` still raises when the path is a *file*, and
        startup - before the logger has a handler and before any window exists -
        is the wrong place to start raising.
        """
        occupied = Path(tmp_path, "notadir")
        occupied.write_text("in the way", encoding="utf-8")

        assert _StubApp()._ensure_folder(occupied) == occupied
        assert occupied.is_file()


class TestWriteConfig:
    """One write, three callers, three verbs."""

    def test_writes_the_configuration(self, tmp_path) -> None:
        """The ordinary case, which is also the first-run case."""
        path = Path(tmp_path, "config.json")

        _StubApp()._write_config(path, {"Log Level": 30}, "write initial")

        assert json.loads(path.read_text(encoding="utf-8")) == {"Log Level": 30}

    @pytest.mark.parametrize(
        "attempt, expected",
        [
            ("write initial", "Unable to write initial config file"),
            ("persist updated", "Unable to persist updated config file"),
            (
                "persist regenerated default",
                "Unable to persist regenerated default config file",
            ),
        ],
    )
    def test_the_verb_reads_into_the_warning(
        self, tmp_path, monkeypatch, attempt, expected
    ) -> None:
        """
        The three call sites differed only here, so the three messages are pinned.

        These are what a user sees when the config directory is not writable, and
        folding them into one method is exactly the edit that could have changed
        them without anything noticing.

        :param attempt: The verb phrase the caller passes.
        :param expected: The warning that verb must produce.
        """
        path = Path(tmp_path, "config.json")
        _block_writes_to(monkeypatch, path)
        stub = _StubApp()

        stub._write_config(path, {}, attempt)

        stub.logger.warning.assert_called_once()
        assert expected in stub.logger.warning.call_args[0][0]

    def test_a_failed_write_does_not_raise(self, tmp_path, monkeypatch) -> None:
        """
        None of the three callers may raise: there is nothing yet to report to.

        :param tmp_path: pytest's per-test temporary directory
        :param monkeypatch: pytest's monkeypatch fixture
        """
        path = Path(tmp_path, "config.json")
        _block_writes_to(monkeypatch, path)

        _StubApp()._write_config(path, {}, "write initial")

        assert not path.exists()


class TestBackfillMissingConfig:
    """Restore whatever the stored configuration is missing."""

    def test_does_nothing_when_every_default_is_present(self, tmp_path) -> None:
        """The common case, and it must not rewrite the file or warn."""
        path = Path(tmp_path, "config.json")
        stub = _StubApp()
        stub.user_plugin_path = Path(tmp_path, "user_plugins")
        stub.app_config = default_app_config(stub.user_plugin_path)

        stub._backfill_missing_config(path)

        stub.logger.warning.assert_not_called()
        assert not path.exists()

    def test_restores_every_missing_default_and_names_them(self, tmp_path) -> None:
        """Every default, not just the one added most recently."""
        path = Path(tmp_path, "config.json")
        stub = _StubApp()
        stub.user_plugin_path = Path(tmp_path, "user_plugins")
        stub.app_config = {"Parent Folder": "D:/kept"}

        stub._backfill_missing_config(path)

        assert stub.app_config["Parent Folder"] == "D:/kept"
        assert stub.app_config["Log Level"] == logging.WARNING
        assert "User Plugin Folder" in stub.app_config
        warned = stub.logger.warning.call_args[0][0]
        assert "Log Level" in warned and "restored to default" in warned
        assert json.loads(path.read_text(encoding="utf-8")) == stub.app_config

    def test_lets_a_wrongly_shaped_config_fail(self, tmp_path) -> None:
        """
        Valid JSON that is not an object raises here, and the caller treats that
        as a corrupt config - the same outcome as unparseable text, and the right
        one. Being defensive here would swallow it and leave a list in app_config.
        """
        stub = _StubApp()
        stub.user_plugin_path = Path(tmp_path, "user_plugins")
        stub.app_config = [1, 2, 3]

        with pytest.raises(TypeError):
            stub._backfill_missing_config(Path(tmp_path, "config.json"))


# ------------- The guard that was missing --------------------------------


class TestAppIsWhole:
    """
    Every method ``App`` calls on itself exists.

    This is here because 5c.5 deleted ``initialize_components`` - a splice
    anchored on the method before it and the method after it took out the one in
    between - and **the entire suite stayed green**. 4,287 tests passed over an
    application that could not start, because nothing constructs ``App``:
    ``App`` is a ``QApplication`` subclass and only one of those may exist in a
    process, so the tests above deliberately borrow its methods onto a stub
    instead.

    That stub is what made the deletion invisible. It borrows the methods it
    names, so a method nothing borrows can vanish without a single failure. This
    reads the class itself instead, which is the one check that does not depend
    on anything being instantiated or borrowed.

    It is a shallow guard - it proves the methods exist, not that they work - but
    the failure it catches is total, and it is the failure that actually
    happened.
    """

    @staticmethod
    def _app_class() -> ast.ClassDef:
        """
        Parse ``main_app.py`` and return the ``App`` class node.

        :return: the ``App`` class definition
        :rtype: ast.ClassDef
        """
        source = Path(App.__module__.replace(".", "/") + ".py")
        tree = ast.parse(
            Path(REPO_ROOT, source).read_text(encoding="utf-8"), filename=str(source)
        )
        return next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "App"
        )

    def test_every_self_call_resolves_to_a_defined_method(self) -> None:
        """A method the class calls on itself but does not define cannot ever run."""
        cls = self._app_class()
        defined = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        called = {
            n.func.attr
            for n in ast.walk(cls)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "self"
        }

        missing = sorted(called - defined)
        assert not missing, (
            f"App calls {missing} on itself but does not define them. "
            f"A refactor that moves or replaces a block of this class can drop a "
            f"method whole, and no other test constructs App to notice."
        )

    def test_the_startup_sequence_is_present(self) -> None:
        """
        The three steps ``__init__`` runs, named explicitly.

        Deliberately a literal list rather than derived from ``__init__``: the
        point is to fail if one of these disappears, and a check that reads the
        same source it is checking would disappear with it.
        """
        cls = self._app_class()
        defined = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}

        for required in (
            "create_appdata_folders",
            "configure_logger",
            "initialize_components",
        ):
            assert required in defined, f"App.{required} is gone; the app cannot start"


class TestInitializeComponents:
    """
    The step that builds the app-shell triad.

    Borrowing the real method and patching the three classes by their names *in
    this module* is what makes this catch both halves of the 5c.5 near-miss: the
    borrow fails if the method is gone, and ``mocker.patch`` fails if the import
    it needs has been removed from ``main_app``.

    That second half is not hypothetical. When the splice deleted
    ``initialize_components``, its three imports became unused and ``ruff --fix``
    removed them - so the tree was self-consistent, every gate passed, and the
    application could not start. The auto-fixer tidied away the evidence.
    """

    def test_builds_the_model_view_and_controller(self, mocker) -> None:
        """
        Model first, then view from the model's plugins, then controller over both.

        The order is the wiring: ``MainView`` needs the available plugins the
        model discovers, and ``MainController`` needs both.

        :param mocker: pytest-mock fixture
        :type mocker: pytest_mock.MockerFixture
        """
        model_cls = mocker.patch("poriscope.main_app.MainModel")
        view_cls = mocker.patch("poriscope.main_app.MainView")
        controller_cls = mocker.patch("poriscope.main_app.MainController")

        stub = _StubApp()
        stub.app_config = {"Log Level": logging.WARNING}

        stub.initialize_components()

        model_cls.assert_called_once_with(stub.app_config)
        view_cls.assert_called_once_with(
            model_cls.return_value.get_available_plugins.return_value
        )
        controller_cls.assert_called_once_with(
            model_cls.return_value, view_cls.return_value
        )
        assert stub.main_model is model_cls.return_value
        assert stub.main_view is view_cls.return_value
        assert stub.main_controller is controller_cls.return_value
