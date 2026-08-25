# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Alejandra Carolina González González
# Kyle Briggs

import bisect
import itertools
import json
import logging
import os
import re
import warnings
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple, Union

import matplotlib.pyplot as pl
import numpy as np
import numpy.typing as npt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.colorbar import Colorbar
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import Axes3D
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
)
from scipy import stats
from scipy.optimize import curve_fit
from scipy.stats import iqr, t
from typing_extensions import override

from poriscope.plugins.analysistabs.utils.metadatacontrols import MetadataControls
from poriscope.plugins.analysistabs.utils.walkthrough_mixin import (
    WalkthroughMixin,
    WalkthroughStep,
)
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log, register_action
from poriscope.utils.MetaView import MetaView
from poriscope.views.widgets.add_subset_filter_dialog import AddSubsetFilterDialog
from poriscope.views.widgets.dict_dialog_widget import DictDialog
from poriscope.views.widgets.edit_subset_filter_dialog import EditSubsetFilterDialog
from poriscope.views.widgets.multiselect import MultiSelectComboBox
from poriscope.views.widgets.SelectionTree import SelectionTree

warnings.filterwarnings(
    "ignore",
    message="constrained_layout not applied because axes sizes collapsed to zero",
)


@inherit_docstrings
class MetadataView(MetaView, WalkthroughMixin):
    """
    Subclass of MetaView for visualizing and interacting with metadata plots.

    This view supports a wide variety of statistical visualizations, including:
    1D histograms, KDEs, capture rates, scatterplots, heatmaps, and event overlays.
    Also provides walkthroughs and export options.

    Attributes:
        metadata_plots (List[str]): List of supported metadata-based plot types.
        event_data_plots (List[str]): List of supported event-based plot types.
        subset_export_count (int): Counter for naming exported subsets.
        plot_initialized (bool): Indicates whether a plot is currently initialized.
        no_cached_data (bool): True if data is not cached due to size.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._init()
        self._init_walkthrough()

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the MetadataView instance.
        """
        self._clear_cache()
        self.plot_initialized = False
        self.no_cached_data = False
        self.subset_export_count = 0
        self.metadata_plots = [
            "Histogram",
            "Normalized Histogram",
            "Categorical Histogram",
            "Kernel Density Plot",
            "Capture Rate",
            "Heatmap",
            "Scatterplot",
            "3D Scatterplot",
        ]
        self.event_data_plots = [
            "Raw Event Overlay",
            "Filtered Event Overlay",
            "Raw All Points Histogram",
            "Normalized Raw All Points Histogram",
            "Filtered All Points Histogram",
            "Normalized Filtered All Points Histogram",
        ]
        self.hist_min: Optional[float] = None
        self.hist_max: Optional[float] = None
        # Heterogeneous by design: the histogram paths append 1-D arrays, the
        # density path appends whole DataFrames, and the all-points path appends
        # (x, y) tuples. Flagged for review.
        self.hist_data: List[Any] = []
        self.hist_labels: List[Any] = []
        self.subset_filters: Dict[str, str] = {}
        self.available_experiment_and_channels_by_loader: Dict[
            str, Dict[str, List[str]]
        ] = {}
        self.selected_experiment_and_channels_by_loader: Dict[
            str, Dict[str, List[str]]
        ] = {}
        self.allowed_plot_type: Optional[str] = None
        self.allowed_columns: List[str] = []
        self.allowed_logs: List[bool] = []
        self.allowed_bins: Optional[Union[int, float]] = None
        self.allowed_sizes: Optional[bool] = None

        self._show_sql_in_display: bool = False
        self._show_event_sql_in_display: bool = False

        self.plotted_datasets: Set[
            Tuple[
                Optional[str],
                Optional[str],
                Optional[int],
                Optional[str],
                Optional[str],
            ]
        ] = set()
        self.vertical: Optional[List[float]] = None
        self.horizontal: Optional[List[float]] = None
        self.points: Optional[List[Tuple[float, float]]] = None
        self.vlabels: Optional[List[str]] = None
        self.hlabels: Optional[List[str]] = None
        self.plabels: Optional[List[str]] = None
        self._heatmap_colorbar: Optional[Colorbar] = None
        self._pending_filter_name: Optional[str] = None
        self._pending_filter_text: Optional[str] = None
        self._pending_old_filter_name: Optional[str] = None
        # list of tuples of things already plotted: (loader, experiment, channel, filter, subset name), which can be None

        # Cache for filter-aware event navigation — rebuilt only when filter/scope changes
        self.filtered_event_ids: List[int] = []
        self.current_sql_filter: Optional[str] = None
        self.current_experiment: Optional[str] = None
        self.current_channel: Optional[int] = None

    @log(logger=logger)
    @override
    def _set_control_area(self, layout: QBoxLayout) -> None:
        """
        Set up the control area layout by inserting metadata controls.

        :param layout: The layout to which the controls will be added.
        :type layout: QBoxLayout
        """
        self.metadatacontrols = MetadataControls()
        self.metadatacontrols.actionTriggered.connect(self.handle_parameter_change)
        self.metadatacontrols.edit_processed.connect(self.handle_edit_triggered)
        self.metadatacontrols.add_processed.connect(self.handle_add_triggered)
        self.metadatacontrols.delete_processed.connect(self.handle_delete_triggered)
        self.metadatacontrols.edit_filter_requested.connect(
            self.show_edit_filter_dialog
        )
        self.metadatacontrols.delete_filter_requested.connect(
            self._delete_filter_by_name
        )

        controlsAndAnalysisLayout = QHBoxLayout()
        controlsAndAnalysisLayout.setContentsMargins(0, 0, 0, 0)

        # Add the rawdatacontrols directly to the main layout
        controlsAndAnalysisLayout.addWidget(self.metadatacontrols, stretch=1)

        layout.setSpacing(0)
        layout.addLayout(controlsAndAnalysisLayout, stretch=1)

    @log(logger=logger)
    def get_save_filename(self) -> str:
        """
        Open a file dialog for the user to choose a save location.

        :return: Selected filename.
        :rtype: str
        """
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV File",
            os.path.expanduser("~"),
            "CSV Files (*.csv);;All Files (*)",
        )
        return file_name

    @log(logger=logger)
    def _clear_figure_state(
        self,
        axis_type: str = "2d",
        *,
        create_default_axes: bool = True,
    ) -> None:
        """
        Canonical figure reset.

        :param axis_type: Type of axes to create if recreating axes.
                        Use "2d" for a standard 2D axes or "3d" for a 3D projection.
        :type axis_type: str
        :param create_default_axes: Whether to recreate a default axes after clearing
                                    the figure. If False, the figure is left without axes.
        :type create_default_axes: bool
        :return: None
        :rtype: None
        """
        # Always invalidate references to figure-owned artists
        self._heatmap_colorbar = None

        fig = getattr(self, "figure", None)
        if fig is None:
            self._clear_cache()
            return

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            fig.clear()

        if create_default_axes:
            if axis_type == "2d":
                self.axes = fig.add_subplot(1, 1, 1)
            else:
                self.axes = fig.add_subplot(1, 1, 1, projection="3d")

        fig.set_layout_engine("constrained")
        self._clear_cache()

    @log(logger=logger)
    def _axes_valid(self, axis_type: str = "2d") -> bool:
        """
        Check whether self.axes currently refers to a live axes object that
        is actually attached to self.figure and has the requested
        projection. After _update_event_plot() rebuilds the figure into a
        grid of per-event subplots, self.axes is left pointing at an axes
        that has been removed from the figure (a stale reference); reusing
        it would silently draw onto an orphaned, invisible axes.

        :param axis_type: Either "2d" or "3d", the projection required by
                        the plot about to be drawn.
        :type axis_type: str
        :return: True if self.axes is safe to reuse, False if a reset is needed.
        :rtype: bool
        """
        ax = getattr(self, "axes", None)
        if ax is None or ax not in self.figure.axes:
            return False
        is_3d = isinstance(ax, Axes3D)
        return is_3d if axis_type == "3d" else not is_3d

    @log(logger=logger)
    @register_action()
    @override
    def _reset_actions(self, axis_type: str = "2d") -> None:
        """
        Clears the figure and reinitializes axes. This will also add a flag to the tab action history
        if @register_action is being used to keep track of actions. Only actions applied after the most
        recent call to this function will be recreated if the related file is loaded.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        """
        # Canonical figure reset
        self._clear_figure_state(axis_type=axis_type, create_default_axes=True)

        self.canvas.draw()

        # Reset plot bookkeeping variables
        self.hist_min = None
        self.hist_max = None
        self.hist_data = []
        self.hist_labels = []
        self.allowed_plot_type = None
        self.allowed_columns = []
        self.allowed_logs = []
        self.allowed_bins = None
        self.allowed_sizes = None
        self.plotted_datasets = (
            set()
        )  # tuple of things already plotted: (loader, experiment, channel, filter, subset_name), which can be None

    @log(logger=logger)
    def _plot_1d_density(
        self,
        ax: Axes,
        data: Any,
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        logscales: Sequence[bool],
        dataset_label: str = "",
        bins: Any = None,
        sizes: bool = False,
    ) -> None:
        """
        :param ax: the axis object on which to plot
        :type ax: Axes
        :param data: Dataframe of metadata to plot. Typed loosely because the body rebinds this name to the extracted column array.
        :type data: Any
        :param cols: Sequence of column names, only the first will be used
        :type cols: Sequence[str]
        :param units: Sequence of unit strings for axis labels, only the first entry will be used
        :type units: Sequence[Optional[str]]
        :param logscales: logscale the data in the given column before building the density plot?
        :type logscales: Sequence[bool]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :param bins: Number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning. Arrives as a single-element list from the controls and is rebound to a scalar (or None, to fall back to an automatic estimate) in the body, hence the loose annotation.
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool
        :raises ValueError: If bins is an empty list.

        Calculate a plot a 1d kernel density with optional logscaling before binning
        """

        if bins is not None:
            if isinstance(bins, list) and len(bins) >= 1:
                bins = bins[0]
            else:
                raise ValueError(f"Invalid bins entry {bins}")

        if self.hist_min is None or min(data) < self.hist_min:
            self.hist_min = min(data)
        if self.hist_max is None or max(data) > self.hist_max:
            self.hist_max = max(data)
        ax.clear()
        self._clear_cache()
        self.hist_data.append(data)
        self.hist_labels.append(dataset_label)

        for data, dataset_label in zip(self.hist_data, self.hist_labels):
            (x_label,) = cols
            (x_units,) = units
            (logx,) = logscales
            data = data[x_label].values
            x_label = self.format_axis_label(x_label, x_units)
            y_label = "Probability Density"

            if logx:
                x_label = f"log10({x_label})"

            logx = logscales[0]

            (data,) = self._logscale_and_filter_multiple_columns(data, log_flags=[logx])

            if bins is not None:
                if sizes is False:
                    numbins = bins
                else:
                    try:
                        if self.hist_max is not None and self.hist_min is not None:
                            numbins = int((self.hist_max - self.hist_min) / bins)
                        else:
                            bins = None
                            numbins = 0
                    except TypeError:
                        bins = None
                        numbins = 0
                    if numbins <= 1:
                        bins = None
            if bins is None:
                try:
                    if iqr(data) > 0:
                        numbins = int(
                            (np.max(data) - np.min(data))
                            * len(data) ** (1.0 / 3.0)
                            / (iqr(data))
                        )
                    else:
                        numbins = int(3.332 * np.log10(len(data)))
                except OverflowError:
                    numbins = 100

            density = stats.kde.gaussian_kde(data.T)
            x = np.linspace(np.min(data), np.max(data), numbins)
            ax.plot(x, density(x), label=dataset_label)
            ax.fill_between(x, density(x), alpha=0.3)

            self._update_cache((x, x_label), (density(x), y_label))

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.legend(loc="best")

    @log(logger=logger)
    def _plot_capture_rate(
        self,
        ax: Axes,
        data: Any,
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        logscales: Sequence[bool],
        dataset_label: str = "",
        bins: Any = None,
        sizes: bool = False,
    ) -> None:
        """
        :param ax: the axis object on which to plot
        :type ax: Axes
        :param data: Dataframe of metadata to plot. Typed loosely because the body rebinds this name to the extracted column array.
        :type data: Any
        :param cols: Sequence of column names, only the first will be used
        :type cols: Sequence[str]
        :param units: Sequence of unit strings for axis labels, only the first entry will be used
        :type units: Sequence[Optional[str]]
        :param logscales: logscale the data in the given column before building the density plot? only the first will be used
        :type logscales: Sequence[bool]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :param bins: Number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning. Arrives as a single-element list from the controls and is rebound to a scalar (or None, to fall back to an automatic estimate) in the body, hence the loose annotation.
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool
        :raises ValueError: If bins is an empty list, or too little data survives the log filter to estimate a capture rate.

        Calculate the capture rate for the given subset
        """

        def log_exp_pdf(
            logt: npt.NDArray[np.float64], rate: float, amplitude: float
        ) -> npt.NDArray[np.float64]:
            x = amplitude * np.exp(-rate * 10.0**logt) * 10.0**logt * np.log(10)
            return x

        if bins is not None:
            if isinstance(bins, list) and len(bins) >= 1:
                bins = bins[0]
            else:
                raise ValueError(f"Invalid bins entry {bins}")

        initial_length = len(data)
        (x_label,) = cols
        (x_units,) = units
        (logx,) = logscales
        data = data[x_label].values
        data = np.diff(np.sort(data))
        data = np.log10(data[data > 0])

        if len(data) < 10:
            raise ValueError(
                f"Not enough data passes the log filter: {len(data)} is not enough to estimate capture rate - skipping"
            )

        if len(data) < initial_length:
            self.add_text_to_display.emit(
                f"{initial_length - len(data)} rows dropped by log filter",
                self.__class__.__name__,
            )

        x_label = f"Interevent Time ({x_units})"
        y_label = "Count"

        if logx:
            x_label = f"log10({x_label})"

        if bins is None:
            try:
                if iqr(data) > 0:
                    numbins = int(
                        (np.max(data) - np.min(data))
                        * len(data) ** (1.0 / 3.0)
                        / (iqr(data))
                    )
                else:
                    numbins = int(3.332 * np.log10(len(data)))
            except OverflowError:
                numbins = int(3.332 * np.log10(len(data)))
        else:
            numbins = bins

        val, bins, patches = ax.hist(
            data,
            bins=numbins,
            histtype="step",
            stacked=False,
            fill=False,
            label=dataset_label,
        )

        bincenters = bins[:-1] + np.diff(bins) / 2.0

        rate_guess = 1.0 / (10 ** bincenters[np.argmax(val)])
        amp_guess = np.max(val) / (np.log(10) / (rate_guess * np.exp(1)))
        p0 = [rate_guess, amp_guess]

        popt, pcov = curve_fit(log_exp_pdf, bincenters, val, p0=p0)
        rate = popt[0]
        amp = popt[1]
        error = -t.isf(0.975, len(val)) * np.sqrt(np.diag(pcov))[0]

        fit = log_exp_pdf(bincenters, rate, amp)

        ax.plot(bincenters, fit, label=f"{rate:.3g} \u00b1 {error:.1g} Hz")

        self._update_cache((bincenters, x_label), (val, y_label))

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.legend(loc="best")

    @log(logger=logger)
    def _plot_1d_histogram(
        self,
        ax: Axes,
        data: Any,
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        logscales: Sequence[bool],
        dataset_label: str = "",
        bins: Any = None,
        sizes: bool = False,
        norm: bool = False,
    ) -> None:
        """
        :param ax: the axis object on which to plot
        :type ax: Axes
        :param data: Dataframe of metadata to plot. Typed loosely because the body rebinds this name to the extracted column array.
        :type data: Any
        :param cols: Sequence of column names, only the first will be used
        :type cols: Sequence[str]
        :param units: Sequence of unit strings for axis labels, only the first entry will be used
        :type units: Sequence[Optional[str]]
        :param logscales: logscale the data in the given column before building the density plot? only the first will be used
        :type logscales: Sequence[bool]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :param bins: Number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning. Arrives as a single-element list from the controls and is rebound to a scalar (or None, to fall back to an automatic estimate) in the body, hence the loose annotation.
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool
        :param norm: normalize output to [0,1]?
        :type norm: bool
        :raises ValueError: If bins is an empty list.

        Calculate a plot a 1d histogram with optional logscaling and normalization
        """
        if bins is not None:
            if isinstance(bins, list) and len(bins) >= 1:
                bins = bins[0]
            else:
                raise ValueError(f"Invalid bins entry {bins}")

        (x_label,) = cols
        (x_units,) = units
        (logx,) = logscales
        data = data[x_label].values

        (data,) = self._logscale_and_filter_multiple_columns(data, log_flags=[logx])

        # Update global min/max
        if self.hist_min is None or np.min(data) < self.hist_min:
            self.hist_min = float(np.min(data))
        if self.hist_max is None or np.max(data) > self.hist_max:
            self.hist_max = float(np.max(data))

        ax.clear()
        self._clear_cache()

        # Store processed data for overlay
        self.hist_data.append(data)
        self.hist_labels.append(dataset_label)

        # Compute shared bin edges once
        # Use ALL currently overlaid data to decide numbins when bins is None (auto)
        all_data = (
            np.concatenate(self.hist_data)
            if len(self.hist_data) > 1
            else self.hist_data[0]
        )

        # Decide numbins once
        numbins: int
        if bins is not None:
            if sizes is False:
                numbins = int(bins)
            else:
                # bins is interpreted as a bin *size*
                try:
                    if self.hist_max is not None and self.hist_min is not None:
                        numbins = int((self.hist_max - self.hist_min) / float(bins))
                    else:
                        numbins = 0
                except Exception:
                    numbins = 0
                if numbins <= 1:
                    # fall back to auto
                    bins = None

        if bins is None:
            try:
                if iqr(all_data) > 0:
                    numbins = int(
                        (np.max(all_data) - np.min(all_data))
                        * len(all_data) ** (1.0 / 3.0)
                        / iqr(all_data)
                    )
                else:
                    numbins = int(3.332 * np.log10(len(all_data)))
            except OverflowError:
                numbins = 100

        # Guardrail
        if numbins < 2:
            numbins = 2

        # Shared bin edges for every dataset
        bin_edges = np.linspace(self.hist_min, self.hist_max, numbins + 1)
        bincenters = bin_edges[:-1] + np.diff(bin_edges) / 2.0
        widths = np.diff(bin_edges)

        # Plot all datasets using the same bin_edges
        for d, lab in zip(self.hist_data, self.hist_labels):
            x_lab = self.format_axis_label(x_label, x_units)
            y_lab = "Count" if not norm else "Fraction"
            if logx:
                x_lab = f"log10({x_lab})"

            val, _ = np.histogram(d, bins=bin_edges)
            val = val.astype(float)
            if norm:
                s = np.sum(val)
                if s > 0:
                    val /= s

            ax.bar(
                bincenters,
                val,
                width=widths,
                alpha=0.5,
                label=lab,
                align="center",
            )

            self._update_cache((bincenters, x_lab), (val, y_lab))

            ax.set_xlabel(x_lab)
            ax.set_ylabel(y_lab)

        ax.legend(loc="best")

    @log(logger=logger)
    def _plot_categorical_histogram(
        self,
        ax: Axes,
        data: pd.DataFrame,
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        dataset_label: str = "",
    ) -> None:
        """
        Calculate and plot a 1d categorical bar chart showing counts of unique values.

        :param ax: the axis object on which to plot
        :type ax: Axes
        :param data: Dataframe of metadata to plot, only the first named column will be used
        :type data: pd.DataFrame
        :param cols: Sequence of column names, only the first will be used
        :type cols: Sequence[str]
        :param units: Sequence of unit strings for axis labels, only the first entry will be used
        :type units: Sequence[Optional[str]]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        """
        (x_label,) = cols
        (x_units,) = units

        # Extract the specific column's values
        data_vals = data[x_label].values

        # Note: If your categories are strings, ensure this method doesn't attempt mathematical log-scaling on them.
        # (data_vals,) = self._logscale_and_filter_multiple_columns(data_vals)

        ax.clear()
        self._clear_cache()

        # Store processed data for overlay
        self.hist_data.append(data_vals)
        self.hist_labels.append(dataset_label)

        # Plot all datasets
        for d, lab in zip(self.hist_data, self.hist_labels):
            x_lab = self.format_axis_label(x_label, x_units)
            y_lab = "Count"

            # Extract unique categorical values and their respective counts
            unique_vals, counts = np.unique(d, return_counts=True)

            val = counts.astype(float)

            # Convert unique values to strings so matplotlib natively aligns them as discrete categories
            categories = [str(uv) for uv in unique_vals]

            ax.bar(
                categories,
                val,
                alpha=0.5,
                label=lab,
                align="center",
            )

            self._update_cache((categories, x_lab), (val, y_lab))

            ax.set_xlabel(x_lab)
            ax.set_ylabel(y_lab)
        ax.tick_params(axis="x", rotation=45)
        ax.legend(loc="best")

    @log(logger=logger)
    def _plot_heatmap(
        self,
        ax: Axes,
        data: pd.DataFrame,
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        logscales: Sequence[bool],
        dataset_label: str = "",
        bins: Any = None,
        sizes: bool = False,
    ) -> None:
        """
        Calculate a 2d heatmap with optional logscaling

        :param ax: the axis object on which to plot
        :type ax: Axes
        :param data: Dataframe of metadata to plot, only the first two named columns will be used
        :type data: pd.DataFrame
        :param cols: Sequence of column names, only the first two entries will be used
        :type cols: Sequence[str]
        :param units: Sequence of unit strings for axis labels, only the first two entries will be used
        :type units: Sequence[Optional[str]]
        :param logscales: logscale the data in the given column before building the density plot? only the first two entries will be used
        :type logscales: Sequence[bool]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :param bins: Number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning. Arrives as a single-element list from the controls and is rebound to a scalar (or None, to fall back to an automatic estimate) in the body, hence the loose annotation.
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool
        """
        x_label, y_label = cols
        x_units, y_units = units
        logx, logy = logscales

        x = data[x_label].values
        y = data[y_label].values

        x_label = self.format_axis_label(x_label, x_units)
        y_label = self.format_axis_label(y_label, y_units)

        if logx:
            x_label = f"log10({x_label})"
        if logy:
            y_label = f"log10({y_label})"

        x, y, z = self._calculate_heatmap(
            x, y, logx=logx, logy=logy, bins=bins, sizes=sizes
        )
        im = ax.imshow(
            z,
            origin="lower",
            interpolation="gaussian",
            extent=[np.min(x), np.max(x), np.min(y), np.max(y)],
            aspect="auto",
        )
        proxy = Line2D([0], [0], color="none", label=dataset_label)

        X, Y = np.meshgrid(x, y)
        x_flat = X.flatten()
        y_flat = Y.flatten()
        z_flat = z.flatten()
        count = np.where(z_flat == -1, 0, 2**z_flat)
        self._update_cache((x_flat, x_label), (y_flat, y_label), (count, "Count"))

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)

        # Determine ticks
        check = self.figure.colorbar(im, ax=ax)
        ticks = np.array(check.get_ticks())
        check.remove()
        tickmax = max(ticks)
        ticks = np.linspace(-1, int(tickmax) + 1, num=int(tickmax) + 3, endpoint=True)

        # Remove the previous colorbar if it exists (overlay case)
        cb = getattr(self, "_heatmap_colorbar", None)
        if cb is not None:
            try:
                # only remove if it still has an axes attached to a figure
                if getattr(cb, "ax", None) is not None and cb.ax.figure is self.figure:
                    cb.remove()
            except Exception:
                # Cosmetic only - the stale colorbar is dropped either way by the
                # reset below. Logged so a plot that looks wrong leaves a trace.
                self.logger.debug(
                    "Could not remove the previous heatmap colorbar", exc_info=True
                )
            self._heatmap_colorbar = None

        self._heatmap_colorbar = self.figure.colorbar(im, ax=ax, ticks=ticks)
        self._heatmap_colorbar.ax.set_yticklabels([0] + list(2 ** ticks[1:]))

        ax.legend(handles=[proxy], loc="best", handlelength=0, handleheight=0)

    @log(logger=logger)
    def _plot_scatterplot(
        self,
        ax: Axes,
        data: pd.DataFrame,
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        logscales: Sequence[bool],
        dataset_label: str = "",
    ) -> None:
        """
        Create a scatterplot of two metadata columns.

        :param ax: Matplotlib axes object.
        :type ax: Axes
        :param data: DataFrame containing the columns to plot.
        :type data: pd.DataFrame
        :param cols: Sequence containing two column names for x and y axes.
        :type cols: Sequence[str]
        :param units: Corresponding units for x and y axes.
        :type units: Sequence[Optional[str]]
        :param logscales: Log-scaling flags for x and y axes.
        :type logscales: Sequence[bool]
        :param dataset_label: Label for the dataset.
        :type dataset_label: str
        """
        x_label, y_label = cols
        x_units, y_units = units
        logx, logy = logscales

        x = data[x_label].values
        y = data[y_label].values

        x_label = self.format_axis_label(x_label, x_units)
        y_label = self.format_axis_label(y_label, y_units)

        if logx:
            x_label = f"log10({x_label})"
        if logy:
            y_label = f"log10({y_label})"

        xdata, ydata = self._logscale_and_filter_multiple_columns(
            x, y, log_flags=[logx, logy]
        )
        ax.scatter(xdata, ydata, s=3, alpha=0.5, label=dataset_label)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)

        self._update_cache((xdata, x_label), (ydata, y_label))
        ax.legend(loc="best")

    @log(logger=logger)
    def _plot_3d_scatterplot(
        self,
        ax: Axes3D,
        data: pd.DataFrame,
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        logscales: Sequence[bool],
        dataset_label: str = "",
    ) -> None:
        """
        Create a 3D scatterplot of three metadata columns.

        :param ax: A 3D Matplotlib axes object.
        :type ax: Axes3D
        :param data: DataFrame with the columns to plot.
        :type data: pd.DataFrame
        :param cols: Sequence with three column names for x, y, and z.
        :type cols: Sequence[str]
        :param units: Corresponding units.
        :type units: Sequence[Optional[str]]
        :param logscales: Log scale flags for each axis.
        :type logscales: Sequence[bool]
        :param dataset_label: Label to apply to the scatter points.
        :type dataset_label: str
        """
        x_label, y_label, z_label = cols
        x_units, y_units, z_units = units
        logx, logy, logz = logscales

        x = data[x_label].values
        y = data[y_label].values
        z = data[z_label].values

        x_label = self.format_axis_label(x_label, x_units)
        y_label = self.format_axis_label(y_label, y_units)
        z_label = self.format_axis_label(z_label, z_units)

        if logx:
            x_label = f"log10({x_label})"
        if logy:
            y_label = f"log10({y_label})"
        if logz:
            z_label = f"log10({z_label})"

        xdata, ydata, zdata = self._logscale_and_filter_multiple_columns(
            x, y, z, log_flags=[logx, logy, logz]
        )

        if not isinstance(ax, Axes3D):
            self._reset_actions(axis_type="3d")
            ax = self.axes

        ax.scatter(xdata, ydata, zdata, label=dataset_label)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_zlabel(z_label)

        self._update_cache((xdata, x_label), (ydata, y_label), (zdata, z_label))
        ax.legend(loc="best")

    @log(logger=logger)
    def _plot_all_points_histogram(
        self,
        ax: Axes,
        data: pd.DataFrame,
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        dataset_label: str = "",
        norm: bool = False,
    ) -> None:
        """
        Plot a histogram of current values across all events (raw or filtered).

        :param ax: Matplotlib axes to draw the histogram on.
        :type ax: Axes
        :param data: DataFrame containing time and current values.
        :type data: pd.DataFrame
        :param cols: Column names for x and y axes.
        :type cols: Sequence[str]
        :param units: Units corresponding to the axes.
        :type units: Sequence[Optional[str]]
        :param dataset_label: Label for the plotted dataset.
        :type dataset_label: str
        :param norm: normalize output to [0,1]?
        :type norm: bool
        """
        x_label, y_label = cols
        x_units, y_units = units

        x = data[x_label].values
        y = data[y_label].values

        x_label = self.format_axis_label(x_label, x_units)
        y_label = self.format_axis_label(y_label, y_units)
        if norm is True:
            y = y.astype(float)
            y /= sum(y)
            y_label = f"Normalized {y_label}"

        ax.clear()
        self._clear_cache()
        self.hist_data.append((x, y))
        self.hist_labels.append(dataset_label)

        for (x, y), label in zip(self.hist_data, self.hist_labels):
            if norm is False:
                ax.plot(x, y, label=label)
            else:
                ax.plot(x, y / np.max(y), label=label)
            self._update_cache((x, x_label), (y, y_label))

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.legend(loc="best")

    @log(logger=logger)
    def update_plot(
        self,
        plot_type: str,
        data: pd.DataFrame,
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        logscales: Sequence[bool],
        dataset_label: str = "",
        bins: Any = None,
        sizes: bool = False,
    ) -> None:
        """
        Update the plot area with the provided data across multiple channels in a grid layout.

        :param plot_type: The kind of plot to draw (e.g. "Histogram", "Scatterplot", "Heatmap"); selects which internal plotting method is dispatched to.
        :type plot_type: str
        :param data: a pandas dataframe with column headers matching x_col, y_col, z_col
        :type data: pd.DataFrame
        :param cols: a sequence of strings corresponding to column headers in the dataframe
        :type cols: Sequence[str]
        :param units: a sequence of strings corresponding to column units in the dataframe
        :type units: Sequence[Optional[str]]
        :param logscales: a sequence of bools indicating whether the given axis should be logscaled
        :type logscales: Sequence[bool]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :param bins: Number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning. Arrives as a single-element list from the controls and is rebound to a scalar (or None, to fall back to an automatic estimate) in the body, hence the loose annotation.
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool
        :raises NotImplementedError: If plot_type is not one of the supported plot types.
        """
        axis_type = "3d" if plot_type == "3D Scatterplot" else "2d"
        if not self._axes_valid(axis_type=axis_type):
            self._reset_actions(axis_type=axis_type)
        ax = self.axes

        if plot_type in ["Histogram", "Normalized Histogram"]:
            norm = False if plot_type != "Normalized Histogram" else True
            self._plot_1d_histogram(
                ax,
                data,
                cols,
                units,
                logscales,
                dataset_label=dataset_label,
                bins=bins,
                sizes=sizes,
                norm=norm,
            )
        elif plot_type == "Categorical Histogram":
            self._plot_categorical_histogram(
                ax, data, cols, units, dataset_label=dataset_label
            )
        elif plot_type == "Kernel Density Plot":
            self._plot_1d_density(
                ax,
                data,
                cols,
                units,
                logscales,
                dataset_label=dataset_label,
                bins=bins,
                sizes=sizes,
            )
        elif plot_type == "Capture Rate":
            try:
                self._plot_capture_rate(
                    ax,
                    data,
                    cols,
                    units,
                    logscales,
                    dataset_label=dataset_label,
                    bins=bins,
                    sizes=sizes,
                )
            except ValueError:
                self.add_text_to_display.emit(
                    f"No data available to plot in {dataset_label} after filtering",
                    self.__class__.__name__,
                )
        elif plot_type == "Scatterplot":
            self._plot_scatterplot(
                ax, data, cols, units, logscales, dataset_label=dataset_label
            )
        elif plot_type == "Heatmap":
            self._plot_heatmap(
                ax,
                data,
                cols,
                units,
                logscales,
                dataset_label=dataset_label,
                bins=bins,
                sizes=sizes,
            )
        elif plot_type == "3D Scatterplot":
            self._plot_3d_scatterplot(
                ax, data, cols, units, logscales, dataset_label=dataset_label
            )
        elif plot_type in [
            "Raw All Points Histogram",
            "Filtered All Points Histogram",
            "Normalized Raw All Points Histogram",
            "Normalized Filtered All Points Histogram",
        ]:
            norm = (
                False
                if plot_type
                not in [
                    "Normalized Raw All Points Histogram",
                    "Normalized Filtered All Points Histogram",
                ]
                else True
            )
            self._plot_all_points_histogram(
                ax, data, cols, units, dataset_label=dataset_label, norm=norm
            )
        else:
            raise NotImplementedError(f"Plot type {plot_type} is not yet supported")

        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    @override
    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """
        Called whenever a new plugin is instantiated elsewhere in the app, to keep an up-to-date list of possible data sources for use by this plugin.

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app.
        :type available_plugins: Dict[str, List[str]]
        """
        super().update_available_plugins(available_plugins)

        try:
            loaders = available_plugins.get("MetaDatabaseLoader", [])
            self.metadatacontrols.update_loaders(loaders)
            for loader in loaders:
                self.request_experiment_structure(loader)
            self.logger.info("ComboBoxes updated with available databases")
            self.logger.debug(
                f"Loaded experiment and channel selection: {self.selected_experiment_and_channels_by_loader}"
            )

        except Exception as e:
            self.logger.info(f"Updating ComboBoxes failed: {repr(e)}")

    @override
    @log(logger=logger)
    def notify_plugin_state_changed(
        self, metaclass: str, plugin_key: str, reason: str
    ) -> None:
        """
        Called when some other plugin instance's state changed elsewhere in the
        app. Refreshes this tab's column list only when the change concerns a
        MetaDatabaseLoader's columns and the loader that changed is the one
        currently selected here; any other metaclass, reason, or a loader that
        isn't currently selected in this tab is ignored.

        :param metaclass: The metaclass of the plugin instance whose state
                        changed.
        :type metaclass: str
        :param plugin_key: The unique key identifying the plugin instance that
                        changed.
        :type plugin_key: str
        :param reason: A short string identifying what kind of change occurred.
        :type reason: str
        :return: None
        :rtype: None
        """
        if metaclass != "MetaDatabaseLoader" or reason != "columns":
            self.logger.debug(
                f"notify_plugin_state_changed: ignoring (metaclass={metaclass}, reason={reason})"
            )
            return
        current = self.metadatacontrols.db_loader_comboBox.currentText()
        if plugin_key == current:
            self.logger.debug(
                f"notify_plugin_state_changed: refreshing columns for {plugin_key}"
            )
            self.update_available_columns(plugin_key)
        else:
            self.logger.debug(
                f"notify_plugin_state_changed: ignoring, {plugin_key} != current selection {current}"
            )

    @log(logger=logger)
    def set_experiment_id(self, experiment_id: Optional[int]) -> None:
        """
        A global signal callback that provides an experiment id for a given filter.

        :param experiment_id: the integer id of the experiment in a MetaEventLoader object
        :type experiment_id: Optional[int]
        """
        self.experiment_id = experiment_id

    @log(logger=logger)
    def set_table_by_column(self, table: Optional[str]) -> None:
        """
        Get a list of tables affected by an SQL query.

        :param table: the name of a table that is implicated in an SQL query to a MetaDatabaseLoader object
        :type table: Optional[str]
        """
        if table is not None:
            self.involved_tables.append(table)

    @log(logger=logger)
    @register_action()
    def _overlay_plot(self, parameters: Dict[str, Any]) -> bool:
        """
        Handle the creation of a new overlay plot based on the selected parameters.

        :param parameters: A dictionary of plotting parameters selected by the user.
        :type parameters: Dict[str, Any]
        :return: True if at least one dataset was plotted, False otherwise - including when every requested dataset was skipped as already plotted, so that the caller can roll the recorded action back rather than leave an undo step that would restore an identical figure.
        :rtype: bool
        """
        self._show_sql_in_display = False
        self._show_event_sql_in_display = False

        selected_filters = self.get_selected_filters()
        loader = parameters["db_loader"]
        plot_type = parameters["plot_type"]
        experiments_and_channels: Optional[
            Union[Dict[str, List[str]], Dict[Any, Any]]
        ] = self.selected_experiment_and_channels_by_loader.get(loader)

        self.plot_initialized = True

        if experiments_and_channels is None or len(experiments_and_channels) == 0:
            experiments_and_channels = {None: [None]}

        if selected_filters is None or selected_filters == {}:
            selected_filters = {"Full Dataset": ""}

        if plot_type in ["Raw Event Overlay", "Filtered Event Overlay", "Heatmap"]:
            if len(experiments_and_channels) > 1:
                self.logger.warning(
                    f"Only a single experiment can be used for {plot_type}"
                )
                self.add_text_to_display.emit(
                    f"Only a single experiment can be used for {plot_type}",
                    self.__class__.__name__,
                )
                return False

            for exp, channels in experiments_and_channels.items():
                if len(channels) > 1:
                    self.logger.warning(
                        f"Only a single channel can be used for {plot_type}"
                    )
                    self.add_text_to_display.emit(
                        f"Only a single channel can be used for {plot_type}",
                        self.__class__.__name__,
                    )
                    return False

            if len(selected_filters) > 1:
                self.add_text_to_display.emit(
                    f"Only a single subset can be used for {plot_type}",
                    self.__class__.__name__,
                )
                return False

        # Tracks whether anything actually made it onto the axes. A click that
        # skips every dataset as already-plotted must not leave a recorded
        # action behind, or Undo would spend a step restoring the same figure.
        plotted_any = False

        for exp, channels in experiments_and_channels.items():
            for channel in channels:
                exp_and_ch_arg = {exp: [channel]}
                # The selection tree hands back the channel as a display
                # string; plotted_datasets keys on the real int channel id.
                # Normalise once so the membership test and the insert below
                # cannot disagree.
                channel_id = int(channel) if channel is not None else None

                for subset_name, sql_filter in selected_filters.items():
                    bins = None

                    dataset_label = (
                        f"{loader} | {exp} Ch {channel}: {subset_name}"
                        if exp is not None
                        else f"{loader} | {subset_name}"
                    )
                    sizes = False
                    columns: List[str] = []
                    logscales: List[bool] = []

                    if plot_type in self.metadata_plots:
                        if plot_type in [
                            "Kernel Density Plot",
                            "Histogram",
                            "Normalized Histogram",
                            "Categorical Histogram",
                        ]:
                            columns = [parameters["x_axis"]]
                            logscales = [parameters["x_log"]]
                            bins = parameters["bins"]
                            sizes = parameters["sizes"]

                        elif plot_type in ["Scatterplot", "Heatmap"]:
                            columns = [parameters["x_axis"], parameters["y_axis"]]
                            logscales = [parameters["x_log"], parameters["y_log"]]
                            bins = parameters["bins"]
                            sizes = parameters["sizes"]

                        elif plot_type in ["3D Scatterplot"]:
                            columns = [
                                parameters["x_axis"],
                                parameters["y_axis"],
                                parameters["z_axis"],
                            ]
                            logscales = [
                                parameters["x_log"],
                                parameters["y_log"],
                                parameters["z_log"],
                            ]

                        elif plot_type in ["Capture Rate"]:
                            columns = ["start_time"]
                            logscales = [True]
                            bins = parameters["bins"]
                            sizes = parameters["sizes"]

                        else:
                            self.add_text_to_display.emit(
                                f"Unsupported Plot Type: {plot_type}",
                                self.__class__.__name__,
                            )
                            return False

                        bin_sensitive = plot_type in [
                            "Histogram",
                            "Normalized Histogram",
                            "Kernel Density Plot",
                            "Capture Rate",
                            "Heatmap",
                        ]
                        bins_changed = getattr(self, "allowed_bins", None) != bins
                        sizes_changed = getattr(self, "allowed_sizes", None) != sizes

                        # reset the plot if the plot options change or the figure is in an unexpected state
                        axis_type = "3d" if plot_type == "3D Scatterplot" else "2d"
                        axes_is_stale = len(
                            self.figure.axes
                        ) > 1 or not self._axes_valid(axis_type=axis_type)

                        if (
                            axes_is_stale
                            or (
                                self.allowed_columns
                                and not all(
                                    col in self.allowed_columns for col in columns
                                )
                            )
                            or (
                                self.allowed_logs
                                and not all(
                                    log in self.allowed_logs for log in logscales
                                )
                            )
                            or (
                                self.allowed_plot_type is not None
                                and plot_type != self.allowed_plot_type
                            )
                            or (bin_sensitive and (bins_changed or sizes_changed))
                        ):
                            axis_type = "3d" if plot_type == "3D Scatterplot" else "2d"
                            self._reset_actions(axis_type=axis_type)

                        seen = set()
                        for col in columns:
                            if col in seen:
                                QMessageBox.warning(
                                    self,
                                    "Duplicate Axis",
                                    "All columns should be different for a meaningful plot "
                                    f"(got '{col}' more than once).",
                                )
                                return False
                            seen.add(col)

                        if (
                            self.plotted_datasets
                            and (loader, exp, channel_id, sql_filter, subset_name)
                            in self.plotted_datasets
                        ):  # do not overlay the same thing twice
                            continue

                        self.global_signal.emit(
                            "MetaDatabaseLoader",
                            loader,
                            "construct_metadata_query",
                            (columns, sql_filter, exp_and_ch_arg),
                            "relay_query",
                            (),
                        )
                        if self.query == "":
                            return False

                        self.global_signal.emit(
                            "MetaDatabaseLoader",
                            loader,
                            "load_metadata",
                            (columns, sql_filter, exp_and_ch_arg),
                            "update_plot_data",
                            (),
                        )

                        if self.plot_data is None:
                            self.add_text_to_display.emit(
                                f"No data matching the subset {dataset_label}, skipping",
                                self.__class__.__name__,
                            )
                            continue
                        else:
                            self.add_text_to_display.emit(
                                f"{len(self.plot_data)} rows in subset {dataset_label}",
                                self.__class__.__name__,
                            )

                        units = []
                        for column in columns:
                            self.global_signal.emit(
                                "MetaDatabaseLoader",
                                loader,
                                "get_column_units",
                                (column),
                                "relay_units",
                                (),
                            )
                            units.append(self.units)

                        if len(columns) != len(units):
                            self.add_text_to_display.emit(
                                "cols and units must have equal length",
                                self.__class__.__name__,
                            )
                            return False
                        if not all(col in self.plot_data.columns for col in columns):
                            self.add_text_to_display.emit(
                                f"All columns {columns} must be present in the provided dataframe",
                                self.__class__.__name__,
                            )
                            return False

                        self.update_plot(
                            plot_type,
                            self.plot_data,
                            columns,
                            units,
                            logscales,
                            dataset_label=dataset_label,
                            bins=bins,
                            sizes=sizes,
                        )

                    elif plot_type in self.event_data_plots:
                        self.global_signal.emit(
                            "MetaDatabaseLoader",
                            loader,
                            "construct_event_data_query",
                            (sql_filter, exp_and_ch_arg),
                            "relay_event_query",
                            (),
                        )
                        if self.event_query == "":
                            return False
                        self.global_signal.emit(
                            "MetaDatabaseLoader",
                            loader,
                            "load_event_data",
                            (sql_filter, exp_and_ch_arg),
                            "relay_event_data_generator",
                            (),
                        )
                        if self.event_data_generator:
                            if plot_type in [
                                "Raw All Points Histogram",
                                "Normalized Raw All Points Histogram",
                                "Filtered All Points Histogram",
                                "Normalized Filtered All Points Histogram",
                            ]:
                                bins = parameters["bins"]
                                sizes = parameters["sizes"]

                                bin_sensitive = True
                                bins_changed = (
                                    getattr(self, "allowed_bins", None) != bins
                                )
                                sizes_changed = (
                                    getattr(self, "allowed_sizes", None) != sizes
                                )
                                if bin_sensitive and (bins_changed or sizes_changed):
                                    axis_type = (
                                        "3d"
                                        if isinstance(
                                            getattr(self, "axes", None), Axes3D
                                        )
                                        else "2d"
                                    )
                                    self._reset_actions(axis_type=axis_type)

                                plot_data = self._construct_all_points_histogram(
                                    self.event_data_generator,
                                    plot_type,
                                    bins=bins,
                                    sizes=sizes,
                                )

                                if plot_data is not None:
                                    self.update_plot(
                                        plot_type,
                                        plot_data,
                                        plot_data.columns,
                                        ["pA", ""],
                                        logscales=[False, False],
                                        dataset_label=dataset_label,
                                    )
                                else:
                                    return False

                            elif plot_type in [
                                "Raw Event Overlay",
                                "Filtered Event Overlay",
                            ]:
                                if not self._axes_valid(axis_type="2d"):
                                    self._reset_actions(axis_type="2d")
                                self._construct_event_overlay(
                                    self.event_data_generator, plot_type, loader
                                )
                        else:
                            return False

                    self.allowed_plot_type = plot_type
                    self.allowed_bins = bins
                    self.allowed_sizes = sizes

                    if plot_type in self.metadata_plots:
                        self.allowed_columns = columns
                        self.allowed_logs = logscales
                    else:
                        # event plots don't have metadata axes/log flags
                        self.allowed_columns = []
                        self.allowed_logs = []

                    self.plotted_datasets.add(
                        (loader, exp, channel_id, sql_filter, subset_name)
                    )
                    plotted_any = True

        return plotted_any

    @log(logger=logger)
    def _construct_all_points_histogram(
        self,
        event_generator: Iterator[Dict[str, Any]],
        plot_type: str,
        bins: Any = None,
        sizes: bool = False,
    ) -> pd.DataFrame:
        """
        Build a combined histogram across all event current values.

        :param event_generator: Generator yielding individual event data.
        :type event_generator: Iterator[Dict[str, Any]]
        :param plot_type: Type of histogram to create (raw or filtered).
        :type plot_type: str
        :param bins: Number of histogram bins. Arrives as a single-element list from the controls and is rebound to a scalar (or None) in the body, hence the loose annotation.
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool
        :return: DataFrame with histogram values and corresponding current levels.
        :rtype: pd.DataFrame
        :raises ValueError: If plot_type is not a recognized all-points-histogram variant.
        """
        # get global stats from the first event, don't forget to use this one later
        egen1, egen2 = itertools.tee(event_generator)

        min_current = float("inf")
        max_current = float("-inf")
        for event in egen1:

            if plot_type in [
                "Raw All Points Histogram",
                "Normalized Raw All Points Histogram",
            ]:
                timeseries = event["raw_data"]
            elif plot_type in [
                "Filtered All Points Histogram",
                "Normalized Filtered All Points Histogram",
            ]:
                timeseries = event["filtered_data"]
            else:
                raise ValueError(f"Unknown plot_type {plot_type!r}")

            padding_before = int(event["padding_before"] * event["samplerate"] * 1e-6)
            baseline = np.median(timeseries[:padding_before])

            min_curr = np.min(
                np.sign(baseline) * timeseries - np.sign(baseline) * baseline
            )
            max_curr = np.max(
                np.sign(baseline) * timeseries - np.sign(baseline) * baseline
            )
            if min_curr < min_current:
                min_current = min_curr
            if max_curr > max_current:
                max_current = max_curr

        if self.hist_min is None or min_current < self.hist_min:
            self.hist_min = min_current
        if self.hist_max is None or max_current > self.hist_max:
            self.hist_max = max_current

        if bins is not None:
            if sizes is False:
                if isinstance(bins, list) and len(bins) >= 1:
                    bins = bins[0]
                else:
                    raise ValueError(f"Invalid bins entry {bins}")
            else:
                try:
                    bins = int((self.hist_max - self.hist_min) / bins[0])
                except Exception as e:
                    raise ValueError(
                        f"Unable to calculate bins given sizes {bins}: {str(e)}"
                    )
        else:
            bins = 100

        bin_edges = np.linspace(self.hist_min, self.hist_max, bins + 1)
        hist = np.zeros(bins)
        for event in egen2:
            if plot_type in [
                "Raw All Points Histogram",
                "Normalized Raw All Points Histogram",
            ]:
                timeseries = event["raw_data"]
            elif plot_type in [
                "Filtered All Points Histogram",
                "Normalized Filtered All Points Histogram",
            ]:
                timeseries = event["filtered_data"]
            else:
                raise ValueError(f"Unknown plot_type {plot_type!r}")
            padding_before = int(event["padding_before"] * event["samplerate"] * 1e-6)
            baseline = np.median(timeseries[:padding_before])
            event_hist, _ = np.histogram(
                np.sign(baseline) * timeseries - np.sign(baseline) * baseline,
                bins=bin_edges,
            )
            hist += event_hist
        bincenters = bin_edges[:-1] + np.diff(bin_edges) / 2.0
        return pd.DataFrame({"Current": bincenters, "Count": hist})

    @log(logger=logger)
    def set_baseline_duration(self, duration: Optional[float]) -> None:
        """
        a callback from a global_signal call that sets the baseline_duration variable for further processing

        :param duration: total duration of baseline data in the scoped subset, or None if it could not be resolved.
        :type duration: Optional[float]
        """
        self.baseline_duration = duration

    @log(logger=logger)
    def set_column_type(self, column_type: Optional[str]) -> None:
        """
        a callback from a global_signal call that sets the column type of a specified variable

        :param column_type: SQL type name of the queried column, or None on failure.
        :type column_type: Optional[str]
        """
        self.column_type = column_type

    @log(logger=logger)
    def _construct_event_overlay(
        self,
        event_generator: Iterator[Dict[str, Any]],
        plot_type: str,
        loader: str,
    ) -> None:
        """
        Overlay multiple event traces in a normalized time plot.

        :param event_generator: Generator of events to overlay.
        :type event_generator: Iterator[Dict[str, Any]]
        :param plot_type: Either 'Raw Event Overlay' or 'Filtered Event Overlay'.
        :type plot_type: str
        :param loader: Identifier of the database loader plugin providing the events.
        :type loader: str
        """
        ax = self.axes

        egen1, egen2 = itertools.tee(event_generator)
        min_duration = float("inf")
        max_duration = float("-inf")

        num_events = 0
        for event in egen1:
            num_events += 1
            if plot_type == "Raw Event Overlay":
                data = event["raw_data"]
            elif plot_type == "Filtered Event Overlay":
                data = event["filtered_data"]
            duration = len(data)
            if duration < min_duration:
                min_duration = duration
            if duration > max_duration:
                max_duration = duration

        for event in egen2:
            if plot_type == "Raw Event Overlay":
                data = event["raw_data"]
            elif plot_type == "Filtered Event Overlay":
                data = event["filtered_data"]

            padding_before = int(event["padding_before"] * event["samplerate"] * 1e-6)
            padding_after = int(event["padding_after"] * event["samplerate"] * 1e-6)
            baseline = np.median(data[:padding_before])

            data = np.sign(baseline) * data - np.sign(baseline) * baseline
            time = np.array(range(len(data)), dtype=np.float64)
            time -= padding_before
            time /= len(data) - padding_after - padding_before

            duration = len(data)
            if max_duration > min_duration:
                alpha = (
                    15
                    / num_events
                    * (
                        1
                        - 0.99
                        * (duration - min_duration)
                        / (max_duration - min_duration)
                    )
                )
            else:
                alpha = 15 / num_events
            alpha = np.min((alpha, 0.5))
            ax.plot(time, data, alpha=alpha, color="b")

        ax.set_xlim(left=-0.333, right=1.333)
        ax.set_xlabel("Normalized Time")
        ax.set_ylabel("Rectified Current (pA)")

        self.canvas.draw()
        self.no_cached_data = True

    @log(logger=logger)
    def set_event_data_generator(self, generator: Iterator[Dict[str, Any]]) -> None:
        """
        Set the event data generator for event-based plots.

        :param generator: A generator that yields event data.
        :type generator: Iterator[Dict[str, Any]]
        """
        self.event_data_generator = generator

    @log(logger=logger)
    def _undo_plot(self) -> None:
        """
        Undo the last plotted action and update the action history.
        """
        self.update_tab_action_history.emit(None, True)

    @log(logger=logger)
    def _save_filter(self) -> None:
        """
        Save the current filters to a JSON file.

        """
        if not self.subset_filters:
            self.logger.info("There are no filters to save.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Filters", os.path.expanduser("~"), "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, "w") as f:
                json.dump(self.subset_filters, f, indent=4)
            self.logger.info(f"Filters saved to {path}")
        except Exception as e:
            self.logger.error(f"Failed to save filters: {e}")

    @log(logger=logger)
    def _load_filter(self, parameters: Dict[str, Any]) -> None:
        """
        Append filters from a JSON file, warn if duplicates are found,
        and apply all new filters only if none conflict with existing ones.

        :param parameters: Dictionary with 'db_loader'.
        :type parameters: Dict[str, Any]
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Filters", os.path.expanduser("~"), "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, "r") as f:
                new_filters = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            message = f"Failed to load filters from {path}: {e}"
            self.logger.error(message)
            self.add_text_to_display.emit(message, self.__class__.__name__)
            return

        if not isinstance(new_filters, dict):
            message = (
                f"Invalid filter file format in {path}: expected a dictionary, "
                f"got {type(new_filters).__name__}."
            )
            self.logger.error(message)
            self.add_text_to_display.emit(message, self.__class__.__name__)
            return

        # Check for name conflicts
        existing_names = set(self.subset_filters.keys())
        new_names = set(new_filters.keys())
        duplicate_names = existing_names & new_names

        if duplicate_names:
            message = (
                f"Duplicate filter names found when loading from {path}: "
                f"{', '.join(duplicate_names)}. No filters were loaded."
            )
            self.logger.warning(message)
            self.add_text_to_display.emit(message, self.__class__.__name__)
            return

        combo = self.metadatacontrols.filter_comboBox
        loader = parameters.get("db_loader")

        if not loader:
            self.logger.warning("No loader found – filters loaded but not validated.")

        for name, filter_text in new_filters.items():
            if loader:
                # Temporarily store to validate
                self._pending_filter_name = name
                self._pending_filter_text = filter_text

                self.global_signal.emit(
                    "MetaDatabaseLoader",
                    loader,
                    "construct_metadata_query",
                    (
                        ["sublevel_current", "voltage", "duration"],
                        filter_text,
                        None,
                    ),
                    "relay_query",
                    ("validate_new_filter",),
                )
            else:
                self.subset_filters[name] = filter_text
                combo.addItem(name)
                combo.selectItem(name, select=True)

        combo.refreshDisplayText()
        self.logger.info(f"Filters loaded from {path}")

    @log(logger=logger)
    @Slot(str, str, tuple)
    def handle_parameter_change(
        self, submodel_name: str, action_name: str, args: tuple
    ) -> None:
        """
        Handle changes triggered by UI controls such as updates to axis selection or filters.

        :param submodel_name: Name of the submodel that triggered the action.
        :type submodel_name: str
        :param action_name: Name of the action triggered.
        :type action_name: str
        :param args: Tuple containing action-specific arguments.
        :type args: tuple
        :raises NotImplementedError: If action_name is "new_axis" (not currently supported).
        """
        parameters = args[0]

        if action_name == "export_plot_data":
            if self.no_cached_data is True:
                self.add_text_to_display.emit(
                    "Event overlay data is not cached due to volume; use Export Subset as CSV instead",
                    self.__class__.__name__,
                )
            else:
                self.export_plot_data.emit()
        elif action_name == "loader_changed":
            loader = parameters["db_loader"]
            self.update_available_columns(loader)
        elif action_name == "select_experiment_and_channel":
            loader = parameters.get("db_loader")
            structure = self.available_experiment_and_channels_by_loader.get(loader, {})
            selection = self.selected_experiment_and_channels_by_loader.get(loader, {})
            self.show_selection_tree(structure, loader, selection)
        elif action_name == "shift_range_backward":
            self._shift_range_and_update_plot(parameters, direction="left")
        elif action_name == "plot_events":
            self.logger.debug(f"plot_events parameters: {parameters}")
            self._handle_plot_events(parameters)
        elif action_name == "shift_range_forward":
            self._shift_range_and_update_plot(parameters, direction="right")
        elif action_name == "plot_type_changed":
            loader = parameters["db_loader"]
            parameters["plot_type"]
        elif action_name == "columns_updated":
            loader = parameters["db_loader"]
            for axis in ["x_axis", "y_axis", "z_axis"]:
                column = parameters[axis]
                self.update_units(loader, column, axis)
        elif action_name == "new_axis":
            raise NotImplementedError("No new axis for you")
            # self._undo_plot()
        elif action_name == "update_plot":
            if parameters.get("plot_type") == "Categorical Histogram":
                loader = parameters["db_loader"]
                x_axis_col = parameters["x_axis"]

                self.column_type = None
                self.global_signal.emit(
                    "MetaDatabaseLoader",
                    loader,
                    "get_column_type",
                    x_axis_col,
                    "relay_column_type",
                    (),
                )

                if not self.is_categorical_type(self.column_type):
                    self.add_text_to_display.emit(
                        f"Categorical histograms can only be plotted for columns that correspond to discrete values: {x_axis_col} has type {self.column_type}",
                        self.__class__.__name__,
                    )
                    # Exit immediately out of handle_parameter_change.
                    # This prevents _overlay_plot from running and avoids the history rollback entirely.
                    return
            success = self._overlay_plot(parameters)
            if success is False:
                self.update_tab_action_history.emit(None, True)
        elif action_name == "reset_plot":
            self._reset_actions()
        elif action_name == "load_plot":
            loader = parameters["db_loader"]
            actions = self._load_actions_from_json()
            if not actions:
                return
            self._update_actions_from_json(actions)
        elif action_name == "save_plot_config":
            self._save_actions_to_json()
        elif action_name == "undo_plot":
            self._undo_plot()
        elif action_name == "add_filter":
            self._show_add_filter_dialog(parameters)
        elif action_name == "edit_filter":
            self._show_filter_info_dialog(
                self.metadatacontrols.filter_comboBox, parameters
            )
        elif action_name == "delete_filter":
            self._delete_all_selected_filters()
        elif action_name == "save_filter":
            self._save_filter()
        elif action_name == "load_filter":
            self._load_filter(parameters)
        elif action_name == "export_csv_subset":
            loader = parameters["db_loader"]
            selection = self.selected_experiment_and_channels_by_loader.get(loader, {})
            selected_filters = selected_filters = self.get_selected_filters()
            self._export_csv_subset(loader, selected_filters, selection)
        else:
            self._handle_other_actions(action_name, parameters)

    @log(logger=logger)
    def _build_where_clause(
        self,
        loader: str,
        sql_filter: str,
        exp: Optional[str],
        channel: Optional[int],
    ) -> str:
        """
        Build a WHERE clause for direct DB queries on the events table, scoped to
        the current filter, experiment, and channel.

        :param loader: Name of the active database loader.
        :type loader: str
        :param sql_filter: SQL filter string (may be empty).
        :type sql_filter: str
        :param exp: Experiment name.
        :type exp: Optional[str]
        :param channel: Channel identifier.
        :type channel: Optional[int]
        :return: WHERE clause string (including the WHERE keyword), or empty string.
        :rtype: str
        """
        filter_parts = []
        if sql_filter:
            filter_parts.append(sql_filter)
        if exp is not None:
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "get_experiment_id_by_name",
                (exp,),
                "relay_experiment_id",
                (),
            )
            exp_id = getattr(self, "relayed_experiment_id", None)
            if exp_id is not None:
                filter_parts.append(f"experiment_id = {exp_id}")
                if channel is not None:
                    filter_parts.append(f"channel_id = {channel}")
        return f"WHERE {' AND '.join(filter_parts)}" if filter_parts else ""

    @log(logger=logger)
    def _rebuild_event_id_cache(
        self,
        loader: str,
        where_clause: str,
        sql_filter: str,
        exp: Optional[str],
        channel: Optional[int],
    ) -> bool:
        """
        Rebuild the filtered event_id cache when filter or scope changes.
        Also emits the display panel message (first plot or filter change only).

        :param loader: Name of the active database loader.
        :type loader: str
        :param where_clause: Pre-built WHERE clause for the events table.
        :type where_clause: str
        :param sql_filter: Current SQL filter string.
        :type sql_filter: str
        :param exp: Current experiment name.
        :type exp: Optional[str]
        :param channel: Current channel identifier.
        :type channel: Optional[int]
        :return: True if cache was rebuilt successfully, False otherwise.
        :rtype: bool
        """
        cache_query = f"SELECT event_id FROM events {where_clause} ORDER BY event_id"
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "query_database_directly",
            (cache_query,),
            "relay_query_result",
            (),
        )
        cache_result = getattr(self, "relayed_query_result", None)
        if cache_result is None or cache_result.empty:
            self.add_text_to_display.emit(
                "No filtered events found",
                self.__class__.__name__,
            )
            return False

        self.filtered_event_ids = cache_result["event_id"].tolist()
        self.current_sql_filter = sql_filter
        self.current_experiment = exp
        self.current_channel = channel

        # Display panel — only on cache rebuild (filter change or first plot)
        total = len(self.filtered_event_ids)
        first_id = self.filtered_event_ids[0]
        last_id = self.filtered_event_ids[-1]
        if sql_filter:
            # Get the filter name from the current selected filters
            selected_filters = self.get_selected_filters()
            filter_name = next(iter(selected_filters.keys()), "Filter")
            label = f'"{filter_name}" subset'
        else:
            label = "All events"
        self.add_text_to_display.emit(
            f"{label}: {total} total | first event_id: {first_id} | last event_id: {last_id}",
            self.__class__.__name__,
        )
        return True

    @log(logger=logger)
    def _shift_range_and_update_plot(
        self, parameters: Dict[str, Any], direction: str
    ) -> None:
        """
        Shift the current event_id forward or backward through the cached filtered set and update the plot.

        :param parameters: Dictionary of current event plotting parameters.
        :type parameters: Dict[str, Any]
        :param direction: Either 'left' or 'right'.
        :type direction: str
        """

        loader = parameters["db_loader"]
        event_id = parameters.get("event_id") or 0
        n_events = parameters.get("n_events", 1)

        selected_filters = self.get_selected_filters()
        if selected_filters is None or selected_filters == {}:
            selected_filters = {"Full Dataset": ""}
        sql_filter = next(iter(selected_filters.values()))

        exp_and_ch = self.selected_experiment_and_channels_by_loader.get(loader)
        if exp_and_ch is None:
            self.logger.error("No experiments or channels in scope for navigation.")
            return

        exp = next(iter(exp_and_ch.keys()))
        selected_channel = next(iter(exp_and_ch.values()))[0]
        channel = int(selected_channel) if selected_channel is not None else None

        # Rebuild cache if filter or scope changed
        if (
            sql_filter != self.current_sql_filter
            or exp != self.current_experiment
            or channel != self.current_channel
            or not self.filtered_event_ids
        ):
            where_clause = self._build_where_clause(loader, sql_filter, exp, channel)
            if not self._rebuild_event_id_cache(
                loader, where_clause, sql_filter, exp, channel
            ):
                return

        if not self.filtered_event_ids:
            return

        # Find current position in the cached list using binary search
        ids = self.filtered_event_ids
        n = len(ids)

        current_idx = bisect.bisect_left(ids, event_id)
        current_idx = min(current_idx, n - 1)

        if direction == "right":
            next_idx = current_idx + n_events
            if next_idx >= n:
                next_idx = 0  # wrap around to start
        else:  # left
            next_idx = current_idx - n_events
            if next_idx < 0:
                next_idx = max(0, n - n_events)  # wrap around to last window

        new_event_id = ids[next_idx]

        # Update the UI field and re-plot
        self.metadatacontrols.set_event_id_input(new_event_id)
        new_params = parameters.copy()
        new_params["event_id"] = new_event_id
        self._handle_plot_events(new_params)

    @log(logger=logger)
    def _get_event_id(self) -> Optional[int]:  # Since params expanded
        """
        Get the current event_id from the event_id input field.

        :return: Integer event_id, or None if the field is empty.
        :rtype: Optional[int]
        """
        text = self.metadatacontrols.event_id_lineEdit.text().strip()
        return int(text) if text else None

    @log(logger=logger)
    def _get_n_events(self) -> int:
        """
        Get the number of events to plot from the n_events input field.

        :return: Number of events, defaulting to 1 if the field is empty.
        :rtype: int
        """
        text = self.metadatacontrols.n_events_lineEdit.text().strip()
        return int(text) if text else 1

    @log(logger=logger)
    def _handle_plot_events(self, parameters: Dict[str, Any]) -> None:
        """
        Handle loading and plotting of selected events based on provided parameters.

        :param parameters: Dictionary containing eventfinder, filter, channels, and event indices.
        :type parameters: Dict[str, Any]
        """
        selected_filters = self.get_selected_filters()
        loader_name = parameters["db_loader"]
        experiments_and_channels = self.selected_experiment_and_channels_by_loader.get(
            loader_name
        )
        if experiments_and_channels is None:
            self.add_text_to_display.emit(
                "No experiments or channels are in scope, select at least one to plot events",
                self.__class__.__name__,
            )
            return

        if selected_filters is not None and len(selected_filters) > 1:
            self.add_text_to_display.emit(
                "Unable to plot more than one subset at a time, select only one filter to apply",
                self.__class__.__name__,
            )
            return

        if (
            self.selected_experiment_and_channels_by_loader[loader_name] is None
            or len(self.selected_experiment_and_channels_by_loader[loader_name]) == 0
        ):
            self.add_text_to_display.emit(
                "No experiments or channels are in scope, select at least one to plot events",
                self.__class__.__name__,
            )
            return

        if len(experiments_and_channels) > 1:
            self.add_text_to_display.emit(
                "Only a single experiment can be used for plotting events",
                self.__class__.__name__,
            )
            return

        for exp, channels in experiments_and_channels.items():
            if len(channels) > 1:
                self.add_text_to_display.emit(
                    "Only a single channel can be used for plotting events",
                    self.__class__.__name__,
                )
                return

        if selected_filters is None or selected_filters == {}:
            selected_filters = {"Full Dataset": ""}

        event_id = parameters.get("event_id") or 0
        n_events = parameters.get("n_events", 1)
        use_raw = parameters.get("raw", False)

        sql_filter = next(iter(selected_filters.values()))
        exp_and_ch = self.selected_experiment_and_channels_by_loader[loader_name]
        loader = parameters["db_loader"]
        exp = next(iter(exp_and_ch.keys()))
        selected_channel = next(iter(exp_and_ch.values()))[0]
        channel = int(selected_channel) if selected_channel is not None else None

        # Rebuild cache only when filter or scope changes — display panel emitted inside
        cache_needs_rebuild = (
            sql_filter != self.current_sql_filter
            or exp != self.current_experiment
            or channel != self.current_channel
            or not self.filtered_event_ids
        )
        if cache_needs_rebuild:
            where_clause = self._build_where_clause(loader, sql_filter, exp, channel)
            if not self._rebuild_event_id_cache(
                loader, where_clause, sql_filter, exp, channel
            ):
                return
        elif not self.filtered_event_ids:
            self.add_text_to_display.emit(
                "No filtered events found",
                self.__class__.__name__,
            )
            return

        # Snap using cache — bisect into filtered_event_ids
        ids = self.filtered_event_ids
        snap_idx = bisect.bisect_left(ids, event_id)
        if snap_idx >= len(ids):
            snap_idx = 0  # wrap around to first event
        snapped_event_ids = ids[snap_idx : snap_idx + n_events]
        snapped_start_id = snapped_event_ids[0]

        # Update the event_id field to reflect the snapped position
        self.metadatacontrols.set_event_id_input(snapped_start_id)

        # Resolve snapped event_ids to event_db_ids for load_event_data, scoped
        # to the current experiment/channel — event_id is only unique within a
        # channel, not across the whole events table, so without this scoping
        # the query can silently match rows from other channels that happen to
        # share the same event_id.

        # NOTE: id-resolution + fetch logic is kept inline here rather than
        # factored into a shared helper (unlike ProteinView, which extracts
        # this into _resolve_event_db_ids/_fetch_event_data) because this is
        # currently the only caller in this view. If a second consumer shows
        # up, port ProteinView's extracted pattern instead of duplicating
        # this block.
        id_tuple = f"({','.join(str(eid) for eid in snapped_event_ids)})"
        where_parts = [f"event_id IN {id_tuple}"]

        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "get_experiment_id_by_name",
            (exp,),
            "relay_experiment_id",
            (),
        )
        exp_id = getattr(self, "relayed_experiment_id", None)
        if exp_id is not None:
            where_parts.append(f"experiment_id = {exp_id}")
            if channel is not None:
                where_parts.append(f"channel_id = {channel}")

        db_id_query = f"SELECT id FROM events WHERE {' AND '.join(where_parts)}"
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "query_database_directly",
            (db_id_query,),
            "relay_query_result",
            (),
        )
        db_id_result = getattr(self, "relayed_query_result", None)
        if db_id_result is None or db_id_result.empty:
            self.add_text_to_display.emit(
                f"No data available for plotting with indices in the specified range {snapped_event_ids}",
                self.__class__.__name__,
            )
            return
        db_ids = db_id_result["id"].tolist()
        db_id_tuple = f"({','.join(str(i) for i in db_ids)})"
        event_db_id_filter = f"e.id IN {db_id_tuple}"

        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "load_event_data",
            (event_db_id_filter, exp_and_ch),
            "relay_event_plot_data_generator",
            (),
        )
        event_generator = getattr(self, "plot_events_generator", None)
        if event_generator is None:
            self.add_text_to_display.emit(
                f"No data available for plotting with indices in the specified range {snapped_event_ids}",
                self.__class__.__name__,
            )
            return

        data_list = []
        # One entry per subplot; each entry is the whole feature list for
        # that subplot, or None when the fitter supplied no features.
        vertical_lines: List[Optional[List[float]]] = []
        vertical_labels: List[Optional[List[str]]] = []
        horizontal_lines: List[Optional[List[float]]] = []
        horizontal_labels: List[Optional[List[str]]] = []
        points: List[Optional[List[Tuple[float, float]]]] = []
        plabels: List[Optional[List[str]]] = []

        for event in event_generator:
            data_list.append(event)
            vertical_lines.append(None)
            vertical_labels.append(None)
            horizontal_lines.append(None)
            horizontal_labels.append(None)
            points.append(None)
            plabels.append(None)
            experiment_id = event["experiment_id"]
            channel_id = event["channel_id"]
            event_id_val = event["event_id"]
            try:
                load_feature_args = (experiment_id, channel_id, event_id_val)
                self.global_signal.emit(
                    "MetaDatabaseLoader",
                    loader,
                    "get_plot_features",
                    load_feature_args,
                    "update_features",
                    (),
                )
            except RuntimeError as e:
                self.logger.error(
                    f"Features for event {event} could not be loaded in channel {channel}, skipping: {e}"
                )
            except KeyError as e:
                self.logger.info(
                    f"Event {event} not found in channel {channel} to get features, skipping: {e}"
                )
            except Exception as e:
                self.logger.error(
                    f"An unexpected error occured while trying to overlay features on the event: {e}"
                )
            else:
                if self.vertical is not None:
                    vertical_lines[-1] = self.vertical
                    vertical_labels[-1] = self.vlabels
                    self.vertical = None
                    self.vlabels = None
                if self.horizontal is not None:
                    horizontal_lines[-1] = self.horizontal
                    horizontal_labels[-1] = self.hlabels
                    self.horizontal = None
                    self.hlabels = None
                if self.points is not None:
                    points[-1] = self.points
                    plabels[-1] = self.plabels
                    self.points = None
                    self.plabels = None

        if data_list:
            self._update_event_plot(
                data_list,
                horizontal_lines,
                vertical_lines,
                points,
                horizontal_labels,
                vertical_labels,
                plabels,
                use_raw=use_raw,
            )
        else:
            self.add_text_to_display.emit(
                f"No data available for plotting with indices in the specified range {snapped_event_ids}",
                self.__class__.__name__,
            )
            self.logger.info(
                f"No data available for plotting with indices in the specified range {snapped_event_ids}"
            )

    @log(logger=logger)
    def set_event_plot_data_generator(
        self, generator: Iterator[Dict[str, Any]]
    ) -> None:
        """
        A callback from a global signal call that sets the generator to be used to construct event plots and overlays.

        :param generator: a generator of event data
        :type generator: Iterator[Dict[str, Any]]
        """
        self.plot_events_generator = generator

    @log(logger=logger)
    def relay_query_result(self, result: Optional[pd.DataFrame]) -> None:
        """
        A callback from a global_signal call that stores the result of a direct DB query.

        :param result: DataFrame returned by query_database_directly.
        :type result: Optional[pd.DataFrame]
        """
        self.relayed_query_result = result

    @log(logger=logger)
    def relay_experiment_id(self, exp_id: Optional[int]) -> None:
        """
        A callback from a global_signal call that stores a resolved experiment id.

        :param exp_id: Integer experiment id.
        :type exp_id: Optional[int]
        """
        self.relayed_experiment_id = exp_id

    @log(logger=logger)
    def update_plot_features(
        self,
        vertical: Optional[List[float]] = None,
        horizontal: Optional[List[float]] = None,
        points: Optional[List[Tuple[float, float]]] = None,
        vlabels: Optional[List[str]] = None,
        hlabels: Optional[List[str]] = None,
        plabels: Optional[List[str]] = None,
    ) -> None:
        """
        Update feature overlays for the plot, such as vertical/horizontal lines and labeled points.

        :param vertical: List of vertical line positions.
        :type vertical: Optional[List[float]]
        :param horizontal: List of horizontal line positions.
        :type horizontal: Optional[List[float]]
        :param points: List of (x, y) point coordinates.
        :type points: Optional[List[Tuple[float, float]]]
        :param vlabels: Labels for vertical lines.
        :type vlabels: Optional[List[str]]
        :param hlabels: Labels for horizontal lines.
        :type hlabels: Optional[List[str]]
        :param plabels: Labels for points.
        :type plabels: Optional[List[str]]
        """
        self.vertical = vertical
        self.horizontal = horizontal
        self.points = points
        self.vlabels = vlabels
        self.hlabels = hlabels
        self.plabels = plabels

    @log(logger=logger)
    def _update_event_plot(
        self,
        event_data: Sequence[Dict[str, Any]],
        horizontal_lines: Sequence[Optional[List[float]]],
        vertical_lines: Sequence[Optional[List[float]]],
        points: Sequence[Optional[List[Tuple[float, float]]]],
        horizontal_labels: Sequence[Optional[Sequence[Optional[str]]]],
        vertical_labels: Sequence[Optional[Sequence[Optional[str]]]],
        point_labels: Sequence[Optional[Sequence[Optional[str]]]],
        use_raw: bool = False,
    ) -> None:
        """
        Update the event plot with raw, filtered, and fitted traces for multiple events.

        Each event is plotted in its own subplot with time on the x-axis and current on the y-axis.
        The method also updates internal cache with data for interactive use (e.g., tooltips or exports).

        :param event_data: List of dictionaries, each containing the data and metadata for one event.
                        Each dictionary should have the keys:
                        'experiment_id', 'channel_id', 'event_id',
                        'raw_data', 'filtered_data', 'fit_data', and 'samplerate'.
        :type event_data: Sequence[Dict[str, Any]]
        :param horizontal_lines: One entry per subplot, each a list of y-values for horizontal line annotations, or None.
        :type horizontal_lines: Sequence[Optional[List[float]]]
        :param vertical_lines: One entry per subplot, each a list of x-values for vertical line annotations, or None.
        :type vertical_lines: Sequence[Optional[List[float]]]
        :param points: One entry per subplot, each a list of (x, y) coordinate tuples for marker points, or None.
        :type points: Sequence[Optional[List[Tuple[float, float]]]]
        :param horizontal_labels: One entry per subplot, each a list of labels for the horizontal lines, or None.
        :type horizontal_labels: Sequence[Optional[Sequence[Optional[str]]]]
        :param vertical_labels: One entry per subplot, each a list of labels for the vertical lines, or None.
        :type vertical_labels: Sequence[Optional[Sequence[Optional[str]]]]
        :param point_labels: One entry per subplot, each a list of labels for the points, or None.
        :type point_labels: Sequence[Optional[Sequence[Optional[str]]]]
        :param use_raw: Whether to also plot/cache the raw (unfiltered) trace alongside the filtered and fitted ones.
        :type use_raw: bool
        :return: None
        :rtype: None
        """
        # Reset metadata plot state so the next "Update Plot" click starts fresh instead of trying to overlay onto the event grid
        self._reset_actions()  # clears figure, creates default axes, draws empty canvas, records in history

        self._clear_figure_state(create_default_axes=False)

        num_events = len(event_data)
        num_rows, num_cols = self._factors(num_events)
        j = 0
        for i, (event, vlines, hlines, pts, vlabels, hlabels, plabels) in enumerate(
            zip(
                event_data,
                vertical_lines,
                horizontal_lines,
                points,
                vertical_labels,
                horizontal_labels,
                point_labels,
            )
        ):
            color_cycle = pl.rcParams["axes.prop_cycle"].by_key()["color"]
            # Filter out black (if black is in the cycle)
            colors_no_black = [
                c for c in color_cycle if c.lower() != "black" and c != "#000000"
            ]
            ax = self.figure.add_subplot(
                num_rows, num_cols, j + 1
            )  # Create subplots in a grid
            label = f'Exp {event["experiment_id"]}/Ch {event["channel_id"]}/Event {event["event_id"]}'
            ax.set_title(label)
            j += 1

            raw_data = event["raw_data"]
            filtered_data = event["filtered_data"]
            fit_data = event["fit_data"]
            samplerate = event["samplerate"]

            time = np.arange(len(raw_data)) / samplerate * 1e6
            if use_raw:
                ax.plot(time, raw_data / 1000, zorder=1)
            ax.plot(time, filtered_data / 1000, zorder=2)
            ax.plot(time, fit_data / 1000, zorder=3)
            color_idx = 0
            if hlines is not None:
                # A fitter may supply features with no labels at all, or fewer
                # labels than features; the branch below already renders those
                # unlabeled, so stand in a matching run of Nones rather than
                # letting zip() silently drop the features that have no label.
                if hlabels is None:
                    hlabels = [None] * len(hlines)
                elif len(hlabels) < len(hlines):
                    hlabels = list(hlabels) + [None] * (len(hlines) - len(hlabels))
                for line, label in zip(hlines, hlabels):
                    if label is None:
                        ax.axhline(y=line / 1000, color="black", linestyle="--")
                    else:
                        color = colors_no_black[color_idx % len(colors_no_black)]
                        ax.axhline(
                            y=line / 1000, linestyle="--", color=color, label=label
                        )
                        color_idx += 1
            color_idx = 0
            if vlines is not None:
                # A fitter may supply features with no labels at all, or fewer
                # labels than features; the branch below already renders those
                # unlabeled, so stand in a matching run of Nones rather than
                # letting zip() silently drop the features that have no label.
                if vlabels is None:
                    vlabels = [None] * len(vlines)
                elif len(vlabels) < len(vlines):
                    vlabels = list(vlabels) + [None] * (len(vlines) - len(vlabels))
                for line, label in zip(vlines, vlabels):
                    if label is None:
                        ax.axvline(x=line, color="black", linestyle="--")
                    else:
                        color = colors_no_black[color_idx % len(colors_no_black)]
                        ax.axvline(x=line, linestyle="--", color=color, label=label)
                        color_idx += 1

            color_idx = 0
            if pts is not None:
                # A fitter may supply features with no labels at all, or fewer
                # labels than features; the branch below already renders those
                # unlabeled, so stand in a matching run of Nones rather than
                # letting zip() silently drop the features that have no label.
                if plabels is None:
                    plabels = [None] * len(pts)
                elif len(plabels) < len(pts):
                    plabels = list(plabels) + [None] * (len(pts) - len(plabels))
                for (x, y), label in zip(pts, plabels):
                    if label is None:
                        ax.plot(x, y / 1000, marker="x", color="black", markersize=10)
                    else:
                        color = colors_no_black[color_idx % len(colors_no_black)]
                        ax.plot(
                            x,
                            y / 1000,
                            marker="x",
                            linestyle="None",
                            label=label,
                            color=color,
                            markersize=10,
                        )
                        color_idx += 1

            x_label = r"Time (us)"
            y_label = r"Current (nA)"

            if use_raw:
                self._update_cache(
                    (time, label + " " + x_label),
                    (raw_data / 1000, label + " Raw " + y_label),
                )
            self._update_cache(
                (time, label + " " + x_label),
                (filtered_data / 1000, label + " Filtered " + y_label),
            )
            self._update_cache(
                (time, label + " " + x_label),
                (fit_data / 1000, label + " Fitted" + y_label),
            )

            if i % num_cols == 0:
                ax.set_ylabel(y_label)
            labelnum = (num_rows - 1) * num_cols
            if num_events % num_cols > 0:
                labelnum -= num_cols - num_events % num_cols
            if i >= labelnum:
                ax.set_xlabel(r"Time ($\mu s$)")

        # Build a single shared legend from all axes, deduplicating by label
        all_handles = {}
        for ax in self.figure.get_axes():
            for handle, label in zip(*ax.get_legend_handles_labels()):
                if label not in all_handles:
                    all_handles[label] = handle

        if all_handles:
            num_entries = len(all_handles)
            fig_height = self.figure.get_size_inches()[1]
            entries_at_default = fig_height / 0.20
            if num_entries <= entries_at_default:
                font_size = 10
            else:
                font_size = max(6, int(10 * entries_at_default / num_entries))

            self.figure.legend(
                list(all_handles.values()),
                list(all_handles.keys()),
                loc="outside right upper",
                frameon=True,
                fontsize=font_size,
            )

        self.figure.set_layout_engine("constrained")
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def _export_csv_subset(
        self, loader: str, filters: Any, selection: Dict[str, List[str]]
    ) -> None:
        """
        Open a dialog to export a filtered subset of the dataset.

        :param loader: Name of the active database loader.
        :type loader: str
        :param filters: Dict of named subset filters; only a single filter may be selected for export. Typed loosely because the body rebinds this name to the single selected filter string.
        :type filters: Any
        :param selection: Selected experiments and channels to scope the export to.
        :type selection: Dict[str, List[str]]
        """
        self.available_plugins.get("MetaDatabaseLoader", [])
        if filters is not None and len(filters) > 1:
            self.add_text_to_display.emit(
                "Select a single filter to export a subset", self.__class__.__name__
            )
            return

        if filters == {}:
            filters = None
        if filters is not None:
            filters = list(filters.values())[0]

        settings = {"Folder": {"Type": str}}
        dialog = DictDialog(
            settings,
            name=f"Subset_{self.subset_export_count}",
            title="Export Settings",
            editable=True,
            show_delete=False,
        )
        dialog.exec()
        result, name = dialog.get_result()
        if not result:  # dialog was cancelled or dismissed
            return

        folder = result["Folder"]["Value"]

        export_subset_args = (folder, name, filters, selection)
        ret_args = (self.subset_export_count, loader, "MetaDatabaseLoader")
        try:
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "export_subset_to_csv",
                export_subset_args,
                "set_generator",
                ret_args,
            )
        except Exception as e:
            self.logger.error(f"Failed to export subset: {repr(e)}")
        else:
            self.run_generators.emit(loader)
            self.subset_export_count += 1

    @log(logger=logger)
    def set_exported_event_count(self, written: int) -> None:
        """
        A global signal callback that provides the number of events written in a call to export events to csv format.

        :param written: number of events successfully written
        :type written: int
        """
        self.exported_event_count = written

    @log(logger=logger)
    def set_query(self, query: str, table_name: str) -> None:
        """
        Set the SQL query and table name used in plotting.

        :param query: SQL query string.
        :type query: str
        :param table_name: Name of the database table.
        :type table_name: str
        """
        self.query = query
        self.table_name = table_name
        if not query:
            return

        # Only display SQL for filter creation/edit validation
        if self._show_sql_in_display:
            self.add_text_to_display.emit(
                f"SQL ({table_name}):\n{query.strip()}",
                self.__class__.__name__,
            )
            # one-shot so normal plot queries never show
            self._show_sql_in_display = False

    @log(logger=logger)
    def set_event_query(self, query: str) -> None:
        """
        A global signal callback that provides a valid SQL query for fetching event data.

        :param query: SQL query string for fetching event data.
        :type query: str
        """
        self.event_query = query
        if not query:
            return

        if self._show_event_sql_in_display:
            self.add_text_to_display.emit(
                f"Event SQL:\n{query.strip()}",
                self.__class__.__name__,
            )
            self._show_event_sql_in_display = False

    @log(logger=logger)
    def set_units(self, units: Any) -> None:
        """
        Set the units returned from the database for use in axis labels.

        :param units: List or string representing units.
        :type units: Any
        """
        self.units = units

    @log(logger=logger)
    def update_available_columns(self, loader: str) -> None:
        """
        Request available columns from the database loader.

        :param loader: Name of the active database loader.
        :type loader: str
        """
        if not loader or loader == "No Event Database":
            return
        try:
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "get_column_names_by_table",
                (),
                "update_column_names",
                (),
            )
        except Exception as e:
            self.logger.error(f"Failed to request column data: {repr(e)}")

    @log(logger=logger)
    def request_experiment_structure(self, loader_name: str) -> None:
        """
        Get a dict of all experiments and channels available in a specified MetaDatabaseLoader object.

        :param loader_name: the key of the loader
        :type loader_name: str
        """
        if not loader_name or loader_name == "No Event Database":
            return

        self.logger.debug(
            f"Requesting experiment-channel structure from loader: {loader_name}"
        )

        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader_name,
            "get_experiments_and_channels",
            (),
            "get_experiment_structure_ready",
            (loader_name,),
        )

    @log(logger=logger)
    def show_selection_tree(
        self,
        structure: dict[str, list[str]],
        loader_name: str,
        selection: Optional[dict[str, list[str]]] = None,
    ) -> None:
        """
        Displays the selection tree for a given loader using the full structure and current selection.
        """
        self.logger.debug(
            f"Displaying selection tree with structure: {structure} for loader: {loader_name}"
        )

        if not hasattr(self, "selection_tree"):
            self.selection_tree = SelectionTree()

        selected = self.selection_tree.show_dialog(
            structure,
            loader_name,
            title="Select Experiment and Channels",
            selected=selection,
        )

        self.selected_experiment_and_channels_by_loader[loader_name] = selected
        self.logger.debug(f"Updated selection for {loader_name}: {selected}")

    @log(logger=logger)
    def update_units(self, loader: str, column: str, axis: str) -> None:
        """
        Request units for a specific column from the loader.

        :param loader: Name of the database loader.
        :type loader: str
        :param column: Name of the column to get units for.
        :type column: str
        :param axis: Axis being updated ('x_axis', 'y_axis', etc.).
        :type axis: str
        """
        try:
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "get_column_units",
                (column,),
                "update_column_units",
                (axis,),
            )
        except Exception as e:
            self.logger.error(f"Failed to request units for column {column}: {repr(e)}")

    @log(logger=logger)
    def update_column_names(self, column_names: List[str]) -> None:
        """
        Relay function to update the list of available columns.

        :param column_names: List of column names.
        :type column_names: List[str]
        """
        self.metadatacontrols.update_axes(column_names)

    @log(logger=logger)
    def update_column_units(self, column_units: Optional[str], axis: str) -> None:
        """
        Relay function to update the column unit label in the UI.

        :param column_units: Unit string for the column, or None if the loader could not resolve one.
        :type column_units: Optional[str]
        :param axis: Axis being updated.
        :type axis: str
        """
        self.metadatacontrols.update_column_units_label(column_units, axis)

    @log(logger=logger)
    def _handle_other_actions(
        self, action_name: str, parameters: Dict[str, Any]
    ) -> None:
        """
        Raise an error for actions not yet implemented.

        :param action_name: The name of the unhandled action.
        :type action_name: str
        :param parameters: Parameters associated with the action.
        :type parameters: Dict[str, Any]
        :raises NotImplementedError: Always
        """
        raise NotImplementedError(f"{action_name} handler not implemented")

    @log(logger=logger)
    def _calculate_heatmap(
        self,
        xdata: npt.NDArray[np.float64],
        ydata: npt.NDArray[np.float64],
        logx: bool = False,
        logy: bool = False,
        bins: Any = None,
        sizes: bool = False,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        :param xdata: the data on the x axis
        :type xdata: npt.NDArray[np.float64]
        :param ydata: the data on the y axis
        :type ydata: npt.NDArray[np.float64]
        :param logx: logscale the x data before building the heatmap?
        :type logx: bool
        :param logy: logscale the y data before building the heatmap?
        :type logy: bool
        :param bins: number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning. Arrives as a list from the controls and may be rebound to None in the body, hence the loose annotation.
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool
        :return: Bin-center x values, bin-center y values, and the log2-scaled 2D histogram counts.
        :rtype: tuple[np.ndarray, np.ndarray, np.ndarray]
        :raises ValueError: If bins is an invalid entry when sizes is False.

        Build a heatmap of the provided data
        """
        xdata, ydata = self._logscale_and_filter_multiple_columns(
            xdata, ydata, log_flags=[logx, logy]
        )

        if bins is not None:
            if sizes is False:
                if isinstance(bins, list) and len(bins) >= 2:
                    xbins = bins[0]
                    ybins = bins[1]
                elif isinstance(bins, list) and len(bins) == 1:
                    xbins = bins[0]
                    ybins = bins[0]
                else:
                    raise ValueError(f"Invalid bin entry: {bins}")
            elif sizes is True:
                if isinstance(bins, list) and len(bins) >= 2:
                    xbins = int((max(xdata) - min(xdata)) / bins[0])
                    ybins = int((max(ydata) - min(ydata)) / bins[1])
                elif isinstance(bins, list) and len(bins) == 1:
                    xbins = int((max(xdata) - min(xdata)) / bins[0])
                    ybins = int((max(ydata) - min(ydata)) / bins[0])
                else:
                    self.logger.info(
                        f"Invalid entry in bins: {bins}, defaulting to iqr"
                    )
                    bins = None
                if xbins <= 1 or ybins <= 1:
                    self.logger.info(
                        f"Invalid entry in bins: {bins}, defaulting to iqr"
                    )
                    bins = None
        if bins is None:
            try:
                if iqr(xdata) > 0:
                    xbins = int(
                        (max(xdata) - min(xdata))
                        * len(xdata) ** (1.0 / 4.0)
                        / (iqr(xdata))
                    )
                else:
                    xbins = int(np.sqrt(len(xdata)))
            except OverflowError:
                xbins = int(np.sqrt(len(xdata)))
            try:
                if iqr(ydata) > 0:
                    ybins = int(
                        (max(ydata) - min(ydata))
                        * len(xdata) ** (1.0 / 4.0)
                        / (iqr(ydata))
                    )
                else:
                    ybins = int(np.sqrt(len(ydata)))
            except OverflowError:
                ybins = int(np.sqrt(len(ydata)))

        z, x, y = np.histogram2d(xdata, ydata, bins=[int(xbins), int(ybins)])
        logged_z = np.empty_like(z)
        for i in range(z.shape[0]):
            for j in range(z.shape[1]):
                logged_z[i, j] = np.log2(z[i, j]) if z[i, j] > 0 else -1

        x = x[:-1] + np.diff(x) / 2.0
        y = y[:-1] + np.diff(y) / 2.0

        return x, y, logged_z.T

    @log(logger=logger)
    def _show_add_filter_dialog(self, parameters: dict) -> None:
        """
        Displays the dialog for adding a new subset filter. Validates filter syntax
        before actually saving the filter.

        :param parameters: Dictionary with 'db_loader'.
        :type parameters: dict
        """
        self._show_sql_in_display = True

        dialog = AddSubsetFilterDialog(
            self, existing_names=list(self.subset_filters.keys())
        )

        if self._walkthrough_active:
            self.logger.info("Launching walkthrough from _show_add_filter_dialog()")
            dialog._init_walkthrough()
            dialog.launch_walkthrough()
            if dialog.walkthrough_dialog:
                dialog.finished.connect(
                    lambda _: dialog.walkthrough_dialog.force_close()
                )

        if dialog.exec() == QDialog.Accepted:
            # These are Optional[str] until the dialog's try_accept/accept
            # fills them, and exec() cannot return Accepted without that
            # having run - but the guarantee travels through a signal
            # connection mypy cannot follow, so it is asserted here once
            # rather than guarded at each of the six downstream uses.
            name: str = dialog.name  # type: ignore[assignment]
            filter_text: str = dialog.filter_text  # type: ignore[assignment]
            loader = parameters["db_loader"]

            if not loader:
                self.logger.error("No database loader selected")
                return

            # Store pending data for use in relay_query
            self._pending_filter_name = name
            self._pending_filter_text = filter_text
            self._pending_old_filter_name = None

            if dialog.is_raw:
                # Raw SQL path — validate via validate_filter_query, not construct_metadata_query
                if not filter_text.strip().upper().startswith("SELECT"):
                    QMessageBox.warning(
                        self,
                        "Invalid Raw SQL Filter",
                        "Raw SQL filters must be complete SELECT statements, e.g. SELECT duration FROM events WHERE duration > 1000",
                    )
                    return
                name = f"{name}_raw" if not name.endswith("_raw") else name
                self._pending_filter_name = name
                self.global_signal.emit(
                    "MetaDatabaseLoader",
                    loader,
                    "validate_filter_query",
                    (filter_text.strip().rstrip(";") + " LIMIT 0",),
                    "on_raw_filter_validated",
                    (),
                )
                return

            self._show_sql_in_display = True

            # Validate assisted filter via construct_metadata_query
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "construct_metadata_query",
                (
                    ["sublevel_current", "voltage", "duration"],
                    filter_text,
                    None,
                ),
                "relay_query",
                ("validate_new_filter",),
            )

    @log(logger=logger)
    def show_edit_filter_dialog(self, name: str, loader: str) -> None:
        """
        Displays the dialog to edit an existing filter, and validates the updated
        SQL filter syntax via construct_metadata_query before saving it.

        :param name: The name of the filter to edit.
        :type name: str
        :param loader: Name of the active database loader.
        :type loader: str
        """
        self._show_sql_in_display = True

        self.logger.debug(f"Editing filter: {name}")
        self.logger.debug(f"Filters available: {self.subset_filters}")

        dialog = EditSubsetFilterDialog(self, name, self.subset_filters)

        if dialog.exec():
            # These are Optional[str] until the dialog's try_accept/accept
            # fills them, and exec() cannot return Accepted without that
            # having run - but the guarantee travels through a signal
            # connection mypy cannot follow, so it is asserted here once
            # rather than guarded at each of the six downstream uses.
            new_name: str = dialog.new_name  # type: ignore[assignment]
            new_filter: str = dialog.new_filter  # type: ignore[assignment]

            self.logger.debug(f"Updated filter: {name} -> {new_name}: {new_filter}")

            if not loader:
                self.logger.error("No database loader selected")
                return

            # Store pending update info to be committed in relay_query after validation
            self._pending_filter_name = new_name
            self._pending_filter_text = new_filter
            self._pending_old_filter_name = name  # important for replacing key

            if dialog.is_raw:
                # Raw SQL path — validate via validate_filter_query, not construct_metadata_query
                if not new_filter.strip().upper().startswith("SELECT"):
                    QMessageBox.warning(
                        self,
                        "Invalid Raw SQL Filter",
                        "Raw SQL filters must be complete SELECT statements, e.g. SELECT duration FROM events WHERE duration > 1000",
                    )
                    return
                new_name = (
                    f"{new_name}_raw" if not new_name.endswith("_raw") else new_name
                )
                self._pending_filter_name = new_name
                self.global_signal.emit(
                    "MetaDatabaseLoader",
                    loader,
                    "validate_filter_query",
                    (new_filter.strip().rstrip(";") + " LIMIT 0",),
                    "on_raw_filter_validated",
                    (),
                )
                return

            self._show_sql_in_display = True
            # Emit signal to validate the updated assisted filter
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "construct_metadata_query",
                (["sublevel_current", "voltage", "duration"], new_filter, None),
                "relay_query",
                ("validate_edited_filter",),
            )

    @log(logger=logger)
    def clear_pending_filter_state(self) -> None:
        """
        reset all filters to factory settings
        """
        self._pending_filter_name = None
        self._pending_filter_text = None
        self._pending_old_filter_name = None

    @log(logger=logger)
    def _show_filter_info_dialog(
        self, comboBox: MultiSelectComboBox, parameters: Dict[str, Any]
    ) -> None:
        """
        Called when clicking the edit button for filters with multiple selection.

        Validates that exactly one filter is selected and delegates to the edit dialog.

        :param comboBox: The combo box containing the list of selectable filters.
        :type comboBox: MultiSelectComboBox
        :param parameters: Dictionary with 'db_loader'.
        :type parameters: Dict[str, Any]
        """
        loader = parameters["db_loader"]
        selected = comboBox.getSelectedItems()
        if len(selected) != 1:
            self.logger.warning("Please select exactly one filter to edit.")
            return

        self.show_edit_filter_dialog(selected[0], loader)

    @log(logger=logger)
    def _delete_filter_by_name(self, name: str) -> None:
        """
        Deletes a single filter by name.

        :param name: The name of the filter to delete.
        :type name: str
        """
        self._delete_filter(name)

    @log(logger=logger)
    def _delete_all_selected_filters(self) -> None:
        """
        Deletes multiple selected filters.
        """
        selected_items = self.metadatacontrols.filter_comboBox.getSelectedItems()

        if not selected_items:
            self.logger.info("No filters selected to delete.")
            return

        for name in selected_items:
            self._delete_filter(name)

    @log(logger=logger)
    def _delete_filter(self, name: str) -> None:
        """
        Internal method to remove a filter and update the UI.

        :param name: The name of the filter to remove.
        :type name: str
        """
        self.subset_filters.pop(name, None)

        list_widget = self.metadatacontrols.filter_comboBox.listWidget
        for i in reversed(range(list_widget.count())):
            widget = list_widget.itemWidget(list_widget.item(i))
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.text() == name:
                    list_widget.takeItem(i)
                    break

        self.metadatacontrols.filter_comboBox.refreshDisplayText()

    @log(logger=logger)
    def get_selected_filters(self) -> dict:
        """
        Get a dict of the filters that the user has indicated should be active for the current plotting task
        """
        return {
            name: self.subset_filters.get(name, "")
            for name in self.metadatacontrols.filter_comboBox.getSelectedItems()
        }

    @log(logger=logger)
    def replace_filter_item(self, name: str) -> None:
        """
        Remove any existing filter item with the same name and add the new one.

        :param name: The name of the filter to (re)add.
        :type name: str
        """
        list_widget = self.metadatacontrols.filter_comboBox.listWidget
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            widget = list_widget.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            if checkbox and checkbox.text() == name:
                list_widget.takeItem(i)
                break

        self.metadatacontrols.filter_comboBox.addItem(name)
        self.metadatacontrols.filter_comboBox.selectItem(name, select=True)

    @log(logger=logger)
    def update_filter_name(self, old_name: str, new_name: str) -> None:
        """
        Replace old filter name with new one in the ComboBox, removing any duplicates.

        :param old_name: The filter name being replaced.
        :type old_name: str
        :param new_name: The filter name to display instead.
        :type new_name: str
        """
        list_widget = self.metadatacontrols.filter_comboBox.listWidget

        # Remove old name
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            widget = list_widget.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            if checkbox and checkbox.text() == old_name:
                list_widget.takeItem(i)
                break

        # Remove new name if it already exists and is different
        if new_name != old_name:
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                widget = list_widget.itemWidget(item)
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.text() == new_name:
                    list_widget.takeItem(i)
                    break

        # Add updated name
        self.metadatacontrols.filter_comboBox.addItem(new_name)
        self.metadatacontrols.filter_comboBox.selectItem(new_name, select=True)
        self.metadatacontrols.filter_comboBox.refreshDisplayText()

    @log(logger=logger)
    def set_channel_db_id(self, channel_db_id: Optional[int]) -> None:
        """
        a global signal callback that provides the channel_db_id for raw query scoping

        :param channel_db_id: Database id of the scoped channel, or None if unresolved.
        :type channel_db_id: Optional[int]
        """
        self.channel_db_id = channel_db_id

    @log(logger=logger)
    def on_raw_filter_validated(self, valid: bool, error_msg: str) -> None:
        """
        Relay callback from validate_filter_query for raw SQL filter validation.

        :param valid: Whether the query is valid.
        :type valid: bool
        :param error_msg: Error message if invalid.
        :type error_msg: str
        """
        if not valid:
            QMessageBox.warning(
                self,
                "Invalid Raw SQL Filter",
                f"The filter could not be validated:\n\n{error_msg}",
            )
            self.clear_pending_filter_state()
            return

        name = self._pending_filter_name
        filter_text = self._pending_filter_text
        old_name = self._pending_old_filter_name

        if name is None:
            # Mirrors the guard the assisted-filter path already applies in
            # relay_query: with no pending name there is nothing to commit.
            self.logger.warning(
                "Raw filter validated with no pending filter name, ignoring."
            )
            self.clear_pending_filter_state()
            return

        if old_name is not None:  # edit path
            self.subset_filters.pop(old_name, None)
            self.subset_filters[name] = filter_text or ""
            self.update_filter_name(old_name, name)
            self.add_text_to_display.emit(
                f"Filter '{old_name}' updated to '{name}'.",
                self.__class__.__name__,
            )
        else:  # add path
            self.subset_filters[name] = filter_text or ""
            self.metadatacontrols.filter_comboBox.addItem(name)
            self.metadatacontrols.filter_comboBox.selectItem(name, select=True)
            self.metadatacontrols.filter_comboBox.refreshDisplayText()
            self.add_text_to_display.emit(
                f"Filter '{name}' added.",
                self.__class__.__name__,
            )

        self.clear_pending_filter_state()

    @log(logger=logger)
    def get_walkthrough_steps(self) -> List[WalkthroughStep]:
        return [
            (
                "Metadata Tab",
                "Click the '+' button to load your metadata database.",
                "MetadataView",
                lambda: [self.metadatacontrols.db_loader_add_button],
            ),
            (
                "Metadata Tab",
                "Click the 'Scope' button to select specific experiments and  channels. By default, all options are selected.",
                "MetadataView",
                lambda: [self.metadatacontrols.selection_tree_button],
            ),
            (
                "Metadata Tab",
                "Choose the type of plot you'd like to generate from this dropdown.",
                "MetadataView",
                lambda: [self.metadatacontrols.plot_type_comboBox],
            ),
            (
                "Metadata Tab",
                "Specify the number of bins for your plot. Use 'x,y' format for heatmaps.",
                "MetadataView",
                lambda: [self.metadatacontrols.bins_lineEdit],
            ),
            (
                "Metadata Tab",
                "Check the sizes box to be able to define the sizes of your bins.",
                "MetadataView",
                lambda: [self.metadatacontrols.sizes_checkbox],
            ),
            (
                "Metadata Tab",
                "Here you can select the data for the x-axis.",
                "MetadataView",
                lambda: [self.metadatacontrols.x_axis_comboBox],
            ),
            (
                "Metadata Tab",
                "Check this box if you want to use a log scale for the x-axis.",
                "MetadataView",
                lambda: [self.metadatacontrols.x_axis_logscale_checkbox],
            ),
            (
                "Metadata Tab",
                "Once you're ready, click 'Update Plot' to generate the visualization.",
                "MetadataView",
                lambda: [self.metadatacontrols.update_plot_button],
            ),
            (
                "Metadata Tab",
                "Not happy with the changes? Click 'Undo' to revert to the previous state at any point.",
                "MetadataView",
                lambda: [self.metadatacontrols.undo_button],
            ),
            (
                "Metadata Tab",
                "Click here to save the current plot to file.",
                "MetadataView",
                lambda: [self.metadatacontrols.save_plot_button],
            ),
            (
                "Metadata Tab",
                "Reload previously saved configurations using the 'Load' button.",
                "MetadataView",
                lambda: [self.metadatacontrols.load_button],
            ),
            (
                "Metadata Tab",
                "Click 'Reset' to clear all changes and restore default settings.",
                "MetadataView",
                lambda: [self.metadatacontrols.reset_button],
            ),
            (
                "Metadata Tab",
                "Click the '+' button to apply filters to the full database or selected experiment/channels to create subsets.",
                "MetadataView",
                lambda: [self.metadatacontrols.filter_add_button],
            ),
            (
                "Metadata Tab",
                "Use this dropdown to view your created subsets.",
                "MetadataView",
                lambda: [self.metadatacontrols.filter_comboBox],
            ),
            (
                "Metadata Tab",
                "Click here to see the information and edit the currently selected subset.",
                "MetadataView",
                lambda: [self.metadatacontrols.filter_info_button],
            ),
            (
                "Metadata Tab",
                "Click the delete button to remove all selected subsets. You can also delete individual ones directly from the dropdown.",
                "MetadataView",
                lambda: [self.metadatacontrols.filter_delete_button],
            ),
            (
                "Metadata Tab",
                "Click 'Save Filter' to save the current subsets for future use.",
                "MetadataView",
                lambda: [self.metadatacontrols.save_filter_button],
            ),
            (
                "Metadata Tab",
                "Click 'Load Filter' to import previously saved subsets.",
                "MetadataView",
                lambda: [self.metadatacontrols.load_filter_button],
            ),
            (
                "Metadata Tab",
                "Use 'Export Subset - CSV' to save only the filtered data you're currently working with.",
                "MetadataView",
                lambda: [self.metadatacontrols.export_csv_subset_button],
            ),
            (
                "Metadata Tab",
                "Select exactly one experiment to visualize its events.",
                "MetadataView",
                lambda: [self.metadatacontrols.selection_tree_button],
            ),
            (
                "Metadata Tab",
                "Then, enter the event_id to start from. The system will snap to the nearest filtered event at or after that ID. Default is 0, which will start from the first event.",
                "MetadataView",
                lambda: [self.metadatacontrols.event_id_lineEdit],
            ),
            (
                "Metadata Tab",
                "You can also specify the number of events to display at once.",
                "MetadataView",
                lambda: [self.metadatacontrols.n_events_lineEdit],
            ),
            (
                "Metadata Tab",
                "Then, click 'Plot Events' to visualize the selected entries.",
                "MetadataView",
                lambda: [self.metadatacontrols.plot_events_pushButton],
            ),
            (
                "Metadata Tab",
                "Use the arrows to quickly navigate between filtered/unfiltered events, with wrap-around at both ends.",
                "MetadataView",
                lambda: [
                    self.metadatacontrols.left_arrow_button,
                    self.metadatacontrols.right_arrow_button,
                ],
            ),
            (
                "Metadata Tab",
                "Check the RAW box to overlay the unfiltered raw signal alongside the filtered and fitted traces.",
                "MetadataView",
                lambda: [self.metadatacontrols.raw_checkbox],
            ),
        ]

    @log(logger=logger)
    def get_current_view(self) -> str:
        return "MetadataView"

    @log(logger=logger)
    def is_categorical_type(self, data_type: Optional[str]) -> bool:
        """
        Evaluates an SQLite column datatype string.
        Returns True if categorical/discrete (or blank/None), False if explicitly continuous.
        """
        if not data_type:
            return True

        dt_upper = data_type.upper()

        # Strictly explicit floating-point keywords
        continuous_keywords = [
            "REAL",
            "FLOAT",
            "DOUB",  # Catches "DOUBLE" and "DOUBLE PRECISION"
        ]

        for keyword in continuous_keywords:
            if keyword in dt_upper:
                return False

        # Allows INT, TEXT, BOOLEAN, BLOB, NUMERIC, DECIMAL, etc.
        return True

    @log(logger=logger)
    def format_axis_label(self, label: str, unit: Optional[str]) -> str:
        """
        Ensure the axis label contains the correct unit exactly once.
        Removes any existing trailing unit in parentheses.
        """
        label = re.sub(r"\s*\(.*?\)$", "", label)  # Remove trailing "(...)"
        return f"{label} ({unit})" if unit and unit.strip() else label
