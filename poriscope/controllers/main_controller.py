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

import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from PySide6.QtCore import QObject, Slot

from poriscope.controllers.DataPluginController import DataPluginController
from poriscope.models.main_model import MainModel
from poriscope.utils.LogDecorator import log
from poriscope.views.main_view import MainView


class MainController(QObject):
    """
    App-shell controller: owns the DataPluginController and every instantiated analysis-tab controller, wires up their signals, and acts as the central relay for the app's signal-bus dispatch pattern (see handle_global_signal/handle_data_plugin_controller_signal), by which one tab or plugin can invoke a method on another plugin instance, or on the DataPluginController itself, without holding a direct reference to it. Also drives session/plugin-history persistence and restore.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, main_model: MainModel, main_view: MainView) -> None:
        super().__init__()
        self.main_model = main_model
        self.main_view = main_view
        self.config_path = Path(Path(__file__).resolve().parent, "..", "configs")

        # analysis tab managers
        self.analysis_tabs: Dict[str, Any] = (
            {}
        )  # a dict keyed by subclass of controllers for analysis tabs, with the instance of that tab

        # data plugin managers
        self.data_plugins: Dict[str, List[str]] = (
            {}
        )  # a dict keyed by metaclass with lists of keys for instances of subclasses of that metaclass

        # keyed by metaclass, same key set as available_plugin_classes
        self.data_plugin_controller = DataPluginController(
            {
                metaclass: self.main_model.get_plugin_classes(metaclass)
                for metaclass in self.main_model.get_available_plugins()
            },
            self.main_model.get_data_server_location(),
        )

        self.plugin_history: Dict[str, Any] = {}
        self.tab_action_history: Dict[str, Any] = {}

        previous_plugin_history = self.main_model.load_session(None)
        self.previous_plugin_history: Dict[str, Any] = (
            previous_plugin_history if previous_plugin_history is not None else {}
        )

        self.setup_connections()

    @log(logger=logger)
    def setup_connections(self) -> None:
        # data plugin signal connections

        self.main_view.instantiate_plugin.connect(
            self.data_plugin_controller.validate_and_instantiate_plugin
        )
        self.data_plugin_controller.get_settings_from_history.connect(
            self.get_settings_from_history
        )
        self.data_plugin_controller.update_available_plugins.connect(
            self.update_available_plugins
        )
        self.data_plugin_controller.update_plugin_history.connect(
            self.update_plugin_history
        )
        self.data_plugin_controller.add_text_to_display.connect(
            self.main_view.add_text_to_display
        )

        # main component connections
        self.main_view.instantiate_analysis_tab.connect(self.instantiate_analysis_tab)
        self.main_view.save_session.connect(self.save_session)
        self.main_view.load_session.connect(self.load_session)
        self.main_view.get_shared_data_server.connect(self.send_curent_data_server)
        self.main_view.get_user_plugin_location.connect(
            self.send_curent_user_plugin_location
        )
        self.main_view.get_shared_logging_level.connect(self.send_curent_logging_level)
        self.main_view.update_data_server_location.connect(
            self.update_data_server_location
        )
        self.main_view.update_user_plugin_location.connect(
            self.update_user_plugin_location
        )
        self.main_view.update_logging_level.connect(
            self.main_model.update_logging_level
        )
        self.main_view.clear_cache.connect(self.main_model.clear_cache)
        self.main_view.request_analysis_tabs.connect(self.send_analysis_tabs)

    @log(logger=logger)
    @Slot()
    def handle_about_to_quit(self) -> None:
        for key, val in self.analysis_tabs.items():
            if val:
                val.handle_kill_all_workers(key, exiting=True)
        self.data_plugin_controller.handle_exit()

    @log(logger=logger)
    @Slot()
    def send_curent_data_server(self) -> None:
        data_server = self.main_model.get_app_config("Parent Folder")
        self.main_view.set_data_server(data_server)

    @log(logger=logger)
    @Slot()
    def send_curent_user_plugin_location(self) -> None:
        data_server = self.main_model.get_app_config("User Plugin Folder")
        self.main_view.set_user_plugin_location(data_server)

    @log(logger=logger)
    @Slot()
    def send_curent_logging_level(self) -> None:
        level = self.main_model.get_logging_level()
        self.main_view.set_logging_level(level)

    @log(logger=logger)
    @Slot(str)
    def update_data_server_location(self, data_server: str) -> None:
        self.main_model.update_app_config("Parent Folder", data_server)
        self.data_plugin_controller.update_data_server_location(data_server)

    @log(logger=logger)
    @Slot(str)
    def update_user_plugin_location(self, user_plugin_loc: str) -> None:
        self.main_model.update_app_config("User Plugin Folder", user_plugin_loc)
        plugin_path = Path(user_plugin_loc).resolve()
        parent_path = plugin_path.parent
        if str(parent_path) not in sys.path:
            sys.path.append(str(parent_path))

    @log(logger=logger)
    @Slot(str, str, object)
    def get_plugin_instance(
        self, metaclass: str, key: str, callback: Callable[[object], None]
    ) -> None:
        callback(self.data_plugin_controller.get_plugin_instance(metaclass, key))

    @log(logger=logger)
    @Slot(str, str)
    def get_settings_from_history(self, metaclass: str, subclass: str) -> None:
        for val in self.plugin_history.values():
            if val.get("subclass") == subclass and val.get("metaclass") == metaclass:
                self.data_plugin_controller.set_settings(val.get("settings"))
                return
        for val in self.previous_plugin_history.values():
            if val.get("subclass") == subclass and val.get("metaclass") == metaclass:
                self.data_plugin_controller.set_settings(val.get("settings"))
                return
        self.data_plugin_controller.set_settings(None)

    @log(logger=logger)
    def _ensure_tuple(self, args: Any) -> tuple:
        if isinstance(args, tuple):
            return args
        else:
            if args is None:
                return ()
            else:
                return (args,)

    @log(logger=logger)
    @Slot(str, str, str, tuple, object, tuple)
    def handle_global_signal(
        self,
        metaclass: str,
        subclass_key: str,
        call_function: str,
        call_args: tuple,
        return_function: Optional[Callable],
        ret_args: tuple,
    ) -> None:
        """
        Resolve (metaclass, subclass_key) to a live data plugin instance and call call_function(*call_args) on it, so a tab or plugin can invoke a method on another plugin without holding a direct reference to it. If call_function raises TypeError, retries with a single None argument, on the assumption call_args didn't apply. If return_function is given, it is called with the result plus ret_args once call_function succeeds (again falling back to a single None argument on TypeError). Errors resolving the instance, function, or either call are logged and swallowed rather than raised.

        :param metaclass: The metaclass of the target plugin instance.
        :type metaclass: str
        :param subclass_key: The unique key of the target plugin instance.
        :type subclass_key: str
        :param call_function: Name of the method to call on the resolved instance.
        :type call_function: str
        :param call_args: Positional arguments to call_function.
        :type call_args: tuple
        :param return_function: Optional callable to invoke with the result of call_function.
        :type return_function: Optional[Callable]
        :param ret_args: Additional positional arguments appended after the result when calling return_function.
        :type ret_args: tuple
        """
        self.logger.debug(
            f"received signal: {metaclass}, {subclass_key}, {call_function}, {call_args}, {return_function}, {ret_args}"
        )
        instance = self.data_plugin_controller.get_plugin_instance(
            metaclass, subclass_key
        )

        if instance is None:
            self.logger.error(
                f"No plugin instance found for {metaclass}/{subclass_key}, unable to call {call_function}"
            )
        else:
            func = getattr(instance, call_function, None)
            if func is None:
                self.logger.error(
                    f"No member of {metaclass}/{subclass_key}.{call_function} found"
                )
                return
            elif not callable(func):
                self.logger.error(
                    f"{metaclass}/{subclass_key}.{call_function} is not callable"
                )
                return
            else:
                try:
                    call_args = self._ensure_tuple(call_args)
                    try:
                        retval = self._ensure_tuple(func(*call_args))
                    except TypeError:
                        retval = self._ensure_tuple(func(None))
                    except Exception as e:
                        self.logger.exception(
                            f"Unable to resolve function {metaclass}/{subclass_key}.{call_function} with arguments {call_args}: {repr(e)}"
                        )
                        return
                    if return_function is not None:
                        try:
                            retval = retval + self._ensure_tuple(ret_args)
                            try:
                                return_function(*retval)
                            except TypeError:
                                return_function(None)
                        except Exception as e:
                            self.logger.exception(
                                f"Error executing return function with args {ret_args}: {repr(e)}"
                            )
                            return
                except Exception as e:
                    self.logger.exception(
                        f"Unexpected error handling global signal for {metaclass}/{subclass_key}.{call_function}: {repr(e)}"
                    )

    @log(logger=logger)
    @Slot(str, str, str, tuple, object, tuple)
    def handle_data_plugin_controller_signal(
        self,
        metaclass: str,
        subclass_key: str,
        call_function: str,
        call_args: tuple,
        return_function: Optional[Callable],
        ret_args: tuple,
    ) -> None:
        """
        Same dispatch mechanism as handle_global_signal, except call_function is looked up and called on the DataPluginController itself rather than on a resolved plugin instance (metaclass/subclass_key are accepted for signal-signature parity with handle_global_signal but are not used to resolve a target here). Used when a tab needs to invoke a DataPluginController method (e.g. to instantiate or edit a plugin) rather than a method on an existing plugin instance.

        :param metaclass: Not used to resolve a target here (only logged); present for signature parity with handle_global_signal.
        :type metaclass: str
        :param subclass_key: Not used to resolve a target here (only logged); present for signature parity with handle_global_signal.
        :type subclass_key: str
        :param call_function: Name of the method to call on the DataPluginController.
        :type call_function: str
        :param call_args: Positional arguments to call_function.
        :type call_args: tuple
        :param return_function: Optional callable to invoke with the result of call_function.
        :type return_function: Optional[Callable]
        :param ret_args: Additional positional arguments appended after the result when calling return_function.
        :type ret_args: tuple
        """
        self.logger.debug(
            f"received signal: {metaclass}, {subclass_key}, {call_function}, {call_args}, {return_function}, {ret_args}"
        )
        instance = (
            self.data_plugin_controller
        )  # this one goes to the data plugin controller directly, NOT to an actual plugin instance

        if instance is not None:
            func = getattr(instance, call_function, None)
            if func is None:
                self.logger.error(
                    f"No value {call_function} found in data plugin controller"
                )
                return
            elif not callable(func):
                self.logger.error(f"{call_function} is not callable")
                return
            else:
                try:
                    call_args = self._ensure_tuple(call_args)
                    self.logger.debug(f"calling with: {call_args}")
                    retval = self._ensure_tuple(func(*call_args))
                    self.logger.debug(f"{call_function} returned {retval}")
                    if return_function is not None:
                        try:
                            self.logger.debug(
                                f"Executing {return_function} with {retval}"
                            )
                            retval = retval + self._ensure_tuple(ret_args)
                            return_function(*retval)
                        except Exception as ex:
                            self.logger.error(f"Error executing return function: {ex}")
                except Exception as e:
                    self.logger.exception(
                        f"Unable to resolve function {metaclass}/{subclass_key}.{call_function} with arguments {call_args}: {repr(e)}"
                    )

    @log(logger=logger)
    @Slot(str, list)
    def update_available_plugins(
        self, metaclass: str, available_plugins: List[str]
    ) -> None:
        self.logger.debug(
            f"Available {metaclass} plugins updates to {available_plugins}"
        )
        self.data_plugins[metaclass] = available_plugins
        for val in self.analysis_tabs.values():
            if val:
                val.update_available_plugins(self.data_plugins)

    @log(logger=logger)
    @Slot(dict, str)
    def update_plugin_history(
        self, history: Optional[Dict[str, Any]], delete_key: Optional[str]
    ) -> None:
        if history and not delete_key:
            if history:
                self.plugin_history[history.pop("key")] = history
        elif not history and delete_key:
            self.plugin_history.pop(delete_key, None)
        elif history and delete_key:
            new_history = {}
            for key, val in self.plugin_history.items():
                if key == delete_key:
                    new_history[history.pop("key")] = history
                else:
                    new_history[key] = val
            self.plugin_history = new_history
        self.main_model.save_session(self.plugin_history)

    @Slot(str, str, str)
    def handle_plugin_state_changed(
        self, metaclass: str, plugin_key: str, reason: str
    ) -> None:
        for val in self.analysis_tabs.values():
            if val:
                val.view.notify_plugin_state_changed(metaclass, plugin_key, reason)

    @log(logger=logger)
    @Slot(str, object)
    def update_tab_action_history(self, key: str, history: Any) -> None:
        self.tab_action_history[key] = history
        self.main_model.save_tab_actions(self.tab_action_history)

    @log(logger=logger)
    @Slot(str)
    def instantiate_analysis_tab(self, subclass: str) -> None:
        """
        Instantiate a new analysis-tab controller of the given subclass and wire it into the app
        (add its page, connect its signals, register it in plugin history), or reuse the existing
        instance if a tab of that type has already been instantiated.

        Exceptions raised while instantiating the controller itself are caught and logged here.
        Exceptions raised afterward, while wiring up or registering the new tab, are not caught
        by this method and will propagate to the caller.

        :param subclass: The class name of the MetaController subclass to instantiate (e.g. "RawDataController").
        :type subclass: str
        """
        new_analysis_tab = None
        history = {}

        if subclass in self.analysis_tabs.keys():
            self.logger.info(
                f"Analysis tab of type {subclass} already exists, use that one"
            )
        else:
            try:
                # Instantiate the analysis tab
                new_analysis_tab = self.main_model.get_plugin_classes("MetaController")[
                    subclass
                ](self.main_model.get_available_plugins())
            except Exception as e:
                self.logger.error(f"Error instantiating analysis tab: {e}")
                return

        if new_analysis_tab is not None:
            history["key"] = subclass
            history["metaclass"] = "MetaController"
            history["subclass"] = subclass
            self.analysis_tabs[subclass] = new_analysis_tab

            self.main_view.add_page(
                new_analysis_tab.view.__class__.__name__,
                self.analysis_tabs[subclass].view,
            )

            # Connect other necessary signals and update plugins
            self.analysis_tabs[subclass].global_signal.connect(
                self.handle_global_signal
            )
            self.analysis_tabs[subclass].create_plugin.connect(
                self.data_plugin_controller.validate_and_instantiate_plugin
            )
            self.analysis_tabs[subclass].data_plugin_controller_signal.connect(
                self.handle_data_plugin_controller_signal
            )
            self.analysis_tabs[subclass].plugin_state_changed.connect(
                self.handle_plugin_state_changed
            )
            self.analysis_tabs[subclass].add_text_to_display.connect(
                self.main_view.add_text_to_display
            )
            self.analysis_tabs[subclass].update_tab_action_history.connect(
                self.update_tab_action_history
            )
            self.analysis_tabs[subclass].save_tab_action_history.connect(
                self.save_tab_action_history
            )
            self.analysis_tabs[subclass].update_available_plugins(self.data_plugins)
            self.logger.debug(f"New analysis tab of type {subclass} added")
            self.update_plugin_history(history, "")

    @log(logger=logger)
    @Slot(str)
    def save_session(self, save_file: Optional[Union[str, Path]] = None) -> None:
        self.main_model.save_session(self.plugin_history, save_file)

    @log(logger=logger)
    @Slot(object, str)
    def save_tab_action_history(
        self, history: Any, save_file: Optional[Union[str, Path]] = None
    ) -> None:
        self.main_model.save_tab_actions(history, save_file)

    @log(logger=logger)
    @Slot(str)
    def load_session(self, file_name: Optional[Union[str, Path]] = None) -> None:
        self.logger.debug(f"Loading session from file {file_name}")
        plugin_history = self.main_model.load_session(file_name)
        if plugin_history is not None:
            self.plugin_history = plugin_history
            self.main_model.save_session(self.plugin_history)
        else:
            self.logger.info(f"Unable to recover plugin history from {file_name}")
            return
        for key, plugin in list(self.plugin_history.items()):
            metaclass = plugin["metaclass"]
            subclass = plugin["subclass"]
            if metaclass == "MetaController":
                try:
                    self.instantiate_analysis_tab(subclass)
                except Exception as e:
                    self.logger.error(
                        f"Unable to restore Analysis Tab {key} of type {subclass} due to {str(e)}"
                    )
            else:
                settings = plugin.get("settings")
                try:
                    self.data_plugin_controller.validate_and_instantiate_plugin(
                        metaclass=metaclass,
                        subclass=subclass,
                        settings=settings,
                        key=key,
                    )
                except Exception as e:
                    self.logger.error(
                        f"Unable to restore plugin {key} of type {metaclass}/{subclass} due to {str(e)}"
                    )

    @log(logger=logger)
    @Slot()
    def send_analysis_tabs(self) -> None:
        """Send the list of instantiated analysis tabs to MainView."""
        self.logger.debug("Sending instantiated analysis tabs to MainView.")

        if not self.analysis_tabs:
            self.logger.warning(
                "No instantiated analysis tabs found in MainController."
            )

        # Emit the correct signal with the current analysis tabs
        self.main_view.received_analysis_tabs.emit(self.analysis_tabs)
