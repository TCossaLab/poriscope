"""
Tests for ``poriscope.utils.LogDecorator.register_action``.

The decorator gives a method a declared name and records each call as
``{"action": name, "args": ..., "kwargs": ...}`` through ``self.record_action``. It
must work the same on a Controller method and, during the transition, on a View method,
which is why these tests run it against plain objects and against the real
``MetaController`` and ``MetaView`` hooks.
"""

import logging
from typing import Any, Dict, List

import pytest

from poriscope.utils.LogDecorator import ACTION_NAME_ATTR, RESET_ACTION, register_action


class _Recorder:
    """A stand-in tab object: just the hook the decorator calls."""

    logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def record_action(self, entry: Dict[str, Any]) -> None:
        self.entries.append(entry)

    @register_action("draw")
    def draw(self, number: int, scale: float = 1.0) -> int:
        return number * 2

    @register_action("outer")
    def outer(self) -> None:
        self.inner()

    @register_action("inner")
    def inner(self) -> None:
        pass


def test_a_decorated_method_records_one_entry_under_its_declared_name() -> None:
    tab = _Recorder()

    result = tab.draw(3, scale=2.0)

    assert result == 6
    assert tab.entries == [{"action": "draw", "args": (3,), "kwargs": {"scale": 2.0}}]


def test_the_entry_does_not_carry_the_python_method_name() -> None:
    tab = _Recorder()

    tab.draw(1)

    assert "function" not in tab.entries[0]


def test_nested_recording_puts_the_inner_entry_first() -> None:
    """
    The entry is recorded after the body returns, so an action called inside another is
    recorded before it. Protein's ensemble plot calls its reset first and relies on that.
    """
    tab = _Recorder()

    tab.outer()

    assert [entry["action"] for entry in tab.entries] == ["inner", "outer"]


def test_the_declared_name_is_findable_and_the_method_keeps_its_own_name() -> None:
    assert getattr(_Recorder.draw, ACTION_NAME_ATTR) == "draw"
    assert _Recorder.draw.__name__ == "draw"


def test_the_reset_name_is_one_shared_constant() -> None:
    assert RESET_ACTION == "reset"


def test_a_recording_failure_is_logged_and_does_not_break_the_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Broken(_Recorder):
        def record_action(self, entry: Dict[str, Any]) -> None:
            raise RuntimeError("history is gone")

    with caplog.at_level(logging.INFO):
        result = _Broken().draw(2)

    assert result == 4
    assert "Unable to log tab action" in caplog.text


def test_an_object_with_no_record_action_still_runs_the_method() -> None:
    class _Bare:
        logger = logging.getLogger(__name__)

        @register_action("draw")
        def draw(self) -> str:
            return "drawn"

    assert _Bare().draw() == "drawn"


class _Skipper:
    """A tab object whose action declares that returning False means it did nothing."""

    logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def record_action(self, entry: Dict[str, Any]) -> None:
        self.entries.append(entry)

    @register_action("acts", skip_on_false=True)
    def acts(self, outcome: Any) -> Any:
        return outcome

    @register_action("plain")
    def plain(self, outcome: Any) -> Any:
        return outcome


def test_a_method_that_returns_false_is_not_recorded_when_it_opts_in() -> None:
    tab = _Skipper()

    result = tab.acts(False)

    assert result is False
    assert tab.entries == []


@pytest.mark.parametrize("outcome", [True, None, 0, "done"])
def test_only_a_literal_false_means_it_did_nothing(outcome: Any) -> None:
    tab = _Skipper()

    tab.acts(outcome)

    assert [entry["action"] for entry in tab.entries] == ["acts"]


def test_without_the_opt_in_a_false_result_is_recorded_as_before() -> None:
    tab = _Skipper()

    tab.plain(False)

    assert [entry["action"] for entry in tab.entries] == ["plain"]
