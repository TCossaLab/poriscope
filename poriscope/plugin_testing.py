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

from app.models.reader import FileLoadModel
from PySide6.QtWidgets import QApplication

from poriscope.controllers.file_load_controller import FileLoadController
from poriscope.views.file_load_view import FileLoadView


class App(QApplication):
    def __init__(self, sys_argv):
        super(App, self).__init__(sys_argv)
        # Set up logging configuration
        logging.basicConfig(level=logging.INFO)

        # Create model and view
        self.model = FileLoadModel()
        self.view = FileLoadView()

        # Create controller and connect to the view
        self.controller = FileLoadController(self.model, self.view)

        # Show the main view
        self.view.show()

        # Load plugins for FileLoadModel
        plugins_path = os.path.join(os.path.dirname(__file__), "plugins", "datareaders")
        self.model.load_plugins(plugins_path)
        logging.info(f"Loaded plugins from: {plugins_path}")


if __name__ == "__main__":
    app = App(sys.argv)
    sys.exit(app.exec())
