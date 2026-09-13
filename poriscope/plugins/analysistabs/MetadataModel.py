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
from typing import Any, Tuple, override

import numpy as np
import numpy.typing as npt
from scipy.stats import iqr

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaModel import MetaModel


@inherit_docstrings
class MetadataModel(MetaModel):
    """
    Subclass of MetaModel for handling metadata-related processing and storage.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        pass

    @log(logger=logger)
    def _auto_bins_1d(self, data: npt.NDArray[np.float64]) -> int:
        """
        Choose a bin count for a 1-D histogram by the Freedman-Diaconis rule.

        Shared verbatim by the density, histogram and capture-rate paths, which used
        three byte-identical copies of it in ``MetadataView``. ``OverflowError`` is
        **not** caught here because the three callers do not agree on what to do
        about it - two fall back to 100 bins and one to the same expression used when
        the interquartile range is zero - and unifying that would be a behaviour
        change rather than a move. The caller catches it.

        An ``OverflowError`` from ``int()`` on an infinite ratio propagates out
        rather than being handled - there is no ``raise`` here to document, but the
        caller's ``try`` is load-bearing.

        :param data: the values to be binned
        :type data: npt.NDArray[np.float64]
        :return: the number of bins
        :rtype: int
        """
        if iqr(data) > 0:
            return int(
                (np.max(data) - np.min(data)) * len(data) ** (1.0 / 3.0) / (iqr(data))
            )
        return int(3.332 * np.log10(len(data)))

    @log(logger=logger)
    def _auto_bins_2d(self, data: npt.NDArray[np.float64], count: int) -> int:
        """
        Choose one axis's bin count for a 2-D heatmap.

        Deliberately separate from :meth:`_auto_bins_1d`, which it resembles: the
        heatmap uses a fourth root rather than a cube root and falls back to the
        square root of the sample size rather than to Sturges' expression. Both
        divergences are real and are preserved rather than unified, so this move
        changes no output.

        ``count`` is the sample size to raise to the fourth power, and is passed
        rather than taken from ``data`` because the heatmap's y-axis calculation uses
        the *x* array's length. Both arrays are always the same length there - the
        filter that precedes it masks them jointly - so it is inert, and it is
        reproduced rather than quietly corrected.

        :param data: the values to be binned on this axis
        :type data: npt.NDArray[np.float64]
        :param count: the sample size used in the fourth-root term
        :type count: int
        :return: the number of bins
        :rtype: int
        """
        if iqr(data) > 0:
            return int(
                (np.max(data) - np.min(data)) * count ** (1.0 / 4.0) / (iqr(data))
            )
        return int(np.sqrt(len(data)))

    @log(logger=logger)
    def calculate_heatmap(
        self,
        xdata: npt.NDArray[np.float64],
        ydata: npt.NDArray[np.float64],
        bins: Any,
        sizes: bool,
    ) -> Tuple[
        npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]
    ]:
        """
        Bin two columns into a 2-D histogram and return it log2-scaled.

        The arrays arrive already filtered and log-scaled: that step is still
        ``MetaView``'s, and stays there until all eight of its call sites can be
        converted together, so this method is handed exactly what the View's own
        filter produced.

        Empty bins come back as ``-1`` rather than ``-inf``, which is what lets the
        caller's colourbar label them as a count of zero.

        :param xdata: the filtered x values
        :type xdata: npt.NDArray[np.float64]
        :param ydata: the filtered y values
        :type ydata: npt.NDArray[np.float64]
        :param bins: number of bins (if sizes is False) or size of bins (if sizes is True); a list from the controls, or None to estimate
        :type bins: Any
        :param sizes: does the bins parameter refer to bin sizes (True) or counts (False)
        :type sizes: bool
        :return: bin-center x values, bin-center y values, and the log2-scaled 2-D histogram counts
        :rtype: Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]
        :raises ValueError: if bins is an invalid entry when sizes is False
        """
        if bins is not None:
            if sizes is False:
                if isinstance(bins, list) and len(bins) >= 2:
                    xbins = bins[0]
                    ybins = bins[1]
                elif isinstance(bins, list) and len(bins) == 1:
                    xbins = bins[0]
                    ybins = bins[0]
                else:
                    raise ValueError(f"Invalid bin entry: {bins}")
            elif sizes is True:
                if isinstance(bins, list) and len(bins) >= 2:
                    xbins = int((max(xdata) - min(xdata)) / bins[0])
                    ybins = int((max(ydata) - min(ydata)) / bins[1])
                elif isinstance(bins, list) and len(bins) == 1:
                    xbins = int((max(xdata) - min(xdata)) / bins[0])
                    ybins = int((max(ydata) - min(ydata)) / bins[0])
                else:
                    self.logger.info(
                        f"Invalid entry in bins: {bins}, defaulting to iqr"
                    )
                    bins = None
                if xbins <= 1 or ybins <= 1:
                    self.logger.info(
                        f"Invalid entry in bins: {bins}, defaulting to iqr"
                    )
                    bins = None
        if bins is None:
            try:
                xbins = self._auto_bins_2d(xdata, len(xdata))
            except OverflowError:
                xbins = int(np.sqrt(len(xdata)))
            try:
                ybins = self._auto_bins_2d(ydata, len(xdata))
            except OverflowError:
                ybins = int(np.sqrt(len(ydata)))

        z, x, y = np.histogram2d(xdata, ydata, bins=[int(xbins), int(ybins)])
        logged_z = np.empty_like(z)
        for i in range(z.shape[0]):
            for j in range(z.shape[1]):
                logged_z[i, j] = np.log2(z[i, j]) if z[i, j] > 0 else -1

        x = x[:-1] + np.diff(x) / 2.0
        y = y[:-1] + np.diff(y) / 2.0

        return x, y, logged_z.T
