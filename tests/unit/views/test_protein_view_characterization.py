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


class TestFitAndPlotEnsembleGeometry:
    """
    The orchestrator that chains the fit, the sampling and the summary.

    Also had zero references in ``tests/``. Its *numeric* content is already
    covered - ``_fit_and_sanity_check_double_gaussian`` and
    ``_generate_vm_ensemble`` each have direct tests of their own - so what is
    pinned here is the wiring: which branch returns ``False``, what the user is
    told, and which ``ensemble_fit_*`` attributes ``_report_ensemble_fit`` will
    later read back.

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

    def test_an_unfittable_histogram_returns_false_and_says_so(
        self, view: ProteinView, mocker, plot_data: pd.DataFrame
    ) -> None:
        """
        The first bail-out: no double Gaussian could be fitted.

        The user is told on the status panel rather than left with an unchanged
        plot and no explanation.
        """
        mocker.patch.object(
            view, "_fit_and_sanity_check_double_gaussian", return_value=None
        )

        assert (
            view._fit_and_plot_ensemble_geometry(plot_data, "Histogram", 10.0, 10.0, 50)
            is False
        )

        messages = [c.args[0] for c in view.add_text_to_display.emit.call_args_list]
        assert any("Unable to fit a double gaussian" in m for m in messages)

    def test_unphysical_geometry_returns_false_and_says_so(
        self, view: ProteinView, mocker, plot_data: pd.DataFrame
    ) -> None:
        """
        The second bail-out: the fit was fine but no sample satisfies the geometry.

        Both ensembles come back empty, which the sampler really does return when
        it hits its bail-out limits.
        """
        view.allowed_bins = 100
        view.allowed_sizes = False
        mocker.patch.object(view, "update_plot")
        mocker.patch.object(
            view,
            "_fit_and_sanity_check_double_gaussian",
            return_value=np.array([100.0, 0.15, 0.03, 60.0, 0.40, 0.04]),
        )
        mocker.patch.object(
            view,
            "_generate_vm_ensemble",
            return_value=(np.array([]), np.array([])),
        )

        assert (
            view._fit_and_plot_ensemble_geometry(plot_data, "Histogram", 10.0, 10.0, 50)
            is False
        )

        messages = [c.args[0] for c in view.add_text_to_display.emit.call_args_list]
        assert any("unphysical geometry" in m for m in messages)

    def test_a_successful_run_records_the_state_report_all_reads_back(
        self, view: ProteinView, mocker, plot_data: pd.DataFrame
    ) -> None:
        """
        The success path, pinned by the attributes it leaves behind.

        ``_report_ensemble_fit`` reads every one of these, and Step 4c moves the
        computation that produces them, so a wiring regression here would surface
        as an empty or stale report rather than as an exception.
        """
        view.allowed_bins = 75
        view.allowed_sizes = True
        popt = np.array([100.0, 0.15, 0.03, 60.0, 0.40, 0.04])
        mocker.patch.object(
            view, "_fit_and_sanity_check_double_gaussian", return_value=popt
        )
        mocker.patch.object(
            view,
            "_generate_vm_ensemble",
            return_value=(np.array([100.0, 200.0, 300.0]), np.array([2.0, 3.0, 4.0])),
        )
        update_plot = mocker.patch.object(view, "update_plot")

        assert (
            view._fit_and_plot_ensemble_geometry(plot_data, "Histogram", 10.0, 10.0, 3)
            is True
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

    def test_the_larger_fitted_peak_is_taken_as_the_maximum(
        self, view: ProteinView, mocker, plot_data: pd.DataFrame
    ) -> None:
        """
        The two Gaussians arrive in arbitrary order and are sorted by mean.

        Pinned because the sampler's ``mean_max``/``mean_min`` arguments are
        positional, so swapping them would silently invert the geometry rather
        than raise.
        """
        view.allowed_bins = 100
        view.allowed_sizes = False
        # deliberately given with the larger mean first
        popt = np.array([60.0, 0.40, -0.04, 100.0, 0.15, 0.03])
        mocker.patch.object(
            view, "_fit_and_sanity_check_double_gaussian", return_value=popt
        )
        sampler = mocker.patch.object(
            view,
            "_generate_vm_ensemble",
            return_value=(np.array([100.0]), np.array([2.0])),
        )
        mocker.patch.object(view, "update_plot")

        view._fit_and_plot_ensemble_geometry(plot_data, "Histogram", 10.0, 10.0, 1)

        _, mean_max, std_max, mean_min, std_min, _, _ = sampler.call_args_list[0].args
        assert mean_max == 0.40
        assert mean_min == 0.15
        # std is taken as an absolute value, so the negative sigma is normalised
        assert std_max == 0.04
        assert std_min == 0.03


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


class TestResolveEventDbIds:
    """
    The scoped event-id resolution, which is both a Step 4a and a Step 4b target.

    It authors SQL in the widget *and* uses the emit-then-read bus pattern twice,
    so it is moved by 4b and rewritten by 4a. The audit reported it as ``RUNS
    ONLY``: it executes in the protein e2e flow, but nothing named it, so neither
    the generated query nor the stale-read guards were pinned.

    The bus is stubbed the way the real one behaves - the emit sets the attribute
    named by its return-function argument - rather than as a bare ``Mock`` that
    silently does nothing. A stub that skips the side effect makes every assertion
    here vacuous, which is the trap ``_qt_mocks.py`` and the earlier
    ``_overlay_plot`` episode both record.
    """

    @pytest.fixture
    def bus(self, view: ProteinView):
        """
        Wire the view's global_signal to deliver results like the real dispatcher.

        :param view: the view under test
        :type view: ProteinView
        :return: a dict controlling what each dispatched call returns
        :rtype: dict
        """
        answers: dict = {
            "get_experiment_id_by_name": 7,
            "query_database_directly": None,
        }

        def deliver(metaclass, key, method, args, return_fn, extra):
            if return_fn == "set_experiment_id":
                view.experiment_id = answers["get_experiment_id_by_name"]
            elif return_fn == "relay_query_result":
                answers["last_query"] = args[0]
                view.relayed_query_result = answers["query_database_directly"]

        view.global_signal.emit.side_effect = deliver
        return answers

    def test_no_event_ids_short_circuits_before_any_query(
        self, view: ProteinView, bus: dict
    ) -> None:
        """An empty selection is not an error and must not reach the database."""
        assert view._resolve_event_db_ids("loader", [], "exp", 0) is None
        view.global_signal.emit.assert_not_called()

    def test_the_query_scopes_by_event_id_experiment_and_channel(
        self, view: ProteinView, bus: dict
    ) -> None:
        """
        All three clauses, in order.

        The scoping is the reason the method exists: ``event_id`` is unique only
        within an experiment and channel, so dropping either clause resolves to
        another channel's row.
        """
        bus["query_database_directly"] = pd.DataFrame({"id": [1], "event_id": [3]})

        view._resolve_event_db_ids("loader", [3, 4], "exp", 2)

        assert bus["last_query"] == (
            "SELECT id, event_id FROM events "
            "WHERE event_id IN (3,4) AND experiment_id = 7 AND channel_id = 2"
        )

    def test_the_experiment_id_is_cleared_before_it_is_requested(
        self, view: ProteinView, bus: dict
    ) -> None:
        """
        The stale-read guard.

        A failed dispatch never calls the return function, so without the pre-clear
        the method would silently reuse the *previous* experiment's id and scope the
        query to the wrong experiment. Simulated by a bus that delivers nothing.
        """
        view.experiment_id = 99
        bus["query_database_directly"] = pd.DataFrame({"id": [1], "event_id": [3]})
        view.global_signal.emit.side_effect = lambda *a, **k: None

        view._resolve_event_db_ids("loader", [3], "exp", None)

        assert view.experiment_id is None

    def test_a_failed_experiment_lookup_omits_the_clause_entirely(
        self, view: ProteinView, bus: dict
    ) -> None:
        """
        Rather than emitting ``experiment_id = None`` into the SQL.

        The query is then wider than intended, which is a real behaviour worth
        knowing about, but it is not malformed.
        """
        captured: dict = {}

        def deliver(metaclass, key, method, args, return_fn, extra):
            if return_fn == "relay_query_result":
                captured["query"] = args[0]
                view.relayed_query_result = pd.DataFrame({"id": [1]})

        view.global_signal.emit.side_effect = deliver

        view._resolve_event_db_ids("loader", [3], "exp", 5)

        assert "experiment_id" not in captured["query"]
        assert "channel_id = 5" in captured["query"]

    def test_no_experiment_means_no_lookup_at_all(
        self, view: ProteinView, bus: dict
    ) -> None:
        """A ``None`` experiment skips the first bus round trip."""
        bus["query_database_directly"] = pd.DataFrame({"id": [1]})

        view._resolve_event_db_ids("loader", [3], None, 1)

        methods = [c.args[2] for c in view.global_signal.emit.call_args_list]
        assert "get_experiment_id_by_name" not in methods

    def test_the_result_is_cleared_before_the_query(
        self, view: ProteinView, bus: dict
    ) -> None:
        """The same guard on the second round trip, and the reason it returns None."""
        view.relayed_query_result = pd.DataFrame({"id": [42]})
        view.global_signal.emit.side_effect = lambda *a, **k: None

        assert view._resolve_event_db_ids("loader", [3], None, None) is None

    @pytest.mark.parametrize(
        "result",
        [None, pd.DataFrame(), pd.DataFrame({"event_id": [1]})],
        ids=["none", "empty", "missing id column"],
    )
    def test_an_unusable_result_becomes_none(
        self, view: ProteinView, bus: dict, result
    ) -> None:
        """
        Three distinct failures collapse to one answer.

        Pinned because the caller only checks for ``None``, so a merge that let an
        empty frame through would break it in a way no type checker would catch.
        """
        bus["query_database_directly"] = result

        assert view._resolve_event_db_ids("loader", [3], None, None) is None

    def test_a_good_result_is_returned_unchanged(
        self, view: ProteinView, bus: dict
    ) -> None:
        """The frame is passed straight back; no reshaping happens here."""
        frame = pd.DataFrame({"id": [10, 11], "event_id": [3, 4]})
        bus["query_database_directly"] = frame

        assert view._resolve_event_db_ids("loader", [3, 4], None, None) is frame


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
