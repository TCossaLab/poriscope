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
import os
import sys
from typing import Any, Dict, List

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QDoubleValidator, QIcon, QIntValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from poriscope.plugins.analysistabs.utils.walkthrough_mixin import WalkthroughMixin


class ClusteringSettingsDialog(QDialog, WalkthroughMixin):
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        dynamic_title="Clustering Settings",
        available_columns=None,
        available_methods=None,
        column_units=None,
        preselected_config=None,
        method_parameters=None,
    ):

        super().__init__()
        self._init_walkthrough()

        self.setWindowTitle("Clustering Settings")
        self.setMinimumSize(700, 500)

        self.dynamic_title = dynamic_title
        self.available_methods = available_methods or []
        self.available_columns = available_columns or []
        self.method_parameters = method_parameters or {}
        self.column_units = column_units or {}
        self.preselected_config = (
            preselected_config
            if preselected_config is not None
            else self.get_default_config()
        )

        self.selected_columns = set()
        self.column_item_widgets = {}
        self.scroll_row = 0

        self.icon_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "configs", "icons"
        )

        self.init_ui()

    # @log(logger=logger)
    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # === Title ===
        self.title_label = QLabel(f"{self.dynamic_title}")
        self.title_label.setAlignment(Qt.AlignHCenter)
        font = self.title_label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.title_label.setFont(font)
        main_layout.addWidget(self.title_label)

        # === Method ===
        method_label = QLabel("METHOD")
        method_label.setFont(self._bold_font())
        self.method_combo = QComboBox()
        self.method_combo.addItem("Select Method")
        self.method_combo.addItems(self.available_methods)
        self.method_combo.setCurrentIndex(0)
        self.method_combo.currentTextChanged.connect(self.update_method_parameters)
        main_layout.addWidget(method_label)
        main_layout.addWidget(self.method_combo)

        # === Dynamic Method Parameters ===
        self.param_container = QWidget()
        self.param_layout = QHBoxLayout()
        self.param_layout.setAlignment(Qt.AlignCenter)
        self.param_container.setLayout(self.param_layout)
        main_layout.addWidget(self.param_container)

        # === Filter ===
        filter_label = QLabel("FILTER")
        filter_label.setFont(self._bold_font())
        self.filter_text = QTextEdit()
        self.filter_text.setPlaceholderText("Enter SQL filter")
        self.filter_text.setFixedHeight(60)
        main_layout.addWidget(filter_label)
        main_layout.addWidget(self.filter_text)

        # === Column Group ===
        group_box = QGroupBox()
        group_layout = QVBoxLayout(group_box)

        # === Header row ===
        header_layout = QGridLayout()
        for i, stretch in enumerate([2, 1, 1, 1, 1]):
            header_layout.setColumnStretch(i, stretch)
        headers = ["COLUMNS", "LOG", "NORM", "PLOT"]
        for i, text in enumerate(headers):
            label = QLabel(text)
            label.setFont(self._bold_font())
            if text == "COLUMNS":
                label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            else:
                label.setAlignment(Qt.AlignCenter)
            header_layout.addWidget(label, 0, i)
        group_layout.addLayout(header_layout)

        # === Scroll Area ===
        self.scroll_container = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_container)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setHorizontalSpacing(4)
        self.scroll_layout.setVerticalSpacing(4)

        # Set column stretch to match header
        for i, stretch in enumerate([2, 1, 1, 1, 1]):
            self.scroll_layout.setColumnStretch(i, stretch)

        # === Two Default Static Rows ===
        self.default_row_widgets: List[Dict[str, Any]] = []
        self._add_default_row(self.scroll_layout, row=0)
        self._add_default_row(self.scroll_layout, row=1)

        # === Add Row (always at the bottom) ===
        self.add_row_index = 2  # starts after the default rows
        self._init_add_row()  # prepares widgets
        self._place_add_row_at_bottom()  # inserts them at row 2

        # === Spacer to force top alignment ===
        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.scroll_layout.addWidget(self.spacer, 9999, 0, 1, 5)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setWidget(self.scroll_container)
        group_layout.addWidget(self.scroll_area)
        main_layout.addWidget(group_box)

        self.plot_warning_label = QLabel()
        self.plot_warning_label.setStyleSheet(
            "color: red; font-size: 10pt; font-style: italic;"
        )
        self.plot_warning_label.setAlignment(Qt.AlignRight)
        self.plot_warning_label.setVisible(False)
        main_layout.addWidget(self.plot_warning_label)

        # === Apply / Cancel Buttons ===
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.apply_button = QPushButton("Apply")
        self.cancel_button = QPushButton("Cancel")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        button_row.addWidget(self.apply_button)
        button_row.addWidget(self.cancel_button)
        main_layout.addLayout(button_row)

        # === Restore Preselected Config ===
        if self.preselected_config:
            try:
                selected_method = self.preselected_config.get("method", "")
                self.method_combo.setCurrentText(selected_method)
                self.filter_text.setText(self.preselected_config.get("filter", ""))
                self.update_method_parameters(selected_method)

                for i, col_data in enumerate(
                    self.preselected_config.get("columns", [])
                ):
                    if i < len(self.default_row_widgets):
                        row = self.default_row_widgets[i]
                        row["combo"].setCurrentText(col_data["column"])
                        row["log_cb"].setChecked(col_data["log"])
                        row["norm_cb"].setChecked(col_data["norm"])
                        row["plot_cb"].setChecked(col_data["plot"])
                    else:
                        self.add_column_item_with_values(
                            col_data["column"],
                            col_data["log"],
                            col_data["norm"],
                            col_data["plot"],
                        )

            except Exception as e:
                self.logger.error(f"Failed to restore preselected config: {e}")

        self._check_apply_enabled()

    def _init_add_row(self):
        self.add_button = QPushButton("Add Column")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.clicked.connect(self.add_column_item)
        self.add_button.setFixedHeight(24)  # same as default widgets like combo boxes
        self.add_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.add_row_container = QWidget()
        add_row_layout = QHBoxLayout(self.add_row_container)
        add_row_layout.setContentsMargins(0, 0, 0, 0)
        add_row_layout.setSpacing(0)
        add_row_layout.addWidget(self.add_button)

    def _place_add_row_at_bottom(self):
        self.scroll_layout.addWidget(
            self.add_row_container, self.add_row_index, 0, 1, 5
        )

    def get_default_config(self):
        return {
            "method": "HDBSCAN",
            "filter": "",
            "method_params": {
                "HDBSCAN_Cluster_Size_input": "40",
                "HDBSCAN_Min_Points_input": "1",
                "HDBSCAN_Sensitivity_input": "1.0",
            },
            "columns": [],
        }

    def update_method_parameters(self, method_name):
        # Clear old parameter widgets
        while self.param_layout.count():
            widget = self.param_layout.takeAt(0).widget()
            if widget:
                widget.setParent(None)

        fields = self.method_parameters.get(method_name, [])
        for field_def in fields:
            field = field_def["name"]
            input_type = field_def.get("type", "str")

            label = QLabel(f"{field}:")
            line_edit = QLineEdit()

            # Set validators based on type
            if input_type == "int":
                line_edit.setValidator(QIntValidator())
            elif input_type == "float":
                line_edit.setValidator(QDoubleValidator())

            key = f"{method_name}_{field.replace(' ', '_')}_input"
            line_edit.setObjectName(key)

            # Restore saved value if present
            if self.preselected_config:
                saved = self.preselected_config.get("method_params", {})
                if key in saved:
                    line_edit.setText(saved[key])

            self.param_layout.addWidget(label)
            self.param_layout.addWidget(line_edit)

    def add_column_item_with_values(self, column, log, norm, plot):
        if len(self.column_item_widgets) >= 8:
            return

        row = self.add_row_index
        self.add_row_index += 1

        combo = QComboBox()
        combo.currentTextChanged.connect(self._check_apply_enabled)
        combo.addItem("Select Column")
        combo.addItems(sorted(self.available_columns))
        combo.setCurrentText(column)
        combo.setMinimumWidth(120)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        unit_label = QLabel()
        unit_label.setStyleSheet("color: gray;")
        unit_label.setMinimumWidth(50)
        unit_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        unit_label.setVisible(False)
        combo.currentTextChanged.connect(
            lambda text, label=unit_label: self.update_unit_label_for_row(text, label)
        )
        self.update_unit_label_for_row(column, unit_label)

        combo_container = QWidget()
        combo_layout = QHBoxLayout(combo_container)
        combo_layout.setContentsMargins(0, 0, 0, 0)
        combo_layout.addWidget(combo)
        combo_layout.addWidget(unit_label)
        combo_layout.addStretch()

        log_cb = QCheckBox()
        norm_cb = QCheckBox()
        plot_cb = QCheckBox()
        plot_cb.stateChanged.connect(self._check_apply_enabled)
        log_cb.setChecked(log)
        norm_cb.setChecked(norm)
        plot_cb.setChecked(plot)

        delete_button = QPushButton()
        delete_icon = QIcon(os.path.join(self.icon_path, "trash.svg"))
        delete_button.setIcon(delete_icon)
        delete_button.setFlat(True)
        delete_button.setIconSize(QSize(15, 15))
        delete_button.setCursor(Qt.PointingHandCursor)

        key = f"row_{row}"
        delete_button.clicked.connect(lambda _, k=key: self.remove_column_item(k))

        self.scroll_layout.addWidget(combo_container, row, 0)
        self.scroll_layout.addWidget(log_cb, row, 1, alignment=Qt.AlignCenter)
        self.scroll_layout.addWidget(norm_cb, row, 2, alignment=Qt.AlignCenter)
        self.scroll_layout.addWidget(plot_cb, row, 3, alignment=Qt.AlignCenter)
        self.scroll_layout.addWidget(delete_button, row, 4, alignment=Qt.AlignCenter)

        self.column_item_widgets[key] = {
            "row": row,
            "combo": combo,
            "unit_label": unit_label,
            "log_cb": log_cb,
            "norm_cb": norm_cb,
            "plot_cb": plot_cb,
        }

        self.scroll_layout.removeWidget(self.add_button)
        self._place_add_row_at_bottom()
        self._check_apply_enabled()

    # @log(logger=logger)
    def _bold_font(self):
        font = QLabel().font()
        font.setBold(True)
        return font

    # @log(logger=logger)
    def update_unit_label(self, text):
        unit = self.column_units.get(text, "")
        self.unit_label.setText(f"({unit})" if unit else "")
        self.unit_label.setVisible(bool(unit))

    # @log(logger=logger)
    def update_unit_label_for_row(self, text, label):
        unit = self.column_units.get(text, "")
        label.setText(f"({unit})" if unit else "")
        label.setVisible(bool(unit))

    def add_column_item(self):
        if len(self.column_item_widgets) >= 8:
            QMessageBox.warning(
                self, "Limit Reached", "You can only add up to 8 dynamic columns."
            )
            return

        row = self.add_row_index
        self.add_row_index += 1

        combo = QComboBox()
        combo.currentTextChanged.connect(self._check_apply_enabled)
        combo.addItem("Select Column")
        combo.addItems(sorted(self.available_columns))
        combo.setMinimumWidth(120)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        unit_label = QLabel()
        unit_label.setStyleSheet("color: gray;")
        unit_label.setMinimumWidth(50)
        unit_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        unit_label.setVisible(False)
        combo.currentTextChanged.connect(
            lambda text, label=unit_label: self.update_unit_label_for_row(text, label)
        )

        combo_container = QWidget()
        combo_layout = QHBoxLayout(combo_container)
        combo_layout.setContentsMargins(0, 0, 0, 0)
        combo_layout.addWidget(combo)
        combo_layout.addWidget(unit_label)
        combo_layout.addStretch()

        log_cb = QCheckBox()
        norm_cb = QCheckBox()
        plot_cb = QCheckBox()
        plot_cb.stateChanged.connect(self._check_apply_enabled)

        delete_button = QPushButton()
        delete_icon = QIcon(os.path.join(self.icon_path, "trash.svg"))
        delete_button.setIcon(delete_icon)
        delete_button.setFlat(True)
        delete_button.setIconSize(QSize(15, 15))
        delete_button.setCursor(Qt.PointingHandCursor)

        # Create a unique key since no pre-selected column
        key = f"row_{row}"
        delete_button.clicked.connect(lambda _, k=key: self.remove_column_item(k))

        self.scroll_layout.addWidget(combo_container, row, 0)
        self.scroll_layout.addWidget(log_cb, row, 1, alignment=Qt.AlignCenter)
        self.scroll_layout.addWidget(norm_cb, row, 2, alignment=Qt.AlignCenter)
        self.scroll_layout.addWidget(plot_cb, row, 3, alignment=Qt.AlignCenter)
        self.scroll_layout.addWidget(delete_button, row, 4, alignment=Qt.AlignCenter)

        self.column_item_widgets[key] = {
            "row": row,
            "combo": combo,
            "unit_label": unit_label,
            "log_cb": log_cb,
            "norm_cb": norm_cb,
            "plot_cb": plot_cb,
        }

        # Move the add button to the next row
        self.scroll_layout.removeWidget(self.add_button)
        self._place_add_row_at_bottom()
        self._check_apply_enabled()

    def _move_add_row_down(self):
        # Remove current add row widgets
        for col in range(5):
            item = self.scroll_layout.itemAtPosition(self.add_row_index - 1, col)
            if item and item.widget():
                item.widget().setParent(None)

        # Reinsert at new index
        self._place_add_row_at_bottom()

    def remove_column_item(self, key):
        if key in self.column_item_widgets:
            row_index = self.column_item_widgets[key]["row"]
            for col in range(5):
                item = self.scroll_layout.itemAtPosition(row_index, col)
                if item and item.widget():
                    item.widget().deleteLater()
            del self.column_item_widgets[key]
            self._refresh_add_button_position()

    def get_result(self):
        column_data = []

        # Include static default rows
        for widget in self.default_row_widgets:
            col = widget["combo"].currentText()
            if col == "Select Column":
                continue  # skip if user didn't choose a column
            column_data.append(
                {
                    "column": col,
                    "unit": self.column_units.get(col, ""),
                    "log": widget["log_cb"].isChecked(),
                    "norm": widget["norm_cb"].isChecked(),
                    "plot": widget["plot_cb"].isChecked(),
                }
            )

        # Include dynamically added rows
        for column, data in self.column_item_widgets.items():
            current_column = data["combo"].currentText()
            column_data.append(
                {
                    "column": current_column,
                    "unit": self.column_units.get(current_column, ""),
                    "log": data["log_cb"].isChecked(),
                    "norm": data["norm_cb"].isChecked(),
                    "plot": data["plot_cb"].isChecked(),
                }
            )

        # Collect method-specific parameters
        method_params = {}
        for i in range(self.param_layout.count()):
            widget = self.param_layout.itemAt(i).widget()
            if isinstance(widget, QLineEdit):
                method_params[widget.objectName()] = widget.text()

        result = {
            "method": self.method_combo.currentText(),
            "method_params": method_params,
            "filter": self.filter_text.toPlainText(),
            "columns": column_data,
        }

        self.logger.info(f"Clustering Settings Dialog params: {result}")
        return result

    # @log(logger=logger)
    def reset_top_inputs(self):
        self.column_combo.setCurrentIndex(0)
        self.unit_label.clear()
        self.unit_label.setVisible(False)
        self.log_cb.setChecked(False)
        self.norm_cb.setChecked(False)
        self.plot_cb.setChecked(False)

    def _add_default_row(self, layout, row):
        combo = QComboBox()
        combo.currentTextChanged.connect(self._check_apply_enabled)
        combo.addItem("Select Column")
        combo.addItems(sorted(self.available_columns))
        combo.setMinimumWidth(120)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        unit_label = QLabel()
        unit_label.setStyleSheet("color: gray;")
        unit_label.setMinimumWidth(50)
        unit_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        unit_label.setVisible(False)
        combo.currentTextChanged.connect(
            lambda text, label=unit_label: self.update_unit_label_for_row(text, label)
        )

        combo_wrapper = QWidget()
        combo_layout = QHBoxLayout(combo_wrapper)
        combo_layout.setContentsMargins(0, 0, 0, 0)
        combo_layout.addWidget(combo)
        combo_layout.addWidget(unit_label)
        combo_layout.addStretch()

        log_cb = QCheckBox()
        norm_cb = QCheckBox()
        plot_cb = QCheckBox()
        plot_cb.stateChanged.connect(self._check_apply_enabled)

        layout.addWidget(combo_wrapper, row, 0)
        layout.addWidget(log_cb, row, 1, alignment=Qt.AlignCenter)
        layout.addWidget(norm_cb, row, 2, alignment=Qt.AlignCenter)
        layout.addWidget(plot_cb, row, 3, alignment=Qt.AlignCenter)

        self.default_row_widgets.append(
            {
                "combo": combo,
                "unit_label": unit_label,
                "log_cb": log_cb,
                "norm_cb": norm_cb,
                "plot_cb": plot_cb,
            }
        )

    def _check_apply_enabled(self):
        if not hasattr(self, "plot_warning_label"):
            return
        plot_checked = 0

        # === Check default rows ===
        for widget in self.default_row_widgets:
            if widget["combo"].currentText() == "Select Column":
                self.plot_warning_label.setVisible(False)
                self.apply_button.setEnabled(False)
                return
            if widget["plot_cb"].isChecked():
                plot_checked += 1

        # === Check dynamic rows ===
        for widget in self.column_item_widgets.values():
            if widget["combo"].currentText() == "Select Column":
                self.plot_warning_label.setText("All rows must have a selected column.")
                self.plot_warning_label.setVisible(True)
                self.apply_button.setEnabled(False)
                return  # <-- move this inside the if block
            if widget["plot_cb"].isChecked():
                plot_checked += 1

        # === Show warnings based on count ===
        if plot_checked < 2:
            self.plot_warning_label.setText(
                "You must select at least 2 columns to plot."
            )
            self.plot_warning_label.setVisible(True)
            self.apply_button.setEnabled(False)
        elif plot_checked > 3:
            self.plot_warning_label.setText(
                "You can only plot 2 or 3 columns at a time."
            )
            self.plot_warning_label.setVisible(True)
            self.apply_button.setEnabled(False)
        else:
            self.plot_warning_label.setVisible(False)
            self.apply_button.setEnabled(True)

    def _refresh_add_button_position(self):
        self.scroll_layout.removeWidget(self.add_row_container)
        self.add_row_index = (
            max([w["row"] for w in self.column_item_widgets.values()] + [1]) + 1
        )
        self._place_add_row_at_bottom()

    def get_current_view(self):
        return "ClusteringSettingsDialog"

    def get_walkthrough_steps(self):
        return [
            (
                "Choose Method",
                "Start by selecting a clustering method from the dropdown list.",
                "ClusteringSettingsDialog",
                lambda: [self.method_combo],
            ),
            (
                "Apply Filter",
                "Optionally, you can define a filter using SQL syntax to subset your data.",
                "ClusteringSettingsDialog",
                lambda: [self.filter_text],
            ),
            (
                "Add Columns",
                "Click 'Add Column' to include additional variables in your analysis.",
                "ClusteringSettingsDialog",
                lambda: [self.add_button],
            ),
            (
                "Select Plot Columns",
                "Choose at least 2 and at most 3 columns to plot. Use the checkboxes beside each column.",
                "ClusteringSettingsDialog",
                lambda: [
                    w["plot_cb"]
                    for w in self.default_row_widgets
                    + list(self.column_item_widgets.values())
                    if "plot_cb" in w
                ],
            ),
            (
                "Apply Settings",
                "Once ready, click 'Apply' to save your clustering configuration.",
                "ClusteringSettingsDialog",
                lambda: [self.apply_button],
            ),
        ]


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication, QDialog

    app = QApplication(sys.argv)

    # === Available options ===
    available_columns = ["duration", "current", "voltage", "charge"]
    available_methods = ["KMeans", "DBSCAN", "Agglomerative"]

    # === Define method parameters (name + type)
    method_parameters = {
        "KMeans": [
            {"name": "Clusters", "type": "int"},
            {"name": "Init Method", "type": "str"},
        ],
        "DBSCAN": [
            {"name": "Eps", "type": "float"},
            {"name": "Min Samples", "type": "int"},
        ],
        "Agglomerative": [{"name": "Linkage", "type": "str"}],
    }

    # === Units for columns
    column_units = {"duration": "ms", "current": "pA", "voltage": "mV", "charge": "fC"}

    # === Preselected config with parameter values
    preselected_config = {
        "method": "KMeans",
        "filter": "duration > 0",
        "method_params": {
            "KMeans_Clusters_input": "5",
            "KMeans_Init_Method_input": "k-means++",
        },
        "columns": [
            {"column": "duration", "log": True, "norm": False, "plot": True},
            {"column": "current", "log": False, "norm": True, "plot": True},
        ],
    }

    window = ClusteringSettingsDialog(
        dynamic_title="Clustering Settings Test",
        available_columns=available_columns,
        available_methods=available_methods,
        column_units=column_units,
        preselected_config=preselected_config,
        method_parameters=method_parameters,
    )

    window.exec()

    if window.result() == QDialog.Accepted:
        result = window.get_result()
        print("Dialog result:")
        print(result)

    sys.exit(0)
