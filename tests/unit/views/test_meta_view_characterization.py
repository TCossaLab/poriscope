"""
Characterization tests for ``MetaView``'s data methods, ahead of the 2.0.0 refactor.

``poriscope/utils/MetaView.py`` has no dedicated test file, and the methods pinned
here are the ones Step 3d moves from ``MetaView`` to ``MetaModel``. Two of them are
the reason this file exists at all:

- ``_logscale_and_filter_multiple_columns`` is referenced by 38 test functions and
  **every one replaces it with a Mock**, so its body has no behavioural coverage
  while sitting on every 1-D and 2-D plot path in ``MetadataView``.
- ``_logscale_and_filter_dataframe`` **is gone.** It had no references in
  ``tests/`` at all and one caller, ``ClusteringView.py``. Pinning the pair's
  differences is what made unifying them a decision rather than an accident: dtype
  behaviour and the status-panel text turned out identical, and the two real
  divergences - ``dropna()``'s wider row scope and its tolerance of a text column -
  were inert at that single call site, which passed exactly ``columns + ["id"]``.
  Step 3d-pre therefore deleted the frame form and adapted the caller to pass those
  same columns as arrays. Its nine tests went with it; the surviving behaviour is
  covered by ``TestLogscaleMultipleColumns`` below and, end to end, by
  ``tests/integration/flows/test_clustering_flow_no_gui.py``.

The five range helpers are pinned for a different reason. They do have tests, in
``test_protein_view.py``'s ``TestRangeHelpers``, but weak ones: the shift tests
assert an ``or``-chain of three alternatives, and one asserts ``>= 0`` under a
comment claiming a clamp the implementation does not have. ``_shift_ranges``
**reflects** a multi-element range rather than translating it, which is
non-obvious and effectively unpinned today.

Values are asserted explicitly rather than through ``pytest-regressions``: these
return short tuples, lists and strings, and a golden file for a two-element tuple
is less legible than the literal.
"""

from typing import Dict, List

import numpy as np
import pytest
from PySide6.QtWidgets import QBoxLayout

from poriscope.utils.MetaView import MetaView
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization


class _ConcreteView(MetaView):
    """A minimal concrete MetaView, so the base's own methods can be exercised."""

    def _init(self) -> None:
        """Satisfy the abstract hook; the tests need no state from it."""

    def _set_control_area(self, layout: QBoxLayout) -> None:
        """Satisfy the abstract hook; no controls widget is built."""

    def _reset_actions(self, axis_type: str = "2d") -> None:
        """Satisfy the abstract hook; no canvas exists to reset."""

    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """Satisfy the abstract hook; no comboboxes to populate."""

    def notify_plugin_state_changed(
        self, metaclass: str, plugin_key: str, reason: str
    ) -> None:
        """Satisfy the abstract hook; nothing listens."""


@pytest.fixture
def view() -> _ConcreteView:
    """
    Build a MetaView without constructing any Qt widget.

    ``__new__`` skips ``QWidget.__init__``, so there is no C++ object behind the
    instance and emitting a class-level Signal would raise "Signal source has been
    deleted"; ``shadow_signals`` swaps each for a stand-in. ``logger`` is a class
    attribute and is deliberately left alone - mocking it blinds ``caplog``.

    :return: a MetaView subclass instance with its signals shadowed
    :rtype: _ConcreteView
    """
    instance = _ConcreteView.__new__(_ConcreteView)
    shadow_signals(instance, _ConcreteView)
    return instance


# ===========================================================================
# _logscale_and_filter_multiple_columns - 38 test references, all Mocks
# ===========================================================================


class TestLogscaleMultipleColumns:
    """The array form: NaN masking, sign rectification, sequential filtering."""

    def test_no_arrays_returns_an_empty_tuple(self, view: _ConcreteView) -> None:
        """The no-data guard returns ``()``, not ``None``."""
        assert view._logscale_and_filter_multiple_columns() == ()

    def test_without_log_flags_only_nans_are_removed(self, view: _ConcreteView) -> None:
        """No flags means no scaling; the arrays come back filtered but untransformed."""
        a = np.array([1.0, 2.0, np.nan, 4.0])
        b = np.array([10.0, 20.0, 30.0, 40.0])

        out_a, out_b = view._logscale_and_filter_multiple_columns(a, b)

        np.testing.assert_array_equal(out_a, [1.0, 2.0, 4.0])
        np.testing.assert_array_equal(out_b, [10.0, 20.0, 40.0])

    def test_a_nan_in_one_array_drops_the_row_from_all(
        self, view: _ConcreteView
    ) -> None:
        """The NaN mask is combined across every array, so filtering stays aligned."""
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([np.nan, 20.0, 30.0])

        out_a, out_b = view._logscale_and_filter_multiple_columns(a, b)

        np.testing.assert_array_equal(out_a, [2.0, 3.0])
        np.testing.assert_array_equal(out_b, [20.0, 30.0])

    def test_log10_is_applied_to_the_flagged_column_only(
        self, view: _ConcreteView
    ) -> None:
        """Only flagged columns are transformed; the others are merely row-filtered."""
        a = np.array([1.0, 10.0, 100.0])
        b = np.array([1.0, 10.0, 100.0])

        out_a, out_b = view._logscale_and_filter_multiple_columns(
            a, b, log_flags=[True, False]
        )

        np.testing.assert_allclose(out_a, [0.0, 1.0, 2.0])
        np.testing.assert_array_equal(out_b, [1.0, 10.0, 100.0])

    def test_all_negative_data_is_rectified_by_its_average_sign(
        self, view: _ConcreteView
    ) -> None:
        """
        Negative data is flipped positive before the log, not discarded.

        The sign comes from the array's *average*, so a wholly negative column
        logs its magnitudes rather than filtering itself away entirely.
        """
        a = np.array([-1.0, -10.0, -100.0])

        (out,) = view._logscale_and_filter_multiple_columns(a, log_flags=[True])

        np.testing.assert_allclose(out, [0.0, 1.0, 2.0])

    def test_values_on_the_wrong_side_of_zero_are_dropped_from_every_array(
        self, view: _ConcreteView
    ) -> None:
        """
        Rectification filters, and the filter applies to all arrays, not just one.

        The average of ``[1, 10, -5]`` is positive, so ``-5`` fails ``rectified > 0``
        and its row leaves both arrays.
        """
        a = np.array([1.0, 10.0, -5.0])
        b = np.array([7.0, 8.0, 9.0])

        out_a, out_b = view._logscale_and_filter_multiple_columns(
            a, b, log_flags=[True, False]
        )

        np.testing.assert_allclose(out_a, [0.0, 1.0])
        np.testing.assert_array_equal(out_b, [7.0, 8.0])

    def test_a_zero_average_defaults_to_a_positive_sign(
        self, view: _ConcreteView
    ) -> None:
        """``np.sign(0)`` is 0, which would zero the data, so the code forces +1."""
        a = np.array([-1.0, 1.0])

        (out,) = view._logscale_and_filter_multiple_columns(a, log_flags=[True])

        np.testing.assert_allclose(out, [0.0])

    def test_wrong_length_log_flags_raises(self, view: _ConcreteView) -> None:
        """Arity is validated rather than silently zipped short."""
        with pytest.raises(ValueError, match="same length"):
            view._logscale_and_filter_multiple_columns(
                np.array([1.0]), np.array([2.0]), log_flags=[True]
            )

    def test_dropped_points_are_reported_on_the_status_panel(
        self, view: _ConcreteView
    ) -> None:
        """
        Both filtering stages tell the user how much data they lost.

        A silent drop is the failure mode this reporting exists to prevent.
        """
        a = np.array([1.0, np.nan, -5.0, 10.0])

        view._logscale_and_filter_multiple_columns(a, log_flags=[True])

        messages = [
            call.args[0] for call in view.add_text_to_display.emit.call_args_list
        ]
        assert any("contained NaN" in m for m in messages)
        assert any("could not be logscaled" in m for m in messages)


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
