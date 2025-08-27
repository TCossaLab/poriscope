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
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import numpy.typing as npt

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log


@inherit_docstrings
class MetaFilter(BaseDataPlugin):
    """
    :ref:`MetaFilter` is the base class for all things related to filtering and/or preprocessing raw data before it is passed to other plugins for analysis. While it is presented as a filtering method and the most common use case for it is Bessel filtering, it is not specifically limited to timeseries filtering per se, instead providing a general interface through which data can be passed or otherwise transformed before analysis.

    What you get by inheriting from MetaFilter
    ------------------------------------------

    :ref:`MetaFilter` will provide a common API with which to define data preprocessing steps that can be swapped in and out of data analysis pipelines.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, settings: Optional[dict] = None):
        """
        :param filter_params: A dict specifying the parameters of the filter to be created. Required keys depend on subclass.
        :type filter_params: dict
        :param kwargs: Additional parameters to set as attributes on the instance.
        :type kwargs: dict

        Initialize the MetaFilter instance.
        """
        super().__init__(settings)

    # public API, should usually be left alone by subclasses
    @log(logger=logger)
    def report_channel_status(self, channel: Optional[int] = None, init=False) -> str:
        """
        :param channel: channel ID
        :type channel: Optional[int]
        :param init: is the function being called as part of plugin initialization? Default False
        :type init: bool

        :return: the status of the channel as a string
        :rtype: str

        Return a string detailing any pertinent information about the status of analysis conducted on a given channel
        """
        return ""

    @log(logger=logger)
    def filter_data(self, data: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Apply the specified filter to the data, callable publicly. Actual filtering should be defined in private API.

        :param data: The data to be filtered
        :type data: npt.NDArray[np.float64]
        :return: The filtered data
        :rtype: npt.NDArray[np.float64]
        """
        return self._apply_filter(data)

    @log(logger=logger)
    def get_callable_filter(self) -> Callable:
        """
        :return: A function that can be called to filter a 1-d npt.NDArray[np.float64] object
        :rtype: Callable

        return a function that can be called to filter data on the fly using this filter object properties
        """
        return self.filter_data

    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Clean up any open file handles or memory.

        This is called during app exit or plugin deletion to ensure proper cleanup of resources that could otherwise leak. Perform any actions necessary to gracefully close resources before app exit. If channel is not None, handle only that channel, else close all of them (taking care to respect thread safety if necessary). If no such operation is needed, it suffices to ``pass``, which will be the case for most :ref:`MetaFilter` instances.


        """
        pass

    @abstractmethod
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]


        **Purpose:** Reset the state of a specific channel for a new operation or run.

        This is called any time an operation on a channel needs to be cleaned up or reset for a new run. If channel is not None, handle only that channel, else close all of them. If calling part of this plugin from different channels to do not create persistent state changes in your plugin, you can simply ``pass`` this function, which will be the case for most :ref:`MetaFilter` instances.


        """
        pass

    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool


        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).

        For plugins that do not depend on other data plugins, by default this simply returns ``False``, meaning that it is acceptable and thread-safe to run operations on different channels in different threads on this plugin. If such operation is not thread-safe, this function should be overridden to simply return ``True``. In the case where your plugin depends on another plugin (for example, event finder plugins depend on reader plugins), then your plugin should defer thread safety considerations to the plugin on which it depends.


        """
        return False

    # public API, must be implemented by subclasses
    @abstractmethod
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone=False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[ Mapping[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]

         **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaReader` subclass.


        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.

        .. code-block:: python

           settings = {
                'Parameter 1': {'Type': <int, float, str, bool>,
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
        and all MetaClass names

        These must have Type str and will cause the GUI to generate appropriate widgets to allow selection of these elements when used.

        In the case of filters, this function must implement returning of a dictionary of settings required to initialize the filter, in the specified format. Values in this dictionary can be accessed downstream through the ``self.settings`` class variable. This structure is a nested dictionary that supplies both values and a variety of information about those values, used by poriscope to perform sanity and consistency checking at instantiation. For example, the following settings would be appropriate for a low-pass Bessel filter:

        ..   code:: python

            settings = {
                "Cutoff": {
                    "Type": float,
                    "Value": None,
                    "Min": 0,
                    "Units": "Hz",
                },
                "Samplerate": {
                    "Type": float,
                    "Value": None,
                    "Min": 0,
                    "Units": "Hz",
                },
                "Poles": {
                    "Type": int,
                    "Value": 8,
                    "Options": [2, 4, 6, 8, 10],
                }
            }
            return settings
        """
        pass

    # private API, MUST be implemented by subclasses
    @abstractmethod
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations before settings are applied.

        This is called immediately at the start of class creation but before settings have been applied, and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most filters simply ``pass`` this function.
        """
        pass

    @abstractmethod
    def _finalize_initialization(self):
        """
        **Purpose:** Perform generic class construction operations after settings are applied. This function is called at the end of the :py:meth:`~poriscope.utils.MetaFilter.MetaFilter.apply_settings` function to perform additional initialization specific to the algorithm being implemented.

        Perform any initialization tasks required after settings are applied. You can access the values in the settings dict provided as needed in the class variable ``self.settings[key]['Value']`` where ``key`` corresponds to the keys in the provided settings dict (as provided to :py:meth:`~poriscope.utils.MetaFilter.MetaFilter.apply_settings` or to the constructor). You can freely make class variables here and you can assume (if using the poriscope app) that this will only be called from a single thread. .

        Should Raise if initialization fails.
        """
        pass

    @abstractmethod
    def _apply_filter(self, data: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        :param data: The data to be filtered
        :type data: npt.NDArray[np.float64]
        :return: The filtered data
        :rtype: npt.NDArray[np.float64]


        **Purpose:** Called to actually filter or otherwise preprocess data

        Take in a 1D timeseries and apply the filter or preprocessing step provided by your plugin.

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

    # private API, should mostly be left alone

    # Utility functions, specific to subclasses as needed
