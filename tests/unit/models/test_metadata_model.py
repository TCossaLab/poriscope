"""
Unit-test suite for MetadataModel.

MetadataModel was a minimal MetaModel subclass with a no-op ``_init()``. **It now
holds the metadata tab's binning and fitting**, moved off MetadataView so that
``scipy``, ``scipy.optimize`` and ``scipy.stats`` leave the View layer.

The two bin-count rules are pinned here before any caller moves onto them, because
``MetadataView`` held **four** copies of the Freedman-Diaconis calculation in one
file - a shape the duplication ratchet cannot see, since it only compares bodies
*across* files in a family.

**The two rules are not duplicates of each other and must not be unified.** The
exponent is ``1 / (2 + D)`` for ``D`` binning dimensions: a cube root for a 1-D
histogram, a fourth root for a 2-D heatmap. The tests below assert each against its
own formula precisely so that collapsing them would fail.
"""

import numpy as np
import pandas as pd
import pytest

from poriscope.plugins.analysistabs.MetadataModel import MetadataModel
from poriscope.utils.MetaModel import MetaModel


@pytest.fixture
def model():
    """
    A MetadataModel to compute with.

    :return: a constructed MetadataModel
    :rtype: MetadataModel
    """
    return MetadataModel()


# ===========================================================================
# Construction / inheritance
# ===========================================================================


class TestConstruction:
    def test_instantiates_without_error(self, model):
        assert model is not None

    def test_is_instance_of_meta_model(self, model):
        assert isinstance(model, MetaModel)

    def test_init_returns_none(self, model):
        assert model._init() is None


# ===========================================================================
# _auto_bins_1d - the rule the density, histogram and capture-rate paths share
# ===========================================================================


class TestAutoBins1d:
    """The Freedman-Diaconis bin count, cube-root form."""

    def test_matches_the_freedman_diaconis_expression(self, model):
        """
        Asserted against the formula rather than a recorded number.

        A golden here would pass just as happily against the fourth-root form, and
        the exponent is the one thing that must stay ``1 / (2 + D)``.
        """
        from scipy.stats import iqr

        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 13.0, 21.0])
        expected = int(
            (np.max(data) - np.min(data)) * len(data) ** (1.0 / 3.0) / iqr(data)
        )

        assert model._auto_bins_1d(data) == expected

    def test_a_zero_interquartile_range_falls_back_to_sturges(self, model):
        """
        Every value identical means no spread to divide by, so the count comes from
        the sample size alone.
        """
        data = np.array([5.0] * 40)

        assert model._auto_bins_1d(data) == int(3.332 * np.log10(len(data)))

    def test_the_fallback_is_not_the_two_dimensional_one(self, model):
        """
        The 1-D and 2-D degenerate fallbacks differ, and this is the assertion that
        fails if someone unifies the two rules.
        """
        data = np.array([5.0] * 40)

        assert model._auto_bins_1d(data) != int(np.sqrt(len(data)))


# ===========================================================================
# _auto_bins_2d - the heatmap's rule, which differs in two places
# ===========================================================================


class TestAutoBins2d:
    """The heatmap's bin count: fourth root, square-root fallback."""

    def test_uses_a_fourth_root_not_a_cube_root(self, model):
        """
        Two binning dimensions, so ``1 / (2 + 2)``.

        Not a divergence from the 1-D rule but the same rule at D = 2; this is the
        assertion that fails if the heatmap is quietly given a cube root.
        """
        from scipy.stats import iqr

        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 13.0, 21.0])
        expected = int(
            (np.max(data) - np.min(data)) * len(data) ** (1.0 / 4.0) / iqr(data)
        )

        assert model._auto_bins_2d(data, len(data)) == expected

    def test_a_zero_interquartile_range_falls_back_to_the_square_root(self, model):
        """The degenerate fallback differs from the 1-D one, and is pinned as-is."""
        data = np.array([5.0] * 40)

        assert model._auto_bins_2d(data, len(data)) == int(np.sqrt(len(data)))

    def test_the_count_is_taken_from_the_argument_not_from_the_data(self, model):
        """
        The heatmap's y-axis calculation raises the **x** array's length to the
        fourth power, not the y array's.

        Inert in the application, because the filter that runs first masks both
        arrays jointly and they are always the same length. Pinned rather than
        quietly corrected, so that the move changes nothing and the oddity stays
        visible to whoever decides about it.
        """
        data = np.array([1.0, 2.0, 3.0, 4.0])

        assert model._auto_bins_2d(data, 4) != model._auto_bins_2d(data, 100000)


# ===========================================================================
# calculate_heatmap - pins moved from test_metadata_view.py with the method
# ===========================================================================


class TestCalculateHeatmap:
    """
    The 2-D binning, moved off MetadataView with its tests.

    These are the pins that predate the move: their passing here against
    ``MetadataModel`` is what says the computation is unchanged. Each lost the
    ``_logscale_and_filter_multiple_columns`` mock it used to need, because the
    Model is handed arrays the View has already filtered.
    """

    def test_returns_three_arrays(self, model):
        """Verify calculate_heatmap returns x, y, z arrays."""
        xdata = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        ydata = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

        x, y, z = model.calculate_heatmap(xdata, ydata, [5], False)

        assert len(x) == 5
        assert len(y) == 5
        assert z.shape == (5, 5)

    def test_uses_different_bins_for_x_and_y(self, model):
        """Verify different bin counts can be specified for x and y."""
        xdata = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        ydata = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

        x, y, z = model.calculate_heatmap(xdata, ydata, [3, 5], False)

        assert z.shape == (5, 3)  # Note: transposed, so y bins first

    def test_calculates_bin_sizes_when_sizes_true(self, model):
        """Verify bin sizes are calculated when sizes=True."""
        xdata = np.array([0.0, 10.0, 20.0, 30.0])
        ydata = np.array([0.0, 10.0, 20.0, 30.0])

        x, y, z = model.calculate_heatmap(xdata, ydata, [5.0], True)

        # (30 - 0) / 5.0 = 6 bins per axis
        assert z.shape[0] == 6
        assert z.shape[1] == 6

    def test_raises_for_invalid_bins(self, model):
        """Verify ValueError is raised for empty bins list."""
        xdata = np.array([1.0, 2.0, 3.0])
        ydata = np.array([10.0, 20.0, 30.0])

        with pytest.raises(ValueError, match="Invalid bin entry"):
            model.calculate_heatmap(xdata, ydata, [], False)

    def test_defaults_to_iqr_when_bins_none(self, model, mocker):
        """
        Verify IQR-based bin calculation when bins=None.

        The patch target moved with the method - it names the module that
        *imported* ``iqr``, which is now the Model's.
        """
        xdata = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        ydata = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        mocker.patch(
            "poriscope.plugins.analysistabs.MetadataModel.iqr", return_value=2.0
        )

        x, y, z = model.calculate_heatmap(xdata, ydata, None, False)

        assert z.shape[0] > 0
        assert z.shape[1] > 0

    def test_applies_log2_to_counts(self, model):
        """Verify counts are log2 transformed."""
        xdata = np.array([1.0, 1.0, 2.0, 2.0])
        ydata = np.array([10.0, 10.0, 20.0, 20.0])

        x, y, z = model.calculate_heatmap(xdata, ydata, [2], False)

        # All non-zero entries should be log2 transformed
        assert np.all((z == -1) | (z >= 0))  # -1 for zero counts, >=0 for others


# ===========================================================================
# _resolve_1d_bins - the explicit-or-automatic decision the 1-D paths share
# ===========================================================================


class TestResolve1dBins:
    """
    Rewritten from seven tests in ``test_metadata_view.py``.

    Those drove every branch of this decision through ``_plot_1d_density`` and then
    asserted ``assert view.hist_data`` - that the dataset had been appended, which
    is true whatever bin count came out. The branches had coverage and the numbers
    had none. Moving the logic somewhere it can return a value is what makes them
    assertable, so they are rewritten here rather than re-pointed.
    """

    def test_an_explicit_count_is_used_as_given(self, model):
        """``sizes`` False means ``bins`` is already the count."""
        data = np.array([1.0, 2.0, 3.0, 4.0])

        assert model._resolve_1d_bins(data, 6, False, 0.0, 10.0) == 6

    def test_a_bin_width_is_divided_into_the_shared_span(self, model):
        """
        The span comes from the shared limits, not from this dataset, which is what
        keeps overlaid datasets on comparable bins.
        """
        data = np.array([1.0, 2.0, 3.0, 4.0])

        assert model._resolve_1d_bins(data, 2.0, True, 0.0, 10.0) == 5

    def test_a_bin_width_without_shared_limits_falls_back_to_automatic(self, model):
        """No span to divide, so the data decides."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 9.0, 16.0])

        assert model._resolve_1d_bins(
            data, 2.0, True, None, None
        ) == model._auto_bins_1d(data)

    def test_a_non_numeric_bin_width_falls_back_to_automatic(self, model):
        """The ``TypeError`` branch: a width that cannot divide the span."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 9.0, 16.0])

        assert model._resolve_1d_bins(
            data, "wide", True, 0.0, 10.0
        ) == model._auto_bins_1d(data)

    def test_a_width_yielding_one_bin_or_fewer_falls_back_to_automatic(self, model):
        """A width as wide as the span is not a binning, so it is discarded."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 9.0, 16.0])

        assert model._resolve_1d_bins(
            data, 20.0, True, 0.0, 10.0
        ) == model._auto_bins_1d(data)

    def test_no_bins_request_uses_the_automatic_rule(self, model):
        """The ordinary path, and the one every plot takes by default."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 9.0, 16.0])

        assert model._resolve_1d_bins(
            data, None, False, 0.0, 10.0
        ) == model._auto_bins_1d(data)

    def test_an_overflow_in_the_automatic_rule_falls_back_to_one_hundred(
        self, model, mocker
    ):
        """
        The density and histogram paths answer an overflow with 100 bins; the
        capture-rate path answers it differently, which is why `_auto_bins_1d` does
        not handle it itself.
        """
        mocker.patch.object(model, "_auto_bins_1d", side_effect=OverflowError)
        data = np.array([1.0, 2.0, 3.0, 4.0])

        assert model._resolve_1d_bins(data, None, False, 0.0, 10.0) == 100


# ===========================================================================
# fit_capture_rate - pins moved from test_metadata_view.py with the method
# ===========================================================================


class TestFitCaptureRate:
    """
    The capture-rate binning and exponential fit, moved off MetadataView.

    The two bin-fallback tests came with the rule they exercise: they patched
    ``MetadataView.iqr``, and ``mock.patch`` names the module that imported the
    symbol, so the target moved too. Both now assert the bin count
    the fallback produces, which the View-side versions could not - there the count
    was only visible as a keyword handed to ``ax.hist``.
    """

    @pytest.fixture
    def log_times(self):
        """
        Log inter-event times of the shape the capture-rate path consumes.

        :return: the base-10 logarithm of a set of inter-event times
        :rtype: np.ndarray
        """
        rng = np.random.default_rng(11)
        # Arrival times are the cumulative sum, so diffing them gives the
        # exponential gaps. Diffing the draws themselves would give order-statistic
        # spacings instead, which are far shorter and describe nothing physical.
        arrivals = np.cumsum(rng.exponential(scale=0.02, size=2000))
        gaps = np.diff(np.sort(arrivals))
        return np.log10(gaps[gaps > 0])

    def test_an_explicit_bin_count_is_used_as_given(self, model, log_times):
        """A count from the controls is passed through to the binning."""
        edges, centers, counts, fit, rate, error = model.fit_capture_rate(log_times, 4)

        assert len(centers) == 4
        assert len(edges) == 5
        assert len(counts) == 4
        assert len(fit) == 4

    def test_a_zero_interquartile_range_falls_back_to_sturges(self, model, mocker):
        """Verify zero-IQR capture-rate data uses the fallback bin estimator."""
        mocker.patch(
            "poriscope.plugins.analysistabs.MetadataModel.iqr", return_value=0.0
        )
        data = np.linspace(1.0, 1.11, 40)

        edges, centers, *_ = model.fit_capture_rate(data, None)

        assert len(centers) == int(3.332 * np.log10(len(data)))

    def test_an_overflow_falls_back_to_sturges_too(self, model, mocker):
        """
        Verify OverflowError in the primary estimator falls back to log-length bins.

        **This path answers an overflow differently from the density and histogram
        paths**, which use 100 bins, and that is the reason it does not share
        ``_resolve_1d_bins``. The assertion is what would fail if it were unified.
        """
        mocker.patch.object(model, "_auto_bins_1d", side_effect=OverflowError)
        data = np.linspace(1.0, 1.11, 40)

        edges, centers, *_ = model.fit_capture_rate(data, None)

        assert len(centers) == int(3.332 * np.log10(len(data)))
        assert len(centers) != 100

    def test_the_rate_is_recovered_from_a_known_distribution(self, model, log_times):
        """
        The fit is exercised for real rather than stubbed.

        The View-side tests all replaced ``curve_fit`` with a canned answer, so
        nothing anywhere asserted that the capture rate came back near the rate the
        data was drawn with. A scale of 0.02 s is 50 Hz.
        """
        _edges, _centers, _counts, _fit, rate, error = model.fit_capture_rate(
            log_times, None
        )

        assert rate == pytest.approx(50.0, rel=0.1)
        assert error != 0.0


# ===========================================================================
# kernel_densities - the per-dataset loop moved off the View
# ===========================================================================


class TestKernelDensities:
    """
    One ``(positions, density)`` pair per dataset, index-aligned with the input.

    The density plot redraws every accumulated dataset on each update, so the loop
    lives here rather than round-tripping per dataset and parking each answer on the
    widget. These tests exist because the method had **no test naming it** - its body
    ran under the e2e suite with nothing asserting what it returned.
    """

    def test_returns_one_pair_per_dataset(self, model):
        datasets = [
            np.linspace(0.0, 1.0, 40),
            np.linspace(0.0, 2.0, 60),
            np.linspace(0.0, 3.0, 80),
        ]

        result = model.kernel_densities(datasets, None, False, None, None)

        assert len(result) == 3
        assert all(len(pair) == 2 for pair in result)

    def test_each_pair_equals_the_single_dataset_call(self, model):
        """
        The loop is the whole method, so the contract is that it delegates unchanged.

        Asserted against ``kernel_density`` rather than against recorded numbers: a
        golden here would go on passing if the loop started dropping an argument.
        """
        datasets = [np.linspace(0.0, 1.0, 40), np.linspace(-2.0, 2.0, 50)]

        result = model.kernel_densities(datasets, 12, False, -2.0, 2.0)

        for data, (positions, density) in zip(datasets, result, strict=True):
            expected_positions, expected_density = model.kernel_density(
                data, 12, False, -2.0, 2.0
            )
            np.testing.assert_allclose(positions, expected_positions)
            np.testing.assert_allclose(density, expected_density)

    def test_the_order_is_the_input_order(self, model):
        """
        The caller indexes the answers against its own dataset list, so a reordering
        would mislabel every curve without failing anything else.
        """
        narrow = np.linspace(0.0, 1.0, 40)
        wide = np.linspace(0.0, 100.0, 40)

        (narrow_positions, _), (wide_positions, _) = model.kernel_densities(
            [narrow, wide], None, False, None, None
        )

        assert narrow_positions.max() < wide_positions.max()

    def test_no_datasets_returns_no_pairs(self, model):
        assert model.kernel_densities([], None, False, None, None) == []


# ===========================================================================
# histogram_bin_edges - one set of edges for every overlaid dataset
# ===========================================================================


class TestHistogramBinEdges:
    """
    The edges span the shared limits, which is what puts overlaid datasets on
    comparable bins. Added with ``kernel_densities`` for the same reason.
    """

    def test_edges_span_the_shared_limits(self, model):
        data = np.linspace(0.0, 10.0, 100)

        edges, _centers, _widths = model.histogram_bin_edges(data, 8, False, 0.0, 10.0)

        assert edges[0] == pytest.approx(0.0)
        assert edges[-1] == pytest.approx(10.0)

    def test_an_explicit_count_decides_the_number_of_bins(self, model):
        data = np.linspace(0.0, 10.0, 100)

        edges, centers, widths = model.histogram_bin_edges(data, 8, False, 0.0, 10.0)

        assert len(edges) == 9
        assert len(centers) == 8
        assert len(widths) == 8

    def test_centers_sit_midway_between_edges(self, model):
        data = np.linspace(0.0, 10.0, 100)

        edges, centers, _widths = model.histogram_bin_edges(data, 5, False, 0.0, 10.0)

        np.testing.assert_allclose(centers, (edges[:-1] + edges[1:]) / 2.0)

    def test_widths_are_the_gaps_between_edges(self, model):
        data = np.linspace(0.0, 10.0, 100)

        edges, _centers, widths = model.histogram_bin_edges(data, 5, False, 0.0, 10.0)

        np.testing.assert_allclose(widths, np.diff(edges))

    def test_a_single_bin_is_raised_to_two(self, model):
        """
        A single bin is not a histogram and zero makes ``linspace`` degenerate, so
        the method floors the count. Pinned because the floor is invisible from the
        caller - it asks for one bin and silently gets two.
        """
        data = np.linspace(0.0, 10.0, 100)

        edges, centers, widths = model.histogram_bin_edges(data, 1, False, 0.0, 10.0)

        assert len(centers) == 2
        assert len(edges) == 3
        assert len(widths) == 2

    def test_a_bin_width_is_divided_into_the_shared_span(self, model):
        """``sizes=True`` makes the second argument a width rather than a count."""
        data = np.linspace(0.0, 10.0, 100)

        _edges, centers, _widths = model.histogram_bin_edges(data, 2.0, True, 0.0, 10.0)

        assert len(centers) == 5


# ===========================================================================
# _log_exp_pdf - the model curve_fit is handed
# ===========================================================================


class TestLogExpPdf:
    """
    Capture is Poisson, so inter-event times are exponential; binning their base-10
    logarithm carries a Jacobian of ``ln(10) * 10**logt``. That factor is the whole
    reason this function is not just an exponential, and it is what these assert.
    """

    def test_matches_the_closed_form(self, model):
        logt = np.linspace(-3.0, 1.0, 25)

        result = model._log_exp_pdf(logt, rate=50.0, amplitude=2.0)

        expected = 2.0 * np.exp(-50.0 * 10.0**logt) * 10.0**logt * np.log(10)
        np.testing.assert_allclose(result, expected)

    def test_the_jacobian_factor_is_present(self, model):
        """
        Asserted separately, because dropping ``10**logt * ln(10)`` still leaves a
        plausible decaying curve that a shape-only assertion would accept.

        At ``logt = 0`` the time is 1 s and the factor is exactly ``ln(10)``.
        """
        value = model._log_exp_pdf(np.array([0.0]), rate=1.0, amplitude=1.0)[0]

        assert value == pytest.approx(np.exp(-1.0) * np.log(10))
        assert value != pytest.approx(np.exp(-1.0))

    def test_amplitude_scales_the_curve_linearly(self, model):
        logt = np.linspace(-2.0, 1.0, 10)

        single = model._log_exp_pdf(logt, rate=10.0, amplitude=1.0)
        triple = model._log_exp_pdf(logt, rate=10.0, amplitude=3.0)

        np.testing.assert_allclose(triple, 3.0 * single)

    def test_the_shape_matches_the_input(self, model):
        logt = np.linspace(-2.0, 2.0, 17)

        assert model._log_exp_pdf(logt, 1.0, 1.0).shape == logt.shape


# ===========================================================================
# resolve_event_ids / load_events_by_id - the SQL moved down from the Views
# ===========================================================================
#
# These assert on the **exact query text** handed to the loader, not on substring
# containment. All 110 tests in test_meta_database_loader.py used containment, so a
# refactor could reorder a clause and every one would still pass; the builder's
# goldens fixed that for the builder and these extend it to these two methods.
#
# The stubbed ``call`` answers from MetaDatabaseLoader's declared return types -
# ``Optional[pd.DataFrame]`` for query_database_directly, a generator for
# load_event_data - rather than from whatever the method happens to do with them.


class TestResolveEventIds:
    """
    The scope is why this query exists: ``event_id`` is unique only within an
    experiment and channel, so an unscoped match returns whichever channel's row
    happens to share the number. Three unscoped-query faults of exactly this family
    have been found, which is why every combination is pinned here.
    """

    def _query(self, model, mocker, event_ids, exp_id, channel):
        """
        Run the method against a stubbed loader and return the SQL it authored.

        :param model: the model under test
        :type model: MetadataModel
        :param mocker: the pytest-mock fixture
        :type mocker: pytest_mock.MockerFixture
        :param event_ids: the event_id values to resolve
        :type event_ids: list
        :param exp_id: the experiment's database id, or None
        :type exp_id: object
        :param channel: the channel to scope to, or None
        :type channel: object
        :return: the query string passed to the loader
        :rtype: str
        """
        call = mocker.patch.object(model, "call", return_value=pd.DataFrame())
        model.resolve_event_ids("L", event_ids, exp_id, channel)
        return call.call_args.args[3]

    def test_projects_id_only(self, model, mocker):
        """
        Metadata asks for ``id`` alone; the protein tab asks for ``id, event_id``
        because its caller re-sorts the rows. The difference is load-bearing and a
        promotion that merged the two would have to keep it.
        """
        query = self._query(model, mocker, [7], None, None)

        assert query == "SELECT id FROM events WHERE event_id IN (7)"

    def test_an_experiment_narrows_the_scope(self, model, mocker):
        query = self._query(model, mocker, [7, 9], 3, None)

        assert query == (
            "SELECT id FROM events WHERE event_id IN (7,9) AND experiment_id = 3"
        )

    def test_a_channel_narrows_the_scope(self, model, mocker):
        query = self._query(model, mocker, [7], None, 2)

        assert query == (
            "SELECT id FROM events WHERE event_id IN (7) AND channel_id = 2"
        )

    def test_both_scopes_are_applied_in_order(self, model, mocker):
        query = self._query(model, mocker, [7], 3, 2)

        assert query == (
            "SELECT id FROM events WHERE event_id IN (7) "
            "AND experiment_id = 3 AND channel_id = 2"
        )

    def test_the_call_is_routed_to_the_named_loader(self, model, mocker):
        call = mocker.patch.object(model, "call", return_value=pd.DataFrame())

        model.resolve_event_ids("SQLiteDBLoader_0", [1], None, None)

        metaclass, key, method, _query = call.call_args.args
        assert (metaclass, key, method) == (
            "MetaDatabaseLoader",
            "SQLiteDBLoader_0",
            "query_database_directly",
        )

    def test_the_loaders_answer_is_returned_unchanged(self, model, mocker):
        frame = pd.DataFrame({"id": [11, 12]})
        mocker.patch.object(model, "call", return_value=frame)

        assert model.resolve_event_ids("L", [1, 2], None, None) is frame

    def test_a_failed_query_comes_back_as_none(self, model, mocker):
        """``query_database_directly`` returns None when the query could not run."""
        mocker.patch.object(model, "call", return_value=None)

        assert model.resolve_event_ids("L", [1], None, None) is None


class TestLoadEventsById:
    """``e.id IN (...)`` is a WHERE-clause body, which is what load_event_data takes."""

    def test_builds_a_where_clause_body_not_a_select(self, model, mocker):
        """
        A complete ``SELECT`` here is the shape that made the protein tab's raw
        filter branch never return a row - the loader splices this in after its own
        ``WHERE``.
        """
        call = mocker.patch.object(model, "call", return_value=iter(()))

        model.load_events_by_id("L", "3,4,5", None)

        conditions = call.call_args.args[3]
        assert conditions == "e.id IN (3,4,5)"
        assert "SELECT" not in conditions

    def test_the_scope_is_passed_through_untouched(self, model, mocker):
        call = mocker.patch.object(model, "call", return_value=iter(()))
        scope = {"exp_a": [2]}

        model.load_events_by_id("L", "3", scope)

        assert call.call_args.args[4] is scope

    def test_the_call_is_routed_to_load_event_data(self, model, mocker):
        call = mocker.patch.object(model, "call", return_value=iter(()))

        model.load_events_by_id("SQLiteDBLoader_0", "3", None)

        assert call.call_args.args[:3] == (
            "MetaDatabaseLoader",
            "SQLiteDBLoader_0",
            "load_event_data",
        )

    def test_the_generator_is_returned_unchanged(self, model, mocker):
        generator = iter([{"data": [1.0]}])
        mocker.patch.object(model, "call", return_value=generator)

        assert model.load_events_by_id("L", "3", None) is generator


# ===========================================================================
# interevent_log_times - the gaps the capture-rate fit is actually about
# ===========================================================================


class TestIntereventLogTimes:
    """
    Capture is Poisson, so the fit is about the gap between consecutive events
    rather than the times themselves. Moved off ``MetadataView`` because the gaps
    are the measurement, not the drawing.
    """

    def test_it_returns_the_log_of_the_gaps(self, model):
        """Times one decade apart give gaps of 9, 90, 900 - logs just under 1, 2, 3."""
        times = np.array([1.0, 10.0, 100.0, 1000.0])

        result = model.interevent_log_times(times)

        np.testing.assert_allclose(result, np.log10([9.0, 90.0, 900.0]))

    def test_the_column_is_sorted_first(self, model):
        """
        A column arrives in whatever order the query returned it, and unsorted gaps
        are meaningless - some would be negative and silently dropped below.
        """
        ordered = model.interevent_log_times(np.array([1.0, 2.0, 4.0, 8.0]))
        shuffled = model.interevent_log_times(np.array([4.0, 1.0, 8.0, 2.0]))

        np.testing.assert_allclose(ordered, shuffled)

    def test_there_is_one_fewer_gap_than_event(self, model):
        """
        The property behind the message a clean column still shows: n events make
        n-1 intervals, and the caller counts that difference as dropped rows.
        """
        assert len(model.interevent_log_times(np.arange(20.0))) == 19

    def test_a_repeated_timestamp_is_dropped(self, model):
        """
        Two events sharing a time produce a zero gap, which log10 has nothing to say
        about - it would be -inf and poison the fit.
        """
        times = np.array([1.0, 2.0, 2.0, 4.0])

        result = model.interevent_log_times(times)

        assert len(result) == 2
        assert np.all(np.isfinite(result))

    def test_every_timestamp_repeated_gives_nothing(self, model):
        assert len(model.interevent_log_times(np.full(5, 3.0))) == 0

    def test_a_single_event_gives_no_intervals(self, model):
        assert len(model.interevent_log_times(np.array([1.0]))) == 0

    def test_no_events_gives_no_intervals(self, model):
        assert len(model.interevent_log_times(np.array([]))) == 0


# ===========================================================================
# categorical_counts - the tallying moved off the View
# ===========================================================================


class TestCategoricalCounts:
    """
    One (categories, counts) pair per overlaid dataset.

    These three came from ``test_metadata_view.py`` with the method: they were
    written against real reported defects, and they assert what the counting
    produces rather than that a bar was drawn, so they belong beside the counting.
    """

    def test_it_counts_each_category(self, model):
        values = np.array(["A", "B", "A", "C", "B", "A"], dtype=object)

        (categories, counts) = model.categorical_counts([values])[0]

        assert categories == ["A", "B", "C"]
        assert list(counts) == [3.0, 2.0, 1.0]

    def test_nulls_are_counted_as_their_own_category(self, model):
        """
        A column holding SQL NULLs must plot, with the missing rows as a "null" bar.

        Reported from a real run: it raised instead. ``np.unique`` sorts, and sorting
        an object column mixing ``None`` with strings raises "'<' not supported
        between instances of 'NoneType' and 'str'".
        """
        values = np.array(["a", "b", None, "a"], dtype=object)

        (categories, counts) = model.categorical_counts([values])[0]

        assert categories == ["a", "b", "null"]
        assert list(counts) == [2.0, 1.0, 1.0]

    def test_a_float_nan_is_labelled_null_too(self, model):
        """
        A float column does not raise on NaN but labelled the bar "nan". "null" is
        what the user sees everywhere else for a missing value, and this is the same
        absence, so it gets the same word.
        """
        values = np.array([1.0, 2.0, np.nan, 1.0])

        (categories, _counts) = model.categorical_counts([values])[0]

        assert categories[-1] == "null"
        assert "nan" not in categories

    def test_the_tallest_bar_comes_first(self, model):
        """
        Requested by a user: the bars read largest on the left, smallest on the
        right, rather than in whatever order the categories happened to sort into.
        """
        values = np.array(["A", "B", "B", "C", "C", "C"], dtype=object)

        (categories, counts) = model.categorical_counts([values])[0]

        assert categories == ["C", "B", "A"]
        assert list(counts) == [3.0, 2.0, 1.0]

    def test_overlaid_datasets_share_one_order(self, model):
        """
        The order is decided from the total across every dataset, not per dataset.

        Matplotlib takes a category axis's order from the first series drawn, so
        ordering each dataset by its own counts would leave the second one's bars
        under the first one's headings and only the first looking sorted. Here "B"
        wins on the total while losing inside the first dataset.
        """
        first = np.array(["A", "A", "B"], dtype=object)
        second = np.array(["B", "B", "B"], dtype=object)

        results = model.categorical_counts([first, second])

        assert [cats for cats, _ in results] == [["B", "A"], ["B"]]
        assert [list(counts) for _, counts in results] == [[1.0, 2.0], [3.0]]

    def test_numeric_categories_keep_numeric_order_on_a_tie(self, model):
        """
        Real categories are counted apart from nulls so that they keep their own
        order; stringifying the whole column before ``np.unique`` would have been
        shorter and would have sorted 10 before 2. Count ordering is stable, so
        that order is what survives a tie - here 1 and 10, both counted once.
        """
        values = np.array([1, 2, 10, 2])

        (categories, _counts) = model.categorical_counts([values])[0]

        assert categories == ["2", "1", "10"]

    def test_one_pair_per_dataset_in_order(self, model):
        """The bar chart redraws every accumulated dataset, index-aligned with labels."""
        first = np.array(["A", "A"], dtype=object)
        second = np.array(["B"], dtype=object)

        results = model.categorical_counts([first, second])

        assert [cats for cats, _ in results] == [["A"], ["B"]]
        assert [list(counts) for _, counts in results] == [[2.0], [1.0]]

    def test_a_column_of_only_nulls_is_all_null(self, model):
        values = np.array([None, None], dtype=object)

        (categories, counts) = model.categorical_counts([values])[0]

        assert categories == ["null"]
        assert list(counts) == [2.0]

    def test_no_datasets_gives_no_results(self, model):
        assert model.categorical_counts([]) == []


# ===========================================================================
# overlaid_histograms - the counting that joined the bin decision
# ===========================================================================


class TestOverlaidHistograms:
    """
    Shared edges from all the data at once, then one count array per dataset.

    The bin decision moved down because it needed ``scipy.stats.iqr``; the counting
    followed, on the grounds that which import a move frees is a different question
    from whose responsibility the work is.
    """

    def test_one_count_array_per_dataset(self, model):
        datasets = [np.array([1.0, 2.0]), np.array([2.0, 3.0]), np.array([1.5])]

        _edges, _centers, _widths, counts = model.overlaid_histograms(
            datasets, 4, False, 1.0, 3.0, False
        )

        assert len(counts) == 3

    def test_every_dataset_is_counted_on_the_same_edges(self, model):
        """
        The point of deciding the edges from all the data at once: two datasets are
        only comparable if their bars line up.
        """
        datasets = [np.array([1.0, 1.1]), np.array([2.9, 3.0])]

        _edges, _centers, _widths, counts = model.overlaid_histograms(
            datasets, 4, False, 1.0, 3.0, False
        )

        assert len({len(c) for c in counts}) == 1
        assert sum(counts[0]) == 2.0
        assert sum(counts[1]) == 2.0

    def test_the_counts_land_in_the_right_bins(self, model):
        """Two values at the bottom of the range and one at the top."""
        datasets = [np.array([1.0, 1.0, 3.0])]

        _edges, _centers, _widths, counts = model.overlaid_histograms(
            datasets, 2, False, 1.0, 3.0, False
        )

        assert list(counts[0]) == [2.0, 1.0]

    def test_normalising_gives_fractions_of_each_dataset(self, model):
        """
        Each dataset is normalised against *itself*, not against the overlay, so two
        datasets of different size are still comparable in shape.
        """
        datasets = [np.array([1.0, 1.0, 3.0]), np.array([1.0, 3.0])]

        _edges, _centers, _widths, counts = model.overlaid_histograms(
            datasets, 2, False, 1.0, 3.0, True
        )

        np.testing.assert_allclose(counts[0], [2 / 3, 1 / 3])
        np.testing.assert_allclose(counts[1], [0.5, 0.5])

    def test_an_all_empty_dataset_does_not_divide_by_zero(self, model):
        """A dataset entirely outside the shared limits counts zero everywhere."""
        datasets = [np.array([99.0, 99.0])]

        _edges, _centers, _widths, counts = model.overlaid_histograms(
            datasets, 2, False, 1.0, 3.0, True
        )

        assert list(counts[0]) == [0.0, 0.0]

    def test_the_edges_come_from_every_dataset_together(self, model):
        """
        A single dataset must not be concatenated differently from several - the
        one-dataset case skips ``np.concatenate``, and the two must agree.
        """
        one = model.overlaid_histograms(
            [np.array([1.0, 2.0, 3.0])], None, False, 1.0, 3.0, False
        )
        split = model.overlaid_histograms(
            [np.array([1.0, 2.0]), np.array([3.0])], None, False, 1.0, 3.0, False
        )

        np.testing.assert_allclose(one[0], split[0])

    def test_the_centers_and_widths_match_the_edges(self, model):
        edges, centers, widths, _counts = model.overlaid_histograms(
            [np.array([1.0, 2.0, 3.0])], 4, False, 1.0, 3.0, False
        )

        np.testing.assert_allclose(centers, (edges[:-1] + edges[1:]) / 2.0)
        np.testing.assert_allclose(widths, np.diff(edges))


# ===========================================================================
# _rectify_event_current - the baseline subtraction all three event paths share
# ===========================================================================


class TestRectifyEventCurrent:
    """
    Previously three byte-identical copies in ``MetadataView``.

    The sign factor is the part worth pinning: without it a negative-baseline
    recording's blockages come out negative and cannot share a histogram with a
    positive-baseline one.
    """

    def test_a_positive_baseline_leaves_a_blockage_negative_going(self, model):
        timeseries = np.array([10.0, 10.0, 10.0, 4.0])

        result = model._rectify_event_current(timeseries, 3)

        assert list(result) == [0.0, 0.0, 0.0, -6.0]

    def test_a_negative_baseline_reads_the_same_way(self, model):
        """
        The two polarities must produce the same numbers, which is the whole point
        of multiplying through by the baseline's sign.
        """
        positive = model._rectify_event_current(np.array([10.0, 10.0, 10.0, 4.0]), 3)
        negative = model._rectify_event_current(
            np.array([-10.0, -10.0, -10.0, -4.0]), 3
        )

        assert list(positive) == list(negative)

    def test_a_zero_baseline_collapses_the_trace(self, model):
        """
        ``np.sign(0)`` is zero, so the whole trace multiplies out. Pinned because it
        is pre-existing behaviour that survived the move, not because it is wanted.
        """
        result = model._rectify_event_current(np.array([0.0, 0.0, 5.0]), 2)

        assert list(result) == [0.0, 0.0, 0.0]


# ===========================================================================
# build_all_points_histogram - every sample of every event in one subset
# ===========================================================================


def _event(**overrides):
    """
    One event payload, with three samples of pre-event baseline.

    :param overrides: fields to replace on the default payload
    :type overrides: object
    :return: an event dict shaped as the loader yields them
    :rtype: dict
    """
    event = {
        "raw_data": np.array([5.0, 5.0, 5.0, 12.0, 13.0, 14.0]),
        "filtered_data": np.array([7.0, 7.0, 7.0, 20.0, 21.0, 22.0]),
        "padding_before": 300.0,  # 300 us * 10 kHz / 1e6 = 3 samples
        "padding_after": 100.0,
        "samplerate": 10000.0,
    }
    event.update(overrides)
    return event


class TestBuildAllPointsHistogram:
    """
    Moved off ``MetadataView``, where it walked the generator inside the widget.
    """

    def test_it_returns_one_count_per_bin_center(self, model):
        bincenters, counts, _, _ = model.build_all_points_histogram(
            iter([_event()]), "Raw All Points Histogram", [10], False, None, None
        )

        assert len(bincenters) == 10
        assert len(counts) == 10

    def test_every_sample_of_every_event_is_counted(self, model):
        bincenters, counts, _, _ = model.build_all_points_histogram(
            iter([_event(), _event()]),
            "Raw All Points Histogram",
            [10],
            False,
            None,
            None,
        )

        assert counts.sum() == 12

    def test_a_raw_plot_type_reads_the_raw_trace(self, model):
        """
        The two traces are far enough apart that the limits alone say which was used.
        """
        _, _, hist_min, hist_max = model.build_all_points_histogram(
            iter([_event()]), "Raw All Points Histogram", [10], False, None, None
        )

        assert hist_min == 0.0
        assert hist_max == 9.0

    def test_a_filtered_plot_type_reads_the_filtered_trace(self, model):
        _, _, hist_min, hist_max = model.build_all_points_histogram(
            iter([_event()]), "Filtered All Points Histogram", [10], False, None, None
        )

        assert hist_min == 0.0
        assert hist_max == 15.0

    def test_the_limits_it_is_given_are_widened_not_replaced(self, model):
        """
        The shared limits are what put overlaid subsets on comparable bins, so a
        subset lying inside an existing range must leave it alone.
        """
        _, _, hist_min, hist_max = model.build_all_points_histogram(
            iter([_event()]), "Raw All Points Histogram", [10], False, -100.0, 100.0
        )

        assert hist_min == -100.0
        assert hist_max == 100.0

    def test_a_bin_width_is_divided_into_the_shared_range(self, model):
        """
        ``sizes=True`` means the number is a width, and the count falls out of the
        range it has to span.
        """
        bincenters, _, _, _ = model.build_all_points_histogram(
            iter([_event()]), "Raw All Points Histogram", [1.0], True, 0.0, 10.0
        )

        assert len(bincenters) == 10

    def test_an_empty_bins_list_is_refused(self, model):
        with pytest.raises(ValueError, match="Invalid bins entry"):
            model.build_all_points_histogram(
                iter([_event()]), "Raw All Points Histogram", [], False, None, None
            )

    def test_a_width_that_cannot_be_divided_is_refused(self, model):
        with pytest.raises(ValueError, match="Unable to calculate bins"):
            model.build_all_points_histogram(
                iter([_event()]), "Raw All Points Histogram", ["wide"], True, 0.0, 10.0
            )

    def test_no_bin_request_falls_back_to_a_hundred(self, model):
        bincenters, _, _, _ = model.build_all_points_histogram(
            iter([_event()]), "Raw All Points Histogram", None, False, None, None
        )

        assert len(bincenters) == 100

    def test_an_unknown_plot_type_is_refused(self, model):
        with pytest.raises(ValueError, match="Unknown plot_type"):
            model.build_all_points_histogram(
                iter([_event()]), "Sideways Histogram", [10], False, None, None
            )


# ===========================================================================
# build_event_overlay - one normalised trace per event
# ===========================================================================


class TestBuildEventOverlay:
    """
    The other half of the event-data reduction, moved with it.
    """

    def test_it_returns_one_pair_per_event(self, model):
        traces = model.build_event_overlay(
            iter([_event(), _event()]), "Raw Event Overlay"
        )

        assert len(traces) == 2
        for time, data in traces:
            assert len(time) == len(data) == 6

    def test_the_event_starts_at_zero_on_the_normalised_axis(self, model):
        """
        The padding is what the axis is normalised against: the event proper runs
        from zero to one however long it is, and the paddings fall outside that.
        """
        ((time, _),) = model.build_event_overlay(iter([_event()]), "Raw Event Overlay")

        # 6 samples, 3 of pre-event padding and 1 of post-event, so the event is 2
        # samples long and the axis divides by 2.
        assert list(time) == [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0]

    def test_the_trace_is_baseline_subtracted(self, model):
        ((_, data),) = model.build_event_overlay(iter([_event()]), "Raw Event Overlay")

        assert list(data) == [0.0, 0.0, 0.0, 7.0, 8.0, 9.0]

    def test_a_filtered_overlay_reads_the_filtered_trace(self, model):
        ((_, data),) = model.build_event_overlay(
            iter([_event()]), "Filtered Event Overlay"
        )

        assert list(data) == [0.0, 0.0, 0.0, 13.0, 14.0, 15.0]

    def test_an_empty_subset_returns_nothing(self, model):
        assert model.build_event_overlay(iter([]), "Raw Event Overlay") == []

    def test_an_unknown_plot_type_is_refused(self, model):
        """
        The two-branch ``if`` this replaced had no ``else``, so an unrecognised type
        left the previous event's samples bound and redrew them under this event's
        label from the second event onwards.
        """
        with pytest.raises(ValueError, match="Unknown plot_type"):
            model.build_event_overlay(iter([_event()]), "Sideways Event Overlay")
