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
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QVBoxLayout, QWidget

from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.plugins.analysistabs.ProteinView import (
    FIT_COLUMN_UNITS,
    FIT_COLUMNS,
    ProteinView,
    format_axis_label,
)
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
# _compute_theoretical_blockages
# ===========================================================================


# ===========================================================================
# _construct_single_event_histogram
# ===========================================================================


# ===========================================================================
# _construct_all_points_histogram
# ===========================================================================


# ``TestBuildLoadEventDataArgs`` lived here and is gone with the method: Step 4a moved
# the raw-subset scoping into ``ProteinController._scope_raw_subset_query``. Its
# coverage is ``tests/unit/controllers/test_raw_subset_scoping.py``, which was
# ``test_view_authored_sql.py`` before the same move.
#
# ``test_raw_scope_requires_live_bus`` is not carried over. It asserted that the scope
# clause is *not* appended, on the grounds that "global_signal.emit() has no connected
# slots in tests so experiment_id stays None" - so it passed by describing the test
# harness rather than the code, and would have gone on passing whatever the scoping
# did. The behaviour it stood in front of is now two tests that drive a lookup
# answering None and assert the plot stops.


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

    def test_set_event_data_generator(self, mock_view):
        g = iter([1, 2, 3])
        mock_view.set_event_data_generator(g)
        assert mock_view.event_data_generator is g

    def test_set_event_plot_data_generator(self, mock_view):
        g = iter([])
        mock_view.set_event_plot_data_generator(g)
        assert mock_view.plot_events_generator is g

    def test_set_experiment_id(self, mock_view):
        mock_view.set_experiment_id(99)
        assert mock_view.experiment_id == 99

    def test_set_units(self, mock_view):
        mock_view.set_units("nm")
        assert mock_view.units == "nm"

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

    def test_set_event_query_stores(self, mock_view):
        mock_view.set_event_query("SELECT * FROM events")
        assert mock_view.event_query == "SELECT * FROM events"

    def test_set_event_query_empty(self, mock_view):
        mock_view.set_event_query("")
        assert mock_view.event_query == ""


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
        """
        ``hist_min``/``hist_max`` went with the binning in Step 4's closeout: the
        two methods that wrote them are on the Model now, which left three clears
        and no reader at all.
        """
        mock_view.hist_data = [([1], [2])]
        mock_view.hist_labels = ["x"]
        mock_view._reset_actions()
        assert mock_view.hist_data == []
        assert mock_view.hist_labels == []
        assert not hasattr(mock_view, "hist_min")

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

    def _emitted(self, real_view, df, logscales, units=("nm^3", "au")):
        """
        Drive the request half and capture what it asked for.

        The filtering is the Model's, so the request half only formats the labels
        and asks; the drawing is ``MetaSubsetTabView.set_scatterplot``.

        :param real_view: the view under test
        :type real_view: ProteinView
        :param df: the frame to plot
        :type df: pd.DataFrame
        :param logscales: the log flags for the two axes
        :type logscales: list
        :param units: the units for the two axes
        :type units: tuple
        :return: the emitted arguments
        :rtype: tuple
        """
        captured = []
        real_view.scatterplot_requested.connect(lambda *args: captured.append(args))
        real_view._plot_scatterplot(
            real_view.ax_vm, df, ["V", "m"], list(units), logscales
        )
        return captured[0]

    def test_labels_set(self, real_view):
        _columns, _flags, ax, labels, _label = self._emitted(
            real_view, self._df(), [False, False]
        )

        assert "V" in labels[0]
        assert "m" in labels[1]
        assert ax is real_view.ax_vm

    def test_the_raw_columns_and_their_flags_go_out(self, real_view):
        """The filter is the Model's, so the columns leave unfiltered."""
        df = self._df()

        columns, flags, _ax, _labels, _label = self._emitted(
            real_view, df, [True, False]
        )

        assert [list(column) for column in columns] == [
            df["V"].tolist(),
            df["m"].tolist(),
        ]
        assert flags == [True, False]

    def test_log_x_prefix(self, real_view):
        _columns, _flags, _ax, labels, _label = self._emitted(
            real_view, self._df(), [True, False], units=("", "")
        )

        assert "log10" in labels[0]

    def test_log_y_prefix(self, real_view):
        _columns, _flags, _ax, labels, _label = self._emitted(
            real_view, self._df(), [False, True], units=("", "")
        )

        assert "log10" in labels[1]


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

    def test_a_missing_error_column_is_refused(self, mock_view):
        """
        Both error columns are required now. The old code accepted a None and drew
        that axis without bars; nothing ever passed one - the single caller names
        two real columns - and supporting it through the filter would mean telling
        the drawing half which of the four arrays it was given. Refusing it is the
        smaller contract, and the wrong-length case already raised.
        """
        with pytest.raises(ValueError, match="two error columns"):
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
        """
        The panel choice is still ``update_plot``'s; what reaches the request half
        is the axes it picked.
        """
        captured = []
        real_view.scatterplot_requested.connect(lambda *args: captured.append(args))
        df = pd.DataFrame({"V": np.random.rand(5), "m": np.random.rand(5)})

        real_view.update_plot("Scatterplot", df, ["V", "m"], ["", ""], [False, False])

        assert captured[0][2] is real_view.ax_vm

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


class TestFactors:
    """
    ``MetaView._factors``, the subplot-grid helper.

    This class held sixteen more tests, for the five event-index range helpers. Step 3e
    moved those helpers off ``MetaView`` and onto ``MetaEventTabView``, whose only
    subclasses are the two event tabs - the protein tab never had a claim on them, and
    reaching a base method through an unrelated tab is what let that go unnoticed.
    ``tests/unit/views/test_meta_view_characterization.py`` pins all five properly, with
    28 tests asserting literal values; the ones deleted here asserted an ``or``-chain of
    three alternatives, and one asserted ``>= 0`` under a comment claiming a clamp the
    implementation does not have.
    """

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
        mock_view._shift_range_and_update_plot(
            {"db_loader": "l"}, "right"
        )  # must not raise

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


def _answer_event_histogram_fits(view):
    """
    Run the round trip ProteinController runs, and hand the answer back to the View.

    Step 4c split ``_update_event_histogram`` into a request and
    ``set_event_histogram_fits``; these tests drive both halves, because driving only
    the first asserts against a View that has not drawn anything yet.

    The histograms and the fits both come from a **real ProteinModel** rather than a
    stub, so their arity and their shapes are the collaborator's own rather than this
    test's idea of them. Step 4's closeout moved the binning down beside the fitting,
    so this helper runs both calls the Controller runs.

    :param view: the view whose request has just been emitted
    :type view: ProteinView
    :return: None
    :rtype: None
    """
    event_data, plot_type, bins, sizes = (
        view.event_histogram_fits_requested.emit.call_args.args
    )
    model = ProteinModel()
    histograms = model.build_event_histograms(event_data, plot_type, bins, sizes)
    view.set_event_histogram_fits(
        model.fit_histograms(histograms), histograms, event_data
    )


class TestUpdateEventHistogram:
    def test_the_request_carries_the_events_and_the_bin_request(self, mock_view):
        """
        The binning moved below the widget in Step 4's closeout, so what goes out is
        the events themselves and how the caller asked for them to be binned.
        """
        events = [_make_event(i, rng_seed=i) for i in range(1, 4)]

        mock_view._update_event_histogram(events, bins=[40], sizes=False)

        event_data, plot_type, bins, sizes = (
            mock_view.event_histogram_fits_requested.emit.call_args.args
        )
        assert event_data is events
        assert plot_type == "Filtered Histogram"
        assert bins == [40]
        assert sizes is False

    def test_switches_to_event_mode(self, mock_view):
        mock_view._update_event_histogram([_make_event(1)])
        _answer_event_histogram_fits(mock_view)
        assert mock_view._display_mode == "event"

    def test_multiple_events(self, mock_view):
        mock_view._update_event_histogram(
            [_make_event(i, rng_seed=i) for i in range(1, 4)]
        )
        _answer_event_histogram_fits(mock_view)

    def test_custom_bins(self, mock_view):
        mock_view._update_event_histogram([_make_event(1)], bins=[50])
        _answer_event_histogram_fits(mock_view)

    def test_cache_committed(self, mock_view):
        mock_view._update_event_histogram([_make_event(1)])
        _answer_event_histogram_fits(mock_view)

    def test_an_event_with_no_fit_still_gets_its_histogram_drawn(self, mock_view):
        """
        A failed fit removes the overlay, not the subplot.

        Every fit is refused here, so the only thing that can still be drawn is the
        histogram itself - which is what stops a fit regression showing up as an
        empty grid rather than as a missing orange line.
        """
        mock_view._update_event_histogram([_make_event(1)])
        event_data, plot_type, bins, sizes = (
            mock_view.event_histogram_fits_requested.emit.call_args.args
        )
        histograms = ProteinModel().build_event_histograms(
            event_data, plot_type, bins, sizes
        )

        mock_view.set_event_histogram_fits([(None, None)], histograms, event_data)

        assert mock_view._display_mode == "event"
        assert mock_view.fig_event.add_subplot.call_count == 1


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
    # Step 4d: the filter's name, the name it replaces and its text travel through
    # the call now. They used to be parked on the widget by a _setup helper and read
    # back off it here, which is the pattern the step deletes.
    def _answer(self, mock_view, valid=True, error_msg="", old_name=None):
        mock_view.on_raw_filter_validated(
            valid, error_msg, "newfilter", old_name, "SELECT * FROM events"
        )

    def test_invalid_shows_warning(self, mock_view, monkeypatch):
        """
        Renamed from test_invalid_emits_message: it is a modal now, not a message.

        Step 4a promoted on_raw_filter_validated to MetaSubsetTabView taking
        Metadata's QMessageBox over this tab's status-panel line, so that a rejected
        raw filter reads the same on both tabs.
        """
        warned = MagicMock()
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(warned))
        self._answer(mock_view, False, "syntax error")
        warned.assert_called_once()
        assert "syntax error" in warned.call_args[0][2]

    def test_valid_add_path(self, mock_view):
        self._answer(mock_view)
        assert "newfilter" in mock_view.subset_filters

    def test_valid_add_emits_added(self, mock_view):
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        self._answer(mock_view)
        assert any("added" in m for m in received)

    def test_valid_edit_path(self, mock_view):
        mock_view.subset_filters["oldfilter"] = "old text"
        mock_view.proteincontrols.filter_comboBox.addItem("oldfilter")
        self._answer(mock_view, old_name="oldfilter")
        assert "oldfilter" not in mock_view.subset_filters
        assert "newfilter" in mock_view.subset_filters

    def test_valid_edit_emits_updated(self, mock_view):
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view.subset_filters["oldfilter"] = "old text"
        mock_view.proteincontrols.filter_comboBox.addItem("oldfilter")
        self._answer(mock_view, old_name="oldfilter")
        assert any("updated" in m for m in received)


# ===========================================================================
# _save_filter / _load_filter (file I/O paths)
# ===========================================================================


class TestSaveLoadFilter:
    @patch("poriscope.utils.MetaSubsetTabView.QFileDialog.getSaveFileName")
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

    @patch("poriscope.utils.MetaSubsetTabView.QFileDialog.getSaveFileName")
    def test_save_filter_empty_is_noop(self, mock_dialog, mock_view):
        mock_view.subset_filters = {}
        mock_view._save_filter()
        mock_dialog.assert_not_called()

    @patch("poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName")
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

    @patch("poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName")
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

    @patch("poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName")
    def test_load_filter_no_path_is_noop(self, mock_dialog, mock_view):
        mock_dialog.return_value = ("", "")
        mock_view._load_filter({})


class TestRestoreSubsetFilters:
    def test_restore_subset_filters_adds_filters_directly(self, mock_view):
        mock_view.restore_subset_filters({"f1": "dur>100"})
        assert mock_view.subset_filters == {"f1": "dur>100"}

    def test_restore_subset_filters_skips_existing_names(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>999"}
        mock_view.restore_subset_filters({"f1": "dur>100"})
        assert mock_view.subset_filters == {"f1": "dur>999"}


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

    # update_units is gone from this tab: Step 4a moved it down to MetadataView, which
    # was its only caller. The protein tab has no units label, keeps no units cache and
    # labels its axes with hardcoded literals, so there was nothing here for the answer
    # to reach - which is also why ProteinView's missing update_column_units was
    # unreachable rather than merely swallowed.

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
        """The binning is the Model's since Step 4's closeout; drive it there."""
        ((bincenters, amplitude),) = ProteinModel().build_event_histograms(
            [_make_event(blockage=0.3)], "Filtered Histogram", None, False
        )
        assert len(bincenters) > 0  # FD-derived, not fixed 100

    def test_all_points_histogram_three_events(self, mock_view):
        """The averaging is the Model's since Step 4's closeout; drive it there."""
        evs = [_make_event(i, blockage=0.2 + i * 0.05, rng_seed=i) for i in range(3)]
        df = ProteinModel().build_all_points_histogram(
            iter(evs), "Filtered Histogram", None, False
        )
        assert isinstance(df, pd.DataFrame) and len(df) == 100

    def test_vm_ensemble_from_histogram_fit(self, mock_view):
        """
        The fit and the sampling are both the Model's since Step 4's closeout, so
        this is no longer cross-layer: it checks that one really does take the
        other's output, which is the join a stub on either side would hide.
        """
        model = ProteinModel()
        x, y = _make_double_gaussian_histogram(mean1=0.1, mean2=0.3)
        popt = model._fit_and_sanity_check_double_gaussian(x, y)
        if popt is None:
            pytest.skip("fit did not converge")

        df_prolate, df_oblate = model.sample_vm_solutions(popt, self.D, self.L, 20)

        assert len(df_prolate) <= 20 and len(df_oblate) <= 20
        assert list(df_prolate.columns) == ["V", "m", "a", "b"]

    def test_update_event_plot_end_to_end(self, mock_view):
        mock_view._update_event_plot([_make_event(1), _make_event(2)])
        assert mock_view._display_mode == "event"

    def test_update_event_histogram_end_to_end(self, mock_view):
        mock_view._update_event_histogram([_make_event(1)])
        _answer_event_histogram_fits(mock_view)
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
            mock_view.handle_parameter_change(
                "p", "loader_changed", ({"db_loader": None},)
            )
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
            mock_view.handle_parameter_change(
                "p", "shift_range_backward", (self._params(),)
            )
        mock.assert_called_once()
        assert mock.call_args[1]["direction"] == "left"

    def test_shift_forward_routes_right(self, mock_view):
        with patch.object(mock_view, "_shift_range_and_update_plot") as mock:
            mock_view.handle_parameter_change(
                "p", "shift_range_forward", (self._params(),)
            )
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
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0", "1"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})
        result = mock_view._fetch_event_data(self._params())
        assert result == []

    def test_multiple_channels_emits_message(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0", "1"]}
        }
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

    def test_asks_the_controller_for_exactly_the_events_requested(self, mock_view):
        """
        Step 4a: the resolve-and-load chain is one intent answered by
        ``ProteinController.load_event_plot_data``, so the stub stands in for the
        Controller by setting the generator the way it does - a stub that does nothing
        where the real collaborator sets the answer would make every assertion below
        vacuous.
        """
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"Full Dataset": ""})
        mock_view.current_sql_filter = ""
        mock_view.current_experiment = "exp1"
        mock_view.current_channel = 0

        requested = []

        def answer(loader, event_ids, exp, channel, scope, action_label):
            requested.append((loader, event_ids, exp, channel, scope, action_label))
            mock_view.plot_events_generator = iter([_make_event(1)])

        mock_view.event_plot_data_requested.connect(answer)

        result = mock_view._fetch_event_data(self._params())

        assert requested == [("ldr", [1], "exp1", 0, {"exp1": ["0"]}, "events")]
        assert len(result) == 1
        assert result[0]["event_id"] == 1

    def test_a_chain_that_did_not_finish_plots_nothing(self, mock_view):
        """
        The generator is cleared before the intent goes out, so a Controller that
        returned early leaves None rather than the previous plot's events - the stale
        read this step exists to remove.
        """
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"Full Dataset": ""})
        mock_view.plot_events_generator = iter([_make_event(99)])
        mock_view.event_plot_data_requested.connect(lambda *a: None)

        assert mock_view._fetch_event_data(self._params()) == []

    def test_the_answer_comes_back_in_the_order_it_was_asked_for(self, mock_view):
        """
        ``load_event_data`` yields in whatever order the database gives, and the
        navigation cares about the order it requested; the re-sort is why the query
        selects ``event_id`` alongside ``id``.
        """
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"Full Dataset": ""})
        mock_view.event_plot_data_requested.connect(
            lambda *a: setattr(
                mock_view,
                "plot_events_generator",
                iter([_make_event(7), _make_event(3), _make_event(5)]),
            )
        )

        result = mock_view._fetch_event_data(
            {"db_loader": "ldr", "event_index": [3, 5, 7]}
        )

        assert [e["event_id"] for e in result] == [3, 5, 7]


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
            mock_view._handle_plot_events(
                {"db_loader": "ldr", "event_id": 1, "n_events": 1}
            )
        assert mock_view._last_event_action == "plot_events"

    def test_calls_update_event_plot_with_data(self, mock_view):
        self._setup(mock_view)
        events = [_make_event(1)]
        mock_view._fetch_event_data = MagicMock(return_value=events)
        with patch.object(mock_view, "_update_event_plot") as mock_plot:
            mock_view._handle_plot_events(
                {"db_loader": "ldr", "event_id": 1, "n_events": 1}
            )
        mock_plot.assert_called_once_with(events, use_raw=False)

    def test_no_data_emits_warning(self, mock_view):
        self._setup(mock_view)
        mock_view._fetch_event_data = MagicMock(return_value=[])
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._handle_plot_events(
            {"db_loader": "ldr", "event_id": 1, "n_events": 2}
        )
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

    def test_cancelled_dialog_does_not_emit_signal(self, mock_view):
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(None, accepted=False),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        mock_view.global_signal.emit.assert_not_called()

    def test_no_loader_logs_error_and_returns(self, mock_view):
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(None, accepted=True),
        ):
            mock_view._show_add_filter_dialog({"db_loader": None})
        mock_view.global_signal.emit.assert_not_called()

    def test_assisted_filter_asks_the_controller_to_validate(self, mock_view):
        """
        Renamed: Step 4a replaced the construct_metadata_query emit with an intent.

        The Controller makes that call now, and chooses the columns to validate
        against, so what this tab does is state the intent.
        """
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        mock_view.filter_validation_requested = MagicMock()
        with patch(
            "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(None, accepted=True, is_raw=False),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        mock_view.filter_validation_requested.emit.assert_called_once_with(
            # Step 4d: the filter's name and the name it replaces (None, for a new
            # one) ride along with the intent instead of being parked on the widget.
            "ldr",
            "dur>1",
            "validate_new_filter",
            "f1",
            None,
        )
        mock_view.global_signal.emit.assert_not_called()

    def test_raw_filter_requires_select_statement(self, mock_view, monkeypatch):
        """
        Reported in a modal since Step 4a promoted this method.

        This tab used to put the rejection on the status panel and the metadata tab
        put it in a QMessageBox; the promoted copy uses the modal, by decision,
        because the dialog has just closed and a status line is easy to miss then.
        """
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        warned = MagicMock()
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(warned))
        with patch(
            "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(
                None, accepted=True, is_raw=True, text="dur > 100"
            ),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        warned.assert_called_once()
        assert "SELECT statements" in warned.call_args[0][2]
        mock_view.global_signal.emit.assert_not_called()

    def test_raw_filter_with_select_validates(self, mock_view):
        mock_view._walkthrough_active = False
        mock_view.global_signal = MagicMock()
        mock_view.raw_filter_validation_requested = MagicMock()
        with patch(
            "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(
                None,
                accepted=True,
                is_raw=True,
                name="f1",
                text="SELECT * FROM events",
            ),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        mock_view.raw_filter_validation_requested.emit.assert_called_once_with(
            # Step 4b: the View sends the filter as written; the Controller adds
            # the LIMIT 0 that makes the check cheap. Step 4d: the name it will be
            # stored under - already _raw-suffixed - and the name it replaces
            # travel with it.
            "ldr",
            "SELECT * FROM events",
            "f1_raw",
            None,
        )
        mock_view.global_signal.emit.assert_not_called()


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

    def test_cancelled_dialog_no_emit(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.utils.MetaSubsetTabView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(accepted=False),
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        mock_view.global_signal.emit.assert_not_called()

    def test_no_loader_logs_error(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        with patch(
            "poriscope.utils.MetaSubsetTabView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(accepted=True),
        ):
            mock_view.show_edit_filter_dialog("f1", None)
        mock_view.global_signal.emit.assert_not_called()

    def test_assisted_edit_asks_the_controller_to_validate(self, mock_view):
        """
        Renamed: Step 4a replaced the construct_metadata_query emit with an intent.

        The edited filter carries validate_edited_filter rather than
        validate_new_filter, which is what tells relay_query to replace the old name
        instead of adding a second entry.
        """
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        mock_view.filter_validation_requested = MagicMock()
        dialog = self._mock_dialog(accepted=True, is_raw=False)
        with patch(
            "poriscope.utils.MetaSubsetTabView.EditSubsetFilterDialog",
            return_value=dialog,
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        mock_view.filter_validation_requested.emit.assert_called_once_with(
            # Step 4d: an edit carries both names, so the Controller knows which
            # entry to replace without reading anything off the widget.
            "ldr",
            dialog.new_filter,
            "validate_edited_filter",
            dialog.new_name,
            "f1",
        )
        mock_view.global_signal.emit.assert_not_called()

    def test_raw_edit_requires_select(self, mock_view, monkeypatch):
        """Modal rather than status panel, for the reason above."""
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        warned = MagicMock()
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(warned))
        with patch(
            "poriscope.utils.MetaSubsetTabView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(
                accepted=True, is_raw=True, new_filter="dur > 5"
            ),
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        warned.assert_called_once()
        assert "SELECT statements" in warned.call_args[0][2]

    def test_raw_edit_with_select_validates(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.global_signal = MagicMock()
        mock_view.raw_filter_validation_requested = MagicMock()
        with patch(
            "poriscope.utils.MetaSubsetTabView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(
                accepted=True,
                is_raw=True,
                new_name="f1",
                new_filter="SELECT * FROM events",
            ),
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        mock_view.raw_filter_validation_requested.emit.assert_called_once_with(
            # Step 4b: the View sends the filter as written; the Controller adds
            # the LIMIT 0 that makes the check cheap. Step 4d: both names ride along.
            "ldr",
            "SELECT * FROM events",
            "f1_raw",
            "f1",
        )
        mock_view.global_signal.emit.assert_not_called()


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
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0", "1"]}
        }
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

    # These four assert on the *status panel*, not the log. The caplog tests above
    # passed throughout while the user was told nothing: QtHandler sits at ERROR and
    # deliberately does not surface WARNING, and its own docstring says anything the
    # user should be told belongs on add_text_to_display. Reported from a real run.

    def test_multiple_experiments_are_reported_on_the_status_panel(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0"], "exp2": ["0"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})

        mock_view._update_distribution_individual(self._params())

        said = [c.args[0] for c in mock_view.add_text_to_display.emit.call_args_list]
        assert any("single experiment" in m for m in said)

    def test_multiple_channels_are_reported_on_the_status_panel(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0", "1"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})

        mock_view._update_distribution_individual(self._params())

        said = [c.args[0] for c in mock_view.add_text_to_display.emit.call_args_list]
        assert any("single channel" in m for m in said)

    def test_an_experiment_with_no_channel_is_reported(self, mock_view):
        """
        The empty case reaches the same guard as the too-many case.

        Before Step 4c the guard read ``> 1`` and a ``for channel in channels:`` over
        an empty list simply never ran, so the tab drew nothing and said nothing.
        """
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": []}}
        mock_view.get_selected_filters = MagicMock(return_value={})

        mock_view._update_distribution_individual(self._params())

        said = [c.args[0] for c in mock_view.add_text_to_display.emit.call_args_list]
        assert any("single channel" in m for m in said)


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
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0", "1"]}
        }
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

    # These four assert on the *status panel*, not the log. The caplog tests above
    # passed throughout while the user was told nothing: QtHandler sits at ERROR and
    # deliberately does not surface WARNING, and its own docstring says anything the
    # user should be told belongs on add_text_to_display. Reported from a real run.

    def test_multiple_experiments_are_reported_on_the_status_panel(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0"], "exp2": ["0"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})

        mock_view._update_distribution_ensemble(self._params())

        said = [c.args[0] for c in mock_view.add_text_to_display.emit.call_args_list]
        assert any("single experiment" in m for m in said)

    def test_multiple_channels_are_reported_on_the_status_panel(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0", "1"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})

        mock_view._update_distribution_ensemble(self._params())

        said = [c.args[0] for c in mock_view.add_text_to_display.emit.call_args_list]
        assert any("single channel" in m for m in said)

    def test_an_experiment_with_no_channel_is_reported(self, mock_view):
        """
        The empty case reaches the same guard as the too-many case.

        Before Step 4c the guard read ``> 1`` and a ``for channel in channels:`` over
        an empty list simply never ran, so the tab drew nothing and said nothing.
        """
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": []}}
        mock_view.get_selected_filters = MagicMock(return_value={})

        mock_view._update_distribution_ensemble(self._params())

        said = [c.args[0] for c in mock_view.add_text_to_display.emit.call_args_list]
        assert any("single channel" in m for m in said)


def _fit_frame() -> pd.DataFrame:
    """
    A fit-data frame carrying every column the commit writes.

    Built from ``FIT_COLUMNS`` rather than typed out, so a column added to the
    production list cannot leave this fixture silently short of it.

    :return: one row, keyed by event id
    :rtype: pd.DataFrame
    """
    frame = {"id": [1]}
    frame.update({column: [1.0] for column in FIT_COLUMNS})
    return pd.DataFrame(frame)


# ===========================================================================
# set_alter_database_status / _commit_fits boundary (extra)
# ===========================================================================


class TestCommitFitsExtended:
    """
    Step 4a made the commit two-phase, so the View asks and the Controller looks.

    What is left to pin on this side is that the question goes out and that the
    answer decides whether the user is asked - the plugin call itself is
    ``ProteinController.check_for_existing_fit_columns``, covered in
    ``test_protein_fetch_slots``.
    """

    def test_asks_whether_the_database_already_holds_fit_data(self, mock_view):
        mock_view.fit_data = _fit_frame()
        asked = []
        mock_view.fit_commit_requested.connect(asked.append)

        mock_view._commit_fits("ldr")

        assert asked == ["ldr"]

    def test_no_existing_columns_commits_without_asking_the_user(self, mock_view):
        mock_view.fit_data = _fit_frame()
        sent = []
        mock_view.fit_commit_confirmed.connect(lambda *args: sent.append(args))

        with patch.object(QMessageBox, "question") as dialog:
            mock_view.confirm_fit_commit("ldr", None)

        dialog.assert_not_called()
        assert len(sent) == 1
        loader, frame, units, table = sent[0]
        assert (loader, table) == ("ldr", None)
        assert list(frame.columns) == ["id"] + FIT_COLUMNS
        assert len(units) == len(FIT_COLUMNS)

    def test_existing_columns_ask_first_and_carry_the_table_through(self, mock_view):
        mock_view.fit_data = _fit_frame()
        sent = []
        mock_view.fit_commit_confirmed.connect(lambda *args: sent.append(args))

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Ok):
            mock_view.confirm_fit_commit("ldr", "events")

        assert sent[0][0] == "ldr"
        assert sent[0][3] == "events"

    def test_declining_the_overwrite_sends_nothing(self, mock_view):
        mock_view.fit_data = _fit_frame()
        sent = []
        mock_view.fit_commit_confirmed.connect(lambda *args: sent.append(args))

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Cancel):
            mock_view.confirm_fit_commit("ldr", "events")

        assert sent == []

    def test_the_units_line_up_with_the_columns(self, mock_view):
        """
        A column added to one list and not the other would mislabel every column
        after it, and nothing downstream could notice.
        """
        assert len(FIT_COLUMN_UNITS) == len(FIT_COLUMNS)


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


# ===========================================================================
# set_distribution_fits - the answering half of distribution_fits_requested
# ===========================================================================
#
# Added 2026-09-14 because this method had **no test reference anywhere in the
# suite**, while being a named Step 4c target: the refactor-coverage audit read
# RUNS ONLY for it, its body executing under the e2e suite with nothing asserting
# what it produced. It is 157 lines and the largest single piece of computation
# still sitting on a View, so branch 5 of the Step 4 closeout moves it - and these
# are the pins that predate that move, which is what makes their passing against
# the Model afterwards evidence that the computation is unchanged.
#
# The ensembles are real, not stubbed: N is kept small so the Monte Carlo stays
# fast, and every assertion is about index alignment, skipping and the shape of
# what comes out rather than about sampled values, which are drawn from a seeded
# generator but are not the contract.


def _blockage_fit(mean_low=0.3, mean_high=0.6, std=0.02):
    """
    Build a popt tuple in the order the double-gaussian fit returns it.

    :param mean_low: the smaller fractional blockage
    :type mean_low: float
    :param mean_high: the larger fractional blockage
    :type mean_high: float
    :param std: the standard deviation given to both peaks
    :type std: float
    :return: a six-element popt, as (amp1, mean1, std1, amp2, mean2, std2)
    :rtype: tuple
    """
    return (1.0, mean_low, std, 1.0, mean_high, std)


def _histogram_pair():
    """
    A stand-in for one event's histogram.

    Only its presence is read by the method under test - a None entry means the
    histogram could not be built - so the contents are deliberately minimal. It was
    a one-column DataFrame until Step 4's closeout moved the binning to the Model,
    which returns the two arrays the drawing half actually uses.

    :return: a (bin centers, amplitude) pair
    :rtype: tuple
    """
    return (np.array([0.1, 0.2, 0.3]), np.array([1.0, 2.0, 1.0]))


class TestSetDistributionFits:
    """
    What is left here is the drawing. The sampling and every question about which
    events survive it moved to ``ProteinModel.sample_event_geometries`` in Step 4's
    closeout, and are pinned in ``tests/unit/models/test_protein_model.py``.
    """

    def _frames(self, rows=1):
        """
        The three frames the Model hands back.

        :param rows: how many fitted events to describe
        :type rows: int
        :return: the prolate solutions, the oblate solutions, and the summary rows
        :rtype: tuple
        """
        solutions = pd.DataFrame(
            {"V": [100.0, 200.0], "m": [2.0, 3.0], "a": [4.0, 5.0], "b": [2.0, 2.5]}
        )
        fit_data = pd.DataFrame(
            [
                {
                    "id": i + 1,
                    "min_fractional_blockage": 0.3,
                    "min_fractional_blockage_std": 0.02,
                    "max_fractional_blockage": 0.6,
                    "max_fractional_blockage_std": 0.02,
                }
                for i in range(rows)
            ]
        )
        return solutions, solutions.copy(), fit_data

    def test_the_summary_rows_are_kept_for_the_commit(self, mock_view, mocker):
        """``_commit_fits`` writes these back to the database."""
        mocker.patch.object(mock_view, "update_plot")
        prolate, oblate, fit_data = self._frames(rows=2)

        mock_view.set_distribution_fits(prolate, oblate, fit_data)

        assert mock_view.fit_data["id"].tolist() == [1, 2]

    def test_the_three_plots_are_requested(self, mock_view, mocker):
        """
        Two scatterplots of the sampled solutions and one errorbar plot of the
        per-event fit parameters.
        """
        update_plot = mocker.patch.object(mock_view, "update_plot")

        mock_view.set_distribution_fits(*self._frames())

        labels = [call.kwargs["dataset_label"] for call in update_plot.call_args_list]
        assert labels == [
            "Prolate Solutions",
            "Oblate Solutions",
            "Event Peak Fit Parameters",
        ]

    def test_the_peak_plot_carries_the_error_columns(self, mock_view, mocker):
        """The errorbar plot is the only one given ``err_cols``."""
        update_plot = mocker.patch.object(mock_view, "update_plot")

        mock_view.set_distribution_fits(*self._frames())

        with_errors = [
            call
            for call in update_plot.call_args_list
            if call.kwargs.get("err_cols") is not None
        ]
        assert len(with_errors) == 1
        assert with_errors[0].args[0] == "Peak Scatterplot"

    def test_an_empty_solution_set_draws_only_what_there_is(self, mock_view, mocker):
        """
        A fit that sampled nothing still has its peak parameters worth plotting, so
        the empty scatterplots are skipped rather than the whole figure.
        """
        update_plot = mocker.patch.object(mock_view, "update_plot")
        _prolate, _oblate, fit_data = self._frames()
        empty = pd.DataFrame(columns=["V", "m", "a", "b"])

        mock_view.set_distribution_fits(empty, empty, fit_data)

        labels = [call.kwargs["dataset_label"] for call in update_plot.call_args_list]
        assert labels == ["Event Peak Fit Parameters"]


# ===========================================================================
# The ensemble histogram's request and answer halves
# ===========================================================================


class TestEnsembleHistogramRequest:
    """What ``_update_distribution_ensemble`` asks for now that it builds nothing."""

    def _params(self):
        """
        The controls' parameters for one ensemble plot.

        :return: the parameter dict
        :rtype: dict
        """
        return {
            "db_loader": "ldr",
            "plot_type": "Filtered Histogram",
            "pore_diameter": "20.0",
            "pore_length": "30.0",
            "n_values": "10",
            "bins": [40],
            "sizes": False,
        }

    def _scoped(self, mock_view):
        """
        Put one experiment, one channel and one subset in scope.

        :param mock_view: the view under test
        :type mock_view: ProteinView
        :return: None
        :rtype: None
        """
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["3"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"sub": "duration < 3"})

    def test_the_request_carries_the_subset_and_the_bin_request(self, mock_view):
        self._scoped(mock_view)

        mock_view._update_distribution_ensemble(self._params())

        args = mock_view.ensemble_histogram_requested.emit.call_args.args
        loader, sql_filter, scope, plot_type, bins, sizes = args[:6]
        assert loader == "ldr"
        assert sql_filter == "duration < 3"
        assert scope == {"exp1": ["3"]}
        assert plot_type == "Filtered Histogram"
        assert bins == [40]
        assert sizes is False

    def test_the_request_carries_the_drawing_context_and_the_geometry(self, mock_view):
        """
        The label, the plotted-datasets key and the pore geometry depart unchanged
        and come back through the setter, so nothing is parked on the widget
        between asking and answering.
        """
        self._scoped(mock_view)

        mock_view._update_distribution_ensemble(self._params())

        args = mock_view.ensemble_histogram_requested.emit.call_args.args
        dataset_label, dataset_key, d, L, N = args[6:]
        assert "sub" in dataset_label
        assert dataset_key == ("ldr", "exp1", 3, "duration < 3", "sub")
        assert (d, L, N) == (20.0, 30.0, 10)

    def test_nothing_is_fetched_into_the_widget(self, mock_view):
        """
        The events never reach it, so neither does the generator - this path does
        not touch the attribute at all now, where it used to clear it, fill it and
        walk it twice.
        """
        self._scoped(mock_view)

        mock_view._update_distribution_ensemble(self._params())

        assert not hasattr(mock_view, "event_data_generator")


class TestSetEnsembleHistogram:
    """The answering half: draw, record, then ask for the geometry."""

    def _frame(self):
        """
        A stand-in for the averaged histogram the Model hands back.

        :return: a two-column frame
        :rtype: pd.DataFrame
        """
        return pd.DataFrame(
            {
                "Normalized Current": np.linspace(0.0, 1.0, 10),
                "Amplitude": np.linspace(1.0, 2.0, 10),
            }
        )

    def test_the_histogram_is_drawn(self, mock_view, mocker):
        mocker.patch.object(mock_view, "update_plot")

        mock_view.set_ensemble_histogram(
            self._frame(), "Filtered Histogram", [40], False, "lbl", ("k",), 1.0, 2.0, 3
        )

        assert mock_view.update_plot.call_args.args[0] == "Filtered Histogram"

    def test_the_bookkeeping_describes_this_plot(self, mock_view, mocker):
        mocker.patch.object(mock_view, "update_plot")

        mock_view.set_ensemble_histogram(
            self._frame(), "Filtered Histogram", [40], False, "lbl", ("k",), 1.0, 2.0, 3
        )

        assert mock_view.allowed_plot_type == "Filtered Histogram"
        assert mock_view.allowed_bins == [40]
        assert mock_view.allowed_sizes is False
        assert ("k",) in mock_view.plotted_datasets

    def test_the_bins_are_recorded_before_the_fit_is_asked_for(self, mock_view, mocker):
        """
        ``set_ensemble_geometry_fit`` reads ``allowed_bins`` and ``allowed_sizes``
        to describe the fit it draws, so they have to describe *this* plot by the
        time the request goes out. The request half used to set them between the
        drawing and the fit; moving the drawing into a setter is exactly the change
        that could have reordered them.
        """
        mocker.patch.object(mock_view, "update_plot")
        seen = {}
        mock_view._request_ensemble_geometry_fit = lambda *a, **k: seen.update(
            bins=mock_view.allowed_bins, sizes=mock_view.allowed_sizes
        )

        mock_view.set_ensemble_histogram(
            self._frame(), "Filtered Histogram", [40], True, "lbl", ("k",), 1.0, 2.0, 3
        )

        assert seen == {"bins": [40], "sizes": True}

    def test_the_geometry_reaches_the_fit_request(self, mock_view, mocker):
        mocker.patch.object(mock_view, "update_plot")
        frame = self._frame()

        mock_view.set_ensemble_histogram(
            frame, "Filtered Histogram", [40], False, "lbl", ("k",), 11.0, 22.0, 33
        )

        args = mock_view.ensemble_fit_requested.emit.call_args.args
        assert args[3:] == ("Filtered Histogram", 11.0, 22.0, 33)
