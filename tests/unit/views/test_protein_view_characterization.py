"""
Characterization tests for ``ProteinView._summarize_vm``.

The method had **zero references anywhere in tests/**. It is pure - a DataFrame in,
formatted strings out - with three branches that each render differently, and it is
what the protein tab shows the user after a Monte Carlo shape fit. Its output was
pinned before the computation it summarises moved to ProteinModel.

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


# ``TestResolveEventDbIds`` lived here and is gone: the whole resolve-and-load
# chain is in ``ProteinController.load_event_plot_data``, so there is
# no View method left for it to name. Its coverage is
# ``tests/unit/controllers/test_protein_fetch_slots.py::TestLoadEventPlotData``,
# written against the loader signatures rather than against the bus. One expectation
# inverted rather than moved: ``test_a_failed_experiment_lookup_omits_the_clause_entirely``
# pinned the widget dropping the experiment scope when the lookup failed, which is the
# unscoped-query fault the conversion fixes. It is now
# ``test_an_unresolvable_experiment_stops_the_plot``.


class TestReportEnsembleFit:
    """
    The Report All readout.

    Ensemble mode has no per-event id to write results back against, so this readout
    is the *only* record of an ensemble fit - if it silently reported the wrong numbers
    there would be nothing else to check them against. The Controller hands it the fit
    the Model keeps, and says itself when there is none.
    """

    PARAMS = np.array([10.0, 0.15, 0.03, 6.0, 0.40, 0.04])
    NONE = pd.DataFrame(columns=["V", "a", "b", "m"])

    def reported(
        self,
        view: ProteinView,
        bins: object = 75,
        sizes: bool = False,
        prolate: pd.DataFrame = NONE,
        oblate: pd.DataFrame = NONE,
    ) -> str:
        """
        Report a fit and return the text the view pushed to the status panel.

        :param view: the view
        :type view: ProteinView
        :param bins: the fit's bins entry
        :type bins: object
        :param sizes: does bins refer to a bin width
        :type sizes: bool
        :param prolate: the prolate solutions
        :type prolate: pd.DataFrame
        :param oblate: the oblate solutions
        :type oblate: pd.DataFrame
        :return: the emitted message
        :rtype: str
        """
        view.show_ensemble_report(self.PARAMS, bins, sizes, prolate, oblate)
        return view.add_text_to_display.emit.call_args.args[0]

    def test_both_peaks_are_reported(self, view: ProteinView) -> None:
        """All six fitted parameters reach the user, at four significant figures."""
        text = self.reported(view)

        assert "amplitude=10, mean=0.15, std=0.03" in text
        assert "amplitude=6, mean=0.4, std=0.04" in text

    def test_a_bin_count_is_labelled_as_a_count(self, view: ProteinView) -> None:
        """
        The binning is part of the result, since a different binning gives a
        different fit, and count and size mean different things.
        """
        assert "bin count = 75" in self.reported(view)

    def test_bin_sizes_are_labelled_as_sizes(self, view: ProteinView) -> None:
        """The other branch of the same label."""
        assert "bin size(s) = [1.0, 2.0]" in self.reported(view, [1.0, 2.0], True)

    def test_an_unset_bin_count_falls_back_to_the_default(
        self, view: ProteinView
    ) -> None:
        """``None`` means the plot used the default of 100, not that it used none."""
        assert "bin count = 100" in self.reported(view, None)

    def test_the_shape_summaries_are_included_when_present(
        self, view: ProteinView
    ) -> None:
        """Both families are reported, each under its own heading."""
        text = self.reported(
            view,
            prolate=shape_frame([1.0] * 3, [2.0] * 3, [1.0] * 3, [2.0] * 3),
            oblate=shape_frame([2.0] * 4, [2.0] * 4, [1.0] * 4, [2.0] * 4),
        )

        assert "<b>Prolate</b> (N=3 samples)" in text
        assert "<b>Oblate</b> (N=4 samples)" in text

    def test_a_missing_summary_is_omitted_rather_than_shown_empty(
        self, view: ProteinView
    ) -> None:
        """
        Sampling can produce one family and not the other, and a heading with
        nothing under it would read as a result of zero rather than as no result.
        """
        text = self.reported(
            view, prolate=shape_frame([1.0] * 3, [2.0] * 3, [1.0] * 3, [2.0] * 3)
        )

        assert "<b>Prolate</b>" in text
        assert "Oblate" not in text
