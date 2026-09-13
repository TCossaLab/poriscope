"""
Unit-test suite for MetadataModel.

MetadataModel was a minimal MetaModel subclass with a no-op ``_init()``. **Step 4c
is giving it the metadata tab's binning and fitting**, moved off MetadataView so
that ``scipy``, ``scipy.optimize`` and ``scipy.stats`` leave the View layer.

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
# calculate_heatmap - pins moved from test_metadata_view.py by Step 4c
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
        *imported* ``iqr``, which is now the Model's (method rule 45).
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
    assertable, so they are rewritten here rather than re-pointed (rule 43).
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
# fit_capture_rate - pins moved from test_metadata_view.py by Step 4c
# ===========================================================================


class TestFitCaptureRate:
    """
    The capture-rate binning and exponential fit, moved off MetadataView.

    The two bin-fallback tests came with the rule they exercise: they patched
    ``MetadataView.iqr``, and ``mock.patch`` names the module that imported the
    symbol, so the target moved too (method rule 45). Both now assert the bin count
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
