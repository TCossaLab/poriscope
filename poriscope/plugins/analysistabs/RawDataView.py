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
from typing import Callable, Dict, List

import numpy as np
from fast_histogram import histogram1d
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox
from scipy.stats import median_abs_deviation
from typing_extensions import override

from poriscope.plugins.analysistabs.utils.rawdatacontrols import RawDataControls
from poriscope.plugins.analysistabs.utils.walkthrough_mixin import WalkthroughMixin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaView import MetaView
from poriscope.views.widgets.time_widget import TimeWidget


@inherit_docstrings
class RawDataView(MetaView, WalkthroughMixin):
    """
    Subclass of MetaView for visualizing raw signal data and PSD plots.

    Handles plot rendering, signal responses, and interactions with readers, filters, and event finders.
    """

    logger = logging.getLogger(__name__)
    calculate_psd = Signal(list, float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init()
        self._init_walkthrough()

    @log(logger=logger)
    @override
    def _init(self):
        """Initialize the RawDataView-specific attributes."""

        self.analysis_time_limits = {}

    @log(logger=logger)
    @override
    def _set_control_area(self, layout):
        """
        Set up the control area layout by embedding the RawDataControls widget.

        Args:
            layout (QLayout): The layout where controls will be added.
        """
        self.rawdatacontrols = RawDataControls()
        self.rawdatacontrols.actionTriggered.connect(self.handle_parameter_change)
        self.rawdatacontrols.edit_processed.connect(self.handle_edit_triggered)
        self.rawdatacontrols.add_processed.connect(self.handle_add_triggered)
        self.rawdatacontrols.delete_processed.connect(self.handle_delete_triggered)

        controlsAndAnalysisLayout = QHBoxLayout()
        controlsAndAnalysisLayout.setContentsMargins(0, 0, 0, 0)

        # Add the rawdatacontrols directly to the main layout
        controlsAndAnalysisLayout.addWidget(self.rawdatacontrols, stretch=1)

        layout.setSpacing(0)
        layout.addLayout(controlsAndAnalysisLayout, stretch=1)

    @log(logger=logger)
    @override
    def _reset_actions(self, axis_type="2d"):
        """
        Clears the figure and reinitializes axes. This will also add a flag to the tab action history if @register_action is being used to keep track of actions. Only actions applied after the most recent call to this function will be recreated if the related file is loaded.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        """
        pass

    @log(logger=logger)
    def _factors(self, n):
        """
        Determine the factor pair (rows, cols) closest to a square layout.

        Args:
            n (int): Total number of plots.

        Returns:
            tuple: (rows, columns) representing subplot grid dimensions.
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
    def get_save_filename(self):
        """
        Open a dialog to save a CSV file.

        Returns:
            str: Selected file path or empty string if cancelled.
        """
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV File",
            os.path.expanduser("~"),
            "CSV Files (*.csv);;All Files (*)",
        )
        return file_name

    @log(logger=logger)
    def update_plot(self, data, channels, start=0, baseline=False):
        """
        Update the plot area with the provided data across multiple channels in a grid layout.

        :param data: List of numpy arrays or lists, one for each channel.
        :param channels: List of channel identifiers corresponding to the data.
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

            if baseline is True:
                amp, mean, std = self._get_baseline_stats(channel_data / 1000)
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
        self.figure.set_constrained_layout(True)
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def update_psd(self, psd_data, rms_data, frequency, channels):
        """
        Update the plot area with the provided psd and frequency data across multiple channels in a grid layout.

        :param data: List of numpy arrays or lists, one for each channel.
        :param channels: List of channel identifiers corresponding to the data.
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
        self.figure.set_constrained_layout(True)
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def update_plot_data(self, data):
        """
        Update the stored plot data for future use.

        Args:
            data (dict or ndarray): Data dictionary or raw array to store.
        """
        self.logger.debug(f"Received data for plotting: {data}")
        if not isinstance(data, dict):
            self.plot_data = data
        else:
            self.plot_data = data[
                "data"
            ]  # event data now returns a dict - this should be refactored to handle this explicitly

    @log(logger=logger)
    def update_plot_samplerate(self, samplerate):
        """
        Update the sampling rate used for plotting.

        Args:
            samplerate (float): Sampling frequency in Hz.
        """
        self.logger.debug(f"Received sampling rate: {samplerate}")
        self.plot_samplerate = samplerate

    @log(logger=logger)
    def update_timer_channels(self, channels):
        """
        Update the list of channels for event timing.

        Args:
            channels (list): List of valid channel indices.
        """
        self.timer_channels = channels

    @log(logger=logger)
    @override
    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """
        Called whenever a new plugin is instantiated elsewhere in the app, to keep an up-to-date list of possible data sources for use by this plugin.

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app.
        :type available_plugins: Dict[str, list[str]]
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

            for finder in eventfinders:
                if finder not in self.analysis_time_limits.keys():
                    self.analysis_time_limits[finder] = {}
                    self.global_signal.emit(
                        "MetaEventFinder",
                        finder,
                        "get_channels",
                        (),
                        "update_timer_channels",
                        (),
                    )
                    for ch in self.timer_channels:
                        self.analysis_time_limits[finder][ch] = {}
                        self.analysis_time_limits[finder][ch]["start"] = 0
                        self.analysis_time_limits[finder][ch]["end"] = 0

            self.logger.info("ComboBoxes updated with available readers and filters")
        except Exception as e:
            self.logger.info(f"Updating ComboBoxes failed: {repr(e)}")

    @log(logger=logger)
    @Slot(str, str, tuple)
    def handle_parameter_change(self, submodel_name, action_name, args):
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
    def _get_baseline_stats(self, data) -> tuple[float, float, float]:
        """
        Get the local amplitude, mean, and standard deviation for a chunk of data. Assumes data is rectified.


        :param data: Chunk of timeseries data to compute statistics on.
        :type data: npt.NDArray[np.float64]
        :return: Tuple of mean and standard deviation.
        :rtype: tuple[float, float]
        """
        top = np.max(data)
        bottom = np.min(data)

        median_abs_deviation(data)
        width = 2 * (top - bottom) / len(data) ** (1 / 3)
        bins = int((top - bottom) / width)
        hist = histogram1d(data, range=[bottom, top], bins=bins)
        centers = np.linspace(bottom, top, len(hist))
        max_index = np.argmax(hist)

        maxval = hist[max_index]
        # top_index: the first index where hist[i] <= maxval/5 starting from max_index
        try:
            top_index = next(
                i for i in range(max_index, len(hist)) if hist[i] <= maxval / 5
            )
        except StopIteration:
            top_index = len(hist) - 1

        # bottom_index: the first index where hist[i] <= maxval/5 going backwards from max_index
        try:
            bottom_index = next(
                i for i in range(max_index, -1, -1) if hist[i] <= maxval / 5
            )
        except StopIteration:
            bottom_index = 0

        np.minimum(top_index - max_index, max_index - bottom_index)

        top = centers[top_index]
        bottom = centers[bottom_index]

        mask = (data > bottom) & (data < top)
        data = data[mask]

        width = 2 * (top - bottom) / len(data) ** (1 / 3)
        bins = int((top - bottom) / width)
        hist = histogram1d(data, range=[bottom, top], bins=bins)
        centers = np.linspace(bottom, top, len(hist))

        max_index = np.argmax(hist)
        maxval = hist[max_index]

        # top_index: the first index where hist[i] <= 0.6*maxval starting from max_index
        try:
            top_index = next(
                i for i in range(max_index, len(hist)) if hist[i] <= 0.6 * maxval
            )
        except StopIteration:
            top_index = len(hist) - 1

        # bottom_index: the first index where hist[i] <= 0.6*maxval going backwards from max_index
        try:
            bottom_index = next(
                i for i in range(max_index, -1, -1) if hist[i] <= 0.6 * maxval
            )
        except StopIteration:
            bottom_index = 0
        std_index = (
            bottom_index
            if max_index - bottom_index < top_index - max_index
            else top_index
        )

        try:
            baseline_params = np.array(
                self._gaussian_fit(
                    hist,
                    centers,
                    centers[max_index],
                    np.absolute(centers[std_index] - centers[max_index]),
                )
            )
        except ValueError:
            raise
        return baseline_params

    @log(logger=logger)
    def _gaussian(self, x: float, A: float, m: float, s: float) -> float:
        """
        :param x: location to calculate the value
        :type x: float
        :param A: amplitude of the gaussian
        :type A: float
        :param A: mean of the gaussian
        :type m: float
        :param s: standard deviation of the gaussian
        :type s: float

        Calculate the value of a 1D gaussian distribution at a location x with the given paramters
        """
        return A * np.exp(-((x - m) ** 2) / (2 * s**2))

    @log(logger=logger)
    def _gaussian_fit(
        self, histogram, bins, mean_guess: float, stdev_guess: float
    ) -> tuple[float, float, float]:
        """
        :param histogram: the histogram to fit, assumed unimodal
        :type histogram: npt.NDArray[np.float64]
        :param bins: centers of the bins for the histogram
        :type bins: npt.NDArray[np.float64]
        :param mean_guess: initial guess for the mean of the fit
        :type mean_guess: float
        :param stdev_guess: initial guess for the standard deviation of the fit
        :type stdev_guess: float

        Fit and return best fit parameters for a 1D gaussian fit to a histogram given an initial guess. Use a matrix multiplication instead of nonlinear fitting for speed.
        """
        if stdev_guess <= 0:
            raise ValueError("Invalud standard deviation guess")
        amp = np.max(histogram)
        localy = histogram / amp
        localx = (bins - mean_guess) / stdev_guess

        x0 = localy
        x1 = localx * x0
        x2 = localx * x1
        x3 = localx * x2
        x4 = localx * x3

        x0 = np.sum(x0)
        x1 = np.sum(x1)
        x2 = np.sum(x2)
        x3 = np.sum(x3)
        x4 = np.sum(x4)

        lny_base = np.array([np.log(y) if y > 0 else 0 for y in localy])

        lny = lny_base * localy
        xlny = localx * lny
        x2lny = localx * xlny

        lny = np.sum(lny)
        xlny = np.sum(xlny)
        x2lny = np.sum(x2lny)

        xTx = np.array([[x4, x3, x2], [x3, x2, x1], [x2, x1, x0]])

        xnlny = np.array([x2lny, xlny, lny])

        xTxinv = np.linalg.inv(xTx)

        params = np.dot(xTxinv, xnlny)

        if params[0] < 0:
            stdev = np.sqrt(-1.0 / (2 * params[0]))
        else:
            raise ValueError("Unable to estimate standard deviation")
        mean = stdev**2 * params[1]
        amplitude = np.exp(params[2] + mean**2 / (2 * stdev**2))

        stdev *= stdev_guess
        mean += mean_guess
        amplitude *= amp
        return amp, mean, np.absolute(stdev)

    @log(logger=logger)
    def _handle_timer(self, parameters):
        """
        Open a time range selection dialog for a given event finder and update the internal time limits.

        :param parameters: Dictionary containing the 'eventfinder' key.
        :type parameters: dict
        """
        finder = parameters["eventfinder"]
        if finder != "No Eventfinder":
            time_widget = TimeWidget(self.analysis_time_limits[finder])
            time_widget.exec()
            result = time_widget.get_result()
            if result is not None:
                self.analysis_time_limits[finder] = result

    @log(logger=logger)
    def _shift_range_and_update_plot(self, parameters, direction):
        """
        Shift selected event index ranges left or right and update the plot accordingly.

        :param parameters: Dictionary containing current event plotting parameters.
        :type parameters: dict
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
        self.rawdatacontrols.set_event_index_input(new_event_str)

    def _get_event_index_text(self) -> str:
        """
        Get the event index input from the UI.

        Returns:
            str: The current text from the event index input field.
        """
        return self.rawdatacontrols.event_index_lineEdit.text().strip()

    @log(logger=logger)
    def validate_single_channel(self, channels):
        """
        Ensure only one channel is selected.

        Args:
            channels (list): List of selected channel indices.

        Raises:
            ValueError: If more than one channel is selected.
        """
        if len(channels) > 1:
            raise ValueError(
                "Unable to plot events from multiple channels, select only one"
            )

    @log(logger=logger)
    def _handle_plot_events(self, parameters):
        """
        Handle loading and plotting of selected events based on provided parameters.

        :param parameters: Dictionary containing eventfinder, filter, channels, and event indices.
        :type parameters: dict
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
        else:
            channel = channels[0]

        try:
            get_status_args = (channel,)
            self.global_signal.emit(
                "MetaEventFinder",
                eventfinder,
                "get_eventfinding_status",
                get_status_args,
                "set_eventfinding_status",
                (),
            )
        except Exception as e:
            raise e

        if self.eventfinding_status is False:
            self.add_text_to_display.emit(
                f"Eventfinding not finished in channel {channel}",
                self.__class__.__name__,
            )
            return

        try:
            get_num_events_args = (channel,)
            self.global_signal.emit(
                "MetaEventFinder",
                eventfinder,
                "get_num_events_found",
                get_num_events_args,
                "set_num_events_allowed",
                (),
            )
        except Exception as e:
            raise e

        if self.num_events_allowed == 0:
            self.add_text_to_display.emit(
                f"No events to display from channel {channel}", self.__class__.__name__
            )
            return

        if events and max(events) >= self.num_events_allowed:
            self.logger.info(
                "Some event indices were out of bounds, truncating indices above {self.num_events_allowed - 1}"
            )

        if events:
            events = [x for x in events if x < self.num_events_allowed]
            # get the data filter to use
            try:
                data_filter_args = ()
                self.data_filter = None
                if data_filter != "No Filter":
                    self.global_signal.emit(
                        "MetaFilter",
                        data_filter,
                        "get_callable_filter",
                        data_filter_args,
                        "set_event_filter",
                        (),
                    )
            except Exception:
                self.data_filter = None
                self.logger.warning(
                    f"Unable to load filter {data_filter}, proceeding without a filter"
                )

            # set plot samplerate
            try:
                self.global_signal.emit(
                    "MetaEventFinder",
                    eventfinder,
                    "get_samplerate",
                    (),
                    "update_plot_samplerate",
                    (),
                )
            except Exception:
                self.plot_samplerate = 1
                self.logger.warning(
                    "Unable to get samplerate, time axis will indicate raw data index"
                )

            try:
                # Load data and update plot
                data_list = []
                for event in events[:]:  # to allow removal if needed
                    self._load_event_data(eventfinder, channel, event, self.data_filter)
                    if self.plot_data is not None:
                        data_list.append(self.plot_data)
                    else:
                        self.logger.warning(
                            f"No data loaded for event {event}, skipping"
                        )
                        events.remove(event)

                if data_list:
                    self._update_event_plot(data_list, events)
                else:
                    self.logger.error("No data available for plotting")
            except Exception:
                self.logger.error("Unable to plot event data")

    @log(logger=logger)
    def _start_writer(self, writer, channels):
        """
        Start a writer plugin to commit events for the specified channels.

        :param writer: Identifier for the writer plugin.
        :type writer: str
        :param channels: List of channel indices.
        :type channels: list
        """
        if not isinstance(channels, list):
            channels = [channels]
        else:
            try:
                for channel in channels:
                    write_events_args = channel
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
    def set_num_events_allowed(self, num_events):
        """
        Set the number of events available for display.

        Args:
            num_events (int): Maximum valid event index + 1.
        """
        self.num_events_allowed = num_events

    @log(logger=logger)
    def set_eventfinding_status(self, status):
        """
        Set the current event finding status.

        Args:
            status (bool): Whether event finding is complete.
        """
        self.eventfinding_status = status

    @log(logger=logger)
    def _update_event_plot(self, event_data, event_indices):
        """
        :param event_data: a list of event data to plot in a grid
        :type event_data: List[npt.NDArray[np.float64]]
        :param event_indices: the indices of the events to plot
        :type event_indices: List[int]

        Plot the event data in a grid that gets as close to square as possible
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
        self.figure.set_constrained_layout(True)
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def _handle_find_events(self, parameters):
        """
        Handle the initiation of the event finding process using the given parameters.

        :param parameters: Dictionary containing eventfinder, filter, and channels.
        :type parameters: dict
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
    def _handle_commit_events(self, parameters):
        """
        Handle committing of found events to the selected writer plugin.

        :param parameters: Dictionary containing writer and channels.
        :type parameters: dict
        """
        try:
            writer, channels = self._extract_commit_event_parameters(parameters)
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return

        if writer is not None and channels is not None:
            self._start_writer(writer, channels)

    @log(logger=logger)
    def _start_eventfinder(self, eventfinder, data_filter, channels):
        """
        Start the event finding operation on the specified channels with an optional filter.

        :param eventfinder: Identifier for the event finder plugin.
        :type eventfinder: str
        :param data_filter: Identifier for the filter plugin, or 'No Filter'.
        :type data_filter: str
        :param channels: List of channel indices to run the event finder on.
        :type channels: list
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
    def _extract_plot_event_parameters(self, parameters):
        """
        Extract event plotting parameters from input.

        Args:
            parameters (dict): Input parameter dictionary.

        Returns:
            tuple: (eventfinder, data_filter, channels, events)
        """
        eventfinder = parameters.get("eventfinder")
        data_filter = parameters.get("filter")
        channels = [int(ch) for ch in parameters["channel"]]
        events = parameters.get("event_index")
        return eventfinder, data_filter, channels, events

    @log(logger=logger)
    def _extract_event_parameters(self, parameters):
        """
        Extract parameters used for event finding.

        Args:
            parameters (dict): Dictionary of parameters.

        Returns:
            tuple: (eventfinder, data_filter, channels)
        """
        eventfinder = parameters.get("eventfinder")
        data_filter = parameters.get("filter")
        channels = [int(ch) for ch in parameters["channel"]]
        return eventfinder, data_filter, channels

    @log(logger=logger)
    def _extract_commit_event_parameters(self, parameters):
        """
        Extract writer and channels from parameters.

        Args:
            parameters (dict): Input dictionary.

        Returns:
            tuple: (writer, channels)
        """
        writer = parameters.get("writer")
        channels = [int(ch) for ch in parameters["channel"]]
        return writer, channels

    @log(logger=logger)
    def set_data_filter_function(self, data_filter: Callable) -> None:
        """
        Set the callcable function to filter data

        :param data_filter: a callable function
        :type data_filter: Callable
        """
        self.data_filter = data_filter

    @log(logger=logger)
    def _shift_range_and_update_trace(self, parameters: dict, direction: str):
        """Shift numeric range left or right and update the plot and GUI input."""

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
    def _handle_load_data_and_update_plot(self, parameters, baseline=False):
        """
        Handle data loading and update the main signal plot.

        This method:
        - Extracts plot parameters (reader, channels, start, length)
        - Loads data using the specified reader for each channel
        - Optionally applies a filter to the data
        - Updates the main plot area with the retrieved data

        :param parameters: Dictionary containing reader, channels, start time, length, and optional filter.
        :type parameters: dict
        """
        # Extract and validate parameters
        try:
            reader, channels, start, length = self._extract_plot_parameters(parameters)
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return

        # Load data and update plot
        if self._validate_plot_parameters(reader, channels, start, length):
            data_list = []
            for channel in channels[:]:  # to allow removal if needed
                self._load_data(reader, channel, start, length)
                if self.plot_data is not None:
                    data_list.append(self.plot_data)
                else:
                    self.logger.error(f"No data loaded for channel {channel}, skipping")
                    channels.remove(channel)

            # Apply filter if needed
            data_filter = parameters.get("filter")
            if data_filter and data_filter != "No Filter":
                filtered_data_list = []
                for channel_data in data_list:
                    filtered_data = self._apply_filter(data_filter, channel_data)
                    filtered_data_list.append(filtered_data)
                data_list = filtered_data_list

            if data_list:
                self.update_plot(data_list, channels, start, baseline=baseline)
            else:
                self.logger.error("No data available for plotting")
        else:
            self.logger.error("Invalid parameters for plotting data")

    @log(logger=logger)
    def _handle_load_data_and_update_psd(self, parameters):
        """
        Handle data loading and update the PSD (Power Spectral Density) plot.

        This method extracts plotting parameters, loads data from the reader,
        optionally applies a filter, emits the signal to calculate PSD, and updates the PSD plot.

        :param parameters: Dictionary containing reader, channels, start time, length, and optional filter.
        :type parameters: dict
        """
        try:
            reader, channels, start, length = self._extract_plot_parameters(parameters)
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return

        # Load data and update plot
        if self._validate_plot_parameters(reader, channels, start, length):
            data_list = []
            for channel in channels[:]:  # to allow removal if needed
                self._load_data(reader, channel, start, length)
                if self.plot_data is not None:
                    data_list.append(self.plot_data)
                else:
                    self.logger.error(f"No data loaded for channel {channel}, skipping")
                    channels.remove(channel)

            # Apply filter if needed
            data_filter = parameters.get("filter")
            if data_filter and data_filter != "No Filter":
                filtered_data_list = []
                for channel_data in data_list:
                    filtered_data = self._apply_filter(data_filter, channel_data)
                    filtered_data_list.append(filtered_data)
                data_list = filtered_data_list
            if data_list:
                self.calculate_psd.emit(data_list, self.plot_samplerate)
                self.update_psd(
                    self.Pxx_list, self.rms_list, self.psd_frequency, channels
                )
            else:
                self.logger.error("No data available for psd calculation")
        else:
            self.logger.error("Invalid parameters for plotting data")

    @log(logger=logger)
    def set_psd(self, Pxx_list, rms_list, frequency):
        """
        Set the PSD and RMS lists for visualization.

        Args:
            Pxx_list (list): Power spectral density data.
            rms_list (list): RMS noise data.
            frequency (ndarray): Frequency axis data.
        """
        self.Pxx_list = Pxx_list
        self.rms_list = rms_list
        self.psd_frequency = frequency

    @log(logger=logger)
    def _apply_filter(self, data_filter, channel_data):
        """
        Apply a data filter using a signal-based plugin system.

        Args:
            data_filter (str): Name of the filter plugin.
            channel_data (ndarray): Data to filter.

        Returns:
            ndarray: Filtered data if successful, else original data.
        """
        try:
            filter_data_args = (channel_data,)
            self.global_signal.emit(
                "MetaFilter",
                data_filter,
                "filter_data",
                filter_data_args,
                "update_plot_data",
                (),
            )
            return self.plot_data  # Assuming the plot_data is updated by the filter
        except Exception as e:
            self.logger.error(f"Unable to filter data with {data_filter}: {repr(e)}")
            return channel_data  # Return unfiltered data if the filter fails

    @log(logger=logger)
    def _extract_plot_parameters(self, parameters):
        """
        Extract reader, channel, start time, and length from parameters.

        Args:
            parameters (dict): Parameter dictionary.

        Returns:
            tuple: (reader, channels, start, length)
        """
        reader = parameters.get("reader")
        channels = [int(ch) for ch in parameters["channel"]]
        start = float(parameters["start_time"])
        length = float(parameters["length"])
        return reader, channels, start, length

    @log(logger=logger)
    def _validate_plot_parameters(self, reader, channel, start, length):
        """
        Validate the extracted parameters for plotting.

        Args:
            reader (str): Reader plugin name.
            channel (list): List of channel numbers.
            start (float): Start time.
            length (float): Duration.

        Returns:
            bool: True if all parameters are valid, else False.
        """
        return all([reader, channel is not None, start is not None, length is not None])

    @log(logger=logger)
    def _load_event_data(self, eventfinder, channel, event, data_filter):
        """
        Load data for a single event from the eventfinder.

        Args:
            eventfinder (str): Name of the event finder plugin.
            channel (int): Channel number.
            event (int): Event index.
            data_filter (str): Filter plugin name, if any.
        """
        try:
            load_data_args = (channel, event, data_filter, False)
            # Emit the signal with the correct handler name for when the data is ready
            self.global_signal.emit(
                "MetaEventFinder",
                eventfinder,
                "get_single_event_data",
                load_data_args,
                "update_plot_data",
                (),
            )
        except (IndexError, ValueError) as e:
            self.logger.error(
                f"Unable to retrieve requested data for event {event}: {repr(e)}"
            )

    @log(logger=logger)
    def _load_data(self, reader, channels, start, length):
        """
        Load data from the specified reader plugin.

        Args:
            reader (str): Reader plugin name.
            channels (list): List of channel indices.
            start (float): Start time.
            length (float): Duration.
        """
        try:
            self.global_signal.emit(
                "MetaReader", reader, "get_samplerate", (), "update_plot_samplerate", ()
            )
        except Exception as e:
            self.plot_samplerate = 1
            self.logger.warning(
                f"Unable to get samplerate: {repr(e)}. X axis will denote raw data indices"
            )
        try:
            # If channels is not a list, make it a list
            if not isinstance(channels, list):
                channels = [channels]

            for channel in channels:
                load_data_args = (start, length, channel)
                # Emit the signal with the correct handler name for when the data is ready
                self.global_signal.emit(
                    "MetaReader",
                    reader,
                    "load_data",
                    load_data_args,
                    "update_plot_data",
                    (),
                )
        except (IndexError, ValueError) as e:
            self.logger.error(
                f"Unable to retrieve requested data for channels {channels}: {repr(e)}"
            )

    @log(logger=logger)
    def _handle_other_actions(self, action_name, parameters):
        """
        Handle plugin-specific actions not otherwise accounted for.

        Args:
            action_name (str): Action to execute.
            parameters (dict): Parameters needed for the action.
        """
        reader = parameters.get("reader")
        if reader:
            self.global_signal.emit(
                "MetaReader", reader, "get_channels", (), "update_channels", ()
            )

    @log(logger=logger)
    def update_channels(self, channels):
        """
        Update the channel combo box with available channels.

        Args:
            channels (list): Available channel identifiers.
        """
        self.rawdatacontrols.update_channels(channels)
        self.logger.info("Updated channels in RawDataControls through RawDataView")

    def get_walkthrough_steps(self):
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

    def get_current_view(self):
        return "RawDataView"
