"""
What ``BaseDataPlugin.apply_settings`` keeps, and what it leaves alone.

A plugin keeps its own copy of the settings it was given, with each plugin it depends
on recorded by name. The caller's dict is neither kept nor changed, so a script can
build a second plugin from the same dict, and nothing outside the plugin shares a dict
with it.
"""

import copy
from typing import Any, Dict

from tests.unit.utils.test_base_data_plugin_validation import ConcretePlugin


def parent_plugin(key: str) -> ConcretePlugin:
    """
    :param key: the parent's name
    :type key: str
    :return: a live plugin with that name
    :rtype: ConcretePlugin
    """
    parent = ConcretePlugin()
    parent.set_key(key)
    return parent


def settings_with(parent: ConcretePlugin) -> Dict[str, Dict[str, Any]]:
    """
    Settings naming a live parent plugin, as the controller and a script hand them over.

    :param parent: the parent
    :type parent: ConcretePlugin
    :return: the settings
    :rtype: Dict[str, Dict[str, Any]]
    """
    return {
        "MetaParent": {"Type": None, "Value": parent, "Options": None},
        "Threshold": {"Type": int, "Value": 4, "Options": [2, 4, 6]},
    }


def test_the_callers_dict_is_left_as_it_was() -> None:
    parent = parent_plugin("parent")
    settings = settings_with(parent)
    given = {name: dict(entry) for name, entry in settings.items()}

    ConcretePlugin(settings)

    assert settings == given
    assert settings["MetaParent"]["Value"] is parent


def test_a_script_can_build_two_plugins_from_one_dict() -> None:
    parent = parent_plugin("parent")
    settings = settings_with(parent)

    first = ConcretePlugin(settings)
    second = ConcretePlugin(settings)

    assert first.settings["MetaParent"]["Value"] is parent
    assert second.settings["MetaParent"]["Value"] is parent


def test_the_plugin_records_its_parent_by_name() -> None:
    plugin = ConcretePlugin(settings_with(parent_plugin("parent")))

    reported = plugin.get_raw_settings()

    assert reported["MetaParent"]["Value"] == "parent"
    copy.deepcopy(reported)


def test_the_plugin_shares_no_dict_or_list_with_the_caller() -> None:
    settings = settings_with(parent_plugin("parent"))
    plugin = ConcretePlugin(settings)

    settings["Threshold"]["Value"] = 6
    settings["Threshold"]["Options"].append(8)

    assert plugin.get_raw_settings()["Threshold"] == {
        "Type": int,
        "Value": 4,
        "Options": [2, 4, 6],
    }


def test_a_plugin_moved_to_another_parent_forgets_the_old_one() -> None:
    plugin = ConcretePlugin(settings_with(parent_plugin("first")))

    plugin.apply_settings(settings_with(parent_plugin("second")))

    assert plugin.get_parents() == {("ConcretePlugin", "second")}
