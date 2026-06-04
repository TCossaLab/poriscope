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
from typing import Dict, List, Mapping, Optional, Tuple, Type, Union, cast

import numpy as np
from scipy.signal import find_peaks
from sklearn.mixture import GaussianMixture
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
        settings["Number of peaks"] = {
            "Type": int,
            "Value": 1,
            "Min": 1,
        }
        settings["Filter Peaks"] = {"Type": bool, "Value": True}
        settings["Lower Filter Threshold"] = {
            "Type": int,
            "Value": -3,
            "Min": -10,
            "Max": 10,
            "Units": "σ",
        }
        settings["Higher Filter Threshold"] = {
            "Type": int,
            "Value": 3,
            "Min": -10,
            "Max": 10,
            "Units": "σ",
        }

        settings["Peak to Peak Distance Ratio"] = {
            "Type": float,
            "Value": 10.0,  # Default to 10% of event length
            "Min": 0.1,
            "Max": 50.0,  # Maximum 50% of event
            "Units": "%",
        }
        settings["Window Length Percentage"] = {
            "Type": float,
            "Value": 10.0,  # Default to 10% of event length
            "Min": 0.1,
            "Max": 50.0,  # Maximum 50% of event
            "Units": "%",
        }
        settings["Classify Levels"] = {
            "Type": bool,
            "Value": True,
        }
        # settings["Plot classification"] = {
        #     "Type": bool,
        #     "Value": True,
        # }
        settings["Min Carrier Blockage"] = {
            "Type": float,
            "Value": 300.0,  # Default minimum blockage for classification
            "Min": 0.0,
            "Max": 10000.0,
            "Units": "pA",
        }
        settings["Visualize Classification"] = {
            "Type": bool,
            "Value": False,
        }

        # settings["Plateau Size"] = {
        #     "Type": str,
        #     "Value": "None",  # Default to no plateau size filtering. Can be "None", a single value (e.g. "5.0"), or a range (e.g. "2.0,10.0")
        #     "Units": "us",
        # }
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

            # Convert times (us) to sample indices (rounded, not floored)
            starts = np.rint(
                self.sublevel_metadata[channel][index]["sublevel_start_times"] / dt_us
            ).astype(int)

            ends = np.rint(
                self.sublevel_metadata[channel][index]["sublevel_end_times"] / dt_us
            ).astype(int)

            # Force the fitted length to match the true raw event length
            true_len = int(self.event_lengths[channel][index])
            ends[-1] = true_len

            sublevel_currents = self.sublevel_metadata[channel][index][
                "sublevel_current"
            ]
            baseline = self.event_metadata[channel][index]["baseline_current"]

            # Peak-related data (stored in us in metadata; convert to indices)
            peak_heights = self.sublevel_metadata[channel][index]["peak_height"]
            peak_fil = self.sublevel_metadata[channel][index]["filtered"]

            peak_rips = np.rint(
                self.sublevel_metadata[channel][index]["right_ips"] / dt_us
            ).astype(
                float
            )  # may contain nan

            peak_lips = np.rint(
                self.sublevel_metadata[channel][index]["left_ips"] / dt_us
            ).astype(
                float
            )  # may contain nan

            peak_max_blockages = self.sublevel_metadata[channel][index].get(
                "max_blockage", [None] * len(peak_heights)
            )

            data = np.zeros(true_len, dtype=np.float64)

            # Build data with sublevels (only if filtered == 3)
            for start, end, current, fil in zip(
                starts,
                ends,
                sublevel_currents,
                peak_fil,
            ):
                # Clamp sublevel bounds to the array
                start_i = int(max(0, min(true_len, start)))
                end_i = int(max(0, min(true_len, end)))
                if end_i <= start_i:
                    continue

                # Fill baseline sublevel current
                data[start_i:end_i] = current

            # Plot max blockage levels between ips for all peaks
            for rips, lips, fil, max_blockage in zip(
                peak_rips,
                peak_lips,
                peak_fil,
                peak_max_blockages,
            ):
                # Plot peak only if ips exist
                if not (np.isnan(lips) or np.isnan(rips)):
                    li = int(max(0, min(true_len, int(lips))))
                    ri = int(max(0, min(true_len, int(rips))))
                    if (
                        ri > li
                        and max_blockage is not None
                        and not np.isnan(max_blockage)
                    ):
                        # Display the mean blockage level (max_blockage) between ips
                        data[li:ri] = baseline - np.sign(baseline) * max_blockage

        except KeyError:
            self.logger.info(
                f"missing event id {index} in channel {channel}: rejected event skipped"
            )
            return None

        return data


    # public API, should generally be left alone by subclasses
    @log(logger=logger)
    def get_plot_features(self, channel: int, index: int) -> Tuple[
        Optional[List[float]],
        Optional[List[float]],
        Optional[List[Tuple[float, float]]],
        Optional[List[str]],
        Optional[List[str]],
        Optional[List[str]],
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
            value = self.settings.get("Plot Features", {}).get("Value")
            if self.settings is None or value == "None":
                return None, None, None, None, None, None

            baseline = self.event_metadata[channel][index]["baseline_current"]
            t1_std = int(self.settings["Lower Filter Threshold"]["Value"])
            t2_std = int(self.settings["Higher Filter Threshold"]["Value"])
            # Initializing arrays
            bases: list[float] = []
            peaks: list[tuple[float, float]] = []
            #ips: list[float] = []
            vlabel: list[str] = []
            hlabel: list[str] = []
            plabel: list[str] = []
            peaks_filtered: list[float] = []
            j = 1

            # some gauges for finetuning filters
            bases.append(baseline)
            hlabel.append("Baseline")
            bases.append(
                -np.sign(baseline)
                * self.event_metadata[channel][index]["unfolded_level"]
                + self.event_metadata[channel][index]["baseline_current"]
            )
            hlabel.append("unfolded level")
            bases.append(
                -np.sign(baseline)
                * self.event_metadata[channel][index]["unfolded_level"]
                + self.event_metadata[channel][index]["baseline_current"]
                - np.sign(baseline)
                * t2_std
                * self.event_metadata[channel][index]["baseline_std"]
            )
            hlabel.append(f"unfolded level {t2_std:+d}σ")
            bases.append(
                -np.sign(baseline)
                * self.event_metadata[channel][index]["unfolded_level"]
                + self.event_metadata[channel][index]["baseline_current"]
                - np.sign(baseline)
                * t1_std
                * self.event_metadata[channel][index]["baseline_std"]
            )
            hlabel.append(f"unfolded level {t1_std:+d}σ")
            
            if self.event_metadata[channel][index]["sequence"] is not None:
                if self.event_metadata[channel][index]["translocation_direction"] == "forward":
                    peaks_filtered.append(self.sublevel_metadata[channel][index]["sublevel_start_times"][1])
                    vlabel.append(f"Forward translocation.\n Sequence: {self.event_metadata[channel][index]['sequence']}")
                elif self.event_metadata[channel][index]["translocation_direction"] == "backward":
                    peaks_filtered.append(self.sublevel_metadata[channel][index]["sublevel_start_times"][-1])
                    vlabel.append(f"Backward translocation.\n Sequence: {self.event_metadata[channel][index]['sequence']}")

                    
            for i in range(len(self.sublevel_metadata[channel][index]["right_ips"])):
                
                if self.sublevel_metadata[channel][index]["peak_id"][i] is not None:
                    # ips.append(self.sublevel_metadata[channel][index]['left_ips'][i]) #can be seen in event construct instead
                    # ips.append(self.sublevel_metadata[channel][index]['right_ips'][i])
                    # vlabel.append("Right ips #" + str(j))
                    # vlabel.append("Left ips #" + str(j))

                    # bases.append(
                    #     -np.sign(baseline)
                    #     * self.sublevel_metadata[channel][index]["left_base"][i]
                    #     + self.event_metadata[channel][index]["baseline"]
                    # )
                    # bases.append(
                    #     -np.sign(baseline)
                    #     * self.sublevel_metadata[channel][index]["right_base"][i]
                    #     + self.event_metadata[channel][index]["baseline"]
                    # )
                    # hlabel.append("Right base #" + str(j))
                    # hlabel.append("Left base #" + str(j))

                    peaks.append(
                        (
                            self.sublevel_metadata[channel][index]["peak_loc"][i],
                            -np.sign(baseline)
                            * self.sublevel_metadata[channel][index]["peak_height"][i]
                            + baseline,
                        )
                    )
                    plabel.append(
                        "Peak #"
                        + str(j)
                        + " Filter: "
                        + str(self.sublevel_metadata[channel][index]["filtered"][i])                        
                        + " Class: "
                        + str(self.sublevel_metadata[channel][index]["classified"][i])
                    )

                    j += 1

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
        # Reset global post-processing flag at the start of fitting for each channel
        # This ensures post-processing runs after each new fitting session
        if not hasattr(self, "_global_postprocessing_done"):
            self._global_postprocessing_done = False
        else:
            # Reset the flag so post-processing can run for this fitting session
            self._global_postprocessing_done = False
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

        low_threshold = abs(
            self.settings.get("Lower Filter Threshold", {}).get("Value", 3)
        )
        high_threshold = abs(
            self.settings.get("Higher Filter Threshold", {}).get("Value", 3)
        )

        min_height = None  # Will be calculated as carrier_blockage + min_prom
        min_prom = None  # Will be calculated as 6*baseline_std to avoid noise detection
        width = 0  # Minimum width of 0 μs (no width constraint)
        min_dist = None  # Will be set to wlen (smallest reasonable window length)
        rel_height = 0.5  # Fixed at 0.5 (width measured at 50% of peak height)

        if baseline_std is None:  # the rest of the args can be None without issue
            if padding_before is not None:
                baseline_std = np.std(data[:padding_before])
            elif padding_after is not None:
                baseline_std = np.std(data[-padding_after:])
            else:
                raise ValueError(
                    "Peankfinder requires that the standard deviation of the local baseline be reported and is unable to calculate it for this event"
                )

        # Find longest continuous segment above threshold 
        # This trims the event to start/end at the longest above-threshold blockage
        
        threshold = min(abs(low_threshold), abs(high_threshold),3) * baseline_std
        event_data = data[padding_before:-padding_after]
        above_threshold = np.abs((np.abs(event_data) - np.sign(baseline_mean) * baseline_mean)) > threshold
        
        if not np.any(above_threshold):
            raise ValueError("No data above threshold found")

        # Find all continuous segments
        diff = np.diff(np.concatenate(([False], above_threshold, [False])).astype(int))
        segment_starts = np.where(diff == 1)[0]
        segment_ends = np.where(diff == -1)[0]

        # Find the longest segment
        segment_lengths = segment_ends - segment_starts
        longest_segment_idx = np.argmax(segment_lengths)
        longest_segment_length = segment_lengths[longest_segment_idx]

        # Check if longest segment meets minimum length requirement
        # Behavior depends on whether classification is enabled
        classify_levels = self.settings.get("Classify Levels", {}).get("Value", True)
        min_segment_length = 10

        if not classify_levels:
            # If classification is disabled, accept any segment length above threshold
            # as long as at least one segment exists above threshold
            if longest_segment_length < 1:
                raise ValueError("No Carrier Level Found")
        else:
            # If classification is enabled, enforce minimum segment length
            # (classification requires a stable carrier level)
            if longest_segment_length < min_segment_length:
                raise ValueError("No Carrier Level Found")

        # Get the start and end indices of the longest segment (relative to event_data)
        longest_start_idx = segment_starts[longest_segment_idx]
        longest_end_idx = segment_ends[longest_segment_idx]

        # Adjust padding to trim to the longest segment only
        # New effective padding_before includes original padding plus everything before longest segment
        new_padding_before = padding_before + longest_start_idx
        # New effective padding_after includes original padding plus everything after longest segment
        new_padding_after = padding_after + (len(event_data) - longest_end_idx)

        # Use adjusted paddings for the rest of processing
        padding_before = new_padding_before
        padding_after = new_padding_after

        # Calculate minimum prominence and height from the user thresholds.
        # Keep the carrier-aware guardrails so peaks still scale with signal depth.
        min_prom_noise = max(abs(low_threshold), abs(high_threshold)) * baseline_std

        # Method 2: Signal-based minimum (relative to carrier blockage depth)
        # Calculate the carrier level blockage (median of the trimmed event)
        trimmed_data = data[padding_before:-padding_after]
        carrier_blockage = np.abs(np.median(trimmed_data) - baseline_mean)

        # Peaks should still be significant relative to the translocation signal
        min_prom_signal = carrier_blockage
        # Use the more stringent of the two criteria
        min_prom = max(min_prom_noise, min_prom_signal)
        # Height is driven by the higher threshold setting, then guarded by the
        # carrier level so peaks still sit beyond the local blockage.
        min_height = max(max(abs(low_threshold), abs(high_threshold)) * baseline_std, carrier_blockage + min_prom)

        # Calculate wlen (prominence window) for finding peak bases
        # wlen is calculated as a user-specified percentage of the trimmed event length
        # This provides a simple, predictable, and user-controllable approach
        #
        # User Setting: Window Length Percentage determines wlen as % of event
        # - Default: 2.2% of event (based on original 160/7249 ratio)
        # - Range: 0.1% to 33.3% (maximum 1/3 of event)
        # - Automatically scales with event duration

        trimmed_event_length = longest_segment_length  # Length in samples

        # Get user-specified window length percentage and convert to ratio
        window_length_percentage = self.settings.get(
            "Window Length Percentage", {}
        ).get("Value", 2.2)
        window_length_ratio = window_length_percentage / 100.0  # Convert % to fraction

        # Calculate wlen directly from user setting
        wlen = int(window_length_ratio * trimmed_event_length)
        # Apply only essential safety bounds
        wlen = min(wlen, trimmed_event_length // 3)  # Maximum 1/3 of event
        wlen = max(wlen, 2)

        # Set minimum distance between peaks to wlen (smallest reasonable window length)
        # This ensures peaks are separated by at least the prominence window width
        min_dist = max(1, wlen // 2)

        # Calculate SNR for logging/diagnostics only
        signal_step = max(min_prom, min_height)
        snr = signal_step / baseline_std if baseline_std > 0 else 10.0

        # Get plateau size setting and convert from microseconds to samples
        #plateau_size_str = self.settings.get("Plateau Size", {}).get("Value", "None")

        # Parse the plateau size string
        # Can be "None", a single value "5.0", or a range "2.0,10.0"
        #plateau_size = None

        self.logger.debug(
            f"Peak detection parameters: dt_us={dt_us:.3f}, baseline_std={baseline_std:.2f}, "
            f"carrier_blockage={carrier_blockage:.2f} pA, "
            f"low_threshold={low_threshold}, high_threshold={high_threshold}, "
            f"min_prom_noise={min_prom_noise:.2f} pA, "
            f"min_prom_signal={min_prom_signal:.2f} pA (50% of carrier), "
            f"final min_prom={min_prom:.2f} pA, "
            f"min_height={min_height:.2f} pA (carrier + min_prom), "
            f"trimmed_event_length={trimmed_event_length} samples ({trimmed_event_length*dt_us:.2f} us), "
            f"window_percentage={window_length_percentage:.1f}%, "
            f"SNR={snr:.2f}, wlen={wlen} samples ({wlen*dt_us:.2f} us), "
            f"min_dist={min_dist} samples ({min_dist*dt_us:.2f} us), "
            #f"plateau_size={plateau_size}"
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

            # plateau_size:number or ndarray or sequence, optional
            # Required size of the flat top of peaks in samples.
            # Either a number, None, an array matching x or a 2-element sequence of the former.
            # The first element is always interpreted as the minimal and the second, if supplied, as the maximal required plateau size.

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

                # ‘plateau_sizes’, left_edges’, ‘right_edges’
                # If plateau_size is given, these keys are accessible and contain the indices of a peak’s edges (edges are still part of the plateau) and the calculated plateau sizes.
            """

        peaks, properties = find_peaks(
            -np.sign(baseline_mean) * data[padding_before:-padding_after],
            height=-np.sign(baseline_mean) * baseline_mean + min_height,
            prominence=min_prom,
            wlen=wlen,
            width=width,
            distance=min_dist,
            rel_height=rel_height,
            # **({"plateau_size": plateau_size} if plateau_size > 0 else {}),
        )

        if len(peaks) == 0:
            raise ValueError("No Peaks Found")

        properties.update(
            {
                "left_bases": [
                    data[properties["left_bases"][i] + padding_before]
                    for i in range(len(peaks))
                ]
            }
        )
        properties.update(
            {
                "right_bases": [
                    data[properties["right_bases"][i] + padding_before]
                    for i in range(len(peaks))
                ]
            }
        )


        if len(peaks) > 0:
            edges = [
                {
                    "index": 0,
                    "type": "start",
                },
                {
                    "index": padding_before,
                    "type": "padding_before",
                },
            ]
            for i in range(len(peaks)):
                left_ip = int(padding_before + properties["left_ips"][i])
                right_ip = int(padding_before + properties["right_ips"][i])
                peak_data_segment = (
                    data[left_ip:right_ip]
                    if right_ip > left_ip
                    else data[left_ip : left_ip + 1]
                )
                max_blockage,_ = self.find_mode_blockage_level(
                    peak_data_segment,
                    baseline_mean,
                    baseline_std,
                )
                edges.append(
                    {
                        "index": int(padding_before + properties["left_ips"][i]),
                        "type": f"event_baseline_{i+1}",
                    }
                )
                edges.append(
                    {
                        "index": peaks[i] + padding_before,
                        "loc": peaks[i],
                        "type": f"peak_{i+1}",
                        "peak_height": np.absolute(
                            np.sign(baseline_mean) * baseline_mean
                            + properties["peak_heights"][
                                i
                            ]  # turned into absolute blockage instead of current
                        ),
                        "prominence": properties["prominences"][i],
                        "left_base": np.absolute(
                            np.sign(baseline_mean) * baseline_mean
                            + properties["left_bases"][i]
                        ),
                        "right_base": np.absolute(
                            np.sign(baseline_mean) * baseline_mean
                            + properties["right_bases"][i]
                        ),
                        "width": properties["widths"][i],
                        "left_ips": left_ip,
                        "right_ips": right_ip,
                        "max_blockage": max_blockage,
                        # "plateau_size": properties.get(
                        #     "plateau_sizes", [None] * len(peaks)
                        # )[i],
                        "filtered": properties.get("filtered", [0] * len(peaks))[i],
                    }
                )
                edges.append(
                    {
                        "index": int(padding_before + properties["right_ips"][i]),
                        "type": f"event_baseline_{i+1}",
                    }
                )

            edges.append(
                {
                    "index": len(data) - padding_after,
                    "type": "padding_after",
                }
            )
            edges.append(
                {
                    "index": len(data),
                    "type": "end",
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
        
        # Determine sublevel types: "peak" (if edge contains peak) or "event_baseline" (other transitions)
        sublevel_metadata["sublevel_type"] = []
        for i in range(num_states):
            start_edge_type = sublevel_starts[i]["type"]
            # A sublevel is "peak" if it starts with a peak edge
            if "peak" in start_edge_type:
                sublevel_metadata["sublevel_type"].append("peak")
            elif "event_baseline" in start_edge_type:
                sublevel_metadata["sublevel_type"].append("event_baseline")
            else:
                sublevel_metadata["sublevel_type"].append("padding")

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
                    else np.median(
                        data[
                            int(sublevel_starts[i + 1]["index"]) : int(
                                sublevel_starts[i]["index"]
                            )
                        ]
                    )
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )

        # get the difference from the local baseline
        # event_baseline = 0.5 * (
        #     sublevel_metadata["sublevel_current"][0]
        #     + sublevel_metadata["sublevel_current"][-1]
        # )
        event_baseline=baseline_mean

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
        # get cumulative sum of raw_ecd (sum of all previous sublevels at each sublevel)
        sublevel_metadata["sublevel_cumulative_ecd"] = np.cumsum(
            sublevel_metadata["sublevel_raw_ecd"]
        )

        # get the maximal deviation from the event baseline for each sublevel
        sublevel_metadata["sublevel_max_deviation"] = np.array(
            [
                (
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
                    if sublevel_starts[i]["index"] < sublevel_starts[i + 1]["index"]
                    else np.max(
                        np.absolute(
                            data[
                                int(sublevel_starts[i + 1]["index"]) : int(
                                    sublevel_starts[i]["index"]
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
        # get peak id
        sublevel_metadata["peak_id"] = self.enumerate_peaks(
            sublevel_starts, num_states, sublevel_metadata["sublevel_type"]
        )

        # get peak location
        sublevel_metadata["peak_loc"] = np.array(
            [
                (
                    sublevel_starts[i]["index"] * dt_us
                    if "peak" in sublevel_starts[i]["type"]
                    else np.nan
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
                    else np.nan
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get normalized peak height (will be calculated in post-processing when unfolded_level is determined)
        sublevel_metadata["normalized_height"] = np.array(
            [
                (
                np.nan
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak height
        sublevel_metadata["peak_height"] = np.array(
            [
                (
                    sublevel_starts[i]["peak_height"]
                    if "peak" in sublevel_starts[i]["type"]
                    else np.nan
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get normalized peak height
        sublevel_metadata["normalized_height"] = np.array(
            [
                (
                    np.nan
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
                    else np.nan
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get normalized peak prominence (will be calculated in post-processing when unfolded_level is determined)
        sublevel_metadata["normalized_prominence"] = np.array(
            [
                (
                    np.nan
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )

        # get peak max blockage
        sublevel_metadata["max_blockage"] = np.array(
            [
                (
                    sublevel_starts[i].get("max_blockage")
                    if "peak" in sublevel_starts[i]["type"]
                    and sublevel_starts[i].get("max_blockage") is not None
                    else None
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get normalized max blockage (max_blockage / unfolded_level) for peak sublevels
        sublevel_metadata["normalized_blockage"] = np.array(
            [
                (
                    np.nan
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
                    else np.nan
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
                    else np.nan
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
                    else np.nan
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
                    else np.nan
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
                    else np.nan
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )

        # get peak filter success
        # Initialize to 0 for peaks (will be classified in post-processing), NaN for non-peaks
        sublevel_metadata["filtered"] = np.array(
            [
                (
                    0  # Initialize to 0, will be updated in post-processing
                    if "peak" in sublevel_starts[i]["type"]
                    else np.nan
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get peak prominence-based classification (will be assigned in post-processing)
        sublevel_metadata["classified"] = np.array(
            [
                (
                    np.nan
                    if "peak" in sublevel_starts[i]["type"]
                    else np.nan
                )
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        
        
        # # get plateau size (flat top of peak in samples)
        # sublevel_metadata["plateau_size"] = np.array(
        #     [
        #         (
        #             sublevel_starts[i]["plateau_size"]
        #             if "peak" in sublevel_starts[i]["type"]
        #             and sublevel_starts[i]["plateau_size"] is not None
        #             else np.nan
        #         )
        #         for i in range(num_states)
        #     ],
        #     dtype=np.float64,
        # )

        ## get plateau size in microseconds (converted from samples)
        # sublevel_metadata["plateau_size_us"] = np.array(
        #     [
        #         (
        #             sublevel_starts[i]["plateau_size"] * dt_us
        #             if "peak" in sublevel_starts[i]["type"]
        #             and sublevel_starts[i]["plateau_size"] is not None
        #             else np.nan
        #         )
        #         for i in range(num_states)
        #     ],
        #     dtype=np.float64,
        # )

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

        # Extract middle sublevels (excluding first and last baseline)
        # middle_sublevels = sublevel_metadata["sublevel_max_deviation"][1:-1]

        # peak_id can include None for non-peak sublevels; ignore non-numeric entries.
        peak_ids = [
            int(pid)
            for pid in sublevel_metadata["peak_id"][1:-1]
            if pid is not None and not np.isnan(pid)
        ]

        event_metadata["number_peaks"] = max(peak_ids) if peak_ids else 0
        event_metadata["duration"] = np.sum(
            [sublevel_metadata["sublevel_duration"][1:-1]]
        )
        event_metadata["raw_ecd"] = np.sum(
            [sublevel_metadata["sublevel_raw_ecd"][1:-1]]
        )
        event_metadata["max_deviation"] = np.max(
            [sublevel_metadata["sublevel_max_deviation"][1:-1]]
        )
        event_metadata["baseline_current"] = baseline_mean

        # Calculate event baseline (average of first and last sublevel currents)
        # This represents the local baseline estimated from the event boundaries
        # event_metadata["baseline_current"] = 0.5 * (
        #     sublevel_metadata["sublevel_current"][0]
        #     + sublevel_metadata["sublevel_current"][-1]
        # )

        # Data has already been trimmed to longest segment in _locate_sublevel_transitions
        # sublevel_start_times[1] is after padding_before (which now includes the trim)
        # So we just use the event data between the first and last sublevel
        start_idx = int(
            sublevel_metadata["sublevel_start_times"][1] * samplerate * 1e-6
        )
        end_idx = int(sublevel_metadata["sublevel_start_times"][-1] * samplerate * 1e-6)
        slice_data = data[start_idx:end_idx]

        self.logger.debug(
            f"find_primary_level: data len={len(data)}, start_idx={start_idx}, end_idx={end_idx}, slice len={len(slice_data)}"
        )
        event_metadata["primary_level"],_ = self.find_mode_blockage_level(
                data[
                    int(
                        sublevel_metadata["sublevel_start_times"][1] * samplerate * 1e-6
                    ) : int(
                        sublevel_metadata["sublevel_start_times"][-1] * samplerate * 1e-6
                    )
                ],
                event_metadata["baseline_current"],
                baseline_std,
        )
        # Leave unfolded_level and folded_level as None - will be determined in post-processing
        event_metadata["unfolded_level"] = None
        event_metadata["folded_level"] = None
        event_metadata["baseline_std"] = baseline_std
        event_metadata["translocation_direction"] = None
        event_metadata["sequence"] = None

        return event_metadata


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
            "baseline_current": float,
            "unfolded_level": float,
            "folded_level": float,
            "primary_level": float,
            "baseline_std": float,
            "translocation_direction": str,
            "sequence": str,
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
            "sublevel_cumulative_ecd": float,
            "sublevel_max_deviation": float,
            "sublevel_type": str,
            "peak_id": int,
            "peak_height": float,
            "peak_loc": float,
            "peak_width": float,
            "prominence": float,
            "classified": float,
            # "plateau_size": float,
            "max_blockage": float,
            "left_base": float,
            "right_base": float,
            "left_ips": float,
            "right_ips": float,
            "height_ips": float,
            "filtered": float,  # Changed to float to support NaN for non-peaks
            "normalized_height": float,
            "normalized_prominence": float,
            "normalized_blockage": float,
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

        metadata_units["number_peaks"] = None
        metadata_units["duration"] = "μs"
        metadata_units["raw_ecd"] = "pC"
        metadata_units["max_deviation"] = "pA"
        metadata_units["baseline_current"] = "pA"
        metadata_units["unfolded_level"] = "pA"
        metadata_units["folded_level"] = "pA"
        metadata_units["primary_level"] = "pA"
        metadata_units["baseline_std"] = "pA"
        metadata_units["translocation_direction"] = None
        metadata_units["sequence"] = None

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
        metadata_units["sublevel_cumulative_ecd"] = "pC"
        metadata_units["sublevel_type"] = None
        metadata_units["peak_id"] = None
        metadata_units["peak_height"] = "pA"
        metadata_units["peak_loc"] = "us"
        metadata_units["peak_width"] = "us"
        metadata_units["prominence"] = "pA"
        metadata_units["classified"] = None
        # metadata_units["plateau_size"] = "us"
        metadata_units["max_blockage"] = "pA"
        metadata_units["left_base"] = "pA"
        metadata_units["right_base"] = "pA"
        metadata_units["left_ips"] = "us"
        metadata_units["right_ips"] = "us"
        metadata_units["height_ips"] = "pA"
        metadata_units["filtered"] = None
        metadata_units["normalized_height"] = None
        metadata_units["normalized_prominence"] = None
        metadata_units["normalized_blockage"] = None

        return metadata_units

    @log(logger=logger)
    @override
    def _post_process_events(self, channel: int) -> None:
        """
        Post-process events for a specific channel.
        Performs global classification across all channels once all channels are fitted.

        :param channel: the index of the channel to postprocess
        :type channel: int
        """
        self.logger.info(f"_post_process_events called for channel {channel}")

        # Check if global post-processing has already been performed
        if not hasattr(self, "_global_postprocessing_done"):
            self._global_postprocessing_done = False

        if self._global_postprocessing_done:
            # Global post-processing already completed
            self.logger.info("Global post-processing already completed, skipping")
            return

        # Check if ALL channels have finished fitting before running global post-processing
        # This is necessary because _post_process_events is called per-channel as each finishes
        if not hasattr(self, "eventfitting_status"):
            self.logger.warning("eventfitting_status attribute not found")
            return

        if not self.eventfitting_status:
            self.logger.warning("eventfitting_status is empty")
            return

        # Get all channels that should be fitted
        all_channels = list(self.event_metadata.keys())
        if not all_channels:
            self.logger.warning("No channels in event_metadata")
            return

        self.logger.info(f"All channels: {all_channels}")
        self.logger.info(f"Current eventfitting_status: {self.eventfitting_status}")

        # Check if all channels with events have finished fitting
        # Note: eventfitting_status[channel] is set AFTER _post_process_events is called,
        # so we need to treat the current channel as "done" for this check
        all_fitted = all(
            (ch == channel) or self.eventfitting_status.get(ch, False)
            for ch in all_channels
        )

        self.logger.info(f"All channels fitted: {all_fitted}")

        if not all_fitted:
            # Not all channels are done yet, wait for the last channel to finish
            self.logger.info(
                f"Channel {channel} fitting complete, but waiting for all channels to finish before global post-processing"
            )
            # Log which channels are not done yet
            for ch in all_channels:
                is_done = (ch == channel) or self.eventfitting_status.get(ch, False)
                self.logger.info(
                    f"  Channel {ch}: fitted={is_done} (current={ch == channel}, status={self.eventfitting_status.get(ch, False)})"
                )
            return

        # Mark as done to prevent multiple executions
        self._global_postprocessing_done = True

        # Check if classification is enabled
        classify_levels = self.settings.get("Classify Levels", {}).get("Value", True)

        if not classify_levels:
            self.logger.info(
                "Level classification is disabled in settings. Skipping post-processing."
            )
            # Set a flag to indicate classification was skipped
            self._classification_results = {
                "skipped": True,
                "reason": "Classification disabled by user",
            }
            return

        # Perform global classification across all channels
        self.logger.info(
            "Starting global post-processing analysis with classification utilities"
        )

        # Get all available channels
        channels = list(self.event_metadata.keys())

        if not channels:
            self.logger.warning("No channels found for post-processing")
            return

        # Collect all event data for global analysis
        all_longest_levels: List[float] = []
        all_raw_ecds: List[float] = []
        all_event_info: List[Tuple[int, int]] = (
            []
        )  # Track (channel, event_index) for updating metadata

        for ch in channels:
            if ch not in self.event_metadata:
                continue

            self.logger.info(
                f"Processing channel {ch}, event_metadata type: {type(self.event_metadata[ch])}, length: {len(self.event_metadata[ch]) if hasattr(self.event_metadata[ch], '__len__') else 'N/A'}"
            )

            for event_index, event_data in self.event_metadata[ch].items():
                if not isinstance(event_data, dict):
                    self.logger.warning(
                        f"Event {event_index} in channel {ch} is not a dict: {type(event_data)}"
                    )
                    continue

                primary_level = event_data.get("primary_level")
                raw_ecd = event_data.get("raw_ecd")

                if event_index < 3:
                    self.logger.info(
                        f"Channel {ch}, Event {event_index}: primary_level = {primary_level}, raw_ecd = {raw_ecd}"
                    )

                if primary_level is not None and raw_ecd is not None and raw_ecd > 0:
                    all_longest_levels.append(primary_level)
                    all_raw_ecds.append(raw_ecd)
                    all_event_info.append((ch, event_index))
                else:
                    self.logger.info(
                        f"Event {event_index} in channel {ch} excluded: "
                        f"primary_level={'None' if primary_level is None else f'{primary_level:.2f}'}, "
                        f"raw_ecd={'None' if raw_ecd is None else f'{raw_ecd:.3f}'}"
                    )

        if len(all_longest_levels) == 0:
            self.logger.warning(
                f"No events with valid primary_level and raw_ecd found for analysis. "
                f"Total events checked: {sum(len(self.event_metadata.get(ch, {})) for ch in channels)}. "
                f"This may indicate that events are too short, have no translocation signal, "
                f"or were trimmed too aggressively. Check event detection parameters."
            )
            return

        all_longest_levels_array = np.array(all_longest_levels)
        all_raw_ecds_array = np.array(all_raw_ecds)

        self.logger.info(
            f"Collected {len(all_longest_levels)} events for classification analysis"
        )

        self._classify_folded_unfolded(
            channels=channels,
            all_event_info=all_event_info,
            all_longest_levels_array=all_longest_levels_array,
            all_raw_ecds_array=all_raw_ecds_array,
        )

        # Classify peak prominences for peaks that survived the type filter
        self._classify_peak_prominences(channels)

        # Classify translocation direction from cumulative ECD before first type-3 peak
        self._classify_translocation_direction(channels)

        # Mark fitting as complete for all processed channels
        for channel in channels:
            self.eventfitting_status[channel] = True

        # Build per-event sequence string from classified filtered-3 peaks
        # Reverse sequence for backward-translocating events
        for ch in channels:
            if ch not in self.sublevel_metadata:
                continue
            for event_index, sublevel_data in self.sublevel_metadata[ch].items():
                filtered_values = np.asarray(sublevel_data.get("filtered", []), dtype=float)
                classified = sublevel_data.get("classified", [])
                sequence = "".join(
                    str(int(classified[i]))
                    for i in range(len(filtered_values))
                    if not np.isnan(filtered_values[i])
                    and int(filtered_values[i]) == 3
                    and i < len(classified)
                    and not (isinstance(classified[i], float) and np.isnan(classified[i]))
                )
                if ch in self.event_metadata and event_index in self.event_metadata[ch]:
                    direction = self.event_metadata[ch][event_index].get("translocation_direction", None)
                    if direction == "backward":
                        sequence = sequence[::-1]
                    self.event_metadata[ch][event_index]["sequence"] = sequence

        # Save classification report after all post-processing is complete
        self._save_classification_report()

        self.logger.info(
            "Post-processing analysis completed with automatic folded/unfolded classification."
        )
        

    @log(logger=logger)
    def update_event_metadata_post_processing(
        self,
        channel: int,
        event_index: int,
        unfolded_level: Optional[float] = None,
        folded_level: Optional[float] = None,
    ):

        """
        Update event metadata after post-processing analysis with proper folded/unfolded classification.
        This function should be called after global analysis determines the correct unfolded and folded levels.
        Also reclassifies peaks using the accurate global folded/unfolded levels.

        :param channel: Channel number
        :type channel: int
        :param event_index: Event index within the channel
        :type event_index: int
        :param unfolded_level: Determined unfolded level for normalization
        :type unfolded_level: float
        :param folded_level: Determined folded level for classification
        :type folded_level: float
        """
        # Validate channel and event_index
        if channel not in self.event_metadata:
            self.logger.warning(f"Channel {channel} not found in event metadata")
            return

        if event_index not in self.event_metadata[channel]:
            self.logger.warning(
                f"Event index {event_index} not found in channel {channel}"
            )
            return

        # Update the folded/unfolded classification at event level
        if unfolded_level is not None:
            self.event_metadata[channel][event_index]["unfolded_level"] = unfolded_level
        if folded_level is not None:
            self.event_metadata[channel][event_index]["folded_level"] = folded_level

        # Check if sublevel metadata exists once
        if (
            channel not in self.sublevel_metadata
            or event_index not in self.sublevel_metadata[channel]
        ):
            self.logger.debug(
                f"Skipping event {event_index} in channel {channel}: "
                f"no sublevel_metadata (channel exists: {channel in self.sublevel_metadata}, "
                f"event exists: {event_index in self.sublevel_metadata.get(channel, {})})"
            )
            return

        # Get sublevel data reference once
        sublevel_data = self.sublevel_metadata[channel][event_index]

        # Normalize peak heights and prominences if we have an unfolded level
        if unfolded_level is not None and unfolded_level > 0:
            if (
                "peak_height" in sublevel_data
                and sublevel_data["peak_height"] is not None
            ):
                heights = np.array(sublevel_data["peak_height"])
                valid_mask = ~np.isnan(heights)
                normalized_heights = np.full_like(heights, np.nan)
                normalized_heights[valid_mask] = heights[valid_mask] / unfolded_level
                sublevel_data["normalized_height"] = normalized_heights

            if (
                "prominence" in sublevel_data
                and sublevel_data["prominence"] is not None
            ):
                prominences = np.array(sublevel_data["prominence"])
                valid_mask = ~np.isnan(prominences)
                normalized_prominences = np.full_like(prominences, np.nan)
                normalized_prominences[valid_mask] = (prominences[valid_mask] / unfolded_level)
                sublevel_data["normalized_prominence"] = normalized_prominences

            if (
                "max_blockage" in sublevel_data 
                and sublevel_data["max_blockage"] is not None
            ):
                blockages = np.array(sublevel_data["max_blockage"])
                valid_mask = ~np.isnan(blockages)
                normalized_blockages = np.full_like(blockages, np.nan)
                normalized_blockages[valid_mask] = blockages[valid_mask] / unfolded_level
                sublevel_data["normalized_blockage"] = normalized_blockages

        # Reclassify peaks using global folded/unfolded levels
        if unfolded_level is not None and folded_level is not None:
            # Get baseline and samplerate for this event
            baseline_mean = self.event_metadata[channel][event_index].get("baseline_current")
            baseline_std = self.event_metadata[channel][event_index].get("baseline_std")

            if baseline_mean is not None and baseline_std is not None:
                # Get event loader to retrieve samplerate
                if self.eventloader is None:
                    self.logger.warning(
                        "Event loader is not set; cannot reclassify peaks"
                    )
                    return

                samplerate = self.eventloader.get_samplerate(channel)

                # Extract peak information from sublevel_metadata
                peak_indices: List[int] = []
                properties: Dict[str, List[Union[float, int]]] = {
                    "left_bases": [],
                    "right_bases": [],
                    "prominences": [],
                    "peak_heights": [],
                    "filtered": [],
                }

                # Iterate through sublevels to find peaks
                for i, peak_id in enumerate(sublevel_data.get("peak_id", [])):
                    if peak_id is not None:  # This is a peak
                        peak_indices.append(i)
                        properties["left_bases"].append(
                            sublevel_data["left_base"][i]
                            - np.sign(baseline_mean) * baseline_mean
                        )
                        properties["right_bases"].append(
                            sublevel_data["right_base"][i]
                            - np.sign(baseline_mean) * baseline_mean
                        )
                        properties["prominences"].append(sublevel_data["prominence"][i])
                        properties["peak_heights"].append(
                            sublevel_data["peak_height"][i]
                        )
                        properties["filtered"].append(sublevel_data["filtered"][i])

                if len(peak_indices) > 0:
                    # Create dummy peaks array (just indices for compatibility)
                    peaks = np.array(peak_indices)

                    # Calculate total event length from sublevel durations
                    event_length = np.sum(sublevel_data.get("sublevel_duration", []))

                    # Call filter_peaks with global levels
                    updated_properties = self.filter_peaks(
                        peaks,
                        properties,
                        unfolded_level,
                        folded_level,
                        baseline_std,
                        baseline_mean,
                        samplerate,
                        event_length,
                    )

                    # Update the filtered values directly in sublevel_data
                    # Get the filtered data (could be list or array)
                    filtered_data = sublevel_data["filtered"]
                    if isinstance(filtered_data, np.ndarray):
                        # If it's a numpy array, modify in place
                        for idx, peak_idx in enumerate(peak_indices):
                            filtered_data[peak_idx] = updated_properties["filtered"][
                                idx
                            ]
                    else:
                        # If it's a list, modify in place
                        for idx, peak_idx in enumerate(peak_indices):
                            filtered_data[peak_idx] = updated_properties["filtered"][
                                idx
                            ]

                    # Debug log the classification results
                    self.logger.debug(
                        f"Channel {channel}, Event {event_index}: Reclassified {len(peak_indices)} peaks, filtered values: {filtered_data}"
                    )
                    
    @log(logger=logger)
    @override
    def report_channel_status(self, channel: Optional[int] = None, init=False) -> str:
        """
        Return a string detailing fitting and classification status.

        :param channel: the channel to report on, or None for all channels
        :type channel: Optional[int]
        :param init: whether this is an initialization report
        :type init: bool
        :return: the status report as a string
        :rtype: str
        """
        # Get the base fitting report from parent class
        
        base_report = super().report_channel_status(channel, init)
        # event_total = loader.get_num_events(channel)
        # fitted_total = len(self.event_metadata.get(channel, {}))
        # base_report = f"\nCh{channel}: {fitted_total}/{event_total} good fits\n"
        # rejected_events = self.rejected.get(channel) if getattr(self, "rejected", None) else None
        # if rejected_events:
        #     base_report += "Rejected Events:\n"
        #     for reason, count in sorted(
        #         rejected_events.items(), key=lambda item: (-item[1], item[0])
        #     ):
        #         base_report += f"  {reason}: {count}\n"

        # If initialization or no classification results yet, return base report
        if init or not hasattr(self, "_classification_results"):              
            return base_report

        # During the final post-processing pass, classification results may be
        # available before the base class flips eventfitting_status[channel].
        # In that case, report the channel as complete instead of incomplete.
        if channel is not None and "fitting incomplete" in base_report:
            if self._classification_results and "error" not in self._classification_results:
                loader = getattr(self, "eventloader", None)
                if loader is None:
                    raise RuntimeError(
                        "Event loader is not initialized; cannot determine total events"
                    )
  

        # Add classification information to the report
        classification_report = "\n\nClassification Results:\n\nFolding Classification Results:"

        if "skipped" in self._classification_results:
            classification_report += (
                f"\n  Classification skipped: {self._classification_results['reason']}"
            )
        elif "error" in self._classification_results:
            classification_report += f"\n  {self._classification_results['error']}"
        else:
            results = self._classification_results
            total_events = cast(int, results["total_events"])
            lower_center = cast(float, results["lower_center"])
            higher_center = cast(float, results["higher_center"])
            threshold = cast(float, results["threshold"])
            folded_count = cast(int, results["folded_count"])
            unfolded_count = cast(int, results["unfolded_count"])

            classification_report += f"\n  Total classified: {total_events} events"
            if "ecd_filtered_events" in results:
                ecd_filtered = cast(int, results["ecd_filtered_events"])
                classification_report += (
                    f"\n  ECD-filtered outliers: {ecd_filtered} events"
                )
            classification_report += (
                f"\n  Lower center (unfolded): {lower_center:.2f} pA"
            )
            classification_report += (
                f"\n  Higher center (folded): {higher_center:.2f} pA"
            )
            if "ratio" in results:
                ratio = cast(float, results["ratio"])
                classification_report += f"\n  Ratio (folded/unfolded): {ratio:.3f}"
                if 1.7 <= ratio <= 2.3:
                    classification_report += "✔ (within expected 2:1 ratio)"
                else:
                    classification_report += "✖ (outside expected 2:1 ratio)"
            classification_report += f"\n  Threshold: {threshold:.2f} pA"
            classification_report += (
                f"\n  Folded events: {folded_count} ({folded_count/total_events:.1%})"
            )
            classification_report += f"\n  Unfolded events: {unfolded_count} ({unfolded_count/total_events:.1%})"

        # Add peak classification statistics if available
        if not hasattr(self, "_peak_statistics") and hasattr(self, "sublevel_metadata"):
            try:
                self._collect_peak_statistics(list(self.sublevel_metadata.keys()))
            except Exception as e:
                self.logger.debug(
                    f"Unable to collect peak statistics for report: {str(e)}"
                )

        if hasattr(self, "_peak_statistics"):
            peak_stats = self._peak_statistics
            classification_report += "\n\nPeak Classification Statistics:"

            # Cast values to proper types for type checking
            total_peaks = cast(int, peak_stats["total_peaks"])
            total_classified = cast(int, peak_stats["total_classified"])
            total_unclassified = cast(int, peak_stats["total_unclassified"])
            peak_type_counts = cast(Dict[int, int], peak_stats["peak_type_counts"])

            classification_report += f"\n  Total peaks detected: {total_peaks}"
            classification_report += f"\n  Classified peaks: {total_classified}"
            classification_report += f"\n  Unclassified peaks: {total_unclassified}"

            if total_peaks > 0:
                classified_pct = total_classified / total_peaks * 100
                unclassified_pct = total_unclassified / total_peaks * 100
                classification_report += f" ({classified_pct:.1f}% classified, {unclassified_pct:.1f}% unclassified)"


        if hasattr(self, "_peak_prominence_classification_results"):
            prominence_stats = self._peak_prominence_classification_results
            classification_report += "\n\nPeak Prominence Classification:"

            total_prominence_peaks = cast(
                int, prominence_stats.get("total_peaks", 0)
            )
            lower_prominence_count = cast(
                int, prominence_stats.get("lower_count", 0)
            )
            higher_prominence_count = cast(
                int, prominence_stats.get("higher_count", 0)
            )
            n_components = cast(int, prominence_stats.get("n_components", 0))

            classification_report += (
                f"\n  Total classified peaks: {total_prominence_peaks}"
            )
            classification_report += (
                f"\n  Class 0 (lower prominence): {lower_prominence_count}"
            )
            classification_report += (
                f"\n  Class 1 (higher prominence): {higher_prominence_count}"
            )
            classification_report += f"\n  Selected populations: {n_components}"

            if total_prominence_peaks > 0:
                classification_report += (
                    f" ({lower_prominence_count/total_prominence_peaks:.1%} class 0, "
                    f"{higher_prominence_count/total_prominence_peaks:.1%} class 1)"
                )
                
            threshold = float(prominence_stats.get("threshold"))  # type: ignore
            
            if threshold is not None:
                classification_report += f"\n  Threshold: {cast(float, threshold):.2f} pA"

            centers = prominence_stats.get("centers")
            
             
            if isinstance(centers, list) and centers:
                formatted_centers = ", ".join(f"{center:.2f}" for center in centers)
                classification_report += f"\n  Centers: {formatted_centers} pA"
            # Break down by peak type
            if peak_type_counts:
                classification_report += "\n\n  Peak Filtering breakdown:"
                # Sort by type number for consistent display
                for peak_type in sorted(peak_type_counts.keys()):
                    count = peak_type_counts[peak_type]
                    pct = count / total_peaks * 100 if total_peaks > 0 else 0

                    # Provide meaningful labels for peak types
                    if peak_type == -1:
                        type_label = "Type -1 (Rejected/Unclassified)"
                    elif peak_type == 0:
                        type_label = "Type 0 (Unprocessed)"
                    elif peak_type == 1:
                        type_label = "Type 1 (Carrier Level)"
                    elif peak_type == 2:
                        type_label = "Type 2 (Above Carrier)"
                    elif peak_type == 3:
                        type_label = "Type 3 (Bundle/Cluster)"
                    elif peak_type == 11:
                        type_label = "Type 11 (1U - Unfolding)"
                    elif peak_type == 12:
                        type_label = "Type 12 (1P - Peak with Height)"
                    elif peak_type == 13:
                        type_label = "Type 13 (1/2F - Folding)"
                    elif peak_type == 21:
                        type_label = "Type 21 (2U/2P - Higher Level)"
                    elif peak_type == 22:
                        type_label = "Type 22 (2P/1/2F - General)"
                    else:
                        type_label = f"Type {peak_type}"

                    classification_report += (
                        f"\n    {type_label}: {count} peaks ({pct:.1f}%)"
                    )

        # Translocation direction classification
        classification_report += "\n\nTranslocation Direction Classification:"
        if hasattr(self, "_translocation_direction_results"):
            td = self._translocation_direction_results
            if "skipped" in td:
                classification_report += f"\n  Skipped: {td['reason']}"
                classification_report += "\n  Note: sequences are not dependent on translocation direction"
            else:
                total_td = cast(int, td["total_events"])
                fwd = cast(int, td["forward_count"])
                bwd = cast(int, td["backward_count"])
                classification_report += f"\n  Total classified: {total_td} events"
                classification_report += f"\n  Forward: {fwd} ({fwd/total_td:.1%})"
                classification_report += f"\n  Backward: {bwd} ({bwd/total_td:.1%})"
                classification_report += f"\n  Lower center (log10 ECD): {td['lower_center']:.3f}"
                classification_report += f"\n  Higher center (log10 ECD): {td['higher_center']:.3f}"
                classification_report += f"\n  Threshold: {td['threshold']:.3f}"
        else:
            classification_report += "\n  Not run"

        if hasattr(self, "event_metadata"):
            fwd_total = bwd_total = unclassified_total = total_events = 0
            for ch_events in self.event_metadata.values():
                for ev_data in ch_events.values():
                    total_events += 1
                    direction = ev_data.get("translocation_direction", "")
                    if direction == "forward":
                        fwd_total += 1
                    elif direction == "backward":
                        bwd_total += 1
                    else:
                        unclassified_total += 1
            if total_events > 0:
                classification_report += "\n\n  Event direction breakdown (all events):"
                classification_report += f"\n    Forward:      {fwd_total} ({fwd_total/total_events:.1%})"
                classification_report += f"\n    Backward:     {bwd_total} ({bwd_total/total_events:.1%})"
                classification_report += f"\n    Unclassified: {unclassified_total} ({unclassified_total/total_events:.1%})"

        # Sequence statistics across all channels
        if hasattr(self, "event_metadata"):
            sequence_counts: Dict[str, int] = {}
            total_with_sequence = 0
            for ch, ch_events in self.event_metadata.items():
                for ev_data in ch_events.values():
                    seq = ev_data.get("sequence", "")
                    if seq:
                        sequence_counts[seq] = sequence_counts.get(seq, 0) + 1
                        total_with_sequence += 1

            if sequence_counts:
                classification_report += "\n\nSequence Statistics:"
                classification_report += f"\n  Events with a sequence: {total_with_sequence}"
                for seq, count in sorted(sequence_counts.items(), key=lambda x: -x[1]):
                    pct = count / total_with_sequence * 100
                    classification_report += f"\n  '{seq}': {count} ({pct:.1f}%)"


        return base_report + classification_report
    
###################################################################################################################    
###################################################################################################################    
 

    #classifiers
    
    @log(logger=logger)
    def _classify_folded_unfolded(
        self,
        channels: List[int],
        all_event_info: List[Tuple[int, int]],
        all_longest_levels_array: np.ndarray,
        all_raw_ecds_array: np.ndarray,
    ) -> None:
        """
        Filter events, run GMM classification, and classify events as folded or unfolded DNA.

        Performs blockage-level and ECD-based pre-filtering, fits a 2-component GMM,
        validates the folded/unfolded ratio, retries with tighter filtering if needed,
        then classifies each event and updates metadata.

        :param channels: List of channel indices
        :param all_event_info: List of (channel, event_index) tuples
        :param all_longest_levels_array: Array of longest blockage levels for all events
        :param all_raw_ecds_array: Array of raw ECD values for all events
        """
        # Pre-filter using blockage level threshold
        min_blockage_threshold = self.settings.get("Min Carrier Blockage", {}).get(
            "Value", 300.0
        )
        blockage_threshold_mask = all_longest_levels_array >= min_blockage_threshold
        n_below_threshold = len(all_event_info) - np.sum(blockage_threshold_mask)

        self.logger.info("Blockage level threshold filtering:")
        self.logger.info(f"  Minimum blockage threshold: {min_blockage_threshold:.1f} pA")
        self.logger.info(
            f"  Filtered out {n_below_threshold} events below threshold ({n_below_threshold/len(all_event_info):.1%})"
        )
        self.logger.info(f"  Remaining events: {np.sum(blockage_threshold_mask)}")

        # Pre-filter using ECD to remove outliers/noise (5th–95th percentile of log10 ECD)
        log_ecd = np.log10(all_raw_ecds_array)
        ecd_5th = np.percentile(log_ecd, 5)
        ecd_95th = np.percentile(log_ecd, 95)
        ecd_filter_mask = (log_ecd >= ecd_5th) & (log_ecd <= ecd_95th)

        combined_filter_mask = blockage_threshold_mask & ecd_filter_mask
        n_filtered_out = len(all_event_info) - np.sum(combined_filter_mask)

        self.logger.info("ECD-based filtering:")
        self.logger.info(
            f"  log10(ECD) range: 5th percentile = {ecd_5th:.3f}, 95th percentile = {ecd_95th:.3f}"
        )
        self.logger.info("Combined filtering results:")
        self.logger.info(
            f"  Total filtered out: {n_filtered_out} events ({n_filtered_out/len(all_event_info):.1%})"
        )
        self.logger.info(f"  Remaining events for classification: {np.sum(combined_filter_mask)}")

        filtered_longest_levels = all_longest_levels_array[combined_filter_mask]
        if len(filtered_longest_levels) < 10:
            self.logger.warning("Too few events after combined filtering, using unfiltered data")
            filtered_longest_levels = all_longest_levels_array
            combined_filter_mask = np.ones(len(all_event_info), dtype=bool)

        n_clusters_1d = 2

        self.logger.info(
            f"Performing 1D GMM classification on {len(filtered_longest_levels)} filtered events"
        )
        labels_1d_filtered, centers_1d, gmm_model = self.classify_1d_distribution(
            filtered_longest_levels,
            n_components=n_clusters_1d,
            return_centers=True,
        )

        self.logger.info("1D Classification Summary (Initial):")
        self.logger.info(f"  Centers: {centers_1d}")
        self.logger.info(f"  Clusters found: {len(np.unique(labels_1d_filtered))}")

        sorted_indices = np.argsort(centers_1d)
        lower_center = centers_1d[sorted_indices[0]]
        higher_center = centers_1d[sorted_indices[1]]
        ratio = higher_center / lower_center if lower_center > 0 else 0
        ratio_fits = 1.7 <= ratio <= 2.3

        self.logger.info(f"  Lower center: {lower_center:.2f} pA")
        self.logger.info(f"  Higher center: {higher_center:.2f} pA")
        self.logger.info(
            f"  Ratio (folded/unfolded): {ratio:.3f} - {'GOOD (within 1.7-2.3)' if ratio_fits else 'WARNING (outside expected 2:1 ratio)'}"
        )

        unique_labels, label_counts = np.unique(labels_1d_filtered, return_counts=True)
        for label, count in zip(unique_labels, label_counts):
            cluster_mean = np.mean(filtered_longest_levels[labels_1d_filtered == label])
            self.logger.info(
                f"  Cluster {label}: {count} events ({count/len(labels_1d_filtered):.1%}), mean: {cluster_mean:.3f}"
            )

        if not ratio_fits:
            self.logger.info("Ratio check FAILED - applying blockage-level filtering strategy")

            blockage_25th = np.percentile(filtered_longest_levels, 25)
            self.logger.info(f"  Blockage level 25th percentile: {blockage_25th:.2f} pA")

            blockage_filter_mask = filtered_longest_levels >= blockage_25th
            re_filtered_longest_levels = filtered_longest_levels[blockage_filter_mask]
            n_blockage_filtered = len(filtered_longest_levels) - len(re_filtered_longest_levels)

            self.logger.info(
                f"  Filtered out {n_blockage_filtered} additional events below 25th percentile"
            )
            self.logger.info(
                f"  Remaining events for re-classification: {len(re_filtered_longest_levels)}"
            )

            if len(re_filtered_longest_levels) >= 10:
                self.logger.info("Re-running GMM on blockage-filtered data...")
                _, centers_1d_new, gmm_model_new = self.classify_1d_distribution(
                    re_filtered_longest_levels,
                    n_components=n_clusters_1d,
                    return_centers=True,
                )

                sorted_indices_new = np.argsort(centers_1d_new)
                lower_center_new = centers_1d_new[sorted_indices_new[0]]
                higher_center_new = centers_1d_new[sorted_indices_new[1]]
                ratio_new = higher_center_new / lower_center_new if lower_center_new > 0 else 0
                ratio_fits_new = 1.7 <= ratio_new <= 2.3

                self.logger.info("1D Classification Summary (After blockage filtering):")
                self.logger.info(f"  New centers: {centers_1d_new}")
                self.logger.info(f"  Lower center: {lower_center_new:.2f} pA")
                self.logger.info(f"  Higher center: {higher_center_new:.2f} pA")
                self.logger.info(
                    f"  New ratio: {ratio_new:.3f} - {'GOOD (within 1.7-2.3)' if ratio_fits_new else 'STILL POOR'}"
                )

                if ratio_fits_new or ratio_new < ratio:
                    self.logger.info("Using blockage-filtered GMM results (ratio improved)")
                    centers_1d = centers_1d_new
                    gmm_model = gmm_model_new
                    lower_center = lower_center_new
                    higher_center = higher_center_new
                    ratio = ratio_new
                    ratio_fits = ratio_fits_new
                    filtered_longest_levels = re_filtered_longest_levels
                else:
                    self.logger.warning("Blockage filtering did not improve ratio, using original results")
            else:
                self.logger.warning("Too few events after blockage filtering, using original results")

        if len(centers_1d) < 2:
            self.logger.warning("Could not find two distinct distributions for folded/unfolded classification")
            self.logger.warning("Classification requires at least 2 centers from GMM analysis")
            self._classification_results = {"error": "Could not find two distinct distributions"}
            self._collect_peak_statistics(channels)
            return

        # Calculate threshold based on ratio quality
        if ratio_fits:
            threshold = (lower_center + higher_center) / 2.0
            self.logger.info(
                f"Using midpoint threshold (ratio is good): {threshold:.2f} pA"
            )
        else:
            threshold = lower_center * 1.5
            self.logger.info(
                f"Using ratio-aware threshold (ratio is poor): {threshold:.2f} pA"
            )

        self.logger.info("Distribution analysis:")
        self.logger.info(f"  Lower center: {lower_center:.3f}")
        self.logger.info(f"  Higher center: {higher_center:.3f}")
        self.logger.info(f"  Threshold: {threshold:.3f}")
        self.logger.info(f"  Ratio: {ratio:.3f}")
        if ratio_fits:
            self.logger.info("  Ratio quality: GOOD - using midpoint threshold")
        else:
            self.logger.info(
                "  Ratio quality: POOR - using ratio-aware threshold as fallback"
            )

        # Classify each event (including filtered-out events) based on its primary_level
        # Higher absolute blockage (above threshold) = Folded DNA (more compact)
        # Lower absolute blockage (below threshold) = Unfolded DNA (more extended)
        folded_count = 0
        unfolded_count = 0

        # Process ALL events (original unfiltered list) for classification
        self.logger.info(f"Starting event classification loop: {len(all_event_info)} events to process")
        for i, (ch, event_index) in enumerate(all_event_info):
            self.logger.debug(f"Processing event {i+1}/{len(all_event_info)}: Channel {ch}, Event {event_index}")
            event_primary_level = all_longest_levels_array[i]
            # Classify based on threshold comparison
            if event_primary_level >= threshold:
                # Above threshold = Folded (higher absolute blockage, more compact)
                event_folded_level = event_primary_level
                event_unfolded_level = event_primary_level / 2.0
                folded_count += 1
            else:
                # Below threshold = Unfolded (lower absolute blockage, more extended)
                event_unfolded_level = event_primary_level
                event_folded_level = event_primary_level * 2.0
                unfolded_count += 1

            # Update metadata with event-specific levels
            try:
                self.update_event_metadata_post_processing(
                    ch,
                    event_index,
                    event_unfolded_level,
                    event_folded_level,
                )
            except Exception as e:
                self.logger.error(f"Error in update_event_metadata_post_processing: {str(e)}")

        self.logger.info("Event classification completed:")
        self.logger.info(
            f"  Folded events: {folded_count} ({folded_count/len(all_event_info):.1%})"
        )
        self.logger.info(
            f"  Unfolded events: {unfolded_count} ({unfolded_count/len(all_event_info):.1%})"
        )

        # Store classification results for status report
        self._classification_results = {
            "total_events": len(all_event_info),
            "folded_count": folded_count,
            "unfolded_count": unfolded_count,
            "lower_center": lower_center,
            "higher_center": higher_center,
            "threshold": threshold,
            "ratio": ratio,
            "ecd_filtered_events": n_filtered_out,
        }

        # Optionally visualize the classification
        if self.settings.get("Visualize Classification", {}).get("Value", False):
            try:
                plot_path = None
                loader = getattr(self, "eventloader", None)
                if loader is None:
                    self.logger.warning(
                        "Visualization enabled, but no event loader is available to derive an output path"
                    )
                else:
                    base_file = loader.get_base_file()
                    plot_path = base_file.with_name(f"{base_file.stem}_folding_classification.png")

                # Calculate threshold for visualization (same logic as above)
                if ratio_fits:
                    viz_threshold = (lower_center + higher_center) / 2.0
                else:
                    viz_threshold = lower_center * 1.5

                ecd_outlier_levels = all_longest_levels_array[~combined_filter_mask]

                # For visualization, use filtered data and corresponding labels/centers
                filtered_data = all_longest_levels_array[combined_filter_mask]
                filtered_labels = (filtered_data >= viz_threshold).astype(int)

                self.visualize_folding_classification(
                    data=filtered_data,
                    labels=filtered_labels,
                    centers=np.array([lower_center, higher_center]),
                    gmm_model=gmm_model,
                    threshold=viz_threshold,
                    title="GMM Classification: Folded vs Unfolded DNA (ECD-filtered)",
                    ecd_outliers=ecd_outlier_levels,
                    save_path=plot_path,
                )
            except Exception as e:
                self.logger.error(f"Error during classification visualization: {str(e)}", exc_info=True)

    @log(logger=logger)
    def visualize_folding_classification(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        centers: np.ndarray,
        gmm_model: GaussianMixture,
        threshold: float,
        title: str = "GMM Classification of Longest Blockage Levels",
        ecd_outliers: Optional[np.ndarray] = None,
        save_path: Optional[str] = None,
    ) -> None:
        """
        Visualize the GMM classification results with histogram and fitted Gaussians.

        :param data: Original 1D data array
        :type data: np.ndarray
        :param labels: Cluster labels for each data point
        :type labels: np.ndarray
        :param centers: Cluster centers (means)
        :type centers: np.ndarray
        :param gmm_model: Fitted GaussianMixture model
        :type gmm_model: GaussianMixture
        :param threshold: Classification threshold between folded/unfolded
        :type threshold: float
        :param title: Plot title
        :type title: str
        :param ecd_outliers: Optional data points excluded by ECD filtering
        :type ecd_outliers: Optional[np.ndarray]
        :param save_path: Optional path to save the figure
        :type save_path: Optional[str]
        """
        import matplotlib.pyplot as plt
        from scipy.stats import norm

        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot histogram of all data
        n_bins = 50
        counts, bins, patches = ax.hist(
            data, bins=n_bins, density=True, alpha=0.5, color="gray", label="All Data"
        )

        if ecd_outliers is not None and len(ecd_outliers) > 0:
            ax.hist(
                ecd_outliers,
                bins=n_bins,
                density=True,
                alpha=0.35,
                color="orange",
                label=f"ECD outliers ({len(ecd_outliers)} events)",
                hatch="//",
                edgecolor="darkorange",
            )

        # Sort centers to identify folded/unfolded
        sorted_indices = np.argsort(centers)
        lower_center = centers[sorted_indices[0]]
        higher_center = centers[sorted_indices[1]]

        # Plot histogram for each cluster
        colors = ["blue", "red"]
        cluster_labels = ["Unfolded (lower)", "Folded (higher)"]

        for i, (cluster_idx, center) in enumerate(
            zip(sorted_indices, [lower_center, higher_center])
        ):
            cluster_data = data[labels == cluster_idx]
            ax.hist(
                cluster_data,
                bins=n_bins,
                density=True,
                alpha=0.6,
                color=colors[i],
                label=f"{cluster_labels[i]}: {center:.2f} pA ({len(cluster_data)} events)",
            )

        # Plot fitted Gaussian distributions
        x_range = np.linspace(data.min(), data.max(), 1000)

        for i, (cluster_idx, center) in enumerate(
            zip(sorted_indices, [lower_center, higher_center])
        ):
            mean = gmm_model.means_[cluster_idx][0]
            std = np.sqrt(gmm_model.covariances_[cluster_idx][0][0])
            weight = gmm_model.weights_[cluster_idx]

            gaussian = weight * norm.pdf(x_range, mean, std)
            ax.plot(
                x_range,
                gaussian,
                color=colors[i],
                linewidth=2,
                linestyle="--",
                label=f"{cluster_labels[i]} Gaussian (mu={mean:.2f}, std={std:.2f})",
            )

        # Plot threshold line
        ax.axvline(
            threshold,
            color="black",
            linestyle="-",
            linewidth=2,
            label=f"Threshold: {threshold:.2f} pA",
        )

        # Add labels and formatting
        ax.set_xlabel("Longest Blockage Level (pA)", fontsize=12)
        ax.set_ylabel("Probability Density", fontsize=12)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.legend(loc="best", fontsize=10)
        ax.grid(True, alpha=0.3)

        # Add text annotation with classification info
        folded_count = len(data[data >= threshold])
        unfolded_count = len(data[data < threshold])
        total = len(data)
        outlier_count = len(ecd_outliers) if ecd_outliers is not None else 0

        info_text = (
            f"Total Events: {total}\n"
            f"Folded (≥ threshold): {folded_count} ({folded_count/total:.1%})\n"
            f"Unfolded (< threshold): {unfolded_count} ({unfolded_count/total:.1%})\n"
            f"ECD outliers: {outlier_count}"
        )
        ax.text(
            0.02,
            0.98,
            info_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            self.logger.info(f"Classification visualization saved to {save_path}")

        #plt.show()

    @log(logger=logger)
    def _classify_peak_prominences(self, channels: List[int]) -> None:
        """
        Classify peak prominences for peaks whose filtered value is 1, 2, or 3.

        The lower prominence population is written as 0 and the higher population
        as 1. If a single population is selected by BIC, all eligible peaks are
        written as 0.
        """
        prominence_values: List[float] = []
        prominence_refs: List[Tuple[int, int, int]] = []

        for ch in channels:
            if ch not in self.sublevel_metadata:
                continue

            for event_index, sublevel_data in self.sublevel_metadata[ch].items():
                filtered_values = np.asarray(sublevel_data.get("filtered", []), dtype=float)
                prominences = np.asarray(sublevel_data.get("prominence", []), dtype=float)
                peak_ids = sublevel_data.get("peak_id", [])

                if "classified" not in sublevel_data or len(sublevel_data["classified"]) != len(peak_ids):
                    self.sublevel_metadata[ch][event_index]["classified"] = np.full(
                        len(peak_ids), np.nan, dtype=np.float64
                    )

                for peak_index, peak_id in enumerate(peak_ids):
                    if peak_id is None or (isinstance(peak_id, float) and np.isnan(peak_id)):
                        continue
                    if peak_index >= len(filtered_values) or peak_index >= len(prominences):
                        continue

                    peak_type = filtered_values[peak_index]
                    if np.isnan(peak_type) or int(peak_type) not in {1, 2, 3}:
                        continue

                    prominence = prominences[peak_index]
                    if np.isnan(prominence):
                        continue

                    prominence_values.append(float(prominence))
                    prominence_refs.append((ch, event_index, peak_index))

        if not prominence_values:
            self.logger.warning(
                "No peaks with filtered values 1, 2, or 3 were available for prominence classification"
            )
            return

        prominence_array = np.asarray(prominence_values, dtype=np.float64)
        prominence_reshaped = prominence_array.reshape(-1, 1)

        candidate_models: List[Tuple[float, GaussianMixture]] = []
        for n_components in (1, 2):
            if len(prominence_array) < n_components:
                continue
            gmm = GaussianMixture(n_components=n_components, random_state=42)
            gmm.fit(prominence_reshaped)
            candidate_models.append((gmm.bic(prominence_reshaped), gmm))

        if not candidate_models:
            self.logger.warning("Unable to fit a prominence classification model")
            return

        selected_model = min(candidate_models, key=lambda item: item[0])[1]
        #gmm_labels = selected_model.predict(prominence_reshaped)
        centers = selected_model.means_.flatten()

        if selected_model.n_components == 1:
            class_labels = np.zeros(len(prominence_array), dtype=np.float64)
            threshold = None
        else:
            sorted_indices = np.argsort(centers)
            lower_idx = int(sorted_indices[0])
            higher_idx = int(sorted_indices[1])
            midpoint = float((centers[lower_idx] + centers[higher_idx]) / 2.0)
            lower_std = float(np.sqrt(selected_model.covariances_.flatten()[lower_idx]))
            min_threshold = float(centers[lower_idx]) + 3.0 * lower_std
            if midpoint >= min_threshold:
                threshold = midpoint
                threshold_type = "midpoint"
            else:
                threshold = min_threshold
                threshold_type = "3σ floor"
            class_labels = np.where(prominence_array >= threshold, 1.0, 0.0).astype(np.float64)

        for class_label, (ch, event_index, peak_index) in zip(class_labels, prominence_refs):
            self.sublevel_metadata[ch][event_index]["classified"][peak_index] = class_label

        self._peak_prominence_classification_results = {
            "total_peaks": int(len(prominence_array)),
            "n_components": int(selected_model.n_components),
            "threshold": threshold,
            "threshold_type": threshold_type,
            "centers": centers.tolist(),
            "lower_count": int(np.sum(class_labels == 0)),
            "higher_count": int(np.sum(class_labels == 1)),
        }

        if self.settings.get("Visualize Classification", {}).get("Value", False):
            loader = getattr(self, "eventloader", None)
            plot_path = None
            if loader is None:
                self.logger.warning(
                    "Peak prominence visualization enabled, but no event loader is available to derive an output path"
                )
            else:
                base_file = loader.get_base_file()
                plot_path = base_file.with_name(
                    f"{base_file.stem}_peak_prominence_classification.png"
                )

            self._visualize_peak_prominence_classification(
                data=prominence_array,
                labels=class_labels,
                centers=centers,
                gmm_model=selected_model,
                threshold=threshold,
                threshold_type=threshold_type,
                save_path=str(plot_path) if plot_path is not None else None,
            )

    @log(logger=logger)
    def _visualize_peak_prominence_classification(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        centers: np.ndarray,
        gmm_model: GaussianMixture,
        threshold: Optional[float] = None,
        threshold_type: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> None:
        """
        Visualize the prominence classification results for peaks.
        """
        import matplotlib.pyplot as plt
        from scipy.stats import norm

        fig, ax = plt.subplots(figsize=(12, 6))
        n_bins = 50
        ax.hist(
            data,
            bins=n_bins,
            density=True,
            alpha=0.5,
            color="gray",
            label="All Peaks",
        )

        sorted_indices = np.argsort(centers)
        colors = ["blue", "red"]
        class_labels = ["Lower prominence (0)", "Higher prominence (1)"]

        for class_idx, gmm_idx in enumerate(sorted_indices):
            cluster_data = data[labels == class_idx]
            ax.hist(
                cluster_data,
                bins=n_bins,
                density=True,
                alpha=0.6,
                color=colors[class_idx % len(colors)],
                label=f"{class_labels[class_idx]}: {centers[gmm_idx]:.2f} pA ({len(cluster_data)} peaks)",
            )

            mean = gmm_model.means_[gmm_idx][0]
            std = np.sqrt(gmm_model.covariances_[gmm_idx][0][0])
            weight = gmm_model.weights_[gmm_idx]
            x_range = np.linspace(data.min(), data.max(), 1000)
            ax.plot(
                x_range,
                weight * norm.pdf(x_range, mean, std),
                color=colors[class_idx % len(colors)],
                linewidth=2,
                linestyle="--",
                label=f"{class_labels[class_idx]} Gaussian (mu={mean:.2f}, std={std:.2f})",
            )

        if threshold is not None:
            ax.axvline(
                threshold,
                color="black",
                linestyle="-",
                linewidth=2,
                label=f"Threshold: {threshold:.2f} pA",
            )

        ax.set_xlabel("Peak Prominence (pA)", fontsize=12)
        ax.set_ylabel("Probability Density", fontsize=12)
        ax.set_title("Peak Prominence Classification", fontsize=14, fontweight="bold")
        ax.legend(loc="best", fontsize=10)
        ax.grid(True, alpha=0.3)

        total = len(data)
        lower_count = int(np.sum(labels == 0))
        higher_count = int(np.sum(labels == 1))

        info_text = (
            f"Total Peaks: {total}\n"
            f"Class 0: {lower_count} ({lower_count/total:.1%})\n"
            f"Class 1: {higher_count} ({higher_count/total:.1%})\n"
            f"Threshold type: {threshold_type if threshold_type else 'N/A'}"
        )
        ax.text(
            0.02,
            0.98,
            info_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            self.logger.info(
                f"Peak prominence classification visualization saved to {save_path}"
            )

        plt.close(fig)
        
    @log(logger=logger)
    def _collect_peak_statistics(self, channels: List[int]) -> None:
        """
        Collect statistics about peak classifications across all events.

        :param channels: List of channel indices to process
        :type channels: List[int]
        """
        # Initialize counters
        peak_type_counts: Dict[int, int] = {}
        total_peaks = 0
        total_classified = 0
        total_unclassified = 0

        # Iterate through all channels and events
        for ch in channels:
            if ch not in self.sublevel_metadata:
                continue

            for event_index in self.sublevel_metadata[ch]:
                sublevel_data = self.sublevel_metadata[ch][event_index]

                # Check if filtered data exists
                if "filtered" not in sublevel_data:
                    continue

                filtered_values = sublevel_data["filtered"]
                peak_ids = sublevel_data.get("peak_id", [])

                # Count peaks by their filtered type
                for i, peak_id in enumerate(peak_ids):
                    if peak_id is not None and not (
                        isinstance(peak_id, float) and np.isnan(peak_id)
                    ):
                        total_peaks += 1
                        filtered_type = filtered_values[i]

                        if filtered_type is not None and not (
                            isinstance(filtered_type, float)
                            and np.isnan(filtered_type)
                        ):
                            # Count by type
                            peak_type_counts[int(filtered_type)] = (
                                peak_type_counts.get(int(filtered_type), 0) + 1
                            )

                            # Classify as classified or unclassified
                            if filtered_type > 0:
                                total_classified += 1
                            else:
                                total_unclassified += 1

        # Store results
        self._peak_statistics = {
            "total_peaks": total_peaks,
            "total_classified": total_classified,
            "total_unclassified": total_unclassified,
            "peak_type_counts": peak_type_counts,
            "threshold type": self._peak_prominence_classification_results.get("threshold_type", "N/A")
        }

        self.logger.info(
            f"Peak statistics collected: {total_peaks} total peaks, "
            f"{total_classified} classified, {total_unclassified} unclassified"
        )
        self.logger.info(f"Peak type distribution: {peak_type_counts}")



    @log(logger=logger)
    def _classify_translocation_direction(self, channels: List[int]) -> None:
        """
        Classify events as forward or backward based on log10 cumulative ECD
        of all sublevels before the first type-3 peak.

        Events with higher pre-peak3 cumulative ECD are labelled 'forward';
        lower cumulative ECD events are labelled 'backward'.
        Result stored in event_metadata[ch][event_index]['translocation_direction'].
        """
        pre_peak3_ecds: List[float] = []
        event_refs: List[Tuple[int, int]] = []

        for ch in channels:
            if ch not in self.sublevel_metadata:
                continue
            for event_index, sublevel_data in self.sublevel_metadata[ch].items():
                filtered_values = np.asarray(sublevel_data.get("filtered", []), dtype=float)
                cumulative_ecds = np.asarray(sublevel_data.get("sublevel_cumulative_ecd", []), dtype=float)

                if len(cumulative_ecds) == 0:
                    continue

                type3_mask = ~np.isnan(filtered_values) & (filtered_values.astype(int) == 3)
                type3_indices = np.where(type3_mask)[0]
                if len(type3_indices) == 0:
                    continue

                first_type3_idx = type3_indices[0]
                last_type3_idx = type3_indices[-1]

                if first_type3_idx >= len(cumulative_ecds) or last_type3_idx >= len(cumulative_ecds):
                    continue

                ecd_before = float(cumulative_ecds[first_type3_idx])
                ecd_after = float(cumulative_ecds[-1] - cumulative_ecds[last_type3_idx])

                if ecd_before <= 0 or ecd_after <= 0:
                    continue

                pre_peak3_ecds.append(np.log10(ecd_before / ecd_after))
                event_refs.append((ch, event_index))

        if len(pre_peak3_ecds) < 2:
            self.logger.warning(
                "Too few events with type-3 peaks for translocation direction classification"
            )
            self._translocation_direction_results = {"skipped": True, "reason": "Too few events with type-3 peaks"}
            return

        log_ecds = np.array(pre_peak3_ecds)
        log_ecds_reshaped = log_ecds.reshape(-1, 1)

        gmm_model = GaussianMixture(n_components=2, random_state=42)
        gmm_model.fit(log_ecds_reshaped)
        centers = gmm_model.means_.flatten()

        self.logger.info(f"Translocation direction GMM centers (log10 ECD): {centers}")

        sorted_indices = np.argsort(centers)
        lower_center = centers[sorted_indices[0]]
        higher_center = centers[sorted_indices[1]]
        threshold = (lower_center + higher_center) / 2.0

        self.logger.info(
            f"  Lower center: {lower_center:.3f}, Higher center: {higher_center:.3f}, Threshold: {threshold:.3f}"
        )

        class_labels = (log_ecds >= threshold).astype(int)
        forward_count = int(np.sum(class_labels == 1))
        backward_count = int(np.sum(class_labels == 0))

        for label, (ch, event_index) in zip(class_labels, event_refs):
            direction = "forward" if label == 1 else "backward"
            if ch in self.event_metadata and event_index in self.event_metadata[ch]:
                self.event_metadata[ch][event_index]["translocation_direction"] = direction

        self.logger.info(
            f"  Forward: {forward_count} ({forward_count/len(event_refs):.1%}), "
            f"Backward: {backward_count} ({backward_count/len(event_refs):.1%})"
        )

        self._translocation_direction_results = {
            "total_events": len(event_refs),
            "forward_count": forward_count,
            "backward_count": backward_count,
            "lower_center": float(lower_center),
            "higher_center": float(higher_center),
            "threshold": float(threshold),
        }

        if self.settings.get("Visualize Classification", {}).get("Value", False):
            try:
                plot_path = None
                loader = getattr(self, "eventloader", None)
                if loader is None:
                    self.logger.warning(
                        "Visualization enabled, but no event loader is available to derive an output path"
                    )
                else:
                    base_file = loader.get_base_file()
                    plot_path = base_file.with_name(
                        f"{base_file.stem}_translocation_direction_classification.png"
                    )

                self._visualize_translocation_direction_classification(
                    data=log_ecds,
                    labels=class_labels,
                    centers=centers,
                    gmm_model=gmm_model,
                    threshold=threshold,
                    save_path=str(plot_path) if plot_path is not None else None,
                )
            except Exception as e:
                self.logger.error(
                    f"Error during translocation direction visualization: {str(e)}",
                    exc_info=True,
                )

    @log(logger=logger)
    def _visualize_translocation_direction_classification(
        self,
        data: np.ndarray,
        labels: np.ndarray,
        centers: np.ndarray,
        gmm_model: GaussianMixture,
        threshold: float,
        threshold_type: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> None:
        """Visualize translocation direction classification on log10 cumulative pre-peak3 ECD."""
        import matplotlib.pyplot as plt
        from scipy.stats import norm

        fig, ax = plt.subplots(figsize=(12, 6))
        n_bins = 50
        ax.hist(data, bins=n_bins, density=True, alpha=0.5, color="gray", label="All Events")

        sorted_indices = np.argsort(centers)
        colors = ["blue", "red"]
        class_names = ["Backward (0)", "Forward (1)"]

        for class_idx, gmm_idx in enumerate(sorted_indices):
            cluster_data = data[labels == class_idx]
            ax.hist(
                cluster_data,
                bins=n_bins,
                density=True,
                alpha=0.6,
                color=colors[class_idx],
                label=f"{class_names[class_idx]}: center={centers[gmm_idx]:.3f} ({len(cluster_data)} events)",
            )

            mean = gmm_model.means_[gmm_idx][0]
            std = np.sqrt(gmm_model.covariances_[gmm_idx][0][0])
            weight = gmm_model.weights_[gmm_idx]
            x_range = np.linspace(data.min(), data.max(), 1000)
            ax.plot(
                x_range,
                weight * norm.pdf(x_range, mean, std),
                color=colors[class_idx],
                linewidth=2,
                linestyle="--",
                label=f"{class_names[class_idx]} Gaussian (mu={mean:.3f}, std={std:.3f})",
            )

        ax.axvline(
            threshold,
            color="black",
            linestyle="-",
            linewidth=2,
            label=f"Threshold: {threshold:.3f}",
        )

        ax.set_xlabel("log\u2081\u2080 (ECD at first type-3 peak / ECD after last type-3 peak)", fontsize=12)
        ax.set_ylabel("Probability Density", fontsize=12)
        ax.set_title("Translocation Direction Classification", fontsize=14, fontweight="bold")
        ax.legend(loc="best", fontsize=10)
        ax.grid(True, alpha=0.3)

        total = len(data)
        backward_count = int(np.sum(labels == 0))
        forward_count = int(np.sum(labels == 1))
        info_text = (
            f"Total Events: {total}\n"
            f"Backward: {backward_count} ({backward_count/total:.1%})\n"
            f"Forward: {forward_count} ({forward_count/total:.1%})"
        )
        ax.text(
            0.02, 0.98, info_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            self.logger.info(f"Translocation direction visualization saved to {save_path}")
        plt.close(fig)


    @log(logger=logger)
    def _save_classification_report(self) -> None:
        """
        Generate and save a comprehensive classification report to a text file.

        Uses the report from report_channel_status() to avoid code duplication.
        """
        try:
            loader = getattr(self, "eventloader", None)
            if loader is None:
                self.logger.warning("No event loader available; skipping classification report save")
                return

            base_file = loader.get_base_file()
            report_path = base_file.with_name(f"{base_file.stem}_classification_report.txt")

            # Get the classification report from report_channel_status
            report_text = self.report_channel_status(channel=None, init=False)

            # Add settings section
            settings_section = "\n\nFITTING SETTINGS\n" + "-" * 80 + "\n"
            if self.settings:
                for key, setting_dict in sorted(self.settings.items()):
                    if key.lower() == "metaeventloader":
                        # Save the path of the event loader object
                        if hasattr(self, "eventloader") and self.eventloader is not None:
                            if hasattr(self.eventloader, "get_base_file"):
                                base_file = self.eventloader.get_base_file()
                                settings_section += f"{key}: {base_file}\n"
                            else:
                                settings_section += f"{key}: {self.eventloader}\n"
                        else:
                            settings_section += f"{key}: Not available\n"
                    elif isinstance(setting_dict, dict) and "Value" in setting_dict:
                        value = setting_dict["Value"]
                        settings_section += f"{key}: {value}\n"
            else:
                settings_section += "No settings available\n"

            # Add header and footer with settings
            header = "=" * 80 + "\nCLASSIFICATION REPORT: DNA Folding and Peak Analysis\n" + "=" * 80 + "\n"
            footer = "\n" + "=" * 80
            report_text = header + report_text.lstrip() + settings_section + footer

            # Write report to file with UTF-8 encoding
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_text)

            self.logger.info(f"Classification report saved to {report_path}")
        except Exception as e:
            self.logger.error(f"Error saving classification report: {str(e)}", exc_info=True)

 

    @log(logger=logger)
    def classify_1d_distribution(
        self,
        data: np.ndarray,
        n_components: int = 2,
        return_centers: bool = False,
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray, GaussianMixture]]:
        """
        Classify 1D data into clusters using Gaussian Mixture Model.

        :param data: 1D array of data to classify
        :type data: np.ndarray
        :param n_components: Number of Gaussian components to fit
        :type n_components: int
        :param return_centers: Whether to return cluster centers and GMM model along with labels
        :type return_centers: bool
        :return: Cluster labels, optionally with centers and fitted GMM model
        :rtype: Union[np.ndarray, Tuple[np.ndarray, np.ndarray, GaussianMixture]]
        """
        data_reshaped = np.array(data).reshape(-1, 1)

        gmm = GaussianMixture(n_components=n_components, random_state=42)
        labels = gmm.fit_predict(data_reshaped)
        centers = gmm.means_.flatten()

        if return_centers:
            return labels, centers, gmm
        return labels   
    
    @log(logger=logger)
    def classify_2d_distribution(
        self,
        data: np.ndarray,
        n_components: int = 2,
        return_centers: bool = False,
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray, GaussianMixture]]:
        """
        Classify 2D data into clusters using Gaussian Mixture Model.

        :param data: 2D array of data to classify
        :type data: np.ndarray
        :param n_components: Number of Gaussian components to fit
        :type n_components: int
        :param return_centers: Whether to return cluster centers and GMM model along with labels
        :type return_centers: bool
        :return: Cluster labels, optionally with centers and fitted GMM model
        :rtype: Union[np.ndarray, Tuple[np.ndarray, np.ndarray, GaussianMixture]]
        """
        data_reshaped = np.array(data).reshape(-1, 2)

        gmm = GaussianMixture(n_components=n_components, random_state=42)
        labels = gmm.fit_predict(data_reshaped)
        centers = gmm.means_.flatten()

        if return_centers:
            return labels, centers, gmm
        return labels


    @log(logger=logger)
    def filter_peaks(
        self,
        peaks,
        properties,
        unfolded_level,
        folded_level,
        baseline_std,
        baseline,
        samplerate,
        event_length,
    ):
      
        #Defining variables and thresholds
          
        t1_std = int(self.settings["Lower Filter Threshold"]["Value"])
        t2_std = int(self.settings["Higher Filter Threshold"]["Value"])
        

        # event_id = getattr(self, "_debug_event_id", None)


        num_peaks = self.settings["Number of peaks"]["Value"]
        prom_indices = np.argsort(properties["prominences"])[::-1]  # all sorted
        filtered = properties["filtered"]

        # Helper thresholds for classification

        # lower_bound = t1_std * baseline_std

        # BARCODE
        """
        Filters peaks based on their level and proximity, classifying potential bundles or barcode features.
        - Type 1: Peaks on the same DNA carrier level (both bases around unfolded_level).
        - Type 2: Peaks higher than the carrier level (both bases above unfolded_level).
        - Type 3: Clusters (bundles) of close peaks with same type (1).
        """
        # # Convert commonly-used properties to numpy arrays for vectorized ops
        # left_bases = np.array(properties.get("left_bases", []), dtype=float) + np.sign(baseline) * baseline
        # right_bases = np.array(properties.get("right_bases", []), dtype=float) + np.sign(baseline) * baseline
        # prominences = np.array(properties.get("prominences", []), dtype=float)
        # widths = np.array(properties.get("widths", []), dtype=float)
        # ips_left = np.array(properties.get("left_ips", []), dtype=float)
        # ips_right = np.array(properties.get("right_ips", []), dtype=float)


        # Early return if no peaks
        if len(peaks) == 0:
            # preserve whatever filtered was provided (likely empty)
            properties["filtered"] = properties.get("filtered", [])
            return properties

        # Ensure filtered is a numeric array matching number of peaks
        filtered_list = list(properties.get("filtered", []))
        if len(filtered_list) < len(peaks):
            filtered_list = filtered_list + [0] * (len(peaks) - len(filtered_list))
        elif len(filtered_list) > len(peaks):
            filtered_list = filtered_list[: len(peaks)]
        filtered = np.array(filtered_list, dtype=int)
        if self.settings["Event Type"]["Value"] == "Barcode":
            # Classify by ordered ranges, requiring both bases to land in the same band.
            # 0: both bases below the lower barcode threshold
            # 1: both bases between the lower threshold and the type-2 lower bound
            # 2: both bases around twice the unfolded level
            # -1: either base above the type-2 upper bound
            # Define thresholds. We treat type-1 as anything from unfolded_level + t1*std
            # up to (but not including) the type-2 lower bound. Type-2 is centered
            # around 2*unfolded_level ± thresholds, and anything above that upper
            # bound is -1 (noise).
            type0_thresh = t2_std * baseline_std
            type1_thresh = unfolded_level + t1_std * baseline_std
            type2_thresh = unfolded_level + t2_std * baseline_std

            # Debug prints to help trace classification during development
            # print(
            #     f"[debug] filter_peaks: event_id={event_id}, unfolded_level={unfolded_level}, baseline_std={baseline_std}, t1={t1_std}, t2={t2_std}"
            # )
            # print(
            #     f"[debug] thresholds: event_id={event_id}, type0={type0_thresh}, type1={type1_thresh}, type2={type2_thresh}"
            # )
            # try:
            #     print(
            #         f"[debug] peaks count={len(peaks)}, event_id={event_id}, left_bases={left_bases.tolist()}, right_bases={right_bases.tolist()}"
            #     )
            # except Exception:
            #     print(f"[debug] peaks count={len(peaks)}, event_id={event_id}, left_bases={left_bases}, right_bases={right_bases}")

            for i in range(len(peaks)):
                left_base = properties["left_bases"][i] + np.sign(baseline) * baseline
                right_base = properties["right_bases"][i] + np.sign(baseline) * baseline
                # print(f"[debug] event_id={event_id}, peak {i}: left_base={left_base}, right_base={right_base}, filtered_before={filtered[i]}")

                # Type 0: both bases are below the lower carrier threshold.
                if left_base <= type0_thresh and right_base <= type0_thresh :
                    filtered[i] = 0
                # Type -1: both bases above the upper type-2 cutoff (noise)
                elif left_base >= type2_thresh + unfolded_level and right_base >= type2_thresh + unfolded_level:
                    filtered[i] = -1
                #    print(f"[debug] event_id={event_id}, peak {i} assigned -1 (both bases >= type2_upper)")
                # Type 2: both bases within the type-2 band around 2*unfolded_level
                elif left_base >= type2_thresh and right_base >= type2_thresh and left_base <= type2_thresh + unfolded_level and right_base <=  type2_thresh + unfolded_level:
                    filtered[i] = 2
                #    print(f"[debug] event_id={event_id}, peak {i} assigned 2 (both bases in type2 band)")
                # Type 1: both bases within the type-1 band around unfolded_level
                elif left_base >= type1_thresh and right_base >= type1_thresh and left_base <= type2_thresh and right_base <= type2_thresh:
                    filtered[i] = 1
                    # print(f"[debug] event_id={event_id}, peak {i} assigned 1 (both bases in type1 band)")
                else:
                    filtered[i] = -1
                    # print(f"[debug] event_id={event_id}, peak {i} assigned -1 (does not meet type1 or type2 criteria, bases missmatch)")
                # if filtered[i] not in [1, 2, -1]:
                #    print(f"Unlabeled peak {i}: left={left_base:.3f}, right={right_base:.3f}, unfolded_level-2std={unfolded_level - 2 * baseline_std:.3f}, 2*unfolded_level+std={2*unfolded_level+baseline_std:.3f}")

            # Step 2: Identify clusters of same-type peaks, but keep only the most prominent one
            # Calculate max_distance as percentage of event length
            max_distance_percentage = self.settings.get(
                "Peak to Peak Distance Ratio", {}
            ).get("Value", 10.0)
            event_length_samples = (
                event_length * samplerate * 1e-6
            )  # Convert us to samples
            max_distance = int((max_distance_percentage / 100.0) * event_length_samples)
            self.logger.debug(
                f"filter_peaks: event_length={event_length:.1f} us, "
                f"event_length_samples={event_length_samples:.1f}, "
                f"max_distance_percentage={max_distance_percentage}%, "
                f"max_distance={max_distance} samples"
            )
            min_group_size = num_peaks

            best_cluster = []
            best_prom_sum = 0

            for label in [1]:
                label_idxs = [i for i in prom_indices if filtered[i] == label]
                if not label_idxs:
                    continue

                label_idxs = label_idxs[:num_peaks]
                sorted_idxs = sorted(label_idxs, key=lambda i: peaks[i])

                # Find clusters where consecutive peaks are within max_distance
                for i in range(len(sorted_idxs)):
                    group = [sorted_idxs[i]]

                    # Add consecutive peaks that are close enough
                    for j in range(i + 1, len(sorted_idxs)):
                        # Check distance between consecutive peaks in the group
                        prev_peak_idx = group[-1]
                        curr_peak_idx = sorted_idxs[j]
                        distance = abs(peaks[curr_peak_idx] - peaks[prev_peak_idx])

                        if distance <= max_distance:
                            group.append(curr_peak_idx)
                        else:
                            # Stop when we find a gap larger than max_distance
                            break

                    # Check if this group is large enough and has higher total prominence
                    if len(group) >= min_group_size:
                        prom_sum = sum(properties["prominences"][idx] for idx in group)
                        
                        if prom_sum > best_prom_sum:
                            best_cluster = group
                            best_prom_sum = prom_sum
                        break  # only use first valid cluster per label

                # Relabel best cluster as Type 3
                for idx in best_cluster:
                    filtered[idx] = 3


            # Persist filtered labels back to properties
            properties["filtered"] = list(filtered.tolist())

        # SINGLE PEAK CARRIER
        if self.settings["Event Type"]["Value"] == "Single Peak":
            
            unfolded_lower_bound = (
                (unfolded_level + t1_std * baseline_std) if unfolded_level is not None else 0
            )
            unfolded_upper_bound = (
                (unfolded_level + t2_std * baseline_std) if unfolded_level is not None else 0
            )

            folded_lower_bound = (
                (folded_level - t1_std * baseline_std) if folded_level is not None else 0
            )
            folded_upper_bound = (
                (folded_level + t2_std * baseline_std) if folded_level is not None else 0
            )

            classified_peaks = []
            for i in range(len(peaks)):
                left_base = properties["left_bases"][i]+ np.sign(baseline) * baseline
                right_base = properties["right_bases"][i]+ np.sign(baseline) * baseline
                prom = properties["prominences"][i]
                height = properties["peak_heights"][i]

                # Classify peak type based on base levels - ordered from most specific to most general
                if right_base >= folded_upper_bound and left_base >= folded_upper_bound:
                    filtered[i] = -1  # Reject peaks that are too high
                elif (
                    right_base >= unfolded_lower_bound
                    and right_base <= unfolded_upper_bound
                    and left_base >= folded_lower_bound
                    and left_base <= folded_upper_bound
                    and height >= folded_upper_bound
                ):
                    filtered[i] = (
                        12  # Type 1P - Most specific case with height requirement
                    )
                elif (
                    right_base >= unfolded_lower_bound
                    and right_base <= unfolded_upper_bound
                    and left_base <= unfolded_lower_bound
                ):
                    filtered[i] = 11  # Type 1U - Clear unfolding transition
                elif (
                    left_base >= folded_lower_bound
                    and left_base <= folded_upper_bound
                    and right_base <= unfolded_lower_bound
                ):
                    filtered[i] = 13  # Type 1/2F - Specific folding transition
                elif (
                    left_base >= unfolded_lower_bound
                    and left_base <= unfolded_upper_bound
                    and right_base <= unfolded_lower_bound
                ):
                    filtered[i] = 21  # Type 2U or 2P - Unfolding/Peak from higher level
                elif (
                    left_base >= unfolded_upper_bound
                    and right_base <= unfolded_lower_bound
                ):
                    filtered[i] = 22  # Type 2P or 1/2F - Most general case
                else:
                    filtered[i] = -1
                    continue

                classified_peaks.append((i, prom))

            # Step 2: Keep only the most prominent valid classified peak at the end
            if classified_peaks:
                # Sort by: prominence (descending) then index (descending)
                classified_peaks.sort(key=lambda x: (-x[1], -x[0]))
                best_idx = classified_peaks[0][0]

                # Set all other peaks to -1
                for i in range(len(peaks)):
                    if i != best_idx:
                        filtered[i] = -1

        # MISC
        if self.settings["Event Type"]["Value"] == "Unspecified":
            pass  # fill out as needed

        # Debug log the classification results
        filtered_counts = {}
        for f in filtered:
            filtered_counts[f] = filtered_counts.get(f, 0) + 1
        self.logger.debug(
            f"filter_peaks: Event Type={self.settings['Event Type']['Value']}, classified {len(peaks)} peaks: {filtered_counts}"
        )

        return properties
    
    # utility functions

    @log(logger=logger)
    def find_mode_blockage_level(self, data, baseline_mean, baseline_std):
        """
        Extract the most populated blockage level from the data.

        Uses numpy histogram to find the most common current level.
        Data should already be trimmed to the longest continuous segment above threshold
        by _locate_sublevel_transitions. Folded/unfolded classification is deferred
        to post-processing across all events.

        :param data: Array of current values (already trimmed to longest segment).
        :type data: numpy.ndarray
        :param baseline_mean: Mean value of the baseline level.
        :type baseline_mean: float
        :param baseline_std: Standard deviation of the baseline level.
        :type baseline_std: float
        :return: Tuple of (primary_blockage_level, secondary_blockage_level) - the 2 most populated distinct blockage levels
        :rtype: Tuple[Optional[float], Optional[float]]
        """
        # Data is already trimmed to longest segment in _locate_sublevel_transitions
        # Find the 2 most populated levels using histogram

        # Fast histogram-based level detection using numpy
        # Create bins with baseline_std/8 spacing for precise level detection
        bin_width = baseline_std / 8
        min_val = np.min(data)
        max_val = np.max(data)
        bins = np.arange(min_val - bin_width / 2, max_val + bin_width, bin_width)

        # Get histogram counts and bin centers
        counts, bin_edges = np.histogram(data, bins=bins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        # Find the 2 bins with maximum counts
        top_2_indices = np.argsort(counts)[-2:][::-1]  # Sort descending, take top 2

        primary_level = np.abs(bin_centers[top_2_indices[0]] - baseline_mean)
        secondary_level = (
            np.abs(bin_centers[top_2_indices[1]] - baseline_mean)
            if len(top_2_indices) > 1 and counts[top_2_indices[1]] > 0
            else None
        )

        return primary_level, secondary_level


    @log(logger=logger)
    def enumerate_peaks(
        self, sublevel_starts: list[dict], num_states: int, sublevel_types: Optional[list[str]] = None
    ) -> List[Optional[int]]:
        """
        :param sublevel_starts: List of dictionaries describing sublevels, each with a 'type' key.
        :type sublevel_starts: list[dict]
        :param num_states: Total number of sublevels to process.
        :type num_states: int
        :param sublevel_types: List of sublevel types ('peak' or 'event_baseline'). If None, falls back to edge type checking.
        :type sublevel_types: Optional[list[str]]
        :return: List of peak IDs or None for non-peak sublevels.
        :rtype: list[Optional[int]]
        """
        j = 1
        id: List[Optional[int]] = []
        for i in range(num_states):
            # Check sublevel_type if provided, otherwise fall back to edge type checking
            is_peak = False
            if sublevel_types is not None:
                is_peak = sublevel_types[i] == "peak"
            else:
                is_peak = "peak" in sublevel_starts[i]["type"]

            if is_peak:
                id.append(j)
                j += 1
            else:
                id.append(None)
        return id
