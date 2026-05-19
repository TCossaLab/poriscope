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

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
)


class BaseSubsetFilterDialog(QDialog):
    logger = logging.getLogger(__name__)

    def __init__(
        self, parent, title, existing_names, default_name="", default_filter=""
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.existing_names = existing_names
        self.name = None
        self.filter_text = None
        self.is_raw = False
        self.default_name = default_name
        self.default_filter = default_filter

        self._init_ui()

    def _init_ui(self):
        self.layout = QVBoxLayout(self)

        self.name_input = QLineEdit(self.default_name)
        self.layout.addWidget(QLabel("Subset:"))
        self.layout.addWidget(self.name_input)

        # Mode selection: Assisted builds the query automatically,
        # Raw SQL passes the filter text directly to the database
        mode_layout = QHBoxLayout()
        self.assisted_radio = QRadioButton("Assisted SQL")
        self.raw_radio = QRadioButton("Raw SQL")
        self.assisted_radio.setChecked(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.assisted_radio)
        self.mode_group.addButton(self.raw_radio)

        mode_layout.addWidget(self.assisted_radio)
        mode_layout.addWidget(self.raw_radio)
        self.layout.addLayout(mode_layout)

        # Pre-select mode based on existing suffix when editing
        if self.default_name.endswith("_raw"):
            self.raw_radio.setChecked(True)
        elif self.default_name.endswith("_assisted"):
            self.assisted_radio.setChecked(True)

        self.filter_input = QTextEdit()
        self.filter_input.setPlainText(self.default_filter)
        self.layout.addWidget(QLabel("Filter:"))
        self.layout.addWidget(self.filter_input)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.try_accept)
        self.button_box.rejected.connect(self.reject)

    def try_accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Missing Name", "Please enter a name for the subset."
            )
            return

        if name != self.default_name and name in self.existing_names:
            reply = QMessageBox.question(
                self,
                "Subset Already Exists",
                f"A subset named '{name}' already exists.\n\nWould you like to override it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self.name = name
        self.filter_text = self.filter_input.toPlainText().strip()
        self.is_raw = self.raw_radio.isChecked()
        self.accept()