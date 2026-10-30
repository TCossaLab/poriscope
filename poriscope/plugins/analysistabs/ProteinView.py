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
import warnings
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    override,
)

import numpy as np
import numpy.typing as npt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLayout,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from poriscope.plugins.analysistabs.utils.proteincontrols import ProteinControls
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabControls import MetaSubsetTabControls
from poriscope.utils.MetaSubsetTabView import MetaSubsetTabView
from poriscope.views.widgets.walkthrough_mixin import (
    WalkthroughStep,
)

warnings.filterwarnings(
    "ignore",
    message="constrained_layout not applied because axes sizes collapsed to zero",
)


#: The fitted columns ``_commit_fits`` writes, in the order they are written.
#: ``FIT_COLUMN_UNITS`` is index-aligned with it, ``None`` where dimensionless, and
#: the two are kept beside each other because a column added to one and not the other
#: silently mislabels every column after it.
FIT_COLUMNS = [
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

#: Units for :py:data:`FIT_COLUMNS`, index-aligned with it.
FIT_COLUMN_UNITS: List[Optional[str]] = [
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


@inherit_docstrings
class ProteinView(MetaSubsetTabView):
    """
    Subclass of MetaSubsetTabView for estimating translocating protein size and shape from nanopore blockage events.

    Given pore diameter/length, fits a two-population (prolate/oblate) volume-and-shape-factor model via Monte Carlo rejection sampling, either per event (Individual mode) or across the aggregate distribution (Ensemble mode). Also supports subset filtering, per-event trace/histogram inspection, and committing or reporting fit results.
    """

    logger = logging.getLogger(__name__)

    #: Asks the Controller for an Individual plot: the loader's key, the selected filters
    #: (name to SQL), the scope, the bin request, the Sizes flag, the pore diameter and
    #: length, and how many solutions to sample per event. The intent a click captured,
    #: which is what the Controller records, so a replay draws what was asked for.
    individual_distribution_requested = Signal(
        str, object, object, object, bool, float, float, int
    )

    #: Asks whether the database already holds fit columns, before any are written.
    #: Answered through ``confirm_fit_commit``.
    #:
    #: Two-phase, because whether the user is asked anything at all depends on this
    #: answer - a single request would have to open the modal from inside the Controller.
    fit_commit_requested = Signal(str)

    #: Sends the approved write out: the loader's key and the table whose existing fit
    #: columns are to be dropped first (None when there are none). The Controller writes
    #: the Individual fit the Model keeps. The user's decision travels here rather than
    #: being parked on this widget between the two phases.
    fit_commit_confirmed = Signal(str, object)

    #: Asks the Controller for an Ensemble plot, with the same intent as
    #: ``individual_distribution_requested``.
    ensemble_distribution_requested = Signal(
        str, object, object, object, bool, float, float, int
    )

    #: Asks the Controller for Report All: it hands back the Ensemble fit the Model keeps,
    #: through ``show_ensemble_report``.
    ensemble_report_requested = Signal()

    #: Asks the Controller to draw events on the event page: the loader's key, the
    #: ``event_id`` values the Event ID resolved to through the filtered-event cache, the
    #: experiment, the channel as the selection tree reports it, the filter's name and SQL,
    #: and the Raw flag. The events a click resolved, which is what the Controller records,
    #: so a replay draws them whatever the panel and the cache hold then.
    plot_events_requested = Signal(str, list, object, object, str, str, bool)

    #: Asks for one double-gaussian fit per event: the (bins, amplitude) pairs, the
    #: frames they came from, and the events themselves. Answered through
    #: ``set_event_histogram_fits``.
    #:
    #: One request for the whole set rather than one per event. A per-event round trip
    #: would work - a same-thread Qt signal is synchronous - but only by parking each
    #: answer where the loop body could read it back. A ``None`` pair marks an event whose
    #: histogram could not be built, so every list stays index-aligned with the events.
    #:
    #: It carries the events and the bin request rather than histograms built here,
    #: because the binning and the fitting are made together and must describe the same
    #: bins.
    event_histogram_fits_requested = Signal(object, str, object, bool)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the ProteinView instance.
        """
        self._clear_cache()
        self.no_cached_data = False

        self._analysis_mode: str = (
            "individual"  # default mode; toggled by Individual/Ensemble buttons
        )

        # Heterogeneous by design: _plot_all_points_histogram appends (x, y)
        # tuples rather than plain arrays. Flagged for review.
        self.hist_data: List[Any] = []
        self.hist_labels: List[Optional[str]] = []
        self.current_sql_filter = None
        self.current_experiment = None
        self.current_channel = None
        self.filtered_event_ids = []
        self.subset_filters = {}
        self.plot_events_generator = None
        self.available_experiment_and_channels_by_loader: Dict[
            str, Dict[str, List[str]]
        ] = {}
        self.selected_experiment_and_channels_by_loader = {}

        self._last_event_action: str = "plot_events"  # or "plot_histogram"

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
        Ask whether this database already holds fit data, before writing any.

        Phase one of a two-phase commit, because the look-up interleaves with a modal
        question: whether the user is asked anything at all depends on the answer, so it
        cannot be a single request. The Controller checks it holds an Individual fit and
        looks, then calls :py:meth:`confirm_fit_commit` back.

        :param loader: Name or ID of the database loader plugin.
        :type loader: str
        """
        self.fit_commit_requested.emit(loader)

    @log(logger=logger)
    @Slot(str, object)
    def confirm_fit_commit(self, loader: str, table_name: Optional[str]) -> None:
        """
        Ask the user about an overwrite if there is one, then send the write out.

        Phase two of the commit. ``table_name`` is both the answer and the flag:
        ``None`` means the database holds no fit columns, so there is nothing to
        confirm and the write goes straight out. The user's decision travels back in
        the intent rather than being parked on this widget between the halves.

        :param loader: Name or ID of the database loader plugin.
        :type loader: str
        :param table_name: the table already holding fit columns, or None
        :type table_name: Optional[str]
        :return: None
        :rtype: None
        """
        if table_name is not None:
            reply = QMessageBox.question(
                self,
                "Confirm Overwrite",
                "fit data data already exists, are you sure you want to overwrite? "
                "This action cannot be undone.",
                QMessageBox.Ok | QMessageBox.Cancel,
            )
            if reply != QMessageBox.Ok:
                return

        self.fit_commit_confirmed.emit(loader, table_name)

    @log(logger=logger)
    def on_fit_commit_finished(self, loader: str) -> None:
        """
        Tell the rest of the app that the loader has new columns.

        Called by the Controller once the write has been attempted, so a commit that
        never reached the database does not announce new columns. This tab reads no
        column names itself, so it asks for none.

        :param loader: Name or ID of the database loader plugin.
        :type loader: str
        :return: None
        :rtype: None
        """
        self.plugin_state_changed.emit("MetaDatabaseLoader", loader, "columns")

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
    def show_ensemble_report(
        self,
        params: Sequence[float],
        bins: Any,
        sizes: bool,
        prolate: pd.DataFrame,
        oblate: pd.DataFrame,
    ) -> None:
        """
        Report the Ensemble plot's double-Gaussian fit and V/m sample summaries.

        Ensemble mode has no per-event id to write these back to the database against, so
        this is a display-only report rather than a database commit. Called by the
        Controller with the fit the Model keeps.

        :param params: the fit, as (amp1, mean1, std1, amp2, mean2, std2)
        :type params: Sequence[float]
        :param bins: the bins entry the histogram was built with, or None to estimate
        :type bins: Any
        :param sizes: does bins refer to a bin width
        :type sizes: bool
        :param prolate: the prolate solutions sampled from the fit
        :type prolate: pd.DataFrame
        :param oblate: the oblate solutions sampled from the fit
        :type oblate: pd.DataFrame
        :return: None
        :rtype: None
        """
        amp1, mean1, std1, amp2, mean2, std2 = params

        if sizes:
            bin_desc = f"bin size(s) = {bins}"
        else:
            bin_desc = f"bin count = {bins or 100}"

        lines = [
            "<br>",
            f"<b>Ensemble double-Gaussian fit</b> ({bin_desc})",
            f"&nbsp;&nbsp;Peak 1: amplitude={amp1:.4g}, mean={mean1:.4g}, std={std1:.4g}",
            f"&nbsp;&nbsp;Peak 2: amplitude={amp2:.4g}, mean={mean2:.4g}, std={std2:.4g}",
            "",
        ]

        if not prolate.empty:
            rows, count_label = self._summarize_vm(prolate)
            lines.append(f"<b>Prolate</b> ({count_label})")
            lines.extend(f"&nbsp;&nbsp;{row}" for row in rows)
            lines.append("")

        if not oblate.empty:
            rows, count_label = self._summarize_vm(oblate)
            lines.append(f"<b>Oblate</b> ({count_label})")
            lines.extend(f"&nbsp;&nbsp;{row}" for row in rows)

        self.add_text_to_display.emit("<br>".join(lines), self.__class__.__name__)

    @property
    def _subset_controls(self) -> MetaSubsetTabControls:
        """
        The controls panel, under the name ``MetaSubsetTabView``'s shared methods use.

        Annotated with the base's type rather than ``ProteinControls`` so the override
        matches the declaration verbatim, which is what the plugin compliance test
        compares. Tab-specific code keeps using ``self.proteincontrols``.

        :return: the panel built by ``_build_controls``
        :rtype: MetaSubsetTabControls
        """
        return self.proteincontrols

    @log(logger=logger)
    def _build_controls(self) -> ProteinControls:
        """
        Build the tab's controls panel and keep it under this tab's own name.

        ``MetaView._set_control_area`` connects it and places it in the layout; the
        named attribute is kept because it is used throughout this tab.

        :return: the controls panel
        :rtype: ProteinControls
        """
        self.proteincontrols = ProteinControls()
        return self.proteincontrols

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

        self.fig_event.set_layout_engine("constrained")
        self._clear_cache()

    @log(logger=logger)
    def clear_plot(self, axis_type: str = "2d", mode: str = "individual") -> None:
        """
        Clear one analysis mode's histogram and V/M figures, and what the histogram accumulated.

        Called by ``ProteinController.reset``, which records the reset; clears no fit.

        :param axis_type: Either '2d' or '3d'; the figures here are always 2-D
        :type axis_type: str
        :param mode: 'individual' or 'ensemble', whose figures are cleared
        :type mode: str
        """
        for kind in ("hist", "vm"):
            figure = getattr(self, f"fig_{kind}_{mode}")
            figure.clear()
            setattr(self, f"ax_{kind}_{mode}", figure.add_subplot(1, 1, 1))
            try:
                figure.tight_layout(pad=0.5)
            except Exception:
                # tight_layout can fail on awkward axes geometry; the plot still
                # renders, just less tidily, so carry on but leave a trace.
                self.logger.debug(
                    f"tight_layout failed for the {kind} figure", exc_info=True
                )
            getattr(self, f"canvas_{kind}_{mode}").draw()

        self.hist_data = []
        self.hist_labels = []

    @log(logger=logger)
    @override
    def _reset_actions(self, axis_type: str = "2d") -> None:
        """
        Clear the figures of the mode showing, unrecorded; a plot clears its own mode's.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        """
        self.clear_plot(axis_type, self._analysis_mode)

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
        ax.legend(loc="best", fontsize="x-small")

    def show_histogram(
        self, mode: str, plot_data: pd.DataFrame, dataset_label: str
    ) -> None:
        """
        Draw an averaged histogram, or its fit, on a mode's histogram figure, over what it holds.

        :param mode: 'individual' or 'ensemble', whose figure is drawn on
        :type mode: str
        :param plot_data: bin centers and amplitudes, in that column order
        :type plot_data: pd.DataFrame
        :param dataset_label: the label the curve is drawn under
        :type dataset_label: str
        """
        self._plot_all_points_histogram(
            getattr(self, f"ax_hist_{mode}"),
            plot_data,
            plot_data.columns,
            ["pA", ""],
            dataset_label=dataset_label,
            norm=False,
        )
        self._finish_plot(mode, "hist")

    @log(logger=logger)
    def show_solutions(
        self,
        mode: str,
        columns: Sequence[npt.NDArray[np.float64]],
        dataset_label: str,
    ) -> None:
        """
        Draw the sampled volume and shape factor of one shape on a mode's V/M figure.

        :param mode: 'individual' or 'ensemble', whose figure is drawn on
        :type mode: str
        :param columns: the filtered V and m values
        :type columns: Sequence[npt.NDArray[np.float64]]
        :param dataset_label: the shape's label
        :type dataset_label: str
        """
        self.set_scatterplot(
            columns,
            getattr(self, f"ax_vm_{mode}"),
            [
                self.format_axis_label("V", "nm$^{3}$"),
                self.format_axis_label("m", None),
            ],
            dataset_label,
        )
        self._finish_plot(mode, "vm")

    @log(logger=logger)
    def show_peak_fits(
        self,
        mode: str,
        columns: Sequence[npt.NDArray[np.float64]],
        dataset_label: str,
    ) -> None:
        """
        Draw each event's two fitted blockages, with their errors, on a mode's histogram figure.

        :param mode: 'individual' or 'ensemble', whose figure is drawn on
        :type mode: str
        :param columns: the filtered smaller and larger blockages and their two errors
        :type columns: Sequence[npt.NDArray[np.float64]]
        :param dataset_label: the label the points are drawn under
        :type dataset_label: str
        """
        self.set_xyerr_scatterplot(
            columns,
            getattr(self, f"ax_hist_{mode}"),
            [
                self.format_axis_label("min_fractional_blockage", "arb. units"),
                self.format_axis_label("max_fractional_blockage", "arb. units"),
            ],
            dataset_label,
        )
        self._finish_plot(mode, "hist")

    @log(logger=logger)
    def _finish_plot(self, mode: str, kind: str) -> None:
        """
        Lay out and draw one of a mode's figures, and hand what it holds to the export cache.

        :param mode: 'individual' or 'ensemble'
        :type mode: str
        :param kind: 'hist' or 'vm'
        :type kind: str
        """
        canvas = getattr(self, f"canvas_{kind}_{mode}")
        try:
            canvas.figure.tight_layout(pad=0.5)
        except Exception:
            # tight_layout can fail on awkward axes geometry; the plot still
            # renders, just less tidily, so carry on but leave a trace.
            self.logger.debug("tight_layout failed for the plot canvas", exc_info=True)
        canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def set_xyerr_scatterplot(
        self,
        columns: Sequence[npt.NDArray[np.float64]],
        ax: Axes,
        axis_labels: Sequence[str],
        dataset_label: str,
    ) -> None:
        """
        Draw a scatterplot of two filtered columns with their error bars.

        Separate from ``set_scatterplot`` because only this tab has an error-bar variant.
        The four arrays arrive filtered together, so the bars still line up with the
        points after any row is dropped.

        :param columns: the filtered x, y, x error and y error values
        :type columns: Sequence[npt.NDArray[np.float64]]
        :param ax: the axis object on which to plot
        :type ax: Axes
        :param axis_labels: the x and y axis labels, already formatted
        :type axis_labels: Sequence[str]
        :param dataset_label: Label for the dataset.
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        xdata, ydata, x_err, y_err = columns
        x_label, y_label = axis_labels

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
        Ignore plugin state changes: nothing this tab shows depends on them.

        The one change the app announces is a database loader gaining columns, and
        this tab reads no column names. The experiment tree is fetched when the
        loader is selected.

        :param metaclass: The metaclass of the plugin instance whose state changed.
        :type metaclass: str
        :param plugin_key: The unique key identifying the plugin instance that changed.
        :type plugin_key: str
        :param reason: A short string identifying what kind of change occurred.
        :type reason: str
        :return: None
        :rtype: None
        """

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
                self.request_experiment_structure(loader)

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
            self._handle_plot_events(parameters)
        elif action_name == "plot_histogram":
            self._handle_plot_histogram(parameters)
        elif action_name == "shift_range_forward":
            self._shift_range_and_update_plot(parameters, direction="right")

        elif action_name == "update_plot":
            self._set_display_mode("distribution")
            loader = parameters["db_loader"]
            scope = self.selected_experiment_and_channels_by_loader.get(loader)
            request = (
                self.individual_distribution_requested
                if self._analysis_mode == "individual"
                else self.ensemble_distribution_requested
            )
            request.emit(
                loader,
                self.get_selected_filters(),
                copy.deepcopy(scope) if scope else {},
                parameters.get("bins"),
                bool(parameters.get("sizes", False)),
                float(parameters["pore_diameter"]),
                float(parameters["pore_length"]),
                int(parameters.get("n_values") or 100),
            )

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
            self._commit_fits(parameters.get("db_loader"))

        elif action_name == "report_all":
            self.ensemble_report_requested.emit()

        else:
            self._handle_other_actions(action_name, parameters)

    # -------------------------------------------------------------------------
    # Event navigation
    # -------------------------------------------------------------------------

    @log(logger=logger)
    def _replot_after_shift(self, parameters: Dict[str, Any]) -> None:
        """
        Re-plot after navigation in the display last requested: histogram or events.

        :param parameters: the navigation parameters, with ``event_id`` moved to the new event
        :type parameters: Dict[str, Any]
        """
        if self._last_event_action == "plot_histogram":
            self._handle_plot_histogram(parameters)
        else:
            self._handle_plot_events(parameters)

    @log(logger=logger)
    def _fetch_event_data(
        self, parameters: Dict[str, Any], action_label: str = "events"
    ) -> Optional[list[dict]]:
        """
        Validate the request, ask for exactly the events named, and order the answer.

        The scope guards stay here because they are about what the widget is showing;
        resolving ``event_index`` to database ids and loading those rows is one intent
        answered by ``MetaSubsetTabController.load_event_plot_data``. Always
        fetches fresh rather than caching event blobs in memory — event_id is only
        unique within an experiment/channel scope, and a per-event_id blob cache is an
        easy invariant to accidentally violate later; the targeted DB query is already
        O(events requested) rather than O(distance into the dataset), so the extra
        memoization isn't worth the correctness risk.

        **A refusal returns None and an empty fetch returns an empty list**, which is
        what lets the caller keep quiet about the first and speak about the second.
        Every refusal here, and every failure in the Controller's half, is reported by
        whoever refused it; returning ``[]`` for both made the caller add "no data
        available for event_id N" underneath, naming the event when the real reason was
        two channels in scope or an experiment the database no longer holds.

        :param parameters: Dictionary containing db_loader, filter, channels, and event indices.
        :type parameters: Dict[str, Any]
        :param action_label: Label used in error messages to identify the plot type.
        :type action_label: str
        :return: the fetched events in the order requested, empty if the fetch found none, or None if the request was refused and reported
        :rtype: Optional[list[dict]]
        """
        loader_name = parameters["db_loader"]
        if self._refuse_scope(loader_name, action_label):
            return None

        event_index = parameters["event_index"]
        exp_and_ch = self.selected_experiment_and_channels_by_loader[loader_name]
        exp = next(iter(exp_and_ch.keys()))
        selected_channel = next(iter(exp_and_ch.values()))[0]
        channel = int(selected_channel) if selected_channel is not None else None

        # Cleared first: the Controller sets the generator only once the whole chain
        # has succeeded, and reports which part did not, so a failure here is not
        # mistaken for the previous plot's events.
        self.plot_events_generator = None
        self.event_plot_data_requested.emit(
            loader_name, list(event_index), exp, channel, exp_and_ch, action_label
        )
        generator = self.plot_events_generator
        if generator is None:
            # The Controller sets the generator only once the whole chain has
            # succeeded, and reports which part did not - so this is a refusal that
            # has already been explained, not an empty result.
            return None

        data_list = list(generator)

        # restore the caller's requested order
        order = {eid: i for i, eid in enumerate(event_index)}
        data_list.sort(key=lambda e: order.get(e["event_id"], len(order)))

        return data_list

    @log(logger=logger)
    def _refuse_scope(self, loader_name: str, action_label: str) -> bool:
        """
        Say on the status panel why the selected filters and scope cannot be plotted from, if so.

        Events are plotted from one subset of one channel of one experiment.

        :param loader_name: the database loader plugin's key
        :type loader_name: str
        :param action_label: what the caller is plotting, for its messages
        :type action_label: str
        :return: True if refused, after saying why
        :rtype: bool
        """
        selected_filters = self.get_selected_filters()
        experiments_and_channels = self.selected_experiment_and_channels_by_loader.get(
            loader_name
        )

        if experiments_and_channels is None:
            self.add_text_to_display.emit(
                f"No experiments or channels are in scope, select at least one to plot {action_label}",
                self.__class__.__name__,
            )
            return True

        if selected_filters is not None and len(selected_filters) > 1:
            self.add_text_to_display.emit(
                "Unable to plot more than one subset at a time, select only one filter to apply",
                self.__class__.__name__,
            )
            return True

        if (
            self.selected_experiment_and_channels_by_loader[loader_name] is None
            or len(self.selected_experiment_and_channels_by_loader[loader_name]) == 0
        ):
            self.add_text_to_display.emit(
                f"No experiments or channels are in scope, select at least one to plot {action_label}",
                self.__class__.__name__,
            )
            return True

        if len(experiments_and_channels) > 1:
            self.add_text_to_display.emit(
                f"Only a single experiment can be used for plotting {action_label}",
                self.__class__.__name__,
            )
            return True

        for channels in experiments_and_channels.values():
            if len(channels) > 1:
                self.add_text_to_display.emit(
                    f"Only a single channel can be used for plotting {action_label}",
                    self.__class__.__name__,
                )
                return True

        return False

    @log(logger=logger)
    def _handle_plot_events(self, parameters: dict) -> None:
        """
        Resolve the Event ID to events through the filtered-event cache, and ask for them to be drawn.

        Refuses a scope events cannot be plotted from before building the cache, then
        snaps the Event ID to the cache and writes it back to the panel. The Controller
        records the request with the events it names.

        :param parameters: Dictionary containing db_loader, event_id (int), n_events (int)
                           and raw (bool).
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
        if self._refuse_scope(loader, "events"):
            return

        selected_filters = self.get_selected_filters()
        if not selected_filters:
            selected_filters = {"Full Dataset": ""}
        subset_name = next(iter(selected_filters))
        sql_filter = selected_filters[subset_name]
        experiments_and_channels = self.selected_experiment_and_channels_by_loader[
            loader
        ]
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
            if not self._rebuild_event_id_cache(
                loader, sql_filter, exp, channel, subset_name
            ):
                return

        cache = self.filtered_event_ids
        n_events = parameters.get("n_events") or 1
        idx = self._snap_to_filtered(parameters.get("event_id") or 0)
        self.proteincontrols.set_event_id_input(cache[idx])

        self.plot_events_requested.emit(
            loader,
            [cache[i] for i in range(idx, min(idx + n_events, len(cache)))],
            exp,
            selected_channel,
            subset_name,
            sql_filter,
            bool(parameters.get("raw", False)),
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
            subset_name = next(iter(selected_filters))
            if not self._rebuild_event_id_cache(
                loader, sql_filter, exp, channel, subset_name
            ):
                return

        cache = self.filtered_event_ids
        event_id = parameters.get("event_id") or 0
        n_events = parameters.get("n_events") or 1

        idx = self._snap_to_filtered(event_id)

        snapped_event_id = cache[idx]
        self.proteincontrols.set_event_id_input(snapped_event_id)

        # Resolve n_events consecutive ids from the cache starting at idx
        event_index = [cache[i] for i in range(idx, min(idx + n_events, len(cache)))]

        # Pass the resolved list into _fetch_event_data via the standard key
        fetch_params = parameters.copy()
        fetch_params["event_index"] = event_index

        data_list = self._fetch_event_data(fetch_params, action_label="histograms")

        if data_list is None:
            # Refused and already reported; see _handle_plot_events.
            return
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
    def show_events(
        self, event_data: Sequence[Dict[str, Any]], use_raw: bool = False
    ) -> None:
        """
        Draw the event page with raw, filtered, and fitted traces for multiple events.

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
        Ask for each event's histogram and its fit; the answer draws them.

        ``ProteinModel`` builds the histogram and its fit together: an event's
        histogram is an aggregate of its samples and it is exported with the plot, and
        binning it apart from fitting it would let the two describe different bins. This
        half ends at the request; ``set_event_histogram_fits`` does every bit of drawing.

        An event whose histogram cannot be built contributes ``None`` rather than
        being dropped, so the lists stay index-aligned with ``event_data`` and the
        drawing half still lays out one subplot per event in the original order.

        :param event_data: List of event dictionaries, each containing data and metadata for one event.
        :type event_data: Sequence[Dict[str, Any]]
        :param bins: Number of bins (if sizes==False) or size of bins (if sizes==True) for use when binning. Arrives as a single-element list from the controls and is passed down as it stands, hence the loose annotation.
        :type bins: Any
        :param sizes: Whether bins represent bin sizes.
        :type sizes: bool
        :param plot_type: Type of histogram to construct.
        :type plot_type: str
        :return: None
        :rtype: None
        """
        self.event_histogram_fits_requested.emit(event_data, plot_type, bins, sizes)

    @log(logger=logger)
    def set_event_histogram_fits(
        self,
        fits: Sequence[
            Tuple[Optional[npt.NDArray[np.float64]], Optional[npt.NDArray[np.float64]]]
        ],
        histograms: Sequence[
            Optional[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        ],
        event_data: Sequence[Dict[str, Any]],
    ) -> None:
        """
        Draw one subplot per event, overlaying each fit that succeeded.

        The answering half of ``event_histogram_fits_requested``. Every list is
        index-aligned with ``event_data``, so the subplot grid keeps its original
        positions whether or not a given event produced a histogram or a fit.

        A fit that failed is simply not overlaid - the histogram is still drawn. That
        was previously expressed as a ``ValueError`` raised into a bare ``except`` in
        the same loop body; it is a plain branch now, because the fit no longer
        happens here and there is nothing left to catch.

        :param fits: one (fit parameters, fitted curve) pair per event, index-aligned with event_data
        :type fits: Sequence[Tuple[Optional[npt.NDArray[np.float64]], Optional[npt.NDArray[np.float64]]]]
        :param histograms: each event's (bin centers, amplitude) pair, or None where none could be built
        :type histograms: Sequence[Optional[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]]
        :param event_data: List of event dictionaries, each containing data and metadata for one event.
        :type event_data: Sequence[Dict[str, Any]]
        :return: None
        :rtype: None
        """
        self._set_display_mode("event")
        self._clear_figure_state(create_default_axes=False)
        num_events = len(event_data)
        num_rows, num_cols = self._factors(num_events)

        x_label = self.format_axis_label("Normalized Current", "pA")
        y_label = self.format_axis_label("Amplitude", "")

        for j, event in enumerate(event_data):
            ax = self.fig_event.add_subplot(num_rows, num_cols, j + 1)
            label = f'Exp {event["experiment_id"]}/Ch {event["channel_id"]}/Event {event["event_id"]}'
            ax.set_title(label)

            histogram = histograms[j]
            if histogram is None:
                continue
            bincenters, amplitude = histogram

            _, curve = fits[j]
            if curve is not None:
                ax.plot(bincenters, curve, color="orange", zorder=2)
                self._update_cache(
                    (bincenters, label + " " + x_label),
                    (curve, label + " " + y_label),
                )

            ax.plot(bincenters, amplitude, color="blue", zorder=1)

            if j % num_cols == 0:
                ax.set_ylabel(y_label)
            labelnum = (num_rows - 1) * num_cols
            if num_events % num_cols > 0:
                labelnum -= num_cols - num_events % num_cols
            if j >= labelnum:
                ax.set_xlabel(x_label)

            self._update_cache(
                (bincenters, label + " " + x_label),
                (amplitude, label + " " + y_label),
            )

        self.fig_event.set_layout_engine("constrained")
        self.canvas_event.draw()
        self._commit_cache()

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
