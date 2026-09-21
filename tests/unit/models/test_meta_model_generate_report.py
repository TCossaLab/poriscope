"""
``MetaModel.generate_report`` - asking a plugin for its channel status.

Step 5e.2 moved this off the global signal bus. It now calls the plugin through
``MetaModel.call`` and emits its own ``add_text_to_display``, which
``MetaController`` already relays onward.

The end-to-end outcome - the status reaching the display panel - is pinned by
``tests/integration/flows/test_bus_outcomes_no_gui.py``, deliberately at that
level so it survives the bus being deleted. What is pinned *here* is the part
that is new rather than moved: ``call`` reports failure by **raising**, where
the bus logged and swallowed several hops away. ``generate_report`` runs as a Qt
slot over a queued connection, so it must not raise, and the swallow now lives
at the call site.
"""

import logging
from typing import override

import pytest

from poriscope.utils.MetaModel import MetaModel


class _ConcreteModel(MetaModel):
    """A minimal concrete MetaModel, since the base is abstract."""

    @override
    def _init(self) -> None:
        pass


@pytest.fixture
def model():
    """
    A concrete MetaModel with one plugin registered under "reader".

    :return: the model under test
    :rtype: _ConcreteModel
    """
    m = _ConcreteModel()
    m.reporter_metaclasses["reader"] = "MetaReader"
    return m


class _Plugin:
    """A plugin that reports a status, or refuses to."""

    def __init__(self, blow_up: bool = False) -> None:
        """
        Build a plugin that either answers or raises.

        :param blow_up: whether ``report_channel_status`` should raise
        :type blow_up: bool
        """
        self.blow_up = blow_up
        self.asked_for: list = []

    def report_channel_status(self, channel: int) -> str:
        """
        Report a status for one channel.

        :param channel: the channel being asked about
        :type channel: int
        :return: the status text
        :rtype: str
        :raises RuntimeError: when the plugin was built to fail
        """
        self.asked_for.append(channel)
        if self.blow_up:
            raise RuntimeError("the reader is not happy")
        return f"channel {channel} is fine"


def test_the_status_is_emitted_against_the_plugin_key(model):
    """
    The plugin is asked about the channel, and its answer goes out keyed by plugin.

    The key is the source the display panel attributes the line to, which is why
    it is the second argument rather than the metaclass.
    """
    plugin = _Plugin()
    model.set_plugin_instances({"MetaReader": {"reader": plugin}})
    emitted = []
    model.add_text_to_display.connect(lambda text, source: emitted.append((text, source)))

    model.generate_report(2, "reader")

    assert plugin.asked_for == [2]
    assert emitted == [("channel 2 is fine", "reader")]


def test_a_plugin_that_raises_is_reported_and_nothing_is_emitted(model, caplog):
    """
    The new swallow. ``call`` raises; this runs as a Qt slot and must not.

    Nothing is emitted, because there is no status to show - putting the
    exception text on the display panel would present a fault as a reading.
    """
    plugin = _Plugin(blow_up=True)
    model.set_plugin_instances({"MetaReader": {"reader": plugin}})
    emitted = []
    model.add_text_to_display.connect(lambda text, source: emitted.append((text, source)))

    with caplog.at_level(logging.ERROR):
        model.generate_report(2, "reader")

    assert emitted == []
    assert "the reader is not happy" in caplog.text
    assert "MetaReader/reader" in caplog.text


def test_an_unregistered_plugin_is_reported_rather_than_raised(model, caplog):
    """
    A plugin deleted while its worker ran resolves to nothing, and ``call`` raises
    ``KeyError``. The slot still must not.
    """
    model.set_plugin_instances({})
    emitted = []
    model.add_text_to_display.connect(lambda text, source: emitted.append((text, source)))

    with caplog.at_level(logging.ERROR):
        model.generate_report(0, "reader")

    assert emitted == []
    assert "Unable to report the status" in caplog.text
