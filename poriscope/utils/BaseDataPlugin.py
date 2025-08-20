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
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple, Type, TypedDict, cast

from poriscope.utils.LogDecorator import log


class Setting(TypedDict):
    Type: Type[Any]
    Value: Any


class BaseDataPlugin(ABC):
    """
    :ref:`BaseDataPlugin` is an abstraction of the functionality and interface that is common to all data plugins. What this means practically is that there is a chain of inheritance: all data plugins inherits from their respective base class, all of which inherit from :ref:`BaseDataPlugin`.

    It handles stuff like instantiating the plugins, constructing settings dictionaries, and sanity checking the inputs, as well as a handful of bookkeeping functions used by the poriscope GUI to manage interactions between the MVC architecture and the data plugins themselves - basically, anything that involves interaction with the nuts and bolts of the poriscope GUI.

    What You Get by Inheriting from Base Data Plugin
    ------------------------------------------------

    .. warning::

       You probably do not need to inherit directly from :ref:`BaseDataPlugin`, as this is a general base class for the specific base classes from which :ref:`Data Plugins <Data_Plugins>` are built. If your intention is to build a data plugin that fits one of the existing subtypes, you should inherit instead refer to one of the following pages:

       1. :ref:`Build_MetaReader`
       2. :ref:`Build_MetaFilter`
       3. :ref:`Build_MetaEventFinder`
       4. :ref:`Build_MetaWriter`
       5. :ref:`Build_MetaEventLoader`
       6. :ref:`Build_MetaEventFitter`
       7. :ref:`Build_MetaDatabaseWriter`
       8. :ref:`Build_MetaDatabaseLoader`

       If you are planning to build an entirely new type of Data Plugin not in the list above, we strongly suggest contacting the poriscope developers first.

    As soon as you subclass a base class from :ref:`BaseDataPlugin`, the following happens:

    - The ``poriscope`` GUI will know how to interact with this plugin type, and will manage its relationship to other plugin classes on which it might depend
    - Your plugin will handle basic sanity checks on settings at instantiation without any extra work needed
    - Several abstract functions are defined that can be realized either at the base class or subclass level that define a common API for all data plugins

    .. note::

        For the most part, users will not have to worry much about anything in this base class, as all other abstract base classes for data plugins inherit from this one and will define the relevant interface at the subclass level. However, in the unlikely event that you are defining an entirely new class of data plugin, it will need to inherit from this base in order to fully integrate into poriscope. Because integrating a new base into poriscope requires registration in core app elements, it is strongly encouraged that you contact the repository managers before trying in order to assess whether there is a simpler solution.
    """

    logger = logging.getLogger(__name__)
    lock = threading.Lock()

    def __init__(self, settings: Optional[dict] = None):
        self._init()
        self.settings: dict[str, dict[str, Any]] = settings or {}
        self.dependents: Set[Tuple[str, str]] = set()
        self.parents: Set[Tuple[str, str]] = set()
        self.raw_settings: dict[str, dict[str, Any]] = {}
        self.key: str = ""
        if settings:
            self.apply_settings(settings)

    def __enter__(self):
        """
        Enter the context management. Return self to be used within a 'with' statement.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context management. Close resources.
        """
        self.close_resources()

    # public API, must be implemented by subclasses
    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit. If channel is not None, handle only that channel, else close all of them.

        :param channel: channel ID
        :type channel: Optional[int]
        """
        pass

    @abstractmethod
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        Perform any actions necessary to reset a channel to its starting state. If channel is not None, handle only that channel, else reset all of them.

        :param channel: channel ID
        :type channel: Optional[int]
        """
        pass

    @abstractmethod
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone=False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.

        .. code-block:: python

          settings = {'Parameter 1': {'Type': <int, float, str, bool>,
                                           'Value': <value> or None,
                                           'Options': [<option_1>, <option_2>, ... ] or None,
                                           'Min': <min_value> or None,
                                           'Max': <max_value> or None
                                          },
                          ...
                          }

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[ Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        pass

    @abstractmethod
    def report_channel_status(self, channel: Optional[int] = None, init=False) -> str:
        """
        Return a string detailing any pertinent information about the status of analysis conducted on a given channel

        :param channel: channel ID
        :type channel: Optional[int]
        :param init: is the function being called as part of plugin initialization? Default False
        :type init: bool

        :return: the status of the channel as a string
        :rtype: str
        """
        pass

    # Public API with default behavior, if you modify these, call super() at an appropriate point in your override
    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).

        For plugins that do not depend on other data plugins, by default this simply returns ``False``, meaning that it is acceptable and thread-safe to run operations on different channels in different threads on this plugin. If such operation is not thread-safe, this function should be overridden to simply return ``True``. In the case where your plugin depends on another plugin (for example, event finder plugins depend on reader plugins), then your plugin should defer thread safety considerations to the plugin on which it depends.

        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool
        """
        return False

    @log(logger=logger)
    def register_dependent(self, metaclass: str, key: str) -> None:
        """

        :return: the dict that must be filled in to initialize the plguin
        :rtype: Optional[dict]
        """
        if metaclass is not None and key is not None:
            self.dependents.add((metaclass, key))

    @log(logger=logger)
    def register_parent(self, metaclass: str, key: str) -> None:
        """

        :return: the dict that must be filled in to initialize the plguin
        :rtype: Optional[dict]
        """
        if metaclass is not None and key is not None:
            self.parents.add((metaclass, key))

    @log(logger=logger)
    def unregister_dependent(self, metaclass: str, key: str) -> None:
        """

        :return: the dict that must be filled in to initialize the plguin
        :rtype: Optional[dict]
        """
        try:
            self.dependents.remove((metaclass, key))
        except Exception:
            pass

    @log(logger=logger)
    def unregister_parent(self, metaclass: str, key: str) -> None:
        """

        :return: the dict that must be filled in to initialize the plguin
        :rtype: Optional[dict]
        """
        try:
            self.parents.remove((metaclass, key))
        except Exception:
            pass

    @log(logger=logger)
    def get_dependents(self) -> Set[Tuple[str, str]]:
        """
        Get the set of (metaclass, key) tuples representing this plugin's dependents.

        :return: Set of dependents
        :rtype: Set[Tuple[str, str]]
        """
        return self.dependents

    @log(logger=logger)
    def get_parents(self) -> Set[Tuple[str, str]]:
        """
        Get the set of (metaclass, key) tuples representing this plugin's parents.

        :return: Set of parents
        :rtype: Set[Tuple[str, str]]
        """
        return self.parents

    @log(logger=logger)
    def get_raw_settings(self) -> Optional[dict]:
        """
        Get the settings that were applied during initialization of the instance

        :return: the dict that must be filled in to initialize the plguin
        :rtype: Optional[dict]
        """
        return self.raw_settings

    @log(logger=logger)
    def update_raw_settings(self, key, val) -> None:
        """
        Update raw settings when needed

        :return: the dict that must be filled in to initialize the plguin
        :rtype: Optional[dict]
        """
        if self.raw_settings and key in self.raw_settings:
            self.raw_settings[key]["Value"] = val

    @log(logger=logger)
    def apply_settings(self, settings: dict) -> None:
        """
        Validate that settings are correct and reasonable, and set params if the check passes

        :param settings: a dict containing the information needed
        :type settings: dict
        """
        if settings:
            self.raw_settings = settings
            self._validate_param_types(settings)
            self._validate_param_ranges(settings)
            self._validate_settings(settings)
            self.settings = {}
            for key, val in settings.items():
                self.settings[key] = {}
                self.settings[key]["Value"] = val[
                    "Value"
                ]  # only update values, ignore updates to type or options from outside
                try:
                    self.raw_settings[key]["Value"] = self.settings[key][
                        "Value"
                    ].get_key()  # store keys for plugins in raw settings instead of actual instances, ignore other values
                except Exception:
                    pass
                else:
                    # register parents and dependents to ensure sane deletion later
                    self.settings[key]["Value"].register_dependent(
                        self.__class__.__bases__[0].__name__, self.get_key()
                    )
                    self.register_parent(
                        self.settings[key]["Value"].__class__.__bases__[0].__name__,
                        self.settings[key]["Value"].get_key(),
                    )

        self._finalize_initialization()

    @log(logger=logger)
    def get_key(self) -> str:
        """
        Get the key used to identify this plugin within the global app scope

        :return: the key of the reader
        :rtype: str
        """
        return self.key

    @log(logger=logger)
    def set_key(self, key: str) -> None:
        """
        Set the key used to identify this plugin within the global app scope

        :param str: they key of the plugin
        :type data: str
        """
        self.key = key

    # private API, must be implemented by subclasses
    @abstractmethod
    def _finalize_initialization(self):
        """
        Apply the provided paramters and intialize any internal structures needed
        Should Raise if initialization fails.

        This function is called at the end of the class constructor to perform additional initialization specific to the algorithm being implemented.
        kwargs provided to the base class constructor are available as class attributes.
        """
        pass

    @abstractmethod
    def _init(self) -> None:
        """
        called at the start of base class initialization
        """
        pass

    @abstractmethod
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass

    # private API, if you override this, call super() at an appropriate point in your override

    @log(logger=logger)
    def _validate_param_types(self, settings: Dict[str, Setting]) -> None:
        """
        Validate that the filter_params dict contains correct data types, but only checks primitives.
        More detailed parameter checking should follow a call to super() in an override.

        param settings: A dict specifying the parameters of the filter to be created. Required keys depend on subclass.
        :type settings: dict
        :raises TypeError: If the filter_params parameters are of the wrong type
        """
        if settings:
            for param, val in settings.items():
                setting_type = cast(Type[Any], val["Type"])
                setting_value = val["Value"]
                if isinstance(setting_type, (int, float, bool, str)):
                    if not isinstance(setting_value, setting_type) and not issubclass(
                        type(setting_value), setting_type
                    ):
                        raise TypeError(f"{param} must have type {val['Type']}")

    @log(logger=logger)
    def _validate_param_ranges(self, settings: dict) -> None:
        """
        Validate that the filter_params dict contains correct data types

        param settings: A dict specifying the parameters of the filter to be created. Required keys depend on subclass.
        :type settings: dict
        :raises TypeError: If the filter_params parameters are of the wrong type
        """
        if settings:
            for param, val in settings.items():
                min_value = val.get("Min", None)
                max_val = val.get("Max", None)
                options = val.get("Options", None)
                value = val.get("Value")
                if min_value is not None and value < min_value:
                    raise ValueError(f"{param} must be larger than {min_value}")
                if max_val is not None and value > max_val:
                    raise ValueError(f"{param} must be smaller than {max_val}")
                if (
                    options is not None
                    and param not in ["Output File", "Input File"]
                    and value not in options
                ):
                    raise ValueError(f"{param} must be one of {options}")
