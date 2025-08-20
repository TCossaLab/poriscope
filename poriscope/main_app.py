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
# Alejandra Carolina González González
#test
import json
import logging
import sys
from pathlib import Path

from platformdirs import user_data_dir
from PySide6.QtWidgets import QApplication

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.utils.JsonDefaultSerializer import serialize_object
from poriscope.utils.QtHandler import QtHandler
from poriscope.views.main_view import MainView


class App(QApplication):
    def __init__(self, sys_argv):
        super(App, self).__init__(sys_argv)
        self.create_appdata_folders()
        self.configure_logger(self.app_config["Log Level"])
        self.initialize_components()
        self.aboutToQuit.connect(self.main_controller.handle_about_to_quit)

        self.main_view.show()

    def create_appdata_folders(self):
        local = Path(user_data_dir())
        self.app_folder = Path(local, "Poriscope")
        if not self.app_folder.exists():
            self.app_folder.mkdir(parents=True, exist_ok=True)

        self.log_path = Path(self.app_folder, "logs")
        if not self.log_path.exists():
            self.log_path.mkdir(parents=True, exist_ok=True)

        self.session_path = Path(self.app_folder, "session")
        if not self.session_path.exists():
            self.session_path.mkdir(parents=True, exist_ok=True)

        self.user_plugin_path = Path(self.app_folder, "user_plugins")
        if not self.user_plugin_path.exists():
            self.user_plugin_path.mkdir(parents=True, exist_ok=True)

        self.config_path = Path(self.app_folder, "config")
        config_file_path = Path(self.config_path, "config.json")

        self.app_config = {
            "Parent Folder": Path(
                r"\\storage.rdc.uottawa.ca\1707_vtabardc"
            ),  # replace with one-time setup
            "User Plugin Folder": self.user_plugin_path,
            "Log Level": logging.WARNING,
        }

        if not self.config_path.exists():
            self.config_path.mkdir(parents=True, exist_ok=True)
        if not config_file_path.is_file():
            with open(config_file_path, "w") as f:
                json.dump(self.app_config, f, default=serialize_object, indent=4)

        try:
            if Path(self.config_path, "config.json").is_file():
                with open(Path(self.config_path, "config.json"), "r") as f:
                    self.app_config = json.load(f)
                    if "User Plugin Folder" not in self.app_config.keys():
                        self.app_config["User Plugin Folder"] = self.user_plugin_path
                        with open(config_file_path, "w") as f:
                            json.dump(
                                self.app_config, f, default=serialize_object, indent=4
                            )
            plugin_path = Path(self.user_plugin_path).resolve()
            parent_path = plugin_path.parent
            if str(parent_path) not in sys.path:
                sys.path.append(str(parent_path))

        except:
            raise

    def initialize_components(self):
        self.main_model = MainModel(self.app_config)
        self.main_view = MainView(self.main_model.get_available_plugins())
        self.main_controller = MainController(self.main_model, self.main_view)

    def configure_logger(self, loglevel):

        formatter = logging.Formatter(
            "%(asctime)s: %(levelname)s:\t%(threadName)s(%(thread)d):\t%(name)s:\t%(message)s"
        )

        root_logger = logging.getLogger()
        root_logger.setLevel(loglevel)

        # console logger
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(formatter)
        root_logger.addHandler(consoleHandler)

        # file logger - create logfile location if not yet available

        log_file_path = Path(self.log_path, "app.log")
        fileHandler = logging.FileHandler(log_file_path)
        fileHandler.setFormatter(formatter)
        root_logger.addHandler(fileHandler)

        # display error messages in dialog box
        qtHandler = QtHandler()
        qtHandler.setFormatter(formatter)
        root_logger.addHandler(qtHandler)

        root_logger.debug(
            "----------------------Initializing Workspace----------------------"
        )


def main():
    import sys

    app = App(sys.argv)

    if not sys.platform.startswith("darwin"):
        app.setStyle("Fusion")

    logger = logging.getLogger(__name__)
    retval = app.exec()
    logger.debug(
        f"----------------------Exiting with exit status {retval}----------------------"
    )
    sys.exit(retval)


if __name__ == "__main__":
    main()
