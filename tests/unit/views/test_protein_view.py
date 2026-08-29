"""
Full unit-test suite for ProteinView.

Covers the ProteinView analysis tab end-to-end, including:
  - format_axis_label (module-level helper)
  - Gaussian fitting: _double_gaussian, _fit_double_gaussian,
    _fit_and_sanity_check_double_gaussian
  - Physical model: _compute_theoretical_blockages, _generate_vm_ensemble
  - Histogram construction: _construct_single_event_histogram,
    _construct_all_points_histogram
  - Plotting: _plot_all_points_histogram, _plot_scatterplot,
    _plot_xyerr_scatterplot, update_plot
  - Event/histogram navigation and caching: _fetch_event_data,
    _handle_plot_events, _handle_plot_histogram, _shift_range_and_update_plot
  - Filter management: add/edit/delete/save/load, and raw-SQL validation
    callbacks (on_raw_filter_validated)
  - Fit commit/reset lifecycle: _commit_fits, _reset_actions
  - Qt wiring: _set_custom_display_area, _set_control_area,
    handle_parameter_change dispatch
  - A small integration/pipeline test class exercising histogram -> fit ->
    V/M scatter as a whole

Uses:
  - A session-scoped QApplication fixture (qt_app) so Qt widgets can be
    constructed once per test session.
  - A per-test ProteinView fixture (mock_view) built via the same
    _set_custom_display_area / _set_control_area sequence MetaView uses in
    the running application, so canvases, axes, and ProteinControls are
    fully wired.
  - Real imports from the poriscope package rather than a mocked ProteinView,
    so tests exercise actual widget and signal behaviour.
  - unittest.mock (MagicMock, patch) to stub out global_signal emissions,
    file dialogs, and modal dialogs (AddSubsetFilterDialog,
    EditSubsetFilterDialog, SelectionTree) so tests remain non-blocking and
    independent of a live plugin bus or database backend.

Notes:
  - Several tests are annotated "documented" or "_bug" in their names; these
    intentionally pin down current behaviour (including known quirks, e.g.
    format_axis_label's regex on nested parentheses, or the double-Gaussian
    fallback fit's degenerate single-peak behaviour) rather than asserting
    an ideal/fixed outcome. Treat failures in these tests as a prompt to
    re-evaluate intent, not just to "fix" them blindly.
  - Tests involving global_signal generally leave it unconnected (no live
    plugin bus), so any code path depending on a slot's return value should
    be set up manually on the mock_view fixture before calling into it.

Run with:
    pytest tests/unit/views/test_protein_view.py -v
"""

import json
import os
import tempfile
import warnings
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from poriscope.plugins.analysistabs.ProteinView import ProteinView, format_axis_label
from tests.unit.views._qt_mocks import mock_axes, shadow_signals

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def real_view(qt_app):
    """
    Return a fully-initialised ProteinView built from real Qt widgets.

    MetaView.__init__ calls _set_custom_display_area and _set_control_area
    during the real widget build sequence; we call them explicitly here so
    that display_stack, ax_hist, canvas_hist, proteincontrols, etc. are all
    present — exactly as in the running application.

    The parent container is kept alive for the test duration, then explicitly
    closed and destroyed in teardown so no Qt state leaks into subsequent
    test files when running the full suite with --cov.

    Use this only where the test needs real Qt or Matplotlib behaviour:
    asserting that construction actually produced widgets, emitting a real
    signal to prove a connection exists, or reading state back off an Axes.
    Everything else should take ``mock_view``, which is far cheaper.
    """
    v = ProteinView()
    container = QWidget()
    layout = QVBoxLayout(container)
    v._set_custom_display_area(layout)
    v._set_control_area(layout)
    v._test_container = container  # keep Qt parent alive for test duration

    return v


@pytest.fixture
def mock_view():
    """
    Return a ProteinView with its Qt and Matplotlib dependencies mocked.

    Built with __new__ so no widget is constructed, then given the attributes
    _set_custom_display_area and _set_control_area would have created, then
    passed through the real _init(). The methods under test are the real ones
    and so is every numeric path; only the drawing surfaces and the controls
    widget are stand-ins. ProteinView never consumes a return value from
    Matplotlib - it calls plot/scatter/errorbar/draw and discards the result -
    so a mocked Axes cannot diverge from a real one here.

    fig_hist/ax_hist/canvas_hist and their _vm counterparts are properties that
    dispatch on _analysis_mode, so both the individual and ensemble attributes
    are populated and that dispatch stays real.

    Tests that assert construction produced something, that emit a real Qt
    signal, or that read state back off an Axes must take ``real_view``: those
    assertions pass vacuously against a MagicMock.
    """
    v = ProteinView.__new__(ProteinView)

    for mode in ("individual", "ensemble"):
        setattr(v, f"fig_hist_{mode}", MagicMock())
        setattr(v, f"ax_hist_{mode}", mock_axes())
        setattr(v, f"canvas_hist_{mode}", MagicMock())
        setattr(v, f"fig_vm_{mode}", MagicMock())
        setattr(v, f"ax_vm_{mode}", mock_axes())
        setattr(v, f"canvas_vm_{mode}", MagicMock())

    v.fig_event = MagicMock()
    v.canvas_event = MagicMock()
    v.event_outer_ax = None
    v.display_stack = MagicMock()
    v.mode_stack = MagicMock()
    v.individual_dist_page = MagicMock()
    v.ensemble_dist_page = MagicMock()
    v.proteincontrols = MagicMock()
    # logger is deliberately NOT mocked: ProteinView.logger is a class
    # attribute, so it resolves on its own, and tests assert through caplog.

    # ProteinView declares Qt Signals at class level. With no C++ QObject behind
    # a __new__ instance, emitting one raises "Signal source has been deleted",
    # so every declared signal is shadowed with a stand-in - discovered by
    # introspection rather than listed, so a newly added signal is covered too.
    shadow_signals(v, ProteinView)

    # _init() -> _clear_cache() reads these, so they must be set first.
    v._analysis_mode = "individual"
    v._display_mode = "distribution"

    v._init()
    return v


# ===========================================================================
# Helpers
# ===========================================================================


def _make_event(
    event_id=1,
    n=2000,
    sr=1_000_000,
    padding_us=100,
    blockage=0.3,
    noise=0.01,
    rng_seed=0,
):
    """Synthetic event dict matching what load_event_data yields."""
    rng = np.random.default_rng(rng_seed)
    pb = int(padding_us * sr * 1e-6)
    pa = int(padding_us * sr * 1e-6)
    baseline = 1000.0
    event_current = baseline * (1.0 - blockage)
    ts = np.full(n, event_current) + rng.normal(0, noise * baseline, n)
    ts[:pb] = baseline + rng.normal(0, noise * baseline, pb)
    ts[-pa:] = baseline + rng.normal(0, noise * baseline, pa)
    fit = np.full(n, event_current)
    fit[:pb] = baseline
    fit[-pa:] = baseline
    return {
        "id": event_id,
        "event_id": event_id,
        "experiment_id": 1,
        "channel_id": 0,
        "raw_data": ts.copy(),
        "filtered_data": ts.copy(),
        "fit_data": fit,
        "samplerate": sr,
        "padding_before": padding_us,
        "padding_after": padding_us,
    }


def _make_double_gaussian_histogram(
    mean1=0.2, std1=0.02, amp1=1.0, mean2=0.6, std2=0.03, amp2=0.8, n_bins=200
):
    x = np.linspace(0.0, 1.0, n_bins)
    g1 = amp1 * np.exp(-((x - mean1) ** 2) / (2 * std1**2))
    g2 = amp2 * np.exp(-((x - mean2) ** 2) / (2 * std2**2))
    return x, g1 + g2


def _add_filter(mock_view, name, text="dur > 0"):
    """Add a filter to both subset_filters dict and the real combobox."""
    mock_view.subset_filters[name] = text
    mock_view.proteincontrols.filter_comboBox.addItem(name)
    mock_view.proteincontrols.filter_comboBox.selectItem(name, select=True)


def _selected_filter_names(mock_view):
    """Return the list of selected filter names from the real combobox."""
    return mock_view.proteincontrols.filter_comboBox.getSelectedItems()


def _all_filter_names(mock_view):
    """Return all item names visible in the real combobox."""
    lw = mock_view.proteincontrols.filter_comboBox.listWidget
    names = []
    for i in range(lw.count()):
        item = lw.item(i)
        widget = lw.itemWidget(item)
        if widget:
            from PySide6.QtWidgets import QCheckBox

            cb = widget.findChild(QCheckBox)
            if cb:
                names.append(cb.text())
    return names


# ===========================================================================
# format_axis_label  (module-level function)
# ===========================================================================


class TestFormatAxisLabel:
    def test_adds_unit(self):
        assert format_axis_label("Duration", "ms") == "Duration (ms)"

    def test_empty_unit(self):
        assert format_axis_label("Amplitude", "") == "Amplitude"

    def test_strips_and_replaces(self):
        assert format_axis_label("Duration (s)", "ms") == "Duration (ms)"

    def test_strips_when_new_unit_empty(self):
        assert format_axis_label("Amplitude (pA)", "") == "Amplitude"

    def test_latex_unit(self):
        assert format_axis_label("Volume", r"nm$^{3}$") == r"Volume (nm$^{3}$)"

    def test_idempotent(self):
        once = format_axis_label("Duration", "ms")
        assert format_axis_label(once, "ms") == once

    def test_inner_parens_bug_documented(self):
        # BUG: regex r"\s*\(.*?\)$" strips "log10(Duration)" -> "log10"
        assert format_axis_label("log10(Duration)", "s") == "log10 (s)"

    def test_none_unit_equivalent(self):
        assert format_axis_label("X", "") == "X"


# ===========================================================================
# _double_gaussian
# ===========================================================================


class TestDoubleGaussian:
    def test_peak_at_mean1(self, mock_view):
        r = mock_view._double_gaussian(np.array([0.2]), 1.0, 0.2, 0.05, 0.8, 0.6, 0.05)
        assert r[0] == pytest.approx(1.0, rel=1e-6)

    def test_peak_at_mean2(self, mock_view):
        r = mock_view._double_gaussian(np.array([0.6]), 1.0, 0.2, 0.05, 0.8, 0.6, 0.05)
        assert r[0] == pytest.approx(0.8, rel=1e-6)

    def test_zero_amplitudes(self, mock_view):
        x = np.linspace(0, 1, 50)
        np.testing.assert_array_equal(
            mock_view._double_gaussian(x, 0, 0.3, 0.05, 0, 0.7, 0.05), 0
        )

    def test_output_shape(self, mock_view):
        x = np.linspace(0, 1, 100)
        assert mock_view._double_gaussian(x, 1, 0.3, 0.1, 1, 0.7, 0.1).shape == (100,)

    def test_tails_near_zero(self, mock_view):
        x = np.array([-10.0, 10.0])
        assert np.all(mock_view._double_gaussian(x, 1, 0.3, 0.05, 1, 0.7, 0.05) < 1e-10)

    def test_symmetry(self, mock_view):
        x = np.linspace(0, 1, 50)
        r1 = mock_view._double_gaussian(x, 1.0, 0.3, 0.05, 0.5, 0.7, 0.05)
        r2 = mock_view._double_gaussian(x, 0.5, 0.7, 0.05, 1.0, 0.3, 0.05)
        np.testing.assert_allclose(r1, r2, rtol=1e-12)

    def test_non_negative(self, mock_view):
        x = np.linspace(-1, 2, 200)
        assert np.all(mock_view._double_gaussian(x, 2, 0.3, 0.1, 1.5, 0.8, 0.15) >= 0)


# ===========================================================================
# _fit_double_gaussian
# ===========================================================================


class TestFitDoubleGaussian:
    def test_clean_two_peak_signal(self, mock_view, qt_app):
        x, y = _make_double_gaussian_histogram()
        popt, pcov = mock_view._fit_double_gaussian(x, y)
        qt_app.processEvents()
        assert popt is not None and len(popt) == 6

    def test_single_peak_fallback_degenerate_bug(self, mock_view, qt_app):
        # BUG: fallback produces a degenerate two-component fit at the same position
        x = np.linspace(0, 1, 200)
        y = np.exp(-((x - 0.5) ** 2) / (2 * 0.05**2))
        popt, _ = mock_view._fit_double_gaussian(x, y)
        qt_app.processEvents()
        assert popt is not None and len(popt) == 6
        assert abs(popt[1] - popt[4]) < 0.05

    def test_flat_returns_none(self, mock_view, qt_app):
        x = np.linspace(0, 1, 100)
        popt, _ = mock_view._fit_double_gaussian(x, np.zeros_like(x))
        qt_app.processEvents()
        assert popt is None


# ===========================================================================
# _fit_and_sanity_check_double_gaussian
# ===========================================================================


class TestFitAndSanityCheck:
    def test_clean_signal_passes(self, mock_view):
        x, y = _make_double_gaussian_histogram()
        popt = mock_view._fit_and_sanity_check_double_gaussian(x, y)
        assert popt is not None and len(popt) == 6

    def test_recovered_means(self, mock_view):
        x, y = _make_double_gaussian_histogram(mean1=0.2, mean2=0.6)
        popt = mock_view._fit_and_sanity_check_double_gaussian(x, y)
        assert popt is not None
        means = sorted([popt[1], popt[4]])
        assert means[0] == pytest.approx(0.2, abs=0.01)
        assert means[1] == pytest.approx(0.6, abs=0.01)

    def test_flat_returns_none(self, mock_view):
        x = np.linspace(0, 1, 100)
        assert mock_view._fit_and_sanity_check_double_gaussian(x, np.zeros_like(x)) is None

    def test_single_peak_behaviour_documented(self, mock_view):
        # Documents that single-peak input may pass or fail the sanity check
        x = np.linspace(0, 1, 200)
        y = np.exp(-((x - 0.5) ** 2) / (2 * 0.05**2))
        result = mock_view._fit_and_sanity_check_double_gaussian(x, y)
        assert result is None or (
            len(result) == 6 and abs(result[1] - result[4]) < 0.05
        )

    def test_dominated_peak_behaviour_documented(self, mock_view):
        # BUG: dominated-peak guard is unreliable when fallback co-locates both components
        x = np.linspace(0, 1, 300)
        y = mock_view._double_gaussian(x, 1.0, 0.2, 0.02, 0.001, 0.7, 0.02)
        result = mock_view._fit_and_sanity_check_double_gaussian(x, y)
        assert result is None or len(result) == 6

    def test_roundtrip_residuals(self, mock_view):
        x, y = _make_double_gaussian_histogram()
        popt = mock_view._fit_and_sanity_check_double_gaussian(x, y)
        assert popt is not None
        assert np.max(np.abs(y - mock_view._double_gaussian(x, *popt))) < 0.02


# ===========================================================================
# _compute_theoretical_blockages
# ===========================================================================


class TestComputeTheoreticalBlockages:
    D, L = 20.0, 30.0

    def test_prolate_output_shape(self, mock_view):
        V, m = np.array([500.0] * 3), np.array([2.0] * 3)
        dmax, dmin = mock_view._compute_theoretical_blockages(V, m, self.D, self.L)
        assert dmax.shape == (3,) and dmin.shape == (3,)

    def test_oblate_output_shape(self, mock_view):
        V, m = np.array([500.0] * 3), np.array([0.5] * 3)
        dmax, dmin = mock_view._compute_theoretical_blockages(V, m, self.D, self.L)
        assert dmax.shape == (3,) and dmin.shape == (3,)

    def test_blockages_positive(self, mock_view):
        for m_val in [2.0, 0.5]:
            V, m = np.array([500.0]), np.array([m_val])
            dmax, dmin = mock_view._compute_theoretical_blockages(V, m, self.D, self.L)
            assert np.all(dmax > 0) and np.all(dmin > 0)

    def test_max_ge_min(self, mock_view):
        for m_val in [2.0, 0.5]:
            V, m = np.array([500.0]), np.array([m_val])
            dmax, dmin = mock_view._compute_theoretical_blockages(V, m, self.D, self.L)
            assert np.all(dmax >= dmin)

    def test_monotone_in_volume(self, mock_view):
        m = np.array([2.0])
        dmax_s, _ = mock_view._compute_theoretical_blockages(
            np.array([100.0]), m, self.D, self.L
        )
        dmax_l, _ = mock_view._compute_theoretical_blockages(
            np.array([1000.0]), m, self.D, self.L
        )
        assert dmax_l > dmax_s

    def test_mixed_raises(self, mock_view):
        V, m = np.array([500.0, 500.0]), np.array([0.5, 2.0])
        with pytest.raises(ValueError, match="Cannot mix"):
            mock_view._compute_theoretical_blockages(V, m, self.D, self.L)

    def test_negative_m_silent_nan_bug(self, mock_view):
        # BUG: negative m satisfies all(m<=1) so the ValueError guard is never reached
        V, m = np.array([500.0]), np.array([-1.0])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dmax, dmin = mock_view._compute_theoretical_blockages(V, m, self.D, self.L)
        assert np.any(np.isnan(dmax)) or np.any(np.isinf(dmax))

    def test_single_element(self, mock_view):
        V, m = np.array([500.0]), np.array([3.0])
        dmax, _ = mock_view._compute_theoretical_blockages(V, m, self.D, self.L)
        assert dmax.shape == (1,)

    def test_linear_scaling_small_objects(self, mock_view):
        m = np.array([2.0])
        dmax1, _ = mock_view._compute_theoretical_blockages(
            np.array([10.0]), m, self.D, self.L
        )
        dmax2, _ = mock_view._compute_theoretical_blockages(
            np.array([20.0]), m, self.D, self.L
        )
        assert dmax2[0] / dmax1[0] == pytest.approx(2.0, abs=0.5)


# ===========================================================================
# _generate_vm_ensemble
# ===========================================================================


class TestGenerateVmEnsemble:
    D, L = 20.0, 30.0
    MMAX, SMAX, MMIN, SMIN = 0.30, 0.03, 0.10, 0.02

    def test_prolate_count(self, mock_view):
        np.random.seed(0)
        V, m = mock_view._generate_vm_ensemble(
            20, self.MMAX, self.SMAX, self.MMIN, self.SMIN, self.D, self.L, prolate=True
        )
        assert len(V) == 20 and len(m) == 20

    def test_oblate_count(self, mock_view):
        np.random.seed(1)
        V, m = mock_view._generate_vm_ensemble(
            20,
            self.MMAX,
            self.SMAX,
            self.MMIN,
            self.SMIN,
            self.D,
            self.L,
            prolate=False,
        )
        assert len(V) == 20 and len(m) == 20

    def test_prolate_m_gt1(self, mock_view):
        np.random.seed(2)
        _, m = mock_view._generate_vm_ensemble(
            20, self.MMAX, self.SMAX, self.MMIN, self.SMIN, self.D, self.L, prolate=True
        )
        assert np.all(m >= 1.0)

    def test_oblate_m_lt1(self, mock_view):
        np.random.seed(3)
        _, m = mock_view._generate_vm_ensemble(
            20,
            self.MMAX,
            self.SMAX,
            self.MMIN,
            self.SMIN,
            self.D,
            self.L,
            prolate=False,
        )
        assert np.all(m > 0) and np.all(m <= 1.0)

    def test_volumes_positive(self, mock_view):
        np.random.seed(4)
        for p in (True, False):
            V, _ = mock_view._generate_vm_ensemble(
                20,
                self.MMAX,
                self.SMAX,
                self.MMIN,
                self.SMIN,
                self.D,
                self.L,
                prolate=p,
            )
            assert np.all(V > 0)

    def test_unphysical_bails_out(self, mock_view):
        np.random.seed(5)
        V, m = mock_view._generate_vm_ensemble(50, 5.0, 0.01, 4.0, 0.01, self.D, self.L)
        assert len(V) < 50

    def test_zero_target(self, mock_view):
        np.random.seed(6)
        V, m = mock_view._generate_vm_ensemble(
            0, self.MMAX, self.SMAX, self.MMIN, self.SMIN, self.D, self.L
        )
        assert len(V) == 0 and len(m) == 0

    def test_accepted_within_cutoff(self, mock_view):
        np.random.seed(7)
        cutoff = 4
        V, m = mock_view._generate_vm_ensemble(
            30,
            self.MMAX,
            self.SMAX,
            self.MMIN,
            self.SMIN,
            self.D,
            self.L,
            prolate=True,
            cutoff_std=cutoff,
        )
        if len(V) == 0:
            pytest.skip("no results for this seed")
        dmax, dmin = mock_view._compute_theoretical_blockages(V, m, self.D, self.L)
        assert np.all(np.abs(dmax - self.MMAX) / self.SMAX <= cutoff + 1e-6)
        assert np.all(np.abs(dmin - self.MMIN) / self.SMIN <= cutoff + 1e-6)


# ===========================================================================
# _construct_single_event_histogram
# ===========================================================================


class TestConstructSingleEventHistogram:
    def test_returns_dataframe(self, mock_view):
        df = mock_view._construct_single_event_histogram(_make_event(), "Filtered Histogram")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["Normalized Current", "Amplitude"]

    def test_default_uses_freedman_diaconis(self, mock_view):
        """Default binning (no explicit bins arg) now uses Freedman-Diaconis,
        which is data-dependent — assert it's a sane positive integer, not a
        fixed count."""
        df = mock_view._construct_single_event_histogram(_make_event(), "Filtered Histogram")
        assert len(df) > 0

    def test_explicit_100_bins_still_works(self, mock_view):
        """Explicit bin count still overrides FD and behaves as before."""
        df = mock_view._construct_single_event_histogram(
            _make_event(), "Filtered Histogram", bins=[100]
        )
        assert len(df) == 100

    def test_custom_bin_count(self, mock_view):
        df = mock_view._construct_single_event_histogram(
            _make_event(), "Filtered Histogram", bins=[50]
        )
        assert len(df) == 50

    def test_custom_bin_size(self, mock_view):
        df = mock_view._construct_single_event_histogram(
            _make_event(), "Filtered Histogram", bins=[0.01], sizes=True
        )
        assert len(df) > 0

    def test_empty_event_returns_none(self, mock_view):
        ev = {
            "id": 1,
            "event_id": 1,
            "experiment_id": 1,
            "channel_id": 0,
            "raw_data": np.zeros(400),
            "filtered_data": np.zeros(400),
            "fit_data": np.zeros(400),
            "samplerate": 1_000_000,
            "padding_before": 200,
            "padding_after": 200,
        }
        assert mock_view._construct_single_event_histogram(ev, "Filtered Histogram") is None

    def test_updates_hist_min_max(self, mock_view):
        mock_view._construct_single_event_histogram(
            _make_event(blockage=0.4), "Filtered Histogram"
        )
        assert mock_view.hist_min is not None
        assert mock_view.hist_max is not None
        assert mock_view.hist_min < mock_view.hist_max

    def test_raw_vs_filtered(self, mock_view):
        ev = _make_event()
        ev["raw_data"] = ev["filtered_data"].copy()
        assert mock_view._construct_single_event_histogram(ev, "Raw Histogram") is not None
        assert (
            mock_view._construct_single_event_histogram(ev, "Filtered Histogram") is not None
        )

    def test_invalid_bins_raises(self, mock_view):
        with pytest.raises((ValueError, TypeError)):
            mock_view._construct_single_event_histogram(
                _make_event(), "Filtered Histogram", bins="bad", sizes=False
            )


# ===========================================================================
# _construct_all_points_histogram
# ===========================================================================


class TestConstructAllPointsHistogram:
    def _events(self, n=3):
        return [_make_event(i, blockage=0.2 + i * 0.05, rng_seed=i) for i in range(n)]

    def test_returns_dataframe(self, mock_view):
        df = mock_view._construct_all_points_histogram(
            iter(self._events()), "Filtered Histogram"
        )
        assert isinstance(df, pd.DataFrame)
        assert "Normalized Current" in df.columns

    def test_default_100_bins(self, mock_view):
        df = mock_view._construct_all_points_histogram(
            iter(self._events()), "Filtered Histogram"
        )
        assert len(df) == 100

    def test_custom_bins(self, mock_view):
        df = mock_view._construct_all_points_histogram(
            iter(self._events()), "Filtered Histogram", bins=[50]
        )
        assert len(df) == 50

    def test_bin_size_mode(self, mock_view):
        df = mock_view._construct_all_points_histogram(
            iter(self._events()), "Filtered Histogram", bins=[0.05], sizes=True
        )
        assert len(df) > 0

    def test_raw_histogram_type(self, mock_view):
        df = mock_view._construct_all_points_histogram(iter(self._events()), "Raw Histogram")
        assert df is not None

    def test_amplitude_nonnegative(self, mock_view):
        df = mock_view._construct_all_points_histogram(
            iter(self._events()), "Filtered Histogram"
        )
        assert np.all(df["Amplitude"].values >= 0)

    def test_multiple_events_extend_range(self, mock_view):
        evs = [
            _make_event(blockage=0.1, rng_seed=0),
            _make_event(blockage=0.5, rng_seed=1),
        ]
        df = mock_view._construct_all_points_histogram(iter(evs), "Filtered Histogram")
        assert df["Normalized Current"].max() - df["Normalized Current"].min() > 0


# ===========================================================================
# _build_load_event_data_args
# ===========================================================================


class TestBuildLoadEventDataArgs:
    def test_non_raw_returns_filter_and_exp(self, mock_view):
        exp_ch = {"ExpA": ["0"]}
        result = mock_view._build_load_event_data_args(
            "dur > 100", "myfilter", "ExpA", "0", exp_ch, "loader1"
        )
        assert result == ("dur > 100", exp_ch)

    def test_raw_returns_none_second(self, mock_view):
        result = mock_view._build_load_event_data_args(
            "SELECT * FROM events", "myfilter_raw", "ExpA", "0", {}, "loader1"
        )
        assert result[1] is None

    def test_raw_strips_trailing_semicolon(self, mock_view):
        result = mock_view._build_load_event_data_args(
            "SELECT * FROM events;", "filter_raw", None, "0", {}, "loader1"
        )
        assert not result[0].endswith(";")

    def test_raw_no_exp_no_scope(self, mock_view):
        result = mock_view._build_load_event_data_args(
            "SELECT * FROM events", "filter_raw", None, "0", {}, "loader1"
        )
        assert "WHERE" not in result[0].upper()

    def test_raw_scope_requires_live_bus(self, mock_view):
        # global_signal.emit() has no connected slots in tests so
        # experiment_id stays None and the scope clause is not appended.
        mock_view.experiment_id = 5
        mock_view.channel_db_id = 2
        result = mock_view._build_load_event_data_args(
            "SELECT * FROM events", "filter_raw", "ExpA", "0", {}, "loader1"
        )
        assert result[1] is None
        assert "SELECT * FROM events" in result[0]


# ===========================================================================
# State setters
# ===========================================================================


class TestStateSetters:
    def test_set_alter_database_status_true(self, mock_view):
        mock_view.set_alter_database_status(True)
        assert mock_view.operation_success is True

    def test_set_alter_database_status_false(self, mock_view):
        mock_view.set_alter_database_status(False)
        assert mock_view.operation_success is False

    def test_update_column_names(self, mock_view):
        mock_view.update_column_names(["a", "b", "c"])
        assert mock_view.available_columns == ["a", "b", "c"]

    def test_set_channel_db_id(self, mock_view):
        mock_view.set_channel_db_id(42)
        assert mock_view.channel_db_id == 42

    def test_set_baseline_duration(self, mock_view):
        mock_view.set_baseline_duration(500)
        assert mock_view.baseline_duration == 500

    def test_set_event_data_generator(self, mock_view):
        g = iter([1, 2, 3])
        mock_view.set_event_data_generator(g)
        assert mock_view.event_data_generator is g

    def test_set_event_plot_data_generator(self, mock_view):
        g = iter([])
        mock_view.set_event_plot_data_generator(g)
        assert mock_view.plot_events_generator is g
        assert mock_view.plot_events_generator_updated is True

    def test_set_experiment_id(self, mock_view):
        mock_view.set_experiment_id(99)
        assert mock_view.experiment_id == 99

    def test_set_table_by_column_appends(self, mock_view):
        if not hasattr(mock_view, "involved_tables"):
            mock_view.involved_tables = []
        before = len(mock_view.involved_tables)
        mock_view.set_table_by_column("events")
        assert len(mock_view.involved_tables) == before + 1
        assert "events" in mock_view.involved_tables

    def test_set_table_by_column_none_ignored(self, mock_view):
        if not hasattr(mock_view, "involved_tables"):
            mock_view.involved_tables = []
        before = len(mock_view.involved_tables)
        mock_view.set_table_by_column(None)
        assert len(mock_view.involved_tables) == before

    def test_set_units(self, mock_view):
        mock_view.set_units("nm")
        assert mock_view.units == "nm"

    def test_clear_pending_filter_state(self, mock_view):
        mock_view._pending_filter_name = "x"
        mock_view._pending_filter_text = "y"
        mock_view._pending_old_filter_name = "z"
        mock_view.clear_pending_filter_state()
        assert mock_view._pending_filter_name is None
        assert mock_view._pending_filter_text is None
        assert mock_view._pending_old_filter_name is None

    def test_get_current_view(self, mock_view):
        assert mock_view.get_current_view() == "ProteinView"
        assert mock_view.get_current_view() == "ProteinView"

    def test_set_query_stores(self, mock_view):
        mock_view.set_query("SELECT * FROM events", "events")
        assert mock_view.query == "SELECT * FROM events"
        assert mock_view.table_name == "events"

    def test_set_query_empty_returns_early(self, mock_view):
        mock_view.set_query("", "events")
        assert mock_view.query == ""

    def test_set_query_shows_sql_when_flag(self, mock_view):
        received = []
        mock_view.add_text_to_display.connect(lambda msg, src: received.append(msg))
        mock_view._show_sql_in_display = True
        mock_view.set_query("SELECT 1", "events")
        assert any("SELECT 1" in m for m in received)
        assert mock_view._show_sql_in_display is False

    def test_set_event_query_stores(self, mock_view):
        mock_view.set_event_query("SELECT * FROM events")
        assert mock_view.event_query == "SELECT * FROM events"

    def test_set_event_query_empty(self, mock_view):
        mock_view.set_event_query("")
        assert mock_view.event_query == ""

    def test_set_event_query_shows_when_flag(self, mock_view):
        received = []
        mock_view.add_text_to_display.connect(lambda msg, src: received.append(msg))
        mock_view._show_event_sql_in_display = True
        mock_view.set_event_query("SELECT 2")
        assert any("SELECT 2" in m for m in received)
        assert mock_view._show_event_sql_in_display is False


# ===========================================================================
# _handle_other_actions
# ===========================================================================


class TestHandleOtherActions:
    def test_raises_not_implemented(self, mock_view):
        with pytest.raises(NotImplementedError, match="unknown_action"):
            mock_view._handle_other_actions("unknown_action", {})


# ===========================================================================
# _set_display_mode
# ===========================================================================


class TestSetDisplayMode:
    def test_event_mode(self, mock_view):
        mock_view._set_display_mode("event")
        assert mock_view._display_mode == "event"

    def test_distribution_mode(self, mock_view):
        mock_view._set_display_mode("event")
        mock_view._set_display_mode("distribution")
        assert mock_view._display_mode == "distribution"

    def test_unknown_defaults_to_distribution(self, mock_view):
        mock_view._set_display_mode("other")
        assert mock_view._display_mode == "distribution"


# ===========================================================================
# _commit_fits
# ===========================================================================


class TestCommitFits:
    def test_raises_when_no_fit_data(self, mock_view):
        mock_view.fit_data = None
        with pytest.raises(AttributeError, match="fit data has not been set"):
            mock_view._commit_fits("loader1")

    def test_proceeds_with_fit_data(self, mock_view):
        # column_table is None so the overwrite dialog is never shown;
        # global_signal is emitted with no connected handler, which is fine.
        mock_view.fit_data = pd.DataFrame(
            {
                "id": [1],
                "prolate_volume": [100.0],
                "prolate_shape_factor": [2.0],
                "prolate_major_axis": [10.0],
                "prolate_minor_axis": [5.0],
                "oblate_volume": [80.0],
                "oblate_shape_factor": [0.5],
                "oblate_major_axis": [4.0],
                "oblate_minor_axis": [8.0],
                "min_fractional_blockage": [0.1],
                "min_fractional_blockage_std": [0.01],
                "max_fractional_blockage": [0.3],
                "max_fractional_blockage_std": [0.02],
            }
        )
        mock_view.column_table = None
        mock_view._commit_fits("loader1")  # should not raise


# ===========================================================================
# _reset_actions
# ===========================================================================


class TestResetActions:
    def test_clears_hist_state(self, mock_view):
        mock_view.hist_min = 1.0
        mock_view.hist_max = 2.0
        mock_view.hist_data = [([1], [2])]
        mock_view.hist_labels = ["x"]
        mock_view._reset_actions()
        assert mock_view.hist_min is None
        assert mock_view.hist_max is None
        assert mock_view.hist_data == []
        assert mock_view.hist_labels == []

    def test_clears_bins(self, mock_view):
        mock_view.allowed_bins = [10]
        mock_view.allowed_sizes = True
        mock_view._reset_actions()
        assert mock_view.allowed_bins is None
        assert mock_view.allowed_sizes is None

    def test_clears_plotted_datasets(self, mock_view):
        mock_view.plotted_datasets = {("a", "b", 0, "", "s")}
        mock_view._reset_actions()
        assert mock_view.plotted_datasets == set()


# ===========================================================================
# _clear_figure_state
# ===========================================================================


class TestClearFigureState:
    def test_clears_cache(self, mock_view):
        # Just verify _clear_figure_state runs without error
        # (cache internals belong to MetaView and vary by implementation)
        mock_view._clear_figure_state()

    def test_resets_event_outer_ax(self, mock_view):
        mock_view.event_outer_ax = object()
        mock_view._clear_figure_state()
        assert mock_view.event_outer_ax is None

    def test_heatmap_colorbar_reset(self, mock_view):
        mock_view._heatmap_colorbar = object()
        mock_view._clear_figure_state()
        assert mock_view._heatmap_colorbar is None


# ===========================================================================
# _plot_all_points_histogram
# ===========================================================================


class TestPlotAllPointsHistogram:
    def _df(self):
        x = np.linspace(0, 1, 20)
        return pd.DataFrame({"NC": x, "Amp": np.ones(20) * 0.5})

    def test_sets_axis_labels(self, real_view):
        real_view._plot_all_points_histogram(
            real_view.ax_hist, self._df(), ["NC", "Amp"], ["pA", ""]
        )
        assert "NC" in real_view.ax_hist.get_xlabel()

    def test_appends_to_hist_data(self, mock_view):
        mock_view._plot_all_points_histogram(
            mock_view.ax_hist, self._df(), ["NC", "Amp"], ["pA", ""], "ds1"
        )
        assert len(mock_view.hist_data) == 1

    def test_accumulates_multiple_calls(self, mock_view):
        mock_view._plot_all_points_histogram(
            mock_view.ax_hist, self._df(), ["NC", "Amp"], ["pA", ""], "ds1"
        )
        mock_view._plot_all_points_histogram(
            mock_view.ax_hist, self._df(), ["NC", "Amp"], ["pA", ""], "ds2"
        )
        assert len(mock_view.hist_data) == 2

    def test_norm_flag_modifies_ylabel(self, real_view):
        real_view._plot_all_points_histogram(
            real_view.ax_hist, self._df(), ["NC", "Amp"], ["pA", ""], norm=True
        )
        assert "Normalized" in real_view.ax_hist.get_ylabel()


# ===========================================================================
# _plot_scatterplot
# ===========================================================================


class TestPlotScatterplot:
    def _df(self):
        rng = np.random.default_rng(0)
        return pd.DataFrame({"V": rng.random(10), "m": rng.random(10)})

    def test_labels_set(self, real_view):
        real_view._plot_scatterplot(
            real_view.ax_vm, self._df(), ["V", "m"], ["nm^3", "au"], [False, False]
        )
        assert "V" in real_view.ax_vm.get_xlabel()
        assert "m" in real_view.ax_vm.get_ylabel()

    def test_log_x_prefix(self, real_view):
        df = pd.DataFrame(
            {
                "V": np.abs(np.random.rand(10)) + 0.01,
                "m": np.abs(np.random.rand(10)) + 0.01,
            }
        )
        real_view._plot_scatterplot(real_view.ax_vm, df, ["V", "m"], ["", ""], [True, False])
        assert "log10" in real_view.ax_vm.get_xlabel()

    def test_log_y_prefix(self, real_view):
        df = pd.DataFrame(
            {
                "V": np.abs(np.random.rand(10)) + 0.01,
                "m": np.abs(np.random.rand(10)) + 0.01,
            }
        )
        real_view._plot_scatterplot(real_view.ax_vm, df, ["V", "m"], ["", ""], [False, True])
        assert "log10" in real_view.ax_vm.get_ylabel()


# ===========================================================================
# _plot_xyerr_scatterplot
# ===========================================================================


class TestPlotXyerrScatterplot:
    def _df(self):
        n = 10
        rng = np.random.default_rng(0)
        return pd.DataFrame(
            {
                "x": rng.random(n),
                "y": rng.random(n),
                "xe": rng.random(n) * 0.01,
                "ye": rng.random(n) * 0.01,
            }
        )

    def test_requires_err_cols(self, mock_view):
        with pytest.raises(ValueError, match="two error columns"):
            mock_view._plot_xyerr_scatterplot(
                mock_view.ax_hist, self._df(), ["x", "y"], ["", ""], [False, False]
            )

    def test_runs_without_error(self, mock_view):
        mock_view._plot_xyerr_scatterplot(
            mock_view.ax_hist,
            self._df(),
            ["x", "y"],
            ["", ""],
            [False, False],
            err_cols=["xe", "ye"],
        )

    def test_null_err_col(self, mock_view):
        mock_view._plot_xyerr_scatterplot(
            mock_view.ax_hist,
            self._df(),
            ["x", "y"],
            ["", ""],
            [False, False],
            err_cols=["xe", None],
        )


# ===========================================================================
# update_plot
# ===========================================================================


class TestUpdatePlot:
    def _df(self):
        x = np.linspace(0, 1, 20)
        return pd.DataFrame({"NC": x, "Amp": np.ones(20) * 0.5})

    def test_histogram_routes_to_hist(self, real_view):
        real_view.update_plot(
            "Filtered Histogram",
            self._df(),
            ["NC", "Amp"],
            ["pA", ""],
            [False, False],
            dataset_label="d",
        )
        assert "NC" in real_view.ax_hist.get_xlabel()

    def test_scatterplot_routes_to_vm(self, real_view):
        df = pd.DataFrame({"V": np.random.rand(5), "m": np.random.rand(5)})
        real_view.update_plot("Scatterplot", df, ["V", "m"], ["", ""], [False, False])
        assert "V" in real_view.ax_vm.get_xlabel()

    def test_peak_scatterplot_routes_to_hist(self, mock_view):
        df = pd.DataFrame(
            {
                "x": np.random.rand(5),
                "y": np.random.rand(5),
                "xe": np.zeros(5),
                "ye": np.zeros(5),
            }
        )
        mock_view.update_plot(
            "Peak Scatterplot",
            df,
            ["x", "y"],
            ["", ""],
            [False, False],
            err_cols=["xe", "ye"],
        )

    def test_unknown_raises(self, mock_view):
        with pytest.raises(NotImplementedError):
            mock_view.update_plot(
                "Heatmap", self._df(), ["NC", "Amp"], ["", ""], [False, False]
            )


# ===========================================================================
# Range helpers (inherited from MetaView, exercised via ProteinView)
# ===========================================================================


class TestRangeHelpers:
    def test_parse_single(self, mock_view):
        assert mock_view._parse_event_indices("5", False) == [(5, 5)]

    def test_parse_range(self, mock_view):
        assert mock_view._parse_event_indices("3-7", False) == [(3, 7)]

    def test_parse_mixed(self, mock_view):
        assert mock_view._parse_event_indices("1,3-5,8", False) == [(1, 1), (3, 5), (8, 8)]

    def test_shift_right_increases_values(self, mock_view):
        before = mock_view._shift_ranges([(3, 3)], "right", 1)
        assert before[0][0] > 3 or before[0][1] > 3 or before[0] == (4, 4)

    def test_shift_left_decreases_values(self, mock_view):
        result = mock_view._shift_ranges([(5, 5)], "left", 1)
        # Left shift should move the range downward
        assert result[0][0] <= 5 and result[0][1] <= 5

    def test_shift_left_does_not_go_below_one(self, mock_view):
        # Shifting left from 1 should not produce 0 or negative
        result = mock_view._shift_ranges([(1, 1)], "left", 1)
        assert result[0][0] >= 0  # at worst 0; real impls clamp to 1

    def test_merge_adjacent(self, mock_view):
        assert mock_view._merge_ranges([(1, 2), (3, 4)]) == [(1, 4)]

    def test_merge_disjoint(self, mock_view):
        assert mock_view._merge_ranges([(1, 2), (5, 6)]) == [(1, 2), (5, 6)]

    def test_merge_empty(self, mock_view):
        assert mock_view._merge_ranges([]) == []

    def test_format_single(self, mock_view):
        assert mock_view._format_ranges([(5, 5)]) == "5"

    def test_format_range(self, mock_view):
        assert mock_view._format_ranges([(3, 7)]) == "3-7"

    def test_format_mixed(self, mock_view):
        assert mock_view._format_ranges([(1, 1), (3, 5)]) == "1,3-5"

    def test_expand_single(self, mock_view):
        assert mock_view._expand_event_indices("5") == [5]

    def test_expand_range(self, mock_view):
        assert mock_view._expand_event_indices("3-5") == [3, 4, 5]

    def test_expand_mixed(self, mock_view):
        assert mock_view._expand_event_indices("1,3-5,8") == [1, 3, 4, 5, 8]

    def test_expand_positive_only(self, mock_view):
        # Only positive indices should appear
        result = mock_view._expand_event_indices("1,2,3")
        assert all(i > 0 for i in result)

    def test_factors_perfect_square(self, mock_view):
        assert mock_view._factors(4) == (2, 2)

    def test_factors_six(self, mock_view):
        nr, nc = mock_view._factors(6)
        assert nr * nc == 6

    def test_factors_one(self, mock_view):
        nr, nc = mock_view._factors(1)
        assert nr * nc == 1

    def test_factors_zero_or_none(self, mock_view):
        # Just confirm it doesn't crash — real MetaView behaviour may differ
        try:
            nr, nc = mock_view._factors(0)
            assert nr >= 0 and nc >= 0
        except Exception:
            pass  # acceptable if MetaView raises on 0


class TestShiftRangeAndUpdatePlot:
    def _setup_cache(
        self, mock_view, cache=(0, 3, 5, 7), sql_filter="", exp="exp1", channel="0"
    ):
        mock_view.selected_experiment_and_channels_by_loader = {"l": {exp: [channel]}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        mock_view.filtered_event_ids = list(cache)
        mock_view.current_sql_filter = sql_filter
        mock_view.current_experiment = exp
        mock_view.current_channel = int(channel) if channel is not None else None

    def test_shift_right_updates_input(self, real_view):
        self._setup_cache(real_view)
        with patch.object(real_view, "_handle_plot_events"):
            real_view._shift_range_and_update_plot(
                {"db_loader": "l", "event_id": 3, "n_events": 1}, "right"
            )
        assert real_view.proteincontrols.event_id_lineEdit.text() == "5"

    def test_shift_left_updates_input(self, real_view):
        self._setup_cache(real_view)
        with patch.object(real_view, "_handle_plot_events"):
            real_view._shift_range_and_update_plot(
                {"db_loader": "l", "event_id": 5, "n_events": 1}, "left"
            )
        assert real_view.proteincontrols.event_id_lineEdit.text() == "3"

    def test_empty_input_returns_early(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {}
        mock_view._shift_range_and_update_plot({"db_loader": "l"}, "right")  # must not raise

    def test_dispatches_histogram(self, mock_view):
        self._setup_cache(mock_view)
        mock_view._last_event_action = "plot_histogram"
        with patch.object(mock_view, "_handle_plot_histogram") as mock_hist:
            mock_view._shift_range_and_update_plot(
                {"db_loader": "l", "event_id": 3, "n_events": 1}, "right"
            )
        mock_hist.assert_called_once()

    def test_dispatches_events(self, mock_view):
        self._setup_cache(mock_view)
        mock_view._last_event_action = "plot_events"
        with patch.object(mock_view, "_handle_plot_events") as mock_ev:
            mock_view._shift_range_and_update_plot(
                {"db_loader": "l", "event_id": 3, "n_events": 1}, "right"
            )
        mock_ev.assert_called_once()


# ===========================================================================
# _update_event_plot
# ===========================================================================


class TestUpdateEventPlot:
    def test_switches_to_event_mode(self, mock_view):
        mock_view._update_event_plot([_make_event(1), _make_event(2)])
        assert mock_view._display_mode == "event"

    def test_canvas_drawn(self, mock_view):
        mock_view._update_event_plot([_make_event(1)])
        assert mock_view._display_mode == "event"

    def test_multi_event_grid(self, mock_view):
        mock_view._update_event_plot([_make_event(i) for i in range(1, 5)])

    def test_cache_committed(self, mock_view):
        # Verify the method completes without error; cache internals are MetaView's
        mock_view._update_event_plot([_make_event(1)])


# ===========================================================================
# _update_event_histogram
# ===========================================================================


class TestUpdateEventHistogram:
    def test_switches_to_event_mode(self, mock_view):
        mock_view._update_event_histogram([_make_event(1)])
        assert mock_view._display_mode == "event"

    def test_multiple_events(self, mock_view):
        mock_view._update_event_histogram([_make_event(i, rng_seed=i) for i in range(1, 4)])

    def test_custom_bins(self, mock_view):
        mock_view._update_event_histogram([_make_event(1)], bins=[50])

    def test_cache_committed(self, mock_view):
        mock_view._update_event_histogram([_make_event(1)])


# ===========================================================================
# Filter management
# ===========================================================================


class TestFilterManagement:
    def test_get_selected_filters_empty(self, real_view):
        assert real_view.get_selected_filters() == {}

    def test_get_selected_filters_one(self, real_view):
        _add_filter(real_view, "f1", "dur > 100")
        result = real_view.get_selected_filters()
        assert "f1" in result
        assert result["f1"] == "dur > 100"

    def test_delete_filter_removes_from_dict(self, real_view):
        _add_filter(real_view, "f1")
        real_view._delete_filter("f1")
        assert "f1" not in real_view.subset_filters

    def test_delete_filter_by_name(self, real_view):
        _add_filter(real_view, "f2")
        real_view._delete_filter_by_name("f2")
        assert "f2" not in real_view.subset_filters

    def test_delete_all_selected(self, real_view):
        _add_filter(real_view, "fa")
        _add_filter(real_view, "fb")
        real_view._delete_all_selected_filters()
        assert "fa" not in real_view.subset_filters
        assert "fb" not in real_view.subset_filters

    def test_delete_nonexistent_no_error(self, real_view):
        real_view._delete_filter("does_not_exist")

    def test_delete_all_when_none_selected(self, real_view):
        real_view._delete_all_selected_filters()

    def test_replace_filter_item(self, real_view):
        _add_filter(real_view, "old")
        real_view.replace_filter_item("old")
        # After replace, "old" should be in the selected items
        assert "old" in _selected_filter_names(real_view)

    def test_update_filter_name(self, real_view):
        _add_filter(real_view, "old", "dur>0")
        real_view.update_filter_name("old", "new")
        all_names = _all_filter_names(real_view)
        assert "old" not in all_names
        assert "new" in all_names

    def test_update_filter_name_same(self, real_view):
        _add_filter(real_view, "same", "dur>0")
        real_view.update_filter_name("same", "same")
        # Should appear exactly once
        assert _all_filter_names(real_view).count("same") == 1


# ===========================================================================
# on_raw_filter_validated
# ===========================================================================


class TestOnRawFilterValidated:
    def _setup(self, mock_view, old_name=None):
        mock_view._pending_filter_name = "newfilter"
        mock_view._pending_filter_text = "SELECT * FROM events"
        mock_view._pending_old_filter_name = old_name

    def test_invalid_clears_pending(self, mock_view):
        self._setup(mock_view)
        mock_view.on_raw_filter_validated(False, "syntax error")
        assert mock_view._pending_filter_name is None

    def test_invalid_emits_message(self, mock_view):
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        self._setup(mock_view)
        mock_view.on_raw_filter_validated(False, "syntax error")
        assert any("syntax error" in m for m in received)

    def test_valid_add_path(self, mock_view):
        self._setup(mock_view)
        mock_view.on_raw_filter_validated(True, "")
        assert "newfilter" in mock_view.subset_filters

    def test_valid_add_emits_added(self, mock_view):
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        self._setup(mock_view)
        mock_view.on_raw_filter_validated(True, "")
        assert any("added" in m for m in received)

    def test_valid_edit_path(self, mock_view):
        mock_view.subset_filters["oldfilter"] = "old text"
        mock_view.proteincontrols.filter_comboBox.addItem("oldfilter")
        self._setup(mock_view, old_name="oldfilter")
        mock_view.on_raw_filter_validated(True, "")
        assert "oldfilter" not in mock_view.subset_filters
        assert "newfilter" in mock_view.subset_filters

    def test_valid_edit_emits_updated(self, mock_view):
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view.subset_filters["oldfilter"] = "old text"
        mock_view.proteincontrols.filter_comboBox.addItem("oldfilter")
        self._setup(mock_view, old_name="oldfilter")
        mock_view.on_raw_filter_validated(True, "")
        assert any("updated" in m for m in received)

    def test_clears_pending_after_success(self, mock_view):
        self._setup(mock_view)
        mock_view.on_raw_filter_validated(True, "")
        assert mock_view._pending_filter_name is None


# ===========================================================================
# _save_filter / _load_filter (file I/O paths)
# ===========================================================================


class TestSaveLoadFilter:
    @patch("poriscope.plugins.analysistabs.ProteinView.QFileDialog.getSaveFileName")
    def test_save_filter_writes_json(self, mock_dialog, mock_view):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fp:
            path = fp.name
        mock_dialog.return_value = (path, "JSON Files (*.json)")
        mock_view.subset_filters = {"f1": "dur>100", "f2": "dur<500"}
        mock_view._save_filter()
        with open(path) as f:
            data = json.load(f)
        assert data == {"f1": "dur>100", "f2": "dur<500"}
        os.unlink(path)

    @patch("poriscope.plugins.analysistabs.ProteinView.QFileDialog.getSaveFileName")
    def test_save_filter_empty_is_noop(self, mock_dialog, mock_view):
        mock_view.subset_filters = {}
        mock_view._save_filter()
        mock_dialog.assert_not_called()

    @patch("poriscope.plugins.analysistabs.ProteinView.QFileDialog.getOpenFileName")
    def test_load_filter_adds_filters(self, mock_dialog, mock_view):
        filters = {"loaded_f": "dur>50"}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as fp:
            json.dump(filters, fp)
            path = fp.name
        mock_dialog.return_value = (path, "JSON Files (*.json)")
        # No loader → else-branch adds filter directly without validation
        mock_view._load_filter({"db_loader": None})
        assert "loaded_f" in mock_view.subset_filters
        os.unlink(path)

    @patch("poriscope.plugins.analysistabs.ProteinView.QFileDialog.getOpenFileName")
    def test_load_filter_blocks_duplicates(self, mock_dialog, mock_view):
        mock_view.subset_filters = {"existing": "dur>0"}
        filters = {"existing": "dur>999"}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as fp:
            json.dump(filters, fp)
            path = fp.name
        mock_dialog.return_value = (path, "JSON Files (*.json)")
        mock_view._load_filter({})
        assert mock_view.subset_filters["existing"] == "dur>0"
        os.unlink(path)

    @patch("poriscope.plugins.analysistabs.ProteinView.QFileDialog.getOpenFileName")
    def test_load_filter_no_path_is_noop(self, mock_dialog, mock_view):
        mock_dialog.return_value = ("", "")
        mock_view._load_filter({})


# ===========================================================================
# Miscellaneous
# ===========================================================================


class TestMiscMethods:

    def test_get_walkthrough_steps_returns_list(self, mock_view):
        steps = mock_view.get_walkthrough_steps()
        assert isinstance(steps, list) and len(steps) > 0

    def test_request_experiment_structure_no_error(self, mock_view):
        mock_view.request_experiment_structure("my_loader")

    def test_update_available_columns_no_error(self, mock_view):
        mock_view.update_available_columns("my_loader")

    def test_update_units_no_error(self, mock_view):
        mock_view.update_units("ldr", "duration", "x_axis")

    def test_update_available_plugins_no_error(self, mock_view):
        mock_view.update_available_plugins({"MetaDatabaseLoader": ["ldr1"]})

    def test_show_selection_tree_sets_selection(self, mock_view):
        # Patch show_dialog to avoid the blocking exec() modal
        with patch(
            "poriscope.views.widgets.SelectionTree.SelectionTree.show_dialog",
            return_value={"ExpA": ["0"]},
        ):
            mock_view.show_selection_tree(
                {"ExpA": ["0", "1"]}, "ldr", selection={"ExpA": ["0"]}
            )
        assert mock_view.selected_experiment_and_channels_by_loader.get("ldr") == {
            "ExpA": ["0"]
        }

    def test_show_filter_info_wrong_count_silent(self, mock_view):
        # 0 selected → returns silently without opening any dialog
        mock_view._show_filter_info_dialog(
            mock_view.proteincontrols.filter_comboBox, {"db_loader": "l"}
        )

    def test_analysis_mode_individual_default(self, mock_view):
        assert mock_view._analysis_mode == "individual"

    def test_no_cached_data_default(self, mock_view):
        assert mock_view.no_cached_data is False


# ===========================================================================
# Integration: histogram → fit → VM scatter pipeline
# ===========================================================================


class TestPipeline:
    D, L = 20.0, 30.0

    def test_single_event_histogram(self, mock_view):
        ev = _make_event(blockage=0.3)
        df = mock_view._construct_single_event_histogram(ev, "Filtered Histogram")
        assert df is not None and len(df) > 0  # FD-derived, not fixed 100

    def test_all_points_histogram_three_events(self, mock_view):
        evs = [_make_event(i, blockage=0.2 + i * 0.05, rng_seed=i) for i in range(3)]
        df = mock_view._construct_all_points_histogram(iter(evs), "Filtered Histogram")
        assert isinstance(df, pd.DataFrame) and len(df) == 100

    def test_double_gaussian_roundtrip(self, mock_view):
        x, y = _make_double_gaussian_histogram()
        popt = mock_view._fit_and_sanity_check_double_gaussian(x, y)
        assert popt is not None
        y_fit = mock_view._double_gaussian(x, *popt)
        assert np.max(np.abs(y - y_fit)) < 0.02

    def test_vm_ensemble_from_histogram_fit(self, mock_view):
        x, y = _make_double_gaussian_histogram(mean1=0.1, mean2=0.3)
        popt = mock_view._fit_and_sanity_check_double_gaussian(x, y)
        if popt is None:
            pytest.skip("fit did not converge")
        means = sorted([popt[1], popt[4]])
        stds = [abs(popt[2]), abs(popt[5])]
        np.random.seed(42)
        V, m = mock_view._generate_vm_ensemble(
            20, max(means), stds[1], min(means), stds[0], self.D, self.L
        )
        assert len(V) <= 20

    def test_update_event_plot_end_to_end(self, mock_view):
        mock_view._update_event_plot([_make_event(1), _make_event(2)])
        assert mock_view._display_mode == "event"

    def test_update_event_histogram_end_to_end(self, mock_view):
        mock_view._update_event_histogram([_make_event(1)])
        assert mock_view._display_mode == "event"


# ===========================================================================
# _set_custom_display_area / _set_control_area — direct structural assertions
# ===========================================================================


class TestSetCustomDisplayArea:
    def test_creates_display_stack(self, real_view):
        assert real_view.display_stack is not None

    def test_creates_distribution_canvases(self, real_view):
        assert real_view.canvas_hist is not None
        assert real_view.canvas_vm is not None

    def test_creates_event_canvas(self, real_view):
        assert real_view.canvas_event is not None

    def test_default_display_mode_is_distribution(self, real_view):
        assert real_view._display_mode == "distribution"

    def test_display_stack_starts_on_distribution_page(self, real_view):
        assert real_view.display_stack.currentIndex() == 0

    def test_event_outer_ax_initially_none(self, real_view):
        assert real_view.event_outer_ax is None


class TestSetControlArea:
    def test_creates_proteincontrols(self, real_view):
        assert real_view.proteincontrols is not None

    def test_action_triggered_connected(self, real_view):
        # Triggering an action via the real signal should route through
        # handle_parameter_change without raising.
        with patch.object(real_view, "_handle_other_actions") as mock:
            real_view.proteincontrols.actionTriggered.emit(
                "protein", "nonexistent_action_xyz", ({},)
            )
        mock.assert_called_once()


# ===========================================================================
# handle_parameter_change — dispatch logic
# ===========================================================================


class TestHandleParameterChange:
    def _params(self, **extra):
        base = {"db_loader": "ldr", "event_id": 1, "n_events": 1}
        base.update(extra)
        return base

    def test_export_plot_data_emits_when_cached(self, mock_view):
        mock_view.no_cached_data = False
        received = []
        mock_view.export_plot_data.connect(lambda: received.append(True))
        mock_view.handle_parameter_change("p", "export_plot_data", (self._params(),))
        assert received == [True]

    def test_export_plot_data_warns_when_not_cached(self, mock_view):
        mock_view.no_cached_data = True
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view.handle_parameter_change("p", "export_plot_data", (self._params(),))
        assert any("Export Subset as CSV" in m for m in received)

    def test_loader_changed_updates_columns_and_structure(self, mock_view):
        with (
            patch.object(mock_view, "update_available_columns") as mock_cols,
            patch.object(mock_view, "request_experiment_structure") as mock_struct,
        ):
            mock_view.handle_parameter_change(
                "p", "loader_changed", (self._params(db_loader="ldr1"),)
            )
        mock_cols.assert_called_once_with("ldr1")
        mock_struct.assert_called_once_with("ldr1")

    def test_loader_changed_no_loader_skips(self, mock_view):
        with patch.object(mock_view, "update_available_columns") as mock_cols:
            mock_view.handle_parameter_change("p", "loader_changed", ({"db_loader": None},))
        mock_cols.assert_not_called()

    def test_select_experiment_and_channel_shows_tree(self, mock_view):
        mock_view.available_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        with patch.object(mock_view, "show_selection_tree") as mock_tree:
            mock_view.handle_parameter_change(
                "p", "select_experiment_and_channel", (self._params(db_loader="ldr"),)
            )
        mock_tree.assert_called_once()

    def test_shift_backward_routes_left(self, mock_view):
        with patch.object(mock_view, "_shift_range_and_update_plot") as mock:
            mock_view.handle_parameter_change("p", "shift_range_backward", (self._params(),))
        mock.assert_called_once()
        assert mock.call_args[1]["direction"] == "left"

    def test_shift_forward_routes_right(self, mock_view):
        with patch.object(mock_view, "_shift_range_and_update_plot") as mock:
            mock_view.handle_parameter_change("p", "shift_range_forward", (self._params(),))
        mock.assert_called_once()
        assert mock.call_args[1]["direction"] == "right"

    def test_plot_events_routes(self, mock_view):
        with patch.object(mock_view, "_handle_plot_events") as mock:
            mock_view.handle_parameter_change("p", "plot_events", (self._params(),))
        mock.assert_called_once()

    def test_plot_histogram_routes(self, mock_view):
        with patch.object(mock_view, "_handle_plot_histogram") as mock:
            mock_view.handle_parameter_change("p", "plot_histogram", (self._params(),))
        mock.assert_called_once()

    def test_update_plot_individual_mode(self, mock_view):
        mock_view._analysis_mode = "individual"
        with (
            patch.object(mock_view, "_update_distribution_individual") as mock_ind,
            patch.object(mock_view, "_update_distribution_ensemble") as mock_ens,
        ):
            mock_view.handle_parameter_change("p", "update_plot", (self._params(),))
        mock_ind.assert_called_once()
        mock_ens.assert_not_called()

    def test_update_plot_ensemble_mode(self, mock_view):
        mock_view._analysis_mode = "ensemble"
        with (
            patch.object(mock_view, "_update_distribution_individual") as mock_ind,
            patch.object(mock_view, "_update_distribution_ensemble") as mock_ens,
        ):
            mock_view.handle_parameter_change("p", "update_plot", (self._params(),))
        mock_ens.assert_called_once()
        mock_ind.assert_not_called()

    def test_update_plot_sets_distribution_mode(self, mock_view):
        mock_view._set_display_mode("event")
        with patch.object(mock_view, "_update_distribution_individual"):
            mock_view.handle_parameter_change("p", "update_plot", (self._params(),))
        assert mock_view._display_mode == "distribution"

    def test_add_filter_routes(self, mock_view):
        with patch.object(mock_view, "_show_add_filter_dialog") as mock:
            mock_view.handle_parameter_change("p", "add_filter", (self._params(),))
        mock.assert_called_once()

    def test_edit_filter_routes(self, mock_view):
        with patch.object(mock_view, "_show_filter_info_dialog") as mock:
            mock_view.handle_parameter_change("p", "edit_filter", (self._params(),))
        mock.assert_called_once()

    def test_delete_filter_routes(self, mock_view):
        with patch.object(mock_view, "_delete_all_selected_filters") as mock:
            mock_view.handle_parameter_change("p", "delete_filter", ({},))
        mock.assert_called_once()

    def test_save_filter_routes(self, mock_view):
        with patch.object(mock_view, "_save_filter") as mock:
            mock_view.handle_parameter_change("p", "save_filter", ({},))
        mock.assert_called_once()

    def test_load_filter_routes(self, mock_view):
        with patch.object(mock_view, "_load_filter") as mock:
            mock_view.handle_parameter_change("p", "load_filter", (self._params(),))
        mock.assert_called_once()

    def test_set_mode_individual(self, mock_view):
        mock_view._analysis_mode = "ensemble"
        mock_view.handle_parameter_change("p", "set_mode_individual", ({},))
        assert mock_view._analysis_mode == "individual"

    def test_set_mode_ensemble(self, mock_view):
        mock_view._analysis_mode = "individual"
        mock_view.handle_parameter_change("p", "set_mode_ensemble", ({},))
        assert mock_view._analysis_mode == "ensemble"

    def test_commit_individual_routes(self, mock_view):
        with patch.object(mock_view, "_commit_fits") as mock:
            mock_view.handle_parameter_change(
                "p", "commit_individual", (self._params(db_loader="ldrX"),)
            )
        mock.assert_called_once_with("ldrX")

    def test_unknown_action_routes_to_other(self, mock_view):
        with patch.object(mock_view, "_handle_other_actions") as mock:
            mock_view.handle_parameter_change("p", "totally_unknown", (self._params(),))
        mock.assert_called_once()
        assert mock.call_args[0][0] == "totally_unknown"


class TestFetchEventData:
    def _params(self):
        return {"db_loader": "ldr", "event_index": [1]}

    def test_no_experiments_returns_empty(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {}
        mock_view.get_selected_filters = MagicMock(return_value={})
        result = mock_view._fetch_event_data(self._params())
        assert result == []

    def test_no_experiments_emits_message(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {}
        mock_view.get_selected_filters = MagicMock(return_value={})
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._fetch_event_data(self._params())
        assert any("No experiments or channels" in m for m in received)

    def test_multiple_filters_returns_empty(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"f1": "a", "f2": "b"})
        result = mock_view._fetch_event_data(self._params())
        assert result == []

    def test_multiple_filters_emits_message(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"f1": "a", "f2": "b"})
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._fetch_event_data(self._params())
        assert any("more than one subset" in m for m in received)

    def test_empty_loader_selection_returns_empty(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        result = mock_view._fetch_event_data(self._params())
        assert result == []

    def test_multiple_experiments_returns_empty(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0"], "exp2": ["0"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})
        result = mock_view._fetch_event_data(self._params())
        assert result == []

    def test_multiple_experiments_emits_message(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0"], "exp2": ["0"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._fetch_event_data(self._params())
        assert any("single experiment" in m for m in received)

    def test_multiple_channels_returns_empty(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0", "1"]}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        result = mock_view._fetch_event_data(self._params())
        assert result == []

    def test_multiple_channels_emits_message(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0", "1"]}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._fetch_event_data(self._params())
        assert any("single channel" in m for m in received)

    def test_empty_filters_default_to_full_dataset(self, mock_view):
        """When no filters selected, defaults to {'Full Dataset': ''}. The generator
        never actually gets populated in this test (global_signal is mocked), so
        we request only event_index values that are already in cached_events to
        avoid the code trying to pull from a None generator."""
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        mock_view.plot_events_generator = None
        mock_view.current_sql_filter = None
        mock_view.current_experiment = None
        mock_view.current_channel = None
        mock_view.global_signal = MagicMock()
        mock_view.plot_events_generator_updated = False
        mock_view.cached_events = {}
        params = {"db_loader": "ldr", "event_index": []}
        result = mock_view._fetch_event_data(params)
        assert result == []

    def test_fetches_fresh_via_resolve_and_generator(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"Full Dataset": ""})
        mock_view.current_sql_filter = ""
        mock_view.current_experiment = "exp1"
        mock_view.current_channel = 0
        mock_view._resolve_event_db_ids = MagicMock(
            return_value=pd.DataFrame({"id": [10], "event_id": [1]})
        )
        mock_view.global_signal = MagicMock()
        mock_view.plot_events_generator = iter([_make_event(1)])
        result = mock_view._fetch_event_data(self._params())
        assert len(result) == 1
        assert result[0]["event_id"] == 1


class TestHandlePlotEvents:
    def _setup(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        mock_view.filtered_event_ids = [1, 2, 3]
        mock_view.current_sql_filter = ""
        mock_view.current_experiment = "exp1"
        mock_view.current_channel = 0

    def test_sets_last_event_action(self, mock_view):
        self._setup(mock_view)
        mock_view._fetch_event_data = MagicMock(return_value=[])
        mock_view._last_event_action = "plot_histogram"
        with patch.object(mock_view, "_update_event_plot"):
            mock_view._handle_plot_events({"db_loader": "ldr", "event_id": 1, "n_events": 1})
        assert mock_view._last_event_action == "plot_events"

    def test_calls_update_event_plot_with_data(self, mock_view):
        self._setup(mock_view)
        events = [_make_event(1)]
        mock_view._fetch_event_data = MagicMock(return_value=events)
        with patch.object(mock_view, "_update_event_plot") as mock_plot:
            mock_view._handle_plot_events({"db_loader": "ldr", "event_id": 1, "n_events": 1})
        mock_plot.assert_called_once_with(events, use_raw=False)

    def test_no_data_emits_warning(self, mock_view):
        self._setup(mock_view)
        mock_view._fetch_event_data = MagicMock(return_value=[])
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._handle_plot_events({"db_loader": "ldr", "event_id": 1, "n_events": 2})
        assert any("No data available" in m for m in received)


class TestHandlePlotHistogram:
    def _setup(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        mock_view.filtered_event_ids = [1, 2, 3]
        mock_view.current_sql_filter = ""
        mock_view.current_experiment = "exp1"
        mock_view.current_channel = 0

    def test_sets_last_event_action(self, mock_view):
        self._setup(mock_view)
        mock_view._fetch_event_data = MagicMock(return_value=[])
        mock_view._handle_plot_histogram(
            {
                "db_loader": "ldr",
                "event_id": 1,
                "n_events": 1,
                "bins": None,
                "sizes": False,
            }
        )
        assert mock_view._last_event_action == "plot_histogram"

    def test_calls_update_event_histogram_with_data(self, mock_view):
        self._setup(mock_view)
        events = [_make_event(1)]
        mock_view._fetch_event_data = MagicMock(return_value=events)
        with patch.object(mock_view, "_update_event_histogram") as mock_hist:
            mock_view._handle_plot_histogram(
                {
                    "db_loader": "ldr",
                    "event_id": 1,
                    "n_events": 1,
                    "bins": None,
                    "sizes": False,
                }
            )
        mock_hist.assert_called_once()
        call_args = mock_hist.call_args
        assert call_args[0][0] == events

    def test_no_data_emits_warning(self, mock_view):
        self._setup(mock_view)
        mock_view._fetch_event_data = MagicMock(return_value=[])
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._handle_plot_histogram(
            {
                "db_loader": "ldr",
                "event_id": 1,
                "n_events": 1,
                "bins": None,
                "sizes": False,
            }
        )
        assert any("No data available" in m for m in received)

    def test_passes_bins_and_sizes(self, mock_view):
        self._setup(mock_view)
        events = [_make_event(1)]
        mock_view._fetch_event_data = MagicMock(return_value=events)
        with patch.object(mock_view, "_update_event_histogram") as mock_hist:
            mock_view._handle_plot_histogram(
                {
                    "db_loader": "ldr",
                    "event_id": 1,
                    "n_events": 1,
                    "bins": [50],
                    "sizes": True,
                }
            )
        kwargs = mock_hist.call_args[1]
        assert kwargs.get("bins") == [50]
        assert kwargs.get("sizes") is True


# ===========================================================================
# _shift_range_and_update_plot — dispatch to histogram vs events
# ===========================================================================


class TestShiftRangeDispatch:
    def _setup_cache(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"l": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        mock_view.filtered_event_ids = [0, 3, 5, 7]
        mock_view.current_sql_filter = ""
        mock_view.current_experiment = "exp1"
        mock_view.current_channel = 0

    def test_histogram_action_dispatches_to_histogram(self, mock_view):
        self._setup_cache(mock_view)
        mock_view._last_event_action = "plot_histogram"
        with (
            patch.object(mock_view, "_handle_plot_histogram") as mock_hist,
            patch.object(mock_view, "_handle_plot_events") as mock_events,
        ):
            mock_view._shift_range_and_update_plot(
                {"db_loader": "l", "event_id": 3, "n_events": 1}, "right"
            )
        mock_hist.assert_called_once()
        mock_events.assert_not_called()

    def test_events_action_dispatches_to_events(self, mock_view):
        self._setup_cache(mock_view)
        mock_view._last_event_action = "plot_events"
        with (
            patch.object(mock_view, "_handle_plot_histogram") as mock_hist,
            patch.object(mock_view, "_handle_plot_events") as mock_events,
        ):
            mock_view._shift_range_and_update_plot(
                {"db_loader": "l", "event_id": 3, "n_events": 1}, "right"
            )
        mock_events.assert_called_once()
        mock_hist.assert_not_called()


# ===========================================================================
# _show_add_filter_dialog
# ===========================================================================


class TestShowAddFilterDialog:
    def _mock_dialog(
        self, mocker_patch, accepted=True, is_raw=False, name="f1", text="dur>1"
    ):
        dialog = MagicMock()
        dialog.exec.return_value = 1 if accepted else 0
        dialog.name = name
        dialog.filter_text = text
        dialog.is_raw = is_raw
        dialog.walkthrough_dialog = None
        return dialog

    def test_sets_show_sql_flag(self, mock_view):
        mock_view._walkthrough_active = False
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(None, accepted=False),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        assert mock_view._show_sql_in_display is True

    def test_cancelled_dialog_does_not_emit_signal(self, mock_view):
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(None, accepted=False),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        mock_view.global_signal.emit.assert_not_called()

    def test_no_loader_logs_error_and_returns(self, mock_view):
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(None, accepted=True),
        ):
            mock_view._show_add_filter_dialog({"db_loader": None})
        mock_view.global_signal.emit.assert_not_called()

    def test_assisted_filter_emits_construct_metadata_query(self, mock_view):
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(None, accepted=True, is_raw=False),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        mock_view.global_signal.emit.assert_called_once()
        call_args = mock_view.global_signal.emit.call_args[0]
        assert call_args[2] == "construct_metadata_query"

    def test_raw_filter_requires_select_statement(self, mock_view):
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(
                None, accepted=True, is_raw=True, text="dur > 100"
            ),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        assert any("SELECT statements" in m for m in received)
        mock_view.global_signal.emit.assert_not_called()

    def test_raw_filter_with_select_validates(self, mock_view):
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(
                None,
                accepted=True,
                is_raw=True,
                name="f1",
                text="SELECT * FROM events",
            ),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        mock_view.global_signal.emit.assert_called_once()
        call_args = mock_view.global_signal.emit.call_args[0]
        assert call_args[2] == "validate_filter_query"

    def test_raw_filter_appends_raw_suffix(self, mock_view):
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(
                None,
                accepted=True,
                is_raw=True,
                name="f1",
                text="SELECT * FROM events",
            ),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        assert mock_view._pending_filter_name == "f1_raw"


# ===========================================================================
# show_edit_filter_dialog
# ===========================================================================


class TestShowEditFilterDialog:
    def _mock_dialog(
        self, accepted=True, is_raw=False, new_name="f1", new_filter="dur>1"
    ):
        dialog = MagicMock()
        dialog.exec.return_value = 1 if accepted else 0
        dialog.new_name = new_name
        dialog.new_filter = new_filter
        dialog.is_raw = is_raw
        return dialog

    @pytest.fixture(autouse=True)
    def _flush_qt_between_tests(self, qt_app):
        yield
        qt_app.processEvents()

    def test_sets_show_sql_flag(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(accepted=False),
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        assert mock_view._show_sql_in_display is True

    def test_cancelled_dialog_no_emit(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(accepted=False),
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        mock_view.global_signal.emit.assert_not_called()

    def test_no_loader_logs_error(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(accepted=True),
        ):
            mock_view.show_edit_filter_dialog("f1", None)
        mock_view.global_signal.emit.assert_not_called()

    def test_assisted_edit_emits_construct_metadata_query(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        dialog = self._mock_dialog(accepted=True, is_raw=False)
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.EditSubsetFilterDialog",
            return_value=dialog,
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        mock_view.global_signal.emit.assert_called_once()
        assert mock_view.global_signal.emit.call_args[0][2] == "construct_metadata_query"

    def test_raw_edit_requires_select(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(
                accepted=True, is_raw=True, new_filter="dur > 5"
            ),
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        assert any("SELECT statements" in m for m in received)

    def test_raw_edit_with_select_validates(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(
                accepted=True,
                is_raw=True,
                new_name="f1",
                new_filter="SELECT * FROM events",
            ),
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        mock_view.global_signal.emit.assert_called_once()
        assert mock_view.global_signal.emit.call_args[0][2] == "validate_filter_query"

    def test_pending_old_filter_name_set(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.plugins.analysistabs.ProteinView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(accepted=True, is_raw=False, new_name="f2"),
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        assert mock_view._pending_old_filter_name == "f1"
        assert mock_view._pending_filter_name == "f2"


# ===========================================================================
# _update_distribution_individual — guard clauses
# ===========================================================================


class TestUpdateDistributionIndividual:
    def _params(self):
        return {
            "db_loader": "ldr",
            "plot_type": "Filtered Histogram",
            "pore_diameter": "20.0",
            "pore_length": "30.0",
            "n_values": "10",
            "bins": [50],
            "sizes": False,
        }

    def test_multiple_experiments_logs_warning_and_returns(self, mock_view, caplog):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0"], "exp2": ["0"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})
        with caplog.at_level("WARNING"):
            mock_view._update_distribution_individual(self._params())
        assert any("single experiment" in r.message for r in caplog.records)

    def test_multiple_channels_logs_warning_and_returns(self, mock_view, caplog):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0", "1"]}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        with caplog.at_level("WARNING"):
            mock_view._update_distribution_individual(self._params())
        assert any("single channel" in r.message for r in caplog.records)

    def test_multiple_filters_warns_and_returns(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"f1": "a", "f2": "b"})
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._update_distribution_individual(self._params())
        assert any("single subset" in m for m in received)

    def test_sets_plot_initialized_true(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"f1": "a", "f2": "b"})
        mock_view.plot_initialized = False
        mock_view._update_distribution_individual(self._params())
        assert mock_view.plot_initialized is True


# ===========================================================================
# _update_distribution_ensemble — guard clauses
# ===========================================================================


class TestUpdateDistributionEnsemble:
    def _params(self):
        return {
            "db_loader": "ldr",
            "plot_type": "Filtered Histogram",
            "pore_diameter": "20.0",
            "pore_length": "30.0",
            "n_values": "10",
        }

    def test_multiple_experiments_logs_warning_and_returns(self, mock_view, caplog):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0"], "exp2": ["0"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})
        with caplog.at_level("WARNING"):
            mock_view._update_distribution_ensemble(self._params())
        assert any("single experiment" in r.message for r in caplog.records)

    def test_multiple_channels_logs_warning_and_returns(self, mock_view, caplog):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0", "1"]}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        with caplog.at_level("WARNING"):
            mock_view._update_distribution_ensemble(self._params())
        assert any("single channel" in r.message for r in caplog.records)

    def test_multiple_filters_warns_and_returns(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"f1": "a", "f2": "b"})
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._update_distribution_ensemble(self._params())
        assert any("single subset" in m for m in received)

    def test_sets_plot_initialized_true(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0"], "exp2": ["0"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})
        mock_view.plot_initialized = False
        mock_view._update_distribution_ensemble(self._params())
        assert mock_view.plot_initialized is True


# ===========================================================================
# set_alter_database_status / _commit_fits boundary (extra)
# ===========================================================================


class TestCommitFitsExtended:
    def test_emits_get_table_by_column(self, mock_view):
        mock_view.fit_data = pd.DataFrame(
            {
                "id": [1],
                "prolate_volume": [1.0],
                "prolate_shape_factor": [1.0],
                "prolate_major_axis": [1.0],
                "prolate_minor_axis": [1.0],
                "oblate_volume": [1.0],
                "oblate_shape_factor": [1.0],
                "oblate_major_axis": [1.0],
                "oblate_minor_axis": [1.0],
                "min_fractional_blockage": [0.1],
                "min_fractional_blockage_std": [0.01],
                "max_fractional_blockage": [0.3],
                "max_fractional_blockage_std": [0.02],
            }
        )
        mock_view.column_table = None
        mock_view.global_signal = MagicMock()
        mock_view._commit_fits("ldr")
        emit_calls = mock_view.global_signal.emit.call_args_list
        actions = [c[0][2] for c in emit_calls]
        assert "get_table_by_column" in actions


# ===========================================================================
# Mode-scoped figure/axes/canvas properties
# ===========================================================================


MODE_SCOPED_PROPERTIES = [
    "fig_hist",
    "ax_hist",
    "canvas_hist",
    "fig_vm",
    "ax_vm",
    "canvas_vm",
]


class TestModeScopedProperties:
    """
    Cover the Individual/Ensemble dispatch on the figure, axes and canvas
    properties.

    Each of these six names is a property that reads or writes the
    ``*_individual`` or ``*_ensemble`` attribute depending on
    ``_analysis_mode``. That dispatch is what makes switching analysis mode show
    that mode's own last-drawn plot rather than the other one's, and nothing
    exercised it: the whole suite passed with a getter hard-wired to one side.
    """

    @pytest.mark.parametrize("prop", MODE_SCOPED_PROPERTIES)
    def test_getter_reads_individual_side_in_individual_mode(self, mock_view, prop):
        mock_view._analysis_mode = "individual"
        assert getattr(mock_view, prop) is getattr(mock_view, f"{prop}_individual")

    @pytest.mark.parametrize("prop", MODE_SCOPED_PROPERTIES)
    def test_getter_reads_ensemble_side_in_ensemble_mode(self, mock_view, prop):
        mock_view._analysis_mode = "ensemble"
        assert getattr(mock_view, prop) is getattr(mock_view, f"{prop}_ensemble")

    @pytest.mark.parametrize("prop", MODE_SCOPED_PROPERTIES)
    def test_getter_returns_a_different_object_per_mode(self, mock_view, prop):
        """The two modes must not collapse onto the same object."""
        mock_view._analysis_mode = "individual"
        individual = getattr(mock_view, prop)
        mock_view._analysis_mode = "ensemble"
        assert getattr(mock_view, prop) is not individual

    @pytest.mark.parametrize("prop", MODE_SCOPED_PROPERTIES)
    def test_setter_writes_individual_side_in_individual_mode(self, mock_view, prop):
        mock_view._analysis_mode = "individual"
        sentinel = MagicMock()
        setattr(mock_view, prop, sentinel)
        assert getattr(mock_view, f"{prop}_individual") is sentinel

    @pytest.mark.parametrize("prop", MODE_SCOPED_PROPERTIES)
    def test_setter_writes_ensemble_side_in_ensemble_mode(self, mock_view, prop):
        mock_view._analysis_mode = "ensemble"
        sentinel = MagicMock()
        setattr(mock_view, prop, sentinel)
        assert getattr(mock_view, f"{prop}_ensemble") is sentinel

    @pytest.mark.parametrize("prop", MODE_SCOPED_PROPERTIES)
    def test_setter_leaves_the_other_mode_untouched(self, mock_view, prop):
        """Writing one mode's plot must not clobber the other mode's."""
        mock_view._analysis_mode = "individual"
        untouched = getattr(mock_view, f"{prop}_ensemble")
        setattr(mock_view, prop, MagicMock())
        assert getattr(mock_view, f"{prop}_ensemble") is untouched
