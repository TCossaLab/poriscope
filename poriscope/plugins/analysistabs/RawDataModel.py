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

import numpy as np
from scipy.signal import welch
from typing_extensions import override

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
    def _init(self):
        pass

    @log(logger=logger)
    def integrate_noise(self, f, Pxx):
        """
        Compute the integrated noise from a power spectral density.

        This method integrates the power spectral density (PSD) over frequency
        to obtain the cumulative root-mean-square (RMS) noise as a function of
        frequency. It assumes evenly spaced frequency bins.

        :param f: Array of frequency values (Hz), evenly spaced.
        :type f: numpy.ndarray or list[float]
        :param Pxx: Power spectral density values corresponding to `f`.
        :type Pxx: numpy.ndarray or list[float]
        :return: Array of integrated RMS noise values for each frequency point.
        :rtype: numpy.ndarray
        """
        df = f[1] - f[0]
        return np.sqrt(np.cumsum(Pxx * df))

    @log(logger=logger)
    def calculate_psd(self, psd_data, samplerate):
        """
        Calculate a psd for each dataset in the list, assuming a common samplerate
        """
        Pxx_list = []
        rms_list = []
        for data in psd_data:
            length = len(data) / 10
            f, Pxx = welch(data, samplerate, nperseg=length)
            rms = self.integrate_noise(f, Pxx)
            Pxx_list.append(Pxx)
            rms_list.append(rms)
        return Pxx_list, rms_list, f
