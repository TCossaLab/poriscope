"""
The root conftest's thread guard: a test that leaves a ``QThread`` running fails, naming it.

Destroying a window whose worker thread is still running aborts the interpreter, and an
abort names no test. The guard records every thread a test starts and, before the windows
are destroyed, reports any still running after a short wait. These drive the two helpers
in ``tests/_thread_guard.py`` against real threads, recorded into a list of their own so
the autouse guard around each test is not involved.
"""

import threading
import time

import pytest
from PySide6.QtCore import QThread

from poriscope.utils.EventWorker import WorkerThread
from tests._thread_guard import record_started_threads, threads_still_running


class Blocked(QThread):
    """A thread that runs until its event is set."""

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()

    def run(self) -> None:
        """Wait to be released."""
        self.release.wait(30)


class BlockedWorker:
    """Stands in for a ``Worker``: ``WorkerThread.run`` calls ``run`` and nothing else."""

    def __init__(self) -> None:
        self.release = threading.Event()

    def run(self) -> None:
        """Wait to be released."""
        self.release.wait(30)


class Brief(QThread):
    """A thread that ends on its own shortly after it starts."""

    def run(self) -> None:
        """Sleep a moment."""
        time.sleep(0.2)


def test_a_thread_still_running_is_named():
    with pytest.MonkeyPatch.context() as local:
        started = record_started_threads(local)
        thread = Blocked()
        thread.start()
        try:
            assert threads_still_running(started, wait_ms=50) == ["Blocked"]
        finally:
            thread.release.set()
            thread.wait()


def test_a_worker_thread_is_named_by_its_key_and_channel():
    """Every tab's work runs in a WorkerThread, so its class alone would not say whose it is."""
    worker = BlockedWorker()
    with pytest.MonkeyPatch.context() as local:
        started = record_started_threads(local)
        thread = WorkerThread(worker, 3, "finder")  # type: ignore[arg-type]
        thread.start()
        try:
            assert threads_still_running(started, wait_ms=50) == [
                "WorkerThread finder/3"
            ]
        finally:
            worker.release.set()
            thread.wait()


def test_a_thread_that_ends_within_the_wait_is_not_reported():
    with pytest.MonkeyPatch.context() as local:
        started = record_started_threads(local)
        thread = Brief()
        thread.start()
        try:
            assert threads_still_running(started, wait_ms=5000) == []
        finally:
            thread.wait()  # a QThread destroyed while running aborts the interpreter


def test_a_finished_thread_is_not_reported():
    with pytest.MonkeyPatch.context() as local:
        started = record_started_threads(local)
        thread = Blocked()
        thread.start()
        thread.release.set()
        thread.wait()
        assert threads_still_running(started, wait_ms=0) == []


def test_a_thread_already_collected_is_not_reported():
    """The guard holds no thread alive; one the test dropped after it ended is simply gone."""
    with pytest.MonkeyPatch.context() as local:
        started = record_started_threads(local)
        thread = Blocked()
        thread.start()
        thread.release.set()
        thread.wait()
        del thread
        assert threads_still_running(started, wait_ms=0) == []


def _argnames(request, fixture: str) -> tuple:
    """
    The fixtures a root fixture asks for, as pytest resolved them for this test.

    :param request: pytest's request for the running test
    :type request: pytest.FixtureRequest
    :param fixture: the fixture's name
    :type fixture: str
    :return: the names it takes as arguments
    :rtype: tuple
    """
    (definition,) = request._fixturemanager.getfixturedefs(fixture, request.node)
    return definition.argnames


def test_the_root_guards_tear_down_replays_then_threads_then_windows(request):
    """
    A replay left running keeps its worker threads; stopped first, it is named as a replay.
    Threads are checked before any window goes, since destroying a window under a running
    thread aborts. Each guard asks for the next, so the order does not rest on their names.
    """
    assert "fail_a_test_that_leaves_a_thread_running" in _argnames(
        request, "stop_replays_after_each_test"
    )
    assert "destroy_windows_after_each_test" in _argnames(
        request, "fail_a_test_that_leaves_a_thread_running"
    )
    names = request.fixturenames
    assert (
        names.index("destroy_windows_after_each_test")
        < names.index("fail_a_test_that_leaves_a_thread_running")
        < names.index("stop_replays_after_each_test")
    )
