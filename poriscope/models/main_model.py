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
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple, Union

from platformdirs import user_data_dir
from PySide6.QtCore import QObject, Signal, Slot

from poriscope.utils.app_config import default_app_config
from poriscope.utils.JsonDefaultSerializer import serialize_object
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
from poriscope.utils.QtHandler import QtHandler

#: Maps the class names written into session JSON back to real types.
_JSON_CLASS_NAMES: Mapping[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "null": None,
}


class MainModel(QObject):
    """
    App-shell model: owns app configuration (loaded from/saved to config.json), discovers and holds every available plugin class under poriscope/plugins/ and the user plugin folder, and persists/restores session and tab-action history.
    """

    add_text_to_display = Signal(str, str)
    logger = logging.getLogger(__name__)

    def __init__(self, app_config: Dict[str, Any]) -> None:
        """
        Initializes the MainModel with the given app configuration.

        :param app_config: The application's configuration settings.
        :type app_config: Dict[str, Any]
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
    def clear_cache(self) -> None:
        """
        Truncate the app's log file (flushing any buffered log data first).
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
    def load_plugin(
        self,
        plugin_key: str,
        folder: Union[str, Path],
        allowed_base_classes: Tuple[type, ...],
    ) -> Optional[type]:
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
            # Logged at ERROR on purpose: QtHandler raises that as a dialog, and on
            # the startup scan - which runs from MainModel's constructor, before
            # MainController exists to connect anything - it is the only signal the
            # user can get. The panel message below lands on the runtime re-scans
            # (changing the user plugin folder, resetting the session), where today
            # the dialog is likewise all there is.
            self.logger.error(f"Error loading plugin {plugin_key}: {e}", exc_info=True)
            self.add_text_to_display.emit(
                f"Error loading plugin {plugin_key}: {e}", self.__class__.__name__
            )
            return None

    @log(logger=logger)
    def populate_available_plugins(
        self,
    ) -> Tuple[Dict[str, Dict[str, type]], Dict[str, List[str]]]:
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

        available_plugin_classes: Dict[str, Dict[str, type]] = {
            k: {} for k in allowed_base_classes
        }
        available_plugins_list: Dict[str, List[str]] = {
            k: [] for k in allowed_base_classes
        }

        # plugin names are unique across the whole app, not per metaclass, so this is
        # keyed by name alone. Built-ins are walked before the user plugin folder, so
        # without this check a user file of the same name silently replaced the shipped
        # plugin and there was no way to tell which one had run.
        seen_plugin_names: Set[str] = set()

        plugin_dirs_to_search = [
            self.plugin_path,
            Path(self.get_app_config("User Plugin Folder")),
        ]

        for base_path in plugin_dirs_to_search:
            if not Path(base_path).is_dir():
                self.logger.warning(
                    f"Skipping plugin directory {base_path}: not a valid directory"
                )
                continue

            for root_dir, _, files in os.walk(base_path):
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

                    # plugin_class is necessarily non-None whenever metaclass was
                    # set above; the explicit check is what lets mypy see that.
                    if metaclass and plugin_class is not None:
                        if subclass in seen_plugin_names:
                            self.logger.error(
                                f"More than one plugin is named {subclass}. The copy at "
                                f"{Path(plugin_folder, plugin_name)} is ignored; rename it "
                                f"to load it."
                            )
                            continue
                        seen_plugin_names.add(subclass)
                        available_plugin_classes[metaclass][subclass] = plugin_class
                        available_plugins_list[metaclass].append(subclass)

        return available_plugin_classes, available_plugins_list

    @log(logger=logger)
    def refresh_available_plugins(self) -> None:
        """
        Re-scan the plugin directories and replace the cached results.

        The scan otherwise runs once, in the constructor, so a user who points
        the app at a different plugin folder sees no change until the next
        launch. Each plugin file is loaded fresh via
        ``importlib.util.spec_from_file_location``/``exec_module`` rather than
        through ``sys.modules``, so an edited file's new code is always picked
        up on the next scan - but that also means every scan hands back a new
        class object, never the one a previous scan produced. This does not
        break anything already instantiated: an instance keeps working
        through its own ``__class__`` reference regardless of what this cache
        holds, it just does not become an instance of the freshly-scanned
        class - the two are distinct objects until nothing references the
        older one any more. Files that have since been deleted simply are not
        walked, and so drop out.

        Callers are responsible for propagating the new lists - the controllers
        and the view each hold a copy taken at construction.
        """
        self.available_plugin_classes, self.available_plugins_list = (
            self.populate_available_plugins()
        )

    @log(logger=logger)
    def get_available_plugins(self) -> Dict[str, List[str]]:
        return self.available_plugins_list

    @log(logger=logger)
    def get_plugin_classes(self, metaclass: str) -> Dict[str, type]:
        return self.available_plugin_classes[metaclass]

    @log(logger=logger)
    def get_plugin(self, metaclass: str, subclass: str) -> Optional[type]:
        try:
            return self.available_plugin_classes[metaclass][subclass]
        except KeyError:
            self.logger.error(f"unable to load class {metaclass} {subclass}")
            return None

    @log(logger=logger)
    def get_plugin_data(self, plugin_key: str) -> Dict[str, Any]:
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
    def save_session(
        self,
        plugin_history: Dict[str, Any],
        save_file: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Write the plugin history to disk as JSON

        A write failure is logged rather than raised. Every caller is a Qt slot, and
        PySide6 does not tolerate an exception escaping a slot invoked from C++, so a
        read-only or otherwise unwritable destination would take the process down.
        ``except Exception`` rather than ``except OSError`` because ``json.dump`` also
        raises ``TypeError`` for a value it cannot serialize.

        The level depends on who asked for the save. An autosave - ``save_file`` is
        ``None``, which includes the app-shutdown path - logs at WARNING, which
        ``QtHandler`` does not raise a dialog for; a modal dialog during
        ``aboutToQuit`` would be its own bug. It also emits ``add_text_to_display``,
        so the status panel says autosaving has stopped: the failure is rare and
        non-blocking, but a user whose work is no longer being persisted needs to know
        they are operating unprotected. A save to a path the user chose logs at ERROR
        instead, and therefore does raise a dialog, so that a Save Session which did
        not happen is not mistaken for one that did.

        :param plugin_history: the session state to persist
        :type plugin_history: Dict[str, Any]
        :param save_file: path to write to, or None to use the default session file
        :type save_file: Optional[Union[str, Path]]
        """
        json_dump = copy.deepcopy(plugin_history)
        self.replace_classes_with_class_names(json_dump)
        user_specified = save_file is not None
        if save_file is None:
            save_file = Path(self.session_path, "plugin_history.json")
        try:
            with open(save_file, "w") as jf:
                json.dump(json_dump, jf, indent=4)
        except Exception as e:
            message = f"Unable to save session to {save_file}: {e}"
            if user_specified:
                self.logger.error(message)
            else:
                self.logger.warning(message)
                self.add_text_to_display.emit(
                    f"Session autosave failed: {e}. Your session is no longer being "
                    "saved automatically until this is resolved.",
                    self.__class__.__name__,
                )

    @log(logger=logger)
    def save_tab_actions(
        self,
        plugin_history: Dict[str, Any],
        save_file: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Write the tab action history to disk as JSON

        Failures are handled exactly as in :py:meth:`save_session`, and for the same
        reasons: logged rather than raised because the callers are Qt slots, at
        WARNING plus a status-panel message for an autosave, and at ERROR for a save
        to a path the user chose.

        :param plugin_history: the tab action history to persist
        :type plugin_history: Dict[str, Any]
        :param save_file: path to write to, or None to use the default session file
        :type save_file: Optional[Union[str, Path]]
        """
        json_dump = copy.deepcopy(plugin_history)
        self.replace_classes_with_class_names(json_dump)
        user_specified = save_file is not None
        if save_file is None:
            save_file = Path(self.session_path, "tab_action_history.json")
        try:
            with open(save_file, "w") as jf:
                json.dump(json_dump, jf, indent=4)
        except Exception as e:
            message = f"Unable to save tab action history to {save_file}: {e}"
            if user_specified:
                self.logger.error(message)
            else:
                self.logger.warning(message)
                self.add_text_to_display.emit(
                    f"Tab action autosave failed: {e}. Tab state is no longer being "
                    "saved automatically until this is resolved.",
                    self.__class__.__name__,
                )

    @log(logger=logger)
    def load_session(
        self, file_name: Optional[Union[str, Path]] = None
    ) -> Optional[Dict[str, Any]]:
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
    def replace_classes_with_class_names(self, d: Any) -> None:
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
        d: Any,
        class_dict: Mapping[str, Any] = _JSON_CLASS_NAMES,
    ) -> None:
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
    def reset_app_config(self) -> Dict[str, Any]:
        """
        Restore the three stored settings to their defaults and persist them.

        Only ``config/config.json`` is touched. Saved sessions, plugin history
        and log files are left alone.

        This writes the file and updates the in-memory config, but does not
        apply the values to anything already running: reverting the parent
        folder has to reach live data plugins, and reverting the log level has
        to reconfigure the logger. ``MainController.reset_app_config`` routes
        the returned values back through the same paths a manual edit uses, so
        those side effects are not duplicated here.

        :return: The defaults that were applied, so the caller can act on them.
        :rtype: Dict[str, Any]
        """
        defaults = default_app_config(Path(self.appdata_path, "user_plugins"))
        for key, value in defaults.items():
            self.update_app_config(key, value)
        self.logger.info("Application settings reset to defaults by user")
        return defaults

    @log(logger=logger)
    def get_app_config(self, key: str) -> Any:
        return self.app_config.get(key)

    @log(logger=logger)
    def update_app_config(self, key: str, val: Any) -> None:
        self.app_config[key] = val
        config_file_path = Path(self.config_path, "config.json")
        try:
            with open(config_file_path, "w") as f:
                json.dump(self.app_config, f, default=serialize_object, indent=4)
        except Exception as e:
            self.logger.warning(
                f"Unable to persist updated config file {config_file_path}: {e}"
            )

    @log(logger=logger)
    def get_data_server_location(self) -> str:
        return self.get_app_config("Parent Folder")

    @log(logger=logger)
    def get_user_plugin_location(self) -> str:
        return self.get_app_config("User Plugin Folder")

    @log(logger=logger)
    def get_logging_level(self) -> int:
        return self.get_app_config("Log Level")

    @log(logger=logger)
    @Slot(int)
    def update_logging_level(self, level: int) -> None:
        logger = logging.getLogger()
        logger.setLevel(level)
        for handler in logger.handlers:
            # QtHandler is excluded on purpose. It raises a modal dialog per record,
            # so its level is a decision about how much to interrupt the user, not
            # about how much to record - and it is the only handler whose level was
            # ever set here, which meant choosing a more verbose log level silently
            # turned every routine warning back into a dialog. It keeps its own
            # ERROR floor; see QtHandler's docstring.
            if isinstance(handler, QtHandler):
                continue
            handler.setLevel(level)
        self.update_app_config("Log Level", level)
