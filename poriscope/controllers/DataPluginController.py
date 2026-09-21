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
import logging
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple

from PySide6.QtCore import QObject, Signal, Slot

from poriscope.models.DataPluginModel import DataPluginModel
from poriscope.utils.LogDecorator import log
from poriscope.views.DataPluginView import DataPluginView


class DataPluginController(QObject):
    """
    Base controller class that manages data plugins
    """

    update_available_plugins = Signal(str, list)
    update_plugin_history = Signal(dict, str)
    add_text_to_display = Signal(str, str)
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        available_plugin_classes: Mapping[str, Mapping[str, type]],
        data_server: str,
        history_lookup: Callable[[str, str], Optional[Dict[str, Any]]],
    ) -> None:
        super().__init__()
        self.view = DataPluginView()
        self.model = DataPluginModel(available_plugin_classes)
        self.data_server = data_server
        self.plugin_manager = None
        self._history_lookup = history_lookup

    @log(logger=logger)
    @Slot(str, str)
    def edit_plugin_settings(self, metaclass: str, key: str) -> None:
        """
        Retrieve plugin details and allow editing of the plugin's settings in the view.
        """
        plugin = self.model.get_plugin_instance(metaclass, key)
        if plugin:
            try:
                settings = plugin.get_raw_settings()
            except AttributeError:
                self.logger.warning(f"Unable to edit plugin {key}")
            else:
                self.edit_plugin(metaclass, key, settings)

    def edit_plugin(self, metaclass: str, key: str, settings: dict) -> None:
        """
        Edit and apply settings for an existing plugin.

        The shape of the edit is: show the dialog, then take one of three routes -
        delete, cancel, or apply - where applying may also rename. Every route
        past the dialog has already unregistered the plugin from its parents, so
        each one either completes or calls `_report_and_restore` to put them back.

        The helpers return False to mean "give up, the user has been told", which
        keeps the decision to stop here rather than scattered through them.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The current key of the plugin instance being edited.
        :type key: str
        :param settings: The plugin's current settings dict, used to populate the edit dialog.
        :type settings: dict
        """
        app_settings = copy.deepcopy(settings)
        instance = self.model.get_plugin_instance(metaclass, key)
        if instance is None:
            self.logger.warning(
                f"Unable to edit plugin {key}: no such instance under {metaclass}"
            )
            return

        self._coerce_plugin_references_to_keys(app_settings)

        new_settings, new_key, delete_requested = self.view.get_user_settings(
            app_settings,
            key,
            self.data_server,
            editable=True,
            show_delete=True,
            editable_source_plugins=False,
            source_plugins=self.model.get_available_metaclasses(),
        )

        parents = instance.get_parents()
        dependents = instance.get_dependents()

        if delete_requested:
            self._unregister_parent_dependent_links(metaclass, key, parents)
            self._complete_requested_deletion(
                metaclass, key, instance, parents, dependents
            )
            return

        if new_settings is None or new_key is None:
            # cancelled, or dismissed with Esc or the window close button, both
            # of which reach QDialog.reject() without running a button handler
            return

        self._unregister_parent_dependent_links(metaclass, key, parents)
        old_key = instance.get_key()
        settings, key = new_settings, new_key

        if key != old_key:
            if not self._rename_plugin(
                metaclass, key, old_key, instance, parents, dependents, settings
            ):
                return

        if not self._resolve_plugin_references(
            app_settings, metaclass, key, instance, parents
        ):
            return

        self._apply_edited_settings(
            app_settings, metaclass, key, instance, parents, settings
        )

    @log(logger=logger)
    def _coerce_plugin_references_to_keys(self, app_settings: dict) -> None:
        """
        Turn each plugin-typed setting into a name the dialog can offer as a choice.

        A setting whose key is a metaclass holds a live plugin object, which no
        dialog can render. Retyping it as `str` and listing the instantiated keys
        as `Options` is what makes it a dropdown; `_resolve_plugin_references`
        turns the chosen name back into the object afterwards.

        Mutates `app_settings` in place, which is why the caller deep-copies the
        user's settings before handing them over.

        :param app_settings: The working copy of the plugin's settings.
        :type app_settings: dict
        """
        for settings_key in app_settings:
            if settings_key in self.model.get_available_metaclasses():
                app_settings[settings_key]["Type"] = str
                app_settings[settings_key][
                    "Options"
                ] = self.model.get_instantiated_plugins_list()[settings_key]

    @log(logger=logger)
    def _complete_requested_deletion(
        self,
        metaclass: str,
        key: str,
        instance: Any,
        parents: Set[Tuple[str, str]],
        dependents: Set[Tuple[str, str]],
    ) -> None:
        """
        Delete the plugin the user asked to remove, unless something still depends on it.

        A plugin with dependents cannot go: they would be left pointing at
        nothing. That is the user's to resolve, so it is reported rather than
        forced, and the parent links this edit already undid are put back.

        The history entry emitted on success is deliberately empty - the second
        argument is the key being removed, and an empty dict is what records a
        deletion rather than an edit.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The key of the plugin being deleted.
        :type key: str
        :param instance: The live plugin instance.
        :type instance: Any
        :param parents: The (metaclass, key) pairs of the plugin's parents.
        :type parents: Set[Tuple[str, str]]
        :param dependents: The (metaclass, key) pairs that depend on this plugin.
        :type dependents: Set[Tuple[str, str]]
        """
        if not dependents:
            self.model.unregister_plugin(metaclass, key)
            self.update_available_plugins.emit(
                metaclass, self.model.get_instantiated_plugins_list()[metaclass]
            )
            self.update_plugin_history.emit({}, key)
            return

        dependent_keys = [dependent[1] for dependent in dependents]
        self._report_and_restore(
            self.logger.info,
            f"Unable to delete {key} since it has dependents {dependent_keys}",
            metaclass,
            instance.get_key(),
            parents,
        )

    @log(logger=logger)
    def _rename_plugin(
        self,
        metaclass: str,
        key: str,
        old_key: str,
        instance: Any,
        parents: Set[Tuple[str, str]],
        dependents: Set[Tuple[str, str]],
        settings: dict,
    ) -> bool:
        """
        Give the plugin its new key, refusing a name that is already taken.

        Plugin names are unique across *every* metaclass, not just within one, so
        the collision check walks the whole instantiated list.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The new key requested by the user.
        :type key: str
        :param old_key: The key the plugin had before this edit.
        :type old_key: str
        :param instance: The live plugin instance.
        :type instance: Any
        :param parents: The (metaclass, key) pairs of the plugin's parents.
        :type parents: Set[Tuple[str, str]]
        :param dependents: The (metaclass, key) pairs that depend on this plugin.
        :type dependents: Set[Tuple[str, str]]
        :param settings: The settings to record against the renamed plugin.
        :type settings: dict
        :return: True if the rename completed, False if the caller should give up.
        :rtype: bool
        """
        for meta, keys in self.model.get_instantiated_plugins_list().items():
            if key in keys:
                self._report_and_restore(
                    self.logger.warning,
                    f"Cannot rename plugin to '{key}' because it already exists under metaclass '{meta}'.",
                    metaclass,
                    instance.get_key(),
                    parents,
                    display_message=f"Plugin name '{key}' already exists under metaclass '{meta}'. Please choose a different name.",
                )
                return False

        self._update_dependents_after_rename(metaclass, old_key, key, dependents)

        try:
            instance.set_key(key)
        except Exception as e:
            self._report_and_restore(
                self.logger.exception,
                f"Unable to edit plugin {key} of type {metaclass} : {str(e)}",
                metaclass,
                instance.get_key(),
                parents,
            )
            return False

        self.model.update_plugin_key(metaclass, key, old_key)
        self.update_available_plugins.emit(
            metaclass, self.model.get_instantiated_plugins_list()[metaclass]
        )
        self.add_text_to_display.emit(
            instance.report_channel_status(channel=None, init=True), key
        )
        self.update_plugin_history.emit(
            {
                "key": key,
                "metaclass": metaclass,
                "subclass": instance.__class__.__name__,
                "settings": settings,
            },
            old_key,
        )
        return True

    @log(logger=logger)
    def _update_dependents_after_rename(
        self,
        metaclass: str,
        old_key: str,
        key: str,
        dependents: Set[Tuple[str, str]],
    ) -> None:
        """
        Point every dependent at the plugin's new name, reporting any that cannot follow.

        Each dependent is handled on its own, and a failure on one neither stops
        the rest nor abandons the rename - the plugin is renamed either way, so
        giving up halfway would leave more dependents stale, not fewer.

        :param metaclass: The metaclass of the renamed plugin.
        :type metaclass: str
        :param old_key: The key the plugin had before this edit.
        :type old_key: str
        :param key: The plugin's new key.
        :type key: str
        :param dependents: The (metaclass, key) pairs that depend on this plugin.
        :type dependents: Set[Tuple[str, str]]
        :raises RuntimeError: if a registered dependent has no live plugin
            instance. Caught by the per-dependent handler below and reported to
            the user; it never propagates to the caller.
        """
        for dmetaclass, dkey in dependents:
            try:
                dinstance = self.model.get_plugin_instance(dmetaclass, dkey)
                if dinstance is None:
                    raise RuntimeError(
                        f"No plugin instance found for {dmetaclass}:{dkey}"
                    )
                dinstance.unregister_parent(metaclass, old_key)
                dinstance.register_parent(metaclass, key)
                dhistory: Dict[str, Any] = {}
                dhistory["key"] = dinstance.get_key()
                dhistory["metaclass"] = dmetaclass
                dhistory["subclass"] = dinstance.__class__.__name__
                # Update the dependent itself first, then snapshot it into
                # history. get_raw_settings() returns a copy, so writing
                # through what it hands back would update history while
                # leaving the plugin's own Value and Options untouched.
                dinstance.update_raw_settings(metaclass, key)
                dinstance.replace_raw_settings_option(metaclass, old_key, key)
                dhistory["settings"] = dinstance.get_raw_settings()
                self.update_plugin_history.emit(dhistory, "")
            except Exception as e:
                self.logger.error(
                    f"Unable to update dependent {dkey} of type {dmetaclass} after renaming {old_key} to {key}: {str(e)}"
                )
                self.add_text_to_display.emit(
                    f"Unable to update dependent {dkey} of type {dmetaclass} after renaming {old_key} to {key}: {str(e)}",
                    self.__class__.__name__,
                )

    @log(logger=logger)
    def _resolve_plugin_references(
        self,
        app_settings: dict,
        metaclass: str,
        key: str,
        instance: Any,
        parents: Set[Tuple[str, str]],
    ) -> bool:
        """
        Turn the plugin names chosen in the dialog back into live plugin objects.

        The inverse of `_coerce_plugin_references_to_keys`: `Type` and `Options`
        go back to None, because the plugin itself expects an object rather than
        a rendered choice.

        :param app_settings: The working copy of the plugin's settings.
        :type app_settings: dict
        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The key of the plugin being edited.
        :type key: str
        :param instance: The live plugin instance.
        :type instance: Any
        :param parents: The (metaclass, key) pairs of the plugin's parents.
        :type parents: Set[Tuple[str, str]]
        :return: True if every reference resolved, False if the caller should give up.
        :rtype: bool
        """
        try:
            for settings_key, val in app_settings.items():
                if settings_key in self.model.get_available_metaclasses():
                    app_settings[settings_key]["Value"] = (
                        self.model.get_plugin_instance(settings_key, val["Value"])
                    )
                    app_settings[settings_key]["Type"] = None
                    app_settings[settings_key]["Options"] = None
        except Exception as e:
            self._report_and_restore(
                self.logger.exception,
                f"Unable to resolve plugin references for {key} of type {metaclass} : {str(e)}",
                metaclass,
                instance.get_key(),
                parents,
            )
            return False
        return True

    @log(logger=logger)
    def _apply_edited_settings(
        self,
        app_settings: dict,
        metaclass: str,
        key: str,
        instance: Any,
        parents: Set[Tuple[str, str]],
        settings: dict,
    ) -> None:
        """
        Hand the resolved settings to the plugin, which is what makes the edit real.

        The last step, and the only one that touches the plugin's own state, so a
        failure here is the one that most needs the parent links put back.

        :param app_settings: The settings with plugin references resolved to objects.
        :type app_settings: dict
        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The key of the plugin being edited.
        :type key: str
        :param instance: The live plugin instance.
        :type instance: Any
        :param parents: The (metaclass, key) pairs of the plugin's parents.
        :type parents: Set[Tuple[str, str]]
        :param settings: The raw settings to record in history, references unresolved.
        :type settings: dict
        """
        try:
            instance.apply_settings(app_settings)
        except Exception as e:
            self._report_and_restore(
                self.logger.info,
                f"Unable to apply settings to plugin {key} of type {metaclass}.{instance.__class__.__name__}: {str(e)}",
                metaclass,
                instance.get_key(),
                parents,
            )
            return

        self.update_plugin_history.emit(
            {
                "key": key,
                "metaclass": metaclass,
                "subclass": instance.__class__.__name__,
                "settings": settings,
            },
            "",
        )
        self.add_text_to_display.emit(
            f"Settings updated successfully for {key}",
            self.__class__.__name__,
        )

    @log(logger=logger)
    def _report_and_restore(
        self,
        report: Callable[[str], None],
        message: str,
        metaclass: str,
        key: str,
        parents: Set[Tuple[str, str]],
        display_message: Optional[str] = None,
    ) -> None:
        """
        Report an abandoned edit and put back the parent links it already undid.

        `edit_plugin` unregisters the plugin from its parents before it starts,
        so every path that gives up afterwards has to restore them. There were
        five such paths, each spelling out the same log, emit and restore by
        hand, and one of them had no test at all - which is precisely how a
        sixth abort gets added without the restore. Gathering them here is what
        makes that impossible rather than merely unlikely.

        The severity is passed in as the bound logger method rather than as a
        level, because it varies and the distinction is meaningful: a rename
        collision is the user's to correct and warns, a failure inside
        `set_key` or reference resolution is a genuine fault and wants
        `logger.exception`'s traceback, and being unable to delete a plugin that
        still has dependents is routine and merely informs. Passing the method
        keeps `exception` meaning exactly what it means everywhere else.

        Control flow stays at the call site. This always returns normally, so
        the caller's own `return` is still what ends the edit - which is why the
        one caller that must *not* stop, the blocked delete, simply does not
        write one.

        :param report: the logger method to report through, which carries the severity
        :type report: Callable[[str], None]
        :param message: what to write to the log
        :type message: str
        :param metaclass: the metaclass of the plugin whose links are restored
        :type metaclass: str
        :param key: the key of the plugin whose links are restored
        :type key: str
        :param parents: the (metaclass, key) pairs of the plugin's parents
        :type parents: Set[Tuple[str, str]]
        :param display_message: what to show on the status panel, when it should
            differ from the logged message
        :type display_message: Optional[str]
        """
        report(message)
        self.add_text_to_display.emit(
            message if display_message is None else display_message,
            self.__class__.__name__,
        )
        self._restore_parent_dependent_links(metaclass, key, parents)

    @log(logger=logger)
    def _unregister_parent_dependent_links(
        self, metaclass: str, key: str, parents: Set[Tuple[str, str]]
    ) -> None:
        """
        Drop this plugin from the dependent list of each of its parents.

        Done upfront in `edit_plugin` so that the edit sees an accurate
        dependency graph; `_restore_parent_dependent_links` undoes it on every
        path that aborts before `apply_settings` re-establishes the link.

        :param metaclass: The metaclass of the plugin being unregistered.
        :type metaclass: str
        :param key: The key of the plugin being unregistered.
        :type key: str
        :param parents: The (metaclass, key) pairs of the plugin's parents.
        :type parents: Set[Tuple[str, str]]
        """
        for pmetaclass, pkey in parents:
            pinstance = self.model.get_plugin_instance(pmetaclass, pkey)
            if pinstance:
                pinstance.unregister_dependent(metaclass, key)

    @log(logger=logger)
    def _restore_parent_dependent_links(
        self, metaclass: str, key: str, parents: Set[Tuple[str, str]]
    ) -> None:
        """
        Re-register this plugin as a dependent on each of its parents.

        Used to undo the upfront `unregister_dependent` calls in `edit_plugin`
        when the edit is aborted before `apply_settings` re-establishes the
        link, since the plugin instance and its actual parent usage are
        otherwise unchanged.

        :param metaclass: The metaclass of the plugin being restored.
        :type metaclass: str
        :param key: The key of the plugin being restored.
        :type key: str
        :param parents: The (metaclass, key) pairs of the plugin's parents.
        :type parents: Set[Tuple[str, str]]
        """
        for pmetaclass, pkey in parents:
            pinstance = self.model.get_plugin_instance(pmetaclass, pkey)
            if pinstance:
                pinstance.register_dependent(metaclass, key)

    @log(logger=logger)
    @Slot(str, str)
    def delete_plugin(self, metaclass: str, key: str) -> None:
        """
        Delete a plugin instance if it has no dependents.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The unique key identifying the plugin instance.
        :type key: str
        """
        instance = self.model.get_plugin_instance(metaclass, key)
        if not instance:
            self.logger.warning(f"No plugin instance found for {metaclass}:{key}")
            return

        dependents = instance.get_dependents()

        if not dependents:
            # Unregister from parents
            parents = instance.get_parents()
            for pmetaclass, pkey in parents:
                parent_instance = self.model.get_plugin_instance(pmetaclass, pkey)
                if parent_instance:
                    parent_instance.unregister_dependent(metaclass, key)

            # Delete from model
            self.model.unregister_plugin(metaclass, key)

            # Remove from persisted plugin history
            self.update_plugin_history.emit({}, key)

            # Notify UI
            self.update_available_plugins.emit(
                metaclass, self.model.get_instantiated_plugins_list()[metaclass]
            )
            self.logger.info(f"Plugin {key} deleted successfully.")
            self.add_text_to_display.emit(
                f"Plugin {key} deleted.", "DataPluginController"
            )
        else:
            dependent_keys = [dep[1] for dep in dependents]
            self.logger.info(
                f"Unable to delete {key} since it has dependents {dependent_keys}"
            )
            self.add_text_to_display.emit(
                f"Unable to delete {key} since it has dependents {dependent_keys}",
                "DataPluginController",
            )

    @log(logger=logger)
    def set_available_plugins(
        self, available_plugin_classes: Mapping[str, Mapping[str, type]]
    ) -> None:
        """
        Pass a re-scanned set of plugin classes down to the model.

        :param available_plugin_classes: Dict of available plugin classes, keyed
            by metaclass then subclass name.
        :type available_plugin_classes: Mapping[str, Mapping[str, type]]
        """
        self.model.set_available_plugins(available_plugin_classes)

    def _instantiated_keys(self) -> List[Tuple[str, str]]:
        """
        Every instantiated plugin as (metaclass, key) pairs.

        :return: One pair per live plugin instance.
        :rtype: List[Tuple[str, str]]
        """
        return [
            (metaclass, key)
            for metaclass, keys in self.model.get_instantiated_plugins_list().items()
            for key in keys
        ]

    @log(logger=logger)
    def delete_all_plugins(self) -> List[str]:
        """
        Delete every instantiated plugin, dependents before their parents.

        Order is not optional: :py:meth:`delete_plugin` refuses any plugin that
        still has dependents, so a single pass in arbitrary order would leave
        most of the graph behind. Each round deletes whatever currently has no
        dependents, which frees the next layer up, until nothing is left.

        The loop stops when a round removes nothing, and returns whatever is
        left so the caller can report a partial clear rather than announce
        success. Three things can leave survivors: a dependency cycle, a stale
        registration leaving a parent holding a dependent that no longer exists,
        and a key listed with no instance behind it.

        That last case is why the guard counts what was actually removed rather
        than what looked removable. A key whose instance is missing reports no
        dependents, so it appears deletable every round, while delete_plugin
        declines it and leaves the key in place - a guard watching for "nothing
        looks deletable" would never fire and the loop would spin forever.

        :return: Keys of any plugins that could not be deleted, empty if all were.
        :rtype: List[str]
        """

        while True:
            before = self._instantiated_keys()
            if not before:
                break
            for metaclass, key in before:
                instance = self.model.get_plugin_instance(metaclass, key)
                if instance is not None and not instance.get_dependents():
                    self.delete_plugin(metaclass, key)
            if self._instantiated_keys() == before:
                break  # nothing came off this round; it will not on the next

        survivors = [
            key
            for keys in self.model.get_instantiated_plugins_list().values()
            for key in keys
        ]
        if survivors:
            self.logger.warning(f"Unable to delete plugins: {survivors}")
        return survivors

    @log(logger=logger)
    def handle_exit(self) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit
        """
        self.model.handle_exit()

    @log(logger=logger)
    def get_plugin_instances(self) -> Dict[str, Dict[str, Any]]:
        """
        Get every instantiated plugin, keyed by metaclass then by key.

        ``MainController`` pushes this to every analysis tab whenever the plugin set
        changes, on the same notification that refreshes the names those tabs show.

        :return: A dict keyed by metaclass, each holding key -> live instance
        :rtype: Dict[str, Dict[str, Any]]
        """
        return self.model.get_plugin_instances()

    def get_plugin_instance(self, metaclass: str, key: str) -> object:
        """
        Get the plugin instance corresponding to the given key.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The key of the plugin instance.
        :type key: str
        :return: The plugin instance, or None if the key is not found.
        :rtype: object
        """
        return self.model.get_plugin_instance(metaclass, key)

    @log(logger=logger)
    @Slot(str, str)
    def validate_and_instantiate_plugin(
        self,
        metaclass: str,
        subclass: str,
        settings: Optional[Dict[str, Any]] = None,
        key: Optional[str] = None,
    ) -> None:
        """
        Validate and instantiate a plugin based on the given metaclass and subclass.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param subclass: The subclass of the plugin.
        :type subclass: str
        :param settings: The settings dictionary for the plugin.
        :type settings: Optional[Dict[str, Any]]
        :param key: Optional key to set for the new plugin instance.
        :type key: Optional[str]
        :raises ValueError: if no key was supplied by the caller and none was
            chosen in the settings dialog. Caught by this method's own handler
            and reported to the user; it never propagates to the caller.
        """
        history: Dict[str, Any] = {}
        temp_instance = None

        # instantiate a temporary instance of the requested data plugin type
        try:
            temp_instance = self.model.get_temp_instance(metaclass, subclass)
        except Exception as e:
            self.logger.error(
                f"Unable to create a temporary instance of plugin of type {metaclass}.{subclass}: {str(e)}"
            )
            self.add_text_to_display.emit(
                f"Unable to create a temporary instance of plugin of type {metaclass}.{subclass}: {str(e)}",
                self.__class__.__name__,
            )
            return

        # get the settings dict required from the user if it is not provided already, pre-populating from history where possible
        try:
            if key is not None:
                temp_instance.set_key(key)
            if settings is None:
                settings = temp_instance.get_empty_settings(
                    self.model.get_instantiated_plugins_list()
                )
                historical_settings = self._history_lookup(metaclass, subclass)
                if historical_settings:
                    for setting_key, val in historical_settings.items():
                        settings[setting_key]["Value"] = val.get("Value")
                if (
                    "Folder" in settings.keys()
                    and settings["Folder"].get("Value") is None
                ):
                    settings["Folder"][
                        "Value"
                    ] = (
                        self.data_server
                    )  # default to the data server in the absence of better things

                new_settings, new_key, _ = self.view.get_user_settings(
                    settings,
                    f"{subclass}_{len(self.model.get_instantiated_plugins_list()[metaclass])}",
                    self.data_server,
                )
                if new_settings is None or new_key is None:
                    return
                settings, key = new_settings, new_key

            # Enforce global uniqueness of plugin name across all metaclasses
            for (
                meta,
                existing_keys,
            ) in self.model.get_instantiated_plugins_list().items():
                if key in existing_keys:
                    self.logger.warning(
                        f"Plugin name '{key}' already exists under metaclass '{meta}'. Please use a unique name."
                    )
                    self.add_text_to_display.emit(
                        f"Plugin name '{key}' already exists under metaclass '{meta}'. Please choose a different name.",
                        self.__class__.__name__,
                    )
                    return

            if key is None:
                raise ValueError("No plugin key was provided or chosen")
            temp_instance.set_key(key)

        except Exception as e:
            self.logger.exception(
                f"Unable to instantiate plugin {key} of type {metaclass}.{subclass}: {str(e)}"
            )
            self.add_text_to_display.emit(
                f"Unable to instantiate plugin {key} of type {metaclass}.{subclass}: {str(e)}",
                self.__class__.__name__,
            )
            return

        if not settings:
            return

        # Replace plugin references in settings with actual instances
        app_settings = copy.deepcopy(settings)

        try:
            for settings_key, val in app_settings.items():
                if settings_key in self.model.get_available_metaclasses():
                    app_settings[settings_key]["Value"] = (
                        self.model.get_plugin_instance(settings_key, val["Value"])
                    )
                    app_settings[settings_key]["Type"] = None
                    app_settings[settings_key]["Options"] = None
        except Exception as e:
            self.logger.exception(
                f"Unable to instantiate plugin {key} of type {metaclass}.{subclass} due to inability to fetch other plugins: {str(e)}"
            )
            self.add_text_to_display.emit(
                f"Unable to instantiate plugin {key} of type {metaclass}.{subclass} due to inability to fetch other plugins: {str(e)}",
                self.__class__.__name__,
            )
            return

        # apply the settings to the new plugin object
        try:
            temp_instance.apply_settings(app_settings)
        except Exception as e:
            self.logger.error(
                f"Unable to apply settings to plugin {key} of type {metaclass}.{subclass}: {str(e)}"
            )
            self.add_text_to_display.emit(
                f"Unable to apply settings to plugin {key} of type {metaclass}.{subclass}: {str(e)}",
                self.__class__.__name__,
            )
            return

        # register the completed plugin for use by the rest of the app
        try:
            self.model.register_plugin(temp_instance, metaclass, key)
        except Exception as e:
            self.logger.error(
                f"Unable to register new plugin instance {key} of type {metaclass}.{subclass}: {str(e)}"
            )
            self.add_text_to_display.emit(
                f"Unable to register new plugin instance {key} of type {metaclass}.{subclass}: {str(e)}",
                self.__class__.__name__,
            )
            return

        self.update_available_plugins.emit(
            metaclass, self.model.get_instantiated_plugins_list()[metaclass]
        )
        self.add_text_to_display.emit(
            temp_instance.report_channel_status(channel=None, init=True), key
        )

        history["key"] = key
        history["metaclass"] = metaclass
        history["subclass"] = subclass
        history["settings"] = settings
        self.update_plugin_history.emit(history, "")

    @log(logger=logger)
    def update_data_server_location(self, data_server: str) -> None:
        """
        Update the cached data server location used to pre-populate a new plugin's Folder setting.
        """
        self.data_server = data_server

    @log(logger=logger)
    def get_instantiated_plugins_list(self) -> Dict[str, List[str]]:
        """
        Get a dict keyed by metaclass with a list of all keys for plugins that have been instantiated

        :return: A dict keyed by metaclass with a list of all keys for plugins that have been instantiated
        :rtype: Dict[str, List[str]]
        """
        return self.model.get_instantiated_plugins_list()

    @log(logger=logger)
    def get_available_metaclasses(self) -> List[str]:
        """
        Get a list of available metaclasses


        :return: Get a list of available metaclasses
        :rtype: List[str]
        """
        return self.model.get_available_metaclasses()
