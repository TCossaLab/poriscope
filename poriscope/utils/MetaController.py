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

import inspect
import json
import logging
from abc import abstractmethod
from collections import OrderedDict
from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from PySide6.QtCore import QObject, Signal, Slot

from poriscope.utils.LogDecorator import (
    ACTION_DECLARATION_ATTR,
    ACTION_NAME_ATTR,
    RESET_ACTION,
    ActionDeclaration,
    log,
)
from poriscope.utils.MetaModel import MetaModel
from poriscope.utils.MetaView import MetaView
from poriscope.utils.QObjectABCMeta import QObjectABCMeta
from poriscope.utils.replay_sequence import ReplaySequence
from poriscope.utils.ReplayGuard import replaying

#: The plugin method that says whether a channel holds a finished run, per plugin family.
#: A run clears its channel as it starts, so once a run ends this says whether that run
#: finished. A result whose plugin is of another family is recorded when its run ends,
#: unasked.
RUN_STATUS = {
    "MetaEventFinder": "get_eventfinding_status",
    "MetaEventFitter": "get_eventfitting_status",
}


def declared_actions(cls: type) -> List[Tuple[str, str]]:
    """
    List the methods of a class that carry a declared action name.

    The class is searched, so no property or Qt attribute is evaluated and no instance is
    needed. A subclass's override is the attribute that is found.

    :param cls: the Controller or View class to search
    :type cls: type
    :return: (attribute name, declared action name) for each declared method
    :rtype: List[Tuple[str, str]]
    """
    declared = []
    for attribute in dir(cls):
        name = getattr(getattr(cls, attribute, None), ACTION_NAME_ATTR, None)
        if isinstance(name, str):
            declared.append((attribute, name))
    return declared


def declarations_of(cls: type) -> Dict[str, ActionDeclaration]:
    """
    Map each action a Controller class declares to what it declares about it.

    :param cls: the Controller class to search
    :type cls: type
    :return: declared action name -> its declaration
    :rtype: Dict[str, ActionDeclaration]
    """
    return {
        name: getattr(getattr(cls, attribute), ACTION_DECLARATION_ATTR)
        for attribute, name in declared_actions(cls)
    }


class MetaController(QObject, metaclass=QObjectABCMeta):
    """
    Base controller class that manages exactly one MetaView and MetaModel instance
    """

    plugin_state_changed = Signal(str, str, str)  # metaclass, plugin_key, reason
    add_text_to_display = Signal(str, str)

    #: The last line sent to the status panel, whoever sent it, so a subclass can leave out a
    #: line that would only repeat the one directly above it.
    last_panel_text: str = ""
    update_tab_action_history = Signal(
        str, object
    )  # name of tab subclass, OrderedDict of actions to take
    save_tab_action_history = Signal(object, str)  # dict of actions, save file name
    create_plugin = Signal(str, str)  # metaclass, subclass
    edit_plugin = Signal(str, str)  # metaclass, key
    delete_plugin = Signal(str, str)  # metaclass, key
    logger = logging.getLogger(__name__)

    #: The View and Model this controller owns. Both are created by the subclass's
    #: ``_init()`` before ``__init__`` wires them, so they are declared here rather
    #: than assigned: without the declarations every ``self.view``/``self.model``
    #: use across the controllers was invisible to the type checker (79 errors in the
    #: project-venv run of 2026-10-05). A subclass that needs the narrower type of its
    #: own View or Model redeclares the attribute with it.
    view: MetaView
    model: MetaModel

    #: name -> method for every declared action of this tab; built on first use by
    #: :py:meth:`action_registry`.
    _action_registry: Optional[Dict[str, Callable[..., Any]]] = None

    #: name -> declaration for every declared action of this tab; read on first use.
    _declarations: Optional[Dict[str, ActionDeclaration]] = None

    #: (plugin key, channel) -> the entry of a result whose run has not ended yet.
    _held_results: Optional[Dict[Tuple[Any, Any], Dict[str, Any]]] = None

    #: (text, source) of each status-panel line held back while this tab replays.
    _held_panel_text: Optional[List[Tuple[str, str]]] = None

    #: True while a line is sent that must reach the panel even during a replay.
    _panel_text_now: bool = False

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
        self.replay_sequence = ReplaySequence(self)
        self.view.set_available_subclasses(available_subclasses)
        self.view.plugin_state_changed.connect(self.plugin_state_changed)
        self.model.update_progressbar.connect(self.view.update_progressbar)
        # Recorded first, so a replay waiting on the run sees the tab's history with it.
        self.model.run_finished.connect(self.record_finished_run)
        self.model.run_finished.connect(self.replay_sequence.on_run_finished)
        self.view.kill_worker.connect(self.handle_kill_worker)
        self.view.kill_all_workers.connect(self.handle_kill_all_workers)
        self.add_text_to_display.connect(self._note_panel_text)
        self.view.add_text_to_display.connect(self.relay_add_text_to_display)
        self.model.add_text_to_display.connect(self.relay_add_text_to_display)
        self.view.save_tab_action_history.connect(self.save_tab_actions)
        self.view.update_tab_action_history.connect(self.update_tab_actions)
        self.view.discard_last_tab_action.connect(self.discard_last_tab_action)
        self.view.cache_plot_data.connect(self.model.cache_plot_data)
        self.view.export_plot_data.connect(self.export_plot_data)
        self.view.load_actions_from_json.connect(self.load_actions_from_json)
        self.view.create_plugin.connect(self._relay_create_plugin)
        self.view.edit_plugin.connect(self._relay_edit_plugin)
        self.view.delete_plugin.connect(self._relay_delete_plugin)
        self._setup_connections()
        self.tab_action_history: OrderedDict[int, dict[str, Any]] = OrderedDict()

    # private API, must be implemented by sublcasses
    @abstractmethod
    def _init(self) -> None:
        """
        Build this tab's View and Model, and do any other setup the tab needs.

        Assigning both ``self.view`` and ``self.model`` is required rather than
        conventional: the constructor calls this and then immediately connects the two to
        each other, so leaving either unset raises ``AttributeError`` before the tab
        exists. kwargs given to the base constructor are available as attributes by the
        time this runs.
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
    @Slot(str, str)
    def _relay_edit_plugin(self, metaclass: str, key: str) -> None:
        """
        Pass a tab's request to edit a plugin's settings up to the app shell.

        One of three identically shaped relays - create, edit, delete - which is
        why this is a plain typed signal rather than the string-dispatched bus
        that used to carry it. The shell connects the far end straight to
        `DataPluginController.edit_plugin_settings`, so mypy checks the pair.

        :param metaclass: the plugin family, e.g. "MetaReader"
        :type metaclass: str
        :param key: the plugin to edit
        :type key: str
        """
        self.edit_plugin.emit(metaclass, key)

    @log(logger=logger)
    @Slot(str, str)
    def _relay_delete_plugin(self, metaclass: str, key: str) -> None:
        """
        Pass a tab's request to delete a plugin up to the app shell.

        :param metaclass: the plugin family, e.g. "MetaReader"
        :type metaclass: str
        :param key: the plugin to delete
        :type key: str
        """
        self.delete_plugin.emit(metaclass, key)

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

    # ------------------------------------------------------- the data plugins
    # The instances arrive from MainController on every plugin lifecycle event and are
    # forwarded straight to the Model, which is where the calls belong: a Controller
    # slot reaches a plugin with self.model.call(...).

    @log(logger=logger)
    def set_plugin_instances(
        self, instances: Mapping[str, Mapping[str, object]]
    ) -> None:
        """
        Receive the live data plugin instances and pass them to the Model.

        Called by ``MainController`` whenever the app's plugin set changes, on the same
        path that refreshes the plugin *names* the View shows in its comboboxes - so a
        rename or a re-instantiation cannot leave either of them stale.

        :param instances: metaclass name -> plugin key -> live instance
        :type instances: Mapping[str, Mapping[str, object]]
        :return: None
        :rtype: None
        """
        self.model.set_plugin_instances(instances)

    # private API, should generally be left alone by subclasses
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
        if not self.start_replay(actions.values()):
            self._panel_text_now = True
            try:
                self.add_text_to_display.emit(
                    f"{self.__class__.__name__}: a replay is already running; stop it, "
                    f"or let it finish, first",
                    self.__class__.__name__,
                )
            finally:
                self._panel_text_now = False

    @log(logger=logger)
    def start_replay(self, entries: Optional[Iterable[Any]] = None) -> bool:
        """
        Replay recorded actions one entry at a time, without blocking the window.

        Each entry runs on its own turn of the event loop. A ``result`` entry waits for its
        plugin's run on its channel to end, and the replay stops at the first entry that
        fails; see :py:mod:`poriscope.utils.replay_sequence`. Undo replays with
        :py:meth:`replay` instead, all at once.

        :param entries: recorded entries, ``{"action": name, "args": [...], "kwargs": {...}}``;
            None continues the last replay from the entry it stopped or failed at
        :type entries: Optional[Iterable[Any]]
        :return: False if a replay of this tab is already running, or there is nothing left
            to continue
        :rtype: bool
        """
        return self.replay_sequence.start(entries)

    @log(logger=logger)
    def is_replaying(self) -> bool:
        """
        Is a replay started by :py:meth:`start_replay` still running?

        :return: True until it is done, has failed or was stopped
        :rtype: bool
        """
        return self.replay_sequence.running

    @log(logger=logger)
    def panel_text_to_show(self, text: str, source: str) -> List[Tuple[str, str]]:
        """
        Say which status-panel lines to show now, given a line this tab has just sent.

        While the tab replays, its lines are held back and nothing is shown, so the panel
        does not interleave them with other tabs' lines. The first line once the replay has
        ended - it says how the replay ended - comes with the held lines before it, in order.
        A line the tab must show at once, such as refusing a second replay, is shown
        alone and holds nothing back.
        The tab's own ``add_text_to_display`` carries every line as it is sent.

        :param text: the line
        :type text: str
        :param source: who sent it
        :type source: str
        :return: (text, source) of each line to show now, in order
        :rtype: List[Tuple[str, str]]
        """
        if self._panel_text_now:
            return [(text, source)]
        if self._held_panel_text is None:
            self._held_panel_text = []
        if self.is_replaying():
            self._held_panel_text.append((text, source))
            return []
        shown = self._held_panel_text + [(text, source)]
        self._held_panel_text = []
        return shown

    @log(logger=logger)
    def record_action(self, entry: Dict[str, Any]) -> None:
        """
        Append one declared action to this tab's history and tell the main window.

        The hook :py:func:`~poriscope.utils.LogDecorator.register_action` calls for a
        decorated Controller method. A ``result`` is held instead, under its plugin and
        channel, until :py:meth:`record_finished_run` hears that its run ended. A second
        launch of a run still going is refused by the Model, so the entry held first is
        kept.

        :param entry: ``{"action": name, "args": ..., "kwargs": ...}``
        :type entry: Dict[str, Any]
        """
        declaration = self._declarations_of_tab().get(entry.get("action", ""))
        kwargs = entry.get("kwargs") or {}
        if (
            declaration is not None
            and declaration.kind == "result"
            and all(name in kwargs for name in declaration.key)
        ):
            run = (kwargs[declaration.key[0]], kwargs[declaration.key[1]])
            self._held().setdefault(run, entry)
            return
        self.update_tab_actions(entry, False)

    @log(logger=logger)
    @Slot(int, str)
    def record_finished_run(self, channel: int, key: str) -> None:
        """
        Record a held result once its run ended, if the plugin says that run finished.

        A run that did not finish - cancelled, failed, or with nothing found - is not
        recorded, and the status panel says so. It cleared the channel as it started, so an
        earlier run of the same plugin and channel, and every view drawn from it, is removed
        from the history too: a restore must not bring back results the tab no longer holds.
        A run nothing was held for, a write say, is ignored.

        :param channel: the channel the run worked on
        :type channel: int
        :param key: the plugin's key
        :type key: str
        """
        entry = self._held().pop((key, channel), None)
        if entry is None:
            return
        if self._run_finished_channel(key, channel):
            self.update_tab_actions(entry, False)
            return
        text = (
            f"{key} did not finish channel {channel}, so this run is not saved in the "
            f"tab's history"
        )
        if self._forget_run(key, channel):
            text += (
                "; its earlier run on that channel is removed from the history too, with "
                "what was drawn from it, since the channel no longer holds its results"
            )
            self.update_tab_action_history.emit(
                self.__class__.__name__, self.tab_action_history
            )
        self.add_text_to_display.emit(text, self.__class__.__name__)

    def _forget_run(self, key: str, channel: int) -> bool:
        """
        Remove every recorded run of one plugin on one channel, and the views drawn from it.

        :param key: the plugin's key
        :type key: str
        :param channel: the channel
        :type channel: int
        :return: True if anything was removed
        :rtype: bool
        """
        declarations = self._declarations_of_tab()
        kept = []
        for recorded in self.tab_action_history.values():
            declaration = declarations.get(recorded.get("action", ""))
            if declaration is not None:
                names = (
                    declaration.key
                    if declaration.kind == "result"
                    else declaration.depends_on
                )
                kwargs = recorded.get("kwargs") or {}
                if names and tuple(kwargs.get(n) for n in names) == (key, channel):
                    continue
            kept.append(recorded)
        if len(kept) == len(self.tab_action_history):
            return False
        self.tab_action_history = OrderedDict(enumerate(kept))
        return True

    def _held(self) -> Dict[Tuple[Any, Any], Dict[str, Any]]:
        """
        The results held until their runs end, created on first use.

        :return: (plugin key, channel) -> held entry
        :rtype: Dict[Tuple[Any, Any], Dict[str, Any]]
        """
        if self._held_results is None:
            self._held_results = {}
        return self._held_results

    def _declarations_of_tab(self) -> Dict[str, ActionDeclaration]:
        """
        This tab's declarations, read once.

        :return: declared action name -> its declaration
        :rtype: Dict[str, ActionDeclaration]
        """
        if self._declarations is None:
            self._declarations = declarations_of(type(self))
        return self._declarations

    def _run_finished_channel(self, key: str, channel: int) -> bool:
        """
        Ask the plugin whether the channel holds a finished run.

        A run clears its channel as it starts, so right after a run ends this says whether
        that run finished. Called from a slot, so a status that cannot be read is logged and counts as not
        finished rather than raised.

        :param key: the plugin's key
        :type key: str
        :param channel: the channel
        :type channel: int
        :return: True if the run finished, or the plugin's family has no such status
        :rtype: bool
        """
        metaclass = self.model.reporter_metaclasses.get(key)
        method = RUN_STATUS.get(metaclass) if isinstance(metaclass, str) else None
        if metaclass is None or method is None:
            return True
        try:
            return bool(self.model.call(metaclass, key, method, channel))
        except Exception as e:
            self.logger.error(
                f"Unable to tell whether {key} finished channel {channel}: {e}"
            )
            return False

    @log(logger=logger)
    def action_registry(self) -> Dict[str, Callable[..., Any]]:
        """
        Map each declared action name to the method that runs it, for this tab.

        Built once, from the decorated methods of this Controller. A method without a
        declaration is not in it, so replay can only reach what was declared; a View
        records nothing and declares nothing.

        :raises ValueError: if one name is declared by two methods
        :return: action name -> bound method
        :rtype: Dict[str, Callable[..., Any]]
        """
        if self._action_registry is None:
            registry: Dict[str, Callable[..., Any]] = {}
            for attribute, name in declared_actions(type(self)):
                if name in registry:
                    raise ValueError(
                        f"The action name '{name}' is declared twice in "
                        f"{self.__class__.__name__}: {attribute} repeats it"
                    )
                registry[name] = getattr(self, attribute)
            self._action_registry = registry
        return self._action_registry

    @log(logger=logger)
    def replay(self, entries: Iterable[Any]) -> None:
        """
        Run recorded actions in order, each through its declared name.

        An entry with no action name, or one that names no declared action of this tab
        (an old-format entry, or a method that has since been removed), is reported on
        the status panel and skipped, and replay moves on. So is an entry whose values no
        longer fit its action's parameters - one saved before they changed - which is
        checked before the call, so an action's own ``TypeError`` still propagates.
        Replaying a decorated method records it again.

        The loop runs inside :py:func:`~poriscope.utils.ReplayGuard.replaying`, so a
        recorded action that reads a controls panel raises
        :py:class:`~poriscope.utils.ReplayGuard.ReplayWidgetReadError` instead of using
        today's widget values.

        :param entries: recorded entries, ``{"action": name, "args": [...], "kwargs": {...}}``
        :type entries: Iterable[Any]
        """
        with replaying():
            for entry in entries:
                resolved = self.resolve_replayed_entry(entry)
                if resolved is not None:
                    method, args, kwargs = resolved
                    method(*args, **kwargs)

    @log(logger=logger)
    def resolve_replayed_entry(
        self, entry: Any
    ) -> Optional[Tuple[Callable[..., Any], List[Any], Dict[str, Any]]]:
        """
        Find the method a recorded entry replays, and the values to call it with.

        An entry with no action name, or one that names no declared action of this tab
        (an old-format entry, or a method that has since been removed), is reported on
        the status panel and gives None. So does an entry whose values no longer fit its
        action's parameters - one saved before they changed. The fit is checked here, so
        an action's own ``TypeError`` still comes from the call.

        :param entry: a recorded entry, ``{"action": name, "args": [...], "kwargs": {...}}``
        :type entry: Any
        :return: the bound method, its positional and its keyword values; None if the
            entry cannot be replayed
        :rtype: Optional[Tuple[Callable[..., Any], List[Any], Dict[str, Any]]]
        """
        name = entry.get("action") if isinstance(entry, Mapping) else None
        method = self.action_registry().get(name) if isinstance(name, str) else None
        if method is None:
            described = (
                f"'{name}' is not a recorded action of {self.__class__.__name__}"
                if isinstance(name, str)
                else f"an entry with no action name was found in {self.__class__.__name__}"
            )
            self.logger.warning(f"Not replayed: {described}")
            self.add_text_to_display.emit(
                f"Not replayed: {described}", self.__class__.__name__
            )
            return None
        args = list(entry.get("args") or [])
        kwargs = dict(entry.get("kwargs") or {})
        try:
            inspect.signature(method).bind(*args, **kwargs)
        except TypeError:
            described = (
                f"the recorded values of '{name}' do not fit that action of "
                f"{self.__class__.__name__} any more"
            )
            self.logger.warning(f"Not replayed: {described}")
            self.add_text_to_display.emit(
                f"Not replayed: {described}", self.__class__.__name__
            )
            return None
        return method, args, kwargs

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

    @Slot(str, str)
    def _note_panel_text(self, text: str, source: str) -> None:
        """
        Remember the line that has just gone to the status panel.

        :param text: the line
        :type text: str
        :param source: who sent it
        :type source: str
        """
        self.last_panel_text = text

    @log(logger=logger)
    @Slot(str, str)
    def relay_add_text_to_display(self, text: str, source: str) -> None:
        """
        Relay text from model or view to be displayed in the main text display widget
        """
        self.add_text_to_display.emit(text, source)

    @log(logger=logger)
    @Slot(str, str)
    def handle_kill_worker(self, subclass: str, identifier: str) -> None:
        """
        Kill the selected worker if it is running, and say so on the display panel.

        Every branch reports to the user. Previously the *success* path logged at
        INFO, which is below the default log level and therefore invisible, while
        the two no-op paths logged at WARNING and so raised a modal dialog
        containing a repr of the whole worker dictionary - feedback was exactly
        inverted, and a user aborting an operation had no way to tell whether it
        had taken effect.

        :param subclass: Name of the controller the kill request is addressed to.
        :type subclass: str
        :param identifier: Worker identifier in ``"key/channel"`` form.
        :type identifier: str
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
            self.add_text_to_display.emit(
                f"Unable to stop {identifier}: expected a 'key/channel' identifier.",
                self.__class__.__name__,
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
                self.add_text_to_display.emit(
                    f"Stopping {key} on channel {channel}.",
                    self.__class__.__name__,
                )
                self.model.stop_workers(key, channel)  # Pass both key and channel
                return
            else:
                # Routine rather than exceptional: discard_generator pops a finished
                # run out of self.workers, so pressing kill on a run that has just
                # completed lands here. INFO plus a panel message, not a dialog.
                self.logger.info(
                    f"No active worker found for channel {channel} under key '{key}' in {subclass}. Available channels: {available_channels}"
                )
                self.add_text_to_display.emit(
                    f"Nothing to stop for {key} on channel {channel} - it is not running.",
                    self.__class__.__name__,
                )
        else:
            self.logger.info(f"No active workers found for key '{key}' in {subclass}.")
            self.logger.debug(f"Full workers dictionary: {self.model.workers}")
            self.add_text_to_display.emit(
                f"Nothing to stop for {key} - it is not running.",
                self.__class__.__name__,
            )

    @log(logger=logger)
    @Slot(str)
    def handle_kill_all_workers(self, subclass: str, exiting: bool = False) -> None:
        """
        Kill all running workers for this tab, stop its replay, and say so on the display panel.

        The panel messages are skipped when ``exiting`` is set: the display widget is
        being torn down along with everything else, so writing to it at that point
        would be pointless at best. A stopped replay continues from the entry it was on
        at the next :py:meth:`start_replay` with no entries.

        :param subclass: Name of the controller the request is addressed to; the
            request is ignored if it names a different one.
        :type subclass: str
        :param exiting: True when called from the application's shutdown handler,
            which additionally blocks until each thread has finished.
        :type exiting: bool
        """
        if subclass != self.__class__.__name__:
            self.logger.debug(
                f"Ignoring kill-all addressed to {subclass}; this is {self.__class__.__name__}"
            )
            return
        self.logger.info(f"Stopping all workers for {subclass}")
        if not exiting:
            self.add_text_to_display.emit(
                "Stopping all running operations.", self.__class__.__name__
            )
        self.replay_sequence.stop(quitting=exiting)
        self.model.stop_workers(exiting=exiting)

    # public API, should generally be left alone by subclasses

    @log(logger=logger)
    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """
        Called whenever a new plugin is instantiated elsewhere in the app, to keep an up to date list of possible data sources for use by this plugin

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app
        :type available_plugins: Dict[str, List[str]]
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

        Undo removes the last action and any resets before it, then replays from the
        last reset left. When none is left, the last reset it removed is replayed first,
        so undoing a figure's only plot clears the figure.

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
            # The reset an undone action started its figure with goes too, and is kept
            # here: with no reset left to replay from, it clears the figure first.
            removed_reset: Optional[Dict[str, Any]] = None
            try:
                last_item = self.tab_action_history[
                    next(reversed(self.tab_action_history))
                ]
            except StopIteration:
                pass
            else:
                while last_item.get("action") == RESET_ACTION:
                    removed_reset = self.tab_action_history.popitem()[1]
                    try:
                        last_item = self.tab_action_history[
                            next(reversed(self.tab_action_history))
                        ]
                    except StopIteration:
                        break
            # Replay from the last reset only. Everything before it was cleared off the
            # figure by that reset, so replaying it re-queried the database on the GUI
            # thread for nothing. It is kept, not truncated, so a later Undo past the
            # reset still has it to redraw from.
            entries = list(deepcopy(self.tab_action_history).items())
            resets = [
                position
                for position, (_, entry) in enumerate(entries)
                if entry.get("action") == RESET_ACTION
            ]
            start = max(resets, default=0)
            self.tab_action_history = OrderedDict(entries[:start])
            replayed = [entry for _, entry in entries[start:]]
            if not resets and removed_reset is not None:
                # Without it the figure would keep what was undone.
                replayed.insert(0, deepcopy(removed_reset))
            self.replay(replayed)
        self.update_tab_action_history.emit(
            self.__class__.__name__, self.tab_action_history
        )

    @log(logger=logger)
    @Slot()
    def discard_last_tab_action(self) -> None:
        """
        Drop the most recently recorded action without replaying anything.

        For an action that was refused and left the figure unchanged - a plot of what is
        already shown, say. Undoing it instead cleared the figure and replayed the whole
        history, which redrew it with the current selection rather than the recorded one.
        """
        try:
            self.tab_action_history.popitem()
        except KeyError:
            return
        self.update_tab_action_history.emit(
            self.__class__.__name__, self.tab_action_history
        )

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
