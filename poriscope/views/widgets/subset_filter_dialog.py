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

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from poriscope.plugins.analysistabs.utils.walkthrough_mixin import WalkthroughMixin


class SubsetFilterDialog(QDialog, WalkthroughMixin):
    def __init__(
        self,
        parent=None,
        name="",
        filter_text="",
        subset_filters=None,
        is_edit=False,
        comboBox=None,
    ):
        super().__init__(parent)
        self._init_walkthrough()

        self.setWindowTitle("Edit Filter" if is_edit else "Create Subset Filter")
        self.resize(400, 300)

        self.comboBox = comboBox
        self.subset_filters = subset_filters or {}
        self.original_name = name
        self.is_edit = is_edit

        layout = QVBoxLayout(self)

        self.name_input = QLineEdit(name)
        self.name_input.setPlaceholderText("Subset name")
        layout.addWidget(QLabel("Subset:"))
        layout.addWidget(self.name_input)

        self.filter_input = QTextEdit()
        self.filter_input.setPlainText(filter_text)
        layout.addWidget(QLabel("Filter:"))
        layout.addWidget(self.filter_input)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)

    def _on_accept(self):
        name = self.name_input.text().strip()
        filter_text = self.filter_input.toPlainText().strip()

        if not name:
            QMessageBox.warning(
                self, "Missing Name", "Please enter a name for the subset."
            )
            return

        if not self.is_edit and name in self.subset_filters:
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
        self.filter = filter_text
        self.accept()

    def get_walkthrough_steps(self):
        return [
            (
                "Enter Name",
                "Provide a name for the subset filter.",
                "SubsetFilterDialog",
                lambda: [self.name_input],
            ),
            (
                "Define Filter",
                "Write the filter condition here.",
                "SubsetFilterDialog",
                lambda: [self.filter_input],
            ),
            (
                "Confirm",
                "Click OK to save the subset filter.",
                "SubsetFilterDialog",
                lambda: [self.button_box.button(QDialogButtonBox.Ok)],
            ),
        ]
