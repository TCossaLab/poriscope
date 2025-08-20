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
from typing import Callable, Dict, List, Optional, Tuple

import matplotlib.pyplot as pl
import numpy as np
import numpy.typing as npt
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox
from typing_extensions import override

from poriscope.plugins.analysistabs.utils.eventAnalysisControls import (
    EventAnalysisControls,
)
from poriscope.plugins.analysistabs.utils.walkthrough_mixin import WalkthroughMixin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaView import MetaView


@inherit_docstrings
class EventAnalysisView(MetaView, WalkthroughMixin):
    """
    Subclass of MetaView for visualizing and interacting with event-based signal analysis.

    Handles event plotting, plugin integration, and user-triggered actions.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init()
        self._init_walkthrough()

    @log(logger=logger)
    @override
    def _init(self):
        """
        Initialize the EventAnalysisView. Called after constructor.
        Used to set up internal variables or state as needed.
        """
        pass

    @log(logger=logger)
    def update_plot(self):
        """
        Update the main plot with the latest data and features.
        This method should be called after data and parameters are updated.
        """
        pass

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
    @override
    def _set_control_area(self, layout):
        """
        Set up the control area with widgets for user interaction.

        :param layout: Layout to which the controls will be added.
        :type layout: QVBoxLayout or QHBoxLayout
        """
        self.eventAnalysisControls = EventAnalysisControls()
        self.eventAnalysisControls.actionTriggered.connect(self.handle_parameter_change)
        self.eventAnalysisControls.edit_processed.connect(self.handle_edit_triggered)
        self.eventAnalysisControls.add_processed.connect(self.handle_add_triggered)
        self.eventAnalysisControls.delete_processed.connect(
            self.handle_delete_triggered
        )

        controlsAndAnalysisLayout = QHBoxLayout()
        controlsAndAnalysisLayout.setContentsMargins(0, 0, 0, 0)

        # Add the eventAnalysisControls directly to the main layout
        controlsAndAnalysisLayout.addWidget(self.eventAnalysisControls, stretch=1)

        layout.setSpacing(0)
        layout.addLayout(controlsAndAnalysisLayout, stretch=1)

    @log(logger=logger)
    def _factors(self, n):
        """
        Compute a pair of factors of n that are closest to each other.
        Useful for determining subplot grid dimensions.

        :param n: Integer to factor.
        :type n: int
        :return: Tuple of two integers whose product is close to n and have minimal difference.
        :rtype: tuple
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
    def update_plot_data(self, data=None):
        """
        Update internal storage of plot data.
        Can be used by signal handlers receiving data.

        :param data: The data to be stored, can be a dict or array.
        :type data: any
        """
        self.logger.debug(f"Received data for plotting: {data}")
        if isinstance(data, dict):
            self.plot_data = data["data"]
        else:
            self.plot_data = data

    @log(logger=logger)
    def update_plot_features(
        self,
        vertical=None,
        horizontal=None,
        points=None,
        vlabels=None,
        hlabels=None,
        plabels=None,
    ):
        """
        Update feature overlays for the plot, such as vertical/horizontal lines and labeled points.

        :param vertical: List of vertical line positions.
        :param horizontal: List of horizontal line positions.
        :param points: List of (x, y) point coordinates.
        :param vlabels: Labels for vertical lines.
        :param hlabels: Labels for horizontal lines.
        :param plabels: Labels for points.
        """
        self.vertical = vertical
        self.horizontal = horizontal
        self.points = points
        self.vlabels = vlabels
        self.hlabels = hlabels
        self.plabels = plabels

    @log(logger=logger)
    def update_plot_samplerate(self, samplerate):
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
        :type available_plugins: Mapping[str, list[str]]
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
    def handle_parameter_change(self, submodel_name, action_name, args):
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
    def _shift_range_and_update_plot(self, parameters, direction):
        """Shift ranges in the GUI and update plot and input if valid."""

        try:
            loader, eventfitter, data_filter, channels, _ = (
                self._extract_plot_event_parameters(parameters)
            )
            self.validate_single_channel(channels)
            channels[0]
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
    def _handle_plot_events(self, parameters):
        """
        Handle loading and plotting of selected events based on provided parameters.

        :param parameters: Dictionary containing eventfinder, filter, channels, and event indices.
        :type parameters: dict
        """
        try:
            loader, eventfitter, data_filter, channels, events = (
                self._extract_plot_event_parameters(parameters)
            )
            self.validate_single_channel(channels)
            channel = channels[0]
            # self._load_and_plot_events(loader, data_filter, channels, events)
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
        try:
            get_num_events_args = (channel,)
            self.global_signal.emit(
                "MetaEventLoader",
                loader,
                "get_num_events",
                get_num_events_args,
                "set_num_events_allowed",
                (),
            )
        except Exception as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
        if events and max(events) >= self.num_events_allowed:
            self.logger.info(
                "Some event indices were out of bounds, truncating indices above {self.num_events_allowed - 1}"
            )
            events = [x for x in events if x < self.num_events_allowed]

        if events:
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
                samplerate_args = (channel,)
                self.global_signal.emit(
                    "MetaEventLoader",
                    loader,
                    "get_samplerate",
                    samplerate_args,
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
                data_list: List[npt.NDArray[np.float64]] = []
                label_list: List[Optional[str]] = []
                vertical_lines: List[Optional[float]] = []
                vertical_labels: List[Optional[str]] = []
                horizontal_lines: List[Optional[float]] = []
                horizontal_labels: List[Optional[str]] = []
                points: List[Optional[Tuple[float, float]]] = []
                plabels: List[Optional[str]] = []
                num_events = 0
                for event in events[:]:  # to allow removal if needed
                    try:
                        load_data_args = (channel, event, self.data_filter)
                        # Emit the signal with the correct handler name for when the data is ready
                        self.global_signal.emit(
                            "MetaEventLoader",
                            loader,
                            "load_event",
                            load_data_args,
                            "update_plot_data",
                            (),
                        )
                    except (IndexError, ValueError) as e:
                        self.logger.error(
                            f"Unable to retrieve requested data for event {event}: {repr(e)}"
                        )
                    if self.plot_data is not None:
                        data_list.append(self.plot_data)
                        vertical_lines.append(None)
                        vertical_labels.append(None)
                        horizontal_lines.append(None)
                        horizontal_labels.append(None)
                        points.append(None)
                        plabels.append(None)
                        self.plot_data = None

                        label_list.append(f"Event {event} Data")
                        num_events += 1

                        if eventfitter != "No Event Fitter":
                            self.eventfitting_status = False
                            eventfitting_status_args = (channel,)
                            self.global_signal.emit(
                                "MetaEventFitter",
                                eventfitter,
                                "get_eventfitting_status",
                                eventfitting_status_args,
                                "set_eventfitting_status",
                                (),
                            )
                            if self.eventfitting_status is True:
                                try:
                                    load_fit_args = (channel, event)
                                    self.global_signal.emit(
                                        "MetaEventFitter",
                                        eventfitter,
                                        "construct_fitted_event",
                                        load_fit_args,
                                        "update_plot_data",
                                        (),
                                    )
                                except RuntimeError as e:
                                    self.logger.error(
                                        f"Fit for event {event} could not be loaded in channel {channel}, skipping: {e}"
                                    )
                                except KeyError as e:
                                    self.logger.error(
                                        f"Event {event} not found in channel {channel}, skipping: {e}"
                                    )
                                except Exception as e:
                                    self.logger.error(
                                        f"An unexpected error occured while trying to overlay the fit on the event: {e}"
                                    )
                                else:
                                    if self.plot_data is not None:
                                        data_list.append(self.plot_data)
                                        self.plot_data = None
                                        label_list.append(f"Event {event} Fit")
                                try:
                                    load_feature_args = (channel, event)
                                    self.global_signal.emit(
                                        "MetaEventFitter",
                                        eventfitter,
                                        "get_plot_features",
                                        load_feature_args,
                                        "update_features",
                                        (),
                                    )
                                except RuntimeError as e:
                                    self.logger.error(
                                        f"Features for event {event} could not be loaded in channel {channel}, skipping: {e}"
                                    )
                                except KeyError as e:
                                    self.logger.info(
                                        f"Event {event} not found in channel {channel} to get features, skipping: {e}"
                                    )
                                except Exception as e:
                                    self.logger.error(
                                        f"An unexpected error occured while trying to overlay features on the event: {e}"
                                    )
                                else:
                                    if self.vertical is not None:
                                        vertical_lines[-1] = self.vertical
                                        vertical_labels[-1] = self.vlabels
                                        self.vertical_lines = None
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

                    else:
                        self.logger.warning(
                            f"No data loaded for event {event}, skipping"
                        )
                        events.remove(event)
                if data_list:
                    self._update_event_plot(
                        data_list,
                        label_list,
                        num_events,
                        vertical_lines,
                        horizontal_lines,
                        points,
                        vertical_labels,
                        horizontal_labels,
                        plabels,
                    )
                else:
                    self.logger.error("No data available for plotting")
            except Exception as e:
                self.logger.error(f"Unable to plot event data: {e}")

    @log(logger=logger)
    def set_eventfitting_status(self, status):
        """
        Set the internal event fitting status.

        :param status: Boolean indicating fitting completion status.
        :type status: bool
        """
        self.eventfitting_status = status

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
    def _start_writer(self, writer, channels):
        """
        Start the process of writing committed events to the database for the given channels.

        :param writer: Identifier of the database writer plugin.
        :type writer: str
        :param channels: List of channel indices for which to write events.
        :type channels: list[int]
        """
        if not isinstance(channels, list):
            channels = [channels]
        try:
            for channel in channels:
                write_events_args = (channel,)
                # Emit the signal with the correct handler name for when the data is ready
                ret_args = (channel, writer, "MetaDatabaseWriter")
                self.global_signal.emit(
                    "MetaDatabaseWriter",
                    writer,
                    "write_events",
                    write_events_args,
                    "set_generator",
                    ret_args,
                )  # update here to unify generators
        except (IndexError, ValueError) as e:
            self.logger.error(
                f"Unable to set up database writer {writer} for channel {channel}: {repr(e)}"
            )
        else:
            self.run_generators.emit(writer)

    @log(logger=logger)
    def set_num_events_allowed(self, num_events):
        """
        Set the maximum number of events allowed to be plotted.

        :param num_events: Number of events allowed.
        :type num_events: int
        """
        self.num_events_allowed = num_events

    @log(logger=logger)
    def _update_event_plot(
        self,
        event_data,
        labels,
        num_events,
        vertical_lines,
        horizontal_lines,
        points,
        vlabels,
        hlabels,
        plabels,
    ):
        """
        Update the event plot with raw data, annotations, and formatting.

        This method generates subplots for each event, displays time-series data,
        and optionally overlays vertical/horizontal lines and annotated points.

        :param event_data: List of 1D arrays containing current traces for each event.
        :type event_data: list[np.ndarray]
        :param labels: List of strings for each subplot's title.
        :type labels: list[str]
        :param num_events: Total number of events to plot (i.e., number of subplots).
        :type num_events: int
        :param vertical_lines: List of lists of x-values for vertical line annotations per subplot.
        :type vertical_lines: list[list[float] or None]
        :param horizontal_lines: List of lists of y-values for horizontal line annotations per subplot.
        :type horizontal_lines: list[list[float] or None]
        :param points: List of lists of (x, y) coordinate tuples for marker points per subplot.
        :type points: list[list[tuple[float, float]] or None]
        :param vlabels: List of lists of labels for vertical lines.
        :type vlabels: list[list[str or None]]
        :param hlabels: List of lists of labels for horizontal lines.
        :type hlabels: list[list[str or None]]
        :param plabels: List of lists of labels for points.
        :type plabels: list[list[str or None]]
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
        for i, (data, label) in enumerate(zip(event_data, labels)):
            if "Data" in label:
                features_plotted = False
                legend = False
                ax = self.figure.add_subplot(
                    num_rows, num_cols, j + 1
                )  # Create subplots in a grid
                ax.set_title(label)
                j += 1

            time = np.arange(len(data)) / self.plot_samplerate * 1e6
            ax.plot(time, data / 1000)

            x_label = r"Time (us)"
            y_label = r"Current (nA)"

            self._update_cache(
                (time, label + " " + x_label), (data / 1000, label + " " + y_label)
            )

            if i % num_cols == 0:
                ax.set_ylabel(y_label)
            labelnum = (num_rows - 1) * num_cols
            if num_events % num_cols > 0:
                labelnum -= num_cols - num_events % num_cols
            if i >= labelnum:
                ax.set_xlabel(r"Time ($\mu s$)")

            if features_plotted is False:
                features_plotted = True

                # --- Vertical lines ---
                verticals = vertical_lines[j - 1]
                vertical_labels = vlabels[j - 1]
                color_idx = 0
                if verticals is not None:
                    for line, label in zip(verticals, vertical_labels):
                        if label is None:
                            ax.axvline(x=line, color="black", linestyle="--")
                        else:
                            legend = True
                            color = colors_no_black[color_idx % len(colors_no_black)]
                            ax.axvline(x=line, linestyle="--", color=color, label=label)
                            color_idx += 1

                # --- Horizontal lines ---
                horizontals = horizontal_lines[j - 1]
                horizontal_labels = hlabels[j - 1]
                color_idx = 0
                if horizontals is not None:
                    for line, label in zip(horizontals, horizontal_labels):
                        if label is None:
                            ax.axhline(y=line / 1000, color="black", linestyle="--")
                        else:
                            legend = True
                            color = colors_no_black[color_idx % len(colors_no_black)]
                            ax.axhline(
                                y=line / 1000, linestyle="--", color=color, label=label
                            )
                            color_idx += 1

                # --- Points ---
                pts = points[j - 1]
                pt_labels = plabels[j - 1]
                color_idx = 0
                if pts is not None:
                    for (x, y), label in zip(pts, pt_labels):
                        if label is None:
                            ax.plot(
                                x, y / 1000, marker="x", color="black", markersize=10
                            )
                        else:
                            legend = True
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

                ax.grid(True)

            if legend:
                ax.legend(loc="best")

        self.figure.set_constrained_layout(True)
        self.canvas.draw()
        self._commit_cache()

    @log(logger=logger)
    def _handle_fit_events(self, parameters):
        """
        Handle the fitting of events using the selected event fitter and data filter.

        :param parameters: Dictionary of parameters from the GUI controls.
        :type parameters: dict
        """
        try:
            eventfitter, data_filter, channels = self._extract_event_fit_parameters(
                parameters
            )
        except ValueError as e:
            self.logger.error(f"Parameter extraction failed: {repr(e)}")
            return
        if eventfitter is not None and channels is not None and data_filter is not None:
            self._start_eventfitter(eventfitter, data_filter, channels)

    @log(logger=logger)
    def _handle_commit_events(self, parameters):
        """
        Handle commit actions by triggering the selected writer to store events.

        :param parameters: Dictionary containing selected writer and channel info.
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
    def _start_eventfitter(self, eventfitter, data_filter, channels):
        """
        Start the event fitting process for the selected channel(s) using the given fitter and filter.

        :param eventfitter: Identifier of the event fitter plugin.
        :type eventfitter: str
        :param data_filter: Identifier of the filter plugin to apply to the data.
        :type data_filter: str
        :param channels: List of integer channel indices.
        :type channels: list[int]
        """
        if not isinstance(channels, list):
            channels = [channels]
        try:
            # If channels is not a list, make it a list
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
        except:
            raise
        else:
            try:
                for channel in channels:
                    self.global_signal.emit(
                        "MetaEventFitter",
                        eventfitter,
                        "get_eventfitting_status",
                        (channel,),
                        "relay_eventfitting_status",
                        (),
                    )  # update here to unify generators
                    if self.eventfitting_status is True:
                        reply = QMessageBox.question(
                            self,
                            "Confirmation",
                            f"Fitting was already completed in channel {channel}. Start over anyway?",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No,
                        )
                        if reply == QMessageBox.No:
                            return
                    fit_events_args = (channel, False, self.data_filter, None)
                    # Emit the signal with the correct handler name for when the data is ready
                    ret_args = (channel, eventfitter, "MetaEventFitter")
                    self.global_signal.emit(
                        "MetaEventFitter",
                        eventfitter,
                        "fit_events",
                        fit_events_args,
                        "set_generator",
                        ret_args,
                    )  # update here to unify generators
            except (IndexError, ValueError) as e:
                self.logger.error(
                    f"Unable to set up event fitter generator {eventfitter} for channel {channel}: {repr(e)}"
                )
            else:
                self.run_generators.emit(eventfitter)

    @log(logger=logger)
    def _extract_plot_event_parameters(self, parameters):
        """
        Extract event plotting parameters from input.

        Args:
            parameters (dict): Input parameter dictionary.

        Returns:
            tuple: (eventfitter, data_filter, channels, events)
        """
        loader = parameters.get("loader")
        eventfitter = parameters.get("eventfitter")
        data_filter = parameters.get("filter")
        channels = [int(ch) for ch in parameters["channel"]]
        events = parameters.get("event_index")
        return loader, eventfitter, data_filter, channels, events

    @log(logger=logger)
    def _extract_event_fit_parameters(self, parameters):
        """
        Extract parameters used for event finding.

        Args:
            parameters (dict): Dictionary of parameters.

        Returns:
            tuple: (eventiftter, data_filter, channels)
        """
        eventfitter = parameters.get("eventfitter")
        data_filter = parameters.get("filter")
        channels = [int(ch) for ch in parameters["channel"]]
        return eventfitter, data_filter, channels

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
    def update_channels(self, channels):
        """
        Update the channel list in the event analysis control widget.

        :param channels: List of available channel indices.
        :type channels: list[int]
        """
        self.eventAnalysisControls.update_channels(channels)
        self.logger.info("Updated channels in EventAnalysisTab")

    @log(logger=logger)
    def _handle_other_actions(self, action_name, parameters):
        """
        Handle non-standard or plugin-specific actions that do not fall into predefined handlers.

        :param action_name: Action identifier.
        :type action_name: str
        :param parameters: Dictionary of parameters for the action.
        :type parameters: dict
        """
        loader = parameters.get("loader")
        if loader:
            self.global_signal.emit(
                "MetaEventLoader", loader, "get_channels", (), "update_channels", ()
            )

    def get_walkthrough_steps(self):
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

    def get_current_view(self):
        return "EventAnalysisView"
