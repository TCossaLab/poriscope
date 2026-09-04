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
