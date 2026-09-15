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
from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple, override

import numpy as np
import numpy.typing as npt
from matplotlib.axes import Axes
from PySide6.QtCore import Slot

from poriscope.plugins.analysistabs.MetadataModel import MetadataModel
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabController import MetaSubsetTabController


@inherit_docstrings
class MetadataController(MetaSubsetTabController):
    """
    Subclass of MetaSubsetTabController for managing metadata view-model logic.

    Relays plot data, query results, and column/unit updates to the view.
    """

    logger = logging.getLogger(__name__)

    #: The last SQL echoed to the status panel, so that replotting the same subset
    #: does not repeat it. Not persisted: it is display state, and a fresh session
    #: showing the query once more is the right behaviour.
    _last_echoed_query: str = ""

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the metadata view and model.
        """
        self.view = MetadataView()
        self.model = MetadataModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Wire this tab's own eleven intents on top of the four the subset base wires.

        :return: None
        :rtype: None
        """
        super()._setup_connections()
        self.view.column_units_requested.connect(self.request_column_units)
        self.view.column_type_requested.connect(self.request_column_type)
        self.view.metadata_subset_requested.connect(self.load_metadata_subset)
        self.view.all_points_histogram_requested.connect(
            self.build_all_points_histogram
        )
        self.view.event_overlay_requested.connect(self.build_event_overlay)
        self.view.event_plot_data_requested.connect(self.load_event_plot_data)
        self.view.plot_features_requested.connect(self.request_plot_features)
        self.view.csv_subset_export_requested.connect(self.export_csv_subset)
        self.view.heatmap_requested.connect(self.calculate_heatmap)
        self.view.scatterplot_3d_requested.connect(self.filter_3d_scatterplot)
        self.view.density_requested.connect(self.estimate_kernel_densities)
        self.view.histogram_bins_requested.connect(self.calculate_histogram_bins)
        self.view.capture_rate_requested.connect(self.fit_capture_rate)
        self.view.categorical_counts_requested.connect(self.count_categories)

    @log(logger=logger)
    @Slot(object, object, object, object, bool, object, str, str, str)
    def calculate_heatmap(
        self,
        xdata: npt.NDArray[np.float64],
        ydata: npt.NDArray[np.float64],
        log_flags: Sequence[bool],
        bins: Any,
        sizes: bool,
        ax: Axes,
        x_label: str,
        y_label: str,
        dataset_label: str,
    ) -> None:
        """
        Filter and bin the heatmap's two columns, and hand the result back to draw.

        Decision B's command path, the same shape as
        ``ClusteringController.cluster``. The drawing context arrives and departs
        unchanged; this slot marshals and does not interpret it.

        An invalid bin entry raises out of the Model, and is reported here rather
        than propagating: before Step 4c it escaped the plotting call unhandled,
        because nothing between here and ``_overlay_plot`` catches it.

        :param xdata: the raw x values
        :type xdata: npt.NDArray[np.float64]
        :param ydata: the raw y values
        :type ydata: npt.NDArray[np.float64]
        :param log_flags: log-scale the x and y values before binning?
        :type log_flags: Sequence[bool]
        :param bins: number of bins, or size of bins when sizes is True, or None to estimate
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or counts (False)
        :type sizes: bool
        :param ax: the axis object the View will draw on
        :type ax: Axes
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param y_label: the y axis label, already formatted
        :type y_label: str
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        try:
            xfiltered, yfiltered = self.model.logscale_and_filter_columns(
                xdata, ydata, log_flags=list(log_flags)
            )
            x, y, z = self.model.calculate_heatmap(xfiltered, yfiltered, bins, sizes)
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to build the heatmap: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to build the heatmap: {e}", self.__class__.__name__
            )
            return
        self.view.set_heatmap(x, y, z, ax, x_label, y_label, dataset_label)

    @log(logger=logger)
    @Slot(object, object, object, object, str)
    def filter_3d_scatterplot(
        self,
        columns: Sequence[npt.NDArray[np.float64]],
        log_flags: Sequence[bool],
        ax: Axes,
        axis_labels: Sequence[str],
        dataset_label: str,
    ) -> None:
        """
        The same for a 3-D scatterplot's three columns.

        Separate from :meth:`filter_scatterplot` because the View's two drawing
        halves are separate: a 3-D scatter rebuilds the axes and carries a z label.

        :param columns: the raw x, y and z values
        :type columns: Sequence[npt.NDArray[np.float64]]
        :param log_flags: log-scale each column?
        :type log_flags: Sequence[bool]
        :param ax: the axis object the View will draw on
        :type ax: Axes
        :param axis_labels: the axis labels, already formatted
        :type axis_labels: Sequence[str]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        try:
            filtered = self.model.logscale_and_filter_columns(
                *columns, log_flags=list(log_flags)
            )
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to filter the 3D scatterplot: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to filter the 3D scatterplot: {e}", self.__class__.__name__
            )
            return
        self.view.set_3d_scatterplot(filtered, ax, axis_labels, dataset_label)

    @log(logger=logger)
    @Slot(object, bool, object, bool, object, object, object, str, str, str)
    def estimate_kernel_densities(
        self,
        datasets: Sequence[npt.NDArray[np.float64]],
        logx: bool,
        bins: Any,
        sizes: bool,
        hist_min: Optional[float],
        hist_max: Optional[float],
        ax: Axes,
        x_label: str,
        column: str,
        dataset_label: str,
    ) -> None:
        """
        Filter every overlaid dataset, then estimate each one's density.

        Decision B's command path, the same shape as :meth:`calculate_heatmap`. The
        drawing context arrives and departs unchanged; this slot marshals and does
        not interpret it.

        The newest dataset is the last of ``datasets`` and has not been accumulated
        by the View yet, so a subset that loses every point to the filter is refused
        here and leaves no label behind.

        :param datasets: one raw column array per overlaid dataset, newest last
        :type datasets: Sequence[npt.NDArray[np.float64]]
        :param logx: log-scale the values before binning them?
        :type logx: bool
        :param bins: number of bins, or size of bins when sizes is True, or None to estimate
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or counts (False)
        :type sizes: bool
        :param hist_min: the shared lower limit so far, or None for the first dataset
        :type hist_min: Optional[float]
        :param hist_max: the shared upper limit so far, or None for the first dataset
        :type hist_max: Optional[float]
        :param ax: the axis object the View will draw on
        :type ax: Axes
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param column: the column's own name, for the message when nothing survives
        :type column: str
        :param dataset_label: the newest dataset's label
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        try:
            filtered = self.model.logscale_and_filter_datasets(datasets, logx)
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to filter the density plot: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to filter the density plot: {e}", self.__class__.__name__
            )
            return

        if len(filtered[-1]) == 0:
            # Every point was filtered out, the commonest cause being a column that
            # is NULL for every row the subset filter selected.
            self.add_text_to_display.emit(
                f"No {column} values in this subset, so there is nothing to plot",
                self.__class__.__name__,
            )
            return

        hist_min, hist_max = self.model.widen_shared_limits(
            filtered[-1], hist_min, hist_max
        )

        try:
            densities = self.model.kernel_densities(
                filtered, bins, sizes, hist_min, hist_max
            )
        except (ValueError, TypeError, IndexError, np.linalg.LinAlgError) as e:
            self.logger.error(f"Unable to estimate the density: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to estimate the density: {e}", self.__class__.__name__
            )
            return

        self.view.set_kernel_densities(
            datasets[-1], dataset_label, densities, hist_min, hist_max, ax, x_label
        )

    @log(logger=logger)
    @Slot(object, bool, object, bool, object, object, bool, object, str, str, str)
    def calculate_histogram_bins(
        self,
        datasets: Sequence[npt.NDArray[np.float64]],
        logx: bool,
        bins: Any,
        sizes: bool,
        hist_min: Optional[float],
        hist_max: Optional[float],
        norm: bool,
        ax: Axes,
        x_label: str,
        column: str,
        dataset_label: str,
    ) -> None:
        """
        Filter every overlaid dataset, bin them onto shared edges, and count them.

        Decision B's command path, the same shape as
        :meth:`estimate_kernel_densities` - deliberately, since the two write the
        same accumulator and the same pair of shared limits, which is why they
        converted in one branch rather than one each.

        :param datasets: one raw column array per overlaid dataset, newest last
        :type datasets: Sequence[npt.NDArray[np.float64]]
        :param logx: log-scale the values before binning them?
        :type logx: bool
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin size (True) or a count (False)
        :type sizes: bool
        :param hist_min: the shared lower limit so far, or None for the first dataset
        :type hist_min: Optional[float]
        :param hist_max: the shared upper limit so far, or None for the first dataset
        :type hist_max: Optional[float]
        :param norm: normalise each dataset to a fraction rather than a count
        :type norm: bool
        :param ax: the axis object the View will draw on
        :type ax: Axes
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param column: the column's own name, for the message when nothing survives
        :type column: str
        :param dataset_label: the newest dataset's label
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        try:
            filtered = self.model.logscale_and_filter_datasets(datasets, logx)
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to filter the histogram: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to filter the histogram: {e}", self.__class__.__name__
            )
            return

        if len(filtered[-1]) == 0:
            self.add_text_to_display.emit(
                f"No {column} values in this subset, so there is nothing to "
                "histogram",
                self.__class__.__name__,
            )
            return

        hist_min, hist_max = self.model.widen_shared_limits(
            filtered[-1], hist_min, hist_max
        )

        try:
            _, bincenters, widths, counts = self.model.overlaid_histograms(
                filtered, bins, sizes, hist_min, hist_max, norm
            )
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to bin the histogram: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to bin the histogram: {e}", self.__class__.__name__
            )
            return

        self.view.set_histogram_bins(
            datasets[-1],
            dataset_label,
            bincenters,
            widths,
            counts,
            hist_min,
            hist_max,
            ax,
            x_label,
            logx,
            norm,
        )

    @log(logger=logger)
    @Slot(object, object, object, str, str)
    def count_categories(
        self,
        datasets: List[npt.NDArray[Any]],
        labels: List[str],
        ax: Axes,
        x_label: str,
        y_label: str,
    ) -> None:
        """
        Tally each overlaid dataset's categories, and hand them back to be drawn.

        Decision B's command path, the same shape as :meth:`estimate_kernel_densities`.
        The drawing context arrives and departs unchanged; this slot marshals and does
        not interpret it.

        A column of a type the tally cannot sort raises out of the Model and is reported
        here rather than escaping a Qt slot - which is what used to happen, since
        nothing between the View and ``_overlay_plot`` catches it.

        :param datasets: one array of raw column values per overlaid dataset
        :type datasets: List[npt.NDArray[Any]]
        :param labels: one label per dataset, index-aligned with datasets
        :type labels: List[str]
        :param ax: the axis object the View will draw on
        :type ax: Axes
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param y_label: the y axis label
        :type y_label: str
        :return: None
        :rtype: None
        """
        try:
            counts = self.model.categorical_counts(datasets)
        except (TypeError, ValueError) as e:
            self.logger.error(f"Unable to count categories: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to count categories: {e}", self.__class__.__name__
            )
            return
        self.view.set_categorical_counts(counts, labels, ax, x_label, y_label)

    @log(logger=logger)
    @Slot(object, object, bool, object, str, str, str)
    def fit_capture_rate(
        self,
        data: npt.NDArray[np.float64],
        bins: Any,
        sizes: bool,
        ax: Axes,
        x_label: str,
        y_label: str,
        dataset_label: str,
    ) -> None:
        """
        Bin and fit the capture rate, and hand the result back to the View to draw.

        Decision B's command path, the same shape as :meth:`calculate_heatmap`. A
        fit that will not converge raises ``RuntimeError`` out of ``curve_fit``, and
        is reported rather than allowed to escape a Qt slot.

        **The inter-event times are computed here rather than in the View**, which is
        where they were until Step 4's closeout: gaps between consecutive events are the
        measurement, not the drawing. Both conditions the View used to judge on them move
        with the computation - too little surviving data is reported instead of raised,
        which reaches the user with the count in it rather than as ``update_plot``'s
        generic "no data available after filtering".

        :param data: the event times as they came out of the column, unsorted
        :type data: npt.NDArray[np.float64]
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param ax: the axis object the View will draw on
        :type ax: Axes
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param y_label: the y axis label
        :type y_label: str
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        initial_length = len(data)
        log_times = self.model.interevent_log_times(data)

        if len(log_times) < 10:
            self.add_text_to_display.emit(
                f"Not enough data passes the log filter: {len(log_times)} is not "
                "enough to estimate capture rate - skipping",
                self.__class__.__name__,
            )
            return

        if len(log_times) < initial_length:
            # Preserved exactly, including that a clean column always reports one row
            # dropped: the interval count is one less than the event count by
            # construction and the original counted that as a drop. Filed rather than
            # corrected here, so this move changes nothing the user sees.
            self.add_text_to_display.emit(
                f"{initial_length - len(log_times)} rows dropped by log filter",
                self.__class__.__name__,
            )

        try:
            bin_edges, bincenters, val, fit, rate, error = self.model.fit_capture_rate(
                log_times, bins, sizes
            )
        except (ValueError, TypeError, IndexError, RuntimeError) as e:
            self.logger.error(f"Unable to fit the capture rate: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to fit the capture rate: {e}", self.__class__.__name__
            )
            return
        self.view.set_capture_rate(
            bin_edges,
            bincenters,
            val,
            fit,
            rate,
            error,
            log_times,
            ax,
            x_label,
            y_label,
            dataset_label,
        )

    @log(logger=logger)
    @Slot(str, list, str, object)
    def load_metadata_subset(
        self,
        loader: str,
        columns: List[str],
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
    ) -> None:
        """
        Fetch one metadata subset - query, rows and units - and hand it to the View.

        Step 4a replaced three ``global_signal`` emits that ``_overlay_plot`` made in
        sequence, reading each answer back off an attribute on the next statement.
        Two of those attributes were never cleared first, so a dispatch that failed
        was indistinguishable from one that succeeded: ``self.query`` kept the
        previous subset's query and passed the ``== ""`` guard, and ``self.units``
        kept the previous column's units and was appended to the list, labelling the
        axis wrongly. The View clears all three now and this method sets them only
        once every part has been fetched, so a partial failure is visible as such.

        This is also where the SQL the user sees comes from: the query echoed to the
        status panel is **the one that runs**, not the smaller one that validated the
        filter, and it is echoed only when it differs from the last one shown.

        :param loader: the database loader plugin's key
        :type loader: str
        :param columns: the columns this plot type needs, in axis order
        :type columns: List[str]
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :return: None
        :rtype: None
        """
        try:
            query, debug, table_name = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "construct_metadata_query",
                columns,
                sql_filter,
                experiments_and_channels,
            )
        except Exception as e:
            # Previously swallowed by the dispatcher, which left the View reading the
            # previous subset's query back and plotting it under this subset's label.
            self.logger.error(f"Failed to build the subset query: {e!r}")
            self.add_text_to_display.emit(
                f"Could not build the query for this subset: {e}",
                self.__class__.__name__,
            )
            return

        if not query:
            self.add_text_to_display.emit(
                debug or "The subset query could not be built",
                self.__class__.__name__,
            )
            return

        try:
            plot_data = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "load_metadata",
                columns,
                sql_filter,
                experiments_and_channels,
            )
            units = [
                self.model.call(
                    "MetaDatabaseLoader", loader, "get_column_units", column
                )
                for column in columns
            ]
        except Exception as e:
            self.logger.error(f"Failed to load the subset: {e!r}")
            self.add_text_to_display.emit(
                f"Could not load this subset from {loader}: {e}",
                self.__class__.__name__,
            )
            return

        # Set together, after everything succeeded: the View's guards distinguish
        # "not fetched" from "fetched and empty", and a half-set bundle would break
        # that distinction.
        self.view.set_query(query, table_name)
        self.view.update_plot_data(plot_data)
        self.view.set_column_units(units)
        self._echo_applied_query(query, table_name)

    @log(logger=logger)
    def _fetch_event_subset(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
    ) -> Optional[Tuple[str, Generator]]:
        """
        Build one event-data subset's query and open a generator over its events.

        Shared by the two event-data plot types, which differ only in what they then
        reduce the events to. Reports its own failure and answers with None, so a
        caller has nothing to handle beyond stopping.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :return: the query that ran and a generator over its events, or None
        :rtype: Optional[Tuple[str, Generator]]
        """
        try:
            # Two values, because construct_event_data_query is declared
            # -> Tuple[str, str] and reports a filter it cannot build as
            # ("", debug). The bus splatted that pair across
            # relay_event_query(query, debug); call() hands it over whole, and a
            # 2-tuple is always truthy - so binding it to one name made the guard
            # below unable to fire and put the pair itself on the status panel.
            query, debug = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "construct_event_data_query",
                sql_filter,
                experiments_and_channels,
            )
        except Exception as e:
            self.logger.error(f"Failed to build the event subset query: {e!r}")
            self.add_text_to_display.emit(
                f"Could not build the event query for this subset: {e}",
                self.__class__.__name__,
            )
            return None

        if not query:
            self.add_text_to_display.emit(
                debug or "The event query for this subset could not be built",
                self.__class__.__name__,
            )
            return None

        try:
            generator = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "load_event_data",
                sql_filter,
                experiments_and_channels,
            )
        except Exception as e:
            self.logger.error(f"Failed to load the event subset: {e!r}")
            self.add_text_to_display.emit(
                f"Could not load this event subset from {loader}: {e}",
                self.__class__.__name__,
            )
            return None

        return query, generator

    @log(logger=logger)
    @Slot(str, str, object, str, object, bool, object, object, str)
    def build_all_points_histogram(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
        plot_type: str,
        bins: Any,
        sizes: bool,
        hist_min: Optional[float],
        hist_max: Optional[float],
        dataset_label: str,
    ) -> None:
        """
        Tally one event-data subset into an all-points histogram for the View.

        Decision B's command path. Step 4's closeout moved the tally down: the events
        themselves were being walked in the widget, twice, and nothing above the Model
        ever wanted them. The query is set only once the tally succeeded, which is
        what lets the View tell a fetch that failed from one that returned nothing.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :param plot_type: the all-points histogram variant being drawn
        :type plot_type: str
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param hist_min: the shared lower limit so far, or None for the first dataset
        :type hist_min: Optional[float]
        :param hist_max: the shared upper limit so far, or None for the first dataset
        :type hist_max: Optional[float]
        :param dataset_label: the label this subset is drawn under
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        fetched = self._fetch_event_subset(loader, sql_filter, experiments_and_channels)
        if fetched is None:
            return
        query, generator = fetched

        try:
            bincenters, counts, new_min, new_max = (
                self.model.build_all_points_histogram(
                    generator, plot_type, bins, sizes, hist_min, hist_max
                )
            )
        except (ValueError, TypeError, IndexError, KeyError) as e:
            self.logger.error(f"Unable to build the all points histogram: {e!r}")
            self.add_text_to_display.emit(
                f"Unable to build the all points histogram: {e}",
                self.__class__.__name__,
            )
            return

        self.view.set_event_query(query)
        self._echo_applied_query(query, "events")
        self.view.set_all_points_histogram(
            bincenters, counts, new_min, new_max, plot_type, dataset_label
        )

    @log(logger=logger)
    @Slot(str, str, object, str)
    def build_event_overlay(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
        plot_type: str,
    ) -> None:
        """
        Put one event-data subset on a shared normalised axis for the View to draw.

        Decision B's command path, the same shape as
        :meth:`build_all_points_histogram`.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :param plot_type: either 'Raw Event Overlay' or 'Filtered Event Overlay'
        :type plot_type: str
        :return: None
        :rtype: None
        """
        fetched = self._fetch_event_subset(loader, sql_filter, experiments_and_channels)
        if fetched is None:
            return
        query, generator = fetched

        try:
            traces = self.model.build_event_overlay(generator, plot_type)
        except (ValueError, TypeError, IndexError, KeyError) as e:
            self.logger.error(f"Unable to build the event overlay: {e!r}")
            self.add_text_to_display.emit(
                f"Unable to build the event overlay: {e}",
                self.__class__.__name__,
            )
            return

        self.view.set_event_query(query)
        self._echo_applied_query(query, "events")
        self.view.set_event_overlay(traces)

    @log(logger=logger)
    def _echo_applied_query(self, query: str, table_name: str) -> None:
        """
        Put the query that actually ran on the status panel, once per distinct query.

        What the panel used to show was the *validation* query built when the filter
        was created, which is a different query from the one that pulls the subset -
        it was built from a fixed three-column guess, so it joined all three metadata
        tables whatever the filter referenced. This shows the real one, whose joins
        are whatever the filter and the chosen axes actually need: one table,
        two or three.

        Deduplicated because a single plot builds one query per experiment and
        channel in scope and replotting is common, so echoing every one would bury
        the panel. Only a query that differs from the last one shown is echoed.

        :param query: the SQL that was run
        :type query: str
        :param table_name: the table its id column belongs to
        :type table_name: str
        :return: None
        :rtype: None
        """
        stripped = query.strip()
        if stripped == self._last_echoed_query:
            return
        self._last_echoed_query = stripped
        self.add_text_to_display.emit(
            f"SQL ({table_name}):\n{stripped}", self.__class__.__name__
        )

    @log(logger=logger)
    @Slot(str, str)
    def request_column_type(self, loader: str, column: str) -> None:
        """
        Fetch one column's declared type, for the categorical-histogram guard.

        Step 4a. The View clears the answer before asking, so a lookup that failed
        leaves it ``None`` and the guard refuses the plot - which is what the bus
        produced by accident, and is now what it produces on purpose.

        :param loader: the database loader plugin's key
        :type loader: str
        :param column: the column whose type is wanted
        :type column: str
        :return: None
        :rtype: None
        """
        try:
            column_type = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_type", column
            )
        except Exception as e:
            self.logger.error(f"Failed to read the type of column {column}: {e!r}")
            return
        self.view.set_column_type(column_type)

    @log(logger=logger)
    @Slot(str, list, object, object, object)
    def load_event_plot_data(
        self,
        loader: str,
        event_ids: List[int],
        exp: Optional[str],
        channel: Optional[int],
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
    ) -> None:
        """
        Load the full data of specific events, named by their ``event_id`` values.

        Step 4a replaced a three-emit chain the View ran a statement at a time:
        resolve the experiment name to an id, query the events table for the primary
        keys of those event_ids within the experiment and channel, then load exactly
        those rows. Each answer was parked on an attribute and read back on the next
        line, and each read was guarded only by having cleared the attribute first.

        The scoping is the reason the middle query exists at all: ``event_id`` is
        unique only within a channel, so an unscoped match picks up rows from other
        channels that happen to share one.

        **One behaviour change.** An experiment name that does not resolve now stops
        the plot and says so. Before, the bus swallowed the failure, the id came back
        ``None``, and the query ran *unscoped* - which is the same "plots the wrong
        subset" class of fault Step 4a's earlier commits fixed, silently returning
        another channel's events under this channel's label.

        :param loader: the database loader plugin's key
        :type loader: str
        :param event_ids: the event_id values to plot, already snapped to the cache
        :type event_ids: List[int]
        :param exp: the experiment the events belong to, or None to leave it out of scope
        :type exp: Optional[str]
        :param channel: the channel the events belong to, or None for all channels
        :type channel: Optional[int]
        :param experiments_and_channels: the scope handed on to ``load_event_data``
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :return: None
        :rtype: None
        """
        exp_id = None
        if exp is not None:
            try:
                exp_id = self.model.call(
                    "MetaDatabaseLoader", loader, "get_experiment_id_by_name", exp
                )
            except Exception as e:
                self.logger.error(f"Failed to resolve experiment {exp}: {e!r}")
                self.add_text_to_display.emit(
                    f"Could not look up experiment {exp} in {loader}: {e}",
                    self.__class__.__name__,
                )
                return
            if exp_id is None:
                self.add_text_to_display.emit(
                    f"{loader} has no experiment named {exp}, so these events cannot "
                    "be scoped to it",
                    self.__class__.__name__,
                )
                return

        try:
            id_result = self.model.resolve_event_ids(loader, event_ids, exp_id, channel)
        except Exception as e:
            self.logger.error(f"Failed to resolve event ids for {event_ids}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not look up these events in {loader}: {e}",
                self.__class__.__name__,
            )
            return

        if id_result is None or id_result.empty:
            self.add_text_to_display.emit(
                f"No data available for plotting with indices in the specified range {event_ids}",
                self.__class__.__name__,
            )
            return
        if "id" not in id_result.columns:
            # A populated result without the column it was asked for means the loader
            # did not honour its own contract, which is a different problem from an
            # empty subset and would raise on the read below.
            self.logger.error(
                f"{loader} returned rows with no id column for events {event_ids} "
                f"in experiment {exp} channel {channel}"
            )
            return

        db_ids = ",".join(str(i) for i in id_result["id"].tolist())
        try:
            generator = self.model.load_events_by_id(
                loader, db_ids, experiments_and_channels
            )
        except Exception as e:
            self.logger.error(f"Failed to load events {event_ids}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not load these events from {loader}: {e}",
                self.__class__.__name__,
            )
            return

        if generator is None:
            self.add_text_to_display.emit(
                f"No data available for plotting with indices in the specified range {event_ids}",
                self.__class__.__name__,
            )
            return

        self.view.set_event_plot_data_generator(generator)

    @log(logger=logger)
    @Slot(str, int, int, int)
    def request_plot_features(
        self, loader: str, experiment_id: int, channel_id: int, event_id: int
    ) -> None:
        """
        Fetch one event's fitted features and hand them to the View.

        Step 4a. Emitted once per event on the plot path, so a failure is logged and
        the event is plotted without features, as it was before - the View clears the
        six feature attributes before each request and reads them back after, so an
        event whose lookup failed gets none rather than the previous event's.

        ``update_features``' label-length validation is called here rather than
        inlined, and its ``ValueError`` is caught for the same reason the bus caught
        it: one fitter returning mismatched labels should not abandon the plot.

        :param loader: the database loader plugin's key
        :type loader: str
        :param experiment_id: the event's experiment id
        :type experiment_id: int
        :param channel_id: the event's channel id
        :type channel_id: int
        :param event_id: the event's id within that channel
        :type event_id: int
        :return: None
        :rtype: None
        """
        try:
            features = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "get_plot_features",
                experiment_id,
                channel_id,
                event_id,
            )
            self.update_features(*features)
        except Exception as e:
            self.logger.error(
                f"Features for event {event_id} in channel {channel_id} of "
                f"experiment {experiment_id} could not be loaded, skipping: {e!r}"
            )

    @log(logger=logger)
    @Slot(str, str, str, object, object, int)
    def export_csv_subset(
        self,
        loader: str,
        folder: str,
        name: str,
        subset_filter: Optional[str],
        experiments_and_channels: Optional[Dict[str, List[str]]],
        export_index: int,
    ) -> None:
        """
        Start writing one filtered subset to CSV in a worker thread.

        Step 4a, and the second emit in this step that was not an emit-then-read: the
        plugin returns a progress generator and the bus passed it straight into
        ``set_generator``, with the export's index, the loader key and the metaclass
        travelling as the bus's ``ret_args``. ``RawDataController.commit_events`` is
        the same shape.

        The View's index only advances for an export that was staged, which is what
        ``on_subset_export_started`` says - and *staged* now means "counted, non-empty,
        and handed to a worker". An export that fails partway through its generator
        still consumes its name, because by then it is a running job rather than a
        refused one.

        ``export_subset_to_csv`` is a **generator**, so ``call()`` only constructs it and
        the ``try/except`` below sees nothing that happens inside its body - including
        its own empty-subset check, which fires on the worker's first advance, after the
        index has already advanced. That is why the subset is counted first through
        ``count_subset_events``, which runs the same query the export runs, through the
        same builder. An empty subset is refused here, before a worker exists.

        :param loader: the database loader plugin's key
        :type loader: str
        :param folder: the folder to write the subset into
        :type folder: str
        :param name: the name to append to the exported filenames
        :type name: str
        :param subset_filter: the single selected filter, or None for the whole dataset
        :type subset_filter: Optional[str]
        :param experiments_and_channels: the experiment and channel scope
        :type experiments_and_channels: Optional[Dict[str, List[str]]]
        :param export_index: the index this export's worker is keyed under
        :type export_index: int
        :return: None
        :rtype: None
        """
        try:
            event_count = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "count_subset_events",
                subset_filter,
                experiments_and_channels,
            )
        except Exception as e:
            self.logger.error(f"Failed to count subset {name}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not export this subset from {loader}: {e}",
                self.__class__.__name__,
            )
            return

        if not event_count:
            self.add_text_to_display.emit(
                f"No events match {name}, so nothing was exported - "
                f"the name {name} is still available",
                self.__class__.__name__,
            )
            return

        try:
            generator = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "export_subset_to_csv",
                folder,
                name,
                subset_filter,
                experiments_and_channels,
            )
        except Exception as e:
            self.logger.error(f"Failed to export subset {name}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not export this subset from {loader}: {e}",
                self.__class__.__name__,
            )
            return

        self.model.set_generator(generator, export_index, loader, "MetaDatabaseLoader")
        self.model.run_generators(loader)
        self.view.on_subset_export_started()

    @log(logger=logger)
    @Slot(str, str, str)
    def request_column_units(self, loader: str, column: str, axis: str) -> None:
        """
        Fetch one column's units and apply them to one axis label.

        Step 4a. The axis travels with the request and back out again, which is what the
        bus carried in its ``ret_args``. This is Metadata's alone: ``update_units`` moved
        down from ``MetaSubsetTabView`` in the same commit, because the protein tab has no
        units label to write to.

        :param loader: the database loader plugin's key
        :type loader: str
        :param column: the column whose units are wanted
        :type column: str
        :param axis: the axis whose label they belong to
        :type axis: str
        :return: None
        :rtype: None
        """
        try:
            column_units = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_units", column
            )
        except Exception as e:
            self.logger.error(f"Failed to request units for column {column}: {repr(e)}")
            return
        self.view.update_column_units(column_units, axis)

    @log(logger=logger)
    def update_features(
        self,
        vertical: Optional[list[float]] = None,
        horizontal: Optional[list[float]] = None,
        points: Optional[list[tuple[float, float]]] = None,
        vlabels: Optional[list[str]] = None,
        hlabels: Optional[list[str]] = None,
        plabels: Optional[list[str]] = None,
    ) -> None:
        """
        Update the plot with visual annotations including vertical lines, horizontal lines, and point markers.

        Validates that each visual feature has a corresponding label (or explicit None) if labels are provided.

        :param vertical: Vertical line positions for the event being plotted.
        :type vertical: Optional[list[float]]
        :param horizontal: Horizontal line positions for the event being plotted.
        :type horizontal: Optional[list[float]]
        :param points: (x, y) point coordinates for the event being plotted.
        :type points: Optional[list[tuple[float, float]]]
        :param vlabels: Labels for the vertical lines.
        :type vlabels: Optional[list[str]]
        :param hlabels: Labels for the horizontal lines.
        :type hlabels: Optional[list[str]]
        :param plabels: Labels for the point markers.
        :type plabels: Optional[list[str]]
        :raises ValueError: If a label list is provided and its length does not match the corresponding feature list.
        """
        if (
            vertical is not None
            and vlabels is not None
            and len(vlabels) != len(vertical)
        ):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every vertical line feature, or no labels at all"
            )
        if (
            horizontal is not None
            and hlabels is not None
            and len(hlabels) != len(horizontal)
        ):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every horizontal line feature, or no labels at all"
            )
        if points is not None and plabels is not None and len(points) != len(plabels):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every point feature, or no labels at all"
            )
        self.view.update_plot_features(
            vertical, horizontal, points, vlabels, hlabels, plabels
        )
