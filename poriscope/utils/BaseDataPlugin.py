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

import contextlib
import logging
import threading
from abc import ABC, abstractmethod
from types import TracebackType
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypedDict,
    cast,
)

from poriscope.utils.LogDecorator import log
from poriscope.utils.settings_schema import FILE_DIALOG_PARAMS


class Setting(TypedDict):
    Type: Type[Any]
    Value: Any


class BaseDataPlugin(ABC):
    """
    This class, :ref:`BaseDataPlugin`, is an abstraction of the functionality and interface that is common to all data plugins. What this means practically is that there is a chain of inheritance: all data plugins inherits from their respective base class, all of which inherit from :ref:`BaseDataPlugin`.

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

    Attributes:
        logger (logging.Logger): Logger instance for logging messages.
        lock (threading.RLock): Per-instance reentrant lock, used by :py:meth:`serialize_channel_operations` to serialize this plugin's own operations across channels when it declares that it must not run concurrently. One lock per plugin instance, so two different plugins never contend with each other. A plugin needing *process-wide* serialization (a non-reentrant native library, say) must declare its own class-level lock rather than reusing this one - see ``WaveletFilter``.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, settings: Optional[dict] = None) -> None:
        """
        Construct the plugin and, if settings are provided, apply them immediately.

        :param settings: A dict specifying the parameters of the plugin to be created. Required keys depend on subclass. If None, the plugin is left unconfigured until :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.apply_settings` is called.
        :type settings: Optional[dict]
        """
        # Created before _init() so that subclass hooks and apply_settings can rely on
        # it. Reentrant on purpose: this guard goes into base classes that plugin authors
        # subclass, and the failure mode of a plain Lock re-acquired by the thread that
        # already holds it is a silent hang rather than an exception.
        self.lock = threading.RLock()  # typeshed: RLock is a factory, not a type
        self._init()
        self.settings: dict[str, dict[str, Any]] = settings or {}
        self.dependents: Set[Tuple[str, str]] = set()
        self.parents: Set[Tuple[str, str]] = set()
        self.raw_settings: dict[str, dict[str, Any]] = {}
        self.key: str = ""
        if settings:
            self.apply_settings(settings)

    def __enter__(self) -> "BaseDataPlugin":
        """
        Enter the context management. Return self to be used within a 'with' statement.
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
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
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Type is required; Value may be omitted or set to None, both meaning there is no default and the user must supply one. All values provided must be consistent with Type.

        .. code-block:: python

          settings = {'Parameter 1': {'Type': <int, float, str, bool>,
                                           'Value': <value> or None,
                                           'Options': [<option_1>, <option_2>, ... ] or None,
                                           'Min': <min_value> or None,
                                           'Max': <max_value> or None
                                          },
                          ...
                          }

        The base implementations here do omit Value - a reader's schema is literally
        ``{"Input File": {"Type": str}}``. Note that a settings dict *supplied back* to
        ``apply_settings()`` does need every Value present, because ``_validate_param_types``
        reads it by subscript; the GUI's settings dialog fills them in before that point.

        Run ``python scripts/check_plugin_schemas.py`` to check a schema you have written for
        self-consistency, or see ``poriscope.utils.settings_schema`` to call the same check
        directly.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[ Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        pass

    @abstractmethod
    def report_channel_status(
        self, channel: Optional[int] = None, init: bool = False
    ) -> str:
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

    @contextlib.contextmanager
    def serialize_channel_operations(self) -> Iterator[None]:
        """
        Hold this plugin's own lock for the duration of the block, but only if the plugin declares that its channels must not run concurrently.

        This is where :py:meth:`force_serial_channel_operations` is actually enforced. The declaration is a statement about *this instance* - "my own operations must not overlap across channels" - so the lock taken is this instance's :py:attr:`lock`. Two different plugin instances never contend with each other, and a plugin that returns ``False`` pays nothing.

        Enforcement lives here, on the object that makes the declaration, rather than in the caller. It used to live in ``MetaModel``, which asked the plugin over the signal bus and then handed its own model-scoped lock to the worker - and since every analysis tab builds its own model, two tabs driving the *same* plugin instance took *different* locks and ran it concurrently anyway, while unrelated plugins within one tab serialized against each other for nothing.

        The lock is held across ``yield``, so a generator guarded by this is serialized for its whole run and releases when it is exhausted or closed. :py:meth:`~poriscope.utils.MetaModel.MetaModel.discard_generator` closes spent generators explicitly so that release does not depend on garbage-collection timing.

        :yield: None; the block runs with the lock held if serialization was requested.
        :ytype: None
        """
        if self.force_serial_channel_operations():
            with self.lock:
                yield
        else:
            yield

    @log(logger=logger)
    def register_dependent(self, metaclass: str, key: str) -> None:
        """
        Record that another plugin, identified by (metaclass, key), depends on this one.

        :param metaclass: the name of the Meta* base class of the dependent plugin
        :type metaclass: str
        :param key: the unique key of the dependent plugin
        :type key: str
        """
        if metaclass is not None and key is not None:
            self.dependents.add((metaclass, key))

    @log(logger=logger)
    def register_parent(self, metaclass: str, key: str) -> None:
        """
        Record that this plugin depends on another plugin, identified by (metaclass, key).

        :param metaclass: the name of the Meta* base class of the parent plugin
        :type metaclass: str
        :param key: the unique key of the parent plugin
        :type key: str
        """
        if metaclass is not None and key is not None:
            self.parents.add((metaclass, key))

    @log(logger=logger)
    def unregister_dependent(self, metaclass: str, key: str) -> None:
        """
        Remove a previously registered dependent, identified by (metaclass, key), if present.

        :param metaclass: the name of the Meta* base class of the dependent plugin
        :type metaclass: str
        :param key: the unique key of the dependent plugin
        :type key: str
        """
        self.dependents.discard((metaclass, key))

    @log(logger=logger)
    def unregister_parent(self, metaclass: str, key: str) -> None:
        """
        Remove a previously registered parent, identified by (metaclass, key), if present.

        :param metaclass: the name of the Meta* base class of the parent plugin
        :type metaclass: str
        :param key: the unique key of the parent plugin
        :type key: str
        """
        self.parents.discard((metaclass, key))

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
    def get_raw_settings(self) -> dict:
        """
        Get the settings that were applied during initialization of the instance

        :return: the dict that must be filled in to initialize the plguin
        :rtype: dict
        """
        return self.raw_settings

    @log(logger=logger)
    def update_raw_settings(self, key: str, val: Any) -> None:
        """
        Update raw settings when needed

        :param key: the settings key to update
        :type key: str
        :param val: the new value to store for that key
        :type val: Any
        """
        if self.raw_settings and key in self.raw_settings:
            self.raw_settings[key]["Value"] = val

    def _resolve_metaclass_name(self, cls: type) -> str:
        """
        Walk the MRO of a plugin class to find its direct Meta* base (e.g.
        MetaEventFinder, MetaReader), regardless of how many concrete-subclass
        layers sit between it and that base.

        Using ``cls.__bases__[0]`` instead only works if ``cls`` subclasses
        its Meta* base directly. For a plugin that subclasses another concrete
        plugin (e.g. ``BoundedBlockageFinder(ClassicBlockageFinder)``, itself
        a subclass of ``MetaEventFinder``), that would return the intermediate
        concrete class's name instead, which does not match any key in
        DataPluginModel's per-metaclass plugin registry.

        :param cls: the plugin class to resolve
        :type cls: type
        :raises TypeError: if cls does not inherit from a Meta* base class
        :return: the name of the Meta* base class cls ultimately derives from
        :rtype: str
        """
        for klass in cls.__mro__:
            if BaseDataPlugin in klass.__bases__:
                return klass.__name__
        raise TypeError(f"{cls.__name__} does not inherit from a Meta* base class")

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
                except AttributeError:
                    # A plain settings value (int, str, float, ...) has no
                    # get_key(); that is the signal that this entry is not a
                    # plugin instance and needs no parent/dependent wiring. Only
                    # AttributeError means that. Anything else is a real fault and
                    # must not be swallowed: the else branch below builds the
                    # dependency graph that DataPluginController relies on to refuse
                    # deleting a plugin that still has dependents, so silently
                    # skipping it would let a plugin be deleted out from under one.
                    pass
                else:
                    # register parents and dependents to ensure sane deletion later
                    self.settings[key]["Value"].register_dependent(
                        self._resolve_metaclass_name(self.__class__), self.get_key()
                    )
                    self.register_parent(
                        self._resolve_metaclass_name(
                            self.settings[key]["Value"].__class__
                        ),
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

        :param key: the key of the plugin
        :type key: str
        """
        self.key = key

    # private API, must be implemented by subclasses
    @abstractmethod
    def _finalize_initialization(self) -> None:
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

        :param settings: Parameters required to configure this plugin.
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

        A parameter with no value at all - either no ``Value`` key or ``Value: None`` - is
        left for :py:meth:`_validate_param_ranges` to reject, which reports it as a missing
        required value rather than as a type error. Reading the key with ``.get`` matters:
        a schema straight out of ``get_empty_settings()`` legitimately omits ``Value``, and
        subscripting it raised ``KeyError`` where the caller expected ``TypeError``.

        :param settings: A dict specifying the parameters of the filter to be created. Required keys depend on subclass.
        :type settings: Dict[str, Setting]
        :raises TypeError: If the filter_params parameters are of the wrong type
        """
        if settings:
            for param, val in settings.items():
                setting_type = cast(Type[Any], val["Type"])
                setting_value = val.get("Value")
                if setting_value is None:
                    continue
                if setting_type in (int, float, bool, str):
                    if not isinstance(setting_value, setting_type):
                        raise TypeError(f"{param} must have type {val['Type']}")

    @log(logger=logger)
    def _validate_param_ranges(self, settings: dict) -> None:
        """
        Validate that every parameter has a value and that it lies within any declared bounds

        A parameter with no value - no ``Value`` key, or ``Value: None`` - is rejected here
        rather than in :py:meth:`_validate_param_types`, so that the user is told the value
        is required instead of being told it has the wrong type. This also keeps ``None``
        away from the bound comparisons below, which would otherwise raise ``TypeError``
        from a method whose contract promises ``ValueError``.

        :param settings: A dict specifying the parameters of the filter to be created. Required keys depend on subclass.
        :type settings: dict
        :raises ValueError: If a required value is missing, out of range, or not an allowed option
        """
        if settings:
            for param, val in settings.items():
                min_value = val.get("Min", None)
                max_val = val.get("Max", None)
                options = val.get("Options", None)
                value = val.get("Value")
                if value is None:
                    raise ValueError(f"{param} requires a value")
                if min_value is not None and value < min_value:
                    raise ValueError(f"{param} must be larger than {min_value}")
                if max_val is not None and value > max_val:
                    raise ValueError(f"{param} must be smaller than {max_val}")
                if (
                    options is not None
                    and param not in FILE_DIALOG_PARAMS
                    and value not in options
                ):
                    raise ValueError(f"{param} must be one of {options}")
