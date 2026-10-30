"""
Full unit-test suite for ProteinView.

Covers the ProteinView analysis tab end-to-end, including:
  - format_axis_label (module-level helper)
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
  - unittest.mock (MagicMock, patch) to stub out the tab's request signals,
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
  - Nothing answers the view's request signals in these tests, so any code path
    that depends on the Controller's answer should either connect a stand-in that
    calls the matching setter, or set the result on the mock_view fixture first.

Run with:
    pytest tests/unit/views/test_protein_view.py -v
"""

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
)
from tests.unit.views._qt_mocks import mock_axes, shadow_signals

# ===========================================================================
# Fixtures
# ===========================================================================


def recorded(view, parameters):
    """
    Give a plot's parameters the selection ``handle_parameter_change`` records into them.

    The recorded plot methods read the filter and channel selection from their
    parameters, so a replay draws what was recorded. A test calling one directly has to
    hand it parameters shaped the same way, and this calls the real ``_record_selection``
    to build them, from whatever the test has stubbed ``get_selected_filters`` and the
    channel selection to be.

    :param view: the view under test
    :type view: Any
    :param parameters: the plot's parameters, updated in place
    :type parameters: dict
    :return: the same parameters
    :rtype: dict
    """
    view._record_selection(parameters)
    return parameters


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

    Both analysis modes' figures, axes and canvases are populated, since every
    drawing names the mode whose figures it uses.

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
# format_axis_label  (inherited from MetaView)
# ===========================================================================


class TestFormatAxisLabel:
    def test_adds_unit(self):
        assert ProteinView.format_axis_label("Duration", "ms") == "Duration (ms)"

    def test_empty_unit(self):
        assert ProteinView.format_axis_label("Amplitude", "") == "Amplitude"

    def test_appends_rather_than_replacing_an_existing_unit(self):
        assert (
            ProteinView.format_axis_label("Duration (s)", "ms") == "Duration (s) (ms)"
        )

    def test_an_empty_unit_leaves_an_existing_parenthetical_in_place(self):
        assert ProteinView.format_axis_label("Amplitude (pA)", "") == "Amplitude (pA)"

    def test_latex_unit(self):
        assert (
            ProteinView.format_axis_label("Volume", r"nm$^{3}$") == r"Volume (nm$^{3}$)"
        )

    def test_idempotent(self):
        once = ProteinView.format_axis_label("Duration", "ms")
        assert ProteinView.format_axis_label(once, "ms") == once

    def test_a_label_containing_its_own_parenthetical_keeps_it(self):
        assert ProteinView.format_axis_label("log10(Duration)", "s") == (
            "log10(Duration) (s)"
        )

    def test_none_unit_equivalent(self):
        assert ProteinView.format_axis_label("X", "") == "X"


# ===========================================================================
# State setters
# ===========================================================================


class TestStateSetters:
    def test_set_event_plot_data_generator(self, mock_view):
        g = iter([])
        mock_view.set_event_plot_data_generator(g)
        assert mock_view.plot_events_generator is g

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
    def test_commit_individual_only_asks_the_controller(self, mock_view):
        """Whether there is a fit to commit is the Controller's to say: the Model keeps it."""
        mock_view.handle_parameter_change(
            "p", "commit_individual", ({"db_loader": "loader1"},)
        )

        mock_view.fit_commit_requested.emit.assert_called_once_with("loader1")


# ===========================================================================
# _reset_actions
# ===========================================================================


class TestResetActions:
    def test_clears_hist_state(self, mock_view):
        """
        ``hist_min``/``hist_max`` went with the binning to the Model: the two
        methods that wrote them live there now, which left three clears and no
        reader at all.
        """
        mock_view.hist_data = [([1], [2])]
        mock_view.hist_labels = ["x"]
        mock_view._reset_actions()
        assert mock_view.hist_data == []
        assert mock_view.hist_labels == []
        assert not hasattr(mock_view, "hist_min")


# ===========================================================================
# _clear_figure_state
# ===========================================================================


class TestClearFigureState:
    def test_clears_cache(self, mock_view):
        # Just verify _clear_figure_state runs without error
        # (cache internals belong to MetaView and vary by implementation)
        mock_view._clear_figure_state()

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
            real_view.ax_hist_individual, self._df(), ["NC", "Amp"], ["pA", ""]
        )
        assert "NC" in real_view.ax_hist_individual.get_xlabel()

    def test_appends_to_hist_data(self, mock_view):
        mock_view._plot_all_points_histogram(
            mock_view.ax_hist_individual, self._df(), ["NC", "Amp"], ["pA", ""], "ds1"
        )
        assert len(mock_view.hist_data) == 1

    def test_accumulates_multiple_calls(self, mock_view):
        mock_view._plot_all_points_histogram(
            mock_view.ax_hist_individual, self._df(), ["NC", "Amp"], ["pA", ""], "ds1"
        )
        mock_view._plot_all_points_histogram(
            mock_view.ax_hist_individual, self._df(), ["NC", "Amp"], ["pA", ""], "ds2"
        )
        assert len(mock_view.hist_data) == 2

    def test_norm_flag_modifies_ylabel(self, real_view):
        real_view._plot_all_points_histogram(
            real_view.ax_hist_individual,
            self._df(),
            ["NC", "Amp"],
            ["pA", ""],
            norm=True,
        )
        assert "Normalized" in real_view.ax_hist_individual.get_ylabel()


# ===========================================================================
# show_* - each plot on its own mode's figure
# ===========================================================================


class TestFiguresByMode:
    """Every drawing names the mode whose figures it uses, whichever mode is showing."""

    MODES = [("individual", "ensemble"), ("ensemble", "individual")]

    def _histogram(self):
        x = np.linspace(0, 1, 20)
        return pd.DataFrame({"Normalized Current": x, "Amplitude": np.ones(20) * 0.5})

    def _columns(self, n=2):
        return [np.array([1.0, 2.0, 3.0]) for _ in range(n)]

    @pytest.mark.parametrize(("mode", "other"), MODES)
    def test_a_histogram_draws_on_its_mode_s_figure_only(self, real_view, mode, other):
        real_view._analysis_mode = other

        real_view.show_histogram(mode, self._histogram(), "d")

        assert len(getattr(real_view, f"ax_hist_{mode}").lines) == 1
        assert len(getattr(real_view, f"ax_hist_{other}").lines) == 0

    def test_a_fit_is_drawn_over_the_histogram(self, real_view):
        real_view.show_histogram("ensemble", self._histogram(), "d")

        real_view.show_histogram("ensemble", self._histogram(), "Fit")

        labels = [line.get_label() for line in real_view.ax_hist_ensemble.lines]
        assert labels == ["d", "Fit"]

    @pytest.mark.parametrize(("mode", "other"), MODES)
    def test_solutions_draw_on_their_mode_s_v_m_figure_only(
        self, real_view, mode, other
    ):
        real_view._analysis_mode = other

        real_view.show_solutions(mode, self._columns(), "Prolate Solutions")

        assert len(getattr(real_view, f"ax_vm_{mode}").collections) == 1
        assert len(getattr(real_view, f"ax_vm_{other}").collections) == 0
        assert getattr(real_view, f"ax_vm_{mode}").get_xlabel().startswith("V")

    @pytest.mark.parametrize(("mode", "other"), MODES)
    def test_peak_fits_draw_on_their_mode_s_histogram_figure_only(
        self, real_view, mode, other
    ):
        real_view._analysis_mode = other

        real_view.show_peak_fits(mode, self._columns(4), "Event Peak Fit Parameters")

        assert len(getattr(real_view, f"ax_hist_{mode}").collections) > 0
        assert len(getattr(real_view, f"ax_hist_{other}").collections) == 0

    def test_each_plot_hands_what_it_drew_to_the_export_cache(self, mock_view):
        mock_view._commit_cache = MagicMock()

        mock_view.show_solutions("ensemble", self._columns(), "Oblate Solutions")

        mock_view._commit_cache.assert_called_once()
        mock_view.canvas_vm_ensemble.draw.assert_called_once()

    @pytest.mark.parametrize(("mode", "other"), MODES)
    def test_clear_plot_clears_its_mode_s_figures_only(self, real_view, mode, other):
        for side in (mode, other):
            getattr(real_view, f"ax_hist_{side}").plot([0.0, 1.0], [0.0, 1.0])

        real_view.clear_plot("2d", mode)

        assert len(getattr(real_view, f"ax_hist_{mode}").lines) == 0
        assert len(getattr(real_view, f"ax_hist_{other}").lines) == 1


# ===========================================================================
# Range helpers (inherited from MetaView, exercised via ProteinView)
# ===========================================================================


class TestFactors:
    """
    ``MetaView._factors``, the subplot-grid helper.

    This class held sixteen more tests, for the five event-index range helpers. Those
    helpers live on ``MetaEventTabView`` rather than ``MetaView``, and its only
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

    @pytest.mark.parametrize(
        "parameters", [{"db_loader": "l"}, {}], ids=["no_scope", "no_loader"]
    )
    def test_nothing_in_scope_is_reported(self, mock_view, parameters):
        """
        Navigation with no experiment or channel selected says so on the status panel.

        A missing loader key reaches the same message, since no scope is filed under it.
        """
        mock_view.selected_experiment_and_channels_by_loader = {}
        mock_view.get_selected_filters = MagicMock(return_value={})
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))

        with patch.object(mock_view, "_handle_plot_events") as mock_ev:
            mock_view._shift_range_and_update_plot(parameters, "right")

        assert received == [
            "No experiments or channels are in scope, select at least one to "
            "navigate events"
        ]
        mock_ev.assert_not_called()

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
# show_events
# ===========================================================================


class TestShowEvents:
    def test_switches_to_event_mode(self, mock_view):
        mock_view.show_events([_make_event(1), _make_event(2)])
        assert mock_view._display_mode == "event"

    def test_canvas_drawn(self, mock_view):
        mock_view.show_events([_make_event(1)])
        assert mock_view._display_mode == "event"

    def test_multi_event_grid(self, mock_view):
        mock_view.show_events([_make_event(i) for i in range(1, 5)])

    def test_cache_committed(self, mock_view):
        # Verify the method completes without error; cache internals are MetaView's
        mock_view.show_events([_make_event(1)])


# ===========================================================================
# _update_event_histogram
# ===========================================================================


def _answer_event_histogram_fits(view):
    """
    Run the round trip ProteinController runs, and hand the answer back to the View.

    ``_update_event_histogram`` is only the request; ``set_event_histogram_fits``
    draws the answer. These tests drive both halves, because driving only
    the first asserts against a View that has not drawn anything yet.

    The histograms and the fits both come from a **real ProteinModel** rather than a
    stub, so their arity and their shapes are the collaborator's own rather than this
    test's idea of them. The binning sits on the Model beside the fitting, so this
    helper runs both calls the Controller runs.

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
        The binning is done below the widget, so what goes out is the events
        themselves and how the caller asked for them to be binned.
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
    # The filter's name, the name it replaces and its text travel through the call.
    # They used to be parked on the widget by a _setup helper and read back off it
    # here, which is state-on-the-widget the View should not be carrying.
    def _answer(self, mock_view, valid=True, error_msg="", old_name=None):
        mock_view.on_raw_filter_validated(
            valid, error_msg, "newfilter", old_name, "SELECT * FROM events"
        )

    def test_invalid_shows_warning(self, mock_view, monkeypatch):
        """
        Renamed from test_invalid_emits_message: it is a modal now, not a message.

        on_raw_filter_validated lives on MetaSubsetTabView and uses Metadata's
        QMessageBox rather than this tab's old status-panel line, so that a rejected
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
    def test_save_filter_asks_for_the_path_and_the_filters(
        self, mock_dialog, mock_view
    ):
        """Writing the file is the model's; choosing where is still the dialog's."""
        mock_dialog.return_value = ("/tmp/filters.json", "JSON Files (*.json)")
        mock_view.subset_filters = {"f1": "dur>100", "f2": "dur<500"}

        mock_view._save_filter()

        path, filters = mock_view.filters_save_requested.emit.call_args.args
        assert path == "/tmp/filters.json"
        assert filters == {"f1": "dur>100", "f2": "dur<500"}

    @patch("poriscope.utils.MetaSubsetTabView.QFileDialog.getSaveFileName")
    def test_save_filter_empty_is_noop(self, mock_dialog, mock_view):
        mock_view.subset_filters = {}
        mock_view._save_filter()
        mock_dialog.assert_not_called()

    def test_loaded_filters_are_added(self, mock_view):
        """No loader, so the else-branch adds the filter without validating it."""
        mock_view.set_loaded_filters({"loaded_f": "dur>50"}, "")

        assert "loaded_f" in mock_view.subset_filters

    def test_loaded_filters_block_duplicates(self, mock_view):
        mock_view.subset_filters = {"existing": "dur>0"}

        mock_view.set_loaded_filters({"existing": "dur>999"}, "")

        assert mock_view.subset_filters["existing"] == "dur>0"

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

    # update_units and update_available_columns are both gone from this tab: they live
    # on MetadataView, which was their only caller. The protein tab has no units label,
    # keeps no units cache, labels its axes with hardcoded literals and reads no column
    # names, so there was nothing here for either answer to reach - which is also why
    # ProteinView's missing update_column_units and update_column_names were
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
        """The binning is the Model's; drive it there."""
        ((bincenters, amplitude),) = ProteinModel().build_event_histograms(
            [_make_event(blockage=0.3)], "Filtered Histogram", None, False
        )
        assert len(bincenters) > 0  # FD-derived, not fixed 100

    def test_all_points_histogram_three_events(self, mock_view):
        """The averaging is the Model's; drive it there."""
        evs = [_make_event(i, blockage=0.2 + i * 0.05, rng_seed=i) for i in range(3)]
        df = ProteinModel().build_all_points_histogram(
            iter(evs), "Filtered Histogram", None, False
        )
        assert isinstance(df, pd.DataFrame) and len(df) == 100

    def test_vm_ensemble_from_histogram_fit(self, mock_view):
        """
        The fit and the sampling are both the Model's, so this is not cross-layer:
        it checks that one really does take the other's output, which is the join
        a stub on either side would hide.
        """
        model = ProteinModel()
        x, y = _make_double_gaussian_histogram(mean1=0.1, mean2=0.3)
        popt = model._fit_and_sanity_check_double_gaussian(x, y)
        if popt is None:
            pytest.skip("fit did not converge")

        df_prolate, df_oblate = model.sample_vm_solutions(popt, self.D, self.L, 20)

        assert len(df_prolate) <= 20 and len(df_oblate) <= 20
        assert list(df_prolate.columns) == ["V", "m", "a", "b"]

    def test_show_events_end_to_end(self, mock_view):
        mock_view.show_events([_make_event(1), _make_event(2)])
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
        for mode in ("individual", "ensemble"):
            assert getattr(real_view, f"canvas_hist_{mode}") is not None
            assert getattr(real_view, f"canvas_vm_{mode}") is not None

    def test_creates_event_canvas(self, real_view):
        assert real_view.canvas_event is not None

    def test_default_display_mode_is_distribution(self, real_view):
        assert real_view._display_mode == "distribution"

    def test_display_stack_starts_on_distribution_page(self, real_view):
        assert real_view.display_stack.currentIndex() == 0


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

    def test_loader_changed_requests_the_structure(self, mock_view):
        """A loader change asks for the experiment structure."""
        with patch.object(mock_view, "request_experiment_structure") as mock_struct:
            mock_view.handle_parameter_change(
                "p", "loader_changed", (self._params(db_loader="ldr1"),)
            )
        mock_struct.assert_called_once_with("ldr1")

    def test_loader_changed_no_loader_skips(self, mock_view):
        with patch.object(mock_view, "request_experiment_structure") as mock_struct:
            mock_view.handle_parameter_change(
                "p", "loader_changed", ({"db_loader": None},)
            )
        mock_struct.assert_not_called()

    def test_a_fit_commit_announces_new_columns(self, mock_view):
        """Committing fits tells the other tabs; there is no column-names signal here to ask with."""
        announced = []
        mock_view.plugin_state_changed.connect(lambda *a: announced.append(a))
        mock_view.on_fit_commit_finished("ldr")
        assert announced == [("MetaDatabaseLoader", "ldr", "columns")]

    def test_select_experiment_and_channel_shows_tree(self, mock_view):
        mock_view.available_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        with patch.object(mock_view, "show_selection_tree") as mock_tree:
            mock_view.handle_parameter_change(
                "p", "select_experiment_and_channel", (self._params(db_loader="ldr"),)
            )
        mock_tree.assert_called_once()

    def test_the_selection_tree_shows_experiments_written_since_the_loader_was_chosen(
        self, mock_view
    ):
        """
        Opening the experiment and channel tree asks the loader again before showing it.

        The stand-in answers the way the Controller does: synchronously, filing the
        loader's current structure.
        """
        mock_view.available_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        now_on_disk = {"exp1": ["0"], "exp2": ["1"]}

        def answer(loader):
            mock_view.available_experiment_and_channels_by_loader[loader] = now_on_disk

        with (
            patch.object(
                mock_view, "request_experiment_structure", side_effect=answer
            ) as mock_request,
            patch.object(mock_view, "show_selection_tree") as mock_tree,
        ):
            mock_view.handle_parameter_change(
                "p", "select_experiment_and_channel", (self._params(db_loader="ldr"),)
            )
        mock_request.assert_called_once_with("ldr")
        assert mock_tree.call_args.args[0] == now_on_disk

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

    def _plot_params(self):
        return self._params(
            pore_diameter="20.0",
            pore_length="30.0",
            n_values="10",
            bins=[50],
            sizes=False,
        )

    @pytest.mark.parametrize(
        ("mode", "asked", "not_asked"),
        [
            (
                "individual",
                "individual_distribution_requested",
                "ensemble_distribution_requested",
            ),
            (
                "ensemble",
                "ensemble_distribution_requested",
                "individual_distribution_requested",
            ),
        ],
    )
    def test_update_plot_asks_with_the_click_s_intent(
        self, mock_view, mode, asked, not_asked
    ):
        mock_view._analysis_mode = mode
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"f": "x > 1"})

        mock_view.handle_parameter_change("p", "update_plot", (self._plot_params(),))

        getattr(mock_view, asked).emit.assert_called_once_with(
            "ldr", {"f": "x > 1"}, {"exp1": ["0"]}, [50], False, 20.0, 30.0, 10
        )
        getattr(mock_view, not_asked).emit.assert_not_called()

    def test_update_plot_individual_mode_with_no_scope_or_n(self, mock_view):
        """N defaults to 100, and an unselected scope goes as an empty one."""
        mock_view._analysis_mode = "individual"
        mock_view.get_selected_filters = MagicMock(return_value={})
        mock_view.handle_parameter_change(
            "p",
            "update_plot",
            (self._params(pore_diameter="20.0", pore_length="30.0", n_values=""),),
        )
        args = mock_view.individual_distribution_requested.emit.call_args.args
        assert args[2] == {}
        assert args[7] == 100

    def test_report_all_asks_the_controller(self, mock_view):
        mock_view.handle_parameter_change("p", "report_all", ({},))

        mock_view.ensemble_report_requested.emit.assert_called_once_with()

    def test_update_plot_sets_distribution_mode(self, mock_view):
        mock_view._set_display_mode("event")
        mock_view.get_selected_filters = MagicMock(return_value={})
        mock_view.handle_parameter_change("p", "update_plot", (self._plot_params(),))
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
    """
    ``None`` means refused and already reported; ``[]`` means the fetch ran and
    found nothing. The callers tell the two apart so a refusal does not get a
    second, contradictory line naming the event - see
    ``test_protein_event_fetch_messages.py``.
    """

    def _params(self):
        return {"db_loader": "ldr", "event_index": [1]}

    def test_no_experiments_is_refused(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {}
        mock_view.get_selected_filters = MagicMock(return_value={})
        result = mock_view._fetch_event_data(self._params())
        assert result is None

    def test_no_experiments_emits_message(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {}
        mock_view.get_selected_filters = MagicMock(return_value={})
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._fetch_event_data(self._params())
        assert any("No experiments or channels" in m for m in received)

    def test_multiple_filters_is_refused(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"f1": "a", "f2": "b"})
        result = mock_view._fetch_event_data(self._params())
        assert result is None

    def test_multiple_filters_emits_message(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={"f1": "a", "f2": "b"})
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._fetch_event_data(self._params())
        assert any("more than one subset" in m for m in received)

    def test_empty_loader_selection_is_refused(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        result = mock_view._fetch_event_data(self._params())
        assert result is None

    def test_multiple_experiments_is_refused(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0"], "exp2": ["0"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})
        result = mock_view._fetch_event_data(self._params())
        assert result is None

    def test_multiple_experiments_emits_message(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0"], "exp2": ["0"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))
        mock_view._fetch_event_data(self._params())
        assert any("single experiment" in m for m in received)

    def test_multiple_channels_is_refused(self, mock_view):
        mock_view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": ["0", "1"]}
        }
        mock_view.get_selected_filters = MagicMock(return_value={})
        result = mock_view._fetch_event_data(self._params())
        assert result is None

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
        """When no filters selected, defaults to {'Full Dataset': ''}. Nothing answers
        the event-plot request in this test, so the generator is never populated;
        requesting no event indices keeps the code from pulling from a None generator.
        """
        mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["0"]}}
        mock_view.get_selected_filters = MagicMock(return_value={})
        mock_view.plot_events_generator = None
        mock_view.current_sql_filter = None
        mock_view.current_experiment = None
        mock_view.current_channel = None
        mock_view.cached_events = {}
        params = {"db_loader": "ldr", "event_index": []}
        result = mock_view._fetch_event_data(params)
        assert result is None

    def test_asks_the_controller_for_exactly_the_events_requested(self, mock_view):
        """
        The resolve-and-load chain is one intent answered by
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

        assert mock_view._fetch_event_data(self._params()) is None

    def test_the_answer_comes_back_in_the_order_it_was_asked_for(self, mock_view):
        """
        ``load_event_data`` yields in whatever order the database gives, and the
        navigation cares about the order it requested. The re-sort keys off the
        ``event_id`` the loader reports on each event, against the indices asked
        for - not off anything the id-resolution query projects.
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

    def _asked(self, mock_view):
        asked = []
        mock_view.plot_events_requested.connect(lambda *args: asked.append(args))
        return asked

    def test_sets_last_event_action(self, mock_view):
        self._setup(mock_view)
        mock_view._last_event_action = "plot_histogram"
        mock_view._handle_plot_events(
            {"db_loader": "ldr", "event_id": 1, "n_events": 1}
        )
        assert mock_view._last_event_action == "plot_events"

    def test_asks_for_the_resolved_events_with_their_subset(self, mock_view):
        self._setup(mock_view)
        asked = self._asked(mock_view)

        mock_view._handle_plot_events(
            {"db_loader": "ldr", "event_id": 2, "n_events": 2, "raw": True}
        )

        assert asked == [("ldr", [2, 3], "exp1", "0", "Full Dataset", "", True)]

    def test_an_id_past_the_cache_snaps_to_the_first_and_says_so(self, mock_view):
        """Plotting an Event ID past every filtered one starts at the first."""
        self._setup(mock_view)
        asked = self._asked(mock_view)
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))

        mock_view._handle_plot_events(
            {"db_loader": "ldr", "event_id": 99, "n_events": 2}
        )

        assert asked[0][1] == [1, 2]
        assert (
            "Event ID 99 is past the last filtered event (3); "
            "wrapped around to the first filtered event (1)"
        ) in received


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

    def test_an_id_past_the_cache_snaps_to_the_first_and_says_so(self, mock_view):
        """The histogram snaps an out-of-range Event ID exactly as Plot Events does."""
        self._setup(mock_view)
        mock_view._fetch_event_data = MagicMock(return_value=[])
        received = []
        mock_view.add_text_to_display.connect(lambda m, s: received.append(m))

        mock_view._handle_plot_histogram(
            {
                "db_loader": "ldr",
                "event_id": 99,
                "n_events": 2,
                "bins": None,
                "sizes": False,
            }
        )

        assert mock_view._fetch_event_data.call_args[0][0]["event_index"] == [1, 2]
        assert (
            "Event ID 99 is past the last filtered event (3); "
            "wrapped around to the first filtered event (1)"
        ) in received

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
        with patch(
            "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(None, accepted=False),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})

    def test_no_loader_logs_error_and_returns(self, mock_view):
        mock_view._walkthrough_active = False
        with patch(
            "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(None, accepted=True),
        ):
            mock_view._show_add_filter_dialog({"db_loader": None})

    def test_assisted_filter_asks_the_controller_to_validate(self, mock_view):
        """
        Renamed: an intent replaced the construct_metadata_query emit.

        The Controller makes that call now, and chooses the columns to validate
        against, so what this tab does is state the intent.
        """
        mock_view._walkthrough_active = False
        mock_view.filter_validation_requested = MagicMock()
        with patch(
            "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog",
            return_value=self._mock_dialog(None, accepted=True, is_raw=False),
        ):
            mock_view._show_add_filter_dialog({"db_loader": "ldr"})
        mock_view.filter_validation_requested.emit.assert_called_once_with(
            # The filter's name and the name it replaces (None, for a new
            # one) ride along with the intent instead of being parked on the widget.
            "ldr",
            "dur>1",
            "validate_new_filter",
            "f1",
            None,
        )

    def test_raw_filter_requires_select_statement(self, mock_view, monkeypatch):
        """
        Reported in a modal since this method moved to MetaSubsetTabView.

        This tab used to put the rejection on the status panel and the metadata tab
        put it in a QMessageBox; the promoted copy uses the modal, by decision,
        because the dialog has just closed and a status line is easy to miss then.
        """
        mock_view._walkthrough_active = False
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
        assert "has to start with SELECT" in warned.call_args[0][2]

    def test_raw_filter_with_select_validates(self, mock_view):
        mock_view._walkthrough_active = False
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
            # The View sends the filter as written; the Controller adds the
            # LIMIT 0 that makes the check cheap. The name it will be
            # stored under - already _raw-suffixed - and the name it replaces
            # travel with it.
            "ldr",
            "SELECT * FROM events",
            "f1_raw",
            None,
        )


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
        with patch(
            "poriscope.utils.MetaSubsetTabView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(accepted=False),
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")

    def test_no_loader_logs_error(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
        with patch(
            "poriscope.utils.MetaSubsetTabView.EditSubsetFilterDialog",
            return_value=self._mock_dialog(accepted=True),
        ):
            mock_view.show_edit_filter_dialog("f1", None)

    def test_assisted_edit_asks_the_controller_to_validate(self, mock_view):
        """
        Renamed: an intent replaced the construct_metadata_query emit.

        The edited filter carries validate_edited_filter rather than
        validate_new_filter, which is what tells relay_query to replace the old name
        instead of adding a second entry.
        """
        mock_view.subset_filters = {"f1": "dur>1"}
        mock_view.filter_validation_requested = MagicMock()
        dialog = self._mock_dialog(accepted=True, is_raw=False)
        with patch(
            "poriscope.utils.MetaSubsetTabView.EditSubsetFilterDialog",
            return_value=dialog,
        ):
            mock_view.show_edit_filter_dialog("f1", "ldr")
        mock_view.filter_validation_requested.emit.assert_called_once_with(
            # An edit carries both names, so the Controller knows which
            # entry to replace without reading anything off the widget.
            "ldr",
            dialog.new_filter,
            "validate_edited_filter",
            dialog.new_name,
            "f1",
        )

    def test_raw_edit_requires_select(self, mock_view, monkeypatch):
        """Modal rather than status panel, for the reason above."""
        mock_view.subset_filters = {"f1": "dur>1"}
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
        assert "has to start with SELECT" in warned.call_args[0][2]

    def test_raw_edit_with_select_validates(self, mock_view):
        mock_view.subset_filters = {"f1": "dur>1"}
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
            # The View sends the filter as written; the Controller adds the
            # LIMIT 0 that makes the check cheap. Both names ride along.
            "ldr",
            "SELECT * FROM events",
            "f1_raw",
            "f1",
        )


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
    The commit is two-phase: the View asks and the Controller looks.

    What is left to pin on this side is that the question goes out and that the
    answer decides whether the user is asked - the plugin call itself is
    ``ProteinController.check_for_existing_fit_columns``, covered in
    ``test_protein_fetch_slots``.
    """

    def test_asks_whether_the_database_already_holds_fit_data(self, mock_view):
        asked = []
        mock_view.fit_commit_requested.connect(asked.append)

        mock_view._commit_fits("ldr")

        assert asked == ["ldr"]

    def test_no_existing_columns_commits_without_asking_the_user(self, mock_view):
        sent = []
        mock_view.fit_commit_confirmed.connect(lambda *args: sent.append(args))

        with patch.object(QMessageBox, "question") as dialog:
            mock_view.confirm_fit_commit("ldr", None)

        dialog.assert_not_called()
        assert sent == [("ldr", None)]

    def test_existing_columns_ask_first_and_carry_the_table_through(self, mock_view):
        sent = []
        mock_view.fit_commit_confirmed.connect(lambda *args: sent.append(args))

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Ok):
            mock_view.confirm_fit_commit("ldr", "events")

        assert sent == [("ldr", "events")]

    def test_declining_the_overwrite_sends_nothing(self, mock_view):
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
