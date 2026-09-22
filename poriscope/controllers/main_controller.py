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
import inspect
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
    App-shell controller: owns the DataPluginController and every instantiated analysis-tab controller, and wires their signals together. A tab reaches a data plugin through MetaModel.call rather than through this class; what is wired here is the typed create/edit/delete trio onto the DataPluginController singleton, plus the display, progress and history signals. Also drives session/plugin-history persistence and restore.
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
        # history_lookup is a bound method, so it resolves self.plugin_history and
        # self.previous_plugin_history (set below) lazily at call time, not here
        self.data_plugin_controller = DataPluginController(
            {
                metaclass: self.main_model.get_plugin_classes(metaclass)
                for metaclass in self.main_model.get_available_plugins()
            },
            self.main_model.get_data_server_location(),
            self._lookup_historical_settings,
        )

        self.plugin_history: Dict[str, Any] = {}
        self.tab_action_history: Dict[str, Any] = {}

        # Both histories persist themselves on every change. Reset Session
        # empties them on its way to a clean workspace, and without this guard
        # that teardown would write an empty session over the file the user
        # expects Restore Session to read back.
        self._suppress_session_save: bool = False

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
        self.data_plugin_controller.update_available_plugins.connect(
            self.update_available_plugins
        )
        self.data_plugin_controller.update_plugin_history.connect(
            self.update_plugin_history
        )
        self.data_plugin_controller.add_text_to_display.connect(
            self.main_view.add_text_to_display
        )
        self.main_model.add_text_to_display.connect(self.main_view.add_text_to_display)

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
        self.main_view.abort_all_analysis.connect(self.handle_abort_all_analysis)
        self.main_view.reset_app_config.connect(self.reset_app_config)
        self.main_view.reset_session.connect(self.reset_session)
        self.main_view.request_analysis_tabs.connect(self.send_analysis_tabs)

    @log(logger=logger)
    @Slot()
    def handle_abort_all_analysis(self) -> None:
        """
        Stop running operations in every open analysis tab.

        Backs the Analysis -> Abort Analysis menu item, which previously emitted a
        signal that was connected to nothing and named a single hard-coded tab, so
        it never aborted anything. Each tab reports its own outcome on the display
        panel, so nothing is emitted here.
        """
        if not self.analysis_tabs:
            self.logger.info("Abort requested with no analysis tabs instantiated.")
            return
        for key, val in self.analysis_tabs.items():
            if val:
                val.handle_kill_all_workers(key)

    @log(logger=logger)
    @Slot()
    def handle_about_to_quit(self) -> None:
        # Flush tab state (e.g. Metadata/Protein subset filters) that only lives on the
        # view and is otherwise persisted lazily, only when some other plugin-history
        # event happens to fire. Without this, editing filters and quitting without
        # touching a data plugin or clicking Save Session would silently lose them.
        self.save_session()
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
        # The folder as well as its parent - see the same loop in `main_app`, which
        # runs at startup where this runs when the folder is changed.
        plugin_path = Path(user_plugin_loc).resolve()
        for importable in (plugin_path.parent, plugin_path):
            if str(importable) not in sys.path:
                sys.path.append(str(importable))
        self.refresh_available_plugins()

    @log(logger=logger)
    def refresh_available_plugins(self) -> None:
        """
        Re-scan the plugin directories and push the result to everyone holding it.

        The scan ran once, in ``MainModel``'s constructor, and its results were
        copied into three places at construction: this controller's data plugin
        controller, that controller's model, and the view's menus. Changing the
        user plugin folder therefore had no visible effect until the next launch.

        Instantiated plugins are untouched. ``self.data_plugins`` is the list of
        *instantiated* plugins rather than available classes, so it is not part
        of this refresh, and an existing instance keeps working through its own
        class reference regardless - see ``MainModel.refresh_available_plugins``
        for why a re-scan does not hand back the same class object it did
        before.
        """
        self.main_model.refresh_available_plugins()
        available_classes = {
            metaclass: self.main_model.get_plugin_classes(metaclass)
            for metaclass in self.main_model.get_available_plugins()
        }
        self.data_plugin_controller.set_available_plugins(available_classes)
        self.main_view.refresh_available_plugins(
            self.main_model.get_available_plugins()
        )

    @log(logger=logger)
    @Slot()
    def reset_app_config(self) -> None:
        """
        Restore the stored settings to their defaults and apply them live.

        The model persists the defaults; each is then routed back through the
        same path a manual edit takes, because rewriting ``config.json`` alone
        would leave the running application on the old values until restart -
        data plugins keep the previous parent folder, and the logger keeps the
        previous level. Finally the settings window is refreshed, which would
        otherwise go on displaying what the user had before.

        Saved sessions and log files are not affected.

        Resetting the user plugin folder re-scans it immediately, the same way
        editing it in Settings does: this routes through
        ``update_user_plugin_location`` below, which already calls
        ``refresh_available_plugins()`` at the end of its own path. The plugin
        menus reflect the default folder right away rather than waiting for
        the next launch.
        """
        defaults = self.main_model.reset_app_config()

        self.update_data_server_location(defaults["Parent Folder"])
        self.update_user_plugin_location(defaults["User Plugin Folder"])
        self.main_model.update_logging_level(defaults["Log Level"])

        self.main_view.set_data_server(defaults["Parent Folder"])
        self.main_view.set_user_plugin_location(defaults["User Plugin Folder"])
        self.main_view.set_logging_level(defaults["Log Level"])

    @log(logger=logger)
    @Slot()
    def reset_session(self) -> None:
        """
        Return the application to the state it has when launched from scratch.

        Deletes every instantiated data plugin, closes every analysis tab, drops
        both in-memory histories and returns to the landing page - so the user
        gets a clean workspace without quitting and starting the app again.

        The saved session files are deliberately left on disk, because that is
        what launching from scratch does: ``load_session`` reads them at startup
        and nothing applies them until the user chooses Restore Session. Leaving
        them means this is reversible - reset, then Restore, and the workspace
        comes back.

        Keeping them takes active effort. Both histories save themselves on every
        change, and deleting a plugin emits a history update per plugin, so the
        teardown below would otherwise write an empty session over the file
        before the user ever got the chance to restore it. ``_suppress_session_save``
        holds that off for the duration.

        Anything that refuses to delete is reported rather than passed over, so
        a partial clear is never announced as a complete one.

        The Settings page, if it was open, is removed too rather than kept
        around - a freshly launched application has never opened it either.
        Its widget is a singleton rather than something disposable, though, so
        ``close_settings_page()`` detaches it first; see that method for why.

        Running workers are stopped first, as they are on quit - deleting a
        plugin closes its resources, so a worker still running against one would
        be reading from a handle that has just been closed.

        The sidebar highlight, the sidebar layout, the status/log panel and the
        floating Help window are reset too. None of those follow from tearing
        down tabs and plugins on their own: the sidebar only ever gains a
        checked button, never loses one; an expanded sidebar stays expanded;
        the log panel only ever grows; and Help is a separate top-level window
        that closing tabs never touches. Left alone, the landing page would
        still show whichever section was last open, whichever sidebar layout
        was last chosen, everything logged before the reset, and a Help window
        a fresh launch would never have open.

        The plugin menus are re-scanned too, the same way changing the user
        plugin folder already does. ``populate_available_plugins()`` otherwise
        only ever runs once, in ``MainModel``'s constructor, so a plugin file
        dropped into the plugin folder mid-session would be invisible in the
        menus after a reset even though a genuine relaunch would pick it up.
        """
        self._suppress_session_save = True
        try:
            # Stop workers before deleting anything they run against. exiting=True
            # blocks until each thread actually finishes, which is needed here for
            # a stronger reason than on quit: the teardown below closes every
            # plugin's resources, and a worker still reading a file handle that
            # has just been closed is a use-after-close. The flag is named for the
            # exit path, but the semantics wanted are simply "wait for the thread".
            for tab_key, tab in list(self.analysis_tabs.items()):
                if tab:
                    tab.handle_kill_all_workers(tab_key, exiting=True)

            undeleted = self.data_plugin_controller.delete_all_plugins()

            self.analysis_tabs.clear()
            self.plugin_history.clear()
            self.tab_action_history.clear()
        finally:
            self._suppress_session_save = False

        # A walkthrough or milestone in progress makes switch_to_page refuse to
        # move, so the return to the landing page below would be silently ignored
        # and the user left on a page that has just been destroyed. A freshly
        # launched application has neither active.
        self.main_view.cancel_walkthrough()
        # Settings' widget is a singleton, not a disposable per-open instance
        # like an analysis tab's view, so it has to be detached from its page
        # wrapper before that wrapper is destroyed below - otherwise Qt would
        # destroy the singleton along with it. A freshly launched application
        # has never opened Settings, so this is a no-op if it wasn't open.
        self.main_view.close_settings_page()
        # Everything but the landing page is an analysis tab or Settings, both
        # of which a freshly launched application starts without.
        self.main_view.remove_pages_except(["MainView"])
        self.main_view.received_analysis_tabs.emit(self.analysis_tabs)
        self.main_view.switch_to_page("MainView")
        # switch_to_page only ever checks a sidebar button, it never unchecks
        # the one it replaces, so whichever section was open before the reset
        # would otherwise stay highlighted on a landing page with nothing open.
        self.main_view.clear_sidebar_highlight()
        # An expanded sidebar stays expanded otherwise - nothing about tearing
        # down tabs collapses it back to the default icon-only layout.
        self.main_view.reset_sidebar_layout()
        # A fresh launch starts with an empty panel; without this the reset
        # message would just be appended under everything logged before it.
        self.main_view.clear_display()
        # Help is a separate top-level window; closing tabs never touches it,
        # and a fresh launch never has it open.
        self.main_view.close_help_window()
        # populate_available_plugins() otherwise only ever runs once, at
        # startup, so a plugin file added since would stay invisible in the
        # menus here even though a genuine relaunch would pick it up.
        self.refresh_available_plugins()

        if undeleted:
            message = (
                f"Partial reset - {', '.join(undeleted)} could not be removed "
                "and are still loaded. Everything else was cleared."
            )
            self.logger.warning(message)
        else:
            message = "Session reset. Saved session files are untouched."
            self.logger.info(message)
        self.main_view.add_text_to_display(message, "MainController")

    @log(logger=logger)
    @Slot(str, str, object)
    def get_plugin_instance(
        self, metaclass: str, key: str, callback: Callable[[object], None]
    ) -> None:
        callback(self.data_plugin_controller.get_plugin_instance(metaclass, key))

    @log(logger=logger)
    def _lookup_historical_settings(
        self, metaclass: str, subclass: str
    ) -> Optional[Dict[str, Any]]:
        """
        Look up the most recently used settings for a plugin type, called directly by
        DataPluginController.validate_and_instantiate_plugin rather than over the signal
        bus, so the result comes back as a genuine return value instead of a signal
        relay that the caller reads back off an attribute on trust.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param subclass: The subclass of the plugin.
        :type subclass: str
        :return: The historical settings dict for this plugin type, or None if none exists.
        :rtype: Optional[Dict[str, Any]]
        """
        for val in self.plugin_history.values():
            if val.get("subclass") == subclass and val.get("metaclass") == metaclass:
                return val.get("settings")
        for val in self.previous_plugin_history.values():
            if val.get("subclass") == subclass and val.get("metaclass") == metaclass:
                return val.get("settings")
        return None

    @log(logger=logger)
    def _return_annotation(self, func: Callable) -> Any:
        """
        Resolve a callable's declared return type, preferring evaluated annotations over their string spellings and reporting inspect.Signature.empty if it has none that can be read.

        :param func: The callable to introspect.
        :type func: Callable
        :return: The resolved return annotation, or inspect.Signature.empty if it cannot be determined.
        :rtype: Any
        """
        try:
            return inspect.signature(func, eval_str=True).return_annotation
        except (TypeError, ValueError, NameError, AttributeError) as e:
            self.logger.debug(
                f"Could not evaluate the annotations of {getattr(func, '__name__', func)}, "
                f"falling back to their unevaluated form: {repr(e)}"
            )
        try:
            return inspect.signature(func).return_annotation
        except (TypeError, ValueError):
            return inspect.Signature.empty

    @log(logger=logger)
    @Slot(str, list)
    def update_available_plugins(
        self, metaclass: str, available_plugins: List[str]
    ) -> None:
        self.logger.debug(
            f"Available {metaclass} plugins updates to {available_plugins}"
        )
        self.data_plugins[metaclass] = available_plugins
        instances = self.data_plugin_controller.get_plugin_instances()
        for val in self.analysis_tabs.values():
            if val:
                # Instances BEFORE names, and the order is load-bearing.
                # Handing a tab the names populates its comboboxes, and populating a
                # combobox fires a selection change *synchronously* - which is when the
                # tab asks the selected loader for its columns. Push the names first and
                # that call finds an empty instance map, so the tab reports a plugin it
                # is displaying as not registered. Both come from the same registry, so
                # they cannot disagree about what exists; only the order can be wrong.
                val.set_plugin_instances(instances)
                val.update_available_plugins(self.data_plugins)

    @log(logger=logger)
    @Slot(dict, str)
    def update_plugin_history(
        self, history: Optional[Dict[str, Any]], delete_key: Optional[str]
    ) -> None:
        """
        Record a plugin being added, removed or renamed, then persist the session.

        The two arguments form a small truth table. `history` alone adds or
        replaces an entry; `delete_key` alone removes one; both together are a
        rename, where the entry named by `delete_key` becomes the one `history`
        describes. Neither is not an error - it still re-syncs and saves, which
        is how a change to a tab's own state reaches the session file without any
        plugin having changed.

        :param history: The plugin's saved state, or None when only deleting.
        :type history: Optional[Dict[str, Any]]
        :param delete_key: The key being removed, or renamed away from, or None.
        :type delete_key: Optional[str]
        """
        if history and not delete_key:
            self.plugin_history[history.pop("key")] = history
        elif not history and delete_key:
            self.plugin_history.pop(delete_key, None)
        elif history and delete_key:
            self.plugin_history = self._renamed_history(delete_key, history)

        self._sync_tab_session_state_into_history()
        if not self._suppress_session_save:
            self.main_model.save_session(self.plugin_history)

    @log(logger=logger)
    def _renamed_history(
        self, delete_key: str, history: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Rebuild the plugin history with one entry renamed, keeping its position.

        Rebuilt rather than popped and reinserted, because a plugin's place in
        the history is its place in the session file and in everything restored
        from it. Popping the old key and adding the new one would move the
        renamed plugin to the end, so a rename would silently reorder the user's
        workspace.

        :param delete_key: The key being renamed away from.
        :type delete_key: str
        :param history: The renamed plugin's state, carrying its new key.
        :type history: Dict[str, Any]
        :return: A new history with the entry replaced where the old one sat.
        :rtype: Dict[str, Any]
        """
        renamed: Dict[str, Any] = {}
        for key, val in self.plugin_history.items():
            if key == delete_key:
                renamed[history.pop("key")] = history
            else:
                renamed[key] = val
        return renamed

    @log(logger=logger)
    def _sync_tab_session_state_into_history(self) -> None:
        """
        Snapshot each open analysis tab's extra session state into its plugin history entry.

        A tab may keep state beyond what MainController already tracks (e.g. Metadata
        and Protein build a filter list entirely on their own view) via
        ``MetaController.get_session_state()``, which defaults to returning nothing.
        This merges whatever a tab does return into its corresponding history entry so
        it round-trips through session save/load along with the rest of the tab's state.
        """
        for subclass, tab in self.analysis_tabs.items():
            if tab is None:
                continue
            entry = self.plugin_history.get(subclass)
            if entry is None:
                continue
            state = tab.get_session_state()
            if state:
                entry.update(copy.deepcopy(state))

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
        if not self._suppress_session_save:
            self.main_model.save_tab_actions(self.tab_action_history)

    @log(logger=logger)
    @Slot(str)
    def instantiate_analysis_tab(self, subclass: str) -> None:
        """
        Instantiate a new analysis-tab controller of the given subclass and wire it into the app
        (add its page, sync the sidebar highlight to it, connect its signals, register it in
        plugin history), or reuse the existing instance if a tab of that type has already been
        instantiated.

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

            view_name = new_analysis_tab.view.__class__.__name__
            self.main_view.add_page(view_name, self.analysis_tabs[subclass].view)
            # The button-click handlers that normally open a tab
            # (on_raw_data_view_click and friends) sync the sidebar highlight
            # themselves alongside emitting the signal that reaches here, so
            # this looks redundant for that path - but callers that reach this
            # method directly, like load_session restoring a saved session,
            # never go through a click handler at all, and the sidebar was
            # left showing nothing (or whatever was highlighted before) with no
            # tab actually behind it.
            self.main_view.sync_sidebar_highlight(view_name)

            # Connect other necessary signals and update plugins
            self.analysis_tabs[subclass].create_plugin.connect(
                self.data_plugin_controller.validate_and_instantiate_plugin
            )
            # Straight to the singleton, as create_plugin already was. There is no
            # return value to carry back - the old bus passed "", () as its return
            # function for both of these - and DataPluginController is constructed
            # once and never reassigned, so there is nothing for a relay to resolve.
            self.analysis_tabs[subclass].edit_plugin.connect(
                self.data_plugin_controller.edit_plugin_settings
            )
            self.analysis_tabs[subclass].delete_plugin.connect(
                self.data_plugin_controller.delete_plugin
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
            # Instances before names, for the reason given in
            # update_available_plugins. A tab created after the plugins already exist -
            # which is what restoring a session does - would otherwise get a populated
            # combobox and an empty instance map.
            self.analysis_tabs[subclass].set_plugin_instances(
                self.data_plugin_controller.get_plugin_instances()
            )
            self.analysis_tabs[subclass].update_available_plugins(self.data_plugins)
            self.logger.debug(f"New analysis tab of type {subclass} added")
            self.update_plugin_history(history, "")

    @log(logger=logger)
    @Slot(str)
    def save_session(self, save_file: Optional[Union[str, Path]] = None) -> None:
        self._sync_tab_session_state_into_history()
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
        """
        Load a saved session, replacing whatever is currently instantiated.

        Applying the loaded plugin history on top of an already-populated
        workspace collided with anything the current session already held
        under the same key or name - a plugin key already registered, a
        named filter already added - and surfaced as an "already exists"
        error for state the user never meant to keep. ``reset_session()``
        clears the workspace first, the same as it does for its own menu
        action, so a load always starts from nothing regardless of what was
        open before it. Both "Load Session" (a chosen file) and "Restore
        Session" (``file_name=None``, the last saved session) route through
        this same method.

        A message naming what was loaded is left on the status/log panel,
        since ``reset_session()`` above already leaves one there of its own -
        without this, the user would see that the workspace was cleared but
        not what, if anything, replaced it.

        :param file_name: Path to the session file to load, or None to
            restore the last saved session.
        :type file_name: Optional[Union[str, Path]]
        """
        self.logger.debug(f"Loading session from file {file_name}")
        plugin_history = self.main_model.load_session(file_name)
        if plugin_history is None:
            self.logger.info(f"Unable to recover plugin history from {file_name}")
            return
        self.reset_session()
        self.plugin_history = plugin_history
        self.main_model.save_session(self.plugin_history)

        # Counted before the loop, which emits update_plugin_history and so can
        # change the dict it is iterating a copy of.
        entries = len(self.plugin_history)
        unrestored: List[str] = []
        for key, plugin in list(self.plugin_history.items()):
            metaclass = plugin["metaclass"]
            subclass = plugin["subclass"]
            if metaclass == "MetaController":
                # reset_session() above has already cleared every tab, so this
                # is always a fresh instantiation - never one already open
                # whose live state should be left alone.
                try:
                    self.instantiate_analysis_tab(subclass)
                except Exception as e:
                    self.logger.error(
                        f"Unable to restore Analysis Tab {key} of type {subclass} due to {str(e)}"
                    )
                    unrestored.append(key)
                    continue
                tab = self.analysis_tabs.get(subclass)
                if tab is not None:
                    tab.restore_session_state(plugin)
            else:
                settings = plugin.get("settings")
                try:
                    # No dialog can appear here - restore supplies both settings
                    # and key - so False means a reported failure, never a
                    # cancellation.
                    if not self.data_plugin_controller.validate_and_instantiate_plugin(
                        metaclass=metaclass,
                        subclass=subclass,
                        settings=settings,
                        key=key,
                    ):
                        unrestored.append(key)
                except Exception as e:
                    self.logger.error(
                        f"Unable to restore plugin {key} of type {metaclass}/{subclass} due to {str(e)}"
                    )
                    unrestored.append(key)

        # Write the restored workspace back out before announcing it. Restoring a
        # tab is two steps - instantiate_analysis_tab, then restore_session_state -
        # and only the first of them refreshes plugin_history, via the
        # update_plugin_history call it ends on. Each tab's entry is therefore
        # snapshotted while its filter list is still empty, and is only corrected by
        # the sync that the *next* tab's instantiation happens to trigger. The last
        # tab restored has no next tab, so the session saved during this loop
        # recorded it with no subset filters at all, and the restore after that one
        # lost them: Metadata kept its filters and Protein did not, purely because
        # Protein was opened second and so is restored second.
        self._sync_tab_session_state_into_history()
        self.main_model.save_session(self.plugin_history)

        if file_name:
            message = f"Loaded session from {file_name}."
        else:
            message = "Restored last saved session."
        if unrestored:
            # Each failure has already been reported individually, but those
            # messages scroll and several of them are usually consequences of one
            # or two root causes - a parent that never instantiated takes its
            # dependents down with it. Without this the panel signed off with an
            # unqualified success line under ten error messages.
            message += (
                f" {len(unrestored)} of {entries} entries could not be restored "
                f"({', '.join(unrestored)}); see the messages above."
            )
        self.main_view.add_text_to_display(message, "MainController")

    @log(logger=logger)
    @Slot()
    def send_analysis_tabs(self) -> None:
        """Send the list of instantiated analysis tabs to MainView."""
        self.logger.debug("Sending instantiated analysis tabs to MainView.")

        if not self.analysis_tabs:
            # Normal at startup and after a session reset, so not a warning:
            # QtHandler promotes WARNING to a modal dialog.
            self.logger.debug("No instantiated analysis tabs in MainController.")

        # Emit the correct signal with the current analysis tabs
        self.main_view.received_analysis_tabs.emit(self.analysis_tabs)
