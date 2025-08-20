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
from poriscope.views.integer_range_line_edit import IntegerRangeLineEdit
from poriscope.views.widgets.multiselect import MultiSelectComboBox


class EventAnalysisControls(QWidget):
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
        self.logger.info("Initializing EventAnalysisControls")
        self.setupUi()
        self.connect_signals()
        self.logger.info("EventAnalysisControls initialized")
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

        loader_layout = QHBoxLayout()
        self.loaders_label = self.createLabel(self.groupBox, 12, "EVENT LOADER")
        self.loaders_comboBox = self.create_comboBox(self.groupBox)
        self.loaders_comboBox.setObjectName("loadersComboBox")
        self.loaders_comboBox.currentIndexChanged.connect(self.on_parameter_changed)
        self.loaders_info_button = self.create_info_button(
            self.groupBox,
            self.loaders_comboBox,
            "Edit selected eventloaders",
            "MetaEventLoader",
        )
        self.loaders_add_button = self.create_add_button(
            self.groupBox, self.loaders_comboBox, "Add eventloaders", "MetaEventLoader"
        )
        self.loaders_delete_button = self.create_delete_button(
            self.groupBox,
            self.loaders_comboBox,
            "Delete eventloaders",
            "MetaEventLoader",
        )

        loader_layout.addWidget(self.loaders_label)
        loader_layout.addWidget(self.loaders_add_button)
        loader_layout.addWidget(self.loaders_info_button)
        loader_layout.addWidget(self.loaders_delete_button)
        loader_layout.addStretch(1)
        group_layout.addLayout(loader_layout, 0, 0)
        group_layout.addWidget(self.loaders_comboBox, 1, 0)

        # PLOT EVENTS CONTAINER
        self.plot_events_widget = QWidget(self.groupBox)
        plot_events_layout = QHBoxLayout(self.plot_events_widget)
        plot_events_layout.setContentsMargins(0, 0, 0, 0)
        plot_events_layout.setSpacing(5)

        # Left arrow button
        self.left_arrow_button = QPushButton(self.plot_events_widget)
        self.left_arrow_button.setIcon(get_icon("arrow-left.svg"))
        self.left_arrow_button.setIconSize(QSize(16, 16))
        self.left_arrow_button.setFixedWidth(30)

        # Main Update Trace button
        self.plot_events_pushButton = self.createButton(
            self.groupBox, "Plot Events", bold=True
        )
        self.plot_events_pushButton.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        # Right arrow button
        self.right_arrow_button = QPushButton(self.plot_events_widget)
        self.right_arrow_button.setIcon(get_icon("arrow-right.svg"))
        self.right_arrow_button.setIconSize(QSize(16, 16))
        self.right_arrow_button.setFixedWidth(30)

        plot_events_layout.addWidget(self.left_arrow_button)
        plot_events_layout.addWidget(self.plot_events_pushButton)
        plot_events_layout.addWidget(self.right_arrow_button)

        group_layout.addWidget(self.plot_events_widget, 4, 0, 1, 2)

        # Second Column: Filters section
        filter_layout = QHBoxLayout()
        self.filters_label = self.createLabel(self.groupBox, 12, "FILTER")
        self.filters_comboBox = self.create_comboBox(self.groupBox)
        self.filters_comboBox.setObjectName("filtersComboBox")
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
        group_layout.addWidget(channel_lbl, 2, 0)
        group_layout.addWidget(self.channel_comboBox, 3, 0)
        self.channel_comboBox.selectionChanged.connect(self.validate_inputs)

        # Third Column: EventFitters section
        eventfitters_layout = QHBoxLayout()
        self.eventfitters_label = self.createLabel(self.groupBox, 12, "EVENT FITTER")
        self.eventfitters_comboBox = self.create_comboBox(self.groupBox)
        self.eventfitters_comboBox.setObjectName("eventFitterdComboBox")
        self.eventfitters_info_button = self.create_info_button(
            self.groupBox,
            self.eventfitters_comboBox,
            "Edit selected eventfitter",
            "MetaEventFitter",
        )
        self.eventfitters_add_button = self.create_add_button(
            self.groupBox,
            self.eventfitters_comboBox,
            "Add eventfitter",
            "MetaEventFitter",
        )
        self.eventfitters_delete_button = self.create_delete_button(
            self.groupBox,
            self.eventfitters_comboBox,
            "Delete eventfitter",
            "MetaEventFitter",
        )

        eventfitters_layout.addWidget(self.eventfitters_label)
        eventfitters_layout.addWidget(self.eventfitters_add_button)
        eventfitters_layout.addWidget(self.eventfitters_info_button)
        eventfitters_layout.addWidget(self.eventfitters_delete_button)

        eventfitters_layout.addStretch(1)
        self.eventfitters_comboBox.currentIndexChanged.connect(
            self.on_parameter_changed
        )

        group_layout.addLayout(eventfitters_layout, 0, 2)
        group_layout.addWidget(self.eventfitters_comboBox, 1, 2)

        self.event_index_lbl = self.createLabel(self.groupBox, 12, "EVENT INDEX")
        self.event_index_lineEdit = IntegerRangeLineEdit(self.groupBox)
        self.event_index_lineEdit.setObjectName("eventIndexLineEdit")
        self.event_index_lineEdit.setPlaceholderText(
            "Enter up to 16 numbers (e.g., 5 or 10-25)"
        )
        group_layout.addWidget(self.event_index_lbl, 2, 1)
        group_layout.addWidget(self.event_index_lineEdit, 3, 1, 1, 3)

        self.fit_events_pushButton = self.createButton(self.groupBox, "Fit Events")
        group_layout.addWidget(self.fit_events_pushButton, 4, 2)

        # Fourth Column: Writers section
        writer_layout = QHBoxLayout()
        self.writers_label = self.createLabel(self.groupBox, 12, "DB-WRITER")
        self.writers_comboBox = self.create_comboBox(self.groupBox)
        self.writers_comboBox.setObjectName("dbwritersComboBox")
        self.writers_info_button = self.create_info_button(
            self.groupBox,
            self.writers_comboBox,
            "Edit selected eventwriter",
            "MetaDatabaseWriter",
        )
        self.writers_add_button = self.create_add_button(
            self.groupBox,
            self.writers_comboBox,
            "Add eventwriter",
            "MetaDatabaseWriter",
        )
        self.writers_delete_button = self.create_delete_button(
            self.groupBox,
            self.writers_comboBox,
            "Add eventwriter",
            "MetaDatabaseWriter",
        )

        writer_layout.addWidget(self.writers_label)
        writer_layout.addWidget(self.writers_add_button)
        writer_layout.addWidget(self.writers_info_button)
        writer_layout.addWidget(self.writers_delete_button)
        writer_layout.addStretch(1)
        self.writers_comboBox.currentIndexChanged.connect(self.on_parameter_changed)

        group_layout.addLayout(writer_layout, 0, 3)
        group_layout.addWidget(self.writers_comboBox, 1, 3)

        self.commit_btn = self.createButton(self.groupBox, "Commit Events")
        group_layout.addWidget(self.commit_btn, 4, 3)

        self.export_plot_data_pushButton = self.createButton(
            self.groupBox, "Export Plot Data", bold=True
        )
        ##        button_layout = QVBoxLayout()
        ##        button_layout.addWidget(self.export_plot_data_pushButton)
        ##        group_layout.addLayout(button_layout, 7, 0, 1, 4)
        group_layout.addWidget(self.export_plot_data_pushButton, 7, 0, 1, 4)

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
        """Returns True if the combobox contains a placeholder like 'No Loader', 'No Database Writer', etc."""
        return comboBox.currentText() in [
            "No Loader",
            "No Database Writer",
            "No Filter",
            "No EventFitter",
        ]

    def clear_popup_reference(self, comboBox):
        """Clears the reference to the popup when it is closed."""
        if comboBox in self.active_popups:
            self.active_popups.pop(comboBox)

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

    def get_plugin_data(self):
        """Fetch plugin data from a JSON file located in the application's local data directory."""
        localappdata = os.getenv("LOCALAPPDATA")
        if localappdata is None:
            raise IOError("Unable to resolve LOCALAPPDATA")
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
        is_commit_valid = True
        is_plot_events_valid = True
        is_fit_events_valid = True  # Add validation flag for fit_events button

        # Gather relevant inputs
        loader = self.loaders_comboBox.currentText()
        self.eventfitters_comboBox.currentText()
        channels = self.channel_comboBox.getSelectedItems()
        event_index_valid = self.event_index_lineEdit.isValid()
        writer = self.writers_comboBox.currentText()
        self.event_index_lineEdit.get_values()

        # Debug logging
        self.logger.debug(
            f"Loader: '{loader}', Channels: {channels}, Event Index Valid: {event_index_valid}"
        )

        if not loader or loader == "No Loader":
            self.logger.debug("No loader selected")
            is_plot_events_valid = False
            is_fit_events_valid = False

        if not channels:
            self.logger.debug("No channels selected")
            is_commit_valid = False
            is_fit_events_valid = False
            is_plot_events_valid = False

        if channels and len(channels) > 1:
            self.logger.debug(f"{len(channels)} channels selected")
            is_plot_events_valid = False

        # Validate event index input
        if not event_index_valid:
            self.logger.debug("Event index is invalid")
            is_plot_events_valid = (
                False  # Disable Plot Events button if event index is not valid
            )

        if not writer or writer == "No Database Writer":
            self.logger.debug("No writer selected")
            is_commit_valid = False

        # Enable or disable buttons based on validation
        self.commit_btn.setEnabled(is_commit_valid)
        self.left_arrow_button.setEnabled(is_plot_events_valid)
        self.plot_events_pushButton.setEnabled(is_plot_events_valid)
        self.right_arrow_button.setEnabled(is_plot_events_valid)
        self.fit_events_pushButton.setEnabled(is_fit_events_valid)

    def connect_signals(self):
        self.export_plot_data_pushButton.clicked.connect(
            lambda: self.on_button_clicked("export_plot_data")
        )
        self.fit_events_pushButton.clicked.connect(
            lambda: self.on_button_clicked("fit_events")
        )
        self.left_arrow_button.clicked.connect(
            lambda: self.on_button_clicked("left_arrow")
        )
        self.plot_events_pushButton.clicked.connect(
            lambda: self.on_button_clicked("plot_events")
        )
        self.right_arrow_button.clicked.connect(
            lambda: self.on_button_clicked("right_arrow")
        )
        self.commit_btn.clicked.connect(lambda: self.on_button_clicked("commit_events"))
        self.logger.info("Signals connected")

        # Ensure that the validate_inputs method is called when the inputs change
        self.event_index_lineEdit.textChanged.connect(self.validate_inputs)
        self.channel_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.filters_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.eventfitters_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.writers_comboBox.currentIndexChanged.connect(self.validate_inputs)

    def on_parameter_changed(self):
        parameters = self.collect_parameters()
        self.logger.debug(
            f"Emitting actionTriggered due to parameter change with parameters {parameters}"
        )
        self.actionTriggered.emit(
            "EventAnalysisModel", "parameter_changed", (parameters,)
        )

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
        self.loaders_comboBox.setCurrentText("")

    def collect_parameters(self):
        self.logger.info("Collecting parameters")

        # Initialize with default values to handle possible None values
        parameters = {
            "loader": self.loaders_comboBox.currentText() or "No Loader",
            "filter": self.filters_comboBox.currentText() or "No Filter",
            "writer": self.writers_comboBox.currentText() or "No Database Writer",
            "eventfitter": self.eventfitters_comboBox.currentText()
            or "No Event Fitter",
            "event_index": [],
            "channel": [item for item in self.channel_comboBox.getSelectedItems()],
        }

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

        if button_type == "export_plot_data":
            self.actionTriggered.emit(
                "EventAnalysisModel", "export_plot_data", (parameters,)
            )
        elif button_type == "fit_events":
            self.actionTriggered.emit("EventAnalysisModel", "fit_events", (parameters,))
        elif button_type == "left_arrow":
            self.actionTriggered.emit(
                "EventAnalysisModel", "shift_range_backward", (parameters,)
            )
        elif button_type == "plot_events":
            self.actionTriggered.emit(
                "EventAnalysisModel", "plot_events", (parameters,)
            )
        elif button_type == "right_arrow":
            self.actionTriggered.emit(
                "EventAnalysisModel", "shift_range_forward", (parameters,)
            )
        elif button_type == "commit_events":
            self.actionTriggered.emit(
                "EventAnalysisModel", "commit_events", (parameters,)
            )

        # Automatically uncheck the button after it is clicked
        button_mapping = {
            "export_plot_data": self.export_plot_data_pushButton,
            "commit_events": self.commit_btn,
            "fit_events": self.fit_events_pushButton,
            "left_arrow": self.left_arrow_button,
            "plot_events": self.plot_events_pushButton,
            "right_arrow": self.right_arrow_button,
        }

        button_mapping.get(button_type, lambda: None).setChecked(False)

    def update_channels(self, channels):
        self.logger.info(f"Updating channels to {channels}")

        # Store the current selection(s)
        current_selections = self.channel_comboBox.getSelectedItems()

        self.channel_comboBox.clear()
        self.channel_comboBox.addItems([str(i) for i in channels])

        # Restore selections if they still exist
        for selection in current_selections:
            if selection in [str(i) for i in channels]:
                self.channel_comboBox.selectItem(selection)

    def update_loaders(self, loaders: list[str]) -> None:
        self.logger.info(f"Updating loaders: {loaders}")

        # Store current selection
        current_selection = self.loaders_comboBox.currentText()

        self.loaders_comboBox.clear()

        if loaders == []:
            loaders.insert(0, "No Loader")
        self.loaders_comboBox.addItems(loaders)

        # Restore selection if it still exists
        if current_selection in loaders:
            self.loaders_comboBox.setCurrentText(current_selection)
        else:
            self.loaders_comboBox.setCurrentIndex(0)

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
            writers.insert(0, "No Database Writer")
        self.writers_comboBox.addItems(writers)

        # Restore selection if it still exists
        if current_selection in writers:
            self.writers_comboBox.setCurrentText(current_selection)
        else:
            self.writers_comboBox.setCurrentIndex(0)

    def update_eventfitters(self, eventfitters: list[str]) -> None:
        self.logger.info(f"Updating eventfitters: {eventfitters}")

        # Store current selection
        current_selection = self.eventfitters_comboBox.currentText()

        self.eventfitters_comboBox.clear()
        if eventfitters == []:
            eventfitters.insert(0, "No EventFitter")
        self.eventfitters_comboBox.addItems(eventfitters)

        # Restore selection if it still exists
        if current_selection in eventfitters:
            self.eventfitters_comboBox.setCurrentText(current_selection)
        else:
            self.eventfitters_comboBox.setCurrentIndex(0)

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
    widget = EventAnalysisControls()
    widget.show()
    sys.exit(app.exec())
