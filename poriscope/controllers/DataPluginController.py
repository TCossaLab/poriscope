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
from typing import Any, Dict, List, Mapping, Optional, Tuple

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
    get_settings_from_history = Signal(str, str)
    add_text_to_display = Signal(str, str)
    logger = logging.getLogger(__name__)

    def __init__(self, available_plugin_classes, data_server) -> None:
        super().__init__()
        self.view = DataPluginView()
        self.model = DataPluginModel(available_plugin_classes)
        self.data_server = data_server
        self.plugin_manager = None

    @log(logger=logger)
    @Slot(str, str)
    def edit_plugin_settings(self, metaclass: str, key: str):
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

    def edit_plugin(self, metaclass, key, settings):
        """
        Edit and apply settings for an existing plugin

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param subclass: The subclass of the plugin, defaults to None.
        :type subclass: Optional[str]
        :raises Exception: If unable to instantiate the plugin.
        """

        app_settings = copy.deepcopy(settings)
        instance = self.model.get_plugin_instance(metaclass, key)

        for settings_key, val in app_settings.items():
            if settings_key in self.model.get_available_metaclasses():
                app_settings[settings_key]["Type"] = str
                app_settings[settings_key][
                    "Options"
                ] = self.model.get_instantiated_plugins_list()[settings_key]

        history: Dict[str, Any] = {}

        result = self.view.get_user_settings(
            app_settings,
            key,
            self.data_server,
            editable=True,
            show_delete=True,
            editable_source_plugins=False,
            source_plugins=self.model.get_available_metaclasses(),
        )
        if result == (None, None):
            return

        parents = instance.get_parents()
        dependents = instance.get_dependents()
        for pmetaclass, pkey in parents:
            pinstance = self.model.get_plugin_instance(pmetaclass, pkey)
            pinstance.unregister_dependent(metaclass, key)

        if result == "delete":
            if not dependents:
                self.model.unregister_plugin(metaclass, key)
                self.update_available_plugins.emit(
                    metaclass, self.model.get_instantiated_plugins_list()[metaclass]
                )
                self.update_plugin_history.emit(history, key)
            else:
                dependents = [dependent[1] for dependent in dependents]
                self.logger.info(
                    f"Unable to delete {key} since it has dependents {dependents}"
                )
                self.add_text_to_display.emit(
                    f"Unable to delete {key} since it has dependents {dependents}",
                    "DataPluginController",
                )
        else:
            old_key = instance.get_key()
            settings, key = result

        # Global plugin key collision check
        if key != old_key:
            for meta, keys in self.model.get_instantiated_plugins_list().items():
                if key in keys:
                    self.logger.warning(
                        f"Cannot rename plugin to '{key}' because it already exists under metaclass '{meta}'."
                    )
                    self.add_text_to_display.emit(
                        f"Plugin name '{key}' already exists under metaclass '{meta}'. Please choose a different name.",
                        "DataPluginController",
                    )
                    return

            for dmetaclass, dkey in dependents:
                dinstance = self.model.get_plugin_instance(dmetaclass, dkey)
                dinstance.unregister_parent(metaclass, old_key)
                dinstance.register_parent(metaclass, key)
                dhistory = {}
                dhistory["key"] = dinstance.get_key()
                dhistory["metaclass"] = dmetaclass
                dhistory["subclass"] = dinstance.__class__.__name__
                dsettings = dinstance.get_raw_settings()
                dhistory["settings"] = dsettings
                dsettings[metaclass]["Value"] = key
                dinstance.update_raw_settings(metaclass, key)
                if dsettings[metaclass]["Options"] is not None:
                    dsettings[metaclass]["Options"].append(key)
                    dsettings[metaclass]["Options"].remove(old_key)
                self.update_plugin_history.emit(dhistory, "")
            try:
                instance.set_key(key)
                for settings_key, val in app_settings.items():
                    if settings_key in self.model.get_available_metaclasses():
                        app_settings[settings_key]["Value"] = (
                            self.model.get_plugin_instance(settings_key, val["Value"])
                        )
                        app_settings[settings_key]["Type"] = None
                        app_settings[settings_key]["Options"] = None
            except Exception as e:
                self.logger.exception(
                    f"Unable to edit plugin {key} of type {metaclass} : {repr(e)}"
                )
                return

            self.model.update_plugin_key(metaclass, key, old_key)
            self.update_available_plugins.emit(
                metaclass, self.model.get_instantiated_plugins_list()[metaclass]
            )

            self.add_text_to_display.emit(
                instance.report_channel_status(channel=None, init=True), key
            )
            history["key"] = key
            history["metaclass"] = metaclass
            history["subclass"] = instance.__class__.__name__
            history["settings"] = settings
            self.update_plugin_history.emit(history, old_key)

        # apply the settings to the new plugin object
        try:
            instance.apply_settings(app_settings)
        except Exception as e:
            self.logger.info(
                f"Unable to apply settings to plugin {key} of type {metaclass}.{instance.__class__.__name__}: {repr(e)}"
            )
            return
        else:
            history["key"] = key
            history["metaclass"] = metaclass
            history["subclass"] = instance.__class__.__name__
            history["settings"] = settings
            self.update_plugin_history.emit(history, "")

    @log(logger=logger)
    @Slot(str, str)
    def delete_plugin(self, metaclass: str, key: str):
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
    def handle_exit(self) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit
        """
        self.model.handle_exit()

    @log(logger=logger)
    def get_plugin_instance(self, metaclass, key):
        """
        Get the plugin instance corresponding to the given key.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The key of the plugin instance.
        :type key: str
        :return: The plugin instance.
        :rtype: object of the type of the data plugin being controlled
        """
        return self.model.get_plugin_instance(metaclass, key)

    @log(logger=logger)
    @Slot(str, str)
    def validate_and_instantiate_plugin(
        self,
        metaclass: str,
        subclass: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
        key: Optional[str] = None,
    ) -> None:
        """
        Validate and instantiate a plugin based on the given metaclass and subclass.

        :param metaclass: The metaclass of the plugin.
        :param subclass: The subclass of the plugin.
        :param settings: The settings dictionary for the plugin.
        :param key: Optional key to set for the new plugin instance.
        """
        history: Dict[str, Any] = {}
        temp_instance = None
        self.historical_settings = None

        # instantiate a temporary instance of the requested data plugin type
        try:
            temp_instance = self.model.get_temp_instance(metaclass, subclass)
        except Exception as e:
            self.logger.error(
                f"Unable to create a temporary instance of plugin of type {metaclass}.{subclass}: {repr(e)}"
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
                self.get_settings_from_history.emit(metaclass, subclass)
                if self.historical_settings:
                    for setting_key, val in self.historical_settings.items():
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

                result: Optional[Tuple[Dict[str, Any], str]] = (
                    self.view.get_user_settings(
                        settings,
                        f"{subclass}_{len(self.model.get_instantiated_plugins_list()[metaclass])}",
                        self.data_server,
                    )
                )
                if result is None or result[0] is None:
                    return
                settings, key = result

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
                        "DataPluginController",
                    )
                    return

            temp_instance.set_key(key)

        except Exception as e:
            self.logger.exception(
                f"Unable to instantiate plugin {key} of type {metaclass}.{subclass}: {repr(e)}"
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
                    app_settings[settings_key]["Options"] = None
        except Exception as e:
            self.logger.exception(
                f"Unable to instantiate plugin {key} of type {metaclass}.{subclass} due to inability to fetch other plugins: {repr(e)}"
            )
            return

        # apply the settings to the new plugin object
        try:
            temp_instance.apply_settings(app_settings)
        except Exception as e:
            self.logger.info(
                f"Unable to apply settings to plugin {key} of type {metaclass}.{subclass}: {repr(e)}, no plugin created."
            )
            return

        # register the completed plugin for use by the rest of the app
        try:
            self.model.register_plugin(temp_instance, metaclass, key)
        except Exception as e:
            self.logger.error(
                f"Unable to register new plugin instance {key} of type {metaclass}.{subclass}: {repr(e)}"
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
    def set_settings(self, settings):
        """
        get previously used settings for this plugin tpye, if available
        """
        self.historical_settings = settings

    @log(logger=logger)
    def update_data_server_location(self, data_server):
        """
        get previously used settings for this plugin tpye, if available
        """
        self.data_server = data_server

    @log(logger=logger)
    def get_instantiated_plugins_list(self) -> Mapping[str, List[str]]:
        """
        Get a dict keyed by metaclass with a list of all keys for plugins that have been instantiated

        :return: A dict keyed by metaclass with a list of all keys for plugins that have been instantiated
        :rtype: Mapping[str, List[str]]
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
