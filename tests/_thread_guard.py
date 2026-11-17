"""
Find the ``QThread`` s a test started and left running.

Destroying a window whose worker thread is still running aborts the interpreter, and an
abort names no test, so the root conftest checks for running threads before it destroys
the test's windows and fails the test that left one, naming it.

Qt keeps no list of the threads a process has started, so :func:`record_started_threads`
patches ``QThread.start`` for the length of a test to note each one. Every worker thread in
``poriscope`` is a ``WorkerThread``, started from Python, so that sees them all. Only weak
references are kept: holding a thread alive would change when it is destroyed.
"""

import weakref
from typing import Any, List

import pytest
from PySide6.QtCore import QThread

# The real start, kept before anything patches it.
_REAL_START = QThread.start


def record_started_threads(monkeypatch: pytest.MonkeyPatch) -> "List[weakref.ref]":
    """
    Patch ``QThread.start`` so every thread started from now on is noted.

    :param monkeypatch: undoes the patch when the test ends
    :type monkeypatch: pytest.MonkeyPatch
    :return: the list each started thread's weak reference is appended to
    :rtype: List[weakref.ref]
    """
    started: "List[weakref.ref]" = []

    def start(thread: QThread, *args: Any, **kwargs: Any) -> None:
        started.append(weakref.ref(thread))
        _REAL_START(thread, *args, **kwargs)

    monkeypatch.setattr(QThread, "start", start)
    return started


def threads_still_running(started: "List[weakref.ref]", wait_ms: int) -> List[str]:
    """
    Name every recorded thread still running after waiting up to ``wait_ms`` for each.

    :param started: what :func:`record_started_threads` returned
    :type started: List[weakref.ref]
    :param wait_ms: how long to wait for each running thread to end
    :type wait_ms: int
    :return: one name per thread still running, empty if none is
    :rtype: List[str]
    """
    running = []
    for ref in started:
        thread = ref()
        if thread is None:
            continue
        try:
            if thread.isRunning() and not thread.wait(wait_ms):
                running.append(_name(thread))
        except RuntimeError:  # the C++ thread is already deleted, so not running
            continue
    return running


def _name(thread: Any) -> str:
    """
    A thread's class, and for a ``WorkerThread`` its key and channel.

    Read by attribute rather than by ``isinstance``: importing ``WorkerThread`` here
    would import all of ``poriscope`` into every test run's root conftest.

    :param thread: a running thread
    :type thread: Any
    :return: e.g. ``"WorkerThread finder/3"``
    :rtype: str
    """
    name = type(thread).__name__
    key, channel = getattr(thread, "key", None), getattr(thread, "channel", None)
    if key is not None and channel is not None:
        name += f" {key}/{channel}"
    return name
