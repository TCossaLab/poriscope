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
from typing import Any, Dict, List, Mapping, Optional, Type

from PySide6.QtCore import QObject

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.LogDecorator import log


class DataPluginModel(QObject):
    """
    Base model class that manages data plugins
    """

    logger = logging.getLogger(__name__)

    def __init__(
        self, available_plugin_classes: Mapping[str, Mapping[str, Type[BaseDataPlugin]]]
    ) -> None:
        """
        Initialize the plugin model.

        :param available_plugin_classes: Dict of available plugin classes, keyed by metaclass then subclass name.
        :type available_plugin_classes: Mapping[str, Mapping[str, Type[BaseDataPlugin]]]
        """
        super().__init__()
        self.available_plugins = available_plugin_classes
        self.plugins: Dict[str, Dict[str, BaseDataPlugin]] = {
            metaclass: {} for metaclass in available_plugin_classes.keys()
        }

    @log(logger=logger)
    def register_plugin(
        self, instance: BaseDataPlugin, metaclass: str, key: str
    ) -> None:
        """
        Register a plugin instance with the given key.

        If key is already registered under metaclass, the plugin is not registered
        and an error is logged instead of raising.

        :param instance: The plugin instance, of the type of plugin managed by this model
        :type instance: BaseDataPlugin
        :param metaclass: the base class of the plugin
        :type metaclass: str
        :param key: The key to register the plugin with
        :type key: str
        :raises KeyError: If metaclass is not a supported plugin type
        """
        if metaclass not in self.plugins.keys():
            self.logger.error(f"Cannot register plugin: {metaclass} not supported")
            raise KeyError(f"Metaclass {metaclass} not found")

        if key not in self.plugins[metaclass].keys():
            self.plugins[metaclass][key] = instance
        else:
            self.logger.error(
                f"Unable to register plugin of type {metaclass} since key {key} already exists"
            )

    @log(logger=logger)
    def update_plugin_key(self, metaclass: str, new_key: str, old_key: str) -> None:
        """
        Re-key an already-registered plugin instance from old_key to new_key.

        :param metaclass: the base class of the plugin
        :type metaclass: str
        :param new_key: The new key to register the plugin instance under
        :type new_key: str
        :param old_key: The existing key the plugin instance is currently registered under
        :type old_key: str
        :raises KeyError: If metaclass is not supported, or if old_key is not currently registered under metaclass

        If new_key is already registered under metaclass (and differs from old_key), the
        rename is refused and an error is logged instead of overwriting the existing entry.
        """
        if metaclass not in self.plugins.keys():
            self.logger.error(f"Cannot update plugin key: {metaclass} not supported")
            raise KeyError(f"Metaclass {metaclass} not found")
        if new_key != old_key and new_key in self.plugins[metaclass]:
            self.logger.error(
                f"Cannot rename plugin key {old_key} to {new_key}: {new_key} already exists under metaclass {metaclass}"
            )
            return
        self.plugins[metaclass][new_key] = self.plugins[metaclass].pop(old_key)

    @log(logger=logger)
    def get_temp_instance(self, metaclass: str, subclass: str) -> BaseDataPlugin:
        """
        Get a temporary plugin instance without settings applied.

        :param metaclass: the base class of the plugin
        :type metaclass: str
        :param subclass: The subclass of the plugin, defaults to None.
        :type subclass: str
        :return: The temporary plugin instance.
        :rtype: BaseDataPlugin
        :raises KeyError: If metaclass or subclass is not a recognized/available plugin type.
        """  # noqa: DOC502 (KeyError is raised implicitly by the dict lookups below, not via an explicit `raise`)
        return self.available_plugins[metaclass][subclass]()

    @log(logger=logger)
    def get_instantiated_plugins_list(self) -> Dict[str, List[str]]:
        """
        Get a dict keyed by metaclass with a list of all keys for plugins that have been instantiated


        :return: A dict keyed by metaclass with a list of all keys for plugins that have been instantiated
        :rtype: Dict[str, List[str]]
        """
        return {
            metaclass: list(plugins.keys())
            for metaclass, plugins in self.plugins.items()
        }

    @log(logger=logger)
    def get_available_metaclasses(self) -> List[str]:
        """
        Get a list of available metaclasses


        :return: Get a list of available metaclasses
        :rtype: List[str]
        """
        return list(self.plugins.keys())

    @log(logger=logger)
    def unregister_plugin(self, metaclass: str, key: str) -> None:
        """
        Unregister a plugin instance.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The key of the plugin instance to remove.
        :type key: str
        :raises KeyError: If the plugin key does not exist.
        """
        if key in self.plugins[metaclass]:
            try:
                self.plugins[metaclass][key].close_resources()
            except Exception as e:
                self.logger.error(
                    f"Error closing resources for plugin {key} in {metaclass}: {e}"
                )
            del self.plugins[metaclass][key]
            self.logger.info(
                f"Plugin {key} successfully unregistered from {metaclass}."
            )
        else:
            self.logger.error(
                f"No plugin found with key {key} in metaclass {metaclass}"
            )
            raise KeyError(f"No plugin found with key {key} in metaclass {metaclass}")

    @log(logger=logger)
    def handle_exit(self) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit
        """
        for plugins in self.plugins.values():
            for plugin in plugins.values():
                plugin.close_resources()

    @log(logger=logger)
    def apply_settings(
        self, instance: Any, settings: Mapping[str, Mapping[str, Any]]
    ) -> None:
        """
        If the plugin needs settings dict to work, call the appropriate method in an instance to apply it

        :param instance: the object to apply the settings to
        :type instance: Any
        :param settings: a nested dict of settings to apply
        :type settings: Mapping[str, Mapping[str, Any]]
        """
        instance.apply_settings(settings)

    @log(logger=logger)
    def get_plugin_instance(self, metaclass: str, key: str) -> Optional[BaseDataPlugin]:
        """
        Get the plugin instance corresponding to the given key.

        :param metaclass: the base class of the plugin
        :type metaclass: str
        :param key: The key of the plugin instance.
        :type key: str
        :return: The plugin instance or None if the key is not found.
        :rtype: Optional[BaseDataPlugin]
        """
        return self.plugins[metaclass].get(key)

    @log(logger=logger)
    def get_plugin_details(self, metaclass: str, key: str) -> Optional[dict]:
        """
        Retrieve the raw settings associated to an already-instantiated plugin by metaclass and key.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The key of the plugin instance to remove.
        :type key: str

        :return: the dict that must be filled in to initialize the plugin, or None on failure
        :rtype: Optional[dict]
        """
        plugin_instance = self.get_plugin_instance(metaclass, key)
        if not plugin_instance:
            self.logger.error(
                f"No plugin instance found for key {key} in metaclass {metaclass}."
            )
            return None
        settings = plugin_instance.get_raw_settings()
        return settings
