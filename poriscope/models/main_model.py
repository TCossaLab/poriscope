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

import copy
import importlib.util
import inspect
import json
import logging
import os
from collections import OrderedDict
from pathlib import Path

from platformdirs import user_data_dir
from PySide6.QtCore import QObject, Signal, Slot

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaDatabaseLoader import MetaDatabaseLoader
from poriscope.utils.MetaDatabaseWriter import MetaDatabaseWriter
from poriscope.utils.MetaEventFinder import MetaEventFinder
from poriscope.utils.MetaEventFitter import MetaEventFitter
from poriscope.utils.MetaEventLoader import MetaEventLoader
from poriscope.utils.MetaFilter import MetaFilter
from poriscope.utils.MetaModel import MetaModel
from poriscope.utils.MetaReader import MetaReader
from poriscope.utils.MetaView import MetaView
from poriscope.utils.MetaWriter import MetaWriter


class MainModel(QObject):
    configUpdated = Signal()
    errorOccurred = Signal(str)
    dataReadInstancesUpdated = Signal(dict)
    fileLoaded = Signal(object)
    logger = logging.getLogger(__name__)

    def __init__(self, app_config):
        """
        Initializes the MainModel with the given configuration file path.
        Args:
            config_path (str): The path to the configuration file.
        """
        super().__init__()
        self.app_config = app_config
        self.appdata_path = Path(user_data_dir(), "Poriscope")
        self.session_path = Path(self.appdata_path, "session")
        self.config_path = Path(self.appdata_path, "config")
        self.log_path = Path(self.appdata_path, "logs")
        self.plugin_path = Path(Path(__file__).resolve().parent, "..", "plugins")
        self.available_plugin_classes, self.available_plugins_list = (
            self.populate_available_plugins()
        )

    @log(logger=logger)
    def clear_cache(self):
        """
        Deletes log file and wait until it's confirmed deleted, with a busy-wait loop.

        :param filepath: Path to the file to be deleted.
        :param timeout: Maximum time (in seconds) to wait for file deletion.
        """
        log_file_path = Path(self.log_path, "app.log")

        # Find the file handler for the log file
        for handler in logging.getLogger().handlers:
            if (
                isinstance(handler, logging.FileHandler)
                and Path(handler.baseFilename) == log_file_path
            ):
                # Flush any buffered log data
                handler.flush()

                # Open the file in write mode and truncate its contents
                with open(handler.baseFilename, "w"):
                    pass

                # Optionally, log that the file was cleared
                self.logger.info("Log file reset by user")
                break

    @log(logger=logger)
    def load_plugin(self, plugin_key, folder, allowed_base_classes):
        """
        Dynamically loads a plugin, ensuring it is a subclass of a supported abstract class.

        Args:
            plugin_key (str): The key representing the plugin to load.

        Returns:
            plugin_class (type): The loaded plugin class, or None if loading fails.

        Note:
            This method uses dynamic module loading as described in the Python documentation:
            https://docs.python.org/3/library/importlib.html

            The simple-plugin-loader package was initially considered but was found to be unsuitable
            for on-demand loading as it loads all plugins upon execution:
            https://pypi.org/project/simple-plugin-loader/
        """
        try:
            plugin_file = f"{plugin_key}.py"
            plugin_full_path = Path(folder, plugin_file)

            if not plugin_full_path.exists():
                raise FileNotFoundError(f"No plugin file found: {plugin_full_path}")
            spec = importlib.util.spec_from_file_location(plugin_key, plugin_full_path)
            if spec is not None:
                module = importlib.util.module_from_spec(spec)
                if spec.loader is not None:
                    spec.loader.exec_module(module)
                else:
                    raise ValueError(
                        "Unable to resolve spec.loader while loadinng plugin"
                    )
            else:
                raise ValueError("Unable to resolve spec while loadinng plugin")

            # Get the plugin class from the module
            plugin_class = getattr(module, plugin_key, None)

            if not plugin_class:
                self.logger.debug(
                    f"No class named {plugin_key} found in {plugin_full_path}, invalid plugin ignored"
                )
                return None
            elif inspect.isclass(plugin_class) and not issubclass(
                plugin_class, allowed_base_classes
            ):
                self.logger.debug(
                    f"The class {plugin_key} does not inherit from an allowed base class, invalid plugin ignored"
                )
                return None
            else:
                return plugin_class
        except Exception as e:
            self.logger.error(f"Error loading plugin {plugin_key}: {e}", exc_info=True)
            self.errorOccurred.emit(f"Error loading plugin {plugin_key}: {e}")
            return None

    @log(logger=logger)
    def populate_available_plugins(self):
        """
        Get a dict of available plugin names, keyed by base class.
        Each entry in the dict is a list of plugin class names.
        Built at runtime by searching plugin directories.
        """
        allowed_base_classes = {
            "MetaFilter": MetaFilter,
            "MetaReader": MetaReader,
            "MetaWriter": MetaWriter,
            "MetaEventLoader": MetaEventLoader,
            "MetaEventFinder": MetaEventFinder,
            "MetaEventFitter": MetaEventFitter,
            "MetaDatabaseWriter": MetaDatabaseWriter,
            "MetaDatabaseLoader": MetaDatabaseLoader,
            "MetaController": MetaController,
            "MetaView": MetaView,
            "MetaModel": MetaModel,
        }

        available_plugin_classes = {k: {} for k in allowed_base_classes}
        available_plugins_list = {k: [] for k in allowed_base_classes}

        plugin_dirs_to_search = [
            self.plugin_path,
            Path(self.get_app_config("User Plugin Folder")),
        ]

        for base_path in plugin_dirs_to_search:
            try:
                walker = os.walk(base_path)
            except Exception as e:
                self.logger.warning(f"Skipping plugin directory {base_path}: {e}")
                continue

            for root_dir, _, files in walker:
                try:
                    files = [
                        f
                        for f in files
                        if f.endswith(".py") and f not in ("__init__.py", "__pycache__")
                    ]
                except Exception as e:
                    self.logger.warning(f"Error reading files in {root_dir}: {e}")
                    continue

                for plugin_name in files:
                    subclass = plugin_name[:-3]
                    plugin_folder = Path(root_dir)
                    try:
                        plugin_class = self.load_plugin(
                            subclass,
                            plugin_folder,
                            tuple(allowed_base_classes.values()),
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to load plugin {subclass}: {e}")
                        plugin_class = None

                    metaclass = None
                    for key, val in allowed_base_classes.items():
                        if (
                            plugin_class
                            and isinstance(plugin_class, type)
                            and issubclass(plugin_class, val)
                        ):
                            metaclass = key
                            break

                    if metaclass:
                        available_plugin_classes[metaclass][subclass] = plugin_class
                        available_plugins_list[metaclass].append(subclass)

        return available_plugin_classes, available_plugins_list

    @log(logger=logger)
    def get_available_plugins(self, metaclass=None):
        if metaclass:
            return self.available_plugins_list[metaclass]
        else:
            return self.available_plugins_list

    @log(logger=logger)
    def get_plugin_classes(self, metaclass=None):
        if metaclass:
            return self.available_plugin_classes[metaclass]
        else:
            return self.available_plugin_classes

    @log(logger=logger)
    def get_plugin(self, metaclass, subclass):
        try:
            return self.available_plugin_classes[metaclass][subclass]
        except KeyError:
            self.logger.error(f"unable to load class {metaclass} {subclass}")

    @log(logger=logger)
    def get_plugin_data(self, plugin_key):
        """
        Fetches plugin data from the local application data JSON file.

        Args:
            plugin_key (str): The key representing the plugin to retrieve data for.

        Returns:
            dict: Plugin data if available, otherwise returns an empty dictionary.
        """
        file_path = Path(user_data_dir(), "Poriscope", "session", "plugin_history.json")
        if not file_path.exists():
            self.logger.error(f"Plugin data file does not exist: {file_path}")
            return {}

        try:
            with open(file_path, "r") as file:
                data = json.load(file)
                plugin_data = data.get(plugin_key, {})
                self.replace_class_names_with_classes(plugin_data)
                return plugin_data
        except Exception as e:
            self.logger.error(f"Failed to load plugin data for {plugin_key}: {e}")
            return {}

    @log(logger=logger)
    def save_session(self, plugin_history, save_file=None):
        json_dump = copy.deepcopy(plugin_history)
        self.replace_classes_with_class_names(json_dump)
        if save_file is None:
            save_file = Path(self.session_path, "plugin_history.json")
        with open(save_file, "w") as jf:
            json.dump(json_dump, jf, indent=4)

    @log(logger=logger)
    def save_tab_actions(self, plugin_history, save_file=None):
        json_dump = copy.deepcopy(plugin_history)
        self.replace_classes_with_class_names(json_dump)
        if save_file is None:
            save_file = Path(self.session_path, "tab_action_history.json")
        with open(save_file, "w") as jf:
            json.dump(json_dump, jf, indent=4)

    @log(logger=logger)
    def load_session(self, file_name=None):
        if not file_name:
            file_name = Path(self.session_path, "plugin_history.json")
        try:
            with open(file_name, "r") as jf:
                plugin_history = json.load(jf, object_pairs_hook=OrderedDict)
        except Exception:
            self.logger.info(
                "Unable to load previous session. Session history will not be available, but you can continue normally."
            )
            return None
        else:
            self.replace_class_names_with_classes(plugin_history)
            return plugin_history

    @log(logger=logger)
    def replace_classes_with_class_names(self, d):
        if isinstance(d, dict):
            for key, value in d.items():
                if isinstance(value, dict):
                    self.replace_classes_with_class_names(value)
                elif isinstance(value, type):
                    d[key] = value.__name__
        elif isinstance(d, list):
            for i in range(len(d)):
                if isinstance(d[i], dict):
                    self.replace_classes_with_class_names(d[i])
                elif isinstance(d[i], type):
                    d[i] = d[i].__name__

    @log(logger=logger)
    def replace_class_names_with_classes(
        self,
        d,
        class_dict={"str": str, "int": int, "float": float, "bool": bool, "null": None},
    ):
        if isinstance(d, dict):
            for key, value in d.items():
                if isinstance(value, dict):
                    self.replace_class_names_with_classes(value, class_dict)
                elif isinstance(value, str):
                    # Check if the value is a class name in the provided class_dict
                    if value in class_dict:
                        d[key] = class_dict[value]
        elif isinstance(d, list):
            for i in range(len(d)):
                if isinstance(d[i], dict):
                    self.replace_class_names_with_classes(d[i], class_dict)
                elif isinstance(d[i], str):
                    # Check if the value is a class name in the provided class_dict
                    if d[i] in class_dict:
                        d[i] = class_dict[d[i]]

    @log(logger=logger)
    def get_app_config(self, key):
        return self.app_config.get(key)

    @log(logger=logger)
    def update_app_config(self, key, val):
        self.app_config[key] = val
        config_file_path = Path(self.config_path, "config.json")
        with open(config_file_path, "w") as f:
            json.dump(self.app_config, f, indent=4)

    @log(logger=logger)
    def get_data_server_location(self):
        return self.get_app_config("Parent Folder")

    @log(logger=logger)
    def get_user_plugin_location(self):
        return self.get_app_config("User Plugin Folder")

    @log(logger=logger)
    @Slot(int)
    def update_logging_level(self, level):
        logger = logging.getLogger()
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)
        self.update_app_config("Log Level", level)
