"""
Tests for poriscope.plugins.analysistabs.MetadataView.

Comprehensive test coverage for:
- Initialization (_init)
- Control area setup (_set_control_area)
- Figure state management (_clear_figure_state, _reset_actions)
- File dialog (get_save_filename)
- Plot methods (_plot_1d_density, _plot_capture_rate)
- Helper functions (format_axis_label)
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

    view_instance.canvas = mocker.Mock()
    view_instance.canvas.draw = mocker.Mock()

    # Mock signals
    view_instance.add_text_to_display = mocker.Mock()
    view_instance.add_text_to_display.emit = mocker.Mock()

    # Mock helper methods
    view_instance._update_cache = mocker.Mock()
    view_instance._clear_cache = mocker.Mock()
    view_instance._logscale_and_filter_multiple_columns = mocker.Mock(
        side_effect=lambda *args, **kwargs: (args[0],) if args else ()
    )

    # Initialize the view
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