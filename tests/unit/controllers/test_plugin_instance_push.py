"""
A tab must be able to call every plugin it is showing, and be able to before it shows it.

Step 4a made a tab call its plugins directly through ``MetaModel.call``, which reads a
map of live instances pushed down from ``MainController``. The *names* a tab shows in its
comboboxes are pushed separately, and this file holds the two invariants that keeps
honest:

1. **Every route that pushes names pushes instances.** A tab that can see a plugin in a
   dropdown but cannot call it is the worst of both worlds - the user has no way to tell
   which half is broken.
2. **Instances go first.** Handing a tab the names populates its comboboxes, and
   populating a combobox fires a selection change *synchronously* - which is when the tab
   asks the selected loader for its columns. Names first, and that call finds an empty
   map.

Both failed in real use. Restoring a session with one clustering tab and one database
loader reported ``KeyError("No MetaDatabaseLoader plugin registered under
'SQLiteDBLoader_0'")`` for a key listed one widget away: first because
``instantiate_analysis_tab`` pushed only names, and then, after that was fixed, because
the push order within the notification was wrong.

Both instances and names now come from **one registry** -
``DataPluginModel.get_plugin_instances`` and ``get_instantiated_plugins_list`` read the
same dict - so they cannot disagree about *what* exists. Only the order can be wrong,
which is what test_instances_are_pushed_before_names is for.
"""

import ast
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.controllers.main_controller import MainController

pytestmark = pytest.mark.characterization

MAIN_CONTROLLER = Path(
    Path(__file__).resolve().parents[3],
    "poriscope",
    "controllers",
    "main_controller.py",
)


@pytest.fixture
def controller(mocker: MockerFixture) -> MainController:
    """
    A MainController with its collaborators mocked, built without Qt.

    ``__new__`` bypasses ``__init__`` so that no application, window or plugin registry
    is constructed; only the attributes the push path reads are set.

    :param mocker: pytest-mock's fixture
    :type mocker: MockerFixture
    :return: the controller under test
    :rtype: MainController
    """
    ctrl: MainController = MainController.__new__(MainController)
    ctrl.logger = mocker.Mock()  # type: ignore[attr-defined]
    ctrl.data_plugins = {}
    ctrl.analysis_tabs = {}
    ctrl.data_plugin_controller = mocker.Mock()
    return ctrl


class TestNamesAndInstancesTravelTogether:
    """Invariant 1: whatever a tab is told exists, it must be able to call."""

    def test_a_lifecycle_event_pushes_both(
        self, controller: MainController, mocker: MockerFixture
    ) -> None:
        """The notification every creation, deletion and rename route already emits."""
        loader = mocker.Mock()
        controller.data_plugin_controller.get_plugin_instances.return_value = {
            "MetaDatabaseLoader": {"SQLiteDBLoader_0": loader}
        }
        tab: MagicMock = mocker.Mock()
        controller.analysis_tabs = {"ClusteringController": tab}

        controller.update_available_plugins("MetaDatabaseLoader", ["SQLiteDBLoader_0"])

        named = tab.update_available_plugins.call_args.args[0]
        pushed = tab.set_plugin_instances.call_args.args[0]
        assert named["MetaDatabaseLoader"] == ["SQLiteDBLoader_0"]
        assert pushed["MetaDatabaseLoader"]["SQLiteDBLoader_0"] is loader

    def test_the_instances_come_from_the_registry_that_owns_them(
        self, controller: MainController, mocker: MockerFixture
    ) -> None:
        """
        Asked for as one map, not rebuilt key by key.

        The first attempt at this rebuilt the map from ``self.data_plugins`` - a *copy*
        of the names - by resolving each key individually. Asking the owner instead
        means there is one source of truth and nothing to skip.
        """
        controller.data_plugin_controller.get_plugin_instances.return_value = {}
        controller.analysis_tabs = {"ClusteringController": mocker.Mock()}

        controller.update_available_plugins("MetaDatabaseLoader", ["L"])

        controller.data_plugin_controller.get_plugin_instances.assert_called_once()

    def test_every_site_that_pushes_names_also_pushes_instances(self) -> None:
        """
        Structural, because the failure mode was a *missing* call.

        No behavioural test of the sites that do push can notice a site that does not,
        so this counts them in the source. Written against the invariant rather than
        against the known sites, so a third route added later fails here too.
        """
        tree = ast.parse(MAIN_CONTROLLER.read_text(encoding="utf-8"))

        name_pushes: List[int] = []
        instance_pushes: List[int] = []
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            ):
                continue
            # a push to a *tab* - not MainController's own method of the same name
            if node.func.attr == "update_available_plugins" and not (
                isinstance(node.func.value, ast.Name) and node.func.value.id == "self"
            ):
                name_pushes.append(node.lineno)
            elif node.func.attr == "set_plugin_instances":
                instance_pushes.append(node.lineno)

        assert name_pushes, "no name pushes found; has the attribute been renamed?"
        assert len(instance_pushes) >= len(name_pushes), (
            f"{len(name_pushes)} site(s) push plugin names to a tab but only "
            f"{len(instance_pushes)} push instances. A tab that can see a plugin in its "
            f"combobox but cannot call it reports a KeyError for a key the user can see. "
            f"Name pushes at lines {name_pushes}, instance pushes at {instance_pushes}."
        )


class TestInstancesArePushedFirst:
    """
    Invariant 2: the order is load-bearing, not cosmetic.

    Populating a combobox fires a selection change synchronously, and that is when a tab
    asks its selected loader for columns. Push the names first and that call runs against
    an empty instance map - which is the bug that survived the first fix.
    """

    def test_instances_are_pushed_before_names(
        self, controller: MainController, mocker: MockerFixture
    ) -> None:
        """Recorded per tab, in call order."""
        controller.data_plugin_controller.get_plugin_instances.return_value = {
            "MetaDatabaseLoader": {"L": mocker.Mock()}
        }
        order: List[str] = []
        tab = mocker.Mock()
        tab.set_plugin_instances.side_effect = lambda *_: order.append("instances")
        tab.update_available_plugins.side_effect = lambda *_: order.append("names")
        controller.analysis_tabs = {"ClusteringController": tab}

        controller.update_available_plugins("MetaDatabaseLoader", ["L"])

        assert order == ["instances", "names"], (
            "names were pushed before instances; populating a combobox fires a "
            "selection change synchronously, so the tab asks for columns while its "
            "instance map is still empty"
        )

    def test_a_tab_can_call_what_it_is_being_told_about_during_the_push(
        self, controller: MainController, mocker: MockerFixture
    ) -> None:
        """
        The real sequence, simulated: the combobox asks back mid-push.

        Standing in for the synchronous selection change, this tab tries to use its
        instance map at the moment it receives the names. That is precisely when the
        reported KeyError happened, so it must succeed here.
        """
        loader = mocker.Mock()
        controller.data_plugin_controller.get_plugin_instances.return_value = {
            "MetaDatabaseLoader": {"SQLiteDBLoader_0": loader}
        }
        seen: Dict[str, Any] = {}
        tab = mocker.Mock()

        def _remember(instances: Dict[str, Dict[str, Any]]) -> None:
            seen.update(instances)

        def _on_names(_names: Dict[str, List[str]]) -> None:
            # what the combobox's selection change does, synchronously
            seen["resolved_during_names"] = seen.get("MetaDatabaseLoader", {}).get(
                "SQLiteDBLoader_0"
            )

        tab.set_plugin_instances.side_effect = _remember
        tab.update_available_plugins.side_effect = _on_names
        controller.analysis_tabs = {"ClusteringController": tab}

        controller.update_available_plugins("MetaDatabaseLoader", ["SQLiteDBLoader_0"])

        assert seen["resolved_during_names"] is loader

    def test_the_instantiation_site_pushes_in_the_same_order(self) -> None:
        """
        Structural: both sites order it the same way.

        ``instantiate_analysis_tab`` builds a real tab, so its ordering is checked in
        the source rather than by constructing one. Within each of the two push sites,
        ``set_plugin_instances`` must appear before ``update_available_plugins``.
        """
        source = MAIN_CONTROLLER.read_text(encoding="utf-8")
        tree = ast.parse(source)

        checked = 0
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in (
                "update_available_plugins",
                "instantiate_analysis_tab",
            ):
                continue
            instance_line = names_line = None
            for inner in ast.walk(node):
                if not (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                ):
                    continue
                if inner.func.attr == "set_plugin_instances":
                    instance_line = inner.lineno
                elif inner.func.attr == "update_available_plugins" and not (
                    isinstance(inner.func.value, ast.Name)
                    and inner.func.value.id == "self"
                ):
                    names_line = inner.lineno
            if instance_line is not None and names_line is not None:
                checked += 1
                assert instance_line < names_line, (
                    f"{node.name} pushes names (line {names_line}) before instances "
                    f"(line {instance_line}); the order is load-bearing"
                )

        assert checked == 2, f"expected two push sites, checked {checked}"
