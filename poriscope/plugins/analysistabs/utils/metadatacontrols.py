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

from PySide6.QtCore import (
    QCoreApplication,
    QRegularExpression,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QFont, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from poriscope.configs.utils import get_icon
from poriscope.utils.LogDecorator import log
from poriscope.views.integer_range_line_edit import IntegerRangeLineEdit
from poriscope.views.widgets.multiselect_filter import MultiSelectComboBox


class MetadataControls(QWidget):
    actionTriggered = Signal(
        str, str, tuple
    )  # Signal to trigger an action in the controller (submodel_name, action_name, args)
    is_signal_connected = False  # Class-level flag to check if signal is connected
    logger = logging.getLogger(__name__)

    edit_processed = Signal(str, str)
    add_processed = Signal(str)
    delete_processed = Signal(str, str)
    edit_filter_requested = Signal(str, str)
    delete_filter_requested = Signal(str)

    logger = logging.getLogger(__name__)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger.info("Initializing MetadataControls")
        self.setupUi()
        self.connect_signals()
        self.logger.info("MetadataControls initialized")
        self.validate_inputs()
        self.max_range_size = 16
        self.active_popups = {}

    def setupUi(self):
        self.logger.info("Setting up UI")
        self.setObjectName("Form")
        self.resize(663, 295)

        main_layout = QVBoxLayout(self)

        self.groupBox = QGroupBox(self)
        self.groupBox.setObjectName("groupBox")
        group_layout = QGridLayout(self.groupBox)
        group_layout.setColumnStretch(0, 1)
        group_layout.setColumnStretch(1, 4)
        group_layout.setColumnStretch(2, 3)

        group_layout.setVerticalSpacing(4)

        # 0-1 row QH DB LOADER + PLOT TYPE

        # DB LOADER
        self.db_loader_label = self.createLabel(self.groupBox, 12, "DB LOADER")
        self.db_loader_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.db_loader_comboBox = self.create_comboBox(self.groupBox)
        self.db_loader_comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.db_loader_comboBox.setObjectName("dbLoaderComboBox")
        self.db_loader_comboBox.currentIndexChanged.connect(self.on_loader_changed)

        self.db_loader_add_button = self.create_add_button(
            self.groupBox, self.db_loader_comboBox, "Add loader", "MetaDatabaseLoader"
        )
        self.db_loader_info_button = self.create_info_button(
            self.groupBox,
            self.db_loader_comboBox,
            "Edit selected loader",
            "MetaDatabaseLoader",
        )
        self.db_loader_delete_button = self.create_delete_button(
            self.groupBox,
            self.db_loader_comboBox,
            "Delete loader",
            "MetaDatabaseLoader",
        )

        self.selection_tree_button = QPushButton("Scope")

        # PLOT TYPE
        self.plot_type_label = self.createLabel(self.groupBox, 12, "PLOT TYPE")

        self.plot_type_comboBox = self.create_comboBox(self.groupBox)
        self.plot_type_comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.plot_type_comboBox.setObjectName("plotTypeComboBox")
        self.plot_type_comboBox.currentIndexChanged.connect(self._plot_type_changed)

        plot_type_options = [
            "Select Plot Type",
            "Histogram",
            "Normalized Histogram",
            "Kernel Density Plot",
            "Capture Rate",
            "Heatmap",
            "Scatterplot",
            "3D Scatterplot",
            "Raw Event Overlay",
            "Filtered Event Overlay",
            "Raw All Points Histogram",
            "Normalized Raw All Points Histogram",
            "Filtered All Points Histogram",
            "Normalized Filtered All Points Histogram",
        ]
        self.plot_type_comboBox.addItems(plot_type_options)

        # --- Set size policies ---
        self.db_loader_comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.plot_type_comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.selection_tree_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        # --- ROW 0 LEFT: DB LOADER Label + Buttons ---
        db_loader_top_layout = QHBoxLayout()
        db_loader_top_layout.setContentsMargins(0, 0, 0, 0)
        db_loader_top_layout.setSpacing(5)
        db_loader_top_layout.setAlignment(Qt.AlignLeft)
        db_loader_top_layout.addWidget(self.db_loader_label)
        db_loader_top_layout.addWidget(self.db_loader_add_button)
        db_loader_top_layout.addWidget(self.db_loader_info_button)
        db_loader_top_layout.addWidget(self.db_loader_delete_button)

        # --- ROW 0 RIGHT: PLOT TYPE Label ---
        plot_type_top_layout = QHBoxLayout()
        plot_type_top_layout.setContentsMargins(0, 0, 0, 0)
        plot_type_top_layout.setSpacing(0)
        plot_type_top_layout.setAlignment(Qt.AlignLeft)
        plot_type_top_layout.addWidget(self.plot_type_label)

        # --- Combine ROW 0 LEFT + RIGHT ---
        top_row_layout = QHBoxLayout()
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(5)
        top_row_layout.addLayout(db_loader_top_layout, 1)
        top_row_layout.addLayout(plot_type_top_layout, 1)

        # --- ROW 1 LEFT: DB Combo + Button inside QWidget ---
        combo_left_widget = QWidget()
        combo_left_layout = QHBoxLayout(combo_left_widget)
        combo_left_layout.setContentsMargins(0, 0, 0, 0)
        combo_left_layout.setSpacing(5)
        combo_left_layout.addWidget(self.db_loader_comboBox)
        combo_left_layout.addWidget(self.selection_tree_button)

        # --- ROW 1 RIGHT: Plot type combo inside QWidget ---
        combo_right_widget = QWidget()
        combo_right_layout = QHBoxLayout(combo_right_widget)
        combo_right_layout.setContentsMargins(0, 0, 0, 0)
        combo_right_layout.setSpacing(0)
        combo_right_layout.addWidget(self.plot_type_comboBox)

        # --- ROW 1: Grid with equal space ---
        bottom_row_layout = QGridLayout()
        bottom_row_layout.setContentsMargins(0, 0, 0, 0)
        bottom_row_layout.setHorizontalSpacing(5)
        bottom_row_layout.addWidget(combo_left_widget, 0, 0)
        bottom_row_layout.addWidget(combo_right_widget, 0, 1)
        bottom_row_layout.setColumnStretch(0, 1)
        bottom_row_layout.setColumnStretch(1, 1)

        # --- Add to group layout ---
        group_layout.addLayout(top_row_layout, 0, 0)
        group_layout.addLayout(bottom_row_layout, 1, 0)

        # --- Force same width after layout settles using QTimer ---
        def match_widths():
            # Ensure layout has calculated widths
            self.plot_type_comboBox.ensurePolished()
            self.plot_type_comboBox.updateGeometry()
            right_width = self.plot_type_comboBox.width()

            # Compute button width
            button_width = self.selection_tree_button.sizeHint().width()
            spacing = combo_left_layout.spacing()
            combo_width = max(right_width - button_width - spacing, 50)

            # Apply fixed width to left side
            self.db_loader_comboBox.setFixedWidth(combo_width)
            self.selection_tree_button.setFixedWidth(button_width)
            self.plot_type_comboBox.setFixedWidth(right_width)

        # Defer this until after the window is visible
        QTimer.singleShot(0, match_widths)

        # 2-3 QH EVENT IDEX + BINS + SIZES

        # --- ROW 2: Labels Row ---
        labels_row = QHBoxLayout()
        labels_row.setContentsMargins(0, 0, 0, 0)
        labels_row.setSpacing(5)

        # Left column: EVENT INDEX label
        event_index_label = self.createLabel(self.groupBox, 12, "EVENT INDEX")
        labels_row.addWidget(event_index_label, 1)

        # Right column: BINS + SIZES labels
        right_labels = QHBoxLayout()
        right_labels.setSpacing(5)

        bins_label = self.createLabel(self.groupBox, 12, "BINS")
        right_labels.addWidget(bins_label, 5)

        sizes_label_wrapper = QVBoxLayout()
        sizes_label_wrapper.addStretch()
        sizes_label = self.createLabel(self.groupBox, 12, "SIZES")
        sizes_label.setAlignment(Qt.AlignCenter)
        sizes_label_wrapper.addWidget(sizes_label, alignment=Qt.AlignCenter)
        sizes_label_wrapper.addStretch()
        right_labels.addLayout(sizes_label_wrapper, 1)

        labels_row.addLayout(right_labels, 1)

        # --- ROW 3:Inputs Row ---
        inputs_row = QHBoxLayout()
        inputs_row.setContentsMargins(0, 0, 0, 0)
        inputs_row.setSpacing(5)

        # Left column: EVENT INDEX input
        self.event_index_lineEdit = IntegerRangeLineEdit(self.groupBox)
        self.event_index_lineEdit.setObjectName("eventIndexLineEdit")
        self.event_index_lineEdit.setPlaceholderText("e.g. 0-15")
        inputs_row.addWidget(self.event_index_lineEdit, 1)

        # Right column: BINS + SIZES inputs
        right_inputs = QHBoxLayout()
        right_inputs.setSpacing(5)

        int_regex = QRegularExpression(r"^\d+(,\d+)*,?$")
        self.int_validator = QRegularExpressionValidator(int_regex)

        # Float validator: e.g., 1.2,3.5,4.0
        float_regex = QRegularExpression(r"^\d*\.?\d+(,\d*\.?\d+)*,?$")
        self.float_validator = QRegularExpressionValidator(float_regex)

        self.bins_lineEdit = QLineEdit(self.groupBox)
        self.bins_lineEdit.setObjectName("binsLineEdit")
        self.bins_lineEdit.setValidator(self.int_validator)
        right_inputs.addWidget(self.bins_lineEdit, 5)

        self.sizes_checkbox = QCheckBox(self.groupBox)

        checkbox_wrapper = QVBoxLayout()
        checkbox_wrapper.addStretch()
        checkbox_wrapper.addWidget(self.sizes_checkbox, alignment=Qt.AlignCenter)
        checkbox_wrapper.addStretch()
        right_inputs.addLayout(checkbox_wrapper, 1)

        inputs_row.addLayout(right_inputs, 1)

        group_layout.addLayout(labels_row, 2, 0)
        group_layout.addLayout(inputs_row, 3, 0)

        # --- Connect checkbox and apply current validator ---
        self.sizes_checkbox.toggled.connect(self._on_sizes_checkbox_toggled)
        self._on_sizes_checkbox_toggled(self.sizes_checkbox.isChecked())

        self.db_loader_comboBox.setMinimumWidth(160)
        self.selection_tree_button.setFixedWidth(50)
        self.plot_type_comboBox.setMinimumWidth(200)
        self.event_index_lineEdit.setMinimumWidth(160)
        self.bins_lineEdit.setMinimumWidth(100)

        # COLUMN 1: AXIS
        x_axis_layout = QHBoxLayout()
        x_axis_layout.setContentsMargins(0, 0, 0, 0)
        self.x_axis_label = self.createLabel(self.groupBox, 12, "X-AXIS")
        self.x_axis_comboBox = self.create_comboBox(self.groupBox)
        self.x_axis_comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.x_axis_comboBox.setObjectName("xAxisComboBox")
        self.x_axis_units_label = self.createLabel(self.groupBox, 16, " ")
        self.x_axis_comboBox.currentIndexChanged.connect(
            lambda: self.update_units(self.x_axis_comboBox, self.x_axis_units_label)
        )

        self.x_axis_logscale_checkbox = QCheckBox("Log", self.groupBox)
        self.x_axis_logscale_checkbox.setObjectName("xAxisLogscaleCheckbox")

        x_axis_layout.addWidget(self.x_axis_comboBox, 4)
        x_axis_layout.addWidget(self.x_axis_units_label, 1)
        x_axis_layout.addWidget(self.x_axis_logscale_checkbox, 1)

        group_layout.addWidget(self.x_axis_label, 0, 1)
        group_layout.addLayout(x_axis_layout, 1, 1)

        y_axis_layout = QHBoxLayout()
        y_axis_layout.setContentsMargins(0, 0, 0, 0)
        self.y_axis_label = self.createLabel(self.groupBox, 12, "Y-AXIS")
        self.y_axis_comboBox = self.create_comboBox(self.groupBox)
        self.y_axis_comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.y_axis_comboBox.setObjectName("yAxisComboBox")
        self.y_axis_units_label = self.createLabel(self.groupBox, 16, " ")
        self.y_axis_comboBox.currentIndexChanged.connect(
            lambda: self.update_units(self.y_axis_comboBox, self.y_axis_units_label)
        )

        self.y_axis_logscale_checkbox = QCheckBox("Log", self.groupBox)
        self.y_axis_logscale_checkbox.setObjectName("yAxisLogscaleCheckbox")

        y_axis_layout.addWidget(self.y_axis_comboBox, 4)
        y_axis_layout.addWidget(self.y_axis_units_label, 1)
        y_axis_layout.addWidget(self.y_axis_logscale_checkbox, 1)

        group_layout.addWidget(self.y_axis_label, 2, 1)
        group_layout.addLayout(y_axis_layout, 3, 1)

        z_axis_layout = QHBoxLayout()
        z_axis_layout.setContentsMargins(0, 0, 0, 0)
        self.z_axis_label = self.createLabel(self.groupBox, 12, "Z-AXIS")
        self.z_axis_comboBox = self.create_comboBox(self.groupBox)
        self.z_axis_comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.z_axis_comboBox.setObjectName("zAxisComboBox")
        self.z_axis_units_label = self.createLabel(self.groupBox, 16, " ")
        self.z_axis_comboBox.currentIndexChanged.connect(
            lambda: self.update_units(self.z_axis_comboBox, self.z_axis_units_label)
        )

        self.z_axis_logscale_checkbox = QCheckBox("Log", self.groupBox)
        self.z_axis_logscale_checkbox.setObjectName("zAxisLogscaleCheckbox")

        z_axis_layout.addWidget(self.z_axis_comboBox, 4)
        z_axis_layout.addWidget(self.z_axis_units_label, 1)
        z_axis_layout.addWidget(self.z_axis_logscale_checkbox, 1)

        group_layout.addWidget(self.z_axis_label, 4, 1)
        group_layout.addLayout(z_axis_layout, 5, 1)

        # COLUMN 2: Filter Layout
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_label = self.createLabel(self.groupBox, 12, "FILTER")
        self.filter_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.filter_comboBox = MultiSelectComboBox(self.groupBox)
        self.filter_comboBox.setObjectName("filterComboBox")

        self.filter_add_button = self.create_add_filter_button(
            self.groupBox, self.filter_comboBox, "Add filter"
        )
        self.filter_info_button = self.create_filter_info_button(
            self.groupBox, self.filter_comboBox, "Edit selected filter"
        )
        self.filter_delete_button = self.create_filter_delete_button(
            self.groupBox, self.filter_comboBox, "Delete selected filter(s)"
        )

        self.filter_comboBox.edit_filter = self.show_filter_info_dialog_single
        self.filter_comboBox.delete_filter = self.delete_filter_by_name

        # Adding the label to the horizontal layout
        filter_layout.setSpacing(5)
        filter_layout.setAlignment(Qt.AlignLeft)
        filter_layout.addWidget(self.filter_label)
        filter_layout.addWidget(self.filter_add_button)
        filter_layout.addWidget(self.filter_info_button)
        filter_layout.addWidget(self.filter_delete_button)

        filter_layout.addStretch(
            1
        )  # This keeps the label aligned left and the rest of the horizontal space empty

        # Adding the horizontal layout to the grid
        group_layout.addLayout(
            filter_layout, 0, 2, 1, 1
        )  # Adds the label at row 0, column 2

        self.save_filter_button = self.createButton(
            self.groupBox, "Save Filter", bold=True
        )
        self.load_filter_button = self.createButton(
            self.groupBox, "Load Filter", bold=True
        )

        # Adding QTextEdit directly to the grid, spanning multiple rows to increase its area
        group_layout.addWidget(
            self.filter_comboBox, 1, 2, 1, 1
        )  # Starts from row 1, spans 6 rows, and takes 2 columns
        group_layout.addWidget(self.save_filter_button, 3, 2, 1, 1)
        group_layout.addWidget(self.load_filter_button, 5, 2, 1, 1)

        self.filter_comboBox.selectionChanged.connect(self.validate_inputs)

        # --- Create Plot Events Container ---
        self.plot_events_widget = QWidget(self.groupBox)
        plot_events_layout = QHBoxLayout(self.plot_events_widget)
        plot_events_layout.setContentsMargins(0, 0, 0, 0)
        plot_events_layout.setSpacing(5)

        self.left_arrow_button = QPushButton(self.plot_events_widget)
        self.left_arrow_button.setIcon(get_icon("arrow-left.svg"))
        self.left_arrow_button.setIconSize(QSize(16, 16))
        self.left_arrow_button.setFixedWidth(30)

        self.plot_events_pushButton = self.createButton(
            self.groupBox, "Plot Events", bold=True
        )
        self.plot_events_pushButton.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        self.right_arrow_button = QPushButton(self.plot_events_widget)
        self.right_arrow_button.setIcon(get_icon("arrow-right.svg"))
        self.right_arrow_button.setIconSize(QSize(16, 16))
        self.right_arrow_button.setFixedWidth(30)

        plot_events_layout.addWidget(self.left_arrow_button)
        plot_events_layout.addWidget(self.plot_events_pushButton)
        plot_events_layout.addWidget(self.right_arrow_button)

        # --- Create Update + Undo group ---
        # Update + Undo group
        self.update_plot_button = self.createButton(
            self.groupBox, "Update Plot", bold=True
        )
        self.undo_button = self.createButton(self.groupBox, "Undo", bold=True)

        # Set expanding policy to allow the layout to distribute space
        self.update_plot_button.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        self.undo_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        update_undo_container = QWidget(self.groupBox)
        update_undo_layout = QHBoxLayout(update_undo_container)
        update_undo_layout.setContentsMargins(0, 0, 0, 0)
        update_undo_layout.setSpacing(5)

        update_undo_layout.addWidget(self.update_plot_button, 2)  # 2 parts
        update_undo_layout.addWidget(self.undo_button, 1)  # 1 part

        # --- Combine both widgets into a single row inside ONE grid cell ---
        row_container = QWidget(self.groupBox)
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        row_layout.addWidget(self.plot_events_widget, 1)
        row_layout.addWidget(update_undo_container, 1)

        # --- Finally, add this full row into ONE cell of your grid layout ---
        group_layout.addWidget(row_container, 5, 0)

        action_button_layout = QHBoxLayout()

        self.save_plot_button = self.createButton(
            self.groupBox, "Save Plot Configuration", bold=True
        )
        self.load_button = self.createButton(
            self.groupBox, "Load Plot Configuration", bold=True
        )
        self.reset_button = self.createButton(self.groupBox, "Reset", bold=True)
        self.export_csv_subset_button = self.createButton(
            self.groupBox, "Export Subset - CSV", bold=True
        )
        self.export_plot_data_pushButton = self.createButton(
            self.groupBox, "Export Plot Data", bold=True
        )

        action_button_layout.addWidget(self.save_plot_button)
        action_button_layout.addSpacing(5)
        action_button_layout.addWidget(self.load_button)
        action_button_layout.addSpacing(5)
        action_button_layout.addWidget(self.reset_button)
        action_button_layout.addSpacing(5)
        action_button_layout.addWidget(self.export_csv_subset_button)
        action_button_layout.addSpacing(5)
        action_button_layout.addWidget(self.export_plot_data_pushButton)

        group_layout.addLayout(
            action_button_layout, 7, 0, 1, group_layout.columnCount()
        )

        main_layout.addWidget(self.groupBox)
        self.retranslateUi()
        self.logger.info("UI setup complete")

    def _on_sizes_checkbox_toggled(self, checked):
        if checked:
            self.bins_lineEdit.setValidator(self.float_validator)
            self.bins_lineEdit.setPlaceholderText("e.g. 1.2, 3.5, 4.0")
        else:
            self.bins_lineEdit.setValidator(self.int_validator)
            self.bins_lineEdit.setPlaceholderText("e.g. 10 or 5,10,15")

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

    def create_filter_info_button(self, parent, comboBox, tooltip):
        button = QToolButton(parent)
        button.setIcon(get_icon("edit.png"))
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet("border: none; background: transparent;")
        button.setToolTip(tooltip)
        return button

    def create_add_filter_button(self, parent, comboBox, tooltip):
        button = QToolButton(parent)
        button.setIcon(get_icon("plus-square-dotted.svg"))
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet("border: none; background: transparent;")
        button.setToolTip(tooltip)
        return button

    def create_filter_delete_button(self, parent, comboBox, tooltip):
        button = QToolButton(parent)
        button.setIcon(get_icon("trash.svg"))
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet("border: none; background: transparent;")
        button.setToolTip(tooltip)
        return button

    def show_filter_info_dialog_single(self, name: str):
        loader = self.db_loader_comboBox.currentText()
        self.edit_filter_requested.emit(name, loader)

    def delete_filter_by_name(self, name: str):
        self.delete_filter_requested.emit(name)

    def retranslateUi(self):
        pass
        # self.setWindowTitle(QCoreApplication.translate("Form", "Form", None))
        # self.db_loader_comboBox.tCurrentText("")

    # QWidget status
    @log(logger=logger)
    def _plot_type_changed(self, index):
        current_text = self.plot_type_comboBox.currentText()
        if current_text == "Heatmap" or current_text == "Scatterplot":
            self.x_axis_comboBox.setEnabled(True)
            self.y_axis_comboBox.setEnabled(True)
            self.z_axis_comboBox.setEnabled(False)
            self.x_axis_logscale_checkbox.setEnabled(True)
            self.y_axis_logscale_checkbox.setEnabled(True)
            self.z_axis_logscale_checkbox.setEnabled(False)
            self.z_axis_logscale_checkbox.setChecked(False)
            self.x_axis_units_label.setEnabled(True)
            self.y_axis_units_label.setEnabled(True)
            self.z_axis_units_label.setEnabled(False)
        elif current_text == "Histogram" or current_text == "Kernel Density Plot":
            self.x_axis_comboBox.setEnabled(True)
            self.y_axis_comboBox.setEnabled(False)
            self.z_axis_comboBox.setEnabled(False)
            self.x_axis_logscale_checkbox.setEnabled(True)
            self.y_axis_logscale_checkbox.setEnabled(False)
            self.z_axis_logscale_checkbox.setEnabled(False)
            self.y_axis_logscale_checkbox.setChecked(False)
            self.z_axis_logscale_checkbox.setChecked(False)
            self.x_axis_units_label.setEnabled(True)
            self.y_axis_units_label.setEnabled(False)
            self.z_axis_units_label.setEnabled(False)
        elif current_text == "3D Scatterplot":
            self.x_axis_comboBox.setEnabled(True)
            self.y_axis_comboBox.setEnabled(True)
            self.z_axis_comboBox.setEnabled(True)
            self.x_axis_logscale_checkbox.setEnabled(True)
            self.y_axis_logscale_checkbox.setEnabled(True)
            self.z_axis_logscale_checkbox.setEnabled(True)
            self.x_axis_units_label.setEnabled(True)
            self.y_axis_units_label.setEnabled(True)
            self.z_axis_units_label.setEnabled(True)
        elif current_text in [
            "Raw All Points Histogram",
            "Filtered All Points Histogram",
            "Event Overlay",
        ]:
            self.x_axis_comboBox.setEnabled(False)
            self.y_axis_comboBox.setEnabled(False)
            self.z_axis_comboBox.setEnabled(False)
            self.x_axis_logscale_checkbox.setEnabled(False)
            self.y_axis_logscale_checkbox.setEnabled(False)
            self.z_axis_logscale_checkbox.setEnabled(False)
            self.x_axis_units_label.setEnabled(False)
            self.y_axis_units_label.setEnabled(False)
            self.z_axis_units_label.setEnabled(False)
        parameters = self.collect_parameters()
        self.logger.debug(
            f"Emitting actionTriggered due to parameter change with parameters {parameters}"
        )
        self.actionTriggered.emit("MetadataView", "plot_type_changed", (parameters,))

    @log(logger=logger)
    def update_axes(self, axes):
        """
        Updates the axes displayed in the comboBoxes for the available plotting axes.
        """
        current_x = self.x_axis_comboBox.currentText()
        current_y = self.y_axis_comboBox.currentText()
        current_z = self.z_axis_comboBox.currentText()

        self.x_axis_comboBox.clear()
        self.y_axis_comboBox.clear()
        self.z_axis_comboBox.clear()

        self.x_axis_comboBox.addItems(axes)
        self.y_axis_comboBox.addItems(axes)
        self.z_axis_comboBox.addItems(axes)

        # If the previously selected item exists in the new list, set it as the current selection
        if current_x in axes:
            index = axes.index(current_x)
            self.x_axis_comboBox.setCurrentIndex(index)
        if current_y in axes:
            index = axes.index(current_y)
            self.y_axis_comboBox.setCurrentIndex(index)
        if current_z in axes:
            index = axes.index(current_z)
            self.z_axis_comboBox.setCurrentIndex(index)

    def update_units(self, comboBox, units_label):
        """Update units based on the selected column in the comboBox and emit an update signal."""
        parameters = self.collect_parameters()
        self.actionTriggered.emit("MetadataView", "columns_updated", (parameters,))

    def update_column_units_label(self, units, axis):
        if units is None or units == "":
            units = " "
        if axis == "x_axis":
            self.x_axis_units_label.setText(units)
        elif axis == "y_axis":
            self.y_axis_units_label.setText(units)
        elif axis == "z_axis":
            self.z_axis_units_label.setText(units)
        else:
            pass

    def toggle_info_button(self, button, comboBox):
        """Enables or disables the info button based on the comboBox selection and item count."""
        button.setEnabled(
            comboBox.count() > 0
            and comboBox.currentIndex() != -1
            and not self.is_placeholder_item(comboBox)
        )

    def is_placeholder_item(self, comboBox):
        """Returns True if the combobox contains a placeholder like 'No Reader', 'No Writer', etc."""
        return comboBox.currentText() in ["No Database"]

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
        self.load_button.clicked.connect(lambda: self.on_button_clicked("load"))
        self.selection_tree_button.clicked.connect(
            lambda: self.on_button_clicked("selection_tree")
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
        self.update_plot_button.clicked.connect(
            lambda: self.on_button_clicked("update_plot")
        )
        self.reset_button.clicked.connect(lambda: self.on_button_clicked("reset"))
        self.save_plot_button.clicked.connect(
            lambda: self.on_button_clicked("save_plot")
        )
        self.export_plot_data_pushButton.clicked.connect(
            lambda: self.on_button_clicked("export_plot_data")
        )
        self.export_csv_subset_button.clicked.connect(
            lambda: self.on_button_clicked("export_csv_subset")
        )
        self.save_filter_button.clicked.connect(
            lambda: self.on_button_clicked("save_filter")
        )
        self.load_filter_button.clicked.connect(
            lambda: self.on_button_clicked("load_filter")
        )
        self.undo_button.clicked.connect(lambda: self.on_button_clicked("undo"))
        self.filter_add_button.clicked.connect(
            lambda: self.on_button_clicked("add_filter")
        )
        self.filter_info_button.clicked.connect(
            lambda: self.on_button_clicked("edit_filter")
        )
        self.filter_delete_button.clicked.connect(
            lambda: self.on_button_clicked("delete_filter")
        )
        self.logger.info("Signals connected")

        # Ensure that validate_inputs is called when inputs change
        self.db_loader_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.plot_type_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.event_index_lineEdit.textChanged.connect(self.validate_inputs)
        self.filter_comboBox.selectionChanged.connect(self.validate_inputs)
        self.bins_lineEdit.textChanged.connect(self.validate_inputs)
        self.x_axis_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.y_axis_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.z_axis_comboBox.currentIndexChanged.connect(self.validate_inputs)

    # Data Validation

    def collect_parameters(self):
        self.logger.info("Collecting parameters")

        # Initialize with default values to handle possible None values
        parameters = {}
        try:
            parameters = {
                "db_loader": self.db_loader_comboBox.currentText()
                or "No Event Database",
                "plot_type": self.plot_type_comboBox.currentText()
                or "Select Plot Type",
                "event_index": [],
                "sizes": self.sizes_checkbox.isChecked(),
                "x_axis": self.x_axis_comboBox.currentText() or None,
                "y_axis": self.y_axis_comboBox.currentText() or None,
                "z_axis": self.z_axis_comboBox.currentText() or None,
                "x_log": self.x_axis_logscale_checkbox.isChecked(),
                "y_log": self.y_axis_logscale_checkbox.isChecked(),
                "z_log": self.z_axis_logscale_checkbox.isChecked(),
                "x_axis_units": self.x_axis_units_label.text() or None,
                "y_axis_units": self.y_axis_units_label.text() or None,
                "z_axis_units": self.z_axis_units_label.text() or None,
                "bins": (
                    [x.strip() for x in self.bins_lineEdit.text().split(",")]
                    if self.bins_lineEdit.text()
                    else None
                ),
            }

            if (
                self.sizes_checkbox.isChecked() is False
                and parameters["bins"] is not None
            ):
                parameters["bins"] = [int(x) for x in parameters["bins"]]
            elif (
                self.sizes_checkbox.isChecked() is True
                and parameters["bins"] is not None
            ):
                parameters["bins"] = [float(x) for x in parameters["bins"]]

            # Collect event index values if valid
            if self.event_index_lineEdit.isValid():
                parameters["event_index"] = self.event_index_lineEdit.get_values()

        except AttributeError:
            pass

        self.logger.debug(f"Collected parameters: {parameters}")
        return parameters

    def get_selected_filter_names(self):
        return self.filter_comboBox.getSelectedItems()

    def on_loader_changed(self):
        """Handles parameter changes and emits an action signal."""
        parameters = self.collect_parameters()
        self.logger.debug(
            f"Emitting actionTriggered due to parameter change with parameters {parameters}"
        )
        self.actionTriggered.emit("MetadataView", "loader_changed", (parameters,))

    def validate_inputs(self):
        """Validates input fields and enables/disables buttons accordingly."""
        # Gather inputs
        db_loader = self.db_loader_comboBox.currentText()
        plot_type = self.plot_type_comboBox.currentText()
        bins_text = self.bins_lineEdit.text()
        x_axis = self.x_axis_comboBox.currentText()
        y_axis = self.y_axis_comboBox.currentText()
        z_axis = self.z_axis_comboBox.currentText()
        filter_selected = self.filter_comboBox.getSelectedItems()
        event_index_valid = self.event_index_lineEdit.isValid()

        db_loader_loaded = True
        is_load_valid = True
        is_save_plot_valid = True
        is_export_valid = True
        is_update_plot_valid = True
        is_plot_events_valid = True
        is_save_edit_delete_filter_valid = True
        is_export_subset_valid = True
        is_bins_valid = (
            all(
                part.strip().isdigit() and int(part.strip()) > 0
                for part in bins_text.split(",")
                if part.strip()
            )
            if bins_text
            else False
        )

        self.logger.debug(
            f"Validating inputs: DB Loader: {db_loader}, Plot Type: {plot_type}, Axes: {x_axis}, {y_axis}, {z_axis}, Filter: {filter_selected}"
        )

        if not is_bins_valid:
            pass

        if not db_loader or db_loader == "No Event Database":
            db_loader_loaded = False
            is_load_valid = False
            is_save_plot_valid = False
            is_export_valid = False
            is_plot_events_valid = False

        if not plot_type or plot_type == "Select Plot Type":
            is_update_plot_valid = False

        if not x_axis:
            is_load_valid = False
            is_update_plot_valid = False

        if not event_index_valid:
            self.logger.debug("Event index is invalid")
            is_plot_events_valid = (
                False  # Disable Plot Events button if event index is not valid
            )

        if not filter_selected:
            is_save_edit_delete_filter_valid = False

        # Enable/disable buttons based on validation results
        self.load_button.setEnabled(is_load_valid)
        self.selection_tree_button.setEnabled(is_load_valid)
        self.left_arrow_button.setEnabled(is_plot_events_valid)
        self.plot_events_pushButton.setEnabled(is_plot_events_valid)
        self.right_arrow_button.setEnabled(is_plot_events_valid)
        self.save_plot_button.setEnabled(is_save_plot_valid)
        self.export_plot_data_pushButton.setEnabled(is_export_valid)
        self.update_plot_button.setEnabled(is_update_plot_valid)
        self.save_filter_button.setEnabled(is_save_edit_delete_filter_valid)
        self.export_csv_subset_button.setEnabled(is_export_subset_valid)
        self.filter_add_button.setEnabled(db_loader_loaded)
        self.filter_info_button.setEnabled(is_save_edit_delete_filter_valid)
        self.filter_delete_button.setEnabled(is_save_edit_delete_filter_valid)
        self.load_filter_button.setEnabled(db_loader_loaded)

    # Actions
    def on_button_clicked(self, button_type):
        """Handles button clicks and emits appropriate signals."""
        parameters = self.collect_parameters()
        self.logger.debug(
            f"Emitting actionTriggered for {button_type} with parameters {parameters}"
        )

        button_actions = {
            "export_plot_data": "export_plot_data",
            "load": "load_plot",
            "selection_tree": "select_experiment_and_channel",
            "left_arrow": "shift_range_backward",
            "plot_events": "plot_events",
            "right_arrow": "shift_range_forward",
            "update_plot": "update_plot",
            "reset": "reset_plot",
            "new_axis": "new_axis",
            "save_plot": "save_plot_config",
            "export_csv_subset": "export_csv_subset",
            "undo": "undo_plot",
            "add_filter": "add_filter",
            "edit_filter": "edit_filter",
            "delete_filter": "delete_filter",
            "save_filter": "save_filter",
            "load_filter": "load_filter",
        }

        if button_type in button_actions:
            self.actionTriggered.emit(
                "EventAnalysisModel", button_actions[button_type], (parameters,)
            )

        # Automatically uncheck the button after it is clicked
        button_mapping = {
            "export_plot_data": self.export_plot_data_pushButton,
            "load": self.load_button,
            "selection_tree": self.selection_tree_button,
            "left_arrow": self.left_arrow_button,
            "plot_events": self.plot_events_pushButton,
            "right_arrow": self.right_arrow_button,
            "update_plot": self.update_plot_button,
            "reset": self.reset_button,
            "save_plot": self.save_plot_button,
            "export_csv_subset": self.export_csv_subset_button,
            "undo": self.undo_button,
            "add_filter": self.filter_add_button,
            "edit_filter": self.filter_info_button,
            "delete_filter": self.filter_delete_button,
            "save_filter": self.save_filter_button,
            "load_filter": self.load_filter_button,
        }

        button_mapping.get(button_type, lambda: None).setChecked(False)

    def update_loaders(self, loaders: list[str]) -> None:
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

    def set_event_index_input(self, value: str):
        self.event_index_lineEdit.blockSignals(True)
        self.event_index_lineEdit.set_range(value)
        self.event_index_lineEdit.blockSignals(False)
        self.validate_inputs()

    def update_filters(self, filters):
        self.logger.info(f"Updating channels to {filters}")

        # Store the current selection(s)
        current_selections = self.filter_comboBox.getSelectedItems()

        self.filter_comboBox.clear()
        self.filter_comboBox.addItems([str(i) for i in filters])

        # Restore selections if they still exist
        for selection in current_selections:
            if selection in [str(i) for i in filters]:
                self.filter_comboBox.selectItem(selection)
