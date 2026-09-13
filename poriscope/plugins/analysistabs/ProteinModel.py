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

import logging
from typing import List, Optional, Sequence, Tuple, override

import numpy as np
import numpy.typing as npt
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, peak_widths
from scipy.stats import t

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaModel import MetaModel


@inherit_docstrings
class ProteinModel(MetaModel):
    """
    Subclass of MetaModel for handling protein volume/shape-factor fitting data and storage.
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
        Step 4a exists to delete. It also means the View does not depend on the
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
