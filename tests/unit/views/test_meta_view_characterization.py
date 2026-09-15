"""
Characterization tests for the data methods on the analysis tabs' view bases.

These files had no dedicated tests, and the methods pinned here are the ones the
2.0.0 refactor moves down to the model layer - so they are pinned before they move
rather than after, and the same assertions run against the destination.

The five event-index range helpers live on ``MetaEventTabView``: their only callers
are ``EventAnalysisView`` and ``RawDataView``, so sitting on the base every tab
inherits was leakage. They do have tests in ``test_protein_view.py``'s
``TestRangeHelpers``, but weak ones - the shift tests assert an ``or``-chain of three
alternatives, and one asserts ``>= 0`` under a comment claiming a clamp the
implementation does not have. ``_shift_ranges`` **reflects** a multi-element range
rather than translating it, which is non-obvious and was effectively unpinned.

The logscale filter was pinned here too, and has moved on: it lives on ``MetaModel``
now and is covered by ``tests/unit/models/test_meta_model_logscale.py``, which
carries these assertions and two more.

Values are asserted explicitly rather than through ``pytest-regressions``: these
return short tuples, lists and strings, and a golden file for a two-element tuple
is less legible than the literal.
"""

from typing import Dict, List

import pytest
from PySide6.QtWidgets import QBoxLayout

from poriscope.utils.MetaEventTabView import MetaEventTabView
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization


class _ConcreteView(MetaEventTabView):
    """
    A minimal concrete view, so the bases' own methods can be exercised.

    It extends ``MetaEventTabView`` rather than ``MetaView`` because Step 3e moved the
    range helpers down to it. Only three abstract hooks need satisfying here:
    ``MetaEventTabView`` already implements ``_reset_actions`` and
    ``notify_plugin_state_changed`` concretely for both event tabs.
    """

    def _init(self) -> None:
        """Satisfy the abstract hook; the tests need no state from it."""

    def _set_control_area(self, layout: QBoxLayout) -> None:
        """Satisfy the abstract hook; no controls widget is built."""

    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """Satisfy the abstract hook; no comboboxes to populate."""


@pytest.fixture
def view() -> _ConcreteView:
    """
    Build the view without constructing any Qt widget.

    ``__new__`` skips ``QWidget.__init__``, so there is no C++ object behind the
    instance and emitting a class-level Signal would raise "Signal source has been
    deleted"; ``shadow_signals`` swaps each for a stand-in. ``logger`` is a class
    attribute and is deliberately left alone - mocking it blinds ``caplog``.

    :return: a MetaEventTabView subclass instance with its signals shadowed
    :rtype: _ConcreteView
    """
    instance = _ConcreteView.__new__(_ConcreteView)
    shadow_signals(instance, _ConcreteView)
    return instance


# ===========================================================================
# The five event-index range helpers
# ===========================================================================


class TestParseEventIndices:
    """Parsing a range string into bounds."""

    def test_mixed_ranges_and_singletons(self, view: _ConcreteView) -> None:
        """A singleton becomes a degenerate range."""
        assert view._parse_event_indices("7-10,12", allow_floats=False) == [
            (7, 10),
            (12, 12),
        ]

    def test_floats_are_accepted_when_allowed(self, view: _ConcreteView) -> None:
        """With floats permitted, fractional bounds survive."""
        assert view._parse_event_indices("1.5-4.5,6", allow_floats=True) == [
            (1.5, 4.5),
            (6.0, 6.0),
        ]

    def test_a_float_is_rejected_when_floats_are_not_allowed(
        self, view: _ConcreteView
    ) -> None:
        """``int('1.5')`` raises, so the segment is warned about and dropped."""
        assert view._parse_event_indices("1.5,3", allow_floats=False) == [(3, 3)]

    def test_a_two_hyphen_segment_is_dropped(self, view: _ConcreteView) -> None:
        """
        ``split('-')`` is unbounded, so three parts fail to unpack into two names.

        Recorded rather than fixed: the segment is logged and skipped.
        """
        assert view._parse_event_indices("1-2-3,5", allow_floats=False) == [(5, 5)]

    def test_a_negative_bound_is_dropped_because_of_the_hyphen(
        self, view: _ConcreteView
    ) -> None:
        """``'-5'`` splits into ``['', '5']`` and the empty string fails to cast."""
        assert view._parse_event_indices("-5,7", allow_floats=False) == [(7, 7)]

    def test_whitespace_and_empty_segments_are_tolerated(
        self, view: _ConcreteView
    ) -> None:
        """Trailing commas and spaces are normal user input, not errors."""
        assert view._parse_event_indices(" 3 , , 5 ", allow_floats=False) == [
            (3, 3),
            (5, 5),
        ]


class TestShiftRanges:
    """
    ``_shift_ranges`` reflects a multi-element range; it does not translate it.

    This is the least obvious behaviour in the group and the reason these tests
    exist: the assertions it replaces in ``test_protein_view.py`` are an
    ``or``-chain of three alternatives that would pass under translation too.
    """

    def test_a_singleton_translates_right(self, view: _ConcreteView) -> None:
        """A single index simply moves by the offset."""
        assert view._shift_ranges([(4, 4)], "right", 1) == [(5, 5)]

    def test_a_singleton_translates_left(self, view: _ConcreteView) -> None:
        """And back the other way."""
        assert view._shift_ranges([(4, 4)], "left", 1) == [(3, 3)]

    def test_a_range_reflects_past_its_end_when_shifted_right(
        self, view: _ConcreteView
    ) -> None:
        """
        ``(2, 5)`` becomes ``(end+offset, 2*end-start+offset)`` = ``(6, 9)``.

        A translation would have given ``(3, 6)``. The range keeps its width and
        lands entirely beyond where it was, which is what "next page of events"
        means here.
        """
        assert view._shift_ranges([(2, 5)], "right", 1) == [(6, 9)]

    def test_a_range_reflects_past_its_start_when_shifted_left(
        self, view: _ConcreteView
    ) -> None:
        """``(2*start-end)-offset`` to ``start-offset`` = ``(-2, 1)`` for ``(2, 5)``."""
        assert view._shift_ranges([(2, 5)], "left", 1) == [(-2, 1)]

    def test_shifting_left_is_not_clamped(self, view: _ConcreteView) -> None:
        """
        Negative bounds are produced and not corrected.

        The test this replaces asserted ``>= 0`` beneath a comment claiming a clamp
        to 1; there is no clamp anywhere in the implementation.
        """
        assert view._shift_ranges([(1, 2)], "left", 5) == [(-5, -4)]

    def test_every_range_in_the_list_is_shifted(self, view: _ConcreteView) -> None:
        """The helper maps over the whole list."""
        assert view._shift_ranges([(1, 1), (4, 6)], "right", 2) == [(3, 3), (8, 10)]


class TestMergeRanges:
    """Merging is contiguity-based, not strictly overlap-based."""

    def test_overlapping_ranges_merge(self, view: _ConcreteView) -> None:
        """The obvious case."""
        assert view._merge_ranges([(1, 5), (3, 8)]) == [(1, 8)]

    def test_adjacent_ranges_merge(self, view: _ConcreteView) -> None:
        """
        ``(1,3)`` and ``(4,6)`` become ``(1,6)``: contiguous counts as overlapping.

        The condition is ``merged[-1][1] < start - 1``, so a one-unit gap closes.
        """
        assert view._merge_ranges([(1, 3), (4, 6)]) == [(1, 6)]

    def test_a_two_unit_gap_does_not_merge(self, view: _ConcreteView) -> None:
        """One further apart and they stay separate, which fixes the boundary."""
        assert view._merge_ranges([(1, 3), (5, 6)]) == [(1, 3), (5, 6)]

    def test_input_order_does_not_matter(self, view: _ConcreteView) -> None:
        """The list is sorted first."""
        assert view._merge_ranges([(10, 12), (1, 3)]) == [(1, 3), (10, 12)]

    def test_a_contained_range_does_not_shrink_its_container(
        self, view: _ConcreteView
    ) -> None:
        """``max`` guards against a shorter nested range truncating the merge."""
        assert view._merge_ranges([(1, 10), (2, 3)]) == [(1, 10)]

    def test_no_ranges_gives_no_ranges(self, view: _ConcreteView) -> None:
        """The empty case is not a special case."""
        assert view._merge_ranges([]) == []


class TestFormatRanges:
    """Formatting is raw ``str()``, which shows in how numbers render."""

    def test_ranges_and_singletons_render_differently(
        self, view: _ConcreteView
    ) -> None:
        """A degenerate range collapses to a bare number."""
        assert view._format_ranges([(8, 11), (13, 13)]) == "8-11,13"

    def test_floats_round_trip_as_floats(self, view: _ConcreteView) -> None:
        """No formatting is applied, so fractional bounds keep their point."""
        assert view._format_ranges([(1.5, 4.5)]) == "1.5-4.5"

    def test_a_whole_float_still_renders_a_trailing_zero(
        self, view: _ConcreteView
    ) -> None:
        """
        ``str(5.0)`` is ``'5.0'``, so a float-parsed integer does not render as ``'5'``.

        Worth pinning: it means a parse-then-format round trip is not the identity
        when ``allow_floats`` is on.
        """
        assert view._format_ranges([(5.0, 5.0)]) == "5.0"

    def test_no_ranges_gives_an_empty_string(self, view: _ConcreteView) -> None:
        """Not ``None``, and not a stray comma."""
        assert view._format_ranges([]) == ""


class TestExpandEventIndices:
    """Expanding a range string into every index it names."""

    def test_ranges_expand_inclusively(self, view: _ConcreteView) -> None:
        """Both bounds are included."""
        assert view._expand_event_indices("1,3-5") == [1, 3, 4, 5]

    def test_the_result_is_sorted_and_deduplicated(self, view: _ConcreteView) -> None:
        """It is backed by a set, so overlaps collapse and order is imposed."""
        assert view._expand_event_indices("5,1-3,2") == [1, 2, 3, 5]

    def test_negative_segments_are_skipped(self, view: _ConcreteView) -> None:
        """A negative bound is dropped rather than raising."""
        assert view._expand_event_indices("-3,4") == [4]

    def test_a_two_hyphen_segment_is_skipped(self, view: _ConcreteView) -> None:
        """Explicitly guarded here, unlike ``_parse_event_indices`` which warns."""
        assert view._expand_event_indices("1-2-3,7") == [7]

    def test_a_descending_range_yields_nothing(self, view: _ConcreteView) -> None:
        """``range(5, 2)`` is empty; no error, no output."""
        assert view._expand_event_indices("5-2") == []

    def test_junk_is_skipped_silently(self, view: _ConcreteView) -> None:
        """Unlike the parser, this one does not even log."""
        assert view._expand_event_indices("abc,2") == [2]
