"""
Destroy every top-level window a test leaves behind.

The whole test session shares one ``QApplication``, so a window one test leaves alive
is paid for by every test after it. ``close()`` only hides a window; it stays alive,
with every widget in it, and grows the heap every later garbage collection walks.
The root conftest calls this after every test and fails the test if anything survives.
"""

from typing import List

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication


def destroy_leftover_windows() -> List[str]:
    """
    Close and delete every top-level widget, then report any that are still alive.

    Events the test left queued are delivered first, while their receivers still
    exist: a worker's queued "finished" reaching a deleted view raises "Internal C++
    object already deleted". ``deleteLater()`` only posts a deferred-delete event,
    which ``processEvents()`` does not dispatch, so those are sent explicitly.

    :return: the class names of the windows still alive afterwards
    :rtype: List[str]
    """
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return []
    app.processEvents()
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return [type(widget).__name__ for widget in QApplication.topLevelWidgets()]
