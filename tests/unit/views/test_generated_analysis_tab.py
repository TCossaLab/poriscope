"""
The acceptance test for ``scripts/new_plugin.py``'s analysis-tab half.

Every other assertion about the generator is static - it parses the generated files, or
imports them far enough to look at the classes - and lives beside the generator's own tests
in ``tests/unit/scripts``. This one is different in kind: it builds the generated triad into
a live Qt widget tree and drives the handful of methods the app calls on a tab it has just
opened. That is the only way to show that a freshly generated tab *runs* rather than merely
type-checks, and it is the promise the scaffold makes.

It lives here rather than in ``tests/unit/scripts`` because constructing a ``MetaView``
builds a Matplotlib ``FigureCanvas`` parented to a Qt widget, and everything that makes that
safe - the offscreen Qt platform, the ``Agg`` backend, the dialog guard and the widget
teardown that stops the PySide/Matplotlib segfaults - is set up by this directory's
``conftest.py`` and nowhere else. The same reasoning already puts the five shipped tabs'
Views under this directory rather than under ``tests/unit/plugins``.
"""

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "new_plugin.py")

# Deliberately not an identifier, and named after the folder in the installation that found
# the bug. Outside the repository the generated Controller imports its siblings by their
# bare file names and the app puts the plugin folder itself on ``sys.path``; generating into
# "User Plugins" is what proves that holds for a folder no import could ever name.
TAB_FOLDER = "User Plugins"
TAB_NAME = "Acceptance"


@pytest.fixture(scope="module")
def script() -> types.ModuleType:
    """
    Import ``scripts/new_plugin.py`` by path, since ``scripts/`` is not a package.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("new_plugin", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def generated_tab(
    script: types.ModuleType, tmp_path: Path, monkeypatch: Any
) -> Dict[str, type]:
    """
    Generate a tab and import its three classes the way the running app imports one.

    :param script: the generator module
    :type script: types.ModuleType
    :param tmp_path: the folder to generate the tab's folder into
    :type tmp_path: Path
    :param monkeypatch: pytest's monkeypatch fixture, used to undo the path change
    :type monkeypatch: Any
    :return: the three generated classes, keyed by role suffix
    :rtype: Dict[str, type]
    """
    # The folder itself goes on sys.path, never its parent, because its name is not an
    # identifier - which is the point of choosing that name here.
    folder = Path(tmp_path, TAB_FOLDER)
    argv = [
        script.TAB,
        TAB_NAME,
        "--output-dir",
        str(folder),
        "--author",
        "Test Author",
    ]
    assert script.main(argv) == 0

    monkeypatch.syspath_prepend(str(folder))
    for role in script.TRIAD:
        sys.modules.pop(f"{TAB_NAME}{role.suffix}", None)
    importlib.invalidate_caches()

    loaded: Dict[str, type] = {}
    for role in script.TRIAD:
        module = importlib.import_module(f"{TAB_NAME}{role.suffix}")
        loaded[role.suffix] = getattr(module, f"{TAB_NAME}{role.suffix}")
    for role in script.TRIAD:
        monkeypatch.delitem(sys.modules, f"{TAB_NAME}{role.suffix}", raising=False)
    return loaded


class TestAGeneratedTabRuns:
    """A generated triad has to be a working tab, not merely a set of legal classes."""

    def test_the_controller_constructs_its_whole_triad(self, qapp, generated_tab):
        """
        ``MetaController.__init__`` runs ``_init`` and then connects nine signals across
        the View and the Model. Constructing it is what proves the generated ``_init``
        built both of them, and that every base-class connection finds its slot.
        """
        tab = generated_tab["Controller"]({"MetaReader": ["BinaryReader"]})
        assert isinstance(tab.view, generated_tab["View"])
        assert isinstance(tab.model, generated_tab["Model"])

    def test_the_view_is_a_widget_the_shell_can_add_as_a_page(
        self, qapp, generated_tab
    ):
        """``MainController`` hands ``tab.view`` straight to ``MainView.add_page``."""
        from PySide6.QtWidgets import QWidget

        tab = generated_tab["Controller"]()
        assert isinstance(tab.view, QWidget)
        assert tab.view.layout() is not None

    def test_the_available_subclasses_the_shell_passes_reach_the_view(
        self, qapp, generated_tab
    ):
        """The one constructor argument the shell supplies has to land somewhere."""
        subclasses = {"MetaReader": ["BinaryReader"]}
        tab = generated_tab["Controller"](subclasses)
        assert tab.view.available_subclasses == subclasses

    def test_update_available_plugins_records_what_it_is_told(
        self, qapp, generated_tab
    ):
        """
        ``MainController`` calls this on every tab whenever any plugin is instantiated.
        The generated override delegates, so the record the base keeps survives - which is
        the failure this stub's ``super()`` call exists to prevent.
        """
        tab = generated_tab["Controller"]()
        available = {"MetaReader": ["BinaryReader_0"]}
        tab.view.update_available_plugins(available)
        assert tab.view.available_plugins == available

    def test_notify_plugin_state_changed_is_safe_to_call(self, qapp, generated_tab):
        """Called on every tab for a change in any other; a new tab must tolerate it."""
        tab = generated_tab["Controller"]()
        tab.view.notify_plugin_state_changed(
            "MetaDatabaseLoader", "SQLite_0", "columns"
        )

    def test_reset_actions_is_safe_to_call(self, qapp, generated_tab):
        """The base calls this whenever a tab's action history is replayed or cleared."""
        tab = generated_tab["Controller"]()
        tab.view._reset_actions()
