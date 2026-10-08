"""
How ``MetaModel`` stages and runs a plugin's generators on worker threads.

A request names a plugin key and a channel. A request for a key with nothing staged -
every channel was skipped before staging - does nothing. A request for a (key, channel)
whose worker is still running is refused: the running one carries on, the new generator
is closed without having started, and the status panel says the request was ignored
rather than dropping it silently.
"""

import inspect
import threading
import time
from typing import Callable, Generator, Iterator, List, Optional, Tuple

import pytest
from PySide6.QtWidgets import QApplication

from poriscope.utils.MetaModel import MetaModel


class Model(MetaModel):
    """The smallest concrete ``MetaModel``."""

    def _init(self) -> None:
        pass


def gated(
    gate: threading.Event, started: List[str], tag: str
) -> Generator[float, Optional[bool], None]:
    """
    A plugin generator that reports it started, then waits to be let go.

    :param gate: set to let the generator finish
    :type gate: threading.Event
    :param started: where it records that it started
    :type started: List[str]
    :param tag: what it records
    :type tag: str
    :return: progress
    :rtype: Generator[float, Optional[bool], None]
    """
    started.append(tag)
    gate.wait(5)
    yield 50.0
    yield 100.0


def pump(app: QApplication, until: Callable[[], bool], timeout: float = 5.0) -> None:
    """
    Run the event loop until a condition holds.

    :param app: the Qt application
    :type app: QApplication
    :param until: the condition
    :type until: Callable[[], bool]
    :param timeout: seconds to wait before failing
    :type timeout: float
    """
    deadline = time.monotonic() + timeout
    while not until():
        assert time.monotonic() < deadline, "timed out"
        app.processEvents()
        time.sleep(0.01)


@pytest.fixture
def model(qapp: QApplication) -> Iterator[Tuple[Model, List[str]]]:
    """
    A model, and the status-panel messages it emits.

    :param qapp: the Qt application
    :type qapp: QApplication
    :return: the model and its messages
    :rtype: Iterator[Tuple[Model, List[str]]]
    """
    instance = Model()
    messages: List[str] = []
    instance.add_text_to_display.connect(lambda text, source: messages.append(text))
    yield instance, messages


def test_a_key_with_nothing_staged_runs_nothing(model: Tuple[Model, List[str]]) -> None:
    instance, messages = model

    instance.run_generators("finder")

    assert instance.threads == {}
    assert messages == []


def test_a_second_request_while_one_runs_is_reported_and_closed(
    qapp: QApplication, model: Tuple[Model, List[str]]
) -> None:
    instance, messages = model
    gate, started = threading.Event(), []
    first = gated(gate, started, "first")
    instance.set_generator(first, 0, "finder", "MetaEventFinder")
    instance.run_generators("finder")
    pump(qapp, lambda: started == ["first"])

    second = gated(gate, started, "second")
    instance.set_generator(second, 0, "finder", "MetaEventFinder")
    instance.run_generators("finder")

    try:
        assert inspect.getgeneratorstate(second) == inspect.GEN_CLOSED
        assert instance.generators["finder"][0] is first
        assert messages == [
            "finder is already running on channel 0; this request was ignored"
        ]
    finally:
        gate.set()
        pump(qapp, lambda: not instance.generators["finder"])
    assert started == ["first"]
