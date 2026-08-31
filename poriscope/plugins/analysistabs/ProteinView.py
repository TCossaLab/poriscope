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

import numpy as np
import numpy.typing as npt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLayout,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, peak_widths
from scipy.stats import t
from typing_extensions import override

from poriscope.plugins.analysistabs.utils.proteincontrols import ProteinControls
from poriscope.plugins.analysistabs.utils.walkthrough_mixin import (
    WalkthroughMixin,
    WalkthroughStep,
)
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log, register_action
from poriscope.utils.MetaView import MetaView
from poriscope.views.widgets.add_subset_filter_dialog import AddSubsetFilterDialog
from poriscope.views.widgets.edit_subset_filter_dialog import EditSubsetFilterDialog
from poriscope.views.widgets.multiselect import MultiSelectComboBox
from poriscope.views.widgets.SelectionTree import SelectionTree

warnings.filterwarnings(
    "ignore",
    message="constrained_layout not applied because axes sizes collapsed to zero",
)


@inherit_docstrings
class ProteinView(MetaView, WalkthroughMixin):
    """
    Subclass of MetaView for estimating translocating protein size and shape from nanopore blockage events.

    Given pore diameter/length, fits a two-population (prolate/oblate) volume-and-shape-factor model via Monte Carlo rejection sampling, either per event (Individual mode) or across the aggregate distribution (Ensemble mode). Also supports subset filtering, per-event trace/histogram inspection, and committing or reporting fit results.
    """

    logger = logging.getLogger(__name__)

    @property
    def fig_hist(self) -> Figure:
        return (
            self.fig_hist_individual
            if self._analysis_mode == "individual"
            else self.fig_hist_ensemble
        )

    @fig_hist.setter
    def fig_hist(self, value: Figure) -> None:
        if self._analysis_mode == "individual":
            self.fig_hist_individual = value
        else:
            self.fig_hist_ensemble = value

    @property
    def ax_hist(self) -> Axes:
        return (
            self.ax_hist_individual
            if self._analysis_mode == "individual"
            else self.ax_hist_ensemble
        )

    @ax_hist.setter
    def ax_hist(self, value: Axes) -> None:
        if self._analysis_mode == "individual":
            self.ax_hist_individual = value
        else:
            self.ax_hist_ensemble = value

    @property
    def canvas_hist(self) -> FigureCanvas:
        return (
            self.canvas_hist_individual
            if self._analysis_mode == "individual"
            else self.canvas_hist_ensemble
        )

    @canvas_hist.setter
    def canvas_hist(self, value: FigureCanvas) -> None:
        if self._analysis_mode == "individual":
            self.canvas_hist_individual = value
        else:
            self.canvas_hist_ensemble = value

    @property
    def fig_vm(self) -> Figure:
        return (
            self.fig_vm_individual
            if self._analysis_mode == "individual"
            else self.fig_vm_ensemble
        )

    @fig_vm.setter
    def fig_vm(self, value: Figure) -> None:
        if self._analysis_mode == "individual":
            self.fig_vm_individual = value
        else:
            self.fig_vm_ensemble = value

    @property
    def ax_vm(self) -> Axes:
        return (
            self.ax_vm_individual
            if self._analysis_mode == "individual"
            else self.ax_vm_ensemble
        )

    @ax_vm.setter
    def ax_vm(self, value: Axes) -> None:
        if self._analysis_mode == "individual":
            self.ax_vm_individual = value
        else:
            self.ax_vm_ensemble = value

    @property
    def canvas_vm(self) -> FigureCanvas:
        return (
            self.canvas_vm_individual
            if self._analysis_mode == "individual"
            else self.canvas_vm_ensemble
        )

    @canvas_vm.setter
    def canvas_vm(self, value: FigureCanvas) -> None:
        if self._analysis_mode == "individual":
            self.canvas_vm_individual = value
        else:
            self.canvas_vm_ensemble = value

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._init()
        self._init_walkthrough()

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the ProteinView instance.
        """
        self._clear_cache()
        self.fit_data: Optional[pd.DataFrame] = None
        self.operation_success: bool = False
        self.ensemble_fit_params: Optional[tuple] = None
        self.ensemble_fit_bins: Optional[Any] = None
        self.ensemble_fit_sizes: Optional[bool] = None
        self.ensemble_fit_prolate_summary: Optional[tuple] = None
        self.ensemble_fit_oblate_summary: Optional[tuple] = None
        self.plot_initialized = False
        self.no_cached_data = False

        self._analysis_mode: str = (
            "individual"  # default mode; toggled by Individual/Ensemble buttons
        )

        self.subset_export_count = 0
        self.hist_min: Optional[float] = None
        self.hist_max: Optional[float] = None
        # Heterogeneous by design: _plot_all_points_histogram appends (x, y)
        # tuples rather than plain arrays. Flagged for review.
        self.hist_data: List[Any] = []
        self.hist_labels: List[Optional[str]] = []
        self.current_sql_filter: Optional[str] = None
        self.current_experiment: Optional[str] = None
        self.current_channel: Optional[int] = None
        self._pending_filter_name: Optional[str] = None
        self._pending_filter_text: Optional[str] = None
        self._pending_old_filter_name: Optional[str] = None
        self.filtered_event_ids: List[int] = []
        self.subset_filters: Dict[str, str] = {}
        self.plot_events_generator: Optional[Iterator[Dict[str, Any]]] = None
        self.available_experiment_and_channels_by_loader: Dict[
            str, Dict[str, List[str]]
        ] = {}
        self.available_columns: List[str] = []
        self.selected_experiment_and_channels_by_loader: Dict[
            str, Dict[str, List[str]]
        ] = {}
        self.allowed_plot_type: Optional[str] = None
        self.allowed_columns: List[str] = []
        self.allowed_logs: List[bool] = []
        self.allowed_bins: Optional[Any] = None
        self.allowed_sizes: Optional[bool] = None

        self._show_sql_in_display: bool = False
        self._show_event_sql_in_display: bool = False

        self._last_event_action: str = "plot_events"  # or "plot_histogram"

        self.plotted_datasets: Set[
            Tuple[
                Optional[str],
                Optional[str],
                Optional[int],
                Optional[str],
                Optional[str],
            ]
        ] = set()
        # list of tuples of things already plotted: (loader, experiment, channel, filter, subset name), which can be None

    @override
    def _set_custom_display_area(self, layout: QLayout) -> None:
        """
        Initialize the display area with two independent sets of canvases — one for
        Individual mode, one for Ensemble mode — shown via a nested QStackedWidget,
        plus a separate full-canvas page for event plots. Each mode's histogram/V-M
        plots persist independently; switching modes shows that mode's last-drawn
        plot immediately, with no redraw needed.
        """
        display_container = QWidget()
        display_container.setObjectName("displayContainer")
        display_container.setStyleSheet(
            "#displayContainer { border: 2px solid black; border-radius: 15px; }"
        )
        outer = QVBoxLayout(display_container)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)
        self.display_stack = QStackedWidget()
        self.display_stack.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.display_stack, stretch=1)

        # Page 0: distribution — nested stack, one page per analysis mode
        self.mode_stack = QStackedWidget()

        (
            self.individual_dist_page,
            self.fig_hist_individual,
            self.canvas_hist_individual,
            self.ax_hist_individual,
            self.fig_vm_individual,
            self.canvas_vm_individual,
            self.ax_vm_individual,
        ) = self._build_dist_page()

        (
            self.ensemble_dist_page,
            self.fig_hist_ensemble,
            self.canvas_hist_ensemble,
            self.ax_hist_ensemble,
            self.fig_vm_ensemble,
            self.canvas_vm_ensemble,
            self.ax_vm_ensemble,
        ) = self._build_dist_page()

        self.mode_stack.addWidget(self.individual_dist_page)  # index 0
        self.mode_stack.addWidget(self.ensemble_dist_page)  # index 1
        self.mode_stack.setCurrentWidget(self.individual_dist_page)

        # Page 1: event (single full canvas, shared across modes — not mode-scoped)
        event_page = QWidget()
        event_outer = QVBoxLayout(event_page)
        event_outer.setContentsMargins(0, 0, 0, 0)
        event_outer.setSpacing(0)
        self.fig_event = Figure()
        self.canvas_event = FigureCanvas(self.fig_event)
        self.event_outer_ax = None
        event_outer.addWidget(self.canvas_event, stretch=1)
        self.event_toolbar = NavigationToolbar(self.canvas_event, self)
        event_outer.addWidget(self.event_toolbar)

        self.display_stack.addWidget(self.mode_stack)  # index 0
        self.display_stack.addWidget(event_page)  # index 1
        layout.addWidget(display_container, stretch=4)
        self._display_mode = "distribution"

    @log(logger=logger)
    def _build_dist_page(self) -> tuple:
        """
        Build one distribution page: a histogram canvas and V/M canvas side by
        side, each with its own navigation toolbar underneath.

        :return: Tuple of (page_widget, fig_hist, canvas_hist, ax_hist, fig_vm,
                canvas_vm, ax_vm) for this page.
        :rtype: tuple
        """
        page = QWidget()
        page_outer = QVBoxLayout(page)
        page_outer.setContentsMargins(0, 0, 0, 0)
        page_outer.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        page_outer.addLayout(row, stretch=1)

        fig_hist = Figure()
        canvas_hist = FigureCanvas(fig_hist)
        ax_hist = fig_hist.add_subplot(1, 1, 1)
        fig_vm = Figure()
        canvas_vm = FigureCanvas(fig_vm)
        ax_vm = fig_vm.add_subplot(1, 1, 1)
        row.addWidget(canvas_hist, stretch=1)
        row.addWidget(canvas_vm, stretch=1)

        toolbar_hist = NavigationToolbar(canvas_hist, self)
        toolbar_vm = NavigationToolbar(canvas_vm, self)
        toolbar_row = QHBoxLayout()
        toolbar_row.addWidget(toolbar_hist)
        toolbar_row.addWidget(toolbar_vm)
        page_outer.addLayout(toolbar_row)

        return page, fig_hist, canvas_hist, ax_hist, fig_vm, canvas_vm, ax_vm

    def _set_display_mode(self, mode: str) -> None:
        """
        Switch between distribution view (hist + V/M)
        and full event plot view.
        """
        if mode == "event":
            self.display_stack.setCurrentIndex(1)
            self._display_mode = "event"
        else:
            self.display_stack.setCurrentIndex(0)
            self._display_mode = "distribution"

    @log(logger=logger)
    def _commit_fits(self, loader: str) -> None:
        """
        Commits fitted data to the database

        :param loader: Name or ID of the database loader plugin.
        :type loader: str
        :raises AttributeError: If fit data has not been set on this view.
        """
        if self.fit_data is None:
            raise AttributeError("fit data has not been set, unable to commit")
        fit_data = self.fit_data[
            [
                "id",
                "prolate_volume",
                "prolate_shape_factor",
                "prolate_major_axis",
                "prolate_minor_axis",
                "oblate_volume",
                "oblate_shape_factor",
                "oblate_major_axis",
                "oblate_minor_axis",
                "min_fractional_blockage",
                "min_fractional_blockage_std",
                "max_fractional_blockage",
                "max_fractional_blockage_std",
            ]
        ]
        units = [
            "nm^3",
            None,
            "nm",
            "nm",
            "nm^3",
            None,
            "nm",
            "nm",
            None,
            None,
            None,
            None,
        ]
        table_name = "events"

        self.column_table = None
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "get_table_by_column",
            ("prolate_volume",),
            "check_column_exists",
            (),
        )
        if self.column_table is not None:
            reply = QMessageBox.question(
                self,
                "Confirm Overwrite",
                "fit data data already exists, are you sure you want to overwrite? This action cannot be undone.",
                QMessageBox.Ok | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Ok:
                self.operation_success = False
                queries = [
                    f"ALTER TABLE {self.column_table} DROP COLUMN prolate_volume",
                    f"ALTER TABLE {self.column_table} DROP COLUMN prolate_shape_factor",
                    f"ALTER TABLE {self.column_table} DROP COLUMN prolate_major_axis",
                    f"ALTER TABLE {self.column_table} DROP COLUMN prolate_minor_axis",
                    f"ALTER TABLE {self.column_table} DROP COLUMN min_fractional_blockage",
                    f"ALTER TABLE {self.column_table} DROP COLUMN min_fractional_blockage_std",
                    f"ALTER TABLE {self.column_table} DROP COLUMN max_fractional_blockage",
                    f"ALTER TABLE {self.column_table} DROP COLUMN max_fractional_blockage_std",
                    "DELETE FROM columns WHERE name = 'prolate_volume'",
                    "DELETE FROM columns WHERE name = 'prolate_shape_factor'",
                    "DELETE FROM columns WHERE name = 'prolate_major_axis'",
                    "DELETE FROM columns WHERE name = 'prolate_minor_axis'",
                    "DELETE FROM columns WHERE name = 'min_fractional_blockage'",
                    "DELETE FROM columns WHERE name = 'min_fractional_blockage_std'",
                    "DELETE FROM columns WHERE name = 'max_fractional_blockage'",
                    "DELETE FROM columns WHERE name = 'max_fractional_blockage_std'",
                    f"ALTER TABLE {self.column_table} DROP COLUMN oblate_volume",
                    f"ALTER TABLE {self.column_table} DROP COLUMN oblate_shape_factor",
                    f"ALTER TABLE {self.column_table} DROP COLUMN oblate_major_axis",
                    f"ALTER TABLE {self.column_table} DROP COLUMN oblate_minor_axis",
                    "DELETE FROM columns WHERE name = 'oblate_volume'",
                    "DELETE FROM columns WHERE name = 'oblate_shape_factor'",
                    "DELETE FROM columns WHERE name = 'oblate_major_axis'",
                    "DELETE FROM columns WHERE name = 'oblate_minor_axis'",
                ]

                self.global_signal.emit(
                    "MetaDatabaseLoader",
                    loader,
                    "alter_database",
                    (queries,),
                    "alter_database_status",
                    (),
                )
                if self.operation_success is not True:
                    self.add_text_to_display.emit(
                        "Unable to delete fit data, you will have to clean it up manually",
                        self.__class__.__name__,
                    )
                    return
            else:
                return
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "add_columns_to_table",
            (fit_data, units, table_name),
            "display_write_status",
            (),
        )
        self.update_available_columns(loader)  # refresh this tab locally
        self.plugin_state_changed.emit(
            "MetaDatabaseLoader", loader, "columns"
        )  # notify everyone else

    @log(logger=logger)
    def _summarize_vm(self, df: pd.DataFrame) -> tuple:
        """
        Build a one-line median +/- std summary of V, a, b, m for a sampled shape DataFrame.
        Falls back to a plain-value readout when there is only one sample (std is undefined
        for N=1), and reports explicitly when there are no samples at all.

        :param df: DataFrame with columns "V", "m", "a", "b" from Monte Carlo shape sampling.
        :type df: pd.DataFrame
        :return: Tuple of (list of formatted "label = value" row strings, sample-count label string).
        :rtype: tuple
        """
        n = len(df)

        if n == 0:
            return ([], "no samples generated")

        if n == 1:
            rows = [
                f"V = {df['V'].iloc[0]:.1f} nm\u00b3",
                f"a = {df['a'].iloc[0]:.1f} nm",
                f"b = {df['b'].iloc[0]:.1f} nm",
                f"m = {df['m'].iloc[0]:.2f}",
            ]
            return (rows, "N=1 sample, std undefined for a single sample")

        rows = [
            f"V = {df['V'].median():.1f} \u00b1 {df['V'].std():.1f} nm\u00b3",
            f"a = {df['a'].median():.1f} \u00b1 {df['a'].std():.1f} nm",
            f"b = {df['b'].median():.1f} \u00b1 {df['b'].std():.1f} nm",
            f"m = {df['m'].median():.2f} \u00b1 {df['m'].std():.2f}",
        ]
        return (rows, f"N={n} samples")

    @log(logger=logger)
    def _report_ensemble_fit(self) -> None:
        """
        Report the double-Gaussian fit parameters and V/m sample summaries from the
        most recent ensemble distribution fit, alongside the binning configuration
        that produced them. Ensemble mode has no per-event id to write these back
        to the database against, so this is a display-only report rather than a
        database commit. Takes no arguments; reads entirely from self.ensemble_fit_*
        state set by _update_distribution_ensemble and cleared by _reset_actions.

        :return: None
        :rtype: None
        """
        if self.ensemble_fit_params is None:
            self.add_text_to_display.emit(
                "No ensemble fit available to report. Run Update Plot in Ensemble mode first.",
                self.__class__.__name__,
            )
            self.logger.warning("No ensemble fit available to report")
            return

        amp1, mean1, std1, amp2, mean2, std2 = self.ensemble_fit_params

        if self.ensemble_fit_sizes:
            bin_desc = f"bin size(s) = {self.ensemble_fit_bins}"
        else:
            bin_desc = f"bin count = {self.ensemble_fit_bins or 100}"

        lines = [
            "<br>",
            f"<b>Ensemble double-Gaussian fit</b> ({bin_desc})",
            f"&nbsp;&nbsp;Peak 1: amplitude={amp1:.4g}, mean={mean1:.4g}, std={std1:.4g}",
            f"&nbsp;&nbsp;Peak 2: amplitude={amp2:.4g}, mean={mean2:.4g}, std={std2:.4g}",
            "",
        ]

        if self.ensemble_fit_prolate_summary:
            rows, count_label = self.ensemble_fit_prolate_summary
            lines.append(f"<b>Prolate</b> ({count_label})")
            lines.extend(f"&nbsp;&nbsp;{row}" for row in rows)
            lines.append("")

        if self.ensemble_fit_oblate_summary:
            rows, count_label = self.ensemble_fit_oblate_summary
            lines.append(f"<b>Oblate</b> ({count_label})")
            lines.extend(f"&nbsp;&nbsp;{row}" for row in rows)

        self.add_text_to_display.emit("<br>".join(lines), self.__class__.__name__)

    @log(logger=logger)
    def set_alter_database_status(self, status: bool) -> None:
        """
        Sets the success status of a database operation.

        :param status: True if successful, False otherwise.
        :type status: bool
        """
        self.operation_success = status

    @log(logger=logger)
    @override
    def _set_control_area(self, layout: QBoxLayout) -> None:
        """
        Set up the control area layout by inserting metadata controls.

        :param layout: The layout to which the controls will be added.
        :type layout: QBoxLayout
        """
        self.proteincontrols = ProteinControls()
        self.proteincontrols.actionTriggered.connect(self.handle_parameter_change)
        self.proteincontrols.edit_processed.connect(self.handle_edit_triggered)
        self.proteincontrols.add_processed.connect(self.handle_add_triggered)
        self.proteincontrols.delete_processed.connect(self.handle_delete_triggered)
        self.proteincontrols.edit_filter_requested.connect(self.show_edit_filter_dialog)
        self.proteincontrols.delete_filter_requested.connect(
            self._delete_filter_by_name
        )

        controlsAndAnalysisLayout = QHBoxLayout()
        controlsAndAnalysisLayout.setContentsMargins(0, 0, 0, 0)

        # Add the rawdatacontrols directly to the main layout
        controlsAndAnalysisLayout.addWidget(self.proteincontrols, stretch=1)

        layout.setSpacing(0)
        layout.addLayout(controlsAndAnalysisLayout, stretch=1)

    @log(logger=logger)
    def update_column_names(self, column_names: List[str]) -> None:
        """
        Store available column names for internal use (filter validation, etc.)
        No UI update is performed.

        :param column_names: List of column names retrieved from the database.
        :type column_names: List[str]
        """
        self.available_columns = column_names

    @log(logger=logger)
    def set_channel_db_id(self, channel_db_id: Optional[int]) -> None:
        """
        A global signal callback that provides the channel_db_id for raw query scoping.

        :param channel_db_id: Database id of the scoped channel, or None if unresolved.
        :type channel_db_id: Optional[int]
        """
        self.channel_db_id = channel_db_id

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
        Canonical figure reset for the event figure.

        :param axis_type: Unused, kept for interface compatibility.
        :type axis_type: str
        :param create_default_axes: Whether to recreate a default axes after clearing
                                    the figure. If False, the figure is left without axes.
        :type create_default_axes: bool
        :return: None
        :rtype: None
        """
        self._heatmap_colorbar = None

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.fig_event.clear()

        self.event_outer_ax = None
        self.fig_event.set_layout_engine("constrained")
        self._clear_cache()

    @log(logger=logger)
    @register_action()
    @override
    def _reset_actions(self, axis_type: str = "2d") -> None:
        """
        Clears the figure and reinitializes axes. This will also add a flag to the tab action history
        if @register_action is being used to keep track of actions. Only actions applied after the most
        recent call to this function will be recreated if the related file is loaded.

        Also clears stored fit state for whichever analysis mode is currently active
        (self.fit_data for Individual, self.ensemble_fit_* for Ensemble), leaving the
        other mode's fit untouched. This means switching modes and running Update Plot,
        or clicking Reset, only affects the fit belonging to the mode you're currently in.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        :return: None
        :rtype: None
        """
        self.fig_hist.clear()
        self.ax_hist = self.fig_hist.add_subplot(1, 1, 1)

        self.fig_vm.clear()
        self.ax_vm = self.fig_vm.add_subplot(1, 1, 1)

        try:
            self.fig_hist.tight_layout(pad=0.5)
        except Exception:
            # tight_layout can fail on awkward axes geometry; the plot still
            # renders, just less tidily, so carry on but leave a trace.
            self.logger.debug("tight_layout failed for self.fig_hist", exc_info=True)
        self.canvas_hist.draw()
        try:
            self.fig_vm.tight_layout(pad=0.5)
        except Exception:
            # tight_layout can fail on awkward axes geometry; the plot still
            # renders, just less tidily, so carry on but leave a trace.
            self.logger.debug("tight_layout failed for self.fig_vm", exc_info=True)
        self.canvas_vm.draw()

        # Reset plot bookkeeping variables TBD
        self.hist_min = None
        self.hist_max = None
        self.hist_data = []
        self.hist_labels = []
        self.allowed_columns = []
        self.allowed_bins = None
        self.allowed_sizes = None
        self.plotted_datasets = (
            set()
        )  # tuple of things already plotted: (loader, experiment, channel, filter, subset_name), which can be None

        if self._analysis_mode == "individual":
            # Individual-mode fit data must not survive a Reset — a stale fit committed
            # after Reset would silently write outdated per-event values to the database.
            self.fit_data = None
        else:
            # Ensemble fit results must not survive a Reset either, for the same reason.
            self.ensemble_fit_params = None
            self.ensemble_fit_bins = None
            self.ensemble_fit_sizes = None
            self.ensemble_fit_prolate_summary = None
            self.ensemble_fit_oblate_summary = None

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
        :param norm: Whether to normalize the plotted y-values.
        :type norm: bool
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
        ax.legend(loc="best", fontsize="x-small")

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
        err_cols: Optional[Sequence[str]] = None,
    ) -> None:
        """
        update the plot area
        """
        # Decide which panel gets updated
        # Histogram plots -> left
        # V vs M plots / scatter / heatmap -> right
        if plot_type in ["Raw Histogram", "Filtered Histogram"]:
            ax = self.ax_hist
            canvas = self.canvas_hist
            self._plot_all_points_histogram(
                ax, data, cols, units, dataset_label=dataset_label, norm=False
            )
        elif plot_type == "Scatterplot":
            ax = self.ax_vm
            canvas = self.canvas_vm
            self._plot_scatterplot(
                ax, data, cols, units, logscales, dataset_label=dataset_label
            )
        elif plot_type == "Peak Scatterplot":
            ax = self.ax_hist
            canvas = self.canvas_hist
            self._plot_xyerr_scatterplot(
                ax,
                data,
                cols,
                units,
                logscales,
                dataset_label=dataset_label,
                err_cols=err_cols,
            )
        else:
            raise NotImplementedError(f"Plot type {plot_type} is not yet supported")

        try:
            canvas.figure.tight_layout(pad=0.5)
        except Exception:
            # tight_layout can fail on awkward axes geometry; the plot still
            # renders, just less tidily, so carry on but leave a trace.
            self.logger.debug("tight_layout failed for the plot canvas", exc_info=True)
        canvas.draw()
        self._commit_cache()

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
    def _plot_xyerr_scatterplot(
        self,
        ax: Axes,
        data: pd.DataFrame,
        cols: Sequence[str],
        units: Sequence[Optional[str]],
        logscales: Sequence[bool],
        dataset_label: str = "",
        err_cols: Optional[Sequence[str]] = None,
    ) -> None:
        """
        Create a scatterplot of two metadata columns with error bars.

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
        :param err_cols: Sequence containing two column names for x and y errors.
        :type err_cols: Optional[Sequence[str]]
        :raises ValueError: If `err_cols` is not a list of exactly two column names.
        """
        if err_cols is None or len(err_cols) != 2:
            raise ValueError(
                "_plot_xyerr_scatterplot() requires exactly two error columns to be specified in err_cols (e.g., [x_err, y_err])"
            )

        x_label, y_label = cols
        x_units, y_units = units
        logx, logy = logscales
        x_err_label, y_err_label = err_cols

        x = data[x_label].values
        y = data[y_label].values

        # Extract error arrays, allowing for None if one axis doesn't have errors
        x_err = data[x_err_label].values if x_err_label else None
        y_err = data[y_err_label].values if y_err_label else None

        x_label = format_axis_label(x_label, x_units)
        y_label = format_axis_label(y_label, y_units)

        if logx:
            x_label = f"log10({x_label})"
        if logy:
            y_label = f"log10({y_label})"

        xdata, ydata = self._logscale_and_filter_multiple_columns(
            x, y, log_flags=[logx, logy]
        )

        # Plot the scatter points
        ax.scatter(xdata, ydata, s=4, alpha=0.5, label=dataset_label)

        # Plot the error bars
        # fmt='none' draws only the error bars without adding new markers
        ax.errorbar(
            xdata,
            ydata,
            xerr=x_err,
            yerr=y_err,
            fmt="none",
            alpha=0.25,
            capsize=1,  # Adds little caps to the ends of the error bars
            zorder=0,  # Puts the error bars behind the scatter points
        )

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)

        self._update_cache((xdata, x_label), (ydata, y_label))
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
            self.proteincontrols.update_loaders(loaders)
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
        current = self.proteincontrols.db_loader_comboBox.currentText()
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
        :param bins: Number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning. Arrives as a single-element list from the controls and is rebound to a scalar (or None, to fall back to an automatic estimate) in the body, hence the loose annotation.
        :type bins: Any
        :param sizes: whether bins represents a number of bins or a bin size.
        :type sizes: bool
        :return: DataFrame with histogram values and corresponding current levels.
        :rtype: pd.DataFrame
        :raises ValueError: If `bins` is not a usable bin count/size specification.
        """
        # get global stats from the first event, don't forget to use this one later
        egen1, egen2 = itertools.tee(event_generator)

        min_current = float("inf")
        max_current = float("-inf")
        for event in egen1:

            if plot_type == "Raw Histogram":
                timeseries = event["raw_data"]
            elif plot_type == "Filtered Histogram":
                timeseries = event["filtered_data"]

            padding_before = int(event["padding_before"] * event["samplerate"] * 1e-6)
            padding_after = int(event["padding_after"] * event["samplerate"] * 1e-6)
            baseline = 0.5 * (
                np.median(timeseries[:padding_before])
                + np.median(timeseries[-padding_after:])
            )
            if baseline == 0:
                self.logger.warning(
                    f'Skipping event {event.get("event_id")} with zero baseline for histogram construction'
                )
                continue
            dI_I = (baseline - timeseries[padding_before:-padding_after]) / baseline

            min_curr = np.min(dI_I)
            max_curr = np.max(dI_I)
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
                    ) from e
        else:
            bins = 100

        bin_edges = np.linspace(self.hist_min, self.hist_max, bins + 1)
        hist = np.zeros(bins)
        count = 0
        for event in egen2:
            if plot_type == "Raw Histogram":
                timeseries = event["raw_data"]
            elif plot_type == "Filtered Histogram":
                timeseries = event["filtered_data"]
            padding_before = int(event["padding_before"] * event["samplerate"] * 1e-6)
            padding_after = int(event["padding_after"] * event["samplerate"] * 1e-6)
            baseline = 0.5 * (
                np.median(timeseries[:padding_before])
                + np.median(timeseries[-padding_after:])
            )
            if baseline == 0:
                self.logger.warning(
                    f'Skipping event {event.get("event_id")} with zero baseline for histogram construction'
                )
                continue
            dI_I = (baseline - timeseries[padding_before:-padding_after]) / baseline
            event_hist, _ = np.histogram(
                dI_I,
                bins=bin_edges,
            )
            hist += event_hist / len(dI_I)
            count += 1
        hist /= count
        bincenters = bin_edges[:-1] + np.diff(bin_edges) / 2.0
        return pd.DataFrame({"Normalized Current": bincenters, "Amplitude": hist})

    @log(logger=logger)
    def _construct_single_event_histogram(
        self,
        event: Dict[str, Any],
        plot_type: str,
        bins: Any = None,
        sizes: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Build a histogram of the current in a single event

        :param event: a dictionary of event metadata and the underlying timeseries
        :type event: Dict[str, Any]
        :param plot_type: Type of histogram to create (raw or filtered).
        :type plot_type: str
        :param bins: Number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning. Arrives as a single-element list from the controls and is rebound to a scalar (or None, to fall back to an automatic estimate) in the body, hence the loose annotation.
        :type bins: Any
        :param sizes: whether bins represents a number or a binsize
        :type sizes: bool
        :return: DataFrame with histogram values and corresponding current levels.
        :rtype: Optional[pd.DataFrame]
        :raises ValueError: If `bins` is not a usable bin count/size specification.
        """
        min_current = float("inf")
        max_current = float("-inf")

        if plot_type == "Raw Histogram":
            timeseries = event["raw_data"]
        elif plot_type == "Filtered Histogram":
            timeseries = event["filtered_data"]

        padding_before = int(event["padding_before"] * event["samplerate"] * 1e-6)
        padding_after = int(event["padding_after"] * event["samplerate"] * 1e-6)
        baseline = 0.5 * (
            np.median(timeseries[:padding_before])
            + np.median(timeseries[-padding_after:])
        )

        dI_I = (baseline - timeseries[padding_before:-padding_after]) / baseline

        if dI_I.size == 0:
            return None

        min_curr = np.min(dI_I)
        max_curr = np.max(dI_I)
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
                    ) from e
        else:
            # Freedman-Diaconis: bin width scales with the event's own IQR and
            # sample count, so shorter/longer events (typical for proteins,
            # where duration varies a lot) get independently sized bins instead
            # of a fixed 100 for every event regardless of length.
            iqr = np.percentile(dI_I, 75) - np.percentile(dI_I, 25)
            bin_width = 2 * iqr / np.cbrt(np.size(dI_I))

            if bin_width <= 0 or not np.isfinite(bin_width):
                # IQR collapses to 0 (near-constant signal) or the event is too
                # short/degenerate for FD to produce a sane width; fall back to
                # the previous fixed default rather than dividing by zero.
                bins = 100
            else:
                bins = int((self.hist_max - self.hist_min) / bin_width)
                bins = max(bins, 1)

        bin_edges = np.linspace(self.hist_min, self.hist_max, bins + 1)
        event_hist, _ = np.histogram(dI_I, bins=bin_edges, density=True)
        bincenters = bin_edges[:-1] + np.diff(bin_edges) / 2.0
        return pd.DataFrame({"Normalized Current": bincenters, "Amplitude": event_hist})

    @log(logger=logger)
    def set_baseline_duration(self, duration: Optional[float]) -> None:
        """
        A callback from a global_signal call that sets the baseline_duration variable for further processing.

        :param duration: total duration of baseline data in the scoped subset, or None if it could not be resolved.
        :type duration: Optional[float]
        """
        self.baseline_duration = duration

    @log(logger=logger)
    def set_event_data_generator(self, generator: Iterator[Dict[str, Any]]) -> None:
        """
        Set the event data generator for event-based plots.

        :param generator: A generator that yields event data.
        :type generator: Iterator[Dict[str, Any]]
        """
        self.event_data_generator = generator

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

        combo = self.proteincontrols.filter_comboBox
        loader = parameters.get("db_loader")

        if not loader:
            self.logger.warning("No loader found – filters loaded but not validated.")

        for name, filter_text in new_filters.items():
            if loader:
                # Raw filters bypass validation — suffix already baked in
                if name.endswith("_raw"):
                    self.subset_filters[name] = filter_text
                    combo.addItem(name)
                    combo.selectItem(name, select=True)
                else:
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
    def restore_subset_filters(self, filters: Dict[str, str]) -> None:
        """
        Restore subset filters captured in a saved session.

        Unlike :meth:`_load_filter`, this does not re-validate the filters against a
        database loader, since they were already valid when the session was saved.

        :param filters: Mapping of filter name to filter expression to restore.
        :type filters: Dict[str, str]
        """
        combo = self.proteincontrols.filter_comboBox
        for name, filter_text in filters.items():
            if name in self.subset_filters:
                self.logger.warning(
                    f"Filter '{name}' already exists; skipping restore of duplicate."
                )
                continue
            self.subset_filters[name] = filter_text
            combo.addItem(name)
            combo.selectItem(name, select=True)
        combo.refreshDisplayText()

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
            loader = parameters.get("db_loader")
            if loader:
                self.update_available_columns(loader)
                self.request_experiment_structure(loader)

        elif action_name == "select_experiment_and_channel":
            loader = parameters.get("db_loader")
            structure = self.available_experiment_and_channels_by_loader.get(loader, {})
            selection = self.selected_experiment_and_channels_by_loader.get(loader, {})
            self.show_selection_tree(structure, loader, selection)

        elif action_name == "shift_range_backward":
            self._shift_range_and_update_plot(parameters, direction="left")
        elif action_name == "plot_events":
            self._handle_plot_events(parameters)
        elif action_name == "plot_histogram":
            self._handle_plot_histogram(parameters)
        elif action_name == "shift_range_forward":
            self._shift_range_and_update_plot(parameters, direction="right")

        elif action_name == "update_plot":
            self._set_display_mode("distribution")
            if self._analysis_mode == "individual":
                parameters["plot_type"] = (
                    "Filtered Histogram"  # hard coded for now, may change later
                )
                self._update_distribution_individual(parameters)
            else:
                parameters["plot_type"] = "Filtered Histogram"
                self._update_distribution_ensemble(parameters)

        elif action_name == "add_filter":
            self._show_add_filter_dialog(parameters)

        elif action_name == "edit_filter":
            self._show_filter_info_dialog(
                self.proteincontrols.filter_comboBox, parameters
            )

        elif action_name == "delete_filter":
            self._delete_all_selected_filters()

        elif action_name == "save_filter":
            self._save_filter()

        elif action_name == "load_filter":
            self._load_filter(parameters)

        elif action_name == "set_mode_individual":
            self._analysis_mode = "individual"
            self.mode_stack.setCurrentWidget(self.individual_dist_page)

        elif action_name == "set_mode_ensemble":
            self._analysis_mode = "ensemble"
            self.mode_stack.setCurrentWidget(self.ensemble_dist_page)

        elif action_name == "commit_individual":
            loader = parameters.get("db_loader")
            try:
                self._commit_fits(loader)
            except AttributeError as e:
                self.add_text_to_display.emit(
                    "No individual fit available to commit. Run Update Plot in Individual mode first.",
                    self.__class__.__name__,
                )
                self.logger.warning(f"Commit Individual failed: {e}")

        elif action_name == "report_all":
            self._report_ensemble_fit()

        else:
            self._handle_other_actions(action_name, parameters)

    # -------------------------------------------------------------------------
    # Filter-aware event_id cache navigation
    # -------------------------------------------------------------------------

    @log(logger=logger)
    def relay_query_result(self, result: Optional[pd.DataFrame]) -> None:
        """
        A global signal callback that stores the result of a direct database query.
        Used by _rebuild_event_id_cache to receive the list of filtered event_ids.

        :param result: DataFrame returned by query_database_directly, or None if the query failed.
        :type result: Optional[pd.DataFrame]
        """
        self.relayed_query_result = result

    @log(logger=logger)
    def _build_where_clause(
        self,
        loader: str,
        sql_filter: str,
        exp: Optional[str],
        channel: Optional[int],
    ) -> str:
        """
        Build a WHERE clause string suitable for the event_id cache query,
        scoped to the current experiment and channel. event_id is only unique
        within an experiment/channel scope, not across the whole events table,
        so without this scoping filtered_event_ids mixes duplicate event_ids
        from every channel, causing navigation to jump to ids that don't exist
        in the active channel and inflating the reported total count.

        :param loader: Name of the database loader.
        :type loader: str
        :param sql_filter: SQL filter expression without the WHERE keyword, e.g. "duration > 1000".
        :type sql_filter: str
        :param exp: Experiment name, or None.
        :type exp: Optional[str]
        :param channel: Channel identifier, or None.
        :type channel: Optional[int]
        :return: Full WHERE clause string (including the WHERE keyword), or "" if no predicate applies.
        :rtype: str
        """
        filter_parts = []
        if sql_filter:
            filter_parts.append(sql_filter)

        if exp is not None:
            self.experiment_id = None
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "get_experiment_id_by_name",
                (exp,),
                "set_experiment_id",
                (),
            )
            if self.experiment_id is not None:
                filter_parts.append(f"experiment_id = {self.experiment_id}")
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
        Fetch all event_ids matching the current filter in one DB query and
        store them sorted in self.filtered_event_ids.

        Also updates current_sql_filter / current_experiment / current_channel
        so that staleness checks in _shift_range_and_update_plot and
        _handle_plot_events/_handle_plot_histogram can detect scope changes.

        Emits a display-panel message with the total count and first/last
        event_id (mirrors ProteinView._rebuild_event_id_cache behaviour).

        :param loader: Name of the database loader.
        :type loader: str
        :param where_clause: Full WHERE clause string (may be empty).
        :type where_clause: str
        :param sql_filter: Raw filter expression without WHERE (used for label and staleness tracking).
        :type sql_filter: str
        :param exp: Experiment name.
        :type exp: Optional[str]
        :param channel: Channel identifier.
        :type channel: Optional[int]
        :return: True if the cache was populated, False if no events were found.
        :rtype: bool
        """
        query = f"SELECT event_id FROM events {where_clause} ORDER BY event_id"
        self.relayed_query_result = None
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "query_database_directly",
            (query,),
            "relay_query_result",
            (),
        )
        result = getattr(self, "relayed_query_result", None)
        if result is None or result.empty or "event_id" not in result.columns:
            self.add_text_to_display.emit(
                "No filtered events found for the current scope.",
                self.__class__.__name__,
            )
            return False

        self.filtered_event_ids = result["event_id"].tolist()
        self.current_sql_filter = sql_filter
        self.current_experiment = exp
        self.current_channel = channel

        selected_filters = self.get_selected_filters()
        n = len(self.filtered_event_ids)
        first = self.filtered_event_ids[0]
        last = self.filtered_event_ids[-1]

        if not sql_filter:
            label = "All events"
        else:
            filter_name = next(iter(selected_filters.keys()), sql_filter)
            label = f'"{filter_name}" subset'

        self.add_text_to_display.emit(
            f"{label}: {n} total | first event_id: {first} | last event_id: {last}",
            self.__class__.__name__,
        )
        return True

    @log(logger=logger)
    def _shift_range_and_update_plot(self, parameters: dict, direction: str) -> None:
        """
        Navigate filtered event_ids by n_events steps in the given direction
        with wrap-around at both ends, then trigger a plot update.

        :param parameters: Action parameters from ProteinControls (must contain
                           'db_loader', 'event_id', 'n_events').
        :type parameters: dict
        :param direction: 'left' (backward) or 'right' (forward).
        :type direction: str
        """
        loader = parameters.get("db_loader")
        if not loader:
            return

        selected_filters = self.get_selected_filters()
        if not selected_filters:
            selected_filters = {"Full Dataset": ""}

        experiments_and_channels = self.selected_experiment_and_channels_by_loader.get(
            loader
        )
        if not experiments_and_channels:
            return

        sql_filter = next(iter(selected_filters.values()))
        exp = next(iter(experiments_and_channels.keys()))
        selected_channel = next(iter(experiments_and_channels.values()))[0]
        channel = int(selected_channel) if selected_channel is not None else None

        # Rebuild cache if the filter/scope has changed or the cache is empty
        if (
            not self.filtered_event_ids
            or sql_filter != self.current_sql_filter
            or exp != self.current_experiment
            or channel != self.current_channel
        ):
            where_clause = self._build_where_clause(loader, sql_filter, exp, channel)
            if not self._rebuild_event_id_cache(
                loader, where_clause, sql_filter, exp, channel
            ):
                return

        cache = self.filtered_event_ids
        event_id = parameters.get("event_id") or 0
        n_events = parameters.get("n_events") or 1

        # Find current position; bisect_left snaps to the first id >= event_id
        idx = bisect.bisect_left(cache, event_id)
        if idx >= len(cache):
            idx = 0

        if direction == "right":
            next_idx = idx + n_events
            if next_idx >= len(cache):
                next_idx = 0  # wrap to beginning
        else:
            next_idx = idx - n_events
            if next_idx < 0:
                next_idx = max(0, len(cache) - n_events)  # wrap to end

        new_event_id = cache[next_idx]
        self.proteincontrols.set_event_id_input(new_event_id)

        new_params = parameters.copy()
        new_params["event_id"] = new_event_id

        if self._last_event_action == "plot_histogram":
            self._handle_plot_histogram(new_params)
        else:
            self._handle_plot_events(new_params)

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
        self.plot_events_generator_updated = True

    # -------------------------------------------------------------------------
    # NOTE: This targeted-fetch-by-id pattern (_resolve_event_db_ids +
    # _fetch_event_data) is factored out here because ProteinView has two
    # callers that need it — _handle_plot_events and _handle_plot_histogram.
    # MetadataView's equivalent id-resolution/fetch logic is only used by
    # _handle_plot_events, so it's kept inline there rather than duplicating
    # this abstraction for a single call site. If another tab ever grows a
    # second consumer of "fetch these event_ids' full data" (e.g. a
    # histogram feature mirroring this one), port this pattern over rather
    # than reinventing it — see ProteinView._resolve_event_db_ids/
    # _fetch_event_data for the scoped-query approach both should use.
    # -------------------------------------------------------------------------

    @log(logger=logger)
    def _resolve_event_db_ids(
        self,
        loader: str,
        event_ids: Sequence[int],
        exp: Optional[str],
        channel: Optional[int],
    ) -> Optional[pd.DataFrame]:
        """
        Resolve a list of event_id values, scoped to a specific experiment and
        channel, to their corresponding database primary keys (id) via a single
        direct query. event_id is only unique within an experiment/channel
        scope, not across the whole events table, so this scoping is required
        to avoid resolving to the wrong row when two channels share an event_id.

        :param loader: Name of the database loader.
        :type loader: str
        :param event_ids: List of event_id values to resolve.
        :type event_ids: Sequence[int]
        :param exp: Experiment name, or None.
        :type exp: Optional[str]
        :param channel: Channel identifier, or None.
        :type channel: Optional[int]
        :return: DataFrame with columns id, event_id for the matching rows, or None on failure.
        :rtype: Optional[pd.DataFrame]
        """
        if not event_ids:
            return None

        id_tuple = f"({','.join(str(eid) for eid in event_ids)})"
        where_parts = [f"event_id IN {id_tuple}"]

        if exp is not None:
            self.experiment_id = None
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "get_experiment_id_by_name",
                (exp,),
                "set_experiment_id",
                (),
            )
            if self.experiment_id is not None:
                where_parts.append(f"experiment_id = {self.experiment_id}")

        if channel is not None:
            where_parts.append(f"channel_id = {channel}")

        query = f"SELECT id, event_id FROM events WHERE {' AND '.join(where_parts)}"
        self.relayed_query_result = None
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "query_database_directly",
            (query,),
            "relay_query_result",
            (),
        )
        result = getattr(self, "relayed_query_result", None)
        if result is None or result.empty or "id" not in result.columns:
            return None
        return result

    @log(logger=logger)
    def _fetch_event_data(
        self, parameters: Dict[str, Any], action_label: str = "events"
    ) -> list[dict]:
        """
        Shared validation and targeted data fetching for event-based plots.
        Resolves the requested event_index list to database ids via a single
        query scoped to the current experiment/channel, then fetches exactly
        those rows. Always fetches fresh rather than caching event blobs in
        memory — event_id is only unique within an experiment/channel scope,
        and a per-event_id blob cache is an easy invariant to accidentally
        violate later; the targeted DB query is already O(events requested)
        rather than O(distance into the dataset), so the extra memoization
        isn't worth the correctness risk.

        :param parameters: Dictionary containing db_loader, filter, channels, and event indices.
        :type parameters: Dict[str, Any]
        :param action_label: Label used in error messages to identify the plot type.
        :type action_label: str
        :return: List of fetched event dictionaries, in the order requested, or empty list on failure.
        :rtype: list[dict]
        """
        selected_filters = self.get_selected_filters()
        loader_name = parameters["db_loader"]
        experiments_and_channels = self.selected_experiment_and_channels_by_loader.get(
            loader_name
        )

        if experiments_and_channels is None:
            self.add_text_to_display.emit(
                f"No experiments or channels are in scope, select at least one to plot {action_label}",
                self.__class__.__name__,
            )
            return []

        if selected_filters is not None and len(selected_filters) > 1:
            self.add_text_to_display.emit(
                "Unable to plot more than one subset at a time, select only one filter to apply",
                self.__class__.__name__,
            )
            return []

        if (
            self.selected_experiment_and_channels_by_loader[loader_name] is None
            or len(self.selected_experiment_and_channels_by_loader[loader_name]) == 0
        ):
            self.add_text_to_display.emit(
                f"No experiments or channels are in scope, select at least one to plot {action_label}",
                self.__class__.__name__,
            )
            return []

        if len(experiments_and_channels) > 1:
            self.add_text_to_display.emit(
                f"Only a single experiment can be used for plotting {action_label}",
                self.__class__.__name__,
            )
            return []

        for channels in experiments_and_channels.values():
            if len(channels) > 1:
                self.add_text_to_display.emit(
                    f"Only a single channel can be used for plotting {action_label}",
                    self.__class__.__name__,
                )
                return []

        if selected_filters is None or selected_filters == {}:
            selected_filters = {"Full Dataset": ""}

        event_index = parameters["event_index"]
        exp_and_ch = self.selected_experiment_and_channels_by_loader[loader_name]
        exp = next(iter(exp_and_ch.keys()))
        selected_channel = next(iter(exp_and_ch.values()))[0]
        channel = int(selected_channel) if selected_channel is not None else None

        id_result = self._resolve_event_db_ids(loader_name, event_index, exp, channel)
        if id_result is None or id_result.empty:
            self.add_text_to_display.emit(
                f"No data available for the requested {action_label}",
                self.__class__.__name__,
            )
            return []

        db_ids = id_result["id"].tolist()
        id_tuple = f"({','.join(str(i) for i in db_ids)})"
        event_db_id_filter = f"e.id IN {id_tuple}"

        self.plot_events_generator_updated = False
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader_name,
            "load_event_data",
            (event_db_id_filter, exp_and_ch),
            "relay_event_plot_data_generator",
            (),
        )

        generator = getattr(self, "plot_events_generator", None)
        if generator is None:
            self.add_text_to_display.emit(
                f"No data available for the requested {action_label}",
                self.__class__.__name__,
            )
            return []

        data_list = list(generator)

        # restore the caller's requested order
        order = {eid: i for i, eid in enumerate(event_index)}
        data_list.sort(key=lambda e: order.get(e["event_id"], len(order)))

        return data_list

    @log(logger=logger)
    def _build_load_event_data_args(
        self,
        sql_filter: str,
        subset_name: str,
        exp: Optional[str],
        channel: str,
        exp_and_ch_arg: dict,
        loader: str,
    ) -> tuple:
        """
        Build the (filter_or_query, exp_and_ch_or_None) args tuple for load_event_data,
        handling raw filter scoping automatically.

        :param sql_filter: SQL filter string or complete raw query.
        :type sql_filter: str
        :param subset_name: Name of the subset filter, used to detect _raw suffix.
        :type subset_name: str
        :param exp: Experiment name, or None.
        :type exp: Optional[str]
        :param channel: Channel identifier.
        :type channel: str
        :param exp_and_ch_arg: Experiment/channel dict for assisted filters.
        :type exp_and_ch_arg: dict
        :param loader: Name of the database loader.
        :type loader: str
        :return: Tuple of (query_or_filter, exp_and_ch_or_None) for load_event_data.
        :rtype: tuple
        """
        if subset_name.endswith("_raw"):
            self.experiment_id = None
            self.channel_db_id = None
            if exp is not None:
                self.global_signal.emit(
                    "MetaDatabaseLoader",
                    loader,
                    "get_experiment_id_by_name",
                    (exp,),
                    "set_experiment_id",
                    (),
                )
                self.global_signal.emit(
                    "MetaDatabaseLoader",
                    loader,
                    "get_channel_db_id",
                    (exp, int(channel)),
                    "set_channel_db_id",
                    (),
                )
            scoped_query = sql_filter.strip().rstrip(";")
            if (
                exp is not None
                and self.experiment_id is not None
                and self.channel_db_id is not None
            ):
                scope = f"experiment_id = {self.experiment_id} AND channel_db_id = {self.channel_db_id}"
                if "WHERE" in scoped_query.upper():
                    scoped_query = f"{scoped_query} AND {scope}"
                else:
                    scoped_query = f"{scoped_query} WHERE {scope}"
            return (scoped_query, None)
        else:
            return (sql_filter, exp_and_ch_arg)

    @log(logger=logger)
    def _handle_plot_events(self, parameters: dict) -> None:
        """
        Handle loading and plotting of selected events based on provided parameters.

        Resolves event_id + n_events into a concrete list of event_ids via the
        filtered_event_ids cache and bisect, then delegates to _fetch_event_data,
        which resolves those event_ids to database ids and fetches them directly.

        :param parameters: Dictionary containing db_loader, filter, channels,
                           event_id (int), and n_events (int).
        :type parameters: dict
        """
        self._last_event_action = "plot_events"

        loader = parameters.get("db_loader")
        if not loader:
            self.add_text_to_display.emit(
                "No experiments or channels are in scope, select at least one to plot events",
                self.__class__.__name__,
            )
            return

        selected_filters = self.get_selected_filters()
        if not selected_filters:
            selected_filters = {"Full Dataset": ""}

        experiments_and_channels = self.selected_experiment_and_channels_by_loader.get(
            loader
        )
        if not experiments_and_channels or len(experiments_and_channels) == 0:
            self.add_text_to_display.emit(
                "No experiments or channels are in scope, select at least one to plot events",
                self.__class__.__name__,
            )
            return

        sql_filter = next(iter(selected_filters.values()))
        exp = next(iter(experiments_and_channels.keys()))
        selected_channel = next(iter(experiments_and_channels.values()))[0]
        channel = int(selected_channel) if selected_channel is not None else None

        # Rebuild the event_id cache if the filter or scope has changed
        if (
            not self.filtered_event_ids
            or sql_filter != self.current_sql_filter
            or exp != self.current_experiment
            or channel != self.current_channel
        ):
            where_clause = self._build_where_clause(loader, sql_filter, exp, channel)
            if not self._rebuild_event_id_cache(
                loader, where_clause, sql_filter, exp, channel
            ):
                return

        cache = self.filtered_event_ids
        event_id = parameters.get("event_id") or 0
        n_events = parameters.get("n_events") or 1

        # Snap to nearest event_id at or after the requested id; wrap if past end
        idx = bisect.bisect_left(cache, event_id)
        if idx >= len(cache):
            idx = 0

        snapped_event_id = cache[idx]
        self.proteincontrols.set_event_id_input(snapped_event_id)

        # Resolve n_events consecutive ids from the cache starting at idx
        event_index = [cache[i] for i in range(idx, min(idx + n_events, len(cache)))]

        # Pass the resolved list into _fetch_event_data via the standard key
        fetch_params = parameters.copy()
        fetch_params["event_index"] = event_index

        data_list = self._fetch_event_data(fetch_params, action_label="events")

        if data_list:
            use_raw = parameters.get("raw", False)
            self._update_event_plot(data_list, use_raw=use_raw)
        else:
            self.add_text_to_display.emit(
                f"No data available for event_id {snapped_event_id}",
                self.__class__.__name__,
            )

    @log(logger=logger)
    def _handle_plot_histogram(self, parameters: dict) -> None:
        """
        Handle loading and plotting of the ΔI/I histogram for selected events,
        each in its own subplot on the event canvas.

        Resolves event_id + n_events into a concrete list of event_ids via the
        filtered_event_ids cache and bisect, then delegates to _fetch_event_data,
        which resolves those event_ids to database ids and fetches them directly.

        :param parameters: Dictionary containing db_loader, filter, channels,
                           event_id (int), n_events (int), bins, and sizes.
        :type parameters: dict
        """

        self._last_event_action = "plot_histogram"

        # Reset bin range so each Plot Histogram click is self-contained
        # Without this, hist_min/hist_max accumulate across navigation sessions,
        # causing bin edges to widen and histogram shape/fit to change on return visits
        self.hist_min = None
        self.hist_max = None

        loader = parameters.get("db_loader")
        if not loader:
            self.add_text_to_display.emit(
                "No experiments or channels are in scope, select at least one to plot histograms",
                self.__class__.__name__,
            )
            return

        bins = parameters.get("bins")
        sizes = parameters.get("sizes", False)
        plot_type = "Filtered Histogram"

        selected_filters = self.get_selected_filters()
        if not selected_filters:
            selected_filters = {"Full Dataset": ""}

        experiments_and_channels = self.selected_experiment_and_channels_by_loader.get(
            loader
        )
        if not experiments_and_channels or len(experiments_and_channels) == 0:
            self.add_text_to_display.emit(
                "No experiments or channels are in scope, select at least one to plot histograms",
                self.__class__.__name__,
            )
            return

        sql_filter = next(iter(selected_filters.values()))
        exp = next(iter(experiments_and_channels.keys()))
        selected_channel = next(iter(experiments_and_channels.values()))[0]
        channel = int(selected_channel) if selected_channel is not None else None

        # Rebuild the event_id cache if the filter or scope has changed
        if (
            not self.filtered_event_ids
            or sql_filter != self.current_sql_filter
            or exp != self.current_experiment
            or channel != self.current_channel
        ):
            where_clause = self._build_where_clause(loader, sql_filter, exp, channel)
            if not self._rebuild_event_id_cache(
                loader, where_clause, sql_filter, exp, channel
            ):
                return

        cache = self.filtered_event_ids
        event_id = parameters.get("event_id") or 0
        n_events = parameters.get("n_events") or 1

        # Snap to nearest event_id at or after the requested id; wrap if past end
        idx = bisect.bisect_left(cache, event_id)
        if idx >= len(cache):
            idx = 0

        snapped_event_id = cache[idx]
        self.proteincontrols.set_event_id_input(snapped_event_id)

        # Resolve n_events consecutive ids from the cache starting at idx
        event_index = [cache[i] for i in range(idx, min(idx + n_events, len(cache)))]

        # Pass the resolved list into _fetch_event_data via the standard key
        fetch_params = parameters.copy()
        fetch_params["event_index"] = event_index

        data_list = self._fetch_event_data(fetch_params, action_label="histograms")

        if data_list:
            self._update_event_histogram(
                data_list, bins=bins, sizes=sizes, plot_type=plot_type
            )
        else:
            self.add_text_to_display.emit(
                f"No data available for event_id {snapped_event_id}",
                self.__class__.__name__,
            )

    @log(logger=logger)
    def _update_event_plot(
        self, event_data: Sequence[Dict[str, Any]], use_raw: bool = False
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
        :param use_raw: Whether to overlay the unfiltered raw signal alongside filtered/fit traces.
        :type use_raw: bool
        :return: None
        :rtype: None
        """
        self._set_display_mode("event")
        self._clear_figure_state(create_default_axes=False)

        num_events = len(event_data)
        num_rows, num_cols = self._factors(num_events)
        j = 0
        for i, event in enumerate(event_data):
            ax = self.fig_event.add_subplot(num_rows, num_cols, j + 1)
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

        self.fig_event.set_layout_engine("constrained")
        self.canvas_event.draw()
        self._commit_cache()

    @log(logger=logger)
    def _update_event_histogram(
        self,
        event_data: Sequence[Dict[str, Any]],
        bins: Any = None,
        sizes: bool = False,
        plot_type: str = "Filtered Histogram",
    ) -> None:
        """
        Update the event canvas with per-event ΔI/I histograms, one subplot per event.

        :param event_data: List of event dictionaries, each containing data and metadata for one event.
        :type event_data: Sequence[Dict[str, Any]]
        :param bins: Number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning. Arrives as a single-element list from the controls and is rebound to a scalar (or None, to fall back to an automatic estimate) in the body, hence the loose annotation.
        :type bins: Any
        :param sizes: Whether bins represent bin sizes.
        :type sizes: bool
        :param plot_type: Type of histogram to construct.
        :type plot_type: str
        :raises ValueError: If the double-Gaussian fit fails for an event; caught internally
            and skipped, so it never propagates to the caller.
        """
        self._set_display_mode("event")
        self._clear_figure_state(create_default_axes=False)
        num_events = len(event_data)
        ##herehere
        num_rows, num_cols = self._factors(num_events)

        x_label = format_axis_label("Normalized Current", "pA")
        y_label = format_axis_label("Amplitude", "")

        for j, event in enumerate(event_data):
            ax = self.fig_event.add_subplot(num_rows, num_cols, j + 1)
            label = f'Exp {event["experiment_id"]}/Ch {event["channel_id"]}/Event {event["event_id"]}'
            ax.set_title(label)

            # Reset per-event so bin edges are determined solely by this event's
            # current range, not influenced by other events in the same plot call.
            self.hist_min = None
            self.hist_max = None

            try:
                plot_data = self._construct_single_event_histogram(
                    event, plot_type, bins=bins, sizes=sizes
                )
            except ValueError as e:
                self.logger.info(
                    f'Unable to construct histogram for event {event["event_id"]}: {e}'
                )
                continue
            if plot_data is None:
                continue

            try:  # try to fit a histogram, ignore if it fails. This code should be split out into a function since it is duplicated.
                popt = self._fit_and_sanity_check_double_gaussian(
                    plot_data["Normalized Current"].values,
                    plot_data["Amplitude"].values,
                )
                if popt is None:
                    raise ValueError("Unable to fit double gaussian")

                amp1, mean1, std1, amp2, mean2, std2 = popt

                ax.plot(
                    plot_data["Normalized Current"].values,
                    self._double_gaussian(
                        plot_data["Normalized Current"].values,
                        amp1,
                        mean1,
                        std1,
                        amp2,
                        mean2,
                        std2,
                    ),
                    color="orange",
                    zorder=2,
                )
                self._update_cache(
                    (plot_data["Normalized Current"].values, label + " " + x_label),
                    (
                        self._double_gaussian(
                            plot_data["Normalized Current"].values,
                            amp1,
                            mean1,
                            std1,
                            amp2,
                            mean2,
                            std2,
                        ),
                        label + " " + y_label,
                    ),
                )

            except (ValueError, RuntimeError):
                pass

            ax.plot(
                plot_data["Normalized Current"].values,
                plot_data["Amplitude"].values,
                color="blue",
                zorder=1,
            )

            if j % num_cols == 0:
                ax.set_ylabel(y_label)
            labelnum = (num_rows - 1) * num_cols
            if num_events % num_cols > 0:
                labelnum -= num_cols - num_events % num_cols
            if j >= labelnum:
                ax.set_xlabel(x_label)

            self._update_cache(
                (plot_data["Normalized Current"].values, label + " " + x_label),
                (plot_data["Amplitude"].values, label + " " + y_label),
            )

        self.fig_event.set_layout_engine("constrained")
        self.canvas_event.draw()
        self._commit_cache()

    @log(logger=logger)
    def _update_distribution_individual(self, parameters: Dict[str, Any]) -> None:
        """
        Compute and plot the ΔI/I histogram and V/M scatterplot for a single
        selected event in Individual analysis mode.

        :param parameters: Dictionary of plotting parameters collected from the controls.
        :type parameters: Dict[str, Any]
        """
        self._reset_actions()
        self._clear_cache()
        self._show_sql_in_display = False
        self._show_event_sql_in_display = False

        selected_filters = self.get_selected_filters()
        loader = parameters["db_loader"]
        plot_type = parameters["plot_type"]
        d = float(parameters["pore_diameter"])
        L = float(parameters["pore_length"])

        # Default N to 100 if missing
        N = int(parameters.get("n_values") or 100)
        bins = parameters.get("bins")
        sizes = parameters.get("sizes", False)

        experiments_and_channels: Optional[
            Union[Dict[str, List[str]], Dict[Any, Any]]
        ] = self.selected_experiment_and_channels_by_loader.get(loader)

        self.plot_initialized = True

        if experiments_and_channels is None or len(experiments_and_channels) == 0:
            experiments_and_channels = {None: [None]}

        if selected_filters is None or selected_filters == {}:
            selected_filters = {"Full Dataset": ""}

        if len(experiments_and_channels) > 1:
            self.logger.warning(f"Only a single experiment can be used for {plot_type}")
            return

        for channels in experiments_and_channels.values():
            if len(channels) > 1:
                self.logger.warning(
                    "Only a single channel at a time can be used for protein ensemble analysis"
                )
                return

        if len(selected_filters) > 1:
            self.add_text_to_display.emit(
                "Only a single subset can be used for protein analysis",
                self.__class__.__name__,
            )
            return

        for exp, channels in experiments_and_channels.items():
            for channel in channels:
                exp_and_ch_arg = {exp: [channel]}

                for subset_name, sql_filter in selected_filters.items():
                    self.global_signal.emit(
                        "MetaDatabaseLoader",
                        loader,
                        "construct_event_data_query",
                        (sql_filter, exp_and_ch_arg),
                        "relay_event_query",
                        (),
                    )

                    if self.event_query == "":
                        return

                    load_event_data_args = self._build_load_event_data_args(
                        sql_filter, subset_name, exp, channel, exp_and_ch_arg, loader
                    )
                    self.global_signal.emit(
                        "MetaDatabaseLoader",
                        loader,
                        "load_event_data",
                        load_event_data_args,
                        "relay_event_data_generator",
                        (),
                    )

                    if plot_type not in ["Raw Histogram", "Filtered Histogram"]:
                        self.logger.warning(f"Invalid plot type: {plot_type}")
                        return

                    if self.event_data_generator is None:
                        self.logger.warning(
                            "No events in dataset or unable to create event generator",
                        )
                        self.add_text_to_display.emit(
                            "No events in dataset or unable to create event generator",
                            self.__class__.__name__,
                        )
                        return

                    processed = 0
                    prolate_solutions: List[Any] = []
                    oblate_solutions: List[Any] = []
                    averaged_event_data: List[Dict[str, Any]] = []

                    for event in self.event_data_generator:
                        processed += 1
                        try:
                            plot_data = self._construct_single_event_histogram(
                                event,
                                plot_type,
                                bins=bins,
                                sizes=sizes,
                            )
                        except ValueError as e:
                            self.logger.info(
                                f'Unable to construct histogram for event {event["event_id"]}: {e}'
                            )
                            continue
                        if plot_data is None:
                            continue

                        popt = self._fit_and_sanity_check_double_gaussian(
                            plot_data["Normalized Current"].values,
                            plot_data["Amplitude"].values,
                        )

                        if popt is None:
                            continue

                        amp1, mean1, std1, amp2, mean2, std2 = popt

                        if mean1 > mean2:
                            mean_max, std_max = mean1, np.abs(std1)
                            mean_min, std_min = mean2, np.abs(std2)
                        else:
                            mean_max, std_max = mean2, np.abs(std2)
                            mean_min, std_min = mean1, np.abs(std1)

                        # --- OPTIMIZED GENERATIVE SAMPLING ---
                        # Call the Monte Carlo generators directly for this specific event
                        prolate_V, prolate_m = self._generate_vm_ensemble(
                            N, mean_max, std_max, mean_min, std_min, d, L, prolate=True
                        )

                        prolate_b = (3 * prolate_V / (4 * np.pi * prolate_m)) ** (1 / 3)
                        prolate_a = prolate_b * prolate_m

                        # Pack the returned arrays into tuples and extend the master list
                        prolate_solutions.extend(
                            zip(prolate_V, prolate_m, prolate_a, prolate_b)
                        )

                        oblate_V, oblate_m = self._generate_vm_ensemble(
                            N, mean_max, std_max, mean_min, std_min, d, L, prolate=False
                        )
                        oblate_b = (3 * oblate_V / (4 * np.pi * oblate_m)) ** (1 / 3)
                        oblate_a = oblate_b * oblate_m
                        # Pack the returned arrays into tuples and extend the master list
                        oblate_solutions.extend(
                            zip(oblate_V, oblate_m, oblate_a, oblate_b)
                        )

                        averaged_event_data.append(
                            {
                                "id": event["id"],
                                "prolate_volume": (
                                    np.median(prolate_V)
                                    if len(prolate_V) > 0
                                    else np.nan
                                ),
                                "prolate_shape_factor": (
                                    np.median(prolate_m)
                                    if len(prolate_m) > 0
                                    else np.nan
                                ),
                                "prolate_major_axis": (
                                    np.median(prolate_a)
                                    if len(prolate_a) > 0
                                    else np.nan
                                ),
                                "prolate_minor_axis": (
                                    np.median(prolate_b)
                                    if len(prolate_b) > 0
                                    else np.nan
                                ),
                                "oblate_volume": (
                                    np.median(oblate_V) if len(oblate_V) > 0 else np.nan
                                ),
                                "oblate_shape_factor": (
                                    np.median(oblate_m) if len(oblate_m) > 0 else np.nan
                                ),
                                "oblate_major_axis": (
                                    np.median(oblate_a) if len(oblate_a) > 0 else np.nan
                                ),
                                "oblate_minor_axis": (
                                    np.median(oblate_b) if len(oblate_b) > 0 else np.nan
                                ),
                                "min_fractional_blockage": mean_min,
                                "min_fractional_blockage_std": std_min,
                                "max_fractional_blockage": mean_max,
                                "max_fractional_blockage_std": std_max,
                            }
                        )

            # --- Create the Pandas DataFrames ---
            df_prolate = pd.DataFrame(prolate_solutions, columns=["V", "m", "a", "b"])
            df_oblate = pd.DataFrame(oblate_solutions, columns=["V", "m", "a", "b"])

            self.fit_data = pd.DataFrame(averaged_event_data)

            if not df_prolate.empty:
                self.update_plot(
                    "Scatterplot",
                    df_prolate,
                    ["V", "m"],
                    ["nm$^{3}$", None],
                    logscales=[False, False],
                    dataset_label="Prolate Solutions",
                )
            if not df_oblate.empty:
                self.update_plot(
                    "Scatterplot",
                    df_oblate,
                    ["V", "m"],
                    ["nm$^{3}$", None],
                    logscales=[False, False],
                    dataset_label="Oblate Solutions",
                )
            if not self.fit_data.empty:
                self.update_plot(
                    "Peak Scatterplot",
                    self.fit_data,
                    ["min_fractional_blockage", "max_fractional_blockage"],
                    ["arb. units", "arb. units"],
                    logscales=[False, False],
                    dataset_label="Event Peak Fit Parameters",
                    err_cols=[
                        "min_fractional_blockage_std",
                        "max_fractional_blockage_std",
                    ],
                )

    @log(logger=logger)
    def _double_gaussian(
        self,
        x: npt.NDArray[np.float64],
        amp1: float,
        mean1: float,
        std1: float,
        amp2: float,
        mean2: float,
        std2: float,
    ) -> npt.NDArray[np.float64]:
        """
        return the value of a double gaussian with the specified paramters

        :param x: array of x values at which to calculate double gaussian
        :type x: npt.NDArray[np.float64]
        :param amp1: amplitude of the first gaussian
        :type amp1: float
        :param mean1: mean of the first gaussian
        :type mean1: float
        :param std1: standard deviation of the first gaussian
        :type std1: float
        :param amp2: amplitude of the second gaussian
        :type amp2: float
        :param mean2: mean of the second gaussian
        :type mean2: float
        :param std2: standard deviation of the second gaussian
        :type std2: float
        :return: array of gaussian values at the given x positions
        :rtype: npt.NDArray[np.float64]
        """
        g1 = amp1 * np.exp(-((x - mean1) ** 2) / (2 * std1**2))
        g2 = amp2 * np.exp(-((x - mean2) ** 2) / (2 * std2**2))
        return g1 + g2

    @log(logger=logger)
    def _fit_double_gaussian(
        self, bins: npt.NDArray[np.float64], amplitude: npt.NDArray[np.float64]
    ) -> tuple:
        """
        Attempt to fit a double gaussian to data or return None on failure.

        :param bins: numpy array of bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: numpy array of amplitude in bins
        :type amplitude: npt.NDArray[np.float64]
        :return: Tuple of (best-fit parameters (amplitude, mean, std, amplitude_2,
                mean_2, std_2), parameter covariance matrix), or (None, None) if
                fitting fails.
        :rtype: tuple
        :raises ValueError: If curve fitting fails or peaks/split points cannot be
            determined; caught internally by nested fallback logic, so it never
            propagates to the caller.
        """
        try:
            min_prominence = np.max(amplitude) * 0.05
            peaks, properties = find_peaks(amplitude, prominence=min_prominence)

            if len(peaks) < 2:
                raise ValueError("Not enough peaks for initial guess")

            prominences = properties["prominences"]

            largest_prominence_indices = np.argsort(prominences)[-2:][::-1]
            top_two_peaks = peaks[largest_prominence_indices]

            widths, _, _, _ = peak_widths(amplitude, top_two_peaks, rel_height=0.5)

            bin_width = bins[1] - bins[0]
            fwhm_guesses = widths * bin_width

            std_guesses = fwhm_guesses / 2.355

            p0 = (
                amplitude[top_two_peaks[0]],
                bins[top_two_peaks[0]],
                std_guesses[0],
                amplitude[top_two_peaks[1]],
                bins[top_two_peaks[1]],
                std_guesses[1],
            )
            min_mean = np.min(bins)
            max_mean = np.max(bins)
            min_amp = 0
            max_amp = np.max(amplitude)
            min_std = 0
            max_std = np.abs(bins[-1] - bins[1])

            popt, pcov = curve_fit(
                self._double_gaussian,
                bins,
                amplitude,
                p0=p0,
                bounds=(
                    [min_amp, min_mean, min_std, min_amp, min_mean, min_std],
                    [max_amp, max_mean, max_std, max_amp, max_mean, max_std],
                ),
            )
            return popt, pcov
        except (RuntimeError, ValueError):
            try:
                n = len(amplitude)
                amax = np.max(amplitude)
                left_start = 0
                while amplitude[left_start] < 0.05 * amax and left_start < n:
                    left_start += 1
                right_start = n - 1
                while amplitude[right_start] < 0.05 * amax and right_start > 0:
                    right_start -= 1

                if left_start >= right_start:
                    raise ValueError(
                        "Cannot determine where to split the histogram for initial guess"
                    )

                left = amplitude[left_start : (left_start + right_start) // 2]
                right = amplitude[(left_start + right_start) // 2 : right_start]

                leftmax = np.max(left)
                leftargmax = np.argmax(left)

                rightmax = np.max(right)
                rightargmax = np.argmax(right)

                left_half_max = leftmax / 2.0
                idx_left = leftargmax
                while idx_left > 0 and left[idx_left] > left_half_max:
                    idx_left -= 1

                left_dist = abs(
                    bins[left_start + idx_left] - bins[left_start + leftargmax]
                )
                left_std_guess = left_dist / 1.177

                right_half_max = rightmax / 2.0
                idx_right = rightargmax
                while idx_right > 0 and right[idx_right] > right_half_max:
                    idx_right -= 1

                right_dist = abs(
                    bins[(left_start + right_start) // 2 + idx_right]
                    - bins[(left_start + right_start) // 2 + rightargmax]
                )
                right_std_guess = right_dist / 1.177

                p0 = (
                    leftmax,
                    bins[left_start + leftargmax],
                    left_std_guess,
                    rightmax,
                    bins[(left_start + right_start) // 2 + rightargmax],
                    right_std_guess,
                )
                min_mean = np.min(bins)
                max_mean = np.max(bins)
                min_amp = 0
                max_amp = np.max(amplitude)
                min_std = 0
                max_std = np.abs(bins[-1] - bins[1])

                popt, pcov = curve_fit(
                    self._double_gaussian,
                    bins,
                    amplitude,
                    p0=p0,
                    bounds=(
                        [min_amp, min_mean, min_std, min_amp, min_mean, min_std],
                        [max_amp, max_mean, max_std, max_amp, max_mean, max_std],
                    ),
                )
                return popt, pcov
            except (RuntimeError, ValueError):
                return None, None

    @log(logger=logger)
    def _fit_and_sanity_check_double_gaussian(
        self, bins: npt.NDArray[np.float64], amplitude: npt.NDArray[np.float64]
    ) -> Optional[npt.NDArray[np.float64]]:
        """
        Attempt to fit a double gaussian to data or None on failure.

        :param bins: numpy array of bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: numpy array of amplitude in bins
        :type amplitude: npt.NDArray[np.float64]
        :return: fit parameters for a double gaussian (amplitude, mean, std, amplitude_2, mean_2, std_2)
        :rtype: Optional[npt.NDArray[np.float64]]
        """
        popt, pcov = self._fit_double_gaussian(
            bins,
            amplitude,
        )

        if (
            popt is None
            or pcov is None
            or np.any(np.isinf(pcov))
            or np.any(np.isnan(pcov))
        ):
            return None

        perr = np.sqrt(np.diag(pcov))
        if np.any(perr > np.abs(popt) * 10):
            return None

        mu1_idx, mu2_idx = 1, 4
        mu1, mu2 = popt[mu1_idx], popt[mu2_idx]
        var_mu1, var_mu2 = (
            pcov[mu1_idx, mu1_idx],
            pcov[mu2_idx, mu2_idx],
        )
        cov_mu1_mu2 = pcov[mu1_idx, mu2_idx]
        variance_diff = var_mu1 + var_mu2 - 2 * cov_mu1_mu2

        if variance_diff <= 0:
            return None

        se_diff = np.sqrt(variance_diff)
        t_stat = abs(mu1 - mu2) / se_diff
        N_points = len(bins)
        df = N_points - len(popt)
        p_value = 2 * t.sf(t_stat, df)

        if p_value > 0.05:
            return None

        A1, A2 = popt[0], popt[3]
        abs_A1, abs_A2 = abs(A1), abs(A2)
        if max(abs_A1, abs_A2) == 0:
            return None

        if min(abs_A1, abs_A2) / max(abs_A1, abs_A2) < 0.05:
            return None

        return popt

    @log(logger=logger)
    @register_action()
    def _update_distribution_ensemble(self, parameters: Dict[str, Any]) -> None:
        """
        Compute and plot the ΔI/I histogram and V/M scatterplot aggregated across
        all events in Ensemble analysis mode.

        :param parameters: Dictionary of plotting parameters collected from the controls.
        :type parameters: Dict[str, Any]
        """
        self._reset_actions()
        self._clear_cache()
        self._show_sql_in_display = False
        self._show_event_sql_in_display = False

        selected_filters = self.get_selected_filters()
        loader = parameters["db_loader"]
        plot_type = parameters["plot_type"]
        d = float(parameters["pore_diameter"])
        L = float(parameters["pore_length"])
        N = int(parameters.get("n_values") or 100)

        experiments_and_channels: Optional[
            Union[Dict[str, List[str]], Dict[Any, Any]]
        ] = self.selected_experiment_and_channels_by_loader.get(loader)

        self.plot_initialized = True

        if experiments_and_channels is None or len(experiments_and_channels) == 0:
            experiments_and_channels = {None: [None]}

        if selected_filters is None or selected_filters == {}:
            selected_filters = {"Full Dataset": ""}

        if len(experiments_and_channels) > 1:
            self.logger.warning(f"Only a single experiment can be used for {plot_type}")
            return

        for channels in experiments_and_channels.values():
            if len(channels) > 1:
                self.logger.warning(
                    "Only a single channel at a time can be used for protein ensemble analysis"
                )
                return

        if len(selected_filters) > 1:
            self.add_text_to_display.emit(
                f"Only a single subset can be used for {plot_type}",
                self.__class__.__name__,
            )
            return

        # The three guards above guarantee that experiments_and_channels, every
        # channels list, and selected_filters each contain exactly one entry,
        # so the triple-nested loop below runs exactly once.

        for exp, channels in experiments_and_channels.items():
            for channel in channels:
                exp_and_ch_arg = {exp: [channel]}
                # The selection tree hands back the channel as a display
                # string; plotted_datasets keys on the real int channel id.
                # Normalise once so that a future membership test cannot
                # disagree with the insert below, as it did in MetadataView.
                channel_id = int(channel) if channel is not None else None

                for subset_name, sql_filter in selected_filters.items():
                    bins = None
                    dataset_label = (
                        f"{loader} | {exp} Ch {channel}: {subset_name}"
                        if exp is not None
                        else f"{loader} | {subset_name}"
                    )
                    sizes = False

                    self.global_signal.emit(
                        "MetaDatabaseLoader",
                        loader,
                        "construct_event_data_query",
                        (sql_filter, exp_and_ch_arg),
                        "relay_event_query",
                        (),
                    )
                    if self.event_query == "":
                        return

                    load_event_data_args = self._build_load_event_data_args(
                        sql_filter, subset_name, exp, channel, exp_and_ch_arg, loader
                    )
                    self.global_signal.emit(
                        "MetaDatabaseLoader",
                        loader,
                        "load_event_data",
                        load_event_data_args,
                        "relay_event_data_generator",
                        (),
                    )

                    if self.event_data_generator:
                        if plot_type in ["Raw Histogram", "Filtered Histogram"]:
                            bins = parameters["bins"]
                            sizes = parameters["sizes"]

                            bin_sensitive = True
                            bins_changed = getattr(self, "allowed_bins", None) != bins
                            sizes_changed = (
                                getattr(self, "allowed_sizes", None) != sizes
                            )

                            if bin_sensitive and (bins_changed or sizes_changed):
                                axis_type = "2d"
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
                            self.logger.info(
                                "No plot data generates for the requested plot configuration"
                            )
                            self.add_text_to_display.emit(
                                "No plot data generates for the requested plot configuration",
                                self.__class__.__name__,
                            )
                            return
                    else:
                        self.logger.warning(f"Invalid plot type: {plot_type}")
                        return

                    self.allowed_plot_type = plot_type
                    self.allowed_bins = bins
                    self.allowed_sizes = sizes

                    self.plotted_datasets.add(
                        (loader, exp, channel_id, sql_filter, subset_name)
                    )

        if not self._fit_and_plot_ensemble_geometry(plot_data, plot_type, d, L, N):
            return

    @log(logger=logger)
    def _fit_and_plot_ensemble_geometry(
        self, plot_data: pd.DataFrame, plot_type: str, d: float, L: float, N: int
    ) -> bool:
        """
        Fit a double Gaussian to the aggregated ensemble histogram, then Monte
        Carlo sample prolate/oblate V/m ensembles from that fit and plot them.

        Called once by _update_distribution_ensemble after its single
        (experiment, channel, filter) combination has been plotted, using
        whatever plot_data that produced.

        :param plot_data: the aggregated histogram DataFrame to fit against.
        :type plot_data: pd.DataFrame
        :param plot_type: the plot type label to reuse when plotting the fit.
        :type plot_type: str
        :param d: the diameter of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :param N: target number of samples to draw for each of the prolate/oblate ensembles
        :type N: int

        :return: True if fitting and plotting succeeded, False if any failure occurred (already logged/displayed to the user).
        :rtype: bool
        """
        popt = self._fit_and_sanity_check_double_gaussian(
            plot_data["Normalized Current"].values, plot_data["Amplitude"].values
        )

        if popt is None:
            self.logger.info("Unable to fit a double gaussian to the histogram")
            self.add_text_to_display.emit(
                "Unable to fit a double gaussian to the histogram",
                self.__class__.__name__,
            )
            return False

        fit_data = self._double_gaussian(plot_data["Normalized Current"].values, *popt)
        plot_data["Amplitude"] = fit_data
        self.update_plot(
            plot_type,
            plot_data,
            plot_data.columns,
            ["pA", ""],
            logscales=[False, False],
            dataset_label="Fit",
        )
        # --- record fit + binning for Report All reporting ---
        self.ensemble_fit_params = popt
        self.ensemble_fit_bins = self.allowed_bins
        self.ensemble_fit_sizes = self.allowed_sizes

        amp1, mean1, std1, amp2, mean2, std2 = popt

        if mean1 > mean2:
            mean_max, std_max = mean1, np.abs(std1)
            mean_min, std_min = mean2, np.abs(std2)
        else:
            mean_max, std_max = mean2, np.abs(std2)
            mean_min, std_min = mean1, np.abs(std1)

        # --- OPTIMIZED GENERATIVE SAMPLING ---
        # Call the Monte Carlo generators directly
        prolate_V, prolate_m = self._generate_vm_ensemble(
            N, mean_max, std_max, mean_min, std_min, d, L, prolate=True
        )
        oblate_V, oblate_m = self._generate_vm_ensemble(
            N, mean_max, std_max, mean_min, std_min, d, L, prolate=False
        )

        if len(prolate_V) == 0 and len(oblate_V) == 0:
            self.logger.warning(
                "Generative sampling bailed out: The ensemble Gaussian fit represents an unphysical geometry."
            )
            self.add_text_to_display.emit(
                "Generative sampling bailed out: The ensemble Gaussian fit represents an unphysical geometry.",
                self.__class__.__name__,
            )
            return False
        elif len(prolate_V) < N or len(oblate_V) < N:
            self.logger.info(
                "Sampling hit bailout limit; returning partial ensemble arrays."
            )

        prolate_b = (3 * prolate_V / (4 * np.pi * prolate_m)) ** (1 / 3)
        prolate_a = prolate_b * prolate_m

        oblate_b = (3 * oblate_V / (4 * np.pi * oblate_m)) ** (1 / 3)
        oblate_a = oblate_b * oblate_m

        # --- Create the Pandas DataFrames ---
        df_prolate = pd.DataFrame(
            {"V": prolate_V, "m": prolate_m, "a": prolate_a, "b": prolate_b}
        )
        df_oblate = pd.DataFrame(
            {"V": oblate_V, "m": oblate_m, "a": oblate_a, "b": oblate_b}
        )

        # --- record V/m summaries for Report All reporting ---
        self.ensemble_fit_prolate_summary = (
            self._summarize_vm(df_prolate) if not df_prolate.empty else None
        )
        self.ensemble_fit_oblate_summary = (
            self._summarize_vm(df_oblate) if not df_oblate.empty else None
        )

        if not df_prolate.empty:
            self.update_plot(
                "Scatterplot",
                df_prolate,
                ["V", "m"],
                ["nm$^{3}$", None],
                logscales=[False, False],
                dataset_label="Prolate Solutions",
            )
        if not df_oblate.empty:
            self.update_plot(
                "Scatterplot",
                df_oblate,
                ["V", "m"],
                ["nm$^{3}$", None],
                logscales=[False, False],
                dataset_label="Oblate Solutions",
            )

        return True

    @log(logger=logger)
    def _compute_theoretical_blockages(
        self,
        V: npt.NDArray[np.float64],
        m: npt.NDArray[np.float64],
        d: float,
        L: float,
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Vectorized forward model: Calculates theoretical max and min blockages
        for arrays of volume (V) and shape factor (m).

        :param V: array of volumes of spheroids in cubic nanometers
        :type V: npt.NDArray[np.float64]
        :param m: array of shape factors of spheroids (major axis / minor axis) of the same length as V. All must be either 0<m<1 or all m>1.
        :type m: npt.NDArray[np.float64]
        :param d: the diameter of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :return: Tuple of arrays of theoretical max and min blockage values for the given parameters, one per V,m pair
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
        :raises ValueError: If `m` contains a mix of oblate (0<m<1) and prolate (m>1)
            form factors, or any negative form factor.
        """
        m_sq = m**2

        if all(m <= 1):
            prolate = False
        elif all(m >= 1):
            prolate = True
        elif any(m < 0):
            raise ValueError("Cannot have negative form factors")
        else:
            raise ValueError(
                "Cannot mix oblate and prolate form factors in a single call to _compute_theoretical_blockages"
            )

        try:
            if not prolate:
                gamma_parallel = 1 / (
                    1 - (1 / (1 - m_sq)) * (1 - (m / np.sqrt(1 - m_sq)) * np.arccos(m))
                )
            else:
                gamma_parallel = 1 / (
                    1
                    - (1 / (m_sq - 1))
                    * ((m / np.sqrt(m_sq - 1)) * np.log(m + np.sqrt(m_sq - 1)) - 1)
                )

            gamma_perpendicular = 1 / (1 - 0.5 / gamma_parallel)
        except ValueError:  # divide by zero from a m=1 case
            gamma_perpendicular = 1.5
            gamma_parallel = 1.5

        b = (3 * V / (4 * np.pi * m)) ** (1 / 3)
        a = b * m
        d_ptn = 2 * b
        l_ptn = 2 * a

        gamma_parallel_prime = gamma_parallel / (
            1 - 0.71 * ((d_ptn**2 + l_ptn**2) / (d**2 + l_ptn**2)) * (d_ptn / d) ** 2
        )

        gamma_perpendicular_prime = gamma_perpendicular / (
            1 - (0.32 + 0.48 * l_ptn / d) * (l_ptn * d_ptn**2 / d**3)
        )

        volume_factor = (4 * V) / (np.pi * d**2 * (L + 0.8 * d))

        parallel_term = volume_factor * gamma_parallel_prime
        perpendicular_term = volume_factor * gamma_perpendicular_prime

        # Map parallel/perpendicular to max/min based on your original logic
        if not prolate:
            dI_max = parallel_term
            dI_min = perpendicular_term
        else:
            dI_max = perpendicular_term
            dI_min = parallel_term

        return dI_max, dI_min

    @log(logger=logger)
    def _generate_vm_ensemble(
        self,
        N_target: int,
        mean_max: float,
        std_max: float,
        mean_min: float,
        std_min: float,
        d: float,
        L: float,
        prolate: bool = True,
        cutoff_std: float = 4,
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Uses Monte Carlo rejection sampling with dynamic bounds to find valid (V, m) pairs.
        Bails out after a maximum number of consecutive failed batches if the experimental
        data represents an unphysical geometry.

        :param N_target: number of value V,m pairs to generate, if possible
        :type N_target: int
        :param mean_max: The mean value of the larger of the two blockage histograms
        :type mean_max: float
        :param std_max: The standard deviation value of the larger of the two blockage histograms
        :type std_max: float
        :param mean_min: The mean value of the smaller of the two blockage histograms
        :type mean_min: float
        :param std_min: The standard deviation value of the smaller of the two blockage histograms
        :type std_min: float
        :param d: the length of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :param prolate: whether we are looking for prolate (m>1) solutions or oblate (0<m<1) solutions
        :type prolate: bool
        :param cutoff_std: the number of standard deviations outside the mean after which to cut off solutions
        :type cutoff_std: float
        :return: Tuple of arrays of V,m pairs
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
        """
        accepted_V: list[float] = []
        accepted_m: list[float] = []
        x = np.minimum(d, L)
        # --- Dynamic Bounds Calculation ---
        K = (np.pi * d**2 * (L + 0.8 * d)) / 4.0  # assumes gamma == 1
        gamma_min = 1

        highest_blockage = mean_max + cutoff_std * std_max
        V_max = highest_blockage * K / gamma_min

        V_min = 1  # we cannot see a 1 nm^3 object anyway so this will always be a safe minimum

        if V_min >= V_max:
            V_max = V_min * 10.0

        batch_size = 50000

        # --- Bailout Logic Variables ---
        max_consecutive_zeros = 5
        consecutive_zeros = 0
        max_batches = 200
        batches = 0

        while (
            len(accepted_V) < N_target
            and consecutive_zeros < max_consecutive_zeros
            and batches < max_batches
        ):
            batches += 1
            # 1. Propose physically valid uniform samples
            V_prop_raw = np.random.uniform(V_min, V_max, batch_size)
            ## pick max(a,b) < min(d,L), use a,b equations for a given V sample to calculate m limit in both cases. Prolate case: a>b, oblate: a<b.
            if prolate:
                m_upper_bounds_raw = np.sqrt((np.pi * x**3) / (6 * V_prop_raw))
                valid_mask = m_upper_bounds_raw >= 1

                V_prop = V_prop_raw[valid_mask]

                # Clip the upper bound to a physical maximum (e.g., m=50.0)
                # to prevent sampling impossible "1D string" geometries
                m_upper_bounds = np.clip(m_upper_bounds_raw[valid_mask], 1, 50.0)

                if len(V_prop) == 0:
                    consecutive_zeros += 1
                    continue

                m_prop = np.random.uniform(1, m_upper_bounds)

            else:
                m_lower_bounds_raw = (6 * V_prop_raw) / (np.pi * x**3)
                valid_mask = m_lower_bounds_raw <= 1

                V_prop = V_prop_raw[valid_mask]

                # Clip the lower bound to a physical minimum (e.g., m=0.01)
                # to prevent divide-by-zero errors and impossible "2D sheet" geometries
                m_lower_bounds = np.clip(m_lower_bounds_raw[valid_mask], 0.02, 1)

                if len(V_prop) == 0:
                    consecutive_zeros += 1
                    continue

                m_prop = np.random.uniform(m_lower_bounds, 1)

            # 2. Forward Calculation

            dI_max_calc, dI_min_calc = self._compute_theoretical_blockages(
                V_prop, m_prop, d, L
            )

            # Clean up unexpected NaNs
            nan_mask = np.isnan(dI_max_calc) | np.isnan(dI_min_calc)
            if np.all(nan_mask):
                consecutive_zeros += 1
                continue

            valid_math = ~nan_mask
            V_prop = V_prop[valid_math]
            m_prop = m_prop[valid_math]
            dI_max_calc = dI_max_calc[valid_math]
            dI_min_calc = dI_min_calc[valid_math]

            # 3. Calculate probability
            # Use safe standard deviations to prevent infinite Z-scores on artificially sharp fits
            safe_std_max = max(std_max, mean_max * 0.01)
            safe_std_min = max(std_min, mean_min * 0.01)

            z_sq_max = ((dI_max_calc - mean_max) / safe_std_max) ** 2
            z_sq_min = ((dI_min_calc - mean_min) / safe_std_min) ** 2

            # Absolute physical constraint: Ignore guesses that are > 4 standard deviations away
            # This prevents the sampler from accepting the "best of the worst" in terrible batches
            physical_mask = (z_sq_max < cutoff_std**2) & (z_sq_min < cutoff_std**2)

            if not np.any(physical_mask):
                consecutive_zeros += 1
                continue

            # Filter arrays to only physically reasonable points before probability rejection
            V_prop = V_prop[physical_mask]
            m_prop = m_prop[physical_mask]
            z_sq_max = z_sq_max[physical_mask]
            z_sq_min = z_sq_min[physical_mask]

            likelihood = np.exp(-0.5 * (z_sq_max + z_sq_min))
            max_likelihood = np.max(likelihood)

            if max_likelihood == 0 or np.isnan(max_likelihood):
                consecutive_zeros += 1
                continue

            prob_accept = likelihood / max_likelihood

            # 4. Accept / Reject
            random_thresh = np.random.uniform(0, 1, len(prob_accept))
            accepted_indices = random_thresh < prob_accept

            new_V = V_prop[accepted_indices]
            new_m = m_prop[accepted_indices]

            if len(new_V) == 0:
                consecutive_zeros += 1
            else:
                consecutive_zeros = (
                    0  # Reset counter if we got at least one valid point
                )
                accepted_V.extend(new_V)
                accepted_m.extend(new_m)

        if len(accepted_V) < N_target:
            self.logger.warning(
                f"_generate_vm_ensemble stopped with only {len(accepted_V)}/{N_target} "
                f"accepted samples after {batches} batches (consecutive_zeros={consecutive_zeros})"
            )

        return np.array(accepted_V[:N_target]), np.array(accepted_m[:N_target])

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
        # "No Event Database" is the combobox's placeholder, i.e. a normal empty state
        # rather than an error, so do not dispatch it as a plugin key.
        if not loader or loader == "No Event Database":
            return
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
    def _handle_other_actions(
        self, action_name: str, parameters: Dict[str, Any]
    ) -> None:
        """
        Raise an error for actions not yet implemented.

        :param action_name: The name of the unhandled action.
        :type action_name: str
        :param parameters: Parameters associated with the action.
        :type parameters: Dict[str, Any]
        :raises NotImplementedError: Always, since this action is not implemented.
        """
        raise NotImplementedError(f"{action_name} handler not implemented")

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
            self.add_text_to_display.emit(
                f"Raw SQL filter could not be validated:\n\n{error_msg}",
                self.__class__.__name__,
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
            self.proteincontrols.filter_comboBox.addItem(name)
            self.proteincontrols.filter_comboBox.selectItem(name, select=True)
            self.proteincontrols.filter_comboBox.refreshDisplayText()
            self.add_text_to_display.emit(
                f"Filter '{name}' added.",
                self.__class__.__name__,
            )

        self.clear_pending_filter_state()

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
                self.add_text_to_display.emit(
                    "No event database selected", self.__class__.__name__
                )
                return

            self._pending_filter_name = name
            self._pending_filter_text = filter_text
            self._pending_old_filter_name = None

            if dialog.is_raw:
                if not filter_text.strip().upper().startswith("SELECT"):
                    self.add_text_to_display.emit(
                        "Raw SQL filters must be complete SELECT statements, e.g. SELECT duration FROM events WHERE duration > 1000",
                        self.__class__.__name__,
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

            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "construct_metadata_query",
                (
                    (
                        list(self.available_columns[:3])
                        if hasattr(self, "available_columns") and self.available_columns
                        else ["sublevel_current", "voltage", "duration"]
                    ),
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
                self.add_text_to_display.emit(
                    "No event database selected", self.__class__.__name__
                )
                return

            self._pending_filter_name = new_name
            self._pending_filter_text = new_filter
            self._pending_old_filter_name = name

            if dialog.is_raw:
                if not new_filter.strip().upper().startswith("SELECT"):
                    self.add_text_to_display.emit(
                        "Raw SQL filters must be complete SELECT statements, e.g. SELECT duration FROM events WHERE duration > 1000",
                        self.__class__.__name__,
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
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "construct_metadata_query",
                (
                    (
                        list(self.available_columns[:3])
                        if hasattr(self, "available_columns") and self.available_columns
                        else ["sublevel_current", "voltage", "duration"]
                    ),
                    new_filter,
                    None,
                ),
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
        selected_items = self.proteincontrols.filter_comboBox.getSelectedItems()

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

        list_widget = self.proteincontrols.filter_comboBox.listWidget
        for i in reversed(range(list_widget.count())):
            widget = list_widget.itemWidget(list_widget.item(i))
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.text() == name:
                    list_widget.takeItem(i)
                    break

        self.proteincontrols.filter_comboBox.refreshDisplayText()

    @log(logger=logger)
    def get_selected_filters(self) -> dict:
        """
        Get a dict of the filters that the user has indicated should be active for the current plotting task
        """
        return {
            name: self.subset_filters.get(name, "")
            for name in self.proteincontrols.filter_comboBox.getSelectedItems()
        }

    @log(logger=logger)
    def replace_filter_item(self, name: str) -> None:
        """
        Remove any existing filter item with the same name and add the new one.

        :param name: The name of the filter to (re)add.
        :type name: str
        """
        list_widget = self.proteincontrols.filter_comboBox.listWidget
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            widget = list_widget.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            if checkbox and checkbox.text() == name:
                list_widget.takeItem(i)
                break

        self.proteincontrols.filter_comboBox.addItem(name)
        self.proteincontrols.filter_comboBox.selectItem(name, select=True)

    @log(logger=logger)
    def update_filter_name(self, old_name: str, new_name: str) -> None:
        """
        Replace old filter name with new one in the ComboBox, removing any duplicates.

        :param old_name: The filter name being replaced.
        :type old_name: str
        :param new_name: The filter name to display instead.
        :type new_name: str
        """
        list_widget = self.proteincontrols.filter_comboBox.listWidget

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
        self.proteincontrols.filter_comboBox.addItem(new_name)
        self.proteincontrols.filter_comboBox.selectItem(new_name, select=True)
        self.proteincontrols.filter_comboBox.refreshDisplayText()

    def get_walkthrough_steps(self) -> List[WalkthroughStep]:
        return [
            (
                "Protein Tab",
                "Click the '+' button to load your protein database.",
                "ProteinView",
                lambda: [self.proteincontrols.db_loader_add_button],
            ),
            (
                "Protein Tab",
                "Click the 'Scope' button to select specific experiments and channels. By default, all options are selected.",
                "ProteinView",
                lambda: [self.proteincontrols.selection_tree_button],
            ),
            (
                "Protein Tab",
                "Enter the pore diameter and length, in nanometers. These are required for volume and shape-factor fitting.",
                "ProteinView",
                lambda: [
                    self.proteincontrols.pore_diameter_lineEdit,
                    self.proteincontrols.pore_length_lineEdit,
                ],
            ),
            (
                "Protein Tab",
                "Choose Individual mode to fit each event separately, or Ensemble mode to fit one shared distribution across all events in scope.",
                "ProteinView",
                lambda: [
                    self.proteincontrols.individual_button,
                    self.proteincontrols.ensemble_button,
                ],
            ),
            (
                "Protein Tab",
                "Set N, the number of Monte Carlo samples used to estimate volume and shape factor.",
                "ProteinView",
                lambda: [self.proteincontrols.n_values_lineEdit],
            ),
            (
                "Protein Tab",
                "Specify histogram bins as either a count or, if 'Sizes' is checked, a bin width.",
                "ProteinView",
                lambda: [self.proteincontrols.bins_lineEdit],
            ),
            (
                "Protein Tab",
                "Check this box to enter bin widths instead of bin counts.",
                "ProteinView",
                lambda: [self.proteincontrols.sizes_checkbox],
            ),
            (
                "Protein Tab",
                "Once you're ready, click 'Update Plot' to generate the histogram and volume/shape-factor scatterplots.",
                "ProteinView",
                lambda: [self.proteincontrols.update_plot_button],
            ),
            (
                "Protein Tab",
                "In Individual mode, click 'Commit Individual' to write the per-event fit results to the database.",
                "ProteinView",
                lambda: [self.proteincontrols.commit_individual],
            ),
            (
                "Protein Tab",
                "In Ensemble mode, click 'Report All' to display the double-Gaussian fit parameters and volume/shape-factor summaries for the current binning.",
                "ProteinView",
                lambda: [self.proteincontrols.report_all],
            ),
            (
                "Protein Tab",
                "Click the '+' button to apply filters to the full database or selected experiment/channels to create subsets.",
                "ProteinView",
                lambda: [self.proteincontrols.filter_add_button],
            ),
            (
                "Protein Tab",
                "Use this dropdown to view your created subsets.",
                "ProteinView",
                lambda: [self.proteincontrols.filter_comboBox],
            ),
            (
                "Protein Tab",
                "Click here to see the information and edit the currently selected subset.",
                "ProteinView",
                lambda: [self.proteincontrols.filter_info_button],
            ),
            (
                "Protein Tab",
                "Click the delete button to remove all selected subsets. You can also delete individual ones directly from the dropdown.",
                "ProteinView",
                lambda: [self.proteincontrols.filter_delete_button],
            ),
            (
                "Protein Tab",
                "Click 'Save Filter' to save the current subsets for future use.",
                "ProteinView",
                lambda: [self.proteincontrols.save_filter_button],
            ),
            (
                "Protein Tab",
                "Click 'Load Filter' to import previously saved subsets.",
                "ProteinView",
                lambda: [self.proteincontrols.load_filter_button],
            ),
            (
                "Protein Tab",
                "Use 'Export Plot Data' to save the data currently shown in your plots.",
                "ProteinView",
                lambda: [self.proteincontrols.export_plot_data_pushButton],
            ),
            (
                "Protein Tab",
                "Select exactly one experiment and channel to visualize its events.",
                "ProteinView",
                lambda: [self.proteincontrols.selection_tree_button],
            ),
            (
                "Protein Tab",
                "Enter the starting event ID and the number of events you want to visualize.",
                "ProteinView",
                lambda: [
                    self.proteincontrols.event_id_lineEdit,
                    self.proteincontrols.n_events_lineEdit,
                ],
            ),
            (
                "Protein Tab",
                "Click 'Plot Events' to view raw/filtered/fitted traces, or 'Plot Histogram' to view a ΔI/I histogram, for the selected events.",
                "ProteinView",
                lambda: [
                    self.proteincontrols.plot_events_pushButton,
                    self.proteincontrols.plot_histogram_pushButton,
                ],
            ),
            (
                "Protein Tab",
                "Use the arrows to navigate to the next or previous events in the filtered set.",
                "ProteinView",
                lambda: [
                    self.proteincontrols.left_arrow_button,
                    self.proteincontrols.right_arrow_button,
                ],
            ),
            (
                "Protein Tab",
                "Check the RAW box to overlay the unfiltered raw signal alongside the filtered and fitted traces.",
                "ProteinView",
                lambda: [self.proteincontrols.raw_checkbox],
            ),
        ]

    def get_current_view(self) -> str:
        return "ProteinView"


def format_axis_label(label: str, unit: Optional[str]) -> str:
    """
    Ensure the axis label contains the correct unit exactly once.
    Removes any existing trailing unit in parentheses.
    """
    label = re.sub(r"\s*\(.*?\)$", "", label)  # Remove trailing "(...)"
    return f"{label} ({unit})" if unit else label
