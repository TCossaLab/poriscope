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

import logging
import warnings
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    override,
)

import matplotlib.pyplot as pl
import numpy as np
import numpy.typing as npt
from matplotlib.axes import Axes
from matplotlib.colorbar import Colorbar
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import Axes3D
from PySide6.QtCore import Signal, Slot

from poriscope.plugins.analysistabs.utils.metadatacontrols import MetadataControls
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import RESET_ACTION, log, register_action
from poriscope.utils.MetaSubsetTabControls import MetaSubsetTabControls
from poriscope.utils.MetaSubsetTabView import MetaSubsetTabView
from poriscope.views.widgets.dict_dialog_widget import DictDialog
from poriscope.views.widgets.walkthrough_mixin import (
    WalkthroughStep,
)

warnings.filterwarnings(
    "ignore",
    message="constrained_layout not applied because axes sizes collapsed to zero",
)


@inherit_docstrings
class MetadataView(MetaSubsetTabView):
    """
    Subclass of MetaSubsetTabView for visualizing and interacting with metadata plots.

    This view supports a wide variety of statistical visualizations, including:
    1D histograms, KDEs, capture rates, scatterplots, heatmaps, and event overlays.
    Also provides walkthroughs and export options.

    Attributes:
        subset_export_count (int): Counter for naming exported subsets.
        no_cached_data (bool): True if data is not cached due to size.
    """

    #: Asks the Controller for one column's units, for one axis label. The axis is
    #: carried so the answer can be applied to the right label, which is what the bus
    #: used its ``ret_args`` for. This tab is the only caller, which is why
    #: ``update_units`` moved down here from ``MetaSubsetTabView``.
    column_units_requested = Signal(str, str, str)

    #: Asks the Controller for a loader's column names, answered through
    #: ``update_column_names``. The Controller calls the loader itself, so a loader that
    #: cannot be read is reported rather than failing silently on the way back. This tab
    #: is the only caller, which is why ``update_available_columns`` moved down here
    #: from ``MetaSubsetTabView``.
    column_names_requested = Signal(str)

    #: Asks for one event's plot features - the lines, points and labels a fitter left
    #: behind. Emitted once per event on the plot path, and answered through
    #: ``update_plot_features``, which the Controller calls only when the lookup
    #: succeeded and the labels it returned match their features.
    plot_features_requested = Signal(str, int, int, int)

    #: Asks for a filtered subset to be written to CSV in a worker thread: the loader's
    #: key, the destination folder, the export's name, the single selected filter (or
    #: None for the whole dataset), the experiment/channel scope, and the index this
    #: export is keyed under. ``on_subset_export_started`` comes back if it was staged.
    csv_subset_export_requested = Signal(str, str, str, object, object, int, str)

    #: Asks the Controller to draw an overlay: the loader's key, the plot type, the x, y
    #: and z columns, their log flags, the bin request, the Sizes flag, the selected
    #: filters (name to SQL) and the scope. The intent a click captured, which is what the
    #: Controller records, so a replay draws what was asked for rather than what the
    #: panel shows then.
    overlay_plot_requested = Signal(str, str, list, list, object, bool, object, object)

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the MetadataView instance.
        """
        self._clear_cache()
        self.no_cached_data = False
        self.subset_export_count = 0
        self.hist_min: Optional[float] = None
        self.hist_max: Optional[float] = None
        # Set by set_event_plot_data_generator once the whole event-plot chain has
        # succeeded. None means it has not been fetched.
        self.plot_events_generator = None
        # Heterogeneous by design: the three 1-D paths - histogram, density and
        # categorical - append the raw column as a 1-D array, and the all-points
        # path appends an (x, y) tuple. Two shapes, not one: flagged for review,
        # since a single element type is the fix and it is a change of its own.
        self.hist_data: List[Any] = []
        self.hist_labels: List[Any] = []
        self.subset_filters = {}
        self.available_experiment_and_channels_by_loader: Dict[
            str, Dict[str, List[str]]
        ] = {}
        self.selected_experiment_and_channels_by_loader = {}
        self.allowed_plot_type: Optional[str] = None
        self.allowed_columns: List[str] = []
        self.allowed_logs: List[bool] = []
        # The bins list from the controls, as the overlay drawn was asked for it.
        self.allowed_bins: Optional[List[Union[int, float]]] = None
        self.allowed_sizes: Optional[bool] = None

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
        # list of tuples of things already plotted: (loader, experiment, channel, filter, subset name), which can be None

        # Cache for filter-aware event navigation — rebuilt only when filter/scope changes
        self.filtered_event_ids = []
        self.current_sql_filter = None
        self.current_experiment = None
        self.current_channel = None

    @property
    def _subset_controls(self) -> MetaSubsetTabControls:
        """
        The controls panel, under the name ``MetaSubsetTabView``'s shared methods use.

        Annotated with the base's type rather than ``MetadataControls`` so the override
        matches the declaration verbatim, which is what the plugin compliance test
        compares. Tab-specific code keeps using ``self.metadatacontrols``.

        :return: the panel built by ``_build_controls``
        :rtype: MetaSubsetTabControls
        """
        return self.metadatacontrols

    @log(logger=logger)
    def _build_controls(self) -> MetadataControls:
        """
        Build the tab's controls panel and keep it under this tab's own name.

        ``MetaView._set_control_area`` connects it and places it in the layout; the
        named attribute is kept because it is used throughout this tab.

        :return: the controls panel
        :rtype: MetadataControls
        """
        self.metadatacontrols = MetadataControls()
        return self.metadatacontrols

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
    @register_action(RESET_ACTION)
    def reset_plot(self, axis_type: str = "2d") -> None:
        """
        Clear the figure, create fresh axes and forget what was drawn.

        A recorded action: Undo replays from the last one, and a new figure starts with
        one. The Controller calls it when an overlay needs a new figure.

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
    @override
    def _reset_actions(self, axis_type: str = "2d") -> None:
        """
        Clear the figure; the same as :meth:`reset_plot`, which records it.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        """
        self.reset_plot(axis_type)

    @log(logger=logger)
    def axes_ready(self, axis_type: str = "2d") -> bool:
        """
        Can the next overlay be drawn on the current axes?

        Not when the figure holds more than one axes - the event grid Plot Events draws -
        or when the axes are stale or of the other projection.

        :param axis_type: Either '2d' or '3d', the projection the plot needs.
        :type axis_type: str
        :return: True if the current axes can take the plot
        :rtype: bool
        """
        return len(self.figure.axes) <= 1 and self._axes_valid(axis_type=axis_type)

    @log(logger=logger)
    def finish_plot(self) -> None:
        """
        Draw the canvas and hand the plotted data to the export cache, after a dataset.
        """
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def show_kernel_densities(
        self,
        values: npt.NDArray[np.float64],
        dataset_label: str,
        densities: Sequence[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]],
        hist_min: float,
        hist_max: float,
        x_label: str,
    ) -> None:
        """
        Draw one filled density curve per overlaid dataset.

        Called by ``MetadataController.overlay_plot``. The curve arrives already
        evaluated, so it is computed once rather than the three times drawing it would
        otherwise need. The newest dataset joins the overlay here as its **raw** column,
        because the Model re-filters every accumulated dataset on each update and a
        pre-filtered one would be filtered twice.

        :param values: the newest dataset's raw column values, to accumulate
        :type values: npt.NDArray[np.float64]
        :param dataset_label: the newest dataset's label
        :type dataset_label: str
        :param densities: one (positions, density) pair per dataset
        :type densities: Sequence[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        :param hist_min: the shared lower limit, widened by this dataset
        :type hist_min: float
        :param hist_max: the shared upper limit, widened by this dataset
        :type hist_max: float
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :return: None
        :rtype: None
        """
        self.hist_data.append(values)
        self.hist_labels.append(dataset_label)
        self.hist_min = hist_min
        self.hist_max = hist_max

        ax = self.axes
        ax.clear()
        self._clear_cache()

        y_label = "Probability Density"

        for (x, y), label in zip(densities, self.hist_labels, strict=True):
            ax.plot(x, y, label=label)
            ax.fill_between(x, y, alpha=0.3)
            self._update_cache((x, x_label), (y, y_label))

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.legend(loc="best")

    @log(logger=logger)
    def show_capture_rate(
        self,
        bin_edges: npt.NDArray[np.float64],
        bincenters: npt.NDArray[np.float64],
        val: npt.NDArray[np.float64],
        fit: npt.NDArray[np.float64],
        rate: float,
        error: float,
        data: npt.NDArray[np.float64],
        x_label: str,
        y_label: str,
        dataset_label: str,
    ) -> None:
        """
        Draw the inter-event time histogram and the exponential fitted to it.

        Called by ``MetadataController.overlay_plot``. The binning and the fit are
        made together below, so both describe the same intervals.

        The histogram is drawn on the **edges the fit was made against**, rather than
        on this widget's own binning of the same request. Handing matplotlib a bin
        count instead would let it bin independently, and the counts the fit used and
        the bars the user sees could then differ with nothing to say so.

        :param bin_edges: the edges the counts and the fit were computed on
        :type bin_edges: npt.NDArray[np.float64]
        :param bincenters: the center of each bin
        :type bincenters: npt.NDArray[np.float64]
        :param val: the counts in each bin
        :type val: npt.NDArray[np.float64]
        :param fit: the fitted curve evaluated at the bin centers
        :type fit: npt.NDArray[np.float64]
        :param rate: the fitted capture rate in Hz
        :type rate: float
        :param error: the 95% confidence half-width on the rate
        :type error: float
        :param data: the log inter-event times the histogram is built from
        :type data: npt.NDArray[np.float64]
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param y_label: the y axis label
        :type y_label: str
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        ax = self.axes
        ax.hist(
            data,
            bins=bin_edges,
            histtype="step",
            stacked=False,
            fill=False,
            label=dataset_label,
        )

        ax.plot(bincenters, fit, label=f"{rate:.3g} ± {error:.1g} Hz")

        self._update_cache((bincenters, x_label), (val, y_label))

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.legend(loc="best")

    @log(logger=logger)
    def show_histogram_bins(
        self,
        values: npt.NDArray[np.float64],
        dataset_label: str,
        bincenters: npt.NDArray[np.float64],
        widths: npt.NDArray[np.float64],
        counts: Sequence[npt.NDArray[np.float64]],
        hist_min: float,
        hist_max: float,
        x_label: str,
        logx: bool,
        norm: bool,
    ) -> None:
        """
        Draw every overlaid dataset onto one shared set of bin edges.

        Called by ``MetadataController.overlay_plot``. This is handed each
        dataset's tallies rather than the edges to tally against, and the edges
        themselves do not come back: nothing here draws with them once the counting is
        done elsewhere, and returning them would invite a second tally against them.

        :param values: the newest dataset's raw column values, to accumulate
        :type values: npt.NDArray[np.float64]
        :param dataset_label: the newest dataset's label
        :type dataset_label: str
        :param bincenters: the center of each bin, which the bars are drawn at
        :type bincenters: npt.NDArray[np.float64]
        :param widths: the width of each bin
        :type widths: npt.NDArray[np.float64]
        :param counts: one array of per-bin counts per overlaid dataset, index-aligned with the accumulated labels
        :type counts: Sequence[npt.NDArray[np.float64]]
        :param hist_min: the shared lower limit, widened by this dataset
        :type hist_min: float
        :param hist_max: the shared upper limit, widened by this dataset
        :type hist_max: float
        :param x_label: the x axis label, already formatted but not yet log-marked
        :type x_label: str
        :param logx: was the data log-scaled, and so should the label say so
        :type logx: bool
        :param norm: normalise each dataset to a fraction rather than a count
        :type norm: bool
        :return: None
        :rtype: None
        """
        self.hist_data.append(values)
        self.hist_labels.append(dataset_label)
        self.hist_min = hist_min
        self.hist_max = hist_max

        ax = self.axes
        ax.clear()
        self._clear_cache()

        # Every accumulated dataset is redrawn, against the tallies the Model made.
        for val, lab in zip(counts, self.hist_labels, strict=True):
            x_lab = x_label
            y_lab = "Count" if not norm else "Fraction"
            if logx:
                x_lab = f"log10({x_lab})"

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
    def show_categorical_counts(
        self,
        values: npt.NDArray[Any],
        dataset_label: str,
        counts: Sequence[Tuple[Sequence[str], npt.NDArray[np.float64]]],
        x_label: str,
        y_label: str,
    ) -> None:
        """
        Draw one bar series per overlaid dataset.

        The tallies are made by :meth:`MetadataModel.categorical_counts`, because
        counting occurrences is aggregation rather than drawing and the tallies are
        exported with the plot. The newest dataset joins the overlay here, once there is
        something to draw, as the histogram's and the density's do.

        :param values: the newest dataset's raw column values, to accumulate
        :type values: npt.NDArray[Any]
        :param dataset_label: the newest dataset's label
        :type dataset_label: str
        :param counts: per dataset, its category names and their counts, index-aligned with the accumulated labels
        :type counts: Sequence[Tuple[Sequence[str], npt.NDArray[np.float64]]]
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param y_label: the y axis label
        :type y_label: str
        :return: None
        :rtype: None
        """
        self.hist_data.append(values)
        self.hist_labels.append(dataset_label)

        ax = self.axes
        ax.clear()
        self._clear_cache()

        for (categories, val), lab in zip(counts, self.hist_labels, strict=True):
            ax.bar(
                categories,
                val,
                alpha=0.5,
                label=lab,
                align="center",
            )

            self._update_cache((categories, x_label), (val, y_label))

            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
        ax.tick_params(axis="x", rotation=45)
        ax.legend(loc="best")

    @log(logger=logger)
    def show_heatmap(
        self,
        x: npt.NDArray[np.float64],
        y: npt.NDArray[np.float64],
        z: npt.NDArray[np.float64],
        extent: Sequence[float],
        x_label: str,
        y_label: str,
        dataset_label: str,
    ) -> None:
        """
        Draw the binned heatmap, its colourbar and its cache entry.

        Called by ``MetadataController.overlay_plot``. The binning is made by
        ``MetadataModel``; everything here is matplotlib configuration, which stays
        because none of it leaves the View.

        :param x: bin-center x values
        :type x: npt.NDArray[np.float64]
        :param y: bin-center y values
        :type y: npt.NDArray[np.float64]
        :param z: the log2-scaled 2-D histogram counts
        :type z: npt.NDArray[np.float64]
        :param extent: the image's drawing bounds in bin-edge coordinates, ``[xmin, xmax, ymin, ymax]``
        :type extent: Sequence[float]
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param y_label: the y axis label, already formatted
        :type y_label: str
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        ax = self.axes
        im = ax.imshow(
            z,
            origin="lower",
            interpolation="gaussian",
            extent=extent,
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
    def show_scatterplot(
        self,
        columns: Sequence[npt.NDArray[np.float64]],
        axis_labels: Sequence[str],
        dataset_label: str,
    ) -> None:
        """
        Draw a scatterplot of two filtered columns on this View's own axes.

        :param columns: the filtered x and y values
        :type columns: Sequence[npt.NDArray[np.float64]]
        :param axis_labels: the x and y axis labels, already formatted
        :type axis_labels: Sequence[str]
        :param dataset_label: Label to apply to the scatter points.
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        self.set_scatterplot(columns, self.axes, axis_labels, dataset_label)

    @log(logger=logger)
    def show_3d_scatterplot(
        self,
        columns: Sequence[npt.NDArray[np.float64]],
        axis_labels: Sequence[str],
        dataset_label: str,
    ) -> None:
        """
        Draw a 3-D scatterplot of three filtered columns.

        Called by ``MetadataController.overlay_plot``, and the same reasoning as
        :meth:`set_scatterplot`. The axes are rebuilt here if they are 2-D, which a
        change of plot type can leave behind.

        :param columns: the filtered x, y and z values
        :type columns: Sequence[npt.NDArray[np.float64]]
        :param axis_labels: the x, y and z axis labels, already formatted
        :type axis_labels: Sequence[str]
        :param dataset_label: Label to apply to the scatter points.
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        xdata, ydata, zdata = columns
        x_label, y_label, z_label = axis_labels

        if not isinstance(self.axes, Axes3D):
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
        x: npt.NDArray[np.float64],
        y: npt.NDArray[np.float64],
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        dataset_label: str = "",
        norm: bool = False,
    ) -> None:
        """
        Plot a histogram of current values across all events (raw or filtered).

        :param ax: Matplotlib axes to draw the histogram on.
        :type ax: Axes
        :param x: the current level at the middle of each bin
        :type x: npt.NDArray[np.float64]
        :param y: how many samples fell in each bin
        :type y: npt.NDArray[np.float64]
        :param cols: Names for x and y axes.
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
            # Normalised, each curve is drawn with its peak at 1, and the export
            # carries the curve as drawn.
            shown = y if norm is False else y / np.max(y)
            ax.plot(x, shown, label=label)
            self._update_cache((x, x_label), (shown, y_label))

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.legend(loc="best")

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
    def show_all_points_histogram(
        self,
        bincenters: npt.NDArray[np.float64],
        counts: npt.NDArray[np.float64],
        hist_min: float,
        hist_max: float,
        plot_type: str,
        dataset_label: str,
    ) -> None:
        """
        Draw one subset's all-points histogram, and take the limits it widened.

        The tally is made by
        :meth:`MetadataModel.build_all_points_histogram`, because walking a subset's
        events and binning every sample of them is aggregation rather than drawing, and
        the result is exported with the plot.

        :param bincenters: the current level at the middle of each bin
        :type bincenters: npt.NDArray[np.float64]
        :param counts: how many samples fell in each bin
        :type counts: npt.NDArray[np.float64]
        :param hist_min: the shared lower limit, widened by this subset
        :type hist_min: float
        :param hist_max: the shared upper limit, widened by this subset
        :type hist_max: float
        :param plot_type: the all-points histogram variant being drawn
        :type plot_type: str
        :param dataset_label: the label this subset is drawn under
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        # The axes check first, then the limits: a reset clears the accumulated
        # limits, so taking them before it would throw away the ones this subset
        # just widened. The old arrangement set them inside the tally and then let
        # ``update_plot`` reset underneath it.
        if not self._axes_valid(axis_type="2d"):
            self._reset_actions(axis_type="2d")
        ax = self.axes

        self.hist_min = hist_min
        self.hist_max = hist_max

        norm = plot_type in [
            "Normalized Raw All Points Histogram",
            "Normalized Filtered All Points Histogram",
        ]
        self._plot_all_points_histogram(
            ax,
            bincenters,
            counts,
            ("Current", "Count"),
            ("pA", ""),
            dataset_label=dataset_label,
            norm=norm,
        )
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def show_event_overlay(
        self,
        traces: Sequence[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]],
    ) -> None:
        """
        Overlay one subset's event traces on a shared normalised time axis.

        The baseline subtraction and
        the per-event time base are made by :meth:`MetadataModel.build_event_overlay` -
        both are exported with the plot; what is left here is the drawing,
        including the alpha each trace is given - a shorter event is drawn more
        opaquely than a longer one so the short ones are not lost under the crowd, and
        that number is read by nothing outside these axes.

        :param traces: one (normalised time, rectified current) pair per event
        :type traces: Sequence[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        :return: None
        :rtype: None
        """
        ax = self.axes

        num_events = len(traces)
        durations = [len(data) for _, data in traces]
        min_duration = min(durations, default=float("inf"))
        max_duration = max(durations, default=float("-inf"))

        for time, data in traces:
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
            alpha = min(alpha, 0.5)
            ax.plot(time, data, alpha=alpha, color="b")

        ax.set_xlim(left=-0.333, right=1.333)
        ax.set_xlabel("Normalized Time")
        ax.set_ylabel("Rectified Current (pA)")

        self.canvas.draw()
        self.no_cached_data = True

    @log(logger=logger)
    def _undo_plot(self) -> None:
        """
        Undo the last plotted action and update the action history.
        """
        self.update_tab_action_history.emit(None, True)

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
            # Asked again each time, so experiments written into the loaded database
            # since it was chosen appear; the Controller answers synchronously.
            self.request_experiment_structure(loader)
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
            self._record_selection(parameters)
            self.overlay_plot_requested.emit(
                parameters["db_loader"],
                parameters["plot_type"],
                [parameters["x_axis"], parameters["y_axis"], parameters["z_axis"]],
                [parameters["x_log"], parameters["y_log"], parameters["z_log"]],
                parameters["bins"],
                parameters["sizes"],
                parameters["selected_filters"],
                parameters["experiments_and_channels"],
            )
        elif action_name == "reset_plot":
            self._reset_actions()
        elif action_name == "load_plot":
            # The file is read and replayed through load_actions_from_json and the
            # Controller; there is nothing to return here.
            self._load_actions_from_json()
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
    def _replot_after_shift(self, parameters: Dict[str, Any]) -> None:
        """
        Re-plot the events after navigation; this tab has no other event display.

        :param parameters: the navigation parameters, with ``event_id`` moved to the new event
        :type parameters: Dict[str, Any]
        """
        self._handle_plot_events(parameters)

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

        for channels in experiments_and_channels.values():
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
            subset_name = next(iter(selected_filters))
            if not self._rebuild_event_id_cache(
                loader, sql_filter, exp, channel, subset_name
            ):
                return
        elif not self.filtered_event_ids:
            # Worded exactly as _rebuild_event_id_cache words it, since the two are
            # the same finding reached by different routes: the cache is current and
            # empty here, rather than having just been rebuilt and come back empty.
            self.add_text_to_display.emit(
                "No filtered events found for the current scope.",
                self.__class__.__name__,
            )
            return

        ids = self.filtered_event_ids
        snap_idx = self._snap_to_filtered(event_id)
        snapped_event_ids = ids[snap_idx : snap_idx + n_events]
        snapped_start_id = snapped_event_ids[0]

        # Update the event_id field to reflect the snapped position
        self.metadatacontrols.set_event_id_input(snapped_start_id)

        # Ask for exactly these events' data. Resolving the snapped event_ids to
        # database ids is part of that request rather than something done here: the
        # ids have to be scoped to the current experiment and channel, because
        # event_id is only unique within a channel and an unscoped match silently
        # picks up rows from other channels that happen to share one.
        #
        # Cleared first: the Controller sets the generator only once the whole chain
        # has succeeded, and reports which part did not, so a failure here is not
        # mistaken for the previous plot's events.
        self.plot_events_generator = None
        self.event_plot_data_requested.emit(
            loader, snapped_event_ids, exp, channel, exp_and_ch, "events"
        )
        event_generator = self.plot_events_generator
        if event_generator is None:
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
            # Called with no arguments to clear all six before asking, for the same
            # reason the generator is cleared above: a lookup that fails leaves them
            # unset, and this event gets no features rather than the last one's.
            #
            # The try/except that used to wrap this emit is gone with it. It could
            # never fire: the bus swallowed every exception a plugin raised, and a
            # Qt slot's exception does not propagate back to the emitter either
            # (measured on PySide6 6.9.0 - emit returns normally and the traceback
            # goes to sys.excepthook), so the Controller reports failures itself.
            self.update_plot_features()
            self.plot_features_requested.emit(
                loader, experiment_id, channel_id, event_id_val
            )
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
            # strict: the caller appends to all seven lists once per event, so a
            # length mismatch is structurally impossible and means the caller is
            # broken. Silently truncating would instead leave the whole bottom
            # row of subplots without an x-axis label, since labelnum below is
            # computed from num_events rather than from the trip count.
            zip(
                event_data,
                vertical_lines,
                horizontal_lines,
                points,
                vertical_labels,
                horizontal_labels,
                point_labels,
                strict=True,
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

        The selected filter's name travels with its text, because a raw filter is a
        complete ``SELECT`` that the Controller has to bind to each selected channel
        before the export can use it.

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
        filter_name = ""
        if filters is not None:
            filter_name = next(iter(filters))
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

        # The export runs in a worker thread, so there is no answer to read back
        # here: the Controller stages the generator, starts it, and calls
        # on_subset_export_started only if it got that far. The try/except that used
        # to wrap this emit went with it - it could not catch a plugin failure, which
        # the bus swallowed before it, and cannot catch one now either, since a Qt
        # slot's exception does not propagate back to the emitter.
        self.csv_subset_export_requested.emit(
            loader,
            folder,
            name,
            filters,
            selection,
            self.subset_export_count,
            filter_name,
        )

    @log(logger=logger)
    def on_subset_export_started(self) -> None:
        """
        Move to the next export index, now that this one is running.

        The index names the export in the dialog and keys its worker, so it advances
        only for an export that was actually staged - which is what the Controller
        calling this says. The Controller counts the subset before staging anything,
        so an export refused for being empty never reaches here and the next dialog
        offers the same name again. Kept here rather than counted in the Controller
        because the dialog needs it before the request goes out, and one owner cannot
        drift from itself.

        :return: None
        :rtype: None
        """
        self.subset_export_count += 1

    @log(logger=logger)
    def update_units(self, loader: str, column: str, axis: str) -> None:
        """
        Ask the Controller for a column's units, for this tab's axis unit labels.

        On this tab rather than on ``MetaSubsetTabView``, although both subset tabs
        inherit that base: the protein tab has no units label, keeps no units cache and
        labels its axes with hardcoded literals, so it has nothing to do with the answer.
        Putting it back on the base would give that tab an inherited request nothing
        answers.

        :param loader: Name of the database loader.
        :type loader: str
        :param column: Name of the column to get units for.
        :type column: str
        :param axis: Axis being updated ('x_axis', 'y_axis', etc.).
        :type axis: str
        :return: None
        :rtype: None
        """
        # "No Event Database" is the combobox's placeholder, i.e. a normal empty state
        # rather than an error, so do not dispatch it as a plugin key.
        if not loader or loader == "No Event Database":
            return
        self.column_units_requested.emit(loader, column, axis)

    @log(logger=logger)
    def update_available_columns(self, loader: str) -> None:
        """
        Request available columns from the database loader.

        :param loader: Name of the active database loader.
        :type loader: str
        """
        if not loader or loader == "No Event Database":
            return
        self.column_names_requested.emit(loader)

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
