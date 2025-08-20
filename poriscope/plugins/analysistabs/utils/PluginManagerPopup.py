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

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from poriscope.utils.LogDecorator import log


class PluginManager(QDialog):
    logger = logging.getLogger(__name__)
    save_requested = Signal(str, dict)  # Emit new name and updated settings
    delete_requested = Signal(str)  # Emit plugin name to delete

    def __init__(self, plugin_name, plugin_data=None, parent=None):
        super().__init__(parent)
        if not isinstance(plugin_name, str):
            raise ValueError("plugin_name must be a string")
        self.plugin_name = plugin_name
        self.plugin_data = plugin_data or {}
        self.setup_ui()

    @log(logger=logger)
    def setup_ui(self):
        self.setWindowTitle("Plugin Manager")
        self.setFixedSize(400, 300)

        main_layout = QVBoxLayout(self)
        self.label_name = QLabel("Name:")
        self.line_name = QLineEdit(self.plugin_name)
        main_layout.addWidget(self.label_name)
        main_layout.addWidget(self.line_name)

        self.save_button = QPushButton("Save", self)
        main_layout.addWidget(self.save_button)
        self.save_button.clicked.connect(self.emit_save)

        # self.delete_button = QPushButton("Delete", self)
        # main_layout.addWidget(self.delete_button)
        # self.delete_button.clicked.connect(self.emit_delete)

    @log(logger=logger)
    def emit_save(self):
        new_settings = {"name": self.line_name.text()}  # Collect settings as necessary
        self.logger.info("PluginManagerPopup: Saving sent")
        self.save_requested.emit(self.plugin_name, new_settings)

    # @log(logger=logger)
    # def emit_delete(self):
    #    self.delete_requested.emit(self.plugin_name)
    #    print(f"Delete sent")


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    plugin_data = {"name": "ExamplePlugin", "settings": {}}
    pm = PluginManager("ExamplePlugin", plugin_data)
    pm.show()
    sys.exit(app.exec_())
