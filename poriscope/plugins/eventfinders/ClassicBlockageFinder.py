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
from typing import Any, Dict, List, Optional, Tuple, override

import numpy as np
import numpy.typing as npt
from fast_histogram import histogram1d

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventFinder import MetaEventFinder


@inherit_docstrings
class ClassicBlockageFinder(MetaEventFinder):
    """
    Event finder plugin for detecting transient blockages in nanopore signals using a threshold-based approach.

    This subclass of MetaEventFinder implements a classic event detection strategy, where events are identified
    by thresholding rectified signal traces. The start and end of events are determined using hysteresis and
    configurable settings such as threshold, minimum/maximum duration, and minimum separation.

    Core features:
    - Event detection based on baseline-normalized threshold crossings.
    - Configurable minimum and maximum event durations and separation.
    - Histogram-based baseline estimation with optional Gaussian fitting.
    - Supports chunked data processing with entry state handling across segments.

    Required settings:
    - Threshold (in pA)
    - Min Duration (in µs)
    - Max Duration (in µs)
    - Min Separation (in µs)
    - MetaReader reference for data access

    This class can be extended (e.g., BoundedBlockageFinder) to impose additional constraints such as baseline range limits.
    """

    logger = logging.getLogger(__name__)

    # public API, must be overridden by subclasses:

    @log(logger=logger)
    @override
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit

        :param channel: the channel identifier
        :type channel: Optional[int]
        """
        pass

    @log(logger=logger)
    @override
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Type is required; Value may be omitted or set to None, both meaning there is no default and the user must supply one. All values provided must be consistent with Type.
        EventFinder objects MUST include a MetaReader object in settings

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
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        settings["Threshold"] = {
            "Type": float,
            "Value": None,
            "Min": 0.0,
            "Units": "pA",
        }
        settings["Min Duration"] = {
            "Type": float,
            "Value": 0.0,
            "Min": 0.0,
            "Units": "us",
        }
        settings["Max Duration"] = {
            "Type": float,
            "Value": 1000000.0,
            "Min": 0.0,
            "Units": "us",
        }
        settings["Min Separation"] = {
            "Type": float,
            "Value": 0.0,
            "Min": 0.0,
            "Units": "us",
        }
        return settings

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        called at the start of base class initialization
        """
        pass

    # private API, MUST be implemented by subclasses
    @log(logger=logger)
    @override
    def _find_events_in_chunk(
        self,
        data: npt.NDArray[np.float64],
        mean: float,
        std: float,
        offset: int,
        entry_state: bool = False,
        first_chunk: bool = False,
    ) -> Tuple[List[int], List[int], bool]:
        """
        Find the start and end points of events in the provided chunk of data and returns them as separate lists,
        along with a boolean indicating whether or not the chunk ended in the middle of an event.
        Should backtrack data to the baseline, since padding logic will assume that it can use data right up to the start and end found as baseline by default

        :param data: Chunk of timeseries data to analyze. Assume it is rectified so that a blockage will always represent a reduction in absolute value.
        :type data: npt.NDArray[np.float64]
        :param mean: Mean of the baseline on the given chunk. Must be positive.
        :type mean: float
        :param std: Standard deviation of the baseline on the given chunk
        :type std: float
        :param offset: the index of the start of the chunk in the global dataset
        :type offset: int
        :param entry_state: Bool indicating whether we start in the middle of an event (True) or not (False)
        :type entry_state: bool
        :param first_chunk: Bool indicating whether this is the first chunk of data in the series to be analyzed
        :type first_chunk: bool
        :raises ValueError: If event_params are invalid.
        :return: Lists of event start and end indices, and boolean entry state.
        :rtype: Tuple[List[int], List[int], bool]
        """
        if np.sign(mean) < 0:
            raise ValueError("Data must be rectifed for event finding")

        data -= mean
        data /= std

        threshold = -self.settings["Threshold"]["Value"] / std
        hysteresis = 1
        event_starts = []
        event_ends = []

        if (
            data[0] < threshold and first_chunk and not entry_state
        ):  # do not count an event that straddles the start of the first chunk
            entry_state = True

        index = 0
        prev_index = 0
        len_data = len(data)

        while index < len_data:
            if not entry_state:  # we are not in an event
                pos = int(np.argmax(data[index:] < threshold))
                if pos == 0 and not (data[index] < threshold):
                    break
                index += pos
                event_start = index
                while (
                    data[event_start] < hysteresis and event_start > prev_index
                ):  # backtrack from the threshold crossing into the baseline to estimate event start point
                    event_start -= 1
                entry_state = True
                event_starts.append(event_start + offset)
            else:
                pos = int(np.argmax(data[index:] > hysteresis))
                if pos == 0 and not (data[index] > hysteresis):
                    break
                index += pos  # no backtracking needed here
                event_ends.append(index + offset)
                entry_state = False
            prev_index = index
        return event_starts, event_ends, entry_state

    @log(logger=logger)
    @override
    def _filter_events(
        self,
        event_starts: List[int],
        event_ends: List[int],
        channel: int,
        last_end: int = 0,
    ) -> Tuple[List[int], List[str]]:
        """
        Remove entries from self.event_starts and self.event_ends list based on any filter criteria defined in user settings

        :param event_starts: a list of starting data indices for events. You may assume that event_starts[0] < event_ends[0]. It is possible that there will be one more entry in this list than in event_ends.
        :type event_starts: List[int]
        :param event_ends: a list of ending data indices for events. You may assume that event_starts[0] < event_ends[0]
        :type event_ends: List[int]
        :param channel: The channel index being processed. Unused by this implementation.
        :type channel: int
        :param last_end: the index of the end of the last accepted event
        :type last_end: int
        :return:  A list of indices to reject from the given list of event starts and ends, and a list of reason for rejection
        :rtype: Tuple[List[int], List[str]]
        :raises RuntimeError: if no reader plugin has been set on this event finder
        """
        # Not an assert: asserts are stripped under python -O, which would turn a
        # missing reader into an opaque AttributeError on the next line. MetaEventFinder
        # guards the same Optional attribute this way at lines 143 and 203.
        if self.reader is None:
            raise RuntimeError("Reader is not set")
        samplerate = self.reader.get_samplerate()

        min_duration = self.settings["Min Duration"]["Value"] * samplerate * 1e-6
        max_duration = self.settings["Max Duration"]["Value"] * samplerate * 1e-6
        min_separation = self.settings["Min Separation"]["Value"] * samplerate * 1e-6

        bad_indices = []
        reasons = []
        for idx, (start, end) in enumerate(zip(event_starts, event_ends)):
            duration = end - start
            separation = start - last_end
            last_end = end
            if separation < min_separation:
                bad_indices.append(idx)
                reasons.append("Too Close")
            elif duration < min_duration:
                bad_indices.append(idx)
                reasons.append("Too Short")
            elif duration > max_duration:
                bad_indices.append(idx)
                reasons.append("Too Long")
        return bad_indices, reasons

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises KeyError: If the settings dict does not contain the correct information.
        """
        if "Threshold" not in settings.keys():
            raise KeyError(
                """Settings must include a 'Treshold' key with value equal to the number of baseline standard deviations at which to call the start of an event"""
            )
        if "MetaReader" not in settings.keys():
            raise KeyError(
                """Settings must include a 'MetaReader' with a value equal to an object comformant to the MetaReader interface"""
            )

    @log(logger=logger)
    @override
    def _get_baseline_stats(self, data: npt.NDArray[np.float64]) -> tuple[float, float]:
        """
        Get the local mean and standard deviation for a chunk of data. Assumes data is rectified.


        :param data: Chunk of timeseries data to compute statistics on.
        :type data: npt.NDArray[np.float64]
        :return: Tuple of mean and standard deviation of the baseline.
        :rtype: tuple[float, float]
        :raises ValueError: if a baseline histogram width cannot be estimated for this chunk (no variation in the data)
        """
        top = np.max(data)
        bottom = np.min(data)

        width = 2 * (top - bottom) / len(data) ** (1 / 3)
        if width <= 0:
            raise ValueError(
                "Unable to estimate a baseline histogram width for this chunk (no variation in the data)"
            )
        bins = int((top - bottom) / width)
        hist = histogram1d(data, range=[bottom, top], bins=bins)
        centers = np.linspace(bottom, top, len(hist))
        max_index = np.argmax(hist)

        maxval = hist[max_index]
        # top_index: the first index where hist[i] <= maxval/5 starting from max_index
        try:
            top_index = next(
                i for i in range(max_index, len(hist)) if hist[i] <= maxval / 5
            )
        except StopIteration:
            top_index = len(hist) - 1

        # bottom_index: the first index where hist[i] <= maxval/5 going backwards from max_index
        try:
            bottom_index = next(
                i for i in range(max_index, -1, -1) if hist[i] <= maxval / 5
            )
        except StopIteration:
            bottom_index = 0

        half_width = np.minimum(top_index - max_index, max_index - bottom_index)
        top_index = max_index + half_width
        bottom_index = max_index - half_width

        top = centers[top_index]
        bottom = centers[bottom_index]

        mask = (data > bottom) & (data < top)
        data = data[mask]

        hist = hist[bottom_index:top_index]
        centers = centers[bottom_index:top_index]

        max_index = np.argmax(hist)
        maxval = hist[max_index]

        # top_index: the first index where hist[i] <= 0.6*maxval starting from max_index
        try:
            top_index = next(
                i for i in range(max_index, len(hist)) if hist[i] <= 0.6 * maxval
            )
        except StopIteration:
            top_index = len(hist) - 1

        # bottom_index: the first index where hist[i] <= 0.6*maxval going backwards from max_index
        try:
            bottom_index = next(
                i for i in range(max_index, -1, -1) if hist[i] <= 0.6 * maxval
            )
        except StopIteration:
            bottom_index = 0

        try:
            _, mean, std = np.array(
                self._gaussian_fit(
                    hist,
                    centers,
                    centers[max_index],
                    np.absolute(centers[top_index] - centers[bottom_index]),
                )
            )
        except ValueError:
            raise
        return mean, std

    # Utility functions, specific to subclasses as needed

    # Utility functions, specific to subclasses as needed
    @log(logger=logger)
    def _gaussian(self, x: float, A: float, m: float, s: float) -> float:
        """
        Evaluate a Gaussian function at a given point.

        :param x: Input value at which to evaluate the function.
        :type x: float
        :param A: Amplitude of the Gaussian.
        :type A: float
        :param m: Mean (center) of the Gaussian.
        :type m: float
        :param s: Standard deviation (spread) of the Gaussian.
        :type s: float
        :return: Value of the Gaussian function at x.
        :rtype: float
        """
        return A * np.exp(-((x - m) ** 2) / (2 * s**2))

    @log(logger=logger)
    def _gaussian_fit(
        self,
        histogram: npt.NDArray[np.float64],
        bins: npt.NDArray[np.float64],
        mean_guess: float,
        stdev_guess: float,
    ) -> tuple[float, float, float]:
        """
        Fit a Gaussian function to histogram data using a linearized least squares approach.

        :param histogram: Array of counts in each histogram bin.
        :type histogram: npt.NDArray[np.float64]
        :param bins: Center positions of histogram bins.
        :type bins: npt.NDArray[np.float64]
        :param mean_guess: Initial estimate of the Gaussian mean.
        :type mean_guess: float
        :param stdev_guess: Initial estimate of the Gaussian standard deviation.
        :type stdev_guess: float
        :return: Tuple containing (amplitude, mean, standard deviation) of the fitted Gaussian.
        :rtype: tuple[float, float, float]
        :raises ValueError: If standard deviation guess is invalid or the fit fails.
        """
        if stdev_guess <= 0:
            raise ValueError("Invalid standard deviation guess")

        amp = np.max(histogram)
        max_loc = int(np.argmax(histogram))

        # Clean Windowing: A gaussian drops to ~1.1% height at 3 standard deviations.
        threshold = np.exp(-4.5) * amp

        # --- CONTIGUOUS MASKING LOGIC ---
        # Walk left from the peak until we hit the threshold or the array edge
        left_bound = max_loc
        while left_bound > 0 and histogram[left_bound - 1] > threshold:
            left_bound -= 1

        # Walk right from the peak until we hit the threshold or the array edge
        right_bound = max_loc
        while (
            right_bound < len(histogram) - 1 and histogram[right_bound + 1] > threshold
        ):
            right_bound += 1

        # Slice the arrays using the exclusive right bound
        y_slice = histogram[left_bound : right_bound + 1]
        x_slice = bins[left_bound : right_bound + 1]

        localy = y_slice / amp
        localx = (x_slice - mean_guess) / stdev_guess

        # Vectorized Matrix Math
        x0 = localy
        x1 = localx * x0
        x2 = localx * x1
        x3 = localx * x2
        x4 = localx * x3

        x0_sum = np.sum(x0)
        x1_sum = np.sum(x1)
        x2_sum = np.sum(x2)
        x3_sum = np.sum(x3)
        x4_sum = np.sum(x4)

        # localy is strictly > 0 because of the threshold mask, so log is safe
        lny = np.log(localy) * localy
        xlny = localx * lny
        x2lny = localx * xlny

        lny_sum = np.sum(lny)
        xlny_sum = np.sum(xlny)
        x2lny_sum = np.sum(x2lny)

        xTx = np.array(
            [
                [x4_sum, x3_sum, x2_sum],
                [x3_sum, x2_sum, x1_sum],
                [x2_sum, x1_sum, x0_sum],
            ]
        )

        xnlny = np.array([x2lny_sum, xlny_sum, lny_sum])
        xTxinv = np.linalg.inv(xTx)
        params = np.dot(xTxinv, xnlny)

        if params[0] >= 0:
            raise ValueError("Unable to estimate standard deviation (inverted fit)")

        stdev = np.sqrt(-1.0 / (2 * params[0]))

        # 'mean_offset' here is the shift in standardized units (mlocal)
        mean_offset = stdev**2 * params[1]
        amplitude = np.exp(params[2] + mean_offset**2 / (2 * stdev**2))

        # --- THE CRITICAL MATH FIX ---
        stdev *= stdev_guess
        mean = (mean_offset * stdev_guess) + mean_guess  # The missing multiplier
        amplitude *= amp
        return amplitude, mean, np.absolute(stdev)
