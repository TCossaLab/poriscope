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
from typing import Any, Dict, List, Mapping

from PySide6.QtCore import QObject

from poriscope.utils.LogDecorator import log


class DataPluginModel(QObject):
    """
    Base controller class that manages data plugins
    """

    logger = logging.getLogger(__name__)

    def __init__(self, available_plugin_classes) -> None:
        """
        Initialize the plugin model.

        :param available_plugins: Dictionary of available plugins.
        :type available_plugins: Mapping[str, List[str]]
        :param config_path: Path to the configuration file.
        :type config_path: str
        """
        super().__init__()
        self.available_plugins = available_plugin_classes
        self.plugins: Dict[str, Dict[str, Any]] = {
            metaclass: {} for metaclass in available_plugin_classes.keys()
        }

    @log(logger=logger)
    def register_plugin(self, instance: object, metaclass: str, key: str):
        """
        Register a plugin instance with the given key.

        :param instance: The plugin instance
        :type instance: object of the type of plugin managed by the instance
        :param metaclass: the base class of the plugin
        :type metaclass: str
        :param key: The key to register the plugin with
        :type key: str
        :raises ValueError: If the key already exists
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
    def update_plugin_key(self, metaclass: str, new_key: str, old_key: str):
        """
        Register a plugin instance with the given key.

        :param instance: The plugin instance
        :type instance: object of the type of plugin managed by the instance
        :param metaclass: the base class of the plugin
        :type metaclass: str
        :param key: The key to register the plugin with
        :type key: str
        :raises ValueError: If the key already exists
        """
        if metaclass not in self.plugins.keys():
            self.logger.error(f"Cannot update plugin key: {metaclass} not supported")
            raise KeyError(f"Metaclass {metaclass} not found")
        self.plugins[metaclass][new_key] = self.plugins[metaclass].pop(old_key)

    @log(logger=logger)
    def get_temp_instance(self, metaclass: str, subclass: str) -> object:
        """
        Get a temporary plugin instance without settings applied.

        :param metaclass: the base class of the plugin
        :type metaclass: str
        :param subclass: The subclass of the plugin, defaults to None.
        :type subclass: str
        :return: The temporary plugin instance.
        :rtype: object of the type of plugin managed by the instance
        :raises NotImplementedError: If the subclass is not provided.
        """
        return self.available_plugins[metaclass][subclass]()

    @log(logger=logger)
    def get_instantiated_plugins_list(self) -> Mapping[str, List[str]]:
        """
        Get a dict keyed by metaclass with a list of all keys for plugins that have been instantiated


        :return: A dict keyed by metaclass with a list of all keys for plugins that have been instantiated
        :rtype: Mapping[str, List[str]]
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
            self.plugins[metaclass][key].close_resources()
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
    def apply_settings(self, instance, settings):
        """
        If the plugin needs settings dict to work, call the appropriate method in an instance to apply it

        :param instance: the object to apply the settings to
        :type instance: A data plugin object
        :param settings: a nested dict of settings to apply
        :type settings: Mapping[str, Mapping[str, Any]]
        """
        instance.apply_settings(settings)

    @log(logger=logger)
    def get_plugin_instance(self, metaclass: str, key: str) -> object:
        """
        Get the plugin instance corresponding to the given key.

        :param metaclass: the base class of the plugin
        :type metaclass: str
        :param key: The key of the plugin instance.
        :type key: str
        :return: The plugin instance or None if the key is not found.
        :rtype: Optional[object]
        """
        return self.plugins[metaclass].get(key)

    @log(logger=logger)
    def get_plugin_details(self, metaclass, key):
        """
        Retrieve the raw settings associated to an already-instantiated plugin by metaclass and key.

        :param metaclass: The metaclass of the plugin.
        :type metaclass: str
        :param key: The key of the plugin instance to remove.
        :type key: str

        :return: the dict that must be filled in to initialize the plguin, or None on failure
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
