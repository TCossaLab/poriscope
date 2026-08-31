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
from abc import abstractmethod
from collections import OrderedDict
from copy import deepcopy
from typing import Any, Dict, Generator, List, Mapping, Optional

from PySide6.QtCore import QObject, Qt, Signal, Slot

from poriscope.utils.LogDecorator import log
from poriscope.utils.QObjectABCMeta import QObjectABCMeta


class MetaController(QObject, metaclass=QObjectABCMeta):
    """
    Base controller class that manages exactly one MetaView and MetaModel instance
    """

    global_signal = Signal(
        str, str, str, tuple, object, tuple
    )  # metaclass type, subclass key, function to call, args for function to call, return function to call
    # NOTE: every connection to global_signal/data_plugin_controller_signal must stay
    # Qt.ConnectionType.DirectConnection (or otherwise guaranteed same-thread). A caller
    # that passes a return_function_name reads the result back off an attribute the
    # callback sets, on the very next statement after .emit() - a queued connection
    # would silently degrade that read to stale/None data with no error and no log line.
    data_plugin_controller_signal = Signal(
        str, str, str, tuple, object, tuple
    )  # metaclass type, subclass key, function to call, args for function to call, function to call with reval, added args for retval
    plugin_state_changed = Signal(str, str, str)  # metaclass, plugin_key, reason
    add_text_to_display = Signal(str, str)
    update_tab_action_history = Signal(
        str, object
    )  # name of tab subclass, OrderedDict of actions to take
    save_tab_action_history = Signal(object, str)  # dict of actions, save file name
    create_plugin = Signal(str, str)  # metaclass, subclass
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        available_subclasses: Optional[Mapping[str, List[str]]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the MetaController, along with its MetaView and MetaModel (built by the subclass's `_init()`).

        :param available_subclasses: mapping of available plugin subclasses, passed through to the view
        :type available_subclasses: Optional[Mapping[str, List[str]]]
        :param \\**kwargs: Additional parameters to set as attributes on the instance
        :type \\**kwargs: Any
        """

        super().__init__()

        for (
            k,
            v,
        ) in kwargs.items():  # set class parameters with kwargs dict for use later
            setattr(self, k, v)

        self._init()
        self._connect_global_signal()
        self.view.set_available_subclasses(available_subclasses)
        self.view.plugin_state_changed.connect(self.plugin_state_changed)
        self.view.run_generators.connect(self.model.run_generators)
        self.model.update_progressbar.connect(self.view.update_progressbar)
        self.view.kill_worker.connect(self.handle_kill_worker)
        self.view.kill_all_workers.connect(self.handle_kill_all_workers)
        self.view.add_text_to_display.connect(self.relay_add_text_to_display)
        self.model.add_text_to_display.connect(self.relay_add_text_to_display)
        self.view.save_tab_action_history.connect(self.save_tab_actions)
        self.view.update_tab_action_history.connect(self.update_tab_actions)
        self.view.cache_plot_data.connect(self.model.cache_plot_data)
        self.view.export_plot_data.connect(self.export_plot_data)
        self.view.load_actions_from_json.connect(self.load_actions_from_json)
        self.view.create_plugin.connect(self._relay_create_plugin)
        self._setup_connections()
        self.tab_action_history: OrderedDict[int, dict[str, Any]] = OrderedDict()

    # private API, must be implemented by sublcasses
    @abstractmethod
    def _init(self) -> None:
        """
        Perform additional initialization specific to the algorithm being implemented.
        Must be implemented by subclasses.

        This function is called at the end of the class constructor to perform additional initialization specific to the algorithm being implemented.
        kwargs provided to the base class constructor are available as class attributes.
        """
        pass

    @abstractmethod
    def _setup_connections(self) -> None:
        """
        Set up any local connections between the subordinate view and model
        """
        pass

    @log(logger=logger)
    @Slot(str, str)
    def _relay_create_plugin(self, metaclass: str, subclass: str) -> None:
        self.create_plugin.emit(metaclass, subclass)

    @log(logger=logger)
    def update_plot_data(self, data: Optional[Any]) -> None:
        """
        Update the view with new plot data.

        :param data: Optional data to be plotted (e.g., event traces or fitted results).
        :type data: Optional[Any]
        """
        self.view.update_plot_data(data)

    # public API, must be implemented by sublcasses

    @log(logger=logger)
    @Slot()
    def export_plot_data(self) -> None:
        """
        Export the currently cached plot data to a CSV file.

        Attempts to retrieve cached plot data from the model, prompts the user for a filename,
        and saves the data as a CSV if available. If no data is cached, logs a warning.
        """
        df = self.model.format_cache_data()
        if df is None:
            self.logger.warning("No cached data, plot something and try again")
            return
        file_name = self.view.get_save_filename()
        if file_name:
            df = df.fillna("")
            df.to_csv(file_name, index=False)

    # private API, should generally be left alone by subclasses
    @log(logger=logger)
    def _connect_global_signal(self) -> None:
        """
        Connect global and data plugin signal relays from the view and model.

        This enables propagation of global signals upward to the main controller.
        """
        self.view.global_signal.connect(
            self._relay_global_signal, type=Qt.ConnectionType.DirectConnection
        )
        self.model.global_signal.connect(
            self._relay_global_signal, type=Qt.ConnectionType.DirectConnection
        )

        self.view.data_plugin_controller_signal.connect(
            self._relay_data_plugin_controller_signal,
            type=Qt.ConnectionType.DirectConnection,
        )
        self.model.data_plugin_controller_signal.connect(
            self._relay_data_plugin_controller_signal,
            type=Qt.ConnectionType.DirectConnection,
        )

    @log(logger=logger)
    @Slot(str)
    def load_actions_from_json(self, filename: str) -> None:
        """
        Load and apply tab actions from a JSON file.

        :param filename: Path to the JSON file containing saved actions.
        :type filename: str
        """
        try:
            with open(filename, "r") as json_file:
                actions = json.load(json_file)
        except Exception as e:
            self.logger.error(f"Error loading action history: {e}")
            return None
        if self.__class__.__name__ in actions.keys():
            actions = actions[self.__class__.__name__]  # allow loading from base file
        self.view.update_actions_from_json(actions)

    @log(logger=logger)
    def display_write_status(self, status: bool) -> None:
        """
        Emit a message indicating whether data was successfully written.

        :param status: True if write was successful, False otherwise.
        :type status: bool
        """
        if status is True:
            self.add_text_to_display.emit(
                "Successfully wrote data", self.__class__.__name__
            )
        else:
            self.add_text_to_display.emit(
                "Failed to write data", self.__class__.__name__
            )

    @log(logger=logger)
    def check_column_exists(self, table_name: str) -> None:
        """
        Notify the view to check if a cluster column exists in the given table.

        :param table_name: Name of the table to check.
        :type table_name: str
        """
        self.view.set_column_exists(table_name)

    @log(logger=logger)
    @Slot(str)
    def relay_add_text_to_display(self, text: str, source: str) -> None:
        """
        Relay text from model or view to be displayed in the main text display widget
        """
        self.add_text_to_display.emit(text, source)

    @log(logger=logger)
    @Slot(str, int)
    def handle_kill_worker(self, subclass: str, identifier: str) -> None:
        """
        Kill the selected worker if it is running.

        Note: the ``@Slot(str, int)`` decorator's declared second-argument type
        (``int``) does not match the ``str`` value actually delivered by
        ``MetaView.kill_worker`` (``Signal(str, str)``) or the ``"key/channel"``
        string parsing performed below; this is a pre-existing mismatch and is
        left as-is here since fixing it is a behavior change, not a type-hint
        change.
        """
        self.logger.debug(
            f"Called handle_kill_worker with subclass='{subclass}', self class='{self.__class__.__name__}', identifier={identifier}"
        )

        # Extract key and channel from identifier
        try:
            key, channel_str = identifier.split("/")  # Extract key and channel
            channel = int(channel_str)  # Convert channel to integer
        except ValueError:
            self.logger.error(
                f"Invalid identifier format: {identifier}. Expected format 'key/channel'."
            )
            return

        # Log full dictionary for debugging
        self.logger.debug(f"Full self.model.workers dictionary: {self.model.workers}")

        # Check if the key exists in workers
        if key in self.model.workers:
            available_channels = list(
                self.model.workers[key].keys()
            )  # Get second-level keys (channels)
            self.logger.debug(
                f"Currently active workers for key '{key}': {available_channels}"
            )

            # Check if the channel exists inside the key's dictionary
            if channel in self.model.workers[key]:
                self.logger.info(
                    f"Stopping worker for channel {channel} in {subclass} (matched worker: {key}/{channel})"
                )
                self.model.stop_workers(key, channel)  # Pass both key and channel
                return
            else:
                self.logger.warning(
                    f"No active worker found for channel {channel} under key '{key}' in {subclass}. Available channels: {available_channels}"
                )
        else:
            self.logger.warning(
                f"No active workers found for key '{key}' in {subclass}. Full dictionary: {self.model.workers}"
            )

    @log(logger=logger)
    def set_generator(
        self,
        generator: Generator[float, Optional[bool], None],
        channel: int,
        key: str,
        metaclass: str,
    ) -> None:
        """
        Assign a generator to the model for asynchronous event processing.

        :param generator: Generator object for producing event data.
        :type generator: Generator[float, Optional[bool], None]
        :param channel: Target channel number.
        :type channel: int
        :param key: Identifier key for the data stream.
        :type key: str
        :param metaclass: Metaclass name associated with the generator.
        :type metaclass: str
        """
        self.model.set_generator(generator, channel, key, metaclass)

    @log(logger=logger)
    @Slot(str)
    def handle_kill_all_workers(self, subclass: str, exiting: bool = False) -> None:
        """
        Kill all running workers.
        """
        if subclass == self.__class__.__name__:
            self.logger.info(f"Stopping all workers for {subclass}")
            self.model.stop_workers(exiting=exiting)

    @Slot(str, str, str, tuple, str, tuple)
    def _relay_global_signal(
        self,
        metaclass: str,
        subclass_key: str,
        call_function: str,
        call_args: tuple,
        return_function_name: Optional[str],
        ret_args: tuple,
    ) -> None:
        """
        Push the global signal up to the main_controller, adding the identifier for the requesting plugin. This will result in a call being made with the following signature in main_controller:

        .. code-block:: python

          main_model.plugins['MetaController'][plugin_key].return_function(*plugins[metaclass][subclass_key].call_function(*call_args)+ret_args)

        Validation is handled by main_controller

        :param metaclass: A string matching the metaclass of the target plugin for the signal
        :type metaclass: str
        :param subclass_key: A string matching the identifier of a plugin that subclasses metaclass
        :type subclass_key: str
        :param call_function: A string matching the signature of a callable in the plugin identified by metaclass and subclass. This function should be a public API member of another subclass that has already been instantiated.
        :type call_function: str
        :param call_args: A tuple that will be passed to the callable matching call_function
        :type call_args: tuple
        :param return_function_name: A string matching the signature of a callable function defined in this controller with a signature that matched the return type of call_function. This function must exist in this controller.
        :type return_function_name: Optional[str]
        :param ret_args: A tuple that will be appended to the return value of the call_function
        :type ret_args: tuple
        """
        self.logger.debug(
            f"MetaController received signal: {metaclass}, {subclass_key}, {call_function}, {call_args}, {return_function_name}, {ret_args}"
        )
        if return_function_name is not None and return_function_name != "":
            return_function = getattr(self, return_function_name, None)
            if return_function is None:
                self.logger.warning(
                    f"{return_function_name} is not an attribute of {self.__class__.__name__}"
                )
                return
            if not callable(return_function):
                self.logger.warning(
                    f"{return_function_name} is not callable on {self.__class__.__name__}"
                )
                return
        else:
            return_function = None

        try:
            self.logger.info(
                "Emitting Global Signal from MetaController to MainController"
            )
            self.global_signal.emit(
                metaclass,
                subclass_key,
                call_function,
                call_args,
                return_function,
                ret_args,
            )
        except Exception:
            self.logger.exception(
                f"Unable to relay global signal for {metaclass}/{subclass_key}.{call_function} "
                f"from {type(self).__name__} to MainController"
            )

    @Slot(str, str, str, tuple, str, tuple)
    def _relay_data_plugin_controller_signal(
        self,
        metaclass: str,
        subclass_key: str,
        call_function: str,
        call_args: tuple,
        return_function_name: Optional[str],
        ret_args: tuple,
    ) -> None:
        """
        Push the data plugin controller signal up to the main_controller, adding the identifier for the requesting plugin. This will result in a call being made with the following signature in main_controller:

        .. code-block:: python

          main_model.plugins['MetaController'][plugin_key].return_function(*plugins[metaclass][subclass_key].call_function(*call_args))

        Validation is handled by main_controller

        :param metaclass: A string matching the metaclass of the target plugin for the signal
        :type metaclass: str
        :param subclass_key: A string matching the identifier of a plugin that subclasses metaclass
        :type subclass_key: str
        :param call_function: A string matching the signature of a callable in the data plugin controller. (NOT in the data plugin itself).
        :type call_function: str
        :param call_args: A tuple that will be passed to the callable matching call_function
        :type call_args: tuple
        :param return_function_name: A string matching the signature of a callable function defined in this controller with a signature that matched the return type of call_function. This function must exist in this controller.
        :type return_function_name: Optional[str]
        :param ret_args: A tuple that will be appended to the return value of the call_function
        :type ret_args: tuple
        """
        self.logger.debug(
            f"MetaController received signal: {metaclass}, {subclass_key}, {call_function}, {call_args}, {return_function_name}, {ret_args}"
        )
        if return_function_name is not None and return_function_name != "":
            return_function = getattr(self, return_function_name, None)
            if return_function is None:
                self.logger.warning(
                    f"{return_function_name} is not an attribute of {self.__class__.__name__}"
                )
                return
            if not callable(return_function):
                self.logger.warning(
                    f"{return_function_name} is not callable on {self.__class__.__name__}"
                )
                return
        else:
            return_function = None

        try:
            self.logger.info(
                "Emitting Data Plugin from MetaController to MainController"
            )
            self.data_plugin_controller_signal.emit(
                metaclass,
                subclass_key,
                call_function,
                call_args,
                return_function,
                ret_args,
            )
        except Exception:
            self.logger.exception(
                f"Unable to relay data plugin controller signal for {call_function} "
                f"from {type(self).__name__} to MainController"
            )

    # public API, should generally be left alone by subclasses

    @log(logger=logger)
    def update_available_plugins(
        self, available_plugins: Mapping[str, list[str]]
    ) -> None:
        """
        Called whenever a new plugin is instantiated elsewhere in the app, to keep an up to date list of possible data sources for use by this plugin

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app
        :type available_plugins: Mapping[str, list[str]]
        """
        self.view.update_available_plugins(available_plugins)
        self.model.update_available_plugins(available_plugins)

    @log(logger=logger)
    @Slot(str)
    def save_tab_actions(self, save_file: Optional[str] = None) -> None:
        """
        Emit a signal to save the current tab action history to the specified file.

        :param save_file: Optional path to the file where actions should be saved.
        :type save_file: Optional[str]
        """
        self.save_tab_action_history.emit(self.tab_action_history, save_file)

    @log(logger=logger)
    @Slot(object, bool)
    def update_tab_actions(
        self, history: Optional[dict] = None, undo: bool = False
    ) -> None:
        """
        Update or undo the current tab action history, and emit the updated state.

        :param history: Dictionary representing a new action to add.
        :type history: Optional[dict]
        :param undo: If True, removes the most recent action and reverts to the previous state.
        :type undo: bool
        """
        if not undo:
            if history:
                self.tab_action_history[len(self.tab_action_history)] = history
        else:
            try:
                self.tab_action_history.popitem()
            except KeyError:
                return
            try:
                last_item = self.tab_action_history[
                    next(reversed(self.tab_action_history))
                ]
            except StopIteration:
                pass
            else:
                while last_item["function"] == "_reset_actions":
                    self.tab_action_history.popitem()
                    try:
                        last_item = self.tab_action_history[
                            next(reversed(self.tab_action_history))
                        ]
                    except StopIteration:
                        break
            history = deepcopy(self.tab_action_history)
            self.tab_action_history = OrderedDict()
            self.view.update_actions_from_json(history)
        self.update_tab_action_history.emit(
            self.__class__.__name__, self.tab_action_history
        )

    @log(logger=logger)
    def ignore(self) -> None:
        """
        Placeholder method that does nothing. Can be overridden if needed.
        """
        pass

    @log(logger=logger)
    def get_session_state(self) -> Dict[str, Any]:
        """
        Return extra tab-specific state to persist alongside this tab's session history entry.

        MainController calls this on every open tab immediately before writing session
        history to disk, and merges the result into that tab's history entry. The base
        implementation returns an empty dict. A subclass that keeps state MainController
        cannot otherwise see (e.g. a filter list built entirely in the view) should
        override this, and override :meth:`restore_session_state` to apply it back.

        :return: Extra state to serialize into this tab's session history entry.
        :rtype: Dict[str, Any]
        """
        return {}

    @log(logger=logger)
    def restore_session_state(self, state: Dict[str, Any]) -> None:
        """
        Restore extra tab-specific state captured by :meth:`get_session_state`.

        Called by MainController after this tab is freshly instantiated during session
        load, with that tab's full history entry (including keys unrelated to session
        state, which implementations should ignore). The base implementation does nothing.

        :param state: This tab's session history entry, as previously written by
            :meth:`get_session_state`.
        :type state: Dict[str, Any]
        """
        pass
