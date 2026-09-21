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

import json
import logging
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List

from platformdirs import user_data_dir
from PySide6.QtWidgets import QApplication

from poriscope.utils.app_config import default_app_config
from poriscope.utils.JsonDefaultSerializer import serialize_object
from poriscope.utils.QtHandler import QtHandler


class App(QApplication):
    logger = logging.getLogger(__name__)

    def __init__(self, sys_argv: List[str]) -> None:
        super(App, self).__init__(sys_argv)
        self.create_appdata_folders()
        self.configure_logger(self.app_config["Log Level"])
        self.initialize_components()
        self.aboutToQuit.connect(self.main_controller.handle_about_to_quit)

        self.main_view.show()

    def create_appdata_folders(self) -> None:
        """
        Create the application's data folders and settle its configuration.

        The first thing `__init__` does, before the logger has a handler and
        before any window exists - so nothing here may raise. A folder that
        cannot be made or a configuration that cannot be written is warned about
        and worked around, because there is nothing yet that could report a
        failure to the user and no way to carry on without these paths.

        The five attributes it sets are read immediately afterwards by
        `configure_logger` and `initialize_components`.
        """
        local = Path(user_data_dir())
        self.app_folder = self._ensure_folder(Path(local, "Poriscope"))
        self.log_path = self._ensure_folder(Path(self.app_folder, "logs"))
        self.session_path = self._ensure_folder(Path(self.app_folder, "session"))
        self.user_plugin_path = self._ensure_folder(
            Path(self.app_folder, "user_plugins")
        )
        self.config_path = self._ensure_folder(Path(self.app_folder, "config"))
        config_file_path = Path(self.config_path, "config.json")

        # default_app_config() is the single definition of these defaults,
        # shared with the settings reset so the two cannot drift apart. Called
        # afresh at each of its three sites deliberately: the backfill and the
        # fallback below each need a dict that later edits to self.app_config
        # cannot have mutated.
        self.app_config: Dict[str, Any] = default_app_config(self.user_plugin_path)

        if not config_file_path.is_file():
            self._write_config(config_file_path, self.app_config, "write initial")

        if config_file_path.is_file():
            try:
                with open(config_file_path, "r") as f:
                    self.app_config = json.load(f)
                self._backfill_missing_config(config_file_path)
            except Exception as e:
                self.logger.warning(
                    f"Unable to load config file {config_file_path}, regenerating defaults: {e}"
                )
                self.app_config = default_app_config(self.user_plugin_path)
                self._write_config(
                    config_file_path, self.app_config, "persist regenerated default"
                )

        # Plugin discovery imports `user_plugins` as a package, so what has to be
        # importable is the directory containing it, not the folder itself.
        plugin_path = Path(self.user_plugin_path).resolve()
        parent_path = plugin_path.parent
        if str(parent_path) not in sys.path:
            sys.path.append(str(parent_path))

    def _ensure_folder(self, path: Path) -> Path:
        """
        Create a folder if it is not already there, and hand back its path.

        Returning the path is what lets each of the five be named and created on
        one line, since the caller keeps every one of them as an attribute.

        The existence check is kept rather than relying on `exist_ok`: the two
        differ when something that is *not* a directory already occupies the
        path, where `mkdir` raises and this does not. Startup is the wrong place
        to start raising.

        :param path: The folder to create.
        :type path: Path
        :return: The same path, now known to exist.
        :rtype: Path
        """
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_config(self, path: Path, config: Dict[str, Any], attempt: str) -> None:
        """
        Write the configuration out, warning rather than failing if it cannot be.

        Called at three points - the first write, a repaired config and a
        regenerated one - which differed only in the verb in their warning, so
        that verb is the parameter.

        None of the three may raise. This runs before the logger has a handler
        and before the window exists, so an unwritable config directory has to
        leave a working application whose settings simply will not persist.

        :param path: Where the configuration is written.
        :type path: Path
        :param config: The configuration to write.
        :type config: Dict[str, Any]
        :param attempt: What this write was for, read straight into the warning.
        :type attempt: str
        """
        try:
            with open(path, "w") as f:
                json.dump(config, f, default=serialize_object, indent=4)
        except Exception as e:
            self.logger.warning(f"Unable to {attempt} config file {path}: {e}")

    def _backfill_missing_config(self, config_file_path: Path) -> None:
        """
        Restore any default the stored configuration is missing, and persist it.

        Every default, not just the one added most recently: a config written by
        an older version, or hand-edited, can be missing any of them. `Log Level`
        is read by subscript in `__init__` before `configure_logger` has
        installed a handler, so a missing key there is a `KeyError` that nothing
        can record.

        Deliberately not defensive about the shape of what was loaded. A config
        file holding valid JSON that is not an object reaches here and fails on
        the assignment below, which the caller catches and treats as a corrupt
        config - the same outcome as unparseable text, and the right one.

        :param config_file_path: Where the configuration is stored.
        :type config_file_path: Path
        """
        defaults = default_app_config(self.user_plugin_path)
        missing = [key for key in defaults if key not in self.app_config]
        if not missing:
            return

        for key in missing:
            self.app_config[key] = defaults[key]
        self.logger.warning(
            f"Config file {config_file_path} was missing "
            f"{', '.join(missing)}; restored to default"
        )
        self._write_config(config_file_path, self.app_config, "persist updated")

    def configure_logger(self, loglevel: int) -> None:

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

        # display error messages in dialog box.
        #
        # Deliberately NOT given `formatter`: that format is right for a log line and
        # wrong for a dialog, which would otherwise show the user a timestamp, a thread
        # name and id, and a dotted module path before the message they need to read.
        # The console and file handlers above still record all of it.
        #
        # QtHandler defaults to ERROR rather than inheriting the root logger's level;
        # see its docstring for why, and note MainModel.update_logging_level skips it
        # when applying a new level to the root logger's handlers.
        qtHandler = QtHandler()
        qtHandler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(qtHandler)

        root_logger.debug(
            "----------------------Initializing Workspace----------------------"
        )


def main() -> None:
    logger = logging.getLogger(__name__)

    # Refuse to run if 32-bit Python
    bit_architecture = platform.architecture()[0]
    if bit_architecture == "32bit":
        logger.error("Poriscope requires a 64-bit version of Python.")
        sys.exit(1)

    app = App(sys.argv)

    if not sys.platform.startswith("darwin"):
        app.setStyle("Fusion")

    retval = app.exec()
    logger.debug(
        f"----------------------Exiting with exit status {retval}----------------------"
    )
    sys.exit(retval)


if __name__ == "__main__":
    main()
