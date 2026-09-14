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


def _solutions():
    """
    A stand-in for one family of sampled geometries.

    :return: a frame with the four geometry columns
    :rtype: pd.DataFrame
    """
    return pd.DataFrame(
        {"V": [100.0, 200.0], "m": [2.0, 3.0], "a": [4.0, 6.0], "b": [2.0, 2.0]}
    )


class TestEnsembleGeometryFit:
    """
    The two halves of the chain: ask for the fit, then sample and plot from it.

    **Step 4c split this.** ``_fit_and_plot_ensemble_geometry`` used to fit inline
    and return a ``bool``; the fit now lives on ``ProteinModel`` and the pair is
    ``_request_ensemble_geometry_fit`` and ``set_ensemble_geometry_fit``. The
    ``bool`` is gone with it, because the single caller's ``if not ...: return`` was
    its own last statement and so decided nothing - the tests that asserted on it
    assert on what the user is told instead.

    The numeric content is covered elsewhere and deliberately not repeated here:
    the fit in ``tests/unit/models/test_protein_model.py``, the sampler in its own
    tests. What is pinned here is the wiring - what the request carries, which
    branch bails out, what the user is told, and which ``ensemble_fit_*``
    attributes ``_report_ensemble_fit`` will later read back.

    ``_generate_vm_ensemble`` is stubbed to return arrays because it is a Monte
    Carlo rejection sampler that would otherwise dominate the runtime; it is
    stubbed the way it really behaves, returning a ``(V, m)`` pair of arrays, and
    the empty-array case it really produces for unphysical geometry is exercised
    as its own branch below.
    """

    @pytest.fixture
    def plot_data(self) -> pd.DataFrame:
        """
        A two-peaked histogram of the shape the ensemble fit consumes.

        :return: the frame
        :rtype: pd.DataFrame
        """
        current = np.linspace(0.0, 0.6, 200)
        amplitude = 100.0 * np.exp(
            -((current - 0.15) ** 2) / (2 * 0.03**2)
        ) + 60.0 * np.exp(-((current - 0.40) ** 2) / (2 * 0.04**2))
        return pd.DataFrame({"Normalized Current": current, "Amplitude": amplitude})

    def test_the_request_half_emits_the_histogram_and_its_context(
        self, view: ProteinView, plot_data: pd.DataFrame
    ) -> None:
        """
        The asking half does nothing but ask, and carries the context with it.

        Pinned because the context travelling through the round trip is what keeps
        it off the widget between the halves; parking it here instead would still
        draw the right plot and would reintroduce exactly the pattern Step 4a
        deleted.
        """
        view._request_ensemble_geometry_fit(plot_data, "Histogram", 10.0, 12.0, 50)

        emitted = view.ensemble_fit_requested.emit.call_args.args
        np.testing.assert_array_equal(
            emitted[0], plot_data["Normalized Current"].values
        )
        np.testing.assert_array_equal(emitted[1], plot_data["Amplitude"].values)
        assert emitted[3:] == ("Histogram", 10.0, 12.0, 50)

    def test_a_successful_run_records_the_state_report_all_reads_back(
        self, view: ProteinView, mocker, plot_data: pd.DataFrame
    ) -> None:
        """
        The success path, pinned by the attributes it leaves behind.

        ``_report_ensemble_fit`` reads every one of these, and Step 4c moved the
        fit while Step 4's closeout moved the sampling, so a wiring regression here
        would surface as an empty or stale report rather than as an exception.
        """
        view.allowed_bins = 75
        view.allowed_sizes = True
        popt = np.array([100.0, 0.15, 0.03, 60.0, 0.40, 0.04])
        update_plot = mocker.patch.object(view, "update_plot")

        view.set_ensemble_geometry_fit(
            popt,
            plot_data["Amplitude"].values,
            plot_data,
            "Histogram",
            _solutions(),
            _solutions(),
        )

        np.testing.assert_array_equal(view.ensemble_fit_params, popt)
        assert view.ensemble_fit_bins == 75
        assert view.ensemble_fit_sizes is True
        assert view.ensemble_fit_prolate_summary is not None
        assert view.ensemble_fit_oblate_summary is not None
        # the fit overlay, then one scatter per solution family
        assert update_plot.call_count == 3
        labels = [c.kwargs["dataset_label"] for c in update_plot.call_args_list[1:]]
        assert labels == ["Prolate Solutions", "Oblate Solutions"]

    def test_an_unsampled_ensemble_still_draws_the_fit(
        self, view: ProteinView, mocker, plot_data: pd.DataFrame
    ) -> None:
        """
        The sampler bailing out is the Controller's to report, and it still calls
        this - so the fitted curve stays on the screen and only the two empty
        scatterplots are skipped. Refusing to call it would have taken the fit off
        the axes along with the solutions.
        """
        view.allowed_bins = 100
        view.allowed_sizes = False
        update_plot = mocker.patch.object(view, "update_plot")
        empty = pd.DataFrame(columns=["V", "m", "a", "b"])

        view.set_ensemble_geometry_fit(
            np.array([100.0, 0.15, 0.03, 60.0, 0.40, 0.04]),
            plot_data["Amplitude"].values,
            plot_data,
            "Histogram",
            empty,
            empty,
        )

        assert update_plot.call_count == 1
        assert view.ensemble_fit_prolate_summary is None
        assert view.ensemble_fit_oblate_summary is None

    def test_the_curve_that_arrives_is_what_gets_plotted(
        self, view: ProteinView, mocker, plot_data: pd.DataFrame
    ) -> None:
        """
        The fitted curve is drawn as handed over, not recomputed here.

        This is the assertion that would fail if ``_double_gaussian`` were quietly
        reintroduced into the View to evaluate the fit a second time.
        """
        view.allowed_bins = 100
        view.allowed_sizes = False
        curve = np.linspace(1.0, 2.0, len(plot_data))
        update_plot = mocker.patch.object(view, "update_plot")

        view.set_ensemble_geometry_fit(
            np.array([100.0, 0.15, 0.03, 60.0, 0.40, 0.04]),
            curve,
            plot_data,
            "Histogram",
            _solutions(),
            _solutions(),
        )

        drawn = update_plot.call_args_list[0].args[1]
        np.testing.assert_array_equal(drawn["Amplitude"].values, curve)


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


# ``TestResolveEventDbIds`` lived here and is gone: Step 4a moved the whole
# resolve-and-load chain into ``ProteinController.load_event_plot_data``, so there is
# no View method left for it to name. Its coverage is
# ``tests/unit/controllers/test_protein_fetch_slots.py::TestLoadEventPlotData``,
# written against the loader signatures rather than against the bus. One expectation
# inverted rather than moved: ``test_a_failed_experiment_lookup_omits_the_clause_entirely``
# pinned the widget dropping the experiment scope when the lookup failed, which is the
# unscoped-query fault the conversion fixes. It is now
# ``test_an_unresolvable_experiment_stops_the_plot``.


class TestReportEnsembleFit:
    """
    The Report All readout, a Step 4c target the exit review found unpinned.

    It executed under the protein e2e flow but nothing named it, so nothing
    asserted what the user is actually shown. Ensemble mode has no per-event id to
    write results back against, so this readout is the *only* record of an ensemble
    fit - if it silently reported the wrong numbers there would be nothing else to
    check them against.
    """

    @pytest.fixture
    def fitted(self, view: ProteinView) -> ProteinView:
        """
        A view carrying the state a completed ensemble fit leaves behind.

        :param view: the bare view
        :type view: ProteinView
        :return: the view, as if an ensemble fit had just run
        :rtype: ProteinView
        """
        view.ensemble_fit_params = np.array([10.0, 0.15, 0.03, 6.0, 0.40, 0.04])
        view.ensemble_fit_bins = 75
        view.ensemble_fit_sizes = False
        view.ensemble_fit_prolate_summary = None
        view.ensemble_fit_oblate_summary = None
        return view

    def reported(self, view: ProteinView) -> str:
        """
        The text the view last pushed to the status panel.

        :param view: the view
        :type view: ProteinView
        :return: the emitted message
        :rtype: str
        """
        return view.add_text_to_display.emit.call_args.args[0]

    def test_no_fit_reports_that_rather_than_an_empty_table(
        self, view: ProteinView
    ) -> None:
        """
        Asking for a report before running one says so, and returns.

        The alternative - unpacking None into six names - would raise at the user
        for what is an ordinary mistake.
        """
        view.ensemble_fit_params = None

        view._report_ensemble_fit()

        assert "No ensemble fit available" in self.reported(view)

    def test_both_peaks_are_reported(self, fitted: ProteinView) -> None:
        """All six fitted parameters reach the user, at four significant figures."""
        fitted._report_ensemble_fit()
        text = self.reported(fitted)

        assert "amplitude=10, mean=0.15, std=0.03" in text
        assert "amplitude=6, mean=0.4, std=0.04" in text

    def test_a_bin_count_is_labelled_as_a_count(self, fitted: ProteinView) -> None:
        """
        The binning is part of the result, since a different binning gives a
        different fit, and count and size mean different things.
        """
        fitted._report_ensemble_fit()

        assert "bin count = 75" in self.reported(fitted)

    def test_bin_sizes_are_labelled_as_sizes(self, fitted: ProteinView) -> None:
        """The other branch of the same label."""
        fitted.ensemble_fit_sizes = True
        fitted.ensemble_fit_bins = [1.0, 2.0]

        fitted._report_ensemble_fit()

        assert "bin size(s) = [1.0, 2.0]" in self.reported(fitted)

    def test_an_unset_bin_count_falls_back_to_the_default(
        self, fitted: ProteinView
    ) -> None:
        """``None`` means the plot used the default of 100, not that it used none."""
        fitted.ensemble_fit_bins = None

        fitted._report_ensemble_fit()

        assert "bin count = 100" in self.reported(fitted)

    def test_the_shape_summaries_are_included_when_present(
        self, fitted: ProteinView
    ) -> None:
        """Both families are reported, each under its own heading."""
        fitted.ensemble_fit_prolate_summary = (["V = 1.0 nm"], "N=3 samples")
        fitted.ensemble_fit_oblate_summary = (["V = 2.0 nm"], "N=4 samples")

        fitted._report_ensemble_fit()
        text = self.reported(fitted)

        assert "<b>Prolate</b> (N=3 samples)" in text
        assert "<b>Oblate</b> (N=4 samples)" in text
        assert "V = 1.0 nm" in text and "V = 2.0 nm" in text

    def test_a_missing_summary_is_omitted_rather_than_shown_empty(
        self, fitted: ProteinView
    ) -> None:
        """
        Sampling can produce one family and not the other, and a heading with
        nothing under it would read as a result of zero rather than as no result.
        """
        fitted.ensemble_fit_prolate_summary = (["V = 1.0 nm"], "N=3 samples")
        fitted.ensemble_fit_oblate_summary = None

        fitted._report_ensemble_fit()
        text = self.reported(fitted)

        assert "<b>Prolate</b>" in text
        assert "Oblate" not in text
