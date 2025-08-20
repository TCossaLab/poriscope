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
# Kyle Briggs
# Alejandra Carolina González González

import logging
import threading
from abc import abstractmethod
from typing import Dict, List, Set

import numpy as np
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from poriscope.utils.LogDecorator import log
from poriscope.utils.QWidgetABCMeta import QWidgetABCMeta


class MetaView(QWidget, metaclass=QWidgetABCMeta):
    """
    Abstract base class designed to provide a unified interface for different analysis tabs.

    This class includes a blank plot canvas for visualizing data, a dedicated space for
    control elements, and an interface for dynamically updating the plot based on user
    interactions or analysis results.
    """

    global_signal = Signal(
        str, str, str, tuple, str, tuple
    )  # metaclass type, subclass key, function to call, args for function to call, function to call with reval (can be None), added args for retval
    data_plugin_controller_signal = Signal(
        str, str, str, tuple, str, tuple
    )  # metaclass type, subclass key, function to call, args for function to call, function to call with reval (cane be None), added args for retval
    update_tab_action_history = Signal(
        object, bool
    )  # OrderedDict of actions to take, whether or not to delete the most recent key
    save_tab_action_history = Signal(str)  # save file name
    kill_worker = Signal(str, str)
    kill_all_workers = Signal(str)
    cache_plot_data = Signal(list, list)
    create_plugin = Signal(str, str)  # metaclass, subclass
    logger = logging.getLogger(__name__)
    save_requested = Signal(str)
    export_plot_data = Signal()
    run_generators = Signal(str)
    add_text_to_display = Signal(str, str)
    load_actions_from_json = Signal(str)  # filename
    lock = threading.Lock()

    def __init__(self):
        """
        Initialize the MetaTab with a blank plot canvas and a space for controls.
        """
        super().__init__()
        self.available_plugins: Dict[str, List[str]] = {}
        self.progress_bars = {}
        self._init()
        self._setup_ui()
        self.plot_data = None
        self.threads = []
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

    # private API, must be implemented by sublcasses
    @abstractmethod
    def _init(self) -> None:
        """
        Perform additional initialization specific to the algorithm being implemented.
        Must be implemented by subclasses.

        This function is called at the end of the class constructor to perform additional
        initialization specific to the algorithm being implemented.
        kwargs provided to the base class constructor are available as class attributes.
        """
        pass

    @log(logger=logger)
    def set_available_subclasses(self, available_subclasses):
        self.available_subclasses = available_subclasses

    @log(logger=logger)
    def update_plot_data(self, data):
        self.plot_data = data

    @log(logger=logger)
    def _clear_cache(self):
        self.data_cache = []
        self.data_cache_labels = []

    @log(logger=logger)
    def _factors(self, n):
        """
        Find the closest pair of factors for a given number to approximate a square layout.

        :param n: Number to factor.
        :type n: int
        :return: Tuple of two factors.
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
    def _update_cache(self, *data_label_pairs):
        """
        Update the cache with an arbitrary number of (data, label) pairs.

        :param data_label_pairs: Tuple(s) of (data, label)
        :type data_label_pairs: Tuple[npt.NDArray[Any], str]
        """
        for pair in data_label_pairs:
            if not isinstance(pair, (tuple, list)) or len(pair) not in [1, 2]:
                raise ValueError(
                    "Each argument must be a tuple or list with 1 or 2 elements: (data,) or (data, label)"
                )

            data = pair[0]
            label = pair[1] if len(pair) == 2 else ""
            self.data_cache.append(data)
            self.data_cache_labels.append(label or "")

    @log(logger=logger)
    def _commit_cache(self):
        if len(self.data_cache) != len(self.data_cache_labels):
            self.logger.warning(
                "Unable to cache data due to label and data mismatch, exported plot data may be incomplete or missing"
            )
        else:
            self.cache_plot_data.emit(self.data_cache, self.data_cache_labels)

    @log(logger=logger)
    def _set_custom_display_area(self, layout) -> None:
        self._setup_canvas()  # Ensure canvas is set up here

        # Create a display layout and add the canvas to it
        display_layout = QVBoxLayout()
        display_layout.setSpacing(0)

        # Create a container widget for the display area
        display_container = QWidget()
        display_container.setLayout(display_layout)
        display_container.setStyleSheet("border: 2px solid black; border-radius: 15px;")

        display_layout.addWidget(self.canvas)

        # Add Matplotlib navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        display_layout.addWidget(self.toolbar)

        # Add display container to the provided layout
        layout.addWidget(display_container, stretch=4)  # Adjusted stretch factor

    @abstractmethod
    def _set_control_area(self, layout) -> None:
        """
        Create and set up the control area for user interaction elements.

        :param layout: The main layout to which the control area will be added.
        :type layout: Union[PySide6.QtWidgets.QVBoxLayout, PySide6.QtWidgets.QHBoxLayout, PySide6.QtWidgets.QGridLayout]
        """
        pass

    @log(logger=logger)
    def _setup_canvas(self, num_channels=1):
        """
        Set up the canvas with a given number of subplots corresponding to the number of channels.
        """
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self)
        self.canvas.setStyleSheet("border: none;")
        self.logger.info("Canvas set up successfully")

    @abstractmethod
    def _reset_actions(self, axis_type: str = "2d") -> None:
        """
        Clears the figure and reinitializes axes. This will also add a flag to the tab action history if @register_action is being used to keep track of actions. Only actions applied after the most recent call to this function will be recreated if the related file is loaded.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        """

    @log(logger=logger)
    def _set_progress_area(self, layout):
        """
        Initialize the area for progress bars within the control area.
        """
        self.progress_bar_container = QWidget()
        self.progress_bar_layout = QHBoxLayout(self.progress_bar_container)
        self.progress_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_bar_layout.setSpacing(10)

        layout.addWidget(self.progress_bar_container)
        self.progress_bar_container.hide()

        self.kill_all_button = QPushButton("❌ ALL")
        self.kill_all_button.setFixedSize(80, 30)
        self.kill_all_button.clicked.connect(self.handle_kill_all)

        self.progress_bar_layout.addWidget(
            self.kill_all_button, alignment=Qt.AlignRight
        )

    @log(logger=logger)
    @Slot(float, str)
    def update_progressbar(self, value, identifier):
        """
        Update a specific progress bar's value or create it if it doesn't exist.
        """
        self.logger.debug(
            f"Updating progress bar: Identifier='{identifier}', Value={value}"
        )

        # If task is complete, remove the progress bar
        if value >= 100:
            self.remove_progress_bar(identifier)
            return

        if identifier in self.progress_bars:
            self.logger.debug(
                f"Progress bar for '{identifier}' exists. Updating value."
            )
            # Update existing progress bar value
            self.progress_bars[identifier]["bar"].setValue(value)
        else:
            self.logger.debug(f"Creating new progress bar for '{identifier}'.")

            # Create container for each progress bar
            progress_container = QWidget()
            progress_layout = QVBoxLayout(progress_container)
            progress_layout.setContentsMargins(0, 0, 0, 0)
            progress_layout.setSpacing(2)

            # Label (row 1)
            progress_label = QLabel(f"{identifier}")

            # Row 2 (progress bar + Kill button)
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)

            # Progress bar
            progress_bar = QProgressBar()
            progress_bar.setMinimumWidth(150)
            progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            # "Kill" button
            kill_button = QPushButton("❌")
            kill_button.setFixedSize(50, 20)
            kill_button.clicked.connect(
                lambda: self.handle_kill_button(identifier)
            )  # Uses lambda because identifier is a dynamic parameter

            # Add widgets to layouts
            row_layout.addWidget(progress_bar, stretch=4)
            row_layout.addWidget(kill_button, stretch=1)

            progress_layout.addWidget(progress_label, alignment=Qt.AlignCenter)
            progress_layout.addLayout(row_layout)

            # Store references
            self.progress_bars[identifier] = {
                "bar": progress_bar,
                "label": progress_label,
                "button": kill_button,
                "layout": progress_layout,
                "container": progress_container,
            }

            # Add progress container before the "Kill All" button
            self.progress_bar_layout.insertWidget(
                self.progress_bar_layout.count() - 1, progress_container
            )
            self.progress_bar_container.show()

            # Set initial value
            progress_bar.setValue(value)

    @log(logger=logger)
    def update_actions_from_json(self, actions):
        for _, val in actions.items():
            function = val.get("function")
            function = getattr(self, function, None)
            if function:
                if callable(function):
                    args = val.get("args")
                    kwargs = val.get("kwargs")
                    function(*args, **kwargs)

    @log(logger=logger)
    def _save_actions_to_json(self):
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save File", "", "JSON Files (*.json)", options=options
        )
        if filename:
            self.save_tab_action_history.emit(filename)

    @log(logger=logger)
    def _load_actions_from_json(self):
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "JSON Files (*.json)", options=options
        )
        if filename:
            self.load_actions_from_json.emit(filename)

    @log(logger=logger)
    def handle_edit_triggered(self, metaclass, key):
        """
        Emit a signal to trigger the saving process for a data plugin, passing the appropriate
        arguments to handle editing plugin settings.

        :param key: the identifier of the plugin to be edited
        :type key: str
        :param metaclass: The class type of the plugin
        :type metaclass: str

        """
        self.logger.info(
            f"RawDataView: Settings edit request emitted for metaclass: {metaclass}, plugin: {key}"
        )
        # Ensure call_args is prepared with metaclass and plugin_name
        call_args = (
            metaclass,
            key,
        )  # This is a tuple of the arguments expected by 'edit_plugin_settings'
        # Emit the signal with correct arguments
        self.data_plugin_controller_signal.emit(
            metaclass, key, "edit_plugin_settings", call_args, "", ()
        )

    @log(logger=logger)
    def handle_add_triggered(self, metaclass: str):
        """
        Trigger addition of a new plugin by prompting for a subclass.

        :param metaclass: The type of plugin to add (e.g., 'MetaReader')
        """

        subclasses = self.available_subclasses.get(metaclass, [])
        if not subclasses:
            QMessageBox.warning(
                self, "No Subclasses", f"No subclasses available for {metaclass}."
            )
            return

        # Prompt the user to select a subclass
        subclass, ok = QInputDialog.getItem(
            self,
            f"Select {metaclass} subclass",
            f"Available {metaclass} subclasses:",
            subclasses,
            0,
            False,
        )

        if ok and subclass:
            self.logger.info(
                f"Add request emitted for metaclass: {metaclass}, subclass: {subclass}"
            )
            self.create_plugin.emit(metaclass, subclass)

    @log(logger=logger)
    def handle_delete_triggered(self, metaclass, key):
        """
        Emit a signal to trigger the delete process for a data plugin, passing the identifier.

        :param key: the identifier of the plugin to be deleted
        :type key: str
        :param metaclass: The class type of the plugin
        :type metaclass: str

        """
        self.logger.info(
            f"Delete request emitted for metaclass: {metaclass}, plugin: {key}"
        )
        # Ensure call_args is prepared with metaclass and plugin_name
        call_args = (
            metaclass,
            key,
        )  # This is a tuple of the arguments expected by 'edit_plugin_settings'
        # Emit the signal with correct arguments
        self.data_plugin_controller_signal.emit(
            metaclass, key, "delete_plugin", call_args, "", ()
        )

    @log(logger=logger)
    def remove_progress_bar(self, identifier):
        """
        Remove a specific progress bar and its components when a task is complete.
        """
        with self.lock:
            if identifier in self.progress_bars:
                progress_data = self.progress_bars.pop(identifier)

                # Remove widget from layout
                self.progress_bar_layout.removeWidget(progress_data["container"])
                progress_data["container"].deleteLater()

                # Hide the container if no progress bars remain
                if not self.progress_bars:
                    self.progress_bar_container.hide()

    @log(logger=logger)
    def handle_kill_button(self, identifier):
        """
        Handle the kill button click event for individual workers.
        """

        controller_name = self.__class__.__name__.replace("View", "Controller")

        self.logger.info(f"Kill button pressed for {identifier}")

        # Emit the kill_worker signal with the modified controller name, key, and channel
        self.kill_worker.emit(controller_name, identifier)

    @log(logger=logger)
    def handle_kill_all(self):
        """
        Handle the 'Kill All' button click event.
        """
        self.logger.info("Kill All button pressed. Stopping all processes.")
        controller_name = self.__class__.__name__.replace("View", "Controller")
        self.kill_all_workers.emit(
            controller_name
        )  # Emits a signal to stop all processes

    # public API, must be implemented by sublcasses
    @abstractmethod
    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """
        Called whenever a new plugin is instantiated elsewhere in the app, to keep an up-to-date
        list of possible data sources for use by this plugin.

        :param available_plugins: Dict of lists keyed by MetaClass, listing the identifiers of all
                                  instantiated plugins throughout the app.
        :type available_plugins: Dict[str, list[str]]
        """
        self.logger.info(f"View updated: {available_plugins}")
        self.available_plugins = available_plugins

    @log(logger=logger)
    def _parse_event_indices(
        self, indices: str, allow_floats: bool = False
    ) -> list[tuple[int, int]]:
        """
        Parse '7-10,12' → [(7,10), (12,12)]
        If allow_floats=True, accepts '1.5-4.5,6' → [(1.5, 4.5), (6.0, 6.0)]
        """
        result = []
        caster = float if allow_floats else int

        for segment in indices.split(","):
            segment = segment.strip()
            if "-" in segment:
                try:
                    start, end = map(caster, segment.split("-"))
                    result.append((start, end))
                except ValueError:
                    self.logger.warning(f"Invalid range segment: {segment}")
            elif segment:
                try:
                    val = caster(segment)
                    result.append((val, val))
                except ValueError:
                    self.logger.warning(f"Invalid index segment: {segment}")

        return result

    @log(logger=logger)
    def _shift_ranges(
        self, ranges: list[tuple[int, int]], direction: str, offset: int
    ) -> list[tuple[int, int]]:
        """Shift each tuple range left or right."""
        shifted = []
        for start, end in ranges:
            if start == end:  # Sigle index
                val = start + offset if direction == "right" else start - offset
                shifted.append((val, val))
            else:  # Range
                new_start = (
                    end + offset
                    if direction == "right"
                    else ((2 * start) - end) - offset
                )
                new_end = (
                    ((2 * end) - start) + offset
                    if direction == "right"
                    else start - offset
                )
                shifted.append((new_start, new_end))
        return shifted

    @log(logger=logger)
    def _merge_ranges(self, ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Merge overlapping or contiguous ranges."""
        merged: list[tuple[int, int]] = []
        for start, end in sorted(ranges):
            if not merged or merged[-1][1] < start - 1:
                merged.append((start, end))
            else:
                last_start, last_end = merged[-1]
                merged[-1] = (last_start, max(last_end, end))
        return merged

    @log(logger=logger)
    def _format_ranges(self, ranges: list[tuple[int, int]]) -> str:
        """Format list of tuples into '8-11,13'"""
        return ",".join(
            f"{start}-{end}" if start != end else str(start) for start, end in ranges
        )

    @log(logger=logger)
    def _expand_event_indices(self, indices_str: str) -> list[int]:
        """
        Expand '1,3-5' → [1,3,4,5], exclude segments with negatives.
        """
        result: Set[int] = set()
        for segment in indices_str.split(","):
            segment = segment.strip()
            try:
                if "-" in segment:
                    parts = segment.split("-")
                    if len(parts) != 2:
                        raise ValueError
                    start, end = map(int, parts)
                    if start < 0 or end < 0:
                        continue
                    result.update(range(start, end + 1))
                else:
                    val = int(segment)
                    if val < 0:
                        continue
                    result.add(val)
            except ValueError:
                continue
        return sorted(result)

    # private API, should generally be left alone by subclasses

    @log(logger=logger)
    def _set_display_area_base(self, layout) -> None:
        """
        Create and set up the display area for the plot canvas.

        :param layout: The main layout to which the display area will be added.
        :type layout: Union[PySide6.QtWidgets.QVBoxLayout, PySide6.QtWidgets.QHBoxLayout, PySide6.QtWidgets.QGridLayout]
        """
        self.dataDisplayArea = QWidget(self)
        self.dataDisplayArea.setStyleSheet(
            "background-color: rgb(255, 255, 255); border-radius: 25px; border: 1px solid;"
        )

        self.dataDisplayAreaLayout = QHBoxLayout(self.dataDisplayArea)
        layout.addWidget(self.dataDisplayArea, stretch=2)
        self._set_custom_display_area(layout)

    @log(logger=logger)
    def _setup_ui(self) -> None:
        """
        Set up the user interface with a main layout containing a display area for
        the plot canvas and a control area for user interaction elements.
        """
        self.setObjectName("MetaTabWidget")

        mainLayout = QVBoxLayout(self)

        # Adjusted layout to give more space to display area
        display_area_container = QWidget()
        display_area_layout = QVBoxLayout(display_area_container)
        self._set_custom_display_area(display_area_layout)
        mainLayout.addWidget(
            display_area_container, stretch=20
        )  # Increased stretch factor for display area

        self._set_control_area(mainLayout)
        self._set_progress_area(mainLayout)
        mainLayout.setStretch(0, 8)  # Increase stretch factor for display area
        mainLayout.setStretch(1, 1)  # Decrease stretch factor for control area

    @log(logger=logger)
    def _logscale_and_filter_multiple_columns(self, *data, log_flags=None):
        """
        Filters multiple data columns for NaN values and applies logarithmic scaling.

        This function takes an arbitrary number of 1D NumPy arrays as input.
        It first removes any data points (rows) where any of the input arrays
        contain a NaN value.
        Then, it optionally applies a base-10 logarithmic scale to specified
        columns. When applying log scale, it handles potentially negative data
        by 'rectifying' it based on its average sign and filters out any
        non-positive values after rectification. This filtering is applied
        sequentially, meaning filtering based on one column affects all others.

        :param data: A variable number of 1D NumPy arrays representing the data columns.
        :type data: npt.NDArray
        :param log_flags: (list or tuple, optional): A list or tuple of booleans, one for each data array. If True, the corresponding array, will be log-scaled. If None, no log scaling is applied. Defaults to None.
        :type log_flags: Union[List[bool],Tuple[bool]]
        :return: Tuple[Optional[npt.NDArray]]: A tuple containing the processed 1D NumPy arrays. The number of arrays returned matches the number of input arrays.
        """
        if not data:
            return ()

        num_arrays = len(data)
        current_data = list(data)  # Work with a list

        # --- Input Validation ---
        if log_flags is None:
            log_flags = [False] * num_arrays
        elif not isinstance(log_flags, (list, tuple)) or len(log_flags) != num_arrays:
            raise ValueError(
                "log_flags must be a list or tuple with the same length as the number of data arguments."
            )

        num_points_init = len(current_data[0])

        # --- NaN Filtering ---
        # Create a combined mask to filter NaNs across all arrays
        mask = np.ones(num_points_init, dtype=bool)
        for d in current_data:
            mask &= ~np.isnan(d)

        # Apply the NaN mask
        current_data = [d[mask] for d in current_data]

        num_points_after_nan = len(current_data[0])
        num_points_nan = num_points_init - num_points_after_nan
        if num_points_nan > 0:
            self.add_text_to_display.emit(
                f"Removed {num_points_nan} out of {num_points_init} points that contained NaN",
                self.__class__.__name__,
            )

        # --- Log Scaling (Sequential) ---
        num_points_before_log = num_points_after_nan

        for i in range(num_arrays):
            if log_flags[i]:
                d = current_data[i]

                # Skip if no data left or data is already scaled
                if len(d) == 0:
                    continue

                # Rectify: Flip data based on average sign, then filter > 0
                avg = np.average(d)
                sign = (
                    np.sign(avg) if avg != 0 else 1
                )  # Default to positive sign if avg is zero
                rectified = sign * d

                log_mask = rectified > 0

                # Apply the mask to *all* current data arrays
                current_data = [arr[log_mask] for arr in current_data]

                current_data[i] = np.log10(
                    current_data[i] * sign
                )  # Apply log10 to the *rectified* value

        num_points_final = len(current_data[0])
        num_points_log_removed = num_points_before_log - num_points_final
        if num_points_log_removed > 0:
            self.add_text_to_display.emit(
                f"Removed {num_points_log_removed} out of {num_points_before_log} points that could not be logscaled",
                self.__class__.__name__,
            )

        return tuple(current_data)

    def _logscale_and_filter_dataframe(self, df, log_columns=None):
        """
        In-place filters a DataFrame for NaN values and applies logarithmic scaling to specified columns.

        This function:

        - Removes rows with NaN values in any column (modifies df in-place).
        - Applies log10 scaling to specified columns after rectifying based on average sign.
        - Sequentially removes rows with non-positive values in log columns.

        Args:
            df (pd.DataFrame): Input DataFrame with numerical data. Will be modified in-place.
            log_columns (list of str, optional): List of column names to apply log scaling.
            If None, no log scaling is applied.

        Returns:
            pd.DataFrame: The same DataFrame reference, filtered and transformed in-place.
        """

        if df.empty:
            return df

        # Create a copy to avoid SettingWithCopyWarning
        df = df.copy()

        if log_columns is None:
            log_columns = []

        if not all(col in df.columns for col in log_columns):
            missing = [col for col in log_columns if col not in df.columns]
            raise ValueError(f"Columns not found in DataFrame: {missing}")

        num_points_init = len(df)

        # Drop NaNs in place
        df.dropna(inplace=True)
        num_points_after_nan = len(df)
        num_points_nan = num_points_init - num_points_after_nan

        if num_points_nan > 0:
            self.add_text_to_display.emit(
                f"Removed {num_points_nan} out of {num_points_init} points that contained NaN",
                self.__class__.__name__,
            )

        num_points_before_log = len(df)

        for col in log_columns:
            if df.empty:
                break

            d = df[col].values
            avg = np.average(d)
            sign = np.sign(avg) if avg != 0 else 1

            rectified = sign * d
            log_mask = rectified > 0

            # Filter rows based on log_mask
            df = df.loc[log_mask].copy()

            # Apply log10 transformation using .loc
            df[col] = df[col].astype(np.float64)
            df.loc[:, col] = np.log10(sign * df[col]).astype(np.float64)

        num_points_final = len(df)
        num_points_log_removed = num_points_before_log - num_points_final

        if num_points_log_removed > 0:
            self.add_text_to_display.emit(
                f"Removed {num_points_log_removed} out of {num_points_before_log} points that could not be logscaled",
                self.__class__.__name__,
            )

        return df
