# type: ignore
"""
Tests for poriscope.plugins.analysistabs.MetadataView.

Comprehensive test coverage for:
- Initialization (_init)
- Control area setup (_set_control_area)
- Figure state management (_clear_figure_state, _reset_actions)
- File dialog (get_save_filename)
- Plot methods (_plot_1d_density, _plot_1d_histogram, _plot_capture_rate,
  _plot_heatmap, _plot_scatterplot, _plot_3d_scatterplot, _plot_all_points_histogram)
- Update plot dispatcher (update_plot)
- Helper functions (format_axis_label)
- __init__ method
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.MetadataView import MetadataView

# ----------------------------- Fixtures ------------------------------


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def mock_qt_dependencies(mocker: MockerFixture) -> None:
    """Mock all Qt and external dependencies to prevent GUI initialization."""
    mocker.patch("poriscope.utils.MetaSubsetTabView.QFileDialog")
    mocker.patch("poriscope.utils.MetaView.QHBoxLayout")
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.MetadataControls")
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.QMessageBox")
    mocker.patch(
        "poriscope.utils.MetaView.MetaView.__init__",
        return_value=None,
    )


@pytest.fixture
def view(mocker: MockerFixture, mock_qt_dependencies: None) -> MetadataView:
    """Create a MetadataView instance with all dependencies mocked."""
    view_instance: MetadataView = MetadataView.__new__(MetadataView)

    # Mock matplotlib figure and axes
    view_instance.figure = mocker.Mock()
    view_instance.figure.clear = mocker.Mock()
    view_instance.figure.add_subplot = mocker.Mock(return_value=mocker.Mock())
    view_instance.figure.set_constrained_layout = mocker.Mock()
    view_instance.figure.axes = []

    view_instance.axes = mocker.Mock()
    view_instance.axes.clear = mocker.Mock()
    view_instance.axes.plot = mocker.Mock()
    view_instance.axes.fill_between = mocker.Mock()
    view_instance.axes.hist = mocker.Mock(
        return_value=([1.0, 2.0, 3.0], [0.0, 1.0, 2.0, 3.0], [])
    )
    view_instance.axes.set_xlabel = mocker.Mock()
    view_instance.axes.set_ylabel = mocker.Mock()
    view_instance.axes.legend = mocker.Mock()
    view_instance.axes.scatter = mocker.Mock()
    view_instance.axes.set_xlim = mocker.Mock()
    view_instance.axes.set_ylim = mocker.Mock()

    view_instance.canvas = mocker.Mock()
    view_instance.canvas.draw = mocker.Mock()

    # Mock signals
    view_instance.add_text_to_display = mocker.Mock()
    view_instance.add_text_to_display.emit = mocker.Mock()
    view_instance.update_tab_action_history = mocker.Mock()
    view_instance.update_tab_action_history.emit = mocker.Mock()

    # Mock helper methods
    view_instance._update_cache = mocker.Mock()
    view_instance._clear_cache = mocker.Mock()
    # Mock methods called by _overlay_plot
    view_instance.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    # The two Step 4a validation intents. Stood in for the same reason global_signal
    # is: this fixture builds the view with __new__ and a patched MetaView.__init__,
    # so no QObject exists behind it and emitting a real Signal raises "Signal source
    # has been deleted".
    view_instance.filter_validation_requested = mocker.Mock()
    view_instance.raw_filter_validation_requested = mocker.Mock()
    # The filter file's two intents. Answered by MetaSubsetTabController in the real
    # app; the tests that drive the answer call set_loaded_filters directly.
    view_instance.filters_load_requested = mocker.Mock()
    view_instance.filters_save_requested = mocker.Mock()
    # The two Step 4a subset intents, answered from whatever a test parked as
    # canned_*. Wired here rather than per test because _overlay_plot clears the
    # answers before emitting, so every test that drives it needs the replay.
    view_instance.metadata_subset_requested = mocker.Mock()
    view_instance.metadata_subset_requested.emit.side_effect = _subset_answers(
        view_instance
    )
    view_instance.all_points_histogram_requested = mocker.Mock()
    view_instance.all_points_histogram_requested.emit.side_effect = (
        _event_intent_answers(view_instance)
    )
    view_instance.event_overlay_requested = mocker.Mock()
    view_instance.event_overlay_requested.emit.side_effect = _event_intent_answers(
        view_instance
    )
    # The four Step 4a intents that replaced the last of this tab's bus emits. The two
    # whose answer is read back on the next statement replay a canned_* value; the two
    # that are fire-and-forget - the per-event feature lookup and the CSV export, which
    # runs in a worker - are bare Mocks, so a test that wants features parks them
    # itself and a test that wants the export just asserts on the emit.
    view_instance.column_type_requested = mocker.Mock()
    view_instance.column_type_requested.emit.side_effect = _column_type_answer(
        view_instance
    )
    view_instance.event_plot_data_requested = mocker.Mock()
    view_instance.event_plot_data_requested.emit.side_effect = _event_plot_data_answer(
        view_instance
    )
    view_instance.plot_features_requested = mocker.Mock()
    view_instance.csv_subset_export_requested = mocker.Mock()
    # Answered by MetadataController.calculate_heatmap in the real app; the tests
    # that drive _plot_heatmap supply the binning themselves via _answer_heatmap,
    # exactly as they used to supply it to a mocked _calculate_heatmap.
    view_instance.heatmap_requested = mocker.Mock()
    # Answered by MetadataController.filter_scatterplot / filter_3d_scatterplot in
    # the real app; the tests that drive them replay the setter via _answer_*.
    view_instance.scatterplot_requested = mocker.Mock()
    view_instance.scatterplot_3d_requested = mocker.Mock()
    # Answered by MetadataController.estimate_kernel_densities in the real app.
    view_instance.density_requested = mocker.Mock()
    # Answered by MetadataController.calculate_histogram_bins in the real app.
    view_instance.histogram_bins_requested = mocker.Mock()
    # Answered by MetadataController.fit_capture_rate in the real app.
    view_instance.capture_rate_requested = mocker.Mock()
    # Answered by MetadataController.count_categories in the real app.
    view_instance.categorical_counts_requested = mocker.Mock()
    # Answered by MetaSubsetTabController.load_event_id_cache in the real app;
    # each test that drives _rebuild_event_id_cache sets its own answer.
    view_instance.event_id_cache_requested = mocker.Mock()

    # Additional mocks needed before _init()
    view_instance._commit_cache = mocker.Mock()
    view_instance.logger = mocker.Mock()
    view_instance.metadatacontrols = mocker.Mock()

    # Initialize the view - this sets up all attributes with correct types
    view_instance._init()

    return view_instance


# ----------------------------- Initialization Tests ------------------------------


def test_init_sets_plot_initialized_false(view: MetadataView) -> None:
    """Verify plot_initialized is set to False."""
    assert view.plot_initialized is False


def test_init_sets_no_cached_data_false(view: MetadataView) -> None:
    """Verify no_cached_data is set to False."""
    assert view.no_cached_data is False


def test_init_sets_subset_export_count_zero(view: MetadataView) -> None:
    """Verify subset_export_count is initialized to 0."""
    assert view.subset_export_count == 0


def test_init_creates_metadata_plots_list(view: MetadataView) -> None:
    """Verify metadata_plots list is created with correct plots."""
    assert len(view.metadata_plots) == 8
    assert "Histogram" in view.metadata_plots
    assert "Normalized Histogram" in view.metadata_plots
    assert "Kernel Density Plot" in view.metadata_plots
    assert "Capture Rate" in view.metadata_plots
    assert "Heatmap" in view.metadata_plots
    assert "Scatterplot" in view.metadata_plots
    assert "3D Scatterplot" in view.metadata_plots


def test_init_creates_event_data_plots_list(view: MetadataView) -> None:
    """Verify event_data_plots list is created with correct plots."""
    assert len(view.event_data_plots) == 6
    assert "Raw Event Overlay" in view.event_data_plots
    assert "Filtered Event Overlay" in view.event_data_plots


def test_init_sets_hist_min_none(view: MetadataView) -> None:
    """Verify hist_min is initialized to None."""
    assert view.hist_min is None


def test_init_sets_hist_max_none(view: MetadataView) -> None:
    """Verify hist_max is initialized to None."""
    assert view.hist_max is None


def test_init_sets_hist_data_empty_list(view: MetadataView) -> None:
    """Verify hist_data is initialized to empty list."""
    assert view.hist_data == []


def test_init_sets_hist_labels_empty_list(view: MetadataView) -> None:
    """Verify hist_labels is initialized to empty list."""
    assert view.hist_labels == []


def test_init_sets_current_sql_filter_none(view: MetadataView) -> None:
    """Verify current_sql_filter is initialized to None."""
    assert view.current_sql_filter is None


def test_init_sets_current_experiment_none(view: MetadataView) -> None:
    """Verify current_experiment is initialized to None."""
    assert view.current_experiment is None


def test_init_sets_current_channel_none(view: MetadataView) -> None:
    """Verify current_channel is initialized to None."""
    assert view.current_channel is None


def test_init_sets_subset_filters_empty_dict(view: MetadataView) -> None:
    """Verify subset_filters is initialized to empty dict."""
    assert view.subset_filters == {}


def test_init_sets_plotted_datasets_empty_set(view: MetadataView) -> None:
    """Verify plotted_datasets is initialized to empty set."""
    assert view.plotted_datasets == set()


def test_init_sets_allowed_plot_type_none(view: MetadataView) -> None:
    """Verify allowed_plot_type is initialized to None."""
    assert view.allowed_plot_type is None


def test_init_sets_allowed_columns_empty_list(view: MetadataView) -> None:
    """Verify allowed_columns is initialized to empty list."""
    assert view.allowed_columns == []


def test_init_sets_allowed_logs_empty_list(view: MetadataView) -> None:
    """Verify allowed_logs is initialized to empty list."""
    assert view.allowed_logs == []


def test_init_sets_allowed_bins_none(view: MetadataView) -> None:
    """Verify allowed_bins is initialized to None."""
    assert view.allowed_bins is None


def test_init_sets_allowed_sizes_none(view: MetadataView) -> None:
    """Verify allowed_sizes is initialized to None."""
    assert view.allowed_sizes is None


# ----------------------------- Control Area Tests ------------------------------


def test_set_control_area_creates_metadata_controls(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    Verify MetadataControls instance is created.

    Still patched in the tab module: Step 3a-bis moved the wiring and layout up to
    ``MetaView``, but ``_build_controls`` - which constructs the widget and stores it
    under this tab's own name - stayed here, which is the whole point of that hook.
    """
    mock_layout: MagicMock = mocker.Mock()
    mock_controls_cls: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.MetadataControls"
    )

    view._set_control_area(mock_layout)

    mock_controls_cls.assert_called_once()
    assert hasattr(view, "metadatacontrols")


def test_set_control_area_connects_action_triggered_signal(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify actionTriggered signal is connected."""
    mock_layout: MagicMock = mocker.Mock()
    view.metadatacontrols = mocker.Mock()
    view.handle_parameter_change = mocker.Mock()  # type: ignore[method-assign]

    view._set_control_area(mock_layout)

    view.metadatacontrols.actionTriggered.connect.assert_called()


def test_set_control_area_adds_controls_to_layout(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    Verify controls are added to layout.

    Since Step 3a-bis the layout is built by ``MetaView._set_control_area``, which the
    tab inherits, so the ``QHBoxLayout`` to patch is the base module's.
    """
    mock_layout: MagicMock = mocker.Mock()
    mocker.patch("poriscope.utils.MetaView.QHBoxLayout")

    view._set_control_area(mock_layout)

    mock_layout.addLayout.assert_called_once()


# ----------------------------- File Dialog Tests ------------------------------


def test_get_save_filename_opens_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify QFileDialog.getSaveFileName is called."""
    mock_dialog: MagicMock = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getSaveFileName",
        return_value=("/path/to/file.csv", "CSV Files (*.csv)"),
    )

    result: str = view.get_save_filename()

    mock_dialog.assert_called_once()
    assert result == "/path/to/file.csv"


def test_get_save_filename_returns_empty_on_cancel(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify empty string is returned when user cancels."""
    mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getSaveFileName",
        return_value=("", ""),
    )

    result: str = view.get_save_filename()

    assert result == ""


# ----------------------------- Clear Figure State Tests ------------------------------


def test_clear_figure_state_clears_heatmap_colorbar(view: MetadataView) -> None:
    """Verify heatmap colorbar reference is cleared."""
    view._heatmap_colorbar = MagicMock()  # type: ignore[assignment,attr-defined]

    view._clear_figure_state()

    assert view._heatmap_colorbar is None  # type: ignore[attr-defined]


def test_clear_figure_state_clears_figure(view: MetadataView) -> None:
    """Verify figure.clear() is called."""
    view._clear_figure_state()

    view.figure.clear.assert_called_once()


def test_clear_figure_state_creates_2d_axes_by_default(view: MetadataView) -> None:
    """Verify 2D axes are created by default."""
    view._clear_figure_state(axis_type="2d")

    view.figure.add_subplot.assert_called_with(1, 1, 1)


def test_clear_figure_state_creates_3d_axes(view: MetadataView) -> None:
    """Verify 3D axes are created when requested."""
    view._clear_figure_state(axis_type="3d")

    view.figure.add_subplot.assert_called_with(1, 1, 1, projection="3d")


def test_clear_figure_state_skips_axes_creation_when_disabled(
    view: MetadataView,
) -> None:
    """Verify axes creation is skipped when create_default_axes=False."""
    view.figure.add_subplot.reset_mock()

    view._clear_figure_state(create_default_axes=False)

    view.figure.add_subplot.assert_not_called()


def test_clear_figure_state_sets_constrained_layout(view: MetadataView) -> None:
    """Verify constrained layout engine is set."""
    view._clear_figure_state()

    view.figure.set_layout_engine.assert_called_with("constrained")


def test_clear_figure_state_calls_clear_cache(view: MetadataView) -> None:
    """Verify _clear_cache is called."""
    view._clear_figure_state()

    view._clear_cache.assert_called()


def test_clear_figure_state_returns_early_when_no_figure(view: MetadataView) -> None:
    """Verify early return when figure is None."""
    view.figure = None  # type: ignore[assignment]
    view._clear_cache.reset_mock()

    view._clear_figure_state()

    view._clear_cache.assert_called_once()


# ----------------------------- Reset Actions Tests ------------------------------


def test_reset_actions_clears_figure_state(view: MetadataView) -> None:
    """Verify figure is cleared."""
    view._reset_actions()

    view.figure.clear.assert_called()


def test_reset_actions_redraws_canvas(view: MetadataView) -> None:
    """Verify canvas is redrawn."""
    view._reset_actions()

    view.canvas.draw.assert_called()


def test_reset_actions_resets_hist_min(view: MetadataView) -> None:
    """Verify hist_min is reset to None."""
    view.hist_min = 10.0

    view._reset_actions()

    assert view.hist_min is None


def test_reset_actions_resets_hist_max(view: MetadataView) -> None:
    """Verify hist_max is reset to None."""
    view.hist_max = 100.0

    view._reset_actions()

    assert view.hist_max is None


def test_reset_actions_resets_hist_data(view: MetadataView) -> None:
    """Verify hist_data is reset to empty list."""
    view.hist_data = [[1.0, 2.0, 3.0]]  # type: ignore[assignment]

    view._reset_actions()

    assert view.hist_data == []


def test_reset_actions_resets_hist_labels(view: MetadataView) -> None:
    """Verify hist_labels is reset to empty list."""
    view.hist_labels = ["label1", "label2"]

    view._reset_actions()

    assert view.hist_labels == []


def test_reset_actions_resets_allowed_plot_type(view: MetadataView) -> None:
    """Verify allowed_plot_type is reset to None."""
    view.allowed_plot_type = "Histogram"

    view._reset_actions()

    assert view.allowed_plot_type is None


def test_reset_actions_resets_allowed_columns(view: MetadataView) -> None:
    """Verify allowed_columns is reset to empty list."""
    view.allowed_columns = ["x", "y"]

    view._reset_actions()

    assert view.allowed_columns == []


def test_reset_actions_resets_allowed_logs(view: MetadataView) -> None:
    """Verify allowed_logs is reset to empty list."""
    view.allowed_logs = [True, False]

    view._reset_actions()

    assert view.allowed_logs == []


def test_reset_actions_resets_allowed_bins(view: MetadataView) -> None:
    """Verify allowed_bins is reset to None."""
    view.allowed_bins = 50  # type: ignore[assignment]

    view._reset_actions()

    assert view.allowed_bins is None


def test_reset_actions_resets_allowed_sizes(view: MetadataView) -> None:
    """Verify allowed_sizes is reset to None."""
    view.allowed_sizes = True  # type: ignore[assignment]

    view._reset_actions()

    assert view.allowed_sizes is None


def test_reset_actions_resets_plotted_datasets(view: MetadataView) -> None:
    """Verify plotted_datasets is reset to empty set."""
    view.plotted_datasets.add(("loader", "exp", 1, "filter", "name"))

    view._reset_actions()

    assert view.plotted_datasets == set()


# ----------------------------- Plot 1D Density Tests ------------------------------


def _answer_density(view, densities, hist_min=0.0, hist_max=1.0):
    """
    Answer ``density_requested`` the way MetadataController does.

    Step 4c split ``_plot_1d_density`` at the estimate and Step 4's closeout moved
    the filter, the shared limits and the accumulation after it: the View emits the
    raw columns and ``set_kernel_densities`` does every bit of drawing and all of
    the bookkeeping. What the Controller decides in between is asserted in
    ``tests/unit/controllers/test_metadata_controller.py``.

    :param view: the view whose request has just been emitted
    :type view: MetadataView
    :param densities: one (positions, density) pair per dataset, to answer with
    :type densities: list
    :param hist_min: the widened lower limit to answer with
    :type hist_min: float
    :param hist_max: the widened upper limit to answer with
    :type hist_max: float
    :return: None
    :rtype: None
    """
    args = view.density_requested.emit.call_args.args
    datasets, ax, x_label, dataset_label = args[0], args[6], args[7], args[9]
    view.set_kernel_densities(
        datasets[-1], dataset_label, densities, hist_min, hist_max, ax, x_label
    )


def test_plot_1d_density_sends_the_raw_column_and_the_log_flag(
    view: MetadataView,
) -> None:
    """
    The filter moved down in Step 4's closeout, so the column leaves unfiltered.

    The newest dataset travels at the end of the accumulated ones rather than being
    appended first, which is what lets the Controller refuse a subset that filters
    away without the View having to take it back out again.
    """
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 2.0, 5.0, 10.0])})

    view._plot_1d_density(view.axes, data, ["x"], ["units"], [True], bins=[7])

    emitted = view.density_requested.emit.call_args.args
    assert [list(dataset) for dataset in emitted[0]] == [[1.0, 2.0, 5.0, 10.0]]
    assert emitted[1] is True
    assert emitted[2] == 7
    assert emitted[8] == "x"


def test_plot_1d_density_does_not_accumulate_before_the_answer(
    view: MetadataView,
) -> None:
    """
    A dataset that filters away must not stay in the overlay, or the next plot
    redraws it and hits the same empty array from inside the loop. Nothing is
    accumulated until ``set_kernel_densities`` runs, and the Controller does not
    call it when nothing survived.
    """
    data: pd.DataFrame = pd.DataFrame({"x": np.array([np.nan, np.nan])})

    view._plot_1d_density(view.axes, data, ["x"], ["units"], [False])

    view.density_requested.emit.assert_called_once()
    assert view.hist_data == []
    assert view.hist_labels == []


def test_set_kernel_densities_accumulates_the_newest_dataset(
    view: MetadataView,
) -> None:
    """Verify the raw column and its label join the overlay when it is drawn."""
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})

    view._plot_1d_density(view.axes, data, ["x"], [""], [False], dataset_label="test")
    _answer_density(view, [(np.array([1.0, 2.0]), np.array([0.1, 0.2]))])

    assert len(view.hist_data) == 1
    assert list(view.hist_data[0]) == [1.0, 2.0, 3.0]
    assert view.hist_labels == ["test"]


def test_set_kernel_densities_takes_the_widened_limits(view: MetadataView) -> None:
    """Verify the shared limits the Model widened come back onto the view."""
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})

    view._plot_1d_density(view.axes, data, ["x"], [""], [False])
    _answer_density(
        view, [(np.array([1.0, 2.0]), np.array([0.1, 0.2]))], hist_min=1.0, hist_max=3.0
    )

    assert view.hist_min == 1.0
    assert view.hist_max == 3.0


def test_set_kernel_densities_clears_axes(view: MetadataView) -> None:
    """
    Verify the axes are cleared before drawing, and not before that.

    They used to be cleared in the request half, so a subset that filtered away
    wiped the plot that was there and drew nothing in its place.
    """
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 2.0])})

    view._plot_1d_density(view.axes, data, ["x"], [""], [False])
    view.axes.clear.assert_not_called()

    _answer_density(view, [(np.array([1.0, 2.0]), np.array([0.1, 0.2]))])
    view.axes.clear.assert_called()


def test_plot_1d_density_raises_on_invalid_bins_list(view: MetadataView) -> None:
    """Verify ValueError is raised for empty bins list."""
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})

    with pytest.raises(ValueError, match="Invalid bins entry"):
        view._plot_1d_density(view.axes, data, ["x"], [""], [False], bins=[])


def test_plot_1d_density_sets_log10_label_when_logscale_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify log10 label is set when logscale is True."""
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 10.0, 100.0])})

    view._plot_1d_density(view.axes, data, ["x"], ["units"], [True])
    _answer_density(view, [(np.array([0.0, 1.0, 2.0]), np.array([0.1, 0.2, 0.3]))])

    view.axes.set_xlabel.assert_called()
    call_args: str = str(view.axes.set_xlabel.call_args)
    assert "log10" in call_args


def test_metaview_runs_each_initializer_exactly_once() -> None:
    """
    ``MetaView.__init__`` is the only constructor, and it calls each hook once.

    Step 3g deleted ``MetadataView.__init__``, which was byte-identical in all five
    tabs. It called ``self._init()`` after ``super().__init__(...)`` - and
    ``MetaView.__init__`` already calls ``_init()`` itself, so **every tab ran it
    twice**, once before ``_setup_ui()`` and once after. That was measured to be a
    no-op before it was removed: no attribute ``_init`` assigns is also assigned
    anywhere in the ``_setup_ui`` call tree, in any of the five tabs, so the second
    call only rewrote its own values.

    Asserted against the source rather than by constructing a tab, because reaching
    ``MetaView.__init__`` at all means building a real ``QWidget``, and the only way
    this file's fixtures avoid that is by patching that very method away.
    """
    source = Path(REPO_ROOT, "poriscope", "utils", "MetaView.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MetaView"
    )
    init = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"
    )
    called = [
        n.func.attr
        for n in ast.walk(init)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "self"
    ]

    assert called.count("_init") == 1, called
    assert called.count("_init_walkthrough") == 1, called
    assert called.count("_setup_ui") == 1, called


def test_no_tab_defines_its_own_dunder_init() -> None:
    """
    All five tabs inherit construction, so the duplicate cannot creep back.

    Asserted across the family rather than on Metadata alone: the five copies were
    identical, so a regression would most likely reintroduce all five.
    """
    from poriscope.plugins.analysistabs.ClusteringView import ClusteringView
    from poriscope.plugins.analysistabs.EventAnalysisView import EventAnalysisView
    from poriscope.plugins.analysistabs.ProteinView import ProteinView
    from poriscope.plugins.analysistabs.RawDataView import RawDataView

    for cls in (
        ClusteringView,
        EventAnalysisView,
        MetadataView,
        ProteinView,
        RawDataView,
    ):
        assert "__init__" not in cls.__dict__, f"{cls.__name__} regrew an __init__"


# ----------------------------- Plot Capture Rate Tests ------------------------------


def _answer_categorical_counts(view):
    """
    Answer ``categorical_counts_requested`` the way MetadataController does.

    Step 4's closeout moved the tallying to ``MetadataModel.categorical_counts``, so
    the View no longer decides what the categories are. The real Model is used here
    rather than a canned answer, so these tests still exercise the counting they were
    written to cover; what the counting *produces* for nulls, NaNs and numeric
    ordering is asserted directly in ``tests/unit/models/test_metadata_model.py``.

    :param view: the view whose request has just been emitted
    :type view: MetadataView
    :return: None
    :rtype: None
    """
    from poriscope.plugins.analysistabs.MetadataModel import MetadataModel

    datasets, labels, ax, x_label, y_label = (
        view.categorical_counts_requested.emit.call_args.args
    )
    counts = MetadataModel.__new__(MetadataModel).categorical_counts(datasets)
    view.set_categorical_counts(counts, labels, ax, x_label, y_label)


def _answer_capture_rate(view, numbins=4):
    """
    Answer ``capture_rate_requested`` the way MetadataController does.

    Step 4c moved the binning and the exponential fit to ``MetadataModel``, so the
    View no longer decides either. These tests supplied a stubbed ``curve_fit``
    before; they supply the finished fit here instead, and what the fit actually
    produces is asserted in ``tests/unit/models/test_metadata_model.py``.

    :param view: the view whose request has just been emitted
    :type view: MetadataView
    :param numbins: how many bins to answer with
    :type numbins: int
    :return: None
    :rtype: None
    """
    data, _bins, _sizes, ax, x_label, y_label, dataset_label = (
        view.capture_rate_requested.emit.call_args.args
    )
    edges = np.linspace(np.min(data), np.max(data), numbins + 1)
    centers = edges[:-1] + np.diff(edges) / 2.0
    counts = np.ones_like(centers)
    view.set_capture_rate(
        edges,
        centers,
        counts,
        counts,
        1.0,
        0.1,
        data,
        ax,
        x_label,
        y_label,
        dataset_label,
    )


def test_plot_capture_rate_sends_the_column_as_it_stands(view: MetadataView) -> None:
    """
    The request carries the event times, not the inter-event times.

    Step 4's closeout moved the gap calculation to the Model, and with it the two
    conditions that were judged on its result - too little surviving data, and how
    much the log filter dropped. Both are pinned in
    ``tests/unit/controllers/test_metadata_controller.py`` now; a View that still
    reduced the column before emitting would fail here.
    """
    times = np.array([1.0, 1.01, 3.0])
    data: pd.DataFrame = pd.DataFrame({"time": times})

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False])

    sent = view.capture_rate_requested.emit.call_args[0][0]
    np.testing.assert_array_equal(sent, times)


def test_plot_capture_rate_calls_hist(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify histogram is plotted."""
    data: pd.DataFrame = pd.DataFrame(
        {
            "time": np.array(
                [0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 2.0, 2.3]
            )
        }
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False])
    _answer_capture_rate(view)

    view.axes.hist.assert_called()


def test_plot_capture_rate_fits_exponential_curve(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify exponential curve is fitted and plotted."""
    data: pd.DataFrame = pd.DataFrame(
        {
            "time": np.array(
                [0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 2.0, 2.3]
            )
        }
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False])
    _answer_capture_rate(view)

    # the curve itself is fitted by MetadataModel and tested there; what is pinned
    # here is that the answer is drawn, as a line over the histogram
    view.axes.plot.assert_called()


def test_plot_capture_rate_raises_on_invalid_bins_list(view: MetadataView) -> None:
    """Verify ValueError is raised for empty bins list."""
    data: pd.DataFrame = pd.DataFrame(
        {
            "time": np.array(
                [0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 2.0, 2.3]
            )
        }
    )

    with pytest.raises(ValueError, match="Invalid bins entry"):
        view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False], bins=[])


def test_plot_capture_rate_sets_axis_labels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axis labels are set correctly."""
    data: pd.DataFrame = pd.DataFrame(
        {
            "time": np.array(
                [0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 2.0, 2.3]
            )
        }
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False])
    _answer_capture_rate(view)

    view.axes.set_xlabel.assert_called()
    view.axes.set_ylabel.assert_called()


def test_plot_capture_rate_uses_first_bins_entry(view: MetadataView) -> None:
    """Verify capture-rate plotting uses the first element from a bins list."""
    data = pd.DataFrame(
        {
            "time": np.array(
                [0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 2.0, 2.3]
            )
        }
    )
    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False], bins=[4])

    # the list is unwrapped before the request goes out; that the Model then makes
    # four bins of it is asserted in tests/unit/models/test_metadata_model.py
    assert view.capture_rate_requested.emit.call_args.args[1] == 4


def test_plot_capture_rate_sets_log10_label_when_logscale_true(
    view: MetadataView,
    mocker: MockerFixture,
) -> None:
    """Verify log-scaled capture-rate plots prefix the x-axis label with log10."""
    data = pd.DataFrame(
        {
            "time": np.array(
                [0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 2.0, 2.3]
            )
        }
    )
    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [True])
    _answer_capture_rate(view)

    xlabel_call = view.axes.set_xlabel.call_args
    assert xlabel_call is not None
    xlabel = xlabel_call.args[0]
    assert "log10" in xlabel


# ----------------------------- Format Axis Label Tests ------------------------------


def test_format_axis_label_adds_unit(view: MetadataView) -> None:
    """Verify unit is added in parentheses."""
    result: str = view.format_axis_label("Duration", "ms")
    assert result == "Duration (ms)"


def test_format_axis_label_replaces_existing_unit(view: MetadataView) -> None:
    """Verify existing unit is replaced."""
    result: str = view.format_axis_label("Duration (s)", "ms")
    assert result == "Duration (ms)"


def test_format_axis_label_no_unit_returns_plain(view: MetadataView) -> None:
    """Verify plain label is returned when no unit."""
    result: str = view.format_axis_label("Duration", "")
    assert result == "Duration"


def test_format_axis_label_handles_multiple_parentheses(view: MetadataView) -> None:
    """Verify only last parenthetical is replaced."""
    result: str = view.format_axis_label("Current (baseline) (pA)", "nA")
    assert "nA" in result


# ----------------------------- Plot 1D Histogram Tests ------------------------------


def _answer_histogram_bins(view, numbins=8):
    """
    Answer ``histogram_bins_requested`` the way MetadataController does.

    Step 4c split ``_plot_1d_histogram`` at the bin decision, Step 4's closeout moved
    the counting down after it, and then the filter, the shared limits and the
    accumulation as well: the View emits every overlaid dataset raw and
    ``set_histogram_bins`` is handed the tallies. The real Model is used here so
    these tests still exercise the counting they were written over; what the bin
    decision returns for a given request is asserted directly in
    ``tests/unit/models/test_metadata_model.py``.

    :param view: the view whose request has just been emitted
    :type view: MetadataView
    :param numbins: how many bins to answer with
    :type numbins: int
    :return: None
    :rtype: None
    """
    from poriscope.plugins.analysistabs.MetadataModel import MetadataModel

    (
        datasets,
        logx,
        _bins,
        _sizes,
        hist_min,
        hist_max,
        norm,
        ax,
        x_label,
        _column,
        dataset_label,
    ) = view.histogram_bins_requested.emit.call_args.args

    model = MetadataModel()
    filtered = model.logscale_and_filter_datasets(datasets, logx)
    hist_min, hist_max = model.widen_shared_limits(filtered[-1], hist_min, hist_max)
    _edges, centers, widths, counts = model.overlaid_histograms(
        filtered, numbins, False, hist_min, hist_max, norm
    )
    view.set_histogram_bins(
        datasets[-1],
        dataset_label,
        centers,
        widths,
        counts,
        hist_min,
        hist_max,
        ax,
        x_label,
        logx,
        norm,
    )


def test_plot_1d_histogram_raises_on_invalid_bins_list(view: MetadataView) -> None:
    """Verify ValueError is raised for invalid bins list."""
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})

    with pytest.raises(ValueError, match="Invalid bins entry"):
        view._plot_1d_histogram(view.axes, data, ["x"], [""], [False], bins=[])


def test_plot_1d_histogram_uses_first_bins_entry(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify bins list is reduced to first entry."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})

    view._plot_1d_histogram(view.axes, data, ["x"], ["u"], [False], bins=[10])

    # the list is unwrapped to its first entry before the request goes out; what
    # the bin decision then does with it is asserted on the Model
    assert view.histogram_bins_requested.emit.call_args.args[2] == 10


def test_plot_1d_histogram_sends_the_raw_column_and_the_log_flag(
    view: MetadataView,
) -> None:
    """
    The same shape as the density's, deliberately: the two write the same
    accumulator and the same pair of shared limits, which is why they converted
    together rather than one branch each.
    """
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 5.0, 10.0])})

    view._plot_1d_histogram(view.axes, data, ["x"], ["units"], [True])

    emitted = view.histogram_bins_requested.emit.call_args.args
    assert [list(dataset) for dataset in emitted[0]] == [[1.0, 2.0, 5.0, 10.0]]
    assert emitted[1] is True
    assert emitted[9] == "x"


def test_plot_1d_histogram_normalizes_when_norm_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify histogram is normalized when norm=True."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})

    view._plot_1d_histogram(view.axes, data, ["x"], ["u"], [False], norm=True)
    _answer_histogram_bins(view)

    ylabel_call = view.axes.set_ylabel.call_args
    assert ylabel_call is not None
    assert "Fraction" in ylabel_call.args[0]


def test_plot_1d_histogram_sets_log10_label_when_logscale_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify log10 label is set when logscale is True."""
    data = pd.DataFrame({"x": np.array([1.0, 10.0, 100.0])})

    view._plot_1d_histogram(view.axes, data, ["x"], ["units"], [True])
    _answer_histogram_bins(view)

    xlabel_call = view.axes.set_xlabel.call_args
    assert xlabel_call is not None
    assert "log10" in xlabel_call.args[0]


def test_plot_1d_histogram_handles_bin_sizes(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify bin sizes mode reaches the request as a width."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})
    view.hist_min = 0.0
    view.hist_max = 10.0

    view._plot_1d_histogram(
        view.axes, data, ["x"], ["u"], [False], bins=[0.5], sizes=True
    )

    emitted = view.histogram_bins_requested.emit.call_args.args
    assert emitted[2] == 0.5
    assert emitted[3] is True
    assert emitted[4] == 0.0
    assert emitted[5] == 10.0


def test_plot_1d_histogram_overlays_multiple_datasets(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    Verify multiple datasets can be overlaid.

    Each one joins the accumulator as it is drawn, so the second request carries
    the first dataset as well as its own.
    """
    data1 = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})
    data2 = pd.DataFrame({"x": np.array([4.0, 5.0, 6.0])})

    view._plot_1d_histogram(view.axes, data1, ["x"], ["u"], [False], dataset_label="d1")
    _answer_histogram_bins(view)
    view._plot_1d_histogram(view.axes, data2, ["x"], ["u"], [False], dataset_label="d2")

    assert len(view.histogram_bins_requested.emit.call_args.args[0]) == 2

    _answer_histogram_bins(view)

    assert len(view.hist_data) == 2
    assert view.hist_labels == ["d1", "d2"]


# ----------------------------- Plot Heatmap Tests ------------------------------


def _answer_heatmap(view, x_bins, y_bins, z_grid):
    """
    Answer ``heatmap_requested`` the way MetadataController does.

    Step 4c split ``_plot_heatmap`` at the binning: it emits the filtered columns
    and ``set_heatmap`` does every bit of drawing. The binning result is supplied
    here rather than computed, which is what the mocked ``_calculate_heatmap``
    used to do for these tests.

    :param view: the view whose request has just been emitted
    :type view: MetadataView
    :param x_bins: bin-center x values to answer with
    :type x_bins: np.ndarray
    :param y_bins: bin-center y values to answer with
    :type y_bins: np.ndarray
    :param z_grid: the log2-scaled counts to answer with
    :type z_grid: np.ndarray
    :return: None
    :rtype: None
    """
    context = view.heatmap_requested.emit.call_args.args[5:]
    view.set_heatmap(x_bins, y_bins, z_grid, *context)


def test_plot_heatmap_requests_the_binning(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify the binning is asked for rather than done here."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view._plot_heatmap(view.axes, data, ["x", "y"], ["u1", "u2"], [False, False])

    view.heatmap_requested.emit.assert_called_once()
    # the raw columns go out, and the drawing context comes back untouched
    emitted = view.heatmap_requested.emit.call_args.args
    assert emitted[5] is view.axes
    assert len(emitted) == 9


def test_plot_heatmap_sets_axis_labels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axis labels are set correctly."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    x_bins = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5])
    y_bins = np.array([3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5])
    z_grid = np.ones((10, 10))

    # Mock the colorbar
    mock_colorbar = mocker.Mock()
    mock_colorbar.get_ticks = mocker.Mock(
        return_value=np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    )
    view.figure.colorbar = mocker.Mock(return_value=mock_colorbar)

    view._plot_heatmap(view.axes, data, ["x", "y"], ["u1", "u2"], [False, False])
    _answer_heatmap(view, x_bins, y_bins, z_grid)

    view.axes.set_xlabel.assert_called()
    view.axes.set_ylabel.assert_called()


def test_plot_heatmap_sets_log10_labels_when_logscale_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify log10 labels are set when logscales are True."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    x_bins = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5])
    y_bins = np.array([3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5])
    z_grid = np.ones((10, 10))

    # Mock the colorbar
    mock_colorbar = mocker.Mock()
    mock_colorbar.get_ticks = mocker.Mock(
        return_value=np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    )
    view.figure.colorbar = mocker.Mock(return_value=mock_colorbar)

    view._plot_heatmap(view.axes, data, ["x", "y"], ["u1", "u2"], [True, True])
    _answer_heatmap(view, x_bins, y_bins, z_grid)

    xlabel_call = view.axes.set_xlabel.call_args
    ylabel_call = view.axes.set_ylabel.call_args
    assert xlabel_call is not None
    assert ylabel_call is not None
    assert "log10" in xlabel_call.args[0]
    assert "log10" in ylabel_call.args[0]


def test_plot_heatmap_removes_previous_colorbar(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify previous colorbar is removed on overlay."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    x_bins = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5])
    y_bins = np.array([3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5])
    z_grid = np.ones((10, 10))

    # Mock the colorbar
    mock_new_colorbar = mocker.Mock()
    mock_new_colorbar.get_ticks = mocker.Mock(
        return_value=np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    )
    view.figure.colorbar = mocker.Mock(return_value=mock_new_colorbar)

    # Create a mock for the previous colorbar
    mock_old_colorbar = mocker.Mock()
    mock_old_colorbar.ax = mocker.Mock()
    mock_old_colorbar.ax.figure = view.figure
    view._heatmap_colorbar = mock_old_colorbar  # type: ignore[attr-defined]

    view._plot_heatmap(view.axes, data, ["x", "y"], ["u1", "u2"], [False, False])
    _answer_heatmap(view, x_bins, y_bins, z_grid)

    mock_old_colorbar.remove.assert_called_once()


# ----------------------------- Plot Scatterplot Tests ------------------------------


def _answer_scatterplot(view: MetadataView, columns: tuple) -> None:
    """
    Stand in for the Controller answering ``scatterplot_requested``.

    Replays ``set_scatterplot`` with the drawing context the View emitted, so the
    test drives the request and the drawing as one, exactly as the app does.

    :param view: the view whose request to answer
    :type view: MetadataView
    :param columns: the filtered columns to answer with
    :type columns: tuple
    :return: None
    :rtype: None
    """
    context = view.scatterplot_requested.emit.call_args.args[2:]
    view.set_scatterplot(columns, *context)


def test_plot_scatterplot_requests_the_filtering(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify the filter is asked for rather than done here."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view._plot_scatterplot(view.axes, data, ["x", "y"], ["u1", "u2"], [True, False])

    emitted = view.scatterplot_requested.emit.call_args.args
    assert [list(column) for column in emitted[0]] == [[1.0, 2.0], [3.0, 4.0]]
    assert emitted[1] == [True, False]
    assert emitted[2] is view.axes


def test_plot_scatterplot_calls_scatter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify scatter is called on axes."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view._plot_scatterplot(view.axes, data, ["x", "y"], ["u1", "u2"], [False, False])
    _answer_scatterplot(view, (np.array([1.0, 2.0]), np.array([3.0, 4.0])))

    view.axes.scatter.assert_called_once()


def test_plot_scatterplot_sets_axis_labels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axis labels are set."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view._plot_scatterplot(view.axes, data, ["x", "y"], ["u1", "u2"], [False, False])
    _answer_scatterplot(view, (np.array([1.0, 2.0]), np.array([3.0, 4.0])))

    view.axes.set_xlabel.assert_called()
    view.axes.set_ylabel.assert_called()


def test_plot_scatterplot_sets_log10_labels_when_logscale_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify log10 labels are set when logscales are True."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view._plot_scatterplot(view.axes, data, ["x", "y"], ["u1", "u2"], [True, True])
    _answer_scatterplot(view, (np.array([1.0, 2.0]), np.array([3.0, 4.0])))

    xlabel_call = view.axes.set_xlabel.call_args
    ylabel_call = view.axes.set_ylabel.call_args
    assert xlabel_call is not None
    assert ylabel_call is not None
    assert "log10" in xlabel_call.args[0]
    assert "log10" in ylabel_call.args[0]


# ----------------------------- Plot 3D Scatterplot Tests ------------------------------


_THREE_COLUMNS = pd.DataFrame(
    {
        "x": np.array([1.0, 2.0]),
        "y": np.array([3.0, 4.0]),
        "z": np.array([5.0, 6.0]),
    }
)


def _answer_3d_scatterplot(view: MetadataView, columns: tuple) -> None:
    """
    Stand in for the Controller answering ``scatterplot_3d_requested``.

    :param view: the view whose request to answer
    :type view: MetadataView
    :param columns: the filtered columns to answer with
    :type columns: tuple
    :return: None
    :rtype: None
    """
    context = view.scatterplot_3d_requested.emit.call_args.args[2:]
    view.set_3d_scatterplot(columns, *context)


_THREE_FILTERED = (
    np.array([1.0, 2.0]),
    np.array([3.0, 4.0]),
    np.array([5.0, 6.0]),
)


def test_plot_3d_scatterplot_requests_the_filtering(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify all three columns and all three flags go out to be filtered."""
    view._plot_3d_scatterplot(
        view.axes,
        _THREE_COLUMNS,
        ["x", "y", "z"],
        ["u1", "u2", "u3"],
        [True, False, True],
    )

    emitted = view.scatterplot_3d_requested.emit.call_args.args
    assert len(emitted[0]) == 3
    assert emitted[1] == [True, False, True]


def test_plot_3d_scatterplot_calls_scatter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify scatter is called on 3D axes."""
    # Make isinstance check pass by setting view.axes as an instance
    type(view.axes).__name__ = "Axes3D"

    view._plot_3d_scatterplot(
        view.axes,
        _THREE_COLUMNS,
        ["x", "y", "z"],
        ["u1", "u2", "u3"],
        [False, False, False],
    )
    _answer_3d_scatterplot(view, _THREE_FILTERED)

    view.axes.scatter.assert_called_once()


def test_plot_3d_scatterplot_sets_axis_labels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify all three axis labels are set."""
    # Make isinstance check pass
    type(view.axes).__name__ = "Axes3D"
    view.axes.set_zlabel = mocker.Mock()

    view._plot_3d_scatterplot(
        view.axes,
        _THREE_COLUMNS,
        ["x", "y", "z"],
        ["u1", "u2", "u3"],
        [False, False, False],
    )
    _answer_3d_scatterplot(view, _THREE_FILTERED)

    view.axes.set_xlabel.assert_called()
    view.axes.set_ylabel.assert_called()
    view.axes.set_zlabel.assert_called()


def test_3d_scatterplot_rebuilds_two_dimensional_axes(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    A 2-D pair left by the previous plot type is replaced before drawing.

    The check used to sit in the request half, after the filtering; it belongs
    with the drawing, which is the half that needs the axes.
    """
    type(view.axes).__name__ = "Axes"
    view._reset_actions = mocker.Mock()
    view.axes.set_zlabel = mocker.Mock()

    view._plot_3d_scatterplot(
        view.axes,
        _THREE_COLUMNS,
        ["x", "y", "z"],
        ["u1", "u2", "u3"],
        [False, False, False],
    )
    _answer_3d_scatterplot(view, _THREE_FILTERED)

    view._reset_actions.assert_called_once_with(axis_type="3d")


# ----------------------------- Plot All Points Histogram Tests ------------------------------


def test_plot_all_points_histogram_plots_data(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot is called with data."""
    view._plot_all_points_histogram(
        view.axes,
        np.array([1.0, 2.0]),
        np.array([3.0, 4.0]),
        ["x", "y"],
        ["u1", "u2"],
    )

    view.axes.plot.assert_called()


def test_plot_all_points_histogram_normalizes_when_norm_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify data is normalized when norm=True."""
    view._plot_all_points_histogram(
        view.axes,
        np.array([1.0, 2.0]),
        np.array([10.0, 20.0]),
        ["x", "y"],
        ["u1", "u2"],
        norm=True,
    )

    ylabel_call = view.axes.set_ylabel.call_args
    assert ylabel_call is not None
    assert "Normalized" in ylabel_call.args[0]


def test_plot_all_points_histogram_clears_axes(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axes are cleared before plotting."""
    view._plot_all_points_histogram(
        view.axes,
        np.array([1.0, 2.0]),
        np.array([3.0, 4.0]),
        ["x", "y"],
        ["u1", "u2"],
    )

    view.axes.clear.assert_called()


# ----------------------------- Update Plot Tests ------------------------------


def test_update_plot_calls_histogram_for_histogram_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _plot_1d_histogram is called for Histogram plot type."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})

    # Mock the data_cache and _commit_cache
    view.data_cache = []  # type: ignore[attr-defined]
    view._commit_cache = mocker.Mock()  # type: ignore[method-assign]

    view._plot_1d_histogram = mocker.Mock()  # type: ignore[method-assign]

    view.update_plot("Histogram", data, ["x"], ["u"], [False])

    view._plot_1d_histogram.assert_called_once()


def test_update_plot_calls_density_for_kernel_density_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _plot_1d_density is called for Kernel Density Plot type."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})

    view.data_cache = []  # type: ignore[attr-defined]
    view._commit_cache = mocker.Mock()  # type: ignore[method-assign]
    view._plot_1d_density = mocker.Mock()  # type: ignore[method-assign]

    view.update_plot("Kernel Density Plot", data, ["x"], ["u"], [False])

    view._plot_1d_density.assert_called_once()


def test_update_plot_calls_capture_rate_for_capture_rate_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _plot_capture_rate is called for Capture Rate type."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})

    view.data_cache = []  # type: ignore[attr-defined]
    view._commit_cache = mocker.Mock()  # type: ignore[method-assign]
    view._plot_capture_rate = mocker.Mock()  # type: ignore[method-assign]

    view.update_plot("Capture Rate", data, ["x"], ["u"], [False])

    view._plot_capture_rate.assert_called_once()


def test_update_plot_handles_capture_rate_value_error(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify ValueError from capture rate is caught and message emitted."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0])})

    view.data_cache = []  # type: ignore[attr-defined]
    view._commit_cache = mocker.Mock()  # type: ignore[method-assign]
    view._plot_capture_rate = mocker.Mock(  # type: ignore[method-assign]
        side_effect=ValueError("Not enough data")
    )

    view.update_plot("Capture Rate", data, ["x"], ["u"], [False], dataset_label="test")

    view.add_text_to_display.emit.assert_called()


def test_update_plot_calls_scatterplot_for_scatterplot_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _plot_scatterplot is called for Scatterplot type."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view.data_cache = []  # type: ignore[attr-defined]
    view._commit_cache = mocker.Mock()  # type: ignore[method-assign]
    view._plot_scatterplot = mocker.Mock()  # type: ignore[method-assign]

    view.update_plot("Scatterplot", data, ["x", "y"], ["u1", "u2"], [False, False])

    view._plot_scatterplot.assert_called_once()


def test_update_plot_calls_heatmap_for_heatmap_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _plot_heatmap is called for Heatmap type."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view.data_cache = []  # type: ignore[attr-defined]
    view._commit_cache = mocker.Mock()  # type: ignore[method-assign]
    view._plot_heatmap = mocker.Mock()  # type: ignore[method-assign]

    view.update_plot("Heatmap", data, ["x", "y"], ["u1", "u2"], [False, False])

    view._plot_heatmap.assert_called_once()


def test_update_plot_calls_3d_scatterplot_for_3d_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _plot_3d_scatterplot is called for 3D Scatterplot type."""
    data = pd.DataFrame(
        {
            "x": np.array([1.0, 2.0]),
            "y": np.array([3.0, 4.0]),
            "z": np.array([5.0, 6.0]),
        }
    )

    view.data_cache = []  # type: ignore[attr-defined]
    view._commit_cache = mocker.Mock()  # type: ignore[method-assign]
    view._plot_3d_scatterplot = mocker.Mock()  # type: ignore[method-assign]

    view.update_plot(
        "3D Scatterplot",
        data,
        ["x", "y", "z"],
        ["u1", "u2", "u3"],
        [False, False, False],
    )

    view._plot_3d_scatterplot.assert_called_once()


def test_update_plot_raises_for_unsupported_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify NotImplementedError is raised for unsupported plot types."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0])})

    view.data_cache = []  # type: ignore[attr-defined]
    view._commit_cache = mocker.Mock()  # type: ignore[method-assign]

    with pytest.raises(NotImplementedError, match="not yet supported"):
        view.update_plot("Unsupported Type", data, ["x"], ["u"], [False])


def test_update_plot_redraws_canvas(view: MetadataView, mocker: MockerFixture) -> None:
    """Verify canvas is redrawn after plotting."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})

    view.data_cache = []  # type: ignore[attr-defined]
    view._commit_cache = mocker.Mock()  # type: ignore[method-assign]

    view.update_plot("Histogram", data, ["x"], ["u"], [False])

    view.canvas.draw.assert_called()


# ----------------------------- Overlay Plot Tests ------------------------------


def test_overlay_plot_sets_plot_initialized_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot_initialized flag is set to True."""
    view.figure.axes = []
    view.plot_initialized = False

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    assert view.plot_initialized is True


def test_overlay_plot_defaults_to_full_dataset_when_no_filters(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify defaults to Full Dataset when selected_filters is None or empty."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    view.metadata_subset_requested.emit.assert_called()


def test_overlay_plot_defaults_experiments_and_channels_when_none(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify defaults to {None: [None]} when no experiments/channels selected."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": None}
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    view.metadata_subset_requested.emit.assert_called()


def test_overlay_plot_rejects_multiple_experiments_for_event_overlay(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Raw Event Overlay rejects multiple experiments."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw Event Overlay",
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {
        "test_loader": {"exp1": [1], "exp2": [1]}
    }

    result = view._overlay_plot(parameters)

    assert result is False
    view.add_text_to_display.emit.assert_called()


def test_overlay_plot_rejects_multiple_channels_for_heatmap(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Heatmap rejects multiple channels."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Heatmap",
        "x_axis": "duration",
        "y_axis": "current",
        "x_log": False,
        "y_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1, 2]}}

    result = view._overlay_plot(parameters)

    assert result is False
    view.add_text_to_display.emit.assert_called()


def test_overlay_plot_rejects_multiple_filters_for_filtered_event_overlay(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Filtered Event Overlay rejects multiple subsets."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Filtered Event Overlay",
    }

    view.get_selected_filters = mocker.Mock(
        return_value={"Filter1": "WHERE x > 1", "Filter2": "WHERE x < 10"}
    )
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}

    result = view._overlay_plot(parameters)

    assert result is False
    view.add_text_to_display.emit.assert_called()


def _subset_answers(view: MetadataView) -> Callable[..., None]:
    """
    Stand in for the Controller answering ``metadata_subset_requested``.

    ``_overlay_plot`` clears ``query``, ``plot_data`` and ``column_units`` before
    emitting and reads them back on the next statement, so that a fetch which failed
    cannot be mistaken for one that succeeded. A bare ``Mock()`` leaves them cleared,
    so a stub has to make the same assignments the real Controller would - from
    whatever the test parked as ``canned_*``.

    ``canned_units`` is a single value, expanded to one per column, because that is
    what the three separate ``get_column_units`` round trips produced before Step 4a
    collapsed them into one list.

    :param view: the view whose answers to set
    :type view: MetadataView
    :return: a side_effect for the mocked intent emit
    :rtype: Callable[..., None]
    """

    def _emit(loader: str, columns: list, sql_filter: str, scope: object) -> None:
        view.query = getattr(view, "canned_query", "SELECT 1")
        view.plot_data = getattr(view, "canned_plot_data", None)
        units = getattr(view, "canned_units", None)
        view.column_units = [units] * len(columns)

    return _emit


def _event_intent_answers(view: MetadataView) -> Callable[..., None]:
    """
    The same, for either of the two event-data intents.

    Step 4's closeout took the generator off the widget: the Controller now answers
    both intents by drawing through a setter, and sets the query only once the whole
    fetch *and* the reduction succeeded. So the one thing a test parks is
    ``canned_event_query``, which is what says the round trip got that far.

    :param view: the view whose answers to set
    :type view: MetadataView
    :return: a side_effect for the mocked intent emit
    :rtype: Callable[..., None]
    """

    def _emit(*args: object) -> None:
        view.event_query = getattr(view, "canned_event_query", "")

    return _emit


def _column_type_answer(view: MetadataView) -> Callable[..., None]:
    """
    Stand in for the Controller answering ``column_type_requested``.

    ``handle_parameter_change`` clears ``column_type`` before asking, so a test that
    wants the categorical guard to see a type parks it as ``canned_column_type``.
    Absent that, the answer is None, which is what a failed lookup leaves.

    :param view: the view whose answer to set
    :type view: MetadataView
    :return: a side_effect for the mocked intent emit
    :rtype: Callable[..., None]
    """

    def _emit(loader: str, column: str) -> None:
        view.column_type = getattr(view, "canned_column_type", None)

    return _emit


def _event_plot_data_answer(view: MetadataView) -> Callable[..., None]:
    """
    Stand in for the Controller answering ``event_plot_data_requested``.

    The one intent replaced three chained emits, so a test that used to park an
    experiment id and a query result now parks only the generator they were resolved
    in order to fetch - as ``canned_plot_events_generator``.

    :param view: the view whose answer to set
    :type view: MetadataView
    :return: a side_effect for the mocked intent emit
    :rtype: Callable[..., None]
    """

    def _emit(
        loader: str,
        event_ids: list,
        exp: object,
        channel: object,
        scope: object,
        action_label: str,
    ) -> None:
        view.plot_events_generator = getattr(view, "canned_plot_events_generator", None)

    return _emit


def test_overlay_plot_constructs_histogram_columns_correctly(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Histogram uses correct columns and logscales."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": True,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_plot_data = plot_data
    view.canned_query = "SELECT * FROM events"
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    call_args = view.update_plot.call_args
    assert call_args is not None
    assert call_args.args[2] == ["duration"]
    assert call_args.args[4] == [True]


def test_overlay_plot_constructs_scatterplot_columns_correctly(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Scatterplot uses correct columns and logscales."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Scatterplot",
        "x_axis": "duration",
        "y_axis": "current",
        "x_log": True,
        "y_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    plot_data = pd.DataFrame({"duration": [1.0, 2.0], "current": [3.0, 4.0]})
    view.canned_plot_data = plot_data
    view.canned_query = "SELECT * FROM events"
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    call_args = view.update_plot.call_args
    assert call_args is not None
    assert call_args.args[2] == ["duration", "current"]
    assert call_args.args[4] == [True, False]


def test_overlay_plot_constructs_3d_scatterplot_columns_correctly(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify 3D Scatterplot uses correct columns and logscales."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "3D Scatterplot",
        "x_axis": "duration",
        "y_axis": "current",
        "z_axis": "voltage",
        "x_log": True,
        "y_log": False,
        "z_log": True,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    plot_data = pd.DataFrame(
        {
            "duration": [1.0, 2.0],
            "current": [3.0, 4.0],
            "voltage": [5.0, 6.0],
        }
    )
    view.canned_plot_data = plot_data
    view.canned_query = "SELECT * FROM events"
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    call_args = view.update_plot.call_args
    assert call_args is not None
    assert call_args.args[2] == ["duration", "current", "voltage"]
    assert call_args.args[4] == [True, False, True]


def test_overlay_plot_constructs_capture_rate_with_start_time(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Capture Rate uses start_time with log scale."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Capture Rate",
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    plot_data = pd.DataFrame(
        {"start_time": [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]}
    )
    view.canned_plot_data = plot_data
    view.canned_query = "SELECT * FROM events"
    view.canned_units = "s"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    call_args = view.update_plot.call_args
    assert call_args is not None
    assert call_args.args[2] == ["start_time"]
    assert call_args.args[4] == [True]


def test_overlay_plot_returns_false_for_unsupported_metadata_plot_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify unsupported metadata plot type returns False."""
    view.metadata_plots.append("Unsupported Type")

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Unsupported Type",
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}

    result = view._overlay_plot(parameters)

    assert result is False
    view.add_text_to_display.emit.assert_called()


def test_overlay_plot_resets_when_columns_change(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot resets when columns change."""
    view.figure.axes = []
    view.allowed_columns = ["old_column"]
    view.allowed_plot_type = "Histogram"
    view._reset_actions = mocker.Mock()

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "new_column",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = pd.DataFrame({"new_column": [1.0, 2.0, 3.0]})
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    view._reset_actions.assert_called_once()


def test_overlay_plot_resets_when_logscales_change(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot resets when logscales change."""
    view.figure.axes = []
    view.allowed_columns = ["duration"]
    view.allowed_logs = [False]
    view.allowed_plot_type = "Histogram"
    view._reset_actions = mocker.Mock()

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": True,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    view._reset_actions.assert_called_once()


def test_overlay_plot_resets_when_plot_type_changes(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot resets when plot type changes."""
    view.figure.axes = []
    view.allowed_columns = ["duration"]
    view.allowed_logs = [False]
    view.allowed_plot_type = "Kernel Density Plot"
    view._reset_actions = mocker.Mock()

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    view._reset_actions.assert_called_once()


def test_overlay_plot_resets_when_bins_change_for_bin_sensitive_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot resets when bins change for bin-sensitive plots."""
    view.figure.axes = []
    view.allowed_columns = ["duration"]
    view.allowed_logs = [False]
    view.allowed_plot_type = "Histogram"
    view.allowed_bins = [30]
    view._reset_actions = mocker.Mock()

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    view._reset_actions.assert_called_once()


def test_overlay_plot_resets_when_sizes_change_for_bin_sensitive_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot resets when sizes flag changes for bin-sensitive plots."""
    view.figure.axes = []
    view.allowed_columns = ["duration"]
    view.allowed_logs = [False]
    view.allowed_plot_type = "Histogram"
    view.allowed_bins = [50]
    view.allowed_sizes = False
    view._reset_actions = mocker.Mock()

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": True,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    view._reset_actions.assert_called_once()


def test_overlay_plot_rejects_duplicate_columns(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify overlay rejects plots with duplicate columns."""
    view.figure.axes = []
    mock_warning = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QMessageBox.warning"
    )

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Scatterplot",
        "x_axis": "duration",
        "y_axis": "duration",
        "x_log": False,
        "y_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}

    result = view._overlay_plot(parameters)

    assert result is False
    mock_warning.assert_called_once()


def test_overlay_plot_skips_already_plotted_datasets(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify already plotted datasets are skipped and the no-op is reported."""
    view.figure.axes = []
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_units = ["ms"]
    view.plotted_datasets.add(("test_loader", None, None, "", "Full Dataset"))
    view._reset_actions = mocker.Mock()  # prevent decorator side effects

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.update_plot = mocker.Mock()

    result = view._overlay_plot(parameters)

    # Every requested dataset was skipped as already plotted, so nothing
    # reached the axes. _overlay_plot reports that as False so the caller can
    # roll back the recorded action, rather than leaving an Undo step that
    # would restore an identical figure.
    assert result is False
    view.update_plot.assert_not_called()


def test_overlay_plot_returns_false_when_query_empty(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns False when query is empty string."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_query = ""

    result = view._overlay_plot(parameters)

    assert result is False


def test_overlay_plot_skips_subset_when_no_plot_data(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify skips subset and emits message when plot_data is None."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = None

    view._overlay_plot(parameters)

    view.add_text_to_display.emit.assert_called()
    call_args = view.add_text_to_display.emit.call_args_list[-1]
    assert "No data matching" in call_args.args[0]


def test_overlay_plot_emits_row_count_message(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify emits message with row count for valid data."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0, 4.0, 5.0]})
    view.canned_plot_data = plot_data
    view.canned_query = "SELECT * FROM events"
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    view.add_text_to_display.emit.assert_called()
    call_args = view.add_text_to_display.emit.call_args_list[0]
    assert "5 rows" in call_args.args[0]


def test_overlay_plot_returns_false_when_columns_missing_from_dataframe(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns False when columns not present in dataframe."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "missing_column",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_query = "SELECT * FROM events"
    view.canned_plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_units = "ms"

    result = view._overlay_plot(parameters)

    assert result is False
    view.add_text_to_display.emit.assert_called()


def test_overlay_plot_calls_update_plot_with_correct_arguments(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify update_plot is called with correct arguments."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Normalized Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Filter1": "WHERE x > 1"})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [2]}}
    plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_plot_data = plot_data
    view.canned_query = "SELECT * FROM events"
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    view.update_plot.assert_called_once()
    call_args = view.update_plot.call_args
    assert call_args is not None
    assert call_args.args[0] == "Normalized Histogram"
    assert isinstance(call_args.args[1], pd.DataFrame)
    assert call_args.args[2] == ["duration"]
    assert call_args.args[3] == ["ms"]
    assert call_args.kwargs["bins"] == [50]
    assert call_args.kwargs["sizes"] is False


def test_overlay_plot_updates_allowed_properties_after_successful_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify allowed properties are updated after successful plot."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": True,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_plot_data = plot_data
    view.canned_query = "SELECT * FROM events"
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    assert view.allowed_plot_type == "Histogram"
    assert view.allowed_columns == ["duration"]
    assert view.allowed_logs == [True]
    assert view.allowed_bins == [50]
    assert view.allowed_sizes is False


def test_overlay_plot_adds_dataset_to_plotted_datasets(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify dataset is added to plotted_datasets set."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Filter1": "WHERE x > 1"})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [2]}}
    plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_plot_data = plot_data
    view.canned_query = "SELECT * FROM events"
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    view._overlay_plot(parameters)

    assert ("test_loader", "exp1", 2, "WHERE x > 1", "Filter1") in view.plotted_datasets


def test_overlay_plot_asks_for_a_raw_all_points_histogram(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify the Raw All Points Histogram branch asks for the tally it draws."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw All Points Histogram",
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_event_query = "SELECT * FROM events"

    assert view._overlay_plot(parameters) is True

    view.all_points_histogram_requested.emit.assert_called_once()
    args = view.all_points_histogram_requested.emit.call_args[0]
    assert args[0] == "test_loader"
    assert args[3] == "Raw All Points Histogram"
    assert args[4] == [50]
    assert args[5] is False
    view.event_overlay_requested.emit.assert_not_called()


def test_overlay_plot_asks_for_a_filtered_all_points_histogram(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify the plot type reaches the Controller, since it picks the trace."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Filtered All Points Histogram",
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_event_query = "SELECT * FROM events"

    view._overlay_plot(parameters)

    args = view.all_points_histogram_requested.emit.call_args[0]
    assert args[3] == "Filtered All Points Histogram"


def test_overlay_plot_resets_for_all_points_histogram_when_bins_change(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot resets when bins change for All Points Histogram."""
    view.allowed_bins = [30]
    view.allowed_sizes = False
    view._reset_actions = mocker.Mock()

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw All Points Histogram",
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_event_query = "SELECT * FROM events"

    view._overlay_plot(parameters)

    view._reset_actions.assert_called_once()


def test_overlay_plot_sends_the_limits_left_by_the_reset(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    Verify the shared limits are read *after* the reset that clears them.

    The limits decide the bins the whole overlay is drawn on, so sending the ones
    the previous plot type left behind would bin this one against data no longer on
    the axes. Reading them before the reset is what that mistake looks like, and it
    is invisible unless the reset is the thing that changes them.
    """
    view.allowed_bins = [30]
    view.allowed_sizes = False
    view.hist_min = -99.0
    view.hist_max = 99.0

    def _clear(axis_type: str = "2d") -> None:
        view.hist_min = None
        view.hist_max = None

    view._reset_actions = mocker.Mock(side_effect=_clear)

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw All Points Histogram",
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_event_query = "SELECT * FROM events"

    view._overlay_plot(parameters)

    args = view.all_points_histogram_requested.emit.call_args[0]
    assert args[6] is None
    assert args[7] is None


def test_overlay_plot_asks_for_a_raw_event_overlay(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Raw Event Overlay asks for the traces it draws."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw Event Overlay",
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_event_query = "SELECT * FROM events"

    view._overlay_plot(parameters)

    view.event_overlay_requested.emit.assert_called_once_with(
        "test_loader", "", {None: [None]}, "Raw Event Overlay"
    )
    view.all_points_histogram_requested.emit.assert_not_called()


def test_overlay_plot_returns_false_when_event_query_empty(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns False when event_query is empty string."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw Event Overlay",
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_event_query = ""

    result = view._overlay_plot(parameters)

    assert result is False


def test_overlay_plot_returns_false_when_the_histogram_could_not_be_built(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    Verify a failed all-points tally rolls the action back.

    The Controller sets the query only once the tally succeeded, so the same empty
    query that reports a failed fetch reports a failed reduction - which used to be
    an exception escaping a Qt slot.
    """
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw All Points Histogram",
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_event_query = ""

    assert view._overlay_plot(parameters) is False


def test_overlay_plot_clears_allowed_columns_for_event_plots(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify allowed_columns and allowed_logs are cleared for event plots."""
    view.allowed_columns = ["duration"]
    view.allowed_logs = [False]

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw Event Overlay",
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_event_query = "SELECT * FROM events"

    view._overlay_plot(parameters)

    assert view.allowed_columns == []
    assert view.allowed_logs == []


def test_overlay_plot_returns_true_on_success(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns True on successful plot."""
    view.figure.axes = []

    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Histogram",
        "x_axis": "duration",
        "x_log": False,
        "bins": [50],
        "sizes": False,
    }

    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.canned_plot_data = plot_data
    view.canned_query = "SELECT * FROM events"
    view.canned_units = "ms"
    view.update_plot = mocker.Mock()

    result = view._overlay_plot(parameters)

    assert result is True


# ----------------------------- set_all_points_histogram Tests ------------------------------
#
# The tally itself moved to MetadataModel.build_all_points_histogram in Step 4's
# closeout and is pinned in tests/unit/models/test_metadata_model.py. What is left
# here is the drawing half, and the shared limits the answer carries back.


def test_set_all_points_histogram_takes_the_widened_limits(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify the limits the tally widened come back onto the view."""
    view.hist_min = None
    view.hist_max = None
    view._plot_all_points_histogram = mocker.Mock()

    view.set_all_points_histogram(
        np.array([1.0, 2.0]),
        np.array([10.0, 20.0]),
        -3.0,
        7.0,
        "Raw All Points Histogram",
        "a label",
    )

    assert view.hist_min == -3.0
    assert view.hist_max == 7.0


def test_set_all_points_histogram_draws_the_counts(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify the bin centers and counts reach the drawing method unchanged."""
    view._plot_all_points_histogram = mocker.Mock()
    x = np.array([1.0, 2.0])
    y = np.array([10.0, 20.0])

    view.set_all_points_histogram(x, y, 0.0, 3.0, "Raw All Points Histogram", "a label")

    view._plot_all_points_histogram.assert_called_once()
    args, kwargs = view._plot_all_points_histogram.call_args
    assert args[1] is x
    assert args[2] is y
    assert kwargs["dataset_label"] == "a label"
    assert kwargs["norm"] is False


@pytest.mark.parametrize(
    "plot_type",
    [
        "Normalized Raw All Points Histogram",
        "Normalized Filtered All Points Histogram",
    ],
)
def test_set_all_points_histogram_normalizes_for_a_normalized_type(
    view: MetadataView, mocker: MockerFixture, plot_type: str
) -> None:
    """Verify the two normalized variants ask the drawing method to normalize."""
    view._plot_all_points_histogram = mocker.Mock()

    view.set_all_points_histogram(
        np.array([1.0, 2.0]),
        np.array([10.0, 20.0]),
        0.0,
        3.0,
        plot_type,
        "a label",
    )

    assert view._plot_all_points_histogram.call_args[1]["norm"] is True


def test_set_all_points_histogram_redraws_the_canvas(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify the canvas is redrawn and the cache committed."""
    view._plot_all_points_histogram = mocker.Mock()

    view.set_all_points_histogram(
        np.array([1.0, 2.0]),
        np.array([10.0, 20.0]),
        0.0,
        3.0,
        "Raw All Points Histogram",
        "a label",
    )

    view.canvas.draw.assert_called()
    view._commit_cache.assert_called()


# ----------------------------- set_event_overlay Tests ------------------------------
#
# The baseline subtraction and the normalised time base moved to
# MetadataModel.build_event_overlay; the alpha stays here, because it is read by
# nothing outside these axes.


_TWO_TRACES = [
    (np.linspace(-0.2, 1.2, 30), np.linspace(0.0, 30.0, 30)),
    (np.linspace(-0.2, 1.2, 40), np.linspace(0.0, 30.0, 40)),
]


def test_set_event_overlay_sets_axis_labels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axis labels are set correctly."""
    view.set_event_overlay(_TWO_TRACES)

    view.axes.set_xlabel.assert_called_with("Normalized Time")
    view.axes.set_ylabel.assert_called_with("Rectified Current (pA)")


def test_set_event_overlay_sets_xlim(view: MetadataView, mocker: MockerFixture) -> None:
    """Verify x-axis limits are set correctly."""
    view.set_event_overlay(_TWO_TRACES)

    view.axes.set_xlim.assert_called_with(left=-0.333, right=1.333)


def test_set_event_overlay_draws_one_trace_per_event(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify every trace handed back is drawn."""
    view.set_event_overlay(_TWO_TRACES)

    assert view.axes.plot.call_count == 2


def test_set_event_overlay_draws_a_shorter_event_more_opaquely(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    Verify the alpha falls with duration, and is capped.

    Short events are the ones that would otherwise be lost under a crowd of long
    ones, so they are drawn more opaquely; the cap keeps a small overlay readable.
    """
    view.set_event_overlay(_TWO_TRACES)

    alphas = [call.kwargs["alpha"] for call in view.axes.plot.call_args_list]
    assert alphas[0] > alphas[1]
    assert all(alpha <= 0.5 for alpha in alphas)


def test_set_event_overlay_uses_one_alpha_when_every_event_is_the_same_length(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify equal durations do not divide by a zero spread."""
    traces = [
        (np.linspace(-0.2, 1.2, 30), np.linspace(0.0, 30.0, 30)),
        (np.linspace(-0.2, 1.2, 30), np.linspace(5.0, 35.0, 30)),
    ]

    view.set_event_overlay(traces)

    alphas = [call.kwargs["alpha"] for call in view.axes.plot.call_args_list]
    assert alphas == [0.5, 0.5]


def test_set_event_overlay_draws_nothing_for_an_empty_subset(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify no event divides by a zero count."""
    view.set_event_overlay([])

    view.axes.plot.assert_not_called()


def test_set_event_overlay_sets_no_cached_data_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify no_cached_data flag is set to True."""
    view.set_event_overlay(_TWO_TRACES)

    assert view.no_cached_data is True


def test_set_event_overlay_redraws_canvas(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify canvas is redrawn after plotting."""
    view.set_event_overlay(_TWO_TRACES)

    view.canvas.draw.assert_called()


# ----------------------------- Set Event Data Generator Tests ------------------------------


def test_set_event_data_generator_sets_value(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify event_data_generator is set correctly."""
    generator = iter([{"data": "test"}])

    view.set_event_data_generator(generator)

    assert view.event_data_generator == generator


# ----------------------------- Undo Plot Tests ------------------------------


def test_undo_plot_emits_update_tab_action_history(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify update_tab_action_history is emitted with undo flag."""
    view._undo_plot()

    view.update_tab_action_history.emit.assert_called_with(None, True)


# ----------------------------- Save Filter Tests ------------------------------


def test_save_filter_returns_early_when_no_filters(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns early when subset_filters is empty."""
    view.subset_filters = {}
    mock_file_dialog = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getSaveFileName"
    )

    view._save_filter()

    mock_file_dialog.assert_not_called()


def test_save_filter_opens_file_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify file dialog is opened."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mock_file_dialog = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getSaveFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )

    view._save_filter()

    mock_file_dialog.assert_called_once()


def test_save_filter_returns_when_no_path_selected(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify nothing is asked for when the user cancels the dialog."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getSaveFileName",
        return_value=("", ""),
    )

    view._save_filter()

    view.filters_save_requested.emit.assert_not_called()


def test_save_filter_asks_for_the_path_and_the_filters(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    Choosing the file is the widget's; writing it is not.

    The filters are copied into the request rather than read back off the widget
    later, so what is written is what was on screen when the user chose the path.
    """
    view.subset_filters = {"Filter1": "WHERE x > 1", "Filter2": "WHERE y < 10"}
    mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getSaveFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )

    view._save_filter()

    path, filters = view.filters_save_requested.emit.call_args.args
    assert path == "/path/to/filters.json"
    assert filters == {"Filter1": "WHERE x > 1", "Filter2": "WHERE y < 10"}
    assert filters is not view.subset_filters


def test_save_filter_asks_for_nothing_when_there_is_nothing_to_save(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """No filters means no dialog, not an empty file."""
    view.subset_filters = {}
    dialog = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getSaveFileName"
    )

    view._save_filter()

    dialog.assert_not_called()
    view.filters_save_requested.emit.assert_not_called()


def test_load_filter_opens_file_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify file dialog is opened."""
    mock_file_dialog = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )

    view._load_filter({"db_loader": "test_loader"})

    mock_file_dialog.assert_called_once()


def test_load_filter_returns_when_no_path_selected(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify nothing is asked for when the user cancels the dialog."""
    mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName",
        return_value=("", ""),
    )

    view._load_filter({"db_loader": "test_loader"})

    view.filters_load_requested.emit.assert_not_called()


def test_load_filter_asks_for_the_path_and_the_loader(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """The loader travels with the request, because the answer is validated against it."""
    mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )

    view._load_filter({"db_loader": "test_loader"})

    assert view.filters_load_requested.emit.call_args.args == (
        "/path/to/filters.json",
        "test_loader",
    )


def test_load_filter_carries_an_empty_loader_when_none_is_chosen(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    A missing loader is not a failure - the filters load unvalidated - so it has to
    survive the round trip as something the answering half can test.
    """
    mocker.patch(
        "poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )

    view._load_filter({})

    assert view.filters_load_requested.emit.call_args.args[1] == ""


def test_set_loaded_filters_warns_on_duplicate_names(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """All or nothing: a partial load leaves the user guessing which half arrived."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}

    view.set_loaded_filters({"Filter1": "WHERE y < 10"}, "test_loader")

    said = [call.args[0] for call in view.add_text_to_display.emit.call_args_list]
    assert any("Duplicate filter names" in message for message in said)
    assert view.subset_filters == {"Filter1": "WHERE x > 1"}


def test_set_loaded_filters_validates_with_loader_when_provided(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filters are validated when a loader is available."""
    view.subset_filters = {}

    view.set_loaded_filters({"Filter1": "WHERE x > 1"}, "test_loader")

    view.filter_validation_requested.emit.assert_called_once()


def test_set_loaded_filters_adds_filter_directly_when_no_loader(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filters are added directly when no loader is available."""
    view.subset_filters = {}

    view.set_loaded_filters({"Filter1": "WHERE x > 1"}, "")

    assert view.subset_filters == {"Filter1": "WHERE x > 1"}
    view.filter_validation_requested.emit.assert_not_called()


# ------------------------ Restore Subset Filters (Session Load) Tests --------------------


def test_restore_subset_filters_adds_filters_directly(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify restored filters are added to subset_filters and the combo box without validation."""
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox = mocker.Mock()

    view.restore_subset_filters({"Filter1": "WHERE x > 1"})

    assert view.subset_filters == {"Filter1": "WHERE x > 1"}
    view.metadatacontrols.filter_comboBox.addItem.assert_called_once_with("Filter1")
    view.metadatacontrols.filter_comboBox.selectItem.assert_called_once_with(
        "Filter1", select=True
    )


def test_restore_subset_filters_skips_existing_names(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify a restored filter whose name already exists is skipped rather than overwritten."""
    view.subset_filters = {"Filter1": "WHERE x > 999"}
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox = mocker.Mock()

    view.restore_subset_filters({"Filter1": "WHERE x > 1"})

    assert view.subset_filters == {"Filter1": "WHERE x > 999"}
    view.metadatacontrols.filter_comboBox.addItem.assert_not_called()


# ----------------------------- Handle Parameter Change Tests ------------------------------


def test_handle_parameter_change_exports_plot_data_when_cached(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify export_plot_data signal is emitted when data is cached."""
    view.no_cached_data = False
    view.export_plot_data = mocker.Mock()

    view.handle_parameter_change("metadata", "export_plot_data", ({},))

    view.export_plot_data.emit.assert_called_once()


def test_handle_parameter_change_warns_when_no_cached_data(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning is emitted when event overlay data is not cached."""
    view.no_cached_data = True
    view.export_plot_data = mocker.Mock()

    view.handle_parameter_change("metadata", "export_plot_data", ({},))

    view.add_text_to_display.emit.assert_called()
    view.export_plot_data.emit.assert_not_called()


def test_handle_parameter_change_updates_columns_on_loader_changed(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify available columns are updated when loader changes."""
    view.update_available_columns = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"db_loader": "test_loader"}

    view.handle_parameter_change("metadata", "loader_changed", (parameters,))

    view.update_available_columns.assert_called_once_with("test_loader")


def test_handle_parameter_change_shows_selection_tree(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify selection tree is shown for experiment/channel selection."""
    view.available_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1, 2]}}  # type: ignore[assignment]
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}  # type: ignore[assignment]
    view.show_selection_tree = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"db_loader": "test_loader"}

    view.handle_parameter_change(
        "metadata", "select_experiment_and_channel", (parameters,)
    )

    view.show_selection_tree.assert_called_once()


def test_handle_parameter_change_shifts_range_backward(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify range is shifted backward."""
    view._shift_range_and_update_plot = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"event_index": [1, 2, 3]}

    view.handle_parameter_change("metadata", "shift_range_backward", (parameters,))

    view._shift_range_and_update_plot.assert_called_once_with(
        parameters, direction="left"
    )


def test_handle_parameter_change_shifts_range_forward(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify range is shifted forward."""
    view._shift_range_and_update_plot = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"event_index": [1, 2, 3]}

    view.handle_parameter_change("metadata", "shift_range_forward", (parameters,))

    view._shift_range_and_update_plot.assert_called_once_with(
        parameters, direction="right"
    )


def test_handle_parameter_change_handles_plot_events(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot events are handled."""
    view._handle_plot_events = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"event_index": [1, 2, 3]}

    view.handle_parameter_change("metadata", "plot_events", (parameters,))

    view._handle_plot_events.assert_called_once_with(parameters)


def test_handle_parameter_change_updates_units_on_columns_updated(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify units are updated when columns change."""
    view.update_units = mocker.Mock()  # type: ignore[method-assign]
    parameters = {
        "db_loader": "test_loader",
        "x_axis": "duration",
        "y_axis": "current",
        "z_axis": "voltage",
    }

    view.handle_parameter_change("metadata", "columns_updated", (parameters,))

    assert view.update_units.call_count == 3


def test_handle_parameter_change_raises_for_new_axis(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify NotImplementedError is raised for new_axis action."""
    parameters = {}

    with pytest.raises(NotImplementedError, match="No new axis for you"):
        view.handle_parameter_change("metadata", "new_axis", (parameters,))


def test_handle_parameter_change_calls_overlay_plot_on_update(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _overlay_plot is called on update_plot action."""
    view._overlay_plot = mocker.Mock(return_value=True)  # type: ignore[method-assign]
    parameters = {"plot_type": "Histogram"}

    view.handle_parameter_change("metadata", "update_plot", (parameters,))

    view._overlay_plot.assert_called_once_with(parameters)


def test_handle_parameter_change_undoes_on_failed_overlay(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify update_tab_action_history is emitted when overlay fails."""
    view._overlay_plot = mocker.Mock(return_value=False)  # type: ignore[method-assign]
    parameters = {"plot_type": "Histogram"}

    view.handle_parameter_change("metadata", "update_plot", (parameters,))

    view.update_tab_action_history.emit.assert_called_with(None, True)


def test_handle_parameter_change_resets_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot is reset on reset_plot action."""
    view._reset_actions = mocker.Mock()  # type: ignore[method-assign]

    view.handle_parameter_change("metadata", "reset_plot", ({},))

    view._reset_actions.assert_called_once()


def test_handle_parameter_change_loads_plot_config(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot configuration is loaded."""
    view._load_actions_from_json = mocker.Mock(return_value={"action": "data"})  # type: ignore[method-assign]
    view._update_actions_from_json = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"db_loader": "test_loader"}

    view.handle_parameter_change("metadata", "load_plot", (parameters,))

    view._load_actions_from_json.assert_called_once()
    view._update_actions_from_json.assert_called_once()


def test_handle_parameter_change_returns_early_when_no_actions(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify early return when no actions are loaded."""
    view._load_actions_from_json = mocker.Mock(return_value=None)  # type: ignore[method-assign]
    view._update_actions_from_json = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"db_loader": "test_loader"}

    view.handle_parameter_change("metadata", "load_plot", (parameters,))

    view._update_actions_from_json.assert_not_called()


def test_handle_parameter_change_saves_plot_config(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot configuration is saved."""
    view._save_actions_to_json = mocker.Mock()  # type: ignore[method-assign]

    view.handle_parameter_change("metadata", "save_plot_config", ({},))

    view._save_actions_to_json.assert_called_once()


def test_handle_parameter_change_undoes_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot is undone on undo_plot action."""
    view._undo_plot = mocker.Mock()  # type: ignore[method-assign]

    view.handle_parameter_change("metadata", "undo_plot", ({},))

    view._undo_plot.assert_called_once()


def test_handle_parameter_change_shows_add_filter_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify add filter dialog is shown."""
    view._show_add_filter_dialog = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"db_loader": "test_loader"}

    view.handle_parameter_change("metadata", "add_filter", (parameters,))

    view._show_add_filter_dialog.assert_called_once_with(parameters)


def test_handle_parameter_change_shows_edit_filter_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify edit filter dialog is shown."""
    view._show_filter_info_dialog = mocker.Mock()  # type: ignore[method-assign]
    view.metadatacontrols = mocker.Mock()
    parameters = {"db_loader": "test_loader"}

    view.handle_parameter_change("metadata", "edit_filter", (parameters,))

    view._show_filter_info_dialog.assert_called_once()


def test_handle_parameter_change_deletes_filter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify selected filters are deleted."""
    view._delete_all_selected_filters = mocker.Mock()  # type: ignore[method-assign]

    view.handle_parameter_change("metadata", "delete_filter", ({},))

    view._delete_all_selected_filters.assert_called_once()


def test_handle_parameter_change_saves_filter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filter is saved."""
    view._save_filter = mocker.Mock()  # type: ignore[method-assign]

    view.handle_parameter_change("metadata", "save_filter", ({},))

    view._save_filter.assert_called_once()


def test_handle_parameter_change_loads_filter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filter is loaded."""
    view._load_filter = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"db_loader": "test_loader"}

    view.handle_parameter_change("metadata", "load_filter", (parameters,))

    view._load_filter.assert_called_once_with(parameters)


def test_handle_parameter_change_exports_csv_subset(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify CSV subset is exported."""
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}  # type: ignore[assignment]
    view.get_selected_filters = mocker.Mock(return_value={"Filter1": "WHERE x > 1"})
    view._export_csv_subset = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"db_loader": "test_loader"}

    view.handle_parameter_change("metadata", "export_csv_subset", (parameters,))

    view._export_csv_subset.assert_called_once()


def test_handle_parameter_change_calls_handle_other_actions_for_unknown(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _handle_other_actions is called for unknown actions."""
    view._handle_other_actions = mocker.Mock()  # type: ignore[method-assign]
    parameters = {"key": "value"}

    view.handle_parameter_change("metadata", "unknown_action", (parameters,))

    view._handle_other_actions.assert_called_once_with("unknown_action", parameters)


# ----------------------------- Handle Plot Events Tests ------------------------------


def test_handle_plot_events_warns_when_no_experiments_selected(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning when no experiments or channels are selected."""
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}  # type: ignore[assignment]
    parameters = {"db_loader": "test_loader", "event_index": [1, 2, 3]}

    view._handle_plot_events(parameters)

    view.add_text_to_display.emit.assert_called()
    assert "No experiments or channels" in view.add_text_to_display.emit.call_args[0][0]


def test_handle_plot_events_warns_when_multiple_filters_selected(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning when multiple filters are selected."""
    view.get_selected_filters = mocker.Mock(
        return_value={"Filter1": "WHERE x > 1", "Filter2": "WHERE y < 10"}
    )
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    parameters = {"db_loader": "test_loader", "event_index": [1, 2, 3]}

    view._handle_plot_events(parameters)

    view.add_text_to_display.emit.assert_called()


def test_handle_plot_events_warns_when_loader_has_empty_selection(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning when loader has empty experiment/channel selection."""
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {}}  # type: ignore[assignment]
    parameters = {"db_loader": "test_loader", "event_index": [1, 2, 3]}

    view._handle_plot_events(parameters)

    view.add_text_to_display.emit.assert_called()
    assert "No experiments or channels" in view.add_text_to_display.emit.call_args[0][0]


def test_handle_plot_events_warns_when_multiple_experiments(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning when multiple experiments are selected."""
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {  # type: ignore[assignment]
        "test_loader": {"exp1": [1], "exp2": [2]}
    }
    parameters = {"db_loader": "test_loader", "event_index": [1, 2, 3]}

    view._handle_plot_events(parameters)

    view.add_text_to_display.emit.assert_called()
    assert "single experiment" in view.add_text_to_display.emit.call_args[0][0]


def test_handle_plot_events_warns_when_multiple_channels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning when multiple channels are selected."""
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1, 2]}}  # type: ignore[assignment]
    parameters = {"db_loader": "test_loader", "event_index": [1, 2, 3]}

    view._handle_plot_events(parameters)

    view.add_text_to_display.emit.assert_called()
    assert "single channel" in view.add_text_to_display.emit.call_args[0][0]


_FULL_EVENT = {
    "event_id": 1,
    "experiment_id": 1,
    "channel_id": 1,
    "raw_data": np.array([1.0, 2.0, 3.0]),
    "filtered_data": np.array([1.1, 2.1, 3.1]),
    "fit_data": np.array([1.0, 2.0, 3.0]),
    "samplerate": 10000,
}


# ----------------------------- Update Event Plot Tests ------------------------------


def _make_event(event_id: int = 1, n_samples: int = 2) -> dict:
    """Return a minimal valid event dict."""
    return {
        "experiment_id": 1,
        "channel_id": 1,
        "event_id": event_id,
        "raw_data": np.ones(n_samples) * 1000.0,
        "filtered_data": np.ones(n_samples) * 1100.0,
        "fit_data": np.ones(n_samples) * 1000.0,
        "samplerate": 10000,
    }


def _none_lists(n: int):
    """Return the six None-filled lists required alongside event_data."""
    return (
        [None] * n,  # horizontal_lines
        [None] * n,  # vertical_lines
        [None] * n,  # points
        [None] * n,  # horizontal_labels
        [None] * n,  # vertical_labels
        [None] * n,  # point_labels
    )


def test_update_event_plot_clears_figure(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify figure is cleared before plotting events."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._clear_figure_state = mocker.Mock()
    view._factors = mocker.Mock(return_value=(1, 1))
    event_data = [_make_event()]

    view._update_event_plot(event_data, *_none_lists(1))

    view._clear_figure_state.assert_called()


def test_update_event_plot_creates_subplots(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify subplots are created for each event."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._clear_figure_state = mocker.Mock()  # <-- add this
    view._factors = mocker.Mock(return_value=(2, 2))
    event_data = [_make_event(i) for i in range(4)]

    view._update_event_plot(event_data, *_none_lists(4))

    assert view.figure.add_subplot.call_count == 4


def test_update_event_plot_plots_all_traces(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify raw (use_raw=True), filtered, and fit traces are plotted."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._clear_figure_state = mocker.Mock()  # add
    view._factors = mocker.Mock(return_value=(1, 1))
    mock_ax = mocker.Mock()
    view.figure.add_subplot = mocker.Mock(return_value=mock_ax)
    event_data = [_make_event()]

    view._update_event_plot(event_data, *_none_lists(1), use_raw=True)

    assert mock_ax.plot.call_count == 3


def test_update_event_plot_sets_subplot_titles(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify subplot titles contain exp/channel/event info."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._clear_figure_state = mocker.Mock()  # add
    view._factors = mocker.Mock(return_value=(1, 1))
    mock_ax = mocker.Mock()
    view.figure.add_subplot = mocker.Mock(return_value=mock_ax)
    event_data = [
        {
            "experiment_id": 5,
            "channel_id": 3,
            "event_id": 42,
            "raw_data": np.array([1.0, 2.0]),
            "filtered_data": np.array([1.1, 2.1]),
            "fit_data": np.array([1.0, 2.0]),
            "samplerate": 10000,
        }
    ]

    view._update_event_plot(event_data, *_none_lists(1))

    mock_ax.set_title.assert_called_once()
    title = mock_ax.set_title.call_args[0][0]
    assert "Exp 5" in title
    assert "Ch 3" in title
    assert "Event 42" in title


def test_update_event_plot_converts_current_to_nanoamps(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify current data is divided by 1000 (pA to nA)."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._clear_figure_state = mocker.Mock()  # add
    view._factors = mocker.Mock(return_value=(1, 1))
    mock_ax = mocker.Mock()
    view.figure.add_subplot = mocker.Mock(return_value=mock_ax)
    event_data = [
        {
            "experiment_id": 1,
            "channel_id": 1,
            "event_id": 1,
            "raw_data": np.array([1000.0, 2000.0]),
            "filtered_data": np.array([1100.0, 2100.0]),
            "fit_data": np.array([1000.0, 2000.0]),
            "samplerate": 10000,
        }
    ]

    view._update_event_plot(event_data, *_none_lists(1), use_raw=False)

    calls = mock_ax.plot.call_args_list
    np.testing.assert_array_almost_equal(calls[0][0][1], np.array([1.1, 2.1]))


def test_update_event_plot_converts_time_to_microseconds(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify time axis is in microseconds."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._clear_figure_state = mocker.Mock()  # add
    view._factors = mocker.Mock(return_value=(1, 1))
    mock_ax = mocker.Mock()
    view.figure.add_subplot = mocker.Mock(return_value=mock_ax)
    event_data = [_make_event(n_samples=2)]

    view._update_event_plot(event_data, *_none_lists(1), use_raw=True)

    calls = mock_ax.plot.call_args_list
    np.testing.assert_array_almost_equal(calls[0][0][0], np.array([0.0, 100.0]))


def test_update_event_plot_updates_cache(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _update_cache is called for each plotted trace."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._clear_figure_state = mocker.Mock()  # add
    view._factors = mocker.Mock(return_value=(1, 1))
    event_data = [_make_event()]

    view._update_event_plot(event_data, *_none_lists(1), use_raw=False)

    assert view._update_cache.call_count == 2


def test_update_event_plot_sets_ylabel_on_leftmost_subplots(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify y-axis labels are set only on leftmost subplots."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._clear_figure_state = mocker.Mock()  # add
    view._factors = mocker.Mock(return_value=(2, 3))
    mock_axes: list = []

    def create_mock_ax(*args: Any) -> Any:
        ax = mocker.Mock()
        mock_axes.append(ax)
        return ax

    view.figure.add_subplot = mocker.Mock(side_effect=create_mock_ax)
    event_data = [_make_event(i) for i in range(6)]

    view._update_event_plot(event_data, *_none_lists(6))

    assert mock_axes[0].set_ylabel.called
    assert not mock_axes[1].set_ylabel.called
    assert not mock_axes[2].set_ylabel.called
    assert mock_axes[3].set_ylabel.called
    assert not mock_axes[4].set_ylabel.called
    assert not mock_axes[5].set_ylabel.called


def test_update_event_plot_sets_xlabel_on_bottom_subplots(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify x-axis labels are set only on bottom row subplots."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._clear_figure_state = mocker.Mock()  # add
    view._factors = mocker.Mock(return_value=(2, 3))
    mock_axes: list = []

    def create_mock_ax(*args: Any) -> Any:
        ax = mocker.Mock()
        mock_axes.append(ax)
        return ax

    view.figure.add_subplot = mocker.Mock(side_effect=create_mock_ax)
    event_data = [_make_event(i) for i in range(6)]

    view._update_event_plot(event_data, *_none_lists(6))

    assert not mock_axes[0].set_xlabel.called
    assert not mock_axes[1].set_xlabel.called
    assert not mock_axes[2].set_xlabel.called
    assert mock_axes[3].set_xlabel.called
    assert mock_axes[4].set_xlabel.called
    assert mock_axes[5].set_xlabel.called


def test_update_event_plot_redraws_canvas(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify canvas.draw() is called after plotting."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._reset_actions = mocker.Mock()  # prevents first canvas.draw()
    view._clear_figure_state = mocker.Mock()  # prevents second figure manipulation
    view._factors = mocker.Mock(return_value=(1, 1))
    event_data = [_make_event()]

    view._update_event_plot(event_data, *_none_lists(1))

    view.canvas.draw.assert_called_once()


def test_update_event_plot_commits_cache(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _commit_cache() is called after plotting."""
    view.figure.axes = []
    view.figure.get_axes = mocker.Mock(return_value=[])
    view.figure.get_size_inches = mocker.Mock(return_value=(8.0, 6.0))
    view._clear_figure_state = mocker.Mock()  # add
    view._factors = mocker.Mock(return_value=(1, 1))
    event_data = [_make_event()]

    view._update_event_plot(event_data, *_none_lists(1))

    view._commit_cache.assert_called_once()


# ----------------------------- Export CSV Subset Tests ------------------------------


def test_export_csv_subset_warns_when_multiple_filters(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning when multiple filters are selected."""
    view.available_plugins = {}  # type: ignore[attr-defined]
    filters = {"Filter1": "WHERE x > 1", "Filter2": "WHERE y < 10"}

    view._export_csv_subset("test_loader", filters, {})

    view.add_text_to_display.emit.assert_called()
    assert "single filter" in view.add_text_to_display.emit.call_args[0][0]


def test_export_csv_subset_opens_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify dialog is opened for export settings."""
    view.available_plugins = {}  # type: ignore[attr-defined]
    view.subset_export_count = 0
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.DictDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.get_result.return_value = ({}, None)
    mock_dialog_class.return_value = mock_dialog

    view._export_csv_subset("test_loader", {"Filter1": "WHERE x > 1"}, {})

    mock_dialog_class.assert_called_once()
    mock_dialog.exec.assert_called_once()


def test_export_csv_subset_converts_empty_filters_to_none(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify empty filter dict is converted to None."""
    view.available_plugins = {}  # type: ignore[attr-defined]
    view.subset_export_count = 0
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.DictDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.get_result.return_value = (
        {"Folder": {"Value": "/path/to/folder"}},
        "export_name",
    )
    mock_dialog_class.return_value = mock_dialog

    view._export_csv_subset("test_loader", {}, {"exp1": [1]})

    assert view.csv_subset_export_requested.emit.call_args[0][3] is None


def test_export_csv_subset_extracts_filter_value(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filter value is extracted from dict."""
    view.available_plugins = {}  # type: ignore[attr-defined]
    view.subset_export_count = 0
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.DictDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.get_result.return_value = (
        {"Folder": {"Value": "/path/to/folder"}},
        "export_name",
    )
    mock_dialog_class.return_value = mock_dialog

    view._export_csv_subset("test_loader", {"Filter1": "WHERE x > 1"}, {})

    assert view.csv_subset_export_requested.emit.call_args[0][3] == "WHERE x > 1"


def test_export_csv_subset_emits_signal_on_success(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify the export intent carries the whole request, and starts no worker here.

    ``run_generators`` was emitted from this method before Step 4a. Staging the
    generator and starting it are the Controller's now, which is the only place that
    knows whether the export was set up at all.
    """
    view.available_plugins = {}  # type: ignore[attr-defined]
    view.subset_export_count = 0
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.DictDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.get_result.return_value = (
        {"Folder": {"Value": "/path/to/folder"}},
        "export_name",
    )
    mock_dialog_class.return_value = mock_dialog
    view.run_generators = mocker.Mock()

    view._export_csv_subset("test_loader", {"Filter1": "WHERE x > 1"}, {"exp1": [1]})

    view.csv_subset_export_requested.emit.assert_called_once_with(
        "test_loader",
        "/path/to/folder",
        "export_name",
        "WHERE x > 1",
        {"exp1": [1]},
        0,
    )
    view.run_generators.emit.assert_not_called()


def test_export_csv_subset_does_not_advance_the_index_by_itself(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify the index advances on the Controller's word, not on the request.

    Was ``..._increments_counter``, which held when this method staged the export
    itself. It advances in ``on_subset_export_started`` now, so an export the loader
    refused does not consume a name.
    """
    view.available_plugins = {}  # type: ignore[attr-defined]
    initial_count = view.subset_export_count
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.DictDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.get_result.return_value = (
        {"Folder": {"Value": "/path/to/folder"}},
        "export_name",
    )
    mock_dialog_class.return_value = mock_dialog

    view._export_csv_subset("test_loader", {"Filter1": "WHERE x > 1"}, {})

    assert view.subset_export_count == initial_count

    view.on_subset_export_started()

    assert view.subset_export_count == initial_count + 1


def test_export_csv_subset_does_not_increment_counter_on_cancel(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify counter is not incremented when dialog is cancelled."""
    view.available_plugins = {}  # type: ignore[attr-defined]
    initial_count = view.subset_export_count
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.DictDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.get_result.return_value = (None, None)  # User cancelled
    mock_dialog_class.return_value = mock_dialog

    view._export_csv_subset("test_loader", {"Filter1": "WHERE x > 1"}, {})

    assert view.subset_export_count == initial_count

    # ----------------------------- Set Exported Event Count Tests ------------------------------


# ----------------------------- Set Query Tests ------------------------------


def test_set_query_sets_query_and_table_name(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify query and table name are set correctly."""
    view.set_query("SELECT * FROM events", "events")

    assert view.query == "SELECT * FROM events"
    assert view.table_name == "events"


def test_set_query_does_not_echo_to_the_status_panel(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """The validation query is not the one that pulls the subset, so it is not shown."""
    view.set_query("SELECT * FROM events", "events")

    view.add_text_to_display.emit.assert_not_called()


# ----------------------------- Set Event Query Tests ------------------------------


def test_set_event_query_sets_query(view: MetadataView, mocker: MockerFixture) -> None:
    """Verify event query is set correctly."""
    view.set_event_query("SELECT * FROM events WHERE id > 100")

    assert view.event_query == "SELECT * FROM events WHERE id > 100"


def test_set_event_query_does_not_echo_to_the_status_panel(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Storing the event query shows nothing on the status panel."""
    view.set_event_query("SELECT * FROM events WHERE id > 100")

    view.add_text_to_display.emit.assert_not_called()


# ----------------------------- Update Available Columns Tests ------------------------------


def test_update_available_columns_emits_a_typed_intent(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Step 4a: an intent naming the loader, not a bus call describing the dispatch."""
    view.column_names_requested = mocker.Mock()

    view.update_available_columns("test_loader")

    view.column_names_requested.emit.assert_called_once_with("test_loader")


def test_update_available_columns_ignores_the_placeholder(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    Replaces test_update_available_columns_handles_exception.

    That test made ``global_signal.emit`` raise, which was worth guarding while the emit
    ran the whole dispatch synchronously. A typed intent has nothing to fail, and the
    Controller slot carries the try/except now - so the property left to assert here is
    the empty-state guard, which is what the method still decides.
    """
    view.column_names_requested = mocker.Mock()

    view.update_available_columns("No Event Database")

    view.column_names_requested.emit.assert_not_called()


# ----------------------------- Request Experiment Structure Tests ------------------------------


def test_request_experiment_structure_emits_a_typed_intent(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    The loader key travels with the request.

    The bus carried it as ``ret_args`` so the answer could be filed under the loader it
    came from; the intent carries it for the same reason.
    """
    view.experiment_structure_requested = mocker.Mock()

    view.request_experiment_structure("test_loader")

    view.experiment_structure_requested.emit.assert_called_once_with("test_loader")


# ----------------------------- Show Selection Tree Tests ------------------------------


def test_show_selection_tree_creates_tree_if_not_exists(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify selection tree is created if it doesn't exist."""
    if hasattr(view, "selection_tree"):
        delattr(view, "selection_tree")

    mock_tree_class = mocker.patch("poriscope.utils.MetaSubsetTabView.SelectionTree")
    mock_tree = mocker.Mock()
    mock_tree.show_dialog.return_value = {"exp1": [1, 2]}
    mock_tree_class.return_value = mock_tree

    view.show_selection_tree({"exp1": [1, 2, 3]}, "test_loader")

    mock_tree_class.assert_called_once()


def test_show_selection_tree_displays_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify dialog is displayed with correct parameters."""
    mock_tree = mocker.Mock()
    mock_tree.show_dialog.return_value = {"exp1": [1, 2]}
    view.selection_tree = mock_tree

    structure = {"exp1": [1, 2, 3], "exp2": [4, 5]}
    selection = {"exp1": [1]}

    view.show_selection_tree(structure, "test_loader", selection)

    mock_tree.show_dialog.assert_called_once_with(
        structure,
        "test_loader",
        title="Select Experiment and Channels",
        selected=selection,
    )


def test_show_selection_tree_updates_selection(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify selection is updated after dialog."""
    mock_tree = mocker.Mock()
    mock_tree.show_dialog.return_value = {"exp1": [1, 2]}
    view.selection_tree = mock_tree

    view.show_selection_tree({"exp1": [1, 2, 3]}, "test_loader")

    assert view.selected_experiment_and_channels_by_loader["test_loader"] == {
        "exp1": [1, 2]
    }


# ----------------------------- Update Units Tests ------------------------------


def test_update_units_emits_a_typed_intent(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    The column and the axis both travel with the request.

    ``update_units`` moved down here from ``MetaSubsetTabView`` in the same commit that
    converted it: it sat on the shared base but only this tab ever called it, because the
    protein tab has no units label to write an answer to.
    """
    view.column_units_requested = mocker.Mock()

    view.update_units("test_loader", "duration", "x_axis")

    view.column_units_requested.emit.assert_called_once_with(
        "test_loader", "duration", "x_axis"
    )


def test_update_units_ignores_the_placeholder(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Replaces test_update_units_handles_exception, for the reason given above."""
    view.column_units_requested = mocker.Mock()

    view.update_units("No Event Database", "duration", "x_axis")

    view.column_units_requested.emit.assert_not_called()


# ----------------------------- Update Column Names Tests ------------------------------


def test_update_column_names_updates_controls(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify metadata controls are updated with column names."""
    view.metadatacontrols = mocker.Mock()
    column_names = ["duration", "current", "voltage"]

    view.update_column_names(column_names)

    view.metadatacontrols.update_axes.assert_called_once_with(column_names)


# ----------------------------- Update Column Units Tests ------------------------------


def test_update_column_units_updates_controls(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify metadata controls are updated with column units."""
    view.metadatacontrols = mocker.Mock()

    view.update_column_units("ms", "x_axis")

    view.metadatacontrols.update_column_units_label.assert_called_once_with(
        "ms", "x_axis"
    )


# ----------------------------- Handle Other Actions Tests ------------------------------


def test_handle_other_actions_raises_not_implemented(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify NotImplementedError is raised for unhandled actions."""
    with pytest.raises(
        NotImplementedError, match="unknown_action handler not implemented"
    ):
        view._handle_other_actions("unknown_action", {})


# ----------------------------- Calculate Heatmap Tests ------------------------------


def test_plot_heatmap_sends_the_raw_columns_and_their_log_flags(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    The filter went down with the binning in Step 4's closeout.

    What the View sends is the column as it came out of the dataframe, plus the
    flags saying which axes are log-scaled - so the values that survive the filter
    are produced once, by the layer that also exports them.
    """
    data = pd.DataFrame({"x": np.array([1.0, 10.0]), "y": np.array([1.0, 10.0])})

    view._plot_heatmap(view.axes, data, ["x", "y"], ["u1", "u2"], [True, True])

    emitted = view.heatmap_requested.emit.call_args.args
    assert list(emitted[0]) == [1.0, 10.0]
    assert emitted[2] == [True, True]


# ----------------------------- Show Add Filter Dialog Tests ------------------------------


def test_show_add_filter_dialog_opens_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify dialog is opened with existing filter names."""
    view._walkthrough_active = False
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mock_dialog_class = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 0
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog

    view._show_add_filter_dialog({"db_loader": "test"})

    mock_dialog_class.assert_called_once()
    assert mock_dialog_class.call_args[1]["existing_names"] == ["Filter1"]


def test_show_add_filter_dialog_validates_filter_on_accept(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filter is validated via global signal when accepted."""
    view._walkthrough_active = False
    mock_dialog_class = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 1  # Accepted
    mock_dialog.name = "NewFilter"
    mock_dialog.filter_text = "WHERE duration > 100"
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog
    view._show_add_filter_dialog({"db_loader": "test_loader"})

    # Step 4a: the Controller makes the construct_metadata_query call now, and picks
    # the columns to validate against, so the View's half is the intent alone.
    view.filter_validation_requested.emit.assert_called_once_with(
        "test_loader",
        "WHERE duration > 100",
        "validate_new_filter",
        "NewFilter",
        None,
    )


def test_show_add_filter_dialog_returns_when_no_loader(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify early return when no loader is provided."""
    view._walkthrough_active = False
    mock_dialog_class = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.AddSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 1
    mock_dialog.name = "NewFilter"
    mock_dialog.filter_text = "WHERE x > 1"
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog

    view._show_add_filter_dialog({"db_loader": ""})


# ----------------------------- Show Filter Info Dialog Tests ------------------------------


def test_show_filter_info_dialog_warns_when_no_selection(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning when no filter is selected."""
    mock_combobox = mocker.Mock()
    mock_combobox.getSelectedItems.return_value = []

    view._show_filter_info_dialog(mock_combobox, {"db_loader": "test"})

    view.logger.warning.assert_called()


def test_show_filter_info_dialog_warns_when_multiple_selected(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning when multiple filters are selected."""
    mock_combobox = mocker.Mock()
    mock_combobox.getSelectedItems.return_value = ["Filter1", "Filter2"]

    view._show_filter_info_dialog(mock_combobox, {"db_loader": "test"})

    view.logger.warning.assert_called()


def test_show_filter_info_dialog_calls_edit_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify edit dialog is called when exactly one filter is selected."""
    mock_combobox = mocker.Mock()
    mock_combobox.getSelectedItems.return_value = ["Filter1"]
    view.show_edit_filter_dialog = mocker.Mock()

    view._show_filter_info_dialog(mock_combobox, {"db_loader": "test_loader"})

    view.show_edit_filter_dialog.assert_called_once_with("Filter1", "test_loader")


# ----------------------------- Show Edit Filter Dialog Tests ------------------------------


def test_show_edit_filter_dialog_opens_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify edit dialog is opened with correct parameters."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mock_dialog_class = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.EditSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 0
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog

    view.show_edit_filter_dialog("Filter1", "test_loader")

    mock_dialog_class.assert_called_once()
    call_args = mock_dialog_class.call_args[0]
    assert call_args[1] == "Filter1"
    assert call_args[2] == {"Filter1": "WHERE x > 1"}


def test_show_edit_filter_dialog_validates_on_accept(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filter is validated when dialog is accepted."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mock_dialog_class = mocker.patch(
        "poriscope.utils.MetaSubsetTabView.EditSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 1
    mock_dialog.new_name = "Filter1Updated"
    mock_dialog.new_filter = "WHERE x > 10"
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog
    view.show_edit_filter_dialog("Filter1", "test_loader")

    view.filter_validation_requested.emit.assert_called_once_with(
        # Step 4d: an edit carries the new name and the one it replaces, which is
        # what used to be parked on the widget as _pending_old_filter_name.
        "test_loader",
        "WHERE x > 10",
        "validate_edited_filter",
        "Filter1Updated",
        "Filter1",
    )


# ----------------------------- Delete Filter By Name Tests ------------------------------


def test_delete_filter_by_name_calls_delete_filter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _delete_filter is called with the name."""
    view._delete_filter = mocker.Mock()

    view._delete_filter_by_name("Filter1")

    view._delete_filter.assert_called_once_with("Filter1")


# ----------------------------- Delete All Selected Filters Tests ------------------------------


def test_delete_all_selected_filters_returns_when_none_selected(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify early return when no filters are selected."""
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox.getSelectedItems.return_value = []
    view._delete_filter = mocker.Mock()

    view._delete_all_selected_filters()

    view._delete_filter.assert_not_called()


def test_delete_all_selected_filters_deletes_each_selected(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify each selected filter is deleted."""
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox.getSelectedItems.return_value = [
        "Filter1",
        "Filter2",
    ]
    view._delete_filter = mocker.Mock()

    view._delete_all_selected_filters()

    assert view._delete_filter.call_count == 2


# ----------------------------- Delete Filter Tests ------------------------------


def test_delete_filter_removes_from_dict(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filter is removed from subset_filters dict."""
    view.subset_filters = {"Filter1": "WHERE x > 1", "Filter2": "WHERE y < 10"}
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox.listWidget = mocker.Mock()
    view.metadatacontrols.filter_comboBox.listWidget.count.return_value = 0

    view._delete_filter("Filter1")

    assert "Filter1" not in view.subset_filters
    assert "Filter2" in view.subset_filters


def test_delete_filter_removes_from_ui(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filter is removed from UI list widget."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    view.metadatacontrols = mocker.Mock()

    mock_item = mocker.Mock()
    mock_checkbox = mocker.Mock()
    mock_checkbox.text.return_value = "Filter1"
    mock_widget = mocker.Mock()
    mock_widget.findChild.return_value = mock_checkbox

    mock_list = mocker.Mock()
    mock_list.count.return_value = 1
    mock_list.item.return_value = mock_item
    mock_list.itemWidget.return_value = mock_widget

    view.metadatacontrols.filter_comboBox.listWidget = mock_list

    view._delete_filter("Filter1")

    mock_list.takeItem.assert_called_once()


# ----------------------------- Get Selected Filters Tests ------------------------------


def test_get_selected_filters_returns_selected_filter_dict(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify selected filters are returned as dict."""
    view.subset_filters = {
        "Filter1": "WHERE x > 1",
        "Filter2": "WHERE y < 10",
        "Filter3": "WHERE z = 5",
    }
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox = mocker.Mock()
    view.metadatacontrols.filter_comboBox.getSelectedItems = mocker.Mock(
        return_value=["Filter1", "Filter3"]
    )
    view.get_selected_filters = MetadataView.get_selected_filters.__get__(view)

    result = view.get_selected_filters()

    assert result == {"Filter1": "WHERE x > 1", "Filter3": "WHERE z = 5"}


def test_get_selected_filters_returns_empty_dict_when_none_selected(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify empty dict is returned when no filters selected."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox = mocker.Mock()
    view.metadatacontrols.filter_comboBox.getSelectedItems = mocker.Mock(
        return_value=[]
    )
    view.get_selected_filters = MetadataView.get_selected_filters.__get__(view)

    result = view.get_selected_filters()

    assert result == {}


# ----------------------------- Replace Filter Item Tests ------------------------------


def test_replace_filter_item_removes_existing_item(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify existing filter item is removed before adding new one."""
    view.metadatacontrols = mocker.Mock()

    mock_checkbox = mocker.Mock()
    mock_checkbox.text.return_value = "Filter1"
    mock_widget = mocker.Mock()
    mock_widget.findChild.return_value = mock_checkbox

    mock_list = mocker.Mock()
    mock_list.count.return_value = 1
    mock_list.itemWidget.return_value = mock_widget

    view.metadatacontrols.filter_comboBox.listWidget = mock_list

    view.replace_filter_item("Filter1")

    mock_list.takeItem.assert_called_once()


def test_replace_filter_item_adds_new_item(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify new filter item is added."""
    view.metadatacontrols = mocker.Mock()
    mock_list = mocker.Mock()
    mock_list.count.return_value = 0
    view.metadatacontrols.filter_comboBox.listWidget = mock_list

    view.replace_filter_item("Filter1")

    view.metadatacontrols.filter_comboBox.addItem.assert_called_once_with("Filter1")


def test_replace_filter_item_selects_new_item(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify new filter item is selected."""
    view.metadatacontrols = mocker.Mock()
    mock_list = mocker.Mock()
    mock_list.count.return_value = 0
    view.metadatacontrols.filter_comboBox.listWidget = mock_list

    view.replace_filter_item("Filter1")

    view.metadatacontrols.filter_comboBox.selectItem.assert_called_once_with(
        "Filter1", select=True
    )


# ----------------------------- Update Filter Name Tests ------------------------------


def test_update_filter_name_removes_old_name(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify old filter name is removed from UI."""
    view.metadatacontrols = mocker.Mock()

    mock_checkbox = mocker.Mock()
    mock_checkbox.text.return_value = "OldFilter"
    mock_widget = mocker.Mock()
    mock_widget.findChild.return_value = mock_checkbox

    mock_list = mocker.Mock()
    mock_list.count.return_value = 2
    mock_list.itemWidget.return_value = mock_widget

    view.metadatacontrols.filter_comboBox.listWidget = mock_list

    view.update_filter_name("OldFilter", "NewFilter")

    # Should be called at least once for old name
    assert mock_list.takeItem.call_count >= 1


def test_update_filter_name_adds_new_name(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify new filter name is added to UI."""
    view.metadatacontrols = mocker.Mock()
    mock_list = mocker.Mock()
    mock_list.count.return_value = 0
    view.metadatacontrols.filter_comboBox.listWidget = mock_list

    view.update_filter_name("OldFilter", "NewFilter")

    view.metadatacontrols.filter_comboBox.addItem.assert_called_with("NewFilter")


def test_update_filter_name_refreshes_display(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify display text is refreshed after update."""
    view.metadatacontrols = mocker.Mock()
    mock_list = mocker.Mock()
    mock_list.count.return_value = 0
    view.metadatacontrols.filter_comboBox.listWidget = mock_list

    view.update_filter_name("OldFilter", "NewFilter")

    view.metadatacontrols.filter_comboBox.refreshDisplayText.assert_called_once()


# ===========================================================================
# get_current_view
# ===========================================================================


def test_get_current_view_returns_correct_string(view: MetadataView) -> None:
    assert view.get_current_view() == "MetadataView"


# ===========================================================================
# get_walkthrough_steps
# ===========================================================================


def test_get_walkthrough_steps_returns_list(view: MetadataView) -> None:
    assert isinstance(view.get_walkthrough_steps(), list)


def test_get_walkthrough_steps_has_correct_count(view: MetadataView) -> None:
    """Verify walkthrough has the correct number of steps."""
    assert len(view.get_walkthrough_steps()) == 25


def test_get_walkthrough_steps_each_is_four_tuple(view: MetadataView) -> None:
    for step in view.get_walkthrough_steps():
        assert len(step) == 4


def test_get_walkthrough_steps_widget_callables_return_lists(
    view: MetadataView, mocker: MockerFixture
) -> None:
    # metadatacontrols must exist for the lambdas to not crash
    view.metadatacontrols = mocker.Mock()
    for _, _, _, fn in view.get_walkthrough_steps():
        result = fn()
        assert isinstance(result, list)
        assert len(result) >= 1


# ===========================================================================
# is_categorical_type
# ===========================================================================


class TestIsCategoricalType:
    def test_none_is_categorical(self, view: MetadataView) -> None:
        assert view.is_categorical_type(None) is True

    def test_empty_string_is_categorical(self, view: MetadataView) -> None:
        assert view.is_categorical_type("") is True

    def test_integer_type_is_categorical(self, view: MetadataView) -> None:
        assert view.is_categorical_type("INTEGER") is True

    def test_text_type_is_categorical(self, view: MetadataView) -> None:
        assert view.is_categorical_type("TEXT") is True

    def test_boolean_type_is_categorical(self, view: MetadataView) -> None:
        assert view.is_categorical_type("BOOLEAN") is True

    def test_numeric_type_is_categorical(self, view: MetadataView) -> None:
        # NUMERIC does not contain REAL, FLOAT, or DOUB so is categorical
        assert view.is_categorical_type("NUMERIC") is True

    def test_real_type_is_not_categorical(self, view: MetadataView) -> None:
        assert view.is_categorical_type("REAL") is False

    def test_float_type_is_not_categorical(self, view: MetadataView) -> None:
        assert view.is_categorical_type("FLOAT") is False

    def test_double_type_is_not_categorical(self, view: MetadataView) -> None:
        assert view.is_categorical_type("DOUBLE") is False

    def test_double_precision_is_not_categorical(self, view: MetadataView) -> None:
        assert view.is_categorical_type("DOUBLE PRECISION") is False

    def test_case_insensitive_real(self, view: MetadataView) -> None:
        assert view.is_categorical_type("real") is False

    def test_case_insensitive_float(self, view: MetadataView) -> None:
        assert view.is_categorical_type("float") is False


# ===========================================================================
# Simple state-setter callbacks
# ===========================================================================


class TestSimpleSetters:
    def test_set_column_type(self, view: MetadataView) -> None:
        view.set_column_type("REAL")
        assert view.column_type == "REAL"

    def test_set_column_type_none(self, view: MetadataView) -> None:
        view.set_column_type(None)
        assert view.column_type is None


# ===========================================================================
# _plot_categorical_histogram
# ===========================================================================


class TestPlotCategoricalHistogram:
    def _data(self) -> pd.DataFrame:
        return pd.DataFrame({"category": ["A", "B", "A", "C", "B", "A"]})

    def test_calls_bar(self, view: MetadataView) -> None:
        view._plot_categorical_histogram(view.axes, self._data(), ["category"], [""])
        _answer_categorical_counts(view)
        view.axes.bar.assert_called()

    def test_clears_axes_before_plot(self, view: MetadataView) -> None:
        view._plot_categorical_histogram(view.axes, self._data(), ["category"], [""])
        view.axes.clear.assert_called()

    def test_sets_axis_labels(self, view: MetadataView) -> None:
        view._plot_categorical_histogram(
            view.axes, self._data(), ["category"], ["unit"]
        )
        _answer_categorical_counts(view)
        view.axes.set_xlabel.assert_called()
        view.axes.set_ylabel.assert_called()

    def test_rotates_x_tick_labels(self, view: MetadataView) -> None:
        view._plot_categorical_histogram(view.axes, self._data(), ["category"], [""])
        _answer_categorical_counts(view)
        view.axes.tick_params.assert_called()

    def test_appends_to_hist_data(self, view: MetadataView) -> None:
        before = len(view.hist_data)
        view._plot_categorical_histogram(
            view.axes, self._data(), ["category"], [""], dataset_label="ds"
        )
        assert len(view.hist_data) == before + 1
        assert view.hist_labels[-1] == "ds"

    def test_counts_categories_correctly(self, view: MetadataView) -> None:
        # A=3, B=2, C=1
        view._plot_categorical_histogram(view.axes, self._data(), ["category"], [""])
        _answer_categorical_counts(view)
        call_args = view.axes.bar.call_args
        categories = list(call_args[0][0])
        counts = list(call_args[0][1])
        assert set(categories) == {"A", "B", "C"}
        idx_a = categories.index("A")
        assert counts[idx_a] == 3.0

    def test_overlays_multiple_datasets(self, view: MetadataView) -> None:
        data2 = pd.DataFrame({"category": ["A", "D"]})
        view._plot_categorical_histogram(
            view.axes, self._data(), ["category"], [""], dataset_label="d1"
        )
        view._plot_categorical_histogram(
            view.axes, data2, ["category"], [""], dataset_label="d2"
        )
        assert len(view.hist_data) == 2
        assert len(view.hist_labels) == 2


# ===========================================================================
# update_plot — Categorical Histogram branch
# ===========================================================================


def test_update_plot_calls_categorical_histogram(
    view: MetadataView, mocker: MockerFixture
) -> None:
    data = pd.DataFrame({"category": ["A", "B", "C"]})
    view._plot_categorical_histogram = mocker.Mock()
    view.update_plot("Categorical Histogram", data, ["category"], [""], [])
    view._plot_categorical_histogram.assert_called_once()


def test_update_plot_categorical_histogram_redraws_canvas(
    view: MetadataView, mocker: MockerFixture
) -> None:
    data = pd.DataFrame({"category": ["A", "B", "C"]})
    view.update_plot("Categorical Histogram", data, ["category"], [""], [])
    view.canvas.draw.assert_called()


# ===========================================================================
# update_plot — Normalized All Points Histogram branches
# ===========================================================================


@pytest.mark.parametrize(
    "plot_type",
    [
        "Raw All Points Histogram",
        "Filtered All Points Histogram",
        "Normalized Raw All Points Histogram",
        "Normalized Filtered All Points Histogram",
    ],
)
def test_update_plot_no_longer_dispatches_the_all_points_histogram(
    view: MetadataView, mocker: MockerFixture, plot_type: str
) -> None:
    """
    Verify the four event-data types are refused by the metadata dispatch.

    Step 4's closeout took their data off the widget, so they no longer arrive as a
    dataframe and ``set_all_points_histogram`` draws them instead. Leaving the
    branch here would have left a path nothing can reach with a frame to give it.
    """
    view._plot_all_points_histogram = mocker.Mock()
    data = pd.DataFrame(
        {"Current": np.array([1.0, 2.0]), "Count": np.array([10.0, 20.0])}
    )

    with pytest.raises(NotImplementedError):
        view.update_plot(
            plot_type,
            data,
            ["Current", "Count"],
            ["pA", ""],
            [False, False],
        )

    view._plot_all_points_histogram.assert_not_called()


# ===========================================================================
# on_raw_filter_validated
# ===========================================================================


class TestOnRawFilterValidated:
    def _setup(self, view: MetadataView, mocker: MockerFixture) -> None:
        view.metadatacontrols = mocker.Mock()
        view.metadatacontrols.filter_comboBox = mocker.Mock()


# ===========================================================================
# handle_parameter_change — "plot_type_changed" branch
# ===========================================================================


def test_handle_parameter_change_plot_type_changed_does_not_crash(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """The plot_type_changed branch reads loader and plot_type but does nothing else."""
    view.metadatacontrols = mocker.Mock()
    params = {"db_loader": "test_loader", "plot_type": "Histogram"}
    view.handle_parameter_change("metadata", "plot_type_changed", (params,))
    # No assertion needed — just must not raise


# ===========================================================================
# handle_parameter_change — Categorical Histogram guard in "update_plot"
# ===========================================================================


class TestHandleParameterChangeCategoricalGuard:
    def _params(self, col: str = "category") -> dict:
        return {
            "db_loader": "test_loader",
            "plot_type": "Categorical Histogram",
            "x_axis": col,
        }

    def test_non_categorical_type_emits_warning_and_returns_early(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        """When column type is continuous, emits a message and skips _overlay_plot."""
        view.canned_column_type = "REAL"
        view._overlay_plot = mocker.Mock(return_value=True)

        view.handle_parameter_change("metadata", "update_plot", (self._params(),))

        view._overlay_plot.assert_not_called()
        view.add_text_to_display.emit.assert_called()

    def test_categorical_type_proceeds_to_overlay_plot(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        """When column type is categorical (e.g. INTEGER), _overlay_plot is called."""
        view.canned_column_type = "INTEGER"
        view._overlay_plot = mocker.Mock(return_value=True)

        view.handle_parameter_change("metadata", "update_plot", (self._params(),))

        view._overlay_plot.assert_called_once()

    def test_none_column_type_proceeds_to_overlay_plot(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        """When column type is None (unknown), treated as categorical — proceeds."""
        view.canned_column_type = None
        view._overlay_plot = mocker.Mock(return_value=True)

        view.handle_parameter_change("metadata", "update_plot", (self._params(),))

        view._overlay_plot.assert_called_once()


# ===========================================================================
# _overlay_plot — Normalized All Points Histogram branches
# ===========================================================================


class TestOverlayPlotNormalizedHistograms:
    def _base_params(self, plot_type: str) -> dict:
        return {
            "db_loader": "test_loader",
            "plot_type": plot_type,
            "bins": [50],
            "sizes": False,
        }

    def _setup(self, view: MetadataView, mocker: MockerFixture) -> None:
        view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
        view.selected_experiment_and_channels_by_loader = {}
        view.canned_event_query = "SELECT * FROM events"

    def test_normalized_raw_all_points_histogram_is_requested(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view._overlay_plot(self._base_params("Normalized Raw All Points Histogram"))
        view.all_points_histogram_requested.emit.assert_called_once()
        assert (
            view.all_points_histogram_requested.emit.call_args[0][3]
            == "Normalized Raw All Points Histogram"
        )

    def test_normalized_filtered_all_points_histogram_is_requested(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view._overlay_plot(
            self._base_params("Normalized Filtered All Points Histogram")
        )
        view.all_points_histogram_requested.emit.assert_called_once()
        assert (
            view.all_points_histogram_requested.emit.call_args[0][3]
            == "Normalized Filtered All Points Histogram"
        )


# ===========================================================================
# _overlay_plot — Categorical Histogram branch
# ===========================================================================


class TestOverlayPlotCategoricalHistogram:
    def _params(self) -> dict:
        return {
            "db_loader": "test_loader",
            "plot_type": "Categorical Histogram",
            "x_axis": "category",
            "x_log": False,
            "bins": [50],
            "sizes": False,
        }

    def test_categorical_histogram_calls_update_plot(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        view.figure.axes = []
        view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
        view.selected_experiment_and_channels_by_loader = {}
        plot_data = pd.DataFrame({"category": ["A", "B", "A"]})
        view.canned_plot_data = plot_data
        view.canned_query = "SELECT * FROM events"
        view.canned_units = ""
        view.update_plot = mocker.Mock()

        view._overlay_plot(self._params())

        view.update_plot.assert_called_once()
        assert view.update_plot.call_args[0][0] == "Categorical Histogram"

    def test_categorical_histogram_passes_correct_columns(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        view.figure.axes = []
        view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
        view.selected_experiment_and_channels_by_loader = {}
        plot_data = pd.DataFrame({"category": ["A", "B", "C"]})
        view.canned_plot_data = plot_data
        view.canned_query = "SELECT * FROM events"
        view.canned_units = ""
        view.update_plot = mocker.Mock()

        view._overlay_plot(self._params())

        call_args = view.update_plot.call_args
        assert call_args[0][2] == ["category"]

    def test_categorical_histogram_returns_true_on_success(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        view.figure.axes = []
        view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
        view.selected_experiment_and_channels_by_loader = {}
        plot_data = pd.DataFrame({"category": ["A", "B", "C"]})
        view.canned_plot_data = plot_data
        view.canned_query = "SELECT * FROM events"
        view.canned_units = ""
        view.update_plot = mocker.Mock()

        result = view._overlay_plot(self._params())

        assert result is True


def test_set_event_plot_data_generator_sets_generator(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify event plot data generator is set and no longer sets plot_events_generator_updated."""
    generator = iter([{"data": "test"}])

    view.set_event_plot_data_generator(generator)

    assert view.plot_events_generator == generator
    assert not hasattr(view, "plot_events_generator_updated")


def test_handle_plot_events_uses_cache_for_navigation(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify bisect snap into filtered_event_ids cache."""
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10, 15, 20]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._update_event_plot = mocker.Mock()
    view.canned_plot_events_generator = iter([_FULL_EVENT])
    parameters = {
        "db_loader": "test_loader",
        "event_id": 3,
        "n_events": 1,
        "raw": False,
    }
    view._handle_plot_events(parameters)

    view.metadatacontrols.set_event_id_input.assert_called_with(5)


# ----------------------------- Filtered Event ID Cache Tests ------------------------------


def test_init_sets_filtered_event_ids_empty_list(view: MetadataView) -> None:
    """Verify filtered_event_ids is initialized to empty list."""
    assert view.filtered_event_ids == []


def test_rebuild_event_id_cache_returns_false_when_no_events(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify False is returned when no filtered events are found."""
    view.event_id_cache_requested.emit.side_effect = lambda *_: setattr(
        view, "event_id_rows", pd.DataFrame()
    )

    result = view._rebuild_event_id_cache("loader", "", None, None)

    assert result is False
    view.add_text_to_display.emit.assert_called()
    assert "No filtered events" in view.add_text_to_display.emit.call_args[0][0]


def test_rebuild_event_id_cache_stores_event_ids(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filtered_event_ids is populated, and sorted, from the query result."""
    view.event_id_cache_requested.emit.side_effect = lambda *_: setattr(
        view, "event_id_rows", pd.DataFrame({"event_id": [10, 0, 5]})
    )

    result = view._rebuild_event_id_cache("loader", "", None, None)

    assert result is True
    assert view.filtered_event_ids == [0, 5, 10]


def test_rebuild_event_id_cache_updates_current_trackers(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify current_sql_filter, current_experiment, and current_channel are updated."""
    view.event_id_cache_requested.emit.side_effect = lambda *_: setattr(
        view, "event_id_rows", pd.DataFrame({"event_id": [1, 2, 3]})
    )

    view._rebuild_event_id_cache("loader", "duration > 1", "exp1", 2)

    assert view.current_sql_filter == "duration > 1"
    assert view.current_experiment == "exp1"
    assert view.current_channel == 2


def test_rebuild_event_id_cache_emits_all_events_when_no_filter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify display panel message says 'All events' when no filter is active."""
    view.get_selected_filters = mocker.Mock(return_value={})
    view.event_id_cache_requested.emit.side_effect = lambda *_: setattr(
        view, "event_id_rows", pd.DataFrame({"event_id": [0, 1, 2]})
    )

    view._rebuild_event_id_cache("loader", "", None, None)

    msg = view.add_text_to_display.emit.call_args[0][0]
    assert "All events" in msg


def test_rebuild_event_id_cache_emits_filter_name_when_filter_active(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify display panel message includes filter name and 'subset' when filter is active."""
    view.get_selected_filters = mocker.Mock(return_value={"my_filter": "duration > 1"})
    view.event_id_cache_requested.emit.side_effect = lambda *_: setattr(
        view, "event_id_rows", pd.DataFrame({"event_id": [3, 7]})
    )

    view._rebuild_event_id_cache("loader", "duration > 1", None, None)

    msg = view.add_text_to_display.emit.call_args[0][0]
    assert "my_filter" in msg
    assert "subset" in msg


def test_rebuild_event_id_cache_emits_total_and_bounds(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify display panel message includes total count, first and last event_id."""
    view.get_selected_filters = mocker.Mock(return_value={})
    view.event_id_cache_requested.emit.side_effect = lambda *_: setattr(
        view, "event_id_rows", pd.DataFrame({"event_id": [2, 5, 9]})
    )

    view._rebuild_event_id_cache("loader", "", None, None)

    msg = view.add_text_to_display.emit.call_args[0][0]
    assert "3 total" in msg
    assert "first event_id: 2" in msg
    assert "last event_id: 9" in msg


# ----------------------------- Shift Range and Update Plot Tests (new) ------------------------------


def test_shift_range_and_update_plot_returns_early_when_no_experiments(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify early return when no experiment/channel scope is available."""
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view._handle_plot_events = mocker.Mock()

    view._shift_range_and_update_plot(
        {"db_loader": "test_loader", "event_id": 0, "n_events": 1}, "right"
    )

    view._handle_plot_events.assert_not_called()


def test_shift_range_and_update_plot_rebuilds_cache_when_stale(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify cache is rebuilt when filter or scope has changed."""
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = []
    view.current_sql_filter = None
    view._rebuild_event_id_cache = mocker.Mock(return_value=False)

    view._shift_range_and_update_plot(
        {"db_loader": "test_loader", "event_id": 0, "n_events": 1}, "right"
    )

    view._rebuild_event_id_cache.assert_called_once()


def test_shift_range_and_update_plot_wraps_forward_at_end(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify forward navigation wraps to index 0 when past the last event."""
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._handle_plot_events = mocker.Mock()

    view._shift_range_and_update_plot(
        {"db_loader": "test_loader", "event_id": 10, "n_events": 1}, "right"
    )

    view.metadatacontrols.set_event_id_input.assert_called_with(0)


def test_shift_range_and_update_plot_wraps_backward_at_start(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify backward navigation wraps to the last window when before the first event."""
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._handle_plot_events = mocker.Mock()

    view._shift_range_and_update_plot(
        {"db_loader": "test_loader", "event_id": 0, "n_events": 1}, "left"
    )

    view.metadatacontrols.set_event_id_input.assert_called_with(10)


def test_shift_range_and_update_plot_calls_handle_plot_events(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _handle_plot_events is called with updated event_id after shift."""
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._handle_plot_events = mocker.Mock()

    view._shift_range_and_update_plot(
        {"db_loader": "test_loader", "event_id": 0, "n_events": 1}, "right"
    )

    view._handle_plot_events.assert_called_once()
    called_params = view._handle_plot_events.call_args[0][0]
    assert called_params["event_id"] == 5


# ----------------------------- Handle Plot Events Tests (new) ------------------------------


def test_handle_plot_events_snaps_to_nearest_filtered_event(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify event_id is snapped to nearest filtered event at or after the requested id."""
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10, 15, 20]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._update_event_plot = mocker.Mock()
    view.canned_plot_events_generator = iter([dict(_FULL_EVENT)])

    view._handle_plot_events(
        {"db_loader": "test_loader", "event_id": 3, "n_events": 1, "raw": False}
    )

    view.metadatacontrols.set_event_id_input.assert_called_with(5)


def test_handle_plot_events_wraps_to_first_when_past_last(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify event_id wraps to first filtered event when requested id exceeds all cached ids."""
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._update_event_plot = mocker.Mock()
    view.canned_plot_events_generator = iter([dict(_FULL_EVENT)])

    view._handle_plot_events(
        {"db_loader": "test_loader", "event_id": 99, "n_events": 1, "raw": False}
    )

    view.metadatacontrols.set_event_id_input.assert_called_with(0)


def test_handle_plot_events_rebuilds_cache_on_filter_change(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify cache is rebuilt when sql_filter has changed since last plot."""
    view.get_selected_filters = mocker.Mock(return_value={"new_filter": "duration > 5"})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 1, 2]
    view.current_sql_filter = "old_filter"
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._rebuild_event_id_cache = mocker.Mock(return_value=False)

    view._handle_plot_events(
        {"db_loader": "test_loader", "event_id": 0, "n_events": 1, "raw": False}
    )

    view._rebuild_event_id_cache.assert_called_once()


def test_handle_plot_events_does_not_rebuild_cache_when_scope_unchanged(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify cache is not rebuilt when filter and scope are unchanged."""
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._rebuild_event_id_cache = mocker.Mock(return_value=True)
    view._update_event_plot = mocker.Mock()
    view.canned_plot_events_generator = iter([dict(_FULL_EVENT)])

    view._handle_plot_events(
        {"db_loader": "test_loader", "event_id": 0, "n_events": 1, "raw": False}
    )

    view._rebuild_event_id_cache.assert_not_called()


def test_handle_plot_events_requests_the_snapped_ids_in_scope(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify the event-plot intent carries the snapped ids and the current scope.

    Was ``..._returns_early_when_no_db_ids``, which drove the db-id resolution the
    View used to do a statement at a time. That whole chain is the Controller's now,
    so what is left to pin here is the request it sends.
    """
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._update_event_plot = mocker.Mock()

    view._handle_plot_events(
        {"db_loader": "test_loader", "event_id": 4, "n_events": 2, "raw": False}
    )

    view.event_plot_data_requested.emit.assert_called_once_with(
        "test_loader", [5, 10], "exp1", 1, {"exp1": [1]}, "events"
    )


def test_handle_plot_events_leaves_the_reporting_to_the_controller(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify nothing is plotted, and nothing said, when no generator comes back.

    The Controller reports which part of the chain failed, so a message from here as
    well would say the same thing twice.
    """
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._update_event_plot = mocker.Mock()

    view._handle_plot_events(
        {"db_loader": "test_loader", "event_id": 0, "n_events": 1, "raw": False}
    )

    assert view.plot_events_generator is None
    view._update_event_plot.assert_not_called()
    view.add_text_to_display.emit.assert_not_called()


# ----------------------------- _overlay_plot scope guards ------------------------------


def test_overlay_plot_reports_multiple_channels_for_a_heatmap(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Probe: does the refusal reach the status panel, or only the log?"""
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {  # type: ignore[assignment]
        "test_loader": {"exp1": ["1", "2"]}
    }

    result = view._overlay_plot({"db_loader": "test_loader", "plot_type": "Heatmap"})

    assert result is False
    said = [call.args[0] for call in view.add_text_to_display.emit.call_args_list]
    assert any("single channel" in message for message in said), said


def test_overlay_plot_resets_before_an_event_overlay_after_another_plot_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """
    Reported from a real run: an All Points Histogram was still on the axes when
    an Event Overlay drew over it, which superimposes two unrelated pictures.

    Every other plot type resets on a change of type. The overlay branch checked
    only whether the axes were *valid* - and a 2-D axes carrying someone else's
    bars is perfectly valid - so nothing cleared them.
    """
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_event_query = "SELECT * FROM events"
    view.allowed_plot_type = "Raw All Points Histogram"
    view._axes_valid = mocker.Mock(return_value=True)
    view._reset_actions = mocker.Mock()

    view._overlay_plot({"db_loader": "test_loader", "plot_type": "Raw Event Overlay"})

    view._reset_actions.assert_called_once_with(axis_type="2d")


def test_overlay_plot_does_not_reset_a_second_overlay_of_the_same_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Overlaying another subset of the same type is what the plot is for."""
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.canned_event_query = "SELECT * FROM events"
    view.allowed_plot_type = "Raw Event Overlay"
    view._axes_valid = mocker.Mock(return_value=True)
    view._reset_actions = mocker.Mock()

    view._overlay_plot({"db_loader": "test_loader", "plot_type": "Raw Event Overlay"})

    view._reset_actions.assert_not_called()
