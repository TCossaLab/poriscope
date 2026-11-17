"""
Stop every replay a test leaves running.

A running replay takes the errors that would otherwise open a dialog, so its question can
show them (``poriscope.utils.ReplayGuard``). The replays that do so are held in one
process-wide set, so a replay one test leaves running swallows the dialogs of every test
after it on the same worker. The root conftest calls this after every test and fails the
test if it left one running.
"""

from typing import List

import shiboken6

from poriscope.utils import ReplayGuard


def stop_leftover_replays() -> List[str]:
    """
    Stop every replay still taking errors, as quitting does, and name each one.

    A replay whose tab has been deleted takes no errors and cannot be stopped through its
    tab; it is only let go.

    :return: the class name of each replay's tab, for every replay that was still running
    :rtype: List[str]
    """
    left: List[str] = []
    for collector in list(ReplayGuard._error_collectors):
        tab = getattr(collector, "_controller", None)
        if getattr(collector, "running", False) and shiboken6.isValid(tab):
            left.append(type(tab).__name__)
            collector.stop(quitting=True)
        ReplayGuard.stop_collecting_errors(collector)
    return left
