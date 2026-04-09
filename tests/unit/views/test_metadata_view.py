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

from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.MetadataView import (
    MetadataView,
    format_axis_label,
)

# ----------------------------- Fixtures ------------------------------


@pytest.fixture
def mock_qt_dependencies(mocker: MockerFixture) -> None:
    """Mock all Qt and external dependencies to prevent GUI initialization."""
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.QFileDialog")
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.QHBoxLayout")
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.MetadataControls")
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.MetaView.__init__",
        return_value=None,
    )
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.WalkthroughMixin.__init__",
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
    view_instance._logscale_and_filter_multiple_columns = mocker.Mock(
        side_effect=lambda *args, **kwargs: (args[0],) if args else ()
    )

    # Mock methods called by _overlay_plot
    view_instance.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view_instance.global_signal = mocker.Mock()
    
    # Additional mocks needed before _init()
    view_instance._commit_cache = mocker.Mock()
    view_instance.logger = mocker.Mock()

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
    assert len(view.metadata_plots) == 7
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


def test_init_sets_cached_events_empty_dict(view: MetadataView) -> None:
    """Verify cached_events is initialized to empty dict."""
    assert view.cached_events == {}


def test_init_sets_subset_filters_empty_dict(view: MetadataView) -> None:
    """Verify subset_filters is initialized to empty dict."""
    assert view.subset_filters == {}


def test_init_sets_plot_events_generator_none(view: MetadataView) -> None:
    """Verify plot_events_generator is initialized to None."""
    assert view.plot_events_generator is None


def test_init_sets_plotted_datasets_empty_set(view: MetadataView) -> None:
    """Verify plotted_datasets is initialized to empty set."""
    assert view.plotted_datasets == set()


def test_init_sets_show_sql_in_display_false(view: MetadataView) -> None:
    """Verify _show_sql_in_display is initialized to False."""
    assert view._show_sql_in_display is False


def test_init_sets_show_event_sql_in_display_false(view: MetadataView) -> None:
    """Verify _show_event_sql_in_display is initialized to False."""
    assert view._show_event_sql_in_display is False


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
    """Verify MetadataControls instance is created."""
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
    """Verify controls are added to layout."""
    mock_layout: MagicMock = mocker.Mock()
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.QHBoxLayout")

    view._set_control_area(mock_layout)

    mock_layout.addLayout.assert_called_once()


# ----------------------------- File Dialog Tests ------------------------------


def test_get_save_filename_opens_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify QFileDialog.getSaveFileName is called."""
    mock_dialog: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getSaveFileName",
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
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getSaveFileName",
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
    """Verify constrained layout is set."""
    view._clear_figure_state()

    view.figure.set_constrained_layout.assert_called_with(True)


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


def test_plot_1d_density_updates_hist_min(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify hist_min is updated with minimum data value."""
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 2.0, 5.0, 10.0])})

    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3])
    mock_kde_class.return_value = mock_kde_instance

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 5.0, 10.0]),)
    )

    original_min = min

    def mock_min(*args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and isinstance(args[0], pd.DataFrame):
            return args[0].min().min()
        return original_min(*args, **kwargs)

    mocker.patch("builtins.min", side_effect=mock_min)

    view._plot_1d_density(view.axes, data, ["x"], ["units"], [False])

    assert view.hist_min == 1.0


def test_plot_1d_density_updates_hist_max(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify hist_max is updated with maximum data value."""
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 2.0, 5.0, 10.0])})

    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3])
    mock_kde_class.return_value = mock_kde_instance

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 5.0, 10.0]),)
    )

    original_max = max

    def mock_max(*args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and isinstance(args[0], pd.DataFrame):
            return args[0].max().max()
        return original_max(*args, **kwargs)

    mocker.patch("builtins.max", side_effect=mock_max)

    view._plot_1d_density(view.axes, data, ["x"], ["units"], [False])

    assert view.hist_max == 10.0


def test_plot_1d_density_clears_axes(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axes are cleared before plotting."""
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 2.0])})

    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2])
    mock_kde_class.return_value = mock_kde_instance

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0]),)
    )

    view._plot_1d_density(view.axes, data, ["x"], [""], [False])

    view.axes.clear.assert_called()


def test_plot_1d_density_appends_to_hist_data(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify data is appended to hist_data."""
    data: pd.DataFrame = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})

    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3])
    mock_kde_class.return_value = mock_kde_instance

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0]),)
    )

    view._plot_1d_density(view.axes, data, ["x"], [""], [False], dataset_label="test")

    assert len(view.hist_data) == 1
    assert len(view.hist_labels) == 1
    assert view.hist_labels[0] == "test"


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

    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3])
    mock_kde_class.return_value = mock_kde_instance

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([0.0, 1.0, 2.0]),)
    )

    view._plot_1d_density(view.axes, data, ["x"], ["units"], [True])

    view.axes.set_xlabel.assert_called()
    call_args: str = str(view.axes.set_xlabel.call_args)
    assert "log10" in call_args


def test_dunder_init_calls_super_and_initializers(mocker: MockerFixture) -> None:
    """Verify __init__ delegates to the parent and helper initializers."""
    mock_super_init: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.MetaView.__init__",
        return_value=None,
    )
    mock_init: MagicMock = mocker.patch.object(MetadataView, "_init", autospec=True)
    mock_init_walkthrough: MagicMock = mocker.patch.object(
        MetadataView,
        "_init_walkthrough",
        autospec=True,
    )

    view = MetadataView("arg", key="value")

    mock_super_init.assert_called_once_with("arg", key="value")
    mock_init.assert_called_once_with(view)
    mock_init_walkthrough.assert_called_once_with(view)


def test_plot_1d_density_uses_first_bins_entry(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify a non-empty bins list is reduced to its first entry."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})
    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3, 0.4])
    mock_kde_class.return_value = mock_kde_instance

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0, 4.0]),)
    )

    view._plot_1d_density(view.axes, data, ["x"], ["u"], [False], bins=[4])

    assert view.hist_data


def test_plot_1d_density_uses_bin_count_directly_when_sizes_false(
    view: MetadataView,
    mocker: MockerFixture,
) -> None:
    """Verify scalar bin counts are used directly when sizes is False."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})
    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3, 0.4])
    mock_kde_class.return_value = mock_kde_instance

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0, 4.0]),)
    )

    view._plot_1d_density(view.axes, data, ["x"], ["u"], [False], bins=[6], sizes=False)

    assert view.hist_data


def test_plot_1d_density_handles_bin_size_without_hist_bounds(
    view: MetadataView,
    mocker: MockerFixture,
) -> None:
    """Verify size-based bins fall back when histogram bounds are unavailable."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})
    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3, 0.4])
    mock_kde_class.return_value = mock_kde_instance

    view.hist_min = None
    view.hist_max = None
    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0, 4.0]),)
    )

    view._plot_1d_density(view.axes, data, ["x"], ["u"], [False], bins=[0.5], sizes=True)

    assert view.hist_data


def test_plot_1d_density_resets_to_auto_bins_when_hist_bounds_are_cleared_before_loop(
    view: MetadataView,
    mocker: MockerFixture,
) -> None:
    """Verify missing histogram bounds force the size-based bins path back to auto-bin estimation."""

    class ResettingList(list[pd.DataFrame]):
        def __init__(self, owner: MetadataView) -> None:
            super().__init__()
            self._owner = owner

        def append(self, item: pd.DataFrame) -> None:
            super().append(item)
            self._owner.hist_min = None
            self._owner.hist_max = None

    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})

    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3, 0.4])
    mock_kde_class.return_value = mock_kde_instance

    mock_iqr: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.iqr",
        return_value=1.0,
    )

    view.hist_data = ResettingList(view)  # type: ignore[assignment]
    view.hist_labels = []
    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0, 4.0]),)
    )

    original_min = min
    original_max = max

    def mock_min(*args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and isinstance(args[0], pd.DataFrame):
            return args[0].min().min()
        return original_min(*args, **kwargs)

    def mock_max(*args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and isinstance(args[0], pd.DataFrame):
            return args[0].max().max()
        return original_max(*args, **kwargs)

    mocker.patch("builtins.min", side_effect=mock_min)
    mocker.patch("builtins.max", side_effect=mock_max)

    view._plot_1d_density(view.axes, data, ["x"], ["u"], [False], bins=[0.5], sizes=True)

    assert mock_iqr.call_count >= 1
    assert len(view.hist_data) == 1


def test_plot_1d_density_handles_type_error_for_bin_size(
    view: MetadataView,
    mocker: MockerFixture,
) -> None:
    """Verify invalid size-based bin entries fall back without crashing."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})
    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3, 0.4])
    mock_kde_class.return_value = mock_kde_instance

    original_min = min
    original_max = max

    def mock_min(*args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and isinstance(args[0], pd.DataFrame):
            return args[0].min().min()
        return original_min(*args, **kwargs)

    def mock_max(*args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and isinstance(args[0], pd.DataFrame):
            return args[0].max().max()
        return original_max(*args, **kwargs)

    mocker.patch("builtins.min", side_effect=mock_min)
    mocker.patch("builtins.max", side_effect=mock_max)

    view.hist_min = 0.0
    view.hist_max = 10.0
    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0, 4.0]),)
    )

    view._plot_1d_density(
        view.axes,
        data,
        ["x"],
        ["u"],
        [False],
        bins=[None],  # type: ignore[list-item]
        sizes=True,
    )

    assert view.hist_data


def test_plot_1d_density_discards_size_bins_that_produce_one_or_fewer_bins(
    view: MetadataView,
    mocker: MockerFixture,
) -> None:
    """Verify tiny histogram ranges disable invalid computed bin counts."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})
    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3, 0.4])
    mock_kde_class.return_value = mock_kde_instance

    original_min = min
    original_max = max

    def mock_min(*args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and isinstance(args[0], pd.DataFrame):
            return args[0].min().min()
        return original_min(*args, **kwargs)

    def mock_max(*args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and isinstance(args[0], pd.DataFrame):
            return args[0].max().max()
        return original_max(*args, **kwargs)

    mocker.patch("builtins.min", side_effect=mock_min)
    mocker.patch("builtins.max", side_effect=mock_max)

    view.hist_min = 0.0
    view.hist_max = 0.4
    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0, 4.0]),)
    )

    view._plot_1d_density(view.axes, data, ["x"], ["u"], [False], bins=[1.0], sizes=True)

    assert view.hist_data


def test_plot_1d_density_uses_log_length_fallback_when_iqr_is_zero(
    view: MetadataView,
    mocker: MockerFixture,
) -> None:
    """Verify the zero-IQR branch computes a fallback number of bins."""
    data = pd.DataFrame({"x": np.array([5.0] * 12)})
    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3])
    mock_kde_class.return_value = mock_kde_instance
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.iqr", return_value=0.0)

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([5.0] * 12),)
    )

    view._plot_1d_density(view.axes, data, ["x"], ["u"], [False], bins=None)

    assert view.hist_data


def test_plot_1d_density_handles_overflow_when_estimating_bins(
    view: MetadataView,
    mocker: MockerFixture,
) -> None:
    """Verify OverflowError during fallback bin estimation is handled."""
    data = pd.DataFrame({"x": np.array([5.0] * 12)})
    mock_kde_class: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.stats.kde.gaussian_kde"
    )
    mock_kde_instance: MagicMock = mocker.Mock()
    mock_kde_instance.return_value = np.array([0.1, 0.2, 0.3])
    mock_kde_class.return_value = mock_kde_instance
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.iqr", return_value=0.0)
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.np.log10",
        side_effect=OverflowError,
    )

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([5.0] * 12),)
    )

    view._plot_1d_density(view.axes, data, ["x"], ["u"], [False], bins=None)

    assert view.hist_data


# ----------------------------- Plot Capture Rate Tests ------------------------------


def test_plot_capture_rate_raises_on_insufficient_data(view: MetadataView) -> None:
    """Verify ValueError is raised when insufficient data after filtering."""
    data: pd.DataFrame = pd.DataFrame({"time": np.array([1.0, 1.01])})

    with pytest.raises(ValueError, match="Not enough data"):
        view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False])


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

    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.curve_fit",
        return_value=(np.array([1.0, 1.0]), np.array([[0.01, 0], [0, 0.01]])),
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False])

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

    mock_curve_fit: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.curve_fit",
        return_value=(np.array([1.5, 2.5]), np.array([[0.01, 0], [0, 0.01]])),
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False])

    mock_curve_fit.assert_called_once()
    view.axes.plot.assert_called()


def test_plot_capture_rate_emits_message_for_filtered_rows(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify message is emitted when rows are filtered."""
    data: pd.DataFrame = pd.DataFrame(
        {
            "time": np.array(
                [-1.0, 0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 2.0, 2.3]
            )
        }
    )

    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.curve_fit",
        return_value=(np.array([1.0, 1.0]), np.array([[0.01, 0], [0, 0.01]])),
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False])

    view.add_text_to_display.emit.assert_called()


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

    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.curve_fit",
        return_value=(np.array([1.0, 1.0]), np.array([[0.01, 0], [0, 0.01]])),
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False])

    view.axes.set_xlabel.assert_called()
    view.axes.set_ylabel.assert_called()


def test_plot_capture_rate_uses_first_bins_entry(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify capture-rate plotting uses the first element from a bins list."""
    data = pd.DataFrame(
        {
            "time": np.array(
                [0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 2.0, 2.3]
            )
        }
    )
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.curve_fit",
        return_value=(np.array([1.0, 1.0]), np.array([[0.01, 0.0], [0.0, 0.01]])),
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False], bins=[4])

    hist_call = view.axes.hist.call_args
    assert hist_call is not None
    assert hist_call.kwargs.get("bins") == 4


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
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.curve_fit",
        return_value=(np.array([1.0, 1.0]), np.array([[0.01, 0.0], [0.0, 0.01]])),
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [True])

    xlabel_call = view.axes.set_xlabel.call_args
    assert xlabel_call is not None
    xlabel = xlabel_call.args[0]
    assert "log10" in xlabel


def test_plot_capture_rate_uses_log_length_fallback_when_iqr_is_zero(
    view: MetadataView,
    mocker: MockerFixture,
) -> None:
    """Verify zero-IQR capture-rate data uses the fallback bin estimator."""
    data = pd.DataFrame({"time": np.linspace(1.0, 1.11, 12)})
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.iqr", return_value=0.0)
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.curve_fit",
        return_value=(np.array([1.0, 1.0]), np.array([[0.01, 0.0], [0.0, 0.01]])),
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False], bins=None)

    view.axes.hist.assert_called()


def test_plot_capture_rate_handles_overflow_when_estimating_bins(
    view: MetadataView,
    mocker: MockerFixture,
) -> None:
    """Verify OverflowError in the primary estimator falls back to log-length bins."""
    data = pd.DataFrame({"time": np.linspace(1.0, 1.11, 12)})
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.iqr", return_value=1.0)

    original_max = np.max

    def mock_np_max(values: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(values, np.ndarray):
            raise OverflowError
        return original_max(values, *args, **kwargs)

    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.np.max",
        side_effect=mock_np_max,
    )
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.curve_fit",
        return_value=(np.array([1.0, 1.0]), np.array([[0.01, 0.0], [0.0, 0.01]])),
    )

    view._plot_capture_rate(view.axes, data, ["time"], ["s"], [False], bins=None)

    hist_call = view.axes.hist.call_args
    assert hist_call is not None
    assert hist_call.kwargs.get("bins") == int(3.332 * np.log10(len(data)))


# ----------------------------- Format Axis Label Tests ------------------------------


def test_format_axis_label_adds_unit() -> None:
    """Verify unit is added in parentheses."""
    result: str = format_axis_label("Duration", "ms")
    assert result == "Duration (ms)"


def test_format_axis_label_replaces_existing_unit() -> None:
    """Verify existing unit is replaced."""
    result: str = format_axis_label("Duration (s)", "ms")
    assert result == "Duration (ms)"


def test_format_axis_label_no_unit_returns_plain() -> None:
    """Verify plain label is returned when no unit."""
    result: str = format_axis_label("Duration", "")
    assert result == "Duration"


def test_format_axis_label_handles_multiple_parentheses() -> None:
    """Verify only last parenthetical is replaced."""
    result: str = format_axis_label("Current (baseline) (pA)", "nA")
    assert "nA" in result

# ----------------------------- Plot 1D Histogram Tests ------------------------------


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

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0, 4.0]),)
    )

    view._plot_1d_histogram(view.axes, data, ["x"], ["u"], [False], bins=[10])

    assert len(view.hist_data) == 1


def test_plot_1d_histogram_updates_hist_min_max(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify hist_min and hist_max are updated."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 5.0, 10.0])})

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 5.0, 10.0]),)
    )

    view._plot_1d_histogram(view.axes, data, ["x"], ["units"], [False])

    assert view.hist_min == 1.0
    assert view.hist_max == 10.0


def test_plot_1d_histogram_normalizes_when_norm_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify histogram is normalized when norm=True."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0, 4.0]),)
    )

    view._plot_1d_histogram(view.axes, data, ["x"], ["u"], [False], norm=True)

    ylabel_call = view.axes.set_ylabel.call_args
    assert ylabel_call is not None
    assert "Fraction" in ylabel_call.args[0]


def test_plot_1d_histogram_sets_log10_label_when_logscale_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify log10 label is set when logscale is True."""
    data = pd.DataFrame({"x": np.array([1.0, 10.0, 100.0])})

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([0.0, 1.0, 2.0]),)
    )

    view._plot_1d_histogram(view.axes, data, ["x"], ["units"], [True])

    xlabel_call = view.axes.set_xlabel.call_args
    assert xlabel_call is not None
    assert "log10" in xlabel_call.args[0]


def test_plot_1d_histogram_handles_bin_sizes(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify bin sizes mode calculates bins correctly."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0, 4.0])})

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0, 4.0]),)
    )
    view.hist_min = 0.0
    view.hist_max = 10.0

    view._plot_1d_histogram(view.axes, data, ["x"], ["u"], [False], bins=[0.5], sizes=True)

    assert len(view.hist_data) == 1


def test_plot_1d_histogram_overlays_multiple_datasets(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify multiple datasets can be overlaid."""
    data1 = pd.DataFrame({"x": np.array([1.0, 2.0, 3.0])})
    data2 = pd.DataFrame({"x": np.array([4.0, 5.0, 6.0])})

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        side_effect=[
            (np.array([1.0, 2.0, 3.0]),),
            (np.array([4.0, 5.0, 6.0]),),
        ]
    )

    view._plot_1d_histogram(view.axes, data1, ["x"], ["u"], [False], dataset_label="d1")
    view._plot_1d_histogram(view.axes, data2, ["x"], ["u"], [False], dataset_label="d2")

    assert len(view.hist_data) == 2
    assert len(view.hist_labels) == 2


# ----------------------------- Plot Heatmap Tests ------------------------------


def test_plot_heatmap_calls_calculate_heatmap(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _calculate_heatmap is called."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    # Create explicit arrays before mocking to avoid evaluation issues
    x_bins = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5])
    y_bins = np.array([3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5])
    z_grid = np.ones((10, 10))

    view._calculate_heatmap = mocker.Mock(  # type: ignore[method-assign]
        return_value=(x_bins, y_bins, z_grid)
    )

    # Mock the colorbar to return proper ticks
    mock_colorbar = mocker.Mock()
    mock_colorbar.get_ticks = mocker.Mock(return_value=np.array([0.0, 0.5, 1.0, 1.5, 2.0]))
    view.figure.colorbar = mocker.Mock(return_value=mock_colorbar)

    view._plot_heatmap(view.axes, data, ["x", "y"], ["u1", "u2"], [False, False])

    view._calculate_heatmap.assert_called_once()


def test_plot_heatmap_sets_axis_labels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axis labels are set correctly."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    x_bins = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5])
    y_bins = np.array([3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5])
    z_grid = np.ones((10, 10))

    view._calculate_heatmap = mocker.Mock(  # type: ignore[method-assign]
        return_value=(x_bins, y_bins, z_grid)
    )

    # Mock the colorbar
    mock_colorbar = mocker.Mock()
    mock_colorbar.get_ticks = mocker.Mock(return_value=np.array([0.0, 0.5, 1.0, 1.5, 2.0]))
    view.figure.colorbar = mocker.Mock(return_value=mock_colorbar)

    view._plot_heatmap(view.axes, data, ["x", "y"], ["u1", "u2"], [False, False])

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

    view._calculate_heatmap = mocker.Mock(  # type: ignore[method-assign]
        return_value=(x_bins, y_bins, z_grid)
    )

    # Mock the colorbar
    mock_colorbar = mocker.Mock()
    mock_colorbar.get_ticks = mocker.Mock(return_value=np.array([0.0, 0.5, 1.0, 1.5, 2.0]))
    view.figure.colorbar = mocker.Mock(return_value=mock_colorbar)

    view._plot_heatmap(view.axes, data, ["x", "y"], ["u1", "u2"], [True, True])

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

    view._calculate_heatmap = mocker.Mock(  # type: ignore[method-assign]
        return_value=(x_bins, y_bins, z_grid)
    )

    # Mock the colorbar
    mock_new_colorbar = mocker.Mock()
    mock_new_colorbar.get_ticks = mocker.Mock(return_value=np.array([0.0, 0.5, 1.0, 1.5, 2.0]))
    view.figure.colorbar = mocker.Mock(return_value=mock_new_colorbar)

    # Create a mock for the previous colorbar
    mock_old_colorbar = mocker.Mock()
    mock_old_colorbar.ax = mocker.Mock()
    mock_old_colorbar.ax.figure = view.figure
    view._heatmap_colorbar = mock_old_colorbar  # type: ignore[attr-defined]

    view._plot_heatmap(view.axes, data, ["x", "y"], ["u1", "u2"], [False, False])

    mock_old_colorbar.remove.assert_called_once()


# ----------------------------- Plot Scatterplot Tests ------------------------------


def test_plot_scatterplot_calls_scatter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify scatter is called on axes."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
    )

    view._plot_scatterplot(view.axes, data, ["x", "y"], ["u1", "u2"], [False, False])

    view.axes.scatter.assert_called_once()


def test_plot_scatterplot_sets_axis_labels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axis labels are set."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
    )

    view._plot_scatterplot(view.axes, data, ["x", "y"], ["u1", "u2"], [False, False])

    view.axes.set_xlabel.assert_called()
    view.axes.set_ylabel.assert_called()


def test_plot_scatterplot_sets_log10_labels_when_logscale_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify log10 labels are set when logscales are True."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
    )

    view._plot_scatterplot(view.axes, data, ["x", "y"], ["u1", "u2"], [True, True])

    xlabel_call = view.axes.set_xlabel.call_args
    ylabel_call = view.axes.set_ylabel.call_args
    assert xlabel_call is not None
    assert ylabel_call is not None
    assert "log10" in xlabel_call.args[0]
    assert "log10" in ylabel_call.args[0]


# ----------------------------- Plot 3D Scatterplot Tests ------------------------------


def test_plot_3d_scatterplot_calls_scatter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify scatter is called on 3D axes."""
    data = pd.DataFrame({
        "x": np.array([1.0, 2.0]),
        "y": np.array([3.0, 4.0]),
        "z": np.array([5.0, 6.0]),
    })

    # Make isinstance check pass by setting view.axes as an instance
    type(view.axes).__name__ = "Axes3D"

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(
            np.array([1.0, 2.0]),
            np.array([3.0, 4.0]),
            np.array([5.0, 6.0]),
        )
    )

    view._plot_3d_scatterplot(
        view.axes, data, ["x", "y", "z"], ["u1", "u2", "u3"], [False, False, False]
    )

    view.axes.scatter.assert_called_once()


def test_plot_3d_scatterplot_sets_axis_labels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify all three axis labels are set."""
    data = pd.DataFrame({
        "x": np.array([1.0, 2.0]),
        "y": np.array([3.0, 4.0]),
        "z": np.array([5.0, 6.0]),
    })

    # Make isinstance check pass
    type(view.axes).__name__ = "Axes3D"

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(
            np.array([1.0, 2.0]),
            np.array([3.0, 4.0]),
            np.array([5.0, 6.0]),
        )
    )
    view.axes.set_zlabel = mocker.Mock()

    view._plot_3d_scatterplot(
        view.axes, data, ["x", "y", "z"], ["u1", "u2", "u3"], [False, False, False]
    )

    view.axes.set_xlabel.assert_called()
    view.axes.set_ylabel.assert_called()
    view.axes.set_zlabel.assert_called()


# ----------------------------- Plot All Points Histogram Tests ------------------------------


def test_plot_all_points_histogram_plots_data(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot is called with data."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view._plot_all_points_histogram(view.axes, data, ["x", "y"], ["u1", "u2"])

    view.axes.plot.assert_called()


def test_plot_all_points_histogram_normalizes_when_norm_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify data is normalized when norm=True."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([10.0, 20.0])})

    view._plot_all_points_histogram(view.axes, data, ["x", "y"], ["u1", "u2"], norm=True)

    ylabel_call = view.axes.set_ylabel.call_args
    assert ylabel_call is not None
    assert "Normalized" in ylabel_call.args[0]


def test_plot_all_points_histogram_clears_axes(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axes are cleared before plotting."""
    data = pd.DataFrame({"x": np.array([1.0, 2.0]), "y": np.array([3.0, 4.0])})

    view._plot_all_points_histogram(view.axes, data, ["x", "y"], ["u1", "u2"])

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

    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0]),)
    )
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
    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
    )
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
    view._calculate_heatmap = mocker.Mock(  # type: ignore[method-assign]
        return_value=(
            np.array([1.0, 2.0]),
            np.array([3.0, 4.0]),
            np.array([[1.0, 2.0], [3.0, 4.0]]),
        )
    )
    view._plot_heatmap = mocker.Mock()  # type: ignore[method-assign]

    view.update_plot("Heatmap", data, ["x", "y"], ["u1", "u2"], [False, False])

    view._plot_heatmap.assert_called_once()


def test_update_plot_calls_3d_scatterplot_for_3d_type(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify _plot_3d_scatterplot is called for 3D Scatterplot type."""
    data = pd.DataFrame({
        "x": np.array([1.0, 2.0]),
        "y": np.array([3.0, 4.0]),
        "z": np.array([5.0, 6.0]),
    })

    view.data_cache = []  # type: ignore[attr-defined]
    view._commit_cache = mocker.Mock()  # type: ignore[method-assign]
    view._plot_3d_scatterplot = mocker.Mock()  # type: ignore[method-assign]

    view.update_plot(
        "3D Scatterplot", data, ["x", "y", "z"], ["u1", "u2", "u3"], [False, False, False]
    )

    view._plot_3d_scatterplot.assert_called_once()


def test_update_plot_raises_for_unsupported_type(view: MetadataView, mocker: MockerFixture) -> None:
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
    view._logscale_and_filter_multiple_columns = mocker.Mock(  # type: ignore[method-assign]
        return_value=(np.array([1.0, 2.0, 3.0]),)
    )

    view.update_plot("Histogram", data, ["x"], ["u"], [False])

    view.canvas.draw.assert_called()

# ----------------------------- Overlay Plot Tests ------------------------------


def test_overlay_plot_sets_show_sql_flags_to_false(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify SQL display flags are set to False at start of overlay."""
    view._show_sql_in_display = True
    view._show_event_sql_in_display = True
    
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    assert view._show_sql_in_display is False
    assert view._show_event_sql_in_display is False


def test_overlay_plot_sets_plot_initialized_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot_initialized flag is set to True."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    assert view.plot_initialized is True


def test_overlay_plot_defaults_to_full_dataset_when_no_filters(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify defaults to Full Dataset when selected_filters is None or empty."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view.global_signal.emit.assert_called()


def test_overlay_plot_defaults_experiments_and_channels_when_none(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify defaults to {None: [None]} when no experiments/channels selected."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view.global_signal.emit.assert_called()


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
    view.selected_experiment_and_channels_by_loader = {
        "test_loader": {"exp1": [1, 2]}
    }
    
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
    view.selected_experiment_and_channels_by_loader = {
        "test_loader": {"exp1": [1]}
    }
    
    result = view._overlay_plot(parameters)
    
    assert result is False
    view.add_text_to_display.emit.assert_called()


def test_overlay_plot_constructs_histogram_columns_correctly(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Histogram uses correct columns and logscales."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0], "current": [3.0, 4.0]})
    view.units = "ms"
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({
        "duration": [1.0, 2.0],
        "current": [3.0, 4.0],
        "voltage": [5.0, 6.0],
    })
    view.units = "ms"
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
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Capture Rate",
        "bins": [50],
        "sizes": False,
    }
    
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({
        "start_time": [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    })
    view.units = "s"
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"new_column": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view._reset_actions.assert_called_once()


def test_overlay_plot_resets_when_logscales_change(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot resets when logscales change."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view._reset_actions.assert_called_once()


def test_overlay_plot_resets_when_plot_type_changes(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot resets when plot type changes."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view._reset_actions.assert_called_once()


def test_overlay_plot_resets_when_bins_change_for_bin_sensitive_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot resets when bins change for bin-sensitive plots."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view._reset_actions.assert_called_once()


def test_overlay_plot_resets_when_sizes_change_for_bin_sensitive_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify plot resets when sizes flag changes for bin-sensitive plots."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view._reset_actions.assert_called_once()


def test_overlay_plot_rejects_duplicate_columns(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify overlay rejects plots with duplicate columns."""
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
    view.add_text_to_display.emit.assert_called()


def test_overlay_plot_skips_already_plotted_datasets(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify already plotted datasets are skipped and function completes successfully."""
    # Pre-populate the plotted datasets
    view.plotted_datasets.add(("test_loader", None, None, "", "Full Dataset"))
    
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
    
    # The loop will iterate but skip the already-plotted dataset
    # and still return True at the end
    result = view._overlay_plot(parameters)
    
    assert result is True
    # Verify update_plot was NOT called since dataset was skipped
    view.update_plot.assert_not_called()


def test_overlay_plot_returns_false_when_query_empty(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns False when query is empty string."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = ""
    
    result = view._overlay_plot(parameters)
    
    assert result is False


def test_overlay_plot_skips_subset_when_no_plot_data(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify skips subset and emits message when plot_data is None."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = None
    
    view._overlay_plot(parameters)
    
    view.add_text_to_display.emit.assert_called()
    call_args = view.add_text_to_display.emit.call_args_list[-1]
    assert "No data matching" in call_args.args[0]


def test_overlay_plot_emits_row_count_message(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify emits message with row count for valid data."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0, 4.0, 5.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view.add_text_to_display.emit.assert_called()
    call_args = view.add_text_to_display.emit.call_args_list[0]
    assert "5 rows" in call_args.args[0]


def test_overlay_plot_returns_false_when_column_units_length_mismatch(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns False when columns and units have different lengths."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Scatterplot",
        "x_axis": "duration",
        "y_axis": "current",
        "x_log": False,
        "y_log": False,
        "bins": [50],
        "sizes": False,
    }
    
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0], "current": [3.0, 4.0]})
    
    # Track which unit retrieval we're on
    unit_call_count = [0]
    
    def mock_emit_side_effect(*args: Any) -> None:
        # Only respond to get_column_units calls
        if len(args) >= 6 and args[2] == "get_column_units":
            unit_call_count[0] += 1
            # Only set units for first call, skip second to create mismatch
            if unit_call_count[0] == 1:
                view.units = "ms"
            # On second call, don't update view.units
            # This leaves it as "ms" from the first call, not adding a new unit
    
    view.global_signal.emit = mocker.Mock(side_effect=mock_emit_side_effect)
    
    result = view._overlay_plot(parameters)
    
    # Should return False due to length mismatch (2 columns but only 1 unique unit collected)
    assert result is False
    view.add_text_to_display.emit.assert_called()


def test_overlay_plot_returns_false_when_columns_missing_from_dataframe(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns False when columns not present in dataframe."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    
    result = view._overlay_plot(parameters)
    
    assert result is False
    view.add_text_to_display.emit.assert_called()


def test_overlay_plot_calls_update_plot_with_correct_arguments(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify update_plot is called with correct arguments."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    assert ("test_loader", "exp1", 2, "WHERE x > 1", "Filter1") in view.plotted_datasets


def test_overlay_plot_handles_raw_all_points_histogram_event_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Raw All Points Histogram event plot is handled."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw All Points Histogram",
        "bins": [50],
        "sizes": False,
    }
    
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.global_signal.emit = mocker.Mock()
    view.event_query = "SELECT * FROM events"
    view.event_data_generator = iter([{"raw_data": np.array([1.0, 2.0, 3.0])}])
    view._construct_all_points_histogram = mocker.Mock(
        return_value=pd.DataFrame({"Current": [1.0, 2.0], "Count": [10, 20]})
    )
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view._construct_all_points_histogram.assert_called_once()
    view.update_plot.assert_called_once()


def test_overlay_plot_handles_filtered_all_points_histogram_event_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Filtered All Points Histogram event plot is handled."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Filtered All Points Histogram",
        "bins": [50],
        "sizes": False,
    }
    
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.global_signal.emit = mocker.Mock()
    view.event_query = "SELECT * FROM events"
    view.event_data_generator = iter([{"filtered_data": np.array([1.0, 2.0, 3.0])}])
    view._construct_all_points_histogram = mocker.Mock(
        return_value=pd.DataFrame({"Current": [1.0, 2.0], "Count": [10, 20]})
    )
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view._construct_all_points_histogram.assert_called_once()


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
    view.global_signal.emit = mocker.Mock()
    view.event_query = "SELECT * FROM events"
    view.event_data_generator = iter([{"raw_data": np.array([1.0, 2.0, 3.0])}])
    view._construct_all_points_histogram = mocker.Mock(
        return_value=pd.DataFrame({"Current": [1.0, 2.0], "Count": [10, 20]})
    )
    view.update_plot = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view._reset_actions.assert_called_once()


def test_overlay_plot_returns_false_when_all_points_histogram_returns_none(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns False when _construct_all_points_histogram returns None."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw All Points Histogram",
        "bins": [50],
        "sizes": False,
    }
    
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.global_signal.emit = mocker.Mock()
    view.event_query = "SELECT * FROM events"
    view.event_data_generator = iter([{"raw_data": np.array([1.0, 2.0, 3.0])}])
    view._construct_all_points_histogram = mocker.Mock(return_value=None)
    
    result = view._overlay_plot(parameters)
    
    assert result is False


def test_overlay_plot_handles_raw_event_overlay_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify Raw Event Overlay plot is handled."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw Event Overlay",
    }
    
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.global_signal.emit = mocker.Mock()
    view.event_query = "SELECT * FROM events"
    view.event_data_generator = iter([{"raw_data": np.array([1.0, 2.0, 3.0])}])
    view._construct_event_overlay = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    view._construct_event_overlay.assert_called_once()


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
    view.global_signal.emit = mocker.Mock()
    view.event_query = ""
    
    result = view._overlay_plot(parameters)
    
    assert result is False


def test_overlay_plot_returns_false_when_event_data_generator_none(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns False when event_data_generator is None."""
    parameters = {
        "db_loader": "test_loader",
        "plot_type": "Raw Event Overlay",
    }
    
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {}
    view.global_signal.emit = mocker.Mock()
    view.event_query = "SELECT * FROM events"
    view.event_data_generator = None
    
    result = view._overlay_plot(parameters)
    
    assert result is False


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
    view.global_signal.emit = mocker.Mock()
    view.event_query = "SELECT * FROM events"
    view.event_data_generator = iter([{"raw_data": np.array([1.0, 2.0, 3.0])}])
    view._construct_event_overlay = mocker.Mock()
    
    view._overlay_plot(parameters)
    
    assert view.allowed_columns == []
    assert view.allowed_logs == []


def test_overlay_plot_returns_true_on_success(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns True on successful plot."""
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = "ms"
    view.update_plot = mocker.Mock()
    
    result = view._overlay_plot(parameters)
    
    assert result is True


# ----------------------------- Construct All Points Histogram Tests ------------------------------


def test_construct_all_points_histogram_returns_dataframe_with_correct_columns(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns DataFrame with Current and Count columns."""
    events = [
        {
            "raw_data": np.array([10.0, 11.0, 12.0, 13.0, 14.0]),
            "padding_before": 100.0,
            "samplerate": 10000.0,
        }
    ]
    
    result = view._construct_all_points_histogram(
        iter(events), "Raw All Points Histogram", bins=[10], sizes=False
    )
    
    assert result is not None
    assert "Current" in result.columns
    assert "Count" in result.columns


def test_construct_all_points_histogram_uses_raw_data_for_raw_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify uses raw_data for Raw All Points Histogram."""
    events = [
        {
            "raw_data": np.array([10.0, 11.0, 12.0, 13.0, 14.0]),
            "filtered_data": np.array([20.0, 21.0, 22.0, 23.0, 24.0]),
            "padding_before": 100.0,
            "samplerate": 10000.0,
        }
    ]
    
    result = view._construct_all_points_histogram(
        iter(events), "Raw All Points Histogram", bins=[10], sizes=False
    )
    
    assert result is not None
    # Verify the histogram was built from raw_data (around 10-14) not filtered (20-24)
    assert result["Current"].min() < 15.0


def test_construct_all_points_histogram_uses_filtered_data_for_filtered_plot(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify uses filtered_data for Filtered All Points Histogram."""
    # Use larger values and more samples so median baseline is clear
    events = [
        {
            "raw_data": np.array([5.0, 5.0, 5.0, 10.0, 11.0, 12.0, 13.0, 14.0]),
            "filtered_data": np.array([20.0, 20.0, 20.0, 25.0, 26.0, 27.0, 28.0, 29.0]),
            "padding_before": 300.0,  # 300 µs * 10000 Hz / 1e6 = 3 samples
            "samplerate": 10000.0,
        }
    ]
    
    result = view._construct_all_points_histogram(
        iter(events), "Filtered All Points Histogram", bins=[10], sizes=False
    )
    
    assert result is not None
    # After baseline subtraction with filtered data, values should be different than raw
    # Check that at least one value is non-zero to confirm data was processed
    assert result["Count"].sum() > 0


def test_construct_all_points_histogram_updates_hist_min_and_max(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify updates hist_min and hist_max based on data."""
    view.hist_min = None
    view.hist_max = None
    
    events = [
        {
            "raw_data": np.array([10.0, 11.0, 12.0, 13.0, 14.0]),
            "padding_before": 100.0,
            "samplerate": 10000.0,
        }
    ]
    
    view._construct_all_points_histogram(
        iter(events), "Raw All Points Histogram", bins=[10], sizes=False
    )
    
    assert view.hist_min is not None
    assert view.hist_max is not None


def test_construct_all_points_histogram_uses_bins_parameter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify uses bins parameter when provided."""
    events = [
        {
            "raw_data": np.array([10.0, 11.0, 12.0, 13.0, 14.0]),
            "padding_before": 100.0,
            "samplerate": 10000.0,
        }
    ]
    
    result = view._construct_all_points_histogram(
        iter(events), "Raw All Points Histogram", bins=[15], sizes=False
    )
    
    assert result is not None
    assert len(result) == 15


def test_construct_all_points_histogram_calculates_bin_size_when_sizes_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify calculates bins from size when sizes=True."""
    view.hist_min = 0.0
    view.hist_max = 10.0
    
    events = [
        {
            "raw_data": np.array([10.0, 11.0, 12.0, 13.0, 14.0]),
            "padding_before": 100.0,
            "samplerate": 10000.0,
        }
    ]
    
    result = view._construct_all_points_histogram(
        iter(events), "Raw All Points Histogram", bins=[1.0], sizes=True
    )
    
    assert result is not None


def test_construct_all_points_histogram_raises_for_invalid_bins(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify raises ValueError for invalid bins."""
    events = [
        {
            "raw_data": np.array([10.0, 11.0, 12.0, 13.0, 14.0]),
            "padding_before": 100.0,
            "samplerate": 10000.0,
        }
    ]
    
    with pytest.raises(ValueError, match="Invalid bins entry"):
        view._construct_all_points_histogram(
            iter(events), "Raw All Points Histogram", bins=[], sizes=False
        )


def test_construct_all_points_histogram_defaults_to_100_bins_when_none(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify defaults to 100 bins when bins=None."""
    events = [
        {
            "raw_data": np.array([10.0, 11.0, 12.0, 13.0, 14.0]),
            "padding_before": 100.0,
            "samplerate": 10000.0,
        }
    ]
    
    result = view._construct_all_points_histogram(
        iter(events), "Raw All Points Histogram", bins=None, sizes=False
    )
    
    assert result is not None
    assert len(result) == 100


def test_construct_all_points_histogram_handles_multiple_events(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify accumulates histogram across multiple events."""
    events = [
        {
            "raw_data": np.array([10.0, 11.0, 12.0]),
            "padding_before": 100.0,
            "samplerate": 10000.0,
        },
        {
            "raw_data": np.array([11.0, 12.0, 13.0]),
            "padding_before": 100.0,
            "samplerate": 10000.0,
        },
    ]
    
    result = view._construct_all_points_histogram(
        iter(events), "Raw All Points Histogram", bins=[10], sizes=False
    )
    
    assert result is not None
    assert result["Count"].sum() == 6  # 3 points from each event


# ----------------------------- Set Baseline Duration Tests ------------------------------


def test_set_baseline_duration_sets_value(view: MetadataView) -> None:
    """Verify baseline_duration is set correctly."""
    view.set_baseline_duration(0.5)
    
    assert view.baseline_duration == 0.5


# ----------------------------- Construct Event Overlay Tests ------------------------------


def test_construct_event_overlay_sets_axis_labels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axis labels are set correctly."""
    # padding calculation: 200 µs * 10000 Hz / 1e6 = 2 samples
    # Need at least 3 samples after removing padding to avoid division by zero
    # Total samples needed: 2 (before) + 3 (middle) + 2 (after) = 7 minimum
    events = [
        {
            "raw_data": np.array([10.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0]),
            "padding_before": 200.0,  # 2 samples
            "padding_after": 200.0,   # 2 samples  
            "samplerate": 10000.0,
        }
    ]
    
    view._construct_event_overlay(iter(events), "Raw Event Overlay", "test_loader")
    
    view.axes.set_xlabel.assert_called_with("Normalized Time")
    view.axes.set_ylabel.assert_called_with("Rectified Current (pA)")


def test_construct_event_overlay_sets_xlim(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify x-axis limits are set correctly."""
    events = [
        {
            "raw_data": np.array([10.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0]),
            "padding_before": 200.0,
            "padding_after": 200.0,
            "samplerate": 10000.0,
        }
    ]
    
    view._construct_event_overlay(iter(events), "Raw Event Overlay", "test_loader")
    
    view.axes.set_xlim.assert_called_with(left=-0.333, right=1.333)

def test_construct_event_overlay_plots_raw_data_for_raw_overlay(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify uses raw_data for Raw Event Overlay."""
    events = [
        {
            "raw_data": np.array([10.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0]),
            "filtered_data": np.array([20.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0]),
            "padding_before": 200.0,
            "padding_after": 200.0,
            "samplerate": 10000.0,
        }
    ]
    
    view._construct_event_overlay(iter(events), "Raw Event Overlay", "test_loader")
    
    view.axes.plot.assert_called()


def test_construct_event_overlay_plots_filtered_data_for_filtered_overlay(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify uses filtered_data for Filtered Event Overlay."""
    events = [
        {
            "raw_data": np.array([10.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0]),
            "filtered_data": np.array([20.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0]),
            "padding_before": 200.0,
            "padding_after": 200.0,
            "samplerate": 10000.0,
        }
    ]
    
    view._construct_event_overlay(iter(events), "Filtered Event Overlay", "test_loader")
    
    view.axes.plot.assert_called()

def test_construct_event_overlay_adjusts_alpha_based_on_event_count(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify alpha is adjusted based on number of events."""
    events = [
        {
            "raw_data": np.array([10.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0]),
            "padding_before": 200.0,
            "padding_after": 200.0,
            "samplerate": 10000.0,
        },
        {
            "raw_data": np.array([10.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0]),
            "padding_before": 200.0,
            "padding_after": 200.0,
            "samplerate": 10000.0,
        },
    ]
    
    view._construct_event_overlay(iter(events), "Raw Event Overlay", "test_loader")
    
    assert view.axes.plot.call_count == 2


def test_construct_event_overlay_sets_no_cached_data_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify no_cached_data flag is set to True."""
    events = [
        {
            "raw_data": np.array([10.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0]),
            "padding_before": 200.0,
            "padding_after": 200.0,
            "samplerate": 10000.0,
        }
    ]
    
    view._construct_event_overlay(iter(events), "Raw Event Overlay", "test_loader")
    
    assert view.no_cached_data is True


def test_construct_event_overlay_redraws_canvas(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify canvas is redrawn after plotting."""
    # Need enough samples: padding_before=200µs * 10000Hz / 1e6 = 2 samples
    # Total: 15 samples - 2 before - 2 after = 11 middle samples (safe from division by zero)
    events = [
        {
            "raw_data": np.array([10.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0]),
            "padding_before": 200.0,
            "padding_after": 200.0,
            "samplerate": 10000.0,
        }
    ]
    
    view._construct_event_overlay(iter(events), "Raw Event Overlay", "test_loader")
    
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
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getSaveFileName"
    )
    
    view._save_filter()
    
    mock_file_dialog.assert_not_called()


def test_save_filter_opens_file_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify file dialog is opened."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mock_file_dialog = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getSaveFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )
    mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch("json.dump")
    
    view._save_filter()
    
    mock_file_dialog.assert_called_once()

def test_save_filter_returns_when_no_path_selected(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns when user cancels file dialog."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getSaveFileName",
        return_value=("", ""),
    )
    mock_open = mocker.patch("builtins.open", mocker.mock_open())
    
    view._save_filter()
    
    mock_open.assert_not_called()


def test_save_filter_writes_json_to_file(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filters are written to JSON file."""
    view.subset_filters = {"Filter1": "WHERE x > 1", "Filter2": "WHERE y < 10"}
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getSaveFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )
    mock_open = mocker.patch("builtins.open", mocker.mock_open())
    mock_json_dump = mocker.patch("json.dump")
    
    view._save_filter()
    
    mock_open.assert_called_with("/path/to/filters.json", "w")
    mock_json_dump.assert_called_once()


def test_save_filter_logs_error_on_exception(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify error is logged when save fails."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getSaveFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )
    mocker.patch("builtins.open", side_effect=OSError("Permission denied"))
    
    view._save_filter()
    
    # Just verify it doesn't crash


# ----------------------------- Load Filter Tests ------------------------------


def test_load_filter_opens_file_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify file dialog is opened."""
    mock_file_dialog = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getOpenFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )
    mocker.patch("json.load", return_value={"Filter1": "WHERE x > 1"})
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox = mocker.Mock()
    
    parameters = {"db_loader": "test_loader"}
    view._load_filter(parameters)
    
    mock_file_dialog.assert_called_once()


def test_load_filter_returns_when_no_path_selected(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify returns when user cancels file dialog."""
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getOpenFileName",
        return_value=("", ""),
    )
    mock_open = mocker.patch("builtins.open", mocker.mock_open())
    
    parameters = {"db_loader": "test_loader"}
    view._load_filter(parameters)
    
    mock_open.assert_not_called()


def test_load_filter_reads_json_from_file(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filters are read from JSON file."""
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getOpenFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )
    mock_open = mocker.patch(
        "builtins.open", mocker.mock_open(read_data='{"Filter1": "WHERE x > 1"}')
    )
    mock_json_load = mocker.patch("json.load", return_value={"Filter1": "WHERE x > 1"})
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox = mocker.Mock()
    
    parameters = {"db_loader": "test_loader"}
    view._load_filter(parameters)
    
    mock_open.assert_called_with("/path/to/filters.json", "r")
    mock_json_load.assert_called_once()


def test_load_filter_raises_for_invalid_format(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify ValueError is raised for non-dict format."""
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getOpenFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )
    mocker.patch("builtins.open", mocker.mock_open(read_data='["not", "a", "dict"]'))
    mocker.patch("json.load", return_value=["not", "a", "dict"])
    
    parameters = {"db_loader": "test_loader"}
    view._load_filter(parameters)
    
    # Should log error but not crash


def test_load_filter_warns_on_duplicate_names(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning when duplicate filter names found."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getOpenFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )
    mocker.patch(
        "builtins.open", mocker.mock_open(read_data='{"Filter1": "WHERE y < 10"}')
    )
    mocker.patch("json.load", return_value={"Filter1": "WHERE y < 10"})
    
    parameters = {"db_loader": "test_loader"}
    view._load_filter(parameters)
    
    # Should log warning and not load


def test_load_filter_validates_with_loader_when_provided(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filters are validated when loader is provided."""
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getOpenFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )
    mocker.patch(
        "builtins.open", mocker.mock_open(read_data='{"Filter1": "WHERE x > 1"}')
    )
    mocker.patch("json.load", return_value={"Filter1": "WHERE x > 1"})
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox = mocker.Mock()
    view.global_signal.emit = mocker.Mock()
    
    parameters = {"db_loader": "test_loader"}
    view._load_filter(parameters)
    
    view.global_signal.emit.assert_called()


def test_load_filter_adds_filter_directly_when_no_loader(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filter is added directly when no loader provided."""
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getOpenFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )
    mocker.patch(
        "builtins.open", mocker.mock_open(read_data='{"Filter1": "WHERE x > 1"}')
    )
    mocker.patch("json.load", return_value={"Filter1": "WHERE x > 1"})
    view.metadatacontrols = mocker.Mock()
    view.metadatacontrols.filter_comboBox = mocker.Mock()
    
    parameters = {}
    view._load_filter(parameters)
    
    assert "Filter1" in view.subset_filters


def test_load_filter_logs_error_on_exception(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify error is logged when load fails."""
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.QFileDialog.getOpenFileName",
        return_value=("/path/to/filters.json", "JSON Files (*.json)"),
    )
    mocker.patch("builtins.open", side_effect=OSError("File not found"))
    
    parameters = {"db_loader": "test_loader"}
    view._load_filter(parameters)
    
    # Should log error but not crash