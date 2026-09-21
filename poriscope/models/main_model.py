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
from typing import (
    Any,
    Dict,
    FrozenSet,
    Iterator,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Union,
)

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
}


class MainModel(QObject):
    """
    App-shell model: owns app configuration (loaded from/saved to config.json), discovers and holds every available plugin class under poriscope/plugins/ and the user plugin folder, and persists/restores session and tab-action history.
    """

    add_text_to_display = Signal(str, str)
    logger = logging.getLogger(__name__)

    #: The plugin families the app recognises, and the base class that identifies
    #: each. A file is a plugin when it subclasses one of these. A class attribute
    #: rather than rebuilt per call, since `refresh_available_plugins` makes
    #: discovery a repeated operation and the mapping never varies.
    ALLOWED_BASE_CLASSES: Dict[str, type] = {
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

    #: Settings keys whose value is a real type rather than data. Session JSON
    #: cannot hold a type, so it is written as its name and restored from that -
    #: but only here. Matching on the string alone is what turned a setting whose
    #: value happened to read "float" into `<class 'float'>`.
    _TYPE_VALUED_KEYS: FrozenSet[str] = frozenset({"Type"})

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
        Find every plugin the app can offer, keyed by the family it belongs to.

        Walks the shipped plugin tree and then the user's plugin folder, importing
        each file to see what it subclasses.

        Plugin names are unique across the whole app rather than per family, so the
        duplicate check here is keyed by name alone. Built-ins are walked first, so
        a user file of the same name is the one rejected - without that, it
        silently replaced the shipped plugin and there was no way to tell which had
        run.

        :return: The plugin classes keyed by family then name, and the same names
            as a plain list per family.
        :rtype: Tuple[Dict[str, Dict[str, type]], Dict[str, List[str]]]
        """
        available_plugin_classes: Dict[str, Dict[str, type]] = {
            k: {} for k in self.ALLOWED_BASE_CLASSES
        }
        available_plugins_list: Dict[str, List[str]] = {
            k: [] for k in self.ALLOWED_BASE_CLASSES
        }
        seen_plugin_names: Set[str] = set()

        for plugin_folder, plugin_name in self._plugin_files():
            found = self._classify_plugin_file(plugin_folder, plugin_name)
            if found is None:
                continue
            metaclass, subclass, plugin_class = found

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

    def _plugin_files(self) -> Iterator[Tuple[Path, str]]:
        """
        Yield every candidate plugin file, the shipped ones before the user's.

        The order is load-bearing rather than incidental: the caller rejects the
        *second* file of any given name, so walking the shipped tree first is what
        decides that a user file loses a name collision.

        :yield: The containing folder and file name of each file worth importing.
        :ytype: Tuple[Path, str]
        """
        for base_path in (
            self.plugin_path,
            Path(self.get_app_config("User Plugin Folder")),
        ):
            if not Path(base_path).is_dir():
                self.logger.warning(
                    f"Skipping plugin directory {base_path}: not a valid directory"
                )
                continue

            for root_dir, _, files in os.walk(base_path):
                for plugin_name in self._python_files(root_dir, files):
                    yield Path(root_dir), plugin_name

    def _python_files(self, root_dir: str, files: List[str]) -> List[str]:
        """
        Pick the importable files out of one directory's listing.

        The guard is inherited rather than newly added. Filtering a list of names
        that `os.walk` has already produced should not be able to fail, but this
        walks user-supplied directories and the cost of keeping it is one branch in
        a small method, so it stays.

        :param root_dir: The directory being listed, named only in the warning.
        :type root_dir: str
        :param files: The file names `os.walk` gave for that directory.
        :type files: List[str]
        :return: The names worth importing, empty if the listing could not be read.
        :rtype: List[str]
        """
        try:
            return [f for f in files if f.endswith(".py") and f != "__init__.py"]
        except Exception as e:
            self.logger.warning(f"Error reading files in {root_dir}: {e}")
            return []

    def _classify_plugin_file(
        self, plugin_folder: Path, plugin_name: str
    ) -> Optional[Tuple[str, str, type]]:
        """
        Import one file and work out which plugin family, if any, it belongs to.

        :param plugin_folder: The directory holding the file.
        :type plugin_folder: Path
        :param plugin_name: The file's name, including its `.py`.
        :type plugin_name: str
        :return: The family, the plugin's name and its class, or None if the file
            is not a plugin or could not be imported.
        :rtype: Optional[Tuple[str, str, type]]
        """
        subclass = plugin_name[:-3]
        plugin_class = self._load_plugin_class(subclass, plugin_folder)

        # Covers both a failed import, which gives None, and a file that defines
        # something other than a class under the name we looked for.
        if not isinstance(plugin_class, type):
            return None

        metaclass = self._metaclass_for(plugin_class)
        if metaclass is None:
            return None
        return metaclass, subclass, plugin_class

    def _load_plugin_class(self, subclass: str, plugin_folder: Path) -> Optional[type]:
        """
        Import one candidate file, giving back None rather than raising.

        Discovery executes every file it walks, including the user's, so anything
        at all can come out of this - and one bad file must not stop the rest of
        the plugins loading.

        :param subclass: The file's name without its extension, which is also the
            class name looked for inside it.
        :type subclass: str
        :param plugin_folder: The directory holding the file.
        :type plugin_folder: Path
        :return: The class, or None if the file could not be imported.
        :rtype: Optional[type]
        """
        try:
            return self.load_plugin(
                subclass,
                plugin_folder,
                tuple(self.ALLOWED_BASE_CLASSES.values()),
            )
        except Exception as e:
            self.logger.warning(f"Failed to load plugin {subclass}: {e}")
            return None

    def _metaclass_for(self, plugin_class: type) -> Optional[str]:
        """
        Name the plugin family a class belongs to.

        First match wins. The eleven families are disjoint in practice, so the
        order of `ALLOWED_BASE_CLASSES` does not decide anything today.

        :param plugin_class: The class to classify.
        :type plugin_class: type
        :return: The family's name, or None if it subclasses none of them.
        :rtype: Optional[str]
        """
        for name, base in self.ALLOWED_BASE_CLASSES.items():
            if issubclass(plugin_class, base):
                return name
        return None

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
        """
        Replace every type in a settings tree with its name, so it can be written as JSON.

        A plugin setting carries a real type under `Type` - `float`, `str` and so
        on - and JSON cannot hold one, so it is written as its name and turned
        back by `replace_class_names_with_classes` on load.

        This converts a type under *any* key, not only the expected ones, so that
        no save can fail on a value `json.dump` cannot serialise. It warns about
        the unexpected ones, because the load side will not convert those back:
        the asymmetry is deliberate, and the warning is what stops it being
        silent.

        Only dict values are walked. A list nested in a dict is not visited - the
        branch that once claimed to do so was unreachable from every caller, and
        nothing needs it: `Options` holds plugin names, not types.

        :param d: The settings tree, edited in place.
        :type d: Any
        """
        if not isinstance(d, dict):
            return

        for key, value in d.items():
            if isinstance(value, dict):
                self.replace_classes_with_class_names(value)
            elif isinstance(value, type):
                if key not in self._TYPE_VALUED_KEYS:
                    self.logger.warning(
                        f"Saving the type {value.__name__} under the key '{key}', "
                        f"which is not restored as a type on load - it will come "
                        f"back as the string '{value.__name__}'."
                    )
                d[key] = value.__name__

    @log(logger=logger)
    def replace_class_names_with_classes(
        self,
        d: Any,
        class_dict: Mapping[str, Any] = _JSON_CLASS_NAMES,
    ) -> None:
        """
        Turn the type names written into session JSON back into real types.

        **Only under the keys that actually hold a type.** Matching on the string
        alone converted any setting whose *value* happened to read `"float"` into
        `<class 'float'>`, so a plugin configured with `Event Type: "float"` came
        back corrupted. The key is what distinguishes a serialised type from a
        string that looks like one, because the save side only ever writes a type
        name in place of a type.

        A name the map does not know is left exactly as written.

        Only dict values are walked, matching the save side.

        :param d: The settings tree, edited in place.
        :type d: Any
        :param class_dict: The names to restore, and the types to restore them to.
        :type class_dict: Mapping[str, Any]
        """
        if not isinstance(d, dict):
            return

        for key, value in d.items():
            if isinstance(value, dict):
                self.replace_class_names_with_classes(value, class_dict)
            elif key in self._TYPE_VALUED_KEYS and isinstance(value, str):
                d[key] = class_dict.get(value, value)

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
