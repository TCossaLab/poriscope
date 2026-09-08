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
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
    override,
)

import numpy as np
import numpy.typing as npt
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from poriscope.plugins.analysistabs.utils.rawdatacontrols import RawDataControls
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventTabView import MetaEventTabView
from poriscope.views.widgets.time_widget import TimeWidget
from poriscope.views.widgets.walkthrough_mixin import (
    WalkthroughStep,
)


@inherit_docstrings
class RawDataView(MetaEventTabView):
    """
    Subclass of MetaEventTabView for visualizing raw signal data and PSD plots.

    Handles plot rendering, signal responses, and interactions with readers, filters, and event finders.
    """

    #: Asks the Controller for the baseline statistics of the channels about to be
    #: plotted. Step 4c introduced it: the fitting moved to RawDataModel, and this
    #: is Decision B's command path to it. The answer arrives as the
    #: baseline_stats argument of update_plot.
    baseline_stats_requested = Signal(object, list, object)

    #: Asks the Controller for a reader's channel list. Step 4a replaced a
    #: ``global_signal`` emit whose answer came back seven hops later through
    #: ``update_channels``; the answer now arrives one hop later, and a reader that
    #: cannot be read is reported instead of failing silently inside the dispatcher.
    reader_channels_requested = Signal(str)

    #: Asks the Controller to load a trace and optionally filter it, for plotting.
    #: reader, channels, start, length, filter key ("" for none), baseline wanted.
    #: The answer arrives as ``set_trace_data``.
    trace_data_requested = Signal(str, list, float, float, str, bool)

    #: The same request, for the PSD path. Separate rather than a mode flag so each
    #: intent names what it is for and carries only what that tail needs. The answer
    #: arrives as ``set_trace_for_psd``.
    psd_data_requested = Signal(str, list, float, float, str)

    #: Asks the Controller for one channel's events, ready to plot. eventfinder,
    #: channel, event indices, filter key ("" for none). The Controller checks the
    #: finder's state, bounds the indices, resolves the filter and loads each event;
    #: the answer arrives as ``set_event_plot_data``.
    event_plot_requested = Signal(str, int, list, str)

    logger = logging.getLogger(__name__)
    calculate_psd = Signal(list, float)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """Initialize the RawDataView-specific attributes."""

        self.analysis_time_limits: Dict[str, Dict[int, Dict[str, Any]]] = {}

    @log(logger=logger)
    def _build_controls(self) -> RawDataControls:
        """
        Build the tab's controls panel and keep it under this tab's own name.

        ``MetaView._set_control_area`` connects it and places it in the layout; the
        named attribute is kept because it is used throughout this tab.

        :return: the controls panel
        :rtype: RawDataControls
        """
        self.rawdatacontrols = RawDataControls()
        return self.rawdatacontrols

    @log(logger=logger)
    def _factors(self, n: int) -> Tuple[int, int]:
        """
        Determine the factor pair (rows, cols) closest to a square layout.

        :param n: Total number of plots.
        :type n: int
        :return: (rows, columns) representing subplot grid dimensions.
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
        Open a dialog to save a CSV file.

        :return: Selected file path, or an empty string if cancelled.
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
    def update_plot(
        self,
        data: Sequence[npt.NDArray[np.float64]],
        channels: Sequence[int],
        start: float = 0,
        baseline_stats: Optional[List[Optional[Tuple[float, float, float]]]] = None,
    ) -> None:
        """
        Update the plot area with the provided data across multiple channels in a grid layout.

        :param data: One array of current samples per channel.
        :type data: Sequence[npt.NDArray[np.float64]]
        :param channels: List of channel identifiers corresponding to the data.
        :type channels: Sequence[int]
        :param start: Time offset added to the plotted time axis, in seconds.
        :type start: float
        :param baseline_stats: Per-channel (amplitude, mean, stdev) from the Model, index-aligned with data, or None to draw no baseline overlay at all. An individual entry may be None where that channel's fit failed.
        :type baseline_stats: Optional[List[Optional[Tuple[float, float, float]]]]
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.figure.clear()
        self._clear_cache()

        num_channels = len(channels)

        num_rows, num_cols = self._factors(num_channels)

        for i, (channel_data, channel) in enumerate(zip(data, channels)):
            ax = self.figure.add_subplot(
                num_rows, num_cols, i + 1
            )  # Create subplots in a grid
            time = np.arange(len(channel_data)) / self.plot_samplerate + float(start)
            ax.plot(time, channel_data / 1000, zorder=1)

            # Computed by RawDataModel since Step 4c and handed over by the
            # Controller. A None entry is a channel whose fit failed, which the
            # Controller has already logged - the trace is still drawn, without a band.
            stats = baseline_stats[i] if baseline_stats is not None else None
            if stats is not None:
                amp, mean, std = stats
                if True:
                    # Add green rectangle for mean ± 3*std
                    ax.axhspan(
                        mean - 3 * std,
                        mean + 3 * std,
                        xmin=0,
                        xmax=1,
                        color="green",
                        alpha=0.2,
                        zorder=2,
                    )

                    # Add red horizontal line at the mean
                    ax.axhline(mean, color="red", linestyle="--", linewidth=1, zorder=3)

                    # Add label with mean and std
                    label = f"Mean = {mean:.2f} nA\nStd = {std:.2f} nA"
                    ax.text(
                        0.98,
                        0.95,
                        label,
                        transform=ax.transAxes,
                        verticalalignment="top",
                        horizontalalignment="right",
                        fontsize=8,
                        bbox=dict(facecolor="white", alpha=0.6, edgecolor="gray"),
                        zorder=4,
                    )

            y_label = r"Current (nA)"
            x_label = r"Time (s)"
            dataset_label = f"Channel {channel}"

            self._update_cache(
                (time, dataset_label + " " + x_label),
                (channel_data / 1000, dataset_label + " " + y_label),
            )

            if i % num_cols == 0:
                ax.set_ylabel(y_label)
            labelnum = (num_rows - 1) * num_cols
            if num_channels % num_cols > 0:
                labelnum -= num_cols - num_channels % num_cols
            if i >= labelnum:
                ax.set_xlabel(x_label)
            ax.set_title(dataset_label)
            ax.grid(True)
        self.figure.set_layout_engine("constrained")
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def update_psd(
        self,
        psd_data: Sequence[npt.NDArray[np.float64]],
        rms_data: Sequence[npt.NDArray[np.float64]],
        frequency: npt.NDArray[np.float64],
        channels: Sequence[int],
    ) -> None:
        """
        Update the plot area with the provided psd and frequency data across multiple channels in a grid layout.

        :param psd_data: Power spectral density values, one array for each channel.
        :type psd_data: Sequence[npt.NDArray[np.float64]]
        :param rms_data: Integrated RMS noise values corresponding to ``psd_data``, one array for each channel.
        :type rms_data: Sequence[npt.NDArray[np.float64]]
        :param frequency: Frequency axis shared across all channels.
        :type frequency: npt.NDArray[np.float64]
        :param channels: List of channel identifiers corresponding to the data.
        :type channels: Sequence[int]
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.figure.clear()
        self._clear_cache()
        num_channels = len(channels)

        # Determine the layout of the subplots: square root of the number of channels rounded up
        num_rows, num_cols = self._factors(num_channels)

        for i, (psd, rms, channel) in enumerate(zip(psd_data, rms_data, channels)):
            max_index = np.searchsorted(rms, 0.999 * rms[-1], side="right")
            max_freq = 10 ** np.ceil(np.log10(frequency[max_index]))
            psd_min = 10 ** (np.floor(np.log10(np.min(psd[:max_index])) * 2) / 2)
            psd_max = 10 ** (np.ceil(np.log10(np.max(psd)) * 2) / 2)

            ax = self.figure.add_subplot(
                num_rows, num_cols, i + 1
            )  # Create subplots in a grid
            ax2 = ax.twinx()

            ax.set_xlim(1, max_freq)
            ax.set_ylim(psd_min, psd_max)

            ax.loglog(frequency, psd, "b-")
            ax2.semilogx(frequency, rms, "r")

            x_label = r"Frequency (Hz)"
            y1_label = r"Spectral Power (pA^2/Hz)"
            y2_label = r"RMS Noise (pA)"
            dataset_label = f"Channel {channel}"

            self._update_cache(
                (frequency, dataset_label + " " + x_label),
                (psd, dataset_label + " " + y1_label),
            )
            self._update_cache(
                (frequency, dataset_label + " " + x_label),
                (rms, dataset_label + " " + y2_label),
            )

            if i % num_cols == 0:
                ax.set_ylabel(r"Spectral Power $\left(\frac{pA^2}{Hz}\right)$")
            if i % num_cols == num_cols - 1:
                ax2.set_ylabel(y2_label)
            labelnum = (num_rows - 1) * num_cols
            if num_channels % num_cols > 0:
                labelnum -= num_cols - num_channels % num_cols
            if i >= labelnum:
                ax.set_xlabel(x_label)

            ax.set_title(dataset_label)
            ax.grid(True)
        self.figure.set_layout_engine("constrained")
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def update_plot_data(self, data: Optional[Any] = None) -> None:
        """
        Update the stored plot data for future use.

        :param data: Data dictionary or raw array to store.
        :type data: Optional[Any]
        """
        self.logger.debug(f"Received data for plotting: {data}")
        if not isinstance(data, dict):
            self.plot_data = data
        else:
            self.plot_data = data[
                "data"
            ]  # event data now returns a dict - this should be refactored to handle this explicitly

    @log(logger=logger)
    def update_plot_samplerate(self, samplerate: float) -> None:
        """
        Update the sampling rate used for plotting.

        :param samplerate: Sampling frequency in Hz.
        :type samplerate: float
        """
        self.logger.debug(f"Received sampling rate: {samplerate}")
        self.plot_samplerate = samplerate

    @log(logger=logger)
    def register_eventfinder_channels(
        self, channels_by_finder: Mapping[str, Sequence[int]]
    ) -> None:
        """
        Give each event finder not seen before a default time range for every channel.

        Step 4a: the channel lookup this used to do itself is now ``RawDataController``'s,
        which resolves every finder up front and hands the answers down. A finder absent
        from ``channels_by_finder``, or present with no channels, is left unregistered so
        the next push retries it - the same "register only on success" rule the emit
        version had, minus the emit-then-read and its clear-before-emit guard.

        A finder already in ``analysis_time_limits`` keeps the ranges the user set on it;
        only genuinely new finders get defaults.

        :param channels_by_finder: channels per event finder, for finders that answered
        :type channels_by_finder: Mapping[str, Sequence[int]]
        :return: None
        :rtype: None
        """
        for finder, channels in channels_by_finder.items():
            if finder in self.analysis_time_limits or not channels:
                continue
            self.analysis_time_limits[finder] = {
                ch: {"start": 0, "end": 0} for ch in channels
            }

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
            readers = available_plugins.get("MetaReader", [])
            filters = available_plugins.get("MetaFilter", [])
            writers = available_plugins.get("MetaWriter", [])
            eventfinders = available_plugins.get("MetaEventFinder", [])

            self.rawdatacontrols.update_readers(readers)
            self.rawdatacontrols.update_filters(filters)
            self.rawdatacontrols.update_writers(writers)
            self.rawdatacontrols.update_eventfinders(eventfinders)

            self.logger.info("ComboBoxes updated with available readers and filters")
        except Exception as e:
            self.logger.info(f"Updating ComboBoxes failed: {repr(e)}")

    @log(logger=logger)
    @Slot(str, str, tuple)
    def handle_parameter_change(
        self, submodel_name: str, action_name: str, args: tuple
    ) -> None:
        """
        Handle parameter changes triggered by RawDataControls and dispatch the corresponding action.

        :param submodel_name: Name of the submodel triggering the action.
        :type submodel_name: str
        :param action_name: Action identifier string.
        :type action_name: str
        :param args: Tuple of arguments passed with the signal.
        :type args: tuple
        """
        parameters = args[0]

        if action_name == "shift_trace_backward":
            self._shift_range_and_update_trace(parameters, direction="left")
        elif action_name == "load_data_and_update_plot":
            self._handle_load_data_and_update_plot(parameters)
        elif action_name == "shift_trace_forward":
            self._shift_range_and_update_trace(parameters, direction="right")
        elif action_name == "get_baseline_stats":
            self._handle_load_data_and_update_plot(parameters, baseline=True)
        elif action_name == "load_data_and_update_psd":
            self._handle_load_data_and_update_psd(parameters)
        elif action_name == "timer":
            self._handle_timer(parameters)
        elif action_name == "find_events":
            self._handle_find_events(parameters)
        elif action_name == "shift_events_backward":
            self._shift_range_and_update_plot(parameters, direction="left")
        elif action_name == "plot_events":
            self._handle_plot_events(parameters)
        elif action_name == "shift_events_forward":
            self._shift_range_and_update_plot(parameters, direction="right")
        elif action_name == "commit_events":
            self._handle_commit_events(parameters)
        elif action_name == "export_plot_data":
            self.export_plot_data.emit()
        else:
            self._handle_other_actions(action_name, parameters)

    @log(logger=logger)
    def _handle_timer(self, parameters: Dict[str, Any]) -> None:
        """
        Open a time range selection dialog for a given event finder and update the internal time limits.

        :param parameters: Dictionary containing the 'eventfinder' key.
        :type parameters: Dict[str, Any]
        """
        finder = parameters["eventfinder"]
        if finder != "No Eventfinder":
            time_widget = TimeWidget(self.analysis_time_limits[finder])
            time_widget.exec()
            result = time_widget.get_result()
            if result is not None:
                self.analysis_time_limits[finder] = result

    @log(logger=logger)
    def _shift_range_and_update_plot(
        self, parameters: Dict[str, Any], direction: str
    ) -> None:
        """
        Shift selected event index ranges left or right and update the plot accordingly.

        :param parameters: Dictionary containing current event plotting parameters.
        :type parameters: Dict[str, Any]
        :param direction: Direction to shift ('left' or 'right').
        :type direction: str
        """
        try:
            eventfinder, filter_name, selected_channels, event_indices = (
                self._extract_plot_event_parameters(parameters)
            )
            self.logger.debug(
                f"Channels received before validation: {selected_channels}"
            )
            self.validate_single_channel(selected_channels)
            selected_channels[0]
        except ValueError as e:
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
            # The log line is kept verbatim: an EventAnalysis e2e test asserts on this
            # exact text. What was missing is the user-visible half - the shift correctly
            # declines to go below event 0, but said so only on the console.
            self.logger.warning("Indices must be positive")
            self.add_text_to_display.emit(
                "Cannot shift further: event indices cannot go below 0",
                self.__class__.__name__,
            )
            return

        # Proceed with valid shift
        new_params = parameters.copy()
        new_params["event_index"] = expanded
        self.logger.debug(f"Updated parameters for plot: {new_params}")

        self._handle_plot_events(new_params)
        self.logger.debug(
            f"Shifting complete. Updating input field to: {new_event_str}"
        )
        self.rawdatacontrols.set_event_index_input(new_event_str)

    def _get_event_index_text(self) -> str:
        """
        Get the event index input from the UI.

        :return: The current text from the event index input field.
        :rtype: str
        """
        return self.rawdatacontrols.event_index_lineEdit.text().strip()

    @log(logger=logger)
    def _handle_plot_events(self, parameters: Dict[str, Any]) -> None:
        """
        Ask the Controller for the selected events, ready to plot.

        Step 4a: this used to run five bus round trips itself - the finder's status and
        event count, the filter callable, the samplerate, then one load per event - each
        one an emit whose answer arrived on an attribute the next line read back. All
        five are the Controller's now, and the plot happens in ``set_event_plot_data``.

        :param parameters: Dictionary containing eventfinder, filter, channels, and event indices.
        :type parameters: Dict[str, Any]
        :return: None
        :rtype: None
        """
        try:
            eventfinder, data_filter, channels, events = (
                self._extract_plot_event_parameters(parameters)
            )
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return
        if len(channels) > 1:
            self.logger.warning(
                "Unable to plot events from multiple channels, select only one"
            )
            return

        self.event_plot_requested.emit(
            eventfinder, channels[0], list(events or []), self._filter_key(parameters)
        )

    @log(logger=logger)
    def set_event_plot_data(
        self,
        event_data: Sequence[npt.NDArray[np.float64]],
        event_indices: Sequence[int],
    ) -> None:
        """
        Plot the events the Controller loaded, or report that there were none.

        ``event_indices`` is the surviving list: an event the finder could not supply is
        dropped by the Controller, so the traces and the indices labelling them stay
        aligned without this method having to prune anything.

        :param event_data: one array of samples per surviving event
        :type event_data: Sequence[npt.NDArray[np.float64]]
        :param event_indices: the event indices that produced data, index-aligned with event_data
        :type event_indices: Sequence[int]
        :return: None
        :rtype: None
        """
        if not len(event_data):
            self.add_text_to_display.emit(
                "No data available for plotting", self.__class__.__name__
            )
            return
        self._update_event_plot(event_data, event_indices)

    @log(logger=logger)
    def _start_writer(self, writer: str, channels: Union[int, List[int]]) -> None:
        """
        Start a writer plugin to commit events for the specified channels.

        :param writer: Identifier for the writer plugin.
        :type writer: str
        :param channels: Channel index, or list of channel indices.
        :type channels: Union[int, List[int]]
        """
        if not isinstance(channels, list):
            channels = [channels]
        try:
            for channel in channels:
                write_events_args = (channel,)
                # Emit the signal with the correct handler name for when the data is ready
                ret_args = (channel, writer, "MetaWriter")
                self.global_signal.emit(
                    "MetaWriter",
                    writer,
                    "commit_events",
                    write_events_args,
                    "set_generator",
                    ret_args,
                )
        except (IndexError, ValueError) as e:
            self.logger.error(
                f"Unable to set up writer {writer} for channel {channel}: {repr(e)}"
            )
        else:
            self.run_generators.emit(writer)

    @log(logger=logger)
    def set_num_events_allowed(self, num_events: int) -> None:
        """
        Set the number of events available for display.

        :param num_events: Maximum valid event index + 1.
        :type num_events: int
        """
        self.num_events_allowed = num_events

    @log(logger=logger)
    def set_eventfinding_status(self, status: bool) -> None:
        """
        Set the current event finding status.

        :param status: Whether event finding is complete.
        :type status: bool
        """
        self.eventfinding_status = status

    @log(logger=logger)
    def _update_event_plot(
        self,
        event_data: Sequence[npt.NDArray[np.float64]],
        event_indices: Sequence[int],
    ) -> None:
        """
        Plot the event data in a grid that gets as close to square as possible

        :param event_data: a list of event data to plot in a grid
        :type event_data: Sequence[npt.NDArray[np.float64]]
        :param event_indices: the indices of the events to plot
        :type event_indices: Sequence[int]
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.figure.clear()
        self._clear_cache()

        num_events = len(event_indices)
        num_rows, num_cols = self._factors(num_events)

        for i, (data, event) in enumerate(zip(event_data, event_indices)):
            ax = self.figure.add_subplot(
                num_rows, num_cols, i + 1
            )  # Create subplots in a grid
            time = np.arange(len(data)) / self.plot_samplerate * 1e6
            ax.plot(time, data / 1000)

            x_label = r"Time (us)"
            y_label = r"Current (nA)"
            dataset_label = f"Event {event}"

            self._update_cache(
                (time, dataset_label + " " + x_label),
                (data / 1000, dataset_label + " " + y_label),
            )

            if i % num_cols == 0:
                ax.set_ylabel(y_label)
            labelnum = (num_rows - 1) * num_cols
            if num_events % num_cols > 0:
                labelnum -= num_cols - num_events % num_cols
            if i >= labelnum:
                ax.set_xlabel(r"Time ($\mu s$)")
            ax.set_title(dataset_label)
            ax.grid(True)
        self.figure.set_layout_engine("constrained")
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def _handle_find_events(self, parameters: Dict[str, Any]) -> None:
        """
        Handle the initiation of the event finding process using the given parameters.

        :param parameters: Dictionary containing eventfinder, filter, and channels.
        :type parameters: Dict[str, Any]
        """
        self.logger.debug(
            "Starting to handle find events with parameters: %s", parameters
        )
        try:
            eventfinder, data_filter, channels = self._extract_event_parameters(
                parameters
            )
            self.logger.info("Event parameters extracted successfully.")
        except ValueError as e:
            self.logger.error("Parameter extraction failed: %s", repr(e))
            return

        if eventfinder is not None and channels is not None and data_filter is not None:
            # Asked at the intent boundary rather than inside _start_eventfinder: this is
            # where the user's click arrives, and it keeps the confirmation out of the
            # mechanism that the characterization suite drives directly.
            if data_filter == "No Filter" and not self.confirm_unfiltered_run(
                "Event finding"
            ):
                return
            self.logger.info("Valid parameters found: Starting event finder.")

            self._start_eventfinder(eventfinder, data_filter, channels)
        else:
            self.logger.warning(
                "Missing or invalid parameters: eventfinder=%s, channels=%s, data_filter=%s",
                eventfinder,
                channels,
                data_filter,
            )
            return
        self.logger.debug("Event finding process initiated.")

    @log(logger=logger)
    def _handle_commit_events(self, parameters: Dict[str, Any]) -> None:
        """
        Handle committing of found events to the selected writer plugin.

        :param parameters: Dictionary containing writer and channels.
        :type parameters: Dict[str, Any]
        """
        try:
            writer, channels = self._extract_commit_event_parameters(parameters)
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return

        if writer is not None and channels is not None:
            self._start_writer(writer, channels)

    @log(logger=logger)
    def _start_eventfinder(
        self, eventfinder: str, data_filter: str, channels: Union[int, List[int]]
    ) -> None:
        """
        Start the event finding operation on the specified channels with an optional filter.

        :param eventfinder: Identifier for the event finder plugin.
        :type eventfinder: str
        :param data_filter: Identifier for the filter plugin, or 'No Filter'.
        :type data_filter: str
        :param channels: Channel index, or list of channel indices, to run the event finder on.
        :type channels: Union[int, List[int]]
        :raises Exception: If setting up the data filter fails.
        """
        self.logger.debug(
            "Starting event finder with eventfinder=%s, data_filter=%s, channels=%s",
            eventfinder,
            data_filter,
            channels,
        )

        if not isinstance(channels, list):
            self.logger.warning("Channels parameter is not a list, converting to list.")
            channels = [channels]

        try:
            self.data_filter = None
            data_filter_args = ()

            if data_filter != "No Filter":
                self.logger.info("Applying data filter: %s", data_filter)
                self.global_signal.emit(
                    "MetaFilter",
                    data_filter,
                    "get_callable_filter",
                    data_filter_args,
                    "set_event_filter",
                    (),
                )
            else:
                self.logger.info("No data filter applied.")
        except Exception as e:
            self.logger.error("Error while setting up the data filter: %s", repr(e))
            raise
        else:
            try:
                for channel in channels:
                    # Check status before launching
                    self.global_signal.emit(
                        "MetaEventFinder",
                        eventfinder,
                        "get_eventfinding_status",
                        (channel,),
                        "relay_eventfinding_status",
                        (),
                    )

                    if self.eventfinding_status is True:
                        reply = QMessageBox.question(
                            self,
                            "Confirmation",
                            f"Event finding was already completed in channel {channel}. Start over anyway?",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No,
                        )
                        if reply == QMessageBox.No:
                            continue  # Skip this channel

                    channel_limits = self.analysis_time_limits[eventfinder][channel]

                    # Get list of ranges
                    if "ranges" in channel_limits:
                        ranges = list(
                            channel_limits["ranges"]
                        )  # Copy to avoid mutation
                    else:
                        start = channel_limits.get("start", 0.0)
                        end = channel_limits.get("end", 0.0) or 0.0
                        ranges = [(start, end)]

                    self.logger.info(
                        "Found %d range(s) for channel %s: %s",
                        len(ranges),
                        channel,
                        ranges,
                    )

                    # Prepare args: ONE call to find_events per channel
                    find_events_args = (
                        channel,
                        ranges,
                        1.0,
                        self.data_filter,
                    )  # ranges is a list of (start, end)
                    ret_args = (channel, eventfinder, "MetaEventFinder")  # unchanged

                    self.logger.info(
                        "Emitting bundled find_events for channel %s with %d range(s)",
                        channel,
                        len(ranges),
                    )
                    self.global_signal.emit(
                        "MetaEventFinder",
                        eventfinder,
                        "find_events",
                        find_events_args,
                        "set_generator",
                        ret_args,
                    )

                self.logger.info(
                    "All channels processed. Triggering run_generators for eventfinder=%s",
                    eventfinder,
                )
                self.run_generators.emit(eventfinder)

            except (IndexError, ValueError) as e:
                self.logger.error(
                    "Failed to set up generators for eventfinder=%s: %s",
                    eventfinder,
                    repr(e),
                )

    @log(logger=logger)
    def _extract_plot_event_parameters(
        self, parameters: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str], List[int], Optional[List[int]]]:
        """
        Extract event plotting parameters from input.

        :param parameters: Input parameter dictionary.
        :type parameters: Dict[str, Any]
        :return: (eventfinder, data_filter, channels, events)
        :rtype: Tuple[Optional[str], Optional[str], List[int], Optional[List[int]]]
        """
        eventfinder = parameters.get("eventfinder")
        data_filter = parameters.get("filter")
        channels = [int(ch) for ch in parameters["channel"]]
        events = parameters.get("event_index")
        return eventfinder, data_filter, channels, events

    @log(logger=logger)
    def _extract_event_parameters(
        self, parameters: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str], List[int]]:
        """
        Extract parameters used for event finding.

        :param parameters: Dictionary of parameters.
        :type parameters: Dict[str, Any]
        :return: (eventfinder, data_filter, channels)
        :rtype: Tuple[Optional[str], Optional[str], List[int]]
        """
        eventfinder = parameters.get("eventfinder")
        data_filter = parameters.get("filter")
        channels = [int(ch) for ch in parameters["channel"]]
        return eventfinder, data_filter, channels

    @log(logger=logger)
    def _shift_range_and_update_trace(
        self, parameters: Dict[str, Any], direction: str
    ) -> None:
        """
        Shift numeric range left or right and update the plot and GUI input.

        :param parameters: Dictionary containing current trace plotting parameters.
        :type parameters: Dict[str, Any]
        :param direction: Direction to shift ('left' or 'right').
        :type direction: str
        """

        # Extract and validate parameters
        try:
            reader, channels, start, length = self._extract_plot_parameters(parameters)
        except ValueError as e:
            self.logger.error(f"Failed to extract plot parameters: {repr(e)}")
            return

        if direction not in ("left", "right"):
            self.logger.error(f"Invalid direction: {direction}")
            return

        # Compute original range
        start = start
        length = length
        end = start + length

        original_range = (start, end)
        self.logger.debug(f"Original range: {original_range}")

        # Shift the range
        offset = 0
        shifted_ranges = self._shift_ranges([original_range], direction, offset)
        self.logger.debug(f"Shifted ranges: {shifted_ranges}")

        # Extract new start and end
        new_start, new_end = shifted_ranges[0]
        new_length = new_end - new_start

        # Prevent negative start
        if new_start < 0:
            self.logger.warning("Ranges must be positive")
            new_start = start
            new_length = length
        else:
            self.logger.debug(
                f"Shifting range {direction}: new start={new_start}, length={new_length}"
            )

        # Update GUI range entry box
        self.rawdatacontrols.set_range_inputs(new_start, new_length)

        new_params = parameters.copy()
        new_params["start_time"] = new_start

        self._handle_load_data_and_update_plot(new_params)

    @log(logger=logger)
    def _handle_load_data_and_update_plot(
        self, parameters: Dict[str, Any], baseline: bool = False
    ) -> None:
        """
        Handle data loading and update the main signal plot.

        This method:
        - Extracts plot parameters (reader, channels, start, length)
        - Loads data using the specified reader for each channel
        - Optionally applies a filter to the data
        - Updates the main plot area with the retrieved data

        :param parameters: Dictionary containing reader, channels, start time, length, and optional filter.
        :type parameters: Dict[str, Any]
        :param baseline: If True, overlay baseline mean/std statistics on the plot.
        :type baseline: bool
        """
        # Extract and validate parameters
        try:
            reader, channels, start, length = self._extract_plot_parameters(parameters)
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return

        # Load data and update plot
        if self._validate_plot_parameters(reader, channels, start, length):
            # Step 4a: loading and filtering are the Controller's now, so the plot
            # happens in set_trace_data when it hands the channels back.
            self.trace_data_requested.emit(
                reader, channels, start, length, self._filter_key(parameters), baseline
            )
        else:
            self.logger.error("Invalid parameters for plotting data")

    @log(logger=logger)
    def _filter_key(self, parameters: Dict[str, Any]) -> str:
        """
        Read the selected filter out of a parameter dict as a plain key.

        The controls panel reports "no filter" as either a missing key or the literal
        ``"No Filter"``; both collapse to the empty string here so the intent signals can
        carry a plain ``str`` rather than an ``object``.

        :param parameters: the parameter dict the controls panel emitted
        :type parameters: Dict[str, Any]
        :return: the filter plugin's key, or "" if none is selected
        :rtype: str
        """
        data_filter = parameters.get("filter")
        if not data_filter or data_filter == "No Filter":
            return ""
        return str(data_filter)

    @log(logger=logger)
    def set_trace_data(
        self,
        data_list: Sequence[npt.NDArray[np.float64]],
        channels: Sequence[int],
        start: float,
        baseline: bool,
    ) -> None:
        """
        Plot the trace the Controller loaded, or report that there was none.

        Step 4a: this is the tail of ``_handle_load_data_and_update_plot``, which used to
        run inline after a bus round trip per channel. ``channels`` is the surviving list
        - a channel the reader could not supply is dropped by the Controller, so the two
        stay index-aligned without this method having to prune anything.

        :param data_list: one array per surviving channel
        :type data_list: Sequence[npt.NDArray[np.float64]]
        :param channels: the channels that produced data, index-aligned with data_list
        :type channels: Sequence[int]
        :param start: the start time being plotted from
        :type start: float
        :param baseline: whether the user asked for the baseline band
        :type baseline: bool
        :return: None
        :rtype: None
        """
        if not len(data_list):
            self.add_text_to_display.emit(
                "No data available for plotting", self.__class__.__name__
            )
            return
        if baseline:
            # The fitting is the Model's since Step 4c, so the plot happens
            # when the Controller hands the statistics back.
            self.baseline_stats_requested.emit(data_list, channels, start)
        else:
            self.update_plot(data_list, channels, start)

    @log(logger=logger)
    def _handle_load_data_and_update_psd(self, parameters: Dict[str, Any]) -> None:
        """
        Handle data loading and update the PSD (Power Spectral Density) plot.

        This method extracts plotting parameters, loads data from the reader,
        optionally applies a filter, emits the signal to calculate PSD, and updates the PSD plot.

        :param parameters: Dictionary containing reader, channels, start time, length, and optional filter.
        :type parameters: Dict[str, Any]
        """
        try:
            reader, channels, start, length = self._extract_plot_parameters(parameters)
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return

        # Load data and update plot
        if self._validate_plot_parameters(reader, channels, start, length):
            # Step 4a: as for the trace path, the loading is the Controller's and the
            # PSD happens in set_trace_for_psd.
            self.psd_data_requested.emit(
                reader, channels, start, length, self._filter_key(parameters)
            )
        else:
            self.logger.error("Invalid parameters for plotting data")

    @log(logger=logger)
    def set_trace_for_psd(
        self,
        data_list: Sequence[npt.NDArray[np.float64]],
        channels: Sequence[int],
    ) -> None:
        """
        Compute and draw the PSD of the trace the Controller loaded.

        Step 4a moved only the *loading* out of this path. The PSD computation below is
        unchanged and is deliberately left as it was: ``calculate_psd`` is an intent
        signal to this tab's own Controller rather than a ``global_signal`` bus call, and
        it is Decision B's template working correctly, so it is not 4a's business. The
        read-back off ``psd_kept_indices`` and friends is safe for the same reason it
        always was - the connection is direct, so ``set_psd`` has already run.

        :param data_list: one array per surviving channel
        :type data_list: Sequence[npt.NDArray[np.float64]]
        :param channels: the channels that produced data, index-aligned with data_list
        :type channels: Sequence[int]
        :return: None
        :rtype: None
        """
        if not len(data_list):
            self.add_text_to_display.emit(
                "No data available for psd calculation", self.__class__.__name__
            )
            return
        self.calculate_psd.emit(list(data_list), self.plot_samplerate)
        psd_channels = [channels[i] for i in self.psd_kept_indices]
        self.update_psd(self.Pxx_list, self.rms_list, self.psd_frequency, psd_channels)

    @log(logger=logger)
    def set_psd(
        self,
        Pxx_list: List[npt.NDArray[np.float64]],
        rms_list: List[npt.NDArray[np.float64]],
        frequency: Optional[npt.NDArray[np.float64]],
        kept_indices: List[int],
    ) -> None:
        """
        Set the PSD and RMS lists for visualization.

        :param Pxx_list: Power spectral density data, one array per kept channel.
        :type Pxx_list: List[npt.NDArray[np.float64]]
        :param rms_list: RMS noise data, one array per kept channel.
        :type rms_list: List[npt.NDArray[np.float64]]
        :param frequency: Frequency axis data, or None if no channel was processed.
        :type frequency: Optional[npt.NDArray[np.float64]]
        :param kept_indices: Indices into the channel list passed to calculate_psd that were successfully processed, since some channels may have been skipped.
        :type kept_indices: List[int]
        """
        self.Pxx_list = Pxx_list
        self.rms_list = rms_list
        self.psd_frequency = frequency
        self.psd_kept_indices = kept_indices

    @log(logger=logger)
    def _extract_plot_parameters(
        self, parameters: Dict[str, Any]
    ) -> Tuple[Optional[str], List[int], float, float]:
        """
        Extract reader, channel, start time, and length from parameters.

        :param parameters: Parameter dictionary.
        :type parameters: Dict[str, Any]
        :return: (reader, channels, start, length)
        :rtype: Tuple[Optional[str], List[int], float, float]
        """
        reader = parameters.get("reader")
        channels = [int(ch) for ch in parameters["channel"]]
        start = float(parameters["start_time"])
        length = float(parameters["length"])
        return reader, channels, start, length

    @log(logger=logger)
    def _validate_plot_parameters(
        self,
        reader: Optional[str],
        channel: Optional[List[int]],
        start: Optional[float],
        length: Optional[float],
    ) -> bool:
        """
        Validate the extracted parameters for plotting.

        :param reader: Reader plugin name.
        :type reader: Optional[str]
        :param channel: List of channel numbers.
        :type channel: Optional[List[int]]
        :param start: Start time.
        :type start: Optional[float]
        :param length: Duration.
        :type length: Optional[float]
        :return: True if all parameters are valid, else False.
        :rtype: bool
        """
        return all([reader, channel is not None, start is not None, length is not None])

    @log(logger=logger)
    def _handle_other_actions(
        self, action_name: str, parameters: Dict[str, Any]
    ) -> None:
        """
        Handle plugin-specific actions not otherwise accounted for.

        :param action_name: Action to execute.
        :type action_name: str
        :param parameters: Parameters needed for the action.
        :type parameters: Dict[str, Any]
        """
        reader = parameters.get("reader")
        if reader and reader != "No Reader":
            self.reader_channels_requested.emit(reader)

    @log(logger=logger)
    def update_channels(self, channels: Sequence[int]) -> None:
        """
        Update the channel combo box with available channels.

        :param channels: Available channel identifiers.
        :type channels: Sequence[int]
        """
        self.rawdatacontrols.update_channels(channels)
        self.logger.info("Updated channels in RawDataControls through RawDataView")

    def get_walkthrough_steps(self) -> List[WalkthroughStep]:
        return [
            # Raw Data Tab
            (
                "Raw Data Tab",
                "You're now in the 'Raw Data' tab. Click the '+' button to add a reader.",
                "RawDataView",
                lambda: [self.rawdatacontrols.readers_add_button],
            ),
            (
                "Raw Data Tab",
                "Great! A reader has been added. Now, select a channel from the dropdown menu to proceed.",
                "RawDataView",
                lambda: [self.rawdatacontrols.channel_comboBox],
            ),
            (
                "Raw Data Tab",
                "Perfect. Click the '+' button to add a filter.",
                "RawDataView",
                lambda: [self.rawdatacontrols.filters_add_button],
            ),
            (
                "Raw Data Tab",
                "Now, enter a valid start time to prepare your trace.",
                "RawDataView",
                lambda: [self.rawdatacontrols.start_time_lineEdit],
            ),
            (
                "Raw Data Tab",
                "Click 'Update Trace' to visualize your raw data.",
                "RawDataView",
                lambda: [self.rawdatacontrols.update_trace_pushButton],
            ),
            (
                "Raw Data Tab",
                "Navigate the trace efficiently using the arrow buttons.",
                "RawDataView",
                lambda: [
                    self.rawdatacontrols.left_trace_arrow_button,
                    self.rawdatacontrols.right_trace_arrow_button,
                ],
            ),
            (
                "Raw Data Tab",
                "Need to check the noise across frequencies? Click 'Update PSD' to view the power spectral density.",
                "RawDataView",
                lambda: [self.rawdatacontrols.update_psd_pushButton],
            ),
            (
                "Raw Data Tab",
                "Click the '+' button to add an event finder.",
                "RawDataView",
                lambda: [self.rawdatacontrols.eventfinders_add_button],
            ),
            (
                "Raw Data Tab",
                "Then, click 'Find Events' to begin detection.",
                "RawDataView",
                lambda: [self.rawdatacontrols.find_events_pushButton],
            ),
            (
                "Raw Data Tab",
                "To refine performance, restrict the time range using the timer button.",
                "RawDataView",
                lambda: [self.rawdatacontrols.timer_pushButton],
            ),
            (
                "Raw Data Tab",
                "If events have been successfully found — you can confirm this on the right-side panel — you may now enter the event indices you wish to inspect.",
                "RawDataView",
                lambda: [self.rawdatacontrols.event_index_lineEdit],
            ),
            (
                "Raw Data Tab",
                "Now click 'Plot Events' to see the result.",
                "RawDataView",
                lambda: [self.rawdatacontrols.plot_events_pushButton],
            ),
            (
                "Raw Data Tab",
                "Use these arrows to quickly browse between plotted events.",
                "RawDataView",
                lambda: [
                    self.rawdatacontrols.left_plot_arrow_button,
                    self.rawdatacontrols.right_plot_arrow_button,
                ],
            ),
            (
                "Raw Data Tab",
                "If you are happy with your events, you can now click the '+' button to add a writer.",
                "RawDataView",
                lambda: self.rawdatacontrols.writers_add_button,
            ),
            (
                "Raw Data Tab",
                "Finally, click 'Commit Events' to save your findings into an events database.",
                "RawDataView",
                lambda: self.rawdatacontrols.commit_btn,
            ),
            (
                "Raw Data Tab",
                "Note: At any time, you can click 'Export Plot Data' to save your graph.",
                "RawDataView",
                lambda: self.rawdatacontrols.export_plot_data_pushButton,
            ),
        ]

    def get_current_view(self) -> str:
        return "RawDataView"
