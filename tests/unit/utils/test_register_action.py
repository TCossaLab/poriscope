"""
Tests for ``poriscope.utils.LogDecorator.register_action``.

The decorator gives a method a declared name and records each call as
``{"action": name, "args": ..., "kwargs": ...}`` through ``self.record_action``, and
carries a declaration of what a restored session keeps of the action, checked when the
class is defined. These tests run it against plain objects.
"""

import logging
from typing import Any, Dict, List

import pytest

from poriscope.utils.LogDecorator import (
    ACTION_DECLARATION_ATTR,
    ACTION_NAME_ATTR,
    RESET_ACTION,
    ActionDeclaration,
    register_action,
)


class _Recorder:
    """A stand-in tab object: just the hook the decorator calls."""

    logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def record_action(self, entry: Dict[str, Any]) -> None:
        self.entries.append(entry)

    @register_action("draw", kind="view", figure="plot")
    def draw(self, number: int, scale: float = 1.0) -> int:
        return number * 2

    @register_action("outer", kind="view", figure="plot")
    def outer(self) -> None:
        self.inner()

    @register_action("inner", kind="view", figure="plot")
    def inner(self) -> None:
        pass


def test_a_decorated_method_records_one_entry_under_its_declared_name() -> None:
    tab = _Recorder()

    result = tab.draw(3, scale=2.0)

    assert result == 6
    assert tab.entries == [
        {"action": "draw", "args": (), "kwargs": {"number": 3, "scale": 2.0}}
    ]


def test_every_argument_is_saved_under_its_name_however_it_was_passed() -> None:
    """A saved file says what each value is, so a reader does not need the code to tell."""
    tab = _Recorder()

    tab.draw(3, 2.0)
    tab.draw(number=3, scale=2.0)
    tab.draw(3, scale=2.0)

    assert tab.entries[0] == tab.entries[1] == tab.entries[2]
    assert tab.entries[0]["kwargs"] == {"number": 3, "scale": 2.0}


def test_a_default_the_caller_left_out_is_saved_too() -> None:
    tab = _Recorder()

    tab.draw(3)

    assert tab.entries[0]["kwargs"] == {"number": 3, "scale": 1.0}


def test_a_named_entry_replays_and_records_the_same_entry() -> None:
    tab = _Recorder()
    tab.draw(3, scale=2.0)
    entry = tab.entries[0]

    tab.draw(*entry["args"], **entry["kwargs"])

    assert tab.entries[1] == entry


def test_an_entry_saved_with_positional_values_still_replays() -> None:
    """Files saved before arguments were named hold an args list; replay accepts it."""
    tab = _Recorder()
    old_entry = {"action": "draw", "args": [3], "kwargs": {"scale": 2.0}}

    result = tab.draw(*old_entry["args"], **old_entry["kwargs"])

    assert result == 6
    assert tab.entries == [
        {"action": "draw", "args": (), "kwargs": {"number": 3, "scale": 2.0}}
    ]


def test_extra_keyword_arguments_are_saved_flat_so_they_replay() -> None:
    class _Open(_Recorder):
        @register_action("open", kind="view", figure="plot")
        def open(self, name: str, **options: Any) -> None:
            pass

    tab = _Open()

    tab.open("a", colour="red")

    assert tab.entries[0]["kwargs"] == {"name": "a", "colour": "red"}
    tab.open(*tab.entries[0]["args"], **tab.entries[0]["kwargs"])
    assert tab.entries[1] == tab.entries[0]


def test_a_method_whose_values_cannot_all_be_named_is_saved_as_called() -> None:
    """``*args`` and positional-only parameters have no name to replay by."""

    class _Varied(_Recorder):
        @register_action("many", kind="view", figure="plot")
        def many(self, *values: int) -> None:
            pass

        @register_action("only", kind="view", figure="plot")
        def only(self, value: int, /, scale: float = 1.0) -> None:
            pass

    tab = _Varied()

    tab.many(1, 2)
    tab.only(4, scale=2.0)

    assert tab.entries == [
        {"action": "many", "args": (1, 2), "kwargs": {}},
        {"action": "only", "args": (4,), "kwargs": {"scale": 2.0}},
    ]


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

        @register_action("draw", kind="view", figure="plot")
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

    @register_action("acts", kind="view", figure="plot", skip_on_false=True)
    def acts(self, outcome: Any) -> Any:
        return outcome

    @register_action("plain", kind="view", figure="plot")
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


def test_the_declaration_is_stored_on_the_method_and_not_in_the_entry() -> None:
    class _Tab(_Recorder):
        @register_action(
            "find", kind="result", key=("finder", "channel"), skip_on_false=True
        )
        def find(self, finder: str, channel: int, ranges: List[Any]) -> bool:
            return True

    tab = _Tab()
    tab.find("Finder A", 1, [])

    assert getattr(_Tab.find, ACTION_DECLARATION_ATTR) == ActionDeclaration(
        "find", "result", key=("finder", "channel"), skip_on_false=True
    )
    assert set(tab.entries[0]) == {"action", "args", "kwargs"}


def test_the_declaration_says_whether_false_means_the_call_did_nothing() -> None:
    """A replay reads it: ``False`` from such an action means it refused or drew nothing."""

    class _Tab(_Recorder):
        @register_action("plain", kind="view", figure="plot")
        def plain(self) -> bool:
            return False

        @register_action("acts", kind="view", figure="plot", skip_on_false=True)
        def acts(self) -> bool:
            return False

    assert getattr(_Tab.plain, ACTION_DECLARATION_ATTR).skip_on_false is False
    assert getattr(_Tab.acts, ACTION_DECLARATION_ATTR).skip_on_false is True


def test_the_declaration_says_which_parameters_name_a_plugin() -> None:
    """Deleting or renaming a plugin finds the entries that name it through these."""

    class _Tab(_Recorder):
        @register_action(
            "trace", kind="view", figure="plot", plugin_args=("reader", "data_filter")
        )
        def trace(self, reader: str, channel: int, data_filter: str) -> None:
            pass

        @register_action(RESET_ACTION, kind="reset", figure="plot")
        def reset(self) -> None:
            pass

    assert getattr(_Tab.trace, ACTION_DECLARATION_ATTR).plugin_args == (
        "reader",
        "data_filter",
    )
    assert getattr(_Tab.reset, ACTION_DECLARATION_ATTR).plugin_args == ()


def test_a_figure_can_be_named_by_a_parameter() -> None:
    class _Tab(_Recorder):
        @register_action(RESET_ACTION, kind="reset", figure_from="mode")
        def reset(self, mode: str = "individual") -> None:
            pass

    declaration = getattr(_Tab.reset, ACTION_DECLARATION_ATTR)
    assert (declaration.figure, declaration.figure_from) == ("", "mode")


def _declare(**fields: Any) -> None:
    """Decorate a method with these fields; a refused declaration raises here."""

    class _Tab:
        @register_action("act", **fields)
        def act(self, plugin: str, channel: int, mode: str) -> None:
            pass


@pytest.mark.parametrize(
    "fields, message",
    [
        ({"kind": "chain", "figure": "plot"}, "kind must be one of"),
        ({"kind": "result"}, "names its plugin parameter, then its channel"),
        (
            {"kind": "result", "key": ("plugin", "channel", "mode")},
            "names its plugin parameter, then its channel",
        ),
        (
            {"kind": "result", "key": ("plugin", "channel"), "figure": "plot"},
            "draws on no figure",
        ),
        ({"kind": "view", "figure": "plot", "key": ("plugin",)}, "only a result"),
        ({"kind": "view"}, "exactly one of figure and figure_from"),
        (
            {"kind": "view", "figure": "plot", "figure_from": "mode"},
            "exactly one of figure and figure_from",
        ),
        (
            {"kind": "additive", "figure": "plot", "depends_on": ("plugin",)},
            "only a view depends on a result",
        ),
        (
            {"kind": "view", "figure": "plot", "depends_on": ("plugin",)},
            "depends on a result's plugin parameter, then its channel",
        ),
        (
            {
                "kind": "view",
                "figure": "plot",
                "depends_on": ("plugin", "channel", "mode"),
            },
            "depends on a result's plugin parameter, then its channel",
        ),
        (
            {"kind": "result", "key": ("finder", "channel")},
            "finder is not a parameter",
        ),
        ({"kind": "reset", "figure_from": "axis"}, "axis is not a parameter"),
        (
            {"kind": "view", "figure": "plot", "depends_on": ("plugin", "chan")},
            "chan is not a parameter",
        ),
        (
            {"kind": "view", "figure": "plot", "plugin_args": ("plugin", "loader")},
            "loader is not a parameter",
        ),
    ],
)
def test_a_declaration_a_restore_could_not_act_on_fails_when_the_class_is_defined(
    fields: Dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message) as raised:
        _declare(**fields)
    assert "@register_action('act')" in str(raised.value)


def test_a_declaration_without_a_kind_is_refused() -> None:
    with pytest.raises(TypeError, match="kind"):
        register_action("act")  # type: ignore[call-arg]
