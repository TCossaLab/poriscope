"""
Resetting a data plugin resets one named channel.

``reset_channel`` runs when a channel is re-analysed or a write is aborted, and every
caller names the channel. Its old ``None`` meant "every channel" in the signature but
was handled by one implementation in four: the fitter wrote ``status[None]``, and both
SQLite writers deleted nothing, since ``channel_id = NULL`` never matches. So the
channel is required, with the same signature on every plugin, and a filter - which has
no channels - inherits a do-nothing reset from ``MetaFilter``.
"""

import inspect

import pytest

from poriscope.plugins.filters.BesselFilter import BesselFilter
from poriscope.plugins.filters.WaveletFilter import WaveletFilter
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
def test_reset_names_its_channel(base: type) -> None:
    """Every family takes ``reset_channel(channel: int)``, with no default to fall back on."""
    channel = inspect.signature(base.reset_channel).parameters["channel"]
    assert channel.default is inspect.Parameter.empty
    assert channel.annotation is int


def test_the_database_writer_helpers_name_their_channel() -> None:
    """The writer only ever builds and stamps a database for a channel it is writing."""
    for name in ("_initialize_database", "_write_experiment_metadata"):
        channel = inspect.signature(getattr(MetaDatabaseWriter, name)).parameters[
            "channel"
        ]
        assert channel.default is inspect.Parameter.empty, name
        assert channel.annotation is int, name


@pytest.mark.parametrize(
    "filter_cls", [BesselFilter, WaveletFilter], ids=lambda c: c.__name__
)
def test_a_filter_inherits_its_reset(filter_cls: type) -> None:
    """A filter has no channels to reset, so it need not write a reset of its own."""
    assert "reset_channel" not in MetaFilter.__abstractmethods__
    assert "reset_channel" not in vars(filter_cls)
