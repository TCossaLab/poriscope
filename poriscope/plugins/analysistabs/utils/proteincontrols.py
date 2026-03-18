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
    Signal,
)
from PySide6.QtGui import QFont, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QButtonGroup,
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
from poriscope.views.integer_range_line_edit import IntegerRangeLineEdit
from poriscope.views.widgets.multiselect_filter import MultiSelectComboBox


class ProteinControls(QWidget):
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
        self.logger.info("Initializing ProteinControls")
        self.setupUi()
        self.connect_signals()
        self.logger.info("ProteinControls initialized")
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

        # 3 columns (LEFT/MIDDLE/RIGHT) spanning over:
        group_layout.setColumnStretch(0, 4)  # 4/12
        group_layout.setColumnStretch(1, 5)  # 5/12
        group_layout.setColumnStretch(2, 3)  # 3/12

        group_layout.setVerticalSpacing(4)

        # ============================================================
        # CREATE WIDGETS (independent of how many rows/columns we have, so they can be reused in different layouts if needed --Below they are ordered by row for reference)
        # ============================================================

        # ---------- LEFT COLUMN ----------

        # Row 0: DB LOADER header: label + add/info/delete
        # --- Set size policies --- (How this widget should behave when there is extra space)
        # QSizePolicy(horizontal, vertical)
        self.db_loader_label = self.createLabel(self.groupBox, 12, "DB LOADER")
        self.db_loader_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Row 1: DB LOADER combobox + scope button
        self.db_loader_comboBox = self.create_comboBox(self.groupBox)
        self.db_loader_comboBox.setObjectName("dbLoaderComboBox")
        self.db_loader_comboBox.currentIndexChanged.connect(self.on_loader_changed)
        self.db_loader_comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Buttons depend on the combobox (enable/disable + callbacks), so create them after the combobox
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

        self.selection_tree_button = QPushButton("Scope", self.groupBox)
        self.selection_tree_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        # Take above defined widgets and put them in a horizontal layout to keep them together as a unit in the grid
        db_loader_top_layout = (
            QHBoxLayout()
        )  # Separate layout for the top row of the left column (label + buttons)
        db_loader_top_layout.setContentsMargins(0, 0, 0, 0)
        db_loader_top_layout.setSpacing(5)
        db_loader_top_layout.setAlignment(Qt.AlignLeft)

        # (Optional but helps placement): vertically center label + toolbuttons so they sit on the same baseline
        db_loader_top_layout.addWidget(self.db_loader_label, alignment=Qt.AlignVCenter)
        db_loader_top_layout.addWidget(
            self.db_loader_add_button, alignment=Qt.AlignVCenter
        )
        db_loader_top_layout.addWidget(
            self.db_loader_info_button, alignment=Qt.AlignVCenter
        )
        db_loader_top_layout.addWidget(
            self.db_loader_delete_button, alignment=Qt.AlignVCenter
        )
        db_loader_top_layout.addStretch(1)

        # Note: Wrapping a layout in a QWidget makes it a controllable, alignable, and stylable unit inside the grid.
        combo_left_widget = QWidget(
            self.groupBox
        )  # Separate widget to hold the combobox and scope button, so they can be aligned as one unit in the grid
        combo_left_layout = QHBoxLayout(
            combo_left_widget
        )  # Separate layout for the combobox + scope button to keep them together and aligned
        combo_left_layout.setContentsMargins(0, 0, 0, 0)
        combo_left_layout.setSpacing(5)
        combo_left_layout.addWidget(self.db_loader_comboBox)
        combo_left_layout.addWidget(self.selection_tree_button)

        # ROW 2: PORE DIAMETER/LENGTH label
        self.pore_diameter_label = self.createLabel(self.groupBox, 12, "DIAMETER")
        self.pore_length_label = self.createLabel(self.groupBox, 12, "LENGTH")

        # ROW 3: PORE DIAMETER/LENGTH input
        self.pore_diameter_lineEdit = QLineEdit(self.groupBox)
        self.pore_diameter_lineEdit.setPlaceholderText("Enter pore diameter")
        self.pore_length_lineEdit = QLineEdit(self.groupBox)
        self.pore_length_lineEdit.setPlaceholderText("Enter pore length")

        # ROW 4: EVENT INDEX
        self.event_index_label = self.createLabel(self.groupBox, 12, "EVENT INDEX")
        self.event_index_lineEdit = IntegerRangeLineEdit(self.groupBox)
        self.event_index_lineEdit.setObjectName("eventIndexLineEdit")
        self.event_index_lineEdit.setPlaceholderText("e.g. 0-15")

        # ROW 5: Plot Events (arrows + button)
        self.plot_events_widget = QWidget(
            self.groupBox
        )  # Separate widget to hold the plot events button and arrows, so it can be aligned as one unit
        plot_events_layout = QHBoxLayout(
            self.plot_events_widget
        )  # Separate layout for the plot events button + arrows to keep them together and aligned
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

        self.plot_histogram_pushButton = self.createButton(
            self.groupBox, "Plot Histogram", bold=True
        )
        self.plot_histogram_pushButton.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        self.right_arrow_button = QPushButton(self.plot_events_widget)
        self.right_arrow_button.setIcon(get_icon("arrow-right.svg"))
        self.right_arrow_button.setIconSize(QSize(16, 16))
        self.right_arrow_button.setFixedWidth(30)

        plot_events_layout.addWidget(self.left_arrow_button)
        plot_events_layout.addWidget(self.plot_events_pushButton)
        plot_events_layout.addWidget(self.plot_histogram_pushButton)
        plot_events_layout.addWidget(self.right_arrow_button)

        # ---------- MIDDLE COLUMN ----------

        # ROW 0: "Distribution event fitting" header
        self.dist_label = self.createLabel(
            self.groupBox, 12, "DISTRIBUTION EVENT FITTING"
        )

        # ROW 1: Individual / Ensemble buttons
        self.individual_button = self.createButton(
            self.groupBox, "Individual", bold=False
        )
        self.ensemble_button = self.createButton(self.groupBox, "Ensemble", bold=False)

        self.analysis_mode_group = QButtonGroup(self.groupBox)
        self.analysis_mode_group.setExclusive(True)
        self.analysis_mode_group.addButton(self.individual_button)
        self.analysis_mode_group.addButton(self.ensemble_button)

        # Default selection
        self.individual_button.setChecked(True)

        def _set_mode_bold():
            f1 = self.individual_button.font()
            f2 = self.ensemble_button.font()

            f1.setBold(self.individual_button.isChecked())
            self.individual_button.setFont(f1)

            f2.setBold(self.ensemble_button.isChecked())
            self.ensemble_button.setFont(f2)

        self.individual_button.toggled.connect(lambda _: _set_mode_bold())
        self.ensemble_button.toggled.connect(lambda _: _set_mode_bold())

        # Apply initial state
        _set_mode_bold()

        individual_ensemble_widget = QWidget(self.groupBox)
        individual_ensemble_layout = QHBoxLayout(individual_ensemble_widget)
        individual_ensemble_layout.setContentsMargins(0, 0, 0, 0)
        individual_ensemble_layout.setSpacing(5)
        individual_ensemble_layout.addWidget(self.individual_button, 1)
        individual_ensemble_layout.addWidget(self.ensemble_button, 1)

        # ROW 2: N + BINS + SIZES labels
        # Left half: N label | Right half: BINS + SIZES labels grouped together
        n_bins_labels_widget = QWidget(self.groupBox)
        n_bins_labels_layout = QHBoxLayout(n_bins_labels_widget)
        n_bins_labels_layout.setContentsMargins(0, 0, 0, 0)
        n_bins_labels_layout.setSpacing(5)

        self.n_values_label = self.createLabel(self.groupBox, 12, "N")
        bins_label = self.createLabel(self.groupBox, 12, "BINS")
        sizes_label = self.createLabel(self.groupBox, 12, "SIZES")
        sizes_label.setAlignment(Qt.AlignCenter)

        # BINS + SIZES labels grouped as one right-half unit
        bins_sizes_right_label_widget = QWidget(self.groupBox)
        bins_sizes_right_label_layout = QHBoxLayout(bins_sizes_right_label_widget)
        bins_sizes_right_label_layout.setContentsMargins(0, 0, 0, 0)
        bins_sizes_right_label_layout.setSpacing(5)
        bins_sizes_right_label_layout.addWidget(bins_label, 1)
        bins_sizes_right_label_layout.addWidget(sizes_label, 0)

        n_bins_labels_layout.addWidget(self.n_values_label, 1)  # left half
        n_bins_labels_layout.addWidget(bins_sizes_right_label_widget, 1)  # right half

        # ROW 3: N + BINS + SIZES inputs
        # Left half: N input | Right half: BINS input + SIZES checkbox
        n_bins_inputs_widget = QWidget(self.groupBox)
        n_bins_inputs_layout = QHBoxLayout(n_bins_inputs_widget)
        n_bins_inputs_layout.setContentsMargins(0, 0, 0, 0)
        n_bins_inputs_layout.setSpacing(5)

        # Validators belong to the widget's configuration, not to runtime logic:
        # A QValidator is part of how the QLineEdit behaves. So it should be defined at the same time the widget is created.

        # Int validator: e.g., 10,15,20
        int_regex = QRegularExpression(r"^\d+(,\d+)*,?$")
        self.int_validator = QRegularExpressionValidator(int_regex)

        # Float validator: e.g., 1.2,3.5,4.0
        float_regex = QRegularExpression(r"^\d*\.?\d+(,\d*\.?\d+)*,?$")
        self.float_validator = QRegularExpressionValidator(float_regex)

        self.n_values_lineEdit = QLineEdit(self.groupBox)
        self.n_values_lineEdit.setObjectName("nValuesLineEdit")
        self.n_values_lineEdit.setPlaceholderText("e.g. 1000")
        self.n_values_lineEdit.setValidator(self.int_validator)

        self.bins_lineEdit = QLineEdit(self.groupBox)
        self.bins_lineEdit.setObjectName("binsLineEdit")
        self.bins_lineEdit.setValidator(self.int_validator)

        self.sizes_checkbox = QCheckBox(self.groupBox)

        sizes_box_wrap = QVBoxLayout()
        sizes_box_wrap.setContentsMargins(0, 0, 0, 0)
        sizes_box_wrap.addStretch()
        sizes_box_wrap.addWidget(self.sizes_checkbox, alignment=Qt.AlignCenter)
        sizes_box_wrap.addStretch()

        # BINS + SIZES grouped as one right-half unit
        bins_sizes_right_widget = QWidget(self.groupBox)
        bins_sizes_right_layout = QHBoxLayout(bins_sizes_right_widget)
        bins_sizes_right_layout.setContentsMargins(0, 0, 0, 0)
        bins_sizes_right_layout.setSpacing(5)
        bins_sizes_right_layout.addWidget(self.bins_lineEdit, 1)
        bins_sizes_right_layout.addLayout(sizes_box_wrap, 0)

        n_bins_inputs_layout.addWidget(self.n_values_lineEdit, 1)  # left half
        n_bins_inputs_layout.addWidget(bins_sizes_right_widget, 1)  # right half

        self.sizes_checkbox.toggled.connect(self._on_sizes_checkbox_toggled)
        self._on_sizes_checkbox_toggled(self.sizes_checkbox.isChecked())

        # ROW 4: Update / Undo / Reset row
        self.update_plot_button = self.createButton(
            self.groupBox, "Update Plot", bold=True
        )
        self.undo_button = self.createButton(self.groupBox, "Undo", bold=True)
        self.reset_button = self.createButton(self.groupBox, "Reset", bold=True)

        update_undo_reset_widget = QWidget(self.groupBox)
        update_undo_reset_layout = QHBoxLayout(update_undo_reset_widget)
        update_undo_reset_layout.setContentsMargins(0, 0, 0, 0)
        update_undo_reset_layout.setSpacing(5)
        update_undo_reset_layout.addWidget(self.update_plot_button, 2)
        update_undo_reset_layout.addWidget(self.undo_button, 1)
        update_undo_reset_layout.addWidget(self.reset_button, 1)

        # ROW 5: Commit row (Commit Individual / Commit All)
        self.commit_individual = self.createButton(
            self.groupBox, "Commit Individual", bold=True
        )
        self.commit_all = self.createButton(self.groupBox, "Commit All", bold=True)

        commit_widget = QWidget(self.groupBox)
        commit_layout = QHBoxLayout(commit_widget)
        commit_layout.setContentsMargins(0, 0, 0, 0)
        commit_layout.setSpacing(5)
        commit_layout.addWidget(self.commit_individual, 1)
        commit_layout.addWidget(self.commit_all, 1)

        # ---------- RIGHT COLUMN ----------

        # Row 0: Filter header row: label + add/info/delete
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
        self.filter_comboBox.selectionChanged.connect(self.validate_inputs)

        filter_header_layout = QHBoxLayout()
        filter_header_layout.setContentsMargins(0, 0, 0, 0)
        filter_header_layout.setSpacing(5)
        filter_header_layout.setAlignment(Qt.AlignLeft)
        filter_header_layout.addWidget(self.filter_label)
        filter_header_layout.addWidget(self.filter_add_button)
        filter_header_layout.addWidget(self.filter_info_button)
        filter_header_layout.addWidget(self.filter_delete_button)
        filter_header_layout.addStretch(1)

        # ROW 3: Save Filter button
        self.save_filter_button = self.createButton(
            self.groupBox, "Save Filter", bold=True
        )

        # ROW 5: Load Filter button
        self.load_filter_button = self.createButton(
            self.groupBox, "Load Filter", bold=True
        )

        # ROW 7: Export Plot Data buttons
        self.export_plot_data_left_pushButton = self.createButton(
            self.groupBox, "Export Left Plot", bold=True
        )
        self.export_plot_data_right_pushButton = self.createButton(
            self.groupBox, "Export Right Plot", bold=True
        )

        # ============================================================
        # PLACE elements IN GRID
        # Rows: 0..6, Cols: 0..2
        # (row, column)
        # ============================================================

        # Row 0
        group_layout.addLayout(db_loader_top_layout, 0, 0)
        group_layout.addWidget(self.dist_label, 0, 1)
        group_layout.addLayout(filter_header_layout, 0, 2)

        # Row 1
        group_layout.addWidget(combo_left_widget, 1, 0)
        group_layout.addWidget(individual_ensemble_widget, 1, 1)
        group_layout.addWidget(self.filter_comboBox, 1, 2)

        # Row 2
        pore_labels_widget = QWidget(self.groupBox)
        pore_labels_layout = QHBoxLayout(pore_labels_widget)
        pore_labels_layout.setContentsMargins(0, 0, 0, 0)
        pore_labels_layout.setSpacing(5)
        pore_labels_layout.addWidget(self.pore_diameter_label, 1)
        pore_labels_layout.addWidget(self.pore_length_label, 1)
        group_layout.addWidget(pore_labels_widget, 2, 0)
        group_layout.addWidget(n_bins_labels_widget, 2, 1)

        # Row 3
        pore_inputs_widget = QWidget(self.groupBox)
        pore_inputs_layout = QHBoxLayout(pore_inputs_widget)
        pore_inputs_layout.setContentsMargins(0, 0, 0, 0)
        pore_inputs_layout.setSpacing(5)
        pore_inputs_layout.addWidget(self.pore_diameter_lineEdit, 1)
        pore_inputs_layout.addWidget(self.pore_length_lineEdit, 1)
        group_layout.addWidget(pore_inputs_widget, 3, 0)
        group_layout.addWidget(n_bins_inputs_widget, 3, 1)
        group_layout.addWidget(self.save_filter_button, 3, 2)

        # Row 4
        group_layout.addWidget(self.event_index_label, 4, 0)

        # Row 5
        group_layout.addWidget(self.event_index_lineEdit, 5, 0)
        group_layout.addWidget(update_undo_reset_widget, 5, 1)
        group_layout.addWidget(self.load_filter_button, 5, 2)

        # Row 6
        group_layout.addWidget(self.plot_events_widget, 6, 0)
        group_layout.addWidget(commit_widget, 6, 1)

        export_widget = QWidget(self.groupBox)
        export_layout = QHBoxLayout(export_widget)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.setSpacing(5)
        export_layout.addWidget(self.export_plot_data_left_pushButton, 1)
        export_layout.addWidget(self.export_plot_data_right_pushButton, 1)
        group_layout.addWidget(export_widget, 6, 2)

        # ============================================================
        # SIZING
        # ============================================================
        self.db_loader_comboBox.setMinimumWidth(160)
        self.selection_tree_button.setFixedWidth(60)

        self.pore_diameter_lineEdit.setMinimumWidth(80)
        self.pore_length_lineEdit.setMinimumWidth(80)
        self.event_index_lineEdit.setMinimumWidth(160)
        self.n_values_lineEdit.setMinimumWidth(60)
        self.bins_lineEdit.setMinimumWidth(60)

        # Add groupbox to main layout
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
        self.selection_tree_button.clicked.connect(
            lambda: self.on_button_clicked("selection_tree")
        )
        self.left_arrow_button.clicked.connect(
            lambda: self.on_button_clicked("left_arrow")
        )
        self.plot_events_pushButton.clicked.connect(
            lambda: self.on_button_clicked("plot_events")
        )
        self.plot_histogram_pushButton.clicked.connect(
            lambda: self.on_button_clicked("plot_histogram")
        )
        self.right_arrow_button.clicked.connect(
            lambda: self.on_button_clicked("right_arrow")
        )
        self.individual_button.clicked.connect(
            lambda: self.on_button_clicked("individual")
        )
        self.ensemble_button.clicked.connect(lambda: self.on_button_clicked("ensemble"))
        self.update_plot_button.clicked.connect(
            lambda: self.on_button_clicked("update_plot")
        )
        self.undo_button.clicked.connect(lambda: self.on_button_clicked("undo"))
        self.reset_button.clicked.connect(lambda: self.on_button_clicked("reset"))
        self.commit_individual.clicked.connect(
            lambda: self.on_button_clicked("commit_individual")
        )
        self.commit_all.clicked.connect(lambda: self.on_button_clicked("commit_all"))
        self.filter_add_button.clicked.connect(
            lambda: self.on_button_clicked("add_filter")
        )
        self.filter_info_button.clicked.connect(
            lambda: self.on_button_clicked("edit_filter")
        )
        self.filter_delete_button.clicked.connect(
            lambda: self.on_button_clicked("delete_filter")
        )
        self.save_filter_button.clicked.connect(
            lambda: self.on_button_clicked("save_filter")
        )
        self.load_filter_button.clicked.connect(
            lambda: self.on_button_clicked("load_filter")
        )
        self.export_plot_data_left_pushButton.clicked.connect(
            lambda: self.on_button_clicked("export_plot_data_left")
        )
        self.export_plot_data_right_pushButton.clicked.connect(
            lambda: self.on_button_clicked("export_plot_data_right")
        )
        self.logger.info("Signals connected")

        # Ensure that validate_inputs is called when inputs change
        self.db_loader_comboBox.currentIndexChanged.connect(self.validate_inputs)
        self.pore_diameter_lineEdit.textChanged.connect(self.validate_inputs)
        self.pore_length_lineEdit.textChanged.connect(self.validate_inputs)
        self.event_index_lineEdit.textChanged.connect(self.validate_inputs)
        self.n_values_lineEdit.textChanged.connect(self.validate_inputs)
        self.bins_lineEdit.textChanged.connect(self.validate_inputs)
        self.filter_comboBox.selectionChanged.connect(self.validate_inputs)
        self.individual_button.toggled.connect(self.validate_inputs)
        self.ensemble_button.toggled.connect(self.validate_inputs)

    # Data Validation

    def collect_parameters(self):
        self.logger.info("Collecting parameters")

        # Initialize with default values to handle possible None values
        parameters = {}
        try:
            parameters = {
                "db_loader": self.db_loader_comboBox.currentText()
                or "No Event Database",
                "pore_diameter": self.pore_diameter_lineEdit.text(),  # TBD: decide on format and parsing in controller
                "pore_length": self.pore_length_lineEdit.text(),  # TBD: decide on format and parsing in controller
                "event_index": [],
                "n_values": self.n_values_lineEdit.text(),
                "sizes": self.sizes_checkbox.isChecked(),
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
        self.actionTriggered.emit("ProteinView", "loader_changed", (parameters,))

    def validate_inputs(self):
        """Validates input fields and enables/disables buttons accordingly."""

        # -----------------
        # Gather inputs
        # -----------------
        db_loader = self.db_loader_comboBox.currentText()
        pore_diameter_valid = bool(self.pore_diameter_lineEdit.text().strip())
        pore_length_valid = bool(self.pore_length_lineEdit.text().strip())
        # bins_text = self.bins_lineEdit.text()
        filter_selected = self.filter_comboBox.getSelectedItems()
        event_index_valid = self.event_index_lineEdit.isValid()

        individual_selected = self.individual_button.isChecked()
        ensemble_selected = self.ensemble_button.isChecked()

        # -----------------
        # Default states
        # -----------------
        db_loader_loaded = True
        is_scope_valid = True
        is_individual_analysis_valid = True
        is_ensemble_analysis_valid = True
        is_commit_individual_valid = True
        is_commit_all_valid = True
        is_export_valid = True
        is_undo_valid = True
        is_reset_valid = True
        is_plot_events_valid = True
        is_save_edit_delete_filter_valid = True

        # DB Loader validation
        if not db_loader or db_loader == "No Event Database":
            db_loader_loaded = False
            is_scope_valid = False
            is_export_valid = False
            is_plot_events_valid = False

        # is_bins_valid = (
        #    all(
        #        part.strip().isdigit() and int(part.strip()) > 0
        #        for part in bins_text.split(",")
        #        if part.strip()
        #    )
        #    if bins_text
        #    else False
        # )

        self.logger.debug(
            f"Validating inputs: DB Loader: {db_loader}, "
            f"Individual: {individual_selected}, Ensemble: {ensemble_selected}, "
            f"Filter: {filter_selected}"
        )

        # Pore dimensions required for analysis
        if not pore_diameter_valid or not pore_length_valid:
            is_individual_analysis_valid = False
            is_ensemble_analysis_valid = False

        # Event index validation
        if not event_index_valid:
            self.logger.debug("Event index is invalid")
            is_plot_events_valid = False

        # Filter validation
        if not filter_selected:
            is_save_edit_delete_filter_valid = False

        # Commit logic based on mode selection
        if individual_selected:
            is_commit_individual_valid = (
                is_individual_analysis_valid
                and db_loader_loaded
                and pore_diameter_valid
                and pore_length_valid
            )
            is_commit_all_valid = False

        elif ensemble_selected:
            is_commit_all_valid = (
                is_ensemble_analysis_valid
                and db_loader_loaded
                and pore_diameter_valid
                and pore_length_valid
            )
            is_commit_individual_valid = False

        else:
            # No mode selected (should not happen if button group is exclusive)
            is_commit_individual_valid = False
            is_commit_all_valid = False

        # ---------------------------
        # Enable/disable buttons
        # ---------------------------
        self.selection_tree_button.setEnabled(is_scope_valid)

        self.left_arrow_button.setEnabled(is_plot_events_valid)
        self.plot_events_pushButton.setEnabled(is_plot_events_valid)
        self.plot_histogram_pushButton.setEnabled(is_plot_events_valid)
        self.right_arrow_button.setEnabled(is_plot_events_valid)

        self.export_plot_data_left_pushButton.setEnabled(is_export_valid)
        self.export_plot_data_right_pushButton.setEnabled(is_export_valid)

        self.update_plot_button.setEnabled(
            db_loader_loaded and pore_diameter_valid and pore_length_valid
        )
        self.undo_button.setEnabled(is_undo_valid)
        self.reset_button.setEnabled(is_reset_valid)

        self.filter_add_button.setEnabled(db_loader_loaded)
        self.save_filter_button.setEnabled(is_save_edit_delete_filter_valid)
        self.filter_info_button.setEnabled(is_save_edit_delete_filter_valid)
        self.filter_delete_button.setEnabled(is_save_edit_delete_filter_valid)
        self.load_filter_button.setEnabled(db_loader_loaded)

        self.commit_individual.setEnabled(is_commit_individual_valid)
        self.commit_all.setEnabled(is_commit_all_valid)

    # Actions
    def on_button_clicked(self, button_type):
        """Handles button clicks and emits appropriate signals."""
        parameters = self.collect_parameters()
        self.logger.debug(
            f"Emitting actionTriggered for {button_type} with parameters {parameters}"
        )

        button_actions = {
            "export_plot_data_left": "export_plot_data_left",
            "export_plot_data_right": "export_plot_data_right",
            "selection_tree": "select_experiment_and_channel",
            "left_arrow": "shift_range_backward",
            "plot_events": "plot_events",
            "plot_histogram": "plot_histogram",
            "right_arrow": "shift_range_forward",
            "update_plot": "update_plot",
            "reset": "reset_plot",
            "undo": "undo_plot",
            "add_filter": "add_filter",
            "edit_filter": "edit_filter",
            "delete_filter": "delete_filter",
            "save_filter": "save_filter",
            "load_filter": "load_filter",
            "individual": "set_mode_individual",
            "ensemble": "set_mode_ensemble",
            "commit_individual": "commit_individual",
            "commit_all": "commit_all",
        }

        if button_type in button_actions:
            self.actionTriggered.emit(
                "ProteinModel", button_actions[button_type], (parameters,)
            )

        # Automatically uncheck the button after it is clicked
        button_mapping = {
            "export_plot_data_left": self.export_plot_data_left_pushButton,
            "export_plot_data_right": self.export_plot_data_right_pushButton,
            "selection_tree": self.selection_tree_button,
            "left_arrow": self.left_arrow_button,
            "plot_events": self.plot_events_pushButton,
            "plot_histogram": self.plot_histogram_pushButton,
            "right_arrow": self.right_arrow_button,
            "update_plot": self.update_plot_button,
            "reset": self.reset_button,
            "undo": self.undo_button,
            "add_filter": self.filter_add_button,
            "edit_filter": self.filter_info_button,
            "delete_filter": self.filter_delete_button,
            "save_filter": self.save_filter_button,
            "load_filter": self.load_filter_button,
            "commit_individual": self.commit_individual,
            "commit_all": self.commit_all,
        }

        btn = button_mapping.get(button_type)
        if btn is not None:
            # Don't uncheck mode buttons (they should stay pushed)
            if button_type not in ("individual", "ensemble"):
                btn.setChecked(False)

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
