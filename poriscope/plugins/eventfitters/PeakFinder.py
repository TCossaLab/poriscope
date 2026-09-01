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
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast, override

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from scipy.interpolate import BSpline, make_smoothing_spline
from scipy.optimize import curve_fit, minimize
from scipy.signal import find_peaks, peak_widths
from scipy.stats import iqr
from sklearn.mixture import GaussianMixture

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventFitter import MetaEventFitter

Numeric = Union[int, float, np.number]


class _ClassificationWarningCollector(logging.Handler):
    """
    Logging handler that records WARNING-level messages verbatim, so they can
    be surfaced in the saved classification report instead of living only in
    the log file.

    Attached to ``PeakFinder.logger`` for the duration of the classifier
    stages in ``_post_process_events`` and nowhere else - see that method for
    where it starts and stops listening. ``report_channel_status`` reads
    ``self._classification_warnings`` afterward; this handler has no effect
    on what actually gets logged, since the root/module logging setup is
    untouched.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.setFormatter(logging.Formatter("%(message)s"))
        self.records: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno == logging.WARNING:
            self.records.append(self.format(record))


@inherit_docstrings
class PeakFinder(MetaEventFitter):
    """
    Event fitter that resolves each event into peaks and classifies them.

    A :ref:`MetaEventFitter` subclass driven entirely by the base class:
    ``MetaEventFitter.fit_events()`` calls ``_pre_process_events`` once per
    channel, then ``_locate_sublevel_transitions`` /
    ``_populate_sublevel_metadata`` / ``_populate_event_metadata`` once per
    event, then ``_post_process_events`` when the channel's last event is
    fitted. Per-event work finds peaks and measures them; the dataset-wide
    classifiers (folding, peak prominence, translocation direction, bound
    star) all run from ``_post_process_events`` once every channel has
    finished, because each of them fits a distribution that only exists
    across the whole run.

    Two companion documents at the repository root describe the behaviour
    that is too large to carry in docstrings: ``peak_finding_pipeline.md``
    for the stage-by-stage flow and the filters applied at each stage, and
    ``fit_fallbacks.md`` for every fallback path in the double-Gaussian
    threshold fit.
    """

    logger = logging.getLogger(__name__)

    #: Minimum number of histogram bins handed to the double-Gaussian fit.
    #: Six free parameters need meaningfully more bins than that to be
    #: constrained; see ``_histogram_for_fit`` for the measurements behind this.
    MIN_FIT_BINS = 30

    #: Percentile core of the log-ECD-ratio distribution that the translocation
    #: direction fit is run on. ``_histogram_for_fit`` takes its bin width from
    #: the IQR, which is outlier-robust, but its range from the extremes, which
    #: is not - so a few events whose pre- or post-barcode ECD is near zero, and
    #: whose log ratio is therefore several decades out, stretch the histogram
    #: until the two real populations share a handful of bins. A single event
    #: two decades out roughly halves the bins the two populations span, and
    #: three events three decades out cut it by about four - at which point the
    #: six parameters are underdetermined and, per ``_histogram_for_fit``, the
    #: fit can converge with both Gaussians on the same mode while passing every
    #: convergence check. ``n_components`` then comes back 1 and the whole pass
    #: declines, leaving every event with no direction at all.
    #:
    #: The threshold this fit produces is applied to *every* event regardless,
    #: so unlike the pre-filter this replaces, the window never decides which
    #: events get classified - only which ones the fit is estimated from.
    #:
    #: The trim is skipped when the core comes out below ``MIN_FIT_BINS``, which
    #: is the only gate it needs: the core is about 90% of the sample, so
    #: reaching that floor already requires 34 events, and a separate
    #: minimum-event count in front of it could never be the binding test.
    DIRECTION_FIT_PERCENTILES = (5.0, 95.0)

    #: Minimum separation, in units of the dominant peak's FWHM, that two
    #: histogram maxima must have before they are accepted as seeds for the two
    #: components of the double-Gaussian fit. Two maxima closer than this are
    #: features of the same mode, not two populations. See
    #: ``_fit_double_gaussian`` for the failure this exists to prevent.
    SEED_SEPARATION_FWHM = 1.0

    #: How many of its own standard deviations the higher fitted component's
    #: mean must sit above the valley (and the lower component's mean below it).
    #: The valley is the boundary *between* the two populations, not a point
    #: inside either one, so a component whose summit sits on it is describing
    #: the other population's skewed shoulder rather than its own data. Because
    #: it is denominated in each component's own fitted width, this is
    #: independent of skew and of absolute current scale. At 0.5 a component may
    #: have fallen no less than to ``exp(-0.5**2/2)`` = 88% of its own peak
    #: height by the valley. See ``_fit_double_gaussian_bounded_at_valley``.
    VALLEY_SEPARATION_SIGMA = 0.5

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

    #: Extra ladder steps to take past the first acceptable lambda. **Zero, and
    #: measured rather than assumed.** Taking a safety margin past the least
    #: smoothing that works sounds prudent and is actively harmful here: on
    #: skewed distributions, two margin steps moved the higher component's mode
    #: bias by an order of magnitude, lowered mean classification accuracy, and
    #: made a fifth of the fits fail outright, because the extra smoothing
    #: washes out the very valley the ladder had just resolved. One step past
    #: "quiet enough" is already past "still shows the real valley".
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
        Declare the settings this fitter exposes, on top of the base contract.

        Called by poriscope when the plugin is instantiated or reconfigured, to
        build the settings dialog and to sanity-check whatever the user enters;
        the accepted values are then readable through ``self.settings``. The
        ``super()`` call supplies the mandatory ``"MetaReader"`` key.

        The keys added here, and where each one is consumed:

        - ``Event Type`` - selects the branch ``filter_peaks`` takes:
          ``"Barcode"``, ``"Single Peak"``, or ``"Unspecified"`` (no peak
          typing at all).
        - ``Number of peaks`` - in the barcode branch, both the smallest
          cluster that may be called a barcode and the number of
          most-prominent peaks considered for clustering.
        - ``Lower Filter Threshold`` / ``Higher Filter Threshold`` - in units
          of the baseline standard deviation, the tolerance bands
          ``filter_peaks`` places around the carrier levels when typing peaks,
          and the margin ``_classify_bound_star`` requires above the folded
          level.
        - ``Peak to Peak Distance Ratio`` - as a percentage of event length,
          how close two peaks must be to join the same barcode cluster.
        - ``Window Length Percentage`` - as a percentage of event length, the
          ``wlen`` prominence window ``_locate_sublevel_transitions`` hands to
          ``scipy.signal.find_peaks``.
        - ``Min Carrier Blockage`` - the smallest carrier blockage an event may
          have and still be admitted to the folding fit.

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
            "Value": 5.0,  # 5% of event length, in the same microseconds as peak_loc
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
        return settings

    @log(logger=logger)
    @override
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        Release per-channel resources. Nothing here holds any, so this is a
        no-op.

        Called by the base class on channel reset and on application exit,
        either for one channel or for all of them.
        """

    @log(logger=logger)
    @override
    def construct_fitted_event(
        self, channel: int, index: int
    ) -> Optional[npt.NDArray[np.float64]]:
        """
        Rebuild an idealised trace for one event from its fitted metadata.

        Called by ``MetaEventFitter.get_fitted_event()``, which validates the
        returned array against the raw event and hands it to the plotting
        layer to be drawn over the raw data. Nothing else consumes it.

        The trace is assembled at baseline, then overwritten in three passes:
        the padding either side of the event, the mean level of every type-3
        sublevel, and the ``max_blockage`` level of each peak between its two
        inflection points. Times held in the metadata in microseconds are
        converted to sample indices here, and the result is forced to the raw
        event's own length so the two can be plotted against one axis.

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
        Build the reference lines and labels drawn over one fitted event.

        Called by the plotting layer through the
        ``MetaEventFitter.get_plot_features()`` contract, alongside
        ``construct_fitted_event()`` for the same event. Returns horizontal
        lines (baseline, unfolded level, and that level offset by each of the
        two filter thresholds), one marker per peak, and the label strings
        that go with them.

        Only metadata that is actually populated reaches a label: an event the
        classifiers never reached reads as having no value rather than a value
        of nan, which would look like a classification that ran and failed.
        ``SQLitePeakDBLoader.get_plot_features`` mirrors this method for events
        read back out of a database and has to be kept in step with it.

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
            bases: list[float] = []
            peaks: list[tuple[float, float]] = []
            vlabel: list[str] = []
            hlabel: list[str] = []
            plabel: list[str] = []
            peaks_filtered: list[float] = []
            j = 1

            # Reference levels, drawn so the filter bands used to type peaks
            # are visible against the trace.
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

            event_data = self.event_metadata[channel][index]
            direction = event_data.get("translocation_direction")
            if direction in ("forward", "backward"):
                start_times = self.sublevel_metadata[channel][index][
                    "sublevel_start_times"
                ]
                peaks_filtered.append(
                    start_times[1] if direction == "forward" else start_times[-1]
                )

                # bound_star shares the direction's line: it is the same
                # forward/backward question answered from the star's position
                # rather than from the ECD ratio, so the two belong side by side.
                label = f"{direction.capitalize()} translocation."
                bound_star = event_data.get("bound_star")
                if bound_star:
                    label += f" Bound star: {bound_star}"

                fields = []
                sequence = event_data.get("sequence")
                if sequence:
                    fields.append(f"Sequence: {sequence}")
                translocation_confidence = event_data.get("translocation_confidence")
                if translocation_confidence is not None:
                    fields.append(f"Confidence: {round(translocation_confidence, 3)}")
                if fields:
                    label += "\n " + " ".join(fields)

                vlabel.append(label)

            for i in range(len(self.sublevel_metadata[channel][index]["right_ips"])):

                if self.sublevel_metadata[channel][index]["peak_id"][i] is not None:
                    peaks.append(
                        (
                            self.sublevel_metadata[channel][index]["peak_loc"][i],
                            -np.sign(baseline)
                            * self.sublevel_metadata[channel][index]["peak_height"][i]
                            + baseline,
                        )
                    )
                    # A peak no classifier acted on - every filter type -1
                    # among them - carries NaN in "classified" and
                    # "classification_confidence". The arrays are absent
                    # entirely when classification never ran, so their presence
                    # is checked before their contents.
                    sublevel = self.sublevel_metadata[channel][index]
                    peak_label = "Peak #" + str(j)

                    filter_values = sublevel.get("filtered")
                    if (
                        filter_values is not None
                        and i < len(filter_values)
                        and filter_values[i] is not None
                        and not np.isnan(filter_values[i])
                    ):
                        peak_label += f" Filter: {filter_values[i]}"

                    class_values = sublevel.get("classified")
                    if (
                        class_values is not None
                        and i < len(class_values)
                        and class_values[i] is not None
                        and not np.isnan(class_values[i])
                    ):
                        peak_label += f" Class: {class_values[i]}"

                    confidence_values = sublevel.get("classification_confidence")
                    if (
                        confidence_values is not None
                        and i < len(confidence_values)
                        and confidence_values[i] is not None
                        and not np.isnan(confidence_values[i])
                    ):
                        peak_label += f" Confidence: {round(confidence_values[i], 3)}"

                    plabel.append(peak_label)

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
        Hook for subclass setup at the start of base class initialization.
        Nothing to do here, so this is a no-op.

        Called once by ``MetaEventFitter`` while the plugin is being
        constructed, before any settings are applied.
        """

    @log(logger=logger)
    @override
    def _pre_process_events(self, channel: int) -> None:
        """
        Arm the run-wide post-processing pass for a channel about to be fitted.

        Called by ``MetaEventFitter.fit_events()`` once per channel, before any
        of that channel's events are fitted. Clearing
        ``_global_postprocessing_done`` here is what lets the classifiers run
        again on a second fitting session in the same app instance;
        ``_post_process_events`` sets the flag when they have run.

        :param channel: the channel to preprocess
        :type channel: int
        """
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

        Re-derives an event's padding boundaries instead of trusting the values
        the event loader supplied.

        **Not currently called.** Its only call site, in
        ``_locate_sublevel_transitions``, is commented out: the padding is taken
        from the event loader and then trimmed to the longest above-threshold
        segment instead. Kept because it is the only change-point detector in
        this plugin and the trimming approach may not suit every recording.

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
        # baseline_std is Optional under the MetaEventFitter contract but sets
        # the CUSUM step size, so an event loader that supplies none is an
        # error rather than a case to work around.
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
        Find the peaks in one event and return the sublevel boundaries around them.

        Called by ``MetaEventFitter.fit_events()`` once per event, first of the
        three per-event hooks; whatever it returns is passed verbatim to
        ``_populate_sublevel_metadata`` and ``_populate_event_metadata``. Here
        that is a list of ``(edge_index, sublevel_type)`` tuples plus the
        ``scipy.signal.find_peaks`` properties dict, so the downstream hooks do
        not have to re-detect anything.

        The stages, and the filters each one applies:

        1. Re-measure the baseline mean and standard deviation from the padding
           the event loader reported.
        2. Trim the event to the **longest continuous run** more than
           ``min(|lower threshold|, |higher threshold|, 3)`` baseline sigma away
           from the baseline, and fold everything outside it into the padding.
           An event with no such run, or whose longest run is under 100
           samples, is rejected.
        3. Take the carrier blockage as the modal level of the trimmed data and
           reject the event if it is below ``Min Carrier Blockage``.
        4. Detect peaks with ``find_peaks``, using a minimum prominence of the
           larger of the noise floor and the carrier blockage, a minimum height
           of the carrier blockage plus that prominence, a prominence window
           ``wlen`` set by ``Window Length Percentage``, and a minimum peak
           separation of half that window.
        5. Turn the peak inflection points into sublevel edges and label each
           sublevel ``"peak"`` or ``"event_baseline"``.

        Rejection at any of these stages raises ``ValueError``, which drops the
        one event and lets the run continue.

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

        min_height = None  # set below, once the carrier blockage is known
        min_prom = None  # set below, once the carrier blockage is known
        width = 0  # no width constraint
        min_dist = None  # set below, from wlen
        rel_height = 0.5  # widths are measured at half the peak height

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

        # The CUSUM alternative to the segment trimming below lives in
        # `redefine_padding` and is not currently used:
        #   edges = self.redefine_padding(data, samplerate, baseline_std)
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

        # Fold everything outside the longest segment into the padding, so the
        # rest of this method - and every downstream stage that works from the
        # padding - sees only the trimmed event.
        new_padding_before = padding_before + longest_start_idx
        new_padding_after = padding_after + (len(event_data) - longest_end_idx)

        padding_before = new_padding_before
        padding_after = new_padding_after

        # The carrier blockage is the modal level of the trimmed event, and is
        # what the peak-detection thresholds below are scaled against.
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

        # A peak has to clear the noise *and* be meaningful against the
        # translocation signal, so the prominence floor is the stricter of the
        # two; the height floor then sits a full prominence beyond the carrier
        # level, so peaks are measured from the carrier rather than from the
        # baseline.
        min_prom_noise = max(abs(low_threshold), abs(high_threshold)) * baseline_std
        min_prom_signal = carrier_blockage
        min_prom = max(min_prom_noise, min_prom_signal)
        min_height = max(
            max(abs(low_threshold), abs(high_threshold)) * baseline_std,
            carrier_blockage + min_prom,
        )

        # wlen bounds how far `find_peaks` may walk when it looks for a peak's
        # bases, and so how much of a neighbouring peak can be counted into
        # this one's prominence. Setting it as a percentage of event length
        # keeps that window scaled to the event rather than to the sample rate.
        trimmed_event_length = len(trimmed_data)

        window_length_percentage = self.settings.get(
            "Window Length Percentage", {}
        ).get("Value", 2.2)
        window_length_ratio = window_length_percentage / 100.0

        wlen = int(window_length_ratio * trimmed_event_length)
        wlen = min(wlen, trimmed_event_length // 3)
        wlen = max(wlen, 2)

        # Peaks closer together than half the prominence window are not
        # separable by it, so they are not reported separately either.
        min_dist = max(1, wlen // 2)

        # Diagnostics only; nothing below reads snr.
        signal_step = max(min_prom, min_height)
        snr = signal_step / baseline_std if baseline_std > 0 else 10.0

        self.logger.debug(
            f"Peak detection parameters: dt_us={dt_us:.3f}, baseline_std={baseline_std:.2f}, "
            f"carrier_blockage={carrier_blockage:.2f} pA, "
            f"low_threshold={low_threshold}, high_threshold={high_threshold}, "
            f"min_prom_noise={min_prom_noise:.2f} pA, "
            f"min_prom_signal={min_prom_signal:.2f} pA (carrier blockage), "
            f"final min_prom={min_prom:.2f} pA, "
            f"min_height={min_height:.2f} pA (carrier + min_prom), "
            f"trimmed_event_length={trimmed_event_length} samples ({trimmed_event_length*dt_us:.2f} us), "
            f"window_percentage={window_length_percentage:.1f}%, "
            f"SNR={snr:.2f}, wlen={wlen} samples ({wlen*dt_us:.2f} us), "
            f"min_dist={min_dist} samples ({min_dist*dt_us:.2f} us), "
        )

        # `find_peaks` is called on the trimmed event, sign-flipped so that
        # blockages are maxima. Its `properties` dict is carried through to
        # `_populate_sublevel_metadata` unchanged apart from the two base keys
        # rewritten below, so the peak measurements are made once.

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
                        # Stored as an absolute blockage depth, not as a
                        # current, so it is comparable across polarities.
                        "peak_height": np.absolute(
                            np.sign(baseline_mean) * baseline_mean
                            + properties["peak_heights"][i]
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
        Measure every sublevel of one event and return one list per quantity.

        Called by ``MetaEventFitter.fit_events()`` once per event, immediately
        after ``_locate_sublevel_transitions``, whose return value arrives here
        as ``sublevel_starts``. Every list returned has exactly one entry per
        sublevel; ``'index'`` is handled by the base class and must not appear.

        Each sublevel is typed ``"peak"``, ``"event_baseline"`` or
        ``"padding"`` from the edge that opens it, and then measured: median
        current, deviation from the local baseline, start and end time,
        duration, raw and cumulative ECD, maximum deviation, and standard
        deviation. Peak sublevels additionally carry everything
        ``find_peaks`` measured - location, width, height, prominence, bases,
        inflection points, modal blockage - plus three fields that only later
        stages can fill:

        - the ``_normalized`` variants, which divide by the event's unfolded
          level and are written in ``update_event_metadata_post_processing``
          once that level is known across the run;
        - ``filtered``, the peak type, initialised to 0 and assigned by
          ``filter_peaks``;
        - ``classified`` and ``classification_confidence``, initialised to NaN
          and assigned by ``_classify_peak_prominences``.

        Non-peak sublevels carry NaN in all of the peak fields, which is what
        distinguishes them downstream.

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

        # One sublevel per gap between transitions, so one fewer than the
        # number of edges (which include the start and end of the data block).
        num_states = len(sublevel_starts) - 1
        dt_us = 1.0 / samplerate * 1e6
        aC_pC = 1e-6

        # Each sublevel takes its type from the edge that opens it.
        sublevel_metadata["sublevel_type"] = []
        for i in range(num_states):
            start_edge_type = sublevel_starts[i]["type"]
            if "peak" in start_edge_type:
                sublevel_metadata["sublevel_type"].append("peak")
            elif "event_baseline" in start_edge_type:
                sublevel_metadata["sublevel_type"].append("event_baseline")
            else:
                sublevel_metadata["sublevel_type"].append("padding")

        # Median rather than mean, so a transition caught inside the sublevel
        # does not drag its level.
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

        # The event baseline is the mean of the two padding sublevels, so a
        # slow drift across the event does not bias every deviation one way.
        event_baseline = 0.5 * (
            sublevel_metadata["sublevel_current"][0]
            + sublevel_metadata["sublevel_current"][-1]
        )

        sublevel_metadata["sublevel_duration"] = np.array(
            [
                (sublevel_starts[i + 1]["index"] - sublevel_starts[i]["index"]) * dt_us
                for i in range(num_states)
            ],
            dtype=np.float64,
        )

        sublevel_metadata["sublevel_start_times"] = np.array(
            [sublevel_starts[i]["index"] * dt_us for i in range(num_states)],
            dtype=np.float64,
        )

        sublevel_metadata["sublevel_end_times"] = np.array(
            [sublevel_starts[i + 1]["index"] * dt_us for i in range(num_states)],
            dtype=np.float64,
        )

        # ECD is the integral of the blockage over the sublevel, in pC.
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
        # Running total, so the ECD either side of any sublevel can be read
        # off directly - which is what _classify_translocation_direction does.
        sublevel_metadata["sublevel_cumulative_ecd"] = np.cumsum(
            sublevel_metadata["sublevel_raw_ecd"]
        )

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
        # 1..N over peak sublevels, None elsewhere.
        sublevel_metadata["peak_id"] = self.enumerate_peaks(
            sublevel_starts, num_states, sublevel_metadata["sublevel_type"]
        )

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

        # Widths are measured at half the peak height (rel_height=0.5 in
        # _locate_sublevel_transitions) and converted from samples to us.
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
        # Peak measurements. Non-peak sublevels carry NaN in every one of
        # these, which is what marks them as non-peaks downstream.
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
        # Normalized against the event's unfolded level, which is only known
        # once every channel is fitted, so filled in
        # update_event_metadata_post_processing rather than here.
        sublevel_metadata["normalized_height"] = np.array(
            [(np.nan) for i in range(num_states)],
            dtype=np.float64,
        )
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
        sublevel_metadata["normalized_prominence"] = np.array(
            [(np.nan) for i in range(num_states)],
            dtype=np.float64,
        )

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
        sublevel_metadata["normalized_blockage"] = np.array(
            [(np.nan) for i in range(num_states)],
            dtype=np.float64,
        )

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

        # Peak type, assigned by filter_peaks during post-processing. 0 means
        # "a peak, not yet typed"; NaN means "not a peak at all".
        sublevel_metadata["filtered"] = np.array(
            [
                (0 if "peak" in sublevel_starts[i]["type"] else np.nan)
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # Assigned by _classify_peak_prominences; NaN until then, and NaN
        # forever on peaks that classifier skips.
        sublevel_metadata["classified"] = np.array(
            [
                (np.nan if "peak" in sublevel_starts[i]["type"] else np.nan)
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
        # Assigned alongside "classified"; see _classification_confidence.
        sublevel_metadata["classification_confidence"] = np.array(
            [
                (np.nan if "peak" in sublevel_starts[i]["type"] else np.nan)
                for i in range(num_states)
            ],
            dtype=np.float64,
        )
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
        Reduce one event's sublevel measurements to a single row of event metadata.

        Called by ``MetaEventFitter.fit_events()`` once per event, last of the
        three per-event hooks, with the dict ``_populate_sublevel_metadata``
        returned. ``'start_time_s'`` and ``'index'`` are handled by the base
        class and must not appear here.

        Peak count, duration, ECD and maximum deviation are summed or reduced
        over the sublevels between the two padding sublevels. The baseline
        current is the duration-weighted mean of the two padding sublevels, and
        the baseline standard deviation the smallest of that weighted mean and
        either padding sublevel on its own, so a padding region that happens to
        contain part of the event cannot inflate it. ``primary_level`` is the
        modal blockage of the event between its first and last sublevel.

        Six fields are set to None here and filled in during post-processing,
        once the whole run has been fitted: ``unfolded_level`` and
        ``folded_level`` by ``_classify_folded_unfolded``,
        ``translocation_direction`` and ``translocation_confidence`` by
        ``_classify_translocation_direction``, ``sequence`` by
        ``_post_process_events``, and ``bound_star`` by
        ``_classify_bound_star``.

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

        # Everything below is reduced over [1:-1] - the sublevels between the
        # two padding sublevels - so the padding never enters an event total.
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

        # The padding already includes whatever _locate_sublevel_transitions
        # trimmed off, so the span between the first and last sublevel start is
        # exactly the trimmed event.
        start_idx = int(
            sublevel_metadata["sublevel_start_times"][1] * samplerate * 1e-6
        )
        end_idx = int(sublevel_metadata["sublevel_start_times"][-1] * samplerate * 1e-6)
        slice_data = data[start_idx:end_idx]

        self.logger.debug(
            f"find_primary_level: data len={len(data)}, start_idx={start_idx}, end_idx={end_idx}, slice len={len(slice_data)}"
        )
        # The metadata dict is typed Union[int, float, str, bool] by the base
        # contract, wider than the Optional[float] find_mode_blockage_level
        # accepts, so both values are narrowed explicitly here rather than
        # being mis-fitted silently.
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
        # Filled in during post-processing; see the docstring.
        event_metadata["unfolded_level"] = None  # type: ignore[assignment]
        event_metadata["folded_level"] = None  # type: ignore[assignment]
        event_metadata["translocation_direction"] = None  # type: ignore[assignment]
        event_metadata["translocation_confidence"] = None  # type: ignore[assignment]
        event_metadata["sequence"] = None  # type: ignore[assignment]
        event_metadata["bound_star"] = None  # type: ignore[assignment]

        return event_metadata

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Check a candidate settings dict beyond the base class's type and range
        checks. There is nothing to add here, so this is a no-op.

        Called by ``MetaEventFitter`` whenever settings are applied, after the
        generic validation against ``get_empty_settings()`` has passed.

        :param settings: Parameters for event detection.
        :type settings: dict
        """

    @log(logger=logger)
    @override
    def _define_event_metadata_types(
        self,
    ) -> Dict[str, Type[Union[int, float, str, bool]]]:
        """
        Declare the column name and dtype of every piece of event metadata.

        Called once by ``MetaEventFitter`` during initialization, and used by
        the database writer downstream to build the events table. The keys must
        match those ``_populate_event_metadata`` returns exactly, and must be
        kept in step with ``_define_event_metadata_units``.

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
            "bound_star": str,
        }

        return metadata_types

    @log(logger=logger)
    @override
    def _define_sublevel_metadata_types(
        self,
    ) -> Dict[str, Type[Union[int, float, str, bool]]]:
        """
        Declare the column name and dtype of every piece of sublevel metadata.

        Called once by ``MetaEventFitter`` during initialization, and used by
        the database writer downstream to build the sublevels table. The keys
        must match those ``_populate_sublevel_metadata`` returns exactly, and
        must be kept in step with ``_define_sublevel_metadata_units``. The type
        given is that of a single entry, not of the list holding them.

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
            "max_blockage": float,
            "left_base": float,
            "right_base": float,
            "left_ips": float,
            "right_ips": float,
            "height_ips": float,
            "filtered": float,  # float rather than int so non-peaks can hold NaN
            "normalized_height": float,
            "normalized_prominence": float,
            "normalized_blockage": float,
        }

        return metadata_types

    @log(logger=logger)
    @override
    def _define_event_metadata_units(self) -> Dict[str, Optional[str]]:
        """
        Declare the unit of every piece of event metadata, or None if unitless.

        Called once by ``MetaEventFitter`` during initialization, and carried
        into the database so downstream plots can label their axes. The keys
        must match ``_define_event_metadata_types`` exactly.

        :return: a dict of metadata keys and associated units
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
        metadata_units["bound_star"] = None

        return metadata_units

    @log(logger=logger)
    @override
    def _define_sublevel_metadata_units(self) -> Dict[str, Optional[str]]:
        """
        Declare the unit of every piece of sublevel metadata, or None if
        unitless.

        Called once by ``MetaEventFitter`` during initialization, and carried
        into the database so downstream plots can label their axes. The keys
        must match ``_define_sublevel_metadata_types`` exactly.

        :return: a dict of metadata keys and associated units
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
        Run every dataset-wide classifier, once the last channel is fitted.

        Called by ``MetaEventFitter.fit_events()`` once per channel, after that
        channel's last event. Each classifier below fits a distribution built
        from every event in the run, so all but the final call return early:
        the guard is ``_global_postprocessing_done``, armed for a new fitting
        session by ``_pre_process_events``.

        On the final call, in order:

        1. Pool one ``primary_level`` per event across all channels, dropping
           events with no primary level or with a non-positive ECD.
        2. ``_classify_folded_unfolded`` fits that pool and, for every event,
           writes ``unfolded_level`` / ``folded_level`` and re-runs
           ``filter_peaks`` against the run-wide levels through
           ``update_event_metadata_post_processing``.
        3. ``_classify_peak_prominences`` fits the prominences of all type 1,
           2 and 3 peaks and writes ``classified`` /
           ``classification_confidence`` per peak.
        4. ``_classify_translocation_direction`` fits the log ratio of the ECD
           before and after each event's barcode and writes
           ``translocation_direction`` / ``translocation_confidence``.
        5. Build each event's ``sequence`` from the prominence classes of its
           type-3 peaks, reversed for a backward event.
        6. ``_classify_bound_star`` writes ``bound_star``. It runs last because
           it needs both the direction, to put the star's position into the
           molecule's frame, and the sequences, to break its report down.
        7. ``_save_classification_report`` writes the run's report to disk.

        Steps 1-6 run with a ``_ClassificationWarningCollector`` attached to
        ``self.logger``, so every ``WARNING``-level message any of them logs -
        a degraded fit, a declined classifier, a fitted mean off its peak -
        is captured into ``self._classification_warnings`` and surfaced in the
        report ``report_channel_status`` builds for step 7, rather than living
        only in the log file.

        :param channel: the index of the channel to postprocess
        :type channel: int
        """
        self.logger.info(f"_post_process_events called for channel {channel}")

        if not hasattr(self, "_global_postprocessing_done"):
            self._global_postprocessing_done = False

        if self._global_postprocessing_done:
            self.logger.info("Global post-processing already completed, skipping")
            return

        # This hook fires once per channel, as each one finishes, but the
        # classifiers below fit distributions over the whole run - so every
        # call but the last returns here.
        if not hasattr(self, "eventfitting_status"):
            self.logger.warning("eventfitting_status attribute not found")
            return

        if not self.eventfitting_status:
            self.logger.warning("eventfitting_status is empty")
            return

        all_channels = list(self.event_metadata.keys())
        if not all_channels:
            self.logger.warning("No channels in event_metadata")
            return

        self.logger.info(f"All channels: {all_channels}")
        self.logger.info(f"Current eventfitting_status: {self.eventfitting_status}")

        # eventfitting_status[channel] is set by the base class AFTER this
        # returns, so the channel now being post-processed counts as done.
        all_fitted = all(
            (ch == channel) or self.eventfitting_status.get(ch, False)
            for ch in all_channels
        )

        self.logger.info(f"All channels fitted: {all_fitted}")

        if not all_fitted:
            self.logger.info(
                f"Channel {channel} fitting complete, but waiting for all channels to finish before global post-processing"
            )
            for ch in all_channels:
                is_done = (ch == channel) or self.eventfitting_status.get(ch, False)
                self.logger.info(
                    f"  Channel {ch}: fitted={is_done} (current={ch == channel}, status={self.eventfitting_status.get(ch, False)})"
                )
            return

        self._global_postprocessing_done = True

        warning_collector = _ClassificationWarningCollector()
        self.logger.addHandler(warning_collector)
        try:
            self.logger.info(
                "Starting global post-processing analysis with classification utilities"
            )

            channels = list(self.event_metadata.keys())

            if not channels:
                self.logger.warning("No channels found for post-processing")
                return

            # The folding fit runs on one primary level per event, pooled across
            # every channel. all_event_info is built index-for-index alongside it
            # so a fitted class can be written back to the event it came from.
            all_longest_levels: list[float] = []
            all_event_info: list[tuple[int, int]] = []

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

                    if (
                        primary_level is not None
                        and raw_ecd is not None
                        and raw_ecd > 0
                    ):
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

            self._classify_peak_prominences(channels)
            self._classify_translocation_direction(channels)

            for channel in channels:
                self.eventfitting_status[channel] = True

            # An event's sequence is the prominence class of each of its barcode
            # (type-3) peaks, read in trace order, then reversed for a backward
            # event so every sequence is written in the molecule's own frame.
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
                    if (
                        ch in self.event_metadata
                        and event_index in self.event_metadata[ch]
                    ):
                        direction = self.event_metadata[ch][event_index].get(
                            "translocation_direction", None
                        )
                        if direction == "backward":
                            sequence = sequence[::-1]
                        self.event_metadata[ch][event_index]["sequence"] = sequence

            # Bound-star detection runs last: it needs the translocation direction
            # to put each star's observed position into the molecule's frame, and
            # the sequence strings its report section counts against.
            self._classify_bound_star(channels)
        finally:
            self.logger.removeHandler(warning_collector)
            self._classification_warnings = warning_collector.records

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
        Write the run-wide carrier levels onto one event and re-type its peaks.

        Called by ``_classify_folded_unfolded``, once per event, as soon as the
        folding fit has decided that event's class. Nothing else calls it.

        Three things happen here, and only the first is bookkeeping:

        1. ``unfolded_level`` and ``folded_level`` are recorded on the event.
        2. ``peak_height``, ``prominence`` and ``max_blockage`` are divided by
           the unfolded level into their ``normalized_*`` counterparts, which
           ``_populate_sublevel_metadata`` could only leave as NaN.
        3. ``filter_peaks`` is re-run for the event against those levels. The
           per-event pass could only guess the carrier levels from that one
           event; this pass re-types every peak against levels measured over
           the whole run, and the ``filtered`` labels it writes are what every
           later stage - sequences, translocation direction, bound star, the
           report - actually reads.

        :param channel: Channel number
        :type channel: int
        :param event_index: Event index within the channel
        :type event_index: int
        :param unfolded_level: Determined unfolded level for normalization
        :type unfolded_level: Optional[float]
        :param folded_level: Determined folded level for classification
        :type folded_level: Optional[float]
        """
        if channel not in self.event_metadata:
            self.logger.warning(f"Channel {channel} not found in event metadata")
            return

        if event_index not in self.event_metadata[channel]:
            self.logger.warning(
                f"Event index {event_index} not found in channel {channel}"
            )
            return

        if unfolded_level is not None:
            self.event_metadata[channel][event_index]["unfolded_level"] = unfolded_level
        if folded_level is not None:
            self.event_metadata[channel][event_index]["folded_level"] = folded_level

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

        sublevel_data = self.sublevel_metadata[channel][event_index]
        event_data = self.event_metadata[channel][event_index]

        # The normalized_* fields left as NaN during fitting can only be
        # filled once the run-wide unfolded level is known.
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

        # Re-type this event's peaks against the run-wide carrier levels,
        # replacing the labels the per-event pass assigned.
        if unfolded_level is not None and folded_level is not None:
            baseline_mean = event_data.get("baseline_current")
            baseline_stdev = self.event_metadata[channel][event_index].get(
                "baseline_stdev"
            )

            if baseline_mean is not None and baseline_stdev is not None:
                if self.eventloader is None:
                    self.logger.warning(
                        "Event loader is not set; cannot reclassify peaks"
                    )
                    return

                samplerate = self.eventloader.get_samplerate(channel)

                # filter_peaks takes the shape find_peaks produces, so the
                # peak sublevels are gathered back into that shape here. Bases
                # are converted from currents to blockage depths on the way.
                peak_indices: list[int] = []
                properties: dict[str, list[float | int]] = {
                    "left_bases": [],
                    "right_bases": [],
                    "prominences": [],
                    "peak_heights": [],
                    "filtered": [],
                    "peak_loc": [],
                }

                for i, peak_id in enumerate(sublevel_data.get("peak_id", [])):
                    if peak_id is not None:
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
                    # filter_peaks indexes its properties lists positionally,
                    # so the sublevel indices stand in for peak positions.
                    peaks = np.array(peak_indices)
                    event_length = np.sum(event_data.get("duration", []))

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

                    # Written back in place, so the new labels land on the
                    # same sublevel rows the peaks were read from. Works for
                    # both the list and the ndarray representation.
                    filtered_data = sublevel_data["filtered"]
                    for idx, peak_idx in enumerate(peak_indices):
                        filtered_data[peak_idx] = updated_properties["filtered"][idx]

                    self.logger.debug(
                        f"Channel {channel}, Event {event_index}: Reclassified {len(peak_indices)} peaks, filtered values: {filtered_data}"
                    )

    @log(logger=logger)
    @override
    def report_channel_status(
        self, channel: Optional[int] = None, init: bool = False
    ) -> str:
        """
        Return the fitting report plus the run's full classification section.

        Called by the UI to show a channel's status, and by
        ``_save_classification_report`` to build the report file written at the
        end of post-processing. The classification section is appended only
        once ``_post_process_events`` has produced ``_classification_results``;
        before that, or when ``init`` is set, only the base report is returned.

        The classification section covers, in order: the folding fit and its
        folded/unfolded counts, the peak type breakdown from
        ``_collect_peak_statistics``, the prominence fit and its class counts,
        the translocation direction fit and its counts, the sequence tallies,
        the bound-star tallies with a per-sequence breakdown, and finally -
        when ``self._classification_warnings`` is non-empty - a "Warnings
        during classification" section listing every distinct WARNING-level
        message logged while the classifiers ran, each with a ``(xN)`` suffix
        if it repeated. See ``_post_process_events`` for how those are
        collected.

        :param channel: the channel to report on, or None for all channels
        :type channel: Optional[int]
        :param init: whether this is an initialization report
        :type init: bool
        :return: the status report as a string
        :rtype: str
        :raises RuntimeError: if the channel's peak statistics cannot be assembled
        """
        # The per-channel base text is built here with explicit super() calls
        # rather than by delegating the channel=None case to the base class.
        # MetaEventFitter.report_channel_status() handles that case by looping
        # over the channels and calling `self.report_channel_status(ch, init)`,
        # which dispatches straight back into this override - so the
        # classification section below would be appended once per channel and
        # once more here, duplicating the report N+1 times for N channels.
        if channel is None:
            base_report = ""
            for ch in self.get_channels():
                base_report += super().report_channel_status(ch, init)
        else:
            base_report = super().report_channel_status(channel, init)

        if init or not hasattr(self, "_classification_results"):
            return base_report

        # During the final post-processing pass the classification results
        # exist before the base class flips eventfitting_status[channel], so a
        # channel that is in fact finished still reports as incomplete.
        #
        # NOTE: this branch does nothing about that. It checks that an event
        # loader is present and raises if not, and the report text is left
        # saying "fitting incomplete" either way.
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

            if peak_type_counts:
                classification_report += "\n\n  Peak Filtering breakdown:"
                for peak_type in sorted(peak_type_counts.keys()):
                    count = peak_type_counts[peak_type]
                    pct = count / total_peaks * 100 if total_peaks > 0 else 0

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

            raw_threshold = prominence_stats.get("threshold")
            if isinstance(raw_threshold, (int, float)) and not isinstance(
                raw_threshold, bool
            ):
                classification_report += f"\n  Threshold: {float(raw_threshold):.2f} pA"

            centers = prominence_stats.get("centers")

            if isinstance(centers, list) and centers:
                formatted_centers = ", ".join(f"{center:.2f}" for center in centers)
                classification_report += f"\n  Centers: {formatted_centers} pA"

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

        # Bound-star classification across all channels
        if hasattr(self, "_bound_star_results"):
            star_stats = self._bound_star_results
            classification_report += "\n\nBound Star Classification:"

            sequence_events = star_stats.get("sequence_events", 0)
            with_star = star_stats.get("with_star", 0)
            star_long_end = star_stats.get("long_end", 0)
            star_short_end = star_stats.get("short_end", 0)
            no_star = star_stats.get("no_star", 0)
            no_height_reference = star_stats.get("no_height_reference", 0)

            classification_report += (
                f"\n  Events with an assigned sequence: {sequence_events}"
            )

            if sequence_events > 0:
                classification_report += (
                    f"\n  With a bound star: {with_star} "
                    f"({with_star/sequence_events:.1%})"
                )
                if with_star > 0:
                    classification_report += (
                        f"\n    Long end (star translocates first): "
                        f"{star_long_end} ({star_long_end/with_star:.1%})"
                    )
                    classification_report += (
                        f"\n    Short end (star translocates last): "
                        f"{star_short_end} ({star_short_end/with_star:.1%})"
                    )
                classification_report += (
                    f"\n  Without a bound star: {no_star} "
                    f"({no_star/sequence_events:.1%})"
                )
                # Only surfaced when it actually fires, which means folding
                # classification declined and no event could be judged at all.
                # Silence here would report a whole run as starless.
                if no_height_reference:
                    classification_report += (
                        f"\n  Candidate peaks but no unfolded level to size "
                        f"them against: {no_height_reference} "
                        f"({no_height_reference/sequence_events:.1%})"
                    )
            else:
                classification_report += "\n  No sequences assigned; nothing to report"

            # Per-sequence breakdown. The three whole-event columns are shares
            # of that sequence's own events; long end and short end are shares
            # of its starred events, matching the denominators used above.
            per_sequence = star_stats.get("per_sequence", {})
            if per_sequence:
                show_unresolved = any(
                    row.get("unresolved_direction", 0) > 0
                    for row in per_sequence.values()
                )
                show_no_floor = any(
                    row.get("no_height_reference", 0) > 0
                    for row in per_sequence.values()
                )
                seq_width = max([len("sequence")] + [len(seq) for seq in per_sequence])
                classification_report += "\n\n  Breakdown by sequence:"
                header = (
                    f"\n    {'sequence':<{seq_width}}  {'events':>7}  "
                    f"{'with star':>16}  {'long end':>15}  {'short end':>15}  "
                    f"{'unbound':>16}"
                )
                if show_unresolved:
                    header += f"  {'no direction':>15}"
                if show_no_floor:
                    header += f"  {'no floor':>15}"
                classification_report += header

                for seq, row in sorted(
                    per_sequence.items(),
                    key=lambda item: (-item[1]["events"], item[0]),
                ):
                    events = row["events"]
                    row_star = row["with_star"]
                    row_long_end = row["long_end"]
                    row_short_end = row["short_end"]
                    row_unbound = row["no_star"]
                    star_text = f"{row_star} ({row_star/events:.1%})"
                    unbound_text = f"{row_unbound} ({row_unbound/events:.1%})"
                    # A sequence with no starred events has no denominator for
                    # the long/short split, so it reports the count alone
                    # rather than a percentage of nothing.
                    if row_star > 0:
                        long_text = f"{row_long_end} ({row_long_end/row_star:.1%})"
                        short_text = f"{row_short_end} ({row_short_end/row_star:.1%})"
                    else:
                        long_text = f"{row_long_end} (-)"
                        short_text = f"{row_short_end} (-)"
                    line = (
                        f"\n    {seq:<{seq_width}}  {events:>7}  "
                        f"{star_text:>16}  {long_text:>15}  "
                        f"{short_text:>15}  {unbound_text:>16}"
                    )
                    if show_unresolved:
                        row_unresolved = row["unresolved_direction"]
                        unresolved_text = (
                            f"{row_unresolved} ({row_unresolved/events:.1%})"
                        )
                        line += f"  {unresolved_text:>15}"
                    if show_no_floor:
                        row_no_floor = row["no_height_reference"]
                        no_floor_text = f"{row_no_floor} ({row_no_floor/events:.1%})"
                        line += f"  {no_floor_text:>15}"
                    classification_report += line

        warnings_seen = getattr(self, "_classification_warnings", None)
        if warnings_seen:
            counts = Counter(warnings_seen)
            classification_report += "\n\nWarnings during classification:"
            for message in dict.fromkeys(warnings_seen):
                count = counts[message]
                suffix = f" (x{count})" if count > 1 else ""
                classification_report += f"\n  - {message}{suffix}"

        return base_report + classification_report

    # ------------------------------------------------------------------
    # Classifiers. All four are called by _post_process_events, in the
    # order they appear below, once every channel has been fitted. Each
    # fits a distribution built from the whole run and writes its result
    # back onto every event or peak.
    # ------------------------------------------------------------------

    @log(logger=logger)
    def _classify_folded_unfolded(
        self,
        channels: list[int],
        all_event_info: list[tuple[int, int]],
        all_longest_levels_array: np.ndarray,
    ) -> None:
        """
        Split events into folded and unfolded carriers by blockage level.

        Called by ``_post_process_events``, first of the four classifiers, with
        one ``primary_level`` per event pooled across every channel. Fits that
        pool with ``fit_threshold``, takes the lower fitted centre as the
        unfolded level and the higher as the folded level, and then, for every
        event, calls ``update_event_metadata_post_processing`` - which records
        both levels on the event and re-runs ``filter_peaks`` against them.
        Everything downstream depends on this: without an unfolded level there
        are no peak types, and so no sequences, no direction and no stars.

        Carrier-blockage filtering is already applied to
        ``all_longest_levels_array`` by the caller and must not be repeated
        here.

        The fit sees the whole dataset exactly once and either succeeds or
        fails: no percentile pre-filter, and no re-fit on a narrowed subset
        when the result looks unconvincing. Retrying until something converges
        hides the fit's real success rate on live data behind whichever attempt
        happened to work. The histogram is likewise built once and reused for
        both the fit and the plot, so the plotted bars cannot be binned against
        edges derived from a different subset than the fit saw.
        """

        try:
            bt = self.fit_threshold(all_longest_levels_array)
        except Exception as e:
            self.logger.error(f"folding double-Gaussian fit failed: {e}")
            self._classification_results = {"error": "double-Gaussian fit failed"}
            self._collect_peak_statistics(channels)
            return

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
                "the double-Gaussian fit returned insufficient results for "
                "classification"
            )
            self._classification_results = {"error": "fit insufficient results"}
            self._collect_peak_statistics(channels)
            return

        centers_bt = np.asarray(bt.get("centers"), dtype=float)
        if centers_bt.size < 2:
            self.logger.warning(
                "the double-Gaussian fit did not yield two centres; cannot "
                "classify folded/unfolded"
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
        # `_fit_and_check_double_gaussian` already computes - forcing a split
        # onto genuinely unimodal data produces a collapsed component or two
        # centres on the same mode, and that outcome is acted on here instead
        # of only appearing as a log line.
        n_components = bt.get("n_components", 2)
        if n_components < 2:
            self.logger.warning(
                "folding classification: the double-Gaussian fit describes a "
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
        # A folded carrier blocks roughly twice as deeply as an unfolded one,
        # so a healthy fit puts the two centres at a ratio near 2. Reported and
        # logged but deliberately NOT acted on: re-fitting until the ratio
        # looks right is exactly what makes a bad fit rate invisible.
        if not 1.7 <= ratio <= 2.3:
            self.logger.warning(
                f"folding fit: centre ratio {ratio:.3f} is outside the expected "
                f"1.7-2.3 band (lower={lower_center:.3f}, "
                f"higher={higher_center:.3f}); the fit may not have resolved the "
                "folded and unfolded populations."
            )

        threshold = bt.get("threshold", (lower_center + higher_center) / 2.0)

        # `all_event_info` and `all_longest_levels_array` are built together,
        # index-for-index, by the sole caller, so this lookup cannot
        # legitimately go out of range. Checked explicitly and logged once
        # rather than swallowed, because silently dropping an event here would
        # let total_events stop reconciling with folded + unfolded.
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

        self._classification_results = {
            "total_events": len(all_event_info),
            "n_components": n_components,
            "folded_count": int(folded_count),
            "unfolded_count": int(unfolded_count),
            "lower_center": lower_center,
            "higher_center": higher_center,
            "threshold": threshold,
            "ratio": ratio,
        }

        # The plot is built from the same histogram the fit used, so the bars
        # cannot be binned against edges the fit never saw.
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

            # A non-zero dynamic range, or np.histogram warns.
            arr = self._jitter_degenerate_array(arr)

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
                        label="All Events",
                    )
                    hist_bins = bins
                except Exception:
                    ax.hist(
                        arr_all,
                        bins=50,
                        density=False,
                        alpha=0.5,
                        color="gray",
                        label="All Events",
                    )
                    hist_bins = None
            else:
                ax.hist(
                    arr_all,
                    bins=50,
                    density=False,
                    alpha=0.5,
                    color="gray",
                    label="All Events",
                )
                hist_bins = None

            class_mask = arr >= threshold
            higher_count = int(np.sum(class_mask))
            lower_count = int(len(arr) - higher_count)
            total_events_plot = len(arr)

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

            self._overlay_fitted_gaussians(
                ax,
                bt.get("params"),
                np.linspace(arr.min(), arr.max(), 1000),
                "Unfolded fit",
                "Folded fit",
                "folded/unfolded classification",
            )

            ax.axvline(
                threshold,
                color="black",
                linestyle="-",
                linewidth=2,
                label=f"Threshold: {threshold:.3f} pA",
            )

            try:
                pct_low = (
                    lower_count / total_events_plot if total_events_plot > 0 else 0.0
                )
                pct_high = (
                    higher_count / total_events_plot if total_events_plot > 0 else 0.0
                )
                info_text = (
                    f"Total Events: {total_events_plot}\n"
                    f"Unfolded: {lower_count} ({pct_low:.1%})\n"
                    f"Folded: {higher_count} ({pct_high:.1%})\n"
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
        Split peaks into two prominence classes, writing ``classified`` and
        ``classification_confidence`` onto every type 1, 2 or 3 peak.

        Called by ``_post_process_events``, second of the four classifiers,
        after ``_classify_folded_unfolded`` has re-typed every peak - so the
        ``filtered`` labels it selects on are the run-wide ones. Peaks of any
        other type, type -1 among them, are skipped and keep NaN. The classes
        it writes are what ``_post_process_events`` reads back to build each
        event's ``sequence``.

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
        # `_fit_and_check_double_gaussian` computes.
        try:
            bt = self.fit_threshold(prominence_array)
        except Exception as e:
            self.logger.error(
                f"double-Gaussian fit failed for prominence classification: {e}"
            )
            return

        n_components = bt.get("n_components", 2)
        centers = (
            np.asarray(bt.get("centers"), dtype=float)
            if bt.get("centers") is not None
            else np.array([])
        )

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
        # _classification_confidence for the derivation. Uses bt["params"]
        # as fit, which already reflects the constrained refit (and its
        # Gaussian-crossing threshold) when params_method is "constrained".
        confidence_values = self._classification_confidence(
            prominence_array, bt["params"], class_labels.astype(bool)
        )

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
            "centers": centers.tolist() if centers.size > 0 else [],
            "lower_count": int(np.sum(class_labels == 0)),
            "higher_count": int(np.sum(class_labels == 1)),
        }

        # The plot is built from the same histogram the fit used.
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

            # A non-zero dynamic range, or np.histogram warns.
            arr = self._jitter_degenerate_array(arr)

            hist_bins = None
            if counts is not None and bins is not None and np.sum(counts) > 0:
                widths = np.diff(bins)
                try:
                    if arr_all.size == 0 or np.any(widths <= 0):
                        raise ValueError("invalid bins")
                    full_counts, _ = np.histogram(arr_all, bins=bins)
                    # Named apart from the fitted `centers` above, which is the
                    # two population means and is still needed by the results.
                    bar_centers = (bins[:-1] + bins[1:]) / 2.0
                    ax.bar(
                        bar_centers,
                        full_counts,
                        width=widths,
                        alpha=0.5,
                        color="gray",
                        label="All Peaks",
                    )
                    hist_bins = bins
                except Exception:
                    ax.hist(
                        arr_all,
                        bins=100,
                        density=False,
                        alpha=0.5,
                        color="gray",
                        label="All Peaks",
                    )
                    hist_bins = None
            else:
                ax.hist(
                    arr_all,
                    bins=100,
                    density=False,
                    alpha=0.5,
                    color="gray",
                    label="All Peaks",
                )
                hist_bins = None

            lower_count = int(np.sum(class_labels == 0))
            higher_count = int(np.sum(class_labels == 1))
            total_peaks = len(arr)

            self._overlay_fitted_gaussians(
                ax,
                bt.get("params"),
                (
                    np.linspace(np.nanmin(arr), np.nanmax(arr), 1000)
                    if arr.size > 0
                    else np.linspace(0, 1, 1000)
                ),
                "Lower prominence fit",
                "Higher prominence fit",
                "peak prominence classification",
            )

            lower_mask = class_labels == 0
            higher_mask = class_labels == 1
            if hist_bins is not None:
                # Reusing the fit's own bin edges keeps the class bars aligned
                # with the grey all-peaks bars and with the fitted curves.
                lower_counts, _ = np.histogram(arr[lower_mask], bins=hist_bins)
                higher_counts, _ = np.histogram(arr[higher_mask], bins=hist_bins)
                widths = np.diff(hist_bins)
                bar_centers = (hist_bins[:-1] + hist_bins[1:]) / 2.0
                for class_counts, color, label in (
                    (lower_counts, "blue", "Lower prominence"),
                    (higher_counts, "red", "Higher prominence"),
                ):
                    ax.bar(
                        bar_centers,
                        class_counts,
                        width=widths,
                        alpha=0.6,
                        color=color,
                        label=label,
                    )
            else:
                for class_values, color, label in (
                    (arr[lower_mask], "blue", "Lower prominence"),
                    (arr[higher_mask], "red", "Higher prominence"),
                ):
                    ax.hist(
                        class_values,
                        bins=100,
                        density=False,
                        alpha=0.6,
                        color=color,
                        label=label,
                    )

            if threshold is not None:
                ax.axvline(
                    threshold,
                    color="black",
                    linestyle="-",
                    linewidth=2,
                    label=f"Threshold: {threshold:.3f} pA",
                )

            try:
                pct_low = lower_count / total_peaks if total_peaks > 0 else 0.0
                pct_high = higher_count / total_peaks if total_peaks > 0 else 0.0
                info_text = (
                    f"Total Peaks: {total_peaks}\n"
                    f"Selected populations: {n_components}\n"
                    f"Class 0: {lower_count} ({pct_low:.1%})\n"
                    f"Class 1: {higher_count} ({pct_high:.1%})\n"
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
        Decide which end of the construct entered the pore first, writing
        ``translocation_direction`` and ``translocation_confidence`` onto every
        event that has a barcode.

        Called by ``_post_process_events``, third of the four classifiers,
        after the peak types are settled and before sequences are built - the
        direction is what decides whether an event's sequence is reversed, and
        which end of the molecule ``_classify_bound_star`` attributes a star to.

        The construct is asymmetric about its barcode, so the ratio of the ECD
        before the first type-3 peak to the ECD after the last one says which
        way round it went. Per event that ratio is reduced to
        ``log10(pre / post)``; over the run those values form two populations,
        and ``fit_threshold`` separates them. Events with no type-3 peak at all
        contribute nothing and keep no direction.

        The fit is estimated from the percentile core of the distribution but
        applied to every event - see ``DIRECTION_FIT_PERCENTILES``. Where the
        fit describes only one population the whole pass declines, because
        "forward" is a claim about a second population that was not found.
        """
        event_refs: list[tuple[int, int]] = []
        log_ecds: list[float] = []

        for ch in channels:
            if ch not in self.sublevel_metadata:
                continue
            for event_index, sublevel_data in self.sublevel_metadata[ch].items():
                filtered_arr = np.asarray(
                    sublevel_data.get("filtered", []), dtype=float
                )
                csum = np.asarray(
                    sublevel_data.get("sublevel_cumulative_ecd", []), dtype=float
                )

                # sublevel_raw_ecd is per-sublevel, so it has to be summed
                # into a running total to stand in for the cumulative array.
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

                if first_type3_idx >= csum.size or last_type3_idx >= csum.size:
                    self.logger.debug(
                        f"Ch{ch} Event{event_index}: Skipped - type-3 index out of bounds (first={first_type3_idx}, last={last_type3_idx}, len={csum.size})"
                    )
                    continue

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

        # Estimate the fit from the percentile core, then classify everything
        # with the threshold it produces. See DIRECTION_FIT_PERCENTILES for why
        # the untrimmed array cannot be fitted reliably: a few near-zero ECDs
        # stretch the histogram until the two populations share too few bins and
        # the fit collapses onto one mode, declining the pass outright.
        #
        # This is deliberately not the old pre-filter, which trimmed the fit and
        # the classification together and so left the excluded events with no
        # direction at all. Only the estimate is trimmed here.
        fit_sample = log_ecds_arr
        low, high = np.percentile(log_ecds_arr, self.DIRECTION_FIT_PERCENTILES)
        core = log_ecds_arr[(log_ecds_arr >= low) & (log_ecds_arr <= high)]
        # A core below the bin floor cannot be fitted any better than the whole
        # array - a degenerate distribution piled on one value does this - so
        # the trim is skipped there and the untrimmed array is the better of two
        # bad options. That single test also covers a small sample, and there is
        # deliberately no separate minimum-event count in front of it: the core
        # is about 90% of n, so reaching MIN_FIT_BINS points already requires
        # n >= 34, and any threshold below that could never be the binding one.
        if core.size >= self.MIN_FIT_BINS:
            fit_sample = core
            self.logger.info(
                f"Translocation direction: fitting on the "
                f"{self.DIRECTION_FIT_PERCENTILES[0]:g}-"
                f"{self.DIRECTION_FIT_PERCENTILES[1]:g} percentile core "
                f"({core.size} of {log_ecds_arr.size} events, "
                f"log-ECD ratio {low:.3f} to {high:.3f}); all "
                f"{log_ecds_arr.size} are classified against the resulting "
                f"threshold"
            )

        try:
            bt = self.fit_threshold(fit_sample)
        except Exception as e:
            self.logger.error(
                f"double-Gaussian fit failed for translocation direction: {e}"
            )
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
                "the double-Gaussian fit did not yield two centres for "
                "translocation direction"
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
        # `_fit_and_check_double_gaussian` already computes - forcing a split
        # onto genuinely unimodal data produces a collapsed component or two
        # centres on the same mode, and that outcome is acted on here instead
        # of only appearing as a log line.
        n_components = bt.get("n_components", 2)
        if n_components < 2:
            self.logger.warning(
                "translocation direction: the double-Gaussian fit describes "
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
        fit_threshold_value = bt.get("threshold")
        if fit_threshold_value is None:
            raise RuntimeError(
                "the fit returned no 'threshold'; translocation direction "
                "cannot be classified without one"
            )
        threshold = float(fit_threshold_value)

        class_labels = (log_ecds_arr >= threshold).astype(int)
        forward_count = int(np.sum(class_labels == 1))
        backward_count = int(np.sum(class_labels == 0))

        # Per-event confidence that the assigned direction is correct - see
        # _classification_confidence for the derivation. Uses bt["params"]
        # as fit, which already reflects the constrained refit (and its
        # Gaussian-crossing threshold) when params_method is "constrained".
        confidence_values = self._classification_confidence(
            log_ecds_arr, bt["params"], class_labels.astype(bool)
        )

        for label, confidence_value, (ch, event_index) in zip(
            class_labels, confidence_values, event_refs
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
            f"Forward: {forward_count} ({forward_count/len(event_refs):.1%}), "
            f"Backward: {backward_count} ({backward_count/len(event_refs):.1%})"
        )

        self._translocation_direction_results = {
            "total_events": len(event_refs),
            "n_components": n_components,
            "forward_count": forward_count,
            "backward_count": backward_count,
            "lower_center": float(lower_center),
            "higher_center": float(higher_center),
            "threshold": float(threshold),
        }

        # The plot is built from the same histogram the fit used.
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
            arr_all = np.asarray(log_ecds_arr, dtype=float)
            arr = arr_all
            fig, ax = plt.subplots(figsize=(12, 6))

            # A non-zero dynamic range, or np.histogram warns.
            arr = self._jitter_degenerate_array(arr)

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
                        label="All Events",
                    )
                    hist_bins = bins
                except Exception:
                    ax.hist(
                        arr_all,
                        bins=100,
                        density=False,
                        alpha=0.5,
                        color="gray",
                        label="All Events",
                    )
                    hist_bins = None
            else:
                ax.hist(
                    arr_all,
                    bins=100,
                    density=False,
                    alpha=0.5,
                    color="gray",
                    label="All Events",
                )
                hist_bins = None

            class_mask = arr >= threshold
            forward_count = int(np.sum(class_mask))
            backward_count = int(len(arr) - forward_count)
            total_events_plot = len(arr)

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
            self._overlay_fitted_gaussians(
                ax,
                bt.get("params"),
                x_range,
                "Backward fit",
                "Forward fit",
                "translocation direction classification",
            )

            ax.axvline(threshold, color="black", linestyle="-", linewidth=2)

            try:
                pct_fwd = (
                    forward_count / total_events_plot if total_events_plot > 0 else 0.0
                )
                pct_bwd = (
                    backward_count / total_events_plot if total_events_plot > 0 else 0.0
                )
                info_text = (
                    f"Total Events: {total_events_plot}\n"
                    f"Forward: {forward_count} ({pct_fwd:.1%})\n"
                    f"Backward: {backward_count} ({pct_bwd:.1%})\n"
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
            ax.legend()
            plt.tight_layout()
            if plot_path is not None:
                plt.savefig(plot_path, dpi=300, bbox_inches="tight")
                self.logger.info(f"Translocation direction plot saved to {plot_path}")
            plt.close(fig)
        except Exception as e:
            self.logger.error(f"Error saving translocation direction plot: {e}")

    @log(logger=logger)
    def _classify_bound_star(self, channels: list[int]) -> None:
        """
        Identify the bound-star peak in each event and record which end of the
        molecule carried it through the pore, writing ``bound_star``.

        Called by ``_post_process_events``, last of the four classifiers. It
        runs last because it needs two things the earlier passes produce: the
        translocation direction, to turn "before or after the barcode in the
        trace" into "long or short end of the molecule", and the event
        sequences, which its report section is broken down by.

        A bound star shows up as a filter type -1 peak lying outside the type-3
        barcode - the tall spike that makes the pre- or post-barcode ECD large,
        and so the same feature ``_classify_translocation_direction`` reads a
        direction off. Only -1 peaks strictly before the first or strictly after
        the last type-3 peak are candidates: one sitting between them has no
        "first or last through the pore" reading. Where an event has several
        candidates the most prominent one wins, ties going to the earlier peak;
        the losing peaks keep their labels, so peak-filtering statistics are
        untouched by this pass.

        A candidate must also be *deeper than a fold*: its modal blockage has
        to clear the folded level - twice that event's unfolded level - by the
        higher filter threshold, in units of the local baseline noise. Position
        alone admits any unclassified blip at the edge of an event, and a -1
        label means only "no carrier band fits this", which a short fold
        satisfies as readily as a bound star does.

        The comparison is level against level: ``max_blockage`` is the modal
        blockage of the peak's own span and the unfolded level is the modal
        blockage of the event, both from ``find_mode_blockage_level``. Using
        the peak's raw extremum (``peak_height``) here does not work, and not
        marginally - the extremum sits deeper than that peak's own level by
        more than the tolerance itself, so it admits exactly the folds this is
        meant to reject.

        An event whose unfolded level was never determined - which is every
        event at once when folding classification declines - has no floor to
        test against and is counted apart rather than reported as starless.

        The label written to ``bound_star`` names the end of the construct the
        star is bound to - ``"long end"`` or ``"short end"`` - and is in the
        molecule's frame rather than the trace's: the observed temporal
        position is flipped for ``translocation_direction == "backward"``
        events, exactly as ``sequence`` is reversed for them, so ``"long end"``
        always means the star end entered the pore first however that event
        happened to thread. A star bound to one consistent end of the construct
        should therefore give one dominant label.

        This deliberately does not reuse the forward/backward vocabulary that
        ``translocation_direction`` owns. The two fields answer different
        questions - which way the construct threaded, and which end carries the
        star - and sharing one pair of words for both invited reading a
        disagreement between them where none exists.

        Counts are tallied both overall and per sequence, since which end
        carries the star is a property of the construct and a sequence that
        breaks the dominant pattern is the thing worth finding.

        The correction needs a direction, so an event carrying a star but no
        assigned ``translocation_direction`` - one whose pre- or post-barcode
        ECD was unusable, or every event if that pass declined outright - keeps
        ``bound_star`` as None. Those are counted separately rather than being
        folded in with the events that genuinely have no star.

        :param channels: List of channel indices to process
        :type channels: list[int]
        """
        results: Dict[str, Any] = {
            "total_events": 0,
            "sequence_events": 0,
            "with_star": 0,
            "long_end": 0,
            "short_end": 0,
            "multi_candidate": 0,
            "no_star": 0,
            "unresolved_direction": 0,
            "no_height_reference": 0,
        }
        # One bucket of the same counters per distinct sequence. `bucket` below
        # is None exactly when the event has no sequence to attribute it to,
        # which is also when the per-sequence totals must not move.
        per_sequence: Dict[str, Dict[str, int]] = {}
        results["per_sequence"] = per_sequence

        # The height floor is per-event (it scales with that event's own folded
        # level and baseline noise) but the multiplier is a setting, so it is
        # read once here.
        higher_threshold = float(
            self.settings.get("Higher Filter Threshold", {}).get("Value", 0)
        )

        for ch in channels:
            if ch not in self.sublevel_metadata:
                continue

            for event_index, sublevel_data in self.sublevel_metadata[ch].items():
                results["total_events"] += 1

                event_data = self.event_metadata.get(ch, {}).get(event_index)
                sequence = ""
                if event_data is not None and event_data.get("sequence"):
                    sequence = str(event_data["sequence"])

                bucket: Optional[Dict[str, int]] = None
                if sequence:
                    results["sequence_events"] += 1
                    bucket = per_sequence.setdefault(
                        sequence,
                        {
                            "events": 0,
                            "with_star": 0,
                            "long_end": 0,
                            "short_end": 0,
                            "no_star": 0,
                            "unresolved_direction": 0,
                            "no_height_reference": 0,
                        },
                    )
                    bucket["events"] += 1

                filtered_arr = np.asarray(
                    sublevel_data.get("filtered", []), dtype=float
                )
                if filtered_arr.size == 0:
                    continue

                type3_indices = np.where(
                    (~np.isnan(filtered_arr)) & (filtered_arr == 3)
                )[0]
                if type3_indices.size == 0:
                    # No barcode, so nothing for a star to be before or after.
                    if bucket is not None:
                        results["no_star"] += 1
                        bucket["no_star"] += 1
                    continue

                first_type3_idx = int(type3_indices[0])
                last_type3_idx = int(type3_indices[-1])

                prominences = np.asarray(
                    sublevel_data.get("prominence", []), dtype=float
                )
                blockages = np.asarray(
                    sublevel_data.get("max_blockage", []), dtype=float
                )

                # A -1 label only ever lands on a peak sublevel, and a peak
                # sublevel always carries a prominence and a blockage, so the
                # length and NaN guards here are defensive rather than expected
                # to fire.
                positional_candidates = [
                    int(idx)
                    for idx in np.where(
                        (~np.isnan(filtered_arr)) & (filtered_arr == -1)
                    )[0]
                    if (idx < first_type3_idx or idx > last_type3_idx)
                    and idx < prominences.size
                    and not np.isnan(prominences[idx])
                    and idx < blockages.size
                    and not np.isnan(blockages[idx])
                ]

                if not positional_candidates:
                    if bucket is not None:
                        results["no_star"] += 1
                        bucket["no_star"] += 1
                    continue

                # A star is deeper than a fold, not merely an unclassified
                # peak: its blockage must clear the folded level - twice this
                # event's unfolded level - by the higher filter threshold.
                #
                # Both sides of this comparison are modal blockage *levels*
                # from `find_mode_blockage_level`, which is what makes the
                # margin mean anything. Comparing the peak's raw extremum
                # (`peak_height`) against a level instead does not work: the
                # extremum sits well below the peak's own modal level, by more
                # than the tolerance itself, so folds pass a criterion meant to
                # reject them.
                height_floor = None
                if event_data is not None:
                    unfolded_level = event_data.get("unfolded_level")
                    baseline_stdev = event_data.get("baseline_stdev")
                    if (
                        isinstance(unfolded_level, (int, float))
                        and not isinstance(unfolded_level, bool)
                        and isinstance(baseline_stdev, (int, float))
                        and not isinstance(baseline_stdev, bool)
                        and not np.isnan(unfolded_level)
                        and not np.isnan(baseline_stdev)
                    ):
                        height_floor = 2.0 * float(
                            unfolded_level
                        ) + higher_threshold * float(baseline_stdev)

                if height_floor is None:
                    # The event has candidate peaks but no unfolded level to
                    # size them against, so whether any is a star cannot be
                    # decided. Counted apart from the events that genuinely
                    # have none: this fires for every event at once when
                    # folding classification declines, and that is worth
                    # seeing.
                    if bucket is not None:
                        results["no_height_reference"] += 1
                        bucket["no_height_reference"] += 1
                    continue

                candidate_indices = [
                    idx
                    for idx in positional_candidates
                    if blockages[idx] > height_floor
                ]

                if not candidate_indices:
                    if bucket is not None:
                        results["no_star"] += 1
                        bucket["no_star"] += 1
                    continue

                if bucket is not None and len(candidate_indices) > 1:
                    results["multi_candidate"] += 1

                # max() keeps the first of any equally prominent candidates, and
                # candidate_indices is in ascending sublevel order, so a tie
                # resolves to the earlier peak.
                star_index = max(
                    candidate_indices, key=lambda idx: float(prominences[idx])
                )
                star_is_before = star_index < first_type3_idx

                direction = None
                if event_data is not None:
                    raw_direction = event_data.get("translocation_direction")
                    if raw_direction in ("forward", "backward"):
                        direction = str(raw_direction)

                if direction is None:
                    if bucket is not None:
                        results["unresolved_direction"] += 1
                        bucket["unresolved_direction"] += 1
                    continue

                # A backward event ran the construct through in reverse, so a
                # star seen last in the trace went through the pore first.
                star_went_first = star_is_before == (direction == "forward")
                bound_star = "long end" if star_went_first else "short end"

                if event_data is not None:
                    event_data["bound_star"] = bound_star

                if bucket is not None:
                    results["with_star"] += 1
                    bucket["with_star"] += 1
                    if star_went_first:
                        results["long_end"] += 1
                        bucket["long_end"] += 1
                    else:
                        results["short_end"] += 1
                        bucket["short_end"] += 1

        self._bound_star_results: Dict[str, Any] = results

        self.logger.info(
            f"Bound star: {results['with_star']} of {results['sequence_events']} "
            f"sequence-bearing events carry one "
            f"(long end: {results['long_end']}, "
            f"short end: {results['short_end']}); "
            f"{results['unresolved_direction']} found a star but had no "
            f"translocation direction to correct against"
        )

    @log(logger=logger)
    def _collect_peak_statistics(self, channels: List[int]) -> None:
        """
        Tally peak counts by filter type across the whole run into
        ``self._peak_statistics``.

        Called by ``_classify_folded_unfolded`` - on every exit path, so the
        counts exist even when the folding fit declines - and again by
        ``report_channel_status``, which renders them as the report's peak
        filtering breakdown.

        Counts are taken over peak sublevels only, identified by ``peak_id``,
        and keyed by the ``filtered`` label. A peak whose label is NaN counts
        as rejected.

        :param channels: List of channel indices to process
        :type channels: List[int]
        """
        peak_type_counts: dict[int, int] = {}
        total_peaks = 0
        total_classified = 0
        total_unclassified = 0

        for ch in channels:
            if ch not in self.sublevel_metadata:
                continue

            for event_index in self.sublevel_metadata[ch]:
                sublevel_data = self.sublevel_metadata[ch][event_index]

                if "filtered" not in sublevel_data:
                    continue

                peak_ids = np.asarray(sublevel_data.get("peak_id", []), dtype=float)
                if peak_ids.size == 0:
                    continue

                # 'peak_id' marks peak positions (1..N) while 'filtered'
                # carries the assigned type per sublevel, NaN for non-peaks.
                filtered_arr = np.asarray(
                    sublevel_data.get("filtered", []), dtype=float
                )
                peak_mask = ~np.isnan(peak_ids)
                n_peaks_in_event = int(np.sum(peak_mask))
                if n_peaks_in_event <= 0:
                    continue

                total_peaks += n_peaks_in_event

                for idx in np.where(peak_mask)[0]:
                    try:
                        label = filtered_arr[idx]
                        if np.isnan(label):
                            peak_type_counts[-1] = peak_type_counts.get(-1, 0) + 1
                        else:
                            label_int = int(label)
                            peak_type_counts[label_int] = (
                                peak_type_counts.get(label_int, 0) + 1
                            )
                    except Exception:
                        peak_type_counts[-1] = peak_type_counts.get(-1, 0) + 1

                classified_arr = np.asarray(
                    sublevel_data.get("classified", []), dtype=float
                )
                if classified_arr.size > 0:
                    classified_peaks = classified_arr[peak_mask]
                    n_classified = int(np.sum(~np.isnan(classified_peaks)))
                    n_unclassified = int(np.sum(np.isnan(classified_peaks)))
                    total_classified += n_classified
                    total_unclassified += n_unclassified

        self._peak_statistics = {
            "total_peaks": int(total_peaks),
            "total_classified": int(total_classified),
            "total_unclassified": int(total_unclassified),
            "peak_type_counts": peak_type_counts,
        }

    @log(logger=logger)
    def _save_classification_report(self) -> None:
        """
        Write the run's classification report next to the event file.

        Called by ``_post_process_events`` as its last step. The body of the
        report is ``report_channel_status()`` with no channel, so the file and
        the status pane always say the same thing; this method adds the header,
        the settings the run used, and the footer, and writes the result to
        ``<event file stem>_classification_report.txt``.
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

            report_text = self.report_channel_status(channel=None, init=False)

            settings_section = "\n\nFITTING SETTINGS\n" + "-" * 80 + "\n"
            if self.settings:
                for key, setting_dict in sorted(self.settings.items()):
                    if key.lower() == "metaeventloader":
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

            header = (
                "=" * 80
                + "\nCLASSIFICATION REPORT: DNA Folding and Peak Analysis\n"
                + "=" * 80
                + "\n"
            )
            footer = "\n" + "=" * 80
            report_text = header + report_text.lstrip() + settings_section + footer

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

        Called by all three ``_classify_*`` methods, on the array they are about
        to fit, before it reaches ``fit_threshold``.

        A degenerate array here means empty, all-NaN, or having no dynamic range
        (``max - min <= 0``, including the single-valued case). An empty or
        all-NaN array is returned unchanged - jittering it would not make it
        histogrammable, it would only hide that it is empty/all-NaN - while a
        single-valued array is nudged by a tiny symmetric linspace so
        ``np.histogram`` has a non-zero bin range to work with.

        The degenerate cases are tested for explicitly rather than caught from
        ``np.nanmax``/``np.nanmin``, because those two do not fail uniformly:
        they raise ``ValueError`` on an empty array but merely warn and return
        ``nan`` on an all-NaN one. Catching would therefore handle only one of
        the two conditions this exists for, while also hiding any unrelated
        failure raised alongside it.

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

    @log(logger=logger)
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
        Draw the two fitted Gaussian components as dashed curves.

        One implementation, three call sites. The only thing that differs
        between the classifiers is what the two populations are called.

        The components are ordered by mean here rather than trusted to arrive
        in that order: ``curve_fit`` is free to return them either way round,
        so the colour and the label would otherwise swap between runs on the
        same data. Amplitudes are already in histogram-count units, so the
        curves need no rescaling to sit on the plotted bars.

        Nothing here rejects or raises. A plot that cannot draw this overlay is
        still worth producing, so every failure is logged and swallowed - but
        it is logged, so an absent curve can be told apart from a curve that
        was never attempted.

        :param ax: the matplotlib axes to draw onto
        :type ax: Any
        :param params: the six fitted parameters,
            ``(amp1, mean1, std1, amp2, mean2, std2)``, in either mean order,
            or None if the fit produced none
        :type params: Optional[Tuple[float, float, float, float, float, float]]
        :param x_range: x positions to evaluate the two curves at
        :type x_range: npt.NDArray[np.float64]
        :param lower_label: legend label for the lower-mean component
        :type lower_label: str
        :param higher_label: legend label for the higher-mean component
        :type higher_label: str
        :param context: classifier name, used to prefix log messages
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
            means = np.array([mean1, mean2], dtype=float)
            stds = np.array([std1, std2], dtype=float)
            amps = np.array([amp1, amp2], dtype=float)

            unusable = None
            if (
                np.any(np.isnan(means))
                or np.any(np.isnan(stds))
                or np.any(np.isnan(amps))
            ):
                unusable = "fitted parameters contain nan"
            elif np.any(stds <= 0):
                unusable = "non-positive fitted standard deviation"

            curves: List[npt.NDArray[np.float64]] = []
            order = np.argsort(means)
            if unusable is None:
                curves = [
                    amps[i] * np.exp(-0.5 * ((x_range - means[i]) / stds[i]) ** 2)
                    for i in order
                ]
                # A negative curve means the parameters are not describing a
                # population at all; draw neither rather than half a fit.
                if any(np.any(curve < -1e-12) for curve in curves):
                    unusable = "fitted curve is negative"

            if unusable is not None:
                self.logger.debug(
                    f"{context}: not drawing the fitted-Gaussian overlay: "
                    f"{unusable}."
                )
                return

            for curve, index, color, label in (
                (curves[0], order[0], "blue", lower_label),
                (curves[1], order[1], "red", higher_label),
            ):
                ax.plot(
                    x_range,
                    curve,
                    "--",
                    color=color,
                    label=f"{label} (mu={means[index]:.3f}, std={stds[index]:.3f})",
                )
        except Exception as e:
            self.logger.debug(
                f"{context}: failed to draw the fitted-Gaussian overlay: {e}",
                exc_info=True,
            )

    def _double_gaussian(
        self,
        x: npt.NDArray[np.float64],
        amp1: float,
        mean1: float,
        std1: float,
        amp2: float,
        mean2: float,
        std2: float,
    ) -> npt.NDArray[np.float64]:
        """
        Return the value of a double gaussian with the specified parameters.

        The parameter order is grouped **per component** - ``(amp, mean, std)``
        then ``(amp, mean, std)`` - rather than by kind. Every consumer of the
        ``"params"`` key must unpack in this order, and nothing can catch a
        mix-up automatically: any other grouping of the same six values is also
        a six-element tuple, so an arity check cannot tell them apart.

        Called by ``_curve_fit_bounded`` as the model handed to ``curve_fit``,
        and by ``_fit_double_gaussian_bounded_at_valley`` as the model inside
        its SLSQP objective. Undecorated by design: ``curve_fit`` calls this
        hundreds of times per fit, and a ``@log`` decorator here would flood
        the logfile.

        :param x: array of x values at which to calculate the double gaussian
        :type x: npt.NDArray[np.float64]
        :param amp1: amplitude of the first gaussian
        :type amp1: float
        :param mean1: mean of the first gaussian
        :type mean1: float
        :param std1: standard deviation of the first gaussian
        :type std1: float
        :param amp2: amplitude of the second gaussian
        :type amp2: float
        :param mean2: mean of the second gaussian
        :type mean2: float
        :param std2: standard deviation of the second gaussian
        :type std2: float
        :return: array of gaussian values at the given x positions
        :rtype: npt.NDArray[np.float64]
        """
        g1 = amp1 * np.exp(-((x - mean1) ** 2) / (2 * std1**2))
        g2 = amp2 * np.exp(-((x - mean2) ** 2) / (2 * std2**2))
        return g1 + g2

    @staticmethod
    def _gaussian_intersection(
        amp1: float,
        mean1: float,
        std1: float,
        amp2: float,
        mean2: float,
        std2: float,
    ) -> Optional[float]:
        """
        Return the x position between ``mean1`` and ``mean2`` where two
        Gaussians are equal, or None if they do not cross there.

        Called by ``_fit_double_gaussian_bounded_at_valley``, on the parameters
        of its constrained refit, to place the classification threshold.

        Both curves are strictly positive everywhere, so ``g1(x) == g2(x)``
        has exactly the same solutions as ``ln(g1(x)) == ln(g2(x))``, and
        each ``ln(g_k(x)) = ln(amp_k) - (x - mean_k)**2 / (2 * std_k**2)`` is
        an honest quadratic in ``x``. Subtracting the two gives another
        quadratic, ``a*x**2 + b*x + c == 0``, with at most two real roots
        over the whole real line - not just between the means - so this is
        an exact, closed-form solve rather than a numeric root search.

        A crossing between the two means is not guaranteed by construction:
        it exists only when each Gaussian is larger than the other at its
        own mean (``g1(mean1) > g2(mean1)`` and ``g2(mean2) > g1(mean2)``),
        i.e. when each population actually dominates its own centre. That is
        exactly the condition
        ``_fit_double_gaussian_bounded_at_valley`` enforces as a fit
        constraint, so a None here from that caller's output would mean the
        constraint itself failed to hold - it should not happen, but this
        still returns None rather than an out-of-range root so a caller
        cannot mistake a tail-region crossing for the boundary between the
        two populations.

        :param amp1: amplitude of the first gaussian
        :type amp1: float
        :param mean1: mean of the first gaussian
        :type mean1: float
        :param std1: standard deviation of the first gaussian
        :type std1: float
        :param amp2: amplitude of the second gaussian
        :type amp2: float
        :param mean2: mean of the second gaussian
        :type mean2: float
        :param std2: standard deviation of the second gaussian
        :type std2: float
        :return: the x position in [min(mean1, mean2), max(mean1, mean2)]
            where the two curves are equal, or None if amp1/amp2 are not
            both positive, or the two curves do not cross between the means
        :rtype: Optional[float]
        """
        if amp1 <= 0 or amp2 <= 0:
            return None

        lo, hi = sorted((mean1, mean2))

        a = 1.0 / (2.0 * std2**2) - 1.0 / (2.0 * std1**2)
        b = mean1 / std1**2 - mean2 / std2**2
        c = (
            -(mean1**2) / (2.0 * std1**2)
            + (mean2**2) / (2.0 * std2**2)
            - np.log(amp2 / amp1)
        )

        if abs(a) < 1e-12:
            # Equal-variance case: the quadratic term vanishes and the
            # crossing condition is linear in x.
            if abs(b) < 1e-12:
                return None
            root = -c / b
            return float(root) if lo <= root <= hi else None

        discriminant = b * b - 4.0 * a * c
        if discriminant < 0:
            return None

        sqrt_disc = np.sqrt(discriminant)
        roots = ((-b + sqrt_disc) / (2.0 * a), (-b - sqrt_disc) / (2.0 * a))
        in_range = [float(r) for r in roots if lo <= r <= hi]
        if not in_range:
            return None
        # Both quadratic roots can land inside [lo, hi] in principle; the one
        # nearer the midpoint is the meaningful separating crossing rather
        # than a second one close to an endpoint.
        midpoint = (lo + hi) / 2.0
        return min(in_range, key=lambda r: abs(r - midpoint))

    def _curve_fit_bounded(
        self,
        bins: npt.NDArray[np.float64],
        amplitude: npt.NDArray[np.float64],
        p0: Tuple[float, float, float, float, float, float],
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Run the bounded double-Gaussian ``curve_fit`` from a given initial guess.

        Called by ``_fit_double_gaussian``, once per initial guess.

        Both of ``_fit_double_gaussian``'s initial guesses are fit against the
        same box, so it lives here once: amplitudes non-negative and no larger
        than the tallest bin, means inside the histogram, and widths between
        half a bin and the histogram's span.

        The lower width bound is half a bin rather than zero because at
        ``std == 0`` the model divides by zero - it evaluates to 0 away from
        the mean and ``nan`` at it, so the component silently vanishes from the
        curve and drags a ``nan`` onto the plot. Nothing narrower than the
        binning is meaningful for a binned fit anyway. The initial guess is
        clamped up to the same floor so it cannot start outside its own bounds.

        Nothing is caught here. ``curve_fit`` raises ``RuntimeError`` when the
        least-squares fit does not converge and ``ValueError`` when the guess
        or bounds are unusable, and both propagate to ``_fit_double_gaussian``,
        which is where the decision to fall through to the next initial guess
        belongs.

        :param bins: histogram bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts
        :type amplitude: npt.NDArray[np.float64]
        :param p0: initial guess, ``(amp1, mean1, std1, amp2, mean2, std2)``
        :type p0: Tuple[float, float, float, float, float, float]
        :return: tuple of (best-fit parameters, parameter covariance matrix)
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
        """
        min_mean = np.min(bins)
        max_mean = np.max(bins)
        min_amp = 0
        max_amp = np.max(amplitude)
        min_std = (bins[1] - bins[0]) / 2.0
        max_std = np.abs(bins[-1] - bins[1])

        p0 = cast(
            Tuple[float, float, float, float, float, float],
            tuple(max(v, min_std) if i in (2, 5) else v for i, v in enumerate(p0)),
        )

        return curve_fit(
            self._double_gaussian,
            bins,
            amplitude,
            p0=p0,
            bounds=(
                [min_amp, min_mean, min_std, min_amp, min_mean, min_std],
                [max_amp, max_mean, max_std, max_amp, max_mean, max_std],
            ),
        )

    @log(logger=logger)
    def _resolve_two_histogram_peaks(
        self, bins: npt.NDArray[np.float64], amplitude: npt.NDArray[np.float64]
    ) -> Optional[
        Tuple[
            npt.NDArray[np.intp],
            npt.NDArray[np.float64],
            npt.NDArray[np.float64],
            npt.NDArray[np.float64],
        ]
    ]:
        """
        Locate the two most prominent histogram peaks that are far enough apart
        to describe separate modes, and measure them.

        Called by ``_fit_double_gaussian`` for its first-stage initial guess, and
        by ``_warn_if_fitted_means_are_off_their_peaks`` for the half-maximum
        spans it checks the fitted means against.

        Two maxima are only accepted as separate modes when they are at least
        one dominant-peak FWHM apart. Without that rule ``find_peaks`` returns
        two maxima a few bins apart on the flank of a single mode - counting
        noise on a tall bin clears the 5%-of-maximum prominence floor easily -
        and treating those as two populations produces a second component of
        near-zero width that contributes nothing. Deriving the distance from
        the dominant peak's own measured width rather than fixing it in bins
        keeps the criterion meaningful across binnings: two modes closer
        together than one linewidth are not resolved by this histogram anyway.

        Returning None means "this histogram does not resolve two modes", which
        is a normal answer rather than a failure, and each caller has its own
        correct response to it.

        The single ``peak_widths`` call serves both callers: the widths seed
        the double-Gaussian fit's standard deviations, and the interpolated
        edge positions bound each peak's half-maximum span.

        :param bins: histogram bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts
        :type amplitude: npt.NDArray[np.float64]
        :return: tuple of (indices of the two peaks, ordered by *descending
            prominence*; their widths in bins; their left and right
            interpolated edge positions at half maximum, in bin-index units),
            or None if the histogram does not resolve two separated peaks
        :rtype: Optional[Tuple[npt.NDArray[np.intp], npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        """
        max_amplitude = float(np.max(amplitude))
        if max_amplitude <= 0:
            return None

        min_prominence = max_amplitude * 0.05
        peaks, properties = find_peaks(amplitude, prominence=min_prominence)
        if peaks.size < 2:
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
        if peaks.size < 2:
            return None

        top_two_peaks = peaks[np.argsort(properties["prominences"])[-2:][::-1]]
        widths, _, left_ips, right_ips = peak_widths(
            amplitude, top_two_peaks, rel_height=0.5
        )
        return top_two_peaks, widths, left_ips, right_ips

    @log(logger=logger)
    def _fit_double_gaussian(
        self, bins: npt.NDArray[np.float64], amplitude: npt.NDArray[np.float64]
    ) -> Tuple[Optional[npt.NDArray[np.float64]], Optional[npt.NDArray[np.float64]]]:
        """
        Attempt to fit a double gaussian to a histogram, or return (None, None).

        Called by ``_fit_and_check_double_gaussian``, which is the only caller and
        the only place its result is judged.

        The initial guess is made in two stages: first from the two most
        prominent resolved histogram peaks and their FWHM, and - if the
        histogram does not resolve two peaks, or the fit from them does not
        converge - from splitting the histogram in half about its
        5%-of-maximum support and taking the argmax of each side. The second
        stage structurally yields one seed per half, so it stays well behaved
        on a single broad mode, where the first stage has nothing to offer.

        :param bins: numpy array of bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: numpy array of amplitude (counts) in each bin
        :type amplitude: npt.NDArray[np.float64]
        :return: tuple of (best-fit parameters (amp1, mean1, std1, amp2, mean2,
            std2), parameter covariance matrix), or (None, None) if both stages
            fail
        :rtype: Tuple[Optional[npt.NDArray[np.float64]], Optional[npt.NDArray[np.float64]]]
        :raises ValueError: if too few peaks are found for the first-stage guess,
            or the histogram cannot be split for the second-stage guess; both are
            caught by this method's own fallback logic and never propagate to the
            caller, which sees (None, None) instead
        """
        bin_width = bins[1] - bins[0]
        try:
            resolved = self._resolve_two_histogram_peaks(bins, amplitude)
            if resolved is None:
                # Not a failure - the histogram-split guess below picks one
                # seed per half and is the better-behaved path on the single
                # broad mode this rejects.
                raise ValueError(
                    "the histogram does not resolve two separated peaks; "
                    "deferring to the histogram-split initial guess"
                )
            top_two_peaks, widths, _, _ = resolved

            std_guesses = widths * bin_width / 2.355

            p0 = (
                amplitude[top_two_peaks[0]],
                bins[top_two_peaks[0]],
                std_guesses[0],
                amplitude[top_two_peaks[1]],
                bins[top_two_peaks[1]],
                std_guesses[1],
            )
            return self._curve_fit_bounded(bins, amplitude, p0)
        except (RuntimeError, ValueError):
            try:
                n = len(amplitude)
                amax = np.max(amplitude)
                left_start = 0
                # The bounds test comes before the index test in both loops so
                # that a histogram where no bin reaches 5% of the maximum walks
                # off the end rather than raising IndexError. The argmax bin
                # always clears that floor for a real histogram, so this guards
                # a case that should not arise rather than one that does.
                while left_start < n and amplitude[left_start] < 0.05 * amax:
                    left_start += 1
                right_start = n - 1
                while right_start > 0 and amplitude[right_start] < 0.05 * amax:
                    right_start -= 1

                if left_start >= right_start:
                    raise ValueError(
                        "Cannot determine where to split the histogram for initial guess"
                    )

                left = amplitude[left_start : (left_start + right_start) // 2]
                right = amplitude[(left_start + right_start) // 2 : right_start]

                leftmax = np.max(left)
                leftargmax = np.argmax(left)

                rightmax = np.max(right)
                rightargmax = np.argmax(right)

                left_half_max = leftmax / 2.0
                idx_left = leftargmax
                while idx_left > 0 and left[idx_left] > left_half_max:
                    idx_left -= 1

                left_dist = abs(
                    bins[left_start + idx_left] - bins[left_start + leftargmax]
                )
                left_std_guess = left_dist / 1.177

                right_half_max = rightmax / 2.0
                idx_right = rightargmax
                while idx_right > 0 and right[idx_right] > right_half_max:
                    idx_right -= 1

                right_dist = abs(
                    bins[(left_start + right_start) // 2 + idx_right]
                    - bins[(left_start + right_start) // 2 + rightargmax]
                )
                right_std_guess = right_dist / 1.177

                p0 = (
                    leftmax,
                    bins[left_start + leftargmax],
                    left_std_guess,
                    rightmax,
                    bins[(left_start + right_start) // 2 + rightargmax],
                    right_std_guess,
                )
                return self._curve_fit_bounded(bins, amplitude, p0)
            except (RuntimeError, ValueError, IndexError):
                return None, None

    @log(logger=logger)
    def _fit_and_check_double_gaussian(
        self, bins: npt.NDArray[np.float64], amplitude: npt.NDArray[np.float64]
    ) -> Tuple[Optional[npt.NDArray[np.float64]], bool]:
        """
        Fit a double gaussian and apply convergence checks only.

        Called by ``fit_threshold``, as the joint fit whose parameters every later
        stage - the threshold search, the constrained refit, the confidences and
        the plots - is derived from.

        **Only convergence failures reject.** A fit that converged but looks
        statistically questionable is reported and allowed through, so it
        reaches the classifier and shows up in its counts and plots rather than
        becoming a silent ``None``. A fit that is quietly discarded is
        indistinguishable from data that never had two populations in it, and
        the failure rate on real recordings is worth being able to see.

        Three non-fatal diagnostics are therefore checked, because a converged
        fit is not the same as a meaningful one. The first two both mean the
        data supports one population rather than two, and are folded into this
        method's second return value so a caller can act on that instead of
        only seeing it in the log:

        - **A collapsed component.** A fitted standard deviation at or below one
          bin describes a spike the histogram cannot resolve; that component
          contributes essentially nothing, the fit is a single Gaussian wearing
          two sets of parameters, and any threshold taken from the midpoint of
          the two means is meaningless because one of those means is a phantom.
        - **Centres that are not separated.** Two fitted means closer together
          than one FWHM of the narrower component describe a single mode, no
          matter how good the residual looks. This is the same criterion stage 1
          of ``_fit_double_gaussian`` applies to its seeds, applied to the
          result, and it is the case the first diagnostic misses: two
          components of comparable, non-degenerate width sitting on top of one
          another.
        - **Unconstrained parameters.** A standard error more than ten times the
          parameter it belongs to means the data does not determine that
          parameter at all. This one is deliberately *not* folded into the
          one-population signal below: it also fires on a genuinely bimodal but
          small or heavily overlapping dataset, which is a precision problem
          rather than a population-count one.

        :param bins: numpy array of bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: numpy array of amplitude (counts) in each bin
        :type amplitude: npt.NDArray[np.float64]
        :return: tuple of (fit parameters (amp1, mean1, std1, amp2, mean2,
            std2), or None if the fit did not converge or produced a
            non-finite covariance) and a bool that is True when the converged
            fit describes one population rather than two (a collapsed
            component, or two centres on the same mode). The bool is
            meaningless when the first element is None.
        :rtype: Tuple[Optional[npt.NDArray[np.float64]], bool]
        """
        popt, pcov = self._fit_double_gaussian(bins, amplitude)

        if popt is None or pcov is None:
            self.logger.debug("double-Gaussian fit did not converge")
            return None, False

        if np.any(np.isinf(pcov)) or np.any(np.isnan(pcov)):
            self.logger.debug(
                "double-Gaussian fit converged but produced a non-finite "
                "covariance matrix"
            )
            return None, False

        # Non-fatal diagnostics. None of them reject the fit; they exist so
        # that a converged-but-meaningless fit is visible in the log instead
        # of being indistinguishable from a good one, and so the first two
        # can drive the one-vs-two-population decision returned below.
        names = ("amp1", "mean1", "std1", "amp2", "mean2", "std2")
        bin_width = float(bins[1] - bins[0])
        one_population = False

        for comp, std_idx, mean_idx in ((1, 2, 1), (2, 5, 4)):
            if popt[std_idx] <= bin_width:
                one_population = True
                self.logger.warning(
                    f"double-Gaussian fit: component {comp} collapsed to "
                    f"std={popt[std_idx]:.4g}, at or below the {bin_width:.4g} "
                    "bin width. It contributes nothing to the fitted curve, so "
                    f"its centre ({popt[mean_idx]:.4g}) and any threshold "
                    "derived from it are not meaningful - this is effectively a "
                    "single-Gaussian fit."
                )

        # The same separation criterion stage 1 applies to its seeds, applied to
        # the fitted result. Two centres closer together than one linewidth are
        # describing a single mode, whatever the fit residual says. This catches
        # the case the first diagnostic misses: two components of comparable,
        # non-degenerate width sitting on top of each other.
        narrower_fwhm = 2.355 * min(float(popt[2]), float(popt[5]))
        centre_separation = abs(float(popt[1]) - float(popt[4]))
        if centre_separation < self.SEED_SEPARATION_FWHM * narrower_fwhm:
            one_population = True
            self.logger.warning(
                f"double-Gaussian fit: the two fitted centres ({popt[1]:.4g} and "
                f"{popt[4]:.4g}) are {centre_separation:.4g} apart, less than the "
                f"{narrower_fwhm:.4g} FWHM of the narrower component. They "
                "describe one mode rather than two populations, so any threshold "
                "taken from their midpoint is arbitrary."
            )

        perr = np.sqrt(np.diag(pcov))
        unconstrained = perr > np.abs(popt) * 10
        if np.any(unconstrained):
            detail = ", ".join(
                f"{names[i]}={popt[i]:.4g}+/-{perr[i]:.4g}"
                for i in np.flatnonzero(unconstrained)
            )
            self.logger.warning(
                "double-Gaussian fit: the data does not constrain "
                f"{np.count_nonzero(unconstrained)} of 6 parameters (standard "
                f"error exceeds 10x the value): {detail}. The fit converged but "
                "these parameters carry no information."
            )

        return popt, one_population

    @log(logger=logger)
    def _warn_if_fitted_means_are_off_their_peaks(
        self,
        bins: npt.NDArray[np.float64],
        amplitude: npt.NDArray[np.float64],
        params: Tuple[float, float, float, float, float, float],
    ) -> None:
        """
        Warn when a fitted mean lands outside the half-maximum span of the
        histogram peak it is supposed to be describing.

        Called by ``fit_threshold`` on the final parameters, after any constrained
        refit, so what is checked is what the plots draw and the classifiers use.
        Returns nothing and rejects nothing.

        This uses the half-maximum spans ``_resolve_two_histogram_peaks``
        measures, and it is deliberately a **warning rather than a bound** on
        the fitted means. Those spans are only defined when the histogram
        resolves two separated peaks, which on skewed data it often does not.
        Across a benchmark of real and reconstructed distributions the spans
        existed only for the well-separated cases, where a mean bound would be
        inert anyway, and for none of the skewed ones where such a bound would
        actually bind: availability is inverted against need. Deriving spans
        some other way (the tallest bin either side of the valley) makes them
        always available but yields zero-width spans wherever that bin is not a
        topographic peak, which turns a sixth of the fits infeasible.

        Bounding would also convert ``find_peaks``' judgement into something
        the optimizer cannot escape, where today a mis-detected peak only
        produces a poor *seed* that the fit can walk away from. A warning
        carries none of that risk: it cannot make a fit infeasible and it
        cannot move a threshold. It catches a failure that is otherwise visible
        only by eye on the plot - a higher component sitting several hundred pA
        below the histogram's visible second mode, because the component is
        describing the lower population's skewed shoulder rather than its own
        data.

        Deliberately silent rather than noisy in every ambiguous case. It skips
        entirely unless the histogram resolves two peaks under the same
        prominence floor and ``SEED_SEPARATION_FWHM`` separation rule stage 1
        applies to its seeds, so single-population data - where the higher
        component correctly describes a sparse region and has no peak of its
        own - does not produce a warning, and neither does a histogram whose
        only two maxima are a mode and a noise wiggle on its flank.

        :param bins: histogram bin centers, as built for the double-Gaussian fit
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts, as built for the double-Gaussian fit
        :type amplitude: npt.NDArray[np.float64]
        :param params: the six fitted parameters being reported,
            ``(amp1, mean1, std1, amp2, mean2, std2)``, in either mean order
        :type params: Tuple[float, float, float, float, float, float]
        :return: None; this only logs
        :rtype: None
        """
        try:
            bin_width = float(bins[1] - bins[0])
            if bin_width <= 0:
                return
            resolved = self._resolve_two_histogram_peaks(bins, amplitude)
            if resolved is None:
                return
            top_two, _, left_ips, right_ips = resolved
            # `_resolve_two_histogram_peaks` orders by prominence; re-order all
            # three arrays together by position so index 0 is the lower mode.
            by_position = np.argsort(bins[top_two])
            top_two = top_two[by_position]
            left_ips = left_ips[by_position]
            right_ips = right_ips[by_position]
        except Exception as e:
            self.logger.debug(
                f"could not check the fitted means against the histogram's "
                f"peaks: {e}",
                exc_info=True,
            )
            return

        _, mean1, _, _, mean2, _ = params
        ordered_means = sorted((float(mean1), float(mean2)))

        for index, (label, fitted_mean) in enumerate(
            zip(("lower", "higher"), ordered_means)
        ):
            # `left_ips`/`right_ips` are in bin-index units, not current -
            # they have to be mapped back onto the bin centers before they can
            # be compared against a fitted mean in pA.
            span_low = float(bins[0]) + float(left_ips[index]) * bin_width
            span_high = float(bins[0]) + float(right_ips[index]) * bin_width
            if span_high <= span_low:
                continue
            if span_low <= fitted_mean <= span_high:
                continue
            peak_position = float(bins[top_two[index]])
            self.logger.warning(
                f"double-Gaussian fit: the {label} component's mean "
                f"({fitted_mean:.4g}) falls outside the half-maximum span "
                f"[{span_low:.4g}, {span_high:.4g}] of the histogram peak it "
                f"should describe, whose maximum is at {peak_position:.4g}. "
                "The component is not centred on the mode it is meant to "
                "represent - on right-skewed data this usually means it has "
                "been pulled into the other population's shoulder, and its "
                "reported mean and width describe neither population "
                "cleanly."
            )

    @log(logger=logger)
    def _histogram_for_fit(
        self, data: npt.NDArray[np.float64]
    ) -> Tuple[
        npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]
    ]:
        """
        Bin 1-D data for double-Gaussian fitting using the Freedman-Diaconis rule.

        Called by ``fit_threshold``, once, on the data to be classified. The
        histogram it returns is the only one in the pipeline: the fit, the
        threshold search, the spline and the plots all reuse these bins.

        Freedman-Diaconis sets bin width from the interquartile range, which
        misbehaves on exactly the data these classifiers exist to separate: two
        populations inflate the IQR, and therefore the bin width, collapsing
        the histogram to a handful of bins. Measured on synthetic
        two-population data (means 300 and 600), the rule alone yields 3 bins
        at n=60, 6 at n=300 and 7 at n=600 - against which a six-parameter
        double Gaussian is underdetermined. The fit then fails outright below
        roughly 600 points and, worse, near 600-1000 it can converge with
        *both* Gaussians sitting on the same mode (595.4 and 597.3 for a
        300/600 dataset) while passing every convergence check.

        Hence the ``MIN_FIT_BINS`` floor, with which the same synthetic data
        resolves correctly at every size tested from n=60 to n=20000. The rule
        is otherwise unmodified, so bin count is not a confounding variable
        when comparing fits across datasets.

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
                "six-parameter double-Gaussian fit is not underdetermined."
            )
            s_bins = self.MIN_FIT_BINS

        counts, bin_edges = np.histogram(arr, bins=s_bins)
        bin_centers = (bin_edges[1:] + bin_edges[:-1]) / 2.0
        return counts.astype(float), bin_edges, bin_centers

    @log(logger=logger)
    def fit_threshold(self, data: npt.NDArray[np.float64]) -> Dict[str, Any]:
        """
        Estimate a binary threshold from 1-D data by fitting a double Gaussian.

        Shared by all three ``_classify_*`` methods and their plotting code,
        which consume the returned dict generically. ``"params"`` is ordered
        per component, ``(amp1, mean1, std1, amp2, mean2, std2)``; the key is
        called ``"threshold"`` rather than anything implying a midpoint,
        because it is placed from the histogram's shape (see
        ``_threshold_between_populations``) and is not the midpoint of anything.

        **This raises when the fit fails rather than falling back to raw
        histogram peak locations.** A failed fit is a result worth seeing, not
        one worth papering over: a fallback would make "no two populations
        here" indistinguishable from "two populations, found and measured".

        A fitted double Gaussian always has two centres, whether or not the
        data actually contains two populations - on genuinely unimodal data it
        either collapses one component or converges with both centres on the
        same mode, both diagnosed by ``_fit_and_check_double_gaussian``.
        ``"n_components"`` surfaces that diagnosis as ``1`` or ``2`` so a
        caller can act on it directly instead of only finding it in the log.

        Where the threshold came from an actual feature of the curve - a valley
        between the two centres, or the above-floor fallback on single-population
        data - the two components are then re-fit jointly, with each mean hard-
        bounded to its own side of that point, and the reported ``"threshold"``
        is replaced by the x position where the two refit curves cross. See
        ``_fit_double_gaussian_bounded_at_valley`` and ``_gaussian_intersection``.
        This also happens on single-population data, where the higher component
        ends up describing only the sparse region above the threshold and so has
        a small amplitude. ``"params_method"`` records whether this ran and
        succeeded (``"constrained"``) or not (``"joint"``): when it is
        ``"joint"``, ``"threshold"`` is still the raw valley/floor value
        ``_threshold_between_populations`` found; when it is ``"constrained"``,
        ``"threshold"`` is the Gaussian crossing instead, which is also exactly
        where ``_classification_confidence`` reads 0.5, so the shape-based
        label and the Gaussian-mixture vote agree exactly at the boundary.
        The two ``fallback`` methods are excluded from this entirely: those
        thresholds are not read off any feature, and ``fallback_degenerate`` is
        the midpoint of two co-located means, so constraining a refit there
        would carve one mode arbitrarily in half.

        :param data: 1-D array of values from which to estimate a binary threshold
        :type data: npt.NDArray[np.float64]
        :return: dict with keys ``"threshold"`` (float), ``"centers"``
            (np.ndarray of the two fitted means), ``"hist"``
            (tuple of counts and bin edges), ``"params"``
            (tuple of the six fitted parameters), ``"n_components"``
            (``1`` if the fit describes one population, ``2`` if it describes
            two), ``"threshold_method"`` (how the valley/floor point that
            anchored the fit was picked - see ``_threshold_between_populations``;
            unaffected by whether the constrained refit below ran), ``"spline"``
            (the smoothing spline that search was run on, or None) paired with
            ``"spline_domain"`` (the populated core it was fit over; the
            returned ``BSpline`` extrapolates without bound outside those
            knots, so any consumer must clip to it), and
            ``"params_method"`` (``"constrained"`` if the components
            were re-fit jointly with their means bounded at that point and
            ``"threshold"`` replaced by their crossing, ``"joint"`` if
            ``"params"`` and ``"threshold"`` are straight from the
            unconstrained double-Gaussian fit and ``_threshold_between_populations``
            respectively)
        :rtype: Dict[str, Any]
        :raises ValueError: if the data cannot be histogrammed, or if the
            double-Gaussian fit fails to converge
        """
        counts, bin_edges, bin_centers = self._histogram_for_fit(data)

        popt, one_population = self._fit_and_check_double_gaussian(bin_centers, counts)
        if popt is None:
            raise ValueError(
                "could not fit a double Gaussian to the histogram of this data"
            )

        amp1, mean1, std1, amp2, mean2, std2 = (float(p) for p in popt)

        threshold, threshold_method, spline = self._threshold_between_populations(
            data, bin_centers, counts, mean1, std1, mean2, std2, one_population
        )

        # Constrain and re-fit wherever the threshold came from an actual
        # feature of the curve, which is both spline-derived methods. That
        # includes the single-population case: the higher component then has
        # only the sparse region above the threshold to describe and comes
        # back with a small amplitude, which is the honest answer - far
        # better than leaving it sitting on top of the lower component, where
        # it claims a second population that was explicitly not found. The
        # two `fallback` methods are excluded: those thresholds are not read
        # off any feature, and `fallback_degenerate` is the midpoint of two
        # co-located means, so constraining a refit there would carve one
        # mode arbitrarily in half.
        params_method = "joint"
        if threshold_method in ("spline_valley", "spline_valley_above_floor"):
            constrained = self._fit_double_gaussian_bounded_at_valley(
                bin_centers, counts, threshold, popt
            )
            if constrained is not None:
                fit, crossing = constrained
                amp1, mean1, std1, amp2, mean2, std2 = (float(p) for p in fit)
                threshold = crossing
                params_method = "constrained"

        # Report - never reject - a component that is not centred on the mode
        # it is supposed to describe. Run on the final parameters rather than
        # the joint fit's, so what is checked is what the plots draw and the
        # classifiers consume, on both the constrained and the fallback path.
        self._warn_if_fitted_means_are_off_their_peaks(
            bin_centers, counts, (amp1, mean1, std1, amp2, mean2, std2)
        )

        # Recomputed rather than threaded out of `_threshold_between_populations`,
        # so that method's return signature stays (threshold, method, spline).
        # It is a pure function of `bin_centers`/`counts`, already in hand here,
        # so recomputing it costs one more cumulative sum, not another fit.
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
            "params_method": params_method,
        }

    def _trim_to_populated_core(
        self,
        bins: npt.NDArray[np.float64],
        amplitude: npt.NDArray[np.float64],
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Drop the near-empty edges of a histogram before it reaches the
        smoothing-spline machinery.

        Called by ``fit_threshold`` to set the domain the spline is drawn over, and
        by ``_threshold_between_populations`` to set the domain it is fit over.

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
        by any data there. On a single-population prominence distribution,
        fitting across the full range drove the curve well below zero counts
        and fabricated a peak hundreds of counts high where the raw histogram
        was within noise of zero; restricting the fit to the populated core
        removed both.

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

        Called by ``_threshold_between_populations``, which uses the returned curve
        to place the threshold at a valley.

        ``make_smoothing_spline`` will select its own smoothing by generalized
        cross-validation if ``lam`` is not given, and that is not good enough
        here: GCV optimizes predictive error, not shape, and on counting data
        it reliably under-smooths. On bimodal prominence distributions it
        leaves several local minima between the two fitted centres, where the
        threshold search wants exactly one. Every extra minimum is a Poisson
        wiggle that the deepest-valley search can return instead of the real
        boundary.

        **A fixed ``lam`` is not an option either, which is why this is a
        ladder rather than a constant.** ``make_smoothing_spline``
        minimizes ``sum(residuals**2) + lam * integral(f''**2)``, and since
        ``f''`` scales as (y-range)/(x-range)**2, the penalty term carries a
        factor of ``(y-range)**2 / (x-range)**3``. A ``lam`` tuned on one
        dataset is therefore meaningless on another with a different current
        range - the same numeric ``lam`` on the same data relabelled from pA to
        nA gives a completely different fit. Expressing it as
        ``lam = lam_shape * x_range**3`` removes that dependence exactly
        (verified: identical fits across unit systems; the y-scale genuinely
        does not matter, only x). But even in that scale-free form no single
        ``lam_shape`` works: searching the band of values giving exactly one
        minimum across four datasets produced ``2.55e-06 .. 4.24e-03`` on
        well-separated bimodal data against ``1.66e-07 .. 2.45e-07`` on a
        skewed one - **non-overlapping**, an order of magnitude apart, and on
        the most skewed dataset the band was a single point. There is no
        constant to pick, and no simple function of bin count either: bin count
        rose 33 -> 62 across those datasets while the required ``lam_shape``
        *fell*, so any ``+log(n_bins)`` term moves the wrong way.

        The ladder sidesteps the whole question. It walks ``lam_shape`` upward
        in log-spaced steps from almost no smoothing and stops at the first
        value whose fitted curve is quiet enough, so it lands inside whatever
        band a given dataset has without that band ever being named. The count
        of local minima is a monotone non-increasing step function of
        ``lam_shape`` (verified over 25 decades), so the first acceptable
        candidate is also the least-smoothed one - which matters more than it
        may appear, because over-smoothing washes out the real valley just as
        surely as under-smoothing buries it in noise. See
        ``SPLINE_LAMBDA_MARGIN_STEPS`` for the measurement showing that even
        two steps of "safety margin" past this point does substantially more
        harm than the noise it was meant to guard against.

        Accepting *at most* ``SPLINE_MAX_MINIMA`` rather than exactly that many
        is deliberate: zero minima is the correct and expected outcome on
        genuinely single-population data, where there is no valley to find and
        the caller falls through to its above-floor search.

        :param bins: histogram bin centers, as built for the double-Gaussian fit
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts, as built for the double-Gaussian fit
        :type amplitude: npt.NDArray[np.float64]
        :param search_lo: lower end of the bracket the caller will search for a
            valley, and so the bracket whose wiggles matter here
        :type search_lo: float
        :param search_hi: upper end of that bracket
        :type search_hi: float
        :return: the least-smoothed ``BSpline`` meeting the criterion, or None
            if the histogram is too small, the bracket is empty, or no
            candidate on the ladder was quiet enough - in which case the caller
            has no spline at all and places its threshold from the data instead
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
                f"between {search_lo:.4g} and {search_hi:.4g}; no spline will "
                "be used and the threshold will come from the data instead."
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
        own shape.

        Called by ``fit_threshold`` once the double Gaussian has converged. Returns
        the threshold, the name of the rung that produced it (which becomes
        ``threshold_method``), and the spline, if one was fit, for the plots.

        A smoothing spline (see ``_fit_least_smoothed_spline``, which chooses
        its smoothing) is fit to the populated core of the same histogram
        (``bins``, ``amplitude``, trimmed by ``_trim_to_populated_core``) the
        double-Gaussian fit used, and evaluated on a fine grid between the two
        fitted means. If that smoothed curve has a local minimum in between -
        an actual valley separating the two modes - the threshold is placed
        there, taking the deepest if more than one is found.

        Reading the boundary off the curve matters most where it differs most
        from the midpoint of the two means: when one population heavily
        outnumbers the other the true valley sits well off-centre, pulled
        toward the smaller one, and a midpoint would cut into it.

        **The between-centres search is skipped entirely when ``one_population``
        is set**, and this matters more than it sounds. On single-population data
        both fitted centres land on the same mode, so the bracket between them is
        narrow and contains no boundary between anything - but it is not empty.
        Beside a tall peak the spline wiggles on counting noise alone, and the
        search will happily return one of those wiggles - a threshold placed a
        few tens of pA off a single mode, from Poisson noise on bins deep inside
        that mode. Skipping the search is the fix; narrowing what counts as a
        valley would not be, because there is no correct answer inside that
        bracket.

        With the search skipped or unsuccessful, the threshold instead becomes the
        **first** local minimum of the same spline above the floor
        ``2 * mean1 - 2 * std1``, where ``mean1``/``std1`` here are whichever of
        the two fitted components has the lower mean (labelled ``mean1``/``std1``
        in this method's signature only by fit-parameter order, not by value).
        Only if there is no local minimum up there either does this fall back to
        the first raw data point above the floor, and finally to the midpoint of
        the two means.

        The fitted spline is returned alongside the threshold. Nothing consumes
        it today - it is kept because the curve and its local minima are the
        natural starting point for improving the fits themselves, which is a
        better use for it than the plot overlay it was originally added for.

        It is fit whenever the histogram has enough bins, even when the valley
        search is then skipped, but there is no fallback curve: if
        ``_fit_least_smoothed_spline`` declines, the spline is None and the
        threshold comes from the data-driven rungs. Substituting a
        cross-validated curve there would hand the valley search exactly the
        noise the ladder was built to remove.

        :param data: the raw 1-D data the histogram was built from
        :type data: npt.NDArray[np.float64]
        :param bins: histogram bin centers, as built for the double-Gaussian fit
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts, as built for the double-Gaussian fit
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
            ``bins``, or None if it could not be fit
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
                # No fallback to plain generalized cross-validation when the
                # ladder declines. GCV is the thing the ladder exists to
                # replace - it under-smooths on counting data, leaving Poisson
                # wiggles that the valley search below cannot tell from a real
                # boundary - so placing a threshold from a GCV curve is not a
                # degraded answer but a wrong one wearing the good rung's
                # label. A declined ladder means no spline, and the threshold
                # comes from the data-driven rungs instead.
                spline = self._fit_least_smoothed_spline(
                    spline_bins, spline_amplitude, search_lo, search_hi
                )
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
        # The FIRST such minimum, not the deepest. Past the bulk of the data
        # the spline is fitting counting noise on near-empty bins, so it
        # wiggles, and every wiggle is a local minimum - typically dozens of
        # them above the floor. The deepest is invariably far out in that
        # noise, at a negative spline value, and would cut off a fraction of a
        # percent of the data; the first one sits just above the floor, which
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
    def _fit_double_gaussian_bounded_at_valley(
        self,
        bins: npt.NDArray[np.float64],
        amplitude: npt.NDArray[np.float64],
        split_point: float,
        popt: npt.NDArray[np.float64],
    ) -> Optional[Tuple[npt.NDArray[np.float64], float]]:
        """
        Re-fit both components jointly, each mean hard-bounded to its own
        side of ``split_point``, and return the analytic crossing of the two
        resulting curves as the classification threshold.

        Called by ``fit_threshold``, but only when the threshold came from a
        feature of the curve - either spline-derived rung. Where it succeeds its
        parameters and its crossing replace the joint fit's, and ``params_method``
        becomes ``"constrained"``.

        **The problem this solves is shoulder-stealing.** Real prominence and
        blockage populations are right-skewed, so a symmetric Gaussian on the
        lower population falls away faster than the data does and leaves an
        un-modelled right shoulder. Fitting both components against one
        unconstrained objective lets least squares reduce that residual by
        widening the higher component and sliding its mean down into the
        shoulder - which lowers the total error while leaving the higher
        component describing neither population. Measured on a reconstruction
        of a real 12096-peak dataset, it put the higher mean 114 pA from the
        mode the data actually has and its width at 755 against a true ~620.

        Bounding the two means keeps both components fitting the *whole*
        histogram in one joint optimization, so neither loses the information
        the other side's shape carries about where the boundary sits;
        ``split_point`` only forbids ``mean_lower`` from crossing above it
        and ``mean_higher`` from crossing below it. That is not, on its own,
        enough to stop the distortion: a tall, narrow higher component can
        still dominate the curve all the way down to the lower mean even with
        its own mean pinned above the split. So this also constrains the fit
        so that **each component is
        the larger of the two at its own mean** (``g_lower(mean_lower) >
        g_higher(mean_lower)`` and the mirror image at ``mean_higher``) -
        which is exactly the condition that guarantees the two curves cross
        somewhere between their means (see ``_gaussian_intersection``), so
        that crossing is always a real feature of the fit rather than a
        tail-region artifact or an out-of-range root.

        **Those two together are still not enough, because a box bound at the
        split point permits the higher component to sit with its summit
        exactly on the valley.** That is the observed failure on skewed real
        data: measured on a reconstruction, ``(mean_higher - split_point) /
        std_higher`` fell to **0.009** - the higher Gaussian was at 99.996% of
        its own peak height at the valley - and its mean landed 402 pA below
        the population's true mode, because it was spending itself covering the
        lower population's right shoulder. The failure is smooth in skew, not a
        cliff: that ratio degrades 0.70 -> 0.30 -> 0.14 -> 0.009 as the lower
        population's skew rises, with the mode error tracking it -48 -> -149 ->
        -255 -> -402 pA.

        ``VALLEY_SEPARATION_SIGMA`` closes it by requiring the valley to be at
        least ``k`` of each component's *own* standard deviations away from its
        mean, which restates "the valley is a boundary between the populations,
        not a point inside one of them" in a form the optimizer can enforce.
        Being denominated in the component's own fitted width is what makes it
        skew-agnostic - it never refers to absolute current, so it does not care
        how the skew stretches the axis. Measured over 24 datasets (four skew
        levels, six seeds each) at ``k = 0.5``: mean absolute error in the
        higher mode 254 -> 111 pA, and its *bias* -241 -> -14 pA, i.e. very
        nearly unbiased where the unconstrained-mean version was systematically
        low; classification accuracy against ground-truth labels 0.8433 ->
        0.8776, better on 23 of the 24 and worse on one by 0.021.

        **The property that makes this safe to apply everywhere is that it is
        inert wherever the fit was already good.** On symmetric, well-separated
        populations the valley naturally sits more than one sigma from each
        mean, so the constraint never binds and the result is identical to what
        the box bounds alone produce - verified bit-for-bit at 3, 4 and 5 sigma
        separation, and on balanced and mildly-imbalanced mixtures. It only
        becomes active in the skewed regime it exists for. Larger ``k`` buys a
        little more classification accuracy (0.8907 at 0.75, 0.8915 at 1.0) at
        the cost of overshooting the mode in the other direction (bias +134 and
        +248 pA) and narrowing the fitted width, so 0.5 is the setting that
        describes the population best rather than the one that maximises the
        threshold's accuracy. Known limit: for a minority population below
        roughly 7% of events the constraint overshoots the higher mean, though
        measured accuracy holds and the collapsed-component guard below catches
        the extreme cases.

        **This also runs on single-population data**, where ``split_point``
        is the above-floor threshold rather than a valley between two modes.
        There the higher component has no population of its own to describe,
        only the sparse region above the threshold, so it comes back with a
        small amplitude pinned near the split - the correct answer, not a
        failure: it says that region is sparsely populated, which is what
        the plot should show, rather than leaving the higher component where
        the unconstrained joint fit put it, on top of the lower one,
        claiming a second population that was explicitly not found.

        :param bins: histogram bin centers, as built for the double-Gaussian fit
        :type bins: npt.NDArray[np.float64]
        :param amplitude: histogram bin counts, as built for the double-Gaussian fit
        :type amplitude: npt.NDArray[np.float64]
        :param split_point: the x position the two means are bounded against -
            the threshold ``_threshold_between_populations`` returned, whether
            that came from a valley between two centres or from the first
            local minimum above the ``2 * mean - 2 * std`` floor
        :type split_point: float
        :param popt: the unconstrained joint double-Gaussian fit's six
            parameters, used to seed this refit and returned unchanged by the
            caller if this declines
        :type popt: npt.NDArray[np.float64]
        :return: tuple of (six parameters ``(amp1, mean1, std1, amp2, mean2,
            std2)`` for the lower population then the higher one, the x
            position where those two curves cross), or None if the
            constrained refit could not be done, did not converge, collapsed
            a component, or - which the dominance constraint should make
            unreachable - produced curves that do not cross between their
            means. In every None case the caller keeps the unconstrained
            joint fit and its valley/floor threshold.
        :rtype: Optional[Tuple[npt.NDArray[np.float64], float]]
        """
        bin_width = float(bins[1] - bins[0])
        amp1, mean1, std1, amp2, mean2, std2 = (float(p) for p in popt)
        if mean1 > mean2:
            amp1, mean1, std1, amp2, mean2, std2 = (
                amp2,
                mean2,
                std2,
                amp1,
                mean1,
                std1,
            )

        min_mean = float(bins[0])
        max_mean = float(bins[-1])
        if not (min_mean <= split_point <= max_mean):
            self.logger.debug(
                f"not constraining at {split_point:.4g}: it falls outside "
                f"the histogram range [{min_mean:.4g}, {max_mean:.4g}]. "
                "Keeping the joint fit."
            )
            return None

        min_amp = 1e-3  # away from zero: the dominance constraint takes log(amp)
        max_amp = float(np.max(amplitude))
        min_std = bin_width / 2.0
        max_std = float(np.abs(bins[-1] - bins[0]))

        lower_bounds = [min_amp, min_mean, min_std, min_amp, split_point, min_std]
        upper_bounds = [max_amp, split_point, max_std, max_amp, max_mean, max_std]

        k = float(self.VALLEY_SEPARATION_SIGMA)
        seed_std1 = float(np.clip(std1, min_std, max_std))
        seed_std2 = float(np.clip(std2, min_std, max_std))
        seed_mean1 = float(np.clip(mean1, min_mean, split_point))
        seed_mean2 = float(np.clip(mean2, split_point, max_mean))
        if k > 0:
            # Walk the seed into the region `_valley_separation` allows before
            # handing it to SLSQP. Seeding infeasibly is not cosmetic: SLSQP
            # still converges to a good answer from there, but then reports
            # "Positive directional derivative for linesearch" with
            # success=False at the constraint boundary, so a perfectly usable
            # fit is thrown away - a quarter of skewed fits in benchmarking,
            # and worse as k rises. Where the box cannot hold a mean that far from
            # the split point, the seed's width is reduced instead; the
            # optimizer is free to widen it again.
            seed_mean2 = float(
                np.clip(
                    max(seed_mean2, split_point + k * seed_std2), split_point, max_mean
                )
            )
            if seed_mean2 - split_point < k * seed_std2:
                seed_std2 = max(min_std, (seed_mean2 - split_point) / k)
            seed_mean1 = float(
                np.clip(
                    min(seed_mean1, split_point - k * seed_std1), min_mean, split_point
                )
            )
            if split_point - seed_mean1 < k * seed_std1:
                seed_std1 = max(min_std, (split_point - seed_mean1) / k)
        p0 = [
            max(amp1, 1.0),
            seed_mean1,
            seed_std1,
            max(amp2, 1.0),
            seed_mean2,
            seed_std2,
        ]

        def _residual_sum_of_squares(params: npt.NDArray[np.float64]) -> float:
            model = self._double_gaussian(bins, *params)
            return float(np.sum((model - amplitude) ** 2))

        def _dominance(params: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
            a_lower, m_lower, s_lower, a_higher, m_higher, s_higher = params
            with np.errstate(divide="ignore", invalid="ignore"):
                at_lower_mean = (
                    np.log(a_lower)
                    - np.log(a_higher)
                    + (m_lower - m_higher) ** 2 / (2.0 * s_higher**2)
                )
                at_higher_mean = (
                    np.log(a_higher)
                    - np.log(a_lower)
                    + (m_higher - m_lower) ** 2 / (2.0 * s_lower**2)
                )
            return np.array([at_lower_mean, at_higher_mean])

        def _valley_separation(
            params: npt.NDArray[np.float64],
        ) -> npt.NDArray[np.float64]:
            _, m_lower, s_lower, _, m_higher, s_higher = params
            return np.array(
                [
                    (m_higher - split_point) - k * s_higher,
                    (split_point - m_lower) - k * s_lower,
                ]
            )

        constraints: List[Dict[str, Any]] = [{"type": "ineq", "fun": _dominance}]
        if k > 0:
            constraints.append({"type": "ineq", "fun": _valley_separation})

        try:
            result = minimize(
                _residual_sum_of_squares,
                p0,
                method="SLSQP",
                bounds=list(zip(lower_bounds, upper_bounds)),
                constraints=constraints,
                options={"maxiter": 500, "ftol": 1e-9},
            )
        except Exception as e:
            self.logger.warning(
                f"constrained double-Gaussian refit at {split_point:.4g} "
                f"raised {e}. Keeping the joint fit."
            )
            return None

        fit = np.asarray(result.x, dtype=float)

        # SLSQP reports a spurious linesearch failure when the optimum sits
        # exactly on a constraint boundary, which is the *expected* place for
        # this fit to land whenever `_valley_separation` is what is holding the
        # higher component up off the valley. Accept a flagged solution that in
        # fact satisfies every constraint and bound; only a genuinely infeasible
        # result is a failure.
        feasible = (
            all(bool(np.all(c["fun"](fit) >= -1e-6)) for c in constraints)
            and bool(np.all(fit >= np.asarray(lower_bounds, dtype=float) - 1e-6))
            and bool(np.all(fit <= np.asarray(upper_bounds, dtype=float) + 1e-6))
        )
        if not (result.success or feasible):
            self.logger.warning(
                f"constrained double-Gaussian refit at {split_point:.4g} did "
                f"not converge: {result.message}. Keeping the joint fit."
            )
            return None
        if fit[2] <= bin_width or fit[5] <= bin_width:
            self.logger.warning(
                f"constrained double-Gaussian refit at {split_point:.4g} "
                f"collapsed a component to std at or below the "
                f"{bin_width:.4g} bin width. Keeping the joint fit instead."
            )
            return None

        crossing = self._gaussian_intersection(*fit)
        if crossing is None:
            # The dominance constraint above guarantees a sign change in
            # `_gaussian_intersection`'s quadratic between the two means, so
            # this is a defensive fallback against a numerically marginal
            # SLSQP solution rather than an expected path.
            self.logger.warning(
                f"constrained double-Gaussian refit at {split_point:.4g} "
                "converged but its two components do not cross between "
                "their means despite the dominance constraint; this should "
                "not happen. Keeping the joint fit."
            )
            return None

        self.logger.debug(
            f"constrained refit at {split_point:.4g}: lower mean "
            f"{fit[1]:.4g} std {fit[2]:.4g}, higher mean {fit[4]:.4g} std "
            f"{fit[5]:.4g}, crossing at {crossing:.4g} (unconstrained joint "
            f"fit had means {mean1:.4g}/{mean2:.4g})."
        )
        return fit, crossing

    @log(logger=logger)
    def _classification_confidence(
        self,
        values: npt.NDArray[np.float64],
        params: Tuple[float, float, float, float, float, float],
        is_higher_class: npt.NDArray[np.bool_],
    ) -> npt.NDArray[np.float64]:
        """
        Score how confidently each value was assigned to its threshold-derived class.

        Called by ``_classify_peak_prominences`` and
        ``_classify_translocation_direction`` to fill
        ``classification_confidence`` and ``translocation_confidence``. The folding
        classifier does not use it.

        ``fit_threshold`` fits ``(amp1, mean1, std1, amp2, mean2, std2)`` with
        ``curve_fit`` against histogram *counts*, not densities, so each fitted
        curve ``amp_k * exp(-(x-mean_k)**2 / (2*std_k**2))`` is already the
        expected bin count contributed by population k at x - amplitude has
        absorbed both the population size and the ``1/(std*sqrt(2*pi))``
        normalization a proper mixture weight would otherwise need. That means
        the usual Gaussian-mixture posterior ("responsibility") falls out of
        the fit parameters directly, with no re-fitting and no extra weighting
        step:

        ``confidence(x) = g_assigned(x) / (g_low(x) + g_high(x))``

        where ``g_low``/``g_high`` are the two fitted curves ordered by mean
        and ``g_assigned`` is whichever of the two matches the class the
        caller already assigned by thresholding ``values`` (``is_higher_class``
        records that assignment so this method does not need to know
        ``fit_threshold``'s own threshold value).

        This is a relative/ordinal score, not a calibrated probability: it
        comes from the same symmetric-Gaussian model ``fit_threshold`` uses,
        so on data where a population is genuinely skewed (see the log-normal
        upper prominence component noted in ``future_fixes.md``) it will read
        as overconfident approaching that skewed shoulder.

        Whether this is guaranteed to cross 0.5 exactly at ``fit_threshold``'s
        own threshold depends on ``"params_method"``. When it is
        ``"constrained"``, ``"threshold"`` *is* the x position where these two
        curves cross (see ``_fit_double_gaussian_bounded_at_valley`` and
        ``_gaussian_intersection``), so this necessarily reads exactly 0.5
        there. When it is ``"joint"`` - the two ``fallback`` threshold methods,
        or a declined constrained refit - ``"threshold"`` is read off the
        smoothing spline's valley or floor instead, not the point where these
        particular fitted Gaussians cross, so a handful of points just past
        the threshold can legitimately score below 0.5 there - the shape-based
        label and the Gaussian-mixture vote disagreeing right at the boundary,
        which is informative rather than a bug.

        :param values: the 1-D data that was thresholded to produce
            ``is_higher_class``
        :type values: npt.NDArray[np.float64]
        :param params: the six fitted double-Gaussian parameters from
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

        **Not currently called.** Kept as the sklearn alternative to the
        ``curve_fit`` path in ``fit_threshold``: it works on raw samples rather
        than on a histogram, so it avoids the binning sensitivity ``MIN_FIT_BINS``
        exists to work around, and BIC would choose the component count instead of
        it being fixed at two.

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

        **Not currently called.** The two-dimensional counterpart of
        ``classify_1d_distribution``, for separating populations that need two
        features - prominence against width, say - rather than one.

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
        Assign a type to every peak in one event, from where its bases sit
        relative to the carrier levels and from how close it is to its
        neighbours. Writes the result into ``properties["filtered"]``.

        Called by ``update_event_metadata_post_processing``, once per event,
        after ``_classify_folded_unfolded`` has measured the run-wide carrier
        levels. Those labels are what every later stage selects on: the
        sequence builder and ``_classify_translocation_direction`` read type 3,
        ``_classify_bound_star`` reads type -1, and
        ``_classify_peak_prominences`` reads types 1, 2 and 3.

        The branch taken depends on the ``Event Type`` setting.

        **Barcode.** Each peak is typed from its two bases, which must both
        land in the same band. Writing ``U`` for the unfolded level, ``s`` for
        the baseline standard deviation, ``t1`` for ``Lower Filter Threshold``
        and ``t2`` for ``Higher Filter Threshold`` (both blockage depths, so
        larger means deeper), the bands are contiguous:

        - **0** - both bases at or below ``t2*s``: on the baseline, not on a
          carrier.
        - **1** - both bases within ``[U + t1*s, U + t2*s]``: a peak sitting on
          the unfolded carrier. ``t1`` defaults negative, so this band opens
          below the unfolded level and closes above it.
        - **2** - both bases within ``[U + t2*s, 2*U + t2*s]``: a peak sitting
          on the folded carrier.
        - **-1** - both bases above ``2*U + t2*s``, or the two bases in
          different bands. This is the catch-all, and it is where a bound star
          lands as well as any straddling or spurious peak.

        A second pass then promotes the **most prominent** run of adjacent
        type-1 peaks to **type 3**, the barcode. Every type-1 peak is a
        candidate; consecutive members of a run must be within ``Peak to Peak
        Distance Ratio`` percent of the event length of each other, and a run
        must reach ``Number of peaks`` members to qualify. Every starting
        position is tried, so an event can have several separated candidate
        runs; the qualifying run with the highest summed prominence wins, and
        a tie goes to whichever run occurs earliest in time. A qualifying run
        longer than ``Number of peaks`` is truncated to that many members
        before its prominence is summed, so a barcode never has more than
        ``Number of peaks`` peaks even when a longer real one exists. Peaks
        left over keep the type the first pass gave them.

        **Single Peak.** Peaks are typed 11, 12, 13, 21 or 22 by which
        transition their bases describe, and everything but the single most
        prominent survivor is then reset to -1.

        **Unspecified.** No typing at all.

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
        # baseline_std is Optional under the MetaEventFitter contract but every
        # threshold below is denominated in it, so an event loader that
        # supplies none is an error rather than a case to work around.
        if baseline_std is None:
            raise RuntimeError(
                "filter_peaks requires a baseline standard deviation to set its "
                "classification thresholds; the event loader supplied None"
            )

        t1_std = int(self.settings["Lower Filter Threshold"]["Value"])
        t2_std = int(self.settings["Higher Filter Threshold"]["Value"])

        num_peaks = self.settings["Number of peaks"]["Value"]
        filtered = properties["filtered"]

        if len(peaks) == 0:
            properties["filtered"] = properties.get("filtered", [])
            return properties

        # One label per peak, whatever length the caller supplied.
        filtered_list = list(properties.get("filtered", []))
        if len(filtered_list) < len(peaks):
            filtered_list = filtered_list + [0] * (len(peaks) - len(filtered_list))
        elif len(filtered_list) > len(peaks):
            filtered_list = filtered_list[: len(peaks)]
        filtered = np.array(filtered_list, dtype=int)
        if self.settings["Event Type"]["Value"] == "Barcode":
            # Step 1: type each peak from its two bases, which must both land
            # in the same band. The bands are ordered and adjacent - baseline,
            # around the unfolded level, around the folded level - and anything
            # above the top of the last one, or straddling two, is -1. See the
            # docstring for what each type means.
            type0_thresh = t2_std * baseline_std
            type1_thresh = unfolded_level + t1_std * baseline_std
            type2_thresh = unfolded_level + t2_std * baseline_std

            for i in range(len(peaks)):
                left_base = properties["left_bases"][i] + np.sign(baseline) * baseline
                right_base = properties["right_bases"][i] + np.sign(baseline) * baseline

                # Type 0: both bases are below the lower carrier threshold.
                if left_base <= type0_thresh and right_base <= type0_thresh:
                    filtered[i] = 0
                # Type -1: both bases above the upper type-2 cutoff (noise)
                elif (
                    left_base >= type2_thresh + unfolded_level
                    and right_base >= type2_thresh + unfolded_level
                ):
                    filtered[i] = -1
                # Type 2: both bases within the type-2 band around 2*unfolded_level
                elif (
                    left_base >= type2_thresh
                    and right_base >= type2_thresh
                    and left_base <= type2_thresh + unfolded_level
                    and right_base <= type2_thresh + unfolded_level
                ):
                    filtered[i] = 2
                # Type 1: both bases within the type-1 band around unfolded_level
                elif (
                    left_base >= type1_thresh
                    and right_base >= type1_thresh
                    and left_base <= type2_thresh
                    and right_base <= type2_thresh
                ):
                    filtered[i] = 1
                else:
                    filtered[i] = -1

            # Step 2: promote the most prominent run of adjacent type-1 peaks
            # to type 3, the barcode.
            #
            # Every type-1 peak is a candidate, and every starting position is
            # tried, so a single event can produce several separated candidate
            # runs; the qualifying one with the highest summed prominence
            # wins, a tie going to whichever was found first (equivalently the
            # earlier run, since starts are walked in time order). A
            # qualifying run is truncated to `num_peaks` members before its
            # prominence is summed, so a barcode never has more than
            # `num_peaks` peaks even when a longer real one exists.
            #
            # max_distance is in microseconds, because that is what it is
            # compared against: `event_length` arrives in us, and the peak
            # positions are `properties["peak_loc"]`, which is the sublevel
            # metadata's `peak_loc` and is also us. Converting the event length
            # to samples here would scale the declared percentage by the sample
            # rate in MHz, making the setting mean something different at every
            # rate.
            max_distance_percentage = self.settings.get(
                "Peak to Peak Distance Ratio", {}
            ).get("Value", 5.0)
            max_distance = (max_distance_percentage / 100.0) * event_length
            self.logger.debug(
                f"filter_peaks: event_length={event_length:.1f} us, "
                f"max_distance_percentage={max_distance_percentage}%, "
                f"max_distance={max_distance:.1f} us "
                f"({max_distance * samplerate * 1e-6:.0f} samples at "
                f"{samplerate * 1e-6:.3g} MHz)"
            )
            min_group_size = num_peaks
            prom_indices = np.argsort(properties["prominences"])[
                ::-1
            ]  # all sorted by prominence
            best_cluster = []
            best_prom_sum = 0

            for label in [1]:
                # Every type-1 peak is a clustering candidate. An earlier
                # version pre-filtered this list down to the `num_peaks` most
                # prominent peaks before ever looking for a run, which capped
                # the whole event to a single possible candidate cluster - the
                # comparison below could never see a second one to prefer.
                label_idxs = [i for i in prom_indices if filtered[i] == label]
                if not label_idxs:
                    continue
                sorted_idxs = sorted(label_idxs, key=lambda i: peaks[i])

                # Clusters are runs that are adjacent in time, not in
                # prominence, so the walk below is over sublevel order.
                for i in range(len(sorted_idxs)):
                    group = [sorted_idxs[i]]

                    for j in range(i + 1, len(sorted_idxs)):
                        prev_peak_idx = group[-1]
                        curr_peak_idx = sorted_idxs[j]
                        distance = abs(
                            properties["peak_loc"][curr_peak_idx]
                            - properties["peak_loc"][prev_peak_idx]
                        )

                        if distance <= max_distance:
                            group.append(curr_peak_idx)
                        else:
                            break

                    group = group[:num_peaks]

                    if len(group) >= min_group_size:
                        prom_sum = sum(properties["prominences"][idx] for idx in group)

                        if prom_sum > best_prom_sum:
                            best_cluster = group
                            best_prom_sum = prom_sum

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
                        continue

                for idx in validated_cluster:
                    filtered[idx] = 3

            properties["filtered"] = list(filtered.tolist())

        # SINGLE PEAK CARRIER
        if self.settings["Event Type"]["Value"] == "Single Peak":

            unfolded_lower_bound = (
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

                # Ordered from most specific to most general.
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

            # Step 2: keep only the most prominent typed peak.
            if classified_peaks:
                classified_peaks.sort(key=lambda x: (-x[1], -x[0]))
                best_idx = classified_peaks[0][0]

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

        Called by ``_locate_sublevel_transitions``, both for the event's carrier
        blockage and for each peak's ``max_blockage``, and by
        ``_populate_event_metadata`` for the event's ``primary_level``. Those
        primary levels are what ``_classify_folded_unfolded`` later fits.

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

        arr = np.asarray(data)
        if arr.size == 0:
            return None, None

        # baseline_mean is Optional under the MetaEventFitter contract but the
        # returned levels are depths measured from it, so an event loader that
        # supplies none is an error rather than a case to work around.
        if baseline_mean is None:
            raise RuntimeError(
                "find_mode_blockage_level requires a baseline mean; the event loader "
                "supplied None, so blockage levels cannot be referenced to a baseline"
            )

        # Fast histogram-based level detection using numpy
        # Prefer bins based on baseline noise when possible, but fall back to 'auto'
        # baseline_std is legitimately Optional here - unlike baseline_mean
        # above - so a missing one selects numpy's 'auto' binning rather than
        # being an error.
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
        Number the peak sublevels of one event 1..N, leaving None elsewhere.

        Called by ``_populate_sublevel_metadata`` to fill ``peak_id``, which is
        what every later stage uses to tell a peak sublevel from a baseline or
        padding one.

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
