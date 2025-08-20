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
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QObject, Slot

from poriscope.controllers.DataPluginController import DataPluginController
from poriscope.utils.LogDecorator import log


class MainController(QObject):
    logger = logging.getLogger(__name__)

    def __init__(self, main_model, main_view):
        super().__init__()
        self.main_model = main_model
        self.main_view = main_view
        self.config_path = Path(Path(__file__).resolve().parent, ".." "configs")

        # analysis tab managers
        self.analysis_tabs = (
            {}
        )  # a dict keyed by subclass of controllers for analysis tabs, with the instance of that tab

        # data plugin managers
        self.data_plugins = (
            {}
        )  # a dict keyed by metaclass with lists of keys for instances of subclasses of that metaclass

        self.data_plugin_controller = DataPluginController(
            self.main_model.get_plugin_classes(),
            self.main_model.get_data_server_location(),
        )

        self.plugin_history: Dict[str, Any] = {}
        self.tab_action_history: Dict[str, Any] = {}

        previous_plugin_history = self.main_model.load_session(None)
        if previous_plugin_history is not None:
            self.previous_plugin_history = previous_plugin_history

        self.setup_connections()

    @log(logger=logger)
    def setup_connections(self):
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
        self.main_view.received_analysis_tabs.connect(
            self.main_view.populate_plugins_menu
        )

    @log(logger=logger)
    @Slot()
    def handle_about_to_quit(self):
        for key, val in self.analysis_tabs.items():
            if val:
                val.handle_kill_all_workers(key, exiting=True)
        self.data_plugin_controller.handle_exit()

    @log(logger=logger)
    @Slot(str, str, object)
    def send_curent_data_server(self):
        data_server = self.main_model.get_app_config("Parent Folder")
        self.main_view.set_data_server(data_server)

    @log(logger=logger)
    @Slot(str, str, object)
    def send_curent_user_plugin_location(self):
        data_server = self.main_model.get_app_config("User Plugin Folder")
        self.main_view.set_user_plugin_location(data_server)

    @log(logger=logger)
    @Slot(str)
    def update_data_server_location(self, data_server):
        self.main_model.update_app_config("Parent Folder", data_server)
        self.data_plugin_controller.update_data_server_location(data_server)

    @log(logger=logger)
    @Slot(str)
    def update_user_plugin_location(self, user_plugin_loc):
        self.main_model.update_app_config("User Plugin Folder", user_plugin_loc)
        plugin_path = Path(user_plugin_loc).resolve()
        parent_path = plugin_path.parent
        if str(parent_path) not in sys.path:
            sys.path.append(str(parent_path))

    @log(logger=logger)
    @Slot(str, str, object)
    def get_plugin_instance(self, metaclass, key, callback):
        callback(self.data_plugin_controller.get_plugin_instance(metaclass, key))

    @log(logger=logger)
    @Slot(str, str)
    def get_settings_from_history(self, metaclass, subclass):
        try:
            for key, val in self.plugin_history.items():
                if (
                    val.get("subclass") == subclass
                    and val.get("metaclass") == metaclass
                ):
                    self.data_plugin_controller.set_settings(val.get("settings"))
                    return
            for key, val in self.previous_plugin_history.items():
                if (
                    val.get("subclass") == subclass
                    and val.get("metaclass") == metaclass
                ):
                    self.data_plugin_controller.set_settings(val.get("settings"))
                    return
        except AttributeError:
            self.data_plugin_controller.set_settings(None)
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
        self.logger.debug(
            f"received signal: {metaclass}, {subclass_key}, {call_function}, {call_args}, {return_function}, {ret_args}"
        )
        instance = self.data_plugin_controller.get_plugin_instance(
            metaclass, subclass_key
        )

        if instance is not None:
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
                except Exception:
                    pass

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
        self.logger.debug(
            f"received signal: {metaclass}, {subclass_key}, {call_function}, {call_args}, {return_function}, {ret_args}"
        )
        instance = (
            self.data_plugin_controller
        )  # this one goes to the data plugin controller directly, NOT to an actual plugin instance

        if instance is not None:
            func = getattr(instance, call_function, None)
            if func is None:
                raise ValueError(
                    f"No value {call_function} found in data plugin controller"
                )
            elif not callable(func):
                raise ValueError(f"{call_function} is not callable")
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
                            raise
                except:
                    raise

    @log(logger=logger)
    @Slot(str, list)
    def update_available_plugins(self, metaclass, available_plugins):
        self.logger.debug(
            f"Available {metaclass} plugins updates to {available_plugins}"
        )
        self.data_plugins[metaclass] = available_plugins
        for key, val in self.analysis_tabs.items():
            if val:
                val.update_available_plugins(self.data_plugins)

    @log(logger=logger)
    @Slot(dict, str)
    def update_plugin_history(self, history, delete_key):
        if history and not delete_key:
            if history:
                self.plugin_history[history.pop("key")] = history
        elif not history and delete_key:
            self.plugin_history.pop(delete_key)
        elif history and delete_key:
            new_history = {}
            for key, val in self.plugin_history.items():
                if key == delete_key:
                    new_history[history.pop("key")] = history
                else:
                    new_history[key] = val
            self.plugin_history = new_history
        self.main_model.save_session(self.plugin_history)

    @log(logger=logger)
    @Slot(str, object)
    def update_tab_action_history(self, key, history):
        self.tab_action_history[key] = history
        self.main_model.save_tab_actions(self.tab_action_history)

    @log(logger=logger)
    @Slot(str)
    def instantiate_analysis_tab(self, subclass):
        """
        Instantiate a reader plugin to read a given dataset. Exceptions are handled in the caller.
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
    def save_session(self, save_file=None):
        self.main_model.save_session(self.plugin_history, save_file)

    @log(logger=logger)
    @Slot(object, str)
    def save_tab_action_history(self, history, save_file=None):
        self.main_model.save_tab_actions(history, save_file)

    @log(logger=logger)
    @Slot(str)
    def load_session(self, file_name=None):
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
                except ValueError as e:
                    if "already exists globally" in str(e):
                        self.logger.warning(
                            f"Skipped loading plugin {key} from session: {str(e)}. Plugin with key '{key}' already exists."
                        )
                    else:
                        self.logger.error(
                            f"Unable to restore plugin {key} of type {metaclass}/{subclass} due to {str(e)}"
                        )
                except Exception as e:
                    # unexpected failure: keep restore running
                    self.logger.error(
                        "Unexpected restore error (%s/%s, key=%s): %s",
                        metaclass,
                        subclass,
                        key,
                        e,
                    )
                # optionally: logger.debug("traceback", exc_info=True)
                # continue

    @log(logger=logger)
    @Slot()
    def send_analysis_tabs(self):
        """Send the list of instantiated analysis tabs to MainView."""
        self.logger.debug("Sending instantiated analysis tabs to MainView.")

        if not self.analysis_tabs:
            self.logger.warning(
                "No instantiated analysis tabs found in MainController."
            )

        # Emit the correct signal with the current analysis tabs
        self.main_view.received_analysis_tabs.emit(self.analysis_tabs)
