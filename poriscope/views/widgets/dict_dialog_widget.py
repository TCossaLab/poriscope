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

import logging
import os
import re
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from poriscope.utils.LogDecorator import log
from poriscope.views.widgets.validators.numeric_validation import NumericLineEdit


class DictDialog(QDialog):
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        params,
        name,
        title="",
        data_server="",
        editable=True,
        show_delete=False,
        editable_source_plugins=True,
        source_plugins=[],
        parent=None,
    ):
        """
        :param params: Plugin parameters to edit.
        :param name: Name of the plugin.
        :param title: Dialog title.
        :param data_server: Base path for folder/file selection.
        :param editable: If True, allow editing of the plugin name.
        :param show_delete: If True, show the Delete button (used for edit settings).
        :param parent: Parent widget.
        """
        super().__init__(parent)
        self.title = title
        self.setWindowTitle(title)
        self.data_server = data_server
        self.editable = editable
        self.params = params
        self.show_delete = show_delete
        self.result = None
        self.source_plugins = source_plugins
        self.editable_source_plugins = editable_source_plugins
        self.init_ui(params, name)

    @log(logger=logger)
    def init_ui(self, params, name):
        layout = QGridLayout(self)
        labels = {}
        self.entrywidgets = {}
        self.unitwidgets = {}
        self.ok_button = QPushButton("OK", self)
        self.ok_button.setEnabled(False)  # Initially disable the OK button
        cancel_button = QPushButton("Cancel", self)

        name_label = QLabel("Name")
        self.name_entry = QLineEdit()
        self.name_entry.setText(name)
        self.name_entry.setEnabled(self.editable)
        layout.addWidget(name_label, 0, 0)
        layout.addWidget(self.name_entry, 0, 1)

        i = 1
        for key, val in params.items():
            labels[key] = QLabel(key)

            if key == "Input File":
                starting_file_path = val.get("Value")
                file_types = val.get("Options")
                if not starting_file_path:
                    starting_file_path = ""
                if file_types is not None:
                    filters = []
                    for ext in file_types:
                        filters.append(f"Files (*{ext})")
                        filter_str = ";;".join(filters)
                else:
                    filter_str = "All Files (*)"
                self.entrywidgets[key] = QPushButton("Select Input File")
                self.entrywidgets[key].clicked.connect(
                    lambda: self.get_input_file(
                        starting_file_path=starting_file_path, file_types=filter_str
                    )
                )

            elif key == "Output File":
                starting_file_path = val.get("Value")
                file_types = val.get("Options")
                if not starting_file_path:
                    starting_file_path = ""
                if file_types is not None:
                    filters = []
                    for ext in file_types:
                        filters.append(f"Files (*{ext})")
                        filter_str = ";;".join(filters)
                else:
                    filter_str = "All Files (*)"

                self.entrywidgets[key] = QPushButton("Select Output File")
                self.entrywidgets[key].clicked.connect(
                    lambda: self.get_output_file(
                        starting_file_path=starting_file_path, file_types=filter_str
                    )
                )
            elif key == "Folder":
                starting_path = val.get("Value")
                if not starting_path:
                    starting_path = self.data_server
                self.entrywidgets[key] = QPushButton("Select Folder")
                self.entrywidgets[key].clicked.connect(
                    lambda: self.get_folder(starting_path=starting_path)
                )
            else:
                val_type = val.get("Type")
                if val.get("Options") is not None and val_type is not bool:
                    self.entrywidgets[key] = QComboBox(self)
                    self.entrywidgets[key].addItems(
                        [str(v) for v in val.get("Options")]
                    )
                    if val.get("Value") is not None:
                        self.entrywidgets[key].setCurrentText(str(val.get("Value")))
                    if (
                        key in self.source_plugins
                        and self.editable_source_plugins is False
                    ):
                        self.entrywidgets[key].setEnabled(False)
                elif val_type in (int, float):
                    self.entrywidgets[key] = NumericLineEdit()
                    self.entrywidgets[key].setRange(
                        val.get("Min"), val.get("Max"), val.get("Type")
                    )
                    self.entrywidgets[key].textChanged.connect(self.check_validity)
                    if val.get("Value") is not None:
                        self.entrywidgets[key].setText(str(val.get("Value")))
                elif val.get("Type") is str:
                    self.entrywidgets[key] = QLineEdit()
                    if val.get("Value") is not None:
                        self.entrywidgets[key].setText(str(val.get("Value")))
                elif val.get("Type") is bool:
                    self.entrywidgets[key] = QCheckBox()
                    self.entrywidgets[key].setChecked(val.get("Value"))
                else:
                    print(key, val)
                    raise ValueError(
                        f"Unsupported value type for plugin settings: {val.get('Type')}"
                    )

            if key not in ["Input File", "Output File", "Folder"]:
                self.unitwidgets[key] = QLabel(val.get("Units"))
            else:
                self.unitwidgets[key] = QCheckBox()
                self.unitwidgets[key].setChecked(False)
                self.unitwidgets[key].setEnabled(False)

            layout.addWidget(labels[key], i, 0)
            layout.addWidget(self.entrywidgets[key], i, 1)
            layout.addWidget(self.unitwidgets[key], i, 2)
            i += 1

        # OK and Cancel buttons

        layout.addWidget(self.ok_button, i, 0)
        layout.addWidget(cancel_button, i, 1)

        # Add Delete button conditionally
        if self.show_delete:
            self.delete_button = QPushButton("Delete", self)
            layout.addWidget(self.delete_button, i, 2)
            self.delete_button.clicked.connect(self.on_delete)

        self.ok_button.clicked.connect(self.on_ok)
        cancel_button.clicked.connect(self.on_cancel)

        QTimer.singleShot(0, self.check_validity)  # Ensure initial validity check
        # we cannot call this directly since UI elements are created outside of the main event loop
        # and this makes sure that the check only happens after they are fully initialized

    @log(logger=logger)
    def get_input_file(
        self,
        starting_file_path: Optional[str] = None,
        file_types: str = "All Files (*)",
    ):
        """
        Get the name of the file to be opened as the basis for a raw data set.

        :param starting_file_path: The starting file path, defaults to None.
        :type starting_file_path: Optional[str]
        :param file_types: The types of files to filter, defaults to "All Files (*)".
        :type file_types: str
        :return: The selected file path.
        :rtype: str
        :raises Exception: If there is an error determining the file path location.
        """
        loc = ""
        if starting_file_path is not None:
            try:
                loc = os.path.dirname(starting_file_path)
            except:
                raise
        input_file, _ = QFileDialog.getOpenFileName(
            self, "Select File", loc, file_types
        )
        if input_file:
            if not os.path.splitext(input_file)[1]:
                self.logger.info(f"Extension not provided, appending: {input_file}")
                match = re.search(r"\(\*\.([a-zA-Z0-9]+)\)", file_types)
                if match:
                    file_extension = match.group(1)
                    input_file += file_extension
            self.params["Input File"]["Value"] = input_file
            self.unitwidgets["Input File"].setChecked(True)
            self.check_validity()

    @log(logger=logger)
    def get_output_file(
        self,
        starting_file_path: Optional[str] = None,
        file_types: str = "All Files (*)",
    ):
        """
        Get the name of the file to save to.

        :param starting_file_path: The starting file path, defaults to None.
        :type starting_file_path: Optional[str]
        :param file_types: The types of files to filter, defaults to "All Files (*)".
        :type file_types: str
        :return: The selected file path for saving.
        :rtype: str
        :raises Exception: If there is an error determining the file path location.
        """
        loc = ""
        if starting_file_path is not None:
            try:
                loc = os.path.dirname(starting_file_path)
            except:
                raise
        options = QFileDialog.Options()
        options |= QFileDialog.DontConfirmOverwrite
        output_file, _ = QFileDialog.getSaveFileName(
            self, "Select File", loc, file_types, options=options
        )
        if output_file:
            self.params["Output File"]["Value"] = output_file
            self.unitwidgets["Output File"].setChecked(True)
            self.check_validity()

    @log(logger=logger)
    def get_folder(self, starting_path: Optional[str] = None):
        """
        Get the name of the output folder to save to

        :param starting_file_path: The starting file path, defaults to None.
        :type starting_file_path: Optional[str]

        :return: The selected file path for saving.
        :rtype: str
        :raises Exception: If there is an error determining the file path location.
        """
        loc = ""
        if starting_path:
            loc = starting_path
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.Directory)
        folder = dialog.getExistingDirectory(
            None, "Select or Create Experiment Folder", loc
        )
        if folder:
            self.params["Folder"]["Value"] = folder
            self.unitwidgets["Folder"].setChecked(True)
            self.check_validity()

    def check_validity(self):
        all_valid = True
        for key, widget in self.entrywidgets.items():
            if isinstance(widget, NumericLineEdit):
                if not widget.isValid():
                    all_valid = False
                    break
        if self.name_entry.text() == "":
            all_valid = False
        if "Input File" in self.entrywidgets.keys():
            if not self.unitwidgets["Input File"].isChecked():
                all_valid = False
        if "Output File" in self.entrywidgets.keys():
            if not self.unitwidgets["Output File"].isChecked():
                all_valid = False
        if "Folder" in self.entrywidgets.keys():
            if not self.unitwidgets["Folder"].isChecked():
                all_valid = False
        self.ok_button.setEnabled(all_valid)

    @log(logger=logger)
    def on_ok(self):
        for key, val in self.params.items():
            if key not in ["Input File", "Output File", "Folder"]:
                try:
                    self.params[key]["Value"] = self.params[key]["Type"](
                        self.entrywidgets[key].isChecked()
                    )
                except AttributeError:
                    try:
                        self.params[key]["Value"] = self.params[key]["Type"](
                            self.entrywidgets[key].currentText()
                        )  # files and folders are already saved on click events
                    except AttributeError:
                        self.params[key]["Value"] = self.params[key]["Type"](
                            self.entrywidgets[key].text()
                        )

        self.result = (self.params, self.name_entry.text())
        self.accept()

    @log(logger=logger)
    def on_cancel(self):
        self.result = (None, None)
        self.reject()

    @log(logger=logger)
    def on_delete(self):
        """Handle Delete button click."""
        self.result = "delete"  # Mark delete request
        self.reject()  # Close dialog

    @log(logger=logger)
    def get_result(self):
        return self.result
