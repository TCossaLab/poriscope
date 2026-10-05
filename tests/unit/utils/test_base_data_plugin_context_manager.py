"""
A data plugin can be used as a context manager in a script.

``BaseDataPlugin`` implements ``__enter__`` and ``__exit__`` so that a script can write
``with Reader(settings) as reader: ...`` and have the plugin's resources released when
the block ends, however it ends. Nothing in the application uses this, which is exactly
why it needs a test of its own: a sweep for code with no callers found it, and only
knowing what it was for kept it.
"""

from unittest.mock import patch

import pytest

from poriscope.plugins.filters.BesselFilter import BesselFilter


def make_filter() -> BesselFilter:
    """
    A configured plugin that needs no file or parent plugin.

    :return: a BesselFilter ready to use
    :rtype: BesselFilter
    """
    plugin = BesselFilter()
    settings = plugin.get_empty_settings(standalone=True)
    settings["Cutoff"]["Value"] = 10000.0
    settings["Samplerate"]["Value"] = 250000.0
    plugin.apply_settings(settings)
    return plugin


def test_the_with_block_gets_the_plugin_itself():
    plugin = make_filter()
    with plugin as entered:
        assert entered is plugin


def test_leaving_the_block_closes_the_plugin():
    plugin = make_filter()
    with patch.object(plugin, "close_resources") as close:
        with plugin:
            close.assert_not_called()
        close.assert_called_once_with()


def test_an_error_in_the_block_still_closes_and_still_propagates():
    plugin = make_filter()
    with patch.object(plugin, "close_resources") as close:
        with pytest.raises(RuntimeError, match="inside the block"):
            with plugin:
                raise RuntimeError("inside the block")
        close.assert_called_once_with()
