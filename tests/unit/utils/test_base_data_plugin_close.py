"""
Closing a data plugin releases the whole plugin, and a plugin holding nothing need not say so.

``close_resources`` runs when the app quits, when a plugin is deleted and when a script's
``with`` block ends, and in each case the caller means the whole plugin: no caller has a
channel to give, and the two shipped plugins that hold anything (the SQLite writers) each
hold one connection shared by every channel. So it takes no channel, and ``BaseDataPlugin``
provides a do-nothing default rather than making every plugin write an empty one.
"""

import inspect

import pytest

from poriscope.plugins.filters.BesselFilter import BesselFilter
from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.MetaDatabaseLoader import MetaDatabaseLoader
from poriscope.utils.MetaDatabaseWriter import MetaDatabaseWriter
from poriscope.utils.MetaEventFinder import MetaEventFinder
from poriscope.utils.MetaEventFitter import MetaEventFitter
from poriscope.utils.MetaEventLoader import MetaEventLoader
from poriscope.utils.MetaFilter import MetaFilter
from poriscope.utils.MetaReader import MetaReader
from poriscope.utils.MetaWriter import MetaWriter

DATA_PLUGIN_BASES = (
    BaseDataPlugin,
    MetaReader,
    MetaFilter,
    MetaEventFinder,
    MetaWriter,
    MetaEventLoader,
    MetaEventFitter,
    MetaDatabaseWriter,
    MetaDatabaseLoader,
)


@pytest.mark.parametrize("base", DATA_PLUGIN_BASES, ids=lambda b: b.__name__)
def test_no_data_plugin_base_requires_an_override(base: type) -> None:
    """A plugin family must not make its plugins write a ``close_resources`` of their own."""
    assert "close_resources" not in base.__abstractmethods__


def test_closing_takes_no_channel() -> None:
    """Every caller closes the whole plugin, so the method names nothing narrower."""
    parameters = list(inspect.signature(BaseDataPlugin.close_resources).parameters)
    assert parameters == ["self"]


def test_a_plugin_without_its_own_close_can_be_closed_twice() -> None:
    """The default does nothing, safely, as often as it is called."""
    assert "close_resources" not in vars(BesselFilter)
    plugin = BesselFilter()
    settings = plugin.get_empty_settings(standalone=True)
    settings["Cutoff"]["Value"] = 10000.0
    settings["Samplerate"]["Value"] = 250000.0
    plugin.apply_settings(settings)
    plugin.close_resources()
    plugin.close_resources()
