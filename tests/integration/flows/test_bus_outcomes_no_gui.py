"""
The three things the global signal bus is still used for, pinned by their outcome.

These were the net for removing the bus, and they are written
deliberately against **what the application does**, not against which signal
carries it:

- a tab asking a plugin for its channel status puts that status on the display
- a tab's edit request reaches ``DataPluginController.edit_plugin_settings``
- a tab's delete request reaches ``DataPluginController.delete_plugin``

Every one of those sentences stays true after the bus is gone, so these tests
passed **unchanged** while ``generate_report`` moved onto ``self.call``, the
string-dispatched ``data_plugin_controller_signal`` became typed
``Signal(str, str)`` signals, and the machinery was deleted. Passing them with the
bus deleted is the evidence that the removal preserved behaviour.

Unit tests of the three call sites were considered and rejected for this job:
they would assert which signal fired with what payload, the removal changed both,
and a test rewritten alongside the code it guards proves nothing about the change.

``handle_edit_triggered`` and ``handle_delete_triggered`` sit at 25% line
coverage and no test named either before this file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Tuple

import pytest

from tests.integration.flows._triad import Triad, build_triad

READER = "reader"


@pytest.fixture
def triad(qapp: Any, tmp_path: Path) -> Any:
    """
    A Raw Data tab wired into a real application shell.

    ``qapp`` is not decoration: ``MainView`` is a real widget, and building one
    without a ``QApplication`` does not raise - it takes the interpreter down
    with a native fault, which pytest reports as no output at all.

    :param qapp: pytest-qt's application fixture; MainView is a real widget
    :type qapp: Any
    :param tmp_path: scratch directory used as the app's data root
    :type tmp_path: Path
    :return: the assembled triad, closed on teardown
    :rtype: Any
    """
    built = build_triad("RawDataController", tmp_path)
    yield built
    built.close()


def display_calls(triad: Triad, monkeypatch: pytest.MonkeyPatch) -> List[Tuple]:
    """
    Record everything that reaches the main window's display panel.

    The panel is the far end of the chain and the only part of it the user sees,
    which is why the report test asserts here rather than on any signal along the
    way.

    :param triad: the assembled application
    :type triad: Triad
    :param monkeypatch: pytest's monkeypatch fixture
    :type monkeypatch: pytest.MonkeyPatch
    :return: a list that accumulates (text, source) as they arrive
    :rtype: List[Tuple]
    """
    seen: List[Tuple] = []
    monkeypatch.setattr(
        triad.view,
        "add_text_to_display",
        lambda text, source: seen.append((text, source)),
    )
    return seen


class _StubReader:
    """
    A minimal stand-in for a reader, carrying only what these flows ask of it.

    A real reader wants a data file; none of these three paths reads one, so
    requiring a file would be testing the fixture rather than the flow.
    """

    def __init__(self) -> None:
        """Record the channel every status request asks about."""
        self.asked_for: List[int] = []

    def report_channel_status(self, channel: int, init: bool = False) -> str:
        """
        Report a fixed status, and remember which channel was asked about.

        :param channel: the channel being asked about
        :type channel: int
        :param init: whether this is the plugin's first report
        :type init: bool
        :return: the status text
        :rtype: str
        """
        self.asked_for.append(channel)
        return f"stub status for channel {channel}"

    def get_key(self) -> str:
        """
        Give the plugin's key.

        :return: the key
        :rtype: str
        """
        return READER

    def close_resources(self, channel: int = None) -> None:
        """
        Release nothing, because this stub holds nothing.

        Required rather than optional: the triad's teardown runs
        ``DataPluginModel.handle_exit``, which calls this on every registered
        plugin, so a stub without it fails the test in teardown having already
        passed.

        :param channel: the channel to close, or None for all of them
        :type channel: int
        """
        return None


def test_a_channel_status_request_reaches_the_display(triad, monkeypatch):
    """
    The report a tab asks a plugin for ends up on the main window's display panel.

    This is the whole of what ``MetaModel.generate_report`` achieves. It moved off
    the bus and onto ``self.call``, and the sentence above stayed true.
    """
    seen = display_calls(triad, monkeypatch)
    reader = _StubReader()
    # Registered through the triad rather than pushed into a registry by hand.
    # There are two of them: the bus resolves against DataPluginModel.plugins,
    # while MetaModel.call resolves against the tab's own _plugin_instances,
    # which MainController fills only when a registration is announced. Reaching
    # into one of them directly would pin this test to whichever mechanism is
    # current, which is exactly what it exists not to do.
    triad.register(reader, "MetaReader", READER)
    triad.tab_controller.model.reporter_metaclasses[READER] = "MetaReader"

    triad.tab_controller.model.generate_report(3, READER)

    assert reader.asked_for == [3], "the plugin was not asked for its channel status"
    assert any(
        "stub status for channel 3" in str(text) for text, _ in seen
    ), f"the status never reached the display; saw {seen}"


def test_an_edit_request_reaches_the_data_plugin_controller(triad, monkeypatch):
    """
    A tab's edit request arrives at ``DataPluginController.edit_plugin_settings``.

    The string-dispatched signal behind this was replaced with a typed
    ``Signal(str, str)`` connected to the same method, so the assertion was
    unaffected.
    """
    called: List[Tuple] = []
    monkeypatch.setattr(
        triad.controller.data_plugin_controller,
        "edit_plugin_settings",
        lambda metaclass, key: called.append((metaclass, key)),
    )

    triad.tab_view.handle_edit_triggered("MetaReader", READER)

    assert called == [("MetaReader", READER)]


def test_a_delete_request_reaches_the_data_plugin_controller(triad, monkeypatch):
    """
    A tab's delete request arrives at ``DataPluginController.delete_plugin``.

    The other half of the typed-signal replacement, and the same reasoning.
    """
    called: List[Tuple] = []
    monkeypatch.setattr(
        triad.controller.data_plugin_controller,
        "delete_plugin",
        lambda metaclass, key: called.append((metaclass, key)),
    )

    triad.tab_view.handle_delete_triggered("MetaReader", READER)

    assert called == [("MetaReader", READER)]
