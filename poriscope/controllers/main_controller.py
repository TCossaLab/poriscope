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
import typing
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from PySide6.QtCore import QObject, Qt, Slot

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
        plugin_path = Path(user_plugin_loc).resolve()
        parent_path = plugin_path.parent
        if str(parent_path) not in sys.path:
            sys.path.append(str(parent_path))
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
    def _binding_error(self, func: Callable, args: tuple) -> Optional[str]:
        """
        Report why func would refuse args as its positional arguments, without calling it. Arity is checked here, up front at the dispatch boundary, so that a TypeError raised from inside a callee is never mistaken for a call-site mismatch and the callee is never invoked twice. The reason is taken from Signature.bind itself rather than reconstructed, so the caller can log which argument is missing or surplus rather than leaving the reader to diff a signature against an argument list. Callables that cannot be introspected at all (C-implemented, or otherwise opaque) report no error, so the dispatcher falls through and calls them rather than refusing to.

        :param func: The callable whose signature is to be tested.
        :type func: Callable
        :param args: Positional arguments to test against the signature.
        :type args: tuple
        :return: None if the call would bind or func cannot be introspected, otherwise a description of the mismatch.
        :rtype: Optional[str]
        """
        try:
            signature = inspect.signature(func)
        except (TypeError, ValueError):
            return None
        try:
            signature.bind(*args)
        except TypeError as e:
            return f"{signature} cannot accept arguments {args}: {e}"
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
    def _unpack_result(self, func: Callable, result: Any) -> tuple:
        """
        Render the result of a dispatched call as the leading positional arguments for its callback.

        The signal protocol splats a tuple return across the callback's parameters and passes anything else as a single argument. Which of those applies is decided here by func's *declared* return type rather than by inspecting the value, because the two are indistinguishable at runtime: a method returning a pair and a method returning two values produce the same object, and a method with an Optional return type that returns None is not returning an empty argument list. Every function under poriscope/ is annotated and none of them defer annotation evaluation, so the declared type is always available and is an exact discriminator.

        A callee that declares a tuple return and produces something else has broken its own contract; that is logged and the value is passed as a single argument rather than coerced, since tuple() would silently shred a string and raise on None.

        Annotations are resolved with eval_str=True so that a plugin written with `from __future__ import annotations` - which no module under poriscope/ uses, but a user plugin dropped into the user plugin folder may - is read as the type it declares rather than as the string spelling of it. A plugin whose annotations cannot be resolved at all falls back to the unevaluated ones, and one with no usable return type is treated as returning a single value.

        :param func: The callable whose result is being unpacked, consulted for its return annotation.
        :type func: Callable
        :param result: The value func returned.
        :type result: Any
        :return: The positional arguments representing that result.
        :rtype: tuple
        """
        annotation = self._return_annotation(func)
        if annotation is tuple or typing.get_origin(annotation) is tuple:
            if isinstance(result, tuple):
                return result
            self.logger.error(
                f"{getattr(func, '__name__', func)} declares a tuple return but returned "
                f"{type(result).__name__}; passing it as a single argument"
            )
        return (result,)

    @log(logger=logger)
    def _call_return_function(
        self,
        return_function: Callable,
        called_function: Callable,
        result: Any,
        ret_args: tuple,
        context: str,
    ) -> None:
        """
        Call return_function with the result of a dispatched call followed by ret_args. The result is rendered into positional arguments by _unpack_result, and the whole argument list is checked against return_function's signature before the call, so a mismatch is reported once and never guessed at. Exceptions raised by return_function itself are not caught here.

        :param return_function: The callback to invoke.
        :type return_function: Callable
        :param called_function: The callable whose result is being relayed, consulted for its return annotation.
        :type called_function: Callable
        :param result: The value returned by the dispatched call.
        :type result: Any
        :param ret_args: Additional positional arguments appended after the result.
        :type ret_args: tuple
        :param context: Description of the originating call, used only in the mismatch log message.
        :type context: str
        """
        call_args = self._unpack_result(called_function, result) + ret_args
        problem = self._binding_error(return_function, call_args)
        if problem is not None:
            self.logger.error(
                f"Not calling return function "
                f"{getattr(return_function, '__name__', return_function)}, which was to "
                f"receive the result of {context}: {problem}"
            )
            return
        return_function(*call_args)

    @log(logger=logger)
    def _dispatch_to(
        self,
        target: object,
        target_label: str,
        call_function: str,
        call_args: tuple,
        return_function: Optional[Callable],
        ret_args: tuple,
    ) -> None:
        """
        Look call_function up on target, call it with call_args, and relay its result to return_function. This is the whole of the signal-bus dispatch mechanism; handle_global_signal and handle_data_plugin_controller_signal differ only in what they resolve as the target, and share this body so that the two paths cannot drift apart in their guards or their diagnostics.

        call_args and ret_args are taken to be tuples of positional arguments, as the signals' own signatures declare; nothing here guesses at a bare value passed in their place. Arity is checked before the call (see _binding_error), so a call that could not bind is reported and never attempted, and a TypeError raised from inside call_function is reported as such rather than being mistaken for a call-site mismatch - call_function is called at most once. The result is splatted or passed whole to return_function according to call_function's declared return type (see _unpack_result). Every failure is logged and swallowed rather than raised, since the callers are Qt slots.

        :param target: The object to look call_function up on.
        :type target: object
        :param target_label: Human-readable identifier for target, used in log messages.
        :type target_label: str
        :param call_function: Name of the method to call on target.
        :type call_function: str
        :param call_args: Positional arguments to call_function.
        :type call_args: tuple
        :param return_function: Optional callable to invoke with the result of call_function.
        :type return_function: Optional[Callable]
        :param ret_args: Additional positional arguments appended after the result when calling return_function.
        :type ret_args: tuple
        """
        func = getattr(target, call_function, None)
        if func is None:
            self.logger.error(f"No member {target_label}.{call_function} found")
            return
        if not callable(func):
            self.logger.error(f"{target_label}.{call_function} is not callable")
            return
        problem = self._binding_error(func, call_args)
        if problem is not None:
            self.logger.error(f"Not calling {target_label}.{call_function}: {problem}")
            return
        try:
            result = func(*call_args)
        except Exception:
            self.logger.exception(
                f"{target_label}.{call_function} raised while executing with arguments {call_args}"
            )
            return
        self.logger.debug(f"{target_label}.{call_function} returned {result}")
        if return_function is not None:
            try:
                self._call_return_function(
                    return_function,
                    func,
                    result,
                    ret_args,
                    f"{target_label}.{call_function}",
                )
            except Exception:
                self.logger.exception(
                    f"Return function "
                    f"{getattr(return_function, '__name__', return_function)} raised "
                    f"while handling the result of {target_label}.{call_function}"
                )

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
        Resolve (metaclass, subclass_key) to a live data plugin instance and dispatch call_function to it, so a tab or plugin can invoke a method on another plugin without holding a direct reference to it. Resolution and the call itself both happen inside the error guard, because looking up an unregistered metaclass raises rather than returning None, and this is a Qt slot, which must not let an exception escape into the C++ caller. The dispatch itself is _dispatch_to, shared with handle_data_plugin_controller_signal.

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
        target_label = f"{metaclass}/{subclass_key}"
        try:
            instance = self.data_plugin_controller.get_plugin_instance(
                metaclass, subclass_key
            )
            if instance is None:
                self.logger.error(
                    f"No plugin instance found for {target_label}, unable to call {call_function}"
                )
                return
            self._dispatch_to(
                instance,
                target_label,
                call_function,
                call_args,
                return_function,
                ret_args,
            )
        except Exception:
            self.logger.exception(
                f"Unexpected error handling global signal for {target_label}.{call_function}"
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
        Same dispatch mechanism as handle_global_signal, and literally the same code path (see _dispatch_to), except that call_function is looked up on the DataPluginController itself rather than on a resolved plugin instance. metaclass and subclass_key are accepted for signal-signature parity with handle_global_signal and are logged, but are not used to resolve a target here and so do not appear in this path's error messages. Used when a tab needs to invoke a DataPluginController method (e.g. to instantiate or edit a plugin) rather than a method on an existing plugin instance.

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
        target_label = "DataPluginController"
        try:
            self._dispatch_to(
                self.data_plugin_controller,
                target_label,
                call_function,
                call_args,
                return_function,
                ret_args,
            )
        except Exception:
            self.logger.exception(
                f"Unexpected error handling data plugin controller signal for {target_label}.{call_function}"
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
        self._sync_tab_session_state_into_history()
        if not self._suppress_session_save:
            self.main_model.save_session(self.plugin_history)

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
            # DirectConnection is required, not cosmetic: callers on the other end of
            # this bus (e.g. RawDataView._apply_filter) emit global_signal/
            # data_plugin_controller_signal and then synchronously read back a result
            # via a return_function_name callback on the very next statement. A queued
            # connection would silently degrade that read to stale/None data with no
            # error and no log line.
            self.analysis_tabs[subclass].global_signal.connect(
                self.handle_global_signal, type=Qt.ConnectionType.DirectConnection
            )
            self.analysis_tabs[subclass].create_plugin.connect(
                self.data_plugin_controller.validate_and_instantiate_plugin
            )
            self.analysis_tabs[subclass].data_plugin_controller_signal.connect(
                self.handle_data_plugin_controller_signal,
                type=Qt.ConnectionType.DirectConnection,
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
                    continue
                tab = self.analysis_tabs.get(subclass)
                if tab is not None:
                    tab.restore_session_state(plugin)
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
            # Normal at startup and after a session reset, so not a warning:
            # QtHandler promotes WARNING to a modal dialog.
            self.logger.debug("No instantiated analysis tabs in MainController.")

        # Emit the correct signal with the current analysis tabs
        self.main_view.received_analysis_tabs.emit(self.analysis_tabs)
