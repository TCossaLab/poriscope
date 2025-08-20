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


import logging

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


class ClusteringControls(QWidget):
    actionTriggered = Signal(
        str, str, tuple
    )  # Signal to trigger an action in the controller (submodel_name, action_name, args)
    is_signal_connected = False  # Class-level flag to check if signal is connected
    logger = logging.getLogger(__name__)

    edit_processed = Signal(str, str)
    add_processed = Signal(str)
    delete_processed = Signal(str, str)

    logger = logging.getLogger(__name__)

    def __init__(self, parent=None):
        """
        Initialize the ClusteringControls widget.

        Sets up the UI, connects signals, and performs initial input validation.
        """
        super().__init__(parent)
        self.logger.info("Initializing ClusteringControls")
        self.setupUi()
        self.connect_signals()
        self.logger.info("ClusteringControls initialized")
        self.validate_inputs()
        self.max_range_size = 16
        self.active_popups = {}

    def setupUi(self):
        self.logger.info("Setting up UI")
        self.setObjectName("Form")
        self.resize(663, 295)

        main_layout = QVBoxLayout(self)

        self.group_box = QGroupBox(self)
        self.group_box.setObjectName("group_box")
        group_layout = QGridLayout(self.group_box)
        group_layout.setVerticalSpacing(8)
        group_layout.setHorizontalSpacing(10)

        # TOP ROW

        # DB Loader Label + Edit Button
        db_layout = QHBoxLayout()
        db_layout.setContentsMargins(0, 0, 0, 0)

        self.db_loader_label = self.createLabel(self.group_box, 12, "DB LOADER")
        self.db_loader_comboBox = self.create_comboBox(self.group_box)
        self.db_loader_comboBox.setObjectName("dbLoaderComboBox")
        self.db_loader_comboBox.currentIndexChanged.connect(self.on_loader_changed)

        self.db_loader_info_button = self.create_info_button(
            self.group_box,
            self.db_loader_comboBox,
            "Edit selected loader",
            "MetaDatabaseLoader",
        )
        self.db_loader_add_button = self.create_add_button(
            self.group_box, self.db_loader_comboBox, "Add loader", "MetaDatabaseLoader"
        )
        self.db_loader_delete_button = self.create_delete_button(
            self.group_box,
            self.db_loader_comboBox,
            "Delete loader",
            "MetaDatabaseLoader",
        )

        db_layout.addWidget(self.db_loader_label)
        db_layout.addWidget(self.db_loader_add_button)
        db_layout.addWidget(self.db_loader_info_button)
        db_layout.addWidget(self.db_loader_delete_button)
        db_layout.addStretch(1)

        group_layout.addLayout(db_layout, 0, 0)
        group_layout.addWidget(self.db_loader_comboBox, 1, 0)

        # LABEL X
        self.label_x_label = self.createLabel(self.group_box, 12, "KEEP LABEL")
        self.label_x_comboBox = self.create_comboBox(self.group_box)
        self.label_x_comboBox.setObjectName("labelXComboBox")
        self.label_x_comboBox.currentIndexChanged.connect(self.on_label_changed)

        label_x_label_layout = QHBoxLayout()
        label_x_label_layout.setContentsMargins(0, 0, 0, 0)
        label_x_label_layout.addWidget(self.label_x_label)
        label_x_label_layout.addStretch(1)

        group_layout.addLayout(label_x_label_layout, 0, 1)
        group_layout.addWidget(self.label_x_comboBox, 1, 1)

        # LABEL Y
        self.label_y_label = self.createLabel(self.group_box, 12, "MERGE WITH")
        self.label_y_comboBox = self.create_comboBox(self.group_box)
        self.label_y_comboBox.setObjectName("labelYComboBox")
        self.label_y_comboBox.currentIndexChanged.connect(self.on_label_changed)

        label_y_label_layout = QHBoxLayout()
        label_y_label_layout.setContentsMargins(0, 0, 0, 0)
        label_y_label_layout.addWidget(self.label_y_label)
        label_y_label_layout.addStretch(1)

        group_layout.addLayout(label_y_label_layout, 0, 2)
        group_layout.addWidget(self.label_y_comboBox, 1, 2)

        # Merge and Commit Buttons
        self.merge_button = self.createButton(self.group_box, "Merge", bold=True)
        self.commit_button = self.createButton(self.group_box, "Commit", bold=True)
        group_layout.addWidget(self.merge_button, 1, 3)
        group_layout.addWidget(self.commit_button, 1, 4)

        # Bottom Row: Cluster Settings | Export Plot Data
        bottom_row_layout = QHBoxLayout()
        bottom_row_layout.setSpacing(10)

        self.cluster_settings_button = self.createButton(
            self.group_box, "Cluster Settings", bold=True
        )
        self.export_plot_data_button = self.createButton(
            self.group_box, "Export Plot Data", bold=True
        )

        self.cluster_settings_button.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self.export_plot_data_button.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )

        group_layout.addWidget(self.cluster_settings_button, 2, 0)
        group_layout.addWidget(self.export_plot_data_button, 2, 1, 1, 4)

        main_layout.addWidget(self.group_box)
        self.retranslateUi()
        self.logger.info("UI setup complete")

    # QWidgets
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

    def retranslateUi(self):
        """
        Update translated UI strings.

        Typically used in Qt for re-applying translations, currently unused.
        """
        pass
        # self.setWindowTitle(QCoreApplication.translate("Form", "Form", None))
        # self.db_loader_comboBox.tCurrentText("")

    # QWidget status

    def update_units(self, comboBox, units_label):
        """Update units based on the selected column in the comboBox and emit an update signal."""
        parameters = self.collect_parameters()
        self.actionTriggered.emit("ClusteringView", "columns_updated", (parameters,))

    def toggle_info_button(self, button, comboBox):
        """Enables or disables the info button based on the comboBox selection and item count."""
        button.setEnabled(
            comboBox.count() > 0
            and comboBox.currentIndex() != -1
            and not self.is_placeholder_item(comboBox)
        )

    def is_placeholder_item(self, comboBox):
        """Returns True if the combobox contains a placeholder like 'No Reader', 'No Writer', etc."""
        return comboBox.currentText() in ["No Event Database"]

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

    # Signals Connection
    def connect_signals(self):
        """Connects signals to corresponding methods."""
        # Core action buttons
        self.cluster_settings_button.clicked.connect(
            lambda: self.on_button_clicked("cluster_settings")
        )
        self.merge_button.clicked.connect(lambda: self.on_button_clicked("merge"))
        self.commit_button.clicked.connect(lambda: self.on_button_clicked("commit"))
        self.export_plot_data_button.clicked.connect(
            lambda: self.on_button_clicked("export_plot_data")
        )

        self.logger.info("Signals connected")

        # Input validation
        self.db_loader_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.label_x_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.label_y_comboBox.currentIndexChanged.connect(self.validate_inputs)

    # Data Validation

    def collect_parameters(self):
        """
        Collect current input values from the UI widgets.

        Gathers selected values from the database loader, X label, and Y label combo boxes.
        Defaults to "No Event Database" or `None` where appropriate.

        :return: A dictionary containing the current selections.
        :rtype: dict
        """
        self.logger.info("Collecting parameters")
        # Initialize with default values to handle possible None values
        parameters = {}
        try:
            parameters = {
                "db_loader": self.db_loader_comboBox.currentText()
                or "No Event Database",
                "label_x": self.label_x_comboBox.currentText() or None,
                "label_y": self.label_y_comboBox.currentText() or None,
            }
        except AttributeError as e:
            self.logger.warning(f"Error collecting parameters: {e}")

        self.logger.debug(f"Collected parameters: {parameters}")
        return parameters

    def on_loader_changed(self):
        """Handles parameter changes and emits an action signal."""
        parameters = self.collect_parameters()
        self.logger.debug(
            f"Emitting actionTriggered due to parameter change with parameters {parameters}"
        )
        self.actionTriggered.emit("ClusteringView", "loader_changed", (parameters,))

    def on_label_changed(self):
        """
        Handle changes in either the X or Y label combo box.

        This function can be extended to trigger updates or validations
        when a label selection changes.
        """
        pass

    def validate_inputs(self):
        """Validates input fields and enables/disables buttons accordingly."""
        is_merge_valid = True
        is_commit_valid = True
        is_settings_valid = True
        is_export_valid = True

        # Gather inputs
        db_loader = self.db_loader_comboBox.currentText()
        label_x = self.label_x_comboBox.currentText()
        label_y = self.label_y_comboBox.currentText()

        self.logger.debug(
            f"Validating inputs: DB Loader: {db_loader}, Label x: {label_x}, Label Y: {label_y}"
        )

        if not db_loader or db_loader == "No Event Database":
            is_merge_valid = False
            is_commit_valid = False
            is_settings_valid = False

        if not label_x or not label_y:
            is_merge_valid = False

        # Enable/disable buttons based on validation results
        self.merge_button.setEnabled(is_merge_valid)
        self.cluster_settings_button.setEnabled(is_settings_valid)
        self.export_plot_data_button.setEnabled(is_export_valid)
        self.commit_button.setEnabled(is_commit_valid)

    # Actions
    def on_button_clicked(self, button_type):
        """Handles button clicks and emits appropriate signals."""
        parameters = self.collect_parameters()
        self.logger.debug(
            f"Emitting actionTriggered for {button_type} with parameters {parameters}"
        )

        # Map button types to model actions
        button_actions = {
            "cluster_settings": "open_cluster_settings",
            "merge": "merge_clusters",
            "commit": "commit_clusters",
            "export_plot_data": "export_plot_data",
        }

        if button_type in button_actions:
            self.actionTriggered.emit(
                "ClusteringModel", button_actions[button_type], (parameters,)
            )

        # If buttons are toggleable, reset their state — otherwise, skip this
        button_mapping = {
            "cluster_settings": self.cluster_settings_button,
            "merge": self.merge_button,
            "commit": self.commit_button,
            "export_plot_data": self.export_plot_data_button,
        }

        button = button_mapping.get(button_type)
        if button and hasattr(button, "setChecked"):
            button.setChecked(False)

    def update_loaders(self, loaders: list[str]) -> None:
        """
        Update the database loader combo box with available loader names.

        Preserves the current selection if it's still valid; otherwise, defaults to the first available loader.

        :param loaders: A list of loader names (strings) to populate the combo box.
        :type loaders: list[str]
        """
        self.logger.info(f"Updating loaders: {loaders}")

        # Store current selection
        current_selection = self.db_loader_comboBox.currentText()
        self.db_loader_comboBox.clear()

        if not loaders:  # If list is empty, insert placeholder
            loaders.insert(0, "No Event Database")

        self.db_loader_comboBox.addItems(loaders)

        # Restore selection if it still exists
        if current_selection in loaders:
            self.db_loader_comboBox.setCurrentText(current_selection)
        else:
            self.db_loader_comboBox.setCurrentIndex(0)

    def update_labels(self):
        """
        Update both X and Y label combo boxes.

        This method should be implemented to populate the combo boxes
        with available cluster labels, possibly from an external source or updated state.
        """
        pass

    def update_clusters(self, clusters):
        """
        Update the X and Y label combo boxes with the provided cluster labels.

        :param clusters: A list of cluster identifiers to populate the combo boxes.
        :type clusters: list[str]
        """

        clusters = [str(c) for c in clusters]
        self.label_x_comboBox.clear()
        self.label_x_comboBox.addItems(clusters)
        self.label_y_comboBox.clear()
        self.label_y_comboBox.addItems(clusters)
