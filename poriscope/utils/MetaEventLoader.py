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
from abc import abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

import numpy as np
import numpy.typing as npt

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log


@inherit_docstrings
class MetaEventLoader(BaseDataPlugin):
    """
    What you get by inheriting from MetaEventLoader
    -----------------------------------------------

    :ref:`MetaEventLoader` is the base class for loading the data written by a :ref:`MetaWriter` subclass instance or any other method that produces an equivalent format.

    Poriscope ships with :ref:`SQLiteEventLoader`, a subclass of :ref:`MetaEventLoader` that reads data written by the :ref:`SQLiteDBWriter` subclass. While additional subclasses can read almost any format you desire, we strongly encourage standardization around this format. Think twice before creating additional subclasses of this base class. It is not sufficient to write just a :ref:`MetaEventLoader` subclass. In addition to this base class, you will also need a paired :ref:`MetaWriter` subclass to write data in your target format.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, settings: Optional[dict] = None) -> None:
        """
        Initialize the MetaEventLoader instance.

        Initialize instance attributes based on provided parameters and perform initialization tasks.

        :param settings: an optional dict conforming to that which is required by the self.get_empty_settings() function
        :type settings: dict
        """
        super().__init__(settings)

    # Public API, must be implemented by subclasses

    # Public API, probably usable as-is in most cases

    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool

        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).
        """
        return False

    @log(logger=logger)
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

        channels = self.get_channels()
        num_events = [
            (self.get_num_events(ch), self.get_samplerate(ch)) for ch in channels
        ]
        report = " \n"
        for channel, (num, samplerate) in zip(channels, num_events):
            report += f"Ch: {channel}: {num} events at {samplerate:.2f}Hz\n"
        return report.rstrip("\n")

    @log(logger=logger)
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone=False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[ Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]

        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaWriter` subclass.

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

        Several parameter keywords are reserved: these are

        'Input File'
        'Output File'
        'Folder'

        These must have Type str and will cause the GUI to generate widgets to allow selection of these elements when used

        This function must implement returning of a dictionary of settings required to initialize the filter, in the specified format. Values in this dictionary can be accessed downstream through the ``self.settings`` class variable. This structure is a nested dictionary that supplies both values and a variety of information about those values, used by poriscope to perform sanity and consistency checking at instantiation.

        While this function is technically not abstract in :ref:`MetaEventLoader`, which already has an implementation of this function that ensures that settings will have the required ``Input File`` key available to users, in most cases you will need to override it to add any other settings required by your subclass or to specify which files types are allowed. If you need additional settings, which you almost certainly do, you **MUST** call ``super().get_empty_settings(globally_available_plugins, standalone)`` **before** any additional code that you add. For example, your implementation could look like this, to limit it to sqlite files:

        .. code:: python

            settings = super().get_empty_settings(globally_available_plugins, standalone)
            settings["Input File"]["Options"] = [
                                    "SQLite3 Files (*.sqlite3)",
                                    "Database Files (*.db)",
                                    "SQLite Files (*.sqlite)",
                                    ]
            return settings

        which will ensure that your have the ``Input File`` key and limit visible options to sqlite3 files. By default, it will accept any file type as output, hence the specification of the ``Options`` key for the relevant plugin in the example above.
        """
        settings: Dict[str, Dict[str, Any]] = {
            "Input File": {"Type": str, "Options": ["All Files (*.*)"]}
        }
        return settings

    @log(logger=logger)
    def get_base_file(self) -> Path:
        """
        Return the full path to the file used to initiate this reader

        :return: path to the file used to initiate the reader
        :rtype: Path
        """
        return self.datafile

    # private API, mostly usable as-is
    @log(logger=logger)
    def _finalize_initialization(self) -> None:
        """
        **Purpose:** Apply application-specific settings to the plugin, if needed.

        If additional initialization operations are required beyond the defaults provided in :ref:`BaseDataPlugin` or :ref:`MetaEventLoader` that must occur after settings have been applied to the reader instance, you can override this function to add those operations, subject to the caveat below.

        .. warning::

            This function implements core functionality required for broader plugin integration into Poriscope. If you do need to override it, you **MUST** call ``super()._finalize_initialization()`` **before** any additional code that you add, and take care to understand the implementation of both :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.apply_settings` and :py:meth:`~poriscope.utils.MetaEventLoader.MetaEventLoader._finalize_initialization` before doing so to ensure that you are not conflicting with those functions.
        """
        self.datafile = Path(self.settings["Input File"]["Value"])

    @log(logger=logger)
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Reset the state of a specific channel for a new operation or run.

        This is called any time an operation on a channel needs to be cleaned up or reset for a new run. If channel is not None, handle only that channel, else reset all of them. In most cases for MetaEventLoaders there is no need to reset and you can simplt ``pass``.
        """
        pass

    @abstractmethod
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations.

        This is called immediately at the start of class creation and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most readers simply ``pass`` this function.
        """
        pass

    @abstractmethod
    def get_valid_indices(self, channel: int) -> List[int]:
        """
        :param channel: channel number from which to load data.
        :type channel: int

        :return: A list of event ids
        :rtype: List[int]

        :raises: ValueError if no event_ids exist

        **Purpose** Return a list of indices correspond to the id of events within the given channel, or a list of all valid indices in the database if channel is not specified
        """
        pass

    @abstractmethod
    def load_event(
        self, channel: int, index: int, data_filter: Optional[Callable] = None
    ) -> Dict[str, Union[npt.NDArray[np.float64], int, float]]:
        """
        :param channel: channel number from which to load data.
        :type channel: int
        :param index: The unique identifier for the event to load
        :type index: int

        :return: data and context corresponding to the event, with baseline padding before and after
        :rtype: Dict[str, Union[npt.NDArray[np.float64], int, float]]

        **Purpose:** Load the data and metadata associated with a single specified event

        Return the data and context for the event identified by index, optionally first applying a filter or preprofessing function to the data returned. You are responsible for raising an appropriate error if the index provided is invalid. The data must be returned as a dict with at least the following keys:

        .. code-block:: python

           event = {
                    'data': npt.NDArray[np.float64],  # the data in pA
                    'absolute_start': int,             # the start index of the event relative to the start of the experiment
                    'padding_before': int,            # number of data points in event['data'] before the event start estimate
                    'padding_after': int,             # number of data points in event['data'] after the event end estimate
                    'baseline_mean': float,           # local baseline mean value in pA - can be estimated from the padding if need be
                    'baseline_std': float             # local baseline standard deviation in pA - can be estimated from the padding if need be
                }

        """
        pass

    # private API, MUST be implemented by subclasses
    @abstractmethod
    def get_num_events(self, channel: int) -> int:
        """
        :param channel: the channel to consider
        :type channel: int

        :return: The number of events in the channel
        :rtype: int

        **Purpose:** Return the number of events that exist in the specified channel
        """
        pass

    @abstractmethod
    def get_samplerate(self, channel: int) -> float:
        """
        :param channel: the channel to consider
        :type channel: int

        :return: Sampling rate for the dataset.
        :rtype: float

        **Purpose:** Return the sampling rate used for event data in the specified channel
        """
        pass

    @log(logger=logger)
    def get_event_generator(
        self, channel: int, data_filter: Optional[Callable] = None
    ) -> Generator[Dict[str, Union[npt.NDArray, float, int]], bool, None]:
        """
        :param channel: channel index to analyze.
        :type channel: int
        :param data_filter: a filter function to apply to the data that is returned
        :type data_filter: Optional[Callable]

        :return: Generator yielding event data.
        :rtype: Generator[Dict[str, Union[npt.NDArray, float, int]], bool, None]

        **Purpose:** Load the all events in a specified channel and yield them to the caller one at a time

        For each event in the specified channel, yield the data and context for the event identified by index, optionally first applying a filter or preprofessing function to the data returned. You are responsible for raising an appropriate error if the index provided is invalid. The data must be yielded as a dict with at least the following keys:

        .. code-block:: python

            event = {
                'data': npt.NDArray[np.float64],  # the data in pA
                'absolute_start': int,             # the start index of the event relative to the start of the experiment
                'padding_before': int,            # number of data points in event['data'] before the event start estimate
                'padding_after': int,             # number of data points in event['data'] after the event end estimate
                'baseline_mean': float,           # local baseline mean value in pA - can be estimated from the padding if need be
                'baseline_std': float            # local baseline standard deviation in pA - can be estimated from the padding if need be
            }

        A reasonable (though possibly inefficient) implementation would acquire a list of valid event IDs in the channel and then

        .. code:: python

           indices = [[get a list of valid indices for the channel]]
           for index in indices:
               yield self.load_event(channel, index, data_filter)

        The generator should cancel and exhaust itself in the event ``True`` is passed back through generator.send()
        """
        event_indices = self.get_valid_indices(channel)
        if event_indices is not None:
            for index in event_indices:
                response = yield self.load_event(channel, index, data_filter)
                abort = bool(response) if response is not None else False
                if abort is True:
                    break

    @abstractmethod
    def get_channels(self) -> List[int]:
        """
        :return: keys of valid channels in the reader
        :rtype: List[int]

        **Purpose:** Get a list of all valid channel identifiers in the dataset
        """
        pass

    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Clean up any open file handles or memory on app exit.

        This is called during app exit or plugin deletion to ensure proper cleanup of resources that could otherwise leak. Do this for all channels if no channel is specified, otherwise limit your closure to the specified channel. If no such operation is needed, it suffices to ``pass``.
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

    # Utility functions, specific to subclasses as needed
