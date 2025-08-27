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
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from poriscope.utils.LogDecorator import log


class DropdownDialog(QDialog):
    logger = logging.getLogger(__name__)

    @log(logger=logger)
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.selected_item = None
        self.save_choice = False
        self.result = (self.selected_item, self.save_choice)
        self.setWindowTitle("Select Reader Plugin")
        self.init_ui(items)

    @log(logger=logger)
    def init_ui(self, items):
        layout = QVBoxLayout(self)

        # Instruction label
        instruction_label = QLabel("Choose a plugin to read the file:", self)
        layout.addWidget(instruction_label)

        # ComboBox for items
        self.combo_box = QComboBox(self)
        self.combo_box.addItems(items)
        layout.addWidget(self.combo_box)

        # CheckBox for saving choice
        self.checkbox = QCheckBox("Save choice", self)
        self.checkbox.setChecked(True)
        layout.addWidget(self.checkbox)

        # OK and Cancel buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK", self)
        cancel_button = QPushButton("Cancel", self)

        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        ok_button.clicked.connect(self.on_ok)
        cancel_button.clicked.connect(self.on_cancel)

    @log(logger=logger)
    def on_ok(self):
        self.selected_item = self.combo_box.currentText()
        self.save_choice = self.checkbox.isChecked()
        self.result = (self.selected_item, self.save_choice)
        self.accept()

    @log(logger=logger)
    def on_cancel(self):
        self.result = (None, False)
        self.reject()

    @log(logger=logger)
    def get_result(self):
        return self.result
