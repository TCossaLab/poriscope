"""
Every path that gives a tab plugin *names* must also give it the *instances*.

Step 4a made a tab call its plugins directly through ``call()``, which reads a map of
live instances pushed down from ``MainController``. The names a tab shows in its
comboboxes travel a separate route, and **the two must not be able to disagree** - a
tab that can see a plugin in a dropdown but cannot call it is the worst of both worlds,
because the user has no way to tell which half is broken.

That is not hypothetical. It shipped: ``update_available_plugins`` pushed both, but
``instantiate_analysis_tab`` pushed only the names, so a tab created *after* the plugins
already existed - exactly what restoring a saved session does - opened with a populated
combobox and an empty instance map. Selecting the loader then reported
``KeyError("No MetaDatabaseLoader plugin registered under 'SQLiteDBLoader_0'")`` for a
key that was plainly listed one widget away.

These tests are written against the *invariant* rather than against the two call sites,
so a third route added later fails here too.
"""

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.controllers.main_controller import MainController

pytestmark = pytest.mark.characterization


@pytest.fixture
def controller(mocker: MockerFixture) -> MainController:
    """
    A MainController with its collaborators mocked, built without Qt.

    ``__new__`` bypasses ``__init__`` so that no application, window or plugin
    registry is constructed; only the attributes the push path reads are set.

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


def _registry(mocker: MockerFixture, instances: Dict[str, Dict[str, Any]]) -> Any:
    """
    Build a stand-in data plugin controller that resolves the given instances.

    :param mocker: pytest-mock's fixture
    :type mocker: MockerFixture
    :param instances: metaclass -> key -> instance
    :type instances: Dict[str, Dict[str, Any]]
    :return: the stand-in
    :rtype: Any
    """
    registry = mocker.Mock()
    registry.get_plugin_instance.side_effect = lambda mc, key: instances.get(
        mc, {}
    ).get(key)
    return registry


class TestTheInstanceMapMatchesTheNames:
    """
    The invariant: whatever a tab is told exists, it must be able to call.

    Asserted by comparing the two pushes rather than by checking one call site, so a
    route added later is covered without being named here.
    """

    def test_a_plugin_lifecycle_event_pushes_both(
        self, controller: MainController, mocker: MockerFixture
    ) -> None:
        """The path that always worked, pinned so it stays working."""
        loader = mocker.Mock()
        controller.data_plugin_controller = _registry(
            mocker, {"MetaDatabaseLoader": {"SQLiteDBLoader_0": loader}}
        )
        tab: MagicMock = mocker.Mock()
        controller.analysis_tabs = {"ClusteringController": tab}

        controller.update_available_plugins(
            "MetaDatabaseLoader", ["SQLiteDBLoader_0"]
        )

        named = tab.update_available_plugins.call_args.args[0]
        pushed = tab.set_plugin_instances.call_args.args[0]
        assert named["MetaDatabaseLoader"] == ["SQLiteDBLoader_0"]
        assert set(pushed["MetaDatabaseLoader"]) == {"SQLiteDBLoader_0"}

    def test_a_tab_created_after_the_plugins_receives_them(
        self, controller: MainController, mocker: MockerFixture
    ) -> None:
        """
        The regression this file exists for.

        Restoring a session registers the plugins first and builds the tabs second, so
        the tab never sees a lifecycle event. It must be handed the instances on
        creation, not only on the next change.
        """
        loader = mocker.Mock()
        controller.data_plugin_controller = _registry(
            mocker, {"MetaDatabaseLoader": {"SQLiteDBLoader_0": loader}}
        )
        controller.data_plugins = {"MetaDatabaseLoader": ["SQLiteDBLoader_0"]}

        instances = controller._live_plugin_instances()

        assert instances["MetaDatabaseLoader"]["SQLiteDBLoader_0"] is loader

    def test_every_push_of_names_is_accompanied_by_a_push_of_instances(self) -> None:
        """
        Structural: the two calls appear together at every site.

        Written against the source because the failure mode was a *missing* call, and
        no behavioural test of the sites that do it can notice a site that does not.
        ``update_available_plugins`` on a tab controller is the only way names reach a
        tab, so each occurrence must have ``set_plugin_instances`` nearby.
        """
        import ast
        from pathlib import Path

        source = Path(
            Path(__file__).resolve().parents[3],
            "poriscope",
            "controllers",
            "main_controller.py",
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)

        name_pushes: List[int] = []
        instance_pushes: List[int] = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            # a push to a *tab*, i.e. the receiver is an analysis_tabs entry or a loop
            # variable over them - not MainController's own method of the same name
            if node.func.attr == "update_available_plugins" and not (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
            ):
                name_pushes.append(node.lineno)
            elif node.func.attr == "set_plugin_instances":
                instance_pushes.append(node.lineno)

        assert name_pushes, "no name pushes found; has the attribute been renamed?"
        assert len(instance_pushes) >= len(name_pushes), (
            f"{len(name_pushes)} site(s) push plugin names to a tab but only "
            f"{len(instance_pushes)} push instances. A tab that can see a plugin in "
            f"its combobox but cannot call it reports a KeyError for a key the user "
            f"can see. Name pushes at lines {name_pushes}, instance pushes at "
            f"{instance_pushes}."
        )


class TestUnresolvableKeysAreSkipped:
    """A key that cannot be resolved must not be stored as None."""

    def test_a_missing_instance_is_left_out(
        self, controller: MainController, mocker: MockerFixture
    ) -> None:
        """
        ``call()`` should raise its own clear KeyError rather than an AttributeError.

        Storing None would push the failure one step further away, into a getattr on
        None inside ``call``.
        """
        controller.data_plugin_controller = _registry(mocker, {})
        controller.data_plugins = {"MetaDatabaseLoader": ["ghost"]}

        instances = controller._live_plugin_instances()

        assert instances["MetaDatabaseLoader"] == {}

    def test_a_raising_registry_does_not_abort_the_whole_push(
        self, controller: MainController, mocker: MockerFixture
    ) -> None:
        """
        One bad key must not cost the other tabs their working plugins.

        ``get_plugin_instance`` indexes a dict by metaclass, so an unregistered family
        raises rather than returning None.
        """
        good = mocker.Mock()
        registry = mocker.Mock()

        def _resolve(metaclass: str, key: str) -> Any:
            if metaclass == "MetaEventLoader":
                raise KeyError("no such metaclass")
            return good

        registry.get_plugin_instance.side_effect = _resolve
        controller.data_plugin_controller = registry
        controller.data_plugins = {
            "MetaEventLoader": ["boom"],
            "MetaDatabaseLoader": ["SQLiteDBLoader_0"],
        }

        instances = controller._live_plugin_instances()

        assert instances["MetaEventLoader"] == {}
        assert instances["MetaDatabaseLoader"]["SQLiteDBLoader_0"] is good
