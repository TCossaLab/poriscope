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
# Nada Kerrouri

import logging
from typing import List, Mapping, Optional, Tuple, Type, Union

import numpy as np
from scipy.signal import find_peaks
from typing_extensions import override

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventFitter import MetaEventFitter

Numeric = Union[int, float, np.number]


@inherit_docstrings
class PeakFinder(MetaEventFitter):
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
        globally_available_plugins=None,
        standalone=False,
    ):
        """
        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[ Mapping[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Mapping[str, Mapping[str, Union[int, float, str, list[Union[int,float,str,None], None]]]]

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
        settings["Event Type"] = {
            "Type": str,
            "Value": "Unspecified",
            "Options": ["Unspecified", "Single Peak", "Barcode"],
        }
        settings["Min Height"] = {
            "Type": float,
            "Value": 500,
            "Min": 0.0,
            "Units": "pA",
        }
        settings["Min Prominence"] = {
            "Type": float,
            "Value": 100,
            "Min": 0.0,
            "Units": "pA",
        }
        settings["Relative Height"] = {"Type": float, "Value": 0.5, "Min": 0}
        settings["Window Length"] = {
            "Type": float,
            "Value": 25,
            "Min": 0.0,
            "Units": "μs",
        }
        settings["Width"] = {"Type": float, "Value": 0, "Min": 0.0, "Units": "μs"}
        settings["Min Distance"] = {
            "Type": float,
            "Value": 1,
            "Min": 0.0,
            "Units": "μs",
        }
        settings["Max Unfolded"] = {
            "Type": float,
            "Value": 750,
            "Min": 0.1,
            "Units": "pA",
        }
        settings["Number of peaks"] = {"Type": int, "Value": 1, "Min": 1}
        settings["Plot Features"] = {
            "Type": str,
            "Value": "Some",
            "Options": ["All", "Some", "None"],
        }
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
    def construct_fitted_event(self, channel, index):
        """
        Construct an array of data corresponding to the peaks for the specified event

        :param channel: analyze only events from this channel
        :type channel: int
        :param index: the index of the target event
        :type index: int

        :return: numpy array of peaked data for the event, or None
        :rtype: Optional[npt.NDArray[np.float64]]

        :raises RuntimeError: if peakfinding is not complete yet
        """
        if (
            not self.sublevel_metadata
            or channel not in self.sublevel_metadata
            or not self.eventfitting_status.get(channel)
        ):
            self.logger.info(
                f"Peak finding is not complete in channel {channel}, find peaks first"
            )
            return None
        try:
            if self.eventloader is None:
                raise RuntimeError(
                    "Event loader is not set; cannot retrieve samplerate."
                )
            samplerate = self.eventloader.get_samplerate(channel)
            dt_us = 1.0 / samplerate * 1e6
            # Convert times to sample indices
            sublevel_start_indices = [
                int(sublevel_duration / dt_us)
                for sublevel_duration in self.sublevel_metadata[channel][index][
                    "sublevel_start_times"
                ]
            ]
            sublevel_end_indices = [
                int(sublevel_duration / dt_us)
                for sublevel_duration in self.sublevel_metadata[channel][index][
                    "sublevel_end_times"
                ]
            ]
            sublevel_currents = self.sublevel_metadata[channel][index][
                "sublevel_current"
            ]
            baseline = self.event_metadata[channel][index]["baseline"]
            # Peak-related data
            peak_heights = [
                loc for loc in self.sublevel_metadata[channel][index]["peak_height"]
            ]
            peak_rips = [
                int(loc / dt_us) if not np.isnan(loc) else None
                for loc in self.sublevel_metadata[channel][index]["right_ips"]
            ]
            peak_lips = [
                int(loc / dt_us) if not np.isnan(loc) else None
                for loc in self.sublevel_metadata[channel][index]["left_ips"]
            ]
            peak_fil = [
                loc for loc in self.sublevel_metadata[channel][index]["filtered"]
            ]
            # Default array
            data = np.zeros(sublevel_end_indices[-1], dtype=np.float64)

            # Build data with sublevels and peaks (only if filtered == 3)
            for start, end, current, height, rips, lips, fil in zip(
                sublevel_start_indices,
                sublevel_end_indices,
                sublevel_currents,
                peak_heights,
                peak_rips,
                peak_lips,
                peak_fil,
            ):
                # Fill baseline sublevel current
                data[start:end] = current
                # Plot peak only if filtered == 3 and lips/rips exist
                if fil == 3:
                    data[lips:rips] = baseline - np.sign(current) * height

        except KeyError:
            self.logger.info(
                f"missing event id {index} in channel {channel}: rejected event skipped"
            )
            return None

        return data

    # public API, should generally be left alone by subclasses
    @log(logger=logger)
    def get_plot_features(self, channel: int, index: int) -> Tuple[
        Optional[List[float]],  # peaks_filtered
        Optional[List[float]],  # bases
        Optional[List[Tuple[float, float]]],  # peaks
        Optional[List[str]],  # vlabel
        Optional[List[str]],  # hlabel
        Optional[List[str]],  # plabel
    ]:
        """
        Get a list of horizontal and vertical lines and associated labels to overlay on the graph generated by construct_fitted_event()

        :param channel: analyze only events from this channel
        :type channel: int
        :param index: the index of the target event
        :type index: int

        :return: a list of x locations to plot vertical lines and a list of y locations to plot horizontal lines, labels for the vertical lines, labels for the horizontal lines. Must be lists of equal length, or None
        :rtype: Tuple[Optional[List[float]], Optional[List[float]], Optional[List[str]], Optional[List[str]]]

        :raises RuntimeError: if fitting is not complete yet
        """

        if self.sublevel_metadata == {} or not self.eventfitting_status.get(channel):
            self.logger.info(
                f"Peak finding is not complete in channel {channel}, find peaks first"
            )
            return None, None, None, None, None, None
        try:
            if (
                self.settings is None
                or self.settings.get("Plot Features", {}).get("Value") == "None"
            ):
                return None, None, None, None, None, None

            # Initializing arrays
            bases = []
            peaks = []
            vlabel = []
            hlabel = []
            plabel = []
            peaks_filtered = []
            j = 1

            # some gauges for debugging
            bases.append(self.event_metadata[channel][index]["baseline"])
            hlabel.append("Baseline")
            bases.append(
                self.event_metadata[channel][index]["unfolded_level"]
                + self.event_metadata[channel][index]["baseline"]
            )
            hlabel.append("unfolded level")
            bases.append(
                self.event_metadata[channel][index]["unfolded_level"]
                + self.event_metadata[channel][index]["baseline"]
                + self.event_metadata[channel][index]["baseline_std"]
            )
            hlabel.append("unfolded level + std")
            bases.append(
                self.event_metadata[channel][index]["unfolded_level"]
                + self.event_metadata[channel][index]["baseline"]
                - 2 * self.event_metadata[channel][index]["baseline_std"]
            )
            hlabel.append("unfolded level - 2std")

            for i in range(len(self.sublevel_metadata[channel][index]["right_ips"])):
                if self.sublevel_metadata[channel][index]["peak_id"][i] is not None:
                    # ips.append(self.sublevel_metadata[channel][index]['left_ips'][i]) #can be seen in event construct instead
                    # ips.append(self.sublevel_metadata[channel][index]['right_ips'][i])
                    bases.append(
                        self.sublevel_metadata[channel][index]["left_base"][i]
                        + self.event_metadata[channel][index]["baseline"]
                    )
                    bases.append(
                        self.sublevel_metadata[channel][index]["right_base"][i]
                        + self.event_metadata[channel][index]["baseline"]
                    )
                    # vlabel.append("Left ips #"+str(i+1))
                    # # vlabel.append("Right ips #"+str(i+1))
                    hlabel.append("Right base #" + str(j))
                    hlabel.append("Left base #" + str(j))
                    peaks.append(
                        (
                            self.sublevel_metadata[channel][index]["peak_loc"][i],
                            self.sublevel_metadata[channel][index]["peak_height"][i]
                            + self.event_metadata[channel][index]["baseline"],
                        )
                    )
                    plabel.append("Peak #" + str(j))
                    if (
                        self.sublevel_metadata[channel][index]["filtered"][i] != 0
                        and self.sublevel_metadata[channel][index]["filtered"][i] != -1
                    ):
                        peaks_filtered.append(
                            self.sublevel_metadata[channel][index]["peak_loc"][i]
                        )
                        vlabel.append(
                            "Type "
                            + str(self.sublevel_metadata[channel][index]["filtered"][i])
                            + " Peak"
                        )
                    j += 1

            value = self.settings.get("Plot Features", {}).get("Value")
            if value == "Some":
                bases = bases[:2]
                hlabel = hlabel[:2]

        except KeyError:
            self.logger.info(
                f"missing event id {index} in channel {channel}: rejected event skipped"
            )
            return None, None, None, None, None, None

        return peaks_filtered, bases, peaks, vlabel, hlabel, plabel

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


        :return: a list of integers corresponding to sublevel transitions
        :rtype: List[int]

        :raises ValueError: if the event is rejected. Note that ValueError will skip and reject the event but will not stop processing of the rest of the dataset
        :raises AttributeError: if the fitting method cannot operate without provision of specific padding and baseline metadata and cannot rescue itself. This will cause a stop to processing of the dataset.
        """
        dt_us = 1.0 / samplerate * 1e6

        min_height = self.settings["Min Height"]["Value"]
        min_prom = self.settings["Min Prominence"]["Value"]
        wlen = int(self.settings["Window Length"]["Value"] / dt_us)
        width = int(self.settings["Width"]["Value"] / dt_us)
        min_dist = int(self.settings["Min Distance"]["Value"] / dt_us)
        rel_height = self.settings["Relative Height"]["Value"]
        max_unfolded = self.settings["Max Unfolded"]["Value"]

        if baseline_std is None:  # the rest of the args can be None without issue
            if padding_before is not None:
                baseline_std = np.std(data[:padding_before])
            elif padding_after is not None:
                baseline_std = np.std(data[-padding_after:])
            else:
                raise ValueError(
                    "Peankfinder requires that the standard deviation of the local baseline be reported and is unable to calculate it for this event"
                )

        """
            scipy find_peaks

            Parameters:

            x:sequence
            A signal with peaks.

            height:number or ndarray or sequence, optional
            Required height of peaks.
            Either a number, None, an array matching x or a 2-element sequence of the former.
            The first element is always interpreted as the minimal and the second, if supplied, as the maximal required height.

            threshold:number or ndarray or sequence, optional
            Required threshold of peaks, the vertical distance to its neighboring samples.
            Either a number, None, an array matching x or a 2-element sequence of the former.
            The first element is always interpreted as the minimal and the second, if supplied, as the maximal required threshold.

            distance:number, optional
            Required minimal horizontal distance (>= 1) in samples between neighbouring peaks.
            Smaller peaks are removed first until the condition is fulfilled for all remaining peaks.

            prominence:number or ndarray or sequence, optional
            Required prominence of peaks.
            Either a number, None, an array matching x or a 2-element sequence of the former.
            The first element is always interpreted as the minimal and the second, if supplied, as the maximal required prominence.

            width:number or ndarray or sequence, optional
            Required width of peaks in samples.
            Either a number, None, an array matching x or a 2-element sequence of the former.
            The first element is always interpreted as the minimal and the second, if supplied, as the maximal required width.

            wlen:int, optional
            Used for calculation of the peaks prominences, thus it is only used if one of the arguments prominence or width is given.
            See argument wlen in peak_prominences for a full description of its effects.

            rel_height:float, optional
            Used for calculation of the peaks width, thus it is only used if width is given.
            See argument rel_height in peak_widths for a full description of its effects.

            plateau_size:number or ndarray or sequence, optional
            Required size of the flat top of peaks in samples.
            Either a number, None, an array matching x or a 2-element sequence of the former.
            The first element is always interpreted as the minimal and the second, if supplied as the maximal required plateau size.

            Returns:

            peaks:ndarray
            Indices of peaks in x that satisfy all given conditions.

            properties:dict
            A dictionary containing properties of the returned peaks which were calculated as intermediate results during evaluation of the specified conditions:

                ‘peak_heights’
                If height is given, the height of each peak in x.

                ‘left_thresholds’, ‘right_thresholds’
                If threshold is given, these keys contain a peaks vertical distance to its neighbouring samples.

                ‘prominences’, ‘right_bases’, ‘left_bases’
                If prominence is given, these keys are accessible. See peak_prominences for a description of their content.

                ‘widths’, ‘width_heights’, ‘left_ips’, ‘right_ips’
                If width is given, these keys are accessible. See peak_widths for a description of their content.

                ‘plateau_sizes’, left_edges’, ‘right_edges’
                If plateau_size is given, these keys are accessible and contain the indices of a peak’s edges (edges are still part of the plateau) and the calculated plateau sizes.
            """

        peaks, properties = find_peaks(
            data[padding_before:-padding_after],
            height=min_height + baseline_mean,
            prominence=min_prom,
            wlen=wlen,
            width=width,
            distance=min_dist,
            rel_height=rel_height,
        )
        properties.update({"filtered": [0 for i in range(len(peaks))]})
        properties.update(
            {
                "left_bases": [
                    np.absolute(
                        data[properties["left_bases"][i] + padding_before]
                        - baseline_mean
                    )
                    for i in range(len(peaks))
                ]
            }
        )
        properties.update(
            {
                "right_bases": [
                    np.absolute(
                        data[properties["right_bases"][i] + padding_before]
                        - baseline_mean
                    )
                    for i in range(len(peaks))
                ]
            }
        )
        unfolded_level = self.find_unfolded_blockage_level(
            data[padding_before:-padding_after],
            max_unfolded,
            baseline_mean,
            baseline_std,
        )
        properties = self.filter_peaks(
            peaks, properties, unfolded_level, baseline_std, baseline_mean, samplerate
        )

        if len(peaks) > 0:
            edges = [
                {
                    "index": 0,
                    "type": "start",
                    "peak_height": None,
                    "prominence": None,
                    "left_base": None,
                    "right_base": None,
                    "width": None,
                    "left_ips": None,
                    "right_ips": None,
                    "filtered": None,
                    "unfolded_level": unfolded_level,
                },
                {
                    "index": padding_before,
                    "type": "padding_before",
                    "peak_height": None,
                    "prominence": None,
                    "left_base": None,
                    "right_base": None,
                    "width": None,
                    "left_ips": None,
                    "right_ips": None,
                    "filtered": None,
                },
            ]
            for i in range(len(peaks)):
                edges.append(
                    {
                        "index": peaks[i] + padding_before,
                        "type": f"peak_{i+1}",
                        "peak_height": np.absolute(
                            properties["peak_heights"][i] - baseline_mean
                        ),
                        "prominence": properties["prominences"][i],
                        "left_base": properties["left_bases"][i],
                        "right_base": properties["right_bases"][i],
                        "width": properties["widths"][i],
                        "left_ips": padding_before + properties["left_ips"][i],
                        "right_ips": padding_before + properties["right_ips"][i],
                        "filtered": properties["filtered"][i],
                    }
                )
            edges.append(
                {
                    "index": len(data) - padding_after,
                    "type": "padding_after",
                    "peak_height": None,
                    "prominence": None,
                    "left_base": None,
                    "right_base": None,
                    "width": None,
                    "left_ips": None,
                    "right_ips": None,
                    "filtered": None,
                }
            )
            edges.append(
                {
                    "index": len(data),
                    "type": "end",
                    "peak_height": None,
                    "prominence": None,
                    "left_base": None,
                    "right_base": None,
                    "width": None,
                    "left_ips": None,
                    "right_ips": None,
                    "filtered": None,
                }
            )
        else:
            raise ValueError("No Peaks Found")

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
        :type sublevel_starts: List[Dict[str, Any]]

        :return: a dict of lists of sublevel metadata values, one list entry per sublevel for each piece of metadata
        :rtype: Mapping[str, npt.NDArray[Numeric]]
        """
        sublevel_metadata = {}

        # Filter out non-peak edges to get actual sublevel boundaries
        num_states = (
            len(sublevel_starts) - 1
        )  # Number of sublevels is one less than the number of transitions (start and end included)
        # rise_time = int(1.0e-6 * 10 * samplerate)
        dt_us = 1.0 / samplerate * 1e6
        aC_pC = 1e-6
        unfolded_level = sublevel_starts[0]["unfolded_level"]
        # average the current over the sublevel, ignoring the rise time
        sublevel_metadata["sublevel_current"] = np.array(
            [
                (
                    np.median(
                        data[
                            int(sublevel_starts[i]["index"]) : int(
                                sublevel_starts[i + 1]["index"]
                            )
                        ]
                    )
                    if sublevel_starts[i]["index"] < sublevel_starts[i + 1]["index"]
                    else data[int(sublevel_starts[i + 1]["index"]) - 1]
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

        # get durations between sublevel start times
        sublevel_metadata["sublevel_duration"] = np.array(
            [
                (sublevel_starts[i + 1]["index"] - sublevel_starts[i]["index"]) * dt_us
                for i in range(num_states)
            ],
            dtype=np.float64,
        )

        # get sublevel start times
        sublevel_metadata["sublevel_start_times"] = np.array(
            [sublevel_starts[i]["index"] * dt_us for i in range(num_states)],
            dtype=np.float64,
        )

        # get sublevel end times
        sublevel_metadata["sublevel_end_times"] = np.array(
            [sublevel_starts[i + 1]["index"] * dt_us for i in range(num_states)],
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
                            int(sublevel_starts[i]["index"]) : int(
                                sublevel_starts[i + 1]["index"]
                            )
                        ]
                    )
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get the maximal deviation from the event baseline for each sublevel
        sublevel_metadata["sublevel_max_deviation"] = np.array(
            [
                np.max(
                    np.absolute(
                        data[
                            int(sublevel_starts[i]["index"]) : int(
                                sublevel_starts[i + 1]["index"]
                            )
                        ]
                        - event_baseline
                    )
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak id
        sublevel_metadata["peak_id"] = self.enumerate_peaks(sublevel_starts, num_states)
        # get peak height
        sublevel_metadata["peak_height"] = np.array(
            [
                (
                    np.absolute(sublevel_starts[i]["peak_height"])
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get normalized peak height
        sublevel_metadata["normalized_height"] = np.array(
            [
                (
                    sublevel_starts[i]["peak_height"] / unfolded_level
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak location
        sublevel_metadata["peak_loc"] = np.array(
            [
                (
                    sublevel_starts[i]["index"] * dt_us
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak widths @relative height
        sublevel_metadata["peak_width"] = np.array(
            [
                (
                    sublevel_starts[i]["width"] * dt_us
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak prominence
        sublevel_metadata["prominence"] = np.array(
            [
                (
                    sublevel_starts[i]["prominence"]
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get normalized peak prominence
        sublevel_metadata["normalized_prominence"] = np.array(
            [
                (
                    sublevel_starts[i]["prominence"] / unfolded_level
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak right base
        sublevel_metadata["right_base"] = np.array(
            [
                (
                    sublevel_starts[i]["right_base"]
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak left base
        sublevel_metadata["left_base"] = np.array(
            [
                (
                    sublevel_starts[i]["left_base"]
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak right ips
        sublevel_metadata["right_ips"] = np.array(
            [
                (
                    sublevel_starts[i]["right_ips"] * dt_us
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak left ips
        sublevel_metadata["left_ips"] = np.array(
            [
                (
                    sublevel_starts[i]["left_ips"] * dt_us
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak height ips
        sublevel_metadata["height_ips"] = np.array(
            [
                (
                    max(
                        data[int(sublevel_starts[i]["left_ips"])],
                        data[int(sublevel_starts[i]["right_ips"])],
                    )
                    if "peak" in sublevel_starts[i]["type"]
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )

        # get peak filter success
        sublevel_metadata["filtered"] = [
            (
                sublevel_starts[i]["filtered"]
                if "peak" in sublevel_starts[i]["type"]
                else None
            )
            for i in range(num_states)
        ]

        # get raw peak height
        # sublevel_metadata['raw_height'] = np.array([np.max(np.absolute(data[int(sublevel_starts[i]['left_ips']):int(sublevel_starts[i]['right_ips'])] - event_baseline))
        #                                             if 'peak'in sublevel_starts[i]['type']
        #                                             else None
        #                                             for i in range(num_states)],
        #                                             dtype=np.float64)

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
        :type sublevel_metadata: Mapping[str, List[Numeric]]

        :return: a dict of event metadata values
        :rtype: Mapping[str, float]
        """
        event_metadata = {}

        event_metadata["number_peaks"] = len(
            sublevel_metadata["sublevel_duration"][1:-1] - 1
        )
        event_metadata["duration"] = np.sum(
            [sublevel_metadata["sublevel_duration"][1:-1]]
        )
        event_metadata["raw_ecd"] = np.sum(
            [sublevel_metadata["sublevel_raw_ecd"][1:-1]]
        )
        event_metadata["max_deviation"] = np.max(
            sublevel_metadata["sublevel_max_deviation"][1:-1]
        )
        event_metadata["baseline"] = baseline_mean
        event_metadata["unfolded_level"] = self.find_unfolded_blockage_level(
            data[
                int(
                    sublevel_metadata["sublevel_start_times"][1] * samplerate * 1e-6
                ) : int(
                    sublevel_metadata["sublevel_start_times"][-1] * samplerate * 1e-6
                )
            ],
            self.settings["Max Unfolded"]["Value"],
            event_metadata["baseline"],
            baseline_std,
        )
        event_metadata["baseline_std"] = baseline_std

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
        :rtype: Mapping[str, Union[int, float, str, bool]]
        """
        metadata_types: Mapping[str, Type[Union[int, float, str, bool]]] = {
            "number_peaks": int,
            "duration": float,
            "raw_ecd": float,
            "max_deviation": float,
            "baseline": float,
            "unfolded_level": float,
            "baseline_std": float,
        }

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
        :rtype: Mapping[str, Union[int, float, str, bool]]
        """
        metadata_types: Mapping[str, Type[Union[int, float, str, bool]]] = {
            "sublevel_current": float,
            "sublevel_duration": float,
            "sublevel_start_times": float,
            "sublevel_end_times": float,
            "sublevel_raw_ecd": float,
            "sublevel_max_deviation": float,
            "peak_id": int,
            "peak_height": float,
            "peak_loc": float,
            "peak_width": float,
            "prominence": float,
            "left_base": float,
            "right_base": float,
            "left_ips": float,
            "right_ips": float,
            "height_ips": float,
            "filtered": int,
            "normalized_height": float,
            "normalized_prominence": float,
        }

        return metadata_types

    @log(logger=logger)
    @override
    def _define_event_metadata_units(self):
        """
        Build a dict of metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Mapping[str, Union[int, float, str, bool]]
        """
        metadata_units = {}

        metadata_units["number_peaks"] = " "
        metadata_units["duration"] = "μs"
        metadata_units["raw_ecd"] = "pC"
        metadata_units["max_deviation"] = "pA"
        metadata_units["unfolded_level"] = "pA"
        metadata_units["baseline_std"] = "pA"

        return metadata_units

    @log(logger=logger)
    @override
    def _define_sublevel_metadata_units(self):
        """
        Build a dict of sublevel metadata units , or None if unitless. Keys must match columns defined in _populate_sublevel_metadata()
        All of this metadata must be populated during fitting.
        it should not include the list element

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Mapping[str, Optional[str]]
        """
        metadata_units = {}

        metadata_units["sublevel_current"] = "pA"
        metadata_units["sublevel_duration"] = "us"
        metadata_units["sublevel_start_times"] = "us"
        metadata_units["sublevel_end_times"] = "us"
        metadata_units["sublevel_max_deviation"] = "pA"
        metadata_units["sublevel_raw_ecd"] = "pC"
        metadata_units["peak_id"] = " "
        metadata_units["peak_height"] = "pA"
        metadata_units["peak_loc"] = "us"
        metadata_units["peak_width"] = "us"
        metadata_units["prominence"] = "pA"
        metadata_units["left_base"] = "pA"
        metadata_units["right_base"] = "pA"
        metadata_units["left_ips"] = "us"
        metadata_units["right_ips"] = "us"
        metadata_units["height_ips"] = "pA"
        metadata_units["filtered"] = " "
        metadata_units["normalized_height"] = "pA"
        metadata_units["normalized_prominence"] = "pA"

        return metadata_units

    # utility functions

    @log(logger=logger)
    def filter_peaks(
        self, peaks, properties, unfolded_level, baseline_std, baseline, samplerate
    ):
        """
        Filters peaks based on their level and proximity, classifying potential bundles or barcode features.
        - Type 1: Peaks on the same DNA carrier level (both bases around unfolded_level).
        - Type 2: Peaks higher than the carrier level (both bases above unfolded_level).
        - Type 3: Clusters (bundles) of close peaks with same type (1 or 2).
        """
        dt_us = 1.0 / samplerate * 1e6
        num_peaks = self.settings["Number of peaks"]["Value"]
        prom_indices = np.argsort(properties["prominences"])[::-1]  # all sorted

        filtered = properties["filtered"]

        if self.settings["Event Type"]["Value"] == "Barcode":
            # Step 1: Classify peaks based on base levels ---
            for i in range(len(peaks)):
                left_base = properties["left_bases"][i]
                right_base = properties["right_bases"][i]

                # ignores peaks near the end of a level (missmatched bases)

                # Type 0: both bases above double the unfolded level, useless messes
                if (
                    left_base >= 2 * unfolded_level + baseline_std
                    and right_base >= 2 * unfolded_level + baseline_std
                ):
                    filtered[i] = -1
                # Type 2: both bases near double the unfolded level
                elif (
                    left_base >= unfolded_level + baseline_std
                    and right_base >= unfolded_level + baseline_std
                ):
                    filtered[i] = 2
                # Type 1: both bases near the unfolded level
                elif (
                    left_base >= unfolded_level - 2 * baseline_std
                    and right_base >= unfolded_level - 2 * baseline_std
                ):
                    filtered[i] = 1

                # if filtered[i] not in [1, 2, -1]:
                #    print(f"Unlabeled peak {i}: left={left_base:.3f}, right={right_base:.3f}, unfolded_level-2std={unfolded_level - 2 * baseline_std:.3f}, 2*unfolded_level+std={2*unfolded_level+baseline_std:.3f}")

                # Step 2: Identify clusters of same-type peaks, but keep only the most prominent one
                max_distance = 100 / dt_us  # in samples
                min_group_size = num_peaks

                best_cluster = []
                best_prom_sum = 0

                for label in [1, 2]:
                    label_idxs = [i for i in prom_indices if filtered[i] == label]
                    if not label_idxs:
                        continue

                    label_idxs = label_idxs[:num_peaks]
                    sorted_idxs = sorted(label_idxs, key=lambda i: peaks[i])

                    for i in range(len(sorted_idxs)):
                        group = [sorted_idxs[i]]
                        for j in range(i + 1, len(sorted_idxs)):
                            if (
                                abs(peaks[sorted_idxs[j]] - peaks[sorted_idxs[i]])
                                <= max_distance
                            ):
                                group.append(sorted_idxs[j])
                            else:
                                break
                        if len(group) >= min_group_size:
                            prom_sum = sum(
                                properties["prominences"][idx] for idx in group
                            )
                            if prom_sum > best_prom_sum:
                                best_cluster = group
                                best_prom_sum = prom_sum
                            break  # only use first valid cluster per label

                    # Relabel best cluster as Type 3
                    for idx in best_cluster:
                        filtered[idx] = 3

        if self.settings["Event Type"]["Value"] == "Single Peak":
            pass  # fill out as needed
        if self.settings["Event Type"]["Value"] == "Unspecified":
            pass  # fill out as needed

        return properties

    @log(logger=logger)
    def find_unfolded_blockage_level(
        self, data, max_unfolded, baseline_mean, baseline_std
    ):
        """
        Estimate the level of unfolded blockage based on data distribution.

        :param data: Array of current values or similar signal to analyze.
        :type data: numpy.ndarray
        :param max_unfolded: Maximum allowed distance from the baseline to consider as unfolded.
        :type max_unfolded: float
        :param baseline_mean: Mean value of the baseline level.
        :type baseline_mean: float
        :param baseline_std: Standard deviation of the baseline level.
        :type baseline_std: float
        :return: Estimated unfolded blockage level.
        :rtype: float
        """
        range = np.arange(min(data), max(data))

        counts = [
            np.sum(
                (data > i - 1 / 2 * baseline_std) & (data < i + 1 / 2 * baseline_std)
            )
            for i in range
        ]

        max_count_index = np.argmax(counts)

        if np.abs(range[max_count_index] - baseline_mean) > max_unfolded:
            return np.abs(range[max_count_index] - baseline_mean) / 2

        return np.abs(range[max_count_index] - baseline_mean)

    @log(logger=logger)
    def enumerate_peaks(self, sublevel_starts, num_states):
        """
        Assign unique peak IDs to sublevels labeled as 'peak'.

        :param sublevel_starts: List of dictionaries describing sublevels, each with a 'type' key.
        :type sublevel_starts: list[dict]
        :param num_states: Total number of sublevels to process.
        :type num_states: int
        :return: List of peak IDs or None for non-peak sublevels.
        :rtype: list[Optional[int]]
        """
        j = 1
        id: List[Optional[int]] = []
        for i in range(num_states):
            if "peak" in sublevel_starts[i]["type"]:
                id.append(j)
                j += 1
            else:
                id.append(None)
        return id
