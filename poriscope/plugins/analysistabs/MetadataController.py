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


import copy
import logging
from typing import (
    Any,
    Dict,
    Generator,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    Union,
    override,
)

import numpy as np
import numpy.typing as npt
import pandas as pd
from PySide6.QtCore import Slot

from poriscope.plugins.analysistabs.MetadataModel import MetadataModel
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import RESET_ACTION, log, register_action
from poriscope.utils.MetaSubsetTabController import (
    MetaSubsetTabController,
    scope_placeholders,
    selected_pairs,
)
from poriscope.utils.MetaSubsetTabModel import FigureKind, OverlayState

#: The plot types drawn from a metadata subset's rows.
METADATA_PLOTS = (
    "Histogram",
    "Normalized Histogram",
    "Categorical Histogram",
    "Kernel Density Plot",
    "Capture Rate",
    "Heatmap",
    "Scatterplot",
    "3D Scatterplot",
)
#: The plot types drawn from a subset's events.
EVENT_DATA_PLOTS = (
    "Raw Event Overlay",
    "Filtered Event Overlay",
    "Raw All Points Histogram",
    "Normalized Raw All Points Histogram",
    "Filtered All Points Histogram",
    "Normalized Filtered All Points Histogram",
)
#: Plot types that draw one dataset only: one experiment, one channel, one subset.
_ONE_DATASET_PLOTS = ("Raw Event Overlay", "Filtered Event Overlay", "Heatmap")
#: Metadata plot types whose figure is drawn on a set of bins, so a bins or Sizes
#: change starts a new figure.
_BIN_SENSITIVE_PLOTS = (
    "Histogram",
    "Normalized Histogram",
    "Kernel Density Plot",
    "Capture Rate",
    "Heatmap",
)
#: The metadata plot types that take one bins entry rather than the list.
_ONE_BINS_ENTRY_PLOTS = (
    "Histogram",
    "Normalized Histogram",
    "Kernel Density Plot",
    "Capture Rate",
)
_ALL_POINTS_PLOTS = (
    "Raw All Points Histogram",
    "Normalized Raw All Points Histogram",
    "Filtered All Points Histogram",
    "Normalized Filtered All Points Histogram",
)


class MetadataSubset(NamedTuple):
    """
    One metadata subset, fetched whole: its rows, each plotted column's units, and the
    note added to its label when a raw query does not use the scope.
    """

    rows: pd.DataFrame
    units: List[Optional[str]]
    scope_note: str


def _one_bins_entry(bins: Any) -> Any:
    """
    The single bins entry a 1-D plot uses, from the list the controls send.

    :param bins: a one-or-more-element list from the controls, or None to estimate
    :type bins: Any
    :raises ValueError: if bins is a list with no entry, which typing only "," gives
    :return: the first entry, or None
    :rtype: Any
    """
    if bins is None:
        return None
    if isinstance(bins, list) and len(bins) >= 1:
        return bins[0]
    raise ValueError(f"Invalid bins entry {bins}")


@inherit_docstrings
class MetadataController(MetaSubsetTabController):
    """
    Subclass of MetaSubsetTabController for managing metadata view-model logic.

    Relays plot data, query results, and column/unit updates to the view.
    """

    logger = logging.getLogger(__name__)

    #: Redeclared with this tab's own types, so the type checker sees the methods
    #: the base View and Model do not have (see MetaController.view).
    view: MetadataView
    model: MetadataModel

    #: The last SQL echoed to the status panel, so that replotting the same subset
    #: does not repeat it. Not persisted: it is display state, and a fresh session
    #: showing the query once more is the right behaviour.

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
        Wire this tab's own six intents on top of the eight the subset base wires.

        :return: None
        :rtype: None
        """
        super()._setup_connections()
        self.view.column_units_requested.connect(self.request_column_units)
        self.view.column_names_requested.connect(self.request_column_names)
        self.view.plot_features_requested.connect(self.request_plot_features)
        self.view.csv_subset_export_requested.connect(self.export_csv_subset)
        self.view.overlay_plot_requested.connect(self.request_overlay_plot)
        self.view.reset_requested.connect(self.reset)

    @log(logger=logger)
    @register_action(RESET_ACTION)
    def reset(self, axis_type: str = "2d") -> None:
        """
        Clear the figure and forget what it held.

        A recorded action: Undo replays from the last one. Reset and Plot Events ask for
        it, and so does an overlay that needs a new figure.

        :param axis_type: Either '2d' or '3d', the projection of the fresh axes
        :type axis_type: str
        """
        self.model.overlay = OverlayState(figure=FigureKind.empty(axis_type))
        self.view.clear_plot(axis_type)

    @log(logger=logger)
    @Slot(str, str, list, list, object, bool, object, object)
    def request_overlay_plot(
        self,
        loader: str,
        plot_type: str,
        axes: List[Optional[str]],
        logs: List[bool],
        bins: Optional[List[Union[int, float]]],
        sizes: bool,
        filters: Dict[str, str],
        scope: Dict[str, List[str]],
    ) -> None:
        """
        Draw the overlay a click on Update Plot asked for, and roll back one that drew nothing.

        The roll-back is the click's alone; a replay calls :meth:`overlay_plot` directly.
        So is the categorical check, which refuses before anything is drawn or recorded.
        A refusal that left the figure as it was drops what it recorded - the reset a new
        figure starts with as well - so Undo does not spend a step restoring an identical
        figure; one that changed the figure - it cleared what was drawn, or drew part of
        the request - is undone, which redraws from the history.

        :param loader: the database loader plugin's key
        :type loader: str
        :param plot_type: the plot type chosen
        :type plot_type: str
        :param axes: the x, y and z columns, whichever the plot type uses
        :type axes: List[Optional[str]]
        :param logs: the x, y and z log-scale flags
        :type logs: List[bool]
        :param bins: a bin count, or a bin width when sizes is True, or None to estimate
        :type bins: Optional[List[Union[int, float]]]
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param filters: the selected filters, name to SQL
        :type filters: Dict[str, str]
        :param scope: the selected experiments and their channels
        :type scope: Dict[str, List[str]]
        :return: None
        :rtype: None
        """
        if plot_type == "Categorical Histogram" and not self._plots_as_categories(
            loader, axes[0]
        ):
            return
        before = set(self.model.overlay.datasets)
        recorded = len(self.tab_action_history)
        drawn = self.overlay_plot(
            loader, plot_type, axes, logs, bins, sizes, filters, scope
        )
        if drawn is False:
            if self.model.overlay.datasets == before:
                while len(self.tab_action_history) > recorded:
                    self.discard_last_tab_action()
            else:
                self.update_tab_actions(None, True)

    @log(logger=logger)
    @register_action("overlay_plot")
    def overlay_plot(
        self,
        loader: str,
        plot_type: str,
        axes: List[Optional[str]],
        logs: List[bool],
        bins: Optional[List[Union[int, float]]],
        sizes: bool,
        filters: Dict[str, str],
        scope: Dict[str, List[str]],
    ) -> bool:
        """
        Overlay every selected subset on the figure, or start a new figure for it.

        A recorded action: it takes the intent the click captured, so a replay draws what
        was recorded whatever the panel now shows. One dataset is drawn per experiment,
        channel and subset. Each is fetched, computed by the Model and drawn by the View;
        the figure is reset first when the plot type, a column, a log flag or - for a
        plot drawn on bins - the bins or Sizes differ from what is drawn, or when the
        View's axes cannot take this plot.

        :param loader: the database loader plugin's key
        :type loader: str
        :param plot_type: the plot type chosen
        :type plot_type: str
        :param axes: the x, y and z columns, whichever the plot type uses
        :type axes: List[Optional[str]]
        :param logs: the x, y and z log-scale flags
        :type logs: List[bool]
        :param bins: a bin count, or a bin width when sizes is True, or None to estimate
        :type bins: Optional[List[Union[int, float]]]
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param filters: the selected filters, name to SQL
        :type filters: Dict[str, str]
        :param scope: the selected experiments and their channels
        :type scope: Dict[str, List[str]]
        :return: True if at least one dataset was drawn
        :rtype: bool
        """
        selected: Dict[str, str] = dict(filters) if filters else {"Full Dataset": ""}
        datasets: Dict[Any, List[Any]] = (
            copy.deepcopy(scope) if scope else {None: [None]}
        )
        if plot_type not in METADATA_PLOTS and plot_type not in EVENT_DATA_PLOTS:
            self._say(f"Unsupported Plot Type: {plot_type}")
            return False
        if plot_type in _ONE_DATASET_PLOTS and not self._one_dataset(
            plot_type, selected, datasets
        ):
            return False

        plotted_any = False
        for exp, channels in datasets.items():
            for channel in channels:
                for subset_name, sql_filter in selected.items():
                    label = (
                        f"{loader} | {exp} Ch {channel}: {subset_name}"
                        if exp is not None
                        else f"{loader} | {subset_name}"
                    )
                    overlay = (
                        self._overlay_metadata_dataset
                        if plot_type in METADATA_PLOTS
                        else self._overlay_event_dataset
                    )
                    outcome = overlay(
                        loader,
                        plot_type,
                        axes,
                        logs,
                        bins,
                        sizes,
                        exp,
                        channel,
                        subset_name,
                        sql_filter,
                        label,
                    )
                    if outcome is None:
                        return False
                    plotted_any = plotted_any or outcome
        return plotted_any

    @log(logger=logger)
    def _one_dataset(
        self, plot_type: str, filters: Dict[str, str], scope: Dict[Any, List[Any]]
    ) -> bool:
        """
        Refuse a plot type that draws one dataset when more than one is selected.

        :param plot_type: the plot type chosen
        :type plot_type: str
        :param filters: the selected filters
        :type filters: Dict[str, str]
        :param scope: the selected experiments and their channels
        :type scope: Dict[Any, List[Any]]
        :return: True if one experiment, one channel and one subset are selected
        :rtype: bool
        """
        if len(scope) > 1:
            self._say(f"Only a single experiment can be used for {plot_type}")
            return False
        if any(len(channels) > 1 for channels in scope.values()):
            self._say(f"Only a single channel can be used for {plot_type}")
            return False
        if len(filters) > 1:
            self._say(f"Only a single subset can be used for {plot_type}")
            return False
        return True

    @log(logger=logger)
    def _overlay_metadata_dataset(
        self,
        loader: str,
        plot_type: str,
        axes: List[Optional[str]],
        logs: List[bool],
        bins: Optional[List[Union[int, float]]],
        sizes: bool,
        exp: Optional[str],
        channel: Optional[str],
        subset_name: str,
        sql_filter: str,
        label: str,
    ) -> Optional[bool]:
        """
        Fetch, compute and draw one metadata dataset, starting a new figure if needed.

        :param loader: the database loader plugin's key
        :type loader: str
        :param plot_type: one of the metadata plot types
        :type plot_type: str
        :param axes: the x, y and z columns
        :type axes: List[Optional[str]]
        :param logs: the x, y and z log-scale flags
        :type logs: List[bool]
        :param bins: the bins list from the controls, or None
        :type bins: Optional[List[Union[int, float]]]
        :param sizes: does bins refer to a bin width
        :type sizes: bool
        :param exp: the experiment, or None for no scope
        :type exp: Optional[str]
        :param channel: the channel as the selection tree reports it, or None
        :type channel: Optional[str]
        :param subset_name: the filter's name
        :type subset_name: str
        :param sql_filter: the filter's SQL
        :type sql_filter: str
        :param label: the dataset's label
        :type label: str
        :return: True if drawn, False if skipped, None if the whole plot must stop
        :rtype: Optional[bool]
        """
        view = self.view
        x_axis, y_axis, z_axis = axes
        x_log, y_log, z_log = logs
        columns: List[Any]
        logscales: List[bool]
        if plot_type == "3D Scatterplot":
            columns, logscales = [x_axis, y_axis, z_axis], [x_log, y_log, z_log]
            bins, sizes = None, False
        elif plot_type in ("Scatterplot", "Heatmap"):
            columns, logscales = [x_axis, y_axis], [x_log, y_log]
        elif plot_type == "Capture Rate":
            columns, logscales = ["start_time"], [True]
        else:
            columns, logscales = [x_axis], [x_log]

        if len(set(columns)) != len(columns):
            duplicate = next(c for c in columns if columns.count(c) > 1)
            self._say(
                "All columns should be different for a meaningful plot "
                f"(got '{duplicate}' more than once)."
            )
            return None

        axis_type = "3d" if plot_type == "3D Scatterplot" else "2d"
        state = self.model.overlay
        bins_changed = state.bins != bins
        sizes_changed = state.sizes != sizes
        options_changed = bool(
            (state.columns and not all(col in state.columns for col in columns))
            or (state.logs and not all(log in state.logs for log in logscales))
            or (state.plot_type is not None and plot_type != state.plot_type)
            or (plot_type in _BIN_SENSITIVE_PLOTS and (bins_changed or sizes_changed))
        )
        if self._needs_new_figure(axis_type, options_changed):
            self.reset(axis_type)

        channel_id = int(channel) if channel is not None else None
        key = (loader, exp, channel_id, sql_filter, subset_name)
        if key in self.model.overlay.datasets:
            return False

        # The selection tree reports channels as display strings.
        scope: Dict[Any, Any] = {exp: [channel]}
        subset = self.load_metadata_subset(
            loader, columns, sql_filter, scope, subset_name
        )
        if subset is None:
            return None
        label += subset.scope_note
        if subset.rows is None or subset.rows.empty:
            self._say(f"No data matching the subset {label}, skipping")
            return False
        self._say(f"{len(subset.rows)} rows in subset {label}")
        if len(columns) != len(subset.units):
            self._say("cols and units must have equal length")
            return None
        if not all(col in subset.rows.columns for col in columns):
            self._say(
                f"All columns {columns} must be present in the provided dataframe"
            )
            return None

        drawn = self._draw_metadata_dataset(
            plot_type, subset.rows, columns, subset.units, logscales, label, bins, sizes
        )
        if drawn is None:
            return None
        view.finish_plot()
        if not drawn:
            return False
        state = self.model.overlay
        state.figure = FigureKind.overlay(axis_type)
        state.plot_type = plot_type
        state.bins = bins
        state.sizes = sizes
        state.columns = columns
        state.logs = logscales
        state.datasets.add(key)
        return True

    @log(logger=logger)
    def _draw_metadata_dataset(
        self,
        plot_type: str,
        rows: pd.DataFrame,
        columns: List[Any],
        units: Sequence[Optional[str]],
        logscales: Sequence[bool],
        label: str,
        bins: Any,
        sizes: bool,
    ) -> Optional[bool]:
        """
        Compute one dataset's plot through the Model and have the View draw it.

        :param plot_type: one of the metadata plot types
        :type plot_type: str
        :param rows: the subset's rows
        :type rows: pd.DataFrame
        :param columns: the columns this plot type uses, in axis order
        :type columns: List[Any]
        :param units: each column's units
        :type units: Sequence[Optional[str]]
        :param logscales: each column's log-scale flag
        :type logscales: Sequence[bool]
        :param label: the dataset's label
        :type label: str
        :param bins: the bins list from the controls, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width
        :type sizes: bool
        :return: True if drawn, False if the computation was refused, None if the bins entry is invalid
        :rtype: Optional[bool]
        """
        view = self.view
        state = self.model.overlay
        if plot_type in _ONE_BINS_ENTRY_PLOTS:
            try:
                bins = _one_bins_entry(bins)
            except ValueError as e:
                self._say(str(e))
                return None

        labels = [
            view.format_axis_label(column, unit) for column, unit in zip(columns, units)
        ]
        logged = [
            f"log10({axis_label})" if log else axis_label
            for axis_label, log in zip(labels, logscales)
        ]
        values = [rows[column].values for column in columns]

        if plot_type in ("Histogram", "Normalized Histogram"):
            return self.calculate_histogram_bins(
                list(state.values) + [values[0]],
                logscales[0],
                bins,
                sizes,
                state.hist_min,
                state.hist_max,
                plot_type == "Normalized Histogram",
                labels[0],
                columns[0],
                label,
            )
        if plot_type == "Kernel Density Plot":
            return self.estimate_kernel_densities(
                list(state.values) + [values[0]],
                logscales[0],
                bins,
                sizes,
                state.hist_min,
                state.hist_max,
                logged[0],
                columns[0],
                label,
            )
        if plot_type == "Categorical Histogram":
            # Not filtered or log-scaled, unlike every other 1-D path: the values here
            # are category names, which have no NaN mask and no logarithm.
            return self.count_categories(
                list(state.values) + [values[0]],
                list(state.labels) + [label],
                labels[0],
                "Count",
            )
        if plot_type == "Capture Rate":
            x_label = f"log10(Interevent Time ({units[0]}))"
            return self.fit_capture_rate(
                values[0], bins, sizes, x_label, "Count", label
            )
        if plot_type == "Heatmap":
            return self.calculate_heatmap(
                values[0],
                values[1],
                list(logscales),
                bins,
                sizes,
                logged[0],
                logged[1],
                label,
            )
        if plot_type == "Scatterplot":
            return self._scatterplot(values, logscales, logged, label)
        return self.filter_3d_scatterplot(values, list(logscales), logged, label)

    @log(logger=logger)
    def _scatterplot(
        self,
        columns: Sequence[npt.NDArray[np.float64]],
        log_flags: Sequence[bool],
        axis_labels: Sequence[str],
        dataset_label: str,
    ) -> bool:
        """
        Filter a scatterplot's two columns and have the View draw them.

        The same work as the shared :meth:`filter_scatterplot`, which Protein still
        reaches through its request and which hands the drawing an axes; Metadata's View
        draws on its own.

        :param columns: the raw x and y values
        :type columns: Sequence[npt.NDArray[np.float64]]
        :param log_flags: log-scale each column?
        :type log_flags: Sequence[bool]
        :param axis_labels: the axis labels, already formatted
        :type axis_labels: Sequence[str]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :return: True if drawn
        :rtype: bool
        """
        try:
            filtered = self.model.logscale_and_filter_columns(
                *columns, log_flags=list(log_flags)
            )
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to filter the scatterplot: {repr(e)}")
            self._say(f"Unable to filter the scatterplot: {e}")
            return False
        self.view.show_scatterplot(filtered, axis_labels, dataset_label)
        return True

    @log(logger=logger)
    def _overlay_event_dataset(
        self,
        loader: str,
        plot_type: str,
        axes: List[Optional[str]],
        logs: List[bool],
        bins: Optional[List[Union[int, float]]],
        sizes: bool,
        exp: Optional[str],
        channel: Optional[str],
        subset_name: str,
        sql_filter: str,
        label: str,
    ) -> Optional[bool]:
        """
        Fetch, reduce and draw one event-data dataset, starting a new figure if needed.

        :param loader: the database loader plugin's key
        :type loader: str
        :param plot_type: one of the event-data plot types
        :type plot_type: str
        :param axes: unused by event-data plots; kept so both kinds share one call
        :type axes: List[Optional[str]]
        :param logs: unused by event-data plots
        :type logs: List[bool]
        :param bins: the bins list from the controls, for the all-points histograms
        :type bins: Optional[List[Union[int, float]]]
        :param sizes: does bins refer to a bin width
        :type sizes: bool
        :param exp: the experiment, or None for no scope
        :type exp: Optional[str]
        :param channel: the channel as the selection tree reports it, or None
        :type channel: Optional[str]
        :param subset_name: the filter's name
        :type subset_name: str
        :param sql_filter: the filter's SQL
        :type sql_filter: str
        :param label: the dataset's label
        :type label: str
        :return: True if drawn, None if the whole plot must stop
        :rtype: Optional[bool]
        """
        # The selection tree reports channels as display strings.
        scope: Dict[Any, Any] = {exp: [channel]}
        state = self.model.overlay
        type_changed = state.plot_type is not None and plot_type != state.plot_type
        if plot_type in _ALL_POINTS_PLOTS:
            if self._needs_new_figure(
                "2d", type_changed or state.bins != bins or state.sizes != sizes
            ):
                self.reset("2d")
            drawn = self.build_all_points_histogram(
                loader,
                sql_filter,
                scope,
                plot_type,
                bins,
                sizes,
                self.model.overlay.hist_min,
                self.model.overlay.hist_max,
                label,
                subset_name,
            )
        else:
            bins, sizes = None, False
            if self._needs_new_figure("2d", type_changed):
                self.reset("2d")
            drawn = self.build_event_overlay(
                loader, sql_filter, scope, plot_type, subset_name
            )
        if not drawn:
            return None
        state = self.model.overlay
        state.figure = FigureKind.OVERLAY_2D
        state.plot_type = plot_type
        state.bins = bins
        state.sizes = sizes
        state.columns = []
        state.logs = []
        channel_id = int(channel) if channel is not None else None
        state.datasets.add((loader, exp, channel_id, sql_filter, subset_name))
        return True

    @log(logger=logger)
    def _needs_new_figure(self, axis_type: str, options_changed: bool) -> bool:
        """
        Must the next dataset start a new figure, with a recorded reset?

        Always when the figure cannot take a plot of this projection. An empty figure
        starts with a reset unless it was just reset, so every history replays onto a
        cleared figure and a Reset is not followed by a second one. An overlaid figure
        starts again when the plot's options changed.

        :param axis_type: Either '2d' or '3d', the projection the plot needs
        :type axis_type: str
        :param options_changed: do the plot's options differ from those on the figure
        :type options_changed: bool
        :return: True if a reset must come first
        :rtype: bool
        """
        figure = self.model.overlay.figure
        # Plot Events replaces the figure with an event grid without telling the Model,
        # so the axes are asked as well.
        if not figure.accepts(axis_type) or not self.view.axes_ready(axis_type):
            return True
        if figure in (FigureKind.EMPTY_2D, FigureKind.EMPTY_3D):
            history = self.tab_action_history
            just_reset = bool(history) and (
                history[next(reversed(history))].get("action") == RESET_ACTION
            )
            return not just_reset
        return options_changed

    @log(logger=logger)
    def _plots_as_categories(self, loader: str, column: Optional[str]) -> bool:
        """
        Refuse a Categorical Histogram of a column declared as continuous.

        A column whose type is REAL, FLOAT or DOUBLE is refused, on the status panel. A
        failed lookup, or a column with no declared type - which SQLite allows - is let
        through, as :meth:`MetadataView.is_categorical_type` decides.

        :param loader: the database loader plugin's key
        :type loader: str
        :param column: the column on the x axis
        :type column: Optional[str]
        :return: True if the plot may go ahead
        :rtype: bool
        """
        column_type = None
        try:
            column_type = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_type", column
            )
        except Exception as e:
            self.logger.error(f"Failed to read the type of column {column}: {e!r}")
        if self.view.is_categorical_type(column_type):
            return True
        self._say(
            "Categorical histograms can only be plotted for columns that correspond "
            f"to discrete values: {column} has type {column_type}"
        )
        return False

    @log(logger=logger)
    def _say(self, text: str) -> None:
        """
        Put a line on the status panel under this tab's name.

        :param text: what to say
        :type text: str
        """
        self.add_text_to_display.emit(text, self.__class__.__name__)

    @log(logger=logger)
    def calculate_heatmap(
        self,
        xdata: npt.NDArray[np.float64],
        ydata: npt.NDArray[np.float64],
        log_flags: Sequence[bool],
        bins: Any,
        sizes: bool,
        x_label: str,
        y_label: str,
        dataset_label: str,
    ) -> bool:
        """
        Filter and bin the heatmap's two columns, and hand the result back to draw.

        A request slot, the same shape as ``ClusteringController.cluster``: the View
        asks, this calls the Model, and the answer goes back to be drawn on the View's
        own axes. The labels arrive and depart unchanged; this method marshals and does
        not interpret them.

        An invalid bin entry raises out of the Model and is **reported here rather than
        propagating**, because nothing between here and :meth:`overlay_plot` catches it.

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
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param y_label: the y axis label, already formatted
        :type y_label: str
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :return: True if the View drew the result
        :rtype: bool
        """
        try:
            xfiltered, yfiltered = self.model.logscale_and_filter_columns(
                xdata, ydata, log_flags=list(log_flags)
            )
            x, y, z, extent = self.model.calculate_heatmap(
                xfiltered, yfiltered, bins, sizes
            )
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to build the heatmap: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to build the heatmap: {e}", self.__class__.__name__
            )
            return False
        self.view.show_heatmap(x, y, z, extent, x_label, y_label, dataset_label)
        return True

    @log(logger=logger)
    def filter_3d_scatterplot(
        self,
        columns: Sequence[npt.NDArray[np.float64]],
        log_flags: Sequence[bool],
        axis_labels: Sequence[str],
        dataset_label: str,
    ) -> bool:
        """
        The same for a 3-D scatterplot's three columns.

        Separate from :meth:`filter_scatterplot` because the View's two drawing
        halves are separate: a 3-D scatter rebuilds the axes and carries a z label.

        :param columns: the raw x, y and z values
        :type columns: Sequence[npt.NDArray[np.float64]]
        :param log_flags: log-scale each column?
        :type log_flags: Sequence[bool]
        :param axis_labels: the axis labels, already formatted
        :type axis_labels: Sequence[str]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :return: True if the View drew the result
        :rtype: bool
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
            return False
        self.view.show_3d_scatterplot(filtered, axis_labels, dataset_label)
        return True

    @log(logger=logger)
    def estimate_kernel_densities(
        self,
        datasets: Sequence[npt.NDArray[np.float64]],
        logx: bool,
        bins: Any,
        sizes: bool,
        hist_min: Optional[float],
        hist_max: Optional[float],
        x_label: str,
        column: str,
        dataset_label: str,
    ) -> bool:
        """
        Filter every overlaid dataset, then estimate each one's density.

        A request slot, the same shape as :meth:`calculate_heatmap`. The labels arrive
        and depart unchanged; this slot marshals and does not interpret them.

        The newest dataset is the last of ``datasets`` and joins what the Model keeps
        only once its result is drawn, so a subset that loses every point to the filter
        is refused here and leaves no label behind.

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
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param column: the column's own name, for the message when nothing survives
        :type column: str
        :param dataset_label: the newest dataset's label
        :type dataset_label: str
        :return: True if the View drew the result
        :rtype: bool
        """
        try:
            filtered = self.model.logscale_and_filter_datasets(datasets, logx)
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to filter the density plot: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to filter the density plot: {e}", self.__class__.__name__
            )
            return False

        if len(filtered[-1]) == 0:
            # Every point was filtered out, the commonest cause being a column that
            # is NULL for every row the subset filter selected.
            self.add_text_to_display.emit(
                f"No {column} values in this subset, so there is nothing to plot",
                self.__class__.__name__,
            )
            return False

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
            return False

        labels = self._accumulate(datasets[-1], dataset_label, hist_min, hist_max)
        self.view.show_kernel_densities(densities, labels, x_label)
        return True

    @log(logger=logger)
    def calculate_histogram_bins(
        self,
        datasets: Sequence[npt.NDArray[np.float64]],
        logx: bool,
        bins: Any,
        sizes: bool,
        hist_min: Optional[float],
        hist_max: Optional[float],
        norm: bool,
        x_label: str,
        column: str,
        dataset_label: str,
    ) -> bool:
        """
        Filter every overlaid dataset, bin them onto shared edges, and count them.

        A request slot, the same shape as :meth:`estimate_kernel_densities` - and it has
        to be, because the two write the same accumulator and the same pair of shared
        limits, so a difference between them would show up as a plot disagreeing with
        itself.

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
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param column: the column's own name, for the message when nothing survives
        :type column: str
        :param dataset_label: the newest dataset's label
        :type dataset_label: str
        :return: True if the View drew the result
        :rtype: bool
        """
        try:
            filtered = self.model.logscale_and_filter_datasets(datasets, logx)
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to filter the histogram: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to filter the histogram: {e}", self.__class__.__name__
            )
            return False

        if len(filtered[-1]) == 0:
            self.add_text_to_display.emit(
                f"No {column} values in this subset, so there is nothing to "
                "histogram",
                self.__class__.__name__,
            )
            return False

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
            return False

        labels = self._accumulate(datasets[-1], dataset_label, hist_min, hist_max)
        self.view.show_histogram_bins(
            bincenters, widths, counts, labels, x_label, logx, norm
        )
        return True

    @log(logger=logger)
    def count_categories(
        self,
        datasets: List[npt.NDArray[Any]],
        labels: List[str],
        x_label: str,
        y_label: str,
    ) -> bool:
        """
        Tally each overlaid dataset's categories, and hand them back to be drawn.

        The same shape as :meth:`estimate_kernel_densities`. The labels arrive and
        depart unchanged; this method marshals and does not interpret them.

        A column of a type the tally cannot sort raises out of the Model and is reported
        here, since nothing between here and :meth:`overlay_plot` catches it.

        :param datasets: one array of raw column values per overlaid dataset, newest last
        :type datasets: List[npt.NDArray[Any]]
        :param labels: one label per dataset, index-aligned with datasets, newest last
        :type labels: List[str]
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param y_label: the y axis label
        :type y_label: str
        :return: True if the View drew the result
        :rtype: bool
        """
        try:
            counts = self.model.categorical_counts(datasets)
        except (TypeError, ValueError) as e:
            self.logger.error(f"Unable to count categories: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to count categories: {e}", self.__class__.__name__
            )
            return False
        state = self.model.overlay
        shown = self._accumulate(
            datasets[-1], labels[-1], state.hist_min, state.hist_max
        )
        self.view.show_categorical_counts(counts, shown, x_label, y_label)
        return True

    @log(logger=logger)
    def _accumulate(
        self,
        values: Any,
        label: str,
        hist_min: Optional[float],
        hist_max: Optional[float],
    ) -> List[str]:
        """
        Add the newest dataset to what the overlaid figure redraws, once it is drawable.

        :param values: the newest dataset's values, in the shape its plot type keeps
        :type values: Any
        :param label: the newest dataset's label
        :type label: str
        :param hist_min: the shared lower limit, widened by this dataset
        :type hist_min: Optional[float]
        :param hist_max: the shared upper limit, widened by this dataset
        :type hist_max: Optional[float]
        :return: every accumulated dataset's label, newest last
        :rtype: List[str]
        """
        state = self.model.overlay
        state.values.append(values)
        state.labels.append(label)
        state.hist_min = hist_min
        state.hist_max = hist_max
        return list(state.labels)

    @log(logger=logger)
    def fit_capture_rate(
        self,
        data: npt.NDArray[np.float64],
        bins: Any,
        sizes: bool,
        x_label: str,
        y_label: str,
        dataset_label: str,
    ) -> bool:
        """
        Bin and fit the capture rate, and hand the result back to the View to draw.

        A request slot, the same shape as :meth:`calculate_heatmap`. A fit that will not
        converge raises ``RuntimeError`` out of ``curve_fit``, and is reported rather
        than allowed to escape a Qt slot, where it would reach nobody.

        **The inter-event times are computed below rather than in the View**: gaps
        between consecutive events are the measurement, not the drawing. Both conditions
        that used to be judged on them belong with the computation - too little surviving
        data is reported instead of raised,
        which reaches the user with the count in it rather than as ``update_plot``'s
        generic "no data available after filtering".

        :param data: the event times as they came out of the column, unsorted
        :type data: npt.NDArray[np.float64]
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param x_label: the x axis label, already formatted
        :type x_label: str
        :param y_label: the y axis label
        :type y_label: str
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :return: True if the View drew the result
        :rtype: bool
        """
        initial_length = len(data)
        log_times = self.model.interevent_log_times(data)

        if len(log_times) < 10:
            self.add_text_to_display.emit(
                f"Not enough data passes the log filter: {len(log_times)} is not "
                "enough to estimate capture rate - skipping",
                self.__class__.__name__,
            )
            return False

        if len(log_times) < initial_length - 1:
            # n events make n-1 intervals by construction, so that is the baseline for
            # how many the log filter dropped, not the raw event count.
            self.add_text_to_display.emit(
                f"{initial_length - 1 - len(log_times)} rows dropped by log filter",
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
            return False
        self.view.show_capture_rate(
            bin_edges,
            bincenters,
            val,
            fit,
            rate,
            error,
            log_times,
            x_label,
            y_label,
            dataset_label,
        )
        return True

    @log(logger=logger)
    def load_metadata_subset(
        self,
        loader: str,
        columns: List[str],
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        subset_name: str,
    ) -> Optional[MetadataSubset]:
        """
        Fetch one metadata subset - its rows and each column's units - for the overlay.

        Every part is fetched before any is returned, so a partial failure is reported
        and answered with None rather than drawn with another subset's units.

        This is also where the SQL the user sees comes from: the query echoed to the
        status panel is **the one that runs**, not the smaller one that validated the
        filter, and it is echoed only when it differs from the last one shown.

        A raw filter - one whose name ends ``_raw`` - is a complete ``SELECT``, not a
        WHERE-clause body, so it cannot go through the query builder. It is run by
        :meth:`_load_raw_metadata_subset`, restricted to the experiment and channel
        scope.

        :param loader: the database loader plugin's key
        :type loader: str
        :param columns: the columns this plot type needs, in axis order
        :type columns: List[str]
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows, or a complete ``SELECT`` for a raw filter
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param subset_name: the selected filter's name, whose ``_raw`` suffix marks a raw filter
        :type subset_name: str
        :return: the subset, or None if any part of it could not be fetched
        :rtype: Optional[MetadataSubset]
        """
        if subset_name.endswith("_raw"):
            return self._load_raw_metadata_subset(
                loader, columns, sql_filter, experiments_and_channels, subset_name
            )

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
            self.logger.error(f"Failed to build the subset query: {e!r}")
            self.add_text_to_display.emit(
                f"Could not build the query for this subset: {e}",
                self.__class__.__name__,
            )
            return None

        if not query:
            self.add_text_to_display.emit(
                debug or "The subset query could not be built",
                self.__class__.__name__,
            )
            return None

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
            return None

        self._echo_applied_query(query, table_name)
        return MetadataSubset(plot_data, units, "")

    @log(logger=logger)
    def _load_raw_metadata_subset(
        self,
        loader: str,
        columns: List[str],
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        subset_name: str,
    ) -> Optional[MetadataSubset]:
        """
        Run a raw ``SELECT`` over the selection and return its rows for a plot.

        The user's projection is the plot's data, so a column the plot needs that the
        ``SELECT`` did not return is named on the status panel rather than drawn around.
        Returns the same as the scoped path, and only once every part has been fetched.

        :param loader: the database loader plugin's key
        :type loader: str
        :param columns: the columns this plot type needs, in axis order
        :type columns: List[str]
        :param sql_filter: the filter's complete ``SELECT``
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param subset_name: the filter's name, for the messages
        :type subset_name: str
        :return: the subset, or None if it could not be run or does not fit the plot
        :rtype: Optional[MetadataSubset]
        """
        ran = self._run_raw_filter(
            loader, sql_filter, experiments_and_channels, subset_name
        )
        if ran is None:
            return None
        plot_data, executed = ran.rows, ran.executed
        if self._ambiguous_raw_columns(plot_data, columns, subset_name):
            return None

        missing = [c for c in columns if c not in plot_data.columns]
        if missing:
            self.add_text_to_display.emit(
                f"{subset_name}'s query does not return the column(s) this plot "
                f"needs: {', '.join(missing)}. "
                f"{self._missing_column_advice(loader, missing)}",
                self.__class__.__name__,
            )
            return None

        try:
            units = [
                self.model.call(
                    "MetaDatabaseLoader", loader, "get_column_units", column
                )
                for column in columns
            ]
        except Exception as e:
            self.logger.error(f"Failed to read the units for {subset_name}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not read the units of {columns} from {loader}: {e}",
                self.__class__.__name__,
            )
            return None

        self._echo_applied_query(executed, "raw query")
        return MetadataSubset(
            plot_data,
            units,
            (
                " (rows not limited to this experiment and channel)"
                if experiments_and_channels and not ran.scoped
                else ""
            ),
        )

    @log(logger=logger)
    def _fetch_event_subset(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        subset_name: str,
    ) -> Optional[Tuple[str, Generator]]:
        """
        Build one event-data subset's query and open a generator over its events.

        Shared by the two event-data plot types, which differ only in what they then
        reduce the events to. Reports its own failure and answers with None, so a
        caller has nothing to handle beyond stopping.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows, or a complete ``SELECT`` for a raw filter
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param subset_name: the selected filter's name, whose ``_raw`` suffix marks a raw filter
        :type subset_name: str
        :return: the query that ran (the user's ``SELECT`` with the selection bound in, for a raw filter) and a generator over its events, or None
        :rtype: Optional[Tuple[str, Generator]]
        """
        is_raw = subset_name.endswith("_raw")
        shown_query = sql_filter
        if is_raw:
            # The selection is applied to the query's own rows, so the events it names
            # are final and are loaded by id with no further scope.
            raw = self._raw_filter_conditions(
                loader, sql_filter, experiments_and_channels, subset_name
            )
            if raw is None:
                return None
            (sql_filter, shown_query), experiments_and_channels = raw, None
        try:
            # Two values, because construct_event_data_query is declared
            # -> Tuple[str, str] and reports a filter it cannot build as
            # ("", debug). The bus used to splat that pair across two arguments;
            # call() hands it over whole, and a
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

        return (shown_query if is_raw else query), generator

    @log(logger=logger)
    def build_all_points_histogram(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        plot_type: str,
        bins: Any,
        sizes: bool,
        hist_min: Optional[float],
        hist_max: Optional[float],
        dataset_label: str,
        subset_name: str,
    ) -> bool:
        """
        Tally one event-data subset into an all-points histogram for the View.

        The events are walked and binned by the Model rather than in the widget: nothing
        above the Model wants them, and walking them there meant walking them twice.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
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
        :param subset_name: the selected filter's name, whose ``_raw`` suffix marks a raw filter
        :type subset_name: str
        :return: True if the View drew the result
        :rtype: bool
        """
        fetched = self._fetch_event_subset(
            loader, sql_filter, experiments_and_channels, subset_name
        )
        if fetched is None:
            return False
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
            return False

        self._echo_applied_query(query, "events")
        labels = self._accumulate((bincenters, counts), dataset_label, new_min, new_max)
        self.view.show_all_points_histogram(
            list(self.model.overlay.values), labels, plot_type
        )
        return True

    @log(logger=logger)
    def build_event_overlay(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        plot_type: str,
        subset_name: str,
    ) -> bool:
        """
        Put one event-data subset on a shared normalised axis for the View to draw.

        The same shape as :meth:`build_all_points_histogram`.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param plot_type: either 'Raw Event Overlay' or 'Filtered Event Overlay'
        :type plot_type: str
        :param subset_name: the selected filter's name, whose ``_raw`` suffix marks a raw filter
        :type subset_name: str
        :return: True if the View drew the result
        :rtype: bool
        """
        fetched = self._fetch_event_subset(
            loader, sql_filter, experiments_and_channels, subset_name
        )
        if fetched is None:
            return False
        query, generator = fetched

        try:
            traces = self.model.build_event_overlay(generator, plot_type)
        except (ValueError, TypeError, IndexError, KeyError) as e:
            self.logger.error(f"Unable to build the event overlay: {e!r}")
            self.add_text_to_display.emit(
                f"Unable to build the event overlay: {e}",
                self.__class__.__name__,
            )
            return False

        self._echo_applied_query(query, "events")
        self.view.show_event_overlay(traces)
        return True

    @log(logger=logger)
    @Slot(str, int, int, int)
    def request_plot_features(
        self, loader: str, experiment_id: int, channel_id: int, event_id: int
    ) -> None:
        """
        Fetch one event's fitted features and hand them to the View.

        Asked once per event on the plot path, so a failure is logged and the event is
        plotted without features rather than stopping the plot. The View clears the six
        feature attributes before each request and reads them back after, so an event
        whose lookup failed gets none rather than the previous event's.

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
    def _raw_export_condition(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        filter_name: str,
    ) -> Optional[str]:
        """
        Turn a raw filter into the condition an export puts in its ``WHERE``.

        An export selects events by a condition on the events table, and a raw filter is
        a complete ``SELECT``, so each selected channel's bound query is checked the way
        a plot checks it - only a read, ``event_id`` returned, every key naming an event -
        and then named as the events whose ``event_id`` it returns, in that channel. The
        query stays in the condition as a subquery rather than being unrolled into a list
        of ids, so the text does not grow with the subset.

        A filter that does not use both placeholders is refused: an export writes files,
        and an unscoped query would write the same events for every selected channel.
        Reports its own refusal and answers with None.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the filter's complete ``SELECT``
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param filter_name: the filter's name, for the messages
        :type filter_name: str
        :return: a condition that selects the filter's events, one that selects none if there are none, or None if the export is refused
        :rtype: Optional[str]
        """
        if scope_placeholders(sql_filter) != {"experiment_id", "channel_id"}:
            self.add_text_to_display.emit(
                f"{filter_name} cannot be exported: an export writes files for the "
                "selected channels, and its query does not use both :experiment_id and "
                ":channel_id, so it would write the same events for every one. Add "
                "experiment_id = :experiment_id AND channel_id = :channel_id to its WHERE",
                self.__class__.__name__,
            )
            return None
        parts: List[str] = []
        for experiment, channel in selected_pairs(experiments_and_channels):
            read = self._run_raw_event_keys(
                loader,
                sql_filter,
                {experiment: None if channel is None else [channel]},
                filter_name,
            )
            if read is None:
                return None
            run, keys, sql_filter = read
            if keys.empty:
                continue
            parts.append(
                f"(e.experiment_id = {run.experiment_id} AND e.channel_id = {run.channel} "
                f"AND e.event_id IN (SELECT event_id FROM (\n{run.executed}\n)))"
            )
        return " OR ".join(parts) if parts else "1 = 0"

    #: How a column of another table is joined to an ``events`` query, by table name.
    JOINS = {
        "sublevels": (
            "s",
            "sublevels s ON s.event_db_id = e.id",
        ),
        "experiments": ("exp", "experiments exp ON exp.id = e.experiment_id"),
    }

    @log(logger=logger)
    def _missing_column_advice(self, loader: str, missing: List[str]) -> str:
        """
        Say how to get the columns a raw query left out into its ``SELECT``.

        A column of ``events`` only has to be added to the list. One of another table,
        such as ``sublevel_duration``, is not in ``events`` at all, so the query has to
        join its table, and the example shows how. The table comes from the loader; if it
        cannot say, the advice is the plain one.

        :param loader: the database loader plugin's key
        :type loader: str
        :param missing: the columns the plot needs that the result does not hold
        :type missing: List[str]
        :return: one or two sentences on what to select
        :rtype: str
        """
        elsewhere: Dict[str, str] = {}
        for column in missing:
            try:
                table = self.model.call(
                    "MetaDatabaseLoader", loader, "get_table_by_column", column
                )
            except Exception:
                table = None
            if isinstance(table, str) and table != "events":
                elsewhere[column] = table
        here = [c for c in missing if c not in elsewhere]
        advice = []
        if here:
            advice.append(f"Add {', '.join(here)} to its SELECT")
        for column, table in elsewhere.items():
            join = self.JOINS.get(table)
            if join is None:
                advice.append(
                    f"{column} is a column of the {table} table, so the query has to "
                    "join that table"
                )
                continue
            alias, clause = join
            advice.append(
                f"{column} is a column of the {table} table, so the query has to join "
                f"it, for example SELECT e.event_id, {alias}.{column} FROM events e "
                f"JOIN {clause} WHERE e.experiment_id = :experiment_id AND "
                "e.channel_id = :channel_id"
            )
        return ". ".join(advice)

    @log(logger=logger)
    @Slot(str, str, str, object, object, int, str)
    def export_csv_subset(
        self,
        loader: str,
        folder: str,
        name: str,
        subset_filter: Optional[str],
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        export_index: int,
        filter_name: str = "",
    ) -> None:
        """
        Start writing one filtered subset to CSV in a worker thread.

        The plugin returns a progress generator rather than a value, so this hands it
        straight to ``set_generator`` along with the export's index, the loader key and
        the metaclass. ``RawDataController.commit_events`` is the same shape.

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
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param export_index: the index this export's worker is keyed under
        :type export_index: int
        :param filter_name: the selected filter's name, whose ``_raw`` suffix marks a raw filter
        :type filter_name: str
        :return: None
        :rtype: None
        """
        if filter_name.endswith("_raw") and subset_filter:
            subset_filter = self._raw_export_condition(
                loader, subset_filter, experiments_and_channels, filter_name
            )
            if subset_filter is None:
                return

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

        The axis travels with the request and back out again, so the answer knows which
        label it belongs to without anything being parked here in between. This is
        Metadata's alone, because the protein tab has no units label to write to.

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
    @Slot(str)
    def request_column_names(self, loader: str) -> None:
        """
        Fetch a loader's column names and hand them to the View.

        The same shape as the reader and loader channel look-ups, against
        ``MetaDatabaseLoader``. An empty answer is logged rather than pushed: clearing the
        axis comboboxes would read as "this database has no columns" when what happened
        is that nobody could ask it.

        :param loader: the database loader plugin's key
        :type loader: str
        :return: None
        :rtype: None
        """
        try:
            column_names = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_names_by_table"
            )
        except Exception as e:
            self.logger.error(f"Failed to request column data: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to read the columns of {loader}: {e}", self.__class__.__name__
            )
            return
        if column_names:
            self.view.update_column_names(column_names)
            self.logger.info("Axis comboboxes updated with new column names.")
        else:
            self.logger.warning("No column names received to update.")

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
