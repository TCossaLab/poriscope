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

import logging
import warnings
from typing import Dict, List, Optional, Union

import numpy as np
import numpy.typing as npt
from typing_extensions import override

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventFitter import MetaEventFitter

Numeric = Union[int, float, np.number]


@inherit_docstrings
class NoFitter(MetaEventFitter):
    """
    Abstract base class to analyze and flag the start and end times of regions
    of interest in a timeseries for further analysis.
    """

    logger = logging.getLogger(__name__)

    # public API, must be overridden by subclasses:
    @log(logger=logger)
    @override
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone=False,
    ):
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

        Your Eventfinder MUST include at least the "MetaReader" key, which can be ensured by calling super().get_empty_settings(globally_available_plugins, standalone) before adding any additional settings keys

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
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        return settings

    @log(logger=logger)
    @override
    def close_resources(self, channel=None):
        """
        Perform any actions necessary to gracefully close resources before app exit
        """
        pass

    @log(logger=logger)
    @override
    def construct_fitted_event(  ##TODO
        self, channel: int, index: int
    ) -> Optional[npt.NDArray[np.float64]]:
        """
        Construct an array of data corresponding to the fit for the specified event

        :param channel: analyze only events from this channel
        :type channel: int
        :param index: the index of the target event
        :type index: int

        :return: numpy array of fitted data for the event, or None
        :rtype: Optional[npt.NDArray[np.float64]]

        :raises RuntimeError: if fitting is not complete yet
        """
        if self.sublevel_metadata == {} or not self.eventfitting_status.get(channel):
            self.logger.info(
                f"Fitting is not complete in channel {channel}, fit events first"
            )
            return None
        try:
            if self.eventloader is not None:
                self.eventloader.get_samplerate(channel)
            else:
                raise AttributeError(
                    "CUSUM cannot operate without a linked MetaEventLoader"
                )
            sublevel_start_indices = self.sublevel_starts[channel][index]
            sublevel_end_indices = self.sublevel_starts[channel][index][1:]
            sublevel_end_indices = np.append(
                sublevel_end_indices, self.event_lengths[channel][index]
            )

            sublevel_currents = self.sublevel_metadata[channel][index][
                "sublevel_current"
            ]
            data = np.zeros(sublevel_end_indices[-1], dtype=np.float64)
            for start, end, current in zip(
                sublevel_start_indices, sublevel_end_indices, sublevel_currents
            ):
                data[start:end] = current
        except KeyError:
            self.logger.info(
                f"missing event id {index} in channel {channel}: rejected event skipped"
            )
            return None
        return data

    # public API, should generally be left alone by subclasses

    # private API, MUST be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        called at the start of base class initialization
        """
        pass

    @log(logger=logger)
    @override
    def _pre_process_events(self, channel: int) -> None:
        """
        :param channel: the channel to preprocess
        :type channel: int
        """
        pass

    @log(logger=logger)
    @override
    def _locate_sublevel_transitions(
        self,
        data,
        samplerate,
        padding_before,
        padding_after,
        baseline_mean,
        baseline_std,
    ):
        """
        Get a list of indices corresponding to the starting point of all sublevels within an event. Will be pre-pended with 0 if 0 is not the first entry.
        Plugin must handle gracefully the case where any of the arguments except data are None, as not all event loaders are guaranteed to return these values.
        Raising an an acceptable handler.

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

        :raises ValueError: if the event is rejected. Note that ValueError will skip and reject the event but will not stop processing of the rest of the dataset
        :raises AttributeError: if the fitting method cannot operate without provision of specific padding and baseline metadata and cannot rescue itself. This will cause a stop to processing of the dataset.
        """

        length = len(data)
        sign = np.sign(baseline_mean)
        rise_time = 0

        edges = [0]  # first sublevel starts at the start of the data block

        k = padding_before
        while data[k] * sign < baseline_mean * sign:  # find starting point
            k -= 1
            rise_time += 1
        edges = np.append(edges, k)  # add start point as an edge
        edges = np.append(edges, len(data) - padding_after - rise_time)
        edges = np.append(edges, length)  # mark the end of the event as an edge
        self.rise_time = rise_time
        return edges

    @log(logger=logger)
    @override
    def _populate_sublevel_metadata(
        self, data, samplerate, baseline_mean, baseline_std, sublevel_starts
    ):
        """
        Build a dict of lists of sublevel metadata with whatever arbitrary keys you want to consider in your event fitter. Every list must have exactly the same length as the sublevel_starts list. Note that 'index' is already handled in the base class

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
        """
        sublevel_metadata = {}

        num_states = len(sublevel_starts) - 1
        rise_time = (
            self.rise_time
        )  # multiply this if you want to ignore more in your averaging
        dt_us = 1.0 / samplerate * 1e6
        aC_pC = 1e-6

        # average the current over the sublevel, ignoring the rise time
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            sublevel_metadata["sublevel_current"] = np.array(
                [
                    (
                        np.median(
                            data[
                                int(sublevel_starts[i] + rise_time) : int(
                                    sublevel_starts[i + 1]
                                )
                            ]
                        )
                        if sublevel_starts[i] + rise_time < sublevel_starts[i + 1]
                        else data[int(sublevel_starts[i + 1]) - 1]
                    )
                    for i in range(num_states)
                ],
                dtype=np.float64,
            )

            if (
                np.absolute(
                    sublevel_metadata["sublevel_current"][0]
                    - sublevel_metadata["sublevel_current"][-1]
                )
                > 2 * baseline_std
            ):
                raise ValueError("Baseline Mismatch")

            # get the standard deviation over the sublevel, ignoring the rise time
            sublevel_metadata["sublevel_stdev"] = np.array(
                [
                    (
                        np.std(
                            data[
                                int(sublevel_starts[i] + rise_time) : int(
                                    sublevel_starts[i + 1]
                                )
                            ]
                        )
                        if sublevel_starts[i] + rise_time < sublevel_starts[i + 1]
                        else baseline_std
                    )
                    for i in range(num_states)
                ],
                dtype=np.float64,
            )

            # get the difference from the local baseline
            event_baseline = 0.5 * (
                sublevel_metadata["sublevel_current"][0]
                + sublevel_metadata["sublevel_current"][-1]
            )
            sublevel_metadata["sublevel_blockage"] = np.array(
                [
                    (
                        (
                            event_baseline
                            - np.median(
                                data[
                                    int(sublevel_starts[i] + rise_time) : int(
                                        sublevel_starts[i + 1]
                                    )
                                ]
                            )
                        )
                        * np.sign(event_baseline)
                        if sublevel_starts[i] + rise_time < sublevel_starts[i + 1]
                        else np.max(
                            np.absolute(
                                data[
                                    int(sublevel_starts[i]) : int(
                                        sublevel_starts[i + 1]
                                    )
                                ]
                                - event_baseline
                            )
                        )
                    )
                    for i in range(num_states)
                ],
                dtype=np.float64,
            )

            # get durations between sublevel start times
            sublevel_metadata["sublevel_duration"] = np.array(
                [
                    (sublevel_starts[i + 1] - sublevel_starts[i]) * dt_us
                    for i in range(num_states)
                ],
                dtype=np.float64,
            )

            # get sublevel start times
            sublevel_metadata["sublevel_start_times"] = np.array(
                sublevel_starts[:-1] * dt_us, dtype=np.float64
            )

            # get sublevel end times
            sublevel_metadata["sublevel_end_times"] = np.array(
                sublevel_starts[1:] * dt_us, dtype=np.float64
            )

            # get the maximal deviation from the event baseline for each sublevel
            sublevel_metadata["sublevel_max_deviation"] = np.array(
                [
                    np.max(
                        np.absolute(
                            data[int(sublevel_starts[i]) : int(sublevel_starts[i + 1])]
                            - event_baseline
                        )
                    )
                    for i in range(num_states)
                ],
                dtype=np.float64,
            )

            # get the ecd using raw data for each sublevel

            sublevel_metadata["sublevel_raw_ecd"] = np.array(
                [
                    np.sum(
                        np.sign(event_baseline)
                        * dt_us
                        * aC_pC
                        * (
                            event_baseline
                            - data[
                                int(sublevel_starts[i]) : int(sublevel_starts[i + 1])
                            ]
                        )
                    )
                    for i in range(num_states)
                ],
                dtype=np.float64,
            )

            # get the ecd using fitted data for each sublevel
            sublevel_metadata["sublevel_fitted_ecd"] = (
                sublevel_metadata["sublevel_blockage"]
                * sublevel_metadata["sublevel_duration"]
                * aC_pC
            )
        return sublevel_metadata

    @log(logger=logger)
    @override
    def _populate_event_metadata(
        self, data, samplerate, baseline_mean, baseline_std, sublevel_metadata
    ):
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
        """
        event_metadata = {}

        event_metadata["duration"] = np.sum(
            sublevel_metadata["sublevel_duration"][1:-1]
        )
        event_metadata["fitted_ecd"] = np.sum(
            sublevel_metadata["sublevel_fitted_ecd"][1:-1]
        )
        event_metadata["raw_ecd"] = np.sum(sublevel_metadata["sublevel_raw_ecd"][1:-1])
        event_metadata["max_blockage"] = np.max(
            sublevel_metadata["sublevel_blockage"][1:-1]
        )
        event_metadata["min_blockage"] = np.min(
            sublevel_metadata["sublevel_blockage"][1:-1]
        )
        event_metadata["max_deviation"] = np.max(
            sublevel_metadata["sublevel_max_deviation"][1:-1]
        )
        event_metadata["max_blockage_duration"] = sublevel_metadata[
            "sublevel_duration"
        ][1:-1][np.argmax(sublevel_metadata["sublevel_blockage"][1:-1])]
        event_metadata["min_blockage_duration"] = sublevel_metadata[
            "sublevel_duration"
        ][1:-1][np.argmin(sublevel_metadata["sublevel_blockage"][1:-1])]
        event_metadata["max_deviation_duration"] = sublevel_metadata[
            "sublevel_duration"
        ][1:-1][np.argmax(sublevel_metadata["sublevel_max_deviation"][1:-1])]
        event_metadata["baseline_current"] = (
            sublevel_metadata["sublevel_current"][0]
            * sublevel_metadata["sublevel_duration"][0]
            + sublevel_metadata["sublevel_current"][-1]
            * sublevel_metadata["sublevel_duration"][-1]
        ) / (
            sublevel_metadata["sublevel_duration"][0]
            + sublevel_metadata["sublevel_duration"][-1]
        )
        event_metadata["baseline_stdev"] = (
            sublevel_metadata["sublevel_stdev"][0]
            * sublevel_metadata["sublevel_duration"][0]
            + sublevel_metadata["sublevel_stdev"][-1]
            * sublevel_metadata["sublevel_duration"][-1]
        ) / (
            sublevel_metadata["sublevel_duration"][0]
            + sublevel_metadata["sublevel_duration"][-1]
        )

        return event_metadata

    @log(logger=logger)
    @override
    def _post_process_events(self, channel: int) -> None:
        """
        :param channel: the index of the channel to postprocess
        :type channel: int
        """
        pass

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass

    @log(logger=logger)
    @override
    def _define_event_metadata_types(self):
        """
        Build a dict of metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Union[int, float, str, bool]]
        """
        metadata_types = {}
        metadata_types["duration"] = float
        metadata_types["fitted_ecd"] = float
        metadata_types["raw_ecd"] = float
        metadata_types["max_blockage"] = float
        metadata_types["min_blockage"] = float
        metadata_types["max_deviation"] = float
        metadata_types["max_blockage_duration"] = float
        metadata_types["min_blockage_duration"] = float
        metadata_types["max_deviation_duration"] = float
        metadata_types["baseline_current"] = float
        metadata_types["baseline_stdev"] = float
        return metadata_types

    @log(logger=logger)
    @override
    def _define_sublevel_metadata_types(self):
        """
        Build a dict of sublevel metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_sublevel_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool. Note that this is the type of entries in the associated list,
        it should not include the list element

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Union[int, float, str, bool]]
        """
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

    @log(logger=logger)
    @override
    def _define_event_metadata_units(self):
        """
        Build a dict of metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Union[int, float, str, bool]]
        """
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

    @log(logger=logger)
    @override
    def _define_sublevel_metadata_units(self):
        """
        Build a dict of sublevel metadata units , or None if unitless. Keys must match columns defined in _populate_sublevel_metadata()
        All of this metadata must be populated during fitting.
        it should not include the list element

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Optional[str]]
        """
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
