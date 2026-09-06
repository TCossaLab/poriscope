"""
Characterization tests for ``ProteinView._summarize_vm``.

The method had **zero references anywhere in tests/**. It is pure - a DataFrame in,
formatted strings out - with three branches that each render differently, and it is
what the protein tab shows the user after a Monte Carlo shape fit. Step 4c moves
the computation it summarises, so its output is pinned first.

Values are asserted as literal strings rather than through ``pytest-regressions``:
the whole point of this method is the exact text a user reads, and a golden file
would hide that behind a diff.
"""

import numpy as np
import pandas as pd
import pytest

from poriscope.plugins.analysistabs.ProteinView import ProteinView
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization

# Named rather than inlined, so an assertion reads as text instead of as a wall of
# punctuation. The source writes them as ³ and ±; these are the same two
# characters, and any mismatch fails the equality assertions below immediately.
CUBED = "³"
PLUSMINUS = "±"


@pytest.fixture
def view() -> ProteinView:
    """
    Build a ProteinView without constructing any Qt widget.

    ``_summarize_vm`` touches nothing on ``self``, so nothing beyond the signal
    shadowing is needed. The logger is left real, per ``_qt_mocks.py``'s warning.

    :return: a ProteinView with its signals shadowed
    :rtype: ProteinView
    """
    instance = ProteinView.__new__(ProteinView)
    shadow_signals(instance, ProteinView)
    return instance


def shape_frame(v: list, a: list, b: list, m: list) -> pd.DataFrame:
    """
    Build a sampled-shape frame in the column order the method reads.

    :param v: volume samples
    :type v: list
    :param a: long semi-axis samples
    :type a: list
    :param b: short semi-axis samples
    :type b: list
    :param m: aspect-ratio samples
    :type m: list
    :return: the frame
    :rtype: pd.DataFrame
    """
    return pd.DataFrame({"V": v, "a": a, "b": b, "m": m})


class TestSummarizeVmEmpty:
    """No samples at all."""

    def test_no_rows_reports_explicitly(self, view: ProteinView) -> None:
        """An empty frame gives no rows and a labelled reason, not a blank readout."""
        rows, label = view._summarize_vm(shape_frame([], [], [], []))

        assert rows == []
        assert label == "no samples generated"


class TestSummarizeVmSingleSample:
    """One sample: the standard deviation is undefined and is not shown."""

    def test_a_single_sample_renders_plain_values(self, view: ProteinView) -> None:
        """
        No ``+/-`` term, because a one-sample standard deviation is NaN.

        pandas' ``std`` defaults to ``ddof=1``, so without this branch the readout
        would print ``nan`` at the user.
        """
        rows, label = view._summarize_vm(shape_frame([123.45], [9.87], [1.23], [8.0]))

        assert rows == [
            f"V = 123.5 nm{CUBED}",
            "a = 9.9 nm",
            "b = 1.2 nm",
            "m = 8.00",
        ]
        assert label == "N=1 sample, std undefined for a single sample"

    def test_the_single_sample_branch_never_emits_a_plus_minus(
        self, view: ProteinView
    ) -> None:
        """Guards the NaN specifically, since it is what the branch exists for."""
        rows, _ = view._summarize_vm(shape_frame([1.0], [1.0], [1.0], [1.0]))

        assert not any(PLUSMINUS in row for row in rows)
        assert not any("nan" in row.lower() for row in rows)


class TestSummarizeVmManySamples:
    """The normal case: median plus sample standard deviation."""

    def test_median_and_std_are_rendered_per_row(self, view: ProteinView) -> None:
        """
        Chosen so the arithmetic is readable: median 200, sample std 100, and so on.

        Note the differing precision - V, a and b carry one decimal place and m
        carries two, which is a deliberate part of the readout.
        """
        rows, label = view._summarize_vm(
            shape_frame(
                [100.0, 200.0, 300.0],
                [10.0, 20.0, 30.0],
                [1.0, 2.0, 3.0],
                [1.0, 2.0, 3.0],
            )
        )

        assert rows == [
            f"V = 200.0 {PLUSMINUS} 100.0 nm{CUBED}",
            f"a = 20.0 {PLUSMINUS} 10.0 nm",
            f"b = 2.0 {PLUSMINUS} 1.0 nm",
            f"m = 2.00 {PLUSMINUS} 1.00",
        ]
        assert label == "N=3 samples"

    def test_it_reports_the_median_not_the_mean(self, view: ProteinView) -> None:
        """
        A skewed sample distinguishes the two, and the method promises the median.

        ``[1, 2, 60]`` has median 2 and mean 21, so this would fail loudly if the
        statistic changed.
        """
        rows, _ = view._summarize_vm(
            shape_frame(
                [1.0, 2.0, 60.0], [1.0, 2.0, 60.0], [1.0, 2.0, 60.0], [1.0, 2.0, 60.0]
            )
        )

        assert rows[0].startswith("V = 2.0 ")

    def test_the_sample_count_is_the_row_count(self, view: ProteinView) -> None:
        """The label reports N, which drives what the user trusts the spread to mean."""
        values = list(np.arange(10.0))
        _, label = view._summarize_vm(shape_frame(values, values, values, values))

        assert label == "N=10 samples"

    def test_a_two_sample_frame_takes_the_many_branch(self, view: ProteinView) -> None:
        """
        Two is the boundary: ``ddof=1`` is defined here, so the spread is shown.

        Pinned because an off-by-one in the branch condition would silently drop a
        legitimate spread or print a NaN.
        """
        rows, label = view._summarize_vm(
            shape_frame([10.0, 20.0], [1.0, 3.0], [1.0, 1.0], [2.0, 2.0])
        )

        assert label == "N=2 samples"
        assert all(PLUSMINUS in row for row in rows)
        # std of two identical values is 0, not NaN
        assert rows[2] == f"b = 1.0 {PLUSMINUS} 0.0 nm"
