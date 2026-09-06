"""
Equivalence tests for the helpers Step 3 is about to merge into a shared base.

The duplication ratchet counts byte-identical bodies; it cannot say whether two
copies *behave* the same, and it says nothing at all about a third copy that was
inlined instead of written as a method. That is what this file is for. Each group
below is merged by Step 3 or Step 4, and the merge should be a decision someone
makes about known behaviour rather than a silent change.

Two groups:

- ``_factors`` exists three times - ``MetaView.py:139`` plus byte-identical
  overrides in ``RawDataView.py:109`` and ``EventAnalysisView.py:121`` that shadow
  the base they could simply inherit. Step 3c deletes the two overrides. Nothing
  today asserts the three agree; each is tested separately in its own module.
- ``format_axis_label`` exists three times, and **the third one differs**.
  ``ProteinView.py:4037`` is a module-level function, ``MetadataView.py:3645`` is
  a byte-identical method, and ``ClusteringView.py:731-742`` is an inlined loop
  that neither strips a pre-existing trailing parenthetical nor rejects a
  whitespace-only unit. The two callable copies are asserted equal here, and the
  two specific behaviours the inline copy lacks are pinned as named tests so that
  merging all three is an explicit decision.
"""

from typing import Optional

import pytest
from PySide6.QtWidgets import QBoxLayout

from poriscope.plugins.analysistabs.EventAnalysisView import EventAnalysisView
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.plugins.analysistabs.ProteinView import format_axis_label
from poriscope.plugins.analysistabs.RawDataView import RawDataView
from poriscope.utils.MetaView import MetaView
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization


class _BaseOnlyView(MetaView):
    """A concrete MetaView that adds nothing, so the base's own copy is reachable."""

    def _init(self) -> None:
        """Satisfy the abstract hook."""

    def _set_control_area(self, layout: QBoxLayout) -> None:
        """Satisfy the abstract hook."""

    def _reset_actions(self, axis_type: str = "2d") -> None:
        """Satisfy the abstract hook."""

    def update_available_plugins(self, available_plugins: dict) -> None:
        """Satisfy the abstract hook."""

    def notify_plugin_state_changed(
        self, metaclass: str, plugin_key: str, reason: str
    ) -> None:
        """Satisfy the abstract hook."""


def build(cls: type) -> object:
    """
    Build a view without constructing any Qt widget.

    :param cls: the view class to instantiate
    :type cls: type
    :return: an instance with its declared signals shadowed
    :rtype: object
    """
    instance = cls.__new__(cls)
    shadow_signals(instance, cls)
    return instance


@pytest.fixture
def factors_copies() -> dict:
    """
    One instance per class carrying a ``_factors`` implementation.

    :return: the three carriers, keyed by class name
    :rtype: dict
    """
    return {
        "MetaView": build(_BaseOnlyView),
        "RawDataView": build(RawDataView),
        "EventAnalysisView": build(EventAnalysisView),
    }


# ===========================================================================
# _factors - three copies, two of them shadowing the base
# ===========================================================================


class TestFactorsAgree:
    """The three copies must return the same grid for the same input."""

    @pytest.mark.parametrize("n", list(range(1, 41)))
    def test_all_three_copies_agree(self, factors_copies: dict, n: int) -> None:
        """
        Swept rather than spot-checked, because the loop grows ``n`` until it can
        factor it nearly squarely, and a divergence could hide at any one value.
        """
        results = {name: view._factors(n) for name, view in factors_copies.items()}
        assert len(set(results.values())) == 1, results

    def test_the_overrides_are_not_merely_inherited(self) -> None:
        """
        The two subclasses genuinely redefine it rather than inheriting it.

        If this ever fails, Step 3c's deletion has already happened and the
        agreement tests above become trivially true - which is the point at which
        this test should be removed rather than repaired.
        """
        assert "_factors" in RawDataView.__dict__
        assert "_factors" in EventAnalysisView.__dict__


class TestFactorsBehaviour:
    """What the shared implementation actually computes."""

    @pytest.mark.parametrize(
        ("n", "expected"),
        [
            (1, (1, 1)),
            (2, (1, 2)),
            (4, (2, 2)),
            (5, (2, 3)),
            (6, (2, 3)),
            (7, (2, 4)),
            (9, (3, 3)),
            (12, (3, 4)),
            (13, (3, 5)),
            (16, (4, 4)),
        ],
    )
    def test_it_returns_the_nearest_square_grid(
        self, factors_copies: dict, n: int, expected: tuple
    ) -> None:
        """
        A prime is rounded *up* to the next number that factors well.

        ``_factors(5)`` is ``(2, 3)``, not ``(1, 5)``: the loop increments ``n``
        until the factor pair differs by at most 2, so the caller gets a usable
        subplot grid with a spare cell rather than a one-row strip.
        """
        assert factors_copies["MetaView"]._factors(n) == expected

    def test_the_grid_is_never_smaller_than_requested(
        self, factors_copies: dict
    ) -> None:
        """The product must still fit every subplot the caller asked for."""
        for n in range(1, 41):
            rows, cols = factors_copies["MetaView"]._factors(n)
            assert rows * cols >= n


# ===========================================================================
# format_axis_label - two identical copies and one that is not
# ===========================================================================


LABEL_CASES = [
    ("Duration", "us", "Duration (us)"),
    ("Duration", None, "Duration"),
    ("Duration", "", "Duration"),
    ("Duration (us)", "ms", "Duration (ms)"),
    ("Duration (us)", None, "Duration"),
    ("Max Amplitude", "pA", "Max Amplitude (pA)"),
    # See TestFormatAxisLabelStripsFromTheFirstParenthesis: the strip reaches back
    # to the *first* parenthesis, not the last, so everything after "A" is lost.
    ("A (nested) label (us)", "pA", "A (pA)"),
    ("", "pA", " (pA)"),
]


@pytest.fixture
def metadata_view() -> MetadataView:
    """
    A MetadataView carrying the method-shaped copy of ``format_axis_label``.

    :return: the view
    :rtype: MetadataView
    """
    return build(MetadataView)


class TestFormatAxisLabelCopiesAgree:
    """The ProteinView function and the MetadataView method are interchangeable."""

    @pytest.mark.parametrize(("label", "unit", "expected"), LABEL_CASES)
    def test_both_copies_produce_the_expected_text(
        self,
        metadata_view: MetadataView,
        label: str,
        unit: Optional[str],
        expected: str,
    ) -> None:
        """Same input, same output, and the output itself is pinned."""
        assert format_axis_label(label, unit) == expected
        assert metadata_view.format_axis_label(label, unit) == expected


class TestFormatAxisLabelDivergenceFromClusteringView:
    """
    The two behaviours ``ClusteringView``'s inlined copy does not share.

    Named individually rather than folded into the table above, because these are
    precisely the decisions Step 3 has to make when the three are merged. The
    inline builder at ``ClusteringView.py:731-742`` composes its label from the
    column name and appends the unit under ``unit is not None and unit != "" and
    unit != " "`` - a three-way literal check rather than ``.strip()`` - and it
    never removes an existing parenthetical because it never receives one.
    """

    def test_a_whitespace_only_unit_is_rejected(
        self, metadata_view: MetadataView
    ) -> None:
        """
        ``.strip()`` rejects any run of spaces; the inline copy only rejects one.

        ``metadatacontrols`` manufactures the single-space unit deliberately, so a
        two-space unit reaching the inline copy would render ``Label (  )``.
        """
        for blank in (" ", "  ", "\t", "\n"):
            assert format_axis_label("Label", blank) == "Label"
            assert metadata_view.format_axis_label("Label", blank) == "Label"

    def test_an_existing_trailing_parenthetical_is_replaced_not_appended(
        self, metadata_view: MetadataView
    ) -> None:
        """
        Re-labelling the same axis twice must not accumulate units.

        The inline copy has no equivalent, which is safe only because it always
        builds its label from a bare column name.
        """
        once = format_axis_label("Duration", "us")
        twice = format_axis_label(once, "ms")

        assert once == "Duration (us)"
        assert twice == "Duration (ms)"
        assert metadata_view.format_axis_label(once, "ms") == "Duration (ms)"

    def test_nothing_is_stripped_without_a_trailing_parenthesis(
        self, metadata_view: MetadataView
    ) -> None:
        """The pattern is anchored at end-of-string, so a mid-label group survives."""
        assert format_axis_label("Rate (per pore) count", "Hz") == (
            "Rate (per pore) count (Hz)"
        )
        assert metadata_view.format_axis_label("Rate (per pore) count", "Hz") == (
            "Rate (per pore) count (Hz)"
        )


class TestFormatAxisLabelStripsFromTheFirstParenthesis:
    """
    A quirk found while writing these tests, characterized rather than fixed.

    The pattern is ``\\s*\\(.*?\\)$``. The ``.*?`` is lazy, but it is anchored at
    ``$``, so the leftmost match wins and ``.*?`` expands across every intervening
    ``)``. The strip therefore reaches back to the **first** parenthesis in the
    label, not the last, whenever the label happens to end in ``)``.

    That is a live defect for any column whose name contains parentheses: a column
    called ``Rate (per pore)`` plotted with unit ``Hz`` is labelled ``Rate (Hz)``,
    silently losing ``per pore``. It is queued in ``future_fixes.md`` rather than
    fixed here - this file's job is to record what the code does today so Step 3's
    merge of the three copies is not blamed for it later.
    """

    def test_a_label_ending_in_a_parenthetical_loses_everything_from_the_first_one(
        self, metadata_view: MetadataView
    ) -> None:
        """``a (b) (c) (d)`` collapses to ``a``, not to ``a (b) (c)``."""
        assert format_axis_label("a (b) (c) (d)", "X") == "a (X)"
        assert metadata_view.format_axis_label("a (b) (c) (d)", "X") == "a (X)"

    def test_a_meaningful_parenthetical_column_name_is_truncated(
        self, metadata_view: MetadataView
    ) -> None:
        """The user-visible consequence: ``per pore`` disappears from the axis."""
        assert format_axis_label("Rate (per pore)", "Hz") == "Rate (Hz)"
        assert metadata_view.format_axis_label("Rate (per pore)", "Hz") == "Rate (Hz)"

    def test_a_label_that_is_entirely_a_parenthetical_becomes_empty(
        self, metadata_view: MetadataView
    ) -> None:
        """Leaving a leading space before the unit, which is what the axis shows."""
        assert format_axis_label("(all)", "pA") == " (pA)"
        assert metadata_view.format_axis_label("(all)", "pA") == " (pA)"
