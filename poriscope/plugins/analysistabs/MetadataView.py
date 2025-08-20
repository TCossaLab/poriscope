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

import itertools
import json
import logging
import os
import re
import warnings
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import numpy.typing as npt
import pandas as pd
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import Axes3D
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QCheckBox, QDialog, QFileDialog, QHBoxLayout
from scipy import stats
from scipy.optimize import curve_fit
from scipy.stats import iqr, t
from typing_extensions import override

from poriscope.plugins.analysistabs.utils.metadatacontrols import MetadataControls
from poriscope.plugins.analysistabs.utils.walkthrough_mixin import WalkthroughMixin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log, register_action
from poriscope.utils.MetaView import MetaView
from poriscope.views.widgets.add_subset_filter_dialog import AddSubsetFilterDialog
from poriscope.views.widgets.dict_dialog_widget import DictDialog
from poriscope.views.widgets.edit_subset_filter_dialog import EditSubsetFilterDialog
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init()
        self._init_walkthrough()

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the MetadataView instance.

        :param args: Positional arguments passed to parent constructors.
        :param kwargs: Keyword arguments passed to parent constructors.
        """
        self._clear_cache()
        self.plot_initialized = False
        self.no_cached_data = False
        self.subset_export_count = 0
        self.metadata_plots = [
            "Histogram",
            "Normalized Histogram",
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
        self.hist_data: List[npt.NDArray[float]] = []
        self.hist_labels: List[Optional[str]] = []
        self.current_sql_filter: Optional[str] = None
        self.current_experiment: Optional[str] = None
        self.current_channel: Optional[int] = None
        self.cached_events: Dict[int, Dict[str, Any]] = {}
        self.subset_filters: Dict[str, str] = {}
        self.plot_events_generator = None
        self.available_experiment_and_channels_by_loader: Dict[
            str, Dict[str, List[str]]
        ] = {}
        self.selected_experiment_and_channels_by_loader: Dict[
            str, Dict[str, List[str]]
        ] = {}
        self.allowed_plot_type: Optional[str] = None
        self.allowed_columns: List[str] = []
        self.allowed_logs: List[bool] = []
        self.plotted_datasets: Set[
            Tuple[Optional[str], Optional[int], Optional[str], Optional[str]]
        ] = (
            set()
        )  # list of tuples of things already plotted: (experiment, channel, filter, subset_name), which can be None

    @log(logger=logger)
    @override
    def _set_control_area(self, layout):
        """
        Set up the control area layout by inserting metadata controls.

        :param layout: The layout to which the controls will be added.
        :type layout: QVBoxLayout
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
    def get_save_filename(self):
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
    @register_action()
    @override
    def _reset_actions(self, axis_type="2d"):
        """
        Clears the figure and reinitializes axes. This will also add a flag to the tab action history if @register_action is being used to keep track of actions. Only actions applied after the most recent call to this function will be recreated if the related file is loaded.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        """
        if hasattr(self, "_heatmap_colorbar") and self._heatmap_colorbar is not None:  # type: ignore
            self._heatmap_colorbar.remove()  # type: ignore
            self._heatmap_colorbar = None  # type: ignore
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            try:
                self.figure.clear()
            except AttributeError:
                pass
            self._clear_cache()
        if axis_type == "2d":
            self.axes = self.figure.add_subplot(1, 1, 1)
        else:
            self.axes = self.figure.add_subplot(1, 1, 1, projection="3d")
        self.figure.set_constrained_layout(True)
        self.canvas.draw()
        self.hist_min = None
        self.hist_max = None
        self.hist_data = []
        self.hist_labels = []
        self.allowed_plot_type = None
        self.allowed_columns = []
        self.allowed_logs = []
        self.plotted_datasets = (
            set()
        )  # tuple of things already plotted: (experiment, channel, filter), which can be None

    @log(logger=logger)
    def _plot_1d_density(
        self, ax, data, cols, units, logscales, dataset_label="", bins=None, sizes=False
    ):
        """
        :param ax: the axis object on which to plot
        :type ax: Axes
        :param data: Tuple of data, only the first entry will be used
        :type data: Tuple[npt.NDArray[np.float64]]
        :param cols: Tuple of column names, only the first will be used
        :type cols: Tuple[str]
        :param units: Tuple of unit strings for axis labels, on the first entry will be used
        :type units: Tuple[str]
        :param logscales: logscale the data in the given column before building the density plot?
        :type logscales: Tuple[bool]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :param bins: number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning
        :type bins: Union[int, float]
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool

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
            x_label = format_axis_label(x_label, x_units)
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
        self, ax, data, cols, units, logscales, dataset_label="", bins=None, sizes=False
    ):
        """
        :param ax: the axis object on which to plot
        :type ax: Axes
        :param data: Tuple of data, only the first entry will be used
        :type data: Tuple[npt.NDArray[np.float64]]
        :param cols: Tuple of column names, only the first will be used
        :type cols: Tuple[str]
        :param units: Tuple of unit strings for axis labels, on the first entry will be used
        :type units: Tuple[str]
        :param logscales: logscale the data in the given column before building the density plot? only the first will be used
        :type logscales: Tuple[bool]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :param bins: number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning
        :type bins: Union[int, float]
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool

        Calculate the capture rate for the given subset
        """

        def log_exp_pdf(logt, rate, amplitude):
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
        ax,
        data,
        cols,
        units,
        logscales,
        dataset_label="",
        bins=None,
        sizes=False,
        norm=False,
    ):
        """
        :param ax: the axis object on which to plot
        :type ax: Axes
        :param data: Tuple of data, only the first entry will be used
        :type data: Tuple[npt.NDArray[np.float64]]
        :param cols: Tuple of column names, only the first will be used
        :type cols: Tuple[str]
        :param units: Tuple of unit strings for axis labels, on the first entry will be used
        :type units: Tuple[str]
        :param logscales: logscale the data in the given column before building the density plot? only the first will be used
        :type logscales: Tuple[bool]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :param bins: number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning
        :type bins: Union[int, float]
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool
        :param norm: normalize output to [0,1]?
        :type norm: bool

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

        if self.hist_min is None or min(data) < self.hist_min:
            self.hist_min = min(data)
        if self.hist_max is None or max(data) > self.hist_max:
            self.hist_max = max(data)
        ax.clear()
        self._clear_cache()
        self.hist_data.append(data)
        self.hist_labels.append(dataset_label)

        for data, dataset_label in zip(self.hist_data, self.hist_labels):
            x_label = format_axis_label(x_label, x_units)
            y_label = "Count" if norm is False else "Fraction"

            if logx:
                x_label = f"log10({x_label})"

            if bins is not None:
                if sizes is False:
                    numbins = bins
                else:
                    try:
                        if self.hist_max is not None and self.hist_min is not None:
                            numbins = int((self.hist_max - self.hist_min) / bins)
                        else:
                            numbins = 0
                            bins = None
                    except TypeError:
                        numbins = 0
                        bins = None
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

            val, bins = np.histogram(
                data, bins=numbins, range=(self.hist_min, self.hist_max)
            )
            val = val.astype(float)
            if norm is True:
                val /= np.sum(val)

            # val, bins, patches = ax.hist(data, bins=numbins, histtype='step', stacked=False, fill=False, density=norm)
            bincenters = bins[:-1] + np.diff(bins) / 2.0

            ax.bar(
                bincenters,
                val,
                width=np.diff(bincenters)[0],
                alpha=0.5,
                label=dataset_label,
            )

            self._update_cache((bincenters, x_label), (val, y_label))

            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
        ax.legend(loc="best")

    @log(logger=logger)
    def _plot_heatmap(
        self, ax, data, cols, units, logscales, dataset_label="", bins=None, sizes=False
    ):
        """
        :param ax: the axis object on which to plot
        :type ax: Axes
        :param data: Tuple of data, only the first two entries will be used
        :type data: Tuple[npt.NDArray[np.float64]]
        :param cols: Tuple of column names, only the first two entries will be used
        :type cols: Tuple[str]
        :param units: Tuple of unit strings for axis labels, on the first two entries will be used
        :type units: Tuple[str]
        :param logscales: logscale the data in the given column before building the density plot? only the first two entries will be used
        :type logscales: Tuple[bool]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :param bins: number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning
        :type bins: Union[int, float]
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool
        :param norm: normalize output to [0,1]?
        :type norm: bool

        Calculate a 2d heatmap with optional logscaling and normalization
        """
        x_label, y_label = cols
        x_units, y_units = units
        logx, logy = logscales

        x = data[x_label].values
        y = data[y_label].values

        x_label = format_axis_label(x_label, x_units)
        y_label = format_axis_label(y_label, y_units)

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

        # Remove the previous colorbar if it exists
        if hasattr(self, "_heatmap_colorbar") and self._heatmap_colorbar:
            self._heatmap_colorbar.remove()
            self._heatmap_colorbar = None

        self._heatmap_colorbar = self.figure.colorbar(im, ax=ax, ticks=ticks)
        self._heatmap_colorbar.ax.set_yticklabels([0] + list(2 ** ticks[1:]))

        ax.legend(handles=[proxy], loc="best", handlelength=0, handleheight=0)

    @log(logger=logger)
    def _plot_scatterplot(self, ax, data, cols, units, logscales, dataset_label=""):
        """
        Create a scatterplot of two metadata columns.

        :param ax: Matplotlib axes object.
        :type ax: matplotlib.axes.Axes
        :param data: DataFrame containing the columns to plot.
        :type data: pd.DataFrame
        :param cols: List containing two column names for x and y axes.
        :type cols: List[str]
        :param units: List of corresponding units for x and y axes.
        :type units: List[str]
        :param logscales: List indicating log-scaling for x and y axes.
        :type logscales: List[bool]
        :param dataset_label: Label for the dataset.
        :type dataset_label: str
        """
        x_label, y_label = cols
        x_units, y_units = units
        logx, logy = logscales

        x = data[x_label].values
        y = data[y_label].values

        x_label = format_axis_label(x_label, x_units)
        y_label = format_axis_label(y_label, y_units)

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
    def _plot_3d_scatterplot(self, ax, data, cols, units, logscales, dataset_label=""):
        """
        Create a 3D scatterplot of three metadata columns.

        :param ax: A 3D Matplotlib axes object.
        :type ax: mpl_toolkits.mplot3d.Axes3D
        :param data: DataFrame with the columns to plot.
        :type data: pd.DataFrame
        :param cols: List with three column names for x, y, and z.
        :type cols: List[str]
        :param units: Corresponding units.
        :type units: List[str]
        :param logscales: Log scale flags for each axis.
        :type logscales: List[bool]
        :param dataset_label: Label to apply to the scatter points.
        :type dataset_label: str
        """
        x_label, y_label, z_label = cols
        x_units, y_units, z_units = units
        logx, logy, logz = logscales

        x = data[x_label].values
        y = data[y_label].values
        z = data[z_label].values

        x_label = format_axis_label(x_label, x_units)
        y_label = format_axis_label(y_label, y_units)
        z_label = format_axis_label(z_label, z_units)

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
        self, ax, data, cols, units, dataset_label="", norm=False
    ):
        """
        Plot a histogram of current values across all events (raw or filtered).

        :param ax: Matplotlib axes to draw the histogram on.
        :type ax: matplotlib.axes.Axes
        :param data: DataFrame containing time and current values.
        :type data: pd.DataFrame
        :param cols: Column names for x and y axes.
        :type cols: List[str]
        :param units: Units corresponding to the axes.
        :type units: List[str]
        :param dataset_label: Label for the plotted dataset.
        :type dataset_label: str
        """
        x_label, y_label = cols
        x_units, y_units = units

        x = data[x_label].values
        y = data[y_label].values

        x_label = format_axis_label(x_label, x_units)
        y_label = format_axis_label(y_label, y_units)
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
        plot_type,
        data,
        cols,
        units,
        logscales,
        dataset_label="",
        bins=None,
        sizes=False,
    ):
        """
        Update the plot area with the provided data across multiple channels in a grid layout.

        :param data: a pandas dataframe with column headers matching x_col, y_col, z_col
        :type data: pd.Dataframe
        :param cols: a list of strings corresponding to column headers in the dataframe
        :type cols: List[str]
        :param units: a list of strings corresponding to column units in the dataframe
        :type units: List[str]
        :param logscales: a list of bools indicating whether the given axis should be logscaled
        :type logscales: List[bool]
        :param axis_coords: x,y coordinates of the axis to which to add the plot
        :type axis_coords: Tuple[int,int]
        """
        if not hasattr(self, "axes"):
            self._reset_actions()
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
        :type available_plugins: Mapping[str, list[str]]
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

    @log(logger=logger)
    def set_experiment_id(self, experiment_id):
        """
        :param experiment_id: the integer id of the experiment in a MetaEventLoader object
        :type experiment_id: Optional[int]

        a global signal callback that provides an experiment id for a given filter
        """
        self.experiment_id = experiment_id

    @log(logger=logger)
    def set_table_by_column(self, table):
        """
        :param table: the name of a table that is implicated in an SQL query to a MetaDatabaseLoader object
        :type table: Optional[str]

        Get a list of tables affected by an SQL query
        """
        if table is not None:
            self.involved_tables.append(table)

    @log(logger=logger)
    @register_action()
    def _overlay_plot(self, parameters):
        """
        Handle the creation of a new overlay plot based on the selected parameters.

        :param parameters: A dictionary of plotting parameters selected by the user.
        :type parameters: dict
        :return: True if the overlay was successful, False otherwise.
        :rtype: bool
        """
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

        for exp, channels in experiments_and_channels.items():
            for channel in channels:
                exp_and_ch_arg = {exp: [channel]}
                for subset_name, sql_filter in selected_filters.items():
                    bins = None
                    dataset_label = (
                        f"{exp} Ch {channel}: {subset_name}"
                        if exp is not None
                        else f"{subset_name}"
                    )
                    sizes = False
                    if plot_type in self.metadata_plots:

                        if plot_type in [
                            "Kernel Density Plot",
                            "Histogram",
                            "Normalized Histogram",
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
                        else:
                            self.add_text_to_display.emit(
                                f"Unsupported Plot Type: {plot_type}",
                                self.__class__.__name__,
                            )
                            return False

                        if (
                            (
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
                        ):
                            self._reset_actions()  # reset the plot if the plot options change

                        seen = set()
                        for col in columns:
                            if col in seen:
                                self.add_text_to_display.emit(
                                    "All columns should be different for a meaningful plot",
                                    self.__class__.__name__,
                                )
                                return False
                            seen.add(col)

                        if (
                            self.plotted_datasets
                            and (exp, channel, sql_filter, subset_name)
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
                                plot_data = self._construct_all_points_histogram(
                                    self.event_data_generator,
                                    plot_type,
                                    bins,
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
                                try:
                                    self._construct_event_overlay(
                                        self.event_data_generator, plot_type, loader
                                    )
                                except:
                                    raise
                        else:
                            return False
                    self.allowed_plot_type = plot_type
                    self.allowed_columns = columns
                    self.allowed_logs = logscales
                    self.plotted_datasets.add((exp, channel, sql_filter, subset_name))
        return True

    @log(logger=logger)
    def _construct_all_points_histogram(
        self, event_generator, plot_type, bins=None, sizes=False
    ):
        """
        Build a combined histogram across all event current values.

        :param event_generator: Generator yielding individual event data.
        :type event_generator: Iterator[dict]
        :param plot_type: Type of histogram to create (raw or filtered).
        :type plot_type: str
        :param bins: Number of histogram bins.
        :type bins: int | None
        :return: DataFrame with histogram values and corresponding current levels.
        :rtype: pd.DataFrame
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
            padding_before = int(event["padding_before"] * event["samplerate"] * 1e-6)
            baseline = np.median(timeseries[:padding_before])
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
            event_hist, _ = np.histogram(
                np.sign(baseline) * timeseries - np.sign(baseline) * baseline,
                bins=bin_edges,
            )
            hist += event_hist
        bincenters = bin_edges[:-1] + np.diff(bin_edges) / 2.0
        return pd.DataFrame({"Current": bincenters, "Count": hist})

    @log(logger=logger)
    def set_baseline_duration(self, duration):
        """
        a callback from a global_signal call that sets the baseline_duration variable for further processing
        """
        self.baseline_duration = duration

    @log(logger=logger)
    def _construct_event_overlay(self, event_generator, plot_type, loader):
        """
        Overlay multiple event traces in a normalized time plot.

        :param event_generator: Generator of events to overlay.
        :type event_generator: Iterator[dict]
        :param plot_type: Either 'Raw Event Overlay' or 'Filtered Event Overlay'.
        :type plot_type: str
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
            alpha = (
                15
                / num_events
                * (1 - 0.99 * (duration - min_duration) / (max_duration - min_duration))
            )
            alpha = np.min((alpha, 0.5))
            ax.plot(time, data, alpha=alpha, color="b")

        ax.set_xlim(left=-0.333, right=1.333)
        ax.set_xlabel("Normalized Time")
        ax.set_ylabel("Rectified Current (pA)")

        self.canvas.draw()
        self.no_cached_data = True

    @log(logger=logger)
    def set_event_data_generator(self, generator):
        """
        Set the event data generator for event-based plots.

        :param generator: A generator that yields event data.
        :type generator: Iterator[dict]
        """
        self.event_data_generator = generator

    @log(logger=logger)
    def _undo_plot(self):
        """
        Undo the last plotted action and update the action history.
        """
        self.update_tab_action_history.emit(None, True)

    @log(logger=logger)
    def _save_filter(self):
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
    def _load_filter(self, parameters):
        """
        Load filters from a JSON file, validate them if loader is available,
        reset UI, and apply loaded filters.
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Filters", os.path.expanduser("~"), "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, "r") as f:
                new_filters = json.load(f)

            if not isinstance(new_filters, dict):
                raise ValueError("Invalid filter file format. Expected a dictionary.")

            combo = self.metadatacontrols.filter_comboBox

            # Reset UI and internal state
            combo.blockSignals(True)
            combo.clear_selection_list()
            combo.blockSignals(False)

            self.subset_filters.clear()

            # Get loader for validation
            loader = parameters.get("db_loader")

            if not loader:
                self.logger.warning(
                    "No loader found – filters loaded but not validated."
                )

            # Store pending validations if loader exists
            for name, filter_text in new_filters.items():
                if loader:
                    # Save temporarily in case validation passes
                    self._pending_filter_name = name
                    self._pending_filter_text = filter_text

                    self.global_signal.emit(
                        "MetaDatabaseLoader",
                        loader,
                        "construct_metadata_query",
                        (
                            ["event_id", "sublevel_current", "voltage"],
                            filter_text,
                            None,
                        ),
                        "relay_query",
                        ("validate_new_filter",),
                    )
                else:
                    # Add unvalidated filter
                    self.subset_filters[name] = filter_text
                    combo.addItem(name)
                    combo.selectItem(name, select=True)

            combo.refreshDisplayText()
            self.logger.info(f"Filters loaded from {path}")

        except Exception as e:
            self.logger.error(f"Failed to load filters: {e}")

    @log(logger=logger)
    @Slot(str, str, tuple)
    def handle_parameter_change(self, submodel_name, action_name, args):
        """
        Handle changes triggered by UI controls such as updates to axis selection or filters.

        :param submodel_name: Name of the submodel that triggered the action.
        :type submodel_name: str
        :param action_name: Name of the action triggered.
        :type action_name: str
        :param args: Tuple containing action-specific arguments.
        :type args: tuple
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
    def _shift_range_and_update_plot(self, parameters, direction):
        """Shift ranges in the GUI and update plot and input if valid."""

        original_str = self._get_event_index_text()
        self.logger.debug(f"Original GUI input string: {original_str}")
        if not original_str:
            self.logger.error("Event index input is empty.")
            return

        parsed = self._parse_event_indices(original_str, False)
        self.logger.debug(f"Parsed input into ranges: {parsed}")

        shifted = self._shift_ranges(parsed, direction, 1)
        self.logger.debug(f"Shifted ranges ({direction}): {shifted}")

        merged = self._merge_ranges(shifted)
        self.logger.debug(f"Merged shifted ranges: {merged}")

        new_event_str = self._format_ranges(merged)
        self.logger.debug(f"Formatted string for GUI: {new_event_str}")

        expanded = self._expand_event_indices(new_event_str)
        self.logger.debug(f"Expanded list for plotting: {expanded}")

        if not expanded:
            self.logger.warning("Indices must be positive")
            return

        # Proceed with valid shift
        new_params = parameters.copy()
        new_params["event_index"] = expanded
        self.logger.debug(f"Updated parameters for plot: {new_params}")

        self._handle_plot_events(new_params)
        self.logger.debug(
            f"Shifting complete. Updating input field to: {new_event_str}"
        )
        self.metadatacontrols.set_event_index_input(new_event_str)

    def _get_event_index_text(self) -> str:  # Since params expanded
        """
        Get the current text from the event index input field.

        :return: Stripped text content of the event index field.
        :rtype: str
        """
        return self.metadatacontrols.event_index_lineEdit.text().strip()

    @log(logger=logger)
    def set_event_plot_data_generator(self, generator):
        """
        :param generator: a generator of event data
        :type generator: Generator[Dict[str, Any]]

        A callback from a global signal call that sets the generator to be used to construct event plots and overlays
        """
        self.plot_events_generator = generator
        self.plot_events_generator_updated = True

    @log(logger=logger)
    def _handle_plot_events(self, parameters):
        """
        Handle loading and plotting of selected events based on provided parameters.

        :param parameters: Dictionary containing eventfinder, filter, channels, and event indices.
        :type parameters: dict
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
            self.add_text_to_display(
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

        event_index = parameters["event_index"]

        sql_filter = next(iter(selected_filters.values()))
        exp_and_ch = self.selected_experiment_and_channels_by_loader[loader_name]
        exp = next(
            iter(self.selected_experiment_and_channels_by_loader[loader_name].keys())
        )
        channel = next(
            iter(self.selected_experiment_and_channels_by_loader[loader_name].values())
        )[0]

        if not (
            sql_filter == self.current_sql_filter
            and self.current_experiment == exp
            and self.current_channel == channel
            and self.plot_events_generator is not None
        ):
            # only load a new generator if the old one is invalid after explicitly aborting the current one
            if self.plot_events_generator is not None:
                try:
                    try:
                        new_event = self.plot_events_generator.send(True)
                    except StopIteration:
                        pass
                except TypeError:
                    try:
                        new_event = next(self.plot_events_generator)
                        new_event = self.plot_events_generator.send(True)
                    except StopIteration:
                        pass
                self.cached_events = {}
                self.plot_events_generator = None

            loader = parameters["db_loader"]
            load_event_data_args = (sql_filter, exp_and_ch)
            self.plot_events_generator_updated = False
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "load_event_data",
                load_event_data_args,
                "relay_event_plot_data_generator",
                (),
            )
            if self.plot_events_generator_updated is True:
                self.current_sql_filter = sql_filter
                self.current_experiment = exp
                self.current_channel = int(channel) if channel is not None else None

        event_index = parameters["event_index"]
        data_list = []

        for index in event_index:
            cached_event = self.cached_events.get(index)
            if cached_event is not None:
                data_list.append(cached_event)
                continue
            else:
                while True:
                    new_event = None
                    try:
                        if self.plot_events_generator is not None:
                            try:
                                new_event = self.plot_events_generator.send(False)
                            except TypeError:
                                new_event = next(self.plot_events_generator)
                        else:
                            raise AttributeError(
                                "Establish a plot events generator before trying to use it"
                            )
                    except StopIteration:
                        break
                    if new_event is not None:
                        self.cached_events[new_event["event_id"]] = new_event
                        if new_event["event_id"] == index:
                            data_list.append(new_event)
                            break
                        elif new_event["event_id"] > index:
                            break
        if data_list:
            self._update_event_plot(data_list)
        else:
            self.add_text_to_display.emit(
                f"No data available for plotting with indices in the specified range {event_index}",
                self.__class__.__name__,
            )
            self.logger.info(
                f"No data available for plotting with indices in the specified range {event_index}"
            )

    @log(logger=logger)
    def _update_event_plot(self, event_data):
        """
        Update the event plot with raw, filtered, and fitted traces for multiple events.

        Each event is plotted in its own subplot with time on the x-axis and current on the y-axis.
        The method also updates internal cache with data for interactive use (e.g., tooltips or exports).

        :param event_data: List of dictionaries, each containing the data and metadata for one event.
                        Each dictionary should have the keys:
                        'experiment_id', 'channel_id', 'event_id',
                        'raw_data', 'filtered_data', 'fit_data', and 'samplerate'.
        :type event_data: list[dict]
        :return: None
        :rtype: None
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.figure.clear()
        self._clear_cache()

        num_events = len(event_data)
        num_rows, num_cols = self._factors(num_events)
        j = 0
        for i, event in enumerate(event_data):
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
            ax.plot(time, raw_data / 1000, zorder=1)
            ax.plot(time, filtered_data / 1000, zorder=2)
            ax.plot(time, fit_data / 1000, zorder=3)

            x_label = r"Time (us)"
            y_label = r"Current (nA)"

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

        self.figure.set_constrained_layout(True)
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def _export_csv_subset(self, loader, filters, selection):
        """
        Open a dialog to export a filtered subset of the dataset.

        :param loader: Name of the active database loader.
        :type loader: str
        :param sql_filter: SQL WHERE clause used to filter the dataset.
        :type sql_filter: str
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
        result = dialog.get_result()
        result, name = result

        if result:
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
    def set_exported_event_count(self, written):
        """
        :param written: number of events successfully written
        :type written: int

        a global signal callback that provides the number of events written in a call to export events to csv format
        """
        self.exported_event_count = written

    @log(logger=logger)
    def set_query(self, query, table_name):
        """
        Set the SQL query and table name used in plotting.

        :param query: SQL query string.
        :type query: str
        :param table_name: Name of the database table.
        :type table_name: str
        """
        self.query = query
        self.table_name = table_name

    @log(logger=logger)
    def set_event_query(self, query):
        """
        a global signal callback that provides a valid SQL query for fetching event data
        """
        self.event_query = query

    @log(logger=logger)
    def set_units(self, units):
        """
        Set the units returned from the database for use in axis labels.

        :param units: List or string representing units.
        :type units: Any
        """
        self.units = units

    @log(logger=logger)
    def update_available_columns(self, loader):
        """
        Request available columns from the database loader.

        :param loader: Name of the active database loader.
        :type loader: str
        """
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
    def request_experiment_structure(self, loader_name: str):
        """
        :param loader_name: the key of the loader
        :type loader_name: str

        get a dict of all experiments and channels available in a specified MetaDatabaseLoader object
        """
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
    def update_units(self, loader, column, axis):
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
    def update_column_names(self, column_names):
        """
        Relay function to update the list of available columns.

        :param column_names: List of column names.
        :type column_names: List[str]
        """
        self.metadatacontrols.update_axes(column_names)

    @log(logger=logger)
    def update_column_units(self, column_units, axis):
        """
        Relay function to update the column unit label in the UI.

        :param column_units: Units to apply.
        :type column_units: str
        :param axis: Axis being updated.
        :type axis: str
        """
        self.metadatacontrols.update_column_units_label(column_units, axis)

    @log(logger=logger)
    def _handle_other_actions(self, action_name, parameters):
        """
        Raise an error for actions not yet implemented.

        :param action_name: The name of the unhandled action.
        :type action_name: str
        :param parameters: Parameters associated with the action.
        :type parameters: dict
        """
        raise NotImplementedError(f"{action_name} handler not implemented")

    @log(logger=logger)
    def _calculate_heatmap(
        self, xdata, ydata, logx=False, logy=False, bins=None, sizes=False
    ):
        """
        :param xdata: the data on the x axis
        :type xdata: npt.NDArray[np.float64]
        :param ydata: the data on the y axis
        :type ydata: npt.NDArray[np.float64]
        :param logx: logscale the x data before building the heatmap?
        :type logx: bool
        :param logy: logscale the y data before building the heatmap?
        :type logy: bool
        :param bins: number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning
        :type bins: Union[int, float]
        :param sizes: does the bins parameter refer to bin sizes (True) or widths (False)
        :type sizes: bool

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
    def _show_add_filter_dialog(self, parameters: dict):
        """
        Displays the dialog for adding a new subset filter. Validates filter syntax
        before actually saving the filter.

        :param parameters: Dictionary with 'db_loader'.
        """
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
            name = dialog.name
            filter_text = dialog.filter_text
            loader = parameters["db_loader"]

            if not loader:
                self.logger.error("No database loader selected")
                return

            # Store pending data for use in relay_query
            self._pending_filter_name = name
            self._pending_filter_text = filter_text
            self._pending_old_filter_name: Optional[str] = None

            # Validate filter via construct_metadata_query
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "construct_metadata_query",
                (
                    ["event_id", "sublevel_current", "voltage"],
                    filter_text,
                    None,
                ),  # using event_id as placeholder column
                "relay_query",
                ("validate_new_filter",),
            )

    @log(logger=logger)
    def clear_pending_filter_state(self):
        """
        reset all filters to factory settings
        """
        self._pending_filter_name = None
        self._pending_filter_text = None
        self._pending_old_filter_name = None

    @log(logger=logger)
    def _show_filter_info_dialog(self, comboBox, parameters):
        """
        Called when clicking the edit button for filters with multiple selection.

        Validates that exactly one filter is selected and delegates to the edit dialog.

        :param comboBox: The combo box containing the list of selectable filters.
        :type comboBox: MultiSelectComboBox
        """
        loader = parameters["db_loader"]
        selected = comboBox.getSelectedItems()
        if len(selected) != 1:
            self.logger.warning("Please select exactly one filter to edit.")
            return

        self.show_edit_filter_dialog(selected[0], loader)

    @log(logger=logger)
    def show_edit_filter_dialog(self, name: str, loader: str):
        """
        Displays the dialog to edit an existing filter, and validates the updated
        SQL filter syntax via construct_metadata_query before saving it.

        :param name: The name of the filter to edit.
        :param parameters: Dictionary with context, must include 'db_loader'.
        """
        self.logger.debug(f"Editing filter: {name}")
        self.logger.debug(f"Filters available: {self.subset_filters}")

        dialog = EditSubsetFilterDialog(self, name, self.subset_filters)

        if dialog.exec():
            new_name = dialog.new_name
            new_filter = dialog.new_filter

            self.logger.debug(f"Updated filter: {name} -> {new_name}: {new_filter}")

            if not loader:
                self.logger.error("No database loader selected")
                return

            # Store pending update info to be committed in relay_query after validation
            self._pending_filter_name = new_name
            self._pending_filter_text = new_filter
            self._pending_old_filter_name = name  # important for replacing key

            # Emit signal to validate the updated filter
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "construct_metadata_query",
                (["event_id", "sublevel_current", "voltage"], new_filter, None),
                "relay_query",
                ("validate_edited_filter",),
            )

    @log(logger=logger)
    def _delete_filter_by_name(self, name: str):
        """
        Deletes a single filter by name.

        :param name: The name of the filter to delete.
        :type name: str
        """
        self._delete_filter(name)

    @log(logger=logger)
    def _delete_all_selected_filters(self):
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
    def _delete_filter(self, name: str):
        """
        Internal method to remove a filter and update the UI.
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
    def replace_filter_item(self, name):
        """
        Remove any existing filter item with the same name and add the new one.
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
    def update_filter_name(self, old_name, new_name):
        """
        Replace old filter name with new one in the ComboBox, removing any duplicates.
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

    def get_walkthrough_steps(self):
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
                "Then, enter the index or ranges of events you want to visualize.",
                "MetadataView",
                lambda: [self.metadatacontrols.event_index_lineEdit],
            ),
            (
                "Metadata Tab",
                "Then, click 'Plot Events' to visualize the selected entries.",
                "MetadataView",
                lambda: [self.metadatacontrols.plot_events_pushButton],
            ),
            (
                "Metadata Tab",
                "Use the arrows to quickly navigate between filtered/unfiltered events.",
                "MetadataView",
                lambda: [
                    self.metadatacontrols.left_arrow_button,
                    self.metadatacontrols.right_arrow_button,
                ],
            ),
        ]

    def get_current_view(self):
        return "MetadataView"


def format_axis_label(label: str, unit: str) -> str:
    """
    Ensure the axis label contains the correct unit exactly once.
    Removes any existing trailing unit in parentheses.
    """
    label = re.sub(r"\s*\(.*?\)$", "", label)  # Remove trailing "(...)"
    return f"{label} ({unit})" if unit else label
