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
# Alejandra Carolina González González
# Kyle Briggs

import itertools
import logging
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    override,
)

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, peak_widths
from scipy.stats import t

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabModel import MetaSubsetTabModel


@inherit_docstrings
class ProteinModel(MetaSubsetTabModel):
    """
    Subclass of MetaSubsetTabModel for protein volume/shape-factor fitting data and storage.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        pass

    @log(logger=logger)
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
        return the value of a double gaussian with the specified paramters

        :param x: array of x values at which to calculate double gaussian
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

    @log(logger=logger)
    def _fit_double_gaussian(
        self, bins: npt.NDArray[np.float64], amplitude: npt.NDArray[np.float64]
    ) -> tuple:
        """
        Attempt to fit a double gaussian to data or return None on failure.

        :param bins: numpy array of bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: numpy array of amplitude in bins
        :type amplitude: npt.NDArray[np.float64]
        :return: Tuple of (best-fit parameters (amplitude, mean, std, amplitude_2,
                mean_2, std_2), parameter covariance matrix), or (None, None) if
                fitting fails.
        :rtype: tuple
        :raises ValueError: If curve fitting fails or peaks/split points cannot be
            determined; caught internally by nested fallback logic, so it never
            propagates to the caller.
        """
        try:
            min_prominence = np.max(amplitude) * 0.05
            peaks, properties = find_peaks(amplitude, prominence=min_prominence)

            if len(peaks) < 2:
                raise ValueError("Not enough peaks for initial guess")

            prominences = properties["prominences"]

            largest_prominence_indices = np.argsort(prominences)[-2:][::-1]
            top_two_peaks = peaks[largest_prominence_indices]

            widths, _, _, _ = peak_widths(amplitude, top_two_peaks, rel_height=0.5)

            bin_width = bins[1] - bins[0]
            fwhm_guesses = widths * bin_width

            std_guesses = fwhm_guesses / 2.355

            p0 = (
                amplitude[top_two_peaks[0]],
                bins[top_two_peaks[0]],
                std_guesses[0],
                amplitude[top_two_peaks[1]],
                bins[top_two_peaks[1]],
                std_guesses[1],
            )
            min_mean = np.min(bins)
            max_mean = np.max(bins)
            min_amp = 0
            max_amp = np.max(amplitude)
            min_std = 0
            max_std = np.abs(bins[-1] - bins[1])

            popt, pcov = curve_fit(
                self._double_gaussian,
                bins,
                amplitude,
                p0=p0,
                bounds=(
                    [min_amp, min_mean, min_std, min_amp, min_mean, min_std],
                    [max_amp, max_mean, max_std, max_amp, max_mean, max_std],
                ),
            )
            return popt, pcov
        except (RuntimeError, ValueError):
            try:
                n = len(amplitude)
                amax = np.max(amplitude)
                left_start = 0
                while amplitude[left_start] < 0.05 * amax and left_start < n:
                    left_start += 1
                right_start = n - 1
                while amplitude[right_start] < 0.05 * amax and right_start > 0:
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
                min_mean = np.min(bins)
                max_mean = np.max(bins)
                min_amp = 0
                max_amp = np.max(amplitude)
                min_std = 0
                max_std = np.abs(bins[-1] - bins[1])

                popt, pcov = curve_fit(
                    self._double_gaussian,
                    bins,
                    amplitude,
                    p0=p0,
                    bounds=(
                        [min_amp, min_mean, min_std, min_amp, min_mean, min_std],
                        [max_amp, max_mean, max_std, max_amp, max_mean, max_std],
                    ),
                )
                return popt, pcov
            except (RuntimeError, ValueError):
                return None, None

    @log(logger=logger)
    def _fit_and_sanity_check_double_gaussian(
        self, bins: npt.NDArray[np.float64], amplitude: npt.NDArray[np.float64]
    ) -> Optional[npt.NDArray[np.float64]]:
        """
        Attempt to fit a double gaussian to data or None on failure.

        :param bins: numpy array of bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: numpy array of amplitude in bins
        :type amplitude: npt.NDArray[np.float64]
        :return: fit parameters for a double gaussian (amplitude, mean, std, amplitude_2, mean_2, std_2)
        :rtype: Optional[npt.NDArray[np.float64]]
        """
        popt, pcov = self._fit_double_gaussian(
            bins,
            amplitude,
        )

        if (
            popt is None
            or pcov is None
            or np.any(np.isinf(pcov))
            or np.any(np.isnan(pcov))
        ):
            return None

        perr = np.sqrt(np.diag(pcov))
        if np.any(perr > np.abs(popt) * 10):
            return None

        mu1_idx, mu2_idx = 1, 4
        mu1, mu2 = popt[mu1_idx], popt[mu2_idx]
        var_mu1, var_mu2 = (
            pcov[mu1_idx, mu1_idx],
            pcov[mu2_idx, mu2_idx],
        )
        cov_mu1_mu2 = pcov[mu1_idx, mu2_idx]
        variance_diff = var_mu1 + var_mu2 - 2 * cov_mu1_mu2

        if variance_diff <= 0:
            return None

        se_diff = np.sqrt(variance_diff)
        t_stat = abs(mu1 - mu2) / se_diff
        N_points = len(bins)
        df = N_points - len(popt)
        p_value = 2 * t.sf(t_stat, df)

        if p_value > 0.05:
            return None

        A1, A2 = popt[0], popt[3]
        abs_A1, abs_A2 = abs(A1), abs(A2)
        if max(abs_A1, abs_A2) == 0:
            return None

        if min(abs_A1, abs_A2) / max(abs_A1, abs_A2) < 0.05:
            return None

        return popt

    @log(logger=logger)
    def fit_histogram(
        self, bins: npt.NDArray[np.float64], amplitude: npt.NDArray[np.float64]
    ) -> Tuple[Optional[npt.NDArray[np.float64]], Optional[npt.NDArray[np.float64]]]:
        """
        Fit a double gaussian to one histogram and evaluate it at the same bins.

        The evaluated curve comes back alongside the parameters because every caller
        that wants a fit also draws it, and returning both is what keeps
        ``_double_gaussian`` out of the View entirely rather than moving the fit and
        leaving its evaluation behind.

        :param bins: numpy array of bin centers
        :type bins: npt.NDArray[np.float64]
        :param amplitude: numpy array of amplitude in bins
        :type amplitude: npt.NDArray[np.float64]
        :return: (fit parameters, fitted curve at bins), or (None, None) if the fit failed its sanity checks
        :rtype: Tuple[Optional[npt.NDArray[np.float64]], Optional[npt.NDArray[np.float64]]]
        """
        popt = self._fit_and_sanity_check_double_gaussian(bins, amplitude)
        if popt is None:
            return None, None
        return popt, self._double_gaussian(bins, *popt)

    @log(logger=logger)
    def fit_histograms(
        self,
        histograms: Sequence[
            Optional[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        ],
    ) -> List[
        Tuple[Optional[npt.NDArray[np.float64]], Optional[npt.NDArray[np.float64]]]
    ]:
        """
        Fit a double gaussian to each histogram in turn.

        The per-event plotting paths fit one histogram per event. Doing them in a
        single call keeps every answer off the widget: a per-event round trip would
        work - a same-thread Qt signal is synchronous, measured - but only by parking
        each answer somewhere for the loop body to read back, which is the pattern
        would be read back by mistake. It also means the View does not depend on the
        connection staying ``Direct``.

        ``None`` stands for an event whose histogram could not be built at all, and
        answers the same way as one that could not be fitted, so the result is
        index-aligned with the input either way and the caller skips exactly the
        events that have no fit.

        :param histograms: (bins, amplitude) pairs, one per event, or None where no histogram could be built
        :type histograms: Sequence[Optional[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]]
        :return: one (fit parameters, fitted curve) pair per input histogram, index-aligned with it
        :rtype: List[Tuple[Optional[npt.NDArray[np.float64]], Optional[npt.NDArray[np.float64]]]]
        """
        return [
            self.fit_histogram(*histogram) if histogram is not None else (None, None)
            for histogram in histograms
        ]

    @log(logger=logger)
    def drop_fit_columns(self, loader: str, table: str, columns: Sequence[str]) -> bool:
        """
        Delete an existing set of fit columns so a new one can replace it.

        Owns the SQL rather than assembling it in the Controller and using the Model as
        a conduit to the loader: the layer that makes the plugin call is the layer that
        writes what it sends. ``ClusteringModel.drop_cluster_columns`` is the same
        shape, for the same reason. ``DECISIONS.md`` (2026-08-25) accepts the f-string interpolation
        itself, because the database is a local file owned by the user running the
        app; this is about *where* the SQL lives.

        Both statements are needed per column: one drops it from the events table and
        one removes its row from the ``columns`` metadata table, which is what tells
        the rest of the application the column exists.

        :param loader: the database loader's plugin key
        :type loader: str
        :param table: the table the fit columns are in
        :type table: str
        :param columns: the fit columns to remove
        :type columns: Sequence[str]
        :return: True if the loader reported success
        :rtype: bool
        """
        queries = [
            f"ALTER TABLE {table} DROP COLUMN {column}" for column in columns
        ] + [f"DELETE FROM columns WHERE name = '{column}'" for column in columns]
        status: bool = self.call(
            "MetaDatabaseLoader", loader, "alter_database", queries
        )
        return status

    @log(logger=logger)
    def _blockage_fraction(
        self, event: Dict[str, Any], plot_type: str
    ) -> npt.NDArray[np.float64]:
        """
        One event's current expressed as a fraction of its own baseline.

        The baseline is the mean of the medians either side of the event, which is
        what makes a slow drift across the event average out rather than bias the
        blockage; the paddings the loader reports are in microseconds while the
        slicing counts samples.

        :param event: one event's payload as the loader yields it
        :type event: Dict[str, Any]
        :param plot_type: 'Raw Histogram' or 'Filtered Histogram'
        :type plot_type: str
        :return: the fractional blockage over the event proper, paddings excluded
        :rtype: npt.NDArray[np.float64]
        :raises ValueError: if plot_type names neither the raw nor the filtered trace
        :raises ZeroDivisionError: if the event's baseline is zero
        """
        if plot_type == "Raw Histogram":
            timeseries = event["raw_data"]
        elif plot_type == "Filtered Histogram":
            timeseries = event["filtered_data"]
        else:
            raise ValueError(f"Unknown plot_type {plot_type!r}")

        padding_before = int(event["padding_before"] * event["samplerate"] * 1e-6)
        padding_after = int(event["padding_after"] * event["samplerate"] * 1e-6)
        baseline = 0.5 * (
            np.median(timeseries[:padding_before])
            + np.median(timeseries[-padding_after:])
        )
        if baseline == 0:
            raise ZeroDivisionError(
                f'Event {event.get("event_id")} has a zero baseline'
            )

        blockage: npt.NDArray[np.float64] = (
            baseline - timeseries[padding_before:-padding_after]
        ) / baseline
        return blockage

    @log(logger=logger)
    def _resolve_event_bins(
        self,
        blockage: npt.NDArray[np.float64],
        bins: Any,
        sizes: bool,
        hist_min: float,
        hist_max: float,
    ) -> int:
        """
        Decide how many bins one event's histogram gets.

        With no explicit request the width comes from Freedman-Diaconis on this
        event's own interquartile range and sample count, so events of different
        durations - which is typical for proteins - get independently sized bins
        rather than a fixed hundred regardless of length.

        :param blockage: the event's fractional blockage
        :type blockage: npt.NDArray[np.float64]
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :param hist_min: the lower limit the bins must span
        :type hist_min: float
        :param hist_max: the upper limit the bins must span
        :type hist_max: float
        :return: the number of bins
        :rtype: int
        :raises ValueError: if bins is neither a usable count nor a usable width
        """
        if bins is not None:
            if sizes is False:
                if isinstance(bins, list) and len(bins) >= 1:
                    return int(bins[0])
                raise ValueError(f"Invalid bins entry {bins}")
            try:
                return int((hist_max - hist_min) / bins[0])
            except Exception as e:
                raise ValueError(
                    f"Unable to calculate bins given sizes {bins}: {str(e)}"
                ) from e

        iqr = np.percentile(blockage, 75) - np.percentile(blockage, 25)
        bin_width = 2 * iqr / np.cbrt(np.size(blockage))

        if bin_width <= 0 or not np.isfinite(bin_width):
            # IQR collapses to 0 (near-constant signal) or the event is too
            # short/degenerate for FD to produce a sane width; fall back to
            # the previous fixed default rather than dividing by zero.
            return 100
        return max(int((hist_max - hist_min) / bin_width), 1)

    @log(logger=logger)
    def build_event_histograms(
        self,
        events: Sequence[Dict[str, Any]],
        plot_type: str,
        bins: Any,
        sizes: bool,
    ) -> List[Optional[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]]:
        """
        Bin each event's fractional blockage, one histogram per event.

        **Each event is binned over its own range**, so the edges of one subplot say
        nothing about its neighbours. The individual-distribution path used to let
        the limits accumulate across the events of a single plot, which made the
        edges depend on the order they arrived in; both paths follow the same rule
        now, which is the one the event-histogram path already documented.

        An event that cannot be binned contributes ``None`` rather than being
        dropped, so the result stays index-aligned with ``events`` and the drawing
        half still lays out one subplot per event in the original order.

        An unusable bin request or an unrecognised plot type raises out of the
        helpers rather than being absorbed per event: both are the same for every
        event, so reporting once is what the caller can act on.

        :param events: the events to bin, in the order they are drawn
        :type events: Sequence[Dict[str, Any]]
        :param plot_type: 'Raw Histogram' or 'Filtered Histogram'
        :type plot_type: str
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :return: one (bin centers, amplitude) pair per event, or None where none could be built
        :rtype: List[Optional[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]]
        """
        histograms: List[
            Optional[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        ] = []

        for event in events:
            blockage = self._usable_blockage(event, plot_type)
            if blockage is None:
                histograms.append(None)
                continue

            hist_min = float(np.min(blockage))
            hist_max = float(np.max(blockage))
            numbins = self._resolve_event_bins(
                blockage, bins, sizes, hist_min, hist_max
            )

            bin_edges = np.linspace(hist_min, hist_max, numbins + 1)
            amplitude, _ = np.histogram(blockage, bins=bin_edges, density=True)
            bincenters = bin_edges[:-1] + np.diff(bin_edges) / 2.0
            histograms.append((bincenters, amplitude))

        return histograms

    @log(logger=logger)
    def build_all_points_histogram(
        self,
        event_generator: Iterator[Dict[str, Any]],
        plot_type: str,
        bins: Any,
        sizes: bool,
    ) -> Optional[pd.DataFrame]:
        """
        Average every event's fractional-blockage histogram into one.

        The generator is walked twice, because the bins cannot be chosen until the
        extremes across all the events are known: the first pass takes the limits and
        the second counts into the edges they decide. Each event contributes its own
        *shape* rather than its length - the counts are divided by the event's sample
        count before they are summed, and the total by the number of events - so a
        long event does not outweigh a short one.

        Unlike the per-event binning, there is no Freedman-Diaconis fallback here: the
        rule is per-event sample count and interquartile range, and a histogram
        averaged over many events of different lengths has neither.

        :param event_generator: the events of one subset, as the loader yields them
        :type event_generator: Iterator[Dict[str, Any]]
        :param plot_type: 'Raw Histogram' or 'Filtered Histogram'
        :type plot_type: str
        :param bins: a bin count, or a bin width when sizes is True, or None
        :type bins: Any
        :param sizes: does bins refer to a bin width (True) or a count (False)
        :type sizes: bool
        :return: the averaged histogram, or None if no event could be used
        :rtype: Optional[pd.DataFrame]
        :raises ValueError: if plot_type is unrecognised, or bins cannot be resolved
        """
        # get global stats from the first event, don't forget to use this one later
        egen1, egen2 = itertools.tee(event_generator)

        hist_min = float("inf")
        hist_max = float("-inf")
        usable = 0
        for event in egen1:
            blockage = self._usable_blockage(event, plot_type)
            if blockage is None:
                continue
            hist_min = min(hist_min, float(np.min(blockage)))
            hist_max = max(hist_max, float(np.max(blockage)))
            usable += 1

        # Before the bounds are used, not after: with no usable event they are still
        # +/-inf, and letting those reach the bin edges would make every one nan.
        # Returning None here is what the caller already reports on.
        if usable == 0:
            return None

        if bins is not None:
            if sizes is False:
                if isinstance(bins, list) and len(bins) >= 1:
                    numbins = int(bins[0])
                else:
                    raise ValueError(f"Invalid bins entry {bins}")
            else:
                try:
                    numbins = int((hist_max - hist_min) / bins[0])
                except Exception as e:
                    raise ValueError(
                        f"Unable to calculate bins given sizes {bins}: {str(e)}"
                    ) from e
        else:
            numbins = 100

        bin_edges = np.linspace(hist_min, hist_max, numbins + 1)
        hist = np.zeros(numbins)
        count = 0
        for event in egen2:
            blockage = self._usable_blockage(event, plot_type)
            if blockage is None:
                continue
            event_hist, _ = np.histogram(blockage, bins=bin_edges)
            hist += event_hist / len(blockage)
            count += 1
        hist /= count
        bincenters = bin_edges[:-1] + np.diff(bin_edges) / 2.0
        return pd.DataFrame({"Normalized Current": bincenters, "Amplitude": hist})

    @log(logger=logger)
    def _usable_blockage(
        self, event: Dict[str, Any], plot_type: str
    ) -> Optional[npt.NDArray[np.float64]]:
        """
        One event's fractional blockage, or None if it cannot contribute.

        Both walks of the generator have to agree on which events count, or the
        limits and the tally describe different sets. An event is refused for one of
        two reasons: its baseline is zero, so the fraction is undefined, or its
        paddings leave no samples between them to bin.

        :param event: one event's payload as the loader yields it
        :type event: Dict[str, Any]
        :param plot_type: 'Raw Histogram' or 'Filtered Histogram'
        :type plot_type: str
        :return: the fractional blockage, or None if the event cannot be used
        :rtype: Optional[npt.NDArray[np.float64]]
        """
        try:
            blockage = self._blockage_fraction(event, plot_type)
        except ZeroDivisionError as e:
            self.logger.warning(f"{e}, so it is skipped")
            return None
        if blockage.size == 0:
            self.logger.warning(
                f'Event {event.get("event_id")} has no samples between its '
                "paddings, so it is skipped"
            )
            return None
        return blockage

    @log(logger=logger)
    def _compute_theoretical_blockages(
        self,
        V: npt.NDArray[np.float64],
        m: npt.NDArray[np.float64],
        d: float,
        L: float,
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Vectorized forward model: Calculates theoretical max and min blockages
        for arrays of volume (V) and shape factor (m).

        :param V: array of volumes of spheroids in cubic nanometers
        :type V: npt.NDArray[np.float64]
        :param m: array of shape factors of spheroids (major axis / minor axis) of the same length as V. All must be either 0<m<1 or all m>1.
        :type m: npt.NDArray[np.float64]
        :param d: the diameter of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :return: Tuple of arrays of theoretical max and min blockage values for the given parameters, one per V,m pair
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
        :raises ValueError: If `m` contains a mix of oblate (0<m<1) and prolate (m>1)
            form factors, or any negative form factor.
        """
        m_sq = m**2

        if all(m <= 1):
            prolate = False
        elif all(m >= 1):
            prolate = True
        elif any(m < 0):
            raise ValueError("Cannot have negative form factors")
        else:
            raise ValueError(
                "Cannot mix oblate and prolate form factors in a single call to _compute_theoretical_blockages"
            )

        try:
            if not prolate:
                gamma_parallel = 1 / (
                    1 - (1 / (1 - m_sq)) * (1 - (m / np.sqrt(1 - m_sq)) * np.arccos(m))
                )
            else:
                gamma_parallel = 1 / (
                    1
                    - (1 / (m_sq - 1))
                    * ((m / np.sqrt(m_sq - 1)) * np.log(m + np.sqrt(m_sq - 1)) - 1)
                )

            gamma_perpendicular = 1 / (1 - 0.5 / gamma_parallel)
        except ValueError:  # divide by zero from a m=1 case
            gamma_perpendicular = 1.5
            gamma_parallel = 1.5

        b = (3 * V / (4 * np.pi * m)) ** (1 / 3)
        a = b * m
        d_ptn = 2 * b
        l_ptn = 2 * a

        gamma_parallel_prime = gamma_parallel / (
            1 - 0.71 * ((d_ptn**2 + l_ptn**2) / (d**2 + l_ptn**2)) * (d_ptn / d) ** 2
        )

        gamma_perpendicular_prime = gamma_perpendicular / (
            1 - (0.32 + 0.48 * l_ptn / d) * (l_ptn * d_ptn**2 / d**3)
        )

        volume_factor = (4 * V) / (np.pi * d**2 * (L + 0.8 * d))

        parallel_term = volume_factor * gamma_parallel_prime
        perpendicular_term = volume_factor * gamma_perpendicular_prime

        # Map parallel/perpendicular to max/min based on your original logic
        if not prolate:
            dI_max = parallel_term
            dI_min = perpendicular_term
        else:
            dI_max = perpendicular_term
            dI_min = parallel_term

        return dI_max, dI_min

    @log(logger=logger)
    def _generate_vm_ensemble(
        self,
        N_target: int,
        mean_max: float,
        std_max: float,
        mean_min: float,
        std_min: float,
        d: float,
        L: float,
        prolate: bool = True,
        cutoff_std: float = 4,
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Uses Monte Carlo rejection sampling with dynamic bounds to find valid (V, m) pairs.
        Bails out after a maximum number of consecutive failed batches if the experimental
        data represents an unphysical geometry.

        :param N_target: number of value V,m pairs to generate, if possible
        :type N_target: int
        :param mean_max: The mean value of the larger of the two blockage histograms
        :type mean_max: float
        :param std_max: The standard deviation value of the larger of the two blockage histograms
        :type std_max: float
        :param mean_min: The mean value of the smaller of the two blockage histograms
        :type mean_min: float
        :param std_min: The standard deviation value of the smaller of the two blockage histograms
        :type std_min: float
        :param d: the length of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :param prolate: whether we are looking for prolate (m>1) solutions or oblate (0<m<1) solutions
        :type prolate: bool
        :param cutoff_std: the number of standard deviations outside the mean after which to cut off solutions
        :type cutoff_std: float
        :return: Tuple of arrays of V,m pairs
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
        """
        accepted_V: list[float] = []
        accepted_m: list[float] = []
        # Seeded and local: the ensemble is reproducible for a given geometry,
        # and drawing here no longer perturbs the global NumPy RNG for the rest
        # of the process. 42 matches the convention already used in PeakFinder.
        rng = np.random.default_rng(42)
        x = np.minimum(d, L)
        # --- Dynamic Bounds Calculation ---
        K = (np.pi * d**2 * (L + 0.8 * d)) / 4.0  # assumes gamma == 1
        gamma_min = 1

        highest_blockage = mean_max + cutoff_std * std_max
        V_max = highest_blockage * K / gamma_min

        V_min = 1  # we cannot see a 1 nm^3 object anyway so this will always be a safe minimum

        if V_min >= V_max:
            V_max = V_min * 10.0

        batch_size = 50000

        # --- Bailout Logic Variables ---
        max_consecutive_zeros = 5
        consecutive_zeros = 0
        max_batches = 200
        batches = 0

        while (
            len(accepted_V) < N_target
            and consecutive_zeros < max_consecutive_zeros
            and batches < max_batches
        ):
            batches += 1
            # 1. Propose physically valid uniform samples
            V_prop_raw = rng.uniform(V_min, V_max, batch_size)
            ## pick max(a,b) < min(d,L), use a,b equations for a given V sample to calculate m limit in both cases. Prolate case: a>b, oblate: a<b.
            if prolate:
                m_upper_bounds_raw = np.sqrt((np.pi * x**3) / (6 * V_prop_raw))
                valid_mask = m_upper_bounds_raw >= 1

                V_prop = V_prop_raw[valid_mask]

                # Clip the upper bound to a physical maximum (e.g., m=50.0)
                # to prevent sampling impossible "1D string" geometries
                m_upper_bounds = np.clip(m_upper_bounds_raw[valid_mask], 1, 50.0)

                if len(V_prop) == 0:
                    consecutive_zeros += 1
                    continue

                m_prop = rng.uniform(1, m_upper_bounds)

            else:
                m_lower_bounds_raw = (6 * V_prop_raw) / (np.pi * x**3)
                valid_mask = m_lower_bounds_raw <= 1

                V_prop = V_prop_raw[valid_mask]

                # Clip the lower bound to a physical minimum (e.g., m=0.01)
                # to prevent divide-by-zero errors and impossible "2D sheet" geometries
                m_lower_bounds = np.clip(m_lower_bounds_raw[valid_mask], 0.02, 1)

                if len(V_prop) == 0:
                    consecutive_zeros += 1
                    continue

                m_prop = rng.uniform(m_lower_bounds, 1)

            # 2. Forward Calculation

            dI_max_calc, dI_min_calc = self._compute_theoretical_blockages(
                V_prop, m_prop, d, L
            )

            # Clean up unexpected NaNs
            nan_mask = np.isnan(dI_max_calc) | np.isnan(dI_min_calc)
            if np.all(nan_mask):
                consecutive_zeros += 1
                continue

            valid_math = ~nan_mask
            V_prop = V_prop[valid_math]
            m_prop = m_prop[valid_math]
            dI_max_calc = dI_max_calc[valid_math]
            dI_min_calc = dI_min_calc[valid_math]

            # 3. Calculate probability
            # Use safe standard deviations to prevent infinite Z-scores on artificially sharp fits
            safe_std_max = max(std_max, mean_max * 0.01)
            safe_std_min = max(std_min, mean_min * 0.01)

            z_sq_max = ((dI_max_calc - mean_max) / safe_std_max) ** 2
            z_sq_min = ((dI_min_calc - mean_min) / safe_std_min) ** 2

            # Absolute physical constraint: Ignore guesses that are > 4 standard deviations away
            # This prevents the sampler from accepting the "best of the worst" in terrible batches
            physical_mask = (z_sq_max < cutoff_std**2) & (z_sq_min < cutoff_std**2)

            if not np.any(physical_mask):
                consecutive_zeros += 1
                continue

            # Filter arrays to only physically reasonable points before probability rejection
            V_prop = V_prop[physical_mask]
            m_prop = m_prop[physical_mask]
            z_sq_max = z_sq_max[physical_mask]
            z_sq_min = z_sq_min[physical_mask]

            likelihood = np.exp(-0.5 * (z_sq_max + z_sq_min))
            max_likelihood = np.max(likelihood)

            if max_likelihood == 0 or np.isnan(max_likelihood):
                consecutive_zeros += 1
                continue

            prob_accept = likelihood / max_likelihood

            # 4. Accept / Reject
            random_thresh = rng.uniform(0, 1, len(prob_accept))
            accepted_indices = random_thresh < prob_accept

            new_V = V_prop[accepted_indices]
            new_m = m_prop[accepted_indices]

            if len(new_V) == 0:
                consecutive_zeros += 1
            else:
                consecutive_zeros = (
                    0  # Reset counter if we got at least one valid point
                )
                accepted_V.extend(new_V)
                accepted_m.extend(new_m)

        if len(accepted_V) < N_target:
            self.logger.warning(
                f"_generate_vm_ensemble stopped with only {len(accepted_V)}/{N_target} "
                f"accepted samples after {batches} batches (consecutive_zeros={consecutive_zeros})"
            )

        return np.array(accepted_V[:N_target]), np.array(accepted_m[:N_target])

    @log(logger=logger)
    def _ordered_blockages(
        self, popt: npt.NDArray[np.float64]
    ) -> Tuple[float, float, float, float]:
        """
        Sort a double-gaussian fit's two peaks into the larger and smaller blockage.

        ``curve_fit`` returns the two components in whatever order it converged on,
        not in blockage order, so which is which has to be decided here rather than
        assumed. The standard deviations come back signed and are made positive.

        :param popt: the six fitted parameters, two amplitude/mean/sigma triples
        :type popt: npt.NDArray[np.float64]
        :return: the larger mean and its sigma, then the smaller mean and its sigma
        :rtype: Tuple[float, float, float, float]
        """
        _amp1, mean1, std1, _amp2, mean2, std2 = popt
        if mean1 > mean2:
            return mean1, float(np.abs(std1)), mean2, float(np.abs(std2))
        return mean2, float(np.abs(std2)), mean1, float(np.abs(std1))

    @log(logger=logger)
    def _vm_frame(
        self, V: npt.NDArray[np.float64], m: npt.NDArray[np.float64]
    ) -> pd.DataFrame:
        """
        Turn a sampled volume and shape factor into the four geometry columns.

        ``b`` is the minor semi-axis a spheroid of that volume and shape factor has,
        and ``a`` is ``b * m`` by the definition of the shape factor.

        :param V: the sampled volumes in cubic nanometers
        :type V: npt.NDArray[np.float64]
        :param m: the sampled shape factors, one per volume
        :type m: npt.NDArray[np.float64]
        :return: the volume, shape factor and both semi-axes
        :rtype: pd.DataFrame
        """
        b = (3 * V / (4 * np.pi * m)) ** (1 / 3)
        return pd.DataFrame({"V": V, "m": m, "a": b * m, "b": b})

    @log(logger=logger)
    def sample_vm_solutions(
        self, popt: npt.NDArray[np.float64], d: float, L: float, N: int
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Monte Carlo the prolate and oblate geometries one fit is consistent with.

        A pair of blockage levels does not determine a shape: a long thin spheroid
        and a flat wide one can block the same pore by the same amounts. Both
        families are sampled, and it is for the reader to say which is physical.

        :param popt: the six fitted parameters, two amplitude/mean/sigma triples
        :type popt: npt.NDArray[np.float64]
        :param d: the diameter of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :param N: target number of samples to draw for each family
        :type N: int
        :return: the prolate and the oblate solutions
        :rtype: Tuple[pd.DataFrame, pd.DataFrame]
        """
        mean_max, std_max, mean_min, std_min = self._ordered_blockages(popt)

        prolate_V, prolate_m = self._generate_vm_ensemble(
            N, mean_max, std_max, mean_min, std_min, d, L, prolate=True
        )
        oblate_V, oblate_m = self._generate_vm_ensemble(
            N, mean_max, std_max, mean_min, std_min, d, L, prolate=False
        )
        return self._vm_frame(prolate_V, prolate_m), self._vm_frame(oblate_V, oblate_m)

    @log(logger=logger)
    def sample_event_geometries(
        self,
        fits: Sequence[
            Tuple[Optional[npt.NDArray[np.float64]], Optional[npt.NDArray[np.float64]]]
        ],
        histograms: Sequence[
            Optional[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]
        ],
        event_data: Sequence[Dict[str, Any]],
        d: float,
        L: float,
        N: int,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Sample every fitted event's geometry, and summarise each one to a row.

        Every list is index-aligned with ``event_data``, so an event whose histogram
        could not be built and one whose fit was refused drop out the same way and
        neither shifts the others. The per-event row is the median of that event's
        own ensembles, which is what the fit columns written back to the database
        hold.

        :param fits: one (fit parameters, fitted curve) pair per event
        :type fits: Sequence[Tuple[Optional[npt.NDArray[np.float64]], Optional[npt.NDArray[np.float64]]]]
        :param histograms: one histogram per event, or None where none could be built
        :type histograms: Sequence[Optional[Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]]
        :param event_data: the events that were fitted
        :type event_data: Sequence[Dict[str, Any]]
        :param d: the diameter of the pore in nanometers
        :type d: float
        :param L: the length of the pore in nanometers
        :type L: float
        :param N: target number of samples to draw for each family
        :type N: int
        :return: every event's prolate solutions, its oblate solutions, and one summary row per fitted event
        :rtype: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
        """
        prolate_frames: List[pd.DataFrame] = []
        oblate_frames: List[pd.DataFrame] = []
        rows: List[Dict[str, Any]] = []

        for index, event in enumerate(event_data):
            # An event with no histogram had no fit either; skipping it here is what
            # keeps both ensembles describing exactly the events that were fitted.
            if histograms[index] is None:
                continue
            popt, _curve = fits[index]
            if popt is None:
                continue

            mean_max, std_max, mean_min, std_min = self._ordered_blockages(popt)
            df_prolate, df_oblate = self.sample_vm_solutions(popt, d, L, N)
            prolate_frames.append(df_prolate)
            oblate_frames.append(df_oblate)

            rows.append(
                {
                    "id": event["id"],
                    "prolate_volume": self._median_or_nan(df_prolate["V"]),
                    "prolate_shape_factor": self._median_or_nan(df_prolate["m"]),
                    "prolate_major_axis": self._median_or_nan(df_prolate["a"]),
                    "prolate_minor_axis": self._median_or_nan(df_prolate["b"]),
                    "oblate_volume": self._median_or_nan(df_oblate["V"]),
                    "oblate_shape_factor": self._median_or_nan(df_oblate["m"]),
                    "oblate_major_axis": self._median_or_nan(df_oblate["a"]),
                    "oblate_minor_axis": self._median_or_nan(df_oblate["b"]),
                    "min_fractional_blockage": mean_min,
                    "min_fractional_blockage_std": std_min,
                    "max_fractional_blockage": mean_max,
                    "max_fractional_blockage_std": std_max,
                }
            )

        columns = ["V", "m", "a", "b"]
        return (
            (
                pd.concat(prolate_frames, ignore_index=True)
                if prolate_frames
                else pd.DataFrame(columns=columns)
            ),
            (
                pd.concat(oblate_frames, ignore_index=True)
                if oblate_frames
                else pd.DataFrame(columns=columns)
            ),
            pd.DataFrame(rows),
        )

    @log(logger=logger)
    def _median_or_nan(self, values: "pd.Series[float]") -> float:
        """
        The median of a sampled column, or NaN when the sampler returned nothing.

        A bailed-out ensemble is a legitimate answer - the fit describes a geometry
        no spheroid has - and it has to reach the database as a missing value rather
        than as a number.

        :param values: one sampled geometry column
        :type values: pd.Series[float]
        :return: the median, or NaN for an empty column
        :rtype: float
        """
        return float(np.median(values)) if len(values) > 0 else float(np.nan)
