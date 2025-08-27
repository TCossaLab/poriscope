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

import gc
import logging
from abc import abstractmethod
from collections.abc import Iterable
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Type, Union

import numpy as np
import numpy.typing as npt

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventLoader import MetaEventLoader

Numeric = Union[int, float, np.number]


@inherit_docstrings
class MetaEventFitter(BaseDataPlugin):
    """
    :ref:`MetaEventFitter` is the base class for fitting events within your nanopore data to extract physical insights from the details of translocation events. :ref:`MetaEventFitter` depends on and is linked at instantiation to a :ref:`MetaEventLoader` subclass instance that serves as its source of event data, meaning that creating and using one of these plugins requires that you first instantiate an event loader. :ref:`MetaEventFinder` can in turn be the child object of :ref:`MetaDatabaseWriter` subclass isntance for downstream saving of the metadata extracted by the fits.

    What you get by inheriting from MetaEventFitter
    -----------------------------------------------

    :ref:`MetaEventFitter` provides a common and intuitive API through which to fit and extract metadata from nanopore events (whatever that means for you). In practice, typically means fitting sublevels, peaks, or other features of interest within your event for downstream postprocessing, visualization, and statistical analysis. The nanopore field has produced numerous methods of fitting nanopore data over the years. All of them could be implemented as subclasses of this base class in order to fit them into the overall poriscope workflow.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, settings: Optional[dict] = None) -> None:
        """
        Initialize the MetaEventFinder instance.
        """

        super().__init__(settings)
        self.event_metadata: Dict[int, Dict[int, dict[str, Any]]] = {}
        self.sublevel_metadata: Dict[int, Dict[int, dict[str, Any]]] = {}
        self.sublevel_starts: Dict[int, Dict[int, Any]] = {}
        self.event_lengths: Dict[int, Dict[int, int]] = {}
        self.eventfitting_status: Dict[int, bool] = {}
        self.rejected: Dict[int, Dict[str, int]] = {}
        self.applied_filters: Dict[
            int, Optional[Callable[[npt.NDArray[np.float64]], npt.NDArray[np.float64]]]
        ] = {}

        self.event_metadata_types: Dict[str, Type[Union[int, float, str, bool]]] = {}
        self.event_metadata_units: Dict[str, Optional[str]] = {}
        self.sublevel_metadata_types: Dict[str, Type[Union[int, float, str, bool]]] = {}
        self.sublevel_metadata_units: Dict[str, Optional[str]] = {}

        self.eventloader: Optional[MetaEventLoader] = None

        self._define_metadata_types()
        self._define_metadata_units()

    # public API, must be overridden by subclasses:
    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        :param channel: the channel identifier
        :type channel: Optional[int]

        **Purpose:** Clean up any open file handles or memory.

        This is called during app exit or plugin deletion to ensure proper cleanup of resources that could otherwise leak. Perform any actions necessary to gracefully close resources before app exit. If channel is not None, handle only that channel, else close all of them (taking care to respect thread safety if necessary). If no such operation is needed, it suffices to ``pass``.
        """
        pass

    @abstractmethod
    def construct_fitted_event(
        self, channel: int, index: int
    ) -> Optional[npt.NDArray[np.float64]]:
        """
        :param channel: analyze only events from this channel
        :type channel: int
        :param index: the index of the target event
        :type index: int

        :return: numpy array of fitted data for the event, or None
        :rtype: Optional[npt.NDArray[np.float64]]

        :raises RuntimeError: if fitting is not complete yet

        **Purpose:** Construct an array of data corresponding to the fit for the specified event.

        Return a numpy array of floats that corresponds 1:1 to the underlying data, but which shows the fit instead of the raw data. What this means practically depends on what you are fitting, but the returned array must have length equal to the length of the raw data that went into the fit.
        """
        pass

    # public API, should generally be left alone by subclasses
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

        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaEventFinder` subclass.

        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.

        Your Eventfitter MUST include at least the "MetaEventLoader" key, which can be ensured by calling ``settings = super().get_empty_settings(globally_available_plugins, standalone)`` before adding any additional settings keys

        This function must implement returning of a dictionary of settings required to initialize the filter, in the specified format. Values in this dictionary can be accessed downstream through the ``self.settings`` class variable. This structure is a nested dictionary that supplies both values and a variety of information about those values, used by poriscope to perform sanity and consistency checking at instantiation.

        While this function is technically not abstract in :ref:`MetaEventFinder`, which already has an implementation of this function that ensures that settings will have the required :ref:`MetaReader` key available to users, in most cases you will need to override it to add any other settings required by your subclass. If you need additional settings, which you almost ccertainly do, you **MUST** call ``super().get_empty_settings(globally_available_plugins, standalone)`` **before** any additional code that you add. For example, your implementation could look like this:

        .. code:: python

            settings = super().get_empty_settings(globally_available_plugins, standalone)
            settings["Threshold"] = {"Type": float,
                                    "Value": None,
                                    "Min": 0.0,
                                    "Units": "pA"
                                    }
            settings["Min Duration"] = {"Type": float,
                                        "Value": 0.0,
                                        "Min": 0.0,
                                        "Units": "us"
                                        }
            settings["Max Duration"] = {"Type": float,
                                        "Value": 1000000.0,
                                        "Min": 0.0,
                                        "Units": "us"
                                        }
            settings["Min Separation"] = {"Type": float,
                                            "Value": 0.0,
                                            "Min": 0.0,
                                            "Units": "us"
                                        }
            return settings

        which will ensure that your have the 3 keys specified above, as well as an additional key, ``"MetaReader"``, as required by eventfinders. In the case of categorical settings, you can also supply the "Options" key in the second level dictionaries.
        """

        eventloader_options: Optional[List[str]] = []
        if globally_available_plugins:
            eventloader_options = globally_available_plugins.get("MetaEventLoader")
        if eventloader_options == [] and not standalone:
            raise KeyError(
                "Cannot instantiate an eventfitter without first instantiating an event loader"
            )
        elif standalone:
            eventloader_options = None
        settings: Dict[str, Dict[str, Any]] = {
            "MetaEventLoader": {
                "Type": str,
                "Value": (
                    eventloader_options[0] if eventloader_options is not None else ""
                ),
                "Options": eventloader_options,
            }
        }
        return settings

    @log(logger=logger)
    def get_plot_features(self, channel: int, index: int) -> Tuple[
        Optional[List[float]],
        Optional[List[float]],
        Optional[List[Tuple[float, float]]],
        Optional[List[str]],
        Optional[List[str]],
    ]:
        """
        :param channel: analyze only events from this channel
        :type channel: int
        :param index: the index of the target event
        :type index: int

        :return: a list of x locations to plot vertical lines, a list of y locations to plot horizontal lines, a list of (x,y) tuples on which to plot dots, labels for the vertical lines, labels for the horizontal lines.
        :rtype: Tuple[Optional[List[float]], Optional[List[float]], Optional[List[Tuple[float,float]]], Optional[List[str]], Optional[List[str]]]

        :raises RuntimeError: if fitting is not complete yet

        **Purpose:** Flag features of interest on an event for display on plots

        This is an optional function is used to Get a list of horizontal and vertical lines, as well as a list of points, and associated labels for the lines, to overlay on the graph generated by construct_fitted_event(). If no features need to be highlighted, you can return None for that elements. Otherwise, the list of horizonal lines must match in length ot the list of labels for it, etc. A subset of labels can be None, but if a list is returned, it must match the length of the corresponding list of features.
        """
        return None, None, None, None, None

    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool

        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).

        By default, eventfitter plugins defer to the thread safety of their child :ref:`MetaEventLoader` instance. If any operation in your event finder is not thread-safe independent of the child reader object, this function should be overridden to simply return ``True``. Most event loaders are thread-safe since reading from a file on disk is usually so, and therefore no override is necessary. Take care to verify that the :ref:`MetaReader`: subclass instance on which this object depends is also threadsafe by calling ``self.eventloader.force_serial_channel_operations()`` to check.
        """
        serial = False
        try:
            if self.eventloader is not None:
                serial = self.eventloader.force_serial_channel_operations()
        except Exception as e:
            serial = False
            self.logger.info(
                f"Unable to check if serial mode is necessary for {self.__class__.__name__}, defaulting to {serial}: {str(e)}"
            )
        return serial

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
        if self.eventloader is None:
            raise RuntimeError("Event loader has not been initialized.")
        if channel is None:
            report = ""
            for ch in self.get_channels():
                report += self.report_channel_status(ch, init)
            return report
        else:
            if init:
                return ""
            else:
                if self.eventfitting_status.get(channel):
                    report = f"\nCh{channel}: {len(self.event_metadata[channel])}/{self.eventloader.get_num_events(channel)} good fits\n"
                    if self.rejected.get(channel) is not None:
                        report += "Rejected Events:\n"
                        report += "\n".join(
                            f"{key}: {value}"
                            for key, value in self.rejected[channel].items()
                        )
                    return report
                else:
                    return f"Ch{channel}: fitting incomplete"

    @log(logger=logger)
    def reset_channel(self, channel=None) -> None:
        """
        :param channel: the channel identifier
        :type channel: Optional[int]

        **Purpose:** Reset the state of a specific channel for a new operation or run, or all of them if no channel is specified.

        :ref:`MetaEventFitter` already has an implementation of this function, but you may override it is you need to do further resetting beyond what is included in :py:meth:`~poriscope.utils.MetaEventFitter.MetaEventFitter.reset_channel` already.

        .. warning::

            This function implements core functionality required for broader plugin integration into Poriscope. If you do need to override it, you **MUST** call ``super().reset_channel(channel)`` **before** any additional code that you add and it is on you to ensure that your additional code does not conflict with the implementation in :ref:`MetaEventFinder`.
        """
        try:
            self.sublevel_metadata.pop(channel)
        except KeyError:
            pass
        try:
            self.event_metadata.pop(channel)
        except KeyError:
            pass
        try:
            self.rejected.pop(channel)
        except KeyError:
            pass
        try:
            self.eventfitting_status[channel] = False
        except KeyError:
            pass
        gc.collect()

    @log(logger=logger)
    def get_samplerate(self, channel: int) -> float:
        """
        :param channel: the channel index
        :type channel: int

        :return: the samplerate of the associated event loader object
        :rtype: float

        Return the samplerate of the associated reader object.
        """
        if self.eventloader is None:
            raise RuntimeError("Event loader has not been initialized.")
        return self.eventloader.get_samplerate(channel)

    @log(logger=logger)
    def get_metadata_columns(self, channel: int) -> List[str]:
        """
        :param channel: analyze only events from this channel
        :type channel: int

        :return: a list of column names
        :rtype: List[str]

        Get a list of event metadata column variables
        """
        if self.eventfitting_status.get(channel) is True:
            return list(self.event_metadata[channel][0].keys())
        raise RuntimeError(
            "Unable to get metatata column names. Fitting has not finished on any channel, please try again after fitting is complete"
        )

    @log(logger=logger)
    def get_sublevel_columns(self, channel: int) -> List[str]:
        """
        Get a list of event metadata column variables

        :param channel: analyze only events from this channel
        :type channel: int

        :return: a list of column names
        :rtype: List[str]
        """
        if self.eventfitting_status.get(channel) is True:
            return list(self.sublevel_metadata[channel][0].keys())
        raise RuntimeError(
            "Unable to get metatata column names. Fitting has not finished on any channel, please try again after fitting is complete"
        )

    @log(logger=logger)
    def get_event_metadata_types(self) -> Dict[str, Type[Union[int, float, str, bool]]]:
        """
        Return a dict of sublevel metadata along with associated datatypes for use by the database writer downstream.

        :return: a dict of event metadata types
        :rtype: Dict[str, Union[int, float, str, bool]]
        """
        return self.event_metadata_types

    @log(logger=logger)
    def get_event_metadata_units(self) -> Dict[str, Optional[str]]:
        """
        Return a dict of sublevel metadata units for use by the database writer downstream.

        :return: a dict of event metadata units
        :rtype: Dict[str, Optional[str]]
        """
        return self.event_metadata_units

    @log(logger=logger)
    def get_sublevel_metadata_types(
        self,
    ) -> Dict[str, Type[Union[int, float, str, bool]]]:
        """
        Assemble a dict of sublevel metadata along with associated datatypes for use by the database writer downstream.

        :return: a dict of event metadata types
        :rtype: Dict[str, Union[int, float, str, bool]]
        """
        return self.sublevel_metadata_types

    @log(logger=logger)
    def get_sublevel_metadata_units(self) -> Dict[str, Optional[str]]:
        """
        Assemble a dict of sublevel metadata units for use by the database writer downstream.

        :return: a dict of sublevel metadata units
        :rtype: Dict[str, Optional[str]]
        """
        return self.sublevel_metadata_units

    @log(logger=logger)
    def fit_events(
        self,
        channel: int,
        silent: bool = False,
        data_filter: Optional[Callable] = None,
        indices: Optional[List[int]] = None,
    ) -> Generator[float, Optional[bool], None]:
        """
        Set up a generator that will walk through all provided events and calculate metadata relating to the sublevels, yielding its percentage completion each time next() is called on it.
        If silent flag is set, run through without yielding progress reports on the first call to next(). Once StopIteration is reached, internal
        lists of event metadata will be populated as entries in a dict keyed by event id.

        :param channel: analyze only events from this channel
        :type channel: int
        :param silent: indicate whether or not to report progress, default false
        :type silent: bool
        :param data_filter: An optional function to call to preprocess the data before looking for events, usually a filter
        :type data_filter: Callable[[npt.NDArray[np.float64]],npt.NDArray[np.float64]]
        :param indices: a list of indices to fit, ignoring the rest. Empty list fits all available indices.
        :type indices: List[int]
        :return: Yield completion fraction on each iteration.
        :rtype: Generator[float, Optional[bool], None]
        """
        if self.eventloader is None:
            raise RuntimeError("Event loader has not been initialized.")

        total_events = self.eventloader.get_num_events(channel)
        if indices is None:
            indices = list(range(total_events))
        else:
            total_events = len(indices)

        self.sublevel_starts[channel] = {}
        self.event_metadata[channel] = {}
        self.event_lengths[channel] = {}
        self.sublevel_metadata[channel] = {}
        self.rejected[channel] = {}
        self.eventfitting_status[channel] = False
        samplerate = self.eventloader.get_samplerate(channel)
        self.applied_filters[channel] = data_filter

        fitted = 0
        self._pre_process_events(channel)

        abort = False
        for index in indices:
            self.logger.info(index / total_events)
            self.event_metadata[channel][index] = {}
            self.sublevel_metadata[channel][index] = {}

            event_id = index

            self.event_metadata[channel][index]["channel_id"] = channel
            self.event_metadata[channel][index]["event_id"] = event_id

            try:
                event = self.eventloader.load_event(channel, index, data_filter)
            except IndexError:
                self.event_metadata[channel].pop(index)
                self.sublevel_metadata[channel].pop(index)
                total_events -= 1
                continue
            data = event["data"]
            absolute_start_raw = event.get("absolute_start")
            if not isinstance(absolute_start_raw, (int, float)):
                raise ValueError("absolute_start must be numeric")
            absolute_start = float(absolute_start_raw)
            raw_padding_before = event.get("padding_before")
            raw_padding_after = event.get("padding_after")

            padding_before: Optional[int] = None
            padding_after: Optional[int] = None

            if raw_padding_before is not None:
                if isinstance(raw_padding_before, int):
                    padding_before = raw_padding_before
                elif isinstance(raw_padding_before, float):
                    padding_before = int(raw_padding_before)
                else:
                    raise TypeError("padding_before must be int, float, or None")

            if raw_padding_after is not None:
                if isinstance(raw_padding_after, int):
                    padding_after = raw_padding_after
                elif isinstance(raw_padding_after, float):
                    padding_after = int(raw_padding_after)
                else:
                    raise TypeError("padding_after must be int, float, or None")

            baseline_mean = event.get("baseline_mean")
            baseline_std = event.get("baseline_std")

            if not hasattr(data, "__len__"):
                raise TypeError("Event data must be sized")
            self.event_lengths[channel][index] = len(data)

            self.event_metadata[channel][index]["start_time"] = (
                absolute_start / samplerate
            )

            # find the changepoints in the event between sublevels, whatever that means
            try:
                sublevel_starts = self._locate_sublevel_transitions(
                    data,
                    samplerate,
                    padding_before,
                    padding_after,
                    baseline_mean,
                    baseline_std,
                )

            except ValueError as e:
                self.rejected[channel][str(e)] = (
                    self.rejected[channel].get(str(e), 0) + 1
                )
                self.logger.info(
                    f"Event {index} in channel {channel} was rejected from fitting: {e}. No further warnings of this type will be issue for this channel."
                )
                self.event_metadata[channel].pop(index)
                self.sublevel_metadata[channel].pop(index)
                continue
            except Exception as e:
                self.rejected[channel][str(e)] = (
                    self.rejected[channel].get(str(e), 0) + 1
                )
                self.logger.info(
                    f"Unknown error locating sublevels transitions for event {event}: {str(e)}"
                )
                self.event_metadata[channel].pop(index)
                self.sublevel_metadata[channel].pop(index)
                continue

            if not isinstance(sublevel_starts, Iterable):
                raise ValueError(
                    "Sublevels is not an iterable. Please return a list of sublevel start points."
                )

            if len(sublevel_starts) <= 0:
                raise ValueError("Sublevels are empty.")

            # if isinstance(sublevel_starts[0], int) and sublevel_starts[0] != 0:
            #    raise ValueError('Sublevels must include the start of the data block as the start of a sublevel') #must start counting at the start of the event, crash if not since things will break downstream otherwise

            # if we do not find baseline + event + baseline for a total of three sublevels, it is not a valid event and should be skipped
            if len(sublevel_starts) <= 3:
                self.logger.info(
                    f"Event {event_id} in channel {channel} has fewer than three sublevels and is invalid, it will be skipped"
                )
                self.rejected[channel]["Too Few Levels"] = (
                    self.rejected[channel].get("Too Few Levels", 0) + 1
                )
                self.event_metadata[channel].pop(index)
                self.sublevel_metadata[channel].pop(index)
                continue

            # use the previously discovered change points to generate an arbitrary dict of sublevel metadata
            self.sublevel_starts[channel][index] = sublevel_starts
            try:
                sublevel_metadata = self._populate_sublevel_metadata(
                    data, samplerate, baseline_mean, baseline_std, sublevel_starts
                )
            except ValueError as e:
                self.rejected[channel][str(e)] = (
                    self.rejected[channel].get(str(e), 0) + 1
                )
                self.logger.info(
                    f"Error populating sublevel metadata for event {event}: {str(e)}"
                )
                self.event_metadata[channel].pop(index)
                self.sublevel_metadata[channel].pop(index)
                continue
            except Exception as e:
                self.rejected[channel][str(e)] = (
                    self.rejected[channel].get(str(e), 0) + 1
                )
                self.logger.info(
                    f"Unknown error populating sublevel metadata for event {event}: {str(e)}"
                )
                self.event_metadata[channel].pop(index)
                self.sublevel_metadata[channel].pop(index)
                continue

            for key, val in sublevel_metadata.items():
                if len(val) != len(sublevel_starts) - 1:
                    self.rejected[channel]["Level Count Mismatch"] = (
                        self.rejected[channel].get("Level Count Mismatch", 0) + 1
                    )
                    self.logger.error(
                        f"Event {event_id} has in channel {channel} fewer entries for {key} ({len(val)} than sublevels ({len(sublevel_starts)} and is invalid"
                    )
                    self.event_metadata[channel].pop(index)
                    self.sublevel_metadata[channel].pop(index)
                    continue
                else:
                    self.sublevel_metadata[channel][index][key] = val

            self.sublevel_metadata[channel][index]["event_id"] = np.array(
                [event_id] * (len(sublevel_starts) - 1), dtype=np.int64
            )
            self.sublevel_metadata[channel][index]["channel_id"] = np.array(
                [channel] * (len(sublevel_starts) - 1), dtype=np.int64
            )
            self.sublevel_metadata[channel][index]["level_id"] = np.array(
                range(len(sublevel_starts) - 1), dtype=np.int64
            )
            self.sublevel_metadata[channel][index]["levels_left"] = (
                self.sublevel_metadata[channel][index]["level_id"][::-1]
            )

            if "sublevel_duration" not in self.sublevel_metadata[channel][index].keys():
                raise KeyError(
                    "Event fitters must define and poopulate sublevel_duration column in the sublevels table. The first entry must correspond to the padding before, and the last entry to the padding after the event"
                )

            # use the sublevel metadata to finalize event-level metadata
            try:
                event_metadata = self._populate_event_metadata(
                    data, samplerate, baseline_mean, baseline_std, sublevel_metadata
                )
            except ValueError as e:
                self.rejected[channel][str(e)] = (
                    self.rejected[channel].get(str(e), 0) + 1
                )
                self.logger.info(
                    f"Error populating sublevel metadata for event {event}: {str(e)}"
                )
                self.event_metadata[channel].pop(index)
                self.sublevel_metadata[channel].pop(index)
                continue
            except Exception as e:
                self.rejected[channel][str(e)] = (
                    self.rejected[channel].get(str(e), 0) + 1
                )
                self.logger.info(
                    f"Unknown error populating sublevel metadata for event {event}: {str(e)}"
                )
                self.event_metadata[channel].pop(index)
                self.sublevel_metadata[channel].pop(index)
                continue

            self.event_metadata[channel][index]["num_sublevels"] = (
                len(sublevel_starts) - 1
            )
            for key, val in event_metadata.items():
                self.event_metadata[channel][index][key] = val

            # yield progress at each iteration
            if not silent:
                fitted += 1
                response = yield fitted / total_events
                abort = bool(response) if response is not None else False
                if abort is True:
                    break
        if abort is False:
            self._post_process_events(channel)
            self.eventfitting_status[channel] = True
        else:
            self.reset_channel(channel)
        yield 1.0

    @log(logger=logger)
    def get_event_metadata_generator(self, channel: int) -> Generator[
        Tuple[
            dict,
            dict,
            npt.NDArray[np.float64],
            npt.NDArray[np.float64],
            npt.NDArray[np.float64],
        ],
        None,
        None,
    ]:
        """
        Set up a generator that will return the metadata dictionary for events in sequence for a given channel

        :param channel: analyze only events from this channel
        :type channel: int

        :return: A Generator that gives data in an event and the index of the start of that event relative to the start of the file. If offset was provided during analysis, it will be included here.
        :rtype: Generator[dict, None, None]
        """
        if self.eventloader is None:
            raise AttributeError("Event loader has not been initialized.")

        for i in sorted(self.event_metadata.get(channel, {})):
            yield self.get_single_event_metadata(channel, i)

    @log(logger=logger)
    def get_channels(self):
        """
        get the number of available channels in the reader
        """
        if self.eventloader is None:
            raise AttributeError("Event loader has not been initialized.")
        return self.eventloader.get_channels()

    @log(logger=logger)
    def get_num_events(self, channel) -> int:
        """
        get the number of events found in the channel if eventfinding has finished

        :param channel: analyze only events from this channel
        :type channel: int

        :return: number of succesfully fitted events in the channel
        :rtype: int

        :raises RuntimeError: if called before eventfinding is completed in the given channel
        """
        if self.eventloader is None:
            raise AttributeError("Event loader has not been initialized.")
        if self.get_eventfitting_status(channel):
            return len(self.event_metadata[channel])
        else:
            raise RuntimeError(f"Event fitting not complete for channel {channel}")

    @log(logger=logger)
    def get_single_event_metadata(self, channel: int, index: int) -> Tuple[
        dict,
        dict,
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        Optional[npt.NDArray[np.float64]],
    ]:
        """
        Return the metadata for the event and sublevels of the event, as well as the raw and fitted data.

        :param channel: Channel from which to retrieve event
        :param index: Index of the event to retrieve
        :return: Tuple of event metadata, sublevel metadata, filtered data, raw data, and fitted data
        :raises RuntimeError: if fitting is not complete or data is missing
        """
        if not self.get_eventfitting_status(channel):
            raise RuntimeError(f"Event fitting not complete for channel {channel}")

        if self.eventloader is None:
            raise RuntimeError("Event loader is not initialized.")

        try:
            data_filter = self.applied_filters.get(channel)
            return (
                self.event_metadata[channel][index],
                self.sublevel_metadata[channel][index],
                self.eventloader.load_event(channel, index, data_filter)["data"],
                self.eventloader.load_event(channel, index, None)["data"],
                self.construct_fitted_event(channel, index),
            )
        except KeyError as e:
            self.logger.info(
                f"Unable to fetch event {index} from channel {channel}: {str(e)}"
            )
            raise RuntimeError(
                f"Missing event data for channel {channel}, index {index}"
            )

    @log(logger=logger)
    def get_eventfitting_status(self, channel: int) -> bool:
        """
        is fitting complete in the channel?

        :param channel: the channel identifier
        :type channel: int

        :return: True if fitting is done, False otherwise
        :rtype: bool
        """
        return self.eventfitting_status.get(channel) is True

    # private API, MUST be implemented by subclasses
    @abstractmethod
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations.

        All data plugins have this function and must provide an implementation. This is called immediately at the start of class creation and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most readers simply ``pass`` this function.
        """
        pass

    @abstractmethod
    def _pre_process_events(self, channel: int) -> None:
        """
        :param channel: the channel to pre-process
        :type channel: int

        **Purpose:** Apply any operations to the fits that need to occur before fitting occurs, for example finding the longest and shorted events. Try to avoid computationally intensive operations here if possible. Most fitters can simple ``pass``.
        """
        pass

    @abstractmethod
    def _locate_sublevel_transitions(
        self,
        data: npt.NDArray[np.float64],
        samplerate: float,
        padding_before: Optional[int],
        padding_after: Optional[int],
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
    ) -> Optional[List[Any]]:
        """
        :param data: an array of data from which to extract the locations of sublevel transitions
        :type data: npt.NDArray[np.float64]
        :param samplerate: the sampling rate
        :type samplerate: float
        :param padding_before: the number of data points before the estimated start of the event in the chunk
        :type padding_before: Optional[int]
        :param padding_after: the number of data points after the estimated end of the event in the chunk
        :type padding_after: Optional[int]
        :param baseline_mean: the local mean value of the baseline current
        :type baseline_mean: Optional[float]
        :param baseline_std: the local standard deviation of the baseline current
        :type baseline_std: Optional[float]

        :return: a list of entries that details sublevel transitions. Normally this would be as a list of ints, but can be a list of tuples or other entries if more info is needed. First entry must correspond to the start of the event.
        :rtype: Optional[List[Any]]

        :raises ValueError: if the event is rejected. Note that ValueError will skip and reject the event but will not stop processing of the rest of the dataset.
        :raises AttributeError: if the fitting method cannot operate without provision of specific padding and baseline metadata and cannot rescue itself. This will cause a stop to processing of the dataset.

        **Purpose:** Get a list of indices and optionally other metadata corresponding to the starting point of all sublevels within an event.

        In this function, you must locate and return all features that qualify as "sublevels" for downstream processing and return a list of information that identifies the starting point of those sublevevels. The first element in the list must correspond to the start of the event (e.g. the level that corresponds to the padding before the event). This list can take any form at all and will be passed verbatim to :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._populate_event_metadata` and :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._populate_sublevel_metadata`, meaning that you can encode extra information about the sublevels that you need in order to implement those functions. For example, if you have two different kinds of sublevels, you might pass a list of tuples that encode the index of the start of each sublevel along with a string representing its type, as in ``[(0, 'padding_before'), (100,'normal_blockage'), (200, 'padding_after')]``, or equivalently a dict that encodes the same information, for example ``[{'index': 0, 'type': 'padding_before'},{'index': 100, 'type': 'normal_blockage'},{'index': 200, 'type': 'padding_after'},]``. The only restrictions are that

        1. The top-level structure must be a 1D iterable
        2. Each entry must contain the index of the start of the sublevel
        3. The first entry must correspond to the start of the event

        Plugin must handle gracefully the case where any of the arguments except data are None, as not all event loaders are guaranteed to return these values.
        Raising an an acceptable handler, as it will be handled, and the event simply skipped as not fitted, in the event that this function Raises.
        """
        pass

    @abstractmethod
    def _populate_sublevel_metadata(
        self,
        data: npt.NDArray[np.float64],
        samplerate: float,
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
        sublevel_starts: List[int],
    ) -> Dict[str, npt.NDArray[Numeric]]:
        """
        :param data: an array of data from which to extract the locations of sublevel transitions
        :type data: npt.NDArray[np.float64]
        :param samplerate: the sampling rate
        :type samplerate: float
        :param baseline_mean: the local mean value of the baseline current
        :type baseline_mean: Optional[float]
        :param baseline_std: the local standard deviation of the baseline current
        :type baseline_std: Optional[float]
        :param sublevel_starts: the list of sublevel start indices located in self._locate_sublevel_transitions()
        :type sublevel_starts: List[int]

        :return: a dict of lists of sublevel metadata values, one list entry per sublevel for each piece of metadata
        :rtype: Dict[str, npt.NDArray[Numeric]]

        **Purpose:** Extract metadata for each sublevel within the event

        The ``sublevel_starts`` list corresponds verbatim to the return value of :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._locate_sublevel_transitions`. Using this information, provide values for all of the sublevle metadata required by the fitter.  This should be returned as a dict with keys that match exactly those defined in :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._define_sublevel_metadata_types` and :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._define_sublevel_metadata_units`. Values for each key should be a list of data with length exactly equal to that of ``sublevel_starts`` and types consistent with :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._define_sublevel_metadata_units`. Do not provide values for any reserved keys.
        """
        pass

    @abstractmethod
    def _define_event_metadata_types(
        self,
    ) -> Dict[str, Type[int | float | str | bool]]:
        """
        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Union[int, float, str, bool]]

        **Purpose**: Tell downstream operations what datatypes correspond to event metadata provided by this plugin

        This data plugin divides event metadata into two types: event metadata, and sublevel metadata. Event metadata refers to numbers that apply to the event as a whole (for example, its duration, its maximal blockage state, etc. - things that have a single number per event). In this function, you must supply a dictionary in which they keys are the names of the event metadata you want to fit, and the values are the primitive datatype of that piece of metadata. All of this metadata must be populated during fitting. This dict must have ths same keys as that supplied in :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._define_event_metadata_units`. Options for dtypes are int, float, str, bool - basic datatypes compatible with any downstream :ref:`MetaDatabaseWriter` subclass. For example:

        .. code:: python

            metadata_types = {}
            metadata_types["sublevel_current"] = float
            metadata_types["sublevel_stdev"] = float
            metadata_types["sublevel_blockage"] = float
            metadata_types["sublevel_duration"] = float
            metadata_types["sublevel_start_times"] = float
            metadata_types["sublevel_end_times"] = float
            metadata_types["sublevel_max_deviation"] = float
            metadata_types["sublevel_raw_ecd"] = float
            metadata_types["sublevel_fitted_ecd"] = float
            return metadata_types

        Note that the base class will add additional keys to all event metadata (so do not duplicate these keys, they are handled for you: "start_time", "num_sublevel", "event_id")
        """
        pass

    @abstractmethod
    def _define_event_metadata_units(self) -> Dict[str, Optional[str]]:
        """
        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Union[int, float, str, bool]]

        **Purpose**: Tell downstream operations what units apply to event metadata provided by this plugin

        This data plugin divides event metadata into two types: event metadata, and sublevel metadata. Event metadata refers to numbers that apply to the event as a whole (for example, its duration, its maximal blockage state, etc. - things that have a single number per event). In this function, you must supply a dictionary in which they keys are the names of the event metadata you want to fit, and the values are a string representing the units for that key. All of this metadata must be populated during fitting. This dict must have ths same keys as that supplied in :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._define_event_metadata_types`. Units can be None. For example:

        .. code:: python

            metadata_units = {}
            metadata_units["duration"] = "us"
            metadata_units["fitted_ecd"] = "pC"
            metadata_units["raw_ecd"] = "pC"
            metadata_units["max_blockage"] = "pA"
            metadata_units["min_blockage"] = "pA"
            metadata_units["max_deviation"] = "pA"
            metadata_units["max_blockage_duration"] = "us"
            metadata_units["min_blockage_duration"] = "us"
            metadata_units["max_deviation_duration"] = "us"
            metadata_units["baseline_current"] = "pA"
            metadata_units["baseline_stdev"] = "pA"
            return metadata_units

        Note that the base class will add additional keys to all event metadata (so do not duplicate these keys, they are handled for you: "start_time", "num_sublevel", "event_id")
        """
        pass

    @abstractmethod
    def _define_sublevel_metadata_types(
        self,
    ) -> Dict[str, Type[int | float | str | bool]]:
        """
        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Union[int, float, str, bool]]

        **Purpose**: Tell downstream operations what datatypes correspond to sublevel metadata provided by this plugin

        This data plugin divides event metadata into two types: event metadata, and sublevel metadata. Sublevel metadata refers to numbers that apply individual sublevels within an event (for example, the duration or blockage state of a single sublevel) as as such may have an arbitrary number of entries per event. In this function, you must supply a dictionary in which they keys are the names of the sublevel metadata you want to fit, and the values are the primitive datatype of that piece of metadata. All of this metadata must be populated during fitting. This dict must have ths same keys as that supplied in :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._define_sublevel_metadata_units`. Options for dtypes are int, float, str, bool - basic datatypes compatible with any downstream :ref:`MetaDatabaseWriter` subclass. For example:

        .. code:: python

            metadata_types = {}
            metadata_types["sublevel_current"] = float
            metadata_types["sublevel_stdev"] = float
            metadata_types["sublevel_blockage"] = float
            metadata_types["sublevel_duration"] = float
            metadata_types["sublevel_start_times"] = float
            metadata_types["sublevel_end_times"] = float
            metadata_types["sublevel_max_deviation"] = float
            metadata_types["sublevel_raw_ecd"] = float
            metadata_types["sublevel_fitted_ecd"] = float
            return metadata_types

        """
        pass

    @abstractmethod
    def _define_sublevel_metadata_units(self) -> Dict[str, Optional[str]]:
        """
        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Optional[str]]

        **Purpose**: Tell downstream operations what units apply to sublevel metadata provided by this plugin

        This data plugin divides event metadata into two types: event metadata, and sublevel metadata. Sublevel metadata refers to numbers that apply individual sublevels within an event (for example, the duration or blockage state of a single sublevel) as as such may have an arbitrary number of entries per event. In this function, you must supply a dictionary in which they keys are the names of the event metadata you want to fit, and the values are a string representing the units for that key. All of this metadata must be populated during fitting. This dict must have ths same keys as that supplied in :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._define_sublevel_metadata_types`. Unites can be None. For example:

        .. code:: python

            metadata_units = {}
            metadata_units["sublevel_current"] = "pA"
            metadata_units["sublevel_stdev"] = "pA"
            metadata_units["sublevel_blockage"] = "pA"
            metadata_units["sublevel_duration"] = "us"
            metadata_units["sublevel_start_times"] = "us"
            metadata_units["sublevel_end_times"] = "us"
            metadata_units["sublevel_max_deviation"] = "pA"
            metadata_units["sublevel_raw_ecd"] = "pC"
            metadata_units["sublevel_fitted_ecd"] = "pC"
            return metadata_units

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

    @abstractmethod
    def _populate_event_metadata(
        self,
        data: npt.NDArray[np.float64],
        samplerate: float,
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
        sublevel_metadata: Dict[str, List[Numeric]],
    ) -> Dict[str, Numeric]:
        """
        Assemble a list of metadata to save in the event database later. Note that keys 'start_time_s' and 'index' are already handled in the base class and should not be touched here.

        :param data: an array of data from which to extract the locations of sublevel transitions
        :type data: npt.NDArray[np.float64]
        :param samplerate: the sampling rate
        :type samplerate: float
        :param baseline_mean: the local mean value of the baseline current
        :type baseline_mean: Optional[float]
        :param baseline_std: the local standard deviation of the baseline current
        :type baseline_std: Optional[float]
        :param sublevel_metadata: the dict of sublevel metadata built by self._populate_sublevel_metadata()
        :type sublevel_metadata: Dict[str, List[Numeric]]

        :return: a dict of event metadata values
        :rtype: Dict[str, float]

        **Purpose:** Extract metadata for each sublevel within the event

        The ``sublevel_metadata`` list corresponds  to the return value of :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._populate_sublevel_metadata`. Using this information, provide values for all of the event metadata required by the fitter.  This should be returned as a dict with keys that match exactly those defined in :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._define_event_metadata_types` and :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._define_event_metadata_units`. Values for each key should be a single value with type consistent with :py:meth:`~poriscope.utils.MetaeventFitter.MetaeventFitter._define_sublevel_metadata_units`. Do not provide values for any reserved keys.
        """
        pass

    @abstractmethod
    def _post_process_events(self, channel: int) -> None:
        """
        :param channel: the index of the channel to preprocess
        :type channel: int

        **Purpose:** Apply any operations to the fits that need to occur after preliminary fitting is finished, for example, refining fits using information about the global dataset structure. Try to avoid computationally intensive operations here if possible. Most fitters can simple ``pass``.
        """
        pass

    # private API, should generally be left alone by subclasses
    @log(logger=logger)
    def _finalize_initialization(self) -> None:
        """
        **Purpose:** Apply application-specific settings to the plugin, if needed.

        This function is called at the end of the class constructor to perform additional initialization specific to the algorithm being implemented. If additional initialization operations are required beyond the defaults provided in :ref:`BaseDataPlugin` or :ref:`MetaEventFinder` that must occur after settings have been applied to the reader instance, you can override this function to add those operations, subject to the caveat below.

        .. warning::

            This function implements core functionality required for broader plugin integration into Poriscope. If you do need to override it, you **MUST** call ``super()._finalize_initialization()`` **before** any additional code that you add, and take care to understand the implementation of both :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.apply_settings` and :py:meth:`~poriscope.utils.MetaEventFitter.MetaEventFitter._finalize_initialization` before doing so to ensure that you are not conflicting with those functions.

        Should Raise if initialization fails.
        """
        self.eventloader = self.settings["MetaEventLoader"]["Value"]

    @log(logger=logger)
    def _validate_param_types(self, settings: dict) -> None:
        """
        Validate that the filter_params dict contains correct data types

        param settings: A dict specifying the parameters of the filter to be created. Required keys depend on subclass.
        :type settings: dict
        :raises TypeError: If the filter_params parameters are of the wrong type
        """
        super()._validate_param_types(settings)
        if settings:
            for param, val in settings.items():
                if param == "MetaEventLoader":
                    if not issubclass(val["Value"].__class__, MetaEventLoader):
                        raise TypeError(
                            "MetaEventLoader key must have as value an object that inherits from MetaEventLoader"
                        )

    @log(logger=logger)
    def _define_metadata_types(self) -> None:
        """
        Define metadata datatypes for all columns calculated by the fitter - should not be touched
        """
        self.event_metadata_types = self._define_event_metadata_types()
        self.event_metadata_types["start_time"] = float
        self.event_metadata_types["num_sublevels"] = int
        self.event_metadata_types["event_id"] = int
        self.sublevel_metadata_types = self._define_sublevel_metadata_types()

    @log(logger=logger)
    def _define_metadata_units(self) -> None:
        """
        Define metadata datatypes for all columns calculated by the fitter - should not be touched
        """
        self.event_metadata_units = self._define_event_metadata_units()
        self.event_metadata_units["start_time"] = "s"
        self.event_metadata_units["num_sublevels"] = None
        self.event_metadata_units["event_id"] = None
        self.sublevel_metadata_units = self._define_sublevel_metadata_units()

    # Utility functions, specific to subclasses as needed
