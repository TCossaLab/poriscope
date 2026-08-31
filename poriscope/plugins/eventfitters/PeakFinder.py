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
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast, override

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from scipy.interpolate import BSpline, make_smoothing_spline
from scipy.signal import find_peaks, peak_widths
from scipy.stats import iqr
from sklearn.mixture import GaussianMixture

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

    #: Minimum number of histogram bins built for threshold fitting. The EM fit
    #: itself sees every unbinned sample, but the histogram still sets the
    #: variance floor, the collapsed-component test, and the smoothing-spline
    #: threshold search, all of which need meaningfully more than a handful of
    #: bins to be well-behaved; see ``_histogram_for_fit`` for the measurements
    #: behind this floor.
    MIN_FIT_BINS = 30

    #: Minimum separation, in units of the narrower component's FWHM, that two
    #: fitted centres must have before they are treated as two populations
    #: rather than one mode fitted twice. See ``_fit_em_double_gaussian`` for
    #: where this decides ``one_population``.
    SEED_SEPARATION_FWHM = 1.0

    #: Number of independent EM restarts. EM is a local method, so a single
    #: start can settle on a poor optimum; ten was enough for bit-identical
    #: parameters across repeated runs on every dataset tested.
    EM_N_INIT = 10

    #: Fixed seed for EM initialization. EM's k-means init is randomized, and an
    #: unseeded fit would make thresholds - and therefore classifications and
    #: sequences - differ between runs on identical data.
    EM_RANDOM_STATE = 0

    #: Degrees of freedom for the Student-t components fitted by
    #: ``_fit_student_t_mixture``. Lower is more robust (nu -> 1 is Cauchy); as
    #: nu grows the t tends to a Gaussian and the robustness weights tend to 1.
    #: Four is the conventional choice for heavy-tailed-but-not-pathological
    #: data and is held fixed rather than estimated: estimating nu adds a
    #: parameter that the minority population cannot constrain, which is the
    #: very problem the Student-t model exists to fix.
    T_DOF = 4.0

    #: Convergence tolerance and iteration cap for the Student-t EM loop, on the
    #: same footing as sklearn's own defaults.
    T_TOL = 1e-6
    T_MAX_ITER = 500

    #: Largest number of local minima the smoothing spline may have inside the
    #: bracket the threshold search will run over. One is the target: a single
    #: real valley between two populations. See ``_fit_least_smoothed_spline``.
    SPLINE_MAX_MINIMA = 1

    #: Bounds and resolution of the smoothing-spline lambda ladder, in units of
    #: the scale-free shape parameter (the lambda actually handed to
    #: ``make_smoothing_spline`` is this times the histogram's x-range cubed).
    #: See ``_fit_least_smoothed_spline``.
    SPLINE_LAMBDA_SHAPE_MIN = 1e-12
    SPLINE_LAMBDA_SHAPE_MAX = 1e2
    SPLINE_LAMBDA_CANDIDATES = 50

    #: Extra ladder steps to take past the first acceptable lambda. Kept at
    #: zero deliberately: over 24 skewed datasets, two margin steps drove the
    #: higher component's mode bias from +22 pA to +685 pA, mean classification
    #: accuracy from 0.8717 to 0.8449, and made 5 of the 24 fits fail outright,
    #: because the extra smoothing washes out the very valley the ladder had
    #: just resolved. One step past "quiet enough" is already past "still shows
    #: the real valley".
    SPLINE_LAMBDA_MARGIN_STEPS = 0

    #: Fraction of a histogram's total count that the smoothing-spline
    #: machinery is fit and drawn over, trimmed symmetrically from each edge.
    #: See ``_trim_to_populated_core`` for why the untrimmed full range is not
    #: safe to fit a single spline across.
    SPLINE_FIT_DOMAIN_COVERAGE = 0.995

    # public API, must be overridden by subclasses:
    @log(logger=logger)
    @override
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
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

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
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
        settings["Lower Filter Threshold"] = {
            "Type": int,
            "Value": -4,
            "Min": -10,
            "Max": 10,
            "Units": "σ",
        }
        settings["Higher Filter Threshold"] = {
            "Type": int,
            "Value": 2,
            "Min": -10,
            "Max": 10,
            "Units": "σ",
        }
        settings["Peak to Peak Distance Ratio"] = {
            "Type": float,
            "Value": 5.0,  # Default to 10% of event length
            "Min": 0.01,
            "Max": 99,  # Maximum 99% of event
            "Units": "%",
        }
        settings["Window Length Percentage"] = {
            "Type": float,
            "Value": 10.0,  # Default to 10% of event length
            "Min": 0.01,
            "Max": 99,  # Maximum 99% of event
            "Units": "%",
        }
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
        return settings

    @log(logger=logger)
    @override
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit
        """

    @log(logger=logger)
    @override
    def construct_fitted_event(
        self, channel: int, index: int
    ) -> Optional[npt.NDArray[np.float64]]:
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
        :rtype: Tuple[Optional[List[float]], Optional[List[float]], Optional[List[Tuple[float, float]]], Optional[List[str]], Optional[List[str]], Optional[List[str]]]

        """

        if self.sublevel_metadata == {} or not self.eventfitting_status.get(channel):
            self.logger.info(
                f"Peak finding is not complete in channel {channel}, find peaks first"
            )
            return None, None, None, None, None, None
        try:
            baseline = self.event_metadata[channel][index]["baseline_current"]
            baseline_stdev = self.event_metadata[channel][index]["baseline_stdev"]
            t1_std = int(self.settings["Lower Filter Threshold"]["Value"])
            t2_std = int(self.settings["Higher Filter Threshold"]["Value"])
            # Initializing arrays
            bases: list[float] = []
            peaks: list[tuple[float, float]] = []
            # ips: list[float] = []
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
                - np.sign(baseline) * t2_std * baseline_stdev
            )
            hlabel.append(f"unfolded level {t2_std:+d}σ")
            bases.append(
                -np.sign(baseline)
                * self.event_metadata[channel][index]["unfolded_level"]
                + self.event_metadata[channel][index]["baseline_current"]
                - np.sign(baseline) * t1_std * baseline_stdev
            )
            hlabel.append(f"unfolded level {t1_std:+d}σ")

            if self.event_metadata[channel][index]["sequence"] is not None:
                translocation_confidence = self.event_metadata[channel][index].get(
                    "translocation_confidence"
                )
                confidence_label = (
                    "nan"
                    if translocation_confidence is None
                    else str(round(translocation_confidence, 3))
                )
                if (
                    self.event_metadata[channel][index]["translocation_direction"]
                    == "forward"
                ):
                    peaks_filtered.append(
                        self.sublevel_metadata[channel][index]["sublevel_start_times"][
                            1
                        ]
                    )
                    vlabel.append(
                        f"Forward translocation.\n Sequence: {self.event_metadata[channel][index]['sequence']} Confidence: {confidence_label}"
                    )
                elif (
                    self.event_metadata[channel][index]["translocation_direction"]
                    == "backward"
                ):
                    peaks_filtered.append(
                        self.sublevel_metadata[channel][index]["sublevel_start_times"][
                            -1
                        ]
                    )
                    vlabel.append(
                        f"Backward translocation.\n Sequence: {self.event_metadata[channel][index]['sequence']} Confidence: {confidence_label}"
                    )

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
                        + " Confidence: "
                        + str(
                            round(
                                self.sublevel_metadata[channel][index][
                                    "classification_confidence"
                                ][i],
                                3,
                            )
                        )
                    )

                    j += 1

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

    @log(logger=logger)
    def redefine_padding(
        self,
        data: npt.NDArray[np.float64],
        samplerate: float,
        baseline_std: Optional[float],
    ) -> npt.NDArray[np.float64]:
        """
        Locate sublevel edges within an event using a CUSUM change-point detector.

        Used to re-derive the padding boundaries of an event rather than trusting the
        values supplied by the event loader.

        :param data: an array of data from which to locate sublevel edges
        :type data: npt.NDArray[np.float64]
        :param samplerate: the sampling rate
        :type samplerate: float
        :param baseline_std: the local standard deviation of the baseline current
        :type baseline_std: Optional[float]
        :return: the located edge positions, beginning at 0 and ending at len(data)
        :rtype: npt.NDArray[np.float64]
        :raises RuntimeError: if baseline_std is None, since it sets the CUSUM step size
        """
        # NOTE (integration): this method had no docstring at all, which is what
        # test_plugin_compliance.py was reporting as
        # "missing docstrings: ['filter_peaks', 'redefine_padding']". Added one
        # describing the existing behaviour.
        # NOTE (integration): baseline_std is Optional under the MetaEventFitter
        # contract but was used unguarded below, so an event loader supplying no
        # baseline estimate produced a TypeError from the division. Checked and raised
        # explicitly instead. The method has no live caller today - its only call site
        # is commented out - so this path was latent.
        if baseline_std is None:
            raise RuntimeError(
                "redefine_padding requires a baseline standard deviation to set its "
                "CUSUM step size; the event loader supplied None"
            )
        step_size = self.settings["Min Carrier Blockage"]["Value"] / (2 * baseline_std)
        rise_time = int(1.0e-6 * samplerate)
        length = len(data)

        retry = True
        while retry:
            retry = False
            logp = 0  # instantaneous log-likelihood for positive jumps
            logn = 0  # instantaneous log-likelihood for negative jumps
            cpos = np.zeros(
                length, dtype=np.float64
            )  # cumulative log-likelihood function for positive jumps
            cneg = np.zeros(
                length, dtype=np.float64
            )  # cumulative log-likelihood function for negative jumps
            gpos = np.zeros(
                length, dtype=np.float64
            )  # decision function for positive jumps
            gneg = np.zeros(
                length, dtype=np.float64
            )  # decision function for negative jumps

            # set up running mean and variance calculation
            mean = data[0]
            # NOTE: baseline_std is Optional under the MetaEventFitter contract and is used here without a guard. Flagged, not fixed - the logic in this plugin belongs to its owner.
            variance = baseline_std * baseline_std
            num_states = 0
            varM = data[0]
            varS = 0
            mean = data[0]

            threshold = step_size
            edges = [0]  # first sublevel starts at the start of the data block

            k = 0  # current data point index
            anchor = 0  # the last detected change
            num_states = 0

            while k < length - 1:
                k += 1
                varOldM = varM  # algorithm to calculate running variance, details here: http://www.johndcook.com/blog/standard_deviation/
                varM = varM + (data[k] - varM) / float(k + 1 - anchor)
                varS = varS + (data[k] - varOldM) * (data[k] - varM)
                variance = varS / float(k - anchor)
                mean = ((k - anchor) * mean + data[k]) / float(k + 1 - anchor)
                if (
                    variance == 0
                ):  # with low-precision data sets it is possible that two adjacent values are equal, in which case there is zero variance for the two-vector of sample if this occurs next to a detected jump. This is very, very rare, but it does happen.
                    variance = (
                        baseline_std * baseline_std
                    )  # in that case, we default to the local baseline variance, which is a good an estimate as any.
                logp = (
                    step_size
                    * baseline_std
                    / variance
                    * (data[k] - mean - step_size * baseline_std / 2)
                )  # instantaneous log-likelihood for current sample assuming local baseline has jumped in the positive direction
                logn = (
                    -step_size
                    * baseline_std
                    / variance
                    * (data[k] - mean + step_size * baseline_std / 2)
                )  # instantaneous log-likelihood for current sample assuming local baseline has jumped in the negative direction
                cpos[k] = cpos[k - 1] + logp  # accumulate positive log-likelihoods
                cneg[k] = cneg[k - 1] + logn  # accumulate negative log-likelihoods
                gpos[k] = max(
                    gpos[k - 1] + logp, 0
                )  # accumulate or reset positive decision function
                gneg[k] = max(
                    gneg[k - 1] + logn, 0
                )  # accumulate or reset negative decision function
                if gpos[k] > threshold or gneg[k] > threshold:
                    jump_accepted = False

                    if gpos[k] > threshold:  # significant positive jump detected
                        jump = 1 + anchor + np.argmin(cpos[anchor : k + 1])
                        # Note: C also checks `length - jump > rise_time` here,
                        # you may want to add that to match C perfectly!
                        if jump - edges[num_states] > rise_time:
                            edges = np.append(edges, jump)
                            num_states += 1
                            jump_accepted = True

                    if gneg[k] > threshold:  # significant negative jump detected
                        jump = 1 + anchor + np.argmin(cneg[anchor : k + 1])
                        if jump - edges[num_states] > rise_time:
                            edges = np.append(edges, jump)
                            num_states += 1
                            jump_accepted = True

                    if jump_accepted:
                        anchor = k
                        cpos[0 : len(cpos)] = 0
                        cneg[0 : len(cneg)] = 0
                        gpos[0 : len(gpos)] = 0
                        gneg[0 : len(gneg)] = 0
                        mean = data[anchor]
                        varM = data[anchor]
            varS = 0
            edges = np.append(edges, length)  # mark the end of the event as an edge
            num_states += 1

            # iteratively remove steps that are too small, from left to right
            minstepflag = False
            while not minstepflag:
                minstepflag = True
                sublevel_means = [
                    (
                        np.median(data[int(edges[i] + rise_time) : int(edges[i + 1])])
                        if edges[i] + rise_time < edges[i + 1]
                        else data[int(edges[i + 1]) - 1]
                    )
                    for i in range(num_states)
                ]

                toosmall = (
                    np.absolute(np.diff(sublevel_means)) < step_size * baseline_std / 2
                )
                for i in range(len(toosmall)):
                    if toosmall[i]:
                        edges = np.delete(edges, i + 1)
                        minstepflag = False
                        num_states -= 1
                        break

        return edges

    @log(logger=logger)
    @override
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
        :rtype: Optional[List[Any]]

        :raises ValueError: if the event is rejected. Note that ValueError will skip and reject the event but will not stop processing of the rest of the dataset
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

        if padding_before is not None:
            baseline_std = np.std(data[:padding_before])
            baseline_mean = np.mean(data[:padding_before])
        elif padding_after is not None:
            baseline_std = np.std(data[-padding_after:])
            baseline_mean = np.mean(data[-padding_after:])
        else:
            raise ValueError(
                "PeakFinder requires that the standard deviation and mean of the local baseline be reported and is unable to calculate it for this event"
            )

        # edges=self.redefine_padding(data, samplerate, baseline_std)
        # cusum_padding_before = edges[1]
        # cusum_padding_after = len(data) - edges[-2]
        # print("Finding padding")
        # print(cusum_padding_before, cusum_padding_after)

        if (
            padding_before is None
            or padding_after is None
            or len(data) == padding_before
            or len(data) == padding_after
        ):
            raise ValueError("No data available for peak detection")

        # Find longest continuous segment above threshold
        # This trims the event to start/end at the longest above-threshold blockage

        threshold = min(abs(low_threshold), abs(high_threshold), 3) * baseline_std
        event_data = data[padding_before:-padding_after]
        above_threshold = (
            np.abs(np.abs(event_data) - np.sign(baseline_mean) * baseline_mean)
            > threshold
        )

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
        min_segment_length = 100
        if longest_segment_length < min_segment_length:
            raise ValueError(
                "No segment above threshold meets minimum length requirement"
            )

        # Get the start and end indices of the longest segment (relative to event_data)
        longest_start_idx = segment_starts[longest_segment_idx]
        longest_end_idx = segment_ends[longest_segment_idx]

        # Adjust padding to trim to the longest segment only
        # New effective padding_before includes original padding plus everything before longest segment
        new_padding_before = padding_before + longest_start_idx
        # New effective padding_after includes original padding plus everything after longest segment
        new_padding_after = padding_after + (len(event_data) - longest_end_idx)

        # Use adjusted paddin gs for the rest of processing
        padding_before = new_padding_before
        padding_after = new_padding_after
        # print(padding_before, padding_after)

        # Method 2: Signal-based minimum (relative to carrier blockage depth)
        # Calculate the carrier level blockage (median of the trimmed event)
        trimmed_data = data[padding_before:-padding_after]
        carrier_blockage, _ = self.find_mode_blockage_level(
            trimmed_data, baseline_mean, baseline_std
        )
        min_segment_length = 100

        # as long as at least one segment exists above threshold
        if len(trimmed_data) < min_segment_length:
            raise ValueError("Too short of a segment above threshold to analyze")
        if carrier_blockage < self.settings["Min Carrier Blockage"]["Value"]:
            raise ValueError("No Carrier Level Found")

        # Calculate minimum prominence and height from the user thresholds.
        # Keep the carrier-aware guardrails so peaks still scale with signal depth.
        min_prom_noise = max(abs(low_threshold), abs(high_threshold)) * baseline_std

        # Peaks should still be significant relative to the translocation signal
        min_prom_signal = carrier_blockage
        # Use the more stringent of the two criteria
        min_prom = max(min_prom_noise, min_prom_signal)
        # Height is driven by the higher threshold setting, then guarded by the
        # carrier level so peaks still sit beyond the local blockage.
        min_height = max(
            max(abs(low_threshold), abs(high_threshold)) * baseline_std,
            carrier_blockage + min_prom,
        )

        # Calculate wlen (prominence window) for finding peak bases
        # wlen is calculated as a user-specified percentage of the trimmed event length
        # This provides a simple, predictable, and user-controllable approach
        #
        # User Setting: Window Length Percentage determines wlen as % of event
        # - Default: 2.2% of event (based on original 160/7249 ratio)
        # - Range: 0.1% to 33.3% (maximum 1/3 of event)
        # - Automatically scales with event duration

        trimmed_event_length = len(trimmed_data)  # Length in samples

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
                max_blockage, _ = self.find_mode_blockage_level(
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
                        "left_base": np.sign(baseline_mean)
                        * (baseline_mean - properties["left_bases"][i]),
                        "right_base": np.sign(baseline_mean)
                        * (baseline_mean - properties["right_bases"][i]),
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
        self,
        data: npt.NDArray[np.float64],
        samplerate: float,
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
        sublevel_starts: List[Any],
    ) -> Dict[str, npt.NDArray[Numeric]]:
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
        :type sublevel_starts: List[Any]

        :return: a dict of lists of sublevel metadata values, one list entry per sublevel for each piece of metadata
        :rtype: Dict[str, npt.NDArray[Numeric]]
        """
        sublevel_metadata: Dict[str, Any] = {}

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
            [(np.nan) for i in range(num_states)],
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
            [(np.nan) for i in range(num_states)],
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
            [(np.nan) for i in range(num_states)],
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
            [(np.nan) for i in range(num_states)],
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
                (np.nan if "peak" in sublevel_starts[i]["type"] else np.nan)
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # confidence in the above classification (will be assigned alongside
        # "classified" in post-processing; see _classification_confidence)
        sublevel_metadata["classification_confidence"] = np.array(
            [
                (np.nan if "peak" in sublevel_starts[i]["type"] else np.nan)
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # get the standard deviation over the sublevel, ignoring the rise time
        sublevel_metadata["sublevel_stdev"] = np.array(
            [
                (
                    np.std(
                        data[
                            int(sublevel_starts[i]["index"]) : int(
                                sublevel_starts[i + 1]["index"]
                            )
                        ]
                    )
                    if sublevel_starts[i]["index"] < sublevel_starts[i + 1]["index"]
                    else np.std(
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

        return sublevel_metadata

    @log(logger=logger)
    @override
    def _populate_event_metadata(
        self,
        data: npt.NDArray[np.float64],
        samplerate: float,
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
        sublevel_metadata: Dict[str, List[Numeric]],
    ) -> Dict[str, Union[int, float, str, bool]]:
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
        :rtype: Dict[str, Union[int, float, str, bool]]
        :raises RuntimeError: if the baseline current or standard deviation is non-numeric, or if no primary blockage level can be determined
        """
        event_metadata: Dict[str, Union[int, float, str, bool]] = {}

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

        event_metadata["baseline_current"] = (
            sublevel_metadata["sublevel_current"][0]
            * sublevel_metadata["sublevel_duration"][0]
            + sublevel_metadata["sublevel_current"][-1]
            * sublevel_metadata["sublevel_duration"][-1]
        ) / (
            sublevel_metadata["sublevel_duration"][0]
            + sublevel_metadata["sublevel_duration"][-1]
        )

        event_metadata["baseline_stdev"] = min(
            (
                sublevel_metadata["sublevel_stdev"][0]
                * sublevel_metadata["sublevel_duration"][0]
                + sublevel_metadata["sublevel_stdev"][-1]
                * sublevel_metadata["sublevel_duration"][-1]
            )
            / (
                sublevel_metadata["sublevel_duration"][0]
                + sublevel_metadata["sublevel_duration"][-1]
            ),
            sublevel_metadata["sublevel_stdev"][0],
            sublevel_metadata["sublevel_stdev"][-1],
        )

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
        # NOTE (integration): these two came out of the metadata dict, whose value type
        # the base contract declares Union[int, float, str, bool] - wider than the
        # Optional[float] find_mode_blockage_level accepts - and were previously passed
        # straight through. Narrowed explicitly, so a metadata dict holding a string or
        # a bool in either slot is reported rather than silently mis-fitted.
        baseline_current = event_metadata["baseline_current"]
        baseline_stdev = event_metadata["baseline_stdev"]
        if isinstance(baseline_current, bool) or not isinstance(
            baseline_current, (int, float)
        ):
            raise RuntimeError(
                f"event metadata 'baseline_current' must be numeric, got "
                f"{type(baseline_current).__name__}"
            )
        if isinstance(baseline_stdev, bool) or not isinstance(
            baseline_stdev, (int, float)
        ):
            raise RuntimeError(
                f"event metadata 'baseline_stdev' must be numeric, got "
                f"{type(baseline_stdev).__name__}"
            )

        primary_level, _ = self.find_mode_blockage_level(
            data[
                int(
                    sublevel_metadata["sublevel_start_times"][1] * samplerate * 1e-6
                ) : int(
                    sublevel_metadata["sublevel_start_times"][-1] * samplerate * 1e-6
                )
            ],
            float(baseline_current),
            float(baseline_stdev),
        )
        if primary_level is None:
            raise RuntimeError(
                "find_mode_blockage_level could not determine a primary blockage "
                "level for this event"
            )
        event_metadata["primary_level"] = primary_level
        # Leave unfolded_level and folded_level as None - will be determined in post-processing
        event_metadata["unfolded_level"] = None  # type: ignore[assignment]
        event_metadata["folded_level"] = None  # type: ignore[assignment]
        event_metadata["translocation_direction"] = None  # type: ignore[assignment]
        event_metadata["translocation_confidence"] = None  # type: ignore[assignment]
        event_metadata["sequence"] = None  # type: ignore[assignment]

        return event_metadata

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        """

    @log(logger=logger)
    @override
    def _define_event_metadata_types(
        self,
    ) -> Dict[str, Type[Union[int, float, str, bool]]]:
        """
        Build a dict of metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Type[Union[int, float, str, bool]]]
        """
        metadata_types: Dict[str, Type[Union[int, float, str, bool]]] = {
            "number_peaks": int,
            "duration": float,
            "raw_ecd": float,
            "max_deviation": float,
            "baseline_current": float,
            "unfolded_level": float,
            "folded_level": float,
            "primary_level": float,
            "baseline_stdev": float,
            "translocation_direction": str,
            "translocation_confidence": float,
            "sequence": str,
        }

        return metadata_types

    @log(logger=logger)
    @override
    def _define_sublevel_metadata_types(
        self,
    ) -> Dict[str, Type[Union[int, float, str, bool]]]:
        """
        Build a dict of sublevel metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_sublevel_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool. Note that this is the type of entries in the associated list,
        it should not include the list element

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Type[Union[int, float, str, bool]]]
        """
        metadata_types: Dict[str, Type[Union[int, float, str, bool]]] = {
            "sublevel_current": float,
            "sublevel_stdev": float,
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
            "classification_confidence": float,
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
    def _define_event_metadata_units(self) -> Dict[str, Optional[str]]:
        """
        Build a dict of metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Optional[str]]
        """
        metadata_units: Dict[str, Optional[str]] = {}

        metadata_units["number_peaks"] = None
        metadata_units["duration"] = "μs"
        metadata_units["raw_ecd"] = "pC"
        metadata_units["max_deviation"] = "pA"
        metadata_units["baseline_current"] = "pA"
        metadata_units["unfolded_level"] = "pA"
        metadata_units["folded_level"] = "pA"
        metadata_units["primary_level"] = "pA"
        metadata_units["baseline_stdev"] = "pA"
        metadata_units["translocation_direction"] = None
        metadata_units["translocation_confidence"] = None
        metadata_units["sequence"] = None

        return metadata_units

    @log(logger=logger)
    @override
    def _define_sublevel_metadata_units(self) -> Dict[str, Optional[str]]:
        """
        Build a dict of sublevel metadata units , or None if unitless. Keys must match columns defined in _populate_sublevel_metadata()
        All of this metadata must be populated during fitting.
        it should not include the list element

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Optional[str]]
        """
        metadata_units: Dict[str, Optional[str]] = {}

        metadata_units["sublevel_current"] = "pA"
        metadata_units["sublevel_stdev"] = "pA"
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
        metadata_units["classification_confidence"] = None
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
        all_longest_levels: list[float] = []
        all_event_info: list[tuple[int, int]] = (
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

        self.logger.info(
            f"Collected {len(all_longest_levels)} events for classification analysis"
        )

        self._classify_folded_unfolded(
            channels=channels,
            all_event_info=all_event_info,
            all_longest_levels_array=all_longest_levels_array,
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
                filtered_values = np.asarray(
                    sublevel_data.get("filtered", []), dtype=float
                )
                classified = sublevel_data.get("classified", [])
                sequence = "".join(
                    str(int(classified[i]))
                    for i in range(len(filtered_values))
                    if not np.isnan(filtered_values[i])
                    and int(filtered_values[i]) == 3
                    and i < len(classified)
                    and not (
                        isinstance(classified[i], float) and np.isnan(classified[i])
                    )
                )
                if ch in self.event_metadata and event_index in self.event_metadata[ch]:
                    direction = self.event_metadata[ch][event_index].get(
                        "translocation_direction", None
                    )
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
    ) -> None:
        """
        Update event metadata after post-processing analysis with proper folded/unfolded classification.
        This function should be called after global analysis determines the correct unfolded and folded levels.
        Also reclassifies peaks using the accurate global folded/unfolded levels.

        :param channel: Channel number
        :type channel: int
        :param event_index: Event index within the channel
        :type event_index: int
        :param unfolded_level: Determined unfolded level for normalization
        :type unfolded_level: Optional[float]
        :param folded_level: Determined folded level for classification
        :type folded_level: Optional[float]
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
        event_data = self.event_metadata[channel][event_index]

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
                normalized_prominences[valid_mask] = (
                    prominences[valid_mask] / unfolded_level
                )
                sublevel_data["normalized_prominence"] = normalized_prominences

            if (
                "max_blockage" in sublevel_data
                and sublevel_data["max_blockage"] is not None
            ):
                blockages = np.array(sublevel_data["max_blockage"])
                valid_mask = ~np.isnan(blockages)
                normalized_blockages = np.full_like(blockages, np.nan)
                normalized_blockages[valid_mask] = (
                    blockages[valid_mask] / unfolded_level
                )
                sublevel_data["normalized_blockage"] = normalized_blockages

        # Reclassify peaks using global folded/unfolded levels
        if unfolded_level is not None and folded_level is not None:
            # Get baseline and samplerate for this event
            baseline_mean = event_data.get("baseline_current")
            baseline_stdev = self.event_metadata[channel][event_index].get(
                "baseline_stdev"
            )

            if baseline_mean is not None and baseline_stdev is not None:
                # Get event loader to retrieve samplerate
                if self.eventloader is None:
                    self.logger.warning(
                        "Event loader is not set; cannot reclassify peaks"
                    )
                    return

                samplerate = self.eventloader.get_samplerate(channel)

                # Extract peak information from sublevel_metadata
                peak_indices: list[int] = []
                properties: dict[str, list[float | int]] = {
                    "left_bases": [],
                    "right_bases": [],
                    "prominences": [],
                    "peak_heights": [],
                    "filtered": [],
                    "peak_loc": [],
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
                        properties["peak_loc"].append(sublevel_data["peak_loc"][i])

                if len(peak_indices) > 0:
                    # Create dummy peaks array (just indices for compatibility)
                    peaks = np.array(peak_indices)

                    # Calculate total event length from sublevel durations
                    event_length = np.sum(event_data.get("duration", []))

                    # Call filter_peaks with global levels
                    updated_properties = self.filter_peaks(
                        peaks,
                        properties,
                        unfolded_level,
                        folded_level,
                        baseline_stdev,
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
    def report_channel_status(
        self, channel: Optional[int] = None, init: bool = False
    ) -> str:
        """
        Return a string detailing fitting and classification status.

        :param channel: the channel to report on, or None for all channels
        :type channel: Optional[int]
        :param init: whether this is an initialization report
        :type init: bool
        :return: the status report as a string
        :rtype: str
        :raises RuntimeError: if the channel's peak statistics cannot be assembled
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
            if (
                self._classification_results
                and "error" not in self._classification_results
            ):
                loader = getattr(self, "eventloader", None)
                if loader is None:
                    raise RuntimeError(
                        "Event loader is not initialized; cannot determine total events"
                    )

        # Add classification information to the report
        classification_report = (
            "\n\nClassification Results:\n\nFolding Classification Results:"
        )

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
                    f"Unable to collect peak statistics for report: {e!s}"
                )

        if hasattr(self, "_peak_statistics"):
            peak_stats = self._peak_statistics
            classification_report += "\n\nPeak Filtering Statistics:"

            # Cast values to proper types for type checking
            total_peaks = cast(int, peak_stats["total_peaks"])
            total_classified = cast(int, peak_stats["total_classified"])
            total_unclassified = cast(int, peak_stats["total_unclassified"])
            peak_type_counts = cast(dict[int, int], peak_stats["peak_type_counts"])
            if total_peaks > 0:
                classified_pct = total_classified / total_peaks * 100
                unclassified_pct = total_unclassified / total_peaks * 100

            classification_report += f"\n  Total peaks detected: {total_peaks}"
            classification_report += (
                f"\n  Filtered peaks: {total_classified} ({classified_pct:.1f}%"
            )
            classification_report += (
                f"\n  Unfiltered peaks: {total_unclassified} ({unclassified_pct:.1f}%"
            )

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

        if hasattr(self, "_peak_prominence_classification_results"):
            prominence_stats = self._peak_prominence_classification_results
            classification_report += "\n\nPeak Prominence Classification:"

            total_prominence_peaks = cast(int, prominence_stats.get("total_peaks", 0))
            lower_prominence_count = cast(int, prominence_stats.get("lower_count", 0))
            higher_prominence_count = cast(int, prominence_stats.get("higher_count", 0))
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

            # NOTE (integration): this read the value, converted it with float(),
            # and only then tested `threshold is not None` - a test that can never
            # fire, since float() either returns a float or raises. A missing
            # "threshold" key therefore raised TypeError from float(None) instead
            # of skipping the line below. The check now guards the conversion,
            # which is what was intended, and the cast() it needed is gone too.
            raw_threshold = prominence_stats.get("threshold")
            if isinstance(raw_threshold, (int, float)) and not isinstance(
                raw_threshold, bool
            ):
                classification_report += f"\n  Threshold: {float(raw_threshold):.2f} pA"

            centers = prominence_stats.get("centers")

            if isinstance(centers, list) and centers:
                formatted_centers = ", ".join(f"{center:.2f}" for center in centers)
                classification_report += f"\n  Centers: {formatted_centers} pA"
            # Break down by peak type

        # Translocation direction classification
        classification_report += "\n\nTranslocation Direction Classification:"
        if hasattr(self, "_translocation_direction_results"):
            td = self._translocation_direction_results
            if "skipped" in td:
                classification_report += f"\n  Skipped: {td['reason']}"
                classification_report += (
                    "\n  Note: sequences are not dependent on translocation direction"
                )
            else:
                total_td = cast(int, td["total_events"])
                fwd = cast(int, td["forward_count"])
                bwd = cast(int, td["backward_count"])
                classification_report += f"\n  Total classified: {total_td} events"
                classification_report += f"\n  Forward: {fwd} ({fwd/total_td:.1%})"
                classification_report += f"\n  Backward: {bwd} ({bwd/total_td:.1%})"
                classification_report += f"\n  Lower center : {td['lower_center']:.3f}"
                classification_report += (
                    f"\n  Higher center : {td['higher_center']:.3f}"
                )
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
                classification_report += (
                    f"\n    Forward:      {fwd_total} ({fwd_total/total_events:.1%})"
                )
                classification_report += (
                    f"\n    Backward:     {bwd_total} ({bwd_total/total_events:.1%})"
                )
                classification_report += f"\n    Unclassified: {unclassified_total} ({unclassified_total/total_events:.1%})"

        # Sequence statistics across all channels
        if hasattr(self, "event_metadata"):
            sequence_counts: dict[str, int] = {}
            total_with_sequence = 0
            for ch, ch_events in self.event_metadata.items():
                for ev_data in ch_events.values():
                    seq = ev_data.get("sequence", "")
                    if seq:
                        sequence_counts[seq] = sequence_counts.get(seq, 0) + 1
                        total_with_sequence += 1

            if sequence_counts:
                classification_report += "\n\nSequence Statistics:"
                classification_report += (
                    f"\n  Events with a sequence: {total_with_sequence}"
                )
                for seq, count in sorted(sequence_counts.items(), key=lambda x: -x[1]):
                    pct = count / total_with_sequence * 100
                    classification_report += f"\n  '{seq}': {count} ({pct:.1f}%)"

        return base_report + classification_report

    ###################################################################################################################
    ###################################################################################################################

    # classifiers

    @log(logger=logger)
    def _classify_folded_unfolded(
        self,
        channels: list[int],
        all_event_info: list[tuple[int, int]],
        all_longest_levels_array: np.ndarray,
    ) -> None:
        """
        Implementation notes:
        - Assumes carrier-blockage pre-filtering has already been applied to the
            provided `all_longest_levels_array` (do not double-filter).
        - Fit a two-component mixture to that array via `fit_threshold` to obtain
            two population centres and the threshold between them.
        - Classify all events and save results + plotting

        Deliberately carries no ECD percentile pre-filter and no re-fit
        fallbacks: the fit sees the whole dataset exactly once and either
        succeeds or fails, so its real success rate on live data is observable
        instead of being masked by retries. The histogram is likewise built once
        and reused for both the fit and the plot, so the plot can no longer be
        binned against edges derived from a different subset of the data.
        """

        try:
            bt = self.fit_threshold(all_longest_levels_array)
        except Exception as e:
            self.logger.error(f"folding fit failed: {e}")
            self._classification_results = {"error": "fit failed"}
            self._collect_peak_statistics(channels)
            return

        # Diagnostic logging for folding fit: params, centers, histogram info
        try:
            params_dbg = bt.get("params") if isinstance(bt, dict) else None
            centers_dbg = bt.get("centers") if isinstance(bt, dict) else None
            hist_dbg = bt.get("hist") if isinstance(bt, dict) else None
            hcnt = (
                hist_dbg[0].tolist()[:5]
                if hist_dbg is not None and hist_dbg[0] is not None
                else None
            )
            hbins = (
                len(hist_dbg[1])
                if hist_dbg is not None and hist_dbg[1] is not None
                else None
            )
            self.logger.debug(
                f"folding fit: params={params_dbg}, centers={centers_dbg}, hist_counts_head={hcnt}, hist_bins={hbins}, n_events={all_longest_levels_array.size}"
            )
        except (TypeError, IndexError, KeyError, AttributeError):
            pass

        if not bt or "threshold" not in bt or bt.get("centers") is None:
            self.logger.error(
                "the fit returned insufficient results for " "classification"
            )
            self._classification_results = {"error": "fit insufficient results"}
            self._collect_peak_statistics(channels)
            return

        centers_bt = np.asarray(bt.get("centers"), dtype=float)
        if centers_bt.size < 2:
            self.logger.warning(
                "the fit did not yield two centres; cannot " "classify folded/unfolded"
            )
            self._classification_results = {
                "error": "Could not find two distinct distributions"
            }
            self._collect_peak_statistics(channels)
            return

        # A folded/unfolded split only means something if the blockage-level
        # distribution actually has two populations. `fit_threshold` reports
        # that via "n_components", derived from the same
        # collapsed-component / centres-not-separated diagnostics
        # `_fit_em_double_gaussian` already computes - forcing a split
        # onto genuinely unimodal data produces a collapsed component or two
        # centres on the same mode, and that outcome is acted on here instead
        # of only appearing as a log line.
        n_components = bt.get("n_components", 2)
        if n_components < 2:
            self.logger.warning(
                "folding classification: the fit describes a "
                "single population in the longest-blockage-level "
                "distribution; folded and unfolded cannot be distinguished "
                "from blockage level alone, so no split is reported."
            )
            self._classification_results = {
                "n_components": 1,
                "error": "only one population detected; cannot classify "
                "folded vs unfolded",
            }
            self._collect_peak_statistics(channels)
            return

        sorted_idx = np.argsort(centers_bt)
        lower_center = float(centers_bt[sorted_idx[0]])
        higher_center = float(centers_bt[sorted_idx[1]])
        ratio = higher_center / lower_center if lower_center > 0 else 0
        # A folded carrier blocks roughly twice as deeply as an unfolded one, so
        # a healthy fit puts the two centres at a ratio near 2. This is reported
        # and logged but deliberately NOT acted on: the previous re-fit on
        # blockage-filtered data rescued weak fits, which is exactly what makes
        # a bad fit rate invisible.
        if not 1.7 <= ratio <= 2.3:
            self.logger.warning(
                f"folding fit: centre ratio {ratio:.3f} is outside the expected "
                f"1.7-2.3 band (lower={lower_center:.3f}, "
                f"higher={higher_center:.3f}); the fit may not have resolved the "
                "folded and unfolded populations."
            )

        threshold = bt.get("threshold", (lower_center + higher_center) / 2.0)

        # Classify events
        # NOTE (S112 fix): `all_event_info` and `all_longest_levels_array` are
        # always built together, index-for-index, by the sole caller
        # (`_post_process_events`), so this lookup cannot legitimately go out of
        # range. The previous `except Exception: continue` silently dropped the
        # event from `folded_count`/`unfolded_count` (and skipped
        # `update_event_metadata_post_processing` for it) with no log line,
        # which let `_classification_results["total_events"]`
        # (== len(all_event_info)) silently stop reconciling with
        # folded_count + unfolded_count. Replaced with an explicit length
        # check, logged once, so a mismatch surfaces instead of quietly
        # eating an event.
        n_events = min(len(all_event_info), int(all_longest_levels_array.size))
        if n_events != len(all_event_info):
            self.logger.warning(
                f"_classify_folded_unfolded: all_event_info has "
                f"{len(all_event_info)} entries but all_longest_levels_array "
                f"has {all_longest_levels_array.size}; truncating to "
                f"{n_events} events to avoid an out-of-range lookup. This "
                "indicates a caller bug."
            )
        folded_count = 0
        unfolded_count = 0
        for i in range(n_events):
            ch, event_index = all_event_info[i]
            event_primary_level = all_longest_levels_array[i]
            if event_primary_level >= threshold:
                event_folded_level = event_primary_level
                event_unfolded_level = event_primary_level / 2.0
                folded_count += 1
            else:
                event_unfolded_level = event_primary_level
                event_folded_level = event_primary_level * 2.0
                unfolded_count += 1
            try:
                self.update_event_metadata_post_processing(
                    ch, event_index, event_unfolded_level, event_folded_level
                )
            except Exception as e:
                self.logger.error(f"Error updating event metadata: {e}")

        # Save classification results
        self._classification_results = {
            "total_events": len(all_event_info),
            "n_components": n_components,
            "folded_count": int(folded_count),
            "unfolded_count": int(unfolded_count),
            "lower_center": lower_center,
            "higher_center": higher_center,
            "threshold": threshold,
            "fit_method": bt.get("fit_method"),
            "threshold_method": bt.get("threshold_method"),
            "valley_threshold": bt.get("valley_threshold"),
            "ratio": ratio,
            # No ECD pre-filter is applied any more, so nothing is excluded from
            # the fit. Key retained because report_channel_status reads it.
            "ecd_filtered_events": 0,
        }

        # Plotting: always create and save plot using the fit's histogram bins
        try:
            loader = getattr(self, "eventloader", None)
            plot_path = None
            if loader is not None and hasattr(loader, "get_base_file"):
                base_file = loader.get_base_file()
                plot_path = base_file.with_name(
                    f"{base_file.stem}_folding_classification.png"
                )

            matplotlib.use("Agg")

            counts, bins = bt.get("hist", (None, None))
            arr_all = np.asarray(all_longest_levels_array)
            arr = np.asarray(all_longest_levels_array)
            fig, ax = plt.subplots(figsize=(12, 6))

            # Ensure non-zero dynamic range to avoid histogram normalization warnings
            arr = self._jitter_degenerate_array(arr)

            # Plot overall histogram using full data (including outliers)
            hist_bins = None
            if counts is not None and bins is not None and np.sum(counts) > 0:
                widths = np.diff(bins)
                # Same bin edges the fit used, which are now the full-data edges
                try:
                    if arr_all.size == 0 or np.any(widths <= 0):
                        raise ValueError("invalid bins")
                    full_counts, _ = np.histogram(arr_all, bins=bins)
                    centers = (bins[:-1] + bins[1:]) / 2.0
                    ax.bar(
                        centers,
                        full_counts,
                        width=widths,
                        alpha=0.5,
                        color="gray",
                        label="All Events (incl. outliers)",
                    )
                    hist_bins = bins
                except Exception:
                    ax.hist(
                        arr_all,
                        bins=50,
                        density=False,
                        alpha=0.5,
                        color="gray",
                        label="All Events (incl. outliers)",
                    )
                    hist_bins = None
            else:
                ax.hist(
                    arr_all,
                    bins=50,
                    density=False,
                    alpha=0.5,
                    color="gray",
                    label="All Events (incl. outliers)",
                )
                hist_bins = None

            # Determine class masks and counts (on filtered/classified data)
            class_mask = arr >= threshold
            higher_count = int(np.sum(class_mask))
            lower_count = int(len(arr) - higher_count)
            total_events_plot = len(arr)
            # Outliers = events present in full data but not in filtered data used for fit
            n_outliers = int(max(0, arr_all.size - arr.size))
            pct_outliers = n_outliers / arr_all.size if arr_all.size > 0 else 0.0

            # Plot per-class histograms using same bins when available
            try:
                if hist_bins is not None:
                    lower_counts, _ = np.histogram(arr[~class_mask], bins=hist_bins)
                    higher_counts, _ = np.histogram(arr[class_mask], bins=hist_bins)
                    widths = np.diff(hist_bins)
                    centers = (hist_bins[:-1] + hist_bins[1:]) / 2.0
                    ax.bar(
                        centers,
                        lower_counts,
                        width=widths,
                        alpha=0.6,
                        color="blue",
                        label="Unfolded",
                    )
                    ax.bar(
                        centers,
                        higher_counts,
                        width=widths,
                        alpha=0.6,
                        color="red",
                        label="Folded",
                    )
                else:
                    ax.hist(
                        arr[~class_mask],
                        bins=100,
                        density=False,
                        alpha=0.6,
                        color="blue",
                        label="Unfolded",
                    )
                    ax.hist(
                        arr[class_mask],
                        bins=100,
                        density=False,
                        alpha=0.6,
                        color="red",
                        label="Folded",
                    )
            except Exception as e:
                self.logger.debug(
                    "folded/unfolded classification: failed to draw the "
                    f"per-class histogram overlay: {e}",
                    exc_info=True,
                )

            # Overlay clusters if parameters available (label with gauss params)
            params = bt.get("params")
            x_range = np.linspace(arr.min(), arr.max(), 1000)
            self._overlay_fitted_gaussians(
                ax,
                params,
                x_range,
                "Unfolded fit",
                "Folded fit",
                "folded/unfolded classification",
            )

            # The curve the threshold below was actually chosen from
            self._overlay_smoothing_spline(ax, bt)

            # The histogram-derived boundary this threshold replaced, if any
            self._overlay_valley_reference(ax, bt)

            # Vertical threshold line (value shown in info textbox)
            ax.axvline(
                threshold,
                color="black",
                linestyle="-",
                linewidth=2,
                label=f"Threshold: {threshold:.3f} pA",
            )

            # Info textbox with counts and threshold type
            try:
                pct_low = (
                    lower_count / total_events_plot if total_events_plot > 0 else 0.0
                )
                pct_high = (
                    higher_count / total_events_plot if total_events_plot > 0 else 0.0
                )
                pct_outliers = (
                    n_outliers / total_events_plot if total_events_plot > 0 else 0.0
                )
                info_text = (
                    f"Total Events (used for fit): {total_events_plot}\n"
                    f"Fit: {bt.get('fit_method')} / {bt.get('threshold_method')}\n"
                    f"Unfolded: {lower_count} ({pct_low:.1%})\n"
                    f"Folded: {higher_count} ({pct_high:.1%})\n"
                    f"Outliers excluded from fit: {n_outliers} ({pct_outliers:.1%})\n"
                )
                ax.text(
                    0.02,
                    0.98,
                    info_text,
                    transform=ax.transAxes,
                    fontsize=10,
                    verticalalignment="top",
                    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.9),
                )
            except Exception as e:
                self.logger.debug(
                    "folded/unfolded classification: failed to draw the "
                    f"summary stats textbox: {e}",
                    exc_info=True,
                )

            # Outlier info shown in textbox; do not add legend entry

            ax.set_xlabel("Longest Blockage Level (pA)")
            ax.set_ylabel("Counts")
            ax.set_title("Folding Classification")
            ax.legend()
            plt.tight_layout()
            if plot_path is not None:
                plt.savefig(plot_path, dpi=300, bbox_inches="tight")
                self.logger.info(f"Folding classification plot saved to {plot_path}")
            plt.close(fig)
        except Exception as e:
            self.logger.error(f"Error saving folding classification plot: {e}")

    @log(logger=logger)
    def _classify_peak_prominences(self, channels: list[int]) -> None:
        """
        Classify peak prominences for peaks whose filtered value is 1, 2, or 3.

        Peaks below the threshold are written as class 0 and peaks at or above
        it as class 1. This holds whether ``fit_threshold`` found two
        populations or one: on single-population data the threshold is the first
        local minimum above ``2 * mean - 2 * std`` rather than a valley between
        two centres (see ``_threshold_between_populations``), but the split
        itself is the same. That is deliberately unlike
        ``_classify_folded_unfolded`` and ``_classify_translocation_direction``,
        which decline to classify a single population at all - "folded" and
        "forward" are claims about a second population that was not found,
        whereas "more prominent than this population accounts for" is not.
        """
        prominence_values: list[float] = []
        prominence_refs: list[tuple[int, int, int]] = []

        for ch in channels:
            if ch not in self.sublevel_metadata:
                continue

            for event_index, sublevel_data in self.sublevel_metadata[ch].items():
                filtered_values = np.asarray(
                    sublevel_data.get("filtered", []), dtype=float
                )
                prominences = np.asarray(
                    sublevel_data.get("prominence", []), dtype=float
                )
                peak_ids = sublevel_data.get("peak_id", [])

                if "classified" not in sublevel_data or len(
                    sublevel_data["classified"]
                ) != len(peak_ids):
                    self.sublevel_metadata[ch][event_index]["classified"] = np.full(
                        len(peak_ids), np.nan, dtype=np.float64
                    )
                if "classification_confidence" not in sublevel_data or len(
                    sublevel_data["classification_confidence"]
                ) != len(peak_ids):
                    self.sublevel_metadata[ch][event_index][
                        "classification_confidence"
                    ] = np.full(len(peak_ids), np.nan, dtype=np.float64)

                for peak_index, peak_id in enumerate(peak_ids):
                    if peak_id is None or (
                        isinstance(peak_id, float) and np.isnan(peak_id)
                    ):
                        continue
                    if peak_index >= len(filtered_values) or peak_index >= len(
                        prominences
                    ):
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

        # Fit the prominence histogram. `fit_threshold` reports whether the fit
        # describes two populations or one (see its "n_components") via the
        # collapsed-component / centres-not-separated diagnostics
        # `_fit_em_double_gaussian` computes.
        try:
            bt = self.fit_threshold(prominence_array)
        except Exception as e:
            self.logger.error(f"fit failed for prominence classification: {e}")
            return

        n_components = bt.get("n_components", 2)
        centers = (
            np.asarray(bt.get("centers"), dtype=float)
            if bt.get("centers") is not None
            else np.array([])
        )

        # NOTE (integration): bt.get('threshold') is Optional, so float()
        # raised TypeError whenever the threshold fit returned without a
        # threshold.
        # Checked and raised explicitly instead.
        fit_threshold_value = bt.get("threshold")
        if fit_threshold_value is None:
            raise RuntimeError(
                "the fit returned no 'threshold'; prominence classes "
                "cannot be assigned without one"
            )
        threshold = float(fit_threshold_value)

        # A single population still gets a threshold and a split. Unlike the
        # other two classifiers - which decline, because there is no meaningful
        # "folded" or "forward" to name without a second population - a
        # prominence split above 2*mean-2*std remains meaningful here: it is the
        # boundary above which a peak is too prominent to belong to the one
        # population that was found, whether or not those peaks are numerous
        # enough to form a mode of their own.
        if n_components < 2:
            self.logger.info(
                "peak prominence classification: the fit describes a single "
                f"population, so the {threshold:.4g} pA threshold comes from "
                f"'{bt.get('threshold_method')}' rather than a valley between "
                "two centres. Peaks below it are class 0, above it class 1."
            )

        class_labels = np.where(prominence_array >= threshold, 1.0, 0.0).astype(
            np.float64
        )

        # Per-peak confidence that the assigned class is correct - see
        # _classification_confidence for the derivation. Uses bt["params"] as
        # fitted by the Student-t mixture (see fit_threshold).
        confidence_values = self._classification_confidence(
            prominence_array, bt["params"], class_labels.astype(bool)
        )

        # Assign classifications back to sublevel metadata
        for class_label, confidence_value, (ch, event_index, peak_index) in zip(
            class_labels, confidence_values, prominence_refs
        ):
            self.sublevel_metadata[ch][event_index]["classified"][
                peak_index
            ] = class_label
            self.sublevel_metadata[ch][event_index]["classification_confidence"][
                peak_index
            ] = confidence_value

        self._peak_prominence_classification_results = {
            "total_peaks": len(prominence_array),
            "n_components": n_components,
            "threshold": threshold,
            "fit_method": bt.get("fit_method"),
            "threshold_method": bt.get("threshold_method"),
            "valley_threshold": bt.get("valley_threshold"),
            "centers": centers.tolist() if centers.size > 0 else [],
            "lower_count": int(np.sum(class_labels == 0)),
            "higher_count": int(np.sum(class_labels == 1)),
        }

        # Plotting: always save plot using the fit's histogram
        try:
            loader = getattr(self, "eventloader", None)
            plot_path = None
            if loader is not None and hasattr(loader, "get_base_file"):
                base_file = loader.get_base_file()
                plot_path = base_file.with_name(
                    f"{base_file.stem}_peak_prominence_classification.png"
                )

            matplotlib.use("Agg")

            counts, bins = bt.get("hist", (None, None))
            arr_all = np.asarray(prominence_array, dtype=float)
            arr = arr_all
            fig, ax = plt.subplots(figsize=(12, 6))

            # Ensure non-zero dynamic range
            arr = self._jitter_degenerate_array(arr)

            # Plot overall histogram using full data (all peaks)
            hist_bins = None
            if counts is not None and bins is not None and np.sum(counts) > 0:
                widths = np.diff(bins)
                try:
                    if arr_all.size == 0 or np.any(widths <= 0):
                        raise ValueError("invalid bins")
                    full_counts, _ = np.histogram(arr_all, bins=bins)
                    centers = (bins[:-1] + bins[1:]) / 2.0
                    ax.bar(
                        centers,
                        full_counts,
                        width=widths,
                        alpha=0.5,
                        color="gray",
                        label="All Peaks (incl. outliers)",
                    )
                    hist_bins = bins
                except Exception:
                    ax.hist(
                        arr_all,
                        bins=100,
                        density=False,
                        alpha=0.5,
                        color="gray",
                        label="All Peaks (incl. outliers)",
                    )
                    hist_bins = None
            else:
                ax.hist(
                    arr_all,
                    bins=100,
                    density=False,
                    alpha=0.5,
                    color="gray",
                    label="All Peaks (incl. outliers)",
                )
                hist_bins = None

            # Overlay fitted Gaussians and per-class histograms
            params = bt.get("params")
            x_range = np.linspace(arr.min(), arr.max(), 1000)

            lower_count = (
                int(np.sum(class_labels == 0))
                if "class_labels" in locals()
                else (
                    int(np.sum(np.asarray(arr) < threshold))
                    if threshold is not None
                    else 0
                )
            )
            higher_count = (
                int(np.sum(class_labels == 1))
                if "class_labels" in locals()
                else (
                    int(np.sum(np.asarray(arr) >= threshold))
                    if threshold is not None
                    else 0
                )
            )
            total_peaks = len(arr)
            n_outliers = int(max(0, arr_all.size - arr.size))
            pct_outliers = n_outliers / arr_all.size if arr_all.size > 0 else 0.0

            # Plot class histograms using the same bins when available
            params = bt.get("params")
            x_range = (
                np.linspace(np.nanmin(arr), np.nanmax(arr), 1000)
                if arr.size > 0
                else np.linspace(0, 1, 1000)
            )
            self._overlay_fitted_gaussians(
                ax,
                params,
                x_range,
                "Lower prominence fit",
                "Higher prominence fit",
                "peak prominence classification",
            )

            if "class_labels" in locals() and class_labels is not None:
                lower_mask = class_labels == 0
                higher_mask = class_labels == 1
                if hist_bins is not None:
                    lower_counts, _ = np.histogram(arr[lower_mask], bins=hist_bins)
                    higher_counts, _ = np.histogram(arr[higher_mask], bins=hist_bins)
                    widths = np.diff(hist_bins)
                    centers = (hist_bins[:-1] + hist_bins[1:]) / 2.0
                    ax.bar(
                        centers,
                        lower_counts,
                        width=widths,
                        alpha=0.6,
                        color="blue",
                        label="Lower prominence",
                    )
                    ax.bar(
                        centers,
                        higher_counts,
                        width=widths,
                        alpha=0.6,
                        color="red",
                        label="Higher prominence",
                    )
                else:
                    ax.hist(
                        arr[lower_mask],
                        bins=100,
                        density=False,
                        alpha=0.6,
                        color="blue",
                        label="Lower prominence",
                    )
                    ax.hist(
                        arr[higher_mask],
                        bins=100,
                        density=False,
                        alpha=0.6,
                        color="red",
                        label="Higher prominence",
                    )

            # The curve the threshold below was actually chosen from. Drawn
            # even in the single-population case, where there is no threshold
            # line to justify: the spline is then the clearest evidence on the
            # plot that the distribution has no valley to split on.
            self._overlay_smoothing_spline(ax, bt)

            # The histogram-derived boundary this threshold replaced, if any
            self._overlay_valley_reference(ax, bt)

            # Vertical threshold line
            if threshold is not None:
                ax.axvline(
                    threshold,
                    color="black",
                    linestyle="-",
                    linewidth=2,
                    label=f"Threshold: {threshold:.3f} pA",
                )

            # Info textbox with counts and threshold type
            try:
                pct_low = lower_count / total_peaks if total_peaks > 0 else 0.0
                pct_high = higher_count / total_peaks if total_peaks > 0 else 0.0
                pct_outliers = n_outliers / total_peaks if total_peaks > 0 else 0.0
                info_text = (
                    f"Total Peaks (used for fit): {total_peaks}\n"
                    f"Selected populations: {n_components}\n"
                    f"Fit: {bt.get('fit_method')} / {bt.get('threshold_method')}\n"
                    f"Class 0: {lower_count} ({pct_low:.1%})\n"
                    f"Class 1: {higher_count} ({pct_high:.1%})\n"
                    f"Outliers excluded from fit: {n_outliers} ({pct_outliers:.1%})\n"
                )
                ax.text(
                    0.02,
                    0.98,
                    info_text,
                    transform=ax.transAxes,
                    fontsize=10,
                    verticalalignment="top",
                    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.9),
                )
            except Exception as e:
                self.logger.debug(
                    "peak prominence classification: failed to draw the "
                    f"summary stats textbox: {e}",
                    exc_info=True,
                )

            # Outlier info shown in textbox; do not add legend entry

            ax.set_xlabel("Peak Prominence (pA)")
            ax.set_ylabel("Counts")
            ax.set_title("Peak Prominence Classification")
            ax.legend()
            plt.tight_layout()
            if plot_path is not None:
                plt.savefig(plot_path, dpi=300, bbox_inches="tight")
                self.logger.info(
                    f"Peak prominence classification plot saved to {plot_path}"
                )
            plt.close(fig)
        except Exception as e:
            self.logger.error(f"Error saving peak prominence plot: {e}")

    @log(logger=logger)
    def _classify_translocation_direction(self, channels: list[int]) -> None:
        """
        Classify translocation direction using cumulative ECD before/after type-3 peaks.

        Builds `log_ecds` (log10 ratio of pre-/post- ECD surrounding type-3 peaks)
        and `event_refs` (tuples of (channel, event_index)), then uses
        `fit_threshold` to compute a threshold and classify each event as
        forward/backward.
        """
        event_refs: list[tuple[int, int]] = []
        log_ecds: list[float] = []

        for ch in channels:
            if ch not in self.sublevel_metadata:
                continue
            for event_index, sublevel_data in self.sublevel_metadata[ch].items():
                # Load per-event arrays
                filtered_arr = np.asarray(
                    sublevel_data.get("filtered", []), dtype=float
                )
                csum = np.asarray(
                    sublevel_data.get("sublevel_cumulative_ecd", []), dtype=float
                )

                # Fall back to raw ECDs if cumulative not present
                if csum.size == 0:
                    raw = np.asarray(
                        sublevel_data.get("sublevel_raw_ecd", []), dtype=float
                    )
                    if raw.size == 0:
                        self.logger.debug(
                            f"Ch{ch} Event{event_index}: Skipped - missing ECD data"
                        )
                        continue
                    csum = np.cumsum(raw)

                # Select type-3 peaks strictly from post-filter labels.
                # Do not fall back to `peak_id` selection; if no filtered
                # labels exist or none equal 3, skip this event.
                if filtered_arr.size == 0 or not np.any(~np.isnan(filtered_arr)):
                    # No filtered labels to use
                    continue

                type3_indices = np.where(
                    (~np.isnan(filtered_arr)) & (filtered_arr == 3)
                )[0]
                if type3_indices.size == 0:
                    # No type-3 peaks in this event
                    continue

                first_type3_idx = int(type3_indices[0])
                last_type3_idx = int(type3_indices[-1])

                # Ensure indices are within bounds of the cumulative array
                if first_type3_idx >= csum.size or last_type3_idx >= csum.size:
                    self.logger.debug(
                        f"Ch{ch} Event{event_index}: Skipped - type-3 index out of bounds (first={first_type3_idx}, last={last_type3_idx}, len={csum.size})"
                    )
                    continue

                # Compute ECD before the first type-3 peak and after the last type-3 peak
                ecd_before = (
                    float(csum[first_type3_idx - 1]) if first_type3_idx > 0 else 0.0
                )
                ecd_after = (
                    float(csum[-1] - csum[last_type3_idx])
                    if last_type3_idx < (csum.size - 1)
                    else 0.0
                )

                if ecd_before <= 0 or ecd_after <= 0:
                    self.logger.debug(
                        f"Ch{ch} Event{event_index}: Skipped - invalid ECD values (before={ecd_before}, after={ecd_after})"
                    )
                    continue

                event_refs.append((ch, event_index))
                log_ecds.append(np.log10(ecd_before / ecd_after))

        if len(log_ecds) == 0:
            self.logger.warning(
                "No events available for translocation direction classification"
            )
            self._translocation_direction_results = {
                "skipped": True,
                "reason": "no data",
            }
            return

        log_ecds_arr = np.asarray(log_ecds, dtype=float)

        # ECD outlier filtering: restrict to 5th-95th percentile to avoid extreme ratios
        try:
            p5 = np.percentile(log_ecds_arr, 5)
            p95 = np.percentile(log_ecds_arr, 95)
            mask = (log_ecds_arr >= p5) & (log_ecds_arr <= p95)
            if np.sum(mask) < 2:
                # not enough data after filtering
                self.logger.warning(
                    "Translocation direction: insufficient events after ECD percentile filtering"
                )
                self._translocation_direction_results = {
                    "skipped": True,
                    "reason": "insufficient events after ECD filtering",
                }
                return
            filtered_log_ecds = log_ecds_arr[mask]
            filtered_refs = [event_refs[i] for i, m in enumerate(mask) if m]
        except Exception:
            filtered_log_ecds = log_ecds_arr
            filtered_refs = event_refs

        try:
            bt = self.fit_threshold(filtered_log_ecds)
        except Exception as e:
            self.logger.error(f"fit failed for translocation direction: {e}")
            self._translocation_direction_results = {
                "skipped": True,
                "reason": "fit failure",
            }
            return

        centers = (
            np.asarray(bt.get("centers"), dtype=float)
            if bt.get("centers") is not None
            else np.array([])
        )
        if centers.size < 2:
            # Single population -> cannot reliably classify
            self.logger.warning(
                "the fit did not yield two centres for " "translocation direction"
            )
            self._translocation_direction_results = {
                "skipped": True,
                "reason": "insufficient centers",
            }
            return

        # A forward/backward split only means something if the log-ECD-ratio
        # distribution actually has two populations. `fit_threshold` reports
        # that via "n_components", derived from the same
        # collapsed-component / centres-not-separated diagnostics
        # `_fit_em_double_gaussian` already computes - forcing a split
        # onto genuinely unimodal data produces a collapsed component or two
        # centres on the same mode, and that outcome is acted on here instead
        # of only appearing as a log line.
        n_components = bt.get("n_components", 2)
        if n_components < 2:
            self.logger.warning(
                "translocation direction: the fit describes "
                "a single population in the log-ECD-ratio distribution; "
                "forward and backward cannot be distinguished, so no "
                "direction is assigned."
            )
            self._translocation_direction_results = {
                "skipped": True,
                "reason": "only one population detected",
                "n_components": 1,
            }
            return

        sorted_indices = np.argsort(centers)
        lower_center = float(centers[sorted_indices[0]])
        higher_center = float(centers[sorted_indices[1]])
        # NOTE (integration): bt.get("threshold") is Optional, so float() raised
        # TypeError whenever the threshold fit returned without one.
        # Checked and
        # raised explicitly instead.
        fit_threshold_value = bt.get("threshold")
        if fit_threshold_value is None:
            raise RuntimeError(
                "the fit returned no 'threshold'; translocation direction "
                "cannot be classified without one"
            )
        threshold = float(fit_threshold_value)

        # Classify only the filtered events, then map results back to original event refs
        class_labels = (filtered_log_ecds >= threshold).astype(int)
        forward_count = int(np.sum(class_labels == 1))
        backward_count = int(np.sum(class_labels == 0))

        # Per-event confidence that the assigned direction is correct - see
        # _classification_confidence for the derivation. Uses bt["params"] as
        # fitted by the Student-t mixture (see fit_threshold).
        confidence_values = self._classification_confidence(
            filtered_log_ecds, bt["params"], class_labels.astype(bool)
        )

        for label, confidence_value, (ch, event_index) in zip(
            class_labels, confidence_values, filtered_refs
        ):
            direction = "forward" if int(label) == 1 else "backward"
            if ch in self.event_metadata and event_index in self.event_metadata[ch]:
                self.event_metadata[ch][event_index][
                    "translocation_direction"
                ] = direction
                self.event_metadata[ch][event_index]["translocation_confidence"] = (
                    float(confidence_value)
                )

        self.logger.info(
            f"Forward: {forward_count} ({forward_count/len(filtered_refs):.1%}), "
            f"Backward: {backward_count} ({backward_count/len(filtered_refs):.1%})"
        )

        self._translocation_direction_results = {
            "total_events": len(filtered_refs),
            "n_components": n_components,
            "forward_count": forward_count,
            "backward_count": backward_count,
            "lower_center": float(lower_center),
            "higher_center": float(higher_center),
            "threshold": float(threshold),
            "fit_method": bt.get("fit_method"),
            "threshold_method": bt.get("threshold_method"),
            "valley_threshold": bt.get("valley_threshold"),
            "ecd_filtered_events": int(len(event_refs) - len(filtered_refs)),
        }

        # Plotting: always save plot using the fit's histogram
        try:
            loader = getattr(self, "eventloader", None)
            plot_path = None
            if loader is not None and hasattr(loader, "get_base_file"):
                base_file = loader.get_base_file()
                plot_path = base_file.with_name(
                    f"{base_file.stem}_translocation_direction_classification.png"
                )

            matplotlib.use("Agg")

            counts, bins = bt.get("hist", (None, None))
            # Full and filtered arrays: full includes outliers; filtered was used for fit
            arr_all = np.asarray(filtered_log_ecds, dtype=float)
            arr = arr_all
            fig, ax = plt.subplots(figsize=(12, 6))

            # Ensure non-zero dynamic range
            arr = self._jitter_degenerate_array(arr)

            # Overall histogram (plot full data including outliers)
            hist_bins = None
            if counts is not None and bins is not None and np.sum(counts) > 0:
                widths = np.diff(bins)
                try:
                    if arr_all.size == 0 or np.any(widths <= 0):
                        raise ValueError("invalid bins")
                    full_counts, _ = np.histogram(arr_all, bins=bins)
                    centers = (bins[:-1] + bins[1:]) / 2.0
                    ax.bar(
                        centers,
                        full_counts,
                        width=widths,
                        alpha=0.5,
                        color="gray",
                        label="All Events (incl. outliers)",
                    )
                    hist_bins = bins
                except Exception:
                    ax.hist(
                        arr_all,
                        bins=100,
                        density=False,
                        alpha=0.5,
                        color="gray",
                        label="All Events (incl. outliers)",
                    )
                    hist_bins = None
            else:
                ax.hist(
                    arr_all,
                    bins=100,
                    density=False,
                    alpha=0.5,
                    color="gray",
                    label="All Events (incl. outliers)",
                )
                hist_bins = None

            # Per-class masks and counts (use filtered array so counts align with bt)
            class_mask = arr >= threshold
            forward_count = int(np.sum(class_mask))
            backward_count = int(len(arr) - forward_count)
            total_events_plot = len(arr)
            n_outliers = int(max(0, arr_all.size - arr.size))
            pct_outliers = n_outliers / arr_all.size if arr_all.size > 0 else 0.0

            # Plot per-class histograms using the same bins when available
            try:
                if hist_bins is not None:
                    lower_counts, _ = np.histogram(arr[~class_mask], bins=hist_bins)
                    higher_counts, _ = np.histogram(arr[class_mask], bins=hist_bins)
                    widths = np.diff(hist_bins)
                    centers = (hist_bins[:-1] + hist_bins[1:]) / 2.0
                    ax.bar(
                        centers,
                        higher_counts,
                        width=widths,
                        alpha=0.6,
                        color="red",
                        label="Forward",
                    )
                    ax.bar(
                        centers,
                        lower_counts,
                        width=widths,
                        alpha=0.6,
                        color="blue",
                        label="Backward",
                    )
                else:
                    ax.hist(
                        arr[class_mask],
                        bins=100,
                        density=False,
                        alpha=0.6,
                        color="red",
                        label="Forward",
                    )
                    ax.hist(
                        arr[~class_mask],
                        bins=100,
                        density=False,
                        alpha=0.6,
                        color="blue",
                        label="Backward",
                    )
            except Exception as e:
                self.logger.debug(
                    "translocation direction classification: failed to draw "
                    f"the forward/backward class histogram overlay: {e}",
                    exc_info=True,
                )

            x_range = (
                np.linspace(np.nanmin(arr), np.nanmax(arr), 1000)
                if arr.size > 0
                else np.linspace(0, 1, 1000)
            )
            # Overlay fitted gaussians when fit params are sensible (dashed)
            params = bt.get("params")
            self._overlay_fitted_gaussians(
                ax,
                params,
                x_range,
                "Backward fit",
                "Forward fit",
                "translocation direction classification",
            )

            # The curve the threshold below was actually chosen from
            self._overlay_smoothing_spline(ax, bt)

            # The histogram-derived boundary this threshold replaced, if any
            self._overlay_valley_reference(ax, bt)

            # Vertical threshold line (not added to legend; value shown in info textbox)
            ax.axvline(threshold, color="black", linestyle="-", linewidth=2)

            # Info textbox (include outlier counts)
            try:
                pct_fwd = (
                    forward_count / total_events_plot if total_events_plot > 0 else 0.0
                )
                pct_bwd = (
                    backward_count / total_events_plot if total_events_plot > 0 else 0.0
                )
                info_text = (
                    f"Total Events (used for fit): {total_events_plot}\n"
                    f"Fit: {bt.get('fit_method')} / {bt.get('threshold_method')}\n"
                    f"Forward: {forward_count} ({pct_fwd:.1%})\n"
                    f"Backward: {backward_count} ({pct_bwd:.1%})\n"
                    f"Outliers excluded from fit: {n_outliers} ({pct_outliers:.1%})\n"
                )
                ax.text(
                    0.02,
                    0.98,
                    info_text,
                    transform=ax.transAxes,
                    fontsize=10,
                    verticalalignment="top",
                    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.9),
                )
            except Exception as e:
                self.logger.debug(
                    "translocation direction classification: failed to draw "
                    f"the summary stats textbox: {e}",
                    exc_info=True,
                )

            ax.set_xlabel("log10(ECD ratio)")
            ax.set_ylabel("Counts")
            ax.set_title("Translocation Direction Classification")
            # Outlier info shown in textbox; do not add legend entry
            ax.legend()
            plt.tight_layout()
            if plot_path is not None:
                plt.savefig(plot_path, dpi=300, bbox_inches="tight")
                self.logger.info(f"Translocation direction plot saved to {plot_path}")
            plt.close(fig)
        except Exception as e:
            self.logger.error(f"Error saving translocation direction plot: {e}")

    @log(logger=logger)
    def _collect_peak_statistics(self, channels: List[int]) -> None:
        """
        Collect statistics about peak classifications across all events.

        :param channels: List of channel indices to process
        :type channels: List[int]
        """
        # Initialize counters
        peak_type_counts: dict[int, int] = {}
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

                peak_ids = np.asarray(sublevel_data.get("peak_id", []), dtype=float)
                if peak_ids.size == 0:
                    continue

                # Count peak types using the post-filtered labels stored in 'filtered'
                # 'peak_id' marks peak positions (1..N) while 'filtered' contains
                # the assigned type for each sublevel (NaN for non-peaks).
                filtered_arr = np.asarray(
                    sublevel_data.get("filtered", []), dtype=float
                )
                # Mask of positions that are peaks
                peak_mask = ~np.isnan(peak_ids)
                n_peaks_in_event = int(np.sum(peak_mask))
                if n_peaks_in_event <= 0:
                    continue

                total_peaks += n_peaks_in_event

                # For each peak position, read the filtered label and count
                for idx in np.where(peak_mask)[0]:
                    try:
                        label = filtered_arr[idx]
                        if np.isnan(label):
                            # treat NaN as unclassified/rejected
                            peak_type_counts[-1] = peak_type_counts.get(-1, 0) + 1
                        else:
                            label_int = int(label)
                            peak_type_counts[label_int] = (
                                peak_type_counts.get(label_int, 0) + 1
                            )
                    except Exception:
                        # fallback: increment rejected count
                        peak_type_counts[-1] = peak_type_counts.get(-1, 0) + 1

                # Count classified vs unclassified only across peak positions
                classified_arr = np.asarray(
                    sublevel_data.get("classified", []), dtype=float
                )
                if classified_arr.size > 0:
                    classified_peaks = classified_arr[peak_mask]
                    n_classified = int(np.sum(~np.isnan(classified_peaks)))
                    n_unclassified = int(np.sum(np.isnan(classified_peaks)))
                    total_classified += n_classified
                    total_unclassified += n_unclassified

        # Save collected statistics
        self._peak_statistics = {
            "total_peaks": int(total_peaks),
            "total_classified": int(total_classified),
            "total_unclassified": int(total_unclassified),
            "peak_type_counts": peak_type_counts,
        }

    @log(logger=logger)
    def _save_classification_report(self) -> None:
        """
        Generate and save a comprehensive classification report to a text file.

        Uses the report from report_channel_status() to avoid code duplication.
        """
        try:
            loader = getattr(self, "eventloader", None)
            if loader is None:
                self.logger.warning(
                    "No event loader available; skipping classification report save"
                )
                return

            base_file = loader.get_base_file()
            report_path = base_file.with_name(
                f"{base_file.stem}_classification_report.txt"
            )

            # Get the classification report from report_channel_status
            report_text = self.report_channel_status(channel=None, init=False)

            # Add settings section
            settings_section = "\n\nFITTING SETTINGS\n" + "-" * 80 + "\n"
            if self.settings:
                for key, setting_dict in sorted(self.settings.items()):
                    if key.lower() == "metaeventloader":
                        # Save the path of the event loader object
                        if (
                            hasattr(self, "eventloader")
                            and self.eventloader is not None
                        ):
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
            header = (
                "=" * 80
                + "\nCLASSIFICATION REPORT: DNA Folding and Peak Analysis\n"
                + "=" * 80
                + "\n"
            )
            footer = "\n" + "=" * 80
            report_text = header + report_text.lstrip() + settings_section + footer

            # Write report to file with UTF-8 encoding
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_text)

            self.logger.info(f"Classification report saved to {report_path}")
        except Exception as e:
            self.logger.error(
                f"Error saving classification report: {e!s}", exc_info=True
            )

    @log(logger=logger)
    def _jitter_degenerate_array(
        self, arr: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """
        Add a small amount of jitter to a degenerate array so downstream
        histogramming does not choke on it.

        A degenerate array here means empty, all-NaN, or having no dynamic range
        (``max - min <= 0``, including the single-valued case). An empty or
        all-NaN array is returned unchanged - jittering it would not make it
        histogrammable, it would only hide that it is empty/all-NaN - while a
        single-valued array is nudged by a tiny symmetric linspace so
        ``np.histogram`` has a non-zero bin range to work with.

        This replaces three identical ``try: ... except Exception: pass`` blocks
        (S110) that were meant to catch exactly this condition but instead caught
        it *and* silently swallowed genuine failures: ``np.nanmax``/``np.nanmin``
        raise ``ValueError`` on an empty array but only warn (returning ``nan``)
        on an all-NaN one, so the empty-array case was the only one the old
        handler ever actually caught, and any unrelated exception raised inside
        that block would have been hidden the same way.

        :param arr: array to inspect for degeneracy
        :type arr: npt.NDArray[np.float64]
        :return: ``arr`` unchanged if it is empty, all-NaN, or already has
            dynamic range; otherwise ``arr`` plus a small symmetric jitter
        :rtype: npt.NDArray[np.float64]
        """
        if arr.size == 0 or np.all(np.isnan(arr)):
            return arr
        if np.nanmax(arr) - np.nanmin(arr) <= 0:
            return arr + np.linspace(-1e-9, 1e-9, arr.size)
        return arr

    def _overlay_fitted_gaussians(
        self,
        ax: Any,
        params: Optional[Tuple[float, float, float, float, float, float]],
        x_range: npt.NDArray[np.float64],
        lower_label: str,
        higher_label: str,
        context: str,
    ) -> None:
        """
        Draw the two fitted components as dashed curves, ordered by mean.

        Shared by all three classifier plots, which previously each carried
        their own copy of this block and had drifted apart: two skipped the
        NaN/non-positive-std/negative-curve validity checks the third one
        applied, so a bad fit there would either draw nothing (an unexplained
        gap in the legend) or, worse, draw a curve dipping below zero counts.
        This applies the strict version everywhere.

        The curve is in the fit histogram's count units already - ``params``
        carries amplitude, not a mixture weight, so no renormalization is
        needed to match the plotted bars.

        Nothing here rejects or raises: a plot that cannot draw this overlay
        is still a useful plot, so a failure is logged and the rest of the
        figure is left intact.

        :param ax: the matplotlib axes to draw on
        :type ax: Any
        :param params: the six fitted parameters from ``fit_threshold``'s
            ``"params"``, ``(amp1, mean1, std1, amp2, mean2, std2)``, not
            necessarily ordered lower-then-higher, or None to draw nothing
        :type params: Optional[Tuple[float, float, float, float, float, float]]
        :param x_range: the x positions to evaluate and draw both curves over
        :type x_range: npt.NDArray[np.float64]
        :param lower_label: legend label for the lower-mean component, before
            its ``(mu, std)`` are appended
        :type lower_label: str
        :param higher_label: legend label for the higher-mean component,
            before its ``(mu, std)`` are appended
        :type higher_label: str
        :param context: short description of the calling classifier, used to
            prefix log messages so they can be traced back to their plot
        :type context: str
        :return: None; the curves are drawn onto ``ax`` in place
        :rtype: None
        """
        if params is None:
            return
        if len(params) != 6:
            self.logger.warning(
                f"{context}: the fit returned 'params' with {len(params)} "
                "values, expected 6 (amp1, mean1, std1, amp2, mean2, std2); "
                "skipping the fitted-Gaussian overlay for this plot."
            )
            return

        try:
            amp1, mean1, std1, amp2, mean2, std2 = params
            u_params = np.array([mean1, mean2], dtype=float)
            w_params = np.array([std1, std2], dtype=float)
            a_params = np.array([amp1, amp2], dtype=float)

            unusable: Optional[str] = None
            if (
                np.any(np.isnan(u_params))
                or np.any(np.isnan(w_params))
                or np.any(np.isnan(a_params))
            ):
                unusable = "a non-finite parameter"
            elif np.any(w_params <= 0):
                unusable = "a non-positive std"
            if unusable is not None:
                self.logger.debug(
                    f"{context}: skipping the fitted-Gaussian overlay ({unusable})."
                )
                return

            order = np.argsort(u_params)
            lower_idx, higher_idx = int(order[0]), int(order[1])
            model_lower = a_params[lower_idx] * np.exp(
                -0.5 * ((x_range - u_params[lower_idx]) / w_params[lower_idx]) ** 2
            )
            model_higher = a_params[higher_idx] * np.exp(
                -0.5 * ((x_range - u_params[higher_idx]) / w_params[higher_idx]) ** 2
            )
            if np.any(model_lower < -1e-12) or np.any(model_higher < -1e-12):
                self.logger.debug(
                    f"{context}: skipping the fitted-Gaussian overlay "
                    "(negative curve values)."
                )
                return

            ax.plot(
                x_range,
                model_lower,
                "--",
                color="blue",
                label=f"{lower_label} (mu={u_params[lower_idx]:.3f}, "
                f"std={w_params[lower_idx]:.3f})",
            )
            ax.plot(
                x_range,
                model_higher,
                "--",
                color="red",
                label=f"{higher_label} (mu={u_params[higher_idx]:.3f}, "
                f"std={w_params[higher_idx]:.3f})",
            )
        except Exception as e:
            self.logger.debug(
                f"{context}: failed to draw the fitted-Gaussian overlay: {e}",
                exc_info=True,
            )

    @log(logger=logger)
    def _overlay_smoothing_spline(self, ax: Any, bt: Dict[str, Any]) -> None:
        """
        Draw the smoothing spline ``fit_threshold`` searched for a valley on.

        Shared by all three classifier plots. The spline is what actually
        chooses the threshold (see ``_threshold_between_populations``), so
        without it on the plot the threshold line has no visible justification -
        and in the fallback case, no visible explanation for why the valley
        search came up empty.

        Evaluated only across ``"spline_domain"`` - the populated core the
        spline was actually fit over (see ``_trim_to_populated_core``) - never
        the plot's full x-range: ``make_smoothing_spline`` returns a ``BSpline``
        that extrapolates without bound outside its knots, and a heavy-tailed
        histogram's full range reaches far past them.

        Like the fitted-Gaussian overlays this sits alongside, the curve is in
        the fit histogram's count units. That matches the plotted bars whenever
        the plot could reuse the fit's bin edges, which is the normal path; on
        the fallback path where the plot re-bins at 50 or 100 bins instead, this
        curve is on the same mismatched scale as those overlays already are.

        Nothing here rejects or raises: a plot that cannot draw the spline is
        still a useful plot, so a failure is logged at debug and the rest of the
        figure is left intact.

        :param ax: the matplotlib axes to draw on
        :type ax: Any
        :param bt: the dict returned by ``fit_threshold``, read for its
            ``"spline"``, ``"spline_domain"``, and ``"hist"`` entries
        :type bt: Dict[str, Any]
        :return: None; the spline is drawn onto ``ax`` in place
        :rtype: None
        """
        spline = bt.get("spline")
        if spline is None:
            return

        domain = bt.get("spline_domain")
        if domain is None:
            # No populated-core domain on hand (an older result dict, or one
            # built by hand rather than by `fit_threshold`) - fall back to the
            # full histogram range rather than not drawing anything.
            hist = bt.get("hist")
            if not hist or hist[1] is None:
                return
            edges = np.asarray(hist[1], dtype=float)
            if edges.size < 3:
                return
            centers = (edges[:-1] + edges[1:]) / 2.0
            domain = (float(centers[0]), float(centers[-1]))

        try:
            x_spline = np.linspace(domain[0], domain[1], 1000)
            # Clipped at zero for display only: a bin count can never be
            # negative, so a dip below it is a natural-spline boundary
            # artifact, not a feature of the data, and left unclipped it reads
            # on the plot as the curve inventing negative counts. This does
            # not touch the threshold search, which is run on the unclipped
            # spline before this method ever sees it.
            ax.plot(
                x_spline,
                np.clip(spline(x_spline), 0.0, None),
                "-",
                color="green",
                linewidth=1.5,
                alpha=0.9,
                label="Smoothing spline (threshold search)",
            )
        except Exception as e:
            self.logger.debug(
                f"failed to draw the smoothing-spline overlay: {e}",
                exc_info=True,
            )

    @log(logger=logger)
    def _overlay_valley_reference(self, ax: Any, bt: Dict[str, Any]) -> None:
        """
        Draw the spline valley alongside the threshold actually used, when they differ.

        Shared by all three classifier plots. When the threshold has been moved
        to the equiprobability point of the two fitted components, the valley it
        replaced is the natural reference for judging whether that move was
        sensible: the valley is where the *histogram* says the boundary is, the
        equiprobability point is where the *fitted model* says it is, and the gap
        between the two lines is a direct read on how well the two Gaussians
        describe this data. A large gap on a plot is the fastest way to spot a
        population the model is misrepresenting - the skewed upper prominence
        population being the known example.

        Nothing is drawn when the two coincide - single-population data, where
        equiprobability is never attempted, and the rare two-population case
        where the equiprobability point could not be computed at all - since a
        duplicate line at the same x would only clutter the legend.

        Nothing here rejects or raises, for the same reason
        ``_overlay_smoothing_spline`` does not: a plot that cannot draw this
        reference is still a useful plot.

        :param ax: the matplotlib axes to draw on
        :type ax: Any
        :param bt: the dict returned by ``fit_threshold``, read for its
            ``"valley_threshold"`` and ``"threshold"`` entries
        :type bt: Dict[str, Any]
        :return: None; the line is drawn onto ``ax`` in place
        :rtype: None
        """
        valley = bt.get("valley_threshold")
        threshold = bt.get("threshold")
        if valley is None or threshold is None:
            return

        try:
            valley = float(valley)
            threshold = float(threshold)
            if not np.isfinite(valley) or np.isclose(valley, threshold):
                return
            ax.axvline(
                valley,
                color="dimgray",
                linestyle=":",
                linewidth=1.5,
                alpha=0.9,
                label=f"Spline valley (not used): {valley:.3f}",
            )
        except (TypeError, ValueError) as e:
            self.logger.debug(
                f"failed to draw the spline-valley reference line: {e}",
                exc_info=True,
            )

    @log(logger=logger)
    def _fit_em_double_gaussian(
        self,
        data: npt.NDArray[np.float64],
        bins: npt.NDArray[np.float64],
        bin_width: float,
    ) -> Tuple[Optional[npt.NDArray[np.float64]], bool, str]:
        """
        Estimate two mixture components by expectation-maximization on the
        unbinned samples, reported through a robust Student-t fit.

        Why EM rather than least squares on the histogram: least squares
        minimises one residual summed over all bins, so the higher component
        earns credit for reducing residual *anywhere*, including inside the
        lower population's un-modelled right shoulder, and ends up describing
        neither population well. EM has no shared residual - each component's
        location and scale are updated only from data weighted by its own
        responsibility - so that recruitment failure does not arise, and no
        valley or split point is needed to obtain clean parameters.

        **The histogram is still built and still used**, for two things: the
        Freedman-Diaconis bin width (with the ``MIN_FIT_BINS`` floor) sets the
        variance floor and the collapsed-component test, and it provides the
        scale factor that converts EM's mixture weights into the count-unit
        amplitudes the plot overlays and ``_classification_confidence`` expect.
        Binning does not constrain the *fit* itself, which sees every sample at
        full resolution.

        Amplitudes are converted as ``amp_k = w_k * n * bin_width /
        (std_k * sqrt(2*pi))`` - the peak height of component k's density
        rescaled to histogram counts - so ``params`` lands on histogram-count
        scale and every consumer of ``"params"`` (the plot overlays,
        ``_classification_confidence``, the database schema) reads it exactly
        as it always has.

        The **reported** location and scale come from the outlier-robust
        Student-t mixture in ``_fit_student_t_mixture``, so a sparse far tail
        cannot inflate a component's width the way a plain second moment would;
        see ``T_DOF`` for why. A Student-t fit that fails or returns malformed
        parameters falls back to reporting the Gaussian mixture's components
        instead, with a warning, rather than failing the whole classification.

        The one-population decision - a component collapsed to at or below one
        bin width, or two centres closer together than one FWHM of the narrower
        component - is **always taken from the Gaussian mixture**, even when
        Student-t components are what gets reported, and both therefore run on
        every call. Both criteria are expressed in units of a component's
        width, so an estimator returning systematically narrower widths relaxes
        them - measured, deciding from the Student-t widths turned a documented
        single-population reconstruction into two. Rescaling the t scale to its
        distributional standard deviation did not reliably fix that either (it
        rescued one seed and not another), and any factor that rescued both
        would be fitted to two datasets rather than derived. Keeping the
        decision on the Gaussian fit leaves it independent of ``nu``. A
        consequence to be aware of: the centres in ``params`` can differ
        slightly from the centres the decision was made on, and the
        population-count warnings quote the latter.

        It deliberately does **not** use BIC or any likelihood-ratio model
        selection to decide one population versus two - BIC was measured
        decisively choosing two components on genuinely single-population
        skewed data. Using EM to *estimate* two components while keeping these
        shape-based diagnostics to decide whether two are *real* sidesteps that.

        Note that under EM the collapsed-component test is close to vestigial,
        because ``reg_covar`` floors the variance at the same bin-derived value
        the test compares against; it is retained because it still fires if that
        floor is lowered, and because losing it silently would leave the
        one-population decision resting on a single criterion. In testing the
        centres-not-separated criterion did all the work, correctly returning one
        population on pure Gaussian, skewed unimodal and lopsided 95/5
        reconstructions, and two on clean bimodal data.

        :param data: the raw 1-D samples to fit
        :type data: npt.NDArray[np.float64]
        :param bins: histogram bin centers, used only for the amplitude scale
            and the bounds-style reporting
        :type bins: npt.NDArray[np.float64]
        :param bin_width: width of one histogram bin, used as the variance floor
            and the collapsed-component threshold
        :type bin_width: float
        :return: tuple of (fit parameters ordered lower-mean component first,
            or None if EM did not converge), a bool that is True when the fit
            describes one population rather than two (meaningless when the
            first element is None), and a string recording which density the
            reported parameters carry - ``"em_student_t"`` normally, or
            ``"em_gaussian"`` when the Student-t mixture failed and the
            Gaussian mixture's own components were reported instead
        :rtype: Tuple[Optional[npt.NDArray[np.float64]], bool, str]
        """
        arr = np.asarray(data, dtype=float).ravel()
        arr = arr[np.isfinite(arr)]
        if arr.size < 2:
            self.logger.debug("EM fit: fewer than two finite samples")
            return None, False, ""

        # The Gaussian mixture is always fitted, and the one-population decision
        # is always taken from it, whatever component model reports the final
        # parameters. Both criteria below are expressed in units of a
        # component's width, so an estimator that returns systematically
        # narrower widths relaxes them: measured on the documented
        # single-population Dataset B, taking the decision from the Student-t
        # widths turned one population into two. Correcting the t scale to its
        # distributional standard deviation (a factor sqrt(nu/(nu-2))) does not
        # reliably fix that either - it rescued one Dataset B seed and not
        # another, and the factor that would rescue both is a number fitted to
        # two datasets rather than derived from anything. Taking the decision
        # from the non-robust fit keeps it on exactly the footing already
        # validated across every dataset tested, and makes it independent of
        # both the component model and nu.
        try:
            gmm = GaussianMixture(
                n_components=2,
                n_init=self.EM_N_INIT,
                random_state=self.EM_RANDOM_STATE,
                # Same floor the least-squares path applies as min_std, squared:
                # nothing narrower than half a bin is resolvable, and an
                # unfloored EM variance can collapse onto a single sample.
                reg_covar=max((bin_width / 2.0) ** 2, 1e-12),
            )
            gmm.fit(arr.reshape(-1, 1))
        except (ValueError, FloatingPointError) as e:
            self.logger.debug(f"EM fit failed: {e}", exc_info=True)
            return None, False, ""

        if not getattr(gmm, "converged_", False):
            self.logger.warning(
                "EM fit did not converge within its iteration limit; keeping the "
                "returned parameters but they may be unreliable."
            )

        means = np.asarray(gmm.means_, dtype=float).ravel()
        stds = np.sqrt(np.asarray(gmm.covariances_, dtype=float).ravel())
        weights = np.asarray(gmm.weights_, dtype=float).ravel()

        if means.size != 2 or not np.all(np.isfinite(means)):
            self.logger.debug("EM fit returned non-finite or malformed means")
            return None, False, ""

        order_idx = np.argsort(means)
        means = means[order_idx]
        stds = stds[order_idx]
        weights = weights[order_idx]

        # Widths and centres the population-count criteria are evaluated
        # against - always the Gaussian ones, per the note above.
        diagnostic_means = means
        diagnostic_stds = stds

        # Refine the *reported* location and scale with the robust fit, which
        # takes no part in the decision above.
        robust: Optional[
            Tuple[
                npt.NDArray[np.float64],
                npt.NDArray[np.float64],
                npt.NDArray[np.float64],
            ]
        ] = None
        robust = self._fit_student_t_mixture(arr, bin_width)
        if robust is None:
            self.logger.warning(
                "the Student-t mixture could not be fitted; reporting "
                "Gaussian components instead, whose widths are more easily "
                "inflated by a sparse tail."
            )
        else:
            means, stds, weights = robust
            if not (
                means.size == 2
                and np.all(np.isfinite(means))
                and np.all(np.isfinite(stds))
            ):
                self.logger.warning(
                    "the Student-t mixture returned malformed parameters; "
                    "reporting Gaussian components instead."
                )
                means, stds = diagnostic_means, diagnostic_stds
                weights = np.asarray(gmm.weights_, dtype=float).ravel()[order_idx]
                robust = None

        # Mixture weights -> histogram-count amplitudes, so `params` lands on
        # the same scale the least-squares fit produced.
        with np.errstate(divide="ignore", invalid="ignore"):
            amps = np.where(
                stds > 0,
                weights * arr.size * bin_width / (stds * np.sqrt(2.0 * np.pi)),
                0.0,
            )

        params = np.array(
            [amps[0], means[0], stds[0], amps[1], means[1], stds[1]], dtype=float
        )

        one_population = False
        for comp, idx in ((1, 0), (2, 1)):
            if diagnostic_stds[idx] <= bin_width:
                one_population = True
                self.logger.warning(
                    f"EM fit: component {comp} collapsed to a width of "
                    f"{diagnostic_stds[idx]:.4g}, at or below the "
                    f"{bin_width:.4g} bin width. It describes a spike the data "
                    f"cannot resolve, so its centre "
                    f"({diagnostic_means[idx]:.4g}) and any threshold derived "
                    "from it are not meaningful - this is effectively a "
                    "single-component fit."
                )

        narrower_fwhm = 2.355 * float(np.min(diagnostic_stds))
        centre_separation = float(abs(diagnostic_means[1] - diagnostic_means[0]))
        if centre_separation < self.SEED_SEPARATION_FWHM * narrower_fwhm:
            one_population = True
            self.logger.warning(
                f"EM fit: the two fitted centres "
                f"({diagnostic_means[0]:.4g} and {diagnostic_means[1]:.4g}) are "
                f"{centre_separation:.4g} apart, less than the "
                f"{narrower_fwhm:.4g} FWHM of the narrower component. They "
                "describe one mode rather than two populations, so any threshold "
                "between them is arbitrary."
            )

        fell_back = robust is None
        fit_method = "em_gaussian" if fell_back else "em_student_t"
        self.logger.debug(
            f"EM fit ({fit_method}"
            f"{' -> gaussian fallback' if fell_back else ''}): reported "
            f"mu={means[0]:.4g}/{means[1]:.4g} "
            f"scale={stds[0]:.4g}/{stds[1]:.4g} "
            f"weights={weights[0]:.4g}/{weights[1]:.4g} "
            f"amps={amps[0]:.4g}/{amps[1]:.4g}; population count taken from "
            f"gaussian mu={diagnostic_means[0]:.4g}/{diagnostic_means[1]:.4g} "
            f"sd={diagnostic_stds[0]:.4g}/{diagnostic_stds[1]:.4g} "
            f"-> {1 if one_population else 2} on {arr.size} samples"
        )
        return params, one_population, fit_method

    @log(logger=logger)
    def _fit_student_t_mixture(
        self,
        data: npt.NDArray[np.float64],
        bin_width: float,
    ) -> Optional[
        Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]
    ]:
        """
        Fit a two-component Student-t mixture by EM, robustly to tail outliers.

        Same expectation-maximization structure as the Gaussian mixture, with
        one addition: because a Student-t is a Gaussian whose precision is
        itself gamma-distributed, its EM carries a second latent quantity per
        point,

        ``u_ik = (nu + 1) / (nu + (x_i - mu_k)^2 / sigma_k^2)``

        which is near 1 for points close to component k's centre and small for
        points far from it. Location and scale updates are weighted by
        ``r_ik * u_ik`` rather than ``r_ik`` alone, so a sparse far tail no
        longer sets a component's width. That is the whole point: the Gaussian
        scale update is a responsibility-weighted second moment, in which a
        point ten widths out counts a hundred times a point one width out, and
        on a minority population a dozen such points dominate several hundred
        well-behaved ones.

        The scale update divides by ``sum(r_ik)`` while its numerator carries
        ``r_ik * u_ik`` - this is the standard ECM update for a t-mixture with
        fixed degrees of freedom, and it is deliberately *not* self-normalising:
        dividing by ``sum(r_ik * u_ik)`` instead would rescale the estimate back
        towards the non-robust one.

        Initialised deterministically from quantiles of the data rather than
        randomly, so no seed is involved and repeated fits on identical data are
        bit-identical. ``nu`` is held at ``T_DOF`` rather than estimated.

        :param data: the raw 1-D samples to fit
        :type data: npt.NDArray[np.float64]
        :param bin_width: histogram bin width, used as the floor on a
            component's scale for the same reason the other paths use it - a
            component narrower than the binning is not resolvable
        :type bin_width: float
        :return: tuple of (means, scales, weights), each of length two and
            ordered by mean, or None if the data is too small or the loop
            produced non-finite parameters
        :rtype: Optional[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        """
        arr = np.asarray(data, dtype=float).ravel()
        arr = arr[np.isfinite(arr)]
        if arr.size < 4:
            return None

        nu = float(self.T_DOF)
        floor = max(bin_width / 2.0, 1e-12)

        # Deterministic quantile initialisation: one seed low in the
        # distribution, one high, with a common starting scale.
        means = np.array(
            [np.percentile(arr, 25.0), np.percentile(arr, 90.0)], dtype=float
        )
        if np.isclose(means[0], means[1]):
            means = np.array([arr.min(), arr.max()], dtype=float)
        spread = float(np.std(arr))
        scales = np.array(
            [max(spread / 3.0, floor), max(spread / 3.0, floor)], dtype=float
        )
        weights = np.array([0.5, 0.5], dtype=float)

        x = arr[:, None]
        for _ in range(int(self.T_MAX_ITER)):
            # E-step: responsibilities from the t density, in log space so a
            # component that is locally negligible cannot underflow to a hard
            # zero and strand its parameters.
            d2 = (x - means) ** 2 / scales**2
            log_p = (
                np.log(np.clip(weights, 1e-300, None))
                - np.log(scales)
                - (nu + 1.0) / 2.0 * np.log1p(d2 / nu)
            )
            log_p -= log_p.max(axis=1, keepdims=True)
            p = np.exp(log_p)
            denom = p.sum(axis=1, keepdims=True)
            resp = np.divide(p, denom, out=np.full_like(p, 0.5), where=denom > 0)

            # The robustness weights, and the combined weights used for the
            # location/scale updates.
            u = (nu + 1.0) / (nu + d2)
            ru = resp * u

            resp_sum = resp.sum(axis=0)
            ru_sum = ru.sum(axis=0)
            if np.any(resp_sum <= 0) or np.any(ru_sum <= 0):
                self.logger.debug(
                    "Student-t EM: a component lost all responsibility; "
                    "abandoning the robust fit"
                )
                return None

            new_means = (ru * x).sum(axis=0) / ru_sum
            new_scales = np.sqrt((ru * (x - new_means) ** 2).sum(axis=0) / resp_sum)
            new_scales = np.maximum(new_scales, floor)
            new_weights = resp_sum / float(arr.size)

            shift = float(
                np.max(np.abs(new_means - means)) + np.max(np.abs(new_scales - scales))
            )
            means, scales, weights = new_means, new_scales, new_weights
            if shift < float(self.T_TOL):
                break
        else:
            self.logger.debug(
                f"Student-t EM hit its {self.T_MAX_ITER}-iteration cap without "
                "meeting the convergence tolerance; using the current estimate."
            )

        if not (
            np.all(np.isfinite(means))
            and np.all(np.isfinite(scales))
            and np.all(np.isfinite(weights))
        ):
            self.logger.debug("Student-t EM produced non-finite parameters")
            return None

        order_idx = np.argsort(means)
        return means[order_idx], scales[order_idx], weights[order_idx]

    @log(logger=logger)
    def _threshold_at_equiprobability(
        self,
        params: Tuple[float, float, float, float, float, float],
        bins: npt.NDArray[np.float64],
    ) -> Optional[float]:
        """
        Locate the point between the two fitted means where they are equally likely.

        Because the amplitudes in ``params`` are on histogram-count scale, they
        already carry each population's size, so the x where the two fitted
        curves are equal is the point where the mixture posterior is 0.5 - the
        Bayes-optimal boundary under the fitted model. Thresholding there makes
        the classification and ``_classification_confidence`` consistent by
        construction: no point can be assigned a class the model considers less
        likely than the alternative, which is what produced confidences well
        below 0.5 when the threshold came from the spline valley instead.

        Taking logs of ``a1*exp(-(x-m1)^2/(2*s1^2)) = a2*exp(-(x-m2)^2/(2*s2^2))``
        gives a quadratic in x with

        - ``A = 1/(2*s1^2)``, ``B = 1/(2*s2^2)``
        - ``a_coef = B - A``
        - ``b_coef = -2*(B*m2 - A*m1)``
        - ``c_coef = B*m2^2 - A*m1^2 - ln(a2/a1)``

        Two Gaussians of *equal* width cross once (the quadratic degenerates to
        a line, and the root is the amplitude-weighted midpoint). Of *unequal*
        width they cross **twice**, and the second crossing is the reason this
        method filters by bracket rather than just taking a root: out in the
        tail the wider component takes over again, and on real data that second
        root can fall inside the measured range. Only the root strictly between
        the two means separates the two modes; the caller falls back to the
        spline valley when there is none, which happens whenever the smaller
        component never rises above the larger one anywhere between them.

        :param params: the six fitted parameters, ``(amp1, mean1, std1, amp2,
            mean2, std2)``
        :type params: Tuple[float, float, float, float, float, float]
        :param bins: histogram bin centers, used to reject a root outside the
            range the fit actually saw
        :type bins: npt.NDArray[np.float64]
        :return: the equiprobability point between the two means, or None if
            there is no real crossing there or it falls outside the histogram
        :rtype: Optional[float]
        """
        amp1, mean1, std1, amp2, mean2, std2 = (float(p) for p in params)

        if amp1 <= 0.0 or amp2 <= 0.0 or std1 <= 0.0 or std2 <= 0.0:
            self.logger.debug(
                "no equiprobability point: a non-positive amplitude or width "
                f"(amp={amp1:.4g}/{amp2:.4g}, std={std1:.4g}/{std2:.4g})"
            )
            return None

        lower_mean, higher_mean = sorted((mean1, mean2))
        if not higher_mean > lower_mean:
            return None

        a_inv = 1.0 / (2.0 * std1**2)
        b_inv = 1.0 / (2.0 * std2**2)
        a_coef = b_inv - a_inv
        b_coef = -2.0 * (b_inv * mean2 - a_inv * mean1)
        c_coef = b_inv * mean2**2 - a_inv * mean1**2 - np.log(amp2 / amp1)

        roots: List[float] = []
        if abs(a_coef) < 1e-15:
            # Equal widths: the quadratic degenerates to a line.
            if abs(b_coef) > 0.0:
                roots = [-c_coef / b_coef]
        else:
            discriminant = b_coef**2 - 4.0 * a_coef * c_coef
            if discriminant < 0.0:
                self.logger.debug(
                    "no equiprobability point: the two fitted curves never meet "
                    "(negative discriminant), so one component stays below the "
                    "other everywhere."
                )
                return None
            sqrt_disc = float(np.sqrt(discriminant))
            roots = [
                (-b_coef - sqrt_disc) / (2.0 * a_coef),
                (-b_coef + sqrt_disc) / (2.0 * a_coef),
            ]

        bracketed = [r for r in roots if lower_mean < r < higher_mean]
        if not bracketed:
            self.logger.debug(
                f"no equiprobability point between the fitted means "
                f"({lower_mean:.4g}, {higher_mean:.4g}); roots were "
                f"{[f'{r:.4g}' for r in roots]}"
            )
            return None

        outside = [r for r in roots if not (bins[0] <= r <= bins[-1])]
        if outside:
            self.logger.debug(
                "equiprobability: ignoring "
                f"{[f'{r:.4g}' for r in outside]}, outside the fit histogram "
                f"range ({bins[0]:.4g}, {bins[-1]:.4g})"
            )

        second_in_range = [
            r for r in roots if r not in bracketed and bins[0] <= r <= bins[-1]
        ]
        if second_in_range:
            self.logger.info(
                "the two fitted components also cross at "
                f"{[f'{r:.4g}' for r in second_in_range]}, inside the measured "
                "range. Past that point the wider component is the more likely "
                "of the two, so a single threshold cannot match the mixture's "
                "own preference everywhere and a few extreme values will carry "
                "a classification confidence below 0.5."
            )

        threshold = float(min(bracketed))
        if not bins[0] <= threshold <= bins[-1]:
            self.logger.warning(
                f"the equiprobability point ({threshold:.4g}) falls outside the "
                f"fit histogram range ({bins[0]:.4g}, {bins[-1]:.4g}); "
                "deferring to the spline-derived threshold."
            )
            return None
        return threshold

    @log(logger=logger)
    def _histogram_for_fit(
        self, data: npt.NDArray[np.float64]
    ) -> Tuple[
        npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]
    ]:
        """
        Bin 1-D data for two-component mixture fitting using the Freedman-Diaconis rule.

        The Freedman-Diaconis rule is carried over from the deleted ``bitthresh``,
        but with a floor of ``MIN_FIT_BINS`` bins, which ``bitthresh`` did not
        have and did not need.

        The floor matters. FD sets bin width from the interquartile range, and on
        exactly the bimodal data these classifiers exist to separate, the two
        populations inflate the IQR and therefore the bin width, collapsing the
        histogram to a handful of bins. Measured on synthetic two-population data
        (means 300 and 600), FD alone yields 3 bins at n=60, 6 at n=300 and 7 at
        n=600 - against which a six-parameter two-component mixture is
        underdetermined. The fit then fails outright below roughly 600 points,
        and worse, near 600-1000 it can converge with *both* components sitting
        on the same mode (595.4 and 597.3 for a 300/600 dataset) and pass every
        convergence check.
        ``bitthresh`` tolerated the same starved binning only because it fell back
        to raw histogram peak locations whenever its own fit failed.

        With the floor applied, the same synthetic data resolves correctly at
        every size tested from n=60 to n=20000.

        :param data: 1-D array of values to histogram
        :type data: npt.NDArray[np.float64]
        :return: tuple of (counts, bin edges, bin centers)
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]
        :raises ValueError: if there are fewer than three data points
        """
        arr = np.asarray(data, dtype=float).ravel()
        if arr.size < 3:
            raise ValueError("need at least 3 data points to build a fit histogram")

        s_bins = 100
        iqr_val = float(iqr(arr))
        if iqr_val > 0 and arr.size > 1:
            bin_width = 2.0 * iqr_val / (arr.size ** (1.0 / 3.0))
            data_range = float(np.max(arr) - np.min(arr))
            if bin_width > 0 and data_range > 0:
                s_bins = max(3, int(np.ceil(data_range / bin_width)))

        if s_bins < self.MIN_FIT_BINS:
            self.logger.debug(
                f"Freedman-Diaconis suggested {s_bins} bins for {arr.size} "
                f"points; raising to the {self.MIN_FIT_BINS}-bin floor so the "
                "six-parameter mixture fit is not underdetermined."
            )
            s_bins = self.MIN_FIT_BINS

        counts, bin_edges = np.histogram(arr, bins=s_bins)
        bin_centers = (bin_edges[1:] + bin_edges[:-1]) / 2.0
        return counts.astype(float), bin_edges, bin_centers

    def _resolve_two_histogram_peaks(
        self,
        bins: npt.NDArray[np.float64],
        amplitude: npt.NDArray[np.float64],
    ) -> Optional[
        Tuple[
            npt.NDArray[np.intp],
            npt.NDArray[np.float64],
            npt.NDArray[np.float64],
            npt.NDArray[np.float64],
        ]
    ]:
        """
        Find the two most prominent, well-separated maxima in a histogram.

        Two-pass ``find_peaks``: the first pass locates the dominant peak and
        measures its FWHM, and the second re-runs with a ``distance`` floor of
        ``SEED_SEPARATION_FWHM`` times that width, so two maxima on the flank
        of the same mode - which easily clear a bare prominence threshold on
        counting noise - are not accepted as two separate peaks. Used by
        ``_warn_if_fitted_means_are_off_their_peaks`` to know what a fitted
        mean should be compared against.

        :param bins: histogram bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts, the same shape as ``bins``
        :type amplitude: npt.NDArray[np.float64]
        :return: tuple of (the two peak indices ordered by prominence,
            their FWHM in bins, and their interpolated left/right half-max
            edge positions in bins, per ``scipy.signal.peak_widths``), or None
            if fewer than two peaks are found even before the separation
            filter, or if it is fewer than two after
        :rtype: Optional[Tuple[npt.NDArray[np.intp], npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        """
        if bins.size < 2:
            return None
        min_prominence = float(np.max(amplitude)) * 0.05
        peaks, properties = find_peaks(amplitude, prominence=min_prominence)
        if len(peaks) < 2:
            return None

        dominant_peak = peaks[int(np.argmax(properties["prominences"]))]
        dominant_width, _, _, _ = peak_widths(
            amplitude, [dominant_peak], rel_height=0.5
        )
        min_separation = max(
            1, int(np.ceil(self.SEED_SEPARATION_FWHM * dominant_width[0]))
        )
        peaks, properties = find_peaks(
            amplitude, prominence=min_prominence, distance=min_separation
        )
        if len(peaks) < 2:
            return None

        top_two = peaks[np.argsort(properties["prominences"])[-2:][::-1]]
        widths, _, left_ips, right_ips = peak_widths(amplitude, top_two, rel_height=0.5)
        return top_two, widths, left_ips, right_ips

    def _warn_if_fitted_means_are_off_their_peaks(
        self,
        bins: npt.NDArray[np.float64],
        amplitude: npt.NDArray[np.float64],
        params: Tuple[float, float, float, float, float, float],
    ) -> None:
        """
        Log a warning when a fitted mean does not sit on the histogram peak it
        is meant to describe.

        Non-fatal by design, matching this file's existing convention of
        reporting a questionable fit rather than rejecting it: a component
        recruited by a neighbouring mode is still a result worth seeing on the
        plot and in the classification counts, not one worth turning into a
        raised exception. This is what catches, by log line, what previously
        had to be caught by eye on a plot - a component reported centred well
        off the mode it is supposed to be describing.

        The check: resolve the two most prominent, well-separated peaks in the
        histogram (``_resolve_two_histogram_peaks``), then for each fitted
        mean, find the histogram peak nearest it and warn if the mean falls
        outside that peak's half-max span. Silent whenever
        ``_resolve_two_histogram_peaks`` cannot resolve two distinct peaks
        under its strict separation rule - including genuinely single-population
        data, where there is only one real peak and nothing to compare a second
        mean against.

        :param bins: histogram bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts, the same shape as ``bins``
        :type amplitude: npt.NDArray[np.float64]
        :param params: the six final fitted parameters, ``(amp1, mean1, std1,
            amp2, mean2, std2)``
        :type params: Tuple[float, float, float, float, float, float]
        :return: None; a warning is logged for each mean found off its peak
        :rtype: None
        """
        resolved = self._resolve_two_histogram_peaks(bins, amplitude)
        if resolved is None:
            return
        peak_idx, widths, left_ips, right_ips = resolved
        bin_width = float(bins[1] - bins[0]) if bins.size >= 2 else 0.0
        peak_positions = bins[peak_idx]
        left_edges = bins[0] + left_ips * bin_width
        right_edges = bins[0] + right_ips * bin_width

        _, mean1, _, _, mean2, _ = params
        for label, mean in (("first", mean1), ("second", mean2)):
            nearest = int(np.argmin(np.abs(peak_positions - mean)))
            if not (left_edges[nearest] <= mean <= right_edges[nearest]):
                self.logger.warning(
                    f"the {label} fitted component's mean ({mean:.4g}) falls "
                    f"outside the half-maximum span "
                    f"({left_edges[nearest]:.4g}, {right_edges[nearest]:.4g}) "
                    f"of the histogram peak nearest it, at "
                    f"{peak_positions[nearest]:.4g}. It may be describing a "
                    "neighbouring population's shoulder rather than its own "
                    "mode."
                )

    @log(logger=logger)
    def fit_threshold(self, data: npt.NDArray[np.float64]) -> Dict[str, Any]:
        """
        Estimate a binary threshold from 1-D data by fitting a two-component
        Student-t mixture.

        Replaces the previous ``bitthresh`` and keeps its return shape, so the
        three ``_classify_*`` methods and their plotting code consume it
        unchanged - with three exceptions: ``"params"`` is now ordered
        ``(amp1, mean1, std1, amp2, mean2, std2)``, per component, where
        ``bitthresh`` grouped by kind as ``(a1, a2, u1, u2, w1, w2)``; the dict
        has a new ``"n_components"`` key; and the key previously called
        ``"midpoint"`` is now ``"threshold"``, because it is no longer
        necessarily a midpoint (see ``_threshold_between_populations``).

        Unlike ``bitthresh``, this raises rather than falling back to raw
        histogram peak locations when the fit fails. A failed fit is a result
        worth seeing, not one worth papering over.

        A fitted mixture always has two centres, whether or not the data
        actually contains two populations - on genuinely unimodal data it
        either collapses one component or converges with both centres on the
        same mode, both diagnosed by ``_fit_em_double_gaussian``.
        ``"n_components"`` surfaces that diagnosis as ``1`` or ``2`` so a
        caller can act on it directly instead of only finding it in the log.

        The two components come from expectation-maximization on the unbinned
        samples (``_fit_em_double_gaussian``); the histogram is used only for
        the bin width, the smoothing-spline threshold search, and the plots.
        ``"fit_method"`` records whether the reported components are the
        Student-t mixture or, if that fit failed, the Gaussian mixture it falls
        back to. On two-population data the threshold is then always moved to
        the point where the two components are equally likely
        (``_threshold_at_equiprobability``), whenever that point can be
        computed, so that classifications agree with the mixture that produced
        them - a warning is logged, but the equiprobability threshold is still
        used, when it disagrees with the histogram-derived threshold above by
        more than the narrower component's FWHM, since that disagreement means
        a component is poorly described by a Gaussian rather than that the
        equiprobability point is wrong. ``"valley_threshold"`` always carries
        that histogram-derived threshold (despite the name, whichever of
        ``_threshold_between_populations``'s methods actually produced it), so
        the two are comparable on the plots via ``_overlay_valley_reference``.

        :param data: 1-D array of values from which to estimate a binary threshold
        :type data: npt.NDArray[np.float64]
        :return: dict with keys ``"threshold"`` (float), ``"centers"``
            (np.ndarray of the two fitted means), ``"hist"``
            (tuple of counts and bin edges), ``"params"``
            (tuple of the six fitted parameters), ``"n_components"``
            (``1`` if the fit describes one population, ``2`` if it describes
            two), ``"threshold_method"`` (how ``"threshold"`` was picked -
            see ``_threshold_between_populations`` for the histogram-derived
            methods, or ``"equiprobability"`` when it was moved to the point
            where the two components are equally likely, which happens
            whenever the fit found two populations and that point could be
            computed), ``"spline"`` (the
            smoothing spline that search was run on, for plotting, or None),
            ``"spline_domain"`` (the ``(low, high)`` x-range that spline was
            actually fit and should be drawn over, or None), ``"fit_method"``
            (``"em_student_t"`` or ``"em_gaussian"``), and ``"valley_threshold"``
            (the spline-derived threshold, retained for plotting and comparison
            whichever threshold won)
        :rtype: Dict[str, Any]
        :raises ValueError: if the data cannot be histogrammed, or if the
            two-component fit fails to converge
        """
        counts, bin_edges, bin_centers = self._histogram_for_fit(data)
        bin_width = float(bin_centers[1] - bin_centers[0])

        popt, one_population, fit_method = self._fit_em_double_gaussian(
            data, bin_centers, bin_width
        )
        if popt is None:
            raise ValueError(
                "could not fit a two-component Student-t mixture to this data"
            )

        amp1, mean1, std1, amp2, mean2, std2 = (float(p) for p in popt)

        threshold, threshold_method, spline = self._threshold_between_populations(
            data, bin_centers, counts, mean1, std1, mean2, std2, one_population
        )

        # Retained under its own key so the plots can show the histogram-derived
        # valley alongside wherever the threshold ends up (see
        # `_overlay_valley_reference`) - the reference point for judging whether
        # moving to the equiprobability point below was reasonable.
        valley_threshold = threshold

        # Move the threshold to the point where the two fitted components are
        # equally likely, so the classification agrees with the mixture that
        # produced it and `_classification_confidence` cannot report a value
        # below 0.5 for a point between the two modes. Only meaningful when the
        # fit found two populations: with one, both centres sit on the same mode
        # and a crossing between them separates nothing - the same reason the
        # between-centres valley search is skipped (see
        # `_threshold_between_populations`). Used whenever it can be computed,
        # regardless of which method produced the histogram-derived threshold
        # above - `valley_threshold` is kept only as a reference point for the
        # plot (`_overlay_valley_reference`) and for the disagreement warning
        # below, never as a fallback value.
        if not one_population:
            equiprobable = self._threshold_at_equiprobability(
                (amp1, mean1, std1, amp2, mean2, std2), bin_centers
            )
            if equiprobable is not None:
                narrower_fwhm = 2.355 * min(std1, std2)
                if abs(equiprobable - valley_threshold) > narrower_fwhm:
                    self.logger.warning(
                        f"the equiprobability threshold ({equiprobable:.4g}) is "
                        f"{abs(equiprobable - valley_threshold):.4g} from the "
                        f"{threshold_method} threshold ({valley_threshold:.4g}), "
                        f"more than the {narrower_fwhm:.4g} FWHM of the narrower "
                        "component. The fitted components and the histogram's "
                        "own shape disagree about where the boundary is, which "
                        "usually means a component is poorly described by a "
                        "Gaussian; using the equiprobability threshold anyway."
                    )
                threshold = equiprobable
                threshold_method = "equiprobability"

        self._warn_if_fitted_means_are_off_their_peaks(
            bin_centers, counts, (amp1, mean1, std1, amp2, mean2, std2)
        )

        # Recomputed rather than threaded out of `_threshold_between_populations`,
        # so that method's return signature stays (threshold, method, spline). It
        # is a pure function of `bin_centers`/`counts`, already in hand here, so
        # recomputing it costs one more cumulative sum, not another fit.
        spline_bins, _ = self._trim_to_populated_core(bin_centers, counts)
        spline_domain = (
            (float(spline_bins[0]), float(spline_bins[-1]))
            if spline is not None and spline_bins.size >= 2
            else None
        )

        return {
            "threshold": threshold,
            "centers": np.array([mean1, mean2], dtype=float),
            "hist": (counts, bin_edges),
            "params": (amp1, mean1, std1, amp2, mean2, std2),
            "n_components": 1 if one_population else 2,
            "threshold_method": threshold_method,
            "spline": spline,
            "spline_domain": spline_domain,
            "fit_method": fit_method,
            "valley_threshold": valley_threshold,
        }

    def _trim_to_populated_core(
        self,
        bins: npt.NDArray[np.float64],
        amplitude: npt.NDArray[np.float64],
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Drop the near-empty edges of a histogram before it reaches the
        smoothing-spline machinery.

        ``_histogram_for_fit`` bins across the data's full range at a width
        set by the populated core's interquartile range, so a heavy-tailed
        dataset - a handful of outlier peaks spread over a range many times
        the width of the real population - ends up with most of its bins
        carrying 0 or 1 counts far past where any population actually sits.
        A single natural cubic smoothing spline is fit through every one of
        those bins, and no ``lam`` is quiet across that near-empty stretch
        and faithful to the sharp populated core at once: smoothed enough to
        flatten the empty tail's Poisson noise, it washes out the real peak;
        left alone, it dips and bulges in the near-empty region, unconstrained
        by any data there. Measured on a reconstruction of a real
        single-population prominence dataset, fitting across the full range
        left the curve as low as -44 counts and fabricated a peak over 250
        counts high where the raw histogram was within noise of zero;
        restricting the fit to the populated core removed both.

        Coverage is measured by cumulative count, not by an amplitude cutoff,
        because a long tail is made of many bins that can each individually
        clear an amplitude threshold while the stretch as a whole is still
        far sparser, per unit range, than the core - cumulative count is what
        actually measures how much of the data a run of bins represents.

        :param bins: histogram bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts, the same shape as ``bins``
        :type amplitude: npt.NDArray[np.float64]
        :return: ``(bins, amplitude)`` restricted to the contiguous span
            holding ``SPLINE_FIT_DOMAIN_COVERAGE`` of the total count, padded
            by a couple of bins on each side; returned unchanged if there are
            too few bins, no counts, or the trim would leave almost nothing
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
        """
        if bins.size < 4:
            return bins, amplitude
        total = float(np.sum(amplitude))
        if total <= 0:
            return bins, amplitude

        cumulative = np.cumsum(amplitude)
        tail_fraction = (1.0 - self.SPLINE_FIT_DOMAIN_COVERAGE) / 2.0
        lo_index = int(np.searchsorted(cumulative, total * tail_fraction))
        hi_index = int(np.searchsorted(cumulative, total * (1.0 - tail_fraction)))

        pad = 2
        lo_index = max(0, lo_index - pad)
        hi_index = min(bins.size - 1, hi_index + pad)
        if hi_index - lo_index < 3:
            return bins, amplitude
        return bins[lo_index : hi_index + 1], amplitude[lo_index : hi_index + 1]

    @log(logger=logger)
    def _fit_least_smoothed_spline(
        self,
        bins: npt.NDArray[np.float64],
        amplitude: npt.NDArray[np.float64],
        search_lo: float,
        search_hi: float,
    ) -> Optional[BSpline]:
        """
        Fit the *least*-smoothed spline that still shows at most
        ``SPLINE_MAX_MINIMA`` local minima between ``search_lo`` and
        ``search_hi``.

        ``make_smoothing_spline`` will select its own smoothing by generalized
        cross-validation if ``lam`` is not given, and that is not good enough
        here: GCV optimizes predictive error, not shape, and on counting data
        it reliably under-smooths, leaving spurious Poisson wiggles that the
        deepest-valley search below can return instead of the real boundary.

        **A fixed ``lam`` is not an option either, which is why this is a
        ladder rather than a constant.** ``make_smoothing_spline``
        minimizes ``sum(residuals**2) + lam * integral(f''**2)``, and since
        ``f''`` scales as (y-range)/(x-range)**2, the penalty term carries a
        factor of ``(y-range)**2 / (x-range)**3``. A ``lam`` tuned on one
        dataset is therefore meaningless on another with a different x-range -
        expressing it as ``lam = lam_shape * x_range**3`` removes that
        dependence, but even in that scale-free form no single ``lam_shape``
        works across every dataset: the band of values giving exactly one
        minimum differs by orders of magnitude between well-separated bimodal
        data and skewed data.

        The ladder sidesteps the whole question. It walks ``lam_shape`` upward
        in log-spaced steps from almost no smoothing and stops at the first
        value whose fitted curve is quiet enough, so it lands inside whatever
        band a given dataset has without that band ever being named. The count
        of local minima is a monotone non-increasing step function of
        ``lam_shape``, so the first acceptable candidate is also the
        least-smoothed one - which matters more than it may appear, because
        over-smoothing washes out the real valley just as surely as
        under-smoothing buries it in noise. See ``SPLINE_LAMBDA_MARGIN_STEPS``
        for the measurement showing that even two steps of "safety margin"
        past this point does substantially more harm than the noise it was
        meant to guard against.

        Accepting *at most* ``SPLINE_MAX_MINIMA`` rather than exactly that many
        is deliberate: zero minima is the correct and expected outcome on
        genuinely single-population data, where there is no valley to find and
        the caller falls through to its above-floor search.

        :param bins: histogram bin centers, as built for the mixture fit
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts, as built for the mixture fit
        :type amplitude: npt.NDArray[np.float64]
        :param search_lo: lower end of the bracket the caller will search for a
            valley, and so the bracket whose wiggles matter here
        :type search_lo: float
        :param search_hi: upper end of that bracket
        :type search_hi: float
        :return: the least-smoothed ``BSpline`` meeting the criterion, or None
            if the histogram is too small, the bracket is empty, or no
            candidate on the ladder was quiet enough - in which case the caller
            falls back to plain GCV
        :rtype: Optional[BSpline]
        """
        if bins.size < 4 or search_hi <= search_lo:
            return None
        x_range = float(bins[-1] - bins[0])
        if x_range <= 0:
            return None

        grid = np.linspace(search_lo, search_hi, 1000)
        shape_lambdas = np.logspace(
            np.log10(self.SPLINE_LAMBDA_SHAPE_MIN),
            np.log10(self.SPLINE_LAMBDA_SHAPE_MAX),
            self.SPLINE_LAMBDA_CANDIDATES,
        )

        chosen = None
        for index, lam_shape in enumerate(shape_lambdas):
            try:
                candidate = make_smoothing_spline(
                    bins, amplitude, lam=float(lam_shape) * x_range**3
                )
            except Exception:
                continue
            diffs = np.diff(candidate(grid))
            n_minima = int(np.sum((diffs[:-1] < 0) & (diffs[1:] > 0)))
            if n_minima <= self.SPLINE_MAX_MINIMA:
                chosen = index
                break

        if chosen is None:
            self.logger.debug(
                "no smoothing-spline lambda on the ladder brought the curve "
                f"down to {self.SPLINE_MAX_MINIMA} or fewer local minima "
                f"between {search_lo:.4g} and {search_hi:.4g}; falling back to "
                "generalized cross-validation."
            )
            return None

        lam_shape = float(
            shape_lambdas[
                min(
                    chosen + self.SPLINE_LAMBDA_MARGIN_STEPS,
                    self.SPLINE_LAMBDA_CANDIDATES - 1,
                )
            ]
        )
        self.logger.debug(
            f"smoothing-spline lambda ladder chose lam_shape={lam_shape:.4g} "
            f"(lam={lam_shape * x_range**3:.4g}) for the bracket "
            f"{search_lo:.4g}..{search_hi:.4g}."
        )
        try:
            return make_smoothing_spline(bins, amplitude, lam=lam_shape * x_range**3)
        except Exception as e:
            self.logger.debug(
                f"smoothing-spline refit at the chosen lambda failed: {e}",
                exc_info=True,
            )
            return None

    @log(logger=logger)
    def _threshold_between_populations(
        self,
        data: npt.NDArray[np.float64],
        bins: npt.NDArray[np.float64],
        amplitude: npt.NDArray[np.float64],
        mean1: float,
        std1: float,
        mean2: float,
        std2: float,
        one_population: bool,
    ) -> Tuple[float, str, Optional[BSpline]]:
        """
        Pick a threshold between two fitted populations from the histogram's
        shape, rather than the arithmetic midpoint of their fitted means.

        A smoothing spline (see ``_fit_least_smoothed_spline``, which chooses
        its smoothing) is fit to the populated core of the same histogram
        (``bins``, ``amplitude``, trimmed by ``_trim_to_populated_core``) the
        mixture fit used, and evaluated on a fine grid between the two fitted
        means. If that smoothed curve has a local minimum in between - an
        actual valley separating the two modes - the threshold is placed there
        (the deepest one, if more than one is found). The arithmetic midpoint
        ignores the histogram's shape entirely and sits there even when the
        true valley is well off-centre, e.g. because one population heavily
        outnumbers the other.

        **The between-centres search is skipped entirely when ``one_population``
        is set**, and this matters more than it sounds. On single-population data
        both fitted centres land on the same mode, so the bracket between them is
        narrow and contains no boundary between anything - but it is not empty.
        Beside a tall peak the spline wiggles on counting noise alone, and the
        search will happily return one of those wiggles. That is what produced a
        2045 pA threshold on a real 6261-peak dataset whose two centres were 1787
        and 2088: a 301 pA window either side of a single mode, and Poisson noise
        of about +/-21 counts on 450-count bins, which is ample to make a local
        minimum. Skipping the search is the fix; narrowing what counts as a valley
        would not be, because there is no correct answer inside that bracket.

        With the search skipped or unsuccessful, the threshold instead becomes the
        **first** local minimum of the same spline above the floor
        ``2 * mean1 - 2 * std1``, where ``mean1``/``std1`` here are whichever of
        the two fitted components has the lower mean (labelled ``mean1``/``std1``
        in this method's signature only by fit-parameter order, not by value).
        Only if there is no local minimum up there either does this fall back to
        the first raw data point above the floor, and finally to the midpoint of
        the two means.

        The fitted spline is returned alongside the threshold so the classifiers
        can draw it on their plots. It is fit whenever the histogram has enough
        bins, even when the valley search is then skipped or comes up empty, so
        that a plot showing a fallback threshold still shows the curve that
        failed to find a valley - which is the evidence for why the fallback was
        used.

        :param data: the raw 1-D data the histogram was built from
        :type data: npt.NDArray[np.float64]
        :param bins: histogram bin centers, as built for the mixture fit
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts, as built for the mixture fit
        :type amplitude: npt.NDArray[np.float64]
        :param mean1: mean of the first fitted component
        :type mean1: float
        :param std1: standard deviation of the first fitted component
        :type std1: float
        :param mean2: mean of the second fitted component
        :type mean2: float
        :param std2: standard deviation of the second fitted component
        :type std2: float
        :param one_population: True when the fit describes a single population,
            in which case the between-centres valley search is skipped because
            the bracket separates nothing and can only return spline noise
        :type one_population: bool
        :return: tuple of (threshold, method, spline), where method is
            ``"spline_valley"`` when a valley was found between the two centres,
            ``"spline_valley_above_floor"`` when there was none and the first
            local minimum above ``2 * mean - 2 * std`` was used instead,
            ``"fallback"`` when even that was unavailable and the first data
            point above that floor was used, or ``"fallback_degenerate"`` on the
            last-resort case where no data point clears the floor either, and
            spline is the fitted smoothing spline over the populated core of
            ``bins`` (see ``_trim_to_populated_core``), or None if it could not
            be fit
        :rtype: Tuple[float, str, Optional[BSpline]]
        """
        if mean1 <= mean2:
            lower_mean, lower_std, higher_mean = mean1, std1, mean2
        else:
            lower_mean, lower_std, higher_mean = mean2, std2, mean1

        fallback_floor = 2.0 * lower_mean - 2.0 * lower_std

        # Trim to the populated core before this histogram goes anywhere near
        # the spline: see `_trim_to_populated_core` for why a heavy sparse
        # tail makes the untrimmed full range unfittable by a single spline.
        spline_bins, spline_amplitude = self._trim_to_populated_core(bins, amplitude)

        # Fit the spline first and unconditionally, so it is available to the
        # plots even on the paths below that do not (or cannot) use it to place
        # the threshold.
        #
        # The lambda ladder is aimed at whichever bracket is actually about to
        # be searched below - between the two centres normally, above the floor
        # when this is single-population data and that search is skipped - since
        # what matters is that the curve is quiet where a valley will be looked
        # for, not that it is quiet everywhere.
        spline: Optional[BSpline] = None
        if spline_bins.size >= 4:
            if not one_population and higher_mean > lower_mean:
                search_lo, search_hi = lower_mean, higher_mean
            else:
                search_lo = max(fallback_floor, float(spline_bins[0]))
                search_hi = float(spline_bins[-1])
            try:
                spline = self._fit_least_smoothed_spline(
                    spline_bins, spline_amplitude, search_lo, search_hi
                )
                if spline is None:
                    # The ladder declined; generalized cross-validation is
                    # still better than no curve at all, for the plot if
                    # nothing else.
                    spline = make_smoothing_spline(spline_bins, spline_amplitude)
            except Exception as e:
                self.logger.debug(
                    "threshold spline fit failed, falling back to the "
                    f"2*mean-2*std floor: {e}",
                    exc_info=True,
                )

        if spline is not None and not one_population and higher_mean > lower_mean:
            grid = np.linspace(lower_mean, higher_mean, 1000)
            values = spline(grid)
            # A local minimum at grid index i (1 <= i <= len(grid)-2): the
            # curve is falling into it from the left and rising out of it
            # to the right. Using the sign of consecutive differences
            # rather than e.g. `scipy.signal.argrelmin` tolerates a short
            # flat run at the bottom of a shallow valley, which a strict
            # less-than-both-neighbours test would miss entirely.
            diffs = np.diff(values)
            valley_idx = np.where((diffs[:-1] < 0) & (diffs[1:] > 0))[0] + 1
            if valley_idx.size > 0:
                deepest = valley_idx[np.argmin(values[valley_idx])]
                return float(grid[deepest]), "spline_valley", spline

        # No valley between the two centres. That is the normal outcome on
        # single-population data, where both fitted centres sit on the same mode
        # and the bracket above is too narrow to contain anything - so there is
        # still a threshold to find, just not between the means. Look for the
        # first local minimum of the same spline *above* the floor instead.
        #
        # The FIRST such minimum, not the deepest. Past the bulk of the data the
        # spline is fitting counting noise on near-empty bins, so it wiggles,
        # and every wiggle is a local minimum: on a real 6261-peak dataset there
        # were 43 local minima in total and 30 of them above the floor, the
        # deepest sitting at 5165 pA with a spline value of -0.29 - i.e. out in
        # the noise, below zero counts, cutting off 0.7% of the data. The first
        # one above the floor landed at 3414 pA against a floor of 3262, which
        # is the boundary the floor was pointing at.
        if spline is not None and float(spline_bins[-1]) > fallback_floor:
            grid = np.linspace(
                max(fallback_floor, float(spline_bins[0])),
                float(spline_bins[-1]),
                2000,
            )
            values = spline(grid)
            diffs = np.diff(values)
            above_idx = np.where((diffs[:-1] < 0) & (diffs[1:] > 0))[0] + 1
            if above_idx.size > 0:
                return (
                    float(grid[above_idx[0]]),
                    "spline_valley_above_floor",
                    spline,
                )

        sorted_data = np.sort(np.asarray(data, dtype=float).ravel())
        above_floor = sorted_data[sorted_data > fallback_floor]
        if above_floor.size > 0:
            return float(above_floor[0]), "fallback", spline

        self.logger.warning(
            "threshold fallback: no data point exceeds 2*mean-2*std "
            f"({fallback_floor:.4g}); using the midpoint between the two "
            "fitted means as a last resort."
        )
        return float((mean1 + mean2) / 2.0), "fallback_degenerate", spline

    @log(logger=logger)
    def _classification_confidence(
        self,
        values: npt.NDArray[np.float64],
        params: Tuple[float, float, float, float, float, float],
        is_higher_class: npt.NDArray[np.bool_],
    ) -> npt.NDArray[np.float64]:
        """
        Score how confidently each value was assigned to its threshold-derived class.

        ``fit_threshold`` reports ``(amp1, mean1, std1, amp2, mean2, std2)`` on
        histogram-count scale (see ``_fit_em_double_gaussian``): each fitted
        curve ``amp_k * exp(-(x-mean_k)**2 / (2*std_k**2))`` is already the
        expected bin count contributed by population k at x - amplitude has
        absorbed both the population size and the ``1/(std*sqrt(2*pi))``
        normalization a proper mixture weight would otherwise need. That means
        the usual Gaussian-mixture posterior ("responsibility") falls out of
        the reported parameters directly, with no re-fitting and no extra
        weighting step:

        ``confidence(x) = g_assigned(x) / (g_low(x) + g_high(x))``

        where ``g_low``/``g_high`` are the two fitted curves ordered by mean
        and ``g_assigned`` is whichever of the two matches the class the
        caller already assigned by thresholding ``values`` (``is_higher_class``
        records that assignment so this method does not need to know
        ``fit_threshold``'s own threshold value).

        This is a relative/ordinal score, not a calibrated probability: even a
        Student-t component is scored here through its reported ``(amp, mean,
        std)`` as if it were symmetric-Gaussian, so on a population that is
        itself skewed it will read as overconfident approaching that skewed
        shoulder. Whether it crosses 0.5 exactly at ``fit_threshold``'s own
        threshold depends on ``"threshold_method"``: on two-population data the
        threshold is moved to the equiprobability point (see
        ``_threshold_at_equiprobability``) whenever that point can be
        computed, and the two then coincide by construction; on the rare
        two-population fit where it could not be computed, or on
        single-population data where it is never attempted,
        ``"threshold_method"`` stays one of ``_threshold_between_populations``'s
        histogram-derived methods and the two can legitimately differ, with a
        handful of points just past the threshold scoring below 0.5. That
        disagreement is informative rather than a bug: it is the same signal
        ``_overlay_valley_reference`` draws, when there is a valley threshold
        to compare against at all.

        :param values: the 1-D data that was thresholded to produce
            ``is_higher_class``
        :type values: npt.NDArray[np.float64]
        :param params: the six fitted parameters from
            ``fit_threshold``'s ``"params"`` - ``(amp1, mean1, std1, amp2,
            mean2, std2)``, not necessarily ordered lower-then-higher
        :type params: Tuple[float, float, float, float, float, float]
        :param is_higher_class: boolean array, same length as ``values``,
            True where the caller assigned the higher-mean class (i.e.
            ``values >= threshold``)
        :type is_higher_class: npt.NDArray[np.bool_]
        :return: array of confidence scores in (0, 1], same length as
            ``values``; 1.0 wherever both fitted curves numerically underflow
            to zero, since a point that far from both means is unambiguously
            not in the overlap between them
        :rtype: npt.NDArray[np.float64]
        """
        amp1, mean1, std1, amp2, mean2, std2 = params
        values = np.asarray(values, dtype=float)

        g1 = amp1 * np.exp(-((values - mean1) ** 2) / (2 * std1**2))
        g2 = amp2 * np.exp(-((values - mean2) ** 2) / (2 * std2**2))

        if mean1 <= mean2:
            g_low, g_high = g1, g2
        else:
            g_low, g_high = g2, g1

        g_assigned = np.where(is_higher_class, g_high, g_low)
        total = g_low + g_high

        with np.errstate(invalid="ignore", divide="ignore"):
            confidence = np.where(total > 0, g_assigned / total, 1.0)

        return np.asarray(confidence, dtype=np.float64)

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
        peaks: npt.NDArray[np.intp],
        properties: Dict[str, Any],
        unfolded_level: float,
        folded_level: Optional[float],
        baseline_std: Optional[float],
        baseline: Optional[float],
        samplerate: float,
        event_length: int,
    ) -> Dict[str, Any]:
        """
        Filters peaks based on their level and proximity, classifying potential bundles or barcode features.
        - Type 1: Peaks on the same DNA carrier level (both bases around unfolded_level).
        - Type 2: Peaks higher than the carrier level (both bases above unfolded_level).
        - Type 3: Clusters (bundles) of close peaks with same type (1).

        :param peaks: indices of the located peaks, as returned by scipy.signal.find_peaks
        :type peaks: npt.NDArray[np.intp]
        :param properties: the peak properties dict returned alongside the peak indices
        :type properties: Dict[str, Any]
        :param unfolded_level: the blockage level of the unfolded carrier
        :type unfolded_level: float
        :param folded_level: the blockage level of the folded carrier, if one is known
        :type folded_level: Optional[float]
        :param baseline_std: the local standard deviation of the baseline current
        :type baseline_std: Optional[float]
        :param baseline: the local mean value of the baseline current
        :type baseline: Optional[float]
        :param samplerate: the sampling rate
        :type samplerate: float
        :param event_length: the length of the event
        :type event_length: int
        :return: the properties dict, with its "filtered" entry updated with peak classifications
        :rtype: Dict[str, Any]
        :raises RuntimeError: if baseline_std is None, since it scales every classification threshold
        """
        # NOTE (integration): this docstring previously sat *below* the four
        # statements that follow, which meant Python treated it as a no-op string
        # expression rather than a docstring - a docstring has to be the very first
        # statement in the function. That is why test_plugin_compliance.py reported
        # "missing docstrings: ['filter_peaks', 'redefine_padding']". Moved it up to
        # the first position and added the :param:/:rtype: fields pydoclint requires;
        # no logic was changed.
        # NOTE (integration): baseline_std is Optional under the MetaEventFitter
        # contract but was used unguarded in every threshold expression below, so an
        # event loader supplying no baseline estimate raised TypeError part-way through
        # classification. Checked once here and raised explicitly instead.
        if baseline_std is None:
            raise RuntimeError(
                "filter_peaks requires a baseline standard deviation to set its "
                "classification thresholds; the event loader supplied None"
            )

        # Defining variables and thresholds
        t1_std = int(self.settings["Lower Filter Threshold"]["Value"])
        t2_std = int(self.settings["Higher Filter Threshold"]["Value"])

        # event_id = getattr(self, "_debug_event_id", None
        num_peaks = self.settings["Number of peaks"]["Value"]
        filtered = properties["filtered"]

        # BARCODE
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
                if left_base <= type0_thresh and right_base <= type0_thresh:
                    filtered[i] = 0
                # Type -1: both bases above the upper type-2 cutoff (noise)
                elif (
                    left_base >= type2_thresh + unfolded_level
                    and right_base >= type2_thresh + unfolded_level
                ):
                    filtered[i] = -1
                #    print(f"[debug] event_id={event_id}, peak {i} assigned -1 (both bases >= type2_upper)")
                # Type 2: both bases within the type-2 band around 2*unfolded_level
                elif (
                    left_base >= type2_thresh
                    and right_base >= type2_thresh
                    and left_base <= type2_thresh + unfolded_level
                    and right_base <= type2_thresh + unfolded_level
                ):
                    filtered[i] = 2
                #    print(f"[debug] event_id={event_id}, peak {i} assigned 2 (both bases in type2 band)")
                # Type 1: both bases within the type-1 band around unfolded_level
                elif (
                    left_base >= type1_thresh
                    and right_base >= type1_thresh
                    and left_base <= type2_thresh
                    and right_base <= type2_thresh
                ):
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
            prom_indices = np.argsort(properties["prominences"])[
                ::-1
            ]  # all sorted by prominence
            best_cluster = []
            best_prom_sum = 0

            for label in [1]:
                label_idxs = [i for i in prom_indices if filtered[i] == label]
                if not label_idxs:
                    continue
                label_idxs = label_idxs[
                    :num_peaks
                ]  # only consider the top N most prominent peaks for clustering
                sorted_idxs = sorted(label_idxs, key=lambda i: peaks[i])

                # Find clusters where consecutive peaks (temporally, not prominence wise) are within max_distance
                for i in range(len(sorted_idxs)):
                    group = [sorted_idxs[i]]

                    # Add consecutive peaks that are close enough
                    for j in range(i + 1, len(sorted_idxs)):
                        # Check distance between consecutive peaks in the group
                        prev_peak_idx = group[-1]
                        curr_peak_idx = sorted_idxs[j]
                        distance = abs(
                            properties["peak_loc"][curr_peak_idx]
                            - properties["peak_loc"][prev_peak_idx]
                        )

                        if distance <= max_distance:
                            group.append(curr_peak_idx)
                        else:
                            # Stop when we find a gap larger than max_distance
                            break

                    group = group[:num_peaks]

                    # Check if this group is large enough and has higher total prominence
                    if len(group) >= min_group_size:
                        prom_sum = sum(properties["prominences"][idx] for idx in group)

                        if prom_sum > best_prom_sum:
                            best_cluster = group
                            best_prom_sum = prom_sum

                        break  # only break if a valid cluster was found

                # Recheck adjacency inside best_cluster before labeling
                validated_cluster = []
                best_cluster_sorted = sorted(best_cluster, key=lambda idx: peaks[idx])

                for i, idx in enumerate(best_cluster_sorted):
                    if i == 0:
                        validated_cluster.append(idx)
                        continue

                    prev_idx = validated_cluster[-1]
                    distance = abs(
                        properties["peak_loc"][idx] - properties["peak_loc"][prev_idx]
                    )

                    if distance <= max_distance:
                        validated_cluster.append(idx)
                    else:
                        # break or continue depending on desired behavior
                        continue

                # Only label validated peaks as type 3
                for idx in validated_cluster:
                    filtered[idx] = 3

            # Persist filtered labels back to properties
            properties["filtered"] = list(filtered.tolist())

        # SINGLE PEAK CARRIER
        if self.settings["Event Type"]["Value"] == "Single Peak":

            unfolded_lower_bound = (
                # NOTE: baseline_std is Optional under the MetaEventFitter contract and is used here without a guard. Flagged, not fixed - the logic in this plugin belongs to its owner.
                (unfolded_level + t1_std * baseline_std)
                if unfolded_level is not None
                else 0
            )
            unfolded_upper_bound = (
                (unfolded_level + t2_std * baseline_std)
                if unfolded_level is not None
                else 0
            )

            folded_lower_bound = (
                (folded_level - t1_std * baseline_std)
                if folded_level is not None
                else 0
            )
            folded_upper_bound = (
                (folded_level + t2_std * baseline_std)
                if folded_level is not None
                else 0
            )

            classified_peaks = []
            for i in range(len(peaks)):
                left_base = properties["left_bases"][i] + np.sign(baseline) * baseline
                right_base = properties["right_bases"][i] + np.sign(baseline) * baseline
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
        filtered_counts: Dict[int, int] = {}
        for f in filtered:
            filtered_counts[f] = filtered_counts.get(f, 0) + 1
        self.logger.debug(
            f"filter_peaks: Event Type={self.settings['Event Type']['Value']}, classified {len(peaks)} peaks: {filtered_counts}"
        )

        return properties

    # utility functions

    @log(logger=logger)
    def find_mode_blockage_level(
        self,
        data: npt.NDArray[np.float64],
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract the most populated blockage level from the data.

        Uses numpy histogram to find the most common current level.
        Data should already be trimmed to the longest continuous segment above threshold
        by _locate_sublevel_transitions. Folded/unfolded classification is deferred
        to post-processing across all events.

        :param data: Array of current values (already trimmed to longest segment).
        :type data: npt.NDArray[np.float64]
        :param baseline_mean: Mean value of the baseline level.
        :type baseline_mean: Optional[float]
        :param baseline_std: Standard deviation of the baseline level.
        :type baseline_std: Optional[float]
        :return: Tuple of (primary_blockage_level, secondary_blockage_level) - the 2 most populated distinct blockage levels
        :rtype: Tuple[Optional[float], Optional[float]]
        :raises RuntimeError: if baseline_mean is None, since blockage levels are measured relative to the baseline
        """
        # Data is already trimmed to longest segment in _locate_sublevel_transitions
        # Find the 2 most populated levels using histogram

        arr = np.asarray(data)
        if arr.size == 0:
            return None, None

        # NOTE (integration): baseline_mean is Optional under the MetaEventFitter
        # contract but was used unguarded in the two np.abs() expressions at the end of
        # this method, so an event loader that supplies no baseline estimate produced a
        # TypeError from inside numpy rather than a diagnosable error. Checked up front
        # and raised explicitly instead.
        if baseline_mean is None:
            raise RuntimeError(
                "find_mode_blockage_level requires a baseline mean; the event loader "
                "supplied None, so blockage levels cannot be referenced to a baseline"
            )

        # Fast histogram-based level detection using numpy
        # Prefer bins based on baseline noise when possible, but fall back to 'auto'
        # NOTE (integration): this was float(baseline_std) inside a bare
        # `except Exception`, which meant a None baseline_std was indistinguishable
        # from a genuine conversion failure. baseline_std is legitimately Optional
        # here, so the None case now selects the 'auto' binning path explicitly.
        if baseline_std is None:
            bin_width = 0.0
        else:
            bin_width = float(baseline_std) / 8.0

        min_val = float(np.min(arr))
        max_val = float(np.max(arr))

        if bin_width > 0 and max_val > min_val:
            # Safe arange only when bin_width is positive
            try:
                bins = np.arange(
                    min_val - bin_width / 2.0, max_val + bin_width, bin_width
                )
                if bins.size < 2:
                    # Fallback
                    bins = "auto"
            except Exception:
                bins = "auto"
        else:
            bins = "auto"

        # Get histogram counts and bin centers
        counts, bin_edges = np.histogram(arr, bins=bins)
        if len(bin_edges) < 2:
            return None, None
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
        self,
        sublevel_starts: List[Dict[str, Any]],
        num_states: int,
        sublevel_types: Optional[List[str]] = None,
    ) -> List[Optional[int]]:
        """
        :param sublevel_starts: List of dictionaries describing sublevels, each with a 'type' key.
        :type sublevel_starts: List[Dict[str, Any]]
        :param num_states: Total number of sublevels to process.
        :type num_states: int
        :param sublevel_types: List of sublevel types ('peak' or 'event_baseline'). If None, falls back to edge type checking.
        :type sublevel_types: Optional[List[str]]
        :return: List of peak IDs or None for non-peak sublevels.
        :rtype: List[Optional[int]]
        """
        j = 1
        id: list[int | None] = []
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
