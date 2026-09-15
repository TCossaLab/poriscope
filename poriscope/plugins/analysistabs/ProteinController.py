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
import pandas as pd
from matplotlib.axes import Axes
from PySide6.QtCore import Slot

from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.plugins.analysistabs.ProteinView import ProteinView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabController import MetaSubsetTabController


@inherit_docstrings
class ProteinController(MetaSubsetTabController):
    """
    Subclass of MetaSubsetTabController for managing protein view-model logic.

    Relays queries, event data, and filter/column metadata between the
    database backend and ProteinView.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the protein view and model.
        """
        self.view = ProteinView()
        self.model = ProteinModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Connect internal view signals to their corresponding controller slots.

        :return: None
        :rtype: None
        """
        super()._setup_connections()
        self.view.event_plot_data_requested.connect(self.load_event_plot_data)
        self.view.event_distribution_data_requested.connect(
            self.load_event_distribution_data
        )
        self.view.fit_commit_requested.connect(self.check_for_existing_fit_columns)
        self.view.fit_commit_confirmed.connect(self.commit_fits)
        self.view.ensemble_fit_requested.connect(self.fit_ensemble_geometry)
        self.view.ensemble_histogram_requested.connect(self.build_ensemble_histogram)
        self.view.xyerr_scatterplot_requested.connect(self.filter_xyerr_scatterplot)
        self.view.event_histogram_fits_requested.connect(self.fit_event_histograms)
        self.view.distribution_fits_requested.connect(self.fit_distribution_events)

    @log(logger=logger)
    @Slot(object, object, object, str, float, float, int)
    def fit_ensemble_geometry(
        self,
        bins: npt.NDArray[np.float64],
        amplitude: npt.NDArray[np.float64],
        plot_data: pd.DataFrame,
        plot_type: str,
        d: float,
        L: float,
        N: int,
    ) -> None:
        """
        Fit the ensemble histogram, and hand the result back to the View to draw.

        Decision B's command path, the same shape as
        ``ClusteringController.cluster``: the View emits an intent, this slot calls
        the Model, and the answer goes back through a setter. Step 4c introduced it,
        when the double-gaussian fitting moved off the widget.

        The context arrives and departs unchanged rather than being held here or on
        the View between the halves. A fit that fails its sanity checks is not an
        error - ``(None, None)`` is a legitimate answer the View reports to the user -
        so only an unexpected failure is caught, and it is reported rather than
        raised, because Qt invoked this from a signal and nothing above it could
        handle it.

        :param bins: the histogram's bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: the amplitude in each bin
        :type amplitude: npt.NDArray[np.float64]
        :param plot_data: the frame the View will draw the fit into
        :type plot_data: pd.DataFrame
        :param plot_type: the plot type label to reuse when plotting the fit
        :type plot_type: str
        :param d: the diameter of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :param N: target number of samples to draw for each ensemble
        :type N: int
        :return: None
        :rtype: None
        """
        try:
            popt, curve = self.model.fit_histogram(bins, amplitude)
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to fit the ensemble histogram: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to fit the ensemble histogram: {e}", self.__class__.__name__
            )
            return

        if popt is None or curve is None:
            self.logger.info("Unable to fit a double gaussian to the histogram")
            self.add_text_to_display.emit(
                "Unable to fit a double gaussian to the histogram",
                self.__class__.__name__,
            )
            return

        try:
            df_prolate, df_oblate = self.model.sample_vm_solutions(popt, d, L, N)
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to sample the ensemble geometry: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to sample the ensemble geometry: {e}",
                self.__class__.__name__,
            )
            return

        if df_prolate.empty and df_oblate.empty:
            self.logger.warning(
                "Generative sampling bailed out: The ensemble Gaussian fit "
                "represents an unphysical geometry."
            )
            self.add_text_to_display.emit(
                "Generative sampling bailed out: The ensemble Gaussian fit "
                "represents an unphysical geometry.",
                self.__class__.__name__,
            )
        elif len(df_prolate) < N or len(df_oblate) < N:
            self.logger.info(
                "Sampling hit bailout limit; returning partial ensemble arrays."
            )

        # Called even when nothing was sampled: the fit itself is still worth
        # drawing, and the two empty frames skip their own scatterplots.
        self.view.set_ensemble_geometry_fit(
            popt, curve, plot_data, plot_type, df_prolate, df_oblate
        )

    @log(logger=logger)
    @Slot(object, object, object, object, str)
    def filter_xyerr_scatterplot(
        self,
        columns: Sequence[npt.NDArray[np.float64]],
        log_flags: Sequence[bool],
        ax: Axes,
        axis_labels: Sequence[str],
        dataset_label: str,
    ) -> None:
        """
        Filter an error-bar scatterplot's columns, and hand them back to draw.

        Separate from the shared ``MetaSubsetTabController.filter_scatterplot``
        because only this tab draws error bars. The four arrays go down together so
        one mask covers them all:
        a row dropped from the values has to be dropped from their error bars, or
        the bars no longer describe the points they sit on.

        :param columns: the raw x, y, x error and y error values
        :type columns: Sequence[npt.NDArray[np.float64]]
        :param log_flags: log-scale each column? the two error columns never are
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
            self.logger.error(f"Unable to filter the scatterplot: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to filter the scatterplot: {e}", self.__class__.__name__
            )
            return
        self.view.set_xyerr_scatterplot(filtered, ax, axis_labels, dataset_label)

    @log(logger=logger)
    @Slot(str, str, object, str, object, bool, str, object, float, float, int)
    def build_ensemble_histogram(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
        plot_type: str,
        bins: Any,
        sizes: bool,
        dataset_label: str,
        dataset_key: Tuple[Any, ...],
        d: float,
        L: float,
        N: int,
    ) -> None:
        """
        Fetch one event subset and average it into a single histogram to draw.

        Decision B's command path. Step 4's closeout took the aggregation down with
        the fetch: the widget used to be handed the generator and walk it twice
        itself, which is what kept whole events - and the DataFrame construction -
        above the Model.

        The drawing context arrives and departs unchanged; this slot marshals and
        does not interpret it. Nothing is handed back at all if the subset has no
        usable event, which is what leaves the previous figure in place.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :param plot_type: 'Raw Histogram' or 'Filtered Histogram'
        :type plot_type: str
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param dataset_label: the label the histogram is drawn under
        :type dataset_label: str
        :param dataset_key: the plotted-datasets key, handed back unchanged
        :type dataset_key: Tuple[Any, ...]
        :param d: the diameter of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :param N: target number of samples to draw for each ensemble
        :type N: int
        :return: None
        :rtype: None
        """
        fetched = self._fetch_event_subset(loader, sql_filter, experiments_and_channels)
        if fetched is None:
            return
        query, generator = fetched

        try:
            plot_data = self.model.build_all_points_histogram(
                generator, plot_type, bins, sizes
            )
        except (ValueError, TypeError, IndexError, KeyError) as e:
            self.logger.error(f"Unable to build the ensemble histogram: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to build the ensemble histogram: {e}",
                self.__class__.__name__,
            )
            return

        if plot_data is None:
            self.add_text_to_display.emit(
                "No usable events in the selected subset, so there is nothing to "
                "plot",
                self.__class__.__name__,
            )
            return

        self.view.set_event_query(query)
        self.view.set_ensemble_histogram(
            plot_data, plot_type, bins, sizes, dataset_label, dataset_key, d, L, N
        )

    @log(logger=logger)
    @Slot(object, str, object, bool)
    def fit_event_histograms(
        self,
        event_data: Sequence[Dict[str, Any]],
        plot_type: str,
        bins: Any,
        sizes: bool,
    ) -> None:
        """
        Bin and fit every event in one call, and hand the results back to draw.

        Decision B's command path. One call rather than one per event keeps each
        answer off the widget; see ``ProteinModel.fit_histograms``. Step 4's closeout
        added the binning ahead of the fitting, so the widget is handed the
        histograms rather than building them.

        The events pass straight through: this slot marshals, it does not interpret
        them. A failure is reported on the status panel rather than raised, because
        Qt invoked this from a signal and nothing above it could handle it - and an
        unusable bin request is now reported once here rather than logged once per
        event and drawn as a grid of empty subplots.

        :param event_data: the events being plotted, passed back to the View unchanged
        :type event_data: Sequence[Dict[str, Any]]
        :param plot_type: 'Raw Histogram' or 'Filtered Histogram'
        :type plot_type: str
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :return: None
        :rtype: None
        """
        try:
            histograms = self.model.build_event_histograms(
                event_data, plot_type, bins, sizes
            )
            fits = self.model.fit_histograms(histograms)
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to fit the event histograms: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to fit the event histograms: {e}", self.__class__.__name__
            )
            return
        self.view.set_event_histogram_fits(fits, histograms, event_data)

    @log(logger=logger)
    @Slot(object, str, object, bool, float, float, int)
    def fit_distribution_events(
        self,
        event_data: Sequence[Dict[str, Any]],
        plot_type: str,
        bins: Any,
        sizes: bool,
        d: float,
        L: float,
        N: int,
    ) -> None:
        """
        Bin and fit every event on the individual distribution path, and hand back.

        Decision B's command path, the same shape as ``fit_event_histograms``. The
        events and the pore geometry pass straight through; this slot marshals and
        does not interpret them.

        :param event_data: the events being plotted, passed back to the View unchanged
        :type event_data: Sequence[Dict[str, Any]]
        :param plot_type: 'Raw Histogram' or 'Filtered Histogram'
        :type plot_type: str
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param d: the diameter of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :param N: target number of samples to draw for each ensemble
        :type N: int
        :return: None
        :rtype: None
        """
        try:
            histograms = self.model.build_event_histograms(
                event_data, plot_type, bins, sizes
            )
            fits = self.model.fit_histograms(histograms)
            df_prolate, df_oblate, fit_data = self.model.sample_event_geometries(
                fits, histograms, event_data, d, L, N
            )
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to fit the event histograms: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to fit the event histograms: {e}", self.__class__.__name__
            )
            return

        if fit_data.empty:
            # Every event was refused, or the subset held none at all. Every guard in
            # the drawing half tests a frame built from these events, so without this
            # the tab drew empty axes and said nothing.
            self.add_text_to_display.emit(
                "No events in the selected subset could be fitted, so there is "
                "nothing to plot",
                self.__class__.__name__,
            )
            return

        self.view.set_distribution_fits(df_prolate, df_oblate, fit_data)

    @log(logger=logger)
    @Slot(str)
    def check_for_existing_fit_columns(self, loader: str) -> None:
        """
        Ask whether this database already holds fit columns, and tell the View.

        Phase one of a two-phase commit. ``_commit_fits`` interleaved a plugin call
        with a modal question for the user, which no single intent can express: the
        answer to "does this already exist?" decides whether the user is asked at all.
        ``RawDataController._start_eventfinder`` has the same shape for the same
        reason.

        The table name is the answer *and* the flag - ``None`` means no such column,
        so nothing needs overwriting.

        :param loader: the database loader plugin's key
        :type loader: str
        :return: None
        :rtype: None
        """
        try:
            table_name = self.model.call(
                "MetaDatabaseLoader", loader, "get_table_by_column", "prolate_volume"
            )
        except Exception as e:
            self.logger.error(f"Failed to look for existing fit columns: {e!r}")
            self.add_text_to_display.emit(
                f"Could not check {loader} for existing fit data: {e}",
                self.__class__.__name__,
            )
            return

        self.view.confirm_fit_commit(loader, table_name)

    @log(logger=logger)
    @Slot(str, object, object, object)
    def commit_fits(
        self,
        loader: str,
        fit_data: pd.DataFrame,
        units: List[Optional[str]],
        overwrite_table: Optional[str],
    ) -> None:
        """
        Drop any fit columns being replaced, then write the new ones.

        Phase two, reached either straight away when the database holds no fit data or
        once the user has approved the overwrite. The user's decision travels as
        ``overwrite_table`` rather than being held on the View between the two halves,
        which is what ``_start_eventfinder``'s filter key does.

        The DROP and DELETE statements are built here rather than in the widget - a
        free Step 4b win, since they were the last SQL this method authored.

        :param loader: the database loader plugin's key
        :type loader: str
        :param fit_data: the fitted columns to write, keyed by event id
        :type fit_data: pd.DataFrame
        :param units: one unit per written column, ``None`` where dimensionless
        :type units: List[Optional[str]]
        :param overwrite_table: the table holding fit columns to drop first, or None
        :type overwrite_table: Optional[str]
        :return: None
        :rtype: None
        """
        if overwrite_table is not None:
            columns = [column for column in fit_data.columns if column != "id"]
            try:
                succeeded = self.model.drop_fit_columns(
                    loader, overwrite_table, columns
                )
            except Exception as e:
                self.logger.error(f"Failed to drop the existing fit columns: {e!r}")
                self.add_text_to_display.emit(
                    f"Unable to delete fit data from {loader}, you will have to clean "
                    f"it up manually: {e}",
                    self.__class__.__name__,
                )
                return
            if succeeded is not True:
                self.add_text_to_display.emit(
                    "Unable to delete fit data, you will have to clean it up manually",
                    self.__class__.__name__,
                )
                return

        try:
            written = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "add_columns_to_table",
                fit_data,
                units,
                "events",
            )
        except Exception as e:
            self.logger.error(f"Failed to write the fit data: {e!r}")
            self.add_text_to_display.emit(
                f"Could not write the fit data to {loader}: {e}",
                self.__class__.__name__,
            )
            return

        self.display_write_status(bool(written))
        self.view.on_fit_commit_finished(loader)

    @log(logger=logger)
    @Slot(str, str, object)
    def load_event_distribution_data(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
    ) -> None:
        """
        Build the query for one subset, load its events, and hand both to the View.

        Step 4a, replacing four emits across three View methods. Both distribution
        modes - individual and ensemble - run this same chain, so there is one slot
        rather than one per mode.

        **The ``_raw`` branch this replaced could never work**, which is why it is
        gone rather than converted. It handed a complete ``SELECT`` to
        ``load_event_data`` as its ``conditions`` argument, and that argument is a
        WHERE-clause body: the loader spliced it in after ``WHERE``, SQLite rejected
        the result as a syntax error, ``construct_event_data_query`` returned
        ``("", debug)`` and the generator yielded nothing. Measured against a real
        loader - the same filter as an ordinary WHERE body yields every event, and as
        a raw ``SELECT`` yields none. Raw filters are refused before a plot is
        attempted now; see ``MetaSubsetTabView._refuse_raw_filters``.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the scope the filter is built against
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :return: None
        :rtype: None
        """
        fetched = self._fetch_event_subset(loader, sql_filter, experiments_and_channels)
        if fetched is None:
            return
        query, generator = fetched

        # Set together, once the whole chain has succeeded: the View distinguishes
        # "not fetched" from "fetched and empty" by these two being untouched.
        self.view.set_event_query(query)
        self.view.set_event_data_generator(generator)

    @log(logger=logger)
    def _fetch_event_subset(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
    ) -> Optional[Tuple[str, Generator]]:
        """
        Build one event subset's query and open a generator over its events.

        Shared by the two things that need a subset's events: the individual
        distribution path, which materialises them in the widget, and the ensemble
        path, which hands them straight to the Model. Reports its own failure and
        answers with None, so a caller has nothing to handle beyond stopping.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the scope the filter is built against
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :return: the query that ran and a generator over its events, or None
        :rtype: Optional[Tuple[str, Generator]]
        """
        try:
            # Two values: construct_event_data_query is declared
            # -> Tuple[str, str] and reports a filter it cannot build as
            # ("", debug). call() does not splat it the way the bus did.
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

        if generator is None:
            self.add_text_to_display.emit(
                "No events in dataset or unable to create event generator",
                self.__class__.__name__,
            )
            return None

        return query, generator

    @log(logger=logger)
    @Slot(str, list, object, object, object, str)
    def load_event_plot_data(
        self,
        loader: str,
        event_ids: List[int],
        exp: Optional[str],
        channel: Optional[int],
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
        action_label: str,
    ) -> None:
        """
        Resolve ``event_id`` values to database ids within scope and load those rows.

        Step 4a. This was three emits spread over two View methods - resolve the
        experiment name to an id, query the events table for the primary keys of those
        ``event_id`` values within that scope, then load exactly those rows - each
        answer parked on a View attribute and read back on the next statement. Nothing
        outside the chain read the intermediate answers, so it converts as one intent
        rather than three.

        ``event_id`` is unique only within an experiment and channel, so **an
        experiment that does not resolve stops the plot** rather than widening the
        query: an unscoped match returns whichever channel's row happens to share the
        number. The View's version appended the scope only when the lookup had
        succeeded, which is the same fault ``MetadataController`` was given this guard
        for on 2026-09-09.

        :param loader: the database loader plugin's key
        :type loader: str
        :param event_ids: the ``event_id`` values the navigation snapped to
        :type event_ids: List[int]
        :param exp: the experiment name in scope, or None
        :type exp: Optional[str]
        :param channel: the channel in scope, or None
        :type channel: Optional[int]
        :param experiments_and_channels: the scope ``load_event_data`` wants
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :param action_label: what the caller is plotting, for its messages
        :type action_label: str
        :return: None
        :rtype: None
        """
        if not event_ids:
            self.add_text_to_display.emit(
                f"No events were requested, so there are no {action_label} to plot",
                self.__class__.__name__,
            )
            return

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
                    f"{loader} has no experiment named {exp}, so these {action_label} "
                    "cannot be scoped to it",
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
                f"No data available for the requested {action_label}",
                self.__class__.__name__,
            )
            return
        if "id" not in id_result.columns:
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
                f"No data available for the requested {action_label}",
                self.__class__.__name__,
            )
            return

        self.view.set_event_plot_data_generator(generator)

    @log(logger=logger)
    def check_column_exists(self, table_name: Optional[str]) -> None:
        """
        Notify the view to check if a fit-data column exists in the given table.

        :param table_name: Name of the table containing the queried column, or None if the loader could not resolve one.
        :type table_name: Optional[str]
        """
        self.view.set_column_exists(table_name)

    @log(logger=logger)
    def alter_database_status(self, status: bool) -> None:
        """
        Inform the view whether database alteration was successful.

        :param status: Result of the database alteration operation.
        :type status: bool
        """
        self.view.set_alter_database_status(status)
