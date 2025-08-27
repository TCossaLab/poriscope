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

import json
import logging
import os
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSize, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from poriscope.configs.utils import get_icon
from poriscope.utils.LogDecorator import log
from poriscope.views.float_range_line_edit import FloatRangeLineEdit
from poriscope.views.integer_range_line_edit import IntegerRangeLineEdit
from poriscope.views.widgets.multiselect import MultiSelectComboBox


class RawDataControls(QWidget):
    actionTriggered = Signal(
        str, str, tuple
    )  # Signal to trigger an action in the controller (submodel_name, action_name, args)
    is_signal_connected = False  # Class-level flag to check if signal is connected
    logger = logging.getLogger(__name__)

    edit_processed = Signal(str, str)
    add_processed = Signal(str)
    delete_processed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger.info("Initializing RawDataControls")
        self.setupUi()
        self.connect_signals()
        self.logger.info("RawDataControls initialized")
        self.validate_inputs()
        self.max_range_size = 16
        self.active_popups = {}

    def setupUi(self):
        self.logger.info("Setting up UI")
        self.setObjectName("Form")
        self.resize(663, 295)

        # Main layout
        main_layout = QVBoxLayout(self)

        # GroupBox and its layout
        self.groupBox = QGroupBox(self)
        self.groupBox.setObjectName("groupBox")
        group_layout = QGridLayout(self.groupBox)

        # First Column: Reader section
        reader_layout = QHBoxLayout()
        self.readers_label = self.createLabel(self.groupBox, 12, "READER")
        self.readers_comboBox = self.create_comboBox(self.groupBox)
        self.readers_comboBox.setObjectName("readersComboBox")
        self.readers_comboBox.currentIndexChanged.connect(self.on_parameter_changed)
        self.readers_info_button = self.create_info_button(
            self.groupBox, self.readers_comboBox, "Edit selected reader", "MetaReader"
        )
        self.readers_add_button = self.create_add_button(
            self.groupBox, self.readers_comboBox, "Add reader", "MetaReader"
        )
        self.readers_delete_button = self.create_delete_button(
            self.groupBox, self.readers_comboBox, "Delete reader", "MetaReader"
        )

        reader_layout.addWidget(self.readers_label)
        reader_layout.addWidget(self.readers_add_button)
        reader_layout.addWidget(self.readers_info_button)
        reader_layout.addWidget(self.readers_delete_button)
        reader_layout.addStretch(1)
        group_layout.addLayout(reader_layout, 0, 0)
        group_layout.addWidget(self.readers_comboBox, 1, 0)

        self.start_time_lineEdit = FloatRangeLineEdit(self.groupBox)
        self.start_time_lineEdit.setObjectName("startTimeLineEdit")
        self.start_time_lineEdit.setPlaceholderText("Enter duration (0-5 or 1.5-6.3)")
        group_layout.addWidget(self.start_time_lineEdit, 2, 0)

        # UPDATE TRACE CONTAINER
        self.update_trace_widget = QWidget(self.groupBox)
        update_trace_layout = QHBoxLayout(self.update_trace_widget)
        update_trace_layout.setContentsMargins(0, 0, 0, 0)
        update_trace_layout.setSpacing(5)

        # Left arrow button
        self.left_trace_arrow_button = QPushButton(self.update_trace_widget)
        self.left_trace_arrow_button.setIcon(get_icon("arrow-left.svg"))
        self.left_trace_arrow_button.setIconSize(QSize(16, 16))
        self.left_trace_arrow_button.setFixedWidth(30)

        # Main Update Trace button
        self.update_trace_pushButton = self.createButton(
            self.groupBox, "Update Trace", bold=True
        )
        self.update_trace_pushButton.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        # Right arrow button
        self.right_trace_arrow_button = QPushButton(self.update_trace_widget)
        self.right_trace_arrow_button.setIcon(get_icon("arrow-right.svg"))
        self.right_trace_arrow_button.setIconSize(QSize(16, 16))
        self.right_trace_arrow_button.setFixedWidth(30)

        update_trace_layout.addWidget(self.left_trace_arrow_button)
        update_trace_layout.addWidget(self.update_trace_pushButton)
        update_trace_layout.addWidget(self.right_trace_arrow_button)

        group_layout.addWidget(self.update_trace_widget, 3, 0)

        self.calculate_baseline_button = self.createButton(
            self.groupBox, "Get baseline stats", bold=True
        )
        group_layout.addWidget(self.calculate_baseline_button, 4, 0)

        # Second Column: Filters section
        filter_layout = QHBoxLayout()
        self.filters_label = self.createLabel(self.groupBox, 12, "FILTER")
        self.filters_comboBox = self.create_comboBox(self.groupBox)
        self.filters_info_button = self.create_info_button(
            self.groupBox, self.filters_comboBox, "Edit selected filter", "MetaFilter"
        )
        self.filters_add_button = self.create_add_button(
            self.groupBox, self.filters_comboBox, "Add filter", "MetaFilter"
        )
        self.filters_delete_button = self.create_delete_button(
            self.groupBox, self.filters_comboBox, "Delete filter", "MetaFilter"
        )

        filter_layout.addWidget(self.filters_label)
        filter_layout.addWidget(self.filters_add_button)
        filter_layout.addWidget(self.filters_info_button)
        filter_layout.addWidget(self.filters_delete_button)
        filter_layout.addStretch(1)
        self.filters_comboBox.currentIndexChanged.connect(self.on_parameter_changed)

        group_layout.addLayout(filter_layout, 0, 1)
        group_layout.addWidget(self.filters_comboBox, 1, 1)

        channel_lbl = self.createLabel(self.groupBox, 12, "CHANNEL")
        self.channel_comboBox = MultiSelectComboBox(self.groupBox)
        self.channel_comboBox.setObjectName("channelComboBox")
        group_layout.addWidget(channel_lbl, 2, 1)
        group_layout.addWidget(self.channel_comboBox, 3, 1)
        self.channel_comboBox.selectionChanged.connect(self.validate_inputs)

        self.update_psd_pushButton = self.createButton(
            self.groupBox, "Update PSD", bold=True
        )
        group_layout.addWidget(self.update_psd_pushButton, 4, 1)

        # Third Column: Eventfinders
        eventfinders_layout = QHBoxLayout()
        self.eventfinders_label = self.createLabel(self.groupBox, 12, "EVENTFINDER")
        self.eventfinders_comboBox = self.create_comboBox(self.groupBox)
        self.eventfinders_info_button = self.create_info_button(
            self.groupBox,
            self.eventfinders_comboBox,
            "Edit selected eventfinder",
            "MetaEventFinder",
        )
        self.eventfinders_add_button = self.create_add_button(
            self.groupBox,
            self.eventfinders_comboBox,
            "Add eventfinder",
            "MetaEventFinder",
        )
        self.eventfinders_delete_button = self.create_delete_button(
            self.groupBox,
            self.eventfinders_comboBox,
            "Delete eventfinder",
            "MetaEventFinder",
        )

        eventfinders_layout.addWidget(self.eventfinders_label)
        eventfinders_layout.addWidget(self.eventfinders_add_button)
        eventfinders_layout.addWidget(self.eventfinders_info_button)
        eventfinders_layout.addWidget(self.eventfinders_delete_button)

        eventfinders_layout.addStretch(1)
        self.eventfinders_comboBox.currentIndexChanged.connect(
            self.on_parameter_changed
        )

        group_layout.addLayout(eventfinders_layout, 0, 2)
        group_layout.addWidget(self.eventfinders_comboBox, 1, 2)

        button_layout = QHBoxLayout()
        self.find_events_pushButton = self.createButton(
            self.groupBox, "Find Events", bold=True
        )

        self.timer_pushButton = QPushButton("", self.groupBox)
        self.timer_pushButton.setIcon(get_icon("stopwatch.svg"))
        self.timer_pushButton.setToolTip("Time Event Fitting")

        button_layout.addWidget(self.find_events_pushButton)
        button_layout.addWidget(self.timer_pushButton)
        group_layout.addLayout(button_layout, 2, 2)

        self.event_index_lineEdit = IntegerRangeLineEdit(self.groupBox)
        self.event_index_lineEdit.setObjectName("eventIndexLineEdit")
        self.event_index_lineEdit.setPlaceholderText("Event index (e.g., 5 or 10-25)")
        group_layout.addWidget(self.event_index_lineEdit, 3, 2)

        self.plot_layout_widget = QWidget(self.groupBox)
        plot_events_layout = QHBoxLayout(self.plot_layout_widget)
        plot_events_layout.setContentsMargins(0, 0, 0, 0)
        plot_events_layout.setSpacing(5)

        # Left arrow button
        self.left_plot_arrow_button = QPushButton(self.plot_layout_widget)
        self.left_plot_arrow_button.setIcon(get_icon("arrow-left.svg"))
        self.left_plot_arrow_button.setIconSize(QSize(16, 16))
        self.left_plot_arrow_button.setFixedWidth(30)

        # Plot events button
        self.plot_events_pushButton = self.createButton(
            self.plot_layout_widget, "Plot Events", bold=True
        )

        # Right arrow button
        self.right_plot_arrow_button = QPushButton(self.plot_layout_widget)
        self.right_plot_arrow_button.setIcon(get_icon("arrow-right.svg"))
        self.right_plot_arrow_button.setIconSize(QSize(16, 16))
        self.right_plot_arrow_button.setFixedWidth(30)

        plot_events_layout.addWidget(self.left_plot_arrow_button)
        plot_events_layout.addWidget(self.plot_events_pushButton)
        plot_events_layout.addWidget(self.right_plot_arrow_button)

        group_layout.addWidget(self.plot_layout_widget, 4, 2)

        # Fourth Column: Writers section
        writer_layout = QHBoxLayout()
        self.writers_label = self.createLabel(self.groupBox, 12, "WRITER")
        self.writers_comboBox = self.create_comboBox(self.groupBox)
        self.writers_info_button = self.create_info_button(
            self.groupBox, self.writers_comboBox, "Edit selected writer", "MetaWriter"
        )
        self.writers_add_button = self.create_add_button(
            self.groupBox, self.writers_comboBox, "Add writer", "MetaWriter"
        )
        self.writers_delete_button = self.create_delete_button(
            self.groupBox, self.writers_comboBox, "Delete writer", "MetaWriter"
        )

        writer_layout.addWidget(self.writers_label)
        writer_layout.addWidget(self.writers_add_button)
        writer_layout.addWidget(self.writers_info_button)
        writer_layout.addWidget(self.writers_delete_button)
        writer_layout.addStretch(1)
        self.writers_comboBox.currentIndexChanged.connect(self.on_parameter_changed)

        group_layout.addLayout(writer_layout, 0, 3)
        group_layout.addWidget(self.writers_comboBox, 1, 3)

        self.commit_btn = self.createButton(self.groupBox, "Commit Events", bold=True)
        group_layout.addWidget(self.commit_btn, 2, 3)

        self.export_plot_data_pushButton = self.createButton(
            self.groupBox, "Export Plot Data", bold=True
        )
        button_layout = QVBoxLayout()
        button_layout.addWidget(self.export_plot_data_pushButton)
        group_layout.addLayout(button_layout, 4, 3)

        # Add groupBox to the main layout
        main_layout.addWidget(self.groupBox)
        self.retranslateUi()
        self.logger.info("UI setup complete")

    def create_info_button(self, parent, comboBox, info_text, metaclass):
        """Creates an info button linked to the corresponding combobox."""
        button = QToolButton(parent)
        button.setIcon(get_icon("edit.png"))
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet("border: none; background: transparent;")
        button.setToolTip(info_text)
        button.clicked.connect(
            lambda _, comboBox=comboBox, metaclass=metaclass: self.show_plugin_edit_manager(
                comboBox, metaclass
            )
        )
        # Disable initially if no valid item is selected
        button.setEnabled(
            comboBox.count() > 0
            and comboBox.currentIndex() != -1
            and not self.is_placeholder_item(comboBox)
        )
        comboBox.currentIndexChanged.connect(
            lambda _, button=button, comboBox=comboBox: self.toggle_info_button(
                button, comboBox
            )
        )
        return button

    def create_add_button(self, parent, comboBox, add_text, metaclass):
        """Creates an add button linked to the corresponding combobox."""
        button = QToolButton(parent)
        button.setIcon(get_icon("plus-square-dotted.svg"))
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet("border: none; background: transparent;")
        button.setToolTip(add_text)
        button.clicked.connect(
            lambda: self.show_plugin_add_manager(comboBox, metaclass)
        )
        button.setEnabled(True)
        return button

    def create_delete_button(self, parent, comboBox, info_text, metaclass):
        """Creates a delete button linked to the corresponding combobox."""
        button = QToolButton(parent)
        button.setIcon(get_icon("trash.svg"))
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet("border: none; background: transparent;")
        button.setToolTip(info_text)
        button.clicked.connect(
            lambda _, comboBox=comboBox, metaclass=metaclass: self.delete_plugin(
                comboBox, metaclass
            )
        )
        # Disable initially if no valid item is selected
        button.setEnabled(
            comboBox.count() > 0
            and comboBox.currentIndex() != -1
            and not self.is_placeholder_item(comboBox)
        )
        comboBox.currentIndexChanged.connect(
            lambda _, button=button, comboBox=comboBox: self.toggle_info_button(
                button, comboBox
            )
        )
        return button

    def toggle_info_button(self, button, comboBox):
        """Enables or disables the info button based on the comboBox selection and item count."""
        button.setEnabled(
            comboBox.count() > 0
            and comboBox.currentIndex() != -1
            and not self.is_placeholder_item(comboBox)
        )

    def is_placeholder_item(self, comboBox):
        """Returns True if the combobox contains a placeholder like 'No Reader', 'No Writer', etc."""
        return comboBox.currentText() in [
            "No Reader",
            "No Writer",
            "No Filter",
            "No Eventfinder",
        ]

    def show_plugin_edit_manager(self, comboBox, metaclass):
        """Displays the plugin manager with details for the selected item from the combobox."""
        key = comboBox.currentText()
        self.edit_processed.emit(metaclass, key)

    def show_plugin_add_manager(self, comboBox, metaclass):
        """Displays the plugin manager with details for the selected item from the combobox."""

        self.add_processed.emit(metaclass)

    def delete_plugin(self, comboBox, metaclass):
        """Deletes the plugin corresponding tot he current ComboBox selection"""

        key = comboBox.currentText()
        self.delete_processed.emit(metaclass, key)

    def clear_popup_reference(self, comboBox):
        """Clears the reference to the popup when it is closed."""
        if comboBox in self.active_popups:
            self.active_popups.pop(comboBox)

    def get_plugin_data(self):
        """Fetch plugin data from a JSON file located in the application's local data directory."""
        localappdata = os.getenv("LOCALAPPDATA")
        if localappdata is None:
            raise IOError("Unable to resolve LOCALAPPDATA folder")
        file_path = Path(localappdata, "nanolyzer", "session", "plugin_history.json")
        try:
            with open(file_path, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            self.logger.error(f"Plugin data file not found at {file_path}")
        except json.JSONDecodeError:
            self.logger.error("Error decoding JSON from plugin data file")
        return {}

    def get_nested_value(d, keys, default=None):
        """
        Recursively fetches values from nested dictionaries.
        :param d: The dictionary to fetch data from.
        :param keys: List of keys to navigate through the nested dictionary.
        :param default: Default value if any key is not found.
        :return: Value fetched from the dictionary or default.
        """
        assert isinstance(keys, list), "Keys must be provided as a list of key names"
        for key in keys:
            if d and isinstance(d, dict):
                d = d.get(key)
            else:
                return default
        return d if d is not None else default

    def validate_inputs(self):
        is_trace_psd_valid = True
        is_commit_valid = True
        is_plot_events_valid = True
        is_find_events_valid = True

        # Gather relevant inputs
        reader = self.readers_comboBox.currentText()
        start_time_valid = self.start_time_lineEdit.isValid()
        start_time = self.start_time_lineEdit.get_start() if start_time_valid else None
        duration = self.start_time_lineEdit.get_duration() if start_time_valid else None
        channels = self.channel_comboBox.getSelectedItems()
        event_index_valid = self.event_index_lineEdit.isValid()
        writer = self.writers_comboBox.currentText()
        self.event_index_lineEdit.get_values()
        eventfinder = self.eventfinders_comboBox.currentText()

        # Debug logging
        self.logger.debug(
            f"Reader: '{reader}', Start Time: '{start_time}', Duration: '{duration}', Channels: {channels}, Event Index Valid: {event_index_valid}"
        )

        if not reader or reader == "No Reader":
            self.logger.debug("No reader selected")
            is_trace_psd_valid = False
            is_find_events_valid = False
            is_plot_events_valid = False
        if not start_time_valid or duration is None or duration == 0:
            self.logger.debug("Start time input is invalid or empty")
            is_trace_psd_valid = False
        if not channels:
            self.logger.debug("No channels selected")
            is_trace_psd_valid = False
            is_find_events_valid = False
            is_plot_events_valid = False

        # Validate event index input
        if not event_index_valid:
            self.logger.debug("Event index is invalid")
            is_plot_events_valid = (
                False  # Disable Plot Events button if event index is not valid
            )

        if not writer or writer == "No Writer":
            self.logger.debug("No writer selected")
            is_commit_valid = False

        if not eventfinder or eventfinder == "No Eventfinder":
            self.logger.debug("No eventfinder selected")
            is_find_events_valid = False

        # Enable or disable buttons based on validation
        self.left_trace_arrow_button.setEnabled(is_trace_psd_valid)
        self.update_trace_pushButton.setEnabled(is_trace_psd_valid)
        self.right_trace_arrow_button.setEnabled(is_trace_psd_valid)
        self.calculate_baseline_button.setEnabled(is_trace_psd_valid)
        self.update_psd_pushButton.setEnabled(is_trace_psd_valid)
        self.commit_btn.setEnabled(is_commit_valid)
        self.left_plot_arrow_button.setEnabled(is_plot_events_valid)
        self.plot_events_pushButton.setEnabled(is_plot_events_valid)
        self.right_plot_arrow_button.setEnabled(is_plot_events_valid)
        self.find_events_pushButton.setEnabled(is_find_events_valid)

    def connect_signals(self):
        self.left_trace_arrow_button.clicked.connect(
            lambda: self.on_button_clicked("left_arrow")
        )
        self.update_trace_pushButton.clicked.connect(
            lambda: self.on_button_clicked("update_trace")
        )
        self.right_trace_arrow_button.clicked.connect(
            lambda: self.on_button_clicked("right_arrow")
        )
        self.calculate_baseline_button.clicked.connect(
            lambda: self.on_button_clicked("calculate_baseline")
        )
        self.update_psd_pushButton.clicked.connect(
            lambda: self.on_button_clicked("update_psd")
        )
        self.export_plot_data_pushButton.clicked.connect(
            lambda: self.on_button_clicked("export_plot_data")
        )
        self.find_events_pushButton.clicked.connect(
            lambda: self.on_button_clicked("find_events")
        )
        self.timer_pushButton.clicked.connect(lambda: self.on_button_clicked("timer"))
        self.left_plot_arrow_button.clicked.connect(
            lambda: self.on_button_clicked("backward_events")
        )
        self.plot_events_pushButton.clicked.connect(
            lambda: self.on_button_clicked("plot_events")
        )
        self.right_plot_arrow_button.clicked.connect(
            lambda: self.on_button_clicked("forward_events")
        )
        self.commit_btn.clicked.connect(lambda: self.on_button_clicked("commit_events"))
        self.logger.info("Signals connected")

        # Ensure that the validate_inputs method is called when the inputs change
        self.start_time_lineEdit.textChanged.connect(self.validate_inputs)
        self.event_index_lineEdit.textChanged.connect(self.validate_inputs)
        self.channel_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.filters_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.eventfinders_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.readers_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.writers_comboBox.currentIndexChanged.connect(self.validate_inputs)

    def on_parameter_changed(self):
        parameters = self.collect_parameters()
        self.logger.debug(
            f"Emitting actionTriggered due to parameter change with parameters {parameters}"
        )
        self.actionTriggered.emit("RawDataModel", "parameter_changed", (parameters,))

    def create_comboBox(self, parent):
        comboBox = QComboBox(parent)
        comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return comboBox

    def createButton(self, parent, text, bold=False):
        button = QPushButton(parent)
        font = QFont()
        font.setBold(bold)
        font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        button.setFont(font)
        button.setText(QCoreApplication.translate("Form", text, None))
        button.setCheckable(True)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.setStyleSheet("")  # Resetting to default style
        return button

    def createLabel(self, parent, pointSize, text):
        label = QLabel(parent)
        font = QFont()
        font.setPointSize(pointSize - 6)
        label.setFont(font)
        label.setText(QCoreApplication.translate("Form", text, None))
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return label

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate("Form", "Form", None))
        self.readers_comboBox.setCurrentText("")

    def collect_parameters(self):
        self.logger.info("Collecting parameters")

        # Initialize with default values to handle possible None values
        parameters = {
            "reader": self.readers_comboBox.currentText() or "No Reader",
            "filter": self.filters_comboBox.currentText() or "No Filter",
            "writer": self.writers_comboBox.currentText() or "No Writer",
            "eventfinder": self.eventfinders_comboBox.currentText() or "No Eventfinder",
            "start_time": None,
            "length": None,
            "event_index": [],
            "channel": [item for item in self.channel_comboBox.getSelectedItems()],
        }

        # Collect start time and length if valid
        if self.start_time_lineEdit.isValid():
            parameters["start_time"] = self.start_time_lineEdit.get_start()
            parameters["length"] = self.start_time_lineEdit.get_duration()

        # Collect event index values if valid
        if self.event_index_lineEdit.isValid():
            parameters["event_index"] = self.event_index_lineEdit.get_values()

        self.logger.debug(f"Collected parameters: {parameters}")
        return parameters

    def on_button_clicked(self, button_type):
        parameters = self.collect_parameters()
        self.logger.debug(
            f"Emitting actionTriggered for {button_type} with parameters {parameters}"
        )

        if button_type == "left_arrow":
            self.actionTriggered.emit(
                "RawDataModel", "shift_trace_backward", (parameters,)
            )
        elif button_type == "update_trace":
            self.actionTriggered.emit(
                "RawDataModel", "load_data_and_update_plot", (parameters,)
            )
        elif button_type == "right_arrow":
            self.actionTriggered.emit(
                "RawDataModel", "shift_trace_forward", (parameters,)
            )
        elif button_type == "calculate_baseline":
            self.actionTriggered.emit(
                "RawDataModel", "get_baseline_stats", (parameters,)
            )
        elif button_type == "update_psd":
            self.actionTriggered.emit(
                "RawDataModel", "load_data_and_update_psd", (parameters,)
            )
        elif button_type == "export_plot_data":
            self.actionTriggered.emit("RawDataModel", "export_plot_data", (parameters,))
        elif button_type == "find_events":
            self.actionTriggered.emit("RawDataModel", "find_events", (parameters,))
        elif button_type == "timer":
            self.actionTriggered.emit("RawDataModel", "timer", (parameters,))
        elif button_type == "backward_events":
            self.actionTriggered.emit(
                "RawDataModel", "shift_events_backward", (parameters,)
            )
        elif button_type == "plot_events":
            self.actionTriggered.emit("RawDataModel", "plot_events", (parameters,))
        elif button_type == "forward_events":
            self.actionTriggered.emit(
                "RawDataModel", "shift_events_forward", (parameters,)
            )
        elif button_type == "commit_events":
            self.actionTriggered.emit("RawDataModel", "commit_events", (parameters,))

        # Automatically uncheck the button after it is clicked
        button_mapping = {
            "left_arrow": self.left_trace_arrow_button,
            "update_trace": self.update_trace_pushButton,
            "right_arrow": self.right_trace_arrow_button,
            "calculate_baseline": self.calculate_baseline_button,
            "update_psd": self.update_psd_pushButton,
            "export_plot_data": self.export_plot_data_pushButton,
            "commit_events": self.commit_btn,
            "find_events": self.find_events_pushButton,
            "timer": self.timer_pushButton,
            "backward_events": self.left_plot_arrow_button,
            "forward_events": self.right_plot_arrow_button,
            "plot_events": self.plot_events_pushButton,
        }

        button_mapping.get(button_type, lambda: None).setChecked(False)

    def update_channels(self, channels):
        """
        Updates the channels displayed in the MultiSelectComboBox widget and restores previous selections.
        """
        self.logger.info(f"Updating channels to {channels}")

        # Get current selections from the MultiSelectComboBox
        current_selections = self.channel_comboBox.getSelectedItems()
        self.logger.debug(
            f"Current selections before restoration: {current_selections}"
        )

        # Clear and add new channels to the MultiSelectComboBox
        new_channels = [str(i) for i in channels]
        self.channel_comboBox.addItems(new_channels)
        self.logger.debug(f"Added channels: {new_channels}")

        # Restore previous selections that are still valid
        self.channel_comboBox.listWidget.itemChanged.disconnect(
            self.channel_comboBox.handleItemChanged
        )
        for selection in current_selections:
            if selection in new_channels:
                self.channel_comboBox.selectItem(selection)
        self.channel_comboBox.listWidget.itemChanged.connect(
            self.channel_comboBox.handleItemChanged
        )

        # Log the final state of selections
        restored_selections = self.channel_comboBox.getSelectedItems()
        self.channel_comboBox.refreshDisplayText()
        self.logger.debug(f"Selected items after restoration: {restored_selections}")

    def update_readers(self, readers: list[str]) -> None:
        self.logger.info(f"Updating readers: {readers}")

        # Store current selection
        current_selection = self.readers_comboBox.currentText()

        self.readers_comboBox.clear()

        if readers == []:
            readers.insert(0, "No Reader")
        self.readers_comboBox.addItems(readers)

        # Restore selection if it still exists
        if current_selection in readers:
            self.readers_comboBox.setCurrentText(current_selection)
        else:
            self.readers_comboBox.setCurrentIndex(0)

    def update_filters(self, filters: list[str]) -> None:
        self.logger.info(f"Updating filters: {filters}")

        # Store current selection
        current_selection = self.filters_comboBox.currentText()

        self.filters_comboBox.clear()
        if "No Filter" not in filters:
            filters.insert(0, "No Filter")
        self.filters_comboBox.addItems(filters)

        # Restore selection if it still exists
        if current_selection in filters:
            self.filters_comboBox.setCurrentText(current_selection)
        else:
            self.filters_comboBox.setCurrentIndex(0)

    def update_writers(self, writers: list[str]) -> None:
        self.logger.info(f"Updating writers: {writers}")

        # Store current selection
        current_selection = self.writers_comboBox.currentText()

        self.writers_comboBox.clear()

        if writers == []:
            writers.insert(0, "No Writer")
        self.writers_comboBox.addItems(writers)

        # Restore selection if it still exists
        if current_selection in writers:
            self.writers_comboBox.setCurrentText(current_selection)
        else:
            self.writers_comboBox.setCurrentIndex(0)

    def update_eventfinders(self, eventfinders: list[str]) -> None:
        self.logger.info(f"Updating eventfinders: {eventfinders}")

        # Store current selection
        current_selection = self.eventfinders_comboBox.currentText()

        self.eventfinders_comboBox.clear()
        if eventfinders == []:
            eventfinders.insert(0, "No Eventfinder")
        self.eventfinders_comboBox.addItems(eventfinders)

        # Restore selection if it still exists
        if current_selection in eventfinders:
            self.eventfinders_comboBox.setCurrentText(current_selection)
        else:
            self.eventfinders_comboBox.setCurrentIndex(0)

    def set_range_inputs(self, start: float, length: float):
        self.start_time_lineEdit.blockSignals(True)
        self.start_time_lineEdit.set_range(start, length)
        self.start_time_lineEdit.blockSignals(False)
        self.validate_inputs()

    @log(logger=logger)
    def set_event_index_input(self, value: str):
        self.event_index_lineEdit.blockSignals(True)
        self.event_index_lineEdit.set_range(value)
        self.event_index_lineEdit.blockSignals(False)
        self.validate_inputs()


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = RawDataControls()
    widget.show()
    sys.exit(app.exec())
