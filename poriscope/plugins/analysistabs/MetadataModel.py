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
from typing import override

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
