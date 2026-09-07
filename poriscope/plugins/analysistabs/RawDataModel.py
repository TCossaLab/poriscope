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
from typing import Optional, override

import numpy as np
import numpy.typing as npt
from fast_histogram import histogram1d
from scipy.signal import welch

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaModel import MetaModel


@inherit_docstrings
class RawDataModel(MetaModel):
    """
    Subclass of MetaModel for processing raw signal data.

    Includes methods to compute PSDs and integrate noise.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        pass

    @log(logger=logger)
    def integrate_noise(
        self, f: npt.NDArray[np.floating], Pxx: npt.NDArray[np.floating]
    ) -> npt.NDArray[np.floating]:
        """
        Compute the integrated noise from a power spectral density.

        This method integrates the power spectral density (PSD) over frequency
        to obtain the cumulative root-mean-square (RMS) noise as a function of
        frequency. It assumes evenly spaced frequency bins.

        :param f: Array of frequency values (Hz), evenly spaced.
        :type f: npt.NDArray[np.floating]
        :param Pxx: Power spectral density values corresponding to `f`.
        :type Pxx: npt.NDArray[np.floating]
        :return: Array of integrated RMS noise values for each frequency point.
        :rtype: npt.NDArray[np.floating]
        """
        df = f[1] - f[0]
        return np.sqrt(np.cumsum(Pxx * df))

    @log(logger=logger)
    def calculate_psd(
        self, psd_data: list, samplerate: float
    ) -> tuple[list, list, Optional[np.ndarray], list[int]]:
        """
        Calculate a psd for each dataset in the list, assuming a common samplerate

        :param psd_data: List of time-domain signal arrays for which PSD will be computed.
        :type psd_data: list
        :param samplerate: Sampling rate of the signal in Hz.
        :type samplerate: float
        :return: Pxx_list, rms_list, the frequency axis, and the indices into
            ``psd_data`` that were successfully processed. A channel is
            skipped (and its index omitted) if it has too few samples, if
            ``welch()`` fails, or if the resulting frequency axis is too
            short to integrate noise over.
        :rtype: tuple[list, list, Optional[np.ndarray], list[int]]
        """
        Pxx_list = []
        rms_list = []
        kept_indices = []
        f = None
        for index, data in enumerate(psd_data):
            length = int(len(data) / 10)
            if length < 1:
                self.logger.warning(
                    f"Skipping PSD calculation for a channel with insufficient data ({len(data)} samples)"
                )
                continue
            try:
                f, Pxx = welch(data, samplerate, nperseg=length)
                rms = self.integrate_noise(f, Pxx)
            except Exception as e:
                self.logger.warning(f"Unable to calculate PSD for a channel: {e}")
                continue
            Pxx_list.append(Pxx)
            rms_list.append(rms)
            kept_indices.append(index)
        return Pxx_list, rms_list, f, kept_indices

    @log(logger=logger)
    def get_baseline_stats(
        self, data: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        """
        Get the local amplitude, mean, and standard deviation for a chunk of data. Assumes data is rectified.


        :param data: Chunk of timeseries data to compute statistics on.
        :type data: npt.NDArray[np.float64]
        :return: Array of local amplitude, mean, and standard deviation, in that order.
        :rtype: npt.NDArray[np.float64]
        :raises ValueError: If a baseline histogram width cannot be estimated for this chunk (no variation in the data), or if the underlying Gaussian fit fails.
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
            baseline_params = np.array(
                self.gaussian_fit(
                    hist,
                    centers,
                    centers[max_index],
                    np.absolute(
                        centers[top_index] - centers[bottom_index]
                    ),  # take an overestimate for std, seems to perform better overall
                )
            )
        except ValueError:
            raise
        return baseline_params

    @log(logger=logger)
    def gaussian_fit(
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
