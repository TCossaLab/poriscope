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
import os
import warnings
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union, override

import matplotlib.pyplot as pl
import numpy as np
import numpy.typing as npt
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from poriscope.plugins.analysistabs.utils.eventAnalysisControls import (
    EventAnalysisControls,
)
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventTabView import MetaEventTabView
from poriscope.views.widgets.walkthrough_mixin import (
    WalkthroughStep,
)


@inherit_docstrings
class EventAnalysisView(MetaEventTabView):
    """
    Subclass of MetaEventTabView for visualizing and interacting with event-based signal analysis.

    Handles event plotting, plugin integration, and user-triggered actions.
    """

    #: Asks the Controller for an event loader's channel list. Step 4a's first intent in
    #: this tab, and the same conversion RawData's reader lookup got: the answer arrives
    #: one hop later through ``update_channels`` instead of seven, and a loader that
    #: cannot be read is reported instead of failing silently inside the dispatcher.
    loader_channels_requested = Signal(str)

    #: Asks the Controller to write this tab's fitted events through a database writer,
    #: one channel at a time. No answer is expected: the plugin hands back a generator,
    #: which the Controller registers with the Model and runs.
    write_requested = Signal(str, list)

    #: Asks the Controller which of these channels the fitter has already completed.
    #: eventfitter, channels, filter key. The answer arrives as
    #: ``set_fitting_statuses``, because the prompt that follows it belongs to the View
    #: and the call that answers it does not - the same two-phase launch RawData's event
    #: finding uses.
    fitting_statuses_requested = Signal(str, list, str)

    #: Asks the Controller for the selected events, their raw traces and their fits,
    #: ready to plot. loader, eventfitter, channel, event indices, filter key, raw
    #: wanted. The answer arrives as ``set_event_plot_data``.
    event_plot_requested = Signal(str, str, int, list, str, bool)

    #: The second half: the channels the user approved, plus the filter key. No answer
    #: is expected; each channel's generator is registered and run by the Controller.
    fitting_requested = Signal(str, list, str)

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the EventAnalysisView. Called after constructor.
        Used to set up internal variables or state as needed.
        """
        pass

    @log(logger=logger)
    def update_plot(self) -> None:
        """
        Update the main plot with the latest data and features.
        This method should be called after data and parameters are updated.
        """
        pass

    @log(logger=logger)
    def _build_controls(self) -> EventAnalysisControls:
        """
        Build the tab's controls panel and keep it under this tab's own name.

        ``MetaView._set_control_area`` connects it and places it in the layout; the
        named attribute is kept because it is used throughout this tab.

        :return: the controls panel
        :rtype: EventAnalysisControls
        """
        self.eventAnalysisControls = EventAnalysisControls()
        return self.eventAnalysisControls

    @log(logger=logger)
    def _factors(self, n: int) -> Tuple[int, int]:
        """
        Compute a pair of factors of n that are closest to each other.
        Useful for determining subplot grid dimensions.

        :param n: Integer to factor.
        :type n: int
        :return: Tuple of two integers whose product is close to n and have minimal difference.
        :rtype: Tuple[int, int]
        """
        diff = n
        min_diff_pair = (1, n)
        while diff > 2:
            factor_pairs = [
                (i, n // i) for i in range(1, int(n**0.5) + 1) if n % i == 0
            ]
            min_diff_pair = min(factor_pairs, key=lambda pair: abs(pair[0] - pair[1]))
            diff = min_diff_pair[1] - min_diff_pair[0]
            n += 1
        return min_diff_pair

    @log(logger=logger)
    def get_save_filename(self) -> str:
        """
        Open a file dialog to let the user select a filename for saving a CSV file.

        :return: Absolute path to the selected file.
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
    def update_plot_data(self, data: Optional[Any] = None) -> None:
        """
        Update internal storage of plot data.
        Can be used by signal handlers receiving data.

        :param data: The data to be stored, can be a dict or array.
        :type data: Optional[Any]
        """
        self.logger.debug(f"Received data for plotting: {data}")
        if isinstance(data, dict):
            self.plot_data = data["data"]
        else:
            self.plot_data = data

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
    def update_plot_samplerate(self, samplerate: float) -> None:
        """
        Update the sampling rate used to convert time units in plots.

        :param samplerate: Sampling rate in Hz.
        :type samplerate: float
        """
        self.logger.debug(f"Received sampling rate: {samplerate}")
        self.plot_samplerate = samplerate

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
            loaders = available_plugins.get("MetaEventLoader", [])
            filters = available_plugins.get("MetaFilter", [])
            writers = available_plugins.get("MetaDatabaseWriter", [])
            eventfitters = available_plugins.get("MetaEventFitter", [])

            self.eventAnalysisControls.update_loaders(loaders)
            self.eventAnalysisControls.update_filters(filters)
            self.eventAnalysisControls.update_writers(writers)
            self.eventAnalysisControls.update_eventfitters(eventfitters)

            self.logger.debug("ComboBoxes updated with available loaders and filters")

        except Exception as e:
            self.logger.debug(f"Updating ComboBoxes failed: {repr(e)}")

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

        if action_name == "fit_events":
            self._handle_fit_events(parameters)
        elif action_name == "shift_range_backward":
            self._shift_range_and_update_plot(parameters, direction="left")
        elif action_name == "plot_events":
            self._handle_plot_events(parameters)
        elif action_name == "shift_range_forward":
            self._shift_range_and_update_plot(parameters, direction="right")
        elif action_name == "commit_events":
            self._handle_commit_events(parameters)
        elif action_name == "export_plot_data":
            self.export_plot_data.emit()
        else:
            self._handle_other_actions(action_name, parameters)

    @log(logger=logger)
    def _shift_range_and_update_plot(
        self, parameters: Dict[str, Any], direction: str
    ) -> None:
        """
        Shift ranges in the GUI and update plot and input if valid.

        :param parameters: Parameter dictionary collected from the control widgets.
        :type parameters: Dict[str, Any]
        :param direction: Either 'left' or 'right'.
        :type direction: str
        """

        try:
            loader, eventfitter, data_filter, channels, _ = (
                self._extract_plot_event_parameters(parameters)
            )
            self.validate_single_channel(channels)
            channels[0]
        except (IndexError, ValueError) as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return

        original_str = self._get_event_index_text()
        self.logger.debug(f"Original GUI input string: {original_str}")
        if not original_str:
            self.logger.debug("Event index input is empty.")
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
        self.eventAnalysisControls.set_event_index_input(new_event_str)

    def _get_event_index_text(self) -> str:  # Since params expanded
        """
        Get the current text from the event index input field.

        :return: Stripped text content of the event index field.
        :rtype: str
        """
        return self.eventAnalysisControls.event_index_lineEdit.text().strip()

    # Trigger the updated plot
    @log(logger=logger)
    def _handle_plot_events(self, parameters: Dict[str, Any]) -> None:
        """
        Ask the Controller for the selected events, their raw traces and their fits.

        Step 4a: this ran eight bus round trips itself - the event count, the filter
        callable, the samplerate, a load per event, an optional unfiltered load, the
        fitting status, the fit, and its features - assembling the answers into plot
        arguments as they arrived off attributes the next line read back. All of it is
        the Controller's now, and the plot happens in ``set_event_plot_data``.

        :param parameters: Dictionary containing eventfinder, filter, channels, and event indices.
        :type parameters: Dict[str, Any]
        :return: None
        :rtype: None
        """
        try:
            loader, eventfitter, data_filter, channels, events = (
                self._extract_plot_event_parameters(parameters)
            )
            self.validate_single_channel(channels)
            channel = channels[0]
        except (IndexError, ValueError) as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return

        filter_key = "" if data_filter in (None, "No Filter") else str(data_filter)
        self.event_plot_requested.emit(
            loader,
            eventfitter,
            channel,
            list(events or []),
            filter_key,
            bool(parameters.get("raw", False)),
        )

    @log(logger=logger)
    def set_event_plot_data(
        self,
        event_data: Sequence[npt.NDArray[np.float64]],
        labels: Sequence[str],
        num_events: int,
        vertical_lines: Sequence[Optional[List[float]]],
        horizontal_lines: Sequence[Optional[List[float]]],
        points: Sequence[Optional[List[Tuple[float, float]]]],
        vlabels: Sequence[Optional[Sequence[Optional[str]]]],
        hlabels: Sequence[Optional[Sequence[Optional[str]]]],
        plabels: Sequence[Optional[Sequence[Optional[str]]]],
        use_raw: bool,
    ) -> None:
        """
        Draw the events the Controller assembled, or report that there were none.

        The six feature sequences carry one entry per *event* while ``event_data`` and
        ``labels`` carry one to three per event, so this method must not try to line them
        up - the Controller built them aligned and ``_update_event_plot`` indexes them by
        event.

        :param event_data: the traces to draw, in order
        :type event_data: Sequence[npt.NDArray[np.float64]]
        :param labels: one label per trace, index-aligned with event_data
        :type labels: Sequence[str]
        :param num_events: how many events those traces belong to
        :type num_events: int
        :param vertical_lines: per event, its vertical feature lines or None
        :type vertical_lines: Sequence[Optional[List[float]]]
        :param horizontal_lines: per event, its horizontal feature lines or None
        :type horizontal_lines: Sequence[Optional[List[float]]]
        :param points: per event, its labelled feature points or None
        :type points: Sequence[Optional[List[Tuple[float, float]]]]
        :param vlabels: per event, the labels for its vertical lines or None
        :type vlabels: Sequence[Optional[Sequence[Optional[str]]]]
        :param hlabels: per event, the labels for its horizontal lines or None
        :type hlabels: Sequence[Optional[Sequence[Optional[str]]]]
        :param plabels: per event, the labels for its points or None
        :type plabels: Sequence[Optional[Sequence[Optional[str]]]]
        :param use_raw: whether unfiltered traces are among those being drawn
        :type use_raw: bool
        :return: None
        :rtype: None
        """
        if not len(event_data):
            self.add_text_to_display.emit(
                "No data available for plotting", self.__class__.__name__
            )
            return
        self._update_event_plot(
            event_data,
            labels,
            num_events,
            vertical_lines,
            horizontal_lines,
            points,
            vlabels,
            hlabels,
            plabels,
            use_raw=use_raw,
        )

    @log(logger=logger)
    def set_eventfitting_status(self, status: bool) -> None:
        """
        Set the internal event fitting status.

        :param status: Boolean indicating fitting completion status.
        :type status: bool
        """
        self.eventfitting_status = status

    @log(logger=logger)
    def set_num_events_allowed(self, num_events: int) -> None:
        """
        Set the maximum number of events allowed to be plotted.

        :param num_events: Number of events allowed.
        :type num_events: int
        """
        self.num_events_allowed = num_events

    @log(logger=logger)
    def _update_event_plot(
        self,
        event_data: Sequence[npt.NDArray[np.float64]],
        labels: Sequence[str],
        num_events: int,
        vertical_lines: Sequence[Optional[List[float]]],
        horizontal_lines: Sequence[Optional[List[float]]],
        points: Sequence[Optional[List[Tuple[float, float]]]],
        vlabels: Sequence[Optional[Sequence[Optional[str]]]],
        hlabels: Sequence[Optional[Sequence[Optional[str]]]],
        plabels: Sequence[Optional[Sequence[Optional[str]]]],
        use_raw: bool = False,
    ) -> None:
        """
        Update the event plot with raw data, annotations, and formatting.

        This method generates subplots for each event, displays time-series data,
        and optionally overlays vertical/horizontal lines and annotated points.

        :param event_data: List of 1D arrays containing current traces for each event.
        :type event_data: Sequence[npt.NDArray[np.float64]]
        :param labels: List of strings for each subplot's title.
        :type labels: Sequence[str]
        :param num_events: Total number of events to plot (i.e., number of subplots).
        :type num_events: int
        :param vertical_lines: List of lists of x-values for vertical line annotations per subplot.
        :type vertical_lines: Sequence[Optional[List[float]]]
        :param horizontal_lines: List of lists of y-values for horizontal line annotations per subplot.
        :type horizontal_lines: Sequence[Optional[List[float]]]
        :param points: List of lists of (x, y) coordinate tuples for marker points per subplot.
        :type points: Sequence[Optional[List[Tuple[float, float]]]]
        :param vlabels: One entry per subplot, each a list of labels for that subplot's vertical lines, or None if the fitter supplied no labels. Individual labels may also be None.
        :type vlabels: Sequence[Optional[Sequence[Optional[str]]]]
        :param hlabels: One entry per subplot, each a list of labels for that subplot's horizontal lines, or None if the fitter supplied no labels. Individual labels may also be None.
        :type hlabels: Sequence[Optional[Sequence[Optional[str]]]]
        :param plabels: One entry per subplot, each a list of labels for that subplot's points, or None if the fitter supplied no labels. Individual labels may also be None.
        :type plabels: Sequence[Optional[Sequence[Optional[str]]]]
        :param use_raw: Whether to plot/cache the raw (unfiltered) trace entries in event_data
            (labeled "Raw") alongside the filtered/fit ones. Entries so labeled are skipped
            entirely when this is False, regardless of whether the caller included them.
        :type use_raw: bool
        :return: None
        :rtype: None
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.figure.clear()
        self._clear_cache()

        # Get the current color cycle
        color_cycle = pl.rcParams["axes.prop_cycle"].by_key()["color"]

        # Filter out black (if black is in the cycle)
        colors_no_black = [
            c for c in color_cycle if c.lower() != "black" and c != "#000000"
        ]

        num_rows, num_cols = self._factors(num_events)

        j = 0
        for data, label in zip(event_data, labels):
            if "Raw" in label and not use_raw:
                # Bypass the raw (unfiltered) trace entirely when not requested,
                # instead of relying on the caller to have omitted it.
                continue
            if "Data" in label:
                features_plotted = False
                ax = self.figure.add_subplot(
                    num_rows, num_cols, j + 1
                )  # Create subplots in a grid
                ax.set_title(label)
                j += 1

            time = np.arange(len(data)) / self.plot_samplerate * 1e6
            should_plot = (
                "Fit" in label
                or "Raw" in label
                or "Data"
                in label  # always show Data (filtered if filter active, raw if not)
            )
            if should_plot:
                zorder = (
                    1 if "Raw" in label else 2
                )  # Raw below filtered data, filtered below Fit
                ax.plot(time, data / 1000, zorder=zorder)

            x_label = r"Time (us)"
            y_label = r"Current (nA)"

            self._update_cache(
                (time, label + " " + x_label), (data / 1000, label + " " + y_label)
            )

            if (j - 1) % num_cols == 0:
                ax.set_ylabel(y_label)
            labelnum = (num_rows - 1) * num_cols
            if num_events % num_cols > 0:
                labelnum -= num_cols - num_events % num_cols
            if (j - 1) >= labelnum:
                ax.set_xlabel(r"Time ($\mu s$)")

            if features_plotted is False:
                features_plotted = True

                # --- Vertical lines ---
                verticals = vertical_lines[j - 1]
                vertical_labels = vlabels[j - 1]
                color_idx = 0
                if verticals is not None:
                    # A fitter may supply features with no labels at all; the
                    # branch below already renders those unlabeled, so stand in
                    # a matching run of Nones rather than zipping against None.
                    if vertical_labels is None:
                        vertical_labels = [None] * len(verticals)
                    for line, line_label in zip(verticals, vertical_labels):
                        if line_label is None:
                            ax.axvline(x=line, color="black", linestyle="--")
                        else:
                            color = colors_no_black[color_idx % len(colors_no_black)]
                            ax.axvline(
                                x=line, linestyle="--", color=color, label=line_label
                            )
                            color_idx += 1

                # --- Horizontal lines ---
                horizontals = horizontal_lines[j - 1]
                horizontal_labels = hlabels[j - 1]
                color_idx = 0
                if horizontals is not None:
                    # A fitter may supply features with no labels at all; the
                    # branch below already renders those unlabeled, so stand in
                    # a matching run of Nones rather than zipping against None.
                    if horizontal_labels is None:
                        horizontal_labels = [None] * len(horizontals)
                    for line, line_label in zip(horizontals, horizontal_labels):
                        if line_label is None:
                            ax.axhline(y=line / 1000, color="black", linestyle="--")
                        else:
                            color = colors_no_black[color_idx % len(colors_no_black)]
                            ax.axhline(
                                y=line / 1000,
                                linestyle="--",
                                color=color,
                                label=line_label,
                            )
                            color_idx += 1

                # --- Points ---
                pts = points[j - 1]
                pt_labels = plabels[j - 1]
                color_idx = 0
                if pts is not None:
                    # A fitter may supply features with no labels at all; the
                    # branch below already renders those unlabeled, so stand in
                    # a matching run of Nones rather than zipping against None.
                    if pt_labels is None:
                        pt_labels = [None] * len(pts)
                    for (x, y), point_label in zip(pts, pt_labels):
                        if point_label is None:
                            ax.plot(
                                x, y / 1000, marker="x", color="black", markersize=10
                            )
                        else:
                            color = colors_no_black[color_idx % len(colors_no_black)]
                            ax.plot(
                                x,
                                y / 1000,
                                marker="x",
                                linestyle="None",
                                label=point_label,
                                color=color,
                                markersize=10,
                            )
                            color_idx += 1

                ax.grid(True)

        # Build a single shared legend from all axes, deduplicating by label
        all_handles = {}
        for ax in self.figure.get_axes():
            for handle, label in zip(*ax.get_legend_handles_labels()):
                if label not in all_handles:
                    all_handles[label] = handle

        if all_handles:
            num_entries = len(all_handles)
            fig_height = self.figure.get_size_inches()[1]
            # estimate how many entries fit comfortably at default font size (10pt)
            # roughly 0.20 inches per entry at 10pt
            entries_at_default = fig_height / 0.20
            if num_entries <= entries_at_default:
                font_size = 10  # plenty of space, use full size
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
    def _handle_fit_events(self, parameters: Dict[str, Any]) -> None:
        """
        Handle the fitting of events using the selected event fitter and data filter.

        :param parameters: Dictionary of parameters from the GUI controls.
        :type parameters: Dict[str, Any]
        """
        try:
            eventfitter, data_filter, channels = self._extract_event_fit_parameters(
                parameters
            )
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return
        if eventfitter is not None and channels is not None and data_filter is not None:
            # See RawDataView._handle_find_events: asked where the click arrives.
            if data_filter == "No Filter" and not self.confirm_unfiltered_run(
                "Event fitting"
            ):
                return
            self._start_eventfitter(eventfitter, data_filter, channels)

    @log(logger=logger)
    def _handle_commit_events(self, parameters: Dict[str, Any]) -> None:
        """
        Handle commit actions by triggering the selected writer to store events.

        :param parameters: Dictionary containing selected writer and channel info.
        :type parameters: Dict[str, Any]
        """
        try:
            writer, channels = self._extract_commit_event_parameters(parameters)
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return

        if writer is not None and channels is not None:
            # Step 4a: the write call itself is the Controller's.
            self.write_requested.emit(
                writer, channels if isinstance(channels, list) else [channels]
            )

    @log(logger=logger)
    def _start_eventfitter(
        self, eventfitter: str, data_filter: str, channels: Union[int, List[int]]
    ) -> None:
        """
        Ask the Controller which of these channels the fitter has already completed.

        Step 4a, and the same two-phase launch RawData's event finding uses: this method
        interleaved a plugin call with a question for the user, asking each channel's
        fitting status over the bus and prompting before redoing a finished channel. The
        prompt stays here and the call leaves, so the statuses go out, the answers come
        back, and the approved channels go out again. The reply arrives as
        ``set_fitting_statuses``.

        :param eventfitter: Identifier of the event fitter plugin.
        :type eventfitter: str
        :param data_filter: Identifier of the filter plugin to apply to the data.
        :type data_filter: str
        :param channels: Channel index, or list of integer channel indices.
        :type channels: Union[int, List[int]]
        :return: None
        :rtype: None
        """
        if not isinstance(channels, list):
            channels = [channels]

        filter_key = "" if data_filter in (None, "No Filter") else str(data_filter)
        self.fitting_statuses_requested.emit(eventfitter, channels, filter_key)

    @log(logger=logger)
    def set_fitting_statuses(
        self, eventfitter: str, statuses: List[Tuple[int, bool]], data_filter: str
    ) -> None:
        """
        Confirm any already-fitted channels, then ask for the approved ones to run.

        The per-channel prompt is kept exactly as it was, including that declining one
        channel skips only that channel. There are no stored ranges to look up here, so
        unlike RawData's equivalent nothing in this half can fail.

        :param eventfitter: the event fitter plugin's key
        :type eventfitter: str
        :param statuses: (channel, already_fitted) for each channel that answered
        :type statuses: List[Tuple[int, bool]]
        :param data_filter: the filter plugin's key, or "" for no filtering
        :type data_filter: str
        :return: None
        :rtype: None
        """
        approved: List[int] = []
        for channel, fitted in statuses:
            if fitted:
                reply = QMessageBox.question(
                    self,
                    "Confirmation",
                    f"Fitting was already completed in channel {channel}. Start over anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    continue
            approved.append(channel)

        if approved:
            self.fitting_requested.emit(eventfitter, approved, data_filter)

    @log(logger=logger)
    def _extract_plot_event_parameters(
        self, parameters: Dict[str, Any]
    ) -> Tuple[
        Optional[str], Optional[str], Optional[str], List[int], Optional[List[int]]
    ]:
        """
        Extract event plotting parameters from input.

        :param parameters: Input parameter dictionary.
        :type parameters: Dict[str, Any]
        :return: (loader, eventfitter, data_filter, channels, events)
        :rtype: Tuple[Optional[str], Optional[str], Optional[str], List[int], Optional[List[int]]]
        """
        loader = parameters.get("loader")
        eventfitter = parameters.get("eventfitter")
        data_filter = parameters.get("filter")
        channels = self._channels_from(parameters)
        events = parameters.get("event_index")
        return loader, eventfitter, data_filter, channels, events

    @log(logger=logger)
    def _extract_event_fit_parameters(
        self, parameters: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str], List[int]]:
        """
        Extract parameters used for event finding.

        :param parameters: Dictionary of parameters.
        :type parameters: Dict[str, Any]
        :return: (eventfitter, data_filter, channels)
        :rtype: Tuple[Optional[str], Optional[str], List[int]]
        """
        eventfitter = parameters.get("eventfitter")
        data_filter = parameters.get("filter")
        channels = self._channels_from(parameters)
        return eventfitter, data_filter, channels

    @log(logger=logger)
    def update_channels(self, channels: List[int]) -> None:
        """
        Update the channel list in the event analysis control widget.

        :param channels: List of available channel indices.
        :type channels: List[int]
        """
        self.eventAnalysisControls.update_channels(channels)
        self.logger.info("Updated channels in EventAnalysisTab")

    @log(logger=logger)
    def _handle_other_actions(
        self, action_name: str, parameters: Dict[str, Any]
    ) -> None:
        """
        Handle non-standard or plugin-specific actions that do not fall into predefined handlers.

        :param action_name: Action identifier.
        :type action_name: str
        :param parameters: Dictionary of parameters for the action.
        :type parameters: Dict[str, Any]
        """
        loader = parameters.get("loader")
        if loader and loader != "No Loader":
            self.loader_channels_requested.emit(loader)

    def get_walkthrough_steps(self) -> List[WalkthroughStep]:
        return [
            (
                "Event Analysis Tab",
                "Welcome to Event Analysis! Click the '+' button to load your event database.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.loaders_add_button],
            ),
            (
                "Event Analysis Tab",
                "Select the channel you'd like to work with from the dropdown menu.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.channel_comboBox],
            ),
            (
                "Event Analysis Tab",
                "Now, select one of your previously created filters from the list.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.filters_comboBox],
            ),
            (
                "Event Analysis Tab",
                "If you'd like to confirm you've loaded the correct event database, enter the range(s) or index(es) to plot.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.event_index_lineEdit],
            ),
            (
                "Event Analysis Tab",
                "Then, click 'Plot Events' to visualize the selected entries.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.plot_events_pushButton],
            ),
            (
                "Event Analysis Tab",
                "Use the arrows to quickly navigate between filtered/unfiltered events.",
                "EventAnalysisView",
                lambda: [
                    self.eventAnalysisControls.left_arrow_button,
                    self.eventAnalysisControls.right_arrow_button,
                ],
            ),
            (
                "Event Analysis Tab",
                "By default the raw trace is shown. When a filter is active, check RAW to also display the unfiltered signal alongside the filtered trace. If a fitter has been run, the fit trace will also appear.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.raw_checkbox],
            ),
            (
                "Event Analysis Tab",
                "Ready to fit the events? Click the '+' button to add a fitter.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.eventfitters_add_button],
            ),
            (
                "Event Analysis Tab",
                "Click 'Fit Events' to begin. Once complete, fitted and rejected events will appear on the side panel.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.fit_events_pushButton],
            ),
            (
                "Event Analysis Tab",
                "You can now enter new indices to inspect the fitted results.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.event_index_lineEdit],
            ),
            (
                "Event Analysis Tab",
                "Click 'Plot Events' again to view the newly selected fitter events.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.plot_events_pushButton],
            ),
            (
                "Event Analysis Tab",
                "Satisfied with the fits? Add a writer by clicking the '+' icon.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.writers_add_button],
            ),
            (
                "Event Analysis Tab",
                "Click 'Commit' to save the results to your event database.",
                "EventAnalysisView",
                lambda: [self.eventAnalysisControls.commit_btn],
            ),
        ]

    def get_current_view(self) -> str:
        return "EventAnalysisView"
