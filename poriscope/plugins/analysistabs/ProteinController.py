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

from poriscope.plugins.analysistabs.ProteinModel import EnsembleFit, ProteinModel
from poriscope.plugins.analysistabs.ProteinView import (
    FIT_COLUMN_UNITS,
    FIT_COLUMNS,
    ProteinView,
)
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import RESET_ACTION, log, register_action
from poriscope.utils.MetaSubsetTabController import MetaSubsetTabController


@inherit_docstrings
class ProteinController(MetaSubsetTabController):
    """
    Subclass of MetaSubsetTabController for managing protein view-model logic.

    Relays queries, event data, and filter/column metadata between the
    database backend and ProteinView.
    """

    logger = logging.getLogger(__name__)

    #: Redeclared with this tab's own types, so the type checker sees the methods
    #: the base View and Model do not have (see MetaController.view).
    view: ProteinView
    model: ProteinModel

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
        self.view.individual_distribution_requested.connect(
            self.request_individual_distribution
        )
        self.view.fit_commit_requested.connect(self.check_for_existing_fit_columns)
        self.view.fit_commit_confirmed.connect(self.commit_fits)
        self.view.ensemble_distribution_requested.connect(
            self.request_ensemble_distribution
        )
        self.view.ensemble_report_requested.connect(self.report_ensemble_fit)
        self.view.event_histogram_fits_requested.connect(self.fit_event_histograms)
        self.view.plot_events_requested.connect(self.plot_events)

    @log(logger=logger)
    @register_action(RESET_ACTION)
    def reset(self, axis_type: str = "2d", mode: str = "individual") -> None:
        """
        Clear one analysis mode's figures.

        A recorded action: a plot records one before it draws, with its own mode, so a
        replay clears the figures it was recorded on whichever mode is showing. Clears no
        fit: the plot that resets keeps the fit it draws. See :meth:`_start_figure`.

        :param axis_type: Either '2d' or '3d'; the figures here are always 2-D
        :type axis_type: str
        :param mode: 'individual' or 'ensemble', whose figures are cleared
        :type mode: str
        """
        self.view.clear_plot(axis_type, mode)

    @log(logger=logger)
    def _start_figure(self, mode: str) -> None:
        """
        Clear a mode's figures for a new plot, recording the reset unless it is already the last entry.

        A replay replays the plot's recorded reset before the plot, so the figures are
        already clear and a second reset would be recorded beside the first.

        :param mode: 'individual' or 'ensemble', whose figures the plot draws on
        :type mode: str
        """
        last = next(reversed(self.tab_action_history.values()), None)
        if (
            last is None
            or last.get("action") != RESET_ACTION
            or last.get("kwargs", {}).get("mode") != mode
        ):
            self.reset("2d", mode)

    @log(logger=logger)
    def _one_subset(
        self,
        filters: Dict[str, str],
        scope: Dict[str, List[str]],
        experiments_refusal: str,
        subsets_refusal: str,
    ) -> Optional[Tuple[Any, Any, str, str]]:
        """
        The one experiment, channel and subset a distribution plot draws, or say why not.

        :param filters: the selected filters, name to SQL; none means the full dataset
        :type filters: Dict[str, str]
        :param scope: the selected experiments and their channels
        :type scope: Dict[str, List[str]]
        :param experiments_refusal: what to say when more than one experiment is selected
        :type experiments_refusal: str
        :param subsets_refusal: what to say when more than one subset is selected
        :type subsets_refusal: str
        :return: the experiment, channel, subset name and its SQL, or None if refused
        :rtype: Optional[Tuple[Any, Any, str, str]]
        """
        selected = dict(filters) if filters else {"Full Dataset": ""}
        datasets: Dict[Any, List[Any]] = (
            copy.deepcopy(scope) if scope else {None: [None]}
        )
        refusal = None
        if len(datasets) > 1:
            refusal = experiments_refusal
        elif len(selected) > 1:
            refusal = subsets_refusal
        elif len(next(iter(datasets.values()))) != 1:
            refusal = "Only a single channel at a time can be used for protein analysis"
        if refusal is not None:
            self.add_text_to_display.emit(refusal, self.__class__.__name__)
            return None
        exp, channels = next(iter(datasets.items()))
        subset_name, sql_filter = next(iter(selected.items()))
        return exp, channels[0], subset_name, sql_filter

    @log(logger=logger)
    @Slot(str, object, object, object, bool, float, float, int)
    def request_ensemble_distribution(
        self,
        loader: str,
        filters: Dict[str, str],
        scope: Dict[str, List[str]],
        bins: Optional[List[Union[int, float]]],
        sizes: bool,
        pore_diameter: float,
        pore_length: float,
        n_values: int,
    ) -> None:
        """
        Ask about a raw filter that lacks ``event_id``, then draw the Ensemble plot a click asked for.

        The question is the click's alone, as for the Individual plot.

        :param loader: the database loader plugin's key
        :type loader: str
        :param filters: the selected filters, name to SQL; none means the full dataset
        :type filters: Dict[str, str]
        :param scope: the selected experiments and their channels
        :type scope: Dict[str, List[str]]
        :param bins: a bin count, or a bin width when sizes is True, or None to estimate
        :type bins: Optional[List[Union[int, float]]]
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param pore_diameter: the diameter of the pore in nanometers
        :type pore_diameter: float
        :param pore_length: the length of the pore in nanometers
        :type pore_length: float
        :param n_values: target number of samples to draw for each shape
        :type n_values: int
        :return: None
        :rtype: None
        """
        resolved = self._ask_event_id_for_raw_filters(loader, filters, scope)
        if resolved is None:
            return
        self.update_ensemble_distribution(
            loader, resolved, scope, bins, sizes, pore_diameter, pore_length, n_values
        )

    @log(logger=logger)
    @register_action("update_ensemble_distribution", skip_on_false=True)
    def update_ensemble_distribution(
        self,
        loader: str,
        filters: Dict[str, str],
        scope: Dict[str, List[str]],
        bins: Optional[List[Union[int, float]]],
        sizes: bool,
        pore_diameter: float,
        pore_length: float,
        n_values: int,
    ) -> bool:
        """
        Average one subset into a histogram, fit it, keep the fit, and draw the geometries it implies.

        A recorded action: it takes the intent the click captured, so a replay draws what
        was recorded whatever the panel shows then. One experiment, one channel and one
        subset; anything else is refused. The Ensemble figures are reset and the Ensemble
        fit forgotten once the histogram has been built, so a refused or failed fetch
        leaves both as they were and records nothing. A histogram that cannot be fitted
        is still drawn, and says why on the status panel.

        :param loader: the database loader plugin's key
        :type loader: str
        :param filters: the selected filters, name to SQL; none means the full dataset
        :type filters: Dict[str, str]
        :param scope: the selected experiments and their channels
        :type scope: Dict[str, List[str]]
        :param bins: a bin count, or a bin width when sizes is True, or None to estimate
        :type bins: Optional[List[Union[int, float]]]
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param pore_diameter: the diameter of the pore in nanometers
        :type pore_diameter: float
        :param pore_length: the length of the pore in nanometers
        :type pore_length: float
        :param n_values: target number of samples to draw for each shape
        :type n_values: int
        :return: True if the histogram was drawn, False if refused or nothing was built
        :rtype: bool
        """
        plot_type = "Filtered Histogram"
        subset = self._one_subset(
            filters,
            scope,
            f"Only a single experiment can be used for {plot_type}",
            f"Only a single subset can be used for {plot_type}",
        )
        if subset is None:
            return False
        exp, channel, subset_name, sql_filter = subset

        fetched = self._fetch_event_subset(
            loader, sql_filter, {exp: [channel]}, subset_name
        )
        if fetched is None:
            return False
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
            return False
        if plot_data is None:
            self.add_text_to_display.emit(
                "No usable events in the selected subset, so there is nothing to plot",
                self.__class__.__name__,
            )
            return False

        self._start_figure("ensemble")
        self.model.set_ensemble_fit(None)
        self.view.set_event_query(query)
        label = (
            f"{loader} | {exp} Ch {channel}: {subset_name}"
            if exp is not None
            else f"{loader} | {subset_name}"
        )
        self.view.show_histogram("ensemble", plot_data, label)
        self._fit_ensemble(plot_data, bins, sizes, pore_diameter, pore_length, n_values)
        return True

    @log(logger=logger)
    def _fit_ensemble(
        self,
        plot_data: pd.DataFrame,
        bins: Any,
        sizes: bool,
        d: float,
        L: float,
        N: int,
    ) -> None:
        """
        Fit the Ensemble histogram, keep the fit, and draw it with the geometries it implies.

        A fit that fails its sanity checks is not an error - the histogram stays drawn and
        the status panel says why. An ensemble that sampled nothing still draws its fit.

        :param plot_data: the averaged histogram, as bin centers and amplitudes
        :type plot_data: pd.DataFrame
        :param bins: the bins entry the histogram was built with
        :type bins: Any
        :param sizes: does bins refer to a bin width
        :type sizes: bool
        :param d: the diameter of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :param N: target number of samples to draw for each shape
        :type N: int
        """
        try:
            popt, curve = self.model.fit_histogram(
                plot_data["Normalized Current"].values, plot_data["Amplitude"].values
            )
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

        fitted = plot_data.copy()
        fitted["Amplitude"] = curve
        self.view.show_histogram("ensemble", fitted, "Fit")
        self.model.set_ensemble_fit(
            EnsembleFit(popt, bins, sizes, df_prolate, df_oblate)
        )
        self._show_distribution("ensemble", df_prolate, df_oblate, None)

    @log(logger=logger)
    def _show_distribution(
        self,
        mode: str,
        df_prolate: pd.DataFrame,
        df_oblate: pd.DataFrame,
        peaks: Optional[pd.DataFrame],
    ) -> None:
        """
        Have the View draw the sampled shapes and, for the Individual plot, each event's peaks.

        Each plot's columns are filtered by the Model first, dropping what cannot be
        drawn, so the points and their error bars stay aligned.

        :param mode: 'individual' or 'ensemble', whose figures are drawn on
        :type mode: str
        :param df_prolate: the prolate solutions
        :type df_prolate: pd.DataFrame
        :param df_oblate: the oblate solutions
        :type df_oblate: pd.DataFrame
        :param peaks: one fit row per event, or None for the Ensemble plot
        :type peaks: Optional[pd.DataFrame]
        """
        for solutions, label in (
            (df_prolate, "Prolate Solutions"),
            (df_oblate, "Oblate Solutions"),
        ):
            if solutions.empty:
                continue
            filtered = self._drawable(solutions["V"].values, solutions["m"].values)
            if filtered is not None:
                self.view.show_solutions(mode, filtered, label)
        if peaks is None or peaks.empty:
            return
        filtered = self._drawable(
            peaks["min_fractional_blockage"].values,
            peaks["max_fractional_blockage"].values,
            peaks["min_fractional_blockage_std"].values,
            peaks["max_fractional_blockage_std"].values,
        )
        if filtered is not None:
            self.view.show_peak_fits(mode, filtered, "Event Peak Fit Parameters")

    @log(logger=logger)
    def _drawable(
        self, *columns: npt.NDArray[np.float64]
    ) -> Optional[List[npt.NDArray[np.float64]]]:
        """
        The rows of these columns that can be drawn, none log-scaled, or None if they cannot be filtered.

        :param \\*columns: the columns of one plot, index-aligned
        :type \\*columns: npt.NDArray[np.float64]
        :return: the filtered columns, or None after saying why on the status panel
        :rtype: Optional[List[npt.NDArray[np.float64]]]
        """
        try:
            filtered = list(
                self.model.logscale_and_filter_columns(
                    *columns, log_flags=[False] * len(columns)
                )
            )
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to filter the scatterplot: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to filter the scatterplot: {e}", self.__class__.__name__
            )
            return None
        return filtered

    @log(logger=logger)
    @register_action("plot_events", skip_on_false=True)
    def plot_events(
        self,
        loader: str,
        event_ids: List[int],
        experiment: Optional[str],
        channel: Optional[str],
        subset_name: str,
        sql_filter: str,
        raw: bool,
    ) -> bool:
        """
        Draw these events on the event page, one subplot each, in the order given.

        A recorded action: it takes the events the click resolved from the Event ID through
        the filtered-event cache, so a replay draws these events whatever the panel and the
        cache hold then. The filter's name and SQL are not used to fetch - the ids already
        are the subset - and are kept so the entry says which subset they came from. The
        event page is neither mode's figure, so no reset is recorded.

        :param loader: the database loader plugin's key
        :type loader: str
        :param event_ids: the ``event_id`` values to draw, in grid order
        :type event_ids: List[int]
        :param experiment: the experiment the events belong to
        :type experiment: Optional[str]
        :param channel: the channel the events belong to, as the selection tree reports it
        :type channel: Optional[str]
        :param subset_name: the name of the filter the events were taken from
        :type subset_name: str
        :param sql_filter: that filter's SQL
        :type sql_filter: str
        :param raw: draw each event's raw trace as well
        :type raw: bool
        :return: True if drawn, False if refused or no event could be loaded
        :rtype: bool
        """
        channel_id = int(channel) if channel is not None else None
        scope: Dict[Any, Any] = {experiment: [channel]}
        events = self.fetch_event_plot_data(
            loader, event_ids, experiment, channel_id, scope, "events"
        )
        if events is None:
            # Refused, and the fetch has said why; naming the event would contradict it.
            return False
        order = {event_id: i for i, event_id in enumerate(event_ids)}
        event_data = sorted(
            events, key=lambda event: order.get(event["event_id"], len(order))
        )
        if not event_data:
            self.add_text_to_display.emit(
                f"No data available for event_id {event_ids[0] if event_ids else None}",
                self.__class__.__name__,
            )
            return False
        self.view.show_events(event_data, use_raw=raw)
        return True

    @log(logger=logger)
    @Slot()
    def report_ensemble_fit(self) -> None:
        """
        Hand the View the Ensemble fit the Model keeps, for Report All.

        :return: None
        :rtype: None
        """
        fit = self.model.ensemble_fit
        if fit is None:
            self.add_text_to_display.emit(
                "No ensemble fit available to report. Run Update Plot in Ensemble mode "
                "first.",
                self.__class__.__name__,
            )
            self.logger.warning("No ensemble fit available to report")
            return
        self.view.show_ensemble_report(
            fit.params, fit.bins, fit.sizes, fit.prolate, fit.oblate
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

        A request slot. One call rather than one per event keeps each answer off the
        widget; see ``ProteinModel.fit_histograms``. The binning happens ahead of the
        fitting in the same call, so the two describe the same bins and the widget is
        handed the histograms rather than building them.

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
    @Slot(str, object, object, object, bool, float, float, int)
    def request_individual_distribution(
        self,
        loader: str,
        filters: Dict[str, str],
        scope: Dict[str, List[str]],
        bins: Optional[List[Union[int, float]]],
        sizes: bool,
        pore_diameter: float,
        pore_length: float,
        n_values: int,
    ) -> None:
        """
        Ask about a raw filter that lacks ``event_id``, then draw the Individual plot a click asked for.

        The question is the click's alone: the plot is recorded with the filter text that
        will run, so a replay, which calls :meth:`update_individual_distribution` directly,
        has nothing to ask.

        :param loader: the database loader plugin's key
        :type loader: str
        :param filters: the selected filters, name to SQL; none means the full dataset
        :type filters: Dict[str, str]
        :param scope: the selected experiments and their channels
        :type scope: Dict[str, List[str]]
        :param bins: a bin count, or a bin width when sizes is True, or None to estimate
        :type bins: Optional[List[Union[int, float]]]
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param pore_diameter: the diameter of the pore in nanometers
        :type pore_diameter: float
        :param pore_length: the length of the pore in nanometers
        :type pore_length: float
        :param n_values: target number of samples to draw for each event
        :type n_values: int
        :return: None
        :rtype: None
        """
        resolved = self._ask_event_id_for_raw_filters(loader, filters, scope)
        if resolved is None:
            return
        self.update_individual_distribution(
            loader, resolved, scope, bins, sizes, pore_diameter, pore_length, n_values
        )

    @log(logger=logger)
    @register_action("update_individual_distribution", skip_on_false=True)
    def update_individual_distribution(
        self,
        loader: str,
        filters: Dict[str, str],
        scope: Dict[str, List[str]],
        bins: Optional[List[Union[int, float]]],
        sizes: bool,
        pore_diameter: float,
        pore_length: float,
        n_values: int,
    ) -> bool:
        """
        Fit every event of one subset, keep the fit, and draw the geometries it implies.

        A recorded action: it takes the intent the click captured, so a replay draws what
        was recorded whatever the panel shows then. One experiment, one channel and one
        subset; anything else is refused on the status panel. The figures are reset and
        the Individual fit replaced only once the events have been fetched and fitted, so
        a refused or failed plot leaves both as they were and records nothing.

        :param loader: the database loader plugin's key
        :type loader: str
        :param filters: the selected filters, name to SQL; none means the full dataset
        :type filters: Dict[str, str]
        :param scope: the selected experiments and their channels
        :type scope: Dict[str, List[str]]
        :param bins: a bin count, or a bin width when sizes is True, or None to estimate
        :type bins: Optional[List[Union[int, float]]]
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param pore_diameter: the diameter of the pore in nanometers
        :type pore_diameter: float
        :param pore_length: the length of the pore in nanometers
        :type pore_length: float
        :param n_values: target number of samples to draw for each event
        :type n_values: int
        :return: True if drawn, False if refused or nothing could be fitted
        :rtype: bool
        """
        plot_type = "Filtered Histogram"
        subset = self._one_subset(
            filters,
            scope,
            f"Only a single experiment can be used for {plot_type}",
            "Only a single subset can be used for protein analysis",
        )
        if subset is None:
            return False
        exp, channel, subset_name, sql_filter = subset

        fetched = self._fetch_event_subset(
            loader, sql_filter, {exp: [channel]}, subset_name
        )
        if fetched is None:
            return False
        query, generator = fetched
        fitted = self._fit_individual_events(
            list(generator),
            plot_type,
            bins,
            sizes,
            pore_diameter,
            pore_length,
            n_values,
        )
        if fitted is None:
            return False
        df_prolate, df_oblate, fit_data = fitted

        self._start_figure("individual")
        self.model.set_individual_fit(fit_data)
        self.view.set_event_query(query)
        self._show_distribution("individual", df_prolate, df_oblate, fit_data)
        return True

    @log(logger=logger)
    def _fit_individual_events(
        self,
        event_data: Sequence[Dict[str, Any]],
        plot_type: str,
        bins: Any,
        sizes: bool,
        d: float,
        L: float,
        N: int,
    ) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
        """
        Bin and fit every event, and sample the geometries each fit is consistent with.

        Reports its own failure on the status panel and answers None.

        :param event_data: the subset's events
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
        :param N: target number of samples to draw for each event
        :type N: int
        :return: the pooled prolate and oblate solutions and one fit row per event, or None
        :rtype: Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]
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
            return None

        if fit_data.empty:
            # Every event was refused, or the subset held none at all. Every guard in
            # the drawing half tests a frame built from these events, so without this
            # the tab drew empty axes and said nothing.
            self.add_text_to_display.emit(
                "No events in the selected subset could be fitted, so there is "
                "nothing to plot",
                self.__class__.__name__,
            )
            return None
        return df_prolate, df_oblate, fit_data

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
        if self.model.individual_fit is None:
            self.add_text_to_display.emit(
                "No individual fit available to commit. Run Update Plot in Individual "
                "mode first.",
                self.__class__.__name__,
            )
            return
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
    @Slot(str, object)
    def commit_fits(self, loader: str, overwrite_table: Optional[str]) -> None:
        """
        Drop any fit columns being replaced, then write the Individual fit the Model keeps.

        Phase two, reached either straight away when the database holds no fit data or
        once the user has approved the overwrite. The user's decision travels as
        ``overwrite_table`` rather than being held on the View between the two halves,
        which is what ``_start_eventfinder``'s filter key does.

        The DROP and DELETE statements are built here rather than in the widget, for
        the same reason as every other piece of SQL: writing it is not a widget's job.

        :param loader: the database loader plugin's key
        :type loader: str
        :param overwrite_table: the table holding fit columns to drop first, or None
        :type overwrite_table: Optional[str]
        :return: None
        :rtype: None
        """
        if self.model.individual_fit is None:
            return
        fit_data = self.model.individual_fit[["id"] + FIT_COLUMNS]
        units = FIT_COLUMN_UNITS
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
    def _fetch_event_subset(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        subset_name: str,
    ) -> Optional[Tuple[str, Generator]]:
        """
        Build one event subset's query and open a generator over its events.

        Shared by the two things that need a subset's events: the individual
        distribution path, which materialises them in the widget, and the ensemble
        path, which hands them straight to the Model. Reports its own failure and
        answers with None, so a caller has nothing to handle beyond stopping.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows, or a complete ``SELECT`` for a raw filter
        :type sql_filter: str
        :param experiments_and_channels: the scope the filter is built against
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

        return (shown_query if is_raw else query), generator
