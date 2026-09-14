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
from typing import List, Sequence, override

import numpy as np
import numpy.typing as npt

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaModel import MetaModel


@inherit_docstrings
class EventAnalysisModel(MetaModel):
    """
    Subclass of MetaModel for handling event analysis data.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        pass

    @log(logger=logger)
    def event_time_bases(
        self, traces: Sequence[npt.NDArray[np.float64]], samplerate: float
    ) -> List[npt.NDArray[np.float64]]:
        """
        Build the time axis for each trace, in microseconds.

        The time base is a property of the samples and the rate they were taken at,
        both of which the Model already owns, so it is derived here rather than in
        the widget that draws it. Step 4's rule: the Model returns a derived value
        where it is a property of the data, and pure styling stays in the View.

        One array per trace, index-aligned with ``traces``, because an event may
        contribute up to three of them - its filtered data, its fit and its raw
        trace - and they need not be the same length.

        :param traces: the current traces to build a time axis for
        :type traces: Sequence[npt.NDArray[np.float64]]
        :param samplerate: the sampling rate in Hz, or 1 to fall back to sample indices
        :type samplerate: float
        :return: one time array per trace, in microseconds
        :rtype: List[npt.NDArray[np.float64]]
        """
        return [np.arange(len(trace)) / samplerate * 1e6 for trace in traces]
