"""
Every plugin has a key from the moment it is constructed.

A plugin made in a script is named ``<ClassName>_<n>``, unique in the process, unless it
is given ``key=``. The key is set before any settings are applied, so a parent records
the plugin under the key it keeps - an empty key would merge every scripted dependent of
one parent into a single entry. The GUI still names its plugins with ``set_key``.
"""

from typing import Type

import pytest

from poriscope.plugins.datareaders.TCossaLabABFReader import TCossaLabABFReader
from poriscope.plugins.datawriters.SQLiteEventWriter import SQLiteEventWriter
from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.plugins.eventloaders.SQLiteEventLoader import SQLiteEventLoader
from poriscope.plugins.filters.BesselFilter import BesselFilter
from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from tests.unit.utils.test_base_data_plugin_settings import (
    parent_plugin,
    settings_with,
)
from tests.unit.utils.test_base_data_plugin_validation import ConcretePlugin


def test_a_plugin_made_without_a_key_is_named_for_its_class() -> None:
    first, second = ConcretePlugin(), ConcretePlugin()

    assert first.get_key().startswith("ConcretePlugin_")
    assert second.get_key().startswith("ConcretePlugin_")
    assert first.get_key() != second.get_key()


def test_a_plugin_keeps_the_key_it_is_given() -> None:
    assert ConcretePlugin(key="mine").get_key() == "mine"


@pytest.mark.parametrize(
    "plugin_class",
    [
        TCossaLabABFReader,
        BesselFilter,
        ClassicBlockageFinder,
        SQLiteEventWriter,
        SQLiteEventLoader,
        CUSUM,
        SQLiteDBWriter,
        SQLiteDBLoader,
    ],
    ids=lambda plugin_class: plugin_class.__name__,
)
def test_every_family_takes_a_key(plugin_class: Type[BaseDataPlugin]) -> None:
    """Each of the eight ``Meta*`` constructors passes ``key`` through to the base."""
    assert plugin_class(key="named").get_key() == "named"


def test_a_parent_records_a_dependent_under_the_key_it_was_given() -> None:
    parent = parent_plugin("parent")

    ConcretePlugin(settings_with(parent), key="child")

    assert parent.get_dependents() == {("ConcretePlugin", "child")}


def test_two_unnamed_dependents_of_one_parent_are_two_dependents() -> None:
    parent = parent_plugin("parent")

    first = ConcretePlugin(settings_with(parent))
    second = ConcretePlugin(settings_with(parent))

    assert len(parent.get_dependents()) == 2
    assert parent.get_dependents() == {
        ("ConcretePlugin", first.get_key()),
        ("ConcretePlugin", second.get_key()),
    }
