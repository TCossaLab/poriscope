"""
A script can hand a data plugin its parent plugin object directly.

A plugin that depends on another - a finder on its reader, a writer on its finder, a
fitter on its event loader, a database writer on its fitter - declares that dependency as a
settings key. In the GUI the user picks the parent from a dropdown of names, so the key is
declared ``Type: str``, and ``DataPluginController`` resolves the name to the instance
before applying settings. A script has no names and no controller: it holds the object. So
``get_empty_settings(standalone=True)`` declares the key as the parent's base class, and the
scripting guide's pipeline - assign the object, apply the settings - works as written.
"""

import gc

import pytest

from poriscope.plugins.datareaders.ChimeraReader20240501 import ChimeraReader20240501
from poriscope.plugins.datawriters.SQLiteEventWriter import SQLiteEventWriter
from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.utils.MetaEventFinder import MetaEventFinder
from poriscope.utils.MetaEventFitter import MetaEventFitter
from poriscope.utils.MetaEventLoader import MetaEventLoader
from poriscope.utils.MetaReader import MetaReader
from tests.unit.plugins.conformance._recipes import (
    build_any_reader,
    build_reader_dataset,
)

DEPENDENTS = [
    (ClassicBlockageFinder, "MetaReader", MetaReader),
    (SQLiteEventWriter, "MetaEventFinder", MetaEventFinder),
    (CUSUM, "MetaEventLoader", MetaEventLoader),
    (SQLiteDBWriter, "MetaEventFitter", MetaEventFitter),
]


@pytest.mark.parametrize(
    "plugin_cls, key, parent_base",
    DEPENDENTS,
    ids=[cls.__name__ for cls, _, _ in DEPENDENTS],
)
def test_standalone_declares_the_parent_as_its_base_class(plugin_cls, key, parent_base):
    settings = plugin_cls().get_empty_settings(standalone=True)
    assert settings[key]["Type"] is parent_base


@pytest.mark.parametrize(
    "plugin_cls, key, parent_base",
    DEPENDENTS,
    ids=[cls.__name__ for cls, _, _ in DEPENDENTS],
)
def test_the_gui_still_offers_the_parent_by_name(plugin_cls, key, parent_base):
    settings = plugin_cls().get_empty_settings(
        globally_available_plugins={key: ["Parent_0"]}, standalone=False
    )
    assert settings[key]["Type"] is str
    assert settings[key]["Value"] == "Parent_0"


@pytest.fixture
def reader(tmp_path):
    """
    A real reader over a synthetic recording.

    :param tmp_path: Pytest's per-test temporary directory.
    :type tmp_path: pathlib.Path
    :yield: The opened reader.
    """
    dataset = build_reader_dataset(ChimeraReader20240501, tmp_path)
    opened = build_any_reader(ChimeraReader20240501, dataset)
    yield opened
    opened.close_resources()
    del opened
    gc.collect()


def test_a_script_assigns_the_parent_object_and_applies(reader):
    finder = ClassicBlockageFinder()
    settings = finder.get_empty_settings(standalone=True)
    settings["MetaReader"]["Value"] = reader
    settings["Threshold"]["Value"] = 100.0
    finder.apply_settings(settings)
    assert finder.reader is reader
