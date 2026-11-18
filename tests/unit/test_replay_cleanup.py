"""
The root conftest's replay cleanup: a replay a test leaves running is stopped and named.

A running replay takes the errors a dialog would show, from a set the whole process
shares, so one left running swallows the dialogs of every test after it on the same
worker. ``tests/_replay_cleanup.py`` stops each one as quitting does and names its tab,
and the root conftest fails the test that left it. These drive the helper against
stand-in replays registered in the real set, so the autouse cleanup around each test is
not involved: every case leaves the set as it found it.
"""

from typing import List

import shiboken6
from PySide6.QtCore import QObject

from poriscope.utils import ReplayGuard
from tests._replay_cleanup import stop_leftover_replays


class TabStandIn(QObject):
    """The tab a replay belongs to: named in the report, and may have been deleted."""


class ReplayStandIn:
    """
    Stands in for a ``ReplaySequence``: what the cleanup reads of one, and no more.

    It collects errors, belongs to a tab, says whether it is running, and stops when
    told to - recording how, since quitting is the only way the cleanup may stop it.
    """

    def __init__(self, tab: QObject, running: bool) -> None:
        """
        :param tab: the tab the replay belongs to
        :type tab: QObject
        :param running: whether the replay is still running
        :type running: bool
        """
        self._controller = tab
        self.running = running
        self.stopped_with: List[bool] = []
        ReplayGuard.collect_errors(self)

    def take_error(self, text: str) -> bool:
        """
        :param text: the error's text
        :type text: str
        :return: whether the replay took the error
        :rtype: bool
        """
        return self.running

    def stop(self, quitting: bool = False) -> None:
        """
        :param quitting: whether the app is quitting
        :type quitting: bool
        """
        self.stopped_with.append(quitting)
        self.running = False


def test_a_replay_left_running_is_stopped_as_quitting_does_and_named(qapp):
    tab = TabStandIn()
    replay = ReplayStandIn(tab, running=True)

    assert stop_leftover_replays() == ["TabStandIn"]

    assert replay.stopped_with == [True]
    assert replay not in ReplayGuard._error_collectors


def test_a_replay_that_has_ended_is_let_go_without_a_word(qapp):
    tab = TabStandIn()
    replay = ReplayStandIn(tab, running=False)

    assert stop_leftover_replays() == []

    assert replay.stopped_with == []
    assert replay not in ReplayGuard._error_collectors


def test_a_replay_whose_tab_is_gone_is_let_go_and_not_stopped_through_it(qapp):
    """Stopping goes through the tab, and a deleted tab cannot be asked anything."""
    tab = TabStandIn()
    replay = ReplayStandIn(tab, running=True)
    shiboken6.delete(tab)

    assert stop_leftover_replays() == []

    assert replay.stopped_with == []
    assert replay not in ReplayGuard._error_collectors


def test_every_replay_left_running_is_named(qapp):
    first, second = TabStandIn(), TabStandIn()
    replays = [ReplayStandIn(first, running=True), ReplayStandIn(second, running=True)]

    assert stop_leftover_replays() == ["TabStandIn", "TabStandIn"]

    assert [replay.stopped_with for replay in replays] == [[True], [True]]
