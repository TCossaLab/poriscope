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
from typing import Any, Dict, List, Optional, Type, Union, override

import numpy as np
import numpy.typing as npt

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

    #: The band, in sigmas, that decides where an edge is: a sample more than this many
    #: local baseline sigmas from the baseline mean is off the baseline, and a sample that
    #: differs from its neighbour by more than this many sigmas of the data's own first
    #: differences is still on an edge. Three keeps a noise excursion from being taken for
    #: an edge (0.13% of samples on Gaussian noise) while every edge a finder would report
    #: exceeds it.
    EDGE_BAND_SIGMA: float = 3.0
    #: How many consecutive off-baseline samples make a departure sustained. One or two
    #: samples past the band is noise; an edge stays past it until the return.
    EDGE_RUN_SAMPLES: int = 3

    # public API, must be overridden by subclasses:
    @log(logger=logger)
    @override
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Declare the settings this event fitter exposes, on top of the base contract.

        Called by poriscope when the plugin is instantiated or reconfigured, to build
        the settings dialog and to sanity-check whatever the user enters; the accepted
        values are then readable through ``self.settings``. See
        :py:meth:`~poriscope.utils.MetaEventFitter.MetaEventFitter.get_empty_settings`
        for the structure of the dict and what ``Type``, ``Value``, ``Min``, ``Max``, ``Options`` and
        ``Units`` mean in it, and for the reserved keys the GUI builds file pickers
        from.

        The ``super()`` call supplies the mandatory ``"MetaEventLoader"`` key, which is how
        this plugin is wired to its data source.

        The keys this plugin adds:

        - None. This fitter deliberately adds no settings: it records each event as a
          single sublevel so that events can be written to a database without a fit
          being imposed on them, which is what makes it the baseline case the other
          fitters are compared against.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaEventLoader" as a key, with explicitly set Type MetaEventLoader.
        :type globally_available_plugins: Optional[ Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        return settings

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
    def construct_fitted_event(  ##TODO
        self, channel: int, index: int
    ) -> Optional[npt.NDArray[np.float64]]:
        """
        Construct an array of data corresponding to the fit for the specified event

        :param channel: analyze only events from this channel
        :type channel: int
        :param index: the index of the target event
        :type index: int

        :return: numpy array of fitted data for the event, or None if fitting is not complete or the event was rejected
        :rtype: Optional[npt.NDArray[np.float64]]
        :raises AttributeError: if this instance is not linked to a MetaEventLoader
        """
        if self.sublevel_metadata == {} or not self.eventfitting_status.get(channel):
            self.logger.info(
                f"Fitting is not complete in channel {channel}, fit events first"
            )
            return None
        try:
            if self.eventloader is None:
                raise AttributeError(
                    "NoFitter cannot operate without a linked MetaEventLoader"
                )
            # Each stored entry is (edge, statistics start, statistics end); only the
            # edge matters here.
            sublevel_start_indices = [
                entry[0] for entry in self.sublevel_starts[channel][index]
            ]
            sublevel_end_indices = sublevel_start_indices[1:]
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
        data: npt.NDArray[np.float64],
        samplerate: float,
        padding_before: Optional[int],
        padding_after: Optional[int],
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
    ) -> Optional[List[Any]]:
        """
        Performs no changepoint search: the event is one blocked stretch between two edges, and each edge is found from the baseline side and walked to where the blocked level begins. Returned indices are pre-pended with 0 if 0 is not already the first entry.

        The finder's start and end estimates may sit anywhere near their edge - in the
        baseline some way out, as the shipped finders report them, or on the edge
        itself - so neither is trusted as a position. From each estimate the walk goes
        inward to the nearest *sustained* departure from the baseline band (at least
        ``EDGE_RUN_SAMPLES`` consecutive samples more than ``EDGE_BAND_SIGMA`` local
        sigmas from the baseline mean) whose run reaches twice the band; a shorter or
        shallower excursion is noise and is skipped. That departure is the edge: the
        start of the event on the leading side, the first baseline sample after the
        return on the trailing side. From each edge a slope walk continues inward while
        the signal keeps moving away from baseline, by more than ``EDGE_BAND_SIGMA``
        times the noise of the data's own first differences (measured on the samples
        that are not on a departure, since on low-pass data consecutive samples differ
        by far less than the sample sigma); where it stops is the foot of the edge. The
        event ends where the return to baseline begins, the sample after the foot of
        the trailing edge, so both edges sit the same distance before the finder's
        boundaries on a symmetric edge and the duration is the finder's. Each
        sublevel's statistics cover its steady part: the leading padding up to the
        start, the blocked stretch from the foot of the leading edge to the end, the
        trailing padding from the first baseline sample after the return. An event
        that never leaves the band keeps the finder's estimates as its edges.

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



        :return: ``(edge, statistics_start, statistics_end)`` for each sublevel boundary - 0, the start of the event, the start of its return to baseline and ``len(data)`` - where the statistics range is the steady part of the sublevel that begins at ``edge``, carried to :meth:`_populate_sublevel_metadata` in the list rather than on the instance.
        :rtype: Optional[List[Any]]

        :raises ValueError: if the event is rejected. Note that ValueError will skip and reject the event but will not stop processing of the rest of the dataset
        """

        length = len(data)
        if (
            baseline_mean is None
            or padding_before is None
            or padding_after is None
            or baseline_std is None
        ):
            raise ValueError(
                "NoFitter requires that baseline_mean, baseline_std, padding_before, and padding_after be reported and is unable to locate sublevel transitions without them"
            )
        if (
            padding_before <= 0
            or padding_after <= 0
            or padding_before + padding_after >= length
            or length < self.EDGE_RUN_SAMPLES
        ):
            raise ValueError(
                "NoFitter requires baseline padding on both sides of the event"
            )
        sign = np.sign(baseline_mean)
        # positive inside a blockage, whichever sign the baseline has
        deviation = (baseline_mean - data) * sign
        band = self.EDGE_BAND_SIGMA * baseline_std
        start_estimate = int(padding_before)
        end_estimate = length - int(padding_after)

        # A sample is off the baseline only as part of a run of EDGE_RUN_SAMPLES such
        # samples, so an isolated excursion is never taken for an edge.
        off_band = deviation > band
        runs = np.lib.stride_tricks.sliding_window_view(
            off_band, self.EDGE_RUN_SAMPLES
        ).all(axis=1)
        sustained = np.zeros(length, dtype=bool)
        for shift in range(self.EDGE_RUN_SAMPLES):
            sustained[shift : shift + runs.size] |= runs

        # The noise of first differences, from the samples that are not on a departure.
        differences = np.diff(data)
        quiet = ~sustained[:-1] & ~sustained[1:]
        quiet_differences = differences[quiet]
        sigma_diff = (
            float(np.std(quiet_differences))
            if quiet_differences.size >= 8
            else float(baseline_std) * np.sqrt(2.0)
        )
        slope_band = self.EDGE_BAND_SIGMA * sigma_diff

        def run_reaches_depth(k: int, step: int) -> bool:
            """Does the sustained run containing ``k`` reach twice the band? A noise bump does not."""
            peak = deviation[k]
            while 0 <= k + step < length and sustained[k + step]:
                k += step
                peak = max(peak, deviation[k])
            return bool(peak > 2 * band)

        def walk_edge(k: int, step: int, limit: int) -> int:
            """From edge sample ``k``, walk inward while the signal keeps moving away from baseline."""
            while k + step != limit:
                one = deviation[k + step] - deviation[k]
                two_ahead = k + 2 * step
                two = (
                    deviation[two_ahead] - deviation[k]
                    if two_ahead != limit and 0 <= two_ahead < length
                    else one
                )
                if one > slope_band or two > 2 * slope_band:
                    k += step
                else:
                    break
            return k

        # The start: inward from the start estimate to the nearest departure that is an edge.
        start = start_estimate
        while start > 0 and sustained[start]:
            start -= 1
        foot_in = start
        while True:
            while start < end_estimate and not sustained[start]:
                start += 1
            if start >= end_estimate:
                break
            if run_reaches_depth(start, +1):
                foot_in = walk_edge(start, +1, end_estimate)
                break
            while start < end_estimate and sustained[start]:
                start += 1
        if start >= end_estimate:
            # never leaves the band: the finder's estimates stand
            return [
                (0, 0, start_estimate),
                (start_estimate, start_estimate, end_estimate),
                (end_estimate, end_estimate, length),
                (length, length, length),
            ]
        # The end: inward (back) from the end estimate to the nearest departure that is an edge.
        after = end_estimate
        while after < length - 1 and sustained[after]:
            after += 1
        foot_out = after
        while True:
            while after > foot_in + 1 and not sustained[after - 1]:
                after -= 1
            if after - 1 <= foot_in:
                break
            if run_reaches_depth(after - 1, -1):
                foot_out = walk_edge(after - 1, -1, foot_in)
                break
            while after > foot_in + 1 and sustained[after - 1]:
                after -= 1
        if after - 1 <= foot_in:
            raise ValueError("Unable to resolve the edges of the event")
        end = foot_out + 1  # the return to baseline begins at the sample after the foot
        if not (0 < start <= foot_in < end <= after < length):
            raise ValueError("Unable to resolve the edges of the event")
        # The geometry travels with the event in its entries, not on the instance: one
        # fitter fits every channel on a thread per channel, so a stored value was
        # replaced by another channel's event before _populate_sublevel_metadata read it.
        return [
            (0, 0, int(start)),
            (int(start), int(foot_in), int(end)),
            (int(end), int(after), length),
            (length, length, length),
        ]

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
        Build a dict of lists of sublevel metadata with whatever arbitrary keys you want to consider in your event fitter. Every list must have one value per sublevel - one fewer than the entries in sublevel_starts, whose last entry is the terminal boundary. Note that 'index' is already handled in the base class

        :param data: an array of data from which to extract the locations of sublevel transitions
        :type data: npt.NDArray[np.float64]
        :param samplerate: the sampling rate
        :type samplerate: float
        :param baseline_mean: the local mean value of the baseline current
        :type baseline_mean: Optional[float]
        :param baseline_std: the local standard deviation of the baseline current
        :type baseline_std: Optional[float]
        :param sublevel_starts: the ``(edge, statistics_start, statistics_end)`` entries located in self._locate_sublevel_transitions()
        :type sublevel_starts: List[Any]

        :return: a dict of lists of sublevel metadata values, one list entry per sublevel for each piece of metadata
        :rtype: Dict[str, npt.NDArray[Numeric]]
        :raises ValueError: if baseline_std is None, or if the sublevel current at the start and end of the event differ by more than twice the local baseline standard deviation (baseline mismatch)
        """
        if baseline_std is None:
            raise ValueError(
                "baseline_std must be provided to populate sublevel metadata; it cannot be recovered here if the event was reported without it"
            )

        sublevel_metadata = {}

        # Each entry is (edge, statistics_start, statistics_end), as
        # _locate_sublevel_transitions returns it. Durations, times, deviations and the
        # raw charge span the whole sublevel between edges; the current, its standard
        # deviation and the blockage are taken over the steady part only, so neither
        # edge skews them. The current is the mean, not a median: NoFitter reports the
        # average of whatever blocked states the event holds, and a median of a
        # two-state event would report the longer state instead.
        edges = [int(entry[0]) for entry in sublevel_starts]
        num_states = len(edges) - 1
        steady = [
            (int(sublevel_starts[i][1]), int(sublevel_starts[i][2]))
            for i in range(num_states)
        ]
        sublevel_starts = edges
        dt_us = 1.0 / samplerate * 1e6
        aC_pC = 1e-6

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            sublevel_metadata["sublevel_current"] = np.array(
                [np.mean(data[lo:hi]) for lo, hi in steady], dtype=np.float64
            )

            if (
                np.absolute(
                    sublevel_metadata["sublevel_current"][0]
                    - sublevel_metadata["sublevel_current"][-1]
                )
                > 2 * baseline_std
            ):
                raise ValueError("Baseline Mismatch")

            sublevel_metadata["sublevel_stdev"] = np.array(
                [np.std(data[lo:hi]) for lo, hi in steady], dtype=np.float64
            )

            # get the difference from the local baseline
            event_baseline = 0.5 * (
                sublevel_metadata["sublevel_current"][0]
                + sublevel_metadata["sublevel_current"][-1]
            )
            sublevel_metadata["sublevel_blockage"] = np.array(
                [
                    (event_baseline - np.mean(data[lo:hi])) * np.sign(event_baseline)
                    for lo, hi in steady
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
                np.asarray(sublevel_starts[:-1]) * dt_us,
                dtype=np.float64,
            )

            # get sublevel end times
            sublevel_metadata["sublevel_end_times"] = np.array(
                np.asarray(sublevel_starts[1:]) * dt_us, dtype=np.float64
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
        """
        event_metadata: Dict[str, Union[int, float, str, bool]] = {}

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
        """
        pass

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
        metadata_types: Dict[str, Type[Union[int, float, str, bool]]] = {}
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
        metadata_types: Dict[str, Type[Union[int, float, str, bool]]] = {}
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
    def _define_event_metadata_units(self) -> Dict[str, Optional[str]]:
        """
        Build a dict of metadata units, or None if unitless. Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting.

        :return: a dict of metadata keys and associated units
        :rtype: Dict[str, Optional[str]]
        """
        metadata_units: Dict[str, Optional[str]] = {}
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
        metadata_units["sublevel_blockage"] = "pA"
        metadata_units["sublevel_duration"] = "us"
        metadata_units["sublevel_start_times"] = "us"
        metadata_units["sublevel_end_times"] = "us"
        metadata_units["sublevel_max_deviation"] = "pA"
        metadata_units["sublevel_raw_ecd"] = "pC"
        metadata_units["sublevel_fitted_ecd"] = "pC"
        return metadata_units
