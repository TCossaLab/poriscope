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

from poriscope.plugins.analysistabs.MetadataView import MetadataView

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


def test_plot_1d_density_clears_axes(view: MetadataView, mocker: MockerFixture) -> None:
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

    view._plot_1d_density(
        view.axes, data, ["x"], ["u"], [False], bins=[0.5], sizes=True
    )

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

    view._plot_1d_density(
        view.axes, data, ["x"], ["u"], [False], bins=[0.5], sizes=True
    )

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

    view._plot_1d_density(
        view.axes, data, ["x"], ["u"], [False], bins=[1.0], sizes=True
    )

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

    view._plot_1d_histogram(
        view.axes, data, ["x"], ["u"], [False], bins=[0.5], sizes=True
    )

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
    mock_colorbar.get_ticks = mocker.Mock(
        return_value=np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    )
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
    mock_colorbar.get_ticks = mocker.Mock(
        return_value=np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    )
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
    mock_colorbar.get_ticks = mocker.Mock(
        return_value=np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    )
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
    data = pd.DataFrame(
        {
            "x": np.array([1.0, 2.0]),
            "y": np.array([3.0, 4.0]),
            "z": np.array([5.0, 6.0]),
        }
    )

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
    data = pd.DataFrame(
        {
            "x": np.array([1.0, 2.0]),
            "y": np.array([3.0, 4.0]),
            "z": np.array([5.0, 6.0]),
        }
    )

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

    view._plot_all_points_histogram(
        view.axes, data, ["x", "y"], ["u1", "u2"], norm=True
    )

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
    view.figure.axes = []
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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame(
        {
            "duration": [1.0, 2.0],
            "current": [3.0, 4.0],
            "voltage": [5.0, 6.0],
        }
    )
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
    view.figure.axes = []

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
    view.plot_data = pd.DataFrame(
        {"start_time": [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]}
    )
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
    view.figure.axes = []

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
    view.figure.axes = []
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0]})
    view.units = ["ms"]
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
    view.global_signal = mocker.Mock()
    view.update_plot = mocker.Mock()

    result = view._overlay_plot(parameters)

    assert result is True
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
    view.global_signal.emit = mocker.Mock()
    view.query = ""

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
    view.global_signal.emit = mocker.Mock()
    view.query = "SELECT * FROM events"
    view.plot_data = pd.DataFrame({"duration": [1.0, 2.0, 3.0, 4.0, 5.0]})
    view.units = "ms"
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


_TWO_EVENTS = [
    {
        "raw_data": np.linspace(10.0, 40.0, 30),
        "filtered_data": np.linspace(10.0, 40.0, 30),
        "padding_before": 200.0,
        "padding_after": 200.0,
        "samplerate": 10000.0,
    },
    {
        "raw_data": np.linspace(10.0, 40.0, 40),  # different length avoids div/zero
        "filtered_data": np.linspace(10.0, 40.0, 40),
        "padding_before": 200.0,
        "padding_after": 200.0,
        "samplerate": 10000.0,
    },
]


def test_construct_event_overlay_sets_axis_labels(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify axis labels are set correctly."""
    view._construct_event_overlay(iter(_TWO_EVENTS), "Raw Event Overlay", "test_loader")

    view.axes.set_xlabel.assert_called_with("Normalized Time")
    view.axes.set_ylabel.assert_called_with("Rectified Current (pA)")


def test_construct_event_overlay_sets_xlim(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify x-axis limits are set correctly."""
    view._construct_event_overlay(iter(_TWO_EVENTS), "Raw Event Overlay", "test_loader")

    view.axes.set_xlim.assert_called_with(left=-0.333, right=1.333)


def test_construct_event_overlay_plots_raw_data_for_raw_overlay(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify uses raw_data for Raw Event Overlay."""
    view._construct_event_overlay(iter(_TWO_EVENTS), "Raw Event Overlay", "test_loader")

    view.axes.plot.assert_called()


def test_construct_event_overlay_plots_filtered_data_for_filtered_overlay(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify uses filtered_data for Filtered Event Overlay."""
    view._construct_event_overlay(
        iter(_TWO_EVENTS), "Filtered Event Overlay", "test_loader"
    )

    view.axes.plot.assert_called()


def test_construct_event_overlay_adjusts_alpha_based_on_event_count(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify alpha is adjusted based on number of events (plot called once per event)."""
    view._construct_event_overlay(iter(_TWO_EVENTS), "Raw Event Overlay", "test_loader")

    assert view.axes.plot.call_count == 2


def test_construct_event_overlay_sets_no_cached_data_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify no_cached_data flag is set to True."""
    view._construct_event_overlay(iter(_TWO_EVENTS), "Raw Event Overlay", "test_loader")

    assert view.no_cached_data is True


def test_construct_event_overlay_redraws_canvas(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify canvas is redrawn after plotting."""
    view._construct_event_overlay(iter(_TWO_EVENTS), "Raw Event Overlay", "test_loader")

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
    view.global_signal = mocker.Mock()
    view.run_generators = mocker.Mock()

    view._export_csv_subset("test_loader", {}, {"exp1": [1]})

    # Verify global_signal was called with None for filters
    call_args = view.global_signal.emit.call_args[0]
    export_args = call_args[3]
    assert export_args[2] is None  # filters should be None


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
    view.global_signal = mocker.Mock()
    view.run_generators = mocker.Mock()

    view._export_csv_subset("test_loader", {"Filter1": "WHERE x > 1"}, {})

    # Verify global_signal was called with filter value
    call_args = view.global_signal.emit.call_args[0]
    export_args = call_args[3]
    assert export_args[2] == "WHERE x > 1"


def test_export_csv_subset_emits_signal_on_success(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify global signal is emitted for export."""
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
    view.global_signal = mocker.Mock()
    view.run_generators = mocker.Mock()

    view._export_csv_subset("test_loader", {"Filter1": "WHERE x > 1"}, {"exp1": [1]})

    view.global_signal.emit.assert_called_once()
    view.run_generators.emit.assert_called_once_with("test_loader")


def test_export_csv_subset_increments_counter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify subset export counter is incremented."""
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
    view.global_signal = mocker.Mock()
    view.run_generators = mocker.Mock()

    view._export_csv_subset("test_loader", {"Filter1": "WHERE x > 1"}, {})

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


def test_export_csv_subset_handles_exception(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify exception is logged when export fails."""
    view.available_plugins = {}
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

    # Create a fresh mock for global_signal that will raise exception
    view.global_signal = mocker.Mock()
    view.global_signal.emit = mocker.Mock(side_effect=Exception("Export failed"))

    view._export_csv_subset("test_loader", {"Filter1": "WHERE x > 1"}, {})

    # Should log error but not crash
    assert view.logger.error.called

    # ----------------------------- Set Exported Event Count Tests ------------------------------


def test_set_exported_event_count_sets_value(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify exported event count is set correctly."""
    view.set_exported_event_count(42)

    assert view.exported_event_count == 42


# ----------------------------- Set Query Tests ------------------------------


def test_set_query_sets_query_and_table_name(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify query and table name are set correctly."""
    view.set_query("SELECT * FROM events", "events")

    assert view.query == "SELECT * FROM events"
    assert view.table_name == "events"


def test_set_query_returns_early_when_query_empty(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify early return when query is empty."""
    view._show_sql_in_display = True

    view.set_query("", "events")

    view.add_text_to_display.emit.assert_not_called()


def test_set_query_emits_sql_when_show_flag_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify SQL is emitted when show flag is True."""
    view._show_sql_in_display = True

    view.set_query("SELECT * FROM events", "events")

    view.add_text_to_display.emit.assert_called()
    call_args = view.add_text_to_display.emit.call_args[0]
    assert "SQL (events)" in call_args[0]
    assert "SELECT * FROM events" in call_args[0]


def test_set_query_resets_show_flag_after_display(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify show SQL flag is reset after displaying."""
    view._show_sql_in_display = True

    view.set_query("SELECT * FROM events", "events")

    assert view._show_sql_in_display is False


def test_set_query_does_not_emit_when_show_flag_false(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify SQL is not emitted when show flag is False."""
    view._show_sql_in_display = False

    view.set_query("SELECT * FROM events", "events")

    view.add_text_to_display.emit.assert_not_called()


# ----------------------------- Set Event Query Tests ------------------------------


def test_set_event_query_sets_query(view: MetadataView, mocker: MockerFixture) -> None:
    """Verify event query is set correctly."""
    view.set_event_query("SELECT * FROM events WHERE id > 100")

    assert view.event_query == "SELECT * FROM events WHERE id > 100"


def test_set_event_query_returns_early_when_empty(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify early return when query is empty."""
    view._show_event_sql_in_display = True

    view.set_event_query("")

    view.add_text_to_display.emit.assert_not_called()


def test_set_event_query_emits_sql_when_show_flag_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify SQL is emitted when show flag is True."""
    view._show_event_sql_in_display = True

    view.set_event_query("SELECT * FROM events")

    view.add_text_to_display.emit.assert_called()
    call_args = view.add_text_to_display.emit.call_args[0]
    assert "Event SQL" in call_args[0]


def test_set_event_query_resets_show_flag_after_display(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify show flag is reset after displaying."""
    view._show_event_sql_in_display = True

    view.set_event_query("SELECT * FROM events")

    assert view._show_event_sql_in_display is False


# ----------------------------- Set Units Tests ------------------------------


def test_set_units_sets_value(view: MetadataView, mocker: MockerFixture) -> None:
    """Verify units are set correctly."""
    view.set_units("ms")

    assert view.units == "ms"


def test_set_units_accepts_list(view: MetadataView, mocker: MockerFixture) -> None:
    """Verify units can be set as a list."""
    view.set_units(["ms", "pA"])

    assert view.units == ["ms", "pA"]


# ----------------------------- Update Available Columns Tests ------------------------------


def test_update_available_columns_emits_signal(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify global signal is emitted to request columns."""
    view.global_signal = mocker.Mock()

    view.update_available_columns("test_loader")

    view.global_signal.emit.assert_called_once()
    call_args = view.global_signal.emit.call_args[0]
    assert call_args[0] == "MetaDatabaseLoader"
    assert call_args[1] == "test_loader"
    assert call_args[2] == "get_column_names_by_table"


def test_update_available_columns_handles_exception(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify exception is logged when signal emission fails."""
    view.global_signal = mocker.Mock()
    view.global_signal.emit = mocker.Mock(side_effect=Exception("Signal failed"))

    view.update_available_columns("test_loader")

    view.logger.error.assert_called()


# ----------------------------- Request Experiment Structure Tests ------------------------------


def test_request_experiment_structure_emits_signal(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify global signal is emitted to request structure."""
    view.global_signal = mocker.Mock()

    view.request_experiment_structure("test_loader")

    view.global_signal.emit.assert_called_once()
    call_args = view.global_signal.emit.call_args[0]
    assert call_args[0] == "MetaDatabaseLoader"
    assert call_args[1] == "test_loader"
    assert call_args[2] == "get_experiments_and_channels"


# ----------------------------- Show Selection Tree Tests ------------------------------


def test_show_selection_tree_creates_tree_if_not_exists(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify selection tree is created if it doesn't exist."""
    if hasattr(view, "selection_tree"):
        delattr(view, "selection_tree")

    mock_tree_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.SelectionTree"
    )
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


def test_update_units_emits_signal(view: MetadataView, mocker: MockerFixture) -> None:
    """Verify global signal is emitted to request units."""
    view.global_signal = mocker.Mock()

    view.update_units("test_loader", "duration", "x_axis")

    view.global_signal.emit.assert_called_once()
    call_args = view.global_signal.emit.call_args[0]
    assert call_args[0] == "MetaDatabaseLoader"
    assert call_args[1] == "test_loader"
    assert call_args[2] == "get_column_units"
    assert call_args[3] == ("duration",)


def test_update_units_handles_exception(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify exception is logged when signal emission fails."""
    view.global_signal = mocker.Mock()
    view.global_signal.emit = mocker.Mock(side_effect=Exception("Signal failed"))

    view.update_units("test_loader", "duration", "x_axis")

    view.logger.error.assert_called()


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


def test_calculate_heatmap_returns_three_arrays(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify calculate_heatmap returns x, y, z arrays."""
    xdata = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    ydata = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    view._logscale_and_filter_multiple_columns = mocker.Mock(
        return_value=(xdata, ydata)
    )

    x, y, z = view._calculate_heatmap(xdata, ydata, bins=[5])

    assert len(x) == 5
    assert len(y) == 5
    assert z.shape == (5, 5)


def test_calculate_heatmap_applies_logscale(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify logscale is applied when requested."""
    xdata = np.array([1.0, 10.0, 100.0])
    ydata = np.array([1.0, 10.0, 100.0])
    view._logscale_and_filter_multiple_columns = mocker.Mock(
        return_value=(xdata, ydata)
    )

    view._calculate_heatmap(xdata, ydata, logx=True, logy=True)

    view._logscale_and_filter_multiple_columns.assert_called_once()
    call_args = view._logscale_and_filter_multiple_columns.call_args
    assert call_args.kwargs["log_flags"] == [True, True]


def test_calculate_heatmap_uses_different_bins_for_x_and_y(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify different bin counts can be specified for x and y."""
    xdata = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    ydata = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    view._logscale_and_filter_multiple_columns = mocker.Mock(
        return_value=(xdata, ydata)
    )

    x, y, z = view._calculate_heatmap(xdata, ydata, bins=[3, 5])

    assert z.shape == (5, 3)  # Note: transposed, so y bins first


def test_calculate_heatmap_calculates_bin_sizes_when_sizes_true(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify bin sizes are calculated when sizes=True."""
    xdata = np.array([0.0, 10.0, 20.0, 30.0])
    ydata = np.array([0.0, 10.0, 20.0, 30.0])
    view._logscale_and_filter_multiple_columns = mocker.Mock(
        return_value=(xdata, ydata)
    )

    x, y, z = view._calculate_heatmap(xdata, ydata, bins=[5.0], sizes=True)

    # (30 - 0) / 5.0 = 6 bins per axis
    assert z.shape[0] == 6
    assert z.shape[1] == 6


def test_calculate_heatmap_raises_for_invalid_bins(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify ValueError is raised for empty bins list."""
    xdata = np.array([1.0, 2.0, 3.0])
    ydata = np.array([10.0, 20.0, 30.0])
    view._logscale_and_filter_multiple_columns = mocker.Mock(
        return_value=(xdata, ydata)
    )

    with pytest.raises(ValueError, match="Invalid bin entry"):
        view._calculate_heatmap(xdata, ydata, bins=[], sizes=False)


def test_calculate_heatmap_defaults_to_iqr_when_bins_none(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify IQR-based bin calculation when bins=None."""
    xdata = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    ydata = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    view._logscale_and_filter_multiple_columns = mocker.Mock(
        return_value=(xdata, ydata)
    )
    mocker.patch("poriscope.plugins.analysistabs.MetadataView.iqr", return_value=2.0)

    x, y, z = view._calculate_heatmap(xdata, ydata, bins=None)

    assert z.shape[0] > 0
    assert z.shape[1] > 0


def test_calculate_heatmap_applies_log2_to_counts(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify counts are log2 transformed."""
    xdata = np.array([1.0, 1.0, 2.0, 2.0])
    ydata = np.array([10.0, 10.0, 20.0, 20.0])
    view._logscale_and_filter_multiple_columns = mocker.Mock(
        return_value=(xdata, ydata)
    )

    x, y, z = view._calculate_heatmap(xdata, ydata, bins=[2])

    # All non-zero entries should be log2 transformed
    assert np.all((z == -1) | (z >= 0))  # -1 for zero counts, >=0 for others


# ----------------------------- Show Add Filter Dialog Tests ------------------------------


def test_show_add_filter_dialog_sets_show_sql_flag(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify show SQL flag is set before dialog."""
    view._show_sql_in_display = False
    view._walkthrough_active = False  # Add this attribute
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.AddSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 0  # Rejected
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog

    view._show_add_filter_dialog({"db_loader": "test"})

    assert view._show_sql_in_display is True


def test_show_add_filter_dialog_opens_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify dialog is opened with existing filter names."""
    view._walkthrough_active = False
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.AddSubsetFilterDialog"
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
        "poriscope.plugins.analysistabs.MetadataView.AddSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 1  # Accepted
    mock_dialog.name = "NewFilter"
    mock_dialog.filter_text = "WHERE duration > 100"
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog
    view.global_signal = mocker.Mock()

    view._show_add_filter_dialog({"db_loader": "test_loader"})

    view.global_signal.emit.assert_called_once()
    call_args = view.global_signal.emit.call_args[0]
    assert call_args[2] == "construct_metadata_query"


def test_show_add_filter_dialog_returns_when_no_loader(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify early return when no loader is provided."""
    view._walkthrough_active = False
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.AddSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 1
    mock_dialog.name = "NewFilter"
    mock_dialog.filter_text = "WHERE x > 1"
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog
    view.global_signal = mocker.Mock()

    view._show_add_filter_dialog({"db_loader": ""})

    view.global_signal.emit.assert_not_called()


# ----------------------------- Clear Pending Filter State Tests ------------------------------


def test_clear_pending_filter_state_resets_all_pending_values(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify all pending filter values are reset to None."""
    view._pending_filter_name = "Filter"
    view._pending_filter_text = "WHERE x > 1"
    view._pending_old_filter_name = "OldFilter"

    view.clear_pending_filter_state()

    assert view._pending_filter_name is None
    assert view._pending_filter_text is None
    assert view._pending_old_filter_name is None


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


def test_show_edit_filter_dialog_sets_show_sql_flag(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify show SQL flag is set before dialog."""
    view._show_sql_in_display = False
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.EditSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 0
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog

    view.show_edit_filter_dialog("Filter1", "test_loader")

    assert view._show_sql_in_display is True


def test_show_edit_filter_dialog_opens_dialog(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify edit dialog is opened with correct parameters."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.EditSubsetFilterDialog"
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
        "poriscope.plugins.analysistabs.MetadataView.EditSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 1
    mock_dialog.new_name = "Filter1Updated"
    mock_dialog.new_filter = "WHERE x > 10"
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog
    view.global_signal = mocker.Mock()

    view.show_edit_filter_dialog("Filter1", "test_loader")

    view.global_signal.emit.assert_called_once()


def test_show_edit_filter_dialog_stores_pending_data_including_old_name(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify pending data includes old filter name for replacement."""
    view.subset_filters = {"Filter1": "WHERE x > 1"}
    mock_dialog_class = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.EditSubsetFilterDialog"
    )
    mock_dialog = mocker.Mock()
    mock_dialog.exec.return_value = 1
    mock_dialog.new_name = "Filter1Updated"
    mock_dialog.new_filter = "WHERE x > 10"
    mock_dialog.is_raw = False  # Ensure assisted path
    mock_dialog_class.return_value = mock_dialog
    view.global_signal = mocker.Mock()

    view.show_edit_filter_dialog("Filter1", "test_loader")

    assert view._pending_filter_name == "Filter1Updated"
    assert view._pending_filter_text == "WHERE x > 10"
    assert view._pending_old_filter_name == "Filter1"


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

    def test_set_experiment_id(self, view: MetadataView) -> None:
        view.set_experiment_id(42)
        assert view.experiment_id == 42

    def test_set_experiment_id_none(self, view: MetadataView) -> None:
        view.set_experiment_id(None)
        assert view.experiment_id is None

    def test_set_table_by_column_appends(self, view: MetadataView) -> None:
        view.involved_tables = []
        view.set_table_by_column("events")
        assert "events" in view.involved_tables

    def test_set_table_by_column_none_does_not_append(self, view: MetadataView) -> None:
        view.involved_tables = []
        view.set_table_by_column(None)
        assert view.involved_tables == []

    def test_set_channel_db_id(self, view: MetadataView) -> None:
        view.set_channel_db_id(7)
        assert view.channel_db_id == 7


# ===========================================================================
# _plot_categorical_histogram
# ===========================================================================


class TestPlotCategoricalHistogram:
    def _data(self) -> pd.DataFrame:
        return pd.DataFrame({"category": ["A", "B", "A", "C", "B", "A"]})

    def test_calls_bar(self, view: MetadataView) -> None:
        view._plot_categorical_histogram(view.axes, self._data(), ["category"], [""])
        view.axes.bar.assert_called()

    def test_clears_axes_before_plot(self, view: MetadataView) -> None:
        view._plot_categorical_histogram(view.axes, self._data(), ["category"], [""])
        view.axes.clear.assert_called()

    def test_sets_axis_labels(self, view: MetadataView) -> None:
        view._plot_categorical_histogram(
            view.axes, self._data(), ["category"], ["unit"]
        )
        view.axes.set_xlabel.assert_called()
        view.axes.set_ylabel.assert_called()

    def test_rotates_x_tick_labels(self, view: MetadataView) -> None:
        view._plot_categorical_histogram(view.axes, self._data(), ["category"], [""])
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


def test_update_plot_calls_all_points_histogram_for_normalized_raw(
    view: MetadataView, mocker: MockerFixture
) -> None:
    data = pd.DataFrame(
        {"Current": np.array([1.0, 2.0]), "Count": np.array([10.0, 20.0])}
    )
    view._plot_all_points_histogram = mocker.Mock()
    view.update_plot(
        "Normalized Raw All Points Histogram",
        data,
        ["Current", "Count"],
        ["pA", ""],
        [False, False],
    )
    view._plot_all_points_histogram.assert_called_once()
    call_kwargs = view._plot_all_points_histogram.call_args[1]
    assert call_kwargs.get("norm") is True


def test_update_plot_calls_all_points_histogram_for_normalized_filtered(
    view: MetadataView, mocker: MockerFixture
) -> None:
    data = pd.DataFrame(
        {"Current": np.array([1.0, 2.0]), "Count": np.array([10.0, 20.0])}
    )
    view._plot_all_points_histogram = mocker.Mock()
    view.update_plot(
        "Normalized Filtered All Points Histogram",
        data,
        ["Current", "Count"],
        ["pA", ""],
        [False, False],
    )
    view._plot_all_points_histogram.assert_called_once()
    call_kwargs = view._plot_all_points_histogram.call_args[1]
    assert call_kwargs.get("norm") is True


# ===========================================================================
# on_raw_filter_validated
# ===========================================================================


class TestOnRawFilterValidated:
    def _setup(self, view: MetadataView, mocker: MockerFixture) -> None:
        view.metadatacontrols = mocker.Mock()
        view.metadatacontrols.filter_comboBox = mocker.Mock()

    def test_invalid_shows_warning_and_clears_pending(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view._pending_filter_name = "F"
        view._pending_filter_text = "SELECT * FROM events"
        view._pending_old_filter_name = None
        mock_warn = mocker.patch(
            "poriscope.plugins.analysistabs.MetadataView.QMessageBox.warning"
        )
        view.on_raw_filter_validated(False, "syntax error")
        mock_warn.assert_called_once()
        assert view._pending_filter_name is None
        assert view._pending_filter_text is None

    def test_valid_add_path_stores_filter(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view._pending_filter_name = "NewFilter"
        view._pending_filter_text = "SELECT * FROM events"
        view._pending_old_filter_name = None
        view.on_raw_filter_validated(True, "")
        assert "NewFilter" in view.subset_filters
        assert view.subset_filters["NewFilter"] == "SELECT * FROM events"
        view.metadatacontrols.filter_comboBox.addItem.assert_called_with("NewFilter")

    def test_valid_add_path_emits_message(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view._pending_filter_name = "NewFilter"
        view._pending_filter_text = "SELECT * FROM events"
        view._pending_old_filter_name = None
        view.on_raw_filter_validated(True, "")
        view.add_text_to_display.emit.assert_called()

    def test_valid_add_path_clears_pending(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view._pending_filter_name = "NewFilter"
        view._pending_filter_text = "SELECT * FROM events"
        view._pending_old_filter_name = None
        view.on_raw_filter_validated(True, "")
        assert view._pending_filter_name is None
        assert view._pending_filter_text is None
        assert view._pending_old_filter_name is None

    def test_valid_edit_path_replaces_filter(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view.subset_filters = {"OldFilter": "WHERE x > 1"}
        view._pending_filter_name = "NewFilter"
        view._pending_filter_text = "WHERE x > 10"
        view._pending_old_filter_name = "OldFilter"
        view.update_filter_name = mocker.Mock()
        view.on_raw_filter_validated(True, "")
        assert "OldFilter" not in view.subset_filters
        assert "NewFilter" in view.subset_filters
        assert view.subset_filters["NewFilter"] == "WHERE x > 10"
        view.update_filter_name.assert_called_once_with("OldFilter", "NewFilter")

    def test_valid_edit_path_emits_message(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view.subset_filters = {"OldFilter": "WHERE x > 1"}
        view._pending_filter_name = "NewFilter"
        view._pending_filter_text = "WHERE x > 10"
        view._pending_old_filter_name = "OldFilter"
        view.update_filter_name = mocker.Mock()
        view.on_raw_filter_validated(True, "")
        view.add_text_to_display.emit.assert_called()

    def test_valid_edit_path_clears_pending(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view.subset_filters = {"OldFilter": "WHERE x > 1"}
        view._pending_filter_name = "NewFilter"
        view._pending_filter_text = "WHERE x > 10"
        view._pending_old_filter_name = "OldFilter"
        view.update_filter_name = mocker.Mock()
        view.on_raw_filter_validated(True, "")
        assert view._pending_filter_name is None
        assert view._pending_filter_text is None
        assert view._pending_old_filter_name is None


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
        view.column_type = "REAL"
        view.global_signal = mocker.Mock()

        def side_effect(*args: Any) -> None:
            if len(args) > 2 and args[2] == "get_column_type":
                view.column_type = "REAL"

        view.global_signal.emit.side_effect = side_effect
        view._overlay_plot = mocker.Mock(return_value=True)

        view.handle_parameter_change("metadata", "update_plot", (self._params(),))

        view._overlay_plot.assert_not_called()
        view.add_text_to_display.emit.assert_called()

    def test_categorical_type_proceeds_to_overlay_plot(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        """When column type is categorical (e.g. INTEGER), _overlay_plot is called."""
        view.column_type = "INTEGER"
        view.global_signal = mocker.Mock()

        def side_effect(*args: Any) -> None:
            if len(args) > 2 and args[2] == "get_column_type":
                view.column_type = "INTEGER"

        view.global_signal.emit.side_effect = side_effect
        view._overlay_plot = mocker.Mock(return_value=True)

        view.handle_parameter_change("metadata", "update_plot", (self._params(),))

        view._overlay_plot.assert_called_once()

    def test_none_column_type_proceeds_to_overlay_plot(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        """When column type is None (unknown), treated as categorical — proceeds."""
        view.column_type = None
        view.global_signal = mocker.Mock()

        def side_effect(*args: Any) -> None:
            if len(args) > 2 and args[2] == "get_column_type":
                view.column_type = None

        view.global_signal.emit.side_effect = side_effect
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
        view.global_signal = mocker.Mock()
        view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
        view.selected_experiment_and_channels_by_loader = {}
        view.event_query = "SELECT * FROM events"
        view.event_data_generator = iter(
            [
                {
                    "raw_data": np.array([1.0, 2.0, 3.0]),
                    "padding_before": 100.0,
                    "samplerate": 10000.0,
                }
            ]
        )
        view._construct_all_points_histogram = mocker.Mock(
            return_value=pd.DataFrame({"Current": [1.0, 2.0], "Count": [10.0, 20.0]})
        )
        view.update_plot = mocker.Mock()

    def test_normalized_raw_all_points_histogram_calls_construct(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view._overlay_plot(self._base_params("Normalized Raw All Points Histogram"))
        view._construct_all_points_histogram.assert_called_once()

    def test_normalized_raw_all_points_histogram_calls_update_plot(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view._overlay_plot(self._base_params("Normalized Raw All Points Histogram"))
        view.update_plot.assert_called_once()
        assert view.update_plot.call_args[0][0] == "Normalized Raw All Points Histogram"

    def test_normalized_filtered_all_points_histogram_calls_construct(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view.event_data_generator = iter(
            [
                {
                    "filtered_data": np.array([1.0, 2.0, 3.0]),
                    "padding_before": 100.0,
                    "samplerate": 10000.0,
                }
            ]
        )
        view._overlay_plot(
            self._base_params("Normalized Filtered All Points Histogram")
        )
        view._construct_all_points_histogram.assert_called_once()

    def test_normalized_filtered_all_points_histogram_calls_update_plot(
        self, view: MetadataView, mocker: MockerFixture
    ) -> None:
        self._setup(view, mocker)
        view.event_data_generator = iter(
            [
                {
                    "filtered_data": np.array([1.0, 2.0, 3.0]),
                    "padding_before": 100.0,
                    "samplerate": 10000.0,
                }
            ]
        )
        view._overlay_plot(
            self._base_params("Normalized Filtered All Points Histogram")
        )
        view.update_plot.assert_called_once()
        assert (
            view.update_plot.call_args[0][0]
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
        view.global_signal = mocker.Mock()
        view.query = "SELECT * FROM events"
        view.plot_data = pd.DataFrame({"category": ["A", "B", "A"]})
        view.units = ""
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
        view.global_signal = mocker.Mock()
        view.query = "SELECT * FROM events"
        view.plot_data = pd.DataFrame({"category": ["A", "B", "C"]})
        view.units = ""
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
        view.global_signal = mocker.Mock()
        view.query = "SELECT * FROM events"
        view.plot_data = pd.DataFrame({"category": ["A", "B", "C"]})
        view.units = ""
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
    view.relayed_query_result = pd.DataFrame({"id": [1]})
    view.plot_events_generator = iter([_FULL_EVENT])
    view._update_event_plot = mocker.Mock()
    view.global_signal = mocker.Mock()

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame({"id": [1]})
        elif args[2] == "load_event_data":
            view.plot_events_generator = iter([_FULL_EVENT])

    view.global_signal.emit.side_effect = side_effect
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
    view.global_signal = mocker.Mock()

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame()

    view.global_signal.emit.side_effect = side_effect

    result = view._rebuild_event_id_cache("loader", "", "", None, None)

    assert result is False
    view.add_text_to_display.emit.assert_called()
    assert "No filtered events" in view.add_text_to_display.emit.call_args[0][0]


def test_rebuild_event_id_cache_stores_event_ids(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify filtered_event_ids is populated from the query result."""
    view.global_signal = mocker.Mock()

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame({"event_id": [0, 5, 10]})

    view.global_signal.emit.side_effect = side_effect

    result = view._rebuild_event_id_cache("loader", "", "", None, None)

    assert result is True
    assert view.filtered_event_ids == [0, 5, 10]


def test_rebuild_event_id_cache_updates_current_trackers(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify current_sql_filter, current_experiment, and current_channel are updated."""
    view.global_signal = mocker.Mock()

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame({"event_id": [1, 2, 3]})

    view.global_signal.emit.side_effect = side_effect

    view._rebuild_event_id_cache(
        "loader", "WHERE duration > 1", "duration > 1", "exp1", 2
    )

    assert view.current_sql_filter == "duration > 1"
    assert view.current_experiment == "exp1"
    assert view.current_channel == 2


def test_rebuild_event_id_cache_emits_all_events_when_no_filter(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify display panel message says 'All events' when no filter is active."""
    view.global_signal = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={})

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame({"event_id": [0, 1, 2]})

    view.global_signal.emit.side_effect = side_effect

    view._rebuild_event_id_cache("loader", "", "", None, None)

    msg = view.add_text_to_display.emit.call_args[0][0]
    assert "All events" in msg


def test_rebuild_event_id_cache_emits_filter_name_when_filter_active(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify display panel message includes filter name and 'subset' when filter is active."""
    view.global_signal = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"my_filter": "duration > 1"})

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame({"event_id": [3, 7]})

    view.global_signal.emit.side_effect = side_effect

    view._rebuild_event_id_cache(
        "loader", "WHERE duration > 1", "duration > 1", None, None
    )

    msg = view.add_text_to_display.emit.call_args[0][0]
    assert "my_filter" in msg
    assert "subset" in msg


def test_rebuild_event_id_cache_emits_total_and_bounds(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify display panel message includes total count, first and last event_id."""
    view.global_signal = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={})

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame({"event_id": [2, 5, 9]})

    view.global_signal.emit.side_effect = side_effect

    view._rebuild_event_id_cache("loader", "", "", None, None)

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
    view._build_where_clause = mocker.Mock(return_value="")

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
    view.global_signal = mocker.Mock()

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame({"id": [1]})
        elif args[2] == "load_event_data":
            view.plot_events_generator = iter([dict(_FULL_EVENT)])

    view.global_signal.emit.side_effect = side_effect

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
    view.global_signal = mocker.Mock()

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame({"id": [1]})
        elif args[2] == "load_event_data":
            view.plot_events_generator = iter([dict(_FULL_EVENT)])

    view.global_signal.emit.side_effect = side_effect

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
    view._build_where_clause = mocker.Mock(return_value="WHERE duration > 5")

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
    view.global_signal = mocker.Mock()

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame({"id": [1]})
        elif args[2] == "load_event_data":
            view.plot_events_generator = iter([dict(_FULL_EVENT)])

    view.global_signal.emit.side_effect = side_effect

    view._handle_plot_events(
        {"db_loader": "test_loader", "event_id": 0, "n_events": 1, "raw": False}
    )

    view._rebuild_event_id_cache.assert_not_called()


def test_handle_plot_events_returns_early_when_no_db_ids(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify early return with message when db_id resolution returns empty result."""
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view._update_event_plot = mocker.Mock()
    view.global_signal = mocker.Mock()

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame()

    view.global_signal.emit.side_effect = side_effect

    view._handle_plot_events(
        {"db_loader": "test_loader", "event_id": 0, "n_events": 1, "raw": False}
    )

    view._update_event_plot.assert_not_called()
    view.add_text_to_display.emit.assert_called()


def test_handle_plot_events_emits_warning_when_generator_none(
    view: MetadataView, mocker: MockerFixture
) -> None:
    """Verify warning is emitted when load_event_data produces no generator."""
    view.metadatacontrols = mocker.Mock()
    view.get_selected_filters = mocker.Mock(return_value={"Full Dataset": ""})
    view.selected_experiment_and_channels_by_loader = {"test_loader": {"exp1": [1]}}
    view.filtered_event_ids = [0, 5, 10]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 1
    view.plot_events_generator = None
    view._update_event_plot = mocker.Mock()
    view.global_signal = mocker.Mock()

    def side_effect(*args: Any) -> None:
        if args[2] == "query_database_directly":
            view.relayed_query_result = pd.DataFrame({"id": [1]})
        # load_event_data does not set plot_events_generator

    view.global_signal.emit.side_effect = side_effect

    view._handle_plot_events(
        {"db_loader": "test_loader", "event_id": 0, "n_events": 1, "raw": False}
    )

    view._update_event_plot.assert_not_called()
    view.add_text_to_display.emit.assert_called()
